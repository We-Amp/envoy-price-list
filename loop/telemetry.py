#!/usr/bin/env python3
"""The loop's telemetry on one clock (CLOCK_MONOTONIC on the box, 1 s bins).

- CPU: `perf stat -x , -I 1000 -e <events> -p <envoy pid>`. This kernel's perf (6.8) refuses `--timeout` together
  with `-I` ("timeout option is not supported with interval-print"), so the window is ended
  either by a workload (`-- sleep W`, mode "sleep", the default: perf counts the -p target only and exits when the
  sleep ends) or by one SIGINT after W (mode "signal"). The window's totals are the sum of its intervals, so ONE perf
  session per window gives both the scored window count and the per-second rows (no second PMU user, no
  multiplexing).
- Requests: Envoy's own counters from a 1 Hz admin sampler with a tight filter (the same cadence in every arm; it is
  served by Envoy's main thread and counts in Envoy's cycles, identically per arm). No statsd sink.
- Client: Nighthawk live snapshots (nighthawk://series) where the traffic runs through nighthawk_service; the adopted
  nighthawk_client has no live output (its end-of-run JSON is kept per instance).
- Ours: the CPU of every process of ours, and a placement check that none of our threads is allowed on, or last ran
  on, a SUT CPU or a SUT sibling."""
import os
import signal
import subprocess
import threading
import time
import urllib.parse

SAMPLER_FILTER = (r"^http\.ingress_http\.downstream_rq_(2xx|4xx|5xx|completed)$|"
                  r"^http\.ingress_http\.downstream_cx_active$|^cluster\.origin\.upstream_rq_pending_overflow$|"
                  r"^server\.memory_allocated$")
CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
PERF_MODES = ("sleep", "signal")


def mono_ns():
    """CLOCK_MONOTONIC (the box's one clock; Nighthawk's monotonic_ns is the same clock on Linux)."""
    if hasattr(time, "clock_gettime_ns") and hasattr(time, "CLOCK_MONOTONIC"):
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    return time.monotonic_ns()


# flipblock stamps its windows with time.monotonic(); on Linux that IS CLOCK_MONOTONIC (offset ~0). On macOS (the
# local stand-in runs) Python's monotonic clock is process-relative, so the offset maps it onto CLOCK_MONOTONIC.
MONO_OFFSET_S = mono_ns() / 1e9 - time.monotonic()


def from_py_monotonic(t):
    return None if t is None else t + MONO_OFFSET_S


# ---------------------------------------------------------------- perf -I

def perf_interval_cmd(perf, events, pid, window_s, tools_cpus=None, mode="sleep", interval_ms=1000):
    """The per-window perf command. Never `--timeout` (refused with -I by perf 6.8)."""
    if mode not in PERF_MODES:
        raise ValueError("perf mode must be one of %s" % (PERF_MODES,))
    cmd = (["taskset", "-c", str(tools_cpus)] if tools_cpus else []) + list(perf) + [
        "stat", "-x", ",", "-I", str(int(interval_ms)), "-e", events, "-p", str(int(pid))]
    if mode == "sleep":
        cmd += ["--", "sleep", "%g" % float(window_s)]
    return cmd


def parse_intervals(text):
    """[{t, event: value}], {event: total}, {event: min running %} from `perf stat -I -x ,` lines
    (<time>,<count>,<unit>,<event>,<run>,<pct>...). A '<not counted>' or '<not supported>' count is kept as missing,
    which fails the window's count check downstream."""
    rows, tot, run, missing = {}, {}, {}, set()
    for line in (text or "").splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split(",")
        if len(f) < 6:
            continue
        try:
            t = float(f[0])
        except ValueError:
            continue
        ev = f[3]
        try:
            v = float(f[1])
        except ValueError:
            missing.add(ev)
            continue
        try:
            pct = float(f[5]) if f[5] else 100.0
        except ValueError:
            pct = 0.0
        rows.setdefault(t, {"t": t})[ev] = v
        tot[ev] = tot.get(ev, 0.0) + v
        run[ev] = min(run.get(ev, 100.0), pct)
    for ev in missing:
        tot.pop(ev, None)
        run[ev] = 0.0
    return [rows[t] for t in sorted(rows)], tot, run


def totals_text(tot, run):
    """The window's totals in the whole-window `perf stat -x ,` form leg.parse_perf_full reads
    (<count>,<unit>,<event>,<run>,<pct>)."""
    return "".join("%.0f,,%s,0,%.2f,,\n" % (v, ev, run.get(ev, 0.0)) for ev, v in sorted(tot.items()))


def _first_interval_t(path):
    """The first interval's time in perf's stderr so far, or None."""
    try:
        with open(path) as f:
            for line in f:
                fl = line.split(",")
                if len(fl) >= 6 and not line.startswith("#"):
                    try:
                        return float(fl[0])
                    except ValueError:
                        continue
    except OSError:
        pass
    return None


def run_perf_window(cmd, window_s, mode="sleep", timeout_s=None, on_start=None, start=None, stamp_first=False):
    """Run one window's perf. Returns {rc, rc_raw, text, t0_ns, t1_ns, pid, cpu_s, proc}: perf's own CPU from wait4
    (ours, on the tools CPUs), the CLOCK_MONOTONIC instant before it was started and after it was reaped.
    - `start(cmd, **kw)` starts it (the instance runner passes its OwnProcesses.start, so perf is in the ledger
      with its start ticks); by default a plain Popen in its own session;
    - mode "signal": one SIGINT W after perf's counter enable, which is read from its first interval line
      (first-line time minus that line's -I time), not from before the fork;
    - whatever happens (a signal to the runner lands in this wait), perf is stopped in the finally: one SIGINT,
      2 s, then SIGKILL, then reaped. perf's own exit handler ends its `sleep`.
    - `stamp_first` (the perf-form check, `instance.py --perf-ab`): the CLOCK_MONOTONIC arrival of perf's first interval line and
      that line's -I time, as `t_first_line_ns` and `first_interval_t_s` (polled every 10 ms; None if none came)."""
    import tempfile
    timeout_s = float(timeout_s or window_s + 30)
    start = start or (lambda c, **kw: subprocess.Popen(c, start_new_session=True, **kw))
    err = tempfile.NamedTemporaryFile(mode="w+", prefix="epl-perf-", suffix=".err", delete=False)
    p = None
    status = ru = None
    try:
        t0 = mono_ns()
        p = start(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err)
        if on_start:
            on_start(p)
        deadline = time.monotonic() + timeout_s
        sigint_at = None
        if mode == "signal":
            # wait for the first interval line (perf enabled its counters 1 interval before it), then time W from
            # the enable instant
            until = time.monotonic() + 10.0
            while time.monotonic() < until and p.poll() is None:
                first = _first_interval_t(err.name)
                if first is not None:
                    sigint_at = mono_ns() / 1e9 - first + float(window_s)
                    break
                time.sleep(0.02)
            if sigint_at is None:
                sigint_at = t0 / 1e9 + float(window_s)
        first_ns = first_t = None
        while True:
            pid, status, ru = os.wait4(p.pid, os.WNOHANG)
            if stamp_first and first_ns is None:
                ft = _first_interval_t(err.name)
                if ft is not None:
                    first_ns, first_t = mono_ns(), ft
            if pid:
                break
            if sigint_at is not None and mono_ns() / 1e9 >= sigint_at:
                try:
                    p.send_signal(signal.SIGINT)
                except OSError:
                    pass
                sigint_at = None
            if time.monotonic() > deadline:
                p.kill()
                pid, status, ru = os.wait4(p.pid, 0)
                break
            time.sleep(0.01)
        t1 = mono_ns()
        p.returncode = os.waitstatus_to_exitcode(status)
        err.seek(0)
        text = err.read()
    finally:
        if p is not None and status is None:
            # interrupted (a signal to the runner, an exception): never leave perf behind
            for sig, wait_s in ((signal.SIGINT, 2.0), (signal.SIGKILL, 5.0)):
                try:
                    p.send_signal(sig)
                except OSError:
                    break
                end = time.monotonic() + wait_s
                done = False
                while time.monotonic() < end:
                    try:
                        if os.wait4(p.pid, os.WNOHANG)[0]:
                            done = True
                            break
                    except ChildProcessError:
                        done = True
                        break
                    time.sleep(0.02)
                if done:
                    p.returncode = -int(sig)
                    break
        err.close()
        try:
            os.unlink(err.name)
        except OSError:
            pass
    rc = p.returncode
    if mode == "signal" and rc in (-signal.SIGINT, 128 + signal.SIGINT) and parse_intervals(text)[0]:
        rc = 0  # the planned stop: perf ended by our SIGINT with its intervals printed
    return {"rc": rc, "rc_raw": p.returncode, "text": text, "t0_ns": t0, "t1_ns": t1, "pid": p.pid, "proc": p,
            "cpu_s": round((ru.ru_utime + ru.ru_stime) if ru else 0.0, 4),
            **({"t_first_line_ns": first_ns, "first_interval_t_s": first_t} if stamp_first else {})}


def absolute_rows(rows, t0_ns, window=None, label=None):
    """perf's relative interval times onto the box's CLOCK_MONOTONIC (s)."""
    out = []
    prev = 0.0
    for r in rows:
        x = dict(r, t_mono_s=round(t0_ns / 1e9 + r["t"], 6),
                 t_mid_mono_s=round(t0_ns / 1e9 + (prev + r["t"]) / 2.0, 6))
        prev = r["t"]
        if window is not None:
            x["window"] = window
        if label is not None:
            x["label"] = label
        out.append(x)
    return out


# ---------------------------------------------------------------- the admin sampler

class AdminSampler:
    """Filtered admin reads, on their own thread, kept in memory and pulled once per step (NL 5.2: never streamed
    per sample). Each read is stamped with CLOCK_MONOTONIC at its start (`t_start_mono_s`) and at its end
    (`t_mono_s`).

    the reads are phase-locked to the windows:
    - `lock_window(t0, W)` first waits for a read in flight to complete (a read lock), so no read straddles the
      window's start, then schedules exactly W reads at t0 + 0.5 + j (j = 0..W-1);
    - after the window's last planned read the sampler waits; `start_gap(t)` (perf's real end + 0.5 s) starts the
      gap reads, one per period, until the next lock. There is no other gap schedule.
    Before the first window it reads freely, once per period. Every window of an instance therefore carries the
    same number of reads (a read is served by Envoy's main thread and counts in Envoy's cycles)."""

    def __init__(self, get, period_s=1.0, flt=SAMPLER_FILTER):
        self.get = get
        self.period = float(period_s)
        self.path = "/stats?filter=" + urllib.parse.quote(flt)
        self.samples = []
        self.errors = 0
        self._stop = threading.Event()
        self._cv = threading.Condition()
        self._read_lock = threading.Lock()
        self._plan = []
        self._next = None
        self._mode = "free"  # free | window | await_gap | gap
        self._t = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._t.start()
        return self

    def lock_window(self, t0_s, window_s):
        with self._read_lock:  # an in-flight read completes first
            with self._cv:
                self._plan = [t0_s + 0.5 + j * self.period for j in range(int(window_s))]
                self._mode = "window"
                self._next = self._plan[0] if self._plan else None
                if not self._plan:
                    self._mode = "await_gap"
                self._cv.notify_all()

    def start_gap(self, t_s):
        """After a window's perf has ended: the gap reads start at t_s, never inside the window just measured."""
        with self._cv:
            self._plan = []
            self._mode = "gap"
            self._next = t_s
            self._cv.notify_all()

    def _take(self, now):
        with self._cv:
            if self._next is None and self._mode == "free":
                self._next = now
            return self._next

    def _advance(self, due):
        """After the read that was due at `due`: only that read leaves the plan (a window locked while a read was in
        flight keeps all its reads)."""
        with self._cv:
            if self._mode == "window":
                if self._plan and self._plan[0] == due:
                    self._plan.pop(0)
                if self._plan:
                    self._next = self._plan[0]
                else:
                    self._mode, self._next = "await_gap", None
            elif self._next == due:
                self._next = due + self.period

    def _read(self, due=None):
        """One read. With `due`: after taking the read lock, the read happens only if it is still the one due
        (a lock_window or start_gap that landed between the schedule check and the lock replans it). Returns False when skipped."""
        with self._read_lock:
            if due is not None:
                with self._cv:
                    if self._next != due:
                        return False
            t0 = mono_ns()
            try:
                st, body = self.get(self.path)
                t = mono_ns()
                if st == 200:
                    vals = {}
                    for line in body.splitlines():
                        if ": " in line:
                            a, b = line.split(": ", 1)
                            try:
                                vals[a.strip()] = int(b.strip())
                            except ValueError:
                                pass
                    self.samples.append({"t_start_mono_s": round(t0 / 1e9, 6), "t_mono_s": round(t / 1e9, 6),
                                         "v": vals})
                else:
                    self.errors += 1
            except Exception:  # noqa: BLE001 - Envoy not up yet, or gone: counted
                self.errors += 1
        return True

    def _loop(self):
        while not self._stop.is_set():
            due = self._take(mono_ns() / 1e9)
            with self._cv:
                if due is None:
                    self._cv.wait(0.5)  # waiting for start_gap or the next window
                    continue
                left = due - mono_ns() / 1e9
                if left > 0:
                    self._cv.wait(left)
                    if self._next != due:  # replanned (a window was locked, or the gap started): start over
                        continue
            if self._stop.is_set():
                break
            if mono_ns() / 1e9 + 1e-3 < due:
                continue
            if not self._read(due):
                continue  # replanned while waiting for the lock: start over on the new schedule
            self._advance(due)

    def stop(self):
        self._stop.set()
        with self._cv:
            self._cv.notify_all()
        if self._t.is_alive():
            self._t.join(timeout=5.0)
        return self.samples


def reads_in(samples, t_start, t_end):
    """A window's reads are those that STARTED inside its span (perf's own: anchor_end .. + span)."""
    return sum(1 for x in samples if t_start <= x.get("t_start_mono_s", x["t_mono_s"]) <= t_end)


# ---------------------------------------------------------------- the timeline

def _cycles(r):
    if "cycles:u" in r and "cycles:k" in r:
        return r["cycles:u"] + r["cycles:k"]
    return r.get("cycles")


def timeline(perf_rows, admin_samples, nh_series=None, windows=None, anchor_s=None):
    """Per-second rows on one clock. Bin b covers [anchor + b, anchor + b + 1) s of CLOCK_MONOTONIC.
    - perf rows (absolute t_mono_s, the interval's end; t_mid_mono_s its midpoint) go to the bin their midpoint
      falls in;
    - admin samples give per-bin deltas of the 2xx counter (later sample's bin);
    - nh_series: {name: [(t_mono_s, cumulative value)]}, per-bin deltas the same way;
    - windows: [{k, label, t_perf_start, t_perf_end}] labels each bin by the window it falls in (else "gap").
    cycles per request per bin uses Envoy's own 2xx count."""
    pts = [r["t_mono_s"] for r in perf_rows] + [s["t_mono_s"] for s in admin_samples]
    for ser in (nh_series or {}).values():
        pts += [t for t, _ in ser]
    if not pts:
        return {"anchor_mono_s": anchor_s, "rows": []}
    anchor = float(anchor_s if anchor_s is not None else min(pts))
    bins = {}

    def bn(t):
        return int((t - anchor) // 1.0)
    for r in perf_rows:
        b = bins.setdefault(bn(r.get("t_mid_mono_s", r["t_mono_s"])), {})
        c = _cycles(r)
        if c is not None:
            b["cycles"] = b.get("cycles", 0.0) + c
        if "instructions:u" in r:
            b["instructions_u"] = b.get("instructions_u", 0.0) + r["instructions:u"]
        if "task-clock" in r:
            b["task_clock_ms"] = b.get("task_clock_ms", 0.0) + r["task-clock"]
    prev = None
    for s in sorted(admin_samples, key=lambda x: x["t_mono_s"]):
        if prev is not None:
            b = bins.setdefault(bn(s["t_mono_s"]), {})
            for key, out in (("http.ingress_http.downstream_rq_2xx", "envoy_2xx"),
                             ("http.ingress_http.downstream_rq_5xx", "envoy_5xx")):
                if key in s["v"] and key in prev["v"]:
                    b[out] = b.get(out, 0) + s["v"][key] - prev["v"][key]
            if "http.ingress_http.downstream_cx_active" in s["v"]:
                b["envoy_cx_active"] = s["v"]["http.ingress_http.downstream_cx_active"]
        prev = s
    for name, ser in (nh_series or {}).items():
        ser = sorted(ser)
        for (t0, v0), (t1, v1) in zip(ser, ser[1:]):
            b = bins.setdefault(bn(t1), {})
            key = "client_" + name.replace(".", "_")
            b[key] = b.get(key, 0) + (v1 - v0)
    rows = []
    for k in sorted(bins):
        b = dict(bins[k], bin=k, t_s=k)
        t_mid = anchor + k + 0.5
        lab = "gap"
        for w in windows or []:
            if w.get("t_perf_start") is not None and w["t_perf_start"] <= t_mid < w["t_perf_end"]:
                lab = "w%02d:%s" % (w["k"], w["label"])
        b["phase"] = lab
        if b.get("cycles") and b.get("envoy_2xx"):
            b["cycles_per_request"] = round(b["cycles"] / b["envoy_2xx"], 3)
        rows.append(b)
    return {"anchor_mono_s": round(anchor, 6), "bin_s": 1.0, "clock": "CLOCK_MONOTONIC (box)", "rows": rows}


# ---------------------------------------------------------------- ours: CPU and placement

def proc_cpu_s(pid):
    """utime + stime of a whole process, in seconds (None when gone)."""
    try:
        with open("/proc/%d/stat" % int(pid)) as f:
            st = f.read()
        fl = st[st.rindex(")") + 2:].split()
        return (int(fl[11]) + int(fl[12])) / float(CLK_TCK)
    except (OSError, ValueError, IndexError):
        return None


def _cpuset(spec):
    out = set()
    for part in str(spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def thread_placement(pid):
    """[(tid, allowed cpus, last cpu)] for every thread of pid, from /proc (empty off Linux or when gone)."""
    out = []
    base = "/proc/%d/task" % int(pid)
    try:
        tids = os.listdir(base)
    except OSError:
        return out
    for t in tids:
        try:
            allowed = None
            with open("%s/%s/status" % (base, t)) as f:
                for line in f:
                    if line.startswith("Cpus_allowed_list:"):
                        allowed = _cpuset(line.split(":", 1)[1])
            with open("%s/%s/stat" % (base, t)) as f:
                st = f.read()
            last = int(st[st.rindex(")") + 2:].split()[36])
            out.append((int(t), allowed, last))
        except (OSError, ValueError, IndexError):
            continue
    return out


def placement_violations(pids, forbidden, placement=thread_placement, check_last=True):
    """Every thread of ours allowed on, or (check_last) last run on, a forbidden CPU (the SUT CPUs and their
    siblings)."""
    bad = []
    forbidden = set(forbidden)
    for pid in pids:
        for tid, allowed, last in placement(pid):
            if (allowed is not None and allowed & forbidden) or (check_last and last in forbidden):
                bad.append({"pid": int(pid), "tid": tid, "allowed": sorted(allowed or []), "last_cpu": last})
    return bad
