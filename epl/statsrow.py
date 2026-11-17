"""Pieces of the stats-flush row: the main-thread sampler and its burst detection, the
kernel's UDP counters, the full admin /stats read, priming, the /ready prober, the
Prometheus scraper, per-process records (file-descriptor limit, memory), and the extras a
leg runs around Envoy (discard sink, priming, sampler, prober, scraper).

Everything here reads /proc and the admin port; nothing signals a process this run did not
start. Pure functions take text or series so they are unit-tested on recorded data.
"""

import concurrent.futures
import http.client
import json
import os
import re
import subprocess
import sys
import threading
import time

from . import envoy_config, sysprobe

# ---------------------------------------------------------------- /proc readers


def read(path, default=None):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def thread_run_ns(pid, tid):
    """Scheduler run time of one thread in ns (/proc/<pid>/task/<tid>/schedstat), or None."""
    txt = read("/proc/%d/task/%d/schedstat" % (pid, tid))
    try:
        return int(txt.split()[0])
    except (AttributeError, ValueError, IndexError):
        return None


def thread_comm(pid, tid):
    t = read("/proc/%d/task/%d/comm" % (pid, tid))
    return t.strip() if t else None


def threads_run_ns(pid):
    """{tid: (comm, run ns)} for every thread of pid."""
    out = {}
    try:
        tids = os.listdir("/proc/%d/task" % pid)
    except OSError:
        return out
    for t in tids:
        try:
            tid = int(t)
        except ValueError:
            continue
        ns = thread_run_ns(pid, tid)
        if ns is not None:
            out[tid] = (thread_comm(pid, tid), ns)
    return out


def parse_limits(text):
    """(soft, hard) of "Max open files" from /proc/<pid>/limits text; None if absent."""
    for line in (text or "").splitlines():
        if line.startswith("Max open files"):
            parts = line.split()
            try:
                soft, hard = parts[3], parts[4]
                return (None if soft == "unlimited" else int(soft), None if hard == "unlimited" else int(hard))
            except (IndexError, ValueError):
                return None
    return None


def fd_count(pid):
    try:
        return len(os.listdir("/proc/%d/fd" % pid))
    except OSError:
        return None


def parse_status_kb(text, key):
    for line in (text or "").splitlines():
        if line.startswith(key + ":"):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def memory_kb(pid):
    t = read("/proc/%d/status" % pid)
    return {"vm_rss_kb": parse_status_kb(t, "VmRSS"), "vm_hwm_kb": parse_status_kb(t, "VmHWM")}


def parse_snmp_udp(text):
    """{field: int} of the `Udp:` lines of /proc/net/snmp (header line, then values)."""
    lines = [ln.split() for ln in (text or "").splitlines() if ln.startswith("Udp:")]
    if len(lines) < 2:
        return {}
    keys, vals = lines[0][1:], lines[1][1:]
    out = {}
    for k, v in zip(keys, vals):
        try:
            out[k] = int(v)
        except ValueError:
            pass
    return out


def parse_udp_socket(text, port, addr="0100007F"):
    """The row of /proc/net/udp bound to 127.0.0.1:port: {rx_queue, drops}; None if absent."""
    want = "%s:%04X" % (addr, int(port))
    for line in (text or "").splitlines()[1:]:
        f = line.split()
        if len(f) >= 13 and f[1].upper() == want:
            try:
                rxq = int(f[4].split(":")[1], 16)
                return {"rx_queue": rxq, "drops": int(f[-1])}
            except (IndexError, ValueError):
                return None
    return None


def udp_counters(port):
    """Kernel-side view of the discard socket: system UDP counters and the socket's row."""
    return {"snmp": parse_snmp_udp(read("/proc/net/snmp")), "sock": parse_udp_socket(read("/proc/net/udp"), port)}


def udp_window(c0, c1, flushes, used_lines=None):
    """Sink evidence over a window from two udp_counters readings. Delivered = the change of
    InDatagrams (the loopback carries nothing else over UDP in an idle leg); dropped = the
    larger of the change of RcvbufErrors and of the socket's drops (the same drops, counted
    twice by the kernel); sent = delivered + dropped."""
    s0, s1 = c0.get("snmp") or {}, c1.get("snmp") or {}
    for k in ("InDatagrams", "RcvbufErrors"):
        if k not in s0 or k not in s1:
            # without RcvbufErrors a drop would read as none: fail closed
            return {"error": "no %s in the Udp: line of /proc/net/snmp" % k}
    delivered = s1["InDatagrams"] - s0["InDatagrams"]
    rcvbuf = s1["RcvbufErrors"] - s0["RcvbufErrors"]
    k0, k1 = c0.get("sock"), c1.get("sock")
    sockd = (k1["drops"] - k0["drops"]) if k0 and k1 else None
    dropped = max(rcvbuf, sockd or 0)
    sent = delivered + dropped
    out = {"delivered": delivered, "rcvbuf_errors": rcvbuf, "socket_drops": sockd, "dropped": dropped,
           "sent": sent, "drop_share": (dropped / sent) if sent else 0.0,
           "in_errors": s1.get("InErrors", 0) - s0.get("InErrors", 0)}
    if flushes:
        out["sent_per_flush"] = sent / flushes
    if used_lines:
        out["used_lines"] = used_lines
    return out


def flush_fit(sent, used_lines, expected):
    """Datagrams between two quiescent points are a whole number of flushes of `used_lines`
    lines each (the plain statsd sink: one datagram per used counter or gauge). n = the
    nearest whole number of flushes; residual = |sent - n x used| / used, as a share of one
    flush; n_error = |n - expected|."""
    if not used_lines or sent is None:
        return {"error": "no used-line count"}
    n = int(round(sent / float(used_lines)))
    return {"n": n, "residual": abs(sent - n * used_lines) / float(used_lines),
            "expected": expected, "n_error": abs(n - expected) if expected is not None else None}


def quiesce(pid, port=None, timeout_s=30.0, step_s=0.03, max_busy=0.1):
    """Wait (bounded) for a quiescent point: the main thread idle over one step (no flush in
    progress) and, with a sink port, its receive queue empty (every datagram sent so far has
    been read, so the kernel's InDatagrams has counted it). Returns (ok, seconds waited)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        a = thread_run_ns(pid, pid)
        time.sleep(step_s)
        b = thread_run_ns(pid, pid)
        idle = a is not None and b is not None and (b - a) / 1e9 / step_s <= max_busy
        q = True
        if port is not None:
            s = parse_udp_socket(read("/proc/net/udp"), port)
            q = s is not None and s["rx_queue"] == 0
        if idle and q:
            return True, round(time.monotonic() - t0, 3)
    return False, round(time.monotonic() - t0, 3)


def busiest_other_ratio(th0, th1, pid):
    """Main thread's run time over the busiest other thread's, between two threads_run_ns
    readings (the plan's smoke check: at least 10 in an idle statsd leg at the top rung)."""
    main = (th1.get(pid, (None, 0))[1] - th0.get(pid, (None, 0))[1]) if pid in th0 and pid in th1 else None
    others = [th1[t][1] - th0[t][1] for t in th1 if t in th0 and t != pid]
    if main is None:
        return None
    top = max(others or [0])
    return main / top if top > 0 else float("inf")


# ---------------------------------------------------------------- admin /stats

HIST_RE = re.compile(r"(P0\(|No recorded values)")


def parse_stats_text(text):
    """Counts and numeric values of a plain-text admin /stats body: {total, histograms,
    text_readouts, numeric: {name: value}}. Counters and gauges look alike in this format."""
    out = {"total": 0, "histograms": 0, "text_readouts": 0, "numeric": {}}
    num = out["numeric"]
    for line in (text or "").splitlines():
        k, sep, v = line.partition(": ")
        if not sep:
            continue
        out["total"] += 1
        v = v.strip()
        if v.startswith('"'):
            out["text_readouts"] += 1
            continue
        if HIST_RE.match(v):
            out["histograms"] += 1
            continue
        try:
            num[k] = int(v)
        except ValueError:
            try:
                num[k] = float(v)
            except ValueError:
                pass
    return out


def admin_text(port, path, timeout):
    t0 = time.monotonic()
    c = http.client.HTTPConnection("127.0.0.1", int(port), timeout=timeout)
    try:
        c.request("GET", path)
        r = c.getresponse()
        body = r.read().decode(errors="replace")
    finally:
        c.close()
    return r.status, body, time.monotonic() - t0


def stats_read(port, timeout, usedonly=False):
    """One full /stats read (every stat walked on the main thread; with stats_flush_on_admin
    it also triggers a full flush). {status, seconds, total, histograms, ..., numeric}."""
    st, body, dt = admin_text(port, "/stats" + ("?usedonly" if usedonly else ""), timeout)
    out = parse_stats_text(body) if st == 200 else {"numeric": {}}
    out.update(status=st, seconds=round(dt, 3), bytes=len(body))
    return out


def generated_sum(numeric, names, suffix):
    """Sum of cluster.<name>.<suffix> over the generated clusters (missing = 0, usedonly)."""
    return sum(int(numeric.get("cluster.%s.%s" % (n, suffix), 0)) for n in names)


# ---------------------------------------------------------------- main-thread sampler

class MainSampler(threading.Thread):
    """Reads the main thread's scheduler run time (ns) every `period_s` (default 20 ms, 50 Hz)
    for the window, from a thread pinned to `cpus` (the client set)."""

    def __init__(self, pid, tid, period_s=0.02, cpus=None):
        super().__init__(daemon=True)
        self.pid, self.tid, self.period_s, self.cpus = pid, tid, period_s, cpus
        self.samples = []  # (monotonic s, run ns)
        self.stop_evt = threading.Event()
        self.missing = 0

    def run(self):
        if self.cpus:
            try:
                os.sched_setaffinity(0, self.cpus)
            except (OSError, AttributeError):
                pass
        t0 = time.monotonic()
        k = 0
        while not self.stop_evt.is_set():
            ns = thread_run_ns(self.pid, self.tid)
            if ns is None:
                self.missing += 1
            else:
                self.samples.append((time.monotonic(), ns))
            k += 1
            d = t0 + k * self.period_s - time.monotonic()
            if d > 0:
                self.stop_evt.wait(d)


def find_bursts(samples, min_busy=0.2, join_gap_s=0.1):
    """Bursts of main-thread work in a run-time series [(t s, run ns)].

    An interval between two samples is busy when the thread ran more than `min_busy` of it.
    A burst is a run of busy intervals; bursts separated by at most `join_gap_s` of quiet
    (the workers' round trip in the histogram merge) are joined. Each burst starts at the
    last sample before it (the boundary) and carries its run time and wall length.
    Returns [{start_t, end_t, wall_s, run_ns, start_i, end_i}]."""
    raw = []
    cur = None
    for i in range(1, len(samples)):
        (ta, na), (tb, nb) = samples[i - 1], samples[i]
        dt = tb - ta
        busy = dt > 0 and (nb - na) / 1e9 / dt > min_busy
        if busy:
            if cur is None:
                cur = {"start_i": i - 1, "end_i": i}
            else:
                cur["end_i"] = i
        elif cur is not None:
            raw.append(cur)
            cur = None
    if cur is not None:
        raw.append(cur)
    joined = []
    for b in raw:
        if joined and samples[b["start_i"]][0] - samples[joined[-1]["end_i"]][0] <= join_gap_s:
            joined[-1]["end_i"] = b["end_i"]
        else:
            joined.append(dict(b))
    for b in joined:
        b["start_t"], b["end_t"] = samples[b["start_i"]][0], samples[b["end_i"]][0]
        b["wall_s"] = b["end_t"] - b["start_t"]
        b["run_ns"] = samples[b["end_i"]][1] - samples[b["start_i"]][1]
    return joined


def summarize_main(samples, bursts, window_s):
    """Per-flush figures from a series and its bursts: run time per second over the window,
    run time per period over K whole periods (first burst start to the K-th later one), burst
    run time and wall length (p50, max)."""
    out = {"samples": len(samples), "bursts": len(bursts)}
    if len(samples) < 2:
        return out
    span = samples[-1][0] - samples[0][0]
    total_ns = samples[-1][1] - samples[0][1]
    out["window_s"] = round(span, 4)
    out["run_ms_per_s"] = total_ns / 1e6 / span if span > 0 else None
    if bursts:
        runs = sorted(b["run_ns"] / 1e6 for b in bursts)
        walls = sorted(b["wall_s"] * 1e3 for b in bursts)
        out["burst_run_ms_mean"] = sum(runs) / len(runs)
        out["burst_run_ms_p50"] = runs[len(runs) // 2]
        out["burst_run_ms_max"] = runs[-1]
        out["stall_ms_p50"] = walls[len(walls) // 2]
        out["stall_ms_max"] = walls[-1]
    if len(bursts) >= 2:
        k = len(bursts) - 1
        a, b = bursts[0]["start_i"], bursts[-1]["start_i"]
        per = (samples[b][1] - samples[a][1]) / 1e6 / k
        out["periods"] = k
        out["run_ms_per_period"] = per
        out["period_s"] = (samples[b][0] - samples[a][0]) / k
    return out


def expected_flushes(window_s, interval_s, burst_s):
    return int(window_s // (interval_s + burst_s)) if interval_s else 0


# ---------------------------------------------------------------- helpers on threads

class ReadyProber(threading.Thread):
    """GET /ready every `period_s`; records latencies and failures (the main thread's
    responsiveness during flushes)."""

    def __init__(self, port, period_s=0.2, cpus=None, timeout=5.0):
        super().__init__(daemon=True)
        self.port, self.period_s, self.cpus, self.timeout = port, period_s, cpus, timeout
        self.lat_ms, self.failures = [], 0
        self.stop_evt = threading.Event()

    def run(self):
        if self.cpus:
            try:
                os.sched_setaffinity(0, self.cpus)
            except (OSError, AttributeError):
                pass
        while not self.stop_evt.is_set():
            try:
                st, _, dt = admin_text(self.port, "/ready", self.timeout)
                if st == 200:
                    self.lat_ms.append(dt * 1e3)
                else:
                    self.failures += 1
            except (OSError, http.client.HTTPException):
                self.failures += 1
            self.stop_evt.wait(self.period_s)

    def summary(self):
        x = sorted(self.lat_ms)
        return {"probes": len(x), "failures": self.failures, "p50_ms": x[len(x) // 2] if x else None,
                "max_ms": x[-1] if x else None}


class PromScraper(threading.Thread):
    """GET /stats/prometheus every `period_s` (the scrape path of the `prom` arm)."""

    def __init__(self, port, period_s=5.0, cpus=None, timeout=60.0):
        super().__init__(daemon=True)
        self.port, self.period_s, self.cpus, self.timeout = port, period_s, cpus, timeout
        self.scrapes = []
        self.stop_evt = threading.Event()

    def run(self):
        if self.cpus:
            try:
                os.sched_setaffinity(0, self.cpus)
            except (OSError, AttributeError):
                pass
        t0 = time.monotonic()
        k = 0
        while not self.stop_evt.is_set():
            try:
                st, body, dt = admin_text(self.port, "/stats/prometheus", self.timeout)
                self.scrapes.append({"status": st, "bytes": len(body), "seconds": round(dt, 4),
                                     "lines": body.count("\n")})
            except (OSError, http.client.HTTPException) as e:
                self.scrapes.append({"status": None, "error": str(e)[:120]})
            k += 1
            d = t0 + k * self.period_s - time.monotonic()
            if d > 0:
                self.stop_evt.wait(d)

    def summary(self):
        ok = [s for s in self.scrapes if s.get("status") == 200]
        lines = sorted(s["lines"] for s in ok)
        secs = sorted(s["seconds"] for s in ok)
        return {"scrapes": len(self.scrapes), "all_200": bool(self.scrapes) and len(ok) == len(self.scrapes),
                "lines_p50": lines[len(lines) // 2] if lines else None,
                "seconds_p50": secs[len(secs) // 2] if secs else None, "seconds_max": secs[-1] if secs else None}


# ---------------------------------------------------------------- priming

class TokenBucket:
    def __init__(self, rate):
        self.rate = float(rate)
        self.lock = threading.Lock()
        self.next = time.monotonic()

    def take(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + 1.0 / self.rate
        d = t - time.monotonic()
        if d > 0:
            time.sleep(d)


def prime(port, names, in_flight=200, per_s=1000, timeout=10.0):
    """One request per generated cluster (header-selected), keep-alive, paced: at most
    `in_flight` at once and `per_s` per second, no retries. {requests, ok, non200, errors,
    seconds}."""
    bucket = TokenBucket(per_s)
    local = threading.local()
    lock = threading.Lock()
    res = {"requests": 0, "ok": 0, "non200": 0, "errors": 0, "first_error": None}

    def one(name):
        bucket.take()
        try:
            c = getattr(local, "c", None)
            if c is None:
                c = local.c = http.client.HTTPConnection("127.0.0.1", int(port), timeout=timeout)
            c.request("GET", envoy_config.STATS_PRIME_PATH, headers={envoy_config.STATS_CLUSTER_HEADER: name})
            r = c.getresponse()
            r.read()
            st = r.status
        except (OSError, http.client.HTTPException) as e:
            local.c = None
            with lock:
                res["requests"] += 1
                res["errors"] += 1
                res["first_error"] = res["first_error"] or "%s: %s" % (name, e)
            return
        with lock:
            res["requests"] += 1
            if st == 200:
                res["ok"] += 1
            else:
                res["non200"] += 1
                res["first_error"] = res["first_error"] or "%s: status %d" % (name, st)

    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(in_flight)) as ex:
        list(ex.map(one, names))
    res["seconds"] = round(time.monotonic() - t0, 2)
    return res


# ---------------------------------------------------------------- the discard sink process

def start_udpsink(own, cpus, port, rcvbuf, out_path, sample_every=1, wait_s=10.0):
    """Start the drain-only UDP sink as this run's own pinned child; wait until it is bound."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "udpsink.py")
    for p in (out_path, out_path + ".ready"):
        if os.path.exists(p):
            os.remove(p)
    p = own.start(["taskset", "-c", cpus, sys.executable, script, "--port", str(port), "--rcvbuf", str(rcvbuf),
                   "--out", out_path, "--sample-every", str(sample_every)],
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.monotonic() + wait_s
    while time.monotonic() < end:
        if os.path.exists(out_path + ".ready"):
            return p
        if p.poll() is not None:
            break
        time.sleep(0.05)
    own.stop(p)
    raise RuntimeError("UDP discard sink did not bind port %d" % port)


def stop_udpsink(own, p, out_path):
    own.stop(p, grace_s=10.0)
    try:
        with open(out_path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"error": "no sink record"}


def process_side(pid, want_cpus, run0_ns, run1_ns, seconds):
    """Side-service record of a plain child process (the discard sink): its CPU list and its
    CPU share of the configured set over the window."""
    want = sysprobe.parse_cpuset(want_cpus)
    al = sysprobe.cpus_allowed(pid)
    r = {"want": want_cpus, "cpuset": al, "cpuset_ok": al is not None and sysprobe.parse_cpuset(al) == want,
         "pids": 1, "pids_ok": al is not None and sysprobe.parse_cpuset(al) == want}
    if run0_ns is None or run1_ns is None or seconds <= 0:
        r["error"] = "sink CPU time unreadable"
        return r
    cpu_s = (run1_ns - run0_ns) / 1e9
    r.update(cpu_s=round(cpu_s, 4), busy_of_set=round(cpu_s / seconds / max(1, len(want)), 5),
             cpus_used=round(cpu_s / seconds, 4))
    return r
