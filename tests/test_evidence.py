import gzip
import json
import os
import subprocess
import sys
import tempfile
import unittest

from epl import evidence, validity

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leg(**over):
    m = {"leg_id": "r01-s-x", "arm": "x", "shape": "s", "round": 1, "responses_raw": 104000,
         "sut_stats_window": {"http.ingress_http.ext_authz.ok": 104050, "http.ingress_http.ext_authz.denied": 0,
                              "cluster.ext_authz.upstream_cx_total": 0,
                              "http.ingress_http.tracing.random_sampling": 1040},
         "sut_stats_leg_end": {"http.ingress_http.downstream_rq_completed": 156000,
                               "tracing.opentelemetry.spans_sent": 1530},
         "access_log_lines": 156100, "tcmalloc_percpu_slab_bytes": 2600000,
         "collector_delta": {"accepted_spans": 1530, "refused_spans": 0}}
    m.update(over)
    return m


def good():
    return {"idle_ok": True, "preflight_ok": True, "pinning_ok": True, "perf_ok": True, "responses": 40000,
            "target_rps": 2000, "sut_rate_2xx": 2001.0, "client_overflow": {}, "client_non2xx": {},
            "sut_non2xx": 0, "client_headroom": 0.6, "client_workers": 16, "client_pending_total": 16,
            "sut_foreign_cpus": 0.01, "sut_sibling_cpus": 0.0, "envoy_exit": 0, "perf_min_running_pct": 100.0,
            "envoy_workers": 4, "envoy_worker_max_share": 0.257, "envoy_worker_min_share": 0.243}


class EvidenceItemTest(unittest.TestCase):
    def one(self, it, m=None, dump=None):
        return evidence.check_item(m or leg(), it, dump)

    def test_per_request_tolerance(self):
        it = {"stat": "http.ingress_http.ext_authz.ok", "per_request": 1.0, "tol": 0.002}
        self.assertTrue(self.one(it)["ok"])  # 104050 / 104000 = 1.00048
        m = leg()
        m["sut_stats_window"]["http.ingress_http.ext_authz.ok"] = 104300  # +0.29%
        r = self.one(it, m)
        self.assertFalse(r["ok"])
        self.assertIn("expected 1", r["why"])

    def test_zero_count_and_absent(self):
        self.assertTrue(self.one({"stat": "http.ingress_http.ext_authz.denied", "equals": 0, "tol_abs": 0})["ok"])
        m = leg()
        m["sut_stats_window"]["http.ingress_http.ext_authz.denied"] = 1
        self.assertFalse(self.one({"stat": "http.ingress_http.ext_authz.denied", "equals": 0, "tol_abs": 0}, m)["ok"])
        # a counter that does not exist is not "zero": missing fails, absent passes
        self.assertFalse(self.one({"stat": "nope", "equals": 0, "tol_abs": 0})["ok"])
        self.assertTrue(self.one({"stat": "nope", "absent": True})["ok"])
        self.assertFalse(self.one({"stat": "http.ingress_http.ext_authz.ok", "absent": True})["ok"])

    def test_leg_scope_default_denominator_and_field(self):
        it = {"stat": "access_log_lines", "scope": "field", "per_request": 1.0, "tol": 0.002,
              "per": "leg:http.ingress_http.downstream_rq_completed"}
        self.assertTrue(self.one(it)["ok"])
        self.assertFalse(self.one(it, leg(access_log_lines=155000))["ok"])
        # leg scope divides by the end-of-leg completed requests by default
        it = {"stat": "tracing.opentelemetry.spans_sent", "scope": "leg", "per_request": 0.01, "tol": 0.05}
        self.assertTrue(self.one(it)["ok"])  # 1530 / 156000 = 0.0098
        it = {"stat": "collector_delta.accepted_spans", "scope": "field", "min": 1450}
        self.assertTrue(self.one(it)["ok"])
        self.assertFalse(self.one({"stat": "tcmalloc_percpu_slab_bytes", "scope": "field", "equals": 0,
                                   "tol_abs": 0})["ok"])

    def test_ratio_of_two_counters(self):
        it = {"stat": "tracing.opentelemetry.spans_sent", "scope": "leg", "per_request": 1.0, "tol": 0.05,
              "per": "leg:http.ingress_http.tracing.random_sampling"}
        m = leg()
        m["sut_stats_leg_end"]["http.ingress_http.tracing.random_sampling"] = 1560
        self.assertTrue(self.one(it, m)["ok"])  # 0.981
        m["sut_stats_leg_end"]["http.ingress_http.tracing.random_sampling"] = 1700
        self.assertFalse(self.one(it, m)["ok"])  # 0.90
        m["sut_stats_leg_end"].pop("http.ingress_http.tracing.random_sampling")
        self.assertIn("denominator", self.one(it, m)["why"])

    def test_binomial(self):
        # 1% of 104000 = 1040, sd = sqrt(.01*.99/104000) = 0.000309; 4 sd = 0.00123
        it = {"stat": "http.ingress_http.tracing.random_sampling", "per_request": 0.01, "tol_binomial_sd": 4}
        self.assertTrue(self.one(it)["ok"])
        m = leg()
        m["sut_stats_window"]["http.ingress_http.tracing.random_sampling"] = 1200  # 0.01154: 5 sd
        self.assertFalse(self.one(it, m)["ok"])
        # 100%: sd is 0, so the relative tolerance carries it
        m["sut_stats_window"]["http.ingress_http.tracing.random_sampling"] = 104100
        it = {"stat": "http.ingress_http.tracing.random_sampling", "per_request": 1.0, "tol_binomial_sd": 4,
              "tol": 0.002}
        self.assertTrue(self.one(it, m)["ok"])

    def test_config_scope(self):
        dump = {"configs": [{"dynamic": [], "static_listeners": [{"listener": {"filter_chains": [{"filters": [
            {"typed_config": {"stream_idle_timeout": "0s",
                              "common_http_protocol_options": {"idle_timeout": "0s"}}}]}]}}]}]}
        self.assertTrue(self.one({"stat": "stream_idle_timeout", "scope": "config", "equals": "0s"}, dump=dump)["ok"])
        self.assertTrue(self.one({"stat": "idle_timeout", "scope": "config", "equals": "0s"}, dump=dump)["ok"])
        self.assertTrue(self.one({"stat": "retry_policy", "scope": "config", "absent": True}, dump=dump)["ok"])
        self.assertFalse(self.one({"stat": "retry_policy", "scope": "config", "present": True}, dump=dump)["ok"])
        dump["configs"][0]["x"] = {"idle_timeout": "3600s"}
        self.assertFalse(self.one({"stat": "idle_timeout", "scope": "config", "equals": "0s"}, dump=dump)["ok"])
        self.assertIn("no /config_dump", self.one({"stat": "x", "scope": "config", "present": True})["why"])

    def test_unfrozen_ref_fails_closed(self):
        r = self.one({"stat": "http.ingress_http.ext_authz.ok", "ref": {"arm": "self"}, "tol_abs": 3})
        self.assertFalse(r["ok"])
        self.assertIn("not frozen", r["why"])

    def test_validate_items(self):
        e = evidence.validate_items([{"stat": "a", "per_request": 1.0}])
        self.assertTrue(any("tolerance" in x for x in e), e)
        e = evidence.validate_items([{"stat": "a", "equals": 0}])
        self.assertTrue(any("tolerance" in x for x in e), e)
        self.assertEqual(evidence.validate_items([{"stat": "a", "equals": 0, "tol_abs": 0},
                                                  {"stat": "b", "absent": True}, {"stat": "c", "min": 1},
                                                  {"stat": "d", "scope": "config", "equals": "0s"}]), [])
        self.assertTrue(evidence.validate_items([{"stat": "a", "scope": "nope", "min": 1}]))
        self.assertTrue(evidence.validate_items([{"stat": "a", "scope": "config", "min": 1}]))
        self.assertTrue(evidence.validate_items([{"stat": "a", "ref": {"arm": "zz"}, "tol_abs": 3}], ["x", "y"]))
        self.assertTrue(evidence.validate_items([{"stat": "a", "per_request": 1, "tol": 0.1, "per": "bad"}]))

    def test_gate_and_record(self):
        items = [{"stat": "http.ingress_http.ext_authz.ok", "per_request": 1.0, "tol": 0.002},
                 {"stat": "missing.counter", "equals": 0, "tol_abs": 0}]
        m = dict(good(), **leg())
        m["evidence"] = evidence.evaluate(m, items)
        v = validity.verdict(m)
        self.assertFalse(v["valid"])
        self.assertTrue(any("evidence: " in r and "missing.counter" in r for r in v["reasons"]), v["reasons"])
        m["evidence"] = evidence.evaluate(m, items, gate=False)
        self.assertTrue(validity.verdict(m)["valid"])
        m["evidence"] = evidence.evaluate(m, items[:1])
        self.assertTrue(validity.verdict(m)["valid"])


class EvidenceCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.run = os.path.join(self.tmp, "smoke")
        os.makedirs(os.path.join(self.run, "config_dump"))
        legs = []
        for r in (1, 2):
            for arm, extra in (("ref", 0), ("hdr", 17)):
                legs.append(leg(leg_id="r%02d-s-%s" % (r, arm), arm=arm, round=r, verdict={"valid": True},
                                sut_stats_window={"cluster.origin.upstream_cx_tx_bytes_total": 104000 * (120 + extra)
                                                  + r * 50}))
        # a superseded leg that would fail, then its re-run
        bad = leg(leg_id="r03-s-hdr", arm="hdr", round=3, verdict={"valid": True},
                  sut_stats_window={"cluster.origin.upstream_cx_tx_bytes_total": 104000 * 120})
        rerun = dict(bad, leg_id="r03-s-hdr.rr1", sut_stats_window={
            "cluster.origin.upstream_cx_tx_bytes_total": 104000 * 137})
        with open(os.path.join(self.run, "legs.jsonl"), "w") as f:
            for m in legs + [bad]:
                f.write(json.dumps(m) + "\n")
            f.write(json.dumps({"supersede": ["r03-s-hdr"]}) + "\n")
            f.write(json.dumps(rerun) + "\n")
        with gzip.open(os.path.join(self.run, "config_dump", "hdr.json.gz"), "wt") as f:
            json.dump({"configs": [{"retry_policy": {"num_retries": 2}}]}, f)
        self.spec = os.path.join(self.tmp, "spec.json")
        with open(self.spec, "w") as f:
            json.dump({"name": "x", "arms": [
                {"name": "ref", "binary": "/bin/true"},
                {"name": "hdr", "binary": "/bin/true", "evidence": [
                    {"stat": "cluster.origin.upstream_cx_tx_bytes_total", "ref": {"arm": "ref", "offset": 17},
                     "tol_abs": 3},
                    {"stat": "retry_policy", "scope": "config", "present": True}]}]}, f)

    def cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "evidence-check"] + list(args),
                              capture_output=True, text=True, timeout=60)

    def test_load_legs_drops_superseded(self):
        ids = [m["leg_id"] for m in evidence.load_legs(self.run)]
        self.assertNotIn("r03-s-hdr", ids)
        self.assertIn("r03-s-hdr.rr1", ids)

    def test_freeze_and_check(self):
        spec = evidence.load_spec(self.spec)
        frozen, problems = evidence.freeze(spec, evidence.load_legs(self.run))
        self.assertEqual(problems, [])
        it = frozen["hdr"][0]
        self.assertEqual(it["shape"], "s")
        self.assertAlmostEqual(it["per_request"], 137.0 + 75.0 / 104000, places=6)
        rows, problems = evidence.check_run(frozen, self.run)
        self.assertEqual(problems, [])
        self.assertTrue(all(ev["ok"] for _, _, ev in rows), rows)
        self.assertEqual(len(rows), 3)

    def test_cli(self):
        r = self.cli(self.spec, self.run)
        self.assertEqual(r.returncode, 1)  # refs not frozen
        self.assertIn("not frozen", r.stdout)
        out = os.path.join(self.tmp, "frozen.json")
        r = self.cli(self.spec, self.run, "--freeze", out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(out) as f:
            cfg = json.load(f)
        self.assertIn("per_request", cfg["arms"][1]["evidence"][0])
        r = self.cli(out, self.run)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("evidence-check: PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
