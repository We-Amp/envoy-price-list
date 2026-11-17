#!/usr/bin/env python3
"""Tables of release record/1, first session.

    python3 examples/release-record/table.py a RUN_A_DIR [--json OUT.json] > tables-a.md
    python3 examples/release-record/table.py c RUN_C_DIR [--json OUT.json] > tables-c.md
    python3 examples/release-record/table.py b RUN_B_DIR [--json OUT.json] > tables-b.md

Run A: validity, the session A/A (v1.40.2-A2 against v1.40.2), the confirmatory rows
(v1.38.0 against v1.37.11 per cell, Holm over those four, from the run), the record rows
(v1.40.2 against every arm, Holm over 28, from the run; sign flipped so negative means
v1.40.2 is cheaper), exploratory steps from the same paired rounds, and per-arm medians
of instructions, user IPC and kernel cycles. Every interval is also printed widened by
the between-session A/A spread, 1.96 * sqrt(SE^2 + 0.34^2) (never narrower than the run's
own). Verdict rules as in examples/releases/table.py.

Run C: per arm and cell, top-down level 1 shares of issue slots (Broadwell, per thread:
slots = 4 x cycles; front-end bound = idq_uops_not_delivered.core / slots; bad speculation
= (uops_issued.any - uops_retired.retire_slots + 4 x int_misc.recovery_cycles) / slots;
retiring = uops_retired.retire_slots / slots; back-end bound = the rest) and events per
request, then paired comparisons (share differences in points, events as log ratios),
plus total cycles over all rounds. Exploratory throughout.

Run B: every patch against v1.38.0 and patch-to-patch steps, total cycles and
instructions, exploratory.
"""

import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import experiment, stats  # noqa: E402

_spec = importlib.util.spec_from_file_location("rel_table", os.path.join(HERE, "..", "releases", "table.py"))
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

ANCHOR, AA = "v1.40.2", "v1.40.2-A2"
A_ORDER = ["v1.37.0", "v1.37.11", "v1.38.0", "v1.38.9", "v1.39.6", "v1.40.0", "v1.40.2"]
A_STEPS = [("v1.37.0", "v1.37.11"), ("v1.38.0", "v1.38.9"), ("v1.40.0", "v1.40.2"),
           ("v1.37.11", "v1.38.0"), ("v1.38.9", "v1.39.6"), ("v1.39.6", "v1.40.0"),
           ("v1.37.11", "v1.38.9"), ("v1.38.9", "v1.40.2"), ("v1.37.11", "v1.40.2")]
C_PAIRS = [("v1.37.11", "v1.38.9"), ("v1.38.9", "v1.40.2"), ("v1.32.13", "v1.40.2"), ("v1.37.11", "v1.40.2")]
B_ORDER = ["v1.38.0", "v1.38.2", "v1.38.5", "v1.38.7", "v1.38.9"]


def load(d):
    with open(os.path.join(d, "results.json")) as f:
        return json.load(f)


def validity(res, out):
    legs = res["legs"]
    inv = [m for m in legs if not m.get("verdict", {}).get("valid")]
    cur = [m for m in legs if m.get("verdict", {}).get("valid") and not m.get("superseded")]
    md = res.get("metadata", {})
    out.append("Legs recorded %d, valid and current %d, invalid %d, superseded %d; rounds %s; stop: %s.\n" % (
        len(legs), len(cur), len(inv), sum(1 for m in legs if m.get("superseded")),
        res["analysis"]["rounds_done"], md.get("stop_reason")))
    for m in inv:
        out.append("- invalid %s: %s" % (m["leg_id"], "; ".join(m.get("verdict", {}).get("reasons", []))))
    if inv:
        out.append("")
    rates = {}
    for m in cur:
        r = m.get("sut_rate_2xx")
        if r:
            rates.setdefault(m["shape"], []).append(r / m["target_rps"] - 1.0)
    for s, v in rates.items():
        out.append("- %s: in-window rate %+.2f%% to %+.2f%% of target; overflow max %s; headroom min %.2f" % (
            s, 100 * min(v), 100 * max(v),
            max(m.get("client_overflow") or 0 for m in cur if m["shape"] == s),
            min(m.get("client_headroom") or 0 for m in cur if m["shape"] == s)))
    out.append("")


def row(p, w, flip=False):
    return T.fmt_iv(p["log_mean_pct"], p["log_lo_pct"], p["log_hi_pct"], flip), T.fmt_w(p["log_mean_pct"], w, flip)


def run_a(res, out, js):
    an = res["analysis"]
    shapes = [s["name"] for s in res["experiment"]["shapes"]]
    rates = {s["name"]: s["rps"] for s in res["experiment"]["shapes"]}
    by = experiment.current_legs(res["legs"])
    out.append("## Run A\n")
    validity(res, out)

    out.append("### A/A (v1.40.2-A2 against v1.40.2)\n")
    out.append("| Cell | Total cycles [95% CI] | Half-width | Widened | Reach (far end) | Holm p (28) | Instructions:u hw |")
    out.append("|---|---|---|---|---|---|---|")
    js["aa"] = {}
    for s in shapes:
        comp = an["shapes"][s]["vs_base"][AA]
        c, p = comp["cycles_total"], comp["cycles_total"]["paired"]
        w = T.widened(p)
        reach = max(abs(T.pct(p["log_lo_pct"])), abs(T.pct(p["log_hi_pct"])))
        reach_w = abs(p["log_mean_pct"]) + w
        js["aa"][s] = {"pct": T.pct(p["log_mean_pct"]), "hw": p["half_width_pct"], "widened": w, "reach": reach,
                       "reach_widened": reach_w, "holm_p": c.get("holm_p"), "n": c["n"]}
        out.append("| %s @ %d | %s | %.2f | %.2f | %.2f (%.2f widened) | %.3f | %.3f |" % (
            s, rates[s], row(p, w)[0], p["half_width_pct"], w, reach, reach_w, c.get("holm_p", 1.0),
            comp["instructions_u"]["paired"]["half_width_pct"]))
    out.append("")

    out.append("### Confirmatory: v1.38.0 against v1.37.11 (Holm over these 4)\n")
    out.append("| Cell | Total cycles [95% CI] | Widened | Holm p (4) | Rounds v1.38.0 dearer | A/A reach | Verdict |")
    out.append("|---|---|---|---|---|---|---|")
    js["confirmatory"] = {}
    for s in shapes:
        comp = an["shapes"][s]["confirmatory"][0]
        c = comp["cycles_total"]
        p = c["paired"]
        w = T.widened(p)
        v = T.verdict(p, w, c.get("holm_p", 1.0))
        js["confirmatory"][s] = {"pct": T.pct(p["log_mean_pct"]), "lo": T.pct(p["log_lo_pct"]),
                                 "hi": T.pct(p["log_hi_pct"]), "widened_lo": T.pct(p["log_mean_pct"] - w),
                                 "widened_hi": T.pct(p["log_mean_pct"] + w), "hw": p["half_width_pct"],
                                 "holm_p": c.get("holm_p"), "n": c["n"], "dearer": c["pairs_lost"], "verdict": v}
        out.append("| %s @ %d | %s | %s | %.3g | %d/%d | %.2f | %s |" % (
            s, rates[s], row(p, w)[0], row(p, w)[1], c.get("holm_p", 1.0), c["pairs_lost"], c["n"],
            js["aa"][s]["reach"], v))
    out.append("")

    out.append("### Record rows: v1.40.2 against each arm (Holm over 28; negative = v1.40.2 cheaper)\n")
    out.append("| Cell | v1.40.2 vs | Effect [95% CI] | Widened | Holm p | Median k cycles arm → v1.40.2 | Verdict |")
    out.append("|---|---|---|---|---|---|---|")
    js["record"] = {}
    for s in shapes:
        for a in A_ORDER[:-1]:
            c = an["shapes"][s]["vs_base"][a]["cycles_total"]
            p = c["paired"]
            w = T.widened(p)
            fp = {"log_mean_pct": -p["log_mean_pct"], "log_lo_pct": -p["log_hi_pct"], "log_hi_pct": -p["log_lo_pct"]}
            v = T.verdict(fp, w, c.get("holm_p", 1.0))
            am = an["shapes"][s]["arms"][a]["cycles_total"]["median"]
            bm = an["shapes"][s]["arms"][ANCHOR]["cycles_total"]["median"]
            js["record"].setdefault(s, {})[a] = {"v140_vs_pct": T.pct(fp["log_mean_pct"]), "lo": T.pct(fp["log_lo_pct"]),
                                                "hi": T.pct(fp["log_hi_pct"]),
                                                "widened_lo": T.pct(fp["log_mean_pct"] - w),
                                                "widened_hi": T.pct(fp["log_mean_pct"] + w),
                                                "holm_p": c.get("holm_p"), "verdict": v}
            out.append("| %s @ %d | %s | %s | %s | %.3g | %.1f → %.1f | %s |" % (
                s, rates[s], a, row(p, w, True)[0], row(p, w, True)[1], c.get("holm_p", 1.0), am / 1e3, bm / 1e3, v))
    out.append("")

    out.append("### Exploratory steps (later against earlier, same paired rounds)\n")
    out.append("| Step | " + " | ".join("%s @ %d" % (s, rates[s]) for s in shapes) + " |")
    out.append("|---|" + "---|" * len(shapes))
    js["steps"] = {}
    for old, new in A_STEPS:
        cells = []
        for s in shapes:
            rb, ra = T.metric_vals(by, s, new, old, "cycles_total")
            p = stats.paired_log_ratio(rb, ra)
            w = T.widened(p)
            hi = sum(1 for x, y in zip(rb, ra) if y > x)
            js["steps"].setdefault("%s->%s" % (old, new), {})[s] = {
                "pct": T.pct(p["log_mean_pct"]), "lo": T.pct(p["log_lo_pct"]), "hi": T.pct(p["log_hi_pct"]),
                "widened_lo": T.pct(p["log_mean_pct"] - w), "widened_hi": T.pct(p["log_mean_pct"] + w),
                "t_p": p["t_p"], "dearer": hi, "n": p["n"], "verdict": T.verdict(p, w)}
            cells.append("%s w%s, %d/%d dearer" % (row(p, w)[0], row(p, w)[1], hi, p["n"]))
        out.append("| %s → %s | %s |" % (old, new, " | ".join(cells)))
    out.append("")

    out.append("### Per arm medians (exploratory): instructions:u k / user IPC / cycles:k k / busy\n")
    out.append("| Arm | " + " | ".join(shapes) + " |")
    out.append("|---|" + "---|" * len(shapes))
    js["medians"] = {}
    for a in A_ORDER + [AA]:
        cells = []
        for s in shapes:
            x = an["shapes"][s]["arms"][a]
            iu, cu, ck = (x[k]["median"] for k in ("instructions_u", "cycles_u", "cycles_k"))
            ct = x["cycles_total"]["median"]
            js["medians"].setdefault(a, {})[s] = {"ins_u": iu, "cyc_u": cu, "cyc_k": ck, "cyc_total": ct,
                                                 "ipc_u": iu / cu, "busy": x.get("sut_busy_mean")}
            cells.append("%.1f / %.3f / %.1f / %.0f%%" % (iu / 1e3, iu / cu, ck / 1e3, 100 * (x.get("sut_busy_mean") or 0)))
        out.append("| %s | %s |" % (a, " | ".join(cells)))
    out.append("")
    out.append("### Kernel cycles and instructions, steps (exploratory)\n")
    out.append("| Step | Metric | " + " | ".join(shapes) + " |")
    out.append("|---|---|" + "---|" * len(shapes))
    for old, new in A_STEPS:
        for k in ("instructions_u", "cycles_k"):
            cells = []
            for s in shapes:
                rb, ra = T.metric_vals(by, s, new, old, k)
                p = stats.paired_log_ratio(rb, ra)
                cells.append(T.fmt_iv(p["log_mean_pct"], p["log_lo_pct"], p["log_hi_pct"]))
                js.setdefault("steps_other", {}).setdefault("%s->%s" % (old, new), {}).setdefault(k, {})[s] = \
                    T.pct(p["log_mean_pct"])
            out.append("| %s → %s | %s | %s |" % (old, new, k, " | ".join(cells)))
    out.append("")


def topdown(m):
    pv = m.get("perf_raw") or {}
    cyc = pv.get("cycles")
    if not cyc:
        return None
    out = {}
    if "uops_issued.any" in pv:
        slots = 4.0 * cyc
        fe = pv["idq_uops_not_delivered.core"] / slots
        bs = (pv["uops_issued.any"] - pv["uops_retired.retire_slots"] + 4.0 * pv["int_misc.recovery_cycles"]) / slots
        ret = pv["uops_retired.retire_slots"] / slots
        out.update(fe_bound=100 * fe, bad_spec=100 * bs, retiring=100 * ret, be_bound=100 * (1 - fe - bs - ret))
    return out


def run_c(res, out, js):
    an = res["analysis"]
    shapes = [s["name"] for s in res["experiment"]["shapes"]]
    rates = {s["name"]: s["rps"] for s in res["experiment"]["shapes"]}
    by = experiment.current_legs(res["legs"])
    groups = res["experiment"]["measure"]["perf_event_groups"]
    out.append("## Run C (counters, exploratory)\n")
    validity(res, out)
    worst = min((m.get("perf_min_running_pct") or 0) for m in by.values())
    out.append("Lowest counter running share over all valid legs: %.2f%% (100 = never multiplexed).\n" % worst)

    def leg_vals(m):
        v = dict(topdown(m) or {})
        pr = m.get("per_req") or {}
        for k, x in (pr.get("events") or {}).items():
            v["ev:" + k] = x
        v["cycles_total"] = pr.get("cycles_total")
        v["instructions_u"] = pr.get("instructions_u")
        return v

    vals = {k: leg_vals(m) for k, m in by.items()}
    keys = sorted({k for v in vals.values() for k in v})
    arms = [a["name"] for a in res["experiment"]["arms"]]
    out.append("### Per arm means (top-down shares in % of slots; events per request)\n")
    js["means"] = {}
    for s in shapes:
        out.append("**%s @ %d**\n" % (s, rates[s]))
        out.append("| Metric | " + " | ".join(arms) + " |")
        out.append("|---|" + "---|" * len(arms))
        for k in keys:
            cells = []
            for a in arms:
                xs = [vals[(ss, aa, r)][k] for (ss, aa, r) in vals if ss == s and aa == a and vals[(ss, aa, r)].get(k) is not None]
                mu = stats.mean(xs) if xs else None
                js["means"].setdefault(s, {}).setdefault(a, {})[k] = mu
                cells.append("–" if mu is None else ("%.2f" % mu if abs(mu) < 1e4 else "%.1fk" % (mu / 1e3)))
            out.append("| %s | %s |" % (k, " | ".join(cells)))
        out.append("")
    out.append("### Paired comparisons (later against earlier; shares: difference in points, t interval; "
               "events and cycles: log ratio %)\n")
    out.append("| Cell | Pair | Metric | Effect [95% CI] | n |")
    out.append("|---|---|---|---|---|")
    js["pairs"] = {}
    for s in shapes:
        for old, new in C_PAIRS:
            rounds = sorted(r for (ss, aa, r) in vals if ss == s and aa == new and (s, old, r) in vals)
            for k in keys:
                pr = [(vals[(s, old, r)].get(k), vals[(s, new, r)].get(k)) for r in rounds]
                pr = [(x, y) for x, y in pr if x is not None and y is not None]
                if len(pr) < 4:
                    continue
                if k in ("fe_bound", "bad_spec", "retiring", "be_bound"):
                    d = [y - x for x, y in pr]
                    n = len(d)
                    mu, sd = stats.mean(d), stats.stdev(d)
                    hw = stats.t_ppf(0.975, n - 1) * sd / math.sqrt(n)
                    txt = "%+.2f pt [%+.2f, %+.2f]" % (mu, mu - hw, mu + hw)
                    js["pairs"].setdefault(s, {}).setdefault("%s->%s" % (old, new), {})[k] = {
                        "pt": mu, "lo": mu - hw, "hi": mu + hw, "n": n}
                else:
                    p = stats.paired_log_ratio([x for x, _ in pr], [y for _, y in pr])
                    n = p["n"]
                    txt = T.fmt_iv(p["log_mean_pct"], p["log_lo_pct"], p["log_hi_pct"])
                    js["pairs"].setdefault(s, {}).setdefault("%s->%s" % (old, new), {})[k] = {
                        "pct": T.pct(p["log_mean_pct"]), "lo": T.pct(p["log_lo_pct"]), "hi": T.pct(p["log_hi_pct"]),
                        "n": n}
                out.append("| %s | %s → %s | %s | %s | %d |" % (s, old, new, k, txt, n))
    out.append("")
    js["groups"] = groups


def run_b(res, out, js):
    shapes = [s["name"] for s in res["experiment"]["shapes"]]
    rates = {s["name"]: s["rps"] for s in res["experiment"]["shapes"]}
    by = experiment.current_legs(res["legs"])
    out.append("## Run B (patch bisection, exploratory)\n")
    validity(res, out)
    out.append("| Pair | Metric | " + " | ".join("%s @ %d" % (s, rates[s]) for s in shapes) + " |")
    out.append("|---|---|" + "---|" * len(shapes))
    pairs = [("v1.38.0", b) for b in B_ORDER[1:]] + list(zip(B_ORDER[1:-1], B_ORDER[2:]))
    for old, new in pairs:
        for k in ("cycles_total", "instructions_u"):
            cells = []
            for s in shapes:
                rb, ra = T.metric_vals(by, s, new, old, k)
                p = stats.paired_log_ratio(rb, ra)
                w = T.widened(p)
                cells.append("%s w%s" % row(p, w))
                js.setdefault("pairs", {}).setdefault("%s->%s" % (old, new), {}).setdefault(k, {})[s] = {
                    "pct": T.pct(p["log_mean_pct"]), "lo": T.pct(p["log_lo_pct"]), "hi": T.pct(p["log_hi_pct"]),
                    "widened_lo": T.pct(p["log_mean_pct"] - w), "widened_hi": T.pct(p["log_mean_pct"] + w)}
            out.append("| %s → %s | %s | %s |" % (old, new, k, " | ".join(cells)))
    out.append("")


def main():
    mode, d = sys.argv[1], sys.argv[2]
    jout = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    res = load(d)
    out, js = [], {}
    {"a": run_a, "c": run_c, "b": run_b}[mode](res, out, js)
    print("\n".join(out))
    if jout:
        with open(jout, "w") as f:
            json.dump(js, f, indent=1)


if __name__ == "__main__":
    main()
