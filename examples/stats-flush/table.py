#!/usr/bin/env python3
"""Tables of the stats-flush row (make.py, run-session.sh).

    python3 examples/stats-flush/table.py SESSION_DIR [--json OUT.json] > tables.md

SESSION_DIR holds the runs (m-10k, m-100k, m-300k, m-1m, w, s-100k, s-1m, sw, x-1m), rungs.json,
cal/ and w-prediction.json. Valid legs of complete blocks only; incomplete runs carry no
verdict and stay out of every Holm step.

- The curve (run M): main-thread ms and cycles per flush. The flush price of an arm is its
  run time per flush period minus flush-off's run time over the same wall time, paired by
  round (at a rung where bursts are under the sampler's resolution: run time per second
  minus flush-off's, times the interval). A difference, not a ratio: a t interval only.
  Derived, labelled as derived: share of one core at the default 5 s interval, d / 5 s capped at
  1 (flushes start one interval apart whatever they take, measured on the bench box; a flush
  longer than the interval keeps the main thread busy all the time).
  Fit cost = a + b N with an intercept, quoted per stat and per cluster of the stock mix;
  scaling exponents between rungs.
- Ratio rows (v2): mean paired log ratio, 95% t interval, widened by 0.34 (an assumption for
  this metric, stated); a finding must clear the larger of 1% and the session's A/A reach.
- Confirmatory (Holm, 5 rows; 6 when run M predicts W's nosink effect at 1% or more): statsd
  against nosink at the four rungs (main-thread run time per second), statsd against
  flush-off in run W (total cycles per request: the per-request cost of the statsd sink on
  the workers).
- Secondary (Holm): W's nosink row otherwise ("at most N%"), the A/A rows.
- Run S (its own Holm family): statsd, dogstatsd-buf and otlp against nosink at the same interval,
  per whole flush from each leg's quiescent span (no flush-off pairing), with the rung's own
  nosink-A2 A/A; and under load (sw) cycles per request against nosink. prom is not in run S.
- Exploratory: stalls, /ready latency, memory, worker-only cycles, run X, user and kernel
  split, used share, datagrams per flush and per request, flush counts per W leg by arm.
"""

import argparse
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")
sys.path.insert(0, REPO)
from epl import experiment, stats  # noqa: E402

_spec = importlib.util.spec_from_file_location("features_table",
                                               os.path.join(REPO, "examples", "settings-matrix", "features_table.py"))
FT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FT)
T = FT.T

RUNGS = [("10k", 100), ("100k", 1000), ("300k", 3000), ("1m", 10000)]
DEFAULT_INTERVAL_S = 5.0
AA_TARGET_PCT = 2.0


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def load(d):
    return FT.load_run(d)


def legs_by_round(res, arm):
    return {r: m for (s, a, r), m in FT.usable_legs(res).items() if a == arm}


def g(m, *path):
    v = m
    for p in path:
        v = (v or {}).get(p) if isinstance(v, dict) else None
    return v


def flush_price_rounds(off, arm):
    """{round: (ms, cycles)}: the arm's main-thread price of one flush, paired with flush-off's
    run time over the same wall time. Burst periods are used only where the burst count
    matched the interval (+/-1); otherwise (the smallest rung, a missed burst) the per-second
    form: (arm - flush-off) per second x the arm's interval."""
    out = {}
    for r in sorted(set(off) & set(arm)):
        ms, cyc = flush_price({r: off[r]}, {r: arm[r]})
        if ms or cyc:
            out[r] = (ms[0] if ms else None, cyc[0] if cyc else None)
    return out


def flush_price(off, arm):
    """Paired per round: the arm's main-thread ms per flush minus flush-off's over the same
    wall time. Returns ([ms], [cycles]) per round."""
    ms, cyc = [], []
    for r in sorted(set(off) & set(arm)):
        a, o = arm[r], off[r]
        off_ms_s, off_cyc_s = g(o, "main", "run_ms_per_s"), g(o, "main_perf", "cycles_per_s")
        per = g(a, "main", "period_s")
        ok = a.get("flushes_from") != "interval" and g(a, "main", "burst_count_error") is not None \
            and g(a, "main", "burst_count_error") <= 1
        if per and ok:
            x = g(a, "main", "run_ms_per_period")
            if x is not None and off_ms_s is not None:
                ms.append(x - off_ms_s * per)
            c = g(a, "main_perf", "cycles_per_s")
            if c is not None and off_cyc_s is not None:
                cyc.append((c - off_cyc_s) * per)
        else:
            iv = a.get("flush_interval_s") or 1.0
            x = g(a, "main", "run_ms_per_s")
            if x is not None and off_ms_s is not None:
                ms.append((x - off_ms_s) * iv)
            c = g(a, "main_perf", "cycles_per_s")
            if c is not None and off_cyc_s is not None:
                cyc.append((c - off_cyc_s) * iv)
    return ms, cyc


def price_ratio_row(res, shape, arm, ref, label, family):
    """Log ratio of the per-flush prices of two arms (each against flush-off, paired by
    round): like with like even when the two run at different intervals."""
    off = legs_by_round(res, "flush-off")
    pa, pr = flush_price_rounds(off, legs_by_round(res, arm)), flush_price_rounds(off, legs_by_round(res, ref))
    rounds = sorted(r for r in set(pa) & set(pr) if pa[r][0] and pr[r][0] and pa[r][0] > 0 and pr[r][0] > 0)
    p = stats.paired_log_ratio([pr[r][0] for r in rounds], [pa[r][0] for r in rounds])
    r = {"label": label, "shape": shape, "arm": arm, "ref": ref, "metric": "flush price (ms per flush)",
         "family": family, "n": p["n"], "incomplete": bool(res.get("metadata", {}).get("incomplete"))}
    ia = {m.get("flush_interval_s") for m in legs_by_round(res, arm).values()}
    ir = {m.get("flush_interval_s") for m in legs_by_round(res, ref).values()}
    if ia != ir:
        r["note"] = "intervals differ (%s against %s): per-flush prices compared" % (sorted(ia), sorted(ir))
    if p.get("half_width_pct") is None:
        r["missing"] = "fewer than 2 pairs"
        return r
    w = T.widened(p)
    r.update(log_mean=p["log_mean_pct"], lo=p["log_lo_pct"], hi=p["log_hi_pct"], hw=p["half_width_pct"],
             t_p=None if r["incomplete"] else p["t_p"], se=T.se_of(p), widened=w,
             effect_pct=T.pct(p["log_mean_pct"]), lo_pct=T.pct(p["log_lo_pct"]), hi_pct=T.pct(p["log_hi_pct"]),
             widened_lo_pct=T.pct(p["log_mean_pct"] - w), widened_hi_pct=T.pct(p["log_mean_pct"] + w))
    return r


def span_price_row(res, shape, arm, ref, label, family):
    """Run S (S1): log ratio of two arms' main-thread run time per whole flush, each taken from
    its own leg's quiescent span (span_flushes.run_ms_per_flush), paired by round. No flush-off
    pairing; the reference is the nosink arm at the same interval."""
    pa, pr = legs_by_round(res, arm), legs_by_round(res, ref)
    va = {r: g(m, "span_flushes", "run_ms_per_flush") for r, m in pa.items()}
    vr = {r: g(m, "span_flushes", "run_ms_per_flush") for r, m in pr.items()}
    rounds = sorted(r for r in set(va) & set(vr) if va[r] and vr[r] and va[r] > 0 and vr[r] > 0)
    p = stats.paired_log_ratio([vr[r] for r in rounds], [va[r] for r in rounds])
    r = {"label": label, "shape": shape, "arm": arm, "ref": ref, "metric": "main ms per whole flush (span)",
         "family": family, "n": p["n"], "incomplete": bool(res.get("metadata", {}).get("incomplete")),
         "arm_ms_per_flush": mean([va[x] for x in rounds]), "ref_ms_per_flush": mean([vr[x] for x in rounds]),
         "price_ms_per_flush": t_interval([va[x] - vr[x] for x in rounds])}
    ia = {m.get("flush_interval_s") for m in pa.values()}
    ir = {m.get("flush_interval_s") for m in pr.values()}
    if ia != ir:
        r["note"] = "intervals differ (%s against %s)" % (sorted(ia), sorted(ir))
    if p.get("half_width_pct") is None:
        r["missing"] = "fewer than 2 pairs"
        return r
    w = T.widened(p)
    r.update(log_mean=p["log_mean_pct"], lo=p["log_lo_pct"], hi=p["log_hi_pct"], hw=p["half_width_pct"],
             t_p=None if r["incomplete"] else p["t_p"], se=T.se_of(p), widened=w,
             effect_pct=T.pct(p["log_mean_pct"]), lo_pct=T.pct(p["log_lo_pct"]), hi_pct=T.pct(p["log_hi_pct"]),
             widened_lo_pct=T.pct(p["log_mean_pct"] - w), widened_hi_pct=T.pct(p["log_mean_pct"] + w))
    return r


def run_s_tables(runs):
    """[lines], {json}: run S per flush (idle rungs) and under load (sw)."""
    L, js = [], {"rows": [], "aa": {}}
    rows = []
    for rung in ("100k", "1m"):
        res = runs.get("s-" + rung)
        if not res:
            continue
        sh = "idle-" + rung
        aa = span_price_row(res, sh, "nosink-A2", "nosink", "A/A 1 s (span, per flush)", "s-aa")
        if not aa.get("missing"):
            js["aa"][rung] = {"hw": aa["hw"], "reach": max(abs(aa["lo"]), abs(aa["hi"]))}
        aa5 = None
        if any(a["name"] == "nosink-5s-A2" for a in res["experiment"]["arms"]):
            aa5 = span_price_row(res, sh, "nosink-5s-A2", "nosink-5s", "A/A 5 s (span, per flush)", "s-aa")
            if not aa5.get("missing"):
                js["aa"][rung + "@5s"] = {"hw": aa5["hw"], "reach": max(abs(aa5["lo"]), abs(aa5["hi"]))}
        refs = res["experiment"].get("s_refs") or {}
        for a in ("statsd", "dogstatsd-buf", "otlp"):
            if a in refs:
                src, lab = res, "%s per flush" % a
                rerun = a == "otlp" and rung == "1m" and runs.get("s-1m-otlp")
                if rerun:
                    # the re-run with the collector's receive limit raised supersedes the first
                    # 1M otlp row (which lost the histogram requests of every flush); it is a
                    # separate session with its own A/A (nosink-20s-A2 against nosink-20s)
                    src, lab = runs["s-1m-otlp"], "otlp per flush (re-run, receive limit raised)"
                    aa20 = span_price_row(src, sh, "nosink-20s-A2", "nosink-20s", "A/A 20 s, re-run (span, per flush)",
                                          "s-aa")
                    if not aa20.get("missing"):
                        js["aa"]["1m@20s-rerun"] = {"hw": aa20["hw"], "reach": max(abs(aa20["lo"]), abs(aa20["hi"]))}
                row = span_price_row(src, sh, a, refs[a], lab, "s")
                if rerun:
                    row["aa_key"] = "1m@20s-rerun"
                    row["note"] = ("the first 1M otlp row was discarded: the collector refused the histogram requests "
                                   "of every flush (receive limit); re-run in a later session against its own nosink-20s "
                                   "and A/A, receive limit 64 MiB")
                    rows.append(row)
                    rows.append(aa20)
                    continue
                # the A/A whose reach a row uses: the reference's interval; the 20 s reference has no
                # copy of its own and uses the 5 s reach (stated in the row)
                row["aa_key"] = rung if refs[a] == "nosink" else rung + "@5s"
                if refs[a] == "nosink-20s":
                    row["note"] = (row.get("note", "") + "; " if row.get("note") else "") + \
                        "A/A reach of the 5 s reference (no 20 s copy)"
                rows.append(row)
        rows.append(aa)
        if aa5 is not None:
            rows.append(aa5)
    if runs.get("sw"):
        for a in ("statsd", "dogstatsd-buf", "otlp"):
            rows.append(ratio_row(runs["sw"], "s", a, "nosink", "cycles_total",
                                  "%s, cycles per request under load" % a, "s"))
        aa = ratio_row(runs["sw"], "s", "nosink-A2", "nosink", "cycles_total", "A/A, loaded", "s-aa")
        if not aa.get("missing"):
            js["aa"]["sw"] = {"hw": aa["hw"], "reach": max(abs(aa["lo"]), abs(aa["hi"]))}
        rows.append(aa)
    if not rows:
        return L, js
    fam = [r for r in rows if r["family"] == "s"]
    k = FT.holm(fam)
    for r in rows:
        key = r.get("aa_key") or (r["shape"].replace("idle-", "") if r["shape"].startswith("idle-") else "sw")
        reach = js["aa"].get(key, {}).get("reach")
        r["verdict"] = verdict(r, reach) if reach is not None or r.get("missing") else \
            "no verdict: no A/A at this rung"
        if r.get("note"):
            r["verdict"] += "; " + r["note"]
    L.append("## Run S: the sinks (Holm over %d rows; per-flush prices from each leg's quiescent span)\n" % k)
    L.append("Each sink against nosink at its own interval (at 1M: statsd and dogstatsd-buf against nosink-5s, otlp "
             "against nosink-20s); a finding must clear the larger of 1% and the A/A reach at the reference's interval "
             "(at 1M the 5 s copy nosink-5s-A2; the 20 s rows use that 5 s reach). Under load (sw): "
             "total cycles per request against nosink at the default 5 s interval.\n")
    L.append(HDR)
    for r in rows:
        L.append(fmt_ratio(r))
    L.append("")
    L.append("| Row | Shape | Arm ms per flush | Reference ms per flush | Price ms per flush [95% CI] |\n"
             "|---|---|---|---|---|")
    for r in rows:
        if r.get("arm_ms_per_flush") is None:
            continue
        t = r["price_ms_per_flush"]
        L.append("| %s | %s | %.1f | %.1f | %s |" % (
            r["label"], r["shape"], r["arm_ms_per_flush"], r["ref_ms_per_flush"],
            "-" if t.get("lo") is None else "%+.1f [%+.1f, %+.1f]" % (t["mean"], t["lo"], t["hi"])))
    L.append("")
    js["rows"] = rows
    return L, js


def share_of_core_pct(d_ms, interval_s):
    """Derived: the main thread's share of one core when a flush of d ms starts every interval
    (flush starts are one interval apart whatever the flush takes), capped at 100%."""
    if d_ms is None:
        return None
    return 100.0 * min(1.0, d_ms / (interval_s * 1000.0))


def t_interval(xs):
    n = len(xs)
    if n < 2:
        return {"n": n, "mean": xs[0] if xs else None}
    mu = stats.mean(xs)
    se = stats.stdev(xs) / math.sqrt(n)
    hw = stats.t_ppf(0.975, n - 1) * se
    return {"n": n, "mean": mu, "lo": mu - hw, "hi": mu + hw, "hw": hw}


def ratio_row(res, shape, arm, ref, key, label, family):
    by = FT.usable_legs(res)
    p = FT.paired(by, shape, arm, ref, key)
    r = {"label": label, "shape": shape, "arm": arm, "ref": ref, "metric": key, "family": family, "n": p["n"],
         "incomplete": bool(res.get("metadata", {}).get("incomplete"))}
    if p.get("half_width_pct") is None:
        r["missing"] = "fewer than 2 pairs"
        return r
    w = T.widened(p)
    r.update(log_mean=p["log_mean_pct"], lo=p["log_lo_pct"], hi=p["log_hi_pct"], hw=p["half_width_pct"],
             t_p=None if r["incomplete"] else p["t_p"], se=T.se_of(p), widened=w,
             effect_pct=T.pct(p["log_mean_pct"]), lo_pct=T.pct(p["log_lo_pct"]), hi_pct=T.pct(p["log_hi_pct"]),
             widened_lo_pct=T.pct(p["log_mean_pct"] - w), widened_hi_pct=T.pct(p["log_mean_pct"] + w))
    return r


def verdict(r, reach):
    if r.get("missing"):
        return "no data (%s)" % r["missing"]
    if r.get("incomplete"):
        return experiment.INCOMPLETE
    floor = max(1.0, reach or 0.0)
    p = {"log_mean_pct": r["log_mean"], "log_lo_pct": r["lo"], "log_hi_pct": r["hi"]}
    v = T.verdict(p, r["widened"], r.get("holm_p"))
    if abs(r["log_mean"]) < floor:
        v = "under the larger of 1%% and the A/A reach (%.2f%%): not a finding" % floor
    return v


def fit(points):
    """Least squares cost = a + b N over [(N, cost)]."""
    n = len(points)
    if n < 2:
        return None
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    if sxx == 0:
        return None
    b = sum((p[0] - mx) * (p[1] - my) for p in points) / sxx
    return {"a": my - b * mx, "b": b}


def fmt_ratio(r):
    if r.get("missing"):
        return "| %s | %s | %s vs %s | - | - | - | - | %s |" % (r["label"], r["shape"], r["arm"], r["ref"],
                                                               r.get("verdict"))
    return "| %s | %s | %s vs %s | %+.2f%% [%+.2f, %+.2f] | [%+.2f, %+.2f] | %s | %d | %s |" % (
        r["label"], r["shape"], r["arm"], r["ref"], r["effect_pct"], r["lo_pct"], r["hi_pct"], r["widened_lo_pct"],
        r["widened_hi_pct"], "%.3g" % r["holm_p"] if r.get("holm_p") is not None else "-", r["n"], r.get("verdict"))


HDR = ("| Row | Shape | Arm vs ref | Effect [95% CI] | Widened | Holm p | Pairs | Verdict |\n"
       "|---|---|---|---|---|---|---|---|")


def tables(sess):
    L, js = [], {}
    runs = {n: load(os.path.join(sess, n)) for n in ("m-10k", "m-100k", "m-300k", "m-1m", "w", "s-100k", "s-1m",
                                                     "x-1m", "sw", "s-1m-otlp")}
    runs = {k: v for k, v in runs.items() if v}
    rungs = {}
    if os.path.exists(os.path.join(sess, "rungs.json")):
        with open(os.path.join(sess, "rungs.json")) as f:
            rungs = json.load(f)
    L.append("# Stats flush row\n")
    L.append("## Runs\n")
    for n, res in runs.items():
        md = res.get("metadata", {})
        inv = sum(1 for m in res["legs"] if not (m.get("verdict") or {}).get("valid"))
        L.append("- %s: %d legs, %d invalid; %s complete rounds%s" % (
            n, len(res["legs"]), inv, md.get("rounds_complete"), " (**incomplete, no verdict**)"
            if md.get("incomplete") else ""))
    L.append("")
    L.append("## Calibration (rungs)\n")
    L.append("| Rung | Clusters | N | Used | Used counter and gauge lines | Share of N sent as statsd lines |"
             "\n|---|---|---|---|---|---|")
    for rung, k in RUNGS + [("3m", 30000), ("10m", 100000)]:
        c = rungs.get(rung)
        if not c:
            continue
        n, u, cg = c.get("stats_total"), c.get("used_total"), c.get("used_cg_lines")
        L.append("| %s | %d | %s | %s | %s | %s |" % (rung, k, n, u, cg, "%.1f%%" % (100.0 * cg / n) if n and cg
                                                       else "-"))
    L.append("")
    js["rungs"] = rungs

    # the curve
    L.append("## The curve (run M): main-thread price of a flush\n")
    L.append("Paired by round against flush-off (same wall time); milliseconds always beside cycles. Derived: "
             "share of one core at the default 5 s interval, d / 5 s capped at 1: flushes start one interval "
             "apart whatever they take (measured), so a flush longer than the interval keeps the main thread "
             "busy all the time.\n")
    L.append("| Rung | N | Arm | ms per flush [95% CI] | M cycles per flush [95% CI] | Share of a core at 5 s "
             "(derived) | Stall p50 / max (ms) | /ready max (ms) | VmHWM (MB) |\n|---|---|---|---|---|---|---|---|---|")
    curve = {}
    for rung, k in RUNGS:
        res = runs.get("m-" + rung)
        if not res:
            continue
        off = legs_by_round(res, "flush-off")
        for a in ("nosink", "statsd", "nosink-A2"):
            mine = legs_by_round(res, a)
            ms, cyc = flush_price(off, mine)
            tm, tc = t_interval(ms), t_interval(cyc)
            stall = [g(m, "main", "stall_ms_p50") for m in mine.values()]
            stall_max = [g(m, "main", "stall_ms_max") for m in mine.values()]
            ready = [g(m, "ready", "max_ms") for m in mine.values()]
            hwm = [g(m, "memory", "vm_hwm_kb_after") for m in mine.values()]
            nN = mean([m.get("stats_total") for m in mine.values()])
            d = tm.get("mean")
            row = {"rung": rung, "clusters": k, "n_stats": nN, "arm": a, "ms": tm, "cycles": tc,
                   "share_at_5s_pct": share_of_core_pct(d, DEFAULT_INTERVAL_S),
                   "stall_p50_ms": mean(stall), "stall_max_ms": max([x for x in stall_max if x is not None] or [0]),
                   "ready_max_ms": max([x for x in ready if x is not None] or [0]), "vm_hwm_kb": mean(hwm)}
            curve.setdefault(a, []).append(row)

            def fi(t, scale=1.0, fmt="%.2f"):
                if t.get("mean") is None:
                    return "-"
                if t.get("lo") is None:
                    return (fmt % (t["mean"] / scale))
                return (fmt + " [" + fmt + ", " + fmt + "]") % (t["mean"] / scale, t["lo"] / scale, t["hi"] / scale)
            L.append("| %s | %s | %s | %s | %s | %s | %s / %s | %s | %s |" % (
                rung, "-" if nN is None else "%.0f" % nN, a, fi(tm), fi(tc, 1e6), "-" if row["share_at_5s_pct"] is None
                else "%.3f%%" % row["share_at_5s_pct"], "-" if row["stall_p50_ms"] is None else "%.0f"
                % row["stall_p50_ms"], "%.0f" % row["stall_max_ms"], "%.0f" % row["ready_max_ms"],
                "-" if row["vm_hwm_kb"] is None else "%.0f" % (row["vm_hwm_kb"] / 1024)))
    L.append("")
    js["curve"] = curve
    L.append("### Fit cost = a + b N (with an intercept; N and the cluster count are collinear here)\n")
    js["fit"] = {}
    for a in ("nosink", "statsd"):
        pts = [(r["n_stats"], r["ms"]["mean"]) for r in curve.get(a, []) if r["n_stats"] and r["ms"].get("mean")
               is not None]
        f = fit(pts)
        js["fit"][a] = f
        if f:
            per_cluster = f["b"] * (pts[-1][0] / [k for rr, k in RUNGS if rr == curve[a][-1]["rung"]][0])
            L.append("- %s: a = %.3f ms, b = %.3f us per stat (%.1f us per cluster of the stock mix); largest "
                     "measured rung %.0f stats, nothing beyond it" % (a, f["a"], f["b"] * 1e3, per_cluster * 1e3,
                                                                      pts[-1][0]))
            ex = []
            for (n1, c1), (n2, c2) in zip(pts, pts[1:]):
                if c1 > 0 and c2 > 0 and n2 > n1:
                    ex.append("%.0f->%.0f: %.2f" % (n1, n2, math.log(c2 / c1) / math.log(n2 / n1)))
            L.append("  scaling exponents (log cost against log N, exploratory): %s" % ("; ".join(ex) or "-"))
    L.append("")

    # A/A per rung and pooled reach
    aa = {}
    L.append("## A/A per rung (nosink-A2 against nosink, main-thread run time per second)\n")
    L.append("| Rung | Half-width | Reach | Target %.0f%% met |\n|---|---|---|---|" % AA_TARGET_PCT)
    for rung, _ in RUNGS:
        res = runs.get("m-" + rung)
        if not res:
            continue
        r = ratio_row(res, "idle-" + rung, "nosink-A2", "nosink", "main_ms_per_s", "A/A", "secondary")
        if r.get("missing"):
            continue
        reach = max(abs(r["lo"]), abs(r["hi"]))
        aa[rung] = {"hw": r["hw"], "reach": reach, "ok": r["hw"] <= AA_TARGET_PCT, "row": r}
        L.append("| %s | %.2f | %.2f | %s |" % (rung, r["hw"], reach, "yes" if r["hw"] <= AA_TARGET_PCT else "no"))
    pooled = max([v["reach"] for v in aa.values()] or [0.0])
    L.append("\nSession reach (the largest per-rung reach, used as the pooled floor): %.2f%%\n" % pooled)
    js["aa"] = {k: {kk: vv for kk, vv in v.items() if kk != "row"} for k, v in aa.items()}

    # families
    pred = {}
    pp = os.path.join(sess, "w-prediction.json")
    if os.path.exists(pp):
        with open(pp) as f:
            try:
                pred = json.load(f)
            except ValueError:
                pred = {}
    conf, sec = [], []
    for rung, _ in RUNGS:
        res = runs.get("m-" + rung)
        if res:
            conf.append(price_ratio_row(res, "idle-" + rung, "statsd", "nosink",
                                        "statsd sink, marginal price per flush", "confirmatory"))
    if runs.get("w"):
        conf.append(ratio_row(runs["w"], "s", "statsd", "flush-off", "cycles_total",
                              "statsd sink, per-request cost on the workers (cycles per request)", "confirmatory"))
        nrow = ratio_row(runs["w"], "s", "nosink", "flush-off", "cycles_total", "the flush, effect on request work",
                         "confirmatory" if pred.get("nosink_row") == "confirmatory" else "secondary")
        (conf if nrow["family"] == "confirmatory" else sec).append(nrow)
        sec.append(ratio_row(runs["w"], "s", "flush-off-A2", "flush-off", "cycles_total", "A/A, loaded", "secondary"))
    for rung, v in aa.items():
        sec.append(v["row"])
    for fam, rows in (("Confirmatory", conf), ("Secondary", sec)):
        k = FT.holm(rows)
        for r in rows:
            reach = aa.get(r["shape"].replace("idle-", ""), {}).get("reach", pooled) if r["metric"] != "cycles_total" \
                else 0.0
            r["verdict"] = verdict(r, reach)
            if r["arm"] == "nosink" and r["family"] == "secondary" and not r.get("missing"):
                r["verdict"] += "; at most %+.2f%% (widened upper end)" % r["widened_hi_pct"]
        L.append("## %s rows (Holm over %d rows)\n" % (fam, k))
        if fam == "Confirmatory" and pred:
            L.append("Run W prediction from run M at 100k: %+.2f%% -> the nosink row is %s.\n" % (
                pred.get("predicted_effect_pct", float("nan")), pred.get("nosink_row")))
        L.append(HDR)
        for r in rows:
            L.append(fmt_ratio(r))
        L.append("")
    js["confirmatory"], js["secondary"] = conf, sec
    sl, sj = run_s_tables(runs)
    L.extend(sl)
    js["run_s"] = sj

    # observation, not a result: the plain statsd sink at 1 s at the top rung
    js["observations"] = []
    cp = os.path.join(sess, "cal", "1m-statsd", "calibrate-legs.jsonl")
    if os.path.exists(cp):
        with open(cp) as f:
            m0 = json.loads(f.readline())
        mn, u = m0.get("main") or {}, m0.get("udp") or {}
        n = (u.get("fit") or {}).get("n")
        span = (m0.get("quiesce") or {}).get("span_s")
        if (mn.get("run_ms_per_s") or 0) >= 900:
            per = span / n if n and span else None
            txt = ("At about %.0f stats (1M rung) the plain statsd sink at a 1 s interval kept the main thread busy "
                   "%.0f%% of the time: flushes of about %s s ran back to back (%s whole flushes in %.1f s), with %s "
                   "drops. Recorded as an observation, not a priced row; the rung's statsd arms run at 5 s." % (
                       m0.get("stats_total") or 0, (mn.get("run_ms_per_s") or 0) / 10.0,
                       "%.1f" % per if per else "?", n, span or 0,
                       "no" if not u.get("dropped") else "%d" % u["dropped"]))
            js["observations"].append(txt)
    L.append("## Observations\n")
    L.append("- Flush scheduling (measured): flushes start one interval apart whatever they take (1.001 s at 1 s "
             "with flushes of 20 to 740 ms); the derived share of a core is d / interval, capped at 1.")
    for t in js["observations"]:
        L.append("- " + t)
    L.append("")

    # run M-fix: the fix build against its base build, per rung (its own family and A/A)
    mf = {r: load(os.path.join(sess, "mfix-" + r)) for r in ("10k", "100k", "1m")}
    mf = {k: v for k, v in mf.items() if v}
    if mf:
        rows = []
        L.append("## Run M-fix: own builds (5e1439980a / 3c9cce2f2c): top (the fix) against main (its base)\n")
        L.append("Main-thread run time per second and cycles per second at the same interval; the A/A is a "
                 "second copy of main without a sink. Two own builds, not upstream releases.\n")
        L.append("| Rung | Arm | main thread ms/s | M cycles/s |\n|---|---|---|---|")
        for rung, res in mf.items():
            by = FT.usable_legs(res)
            for a in ("nosink-main", "nosink-top", "statsd-main", "statsd-top", "nosink-main-A2"):
                ms = mean([g(m, "main", "run_ms_per_s") for (s_, aa_, r_), m in by.items() if aa_ == a])
                cy = mean([g(m, "main_perf", "cycles_per_s") for (s_, aa_, r_), m in by.items() if aa_ == a])
                L.append("| %s | %s | %s | %s |" % (rung, a, "-" if ms is None else "%.2f" % ms,
                                                   "-" if cy is None else "%.1f" % (cy / 1e6)))
        L.append("")
        for rung, res in mf.items():
            for a, b, lab in (("nosink-top", "nosink-main", "own builds (5e1439980a / 3c9cce2f2c), no sink"),
                              ("statsd-top", "statsd-main", "own builds (5e1439980a / 3c9cce2f2c), statsd sink")):
                rows.append(ratio_row(res, "idle-" + rung, a, b, "main_ms_per_s", lab, "mfix"))
        aa_mf = {}
        for rung, res in mf.items():
            r = ratio_row(res, "idle-" + rung, "nosink-main-A2", "nosink-main", "main_ms_per_s", "A/A", "mfix-aa")
            if not r.get("missing"):
                aa_mf[rung] = max(abs(r["lo"]), abs(r["hi"]))
                r["verdict"] = "A/A half-width %.2f%%, reach %.2f%%" % (r["hw"], aa_mf[rung])
            rows.append(r)
        k = FT.holm([r for r in rows if r["family"] == "mfix"])
        for r in rows:
            if r["family"] == "mfix":
                r["verdict"] = verdict(r, aa_mf.get(r["shape"].replace("idle-", ""), pooled))
        L.append("### Fix rows (Holm over %d rows; a finding must clear the larger of 1%% and the rung's own A/A "
                 "reach)\n" % k)
        L.append(HDR)
        for r in rows:
            L.append(fmt_ratio(r))
        L.append("")
        js["mfix"] = rows

    # exploratory
    L.append("## Exploratory\n")
    if runs.get("w"):
        by = FT.usable_legs(runs["w"])
        fl = {}
        for (s, a, r), m in by.items():
            fl.setdefault(a, []).append(m.get("flushes_counted"))
        L.append("- run W flushes counted in the window, by arm: %s" % ", ".join(
            "%s %s" % (a, sorted(x for x in v if x is not None)) for a, v in sorted(fl.items())))
        dpr = [g(m, "udp", "datagrams_per_request") for (s, a, r), m in by.items() if a == "statsd"]
        if any(x is not None for x in dpr):
            L.append("- run W statsd datagrams per request: %.2f" % mean(dpr))
        wc = {a: mean([m.get("workers_cycles_per_req") for (s, aa_, r), m in by.items() if aa_ == a])
              for a in ("flush-off", "nosink", "statsd")}
        L.append("- run W worker-only cycles per request: %s" % ", ".join(
            "%s %s" % (a, "-" if v is None else "%.1fk" % (v / 1e3)) for a, v in wc.items()))
    for rung, _ in RUNGS:
        res = runs.get("m-" + rung)
        if not res:
            continue
        by = FT.usable_legs(res)
        for a in ("nosink", "statsd"):
            u = mean([g(m, "main_perf", "cycles_u_per_s") for (s, aa_, r), m in by.items() if aa_ == a])
            kk = mean([g(m, "main_perf", "cycles_k_per_s") for (s, aa_, r), m in by.items() if aa_ == a])
            spf = mean([g(m, "udp", "sent_per_flush") for (s, aa_, r), m in by.items() if aa_ == a])
            L.append("- %s %s: main thread user / kernel cycles per second %s / %s%s" % (
                rung, a, "-" if u is None else "%.1fM" % (u / 1e6), "-" if kk is None else "%.1fM" % (kk / 1e6),
                "" if spf is None else "; datagrams per flush %.0f" % spf))
    if runs.get("x-1m"):
        res = runs["x-1m"]
        for a, ref in (("statsd-5s", "statsd"), ("statsd-cold", "statsd"), ("nosink-cold", "statsd")):
            r = ratio_row(res, "idle-1m", a, ref, "main_ms_per_s", a, "exploratory")
            if not r.get("missing"):
                L.append("- run X %s against %s (run time per second): %+.2f%% [%+.2f, %+.2f]" % (
                    a, ref, r["effect_pct"], r["lo_pct"], r["hi_pct"]))
    for rung in ("100k", "1m"):
        res = runs.get("s-" + rung)
        if res:
            by = FT.usable_legs(res)
            ot = mean([m.get("other_threads_ms_per_s") for (s, a, r), m in by.items() if a == "otlp"])
            if ot is not None:
                L.append("- %s otlp: other threads' run time %.2f ms/s beside the main thread" % (rung, ot))
    L.append("")
    return "\n".join(L) + "\n", js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--json")
    a = ap.parse_args()
    text, js = tables(a.session)
    sys.stdout.write(text)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(js, f, indent=1, default=str)


if __name__ == "__main__":
    main()
