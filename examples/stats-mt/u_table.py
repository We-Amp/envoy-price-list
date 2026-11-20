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
                loc, rem = mean([e.get(HITM[0]) for e in ev]), mean([e.get(HITM[1]) for e in ev])
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--hitm")
    ap.add_argument("--json")
    a = ap.parse_args()
    res = load(a.run)
    if res is None:
        sys.exit("no results.json in %s" % a.run)
    text, js = tables(res, load(a.hitm) if a.hitm else None)
    sys.stdout.write(text)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(js, f, indent=1, default=str)


if __name__ == "__main__":
    main()
