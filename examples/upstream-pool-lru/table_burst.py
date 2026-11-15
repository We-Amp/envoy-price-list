#!/usr/bin/env python3
"""Tables for the burst-recovery follow-up.

    python3 examples/upstream-pool-lru/table_burst.py RUN_DIR [--json OUT.json] [--include-invalid]

(--include-invalid only for smoke runs: it puts invalid legs into the summaries.)

Reads legs.jsonl and timeline/<leg>.json.gz. Current legs only (the highest attempt
per round, shape and arm); a pair needs both legs valid.

Definitions (fixed before the run):
- intervals: between consecutive 1 s samples; per hop B worker, scheduler run time
  over the interval. Busiest share = busiest worker / all workers; busiest busy =
  busiest worker, of a core.
- pre-burst: intervals that end at or before the pause; post-burst: intervals that
  start at or after the end of the pause.
- T_rec (primary): seconds from the end of the pause to the start of the first
  post-burst interval that begins a run of RUN consecutive intervals with busiest
  share <= 1.2 x even (0.30 for 4 workers). Censored when no such run starts by the
  end of the window (reported as ">X s").
- T_base (secondary): the same with the threshold max(0.30, the leg's pre-burst
  median + 0.02), i.e. back to where that leg was before the pause.
- p99 (exploratory): hop A's downstream_rq_time interval p99, read every second (the
  value changes once per 5 s stats flush; Envoy records this histogram in whole
  milliseconds, so a sub-millisecond steady p99 reads 0). "recovery" = the largest
  value read in the 11 s after the pause, "steady" = the median before it.
- CPU: total cycles per request of both hops over the whole perf window (pre and
  post), paired against mru per round; CPU-seconds of both hops (task-clock).
"""

import gzip
import json
import math
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import stats  # noqa: E402

EVEN = 0.25
THRESH = 1.2 * EVEN
RUN = 10
TAU = 0.34  # between-run A/A spread, pooled over all A/A runs (one SD, %); widens rows under 2%


def load(run_dir):
    cur = {}
    with open(os.path.join(run_dir, "legs.jsonl")) as f:
        for line in f:
            m = json.loads(line)
            if "shape" not in m:
                continue  # re-run markers
            k = (m["shape"], m["round"], m["arm"])
            if k not in cur or m.get("attempt", 0) >= cur[k].get("attempt", 0):
                cur[k] = m
    return cur


def timeline(run_dir, leg_id):
    p = os.path.join(run_dir, "timeline", leg_id + ".json.gz")
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt") as f:
        return json.load(f)


def intervals(samples, key):
    out = []
    for a, b in zip(samples, samples[1:]):
        dt = b["t"] - a["t"]
        wa, wb = a.get(key) or {}, b.get(key) or {}
        ws = sorted(set(wa) & set(wb))
        if dt <= 0 or not ws:
            continue
        d = [(wb[w] - wa[w]) / 1e9 for w in ws]
        tot = sum(d)
        if tot <= 0:
            continue
        out.append({"t0": a["t"], "t1": b["t"], "share_max": max(d) / tot, "share_min": min(d) / tot,
                    "busy_max": max(d) / dt, "busy_sum": tot / dt, "n": len(ws)})
    return out


def first_run(post, t_end_pause, thr):
    for i in range(len(post) - RUN + 1):
        if all(x["share_max"] <= thr for x in post[i:i + RUN]):
            return max(0.0, post[i]["t0"] - t_end_pause), False
    # censored at the last start a full run still fits after
    last = post[-RUN]["t0"] - t_end_pause if len(post) >= RUN else 0.0
    return max(0.0, last), True


def gauge(s, hop, name):
    return (s.get(hop) or {}).get(name)


def hop_b_conns(s):
    b = s.get("b") or {}
    v = [b[k] for k in sorted(b) if k.endswith(".downstream_cx_active") and ".worker_" in k]
    return v


def leg_summary(m, tl):
    b = tl["burst"]
    tp, pause = b["t"], b["pause_ms_actual"] / 1000.0
    te = tp + pause
    s = tl["samples"]
    iv = intervals(s, "b_wrk")
    pre = [x for x in iv if x["t1"] <= tp + 1e-6]
    post = [x for x in iv if x["t0"] >= te - 1e-6]
    base = st.median([x["share_max"] for x in pre]) if pre else None
    t_rec, cens = first_run(post, te, THRESH)
    thr_b = max(THRESH, (base or 0) + 0.02)
    t_base, cens_b = first_run(post, te, thr_b)
    pool = [(x["t"], gauge(x, "a", "cluster.origin.upstream_cx_active")) for x in s]
    pool = [(t, v) for t, v in pool if v is not None]
    pool_pre = [v for t, v in pool if t <= tp]
    pool_post = [(t - te, v) for t, v in pool if t >= te]

    def pool_at(dt):
        c = [v for t, v in pool_post if t >= dt]
        return c[0] if c else None

    opened = [(x["t"], gauge(x, "a", "cluster.origin.upstream_cx_total")) for x in s]
    opened = [(t, v) for t, v in opened if v is not None]
    o_pre = [v for t, v in opened if t <= tp]
    o_post = [v for t, v in opened if t >= te]
    o5 = [v for t, v in opened if t >= te + 5.0]  # the pool's growth is over within a few seconds
    p99 = []
    for x in s:
        q = (x.get("a_rq_time_ms") or {}).get("99")
        if q and q[0] is not None:
            p99.append((x["t"], q[0]))
    p99_pre = [v for t, v in p99 if t <= tp]
    p99_rec = [v for t, v in p99 if te < t <= te + 11.0]
    bc = [hop_b_conns(x) for x in s]
    bc_pre = [c for x, c in zip(s, bc) if x["t"] <= tp and c]
    bc_end = [c for c in bc if c][-1:] or [None]
    pr = m.get("per_req") or {}
    tc = (m.get("perf_raw") or {}).get("task-clock", 0.0) + (m.get("hop2_perf_raw") or {}).get("task-clock", 0.0)
    return {
        "leg": m["leg_id"], "arm": m["arm"], "round": m["round"], "valid": m["verdict"]["valid"],
        "pause_ms": b["pause_ms_actual"], "n_pre": len(pre), "n_post": len(post),
        "share_pre": base, "share_peak": max(x["share_max"] for x in post) if post else None,
        "busy_peak": max(x["busy_max"] for x in post) if post else None,
        "busy_pre": st.median([x["busy_max"] for x in pre]) if pre else None,
        "share_post_end": st.median([x["share_max"] for x in post[-20:]]) if post else None,
        "t_rec": t_rec, "t_rec_censored": cens, "t_base": t_base, "t_base_censored": cens_b, "thr_base": thr_b,
        "pool_pre": st.median(pool_pre) if pool_pre else None,
        "pool_peak": max(v for t, v in pool_post) if pool_post else None,
        "pool_10": pool_at(10), "pool_30": pool_at(30), "pool_60": pool_at(60), "pool_120": pool_at(120),
        "pool_end": pool_post[-1][1] if pool_post else None,
        "cx_opened_burst": (o5[0] - o_pre[-1]) if o5 and o_pre else None,
        "cx_opened_post": (o_post[-1] - o5[0]) if o5 and o_post else None,
        "p99_pre_ms": st.median(p99_pre) if p99_pre else None,
        "p99_rec_ms": max(p99_rec) if p99_rec else None,
        "p99_post_med_ms": med([v for t, v in p99 if t > te + 11.0]),
        "hopb_conns_pre": bc_pre[len(bc_pre) // 2] if bc_pre else None, "hopb_conns_end": bc_end[0],
        "cycles_all": pr.get("cycles_total_all"), "cycles_a": pr.get("cycles_total"),
        "cycles_b": pr.get("cycles_total_hop2"),
        "cpu_s": tc / 1000.0, "p99_whole_us": (m.get("latency_us") or {}).get("p99"),
        "p50_whole_us": (m.get("latency_us") or {}).get("p50"),
        "remote_close": (m.get("sut_stats_delta") or {}).get("cluster.origin.upstream_cx_destroy_remote", 0),
        "non2xx": m.get("sut_non2xx"),
        "series": [{"t": round(x["t0"] - te, 2), "share_max": round(x["share_max"], 4),
                    "busy_max": round(x["busy_max"], 4)} for x in iv],
        "pool_series": [(round(t - te, 2), v) for t, v in pool],
    }


def fmt_t(v, c):
    return (">%.0f" % v) if c else ("%.0f" % v)


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def rng(xs, f="%.2f"):
    xs = [x for x in xs if x is not None]
    return (f + "–" + f) % (min(xs), max(xs)) if xs else "–"


def nz(v):
    return float("nan") if v is None else v


def tau_hw(p):
    if "half_width_pct" not in p or p["n"] < 2:
        return None
    se = p["half_width_pct"] / stats.t_ppf(0.975, p["n"] - 1)
    return 1.96 * math.sqrt(se * se + TAU * TAU)


def main():
    run_dir = sys.argv[1]
    jout = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    cur = load(run_dir)
    exp = json.load(open(os.path.join(run_dir, "experiment.json")))
    arms = [a["name"] for a in exp["arms"]]
    base = exp.get("base_arm", arms[0])
    rows = []
    for (s, r, a), m in sorted(cur.items()):
        tl = timeline(run_dir, m["leg_id"])
        if tl and tl.get("burst") and not tl["burst"].get("error"):
            rows.append(leg_summary(m, tl))
    valid = [x for x in rows if x["valid"] or "--include-invalid" in sys.argv]
    by = {a: [x for x in valid if x["arm"] == a] for a in arms}
    print("# Burst recovery: %s\n" % exp["name"])
    print("Legs: %d current, %d valid. Pause: %s ms (actual, min–max).\n" % (
        len(cur), len(valid), rng([x["pause_ms"] for x in rows], "%.1f")))
    print("## Recovery of hop B's busiest share (threshold %.2f, %d consecutive 1 s intervals)\n" % (THRESH, RUN))
    print("| Arm | legs | pre-burst busiest share, median (range) | peak after | T_rec median (range), s | "
          "recovered by 10 / 30 / 60 s / never | T_base median (range), s | never back to own level | "
          "last 20 s busiest share, median (range) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for a in arms:
        L = by[a]
        if not L:
            continue
        tr = sorted(L, key=lambda x: (x["t_rec_censored"], x["t_rec"]))
        n10 = sum(1 for x in L if not x["t_rec_censored"] and x["t_rec"] <= 10)
        n30 = sum(1 for x in L if not x["t_rec_censored"] and x["t_rec"] <= 30)
        n60 = sum(1 for x in L if not x["t_rec_censored"] and x["t_rec"] <= 60)
        nn = sum(1 for x in L if x["t_rec_censored"])
        mid = tr[len(tr) // 2] if len(tr) % 2 else None
        if mid is None:
            a1, a2 = tr[len(tr) // 2 - 1], tr[len(tr) // 2]
            mtxt = (">%.0f" % a2["t_rec"]) if a2["t_rec_censored"] else "%.0f" % ((a1["t_rec"] + a2["t_rec"]) / 2)
        else:
            mtxt = fmt_t(mid["t_rec"], mid["t_rec_censored"])
        tb = sorted(L, key=lambda x: (x["t_base_censored"], x["t_base"]))
        tbm = tb[len(tb) // 2]
        print("| %s | %d | %.2f (%s) | %.2f (%s) | %s (%s) | %d / %d / %d / %d | %s (%s) | %d | %.2f (%s) |" % (
            a, len(L), med([x["share_pre"] for x in L]), rng([x["share_pre"] for x in L]),
            med([x["share_peak"] for x in L]), rng([x["share_peak"] for x in L]), mtxt,
            "%s to %s" % (fmt_t(tr[0]["t_rec"], tr[0]["t_rec_censored"]),
                          fmt_t(tr[-1]["t_rec"], tr[-1]["t_rec_censored"])),
            n10, n30, n60, nn, fmt_t(tbm["t_base"], tbm["t_base_censored"]),
            "%s to %s" % (fmt_t(tb[0]["t_base"], tb[0]["t_base_censored"]),
                          fmt_t(tb[-1]["t_base"], tb[-1]["t_base_censored"])),
            sum(1 for x in L if x["t_base_censored"]),
            med([x["share_post_end"] for x in L]), rng([x["share_post_end"] for x in L])))
    print("\n## Hop B's busiest worker (of a core) and hop A's pool\n")
    print("| Arm | busiest worker pre, median | busiest worker peak after, median (max) | hop A pool pre | peak | "
          "+10 s | +30 s | +60 s | +120 s | conns opened in the 5 s after the pause | opened after that | "
          "hop B conns per worker, pre (median leg) | at the end |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for a in arms:
        L = by[a]
        if not L:
            continue
        mid = sorted(L, key=lambda x: x["pool_peak"] or 0)[len(L) // 2]
        print("| %s | %.2f | %.2f (%.2f) | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            a, med([x["busy_pre"] for x in L]), med([x["busy_peak"] for x in L]),
            max(x["busy_peak"] for x in L), rng([x["pool_pre"] for x in L], "%.0f"),
            rng([x["pool_peak"] for x in L], "%.0f"), rng([x["pool_10"] for x in L], "%.0f"),
            rng([x["pool_30"] for x in L], "%.0f"), rng([x["pool_60"] for x in L], "%.0f"),
            rng([x["pool_120"] for x in L], "%.0f"), rng([x["cx_opened_burst"] for x in L], "%.0f"),
            rng([x["cx_opened_post"] for x in L], "%.0f"),
            "/".join(str(v) for v in sorted(mid["hopb_conns_pre"] or [], reverse=True)),
            "/".join(str(v) for v in sorted(mid["hopb_conns_end"] or [], reverse=True))))
    print("\n## CPU over the whole window and latency (paired against %s, per round)\n" % base)
    print("| Arm | cycles/req both hops, median | effect [95% CI] | τ-widened half-width (rule for < 2%) | "
          "p (t) | CPU-s both hops, median | p99 steady, ms (median) | p99 in the 10 s after, ms, median (max) | "
          "whole-run p99 µs, median | remote closes | non-2xx |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    out = {"legs": rows, "comparisons": {}}
    for a in arms:
        L = by[a]
        if not L:
            continue
        rb = {x["round"]: x for x in by[base]}
        pb = [(rb[x["round"]]["cycles_all"], x["cycles_all"]) for x in L if x["round"] in rb]
        eff, tw, p = "–", "–", "–"
        if a != base and pb:
            c = stats.paired_log_ratio([u for u, _ in pb], [v for _, v in pb])
            out["comparisons"][a] = {k: v for k, v in c.items() if k != "log_pcts"}
            if "lo_pct" in c:
                eff = "%+.1f%% [%+.1f, %+.1f]" % (c["effect_pct"], c["lo_pct"], c["hi_pct"])
                h = max(tau_hw(c), c["half_width_pct"])  # never narrower than the run's own t interval
                tw = "±%.1f → [%+.1f, %+.1f]" % (h, c["log_mean_pct"] - h, c["log_mean_pct"] + h) \
                    if abs(c["effect_pct"]) < 2 else "not needed"
                p = "%.2g" % c["t_p"]
        print("| %s | %.1fk | %s | %s | %s | %.1f | %.2f | %.2f (%.2f) | %.0f | %d | %d |" % (
            a, med([x["cycles_all"] for x in L]) / 1e3, eff, tw, p, med([x["cpu_s"] for x in L]),
            nz(med([x["p99_pre_ms"] for x in L])), nz(med([x["p99_rec_ms"] for x in L])),
            max([x["p99_rec_ms"] for x in L if x["p99_rec_ms"] is not None] or [float("nan")]),
            med([x["p99_whole_us"] for x in L]), sum(x["remote_close"] or 0 for x in L),
            sum(x["non2xx"] or 0 for x in L)))
    print("\n## Per leg\n")
    print("| leg | valid | pause ms | pre share | peak share | T_rec | T_base | pool pre/peak/+60/end | "
          "cycles/req all |")
    print("|---|---|---|---|---|---|---|---|---|")
    for x in rows:
        print("| %s | %s | %.1f | %.2f | %.2f | %s | %s | %s/%s/%s/%s | %.1fk |" % (
            x["leg"], "y" if x["valid"] else "n", x["pause_ms"], x["share_pre"] or 0, x["share_peak"] or 0,
            fmt_t(x["t_rec"], x["t_rec_censored"]), fmt_t(x["t_base"], x["t_base_censored"]),
            x["pool_pre"], x["pool_peak"], x["pool_60"], x["pool_end"], (x["cycles_all"] or 0) / 1e3))
    if jout:
        with open(jout, "w") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
