#!/usr/bin/env python3
"""Wave 7 S4 tables from a run directory's results.json, recomputed from the legs.

    python3 examples/wave7s4/table.py RUN_DIR [--json OUT]

Per shape: medians per arm; every pre-registered row as the mean per-round log ratio with the 95% t interval,
the widened interval 1.96*sqrt(SE^2+0.34^2), and the QUOTED interval (the wider of the two). Units are on
every column: `simple %` is expm1 of the log figure (kill lines and bands are read on simple %); `log-%` is
100*ln(ratio). Holm over the run's confirmatory rows (both shapes).

A/A gate, per shape (plan section 1): the A/A row's quoted interval must include 0 and |effect| must be
under the floor, 1.0 for both shapes, compared in log points. A shape whose A/A misses the floor (the three-times
rule): a kill line that depends on the shape is decided only when the effect is at least three times the
observed A/A excursion (|A/A effect|, log points); otherwise the row is "Not resolved". Nothing is re-run.

Run-specific parts (rows and lines fixed before the run):
  s4a  candidate 4. Kill line: patched-0 vs notrace still above +4% (simple) on s. Within 1.5 points of the
       line (a rebuilt binary also moves code layout): "at the line", not decided by the table. Anchor reading:
       stock-0 vs notrace near +6.7%. Readings: patched-0 vs stock-0 (what the patch saves on the official
       binary's tracer cost), patched-0-guard-off vs stock-0 (the control: the build without the patch's
       path should read as the official binary), patched-0 vs patched-0-guard-off (the patch inside one
       binary), patched-1 vs stock-1 (sampled cost unchanged), patched-notrace vs notrace (layout shift
       without a tracer), points recovered = (stock-0 vs notrace) - (patched-0 vs notrace).
  s4b  candidate 2. Kept share = (1 - tests/official) / (1 - trainer/official), from the medians of cycles
       per request (simple ratios). Kill line: under 50% on s and on fh. Validity band: pgolto-trainer vs
       official on s inside -30% to -45% (simple), else held. Beside it: the per-round kept share (each
       round's three legs) with its 95% t interval, as a spread, and the 40-60% window set before the run for the
       optional integration-tests arm."""
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import stats  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


t3 = _load("w7s3_table_for_s4", os.path.join(HERE, "..", "wave7s3", "table.py"))
row, med, medf, fmt, HEAD, valid, val, interval = t3.row, t3.med, t3.medf, t3.fmt, t3.HEAD, t3.valid, t3.val, t3.interval

FLOOR = 1.0
RUNS = {
    "s4a": {"aa": [("stock-0-A2", "stock-0")],
            "conf": [("patched-0", "notrace"), ("stock-0", "notrace"), ("patched-0", "stock-0"),
                     ("patched-0-guard-off", "stock-0"), ("patched-1", "stock-1"), ("patched-notrace", "notrace")],
            "other": [("patched-0", "patched-0-guard-off"), ("patched-0", "patched-notrace"), ("stock-1", "notrace"),
                      ("patched-1", "notrace"), ("patched-0-guard-off", "notrace"), ("stock-1", "stock-0"),
                      ("patched-1", "patched-0")]},
    "s4b": {"aa": [("official-A2", "official")],
            "conf": [("pgolto-trainer", "official"), ("pgolto-tests", "official"), ("pgolto-tests", "pgolto-trainer")],
            "other": [("pgolto-trainer", "official-A2"), ("pgolto-tests", "official-A2")]},
}
MET = "cycles_total"
EXTRA = ["cycles_u", "cycles_k", "instructions_u", "instructions_k", "context_switches"]
KILL_C4, AT_LINE_C4, ANCHOR_C4 = 4.0, 1.5, 6.7
KILL_C2, BAND_C2 = 50.0, (-45.0, -30.0)


def aa_gate(aa):
    ok = aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] and abs(aa["log_pct"]) < FLOOR
    reach = abs(aa["simple_pct"]) + (aa["simple_quoted"][1] - aa["simple_quoted"][0]) / 2.0
    return ok, reach, abs(aa["log_pct"])


def basis(x, aa_ok, exc):
    """Basis label of a row on a shape: Measured, or (A/A missed its floor) Measured only at 3 x the excursion."""
    if aa_ok:
        return "Measured"
    if abs(x["log_pct"]) >= 3.0 * exc:
        return "Measured (A/A missed its floor; the effect, %.2f log points, is at least 3 x the A/A excursion %.2f)" % (
            abs(x["log_pct"]), exc)
    return "Not resolved (A/A missed its floor; the effect, %.2f log points, is under 3 x the A/A excursion %.2f)" % (
        abs(x["log_pct"]), exc)


def kept_share(legs, sh):
    """(share from medians, per-round shares) of the trainer gain the tests profile keeps, in %."""
    mo, mt, mx = (med(legs, sh, a, MET) for a in ("official", "pgolto-trainer", "pgolto-tests"))
    if not (mo and mt and mx) or mt >= mo:
        return None, [], (mo, mt, mx)
    share = 100.0 * (1.0 - mx / mo) / (1.0 - mt / mo)
    by = {}
    for m in legs:
        if m.get("shape") == sh and valid(m) and m.get("arm") in ("official", "pgolto-trainer", "pgolto-tests"):
            v = val(m, MET)
            if v:
                by.setdefault(m["round"], {})[m["arm"]] = v
    per = [100.0 * (1.0 - x["pgolto-tests"] / x["official"]) / (1.0 - x["pgolto-trainer"] / x["official"])
           for r, x in sorted(by.items()) if len(x) == 3 and x["pgolto-trainer"] < x["official"]]
    return share, per, (mo, mt, mx)


def main(argv):
    rd = argv[0].rstrip("/")
    d = json.load(open(os.path.join(rd, "results.json")))
    legs = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]
    key = [k for k in RUNS if k in os.path.basename(rd)][0]
    spec = RUNS[key]
    arms = sorted({m["arm"] for m in legs})
    shapes = sorted({m["shape"] for m in legs}, key=lambda s: (s != "s", s))
    out = {"run": os.path.basename(rd), "metric": MET, "shapes": {}, "floor_log_points": FLOOR}
    md = d.get("metadata") or {}
    print("# %s: primary metric %s (cycles user+kernel per request, Envoy process)" % (os.path.basename(rd), MET))
    print("\nlegs: %d current, %d valid; evidence failing: %d; superseded (replaced by the harness): %d; target rates: %s" % (
        len(legs), sum(1 for m in legs if valid(m)),
        sum(1 for m in legs if (m.get("evidence") or {"ok": True}).get("ok") is False),
        sum(1 for m in d["legs"] if m.get("superseded")),
        ", ".join("%s %s/s" % (s, sorted({m["target_rps"] for m in legs if m["shape"] == s})) for s in shapes)))
    pos = {id(m): i for i, m in enumerate(d["legs"])}
    order = {r: sorted({m["shape"] for m in legs if m["round"] == r},
                       key=lambda sh: min(pos[id(m)] for m in legs if m["round"] == r and m["shape"] == sh))
             for r in sorted({m["round"] for m in legs})}
    out["shape_order_by_round"] = order
    print("\nshape order by round (as run): %s" % "; ".join("r%d %s" % (r, " then ".join(v)) for r, v in order.items()))
    print("\n| arm | binary sha256 (as started) | md5 unchanged at the end | version |\n|---|---|---|---|")
    out["binaries"] = {}
    for a in arms:
        b = (md.get("arms") or {}).get(a) or {}
        out["binaries"][a] = {"sha256": b.get("sha256"), "path": b.get("path"), "version": b.get("version")}
        print("| %s | %s | %s | %s |" % (a, b.get("sha256"), md.get("arms_md5_unchanged"), (b.get("version") or "")[:12]))
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
              "Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for a in arms:
            mine = [m for m in legs if m["arm"] == a and m["shape"] == sh]
            if not mine:
                continue
            g = lambda k: med(legs, sh, a, k)  # noqa: E731
            k = lambda v, s=1e3, f="%.1fk": (f % (v / s)) if v is not None else "-"  # noqa: E731
            S["medians"][a] = {x: g(x) for x in [MET, "cycles_u", "cycles_k", "instructions_u", "instructions_k",
                                                 "context_switches", "p50_us", "p99_us"]}
            cr = sorted(m.get("client_rate_2xx") or 0 for m in mine)
            busy = medf(legs, sh, a, lambda m: m.get("envoy_cpus_run"))
            S["medians"][a].update(envoy_cpus_run=busy)
            print("| %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %.1f–%.1f | %.3f |" % (
                a, sum(1 for m in mine if valid(m)), len(mine), k(g(MET)), k(g("cycles_u")), k(g("cycles_k")),
                k(g("instructions_u")), k(g("instructions_k")), k(g("context_switches"), 1, "%.2f"), k(g("p50_us"), 1, "%.0f"),
                k(g("p99_us"), 1, "%.0f"), "%.3f" % busy if busy is not None else "-", cr[0], cr[-1],
                max(m.get("envoy_worker_max_share") or 0 for m in mine)))
        print("\n" + HEAD % ("A/A, %s" % MET))
        ok, reach, exc = True, 0.0, 0.0
        for a, r in spec["aa"]:
            aa = row(legs, sh, a, r, MET)
            if not aa:
                print("| %s vs %s: fewer than 3 paired rounds |" % (a, r))
                ok = False
                continue
            o, rc, ex = aa_gate(aa)
            S["aa"].append(dict(aa, floor_log_points=FLOOR, gate_pass=o, reach_simple_pct=rc))
            print(fmt(aa) + (" PASS" if o else " FAIL"))
            ok = ok and o
            reach, exc = max(reach, rc), max(exc, ex)
        S.update(aa_pass=ok, aa_reach_simple_pct=reach, aa_excursion_log_points=exc)
        print("\nA/A gate (shape %s, floor %.1f log points): **%s**; A/A effect %.2f log points; A/A reach %.2f%% (simple)" % (
            sh, FLOOR, "PASS" if ok else "FAIL (the three-times rule applies: a line is decided only at 3 x the excursion)", exc, reach))
        print("\n" + HEAD % ("confirmatory, %s" % MET))
        for a, r in spec["conf"]:
            x = row(legs, sh, a, r, MET)
            if not x:
                continue
            h = holm.get((sh, a, r))
            x.update(holm_p=h, kind="confirmatory", aa_pass=ok, basis=basis(x, ok, exc),
                     finding=bool(ok and abs(x["log_pct"]) >= FLOOR and abs(x["simple_pct"]) > reach
                                  and not (x["log_quoted"][0] <= 0 <= x["log_quoted"][1]) and h is not None and h < 0.05))
            S["rows"].append(x)
            print(fmt(x, h) + (" finding" if x["finding"] else " not a finding") + "; basis: " + x["basis"])
        rows2 = [x for x in (row(legs, sh, a, r, MET) for a, r in spec["other"]) if x]
        if rows2:
            print("\n" + HEAD % ("exploratory, %s" % MET))
            for x in rows2:
                x.update(kind="other", aa_pass=ok, basis="Exploratory")
                S["rows"].append(x)
                print(fmt(x))
        print("\n" + HEAD % "parts, exploratory")
        for a, r in spec["conf"] + spec["aa"]:
            for mm in EXTRA + ["p50_us", "p99_us"]:
                x = row(legs, sh, a, r, mm)
                if x:
                    x["kind"] = "part"
                    S["rows"].append(x)
                    print(fmt(dict(x, arm="%s [%s]" % (a, mm))))
    find = lambda sh, a, r: next((x for x in (out["shapes"].get(sh) or {}).get("rows", [])  # noqa: E731
                                  if x["kind"] in ("confirmatory", "other") and (x["arm"], x["ref"]) == (a, r)), None)
    out["lines"] = {}
    if key == "s4a":
        print("\n## candidate 4: the kill line and its readings (simple %; the point estimate decides)\n")
        for sh in shapes:
            S = out["shapes"][sh]
            p0, s0 = find(sh, "patched-0", "notrace"), find(sh, "stock-0", "notrace")
            if not p0 or not s0:
                continue
            eff, lo, hi = p0["simple_pct"], p0["simple_quoted"][0], p0["simple_quoted"][1]
            if sh == "s":
                if not S["aa_pass"] and abs(p0["log_pct"]) < 3.0 * S["aa_excursion_log_points"]:
                    verdict = "Not resolved"
                elif abs(eff - KILL_C4) <= AT_LINE_C4 or lo < KILL_C4 < hi:
                    verdict = "AT THE LINE (within %.1f points of +%.0f%%, or the quoted interval straddles it): not decided by the table" % (AT_LINE_C4, KILL_C4)
                elif eff > KILL_C4:
                    verdict = "KILLED by the line (still above +%.0f%%)" % KILL_C4
                else:
                    verdict = "kill line NOT met (at or under +%.0f%%)" % KILL_C4
            else:
                verdict = "no line on this shape (reading)"
            rec = s0["simple_pct"] - eff
            out["lines"]["c4_" + sh] = {"patched0_vs_notrace_simple_pct": eff, "quoted": [lo, hi], "verdict": verdict,
                                        "stock0_vs_notrace_simple_pct": s0["simple_pct"], "stock0_quoted": s0["simple_quoted"],
                                        "points_recovered": rec, "basis": p0["basis"], "aa_pass": S["aa_pass"]}
            print("- %s: patched-0 vs notrace %+.2f%% [%+.2f, %+.2f]: %s; basis: %s" % (sh, eff, lo, hi, verdict, p0["basis"]))
            print("  - anchor, stock-0 vs notrace: %+.2f%% [%+.2f, %+.2f] (published +%.1f%% on s); points recovered by the "
                  "patch: %.2f of %.2f" % (s0["simple_pct"], s0["simple_quoted"][0], s0["simple_quoted"][1], ANCHOR_C4, rec, s0["simple_pct"]))
            for a, r, what in (("patched-0", "stock-0", "the patch against the official binary at 0%"),
                               ("patched-0-guard-off", "stock-0", "the control: guard off should read as the official binary"),
                               ("patched-0", "patched-0-guard-off", "the patch inside one binary (guard on vs off)"),
                               ("patched-1", "stock-1", "sampled at 1%: cost unchanged?"),
                               ("patched-notrace", "notrace", "the build's layout shift without a tracer"),
                               ("patched-0", "patched-notrace", "the tracer at 0% inside the patched binary")):
                x = find(sh, a, r)
                if x:
                    print("  - %s vs %s (%s): %+.2f%% [%+.2f, %+.2f], %+.1fk ± %.1fk cycles per request; reads as no difference: %s" % (
                        a, r, what, x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1], x["diff_per_req"] / 1e3,
                        x["diff_per_req_t_hw"] / 1e3,
                        "yes" if x["simple_quoted"][0] <= 0 <= x["simple_quoted"][1] and abs(x["log_pct"]) < FLOOR else "no"))
    if key == "s4b":
        print("\n## candidate 2: kept share of the trainer gain (from medians of cycles per request; simple ratios)\n")
        under = {}
        for sh in shapes:
            S = out["shapes"][sh]
            share, per, (mo, mt, mx) = kept_share(legs, sh)
            tr, te = find(sh, "pgolto-trainer", "official"), find(sh, "pgolto-tests", "official")
            if share is None or not tr or not te:
                print("- %s: no kept share (medians: official %s, trainer %s, tests %s)" % (sh, mo, mt, mx))
                continue
            resolved = S["aa_pass"] or (abs(tr["log_pct"]) >= 3.0 * S["aa_excursion_log_points"]
                                        and abs(te["log_pct"]) >= 3.0 * S["aa_excursion_log_points"])
            pm, _, phw, _ = interval(per) if len(per) >= 3 else (None, None, None, None)
            straddle = pm is not None and (pm - phw) < KILL_C2 < (pm + phw)
            label = ("Measured" if S["aa_pass"] else "Measured (A/A missed its floor; both effects are at least 3 x the A/A "
                     "excursion)") if resolved else "Not resolved"
            under[sh] = (share < KILL_C2) if resolved else None
            out["lines"]["c2_" + sh] = {
                "kept_share_pct_from_medians": share, "median_cycles": {"official": mo, "pgolto-trainer": mt, "pgolto-tests": mx},
                "trainer_gain_simple_pct_from_medians": 100.0 * (mt / mo - 1.0), "tests_gain_simple_pct_from_medians": 100.0 * (mx / mo - 1.0),
                "per_round_kept_share_pct": per, "per_round_mean": pm, "per_round_t_hw": phw, "basis": label,
                "under_50": under[sh], "at_the_line": bool(straddle), "aa_pass": S["aa_pass"],
                "in_40_60_window": 40.0 <= share <= 60.0}
            print("- %s: medians official %.1fk, pgolto-trainer %.1fk (%+.2f%%), pgolto-tests %.1fk (%+.2f%%): kept share **%.1f%%** "
                  "of the trainer gain (%s the 50%% line%s); per-round kept share mean %s [95%% t ±%s] over %d rounds; basis: %s; "
                  "in the 40-60%% window: %s" % (
                      sh, mo / 1e3, mt / 1e3, 100.0 * (mt / mo - 1.0), mx / 1e3, 100.0 * (mx / mo - 1.0), share,
                      "under" if share < KILL_C2 else "at or above",
                      "; AT THE LINE: the per-round interval straddles it" if straddle else "",
                      "%.1f%%" % pm if pm is not None else "-", "%.1f" % phw if phw is not None else "-", len(per), label,
                      "yes" if 40.0 <= share <= 60.0 else "no"))
            print("  - paired rows: pgolto-trainer vs official %+.2f%% [%+.2f, %+.2f]; pgolto-tests vs official %+.2f%% [%+.2f, %+.2f] (simple)" % (
                tr["simple_pct"], tr["simple_quoted"][0], tr["simple_quoted"][1], te["simple_pct"], te["simple_quoted"][0], te["simple_quoted"][1]))
            if sh == "s":
                inb = BAND_C2[0] <= tr["simple_pct"] <= BAND_C2[1]
                out["lines"]["c2_validity_band_s"] = {"trainer_vs_official_simple_pct": tr["simple_pct"], "inside": inb}
                print("  - validity band (pgolto-trainer vs official on s inside %.0f%% to %.0f%%): %+.2f%%: %s" % (
                    BAND_C2[1], BAND_C2[0], tr["simple_pct"], "inside" if inb else "OUTSIDE: the run is HELD"))
        if under:
            if all(v is True for v in under.values()) and len(under) == 2:
                v = "KILLED by the line: the kept share is under 50% on s and on fh"
            elif under.get("s") is True and under.get("fh") is None:
                v = "the s reading is under 50%; fh Not resolved (the verdict is the s reading with that note)"
            elif under.get("s") is None:
                v = "Not resolved on s"
            else:
                v = "kill line NOT met: the kept share is at or above 50% on %s" % " and ".join(k for k, x in under.items() if x is False)
            out["lines"]["c2_verdict"] = v
            print("\nkill line (under 50%% on s and on fh): %s" % v)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
