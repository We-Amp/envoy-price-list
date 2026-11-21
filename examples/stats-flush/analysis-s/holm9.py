#!/usr/bin/env python3
"""Holm over the stated family of 9 sink rows of run S.

    python3 holm9.py [SESSION_DIR] > holm9.txt

The family: statsd, dogstatsd-buf and otlp against their same-interval no-sink reference at 100k
(run S, s-100k) and at 1M (statsd and dogstatsd-buf from run S, s-1m; otlp from the re-run,
s-1m-otlp-rerun), and the three sinks under load (sw, total cycles per request). Run S's own
OTLP legs at 1M are invalid and are not in the family. Per row: paired log ratio by round on
the per-flush price (burst list re-summed) or on cycles per request; raw two-sided t-test p;
Holm step-down adjusted p. No harness import.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_lib as A  # noqa: E402

SESSION = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "..", "data", "stats", "sink-types")


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


def span(m):
    b = m["span_flushes"]["bursts"]
    return sum(x["run_ms"] for x in b) / len(b)


def cyc(m):
    return m["per_req"]["cycles_total"]


def row(run, arm, ref, f):
    legs = load(run)
    a = {m["round"]: f(m) for m in legs if m["arm"] == arm}
    r = {m["round"]: f(m) for m in legs if m["arm"] == ref}
    rs = sorted(set(a) & set(r))
    return A.log_ratio([a[x] for x in rs], [r[x] for x in rs])


FAMILY = [
    ("s-100k", "statsd", "nosink", span), ("s-100k", "dogstatsd-buf", "nosink", span), ("s-100k", "otlp", "nosink", span),
    ("s-1m", "statsd", "nosink-5s", span), ("s-1m", "dogstatsd-buf", "nosink-5s", span),
    ("s-1m-otlp-rerun", "otlp", "nosink-20s", span),
    ("sw", "statsd", "nosink", cyc), ("sw", "dogstatsd-buf", "nosink", cyc), ("sw", "otlp", "nosink", cyc),
]
rows = [row(*f) for f in FAMILY]
ps = [r["p"] for r in rows]
order = sorted(range(len(ps)), key=lambda i: ps[i])
adj, run_ = [0.0] * len(ps), 0.0
for k, i in enumerate(order):
    run_ = max(run_, min(1.0, (len(ps) - k) * ps[i]))
    adj[i] = run_
print("Holm over %d rows (alpha 0.05)" % len(rows))
print("%-16s %-14s %-11s %2s %10s %22s %10s %10s" % ("run", "arm", "reference", "n", "effect", "95% t interval", "raw p", "Holm p"))
for f, r, hp in zip(FAMILY, rows, adj):
    print("%-16s %-14s %-11s %2d %+9.2f%% [%+9.2f, %+9.2f] %10.2e %10.2e" % (f[0], f[1], f[2], r["n"], r["eff"], r["lo"], r["hi"], r["p"], hp))
print("log-scale effect over the A/A reach at the reference interval (log-%%): "
      "re-run otlp %.1f / 4.02 = %.0f; 1M dogstatsd-buf %.1f / 4.29 = %.0f" % (rows[5]["log"], rows[5]["log"] / 4.02, rows[4]["log"], rows[4]["log"] / 4.29))
