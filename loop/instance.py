#!/usr/bin/env python3
"""One screen instance, run as its own process by epl-agentd.

    python3 -I loop/instance.py CONFIG --out DIR [--perf-mode sleep|signal] [--standin STANDIN.json]

One instance is one flip block (loop/flipblock.py, FlipBlock, unchanged): one fresh Envoy, one continuous
client, runtime flips between windows, and flipblock's per-window and per-block validity. What this runner changes:
- each window's perf is `perf stat -I 1000` ended by a sleep workload or by one SIGINT (never `--timeout`, which
  perf 6.8 refuses with -I); the window's totals are the sum of its intervals, and the intervals are kept as the
  per-second CPU series on CLOCK_MONOTONIC;
- a 1 Hz admin sampler runs for the whole instance (the same cadence in every window, A or B);
- ours: the runner's own CPU, every perf's CPU (wait4), and a placement check of our threads against the SUT CPUs
  and their siblings. Any thread of ours there makes the instance invalid.

SIGTERM or SIGHUP stop the block through flipblock's own finally (the client, Envoy, every registered PID; the
ledger is DIR/ledger.jsonl) and leave block.json marked invalid. rc 0 valid, 3 invalid, 2 config refused.
--standin runs the same code against the local stand-ins (loop/standin/): a fake Envoy admin process, a
fake client and a fake perf (tests, and the local end-to-end run).

Two box checks run one instance in a special mode (mutually exclusive; the config is an A/A flip block,
flip.kind "aa", order "AB BA BA AB", 4 pairs; rc 0 when all 8 windows ran, 3 otherwise, 2 refused):
- `--sampler-ab` (the sampler check): the admin sampler is on in the A windows (its W phase-locked reads) and
  off in the B windows (no read inside the window); the sampler's level effect, on minus off, per pair and over the
  4 pairs, is printed "in-process effect, Exploratory" with no line;
- `--perf-ab` (the perf-form check): A windows use flipblock's own whole-window form (`perf stat --timeout W`, no -I),
  B windows the loop's form (`perf stat -I 1000 ... -- sleep W`); it prints cycles per request of each form, the mean
  pair difference (B - A) against the line |mean| < 3 x 0.077 lp, every B window's perf_span_minus_W_ms and
  anchor_end_s - anchor_start_s against 50 ms, the start-to-first-interval offset, rc 0, -p target only and 100%
  running on every event. The PASS/FAIL line is a check printed for the operator, not a gate in the instance."""
import argparse
import json
import os
import resource
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STANDIN = os.path.join(HERE, "standin")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import flipblock as fb  # noqa: E402
import telemetry as tm  # noqa: E402
from epl import leg, sysprobe  # noqa: E402

BASIS = "in-process effect, Exploratory"
SPAN_TOLERANCE_MS = 50.0
AB_ORDER = "AB BA BA AB"  # the sampler and perf-form checks: 4 pairs, counterbalanced
AB_MODES = ("sampler-ab", "perf-ab")
# perf-form check: |mean pair difference| below 3 x 0.077 lp (an in-process A/A noise measured on the example box)
PERF_AB_LINE_LP = 3 * 0.077
PERF_AB_SPAN_MS = 50.0       # perf-form check: every B window's span within 50 ms of W
SPAN_RC = 253  # flipblock reads it as "perf exited 253": the window is invalid


class LoopOps(fb.RealOps):
    """flipblock's RealOps with the window's perf as `perf stat -I` (sleep- or signal-ended) and ours accounted."""

    perf_mode = "sleep"
    placement = staticmethod(tm.thread_placement)

    ab_mode = None  # None, "sampler-ab" or "perf-ab"

    def setup_loop(self, perf_mode, forbidden, ab_mode=None, ab_order=None):
        self.perf_mode = perf_mode
        self.forbidden = set(forbidden)
        self.perf_rows = []
        self.perf_runs = []
        self.violations = []
        self._w = 0
        self._pc = 0
        self.ab_mode = ab_mode
        self.ab_order = list(ab_order or [])

    def _label(self, k):
        """The flip label of window k (1-based), or None outside an A/B mode."""
        return self.ab_order[k - 1] if self.ab_mode and 0 < k <= len(self.ab_order) else None

    def perf_base(self):
        return list(self.exp["measure"]["perf"])

    def tools_cpus(self):
        return self.exp["cpus"]["flip_tools"]

    def perf_cmd(self, pid, events, window_s, interval_ms=None):
        self._pending = float(window_s)
        self._pc += 1
        self._pending_form = "interval"
        if self.ab_mode == "perf-ab" and self._label(self._pc) == "A":
            # the perf-form check's A form: flipblock's own whole-window perf (--timeout, no -I), on the same tools CPUs
            self._pending_form = "timeout"
            t = self.tools_cpus()
            return (["taskset", "-c", str(t)] if t else []) + self.perf_base() + [
                "stat", "-x", ",", "-e", events, "-p", str(int(pid)), "--timeout", str(int(round(window_s * 1000)))]
        return tm.perf_interval_cmd(self.perf_base(), events, pid, window_s, self.tools_cpus(), self.perf_mode)

    def _check_perf(self, p):
        time.sleep(0.2)
        self.violations += self.placement_check([p.pid], "perf")

    def placement_check(self, pids, role):
        return [dict(v, role=role) for v in tm.placement_violations(pids, self.forbidden, self.placement)]

    def _start_perf(self, cmd, **kw):
        # perf through OwnProcesses, so it is in the instance ledger with its start ticks
        return self.own.start(cmd, role="perf", **kw)

    def run_perf(self, cmd, timeout):
        self._w += 1
        W = self._pending
        label = self._label(self._w)
        # the sampler check: the sampler off in the B windows (a lock with no planned read: nothing is read inside the
        # window, and the gap reads start after it as usual)
        reads = 0 if (self.ab_mode == "sampler-ab" and label == "B") else W
        if getattr(self, "sampler", None) is not None:
            self.sampler.lock_window(tm.mono_ns() / 1e9, reads)  # exactly W admin reads inside the window
        if getattr(self, "_pending_form", "interval") == "timeout":
            return self._run_whole_window_perf(cmd, W, timeout, label)
        r = tm.run_perf_window(cmd, W, self.perf_mode, timeout, on_start=self._check_perf, start=self._start_perf,
                               stamp_first=self.ab_mode == "perf-ab")
        if getattr(self, "sampler", None) is not None:
            self.sampler.start_gap(r["t1_ns"] / 1e9 + 0.5)
        try:
            self.own.stop(r["proc"])  # reaped already: only the registry entry goes
        except Exception:  # noqa: BLE001
            pass
        rows, tot, run = tm.parse_intervals(r["text"])
        span = rows[-1]["t"] if rows else None
        # perf's -I times count from its counter enable; anchor them at the reap (the exit latency after the
        # last interval is the smaller one), and keep the before-fork anchor beside it
        anchor_end_ns = r["t1_ns"] - int(span * 1e9) if span else r["t0_ns"]
        self.perf_rows += tm.absolute_rows(rows, anchor_end_ns, window=self._w)
        rec = {"window": self._w, "rc": r["rc"], "rc_raw": r["rc_raw"], "cpu_s": r["cpu_s"], "pid": r["pid"],
               "t0_mono_s": round(r["t0_ns"] / 1e9, 6), "t1_mono_s": round(r["t1_ns"] / 1e9, 6),
               "anchor_start_s": round(r["t0_ns"] / 1e9, 6), "anchor_end_s": round(anchor_end_ns / 1e9, 6),
               "intervals": len(rows), "mode": self.perf_mode,
               "perf_span_s": round(span, 6) if span else None,
               "perf_span_minus_W_ms": round((span - W) * 1000.0, 3) if span else None}
        if self.ab_mode:
            rec.update(label=label, form="interval", cmd=list(cmd), planned_reads=reads)
            if r.get("t_first_line_ns") is not None:
                # the perf-form check: perf's start (before the fork) to the arrival of its first interval line
                rec["start_to_first_interval_ms"] = round((r["t_first_line_ns"] - r["t0_ns"]) / 1e6, 3)
        self.perf_runs.append(rec)
        self.violations += self.placement_check([os.getpid()], "instance-runner")
        if r["rc"] != 0:
            return r["rc"], r["text"]
        if not rows:
            return 255, "no perf intervals: " + r["text"][-400:]
        if abs(span - W) * 1000.0 > getattr(self, "span_tol_ms", SPAN_TOLERANCE_MS):
            # a window whose counting span is off W by more than the tolerance is invalid (flipblock: perf rc)
            rec["reason"] = "perf span %.3f s is %+.1f ms off the %.0f s window" % (span, (span - W) * 1000, W)
            return SPAN_RC, rec["reason"]
        # the totals over perf's own span, scaled to W: the 2xx are scaled to W by flipblock, so both sides of
        # cycles per request cover the same W
        return 0, tm.totals_text({ev: v * W / span for ev, v in tot.items()}, run)


    def _run_whole_window_perf(self, cmd, W, timeout, label):
        """The perf-form check's A window: flipblock's whole-window perf (--timeout), through OwnProcesses (in the
        ledger), its totals passed to flipblock as they are. The reads are counted over perf's run (before the fork to the reap):
        a whole-window perf has no interval anchor."""
        r = tm.run_perf_window(cmd, W, "sleep", timeout, on_start=self._check_perf, start=self._start_perf)
        if getattr(self, "sampler", None) is not None:
            self.sampler.start_gap(r["t1_ns"] / 1e9 + 0.5)
        try:
            self.own.stop(r["proc"])
        except Exception:  # noqa: BLE001
            pass
        self.perf_runs.append({"window": self._w, "rc": r["rc"], "rc_raw": r["rc_raw"], "cpu_s": r["cpu_s"],
                               "pid": r["pid"], "t0_mono_s": round(r["t0_ns"] / 1e9, 6),
                               "t1_mono_s": round(r["t1_ns"] / 1e9, 6), "mode": "timeout", "label": label,
                               "form": "timeout", "cmd": list(cmd), "planned_reads": W,
                               "count_span_s": [round(r["t0_ns"] / 1e9, 6), round(r["t1_ns"] / 1e9, 6)]})
        self.violations += self.placement_check([os.getpid()], "instance-runner")
        return r["rc"], r["text"]


def ab_errors(exp, mode):
    """The refusals of --sampler-ab and --perf-ab: an A/A flip block of 4 pairs in the order AB BA BA AB."""
    if mode is None:
        return []
    if mode not in AB_MODES:
        return ["unknown A/B mode %r" % mode]
    f = exp.get("flip") or {}
    errs = []
    if f.get("kind") != "aa":
        errs.append('--%s needs an A/A flip block (flip.kind "aa")' % mode)
    if " ".join(str(f.get("order", "")).split()) != AB_ORDER:
        errs.append("--%s needs flip.order %r" % (mode, AB_ORDER))
    vals = f.get("values") or {}
    if set(vals) != {"A", "B"} or vals.get("A") != vals.get("B"):
        errs.append("--%s needs flip.values A and B equal (an A/A block)" % mode)
    if mode == "perf-ab" and f.get("perf_interval_ms"):
        errs.append("--perf-ab compares flipblock's whole-window perf: flip.perf_interval_ms must be unset")
    return errs


def _t_summary(xs):
    """mean, SD, the 95% t interval (df n - 1), or {} below 2 values."""
    if len(xs) < 2:
        return {"n": len(xs)}
    from epl import stats
    n = len(xs)
    m = sum(xs) / n
    sd = stats.stdev(xs)
    hw = stats.t_ppf(0.975, n - 1) * sd / n ** 0.5
    return {"n": n, "mean_lp": round(m, 4), "sd_lp": round(sd, 4), "df": n - 1,
            "t_interval_lp": [round(m - hw, 4), round(m + hw, 4)]}


def sampler_ab_summary(res, reads):
    """The sampler check: the admin sampler's level effect, on (A) minus off (B), per pair: d = 100 ln(c_on / c_off),
    which is minus flipblock's pair d (B over A). Printed, Exploratory, no line."""
    pairs = []
    for p in (res.get("summary") or {}).get("pairs") or []:
        if "d_lp" in p:
            pairs.append({"pair": p["pair"], "order": p["order"], "on_minus_off_lp": round(-p["d_lp"], 4)})
    out = {"basis": BASIS, "check": "sampler-ab", "line": "none: printed, Exploratory",
           "definition": "100 ln(cycles per request, sampler on / sampler off); A = on, B = off",
           "pairs": pairs, "reads_per_window": reads, "block_valid": bool(res.get("valid"))}
    out.update(_t_summary([p["on_minus_off_lp"] for p in pairs]))
    return out


def perf_ab_summary(res, perf_runs, events, envoy_pid):
    """The perf-form check: the two perf forms on one warm Envoy (A whole-window --timeout, B -I 1000 -- sleep W)."""
    ws = {w["k"]: w for w in res.get("windows") or []}
    evs = [e for e in str(events).split(",") if e]
    rows, why = [], []
    for r in perf_runs:
        w = ws.get(r["window"]) or {}
        cmd = r.get("cmd") or []
        p_only = cmd.count("-p") == 1 and cmd[cmd.index("-p") + 1] == str(envoy_pid) and not (
            {"-a", "--all-cpus", "-C", "--cpu"} & set(cmd))
        raw = w.get("perf_raw") or {}
        running = w.get("perf_running_pct") or {}
        full = all(e in raw for e in evs) and all(running.get(e) == 100.0 for e in evs)
        row = {"window": r["window"], "label": r.get("label"), "form": r.get("form"), "rc": w.get("perf_rc"),
               "p_target_only": p_only, "events_100pct_running": full,
               "cycles_per_req": (w.get("per_req") or {}).get("cycles_total")}
        if r.get("form") == "interval":
            row.update(perf_span_minus_W_ms=r.get("perf_span_minus_W_ms"),
                       anchor_end_minus_start_ms=round((r["anchor_end_s"] - r["anchor_start_s"]) * 1000.0, 3),
                       start_to_first_interval_ms=r.get("start_to_first_interval_ms"))
        rows.append(row)
        if row["rc"] != 0:
            why.append("window %d: perf rc %s" % (r["window"], row["rc"]))
        if not p_only:
            why.append("window %d: perf not on the -p target only (%s)" % (r["window"], " ".join(cmd)))
        if not full:
            why.append("window %d: not every one of the %d events counted 100%% running" % (r["window"], len(evs)))
    bad_span = [x["window"] for x in rows if x.get("form") == "interval" and (
        x.get("perf_span_minus_W_ms") is None or abs(x["perf_span_minus_W_ms"]) > PERF_AB_SPAN_MS)]
    if bad_span:
        why.append("B windows %s: span off W by more than %.0f ms" % (bad_span, PERF_AB_SPAN_MS))
    # the perf-form check never reads PASS on an invalid block (a rate miss, foreign load or any other
    # flipblock item in a window): the perf items alone do not make the comparison sound
    if not res.get("valid"):
        why.append("block invalid: %s" % "; ".join(str(x) for x in (res.get("reasons") or ["no reason recorded"]))[:300])
    ds = [p["d_lp"] for p in (res.get("summary") or {}).get("pairs") or [] if "d_lp" in p]
    t = _t_summary(ds)
    if len(ds) != len(AB_ORDER.split()):
        why.append("%d of %d pairs measured" % (len(ds), len(AB_ORDER.split())))
    elif abs(t["mean_lp"]) >= PERF_AB_LINE_LP:
        why.append("mean pair difference %.4f lp, not below %.3f lp" % (t["mean_lp"], PERF_AB_LINE_LP))
    per_form = {}
    for form in ("timeout", "interval"):
        c = [x["cycles_per_req"] for x in rows if x.get("form") == form and x.get("cycles_per_req")]
        per_form[form] = round(sum(c) / len(c), 3) if c else None
    out = {"check": "perf-ab", "basis": BASIS,
           "definition": "d = 100 ln(cycles per request, -I 1000 -- sleep W (B) / --timeout W (A)) per pair",
           "line": "|mean d| < %.3f lp (3 x 0.077), every B span within %.0f ms of W, rc 0, -p target only, "
                   "100%% running on the %d events" % (PERF_AB_LINE_LP, PERF_AB_SPAN_MS, len(evs)),
           "anchor_line_ms": PERF_AB_SPAN_MS,
           "anchor_note": "anchor_end_s - anchor_start_s (perf's start to its counter enable) is printed against "
                          "50 ms; it is not part of the line",
           "cycles_per_req_by_form": per_form, "windows": rows, "pairs_d_lp": ds, "block_valid": bool(res.get("valid")),
           "reasons": why, "reading": "PASS" if not why else "FAIL"}
    out.update(t)
    return out


def print_ab(res):
    """The A/B mode's printed result (stdout)."""
    if res.get("sampler_ab"):
        s = res["sampler_ab"]
        print("sampler-ab (%s): sampler on - off = %s lp %s (n %s, df %s); pairs %s; block valid %s; no line" % (
            s["basis"], s.get("mean_lp"), s.get("t_interval_lp"), s.get("n"), s.get("df"),
            [p["on_minus_off_lp"] for p in s["pairs"]], s["block_valid"]))
    if res.get("perf_ab"):
        s = res["perf_ab"]
        print("perf-ab: cycles per request by form %s; mean d (B - A) %s lp %s; %s" % (
            s["cycles_per_req_by_form"], s.get("mean_lp"), s.get("t_interval_lp"), s["line"]))
        for x in s["windows"]:
            if x.get("form") == "interval":
                print("perf-ab: window %d (B): perf_span_minus_W_ms %s (line %.0f), anchor_end - anchor_start %s ms "
                      "(against %.0f), start to first interval %s ms" % (
                          x["window"], x["perf_span_minus_W_ms"], PERF_AB_SPAN_MS, x["anchor_end_minus_start_ms"],
                          PERF_AB_SPAN_MS, x["start_to_first_interval_ms"]))
        print("perf-ab: %s%s" % (s["reading"], "" if not s["reasons"] else " (%s)" % "; ".join(s["reasons"])))


class StandInLoopOps(LoopOps):
    """The box parts replaced by local stand-ins: a fake Envoy (a real child process serving admin), the fake
    client and the fake perf (loop/standin/). No taskset, no /proc, no Envoy binary. The admin reads, the
    POSTs, OwnProcesses, the ledger, the event log, perf's -I path and every verdict are the real code."""

    def __init__(self, exp, run_dir, log, standin):
        self.exp, self.run_dir, self.log = exp, run_dir, log
        self.own = leg.OwnProcesses()
        self.admin_port = exp["envoy"]["admin_port"]
        self.si = standin

    def preflight(self, shape):
        return True, {"stand-in": True}

    def validate_bootstrap(self, path):
        with open(path) as f:
            json.load(f)
        return {"ok": True}

    def start_envoy(self, arm, bootstrap):
        self._elog_f = open(os.path.join(self.run_dir, "logs", "envoy.log"), "w")
        p = self.own.start([sys.executable, "-I", os.path.join(STANDIN, "envoy.py"), "--admin-port",
                            str(self.admin_port), "--params", json.dumps(dict(
                                {"rate": self.exp["shapes"][0]["rps"], "instance": instance_number(self.exp["name"])},
                                **(self.si.get("envoy") or {})))],
                           role="envoy", stdout=self._elog_f, stderr=subprocess.STDOUT)
        if not sysprobe.wait_port("127.0.0.1", self.admin_port, 10.0):
            raise RuntimeError("stand-in envoy admin not up")
        return p

    def stop_envoy(self, p):
        rc = self.own.stop(p)
        self._elog_f.close()
        return rc

    def exe_identity(self, pid, path):
        return {"client_exe_ok": True, "client_exe": path}

    def cpus_ok(self, pid, want):
        return True

    def start_client(self, args, out, err):
        return self.own.start([sys.executable, "-I", os.path.join(STANDIN, "client.py")] + args, role="client",
                              stdout=out, stderr=err)

    def perf_base(self):
        return [sys.executable, "-I", os.path.join(STANDIN, "perf.py"), "--standin-admin", str(self.admin_port)]

    def tools_cpus(self):
        return None

    def sched(self, envoy_pid):
        return 0, {0: 0, 40: 0}, None

    def sut_sets(self):
        return {0}, {40}


def instance_number(name):
    """The instance number from a screen instance's name (scrNN-iKK), for the stand-in's deterministic seed."""
    tail = str(name).rsplit("-i", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def forbidden_cpus(exp):
    sut = sysprobe.parse_cpuset(exp["cpus"]["sut"])
    try:
        sib = sysprobe.siblings_of(sut)
    except Exception:  # noqa: BLE001 - no sysfs topology (not Linux): the SUT CPUs alone
        sib = set()
    return set(sut) | set(sib)


def run_instance(config, out, perf_mode="sleep", standin=None, log=None, span_tol_ms=SPAN_TOLERANCE_MS, ab=None):
    exp, errs = fb.load(config)
    os.makedirs(out, exist_ok=True)
    if not errs:
        errs = ab_errors(exp, ab)
    if errs:
        res = {"valid": False, "reasons": ["config refused: %s" % e for e in errs], "windows": [], "basis": BASIS}
        _write(out, res)
        return res, 2
    logf = open(os.path.join(out, "log.txt"), "a")

    def _log(msg):
        logf.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg))
        logf.flush()
    log = log or _log
    if standin is not None:
        os.makedirs(os.path.join(out, "logs"), exist_ok=True)
        ops = StandInLoopOps(exp, out, log, standin)
    else:
        ops = LoopOps(exp, out, log)
    ops.setup_loop(perf_mode, forbidden_cpus(exp), ab, fb.parse_order(exp["flip"]["order"]) if ab else None)
    ops.span_tol_ms = float(span_tol_ms)
    r0 = resource.getrusage(resource.RUSAGE_SELF)
    sampler = tm.AdminSampler(ops.admin_get).start()
    ops.sampler = sampler
    res = None
    try:
        res = fb.FlipBlock(exp, out, ops, log).run()
    finally:
        samples = sampler.stop()
        if res is None:
            # a signal (SystemExit) went through FlipBlock's own finally: every process it started is stopped
            res = {"name": exp["name"], "valid": False, "reasons": ["aborted: the runner was signalled"],
                   "windows": [], "basis": BASIS, "aborted": True}
        r1 = resource.getrusage(resource.RUSAGE_SELF)
        windows = [{"k": w["k"], "label": w["label"], "t_perf_start": tm.from_py_monotonic(w.get("t_perf_start")),
                    "t_perf_end": tm.from_py_monotonic(w.get("t_perf_end"))} for w in res.get("windows") or []]
        tl = tm.timeline(ops.perf_rows, samples, None, windows)
        # the admin reads inside each window, which must be equal in every window of the instance
        # counted by each read's start inside perf's own span (the span the cycles cover)
        by_window = {r["window"]: tm.reads_in(samples, r["anchor_end_s"], r["anchor_end_s"] + r["perf_span_s"])
                     for r in ops.perf_runs if r.get("perf_span_s")}
        # the perf-form check's whole-window (--timeout) windows: the reads over perf's run
        by_window.update({r["window"]: tm.reads_in(samples, *r["count_span_s"]) for r in ops.perf_runs
                          if r.get("count_span_s")})
        reads = [by_window[k] for k in sorted(by_window)]
        for w in res.get("windows") or []:
            if w["k"] in by_window:
                w["admin_reads_in_window"] = by_window[w["k"]]
        with open(os.path.join(out, "telemetry.json"), "w") as f:
            json.dump(sysprobe.scrub({"basis": BASIS, "timeline": tl, "perf_runs": ops.perf_runs,
                                      "admin_samples": len(samples), "admin_errors": sampler.errors,
                                      "client_snapshots": "not available with the adopted nighthawk_client (no "
                                                          "live output); its end-of-run JSON is in nighthawk/"}),
                      f, indent=1, sort_keys=True)
        ours = {"runner_cpu_s": round((r1.ru_utime + r1.ru_stime) - (r0.ru_utime + r0.ru_stime), 4),
                "perf_cpu_s": round(sum(p["cpu_s"] for p in ops.perf_runs), 4),
                "placement_violations": ops.violations[:20], "forbidden_cpus": sorted(ops.forbidden)}
        res["loop"] = {"basis": BASIS, "perf_mode": perf_mode, "ours": ours, "telemetry": "telemetry.json",
                       "span_tolerance_ms": ops.span_tol_ms,
                       "admin_samples": len(samples), "per_second_rows": len(tl["rows"])}
        res["loop"]["admin_reads_in_window"] = reads
        if ab == "sampler-ab":
            # the sampler check: the planned reads, W in an A window (sampler on) and 0 in a B window (off)
            want = {r["window"]: r.get("planned_reads") for r in ops.perf_runs}
            off = {k: v for k, v in by_window.items() if want.get(k) is not None and round(want[k]) != v}
            if off or not by_window:
                res["valid"] = False
                res.setdefault("reasons", []).append("sampler A/B reads per window not as planned (window: "
                                                     "reads, planned): %s" % {k: (by_window.get(k), want.get(k))
                                                                              for k in off})
        elif len(set(reads)) > 1:
            res["valid"] = False
            res.setdefault("reasons", []).append("admin reads per window differ: %s" % reads)
        if ops.violations:
            res["valid"] = False
            res.setdefault("reasons", []).append("ours on a SUT CPU or a SUT sibling: %s" % ops.violations[:3])
        if res.get("summary"):
            res["summary"]["valid"] = res["valid"]
        if ab == "sampler-ab":
            res["sampler_ab"] = sampler_ab_summary(res, {k: by_window[k] for k in sorted(by_window)})
        elif ab == "perf-ab":
            events = exp["measure"].get("perf_events") or leg.PERF_EVENTS
            res["perf_ab"] = perf_ab_summary(res, ops.perf_runs, events, res.get("envoy_pid"))
        _write(out, res)
        logf.close()
    if ab:
        # a check, not a gate: rc 0 when every planned window ran
        ran = len(res.get("windows") or []) == len(AB_ORDER.replace(" ", "")) and not res.get("aborted")
        return res, 0 if ran else 3
    return res, 0 if res["valid"] else 3


def _write(out, res):
    tmp = os.path.join(out, "block.json.tmp")
    with open(tmp, "w") as f:
        json.dump(sysprobe.scrub(res), f, indent=1, sort_keys=True, default=str)
    os.replace(tmp, os.path.join(out, "block.json"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("config")
    ap.add_argument("--out", required=True)
    ap.add_argument("--perf-mode", choices=tm.PERF_MODES, default="sleep")
    ap.add_argument("--standin", help="a JSON file with the stand-ins' parameters (local tests only)")
    ap.add_argument("--span-tolerance-ms", type=float, default=SPAN_TOLERANCE_MS,
                    help="perf's span may differ from W by this much before the window is invalid (box: 50)")
    ab = ap.add_mutually_exclusive_group()
    ab.add_argument("--sampler-ab", action="store_true",
                    help="the sampler check: the admin sampler on in A windows, off in B windows "
                         "(A/A block, AB BA BA AB)")
    ab.add_argument("--perf-ab", action="store_true",
                    help="the perf-form check: flipblock's --timeout perf in A windows, the loop's -I form in "
                         "B windows")
    a = ap.parse_args(argv)
    mode = "sampler-ab" if a.sampler_ab else "perf-ab" if a.perf_ab else None

    # never read the daemon's MCP channel, whatever a child does
    nul = os.open(os.devnull, os.O_RDONLY)
    os.dup2(nul, 0)
    os.close(nul)

    def _on_term(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGHUP, _on_term)
    signal.signal(signal.SIGINT, _on_term)
    standin = None
    if a.standin:
        with open(a.standin) as f:
            standin = json.load(f)
    elif hasattr(os, "sched_setaffinity"):
        exp, _ = fb.load(a.config)
        os.sched_setaffinity(0, sysprobe.parse_cpuset(exp["cpus"]["flip_tools"]))
    res, rc = run_instance(a.config, a.out, a.perf_mode, standin, span_tol_ms=a.span_tolerance_ms, ab=mode)
    print("%s: valid %s" % (res.get("name"), res["valid"]))
    print_ab(res)
    return rc


if __name__ == "__main__":
    sys.exit(main())
