import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest

from epl import envoy_config, evidence, experiment
from epl.__main__ import check_expect, request_headers
from epl.sim import SimBackend

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SM = os.path.join(HERE, "examples", "settings-matrix")
F2DIR = os.path.join(SM, "features2")


def _mod(name, path):
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.path.pop(0)


F2 = _mod("features2", os.path.join(SM, "features2.py"))
FT2 = _mod("features_table2", os.path.join(SM, "features_table2.py"))
BODY = _mod("make_json_body", os.path.join(F2DIR, "make_json_body.py"))
S = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 1600}]
E = {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True}


def filters(b):
    h = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]
    return h["http_filters"]


class FilterSettingsTest(unittest.TestCase):
    def test_compressor(self):
        for lib in ("gzip", "brotli", "zstd"):
            fs = filters(envoy_config.bootstrap(S, dict(E, compressor={"library": lib}), 8092))
            self.assertEqual([f["name"] for f in fs], ["envoy.filters.http.compressor", "envoy.filters.http.router"])
            tc = fs[0]["typed_config"]
            self.assertNotIn("request_direction_config", tc)
            self.assertEqual(tc["response_direction_config"]["common_config"], {"min_content_length": 30})
            lc = tc["compressor_library"]
            self.assertEqual(lc["name"], "epl")
            self.assertEqual(lc["typed_config"]["chunk_size"], 4096)
            self.assertTrue(lc["typed_config"]["@type"].endswith(".v3." + {"gzip": "Gzip", "brotli": "Brotli",
                                                                             "zstd": "Zstd"}[lib]))
        g = filters(envoy_config.bootstrap(S, dict(E, compressor={"library": "gzip"}), 8092))[0]
        self.assertEqual(g["typed_config"]["compressor_library"]["typed_config"]["window_bits"], 12)
        b = filters(envoy_config.bootstrap(S, dict(E, compressor={"library": "brotli", "quality": 5}), 8092))[0]
        self.assertEqual(b["typed_config"]["compressor_library"]["typed_config"]["quality"], 5)
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S, dict(E, compressor={"library": "lz4"}), 8092)
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S, dict(E, compressor={"library": "gzip", "level": 9}), 8092)

    def test_lua_and_wasm(self):
        fs = filters(envoy_config.bootstrap(S, dict(E, lua={"inline": "function envoy_on_request(h) end"}), 8092))
        self.assertEqual(fs[0]["name"], "envoy.filters.http.lua")
        self.assertIn("envoy_on_request", fs[0]["typed_config"]["default_source_code"]["inline_string"])
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S, dict(E, lua={"file": "x.lua"}), 8092)
        w = {"file": "/abs/m.wasm", "sha256": "ab", "runtime": "envoy.wasm.runtime.v8"}
        fs = filters(envoy_config.bootstrap(S, dict(E, wasm=w), 8092))
        c = fs[0]["typed_config"]["config"]
        self.assertEqual(c["vm_config"]["code"]["local"]["filename"], "/abs/m.wasm")
        self.assertEqual(c["vm_config"]["runtime"], "envoy.wasm.runtime.v8")
        self.assertEqual(c["failure_policy"], "FAIL_CLOSED")
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S, dict(E, wasm=dict(w, runtime="envoy.wasm.runtime.wamr")), 8092)

    def test_origin_types_and_bodies(self):
        self.assertEqual(envoy_config.nginx_conf(8092, 8), envoy_config.nginx_conf(8092, 8, types={}))
        c = envoy_config.nginx_conf(8092, 8, types={"/j4": "application/json"})
        self.assertIn("location = /j4 { types { } default_type application/json; }", c)
        self.assertNotIn("gzip", c)
        sh = F2.shapes({})
        b = envoy_config.origin_bodies([sh["j4"], sh["j16"], sh["s"]], experiment.HARNESS_ROOT)
        self.assertEqual(sorted(b), ["j16", "j4"])
        self.assertEqual(len(b["j16"]), 16384)
        bad = dict(sh["j4"], body_sha256="0" * 64)
        with self.assertRaises(ValueError):
            envoy_config.origin_bodies([bad], experiment.HARNESS_ROOT)
        with self.assertRaises(ValueError):
            envoy_config.origin_bodies([dict(sh["j4"], body_bytes=4000)], experiment.HARNESS_ROOT)
        with self.assertRaises(ValueError):
            envoy_config.content_types([sh["j4"], dict(sh["j4"], content_type="text/plain")])

    def test_validate_shapes(self):
        tmp = tempfile.mkdtemp()
        c = json.load(open(os.path.join(F2DIR, "14-compression.json")))
        c["shapes"][0]["body_sha256"] = "0" * 64
        c["shapes"][1]["warmup_s"] = -1
        p = os.path.join(tmp, "c.json")
        json.dump(c, open(p, "w"))
        errs = experiment.validate(experiment.load(p))
        self.assertTrue(any("body_sha256" in e for e in errs), errs)
        self.assertTrue(any("warmup_s" in e for e in errs), errs)


class BodiesAndModulesTest(unittest.TestCase):
    def test_bodies_are_reproducible_and_reserved(self):
        for name, size in BODY.SIZES.items():
            b = BODY.body(size)
            self.assertEqual(len(b), size)
            with open(os.path.join(F2DIR, "bodies", name), "rb") as f:
                self.assertEqual(f.read(), b, name + ": rerun make_json_body.py")
            self.assertEqual(hashlib.sha256(b).hexdigest(), F2.sums("features2/bodies", name))
            doc = json.loads(b)
            for rec in doc["data"]:
                self.assertTrue(rec["user"]["email"].endswith("@example.com"))
                self.assertTrue(rec["host"].endswith(".example.test"))
            self.assertEqual(doc["total"], len(doc["data"]))

    def test_wasm_modules_match_their_digests(self):
        for k in ("empty", "header"):
            w = F2.WASM[k]
            with open(os.path.join(HERE, w["file"]), "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), w["sha256"])
        with open(os.path.join(F2DIR, "wasm", "TOOLCHAIN")) as f:
            tc = f.read()
        self.assertIn("rustc 1.84.1", tc)
        self.assertIn("@sha256:", tc)
        with open(os.path.join(F2DIR, "wasm", "build.sh")) as f:
            self.assertIn(tc.split("image ")[1].split()[0], f.read())
        for d in ("rust-std", "proxy-wasm-0.2.2"):
            self.assertTrue(os.listdir(os.path.join(F2DIR, "wasm", "licenses", d)))

    def test_check_wasm(self):
        exp = experiment.load(os.path.join(F2DIR, "run-f.json"))
        self.assertEqual(experiment.check_wasm(exp), [])
        files = experiment.wasm_files(exp)
        self.assertEqual(sorted(files), ["wasm-empty", "wasm-header"])
        self.assertTrue(os.path.isabs(files["wasm-empty"][0]))
        exp["arms"][3]["settings"]["wasm"]["sha256"] = "0" * 64
        self.assertTrue(any("sha256" in e for e in experiment.check_wasm(exp)))


class EvidenceShapesTest(unittest.TestCase):
    def legs(self):
        out = []
        for arm, extra in (("filter-off", 0), ("lua-header", 17)):
            for shape, base in (("s", 300), ("fh", 900)):
                out.append({"leg_id": "r01-%s-%s" % (shape, arm), "arm": arm, "shape": shape, "round": 1,
                            "responses_raw": 1000, "verdict": {"valid": True},
                            "sut_stats_window": {"http.ingress_http.downstream_cx_tx_bytes_total": 1000 * (base + extra)}})
        return out

    def test_freeze_per_shape_and_shape_items(self):
        spec = {"lua-header": [{"stat": "http.ingress_http.downstream_cx_tx_bytes_total",
                                "ref": {"arm": "filter-off", "offset": 17}, "tol_abs": 3}]}
        frozen, problems = evidence.freeze(spec, self.legs())
        self.assertEqual(problems, [])
        items = {it["shape"]: it["per_request"] for it in frozen["lua-header"]}
        self.assertEqual(items, {"fh": 917.0, "s": 317.0})
        for m in self.legs():
            if m["arm"] == "lua-header":
                ev = evidence.evaluate(m, frozen["lua-header"])
                self.assertTrue(ev["ok"], ev)
                self.assertEqual(len(ev["items"]), 1)  # only the item of its own shape
        # refreezing keeps frozen items as they are
        again, _ = evidence.freeze(frozen, self.legs())
        self.assertEqual(again, frozen)

    def test_prefix_absent(self):
        m = {"shape": "s", "sut_stats_window": {"http.ingress_http.lua.errors": 0, "x": 1}}
        it = {"stat": "http.ingress_http.lua.*", "absent": True}
        self.assertFalse(evidence.check_item(m, it)["ok"])
        self.assertTrue(evidence.check_item(m, {"stat": "wasm.*", "absent": True})["ok"])

    def test_ref_is_a_kind(self):
        self.assertEqual(evidence.validate_items([{"stat": "a", "ref": {"arm": "self"}, "tol": 0.02}]), [])


class Session2ConfigsTest(unittest.TestCase):
    def test_written_configs_are_current(self):
        for fn, c in F2.configs({}).items():
            with open(os.path.join(F2DIR, fn)) as f:
                self.assertEqual(json.load(f), json.loads(json.dumps(c)), fn + ": rerun features2.py")

    def test_validate_and_plan(self):
        legs = {"aa-2.json": (96, 192), "run-f.json": (200, 300), "14-compression.json": (128, 192),
                "lc-j16.json": (72, 72), "14b.json": (32, 64), "lc-sfh.json": (48, 48)}
        for fn in sorted(x for x in os.listdir(F2DIR) if x.endswith(".json")):
            exp = experiment.load(os.path.join(F2DIR, fn))
            short = fn.startswith("smoke") or fn == "jit-check.json"
            self.assertEqual(experiment.validate(exp, allow_short=short), [], fn)
            self.assertEqual(exp["order_seed"], 22, fn)
            for a in exp["arms"]:
                self.assertTrue(a.get("evidence"), fn + " " + a["name"])
            if fn in legs:
                mx = exp["rounds_max"] if exp.get("adaptive", True) else exp["rounds"]
                self.assertEqual((len(experiment.schedule(exp)), len(experiment.schedule(exp, 1, mx))), legs[fn], fn)

    def test_rules(self):
        c = F2.run_configs({"j16": 2000, "f_warmup_s": 15})
        f = c["run-f.json"]
        self.assertEqual(f["client"]["warmup_s"], 15)
        self.assertEqual({s["name"]: s["stop_target_half_width_pct"] for s in f["shapes"]}, {"s": 0.8, "fh": 1.5})
        self.assertEqual(f["floor_arm"], "base-A2")
        c14 = c["14-compression.json"]
        self.assertIn("minor-faults", c14["measure"]["perf_events"])
        self.assertEqual([s["rps"] for s in c14["shapes"]], [5200, 2000])
        for s in c14["shapes"]:
            self.assertIn("accept-encoding:gzip, br, zstd", s["client_extra_args"])
        ref = [a for a in c14["arms"] if a["name"] == "comp-off"][0]
        self.assertNotIn("settings", ref)
        lc = c["lc-j16.json"]
        self.assertEqual([a["name"] for a in lc["arms"]], ["comp-off", "comp-off-A2"])
        self.assertEqual([s.get("lead_in_s") for s in lc["shapes"]], [None, 3, 3])
        idle = c["14b.json"]["arms"][1]
        self.assertEqual(idle["settings"], {"compressor": {"library": "gzip"}})
        self.assertIn("not_compressed", idle["evidence"][0]["stat"])
        jit = c["jit-check.json"]
        self.assertEqual([s["warmup_s"] for s in jit["shapes"]], [5, 30])

    def test_smokes_cover_every_arm_and_check_lists(self):
        cfgs = F2.configs({})
        smokes = {fn[:-5]: c for fn, c in cfgs.items() if fn.startswith("smoke")}
        self.assertEqual(sorted(smokes), sorted(s for v in F2.CHECK.values() for s in v))
        for run, sl in F2.CHECK.items():
            smoked = {a["name"] for s in sl for a in smokes[s]["arms"]}
            self.assertEqual(smoked, {a["name"] for a in cfgs[run + ".json"]["arms"]}, run)
        with open(os.path.join(SM, "run-session-2.sh")) as f:
            txt = f.read()
        for s in smokes:
            self.assertIn(s, txt)
        self.assertIn('if [ "$rc" -eq 3 ] && [ "${FORCE:-0}" = 1 ]; then', txt)
        self.assertIn("timeout --foreground --signal=TERM", txt)
        self.assertEqual(F2.MANDATORY + F2.OPTIONAL, ["aa-2", "run-f", "14-compression", "lc-j16", "14b", "lc-sfh"])


class ProbeHelpersTest(unittest.TestCase):
    def test_headers_and_expect(self):
        sh = F2.shapes({})["j4"]
        self.assertEqual(request_headers(sh), [("accept-encoding", "gzip, br, zstd")])
        h = [("Content-Encoding", "br"), ("x-epl-filter", "1")]
        self.assertEqual(check_expect(h, ["content-encoding=br", "x-epl-filter=1", "vary="]), [])
        self.assertEqual(len(check_expect(h, ["content-encoding=gzip"])), 1)
        self.assertEqual(len(check_expect(h, ["x-epl-filter="])), 1)


class Table2Test(unittest.TestCase):
    def test_interpolate(self):
        pts = [(0.14, 600e3, "j16"), (0.30, 520e3, "j16-a"), (0.60, 470e3, "j16-c")]
        self.assertAlmostEqual(FT2.interpolate(pts, 0.45), 495e3)
        self.assertIsNone(FT2.interpolate(pts, 0.70))

    def test_jit(self):
        d = tempfile.mkdtemp()
        legs = []
        for arm, d5 in (("lua-header", 1.002), ("wasm-header", 1.009)):
            for s, f in (("s-wu5", d5), ("s-wu30", 1.0)):
                legs.append({"arm": arm, "shape": s, "round": 1, "verdict": {"valid": True},
                             "per_req": {"instructions_u": 200e3 * f}})
        with open(os.path.join(d, "results.json"), "w") as fh:
            json.dump({"legs": legs, "metadata": {}}, fh)
        out, ok = FT2.jit(d)
        self.assertFalse(ok)
        self.assertAlmostEqual(out["lua-header"]["diff_pct"], 0.2)
        self.assertAlmostEqual(out["wasm-header"]["diff_pct"], 0.9)

    def test_tables_on_a_dry_run(self):
        tmp = tempfile.mkdtemp()
        sess = os.path.join(tmp, "s2")
        for fn, fac in (("aa-2.json", {}), ("run-f.json", {"lua-header": 1.03, "wasm-header": 1.06})):
            c = json.load(open(os.path.join(F2DIR, fn)))
            for a in c["arms"]:
                a["sim_factor"] = fac.get(a["name"], 1.0)
            c.pop("floor_from", None)
            c.pop("floor_arm", None)
            c["sim_cycles_noise"] = 0.004
            p = os.path.join(tmp, fn)
            json.dump(c, open(p, "w"))
            experiment.Runner(experiment.load(p), os.path.join(sess, fn[:-5]), SimBackend).run(simulate=True)
        text, js = FT2.tables(FT2.FT.load_session(sess))
        fam = js["families"]["confirmatory"]
        self.assertEqual((fam["size"], fam["with_data"]), (10, 4))
        rows = {(r["shape"], r["arm"]): r for r in fam["rows"] if r["run"] == "run-f"}
        self.assertTrue(rows[("fh", "wasm-header")]["verdict"].startswith("differs"))
        self.assertEqual(js["families"]["secondary"]["size"], 7)
        self.assertIn("Wasm against Lua, header", text)
        self.assertIn("j4 | base-A2 on s (borrowed)", text.replace("14-compression / ", ""))


if __name__ == "__main__":
    unittest.main()
