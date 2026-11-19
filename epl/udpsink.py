"""UDP discard sink for the statsd arms of the stats row. Standalone (stdlib only), run by the
harness as its own pinned child process:

    python3 udpsink.py --port 8125 --rcvbuf 268435456 --out FILE [--sample-every 1000]

It only drains: large recv_into reads into one buffer, counting datagrams, bytes and
newlines, with no per-line parsing. One datagram in `sample_every` (default every one: the
unbuffered statsd sink sends the uptime gauge as a datagram of its own) is scanned in C for a
`server.uptime` line, and only a hit is decoded (the flush clock; recorded, never gated). It asks for a receive
buffer of `rcvbuf` bytes and records what the kernel granted (the kernel caps the request at
net.core.rmem_max). The sink's evidence is the kernel's counters, read by the harness; these
counts are the receiver's own view. On SIGTERM it writes its counts as JSON to FILE and exits.

With --classes (run L only; without it the sink behaves as in every earlier run: no classing, and
it stops reading at the stop signal): every datagram is also classed by its last byte (`c` counter, `g` gauge, `s` for an `ms`
timer line, `h`, anything else `other`; a trailing newline is skipped), and at each
`server.uptime` hit a mark is appended: [monotonic_ns, uptime, cumulative c, g, ms, datagrams],
so the lines between two marks are one flush as the receiver saw it. On SIGTERM the socket is
drained until it has been quiet for 0.5 s (bounded by --drain-s) before the counts are
written; `drain_quiet` says whether the quiet was reached.
"""

import argparse
import json
import re
import signal
import socket
import sys
import time

UPTIME_RE = re.compile(rb"server\.uptime:([0-9.]+)\|g")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--rcvbuf", type=int, default=268435456)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample-every", type=int, default=1)
    ap.add_argument("--classes", action="store_true")
    ap.add_argument("--drain-s", type=float, default=8.0)
    a = ap.parse_args(argv)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, a.rcvbuf)
    granted = s.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    s.bind(("127.0.0.1", a.port))
    s.settimeout(0.5)
    st = {"port": a.port, "rcvbuf_requested": a.rcvbuf, "rcvbuf_granted": granted, "datagrams": 0, "bytes": 0,
          "newlines": 0, "uptime_samples": [], "started": time.time()}
    classes = a.classes
    marks = []
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    buf = bytearray(65536)
    view = memoryview(buf)
    ready = a.out + ".ready"
    with open(ready, "w") as f:
        f.write(json.dumps({"rcvbuf_granted": granted}))
    k = 0
    # datagrams by their last byte: c, g, s (ms), h, other
    cls = [0] * 256
    drain_end = None
    quiet = False
    while True:
        if stop and drain_end is None:
            if not classes:
                break
            drain_end = time.monotonic() + a.drain_s
            st["datagrams_at_stop"] = st["datagrams"]
        if drain_end is not None and time.monotonic() > drain_end:
            break
        try:
            n = s.recv_into(buf)
        except socket.timeout:
            if drain_end is not None:
                quiet = True   # 0.5 s without a datagram after the stop: the queue is empty
                break
            continue
        except InterruptedError:
            continue
        st["datagrams"] += 1
        st["bytes"] += n
        st["newlines"] += buf.count(b"\n", 0, n)
        if classes and n:
            last = buf[n - 1]
            if last == 10 and n > 1:
                last = buf[n - 2]
            cls[last] += 1
        k += 1
        if k >= a.sample_every:
            k = 0
            # a C-level scan of the datagram; only a hit is decoded
            i = buf.find(b"server.uptime:", 0, n)
            if i >= 0 and len(st["uptime_samples"]) < 10000:
                m = UPTIME_RE.search(bytes(view[i:n]))
                if m:
                    st["uptime_samples"].append([round(time.time(), 3), float(m.group(1))])
                    if classes:
                        marks.append([time.monotonic_ns(), float(m.group(1)), cls[99], cls[103], cls[115],
                                      st["datagrams"]])
    st["stopped"] = time.time()
    if classes:
        st["marks"] = marks
        st["classes"] = {"c": cls[99], "g": cls[103], "ms": cls[115], "h": cls[104],
                         "other": st["datagrams"] - cls[99] - cls[103] - cls[115] - cls[104]}
        st["drain_quiet"] = quiet
        st["drained_datagrams"] = st["datagrams"] - st.get("datagrams_at_stop", st["datagrams"])
        st["clock_end"] = {"monotonic_ns": time.monotonic_ns(), "time_ns": time.time_ns()}
    with open(a.out, "w") as f:
        json.dump(st, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
