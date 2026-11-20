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

Run R1 ("dose", a run whose config has a `dose` block; statements pre-stated 2026-11-20, as
amended three times the same day before any timed leg ran):

    python3 examples/stats-mt/u_table.py DOSE_DIR [--evidence DOSE_EVIDENCE_DIR] [--json OUT.json]

Every cell has its own dose K_c (counters per request) and its own arms (the config's dose.cells:
counters, reference, shared, aa); one cell also runs a second dose (dose.low). Estimand per
cell c: rho_c = the mean per-round 100 x ln(shared / own) of worker-only cycles per request at
K_c (log points x 100, read as percent). A/A per cell: the second own arm against own at K_c;
passes with a 95% half-width of at most 1% and unresolved (its raw p above 0.05). The second
dose's pair uses its cell's A/A. A cell needs 12 valid rounds (own, shared and the A/A arm all
valid) for a verdict; under that it is incomplete, and so is a contrast it is part of. A short
run (the config's dose.short_run: fewer rounds than that minimum, by decision) has no such
minimum: every statement is reported with the same interval forms and finding rules, and what
they do not resolve reads "not resolved in a short run, under X", X the widened interval's upper
end. A hot-counter pair (dose.hot: one counter takes all the increments of a request) is
exploratory: its rho and price per update are printed beside its cell's pair, outside the
statements. Holm over the five statements:
  S1-S3 (rho at the cell's dose, one per cell). A cell whose A/A fails has no verdict. An
    interval entirely below 0 is "comparison invalid (own slower than shared)". A finding when
    all hold: the widened interval rho_c +/- 1.96 x sqrt(SE^2 + 0.34^2) excludes 0 (and the
    statement survives Holm); the estimate is at least 1% and beyond the A/A's reach. A finding
    is called "line transfer" only when instructions:u per request match within 0.5% between
    shared and own and HITM:u (shared - own) per request is at least 0.15 x K_c (evidence
    legs). Otherwise the cell is a bound, "rho_c <= the widened interval's upper end".
  S4 (socket) and S5 (workers): the difference of two cells' rho at the same dose, paired by
    round, widened with 1.96 x sqrt(SE^2 + 2 x 0.34^2). Where the two cells' own doses differ,
    the contrast uses the second dose's pair of the cell that has one (rho_D(64) - rho_A(64)).
    S4 predicted +2 to +4 points; S5 no directional prediction.
Linearity is a description, not a statement: the price per update at the two doses of the cell
that has both, P = (exp(rho) - 1) x C / dose on the means (C that dose's own-arm cycles), and
ln(P(K) / P(second dose)) with its unwidened interval (delta method, paired by round).
Prices: (shared - own) / dose in worker cycles, measured, and likely understating the sharing
price (own pays extra L3 hits for its per-connection counter sets). Beside each, where the
evidence legs have that pair, the footprint band P + d x 45 cycles, d = clean L3 hits per update
(L3 hits minus local HITM loads), own minus shared: a modelled upper figure (45 cycles is an
assumed L3 hit latency on this CPU, no overlap credited).
Model row for the plain config, always labelled a model, per cell: contention <= T x P / C with
P = (exp(the widened interval's upper end of rho) - 1) x own cycles / dose (in the second dose's
cell at both doses), T the store-stat operations per request of the plain config from the
stat-operation probe (counter increments and histogram samples of base), C base worker cycles per
request. Beside it, for comparison, the HITM-scaled figure: HITM:u (base - stats-reject) per
request x P / h, h = HITM:u (shared - own) per update in the same cell. A cell without a
verdict, or whose comparison is invalid, has no model row. The headline gives the one-socket and
the two-socket cells separately.
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
DOSE_HITM_SHARE = 0.15         # "line transfer": HITM:u (shared - own) per request >= this x the cell's K
DOSE_L3_HIT = "mem_load_uops_retired.l3_hit"
DOSE_L3_CYCLES = 45.0          # assumed L3 hit latency on the bench CPU (the footprint band)
DOSE_MIN_ROUNDS = 12           # valid rounds a cell needs for a verdict
DOSE_AA_ALPHA = 0.05           # the A/A is unresolved when its raw p is above this
DOSE_PREDICTED = {"socket": "+2 to +4 points", "workers": "no directional prediction"}
DOSE_INVALID = "comparison invalid (own slower than shared)"
DOSE_MODEL_EXPECTED = "0.3-0.8% on one socket, 0.6-1.7% split"


def ev_get(e, name):
    """An event's per-request value under either spelling (counted in user mode: NAME:u)."""
    v = e.get(name)
    return e.get(name + ":u") if v is None else v


def clean_l3(m, k):
    """L3 hits that are not local HITM loads, per request and counter update; None unless both
    events were counted."""
    e = ((m or {}).get("per_req") or {}).get("events") or {}
    hit, hitm = ev_get(e, DOSE_L3_HIT), ev_get(e, HITM[0])
    return None if hit is None or hitm is None else (hit - hitm) / k


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


def linearity(rk, rl, ck, cl, K, Klow):
    """A description, not a statement: ln(P(K) / P(Klow)) with P = (exp(rho) - 1) x C / dose, from
    the per-round rho of the two doses (log points x 100, the rounds both have) and each dose's
    own-arm mean cycles. Unwidened 95% interval by the delta method, d ln(exp(rho) - 1) / d rho
    = exp(rho) / (exp(rho) - 1), the two rho paired by round. Log points x 100; `why` when a
    price is not positive."""
    rounds = sorted(set(rk) & set(rl))
    n = len(rounds)
    out = {"n": n, "mean": None}
    if n < 2 or not ck or not cl:
        return out
    xk, xl = [rk[r] / 100.0 for r in rounds], [rl[r] / 100.0 for r in rounds]
    mk, ml = stats.mean(xk), stats.mean(xl)
    out.update(rho_k=100 * mk, rho_low=100 * ml)
    if mk <= 0 or ml <= 0:
        out["why"] = "the price is not positive at %s" % ("K" if mk <= 0 else "Klow")
        return out
    pk, pl = math.expm1(mk) * ck / K, math.expm1(ml) * cl / Klow
    a, b = math.exp(mk) / math.expm1(mk), math.exp(ml) / math.expm1(ml)
    cov = sum((x - mk) * (y - ml) for x, y in zip(xk, xl)) / (n - 1)
    var = (a * a * stats.stdev(xk) ** 2 + b * b * stats.stdev(xl) ** 2 - 2 * a * b * cov) / n
    se = math.sqrt(max(var, 0.0))
    g = math.log(pk / pl)
    out.update(mean=100 * g, se=100 * se, lo=100 * (g - DOSE_Z * se), hi=100 * (g + DOSE_Z * se),
               price_k=pk, price_low=pl)
    return out


def model_price(w, own_cycles, dose):
    """The model's price per shared update: (exp(the widened interval's upper end of rho) - 1) x
    own cycles per request / dose. None without an interval or own cycles."""
    if not w or w.get("hi") is None or not own_cycles:
        return None
    return math.expm1(w["hi"] / 100.0) * own_cycles / dose


def dose_evidence_rows(ev, cells):
    """Per cell, from the evidence legs, at the cell's own dose and arms: HITM:u per request per
    arm, h = (shared - own) / K_c, clean L3 hits per update own minus shared (the footprint), the
    base - stats-reject difference, base worker cycles per request, the store-stat operations per
    request of base (counter increments and histogram samples) and base's worker busy share."""
    by = usable(ev)
    out = {}
    for c in cells:
        s, K, own, shared = c["shape"], c["counters"], c["reference"], c["shared"]
        legs = lambda arm: [m for (x, a, r), m in by.items() if x == s and a == arm]  # noqa: E731
        hd = paired_rounds(by, s, shared, own, hitm_per_req)
        td = paired_rounds(by, s, "base", "stats-reject", hitm_per_req)
        fd = paired_rounds(by, s, own, shared, lambda m: clean_l3(m, K))
        ops = [((m["stat_ops"]["counter_incs"] + m["stat_ops"]["histogram_samples"]) / m["responses"])
               for m in legs("base") if m.get("stat_ops") and m.get("responses")]
        row = {"counters": K, "own": own, "shared": shared,
               "hitm": {"base": mean([hitm_per_req(m) for m in legs("base")]),
                        "stats-reject": mean([hitm_per_req(m) for m in legs("stats-reject")]),
                        "own": mean([hitm_per_req(m) for m in legs(own)]),
                        "shared": mean([hitm_per_req(m) for m in legs(shared)])},
               "hitm_shared_minus_own": t_interval(list(hd.values())),
               "hitm_base_minus_reject": t_interval(list(td.values())),
               "footprint": t_interval(list(fd.values())),
               "base_cycles": mean([val(m) or val(m, "cycles_total") for m in legs("base")]),
               "base_busy": mean([m.get("sut_busy") for m in legs("base")]),
               "stat_ops_per_req": mean(ops)}
        hm = row["hitm_shared_minus_own"].get("mean")
        row["h"] = None if hm is None else hm / K
        out[c["cell"]] = row
    return out


def dose_pair(by, shape, own, shared, K):
    """One own/shared pair at one dose in one cell: per-round rho, its intervals, the price per
    update and the own arm's level."""
    rr = log_rounds(by, shape, shared, own)
    price = paired_rounds(by, shape, shared, own, lambda m: None if val(m) is None else val(m) / K)
    return {"shape": shape, "counters": K, "own": own, "shared": shared, "rho_rounds": rr,
            "rho_t": t_interval(list(rr.values())), "rho": widened(list(rr.values())),
            "instr_pct": mean(list(log_rounds(by, shape, shared, own, "instructions_u").values())),
            "price_rounds": price, "price": t_interval(list(price.values())),
            "own_k": mean([val(m) for (x, a, r), m in by.items() if x == shape and a == own]),
            "busy": mean([m.get("sut_busy") for (x, a, r), m in by.items() if x == shape and a == own])}


def dose_tables(res, evidence=None):
    exp = res["experiment"]
    d = exp["dose"]
    box = exp.get("box") or {}
    by = usable(res)
    md = res.get("metadata", {})
    inc = bool(md.get("incomplete"))
    cells = d["cells"]
    workers = {s["name"]: s.get("workers") for s in exp["shapes"]}
    short_run = bool(d.get("short_run"))
    L, js = ["# Run R1 (dose)%s: shared against worker-exclusive counters (%s)\n" % (
        ", SHORT RUN of %s rounds" % d.get("rounds") if short_run else "", box.get("label", exp["name"]))], {}
    js["short_run"] = short_run
    need = 2 if short_run else DOSE_MIN_ROUNDS
    L.append("Legs %d, invalid %d, complete rounds %s%s. In each cell: own (the reference: one set of K counters per "
             "downstream connection), shared (the same K counters as one object each, written by every worker) and a "
             "second copy of own (A/A), at the cell's own K: %s. rho = mean per-round 100 x ln(shared / own) of "
             "worker-only cycles per request.\n" % (
                 len(res["legs"]), sum(1 for m in res["legs"] if not (m.get("verdict") or {}).get("valid")),
                 md.get("rounds_complete"), " (**incomplete, no verdict**)" if inc else "",
                 ", ".join("cell %s K = %d" % (c["cell"], c["counters"]) for c in cells)))
    ev = dose_evidence_rows(evidence, cells) if evidence else {}
    # per cell, at its own dose: rho, A/A, instructions, price per update
    cs = {}
    for c in cells:
        x = dose_pair(by, c["shape"], c["reference"], c["shared"], c["counters"])
        p = paired_log(by, c["shape"], c["aa"][0], c["aa"][1])
        aa = None
        if p.get("half_width_pct") is not None:
            aa = {"hw": p["half_width_pct"], "reach": max(abs(p["log_lo_pct"]), abs(p["log_hi_pct"])),
                  "t_p": p["t_p"], "n": p["n"], "lo": p["log_lo_pct"], "hi": p["log_hi_pct"]}
        nv = len([r for r in x["rho_rounds"] if (c["shape"], c["aa"][0], r) in by])
        x.update(aa=aa, valid_rounds=nv, enough=nv >= need)
        if aa:
            # unresolved: the raw p of the A/A difference (no Holm: a correction would make it easier to pass)
            aa["ok"] = aa["hw"] <= AA_LIMIT_PCT and aa["t_p"] > DOSE_AA_ALPHA and not inc and x["enough"]
        cs[c["cell"]] = x
    by_cell = {c["cell"]: c for c in cells}
    low = d.get("low")
    lo = None
    if low and low["cell"] in cs:
        k = low["cell"]
        lo = dose_pair(by, cs[k]["shape"], low["reference"], low["shared"], low["counters"])
        nv = len([r for r in lo["rho_rounds"] if r in cs[k]["rho_rounds"] and (cs[k]["shape"], by_cell[k]["aa"][0], r) in by])
        lo.update(cell=k, valid_rounds=nv, enough=nv >= need,
                  lin=linearity(cs[k]["rho_rounds"], lo["rho_rounds"], cs[k]["own_k"], lo["own_k"],
                                cs[k]["counters"], low["counters"]))
    js["low"] = lo
    hot = None
    if d.get("hot") and d["hot"]["cell"] in cs:
        # exploratory: one counter takes the K increments of a request (outside the statements)
        hk = d["hot"]["cell"]
        hot = dose_pair(by, cs[hk]["shape"], d["hot"]["reference"], d["hot"]["shared"], d["hot"]["counters"])
        hot.update(cell=hk, valid_rounds=len(hot["rho_rounds"]))
    js["hot"] = hot
    aa_ok = lambda k: bool((cs.get(k, {}).get("aa") or {}).get("ok"))  # noqa: E731
    reach = lambda k: (cs.get(k, {}).get("aa") or {}).get("reach")  # noqa: E731
    L.append("## Cells (descriptive)\n")
    L.append("| Cell | Rung | Workers | Rate per worker | Role | K | Own worker cycles/req (k) | rho % [95% t CI] | "
             "Busy own | Valid rounds | A/A hw | A/A reach | A/A p | A/A pass | Instructions shared / own |\n"
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    def cell_row(c, x, a, second=""):
        return "| %s | %s | %s | %s | %s | %d | %s | %s | %s | %d | %s | %s | %s | %s | %s |" % (
            c["cell"] + second, c["rung"], workers.get(c["shape"]), c["rate_per_worker"],
            c["role"], x["counters"], "-" if x["own_k"] is None else "%.1f" % (x["own_k"] / 1e3), _ci(x["rho_t"]),
            "-" if x["busy"] is None else "%.1f%%" % (100 * x["busy"]), x["valid_rounds"],
            "-" if not a else "%.2f" % a["hw"], "-" if not a else "%.2f" % a["reach"],
            "-" if not a else "%.3g" % a["t_p"], "-" if not a else ("yes" if a["ok"] else "no"),
            "-" if x["instr_pct"] is None else "%+.3f%%" % x["instr_pct"])
    for c in cells:
        L.append(cell_row(c, cs[c["cell"]], cs[c["cell"]]["aa"] or {}))
        if lo and lo["cell"] == c["cell"]:
            L.append(cell_row(c, lo, cs[c["cell"]]["aa"] or {}, " (second dose)"))
        if hot and hot["cell"] == c["cell"]:
            L.append(cell_row(c, hot, cs[c["cell"]]["aa"] or {}, " (HOT COUNTER, exploratory)"))
    L.append("")
    if short_run:
        L.append("A short run: %s rounds, by decision; no minimum of %d valid rounds applies, and nothing is re-run "
                 "to rescue a statement.\n" % (d.get("rounds"), DOSE_MIN_ROUNDS))
    if lo:
        L.append("The second dose's pair in cell %s uses that cell's A/A (%s against %s).\n" % (
            lo["cell"], by_cell[lo["cell"]]["aa"][0], by_cell[lo["cell"]]["aa"][1]))
    # statements
    rows = []
    for i, c in enumerate(cells):
        rows.append({"id": "S%d" % (i + 1), "kind": "cell", "cell": c["cell"], "counters": c["counters"],
                     "statement": "rho_%s at K = %d (%s, %s)" % (c["cell"], c["counters"], c["rung"], c["role"]),
                     "w": cs[c["cell"]]["rho"]})

    def at_dose(k, n):
        """The pair of cell k at dose n: the cell's own, or its second dose's; None when it has neither."""
        if cs[k]["counters"] == n:
            return cs[k]
        return lo if lo and lo["cell"] == k and lo["counters"] == n else None
    for kind, pair in (("socket", d.get("socket")), ("workers", d.get("workers"))):
        if not pair or pair[0] not in cs or pair[1] not in cs:
            continue
        # the dose both cells have: the first cell's own dose, else the second's
        n = next((n for n in (cs[pair[0]]["counters"], cs[pair[1]]["counters"])
                  if at_dose(pair[0], n) and at_dose(pair[1], n)), None)
        row = {"id": "S%d" % (len(rows) + 1), "kind": kind, "cells": pair, "counters": n}
        if n is None:
            row.update(statement="%s: rho_%s - rho_%s" % (kind, pair[0], pair[1]), w={"n": 0, "mean": None},
                       no_dose="the two cells have no pair at the same dose")
        else:
            xa, xb = at_dose(pair[0], n), at_dose(pair[1], n)
            common = sorted(set(xa["rho_rounds"]) & set(xb["rho_rounds"]))
            row.update(statement="%s: rho_%s(%d) - rho_%s(%d)" % (kind, pair[0], n, pair[1], n), pairs=[xa, xb],
                       w=widened([xa["rho_rounds"][r] - xb["rho_rounds"][r] for r in common], terms=2))
        rows.append(row)
    short = lambda k, nv: "%s (cell %s: %d valid rounds of the %d a verdict needs)" % (  # noqa: E731
        experiment.INCOMPLETE, k, nv, need)
    aa_why = lambda k: "A/A failed" + ("" if not cs[k]["aa"] else ": half-width %.2f%%, reach %.2f%%, p %.3g" % (  # noqa: E731
        cs[k]["aa"]["hw"], cs[k]["aa"]["reach"], cs[k]["aa"]["t_p"]))
    for r, h in zip(rows, stats.holm([r["w"].get("p", 1.0) if r["w"].get("p") is not None else 1.0 for r in rows])):
        w = r["w"]
        r["holm_p"] = h
        mine = [r["cell"]] if r["kind"] == "cell" else r["cells"]
        used = [cs[r["cell"]]] if r["kind"] == "cell" else r.pop("pairs", [])
        if inc:
            r["verdict"] = experiment.INCOMPLETE
            continue
        if r.get("no_dose"):
            r["verdict"] = "no verdict: %s" % r["no_dose"]
            continue
        few = [(k, x["valid_rounds"]) for k, x in zip(mine, used) if not x["enough"]] + \
            [(k, cs[k]["valid_rounds"]) for k in mine if not cs[k]["enough"]]
        if few:
            r["verdict"] = short(*few[0])
            continue
        if w.get("lo") is None:
            r["verdict"] = "no data"
            continue
        if not all(aa_ok(k) for k in mine):
            bad = next(k for k in mine if not aa_ok(k))
            r["verdict"] = "no verdict: cell %s %s" % (bad, aa_why(bad))
            continue
        excl = not (w["lo"] <= 0 <= w["hi"])
        if r["kind"] == "cell":
            k, K = r["cell"], r["counters"]
            if w["hi"] < 0:
                r["invalid"] = True
                r["verdict"] = DOSE_INVALID
                continue
            why = []
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
                r["verdict"] = ("not resolved in a short run, under %+.2f%% (%s)" % (w["hi"], "; ".join(why))
                                if short_run else "bound: rho_%s <= %+.2f%% (%s)" % (k, w["hi"], "; ".join(why)))
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
                no.append("HITM:u (shared - own) %.1f per request under %.2f x K = %.1f" % (
                    hd, DOSE_HITM_SHARE, DOSE_HITM_SHARE * K))
            r["line_transfer"] = not no
            r["verdict"] = ("finding: line transfer" if not no else
                            "finding, not called line transfer (%s)" % "; ".join(no))
            continue
        # a contrast: neither of its pairs may be an invalid comparison
        bad = [k for k, x in zip(mine, used) if x["rho"].get("hi") is not None and x["rho"]["hi"] < 0]
        if bad:
            r["verdict"] = "no verdict: cell %s at K = %d %s" % (bad[0], r["counters"], DOSE_INVALID)
            continue
        resolved = excl and h <= 0.05
        r["resolved"] = resolved
        what = "across sockets" if r["kind"] == "socket" else "at the larger worker count"
        r["verdict"] = ("resolved: %s %s" % ("higher" if w["mean"] > 0 else "lower", what) if resolved else
                        "not resolved in a short run, under %+.2f points" % w["hi"] if short_run else
                        "not resolved: <= %+.2f points" % w["hi"])
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
    L.append("%s; a cell whose A/A fails has no verdict (not a bound); an "
             "interval entirely below 0 is an invalid comparison, not a negative price. rho is diluted by the logger's "
             "own cost per update (it is in own and in shared alike); the price per update below is not.\n"
             % ("A short run: what its rounds do not resolve is \"not resolved in a short run, under X\", X the "
                "widened interval's upper end" if short_run else
                "A cell under %d valid rounds is incomplete" % DOSE_MIN_ROUNDS))
    js["statements"] = rows
    # prices, with the footprint band where the evidence legs have that pair
    L.append("## Cycles per shared update\n")
    L.append("| Cell | K | P: (shared - own) / K, worker cycles [95%% t CI] (measured) | d: clean L3 hits per update, own - "
             "shared (evidence legs) | P + d x %.0f cycles (MODELLED upper figure) |\n|---|---|---|---|---|"
             % DOSE_L3_CYCLES)
    prices = []
    for c in cells:
        for x in [cs[c["cell"]]] + ([lo] if lo and lo["cell"] == c["cell"] else []):
            e = ev.get(c["cell"]) or {}
            dd = (e.get("footprint") or {}).get("mean") if e.get("counters") == x["counters"] else None
            pm = x["price"].get("mean")
            band = None if dd is None or pm is None else pm + dd * DOSE_L3_CYCLES
            prices.append({"cell": c["cell"], "counters": x["counters"], "price": x["price"], "footprint_d": dd,
                           "band": band})
            L.append("| %s | %d | %s | %s | %s |" % (
                c["cell"], x["counters"], _ci(x["price"], fmt="%+.1f"),
                "-" if dd is None else "%+.2f" % dd, "-" if band is None else "%.1f" % band))
    if hot:
        L.append("| %s, HOT COUNTER (exploratory) | %d on one counter | %s | - | - |" % (
            hot["cell"], hot["counters"], _ci(hot["price"], fmt="%+.1f")))
    L.append("")
    js["prices"] = prices
    if hot:
        sp, hp = cs[hot["cell"]]["price"].get("mean"), hot["price"].get("mean")
        L.append("Hot counter in cell %s (EXPLORATORY, outside the statements, %d rounds): one counter takes the %d "
                 "increments of a request, so the write rate on its line is %d times a spread counter's. rho %s%% "
                 "(widened %s), price %s cycles per update against %s for the spread pair at K = %d%s. A hot price "
                 "clearly above the spread price is the sign of writers queuing on a line; own's hot counter stays in "
                 "its worker's cache, so the two pairs' own arms differ.\n" % (
                     hot["cell"], hot["valid_rounds"], hot["counters"], hot["counters"], _ci(hot["rho_t"]),
                     _ci(hot["rho"]), "-" if hp is None else "%+.1f" % hp, "-" if sp is None else "%+.1f" % sp,
                     cs[hot["cell"]]["counters"],
                     "" if not sp or hp is None or sp <= 0 else " (%.2f times)" % (hp / sp)))
    L.append("P is measured and likely understates the sharing price: the own arm holds one counter set per "
             "connection and pays extra L3 hits for them. The last column adds d L3 hits at an assumed %.0f cycles "
             "each (no overlap credited): a modelled upper figure, not a measurement. No band where the evidence "
             "legs do not run that pair.\n" % DOSE_L3_CYCLES)
    if lo:
        w = lo["lin"]
        if w.get("lo") is not None:
            L.append("Linearity in cell %s (a description, not a statement): on the means, P = (exp(rho) - 1) x C / "
                     "dose is %.1f cycles per update at K = %d (rho %+.2f%%) and %.1f at K = %d (rho %+.2f%%); "
                     "ln(P(%d) / P(%d)) = %+.1f [%+.1f, %+.1f] (log points x 100, unwidened, %d rounds). At the "
                     "smaller dose the effect is small and the footprint of the own arm differs, so this has little "
                     "power.\n" % (lo["cell"], w["price_k"], cs[lo["cell"]]["counters"], w["rho_k"], w["price_low"],
                                   lo["counters"], w["rho_low"], cs[lo["cell"]]["counters"], lo["counters"],
                                   w["mean"], w["lo"], w["hi"], w["n"]))
        else:
            L.append("Linearity in cell %s (a description, not a statement): not computable (%s).\n" % (
                lo["cell"], w.get("why") or "too few rounds"))
    f = lambda v, fmt="%.2f": "-" if v is None else fmt % v  # noqa: E731
    if ev:
        L.append("## HITM:u loads per request (evidence legs, outside the timed run)\n")
        L.append("| Cell | K | base | stats-reject | own | shared | (shared - own) / K = h | Line-transfer threshold "
                 "%.2f x K | base - stats-reject [95%% t CI] | Store-stat operations/req, base |\n"
                 "|---|---|---|---|---|---|---|---|---|---|" % DOSE_HITM_SHARE)
        for c in cells:
            e = ev[c["cell"]]
            L.append("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                c["cell"], e["counters"], f(e["hitm"]["base"]), f(e["hitm"]["stats-reject"]), f(e["hitm"]["own"]),
                f(e["hitm"]["shared"]), f(e["h"], "%.3f"), "%.1f per request" % (DOSE_HITM_SHARE * e["counters"]),
                _ci(e["hitm_base_minus_reject"]), f(e["stat_ops_per_req"], "%.1f")))
        L.append("")
        L.append("The HITM load event sees only a fraction of the transfers of locked updates (h well under 1 in the "
                 "pilot). Gauge updates are not in the operation count (an increment and a decrement cancel in "
                 "snapshots).\n")
    # the model row
    L.append("## Model row for the plain config (a MODEL, not a measurement)\n")
    model = {"cells": {}}
    if not ev:
        L.append("No evidence legs given (--evidence): the model row needs the store-stat operations and base cycles "
                 "of the plain config.\n")
    else:
        L.append("| Cell | Sockets | K | P: price per update from the widened upper end of rho, cycles | T: store-stat "
                 "operations/req of the plain config (probe) | C: base worker cycles/req (k) | MODEL T x P / C | For "
                 "comparison, HITM-scaled: HITM:u (base - reject) x P / h, as a share of C |\n"
                 "|---|---|---|---|---|---|---|---|")
        verdict = {r["cell"]: r for r in rows if r["kind"] == "cell"}
        entries = []
        for c in cells:
            entries.append((c, cs[c["cell"]]))
            if lo and lo["cell"] == c["cell"]:
                entries.append((c, lo))
        for c, x in entries:
            k, dose = c["cell"], x["counters"]
            e, v = ev[k], verdict.get(k, {})
            P = model_price(x["rho"], x["own_k"], dose)
            T, C = e["stat_ops_per_req"], e["base_cycles"]
            why = None
            if inc or not cs[k]["enough"] or not x["enough"]:
                why = experiment.INCOMPLETE
            elif not aa_ok(k):
                why = "the cell has no verdict (A/A failed)"
            elif v.get("invalid") or (x["rho"].get("hi") is not None and x["rho"]["hi"] < 0):
                why = DOSE_INVALID
            elif P is None:
                why = "no price interval"
            elif T is None:
                why = "no stat-operation probe of base"
            elif not C:
                why = "no base cycles"
            row = {"cell": k, "dose": dose, "P": P, "T": T, "C": C, "why": why, "sockets": c.get("sockets")}
            hs = None
            if why is None:
                row["x_pct"] = max(0.0, 100.0 * T * P / C)
                # the comparison figure uses the HITM evidence of the cell's own dose
                th, h = e["hitm_base_minus_reject"].get("mean"), e["h"]
                if th is not None and h and h > 0:
                    hs = row["hitm_scaled_pct"] = 100.0 * th * P / h / C
            model["cells"].setdefault(k, []).append(row)
            L.append("| %s | %s | %d | %s | %s | %s | %s | %s |" % (
                k, c.get("sockets", "-"), dose, "-" if P is None else "%.1f" % P, "-" if T is None else "%.1f" % T,
                "-" if not C else "%.1f" % (C / 1e3), why if why else "%.2f%%" % row["x_pct"],
                "-" if hs is None else "%.2f%%" % hs))
        L.append("")
        model["headline"] = {}
        for n, word in ((1, "one socket"), (2, "two sockets")):
            mine = [c for c in cells if c.get("sockets") == n]
            got = [(c, r) for c in mine for r in model["cells"][c["cell"]] if r.get("x_pct") is not None]
            if not mine:
                continue
            if not got:
                L.append("**MODEL, %s:** no model row (%s).\n" % (word, "; ".join(sorted(
                    {"cell %s: %s" % (c["cell"], r["why"]) for c in mine for r in model["cells"][c["cell"]]}))))
                continue
            x = max(r["x_pct"] for c, r in got)
            model["headline"][word] = x
            busy = sorted(100 * ev[c["cell"]]["base_busy"] for c in mine if ev[c["cell"]]["base_busy"] is not None)
            L.append("**MODEL, %s:** sharing store stats across %s, %s busy, costs at most %.2f%% of worker cycles "
                     "per request (%s; modelled as T x P / C from this run's price per shared update, not "
                     "measured in the plain config).%s\n" % (
                         word, " and ".join("%d workers (cell %s)" % (workers.get(c["shape"]), c["cell"])
                                            for c in mine),
                         ("%.0f%%" % busy[0] if round(busy[0]) == round(busy[-1]) else "%.0f-%.0f%%" % (
                             busy[0], busy[-1])) if busy else "unknown", x,
                         "; ".join("cell %s %.2f%% with the price at %d counters" % (c["cell"], r["x_pct"], r["dose"])
                                   for c, r in got),
                         "".join(" Cell %s has no model row (%s)." % (c["cell"], model["cells"][c["cell"]][0]["why"])
                                 for c in mine if all(r.get("x_pct") is None for r in model["cells"][c["cell"]]))))
        L.append("Expected: %s. P = (exp(the widened interval's upper end of rho) - 1) x own cycles / counters; T "
                 "counts every store-stat operation of the plain config as a shared update. The HITM-scaled column is "
                 "printed for comparison only (means, not upper ends).\n" % DOSE_MODEL_EXPECTED)
    L.append("R1 prices a shared update; the claim about deployments is the model row only. The K updates of a "
             "request arrive in one burst.\n")
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
