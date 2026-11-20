#!/usr/bin/env python3
"""Request latency in the loaded legs of the stats-flush row, per sink arm.

    python3 latency.py [S_SESSION_DIR [W_RUN_DIR]] > latency.txt

Reads the load generator's own JSON output per leg (nighthawk/<leg>.json or .json.gz: the `global` result,
statistic benchmark_http_client.request_to_response, an HdrHistogram percentile list over the
whole 28 s client run) and legs.jsonl for validity, rounds and the main-thread flush figures.
Run S loaded rung: SESSION/sw (arms nosink, nosink-A2, statsd, dogstatsd-buf, otlp; reference
nosink). Run W: W_RUN_DIR (arms flush-off, flush-off-A2, nosink, statsd; reference
flush-off). Paired by round; percentiles as log ratios with a 95% t interval, tail counts and
the maximum as paired differences. No harness import.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_lib as A  # noqa: E402

SESSION = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "..", "data", "stats", "sink-types")
WDIR = sys.argv[2] if len(sys.argv) > 2 else os.path.join(SESSION, "..", "sink-flush-cost", "w")
QS = [("p50", 0.5), ("p90", 0.9), ("p99", 0.99), ("p99.9", 0.999), ("p99.99", 0.9999)]
THR_MS = [1.0, 2.0, 5.0, 10.0, 20.0]
STAT = "benchmark_http_client.request_to_response"


def dur(s):
    return float(s.rstrip("s")) * 1e3  # ms


def load_legs(rundir):
    recs, sup = [], set()
    for line in open(os.path.join(rundir, "legs.jsonl")):
        if not line.strip():
            continue
        r = json.loads(line)
        if "arm" not in r:
            ids = set(r.get("supersede") or [])
            sup |= {i for i, p in enumerate(recs) if p["leg_id"] in ids}
            continue
        recs.append(r)
    return [r for i, r in enumerate(recs) if i not in sup and r["verdict"]["valid"]]


def read_json(path):
    """A JSON file, stored as it was written or gzip-compressed (path + ".gz")."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    import gzip as _gzip
    with _gzip.open(path + ".gz", "rt") as f:
        return json.load(f)


def client(rundir, m):
    d = read_json(os.path.join(rundir, "nighthawk", m["leg_id"] + ".json"))
    g = [r for r in d["results"] if r["name"] == "global"][0]
    s = [x for x in g["statistics"] if x["id"] == STAT][0]
    pts = [(p["percentile"], dur(p["duration"]), int(p["count"])) for p in s["percentiles"]]
    n = int(s["count"])
    out = {"n": n, "max": dur(s["max"]), "mean": dur(s["mean"]), "points": len(pts),
           "duration_s": float(g["execution_duration"].rstrip("s")), "start": g["execution_start"]}
    for name, q in QS:
        out[name] = next(d_ for p_, d_, c_ in pts if p_ >= q)
    for t in THR_MS:
        # requests slower than t ms: all minus the largest cumulative count at a duration <= t
        below = max([c for _, d_, c in pts if d_ <= t] or [0])
        out["gt%g" % t] = n - below
    # per client worker: the slowest request seen by each of the 16 workers
    out["worker_max"] = [dur([x for x in r["statistics"] if x["id"] == STAT][0]["max"])
                         for r in d["results"] if r["name"] != "global"]
    qc = [x for x in g["statistics"] if x["id"] == "benchmark_http_client.queue_to_connect"][0]
    out["queue_max"] = dur(qc["max"])
    # what else the file holds, for the "what was recorded" statement
    out["stat_ids"] = sorted(x["id"] for x in g["statistics"] if int(x.get("count", 0) or 0) > 0)
    out["result_names"] = len(d["results"])
    return out


def ci(t, f="%.3f"):
    return (f + " [" + f + ", " + f + "]") % (t["mean"], t["lo"], t["hi"])


def run(rundir, ref, aa, arms, title):
    legs = load_legs(rundir)
    print("\n" + "=" * 110)
    print("%s  (%s)  reference %s, A/A %s" % (title, os.path.relpath(rundir, SESSION), ref, aa))
    data = {}
    for m in legs:
        c = client(rundir, m)
        # the harness's summary must be the same histogram
        lu = m["latency_us"]
        assert abs(lu["p99"] / 1e3 - c["p99"]) < 1e-6 and lu["count"] == c["n"], m["leg_id"]
        c["flush_ms"] = m["main"].get("burst_run_ms_mean")
        c["stall_max"] = m["main"].get("stall_ms_max")
        c["bursts"] = m["main"].get("bursts")
        c["busy"] = m["sut_busy"]
        data.setdefault(m["arm"], {})[m["round"]] = c
    one = next(iter(data[ref].values()))
    print("recorded per leg: %d results (16 client workers + global); statistics with samples: %s" % (one["result_names"], one["stat_ids"]))
    print("percentile list: %d points per statistic; one histogram over the whole client run of %.0f s (%d requests); no per-interval output" % (
        one["points"], one["duration_s"], one["n"]))
    order = [ref, aa] + arms
    print("\n-- per arm, mean over rounds of the leg values (ms); max = slowest single request in any leg")
    print("   %-14s %2s %7s %7s %7s %7s %7s %8s %9s  %s" % ("arm", "n", "p50", "p90", "p99", "p99.9", "p99.99", "max mean", "max worst", "requests per leg slower than " + ", ".join("%g ms" % t for t in THR_MS)))
    for a in order:
        d = data[a]
        rs = sorted(d)
        print("   %-14s %2d %7.3f %7.3f %7.3f %7.3f %7.3f %8.2f %9.2f  %s" % (
            a, len(rs), *[A.mean([d[r][k] for r in rs]) for k, _ in QS], A.mean([d[r]["max"] for r in rs]),
            max(d[r]["max"] for r in rs), "  ".join("%.1f" % A.mean([d[r]["gt%g" % t] for r in rs]) for t in THR_MS)))
    print("\n-- main-thread flush under load, and what it could reach if every request arriving during a flush waited for it")
    for a in order:
        d = data[a]
        rs = sorted(d)
        f = A.mean([d[r]["flush_ms"] or 0.0 for r in rs])
        nb = sorted({d[r]["bursts"] for r in rs})
        share = f / 5000.0
        print("   %-14s flush burst %.0f ms mean (stall max %.0f ms), bursts in window %s, busy %.1f%%: %.2f%% of a 5 s period -> "
              "visible from p%.2f upward; about %.0f requests per 28 s client run arrive during a flush" % (
                  a, f, max(d[r]["stall_max"] or 0 for r in rs), nb, 100 * A.mean([d[r]["busy"] for r in rs]),
                  100 * share, 100 * (1 - share), one["n"] * share))
    print("\n-- paired by round against %s: percentiles as %% change [95%% t interval]" % ref)
    for a in [aa] + arms:
        rs = sorted(set(data[a]) & set(data[ref]))
        parts = []
        for k, _ in QS:
            r = A.log_ratio([data[a][x][k] for x in rs], [data[ref][x][k] for x in rs])
            parts.append("%s %+.1f%% [%+.1f, %+.1f]" % (k, r["eff"], r["lo"], r["hi"]))
        print("   %-14s n=%d  %s" % (a, len(rs), ";  ".join(parts)))
    print("\n-- paired by round against %s: absolute differences [95%% t interval]" % ref)
    for a in [aa] + arms:
        rs = sorted(set(data[a]) & set(data[ref]))
        parts = []
        for k, _ in QS:
            parts.append("%s %s us" % (k, ci(A.t_int([1e3 * (data[a][x][k] - data[ref][x][k]) for x in rs]), "%+.0f")))
        parts.append("max %s ms" % ci(A.t_int([data[a][x]["max"] - data[ref][x]["max"] for x in rs]), "%+.2f"))
        print("   %-14s %s" % (a, ";  ".join(parts)))
        parts = []
        for t in THR_MS:
            parts.append("> %g ms: %s" % (t, ci(A.t_int([data[a][x]["gt%g" % t] - data[ref][x]["gt%g" % t] for x in rs]), "%+.1f")))
        print("   %-14s requests per leg (of %d): %s" % ("", one["n"], ";  ".join(parts)))
    print("\n-- slowest request per leg (ms), by round, and the client's own queue-to-connect maximum")
    for a in order:
        d = data[a]
        rs = sorted(d)
        print("   %-14s max %s | queue-to-connect max %.1f | workers whose own max is over 5 ms, per leg: %s" % (
            a, " ".join("%.1f" % d[r]["max"] for r in rs), max(d[r]["queue_max"] for r in rs),
            " ".join("%d" % sum(1 for w in d[r]["worker_max"] if w > 5.0) for r in rs)))
    return data


run(os.path.join(SESSION, "sw"), "nosink", "nosink-A2", ["statsd", "dogstatsd-buf", "otlp"],
    "RUN S loaded rung (100k stats, 5 s interval, 5,200 req/s)")
if os.path.exists(os.path.join(WDIR, "legs.jsonl")):
    run(WDIR, "flush-off", "flush-off-A2", ["nosink", "statsd"], "RUN W (2026-11-18; 100k stats, 5 s interval, 5,200 req/s)")

# what else is time-resolved in the leg records
legs = load_legs(os.path.join(SESSION, "sw"))
m = [x for x in legs if x["arm"] == "statsd"][0]
print("\n" + "=" * 110)
print("time-resolved data in a loaded leg (r%02d statsd):" % m["round"])
print("   raw main-thread series kept: %s (idle runs keep main/<leg>.json.gz)" % os.path.isdir(os.path.join(SESSION, "sw", "main")))
print("   main summary keys: %s" % sorted(m["main"]))
print("   discard sink uptime samples (wall clock s, server.uptime): %d, first %s, last %s" % (
    len(m["udpsink"]["uptime_samples"]), m["udpsink"]["uptime_samples"][0], m["udpsink"]["uptime_samples"][-1]))
print("   latency fields in the leg record: %s" % sorted(m["latency_us"]))
