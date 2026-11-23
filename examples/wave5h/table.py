#!/usr/bin/env python3
"""Track H tables and the decision rules fixed before the runs, offline, from the runs' legs.

    python3 examples/wave5h/table.py block BLOCK_DIR [--json OUT]
    python3 examples/wave5h/table.py cross A_DIR B_DIR C_DIR [--pl-off D_DIR] [--json OUT]
    python3 examples/wave5h/table.py defer H0_DIR [--json OUT]

block  the same-boot rows of one block: the A/A of every run and shape, c1 - ka per connection (h-c1),
       ssbd and ibp against base (h-spec, with the h-pl A/A on s of the same block as its floor).
cross  the price of the boot-time mitigations: per shape the level of each boot (mean over the rounds of
       the per-round mean of 100 ln(metric) over the level arms), P = (A + C)/2 - B ("on minus off"),
       the A - C difference as the boot-to-boot floor, and the verdict by the rules fixed before the runs.
defer  TCP_DEFER_ACCEPT against the idle states: the p50 effect of c1-defer against c1 with default idle
       states and with C1 only on Envoy's CPUs, their difference, and the verdict.

Effects are in log points (100 ln ratio; 1 log point is about 1%); percent columns are 100 (e^(x/100) - 1).
Legs that are warm-ups, superseded, re-run originals or invalid are left out.
"""

import argparse
import json
import math
import os
import sys

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
       11: 2.201, 12: 2.179}
WIDEN = 0.34  # log points: the method's widened interval 1.96 sqrt(SE^2 + 0.34^2)
METRICS = ("cycles_total", "cycles_u", "cycles_k", "instructions_u", "instructions_k")
# the level arms of each run and shape in the cross-boot rows (every arm that runs the same config)
LEVEL = {("h-pl", "s"): ("base", "base-A2"), ("h-pl", "fh"): ("base", "base-A2"),
         ("h-c1", "c1"): ("c1",), ("h-c1", "ka"): ("ka", "ka-A2")}
CONFIRMATORY = (("h-pl", "s"), ("h-pl", "fh"), ("h-c1", "c1"))
KILL = 2.0           # log points: under this the mitigations are not worth an operator's attention
BOOT_NOISE_MAX = 2.0  # |A - C| at or above this: that shape's cross-boot row is inconclusive
INSTR_U_MAX = 0.5    # |difference| of user instructions per request between any two boots (workload identity)


def legs(run_dir):
    """Scored, valid legs of a run: {(round, shape, arm): leg}; a re-run replaces the earlier attempt."""
    rows, sup = [], set()
    with open(os.path.join(run_dir, "legs.jsonl")) as f:
        for ln in f:
            m = json.loads(ln)
            if "supersede" in m:
                sup.update(m["supersede"])
            elif "arm" in m:
                rows.append(m)
    out = {}
    for m in rows:
        if m.get("warmup") or m.get("superseded") or m.get("leg_id") in sup:
            continue
        if not (m.get("verdict") or {}).get("valid"):
            continue
        out[(m["round"], m["shape"], m["arm"])] = m
    return out


def value(m, metric):
    if metric in ("p50_us", "p99_us"):
        return (m.get("latency_us") or {}).get(metric[:3])
    return (m.get("per_req") or {}).get(metric)


def lg(x):
    return 100.0 * math.log(x)


def mean_se(xs):
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan"), 0
    mu = sum(xs) / n
    if n < 2:
        return mu, float("nan"), n
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
    return mu, sd / math.sqrt(n), n


def pct(x):
    return 100.0 * (math.exp(x / 100.0) - 1.0)


def paired(L, arm, ref, metric, shape):
    """Per-round log ratio arm/ref on one shape: mean, t half-width, widened half-width, n, rounds up,
    and the paired raw difference (arm - ref) with its t half-width."""
    d, raw = [], []
    for (r, s, a), m in L.items():
        if s != shape or a != arm:
            continue
        o = L.get((r, s, ref))
        if not o:
            continue
        x, y = value(m, metric), value(o, metric)
        if x and y:
            d.append(lg(x) - lg(y))
            raw.append(x - y)
    mu, se, n = mean_se(d)
    rmu, rse, _ = mean_se(raw)
    t = T95.get(n - 1, 1.96) if n >= 2 else float("nan")
    return {"arm": arm, "ref": ref, "shape": shape, "metric": metric, "n": n, "effect": mu,
            "t_hw": t * se, "widened_hw": 1.96 * math.sqrt(se ** 2 + WIDEN ** 2) if n >= 2 else float("nan"),
            "up": sum(1 for x in d if x > 0), "raw": rmu, "raw_t_hw": t * rse}


def hw(row):
    return max(row["t_hw"], row["widened_hw"])


def aa_ok(row):
    """The A/A rule: the widened interval includes 0."""
    return row["n"] >= 6 and abs(row["effect"]) <= row["widened_hw"]


def reach(row):
    """The A/A reach: |mean| + t half-width (an effect inside it is not a finding)."""
    return abs(row["effect"]) + row["t_hw"]


def fmt(row, unit=""):
    return "%+.2f [%+.2f, %+.2f] (n %d, %d up; %+.0f%s)" % (
        row["effect"], row["effect"] - hw(row), row["effect"] + hw(row), row["n"], row["up"], row["raw"], unit)


# ---------------------------------------------------------------- block

def block(bdir):
    out = {"block": os.path.basename(os.path.normpath(bdir)), "rows": [], "notes": []}
    runs = {r: os.path.join(bdir, r) for r in ("h-pl", "h-c1", "h-spec")
            if os.path.exists(os.path.join(bdir, r, "legs.jsonl"))}
    aa_s = None
    for run, path in sorted(runs.items()):
        L = legs(path)
        if run == "h-pl":
            for sh in ("s", "fh"):
                r = paired(L, "base-A2", "base", "cycles_total", sh)
                r.update(run=run, row="A/A", aa_pass=aa_ok(r), reach=reach(r))
                out["rows"].append(r)
                if sh == "s":
                    aa_s = r
        elif run == "h-c1":
            r = paired(L, "ka-A2", "ka", "cycles_total", "s")
            r.update(run=run, row="A/A", aa_pass=aa_ok(r), reach=reach(r))
            out["rows"].append(r)
            for mt in ("cycles_total", "cycles_u", "cycles_k"):
                c = paired(L, "c1", "ka", mt, "s")
                c.update(run=run, row="per connection (c1 - ka), %s" % mt)
                out["rows"].append(c)
        elif run == "h-spec":
            for arm in ("ssbd", "ibp"):
                for mt in ("cycles_total", "cycles_u", "cycles_k"):
                    c = paired(L, arm, "base", mt, "s")
                    c.update(run=run, row="%s vs base, %s" % (arm, mt))
                    if mt == "cycles_total":
                        c["verdict"] = spec_verdict(c, aa_s)
                    out["rows"].append(c)
    return out


def spec_verdict(row, aa):
    """Within-boot finding: |effect| >= 1, outside the same block's h-pl A/A reach on s,
    widened interval excluding 0. (Holm over the two rows is read from results.json.)"""
    if aa is None or not aa_ok(aa):
        return "no verdict: the same block's h-pl A/A on s is missing or failed"
    e = row["effect"]
    if row["n"] < 6:
        return "insufficient (fewer than 6 pairs)"
    if abs(e) >= 1.0 and abs(e) > reach(aa) and abs(e) > row["widened_hw"]:
        return "finding: %+.1f%%" % pct(e)
    return "no measurable effect (under 1%% or inside the A/A reach %.2f)" % reach(aa)


# ---------------------------------------------------------------- cross

def level(L, arms, shape, metric):
    """Per-round level: the mean of 100 ln(metric) over the level arms with a valid leg in that round."""
    by = {}
    for (r, s, a), m in L.items():
        if s == shape and a in arms and value(m, metric):
            by.setdefault(r, []).append(lg(value(m, metric)))
    per = [sum(v) / len(v) for _, v in sorted(by.items())]
    mu, se, n = mean_se(per)
    return {"level": mu, "se": se, "rounds": n}


def shape_of(run, sh):
    # h-c1 runs one shape (s); its c1 and ka "shapes" in LEVEL are arm groups on that shape
    return "s" if run == "h-c1" else sh


def cross(dirs, pl_off=None):
    """pl_off: the directory of a second off boot (block D) whose h-pl run replaces B's h-pl in every h-pl row
    (the rule fixed before block D ran); B's h-c1 is used as it is."""
    names = ("A", "B", "C")
    Ls = {}
    for n, d in zip(names, dirs):
        for run in ("h-pl", "h-c1"):
            src = pl_off if (n == "B" and run == "h-pl" and pl_off) else d
            p = os.path.join(src, run, "legs.jsonl")
            Ls[(n, run)] = legs(os.path.dirname(p)) if os.path.exists(p) else {}
    out = {"rows": [], "aa": [], "identity": [], "verdicts": {}, "pl_off": pl_off}
    # 1. every block's own A/A (rule 5.1): a failed A/A takes that block's run out of the cross rows
    bad = set()
    for n in names:
        for run, arm, ref, shapes in (("h-pl", "base-A2", "base", ("s", "fh")), ("h-c1", "ka-A2", "ka", ("s",))):
            for sh in shapes:
                r = paired(Ls[(n, run)], arm, ref, "cycles_total", sh)
                r.update(block=n, run=run, aa_pass=aa_ok(r))
                out["aa"].append(r)
                if not r["aa_pass"]:
                    bad.add((n, run))
    for (run, sh), arms in sorted(LEVEL.items()):
        for mt in METRICS:
            lv = {n: level(Ls[(n, run)], arms, shape_of(run, sh), mt) for n in names}
            a, b, c = (lv[n]["level"] for n in names)
            sa, sb, sc = (lv[n]["se"] for n in names)
            P = (a + c) / 2.0 - b
            D = a - c
            row = {"run": run, "shape": sh, "metric": mt, "levels": lv, "P": P, "P_pct": pct(P),
                   "P_A": a - b, "P_C": c - b, "D": D,
                   "P_hw": 1.96 * math.sqrt(sb ** 2 + (sa ** 2 + sc ** 2) / 4.0 + WIDEN ** 2),
                   "R": abs(D) + 1.96 * math.sqrt(sa ** 2 + sc ** 2 + WIDEN ** 2),
                   "excluded_blocks": sorted(n for n in names if (n, run) in bad)}
            out["rows"].append(row)
            if mt == "instructions_u":
                worst = max(abs(a - b), abs(a - c), abs(b - c))
                out["identity"].append({"run": run, "shape": sh, "max_diff": worst, "ok": worst <= INSTR_U_MAX})
    # 2. verdicts on the primary metric, confirmatory shapes (rules 5.2-5.4)
    ident_ok = all(x["ok"] for x in out["identity"])
    for run, sh in CONFIRMATORY:
        row = next(r for r in out["rows"] if r["run"] == run and r["shape"] == sh and r["metric"] == "cycles_total")
        out["verdicts"]["%s/%s" % (run, sh)] = cross_verdict(row, ident_ok)
    out["kill"] = kill_line(out["verdicts"])
    return out


def cross_verdict(row, ident_ok):
    if row["excluded_blocks"]:
        return "invalid: the A/A of block(s) %s failed" % ",".join(row["excluded_blocks"])
    if not ident_ok:
        return "withheld: user instructions per request differ by more than %.1f between boots" % INSTR_U_MAX
    if any(math.isnan(x) for x in (row["P"], row["D"], row["P_hw"])):
        return "insufficient data"
    if abs(row["D"]) >= BOOT_NOISE_MAX:
        return "inconclusive: A - C = %+.2f, boot-to-boot noise at the kill line" % row["D"]
    P = row["P"]
    same_sign = row["P_A"] * row["P_C"] > 0 and min(abs(row["P_A"]), abs(row["P_C"])) >= KILL
    if abs(P) >= KILL and abs(P) > row["R"] and abs(P) > row["P_hw"] and same_sign:
        return "finding: mitigations on cost %+.1f%% (P %+.2f, reach %.2f)" % (pct(P), P, row["R"])
    return "under the kill line or inside the boot-to-boot reach (P %+.2f, reach %.2f)" % (P, row["R"])


def kill_line(v):
    fs = {k for k, x in v.items() if x.startswith("finding")}
    if any(x.startswith(("invalid", "withheld", "inconclusive", "insufficient")) for x in v.values()):
        return "open: at least one confirmatory row has no verdict (see verdicts)"
    if not fs:
        return "killed: under 2% on every shape; the syscall-count follow-ups are dropped"
    if fs == {"h-c1/c1"}:
        return "only the churn shape pays: syscall trimming matters for one-request connections only"
    return "a price row on: " + ", ".join(sorted(fs))


# ---------------------------------------------------------------- defer

def defer(h0):
    out = {"runs": {}}
    for run in ("h-defer-deep", "h-defer-c1only"):
        L = legs(os.path.join(h0, run))
        rr = {"aa_cycles": paired(L, "c1-A2", "c1", "cycles_total", "s"),
              "aa_p50": paired(L, "c1-A2", "c1", "p50_us", "s"),
              "defer_p50": paired(L, "c1-defer", "c1", "p50_us", "s"),
              "defer_p99": paired(L, "c1-defer", "c1", "p99_us", "s"),
              "defer_cycles": paired(L, "c1-defer", "c1", "cycles_total", "s"),
              "c1_p50_us": mean_se([value(m, "p50_us") for (r, s, a), m in L.items() if a == "c1"])[0],
              "c1_cycles": mean_se([value(m, "cycles_total") for (r, s, a), m in L.items() if a == "c1"])[0]}
        rr["aa_pass"] = aa_ok(rr["aa_cycles"])
        out["runs"][run] = rr
    out["verdict"] = defer_verdict(out["runs"]["h-defer-deep"], out["runs"]["h-defer-c1only"])
    return out


def defer_verdict(d, p):
    """The TCP_DEFER_ACCEPT rules fixed before the run, in order."""
    if not (d["aa_pass"] and p["aa_pass"]):
        return "invalid: a run's A/A on cycles failed"
    dd, dp = d["defer_p50"], p["defer_p50"]
    if dd["n"] < 6 or dp["n"] < 6:
        return "insufficient (fewer than 6 pairs)"
    if not (dd["effect"] >= 5.0 and dd["effect"] > reach(d["aa_p50"]) and dd["effect"] - dd["t_hw"] > 0):
        return "not replicated: default-idle p50 effect %+.2f (E2b +11.9 log points); no latency statement" % dd["effect"]
    i = dd["effect"] - dp["effect"]
    se_d = dd["t_hw"] / T95[dd["n"] - 1]
    se_p = dp["t_hw"] / T95[dp["n"] - 1]
    i_hw = T95[min(dd["n"], dp["n"]) - 1] * math.sqrt(se_d ** 2 + se_p ** 2)
    tag = "interaction %+.2f +/- %.2f log points (default %+.2f, C1 only %+.2f)" % (i, i_hw, dd["effect"], dp["effect"])
    if dp["effect"] <= 0.5 * dd["effect"] and i - i_hw > 0:
        return "supported: deep idle states explain most of the shift; " + tag
    if i - i_hw <= 0 or dp["effect"] >= 0.75 * dd["effect"]:
        return "rejected: the shift does not depend on the idle states; " + tag
    return "partly: the idle states explain part of the shift; " + tag


# ---------------------------------------------------------------- output

def md_block(b):
    print("## Block %s\n" % b["block"])
    print("| Run | Row | Shape | Effect, log points [95%] (n, up; paired raw) | Verdict |")
    print("|---|---|---|---|---|")
    for r in b["rows"]:
        v = r.get("verdict") or ("A/A %s, reach %.2f" % ("pass" if r.get("aa_pass") else "FAIL", r["reach"])
                                 if r["row"] == "A/A" else "")
        print("| %s | %s | %s | %s | %s |" % (r["run"], r["row"], r["shape"], fmt(r), v))
    print()


def md_cross(x):
    print("## Cross-boot rows (P = (A + C)/2 - B, log points; on minus off)%s\n" % (
        "; h-pl rows: B = block D (%s)" % x["pl_off"] if x.get("pl_off") else ""))
    print("| Run/shape | Metric | A | B | C | P [hw] | % | A - C | reach |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in x["rows"]:
        lv = r["levels"]
        print("| %s/%s | %s | %.2f (%d) | %.2f (%d) | %.2f (%d) | %+.2f [%.2f] | %+.1f | %+.2f | %.2f |" % (
            r["run"], r["shape"], r["metric"], lv["A"]["level"], lv["A"]["rounds"], lv["B"]["level"],
            lv["B"]["rounds"], lv["C"]["level"], lv["C"]["rounds"], r["P"], r["P_hw"], r["P_pct"], r["D"], r["R"]))
    print("\nA/A per block: " + "; ".join("%s %s/%s %+.2f (%s)" % (a["block"], a["run"], a["shape"], a["effect"],
                                                                    "pass" if a["aa_pass"] else "FAIL") for a in x["aa"]))
    print("User-instruction identity: " + "; ".join("%s/%s %.2f %s" % (i["run"], i["shape"], i["max_diff"],
                                                                         "ok" if i["ok"] else "FAIL") for i in x["identity"]))
    print("\nVerdicts:")
    for k, v in sorted(x["verdicts"].items()):
        print("- %s: %s" % (k, v))
    print("- the mitigations as a price-list row: %s" % x["kill"])


def fmt_pct(row, unit=""):
    """fmt() plus the effect and its interval as a percent change."""
    h = hw(row)
    return "%s = %+.1f%% [%+.1f, %+.1f]" % (fmt(row, unit), pct(row["effect"]), pct(row["effect"] - h),
                                           pct(row["effect"] + h))


def md_defer(d):
    print("## TCP_DEFER_ACCEPT against the idle states\n")
    print("Effects in log points (100 ln ratio) [95%] (n, rounds up; paired raw difference); the latency rows also"
          " as a percent change.\n")
    for run, r in d["runs"].items():
        print("- %s: A/A cycles %s (%s); A/A p50 %s; defer p50 %s; defer p99 %s; defer cycles %s; c1 p50 %.0f us, "
              "c1 cycles %.0fk" % (run, fmt(r["aa_cycles"]), "pass" if r["aa_pass"] else "FAIL", fmt(r["aa_p50"], " us"),
                                   fmt_pct(r["defer_p50"], " us"), fmt_pct(r["defer_p99"], " us"), fmt(r["defer_cycles"]),
                                   r["c1_p50_us"], r["c1_cycles"] / 1e3))
    print("\nVerdict: %s" % d["verdict"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("block", "cross", "defer"))
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--json")
    ap.add_argument("--pl-off", help="cross: a second off boot whose h-pl replaces B's h-pl (block D)")
    a = ap.parse_args()
    if a.mode == "block":
        res = [block(d) for d in a.dirs]
        for b in res:
            md_block(b)
    elif a.mode == "cross":
        if len(a.dirs) != 3:
            ap.error("cross takes A_DIR B_DIR C_DIR")
        res = cross(a.dirs, a.pl_off)
        md_cross(res)
    else:
        res = defer(a.dirs[0])
        md_defer(res)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(res, f, indent=1, sort_keys=True, default=str)


if __name__ == "__main__":
    sys.exit(main())
