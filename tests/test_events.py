"""Event-study support. Per-thread CPU from /proc schedstat aligned to the perf clock (epl.workercpu); the scheduler, the null event, the
expected-error declarations, the bracketing-baseline estimands, the frozen band, and the across-instance readings
(epl.events), on synthetic inputs."""
import copy
import os
import tempfile
import time
import unittest

from epl import clientcheck, events, workercpu



# ---------------------------------------------------------------- epl.workercpu

class TaskStatTest(unittest.TestCase):
    def test_parse(self):
        line = "4242 (wrk:worker_3) S 1 2 3 0 -1 4194368 10 0 0 0 1234 567 0 0 20 0 9 0 99 0 0\n"
        self.assertEqual(workercpu.parse_task_stat(line), ("wrk:worker_3", 1234, 567))
        odd = "7 (a) b (c)) R 1 2 3 0 -1 0 0 0 0 0 11 22 0 0\n"
        self.assertEqual(workercpu.parse_task_stat(odd), ("a) b (c)", 11, 22))
        self.assertEqual(workercpu.parse_schedstat("123456789 2000 17\n"), 123456789)

    def test_proc_tree_schedstat(self):
        tmp = tempfile.mkdtemp()
        for tid, comm, u, s, ns in ((100, "envoy", 5, 5, 99_000_000), (101, "wrk:worker_0", 40, 2, 412_345_678),
                                    (102, "wrk:worker_1", 41, 3, 430_000_001), (103, "GrpcGoogClient", 1, 1, 1)):
            d = os.path.join(tmp, "100", "task", str(tid))
            os.makedirs(d)
            with open(os.path.join(d, "comm"), "w") as f:
                f.write(comm + "\n")
            with open(os.path.join(d, "stat"), "w") as f:
                f.write("%d (%s) S 1 1 1 0 -1 0 0 0 0 0 %d %d 0 0 20 0 1 0 5 0 0\n" % (tid, comm, u, s))
            with open(os.path.join(d, "schedstat"), "w") as f:
                f.write("%d 0 0\n" % ns)
        tids = workercpu.worker_threads(100, proc=tmp)
        self.assertEqual(tids, {0: 101, 1: 102})
        # ns from schedstat first, the ticks beside it; the main thread (tid == pid) too
        self.assertEqual(workercpu.read_cpu(100, tids, proc=tmp),
                         {0: [412_345_678, 40, 2], 1: [430_000_001, 41, 3], "main": [99_000_000, 5, 5]})
        self.assertEqual(sorted(workercpu.read_cpu(100, {0: 101, 5: 999}, proc=tmp), key=str), [0, "main"])
        self.assertEqual(workercpu.worker_threads(4242, proc=tmp), {})


def fake_read(t0, shares):
    def read(tids):
        dt = time.monotonic() - t0
        out = {i: [int(dt * 1e9 * shares.get(i, 0.5)), int(dt * 100 * 0.4), int(dt * 100 * 0.1)] for i in tids}
        out["main"] = [int(dt * 1e8), 0, 0]
        return out
    return read


class SamplerTest(unittest.TestCase):
    def test_samples_record_crosscheck(self):
        s = workercpu.WorkerCpuSampler(1, 0.05, threads=lambda: {0: 10, 1: 11}, read=fake_read(time.monotonic(), {}))
        s.start()
        time.sleep(0.5)
        s.stop_evt.set()
        s.join(5)
        r = s.record(workers=2)
        self.assertTrue(r["ok"], r)
        self.assertGreaterEqual(r["n_samples"], 8)
        self.assertAlmostEqual(r["crosscheck"]["0"]["schedstat_cores"], 0.5, places=2)
        self.assertIn("schedstat", r["source"])
        self.assertFalse(s.record(workers=4)["ok"])  # planned 4 workers, found 2

    def test_thread_change_mid_run_and_at_the_end(self):
        n = [0]

        def read(tids):
            n[0] += 1
            out = {0: [n[0], 0, 0], "main": [n[0], 0, 0]}
            if n[0] <= 3:
                out[1] = [n[0], 0, 0]
            return out
        s = workercpu.WorkerCpuSampler(1, 0.02, threads=lambda: {0: 10, 1: 11}, read=read)
        s.start()
        time.sleep(0.2)
        s.stop_evt.set()
        s.join(5)
        self.assertTrue(any("worker threads changed" in x for x in s.record(workers=2)["reasons"]))
        # a live thread read sees a worker that is gone at the end
        sets = [{0: 10, 1: 11}, {0: 10}]
        s = workercpu.WorkerCpuSampler(1, 0.02, threads=lambda: sets.pop(0),
                                       read=lambda t: dict({i: [1, 0, 0] for i in t}, main=[1, 0, 0]))
        s.start()
        time.sleep(0.1)
        s.stop_evt.set()
        s.join(5)
        r = s.record(workers=2)
        self.assertFalse(r["ok"])
        self.assertTrue(any("'after': [0]" in x for x in r["reasons"]), r["reasons"])


class AlignTest(unittest.TestCase):
    def test_align_bins_and_tolerance(self):
        o = 5_000_000_000
        stamped = []
        for i, lag_ms in enumerate((2.0, 0.5, 3.0, 1.0)):
            t = (i + 1) * 1.0
            ns = o + int(t * 1e9) + int(lag_ms * 1e6)
            stamped.append((ns, "%.6f,1000,,cycles:u,1,100.00,," % t))
            stamped.append((ns + 10000, "%.6f,500,,cycles:k,1,100.00,," % t))
        stamped.append((0, "# started on ..."))
        al = workercpu.align_perf_clock(stamped)
        self.assertEqual(al["origin_mono_ns"], o + 500_000)  # the smallest lag
        self.assertAlmostEqual(al["max_lag_ms"], 2.5)
        rows, _, _ = clientcheck.parse_intervals("\n".join(x for _, x in stamped))
        bins = workercpu.perf_bins(rows, al["origin_mono_ns"])
        self.assertEqual(len(bins), 4)
        self.assertEqual(bins[1]["t0_ns"], al["origin_mono_ns"] + 1_000_000_000)
        self.assertEqual((bins[1]["t_rel0"], bins[1]["t_rel"]), (1.0, 2.0))
        self.assertEqual(bins[1]["counts"], {"cycles:u": 1000.0, "cycles:k": 500.0})
        self.assertIsNone(workercpu.align_perf_clock([]))
        # min(10% of a bin, 25 ms)
        self.assertEqual(workercpu.align_tolerance_ms(1000), 25.0)
        self.assertEqual(workercpu.align_tolerance_ms(100), 10.0)

    def test_on_interval_callback(self):
        import io
        seen = []
        st = workercpu.LineStamper(io.StringIO("1.0,5,,cycles,1,100,,\n1.0,6,,instructions:u,1,100,,\n"
                                               "2.0,5,,cycles,1,100,,\n"), on_interval=lambda t, ns: seen.append(t))
        st.run()
        self.assertEqual(seen, [1.0, 2.0])  # once per new interval, on its first line

    def test_bin_worker_cpu_ns(self):
        samples = [{"mono_ns": int(k * 0.25e9), "w": {0: [int(k * 0.25e9 * 0.4), 0, 0],
                                                      1: [int(k * 0.25e9 * 0.8), 0, 0],
                                                      "main": [int(k * 0.25e9 * 0.05), 0, 0]}} for k in range(9)]
        bins = [{"t0_ns": 0, "t1_ns": 1_000_000_000}, {"t0_ns": 1_000_000_000, "t1_ns": 2_000_000_000},
                {"t0_ns": 1_500_000_000, "t1_ns": 2_500_000_000}]
        out = workercpu.bin_worker_cpu(samples, bins)
        self.assertAlmostEqual(out[0]["cores"][0], 0.4)
        self.assertAlmostEqual(out[1]["cores"][1], 0.8)
        self.assertAlmostEqual(out[0]["max_over_mean"], 0.8 / 0.6, places=5)
        self.assertAlmostEqual(out[0]["main_cores"], 0.05)
        self.assertIsNone(out[2])  # past the last sample: never extrapolated


# ---------------------------------------------------------------- epl.events: validation, plan, scheduler

def base_ev(**kw):
    ev = {"kind": "origin_fault", "at_s": [10, 30], "hold_s": 2, "run_s": 50, "pre_s": 5, "post_s": 5,
          "params": {"abort_percent": 5}, "expected_errors": {"codes": ["503"]}}
    ev.update(kw)
    return ev


class EventValidateTest(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(events.event_errors(base_ev()), [])

    def test_refusals(self):
        cal = {"from": "cal-1", "band_pct": 2.0, "bin_ms": 1000}
        cases = [
            ({"kind": "x"}, "event.kind must be one of"),
            ({"at_s": [10, 10]}, "strictly increasing"),
            ({"at_s": [5.5, 30]}, "leaves less than pre_s + one guard bin"),
            ({"at_s": [10, 25]}, "the analysis windows overlap (spacing must be >= post_s + pre_s (bracketing)"),
            ({"at_s": [10, 42]}, "the last event's bracketing window ends after run_s"),
            ({"post_s": 6}, "event.pre_s must be >= post_s"),
            ({"hold_s": None}, "an origin_fault event needs event.hold_s"),
            ({"hold_s": 5}, "event.post_s must exceed hold_s"),
            ({"null": "sometimes"}, "event.null must be"),
            ({"null": "alternate"}, "alternate needs a multiple of 4 events"),
            ({"perf_interval_ms": 50}, "perf_interval_ms must be whole ms >= 100"),
            ({"worker_sample_s": 0.5}, "at least 4 samples per bin"),
            ({"scrape_s": 1.0}, "event: unknown keys ['scrape_s']"),
            ({"lead_in_s": 0.5}, "event.lead_in_s must be a number >= 1"),
            ({"expected_errors": {"codes": ["200"]}}, "codes must be distinct non-2xx"),
            ({"expected_errors": {"codes": ["503"], "window": "x"}}, "window must be hold or hold+post"),
            ({"expected_errors": {"codes": ["503"], "source": "any"}}, "source any must name its local_codes"),
            ({"expected_errors": {"codes": ["503"], "local_codes": ["503"]}}, "local_codes is for source any"),
            ({"expected_errors": {"codes": ["503"], "counters": ["x"]}}, "counters must be among"),
            ({"expected_errors": {"codes": ["503"], "max_share": 2}}, "max_share must be a share"),
            ({"recovery": {"band_pct": 2.0}}, "the band comes frozen from event.calibration"),
            ({"recovery": {"basis": "x"}}, "recovery.basis must be cycles_per_s"),
            ({"calibration": dict(cal, bin_ms=250)}, "a band holds at its own bin size only"),
            ({"calibration": dict(cal, band_pct=0)}, "calibration.band_pct must be a number > 0"),
            ({"calibration": {"band_pct": 2.0, "bin_ms": 1000}}, "calibration.from names the separate null"),
            ({"calibration": dict(cal, sha256="0" * 64)}, "sha256 does not match its content"),
            ({"fault_effect": {"z": -1}}, "event.fault_effect: z > 0"),
            ({"kind": "runtime", "fault_effect": {}}, "event.fault_effect (origin_fault only)"),
            ({"shape_client_check": ""}, "names the client-check result"),
        ]
        for kw, want in cases:
            errs = events.event_errors(base_ev(**kw))
            self.assertTrue(any(want in e for e in errs), (kw, want, errs))
        good = dict(cal)
        good["sha256"] = events.calibration_sha256(good)
        self.assertEqual(events.event_errors(base_ev(calibration=good)), [])

    def test_plan_and_null(self):
        ev = base_ev(null="alternate", at_s=[10, 30, 50, 70], run_s=90)
        self.assertEqual(events.event_errors(ev), [])
        self.assertEqual([n for _, _, ph, n in events.plan(ev) if ph == "on"], [False, True, True, False])  # R N N R
        self.assertTrue(all(n for _, _, _, n in events.plan(base_ev(null=True))))
        self.assertFalse(any(n for _, _, _, n in events.plan(base_ev())))
        self.assertIn("snapshot", events.NULL_EXECUTES["runtime"])  # what a null still executes


class SchedulerTest(unittest.TestCase):
    def test_fires_in_order(self):
        calls = []
        ev = {"at_s": [0.2, 0.5], "hold_s": 0.1, "max_late_ms": 50}
        t0 = time.monotonic_ns()
        s = events.Scheduler(ev, t0, lambda k, ph, null: calls.append((k, ph, null, time.monotonic_ns())) or
                             {"ok": True})
        s.start()
        s.join(5)
        self.assertEqual([(k, ph) for k, ph, _, _ in calls], [(0, "on"), (0, "off"), (1, "on"), (1, "off")])
        for (k, ph, _, t), off in zip(calls, (0.2, 0.3, 0.5, 0.6)):
            self.assertGreaterEqual(t - t0, off * 1e9)
        r = s.record()
        self.assertTrue(r["ok"], r["reasons"])

    def test_late_failed_and_missing_fail_closed(self):
        def act(k, ph, null):
            if (k, ph) == (0, "on"):
                time.sleep(0.3)
            if (k, ph) == (1, "on"):
                raise RuntimeError("POST refused")
            return {"ok": True}
        s = events.Scheduler({"at_s": [0.1, 0.6], "hold_s": 0.1, "max_late_ms": 50}, time.monotonic_ns(), act)
        s.start()
        s.join(5)
        r = s.record()
        self.assertFalse(r["ok"])
        self.assertTrue(any("event 0 off fired" in x and "late" in x for x in r["reasons"]), r["reasons"])
        self.assertTrue(any("event 1 on failed: RuntimeError: POST refused" in x for x in r["reasons"]), r["reasons"])
        s2 = events.Scheduler({"at_s": [5.0]}, time.monotonic_ns(), lambda *a: {"ok": True})
        s2.start()
        s2.stop_evt.set()
        s2.join(5)
        self.assertIn("0 of 1 event actions fired", s2.record()["reasons"])


# ---------------------------------------------------------------- expected errors

def scrape(t_s, ok2xx, c5=0, up503=0, up504=0, **counters):
    st = {"http.ingress_http.downstream_rq_2xx": ok2xx, "http.ingress_http.downstream_rq_5xx": c5,
          "cluster.origin.upstream_rq_200": ok2xx, "cluster.origin.upstream_rq_503": up503,
          "cluster.origin.upstream_rq_504": up504, "cluster.origin.upstream_rq_5xx": up503 + up504}
    st.update({"cluster.origin.upstream_" + k: v for k, v in counters.items()})
    return {"mono_ns": int(t_s * 1e9), "stats": st}


def fired(*events_):
    out = []
    for k, on, off, null in events_:
        out.append({"k": k, "phase": "on", "null": null, "fired_ns": int(on * 1e9), "done_ns": int(on * 1e9) + 1000})
        out.append({"k": k, "phase": "off", "null": null, "fired_ns": int(off * 1e9), "done_ns": int(off * 1e9) + 1000})
    return out


class ExpectedErrorsTest(unittest.TestCase):
    ev = {"post_s": 5, "hold_s": 2, "expected_errors": {"codes": ["503"], "window": "hold+post", "slack_s": 1.0}}

    def check(self, scrapes, fire, ev=None, client=None):
        return events.expected_errors_check(ev or self.ev, fire, events.scrape_deltas(scrapes), client)

    def test_declared_codes_inside_the_interval(self):
        sc = [scrape(t, 100 * t, c5=(5 if t >= 11 else 0), up503=(5 if t >= 11 else 0)) for t in range(0, 20)]
        r = self.check(sc, fired((0, 10.0, 12.0, False)))
        self.assertTrue(r["ok"], r["reasons"])
        self.assertEqual(r["per_event"][0]["codes"], {"503": 5})
        self.assertEqual(r["label"], "Observed (count)")

    def test_one_request_skew_across_adjacent_scrapes_passes(self):
        # the origin's 503 is charged one scrape earlier than the SUT's 5xx for one response
        ups = {11: 2, 12: 5, 13: 9}
        sut = {11: 1, 12: 4, 13: 9}
        sc = [scrape(t, 100 * t, c5=sut.get(t, 9 if t > 13 else 0), up503=ups.get(t, 9 if t > 13 else 0))
              for t in range(0, 20)]
        r = self.check(sc, fired((0, 10.0, 12.0, False)))
        self.assertTrue(r["ok"], r["reasons"])
        self.assertEqual(r["per_event"][0]["classes"], {"5xx": 9})

    def test_outside_and_undeclared_fail(self):
        sc = [scrape(t, 100 * t, c5=(5 if t >= 18 else 0), up503=(5 if t >= 18 else 0)) for t in range(0, 20)]
        r = self.check(sc, fired((0, 10.0, 12.0, False)))
        self.assertFalse(r["ok"])
        self.assertTrue(any("outside every declared interval" in x for x in r["reasons"]))
        sc = [scrape(t, 100 * t, c5=(5 if t >= 11 else 0), up504=(5 if t >= 11 else 0)) for t in range(0, 20)]
        r = self.check(sc, fired((0, 10.0, 12.0, False)))
        self.assertTrue(any("origin code 504 5 not declared" in x for x in r["reasons"]), r["reasons"])
        self.assertTrue(any("not accounted for by the origin's declared codes" in x for x in r["reasons"]))

    def test_local_reply(self):
        # a SUT 5xx with no origin code over the event's whole interval: fails unless source any names its code
        sc = [scrape(t, 100 * t, c5=(5 if t >= 11 else 0)) for t in range(0, 20)]
        r = self.check(sc, fired((0, 10.0, 12.0, False)))
        self.assertFalse(r["ok"])
        self.assertTrue(any("above the origin cluster's 5xx" in x for x in r["reasons"]), r["reasons"])
        ev = copy.deepcopy(self.ev)
        ev["expected_errors"].update(source="any", local_codes=["503"])
        self.assertTrue(self.check(sc, fired((0, 10.0, 12.0, False)), ev)["ok"])

    def test_null_events_get_no_allowance(self):
        sc = [scrape(t, 100 * t, c5=(5 if t >= 11 else 0), up503=(5 if t >= 11 else 0)) for t in range(0, 20)]
        r = self.check(sc, fired((0, 10.0, 12.0, True)))
        self.assertFalse(r["ok"])
        self.assertTrue(any("outside every declared interval" in x for x in r["reasons"]))
        sc = [scrape(t, 100 * t) for t in range(0, 20)]
        self.assertTrue(self.check(sc, fired((0, 10.0, 12.0, True)))["ok"])

    def test_counter_gates(self):
        # a timeout, a connect failure, an overflow or a retry: 0 unless declared, and then only inside
        for name in ("rq_timeout", "cx_connect_fail", "rq_pending_overflow", "cx_overflow", "rq_retry"):
            sc = [scrape(t, 100 * t, **{name: (1 if t >= 11 else 0)}) for t in range(0, 20)]
            r = self.check(sc, fired((0, 10.0, 12.0, False)))
            self.assertTrue(any("cluster.origin.upstream_%s 1" % name in x and "not declared" in x
                                for x in r["reasons"]), (name, r["reasons"]))
        ev = copy.deepcopy(self.ev)
        ev["expected_errors"]["counters"] = ["cluster.origin.upstream_rq_timeout"]
        sc = [scrape(t, 100 * t, rq_timeout=(1 if t >= 11 else 0)) for t in range(0, 20)]
        self.assertTrue(self.check(sc, fired((0, 10.0, 12.0, False)), ev)["ok"])
        sc = [scrape(t, 100 * t, rq_timeout=(1 if t >= 18 else 0)) for t in range(0, 20)]
        r = self.check(sc, fired((0, 10.0, 12.0, False)), ev)
        self.assertTrue(any("outside every declared interval" in x for x in r["reasons"]), r["reasons"])

    def test_window_hold_share_and_client(self):
        ev = copy.deepcopy(self.ev)
        ev["expected_errors"].update(window="hold", max_share=0.01)
        sc = [scrape(t, 100 * t, c5=(5 if t >= 15 else 0), up503=(5 if t >= 15 else 0)) for t in range(0, 20)]
        self.assertFalse(self.check(sc, fired((0, 10.0, 12.0, False)), ev)["ok"])
        sc = [scrape(t, 100 * t, c5=(50 if t >= 11 else 0), up503=(50 if t >= 11 else 0)) for t in range(0, 20)]
        r = self.check(sc, fired((0, 10.0, 12.0, False)), ev)
        self.assertTrue(any("above the declared 0.010" in x for x in r["reasons"]), r["reasons"])
        sc = [scrape(t, 100 * t) for t in range(0, 20)]
        r = self.check(sc, fired((0, 10.0, 12.0, False)), client={"benchmark.http_4xx": 2, "benchmark.http_5xx": 0})
        self.assertIn("client benchmark.http_4xx 2 not a declared class", r["reasons"])


# ---------------------------------------------------------------- estimands

def mkbins(n, cyc_at, dt=1.0, ins_at=None, skew_at=None):
    bins, w = [], []
    for i in range(n):
        c = cyc_at(i)
        ins = (ins_at or (lambda j: 2.0 * cyc_at(j)))(i)
        bins.append({"t0_ns": int(i * dt * 1e9), "t1_ns": int((i + 1) * dt * 1e9), "dt_s": dt, "t_rel0": i * dt,
                     "t_rel": (i + 1) * dt, "counts": {"cycles:u": c * 0.6, "cycles:k": c * 0.4,
                                                       "instructions:u": ins * 0.7, "instructions:k": ins * 0.3},
                     "uncounted": []})
        w.append({"max_over_mean": (skew_at or (lambda j: 1.02))(i), "main_cores": 0.05})
    return bins, [1000.0] * n, w


class EstimandTest(unittest.TestCase):
    ev = {"pre_s": 5, "post_s": 5, "recovery": {"consecutive_bins": 2},
          "calibration": {"from": "cal", "band_pct": 2.0, "bin_ms": 1000, "sigma_cycles_per_bin": 1e6}}

    def est(self, bins, reqs, w, at=10.0, null=False, ev=None):
        return events.event_estimands(ev or self.ev, fired((0, at, at + 2, null)), bins, reqs, w)[0]

    def test_excess_t95_settled_and_the_guard_bin(self):
        extra = {10: 5e7, 11: 4e7, 12: 1e7}
        bins, reqs, w = mkbins(30, lambda i: 1e8 + extra.get(i, 0.0) + (9e7 if i == 9 else 0.0),
                               ins_at=lambda i: 2e8)
        e = self.est(bins, reqs, w)
        self.assertTrue(e["complete"], e)
        self.assertTrue(e["guard_bin"])  # bin 9 (the spike) is the guard bin: not in the baseline
        self.assertEqual((e["pre_bins"], e["post_bins"], e["postpost_bins"]), (5, 5, 5))
        self.assertAlmostEqual(e["excess_cycles"], 1.0e8)
        self.assertAlmostEqual(e["excess_instructions"], 0.0)  # cycles moved, instructions did not
        self.assertAlmostEqual(e["excess_cycles_per_post_window_request"], 1.0e8 / 5000)
        # t95: 95 M of 100 M are reached inside bin 12 (cum 90 M after bin 11; bin 12 adds 10 M): 2.5 s
        self.assertAlmostEqual(e["t95_s"], 2.5)
        self.assertEqual(e["settled_s"], 3.0)
        self.assertFalse(e["censored"])
        self.assertIn("excess_se_cycles", e)
        self.assertEqual(e["basis"], events.LABEL)

    def test_bracketing_removes_linear_drift(self):
        bins, reqs, w = mkbins(30, lambda i: 1e8 * (1 + 0.01 * i))
        e = self.est(bins, reqs, w, null=True)
        self.assertLess(abs(e["excess_cycles"]), 1e-3 * 1e8)
        # a pre-only median would have charged the drift to the event: 5 bins x up to 5% x 1e8
        self.assertLess(e["peak_dev_pct"], 0.1)

    def test_censored_incomplete_and_no_band(self):
        bins, reqs, w = mkbins(30, lambda i: 1e8 if i < 10 or i >= 15 else 1.5e8)
        e = self.est(bins, reqs, w)
        self.assertTrue(e["censored"])  # 5 post bins at +50%: never settles inside post_s
        self.assertEqual(e["settled"], "not recovered within post_s")
        ev = copy.deepcopy(self.ev)
        ev.pop("calibration")
        self.assertEqual(self.est(bins, reqs, w, ev=ev)["settled"],
                         "Not resolved (no frozen band in event.calibration)")
        w2 = list(w)
        w2[12] = None
        self.assertIn("a bin without per-worker CPU", self.est(bins, reqs, w2)["reasons"])
        self.assertFalse(self.est(bins, reqs, w, at=26.0)["complete"])  # no post-post window
        self.assertFalse(self.est(bins, reqs, w, at=3.0)["complete"])  # too little baseline
        ev = copy.deepcopy(self.ev)
        ev["recovery"]["basis"] = "cycles_per_req"
        reqs2 = list(reqs)
        reqs2[12] = None  # an uncounted bin
        self.assertIn("a bin without a counted request count (recovery.basis cycles_per_req)",
                      self.est(bins, reqs2, w, ev=ev)["reasons"])

    def test_requests_counted_at_the_edges(self):
        o = 1_000_000_000
        bins = workercpu.perf_bins([{"t": 1.0}, {"t": 2.0}, {"t": 3.0}], o)
        sc = [{"t": 0.0, "mono_ns": o + 3_000_000, "stats": {"http.ingress_http.downstream_rq_2xx": 0}},
              {"t": 1.0, "mono_ns": o + 1_004_000_000, "stats": {"http.ingress_http.downstream_rq_2xx": 1000}},
              {"t": 2.0, "mono_ns": o + 2_060_000_000, "stats": {"http.ingress_http.downstream_rq_2xx": 2050}},
              {"t": 3.0, "mono_ns": o + 3_002_000_000, "stats": {"http.ingress_http.downstream_rq_2xx": 3000,
                                                                 "http.ingress_http.downstream_rq_5xx": 7}}]
        # the 2.0 edge answered 60 ms late: both bins it bounds are uncounted (never interpolated)
        self.assertEqual(events.requests_per_bin(bins, sc, o, 25.0), [1000, None, None])
        sc[2]["mono_ns"] = o + 2_010_000_000
        self.assertEqual(events.requests_per_bin(bins, sc, o, 25.0), [1000, 1050, 957])

    def test_band_check_calibrate_and_quantile(self):
        bins, reqs, w = mkbins(30, lambda i: 1e8 * (1.0 + (0.004 if i % 2 else -0.004)))
        nul = self.est(bins, reqs, w, null=True)
        self.assertFalse(nul["censored"])
        self.assertTrue(events.band_check([nul])["ok"])
        ev = copy.deepcopy(self.ev)
        ev["calibration"]["band_pct"] = 0.1  # tighter than the null's own noise: its nulls never settle
        bad = self.est(bins, reqs, w, null=True, ev=ev)
        r = events.band_check([bad])
        self.assertFalse(r["ok"])
        self.assertTrue(r["reading"].startswith("Not resolved"))
        rec, extra = events.calibrate([[nul, nul]] * 6, "cal-run", 1000)
        self.assertEqual(rec["n_instances"], 6)
        self.assertEqual(rec["bin_ms"], 1000)
        self.assertEqual(rec["sha256"], events.calibration_sha256(rec))
        self.assertLessEqual(rec["band_pct"], max(nul["post_devs_pct"]))
        self.assertEqual(events.calibration_errors(rec, 1000), [])
        with self.assertRaises(ValueError):
            events.calibrate([[nul]] * 5, "cal-run", 1000)  # fewer than 6 instances
        real = self.est(bins, reqs, w)
        with self.assertRaises(ValueError):
            events.calibrate([[nul, real]] * 6, "cal-run", 1000)  # a calibration holds nulls only
        self.assertAlmostEqual(events.quantile(list(range(101)), 0.99), 99.0)


def inst(name, real_x, null_x, real_skew=1.3, null_skew=1.2, real_ins=None, t95=2.0, censored=False):
    es = []
    for k, (x, null) in enumerate(zip(real_x + null_x, [False] * len(real_x) + [True] * len(null_x))):
        es.append({"k": k, "null": null, "complete": True, "excess_cycles": x,
                   "excess_instructions": (real_ins if real_ins is not None else 2 * x) if not null else 0.0,
                   "peak_worker_max_over_mean": null_skew if null else real_skew, "peak_dev_pct": 1.0,
                   "t95_s": None if null else t95, "censored": censored and not null, "settled_s": 1.0})
    return {"name": name, "estimands": es}


class AcrossInstancesTest(unittest.TestCase):
    def test_alternate(self):
        insts = [inst("i%d" % i, [100.0 + i, 102.0 + i], [1.0, -1.0], real_skew=1.3 + 0.01 * i) for i in range(6)]
        a = events.across_instances(insts, within_s=3.0)
        self.assertEqual(a["n_instances"], 6)
        self.assertAlmostEqual(a["excess_cycles"]["mean"], 103.5)
        self.assertEqual(a["excess_cycles"]["reading"], "detected")
        self.assertNotIn("label", a["excess_cycles"])
        # the skew is real peak minus null peak
        self.assertAlmostEqual(a["peak_worker_max_over_mean"]["mean"], 0.125, places=6)
        self.assertEqual(a["recovery"]["reading"], "recovers within 3.0 s")
        self.assertTrue(a["null_subtracted"])
        self.assertEqual(a["basis"], events.LABEL)

    def test_mix_refused_and_drops_named(self):
        insts = [inst("i%d" % i, [100.0, 101.0], [0.0, 0.0]) for i in range(5)] + [inst("raw", [100.0, 101.0], [])]
        with self.assertRaises(ValueError) as cm:
            events.across_instances(insts)
        self.assertIn("['raw'] hold no null event", str(cm.exception))
        insts[-1] = inst("short", [100.0, 101.0], [0.0])
        a = events.across_instances(insts)
        self.assertEqual(a["dropped"], [{"name": "short", "why": "2 complete real and 1 complete null events "
                                                                 "(want >= 2 each)"}])
        self.assertEqual(a["n_instances"], 5)
        self.assertTrue(a["excess_cycles"]["reading"].startswith("Not resolved (fewer than 6 instances)"))

    def test_mechanism_label_censoring_and_carry_over(self):
        insts = [inst("i%d" % i, [100.0 + i, 101.0 - i], [0.0, 0.0], real_ins=0.5 * (-1) ** i, censored=(i < 3))
                 for i in range(6)]
        a = events.across_instances(insts, margin={"excess_instructions": 5.0}, within_s=10.0)
        self.assertEqual(a["excess_cycles"]["reading"], "detected")
        self.assertTrue(a["excess_instructions"]["reading"].startswith("cheap (equivalence"))
        self.assertIn("idle-state or frequency effect", a["excess_cycles"]["label"])
        self.assertEqual(a["recovery"]["reading"], "t95 with its interval")  # censored events: never "within"
        self.assertIn("6 of 12 events censored", a["recovery"]["settled_reading"])
        # the R N N R slots; a null after a real slot carries extra cycles
        es = []
        for k, null in enumerate([False, True, True, False]):
            es.append({"k": k, "null": null, "complete": True, "excess_cycles": 0.0 if not null else (5.0 if k == 1
                                                                                                    else 0.0),
                       "excess_instructions": 0.0, "peak_worker_max_over_mean": 1.0, "peak_dev_pct": 0.0,
                       "t95_s": 1.0})
        co = events.across_instances([{"name": "c%d" % i, "estimands": [dict(e, excess_cycles=e["excess_cycles"] + 0.01
                                                                              * i) for e in es]}
                                      for i in range(6)])["carry_over"]
        self.assertEqual(co["reading"], "spacing too short: null after real differs from null after null")

    def test_real_mode_and_between(self):
        reals = [inst("r%d" % i, [100.0 + i, 101.0], []) for i in range(8)]
        nulls = [{"name": "n%d" % i, "estimands": [dict(e, null=True) for e in inst("x", [1.0 * i, 0.0],
                                                                                    [])["estimands"]]}
                 for i in range(8)]
        a = events.across_instances(reals, mode="real")
        self.assertFalse(a["null_subtracted"])
        with self.assertRaises(ValueError):
            events.across_instances(reals[:2] + nulls[:1], mode="real")
        b = events.between_instances(reals, nulls)
        self.assertEqual(b["excess_cycles"]["reading"], "detected")
        self.assertTrue(events.between_instances(reals[:7], nulls)["excess_cycles"]["reading"].startswith(
            "Not resolved"))


if __name__ == "__main__":
    unittest.main()
