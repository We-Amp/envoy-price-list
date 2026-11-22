#!/usr/bin/env python3
"""Top-down study (track A) analysis: per-request counters from legs.jsonl -> markdown tables + a
decisions file (<out>.json next to <out.md>).

Usage: python3 analyse.py <run dir with legs.jsonl> <out.md>
Every event is normalised per response (the harness's window-scaled `responses`). Within-leg ratios
(e.g. walk cycles / user cycles) use the same leg; TMA pieces from different groups are combined
through per-request means of the same arm and shape.

Round r counts event group G((r - 1) % 8 + 1). The follow-up rules, fixed before the run, each read
per-round values (mean, min, max over the rounds of one group): a threshold counts as met when every
round is at or above it, as missed when every round is below it, and as undecided when the rounds
straddle it.
  huge-page text (stock)   KEEP when stock iTLB walk cycles / user cycles >= 3% on s or fh; KILL
                           when missed on s and fh and not met on fl; else UNDECIDED.
  huge-page text (pgolto)  the same 3% threshold on pgolto: KEEP when met on any shape, KILL when
                           missed on every shape.
  call-graph ordering file KEEP when the stock user frontend bound is >= 15% on s and fh and
                           pgolto's is at least 5 points lower on both; KILL when the 15% is missed
                           on s or fh, or met but pgolto is not 5 points lower.
  cold log sites           KILL when stock i-cache stall cycles / user cycles < 10% on s and fh;
                           when >= 10% on s or fh, KEEP if pgolto removes at most half of the stock
                           i-cache stall cycles per request on s and fh, else KILL.
  BOLT/Propeller on pgolto KEEP when pgolto's user frontend bound is >= 25% on any shape; KILL when
                           under 25% on every shape.
  HeaderString (data side) on fl, stock: KEEP when the data-side cost bound (12 x L1d replacements
                           + 40 x L2 misses) / user cycles >= 3% and memory stall cycles / user
                           cycles >= 10%; KILL when either is missed.
"""
import json
import statistics as st
import sys
from collections import defaultdict

run, out = sys.argv[1], sys.argv[2]
legs = [json.loads(x) for x in open(run + "/legs.jsonl")]
NG = 8
valid = [m for m in legs if m["verdict"]["valid"]]
invalid = [(m["leg_id"], m["verdict"]["reasons"]) for m in legs if not m["verdict"]["valid"]]

# per (arm, shape, group): list of (round, {event: per-request value}, raw leg)
cell = defaultdict(list)
for m in valid:
    g = (int(m["round"]) - 1) % NG + 1
    pr = {k: v / m["responses"] for k, v in m["perf_raw"].items()}
    cell[(m["arm"], m["shape"], g)].append((m["round"], pr, m))

ARMS = ["stock", "pgolto"]
SHAPES = ["s", "fh", "fl"]


def vals(a, s, g, fn):
    return [(r, fn(pr)) for r, pr, _ in sorted(cell[(a, s, g)], key=lambda x: x[0])]


def mean(a, s, g, ev):
    v = [pr[ev] for _, pr, _ in cell[(a, s, g)] if ev in pr]
    return st.mean(v) if v else float("nan")


def cu(pr):
    return pr.get("cycles:u")


def tot(pr):
    return pr.get("cycles") or (pr["cycles:u"] + pr["cycles:k"])


# metric name -> (group, function of per-request dict, (arm, shape) context, format)
def metrics(a, s):
    rec_u = mean(a, s, 3, "int_misc.recovery_cycles:u")
    iss_u = mean(a, s, 2, "uops_issued.any:u")
    ret_u = mean(a, s, 2, "uops_retired.retire_slots:u")
    ms_u = mean(a, s, 4, "idq.ms_uops:u")
    fe_u_mean = st.mean([pr["idq_uops_not_delivered.core:u"] / (4 * pr["cycles:u"]) for _, pr, _ in cell[(a, s, 2)]]) \
        if cell[(a, s, 2)] else float("nan")
    misp = mean(a, s, 3, "br_misp_retired.all_branches:u")
    clears = mean(a, s, 4, "machine_clears.count:u")
    return [
        ("all-ring: user cycles share (G2..G8 legs)", 2, lambda p: p["cycles:u"] / tot(p), "pct"),
        ("all-ring TMA: frontend bound", 1, lambda p: p["idq_uops_not_delivered.core"] / (4 * p["cycles"]), "pct"),
        ("all-ring TMA: bad speculation", 1, lambda p: (p["uops_issued.any"] - p["uops_retired.retire_slots"]
                                                       + 4 * p["int_misc.recovery_cycles"]) / (4 * p["cycles"]), "pct"),
        ("all-ring TMA: retiring", 1, lambda p: p["uops_retired.retire_slots"] / (4 * p["cycles"]), "pct"),
        ("all-ring TMA: backend bound", 1, lambda p: 1 - (p["idq_uops_not_delivered.core"] + p["uops_issued.any"]
                                                         + 4 * p["int_misc.recovery_cycles"]) / (4 * p["cycles"]), "pct"),
        ("user TMA: frontend bound", 2, lambda p: p["idq_uops_not_delivered.core:u"] / (4 * p["cycles:u"]), "pct"),
        ("user TMA: bad speculation", 2, lambda p: (p["uops_issued.any:u"] - p["uops_retired.retire_slots:u"]
                                                    + 4 * rec_u) / (4 * p["cycles:u"]), "pct"),
        ("user TMA: retiring", 2, lambda p: p["uops_retired.retire_slots:u"] / (4 * p["cycles:u"]), "pct"),
        ("user TMA: backend bound", 2, lambda p: 1 - (p["idq_uops_not_delivered.core:u"] + p["uops_issued.any:u"]
                                                      + 4 * rec_u) / (4 * p["cycles:u"]), "pct"),
        ("user L2: fetch latency", 3, lambda p: p["idq_uops_not_delivered.cycles_0_uops_deliv.core:u"] / p["cycles:u"], "pct"),
        ("user L2: fetch bandwidth (FE mean - fetch latency)", 3,
         lambda p: fe_u_mean - p["idq_uops_not_delivered.cycles_0_uops_deliv.core:u"] / p["cycles:u"], "pct"),
        ("user L2: branch mispredicts (share of bad spec x bad spec)", 3,
         lambda p: (p["br_misp_retired.all_branches:u"] / (p["br_misp_retired.all_branches:u"] + clears))
         * (iss_u - ret_u + 4 * p["int_misc.recovery_cycles:u"]) / (4 * p["cycles:u"]), "pct"),
        ("user L2: machine clears", 4,
         lambda p: (p["machine_clears.count:u"] / (misp + p["machine_clears.count:u"]))
         * (iss_u - ret_u + 4 * rec_u) / (4 * p["cycles:u"]), "pct"),
        ("user L2: heavy operations (MS)", 4, lambda p: (ret_u / iss_u) * p["idq.ms_uops:u"] / (4 * p["cycles:u"]), "pct"),
        ("user IPC", 2, lambda p: p["instructions:u"] / p["cycles:u"], "f2"),
        ("instructions:u per request", 2, lambda p: p["instructions:u"], "k"),
        ("cycles:u per request", 2, lambda p: p["cycles:u"], "k"),
        ("cycles total per request", 2, tot, "k"),
        ("iTLB walk cycles / user cycles", 5, lambda p: p["itlb_misses.walk_duration:u"] / p["cycles:u"], "pct"),
        ("iTLB walk cycles / total cycles", 5, lambda p: p["itlb_misses.walk_duration:u"] / tot(p), "pct"),
        ("iTLB walks per request", 5, lambda p: p["itlb_misses.walk_completed:u"], "f1"),
        ("cycles per iTLB walk", 5, lambda p: p["itlb_misses.walk_duration:u"] / max(p["itlb_misses.walk_completed:u"], 1), "f1"),
        ("i-cache stall cycles / user cycles", 5, lambda p: p["icache.ifdata_stall:u"] / p["cycles:u"], "pct"),
        ("i-cache misses per request", 6, lambda p: p["icache.misses:u"], "f1"),
        ("i-cache misses per 1k instructions", 6, lambda p: 1000 * p["icache.misses:u"] / p["instructions:u"], "f2"),
        ("DSB share of uops (DSB/(DSB+MITE+MS))", 6, lambda p: p["idq.dsb_uops:u"] / (p["idq.dsb_uops:u"] + p["idq.mite_uops:u"] + ms_u), "pct"),
        ("MITE share of uops", 6, lambda p: p["idq.mite_uops:u"] / (p["idq.dsb_uops:u"] + p["idq.mite_uops:u"] + ms_u), "pct"),
        ("branch mispredicts per request", 3, lambda p: p["br_misp_retired.all_branches:u"], "f1"),
        ("branch mispredicts per 1k instructions", 3, lambda p: 1000 * p["br_misp_retired.all_branches:u"] / p["instructions:u"], "f2"),
        ("BAClears per request", 4, lambda p: p["baclears.any:u"], "f1"),
        ("machine clears per request", 4, lambda p: p["machine_clears.count:u"], "f2"),
        ("L1d replacements per request", 7, lambda p: p["l1d.replacement:u"], "f1"),
        ("L2 misses per request", 7, lambda p: p["l2_rqsts.miss:u"], "f1"),
        ("LLC misses per request", 7, lambda p: p["longest_lat_cache.miss:u"], "f2"),
        ("L1d repl per 1k instructions", 7, lambda p: 1000 * p["l1d.replacement:u"] / p["instructions:u"], "f2"),
        ("L2 misses per 1k instructions", 7, lambda p: 1000 * p["l2_rqsts.miss:u"] / p["instructions:u"], "f2"),
        ("data-side cost bound (12xL1d + 40xL2) / user cycles", 7,
         lambda p: (12 * p["l1d.replacement:u"] + 40 * p["l2_rqsts.miss:u"]) / p["cycles:u"], "pct"),
        ("memory stall cycles (stalls_mem_any) / user cycles", 8, lambda p: p["cycle_activity.stalls_mem_any:u"] / p["cycles:u"], "pct"),
        ("store-buffer stall cycles / user cycles", 8, lambda p: p["resource_stalls.sb:u"] / p["cycles:u"], "pct"),
        ("all stall cycles (stalls_total) / user cycles", 8, lambda p: p["cycle_activity.stalls_total:u"] / p["cycles:u"], "pct"),
    ]


def fmt(v, f):
    if v != v:
        return "n/a"
    return {"pct": "%.1f%%" % (100 * v), "f2": "%.2f" % v, "f1": "%.1f" % v, "k": "%.1fk" % (v / 1e3)}[f]


res = {}
lines = ["# Top-down counter tables (generated by analyse.py)", "",
         "Legs: %d, valid %d. Invalid: %s" % (len(legs), len(valid), invalid or "none"), ""]
for s in SHAPES:
    lines += ["## shape `%s`" % s, "", "| metric | G | stock (rounds) | stock mean | pgolto (rounds) | pgolto mean |",
              "|---|---|---|---|---|---|"]
    for i, (name, g, fn, f) in enumerate(metrics("stock", s)):
        row = ["%s" % name, "G%d" % g]
        for a in ARMS:
            fn_a = metrics(a, s)[i][2]
            try:
                v = vals(a, s, g, fn_a)
            except (KeyError, ZeroDivisionError):
                v = []
            res[(a, s, name)] = [x for _, x in v]
            row += [" / ".join(fmt(x, f) for _, x in v) or "n/a", fmt(st.mean([x for _, x in v]), f) if v else "n/a"]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")


def m_(a, s, name):
    v = res.get((a, s, name)) or []
    return (st.mean(v), min(v), max(v)) if v else (float("nan"),) * 3


dec = []


def decide(item, measured, keep, why):
    dec.append((item, measured, "KEEP" if keep is True else ("KILL" if keep is False else "UNDECIDED"), why))


def thr(vals3, t):
    """True if all >= t, False if all < t, None if straddling."""
    _, lo, hi = vals3
    if lo >= t:
        return True
    if hi < t:
        return False
    return None


w = {s: m_("stock", s, "iTLB walk cycles / user cycles") for s in SHAPES}
k = [thr(w[s], 0.03) for s in ("s", "fh")]
keep = True if True in k else (False if all(x is False for x in k) and thr(w["fl"], 0.03) is not True else None)
decide("huge-page text (stock)", ", ".join("%s %.2f%% [%.2f-%.2f]" % (s, 100 * w[s][0], 100 * w[s][1], 100 * w[s][2]) for s in SHAPES),
       keep, "iTLB walk cycles / user cycles >= 3% on s or fh keeps")
wp = {s: m_("pgolto", s, "iTLB walk cycles / user cycles") for s in SHAPES}
decide("huge-page text on pgolto", ", ".join("%s %.2f%%" % (s, 100 * wp[s][0]) for s in SHAPES),
       True if any(thr(wp[s], 0.03) is True for s in SHAPES) else (False if all(thr(wp[s], 0.03) is False for s in SHAPES) else None),
       ">= 3% keeps a pgolto arm")
fe = {a: {s: m_(a, s, "user TMA: frontend bound") for s in SHAPES} for a in ARMS}
k10 = [thr(fe["stock"][s], 0.15) for s in ("s", "fh")]
lev = all(fe["stock"][s][0] - fe["pgolto"][s][0] >= 0.05 for s in ("s", "fh"))
keep10 = (True if lev else False) if all(x is True for x in k10) else (False if any(x is False for x in k10) else None)
decide("call-graph ordering file", "stock FE " + ", ".join("%s %.1f%%" % (s, 100 * fe["stock"][s][0]) for s in SHAPES)
       + "; pgolto FE " + ", ".join("%s %.1f%%" % (s, 100 * fe["pgolto"][s][0]) for s in SHAPES),
       keep10, "stock user FE >= 15% on s and fh, and pgolto at least 5 points lower")
ic = {a: {s: m_(a, s, "i-cache stall cycles / user cycles") for s in SHAPES} for a in ARMS}
k22 = [thr(ic["stock"][s], 0.10) for s in ("s", "fh")]
# share of stock i-cache stall cycles per request that pgolto removes
cyc = {a: {s: m_(a, s, "cycles:u per request")[0] for s in SHAPES} for a in ARMS}
rem = {s: 1 - (ic["pgolto"][s][0] * cyc["pgolto"][s]) / (ic["stock"][s][0] * cyc["stock"][s]) for s in SHAPES}
keep22 = None
if all(x is False for x in k22):
    keep22 = False
elif any(x is True for x in k22):
    keep22 = all(rem[s] <= 0.5 for s in ("s", "fh"))
decide("cold log sites", "stock i-cache stall " + ", ".join("%s %.1f%%" % (s, 100 * ic["stock"][s][0]) for s in SHAPES)
       + "; pgolto removes " + ", ".join("%s %.0f%%" % (s, 100 * rem[s]) for s in SHAPES) + " of the stall cycles/req",
       keep22, "stock i-cache stall >= 10% and pgolto removes at most half")
k8 = [thr(fe["pgolto"][s], 0.25) for s in SHAPES]
decide("BOLT/Propeller on pgolto", "pgolto FE " + ", ".join("%s %.1f%%" % (s, 100 * fe["pgolto"][s][0]) for s in SHAPES),
       True if any(x is True for x in k8) else (False if all(x is False for x in k8) else None), "pgolto user FE > 25% keeps")
dc = m_("stock", "fl", "data-side cost bound (12xL1d + 40xL2) / user cycles")
ms = m_("stock", "fl", "memory stall cycles (stalls_mem_any) / user cycles")
a20, b20 = thr(dc, 0.03), thr(ms, 0.10)
decide("HeaderString (data side)", "fl stock data-side bound %.1f%% [%.1f-%.1f], memory stalls %.1f%% [%.1f-%.1f]"
       % (100 * dc[0], 100 * dc[1], 100 * dc[2], 100 * ms[0], 100 * ms[1], 100 * ms[2]),
       True if (a20 is True and b20 is True) else (False if (a20 is False or b20 is False) else None),
       "data-side bound >= 3% and memory stalls >= 10% keep")

lines += ["## Decisions (counters)", "", "| follow-up | measured (stock unless named) | verdict | rule |", "|---|---|---|---|"]
for d in dec:
    lines.append("| %s | %s | %s | %s |" % d)
lines.append("")
# harness cycles comparison by-product
lines += ["## cycles_total per request, all 24 rounds (by-product)", "", "| shape | stock mean | pgolto mean | ratio |", "|---|---|---|---|"]
for s in SHAPES:
    c = {a: [tot(pr) for g in range(1, NG + 1) for _, pr, _ in cell[(a, s, g)]] for a in ARMS}
    if c["stock"] and c["pgolto"]:
        lines.append("| %s | %.1fk | %.1fk | %.3f |" % (s, st.mean(c["stock"]) / 1e3, st.mean(c["pgolto"]) / 1e3,
                                                      st.mean(c["pgolto"]) / st.mean(c["stock"])))
lines.append("")
# leg health
lines += ["## leg health", "", "| shape | arm | rate (min) | sut_busy mean | eff GHz mean | upstream rq / response |", "|---|---|---|---|---|---|"]
for s in SHAPES:
    for a in ARMS:
        L = [m for g in range(1, NG + 1) for _, _, m in cell[(a, s, g)]]
        if not L:
            continue
        up = [((m.get("sut_stats_delta") or {}).get("cluster.origin.upstream_rq_total", 0)) / max(m.get("responses_raw") or 1, 1) for m in L]
        lines.append("| %s | %s | %.1f | %.1f%% | %.3f | %.3f |" % (s, a, min(m["sut_rate_2xx"] for m in L),
                     100 * st.mean(m["sut_busy"] for m in L), st.mean(m.get("eff_ghz") or 0 for m in L), st.mean(up)))
open(out, "w").write("\n".join(lines) + "\n")
json.dump({"decisions": dec}, open(out.replace(".md", ".json"), "w"), indent=1)
print("\n".join(lines[-40:]))
