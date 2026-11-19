"""Open-loop latency probe of the flush-latency run (run L). Standalone (stdlib only), run by
the harness as its own pinned child process:

    python3 latprobe.py --listener-port P --admin-port A --origin-port O --envoy-pid PID \
        --out-log FILE.jsonl.gz --out-summary FILE.json

Three streams, every request with an intended send time fixed in advance (base + phase +
k x period, integers of CLOCK_MONOTONIC ns); latency is always done - intended:

  d  data:    N keep-alive HTTP/1.1 connections to the listener, one request per period on
              each, phases staggered. A request whose turn comes while the previous response
              is outstanding goes out when the connection frees: no pipelining, nothing
              skipped (a stall shows as a catch-up ramp, not as one long sample).
  a  admin:   GET /ready on a new connection per probe, concurrent (a probe never waits for
              the previous one).
  c  control: keep-alive connections straight to the origin, same path.

Before the streams start, the map phase finds the worker thread that owns each data
connection: 100 back-to-back requests on a new connection, every wrk: thread's scheduler run
time read before and after; the owner is the thread with the largest increase, required at
least `--map-margin` times the next. Connections are kept until every worker has exactly
`--per-worker`; the others are closed. No connection is ever reopened after the map phase:
an error or close on a stream is recorded and that connection stays dead.

Output: FILE.jsonl.gz (first line a meta object, then one array per request:
[stream, connection, sequence, intended_ns, sent_ns, done_ns, status, bytes], last line an
end object with the loop gaps over 1 ms, events and the end clock pair) and FILE.json (the
summary). FILE.json.ready appears after the map phase. SIGTERM: requests with an intended
time up to that moment are still sent and awaited (bounded by --drain-s), then the files
are written.
"""

import argparse
import errno
import gc
import gzip
import json
import os
import selectors
import signal
import socket
import sys
import time

mono = time.monotonic_ns
MS = 1000000


# ---------------------------------------------------------------- HTTP response parsing

class Resp:
    """Incremental HTTP/1.1 response reader: content-length or chunked bodies."""

    __slots__ = ("buf", "need", "status", "got", "chunked", "body_at", "to_eof")

    def __init__(self):
        self.buf = bytearray()
        self.need = None      # body bytes still missing (content-length), None before the head
        self.status = None
        self.got = 0
        self.chunked = False
        self.to_eof = False   # neither length nor chunks: the body ends with the connection
        self.body_at = 0

    def feed(self, data):
        """True when the response is complete; raises ValueError on a malformed or over-long one.
        A body delimited by the end of the connection (`to_eof`) never completes here."""
        self.got += len(data)
        if self.to_eof:
            return False
        if self.status is None:
            self.buf += data
            i = self.buf.find(b"\r\n\r\n")
            if i < 0:
                return False
            head = bytes(self.buf[:i]).lower()
            if not head.startswith(b"http/1.") or len(head) < 12:
                raise ValueError("not an HTTP/1 response")
            self.status = int(head[9:12])
            self.body_at = i + 4
            j = head.find(b"\r\ncontent-length:")
            if j >= 0:
                e = head.find(b"\r\n", j + 2)
                self.need = int(head[j + 17:e if e >= 0 else len(head)]) - (len(self.buf) - self.body_at)
            elif b"\r\ntransfer-encoding: chunked" in head:
                self.chunked = True
            else:
                self.to_eof = True
                return False
        elif self.chunked:
            self.buf += data
        else:
            self.need -= len(data)
        if self.chunked:
            return self._chunks_done()
        if self.need < 0:
            raise ValueError("more bytes than content-length")
        return self.need == 0

    def _chunks_done(self):
        b, p = self.buf, self.body_at
        while True:
            e = b.find(b"\r\n", p)
            if e < 0:
                return False
            n = int(bytes(b[p:e]).split(b";")[0], 16)
            if n == 0:
                if len(b) >= e + 4:
                    if len(b) > e + 4:
                        raise ValueError("bytes after the last chunk")
                    return True
                return False
            p = e + 2 + n + 2
            if p > len(b):
                return False


# ---------------------------------------------------------------- the map phase

def map_decide(before, after):
    """(owner tid, margin, {tid: run ns increase}) from two {tid: run ns} readings: the owner
    is the thread with the largest increase, the margin its increase over the next one's."""
    d = {t: after[t] - before[t] for t in before if t in after}
    order = sorted(d, key=lambda t: d[t], reverse=True)
    if not order or d[order[0]] <= 0:
        return None, 0.0, d
    nxt = d[order[1]] if len(order) > 1 else 0
    return order[0], d[order[0]] / float(max(nxt, 1)), d


def map_connections(open_conn, measure, tids, per_worker=4, min_margin=5.0, max_opens=64, settle=lambda: None):
    """Open connections until every tid of `tids` owns exactly `per_worker` kept ones.
    open_conn() -> a connection with close(); measure(conn) -> (before, after) run ns per tid
    around 100 requests on it. A connection without a clear owner (margin under `min_margin`)
    or whose worker is full is closed. Gives up after `max_opens` opens.
    Returns (kept [(conn, tid, margin)], attempts [record], ok)."""
    count = {t: 0 for t in tids}
    kept, attempts = [], []
    for n in range(max_opens):
        if all(v == per_worker for v in count.values()):
            break
        conn = open_conn()
        before, after = measure(conn)
        owner, margin, _ = map_decide(before, after)
        rec = {"open": n, "owner": owner, "margin": round(margin, 2), "kept": False}
        if owner is None or owner not in count or margin < min_margin:
            rec["why"] = "no clear owner"
        elif count[owner] >= per_worker:
            rec["why"] = "worker full"
        else:
            rec["kept"] = True
            count[owner] += 1
            kept.append((conn, owner, margin))
        if not rec["kept"]:
            conn.close()
            settle()
        attempts.append(rec)
    return kept, attempts, bool(count) and all(v == per_worker for v in count.values())


def wrk_threads(pid, proc="/proc"):
    """{tid: {comm, cpus}} of the wrk: threads of pid (cpus = Cpus_allowed_list text)."""
    out = {}
    base = "%s/%d/task" % (proc, pid)
    try:
        tids = os.listdir(base)
    except OSError:
        return out
    for t in tids:
        try:
            with open("%s/%s/comm" % (base, t)) as f:
                comm = f.read().strip()
            if not comm.startswith("wrk:"):
                continue
            cpus = None
            with open("%s/%s/status" % (base, t)) as f:
                for line in f:
                    if line.startswith("Cpus_allowed_list:"):
                        cpus = line.split(":", 1)[1].strip()
            out[int(t)] = {"comm": comm, "cpus": cpus}
        except (OSError, ValueError):
            continue
    return out


def run_ns(pid, tids, proc="/proc"):
    out = {}
    for t in tids:
        try:
            with open("%s/%d/task/%d/schedstat" % (proc, pid, t)) as f:
                out[t] = int(f.read().split()[0])
        except (OSError, ValueError, IndexError):
            pass
    return out


def blocking_request(sock, req):
    """One request and its whole response on a blocking socket; (status, bytes)."""
    sock.sendall(req)
    r = Resp()
    while True:
        data = sock.recv(65536)
        if not data:
            raise OSError("closed by peer during the map phase")
        if r.feed(data):
            return r.status, r.got


def map_phase(a, req, events):
    """The data connections with their owners, or raises RuntimeError. Returns
    ([(socket, tid, margin)], record)."""
    pid = a.envoy_pid
    threads = wrk_threads(pid)
    tids = sorted(threads)
    rec = {"workers_found": len(tids), "threads": {str(t): threads[t] for t in tids}}
    if len(tids) != a.workers:
        rec["error"] = "%d wrk: threads of pid %d, expected %d" % (len(tids), pid, a.workers)
        return [], rec

    def open_conn():
        s = socket.create_connection(("127.0.0.1", a.listener_port), timeout=5.0)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return s

    def measure(s):
        b = run_ns(pid, tids)
        for _ in range(a.map_requests):
            st, _n = blocking_request(s, req)
            if st != 200:
                raise OSError("status %d in the map phase" % st)
        time.sleep(0.003)  # the worker is back in its poll: its run time is accounted
        return b, run_ns(pid, tids)

    try:
        kept, attempts, ok = map_connections(open_conn, measure, tids, a.per_worker, a.map_margin, a.map_max_opens,
                                             settle=lambda: time.sleep(0.005))
    except (OSError, ValueError) as ex:
        rec["error"] = "map phase: %s" % ex
        return [], rec
    rec.update(ok=ok, opens=len(attempts), attempts=attempts,
               min_margin=min([m for _, _, m in kept] or [0.0]),
               per_worker={str(t): sum(1 for _, o, _ in kept if o == t) for t in tids})
    if not ok:
        rec["error"] = "no %d connections per worker after %d opens" % (a.per_worker, len(attempts))
        for s, _, _ in kept:
            s.close()
        return [], rec
    rec["connections"] = [{"conn": i, "tid": t, "comm": threads[t]["comm"], "cpus": threads[t]["cpus"],
                           "margin": round(m, 2), "local_port": s.getsockname()[1]}
                          for i, (s, t, m) in enumerate(kept)]
    return kept, rec


# ---------------------------------------------------------------- the streams

class Keep:
    """A keep-alive connection with its own schedule; one request at a time."""

    __slots__ = ("stream", "idx", "sock", "req", "period", "next_t", "seq", "cur", "resp", "dead")

    def __init__(self, stream, idx, sock, req, period, first_t):
        self.stream, self.idx, self.sock, self.req, self.period = stream, idx, sock, req, period
        self.next_t, self.seq, self.cur, self.resp, self.dead = first_t, 0, None, None, False


class Once:
    """One admin probe on its own connection."""

    __slots__ = ("sock", "rec", "resp", "sent")

    def __init__(self, sock, rec):
        self.sock, self.rec, self.resp, self.sent = sock, rec, Resp(), False


def clock_pair():
    a = mono()
    w = time.time_ns()
    b = mono()
    return {"monotonic_ns": (a + b) // 2, "time_ns": w, "read_ns": b - a}


def run_streams(data_socks, ctl_socks, admin_addr, cfg, stop, rows, gaps, events):
    """The busy-poll loop. data_socks / ctl_socks: connected sockets (set non-blocking here);
    admin_addr: (host, port) or None; cfg: data_req, ctl_req, admin_req (bytes), data_period_ns,
    data_stagger_ns, ctl_period_ns, admin_period_ns, gap_ns, drain_ns, start_delay_ns,
    max_ns (optional: stop by itself after that long, for tests). stop: a list, non-empty
    means stop. Appends request rows, loop gaps [from_ns, to_ns] and events.
    Returns {base_ns, stop_ns, end_ns, drained}."""
    sel = selectors.DefaultSelector()
    base = mono() + cfg.get("start_delay_ns", 100 * MS)
    keeps = []
    for i, s in enumerate(data_socks):
        s.setblocking(False)
        k = Keep("d", i, s, cfg["data_req"], cfg["data_period_ns"], base + i * cfg["data_stagger_ns"])
        keeps.append(k)
        sel.register(s, selectors.EVENT_READ, k)
    for i, s in enumerate(ctl_socks):
        s.setblocking(False)
        per = cfg["ctl_period_ns"]
        k = Keep("c", i, s, cfg["ctl_req"], per, base + (i * per) // max(1, len(ctl_socks)) + 600000)
        keeps.append(k)
        sel.register(s, selectors.EVENT_READ, k)
    admin_next, admin_seq, admin_open = base + 300000, 0, 0
    admin_per = cfg.get("admin_period_ns") if admin_addr else None
    gap_ns, drain_ns = cfg.get("gap_ns", MS), cfg.get("drain_ns", 10000 * MS)
    max_ns = cfg.get("max_ns")
    limit = None       # intended times after this are not sent (set at the stop)
    deadline = None
    outstanding = 0    # keep-alive requests in flight
    select = sel.select
    last = mono()

    def fail(k, what, now):
        nonlocal outstanding
        events.append({"t_ns": now, "stream": k.stream, "conn": k.idx, "what": what})
        if k.cur is not None:
            outstanding -= 1   # the request stays in the rows without done_ns
            k.cur = None
        k.dead = True
        try:
            sel.unregister(k.sock)
        except (KeyError, ValueError):
            pass
        k.sock.close()

    while True:
        now = mono()
        if now - last > gap_ns:
            gaps.append([last, now])
        last = now
        if limit is None and (stop or (max_ns is not None and now - base >= max_ns)):
            limit, deadline = now, now + drain_ns
        horizon = now if limit is None else limit
        for k in keeps:
            if k.cur is None and not k.dead and k.next_t <= horizon and k.next_t <= now:
                rec = [k.stream, k.idx, k.seq, k.next_t, mono(), None, None, 0]
                try:
                    k.sock.send(k.req)
                except OSError as ex:
                    rows.append(rec)
                    k.cur = None
                    fail(k, "send: %s" % ex, now)
                    continue
                rows.append(rec)
                k.cur, k.resp = rec, Resp()
                k.seq += 1
                k.next_t += k.period
                outstanding += 1
        if admin_per:
            while admin_next <= horizon and admin_next <= now:
                rec = ["a", 0, admin_seq, admin_next, None, None, None, 0]
                rows.append(rec)
                admin_seq += 1
                admin_next += admin_per
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setblocking(False)
                    rc = s.connect_ex(admin_addr)
                    if rc not in (0, errno.EINPROGRESS):
                        raise OSError(rc, os.strerror(rc))
                    sel.register(s, selectors.EVENT_WRITE, Once(s, rec))
                    admin_open += 1
                except OSError as ex:
                    events.append({"t_ns": now, "stream": "a", "conn": rec[2], "what": "connect: %s" % ex})
        for key, ev in select(0):
            c = key.data
            if type(c) is Keep:
                try:
                    data = c.sock.recv(65536)
                except (BlockingIOError, InterruptedError):
                    continue
                except OSError as ex:
                    fail(c, "recv: %s" % ex, now)
                    continue
                if not data:
                    fail(c, "closed by peer", now)
                    continue
                if c.cur is None:
                    fail(c, "bytes without a request", now)
                    continue
                try:
                    done = c.resp.feed(data)
                    if c.resp.to_eof:
                        raise ValueError("no content-length or chunked encoding on a keep-alive connection")
                except ValueError as ex:
                    fail(c, "response: %s" % ex, now)
                    continue
                if done:
                    rec = c.cur
                    rec[5], rec[6], rec[7] = mono(), c.resp.status, c.resp.got
                    c.cur = None
                    outstanding -= 1
                continue
            # an admin probe
            try:
                if not c.sent:
                    err = c.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    if err:
                        raise OSError(err, os.strerror(err))
                    c.rec[4] = mono()
                    c.sock.send(cfg["admin_req"])
                    c.sent = True
                    sel.modify(c.sock, selectors.EVENT_READ, c)
                    continue
                data = c.sock.recv(65536)
                # connection: close, so the end of the stream also ends a response
                done = (not data and c.resp.status is not None) or (bool(data) and c.resp.feed(data))
                if not data and not done:
                    raise OSError("closed before a response")
                if not done:
                    continue
                c.rec[5], c.rec[6], c.rec[7] = mono(), c.resp.status, c.resp.got
            except (BlockingIOError, InterruptedError):
                continue
            except (OSError, ValueError) as ex:
                events.append({"t_ns": now, "stream": "a", "conn": c.rec[2], "what": str(ex)})
            sel.unregister(c.sock)
            c.sock.close()
            admin_open -= 1
        if limit is not None:
            idle = outstanding == 0 and admin_open == 0 and all(
                k.dead or k.next_t > limit for k in keeps) and (not admin_per or admin_next > limit)
            if idle or now > deadline:
                drained = idle
                break
    end = mono()
    for key in list(sel.get_map().values()):
        if type(key.data) is Once:
            key.data.sock.close()
    sel.close()
    return {"base_ns": base, "stop_ns": limit, "end_ns": end, "drained": drained}


def summarize(rows, events, gaps, run):
    out = {"gaps": len(gaps), "events": len(events), "drained": run["drained"]}
    for st, name in (("d", "data"), ("a", "admin"), ("c", "control")):
        mine = [r for r in rows if r[0] == st]
        done = [r for r in mine if r[5] is not None]
        out[name] = {"planned": len(mine), "sent": sum(1 for r in mine if r[4] is not None), "done": len(done),
                     "non200": sum(1 for r in done if r[6] != 200),
                     "errors": sum(1 for e in events if e["stream"] == st)}
    return out


def request_bytes(path, host, close=False):
    return ("GET %s HTTP/1.1\r\nHost: %s\r\n%s\r\n" % (path, host, "Connection: close\r\n" if close else "")).encode()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--listener-port", type=int, required=True)
    ap.add_argument("--admin-port", type=int, required=True)
    ap.add_argument("--origin-port", type=int, required=True)
    ap.add_argument("--envoy-pid", type=int, required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--path", default="/s")
    ap.add_argument("--per-worker", type=int, default=4)
    ap.add_argument("--data-hz", type=float, default=50.0)
    ap.add_argument("--data-stagger-ms", type=float, default=1.25)
    ap.add_argument("--admin-period-ms", type=float, default=50.0)
    ap.add_argument("--control-conns", type=int, default=2)
    ap.add_argument("--control-hz", type=float, default=25.0)
    ap.add_argument("--map-requests", type=int, default=100)
    ap.add_argument("--map-margin", type=float, default=5.0)
    ap.add_argument("--map-max-opens", type=int, default=64)
    ap.add_argument("--gap-ms", type=float, default=1.0)
    ap.add_argument("--drain-s", type=float, default=10.0)
    ap.add_argument("--out-log", required=True)
    ap.add_argument("--out-summary", required=True)
    a = ap.parse_args(argv)
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    summary = {"args": vars(a), "pid": os.getpid(), "clock_start": clock_pair(),
               "cpus_allowed": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None}
    events, rows, gaps = [], [], []
    data_req = request_bytes(a.path, "127.0.0.1:%d" % a.listener_port)
    kept, mrec = map_phase(a, data_req, events)
    summary["map"] = mrec
    if mrec.get("error"):
        summary["error"] = mrec["error"]
        with open(a.out_summary, "w") as f:
            json.dump(summary, f)
        return 3
    try:
        ctl = []
        for _ in range(a.control_conns):
            s = socket.create_connection(("127.0.0.1", a.origin_port), timeout=5.0)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            ctl.append(s)
    except OSError as ex:
        summary["error"] = "control connection: %s" % ex
        with open(a.out_summary, "w") as f:
            json.dump(summary, f)
        return 3
    cfg = {"data_req": data_req, "ctl_req": request_bytes(a.path, "127.0.0.1:%d" % a.origin_port),
           "admin_req": request_bytes("/ready", "127.0.0.1:%d" % a.admin_port, close=True),
           "data_period_ns": int(round(1e9 / a.data_hz)), "data_stagger_ns": int(round(a.data_stagger_ms * 1e6)),
           "ctl_period_ns": int(round(1e9 / a.control_hz)), "admin_period_ns": int(round(a.admin_period_ms * 1e6)),
           "gap_ns": int(round(a.gap_ms * 1e6)), "drain_ns": int(round(a.drain_s * 1e9))}
    socks = [s for s, _, _ in kept]
    with open(a.out_summary + ".ready", "w") as f:
        json.dump({"map": mrec}, f)
    gc.disable()
    run = run_streams(socks, ctl, ("127.0.0.1", a.admin_port), cfg, stop, rows, gaps, events)
    gc.enable()
    # the map at the end: the same sockets, still open, the same threads on the same CPUs
    end_ports = []
    for s in socks:
        try:
            end_ports.append(s.getsockname()[1] if s.fileno() >= 0 else None)
        except OSError:
            end_ports.append(None)
    th = wrk_threads(a.envoy_pid)
    summary["map_end"] = {"local_ports": end_ports, "threads": {str(t): th[t] for t in sorted(th)}}
    summary["map_end"]["unchanged"] = (
        end_ports == [c["local_port"] for c in mrec["connections"]]
        and summary["map_end"]["threads"] == mrec["threads"])
    summary["clock_end"] = clock_pair()
    summary["run"] = run
    summary.update(summarize(rows, events, gaps, run))
    meta = {"meta": {k: summary[k] for k in ("args", "clock_start", "map", "run", "cpus_allowed")},
            "periods_ns": {k: cfg[k] for k in cfg if k.endswith("_ns")},
            "columns": ["stream", "connection", "sequence", "intended_ns", "sent_ns", "done_ns", "status", "bytes"]}
    with gzip.open(a.out_log, "wt", compresslevel=1) as f:
        f.write(json.dumps(meta) + "\n")
        for r in rows:
            f.write(json.dumps(r) + "\n")
        f.write(json.dumps({"end": {"gaps": gaps, "events": events, "clock_end": summary["clock_end"],
                                    "map_end": summary["map_end"]}}) + "\n")
    with open(a.out_summary, "w") as f:
        json.dump(summary, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
