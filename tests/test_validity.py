import unittest

import os
import tempfile

from epl import sysprobe, validity


def good():
    return {"idle_ok": True, "preflight_ok": True, "pinning_ok": True, "perf_ok": True, "responses": 40000,
            "target_rps": 2000, "sut_rate_2xx": 2001.0, "client_overflow": {}, "client_non2xx": {},
            "sut_non2xx": 0, "client_headroom": 0.6, "client_workers": 16, "client_pending_total": 16,
            "sut_foreign_cpus": 0.01, "sut_sibling_cpus": 0.0, "envoy_exit": 0, "perf_min_running_pct": 100.0,
            "envoy_workers": 4, "envoy_worker_max_share": 0.257, "envoy_worker_min_share": 0.243}


class ValidityTest(unittest.TestCase):
    def check(self, mut, needle):
        m = good()
        mut(m)
        v = validity.verdict(m)
        self.assertFalse(v["valid"], needle)
        self.assertTrue(any(needle in r for r in v["reasons"]), v["reasons"])

    def test_good_leg_is_valid(self):
        self.assertTrue(validity.verdict(good())["valid"])

    def test_rate_within_one_percent(self):
        m = good()
        m["sut_rate_2xx"] = 2019.0
        self.assertTrue(validity.verdict(m)["valid"])
        self.check(lambda m: m.update(sut_rate_2xx=1975.0), "misses target")
        self.check(lambda m: m.update(sut_rate_2xx=2025.0), "misses target")

    def test_overflow(self):
        self.check(lambda m: m.update(client_overflow={"benchmark.pool_overflow": 1}), "overflow")

    def test_headroom(self):
        self.check(lambda m: m.update(client_headroom=0.1), "headroom")
        self.check(lambda m: m.update(client_headroom=None), "headroom")

    def test_port_preflight(self):
        self.check(lambda m: m.update(preflight_ok=False, preflight_detail="port 10110 already in use"),
                   "preflight")

    def test_idle(self):
        self.check(lambda m: m.update(idle_ok=False), "not idle")

    def test_non2xx(self):
        self.check(lambda m: m.update(client_non2xx={"benchmark.http_5xx": 1}), "non-2xx")
        self.check(lambda m: m.update(sut_non2xx=1), "non-2xx")

    def test_misc(self):
        self.check(lambda m: m.update(perf_ok=False), "perf")
        self.check(lambda m: m.update(error="boom"), "error")
        self.check(lambda m: m.update(pinning_ok=False), "CPUs")
        self.check(lambda m: m.update(responses=0), "zero")

    def test_pending_total(self):
        self.check(lambda m: m.update(client_pending_total=17), "pending total")
        m = good()
        m["client_pending_total"] = 12
        self.assertTrue(validity.verdict(m)["valid"])

    def test_during_window_idle(self):
        self.check(lambda m: m.update(sut_foreign_cpus=0.2), "other tasks")
        self.check(lambda m: m.update(sut_sibling_cpus=0.3), "SMT siblings")

    def test_during_window_probe_fails_closed(self):
        self.check(lambda m: m.pop("sut_foreign_cpus"), "no scheduler run time")
        self.check(lambda m: m.update(sut_sibling_cpus=None, sched_probe="cannot read"), "cannot read")
        self.check(lambda m: m.update(sut_foreign_cpus=-0.05), "probe inconsistent")
        m = good()
        m["sut_foreign_cpus"] = -0.0001  # snapshot skew
        self.assertTrue(validity.verdict(m)["valid"])
        m = good()
        del m["sut_foreign_cpus"]
        self.assertTrue(validity.verdict(m, {"max_sut_foreign_cpus": None, "max_sut_sibling_cpus": None})["valid"])

    def test_worker_share(self):
        m = good()
        m.update(envoy_worker_max_share=0.29, envoy_worker_min_share=0.22)
        self.assertTrue(validity.verdict(m)["valid"])
        self.check(lambda m: m.update(envoy_worker_max_share=0.6), "busiest worker")
        # three of four workers busy: 0.354 passed the old 1.5x gate
        self.check(lambda m: m.update(envoy_worker_max_share=0.354, envoy_worker_min_share=0.06), "busiest worker")
        self.check(lambda m: m.update(envoy_worker_max_share=0.31), "busiest worker")
        self.check(lambda m: m.update(envoy_worker_min_share=0.1), "least busy worker")

    def test_worker_share_fails_closed(self):
        self.check(lambda m: m.update(envoy_worker_max_share=None, envoy_worker_probe="no wrk: thread"),
                   "no wrk: thread")
        self.check(lambda m: m.pop("envoy_workers"), "no Envoy worker CPU")
        m = good()
        del m["envoy_worker_max_share"]
        self.assertTrue(validity.verdict(m, {"max_worker_share_factor": None,
                                             "min_worker_share_factor": None})["valid"])

    def test_overflow_ignore(self):
        m = good()
        m["client_overflow"] = {"upstream_cx_overflow": 500}
        self.assertFalse(validity.verdict(m)["valid"])
        self.assertTrue(validity.verdict(m, {"overflow_ignore": ["upstream_cx_overflow"]})["valid"])
        m["client_overflow"]["benchmark.pool_overflow"] = 1
        self.assertFalse(validity.verdict(m, {"overflow_ignore": ["upstream_cx_overflow"]})["valid"])

    def test_cpuidle_change_invalidates(self):
        m = good()
        m["cpuidle_unchanged"] = True
        self.assertTrue(validity.verdict(m)["valid"])
        self.check(lambda m: m.update(cpuidle_unchanged=False), "idle-state configuration")

    def test_cpuset_text(self):
        self.assertEqual(sysprobe._cpuset_text([0, 1, 2, 5, 40, 41]), "0-2,5,40-41")
        self.assertEqual(sysprobe._cpuset_text([]), "")

    def test_exit_and_multiplexing(self):
        self.check(lambda m: m.update(envoy_exit=-9), "exit code")
        self.check(lambda m: m.update(perf_min_running_pct=50.0), "multiplexed")
        m = good()
        m["eff_ghz"] = 1.5
        self.assertTrue(validity.verdict(m)["valid"])
        self.assertFalse(validity.verdict(m, {"min_eff_ghz": 2.0})["valid"])

    def test_latency_gate_is_separate(self):
        m = good()
        m["latency_us"] = {"max": 25000.0}
        self.assertTrue(validity.verdict(m, {"max_latency_ms": 10})["valid"])
        self.assertFalse(validity.latency_ok(m, {"max_latency_ms": 10}))
        self.assertTrue(validity.latency_ok(m))


class SchedstatTest(unittest.TestCase):
    def read(self, text):
        fd, p = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(text)
        try:
            return sysprobe.cpu_run_ns(p)
        finally:
            os.unlink(p)

    def test_version_15(self):
        out, why = self.read("version 15\ntimestamp 1\ncpu0 0 0 10 2 5 3 777 9 4\ndomain0 ff 1 2\n"
                             "cpu1 0 0 10 2 5 3 888 9 4\n")
        self.assertIsNone(why)
        self.assertEqual(out, {0: 777, 1: 888})

    def test_unknown_version_fails_closed(self):
        out, why = self.read("version 14\ncpu0 0 0 10 2 5 3 777 9 4\n")
        self.assertIsNone(out)
        self.assertIn("version 14", why)
        out, why = self.read("cpu0 0 0 10 2 5 3 777 9 4\n")
        self.assertIsNone(out)

    def test_unreadable_fails_closed(self):
        out, why = sysprobe.cpu_run_ns("/nonexistent/schedstat")
        self.assertIsNone(out)
        self.assertIn("cannot read", why)


if __name__ == "__main__":
    unittest.main()
