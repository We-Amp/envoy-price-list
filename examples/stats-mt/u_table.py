#!/usr/bin/env python3
"""Tables of run U (multi-threaded stats study): what store stats cost by worker count.

    python3 examples/stats-mt/u_table.py RUN_U_DIR [--hitm U_HITM_DIR] [--json OUT.json] > u.md

Valid legs of complete rotation blocks only. Per rung (shape mt-<rung>) and round:
  Δ = base − stats-reject in worker-only cycles per request (the wrk: threads), and the log
  ratio stats-reject / base; descriptive (the level).
A/A per rung: base-A2 against base on the same metric; passes with a half-width of at most 1%
and no Holm-significant difference (Holm over the machine's A/A rows).
Growth (confirmatory): Δ(top) − Δ(1w), paired within round, 95% t interval; on the bench box
also Δ(14w-one) − Δ(1w) and the cross-socket contrast Δ(14w-split) − Δ(14w-one). One Holm
family per machine. A contrast needs the A/A of both its rungs to pass, otherwise it is
printed with its reach and no verdict. This is the price of store stats with the per-host
primitive stats still on: a lower bound on the price of all stat updates; its growth misses
the host-stat part of line transfer.
Beside it: process cycles per request, frequency (cycles / ref-cycles, rungs more than 5%
apart flagged), worker busy share, steal share, memory per NUMA node, and from the HITM
evidence run the local and remote HITM loads per request.

Run R1 ("dose", a run whose config has a `dose` block; statements pre-stated 2026-11-20):

    python3 examples/stats-mt/u_table.py DOSE_DIR [--evidence DOSE_EVIDENCE_DIR] [--json OUT.json]

Estimand per cell c: rho_c = the mean per-round 100 x ln(shared / own) of worker-only cycles per
request (log points x 100, read as percent). A/A per cell: the second own arm against own;
passes with a 95% half-width of at most 1% and unresolved (no Holm-significant difference,
Holm over the run's A/A rows, as in run U).
  S1-S3 (one per cell): a finding when all hold: the cell's A/A passes; the widened interval
    rho_c +/- 1.96 x sqrt(SE^2 + 0.34^2) excludes 0 (and the statement survives Holm over the
    five); the estimate is at least 1% and beyond the A/A's reach. A finding is called "line
    transfer" only when instructions:u per request match within 0.5% between shared and own and
    HITM:u (shared - own) per request is at least 0.5 x K (evidence legs). Every other cell is
    reported as a bound, "rho_c <= the widened interval's upper end".
  S4 (socket): rho_B - rho_A, paired by round, widened with 1.96 x sqrt(SE^2 + 2 x 0.34^2).
    Predicted +2 to +4 points.
  S5 (load): rho_C - rho_A, same form. Predicted 0 +/- 1; a resolved increase above 1 point
    refutes the "no queueing" reading (then: a load ladder). Secondary: cycles per shared update.
Model row for the plain config, always labelled a model: contention <= T x P / C, P the upper
95% end of (shared - own) / K in cycles, T the upper 95% end of HITM:u (base - stats-reject) per
request divided by h = HITM:u (shared - own) / K (beside it the store-stat operations per
request, which T should not exceed), C base worker cycles per request.
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import experiment, stats  # noqa: E402

METRIC = "workers_cycles_per_req"
AA_LIMIT_PCT = 1.0
HITM = ("mem_load_uops_l3_hit_retired.xsnp_hitm", "mem_load_uops_l3_miss_retired.remote_hitm")
# Run R1 ("dose"), pre-stated 2026-11-20
DOSE_Z = 1.96
DOSE_SYS_PCT = 0.34            # the widening term of every dose interval (log points x 100)
DOSE_MIN_EFFECT_PCT = 1.0      # a finding is at least this large
DOSE_INSTR_TOL_PCT = 0.5       # "line transfer": instructions:u per request, shared against own
DOSE_HITM_SHARE = 0.5          # "line transfer": HITM:u (shared - own) per request >= this x K
DOSE_LOAD_REFUTE_PT = 1.0      # S5: a resolved increase above this refutes "no queueing"
DOSE_PREDICTED = {"socket": "+2 to +4 points", "load": "0 +/- 1 point"}
DOSE_MODEL_EXPECTED = "0.3-0.8% on one socket, 0.6-1.7% split"


def ev_get(e, name):
    """An event's per-request value under either spelling (counted in user mode: NAME:u)."""
    v = e.get(name)
    return e.get(name + ":u") if v is None else v


def hitm_per_req(m):
    """Local plus remote HITM loads per request of a leg; None unless both were counted."""
    e = (m.get("per_req") or {}).get("events") or {}
    loc, rem = ev_get(e, HITM[0]), ev_get(e, HITM[1])
    return None if loc is None or rem is None else loc + rem


def load(d):
    p = os.path.join(d, "results.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def usable(res):
    rc = res.get("metadata", {}).get("rounds_complete")
    if rc is None:
        rc = experiment.complete_rounds(res["experiment"], res["legs"])
    return {k: m for k, m in experiment.current_legs(res["legs"]).items() if k[2] <= rc}


def val(m, key=METRIC):
    if key == METRIC:
        return m.get("workers_cycles_per_req")
    return (m.get("per_req") or {}).get(key)


def deltas(by, shape, key=METRIC):
    """{round: base − stats-reject} for one rung."""
    out = {}
    for (s, a, r), m in by.items():
        if s != shape or a != "base" or (s, "stats-reject", r) not in by:
            continue
        b, x = val(m, key), val(by[(s, "stats-reject", r)], key)
        if b is not None and x is not None:
            out[r] = b - x
    return out


def t_interval(xs):
    n = len(xs)
    if n < 2:
        return {"n": n, "mean": xs[0] if xs else None}
    mu = stats.mean(xs)
    se = stats.stdev(xs) / math.sqrt(n)
    tq = stats.t_ppf(0.975, n - 1)
    tp = 2.0 * (1.0 - stats.t_cdf(abs(mu) / se, n - 1)) if se > 0 else (0.0 if mu else 1.0)
    return {"n": n, "mean": mu, "lo": mu - tq * se, "hi": mu + tq * se, "t_p": tp}


def paired_log(by, shape, arm, ref, key=METRIC):
    rounds = sorted(r for (s, a, r) in by if s == shape and a == arm and (s, ref, r) in by
                    and val(by[(s, a, r)], key) and val(by[(s, ref, r)], key))
    return stats.paired_log_ratio([val(by[(shape, ref, r)], key) for r in rounds],
                                  [val(by[(shape, arm, r)], key) for r in rounds])


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def tables(res, hitm=None):
    exp = res["experiment"]
    box = exp.get("box") or {}
    by = usable(res)
    rungs = [s["name"] for s in exp["shapes"]]
    L, js = ["# Run U: store stats by worker count (%s)\n" % box.get("label", exp["name"])], {}
    md = res.get("metadata", {})
    L.append("Legs %d, invalid %d, complete rounds %s%s. Primary metric: worker-only cycles per request (the wrk: "
             "threads). stats-reject removes the store stats; the per-host primitive stats stay on, so the level "
             "and growth are the price of store stats, a lower bound on the price of all stat updates.\n" % (
                 len(res["legs"]), sum(1 for m in res["legs"] if not (m.get("verdict") or {}).get("valid")),
                 md.get("rounds_complete"), " (**incomplete, no verdict**)" if md.get("incomplete") else ""))
    # A/A per rung
    aa = {}
    for s in rungs:
        p = paired_log(by, s, "base-A2", "base")
        if p.get("half_width_pct") is not None:
            aa[s] = {"hw": p["half_width_pct"], "reach": max(abs(p["log_lo_pct"]), abs(p["log_hi_pct"])),
                     "t_p": p["t_p"], "n": p["n"]}
    hp = stats.holm([v["t_p"] for v in aa.values()])
    for (s, v), h in zip(aa.items(), hp):
        v["holm_p"] = h
        v["ok"] = v["hw"] <= AA_LIMIT_PCT and h > 0.05 and not md.get("incomplete")
    js["aa"] = aa
    # levels
    L.append("## Level per rung (descriptive)\n")
    L.append("| Rung | Workers | Base worker cycles/req (k) | Δ base − reject (k) [95% CI] | reject / base | A/A hw | "
             "A/A pass | Freq ratio base | Busy base | Steal max |\n|---|---|---|---|---|---|---|---|---|---|")
    lv = {}
    for sh in exp["shapes"]:
        s = sh["name"]
        d = deltas(by, s)
        t = t_interval(list(d.values()))
        p = paired_log(by, s, "stats-reject", "base")
        base = [val(m) for (x, a, r), m in by.items() if x == s and a == "base"]
        fr = mean([m.get("freq_ratio") for (x, a, r), m in by.items() if x == s and a == "base"])
        busy = mean([m.get("sut_busy") for (x, a, r), m in by.items() if x == s and a == "base"])
        steal = max([m.get("steal_share") or 0 for (x, a, r), m in by.items() if x == s] or [0])
        lv[s] = {"delta": t, "ratio_pct": p.get("effect_pct"), "base_k": mean(base), "freq_ratio": fr, "busy": busy,
                 "deltas": d}
        a = aa.get(s, {})
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            s, sh.get("workers"), "-" if lv[s]["base_k"] is None else "%.1f" % (lv[s]["base_k"] / 1e3),
            "-" if t.get("mean") is None else ("%.2f" % (t["mean"] / 1e3) if t.get("lo") is None else
                                                "%.2f [%.2f, %.2f]" % (t["mean"] / 1e3, t["lo"] / 1e3, t["hi"] / 1e3)),
            "-" if p.get("effect_pct") is None else "%+.2f%%" % p["effect_pct"],
            "-" if not a else "%.2f" % a["hw"], "-" if not a else ("yes" if a["ok"] else "no"),
            "-" if fr is None else "%.3f" % fr, "-" if busy is None else "%.1f%%" % (100 * busy), "%.2f%%" % (100 * steal)))
    L.append("")
    frs = [v["freq_ratio"] for v in lv.values() if v["freq_ratio"]]
    if frs and (max(frs) / min(frs) - 1.0) > 0.05:
        L.append("**Frequency flag:** the rungs' average frequency differs by more than 5% (%.3f to %.3f).\n" % (
            min(frs), max(frs)))
    js["level"] = lv
    # growth and cross-socket
    # a run may name its own contrasts (high-load run U: no 1w rung); else the box's, and only
    # those whose two rungs the run has
    have = {sh["name"] for sh in exp["shapes"]}
    gl = exp["growth"] if "growth" in exp else box.get("growth", [])
    cl = exp["cross_socket"] if "cross_socket" in exp else box.get("cross_socket", [])
    contrasts = [(a, b, k) for (a, b, k) in [(a, b, "growth") for a, b in gl] + [(a, b, "cross-socket") for a, b in cl]
                 if "mt-" + a in have and "mt-" + b in have]
    rows = []
    for a, b, kind in contrasts:
        sa, sb = "mt-" + a, "mt-" + b
        da, db = lv.get(sa, {}).get("deltas", {}), lv.get(sb, {}).get("deltas", {})
        rr = sorted(set(da) & set(db))
        t = t_interval([da[r] - db[r] for r in rr])
        ok = aa.get(sa, {}).get("ok") and aa.get(sb, {}).get("ok")
        rows.append({"contrast": "Δ(%s) − Δ(%s)" % (a, b), "kind": kind, "t": t, "aa_ok": bool(ok),
                     "reach": max(aa.get(sa, {}).get("reach", 0), aa.get(sb, {}).get("reach", 0))})
    for r, h in zip(rows, stats.holm([r["t"].get("t_p", 1.0) if r["t"].get("t_p") is not None else 1.0 for r in rows])):
        r["holm_p"] = h
        if md.get("incomplete"):
            r["verdict"] = experiment.INCOMPLETE
        elif not r["aa_ok"]:
            r["verdict"] = "no verdict: an A/A of its rungs failed (reach %.2f%%)" % r["reach"]
        elif r["t"].get("lo") is None:
            r["verdict"] = "no data"
        elif h <= 0.05 and not (r["t"]["lo"] <= 0 <= r["t"]["hi"]):
            r["verdict"] = "grows" if r["t"]["mean"] > 0 else "falls"
        else:
            r["verdict"] = "not resolved"
    L.append("## Confirmatory contrasts (Holm over %d rows)\n" % len(rows))
    L.append("| Contrast | Kind | k cycles/req [95% CI] | Rounds | Holm p | Verdict |\n|---|---|---|---|---|---|")
    for r in rows:
        t = r["t"]
        L.append("| %s | %s | %s | %d | %s | %s |" % (
            r["contrast"], r["kind"], "-" if t.get("lo") is None else "%+.2f [%+.2f, %+.2f]" % (
                t["mean"] / 1e3, t["lo"] / 1e3, t["hi"] / 1e3), t["n"], "%.3g" % r["holm_p"], r["verdict"]))
    L.append("")
    js["contrasts"] = rows
    L.append("Host stats (per-host primitive counters and gauges) are not in these figures: their price is a model "
             "estimate (operation counts per request from step 0 times the microbenchmark cost per operation), "
             "given beside the row once both are measured.\n")
    if hitm:
        hb = usable(hitm)
        L.append("## HITM loads per request (evidence legs, outside the timed run)\n")
        L.append("| Rung | Arm | local HITM / req | remote HITM / req |\n|---|---|---|---|")
        js["hitm"] = {}
        for s in rungs:
            for a in ("base", "stats-reject"):
                ev = [(m.get("per_req") or {}).get("events") or {} for (x, aa_, r), m in hb.items() if x == s and aa_ == a]
                loc, rem = mean([ev_get(e, HITM[0]) for e in ev]), mean([ev_get(e, HITM[1]) for e in ev])
                js["hitm"]["%s/%s" % (s, a)] = {"local": loc, "remote": rem}
                L.append("| %s | %s | %s | %s |" % (s, a, "-" if loc is None else "%.3f" % loc,
                                                   "-" if rem is None else "%.3f" % rem))
        L.append("")
    numa = {}
    for (s, a, r), m in by.items():
        if a == "base" and isinstance(m.get("numastat"), dict) and "error" not in m["numastat"]:
            numa.setdefault(s, []).append(m["numastat"])
    if numa:
        L.append("## Envoy memory per NUMA node (base, MB, mean)\n")
        for s, xs in sorted(numa.items()):
            nodes = sorted({k for x in xs for k in x})
            L.append("- %s: %s" % (s, ", ".join("%s %.0f" % (n, mean([x.get(n) for x in xs])) for n in nodes)))
        L.append("")
    return "\n".join(L) + "\n", js


def widened(xs, terms=1):
    """Mean of xs (log points x 100) with the dose runs' widened interval: 1.96 x
    sqrt(SE^2 + terms x 0.34^2), and the two-sided normal p of the mean on that width."""
    n = len(xs)
    if n < 2:
        return {"n": n, "mean": xs[0] if xs else None}
    mu = stats.mean(xs)
    se = stats.stdev(xs) / math.sqrt(n)
    w = math.sqrt(se * se + terms * DOSE_SYS_PCT ** 2)
    return {"n": n, "mean": mu, "se": se, "width": w, "lo": mu - DOSE_Z * w, "hi": mu + DOSE_Z * w,
            "p": math.erfc(abs(mu) / w / math.sqrt(2.0))}


def paired_rounds(by, shape, a, b, f):
    """{round: f(leg of arm a) - f(leg of arm b)} for one shape, rounds where both have a value."""
    out = {}
    for (s, arm, r), m in by.items():
        if s != shape or arm != a or (s, b, r) not in by:
            continue
        x, y = f(m), f(by[(s, b, r)])
        if x is not None and y is not None:
            out[r] = x - y
    return out


def log_rounds(by, shape, a, b, key=METRIC):
    """{round: 100 x ln(a / b)} of one metric for one shape."""
    out = {}
    for (s, arm, r), m in by.items():
        if s != shape or arm != a or (s, b, r) not in by:
            continue
        x, y = val(m, key), val(by[(s, b, r)], key)
        if x and y and x > 0 and y > 0:
            out[r] = 100.0 * math.log(x / y)
    return out


def _ci(t, scale=1.0, fmt="%+.2f"):
    if t.get("mean") is None:
        return "-"
    if t.get("lo") is None:
        return fmt % (t["mean"] / scale)
    return (fmt + " [" + fmt + ", " + fmt + "]") % (t["mean"] / scale, t["lo"] / scale, t["hi"] / scale)


def dose_evidence_rows(ev, d, cells):
    """Per cell, from the evidence legs: HITM:u per request per arm, h = (shared - own) / K, the
    base - stats-reject difference, base worker cycles per request, the store-stat operations
    per request of base (counter increments and histogram samples) and base's worker busy share."""
    by = usable(ev)
    K, own, shared = d["counters"], d["reference"], d["shared"]
    out = {}
    for c in cells:
        s = c["shape"]
        legs = lambda arm: [m for (x, a, r), m in by.items() if x == s and a == arm]  # noqa: E731
        hd = paired_rounds(by, s, shared, own, hitm_per_req)
        td = paired_rounds(by, s, "base", "stats-reject", hitm_per_req)
        ops = [((m["stat_ops"]["counter_incs"] + m["stat_ops"]["histogram_samples"]) / m["responses"])
               for m in legs("base") if m.get("stat_ops") and m.get("responses")]
        row = {"hitm": {a: mean([hitm_per_req(m) for m in legs(a)]) for a in ("base", "stats-reject", own, shared)},
               "hitm_shared_minus_own": t_interval(list(hd.values())),
               "hitm_base_minus_reject": t_interval(list(td.values())),
               "base_cycles": mean([val(m) or val(m, "cycles_total") for m in legs("base")]),
               "base_busy": mean([m.get("sut_busy") for m in legs("base")]),
               "stat_ops_per_req": mean(ops)}
        hm = row["hitm_shared_minus_own"].get("mean")
        row["h"] = None if hm is None else hm / K
        out[c["cell"]] = row
    return out


def dose_tables(res, evidence=None):
    exp = res["experiment"]
    d = exp["dose"]
    box = exp.get("box") or {}
    K, own, shared, aa_arms = d["counters"], d["reference"], d["shared"], d["aa"]
    by = usable(res)
    md = res.get("metadata", {})
    inc = bool(md.get("incomplete"))
    cells = d["cells"]
    workers = {s["name"]: s.get("workers") for s in exp["shapes"]}
    L, js = ["# Run R1 (dose): shared against worker-exclusive counters, K = %d (%s)\n" % (
        K, box.get("label", exp["name"]))], {"counters": K}
    L.append("Legs %d, invalid %d, complete rounds %s%s. Arms: %s (reference: one set of %d counters per downstream "
             "connection), %s (the same %d counters as one object each, written by every worker), %s (A/A). "
             "rho = mean per-round 100 x ln(%s / %s) of worker-only cycles per request.\n" % (
                 len(res["legs"]), sum(1 for m in res["legs"] if not (m.get("verdict") or {}).get("valid")),
                 md.get("rounds_complete"), " (**incomplete, no verdict**)" if inc else "", own, K, shared, K,
                 aa_arms[0], shared, own))
    ev = dose_evidence_rows(evidence, d, cells) if evidence else {}
    # per cell: rho, A/A, instructions, price per update
    cs = {}
    for c in cells:
        s = c["shape"]
        rr = log_rounds(by, s, shared, own)
        p = paired_log(by, s, aa_arms[0], aa_arms[1])
        aa = None
        if p.get("half_width_pct") is not None:
            aa = {"hw": p["half_width_pct"], "reach": max(abs(p["log_lo_pct"]), abs(p["log_hi_pct"])),
                  "t_p": p["t_p"], "n": p["n"], "lo": p["log_lo_pct"], "hi": p["log_hi_pct"]}
        ins = log_rounds(by, s, shared, own, "instructions_u")
        price = paired_rounds(by, s, shared, own, lambda m: None if val(m) is None else val(m) / K)
        cs[c["cell"]] = {"shape": s, "rho_rounds": rr, "rho_t": t_interval(list(rr.values())),
                         "rho": widened(list(rr.values())), "aa": aa,
                         "instr_pct": mean(list(ins.values())), "price_rounds": price,
                         "price": t_interval(list(price.values())),
                         "own_k": mean([val(m) for (x, a, r), m in by.items() if x == s and a == own]),
                         "busy": mean([m.get("sut_busy") for (x, a, r), m in by.items() if x == s and a == own])}
    have_aa = [k for k in cs if cs[k]["aa"]]
    for k, h in zip(have_aa, stats.holm([cs[k]["aa"]["t_p"] for k in have_aa])):
        a = cs[k]["aa"]
        a["holm_p"] = h
        a["ok"] = a["hw"] <= AA_LIMIT_PCT and h > 0.05 and not inc
    aa_ok = lambda k: bool((cs.get(k, {}).get("aa") or {}).get("ok"))  # noqa: E731
    reach = lambda k: (cs.get(k, {}).get("aa") or {}).get("reach")  # noqa: E731
    L.append("## Cells (descriptive)\n")
    L.append("| Cell | Rung | Workers | Rate per worker | Role | Own worker cycles/req (k) | rho % [95% t CI] | "
             "Busy own | A/A hw | A/A reach | A/A pass | Instructions shared / own |\n"
             "|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in cells:
        x = cs[c["cell"]]
        a = x["aa"] or {}
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            c["cell"], c["rung"], workers.get(c["shape"]), c["rate_per_worker"], c["role"],
            "-" if x["own_k"] is None else "%.1f" % (x["own_k"] / 1e3), _ci(x["rho_t"]),
            "-" if x["busy"] is None else "%.1f%%" % (100 * x["busy"]),
            "-" if not a else "%.2f" % a["hw"], "-" if not a else "%.2f" % a["reach"],
            "-" if not a else ("yes" if a["ok"] else "no"),
            "-" if x["instr_pct"] is None else "%+.3f%%" % x["instr_pct"]))
    L.append("")
    # statements
    rows = []
    for i, c in enumerate(cells):
        rows.append({"id": "S%d" % (i + 1), "kind": "cell", "cell": c["cell"],
                     "statement": "rho_%s (%s, %s)" % (c["cell"], c["rung"], c["role"]), "w": cs[c["cell"]]["rho"]})
    for kind, pair in (("socket", d.get("socket")), ("load", d.get("load"))):
        if not pair or pair[0] not in cs or pair[1] not in cs:
            continue
        ra, rb = cs[pair[0]]["rho_rounds"], cs[pair[1]]["rho_rounds"]
        common = sorted(set(ra) & set(rb))
        rows.append({"id": "S%d" % (len(rows) + 1), "kind": kind, "cells": pair,
                     "statement": "%s: rho_%s - rho_%s" % (kind, pair[0], pair[1]),
                     "w": widened([ra[r] - rb[r] for r in common], terms=2)})
    for r, h in zip(rows, stats.holm([r["w"].get("p", 1.0) if r["w"].get("p") is not None else 1.0 for r in rows])):
        w = r["w"]
        r["holm_p"] = h
        if inc:
            r["verdict"] = experiment.INCOMPLETE
            continue
        if w.get("lo") is None:
            r["verdict"] = "no data"
            continue
        excl = not (w["lo"] <= 0 <= w["hi"])
        if r["kind"] == "cell":
            k = r["cell"]
            why = []
            if not aa_ok(k):
                a = cs[k]["aa"]
                why.append("A/A gate failed" + ("" if not a else ": half-width %.2f%%, reach %.2f%%" % (
                    a["hw"], a["reach"])))
            if not excl:
                why.append("the widened interval includes 0")
            elif h > 0.05:
                why.append("not significant after Holm")
            if w["mean"] < DOSE_MIN_EFFECT_PCT:
                why.append("estimate %+.2f%% under %.0f%%" % (w["mean"], DOSE_MIN_EFFECT_PCT))
            elif reach(k) is not None and w["mean"] <= reach(k):
                why.append("estimate within the A/A's reach (%.2f%%)" % reach(k))
            r["finding"] = not why
            if why:
                r["verdict"] = "bound: rho_%s <= %+.2f%% (%s)" % (k, w["hi"], "; ".join(why))
                continue
            ins, e = cs[k]["instr_pct"], ev.get(k) or {}
            hd = (e.get("hitm_shared_minus_own") or {}).get("mean")
            no = []
            if ins is None or abs(ins) > DOSE_INSTR_TOL_PCT:
                no.append("instructions:u per request differ by %s (limit %.1f%%)" % (
                    "an unknown amount" if ins is None else "%+.3f%%" % ins, DOSE_INSTR_TOL_PCT))
            if hd is None:
                no.append("no HITM:u evidence for this cell")
            elif hd < DOSE_HITM_SHARE * K:
                no.append("HITM:u (shared - own) %.1f per request under %.1f x K = %.0f" % (
                    hd, DOSE_HITM_SHARE, DOSE_HITM_SHARE * K))
            r["line_transfer"] = not no
            r["verdict"] = ("finding: line transfer" if not no else
                            "finding, not called line transfer (%s)" % "; ".join(no))
            continue
        ka, kb = r["cells"]
        ok = aa_ok(ka) and aa_ok(kb)
        resolved = ok and excl and h <= 0.05
        r["resolved"] = resolved
        if not ok:
            r["verdict"] = "no verdict: an A/A of its cells failed (reach %.2f%%); <= %+.2f points" % (
                max(reach(ka) or 0, reach(kb) or 0), w["hi"])
        elif r["kind"] == "load":
            if resolved and w["mean"] > DOSE_LOAD_REFUTE_PT:
                r["verdict"] = ("increase above %.0f point: refutes the \"no queueing\" reading; next: a load ladder"
                                % DOSE_LOAD_REFUTE_PT)
            elif resolved:
                r["verdict"] = "resolved, no increase above %.0f point" % DOSE_LOAD_REFUTE_PT
            else:
                r["verdict"] = "not resolved: <= %+.2f points%s" % (
                    w["hi"], "; an increase above %.0f point is not excluded" % DOSE_LOAD_REFUTE_PT
                    if w["hi"] > DOSE_LOAD_REFUTE_PT else "")
        else:
            r["verdict"] = ("resolved: %s" % ("higher across sockets" if w["mean"] > 0 else "lower across sockets")
                            if resolved else "not resolved: <= %+.2f points" % w["hi"])
    L.append("## Statements (pre-stated 2026-11-20; Holm over %d)\n" % len(rows))
    L.append("| # | Statement | Estimate, widened 95% interval | Rounds | Holm p | Predicted | Verdict |\n"
             "|---|---|---|---|---|---|---|")
    for r in rows:
        w = r["w"]
        L.append("| %s | %s | %s | %d | %s | %s | %s |" % (
            r["id"], r["statement"], _ci(w), w["n"], "%.3g" % r["holm_p"],
            DOSE_PREDICTED.get(r["kind"], "-"), r["verdict"]))
    L.append("")
    L.append("Estimates are log points x 100 (percent; S4 and S5 in points). Widened: 1.96 x sqrt(SE^2 + 0.34^2) "
             "for a cell, 1.96 x sqrt(SE^2 + 2 x 0.34^2) for a difference of two cells. A cell that is not a finding "
             "is a bound on rho, not evidence of no cost.\n")
    js["statements"] = rows
    # price per shared update (S5's secondary)
    L.append("## Cycles per shared update (descriptive; S5's secondary)\n")
    L.append("| Cell | (shared - own) / K, worker cycles [95% t CI] |\n|---|---|")
    for c in cells:
        L.append("| %s | %s |" % (c["cell"], _ci(cs[c["cell"]]["price"], fmt="%+.1f")))
    lp = d.get("load")
    if lp and lp[0] in cs and lp[1] in cs:
        pa, pb = cs[lp[0]]["price_rounds"], cs[lp[1]]["price_rounds"]
        t = t_interval([pa[r] - pb[r] for r in sorted(set(pa) & set(pb))])
        js["price_load_difference"] = t
        L.append("| %s - %s | %s |" % (lp[0], lp[1], _ci(t, fmt="%+.1f")))
    L.append("")
    if ev:
        L.append("## HITM:u loads per request (evidence legs, outside the timed run)\n")
        L.append("| Cell | base | stats-reject | %s | %s | (shared - own) / K = h | base - stats-reject [95%% t CI] | "
                 "Store-stat operations/req, base |\n|---|---|---|---|---|---|---|---|" % (own, shared))
        f = lambda v, fmt="%.2f": "-" if v is None else fmt % v  # noqa: E731
        for c in cells:
            e = ev[c["cell"]]
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                c["cell"], f(e["hitm"]["base"]), f(e["hitm"]["stats-reject"]), f(e["hitm"][own]),
                f(e["hitm"][shared]), f(e["h"], "%.3f"), _ci(e["hitm_base_minus_reject"]),
                f(e["stat_ops_per_req"], "%.1f")))
        L.append("")
        L.append("Gauge updates are not in the operation count (an increment and a decrement cancel in "
                 "snapshots).\n")
    # the model row
    L.append("## Model row for the plain config (a MODEL, not a measurement)\n")
    model = {"cells": {}}
    if not ev:
        L.append("No evidence legs given (--evidence): the model row needs HITM:u of base, stats-reject, own and "
                 "shared.\n")
    else:
        L.append("| Cell | P: upper end of (shared - own) / K, cycles | T: upper end of HITM:u (base - reject) / h, "
                 "updates/req | Store-stat operations/req | C: base worker cycles/req (k) | MODEL T x P / C |\n"
                 "|---|---|---|---|---|---|")
        for c in cells:
            k = c["cell"]
            e, P = ev[k], cs[k]["price"].get("hi")
            th, h, C = e["hitm_base_minus_reject"].get("hi"), e["h"], e["base_cycles"]
            why = None
            if inc:
                why = experiment.INCOMPLETE
            elif P is None:
                why = "no price interval"
            elif th is None:
                why = "no base - stats-reject interval"
            elif h is None or h <= 0:
                why = "h is not positive"
            elif not C:
                why = "no base cycles"
            row = {"P": P, "h": h, "C": C, "why": why, "stat_ops_per_req": e["stat_ops_per_req"]}
            if why is None:
                row["T"] = th / h
                row["x_pct"] = max(0.0, 100.0 * row["T"] * P / C)
                row["T_above_ops"] = bool(e["stat_ops_per_req"] is not None and row["T"] > e["stat_ops_per_req"])
            model["cells"][k] = row
            L.append("| %s | %s | %s | %s | %s | %s |" % (
                k, "-" if P is None else "%.1f" % P, "-" if why else "%.1f%s" % (
                    row["T"], " (above the operation count)" if row["T_above_ops"] else ""),
                "-" if e["stat_ops_per_req"] is None else "%.1f" % e["stat_ops_per_req"],
                "-" if not C else "%.1f" % (C / 1e3), why if why else "%.2f%%" % row["x_pct"]))
        L.append("")
        xs = [r["x_pct"] for r in model["cells"].values() if r.get("x_pct") is not None]
        if xs and len(xs) == len(cells):
            ws = sorted(workers.get(c["shape"]) for c in cells)
            busy = sorted(100 * ev[c["cell"]]["base_busy"] for c in cells if ev[c["cell"]]["base_busy"] is not None)
            model["x_pct"] = max(xs)
            L.append("**MODEL:** sharing store stats across %s workers, %s, %s busy, costs at most %.2f%% of worker "
                     "cycles per request (the largest cell; modelled as T x P / C from this run's price per shared "
                     "update, not measured in the plain config). Expected: %s.\n" % (
                         "%d-%d" % (ws[0], ws[-1]) if ws[0] != ws[-1] else "%d" % ws[0],
                         "one or two sockets" if any(c["role"] == "socket" for c in cells) else "one socket",
                         "%.0f-%.0f%%" % (busy[0], busy[-1]) if busy else "unknown", model["x_pct"],
                         DOSE_MODEL_EXPECTED))
        else:
            L.append("**MODEL:** not computable for every cell (see the table); no model row.\n")
    L.append("The own arms hold one counter set per connection, so their updates hit a larger per-thread table and "
             "colder lines than a single shared set would without sharing: this understates the price of sharing. "
             "The K updates of a request arrive in one burst. R1 prices a shared update; the claim about "
             "deployments is the model row only.\n")
    js.update(cells=cs, evidence=ev, model=model)
    return "\n".join(L) + "\n", js


def render(res, hitm=None, evidence=None):
    """The tables of a run: a dose run (its config has a `dose` block) or run U."""
    if (res.get("experiment") or {}).get("dose"):
        return dose_tables(res, evidence)
    return tables(res, hitm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--hitm")
    ap.add_argument("--evidence", help="the dose run's evidence legs (dose-evidence.json)")
    ap.add_argument("--json")
    a = ap.parse_args()
    res = load(a.run)
    if res is None:
        sys.exit("no results.json in %s" % a.run)
    if a.evidence and load(a.evidence) is None:
        sys.exit("no results.json in %s" % a.evidence)
    text, js = render(res, load(a.hitm) if a.hitm else None, load(a.evidence) if a.evidence else None)
    sys.stdout.write(text)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(js, f, indent=1, default=str)


if __name__ == "__main__":
    main()
