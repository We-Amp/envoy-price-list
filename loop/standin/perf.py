#!/usr/bin/env python3
"""Stand-in `perf stat -I` for the loop's local tests. It refuses `--timeout` together with `-I`, as perf 6.8 does, and
ends either when its workload (`-- sleep W`) ends or at one SIGINT. Each interval's counts come from the stand-in
Envoy's /standin (cycles and instructions per request at the current runtime value) times the request rate.

    perf.py --standin-admin PORT [--standin-startup-ms MS] stat -x , -I MS -e EVENTS -p PID [-- sleep W]

Without -I it is flipblock's whole-window form (the perf-form check, `instance.py --perf-ab`): `--timeout MS` counts for MS and
then prints one total line per event (<count>,<unit>,<event>,<run>,<pct>,,), as perf stat -x , does."""
import json
import signal
import sys
import time
import urllib.request

args = sys.argv[1:]
port = int(args[args.index("--standin-admin") + 1])
if "--timeout" in args and "-I" in args:
    sys.stderr.write("timeout option is not supported with interval-print.\n")
    sys.exit(234)
events = args[args.index("-e") + 1].split(",")
startup = float(args[args.index("--standin-startup-ms") + 1]) / 1000.0 if "--standin-startup-ms" in args else 0.0


def counts(dt):
    """The stand-in Envoy's counts over dt seconds at its current runtime value, or None."""
    try:
        s = json.load(urllib.request.urlopen("http://127.0.0.1:%d/standin" % port, timeout=2))
    except OSError:
        return None
    n = s["rate"] * dt
    return {"cycles:u": 0.62 * s["cycles_per_req"] * n, "cycles:k": 0.38 * s["cycles_per_req"] * n,
            "cycles": s["cycles_per_req"] * n, "instructions:u": s["ins_per_req"] * n,
            "instructions:k": 500.0 * n, "task-clock": dt * 4000.0, "context-switches": 10.0 * dt,
            "cpu-migrations": 0.0}


if "-I" not in args:
    if "--timeout" not in args:
        sys.stderr.write("stand-in perf: -I or --timeout is required\n")
        sys.exit(129)
    dur = int(args[args.index("--timeout") + 1]) / 1000.0
    time.sleep(startup)
    time.sleep(dur)
    vals = counts(dur) or {}  # counted over exactly the timeout (a stand-in: no wake-up overshoot)
    for ev in events:
        sys.stderr.write("%.0f,,%s,%d,100.00,,\n" % (vals.get(ev, 0.0), ev, int(dur * 1e9)))
    sys.exit(0)
iv = int(args[args.index("-I") + 1]) / 1000.0
work = None
if "--" in args:
    rest = args[args.index("--") + 1:]
    if rest[:1] == ["sleep"]:
        work = float(rest[1])
stop = {"t": None}
signal.signal(signal.SIGINT, lambda *a: stop.__setitem__("t", time.monotonic()))
time.sleep(startup)  # a real perf's start-up: parsing, opening the events on every thread; -I counts from enable
t0 = time.monotonic()
end = t0 + work if work is not None else None
k = 0
last = t0


def emit(t_rel, dt):
    vals = counts(dt)
    if vals is None:
        return
    for ev in events:
        sys.stderr.write("%.9f,%.0f,,%s,%d,100.00,,\n" % (t_rel, vals.get(ev, 0.0), ev, int(dt * 1e9)))
    sys.stderr.flush()


while True:
    k += 1
    nxt = t0 + k * iv
    stop_at = min(x for x in (nxt, end, stop["t"] or nxt) if x is not None)
    while time.monotonic() < stop_at and stop["t"] is None:
        time.sleep(min(0.01, max(0.0, stop_at - time.monotonic())))
    now = time.monotonic()
    if stop["t"] is not None or (end is not None and now >= end - 1e-6):
        if now - last > 1e-3:
            emit(now - t0, now - last)
        break
    emit(now - t0, now - last)
    last = now
sys.exit(0)
