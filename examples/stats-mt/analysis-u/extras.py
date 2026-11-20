#!/usr/bin/env python3
"""Run U: figures quoted beside the table of u_table.py, recomputed from the leg records.

    python3 examples/stats-mt/analysis-u/extras.py [U_STUDY_DIR] > extras.txt

U_STUDY_DIR holds u/ and u-hitm/ (default: data/stats/multi-worker). Valid, current legs of
rounds in which a rung has both arms; paired by round; 95% t intervals. Nothing here is a
pre-stated row: the contrasts between rungs other than those against the 1-worker rung are
exploratory, and the HITM figures come from two evidence rounds.

1. The store-stat price per rung as a share of the base level, with the interval of the
   difference divided by the base mean.
2. Instructions per request removed by stats-reject (user plus kernel), per rung.
3. Differences of the price between rungs: 28w - 4w, 28w - 14w-one, 14w-split - 14w-one.
4. HITM loads per request (local plus remote): base level and base minus stats-reject.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))
from epl import stats  # noqa: E402

D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "..", "data", "stats", "multi-worker")
RUNGS = ["mt-1w", "mt-4w", "mt-14w-one", "mt-14w-split", "mt-28w"]


def legs(run):
    with open(os.path.join(D, run, "results.json")) as f:
        res = json.load(f)
    return [m for m in res["legs"] if m["verdict"]["valid"] and not m.get("superseded")]


def ti(xs):
    n, m = len(xs), stats.mean(xs)
    hw = stats.t_ppf(0.975, n - 1) * stats.stdev(xs) / math.sqrt(n)
    return n, m, m - hw, m + hw


def by_round(ls, rung, arm, get):
    return {m["round"]: get(m) for m in ls if m["shape"] == rung and m["arm"] == arm}


def delta(ls, rung, get):
    b, r = by_round(ls, rung, "base", get), by_round(ls, rung, "stats-reject", get)
    return {k: b[k] - r[k] for k in sorted(set(b) & set(r))}, b


U = legs("u")
cyc = lambda m: m["workers_cycles_per_req"]  # noqa: E731
ins = lambda m: m["per_req"]["instructions_u"] + m["per_req"]["instructions_k"]  # noqa: E731

print("1. Store-stat price (base - stats-reject, worker-only cycles per request) and its share of base")
dl = {}
for rung in RUNGS:
    d, b = delta(U, rung, cyc)
    dl[rung] = d
    n, m, lo, hi = ti(list(d.values()))
    bm = stats.mean([b[k] for k in d])
    print("   %-13s n %2d  %.2f [%.2f, %.2f] k cycles; base %.1fk; share %.2f%% [%.2f, %.2f]" % (
        rung, n, m / 1e3, lo / 1e3, hi / 1e3, bm / 1e3, 100 * m / bm, 100 * lo / bm, 100 * hi / bm))

print("\n2. Instructions per request removed (user + kernel, whole process)")
for rung in RUNGS:
    d, b = delta(U, rung, ins)
    n, m, lo, hi = ti(list(d.values()))
    bu = stats.mean([x["per_req"]["instructions_u"] for x in U if x["shape"] == rung and x["arm"] == "base"])
    print("   %-13s n %2d  %.2f [%.2f, %.2f] k instructions; %.1f%% of base user instructions" % (
        rung, n, m / 1e3, lo / 1e3, hi / 1e3, 100 * m / bu))

print("\n3. Price differences between rungs (paired by round; exploratory)")
for a, b in (("mt-28w", "mt-4w"), ("mt-28w", "mt-14w-one"), ("mt-14w-split", "mt-14w-one")):
    rs = sorted(set(dl[a]) & set(dl[b]))
    n, m, lo, hi = ti([dl[a][r] - dl[b][r] for r in rs])
    print("   delta(%s) - delta(%s): n %2d  %+.2fk [%+.2f, %+.2f]" % (a[3:], b[3:], n, m / 1e3, lo / 1e3, hi / 1e3))

print("\n4. HITM loads per request (evidence legs, mean over the rounds)")
H = legs("u-hitm")
EV = ("mem_load_uops_l3_hit_retired.xsnp_hitm", "mem_load_uops_l3_miss_retired.remote_hitm")


def ev(m, name):
    e = m["per_req"]["events"]
    return e[name] if e.get(name) is not None else e[name + ":u"]


for rung in RUNGS:
    row = {}
    for arm in ("base", "stats-reject"):
        ms = [m for m in H if m["shape"] == rung and m["arm"] == arm]
        row[arm] = [stats.mean([ev(m, n) for m in ms]) for n in EV]
    dloc, drem = row["base"][0] - row["stats-reject"][0], row["base"][1] - row["stats-reject"][1]
    print("   %-13s base local %.1f remote %.1f total %.1f; base - stats-reject: local %+.1f remote %+.1f total %+.1f" % (
        rung, row["base"][0], row["base"][1], sum(row["base"]), dloc, drem, dloc + drem))
