"""Linux probes: port preflight, idle check, process CPU accounting, run metadata.

Rules encoded here:
- Port checks use a plain Python socket connect, nothing else.
- Process checks use `pgrep -f` (full command line). Bare pgrep matches the
  15-character comm name and misses or mismatches long binary names.
- The idle check excludes this process and its ancestors, so the harness never
  sees itself as load.
"""

import hashlib
import hmac
import os
import platform
import re
import socket
import subprocess
import time

CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


# ---------------------------------------------------------------- hashing

def file_hashes(path):
    md5 = hashlib.md5()
    sha = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            md5.update(b)
            sha.update(b)
            size += len(b)
    return {"md5": md5.hexdigest(), "sha256": sha.hexdigest(), "size": size}


def text_sha256(text):
    if isinstance(text, str):
        text = text.encode()
    return hashlib.sha256(text).hexdigest()


# ---------------------------------------------------------------- ports

def port_open(host, port, timeout=0.5):
    """True when something accepts a TCP connection on host:port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def port_preflight(must_be_free, must_be_open, host="127.0.0.1"):
    """Return (ok, detail). must_be_free: ports nobody listens on yet."""
    problems = []
    for p in must_be_free:
        if port_open(host, p):
            problems.append("port %d already in use" % p)
    for p in must_be_open:
        if not port_open(host, p):
            problems.append("port %d not accepting connections" % p)
    return (not problems, "; ".join(problems) or "ok")


def wait_port(host, port, timeout_s):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if port_open(host, port):
            return True
        time.sleep(0.1)
    return False


# ---------------------------------------------------------------- /proc

def loadavg1():
    with open("/proc/loadavg") as f:
        return float(f.read().split()[0])


def _cpu_times():
    with open("/proc/stat") as f:
        parts = f.readline().split()[1:]
    vals = [int(x) for x in parts]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)  # idle + iowait
    return sum(vals[:8]), idle


def system_busy_pct(sample_s=1.0):
    t0, i0 = _cpu_times()
    time.sleep(sample_s)
    t1, i1 = _cpu_times()
    dt = t1 - t0
    return 100.0 * (1.0 - (i1 - i0) / dt) if dt > 0 else 0.0


def per_cpu_times():
    """{cpu: (busy_ticks, all_ticks)} from /proc/stat.

    busy_ticks = everything but idle and iowait (user, nice, system, irq,
    softirq, steal). A process's utime + stime on this kernel includes the
    softirq work done in its context, so comparing it with user + system alone
    reads negative; comparing with all non-idle time leaves only real foreign
    work (other tasks, and interrupt work not done on Envoy's behalf).
    """
    out = {}
    with open("/proc/stat") as f:
        for line in f:
            if not line.startswith("cpu") or line.startswith("cpu "):
                continue
            parts = line.split()
            try:
                c = int(parts[0][3:])
                v = [int(x) for x in parts[1:9]]
            except ValueError:
                continue
            out[c] = (sum(v) - v[3] - v[4], sum(v))
    return out


# /proc/schedstat format versions whose cpuN line has rq_cpu_time (ns that
# tasks ran, idle task excluded) as its 7th counter (field 8 of the line).
# Version 15 (kernels 4.x to 6.x) is the one this was checked against; 16 and
# 17 changed only the domain lines.
SCHEDSTAT_VERSIONS = (15, 16, 17)


def cpu_run_ns(path="/proc/schedstat"):
    """({cpu: ns that tasks ran on it}, None) from /proc/schedstat, or (None, why).

    Precise scheduler time, unlike the tick-sampled /proc/stat: with short,
    frequent bursts (a worker waking once per request) tick sampling is biased
    in a way that depends on the workload shape. Fails closed: an unreadable
    file, an unknown format version or no cpu lines give None and a reason."""
    out = {}
    version = None
    try:
        with open(path) as f:
            for line in f:
                p = line.split()
                if not p:
                    continue
                if p[0] == "version" and len(p) > 1:
                    version = int(p[1])
                elif p[0].startswith("cpu") and len(p) > 7:
                    out[int(p[0][3:])] = int(p[7])
    except (OSError, ValueError) as ex:
        return None, "cannot read %s: %s" % (path, ex)
    if version not in SCHEDSTAT_VERSIONS:
        return None, "%s format version %s, expected one of %s" % (path, version, list(SCHEDSTAT_VERSIONS))
    if not out:
        return None, "no cpu lines in %s" % path
    return out, None


def proc_run_ns(pid):
    """ns that all threads of pid ran (sum of /proc/<pid>/task/*/schedstat)."""
    base = "/proc/%d/task" % pid
    try:
        tids = os.listdir(base)
    except OSError:
        return None
    t = 0
    for tid in tids:
        try:
            with open("%s/%s/schedstat" % (base, tid)) as f:
                t += int(f.read().split()[0])
        except (OSError, ValueError, IndexError):
            continue
    return t


def cpus_busy_ticks(before, after, cpus):
    """Sum of task ticks on cpus between two per_cpu_times snapshots."""
    return sum(after[c][0] - before[c][0] for c in cpus if c in before and c in after)


def per_cpu_busy_pct(before, after, cpus):
    out = {}
    for c in sorted(cpus):
        if c in before and c in after:
            dt = after[c][1] - before[c][1]
            out[c] = 100.0 * (after[c][0] - before[c][0]) / dt if dt > 0 else 0.0
    return out


def proc_cpu_ticks(pid):
    """utime + stime of the whole process (all threads), in ticks."""
    try:
        with open("/proc/%d/stat" % pid) as f:
            st = f.read()
        fields = st[st.rindex(")") + 2:].split()
        return int(fields[11]) + int(fields[12])
    except (OSError, ValueError, IndexError):
        return None


def proc_threads_detail(pid):
    """{tid: (comm, ticks, last_cpu, voluntary_ctxt, nonvoluntary_ctxt)} for every thread."""
    out = {}
    base = "/proc/%d/task" % pid
    try:
        tids = os.listdir(base)
    except OSError:
        return out
    for t in tids:
        try:
            with open("%s/%s/stat" % (base, t)) as f:
                st = f.read()
            comm = st[st.index("(") + 1:st.rindex(")")]
            fields = st[st.rindex(")") + 2:].split()
            vol = nvol = None
            with open("%s/%s/status" % (base, t)) as f:
                for line in f:
                    if line.startswith("voluntary_ctxt_switches:"):
                        vol = int(line.split()[1])
                    elif line.startswith("nonvoluntary_ctxt_switches:"):
                        nvol = int(line.split()[1])
            out[int(t)] = (comm, int(fields[11]) + int(fields[12]), int(fields[36]), vol, nvol)
        except (OSError, ValueError, IndexError):
            continue
    return out


def threads_summary(before, after, seconds):
    """Per-thread busy share, last CPU and context switches over a window, keyed by tid."""
    out = {}
    for tid, (comm, t1, cpu, v1, n1) in after.items():
        b = before.get(tid)
        if not b:
            continue
        out[str(tid)] = {"comm": comm, "busy": (t1 - b[1]) / CLK_TCK / seconds if seconds > 0 else 0.0,
                         "last_cpu": cpu,
                         "vol_cs": (v1 - b[3]) if v1 is not None and b[3] is not None else None,
                         "nonvol_cs": (n1 - b[4]) if n1 is not None and b[4] is not None else None}
    return out


def thread_siblings(cpu):
    txt = _read("/sys/devices/system/cpu/cpu%d/topology/thread_siblings_list" % cpu)
    return parse_cpuset(txt) if txt else {cpu}


def siblings_of(cpus):
    """SMT siblings of cpus that are not in cpus themselves."""
    out = set()
    for c in cpus:
        out |= thread_siblings(c)
    return out - set(cpus)


def online_cpus():
    txt = _read("/sys/devices/system/cpu/online")
    return parse_cpuset(txt) if txt else set(range(os.cpu_count() or 1))


def ancestors(pid=None):
    pid = pid or os.getpid()
    out = set()
    while pid and pid > 1 and pid not in out:
        out.add(pid)
        try:
            with open("/proc/%d/stat" % pid) as f:
                st = f.read()
            pid = int(st[st.rindex(")") + 2:].split()[1])
        except (OSError, ValueError):
            break
    return out


def pgrep_full(pattern):
    """PIDs whose FULL command line matches pattern (pgrep -f), minus our own tree."""
    try:
        r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    mine = ancestors()
    pids = []
    for line in r.stdout.split():
        try:
            p = int(line)
        except ValueError:
            continue
        if p not in mine:
            pids.append(p)
    return pids


def cmdline(pid):
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            return f.read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def idle_check(cfg, own_pids=(), watch_cpus=()):
    """One idle sample: (ok, detail dict). cfg is the experiment's idle section.

    watch_cpus (the SUT CPUs and their SMT siblings) must each stay under
    max_cpu_busy_pct, besides the whole-box load and busy share.
    """
    load = loadavg1()
    c0 = per_cpu_times()
    busy = system_busy_pct(cfg.get("sample_s", 1.0))
    c1 = per_cpu_times()
    per = per_cpu_busy_pct(c0, c1, watch_cpus)
    hot = {str(c): round(v, 1) for c, v in per.items() if v >= cfg.get("max_cpu_busy_pct", 5.0)}
    found = {}
    for pat in cfg.get("procs", []):
        pids = pgrep_full(pat)
        if pids is None:
            found[pat] = ["pgrep-failed"]
            continue
        pids = [p for p in pids if p not in own_pids]
        if pids:
            found[pat] = [{"pid": p, "cmd": cmdline(p)[:160]} for p in pids]
    ok = load < cfg.get("max_load1", 4.0) and busy < cfg.get("max_busy_pct", 2.0) and not found and not hot
    return ok, {"load1": load, "busy_pct": round(busy, 2), "procs": found, "hot_watched_cpus": hot}


def wait_idle(cfg, own_pids=(), log=None, watch_cpus=()):
    """Poll until idle or timeout. Returns (ok, last detail, seconds waited)."""
    t0 = time.monotonic()
    timeout = cfg.get("timeout_s", 300)
    while True:
        ok, det = idle_check(cfg, own_pids, watch_cpus)
        waited = time.monotonic() - t0
        if ok:
            return True, det, waited
        if waited >= timeout:
            return False, det, waited
        if log:
            log("not idle yet: load1=%.2f busy=%.1f%% procs=%d hot=%s" % (
                det["load1"], det["busy_pct"], len(det["procs"]), det["hot_watched_cpus"]))
        time.sleep(cfg.get("poll_s", 5))


def proc_threads_cpu(pid):
    """{tid: utime+stime ticks} for every thread of pid."""
    out = {}
    base = "/proc/%d/task" % pid
    try:
        tids = os.listdir(base)
    except OSError:
        return out
    for t in tids:
        try:
            with open("%s/%s/stat" % (base, t)) as f:
                st = f.read()
            fields = st[st.rindex(")") + 2:].split()
            out[int(t)] = int(fields[11]) + int(fields[12])
        except (OSError, ValueError, IndexError):
            continue
    return out


def threads_busy(before, after, seconds):
    """Per-thread busy fraction between two proc_threads_cpu snapshots."""
    res = {}
    for tid, t1 in after.items():
        t0 = before.get(tid, 0)
        res[tid] = (t1 - t0) / CLK_TCK / seconds if seconds > 0 else 0.0
    return res


def cpus_allowed(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            for line in f:
                if line.startswith("Cpus_allowed_list:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def parse_cpuset(spec):
    out = set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


# ---------------------------------------------------------------- metadata

def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def cpu_model():
    txt = _read("/proc/cpuinfo", "")
    m = re.search(r"^model name\s*:\s*(.+)$", txt, re.M)
    return m.group(1).strip() if m else platform.processor()


def topology():
    sockets, cores = set(), set()
    n = 0
    base = "/sys/devices/system/cpu"
    for d in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if not re.match(r"cpu\d+$", d):
            continue
        pkg = _read("%s/%s/topology/physical_package_id" % (base, d))
        core = _read("%s/%s/topology/core_id" % (base, d))
        if pkg is None:
            continue
        n += 1
        sockets.add(pkg)
        cores.add((pkg, core))
    numa = len([d for d in os.listdir("/sys/devices/system/node") if re.match(r"node\d+$", d)]) \
        if os.path.isdir("/sys/devices/system/node") else None
    return {"logical_cpus": n, "sockets": len(sockets), "physical_cores": len(cores),
            "threads_per_core": (n // len(cores)) if cores else None, "numa_nodes": numa}


def cpufreq(cpus):
    out = {}
    for c in sorted(cpus):
        b = "/sys/devices/system/cpu/cpu%d/cpufreq" % c
        out[str(c)] = {
            "governor": _read(b + "/scaling_governor"),
            "driver": _read(b + "/scaling_driver"),
            "cur_khz": _read(b + "/scaling_cur_freq"),
            "min_khz": _read(b + "/scaling_min_freq"),
            "max_khz": _read(b + "/scaling_max_freq"),
        }
    return out


def cpuidle(cpus):
    """Idle states per CPU: name, exit latency (us) and whether it is disabled."""
    out = {}
    for c in sorted(cpus):
        b = "/sys/devices/system/cpu/cpu%d/cpuidle" % c
        states = []
        if os.path.isdir(b):
            for d in sorted(os.listdir(b)):
                if d.startswith("state"):
                    states.append({"name": _read("%s/%s/name" % (b, d)),
                                   "latency_us": _read("%s/%s/latency" % (b, d)),
                                   "disable": _read("%s/%s/disable" % (b, d))})
        out[str(c)] = states
    return out


def cpuidle_disabled_vector(cpus):
    """[(cpu, state dir, name, disable)] for every idle state of every CPU in cpus."""
    out = []
    for c in sorted(cpus):
        b = "/sys/devices/system/cpu/cpu%d/cpuidle" % c
        if not os.path.isdir(b):
            out.append((c, None, None, None))
            continue
        for d in sorted(os.listdir(b)):
            if d.startswith("state"):
                out.append((c, d, _read("%s/%s/name" % (b, d)), _read("%s/%s/disable" % (b, d))))
    return out


def cpuidle_fingerprint(cpus):
    """Short hash of the driver, governor and every state's disable flag on cpus.
    Equal fingerprints mean the idle-state configuration did not change."""
    base = "/sys/devices/system/cpu/cpuidle"
    parts = [_read(base + "/current_driver") or "-", _read(base + "/current_governor") or
             _read(base + "/current_governor_ro") or "-"]
    parts += ["%s:%s:%s:%s" % x for x in cpuidle_disabled_vector(cpus)]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def cpuidle_summary(cpus):
    """Idle-state configuration of cpus in one readable record: driver, governor,
    and per state its exit latency and the CPUs it is disabled on."""
    base = "/sys/devices/system/cpu/cpuidle"
    states = {}
    for c, d, name, dis in cpuidle_disabled_vector(cpus):
        if d is None:
            continue
        st = states.setdefault(d, {"state": d, "name": name, "latency_us": _read(
            "/sys/devices/system/cpu/cpu%d/cpuidle/%s/latency" % (c, d)), "disabled_on": [], "enabled_on": []})
        (st["disabled_on"] if dis == "1" else st["enabled_on"]).append(c)
    rows = []
    for d in sorted(states, key=lambda x: int(x[5:]) if x[5:].isdigit() else 0):
        st = states[d]
        st["disabled_on"] = _cpuset_text(st["disabled_on"])
        st["enabled_on"] = _cpuset_text(st["enabled_on"])
        rows.append(st)
    disabled = [s["name"] for s in rows if s["disabled_on"] and not s["enabled_on"]]
    mixed = [s["name"] for s in rows if s["disabled_on"] and s["enabled_on"]]
    cmd = _read("/proc/cmdline", "") or ""
    idle_args = [t for t in cmd.split() if re.match(r"(intel_idle\.|processor\.max_cstate|idle=|cpuidle\.|"
                                                     r"intel_pstate=|nohz|isolcpus)", t)]
    return {"cpus": _cpuset_text(cpus), "driver": _read(base + "/current_driver"),
            "governor": _read(base + "/current_governor") or _read(base + "/current_governor_ro"),
            "intel_idle_max_cstate": _read("/sys/module/intel_idle/parameters/max_cstate"),
            "intel_idle_states_off": _read("/sys/module/intel_idle/parameters/states_off"),
            "kernel_cmdline_idle_args": idle_args,
            "states": rows, "disabled_everywhere": disabled, "disabled_somewhere": mixed,
            "text": "%s/%s; disabled: %s%s" % (
                _read(base + "/current_driver"), _read(base + "/current_governor") or
                _read(base + "/current_governor_ro"), ", ".join(disabled) or "none",
                ("; mixed: " + ", ".join(mixed)) if mixed else ""),
            "fingerprint": cpuidle_fingerprint(cpus)}


def _cpuset_text(cpus):
    """[0,1,2,5] -> "0-2,5"."""
    cs = sorted(set(cpus))
    out = []
    i = 0
    while i < len(cs):
        j = i
        while j + 1 < len(cs) and cs[j + 1] == cs[j] + 1:
            j += 1
        out.append(str(cs[i]) if i == j else "%d-%d" % (cs[i], cs[j]))
        i = j + 1
    return ",".join(out)


def os_release():
    txt = _read("/etc/os-release", "")
    m = re.search(r'^PRETTY_NAME="?([^"\n]+)"?', txt, re.M)
    return m.group(1) if m else None


def machine_metadata(cpusets, record_hostname=False):
    allc = set()
    for v in cpusets.values():
        allc |= parse_cpuset(v)
    freqs = cpufreq(allc)
    sut = parse_cpuset(cpusets.get("sut", ""))
    sut_all = sut | parse_cpuset(cpusets.get("hop2", ""))
    govs = sorted({v["governor"] for v in freqs.values() if v["governor"]})
    curs = sorted({v["cur_khz"] for v in freqs.values() if v["cur_khz"]})
    md = {
        "kernel": platform.release(),
        "os": os_release(),
        "cpu_model": cpu_model(),
        "topology": topology(),
        "governors_in_use": govs,
        "cur_khz_in_use": curs,
        "cpufreq_per_cpu": freqs,
        "no_turbo": _read("/sys/devices/system/cpu/intel_pstate/no_turbo"),
        "boost": _read("/sys/devices/system/cpu/cpufreq/boost"),
        "smt_active": _read("/sys/devices/system/cpu/smt/active"),
        "sut_smt_siblings_outside_sut": sorted(siblings_of(sut)),
        "cpuidle_driver": _read("/sys/devices/system/cpu/cpuidle/current_driver"),
        "intel_idle_max_cstate": _read("/sys/module/intel_idle/parameters/max_cstate"),
        "cpuidle_sut": cpuidle(sut),
        # The SUT CPUs (every Envoy hop) and their SMT siblings: deep idle states
        # change what a request costs when the load is spread thin, so every run
        # says which states were allowed. The harness never changes them.
        "cpuidle_sut_summary": cpuidle_summary(sut_all | siblings_of(sut_all)),
        "perf_event_paranoid": _read("/proc/sys/kernel/perf_event_paranoid"),
        "python": platform.python_version(),
        "mem_total_kb": None,
    }
    m = re.search(r"MemTotal:\s+(\d+)", _read("/proc/meminfo", "") or "")
    if m:
        md["mem_total_kb"] = int(m.group(1))
    if record_hostname:
        md["hostname"] = platform.node()
    else:
        md["host_id"] = host_id()
    return md


def host_id(salt_path="~/.config/epl/host-salt"):
    """A keyed hash of the host name. The key is a random 32-byte salt kept on the
    bench box (mode 0600, never written to a run directory), so the id groups
    runs from one machine but cannot be reversed with a word list."""
    p = os.path.expanduser(salt_path)
    try:
        with open(p, "rb") as f:
            salt = f.read()
    except OSError:
        salt = b""
    if len(salt) < 32:
        os.makedirs(os.path.dirname(p), mode=0o700, exist_ok=True)
        salt = os.urandom(32)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(salt)
    return hmac.new(salt, platform.node().encode(), hashlib.sha256).hexdigest()[:16]


# ---------------------------------------------------------------- scrubbing

def _home_patterns():
    pats = []
    home = os.path.expanduser("~")
    if home and home not in ("/", "~"):
        pats.append(re.escape(home.rstrip("/")))
    pats.append(r"/home/[A-Za-z0-9._-]+")
    pats.append(r"/Users/[A-Za-z0-9._-]+")
    pats.append(r"/root(?=/)")
    return re.compile("(" + "|".join(pats) + ")")


_HOME_RE = None


def scrub_text(text):
    """Replace home directory prefixes (/home/<user>, /Users/<user>, $HOME) with ~."""
    global _HOME_RE
    if _HOME_RE is None:
        _HOME_RE = _home_patterns()
    return _HOME_RE.sub("~", text)


def scrub(obj):
    """scrub_text applied to every string in a JSON-like structure."""
    if isinstance(obj, str):
        return scrub_text(obj)
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, tuple):
        return [scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {scrub(k) if isinstance(k, str) else k: scrub(v) for k, v in obj.items()}
    return obj


TEXT_SUFFIXES = (".json", ".jsonl", ".txt", ".log", ".md", ".csv", ".conf")


def scrub_tree(root):
    """Rewrite every text file under root with home paths replaced. Returns files changed."""
    changed = []
    for d, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(TEXT_SUFFIXES):
                continue
            p = os.path.join(d, fn)
            try:
                with open(p, encoding="utf-8", errors="surrogateescape") as f:
                    txt = f.read()
            except OSError:
                continue
            new = scrub_text(txt)
            if new != txt:
                with open(p, "w", encoding="utf-8", errors="surrogateescape") as f:
                    f.write(new)
                changed.append(os.path.relpath(p, root))
    return changed


def cpuidle_counts(cpus):
    """{cpu: {state name: (usage, time_us)}} from cpuidle sysfs (read only)."""
    out = {}
    for c in sorted(cpus):
        b = "/sys/devices/system/cpu/cpu%d/cpuidle" % c
        st = {}
        if os.path.isdir(b):
            for d in sorted(os.listdir(b)):
                if d.startswith("state"):
                    try:
                        st[_read("%s/%s/name" % (b, d)) or d] = (int(_read("%s/%s/usage" % (b, d))),
                                                                 int(_read("%s/%s/time" % (b, d))))
                    except (TypeError, ValueError):
                        pass
        out[c] = st
    return out


def cpuidle_residency(a, b, window_s):
    """Per CPU and idle state over a window: entries per second and the share of the
    window spent in the state; plus the sum over the CPUs."""
    out, tot = {}, {}
    for c in a:
        row = {}
        for name, (u0, t0) in a[c].items():
            if name not in b.get(c, {}):
                continue
            u1, t1 = b[c][name]
            row[name] = {"entries_per_s": round((u1 - u0) / window_s, 1),
                         "residency": round((t1 - t0) / 1e6 / window_s, 4)}
            x = tot.setdefault(name, {"entries_per_s": 0.0, "residency": 0.0})
            x["entries_per_s"] = round(x["entries_per_s"] + row[name]["entries_per_s"], 1)
            x["residency"] = round(x["residency"] + row[name]["residency"], 4)
        out[str(c)] = row
    return {"per_cpu": out, "sum": tot}
