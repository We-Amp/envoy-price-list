#!/usr/bin/env python3
"""The event log: one line per event, `<utc_iso_ms> <monotonic_ns> <event> <detail>`, both clocks
read together (one clock pair per line).

    evlog.py FILE EVENT [DETAIL...]

Details use role names ("box", "workstation", "build host") and paths relative to the run directory, never host names or
home paths: a detail holding the home directory or this host's name is refused (rc 2), so trimmed excerpts
are safe to publish by construction."""
import os
import socket
import sys
import time


def line(event, detail=""):
    mono = time.monotonic_ns()
    wall = time.time_ns()
    iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(wall // 10 ** 9)) + ".%03dZ" % (wall // 10 ** 6 % 1000)
    return "%s %d %s %s" % (iso, mono, event, " ".join(str(detail).split()))


def unsafe(text):
    home = os.path.expanduser("~")
    host = socket.gethostname().split(".")[0]
    bad = []
    if home and home != "/" and home in text:
        bad.append("the home path")
    if host and len(host) > 2 and host.lower() in text.lower():
        bad.append("the host name")
    return bad


def main(argv):
    if len(argv) < 2 or not argv[1] or " " in argv[1]:
        sys.exit(__doc__)
    detail = " ".join(argv[2:])
    bad = unsafe(detail)
    if bad:
        sys.stderr.write("evlog: refused, the detail names %s (use role names and run-relative paths)\n"
                         % " and ".join(bad))
        return 2
    with open(argv[0], "a") as f:
        f.write(line(argv[1], detail) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
