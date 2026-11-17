import json
import os
import subprocess
import sys
import tempfile
import unittest

from epl import evidence, experiment, origin
from epl.sim import SimBackend

from .test_evidence import leg
from .test_features import F, FT, FEAT

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HERE, "examples", "settings-matrix", "run-session-1.sh")


class EvidenceCheckMissingArmTest(unittest.TestCase):
    """B1: an arm of the spec with no leg fails the check, reference arms included."""

    def test_missing_arm_fails(self):
        d = tempfile.mkdtemp()
        run = os.path.join(d, "smoke")
        os.makedirs(run)
        with open(os.path.join(run, "legs.jsonl"), "w") as f:
            f.write(json.dumps(leg(leg_id="r01-s-x", arm="x", verdict={"valid": True})) + "\n")
        spec = os.path.join(d, "spec.json")
        with open(spec, "w") as f:
            json.dump({"evidence": {"x": [{"stat": "http.ingress_http.ext_authz.ok", "per_request": 1.0, "tol": 0.002}],
                                    "ref": [{"stat": "http.ingress_http.ext_authz.ok", "absent": True}]}}, f)
        r = subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "evidence-check", spec, run],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no leg in these runs: ref", r.stdout)
        with open(spec, "w") as f:
            json.dump({"evidence": {"x": [{"stat": "http.ingress_http.ext_authz.ok", "per_request": 1.0, "tol": 0.002}]}},
                      f)
        r = subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "evidence-check", spec, run],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_smokes_cover_every_arm(self):
        cfgs = F.configs({})
        smoked = {a["name"] for fn, c in cfgs.items() if fn.startswith("smoke") for a in c["arms"]}
        for fn, c in cfgs.items():
            if fn.startswith("smoke"):
                continue
            for a in c["arms"]:
                self.assertIn(a["name"], smoked, "%s: %s has no smoke" % (fn, a["name"]))
        with open(SCRIPT) as f:
            txt = f.read()
        for fn in cfgs:
            if fn.startswith("smoke"):
                self.assertIn(fn[:-5], txt, "run-session-1.sh does not run " + fn)


class SnapshotMissingTest(unittest.TestCase):
    """S6: absent (and every other window/leg item) fails when the snapshot was never taken."""

    def test_absent_needs_a_snapshot(self):
        it = {"stat": "tracing.opentelemetry.timer_flushed", "scope": "leg", "absent": True}
        self.assertTrue(evidence.check_item(leg(), it)["ok"])
        m = leg()
        m.pop("sut_stats_leg_end")
        m["leg_end_snapshot_error"] = "admin /stats returned 503"
        r = evidence.check_item(m, it)
        self.assertFalse(r["ok"])
        self.assertIn("no leg snapshot", r["why"])
        m = leg(sut_stats_window={})
        self.assertFalse(evidence.check_item(m, {"stat": "x", "absent": True})["ok"])
        # field items do not need a snapshot
        self.assertTrue(evidence.check_item(m, {"stat": "nope", "scope": "field", "absent": True})["ok"])

    def test_validate_rejects_empty_and_mixed(self):
        self.assertTrue(evidence.validate_items([]))
        self.assertTrue(any("equals cannot" in e for e in evidence.validate_items(
            [{"stat": "a", "equals": 0, "tol_abs": 0, "max": 3}])))


class ScrapeTest(unittest.TestCase):
    def test_scrape_bad_status_line_is_an_error_not_an_exception(self):
        import socket
        import threading
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def serve():
            c, _ = srv.accept()
            c.recv(1024)
            c.sendall(b"garbage\r\n\r\n")
            c.close()
        t = threading.Thread(target=serve, daemon=True)
        t.start()
        col = origin.Collector({"port": 4317, "image": "x", "metrics_port": port}, "0", tempfile.mkdtemp(), print)
        r = col.scrape()
        t.join(5)
        srv.close()
        self.assertIn("error", r)


class QueueGateTest(unittest.TestCase):
    """S1: FORCE=1 overrides only the budget question, never a failed evidence check."""

    def test_force_does_not_override_evidence(self):
        with open(SCRIPT) as f:
            txt = f.read()
        self.assertIn('if [ "$rc" -eq 3 ] && [ "${FORCE:-0}" = 1 ]; then', txt)
        self.assertIn("timeout --foreground --signal=TERM", txt)
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "smoke"))
        r = subprocess.run(["bash", SCRIPT, "queue"], env=dict(os.environ, RUNS=d, FORCE="1"),
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 1)
        self.assertIn("queue not started", r.stdout)
        self.assertNotIn("start run-s", r.stdout)


class Stopper(SimBackend):
    at = None

    def run_leg(self, arm, shape, rnd, bootstrap_path, leg_id):
        self.n = getattr(self, "n", 0) + 1
        if self.n == self.at:
            raise SystemExit("terminated by signal 15")
        return SimBackend.run_leg(self, arm, shape, rnd, bootstrap_path, leg_id)


class StoppedRunFloorTest(unittest.TestCase):
    """S3: a run stopped after its minimum but before its stop rule is incomplete: no floor."""

    def test_stopped_run_s_is_no_floor(self):
        with open(os.path.join(FEAT, "run-s.json")) as f:
            c = json.load(f)
        c["sim_cycles_noise"] = 0.05  # the 0.8% target is not reached at 20 rounds
        d = tempfile.mkdtemp()
        p = os.path.join(d, "c.json")
        with open(p, "w") as f:
            json.dump(c, f)
        exp = experiment.load(p)
        Stopper.at = 2 * 5 * 24  # inside the block 21..30
        with self.assertRaises(RuntimeError):
            experiment.Runner(exp, os.path.join(d, "run-s"), Stopper).run(simulate=True)
        with open(os.path.join(d, "run-s", "results.json")) as f:
            md = json.load(f)["metadata"]
        self.assertEqual(md["rounds_complete"], 20)
        self.assertTrue(md["incomplete"])
        ok, why = F.has_floor(os.path.join(d, "run-s"))
        self.assertFalse(ok)
        self.assertIn("SystemExit", why)


class TableRulesTest(unittest.TestCase):
    """S4, S5 and N4 in features_table."""

    def test_no_measurable_cost_needs_a_valid_aa(self):
        r = {"verdict": "within the A/A spread (< 1%)", "widened_hi_pct": 1.2}
        self.assertTrue(FT.closing(r, {"ok": True}).startswith("no measurable cost"))
        for aa in (None, {"ok": None}, {"ok": False, "reach": 1.8}):
            self.assertEqual(FT.closing(r, aa), "not resolved; at most +1.2%")
        v = FT.verdict({"log_mean": 0.3, "lo": -0.4, "hi": 1.0, "widened": 0.8, "effect_pct": 0.3, "holm_p": 1.0},
                       {"ok": None, "why": "run not found"})
        self.assertIn("WARNING: no A/A", v)

    def test_incomplete_run_stays_out_of_holm(self):
        d = tempfile.mkdtemp()
        sess = os.path.join(d, "wk5")
        with open(os.path.join(FEAT, "18-access-log.json")) as f:
            c = json.load(f)
        for a in c["arms"]:
            a["sim_factor"] = {"log-text": 1.04, "log-json": 1.05}.get(a["name"], 1.0)
        c.pop("floor_from")
        c.pop("floor_arm")
        c["sim_cycles_noise"] = 0.004
        p = os.path.join(d, "c.json")
        with open(p, "w") as f:
            json.dump(c, f)
        Stopper.at = 2 * 3 * 20  # stopped in round 20, after the minimum 18
        with self.assertRaises(RuntimeError):
            experiment.Runner(experiment.load(p), os.path.join(sess, "18-access-log"), Stopper).run(simulate=True)
        text, js = FT.tables(FT.load_session(sess), os.path.join(HERE, "data"))
        rows = [r for r in js["families"]["confirmatory"]["rows"] if r["run"] == "18-access-log"]
        self.assertEqual(len(rows), 4)
        for r in rows:
            self.assertIsNone(r["t_p"])
            self.assertEqual(r["holm_p"], 1.0)
            self.assertEqual(r["verdict"], experiment.INCOMPLETE)
            self.assertIsNotNone(r["t_p_incomplete"])
        self.assertIn("Rows of incomplete runs", text)

    def test_evidence_summary_counts_invalid_legs(self):
        res = {"legs": [{"leg_id": "a", "shape": "s", "arm": "x", "round": 1, "verdict": {"valid": True},
                         "evidence": {"ok": True}},
                        {"leg_id": "b", "shape": "s", "arm": "x", "round": 2, "verdict": {"valid": False},
                         "evidence": {"ok": False}},
                        {"leg_id": "c", "shape": "s", "arm": "x", "round": 3, "superseded": True,
                         "verdict": {"valid": False}, "evidence": {"ok": False}}]}
        self.assertEqual(FT.evidence_summary(res)["s/x"]["legs"], 2)
        self.assertEqual(FT.evidence_summary(res)["s/x"]["evidence_ok"], 1)

    def test_row_13_has_no_run_s_floor(self):
        c = F.run_configs({})["13-ext-authz.json"]
        self.assertNotIn("floor_from", c)
        self.assertNotIn("floor_arm", c)


if __name__ == "__main__":
    unittest.main()
