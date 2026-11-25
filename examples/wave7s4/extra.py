#!/usr/bin/env python3
"""Wave 7 S4, supplementary readings of the tracing run (analysis only, written after the run; every line is
Exploratory): how the candidate 4 rows move with the choice of the stock reference arm, the parts (user and
kernel cycles, user instructions), the per-round values behind the kill-line row, and the 1% increments.

    python3 examples/wave7s4/extra.py RUN_DIR(s4a-otel)"""
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
spec = importlib.util.spec_from_file_location("w7s4_table_x", os.path.join(HERE, "table.py"))
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


def q(d):
    mu, se, hw, _ = t.interval(d)
    h = max(hw, 1.96 * math.sqrt(se * se + 0.34 ** 2))
    return mu, mu - h, mu + h


def main(argv):
    d = json.load(open(os.path.join(argv[0].rstrip("/"), "results.json")))
    legs = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]

    def show(sh, a, r, met="cycles_total"):
        x = t.row(legs, sh, a, r, met)
        print("- %s: %s vs %s [%s]: %+.2f%% [%+.2f, %+.2f] (simple), %+.2f log points; paired difference %+.1fk ± %.1fk; up in %d of %d rounds" % (
            sh, a, r, met, x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1], x["log_pct"], x["diff_per_req"] / 1e3,
            x["diff_per_req_t_hw"] / 1e3, x["up"], x["n"]))

    for sh in ("s", "fh"):
        print("\n## shape %s\n" % sh)
        for a, r in (("patched-0", "stock-0-A2"), ("stock-0-A2", "notrace"), ("patched-0-guard-off", "stock-0-A2")):
            show(sh, a, r)
        for a, r in (("stock-0", "notrace"), ("patched-0", "notrace"), ("patched-0", "stock-0"), ("patched-0-guard-off", "stock-0"),
                     ("patched-1", "stock-1"), ("patched-notrace", "notrace")):
            for met in ("instructions_u", "cycles_u", "cycles_k"):
                show(sh, a, r, met)
        by = {}
        for m in legs:
            if m["shape"] == sh and t.valid(m):
                by.setdefault(m["round"], {})[m["arm"]] = m["per_req"]["cycles_total"]
        R = [x for _, x in sorted(by.items())]
        mu, lo, hi = q([100 * math.log(x["patched-0"] / math.sqrt(x["stock-0"] * x["stock-0-A2"])) for x in R])
        print("- %s: patched-0 vs the geometric mean of stock-0 and stock-0-A2: %+.2f%% [%+.2f, %+.2f] (simple)" % (
            sh, t.t3.sp(mu), t.t3.sp(lo), t.t3.sp(hi)))
        mu, lo, hi = q([100 * (math.log(x["patched-1"] / x["patched-0"]) - math.log(x["stock-1"] / x["stock-0"])) for x in R])
        print("- %s: the 1%% increment, (patched-1 vs patched-0) minus (stock-1 vs stock-0): %+.2f log points [%+.2f, %+.2f]" % (sh, mu, lo, hi))
        pr = [100 * (x["patched-0"] / x["notrace"] - 1) for x in R]
        print("- %s: patched-0 vs notrace per round, simple %%: %s; mean of the simple ratios %+.2f, median %+.2f; rounds above +4: %d of %d" % (
            sh, " ".join("%+.2f" % v for v in pr), sum(pr) / len(pr), sorted(pr)[len(pr) // 2 - 1] / 2 + sorted(pr)[len(pr) // 2] / 2,
            sum(1 for v in pr if v > 4.0), len(pr)))
        for drop in range(len(R)):
            rest = [100 * math.log(x["patched-0"] / x["notrace"]) for i, x in enumerate(R) if i != drop]
            print("  - without round %d: %+.2f%%" % (drop + 1, t.t3.sp(sum(rest) / len(rest))))
        rec = [100 * (x["stock-0"] / x["notrace"] - x["patched-0"] / x["notrace"]) for x in R]
        mu, _, hw, _ = t.interval(rec)
        print("- %s: points recovered per round (stock-0 minus patched-0, both against notrace): %s; mean %.2f ± %.2f (95%% t)" % (
            sh, " ".join("%.2f" % v for v in rec), mu, hw))
        print("- %s: cycles per request by round (k): %s" % (sh, "; ".join(
            "r%d notrace %.1f stock-0 %.1f stock-0-A2 %.1f patched-0 %.1f guard-off %.1f" % (
                i + 1, x["notrace"] / 1e3, x["stock-0"] / 1e3, x["stock-0-A2"] / 1e3, x["patched-0"] / 1e3, x["patched-0-guard-off"] / 1e3)
            for i, x in enumerate(R))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
