import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

from epl import envoy_config, evidence, experiment
from epl.sim import SimBackend

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SM = os.path.join(HERE, "examples", "settings-matrix")
FEAT = os.path.join(SM, "features")


def _mod(name, path):
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.path.pop(0)


F = _mod("features", os.path.join(SM, "features.py"))
FT = _mod("features_table", os.path.join(SM, "features_table.py"))


class FeatureConfigsTest(unittest.TestCase):
    def test_written_configs_are_current(self):
        for fn, c in F.configs({}).items():
            with open(os.path.join(FEAT, fn)) as f:
                self.assertEqual(json.load(f), json.loads(json.dumps(c)), fn + ": rerun features.py")

    def test_every_config_validates(self):
        for fn in sorted(os.listdir(FEAT)):
            exp = experiment.load(os.path.join(FEAT, fn))
            self.assertEqual(experiment.validate(exp, allow_short=fn.startswith("smoke")), [], fn)
            self.assertEqual(exp["order_seed"], 21, fn)
            with tempfile.TemporaryDirectory() as d:
                _, texts, _ = experiment.prepare_bootstraps(exp, d, make_certs=False)
            for a in exp["arms"]:
                self.assertTrue(a.get("evidence"), "%s %s has no evidence" % (fn, a["name"]))
                self.assertLessEqual(len(experiment.arm_settings(a)) + len(a.get("env", {})), 1, fn)
                if a["name"].endswith("-A2") or a["name"] == exp["base_arm"]:
                    continue
            if fn.startswith("smoke"):
                self.assertEqual(exp["evidence_mode"], "record", fn)
                self.assertNotIn("floor_from", exp)

    def test_baseline_bootstrap_is_the_matrix_baseline(self):
        # the reference arms of the s+fh runs render the same bootstrap as week 4's baseline
        def text(path, arm):
            exp = experiment.load(path)
            a = [x for x in exp["arms"] if x["name"] == arm][0]
            return envoy_config.bootstrap_text(exp["shapes"], experiment.arm_envoy(exp, a, "/r"),
                                               exp["origin"]["port"], "/r/certs")
        wk4 = text(os.path.join(SM, "filters", "12-local-ratelimit.json"), "ratelimit-off")
        for fn, arm in (("run-s.json", "base"), ("run-s.json", "base-A2"), ("18-access-log.json", "log-off"),
                        ("17-tracing.json", "trace-off"), ("13-ext-authz.json", "authz-off")):
            self.assertEqual(text(os.path.join(FEAT, fn), arm), wk4, fn)

    def test_rows_and_rules(self):
        c = F.run_configs({})
        s = c["run-s.json"]
        self.assertEqual([a["name"] for a in s["arms"]], ["base", "retry-on", "idle-off", "percpu-on", "base-A2"])
        self.assertEqual((s["rounds"], s["rounds_block"], s["rounds_max"]), (20, 10, 30))
        self.assertEqual({x["name"]: x["stop_target_half_width_pct"] for x in s["shapes"]}, {"s": 0.8, "fh": 0.8})
        self.assertEqual(s["stop"]["rows"], "confirmatory")
        pc = [a for a in s["arms"] if a["name"] == "percpu-on"][0]
        self.assertEqual(pc["env"], {"GLIBC_TUNABLES": "glibc.pthread.rseq=0"})
        lg = c["18-access-log.json"]
        self.assertEqual({x["name"]: x["stop_target_half_width_pct"] for x in lg["shapes"]}, {"s": 0.8, "fh": 1.5})
        self.assertEqual(lg["floor_arm"], "base-A2")
        for fn in ("17-tracing.json", "13-ext-authz.json"):
            self.assertEqual((c[fn]["rounds"], c[fn]["rounds_max"], c[fn]["adaptive"]), (16, 16, False))
        self.assertEqual(c["17-tracing.json"]["collector"]["metrics_port"], 8888)
        az = c["13-ext-authz.json"]
        self.assertEqual([x["name"] for x in az["shapes"]], ["s", "fh6"])
        self.assertEqual(az["shapes"][1]["rps"], 6000)
        self.assertIn("authz-off-A2", [a["name"] for a in az["arms"]])
        w = c["18w-access-log-w16.json"]
        self.assertEqual((w["envoy"]["workers"], w["cpus"]["sut"]), (16, "0-15"))
        sh = w["shapes"][0]
        self.assertEqual((sh["lead_in_s"], sh["rps"] % 16), (3, 0))
        self.assertIn("--rate-limiter-plugin-config", sh["client_extra_args"])
        # every smoke arm of the session, every non-reference arm smoked
        smoked = {a["name"] for fn, cc in F.configs({}).items() if fn.startswith("smoke") for a in cc["arms"]}
        for fn, cc in c.items():
            for a in cc["arms"]:
                if a["name"] != cc["base_arm"] and not a["name"].endswith("-A2"):
                    self.assertIn(a["name"], smoked)

    def test_evidence_specs_validate_and_hold_on_a_good_leg(self):
        c = F.run_configs({})
        good = {"responses_raw": 104000, "access_log_lines": 156100, "access_log_bytes_per_line": 140.0,
                "access_log_json_ok": True, "tcmalloc_percpu_slab_bytes": 0,
                "sut_stats_window": {"http.ingress_http.ext_authz.ok": 104000, "http.ingress_http.ext_authz.denied": 0,
                                     "http.ingress_http.ext_authz.error": 0,
                                     "http.ingress_http.ext_authz.failure_mode_allowed": 0,
                                     "cluster.ext_authz.upstream_rq_timeout": 0,
                                     "cluster.ext_authz.upstream_rq_total": 104000,
                                     "cluster.ext_authz.upstream_cx_total": 0,
                                     "cluster.origin.upstream_rq_retry": 0,
                                     "http.ingress_http.tracing.random_sampling": 1040,
                                     "cluster.otel_collector.upstream_rq_timeout": 0,
                                     "cluster.otel_collector.upstream_cx_connect_fail": 0},
                "sut_stats_leg_end": {"http.ingress_http.downstream_rq_completed": 156000,
                                      "http.ingress_http.downstream_cx_idle_timeout": 0,
                                      "http.ingress_http.downstream_rq_idle_timeout": 0,
                                      "filesystem.write_failed": 0, "filesystem.reopen_failed": 0,
                                      "http.ingress_http.tracing.random_sampling": 1560,
                                      "tracing.opentelemetry.spans_sent": 1550},
                "collector_delta": {"accepted_spans": 1550, "refused_spans": 0}}
        dump_idle = {"configs": [{"stream_idle_timeout": "0s", "common_http_protocol_options": {"idle_timeout": "0s"}}]}
        dump_retry = {"configs": [{"retry_policy": {"num_retries": 2}}]}
        for fn, cc in c.items():
            for a in cc["arms"]:
                self.assertEqual(evidence.validate_items(a["evidence"], [x["name"] for x in cc["arms"]]), [], fn)
                m = json.loads(json.dumps(good))
                dump = {"configs": []}
                n = a["name"]
                if n == "idle-off":
                    dump = dump_idle
                elif n == "retry-on":
                    dump = dump_retry
                elif n == "percpu-on":
                    m["tcmalloc_percpu_slab_bytes"] = 2600000
                if n in ("log-off", "log-off-A2") or not n.startswith("log"):
                    for k in ("access_log_lines", "access_log_bytes_per_line", "access_log_json_ok"):
                        m.pop(k)
                if n in ("authz-off", "authz-off-A2") or not n.startswith("authz"):
                    for k in list(m["sut_stats_window"]):
                        if "ext_authz" in k:
                            m["sut_stats_window"].pop(k)
                if n == "trace-off":
                    m["sut_stats_leg_end"].pop("tracing.opentelemetry.spans_sent")
                    m["sut_stats_window"]["http.ingress_http.tracing.random_sampling"] = 0
                if n == "trace-10":
                    m["sut_stats_window"]["http.ingress_http.tracing.random_sampling"] = 10400
                    m["sut_stats_leg_end"]["http.ingress_http.tracing.random_sampling"] = 15600
                    m["sut_stats_leg_end"]["tracing.opentelemetry.spans_sent"] = 15580
                    m["collector_delta"]["accepted_spans"] = 15580
                if n == "trace-100":
                    m["sut_stats_window"]["http.ingress_http.tracing.random_sampling"] = 104050
                    m["sut_stats_leg_end"]["http.ingress_http.tracing.random_sampling"] = 156000
                    m["sut_stats_leg_end"]["tracing.opentelemetry.spans_sent"] = 155990
                    m["collector_delta"]["accepted_spans"] = 155990
                ev = evidence.evaluate(m, a["evidence"], dump)
                self.assertTrue(ev["ok"], "%s %s: %s" % (fn, n, ev["failed"]))

    def test_budget_and_floor_helpers(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "smoke-a"))
        with open(os.path.join(d, "smoke-a", "legs.jsonl"), "w") as f:
            for i in range(5):
                f.write(json.dumps({"leg_id": "x%d" % i, "started_utc": "2026-11-17T10:00:%02dZ" % (i * 10)}) + "\n")
            f.write(json.dumps({"supersede": ["x1"]}) + "\n")
        self.assertEqual(F.seconds_per_leg(d), (10.0, 4))
        mand, caps = F.budget(d, out=io.StringIO())
        self.assertEqual(caps["run-s"], 3000.0)
        self.assertEqual(mand, (300 + 180 + 128 + 128) * 10.0)
        self.assertEqual(caps["18w-access-log-w16"], 1280.0)
        self.assertFalse(F.has_floor(d)[0])
        os.makedirs(os.path.join(d, "run-s"))
        with open(os.path.join(d, "run-s", "results.json"), "w") as f:
            json.dump({"metadata": {"incomplete": True, "rounds_complete": 10}}, f)
        self.assertFalse(F.has_floor(os.path.join(d, "run-s"))[0])
        with open(os.path.join(d, "run-s", "results.json"), "w") as f:
            json.dump({"metadata": {"incomplete": False, "rounds_complete": 30}}, f)
        self.assertTrue(F.has_floor(os.path.join(d, "run-s"))[0])


class FeaturesTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.session = os.path.join(cls.tmp, "wk5")
        # run S and row 18 only, simulated, with known effects
        for fn, factors in (("run-s.json", {"retry-on": 1.015, "percpu-on": 0.99}),
                            ("18-access-log.json", {"log-text": 1.04, "log-json": 1.05})):
            with open(os.path.join(FEAT, fn)) as f:
                c = json.load(f)
            for a in c["arms"]:
                a["sim_factor"] = factors.get(a["name"], 1.0)
            c.pop("floor_from", None)
            c.pop("floor_arm", None)
            c["sim_cycles_noise"] = 0.004
            p = os.path.join(cls.tmp, fn)
            with open(p, "w") as f:
                json.dump(c, f)
            exp = experiment.load(p)
            experiment.Runner(exp, os.path.join(cls.session, fn[:-5]), SimBackend).run(simulate=True)
        cls.text, cls.js = FT.tables(FT.load_session(cls.session), os.path.join(HERE, "data"))

    def test_session_wide_holm_family(self):
        fam = self.js["families"]["confirmatory"]
        self.assertEqual(fam["size"], 16)
        self.assertEqual(fam["with_data"], 8)
        self.assertIn("Holm over 16 rows, 8 with data", self.text)
        rows = {(r["run"], r["shape"], r["arm"]): r for r in fam["rows"]}
        # rows of runs that did not run count as p = 1 and get no verdict
        self.assertEqual(rows[("17-tracing", "s", "trace-1")]["holm_p"], 1.0)
        self.assertTrue(rows[("17-tracing", "s", "trace-1")]["verdict"].startswith("no data"))
        # Holm over 16 against Holm over the 8 present: never smaller
        ps = [r["t_p"] for r in fam["rows"] if r.get("t_p") is not None]
        from epl import stats
        h8 = dict(zip(ps, stats.holm(ps)))
        for r in fam["rows"]:
            if r.get("t_p") is not None:
                self.assertGreaterEqual(r["holm_p"], h8[r["t_p"]] - 1e-12)
        self.assertTrue(rows[("18-access-log", "s", "log-json")]["verdict"].startswith("differs"))
        self.assertEqual(self.js["families"]["secondary"]["size"], 7)

    def test_replication_against_data(self):
        reps = {(r["row"][0], r["row"][1], r["row"][2], r["old"]["name"]): r for r in self.js["replication"]}
        r = reps[("18-access-log", "s", "log-json", "row 5")]
        self.assertIsNotNone(r["z"])
        self.assertIn("first, row 5", r["wording"])
        # the simulated +5% against the published +4.5%: replicated
        self.assertTrue(r["replicated"], r)
        r = reps[("run-s", "fh", "percpu-on", "row 9")]  # simulated -1% against the published +1.58%
        self.assertFalse(r["same_sign"])
        self.assertFalse(r["replicated"])
        self.assertIn("held for review", r["wording"])

    def test_rules(self):
        new = {"log_mean": 0.4, "se": 0.1, "effect_pct": 0.4, "verdict": "within the A/A spread (< 1%)"}
        old = {"log_mean": 1.49, "se": 0.3, "effect_pct": 1.5, "name": "row 7"}
        r = FT.replication(new, old)
        self.assertLessEqual(abs(r["z"]), 2.0)
        self.assertFalse(r["replicated"])  # a vanished effect is not a replication (review S7)
        new.update(log_mean=1.6, effect_pct=1.6, verdict="differs: about +1.6%, near the floor")
        self.assertTrue(FT.replication(new, old)["replicated"])
        new.update(log_mean=-1.6, effect_pct=-1.6)
        self.assertFalse(FT.replication(new, old)["replicated"])
        self.assertEqual(FT.closing({"verdict": "within the A/A spread (< 1%)", "widened_hi_pct": 1.4}, {"ok": True}),
                         "no measurable cost (widened upper end +1.40%)")
        self.assertEqual(FT.closing({"verdict": "within the A/A spread (< 1%)", "widened_hi_pct": 1.62}, {"ok": True}),
                         "not resolved; at most +1.6%")
        self.assertEqual(FT.closing({"incomplete": True, "verdict": "x"}), "open (no verdict)")
        self.assertEqual(FT.verdict({"incomplete": True, "log_mean": 5.0}), experiment.INCOMPLETE)
        rows = [{"t_p": 0.01}, {"t_p": None}, {"t_p": 0.04}]
        self.assertEqual(FT.holm(rows), 3)
        self.assertAlmostEqual(rows[0]["holm_p"], 0.03)
        self.assertAlmostEqual(rows[2]["holm_p"], 0.08)
        self.assertEqual(rows[1]["holm_p"], 1.0)

    def test_aa_and_absolute_tables(self):
        self.assertIn("## A/A of the session", self.text)
        self.assertIn("run-s / s | base-A2 vs base (run-s)", self.text)
        self.assertIn("cycles:u effect", self.text)
        self.assertIn("R17 access log JSON", self.text)


if __name__ == "__main__":
    unittest.main()
