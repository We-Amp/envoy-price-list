#!/usr/bin/env python3
"""Wave 7 S3 tables from a run directory's results.json, recomputed from the legs.

    python3 examples/wave7s3/table.py RUN_DIR [--json OUT]

Per shape: medians per arm; every pre-registered row as the mean per-round log ratio with the 95% t
interval, the widened interval 1.96*sqrt(SE^2+0.34^2), and the QUOTED interval (the wider of the two).
Units are written on every column: `simple %` is expm1 of the log figure (kill lines, bands and predictions
are read on simple %); `log-%` is 100*ln(ratio). Holm over the run's confirmatory rows.

A/A gate, per shape (plan section 1): the A/A row's quoted interval must include 0 and |effect| must be
under the floor, 1.0% for these published HTTP/1 shapes; like the earlier waves the floor is compared on the
log-% figure (at 1% the two units differ by 0.005 points; both are printed). s3a has two A/A rows (bare-A2
vs bare at the baseline's load, typical-A2 vs typical at the stack's load) and both must pass. A finding
needs |effect| at or above the floor, outside the A/A reach (|A/A| + its quoted half-width; the larger of
the shape's A/A rows), a quoted interval that excludes 0, and Holm p < 0.05.

A shape whose A/A misses the floor (the three-times rule, the plan's "fh rule", applied to every shape of S3):
its rows are not thrown away unread. A kill line that depends on the shape is decided only when the effect
is at least three times the observed A/A excursion (|A/A effect|, log-%, the larger of the shape's A/A
rows); otherwise the row is "Not resolved". The floor is not loosened and nothing is re-run.

Run-specific parts:
  s3a  the compounding claim: typical and typical-nosink against the predicted sums of the published single
       rows (simple %, +/-3 points), and the same in cycles (the published per-request cycle differences
       summed, over this run's bare median); lean vs typical (what settings give back); statsd datagrams
       per request; Envoy busy per arm
  s3b  candidate 11 (f10 vs f0 on s, +6% line), candidate 7 (idle-off vs f0, a saving of 3% on s or on fh),
       the route timeout's own price (timers-off-all vs idle-off)"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from epl import stats  # noqa: E402

FLOOR = 1.0
RUNS = {
    "s3a": {"aa": [("bare-A2", "bare"), ("typical-A2", "typical")],
            "conf": [("typical", "bare"), ("typical-nosink", "bare"), ("lean", "bare"), ("lean", "typical")],
            "other": [("typical", "typical-nosink"), ("lean", "typical-nosink"), ("typical-A2", "bare")]},
    "s3b": {"aa": [("f0-A2", "f0")],
            "conf": [("f10", "f0"), ("f10-off", "f0"), ("idle-off", "f0"), ("timers-off-all", "f0")],
            "other": [("timers-off-all", "idle-off"), ("f10-off", "f10")]},
}
MET = "cycles_total"
EXTRA = ["cycles_u", "cycles_k", "instructions_u", "instructions_k", "context_switches"]

# Plan 4.1, fixed before the run: additive sums of the published single rows, simple %, against bare
PREDICTED = {"typical": 40.5, "typical-nosink": 24.5, "lean": 23.6}
BAND = 3.0
# The same rows as per-request cycle differences (mean paired difference of the published runs, recomputed
# from the data tree: data/features/2026-11-17/{18-access-log,17-tracing,run-s}, data/features/2026-11-18/14b,
# data/settings-filters/{11-jwt-authn,12-local-ratelimit}); statsd: the worker part of run W, +16.0% of its
# flush-off median of 516k cycles per request (PHASE2-stats-sink.md)
PUBLISHED_CYCLES = {"log-json": 24284, "log-text": 19370, "trace-1": 37904, "gzip-idle": 27703, "jwt-cache": 23078,
                    "ratelimit": 10144, "retry": 7072, "statsd-workers": 0.160 * 516000}
STACK = {"typical": ["log-json", "trace-1", "statsd-workers", "gzip-idle", "jwt-cache", "ratelimit", "retry"],
         "typical-nosink": ["log-json", "trace-1", "gzip-idle", "jwt-cache", "ratelimit", "retry"],
         "lean": ["log-text", "trace-1", "gzip-idle", "jwt-cache", "ratelimit", "retry"]}


def val(m, metric):
    if metric in ("p50_us", "p99_us"):
        return (m.get("latency_us") or {}).get(metric[:3])
    return (m.get("per_req") or {}).get(metric)


def valid(m):
    return bool((m.get("verdict") or {}).get("valid"))


def interval(d):
    """Mean, SE, t half-width and t p-value of per-round values d (log-% or cycles)."""
    n = len(d)
    mu, sd = stats.mean(d), stats.stdev(d)
    se = sd / math.sqrt(n)
    tq = stats.t_ppf(0.975, n - 1)
    p = 2.0 * (1.0 - stats.t_cdf(abs(mu) / se, n - 1)) if se > 0 else 0.0
    return mu, se, tq * se, p


def sp(x):
    return math.expm1(x / 100.0) * 100.0


def row(legs, shape, arm, ref, metric):
    """Paired per-round log ratios arm/ref over rounds where both legs are valid."""
    by = {}
    for m in legs:
        if m.get("shape") == shape and m.get("arm") in (arm, ref) and valid(m):
            v = val(m, metric)
            if v:
                by.setdefault(m["round"], {})[m["arm"]] = v
    d = [100.0 * math.log(x[arm] / x[ref]) for r, x in sorted(by.items()) if arm in x and ref in x]
    n = len(d)
    if n < 3:
        return None
    mu, se, t_hw, p = interval(d)
    w_hw = 1.96 * math.sqrt(se * se + 0.34 ** 2)
    hw = max(t_hw, w_hw)
    dc = [x[arm] - x[ref] for r, x in sorted(by.items()) if arm in x and ref in x]
    cmu, _, chw, _ = interval(dc)
    return {"arm": arm, "ref": ref, "metric": metric, "n": n, "log_pct": mu, "log_se": se, "log_t_hw": t_hw,
            "log_widened_hw": w_hw, "log_quoted": [mu - hw, mu + hw], "which": "t" if t_hw >= w_hw else "widened",
            "simple_pct": sp(mu), "simple_quoted": [sp(mu - hw), sp(mu + hw)], "t_p": p, "up": sum(1 for x in d if x > 0),
            "per_round_log_pct": d, "diff_per_req": cmu, "diff_per_req_t_hw": chw}


def med(legs, shape, arm, metric):
    v = sorted(x for x in (val(m, metric) for m in legs if m.get("shape") == shape and m.get("arm") == arm and valid(m))
               if x is not None)
    return stats.median(v) if v else None


def medf(legs, shape, arm, fn):
    v = sorted(x for x in (fn(m) for m in legs if m.get("shape") == shape and m.get("arm") == arm and valid(m))
               if x is not None)
    return stats.median(v) if v else None


def fmt(r, holm=None):
    return "| %s vs %s | %+.2f | [%+.2f, %+.2f] | %+.2f | ±%.2f / ±%.2f (%s) | %d/%d | %.2g | %s | %+.1fk ± %.1fk |" % (
        r["arm"], r["ref"], r["simple_pct"], r["simple_quoted"][0], r["simple_quoted"][1], r["log_pct"],
        r["log_t_hw"], r["log_widened_hw"], r["which"], r["up"], r["n"], r["t_p"], "%.2g" % holm if holm is not None else "-",
        r["diff_per_req"] / 1e3, r["diff_per_req_t_hw"] / 1e3)


HEAD = ("| row (%s) | effect, simple %% | quoted 95%% interval, simple %% | effect, log-%% | half-width t / widened, log-%% "
        "(wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row "
        "names another metric) |\n|---|---|---|---|---|---|---|---|---|")


def aa_gate(aa):
    """(pass, reach in simple %, excursion in log-%) of one A/A row."""
    ok = aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] and abs(aa["log_pct"]) < FLOOR
    reach = abs(aa["simple_pct"]) + (aa["simple_quoted"][1] - aa["simple_quoted"][0]) / 2.0
    return ok, reach, abs(aa["log_pct"])


def line_reading(x, line, aa_ok, excursion, what):
    """How a kill line reads on row x: (label, text). `line` is a signed simple-% threshold; the row is on the
    far side when its effect is at or beyond it (in the line's direction)."""
    eff, lo, hi = x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1]
    beyond = eff >= line if line > 0 else eff <= line
    straddles = lo < line < hi
    side = ("at or beyond" if beyond else "short of") + " the %+.0f%% line" % line
    if not aa_ok:
        if abs(x["log_pct"]) >= 3.0 * excursion:
            lab = "Measured (A/A missed its floor; effect %.2f log-%% is at least 3 x the A/A excursion %.2f)" % (
                abs(x["log_pct"]), excursion)
        else:
            return "Not resolved", "%s: %+.2f%% [%+.2f, %+.2f]: Not resolved (A/A missed its floor; effect %.2f log-%% is under 3 x the A/A excursion %.2f log-%%)" % (
                what, eff, lo, hi, abs(x["log_pct"]), excursion)
    else:
        lab = "Measured"
    return lab, "%s: %+.2f%% [%+.2f, %+.2f], %s%s; basis: %s" % (
        what, eff, lo, hi, side, " (AT THE LINE: the quoted interval straddles it; not decided by the table)" if straddles else "", lab)


def main(argv):
    rd = argv[0].rstrip("/")
    d = json.load(open(os.path.join(rd, "results.json")))
    legs = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]
    key = [k for k in RUNS if k in os.path.basename(rd)][0]
    spec = RUNS[key]
    arms = sorted({m["arm"] for m in legs})
    shapes = sorted({m["shape"] for m in legs})
    out = {"run": os.path.basename(rd), "metric": MET, "shapes": {}, "floor_pct": FLOOR}
    print("# %s: primary metric %s (cycles user+kernel per request, Envoy process)" % (os.path.basename(rd), MET))
    print("\nlegs: %d current, %d valid; evidence failing: %d; superseded (replaced by the harness): %d; target rates: %s" % (
        len(legs), sum(1 for m in legs if valid(m)),
        sum(1 for m in legs if (m.get("evidence") or {"ok": True}).get("ok") is False),
        sum(1 for m in d["legs"] if m.get("superseded")),
        ", ".join("%s %s/s" % (s, sorted({m["target_rps"] for m in legs if m["shape"] == s})) for s in shapes)))
    conf = []
    for sh in shapes:
        for a, r in spec["conf"]:
            x = row(legs, sh, a, r, MET)
            if x:
                conf.append((sh, x))
    hp = stats.holm([x["t_p"] for _, x in conf]) if conf else []
    holm = {(sh, x["arm"], x["ref"]): p for (sh, x), p in zip(conf, hp)}
    for sh in shapes:
        S = out["shapes"][sh] = {"medians": {}, "rows": [], "aa": []}
        print("\n## shape %s\n" % sh)
        print("| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | "
              "Envoy busy (CPUs of 4) | client 2xx/s | side services, CPU share of their set (max) | busiest worker share (max) | "
              "statsd datagrams /req (median) |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for a in arms:
            mine = [m for m in legs if m["arm"] == a and m["shape"] == sh]
            if not mine:
                continue
            g = lambda k: med(legs, sh, a, k)  # noqa: E731
            k = lambda v, s=1e3, f="%.1fk": (f % (v / s)) if v is not None else "-"  # noqa: E731
            S["medians"][a] = {x: g(x) for x in [MET, "cycles_u", "cycles_k", "instructions_u", "instructions_k",
                                                 "context_switches", "p50_us", "p99_us"]}
            cr = sorted(m.get("client_rate_2xx") or 0 for m in mine)
            so = [max([(sv or {}).get("busy_of_set") or 0 for sv in (m.get("side_services") or {}).values()] or [0])
                  for m in mine]
            busy = medf(legs, sh, a, lambda m: m.get("envoy_cpus_run"))
            dg = medf(legs, sh, a, lambda m: (m.get("udp") or {}).get("datagrams_per_request"))
            S["medians"][a].update(envoy_cpus_run=busy, side_busy_max=max(so) if so else None, statsd_datagrams_per_request=dg)
            print("| %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %.1f–%.1f | %.3f | %.3f | %s |" % (
                a, sum(1 for m in mine if valid(m)), len(mine), k(g(MET)), k(g("cycles_u")), k(g("cycles_k")),
                k(g("instructions_u")), k(g("instructions_k")), k(g("context_switches"), 1, "%.2f"), k(g("p50_us"), 1, "%.0f"),
                k(g("p99_us"), 1, "%.0f"), "%.3f" % busy if busy is not None else "-", cr[0], cr[-1], max(so) if so else 0,
                max(m.get("envoy_worker_max_share") or 0 for m in mine), "%.3f" % dg if dg is not None else "-"))
        print("\n" + HEAD % ("A/A, %s" % MET))
        ok, reach, exc = True, 0.0, 0.0
        for a, r in spec["aa"]:
            aa = row(legs, sh, a, r, MET)
            if not aa:
                print("| %s vs %s: fewer than 3 paired rounds |" % (a, r))
                ok = False
                continue
            o, rc, ex = aa_gate(aa)
            S["aa"].append(dict(aa, floor_pct=FLOOR, gate_pass=o, reach_simple_pct=rc))
            print(fmt(aa) + (" PASS" if o else " FAIL"))
            ok = ok and o
            reach, exc = max(reach, rc), max(exc, ex)
        S.update(aa_pass=ok, aa_reach_simple_pct=reach, aa_excursion_log_pct=exc)
        print("\nA/A gate (shape %s, floor %.1f%%): **%s**; A/A reach %.2f%% (simple); largest A/A excursion %.2f log-%%" % (
            sh, FLOOR, "PASS" if ok else "FAIL (the three-times rule applies: a line is decided only at 3 x the excursion)", reach, exc))
        print("\n" + HEAD % ("confirmatory, %s" % MET))
        for a, r in spec["conf"]:
            x = row(legs, sh, a, r, MET)
            if not x:
                continue
            h = holm.get((sh, a, r))
            x["holm_p"] = h
            x["finding"] = bool(ok and abs(x["log_pct"]) >= FLOOR and abs(x["simple_pct"]) > reach
                                and not (x["log_quoted"][0] <= 0 <= x["log_quoted"][1]) and h is not None and h < 0.05)
            x["kind"] = "confirmatory"
            x["aa_pass"] = ok
            x["resolved_by_3x"] = bool(not ok and abs(x["log_pct"]) >= 3.0 * exc)
            S["rows"].append(x)
            tag = " finding" if x["finding"] else " not a finding" if ok else (
                " A/A FAILED: effect at least 3 x the excursion" if x["resolved_by_3x"] else " A/A FAILED: Not resolved")
            print(fmt(x, h) + tag)
        rows2 = [x for x in (row(legs, sh, a, r, MET) for a, r in spec["other"]) if x]
        if rows2:
            print("\n" + HEAD % ("exploratory, %s" % MET))
            for x in rows2:
                x["kind"] = "other"
                x["aa_pass"] = ok
                S["rows"].append(x)
                print(fmt(x))
        print("\n" + HEAD % "parts, exploratory")
        for a, r in spec["conf"] + spec["other"][:1] + spec["aa"]:
            for mm in EXTRA + ["p50_us", "p99_us"]:
                x = row(legs, sh, a, r, mm)
                if x:
                    x["kind"] = "part"
                    S["rows"].append(x)
                    print(fmt(dict(x, arm="%s [%s]" % (a, mm))))
    find = lambda sh, a, r: next((x for x in (out["shapes"].get(sh) or {}).get("rows", [])  # noqa: E731
                                  if x["kind"] in ("confirmatory", "other") and (x["arm"], x["ref"]) == (a, r)), None)
    if key == "s3a":
        S = out["shapes"].get("sx") or {}
        bare = (S.get("medians") or {}).get("bare", {}).get(MET)
        print("\n## the compounding claim (plan 4.2): the stack against the sum of the published single rows\n")
        print("| arm vs bare | measured, simple %% [quoted 95%%] | predicted sum, simple %% | measured − predicted, points | "
              "band ±%.0f | predicted in cycles (published differences summed / this run's bare median) | measured, cycles "
              "(paired difference) | reading |" % BAND)
        print("|---|---|---|---|---|---|---|---|")
        out["compounding"] = {}
        for a in ("typical-nosink", "typical", "lean"):
            x = find("sx", a, "bare")
            if not x or not bare:
                continue
            pc = sum(PUBLISHED_CYCLES[k] for k in STACK[a])
            pcp = 100.0 * pc / bare
            gap = x["simple_pct"] - PREDICTED[a]
            reading = "the rows add up" if abs(gap) <= BAND else "the stack costs more than the sum" if gap > 0 else "sub-additive"
            edge = (x["simple_quoted"][0] - PREDICTED[a] < -BAND < x["simple_quoted"][1] - PREDICTED[a]
                    or x["simple_quoted"][0] - PREDICTED[a] < BAND < x["simple_quoted"][1] - PREDICTED[a])
            out["compounding"][a] = {"measured_simple_pct": x["simple_pct"], "quoted": x["simple_quoted"],
                                     "predicted_simple_pct": PREDICTED[a], "gap_points": gap, "reading": reading,
                                     "interval_reaches_band_edge": edge, "predicted_cycles": pc, "predicted_cycles_pct": pcp,
                                     "measured_cycles": x["diff_per_req"], "bare_median": bare, "aa_pass": x["aa_pass"],
                                     "units_agree_within_1_point": abs(pcp - PREDICTED[a]) <= 1.0}
            print("| %s | %+.2f [%+.2f, %+.2f] | %+.1f | %+.2f | %s | %.1fk = %+.2f%% (%s the simple-%% sum within 1 point) | %+.1fk ± %.1fk | %s%s |" % (
                a, x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1], PREDICTED[a], gap,
                "inside" if abs(gap) <= BAND else "outside", pc / 1e3, pcp, "agrees with" if abs(pcp - PREDICTED[a]) <= 1.0 else "DIFFERS from",
                x["diff_per_req"] / 1e3, x["diff_per_req_t_hw"] / 1e3, reading,
                " (the quoted interval reaches a band edge)" if edge else ""))
        x = find("sx", "lean", "typical")
        if x:
            print("\nwhat settings give back: lean vs typical %+.2f%% [%+.2f, %+.2f] (simple), %+.1fk ± %.1fk cycles per request" % (
                x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1], x["diff_per_req"] / 1e3, x["diff_per_req_t_hw"] / 1e3))
        x = find("sx", "typical", "typical-nosink")
        if x and bare:
            print("the statsd sink inside the stack: typical vs typical-nosink %+.2f%% [%+.2f, %+.2f] of the no-sink stack, %+.1fk ± %.1fk "
                  "cycles per request = %+.2f%% of bare (published worker figure +16.0%%, %.1fk cycles)" % (
                      x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1], x["diff_per_req"] / 1e3,
                      x["diff_per_req_t_hw"] / 1e3, 100.0 * x["diff_per_req"] / bare, PUBLISHED_CYCLES["statsd-workers"] / 1e3))
            out["sink_in_stack"] = {"simple_pct_of_nosink": x["simple_pct"], "cycles": x["diff_per_req"],
                                    "pct_of_bare": 100.0 * x["diff_per_req"] / bare}
    if key == "s3b":
        out["lines"] = {}
        print("\n## kill lines (simple %; the point estimate decides; plan 4.3)\n")
        for sh in ("s", "fh"):
            S = out["shapes"].get(sh)
            if not S:
                continue
            x = find(sh, "f10", "f0")
            if x:
                lab, txt = line_reading(x, 6.0, S["aa_pass"], S["aa_excursion_log_pct"],
                                        "candidate 11, f10 vs f0 on %s%s" % (sh, "" if sh == "s" else " (no line on this shape; reading)"))
                out["lines"]["c11_" + sh] = {"label": lab, "simple_pct": x["simple_pct"], "quoted": x["simple_quoted"]}
                print("- " + txt)
            x = find(sh, "f10-off", "f0")
            if x:
                print("- f10-off vs f0 on %s: %+.2f%% [%+.2f, %+.2f] (reads as f0 when the interval includes 0 and |effect| is under the floor: %s)" % (
                    sh, x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1],
                    "yes" if x["simple_quoted"][0] <= 0 <= x["simple_quoted"][1] and abs(x["log_pct"]) < FLOOR else "no"))
            x = find(sh, "idle-off", "f0")
            if x:
                lab, txt = line_reading(x, -3.0, S["aa_pass"], S["aa_excursion_log_pct"],
                                        "candidate 7, idle-off vs f0 on %s (a saving of 3%% or more keeps the patch)" % sh)
                out["lines"]["c7_" + sh] = {"label": lab, "simple_pct": x["simple_pct"], "quoted": x["simple_quoted"]}
                print("- " + txt)
            x = find(sh, "timers-off-all", "f0")
            if x:
                print("- the full ceiling, timers-off-all vs f0 on %s: %+.2f%% [%+.2f, %+.2f] (never decides the patch)" % (
                    sh, x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1]))
            x = find(sh, "timers-off-all", "idle-off")
            if x:
                print("- the route timeout's own price, timers-off-all vs idle-off on %s: %+.2f%% [%+.2f, %+.2f], %+.1fk ± %.1fk cycles" % (
                    sh, x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1], x["diff_per_req"] / 1e3, x["diff_per_req_t_hw"] / 1e3))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
