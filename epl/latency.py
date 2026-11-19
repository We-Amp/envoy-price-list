"""Run L (flush latency): the analysis definitions as pure functions. Used by the leg (its
gates), by lat_table.py (the result) and by the tests, on the same inputs: the probe log
(latprobe.py), the thread series of the leg (statsrow.ThreadSampler) and the window.

Clock: every time here is CLOCK_MONOTONIC of the one box, in seconds (the probe's ns / 1e9).

A flush window is a burst of the main-thread series, [start, end]. A probe is classed by its
intended send time ts (guard g):
  IN     start + g <= ts <= end - g           (whole bursts inside the used span only)
  ONSET  start - g <= ts <= start + onset     (overlaps IN by design, never pooled with it)
  POST   end - g < ts <= end + post           (reported, in neither side)
  OUT    inside the used span and outside [start - g, end + post] of every burst, whole or not
Probes whose intended time falls in a recorded loop gap of the probe are dropped and counted.
Latency is done - intended, in microseconds.
"""

import bisect
import gzip
import json
import math

DEFAULTS = {"guard_s": 0.02, "onset_s": 0.05, "post_s": 0.25, "edge_s": 0.5, "interval_s": 10.0,
            "sham_step_s": 0.5, "admin_slow_ms": 20.0, "admin_widen_s": 0.06}


def params(cfg=None):
    p = dict(DEFAULTS)
    p.update({k: v for k, v in (cfg or {}).items() if k in DEFAULTS})
    return p


# ---------------------------------------------------------------- inputs

def load_probe(path):
    """{meta, rows, end} of a probe log; `end` is None when the probe did not finish its file."""
    meta, rows, end = None, [], None
    with gzip.open(path, "rt") as f:
        for line in f:
            x = json.loads(line)
            if isinstance(x, list):
                rows.append(x)
            elif "meta" in x:
                meta = x
            elif "end" in x:
                end = x["end"]
    return {"meta": meta, "rows": rows, "end": end}


def load_series(path):
    """The thread series a loaded leg saved (main/<leg>.json.gz): {main_tid, period_s, missing,
    threads {tid: {comm, cpus}}, series {tid: [[t, run ns, wait ns]]}, bursts}, tids as ints."""
    with gzip.open(path, "rt") as f:
        d = json.load(f)
    d["series"] = {int(k): v for k, v in (d.get("series") or {}).items()}
    d["threads"] = {int(k): v for k, v in (d.get("threads") or {}).items()}
    return d


def pct(sorted_vals, q):
    """Nearest-rank quantile of a sorted list (None when empty)."""
    n = len(sorted_vals)
    if not n:
        return None
    return sorted_vals[min(n - 1, max(0, int(math.ceil(q * n)) - 1))]


def stats_of(lat_us):
    """n, p50, p90, p99, max (us), share over 2 ms, counts over 20 ms and over 100 ms."""
    v = sorted(lat_us)
    n = len(v)
    if not n:
        return {"n": 0}
    return {"n": n, "p50": pct(v, 0.5), "p90": pct(v, 0.9), "p99": pct(v, 0.99), "max": v[-1],
            "share_over_2ms": (n - bisect.bisect_right(v, 2000.0)) / float(n),
            "over_20ms": n - bisect.bisect_right(v, 20000.0), "over_100ms": n - bisect.bisect_right(v, 100000.0)}


def in_gap(ns, gaps, starts=None):
    """Whether an intended time (ns) falls in a recorded loop gap (from, to]."""
    starts = starts if starts is not None else [g[0] for g in gaps]
    i = bisect.bisect_left(starts, ns) - 1
    return i >= 0 and gaps[i][0] < ns <= gaps[i][1]


def data_points(rows, a, b, gaps, stream="d"):
    """Probes of one stream with an intended time in [a, b] (s), answered and outside every loop
    gap: ([(ts s, latency us, connection)] sorted by ts, {dropped_for_gap, unanswered, total})."""
    gaps = sorted(gaps or [])
    starts = [g[0] for g in gaps]
    out, dropped, unanswered, total = [], 0, 0, 0
    for r in rows:
        if r[0] != stream:
            continue
        ts = r[3] / 1e9
        if ts < a or ts > b:
            continue
        total += 1
        if gaps and in_gap(r[3], gaps, starts):
            dropped += 1
            continue
        if r[5] is None:
            unanswered += 1
            continue
        out.append((ts, (r[5] - r[3]) / 1e3, r[1]))
    out.sort()
    return out, {"dropped_for_gap": dropped, "unanswered": unanswered, "total": total}


# ---------------------------------------------------------------- windows and slices

def used_span(t0, t1, p):
    return (t0 + p["edge_s"], t1 - p["edge_s"])


def whole_bursts(bursts, span):
    """The bursts wholly inside the used span, as [(start, end)]."""
    a, b = span
    return [(x["start_t"], x["end_t"]) for x in bursts if x["start_t"] >= a and x["end_t"] <= b]


def all_windows(bursts):
    return [(x["start_t"], x["end_t"]) for x in bursts]


def _merge(iv):
    out = []
    for lo, hi in sorted(iv):
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def slice_ranges(ts, focus, exclude, span, p):
    """Index ranges into the sorted intended times `ts` for the slices of `focus` windows.
    `exclude`: every window whose zone [start - g, end + post] is no OUT time (the focus
    windows and any other burst). Returns {in, onset, post, out: [(i0, i1)]}."""
    a, b = span
    g, on, post = p["guard_s"], p["onset_s"], p["post_s"]
    L, R = bisect.bisect_left, bisect.bisect_right
    out = {"in": [], "onset": [], "post": [], "out": []}
    for s, e in focus:
        if e - g >= s + g:
            out["in"].append((L(ts, max(a, s + g)), R(ts, min(b, e - g))))
        out["onset"].append((L(ts, max(a, s - g)), R(ts, min(b, s + on))))
        out["post"].append((R(ts, max(a, e - g)), R(ts, min(b, e + post))))
    lo, lo_open = a, False
    for zs, ze in _merge([(s - g, e + post) for s, e in exclude]):
        if ze < lo:
            continue
        if zs > b:
            break
        if zs > lo:
            i0 = R(ts, lo) if lo_open else L(ts, lo)
            i1 = L(ts, zs)
            if i1 > i0:
                out["out"].append((i0, i1))
        lo, lo_open = ze, True
    if lo < b or (lo == b and not lo_open):
        i0 = R(ts, lo) if lo_open else L(ts, lo)
        i1 = R(ts, b)
        if i1 > i0:
            out["out"].append((i0, i1))
    for k in ("in", "onset", "post"):
        out[k] = [(i0, i1) for i0, i1 in out[k] if i1 > i0]
    return out


def classify(t, focus, exclude, span, p):
    """The slices one intended time belongs to (a set of in, onset, post, out), by the same rules
    as slice_ranges; an empty set = in no slice (outside the span, or in a guard or a partial
    burst)."""
    r = slice_ranges([t], focus, exclude, span, p)
    return {k for k, v in r.items() if v}


def _take(vals, ranges):
    out = []
    for i0, i1 in ranges:
        out.extend(vals[i0:i1])
    return out


def group_arrays(points, groups):
    """{group: (ts list, latency list)} from sorted points and {group: set of connections or None}."""
    out = {}
    for name, conns in groups.items():
        sel = [x for x in points if conns is None or x[2] in conns]
        out[name] = ([x[0] for x in sel], [x[1] for x in sel])
    return out


def slice_stats(arrays, focus, exclude, span, p):
    """{group: {slice: stats}} for one set of focus windows."""
    out = {}
    for name, (ts, lat) in arrays.items():
        r = slice_ranges(ts, focus, exclude, span, p)
        out[name] = {k: stats_of(_take(lat, r[k])) for k in ("in", "onset", "post", "out")}
    return out


METRICS = ("p99", "p50", "share_over_2ms")


def _diff(x, y, m):
    if not x or not y or x.get(m) is None or y.get(m) is None:
        return None
    return x[m] - y[m]


def contrasts(sl):
    """The per-leg contrasts from slice_stats: L1 = IN - OUT on all connections, L2 = ONSET -
    OUT on all, L3 = (IN - OUT on the connections of the worker on the shared CPU) - (the same
    on the other workers' connections); each at p99, p50 (us) and share over 2 ms. `out_*`:
    the OUT values the percentages refer to."""
    out = {}
    for m in METRICS:
        al = sl.get("all") or {}
        out["L1_" + m] = _diff(al.get("in"), al.get("out"), m)
        out["L2_" + m] = _diff(al.get("onset"), al.get("out"), m)
        c0 = _diff((sl.get("cpu0") or {}).get("in"), (sl.get("cpu0") or {}).get("out"), m)
        ot = _diff((sl.get("others") or {}).get("in"), (sl.get("others") or {}).get("out"), m)
        out["L3_" + m] = None if c0 is None or ot is None else c0 - ot
        out["out_" + m] = (al.get("out") or {}).get(m)
    return out


def sham_shifts(whole, exclude, span, p):
    """Admissible sham shifts: [(s, [(start + s, end + s)])] for s on the step grid up to one
    interval. The leg's whole flush windows are shifted together; a shifted window that leaves
    the used span (with its POST zone) is dropped, at most one may be; no remaining sham
    window's zone [start - g, end + post] may touch a real burst's zone."""
    a, b = span
    g, post, step = p["guard_s"], p["post_s"], p["sham_step_s"]
    real = _merge([(s - g, e + post) for s, e in exclude])
    out = []
    if not whole:
        return out
    k = 1
    while k * step < p["interval_s"] - 1e-9:
        s = k * step
        k += 1
        sh = [(x + s, y + s) for x, y in whole if y + s + post <= b and x + s - g >= a]
        if len(sh) < max(1, len(whole) - 1):
            continue
        if any(lo - g <= ze and hi + post >= zs for lo, hi in sh for zs, ze in real):
            continue
        out.append((s, sh))
    return out


def analyse_leg(points, groups, bursts, t0, t1, cfg=None, sham=True):
    """Slices, contrasts and the sham contrasts of one leg. points: data_points(...)[0];
    groups: {all: None, cpu0: {conns}, others: {conns}}; bursts: find_bursts of the main thread."""
    p = params(cfg)
    span = used_span(t0, t1, p)
    whole, allw = whole_bursts(bursts, span), all_windows(bursts)
    arrays = group_arrays(points, groups)
    sl = slice_stats(arrays, whole, allw, span, p)
    out = {"span": list(span), "whole": [list(w) for w in whole], "slices": sl, "contrasts": contrasts(sl)}
    if sham:
        out["sham"] = {}
        for s, sh in sham_shifts(whole, allw, span, p):
            out["sham"]["%.1f" % s] = contrasts(slice_stats(arrays, sh, allw + sh, span, p))
    return out


# ---------------------------------------------------------------- the leg's gates

def flush_record(bursts, t0, t1, p):
    """Flush windows of the leg: counts, lengths and the grid of their starts."""
    span = used_span(t0, t1, p)
    whole = whole_bursts(bursts, span)
    # a burst the series begins inside has no start: left out of the grid
    starts = [b["start_t"] for b in bursts if b.get("start_i", 1) > 0]
    diffs = [y - x for x, y in zip(starts, starts[1:])]
    walls = sorted(e - s for s, e in whole)
    return {"bursts_window": len(bursts), "whole": len(whole), "starts": len(starts),
            "grid_max_error_s": round(max(abs(d - p["interval_s"]) for d in diffs), 4) if diffs else None,
            "wall_s_max": round(walls[-1], 4) if walls else None,
            "wall_s_p50": round(walls[len(walls) // 2], 4) if walls else None,
            "whole_windows": [[round(s - t0, 4), round(e - t0, 4)] for s, e in whole]}


def clock_record(rows, bursts, t0, t1, harness_pairs, probe_pairs, stop_ns, p):
    """The two independent flush signals against each other. pair_error_ms: the largest
    difference between (time - monotonic) of any harness pair and any probe pair. Admin probes
    slower than `admin_slow_ms` with an intended time in the used span: how many lie outside
    every burst widened by `admin_widen_s`; and how many whole bursts hold none."""
    span = used_span(t0, t1, p)
    whole, allw = whole_bursts(bursts, span), all_windows(bursts)
    w = p["admin_widen_s"]
    offs_h = [x["time_ns"] - x["monotonic_ns"] for x in harness_pairs if x]
    offs_p = [x["time_ns"] - x["monotonic_ns"] for x in probe_pairs if x]
    out = {"pair_error_ms": round(max(abs(h - q) for h in offs_h for q in offs_p) / 1e6, 4)
           if offs_h and offs_p and len(offs_p) >= 2 else None}
    slow = []
    n = 0
    for r in rows:
        if r[0] != "a":
            continue
        ts = r[3] / 1e9
        if ts < span[0] or ts > span[1]:
            continue
        n += 1
        # an unanswered probe waited at least until the probe stopped
        end = r[5] if r[5] is not None else stop_ns
        if end is not None and (end - r[3]) / 1e6 > p["admin_slow_ms"]:
            slow.append(ts)
    outside = [t for t in slow if not any(s - w <= t <= e + w for s, e in allw)]
    empty = [1 for s, e in whole if not any(s - w <= t <= e + w for t in slow)]
    out.update(admin_in_span=n, admin_slow=len(slow), admin_slow_outside=len(outside),
               bursts_without_slow_admin=len(empty) if n else None)
    return out


def sampler_record(series, t0, t1, period_s, missing):
    """Completeness of the thread series: the worst thread's share of the expected samples and
    its largest gap between samples."""
    expected = (t1 - t0) / period_s
    share, gap = None, None
    for tid, s in series.items():
        sh = len(s) / expected if expected > 0 else 0.0
        g = max([y[0] - x[0] for x, y in zip(s, s[1:])] or [float("inf")])
        share = sh if share is None else min(share, sh)
        gap = g if gap is None else max(gap, g)
    return {"threads": len(series), "missing": missing, "expected": int(round(expected)),
            "share": round(share, 4) if share is not None else None,
            "max_gap_ms": round(gap * 1e3, 3) if gap not in (None, float("inf")) else None}


def lateness_record(rows, t0, t1):
    """Probe headroom on the data stream in the window: lateness = sent - max(intended, the
    moment the connection became free), p99 (ms) and the share over 1 ms."""
    last_done = {}
    late = []
    for r in rows:
        if r[0] != "d":
            continue
        free = last_done.get(r[1])
        if r[5] is not None:
            last_done[r[1]] = r[5]
        ts = r[3] / 1e9
        if ts < t0 or ts >= t1 or r[4] is None:
            continue
        late.append((r[4] - max(r[3], free or 0)) / 1e6)
    late.sort()
    n = len(late)
    return {"n": n, "p99_ms": round(pct(late, 0.99), 4) if n else None, "max_ms": round(late[-1], 4) if n else None,
            "over_1ms_share": (n - bisect.bisect_right(late, 1.0)) / float(n) if n else None}


def probe_record(probe, summary, t0, t1, cfg):
    """Counts of the probe against its plan: data requests with an intended time in the window
    against rate x window, unanswered, errors, statuses, loop gaps, the control stream."""
    rows = probe["rows"]
    end = probe.get("end") or {}
    gaps = end.get("gaps")
    events = end.get("events")
    rate = float(cfg["data_conns"]) * float(cfg["data_hz"])
    d = [r for r in rows if r[0] == "d"]
    inw = [r for r in d if t0 <= r[3] / 1e9 < t1]
    out = {"finished": probe.get("end") is not None,
           "data_rate": rate, "data_in_window": len(inw), "data_expected": round(rate * (t1 - t0), 1),
           "data_count_error": round(abs(len(inw) - rate * (t1 - t0)), 1),
           "data_unanswered": sum(1 for r in d if r[5] is None),
           "data_non200": sum(1 for r in d if r[5] is not None and r[6] != 200),
           "data_connections_used": len({r[1] for r in inw}),
           "drained": ((summary or {}).get("run") or {}).get("drained")}
    if events is not None:
        out["data_errors"] = sum(1 for e in events if e.get("stream") == "d")
        out["control_errors"] = sum(1 for e in events if e.get("stream") == "c")
        out["admin_errors"] = sum(1 for e in events if e.get("stream") == "a")
    if gaps is not None:
        out["loop_gaps_window"] = sum(1 for g in gaps if g[1] / 1e9 >= t0 and g[0] / 1e9 <= t1)
        out["loop_gaps_total"] = len(gaps)
        _, cnt = data_points(rows, t0, t1, gaps)
        out["gap_dropped_share"] = cnt["dropped_for_gap"] / float(cnt["total"]) if cnt["total"] else None
    out["lateness"] = lateness_record(rows, t0, t1)
    cpts, ccnt = data_points(rows, t0, t1, gaps or [], "c")
    cs = stats_of([x[1] for x in cpts])
    out["control"] = {"n": cs["n"], "unanswered": ccnt["unanswered"],
                      "non200": sum(1 for r in rows if r[0] == "c" and r[5] is not None and r[6] != 200),
                      "p50_us": cs.get("p50"), "p99_us": cs.get("p99"), "max_us": cs.get("max")}
    a = [r for r in rows if r[0] == "a" and t0 <= r[3] / 1e9 < t1]
    out["admin"] = {"n": len(a), "unanswered": sum(1 for r in a if r[5] is None),
                    "non200": sum(1 for r in a if r[5] is not None and r[6] != 200)}
    return out


def map_record(summary, workers, per_worker, cpu0):
    """The connection map of the probe as gate fields, and the connection groups."""
    mp = (summary or {}).get("map") or {}
    conns = mp.get("connections") or []
    counts = [int(v) for v in (mp.get("per_worker") or {}).values()]
    out = {"ok": bool(mp.get("ok")), "workers": mp.get("workers_found"), "opens": mp.get("opens"),
           "connections": len(conns),
           "per_worker_min": min(counts) if counts else None, "per_worker_max": max(counts) if counts else None,
           "min_margin": mp.get("min_margin") if conns else None,
           "unchanged_at_end": ((summary or {}).get("map_end") or {}).get("unchanged"),
           # every owner allowed on exactly one CPU, the CPUs all different
           "one_cpu_each": bool(conns) and all(str(c.get("cpus", "")).isdigit() for c in conns)
           and len({c["cpus"] for c in conns}) == int(workers),
           "want_per_worker": int(per_worker)}
    c0 = {c["conn"] for c in conns if str(c.get("cpus")) == str(cpu0)}
    out["cpu0_connections"] = len(c0)
    groups = {"all": None, "cpu0": c0, "others": {c["conn"] for c in conns} - c0}
    return out, groups


def worker_record(series, threads, main_tid, bursts, t0, t1, p):
    """Per thread of the series: busy share of the window, and the run-queue wait per second in
    flush and out of flush (IN and OUT as for the probes, by the midpoint of each sample
    interval): the manipulation check of the shared-core shape."""
    span = used_span(t0, t1, p)
    whole, allw = whole_bursts(bursts, span), all_windows(bursts)
    out = {}
    for tid, s in series.items():
        if len(s) < 2:
            continue
        mids = [(x[0] + y[0]) / 2.0 for x, y in zip(s, s[1:])]
        r = slice_ranges(mids, whole, allw, span, p)
        rec = {"comm": (threads.get(tid) or {}).get("comm"), "cpus": (threads.get(tid) or {}).get("cpus"),
               "main": tid == main_tid,
               "busy": round((s[-1][1] - s[0][1]) / 1e9 / (s[-1][0] - s[0][0]), 4) if s[-1][0] > s[0][0] else None}
        for k in ("in", "out"):
            dt = sum(s[i + 1][0] - s[i][0] for i0, i1 in r[k] for i in range(i0, i1))
            dw = sum(s[i + 1][2] - s[i][2] for i0, i1 in r[k] for i in range(i0, i1))
            dr = sum(s[i + 1][1] - s[i][1] for i0, i1 in r[k] for i in range(i0, i1))
            rec["wait_ms_per_s_" + k] = round(dw / 1e6 / dt, 4) if dt > 0 else None
            rec["run_ms_per_s_" + k] = round(dr / 1e6 / dt, 3) if dt > 0 else None
            rec["seconds_" + k] = round(dt, 3)
        out[str(tid)] = rec
    return out


def manipulation(workers, cpu0):
    """S-5: the wait per second of the worker on the shared CPU in flush, over its own out of
    flush and over the largest of the other workers in flush."""
    w0 = [w for w in workers.values() if not w.get("main") and str(w.get("cpus")) == str(cpu0)]
    others = [w for w in workers.values() if not w.get("main") and str(w.get("cpus")) != str(cpu0)]
    if len(w0) != 1 or not others or w0[0].get("wait_ms_per_s_in") is None:
        return {"error": "no single worker on CPU %s with in-flush samples" % cpu0}
    a = w0[0]["wait_ms_per_s_in"]
    b = w0[0].get("wait_ms_per_s_out")
    c = max((w.get("wait_ms_per_s_in") or 0.0) for w in others)
    floor = 1e-4  # 0.1 us of wait per second: a ratio against nothing stays finite
    return {"cpu0_wait_in": a, "cpu0_wait_out": b, "others_wait_in_max": c,
            "in_over_out": round(a / max(b or 0.0, floor), 1), "in_over_others": round(a / max(c, floor), 1)}


def statsd_flushes(marks, used_cg_lines, t_from_ns, t_to_ns):
    """The receiver's own count per flush: counter and gauge lines between consecutive
    server.uptime lines (marks: [monotonic_ns, uptime, c, g, ms, datagrams], cumulative), for
    the marks between two times. max_rel_error: the worst flush against the admin count of
    used counters and gauges; spread: (max - min) / mean over the flushes."""
    ms = [m for m in marks or [] if t_from_ns <= m[0] <= t_to_ns]
    per = [(b[2] + b[3]) - (a[2] + a[3]) for a, b in zip(ms, ms[1:])]
    out = {"marks": len(ms), "flushes": len(per), "cg_per_flush_min": min(per) if per else None,
           "cg_per_flush_max": max(per) if per else None, "used_cg_lines": used_cg_lines}
    if per and used_cg_lines:
        out["max_rel_error"] = max(abs(x - used_cg_lines) for x in per) / float(used_cg_lines)
        mean = sum(per) / float(len(per))
        out["spread"] = (max(per) - min(per)) / mean if mean else None
    return out


def leg_record(probe, summary, series, threads, main_tid, bursts, t0, t1, harness_pairs, sampler_missing, cfg):
    """Everything the leg's gates read, under m["lat"]; a field that cannot be computed is
    absent or None, and its gate then fails."""
    p = params(cfg)
    stop_ns = ((summary or {}).get("run") or {}).get("stop_ns")
    out = {"window_mono": [t0, t1], "params": p}
    out["probe"] = probe_record(probe, summary, t0, t1, cfg)
    out["map"], groups = map_record(summary, cfg["workers"], cfg["per_worker"], cfg["cpu0"])
    out["flush"] = flush_record(bursts, t0, t1, p)
    out["clock"] = clock_record(probe["rows"], bursts, t0, t1, harness_pairs,
                                [(summary or {}).get("clock_start"), (summary or {}).get("clock_end")], stop_ns, p)
    out["sampler"] = sampler_record(series, t0, t1, float(cfg["sample_s"]), sampler_missing)
    out["workers"] = worker_record(series, threads, main_tid, bursts, t0, t1, p)
    out["manipulation"] = manipulation(out["workers"], cfg["cpu0"])
    wk = [w["busy"] for w in out["workers"].values() if not w.get("main") and w.get("busy") is not None]
    out["worker_busy_mean"] = round(sum(wk) / len(wk), 4) if wk else None
    span = used_span(t0, t1, p)
    pts, cnt = data_points(probe["rows"], span[0], span[1], (probe.get("end") or {}).get("gaps") or [])
    an = analyse_leg(pts, groups, bursts, t0, t1, cfg, sham=False)
    out["slices"], out["contrasts"], out["span_counts"] = an["slices"], an["contrasts"], cnt
    return out
