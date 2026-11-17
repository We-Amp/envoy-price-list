#!/usr/bin/env python3
"""Tables of the stats-flush row (make.py, run-session.sh).

    python3 examples/stats-flush/table.py SESSION_DIR [--json OUT.json] > tables.md

SESSION_DIR holds the runs (m-10k, m-100k, m-300k, m-1m, w, s-100k, s-1m, x-1m), rungs.json,
cal/ and w-prediction.json. Valid legs of complete blocks only; incomplete runs carry no
verdict and stay out of every Holm step.

- The curve (run M): main-thread ms and cycles per flush. The flush price of an arm is its
  run time per flush period minus flush-off's run time over the same wall time, paired by
  round (at a rung where bursts are under the sampler's resolution: run time per second
  minus flush-off's, times the interval). A difference, not a ratio: a t interval only.
  Derived, labelled as derived: share of one core at the default 5 s interval, d / (5 s + d).
  Fit cost = a + b N with an intercept, quoted per stat and per cluster of the stock mix;
  scaling exponents between rungs.
- Ratio rows (v2): mean paired log ratio, 95% t interval, widened by 0.34 (an assumption for
  this metric, stated); a finding must clear the larger of 1% and the session's A/A reach.
- Confirmatory (Holm, 5 rows; 6 when run M predicts W's nosink effect at 1% or more): statsd
  against nosink at the four rungs (main-thread run time per second), statsd against
  flush-off in run W (total cycles per request: the per-request cost of the statsd sink on
  the workers).
- Secondary (Holm): W's nosink row otherwise ("at most N%"), the A/A rows, dogstatsd-buf,
  otlp and prom against nosink at both rungs.
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


def flush_price(off, arm):
    """Paired per round: the arm's main-thread ms per flush minus flush-off's over the same
    wall time. Returns ([ms], [cycles]) per round."""
    ms, cyc = [], []
    for r in sorted(set(off) & set(arm)):
        a, o = arm[r], off[r]
        off_ms_s, off_cyc_s = g(o, "main", "run_ms_per_s"), g(o, "main_perf", "cycles_per_s")
        per = g(a, "main", "period_s")
        if per:
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
                                                     "x-1m")}
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
             "share of one core at the default 5 s interval, d / (5 s + d).\n")
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
                   "share_at_5s_pct": 100.0 * d / (5000.0 + d) if d is not None else None,
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
            conf.append(ratio_row(res, "idle-" + rung, "statsd", "nosink", "main_ms_per_s",
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
    for rung in ("100k", "1m"):
        res = runs.get("s-" + rung)
        if res:
            for a in ("dogstatsd-buf", "otlp", "prom"):
                sec.append(ratio_row(res, "idle-" + rung, a, "nosink", "main_ms_per_s", a, "secondary"))
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
