"""Client-bottleneck checks.

The client self-check (the busiest client thread's busy share against a zero-load floor) is dominated by the client's
`poll` idle floor, so it passed in every leg and cannot fail. These checks can:

- **The idle floor per client recipe** (`client_calibration.per_recipe: true`): one zero-load floor leg for every
  distinct client recipe among the arms (binary pin, recipe, lifetime, phases, flags), chosen by the harness, and
  the floor gates required. This reuses the client self-check's calibration legs (experiment.Runner._client_floor) and
  its matching by client signature (leg.above_floor); a leg whose recipe has no good floor fails closed by that name.
- **perf stat on the client with -I and no --timeout** (`measure.client_perf_interval_ms`): per-interval counts
  over the window, the perf process ended by one SIGINT after the window (perf 6.8 refuses --timeout with -I).
  The record carries the window totals under the same keys as the client_perf record, plus
  the busiest interval's client CPUs per client worker (a short client peak that the window average hides). The
  record is ok only when every interval ran unmultiplexed with task-clock and cycles, and the intervals cover the
  window; the optional gate `validity.max_client_perf_interval_cpus_per_worker` bounds the peak.
- **Per-worker sequencer gates** (`validity.max_client_worker_sequencer_blocking`,
  `validity.max_client_worker_callback_ms`): each client worker's own sequencer.blocking count and sequencer.callback
  maximum, read from the worker results of the client's output (in a --phases run every worker's result is its last
  phase's, the measure phase). The self-check's gates read the sum over the workers and the largest maximum, which hide
  which worker was late; these name it. A worker without the statistic, or a worker count other than the planned one,
  fails closed.
- **The split test** lives in the flip-block driver (loop/flipblock.py, flip.kind "split"): the same total
  load from one client process and from two at half the load each, window pairs in one Envoy process; a difference
  in SUT cycles per request beyond flip.split_bound_lp flags the client as the bottleneck. Each of the two processes
  runs half the workers at the same rate and connections per worker, on its own half of cpus.client (so the
  client threads and their CPUs match the one-process arm), and every client process's CPU per worker
  in every window is gated by flip.split_max_client_cpus_per_worker.

- **The per-worker overflow gate** (`validity.client_overflow_gate: "per_worker"`): in **every** `worker_<i>`
  result, `benchmark.pool_overflow` = 0 and `upstream_rq_pending_overflow` = 0. A global zero is not enough (one
  hot worker can hide behind the global sum). Nighthawk omits a zero counter, so a
  worker result that is present but omits one reads 0 **only if** it carries `upstream_rq_total` > 0. A missing
  worker result, a worker count other than the planned one, or an unreadable output fails. The leg record is
  `client_worker_overflow` ({ok, reasons, workers_seen, workers_planned, failed_workers, per_worker}), and every
  failure reason starts with `per-worker overflow:`, so an analysis can count these failures by that prefix. Flip
  windows and screen instances (one flip block each) carry the same record under their client record's
  `worker_overflow`.

Every check is off unless its key is set, so earlier configs and their verdicts are unchanged.
"""

import json
import math
import os
import signal
import subprocess

from . import nighthawk

CLIENT_PERF_EVENTS = "task-clock,cycles,instructions,context-switches"  # leg.CLIENT_PERF_EVENTS (no leg import)
MIN_INTERVAL_MS = 250  # a shorter client perf interval is too noisy for the peak gate

VALIDITY_KEYS = ("max_client_worker_sequencer_blocking", "max_client_worker_callback_ms",
                 "max_client_perf_interval_cpus_per_worker", "client_overflow_gate")

# the per-worker overflow gate: the only value of validity.client_overflow_gate; unset = off
OVERFLOW_GATE = "per_worker"
GO_PREFIX = "per-worker overflow: "
GO_COUNTERS = ("benchmark.pool_overflow", "upstream_rq_pending_overflow")


# ---------------------------------------------------------------- perf -I on the client

def client_perf_interval_cmd(mcfg, perf, pid):
    """perf stat -I on the client PID: measure.client_perf_bin (a plain perf binary) when set, else measure.perf;
    `-I MS` and no --timeout (perf 6.8 refuses the two together). The caller ends it with one SIGINT after the
    window; perf then prints the last (partial) interval."""
    base = [mcfg["client_perf_bin"]] if mcfg.get("client_perf_bin") else list(perf)
    return base + ["stat", "-x", ",", "-e", CLIENT_PERF_EVENTS, "-p", str(pid),
                   "-I", str(int(mcfg["client_perf_interval_ms"]))]


def end_interval_perf(own, p, done):
    """The client's perf -I after the window, on every path. On the normal path (done) it has
    printed and exited after its SIGINT and is only taken out of the registry; otherwise it gets one SIGINT if it still
    runs, up to 10 s to print and exit, then own.stop (SIGTERM, SIGKILL) for one that did not."""
    if not done:
        if p.poll() is None:
            p.send_signal(signal.SIGINT)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    own.stop(p)


def parse_intervals(text):
    """[{t, event: value}] (sorted by t), {event: total}, {event: min running %} from `perf stat -I -x ,` lines
    (<time>,<count>,<unit>,<event>,<run>,<pct>,...). A "<not counted>" or "<not supported>" value leaves the event
    out of its row (the row is then incomplete)."""
    rows, tot, run = {}, {}, {}
    for line in (text or "").splitlines():
        if line.startswith("#"):
            continue
        f = line.split(",")
        if len(f) < 6:
            continue
        try:
            t = float(f[0])
        except ValueError:
            continue
        ev = f[3].strip()
        rows.setdefault(t, {"t": t})
        try:
            v = float(f[1])
            pct = float(f[5]) if f[5].strip() else 100.0
        except ValueError:
            rows[t].setdefault("_uncounted", []).append(ev)
            continue
        rows[t][ev] = v
        tot[ev] = tot.get(ev, 0.0) + v
        run[ev] = min(run.get(ev, 100.0), pct)
    return [rows[t] for t in sorted(rows)], tot, run


def client_perf_interval_record(text, window_s, responses, client_workers, interval_ms, rc=None):
    """The client's perf stat -I over the window. The keys of the client_perf record (raw, running_pct, ok, cpus,
    cpus_per_worker, cycles_per_req, instructions_per_req, ghz) over the whole span, plus the intervals and the
    busiest interval's client CPUs per client worker. ok only when: perf ended on the SIGINT (rc 0, or the SIGINT
    exit), at least one interval, every interval has task-clock and cycles, every counter ran unmultiplexed, and the
    intervals cover the window (to within one interval). Fail closed: anything missing is not ok, with a reason.
    The busiest interval leaves out intervals shorter than half interval_ms (the partial last one after the
    SIGINT); they stay in the totals. cycles_per_req and instructions_per_req divide the counts over the
    whole perf span (the window plus perf's start-up and the SIGINT delay, tens of ms) by the window's responses, so
    they read about 0.1-0.3% high; the cpus figures are normalized by the span."""
    rows, tot, run = parse_intervals(text)
    why = []
    iv = float(interval_ms) / 1000.0
    if rc not in (None, 0, -2, 130):
        why.append("client perf exited %s" % rc)
    if not rows:
        why.append("no client perf intervals")
    span = rows[-1]["t"] if rows else 0.0
    peak, peak_t, prev = None, None, 0.0
    out_rows = []
    for r in rows:
        dt = r["t"] - prev
        prev = r["t"]
        miss = [e for e in ("task-clock", "cycles") if e not in r]
        rec = {"t": round(r["t"], 6), "dt_s": round(dt, 6)}
        if miss or dt <= 0:
            why.append("client perf interval at %.3f s lacks %s" % (r["t"], ", ".join(miss) or "a positive length"))
        else:
            c = r["task-clock"] / 1000.0 / dt
            rec["cpus"] = round(c, 6)
            if client_workers:
                rec["cpus_per_worker"] = round(c / client_workers, 6)
                if dt >= 0.5 * iv and (peak is None or rec["cpus_per_worker"] > peak):
                    peak, peak_t = rec["cpus_per_worker"], rec["t"]
            rec["cycles"] = r["cycles"]
        out_rows.append(rec)
    if any(v < 99.99 for v in run.values()):
        why.append("client perf counters multiplexed (%.2f%% running)" % min(run.values()))
    if rows and span < float(window_s) - iv - 1e-6:
        why.append("client perf intervals cover %.3f s of the %.3f s window" % (span, float(window_s)))
    tc = tot.get("task-clock")
    cpus = tc / 1000.0 / span if tc is not None and span > 0 else None
    return {"raw": tot, "running_pct": run, "ok": not why, "reasons": why, "cpus": cpus,
            "cpus_per_worker": cpus / client_workers if cpus is not None and client_workers else None,
            "cycles_per_req": tot["cycles"] / responses if "cycles" in tot and responses else None,
            "instructions_per_req": tot["instructions"] / responses if "instructions" in tot and responses else None,
            "ghz": tot["cycles"] / (tc / 1000.0) / 1e9 if tc and "cycles" in tot else None,
            "interval_ms": int(interval_ms), "intervals": out_rows, "n_intervals": len(rows), "span_s": span,
            "peak_interval_cpus_per_worker": peak, "peak_interval_t": peak_t,
            "peak_excludes": "intervals shorter than half interval_ms", "stopped_by": "SIGINT after the window "
                                                                                    "(no --timeout)"}


# ---------------------------------------------------------------- per-worker sequencer statistics

def worker_sequencer(path):
    """{worker result name: {blocking_count, blocking_max_us, callback_count, callback_max_us}} from a Nighthawk
    output file: every worker result (not "global", not a phase result); a single-worker run has only the global
    result, which stands for its worker. A statistic the worker does not carry is absent from its entry. Read here,
    beside parse_output (whose dict stays as it was for every recorded output)."""
    with open(path) as f:
        d = json.load(f)
    plain = [r for r in d.get("results") or [] if not nighthawk.is_phase_result(r)]
    workers = [r for r in plain if r.get("name") != "global"] or [r for r in plain if r.get("name") == "global"]
    return {r["name"]: nighthawk._seq_stats(r) for r in workers}


def worker_sequencer_check(per_worker, workers, max_blocking=None, max_callback_ms=None):
    """The per-worker gates. Fail closed: the planned worker count must match the worker results, and each gated
    statistic must be present in every worker. {ok, reasons, workers_seen, worst_blocking, worst_callback_ms}."""
    why = []
    per_worker = per_worker or {}
    if workers is not None and len(per_worker) != int(workers):
        why.append("client per-worker sequencer statistics for %d workers, planned %d" % (len(per_worker),
                                                                                         int(workers)))
    wb = wc = None
    for name in sorted(per_worker):
        s = per_worker[name] or {}
        if max_blocking is not None:
            v = s.get("blocking_count")
            if v is None:
                why.append("client %s: no sequencer.blocking statistic" % name)
            else:
                wb = v if wb is None else max(wb, v)
                if v > max_blocking:
                    why.append("client %s: sequencer blocked %d times (limit %d per worker)" % (name, v,
                                                                                             max_blocking))
        if max_callback_ms is not None:
            v = s.get("callback_max_us")
            if v is None:
                why.append("client %s: no sequencer.callback maximum" % name)
            else:
                wc = v / 1000.0 if wc is None else max(wc, v / 1000.0)
                if v > max_callback_ms * 1000.0:
                    why.append("client %s: sequencer.callback max %.3f ms over %.3f ms" % (name, v / 1000.0,
                                                                                         max_callback_ms))
    return {"ok": not why, "reasons": why, "workers_seen": len(per_worker), "worst_blocking": wb,
            "worst_callback_ms": wc, "per_worker": per_worker}


def worker_overflow(path):
    """{worker result name: {counter: value or None, "upstream_rq_total": value or None}} from a Nighthawk output
    file, for the per-worker overflow gate: every worker result (not "global", not a phase result). Unlike
    worker_sequencer, a run with no worker result gives {} (the gate is planned for several workers, so the global
    result never stands in for one)."""
    with open(path) as f:
        d = json.load(f)
    out = {}
    for r in d.get("results") or []:
        if nighthawk.is_phase_result(r) or r.get("name") == "global":
            continue
        cs = {c["name"]: int(c["value"]) for c in r.get("counters") or []}
        out[r["name"]] = {k: cs.get(k) for k in GO_COUNTERS + ("upstream_rq_total",)}
    return out


def overflow_check(per_worker, workers):
    """The per-worker overflow gate over the per-worker counters (worker_overflow). Fail closed: the planned worker
    count must equal the worker results, and each is named worker_<i>; per worker both counters 0, an absent counter 0
    only when the worker's upstream_rq_total > 0. {ok, reasons, workers_seen, workers_planned, failed_workers,
    per_worker}."""
    why, bad = [], []
    per_worker = per_worker or {}
    want = None if workers is None else int(workers)
    if want is None:
        why.append(GO_PREFIX + "no planned client worker count")
    elif len(per_worker) != want:
        why.append(GO_PREFIX + "client worker results for %d workers, planned %d" % (len(per_worker), want))
    elif sorted(per_worker) != sorted("worker_%d" % i for i in range(want)):
        why.append(GO_PREFIX + "client worker results named %s, planned worker_0..worker_%d" % (sorted(per_worker),
                                                                                              want - 1))
    for name in sorted(per_worker, key=lambda n: (len(n), n)):
        w = per_worker[name] or {}
        rq = w.get("upstream_rq_total")
        for k in GO_COUNTERS:
            v = w.get(k)
            if v is None and not (rq is not None and rq > 0):
                why.append(GO_PREFIX + "client %s: %s absent and no requests sent (upstream_rq_total %s): not "
                           "readable as 0" % (name, k, rq))
                bad.append(name)
            elif v:
                why.append(GO_PREFIX + "client %s: %s %d" % (name, k, v))
                bad.append(name)
    return {"ok": not why, "reasons": why, "workers_seen": len(per_worker), "workers_planned": want,
            "failed_workers": sorted(set(bad), key=lambda n: (len(n), n)), "per_worker": per_worker}


def overflow_gate_on(vcfg):
    """Whether this validity config turns the per-worker overflow gate on."""
    return (vcfg or {}).get("client_overflow_gate") == OVERFLOW_GATE


def leg_worker_overflow(path, workers):
    """The per-worker overflow record of one client output, or a failed record naming the read failure."""
    try:
        pw = worker_overflow(path)
    except (OSError, ValueError, KeyError, TypeError) as ex:
        return {"ok": False, "reasons": [GO_PREFIX + "client output unreadable: %s" % ex], "workers_seen": 0,
                "workers_planned": workers, "failed_workers": [], "per_worker": {}}
    return overflow_check(pw, workers)


def gates_on(vcfg):
    """Whether this validity config turns a per-worker sequencer gate on."""
    v = vcfg or {}
    return v.get("max_client_worker_sequencer_blocking") is not None or \
        v.get("max_client_worker_callback_ms") is not None


def leg_worker_sequencer(path, workers, vcfg):
    """The leg's per-worker record, or a not-ok record naming the read failure."""
    try:
        pw = worker_sequencer(path)
    except (OSError, ValueError, KeyError, TypeError) as ex:
        return {"ok": False, "reasons": ["client output unreadable for the per-worker sequencer: %s" % ex]}
    return worker_sequencer_check(pw, workers, (vcfg or {}).get("max_client_worker_sequencer_blocking"),
                                  (vcfg or {}).get("max_client_worker_callback_ms"))


def validity_reasons(m, c):
    """The client-bottleneck leg gates (validity.client_checks calls this): fail closed when a gate is on and its record
    is missing or not ok."""
    reasons = []
    if gates_on(c):
        rec = m.get("client_worker_sequencer")
        if rec is None:
            reasons.append("no client per-worker sequencer record (gate on)")
        elif not rec.get("ok"):
            reasons.append("client per-worker sequencer: %s" % "; ".join(rec.get("reasons") or ["?"]))
    lim = c.get("max_client_perf_interval_cpus_per_worker")
    if lim is not None:
        cp = m.get("client_perf") or {}
        v = cp.get("peak_interval_cpus_per_worker")
        if "interval_ms" not in cp:
            reasons.append("no client perf -I record (validity.max_client_perf_interval_cpus_per_worker is set)")
        elif v is None:
            reasons.append("client perf busiest interval not measured")
        elif v > lim:
            reasons.append("client perf busiest interval %.3f CPUs per client worker (limit %.3f)" % (v, lim))
    if overflow_gate_on(c):
        rec = m.get("client_worker_overflow")
        if rec is None:
            reasons.append(GO_PREFIX + "no per-worker overflow record (gate on)")
        elif not rec.get("ok"):
            reasons += list(rec.get("reasons") or [GO_PREFIX + "?"])
    return reasons


# ---------------------------------------------------------------- the idle floor per client recipe

def recipe_key(exp, arm):
    """A plan-time identity of an arm's client recipe: its client binary and pin, the experiment's client settings
    with the arm's recipe keys over them, and the arm's own client flags. Two arms with the same key send the same
    client signature on every shape; two keys may still give one signature (an extra floor, never a missing one)."""
    from .experiment import arm_client_cfg, client_pin
    acl = arm.get("client") if isinstance(arm.get("client"), dict) else {}
    return json.dumps({"pin": list(client_pin(exp, arm)), "cfg": arm_client_cfg(exp, arm),
                       "arm": {k: acl[k] for k in sorted(acl) if k not in ("binary", "md5")}},
                      sort_keys=True, default=str)


def recipe_arms(exp):
    """One arm per distinct client recipe, in arm order (the first arm of each recipe)."""
    seen, out = set(), []
    for a in exp.get("arms") or []:
        k = recipe_key(exp, a)
        if k not in seen:
            seen.add(k)
            out.append(a)
    return out


def config_errors(exp):
    """validate's client-bottleneck checks; nothing for a config that uses none of their keys."""
    errs = []
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    cc = exp.get("client_calibration")
    v = exp.get("validity") or {}
    ms = exp.get("measure") or {}
    if isinstance(cc, dict) and "per_recipe" in cc:
        if cc["per_recipe"] is not True:
            errs.append("client_calibration.per_recipe takes true")
        else:
            arms = {a.get("name") for a in exp.get("arms") or []}
            want = cc.get("arm")
            if want is not None:
                want = {want} if isinstance(want, str) else set(want or [])
                have = {recipe_key(exp, a) for a in exp.get("arms") or [] if a.get("name") in want}
                lack = [a.get("name") for a in recipe_arms(exp) if recipe_key(exp, a) not in have]
                if lack and want <= arms:
                    errs.append("client_calibration.per_recipe: no floor arm for the client recipe of %s (name one "
                                "arm per recipe, or leave client_calibration.arm out)" % lack)
            if v.get("max_client_busy_above_floor") is None and v.get("max_client_perf_cpus_above_floor") is None:
                errs.append("client_calibration.per_recipe needs a floor gate (validity.max_client_busy_above_floor "
                            "or validity.max_client_perf_cpus_above_floor): a floor no gate reads checks nothing")
    if "client_perf_interval_ms" in ms:
        iv = ms["client_perf_interval_ms"]
        if not (isinstance(iv, int) and not isinstance(iv, bool) and iv >= MIN_INTERVAL_MS):
            errs.append("measure.client_perf_interval_ms must be whole ms >= %d" % MIN_INTERVAL_MS)
        elif not ms.get("client_perf"):
            errs.append("measure.client_perf_interval_ms needs measure.client_perf true")
        elif iv > 1000 * float(ms.get("window_s", 20)):
            errs.append("measure.client_perf_interval_ms is longer than the window")
    for k in ("max_client_worker_sequencer_blocking",):
        if v.get(k) is not None and not (isinstance(v[k], int) and not isinstance(v[k], bool) and v[k] >= 0):
            errs.append("validity.%s must be a whole number >= 0" % k)
    for k in ("max_client_worker_callback_ms", "max_client_perf_interval_cpus_per_worker"):
        if v.get(k) is not None and not (num(v[k]) and v[k] > 0):
            errs.append("validity.%s must be a number > 0" % k)
    if "client_overflow_gate" in v and v["client_overflow_gate"] not in (None, OVERFLOW_GATE):
        errs.append('validity.client_overflow_gate takes "%s"' % OVERFLOW_GATE)
    if v.get("max_client_perf_interval_cpus_per_worker") is not None and not ms.get("client_perf_interval_ms"):
        errs.append("validity.max_client_perf_interval_cpus_per_worker needs measure.client_perf_interval_ms")
    return errs


# ---------------------------------------------------------------- the split test (flipblock kind "split")

def split_rates(rps, concurrency, connections_per_worker):
    """Per-process settings of the split arm (two client processes at half the load each): (rps
    per process, workers per process). Each process runs half the workers at the same rate per worker and the same
    connections per worker, so the client threads, the connections and the total rate match the one-process arm.
    Raises ValueError when a value does not divide."""
    rps, conc = int(rps), int(concurrency)
    if conc % 2:
        raise ValueError("the split test needs an even client.concurrency (%d): each process runs half" % conc)
    if rps % conc:
        raise ValueError("the split test needs the shape's rps (%d) divisible by client.concurrency (%d)" % (rps, conc))
    return rps // 2, conc // 2


def cpu_halves(cpuset):
    """cpus.client split into two disjoint halves for the split arm's two processes: every contiguous range is cut in
    half, the first halves to process 1 and the second halves to process 2 (20-31,60-71 gives 20-25,60-65 and
    26-31,66-71, so SMT siblings land together). Raises ValueError on a range of odd length."""
    runs = []
    for part in str(cpuset).split(","):
        part = part.strip()
        if not part:
            continue
        lo, _, hi = part.partition("-")
        lo, hi = int(lo), int(hi or lo)
        if (hi - lo + 1) % 2:
            raise ValueError("cpus.client range %s has an odd length: the split test cannot halve it" % part)
        runs.append((lo, hi))
    if not runs:
        raise ValueError("cpus.client is empty")
    fmt = lambda a, b: "%d" % a if a == b else "%d-%d" % (a, b)  # noqa: E731
    one = ",".join(fmt(lo, lo + (hi - lo + 1) // 2 - 1) for lo, hi in runs)
    two = ",".join(fmt(lo + (hi - lo + 1) // 2, hi) for lo, hi in runs)
    return one, two


def proc_cpu_s(pid, proc="/proc"):
    """A process's CPU seconds (utime + stime over all its threads, from /proc/<pid>/stat), or None."""
    try:
        with open(os.path.join(proc, str(pid), "stat")) as f:
            t = f.read()
        fl = t[t.rindex(")") + 2:].split()
        return (int(fl[11]) + int(fl[12])) / float(os.sysconf("SC_CLK_TCK"))
    except (OSError, ValueError, IndexError):
        return None


def client_cpu_record(c0, c1, window_s, workers, limit):
    """One client process's CPU per worker over a window, gated (fail closed when unread)."""
    if c0 is None or c1 is None or window_s <= 0:
        return {"ok": False, "cpus_per_worker": None, "reason": "client process CPU not read"}
    v = (c1 - c0) / window_s / workers
    ok = v <= limit
    return {"ok": ok, "cpus_per_worker": round(v, 6),
            "reason": None if ok else "client process at %.3f CPUs per worker (limit %.3f)" % (v, limit)}


def split_verdict(mean_lp, n, bound_lp, block_valid):
    """The split test's reading: d = 100 ln(c_two / c_one) log points on SUT cycles per request. "client not the
    bottleneck" when |mean| <= bound; "client bottleneck" when |mean| > bound; "not resolved" (fail closed) when the
    block is invalid or fewer than 2 pairs were scored."""
    if not block_valid or mean_lp is None or n < 2:
        return {"reading": "not resolved", "client_bottleneck": None, "pass": False}
    flagged = abs(mean_lp) > bound_lp or math.isnan(mean_lp)
    return {"reading": "client bottleneck" if flagged else "client not the bottleneck",
            "client_bottleneck": flagged, "pass": not flagged}
