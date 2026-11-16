#!/usr/bin/env python3
"""Tables of the route-table and constant-header runs.

    python3 examples/route-table/table.py RUN_DIR [RUN_DIR ...] [--json OUT.json] > tables.md

For each run (results.json in RUN_DIR), per shape:

- busy share of the four workers and medians per arm (instructions:u, total cycles,
  p50, p99);
- every arm against base: instructions:u, cycles:u, cycles:k, total cycles (primary,
  with the run's Holm p), p50 and p99, as the mean per-round log ratio turned into a
  percentage with its 95% t interval, the interval widened by the between-session A/A
  spread (1.96 * sqrt(SE^2 + 0.34^2), never narrower than the run's own), the pairs
  in which the arm was lower, and a verdict;
- extra pairs that are not against base (d2v3 against d1v4) from the same paired
  rounds: exploratory, interval only.

Verdicts as in examples/releases/table.py: "within the A/A spread" when |effect| < 1%;
for a primary row "not resolved after Holm" when Holm p > 0.05; "about X%, not
resolved" when the run's interval excludes 0 but the widened one does not; "differs"
otherwise when the widened interval excludes 0.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import experiment, stats  # noqa: E402

TAU = 0.34
METRICS = [("instructions_u", "instructions:u"), ("cycles_u", "cycles:u"), ("cycles_k", "cycles:k"),
           ("cycles_total", "total cycles"), ("p50_us", "p50"), ("p99_us", "p99")]
EXTRA_PAIRS = [("d2v3", "d1v4")]


def pct(x):
    return 100.0 * (math.exp(x / 100.0) - 1.0)


def widened(p):
    if p.get("half_width_pct") is None or p["n"] < 2:
        return None
    se = p["half_width_pct"] / stats.t_ppf(0.975, p["n"] - 1)
    return max(1.96 * math.sqrt(se * se + TAU * TAU), p["half_width_pct"])


def verdict(p, w, holm_p=None):
    m = p["log_mean_pct"]
    own = not (p["log_lo_pct"] <= 0.0 <= p["log_hi_pct"])
    if abs(m) < 1.0:
        return "within the A/A spread (< 1%)"
    if holm_p is not None and holm_p > 0.05:
        return "not resolved after Holm"
    if abs(m) > w:
        return "differs"
    if own:
        return "about %+.1f%%, not resolved" % pct(m)
    return "not resolved"


def row(p, w):
    return {"pct": pct(p["log_mean_pct"]), "lo": pct(p["log_lo_pct"]), "hi": pct(p["log_hi_pct"]),
            "wlo": pct(p["log_mean_pct"] - w), "whi": pct(p["log_mean_pct"] + w), "n": p["n"],
            "log_mean": p["log_mean_pct"], "hw": p["half_width_pct"], "widened_hw": w}


def fmt(r):
    return "%+.1f%% [%+.1f, %+.1f]" % (r["pct"], r["lo"], r["hi"])


def fmtw(r):
    return "[%+.1f, %+.1f]" % (r["wlo"], r["whi"])


def run_tables(run_dir, out, js):
    with open(os.path.join(run_dir, "results.json")) as f:
        res = json.load(f)
    exp, an, legs = res["experiment"], res["analysis"], res["legs"]
    name = exp["name"]
    base = an["base_arm"]
    arms = [a["name"] for a in exp["arms"]]
    nvalid = sum(1 for m in legs if m.get("verdict", {}).get("valid") and not m.get("superseded"))
    ninv = sum(1 for m in legs if not m.get("verdict", {}).get("valid"))
    js[name] = {"legs": len(legs), "valid_current": nvalid, "invalid": ninv, "rounds": an["rounds_done"],
                "primary_family": an["primary_family_size"], "shapes": {}}
    out.append("## %s\n" % name)
    out.append("%d legs recorded, %d valid and current, %d invalid; %d rounds; Holm over %d primary rows.\n" % (
        len(legs), nvalid, ninv, an["rounds_done"], an["primary_family_size"]))
    by = experiment.current_legs(legs)
    get = {k: g for k, _, g in experiment.METRICS}
    for sh in exp["shapes"]:
        s = sh["name"]
        sa = an["shapes"][s]
        jss = js[name]["shapes"][s] = {"rps": sh["rps"], "arms": {}, "vs_base": {}, "extra": {}}
        out.append("### %s @ %d req/s\n" % (s, sh["rps"]))
        out.append("| Arm | valid | busy (of 4 workers) | instructions:u/req (k) | total cycles/req (k) | p50 (us) | p99 (us) |")
        out.append("|---|---|---|---|---|---|---|")
        for a in arms:
            x = sa["arms"][a]
            med = lambda k: x.get(k, {}).get("median")  # noqa: E731
            jss["arms"][a] = {"valid": x["valid"], "busy": x.get("sut_busy_mean"),
                              **{k: med(k) for k, _ in METRICS}}
            out.append("| %s | %d | %.1f%% | %.1f | %.1f | %.0f | %.0f |" % (
                a, x["valid"], 100 * (x.get("sut_busy_mean") or 0), (med("instructions_u") or 0) / 1e3,
                (med("cycles_total") or 0) / 1e3, med("p50_us") or 0, med("p99_us") or 0))
        out.append("")
        out.append("| Arm vs %s | Metric | Effect [95%% CI] | Widened | Arm lower | Holm p | Verdict |" % base)
        out.append("|---|---|---|---|---|---|---|")
        for a in arms:
            if a == base:
                continue
            comp = sa["vs_base"].get(a, {})
            for k, lab in METRICS:
                c = comp.get(k)
                if not c or c.get("status") == "insufficient":
                    continue
                p = c["paired"]
                w = widened(p)
                hp = c.get("holm_p") if k == an["primary_metric"] else None
                r = row(p, w)
                lower = sum(1 for d in p["log_pcts"] if d < 0)
                r.update(lower=lower, holm_p=hp, verdict=verdict(p, w, hp))
                jss["vs_base"].setdefault(a, {})[k] = r
                out.append("| %s | %s | %s | %s | %d/%d | %s | %s |" % (
                    a, lab, fmt(r), fmtw(r), lower, p["n"], ("%.2g" % hp) if hp is not None else "–", r["verdict"]))
        for a, b in EXTRA_PAIRS:
            if a not in arms or b not in arms:
                continue
            for k, lab in METRICS:
                rounds = sorted(r for (ss, x, r) in by if ss == s and x == a and (s, b, r) in by)
                va, vb = [], []
                for rr in rounds:
                    try:
                        x1, x2 = get[k](by[(s, a, rr)]), get[k](by[(s, b, rr)])
                    except (KeyError, TypeError):
                        continue
                    if x1 and x2:
                        va.append(x1)
                        vb.append(x2)
                if len(va) < 6:
                    continue
                p = stats.paired_log_ratio(vb, va)
                w = widened(p)
                r = row(p, w)
                lower = sum(1 for d in p["log_pcts"] if d < 0)
                r.update(lower=lower, verdict=verdict(p, w) + " (exploratory)")
                jss["extra"].setdefault("%s vs %s" % (a, b), {})[k] = r
                out.append("| %s vs %s | %s | %s | %s | %d/%d | – | %s |" % (
                    a, b, lab, fmt(r), fmtw(r), lower, p["n"], r["verdict"]))
        out.append("")


def main():
    args = sys.argv[1:]
    jout = None
    if "--json" in args:
        i = args.index("--json")
        jout = args[i + 1]
        del args[i:i + 2]
    out, js = [], {}
    for d in args:
        run_tables(d, out, js)
    print("\n".join(out))
    if jout:
        with open(jout, "w") as f:
            json.dump(js, f, indent=1)


if __name__ == "__main__":
    main()
