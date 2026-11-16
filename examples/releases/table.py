#!/usr/bin/env python3
"""Tables of the release back-fill and the two filter rows.

    python3 examples/releases/table.py RELEASES_RUN [ROW_RUN ...] [--json OUT.json] > tables.md

RELEASES_RUN is the release run directory (results.json in it); ROW_RUN are the run
directories of the filter rows (11-jwt-authn, 12-local-ratelimit). Writes Markdown to
stdout:

- the A/A of the session (arm v1.40.2-A2 against v1.40.2), per shape;
- every release against v1.40.2 as "what v1.40.2 costs against release X": the sign is
  flipped, so a negative number means v1.40.2 is cheaper. Total cycles per request,
  95% t interval, Holm p from the run (Holm over the 24 primary rows of the run, the A/A
  row included), the half-width widened by the between-session A/A spread
  (1.96 * sqrt(SE^2 + 0.34^2), never narrower than the run's own) and a verdict;
- release-to-release steps (each release against the one before it) from the same
  paired rounds: exploratory, interval only;
- instructions, user and kernel cycles, p50 and p99 against v1.40.2 (exploratory);
- the filter rows against their baselines, with Holm across their primary rows, the
  floor from the release run's A/A arm, the widened half-width and the counters that
  show the setting did what it says.

Verdicts: "within the A/A spread" when |effect| < 1%; for a primary row, "not resolved
after Holm" when its Holm p is above 0.05; "about X%, not resolved" when the run's
interval excludes 0 but the widened one does not; "differs" when |effect| >= 1%, the
widened interval excludes 0 and (primary rows) Holm p <= 0.05. Steps are exploratory.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import experiment, stats  # noqa: E402

TAU = 0.34  # between-run A/A spread (one SD, log-%), PHASE2 label-swap pooling over every A/A run
BASE = "v1.40.2"
AA = "v1.40.2-A2"
ORDER = ["v1.32.13", "v1.34.14", "v1.36.13", "v1.37.11", "v1.38.9", "v1.40.2"]


def load(run_dir):
    with open(os.path.join(run_dir, "results.json")) as f:
        return json.load(f)


def pct(log_pct):
    return 100.0 * (math.exp(log_pct / 100.0) - 1.0)


def paired(vals_ref, vals_arm):
    return stats.paired_log_ratio(vals_ref, vals_arm)


def se_of(p):
    if p.get("half_width_pct") is None or p["n"] < 2:
        return None
    return p["half_width_pct"] / stats.t_ppf(0.975, p["n"] - 1)


def widened(p):
    se = se_of(p)
    if se is None:
        return None
    return max(1.96 * math.sqrt(se * se + TAU * TAU), p["half_width_pct"])


def verdict(p, w, holm_p=None):
    """holm_p: for a primary row, its Holm-adjusted p; a row that is not significant after
    Holm is not a difference, whatever its intervals say. None for exploratory rows."""
    m = p["log_mean_pct"]
    own = not (p["log_lo_pct"] <= 0.0 <= p["log_hi_pct"])
    wide = abs(m) > w
    if abs(m) < 1.0:
        return "within the A/A spread (< 1%)"
    if holm_p is not None and holm_p > 0.05:
        return "not resolved after Holm" + (" (about %+.1f%%)" % pct(m) if own else "")
    if wide:
        return "differs"
    if own:
        return "about %+.1f%%, not resolved" % pct(m)
    return "not resolved"


def fmt_iv(m, lo, hi, flip=False):
    if flip:
        m, lo, hi = -m, -hi, -lo
    return "%+.2f%% [%+.2f, %+.2f]" % (pct(m), pct(lo), pct(hi))


def fmt_w(m, w, flip=False):
    if flip:
        m = -m
    return "[%+.2f, %+.2f]" % (pct(m - w), pct(m + w))


def by_round(res):
    by = experiment.current_legs(res["legs"])
    return by


def metric_vals(by, shape, a, b, key):
    get = dict((k, g) for k, _, g in experiment.METRICS)[key]
    rounds = sorted(r for (s, x, r) in by if s == shape and x == a and (shape, b, r) in by)
    ra, rb = [], []
    for r in rounds:
        try:
            va, vb = get(by[(shape, a, r)]), get(by[(shape, b, r)])
        except (KeyError, TypeError):
            continue
        if va is None or vb is None:
            continue
        ra.append(va)
        rb.append(vb)
    return rb, ra


def releases_tables(res, out, js):
    an = res["analysis"]
    shapes = [s["name"] for s in res["experiment"]["shapes"]]
    rates = {s["name"]: s["rps"] for s in res["experiment"]["shapes"]}
    by = by_round(res)
    legs = res["legs"]
    nvalid = sum(1 for m in legs if m.get("verdict", {}).get("valid") and not m.get("superseded"))
    ninv = sum(1 for m in legs if not m.get("verdict", {}).get("valid"))
    out.append("Release run: %d legs recorded, %d valid and current, %d invalid; %d rounds; primary family %d rows "
               "(Holm).\n" % (len(legs), nvalid, ninv, an["rounds_done"], an["primary_family_size"]))
    busy = {}
    for s in shapes:
        busy[s] = {a: an["shapes"][s]["arms"][a].get("sut_busy_mean") for a in an["shapes"][s]["arms"]}
    js["busy"] = busy

    out.append("### A/A of the session (%s against %s)\n" % (AA, BASE))
    out.append("| Shape @ rps | Metric | Effect [95% CI] | Half-width | Widened half-width | Holm p (run) | Pairs |")
    out.append("|---|---|---|---|---|---|---|")
    js["aa"] = {}
    for s in shapes:
        comp = an["shapes"][s]["vs_base"].get(AA, {})
        for k in ("instructions_u", "cycles_total", "p50_us", "p99_us"):
            c = comp.get(k)
            if not c:
                continue
            p = c["paired"]
            w = widened(p)
            js["aa"].setdefault(s, {})[k] = {"mean_pct": p["log_mean_pct"], "hw": p["half_width_pct"], "widened": w,
                                            "lo": p["log_lo_pct"], "hi": p["log_hi_pct"], "n": c["n"]}
            out.append("| %s @ %d | %s | %s | %.2f | %.2f | %s | %d |" % (
                s, rates[s], k, fmt_iv(p["log_mean_pct"], p["log_lo_pct"], p["log_hi_pct"]), p["half_width_pct"],
                w, ("%.3f" % c["holm_p"]) if "holm_p" in c else "–", c["n"]))
    out.append("")

    out.append("### Total cycles per request: v1.40.2 against each release (primary)\n")
    out.append("Negative = v1.40.2 is cheaper. Holm p from the run (24 rows). \"Widened\" = the interval with the "
               "between-session A/A spread added. Medians in k cycles per request.\n")
    out.append("| Shape @ rps | v1.40.2 vs | Effect [95% CI] | Widened | Holm p | v1.40.2 lower in | Median release → v1.40.2 | Verdict |")
    out.append("|---|---|---|---|---|---|---|---|")
    js["vs_base"] = {}
    for s in shapes:
        for a in ORDER[:-1]:
            comp = an["shapes"][s]["vs_base"].get(a)
            c = (comp or {}).get("cycles_total")
            if not c or c.get("status") == "insufficient":
                out.append("| %s @ %d | %s | insufficient | | | | | |" % (s, rates[s], a))
                continue
            p = c["paired"]
            w = widened(p)
            # flipped: v1.40.2 against the release
            fp = {"log_mean_pct": -p["log_mean_pct"], "log_lo_pct": -p["log_hi_pct"], "log_hi_pct": -p["log_lo_pct"]}
            v = verdict(fp, w, c.get("holm_p", 1.0))
            arm_med = an["shapes"][s]["arms"][a]["cycles_total"]["median"]
            base_med = an["shapes"][s]["arms"][BASE]["cycles_total"]["median"]
            js["vs_base"].setdefault(s, {})[a] = {"v140_vs_pct": pct(fp["log_mean_pct"]), "lo": pct(fp["log_lo_pct"]),
                                                 "hi": pct(fp["log_hi_pct"]), "widened_lo": pct(fp["log_mean_pct"] - w),
                                                 "widened_hi": pct(fp["log_mean_pct"] + w), "holm_p": c.get("holm_p"),
                                                 "n": c["n"], "verdict": v}
            out.append("| %s @ %d | %s | %s | %s | %s | %d/%d | %.1fk → %.1fk | %s |" % (
                s, rates[s], a, fmt_iv(p["log_mean_pct"], p["log_lo_pct"], p["log_hi_pct"], flip=True),
                fmt_w(p["log_mean_pct"], w, flip=True), ("%.3g" % c["holm_p"]) if "holm_p" in c else "–",
                c["pairs_lost"], c["n"], arm_med / 1e3, base_med / 1e3, v))
    out.append("")

    out.append("### Release-to-release steps, total cycles (exploratory, same paired rounds)\n")
    out.append("| Shape @ rps | Step | Effect [95% CI] | Widened | Pairs lower | Reading |")
    out.append("|---|---|---|---|---|---|")
    js["steps"] = {}
    for s in shapes:
        for i in range(1, len(ORDER)):
            old, new = ORDER[i - 1], ORDER[i]
            rb, ra = metric_vals(by, s, new, old, "cycles_total")
            if len(rb) < 6:
                continue
            p = paired(rb, ra)
            w = widened(p)
            v = verdict(p, w)
            lower = sum(1 for x, y in zip(rb, ra) if y < x)
            js["steps"].setdefault(s, {})["%s->%s" % (old, new)] = {"pct": pct(p["log_mean_pct"]),
                                                                    "lo": pct(p["log_lo_pct"]),
                                                                    "hi": pct(p["log_hi_pct"]), "widened": w,
                                                                    "n": p["n"], "reading": v}
            out.append("| %s @ %d | %s → %s | %s | %s | %d/%d | %s |" % (
                s, rates[s], old, new, fmt_iv(p["log_mean_pct"], p["log_lo_pct"], p["log_hi_pct"]),
                fmt_w(p["log_mean_pct"], w), lower, p["n"], v))
    out.append("")

    out.append("### Exploratory: v1.40.2 against each release, other metrics (interval only)\n")
    out.append("| Shape | v1.40.2 vs | instructions:u | cycles:u | cycles:k | p50 | p99 |")
    out.append("|---|---|---|---|---|---|---|")
    for s in shapes:
        for a in ORDER[:-1]:
            comp = an["shapes"][s]["vs_base"].get(a) or {}
            cells = []
            for k in ("instructions_u", "cycles_u", "cycles_k", "p50_us", "p99_us"):
                c = comp.get(k)
                if not c or c["paired"].get("half_width_pct") is None:
                    cells.append("–")
                    continue
                p = c["paired"]
                cells.append(fmt_iv(p["log_mean_pct"], p["log_lo_pct"], p["log_hi_pct"], flip=True))
            out.append("| %s | %s | %s |" % (s, a, " | ".join(cells)))
    out.append("")

    out.append("### Medians per release (valid legs)\n")
    out.append("| Shape @ rps | Release | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req (CV) | IPC:u | p50 µs | p99 µs | Envoy busy |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for s in shapes:
        for a in ORDER + [AA]:
            m = an["shapes"][s]["arms"].get(a)
            if not m or "cycles_total" not in m:
                continue
            g = lambda k: m[k]["median"]  # noqa: E731
            out.append("| %s @ %d | %s | %.1fk | %.1fk | %.1fk | %.1fk (%.1f%%) | %.2f | %.0f | %.0f | %.1f%% |" % (
                s, rates[s], a, g("instructions_u") / 1e3, g("cycles_u") / 1e3, g("cycles_k") / 1e3,
                g("cycles_total") / 1e3, m["cycles_total"]["cv_pct"], g("instructions_u") / g("cycles_u"),
                g("p50_us"), g("p99_us"), 100 * (m.get("sut_busy_mean") or 0)))
    out.append("")


EVID = {
    "jwt": ["http.ingress_http.jwt_authn.allowed", "http.ingress_http.jwt_authn.denied",
            "http.ingress_http.jwt_authn.jwt_cache_hit", "http.ingress_http.jwt_authn.jwt_cache_miss"],
    "ratelimit": ["http_local_rate_limiter.http_local_rate_limit.enabled",
                  "http_local_rate_limiter.http_local_rate_limit.enforced",
                  "http_local_rate_limiter.http_local_rate_limit.ok",
                  "http_local_rate_limiter.http_local_rate_limit.rate_limited"],
}


def rows_tables(row_runs, floor, out, js):
    rows = []
    for rd in row_runs:
        res = load(rd)
        an = experiment.analyse(res["experiment"], res["legs"], floor)
        rows.append((rd, res, an))
    prim = []
    for rd, res, an in rows:
        for s, sres in an["shapes"].items():
            for comp in sres["comparisons"]:
                c = comp.get("cycles_total")
                if c and c["paired"].get("t_p") is not None:
                    prim.append(c)
    for c, a in zip(prim, stats.holm([c["paired"]["t_p"] for c in prim])):
        c["holm_rows"] = a
    out.append("### Filter rows: total cycles per request against the baseline (primary)\n")
    out.append("Holm across the %d primary rows of the two rows. \"A/A reach\" = far end of the release run's A/A "
               "interval for the shape (same session, same baseline). Δ = difference of medians.\n" % len(prim))
    out.append("| Row | Arm vs base | Shape @ rps | Total cycles/req [95% CI] | Widened | Holm p | A/A reach | Δ cycles/req | instructions:u | p50 | p99 | Base busy → arm busy | Pairs higher | Verdict |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    js["rows"] = {}
    for rd, res, an in rows:
        name = res["experiment"]["name"]
        rates = {s["name"]: s["rps"] for s in res["experiment"]["shapes"]}
        nvalid = sum(1 for m in res["legs"] if m.get("verdict", {}).get("valid") and not m.get("superseded"))
        ninv = sum(1 for m in res["legs"] if not m.get("verdict", {}).get("valid"))
        js["rows"][name] = {"legs": len(res["legs"]), "valid": nvalid, "invalid": ninv, "rounds": an["rounds_done"],
                            "comparisons": {}}
        for s, sres in an["shapes"].items():
            for comp in sres["comparisons"]:
                c = comp["cycles_total"]
                p = c["paired"]
                w = widened(p)
                v = verdict(p, w, c.get("holm_rows", 1.0))
                far = c.get("aa_floor_far_pct")
                ex = []
                for k in ("instructions_u", "p50_us", "p99_us"):
                    e = comp.get(k)
                    ex.append(fmt_iv(e["paired"]["log_mean_pct"], e["paired"]["log_lo_pct"], e["paired"]["log_hi_pct"])
                              if e and e["paired"].get("half_width_pct") is not None else "–")
                arms = sres["arms"]
                d = arms[comp["arm"]]["cycles_total"]["median"] - arms[comp["ref"]]["cycles_total"]["median"]
                js["rows"][name]["comparisons"]["%s/%s" % (s, comp["arm"])] = {
                    "pct": pct(p["log_mean_pct"]), "lo": pct(p["log_lo_pct"]), "hi": pct(p["log_hi_pct"]),
                    "widened_lo": pct(p["log_mean_pct"] - w), "widened_hi": pct(p["log_mean_pct"] + w),
                    "holm_rows": c.get("holm_rows"), "delta_cycles": d, "n": c["n"], "verdict": v,
                    "aa_far": far}
                out.append("| %s | %s vs %s | %s @ %d | %s | %s | %s | %s | %+.1fk | %s | %s | %s | %.1f%% → %.1f%% | %d/%d | %s |" % (
                    name, comp["arm"], comp["ref"], s, rates[s],
                    fmt_iv(p["log_mean_pct"], p["log_lo_pct"], p["log_hi_pct"]), fmt_w(p["log_mean_pct"], w),
                    ("%.3g" % c["holm_rows"]) if "holm_rows" in c else "–",
                    ("%.2f" % far) if far is not None else "–", d / 1e3, ex[0], ex[1], ex[2],
                    100 * (arms[comp["ref"]].get("sut_busy_mean") or 0), 100 * (arms[comp["arm"]].get("sut_busy_mean") or 0),
                    c["pairs_lost"], c["n"], v))
    out.append("")
    out.append("### Filter rows: what the setting did (counter deltas per request in the window, mean over valid legs)\n")
    out.append("| Row | Arm | Shape | Counter | Per request |")
    out.append("|---|---|---|---|---|")
    for rd, res, an in rows:
        name = res["experiment"]["name"]
        by = experiment.current_legs(res["legs"])
        for (s, a, r) in sorted(set((s, a, 0) for (s, a, _) in by)):
            ms = [m for (ss, aa, rr), m in by.items() if ss == s and aa == a]
            fam = "jwt" if "jwt" in a else ("ratelimit" if "ratelimit" in a else None)
            if not fam:
                continue
            for k in EVID[fam]:
                vals = []
                for m in ms:
                    dl = m.get("sut_stats_delta") or {}
                    req = (dl.get("http.ingress_http.downstream_rq_total") or
                           dl.get("http.ingress_http.downstream_rq_2xx"))
                    if req:
                        vals.append(dl.get(k, 0) / req)
                if vals:
                    out.append("| %s | %s | %s | `%s` | %.4f |" % (name, a, s, k, stats.mean(vals)))
    out.append("")


def main():
    argv = list(sys.argv[1:])
    jout = None
    if "--json" in argv:
        i = argv.index("--json")
        jout = argv[i + 1]
        del argv[i:i + 2]
    rel = load(argv[0])
    out, js = [], {}
    releases_tables(rel, out, js)
    if len(argv) > 1:
        floor = experiment.floor_from_results(rel, AA)
        rows_tables(argv[1:], floor, out, js)
    sys.stdout.write("\n".join(out) + "\n")
    if jout:
        with open(jout, "w") as f:
            json.dump(js, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
