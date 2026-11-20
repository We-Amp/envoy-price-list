"""One measurement leg: start Envoy pinned, drive load, count SUT-side CPU, stop Envoy.

Sequence:
  1. idle check (/proc load + busy, per-CPU busy on the SUT CPUs and their SMT
     siblings, `pgrep -f` for stray load generators/proxies)
  2. port preflight (python socket connect: listener + admin free, origin open)
  3. start Envoy under taskset on the SUT CPUs; wait for /ready
  4. warm-up client run
  5. measured client run; after a lead-in, snapshot admin stats and client
     thread CPU, Envoy thread CPU and per-CPU times, run
     `perf stat -p <envoy pid>` for the steady window, snapshot again (the
     during-window idle check compares the SUT CPUs' busy time with Envoy's)
  6. stop Envoy (only the PID this process started), parse, verdict

Every wait is bounded by a timeout, so a stuck child can never hang the run.
"""

import gzip
import http.client
import json
import math
import os
import re
import signal
import subprocess
import threading
import time
import urllib.parse

from . import envoy_config
from . import experiment as _exp
from . import latency, nighthawk, statsrow, sysprobe, validity

PERF_EVENTS = "instructions:u,cycles:u,cycles:k,instructions:k,task-clock,context-switches,cpu-migrations"
BASE_EVENT_NAMES = ("instructions:u", "cycles:u", "cycles:k", "instructions:k", "cycles", "task-clock",
                    "context-switches", "cpu-migrations")


def perf_events(mcfg, rnd):
    """The perf event list of a leg: `measure.perf_event_groups` rotated by round (every arm
    of a round counts the same group, so paired rounds compare like with like), else
    `measure.perf_events`, else the default list."""
    groups = mcfg.get("perf_event_groups")
    if groups:
        return groups[(int(rnd) - 1) % len(groups)]
    return mcfg.get("perf_events") or PERF_EVENTS


def perf_counts_ok(pv):
    """instructions:u and total cycles: either cycles:u + cycles:k, or `cycles` (user + kernel
    on one counter, which leaves a programmable counter free for an event group)."""
    return "instructions:u" in pv and (("cycles:u" in pv and "cycles:k" in pv) or "cycles" in pv)


class OwnProcesses:
    """Registry of child processes this run started. Only these are ever signalled."""

    def __init__(self):
        self.procs = {}

    def start(self, args, **kw):
        p = subprocess.Popen(args, start_new_session=True, **kw)
        self.procs[p.pid] = (p, os.path.realpath(args[0]) if os.path.exists(args[0]) else args[0])
        return p

    def pids(self):
        return set(pid for pid, (p, _) in self.procs.items() if p.poll() is None)

    def stop(self, p, grace_s=10.0):
        """SIGTERM then SIGKILL, only for a Popen we created and that has not been reaped."""
        if p.pid not in self.procs:
            raise RuntimeError("refusing to signal PID %d: not started by this run" % p.pid)
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
            try:
                p.wait(timeout=grace_s)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=grace_s)
        self.procs.pop(p.pid, None)
        return p.returncode

    def stop_all(self):
        for pid in list(self.procs):
            p, _ = self.procs[pid]
            try:
                self.stop(p, grace_s=5.0)
            except Exception:  # noqa: BLE001 - best effort at exit
                pass


def admin_get(port, path, timeout=5.0):
    c = http.client.HTTPConnection("127.0.0.1", int(port), timeout=timeout)
    try:
        c.request("GET", path)
        r = c.getresponse()
        return r.status, r.read().decode(errors="replace")
    finally:
        c.close()


STAT_FILTER = (r"^(http\.ingress_http\.|cluster\.(origin|ext_authz|otel_collector)\.upstream_(cx_total|rq_total|"
               r"cx_connect_fail|cx_overflow|rq_pending_overflow|rq_retry|rq_2xx|rq_4xx|rq_5xx|rq_timeout|cx_destroy|cx_active|"
               r"cx_tx_bytes_total|cx_rx_bytes_total|"
               r"cx_destroy_local|cx_destroy_remote|cx_destroy_local_with_active_rq|cx_destroy_remote_with_active_rq|"
               r"cx_max_requests|cx_idle_timeout|cx_max_duration_reached|rq_reset|cx_protocol_error|rq_503|"
               r"flow_control_[a-z_]+)$|"
               r"listener\..*\.(ssl\.(handshake|session_reused|connection_error|no_certificate)|downstream_cx_total|"
               r"downstream_cx_active)$|"
               r"listener\..*\.ssl\.(versions|ciphers|curves|sigalgs)\.|"
               r"tracing\.|access_logs\.|[a-z_]+\.http_local_rate_limit\.|filesystem\.|lua\.|wasm\.)")
# deltas of these are recorded per leg (counters only; gauges and histograms are skipped)
DELTA_KEYS_RE = re.compile(r"(ext_authz\.|tracing\.|jwt_authn\.|http_local_rate_limit\.|ssl\.|upstream_rq_retry|upstream_rq_total|upstream_cx_total|"
                           r"filesystem\.|downstream_rq_completed|tx_bytes_total|compressor\.|lua\.|wasm\.|"
                           r"downstream_cx_total|downstream_rq_total|downstream_rq_2xx|rq_timeout|cx_destroy$|overflow|"
                           r"cx_destroy_local|cx_destroy_remote|cx_max_requests|max_requests_reached|idle_timeout|"
                           r"max_duration_reached|"
                           r"rq_reset|protocol_error|rq_5xx|rq_503|"
                           r"flow_control_)")
# cumulative values recorded at the end of the window: what TLS negotiated (keep-alive
# connections handshake before the window) and the gauges of open connections
END_KEYS_RE = re.compile(r"(ssl\.(versions|ciphers|curves|sigalgs)\.|upstream_cx_active$|downstream_cx_active$)")


def admin_stats(port, timeout=5.0, extra=None):
    """The filtered stats snapshot; `extra` (measure.stat_filter_extra) is one more regex
    alternative, for a stat an experiment's evidence reads that the fixed filter leaves out."""
    flt = STAT_FILTER + ("|" + extra if extra else "")
    st, body = admin_get(port, "/stats?filter=" + urllib.parse.quote(flt), timeout=timeout)
    if st != 200:
        raise RuntimeError("admin /stats returned %d" % st)
    out = {}
    for line in body.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            try:
                out[k.strip()] = int(v.strip())
            except ValueError:
                pass
    return out


STAT_COUNT_REQUESTS = "http.ingress_http.downstream_rq_completed"


def parse_stat_count(body, prefix, beside=STAT_COUNT_REQUESTS):
    """(number of stats, sum of their values, value of the stat `beside` or None) over the lines
    of an admin /stats page; the count and sum cover the names that start with `prefix`."""
    n = total = 0
    other = None
    for line in body.splitlines():
        k, sep, v = line.partition(": ")
        if not sep or not (k.startswith(prefix) or k == beside):
            continue
        try:
            x = int(v.strip())
        except ValueError:
            continue
        if k == beside:
            other = x
            continue
        total += x
        n += 1
    return n, total, other


def stat_count(port, prefix, timeout=5.0):
    """{n, sum, requests, read_s}: how many counters whose name starts with `prefix` exist, the
    sum of their values, and Envoy's completed-request counter from the same read, so the sum
    has a request count taken with it (measure.stat_count_prefix). One admin read of counters
    only; with tens of thousands of them it takes a while, so it runs outside the response
    count's time base. A failed read raises: the leg is then invalid, never counted as zero stats."""
    t = time.monotonic()
    flt = "^(%s|%s$)" % (re.escape(prefix), re.escape(STAT_COUNT_REQUESTS))
    st, body = admin_get(port, "/stats?type=Counters&filter=" + urllib.parse.quote(flt), timeout=timeout)
    if st != 200:
        raise RuntimeError("admin /stats (counters %s*) returned %d" % (prefix, st))
    n, total, rq = parse_stat_count(body, prefix)
    return {"n": n, "sum": total, "requests": rq, "read_s": round(time.monotonic() - t, 4)}


def stat_count_record(prefix, a, b, pre_window_s=None):
    """The leg's `stat_count` record from the reads before (a) and after (b) the window: the
    counts, how many stats appeared in between (a reconnect creates new per-connection
    counters), and the sum's change per request completed between the same two reads (None
    without Envoy's request counter: an arm that rejects every stat). `pre_window_s`: the time
    from the first read before the window to the window's start (it comes out of the client
    run's slack: lead-in + this + window must stay under the client's duration)."""
    rq = None if a["requests"] is None or b["requests"] is None else b["requests"] - a["requests"]
    return {"prefix": prefix, "start_n": a["n"], "end_n": b["n"], "new_in_window": b["n"] - a["n"],
            "sum_delta": b["sum"] - a["sum"], "requests_delta": rq,
            "sum_per_request": (b["sum"] - a["sum"]) / rq if rq else None,
            "start_read_s": a["read_s"], "end_read_s": b["read_s"], "pre_window_s": pre_window_s}


def wait_ready(port, timeout_s, proc):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if proc.poll() is not None:
            return False
        try:
            st, body = admin_get(port, "/ready", timeout=1.0)
            if st == 200 and "LIVE" in body:
                return True
        except OSError:
            pass
        time.sleep(0.2)
    return False


def parse_perf(text):
    """{event: value} from `perf stat -x ,`; events that did not count are left out."""
    return parse_perf_full(text)[0]


def parse_perf_per_thread(text):
    """{tid: {comm, event: value}} from `perf stat -x , --per-thread`: each line starts with
    <comm>-<tid>, then the count, unit, event."""
    out = {}
    for line in text.splitlines():
        f = line.split(",")
        if len(f) < 4 or "-" not in f[0]:
            continue
        comm, _, tid = f[0].rpartition("-")
        try:
            tid, v = int(tid), float(f[1])
        except ValueError:
            continue
        d = out.setdefault(tid, {"comm": comm})
        d[f[3]] = v
        if len(f) > 5:
            try:
                d.setdefault("_running_pct", {})[f[3]] = float(f[5])
            except ValueError:
                pass
    return out


def perf_totals(per_thread):
    """({event: sum over threads}, {event: lowest running percent}) from parse_perf_per_thread."""
    tot, run = {}, {}
    for d in per_thread.values():
        for k, v in d.items():
            if k in ("comm", "_running_pct"):
                continue
            tot[k] = tot.get(k, 0.0) + v
        for k, p in (d.get("_running_pct") or {}).items():
            run[k] = min(run.get(k, 100.0), p)
    return tot, run


def parse_perf_full(text):
    """({event: value}, {event: percent of the window the counter was running})."""
    v, run = {}, {}
    for line in text.splitlines():
        f = line.split(",")
        if len(f) < 3:
            continue
        try:
            v[f[2]] = float(f[0])
        except ValueError:
            continue
        if len(f) > 4:
            try:
                run[f[2]] = float(f[4])
            except ValueError:
                pass
    return v, run


SEGS_RE = re.compile(r"\bsegs_in:(\d+)")


def conn_usage(filter_expr, save_path=None):
    """Per-connection inbound segment counts from `ss -tin`, summarised.

    Shows whether traffic spreads over all connections or a few carry it. With
    save_path the raw `ss` text is kept (gzip), so the summary can be recomputed."""
    try:
        r = subprocess.run(["ss", "-tinH", "state", "established", filter_expr],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with gzip.open(save_path, "wt") as f:
            f.write(r.stdout)
    segs = sorted((int(x) for x in SEGS_RE.findall(r.stdout)), reverse=True)
    if not segs:
        return {"conns": 0}
    tot = float(sum(segs)) or 1.0
    med = segs[len(segs) // 2]
    return {"conns": len(segs), "segs_total": int(tot),
            "conns_over_1pct_of_mean": sum(1 for x in segs if x > 0.01 * tot / len(segs)),
            "top16_share": round(sum(segs[:16]) / tot, 4),
            "max": segs[0], "median": med, "min": segs[-1]}


def _delta(a, b, key):
    return b.get(key, 0) - a.get(key, 0)


def _worker_share(threads, workers, pid):
    """Busiest and least busy Envoy worker's share of worker CPU in the window."""
    wb = [t["busy"] for t in threads.values() if t["comm"].startswith("wrk:")]
    # The worker count comes from the config; a configured worker
    # without a wrk: thread counts as idle, so it fails the floor.
    # (an arm whose extra_args raise the count is judged on what ran).
    nw = max(int(workers), len(wb))
    out = {"envoy_workers": nw, "envoy_worker_threads_found": len(wb)}
    if not wb:
        out["envoy_worker_probe"] = "no wrk: thread in /proc/%d/task" % pid
    elif sum(wb) <= 0:
        out["envoy_worker_probe"] = "worker threads used no CPU in the window"
    else:
        wb = wb + [0.0] * max(0, nw - len(wb))
        # 1/workers = perfectly even; 1.0 = one worker did everything
        out["envoy_worker_max_share"] = round(max(wb) / sum(wb), 4)
        out["envoy_worker_min_share"] = round(min(wb) / sum(wb), 4)
        out["envoy_worker_share"] = [round(x / sum(wb), 4) for x in wb]
    return out


def _stat_end(q1):
    return {k: v for k, v in sorted(q1.items()) if END_KEYS_RE.search(k) and v}


def _worker_busy(threads):
    """Busiest and least busy Envoy worker, as a fraction of one CPU."""
    wb = [t["busy"] for t in threads.values() if t["comm"].startswith("wrk:")]
    return {"worker_max_busy": round(max(wb), 4), "worker_min_busy": round(min(wb), 4)} if wb else {}


def _stat_deltas(q0, q1):
    return {k: q1[k] - q0.get(k, 0) for k in sorted(q1) if DELTA_KEYS_RE.search(k) and q1[k] != q0.get(k, 0)}


def parse_prometheus(text):
    """{(type, name with labels): value} of an Envoy /stats/prometheus page (counters, gauges and
    histogram _count / _sum samples)."""
    types, out = {}, {}
    for line in (text or "").splitlines():
        if line.startswith("# TYPE "):
            parts = line.split()
            if len(parts) >= 4:
                types[parts[2]] = parts[3]
            continue
        if not line or line.startswith("#"):
            continue
        key, _, val = line.rpartition(" ")
        base = key.split("{", 1)[0]
        fam = base
        for suf in ("_count", "_sum", "_bucket"):
            if base.endswith(suf) and types.get(base[: -len(suf)]) == "histogram":
                fam = base[: -len(suf)]
        t = types.get(fam)
        if t is None:
            continue
        try:
            out[(t if fam == base else t + base[len(fam):], key)] = float(val)
        except ValueError:
            pass
    return out


def stat_ops(p0, p1, apart=None):
    """Store-stat operations over a window from two /stats/prometheus snapshots: counter
    increments (the sum of counter deltas, byte counters left out because they add sizes, not
    one per event), histogram samples (the _count deltas), and the counters that changed.
    Gauge updates cannot be counted from snapshots (an inc and a dec cancel).
    `apart`: counters whose Prometheus name starts with it (an experiment's own generated
    counters, tens of thousands of names) are summed on their own (`apart_incs`, `apart_changed`)
    and stay out of the other figures and of the name list."""
    inc = samples = a_inc = 0.0
    changed = []
    a_changed = 0
    for (t, k), v in p1.items():
        d = v - p0.get((t, k), 0.0)
        if t == "counter" and d:
            if apart and k.startswith(apart):
                a_inc += d
                a_changed += 1
                continue
            changed.append(k)
            if "bytes" not in k:
                inc += d
        elif t == "histogram_count" and d:
            samples += d
    out = {"counter_incs": inc, "histogram_samples": samples, "counters_changed": sorted(changed)}
    if apart:
        out.update(apart=apart, apart_incs=a_inc, apart_changed=a_changed)
    return out


def prometheus_prefix(stat_prefix):
    """The Prometheus name prefix of the stats under a flat-name prefix (dose. -> envoy_dose_)."""
    return "envoy_" + re.sub(r"[^A-Za-z0-9_]", "_", stat_prefix)


def admin_prometheus(port, timeout=5.0):
    st, body = admin_get(port, "/stats/prometheus?usedonly", timeout=timeout)
    if st != 200:
        raise RuntimeError("admin /stats/prometheus returned %d" % st)
    return parse_prometheus(body)


def _stat_window(q0, q1):
    """Every filtered stat's change over the window, zeros included, so evidence can tell a
    counter that stayed at 0 from one that does not exist (gauges come out as changes too)."""
    return {k: q1[k] - q0.get(k, 0) for k in sorted(q1)}


JSON_CHECK_LINES = 100


def json_lines_check(path, n=JSON_CHECK_LINES):
    """Parse the first and the last n lines of a JSON access log. {checked, bad, first_error}."""
    with open(path, "rb") as f:
        head = []
        for _ in range(n):
            ln = f.readline()
            if not ln:
                break
            head.append(ln)
        f.seek(0, os.SEEK_END)
        size = f.tell()
        off = max(len(b"".join(head)), size - 256 * 1024)
        f.seek(off)
        tail = f.read().splitlines(True)
    if off > len(b"".join(head)) and tail:
        tail = tail[1:]  # the read started inside a line
    tail = tail[-n:]
    out = {"checked": 0, "bad": 0}
    for ln in head + tail:
        ln = ln.strip()
        if not ln:
            continue
        out["checked"] += 1
        try:
            if not isinstance(json.loads(ln.decode("utf-8", "replace")), dict):
                raise ValueError("not an object")
        except ValueError as e:
            out["bad"] += 1
            out.setdefault("first_error", str(e)[:120])
    return out


# timeline samples (measure.burst): pool and connection gauges and counters of each hop
TIMELINE_FILTER = (r"^(cluster\.origin\.upstream_(cx_active|cx_total|cx_destroy|cx_max_requests|cx_idle_timeout|"
                   r"cx_max_duration_reached|rq_active|rq_pending_active|rq_total)|"
                   r"http\.ingress_http\.downstream_(rq_2xx|cx_active)|"
                   r"listener\..*\.worker_[0-9]+\.downstream_cx_active)$")
RQ_TIME_FILTER = r"^http\.ingress_http\.downstream_rq_time$"
QUANTILE_RE = re.compile(r"P([0-9.]+)\(([^,()]+),([^,()]+)\)")


def parse_quantiles(line):
    """{quantile: (interval, cumulative)} from an admin histogram line, e.g.
    `x: P0(nan,0) P50(1.05,1.1) ...`; nan becomes None."""
    out = {}
    for q, a, b in QUANTILE_RE.findall(line or ""):
        vals = []
        for v in (a, b):
            try:
                f = float(v)
                vals.append(None if f != f else f)
            except ValueError:
                vals.append(None)
        out[q] = tuple(vals)
    return out


def worker_run_ns(pid):
    """{comm: ns run} for the wrk: threads of pid (schedstat, ns resolution)."""
    out = {}
    base = "/proc/%d/task" % pid
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
            with open("%s/%s/schedstat" % (base, t)) as f:
                out[comm] = int(f.read().split()[0])
        except (OSError, ValueError, IndexError):
            continue
    return out


class Timeline(threading.Thread):
    """Samples both hops once per `sample_s` from the start of the perf window and,
    at `at_s`, freezes the second hop for `pause_hop2_ms` (SIGSTOP, then SIGCONT, to
    the PID this run started): a stalled next hop, during which the first hop's
    pool grows by rate x pause. Every sample: per-worker scheduler run time of
    each hop, pool and listener gauges, and the first hop's downstream_rq_time
    quantiles (interval values change once per stats flush)."""

    def __init__(self, cfg, own, envoy, hop_b, admin_a, admin_b, t0):
        super().__init__(daemon=True)
        self.cfg, self.own, self.envoy, self.hop_b = cfg, own, envoy, hop_b
        self.admin_a, self.admin_b, self.t0 = admin_a, admin_b, t0
        self.stop_evt = threading.Event()
        self.samples, self.burst, self.errors = [], None, []

    def _stats(self, port):
        st, body = admin_get(port, "/stats?filter=" + urllib.parse.quote(TIMELINE_FILTER), timeout=2.0)
        out = {}
        for line in body.splitlines() if st == 200 else []:
            if ": " in line:
                k, v = line.split(": ", 1)
                try:
                    out[k.strip()] = int(v.strip())
                except ValueError:
                    pass
        return out

    def _sample(self):
        s = {"t": round(time.monotonic() - self.t0, 4)}
        s["a_wrk"] = worker_run_ns(self.envoy.pid)
        s["b_wrk"] = worker_run_ns(self.hop_b.pid) if self.hop_b else {}
        s["t_proc"] = round(time.monotonic() - self.t0, 4)
        try:
            s["a"] = self._stats(self.admin_a)
            if self.hop_b:
                s["b"] = self._stats(self.admin_b)
            st, body = admin_get(self.admin_a, "/stats?filter=" + urllib.parse.quote(RQ_TIME_FILTER), timeout=2.0)
            q = parse_quantiles(body) if st == 200 else {}
            s["a_rq_time_ms"] = {k: q[k] for k in ("50", "90", "99", "99.9", "100") if k in q}
        except OSError as e:
            self.errors.append("t=%.1f: %s" % (s["t"], e))
        return s

    def _pause(self):
        hb = self.hop_b
        if hb is None or hb.pid not in self.own.procs or hb.poll() is not None:
            self.burst = {"error": "no running second hop started by this run"}
            return
        ms = float(self.cfg["pause_hop2_ms"])
        t_rel = time.monotonic() - self.t0
        a = time.perf_counter()
        os.kill(hb.pid, signal.SIGSTOP)
        try:
            time.sleep(ms / 1000.0)
        finally:
            os.kill(hb.pid, signal.SIGCONT)
        b = time.perf_counter()
        self.burst = {"method": "pause_hop2", "t": round(t_rel, 4), "pause_ms_target": ms,
                      "pause_ms_actual": round((b - a) * 1000.0, 3)}

    def run(self):
        period = float(self.cfg.get("sample_s", 1.0))
        at = float(self.cfg["at_s"])
        k = 0
        while not self.stop_evt.is_set():
            target = self.t0 + k * period
            if self.burst is None and "pause_hop2_ms" in self.cfg and time.monotonic() - self.t0 >= at:
                self._pause()
                continue
            delay = target - time.monotonic()
            if self.burst is None and "pause_hop2_ms" in self.cfg:
                delay = min(delay, self.t0 + at - time.monotonic())
            if delay > 0:
                if self.stop_evt.wait(delay):
                    break
                continue
            self.samples.append(self._sample())
            k += 1


TCMALLOC_PERCPU_RE = re.compile(r"MALLOC:\s+(\d+)\s+\([^)]*\)\s+per-CPU slab bytes used")


def tcmalloc_percpu(port):
    """Bytes in tcmalloc's per-CPU slabs from admin /memory/tcmalloc (0 = per-CPU
    caches inactive), or None when the endpoint or the line is missing."""
    try:
        st, body = admin_get(port, "/memory/tcmalloc", timeout=5.0)
    except OSError:
        return None
    mm = TCMALLOC_PERCPU_RE.search(body) if st == 200 else None
    return int(mm.group(1)) if mm else None


def _count_lines(path):
    n, size = 0, 0
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            n += b.count(b"\n")
            size += len(b)
    return n, size


def _nofile_preexec(soft):
    def f():
        import resource
        cur_soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        want = soft if hard == resource.RLIM_INFINITY else min(soft, hard)
        resource.setrlimit(resource.RLIMIT_NOFILE, (max(cur_soft, want), hard))
    return f


def _primes(arm, shape):
    """Primed is the default; an arm or a shape with prime: false runs cold."""
    return arm.get("prime", True) and shape.get("prime", True)


def nofile_for(aenv, exp=None):
    """Soft fd limit for an Envoy with generated clusters: 4 x clusters + 4,096 plus a margin,
    or the configured envoy.nofile; None leaves the inherited limit."""
    n = (exp or {}).get("envoy", {}).get("nofile")
    if n:
        return int(n)
    sc = aenv.get("stats_clusters")
    return 4 * int(sc["count"]) + 4096 + 1024 if sc else None


# ---------------------------------------------------------------- rungs (multi-threaded stats)

def rung_of(e, shape):
    """A shape may be a rung: `workers` (the concurrency), `worker_cpus` (their set) and
    `main_cpu` (the main thread's one core, outside the worker set, the same at every rung).
    Returns {workers, main_cpu, worker_set, sut_set, start_cpus}; without them the
    experiment's envoy.workers and cpus.sut as before."""
    if shape.get("main_cpu") is None:
        return {"workers": int(shape.get("workers") or e["envoy"]["workers"]), "main_cpu": None,
                "worker_set": None, "sut_set": sysprobe.parse_cpuset(e["cpus"]["sut"]),
                "start_cpus": e["cpus"]["sut"]}
    ws = sysprobe.parse_cpuset(shape["worker_cpus"])
    main = int(shape["main_cpu"])
    return {"workers": int(shape["workers"]), "main_cpu": main, "worker_set": ws, "sut_set": ws | {main},
            "start_cpus": str(main), "one_to_one": shape.get("worker_pin") == "one_to_one"}


# /proc root of the thread helpers below (a test points it at a made-up tree)
PROC = "/proc"
WORKER_COMM_RE = re.compile(r"^wrk:worker_(\d+)$")


def _wrk_comms(pid):
    out = {}
    for t in _wrk_tids(pid):
        try:
            with open("%s/%d/task/%d/comm" % (PROC, pid, t)) as f:
                out[t] = f.read().strip()
        except OSError:
            continue
    return out


def one_to_one_plan(comms, worker_set):
    """{tid: cpu} for `worker_pin: one_to_one`: wrk:worker_i goes on the i-th CPU (ascending) of
    the worker set. None unless the threads are exactly worker_0..n-1, one per CPU."""
    cpus = sorted(worker_set)
    plan = {}
    for tid, comm in comms.items():
        mm = WORKER_COMM_RE.match(comm or "")
        if not mm or int(mm.group(1)) >= len(cpus):
            return None
        plan[tid] = cpus[int(mm.group(1))]
    return plan if sorted(plan.values()) == cpus else None


def _set_affinity(tid, cpus):
    os.sched_setaffinity(tid, cpus)


def _wrk_tids(pid):
    out = []
    try:
        tids = os.listdir("%s/%d/task" % (PROC, pid))
    except OSError:
        return out
    for t in tids:
        try:
            with open("%s/%d/task/%s/comm" % (PROC, pid, t)) as f:
                if f.read().startswith("wrk:"):
                    out.append(int(t))
        except OSError:
            continue
    return sorted(out)


def _last_cpu(pid, tid):
    try:
        with open("%s/%d/task/%d/stat" % (PROC, pid, tid)) as f:
            return int(f.read().rsplit(")", 1)[1].split()[36])
    except (OSError, ValueError, IndexError):
        return None


def _allowed(pid, tid):
    try:
        with open("%s/%d/task/%d/status" % (PROC, pid, tid)) as f:
            for line in f:
                if line.startswith("Cpus_allowed_list:"):
                    return sysprobe.parse_cpuset(line.split(":", 1)[1].strip())
    except OSError:
        return None
    return None


def pin_check(pid, main_cpu, worker_set, workers, one_to_one=False):
    """Main thread (tid = pid) allowed on main_cpu only and last on it; every wrk: thread
    allowed on the worker set and last inside it; as many wrk: threads as workers.
    one_to_one: every wrk:worker_i allowed on its one CPU only (one_to_one_plan) and last on it."""
    wt = _wrk_tids(pid)
    main_ok = _allowed(pid, pid) == {main_cpu} and _last_cpu(pid, pid) == main_cpu
    if one_to_one:
        plan = one_to_one_plan(_wrk_comms(pid), worker_set)
        if plan is None or sorted(plan) != wt:
            return {"ok": False, "main_ok": main_ok, "workers_found": len(wt), "bad_workers": wt[:8],
                    "error": "worker threads are not wrk:worker_0..%d, one per CPU" % (len(worker_set) - 1)}
        bad = [t for t in wt if _allowed(pid, t) != {plan[t]} or _last_cpu(pid, t) != plan[t]]
        return {"ok": main_ok and len(wt) == workers and not bad, "main_ok": main_ok, "workers_found": len(wt),
                "bad_workers": bad[:8], "one_to_one": {str(t): plan[t] for t in wt}}
    bad = [t for t in wt if _allowed(pid, t) != worker_set or _last_cpu(pid, t) not in worker_set]
    return {"ok": main_ok and len(wt) == workers and not bad, "main_ok": main_ok, "workers_found": len(wt),
            "bad_workers": bad[:8]}


def pin_rung(pid, main_cpu, worker_set, workers, wait_s=10.0, one_to_one=False):
    """Move every wrk: thread of the Envoy this run started onto the worker set (the process
    started on the main core only), then verify; the leg only proceeds when this holds.
    one_to_one: each wrk:worker_i onto its own CPU of the set."""
    end = time.monotonic() + wait_s
    while len(_wrk_tids(pid)) < workers and time.monotonic() < end:
        time.sleep(0.05)
    plan = None
    if one_to_one:
        plan = one_to_one_plan(_wrk_comms(pid), worker_set)
        if plan is None:
            return {"ok": False, "error": "worker threads are not wrk:worker_0..%d: %s" % (
                len(worker_set) - 1, sorted(_wrk_comms(pid).values())[:8])}
    for t in _wrk_tids(pid):
        try:
            _set_affinity(t, {plan[t]} if plan else worker_set)
        except (OSError, KeyError) as ex:
            return {"ok": False, "error": "could not move %d: %s" % (t, ex)}
    time.sleep(0.2)  # let each moved thread run once on its new set
    r = pin_check(pid, main_cpu, worker_set, workers, one_to_one)
    if not r["ok"]:
        # a thread that has not run since the move still shows its old last CPU: check once more
        time.sleep(1.0)
        r = pin_check(pid, main_cpu, worker_set, workers, one_to_one)
    return r


def lat_client_duration(base_s, lat, arm_name, count_read_s):
    """Client duration of a run-L leg: the configured one plus, for each of the two count reads,
    the longest flush it may have to wait for (`flush_allow_s`, per arm) and the read itself
    (`read_allow_factor` x the time of one read on the idle Envoy)."""
    fa = lat["flush_allow_s"]
    allow = float(fa.get(arm_name, fa["default"]) if isinstance(fa, dict) else fa)
    return int(base_s + math.ceil(2.0 * (allow + float(lat["read_allow_factor"]) * count_read_s)))


def cluster_sum(numeric, suffix):
    """Sum of cluster.<any>.<suffix> over every cluster of a stats read."""
    return sum(v for k, v in numeric.items() if k.startswith("cluster.") and k.endswith("." + suffix))


def lat_count(n0, n1, nh_2xx, probe_rows, map_requests):
    """The listener's 2xx count between the leg's two quiescent reads against its three sources:
    Nighthawk's 2xx, the probe's answered data requests and the map phase's requests. No time
    base: the three must add up exactly. A missing part leaves `error` out (the gate fails)."""
    k = "http.ingress_http.downstream_rq_2xx"
    answered = sum(1 for r in probe_rows if r[0] == "d" and r[5] is not None and r[6] == 200)
    out = {"listener_2xx": n1[k] - n0[k] if k in n0 and k in n1 else None, "nighthawk_2xx": nh_2xx,
           "probe_answered": answered, "map_requests": map_requests}
    if None not in out.values():
        out["expected"] = nh_2xx + answered + map_requests
        out["error"] = out["listener_2xx"] - out["expected"]
    return out


def timer_lines_expected(n):
    """Timer (ms) lines the statsd sink must have sent by a stats read, from Envoy's own counters
    of that read: three per proxied request (downstream, upstream and the cluster's external
    request time), one per admin request, two per closed downstream connection (connection
    manager and listener length), one per upstream connect and one per upstream close.
    None when a counter is missing."""
    need = ("http.ingress_http.downstream_rq_completed", "http.admin.downstream_rq_completed",
            "http.ingress_http.downstream_cx_destroy", "http.admin.downstream_cx_destroy")
    if any(k not in n for k in need):
        return None
    parts = {"requests": 3 * n[need[0]], "admin_requests": n[need[1]],
             "downstream_closes": 2 * (n[need[2]] + n[need[3]]),
             "upstream_connects": cluster_sum(n, "upstream_cx_total"),
             "upstream_closes": cluster_sum(n, "upstream_cx_destroy")}
    parts["total"] = sum(parts.values())
    return parts


def clock_pair():
    """(CLOCK_MONOTONIC, wall clock) read together, as the probe records its own."""
    a = time.monotonic_ns()
    w = time.time_ns()
    b = time.monotonic_ns()
    return {"monotonic_ns": (a + b) // 2, "time_ns": w, "read_ns": b - a}


def client_kw(ccfg):
    """Popen keywords for the client: a soft fd limit (client.nofile) for this child only."""
    return {"preexec_fn": _nofile_preexec(int(ccfg["nofile"]))} if ccfg.get("nofile") else {}


def client_for(ccfg, shape):
    """A rung fixes the client's workers and connections per worker (`client_concurrency`,
    `client_connections_per_worker`), so connections per Envoy worker are the same at every rung."""
    c = dict(ccfg)
    if shape.get("client_concurrency"):
        c["concurrency"] = int(shape["client_concurrency"])
    if shape.get("client_connections_per_worker"):
        c["connections_per_worker"] = int(shape["client_connections_per_worker"])
    return c


def parse_stub_status(text):
    """`requests` of an nginx stub_status page (the third number of its counters line)."""
    lines = (text or "").splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith("server accepts handled requests") and i + 1 < len(lines):
            try:
                return int(lines[i + 1].split()[2])
            except (IndexError, ValueError):
                return None
    return None


def origin_requests(e):
    try:
        st, body = admin_get(e["origin"]["port"], envoy_config.ORIGIN_STATUS_PATH, timeout=5.0)
    except OSError:
        return None
    return parse_stub_status(body) if st == 200 else None


def parse_numastat(text):
    """{node: MB} from the Total line of `numastat -p PID`."""
    lines = (text or "").splitlines()
    head = None
    for ln in lines:
        f = ln.split()
        if f and f[0] == "Node" and head is None:
            head = [x for x in f if x not in ("Node",) and x != "Total"]
        if f and f[0] == "Total" and head:
            vals = f[1:1 + len(head)]
            try:
                return {"node%s" % h: float(v) for h, v in zip(head, vals)}
            except ValueError:
                return None
    return None


def numastat_totals(pid):
    try:
        r = subprocess.run(["numastat", "-p", str(pid)], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as ex:
        return {"error": str(ex)}
    return parse_numastat(r.stdout) or {"error": "no Total line"}


def sysprobe_steal():
    """(total jiffies, steal jiffies) of the first line of /proc/stat."""
    try:
        with open("/proc/stat") as f:
            v = [int(x) for x in f.readline().split()[1:]]
    except (OSError, ValueError):
        return None
    return (sum(v[:8]), v[7]) if len(v) >= 8 else None


def steal_share(a, b):
    tot = b[0] - a[0]
    return (b[1] - a[1]) / tot if tot > 0 else 0.0


IDLE_KEEP_RE = re.compile(r"^(server\.|cluster_manager\.|.*watchdog|http\.ingress_http\.|"
                          r"cluster\.(origin|otel_collector)\.|stats\.|runtime\.)")
EMFILE_RE = re.compile(r"(?i)(too many open files|EMFILE)")


class RealBackend:
    def __init__(self, exp, run_dir, log):
        self.exp = exp
        self.run_dir = run_dir
        self.log = log
        self.own = OwnProcesses()
        self.perf = exp["measure"]["perf"]
        # Idle-state configuration of the SUT CPUs and their siblings at the start
        # of the run; every leg re-reads it and a change invalidates the leg.
        self.idle_cpus = self._idle_cpus()
        self.cpuidle_fp0 = sysprobe.cpuidle_fingerprint(self.idle_cpus)
        self.side = []           # SideService objects of the containers this run started
        self.side_expected = []  # names of the containers this run started
        self.collector = None    # origin.Collector, for its span counters
        self.config_dumps = {}   # arm -> parsed /config_dump at its first start
        self.stats_saved = set()

    def attach(self, origin=None, collector=None):
        """The side services the run started; their CPU and placement are gated per leg.
        A container whose cgroup could not be read is recorded as such and fails the gate."""
        self.side = []
        self.side_expected = []
        for name, svc in (("origin", origin), ("collector", collector)):
            if svc is None or not getattr(svc, "container_id", None):
                continue
            self.side_expected.append(name)
            if svc.side is not None:
                self.side.append(svc.side)
        self.collector = collector

    def _save_config_dump(self, arm, port, timeout=10.0):
        """/config_dump of the arm at its first start, kept gzipped in the run directory."""
        if arm in self.config_dumps:
            return
        st, body = admin_get(port, "/config_dump", timeout=timeout)
        if st != 200:
            raise RuntimeError("admin /config_dump returned %d" % st)
        d = os.path.join(self.run_dir, "config_dump")
        os.makedirs(d, exist_ok=True)
        with gzip.open(os.path.join(d, arm + ".json.gz"), "wt") as f:
            f.write(body)
        self.config_dumps[arm] = json.loads(body)

    def _save_stats(self, arm, port, timeout=10.0):
        """Every stat name and value at the end of the arm's first leg (for freezing evidence names)."""
        if arm in self.stats_saved:
            return
        st, body = admin_get(port, "/stats", timeout=timeout)
        if st == 200:
            d = os.path.join(self.run_dir, "stats")
            os.makedirs(d, exist_ok=True)
            with gzip.open(os.path.join(d, arm + ".txt.gz"), "wt") as f:
                f.write(body)
            self.stats_saved.add(arm)

    def _idle_cpus(self):
        c = sysprobe.parse_cpuset(self.exp["cpus"]["sut"]) | sysprobe.parse_cpuset(self.exp["cpus"].get("hop2", ""))
        return c | sysprobe.siblings_of(c)

    def own_pids(self):
        return self.own.pids()

    def _start_envoy(self, binary, bootstrap, cpus, workers, admin_port, env, extra, log_path, ready_timeout_s=60,
                     nofile=None):
        """nofile: soft RLIMIT_NOFILE for this child only (set before exec; never a system change)."""
        elog = open(log_path, "w")
        cmd = ["taskset", "-c", cpus, binary, "-c", bootstrap, "--concurrency", str(workers),
               "--use-dynamic-base-id", "-l", self.exp["envoy"].get("log_level", "warn")] + list(extra)
        kw = {}
        if nofile:
            kw["preexec_fn"] = _nofile_preexec(int(nofile))
        p = self.own.start(cmd, stdout=elog, stderr=subprocess.STDOUT, env=dict(os.environ, **env), **kw)
        if not wait_ready(admin_port, ready_timeout_s, p):
            raise RuntimeError("envoy (%s) not ready (exit %s)" % (os.path.basename(bootstrap), p.poll()))
        exe = os.path.realpath("/proc/%d/exe" % p.pid)
        if exe != os.path.realpath(binary):
            raise RuntimeError("envoy pid %d runs %s, expected %s" % (p.pid, exe, binary))
        return p, elog

    def _stop_envoy(self, p, elog, log_path):
        rc = self.own.stop(p)
        elog.close()
        out = {"exit": rc}
        try:
            with open(log_path) as f:
                txt = f.read()
            out["deprecated_lines"] = len(re.findall(r"(?i)deprecat", txt))
            out["log_bytes"] = len(txt)
        except OSError:
            pass
        return out

    def run_leg(self, arm, shape, rnd, bootstrap_path, leg_id):
        e = self.exp
        ecfg, ccfg, mcfg = e["envoy"], e["client"], e["measure"]
        if shape.get("lead_in_s") is not None:
            # a shape may start its window later (a client that ramps its rate up)
            mcfg = dict(mcfg, lead_in_s=shape["lead_in_s"])
        m = {"leg_id": leg_id, "arm": arm["name"], "shape": shape["name"], "round": rnd,
             "target_rps": shape["rps"], "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        aenv = _exp.arm_envoy(e, arm, self.run_dir)
        two_hop = bool(aenv.get("two_hop"))
        # gate overrides: shape first, then arm (an arm that is meant to measure a
        # concentrated second hop turns its share gate off for itself only)
        vcfg = dict(e["validity"], **(shape.get("validity") or {}))
        vcfg.update(arm.get("validity") or {})
        bpath_b = bootstrap_path.get(_exp.hop2_key(arm)) if isinstance(bootstrap_path, dict) else None
        if isinstance(bootstrap_path, dict):
            bootstrap_path = bootstrap_path[arm["name"]]
        hop2_set = sysprobe.parse_cpuset(e["cpus"].get("hop2", ""))
        rung = rung_of(e, shape)
        workers = rung["workers"]
        sut_set = rung["sut_set"]
        # run L (measure.latency): the open-loop probe beside the client, the thread series kept
        lat = mcfg.get("latency") if shape["kind"] != "idle" else None
        lx = None
        if lat:
            # the listener's rate is the client's plus the probe's data stream
            m["client_target_rps"] = shape["rps"]
            m["target_rps"] = shape["rps"] + int(round(float(lat["data_conns"]) * float(lat["data_hz"])))
        if rung["main_cpu"] is not None:
            m.update(rung_workers=workers, rung_worker_cpus=shape["worker_cpus"], rung_main_cpu=rung["main_cpu"])
        # the during-window checks cover every hop's CPUs (an idle hop2 set must stay idle)
        sut_set = sut_set | hop2_set
        sib_set = sysprobe.siblings_of(sut_set)
        # 1. idle
        ok, det, waited = sysprobe.wait_idle(e["idle"], self.own_pids(), log=self.log,
                                             watch_cpus=sut_set | sib_set)
        m.update(idle_ok=ok, idle_detail=det, idle_wait_s=round(waited, 1))
        m["cpuidle_fingerprint"] = sysprobe.cpuidle_fingerprint(self.idle_cpus)
        m["cpuidle_unchanged"] = m["cpuidle_fingerprint"] == self.cpuidle_fp0
        # 2. port preflight
        must_open = [e["origin"]["port"]] if shape["kind"] == "proxied" or (
            aenv.get("stats_clusters") and _primes(arm, shape)) else []
        if aenv.get("ext_authz"):
            must_open.append(aenv["authz_grpc_port"] if aenv["ext_authz"] == "grpc" else aenv["authz_port"])
        if aenv.get("tracing") or (aenv.get("stats_sink") or {}).get("kind") == "otlp":
            must_open.append(aenv["collector_port"])
            if e["collector"].get("metrics_port"):
                must_open.append(int(e["collector"]["metrics_port"]))
        free = [ecfg["listener_port"], ecfg["admin_port"]]
        if aenv.get("stats_sink_port"):
            free.append(int(aenv["stats_sink_port"]))
        if hop2_set:
            free += [e["hop2"]["listener_port"], e["hop2"]["admin_port"]]
        ok, det = sysprobe.port_preflight(free, must_open)
        m.update(preflight_ok=ok, preflight_detail=det)
        if not (m["idle_ok"] and m["preflight_ok"]):
            m["verdict"] = validity.verdict(m, vcfg)
            return m
        if shape["kind"] == "idle":
            return self._run_idle_leg(arm, shape, rnd, bootstrap_path, leg_id, m, aenv, vcfg)
        envoy = None
        hop_b = None
        sink = sink_out = sampler = None
        adm_t = float(shape.get("admin_timeout_s", 5.0))
        sfx = mcfg.get("stat_filter_extra")
        scp = mcfg.get("stat_count_prefix")
        side_u0 = {}
        if self.side_expected:
            # placement of every side-service process, read before Envoy starts
            m["side_services"] = {n: {"error": "cgroup not readable"} for n in self.side_expected}
            for svc in self.side:
                try:
                    m["side_services"][svc.name] = svc.placement()
                except OSError as ex:
                    m["side_services"][svc.name] = {"error": "placement unreadable: %s" % ex}
        coll0 = self.collector.scrape() if self.collector and (
            aenv.get("tracing") or (aenv.get("stats_sink") or {}).get("kind") == "otlp") else None
        alog = (aenv.get("access_log") or {}).get("path")
        if alog:
            with open(alog, "w"):
                pass  # the harness owns this file; every leg starts it empty
        try:
            env = dict(arm.get("env") or {})
            pin_ok = True
            # 3. Envoy (the second hop first, so the first hop's upstream is up)
            if two_hop:
                blog = os.path.join(self.run_dir, "logs", leg_id + ".envoy-hop2.log")
                # the second hop gets the arm's env unless the arm gives it its own (`hop2_env`)
                env_b = dict(arm["hop2_env"]) if "hop2_env" in arm else env
                hop_b, belog = self._start_envoy(arm["binary"], bpath_b, e["cpus"]["hop2"], ecfg["workers"],
                                                 e["hop2"]["admin_port"], env_b, arm.get("extra_args", []), blog)
                m["hop2_pid"] = hop_b.pid
                m["hop2_cpus_allowed"] = sysprobe.cpus_allowed(hop_b.pid)
                pin_ok = sysprobe.parse_cpuset(m["hop2_cpus_allowed"]) == hop2_set
            elog_path = os.path.join(self.run_dir, "logs", leg_id + ".envoy.log")
            sink, sink_out = self._sink_start(aenv, leg_id)
            # a rung starts Envoy on the main core only (its stats are allocated there, at config
            # load) and moves the workers to their set once they exist
            envoy, elog = self._start_envoy(arm["binary"], bootstrap_path, rung["start_cpus"], workers,
                                            ecfg["admin_port"], env, arm.get("extra_args", []), elog_path,
                                            ready_timeout_s=float(shape.get("ready_timeout_s", 60)),
                                            nofile=nofile_for(aenv, e))
            m["envoy_pid"] = envoy.pid
            if rung["main_cpu"] is not None:
                m["rung_pin"] = pin_rung(envoy.pid, rung["main_cpu"], rung["worker_set"], workers,
                                         one_to_one=rung.get("one_to_one", False))
            if not sysprobe.port_open("127.0.0.1", ecfg["listener_port"]):
                raise RuntimeError("listener port not open after ready")
            self._save_config_dump(arm["name"], ecfg["admin_port"], timeout=max(10.0, adm_t))
            if aenv.get("stats_clusters"):
                lim = statsrow.parse_limits(statsrow.read("/proc/%d/limits" % envoy.pid))
                m["nofile_soft"], m["nofile_hard"] = lim if lim else (None, None)
            self._prime(m, arm, shape, aenv)
            sut_cpus = sysprobe.cpus_allowed(envoy.pid)
            m["sut_cpus_allowed"] = sut_cpus
            if rung["main_cpu"] is not None:
                pin_ok = pin_ok and bool(m["rung_pin"].get("ok"))
            else:
                pin_ok = pin_ok and sysprobe.parse_cpuset(sut_cpus) == sysprobe.parse_cpuset(e["cpus"]["sut"])
            ccfg = client_for(ccfg, shape)
            scheme = "https" if aenv.get("tls") else "http"
            url = "%s://127.0.0.1:%d%s" % (scheme, ecfg["listener_port"], shape["path"])
            cextra = list(shape.get("client_extra_args") or [])
            nh = ccfg["binary"]
            # 4. warm-up (a shape may set its own length: the JIT warm-up check)
            warm_s = shape["warmup_s"] if shape.get("warmup_s") is not None else ccfg.get("warmup_s", 0)
            if warm_s > 0:
                wa = nighthawk.client_args(ccfg, shape["rps"], url, warm_s, False, cextra,
                                             shape.get("client_base_args"))
                w = self.own.start(["taskset", "-c", e["cpus"]["client"], nh] + wa,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **client_kw(ccfg))
                try:
                    w.wait(timeout=warm_s + 60)
                finally:
                    self.own.stop(w)
            if lat:
                # the reads at a quiescent point before the client starts, then the probe (its map
                # phase needs the listener to itself); the client starts once the probe is ready
                lx = self._lat_before(m, aenv, envoy, sink, leg_id, lat, adm_t, shape, workers)
            # 5. measured run
            dur = ccfg["duration_s"]
            if lat:
                # the two count reads around the window are served by the main thread: each walks
                # every stat (timed on this Envoy just now; slower beside the load and on a shared
                # core, hence the factor) and each may first wait for a whole flush. The client runs
                # longer by both, so the second read ends while it still sends.
                dur = lat_client_duration(dur, lat, arm["name"], lx["count_read_s"])
                m["lat_client_duration_s"] = dur
            nh_json = os.path.join(self.run_dir, "nighthawk", leg_id + ".json")
            ma = nighthawk.client_args(ccfg, shape["rps"], url, dur, True, cextra,
                                         shape.get("client_base_args"))
            m["client_args"] = ma
            with open(nh_json, "w") as out, open(os.path.join(self.run_dir, "logs", leg_id + ".client.log"), "w") as cerr:
                cl = self.own.start(["taskset", "-c", e["cpus"]["client"], nh] + ma, stdout=out, stderr=cerr,
                                    **client_kw(ccfg))
                try:
                    time.sleep(mcfg["lead_in_s"])
                    cl_cpus = sysprobe.cpus_allowed(cl.pid)
                    pin_ok = pin_ok and sysprobe.parse_cpuset(cl_cpus) == sysprobe.parse_cpuset(e["cpus"]["client"])
                    m["client_cpus_allowed"] = cl_cpus
                    c0 = sysprobe.proc_threads_cpu(cl.pid)
                    e0 = sysprobe.proc_threads_detail(envoy.pid)
                    b0 = sysprobe.proc_threads_detail(hop_b.pid) if hop_b else None
                    # smoke-only probe (measure.stat_ops_probe): every store stat around the window
                    t_reads0 = time.monotonic()
                    sp0 = admin_prometheus(ecfg["admin_port"], adm_t) if mcfg.get("stat_ops_probe") else None
                    # the stat count by prefix (measure.stat_count_prefix): before the window's
                    # first snapshot and after its time base ends, so a slow read is in neither
                    sc0 = stat_count(ecfg["admin_port"], scp, adm_t) if scp else None
                    t_q0 = time.monotonic()
                    q0 = admin_stats(ecfg["admin_port"], adm_t, sfx)
                    if lat:
                        lx["t_q0_end"] = time.monotonic()
                    from_origin = mcfg.get("responses_from") == "origin"
                    o0 = origin_requests(e) if from_origin else None
                    st0 = sysprobe_steal()
                    settle = float(shape.get("pre_window_settle_s") or 0)
                    if settle:
                        # an admin stats read flushes under stats_flush_on_admin: let that flush end
                        # before the window opens (the response count still brackets q0..q1)
                        time.sleep(settle)
                    u0 = statsrow.udp_counters(e["stats_sink"]["port"]) if sink else None
                    qb0 = admin_stats(e["hop2"]["admin_port"]) if hop_b else None
                    p0 = sysprobe.per_cpu_times()
                    k0 = sysprobe.proc_run_ns(envoy.pid)
                    kb0 = sysprobe.proc_run_ns(hop_b.pid) if hop_b else 0
                    r0, rwhy0 = sysprobe.cpu_run_ns()
                    side_u0 = {svc.name: svc.usage_us() for svc in self.side}
                    i0 = sysprobe.cpuidle_counts(sut_set)
                    t0 = time.monotonic()
                    events = perf_events(mcfg, rnd)
                    if events != PERF_EVENTS:
                        m["perf_events"] = events
                    per_thread = ["--per-thread"] if mcfg.get("per_thread") else []
                    pcmd = lambda pid: self.perf + ["stat", "-x", ",", "-e", events] + per_thread + [  # noqa: E731
                        "-p", str(pid), "--", "sleep", str(mcfg["window_s"])]
                    if lat:
                        # main and every worker, run time and run-queue wait, from the sampler's CPU
                        sampler = statsrow.ThreadSampler(
                            envoy.pid, [envoy.pid] + _wrk_tids(envoy.pid), float(lat["sample_s"]),
                            sysprobe.parse_cpuset(e["cpus"]["sampler"]),
                            udp_port=e["stats_sink"]["port"] if sink else None)
                        lx["clock"].append(clock_pair())
                        lx["t0"] = t0 = time.monotonic()
                        sampler.start()
                    elif mcfg.get("main_sampler"):
                        sampler = statsrow.MainSampler(envoy.pid, envoy.pid, float(mcfg.get("main_sample_s", 0.02)),
                                                       sysprobe.parse_cpuset(e["cpus"]["client"]))
                        sampler.start()
                    pb = subprocess.Popen(pcmd(hop_b.pid), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True) if hop_b else None
                    tl = None
                    if mcfg.get("burst"):
                        tl = Timeline(mcfg["burst"], self.own, envoy, hop_b, ecfg["admin_port"],
                                      e["hop2"]["admin_port"], t0)
                        tl.start()
                    try:
                        pr = subprocess.run(pcmd(envoy.pid), capture_output=True, text=True,
                                            timeout=mcfg["window_s"] + 60)
                        pb_err = pb.communicate(timeout=mcfg["window_s"] + 60)[1] if pb else None
                    finally:
                        if tl:
                            tl.stop_evt.set()
                            tl.join(timeout=30)
                    t1 = time.monotonic()
                    if sampler:
                        sampler.stop_evt.set()
                        sampler.join(timeout=10)
                    if lat:
                        lx["t1"] = t1
                        lx["clock"].append(clock_pair())
                        lx["sampler"] = sampler
                        sampler.samples = sampler.main_samples(envoy.pid)
                    u1 = statsrow.udp_counters(e["stats_sink"]["port"]) if sink else None
                    if tl:
                        tdir = os.path.join(self.run_dir, "timeline")
                        os.makedirs(tdir, exist_ok=True)
                        with gzip.open(os.path.join(tdir, leg_id + ".json.gz"), "wt") as f:
                            json.dump({"leg_id": leg_id, "burst": tl.burst, "samples": tl.samples,
                                       "errors": tl.errors}, f)
                        m["burst"] = tl.burst
                        m["timeline_samples"] = len(tl.samples)
                        m["timeline_errors"] = len(tl.errors)
                        if not tl.burst or tl.burst.get("error"):
                            raise RuntimeError("burst not applied: %s" % (tl.burst or "never reached"))
                    i1 = sysprobe.cpuidle_counts(sut_set)
                    m["cpuidle_residency"] = sysprobe.cpuidle_residency(i0, i1, t1 - t0)
                    r1, rwhy1 = sysprobe.cpu_run_ns()
                    side_u1 = {svc.name: svc.usage_us() for svc in self.side}
                    k1 = sysprobe.proc_run_ns(envoy.pid)
                    kb1 = sysprobe.proc_run_ns(hop_b.pid) if hop_b else 0
                    p1 = sysprobe.per_cpu_times()
                    t_q1 = time.monotonic()
                    q1 = admin_stats(ecfg["admin_port"], adm_t, sfx)
                    t_q1_end = time.monotonic()
                    o1 = origin_requests(e) if from_origin else None
                    st1 = sysprobe_steal()
                    qb1 = admin_stats(e["hop2"]["admin_port"]) if hop_b else None
                    # the response count's time base ends with the last count read, before
                    # anything slow (thread checks, numastat) runs
                    t2 = time.monotonic()
                    if lat:
                        # the count read must end while the client and the probe still send
                        m["lat_senders_running"] = cl.poll() is None and lx["probe"].poll() is None
                        m["lat_count_reads_s"] = [round(lx["t_q0_end"] - t_q0, 3), round(t_q1_end - t_q1, 3)]
                    if sc0 is not None:
                        m["stat_count"] = stat_count_record(scp, sc0, stat_count(ecfg["admin_port"], scp, adm_t),
                                                            round(t0 - t_reads0, 3))
                    if sp0 is not None:
                        m["stat_ops"] = stat_ops(sp0, admin_prometheus(ecfg["admin_port"], adm_t),
                                                 prometheus_prefix(scp) if scp else None)
                    if rung["main_cpu"] is not None:
                        # where every thread ran last, after the window: still on its own set
                        m["rung_pin_after"] = pin_check(envoy.pid, rung["main_cpu"], rung["worker_set"], workers,
                                                        one_to_one=rung.get("one_to_one", False))
                    if mcfg.get("numastat"):
                        # after the window: where Envoy's memory sits, per node
                        m["numastat"] = numastat_totals(envoy.pid)
                    e1 = sysprobe.proc_threads_detail(envoy.pid)
                    b1 = sysprobe.proc_threads_detail(hop_b.pid) if hop_b else None
                    c1 = sysprobe.proc_threads_cpu(cl.pid)
                    if mcfg.get("conn_probe", True):
                        ssp = lambda n: os.path.join(self.run_dir, "ss", "%s.%s.txt.gz" % (leg_id, n))  # noqa: E731
                        m["conn_downstream"] = conn_usage("( sport = :%d )" % ecfg["listener_port"], ssp("down"))
                        if shape["kind"] == "proxied":
                            m["conn_upstream"] = conn_usage("( dport = :%d )" % e["origin"]["port"], ssp("up"))
                        if hop_b:
                            # first hop -> second hop: how the second hop's load spreads over connections
                            m["conn_hop2_downstream"] = conn_usage("( sport = :%d )" % e["hop2"]["listener_port"],
                                                                   ssp("hop2down"))
                    if lat:
                        # the probe runs at least 1 s past the window; it then answers what it sent
                        time.sleep(max(0.0, t1 + 1.0 - time.monotonic()))
                        lx["summary"] = statsrow.stop_latprobe(self.own, lx.pop("probe"), lx["summary_path"])
                    cl.wait(timeout=dur + 120)
                finally:
                    self.own.stop(cl)
            if lat:
                self._lat_after(m, aenv, envoy, sink, lat, adm_t, lx)
                pin_ok = pin_ok and lx["pins_ok"](lx["summary"], sampler)
            m["pinning_ok"] = pin_ok
            with open(os.path.join(self.run_dir, "perf", leg_id + ".csv"), "w") as f:
                f.write(pr.stderr)
            pv, prun = parse_perf_full(pr.stderr)
            if per_thread:
                # --per-thread lines carry the thread first: totals are the sum over threads
                pv, prun = perf_totals(parse_perf_per_thread(pr.stderr))
            # Admin snapshots bracket the perf command, so the response count
            # covers a slightly longer span than the counters do; scale it to the
            # perf window (same for every arm, it only fixes absolute numbers).
            win = t2 - (t_q0 if settle else t0)
            if lat:
                # a recorded figure only in run L (the gate is the exact request count, lat_count):
                # each read may wait behind a flush and reads its counter somewhere inside, so this
                # midpoint-to-midpoint span is off by up to half the difference of the two read times
                win = (t_q1 + t_q1_end) / 2.0 - (t_q0 + lx["t_q0_end"]) / 2.0
            perf_s = float(mcfg["window_s"])
            resp_raw = _delta(q0, q1, "http.ingress_http.downstream_rq_2xx")
            if from_origin:
                # responses counted at the origin (nginx stub_status): independent of Envoy's own
                # stats, which an arm may reject; each status read is one request, not counted.
                # A failed read is zero responses (invalid), never a fall back to Envoy's count.
                m["responses_admin_raw"] = resp_raw
                m["responses_from"] = "origin"
                m["origin_reads_ok"] = o0 is not None and o1 is not None
                resp_raw = (o1 - o0 - 1) if m["origin_reads_ok"] else 0
            resp = resp_raw * perf_s / win if win > 0 else 0
            if st0 and st1:
                m["steal_share"] = steal_share(st0, st1)
            busy_win = t1 - t0
            miss = [x for x in (rwhy0, rwhy1) if x]
            if k0 is None or k1 is None or kb0 is None or kb1 is None:
                miss.append("no /proc/<envoy>/task/*/schedstat")
            if not set(sut_set) <= set(r0 or {}) & set(r1 or {}):
                miss.append("SUT CPUs missing from /proc/schedstat")
            if miss:
                m["sched_probe"] = "; ".join(miss)
            elif busy_win > 0:
                # scheduler run time (ns): every task on the SUT CPUs minus Envoy's threads
                envoy_cpus = ((k1 - k0) + (kb1 - kb0)) / 1e9 / busy_win
                sut_run = sum(r1[c] - r0[c] for c in sut_set) / 1e9 / busy_win
                m["sut_cpus_run"] = round(sut_run, 4)
                m["sut_foreign_cpus"] = round(sut_run - envoy_cpus, 4)
                m["sut_sibling_cpus"] = round(sum(r1[c] - r0[c] for c in sib_set if c in r0 and c in r1)
                                              / 1e9 / busy_win, 4) if sib_set else 0.0
                m["envoy_cpus_run"] = round(envoy_cpus, 4)
            m["sut_cpu_busy_pct"] = {str(k): round(v, 1)
                                     for k, v in sysprobe.per_cpu_busy_pct(p0, p1, sut_set | sib_set).items()}
            m["envoy_threads"] = sysprobe.threads_summary(e0, e1, t2 - t0)
            ws = _worker_share(m["envoy_threads"], int(workers), envoy.pid)
            m.update(ws)
            m.update({"envoy_" + k: v for k, v in _worker_busy(m["envoy_threads"]).items()})
            if hop_b:
                m["hop2_threads"] = sysprobe.threads_summary(b0, b1, t2 - t0)
                wsb = _worker_share(m["hop2_threads"], int(ecfg["workers"]), hop_b.pid)
                m["hop2_workers"] = {k[len("envoy_"):]: v for k, v in wsb.items()}
                m["hop2_workers"].update(_worker_busy(m["hop2_threads"]))
                # the gate takes the worse of both hops (unless the shape turns it off for hop 2)
                if not vcfg.get("hop2_worker_share_gate", True):
                    pass
                elif wsb.get("envoy_worker_probe") and not ws.get("envoy_worker_probe"):
                    m["envoy_worker_probe"] = "hop2: " + wsb["envoy_worker_probe"]
                    m.pop("envoy_worker_max_share", None)
                elif "envoy_worker_max_share" in wsb and "envoy_worker_max_share" in m:
                    m["envoy_worker_max_share"] = max(m["envoy_worker_max_share"], wsb["envoy_worker_max_share"])
                    m["envoy_worker_min_share"] = min(m["envoy_worker_min_share"], wsb["envoy_worker_min_share"])
            non2 = sum(_delta(q0, q1, "http.ingress_http.downstream_rq_%s" % c) for c in ("1xx", "3xx", "4xx", "5xx"))
            m["sut_stats_delta"] = _stat_deltas(q0, q1)
            m["sut_stats_window"] = _stat_window(q0, q1)
            m["sut_stats_window_ok"] = True
            if per_thread:
                pt = parse_perf_per_thread(pr.stderr)
                m["perf_per_thread"] = pt
                wk = [v for v in pt.values() if v["comm"].startswith("wrk:")]
                cyc = lambda v: v.get("cycles", v.get("cycles:u", 0) + v.get("cycles:k", 0))  # noqa: E731
                m["workers_perf_threads"], m["workers_expected"] = len(wk), int(workers)
                if wk and resp > 0:
                    m["workers_cycles_per_req"] = sum(cyc(v) for v in wk) / resp
            if sampler:
                from . import statsrow as _sr
                bursts = _sr.find_bursts(sampler.samples, float(shape.get("burst_min_busy", 0.2)),
                                         float(shape.get("burst_join_s", 0.1)))
                m["main"] = _sr.summarize_main(sampler.samples, bursts, perf_s)
                m["flushes_counted"] = m["main"]["bursts"]
            if sink:
                m["udp"] = statsrow.udp_window(u0, u1, (m.get("main") or {}).get("bursts"))
                if resp > 0:
                    m["udp"]["datagrams_per_request"] = m["udp"]["sent"] / (resp_raw * (t1 - t0) / win)
            cu = m.get("conn_upstream") or {}
            if cu.get("segs_total") and q1.get("cluster.origin.upstream_rq_total"):
                # TCP segments Envoy received from the origin per response, over the connections'
                # lifetime: a proxy for how many reads a response arrives in
                m["upstream_segs_in_per_response"] = round(cu["segs_total"] / q1["cluster.origin.upstream_rq_total"], 3)
            if self.side:
                from .sideservice import window_record
                for svc in self.side:
                    rec = window_record(svc, side_u0.get(svc.name), side_u1.get(svc.name), busy_win, resp_raw)
                    m["side_services"][svc.name] = dict(m["side_services"].get(svc.name) or {}, **rec)
            m["sut_stats_end"] = _stat_end(q1)
            m["tcmalloc_percpu_slab_bytes"] = tcmalloc_percpu(ecfg["admin_port"])
            if hop_b:
                non2 += sum(_delta(qb0, qb1, "http.ingress_http.downstream_rq_%s" % c)
                            for c in ("1xx", "3xx", "4xx", "5xx"))
                m["hop2_stats_delta"] = _stat_deltas(qb0, qb1)
                m["hop2_stats_end"] = _stat_end(qb1)
                m["hop2_responses_raw"] = _delta(qb0, qb1, "http.ingress_http.downstream_rq_2xx")
            busy = sysprobe.threads_busy(c0, c1, win)
            maxb = max(busy.values()) if busy else None
            nhp = nighthawk.parse_output(nh_json)
            if lat:
                sent, want = nhp["counters"].get("upstream_rq_total"), shape["rps"] * float(dur)
                m["lat_nh"] = {"open_loop": "--open-loop" in ma, "requests": sent, "expected": want,
                               "responses_2xx": nhp["counters"].get("benchmark.http_2xx"),
                               "sent_ratio": sent / want if sent is not None and want else None,
                               "execution_s": nhp["execution_duration_s"]}
            m.update(
                window_s=round(win, 4), perf_window_s=perf_s, responses_raw=resp_raw, responses=resp,
                sut_rate_2xx=resp_raw / win if win > 0 else 0.0,
                sut_non2xx=non2,
                upstream_cx_opened=_delta(q0, q1, "cluster.origin.upstream_cx_total"),
                perf_raw=pv,
                perf_ok=perf_counts_ok(pv),
                perf_running_pct=prun,
                perf_min_running_pct=min(prun.values()) if prun else None,
                client_thread_busy_max=maxb,
                client_headroom=(1.0 - maxb) if maxb is not None else None,
                client_rate_2xx=nhp["rate_2xx"], client_overflow=nhp["overflow"],
                client_non2xx=nhp["non2xx"], latency_us=nhp["latency_us"],
                client_version=nhp["client_version"],
                client_workers=nhp["workers"], client_pending_total=nhp["pending_total"],
                client_cx_total=nhp["cx_total"], client_worker_r2r_max_us=nhp["worker_r2r_max_us"],
                client_queue_to_connect_max_us=nhp["queue_to_connect_max_us"],
                client_callback_max_us=nhp["callback_max_us"],
            )
            if resp > 0 and m["perf_ok"]:
                iu = pv["instructions:u"]
                split = "cycles:u" in pv and "cycles:k" in pv
                cu, ck = (pv["cycles:u"], pv["cycles:k"]) if split else (None, None)
                ctot = (cu + ck) if split else pv["cycles"]
                tc = pv.get("task-clock", 0.0)  # msec
                m["per_req"] = {
                    "instructions_u": iu / resp,
                    "instructions_k": pv.get("instructions:k", 0.0) / resp,
                    "cycles_u": cu / resp if split else None,
                    "cycles_k": ck / resp if split else None,
                    "cycles_total": ctot / resp,
                    "task_clock_us": tc * 1000.0 / resp,
                    "context_switches": pv.get("context-switches", 0.0) / resp,
                    "cpu_migrations": pv.get("cpu-migrations", 0.0) / resp,
                }
                if not split:
                    for k in ("cycles_u", "cycles_k", "instructions_k"):
                        m["per_req"].pop(k)
                extra = {k: v / resp for k, v in pv.items() if k not in BASE_EVENT_NAMES}
                if extra:
                    m["per_req"]["events"] = extra
                m["sut_busy"] = tc / 1000.0 / (mcfg["window_s"] * workers)
                if pv.get("ref-cycles"):
                    # average core frequency over the window, relative to the reference clock
                    m["freq_ratio"] = ctot / pv["ref-cycles"]
                m["eff_ghz"] = ctot / (tc / 1000.0) / 1e9 if tc else None
                if hop2_set:
                    # two-hop experiment: every hop together and per hop (a single-hop arm has one hop)
                    hops, ins_all, cyc_all = 1, iu, cu + ck
                    if hop_b:
                        with open(os.path.join(self.run_dir, "perf", leg_id + ".hop2.csv"), "w") as f:
                            f.write(pb_err or "")
                        bv, brun = parse_perf_full(pb_err or "")
                        m["hop2_perf_raw"] = bv
                        if not all(k in bv for k in ("instructions:u", "cycles:u", "cycles:k")):
                            m["perf_ok"] = False
                        else:
                            if brun:
                                m["perf_min_running_pct"] = min(m["perf_min_running_pct"] or 100.0,
                                                                min(brun.values()))
                            btc = bv.get("task-clock", 0.0)
                            m["hop2_per_req"] = {
                                "instructions_u": bv["instructions:u"] / resp, "cycles_u": bv["cycles:u"] / resp,
                                "cycles_k": bv["cycles:k"] / resp,
                                "cycles_total": (bv["cycles:u"] + bv["cycles:k"]) / resp,
                                "task_clock_us": btc * 1000.0 / resp,
                                "context_switches": bv.get("context-switches", 0.0) / resp}
                            m["hop2_busy"] = btc / 1000.0 / (mcfg["window_s"] * ecfg["workers"])
                            m["per_req"]["cycles_total_hop2"] = m["hop2_per_req"]["cycles_total"]
                            hops = 2
                            ins_all += bv["instructions:u"]
                            cyc_all += bv["cycles:u"] + bv["cycles:k"]
                    if m["perf_ok"]:
                        m["per_req"]["hops"] = hops
                        m["per_req"]["instructions_u_all"] = ins_all / resp
                        m["per_req"]["cycles_total_all"] = cyc_all / resp
                        m["per_req"]["cycles_total_per_hop"] = cyc_all / resp / hops
        except Exception as ex:  # noqa: BLE001 - recorded as an invalid leg
            m["error"] = "%s: %s" % (type(ex).__name__, ex)
        finally:
            if envoy is not None and envoy.poll() is None:
                # end-of-leg snapshot: cumulative counters over the whole leg, just before the stop
                try:
                    m["sut_stats_leg_end"] = admin_stats(ecfg["admin_port"], adm_t, sfx)
                    m["sut_stats_leg_end_ok"] = True
                    self._save_stats(arm["name"], ecfg["admin_port"], timeout=max(10.0, adm_t))
                    sc = aenv.get("stats_clusters")
                    if sc:
                        # the generated clusters' connect failures and overflows over the leg
                        # (a used-only read after the window; it flushes under on_admin)
                        names = envoy_config.stats_cluster_names(sc["count"], sc.get("seed", 1))
                        # run L read it at its own quiescent point after the client ended
                        post = (lx or {}).get("post") or statsrow.stats_read(ecfg["admin_port"], max(10.0, adm_t),
                                                                              usedonly=True)
                        if post.get("status") != 200:
                            # fail closed: no counts from a failed read (the evidence then fails too)
                            m["error"] = m.get("error") or "post-window /stats?usedonly returned %s" % post.get("status")
                            raise RuntimeError("post-window /stats returned %s" % post.get("status"))
                        m["gen_cx_connect_fail"] = statsrow.generated_sum(post["numeric"], names,
                                                                          "upstream_cx_connect_fail")
                        m["gen_cx_overflow"] = statsrow.generated_sum(post["numeric"], names, "upstream_cx_overflow")
                except (OSError, RuntimeError) as ex:
                    m["leg_end_snapshot_error"] = str(ex)
            if lx and lx.get("probe") is not None:
                # a leg that failed before its probe was stopped: stop it now (own child only)
                try:
                    self.own.stop(lx.pop("probe"), grace_s=40.0)
                except Exception:  # noqa: BLE001 - best effort; the leg is invalid already
                    pass
            if envoy is not None:
                st = self._stop_envoy(envoy, elog, elog_path)
                m["envoy_exit"] = st["exit"]
                m["envoy_log_deprecated_lines"] = st.get("deprecated_lines")
                m["envoy_log_bytes"] = st.get("log_bytes")
                if lat:
                    try:
                        with open(elog_path) as f:
                            m["envoy_log_emfile"] = len(EMFILE_RE.findall(f.read()))
                    except OSError:
                        m["envoy_log_emfile"] = None
            if sampler is not None:
                sampler.stop_evt.set()
            if sink is not None:
                m["udpsink"] = statsrow.stop_udpsink(self.own, sink, sink_out)
            if hop_b is not None:
                st = self._stop_envoy(hop_b, belog, blog)
                m["hop2_exit"] = st["exit"]
                if st["exit"] not in (0, None) and m.get("envoy_exit") in (0, None):
                    m["envoy_exit"] = st["exit"]
            if alog and os.path.exists(alog):
                # every request should have a line (written by the flush thread, flushed at exit)
                n, size = _count_lines(alog)
                m["access_log_lines"], m["access_log_bytes"] = n, size
                m["access_log_bytes_per_line"] = round(size / n, 2) if n else None
                if (aenv.get("access_log") or {}).get("format") == "json":
                    js = json_lines_check(alog)
                    m["access_log_json"] = js
                    m["access_log_json_ok"] = js["checked"] > 0 and js["bad"] == 0
                with open(alog, "rb") as f:
                    sample = f.read(4096)
                with open(os.path.join(self.run_dir, "alog", leg_id + ".sample"), "wb") as f:
                    f.write(sample)
                with open(alog, "w"):
                    pass  # keep the run directory small: sample kept, file emptied
        if lat:
            # run L: the collector was read at the two quiescent points (_lat_before, _lat_after)
            self._lat_finish(m, aenv, shape, leg_id, lat, lx, rung)
        elif coll0 is not None:
            c1 = self.collector.scrape()
            if "error" in coll0 or "error" in c1:
                m["collector_delta"] = {"error": coll0.get("error") or c1.get("error")}
            else:
                m["collector_delta"] = {k: c1.get(k, 0) - coll0.get(k, 0) for k in set(coll0) | set(c1)}
        if arm.get("evidence") is not None:
            from . import evidence
            m["evidence"] = evidence.evaluate(m, arm["evidence"], self.config_dumps.get(arm["name"]),
                                              gate=e.get("evidence_mode", "gate") == "gate")
        m["verdict"] = validity.verdict(m, vcfg)
        return m

    # ---------------------------------------------------------------- run L (flush latency)

    def _lat_before(self, m, aenv, envoy, sink, leg_id, lat, adm_t, shape, workers):
        """Before the client starts: one full /stats read, a quiescent point, the kernel's UDP
        counters and the collector (settled); then the probe, started on its own CPU and ready
        (its connections mapped to workers). Returns the leg's run-L context."""
        e = self.exp
        ecfg = e["envoy"]
        pid = envoy.pid
        kind = (aenv.get("stats_sink") or {}).get("kind")
        sc = aenv.get("stats_clusters")
        names = envoy_config.stats_cluster_names(sc["count"], sc.get("seed", 1)) if sc else []
        lx = {"clock": [], "kind": kind, "port": e["stats_sink"]["port"] if sink else None}
        lx["t_pre"] = time.monotonic()
        pre = statsrow.stats_read(ecfg["admin_port"], max(10.0, adm_t))
        if pre["status"] != 200:
            raise RuntimeError("pre-client /stats returned %s" % pre["status"])
        lx["t_cl0"] = time.monotonic()
        # one filtered read, timed: what each of the two count reads around the window will take
        admin_stats(ecfg["admin_port"], max(10.0, adm_t))
        lx["count_read_s"] = time.monotonic() - lx["t_cl0"]
        m["lat_count_read_idle_s"] = round(lx["count_read_s"], 3)
        n0 = lx["n0"] = pre["numeric"]
        m["pre_read"] = {k: pre[k] for k in ("total", "histograms", "text_readouts", "seconds", "bytes")}
        m["stats_total"] = pre["total"]
        m["active_clusters"] = n0.get("cluster_manager.active_clusters")
        m["gen_cx_active_pre"] = statsrow.generated_sum(n0, names, "upstream_cx_active")
        m["flush_interval_s"] = float((aenv.get("stats_flush") or {}).get("interval_s", 5))
        qt = float(shape.get("quiesce_timeout_s", 30))
        q_ok, q_s = statsrow.quiesce(pid, lx["port"], qt)
        lx["tu0_ns"] = time.monotonic_ns()
        lx["u0"] = statsrow.udp_counters(e["stats_sink"]["port"])
        lx["coll0"] = statsrow.settled_scrape(self.collector) if (self.collector and kind == "otlp") else None
        m["quiesce"] = {"before_ok": q_ok, "before_s": q_s}
        d = os.path.join(self.run_dir, "probe")
        os.makedirs(d, exist_ok=True)
        lx["log"] = os.path.join(d, leg_id + ".jsonl.gz")
        lx["summary_path"] = os.path.join(d, leg_id + ".json")
        probe_cpus = sysprobe.parse_cpuset(e["cpus"]["probe"])
        sampler_cpus = sysprobe.parse_cpuset(e["cpus"]["sampler"])
        args = ["--listener-port", ecfg["listener_port"], "--admin-port", ecfg["admin_port"],
                "--origin-port", e["origin"]["port"], "--envoy-pid", pid, "--workers", workers,
                "--path", shape["path"], "--per-worker", lat["per_worker"], "--data-hz", lat["data_hz"],
                "--data-stagger-ms", lat["data_stagger_ms"], "--admin-period-ms", lat["admin_period_ms"],
                "--control-conns", lat["control_conns"], "--control-hz", lat["control_hz"],
                "--map-requests", lat["map_requests"], "--map-margin", lat["map_margin"],
                "--map-max-opens", lat["map_max_opens"], "--gap-ms", lat["gap_ms"], "--drain-s", lat["drain_s"],
                "--out-log", lx["log"], "--out-summary", lx["summary_path"]]
        if int(lat["per_worker"]) * int(workers) != int(lat["data_conns"]):
            raise RuntimeError("measure.latency: data_conns must be per_worker x workers")
        lx["probe"] = statsrow.start_latprobe(self.own, e["cpus"]["probe"], args, lx["summary_path"],
                                               float(lat.get("ready_timeout_s", 60)))
        lx["probe_cpus_allowed"] = sysprobe.cpus_allowed(lx["probe"].pid)

        def pins_ok(summary, sampler):
            # the probe on its CPU (as the kernel and as the probe itself saw it), the sampler on its own
            got = sysprobe.parse_cpuset(lx["probe_cpus_allowed"] or "")
            return got == probe_cpus and set((summary or {}).get("cpus_allowed") or []) == probe_cpus \
                and set(getattr(sampler, "affinity", None) or []) == sampler_cpus
        lx["pins_ok"] = pins_ok
        return lx

    def _lat_after(self, m, aenv, envoy, sink, lat, adm_t, lx):
        """After the client ended, Envoy still up: one used-only /stats read, a quiescent point,
        the UDP counters and the collector (settled). The evidence of the leg is between these
        reads and the ones of _lat_before, both of this leg."""
        e = self.exp
        pid = envoy.pid
        kind = lx["kind"]
        n0 = lx["n0"]
        t_post = time.monotonic()
        post = statsrow.stats_read(e["envoy"]["admin_port"], max(10.0, adm_t), usedonly=True)
        if post.get("status") != 200:
            raise RuntimeError("post-client /stats?usedonly returned %s" % post.get("status"))
        lx["post"] = post
        n1 = post["numeric"]
        q_ok, q_s = statsrow.quiesce(pid, lx["port"], 30.0)
        lx["tu1_ns"] = time.monotonic_ns()
        u1 = statsrow.udp_counters(e["stats_sink"]["port"])
        c1 = statsrow.settled_scrape(self.collector) if lx["coll0"] is not None else None
        m["quiesce"].update(after_ok=q_ok, after_s=q_s, span_s=round((lx["tu1_ns"] - lx["tu0_ns"]) / 1e9, 3))
        m["post_read"] = {k: post.get(k) for k in ("total", "histograms", "text_readouts", "seconds", "bytes",
                                                     "status")}
        m["used_total"] = post.get("total")
        m["used_cg_lines"] = (post.get("total") or 0) - (post.get("histograms") or 0) - \
            (post.get("text_readouts") or 0)
        up0, up1 = n0.get("server.uptime"), n1.get("server.uptime")
        if up0 is not None and up1 is not None:
            el = t_post - lx["t_pre"]
            m["uptime"] = {"delta_s": up1 - up0, "elapsed_s": round(el, 3), "error_s": round(abs((up1 - up0) - el), 3)}
        m["dropped_stat_flushes_delta"] = n1.get("server.dropped_stat_flushes", 0) - \
            n0.get("server.dropped_stat_flushes", 0)
        # names as this binary has them (every stat of the arm is saved once in stats/): any
        # watchdog counter and every server.main_thread stat, as changes over the leg
        m["watchdog_delta"] = {k: n1.get(k, 0) - n0.get(k, 0) for k in sorted(set(n0) | set(n1))
                               if "watchdog" in k}
        m["main_thread_delta"] = {k: n1.get(k, 0) - n0.get(k, 0) for k in sorted(set(n0) | set(n1))
                                  if k.startswith("server.main_thread.")}
        uw = statsrow.udp_window(lx["u0"], u1, None)
        if "error" not in uw:
            s0, s1 = lx["u0"].get("snmp") or {}, u1.get("snmp") or {}
            uw["no_ports"] = s1.get("NoPorts", 0) - s0.get("NoPorts", 0) if "NoPorts" in s0 and "NoPorts" in s1 \
                else None
            uw["rx_queue_quiescent"] = [(lx["u0"].get("sock") or {}).get("rx_queue"),
                                        (u1.get("sock") or {}).get("rx_queue")]
        m["udp_leg"] = uw
        if kind == "otlp":
            m["otlp_cluster"] = statsrow.otlp_cluster(
                n0, n1, m.get("used_total"),
                int((aenv.get("stats_sink") or {}).get("max_data_points_per_request") or 10000),
                t_post - lx["t_cl0"], m["flush_interval_s"])
            coll0 = lx["coll0"]
            if c1 is None or "error" in coll0 or "error" in c1:
                m["collector_delta"] = {"error": (coll0 or {}).get("error") or (c1 or {}).get("error") or "no read"}
            else:
                cd = {k: c1.get(k, 0) - coll0.get(k, 0) for k in set(coll0) | set(c1) if not k.startswith("_")}
                fl = m["otlp_cluster"].get("flushes")
                if fl is not None and "accepted_metric_points" in cd:
                    # the divisor is the whole number of flushes the points hold; it may differ by
                    # one from the flushes Envoy's request count gives (one in flight at a read)
                    fitd = statsrow.flush_fit(cd["accepted_metric_points"], m.get("used_total"), int(round(fl)))
                    cd["fit"] = fitd
                    if fitd.get("n"):
                        cd["accepted_metric_points_per_flush"] = cd["accepted_metric_points"] / fitd["n"]
                cd["settled"] = bool(coll0.get("_settled")) and bool(c1.get("_settled"))
                m["collector_delta"] = cd
            m["collector_cfg"] = self._collector_cfg()

    def _collector_cfg(self):
        """What the collector's own config.yaml says about its receive limit (None: not there)."""
        try:
            with open(os.path.join(self.run_dir, "collector", "config.yaml")) as f:
                mm = re.search(r"^\s*max_recv_msg_size_mib:\s*(\d+)\s*$", f.read(), re.M)
        except OSError as ex:
            return {"error": str(ex)}
        return {"max_recv_msg_size_mib": int(mm.group(1)) if mm else None}

    def _lat_finish(self, m, aenv, shape, leg_id, lat, lx, rung):
        """After Envoy and the sink stopped: the leg's series saved (main/<leg>.json.gz), the
        probe log read back, and m["lat"] (latency.leg_record) with the receiver's own flush
        counts. Anything missing leaves its fields out, and the gates on them fail."""
        try:
            if not lx or "summary" not in lx or "sampler" not in lx:
                raise RuntimeError("the leg ended before its probe and series were complete")
            sampler, summary = lx["sampler"], lx["summary"]
            pid = m["envoy_pid"]
            bursts = statsrow.find_bursts(sampler.samples, float(shape.get("burst_min_busy", 0.2)),
                                          float(shape.get("burst_join_s", 0.1)))
            threads = {int(t): v for t, v in ((summary.get("map") or {}).get("threads") or {}).items()}
            threads[pid] = {"comm": "main", "cpus": str(rung["main_cpu"])}
            t0, t1 = lx["t0"], lx["t1"]
            mdir = os.path.join(self.run_dir, "main")
            os.makedirs(mdir, exist_ok=True)
            with gzip.open(os.path.join(mdir, leg_id + ".json.gz"), "wt") as f:
                json.dump({"leg_id": leg_id, "samples": sampler.samples, "bursts": bursts, "main_tid": pid,
                           "period_s": sampler.period_s, "missing": sampler.missing,
                           "threads": {str(t): v for t, v in threads.items()},
                           "series": {str(t): v for t, v in sampler.series.items()},
                           "window_mono": [t0, t1], "harness_clock": lx["clock"],
                           "sampler_affinity": sampler.affinity, "rx_queue": sampler.rx_queue}, f)
            m["lat_probe"] = {k: summary.get(k) for k in ("exit", "error", "data", "admin", "control", "gaps",
                                                           "events", "drained", "cpus_allowed", "run", "map_end")}
            if summary.get("error") or summary.get("exit") != 0:
                raise RuntimeError("probe: %s (exit %s)" % (summary.get("error"), summary.get("exit")))
            probe = latency.load_probe(lx["log"])
            m["lat_count"] = lat_count(lx["n0"], (lx.get("post") or {}).get("numeric") or {},
                                       (m.get("lat_nh") or {}).get("responses_2xx"), probe["rows"],
                                       (summary.get("map") or {}).get("requests"))
            cfg = dict(lat, workers=rung["workers"], interval_s=m["flush_interval_s"])
            rec = latency.leg_record(probe, summary, sampler.series, threads, pid, bursts, t0, t1, lx["clock"],
                                     sampler.missing, cfg)
            sink = m.get("udpsink") or {}
            if lx["kind"] == "statsd":
                sd = latency.statsd_flushes(sink.get("marks"), m.get("used_cg_lines"), lx["tu0_ns"],
                                            lx.get("tu1_ns", 0))
                inw = sum(1 for x in sink.get("marks") or [] if t0 <= x[0] / 1e9 <= t1)
                sd["marks_window"] = inw
                sd["marks_window_error"] = abs(inw - rec["flush"]["bursts_window"])
                done = (m.get("sut_stats_leg_end") or {}).get("http.ingress_http.downstream_rq_completed")
                ms = (sink.get("classes") or {}).get("ms")
                sd["ms_lines"], sd["requests_completed"] = ms, done
                sd["ms_per_request"] = ms / float(done) if ms is not None and done else None
                # the expectation from this leg's own counters at its post-client read (what Envoy
                # sends after that read, a few admin requests and the closes at its stop, is in the band)
                exp_ms = timer_lines_expected((lx.get("post") or {}).get("numeric") or {})
                sd["ms_expected"] = exp_ms
                if exp_ms and exp_ms["total"] and ms is not None:
                    sd["ms_error_share"] = abs(ms - exp_ms["total"]) / float(exp_ms["total"])
                rec["statsd"] = sd
            if lx["port"] is not None:
                # S-6: the receive queue against the buffer the kernel granted (quiescent points
                # and once per second from the sampler thread)
                qs = [q for _, q in sampler.rx_queue if q is not None] + \
                    [q for q in (m.get("udp_leg") or {}).get("rx_queue_quiescent") or [] if q is not None]
                granted = sink.get("rcvbuf_granted")
                rec["rx_queue"] = {"samples": len(qs), "max": max(qs) if qs else None, "granted": granted,
                                   "max_share": max(qs) / float(granted) if qs and granted else None}
            m["lat"] = rec
        except Exception as ex:  # noqa: BLE001 - recorded as an invalid leg
            m["lat_error"] = "%s: %s" % (type(ex).__name__, ex)
            m["error"] = m.get("error") or "run L record: %s" % m["lat_error"]

    # ---------------------------------------------------------------- idle legs (stats row)

    def _sink_start(self, aenv, leg_id):
        """The drain-only UDP sink for a statsd or dog_statsd arm, as this run's own child."""
        from . import statsrow
        kind = (aenv.get("stats_sink") or {}).get("kind")
        if kind not in ("statsd", "dog_statsd"):
            return None, None
        sc = self.exp["stats_sink"]
        d = os.path.join(self.run_dir, "udpsink")
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, leg_id + ".json")
        p = statsrow.start_udpsink(self.own, self.exp["cpus"]["origin"], int(sc["port"]), int(sc["rcvbuf"]), out,
                                   int(sc.get("sample_every", 1)),
                                   classes=bool(self.exp["measure"].get("latency")))
        return p, out

    def _prime(self, m, arm, shape, aenv):
        """One paced request per generated cluster, then a settle for the upstream connections
        to close (their idle timeout); outside any window."""
        from . import statsrow
        sc = aenv.get("stats_clusters")
        if not sc or not _primes(arm, shape):
            m["primed"] = False
            return
        names = envoy_config.stats_cluster_names(sc["count"], sc.get("seed", 1))
        m["primed"] = True
        m["prime"] = statsrow.prime(self.exp["envoy"]["listener_port"], names,
                                    int(shape.get("prime_in_flight", 200)), int(shape.get("prime_per_s", 1000)))
        time.sleep(float(shape.get("prime_settle_s", 5)))

    def _run_idle_leg(self, arm, shape, rnd, bootstrap_path, leg_id, m, aenv, vcfg):
        """A leg with no client load: start Envoy, prime the generated clusters, read /stats once
        before the window (then settle), sample the main thread for the window, read /stats
        (used only) once after it, stop. Metrics per flush period, not per request."""
        from . import statsrow
        e = self.exp
        ecfg, mcfg = e["envoy"], e["measure"]
        m["idle_leg"] = True
        if isinstance(bootstrap_path, dict):
            bootstrap_path = bootstrap_path[arm["name"]]
        sut = sysprobe.parse_cpuset(e["cpus"]["sut"])
        sib = sysprobe.siblings_of(sut)
        client_cpus = sysprobe.parse_cpuset(e["cpus"]["client"])
        ready_t = float(shape.get("ready_timeout_s", 60))
        adm_t = float(shape.get("admin_timeout_s", 30))
        settle = float(shape.get("settle_s", 2))
        window = float(arm.get("window_s") or shape.get("window_s", mcfg["window_s"]))
        sf = aenv.get("stats_flush") or {}
        interval = None if sf.get("on_admin") else float(sf.get("interval_s", 5))
        m["flush_interval_s"] = interval
        sc = aenv.get("stats_clusters")
        names = envoy_config.stats_cluster_names(sc["count"], sc.get("seed", 1)) if sc else []
        m["stats_clusters_count"] = len(names)
        kind = (aenv.get("stats_sink") or {}).get("kind")
        envoy = elog = sink = sampler = prober = scraper = span = None
        sink_out = None
        elog_path = os.path.join(self.run_dir, "logs", leg_id + ".envoy.log")
        t_leg_wall = time.time()
        try:
            sink, sink_out = self._sink_start(aenv, leg_id)
            t_s = time.monotonic()
            envoy, elog = self._start_envoy(arm["binary"], bootstrap_path, e["cpus"]["sut"], ecfg["workers"],
                                            ecfg["admin_port"], dict(arm.get("env") or {}), arm.get("extra_args", []),
                                            elog_path, ready_timeout_s=ready_t, nofile=nofile_for(aenv, e))
            pid = envoy.pid
            m["envoy_pid"] = pid
            m["start_s"] = round(time.monotonic() - t_s, 2)
            m["sut_cpus_allowed"] = sysprobe.cpus_allowed(pid)
            m["pinning_ok"] = sysprobe.parse_cpuset(m["sut_cpus_allowed"]) == sut
            lim = statsrow.parse_limits(statsrow.read("/proc/%d/limits" % pid))
            m["nofile_soft"], m["nofile_hard"] = lim if lim else (None, None)
            self._save_config_dump(arm["name"], ecfg["admin_port"], timeout=adm_t)
            self._prime(m, arm, shape, aenv)
            m["fd_count"] = statsrow.fd_count(pid)
            # the main thread is the thread whose tid is the pid; workers are wrk:*
            m["main_comm"] = statsrow.thread_comm(pid, pid)
            # one admin stats read before the window (with stats_flush_on_admin it flushes), then settle
            t_pre = time.monotonic()
            pre = statsrow.stats_read(ecfg["admin_port"], adm_t)
            if pre["status"] != 200:
                raise RuntimeError("pre-window /stats returned %s" % pre["status"])
            n0 = pre["numeric"]
            t_cl0 = time.monotonic()  # the start of the otlp_cluster span (after the pre-window read)
            m["pre_read"] = {k: pre[k] for k in ("total", "histograms", "text_readouts", "seconds", "bytes")}
            m["stats_total"] = pre["total"]
            m["active_clusters"] = n0.get("cluster_manager.active_clusters")
            m["gen_cx_active_pre"] = statsrow.generated_sum(n0, names, "upstream_cx_active")
            time.sleep(settle)
            # window
            vm0 = statsrow.memory_kb(pid)
            # the span sampler runs from before the first quiescent point to after the second, so
            # the flushes between the two are counted whole (a quiescent point is between flushes)
            span = statsrow.MainSampler(pid, pid, float(mcfg.get("main_sample_s", 0.02)), client_cpus)
            span.start()
            # a quiescent point (no flush in progress, the sink's queue read empty) before the
            # kernel counters, so the window's datagrams are whole flushes
            q0_ok, q0_s = statsrow.quiesce(pid, e["stats_sink"]["port"] if sink else None,
                                           float(shape.get("quiesce_timeout_s", 30)))
            tu0 = time.monotonic()
            u0 = statsrow.udp_counters(e["stats_sink"]["port"]) if sink else None
            sk0 = sysprobe.proc_run_ns(sink.pid) if sink else None
            coll0 = statsrow.settled_scrape(self.collector) if (self.collector and kind == "otlp") else None
            r0, rwhy0 = sysprobe.cpu_run_ns()
            k0 = sysprobe.proc_run_ns(pid)
            th0 = statsrow.threads_run_ns(pid)
            sampler = statsrow.MainSampler(pid, pid, float(mcfg.get("main_sample_s", 0.02)), client_cpus)
            prober = statsrow.ReadyProber(ecfg["admin_port"], 0.2, client_cpus)
            if arm.get("prom_scrape_s"):
                scraper = statsrow.PromScraper(ecfg["admin_port"], float(arm["prom_scrape_s"]), client_cpus, adm_t)
            t0 = time.monotonic()
            for th in (sampler, prober, scraper):
                if th:
                    th.start()
            events = mcfg.get("main_perf_events") or "instructions:u,cycles:u,cycles:k,instructions:k,task-clock"
            pr = subprocess.run(self.perf + ["stat", "-x", ",", "-e", events, "-t", str(pid), "--", "sleep",
                                             "%g" % window], capture_output=True, text=True, timeout=window + 60)
            for th in (sampler, prober, scraper):
                if th:
                    th.stop_evt.set()
            for th in (sampler, prober, scraper):
                if th:
                    th.join(timeout=adm_t + 10)
            t1 = time.monotonic()
            r1, rwhy1 = sysprobe.cpu_run_ns()
            k1 = sysprobe.proc_run_ns(pid)
            th1 = statsrow.threads_run_ns(pid)
            q1_ok, q1_s = statsrow.quiesce(pid, e["stats_sink"]["port"] if sink else None,
                                           float(shape.get("quiesce_timeout_s", 30)))
            tu1 = time.monotonic()
            u1 = statsrow.udp_counters(e["stats_sink"]["port"]) if sink else None
            # the collector at the second quiescent point: read until two reads agree (the export
            # of the last flush may still be in flight after the main thread went idle)
            c1 = statsrow.settled_scrape(self.collector) if coll0 is not None and self.collector else None
            span.stop_evt.set()
            span.join(timeout=adm_t + 10)
            sb = statsrow.find_bursts(span.samples, float(shape.get("burst_min_busy", 0.2)),
                                      float(shape.get("burst_join_s", 0.1)))
            m["span_flushes"] = statsrow.span_flushes(sb, tu0, tu1)
            m["quiesce"] = {"before_ok": q0_ok, "before_s": q0_s, "after_ok": q1_ok, "after_s": q1_s,
                            "span_s": round(tu1 - tu0, 3)}
            sk1 = sysprobe.proc_run_ns(sink.pid) if sink else None
            vm1 = statsrow.memory_kb(pid)
            m["memory"] = {"vm_rss_kb_before": vm0["vm_rss_kb"], "vm_hwm_kb_after": vm1["vm_hwm_kb"],
                           "page_size": os.sysconf("SC_PAGE_SIZE")}
            # one admin stats read after the window: used stats only
            t_post = time.monotonic()
            post = statsrow.stats_read(ecfg["admin_port"], adm_t, usedonly=True)
            n1 = post["numeric"]
            m["post_read"] = {k: post.get(k) for k in ("total", "histograms", "text_readouts", "seconds", "bytes",
                                                         "status")}
            m["used_total"] = post.get("total")
            m["used_cg_lines"] = (post.get("total") or 0) - (post.get("histograms") or 0) - \
                (post.get("text_readouts") or 0)
            if kind == "otlp":
                # the export requests on Envoy's side, independent of the collector's count: requests
                # per flush (the sink cuts one every max_data_points_per_request points) and stream
                # resets between the pre-window and post-window reads
                m["otlp_cluster"] = statsrow.otlp_cluster(
                    n0, n1, m.get("used_total"),
                    int((aenv.get("stats_sink") or {}).get("max_data_points_per_request") or 10000),
                    t_post - t_cl0, interval)
            if getattr(self, "calibrate", False):
                # calibration only: N and used N by kind (each read flushes under on_admin)
                bk = {}
                for kd in ("Counters", "Gauges", "Histograms", "TextReadouts"):
                    for uo in (False, True):
                        st_, body_, dt_ = statsrow.admin_text(ecfg["admin_port"], "/stats?type=%s%s" % (
                            kd, "&usedonly" if uo else ""), adm_t)
                        bk["%s%s" % (kd.lower(), "_used" if uo else "")] = (
                            sum(1 for ln in body_.splitlines() if ": " in ln) if st_ == 200 else None)
                m["by_kind"] = bk
            m["gen_cx_connect_fail"] = statsrow.generated_sum(n1, names, "upstream_cx_connect_fail")
            m["gen_cx_overflow"] = statsrow.generated_sum(n1, names, "upstream_cx_overflow")
            keep0 = {k: v for k, v in n0.items() if IDLE_KEEP_RE.search(k)}
            keep1 = {k: v for k, v in n1.items() if IDLE_KEEP_RE.search(k)}
            m["sut_stats_leg_end"] = keep1
            m["sut_stats_window"] = {k: keep1.get(k, 0) - keep0.get(k, 0) for k in sorted(set(keep0) | set(keep1))}
            up0, up1 = n0.get("server.uptime"), n1.get("server.uptime")
            if up0 is not None and up1 is not None:
                m["uptime"] = {"delta_s": up1 - up0, "elapsed_s": round(t_post - t_pre, 3),
                               "error_s": round(abs((up1 - up0) - (t_post - t_pre)), 3)}
            m["dropped_stat_flushes_delta"] = n1.get("server.dropped_stat_flushes", 0) - \
                n0.get("server.dropped_stat_flushes", 0)
            m["watchdog_delta"] = {k: n1.get(k, 0) - n0.get(k, 0) for k in set(n0) | set(n1) if "watchdog" in k
                                   and n1.get(k, 0) - n0.get(k, 0)}
            m["memory"].update({k: n1[k] for k in n1 if k.startswith("server.memory_")})
            # main thread: series, bursts, per-flush figures
            samples = sampler.samples
            bursts = statsrow.find_bursts(samples, float(shape.get("burst_min_busy", 0.2)),
                                          float(shape.get("burst_join_s", 0.1)))
            main = statsrow.summarize_main(samples, bursts, window)
            main["sampler_missing"] = sampler.missing
            if interval:
                exp_n = statsrow.expected_flushes(t1 - t0, interval)
                main["expected_flushes"] = exp_n
                # with the main thread saturated the bursts merge into one: no count to compare
                main["burst_count_error"] = None if statsrow.saturated(main.get("run_ms_per_s")) else \
                    abs(main["bursts"] - exp_n)
            m["main"] = main
            mdir = os.path.join(self.run_dir, "main")
            os.makedirs(mdir, exist_ok=True)
            with gzip.open(os.path.join(mdir, leg_id + ".json.gz"), "wt") as f:
                json.dump({"samples": samples, "bursts": bursts}, f)
            m["main_tid_ok"] = bool(m["main_comm"]) and not m["main_comm"].startswith("wrk:") and \
                sampler.missing == 0 and len(samples) >= 0.8 * window / float(mcfg.get("main_sample_s", 0.02))
            # perf on the main thread
            with open(os.path.join(self.run_dir, "perf", leg_id + ".csv"), "w") as f:
                f.write(pr.stderr)
            pv, prun = parse_perf_full(pr.stderr)
            m["main_perf_raw"] = pv
            m["perf_min_running_pct"] = min(prun.values()) if prun else None
            cyc = (pv["cycles:u"] + pv["cycles:k"]) if ("cycles:u" in pv and "cycles:k" in pv) else pv.get("cycles")
            m["perf_ok"] = cyc is not None and "instructions:u" in pv
            if m["perf_ok"]:
                ws = float(window)
                mp = {"cycles_per_s": cyc / ws, "instructions_u_per_s": pv["instructions:u"] / ws}
                if "cycles:u" in pv:
                    mp.update(cycles_u_per_s=pv["cycles:u"] / ws, cycles_k_per_s=pv["cycles:k"] / ws)
                if main.get("period_s"):
                    mp["cycles_per_period"] = mp["cycles_per_s"] * main["period_s"]
                m["main_perf"] = mp
            # every thread's run time; SUT CPUs clean during the window
            busy_win = t1 - t0
            other = sum(th1[t][1] - th0[t][1] for t in th1 if t in th0 and t != pid)
            m["main_over_busiest_other"] = statsrow.busiest_other_ratio(th0, th1, pid)
            m["other_threads_ms_per_s"] = other / 1e6 / busy_win if busy_win > 0 else None
            if k0 is not None and k1 is not None and r0 and r1 and not rwhy0 and not rwhy1:
                envoy_cpus = (k1 - k0) / 1e9 / busy_win
                sut_run = sum(r1[c] - r0[c] for c in sut if c in r0 and c in r1) / 1e9 / busy_win
                m["envoy_cpus_run"] = round(envoy_cpus, 5)
                m["sut_foreign_cpus"] = round(sut_run - envoy_cpus, 4)
                m["sut_sibling_cpus"] = round(sum(r1[c] - r0[c] for c in sib if c in r0 and c in r1)
                                              / 1e9 / busy_win, 4) if sib else 0.0
            else:
                m["sched_probe"] = "; ".join(x for x in (rwhy0, rwhy1) if x) or "no schedstat"
            m["ready"] = prober.summary()
            if scraper:
                pc = scraper.summary()
                pc["expected"] = int(busy_win // float(arm["prom_scrape_s"]))
                pc["count_error"] = abs(pc["scrapes"] - pc["expected"])
                m["prom"] = pc
            # the flush count: bursts where the rung's flushes are visible to the sampler, else the
            # interval (at the smallest rung a flush is under the 20 ms resolution)
            visible = shape.get("bursts_visible", True)
            if interval and (not visible or not main.get("bursts")):
                flushes, m["flushes_from"] = int(round(busy_win / interval)), "interval"
            else:
                flushes, m["flushes_from"] = main.get("bursts") or 0, "bursts"
            m["flushes_counted"] = flushes
            if sink:
                m["udp"] = statsrow.udp_window(u0, u1, None, m["used_cg_lines"])
                if "error" not in m["udp"]:
                    # whole flushes between the two quiescent points
                    # flushes the span holds: by the measured period, else the interval (flush
                    # starts are one interval apart); a saturated main thread then fails the count,
                    # closed: its flushes are longer than the interval
                    per = main.get("period_s") if not statsrow.saturated(main.get("run_ms_per_s")) else None
                    exp_n = int(round((tu1 - tu0) / (per or interval)))
                    main["saturated"] = statsrow.saturated(main.get("run_ms_per_s"))
                    sn = m["span_flushes"]["n"]
                    if kind == "statsd":
                        m["udp"]["fit"] = statsrow.flush_fit(m["udp"]["sent"], m["used_cg_lines"], exp_n)
                        if m["udp"]["fit"].get("n"):
                            m["udp"]["sent_per_flush"] = m["udp"]["sent"] / m["udp"]["fit"]["n"]
                            m["udp"]["fit"]["span_n_error"] = abs(m["udp"]["fit"]["n"] - sn)
                    elif sn:
                        # batched lines (T5): datagrams over the whole flushes counted between the two
                        # quiescent points, with that count checked against the span and period
                        m["udp"]["sent_per_flush"] = m["udp"]["sent"] / sn
                        m["udp"]["span_fit"] = {"n": sn, "expected": exp_n, "n_error": abs(sn - exp_n)}
                m.setdefault("side_services", {})["udpsink"] = statsrow.process_side(
                    sink.pid, e["cpus"]["origin"], sk0, sk1, busy_win)
            if coll0 is not None and c1 is not None:
                if "error" in coll0 or "error" in c1:
                    m["collector_delta"] = {"error": coll0.get("error") or c1.get("error")}
                else:
                    cd = {k: c1.get(k, 0) - coll0.get(k, 0) for k in set(coll0) | set(c1)
                          if not k.startswith("_")}
                    sn = m["span_flushes"]["n"]
                    if sn and "accepted_metric_points" in cd:
                        # T5/S3: the collector reads are not atomic with the quiescent points (a
                        # flush can start or finish exporting between a quiescent point and its
                        # read), so the divisor is the whole number of flushes the points hold,
                        # n = round(points / used stats: one point per used counter, gauge and
                        # histogram), and n may differ from the flushes counted in the span by at
                        # most one; a real loss leaves a residual and fails
                        fitd = statsrow.flush_fit(cd["accepted_metric_points"], m.get("used_total"), sn)
                        cd["fit"] = fitd
                        if fitd.get("n"):
                            cd["accepted_metric_points_per_flush"] = cd["accepted_metric_points"] / fitd["n"]
                    cd["settled"] = c1.get("_settled")
                    m["collector_delta"] = cd
        except Exception as ex:  # noqa: BLE001 - recorded as an invalid leg
            m["error"] = "%s: %s" % (type(ex).__name__, ex)
        finally:
            for th in (sampler, prober, scraper, span):
                if th is not None:
                    th.stop_evt.set()
            if envoy is not None:
                st = self._stop_envoy(envoy, elog, elog_path)
                m["envoy_exit"] = st["exit"]
                try:
                    with open(elog_path) as f:
                        m["envoy_log_emfile"] = len(EMFILE_RE.findall(f.read()))
                except OSError:
                    m["envoy_log_emfile"] = None
            if sink is not None:
                m["udpsink"] = statsrow.stop_udpsink(self.own, sink, sink_out)
            if kind == "otlp" and self.collector is not None:
                # the collector's own log over this leg, kept beside the leg
                m["collector_log"] = self.collector.save_log_since(
                    t_leg_wall, os.path.join(self.run_dir, "collector", leg_id + ".log"))
        if arm.get("evidence") is not None:
            from . import evidence
            m["evidence"] = evidence.evaluate(m, arm["evidence"], self.config_dumps.get(arm["name"]),
                                              gate=e.get("evidence_mode", "gate") == "gate")
        m["verdict"] = validity.verdict(m, vcfg)
        return m

    def close(self):
        self.own.stop_all()
