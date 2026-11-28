#!/usr/bin/env python3
"""The PID ledger: every process a chain, `epl run` or flipblock.py starts is
written down with its start time, so the chain's EXIT trap signals only PIDs it can verify.

    ledger.py record LEDGER ROLE PID     append {role, pid, start_ticks, utc} (start ticks: /proc/<pid>/stat field 22)
    ledger.py stop LEDGER...             for every entry whose PID is still the same process (same start ticks):
                                            one SIGTERM, up to 10 s, then SIGKILL; prints what it did; rc 0 when none is
                                            left. A PID whose start ticks differ is a different process: never signalled
    ledger.py alive LEDGER...            rc 1 and the list when any verified entry is still running

The rc contract callers test (`if ledger.py alive ...; then <none running>`):
    alive   rc 0: no verified entry is running (an empty or missing ledger included); rc 1: at least one verified
            entry is still running (each printed), or a usage error (main exits with this text, rc 1)
    stop    rc 0: none is left; rc 1: an entry would not stop
    record  rc 0: recorded

Nothing is matched by name or command line."""
import json
import os
import signal
import sys
import time


# the /proc root: always /proc on the box; EPL_LEDGER_PROC_ROOT points the probe at a fake tree in tests (macOS has
# no /proc), so a ledger check can run end to end there
PROC = os.environ.get("EPL_LEDGER_PROC_ROOT") or "/proc"


def ticks(pid):
    try:
        with open(os.path.join(PROC, "%d" % int(pid), "stat")) as f:
            return int(f.read().rsplit(")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def entries(paths):
    out = []
    for p in paths:
        try:
            with open(p) as f:
                for ln in f:
                    ln = ln.strip()
                    if ln:
                        try:
                            out.append(json.loads(ln))
                        except ValueError:
                            pass
        except OSError:
            pass
    return out


def verified(e):
    """The entry still names the process it recorded (alive, same start ticks; a zombie counts as gone)."""
    t = ticks(e.get("pid", -1))
    if t is None or e.get("start_ticks") is None or t != e["start_ticks"]:
        return False
    try:
        with open(os.path.join(PROC, "%d" % int(e["pid"]), "stat")) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def record(path, role, pid):
    with open(path, "a") as f:
        f.write(json.dumps({"role": role, "pid": int(pid), "start_ticks": ticks(pid),
                            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
    return 0


def stop(paths, grace_s=10.0):
    live = [e for e in entries(paths) if verified(e)]
    for e in live:
        try:
            os.kill(int(e["pid"]), signal.SIGTERM)
            print("ledger: SIGTERM %s pid %d" % (e.get("role"), e["pid"]))
        except OSError:
            pass
    end = time.monotonic() + grace_s
    while time.monotonic() < end and any(verified(e) for e in live):
        time.sleep(0.2)
    left = []
    for e in live:
        if verified(e):
            try:
                os.kill(int(e["pid"]), signal.SIGKILL)
                print("ledger: SIGKILL %s pid %d" % (e.get("role"), e["pid"]))
            except OSError:
                pass
            time.sleep(0.2)
            if verified(e):
                left.append(e)
    print("ledger: %d verified process(es) were running; %d left" % (len(live), len(left)))
    return 1 if left else 0


def alive(paths):
    live = [e for e in entries(paths) if verified(e)]
    for e in live:
        print("ledger: still running: %s pid %d" % (e.get("role"), e["pid"]))
    return 1 if live else 0


def main(argv):
    if len(argv) == 4 and argv[0] == "record":
        return record(argv[1], argv[2], argv[3])
    if len(argv) >= 2 and argv[0] == "stop":
        return stop(argv[1:])
    if len(argv) >= 2 and argv[0] == "alive":
        return alive(argv[1:])
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
