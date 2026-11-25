#!/usr/bin/env python3
"""The state the S3 predictions rest on, read from a smoke directory, fixed before the run (plan 4.1 and
4.2, Revision 1).

    s3_check.py SMOKE_DIR     one line per leg; exit 1 when a state rule fails

Rules (the per-leg validity gates and the evidence items are the harness's own; these are on top):
  every arm       the stat count of the arm's saved /stats (stats/<arm>.txt.gz, every stat of the first leg)
                  under 2,000: no arm carries generated clusters
  statsd arms     udp.datagrams_per_request inside 2.5 to 3.5 (the workers' three histogram datagrams per
                  request; the published 4.21 minus its 1.20 of flush at 118k stats)
  other arms      no `udp` record (no sink was started)
The lines also show what the evidence items read: access-log lines per request, spans accepted, metric
points accepted, box-wide UDP datagrams sent per request, Envoy busy."""
import gzip
import json
import os
import sys

STAT_LIMIT = 2000
BAND = (2.5, 3.5)


def latest(d):
    out, sup = {}, set()
    p = os.path.join(d, "legs.jsonl")
    if not os.path.exists(p):
        return out
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        m = json.loads(line)
        if "supersede" in m:
            sup.update(m["supersede"])
        elif m.get("arm") and m.get("leg_id") not in sup:
            out[(m.get("shape"), m["arm"])] = m
    return out


def stat_count(d, arm):
    p = os.path.join(d, "stats", arm + ".txt.gz")
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt", errors="replace") as f:
        return sum(1 for line in f if ": " in line)


def statsd_arm(d, arm):
    """Whether the arm's config (experiment.json of the run directory) carries the statsd sink."""
    p = os.path.join(d, "experiment.json")
    if not os.path.exists(p):
        return None
    for a in json.load(open(p)).get("arms", []):
        if a.get("name") == arm:
            return ((a.get("settings") or {}).get("stats_sink") or {}).get("kind") == "statsd"
    return None


def check(d):
    legs = latest(d)
    rows, bad = [], []
    if not legs:
        return ["no legs in %s" % d], ["no legs"]
    for (sh, arm), m in sorted(legs.items()):
        n = stat_count(d, arm)
        dg = (m.get("udp") or {}).get("datagrams_per_request")
        sd = statsd_arm(d, arm)
        rr = m.get("responses_raw") or 0
        kn = ((m.get("kernel_net") or {}).get("d") or {}).get("UdpOutDatagrams")
        cd = m.get("collector_delta") or {}
        rows.append("%s/%s: stats %s (limit %d), statsd datagrams per request %s, box-wide UDP out per request %s, "
                    "access-log lines %s, spans accepted %s, metric points accepted %s, Envoy busy %s CPUs; valid %s, "
                    "evidence %s%s" % (
                        sh, arm, n, STAT_LIMIT, "%.3f" % dg if dg is not None else "-",
                        "%.4f" % (kn / rr) if kn is not None and rr else "-", m.get("access_log_lines", "-"),
                        cd.get("accepted_spans", "-"), cd.get("accepted_metric_points", "-"), m.get("envoy_cpus_run"),
                        (m.get("verdict") or {}).get("valid"), (m.get("evidence") or {}).get("ok"),
                        "" if (m.get("evidence") or {}).get("ok") is not False else
                        " FAILED: " + "; ".join((m["evidence"].get("failed") or [])[:6])))
        if n is None or n >= STAT_LIMIT:
            bad.append("%s/%s: %s stats (limit %d, fail closed when the saved /stats is missing)" % (sh, arm, n, STAT_LIMIT))
        if sd is None:
            bad.append("%s/%s: the arm is not in experiment.json" % (sh, arm))
        elif sd and (dg is None or not BAND[0] <= dg <= BAND[1]):
            bad.append("%s/%s: statsd datagrams per request %s outside %.1f to %.1f" % (sh, arm, dg, BAND[0], BAND[1]))
        elif not sd and m.get("udp") is not None:
            bad.append("%s/%s: a UDP sink record on an arm without the statsd sink" % (sh, arm))
    return rows, bad


def main(argv):
    rows, bad = check(argv[0].rstrip("/"))
    print("\n".join(rows))
    for b in bad:
        print("STATE RULE FAILED: " + b)
    print("s3_check %s: %s" % (os.path.basename(argv[0].rstrip("/")), "OK" if not bad else "FAILED (%d)" % len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
