#!/usr/bin/env python3
"""Wave 8 W8-1 tables: the scored runs, recomputed from the legs (analysis only; nothing here ran on the box).

    python3 examples/wave8w1/table.py RUNS_DIR [--json OUT]

RUNS_DIR holds pick-a.txt, pick-b.txt, pick-d.txt, pick-c.txt (each run's variant) and the run directories.

FIXED BEFORE ANY DATA (the wave 8 plan, sections 1 and 4.2, and the decisions for this session):
  metric    cycles (user + kernel) of the Envoy process per request. The patch can lose in the kernel (more and
            smaller writes), so user and kernel parts are printed beside every row, never instead of it.
  rows      the mean per-round log ratio, with the 95% t interval, the widened interval 1.96*sqrt(SE^2+0.34^2) and
            the QUOTED interval (the wider). `simple %` is expm1 of the log figure; `log points` is 100*ln(ratio).
  families  patch (Holm over 3): C1 frag-on-ch8k vs off-ch8k on b1m; C2 the same on b64k; C3 frag-on vs off on
            ngx-ch64. Rider (Holm over 2): R1 h2in-ngx vs cl-ngx on l64; R2 on l1m. T1 frag-on vs off on b1m-h2tls:
            pre-registered, no kill line, in no family.
  lines     worth proposing: C1 and C2 each save 3.0% or more. Narrow ("large chunked bodies"): C1 does, C2 does
            not. C2 does and C1 does not: reported as found, no label, not decided by the table. Killed: both under 3.0%.
            Harm stop: frag-on-cl8k vs off-cl8k (either size), C3 or T1 a cost of +1.0% or more with a quoted
            interval that excludes 0. Rider: published row when R1 is +10% or more and R2 +25% or more.
            The point estimate decides; "at the line" when the quoted interval straddles the line.
  same-build check per shape: the A2 arm vs its twin; passes when the quoted interval includes 0 and |effect| is
            under the floor (log points): 1.0 on b64k and b1m, 1.5 on ngx-ch64, b1m-h2tls, l64, l1m. On a miss a row
            of that shape is decided only when |effect| is at least three times the observed excursion; otherwise
            "Not resolved". Nothing is re-run.
  build control: off vs official (the chunked arms). +1.0% or more (simple) with a quoted interval that excludes
            0: the headline of the shape's rows is the figure against official.
  basis     Measured (a fixed row; the shape's same-build check passed, or the three-times rule holds) / Not
            resolved / Exploratory (every other row: against official, parts, the recovered share, costs).
  finding   quoted interval excludes 0, Holm p < 0.05 in its family (T1: its own t p), and the same-build rule.
Costs per arm: latency p50, p99, maximum; Envoy's allocated memory and heap at the end of the window
(server.memory_allocated, server.memory_heap_size: a fragment keeps its whole read slice alive); error counters are
evidence items (zero in every valid leg, or the leg is not valid)."""
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


t3 = _load("w7s3_table_for_w8w1", os.path.join(HERE, "..", "wave7s3", "table.py"))
row, med, medf, fmt, HEAD, valid, interval = t3.row, t3.med, t3.medf, t3.fmt, t3.HEAD, t3.valid, t3.interval

MET = "cycles_total"
EXTRA = ["cycles_u", "cycles_k", "instructions_u", "instructions_k", "context_switches", "p50_us", "p99_us"]
LINE, HARM = -3.0, 1.0
# shape -> run, floor, same-build pair, build control, fixed rows (tag, arm, ref, family), exploratory pairs
SHAPES = {
    "b1m": {"run": "a", "floor": 1.0, "aa": ("official-ch8k-A2", "official-ch8k"), "control": ("off-ch8k", "official-ch8k"),
            "rows": [("C1", "frag-on-ch8k", "off-ch8k", "patch"), ("CL-b1m", "frag-on-cl8k", "off-cl8k", "harm")],
            "other": [("frag-on-ch8k", "official-ch8k"), ("off-ch8k", "off-cl8k"), ("frag-on-ch8k", "frag-on-cl8k"), ("frag-on-ch8k", "off-cl8k")]},
    "b64k": {"run": "a", "floor": 1.0, "aa": ("official-ch8k-A2", "official-ch8k"), "control": ("off-ch8k", "official-ch8k"),
             "rows": [("C2", "frag-on-ch8k", "off-ch8k", "patch"), ("CL-b64k", "frag-on-cl8k", "off-cl8k", "harm")],
             "other": [("frag-on-ch8k", "official-ch8k"), ("off-ch8k", "off-cl8k"), ("frag-on-ch8k", "frag-on-cl8k"), ("frag-on-ch8k", "off-cl8k")]},
    "ngx-ch64": {"run": "b", "floor": 1.5, "aa": ("official-A2", "official"), "control": ("off", "official"),
                 "rows": [("C3", "frag-on", "off", "patch")], "other": [("frag-on", "official")]},
    "b1m-h2tls": {"run": "d", "floor": 1.5, "aa": ("official-A2", "official"), "control": ("off", "official"),
                  "rows": [("T1", "frag-on", "off", "none")], "other": [("frag-on", "official")]},
    "l64": {"run": "c", "floor": 1.5, "aa": ("cl-ngx-A2", "cl-ngx"), "control": None,
            "rows": [("R1", "h2in-ngx", "cl-ngx", "rider")], "other": [("h2in-ngx", "cl-ngx-A2")]},
    "l1m": {"run": "c", "floor": 1.5, "aa": ("cl-ngx-A2", "cl-ngx"), "control": None,
            "rows": [("R2", "h2in-ngx", "cl-ngx", "rider")], "other": [("h2in-ngx", "cl-ngx-A2")]},
}
ORDER = ["b1m", "b64k", "ngx-ch64", "b1m-h2tls", "l64", "l1m"]


def load(rd, run):
    try:
        var = open(os.path.join(rd, "pick-%s.txt" % run)).read().strip()
    except OSError:
        return None, [], ["no pick-%s.txt" % run], 0
    p = os.path.join(rd, var, "results.json")
    if var == "none" or not os.path.exists(p):
        return var, [], ["%s: no results.json (not run)" % var], 0
    d = json.load(open(p))
    md = d.get("metadata") or {}
    mine = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]
    sup = sum(1 for m in d["legs"] if m.get("superseded"))
    note = ("%s: %d current legs, %d valid, evidence failing %d, rounds complete %s, stop reason %s, incomplete %s, binaries unchanged at the "
            "end %s, started %s, finished %s; legs replaced by the harness %d" % (
                var, len(mine), sum(1 for m in mine if valid(m)), sum(1 for m in mine if (m.get("evidence") or {"ok": True}).get("ok") is False),
                md.get("rounds_complete"), md.get("stop_reason"), md.get("incomplete"), md.get("arms_md5_unchanged"), md.get("started_utc"),
                md.get("finished_utc"), sup))
    return var, mine, [note], sup


def gate(aa, floor):
    ok = aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] and abs(aa["log_pct"]) < floor
    reach = abs(aa["simple_pct"]) + (aa["simple_quoted"][1] - aa["simple_quoted"][0]) / 2.0
    return ok, reach, abs(aa["log_pct"])


def recovered(legs, shape):
    """Per round (off-ch8k - frag-on-ch8k) / (off-ch8k - off-cl8k), cycles per request. Exploratory."""
    by = {}
    for m in legs:
        if m.get("shape") == shape and valid(m):
            by.setdefault(m["round"], {})[m["arm"]] = (m.get("per_req") or {}).get(MET)
    d = [(x["off-ch8k"] - x["frag-on-ch8k"]) / (x["off-ch8k"] - x["off-cl8k"]) * 100.0 for _, x in sorted(by.items())
         if all(x.get(k) for k in ("off-ch8k", "frag-on-ch8k", "off-cl8k")) and x["off-ch8k"] != x["off-cl8k"]]
    if len(d) < 3:
        return None
    mu, se, hw, _ = interval(d)
    return {"n": len(d), "share_pct": mu, "t_interval": [mu - hw, mu + hw], "per_round": d}


def mem(m, k):
    return (m.get("sut_stats_end") or {}).get("server.memory_" + k)


def main(argv):
    rd = argv[0].rstrip("/")
    out = {"metric": MET, "shapes": {}, "runs": {}}
    data = {}
    for run in "abdc":
        var, legs, notes, sup = load(rd, run)
        data[run] = legs
        out["runs"][run] = {"variant": var, "notes": notes}
    try:
        out["rider"] = open(os.path.join(rd, "rider.txt")).read().strip()
    except OSError:
        out["rider"] = None
    fam = {"patch": [], "rider": []}
    for sh in ORDER:
        S = SHAPES[sh]
        for tag, a, r, f in S["rows"]:
            if f in fam:
                x = row(data[S["run"]], sh, a, r, MET)
                if x:
                    fam[f].append((tag, x["t_p"]))
    holm = {}
    for f, lst in fam.items():
        for (tag, _), p in zip(lst, stats.holm([p for _, p in lst]) if lst else []):
            holm[tag] = p
    out["holm"] = {"patch_family_rows": [t for t, _ in fam["patch"]], "rider_family_rows": [t for t, _ in fam["rider"]], "p": holm}
    print("# wave 8 W8-1: cycles (user+kernel) of the Envoy process per request")
    print("\nvariants: %s; rider: %s" % (", ".join("%s=%s" % (k, v["variant"]) for k, v in out["runs"].items()), out["rider"]))
    print("Holm families: patch %s; rider %s" % ([t for t, _ in fam["patch"]], [t for t, _ in fam["rider"]]))
    for run in "abdc":
        for n in out["runs"][run]["notes"]:
            print("- " + n)
    for sh in ORDER:
        S, legs = SHAPES[sh], [m for m in data[SHAPES[sh]["run"]] if m.get("shape") == sh]
        O = out["shapes"][sh] = {"run": S["run"], "floor_log_points": S["floor"], "medians": {}, "rows": []}
        print("\n## shape %s (run %s, floor %.1f log points)\n" % (sh, S["run"], S["floor"]))
        if not legs:
            print("- no legs (not run)")
            continue
        arms = []
        for m in legs:
            if m["arm"] not in arms:
                arms.append(m["arm"])
        print("- target rate %s req/s; rounds %s" % (sorted({m.get("target_rps") for m in legs}), sorted({m["round"] for m in legs})))
        print("\n| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs (median of "
              "legs / highest leg) | latency max µs (median / largest leg) | Envoy busy (CPUs of 4) | busiest worker share (max) | memory allocated "
              "at the window's end, MiB (median / largest) | heap size MiB (median / largest) | user cycles /req, lowest to highest leg |")
        print("|" + "---|" * 16)
        for a in sorted(arms):
            mine = [m for m in legs if m["arm"] == a and valid(m)]
            alln = [m for m in legs if m["arm"] == a]
            if not mine:
                print("| %s | 0/%d | no valid leg |" % (a, len(alln)))
                continue
            g = lambda k: med(legs, sh, a, k)  # noqa: E731
            k = lambda v, s=1e3, f="%.1fk": (f % (v / s)) if v is not None else "-"  # noqa: E731
            lm = sorted((m.get("latency_us") or {}).get("max") or 0 for m in mine)
            p99 = sorted((m.get("latency_us") or {}).get("p99") or 0 for m in mine)
            ma = sorted(x for x in (mem(m, "allocated") for m in mine) if x)
            mh = sorted(x for x in (mem(m, "heap_size") for m in mine) if x)
            cu = sorted((m.get("per_req") or {}).get("cycles_u") or 0 for m in mine)
            iu = sorted((m.get("per_req") or {}).get("instructions_u") or 0 for m in mine)
            busy = medf(legs, sh, a, lambda m: m.get("envoy_cpus_run"))
            shr = max(m.get("envoy_worker_max_share") or 0 for m in mine)
            O["medians"][a] = dict({x: g(x) for x in [MET] + EXTRA}, legs=len(alln), valid=len(mine), envoy_cpus_run=busy, worker_share_max=shr,
                                   latency_max_us=lm, p99_us_per_leg=p99, memory_allocated=ma, memory_heap_size=mh, cycles_u_range=[cu[0], cu[-1]],
                                   instructions_u_range=[iu[0], iu[-1]])
            mb = lambda v: "-" if not v else "%.1f / %.1f" % (stats.median(v) / 1048576.0, v[-1] / 1048576.0)  # noqa: E731
            print("| %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %.0f / %.0f | %.0f / %.0f | %s | %.3f | %s | %s | %.1fk to %.1fk |" % (
                a, len(mine), len(alln), k(g(MET)), k(g("cycles_u")), k(g("cycles_k")), k(g("instructions_u")), k(g("instructions_k")),
                k(g("context_switches"), 1, "%.2f"), k(g("p50_us"), 1, "%.0f"), stats.median(p99), p99[-1], stats.median(lm), lm[-1],
                "%.3f" % busy if busy is not None else "-", shr, mb(ma), mb(mh), cu[0] / 1e3, cu[-1] / 1e3))
        aa = row(legs, sh, S["aa"][0], S["aa"][1], MET)
        ok, reach, exc = False, None, None
        print("\n" + HEAD % ("same-build check, %s" % MET))
        if aa:
            ok, reach, exc = gate(aa, S["floor"])
            aa.update(kind="same-build", gate_pass=ok, reach_simple_pct=reach, excursion_log_points=exc)
            O["rows"].append(aa)
            print(fmt(aa))
            print("\nsame-build check on %s: %s (effect %+.2f log points against the floor %.1f; quoted interval [%+.2f, %+.2f] log points %s "
                  "0); reach %.2f%% (simple)" % (sh, "PASS" if ok else "MISS", aa["log_pct"], S["floor"], aa["log_quoted"][0], aa["log_quoted"][1],
                                                "includes" if aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] else "EXCLUDES", reach))
        else:
            print("| no same-build row (legs missing) |")
        O.update(same_build_pass=ok, same_build_reach_simple_pct=reach, same_build_excursion_log_points=exc)
        head_off = False
        if S["control"]:
            bc = row(legs, sh, S["control"][0], S["control"][1], MET)
            print("\n" + HEAD % ("build control (expected zero), %s" % MET))
            if bc:
                head_off = bc["simple_pct"] >= 1.0 and not (bc["log_quoted"][0] <= 0 <= bc["log_quoted"][1])
                bc.update(kind="build-control", headline_against_official=head_off)
                O["rows"].append(bc)
                print(fmt(bc))
                bi = row(legs, sh, S["control"][0], S["control"][1], "instructions_u")
                print("\nbuild control on %s: %+.2f%% [%+.2f, %+.2f] simple. Fixed rule (+1.0%% or more, interval excluding 0): %s. User "
                      "instructions per request: %s %.0f, %s %.0f (%s)" % (
                          sh, bc["simple_pct"], bc["simple_quoted"][0], bc["simple_quoted"][1],
                          "MET: the headline of this shape's rows is the figure against official" if head_off else "not met: the in-binary figure is the headline",
                          S["control"][0], med(legs, sh, S["control"][0], "instructions_u") or 0, S["control"][1],
                          med(legs, sh, S["control"][1], "instructions_u") or 0,
                          "%+.2f%% [%+.2f, %+.2f]" % (bi["simple_pct"], bi["simple_quoted"][0], bi["simple_quoted"][1]) if bi else "-"))
        O["headline_against_official"] = head_off
        print("\n" + HEAD % ("fixed rows, %s" % MET))
        for tag, a, r, f in S["rows"]:
            x = row(legs, sh, a, r, MET)
            if not x:
                print("| %s: %s vs %s | no row (legs missing) |" % (tag, a, r))
                continue
            h = holm.get(tag)
            three = exc is not None and abs(x["log_pct"]) >= 3.0 * exc
            decided = bool(aa) and (ok or three)
            basis = "Measured" if (aa and ok) else ("Measured (same-build check missed its floor; the effect is at least 3 x its excursion)" if (aa and three)
                                                    else "Not resolved (same-build check missed its floor or is missing; the effect is under 3 x its excursion)")
            p_used = h if h is not None else x["t_p"]
            excl = not (x["log_quoted"][0] <= 0 <= x["log_quoted"][1])
            x.update(tag=tag, family=f, holm_p=h, kind="fixed", basis=basis, decided=decided, excludes_zero=excl,
                     finding=bool(decided and excl and p_used < 0.05),
                     harm=bool(x["simple_pct"] >= HARM and excl))
            O["rows"].append(x)
            print(fmt(dict(x, arm="%s: %s" % (tag, a)), h) + (" finding" if x["finding"] else " not a finding") + "; basis: %s" % basis)
            for mm in ("cycles_u", "cycles_k", "instructions_u"):
                y = row(legs, sh, a, r, mm)
                if y:
                    y.update(kind="part", beside=tag)
                    O["rows"].append(y)
                    print("  %s [%s, Exploratory]: %+.2f%% [%+.2f, %+.2f] simple; paired difference %+.1fk ± %.1fk per request" % (
                        tag, mm, y["simple_pct"], y["simple_quoted"][0], y["simple_quoted"][1], y["diff_per_req"] / 1e3, y["diff_per_req_t_hw"] / 1e3))
            if S["control"]:
                ag = row(legs, sh, a, S["control"][1] if "cl8k" not in a else r, MET)
                if ag and "cl8k" not in a:
                    ag.update(kind="other", basis="Exploratory", beside=tag)
                    O["rows"].append(ag)
                    print("  beside %s, against the stock release [Exploratory]: %s vs %s %+.2f%% [%+.2f, %+.2f] simple (%d rounds)" % (
                        tag, a, S["control"][1], ag["simple_pct"], ag["simple_quoted"][0], ag["simple_quoted"][1], ag["n"]))
            for lat in ("p50_us", "p99_us"):
                y = row(legs, sh, a, r, lat)
                if y:
                    y.update(kind="part", beside=tag)
                    O["rows"].append(y)
                    print("  %s [%s, Exploratory]: %+.2f%% [%+.2f, %+.2f] simple" % (tag, lat, y["simple_pct"], y["simple_quoted"][0], y["simple_quoted"][1]))
        if sh in ("b1m", "b64k"):
            rec = recovered(legs, sh)
            O["recovered_share"] = rec
            if rec:
                print("\nrecovered share [Exploratory]: (off-ch8k minus frag-on-ch8k) over (off-ch8k minus off-cl8k), cycles per request, per round: "
                      "%.1f%% [%.1f, %.1f] (t interval, %d rounds)" % (rec["share_pct"], rec["t_interval"][0], rec["t_interval"][1], rec["n"]))
            mo, mn = O["medians"].get("off-ch8k"), O["medians"].get("frag-on-ch8k")
            if mo and mn:
                O["marker"] = {"off_user_cycles": mo["cycles_u_range"], "on_user_cycles": mn["cycles_u_range"],
                               "apart": mn["cycles_u_range"][1] < mo["cycles_u_range"][0],
                               "off_user_instructions": mo["instructions_u_range"], "on_user_instructions": mn["instructions_u_range"]}
                print("marker in the scored legs [the plan's instruction marker does not apply: the copy is one instruction per run]: user cycles per "
                      "request, lowest to highest leg: off-ch8k %.1fk to %.1fk, frag-on-ch8k %.1fk to %.1fk: ranges apart %s. User instructions: "
                      "off-ch8k %.1fk to %.1fk, frag-on-ch8k %.1fk to %.1fk" % (
                          mo["cycles_u_range"][0] / 1e3, mo["cycles_u_range"][1] / 1e3, mn["cycles_u_range"][0] / 1e3, mn["cycles_u_range"][1] / 1e3,
                          "YES" if O["marker"]["apart"] else "NO", mo["instructions_u_range"][0] / 1e3, mo["instructions_u_range"][1] / 1e3,
                          mn["instructions_u_range"][0] / 1e3, mn["instructions_u_range"][1] / 1e3))
        print("\n" + HEAD % ("exploratory, %s" % MET))
        for a, r in S["other"]:
            x = row(legs, sh, a, r, MET)
            if x:
                x.update(kind="other", basis="Exploratory")
                O["rows"].append(x)
                print(fmt(x))
        print("\nper-round log points (arm vs ref), for the reviewer:")
        for x in O["rows"]:
            if x.get("kind") in ("fixed", "same-build", "build-control"):
                print("- %s vs %s: %s" % (x["arm"], x["ref"], " ".join("%+.2f" % v for v in x["per_round_log_pct"])))
    # the fixed lines
    find = lambda tag: next((x for sh in ORDER for x in out["shapes"].get(sh, {}).get("rows", []) if x.get("tag") == tag), None)  # noqa: E731
    print("\n## the fixed lines\n")
    L = out["lines"] = {}
    for tag in ("C1", "C2", "C3", "T1", "CL-b1m", "CL-b64k", "R1", "R2"):
        x = find(tag)
        if not x:
            print("- %s: no row" % tag)
            continue
        eff, lo, hi = x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1]
        L[tag] = {"effect": eff, "quoted": [lo, hi], "decided": x["decided"], "saves_3": bool(x["decided"] and eff <= LINE),
                  "at_line_3": lo < LINE < hi, "harm": bool(x["harm"] and x["decided"]), "basis": x["basis"], "n": x["n"]}
        print("- %s (%s vs %s): %+.2f%% [%+.2f, %+.2f] simple, %d rounds; basis %s%s%s" % (
            tag, x["arm"], x["ref"], eff, lo, hi, x["n"], x["basis"],
            "; quoted interval straddles -3.0 (AT THE LINE)" if (tag in ("C1", "C2") and lo < LINE < hi) else "",
            "; HARM line met (+1.0% or more, interval excluding 0)" if x["harm"] else ""))
    c1, c2 = L.get("C1"), L.get("C2")
    if c1 and c2:
        if not (c1["decided"] and c2["decided"]):
            word = "Not resolved on at least one of C1, C2 (see the same-build checks): no label by the lines"
        elif c1["saves_3"] and c2["saves_3"]:
            word = "WORTH PROPOSING (C1 and C2 each save 3.0% or more)"
        elif c1["saves_3"]:
            word = "WORTH PROPOSING, NARROW: large chunked bodies (C1 saves 3.0% or more, C2 does not)"
        elif c2["saves_3"]:
            word = "C2 saves 3.0% or more and C1 does not: reported as found, no label; not decided by the table"
        else:
            word = "KILLED by the line (C1 and C2 both under 3.0%)"
        harm = [t for t in ("CL-b1m", "CL-b64k", "C3", "T1") if L.get(t, {}).get("harm")]
        if harm:
            word += "; HARM STOP on %s: not proposed until the cost is explained" % ", ".join(harm)
        out["verdict"] = word
        print("\nVERDICT by the fixed lines: %s" % word)
    r1, r2 = L.get("R1"), L.get("R2")
    if r1 and r2:
        pub = r1["decided"] and r2["decided"] and r1["effect"] >= 10.0 and r2["effect"] >= 25.0
        out["rider_verdict"] = "published row (R1 +10% or more and R2 +25% or more)" if pub else "stays internal: origin-dependent (or not resolved)"
        print("RIDER by the fixed line: %s" % out["rider_verdict"])
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
