#!/usr/bin/env python3
"""Run S, second pass: silent-loss checks on the receivers and A/A-widened intervals.

    python3 extra.py [SESSION_DIR] > extra.txt

1. UDP sinks: receiver-process lifetime counts (datagrams, bytes, newlines, flushes seen through
   the sampled server.uptime lines) for statsd and dogstatsd-buf, against each other and against
   the admin's used counter+gauge count; kernel drop counters; window datagrams per flush.
2. OTLP: requests per flush against ceil(used / 10,000), http2.rx_reset, bytes written, at 100k,
   1M and under load (sw: window deltas and the leg-wide collector count).
3. Idle sink rows with the interval widened by the rung's own A/A half-width in place of 0.34
   (the rule of 2026-11-18 for a rung whose A/A misses the 2% half-width target).
"""
import gzip
import json
import math
import os
import re
import sys

from scipy import stats as sps

HERE = os.path.dirname(os.path.abspath(__file__))
SESSION = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "..", "data", "stats", "sink-types")
sys.path.insert(0, HERE)


def load(run):
    recs, sup = [], set()
    for line in open(os.path.join(SESSION, run, "legs.jsonl")):
        if not line.strip():
            continue
        r = json.loads(line)
        if "arm" not in r:
            ids = set(r.get("supersede") or [])
            sup |= {i for i, p in enumerate(recs) if p["leg_id"] in ids}
            continue
        recs.append(r)
    return [r for i, r in enumerate(recs) if i not in sup and r["verdict"]["valid"]]


def mean(xs):
    return sum(xs) / len(xs)


def rng(xs, f="%.0f"):
    return (f + " .. " + f) % (min(xs), max(xs))


print("== 1. UDP sinks: receiver-side counts")
for run in ("s-100k", "s-1m"):
    legs = load(run)
    by = {a: sorted([m for m in legs if m["arm"] == a], key=lambda m: m["round"]) for a in ("statsd", "dogstatsd-buf")}
    print("\n%s" % run)
    for a in ("statsd", "dogstatsd-buf"):
        L = by[a]
        us = [m["udpsink"] for m in L]
        # one line per datagram for statsd (no newline inside); dogstatsd joins lines with a newline
        lines = [u["datagrams"] + u["newlines"] for u in us]
        nfl = [len(u["uptime_samples"]) for u in us]
        print("  %-14s window (kernel InDatagrams): datagrams per flush %s; kernel dropped %d, RcvbufErrors %d, socket drops %d, InErrors %d" % (
            a, rng([m["udp"]["sent_per_flush"] for m in L], "%.1f"), sum(m["udp"]["dropped"] for m in L),
            sum(m["udp"]["rcvbuf_errors"] for m in L), sum(m["udp"]["socket_drops"] or 0 for m in L), sum(m["udp"]["in_errors"] for m in L)))
        print("  %-14s admin used counter+gauge count %s" % ("", sorted({m["used_cg_lines"] for m in L})))
        print("  %-14s receiver lifetime: datagrams %s; lines (datagrams + newlines) %s; bytes per line %s; bytes per datagram %s; "
              "flushes seen (uptime lines) %s; rcvbuf granted %s" % (
                  "", rng([u["datagrams"] for u in us]), rng(lines), rng([u["bytes"] / l for u, l in zip(us, lines)], "%.2f"),
                  rng([u["bytes"] / u["datagrams"] for u in us], "%.0f"), sorted(set(nfl)), sorted({u["rcvbuf_granted"] for u in us})))
        print("  %-14s receiver lifetime lines per flush seen: %s" % ("", " ".join("%.0f" % (l / n) for l, n in zip(lines, nfl))))
        by[a + ":lines"] = lines
        by[a + ":nfl"] = nfl
    s, d = by["statsd"], by["dogstatsd-buf"]
    sl, dl = by["statsd:lines"], by["dogstatsd-buf:lines"]
    print("  dogstatsd-buf lifetime lines / statsd lifetime lines, by round: %s" % " ".join("%.4f" % (b / a) for a, b in zip(sl, dl)))
    print("  mean ratio %.4f; mean lifetime lines statsd %.0f, dogstatsd-buf %.0f" % (mean(dl) / mean(sl), mean(sl), mean(dl)))
    spf = mean([m["udp"]["sent_per_flush"] for m in s])
    dpf = mean([m["udp"]["sent_per_flush"] for m in d])
    bpl = mean([u["udpsink"]["bytes"] / (u["udpsink"]["datagrams"] + u["udpsink"]["newlines"]) for u in d])
    print("  window: statsd lines per flush %.1f; dogstatsd-buf datagrams per flush %.1f -> %.2f lines per datagram if every line arrived; "
          "dogstatsd bytes per line (lifetime, without the joining newline) %.1f -> a 1432-byte datagram holds at most %d lines; "
          "implied fill %.0f bytes of 1432" % (spf, dpf, spf / dpf, bpl, int(1433 // (bpl + 1)), spf / dpf * (bpl + 1) - 1))

print("\n== 2. OTLP: requests, resets, bytes")
for run in ("s-100k", "s-1m"):
    legs = sorted([m for m in load(run) if m["arm"] == "otlp"], key=lambda m: m["round"])
    print("\n%s (leg-end counters cover the whole leg; flushes in the leg = rq_total / requests per flush)" % run)
    for m in legs:
        e = m["sut_stats_leg_end"]
        used = m["used_total"]
        per = math.ceil(used / 10000.0)
        rq = e.get("cluster.otel_collector.upstream_rq_total")
        print("  r%02d used %d -> %d requests per flush expected; rq_total %s (%.2f flushes), rq_2xx %s, http2.rx_reset %s, "
              "tx %.1f MB (%.2f MB per flush), collector points per flush %.1f = %.4f of used, refused %d" % (
                  m["round"], used, per, rq, rq / per, e.get("cluster.otel_collector.upstream_rq_2xx"),
                  e.get("cluster.otel_collector.http2.rx_reset", "absent (unused = 0)"),
                  e.get("cluster.otel_collector.upstream_cx_tx_bytes_total") / 1e6,
                  e.get("cluster.otel_collector.upstream_cx_tx_bytes_total") / 1e6 / (rq / per),
                  m["collector_delta"]["accepted_metric_points_per_flush"],
                  m["collector_delta"]["accepted_metric_points_per_flush"] / used, m["collector_delta"]["refused_metric_points"]))
    # every counter of the collector cluster that is non-zero in any leg and names a failure
    bad = {}
    for m in legs:
        for k, v in (m.get("sut_stats_window") or {}).items():
            if "otel_collector" in k and v and re.search(r"reset|fail|timeout|overflow|retry|cancel|destroy|protocol_error|[45]xx|503", k):
                bad.setdefault(k, []).append(v)
    print("  non-zero failure-type counters of cluster.otel_collector (window read): %s" % (bad or "none"))

legs = sorted([m for m in load("sw") if m["arm"] == "otlp"], key=lambda m: m["round"])
print("\nsw (loaded, 100k, 5 s)")
# used stats under load, from the arm's saved full stats dump (one per arm)
p = os.path.join(SESSION, "sw", "stats", "otlp.txt.gz")
txt = gzip.open(p, "rt").read().splitlines()
print("  sw/stats/otlp.txt.gz: %d lines (what this dump holds is not labelled used-only or all; not used as an expectation)" % len(txt))
for m in legs:
    d, e = m.get("sut_stats_delta") or {}, m.get("sut_stats_leg_end") or {}
    rq = e.get("cluster.otel_collector.upstream_rq_total")
    acc = m["collector_delta"]["accepted_metric_points"]
    fail = {k: v for k, v in list(d.items()) + list(e.items())
            if "otel_collector" in k and v and re.search(r"reset|fail|timeout|overflow|retry|cancel|protocol_error|[45]xx|503", k)}
    print("  r%02d window: %s requests in %d flushes, tx %.2f MB; leg end: rq_total %s rq_2xx %s; collector accepted %d (%.1f per request-quartet), "
          "refused %d; failure-type counters non-zero: %s" % (
              m["round"], d.get("cluster.otel_collector.upstream_rq_total"), m["flushes_counted"],
              d.get("cluster.otel_collector.upstream_cx_tx_bytes_total", 0) / 1e6, rq, e.get("cluster.otel_collector.upstream_rq_2xx"),
              acc, acc / (rq / 4.0), m["collector_delta"]["refused_metric_points"], fail or "none"))
accs = [m["collector_delta"]["accepted_metric_points"] for m in legs]
print("  accepted modulo 10,000: %s  (legs differ by whole 10,000-point requests)" % sorted({a % 10000 for a in accs}))

print("\n== 3. idle sink rows, A/A-widened (rung's A/A half-width in place of 0.34)")
import analyze_lib as A  # noqa: E402
for run, rows, aas in (("s-100k", [("statsd", "nosink"), ("dogstatsd-buf", "nosink"), ("otlp", "nosink")], {"nosink": ("nosink-A2", "nosink")}),
                       ("s-1m", [("statsd", "nosink-5s"), ("dogstatsd-buf", "nosink-5s"), ("otlp", "nosink-20s")],
                        {"nosink-5s": ("nosink-5s-A2", "nosink-5s"), "nosink-20s": ("nosink-5s-A2", "nosink-5s"), "nosink": ("nosink-A2", "nosink")})):
    legs = load(run)
    v = {}
    for m in legs:
        b = m["span_flushes"]["bursts"]
        v.setdefault(m["arm"], {})[m["round"]] = sum(x["run_ms"] for x in b) / len(b)
    hw = {}
    for ref, (a2, a1) in aas.items():
        rs = sorted(set(v[a2]) & set(v[a1]))
        r = A.log_ratio([v[a2][x] for x in rs], [v[a1][x] for x in rs])
        hw[ref] = r["hw"]
        print("  %s A/A %s vs %s: half-width %.2f log-%% (2%% target %s), reach %.2f" % (
            run, a2, a1, r["hw"], "met" if r["hw"] <= 2.0 else "missed", max(abs(r["log_lo"]), abs(r["log_hi"]))))
    for a, ref in rows:
        rs = sorted(set(v[a]) & set(v[ref]))
        r = A.log_ratio([v[a][x] for x in rs], [v[ref][x] for x in rs])
        w = max(r["hw"], 1.96 * math.sqrt(r["se"] ** 2 + hw[ref] ** 2))
        d = A.t_int([v[a][x] - v[ref][x] for x in rs])
        absm = mean([v[a][x] for x in rs])
        print("  %s %-14s vs %-10s %+.0f%% plain [%+.0f, %+.0f]; A/A-widened [%+.0f, %+.0f]; arm %.1f ms +/- %.1f%% (A/A half-width) = +/- %.1f ms; "
              "delta %+.1f ms" % (run, a, ref, r["eff"], r["lo"], r["hi"], A.pct(r["log"] - w), A.pct(r["log"] + w),
                                 absm, hw[ref], absm * hw[ref] / 100.0, d["mean"]))
