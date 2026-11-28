"""The client-window checks: the client's lifetime follows the window, the client-sending check, in-window
denominators and the client self-check. Code tests only; no box, no Nighthawk build."""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

from epl import experiment, leg, nighthawk, validity
from tests.test_experiment import cfg, load


def nh_json(workers=2, start="2026-11-25T14:04:37.984152Z", dur="24.5s", counters=None, blocking=0,
            callback_max="0.021434367s", graceful=0):
    """A Nighthawk JSON output in the shape the box binary writes (global plus one result per worker)."""
    def stats(cb_max):
        return [{"id": "benchmark_http_client.request_to_response", "count": "100", "mean": "0.0004s",
                 "max": "0.009s", "percentiles": [{"percentile": 0.5, "duration": "0.0004s"},
                                                   {"percentile": 0.99, "duration": "0.001s"}]},
                {"id": "sequencer.blocking", "count": str(blocking), "mean": "0s",
                 "max": "0.002s" if blocking else "0s"},
                {"id": "sequencer.callback", "count": "100", "mean": "0.0004s", "max": cb_max}]
    c = {"benchmark.http_2xx": 1000, "upstream_rq_total": 1000, "upstream_cx_total": 32,
         "upstream_rq_pending_total": workers}
    if graceful:
        c["graceful_stop_requested"] = graceful
    c.update(counters or {})
    res = [{"name": "global", "execution_start": start, "execution_duration": dur, "statistics": stats(callback_max),
            "counters": [{"name": k, "value": str(v)} for k, v in c.items()]}]
    if workers > 1:
        for i in range(workers):
            res.append({"name": "worker_%d" % i, "execution_start": start, "execution_duration": dur,
                        "statistics": stats(callback_max if i == 0 else "0.001s"), "counters": []})
    return {"results": res, "version": {"version": {"major_number": 0, "minor_number": 3, "patch": 0}}}


def write_json(d, obj):
    p = os.path.join(d, "nh.json")
    with open(p, "w") as f:
        json.dump(obj, f)
    return p


class ClientArgsTest(unittest.TestCase):
    def test_no_duration(self):
        a = nighthawk.client_args({"concurrency": 16}, 1600, "http://127.0.0.1:1/s", None, True)
        self.assertIn("--no-duration", a)
        self.assertNotIn("--duration", a)

    def test_duration_unchanged(self):
        a = nighthawk.client_args({"concurrency": 16}, 1600, "http://127.0.0.1:1/s", 25, True)
        self.assertEqual(a[:8], ["--rps", "100", "--connections", "16", "--concurrency", "16", "--duration", "25"])
        self.assertNotIn("--no-duration", a)

    def test_ramp_and_arg_value(self):
        ramp = ('--rate-limiter-plugin={"name":"nighthawk.linear_rate_limiter","typed_config":{"@type":'
                '"type.googleapis.com/nighthawk.LinearRampingRateLimiterConfig","ramp_time":"1s"}}')
        self.assertEqual(nighthawk.ramp_s(["--rps", "10", ramp]), 1.0)
        self.assertEqual(nighthawk.ramp_s(["--rps", "10"]), 0.0)
        self.assertEqual(nighthawk.arg_value(["--duration", "25", "x"], "--duration"), "25")
        self.assertIsNone(nighthawk.arg_value(["--no-duration"], "--duration"))

    def test_lifetime_option(self):
        self.assertEqual(leg.client_lifetime({}), "duration")
        self.assertEqual(leg.client_lifetime({"lifetime": "window"}), "window")
        with self.assertRaises(ValueError):
            leg.client_lifetime({"lifetime": "forever"})


class TimestampTest(unittest.TestCase):
    def test_forms(self):
        base = nighthawk.parse_timestamp("2026-11-25T14:04:37Z")
        self.assertEqual(base, 1795615477.0)
        self.assertAlmostEqual(nighthawk.parse_timestamp("2026-11-25T14:04:37.984152Z") - base, 0.984152, places=6)
        self.assertAlmostEqual(nighthawk.parse_timestamp("2026-11-25T14:04:37.123456789Z") - base, 0.123456789,
                               places=6)
        self.assertAlmostEqual(nighthawk.parse_timestamp("2026-11-25T15:04:37+01:00"), base)
        for bad in (None, "", "yesterday", 5):
            self.assertIsNone(nighthawk.parse_timestamp(bad))


class ParseOutputTest(unittest.TestCase):
    def test_worker_exec_and_sequencer(self):
        with tempfile.TemporaryDirectory() as d:
            p = nighthawk.parse_output(write_json(d, nh_json(workers=2, blocking=3, graceful=2)))
        self.assertEqual([w["name"] for w in p["worker_exec"]], ["worker_0", "worker_1"])
        self.assertAlmostEqual(p["worker_exec"][0]["duration_s"], 24.5)
        self.assertIsNotNone(p["worker_exec"][0]["start_wall_s"])
        self.assertEqual(p["graceful_stop_requested"], 2)
        self.assertEqual(p["failed_terminations"], 0)
        self.assertEqual(p["sequencer"]["blocking_count_total"], 6)
        self.assertAlmostEqual(p["sequencer"]["callback_max_us"], 21434.367, places=2)
        self.assertAlmostEqual(p["sequencer"]["blocking_max_us"], 2000.0)
        # unchanged fields
        self.assertAlmostEqual(p["rate_2xx"], 1000 / 24.5)
        self.assertEqual(p["workers"], 2)

    def test_single_worker_uses_global(self):
        with tempfile.TemporaryDirectory() as d:
            p = nighthawk.parse_output(write_json(d, nh_json(workers=1)))
        self.assertEqual([w["name"] for w in p["worker_exec"]], ["global"])
        self.assertIn("global", p["sequencer"]["per_worker"])

    def test_real_recording_if_present(self):
        # EPL_TEST_DATA: a directory with a recorded Nighthawk output (nighthawk/r01-s-b1s.json); skipped without it
        f = os.path.join(os.environ.get("EPL_TEST_DATA") or "", "nighthawk", "r01-s-b1s.json")
        if not os.environ.get("EPL_TEST_DATA") or not os.path.exists(f):
            self.skipTest("EPL_TEST_DATA not set or the recording is not present")
        p = nighthawk.parse_output(f)
        self.assertEqual(len(p["worker_exec"]), p["workers"])
        self.assertTrue(all(w["start_wall_s"] for w in p["worker_exec"]))
        self.assertEqual(p["sequencer"]["blocking_count_total"], 0)
        self.assertEqual(p["graceful_stop_requested"], 0)


def worker(start_wall, dur, name="worker_0"):
    return {"name": name, "start_wall_s": start_wall, "duration_s": dur}


class SendingCheckTest(unittest.TestCase):
    # wall = mono + 1000 (mono_minus_wall = -1000)
    OFF = -1000.0

    def check(self, **kw):
        a = dict(lifetime="duration", workers_exec=[worker(1100.3, 25.0), worker(1100.31, 25.0, "worker_1")],
                 mono_minus_wall_s=self.OFF, t_window_start=103.3, t_last_read=123.6, ramp=1.0, margin_s=1.0,
                 alive_at_last_read=True)
        a.update(kw)
        return nighthawk.sending_check(**a)

    def test_normal_old_recipe_passes(self):
        r = self.check()
        self.assertTrue(r["ok"], r)
        self.assertAlmostEqual(r["first_end_after_last_read_s"], 1.7, places=3)
        self.assertAlmostEqual(r["last_ramp_end_before_window_s"], 1.99, places=3)

    def test_stretched_window_fails_named(self):
        # 16 workers: lead-in 3 s, then a 24.21 s stats window against a 25 s client
        r = self.check(t_window_start=103.3, t_last_read=103.3 + 24.21)
        self.assertFalse(r["ok"])
        self.assertIn("stopped", r["reasons"][0])

    def test_margin(self):
        self.assertFalse(self.check(t_last_read=124.5)["ok"])  # 0.8 s left, margin 1 s
        self.assertTrue(self.check(t_last_read=124.5, margin_s=0.5)["ok"])

    def test_ramp_inside_window_fails(self):
        r = self.check(t_window_start=101.0)
        self.assertFalse(r["ok"])
        self.assertIn("ramp", r["reasons"][0])

    def test_dead_or_missing_fail_closed(self):
        self.assertFalse(self.check(alive_at_last_read=False)["ok"])
        self.assertFalse(self.check(workers_exec=[])["ok"])
        self.assertFalse(self.check(workers_exec=[worker(None, 25.0)])["ok"])
        self.assertFalse(self.check(mono_minus_wall_s=None)["ok"])

    def test_worker_results_must_match_configured_workers(self):
        # two configured workers, one result in the output
        r = self.check(workers_exec=[worker(1100.3, 25.0)], workers=2)
        self.assertFalse(r["ok"])
        self.assertIn("client output has 1 worker results for 2 workers", r["reasons"])
        self.assertTrue(self.check(workers=2)["ok"])
        self.assertTrue(self.check(workers_exec=[worker(1100.3, 25.0, "global")], workers=1)["ok"])

    def test_window_lifetime(self):
        ws = [worker(1100.3, 25.0), worker(1100.3, 25.0, "worker_1")]
        ok = self.check(lifetime="window", workers_exec=ws, exit_code=0, graceful_stops=2, workers=2)
        self.assertTrue(ok["ok"], ok)
        for bad in (dict(exit_code=1), dict(exit_code=None), dict(graceful_stops=0), dict(graceful_stops=1),
                    dict(failed_terminations=1)):
            kw = dict(lifetime="window", workers_exec=ws, exit_code=0, graceful_stops=2, workers=2)
            kw.update(bad)
            self.assertFalse(self.check(**kw)["ok"], bad)


class TerminateTest(unittest.TestCase):
    """OwnProcesses.terminate against a stand-in client that keeps Nighthawk's signal contract (the real
    binary's behaviour is checked on the box). The stand-in logs every SIGTERM it receives."""
    FAKE = textwrap.dedent("""
        import json, os, signal, sys, time
        out, mode, log = sys.argv[1], sys.argv[2], sys.argv[3]
        state = {"n": 0}
        def got(*_):
            with open(log, "a") as f:
                f.write("TERM\\n")
            state["n"] += 1
        signal.signal(signal.SIGTERM, got if mode == "obey" else signal.SIG_IGN)
        print("ready", flush=True)
        t = time.monotonic()
        while time.monotonic() - t < 60:
            if state["n"]:
                time.sleep(0.3)  # a second SIGTERM arriving now would be logged too
                json.dump({"results": [{"name": "global", "execution_duration": "1s", "counters":
                           [{"name": "graceful_stop_requested", "value": "1"}]}]}, open(out, "w"))
                sys.exit(0)
            time.sleep(0.01)
    """)

    def run_fake(self, mode, grace, then_stop=False):
        own = leg.OwnProcesses()
        with tempfile.TemporaryDirectory() as d:
            script = os.path.join(d, "fake.py")
            with open(script, "w") as f:
                f.write(self.FAKE)
            out, log = os.path.join(d, "o.json"), os.path.join(d, "sig.log")
            p = own.start([sys.executable, "-I", script, out, mode, log], stdout=subprocess.PIPE, text=True)
            p.stdout.readline()
            try:
                rc = own.terminate(p, grace_s=grace)
            finally:
                if then_stop:
                    own.stop(p)  # run_leg's finally: must not raise, must not signal again
            body = sig = None
            if os.path.exists(out):
                with open(out) as f:
                    body = f.read()
            if os.path.exists(log):
                with open(log) as f:
                    sig = f.read().count("TERM")
            p.stdout.close()
        return rc, body, sig, own

    def test_one_sigterm_output_and_rc0(self):
        rc, body, sig, own = self.run_fake("obey", 10)
        self.assertEqual(rc, 0)
        self.assertIn("graceful_stop_requested", body)
        self.assertEqual(sig, 1)
        self.assertEqual(own.pids(), set())

    def test_terminate_then_stop_as_run_leg_does(self):
        # terminate() followed by the finally's stop() on the same Popen
        rc, body, sig, own = self.run_fake("obey", 10, then_stop=True)
        self.assertEqual(rc, 0)
        self.assertEqual(sig, 1)
        self.assertEqual(own.procs, {})

    def test_ignored_is_killed_none(self):
        t = time.monotonic()
        rc, body, sig, own = self.run_fake("ignore", 0.5, then_stop=True)
        self.assertIsNone(rc)
        self.assertIsNone(body)
        self.assertLess(time.monotonic() - t, 15)
        self.assertEqual(own.procs, {})

    def test_refuses_foreign(self):
        own = leg.OwnProcesses()
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        with self.assertRaises(RuntimeError):
            own.terminate(p)


def leg_record(**kw):
    m = {"idle_ok": True, "preflight_ok": True, "target_rps": 1000, "sut_rate_2xx": 1000.0, "client_headroom": 0.5,
         "perf_ok": True, "responses": 20000, "sut_foreign_cpus": 0.0, "sut_sibling_cpus": 0.0,
         "envoy_worker_max_share": 0.25, "envoy_worker_min_share": 0.25, "envoy_workers": 4}
    m.update(kw)
    return m


class ValidityTest(unittest.TestCase):
    def test_old_leg_unchanged(self):
        self.assertTrue(validity.verdict(leg_record())["valid"])

    def test_marked_without_record_fails_closed(self):
        v = validity.verdict(leg_record(harness_marks=["n1"]))
        self.assertFalse(v["valid"])
        self.assertIn("no client-sending record", v["reasons"])

    def test_record_gates(self):
        good = {"ok": True, "reasons": []}
        bad = {"ok": False, "reasons": ["a client worker stopped -2.000 s after the window's last read"]}
        self.assertTrue(validity.verdict(leg_record(harness_marks=["n1"], client_sending=good))["valid"])
        v = validity.verdict(leg_record(harness_marks=["n1"], client_sending=bad))
        self.assertFalse(v["valid"])
        self.assertTrue(v["reasons"][0].startswith("client not sending through the window"))
        self.assertTrue(validity.verdict(leg_record(client_sending=bad), {"require_client_sending": False})["valid"])

    def test_margin_default(self):
        self.assertEqual(leg.client_sending_margin({}), 1.0)
        self.assertEqual(leg.client_sending_margin({"client_sending_margin_s": 0.25}), 0.25)


class InWindowDenominatorsTest(unittest.TestCase):
    """Per-request figures divide by in-window counts on n1 legs; unmarked legs keep their published ones."""

    def test_per_request_rate(self):
        self.assertEqual(nighthawk.per_request_rate({"sut_rate_2xx": 20000.0, "client_rate_2xx": 19000.0}), 20000.0)
        self.assertIsNone(nighthawk.per_request_rate({"client_rate_2xx": 19000.0}))

    def test_steady_rate(self):
        # a 16-worker leg: run-wide rate under-reads by ramp / 2 over the execution
        self.assertAlmostEqual(nighthawk.steady_rate(2450, 24.5, 1.0), 2450 / 24.0)
        self.assertAlmostEqual(nighthawk.steady_rate(2450, 24.5, 0.0), 100.0)
        self.assertIsNone(nighthawk.steady_rate(10, 0.4, 1.0))



PERF_CSV = """20000.50,msec,task-clock,20000500000,100.00,1.000,CPUs utilized
46000000000,,cycles,20000500000,100.00,2.300,GHz
52000000000,,instructions,20000500000,100.00,1.13,insn per cycle
1200,,context-switches,20000500000,100.00,60.0,/sec
"""


class ClientSelfCheckTest(unittest.TestCase):
    """A client self-check that can fail."""

    def test_perf_record(self):
        r = leg.client_perf_record(PERF_CSV, 20.0, 400000, 16)
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["cpus"], 1.000025)
        self.assertAlmostEqual(r["cpus_per_worker"], 1.000025 / 16)
        self.assertAlmostEqual(r["cycles_per_req"], 115000.0)
        self.assertAlmostEqual(r["ghz"], 46e9 / 20.0005 / 1e9)
        mux = PERF_CSV.replace("46000000000,,cycles,20000500000,100.00", "46000000000,,cycles,10000000000,50.00")
        self.assertFalse(leg.client_perf_record(mux, 20.0, 400000, 16)["ok"])
        self.assertFalse(leg.client_perf_record("", 20.0, 400000, 16)["ok"])

    def test_floor_and_above(self):
        cal = {"shape": "s-floor", "target_rps": 16, "client_thread_busy_max": 0.26,
               "client_perf": {"ok": True, "cpus_per_worker": 0.25}, "client_sending": {"ok": True},
               "client_sequencer": {"blocking_count_total": 0}}
        f = leg.client_floor_record(cal, "r00-s-floor-a")
        self.assertTrue(f["ok"], f)
        self.assertEqual(f["thread_busy_max"], 0.26)
        a = leg.above_floor(f, 0.31, {"cpus_per_worker": 0.27})
        self.assertAlmostEqual(a["client_busy_above_floor"], 0.05)
        self.assertAlmostEqual(a["client_perf_cpus_above_floor"], 0.02)
        self.assertEqual(leg.above_floor(None, 0.31, None), {})
        for bad in (dict(error="x"), dict(client_thread_busy_max=None), dict(client_sending={"ok": False}),
                    dict(client_sequencer={"blocking_count_total": 2}), dict(client_perf={"ok": False})):
            fb = leg.client_floor_record(dict(cal, **bad), "x")
            self.assertFalse(fb["ok"], bad)
            self.assertNotIn("client_busy_above_floor", leg.above_floor(fb, 0.31, None))
        # a floor leg without a client-sending record is not a good floor
        nr = dict(cal)
        nr.pop("client_sending")
        self.assertFalse(leg.client_floor_record(nr, "x")["ok"])
        # the ramp-end item alone does not fail a zero-load floor; any other sending item
        # (alone or beside it) still does, and a not-ok record without reasons still does
        ramp = "a client worker's ramp ended 0.301 s after the window's first read"
        fw = leg.client_floor_record(dict(cal, client_sending={"ok": False, "reasons": [ramp],
                                                              "last_ramp_end_before_window_s": -0.3007}), "x")
        self.assertTrue(fw["ok"], fw)
        self.assertTrue(fw["sending_ramp_end_waived"])
        # bounded: 1.5 s late is waived, later or unrecorded is not
        for late, want in ((-1.5, True), (-1.5001, False), (-4.0, False), (None, False)):
            fl = leg.client_floor_record(dict(cal, client_sending={"ok": False, "reasons": [ramp],
                                                                  "last_ramp_end_before_window_s": late}), "x")
            self.assertEqual((fl["ok"], fl["sending_ramp_end_waived"]), (want, want), late)
        self.assertFalse(f["sending_ramp_end_waived"])
        for rs in ([ramp, "client had exited before the window's last read ended"],
                   ["a client worker stopped 0.200 s after the window's last read (need >= 1.000 s)"], []):
            fb = leg.client_floor_record(dict(cal, client_sending={"ok": False, "reasons": rs}), "x")
            self.assertFalse(fb["ok"], rs)
            self.assertFalse(fb["sending_ramp_end_waived"], rs)
        # the headroom stands in for the thread busy share (the simulator's legs)
        self.assertEqual(leg.client_floor_record({"client_headroom": 0.7}, "x")["thread_busy_max"], 0.30000000000000004)

    def test_gates_off_by_default(self):
        m = leg_record(client_sequencer={"blocking_count_total": 5, "callback_max_us": 900000.0},
                       client_busy_above_floor=0.9)
        self.assertTrue(validity.verdict(m)["valid"])

    def test_sequencer_gates(self):
        c = {"max_client_sequencer_blocking": 0, "max_client_callback_ms": 50}
        ok = leg_record(client_sequencer={"blocking_count_total": 0, "callback_max_us": 30000.0})
        self.assertTrue(validity.verdict(ok, c)["valid"])
        v = validity.verdict(leg_record(client_sequencer={"blocking_count_total": 3, "callback_max_us": 30000.0}), c)
        self.assertEqual(v["reasons"], ["client sequencer blocked 3 times (limit 0)"])
        v = validity.verdict(leg_record(client_sequencer={"blocking_count_total": 0, "callback_max_us": 60000.0}), c)
        self.assertEqual(v["reasons"], ["client sequencer.callback max 60.0 ms over 50.0 ms"])
        v = validity.verdict(leg_record(), c)
        self.assertEqual(len(v["reasons"]), 2)  # missing statistics fail closed

    def test_floor_gates(self):
        c = {"max_client_busy_above_floor": 0.2, "max_client_perf_cpus_above_floor": 0.1}
        good = leg_record(client_busy_above_floor=0.05, client_perf_cpus_above_floor=0.02, client_floor_leg="f")
        self.assertTrue(validity.verdict(good, c)["valid"])
        v = validity.verdict(dict(good, client_busy_above_floor=0.35), c)
        self.assertEqual(v["reasons"], ["busiest client thread 0.350 above the zero-load floor (limit 0.200)"])
        v = validity.verdict(leg_record(), c)
        self.assertEqual(len(v["reasons"]), 2)
        self.assertIn("no good calibration leg in this run", v["reasons"][0])
        v = validity.verdict(leg_record(client_perf={"ok": False}))
        self.assertIn("client perf counters missing or multiplexed", v["reasons"])

    def test_parse_feeds_gates(self):
        with tempfile.TemporaryDirectory() as d:
            p = nighthawk.parse_output(write_json(d, nh_json(workers=4, blocking=1, callback_max="0.080s")))
        v = validity.verdict(leg_record(client_sequencer=p["sequencer"]),
                             {"max_client_sequencer_blocking": 0, "max_client_callback_ms": 50})
        self.assertEqual(len(v["reasons"]), 2)


class ClientPerfCommandTest(unittest.TestCase):
    """The client's perf stat cannot be taken over by a window-command wrapper."""

    def test_command_shape(self):
        al = ["bash", "/x/wrap-perf.sh", "timeline"]
        c = leg.client_perf_cmd({"client_perf_bin": "/usr/bin/perf"}, al, 4242, 20)
        self.assertEqual(c[0], "/usr/bin/perf")
        self.assertNotIn("--", c)
        self.assertNotIn("sleep", c)
        self.assertNotIn("wrapper-perf.sh", " ".join(c))
        self.assertEqual(c[c.index("-p") + 1], "4242")
        self.assertEqual(c[c.index("--timeout") + 1], "20000")
        plain = leg.client_perf_cmd({}, ["perf"], 1, 20.5)
        self.assertEqual(plain[:2], ["perf", "stat"])
        self.assertEqual(plain[-1], "20500")
        self.assertNotIn("--", plain)

    def test_wrapper_never_matches(self):
        # a wrapper intercepts only a `stat` call with -p and a `--`; check its own condition on our argv
        c = leg.client_perf_cmd({}, ["bash", "wrapper-perf.sh", "timeline"], 7, 20)
        args = c[3:]  # what wrapper-perf.sh sees after MODE
        self.assertEqual(args[0], "stat")
        self.assertNotIn("--", args)

    def test_validate(self):
        tmp = tempfile.mkdtemp()
        errs = lambda c: experiment.validate(load(c, tmp))  # noqa: E731
        wrapped = {"lead_in_s": 2, "window_s": 20, "perf": ["bash", "wrapper-perf.sh", "score"], "client_perf": True}
        self.assertTrue(any("client_perf_bin" in e for e in errs(cfg(measure=wrapped))))
        self.assertEqual(errs(cfg(measure=dict(wrapped, client_perf_bin="/usr/bin/perf"))), [])
        self.assertEqual(errs(cfg(measure={"lead_in_s": 2, "window_s": 20, "perf": ["perf"], "client_perf": True})),
                         [])
        self.assertTrue(errs(cfg(measure=dict(wrapped, client_perf_bin=""))))


class FloorSignatureTest(unittest.TestCase):
    """A floor applies only to legs with the same client flags."""

    def test_signature_drops_rate_and_target(self):
        c = {"concurrency": 16}
        a = nighthawk.client_args(c, 16, "http://127.0.0.1:1/s-floor", None, True, ["--h2"])
        b = nighthawk.client_args(c, 1760, "http://127.0.0.1:1/s", None, True, ["--h2"])
        self.assertEqual(nighthawk.client_signature(a, "http://127.0.0.1:1/s-floor"),
                         nighthawk.client_signature(b, "http://127.0.0.1:1/s"))
        self.assertNotIn("--rps", nighthawk.client_signature(a, "u"))
        mt = nighthawk.multi_target_args("http", 1, "/s", {"count": 2})
        d = nighthawk.client_args(c, 1760, mt, None, True)
        self.assertEqual(nighthawk.client_signature(d, mt), nighthawk.client_signature(
            nighthawk.client_args(c, 1760, "u", None, True), "u"))
        h1 = nighthawk.client_args(c, 1760, "u", None, True)
        self.assertNotEqual(nighthawk.client_signature(b, "u"), nighthawk.client_signature(h1, "u"))
        self.assertNotEqual(nighthawk.client_signature(nighthawk.client_args({"concurrency": 8}, 1760, "u", None, True),
                                                       "u"), nighthawk.client_signature(h1, "u"))

    def test_mismatch_fails_closed_by_name(self):
        f = {"leg_id": "r00-s-floor-a", "ok": True, "thread_busy_max": 0.25, "perf_cpus_per_worker": 0.2,
             "client_signature": ["--concurrency", "16"]}
        g = dict(f, leg_id="r00-h2-floor-a", thread_busy_max=0.3, client_signature=["--concurrency", "16", "--h2"])
        a = leg.above_floor([f, g], 0.4, None, ["--concurrency", "16", "--h2"])
        self.assertEqual(a["client_floor_leg"], "r00-h2-floor-a")
        self.assertAlmostEqual(a["client_busy_above_floor"], 0.1)
        x = leg.above_floor([f, g], 0.4, None, ["--concurrency", "8"])
        self.assertEqual(x, {"client_floor_leg": None, "client_floor_ok": False, "client_floor_mismatch": True})
        v = validity.verdict(leg_record(**x), {"max_client_busy_above_floor": 0.2})
        self.assertIn("no matching floor", v["reasons"][0])
        self.assertEqual(leg.above_floor([], 0.4, None, None), {})

    def test_list_of_shapes(self):
        from epl.sim import SimBackend

        class Sending(SimBackend):
            def run_leg(self, *a, **k):
                return dict(SimBackend.run_leg(self, *a, **k), client_sending={"ok": True, "reasons": []})
        tmp = tempfile.mkdtemp()
        self.assertEqual(experiment.validate(load(cfg(client_calibration={"shape": ["s", "fh"]}), tmp)), [])
        self.assertTrue(experiment.validate(load(cfg(client_calibration={"shape": ["s", "s"]}), tmp)))
        self.assertTrue(experiment.validate(load(cfg(client_calibration={"shape": []}), tmp)))
        exp = load(cfg(client_calibration={"shape": ["s", "fh"]}), tmp)
        self.assertEqual([x["name"] for x in experiment.calibration_shapes(exp)], ["s-floor", "fh-floor"])
        res = experiment.Runner(exp, os.path.join(tmp, "run"), Sending).run(simulate=True)
        self.assertEqual([f["leg_id"] for f in res["metadata"]["client_floors"]], ["r00-s-floor-a", "r00-fh-floor-a"])
        self.assertEqual(res["metadata"]["client_floor"]["leg_id"], "r00-s-floor-a")
        self.assertEqual(sum(1 for m in res["legs"] if m.get("client_calibration")), 2)


class KilledClientTest(unittest.TestCase):
    """A client killed after term_grace_s gives a named reason."""

    def test_record_and_verdict(self):
        m = leg_record(harness_marks=["n1"])
        ex = leg.client_killed(m)
        self.assertIsInstance(ex, leg.ClientKilled)
        self.assertEqual(m["error"], leg.CLIENT_KILLED)
        self.assertFalse(m["client_sending"]["ok"])
        v = validity.verdict(m)
        self.assertIn("error: " + leg.CLIENT_KILLED, v["reasons"])
        self.assertIn("client not sending through the window: " + leg.CLIENT_KILLED, v["reasons"])

    def test_run_leg_raises_it_on_a_killed_client(self):
        import inspect
        src = inspect.getsource(leg.RealBackend.run_leg)
        i = src.index("self.own.terminate(cl")
        self.assertIn("raise client_killed(m)", src[i:i + 500])
        self.assertIn("isinstance(ex, ClientKilled)", src)


class RateBypassTest(unittest.TestCase):
    """The divisibility rule and client.lifetime cannot be bypassed, and no client-window number is a no-op."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def errs(self, c):
        return experiment.validate(load(c, self.tmp))

    def test_cli_rates(self):
        from epl import __main__ as cli
        exp = load(cfg(client={"binary": "/bin/true", "concurrency": 16}), self.tmp)
        sh = exp["shapes"][0]
        self.assertEqual(cli.cli_rates(exp, sh, "1600,1760"), [1600, 1760])
        for bad in ("1600,1800", "x", "1760.5"):
            with self.assertRaises(ValueError):
                cli.cli_rates(exp, sh, bad)
        self.assertEqual(cli.cli_rates(exp, dict(sh, client_concurrency=12), "1800"), [1800])
        with self.assertRaises(SystemExit) as cm:
            cli.check_cli_rates(exp, sh, "1800")
        self.assertIn("not divisible by the 16 client workers", str(cm.exception))

    def test_cli_check_runs_before_anything_starts(self):
        import inspect
        from epl import __main__ as cli
        for fn in (cli.cmd_calibrate, cli.cmd_probe):
            src = inspect.getsource(fn)
            self.assertLess(src.index("check_cli_rates("), src.index("_run_dir("), fn.__name__)

    def test_harness_flags_refused_everywhere(self):
        for flag in ("--rps", "--concurrency", "--duration", "--no-duration", "--rps=10", "--duration=5"):
            c = cfg(client={"binary": "/bin/true", "extra_args": [flag, "1"]})
            self.assertTrue(any("set by the harness" in e for e in self.errs(c)), flag)
        c = cfg()
        c["shapes"][0]["client_extra_args"] = ["--concurrency", "3"]
        self.assertTrue(any("shape s client_extra_args" in e for e in self.errs(c)))
        c = cfg()
        c["shapes"][1]["client_base_args"] = ["--duration", "100"]
        self.assertTrue(any("shape fh client_base_args" in e for e in self.errs(c)))
        c = cfg()
        c["arms"][1]["client"] = {"base_args": ["--no-duration"]}
        self.assertTrue(any("arm b client.base_args" in e for e in self.errs(c)))
        c = cfg(client={"binary": "/bin/true", "extra_args": ["--rps-total", "1800"]})
        self.assertFalse(any("set by the harness" in e for e in self.errs(c)))  # not a harness flag; Nighthawk refuses it
        self.assertEqual(self.errs(cfg(client={"binary": "/bin/true", "extra_args": ["--h2", "--open-loop"]})), [])

    def test_phases_refused(self):
        for a in (["--phases", "[]"], ['--phases=[{"id":"warm"}]'], ['{"PHASES": 1}']):
            c = cfg(client={"binary": "/bin/true", "extra_args": a})
            self.assertTrue(any("client phases are refused" in e for e in self.errs(c)), a)

    def test_per_phase_rule(self):
        ok = [{"id": "warm", "requests_per_second": 1600}, {"id": "measure", "requests_per_second": 1760}]
        self.assertEqual(experiment.phase_rate_errors(ok, 16), [])
        bad = [{"id": "warm", "requests_per_second": 1800}, {"id": "m", "requests_per_second": 1800, "workers": 12}]
        e = experiment.phase_rate_errors(bad, 16)
        self.assertEqual(len(e), 1)
        self.assertTrue(e[0].startswith("phase warm: planned total rate 1800 is not divisible by the 16"))

    def test_numbers(self):
        self.assertTrue(any("client_sending_margin_s" in e for e in self.errs(cfg(validity={"client_sending_margin_s":
                                                                                          0.1}))))
        c = cfg()
        c["shapes"][0]["validity"] = {"client_sending_margin_s": -1}
        self.assertTrue(any("shape s validity.client_sending_margin_s" in e for e in self.errs(c)))
        self.assertEqual(self.errs(cfg(validity={"client_sending_margin_s": 0.25})), [])
        self.assertTrue(any("term_slack_s" in e for e in self.errs(cfg(client={"binary": "/bin/true",
                                                                               "term_slack_s": -0.1}))))
        self.assertTrue(any("term_grace_s" in e for e in self.errs(cfg(client={"binary": "/bin/true",
                                                                               "term_grace_s": 0}))))
        self.assertTrue(any("term_grace_s" in e for e in self.errs(cfg(client={"binary": "/bin/true",
                                                                               "term_grace_s": "60"}))))
        self.assertEqual(self.errs(cfg(client={"binary": "/bin/true", "term_slack_s": 0, "term_grace_s": 30})), [])


class CalibrationLegTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_validate(self):
        e = lambda c: experiment.validate(load(c, self.tmp))  # noqa: E731
        self.assertEqual(e(cfg(client_calibration={})), [])
        self.assertEqual(e(cfg(client_calibration={"shape": "fh", "rps_per_worker": 2})), [])
        self.assertTrue(e(cfg(client_calibration={"shape": "nope"})))
        self.assertTrue(e(cfg(client_calibration={"rps_per_worker": 0})))
        self.assertTrue(e(cfg(client_calibration={"rate": 1})))

    def test_shape(self):
        exp = load(cfg(client_calibration={"rps_per_worker": 2}, client={"binary": "/bin/true", "concurrency": 16}),
                   self.tmp)
        sh = experiment.calibration_shape(exp)
        self.assertEqual((sh["name"], sh["rps"], sh["path"]), ("s-floor", 32, "/s"))

    def test_runner_records_floor_unscored(self):
        from epl.sim import SimBackend

        class Sending(SimBackend):
            def run_leg(self, *a, **k):
                return dict(SimBackend.run_leg(self, *a, **k), client_sending={"ok": True, "reasons": []})
        # the plain simulator writes no client-sending record: its floor is not ok
        exp = load(cfg(client_calibration={}), self.tmp)
        bad = experiment.Runner(exp, os.path.join(self.tmp, "run0"), SimBackend).run(simulate=True)
        self.assertFalse(bad["metadata"]["client_floor"]["ok"])
        self.assertIn("client not sending through the window (or no record)", bad["metadata"]["client_floor"]["why"])
        res = experiment.Runner(exp, os.path.join(self.tmp, "run"), Sending).run(simulate=True)
        fl = res["metadata"]["client_floor"]
        self.assertTrue(fl["ok"], fl)
        self.assertEqual(fl["leg_id"], "r00-s-floor-a")
        cal = [m for m in res["legs"] if m.get("client_calibration")]
        self.assertEqual(len(cal), 1)
        self.assertTrue(cal[0]["superseded"])
        self.assertEqual(cal[0]["round"], 0)
        # the analysis is the same as without the calibration leg
        exp2 = load(cfg(), self.tmp)
        res2 = experiment.Runner(exp2, os.path.join(self.tmp, "run2"), SimBackend).run(simulate=True)
        self.assertEqual(res["metadata"]["rounds_complete"], res2["metadata"]["rounds_complete"])
        self.assertEqual(len(res["legs"]), len(res2["legs"]) + 1)


class ExperimentValidateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def errs(self, c):
        return experiment.validate(load(c, self.tmp))

    def test_window_lifetime_has_no_duration_arithmetic(self):
        short = {"binary": "/bin/true", "duration_s": 5}
        self.assertTrue(any("client duration" in e for e in self.errs(cfg(client=short))))
        self.assertEqual(self.errs(cfg(client=dict(short, lifetime="window"))), [])

    def test_bad_lifetime(self):
        self.assertTrue(any("client.lifetime" in e for e in self.errs(cfg(client={"binary": "/bin/true",
                                                                                   "lifetime": "x"}))))


if __name__ == "__main__":
    unittest.main()


class WholeWorkerRateTest(unittest.TestCase):
    """No total-rate option, by design; a total the worker count does not divide is refused."""

    def test_per_worker(self):
        self.assertEqual(nighthawk.per_worker_rps(1760, 16), 110)
        self.assertEqual(nighthawk.per_worker_rps(1800.0, 12), 150)
        with self.assertRaises(ValueError) as cm:
            nighthawk.per_worker_rps(1800, 16)
        self.assertIn("use 1792 or 1808", str(cm.exception))
        for bad in ((1800.5, 1), (0, 16), (100, 0), (None, 16), ("x", 4)):
            with self.assertRaises(ValueError):
                nighthawk.per_worker_rps(*bad)

    def test_client_args_refuses(self):
        with self.assertRaises(ValueError):
            nighthawk.client_args({"concurrency": 16}, 1800, "http://127.0.0.1:1/s", 25, True)

    def test_plan_time_refusal(self):
        tmp = tempfile.mkdtemp()
        errs = lambda c: experiment.validate(load(c, tmp))  # noqa: E731
        c = cfg()
        c["shapes"][0]["rps"] = 4002  # client.concurrency default 4
        self.assertTrue(any("not divisible by the 4 client workers" in e for e in errs(c)), errs(c))
        # a rung's own client worker count is the one that must divide its rate
        c = cfg()
        c["shapes"][0].update(rps=4000, client_concurrency=12)
        self.assertTrue(any("shape s: planned total rate 4000 is not divisible by the 12" in e for e in errs(c)))
        c["shapes"][0]["rps"] = 3996
        self.assertEqual(errs(c), [])
