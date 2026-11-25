"""Wave 7 S2: the stream origin, per-arm client paths, route matches, and the S2 configs."""
import importlib.util
import json
import os
import re
import tempfile
import unittest

from epl import envoy_config as ec
from epl import evidence, experiment, origin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S2 = os.path.join(ROOT, "examples", "wave7s2")
CFG = os.path.join(S2, "configs")
ENV = {"listener_port": 10110, "admin_port": 9921}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mk = _load("w7s2_make_t", os.path.join(S2, "make.py"))
pick = _load("w7s2_pick_t", os.path.join(S2, "s2_pick.py"))


class Harness(unittest.TestCase):
    def test_route_match_and_shared_route(self):
        sh = mk.s2a_shapes()
        b = ec.bootstrap(sh, dict(ENV), 8092)
        rts = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]["route_config"][
            "virtual_hosts"][0]["routes"]
        self.assertEqual(rts, [{"match": {"prefix": "/c"}, "route": {"cluster": "origin"}}])
        self.assertEqual(ec.origin_files(sh), {})  # the stream origin serves them, nginx gets no file
        plain = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200}]
        self.assertEqual(ec.bootstrap(plain, dict(ENV), 8092)["static_resources"]["listeners"][0]["filter_chains"][0][
            "filters"][0]["typed_config"]["route_config"]["virtual_hosts"][0]["routes"][0]["match"], {"path": "/s"})

    def test_origin_server_stream_ports(self):
        e = experiment.load(os.path.join(CFG, "s2a-chunked.json"))
        arms = {a["name"]: a for a in e["arms"]}
        port = lambda a: experiment.arm_envoy(e, arms[a])["upstream_port"]  # noqa: E731
        self.assertEqual(port("cl"), 8098)
        self.assertEqual(port("ch8k"), 8098)
        self.assertEqual(port("h2in"), 8099)
        b = json.loads(ec.bootstrap_text(e["shapes"], experiment.arm_envoy(e, arms["h2in"]), 8092))
        self.assertIn("http2_protocol_options", json.dumps(b["static_resources"]["clusters"][0]))
        bad = json.loads(json.dumps(e))
        bad["origin"].pop("stream_sha256")
        self.assertTrue(any("stream_sha256" in x for x in experiment.validate(bad, allow_short=True)))

    def test_stream_origin_args_are_loopback_and_pinned(self):
        cfg = {"stream_port": 8098, "stream_h2_port": 8099, "image": "nginx:alpine@sha256:x"}
        a = origin.stream_args(cfg, "32-39,72-79", "n", "/h/bin")
        self.assertEqual(a[a.index("-h1") + 1], "127.0.0.1:8098")
        self.assertEqual(a[a.index("-h2") + 1], "127.0.0.1:8099")
        self.assertEqual(a[a.index("--cpuset-cpus") + 1], "32-39,72-79")
        self.assertIn("/h/bin:/epl-streamorigin:ro", a)
        self.assertNotIn("0.0.0.0", " ".join(a))

    def test_stream_window(self):
        w = origin.stream_window({"responses": 10, "events": 100, "max_late_us": 3}, {"responses": 30, "events": 500, "max_late_us": 9})
        self.assertEqual(w, {"ok": True, "d": {"responses": 20, "events": 400}, "max_late_us": 9})
        self.assertFalse(origin.stream_window(None, {"responses": 1})["ok"])

    def test_wire_sizes_match_the_origin_source(self):
        src = open(os.path.join(ROOT, "tools", "streamorigin", "main.go")).read()
        for name, want in (("headCL", mk.HEAD_CL), ("headCh", mk.HEAD_CH), ("headSSE", mk.HEAD_SSE)):
            m = re.search(r'%s\s+= "([^"]*)"' % name, src)
            self.assertEqual(m.group(1).encode().decode("unicode_escape"), want, name)
        self.assertEqual(mk.wire_cl(65536), 65618)           # read back by Envoy in the local functional check
        self.assertEqual(mk.wire_chunked(65536, 8192), 65692)
        self.assertEqual(mk.wire_chunked(65536, 4096), 65756)
        self.assertEqual(mk.wire_chunked(1048576, 8192), 1049692)
        self.assertEqual(mk.wire_sse(20), 4205)
        self.assertEqual(mk.wire_sse(200), 41285)


class Configs(unittest.TestCase):
    def test_arms_rounds_and_rates(self):
        legs = {}
        for fn in sorted(os.listdir(CFG)):
            e = experiment.load(os.path.join(CFG, fn))
            self.assertEqual(experiment.validate(e, allow_short=True), [], fn)
            legs[fn[:-5]] = len(experiment.cells(e)) * e["rounds"]
            self.assertEqual(e["idle"]["procs"], [], fn)
            for a in e["arms"]:
                self.assertEqual(a["source_sha256"], "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc", fn)
        self.assertEqual([legs[k] for k in ("s2a-chunked", "s2b-stream", "s2c-buf", "s2d-h3")], [72, 36, 18, 36])
        self.assertEqual([legs["smoke-" + k] for k in ("s2a-chunked", "s2b-stream", "s2c-buf", "s2d-h3")], [12, 6, 3, 6])
        mech = ("mech-sys-chunked", "mech-sys-stream", "mech-sys-grpc", "mech-sys-buf", "mech-sys-h3", "mech-kcg-chunked",
                "mech-kcg-stream", "mech-kcg-h3")
        self.assertEqual([legs[k] for k in mech], [6, 4, 4, 6, 2, 2, 2, 2])
        self.assertEqual([legs[k] for k in ("smoke-mech-sys", "smoke-mech-kcg")], [2, 2])
        rate = lambda fn: {s["name"]: s["rps"] for s in experiment.load(os.path.join(CFG, fn))["shapes"]}  # noqa: E731
        self.assertEqual(rate("s2a-chunked.json"), {"b64k": 4000, "b1m": 800})
        self.assertEqual(rate("s2a-chunked-h1m.json"), {"b64k": 4000, "b1m": 400})
        self.assertEqual(rate("s2a-chunked-hh.json"), {"b64k": 2000, "b1m": 400})
        # both streamed shapes carry the same event rate
        for fn in ("s2b-stream.json", "s2b-stream-half.json"):
            ev = {s["name"]: s["rps"] * s["events"] for s in experiment.load(os.path.join(CFG, fn))["shapes"]}
            self.assertEqual(ev["ev20"], ev["ev200"], fn)
        self.assertEqual(rate("s2d-h3.json"), {"z0": 2000, "s": 2000})

    def test_s2a_paths_have_one_length_and_name_the_pattern(self):
        e = experiment.load(os.path.join(CFG, "s2a-chunked.json"))
        for sh in ("b64k", "b1m"):
            ps = {a["name"]: a["client"]["paths"][sh] for a in e["arms"]}
            self.assertEqual(len({len(p) for p in ps.values()}), 1, ps)
            self.assertTrue(ps["cl"].startswith("/cl?") and "chunk=0" in ps["cl"])
            self.assertTrue(ps["cl8k"].startswith("/cl?") and "chunk=8192" in ps["cl8k"])
            self.assertTrue(ps["ch8k"].startswith("/chunked?") and "chunk=8192" in ps["ch8k"])
            self.assertTrue(ps["ch4k"].startswith("/chunked?") and "chunk=4096" in ps["ch4k"])
            self.assertEqual(ps["cl"], ps["cl-A2"])
            self.assertEqual(ps["cl"], ps["h2in"])
        base = e["base_arm"]
        self.assertEqual(base, "cl")

    def test_idle_off_is_three_timers_and_no_route_timeout(self):
        e = experiment.load(os.path.join(CFG, "s2b-stream.json"))
        arms = {a["name"]: a for a in e["arms"]}
        b = json.loads(ec.bootstrap_text(e["shapes"], experiment.arm_envoy(e, arms["idle-off"]), 8092))
        hcm = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]
        self.assertEqual(hcm["stream_idle_timeout"], "0s")
        self.assertEqual(hcm["common_http_protocol_options"], {"idle_timeout": "0s"})
        opts = b["static_resources"]["clusters"][0]["typed_extension_protocol_options"][
            "envoy.extensions.upstreams.http.v3.HttpProtocolOptions"]
        self.assertEqual(opts["common_http_protocol_options"], {"idle_timeout": "0s"})
        self.assertNotIn('"timeout"', json.dumps(hcm["route_config"]))
        b0 = json.loads(ec.bootstrap_text(e["shapes"], experiment.arm_envoy(e, arms["base"]), 8092))
        self.assertNotIn("idle_timeout", json.dumps(b0))
        # the evidence passes on its own bootstrap and fails on the other arm's
        for mine, other in (("idle-off", b0), ("base", b)):
            items = [it for it in arms[mine]["evidence"] if it.get("scope") == "config"]
            self.assertTrue(items)
            self.assertFalse(all(evidence.check_item({}, it, other)["ok"] for it in items), mine)
            own = b if mine == "idle-off" else b0
            self.assertTrue(all(evidence.check_item({}, it, own)["ok"] for it in items), mine)

    def test_h3_arms_are_g1(self):
        g = _load("w4g_make_t", os.path.join(ROOT, "examples", "wave4g", "make.py"))
        ref = {a["name"]: a for a in g.g1(False, 2000)["arms"]}
        e = experiment.load(os.path.join(CFG, "s2d-h3.json"))
        for a in e["arms"]:
            self.assertEqual(a["settings"], ref[a["name"]]["settings"], a["name"])
            self.assertEqual(a["client"], ref[a["name"]]["client"], a["name"])
            self.assertEqual(a["validity"], ref[a["name"]]["validity"], a["name"])
        self.assertEqual(e["client"]["extra_args"], g.g1(False, 2000)["client"]["extra_args"])
        self.assertEqual(e["envoy"]["codec_type"], "HTTP2")

    def test_everything_binds_to_loopback(self):
        for fn in sorted(os.listdir(CFG)):
            e = experiment.load(os.path.join(CFG, fn))
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                _, texts, _ = experiment.prepare_bootstraps(e, d, make_certs=False)
            addrs = []

            def walk(x):
                if isinstance(x, dict):
                    if "address" in x and "port_value" in x:
                        addrs.append(str(x["address"]))
                    self.assertNotIn("pipe", x, fn)
                    for v in x.values():
                        walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
            for t in texts.values():
                walk(json.loads(t))
            self.assertTrue(addrs, fn)
            self.assertEqual([a for a in addrs if not a.startswith("127.")], [], fn)
            conf = ec.nginx_conf(e["origin"]["port"], 8, stub_status=True)
            self.assertEqual([x for x in re.findall(r"listen ([^ ;]+)", conf) if not x.startswith("127.")], [], fn)
            if e["origin"].get("stream_port"):
                a = origin.stream_args(e["origin"], e["cpus"]["origin"], "n", "/b")
                self.assertEqual([x for x in a if re.match(r"^\d+\.\d+\.\d+\.\d+:", x) and not x.startswith("127.")], [], fn)

    def test_mech_configs_use_the_wrappers_and_are_not_scored(self):
        for fn in sorted(os.listdir(CFG)):
            if "mech" not in fn:
                continue
            e = json.load(open(os.path.join(CFG, fn)))
            self.assertTrue(e["smoke"] and e["rounds"] == 1 and e["evidence_mode"] == "record", fn)
            self.assertRegex(e["measure"]["perf"], r"^bash ~/epl/harness-wave7s2/examples/wave7s2/perf-(sys|kcg)\.sh$", fn)
            self.assertEqual(("kcg" in fn), e["measure"]["perf"].endswith("perf-kcg.sh"), fn)
            for sh in e["shapes"]:
                self.assertGreaterEqual(sum(1 for a in e["arms"] if not a.get("shapes") or sh["name"] in a["shapes"]), 2, fn)


class Pick(unittest.TestCase):
    def leg(self, shape, arm, valid=True, reasons=None, ev_failed=None):
        return {"leg_id": "%s-%s" % (shape, arm), "shape": shape, "arm": arm,
                "verdict": {"valid": valid, "reasons": reasons or []},
                "evidence": {"ok": not ev_failed, "failed": ev_failed or []}}

    def decide(self, legs, kind):
        with tempfile.TemporaryDirectory(dir="/tmp") as d:
            with open(os.path.join(d, "legs.jsonl"), "w") as f:
                for m in legs:
                    f.write(json.dumps(m) + "\n")
            import contextlib
            import io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                pick.main([kind, d])
            return buf.getvalue().strip()

    def test_s2a(self):
        ok = [self.leg(s, a) for s in ("b64k", "b1m") for a in ("cl", "ch8k")]
        self.assertEqual(self.decide(ok, "s2a"), "s2a-chunked")
        load = ok[:3] + [self.leg("b1m", "ch8k", False, ["client headroom 12% under 25%"])]
        self.assertEqual(self.decide(load, "s2a"), "s2a-chunked-h1m")
        so = [self.leg("b64k", "cl", False, ["side service stream_origin used 61% of its CPU set in the window, limit 50%"])] + ok[1:]
        self.assertEqual(self.decide(so, "s2a"), "s2a-chunked-h64")
        both = [self.leg("b64k", "cl", False, ["achieved rate 3800.0 misses target 4000 by 5.00%"]),
                self.leg("b1m", "cl", True, None, ["origin: its own response count per request 1.000: 0.9 per request"])]
        self.assertEqual(self.decide(both, "s2a"), "s2a-chunked-hh")
        hard = ok[:3] + [self.leg("b1m", "ch8k", False, ["envoy exit code 1"])]
        self.assertEqual(self.decide(hard, "s2a"), "fail")
        hard_ev = ok[:3] + [self.leg("b1m", "ch8k", True, None, ["upstream bytes read per request: 1 per request"])]
        self.assertEqual(self.decide(hard_ev, "s2a"), "fail")
        self.assertEqual(self.decide(ok[:2], "s2a"), "fail")  # a shape without legs

    def test_s2b(self):
        ok = [self.leg(s, a) for s in ("ev20", "ev200") for a in ("base", "idle-off")]
        self.assertEqual(self.decide(ok, "s2b"), "s2b-stream")
        late = ok[:3] + [self.leg("ev200", "idle-off", True, None,
                                  ["origin: events sent more than 0.5 ms late under 0.1% of events: 0.004 outside [None, 0.001]"])]
        self.assertEqual(self.decide(late, "s2b"), "s2b-stream-half")
        self.assertEqual(self.decide(ok[:3] + [self.leg("ev200", "idle-off", False, ["error: x"])], "s2b"), "fail")

    def test_every_origin_evidence_label_counts_as_load(self):
        e = experiment.load(os.path.join(CFG, "s2b-stream.json"))
        for it in e["arms"][0]["evidence"]:
            if it["stat"].startswith("stream_origin.d.") and it["stat"].split(".")[-1] in (
                    "responses", "events", "write_calls", "late_events", "body_bytes"):
                self.assertTrue(evidence.label(it).startswith(pick.EV_LOAD), it)


if __name__ == "__main__":
    unittest.main()
