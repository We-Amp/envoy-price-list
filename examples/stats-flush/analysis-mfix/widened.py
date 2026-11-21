#!/usr/bin/env python3
"""Run M-fix: the own-build rows with the interval widened by the rung's own A/A.

    python3 examples/stats-flush/analysis-mfix/widened.py [TABLES_JSON] > widened.txt

TABLES_JSON: the JSON that table.py writes (default data/stats/sink-flush-cost/tables.json). Its
"mfix" rows carry, per rung, the paired log ratio of main-thread run time per second (top
against main, 5 rounds: mean, standard error, t half-width) and the A/A row of the rung (a
second copy of main against main).

The A/A of all three rungs misses its 2% half-width target. A fix row is therefore widened by
its rung's A/A half-width in place of the fixed 0.34 term that table.py's "Widened" column uses:

    half-width = max(t half-width, 1.96 x sqrt(SE^2 + AA^2))        (log-percent)

A row is a finding only if that interval excludes zero.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(x):
    return 100.0 * (math.exp(x / 100.0) - 1.0)


def widened_half_width(hw, se, aa):
    return max(hw, 1.96 * math.sqrt(se * se + aa * aa))


def rows(tables):
    """[(shape, arm, ref, effect %, plain (lo, hi) %, A/A half-width, widened (lo, hi) %, pairs)]."""
    aa = {r["shape"]: r["hw"] for r in tables["mfix"] if r["family"] == "mfix-aa" and not r.get("missing")}
    out = []
    for r in tables["mfix"]:
        if r["family"] != "mfix" or r.get("missing"):
            continue
        w = widened_half_width(r["hw"], r["se"], aa[r["shape"]])
        out.append((r["shape"], r["arm"], r["ref"], r["effect_pct"], (r["lo_pct"], r["hi_pct"]), aa[r["shape"]],
                    (pct(r["log_mean"] - w), pct(r["log_mean"] + w)), r["n"]))
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "..", "data", "stats", "sink-flush-cost",
                                                              "tables.json")
    with open(path) as f:
        tables = json.load(f)
    print("Run M-fix, main-thread run time per second, top (the fix) against main (its base); 95% intervals")
    print("| Rung | Arm vs ref | Effect [plain t interval] | A/A half-width | Widened by the A/A | Rounds | Widened interval excludes zero |")
    print("|---|---|---|---|---|---|---|")
    for shape, arm, ref, eff, plain, aa, wide, n in rows(tables):
        print("| %s | %s vs %s | %+.1f%% [%+.1f, %+.1f] | %.2f%% | [%+.1f, %+.1f] | %d | %s |" % (
            shape.replace("idle-", ""), arm, ref, eff, plain[0], plain[1], aa, wide[0], wide[1], n,
            "yes" if wide[0] > 0 or wide[1] < 0 else "no"))


if __name__ == "__main__":
    main()
