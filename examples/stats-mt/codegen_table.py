#!/usr/bin/env python3
"""Tables of the arm64 atomics codegen run (make.py codegen*.json).

    python3 examples/stats-mt/codegen_table.py RUN_DIR [--json OUT.json] > codegen.md

Valid legs of complete rounds only; worker-only cycles per request (the wrk: threads) unless
--metric names a per-request field (instructions_u, cycles_total, ...). Per rung, paired by
round, log ratios in percent with a 95% t interval:

  A/A        official-A2 / official; passes with a half-width of at most 1% and an interval
             that includes zero. Without a passing A/A on a rung no row of that rung gets a
             verdict.
  price      the stats price of each binary: ln(official / official-reject) and
             ln(dev / dev-reject).
  primary    ln(dev / dev-reject) - ln(official / official-reject): how much more (positive)
             or less the stats cost in the inline LL/SC build than in the out-of-line
             helpers build. A finding needs an interval excluding zero and a mean of at least
             1% of the official build's cycles per request.
  absolute   (dev - dev-reject) - (official - official-reject) in cycles per request, paired
             by round: the same contrast without the baseline in the denominator (a build whose
             other work is slower shrinks its percentage with no change in the absolute cost).
  direct     dev / official: labelled confounded (the builds differ beyond the atomics).

The two rungs are two separate rows, each with its own A/A gate; there is no multiplicity
correction across them.

Beside them the level of each arm (median cycles and instructions per request) and the
instructions-per-request ratio dev / official, which shows whether the codegen difference is
visible in the instruction stream.
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import u_table  # noqa: E402
from epl import experiment, stats  # noqa: E402

AA_LIMIT_PCT = 1.0
FINDING_PCT = 1.0
ARMS = ("official", "official-reject", "dev", "dev-reject", "official-A2")


def per_round(by, shape, metric):
    """{round: {arm: value}} with every arm of the run present."""
    out = {}
    for (s, a, r), m in by.items():
        if s != shape:
            continue
        v = u_table.val(m, metric)
        if v is not None and v > 0:
            out.setdefault(r, {})[a] = v
    return {r: v for r, v in out.items() if all(a in v for a in ARMS)}


def lr(a, b):
    return 100.0 * math.log(a / b)


def interval(xs):
    t = u_table.t_interval(xs)
    if t.get("lo") is not None:
        t["half_width"] = (t["hi"] - t["lo"]) / 2.0
    return t


def rung_rows(rounds, incomplete=False):
    aa = interval([lr(v["official-A2"], v["official"]) for v in rounds.values()])
    p_off = interval([lr(v["official"], v["official-reject"]) for v in rounds.values()])
    p_dev = interval([lr(v["dev"], v["dev-reject"]) for v in rounds.values()])
    prim = interval([lr(v["dev"], v["dev-reject"]) - lr(v["official"], v["official-reject"])
                     for v in rounds.values()])
    direct = interval([lr(v["dev"], v["official"]) for v in rounds.values()])
    absolute = u_table.t_interval([(v["dev"] - v["dev-reject"]) - (v["official"] - v["official-reject"])
                                   for v in rounds.values()])
    price_abs = {"official": u_table.t_interval([v["official"] - v["official-reject"] for v in rounds.values()]),
                 "dev": u_table.t_interval([v["dev"] - v["dev-reject"] for v in rounds.values()])}
    aa_ok = (aa.get("half_width") is not None and aa["half_width"] <= AA_LIMIT_PCT and aa["lo"] <= 0 <= aa["hi"])
    if incomplete:
        verdict = experiment.INCOMPLETE
    elif not aa_ok:
        verdict = "no verdict (A/A did not pass)"
    elif prim.get("lo") is None:
        verdict = "no verdict (too few rounds)"
    elif prim["lo"] > 0 or prim["hi"] < 0:
        verdict = ("finding" if abs(prim["mean"]) >= FINDING_PCT else
                   "resolved but under %g%% (not a finding)" % FINDING_PCT)
    else:
        verdict = "no resolved difference; at most %.2f%%" % max(abs(prim["lo"]), abs(prim["hi"]))
    return {"rounds": len(rounds), "aa": aa, "aa_pass": aa_ok, "price_official": p_off, "price_dev": p_dev,
            "primary": prim, "primary_verdict": verdict, "absolute": absolute, "price_absolute": price_abs,
            "direct_confounded": direct}


def fmt(t):
    if t.get("lo") is None:
        return "%s (n=%d)" % ("-" if t.get("mean") is None else "%+.2f%%" % t["mean"], t["n"])
    return "%+.2f%% [%+.2f, %+.2f]" % (t["mean"], t["lo"], t["hi"])


def fmt_abs(t):
    if t.get("lo") is None:
        return "-" if t.get("mean") is None else "%+.0f (n=%d)" % (t["mean"], t["n"])
    return "%+.0f [%+.0f, %+.0f]" % (t["mean"], t["lo"], t["hi"])


def table(run_dir, metric=u_table.METRIC):
    res = u_table.load(run_dir)
    if res is None:
        raise SystemExit("no results.json in %s" % run_dir)
    by = u_table.usable(res)
    shapes = sorted({s for (s, a, r) in by}, key=lambda s: int("".join(c for c in s if c.isdigit()) or 0))
    L = ["# arm64 atomics codegen: official release against the main dev-image build\n",
         "Metric: %s, valid legs of complete rounds. Log ratios in percent, 95%% t interval over rounds. "
         "Primary: ln(dev / dev-reject) - ln(official / official-reject) (positive: store stats cost more in the "
         "inline LL/SC build). The direct dev / official row is confounded by every other difference between "
         "the builds.\n" % metric,
         "| Rung | Rounds | A/A | Stats price, official | Stats price, dev | Primary | Verdict | Direct (confounded) |",
         "|---|---|---|---|---|---|---|---|"]
    js = {"metric": metric, "rungs": {}}
    for s in shapes:
        rounds = per_round(by, s, metric)
        if not rounds:
            continue
        row = rung_rows(rounds, bool(res.get("metadata", {}).get("incomplete")))
        lvl = {}
        for a in ARMS:
            lvl[a] = {"value": stats.median([v[a] for v in rounds.values()])}
            ins = [u_table.val(by[(s, a, r)], "instructions_u") for r in rounds if (s, a, r) in by]
            ins = [x for x in ins if x]
            lvl[a]["instructions_u"] = stats.median(ins) if ins else None
        row["level"] = lvl
        if lvl["dev"]["instructions_u"] and lvl["official"]["instructions_u"]:
            row["instructions_u_dev_over_official"] = lvl["dev"]["instructions_u"] / lvl["official"]["instructions_u"]
        js["rungs"][s] = row
        L.append("| %s | %d | %s%s | %s | %s | %s | %s | %s |" % (
            s, row["rounds"], fmt(row["aa"]), "" if row["aa_pass"] else " (fails)", fmt(row["price_official"]),
            fmt(row["price_dev"]), fmt(row["primary"]), row["primary_verdict"], fmt(row["direct_confounded"])))
    L.append("")
    L.append("Absolute (cycles per request, 95%% t interval over rounds):\n")
    L.append("| Rung | Stats price, official | Stats price, dev | (dev - dev-reject) - (official - official-reject) |\n"
             "|---|---|---|---|")
    for s, row in js["rungs"].items():
        L.append("| %s | %s | %s | %s |" % (s, fmt_abs(row["price_absolute"]["official"]),
                                           fmt_abs(row["price_absolute"]["dev"]), fmt_abs(row["absolute"])))
    L.append("")
    L.append("The two rungs are separate rows with their own A/A gate; no multiplicity correction across them.\n")
    L.append("| Rung | Arm | Median %s | Median user instructions per request |\n|---|---|---|---|" % metric)
    for s, row in js["rungs"].items():
        for a in ARMS:
            ins = row["level"][a]["instructions_u"]
            L.append("| %s | %s | %.1f | %s |" % (s, a, row["level"][a]["value"], "%.1f" % ins if ins else "-"))
    L.append("")
    return "\n".join(L) + "\n", js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--json")
    ap.add_argument("--metric", default=u_table.METRIC)
    a = ap.parse_args()
    text, js = table(a.run_dir, a.metric)
    sys.stdout.write(text)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(js, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
