"""Stage 2: data set, count-gate diagnosis, L1 to L4, sham A/A, Holm, evidence, anomalies.

Reads perleg.json (perleg.py). Prints text; also writes results.json.
"""
import json
import math
import os
import sys

import numpy as np

import lib
from lib import CELLS, cell_name, tci, holm, fmt, fnum

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(lib.OUT, "perleg.json")))
LEGS = {l["leg_id"]: l for l in P["legs"]}
RES = {}


def nanmean(v):
    v = [x for x in v if x is not None and not math.isnan(x)]
    return sum(v) / len(v) if v else math.nan


# ------------------------------------------------------------------ 1. data set

def datasets():
    """Applies the plan's rule in file order: a re-run replaces the whole round."""
    current = {}   # round -> {cell: leg}
    first = {}
    order = {}     # round -> list of cells in run order (first pass)
    superseded = set()
    for ln in P["lines"]:
        if "supersede" in ln:
            for lid in ln["supersede"]:
                superseded.add(lid)
                r = LEGS[lid]["round"]
            current[r] = {}
            continue
        l = LEGS[ln["leg"]]
        c = (l["shape"], l["arm"])
        current.setdefault(l["round"], {})[c] = l
        if l["attempt"] == 0:
            first.setdefault(l["round"], {})[c] = l
            order.setdefault(l["round"], []).append(c)
    complete = {r: m for r, m in current.items() if all(c in m and m[c]["valid"] for c in CELLS)}
    return current, first, order, complete, superseded


CUR, FIRST, ORDER, COMPLETE, SUPERSEDED = datasets()
PRIMARY = dict(COMPLETE)
SENS = dict(COMPLETE)
SENS[4] = FIRST[4]            # first-pass round 4, with its invalid shared/statsd leg: sensitivity only
FIRSTPASS = dict(FIRST)       # all five first-pass rounds as run (three invalid legs): sensitivity only
SETS = [("PRIMARY (plan rule: complete rounds %s)" % sorted(PRIMARY), PRIMARY),
        ("SENSITIVITY A (PRIMARY + first-pass round 4, incl. its INVALID shared/statsd leg)", SENS),
        ("SENSITIVITY B (the five first-pass rounds as run, incl. 3 INVALID shared/statsd legs)", FIRSTPASS)]


def section(t):
    print()
    print("=" * 110)
    print(t)
    print("=" * 110)


def s1():
    section("1. LEGS AS RUN, AND THE VALID DATA SET")
    print("legs.jsonl in file order (S = supersede marker written before a re-run round):")
    pos = 0
    for ln in P["lines"]:
        if "supersede" in ln:
            print("  line %2d  S  supersedes %s" % (ln["line"], ", ".join(ln["supersede"])))
            continue
        l = LEGS[ln["leg"]]
        print("  line %2d  %-24s round %d attempt %d %-13s %s  %s  evidence items %d, failed %d%s" % (
            ln["line"], l["leg_id"], l["round"], l["attempt"], cell_name((l["shape"], l["arm"])), l["started_utc"],
            "VALID  " if l["valid"] else "INVALID", l["evidence_items"], l["evidence_items_failed"],
            ("  <- " + "; ".join(l["evidence_failed"])[:60]) if not l["valid"] else ""))
    n = len(P["legs"])
    print("legs run: %d; valid by the harness's gates: %d; invalid: %d" % (n, sum(l["valid"] for l in P["legs"]), sum(not l["valid"] for l in P["legs"])))
    print()
    print("Round by round after the plan's rule (an invalid leg -> the whole round is replaced by its re-run):")
    for r in sorted(CUR):
        m = CUR[r]
        have = [cell_name(c) for c in CELLS if c in m]
        st = "COMPLETE" if r in COMPLETE else "INCOMPLETE"
        src = "re-run" if any(l["attempt"] for l in m.values()) else "first pass"
        print("  round %d: %-10s source %-10s legs %d/5 (%s)%s" % (
            r, st, src, len(have), ", ".join(m[c]["leg_id"] for c in CELLS if c in m),
            "" if r in COMPLETE else "; first pass had an invalid leg and was superseded, the re-run was cut after %d leg(s)" % len(have)))
    print("complete rounds: %d %s  (plan: under 4 complete rounds = incomplete, no verdict; design 5)" % (len(COMPLETE), sorted(COMPLETE)))
    print()
    print("Position of each cell in its round (1..5), first-pass order = re-run order:")
    print("  %-14s %s | positions held in the %d complete rounds" % ("cell", " ".join("r%d" % r for r in sorted(ORDER)), len(COMPLETE)))
    for c in CELLS:
        ps = {r: ORDER[r].index(c) + 1 for r in sorted(ORDER)}
        held = sorted(ps[r] for r in COMPLETE)
        print("  %-14s %s  | %s, missing %s" % (cell_name(c), "  ".join(str(ps[r]) for r in sorted(ps)), held, sorted(set(range(1, 6)) - set(held))))
    print("Wall time of the legs in the primary set (UTC):")
    for r in sorted(PRIMARY):
        ts = sorted(l["started_utc"][11:19] for l in PRIMARY[r].values())
        print("  round %d: %s to %s" % (r, ts[0], ts[-1]))
    from scipy import stats as sst
    t3, t4 = sst.t.ppf(0.975, 3), sst.t.ppf(0.975, 4)
    print("t(0.975): df 3 = %.3f, df 4 = %.3f; half-width for the same SD: n=4 %.3f SD, n=5 %.3f SD (+%.0f%%)" % (
        t3, t4, t3 / 2, t4 / math.sqrt(5), 100 * ((t3 / 2) / (t4 / math.sqrt(5)) - 1)))
    RES["complete_rounds"] = sorted(COMPLETE)
    nf = {cell_name(c): sum(len(PRIMARY[r][c]["whole"]) for r in PRIMARY) for c in CELLS}
    print("whole flushes per cell in the primary set:", nf)
    RES["flushes_per_cell"] = nf


# ------------------------------------------------------------------ 2. count gate

def s2():
    section("2. THE EXACT REQUEST-COUNT GATE (listener 2xx - Nighthawk 2xx - probe answered - map requests)")
    print("%-24s %-7s %9s %9s %7s %6s | %9s %8s %-22s | NH end: s after t1, s into flush (grid / marks), flush wall s | cpu0 share>3.64ms in/out, others in" % (
        "leg", "valid", "listener", "NH 2xx", "probe", "map", "error", "NH sent-2xx", "NH workers short"))
    rows = []
    for l in P["legs"]:
        c = l["count"]
        pm = c.get("nh_end_phase_from_marks_s")
        inflush = c["nh_end_phase_s"] <= c["flush_wall_max_s"]
        rows.append((l, inflush))
        print("%-24s %-7s %9d %9d %7d %6d | %9d %8d %-22s | %6.2f  %5.2f / %-5s  %4.2f-%4.2f %-3s | %.4f / %.5f, %.5f" % (
            l["leg_id"], "valid" if l["valid"] else "INVALID", c["listener_2xx"], c["nighthawk_2xx"], c["probe_answered"], c["map_requests"],
            c["recomputed_error"], c["nh_requests"] - c["nh_2xx"], ",".join("%s:%d" % (s["worker"], s["missing"]) for s in c["nh_workers_short"]) or "-",
            c["nh_end_rel_t1"], c["nh_end_phase_s"], ("%.2f" % pm) if pm is not None else "-", c["flush_wall_mean_s"], c["flush_wall_max_s"],
            "IN" if inflush else "out", c["cpu0_in_share_over_3p6ms"], c["cpu0_out_share_over_3p6ms"], c["others_in_share_over_3p6ms"]))
    ok = all(l["count"]["recomputed_error"] == l["count"]["error"] for l in P["legs"])
    print("recomputed error equals the record's on every leg:", ok)
    print("error == Nighthawk (requests sent - 2xx counted) on every leg:", all(l["count"]["recomputed_error"] == l["count"]["nh_requests"] - l["count"]["nh_2xx"] for l in P["legs"]))
    print("Envoy listener: connections destroyed with an active request / rx reset / tx reset, summed over the invalid legs:",
          [(l["leg_id"], l["count"]["downstream_cx_destroy_active_rq"], l["count"]["downstream_rq_rx_reset"], l["count"]["downstream_rq_tx_reset"]) for l in P["legs"] if not l["valid"]])
    print()
    for c in CELLS:
        ls = [l for l in P["legs"] if (l["shape"], l["arm"]) == c]
        nin = sum(1 for l in ls if l["count"]["nh_end_phase_s"] <= l["count"]["flush_wall_max_s"])
        nerr = sum(1 for l in ls if l["count"]["recomputed_error"])
        tot = sum(l["count"]["recomputed_error"] for l in ls)
        ph = [l["count"]["nh_end_phase_s"] for l in ls]
        p = nanmean([l["count"]["cpu0_in_share_over_3p6ms"] for l in ls])
        print("  %-14s legs %d; Nighthawk ended inside a flush in %d; phase %.2f to %.2f s after a flush start; legs with a count error %d (responses %d); "
              "expected lost per leg if the end is in a flush = 16 workers x 1/4 x P(cpu0 in-flush latency > 1/275 s = %.4f) = %.2f" % (
                  cell_name(c), len(ls), nin, min(ph), max(ph), nerr, tot, p, 16 * 0.25 * p))
    ls = [l for l in P["legs"] if (l["shape"], l["arm"]) == ("shared", "statsd")]
    lam = nanmean([16 * 0.25 * l["count"]["cpu0_in_share_over_3p6ms"] for l in ls])
    print("  shared/statsd: expected lost responses per leg %.2f -> P(at least one) = %.2f; observed %d of %d legs (%.2f), %d responses (%.2f per leg)" % (
        lam, 1 - math.exp(-lam), sum(1 for l in ls if l["count"]["recomputed_error"]), len(ls),
        sum(1 for l in ls if l["count"]["recomputed_error"]) / len(ls), sum(l["count"]["recomputed_error"] for l in ls),
        sum(l["count"]["recomputed_error"] for l in ls) / len(ls)))
    print()
    print("Latency contrasts of the invalid legs beside the valid legs of the same cell (us):")
    for l in ls:
        k = l["contrasts"]
        print("  %-24s %-7s L1 p99 %+7.0f  L2 p99 %+7.0f  L3 p99 %+7.0f  out p99 %6.0f  in p99 cpu0 %6.0f  worst in-flush cpu0 %.1f ms  flush wall %.2f s" % (
            l["leg_id"], "valid" if l["valid"] else "INVALID", k["L1_p99"], k["L2_p99"], k["L3_p99"], k["out_p99"],
            l["slices"]["cpu0"]["in"]["p99"], l["worst"]["cpu0_in"], l["count"]["flush_wall_mean_s"]))
    v = [l["contrasts"]["L3_p99"] for l in ls if l["valid"]]
    iv = [l["contrasts"]["L3_p99"] for l in ls if not l["valid"]]
    print("  L3 p99: valid legs mean %.0f (min %.0f, max %.0f, n %d); invalid legs mean %.0f (min %.0f, max %.0f, n %d)" % (
        np.mean(v), min(v), max(v), len(v), np.mean(iv), min(iv), max(iv), len(iv)))
    v = [l["contrasts"]["L1_p99"] for l in ls if l["valid"]]
    iv = [l["contrasts"]["L1_p99"] for l in ls if not l["valid"]]
    print("  L1 p99: valid legs mean %.0f (min %.0f, max %.0f); invalid legs mean %.0f (min %.0f, max %.0f)" % (
        np.mean(v), min(v), max(v), np.mean(iv), min(iv), max(iv)))


# ------------------------------------------------------------------ 3. rows

def row(ds, cells, key, pooled=False):
    """Per-round values of a contrast. pooled: mean over the cells per round first."""
    rounds = sorted(ds)
    vals, outs, legs = [], [], []
    for r in rounds:
        ls = [ds[r][c] for c in cells if c in ds[r]]
        if len(ls) != len(cells):
            continue
        vals.append(float(np.mean([l["contrasts"][key] for l in ls])))
        m = key.split("_", 1)[1]
        outs.append(float(np.mean([l["contrasts"][("out0_" if key.startswith("L3") else "out_") + m] for l in ls])))
        legs.append(ls)
    st = tci(vals)
    st["values"] = vals
    st["out"] = float(np.mean(outs))
    st["pct"] = 100.0 * st["mean"] / st["out"] if st["out"] else math.nan
    # sham: shifts admissible in every leg of the row
    flat = [l for ls in legs for l in ls]
    shifts = set(flat[0]["sham"]) if flat else set()
    for l in flat[1:]:
        shifts &= set(l["sham"])
    sm = {}
    for s in sorted(shifts, key=float):
        sm[s] = float(np.mean([np.mean([l["sham"][s][key] for l in ls]) for ls in legs]))
    st["sham_means"] = sm
    st["shifts"] = len(sm)
    st["reach"] = max(abs(v) for v in sm.values()) if len(sm) >= 2 else math.nan
    st["sham_mean"] = float(np.mean(list(sm.values()))) if sm else math.nan
    st["sham_sd"] = float(np.std(list(sm.values()), ddof=1)) if len(sm) > 1 else math.nan
    st["legs"] = legs
    return st


ROWS = [("L1 own/nosink", [("own", "nosink")], "L1", True),
        ("L1 own/statsd", [("own", "statsd")], "L1", True),
        ("L1 own/otlp", [("own", "otlp")], "L1", True),
        ("L2 own, 3 arms pooled", [("own", "nosink"), ("own", "statsd"), ("own", "otlp")], "L2", True),
        ("L3 shared/nosink", [("shared", "nosink")], "L3", True),
        ("L3 shared/statsd", [("shared", "statsd")], "L3", True),
        ("L1 shared/nosink", [("shared", "nosink")], "L1", False),
        ("L1 shared/statsd", [("shared", "statsd")], "L1", False),
        ("L2 own/nosink", [("own", "nosink")], "L2", False),
        ("L2 own/statsd", [("own", "statsd")], "L2", False),
        ("L2 own/otlp", [("own", "otlp")], "L2", False),
        ("L2 shared/nosink", [("shared", "nosink")], "L2", False),
        ("L2 shared/statsd", [("shared", "statsd")], "L2", False),
        ("L3 own/nosink (placebo)", [("own", "nosink")], "L3", False),
        ("L3 own/statsd (placebo)", [("own", "statsd")], "L3", False),
        ("L3 own/otlp (placebo)", [("own", "otlp")], "L3", False)]


def verdict(st, metric, hp=None):
    floor = lib.FLOORS[metric]
    if st["n"] < 4:
        return "no verdict (n<4)"
    if math.isnan(st["reach"]):
        return "no reach, no verdict"
    excl = st["lo"] > 0 or st["hi"] < 0
    big = abs(st["mean"]) > max(st["reach"], floor)
    if excl and big and (hp is None or hp <= 0.05):
        return "FINDING"
    if excl and big:
        return "not shown (Holm p %.3f)" % hp
    if not big:
        return "not shown (inside reach/floor %.0f)" % max(st["reach"], floor) if metric != "share2" else "not shown (inside reach/floor %.2f)" % max(st["reach"], floor)
    return "not shown (interval includes 0)"


def s3():
    section("3. L1 TO L3: per-round contrasts, 95% t interval, sham-window A/A reach, Holm over the six primary p99 rows")
    for name, ds in SETS:
        print()
        print("--- %s; n = %d rounds" % (name, len(ds)))
        allres = {}
        prim = []
        for metric, unit in (("p99", "us"), ("p50", "us"), ("share2", "points")):
            print("  metric %s (%s); floor %s" % (metric, unit, lib.FLOORS[metric]))
            print("  %-26s %2s %10s %22s %8s %7s %9s | %6s %9s %9s %9s | %-9s %s" % (
                "row", "n", "mean", "95% CI", "% of OUT", "SD", "t-test p", "shifts", "sham mean", "sham SD", "reach", "Holm p", "verdict"))
            sts = []
            for rname, cells, L, primary in ROWS:
                st = row(ds, cells, "%s_%s" % (L, metric), pooled=len(cells) > 1)
                sts.append((rname, primary, st))
            hp = {}
            if metric == "p99":
                pr = [(rn, st) for rn, p, st in sts if p]
                adj = holm([st["p"] if not math.isnan(st["p"]) else 1.0 for _, st in pr])
                hp = {rn: a for (rn, _), a in zip(pr, adj)}
            for rname, primary, st in sts:
                d = 0 if metric != "share2" else 3
                h = hp.get(rname)
                v = verdict(st, metric, h) if (primary and metric == "p99") else verdict(st, metric) + " [secondary]"
                print("  %-26s %2d %10s %22s %8s %7s %9s | %6d %9s %9s %9s | %-9s %s" % (
                    rname, st["n"], fmt(st["mean"], d), "[%s, %s]" % (fmt(st["lo"], d), fmt(st["hi"], d)),
                    fmt(st["pct"], 1) if metric != "share2" else "-", fnum(st["sd"], d), "%.2g" % st["p"],
                    st["shifts"], fmt(st["sham_mean"], d), fnum(st["sham_sd"], d), fnum(st["reach"], d),
                    ("%.3g" % h) if h is not None else "-", v))
                allres["%s|%s" % (rname, metric)] = {k: st[k] for k in ("n", "mean", "lo", "hi", "pct", "sd", "p", "shifts", "reach", "sham_mean", "sham_sd", "values", "out")}
                allres["%s|%s" % (rname, metric)]["holm"] = h
                allres["%s|%s" % (rname, metric)]["verdict"] = v
        RES["rows:" + name.split(" (")[0]] = allres
    print()
    print("Per-round values of the six primary rows (us, p99), every leg run, for reading the spread:")
    for rname, cells, L, primary in ROWS:
        if not primary:
            continue
        vals = []
        for l in P["legs"]:
            if (l["shape"], l["arm"]) in cells:
                vals.append("%s%s=%+.0f" % (l["leg_id"].split("-")[0] + (".rr1" if l["attempt"] else ""), "" if l["valid"] else "(INVALID)", l["contrasts"]["%s_p99" % L]))
        print("  %-24s %s" % (rname, "  ".join(vals)))
    print()
    print("Sham means per shift, primary set, p99 (us):")
    for rname, cells, L, primary in ROWS[:6]:
        st = row(PRIMARY, cells, "%s_p99" % L)
        print("  %-24s %s" % (rname, "  ".join("%s:%+.0f" % (s, v) for s, v in st["sham_means"].items())))


# ------------------------------------------------------------------ per cell descriptives

def s4():
    section("4. PER CELL (primary set): flush length, probe latency by slice, worst cases, Nighthawk as background")
    print("Flush wall time (main-thread burst, 5 ms sampler) and main-thread run time per flush:")
    out = {}
    for c in CELLS:
        ls = [PRIMARY[r][c] for r in sorted(PRIMARY)]
        wall = [1e3 * (b["end"] - b["start"]) for l in ls for b in l["whole"]]
        run = [1e3 * b["run_s"] for l in ls for b in l["whole"]]
        allwall = [1e3 * (b["end"] - b["start"]) for l in P["legs"] if (l["shape"], l["arm"]) == c for b in l["whole"]]
        print("  %-14s flushes %2d  wall ms: min %6.0f p50 %6.0f mean %6.0f max %6.0f | run ms: p50 %6.0f mean %6.0f max %6.0f | run/wall %.2f | all %d legs run: %d flushes, wall p50 %.0f max %.0f" % (
            cell_name(c), len(wall), min(wall), np.median(wall), np.mean(wall), max(wall), np.median(run), np.mean(run), max(run), np.sum(run) / np.sum(wall),
            sum(1 for l in P["legs"] if (l["shape"], l["arm"]) == c), len(allwall), np.median(allwall), max(allwall)))
        out[cell_name(c)] = {"n": len(wall), "wall_p50": float(np.median(wall)), "wall_mean": float(np.mean(wall)), "wall_min": float(min(wall)), "wall_max": float(max(wall)),
                             "run_p50": float(np.median(run)), "run_mean": float(np.mean(run)), "run_max": float(max(run))}
    RES["flush"] = out
    print()
    print("Probe latency (done - intended), mean over the legs of per-leg figures; counts and max over all legs of the cell:")
    print("  %-14s %-7s %-6s %8s %7s %7s %7s %9s %8s %6s %6s" % ("cell", "group", "slice", "n total", "p50 us", "p90 us", "p99 us", "share>2ms%", "max ms", ">20ms", ">100ms"))
    sl = {}
    for c in CELLS:
        ls = [PRIMARY[r][c] for r in sorted(PRIMARY)]
        for g in ("all", "cpu0", "others"):
            for s in ("in", "onset", "post", "out"):
                x = [l["slices"][g][s] for l in ls]
                rowv = {"n": sum(v["n"] for v in x), "p50": nanmean([v["p50"] for v in x]), "p90": nanmean([v["p90"] for v in x]),
                        "p99": nanmean([v["p99"] for v in x]), "share2": nanmean([v["share2"] for v in x]),
                        "max": max(v["max"] for v in x) / 1e3, "over20": sum(v["over20"] for v in x), "over100": sum(v["over100"] for v in x)}
                sl["%s|%s|%s" % (cell_name(c), g, s)] = rowv
                print("  %-14s %-7s %-6s %8d %7.0f %7.0f %7.0f %9.3f %8.2f %6d %6d" % (
                    cell_name(c), g, s, rowv["n"], rowv["p50"], rowv["p90"], rowv["p99"], rowv["share2"], rowv["max"], rowv["over20"], rowv["over100"]))
    RES["slices"] = sl
    print()
    print("Worst probe latency per leg in the used span, with where it fell (every leg run):")
    worst = {}
    for c in CELLS:
        for l in [x for x in P["legs"] if (x["shape"], x["arm"]) == c]:
            t = l["top"][0]
            comp = l.get("top_companions", {})
            where = ("in a flush zone: %.0f ms after its start, %.0f ms before its end" % (t["since_start_ms"], t["before_end_ms"])) if t["flush"] == "yes" else \
                    ("outside any flush (next start in %.2f s)" % t["to_next_start_s"] if t.get("to_next_start_s") is not None else "outside any flush")
            used = "PRIMARY" if any(PRIMARY[r][c]["leg_id"] == l["leg_id"] for r in PRIMARY) else ("invalid" if not l["valid"] else "not in set")
            print("  %-24s %-10s worst %6.2f ms slice %-5s worker CPU %s; %s; probes over 5 ms within 20 ms of it: %d on %d connections, CPUs %s; control stream max %.2f ms (over 5 ms: %d)" % (
                l["leg_id"], used, t["lat_ms"], t["slice"], t["cpu"], where, comp.get("probes_over_5ms_within_20ms", 0), comp.get("connections", 0),
                ",".join(comp.get("cpus", [])), l["control"]["max_us"] / 1e3, l["control"]["over_5ms"]))
    print()
    print("Per cell, primary set: worst probe latency by slice and group (ms); worst probe lateness; Nighthawk (whole 80-90 s client run, not time-resolved):")
    for c in CELLS:
        ls = [PRIMARY[r][c] for r in sorted(PRIMARY)]
        w = {k: max(l["worst"][k] for l in ls) for k in ls[0]["worst"]}
        lt = max(ls, key=lambda l: l["lateness"]["max_us"])
        la = lt["lateness"]["max_at"]
        over20 = sum(l["slices"]["all"][s]["over20"] for l in ls for s in ("in", "onset", "post", "out"))
        print("  %-14s worst latency ms: IN all %.2f (cpu0 %.2f, others %.2f) | ONSET %.2f | POST %.2f | OUT %.2f (cpu0 %.2f, others %.2f) | probes over 20 ms: %d" % (
            cell_name(c), w["all_in"], w["cpu0_in"], w["others_in"], w["all_onset"], w["all_post"], w["all_out"], w["cpu0_out"], w["others_out"], over20))
        print("  %-14s worst lateness %.3f ms (%s, worker CPU %s, %s); lateness p99 max over legs %.4f ms; share over 1 ms max %.5f; requests queued behind the previous one on their connection: %d (cpu0 %d; in a flush zone %d); pipelined %d" % (
            "", lt["lateness"]["max_us"] / 1e3, lt["leg_id"], la["cpu"],
            ("in a flush zone, %.0f ms after its start, %.0f ms before its end" % (la["since_start_ms"], la["before_end_ms"])) if la["flush"] == "yes" else "outside any flush",
            max(l["lateness"]["p99_us"] for l in ls) / 1e3, max(l["lateness"]["share_over_1ms"] for l in ls),
            sum(l["lateness"]["queued_in_window"] for l in ls), sum(l["lateness"]["queued_cpu0"] for l in ls), sum(l["lateness"]["queued_in_flush"] for l in ls),
            sum(l["lateness"]["pipelined"] for l in ls)))
        print("  %-14s Nighthawk: p50 %.0f us, p99 %.0f us, p99.9 %.0f us, max %.1f ms (mean of legs; max of legs %.1f ms); pending total %s; queue-to-connect max %.1f ms; overflow %s" % (
            "", nanmean([l["ev"]["nh_latency"]["p50"] for l in ls]), nanmean([l["ev"]["nh_latency"]["p99"] for l in ls]), nanmean([l["ev"]["nh_latency"]["p999"] for l in ls]),
            nanmean([l["ev"]["nh_latency"]["max"] for l in ls]) / 1e3, max(l["ev"]["nh_latency"]["max"] for l in ls) / 1e3,
            sorted(set(l["ev"]["client_pending_total"] for l in ls)), max(l["ev"]["client_q2c_max_us"] for l in ls) / 1e3, sorted(set(json.dumps(l["ev"]["client_overflow"]) for l in ls))))
        worst[cell_name(c)] = {"w": w, "late_ms": lt["lateness"]["max_us"] / 1e3, "late_where": la, "over20": over20,
                               "nh_max_ms": max(l["ev"]["nh_latency"]["max"] for l in ls) / 1e3, "nh_p99": nanmean([l["ev"]["nh_latency"]["p99"] for l in ls])}
    RES["worst"] = worst
    print()
    print("Latency by time since flush start (10 ms bins, data probes, pooled over the primary legs: n, mean of per-leg p50, mean of per-leg p99, max; us):")
    for c in CELLS:
        ls = [PRIMARY[r][c] for r in sorted(PRIMARY)]
        parts = []
        for lo in range(-50, 100, 10):
            x = [l["profile"].get(str(lo)) for l in ls]
            x = [v for v in x if v]
            if x:
                parts.append("[%+d,%+d) n=%d p50=%.0f p99=%.0f max=%.0f" % (lo, lo + 10, sum(v["n"] for v in x), np.mean([v["p50"] for v in x]), np.mean([v["p99"] for v in x]), max(v["max"] for v in x)))
        print("  %s" % cell_name(c))
        for p in parts:
            print("      " + p)
    print()
    print("Scheduler view, primary set: thread run and run-queue wait, ms per second, inside whole flushes and outside (manipulation check for L3):")
    man = {}
    for c in CELLS:
        ls = [PRIMARY[r][c] for r in sorted(PRIMARY)]
        print("  %s" % cell_name(c))
        for th in ("main", "wrk:worker_0", "wrk:worker_1", "wrk:worker_2", "wrk:worker_3"):
            ri = nanmean([l["threads"][th]["in"]["run_ms_per_s"] for l in ls]); ro = nanmean([l["threads"][th]["out"]["run_ms_per_s"] for l in ls])
            wi = nanmean([l["threads"][th]["in"]["wait_ms_per_s"] for l in ls]); wo = nanmean([l["threads"][th]["out"]["wait_ms_per_s"] for l in ls])
            print("      %-13s CPU %s  run in %7.1f out %7.1f | wait in %7.2f out %7.2f | window busy %.1f%%" % (
                th, ls[0]["threads"][th]["cpus"], ri, ro, wi, wo, nanmean([l["threads"][th]["window"]["run_ms_per_s"] for l in ls]) / 10))
            man["%s|%s" % (cell_name(c), th)] = {"run_in": ri, "run_out": ro, "wait_in": wi, "wait_out": wo}
        w0 = man["%s|wrk:worker_0" % cell_name(c)]
        oth = max(man["%s|wrk:worker_%d" % (cell_name(c), i)]["wait_in"] for i in (1, 2, 3))
        print("      worker_0 wait in flush / out of flush = %.0fx; / the other workers' largest in flush = %.0fx" % (w0["wait_in"] / w0["wait_out"], w0["wait_in"] / oth))
    RES["sched"] = man


# ------------------------------------------------------------------ L4

def s5():
    section("5. L4: admin /ready during a flush (every 50 ms, new connection each)")
    out = {}
    for c in CELLS:
        ls = [PRIMARY[r][c] for r in sorted(PRIMARY)]
        per = [p for l in ls for p in l["admin"]["per_flush"]]
        ratio = [p["ratio"] for p in per]
        sent = sum(p["sent_in"] for p in per)
        early = sum(p["answered_before_end"] for p in per)
        o = {"flushes": len(per), "in_p50_ms": nanmean([l["admin"]["in"]["p50"] for l in ls]), "in_max_ms": max(l["admin"]["in"]["max"] for l in ls),
             "out_p50_ms": nanmean([l["admin"]["out"]["p50"] for l in ls]), "out_max_ms": max(l["admin"]["out"]["max"] for l in ls),
             "out_p99_ms": nanmean([l["admin"]["out"]["p99"] for l in ls]),
             "ratio_mean": float(np.mean(ratio)), "ratio_min": float(min(ratio)), "ratio_max": float(max(ratio)),
             "longest_wait_ms": max(p["max_wait_ms"] for p in per), "sent_in": sent, "answered_before_end": early,
             "slow_out": sum(l["admin"]["slow_out"] for l in ls), "n_out": sum(l["admin"]["out"]["n"] for l in ls),
             "unanswered": sum(l["admin"]["unanswered"] for l in ls), "non200": sum(l["admin"]["non200"] for l in ls)}
        out[cell_name(c)] = o
        print("  %-14s flushes %2d | sent inside a flush: p50 %7.1f ms max %7.1f ms | outside: p50 %.3f ms p99 %.3f ms max %.2f ms (over 20 ms: %d of %d) | longest wait / flush wall: mean %.3f (min %.3f, max %.3f); longest wait %.0f ms | "
              "probes sent >=20 ms after a start and >=100 ms before its end: %d, answered more than 50 ms before the end: %d | unanswered %d, non-200 %d" % (
                  cell_name(c), o["flushes"], o["in_p50_ms"], o["in_max_ms"], o["out_p50_ms"], o["out_p99_ms"], o["out_max_ms"], o["slow_out"], o["n_out"],
                  o["ratio_mean"], o["ratio_min"], o["ratio_max"], o["longest_wait_ms"], sent, early, o["unanswered"], o["non200"]))
    RES["L4"] = out
    print("  main-thread watchdog deltas per leg (miss, mega_miss), worker watchdog misses, primary set:")
    for c in CELLS:
        ls = [PRIMARY[r][c] for r in sorted(PRIMARY)]
        wd = [l["ev"]["watchdog"] for l in ls]
        print("    %-14s main miss %s mega %s | workers miss %s mega %s" % (
            cell_name(c), [w.get("server.main_thread.watchdog_miss") for w in wd], [w.get("server.main_thread.watchdog_mega_miss") for w in wd],
            [w.get("workers.watchdog_miss") for w in wd], [w.get("workers.watchdog_mega_miss") for w in wd]))


# ------------------------------------------------------------------ evidence

def s6():
    section("6. EVIDENCE ITEMS, RECOMPUTED (all %d legs run unless stated)" % len(P["legs"]))
    print("Probe, open loop:")
    for c in CELLS:
        ls = [l for l in P["legs"] if (l["shape"], l["arm"]) == c]
        print("  %-14s legs %d | intended times on the fixed 20 ms grid on every connection: %s | sent before intended: %d | rows/200/unanswered: %d/%d/%d | in window vs 800 x window: max abs diff %.1f | "
              "lateness p50 %.1f us, p99 max %.1f us, max %.0f us, share over 1 ms max %.5f | loop gaps over 1 ms: %s | gap-dropped %d | connection events %d | map 4 per CPU: %s, min margin %.0f, unchanged %s" % (
                  cell_name(c), len(ls), all(l["probe"]["intended_on_fixed_grid"] for l in ls), sum(l["probe"]["sent_before_intended"] for l in ls),
                  sum(l["probe"]["rows"] for l in ls), sum(l["probe"]["answered_200"] for l in ls), sum(l["probe"]["unanswered"] for l in ls),
                  max(abs(l["probe"]["in_window"] - l["probe"]["expected_in_window"]) for l in ls),
                  nanmean([l["lateness"]["p50_us"] for l in ls]), max(l["lateness"]["p99_us"] for l in ls), max(l["lateness"]["max_us"] for l in ls),
                  max(l["lateness"]["share_over_1ms"] for l in ls), [len(l["gaps"]) for l in ls], sum(l["probe"]["gap_dropped"] for l in ls), sum(l["events"] for l in ls),
                  all(set(l["map"]["per_cpu"].values()) == {4} and len(l["map"]["per_cpu"]) == 4 for l in ls), min(l["map"]["min_margin"] for l in ls), all(l["map"]["unchanged"] for l in ls)))
    print("  probe loop gaps over 1 ms (all in shared/statsd): leg, t in window s, length ms, distance to the nearest flush end ms:")
    for l in P["legs"]:
        for g in l["gaps"]:
            print("      %-24s t=%7.3f  %.2f ms  %.1f ms from a flush end" % (l["leg_id"], g["t"], g["ms"], g["since_flush_end_ms"]))
    print("  probe coverage: largest gap between consecutive intended times on one worker's four connections, ms (max over legs):",
          {cpu: round(max(l["coverage_gap_ms"][cpu] for l in P["legs"]), 2) for cpu in ("0", "1", "2", "3")})
    print("  control stream (direct to origin): p50 %.0f us, p99 max over legs %.0f us, max %.2f ms; probes over 1 ms: %d, over 5 ms: %d (of %d)" % (
        nanmean([l["control"]["p50_us"] for l in P["legs"]]), max(l["control"]["p99_us"] for l in P["legs"]), max(l["control"]["max_us"] for l in P["legs"]) / 1e3,
        sum(l["control"]["over_1ms"] for l in P["legs"]), sum(l["control"]["over_5ms"] for l in P["legs"]), sum(l["control"]["n"] for l in P["legs"])))
    print()
    print("Sampler and flush grid:")
    print("  samples/expected min %.4f; largest sample gap %.1f ms; missing reads %s; sampler CPU %s; whole flushes per leg %s; largest grid error %.0f ms; minor bursts %d; my burst edges vs the harness's: max diff %.2f ms" % (
        min(l["sampler"]["n"] / l["sampler"]["expected"] for l in P["legs"]), max(l["sampler"]["max_gap_ms"] for l in P["legs"]),
        sorted(set(l["sampler"]["missing"] for l in P["legs"])), sorted(set(json.dumps(l["sampler"]["affinity"]) for l in P["legs"])),
        sorted(set(len(l["whole"]) for l in P["legs"])), max(l["grid_err_ms"] for l in P["legs"]), sum(len(l["minor_bursts"]) for l in P["legs"]),
        max((l["burst_edge_diff_ms"] or 0) for l in P["legs"])))
    print("  legs with fewer than 6 whole flushes:", [(l["leg_id"], len(l["whole"]), sum(b["partial"] for b in l["bursts_all"])) for l in P["legs"] if len(l["whole"]) != 6])
    print()
    print("Pinning, CPU, rate:")
    ev = {}
    for c in CELLS:
        ls = [l for l in P["legs"] if (l["shape"], l["arm"]) == c]
        pins = all(l["ev"]["pin_before"] and l["ev"]["pin_after"] and l["ev"]["pinning_ok"] for l in ls)
        mapok = all(sorted(l["ev"]["pin_map"].values()) == [0, 1, 2, 3] for l in ls)
        last = set(json.dumps(sorted(l["ev"]["thread_last_cpu"].items())) for l in ls)
        mig = sum(l["ev"]["migrations"] for l in ls)
        busy = {k: nanmean([l["ev"]["perf_busy"].get(k) for l in ls]) for k in ("envoy-1.40.2", "wrk:worker_0", "wrk:worker_1", "wrk:worker_2", "wrk:worker_3")}
        cpub = {k: nanmean([l["ev"]["sut_cpu_busy_pct"].get(k) for l in ls]) for k in ("0", "1", "2", "3", "4")}
        sib = max(max(l["ev"]["sut_cpu_busy_pct"].get(k, 0.0) for k in ("40", "41", "42", "43", "44")) for l in ls)
        sibkeys = sorted(set(k for l in ls for k in l["ev"]["sut_cpu_busy_pct"]), key=int)
        print("  %-14s pins before and after ok: %s; workers on CPUs 0-3 one each: %s; main CPU %s; last CPU of main and workers: %s; migrations (perf) %d" % (
            cell_name(c), pins, mapok, sorted(set(l["ev"]["main_cpu"] for l in ls)), "; ".join(sorted(last)), mig))
        print("  %-14s thread busy (perf task-clock / window): main %.1f%%, workers %s; CPU busy %% (CPU 0..4): %s; siblings 40-44 max %.1f%%; SUT busy (workers' mean) %.1f%%; cycles/request %.0fk" % (
            "", 100 * busy["envoy-1.40.2"], " ".join("%.1f%%" % (100 * busy["wrk:worker_%d" % i]) for i in range(4)), " ".join(fnum(cpub[k], 1) for k in ("0", "1", "2", "3", "4")) + " (CPUs recorded: " + ",".join(sibkeys) + ")", sib,
            100 * nanmean([l["ev"]["sut_busy"] for l in ls]), nanmean([l["ev"]["cycles_total_per_req"] for l in ls]) / 1e3))
        print("  %-14s Nighthawk 2xx rate %.2f to %.2f /s (target 4400); probe in window / window: %.2f to %.2f /s (target 800); listener windowed rate (recorded, read-time biased) %.1f to %.1f; "
              "exact count error: %s; client headroom min %.2f; non-2xx %s; Envoy exit %s" % (
                  "", min(l["ev"]["client_rate_2xx"] for l in ls), max(l["ev"]["client_rate_2xx"] for l in ls),
                  min(l["probe"]["in_window"] / (l["t1"] - l["t0"]) for l in ls), max(l["probe"]["in_window"] / (l["t1"] - l["t0"]) for l in ls),
                  min(l["ev"]["sut_rate_2xx"] for l in ls), max(l["ev"]["sut_rate_2xx"] for l in ls), [l["count"]["recomputed_error"] for l in ls],
                  min(l["ev"]["client_headroom"] for l in ls), sorted(set(json.dumps(l["ev"]["non2xx"]) for l in ls)), sorted(set(l["ev"]["envoy_exit"] for l in ls))))
        ev[cell_name(c)] = {"main_busy": busy["envoy-1.40.2"], "worker_busy": [busy["wrk:worker_%d" % i] for i in range(4)], "cpu_busy": cpub,
                            "sut_busy": nanmean([l["ev"]["sut_busy"] for l in ls])}
    RES["busy"] = ev
    print()
    print("Stats count, flushes, uptime:")
    for c in CELLS:
        ls = [l for l in P["legs"] if (l["shape"], l["arm"]) == c]
        print("  %-14s stats total %s; used %d to %d; dropped_stat_flushes delta %s; uptime error s max %.3f" % (
            cell_name(c), sorted(set(l["ev"]["stats_total"] for l in ls)), min(l["ev"]["used_total"] for l in ls), max(l["ev"]["used_total"] for l in ls),
            sorted(set(l["ev"]["dropped_stat_flushes"] for l in ls)), max(abs(l["ev"]["uptime"]["error_s"]) for l in ls)))
    print()
    print("UDP (statsd legs):")
    for l in P["legs"]:
        if l["arm"] != "statsd":
            continue
        u, s = l["ev"]["udp_leg"], l["ev"]["statsd"]
        cg = s["cg_per_flush"]
        full = [x for x in cg if x > 0.99 * l["ev"]["used_cg_lines"]]
        print("  %-24s kernel sent %d delivered %d dropped %d rcvbuf_errors %d in_errors %d socket_drops %s | sink datagrams %d, classes c %d g %d ms %d other %d h %d | uptime marks %d; c+g per flush %d to %d over %d full flushes (admin used c+g %d; max rel diff %.2e); "
              "receive queue max %d of %d bytes; drained quiet %s" % (
                  l["leg_id"], u["sent"], u["delivered"], u["dropped"], u["rcvbuf_errors"], u["in_errors"], u["socket_drops"], s["datagrams"],
                  s["classes"]["c"], s["classes"]["g"], s["classes"]["ms"], s["classes"]["other"], s["classes"]["h"], s["marks"],
                  min(full), max(full), len(full), l["ev"]["used_cg_lines"], max(abs(x - l["ev"]["used_cg_lines"]) for x in full) / l["ev"]["used_cg_lines"],
                  s["rx_queue_max"], s["rcvbuf_granted"], s["drain_quiet"]))
    print("  nosink and otlp legs, box-wide UDP delivered / to closed ports over the leg:", sorted(set((l["ev"]["udp_leg"]["delivered"], l["ev"]["udp_leg"]["no_ports"]) for l in P["legs"] if l["arm"] != "statsd")))
    print()
    print("OTLP (own/otlp legs): Envoy's request counter and the collector's accepted points, against the admin count of used stats:")
    for l in P["legs"]:
        if l["arm"] != "otlp":
            continue
        oc, cd = l["ev"]["otlp_cluster"], l["ev"]["collector_delta"]
        used = l["ev"]["used_total"]
        per = cd["accepted_metric_points"] / cd["fit"]["n"]
        print("  %-22s used %d | Envoy: requests %d = %d flushes x %d (ceil(used/10000) = %d), whole_error %s, rx_reset %s, http2 stats present %s | collector: accepted %d over n = %d flushes = %.1f per flush (%+.4f%% of used), refused %d, settled %s, limit %s MiB" % (
            l["leg_id"], used, oc["requests"], oc["flushes"], oc["requests_per_flush_expected"], math.ceil(used / 10000), oc["whole_error"], oc["rx_reset"], oc["http2_stats_present"],
            cd["accepted_metric_points"], cd["fit"]["n"], per, 100 * (per / used - 1), cd["refused_metric_points"], cd["settled"], l["ev"]["collector_cfg"]["max_recv_msg_size_mib"]))


# ------------------------------------------------------------------ sensitivity of the design

def s7():
    section("7. WHAT THE RUN COULD HAVE SEEN: a synthetic stall added to the real probe data (primary set)")
    print("A stall of D ms is added at every whole flush: a probe with intended time x inside [s, s + D) gets (s + D - x) more latency.")
    print("'onset' = s is the flush start, all workers (tests L2 and L1). 'mid' = s is the middle of the flush, all workers (L1) or the CPU 0 worker only (L3).")
    print("Detected = the row's 95% interval excludes zero and |mean| exceeds max(reach, 120 us); Holm p with the other five rows as observed.")
    base = {}
    for rname, cells, L, primary in ROWS[:6]:
        base[rname] = row(PRIMARY, cells, "%s_p99" % L)
    tests = [("L2 own, 3 arms pooled", "L2_p99", "onset stall, all workers"),
             ("L1 own/nosink", "L1_p99_onset_stall", "onset stall, all workers"),
             ("L1 own/nosink", "L1_p99_mid_stall", "mid-flush stall, all workers"),
             ("L1 own/statsd", "L1_p99_mid_stall", "mid-flush stall, all workers"),
             ("L1 own/otlp", "L1_p99_mid_stall", "mid-flush stall, all workers"),
             ("L3 own/nosink (placebo)", "L3_p99_mid_stall_cpu0", "mid-flush stall, CPU 0 worker only"),
             ("L3 own/statsd (placebo)", "L3_p99_mid_stall_cpu0", "mid-flush stall, CPU 0 worker only")]
    names = {r[0]: r for r in ROWS}
    out = {}
    for rname, key, what in tests:
        cells = names[rname][1]
        b = base.get(rname) or row(PRIMARY, cells, "%s_p99" % names[rname][2])
        line = []
        first = None
        for d in ("0.5", "1", "2", "3", "5", "10", "20"):
            vals = []
            for r in sorted(PRIMARY):
                vals.append(float(np.mean([PRIMARY[r][c]["inject"][d][key] for c in cells])))
            st = tci(vals)
            ps = [base[k]["p"] for k in base if k != rname] + [st["p"]]
            hp = holm(ps)[-1]
            det = (st["lo"] > 0 or st["hi"] < 0) and abs(st["mean"]) > max(b["reach"], 120.0)
            line.append("D=%s: %+.0f [%+.0f, %+.0f] %s%s" % (d, st["mean"], st["lo"], st["hi"], "DETECTED" if det else "no", (" (Holm p %.3f)" % hp) if det else ""))
            if det and first is None:
                first = d
        print("  %-26s %-36s reach %.0f us | %s" % (rname, what, b["reach"], " | ".join(line)))
        print("  %-26s -> smallest D on the grid meeting the rule: %s ms" % ("", first))
        out["%s|%s" % (rname, what)] = first
    RES["inject"] = out
    print()
    print("Hard bound from the worst probe actually seen inside a flush on the own-core cells (IN and ONSET slices):")
    for c in CELLS:
        ls = [PRIMARY[r][c] for r in sorted(PRIMARY)]
        w = max(max(l["worst"]["all_in"], l["worst"]["all_onset"]) for l in ls)
        nfl = sum(len(l["whole"]) for l in ls)
        cov = max(max(l["coverage_gap_ms"].values()) for l in ls)
        print("  %-14s %d flushes; worst probe sent in a flush %.2f ms; a probe reaches each worker at least every %.2f ms -> no worker stood still for longer than about %.1f ms in any of these flushes; "
              "zero such stalls in %d flushes bounds the chance per flush at %.1f%% (95%%)" % (
                  cell_name(c), nfl, w, cov, w + cov, nfl, 100 * (1 - 0.05 ** (1.0 / nfl))))


# ------------------------------------------------------------------ anomalies

def s8():
    section("8. ANOMALIES")
    print("Statsd timer ('ms') lines against the harness's expectation (3 per request + admin requests + 2 per downstream close + upstream connects + upstream closes):")
    for l in P["legs"]:
        if l["arm"] != "statsd":
            continue
        s = l["ev"]["statsd"]
        e = s["ms_expected"]
        res = s["ms_residual"]
        r2 = res - e["upstream_closes"]
        act = s["upstream_cx_active_end"]
        fm = s["first_marks"]
        print("  %-24s lines %d expected %d residual %+d (%.3f%%) | residual - upstream closes (%d) = %+d; ingress connections %s; upstream connections still open at the read %s | timer lines at the first uptime marks: %s" % (
            l["leg_id"], s["ms_lines"], e["total"], res, 100.0 * res / e["total"], e["upstream_closes"], r2, s["ingress_cx_total"], act,
            ", ".join("uptime %.0f s: %d" % (m[0], m[3]) for m in fm)))
    rs = [l["ev"]["statsd"]["ms_residual"] for l in P["legs"] if l["arm"] == "statsd"]
    tot = [l["ev"]["statsd"]["ms_expected"]["total"] for l in P["legs"] if l["arm"] == "statsd"]
    print("  residual: %d to %d lines, mean %.0f, SD %.0f; expected totals %d to %d; share %.3f%% to %.3f%%" % (
        min(rs), max(rs), np.mean(rs), np.std(rs, ddof=1), min(tot), max(tot), 100 * min(r / t for r, t in zip(rs, tot)), 100 * max(r / t for r, t in zip(rs, tot))))
    print("  correlation of the residual with the expected total over the %d legs: %.2f (a per-request term would scale; r01-own-statsd has 25,000 more requests and the same residual)" % (len(rs), np.corrcoef(rs, tot)[0, 1]))
    print()
    print("Nighthawk run length: requests sent per leg by cell:", {cell_name(c): sorted(set(l["count"]["nh_requests"] for l in P["legs"] if (l["shape"], l["arm"]) == c)) for c in CELLS})
    print("Count reads (s) before and after, by cell (mean):", {cell_name(c): [round(nanmean([l["count"]["reads_s"][i] for l in P["legs"] if (l["shape"], l["arm"]) == c]), 2) for i in (0, 1)] for c in CELLS})
    print("Nighthawk end relative to a flush start (s), all legs by cell:", {cell_name(c): [round(l["count"]["nh_end_phase_s"], 2) for l in P["legs"] if (l["shape"], l["arm"]) == c] for c in CELLS})
    print("First whole flush start after t0 (s), all legs by cell:", {cell_name(c): [round(l["bursts_all"][0]["start"] - l["t0"], 2) for l in P["legs"] if (l["shape"], l["arm"]) == c] for c in CELLS})


for f in (s1, s2, s3, s4, s5, s6, s7, s8):
    f()
with open(os.path.join(lib.OUT, "results.json"), "w") as fh:
    json.dump(RES, fh, indent=1, default=str)
