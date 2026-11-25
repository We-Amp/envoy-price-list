#!/usr/bin/env python3
"""Wave 7 S4b table from the run directory's results.json, recomputed from the legs.

    python3 examples/wave7s4b/table.py RUN_DIR [--s4 S4_S4B_TABLE_JSON] [--json OUT]

Question, fixed before the run: the kept share of the trainer profile's gain for the profile from Envoy's
integration tests alone (pgolto-tests-it), per shape, against the 50% line; and pgolto-tests-it against
pgolto-tests (the full tests profile) directly.

Rows: the mean per-round log ratio with the 95% t interval, the widened interval 1.96*sqrt(SE^2+0.34^2) and the
QUOTED interval (the wider of the two). `simple %` is expm1 of the log figure; `log points` is 100*ln(ratio).
Holm over the run's confirmatory rows (five per shape, both shapes: ten).

Kept share, as S4 computed it: (1 - X/official) / (1 - trainer/official) from the medians of cycles per request
(simple ratios), X = pgolto-tests-it and X = pgolto-tests; beside it the per-round kept share (each round's
three legs), its mean and 95% t half-width. Added here: a widened half-width for the per-round mean,
1.96*sqrt(SE^2 + w^2), where w carries the 0.34 log points of each of the two ratios through the share
(first-order: w^2 = 0.34^2 * ((ds/da)^2 + (ds/db)^2), a and b the log ratios X/official and trainer/official,
at the medians); the quoted interval of the share is the wider of the two. The line is read on the share from
medians (the point estimate decides); "at the line" when the quoted per-round interval straddles 50.

No same-build A/A arm in this run. The reference is S4's s4b-pgo A/A on the same rig (--s4: its table JSON),
and the three arms both sessions ran (official, pgolto-trainer, pgolto-tests) are the session-to-session check:
per shape, each repeated row's difference between the sessions in log points against the root-sum-square of
the two quoted half-widths ("reproduces" when inside), the per-arm medians, and the full-tests kept share.
A finding needs |effect| at or above 1.0 log points, outside S4's A/A reach on the shape, a quoted interval
that excludes 0 and Holm p < 0.05."""
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


t3 = _load("w7s3_table_for_s4b", os.path.join(HERE, "..", "wave7s3", "table.py"))
row, med, medf, fmt, HEAD, valid, val, interval = t3.row, t3.med, t3.medf, t3.fmt, t3.HEAD, t3.valid, t3.val, t3.interval

FLOOR = 1.0
W = 0.34
MET = "cycles_total"
EXTRA = ["cycles_u", "cycles_k", "instructions_u", "instructions_k", "context_switches", "p50_us", "p99_us"]
CONF = [("pgolto-trainer", "official"), ("pgolto-tests-it", "official"), ("pgolto-tests", "official"),
        ("pgolto-tests-it", "pgolto-tests"), ("pgolto-tests-it", "pgolto-trainer")]
OTHER = [("pgolto-tests", "pgolto-trainer")]
REPEATED = [("pgolto-trainer", "official"), ("pgolto-tests", "official"), ("pgolto-tests", "pgolto-trainer")]
KILL, BAND = 50.0, (-45.0, -30.0)
BASIS = "Measured (8 paired rounds, Williams order; no A/A arm in this run: S4's A/A on the shape is the reference)"


def kept_share(legs, sh, x_arm):
    """Kept share of the trainer gain for x_arm, in %: from medians, per round, with t and widened half-widths."""
    mo, mt, mx = (med(legs, sh, a, MET) for a in ("official", "pgolto-trainer", x_arm))
    if not (mo and mt and mx) or mt >= mo:
        return None
    share = 100.0 * (1.0 - mx / mo) / (1.0 - mt / mo)
    by = {}
    for m in legs:
        if m.get("shape") == sh and valid(m) and m.get("arm") in ("official", "pgolto-trainer", x_arm):
            v = val(m, MET)
            if v:
                by.setdefault(m["round"], {})[m["arm"]] = v
    per = {r: 100.0 * (1.0 - x[x_arm] / x["official"]) / (1.0 - x["pgolto-trainer"] / x["official"])
           for r, x in sorted(by.items()) if len(x) == 3 and x["pgolto-trainer"] < x["official"]}
    out = {"arm": x_arm, "from_medians_pct": share, "median_cycles": {"official": mo, "pgolto-trainer": mt, x_arm: mx},
           "trainer_gain_simple_pct_from_medians": 100.0 * (mt / mo - 1.0),
           "arm_gain_simple_pct_from_medians": 100.0 * (mx / mo - 1.0), "per_round_pct": per,
           "under_50": share < KILL, "in_40_60_window": 40.0 <= share <= 60.0}
    if len(per) >= 3:
        pm, se, thw, _ = interval(list(per.values()))
        ea, eb = mx / mo, mt / mo
        dsa = -ea / (1.0 - eb)
        dsb = (1.0 - ea) * eb / (1.0 - eb) ** 2
        w = W * math.sqrt(dsa * dsa + dsb * dsb)  # share points: 100 * (W / 100) * the sensitivity
        whw = 1.96 * math.sqrt(se * se + w * w)
        hw = max(thw, whw)
        out.update(per_round_mean=pm, per_round_se=se, per_round_t_hw=thw, per_round_widened_hw=whw, widening_term_share_points=w,
                   quoted=[pm - hw, pm + hw], which="t" if thw >= whw else "widened",
                   at_the_line=bool(pm - hw < KILL < pm + hw), per_round_min=min(per.values()), per_round_max=max(per.values()))
    return out


def share_diff(a, b):
    """Per-round kept share of a minus b (share points), rounds both have: mean and 95% t half-width."""
    d = [a["per_round_pct"][r] - b["per_round_pct"][r] for r in sorted(a["per_round_pct"]) if r in b["per_round_pct"]]
    if len(d) < 3:
        return None
    mu, se, thw, p = interval(d)
    return {"mean_share_points": mu, "t_hw": thw, "t_p": p, "n": len(d), "per_round": d}


def main(argv):
    rd = argv[0].rstrip("/")
    d = json.load(open(os.path.join(rd, "results.json")))
    s4 = json.load(open(argv[argv.index("--s4") + 1])) if "--s4" in argv else None
    legs = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]
    arms = sorted({m["arm"] for m in legs})
    shapes = sorted({m["shape"] for m in legs}, key=lambda s: (s != "s", s))
    out = {"run": os.path.basename(rd), "metric": MET, "shapes": {}, "floor_log_points": FLOOR, "lines": {}, "repro": {}}
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
    conf = [(sh, x) for sh in shapes for x in (row(legs, sh, a, r, MET) for a, r in CONF) if x]
    hp = stats.holm([x["t_p"] for _, x in conf]) if conf else []
    holm = {(sh, x["arm"], x["ref"]): p for (sh, x), p in zip(conf, hp)}
    for sh in shapes:
        S = out["shapes"][sh] = {"medians": {}, "rows": []}
        ref = ((s4 or {}).get("shapes") or {}).get(sh) or {}
        reach = ref.get("aa_reach_simple_pct")
        S["s4_aa_reach_simple_pct"] = reach
        S["s4_aa_pass"] = ref.get("aa_pass")
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
            S["medians"][a] = {x: g(x) for x in [MET] + EXTRA}
            cr = sorted(m.get("client_rate_2xx") or 0 for m in mine)
            busy = medf(legs, sh, a, lambda m: m.get("envoy_cpus_run"))
            S["medians"][a].update(envoy_cpus_run=busy)
            print("| %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %.1f–%.1f | %.3f |" % (
                a, sum(1 for m in mine if valid(m)), len(mine), k(g(MET)), k(g("cycles_u")), k(g("cycles_k")),
                k(g("instructions_u")), k(g("instructions_k")), k(g("context_switches"), 1, "%.2f"), k(g("p50_us"), 1, "%.0f"),
                k(g("p99_us"), 1, "%.0f"), "%.3f" % busy if busy is not None else "-", cr[0], cr[-1],
                max(m.get("envoy_worker_max_share") or 0 for m in mine)))
        print("\nA/A: none in this run. Reference, S4's s4b-pgo on this shape: gate %s, A/A reach %s%% (simple)" % (
            {True: "PASS", False: "FAIL", None: "not given (--s4)"}[ref.get("aa_pass")], "%.2f" % reach if reach is not None else "-"))
        print("\n" + HEAD % ("confirmatory, %s" % MET))
        for a, r in CONF:
            x = row(legs, sh, a, r, MET)
            if not x:
                continue
            h = holm.get((sh, a, r))
            x.update(holm_p=h, kind="confirmatory", basis=BASIS,
                     finding=bool(abs(x["log_pct"]) >= FLOOR and (reach is None or abs(x["simple_pct"]) > reach)
                                  and not (x["log_quoted"][0] <= 0 <= x["log_quoted"][1]) and h is not None and h < 0.05))
            S["rows"].append(x)
            print(fmt(x, h) + (" finding" if x["finding"] else " not a finding"))
        print("\n" + HEAD % ("exploratory, %s" % MET))
        for a, r in OTHER:
            x = row(legs, sh, a, r, MET)
            if x:
                x.update(kind="other", basis="Exploratory")
                S["rows"].append(x)
                print(fmt(x))
        print("\n" + HEAD % "parts, exploratory")
        for a, r in CONF:
            for mm in EXTRA:
                x = row(legs, sh, a, r, mm)
                if x:
                    x["kind"] = "part"
                    S["rows"].append(x)
                    print(fmt(dict(x, arm="%s [%s]" % (a, mm))))
    find = lambda sh, a, r: next((x for x in (out["shapes"].get(sh) or {}).get("rows", [])  # noqa: E731
                                  if x["kind"] in ("confirmatory", "other") and (x["arm"], x["ref"]) == (a, r)), None)

    print("\n## kept share of the trainer gain (from medians of cycles per request; simple ratios; share in %)\n")
    under = {}
    for sh in shapes:
        ks = {a: kept_share(legs, sh, a) for a in ("pgolto-tests-it", "pgolto-tests")}
        for a, k in ks.items():
            if not k:
                print("- %s, %s: no kept share" % (sh, a))
                continue
            out["lines"]["%s_%s" % (a, sh)] = k
            mc = k["median_cycles"]
            print("- %s, %s: medians official %.1fk, pgolto-trainer %.1fk (%+.2f%%), %s %.1fk (%+.2f%%): kept share **%.1f%%** "
                  "(%s the 50%% line%s); per-round mean %.1f%%, 95%% t ±%.1f, widened ±%.1f (term %.2f share points), quoted "
                  "[%.1f, %.1f] (%s), rounds %d, range %.1f to %.1f; in the 40-60%% window: %s; basis: %s" % (
                      sh, a, mc["official"] / 1e3, mc["pgolto-trainer"] / 1e3, k["trainer_gain_simple_pct_from_medians"], a,
                      mc[a] / 1e3, k["arm_gain_simple_pct_from_medians"], k["from_medians_pct"],
                      "under" if k["under_50"] else "at or above",
                      "; AT THE LINE: the quoted per-round interval straddles it" if k.get("at_the_line") else "",
                      k["per_round_mean"], k["per_round_t_hw"], k["per_round_widened_hw"], k["widening_term_share_points"],
                      k["quoted"][0], k["quoted"][1], k["which"], len(k["per_round_pct"]), k["per_round_min"], k["per_round_max"],
                      "yes" if k["in_40_60_window"] else "no", BASIS))
        if ks["pgolto-tests-it"]:
            under[sh] = ks["pgolto-tests-it"]["under_50"]
        if ks["pgolto-tests-it"] and ks["pgolto-tests"]:
            dd = share_diff(ks["pgolto-tests-it"], ks["pgolto-tests"])
            x = find(sh, "pgolto-tests-it", "pgolto-tests")
            out["lines"]["it_minus_tests_" + sh] = dd
            if dd and x:
                print("  - integration-tests-only against full tests, %s: kept share %+.1f share points (per-round mean, 95%% t ±%.1f, "
                      "%d rounds; from medians %+.1f); cycles per request %+.2f%% [%+.2f, %+.2f] (simple, quoted), %+.2f log "
                      "points, %+.1fk ± %.1fk" % (
                          sh, dd["mean_share_points"], dd["t_hw"], dd["n"],
                          ks["pgolto-tests-it"]["from_medians_pct"] - ks["pgolto-tests"]["from_medians_pct"], x["simple_pct"],
                          x["simple_quoted"][0], x["simple_quoted"][1], x["log_pct"], x["diff_per_req"] / 1e3, x["diff_per_req_t_hw"] / 1e3))
        tr = find(sh, "pgolto-trainer", "official")
        if sh == "s" and tr:
            inb = BAND[0] <= tr["simple_pct"] <= BAND[1]
            out["lines"]["validity_band_s"] = {"trainer_vs_official_simple_pct": tr["simple_pct"], "inside": inb}
            print("  - validity band (pgolto-trainer vs official on s inside %.0f%% to %.0f%%): %+.2f%%: %s" % (
                BAND[1], BAND[0], tr["simple_pct"], "inside" if inb else "OUTSIDE: the run is HELD"))
    if under:
        if len(under) == 2 and all(under.values()):
            v = "UNDER the line on s and on fh: the integration-tests-only profile is also under 50%"
        elif not any(under.values()):
            v = "AT OR ABOVE the line on %s: the integration-tests-only profile keeps at least 50%%" % " and ".join(under)
        else:
            v = "SPLIT: under 50%% on %s, at or above on %s" % (" and ".join(k for k, x in under.items() if x),
                                                                " and ".join(k for k, x in under.items() if not x))
        out["lines"]["verdict"] = v
        print("\nline (50%%, pgolto-tests-it, share from medians): %s" % v)

    if s4:
        print("\n## the repeated arms against S4's s4b-pgo (session-to-session check)\n")
        print("| shape | item | S4 | this run | difference | allowance | reproduces |\n|---|---|---|---|---|---|---|")
        for sh in shapes:
            R = out["repro"][sh] = {"rows": [], "medians": {}}
            old = (s4["shapes"].get(sh) or {})
            for a, r in REPEATED:
                x = find(sh, a, r)
                o = next((y for y in old.get("rows", []) if y.get("kind") in ("confirmatory", "other")
                          and (y["arm"], y["ref"]) == (a, r)), None)
                if not x or not o:
                    continue
                dlt = x["log_pct"] - o["log_pct"]
                hx = (x["log_quoted"][1] - x["log_quoted"][0]) / 2.0
                ho = (o["log_quoted"][1] - o["log_quoted"][0]) / 2.0
                allow = math.sqrt(hx * hx + ho * ho)
                okr = abs(dlt) <= allow
                R["rows"].append({"arm": a, "ref": r, "s4_log_points": o["log_pct"], "this_log_points": x["log_pct"],
                                  "s4_simple_pct": o["simple_pct"], "this_simple_pct": x["simple_pct"],
                                  "diff_log_points": dlt, "allowance_log_points": allow, "reproduces": okr})
                print("| %s | %s vs %s, simple %% (log points) | %+.2f (%+.2f) | %+.2f (%+.2f) | %+.2f log points | ±%.2f log points "
                      "(root-sum-square of the two quoted half-widths) | %s |" % (
                          sh, a, r, o["simple_pct"], o["log_pct"], x["simple_pct"], x["log_pct"], dlt, allow, "yes" if okr else "NO"))
            for a in ("official", "pgolto-trainer", "pgolto-tests"):
                mo = ((old.get("medians") or {}).get(a) or {}).get(MET)
                mn = (out["shapes"][sh]["medians"].get(a) or {}).get(MET)
                if mo and mn:
                    R["medians"][a] = {"s4": mo, "this": mn, "diff_simple_pct": 100.0 * (mn / mo - 1.0)}
                    print("| %s | %s median, cycles per request | %.1fk | %.1fk | %+.2f%% (simple) | (reading; S4 A/A reach %s%%) | - |" % (
                        sh, a, mo / 1e3, mn / 1e3, 100.0 * (mn / mo - 1.0),
                        "%.2f" % old["aa_reach_simple_pct"] if old.get("aa_reach_simple_pct") is not None else "-"))
            ko = (s4.get("lines") or {}).get("c2_" + sh)
            kn = out["lines"].get("pgolto-tests_" + sh)
            if ko and kn:
                dlt = kn["from_medians_pct"] - ko["kept_share_pct_from_medians"]
                dpr = kn["per_round_mean"] - ko["per_round_mean"]
                hn = (kn["quoted"][1] - kn["quoted"][0]) / 2.0
                allow = math.sqrt(hn * hn + ko["per_round_t_hw"] ** 2)
                okr = abs(dpr) <= allow
                R["kept_share_tests"] = {"s4_from_medians": ko["kept_share_pct_from_medians"], "this_from_medians": kn["from_medians_pct"],
                                         "s4_per_round_mean": ko["per_round_mean"], "this_per_round_mean": kn["per_round_mean"],
                                         "diff_from_medians": dlt, "diff_per_round_mean": dpr, "allowance_share_points": allow,
                                         "reproduces": okr}
                print("| %s | kept share, pgolto-tests, from medians (per-round mean), %% | %.1f (%.1f) | %.1f (%.1f) | %+.1f (%+.1f) share "
                      "points | ±%.1f share points on the per-round mean (root-sum-square of S4's t half-width and this run's quoted "
                      "half-width) | %s |" % (sh, ko["kept_share_pct_from_medians"], ko["per_round_mean"], kn["from_medians_pct"],
                                              kn["per_round_mean"], dlt, dpr, allow, "yes" if okr else "NO"))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
