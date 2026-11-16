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
import os
import re
import signal
import subprocess
import threading
import time
import urllib.parse

from . import experiment as _exp
from . import nighthawk, sysprobe, validity

PERF_EVENTS = "instructions:u,cycles:u,cycles:k,instructions:k,task-clock,context-switches,cpu-migrations"


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
               r"cx_destroy_local|cx_destroy_remote|cx_destroy_local_with_active_rq|cx_destroy_remote_with_active_rq|"
               r"cx_max_requests|cx_idle_timeout|cx_max_duration_reached|rq_reset|cx_protocol_error|rq_503|"
               r"flow_control_[a-z_]+)$|"
               r"listener\..*\.(ssl\.(handshake|session_reused|connection_error|no_certificate)|downstream_cx_total|"
               r"downstream_cx_active)$|"
               r"listener\..*\.ssl\.(versions|ciphers|curves|sigalgs)\.|"
               r"tracing\.|access_logs\.|[a-z_]+\.http_local_rate_limit\.)")
# deltas of these are recorded per leg (counters only; gauges and histograms are skipped)
DELTA_KEYS_RE = re.compile(r"(ext_authz\.|tracing\.|jwt_authn\.|http_local_rate_limit\.|ssl\.|upstream_rq_retry|upstream_rq_total|upstream_cx_total|"
                           r"downstream_cx_total|downstream_rq_total|downstream_rq_2xx|rq_timeout|cx_destroy$|overflow|"
                           r"cx_destroy_local|cx_destroy_remote|cx_max_requests|max_requests_reached|idle_timeout|"
                           r"max_duration_reached|"
                           r"rq_reset|protocol_error|rq_5xx|rq_503|"
                           r"flow_control_)")
# cumulative values recorded at the end of the window: what TLS negotiated (keep-alive
# connections handshake before the window) and the gauges of open connections
END_KEYS_RE = re.compile(r"(ssl\.(versions|ciphers|curves|sigalgs)\.|upstream_cx_active$|downstream_cx_active$)")


def admin_stats(port):
    st, body = admin_get(port, "/stats?filter=" + urllib.parse.quote(STAT_FILTER))
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

    def _idle_cpus(self):
        c = sysprobe.parse_cpuset(self.exp["cpus"]["sut"]) | sysprobe.parse_cpuset(self.exp["cpus"].get("hop2", ""))
        return c | sysprobe.siblings_of(c)

    def own_pids(self):
        return self.own.pids()

    def _start_envoy(self, binary, bootstrap, cpus, workers, admin_port, env, extra, log_path):
        elog = open(log_path, "w")
        cmd = ["taskset", "-c", cpus, binary, "-c", bootstrap, "--concurrency", str(workers),
               "--use-dynamic-base-id", "-l", self.exp["envoy"].get("log_level", "warn")] + list(extra)
        p = self.own.start(cmd, stdout=elog, stderr=subprocess.STDOUT, env=dict(os.environ, **env))
        if not wait_ready(admin_port, 60, p):
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
        sut_set = sysprobe.parse_cpuset(e["cpus"]["sut"])
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
        must_open = [e["origin"]["port"]] if shape["kind"] == "proxied" else []
        if aenv.get("ext_authz"):
            must_open.append(aenv["authz_grpc_port"] if aenv["ext_authz"] == "grpc" else aenv["authz_port"])
        if aenv.get("tracing"):
            must_open.append(aenv["collector_port"])
        free = [ecfg["listener_port"], ecfg["admin_port"]]
        if hop2_set:
            free += [e["hop2"]["listener_port"], e["hop2"]["admin_port"]]
        ok, det = sysprobe.port_preflight(free, must_open)
        m.update(preflight_ok=ok, preflight_detail=det)
        if not (m["idle_ok"] and m["preflight_ok"]):
            m["verdict"] = validity.verdict(m, vcfg)
            return m
        envoy = None
        hop_b = None
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
            envoy, elog = self._start_envoy(arm["binary"], bootstrap_path, e["cpus"]["sut"], ecfg["workers"],
                                            ecfg["admin_port"], env, arm.get("extra_args", []), elog_path)
            m["envoy_pid"] = envoy.pid
            if not sysprobe.port_open("127.0.0.1", ecfg["listener_port"]):
                raise RuntimeError("listener port not open after ready")
            sut_cpus = sysprobe.cpus_allowed(envoy.pid)
            m["sut_cpus_allowed"] = sut_cpus
            pin_ok = pin_ok and sysprobe.parse_cpuset(sut_cpus) == sysprobe.parse_cpuset(e["cpus"]["sut"])
            scheme = "https" if aenv.get("tls") else "http"
            url = "%s://127.0.0.1:%d%s" % (scheme, ecfg["listener_port"], shape["path"])
            cextra = list(shape.get("client_extra_args") or [])
            nh = ccfg["binary"]
            # 4. warm-up
            if ccfg.get("warmup_s", 0) > 0:
                wa = nighthawk.client_args(ccfg, shape["rps"], url, ccfg["warmup_s"], False, cextra,
                                             shape.get("client_base_args"))
                w = self.own.start(["taskset", "-c", e["cpus"]["client"], nh] + wa,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    w.wait(timeout=ccfg["warmup_s"] + 60)
                finally:
                    self.own.stop(w)
            # 5. measured run
            nh_json = os.path.join(self.run_dir, "nighthawk", leg_id + ".json")
            ma = nighthawk.client_args(ccfg, shape["rps"], url, ccfg["duration_s"], True, cextra,
                                         shape.get("client_base_args"))
            m["client_args"] = ma
            with open(nh_json, "w") as out, open(os.path.join(self.run_dir, "logs", leg_id + ".client.log"), "w") as cerr:
                cl = self.own.start(["taskset", "-c", e["cpus"]["client"], nh] + ma, stdout=out, stderr=cerr)
                try:
                    time.sleep(mcfg["lead_in_s"])
                    cl_cpus = sysprobe.cpus_allowed(cl.pid)
                    pin_ok = pin_ok and sysprobe.parse_cpuset(cl_cpus) == sysprobe.parse_cpuset(e["cpus"]["client"])
                    m["client_cpus_allowed"] = cl_cpus
                    c0 = sysprobe.proc_threads_cpu(cl.pid)
                    e0 = sysprobe.proc_threads_detail(envoy.pid)
                    b0 = sysprobe.proc_threads_detail(hop_b.pid) if hop_b else None
                    q0 = admin_stats(ecfg["admin_port"])
                    qb0 = admin_stats(e["hop2"]["admin_port"]) if hop_b else None
                    p0 = sysprobe.per_cpu_times()
                    k0 = sysprobe.proc_run_ns(envoy.pid)
                    kb0 = sysprobe.proc_run_ns(hop_b.pid) if hop_b else 0
                    r0, rwhy0 = sysprobe.cpu_run_ns()
                    i0 = sysprobe.cpuidle_counts(sysprobe.parse_cpuset(e["cpus"]["sut"]) | hop2_set)
                    t0 = time.monotonic()
                    pcmd = lambda pid: self.perf + ["stat", "-x", ",", "-e", PERF_EVENTS, "-p", str(pid),  # noqa: E731
                                                    "--", "sleep", str(mcfg["window_s"])]
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
                    i1 = sysprobe.cpuidle_counts(sysprobe.parse_cpuset(e["cpus"]["sut"]) | hop2_set)
                    m["cpuidle_residency"] = sysprobe.cpuidle_residency(i0, i1, t1 - t0)
                    r1, rwhy1 = sysprobe.cpu_run_ns()
                    k1 = sysprobe.proc_run_ns(envoy.pid)
                    kb1 = sysprobe.proc_run_ns(hop_b.pid) if hop_b else 0
                    p1 = sysprobe.per_cpu_times()
                    q1 = admin_stats(ecfg["admin_port"])
                    qb1 = admin_stats(e["hop2"]["admin_port"]) if hop_b else None
                    t2 = time.monotonic()
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
                    cl.wait(timeout=ccfg["duration_s"] + 120)
                finally:
                    self.own.stop(cl)
            m["pinning_ok"] = pin_ok
            with open(os.path.join(self.run_dir, "perf", leg_id + ".csv"), "w") as f:
                f.write(pr.stderr)
            pv, prun = parse_perf_full(pr.stderr)
            # Admin snapshots bracket the perf command, so the response count
            # covers a slightly longer span than the counters do; scale it to the
            # perf window (same for every arm, it only fixes absolute numbers).
            win = t2 - t0
            perf_s = float(mcfg["window_s"])
            resp_raw = _delta(q0, q1, "http.ingress_http.downstream_rq_2xx")
            resp = resp_raw * perf_s / win if win > 0 else 0
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
            ws = _worker_share(m["envoy_threads"], int(ecfg["workers"]), envoy.pid)
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
            m.update(
                window_s=round(win, 4), perf_window_s=perf_s, responses_raw=resp_raw, responses=resp,
                sut_rate_2xx=resp_raw / win if win > 0 else 0.0,
                sut_non2xx=non2,
                upstream_cx_opened=_delta(q0, q1, "cluster.origin.upstream_cx_total"),
                perf_raw=pv,
                perf_ok=all(k in pv for k in ("instructions:u", "cycles:u", "cycles:k")),
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
                cu, ck, iu = pv["cycles:u"], pv["cycles:k"], pv["instructions:u"]
                tc = pv.get("task-clock", 0.0)  # msec
                m["per_req"] = {
                    "instructions_u": iu / resp,
                    "instructions_k": pv.get("instructions:k", 0.0) / resp,
                    "cycles_u": cu / resp,
                    "cycles_k": ck / resp,
                    "cycles_total": (cu + ck) / resp,
                    "task_clock_us": tc * 1000.0 / resp,
                    "context_switches": pv.get("context-switches", 0.0) / resp,
                    "cpu_migrations": pv.get("cpu-migrations", 0.0) / resp,
                }
                m["sut_busy"] = tc / 1000.0 / (mcfg["window_s"] * ecfg["workers"])
                m["eff_ghz"] = (cu + ck) / (tc / 1000.0) / 1e9 if tc else None
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
            if envoy is not None:
                st = self._stop_envoy(envoy, elog, elog_path)
                m["envoy_exit"] = st["exit"]
                m["envoy_log_deprecated_lines"] = st.get("deprecated_lines")
                m["envoy_log_bytes"] = st.get("log_bytes")
            if hop_b is not None:
                st = self._stop_envoy(hop_b, belog, blog)
                m["hop2_exit"] = st["exit"]
                if st["exit"] not in (0, None) and m.get("envoy_exit") in (0, None):
                    m["envoy_exit"] = st["exit"]
            if alog and os.path.exists(alog):
                # every request should have a line (written by the flush thread, flushed at exit)
                n, size = _count_lines(alog)
                m["access_log_lines"], m["access_log_bytes"] = n, size
                with open(alog, "rb") as f:
                    sample = f.read(4096)
                with open(os.path.join(self.run_dir, "alog", leg_id + ".sample"), "wb") as f:
                    f.write(sample)
                with open(alog, "w"):
                    pass  # keep the run directory small: sample kept, file emptied
        m["verdict"] = validity.verdict(m, vcfg)
        return m

    def close(self):
        self.own.stop_all()
