#!/usr/bin/env python3
"""Stand-in nighthawk_client for the loop's local tests: it keeps Nighthawk's contract for a `--no-duration` run (runs
until one SIGTERM, then prints its JSON output and exits 0), with per-worker execution times and
sequencer.blocking 0. It sends no traffic: the stand-in Envoy counts its own 2xx. Each worker result carries its
own upstream_rq_total (Nighthawk omits zero counters, so the per-worker overflow gate reads an absent overflow counter as 0 only then); the
environment variable EPL_STANDIN_CLIENT_OVERFLOW=worker_<i>:<n> gives that worker n pool overflows (the gate's tests)."""
import datetime
import json
import os
import signal
import sys
import time

args = sys.argv[1:]
workers = int(args[args.index("--concurrency") + 1]) if "--concurrency" in args else 1
stop = {"t": None}
signal.signal(signal.SIGTERM, lambda *a: stop.__setitem__("t", time.time()))


def iso(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


t0 = time.time()
while stop["t"] is None and time.time() < t0 + 3600:
    time.sleep(0.01)
d = "%.6fs" % ((stop["t"] or time.time()) - t0)
res = [{"name": "global", "execution_start": iso(t0), "execution_duration": d, "statistics": [],
        "counters": [{"name": "benchmark.http_2xx", "value": "1000"}, {"name": "upstream_cx_total", "value": "8"},
                     {"name": "graceful_stop_requested", "value": str(workers)}]}]
hot = (os.environ.get("EPL_STANDIN_CLIENT_OVERFLOW") or "").split(":")


def wcounters(i):
    c = [{"name": "upstream_rq_total", "value": str(1000 // workers)}]
    if len(hot) == 2 and hot[0] == "worker_%d" % i:
        c.append({"name": "benchmark.pool_overflow", "value": hot[1]})
    return c


res += [{"name": "worker_%d" % i, "execution_start": iso(t0), "execution_duration": d,
         "statistics": [{"id": "sequencer.blocking", "count": "0"}], "counters": wcounters(i)} for i in range(workers)]
print(json.dumps({"results": res}))
