"""Exploratory checks beside the pre-stated rows (labelled as such in the write-up):

A. what the workers do at a flush start (scheduler run time, 5 ms samples) and the probe latency there (1 ms bins);
B. the flush-start spike per flush against sham windows of the same legs;
C. slow-probe events (several probes of one worker over 5 ms together): rate inside and outside flushes,
   and what the worker's thread did during the largest ones;
D. the OTLP flush: when admin probes sent inside the burst were answered.

Uses the primary set (complete rounds) unless stated. Reads raw files.
"""
import json
import math
import os

import numpy as np

import lib
from lib import CELLS, cell_name

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(lib.OUT, "perleg.json")))
LEGS = {l["leg_id"]: l for l in P["legs"]}
PRIMARY_IDS = ["r01-%s.rr1", "r02-%s.rr1", "r03-%s", "r05-%s"]


def primary(c):
    return [LEGS[p % ("%s-%s" % c)] for p in PRIMARY_IDS]


def load(l):
    main = lib.load_main(l["leg_id"])
    pr = lib.load_probe(l["leg_id"])
    cpu_of = {c["conn"]: c["cpus"] for c in pr["meta"]["meta"]["map"]["connections"]}
    tid_of = {info["cpus"]: tid for tid, info in main["threads"].items() if info["comm"].startswith("wrk:")}
    d = pr["d"]
    ts = d[:, 2] / 1e9
    lat = (d[:, 4] - d[:, 2]) / 1e3
    cpu = np.array([int(cpu_of[int(c)]) for c in d[:, 0]])
    return main, pr, ts, lat, cpu, tid_of


out = {}
print("A. FLUSH START: worker run time and probe latency around the main-thread burst start (primary set)")
print("   worker run time per 5 ms sample, mean over 4 workers and the cell's 24 flushes, minus the cell's out-of-flush mean (ms of CPU per 5 ms):")
cache = {}
for c in CELLS:
    acc = {}
    extra_per_flush = []
    fine = {}
    for l in primary(c):
        main, pr, ts, lat, cpu, tid_of = cache.setdefault(l["leg_id"], load(l))
        t0, t1 = l["t0"], l["t1"]
        for cpu_id, tid in tid_of.items():
            if c[0] == "shared" and cpu_id == "0":
                continue  # worker_0 shares its CPU with the main thread there; the others show the merge alone
            a = np.asarray(main["series"][tid], dtype=np.float64)
            t = a[:, 0]
            dr = np.diff(a[:, 1]) / 1e6
            base = l["threads"][main["threads"][tid]["comm"]]["out"]["run_ms_per_s"] / 1e3 * 5.0
            for b in l["whole"]:
                i0 = int(np.searchsorted(t, b["start"])) - 1  # sample interval that begins at the burst start
                tot = 0.0
                for k in range(-8, 9):
                    j = i0 + k
                    if 0 <= j < len(dr):
                        acc.setdefault(k, []).append(dr[j] - base * (t[j + 1] - t[j]) / 0.005)
                        if -4 <= k <= 1:
                            tot += dr[j] - base * (t[j + 1] - t[j]) / 0.005
                extra_per_flush.append(tot)
        for b in l["whole"]:
            rel = (ts - b["start"]) * 1e3
            for k in range(-15, 12):
                m = (rel >= k) & (rel < k + 1)
                if c[0] == "shared":
                    m &= cpu != 0
                fine.setdefault(k, []).extend(lat[m].tolist())
    print("   %-14s %s" % (cell_name(c), " ".join("%+d:%+.2f" % (5 * k, np.mean(v)) for k, v in sorted(acc.items()))))
    print("   %-14s extra worker CPU in [-20, +10) ms around the burst start: mean %.2f ms per worker per flush (SD %.2f, n %d worker-flushes)%s" % (
        "", np.mean(extra_per_flush), np.std(extra_per_flush, ddof=1), len(extra_per_flush), "; workers 1-3 only" if c[0] == "shared" else ""))
    out["merge_cpu_ms:" + cell_name(c)] = float(np.mean(extra_per_flush))
    print("   %-14s probe latency by intended time since the burst start, 1 ms bins (n, share over 1 ms, max us)%s:" % ("", "; workers 1-3 only" if c[0] == "shared" else ""))
    print("        " + " | ".join("%+d: n=%d %.0f%% max %.0f" % (k, len(v), 100 * np.mean(np.array(v) > 1000), max(v) if v else 0) for k, v in sorted(fine.items())))

print()
print("B. FLUSH-START SPIKE PER FLUSH against sham windows (exploratory; window [start - 15 ms, start + 10 ms), 20 probes)")
print("   per flush: largest probe latency in the window; a 'spike' = at least one probe over 1.5 ms")
for c in CELLS:
    real, sham = [], []
    real_n2, sham_n2 = [], []
    for l in primary(c):
        main, pr, ts, lat, cpu, tid_of = cache[l["leg_id"]]
        t0, t1 = l["t0"], l["t1"]
        sel = np.ones(len(ts), dtype=bool) if c[0] == "own" else (cpu != 0)
        shifts = lib.sham_shifts(l["whole"], l["bursts_all"], t0, t1)
        for b in l["whole"]:
            m = (ts >= b["start"] - 0.015) & (ts < b["start"] + 0.010) & sel
            real.append(lat[m].max())
            real_n2.append(int((lat[m] > 1500).sum()))
        for s, wins in shifts.items():
            for a, e in wins:
                m = (ts >= a - 0.015) & (ts < a + 0.010) & sel
                sham.append(lat[m].max())
                sham_n2.append(int((lat[m] > 1500).sum()))
    real, sham = np.array(real), np.array(sham)
    print("   %-14s%s real flushes %d: with a spike %d (%.0f%%); largest latency in the window: median %.2f ms, p90 %.2f, max %.2f; probes over 1.5 ms per flush mean %.2f | sham windows %d: with a spike %d (%.1f%%); median %.2f ms, p90 %.2f, max %.2f" % (
        cell_name(c), " (workers 1-3)" if c[0] == "shared" else "", len(real), int((real > 1500).sum()), 100 * np.mean(real > 1500), np.median(real) / 1e3, np.percentile(real, 90) / 1e3, real.max() / 1e3, np.mean(real_n2),
        len(sham), int((sham > 1500).sum()), 100 * np.mean(sham > 1500), np.median(sham) / 1e3, np.percentile(sham, 90) / 1e3, sham.max() / 1e3))
    out["spike:" + cell_name(c)] = {"flushes": len(real), "with_spike": int((real > 1500).sum()), "median_ms": float(np.median(real) / 1e3), "p90_ms": float(np.percentile(real, 90) / 1e3),
                                    "max_ms": float(real.max() / 1e3), "sham_n": len(sham), "sham_with_spike": int((sham > 1500).sum()), "sham_median_ms": float(np.median(sham) / 1e3)}
# per round test of the per-leg spike share, own-core cells pooled
vals = []
for pid in PRIMARY_IDS:
    r, s = [], []
    for c in CELLS[:3]:
        l = LEGS[pid % ("%s-%s" % c)]
        main, pr, ts, lat, cpu, tid_of = cache[l["leg_id"]]
        for b in l["whole"]:
            m = (ts >= b["start"] - 0.015) & (ts < b["start"] + 0.010)
            r.append(lat[m].max() > 1500)
        for sft, wins in lib.sham_shifts(l["whole"], l["bursts_all"], l["t0"], l["t1"]).items():
            for a, e in wins:
                m = (ts >= a - 0.015) & (ts < a + 0.010)
                s.append(lat[m].max() > 1500)
    vals.append(100 * (np.mean(r) - np.mean(s)))
st = lib.tci(vals)
print("   own core, three arms pooled, per round: share of flushes with a spike minus the share of sham windows with one, points: %s; mean %+.1f [%+.1f, %+.1f], n %d, p %.2g (exploratory, not in the Holm family)" % (
    ", ".join("%+.1f" % v for v in vals), st["mean"], st["lo"], st["hi"], st["n"], st["p"]))
out["spike_test"] = {"values": vals, "mean": st["mean"], "lo": st["lo"], "hi": st["hi"], "p": st["p"]}

print()
print("C. SLOW-PROBE EVENTS (all 36 legs): a group of probes over 5 ms on one worker's connections within 25 ms")
print("   exposure: seconds inside whole flushes (IN zone incl. guard) and outside all flush zones, per cell")
ev_rows = []
for c in CELLS:
    n_in = n_out = n_post = 0
    s_in = s_out = 0.0
    sizes = []
    multi = 0
    for l in [x for x in P["legs"] if (x["shape"], x["arm"]) == c]:
        main, pr, ts, lat, cpu, tid_of = cache.setdefault(l["leg_id"], load(l))
        t0, t1 = l["t0"], l["t1"]
        span = (ts >= t0 + lib.EDGE) & (ts <= t1 - lib.EDGE)
        zones = [(b["start"] - lib.GUARD, b["end"] + lib.POST) for b in l["bursts_all"]]
        inz = [(b["start"] - lib.GUARD, b["end"]) for b in l["whole"]]
        s_in += sum(e - a for a, e in inz)
        s_out += (t1 - t0 - 2 * lib.EDGE) - sum(min(e, t1 - lib.EDGE) - max(a, t0 + lib.EDGE) for a, e in zones if e > t0 + lib.EDGE and a < t1 - lib.EDGE)
        for w in range(4):
            if c[0] == "shared" and w == 0:
                continue  # worker_0 is the treated worker there
            m = span & (cpu == w) & (lat > 5000)
            tt = np.sort(ts[m])
            if len(tt) == 0:
                continue
            groups = [[tt[0]]]
            for x in tt[1:]:
                if x - groups[-1][-1] <= 0.025:
                    groups[-1].append(x)
                else:
                    groups.append([x])
            for g in groups:
                mm = span & (cpu == w) & (ts >= g[0] - 1e-9) & (ts <= g[-1] + 1e-9)
                peak = float(lat[mm].max() / 1e3)
                # are other workers slow at the same moment?
                oth = span & (cpu != w) & (ts >= g[0] - 0.01) & (ts <= g[-1] + 0.01) & (lat > 5000)
                multi += int(oth.any())
                where = "out"
                for a, e in inz:
                    if a <= g[0] <= e:
                        where = "in"
                if where == "out":
                    for a, e in zones:
                        if a <= g[0] <= e:
                            where = "post/partial"
                if where == "in":
                    n_in += 1
                elif where == "out":
                    n_out += 1
                else:
                    n_post += 1
                sizes.append(peak)
                rel = None
                for b in l["whole"]:
                    if b["start"] - lib.GUARD <= g[0] <= b["end"]:
                        rel = (g[0] - b["start"]) * 1e3
                ev_rows.append((peak, l["leg_id"], w, where, g[0], len(g), rel, tid_of[str(w)]))
    r_in = n_in / s_in if s_in else math.nan
    r_out = n_out / s_out if s_out else math.nan
    # exact conditional test: given n_in + n_out events, is the split what the exposure says?
    from scipy import stats as sst
    pbin = sst.binomtest(n_in, n_in + n_out, s_in / (s_in + s_out)).pvalue if (n_in + n_out) else math.nan
    print("   %-14s%s events %d (in %d, out %d, post or partial %d); exposure in %.0f s, out %.0f s; rate in %.4f/s, out %.4f/s (per worker-leg-second x workers); expected in by exposure %.1f; binomial p %.2f; peak ms median %.1f max %.1f; with another worker slow at the same time: %d" % (
        cell_name(c), " (workers 1-3)" if c[0] == "shared" else "", n_in + n_out + n_post, n_in, n_out, n_post, s_in, s_out, r_in, r_out,
        (n_in + n_out) * s_in / (s_in + s_out), pbin, np.median(sizes) if sizes else math.nan, max(sizes) if sizes else math.nan, multi))
    out["events:" + cell_name(c)] = {"in": n_in, "out": n_out, "post": n_post, "s_in": s_in, "s_out": s_out, "p": pbin, "peak_max": max(sizes) if sizes else None}
tot_in = sum(out["events:" + cell_name(c)]["in"] for c in CELLS)
tot_out = sum(out["events:" + cell_name(c)]["out"] for c in CELLS)
sin = sum(out["events:" + cell_name(c)]["s_in"] * (3 if c[0] == "shared" else 4) for c in CELLS)
sout = sum(out["events:" + cell_name(c)]["s_out"] * (3 if c[0] == "shared" else 4) for c in CELLS)
from scipy import stats as sst
print("   all cells: in %d, out %d; worker-seconds in %.0f, out %.0f; rate per worker-hour in %.1f, out %.1f; binomial p %.2f" % (
    tot_in, tot_out, sin, sout, 3600 * tot_in / sin, 3600 * tot_out / sout, sst.binomtest(tot_in, tot_in + tot_out, sin / (sin + sout)).pvalue))
out["events_all"] = {"in": tot_in, "out": tot_out, "ws_in": sin, "ws_out": sout}
rels = [r[6] for r in ev_rows if r[3] == "in" and r[6] is not None]
late_in = sum(1 for x in rels if x > 50)
print("   without the events within 50 ms of a flush start (the start spike of section A): in %d, out %d; expected in by exposure %.1f; binomial p %.2f; rate per worker-hour in %.1f, out %.1f" % (
    late_in, tot_out, (late_in + tot_out) * sin / (sin + sout), sst.binomtest(late_in, late_in + tot_out, sin / (sin + sout)).pvalue, 3600 * late_in / sin, 3600 * tot_out / sout))
out["events_all"]["in_after_50ms"] = late_in
print("   in-flush events: time since the flush start (ms):", sorted(round(r[6]) for r in ev_rows if r[3] == "in" and r[6] is not None))
ev_rows.sort(reverse=True)
kinds = {"run-queue wait of 5 ms or more": 0, "worker ran flat out (3 samples at 4.5 ms or more of 5)": 0, "neither": 0}
waits = []
for peak, lid, w, where, tg, n, rel, tid in ev_rows:
    main = cache[lid][0]
    a = np.asarray(main["series"][tid], dtype=np.float64)
    t = a[:, 0]
    i = int(np.searchsorted(t, tg))
    lo, hi = max(i - 2, 0), min(i + 9, len(t) - 1)
    wsum = (a[hi, 2] - a[lo, 2]) / 1e6
    runs = np.diff(a[lo:hi + 1, 1]) / 1e6
    flat = any(all(runs[j + q] >= 4.5 for q in range(3)) for j in range(max(len(runs) - 2, 0)))
    if wsum >= 5.0:
        kinds["run-queue wait of 5 ms or more"] += 1
        waits.append(wsum)
    elif flat:
        kinds["worker ran flat out (3 samples at 4.5 ms or more of 5)"] += 1
    else:
        kinds["neither"] += 1
print("   all %d events by what the worker thread's scheduler counters show in the 55 ms around the event: %s; wait in the first kind: median %.1f ms, max %.1f ms" % (
    len(ev_rows), kinds, np.median(waits) if waits else math.nan, max(waits) if waits else math.nan))
out["event_kinds"] = kinds
print("   the 10 largest events and what that worker's thread did in the 5 ms samples around it (run ms / run-queue wait ms per 5 ms sample):")
for peak, lid, w, where, tg, n, rel, tid in ev_rows[:10]:
    main = cache[lid][0]
    a = np.asarray(main["series"][tid], dtype=np.float64)
    t = a[:, 0]
    i = int(np.searchsorted(t, tg))
    seg = []
    for j in range(max(i - 2, 0), min(i + 9, len(t) - 1)):
        seg.append("%.1f/%.1f" % ((a[j + 1, 1] - a[j, 1]) / 1e6, (a[j + 1, 2] - a[j, 2]) / 1e6))
    mt = np.asarray(main["series"][str(main["main_tid"])], dtype=np.float64)
    k = int(np.searchsorted(mt[:, 0], tg))
    mrun = (mt[min(k + 8, len(mt) - 1), 1] - mt[max(k - 2, 0), 1]) / 1e6
    print("     %-24s worker CPU %d peak %5.1f ms probes %d %-12s%s | %s | main thread ran %.1f ms in those 50 ms" % (
        lid, w, peak, n, where, (" %+.0f ms from flush start" % rel) if rel is not None else "", " ".join(seg), mrun))

print()
print("D. OTLP: admin probes sent inside the burst, by tenth of the burst (primary set): n, median wait ms, share answered within 20 ms")
rows = {}
for l in primary(("own", "otlp")):
    main, pr, ts, lat, cpu, tid_of = cache[l["leg_id"]]
    a = pr["a"]
    ats = a[:, 2] / 1e9
    aw = (a[:, 4] - a[:, 2]) / 1e6
    for b in l["whole"]:
        f = (ats - b["start"]) / (b["end"] - b["start"])
        for k in range(10):
            m = (f >= k / 10) & (f < (k + 1) / 10)
            rows.setdefault(k, []).extend(aw[m].tolist())
        # when does the main thread first answer after the burst start?
for k, v in sorted(rows.items()):
    v = np.array(v)
    print("   %d0-%d0%%: n=%d median %.0f ms, answered within 20 ms: %.0f%%" % (k, k + 1, len(v), np.median(v), 100 * np.mean(v < 20)))
blk = []
for l in primary(("own", "otlp")):
    main, pr, ts, lat, cpu, tid_of = cache[l["leg_id"]]
    a = pr["a"]
    ats = a[:, 2] / 1e9
    ad = a[:, 4] / 1e9
    for b in l["whole"]:
        m = (ats >= b["start"] + 0.02) & (ats <= b["start"] + 0.2)
        if m.any():
            blk.append((float(ad[m].min() - b["start"]), b["end"] - b["start"]))
blk = np.array(blk)
print("   first answer to a probe sent 20-200 ms after the burst start comes %.0f ms after the start (median; min %.0f, max %.0f); burst wall median %.0f ms -> blocking part about %.0f%% of the burst" % (
    1e3 * np.median(blk[:, 0]), 1e3 * blk[:, 0].min(), 1e3 * blk[:, 0].max(), 1e3 * np.median(blk[:, 1]), 100 * np.median(blk[:, 0] / blk[:, 1])))
out["otlp_block_ms"] = {"median": float(1e3 * np.median(blk[:, 0])), "min": float(1e3 * blk[:, 0].min()), "max": float(1e3 * blk[:, 0].max()), "wall_median": float(1e3 * np.median(blk[:, 1]))}
for c in (("own", "nosink"), ("own", "statsd"), ("shared", "nosink"), ("shared", "statsd")):
    blk = []
    for l in primary(c):
        main, pr, ts, lat, cpu, tid_of = cache[l["leg_id"]]
        a = pr["a"]
        ats = a[:, 2] / 1e9
        ad = a[:, 4] / 1e9
        for b in l["whole"]:
            m = (ats >= b["start"] + 0.02) & (ats <= b["start"] + 0.2)
            if m.any():
                blk.append((float(ad[m].min() - b["start"]), b["end"] - b["start"]))
    blk = np.array(blk)
    print("   %-14s same figure: first answer %.0f ms after the start (median); burst wall median %.0f ms -> %.0f%%" % (cell_name(c), 1e3 * np.median(blk[:, 0]), 1e3 * np.median(blk[:, 1]), 100 * np.median(blk[:, 0] / blk[:, 1])))
    out["block_ms:" + cell_name(c)] = float(1e3 * np.median(blk[:, 0]))

with open(os.path.join(lib.OUT, "extra.json"), "w") as f:
    json.dump(out, f, indent=1)
