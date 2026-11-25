#!/usr/bin/env python3
"""Wave 7 S5 table: the scored runs of one shape pooled over their Williams squares, recomputed from the legs.

    python3 examples/wave7s5/table.py RUNS_DIR [--json OUT]

RUNS_DIR holds relay-1, relay-2 (shape p64, one request = two relayed messages) and http-1, http-2 (shape s).
Each run is one Williams square of six rounds; a shape's runs are pooled as rounds 1-6 and 7-12 (a round's legs
are paired inside their own run only). A run that is missing or was stopped is named.

FIXED BEFORE ANY DATA (the design of 2026-11-23; nothing below was changed after the run):
  rows      the mean per-round log ratio of cycles (user+kernel, Envoy process) per request, with the 95% t
            interval, the widened interval 1.96*sqrt(SE^2+0.34^2) and the QUOTED interval (the wider of the two).
            `simple %` is expm1 of the log figure; `log points` is 100*ln(ratio). On the relay shape the paired
            difference is also given in cycles per relayed message (per request / 2).
  confirmatory, relay (p64): both-on vs patched-off, read-only vs patched-off, write-only vs patched-off.
  confirmatory, http (s): both-on vs patched-off (no line). Holm over these four.
  LINE (relay): the two calls are "worth a patch" when both-on saves 3% or more of CPU per relayed message
            (simple %, the point estimate decides; "at the line" when the quoted interval straddles -3).
  PREDICTION (S1, Exploratory): both-on saves 7 to 11% on the relay shape; about 3% on HTTP.
  build control: patched-off vs official per shape, expected zero: "reads as official" when its quoted interval
            includes 0 and |effect| is under 1.0 log points.
  same-build check per shape: official-A2 vs official; passes when its quoted interval includes 0 and |effect|
            is under the floor of 1.0 log points. When a shape misses it, a line on that shape is decided only
            when the effect is at least three times the observed excursion; otherwise "Not resolved".
  basis     Measured (the shape's same-build check passed, or the three-times rule holds) / Not resolved /
            Exploratory (anything outside the rows above: parts, per-run rows, the sum of the two guards).
  finding   |effect| at or above 1.0 log points, outside the same-build reach (|effect| + quoted half-width of
            the same-build row, simple %), a quoted interval that excludes 0, and Holm p < 0.05."""
import importlib.util
import json
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


t3 = _load("w7s3_table_for_s5", os.path.join(HERE, "..", "wave7s3", "table.py"))
row, med, medf, fmt, HEAD, valid = t3.row, t3.med, t3.medf, t3.fmt, t3.HEAD, t3.valid

FLOOR = 1.0
MET = "cycles_total"
EXTRA = ["cycles_u", "cycles_k", "instructions_u", "instructions_k", "context_switches", "p50_us", "p99_us"]
SHAPES = {"p64": {"runs": ["relay-1", "relay-2"], "conf": [("both-on", "patched-off"), ("read-only", "patched-off"), ("write-only", "patched-off")],
                  "unit": "relayed message", "per": 2.0},
          "s": {"runs": ["http-1", "http-2"], "conf": [("both-on", "patched-off")], "unit": "request", "per": 1.0}}
AA = ("official-A2", "official")
CONTROL = ("patched-off", "official")
OTHER = [("both-on", "official"), ("read-only", "official"), ("write-only", "official"), ("both-on", "read-only"),
         ("both-on", "write-only"), ("patched-off", "official-A2")]
LINE = -3.0
PRED = (-11.0, -7.0)
ARMS = ["official", "official-A2", "patched-off", "read-only", "write-only", "both-on"]


def pooled(rd, runs):
    """(legs with rounds renumbered over the runs, per-run notes, superseded count)."""
    legs, notes, sup = [], [], 0
    for i, r in enumerate(runs):
        p = os.path.join(rd, r, "results.json")
        if not os.path.exists(p):
            notes.append("%s: no results.json (not run)" % r)
            continue
        d = json.load(open(p))
        md = d.get("metadata") or {}
        mine = [dict(m, round=m["round"] + 6 * i, run=r) for m in d["legs"] if not m.get("superseded") and m.get("arm")]
        sup += sum(1 for m in d["legs"] if m.get("superseded"))
        legs += mine
        notes.append("%s: %d current legs, %d valid, evidence failing %d, rounds complete %s, stop reason %s, incomplete %s, "
                     "binaries unchanged at the end %s, started %s, finished %s" % (
                         r, len(mine), sum(1 for m in mine if valid(m)),
                         sum(1 for m in mine if (m.get("evidence") or {"ok": True}).get("ok") is False),
                         md.get("rounds_complete"), md.get("stop_reason"), md.get("incomplete"), md.get("arms_md5_unchanged"),
                         md.get("started_utc"), md.get("finished_utc")))
    return legs, notes, sup


def gate(aa):
    ok = aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] and abs(aa["log_pct"]) < FLOOR
    reach = abs(aa["simple_pct"]) + (aa["simple_quoted"][1] - aa["simple_quoted"][0]) / 2.0
    return ok, reach, abs(aa["log_pct"])


def main(argv):
    rd = argv[0].rstrip("/")
    out = {"metric": MET, "floor_log_points": FLOOR, "line_simple_pct": LINE, "prediction_simple_pct": list(PRED), "shapes": {}}
    data = {sh: pooled(rd, spec["runs"]) for sh, spec in SHAPES.items()}
    conf = [(sh, x) for sh, spec in SHAPES.items() for x in (row(data[sh][0], sh, a, r, MET) for a, r in spec["conf"]) if x]
    hp = stats.holm([x["t_p"] for _, x in conf]) if conf else []
    holm = {(sh, x["arm"], x["ref"]): p for (sh, x), p in zip(conf, hp)}
    out["holm_family_size"] = len(conf)
    print("# wave 7 S5: cycles (user+kernel) of the Envoy process per request; pooled Williams squares per shape")
    print("\nconfirmatory rows in the Holm family: %d" % len(conf))
    for sh, spec in SHAPES.items():
        legs, notes, sup = data[sh]
        S = out["shapes"][sh] = {"runs": notes, "medians": {}, "rows": [], "superseded": sup, "unit": spec["unit"]}
        per = spec["per"]
        print("\n## shape %s (%s; unit of the price: one %s)\n" % (sh, " + ".join(spec["runs"]), spec["unit"]))
        for n in notes:
            print("- " + n)
        print("- legs replaced by the harness (superseded): %d; rounds pooled: %s" % (sup, sorted({m["round"] for m in legs})))
        if not legs:
            continue
        print("\n| arm | valid legs | cycles u+k /req (median) | per %s | user /req | kernel /req | instr user | instr kernel | ctx sw /req | "
              "p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |" % spec["unit"])
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for a in ARMS:
            mine = [m for m in legs if m["arm"] == a]
            if not mine:
                continue
            g = lambda k: med(legs, sh, a, k)  # noqa: E731
            k = lambda v, s=1e3, f="%.1fk": (f % (v / s)) if v is not None else "-"  # noqa: E731
            S["medians"][a] = {x: g(x) for x in [MET] + EXTRA}
            cr = sorted(m.get("client_rate_2xx") or 0 for m in mine)
            busy = medf(legs, sh, a, lambda m: m.get("envoy_cpus_run"))
            S["medians"][a].update(envoy_cpus_run=busy, per_unit=(g(MET) / per) if g(MET) else None)
            print("| %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %.1f–%.1f | %.3f |" % (
                a, sum(1 for m in mine if valid(m)), len(mine), k(g(MET)), k(g(MET) / per if g(MET) else None), k(g("cycles_u")),
                k(g("cycles_k")), k(g("instructions_u")), k(g("instructions_k")), k(g("context_switches"), 1, "%.2f"),
                k(g("p50_us"), 1, "%.0f"), k(g("p99_us"), 1, "%.0f"), "%.3f" % busy if busy is not None else "-", cr[0], cr[-1],
                max(m.get("envoy_worker_max_share") or 0 for m in mine)))
        aa = row(legs, sh, AA[0], AA[1], MET)
        ok, reach, exc = (False, None, None)
        print("\n" + HEAD % ("same-build check, %s" % MET))
        if aa:
            ok, reach, exc = gate(aa)
            aa.update(kind="same-build", gate_pass=ok, reach_simple_pct=reach, excursion_log_points=exc)
            S["rows"].append(aa)
            print(fmt(aa))
            print("\nsame-build check on %s: %s (effect %+.2f log points against the floor %.1f; quoted interval [%+.2f, %+.2f] log "
                  "points %s 0); reach %.2f%% (simple)" % (sh, "PASS" if ok else "FAIL", aa["log_pct"], FLOOR, aa["log_quoted"][0],
                                                          aa["log_quoted"][1], "includes" if aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] else "EXCLUDES", reach))
        else:
            print("no same-build row (legs missing)")
        S.update(same_build_pass=ok, same_build_reach_simple_pct=reach, same_build_excursion_log_points=exc)
        bc = row(legs, sh, CONTROL[0], CONTROL[1], MET)
        print("\n" + HEAD % ("build control (expected zero), %s" % MET))
        if bc:
            zero = bc["log_quoted"][0] <= 0 <= bc["log_quoted"][1] and abs(bc["log_pct"]) < FLOOR
            bc.update(kind="build-control", reads_as_official=zero)
            S["rows"].append(bc)
            print(fmt(bc))
            print("\nbuild control on %s: patched-off %s (%+.2f%% [%+.2f, %+.2f] simple; %+.1fk ± %.1fk cycles per %s)" % (
                sh, "READS AS official" if zero else "DOES NOT read as official", bc["simple_pct"], bc["simple_quoted"][0],
                bc["simple_quoted"][1], bc["diff_per_req"] / per / 1e3, bc["diff_per_req_t_hw"] / per / 1e3, spec["unit"]))
        print("\n" + HEAD % ("confirmatory, %s" % MET))
        for a, r in spec["conf"]:
            x = row(legs, sh, a, r, MET)
            if not x:
                print("| %s vs %s | no row (legs missing) |" % (a, r))
                continue
            h = holm.get((sh, a, r))
            three = exc is not None and abs(x["log_pct"]) >= 3.0 * exc
            basis = "Measured" if ok else ("Measured (same-build check missed its floor; the effect is at least 3 x its excursion)"
                                           if three else "Not resolved (same-build check missed its floor; the effect is under 3 x its excursion)")
            x.update(holm_p=h, kind="confirmatory", basis=basis, per_unit_diff=x["diff_per_req"] / per,
                     per_unit_diff_t_hw=x["diff_per_req_t_hw"] / per,
                     finding=bool(abs(x["log_pct"]) >= FLOOR and (reach is None or abs(x["simple_pct"]) > reach)
                                  and not (x["log_quoted"][0] <= 0 <= x["log_quoted"][1]) and h is not None and h < 0.05))
            S["rows"].append(x)
            print(fmt(x, h) + (" finding" if x["finding"] else " not a finding") + "; %+.2fk ± %.2fk cycles per %s; basis: %s" % (
                x["per_unit_diff"] / 1e3, x["per_unit_diff_t_hw"] / 1e3, spec["unit"], basis))
        find = lambda a, r: next((x for x in S["rows"] if x.get("kind") == "confirmatory" and (x["arm"], x["ref"]) == (a, r)), None)  # noqa: E731
        bo = find("both-on", "patched-off")
        if sh == "p64" and bo:
            eff, lo, hi = bo["simple_pct"], bo["simple_quoted"][0], bo["simple_quoted"][1]
            decided = ok or (exc is not None and abs(bo["log_pct"]) >= 3.0 * exc)
            side = "saves 3% or more: WORTH A PATCH by the line" if eff <= LINE else "saves under 3%: NOT worth a patch by the line"
            pred = ("inside the predicted 7 to 11%" if PRED[0] <= eff <= PRED[1] else
                    "SMALLER than the predicted 7 to 11%" if eff > PRED[1] else "LARGER than the predicted 7 to 11%")
            S["line"] = {"effect_simple_pct": eff, "quoted": [lo, hi], "decided": decided, "worth_a_patch": bool(eff <= LINE) if decided else None,
                         "at_the_line": bool(lo < LINE < hi), "against_prediction": pred,
                         "prediction_inside_quoted": bool(lo <= PRED[1] and hi >= PRED[0])}
            print("\nLINE (relay, both-on vs patched-off, simple %%, cycles per relayed message): %+.2f%% [%+.2f, %+.2f]: %s%s. Against "
                  "S1's prediction: %s (the quoted interval %s the predicted range). Basis: %s" % (
                      eff, lo, hi, side if decided else "Not resolved (same-build check missed its floor and the effect is under 3 x its excursion)",
                      " (AT THE LINE: the quoted interval straddles -3)" if lo < LINE < hi else "", pred,
                      "overlaps" if (lo <= PRED[1] and hi >= PRED[0]) else "does not overlap", bo["basis"]))
            ro, wo = find("read-only", "patched-off"), find("write-only", "patched-off")
            if ro and wo:
                s = ro["per_unit_diff"] + wo["per_unit_diff"]
                S["split"] = {"read_only_cycles_per_message": ro["per_unit_diff"], "write_only_cycles_per_message": wo["per_unit_diff"],
                              "sum": s, "both_on_cycles_per_message": bo["per_unit_diff"]}
                print("\nper-guard split [the two rows are confirmatory; their sum is Exploratory], cycles per relayed message: read-only "
                      "%+.2fk, write-only %+.2fk, sum %+.2fk; both-on %+.2fk (both-on minus the sum %+.2fk)" % (
                          ro["per_unit_diff"] / 1e3, wo["per_unit_diff"] / 1e3, s / 1e3, bo["per_unit_diff"] / 1e3, (bo["per_unit_diff"] - s) / 1e3))
        print("\n" + HEAD % ("exploratory, %s" % MET))
        for a, r in OTHER:
            x = row(legs, sh, a, r, MET)
            if x:
                x.update(kind="other", basis="Exploratory")
                S["rows"].append(x)
                print(fmt(x))
        print("\n" + HEAD % "parts, exploratory")
        for a, r in spec["conf"] + [CONTROL, AA]:
            for mm in EXTRA:
                x = row(legs, sh, a, r, mm)
                if x:
                    x["kind"] = "part"
                    S["rows"].append(x)
                    print(fmt(dict(x, arm="%s [%s]" % (a, mm))))
        print("\n" + HEAD % "per run (one Williams square each), exploratory")
        for i, r in enumerate(spec["runs"]):
            sub = [m for m in legs if m.get("run") == r]
            for a, rf in spec["conf"] + [CONTROL, AA]:
                x = row(sub, sh, a, rf, MET) if sub else None
                if x:
                    x.update(kind="per-run", run=r)
                    S["rows"].append(x)
                    print(fmt(dict(x, arm="%s: %s" % (r, a))))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
