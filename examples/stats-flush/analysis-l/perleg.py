"""Stage 1: one record per leg from the raw files -> perleg.json (read by analyze.py)."""
import datetime
import json
import math
import os
import sys

import numpy as np

import lib

STALLS_MS = [0.5, 1, 2, 3, 5, 10, 20]


def wall_ns(s):
    # "2026-11-19T22:36:29.061505Z"
    d = datetime.datetime.strptime(s[:26].rstrip("Z"), "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc)
    return int(d.timestamp() * 1e9 + 0.5)


def thread_rates(series, ranges):
    a = np.asarray(series, dtype=np.float64)
    t = a[:, 0]
    run = wait = sec = 0.0
    for lo, hi in ranges:
        i = int(np.searchsorted(t, lo, "left"))
        j = int(np.searchsorted(t, hi, "right")) - 1
        if j > i:
            run += a[j, 1] - a[i, 1]
            wait += a[j, 2] - a[i, 2]
            sec += t[j] - t[i]
    if sec <= 0:
        return {"run_ms_per_s": math.nan, "wait_ms_per_s": math.nan, "s": 0.0}
    return {"run_ms_per_s": run / 1e6 / sec, "wait_ms_per_s": wait / 1e6 / sec, "s": sec}


def one(rec):
    lid = rec["leg_id"]
    out = {"leg_id": lid, "round": rec["round"], "shape": rec["shape"], "arm": rec["arm"],
           "attempt": rec["attempt"], "line": rec["_line"], "started_utc": rec["started_utc"],
           "valid": bool(rec["verdict"]["valid"]), "reasons": rec["verdict"]["reasons"],
           "evidence_failed": rec["evidence"]["failed"],
           "evidence_items": len(rec["evidence"]["items"]),
           "evidence_items_failed": sum(1 for i in rec["evidence"]["items"] if not i["ok"])}
    main = lib.load_main(lid)
    t0, t1 = main["window_mono"]
    out["t0"], out["t1"] = t0, t1
    whole, allb, minor = lib.flush_windows(main, t0, t1)
    out["whole"] = whole
    out["bursts_all"] = allb
    out["minor_bursts"] = minor
    # the harness's own burst list, only to say how far my detector is from it
    hb = [b for b in main["bursts"]]
    out["harness_bursts"] = len(hb)
    hw = rec["lat"]["flush"]["whole_windows"]
    if len(hw) == len(whole):
        out["burst_edge_diff_ms"] = max(max(abs(b["start"] - t0 - h[0]), abs(b["end"] - t0 - h[1])) for b, h in zip(whole, hw)) * 1e3
    else:
        out["burst_edge_diff_ms"] = None
    starts = [b["start"] for b in whole]
    out["grid_err_ms"] = max([abs((b - a) - lib.INTERVAL) for a, b in zip(starts, starts[1:])] or [math.nan]) * 1e3

    # sampler quality
    ms = np.asarray(main["series"][str(main["main_tid"])], dtype=np.float64)
    out["sampler"] = {"n": int(len(ms)), "max_gap_ms": float(np.diff(ms[:, 0]).max() * 1e3),
                      "expected": (t1 - t0) / main["period_s"], "missing": main.get("missing"),
                      "affinity": main.get("sampler_affinity")}

    # per-thread run and wait inside flushes and outside
    in_r = [(b["start"], b["end"]) for b in whole]
    zones = sorted((b["start"] - lib.GUARD, b["end"] + lib.POST) for b in allb)
    out_r = []
    cur = t0 + lib.EDGE
    for za, zb in zones:
        if za > cur:
            out_r.append((cur, min(za, t1 - lib.EDGE)))
        cur = max(cur, zb)
    if cur < t1 - lib.EDGE:
        out_r.append((cur, t1 - lib.EDGE))
    thr = {}
    for tid, info in main["threads"].items():
        s = main["series"][tid]
        thr[info["comm"]] = {"cpus": info["cpus"], "in": thread_rates(s, in_r), "out": thread_rates(s, out_r),
                             "window": thread_rates(s, [(t0, t1)])}
    out["threads"] = thr

    # probe
    pr = lib.load_probe(lid)
    pm = pr["meta"]["meta"]["map"]
    cpu_of = {c["conn"]: c["cpus"] for c in pm["connections"]}
    out["map"] = {"per_cpu": {k: sum(1 for v in cpu_of.values() if v == k) for k in sorted(set(cpu_of.values()))},
                  "min_margin": pm["min_margin"], "opens": pm["opens"], "requests": pm["requests"],
                  "unchanged": pr["end"]["map_end"]["unchanged"]}
    gaps = [(a / 1e9, b / 1e9) for a, b in pr["end"]["gaps"]]
    out["gaps"] = [{"t": a - t0, "ms": (b - a) * 1e3,
                    "since_flush_end_ms": min([abs(a - x["end"]) for x in allb] or [math.nan]) * 1e3} for a, b in gaps]
    out["events"] = len(pr["end"]["events"])
    d = pr["d"]
    conn, seq, intended, sent, done, status = d[:, 0], d[:, 1], d[:, 2], d[:, 3], d[:, 4], d[:, 5]
    ts = intended / 1e9
    lat = (done - intended) / 1e3  # us
    cpu0 = np.array([cpu_of[int(c)] == "0" for c in conn])
    masks = lib.slice_masks(ts, whole, allb, t0, t1, gaps)
    inwin = (ts >= t0) & (ts <= t1)
    out["probe"] = {"rows": int(len(d)), "in_window": int(inwin.sum()), "expected_in_window": 800.0 * (t1 - t0),
                    "non200": int((status != 200).sum()), "unanswered": int((done < 0).sum()),
                    "answered_200": int(((status == 200) & (done > 0)).sum()),
                    "span": int(masks["span"].sum()), "gap_dropped": int(masks["gap"].sum())}
    # intended times are a fixed grid: base + phase + k * period
    grid_ok = True
    for c in np.unique(conn):
        it = intended[conn == c]
        if len(it) > 1 and not np.all(np.diff(it) == 20000000):
            grid_ok = False
    out["probe"]["intended_on_fixed_grid"] = grid_ok
    out["probe"]["sent_before_intended"] = int((sent < intended).sum())
    # lateness: sent - max(intended, previous response on the same connection)
    free = np.zeros(len(d), dtype=np.int64)
    order = np.lexsort((seq, conn))
    prev_done = np.full(len(d), -1, dtype=np.int64)
    oc, od = conn[order], done[order]
    same = np.zeros(len(d), dtype=bool)
    same[1:] = oc[1:] == oc[:-1]
    pd_sorted = np.full(len(d), -1, dtype=np.int64)
    pd_sorted[1:] = np.where(same[1:], od[:-1], -1)
    prev_done[order] = pd_sorted
    ready = np.maximum(intended, prev_done)
    late = (sent - ready) / 1e3  # us
    queued = prev_done > intended  # the previous response was still outstanding at the intended time
    lw = late[inwin]
    out["lateness"] = {"p50_us": float(np.percentile(lw, 50)), "p99_us": float(np.percentile(lw, 99)),
                       "max_us": float(lw.max()), "share_over_1ms": float(np.mean(lw > 1000.0)),
                       "queued_in_window": int((queued & inwin).sum()),
                       "queued_cpu0": int((queued & inwin & cpu0).sum()),
                       "queued_in_flush": int((queued & (masks["in"] | masks["post"] | masks["onset"])).sum()),
                       "pipelined": int(((sent < prev_done) & (prev_done > 0)).sum())}
    i = int(np.argmax(np.where(inwin, late, -1)))
    out["lateness"]["max_at"] = event(ts[i], whole, allb, t0)
    out["lateness"]["max_at"]["cpu"] = cpu_of[int(conn[i])]

    cts, st = lib.contrasts(lat, masks, cpu0)
    out["contrasts"] = cts
    groups = {"all": np.ones(len(lat), dtype=bool), "cpu0": cpu0, "others": ~cpu0}
    out["slices"] = {g: {s: lib.sstat(lat[masks[s] & gm]) for s in ("in", "onset", "post", "out")} for g, gm in groups.items()}
    out["harness_contrasts"] = rec["lat"]["contrasts"]

    # top events
    idx = np.argsort(-np.where(masks["span"], lat, -1))[:8]
    top = []
    for i in idx:
        e = event(ts[i], whole, allb, t0)
        e.update({"lat_ms": float(lat[i] / 1e3), "cpu": cpu_of[int(conn[i])], "conn": int(conn[i]),
                  "slice": next((s for s in ("in", "onset", "post", "out") if masks[s][i]), "none")})
        top.append(e)
    out["top"] = top
    # how many connections and workers are slow in the same 20 ms as the worst event (background signature)
    if len(top):
        tw = top[0]["t"] + t0
        near = (np.abs(ts - tw) <= 0.02) & (lat > 5000.0)
        out["top_companions"] = {"probes_over_5ms_within_20ms": int(near.sum()),
                                 "connections": int(len(np.unique(conn[near]))),
                                 "cpus": sorted(set(cpu_of[int(c)] for c in conn[near]))}
    # by-worker worst in flush and out of flush
    out["worst"] = {}
    for g, gm in groups.items():
        for s in ("in", "onset", "post", "out"):
            m = masks[s] & gm
            out["worst"][g + "_" + s] = float(lat[m].max() / 1e3) if m.any() else math.nan

    # sham
    sh = lib.sham_shifts(whole, allb, t0, t1)
    out["sham"] = {("%.1f" % s): lib.sham_contrast(ts, lat, cpu0, masks, wins) for s, wins in sh.items()}

    # synthetic stall at each whole flush start, every worker (sensitivity of L2 and L1), and one worker (L3)
    inj = {}
    for dms in STALLS_MS:
        dd = dms / 1e3
        add = np.zeros(len(lat))
        for b in whole:
            m = (ts >= b["start"]) & (ts < b["start"] + dd)
            add[m] = np.maximum(add[m], (b["start"] + dd - ts[m]) * 1e6)
        c_all, _ = lib.contrasts(lat + add, masks, cpu0)
        # stall in the middle of the flush instead of its start
        add2 = np.zeros(len(lat))
        for b in whole:
            mid = 0.5 * (b["start"] + b["end"])
            m = (ts >= mid) & (ts < mid + dd)
            add2[m] = (mid + dd - ts[m]) * 1e6
        c_mid, _ = lib.contrasts(lat + add2, masks, cpu0)
        c_one, _ = lib.contrasts(lat + np.where(cpu0, add2, 0.0), masks, cpu0)
        inj[str(dms)] = {"L2_p99": c_all["L2_p99"], "L1_p99_onset_stall": c_all["L1_p99"],
                         "L1_p99_mid_stall": c_mid["L1_p99"], "L3_p99_mid_stall_cpu0": c_one["L3_p99"],
                         "onset_max_ms": float((lat + add)[masks["onset"]].max() / 1e3) if masks["onset"].any() else math.nan}
    out["inject"] = inj

    # probe coverage per worker: largest gap between consecutive intended times on one worker's connections
    cov = {}
    for cpu in sorted(set(cpu_of.values())):
        m = np.array([cpu_of[int(c)] == cpu for c in conn]) & inwin
        x = np.sort(ts[m])
        cov[cpu] = float(np.diff(x).max() * 1e3)
    out["coverage_gap_ms"] = cov

    # profile since flush start (data stream), 10 ms bins around the start
    prof = {}
    if whole:
        rel = np.full(len(ts), np.nan)
        for b in whole:
            m = (ts >= b["start"] - 0.05) & (ts < b["start"] + 0.1)
            rel[m] = ts[m] - b["start"]
        for lo in range(-50, 100, 10):
            m = (rel >= lo / 1e3) & (rel < (lo + 10) / 1e3)
            if m.any():
                prof[str(lo)] = {"n": int(m.sum()), "p50": float(np.percentile(lat[m], 50)),
                                 "p99": float(np.percentile(lat[m], 99)), "max": float(lat[m].max())}
    out["profile"] = prof

    # admin stream (L4)
    a = pr["a"]
    ats = a[:, 2] / 1e9
    adone = a[:, 4]
    alat = np.where(adone > 0, (adone - a[:, 2]) / 1e6, np.nan)  # ms
    am = lib.slice_masks(ats, whole, allb, t0, t1)
    per = []
    for b in whole:
        m = (ats >= b["start"] - 0.05) & (ats <= b["end"])
        if m.any() and np.isfinite(alat[m]).any():
            mx = float(np.nanmax(alat[m]))
            # answered inside the flush: intended in IN and done at least 20 ms before the burst end
            mi = (ats >= b["start"] + lib.GUARD) & (ats <= b["end"] - 0.1)
            early = int(np.sum((adone[mi] / 1e9) < b["end"] - 0.05)) if mi.any() else 0
            per.append({"wall_ms": (b["end"] - b["start"]) * 1e3, "max_wait_ms": mx,
                        "ratio": mx / ((b["end"] - b["start"]) * 1e3), "sent_in": int(mi.sum()), "answered_before_end": early,
                        "run_ms": b["run_s"] * 1e3})
    out["admin"] = {"n": int(len(a)), "unanswered": int((adone < 0).sum()), "non200": int((a[:, 5] != 200).sum()),
                    "in": simple(alat[am["in"]]), "out": simple(alat[am["out"]]), "per_flush": per,
                    "slow_out": int(np.sum(alat[am["out"]] > 20.0)), "slow_in": int(np.sum(alat[am["in"]] > 20.0))}

    # control stream
    c = pr["c"]
    cts_ = c[:, 2] / 1e9
    clat = (c[:, 4] - c[:, 2]) / 1e3
    cm = (cts_ >= t0) & (cts_ <= t1)
    out["control"] = {"n": int(cm.sum()), "p50_us": float(np.percentile(clat[cm], 50)), "p99_us": float(np.percentile(clat[cm], 99)),
                      "max_us": float(clat[cm].max()), "over_5ms": int(np.sum(clat[cm] > 5000.0)), "over_1ms": int(np.sum(clat[cm] > 1000.0))}

    # count gate and the Nighthawk end
    lc, nh = rec["lat_count"], rec["lat_nh"]
    out["count"] = dict(lc)
    out["count"]["recomputed_error"] = lc["listener_2xx"] - nh["responses_2xx"] - out["probe"]["answered_200"] - pm["requests"]
    out["count"]["nh_requests"] = nh["requests"]
    out["count"]["nh_2xx"] = nh["responses_2xx"]
    out["count"]["reads_s"] = rec["lat_count_reads_s"]
    nj = lib.read_json(os.path.join(lib.RUN, "nighthawk", lid + ".json"))
    short = []
    g = None
    for r in nj["results"]:
        cn = {x["name"]: int(x["value"]) for x in r["counters"]}
        if r["name"] == "global":
            g = r
            out["count"]["nh_global_rq_total"] = cn.get("upstream_rq_total")
            out["count"]["nh_global_2xx"] = cn.get("benchmark.http_2xx")
            out["count"]["nh_pending_total"] = cn.get("upstream_rq_pending_total")
        else:
            miss = cn.get("upstream_rq_total", 0) - cn.get("benchmark.http_2xx", 0)
            if miss:
                short.append({"worker": r["name"], "missing": miss, "rx_bytes": cn.get("upstream_cx_rx_bytes_total")})
    out["count"]["nh_workers_short"] = short
    hc = main["harness_clock"][1]
    off = hc["time_ns"] - hc["monotonic_ns"]
    dur = float(g["execution_duration"].rstrip("s"))
    nh_start = (wall_ns(g["execution_start"]) - off) / 1e9
    nh_end = nh_start + dur
    out["count"]["nh_start_rel_t0"] = nh_start - t0
    out["count"]["nh_end_rel_t1"] = nh_end - t1
    if whole:
        starts = np.array([b["start"] for b in whole])
        period = float(np.mean(np.diff(starts))) if len(starts) > 1 else lib.INTERVAL
        ph = (nh_end - starts[-1]) % period
        out["count"]["nh_end_phase_s"] = float(ph)
        out["count"]["flush_wall_mean_s"] = float(np.mean([b["end"] - b["start"] for b in whole]))
        out["count"]["flush_wall_max_s"] = float(np.max([b["end"] - b["start"] for b in whole]))
        out["count"]["period_s"] = period
        # second estimate from the statsd receiver's uptime marks (one per flush, on the same clock)
        us = rec.get("udpsink") or {}
        marks = [m[0] / 1e9 for m in us.get("marks", [])]
        if marks:
            offs = []
            for b in whole:
                mm = [x for x in marks if b["start"] <= x <= b["end"] + 1.0]
                if mm:
                    offs.append(mm[0] - b["start"])
            out["count"]["mark_offset_s"] = [float(np.min(offs)), float(np.max(offs))] if offs else None
            before = [x for x in marks if x <= nh_end + 6.0]
            # the flush whose uptime mark is the last one at or before nh_end + its offset
            cand = [x - float(np.mean(offs)) for x in marks] if offs else []
            cand = [x for x in cand if x <= nh_end]
            out["count"]["nh_end_phase_from_marks_s"] = float(nh_end - cand[-1]) if cand else None
    # share of cpu0 probes in flush slower than the time Nighthawk's last request of a worker has (1/275 s)
    m = masks["in"] & cpu0
    out["count"]["cpu0_in_share_over_3p6ms"] = float(np.mean(lat[m] > 1e6 / 275.0)) if m.any() else math.nan
    m = masks["out"] & cpu0
    out["count"]["cpu0_out_share_over_3p6ms"] = float(np.mean(lat[m] > 1e6 / 275.0)) if m.any() else math.nan
    m = masks["in"] & ~cpu0
    out["count"]["others_in_share_over_3p6ms"] = float(np.mean(lat[m] > 1e6 / 275.0)) if m.any() else math.nan
    le = rec.get("sut_stats_leg_end") or {}
    out["count"]["downstream_cx_destroy_active_rq"] = le.get("http.ingress_http.downstream_cx_destroy_active_rq")
    out["count"]["downstream_rq_rx_reset"] = le.get("http.ingress_http.downstream_rq_rx_reset")
    out["count"]["downstream_rq_tx_reset"] = le.get("http.ingress_http.downstream_rq_tx_reset")

    # evidence, straight from the leg's raw fields
    pt = rec["perf_per_thread"]
    pw = rec["perf_window_s"]
    busy = {}
    for v in (pt.values() if isinstance(pt, dict) else pt):
        cmn = v.get("comm")
        if cmn and (cmn.startswith("wrk:") or cmn.startswith("envoy")):
            busy[cmn] = v["task-clock"] / 1e3 / pw
    out["ev"] = {
        "pin_before": rec["rung_pin"]["ok"] and rec["rung_pin"]["main_ok"], "pin_after": rec["rung_pin_after"]["ok"] and rec["rung_pin_after"]["main_ok"],
        "pin_map": rec["rung_pin"].get("one_to_one"), "main_cpu": rec["rung_main_cpu"], "pinning_ok": rec["pinning_ok"],
        "thread_last_cpu": {v["comm"]: v["last_cpu"] for v in (rec["envoy_threads"].values() if isinstance(rec["envoy_threads"], dict) else rec["envoy_threads"]) if v["comm"].startswith("wrk:") or v["comm"].startswith("envoy")},
        "migrations": rec["perf_raw"].get("cpu-migrations"),
        "perf_busy": busy, "sut_cpu_busy_pct": rec["sut_cpu_busy_pct"], "sut_busy": rec["sut_busy"],
        "client_rate_2xx": rec["client_rate_2xx"], "nh_exec_s": nh["execution_s"], "sut_rate_2xx": rec["sut_rate_2xx"],
        "client_headroom": rec["client_headroom"], "client_pending_total": rec["client_pending_total"],
        "client_q2c_max_us": rec["client_queue_to_connect_max_us"], "client_overflow": rec["client_overflow"],
        "nh_latency": rec["latency_us"], "nh_worker_max_ms": max(rec["client_worker_r2r_max_us"]) / 1e3,
        "udp_leg": rec.get("udp_leg"), "watchdog": rec.get("watchdog_delta"),
        "dropped_stat_flushes": rec.get("dropped_stat_flushes_delta"), "uptime": rec.get("uptime"),
        "stats_total": rec.get("stats_total"), "used_total": rec.get("used_total"), "used_cg_lines": rec.get("used_cg_lines"),
        "otlp_cluster": rec.get("otlp_cluster"), "collector_delta": rec.get("collector_delta"), "collector_cfg": rec.get("collector_cfg"),
        "cycles_total_per_req": rec["per_req"]["cycles_total"], "steal": rec.get("steal_share"),
        "envoy_exit": rec.get("envoy_exit"), "non2xx": rec.get("sut_non2xx"),
    }
    us = rec.get("udpsink")
    if us:
        marks = us["marks"]
        cg = [(b[2] + b[3]) - (a[2] + a[3]) for a, b in zip(marks, marks[1:])]
        dt = [(b[0] - a[0]) / 1e9 for a, b in zip(marks, marks[1:])]
        ex = rec["lat"]["statsd"]["ms_expected"]
        out["ev"]["statsd"] = {
            "classes": us["classes"], "datagrams": us["datagrams"], "marks": len(marks),
            "cg_per_flush": cg, "mark_dt": dt, "first_marks": [m[1:] for m in marks[:3]],
            "drain_quiet": us.get("drain_quiet"), "ms_lines": us["classes"]["ms"], "ms_expected": ex,
            "ms_residual": us["classes"]["ms"] - ex["total"],
            "rcvbuf_granted": us.get("rcvbuf_granted"),
            "rx_queue_max": max([q[1] for q in main.get("rx_queue", [])] or [0]),
            "ingress_cx_total": le.get("http.ingress_http.downstream_cx_total"),
            "upstream_cx_active_end": le.get("cluster.origin.upstream_cx_active"),
        }
    return out


def event(t, whole, allb, t0):
    best = None
    for b in allb:
        if b["start"] - 0.05 <= t <= b["end"] + lib.POST:
            best = b
    e = {"t": float(t - t0)}
    if best is None:
        e["flush"] = "no"
        nxt = [b["start"] - t for b in allb if b["start"] > t]
        e["to_next_start_s"] = float(min(nxt)) if nxt else None
    else:
        e["flush"] = "yes"
        e["since_start_ms"] = float((t - best["start"]) * 1e3)
        e["before_end_ms"] = float((best["end"] - t) * 1e3)
    return e


def simple(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return {"n": 0, "p50": math.nan, "max": math.nan}
    return {"n": int(len(x)), "p50": float(np.percentile(x, 50)), "p99": float(np.percentile(x, 99)), "max": float(x.max())}


def main():
    recs = lib.load_legs()
    out = {"lines": [], "legs": []}
    for r in recs:
        if "supersede" in r:
            out["lines"].append({"line": r["_line"], "supersede": r["supersede"]})
            continue
        sys.stderr.write(r["leg_id"] + "\n")
        out["legs"].append(one(r))
        out["lines"].append({"line": r["_line"], "leg": r["leg_id"]})
    dst = os.path.join(lib.OUT, "perleg.json")
    with open(dst, "w") as f:
        json.dump(out, f)
    print("wrote", dst, len(out["legs"]), "legs")


if __name__ == "__main__":
    main()
