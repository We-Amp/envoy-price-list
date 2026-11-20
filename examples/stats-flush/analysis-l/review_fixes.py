"""Checks made for the numbers review of run L, from the raw files.

F2  probe latency outside the 60 s window (whole logs), per cell and worker group
F3  admin wait for a probe intended inside a burst (no guard): median and max per cell
F4  slow events on the 20 legs of the complete rounds only, own-core cells separately, two definitions
F9  admin probes sent well inside a flush: answered more than 20 / 10 ms before the burst end
F13 requests that waited for their own connection: count and longest wait
"""
import json
import math
import os

import numpy as np
from scipy import stats as sst

import lib
from lib import CELLS, cell_name

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(lib.OUT, "perleg.json")))
LEGS = {l["leg_id"]: l for l in P["legs"]}
PRIMARY_IDS = ["r01-%s.rr1", "r02-%s.rr1", "r03-%s", "r05-%s"]


def primary(c):
    return [LEGS[p % ("%s-%s" % c)] for p in PRIMARY_IDS]


def is_primary(l):
    return any(x["leg_id"] == l["leg_id"] for x in primary((l["shape"], l["arm"])))


cache = {}


def load(l):
    if l["leg_id"] in cache:
        return cache[l["leg_id"]]
    main = lib.load_main(l["leg_id"])
    pr = lib.load_probe(l["leg_id"])
    cpu_of = {c["conn"]: c["cpus"] for c in pr["meta"]["meta"]["map"]["connections"]}
    d = pr["d"]
    r = {"main": main, "pr": pr, "ts": d[:, 2] / 1e9, "lat": (d[:, 4] - d[:, 2]) / 1e3,
         "cpu": np.array([int(cpu_of[int(c)]) for c in d[:, 0]]), "d": d}
    cache[l["leg_id"]] = r
    return r


print("F2. PROBE LATENCY OUTSIDE THE WINDOW (whole probe logs; all 36 legs)")
print("    flush phase before the window = seconds after a start on the leg's 10 s grid, extrapolated back from the first whole burst")
allover100 = 0
rows_total = 0
for c in CELLS:
    for l in [x for x in P["legs"] if (x["shape"], x["arm"]) == c]:
        r = load(l)
        ts, lat, cpu = r["ts"], r["lat"], r["cpu"]
        rows_total += len(ts)
        allover100 += int((lat >= 100000).sum())
        t0, t1 = l["t0"], l["t1"]
        outw = (ts < t0) | (ts > t1)
        if not outw.any():
            continue
        i = int(np.argmax(np.where(outw, lat, -1)))
        s0 = l["whole"][0]["start"]
        wall = np.mean([b["end"] - b["start"] for b in l["whole"]])
        ph = (ts[i] - s0) % 10.0
        m20 = outw & (lat > 20000)
        nh = l["count"]["nh_start_rel_t0"]
        print("    %-24s %-8s outside the window: n %5d, worst %6.2f ms on worker CPU %d at t0 %+.2f s (Nighthawk starts at t0 %+.2f s); %.2f s after a grid flush start (flush %.2f s: %s); over 20 ms: %d (CPU 0: %d), their times rel t0: %s" % (
            l["leg_id"], "PRIMARY" if is_primary(l) else ("invalid" if not l["valid"] else "unused"), int(outw.sum()), lat[i] / 1e3, cpu[i], ts[i] - t0, nh, ph, wall,
            "in flush" if ph <= wall else "outside", int(m20.sum()), int((m20 & (cpu == 0)).sum()),
            ", ".join("%.2f" % (x - t0) for x in sorted(ts[m20])[:6])))
print("    probes of 100 ms or more in the whole logs: %d of %d" % (allover100, rows_total))
for c in CELLS:
    ls = [x for x in P["legs"] if (x["shape"], x["arm"]) == c]
    w = []
    for l in ls:
        r = load(l)
        outw = (r["ts"] < l["t0"]) | (r["ts"] > l["t1"])
        w.append(r["lat"][outw].max() / 1e3)
    print("    %-14s worst outside the window per leg, ms: %s" % (cell_name(c), " ".join("%.1f" % x for x in w)))

print()
print("F3. ADMIN WAIT, probe intended inside a burst [start, end], no guard (primary set)")
for c in CELLS:
    waits = []
    for l in primary(c):
        r = load(l)
        a = r["pr"]["a"]
        ats = a[:, 2] / 1e9
        aw = (a[:, 4] - a[:, 2]) / 1e6
        for b in l["whole"]:
            m = (ats >= b["start"]) & (ats <= b["end"])
            waits.extend(aw[m].tolist())
    print("    %-14s n %4d median %.0f ms max %.0f ms" % (cell_name(c), len(waits), np.median(waits), max(waits)))

print()
print("F9. ADMIN probes sent from start + 20 ms to end - 100 ms: answered more than 50 / 20 / 10 ms before the burst end (primary set)")
f9_sent = f9_e20 = 0  # the no-sink and statsd cells together (the OTLP flush answers during its burst)
for c in CELLS:
    n = e50 = e20 = e10 = 0
    lead = []
    for l in primary(c):
        r = load(l)
        a = r["pr"]["a"]
        ats = a[:, 2] / 1e9
        ad = a[:, 4] / 1e9
        for b in l["whole"]:
            m = (ats >= b["start"] + 0.02) & (ats <= b["end"] - 0.1)
            n += int(m.sum())
            e50 += int((ad[m] < b["end"] - 0.05).sum())
            e20 += int((ad[m] < b["end"] - 0.02).sum())
            e10 += int((ad[m] < b["end"] - 0.01).sum())
            lead.extend(((b["end"] - ad[m]) * 1e3).tolist())
    print("    %-14s sent %4d; answered >50 ms before the end %d, >20 ms %d, >10 ms %d; answer time before the burst end: median %.1f ms, max %.1f ms" % (
        cell_name(c), n, e50, e20, e10, np.median(lead), max(lead)))
    if "otlp" not in cell_name(c):
        f9_sent += n
        f9_e20 += e20
print("    no-sink and statsd cells together: sent %s; answered more than 20 ms before the burst end: %d" % (
    "{:,}".format(f9_sent), f9_e20))

print()
print("F13. REQUESTS THAT WAITED FOR THEIR OWN CONNECTION, in the window (primary set)")
tot = 0
longest = 0.0
for c in CELLS:
    k = 0
    for l in primary(c):
        r = load(l)
        d = r["d"]
        conn, seq, intended, sent, done = d[:, 0], d[:, 1], d[:, 2], d[:, 3], d[:, 4]
        order = np.lexsort((seq, conn))
        oc, od, oi = conn[order], done[order], intended[order]
        prev = np.full(len(d), -1, dtype=np.int64)
        prev[1:] = np.where(oc[1:] == oc[:-1], od[:-1], -1)
        inw = (oi / 1e9 >= l["t0"]) & (oi / 1e9 <= l["t1"])
        q = (prev > oi) & inw
        k += int(q.sum())
        if q.any():
            longest = max(longest, float(((prev - oi)[q]).max() / 1e6))
    tot += k
    print("    %-14s %d" % (cell_name(c), k))
print("    total %d; longest wait for the connection %.1f ms" % (tot, longest))

print()
print("F4. SLOW EVENTS, the 20 legs of the complete rounds only (exploratory)")
print("    probe in the used span over 5 ms; probes of ONE worker closer than 25 ms (intended time) are one event.")
print("    Definition A: any such group (one probe is enough). Definition B: the group spans at least 2 of the worker's 4 connections.")
print("    In the shared-core cells the worker on CPU 0 is left out (its in-flush delay is the L3 effect); own-core cells count all 4 workers.")
print("    in = first probe of the event inside [start - 20 ms, end] of a whole flush; out = outside every flush zone [start - 20 ms, end + 250 ms]; else post.")


def events(l, min_conns):
    r = load(l)
    ts, lat, cpu, conn = r["ts"], r["lat"], r["cpu"], r["d"][:, 0]
    t0, t1 = l["t0"], l["t1"]
    span = (ts >= t0 + lib.EDGE) & (ts <= t1 - lib.EDGE)
    zones = [(b["start"] - lib.GUARD, b["end"] + lib.POST) for b in l["bursts_all"]]
    inz = [(b["start"] - lib.GUARD, b["end"]) for b in l["whole"]]
    s_in = sum(e - a for a, e in inz)
    s_out = (t1 - t0 - 2 * lib.EDGE) - sum(min(e, t1 - lib.EDGE) - max(a, t0 + lib.EDGE) for a, e in zones if e > t0 + lib.EDGE and a < t1 - lib.EDGE)
    ev = []
    workers = [1, 2, 3] if l["shape"] == "shared" else [0, 1, 2, 3]
    for w in workers:
        idx = np.flatnonzero(span & (cpu == w) & (lat > 5000))
        idx = idx[np.argsort(ts[idx])]
        if len(idx) == 0:
            continue
        groups = [[idx[0]]]
        for i in idx[1:]:
            if ts[i] - ts[groups[-1][-1]] <= 0.025:
                groups[-1].append(i)
            else:
                groups.append([i])
        for g in groups:
            if len(set(conn[g].tolist())) < min_conns:
                continue
            tg = ts[g[0]]
            where = "out"
            rel = None
            for b in l["whole"]:
                if b["start"] - lib.GUARD <= tg <= b["end"]:
                    where = "in"
                    rel = (tg - b["start"]) * 1e3
            if where == "out" and any(a <= tg <= e for a, e in zones):
                where = "post"
            ev.append({"where": where, "rel": rel, "peak": float(lat[g].max() / 1e3), "w": w})
    return ev, s_in * len(workers), s_out * len(workers)


for name, mc in (("A (any group)", 1), ("B (2 or more connections)", 2)):
    print("    definition %s" % name)
    agg = {}
    for c in CELLS:
        n_in = n_out = n_post = n_start = 0
        ws_in = ws_out = 0.0
        peaks = []
        for l in primary(c):
            ev, a, b = events(l, mc)
            ws_in += a
            ws_out += b
            for e in ev:
                peaks.append(e["peak"])
                if e["where"] == "in":
                    n_in += 1
                    if e["rel"] is not None and e["rel"] <= 50:
                        n_start += 1
                elif e["where"] == "out":
                    n_out += 1
                else:
                    n_post += 1
        agg[c] = (n_in, n_out, n_post, n_start, ws_in, ws_out)
        p = sst.binomtest(n_in, n_in + n_out, ws_in / (ws_in + ws_out)).pvalue if n_in + n_out else math.nan
        print("      %-14s events %2d: in %2d (within 50 ms of a start: %d), out %2d, post %d; worker-seconds in %.0f, out %.0f; per worker-hour in %.0f, out %.0f; expected in %.1f; binomial p %.2f; peak max %.1f ms" % (
            cell_name(c), n_in + n_out + n_post, n_in, n_start, n_out, n_post, ws_in, ws_out,
            3600 * n_in / ws_in, 3600 * n_out / ws_out, (n_in + n_out) * ws_in / (ws_in + ws_out), p, max(peaks) if peaks else math.nan))
    for label, cs in (("own-core cells", CELLS[:3]), ("shared-core cells, workers 1 to 3", CELLS[3:]), ("all five cells", CELLS)):
        n_in = sum(agg[c][0] for c in cs)
        n_out = sum(agg[c][1] for c in cs)
        n_st = sum(agg[c][3] for c in cs)
        wi = sum(agg[c][4] for c in cs)
        wo = sum(agg[c][5] for c in cs)
        p2 = sst.binomtest(n_in, n_in + n_out, wi / (wi + wo)).pvalue
        p3 = sst.binomtest(n_in - n_st, n_in - n_st + n_out, wi / (wi + wo)).pvalue
        print("      %-34s in %2d, out %2d; per worker-hour in %.0f, out %.0f; expected in %.1f; binomial two-sided p %.2f | without the %d within 50 ms of a start: in %d, per worker-hour %.0f, p %.2f" % (
            label, n_in, n_out, 3600 * n_in / wi, 3600 * n_out / wo, (n_in + n_out) * wi / (wi + wo), p2, n_st, n_in - n_st, 3600 * (n_in - n_st) / wi, p3))

print()
print("F4b. WHAT THE EVENTS ARE (definition A, the 20 legs of the complete rounds): scheduler counters of that worker's thread in the 55 ms around the event")
kinds = {"wait": 0, "flat": 0, "neither": 0}
waits, peaks, alone, total = [], [], 0, 0
for c in CELLS:
    for l in primary(c):
        r = load(l)
        ts, lat, cpu, conn = r["ts"], r["lat"], r["cpu"], r["d"][:, 0]
        main = r["main"]
        tid_of = {info["cpus"]: tid for tid, info in main["threads"].items() if info["comm"].startswith("wrk:")}
        t0, t1 = l["t0"], l["t1"]
        span = (ts >= t0 + lib.EDGE) & (ts <= t1 - lib.EDGE)
        for w in ([1, 2, 3] if l["shape"] == "shared" else [0, 1, 2, 3]):
            idx = np.flatnonzero(span & (cpu == w) & (lat > 5000))
            idx = idx[np.argsort(ts[idx])]
            if len(idx) == 0:
                continue
            groups = [[idx[0]]]
            for i in idx[1:]:
                if ts[i] - ts[groups[-1][-1]] <= 0.025:
                    groups[-1].append(i)
                else:
                    groups.append([i])
            for g in groups:
                total += 1
                peaks.append(lat[g].max() / 1e3)
                tg = ts[g[0]]
                oth = span & (cpu != w) & (ts >= tg - 0.01) & (ts <= ts[g[-1]] + 0.01) & (lat > 5000)
                alone += int(not oth.any())
                a = np.asarray(main["series"][tid_of[str(w)]], dtype=np.float64)
                i = int(np.searchsorted(a[:, 0], tg))
                lo, hi = max(i - 2, 0), min(i + 9, len(a) - 1)
                wsum = (a[hi, 2] - a[lo, 2]) / 1e6
                runs = np.diff(a[lo:hi + 1, 1]) / 1e6
                flat = any(all(runs[j + q] >= 4.5 for q in range(3)) for j in range(max(len(runs) - 2, 0)))
                if wsum >= 5.0:
                    kinds["wait"] += 1
                    waits.append(wsum)
                elif flat:
                    kinds["flat"] += 1
                else:
                    kinds["neither"] += 1
print("    events %d; peak ms median %.1f, max %.1f; no other worker slow within 10 ms: %d; run-queue wait of 5 ms or more: %d (median %.1f ms, max %.1f); worker ran flat out 15 ms: %d; neither: %d" % (
    total, np.median(peaks), max(peaks), alone, kinds["wait"], np.median(waits), max(waits), kinds["flat"], kinds["neither"]))
tot_c = sum(int(((load(l)["pr"]["c"][:, 4] - load(l)["pr"]["c"][:, 2]) / 1e3 > 5000).sum()) for c in CELLS for l in primary(c))
nc = sum(len(load(l)["pr"]["c"]) for c in CELLS for l in primary(c))
print("    control stream, the same 20 legs, whole logs: over 5 ms %d of %d" % (tot_c, nc))
