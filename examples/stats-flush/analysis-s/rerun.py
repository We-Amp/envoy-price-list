#!/usr/bin/env python3
"""OTLP at 1M, the re-run (s-1m-otlp-rerun): independent re-derivation from the raw legs.

    python3 rerun.py [RERUN_DIR] > rerun.txt

Same method as analyze.py: per-flush price from the burst list between the quiescent points
(re-summed), an own burst detector on the raw 50 Hz series as a second estimator, perf cycles
as a third; paired by round; log ratio with a t interval, widened by 0.34 and by the A/A
half-width; delivery evidence per leg from the collector's count and Envoy's own counters.
No harness import.
"""
import glob
import gzip
import json
import math
import os
import re
import sys

from scipy import stats as sps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_lib as A  # noqa: E402

RUN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "..", "data", "stats", "sink-types", "s-1m-otlp-rerun")
POINTS = 360146
C = "cluster.otel_collector."


def own_periods(samples, busy_min=0.2, join_s=0.1):
    starts, last_t, open_ = [], None, False
    for i in range(1, len(samples)):
        dt = samples[i][0] - samples[i - 1][0]
        if dt > 0 and (samples[i][1] - samples[i - 1][1]) / (dt * 1e9) > busy_min:
            if not open_ or samples[i - 1][0] - last_t > join_s:
                starts.append(i - 1)
                open_ = True
            last_t = samples[i][0]
    k = len(starts) - 1
    return (samples[starts[-1]][1] - samples[starts[0]][1]) / 1e6 / k, len(starts)


recs = [json.loads(l) for l in open(os.path.join(RUN, "legs.jsonl")) if l.strip()]
sup = [r for r in recs if "arm" not in r]
legs = [r for r in recs if "arm" in r]
print("records %d, supersede records %d, valid %d, attempts %s, intervals %s" % (
    len(legs), len(sup), sum(m["verdict"]["valid"] for m in legs), sorted({m["attempt"] for m in legs}),
    sorted({m["flush_interval_s"] for m in legs})))
arms = ["nosink-20s", "nosink-20s-A2", "otlp"]
v = {a: {} for a in arms}
for m in legs:
    b = m["span_flushes"]["bursts"]
    a_ = sum(x["run_ms"] for x in b) / len(b)
    assert abs(a_ - m["span_flushes"]["run_ms_per_flush"]) < 0.01
    s = json.load(gzip.open(os.path.join(RUN, "main", m["leg_id"] + ".json.gz")))["samples"]
    b_, nb = own_periods(s)
    v[m["arm"]][m["round"]] = {"a": a_, "b": b_, "nb": nb, "n": len(b), "c": m["main_perf"]["cycles_per_s"] * 20.0 / 1e6,
                               "k": m["main_perf"]["cycles_k_per_s"] / m["main_perf"]["cycles_per_s"], "m": m,
                               "bursts": [x["run_ms"] for x in b]}
rounds = sorted(v["otlp"])
pos = {a: [0, 0, 0] for a in arms}
for r in rounds:
    for i, m in enumerate(sorted([v[a][r]["m"] for a in arms], key=lambda m: m["started_utc"])):
        pos[m["arm"]][i] += 1
print("order positions per arm: %s; window %s to %s" % (pos, min(m["started_utc"] for m in legs), max(m["started_utc"] for m in legs)))


def ci(t, f="%.1f"):
    return (f + " [" + f + ", " + f + "]") % (t["mean"], t["lo"], t["hi"])


print("\n-- per arm (mean [95%% t] over %d rounds): (a) span ms per flush, (b) own detector ms per 20 s period, (c) M cycles per 20 s" % len(rounds))
for a in arms:
    d = v[a]
    ms = [d[r]["m"] for r in rounds]
    print("   %-14s (a) %-26s (b) %-26s (c) %-24s kernel %.1f%%; flushes in span %s; stall max %.0f ms; /ready max %.0f ms; VmHWM %.0f MiB; "
          "other threads %.2f ms/s; watchdog miss %s mega %s" % (
              a, ci(A.t_int([d[r]["a"] for r in rounds])), ci(A.t_int([d[r]["b"] for r in rounds])),
              ci(A.t_int([d[r]["c"] for r in rounds])), 100 * A.mean([d[r]["k"] for r in rounds]), sorted({d[r]["n"] for r in rounds}),
              max(m["main"]["stall_ms_max"] for m in ms), max(m["ready"]["max_ms"] for m in ms),
              A.mean([m["memory"]["vm_hwm_kb_after"] / 1024.0 for m in ms]), A.mean([m["other_threads_ms_per_s"] for m in ms]),
              sorted({(m.get("watchdog_delta") or {}).get("main_thread.watchdog_miss", 0) for m in ms}),
              sorted({(m.get("watchdog_delta") or {}).get("main_thread.watchdog_mega_miss", 0) for m in ms})))
    print("   %-14s by round (a): %s" % ("", " ".join("%.1f" % d[r]["a"] for r in rounds)))
    res = sps.linregress(rounds, [math.log(d[r]["a"]) for r in rounds])
    allb = [x for r in rounds for x in d[r]["bursts"]]
    print("   %-14s drift %+.2f%% per round (p %.2f); single flushes: n %d, min %.1f, max %.1f, CV %.2f%%" % (
        "", 100 * res.slope, res.pvalue, len(allb), min(allb), max(allb), 100 * A.sd(allb) / A.mean(allb)))

print("\n-- A/A nosink-20s-A2 against nosink-20s")
aa = {}
for key, name in (("a", "span, per flush"), ("b", "window, per period"), ("c", "cycles per 20 s")):
    r = A.log_ratio([v["nosink-20s-A2"][x][key] for x in rounds], [v["nosink-20s"][x][key] for x in rounds])
    aa[key] = r
    print("   %-20s %+.2f%% [%+.2f, %+.2f]; half-width %.2f log-%%; reach %.2f; p %.3f; pair SD %.2f" % (
        name, r["eff"], r["lo"], r["hi"], r["hw"], max(abs(r["log_lo"]), abs(r["log_hi"])), r["p"], A.sd(r["d"])))
print("   per-round log ratio (span): %s" % " ".join("%+.1f" % x for x in aa["a"]["d"]))
d = A.t_int([v["nosink-20s-A2"][x]["a"] - v["nosink-20s"][x]["a"] for x in rounds])
print("   difference %s ms per flush" % ci(d, "%+.2f"))
# the harness's primary metric (main ms per s), recomputed from the record, for the 3.54% line
r = A.log_ratio([v["nosink-20s-A2"][x]["m"]["main"]["run_ms_per_s"] for x in rounds], [v["nosink-20s"][x]["m"]["main"]["run_ms_per_s"] for x in rounds])
print("   harness primary metric (main ms per s over the window): %+.2f%% [%+.2f, %+.2f]; half-width %.2f (target 3.00)" % (r["eff"], r["lo"], r["hi"], r["hw"]))

print("\n-- otlp against nosink-20s (paired by round), and against the A/A copy")
for ref in ("nosink-20s", "nosink-20s-A2"):
    for key, name, unit in (("a", "span", "ms per flush"), ("b", "window", "ms per flush"), ("c", "perf", "M cycles per flush")):
        t = A.t_int([v["otlp"][x][key] - v[ref][x][key] for x in rounds])
        extra = ""
        if key == "a":
            extra = "  = %.3f us per point [%.3f, %.3f] over %d points" % (1e3 * t["mean"] / POINTS, 1e3 * t["lo"] / POINTS, 1e3 * t["hi"] / POINTS, POINTS)
        if key == "c":
            extra = "  = %.1f ms at 2.3 GHz" % (t["mean"] / 2.3)
        print("   vs %-14s delta (%s) %s %s%s" % (ref, name, ci(t, "%+.1f"), unit, extra))
    r = A.log_ratio([v["otlp"][x]["a"] for x in rounds], [v[ref][x]["a"] for x in rounds])
    hw_aa = aa["a"]["hw"]
    w = max(r["hw"], 1.96 * math.sqrt(r["se"] ** 2 + hw_aa ** 2))
    print("   vs %-14s ratio (span) %+.1f%% [%+.1f, %+.1f]; widened 0.34 [%+.1f, %+.1f]; widened by the A/A half-width %.2f: [%+.1f, %+.1f]; SE %.2f; p %.2e" % (
        ref, r["eff"], r["lo"], r["hi"], r["wlo"], r["whi"], hw_aa, A.pct(r["log"] - w), A.pct(r["log"] + w), r["se"], r["p"]))
absm = A.mean([v["otlp"][x]["a"] for x in rounds])
refm = A.mean([v["nosink-20s"][x]["a"] for x in rounds])
dm = absm - refm
print("   absolute: otlp %.1f ms, reference %.1f ms; A/A half-width %.2f%% of the reference = +/- %.1f ms on the delta; "
      "delta range under that: %.1f .. %.1f ms = %.3f .. %.3f us per point" % (
          absm, refm, aa["a"]["hw"], refm * aa["a"]["hw"] / 100, dm - refm * aa["a"]["hw"] / 100, dm + refm * aa["a"]["hw"] / 100,
          1e3 * (dm - refm * aa["a"]["hw"] / 100) / POINTS, 1e3 * (dm + refm * aa["a"]["hw"] / 100) / POINTS))
print("   A/A reach as ms on the reference: %.1f ms; as a share of the delta: %.2f%%" % (
    refm * max(abs(aa["a"]["log_lo"]), abs(aa["a"]["log_hi"])) / 100, 100 * refm * max(abs(aa["a"]["log_lo"]), abs(aa["a"]["log_hi"])) / 100 / dm))

print("\n-- delivery evidence per otlp leg")
print("   round  used  cg  hist | collector: points  fit n  per flush  residual  refused  settled | span n | Envoy (window reads): requests  flushes  rx_reset  h2 present  tx MB | "
      "leg end: rq_total rq_2xx rx_reset tx MB per flush | collector log lines (in span / total / error-level)")
for r in rounds:
    m = v["otlp"][r]["m"]
    cd, oc, e = m["collector_delta"], m["otlp_cluster"], m["sut_stats_leg_end"]
    log = open(os.path.join(RUN, "collector", m["leg_id"] + ".log")).read().splitlines() if os.path.exists(os.path.join(RUN, "collector", m["leg_id"] + ".log")) else []
    kinds = {}
    for ln in log:
        f = ln.split("\t")
        kinds[(f[1] if len(f) > 1 else "?", re.sub(r"\s+", " ", f[3] if len(f) > 3 else ln)[:90])] = kinds.get((f[1] if len(f) > 1 else "?", re.sub(r"\s+", " ", f[3] if len(f) > 3 else ln)[:90]), 0) + 1
    rq = e.get(C + "upstream_rq_total")
    print("   r%02d %d %d %d | %d %d %.2f %.2e %d %s | %d | %d %.1f %d %s %.1f | %s %s %s %.2f | %d lines %s; record: %s" % (
        r, m["used_total"], m["used_cg_lines"], m["post_read"]["histograms"], cd["accepted_metric_points"], cd["fit"]["n"],
        cd["accepted_metric_points_per_flush"], cd["fit"]["residual"], cd["refused_metric_points"], cd["settled"], m["span_flushes"]["n"],
        oc["requests"], oc["flushes"], oc["rx_reset"], oc["http2_stats_present"], oc["tx_bytes"] / 1e6,
        rq, e.get(C + "upstream_rq_2xx"), e.get(C + "http2.rx_reset", "absent"),
        e.get(C + "upstream_cx_tx_bytes_total") / 1e6 / (rq / 37.0), len(log), dict(kinds), json.dumps(m.get("collector_log"))[:160]))
    bad = {k: x for k, x in e.items() if C in k and x and re.search(r"reset|fail|timeout|overflow|retry|cancel|protocol_error|[45]xx|503", k)}
    if bad:
        print("        failure-type counters non-zero: %s" % bad)
    # log lines: when, against the leg
    ts = sorted({ln[:19] for ln in log})
    print("        collector log timestamps %s; leg started %s" % (ts, m["started_utc"]))

print("\n-- gates over the 27 legs (failing count)")
checks = {
    "valid": lambda m: m["verdict"]["valid"], "evidence ok": lambda m: m["evidence"]["ok"] is True,
    "main_tid_ok": lambda m: m.get("main_tid_ok") is True,
    "perf_ok, no multiplexing": lambda m: m.get("perf_ok") is True and m.get("perf_min_running_pct") == 100.0,
    "pinning_ok": lambda m: m.get("pinning_ok") is True, "idle_ok": lambda m: m.get("idle_ok") is True,
    "cpuidle_unchanged": lambda m: m.get("cpuidle_unchanged") is True, "envoy_exit 0": lambda m: m.get("envoy_exit") == 0,
    "dropped_stat_flushes 0": lambda m: m.get("dropped_stat_flushes_delta") == 0,
    "sampler_missing 0": lambda m: m["main"]["sampler_missing"] == 0, "span partial 0": lambda m: m["span_flushes"]["partial"] == 0,
    "3 whole flushes in span": lambda m: m["span_flushes"]["n"] == 3,
    "quiescent both": lambda m: m["quiesce"]["before_ok"] and m["quiesce"]["after_ok"],
    "prime all 200": lambda m: m["prime"]["ok"] == 10000 and m["prime"]["errors"] == 0,
    "burst_count_error 0": lambda m: m["main"]["burst_count_error"] == 0,
}
for k, f in checks.items():
    bad = [m["leg_id"] for m in legs if not f(m)]
    print("   %-26s %d %s" % (k, len(bad), bad[:5]))
print("   stats_total by arm %s; used_total by arm %s" % ({a: sorted({v[a][r]["m"]["stats_total"] for r in rounds}) for a in arms},
                                                        {a: sorted({v[a][r]["m"]["used_total"] for r in rounds}) for a in arms}))
print("   uptime error max by arm %s; load1 max %.2f; foreign cpu max %.4f; sibling max %.4f; cpuidle fingerprints %s" % (
    {a: max(v[a][r]["m"]["uptime"]["error_s"] for r in rounds) for a in arms}, max(m["idle_detail"]["load1"] for m in legs),
    max(m["sut_foreign_cpus"] for m in legs), max(m["sut_sibling_cpus"] for m in legs), sorted({m["cpuidle_fingerprint"] for m in legs})))
print("   own detector bursts in window by arm: %s" % {a: sorted({v[a][r]["nb"] for r in rounds}) for a in arms})

# against run S (s-1m, same day, 12:16Z to 13:32Z)
S = os.path.join(RUN, "..", "s-1m", "legs.jsonl")
if os.path.exists(S):
    old = {}
    for l in open(S):
        m = json.loads(l)
        if m.get("arm") in ("nosink-20s", "otlp", "nosink", "nosink-5s"):
            b = m["span_flushes"]["bursts"]
            old.setdefault(m["arm"], []).append(sum(x["run_ms"] for x in b) / len(b))
    print("\n-- against run S's 1M legs (unpaired, different session): mean ms per flush")
    for a, xs in old.items():
        print("   run S %-10s %.1f (n %d, SD %.1f)" % (a, A.mean(xs), len(xs), A.sd(xs)))
    for a in arms:
        xs = [v[a][r]["a"] for r in rounds]
        print("   re-run %-14s %.1f (n %d, SD %.1f)" % (a, A.mean(xs), len(xs), A.sd(xs)))
    for a, b in (("nosink-20s", "nosink-20s"), ("otlp", "otlp")):
        x, y = [v[a][r]["a"] for r in rounds], old[b]
        w = sps.ttest_ind(x, y, equal_var=False)
        print("   %s re-run against run S: %+.2f%% (Welch p %.3f)" % (a, 100 * (A.mean(x) / A.mean(y) - 1), w.pvalue))
    print("   run S otlp minus nosink-20s (truncated flush): %+.1f; re-run: %+.1f" % (A.mean(old["otlp"]) - A.mean(old["nosink-20s"]), dm))
