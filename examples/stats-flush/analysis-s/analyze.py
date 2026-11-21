#!/usr/bin/env python3
"""Independent re-derivation of run S (stats sinks) from the raw per-leg data.

    python3 analyze.py [SESSION_DIR] > analysis.txt

Reads only SESSION_DIR/{s-100k,s-1m,sw}/legs.jsonl and the raw main-thread sampler series in
SESSION_DIR/{s-100k,s-1m}/main/*.json.gz. Does not import the harness (no epl, no table.py):
the statistics are re-implemented here (scipy for the t distribution).

Method v2: paired log ratios within round, 95% t interval, widened half-width
max(t half-width, 1.96*sqrt(SE^2 + 0.34^2)), Holm across the family, a finding must clear the
larger of 1% and the A/A reach, and its Holm p must be <= 0.05.
"""
import gzip
import json
import math
import os
import sys

from scipy import stats as sps

HERE = os.path.dirname(os.path.abspath(__file__))
SESSION = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "..", "data", "stats", "sink-types")
TAU = 0.34
OUT = {}


# ------------------------------------------------------------------ loading
def load(run):
    """(current legs, all leg records, superseded ids). A record without `arm` names the leg
    ids a re-run of their round supersedes; legs before that record with those ids are out."""
    recs, sup_idx = [], set()
    for line in open(os.path.join(SESSION, run, "legs.jsonl")):
        if not line.strip():
            continue
        r = json.loads(line)
        if "arm" not in r:
            ids = set(r.get("supersede") or [])
            for i, p in enumerate(recs):
                if p["leg_id"] in ids:
                    sup_idx.add(i)
            continue
        recs.append(r)
    cur = [r for i, r in enumerate(recs) if i not in sup_idx]
    old = [r for i, r in enumerate(recs) if i in sup_idx]
    return cur, recs, old


def valid(m):
    return bool((m.get("verdict") or {}).get("valid"))


def by_round(legs, arm):
    return {m["round"]: m for m in legs if m["arm"] == arm and valid(m)}


# ------------------------------------------------------------------ statistics
def mean(xs):
    return sum(xs) / len(xs)


def sd(xs):
    mu = mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def t_int(xs):
    n = len(xs)
    mu, se = mean(xs), sd(xs) / math.sqrt(n)
    hw = sps.t.ppf(0.975, n - 1) * se
    return {"n": n, "mean": mu, "lo": mu - hw, "hi": mu + hw, "se": se, "sd": sd(xs)}


def pct(logpct):
    return 100.0 * (math.exp(logpct / 100.0) - 1.0)


def log_ratio(arm_vals, ref_vals):
    d = [100.0 * math.log(a / b) for a, b in zip(arm_vals, ref_vals)]
    t = t_int(d)
    se = t["se"]
    hw = t["hi"] - t["mean"]
    w = max(hw, 1.96 * math.sqrt(se * se + TAU * TAU))
    p = 2.0 * sps.t.sf(abs(t["mean"]) / se, t["n"] - 1) if se > 0 else 0.0
    return {"n": t["n"], "log": t["mean"], "log_lo": t["lo"], "log_hi": t["hi"], "hw": hw, "se": se, "w": w,
            "eff": pct(t["mean"]), "lo": pct(t["lo"]), "hi": pct(t["hi"]),
            "wlo": pct(t["mean"] - w), "whi": pct(t["mean"] + w), "p": p, "d": d}


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        adj[i] = run
    return adj


def verdict(r, reach, holm_p):
    floor = max(1.0, reach)
    if abs(r["log"]) < floor:
        return "not a finding (under %.2f%%, the larger of 1%% and the A/A reach)" % floor
    if holm_p > 0.05:
        return "not a finding (Holm p %.3g)" % holm_p
    if r["wlo"] <= 0.0 <= r["whi"]:
        return "not a finding (widened interval includes 0)"
    return "finding"


# ------------------------------------------------------------------ per-leg estimators (idle)
def span_ms_per_flush(m):
    """(a) the harness's own burst list between the two quiescent points, summed here."""
    b = m["span_flushes"]["bursts"]
    return sum(x["run_ms"] for x in b) / len(b), len(b)


def raw_series(run, m):
    return json.load(gzip.open(os.path.join(SESSION, run, "main", m["leg_id"] + ".json.gz")))["samples"]


def own_periods(samples, busy_min=0.2, join_s=0.1):
    """(b) own burst detector on the raw 50 Hz schedstat series of the measurement window: a
    sample step is busy when the main thread ran more than busy_min of it; busy steps closer
    than join_s are one burst. Returns (run ms per whole flush period, bursts, mean period s,
    run ms inside bursts per burst): run time from the sample before the first burst to the
    sample before the last burst, over the number of periods. Includes the main thread's
    non-flush run time of one period; no flush-off arm exists in run S to subtract it."""
    starts, ends, last_busy_t, open_ = [], [], None, False
    for i in range(1, len(samples)):
        dt = samples[i][0] - samples[i - 1][0]
        busy = dt > 0 and (samples[i][1] - samples[i - 1][1]) / (dt * 1e9) > busy_min
        if busy:
            if not open_ or (samples[i - 1][0] - last_busy_t) > join_s:
                if open_:
                    ends.append(last_i)
                starts.append(i - 1)
                open_ = True
            last_busy_t, last_i = samples[i][0], i
    if open_:
        ends.append(last_i)
    if len(starts) < 2:
        return None, len(starts), None, None
    k = len(starts) - 1
    run_ms = (samples[starts[-1]][1] - samples[starts[0]][1]) / 1e6 / k
    per = (samples[starts[-1]][0] - samples[starts[0]][0]) / k
    # whole bursts only (a burst touching the window edge is cut)
    whole = [(s, e) for s, e in zip(starts, ends) if s > 0 and e < len(samples) - 1]
    inb = mean([(samples[e][1] - samples[s][1]) / 1e6 for s, e in whole]) if whole else None
    return run_ms, len(starts), per, inb


def cycles_per_interval(m):
    """(c) perf stat on the main tid over the window: cycles (user + kernel) per second times the
    flush interval, in M cycles. Includes non-flush cycles; window edges not aligned to flushes."""
    return m["main_perf"]["cycles_per_s"] * m["flush_interval_s"] / 1e6


def kernel_share(m):
    p = m["main_perf"]
    return p["cycles_k_per_s"] / p["cycles_per_s"]


def fmt_ci(t, f="%.1f"):
    return (f + " [" + f + ", " + f + "]") % (t["mean"], t["lo"], t["hi"])


def P(*a):
    print(*a)


# ------------------------------------------------------------------ idle rungs
IDLE = {
    "s-100k": {"refs": {"statsd": "nosink", "dogstatsd-buf": "nosink", "otlp": "nosink"},
               "aa": [("nosink-A2", "nosink")], "N": 118396},
    "s-1m": {"refs": {"statsd": "nosink-5s", "dogstatsd-buf": "nosink-5s", "otlp": "nosink-20s"},
             "aa": [("nosink-A2", "nosink"), ("nosink-5s-A2", "nosink-5s")], "N": 1180396},
}
family = []          # confirmatory rows for Holm: (label, row)
aa_reach = {}


def idle_run(run):
    cfg = IDLE[run]
    cur, recs, old = load(run)
    arms = []
    for m in recs:
        if m["arm"] not in arms:
            arms.append(m["arm"])
    P("\n" + "=" * 100)
    P("RUN %s: %d leg records, %d superseded, %d current; arms %s" % (run, len(recs), len(old), len(cur), arms))

    # ---- gate accounting
    P("\n-- legs per arm: current valid / current invalid / superseded (valid, invalid)")
    for a in arms:
        c = [m for m in cur if m["arm"] == a]
        o = [m for m in old if m["arm"] == a]
        P("   %-14s %2d / %d / %d (%d valid, %d invalid)   rounds %s   interval %s s" % (
            a, sum(valid(m) for m in c), sum(not valid(m) for m in c), len(o),
            sum(valid(m) for m in o), sum(not valid(m) for m in o),
            sorted(m["round"] for m in c if valid(m)), sorted({m["flush_interval_s"] for m in c})))
    for m in recs:
        if not valid(m):
            P("   INVALID %s attempt %s: %s" % (m["leg_id"], m.get("attempt"), (m.get("verdict") or {}).get("reasons")))
    for m in old:
        sf = m.get("span_flushes") or {}
        P("   superseded %-30s valid=%s span n=%s partial=%s ms/flush=%s" % (
            m["leg_id"], valid(m), sf.get("n"), sf.get("partial"), sf.get("run_ms_per_flush")))

    # ---- order balance
    P("\n-- order: position of each arm within its round (by start time), counts per position")
    rounds = sorted({m["round"] for m in cur})
    pos = {a: [0] * len(arms) for a in arms}
    for r in rounds:
        seq = sorted([m for m in cur if m["round"] == r], key=lambda m: m["started_utc"])
        for i, m in enumerate(seq):
            pos[m["arm"]][i] += 1
    for a in arms:
        P("   %-14s %s" % (a, pos[a]))
    P("   run window: %s to %s" % (min(m["started_utc"] for m in recs), max(m["started_utc"] for m in recs)))

    # ---- per-arm absolute prices
    P("\n-- per arm: main-thread ms per flush, three estimators (mean [95% t interval] over rounds)")
    P("   (a) span: burst run time between quiescent points / whole flushes (burst list re-summed)")
    P("   (b) window: own burst detector on the raw series, run time per whole period (includes non-flush run time)")
    P("   (c) perf: M cycles per interval (cycles/s x interval), kernel share of main-thread cycles")
    est = {}
    for a in arms:
        br = by_round(cur, a)
        A, B, C, K, NF, PER, INB = {}, {}, {}, {}, {}, {}, {}
        for r, m in br.items():
            A[r], NF[r] = span_ms_per_flush(m)
            assert abs(A[r] - m["span_flushes"]["run_ms_per_flush"]) < 0.01, m["leg_id"]
            b, nb, per, inb = own_periods(raw_series(run, m))
            B[r], PER[r], INB[r] = b, per, inb
            C[r] = cycles_per_interval(m)
            K[r] = kernel_share(m)
            # own detector against the record
            rec = m["main"]
            if rec.get("bursts") != nb or (b and abs(b - rec["run_ms_per_period"]) > 0.02 * rec["run_ms_per_period"] + 0.05):
                P("   NOTE %s: own detector %s bursts, %.2f ms/period; record %s bursts, %.2f" % (
                    m["leg_id"], nb, b or -1, rec.get("bursts"), rec.get("run_ms_per_period") or -1))
        est[a] = {"a": A, "b": B, "c": C, "k": K, "n": NF, "per": PER, "inb": INB, "legs": br}
        rs = sorted(A)
        P("   %-14s n=%2d (a) %-28s (b) %-28s (c) %-28s kernel %4.1f%%  flushes/span %s  period %.3f s" % (
            a, len(rs), fmt_ci(t_int([A[r] for r in rs]), "%.2f"), fmt_ci(t_int([B[r] for r in rs]), "%.2f"),
            fmt_ci(t_int([C[r] for r in rs]), "%.1f"), 100 * mean([K[r] for r in rs]),
            sorted({NF[r] for r in rs}), mean([PER[r] for r in rs])))
        st = [m["main"]["stall_ms_max"] for m in br.values()]
        rd = [m["ready"]["max_ms"] for m in br.values()]
        ot = [m["other_threads_ms_per_s"] for m in br.values()]
        hw = [m["memory"]["vm_hwm_kb_after"] / 1024.0 for m in br.values()]
        P("   %-14s stall max %.0f ms (median of leg maxima %.0f); /ready max %.0f ms; other threads %.2f ms/s; VmHWM %.0f MiB; "
          "watchdog miss/mega per leg %s" % ("", max(st), sorted(st)[len(st) // 2], max(rd), mean(ot), mean(hw),
                                              sorted({(m.get("watchdog_delta") or {}).get("main_thread.watchdog_miss", 0) for m in br.values()}).__repr__()
                                              + "/" + sorted({(m.get("watchdog_delta") or {}).get("main_thread.watchdog_mega_miss", 0) for m in br.values()}).__repr__()))

    # ---- A/A
    P("\n-- A/A (paired log ratio per round), span (a) and window (b)")
    for arm, ref in cfg["aa"]:
        rs = sorted(set(est[arm]["a"]) & set(est[ref]["a"]))
        for key, name in (("a", "span"), ("b", "window")):
            r = log_ratio([est[arm][key][x] for x in rs], [est[ref][key][x] for x in rs])
            reach = max(abs(r["log_lo"]), abs(r["log_hi"]))
            P("   %-12s vs %-10s %-6s n=%d  %+.2f%% [%+.2f, %+.2f]  half-width %.2f  reach %.2f  p %.3f" % (
                arm, ref, name, r["n"], r["eff"], r["lo"], r["hi"], r["hw"], reach, r["p"]))
            if key == "a":
                aa_reach[(run, ref)] = reach
                d = t_int([est[arm]["a"][x] - est[ref]["a"][x] for x in rs])
                P("   %-12s vs %-10s diff   %s ms per flush" % (arm, ref, fmt_ci(d, "%+.2f")))
    if run == "s-1m":
        # cross-interval consistency of the no-sink flush (not an A/A: different intervals)
        for arm, ref in (("nosink-5s", "nosink"), ("nosink-20s", "nosink"), ("nosink-20s", "nosink-5s")):
            rs = sorted(set(est[arm]["a"]) & set(est[ref]["a"]))
            r = log_ratio([est[arm]["a"][x] for x in rs], [est[ref]["a"][x] for x in rs])
            P("   interval check %-10s vs %-10s span n=%d %+.2f%% [%+.2f, %+.2f] p %.3f" % (
                arm, ref, r["n"], r["eff"], r["lo"], r["hi"], r["p"]))

    # ---- sink rows
    P("\n-- sink minus reference at the same interval (paired by round)")
    for a, ref in cfg["refs"].items():
        rs = sorted(set(est[a]["a"]) & set(est[ref]["a"]))
        da = t_int([est[a]["a"][x] - est[ref]["a"][x] for x in rs])
        db = t_int([est[a]["b"][x] - est[ref]["b"][x] for x in rs])
        dc = t_int([est[a]["c"][x] - est[ref]["c"][x] for x in rs])
        r = log_ratio([est[a]["a"][x] for x in rs], [est[ref]["a"][x] for x in rs])
        aak = (run, ref) if (run, ref) in aa_reach else (run, "nosink-5s")
        row = {"run": run, "arm": a, "ref": ref, "r": r, "delta": da, "aa": aak, "n": len(rs)}
        family.append(row)
        P("   %-14s vs %-10s n=%d interval %g s" % (a, ref, len(rs), list(est[a]["legs"].values())[0]["flush_interval_s"]))
        P("       delta (a) span   %s ms per flush" % fmt_ci(da, "%+.1f"))
        P("       delta (b) window %s ms per flush" % fmt_ci(db, "%+.1f"))
        P("       delta (c) perf   %s M cycles per flush  (= %.1f ms at 2.3 GHz)" % (fmt_ci(dc, "%+.1f"), dc["mean"] / 2.3))
        P("       ratio (a) %+.1f%% [%+.1f, %+.1f]; widened [%+.1f, %+.1f]; SE %.2f log-%%; raw p %.3g" % (
            r["eff"], r["lo"], r["hi"], r["wlo"], r["whi"], r["se"], r["p"]))
        row["absolute"] = t_int([est[a]["a"][x] for x in rs])
        row["refabs"] = t_int([est[ref]["a"][x] for x in rs])
        # A/A-widened interval of the ratio (the rule of 2026-11-18, where the A/A misses 2%)
        OUT.setdefault("rows", []).append(row)

    # ---- evidence: what the receivers recorded
    P("\n-- receiver evidence per sink leg (current legs)")
    for a in ("statsd", "dogstatsd-buf"):
        br = est[a]["legs"]
        spf = [m["udp"]["sent_per_flush"] for m in br.values()]
        P("   %-14s datagrams per flush %.1f .. %.1f (mean %.1f); dropped total %d; rcvbuf_errors %d; socket_drops %d; in_errors %d; "
          "used counter+gauge lines %s; rcvbuf granted %s" % (
              a, min(spf), max(spf), mean(spf), sum(m["udp"]["dropped"] for m in br.values()),
              sum(m["udp"]["rcvbuf_errors"] for m in br.values()), sum(m["udp"]["socket_drops"] or 0 for m in br.values()),
              sum(m["udp"]["in_errors"] for m in br.values()), sorted({m["used_cg_lines"] for m in br.values()}),
              sorted({m["udpsink"]["rcvbuf_granted"] for m in br.values()})))
        if a == "statsd":
            P("   %-14s fit residual max %.4f of a flush; fit n = span n on every leg: %s" % (
                "", max(m["udp"]["fit"]["residual"] for m in br.values()),
                all(m["udp"]["fit"]["span_n_error"] == 0 for m in br.values())))
        else:
            P("   %-14s span fit n_error max %d; sink process lifetime: bytes/datagram %.0f, newlines/datagram %.2f" % (
                "", max(m["udp"]["span_fit"]["n_error"] for m in br.values()),
                mean([m["udpsink"]["bytes"] / m["udpsink"]["datagrams"] for m in br.values()]),
                mean([m["udpsink"]["newlines"] / m["udpsink"]["datagrams"] for m in br.values()])))
        OUT[(run, a, "dgrams")] = mean(spf)
        OUT[(run, a, "lines")] = mean([m["used_cg_lines"] for m in br.values()])
    br = est["otlp"]["legs"]
    P("   otlp: per leg  round  points/flush  basis  fit n  span n  residual  refused  used_total  used_cg  histograms(used)  "
      "rq_total  rq_2xx  h2 rx_reset  tx MB  uptime s")
    for r in sorted(br):
        m = br[r]
        cd, se_ = m["collector_delta"], m["sut_stats_leg_end"]
        P("         r%02d  %10.1f  %5s  %5s  %6s  %8.5f  %7s  %10s  %7s  %16s  %8s  %6s  %9s  %6.1f  %s" % (
            r, cd["accepted_metric_points_per_flush"], cd["fit"]["basis"], cd["fit"]["n"], m["span_flushes"]["n"],
            cd["fit"]["residual"], cd["refused_metric_points"], m["used_total"], m["used_cg_lines"],
            m["post_read"]["histograms"], se_.get("cluster.otel_collector.upstream_rq_total"),
            se_.get("cluster.otel_collector.upstream_rq_2xx"), se_.get("cluster.otel_collector.http2.rx_reset"),
            se_.get("cluster.otel_collector.upstream_cx_tx_bytes_total", 0) / 1e6, se_.get("server.uptime")))
    pts = [m["collector_delta"]["accepted_metric_points_per_flush"] for m in br.values()]
    OUT[(run, "otlp", "accepted")] = mean(pts)
    OUT[(run, "otlp", "used_total")] = mean([m["used_total"] for m in br.values()])
    OUT[(run, "otlp", "used_cg")] = mean([m["used_cg_lines"] for m in br.values()])
    OUT[(run, "otlp", "hist")] = mean([m["post_read"]["histograms"] for m in br.values()])
    # request-chunk model: gauges, counters, then histograms, 10,000 points per request; a request
    # holding more than `hmax` histogram points is over the collector's 4 MiB message limit
    P("   otlp: request-chunk model (order gauges, counters, histograms; 10,000 points per request):")
    for r in sorted(br):
        m = br[r]
        cg, h = m["used_cg_lines"], m["post_read"]["histograms"]
        for dcg in (0, -1):
            reqs, left_cg, left_h = [], cg + dcg, h
            while left_cg + left_h > 0:
                c = min(10000, left_cg)
                hh = min(10000 - c, left_h)
                reqs.append((c, hh))
                left_cg -= c
                left_h -= hh
            acc = sum(c + hh for c, hh in reqs if hh < 9000)
            rej = [(c, hh) for c, hh in reqs if hh >= 9000]
            if r == sorted(br)[0] or dcg == 0:
                pass
            if dcg == 0 or acc == round(m["collector_delta"]["accepted_metric_points_per_flush"]):
                P("         r%02d cg=%d hist=%d: %d requests per flush; if requests with >= 9,000 histogram points are rejected: "
                  "%d rejected %s, accepted %d (collector recorded %.0f)" % (
                      r, cg + dcg, h, len(reqs), len(rej), rej[:2], acc, m["collector_delta"]["accepted_metric_points_per_flush"]))

    # ---- drift across rounds
    P("\n-- drift across rounds: span ms per flush by round, and slope (%% per round, least squares on log)")
    for a in arms:
        A = est[a]["a"]
        rs = sorted(A)
        ys = [math.log(A[r]) for r in rs]
        mx, my = mean(rs), mean(ys)
        slope = sum((x - mx) * (y - my) for x, y in zip(rs, ys)) / sum((x - mx) ** 2 for x in rs)
        res = sps.linregress(rs, ys)
        P("   %-14s %s  slope %+.2f%%/round (p %.2f)  CV %.2f%%" % (
            a, " ".join("%.1f" % A[r] for r in rs), 100 * slope, res.pvalue, 100 * sd([A[r] for r in rs]) / mean([A[r] for r in rs])))
    OUT[run] = est
    # common gates over current legs
    P("\n-- common gates over current legs (count of legs failing each)")
    checks = {
        "main_tid_ok": lambda m: m.get("main_tid_ok") is True,
        "perf_ok / no multiplexing": lambda m: m.get("perf_ok") is True and m.get("perf_min_running_pct") == 100.0,
        "pinning_ok": lambda m: m.get("pinning_ok") is True,
        "idle_ok": lambda m: m.get("idle_ok") is True,
        "cpuidle_unchanged": lambda m: m.get("cpuidle_unchanged") is True,
        "envoy_exit 0": lambda m: m.get("envoy_exit") == 0,
        "dropped_stat_flushes 0": lambda m: m.get("dropped_stat_flushes_delta") == 0,
        "sampler_missing 0": lambda m: m["main"].get("sampler_missing") == 0,
        "span partial 0": lambda m: m["span_flushes"]["partial"] == 0,
        "quiescent before+after": lambda m: m["quiesce"]["before_ok"] and m["quiesce"]["after_ok"],
        "evidence ok": lambda m: m["evidence"]["ok"] is True,
        "stats_total exact": lambda m: abs(m["stats_total"] - cfg["N"]) <= 0.005 * cfg["N"],
        "prime all 200": lambda m: m["prime"]["ok"] == m["stats_clusters_count"] and m["prime"]["errors"] == 0,
        "burst_count_error 0": lambda m: m["main"]["burst_count_error"] == 0,
    }
    for k, f in checks.items():
        bad = [m["leg_id"] for m in cur if not f(m)]
        P("   %-28s %d failing %s" % (k, len(bad), bad[:6]))
    P("   stats_total by arm: %s" % {a: sorted({m["stats_total"] for m in cur if m["arm"] == a}) for a in arms})
    P("   used_total by arm: %s" % {a: sorted({m["used_total"] for m in cur if m["arm"] == a}) for a in arms})
    P("   uptime error s max by arm: %s" % {a: max(m["uptime"]["error_s"] for m in cur if m["arm"] == a) for a in arms})
    P("   sut_foreign_cpus max %.4f, sut_sibling_cpus max %.4f, load1 max %.2f" % (
        max(m["sut_foreign_cpus"] for m in cur), max(m["sut_sibling_cpus"] for m in cur),
        max(m["idle_detail"]["load1"] for m in cur)))


# ------------------------------------------------------------------ loaded rung
def loaded():
    run = "sw"
    cur, recs, old = load(run)
    arms = []
    for m in recs:
        if m["arm"] not in arms:
            arms.append(m["arm"])
    P("\n" + "=" * 100)
    P("RUN sw (loaded): %d leg records, %d superseded, %d current; arms %s" % (len(recs), len(old), len(cur), arms))
    for a in arms:
        c = [m for m in cur if m["arm"] == a]
        P("   %-14s valid %2d / invalid %d   rounds %s" % (a, sum(valid(m) for m in c), sum(not valid(m) for m in c),
                                                           sorted(m["round"] for m in c if valid(m))))
    rounds = sorted({m["round"] for m in cur})
    pos = {a: [0] * len(arms) for a in arms}
    for r in rounds:
        for i, m in enumerate(sorted([m for m in cur if m["round"] == r], key=lambda m: m["started_utc"])):
            pos[m["arm"]][i] += 1
    P("-- order positions per arm: %s" % pos)
    P("   run window: %s to %s" % (min(m["started_utc"] for m in recs), max(m["started_utc"] for m in recs)))

    def cyc(m):
        # recomputed from the raw perf counters and the SUT's own 2xx count, not from per_req
        raw = m["perf_raw"]
        ck = [k for k in raw if k.startswith("cycles")]
        return sum(raw[k] for k in ck) / m["responses"]

    P("-- per arm (means over rounds; p50 and p99 are medians of the leg values)")
    vals = {}
    for a in arms:
        br = by_round(cur, a)
        c = {r: cyc(m) for r, m in br.items()}
        for r, m in br.items():
            assert abs(c[r] - m["per_req"]["cycles_total"]) / c[r] < 1e-6, (m["leg_id"], c[r], m["per_req"]["cycles_total"])
        vals[a] = {"cyc": c, "wk": {r: m["workers_cycles_per_req"] for r, m in br.items()},
                   "p50": {r: m["latency_us"]["p50"] for r, m in br.items()},
                   "p99": {r: m["latency_us"]["p99"] for r, m in br.items()},
                   "ck": {r: m["per_req"]["cycles_k"] for r, m in br.items()},
                   "iu": {r: m["per_req"]["instructions_u"] for r, m in br.items()},
                   "main": {r: m["main"]["run_ms_per_period"] for r, m in br.items()}, "legs": br}
        med = lambda d: sorted(d.values())[len(d) // 2]
        P("   %-14s cycles/req %.0f  workers %.0f  busy %.1f%%  rate %.0f..%.0f  p50 %.0f us  p99 %.0f us  flushes in window %s  "
          "main ms/5 s period %.1f  non2xx %d  perf running min %.0f%%" % (
              a, mean(list(c.values())), mean(list(vals[a]["wk"].values())), 100 * mean([m["sut_busy"] for m in br.values()]),
              min(m["sut_rate_2xx"] for m in br.values()), max(m["sut_rate_2xx"] for m in br.values()),
              med(vals[a]["p50"]), med(vals[a]["p99"]), sorted({m["flushes_counted"] for m in br.values()}),
              mean(list(vals[a]["main"].values())), sum(m["sut_non2xx"] for m in br.values()),
              min(m["perf_min_running_pct"] for m in br.values())))
    aa = None
    P("-- effects against nosink (paired log ratio by round)")
    for a in ("nosink-A2", "statsd", "dogstatsd-buf", "otlp"):
        rs = sorted(set(vals[a]["cyc"]) & set(vals["nosink"]["cyc"]))
        r = log_ratio([vals[a]["cyc"][x] for x in rs], [vals["nosink"]["cyc"][x] for x in rs])
        P("   %-14s total cycles/req %+.2f%% [%+.2f, %+.2f]; widened [%+.2f, %+.2f]; SE %.3f; p %.3g; n=%d" % (
            a, r["eff"], r["lo"], r["hi"], r["wlo"], r["whi"], r["se"], r["p"], r["n"]))
        for key, name in (("wk", "worker cycles/req"), ("ck", "kernel cycles/req"), ("iu", "user instructions/req"),
                          ("p50", "p50"), ("p99", "p99"), ("main", "main-thread ms per period")):
            x = log_ratio([vals[a][key][q] for q in rs], [vals["nosink"][key][q] for q in rs])
            P("        %-26s %+.2f%% [%+.2f, %+.2f]" % (name, x["eff"], x["lo"], x["hi"]))
        if a == "nosink-A2":
            aa_reach[("sw", "nosink")] = max(1.0, 0.0)  # floor is 1%: see below
            OUT["sw_aa"] = r
            P("        A/A reach (far end of the t interval) %.2f%%; half-width %.2f%%" % (max(abs(r["log_lo"]), abs(r["log_hi"])), r["hw"]))
            aa_reach[("sw", "nosink")] = max(abs(r["log_lo"]), abs(r["log_hi"]))
        else:
            row = {"run": "sw", "arm": a, "ref": "nosink", "r": r, "aa": ("sw", "nosink"), "n": len(rs)}
            family.append(row)
            OUT.setdefault("rows", []).append(row)
    P("-- receiver evidence")
    for a in ("statsd", "dogstatsd-buf"):
        br = vals[a]["legs"]
        P("   %-14s datagrams/request %.3f .. %.3f; datagrams per 5 s %.0f; dropped %d; rcvbuf_errors %d; in_errors %d" % (
            a, min(m["udp"]["datagrams_per_request"] for m in br.values()), max(m["udp"]["datagrams_per_request"] for m in br.values()),
            mean([m["udp"]["sent_per_flush"] for m in br.values()]), sum(m["udp"]["dropped"] for m in br.values()),
            sum(m["udp"]["rcvbuf_errors"] for m in br.values()), sum(m["udp"]["in_errors"] for m in br.values())))
    br = vals["otlp"]["legs"]
    for r in sorted(br):
        m = br[r]
        d, e = m.get("sut_stats_delta") or {}, m.get("sut_stats_leg_end") or {}
        P("   otlp r%02d accepted points (collector delta) %d refused %d; window: requests %s, tx MB %.1f; leg end: rq_total %s rq_2xx %s rx_reset %s" % (
            r, m["collector_delta"]["accepted_metric_points"], m["collector_delta"]["refused_metric_points"],
            d.get("cluster.otel_collector.upstream_rq_total"), d.get("cluster.otel_collector.upstream_cx_tx_bytes_total", 0) / 1e6,
            e.get("cluster.otel_collector.upstream_rq_total"), e.get("cluster.otel_collector.upstream_rq_2xx"),
            e.get("cluster.otel_collector.http2.rx_reset", e.get("cluster.otel_collector.upstream_rq_rx_reset"))))
    P("-- drift: nosink cycles/req by round: %s" % " ".join("%.0f" % vals["nosink"]["cyc"][r] for r in sorted(vals["nosink"]["cyc"])))
    for a in arms:
        rs = sorted(vals[a]["cyc"])
        res = sps.linregress(rs, [math.log(vals[a]["cyc"][r]) for r in rs])
        P("   %-14s slope %+.3f%%/round (p %.2f)" % (a, 100 * res.slope, res.pvalue))
    checks = {
        "evidence ok": lambda m: m["evidence"]["ok"] is True,
        "perf_ok": lambda m: m.get("perf_ok") is True,
        "pinning_ok": lambda m: m.get("pinning_ok") is True,
        "idle_ok": lambda m: m.get("idle_ok") is True,
        "cpuidle_unchanged": lambda m: m.get("cpuidle_unchanged") is True,
        "sut_non2xx 0": lambda m: m.get("sut_non2xx") == 0,
        "client rate within 0.5% of 5200": lambda m: abs(m["client_rate_2xx"] - 5200) < 26,
        "prime ok": lambda m: m["prime"]["ok"] == 1000,
    }
    for k, f in checks.items():
        bad = [m["leg_id"] for m in cur if not f(m)]
        P("   gate %-32s %d failing %s" % (k, len(bad), bad[:6]))


idle_run("s-100k")
idle_run("s-1m")
loaded()

# ------------------------------------------------------------------ Holm over the family of 9
P("\n" + "=" * 100)
P("HOLM over the %d sink rows (3 sinks x 100k, 1M, loaded)" % len(family))
adj = holm([row["r"]["p"] for row in family])
for row, hp in zip(family, adj):
    r = row["r"]
    reach = aa_reach[row["aa"]]
    # A/A-widened interval (the rule of 2026-11-18): the rung's A/A half-width in place of 0.34
    P("   %-7s %-14s vs %-10s n=%2d  %+9.2f%% [%+.2f, %+.2f]  widened [%+.2f, %+.2f]  raw p %.2e  Holm p %.2e  A/A reach %.2f%%  -> %s" % (
        row["run"], row["arm"], row["ref"], row["n"], r["eff"], r["lo"], r["hi"], r["wlo"], r["whi"], r["p"], hp, reach,
        verdict(r, reach, hp)))

P("\nHOLM over the 8 rows left when the 1M OTLP row is excluded (invalid: the collector rejected part of every flush)")
fam8 = [row for row in family if not (row["run"] == "s-1m" and row["arm"] == "otlp")]
for row, hp in zip(fam8, holm([row["r"]["p"] for row in fam8])):
    P("   %-7s %-14s Holm p %.2e -> %s" % (row["run"], row["arm"], hp, verdict(row["r"], aa_reach[row["aa"]], hp)))

# ------------------------------------------------------------------ per line / per point
P("\n" + "=" * 100)
P("PER LINE / PER POINT (sink-minus-reference ms per flush over the unit count)")
for row in OUT["rows"]:
    if row["run"] == "sw":
        continue
    run, a, d = row["run"], row["arm"], row["delta"]
    if a == "statsd":
        n = OUT[(run, a, "dgrams")]
        P("   %-7s statsd        %+.1f ms / %.0f lines (= datagrams) = %.2f us per line [%.2f, %.2f]" % (
            run, d["mean"], n, 1e3 * d["mean"] / n, 1e3 * d["lo"] / n, 1e3 * d["hi"] / n))
    elif a == "dogstatsd-buf":
        n, g = OUT[(run, "statsd", "dgrams")], OUT[(run, a, "dgrams")]
        P("   %-7s dogstatsd-buf %+.1f ms / %.0f lines (statsd's line count; not counted per window for this sink) = %.2f us per line; "
          "%.0f datagrams per flush = %.1f lines per datagram, %.1f us per datagram" % (
              run, d["mean"], n, 1e3 * d["mean"] / n, g, n / g, 1e3 * d["mean"] / g))
    else:
        acc, ut, cg, h = (OUT[(run, a, k)] for k in ("accepted", "used_total", "used_cg", "hist"))
        P("   %-7s otlp          %+.1f ms; per accepted point (%.0f) %.2f us; per used stat (%.0f) %.2f us; "
          "per used counter+gauge (%.0f) %.2f us; used histograms %.0f" % (
              run, d["mean"], acc, 1e3 * d["mean"] / acc, ut, 1e3 * d["mean"] / ut, cg, 1e3 * d["mean"] / cg, h))
P("\nno-sink flush, us per stat (span ms per flush / N):")
for run, N in (("s-100k", 118396), ("s-1m", 1180396)):
    for a in ("nosink", "nosink-A2", "nosink-5s", "nosink-5s-A2", "nosink-20s"):
        if a in OUT[run]:
            v = list(OUT[run][a]["a"].values())
            P("   %-7s %-12s %.2f ms = %.3f us per stat" % (run, a, mean(v), 1e3 * mean(v) / N))
