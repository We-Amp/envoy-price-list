#!/usr/bin/env python3
"""Arm codegen run: instructions per request removed by rejecting the store's stats, per build.

    python3 examples/stats-mt/analysis-codegen/extras.py [CODEGEN_RUN_DIR] > extras.txt

CODEGEN_RUN_DIR: the run's directory (default data/stats/arm-codegen/arm-vm/codegen). Valid,
current legs; per round the arm with every store stat minus the same build with reject_all;
mean over the rounds with a 95% t interval. User instructions of the whole process per request
(the table of codegen_table.py prints medians of the levels, which differ in the third digit).
If the two builds did the same stats work the two figures would agree; they do not quite.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))
from epl import stats  # noqa: E402

PAIRS = (("official", "official-reject"), ("dev", "dev-reject"))


def removed(legs, shape, arm, reject, get):
    """(n, mean, low, high) of arm - reject, paired by round."""
    a = {m["round"]: get(m) for m in legs if m["shape"] == shape and m["arm"] == arm}
    b = {m["round"]: get(m) for m in legs if m["shape"] == shape and m["arm"] == reject}
    d = [a[r] - b[r] for r in sorted(set(a) & set(b))]
    n, mean = len(d), stats.mean(d)
    hw = stats.t_ppf(0.975, n - 1) * stats.stdev(d) / math.sqrt(n)
    return n, mean, mean - hw, mean + hw


def main():
    run = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "..", "data", "stats", "arm-codegen",
                                                             "arm-vm", "codegen")
    with open(os.path.join(run, "results.json")) as f:
        legs = [m for m in json.load(f)["legs"] if m["verdict"]["valid"] and not m.get("superseded")]
    arms = {m["arm"] for m in legs}
    print("User instructions per request removed by reject_all (arm minus its reject arm, paired by round)")
    for shape in sorted({m["shape"] for m in legs}, key=lambda s: int(s[3:-1])):
        got = {}
        for arm, rej in PAIRS:
            if arm in arms and rej in arms:
                got[arm] = removed(legs, shape, arm, rej, lambda m: m["per_req"]["instructions_u"])
        for arm, (n, mean, lo, hi) in got.items():
            print("   %-7s %-8s %.2fk [%.2f, %.2f]  (%.1f, %d rounds)" % (shape, arm, mean / 1e3, lo / 1e3, hi / 1e3, mean, n))
        if len(got) == 2:
            o, d = got["official"][1], got["dev"][1]
            print("   %-7s the release removes %.1f%% more than the dev build (%.2fk against %.2fk per request)" % (
                shape, 100.0 * (o - d) / o, o / 1e3, d / 1e3))


if __name__ == "__main__":
    main()
