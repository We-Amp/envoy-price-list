#!/usr/bin/env python3
"""Tables of run L (flush latency) from a run directory: legs.jsonl, probe/ and main/ only.

    python3 lat_table.py RUN_DIR [--json OUT.json]

Definitions (epl/latency.py): a flush window is a burst of the main-thread series; a probe is
classed by its intended send time (IN, ONSET, POST, OUT; guard 20 ms); latency is done minus
intended. One contrast per leg, on p99 (primary), p50 and the share over 2 ms (secondary):

  L1  IN - OUT, all probe connections                  per own-core arm
  L2  ONSET - OUT, all connections                     the own-core arms pooled per round
  L3  (IN - OUT on the connections of the worker on the shared CPU) - (the same on the other
      workers' connections)                            per shared-core arm; the own-core legs
                                                       give the same contrast as a placebo

Row = mean over rounds with a 95% t interval, in us and as a share of the OUT value. Reach =
the largest absolute mean of the same contrast on sham windows (the leg's windows shifted on a
0.5 s grid, shifts that touch no real flush and are admissible in every leg of the row; at
least 2, else no verdict). Finding = Holm-adjusted p <= 0.05 over the six p99 rows and the
absolute mean above the larger of the reach and the floor. Rounds count only when every cell
has a valid leg; under 4 such rounds the run is incomplete and no row has a verdict.
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import evidence, experiment, latency, stats  # noqa: E402

MIN_ROUNDS = 4
ALPHA = 0.05
FLOORS = {"p99": 120.0, "p50": 20.0, "share_over_2ms": 0.002}
BACKGROUND_US = 5000.0   # a control-stream probe slower than this marks its 20 ms bin as background
BIN_S = 0.02


def load(run_dir):
    with open(os.path.join(run_dir, "experiment.json")) as f:
        exp = json.load(f)
    legs = [m for m in evidence.load_legs(run_dir) if m.get("leg_id")]
    return exp, legs


def invalid_legs(run_dir):
    """Every invalid leg the run recorded, superseded ones included, straight from legs.jsonl:
    [{leg_id, cell, round, attempt, superseded, reasons}]. A leg that failed because a worker
    stalled is re-run and leaves the result; it must stay visible beside it."""
    raw, sup = [], set()
    with open(os.path.join(run_dir, "legs.jsonl")) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            x = json.loads(line)
            if "supersede" in x:
                sup.update(x["supersede"])
            elif x.get("leg_id"):
                raw.append(x)
    out = []
    for m in raw:
        v = m.get("verdict") or {}
        if v.get("valid"):
            continue
        out.append({"leg_id": m["leg_id"], "cell": "%s/%s" % (m.get("shape"), m.get("arm")), "round": m.get("round"),
                    "attempt": m.get("attempt", 0), "superseded": m["leg_id"] in sup or bool(m.get("superseded")),
                    "reasons": v.get("reasons") or ["no verdict"]})
    return out, len(raw)


def leg_inputs(run_dir, m):
    probe = latency.load_probe(os.path.join(run_dir, "probe", m["leg_id"] + ".jsonl.gz"))
    ser = latency.load_series(os.path.join(run_dir, "main", m["leg_id"] + ".json.gz"))
    return probe, ser


def groups_of(probe, cpu0):
    conns = ((probe["meta"] or {}).get("meta") or {}).get("map", {}).get("connections") or []
    c0 = {c["conn"] for c in conns if str(c.get("cpus")) == str(cpu0)}
    return {"all": None, "cpu0": c0, "others": {c["conn"] for c in conns} - c0}


def background_bins(rows, span):
    out = set()
    for r in rows:
        if r[0] == "c" and r[5] is not None and span[0] <= r[3] / 1e9 <= span[1] \
                and (r[5] - r[3]) / 1e3 > BACKGROUND_US:
            out.add(int(r[3] / 1e9 / BIN_S))
    return out


def analyse(run_dir, m, cfg):
    """One leg: slices, contrasts, sham contrasts, the admin stream, the profile bins."""
    probe, ser = leg_inputs(run_dir, m)
    t0, t1 = ser["window_mono"]
    p = latency.params(cfg)
    span = latency.used_span(t0, t1, p)
    gaps = (probe.get("end") or {}).get("gaps") or []
    pts, cnt = latency.data_points(probe["rows"], span[0], span[1], gaps)
    groups = groups_of(probe, cfg["cpu0"])
    bursts = ser["bursts"]
    out = latency.analyse_leg(pts, groups, bursts, t0, t1, cfg, sham=True)
    out["counts"] = cnt
    # sensitivity (pre-declared, secondary): the 20 ms bins the control stream shows as slow, removed
    bg = background_bins(probe["rows"], span)
    kept = [x for x in pts if int(x[0] / BIN_S) not in bg]
    out["background_bins"] = len(bg)
    out["contrasts_no_background"] = latency.analyse_leg(kept, groups, bursts, t0, t1, cfg, sham=False)["contrasts"]
    whole = [tuple(w) for w in out["whole"]]
    allw = latency.all_windows(bursts)
    # L4: the admin stream by intended time
    apts, acnt = latency.data_points(probe["rows"], span[0], span[1], gaps, "a")
    ats, alat = [x[0] for x in apts], [x[1] for x in apts]
    r = latency.slice_ranges(ats, whole, allw, span, p)
    ain, aout = latency._take(alat, r["in"]), latency._take(alat, r["out"])
    ratios = []
    for s, e in whole:
        inside = [l for t, l in zip(ats, alat) if s - p["admin_widen_s"] <= t <= e]
        if inside and e > s:
            ratios.append(max(inside) / 1e6 / (e - s))
    out["admin"] = {"in": latency.stats_of(ain), "out": latency.stats_of(aout), "unanswered": acnt["unanswered"],
                    "longest_wait_over_flush": ratios}
    out["flush_wall_s"] = [e - s for s, e in whole]
    # the control stream (direct to the origin)
    cpts, _ = latency.data_points(probe["rows"], span[0], span[1], gaps, "c")
    out["control"] = latency.stats_of([x[1] for x in cpts])
    # profile: latency by intended time since the flush start, 10 ms bins from -20 to +100 ms
    prof = {}
    starts = [s for s, _ in whole]
    for ts, lat, _ in pts:
        for s in starts:
            d = ts - s
            if -0.02 <= d < 0.1:
                prof.setdefault(int(math.floor(d / 0.01)), []).append(lat)
    out["profile"] = prof
    ts, lat = [x[0] for x in pts], [x[1] for x in pts]
    r = latency.slice_ranges(ts, whole, allw, span, p)
    out["all_out"], out["all_in"] = latency._take(lat, r["out"]), latency._take(lat, r["in"])
    return out


def t_row(vals):
    """Mean, 95% t interval and two-sided p of the mean against zero."""
    v = [x for x in vals if x is not None]
    n = len(v)
    if n < 2 or n != len(vals):
        return {"n": n, "mean": sum(v) / n if n else None}
    mu = sum(v) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1))
    se = sd / math.sqrt(n)
    tq = stats.t_ppf(1 - ALPHA / 2, n - 1)
    out = {"n": n, "mean": mu, "sd": sd, "lo": mu - tq * se, "hi": mu + tq * se}
    if se > 0:
        out["t_p"] = 2 * (1 - stats.t_cdf(abs(mu / se), n - 1))
    else:
        out["t_p"] = 0.0 if mu else 1.0
    return out


def reach_of(per_round_sham):
    """per_round_sham: [ {shift: value} per round ]. The largest absolute mean over the shifts
    present (with a value) in every round; None with fewer than 2 such shifts."""
    if not per_round_sham:
        return None, 0
    common = set(per_round_sham[0])
    for d in per_round_sham[1:]:
        common &= set(d)
    common = [s for s in common if all(d[s] is not None for d in per_round_sham)]
    if len(common) < 2:
        return None, len(common)
    return max(abs(sum(d[s] for d in per_round_sham) / len(per_round_sham)) for s in common), len(common)


def build(run_dir):
    exp, legs = load(run_dir)
    cfg = dict(exp["measure"]["latency"], interval_s=(exp.get("lat") or {}).get("interval_s", 10))
    cells = [(sh["name"], a["name"]) for sh, a in experiment.cells(exp)]
    valid = {}
    for m in legs:
        if (m.get("verdict") or {}).get("valid") and not m.get("superseded"):
            valid[(m["round"], m["shape"], m["arm"])] = m
    rounds = sorted({r for r, _, _ in valid if all((r, s, a) in valid for s, a in cells)})
    inv, n_raw = invalid_legs(run_dir)
    res = {"run_dir": run_dir, "cells": ["%s/%s" % c for c in cells], "rounds": rounds,
           "invalid_legs": inv, "legs_run": n_raw,
           "legs_recorded": len(legs), "legs_invalid": sum(1 for m in legs if not (m.get("verdict") or {}).get("valid")),
           "complete": len(rounds) >= MIN_ROUNDS, "floors": FLOORS, "rows": [], "cells_detail": {}}
    an = {}
    for r in rounds:
        for s, a in cells:
            an[(r, s, a)] = analyse(run_dir, valid[(r, s, a)], cfg)
    own = [a for s, a in cells if s == "own"]
    shared = [a for s, a in cells if s == "shared"]

    def row(label, metric, per_round, sham_per_round, primary, cell=None, out_per_round=None):
        tr = t_row(per_round)
        rc, nshift = reach_of(sham_per_round)
        outv = [x for x in (out_per_round or []) if x]
        d = dict(tr, label=label, metric=metric, primary=primary, reach=rc, sham_shifts=nshift, cell=cell,
                 floor=FLOORS[metric], per_round=per_round,
                 pct_of_out=(100.0 * tr["mean"] / (sum(outv) / len(outv))) if outv and tr.get("mean") is not None
                 and metric != "share_over_2ms" else None)
        res["rows"].append(d)
        return d

    for metric in latency.METRICS:
        prim = metric == "p99"
        for a in own:
            row("L1 own/%s" % a, metric, [an[(r, "own", a)]["contrasts"]["L1_" + metric] for r in rounds],
                [{k: v["L1_" + metric] for k, v in an[(r, "own", a)]["sham"].items()} for r in rounds], prim,
                "own/" + a, [an[(r, "own", a)]["contrasts"]["out_" + metric] for r in rounds])
        if own:
            def pool(r, key, sham=None):
                vs = [(an[(r, "own", a)]["sham"].get(sham, {}) if sham else an[(r, "own", a)]["contrasts"]).get(key)
                      for a in own]
                return None if any(v is None for v in vs) else sum(vs) / len(vs)
            shifts = [set(an[(r, "own", a)]["sham"]) for r in rounds for a in own]
            common = set.intersection(*shifts) if shifts else set()
            row("L2 own, arms pooled", metric, [pool(r, "L2_" + metric) for r in rounds],
                [{k: pool(r, "L2_" + metric, k) for k in common} for r in rounds], prim, "own/*",
                [pool(r, "out_" + metric) for r in rounds])
        for a in shared:
            row("L3 shared/%s" % a, metric, [an[(r, "shared", a)]["contrasts"]["L3_" + metric] for r in rounds],
                [{k: v["L3_" + metric] for k, v in an[(r, "shared", a)]["sham"].items()} for r in rounds], prim,
                "shared/" + a, [an[(r, "shared", a)]["contrasts"]["out_" + metric] for r in rounds])
        # descriptive rows: the placebo (L3 on the own-core legs) and L1 on the shared-core legs
        for a in own:
            row("placebo: L3 own/%s" % a, metric, [an[(r, "own", a)]["contrasts"]["L3_" + metric] for r in rounds],
                [{k: v["L3_" + metric] for k, v in an[(r, "own", a)]["sham"].items()} for r in rounds], False,
                "own/" + a)["descriptive"] = True
        for a in shared:
            row("descriptive: L1 shared/%s" % a, metric,
                [an[(r, "shared", a)]["contrasts"]["L1_" + metric] for r in rounds],
                [{k: v["L1_" + metric] for k, v in an[(r, "shared", a)]["sham"].items()} for r in rounds], False,
                "shared/" + a)["descriptive"] = True
        for a in own:
            row("sensitivity: L1 own/%s, background bins removed" % a, metric,
                [an[(r, "own", a)]["contrasts_no_background"]["L1_" + metric] for r in rounds], [], False,
                "own/" + a)["descriptive"] = True
    prim = [d for d in res["rows"] if d["primary"] and d.get("t_p") is not None]
    for d, hp in zip(prim, stats.holm([d["t_p"] for d in prim])):
        d["holm_p"] = hp
    res["holm_family"] = len([d for d in res["rows"] if d["primary"]])
    for d in res["rows"]:
        d["status"] = status(d, res["complete"])
    for s, a in cells:
        res["cells_detail"]["%s/%s" % (s, a)] = cell_detail([an[(r, s, a)] for r in rounds],
                                                            [valid[(r, s, a)] for r in rounds])
    return res


def status(d, complete):
    if not complete:
        return "incomplete, no verdict"
    if d.get("descriptive"):
        return "descriptive"
    if d.get("lo") is None:
        return "no interval, no verdict"
    if d["reach"] is None:
        return "no reach, no verdict"
    bound = max(d["reach"], d["floor"])
    excl = d["lo"] > 0 or d["hi"] < 0
    if d["primary"]:
        excl = excl and d.get("holm_p") is not None and d["holm_p"] <= ALPHA
    if excl and abs(d["mean"]) > bound:
        return "finding" if d["primary"] else "secondary: differs"
    return "not shown (bound %s)" % fmt(bound, d["metric"])


def cell_detail(ans, legs):
    """Descriptive figures of one cell, its legs pooled or listed."""
    def tot(key, sl):
        return sum((x["slices"]["all"][sl] or {}).get(key, 0) for x in ans)
    all_in = sorted(v for x in ans for v in x["all_in"])
    all_out = sorted(v for x in ans for v in x["all_out"])
    prof = {}
    for x in ans:
        for b, v in x["profile"].items():
            prof.setdefault(b, []).extend(v)
    walls = [w for x in ans for w in x["flush_wall_s"]]
    ratios = [w for x in ans for w in x["admin"]["longest_wait_over_flush"]]
    ain = sorted(v for x in ans for v in [x["admin"]["in"].get("p50")] if v is not None)
    wd = {}
    for m in legs:
        for k, v in (m.get("watchdog_delta") or {}).items():
            if v:
                wd[k] = wd.get(k, 0) + v

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None
    return {
        "legs": len(ans), "flushes": len(walls),
        "flush_wall_s_mean": mean(walls), "flush_wall_s_max": max(walls) if walls else None,
        "in_n": len(all_in), "out_n": len(all_out),
        "in_over_20ms": tot("over_20ms", "in"), "out_over_20ms": tot("over_20ms", "out"),
        "in_over_100ms": tot("over_100ms", "in"), "out_over_100ms": tot("over_100ms", "out"),
        "in_max_us": all_in[-1] if all_in else None, "out_max_us": all_out[-1] if all_out else None,
        "in_p999_us": latency.pct(all_in, 0.999), "out_p999_us": latency.pct(all_out, 0.999),
        "in_p50_us": latency.pct(all_in, 0.5), "out_p50_us": latency.pct(all_out, 0.5),
        "in_p99_us": latency.pct(all_in, 0.99), "out_p99_us": latency.pct(all_out, 0.99),
        "admin_in_p50_us": mean(ain), "admin_in_max_us": max([x["admin"]["in"].get("max") or 0 for x in ans] or [0]),
        "admin_out_p50_us": mean([x["admin"]["out"].get("p50") for x in ans]),
        "admin_out_max_us": max([x["admin"]["out"].get("max") or 0 for x in ans] or [0]),
        "admin_unanswered": sum(x["admin"]["unanswered"] for x in ans),
        "admin_longest_wait_over_flush_mean": mean(ratios),
        "admin_longest_wait_over_flush_max": max(ratios) if ratios else None,
        "control_p50_us": mean([x["control"].get("p50") for x in ans]),
        "control_p99_us": mean([x["control"].get("p99") for x in ans]),
        "control_max_us": max([x["control"].get("max") or 0 for x in ans] or [0]),
        "background_bins": sum(x["background_bins"] for x in ans),
        "dropped_for_gap": sum(x["counts"]["dropped_for_gap"] for x in ans),
        "watchdog_delta": wd,
        "worker_busy_mean": mean([(m.get("lat") or {}).get("worker_busy_mean") for m in legs]),
        "manipulation_in_over_out": [((m.get("lat") or {}).get("manipulation") or {}).get("in_over_out") for m in legs],
        "manipulation_in_over_others": [((m.get("lat") or {}).get("manipulation") or {}).get("in_over_others")
                                        for m in legs],
        "nighthawk_p50_us": mean([(m.get("latency_us") or {}).get("p50") for m in legs]),
        "nighthawk_p99_us": mean([(m.get("latency_us") or {}).get("p99") for m in legs]),
        "nighthawk_pending_total": [m.get("client_pending_total") for m in legs],
        "nighthawk_overflow": [sum((m.get("client_overflow") or {}).values()) for m in legs],
        "nighthawk_queue_to_connect_max_us": [m.get("client_queue_to_connect_max_us") for m in legs],
        "cycles_per_request": mean([(m.get("per_req") or {}).get("cycles_total") for m in legs]),
        "profile": {str(b): {"n": len(v), "p50_us": latency.pct(sorted(v), 0.5), "p99_us": latency.pct(sorted(v), 0.99)}
                    for b, v in sorted(prof.items())},
    }


def fmt(v, metric=None):
    if v is None:
        return "-"
    if metric == "share_over_2ms":
        return "%.3f pt" % (100.0 * v)
    return "%.0f us" % v


def markdown(res):
    o = []
    o.append("# Run L: request latency in and out of a stats flush\n")
    o.append("Run %s. Cells %s. Complete rounds %d (%s), legs recorded %d, invalid %d.%s\n" % (
        res["run_dir"], ", ".join(res["cells"]), len(res["rounds"]), res["rounds"], res["legs_recorded"],
        res["legs_invalid"], "" if res["complete"] else " **Incomplete (under %d complete rounds): no verdict.**"
        % MIN_ROUNDS))
    for metric, title in (("p99", "p99 (primary; Holm over %d rows)" % res["holm_family"]),
                          ("p50", "p50 (secondary)"), ("share_over_2ms", "share over 2 ms (secondary)")):
        o.append("\n## %s\n" % title)
        o.append("| Row | Rounds | Mean | 95% interval | % of OUT | p | Holm p | Reach (shifts) | Floor | Status |")
        o.append("|---|---|---|---|---|---|---|---|---|---|")
        for d in res["rows"]:
            if d["metric"] != metric:
                continue
            o.append("| %s | %d | %s | %s | %s | %s | %s | %s (%d) | %s | %s |" % (
                d["label"], d["n"], fmt(d.get("mean"), metric),
                "[%s, %s]" % (fmt(d["lo"], metric), fmt(d["hi"], metric)) if d.get("lo") is not None else "-",
                "%.1f%%" % d["pct_of_out"] if d.get("pct_of_out") is not None else "-",
                "%.3f" % d["t_p"] if d.get("t_p") is not None else "-",
                "%.3f" % d["holm_p"] if d.get("holm_p") is not None else "-",
                fmt(d["reach"], metric), d["sham_shifts"], fmt(d["floor"], metric), d["status"]))
    o.append("\n## Invalid legs (every one the run recorded, re-run ones included)\n")
    o.append("A gate that the effect under study can trip (a stalled worker: client rate, probe drain, flush count) "
             "removes the leg and its round is run again; those legs are listed here, not hidden. Legs run: %d, "
             "invalid: %d.\n" % (res["legs_run"], len(res["invalid_legs"])))
    o.append("| Cell | Invalid legs | Leg | Re-run later | Reasons |")
    o.append("|---|---|---|---|---|")
    for c in res["cells"]:
        mine = [x for x in res["invalid_legs"] if x["cell"] == c]
        if not mine:
            o.append("| %s | 0 | - | - | - |" % c)
        for x in mine:
            o.append("| %s | %d | %s | %s | %s |" % (c, len(mine), x["leg_id"], "yes" if x["superseded"] else "no",
                                                    "; ".join(x["reasons"]).replace("|", "/")))
    o.append("\n## Per cell (descriptive; pooled over the complete rounds)\n")
    keys = [("flushes", "whole flushes"), ("flush_wall_s_mean", "flush wall s, mean"), ("flush_wall_s_max", "flush wall s, max"),
            ("in_n", "probes IN"), ("out_n", "probes OUT"), ("in_p50_us", "IN p50 us"), ("out_p50_us", "OUT p50 us"),
            ("in_p99_us", "IN p99 us"), ("out_p99_us", "OUT p99 us"),
            ("in_p999_us", "IN p99.9 us (no verdict)"), ("out_p999_us", "OUT p99.9 us (no verdict)"),
            ("in_max_us", "IN max us"), ("out_max_us", "OUT max us"),
            ("in_over_20ms", "IN over 20 ms"), ("out_over_20ms", "OUT over 20 ms"),
            ("in_over_100ms", "IN over 100 ms"), ("out_over_100ms", "OUT over 100 ms"),
            ("admin_in_p50_us", "admin /ready IN p50 us"), ("admin_in_max_us", "admin IN max us"),
            ("admin_out_p50_us", "admin OUT p50 us"), ("admin_out_max_us", "admin OUT max us"),
            ("admin_unanswered", "admin unanswered"),
            ("admin_longest_wait_over_flush_mean", "longest admin wait / flush wall, mean"),
            ("admin_longest_wait_over_flush_max", "longest admin wait / flush wall, max"),
            ("control_p50_us", "control (origin direct) p50 us"), ("control_p99_us", "control p99 us"),
            ("control_max_us", "control max us"), ("background_bins", "20 ms bins with a slow control probe"),
            ("dropped_for_gap", "probes dropped for a loop gap"), ("worker_busy_mean", "worker busy share"),
            ("manipulation_in_over_out", "worker on shared CPU: wait in / out, per leg"),
            ("manipulation_in_over_others", "same: against the other workers in flush"),
            ("nighthawk_p50_us", "Nighthawk p50 us (background load)"), ("nighthawk_p99_us", "Nighthawk p99 us"),
            ("nighthawk_pending_total", "Nighthawk pending total, per leg"),
            ("nighthawk_overflow", "Nighthawk overflow counters, per leg"),
            ("nighthawk_queue_to_connect_max_us", "Nighthawk queue_to_connect max us, per leg"),
            ("cycles_per_request", "cycles per request (context only)"), ("watchdog_delta", "watchdog counters, change")]
    cells = list(res["cells_detail"])
    o.append("| | " + " | ".join(cells) + " |")
    o.append("|---|" + "---|" * len(cells))
    for k, label in keys:
        def cell(v):
            if isinstance(v, float):
                return "%.4g" % v
            if isinstance(v, dict):
                return ", ".join("%s %s" % kv for kv in sorted(v.items())) or "none"
            return "-" if v is None else str(v)
        o.append("| %s | %s |" % (label, " | ".join(cell(res["cells_detail"][c].get(k)) for c in cells)))
    o.append("\n## Probe latency by intended time since the flush start (10 ms bins; n / p50 us / p99 us)\n")
    o.append("| Bin start ms | " + " | ".join(cells) + " |")
    o.append("|---|" + "---|" * len(cells))
    for b in range(-2, 10):
        row = []
        for c in cells:
            pb = res["cells_detail"][c]["profile"].get(str(b))
            row.append("%d / %.0f / %.0f" % (pb["n"], pb["p50_us"], pb["p99_us"]) if pb else "-")
        o.append("| %d | %s |" % (b * 10, " | ".join(row)))
    return "\n".join(o) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--json")
    ap.add_argument("--min-rounds", type=int, help="for a smoke: 1 (numbers only, never a verdict below %d)" % MIN_ROUNDS)
    a = ap.parse_args(argv)
    res = build(os.path.expanduser(a.run_dir))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(res, f, indent=1, sort_keys=True)
    sys.stdout.write(markdown(res))
    if a.min_rounds is not None and len(res["rounds"]) < a.min_rounds:
        sys.stderr.write("only %d complete rounds, wanted %d\n" % (len(res["rounds"]), a.min_rounds))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
