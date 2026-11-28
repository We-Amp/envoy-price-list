"""Per-worker Envoy CPU per bin, read from /proc with no Envoy involvement (the admin scrape runs on Envoy's main
thread, which an event may be loading), and aligned to the perf clock.

- **The source is schedstat**: the first field of /proc/<pid>/task/<tid>/schedstat is the
  thread's exact on-CPU time in ns (sum_exec_runtime). utime and stime (stat fields 14 and 15, clock ticks) are tick
  samples in 10 ms units on a kernel without full-dynticks accounting, so they are kept only as a cross-check.
- `WorkerCpuSampler` reads every `wrk:worker_N` thread and the main thread (tid == pid, so a main-thread event is
  then visible as itself) every `sample_s` on CLOCK_MONOTONIC, from a thread the caller may pin. A worker thread that
  appears or disappears is recorded (`threads_changed`), and the record then fails closed.
- `LineStamper` reads `perf stat -I` lines as perf prints them and stamps each with CLOCK_MONOTONIC on arrival. It
  calls `on_interval(t, ns)` on the first line of every new interval (the event block scrapes the admin then, so the
  per-bin request counts are counted at the bin edges, not interpolated). perf's interval times are seconds since
  perf started counting; `align_perf_clock` places that origin at min(arrival - t) and reports the largest lag as
  the alignment's uncertainty.
- `bin_worker_cpu` interpolates each thread's cumulative ns to the perf interval edges (samples are 4 or more per
  bin, so the interpolation spans at most one sample gap), giving each bin's per-worker cores, the busiest and the
  mean worker, max/mean, and the main thread's cores. A bin the samples do not cover is None (never extrapolated).
"""

import os
import re
import threading
import time

PROC = "/proc"
WORKER_COMM_RE = re.compile(r"^wrk:worker_(\d+)$")
MAIN = "main"


def clk_tck():
    try:
        return os.sysconf("SC_CLK_TCK")
    except (ValueError, OSError, AttributeError):
        return 100


def parse_task_stat(text):
    """(comm, utime, stime) from a /proc/<pid>/task/<tid>/stat line (comm may hold spaces and parentheses)."""
    a, b = text.index("("), text.rindex(")")
    comm = text[a + 1:b]
    f = text[b + 2:].split()
    # f[0] is field 3 (state): utime is field 14, stime field 15
    return comm, int(f[11]), int(f[12])


def parse_schedstat(text):
    """The on-CPU time in ns: the first field of /proc/<pid>/task/<tid>/schedstat."""
    return int(text.split()[0])


def worker_threads(pid, proc=PROC):
    """{worker index: tid} of the process's `wrk:worker_N` threads."""
    out = {}
    try:
        tids = os.listdir(os.path.join(proc, str(pid), "task"))
    except OSError:
        return out
    for t in tids:
        try:
            with open(os.path.join(proc, str(pid), "task", t, "comm")) as f:
                comm = f.read().strip()
        except OSError:
            continue
        m = WORKER_COMM_RE.match(comm)
        if m:
            out[int(m.group(1))] = int(t)
    return out


def read_cpu(pid, tids, proc=PROC):
    """{worker index: [run_ns, utime, stime]} for the given {index: tid}, plus "main" (tid == pid). A thread that
    cannot be read, or whose comm is no longer a worker's, is left out."""
    out = {}
    for i, tid in list(tids.items()) + [(MAIN, pid)]:
        d = os.path.join(proc, str(pid), "task", str(tid))
        try:
            with open(os.path.join(d, "stat")) as f:
                comm, u, s = parse_task_stat(f.read())
            with open(os.path.join(d, "schedstat")) as f:
                ns = parse_schedstat(f.read())
        except (OSError, ValueError, IndexError):
            continue
        if i == MAIN or WORKER_COMM_RE.match(comm):
            out[i] = [ns, u, s]
    return out


class WorkerCpuSampler(threading.Thread):
    """Samples every worker thread (and the main thread) every sample_s, on a fixed schedule from its start, so a slow
    read never shifts later samples. `threads` and `read` are injectable (tests); by default /proc."""

    def __init__(self, pid, sample_s, cpus=None, threads=None, read=None, clock_ns=time.monotonic_ns):
        super().__init__(daemon=True)
        self.pid = pid
        self.sample_s = float(sample_s)
        self.cpus = cpus
        self._threads = threads or (lambda: worker_threads(pid))
        self._read = read or (lambda tids: read_cpu(pid, tids))
        self.clock_ns = clock_ns
        self.stop_evt = threading.Event()
        self.samples = []
        self.tids = None
        self.threads_changed = []
        self.errors = []

    def _sample(self):
        ticks = self._read(self.tids)
        now = self.clock_ns()
        want = set(self.tids) | {MAIN}
        if set(ticks) != want:
            self.threads_changed.append({"mono_ns": now, "missing": sorted(str(x) for x in want - set(ticks))})
        self.samples.append({"mono_ns": now, "w": ticks})

    def run(self):
        if self.cpus and hasattr(os, "sched_setaffinity"):
            try:
                os.sched_setaffinity(0, self.cpus)  # this thread only (Linux: a tid)
            except OSError as ex:
                self.errors.append("affinity: %s" % ex)
        self.tids = self._threads()
        t0 = self.clock_ns()
        k = 0
        while not self.stop_evt.is_set():
            self._sample()
            k += 1
            wait = (t0 + int(k * self.sample_s * 1e9) - self.clock_ns()) / 1e9
            if wait > 0:
                self.stop_evt.wait(wait)
        self._sample()  # one last sample at the stop, so the run's last bin is covered
        after = self._threads()
        if set(after) != set(self.tids):
            self.threads_changed.append({"mono_ns": self.clock_ns(), "before": sorted(self.tids),
                                         "after": sorted(after)})

    def crosscheck(self, hz=None):
        """Per worker, over the whole run: schedstat cores against utime + stime ticks (the tick cross-check)."""
        hz = float(hz or clk_tck())
        if len(self.samples) < 2:
            return {}
        a, b = self.samples[0], self.samples[-1]
        span = (b["mono_ns"] - a["mono_ns"]) / 1e9
        out = {}
        for i in sorted(set(a["w"]) & set(b["w"]), key=str):
            ns = (b["w"][i][0] - a["w"][i][0]) / 1e9 / span if span > 0 else None
            tk = ((b["w"][i][1] + b["w"][i][2]) - (a["w"][i][1] + a["w"][i][2])) / hz / span if span > 0 else None
            out[str(i)] = {"schedstat_cores": ns, "tick_cores": tk}
        return out

    def record(self, workers=None):
        """{ok, reasons, workers, n_samples, max_gap_s, crosscheck}: fail closed on a worker count other than planned,
        a thread change, no main thread, a gap of more than 2 x sample_s, or fewer than 2 samples."""
        why = []
        n = len(self.tids or {})
        if workers is not None and n != int(workers):
            why.append("found %d wrk:worker_N threads, planned %d" % (n, int(workers)))
        if self.threads_changed:
            why.append("worker threads changed during the run: %s" % self.threads_changed[:3])
        if len(self.samples) < 2:
            why.append("fewer than 2 worker CPU samples")
        ts = [s["mono_ns"] for s in self.samples]
        gap = max((b - a for a, b in zip(ts, ts[1:])), default=0) / 1e9
        if gap > 2 * self.sample_s + 0.05:
            why.append("a %.3f s gap between worker CPU samples (sample_s %.3f)" % (gap, self.sample_s))
        return {"ok": not why, "reasons": why, "workers": sorted(self.tids or {}), "n_samples": len(self.samples),
                "max_gap_s": round(gap, 4), "sample_s": self.sample_s, "errors": self.errors,
                "source": "schedstat ns (utime + stime ticks as the cross-check)", "crosscheck": self.crosscheck()}


# ---------------------------------------------------------------- perf's clock on CLOCK_MONOTONIC

def _interval_time(line):
    if line.startswith("#"):
        return None
    f = line.split(",")
    if len(f) < 4:
        return None
    try:
        return float(f[0])
    except ValueError:
        return None


class LineStamper(threading.Thread):
    """Reads a text stream line by line and stamps each line with CLOCK_MONOTONIC (ns) on arrival; calls
    on_interval(t, ns) on the first line of each new interval."""

    def __init__(self, stream, clock_ns=time.monotonic_ns, on_interval=None):
        super().__init__(daemon=True)
        self.stream = stream
        self.clock_ns = clock_ns
        self.on_interval = on_interval
        self.lines = []

    def run(self):
        seen = set()
        for line in iter(self.stream.readline, ""):
            ns = self.clock_ns()
            line = line.rstrip("\n")
            self.lines.append((ns, line))
            t = _interval_time(line)
            if t is not None and t not in seen:
                seen.add(t)
                if self.on_interval is not None:
                    self.on_interval(t, ns)

    def text(self):
        return "\n".join(x for _, x in self.lines)


def interval_arrivals(stamped):
    """{interval time t (s): first arrival (ns)} from stamped `perf stat -I -x ,` lines."""
    out = {}
    for ns, line in stamped:
        t = _interval_time(line)
        if t is not None:
            out[t] = min(out.get(t, ns), ns)
    return out


def align_perf_clock(stamped):
    """perf's t = 0 on CLOCK_MONOTONIC: min over intervals of (arrival - t), and the largest lag over it (the
    alignment's uncertainty: how much later than its interval's end a line arrived). None without intervals."""
    arr = interval_arrivals(stamped)
    if not arr:
        return None
    offs = [ns - int(round(t * 1e9)) for t, ns in arr.items()]
    o = min(offs)
    return {"origin_mono_ns": o, "max_lag_ms": round((max(offs) - o) / 1e6, 3), "intervals": len(arr)}


def align_tolerance_ms(interval_ms):
    """The largest alignment lag a run may carry, min(10% of a bin, 25 ms)."""
    return min(0.1 * float(interval_ms), 25.0)


def perf_bins(rows, origin_ns):
    """The perf interval rows (epl.clientcheck.parse_intervals) as bins on CLOCK_MONOTONIC: [{t0_ns, t1_ns, dt_s,
    t_rel (perf's own interval end), counts}]."""
    out, prev = [], 0.0
    for r in rows:
        t = r["t"]
        counts = {k: v for k, v in r.items() if k not in ("t", "_uncounted")}
        out.append({"t0_ns": origin_ns + int(round(prev * 1e9)), "t1_ns": origin_ns + int(round(t * 1e9)),
                    "dt_s": t - prev, "t_rel0": prev, "t_rel": t, "counts": counts,
                    "uncounted": r.get("_uncounted") or []})
        prev = t
    return out


# ---------------------------------------------------------------- per-worker CPU per bin

def _interp(samples, idx, t_ns):
    """Thread idx's cumulative on-CPU ns at t_ns, linear between the samples around it; None outside them or where
    the thread is missing."""
    prev = None
    for s in samples:
        if idx not in s["w"]:
            continue
        v = s["w"][idx][0]
        if s["mono_ns"] == t_ns:
            return float(v)
        if s["mono_ns"] > t_ns:
            if prev is None:
                return None
            (t0, v0) = prev
            return v0 + (v - v0) * (t_ns - t0) / float(s["mono_ns"] - t0)
        prev = (s["mono_ns"], v)
    return None


def bin_worker_cpu(samples, bins):
    """Per bin: {worker index: cores} (schedstat ns), the busiest and the mean worker (cores), max/mean and the main
    thread's cores; None for a bin the samples do not cover."""
    idxs = sorted({i for s in samples for i in s["w"] if i != MAIN})
    out = []
    for b in bins:
        dt = (b["t1_ns"] - b["t0_ns"]) / 1e9
        cores = {}
        for i in idxs:
            a, c = _interp(samples, i, b["t0_ns"]), _interp(samples, i, b["t1_ns"])
            if a is None or c is None or dt <= 0:
                cores = None
                break
            cores[i] = round((c - a) / 1e9 / dt, 6)
        if not cores:
            out.append(None)
            continue
        mx, mean = max(cores.values()), sum(cores.values()) / len(cores)
        a, c = _interp(samples, MAIN, b["t0_ns"]), _interp(samples, MAIN, b["t1_ns"])
        out.append({"cores": cores, "max": round(mx, 6), "mean": round(mean, 6),
                    "max_over_mean": round(mx / mean, 6) if mean > 0 else None,
                    "main_cores": round((c - a) / 1e9 / dt, 6) if a is not None and c is not None else None})
    return out
