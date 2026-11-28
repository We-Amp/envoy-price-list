"""Client-bottleneck checks (epl.clientcheck): the client perf -I record, the per-worker sequencer gates, the
floor per client recipe, the split verdict, their validate checks and the example config."""
import copy
import inspect
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from epl import clientcheck, experiment, leg, validity

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIX = os.path.join(ROOT, "tests", "fixtures")


def iv_lines(n, dt=1.0, tc_ms=500.0, cyc=1e9, pct="100.00", missing=None, extra=""):
    out = []
    for i in range(n):
        t = (i + 1) * dt
        for ev, v in (("task-clock", tc_ms * dt), ("cycles", cyc * dt), ("instructions", 2 * cyc * dt),
                      ("context-switches", 10)):
            if missing and ev == missing:
                out.append("%.6f,<not counted>,,%s,0,0.00,," % (t, ev))
            else:
                out.append("%.6f,%.1f,msec,%s,1000000000,%s,," % (t, v, ev, pct))
    return "\n".join(out) + extra


def load_ex(name, **sets):
    exp = experiment.load(os.path.join(FIX, name + ".json"),
                          experiment.parse_sets(["%s=%s" % (k, json.dumps(v)) for k, v in sets.items()]))
    return exp, experiment.validate(exp, allow_short=True)


class PerfIntervalTest(unittest.TestCase):
    def test_cmd_has_interval_and_no_timeout(self):
        cmd = clientcheck.client_perf_interval_cmd({"client_perf_interval_ms": 1000}, ["perf"], 42)
        self.assertEqual(cmd, ["perf", "stat", "-x", ",", "-e", clientcheck.CLIENT_PERF_EVENTS, "-p", "42",
                               "-I", "1000"])
        self.assertNotIn("--timeout", cmd)
        cmd = clientcheck.client_perf_interval_cmd({"client_perf_interval_ms": 500, "client_perf_bin": "/p"},
                                                   ["wrapper-perf.sh", "perf"], 7)
        self.assertEqual(cmd[0], "/p")
        self.assertEqual(clientcheck.CLIENT_PERF_EVENTS, leg.CLIENT_PERF_EVENTS)

    def test_record_ok_and_peak(self):
        text = iv_lines(20, tc_ms=500.0)
        # one busier interval: 3,000 ms of task-clock in a 1 s interval = 3 CPUs over 4 workers
        text = text.replace("\n5.000000,500.0,msec,task-clock", "\n5.000000,3000.0,msec,task-clock")
        r = clientcheck.client_perf_interval_record(text, 20, 100000, 4, 1000, rc=0)
        self.assertTrue(r["ok"], r["reasons"])
        self.assertEqual(r["n_intervals"], 20)
        self.assertAlmostEqual(r["peak_interval_cpus_per_worker"], 0.75)
        self.assertAlmostEqual(r["cpus"], (19 * 500 + 3000) / 1000.0 / 20)
        self.assertAlmostEqual(r["cpus_per_worker"], r["cpus"] / 4)
        self.assertAlmostEqual(r["cycles_per_req"], 20e9 / 100000)
        for k in ("raw", "running_pct", "ok", "cpus", "cpus_per_worker", "cycles_per_req", "instructions_per_req",
                  "ghz"):
            self.assertIn(k, r)  # the self-check's keys: above_floor and validity read the same record

    def test_short_last_interval_left_out_of_the_peak(self):
        # a 0.05 s partial interval at 4 CPUs per worker is in the totals but never the peak
        text = iv_lines(20) + "\n20.050000,200.0,msec,task-clock,1,100.00,,\n20.050000,5e7,,cycles,1,100.00,,"
        r = clientcheck.client_perf_interval_record(text, 20, 1000, 1, 1000, rc=0)
        self.assertTrue(r["ok"], r["reasons"])
        self.assertAlmostEqual(r["peak_interval_cpus_per_worker"], 0.5)
        self.assertEqual(r["intervals"][-1]["cpus_per_worker"], 4.0)
        self.assertIn(r["peak_interval_t"], [float(i) for i in range(1, 21)])

    def test_end_interval_perf_on_the_exception_path(self):
        # a perf-like process registered as perf-client, stopped with SIGINT on an abnormal path; the ledger
        # holds its line and the registry is empty after
        tmp = tempfile.mkdtemp()
        py = os.path.join(tmp, "perf.py")
        with open(py, "w") as f:
            f.write("import signal, sys, time\nsignal.signal(signal.SIGINT, lambda *a: sys.exit(0))\n"
                    "while True:\n    time.sleep(0.05)\n")
        own = leg.OwnProcesses(ledger=os.path.join(tmp, "ledger.jsonl"))
        p = own.start([sys.executable, "-I", py], role="perf-client", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      text=True)
        time.sleep(0.3)
        clientcheck.end_interval_perf(own, p, done=False)
        self.assertEqual(p.returncode, 0)  # ended by its SIGINT
        self.assertEqual(own.procs, {})
        with open(os.path.join(tmp, "ledger.jsonl")) as f:
            self.assertEqual([json.loads(x)["role"] for x in f], ["perf-client"])
        # one that ignores the SIGINT is stopped by own.stop after the 10 s wait
        with open(py, "w") as f:
            f.write("import signal, time\nsignal.signal(signal.SIGINT, signal.SIG_IGN)\n"
                    "while True:\n    time.sleep(0.05)\n")
        p = own.start([sys.executable, "-I", py], role="perf-client")
        time.sleep(0.3)
        t = time.monotonic()
        clientcheck.end_interval_perf(own, p, done=False)
        self.assertIsNotNone(p.returncode)
        self.assertGreaterEqual(time.monotonic() - t, 9.5)
        self.assertEqual(own.procs, {})

    def test_record_partial_last_interval_counts(self):
        text = iv_lines(19) + "\n" + "19.400000,200.0,msec,task-clock,1,100.00,,\n19.400000,4e8,,cycles,1,100.00,,"
        r = clientcheck.client_perf_interval_record(text, 20, 1, 1, 1000, rc=0)
        self.assertTrue(r["ok"], r["reasons"])  # 19.4 s covers the window to within one interval
        self.assertAlmostEqual(r["intervals"][-1]["dt_s"], 0.4)

    def test_fail_closed(self):
        cases = [
            ("", "no client perf intervals"),
            (iv_lines(20, pct="98.00"), "multiplexed"),
            (iv_lines(10), "cover 10.000 s of the 20.000 s window"),
            (iv_lines(20, missing="task-clock"), "lacks task-clock"),
        ]
        for text, want in cases:
            r = clientcheck.client_perf_interval_record(text, 20, 1000, 4, 1000, rc=0)
            self.assertFalse(r["ok"], want)
            self.assertTrue(any(want in x for x in r["reasons"]), (want, r["reasons"]))
        r = clientcheck.client_perf_interval_record(iv_lines(20), 20, 1000, 4, 1000, rc=1)
        self.assertIn("client perf exited 1", r["reasons"])
        for rc in (0, -2, 130):
            self.assertTrue(clientcheck.client_perf_interval_record(iv_lines(20), 20, 1000, 4, 1000, rc=rc)["ok"])

    def test_sigint_ends_a_perf_like_process(self):
        # a stand-in that keeps perf -I's contract: lines every interval, the partial one at SIGINT, then exit 0
        tmp = tempfile.mkdtemp()
        py = os.path.join(tmp, "perf.py")
        with open(py, "w") as f:
            f.write("import signal, sys, time\n"
                    "t0 = time.monotonic(); k = [0]\n"
                    "def line(t):\n"
                    "    sys.stderr.write('%.6f,%.1f,msec,task-clock,1,100.00,,\\n%.6f,%.0f,,cycles,1,100.00,,\\n'"
                    " % (t, 100.0 * t, t, 1e8 * t)); sys.stderr.flush()\n"
                    "def stop(*a):\n    line(time.monotonic() - t0); sys.exit(0)\n"
                    "signal.signal(signal.SIGINT, stop)\n"
                    "while True:\n    time.sleep(0.1); line(round(time.monotonic() - t0, 1))\n")
        p = subprocess.Popen([sys.executable, "-I", py], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.55)
        p.send_signal(signal.SIGINT)
        err = p.communicate(timeout=10)[1]
        rows, tot, run = clientcheck.parse_intervals(err)
        self.assertGreaterEqual(len(rows), 4)
        self.assertEqual(p.returncode, 0)

    def test_leg_wiring(self):
        src = inspect.getsource(leg.RealBackend.run_leg)
        i = src.index("clientcheck.client_perf_interval_cmd(mcfg, self.perf, cl.pid)")
        # the -I perf is ours (the registry and the ledger), and its stop is in the finally
        self.assertIn('role="perf-client"', src[i:i + 200])
        f = src.index("finally:", src.index("cperf_done = False"))
        self.assertIn("clientcheck.end_interval_perf(self.own, cperf, cperf_done)", src[f:f + 300])
        j = src.index("pr = subprocess.run(pcmd(envoy.pid)")
        k = src.index("cperf.send_signal(signal.SIGINT)")
        c = src.index("cperf_err = cperf.communicate(")
        self.assertLess(i, j)
        self.assertLess(j, k)  # the SIGINT after the Envoy window ended
        self.assertLess(k, c)
        self.assertIn("clientcheck.client_perf_interval_record(", src)
        self.assertIn("clientcheck.leg_worker_sequencer(nh_json", src)
        # without the key, the plain client perf path is the one that runs (--timeout)
        self.assertIn("client_perf_cmd(mcfg, self.perf, cl.pid, mcfg[\"window_s\"])", src)


def nh_output(workers, blocking=None, callback_us=None, drop=None, phases=False):
    def stats(i):
        out = []
        if drop != ("blocking", i):
            st = {"id": "sequencer.blocking"}
            b = (blocking or {}).get(i, 0)
            if b:
                st["count"] = str(b)
                st["max"] = "0.002s"
            out.append(st)
        if drop != ("callback", i):
            out.append({"id": "sequencer.callback", "count": "100",
                        "max": "%.6fs" % ((callback_us or {}).get(i, 500.0) / 1e6)})
        return out
    res = [{"name": "global", "statistics": [], "counters": []}]
    if workers > 1:
        res += [{"name": "worker_%d" % i, "statistics": stats(i)} for i in range(workers)]
    else:
        res[0]["statistics"] = stats(0)
    if phases:
        res += [{"name": "phase_0_warm", "phase_id": "warm", "statistics": stats(99)},
                {"name": "phase_1_measure", "phase_id": "measure", "statistics": stats(99)}]
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "nh.json")
    with open(p, "w") as f:
        json.dump({"results": res}, f)
    return p


class WorkerSequencerTest(unittest.TestCase):
    def test_per_worker_read(self):
        pw = clientcheck.worker_sequencer(nh_output(4, blocking={2: 3}))
        self.assertEqual(sorted(pw), ["worker_0", "worker_1", "worker_2", "worker_3"])
        self.assertEqual(pw["worker_2"]["blocking_count"], 3)
        self.assertEqual(pw["worker_0"]["blocking_count"], 0)
        # one worker: the global result stands for it; phase results are never workers
        self.assertEqual(sorted(clientcheck.worker_sequencer(nh_output(1))), ["global"])
        self.assertEqual(sorted(clientcheck.worker_sequencer(nh_output(2, phases=True))), ["worker_0", "worker_1"])

    def test_check_names_the_worker(self):
        r = clientcheck.leg_worker_sequencer(nh_output(4, blocking={2: 3}, callback_us={1: 9000.0}), 4,
                                             {"max_client_worker_sequencer_blocking": 0,
                                              "max_client_worker_callback_ms": 5.0})
        self.assertFalse(r["ok"])
        self.assertIn("client worker_2: sequencer blocked 3 times (limit 0 per worker)", r["reasons"])
        self.assertIn("client worker_1: sequencer.callback max 9.000 ms over 5.000 ms", r["reasons"])
        self.assertEqual(r["worst_blocking"], 3)
        ok = clientcheck.leg_worker_sequencer(nh_output(4), 4, {"max_client_worker_sequencer_blocking": 0,
                                                                "max_client_worker_callback_ms": 5.0})
        self.assertTrue(ok["ok"], ok["reasons"])

    def test_sum_gate_cannot_see_what_the_per_worker_gate_sees(self):
        # 2 blocks on one worker: the summed gate at limit 2 passes, the per-worker gate at 1 names worker_3
        p = nh_output(4, blocking={3: 2})
        r = clientcheck.leg_worker_sequencer(p, 4, {"max_client_worker_sequencer_blocking": 1})
        self.assertEqual(r["reasons"], ["client worker_3: sequencer blocked 2 times (limit 1 per worker)"])

    def test_fail_closed(self):
        v = {"max_client_worker_sequencer_blocking": 0, "max_client_worker_callback_ms": 5.0}
        r = clientcheck.leg_worker_sequencer(nh_output(4, drop=("blocking", 1)), 4, v)
        self.assertIn("client worker_1: no sequencer.blocking statistic", r["reasons"])
        r = clientcheck.leg_worker_sequencer(nh_output(4, drop=("callback", 0)), 4, v)
        self.assertIn("client worker_0: no sequencer.callback maximum", r["reasons"])
        r = clientcheck.leg_worker_sequencer(nh_output(3), 4, v)
        self.assertIn("client per-worker sequencer statistics for 3 workers, planned 4", r["reasons"])
        r = clientcheck.leg_worker_sequencer("/nonexistent/nh.json", 4, v)
        self.assertFalse(r["ok"])
        self.assertTrue(r["reasons"][0].startswith("client output unreadable"))


def good_leg(**kw):
    m = {"idle_ok": True, "preflight_ok": True, "target_rps": 100, "sut_rate_2xx": 100.0, "client_headroom": 0.7,
         "perf_ok": True, "responses": 100, "sut_foreign_cpus": 0.0, "sut_sibling_cpus": 0.0,
         "envoy_worker_max_share": 0.25, "envoy_worker_min_share": 0.25, "envoy_workers": 4}
    m.update(kw)
    return m


class ValidityTest(unittest.TestCase):
    def test_off_by_default(self):
        self.assertTrue(validity.verdict(good_leg())["valid"])
        self.assertEqual(set(validity.F1_KEYS), set(clientcheck.VALIDITY_KEYS))
        for k in validity.F1_KEYS:
            self.assertIsNone(validity.DEFAULTS.get(k))

    def test_gates_fail_closed(self):
        c = {"max_client_worker_sequencer_blocking": 0}
        v = validity.verdict(good_leg(), c)
        self.assertIn("no client per-worker sequencer record (gate on)", v["reasons"])
        v = validity.verdict(good_leg(client_worker_sequencer={"ok": False, "reasons": ["client worker_2: x"]}), c)
        self.assertIn("client per-worker sequencer: client worker_2: x", v["reasons"])
        self.assertTrue(validity.verdict(good_leg(client_worker_sequencer={"ok": True}), c)["valid"])
        c = {"max_client_perf_interval_cpus_per_worker": 0.5}
        v = validity.verdict(good_leg(client_perf={"ok": True}), c)
        self.assertIn("no client perf -I record (validity.max_client_perf_interval_cpus_per_worker is set)",
                      v["reasons"])
        v = validity.verdict(good_leg(client_perf={"ok": True, "interval_ms": 1000,
                                                   "peak_interval_cpus_per_worker": 0.8}), c)
        self.assertIn("client perf busiest interval 0.800 CPUs per client worker (limit 0.500)", v["reasons"])
        v = validity.verdict(good_leg(client_perf={"ok": False, "interval_ms": 1000, "reasons": ["x"],
                                                   "peak_interval_cpus_per_worker": 0.1}), c)
        self.assertIn("client perf counters missing or multiplexed", v["reasons"])  # the self-check's gate reads ok


class ConfigTest(unittest.TestCase):
    def test_example_valid(self):
        exp, errs = load_ex("client-checks")
        self.assertEqual(errs, [])
        self.assertEqual([a["name"] for a in experiment.calibration_arms(exp)], ["off"])  # one recipe, one floor
        exp2, errs = load_ex("client-checks")
        self.assertEqual(errs, [])

    def errs(self, **sets):
        return load_ex("client-checks", **sets)[1]

    def test_refusals(self):
        self.assertIn("client_calibration.per_recipe needs a floor gate (validity.max_client_busy_above_floor or "
                      "validity.max_client_perf_cpus_above_floor): a floor no gate reads checks nothing",
                      self.errs(**{"validity.max_client_busy_above_floor": None}))
        self.assertIn("client_calibration.per_recipe takes true", self.errs(**{"client_calibration.per_recipe": 1}))
        for bad in (50, 100, 249, 250.0, True):
            self.assertIn("measure.client_perf_interval_ms must be whole ms >= 250",
                          self.errs(**{"measure.client_perf_interval_ms": bad}), bad)
        self.assertEqual(self.errs(**{"measure.client_perf_interval_ms": 250}), [])
        self.assertEqual(clientcheck.MIN_INTERVAL_MS, 250)
        self.assertIn("measure.client_perf_interval_ms needs measure.client_perf true",
                      self.errs(**{"measure.client_perf": False}))
        self.assertIn("measure.client_perf_interval_ms is longer than the window",
                      self.errs(**{"measure.client_perf_interval_ms": 30000}))
        self.assertIn("validity.max_client_worker_sequencer_blocking must be a whole number >= 0",
                      self.errs(**{"validity.max_client_worker_sequencer_blocking": -1}))
        self.assertIn("validity.max_client_worker_callback_ms must be a number > 0",
                      self.errs(**{"validity.max_client_worker_callback_ms": 0}))
        self.assertIn("validity.max_client_perf_interval_cpus_per_worker needs measure.client_perf_interval_ms",
                      self.errs(**{"measure.client_perf_interval_ms": None}))
        self.assertIn("client_calibration takes shape, rps_per_worker, arm and per_recipe only",
                      self.errs(**{"client_calibration.bogus": 1}))

    def test_old_message_unchanged_without_per_recipe(self):
        exp, _ = load_ex("client-checks")
        exp = copy.deepcopy(exp)
        exp["client_calibration"] = {"shape": "s", "bogus": 1}
        self.assertIn("client_calibration takes shape, rps_per_worker and arm only",
                      experiment.validate(exp, allow_short=True))

    def test_one_floor_per_recipe(self):
        exp, _ = load_ex("client-checks")
        exp = copy.deepcopy(exp)
        other = {"binary": "/old/nighthawk_client", "md5": "1" * 32, "sha256": "2" * 64}
        exp["arms"].append(dict(exp["arms"][0], name="old", client=other))
        exp["arms"].append(dict(exp["arms"][0], name="old-A2", client=dict(other)))
        exp["arms"].append(dict(exp["arms"][0], name="win", client={"lifetime": "window"}))
        self.assertEqual([a["name"] for a in experiment.calibration_arms(exp)], ["off", "old", "win"])
        # naming the floor arms by hand: every recipe needs one
        exp["client_calibration"]["arm"] = ["off", "old"]
        self.assertTrue(any("no floor arm for the client recipe of ['win']" in x
                            for x in clientcheck.config_errors(exp)))
        exp["client_calibration"]["arm"] = ["off", "old-A2", "win"]
        self.assertEqual(clientcheck.config_errors(exp), [])
        self.assertEqual([a["name"] for a in experiment.calibration_arms(exp)], ["off", "old-A2", "win"])

    def test_dry_run_example(self):
        from epl.experiment import Runner
        from epl.sim import SimBackend
        exp, errs = load_ex("client-checks")
        tmp = tempfile.mkdtemp()
        r = Runner(exp, tmp, SimBackend, allow_short=True)
        res = r.run(simulate=True)
        legs = res["legs"]
        scored = [m for m in legs if not m.get("client_calibration")]
        self.assertTrue(scored)
        self.assertTrue(all(m["verdict"]["valid"] for m in scored), [m["verdict"] for m in scored[:2]])
        self.assertTrue(all(m.get("client_floor_ok") for m in scored))
        self.assertIsNotNone(res)


class SplitTest(unittest.TestCase):
    def test_rates_and_halves(self):
        # half the workers per process, the same rate and connections per worker
        self.assertEqual(clientcheck.split_rates(5184, 16, 32), (2592, 8))
        self.assertEqual(clientcheck.split_rates(5200, 16, 32), (2600, 8))  # shape s itself now divides
        for args in ((5201, 16, 32), (5184, 15, 32)):
            with self.assertRaises(ValueError):
                clientcheck.split_rates(*args)
        self.assertEqual(clientcheck.cpu_halves("20-31,60-71"), ("20-25,60-65", "26-31,66-71"))
        self.assertEqual(clientcheck.cpu_halves("4-5"), ("4", "5"))
        with self.assertRaises(ValueError):
            clientcheck.cpu_halves("20-30")
        r = clientcheck.client_cpu_record(1.0, 5.0, 10.0, 8, 0.6)
        self.assertEqual((r["ok"], r["cpus_per_worker"]), (True, 0.05))
        self.assertFalse(clientcheck.client_cpu_record(0.0, 60.0, 10.0, 8, 0.6)["ok"])
        self.assertEqual(clientcheck.client_cpu_record(None, 5.0, 10.0, 8, 0.6)["reason"],
                         "client process CPU not read")

    def test_verdict(self):
        self.assertEqual(clientcheck.split_verdict(0.4, 8, 1.0, True)["reading"], "client not the bottleneck")
        v = clientcheck.split_verdict(-1.6, 8, 1.0, True)
        self.assertEqual((v["reading"], v["client_bottleneck"], v["pass"]), ("client bottleneck", True, False))
        for args in ((0.1, 8, 1.0, False), (None, 0, 1.0, True), (0.1, 1, 1.0, True)):
            v = clientcheck.split_verdict(*args)
            self.assertEqual((v["reading"], v["pass"]), ("not resolved", False))



if __name__ == "__main__":
    unittest.main()
