#!/usr/bin/env python3
"""Idle-state follow-up to wc2.py (bench-host): does the 40-vs-2-worker penalty come from deep idle states?

Conditions, switched per round in an ABBA pattern over round pairs:
  A  "cap": on the node CPUs (0-19,40-59) every idle state with exit latency > 2 us is disabled
     (C1E, C3, C6); POLL and C1 stay enabled. Set through sudo -n cstate.sh cap.
  B  "default": the box's original idle settings (saved snapshot written back, read-back verified).
Arms per round as in wc2.py (default workers vs --concurrency 2), ABBA within round pairs.
Every pod gets an unmeasured 20 s warm-up load at 8000 rps before the measured rates.

Extra per-leg records: per-thread voluntary/involuntary context switches, utime/stime and
migrations; cgroup user/system split; per-CPU run time on every CPU; per-CPU idle-state
usage/time deltas; worker placement samples (processor field every 0.2 s); perf counters
(instructions, cycles, user and all) for the pod's container cgroup on the node CPUs.

Touches only what it creates: the pod "wc2" in the cluster of $KUBECONFIG, the Nighthawk and
perf processes it starts (own Popen handles), and the idle-state knobs of the node CPUs.

  wc3.py ab OUT ROUNDS RPS[,RPS...]
  wc3.py analyze OUT
"""
import json
import math
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wc2  # noqa: E402
from wc2 import stats, nhp  # noqa: E402

wc2.NODE_CONTAINER = "wc3-control-plane"
CSTATE = os.path.expanduser("~/wc2/cstate/scripts/cstate.sh")
ORIG = os.path.expanduser("~/wc2/cstate/idle-orig.txt")
WARM_S = 20
WARM_RPS = 8000
SAMPLE_S = 0.2
ALL_CPUS = list(range(80))
NODE_LIST = sorted(wc2.NODE_SET)


# ------------------------------------------------------------------ idle-state knobs

def read_orig():
    d = {}
    with open(ORIG) as f:
        for line in f:
            p, v = line.split()
            d[p] = v
    return d


ORIG_VALS = read_orig()


def knob(cpu, st):
    return "/sys/devices/system/cpu/cpu%d/cpuidle/state%d/disable" % (cpu, st)


def state_meta():
    out = []
    for st in range(5):
        b = "/sys/devices/system/cpu/cpu0/cpuidle/state%d/" % st
        out.append({k: open(b + k).read().strip() for k in ("name", "latency", "residency", "default_status")})
    return out


STATES = state_meta()


def expected(cond):
    exp = dict(ORIG_VALS)
    if cond == "A":
        for c in NODE_LIST:
            for st in range(5):
                exp[knob(c, st)] = "1" if int(STATES[st]["latency"]) > 2 else "0"
    return exp


def readback(cond):
    bad = []
    for p, v in expected(cond).items():
        now = open(p).read().strip()
        if now != v:
            bad.append((p, now, v))
    return bad


def set_condition(out, cond):
    if cond == "A":
        r = subprocess.run(["sudo", "-n", CSTATE, "cap"], capture_output=True, text=True, timeout=60)
    else:
        r = subprocess.run(["sudo", "-n", CSTATE, "restore", ORIG], capture_output=True, text=True, timeout=60)
    bad = readback(cond)
    wc2.log(out, "condition %s set: rc %d %s readback mismatches %d" % (cond, r.returncode, r.stdout.strip()[-80:],
                                                                       len(bad)))
    if r.returncode != 0 or bad:
        raise RuntimeError("condition %s not applied: rc %d %s %s" % (cond, r.returncode, r.stderr, bad[:3]))


def idle_counters():
    out = {}
    for c in ALL_CPUS:
        row = []
        for st in range(5):
            b = "/sys/devices/system/cpu/cpu%d/cpuidle/state%d/" % (c, st)
            with open(b + "usage") as f:
                u = int(f.read())
            with open(b + "time") as f:
                t = int(f.read())
            row.append((u, t))
        out[c] = row
    return out


# ------------------------------------------------------------------ thread readers

def thread_detail(pid):
    """{tid: dict(comm, vcs, ivcs, utime, stime, cpu, migr)} for every thread of pid."""
    out = {}
    base = "/proc/%d/task" % pid
    for t in os.listdir(base):
        try:
            d = {}
            with open("%s/%s/status" % (base, t)) as f:
                for line in f:
                    if line.startswith("Name:"):
                        d["comm"] = line.split(None, 1)[1].strip()
                    elif line.startswith("voluntary_ctxt_switches:"):
                        d["vcs"] = int(line.split()[1])
                    elif line.startswith("nonvoluntary_ctxt_switches:"):
                        d["ivcs"] = int(line.split()[1])
            with open("%s/%s/stat" % (base, t)) as f:
                s = f.read()
            fl = s[s.rindex(")") + 2:].split()
            d["utime"], d["stime"], d["cpu"] = int(fl[11]), int(fl[12]), int(fl[36])
            try:
                with open("%s/%s/sched" % (base, t)) as f:
                    for line in f:
                        if line.startswith("se.nr_migrations"):
                            d["migr"] = int(line.split(":")[1])
            except OSError:
                d["migr"] = None
            out[int(t)] = d
        except (OSError, ValueError, IndexError):
            continue
    return out


def cg_stat(pid):
    d = {}
    for line in wc2.cg_read(pid, "cpu.stat").splitlines():
        k, _, v = line.partition(" ")
        try:
            d[k] = int(v)
        except ValueError:
            pass
    return d


class Sampler(threading.Thread):
    """Samples the processor field of every wrk: thread every SAMPLE_S."""

    def __init__(self, pid, tids):
        super().__init__(daemon=True)
        self.pid, self.tids, self.stop_ev, self.samples = pid, tids, threading.Event(), []

    def run(self):
        while not self.stop_ev.is_set():
            row = {}
            for t in self.tids:
                try:
                    with open("/proc/%d/task/%d/stat" % (self.pid, t)) as f:
                        s = f.read()
                    row[t] = int(s[s.rindex(")") + 2:].split()[36])
                except (OSError, ValueError, IndexError):
                    pass
            self.samples.append(row)
            self.stop_ev.wait(SAMPLE_S)


def perf_start(pid, seconds, path):
    cg = wc2.cgroup_dir(pid)
    rel = cg[len("/sys/fs/cgroup/"):]
    ev = "instructions,cycles,instructions:u,cycles:u"
    args = ["taskset", "-c", wc2.HARNESS_CPUS, "perf", "stat", "-x", ",", "-o", path, "-a", "-C", wc2.NODE_CPUS,
            "-e", ev, "-G", ",".join([rel] * 4), "--", "sleep", str(seconds)]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def perf_parse(path):
    out = {}
    try:
        for line in open(path):
            f = line.strip().split(",")
            if len(f) < 3 or line.startswith("#"):
                continue
            try:
                # with -G: count,unit,event,cgroup,run_ns,run_pct,...
                out[f[2]] = {"count": int(f[0]), "fields": f}
            except ValueError:
                out[f[2]] = {"raw": line.strip()}
    except OSError as e:
        out["error"] = str(e)
    return out


# ------------------------------------------------------------------ snapshots

def snap(pid, ip, client_pid):
    s = wc2.snapshot(pid, ip, client_pid, conns=True)
    s["threads"] = thread_detail(pid)
    s["cgstat"] = cg_stat(pid)
    s["idle"] = idle_counters()
    return s


def extras(s0, s1, requests, n_workers):
    dt = s1["t"] - s0["t"]
    hz = wc2.HZ
    thr = {}
    for t, d1 in s1["threads"].items():
        d0 = s0["threads"].get(t)
        if not d0:
            continue
        thr[t] = {"comm": d1["comm"], "vcs": d1["vcs"] - d0["vcs"], "ivcs": d1["ivcs"] - d0["ivcs"],
                  "utime_s": (d1["utime"] - d0["utime"]) / hz, "stime_s": (d1["stime"] - d0["stime"]) / hz,
                  "migr": (d1["migr"] - d0["migr"]) if d1.get("migr") is not None and d0.get("migr") is not None
                  else None}
    wk = [v for v in thr.values() if v["comm"].startswith("wrk:")]
    req = float(requests) or 1.0
    e = {
        "threads": thr,
        "workers_vcs_per_req": sum(v["vcs"] for v in wk) / req,
        "workers_ivcs_per_req": sum(v["ivcs"] for v in wk) / req,
        "all_vcs_per_req": sum(v["vcs"] for v in thr.values()) / req,
        "all_ivcs_per_req": sum(v["ivcs"] for v in thr.values()) / req,
        "workers_migr_per_s": sum(v["migr"] or 0 for v in wk) / dt,
        "workers_utime_s": sum(v["utime_s"] for v in wk), "workers_stime_s": sum(v["stime_s"] for v in wk),
    }
    c0, c1 = s0["cgstat"], s1["cgstat"]
    e["cg_user_us_per_req"] = (c1["user_usec"] - c0["user_usec"]) / req
    e["cg_sys_us_per_req"] = (c1["system_usec"] - c0["system_usec"]) / req
    e["cg_user_share"] = (c1["user_usec"] - c0["user_usec"]) / max(1, c1["usage_usec"] - c0["usage_usec"])
    e["cpu_run"] = {c: (s1["cpu"][c] - s0["cpu"][c]) / 1e9 / dt for c in s1["cpu"]}
    idle = {}
    for c in ALL_CPUS:
        idle[c] = [[s1["idle"][c][st][0] - s0["idle"][c][st][0], s1["idle"][c][st][1] - s0["idle"][c][st][1]]
                   for st in range(5)]
    e["idle_delta"] = idle
    # residency summary over the node CPUs: share of wall time per state, entries per CPU-second
    e["node_residency"] = {STATES[st]["name"]: sum(idle[c][st][1] for c in NODE_LIST) / (dt * 1e6 * len(NODE_LIST))
                           for st in range(5)}
    e["node_entries_per_cpu_s"] = {STATES[st]["name"]: sum(idle[c][st][0] for c in NODE_LIST) / (dt * len(NODE_LIST))
                                   for st in range(5)}
    return e


def placement(samples, n_workers):
    per = {}
    for row in samples:
        for t, c in row.items():
            per.setdefault(t, {}).setdefault(c, 0)
            per[t][c] += 1
    out = {"samples": len(samples), "per_worker": {str(t): v for t, v in per.items()}}
    if n_workers == 2 and samples:
        both = [r for r in samples if len(r) == 2]
        same_core = sum(1 for r in both if len({c % 40 for c in r.values()}) == 1)
        same_cpu = sum(1 for r in both if len(set(r.values())) == 1)
        out["two_worker_same_core_frac"] = same_core / len(both) if both else None
        out["two_worker_same_cpu_frac"] = same_cpu / len(both) if both else None
        out["distinct_cpus_per_worker"] = {str(t): len(v) for t, v in per.items()}
        out["top_cpu_share_per_worker"] = {str(t): max(v.values()) / sum(v.values()) for t, v in per.items()}
        out["socket0_frac"] = sum(1 for r in samples for c in r.values() if c in wc2.NODE_SET) / max(
            1, sum(len(r) for r in samples))
    return out


# ------------------------------------------------------------------ client runs

def nh_args(ip, rps, duration):
    conc = wc2.NH_CONC
    return ["taskset", "-c", wc2.CLIENT_CPUS, wc2.NH, "--rps", str(rps // conc), "--connections", str(wc2.NH_CONNS),
            "--concurrency", str(conc), "--duration", str(duration), "--sequencer-idle-strategy", "poll",
            "--open-loop", "--prefetch-connections", "--max-pending-requests", "1000",
            "--experimental-h1-connection-reuse-strategy", "lru", "--output-format", "json",
            "http://%s:10000/" % ip]


def own_popen(args, own, **kw):
    p = subprocess.Popen(args, **kw)
    own.add(p.pid)
    return p


def stop_own(p, own):
    try:
        if p.poll() is None:
            p.terminate()  # own Popen handle only
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=20)
    finally:
        own.discard(p.pid)


def warmup(out, tag, ip, own):
    jout = os.path.join(out, tag + "-warm.nh.json")
    with open(jout, "w") as jf, open(os.path.join(out, tag + "-warm.nh.err"), "w") as ef:
        p = own_popen(nh_args(ip, WARM_RPS, WARM_S), own, stdout=jf, stderr=ef)
        try:
            p.wait(timeout=WARM_S + 60)
        finally:
            stop_own(p, own)
    try:
        nh = nhp.parse_output(jout)
        return {"exit": p.returncode, "overflow": nh["overflow"], "rate_2xx": nh["rate_2xx"],
                "p50_us": nh["latency_us"]["p50"]}
    except Exception as e:  # noqa: BLE001 - warm-up is not gated
        return {"exit": p.returncode, "parse_error": str(e)}


def run_client3(out, tag, ip, rps, pid, own, n_workers):
    jout = os.path.join(out, tag + ".nh.json")
    wtids = [t for t, d in thread_detail(pid).items() if d["comm"].startswith("wrk:")]
    with open(jout, "w") as jf, open(os.path.join(out, tag + ".nh.err"), "w") as ef:
        p = own_popen(nh_args(ip, rps, wc2.DURATION), own, stdout=jf, stderr=ef)
        perf = None
        sampler = Sampler(pid, wtids)
        try:
            time.sleep(wc2.WIN_START)
            ncpus = None
            with open("/proc/%d/status" % p.pid) as f:
                for line in f:
                    if line.startswith("Cpus_allowed_list:"):
                        ncpus = line.split(":", 1)[1].strip()
            perf_path = os.path.join(out, tag + ".perf.csv")
            perf = perf_start(pid, wc2.WIN_END - wc2.WIN_START, perf_path)
            own.add(perf.pid)
            s0 = snap(pid, ip, p.pid)
            sampler.start()
            time.sleep(wc2.WIN_END - wc2.WIN_START)
            s1 = snap(pid, ip, p.pid)
            sampler.stop_ev.set()
            sampler.join(timeout=5)
            perr = perf.communicate(timeout=30)[1]
            own.discard(perf.pid)
            p.wait(timeout=wc2.DURATION + 60)
        except BaseException:
            if perf is not None:
                stop_own(perf, own)
            stop_own(p, own)
            raise
        finally:
            own.discard(p.pid)
    w = wc2.window(s0, s1)
    w["client_cpus_allowed"] = ncpus
    w["client_exit"] = p.returncode
    w["nh"] = nhp.parse_output(jout)
    w.update(extras(s0, s1, w["requests"], n_workers))
    w["placement"] = placement(sampler.samples, n_workers)
    w["perf"] = perf_parse(perf_path)
    w["perf_rc"] = perf.returncode
    w["perf_err"] = (perr or "")[-300:]
    return w


def worker_summary(wb, n_workers):
    s = wc2.worker_summary(wb, n_workers)
    vals = sorted(wb.values(), reverse=True) + [0.0] * max(0, n_workers - len(wb))
    s["busy_median"] = round(stats.median(vals), 4)
    return s


def one_arm(out, ip, rnd, cond, arm, rates, own):
    tag = "c%02d-%s-%s" % (rnd, cond, arm)
    rec = {"round": rnd, "cond": cond, "arm": arm, "tag": tag, "started_utc": wc2.now(), "invalid": [], "loads": {}}
    bad = readback(cond)
    if bad:
        rec["invalid"].append("condition %s readback mismatch %s" % (cond, bad[:3]))
        return rec
    pid = wc2.deploy(ip, tag, wc2.ARMS[arm])
    own.add(pid)
    try:
        si = json.loads(wc2.http_get("http://%s:9901/server_info" % ip))
        st = wc2.proc_status(pid)
        tasks = wc2.task_run_ns(pid)
        rec.update(concurrency=si["command_line_options"]["concurrency"], envoy_version=si.get("version"),
                   worker_threads=sum(1 for c, _ in tasks.values() if c.startswith("wrk:")),
                   threads_total=len(tasks), cpus_allowed=st.get("Cpus_allowed_list"),
                   cgroup_cpu_max=wc2.cg_read(pid, "cpu.max"), cgroup_dir=wc2.cgroup_dir(pid))
        if wc2.parse_cpuset(rec["cpus_allowed"]) != wc2.NODE_SET:
            rec["invalid"].append("envoy not on the node CPUs (%s)" % rec["cpus_allowed"])
        time.sleep(wc2.SETTLE_S)
        rec["pre_idle"] = wc2.pre_check(own)
        if rec["pre_idle"]["foreign_procs"]:
            rec["invalid"].append("foreign envoy/nighthawk %s" % rec["pre_idle"]["foreign_procs"])
        s0 = wc2.snapshot(pid, None)
        s0["threads"], s0["cgstat"], s0["idle"] = thread_detail(pid), cg_stat(pid), idle_counters()
        time.sleep(wc2.IDLE_S)
        s1 = wc2.snapshot(pid, None)
        s1["threads"], s1["cgstat"], s1["idle"] = thread_detail(pid), cg_stat(pid), idle_counters()
        iw = wc2.window(s0, s1)
        ie = extras(s0, s1, 1, rec["concurrency"])
        iw.update({k: ie[k] for k in ("node_residency", "node_entries_per_cpu_s", "cpu_run", "idle_delta")})
        iw["workers_vcs_per_s"] = sum(v["vcs"] for v in ie["threads"].values()
                                      if v["comm"].startswith("wrk:")) / iw["window_s"]
        iw["rss_kb"] = int(wc2.proc_status(pid)["VmRSS"].split()[0])
        iw["workers"] = worker_summary(iw["worker_busy"], rec["concurrency"])
        iw["invalid"] = wc2.verdict_box(iw)
        rec["idle"] = iw
        rec["warmup"] = warmup(out, tag, ip, own)
        for rps in rates:
            time.sleep(wc2.PAUSE_S)
            pc = wc2.pre_check(own)
            lw = run_client3(out, "%s-%d" % (tag, rps), ip, rps, pid, own, rec["concurrency"])
            lw["pre_idle"] = pc
            lw["cpu_us_per_req"] = lw["envoy_cpus_cgroup"] / lw["rps"] * 1e6 if lw["rps"] else None
            lw["cpu_us_per_req_sched"] = lw["envoy_cpus_sched"] / lw["rps"] * 1e6 if lw["rps"] else None
            lw["workers"] = worker_summary(lw["worker_busy"], rec["concurrency"])
            lw["p50_us"] = lw["nh"]["latency_us"]["p50"]
            lw["p99_us"] = lw["nh"]["latency_us"]["p99"]
            lw["cond_readback_mismatch"] = len(readback(cond))
            lw["invalid"] = wc2.verdict_load(lw, rps) + (
                ["foreign envoy/nighthawk %s" % pc["foreign_procs"]] if pc["foreign_procs"] else []) + (
                ["condition readback mismatch"] if lw["cond_readback_mismatch"] else [])
            rec["loads"][str(rps)] = lw
            pf = lw["perf"]
            ipc = (pf.get("instructions", {}).get("count", 0) / pf["cycles"]["count"]) if pf.get("cycles", {}).get(
                "count") else float("nan")
            wc2.log(out, "  %s %d rps: %.2f us/req (u %.1f s %.1f) p50 %.0f vcs/req %.3f ivcs/req %.3f "
                         "C1 %.2f C6 %.2f POLL %.3f ipc %.3f ins/req %.0f busy max/med %.3f/%.3f invalid=%s" % (
                             tag, rps, lw["cpu_us_per_req"], lw["cg_user_us_per_req"], lw["cg_sys_us_per_req"],
                             lw["p50_us"], lw["workers_vcs_per_req"], lw["workers_ivcs_per_req"],
                             lw["node_residency"]["C1"], lw["node_residency"]["C6"], lw["node_residency"]["POLL"],
                             ipc, pf.get("instructions", {}).get("count", 0) / max(1, lw["requests"]),
                             lw["workers"]["busy_max"], lw["workers"]["busy_median"], lw["invalid"]))
        rec["rss_kb_after_load"] = int(wc2.proc_status(pid)["VmRSS"].split()[0])
    finally:
        own.discard(pid)
        wc2.delete_pod()
    wc2.log(out, "  %s idle %.4f CPUs rss %d kB workers=%s warm=%s invalid=%s %s" % (
        tag, rec["idle"]["envoy_cpus_cgroup"], rec["idle"]["rss_kb"], rec["concurrency"], rec.get("warmup"),
        rec["invalid"], rec["idle"]["invalid"]))
    return rec


def round_cond(rnd):
    """Round pair p: (A, B) for even p, (B, A) for odd p."""
    p = (rnd - 1) // 2
    first = ["A", "B"] if p % 2 == 0 else ["B", "A"]
    return first[(rnd - 1) % 2]


def box_meta():
    def rd(p):
        try:
            return open(p).read().strip()
        except OSError as e:
            return "ERR %s" % e
    cfg = {}
    try:
        for line in open("/boot/config-" + os.uname().release):
            if line.startswith(("CONFIG_IRQ_TIME_ACCOUNTING", "# CONFIG_IRQ_TIME_ACCOUNTING", "CONFIG_NO_HZ",
                                "# CONFIG_NO_HZ", "CONFIG_HZ=")):
                cfg[line.strip()] = True
    except OSError:
        pass
    vul = {}
    vd = "/sys/devices/system/cpu/vulnerabilities"
    for f in sorted(os.listdir(vd)):
        vul[f] = rd(os.path.join(vd, f))
    unc = {}
    for pk in ("package_00_die_00", "package_01_die_00"):
        b = "/sys/devices/system/cpu/intel_uncore_frequency/%s/" % pk
        unc[pk] = {k: rd(b + k) for k in ("min_freq_khz", "max_freq_khz", "initial_min_freq_khz",
                                          "initial_max_freq_khz")}
    return {"kernel": os.uname().release, "cmdline": rd("/proc/cmdline"),
            "idle_driver": rd("/sys/devices/system/cpu/cpuidle/current_driver"),
            "idle_governor": rd("/sys/devices/system/cpu/cpuidle/current_governor"),
            "intel_idle_max_cstate": rd("/sys/module/intel_idle/parameters/max_cstate"),
            "states": STATES, "orig_disabled_count": sum(1 for v in ORIG_VALS.values() if v == "1"),
            "governor": rd("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
            "scaling_min_max_khz": [rd("/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq"),
                                    rd("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")],
            "no_turbo": rd("/sys/devices/system/cpu/intel_pstate/no_turbo"),
            "kconfig": sorted(cfg), "vulnerabilities": vul, "uncore": unc,
            "package_cstate_limit": "not read (MSR access needs root beyond the idle knobs)",
            "perf_event_paranoid": rd("/proc/sys/kernel/perf_event_paranoid")}


def cmd_ab(out, rounds, rates, max_attempts=3):
    os.makedirs(out, exist_ok=True)
    os.sched_setaffinity(0, wc2.parse_cpuset(wc2.HARNESS_CPUS))
    ip = wc2.node_ip()
    wc2.ensure_configmap()
    own = set()
    path = os.path.join(out, "cs-records.json")
    recs = json.load(open(path))["records"] if os.path.exists(path) else []
    meta = {"image": wc2.IMAGE, "node_cpus": wc2.NODE_CPUS, "client_cpus": wc2.CLIENT_CPUS,
            "harness_cpus": wc2.HARNESS_CPUS, "nh_conc": wc2.NH_CONC, "nh_conns_per_worker": wc2.NH_CONNS,
            "duration_s": wc2.DURATION, "window": [wc2.WIN_START, wc2.WIN_END], "settle_s": wc2.SETTLE_S,
            "idle_s": wc2.IDLE_S, "warm_s": WARM_S, "warm_rps": WARM_RPS, "rates": rates, "gates": wc2.GATES,
            "seed": wc2.SEED, "started_utc": wc2.now(), "box": box_meta()}
    write_json = wc2.write_json
    done = {(r["round"], r["arm"]) for r in recs if r.get("ok")}
    for rnd in range(1, rounds + 1):
        cond = round_cond(rnd)
        rr = wc2.rate_order(rnd, rates)
        arms = [a for a in wc2.round_order(rnd) if (rnd, a) not in done]
        if not arms:
            continue
        set_condition(out, cond)
        time.sleep(5)
        for arm in arms:
            for attempt in range(1, max_attempts + 1):
                wc2.log(out, "round %d cond %s arm %s attempt %d rates %s" % (rnd, cond, arm, attempt, rr))
                try:
                    rec = one_arm(out, ip, rnd, cond, arm, rr, own)
                except Exception as e:  # noqa: BLE001 - recorded as an invalid attempt
                    rec = {"round": rnd, "cond": cond, "arm": arm, "invalid": ["error %s: %s" % (type(e).__name__, e)],
                           "loads": {}}
                    wc2.log(out, "  error %s" % e)
                rec["attempt"] = attempt
                rec["rate_order"] = rr
                rec["ok"] = not rec["invalid"] and not rec.get("idle", {}).get("invalid") and \
                    all(not lw["invalid"] for lw in rec["loads"].values()) and len(rec["loads"]) == len(rates)
                recs.append(rec)
                write_json(path, {"meta": meta, "records": recs})
                if rec["ok"]:
                    break
                time.sleep(30)
    set_condition(out, "B")
    analyze(out)


# ------------------------------------------------------------------ analysis

def ratio(ref, arm):
    r = stats.paired_log_ratio(ref, arm)
    return {k: r.get(k) for k in ("n", "effect_pct", "lo_pct", "hi_pct", "log_sd_pct", "t_p")}


def leg_metrics(lw):
    pf = lw.get("perf", {})
    ins, cyc = pf.get("instructions", {}).get("count"), pf.get("cycles", {}).get("count")
    insu, cycu = pf.get("instructions:u", {}).get("count"), pf.get("cycles:u", {}).get("count")
    rq = lw["requests"]
    m = {"cpu_us_per_req": lw["cpu_us_per_req"], "p50_us": lw["p50_us"],
         "user_us_per_req": lw["cg_user_us_per_req"], "sys_us_per_req": lw["cg_sys_us_per_req"],
         "vcs_per_req": lw["workers_vcs_per_req"], "ivcs_per_req": lw["workers_ivcs_per_req"],
         "migr_per_s": lw["workers_migr_per_s"],
         "ins_per_req": ins / rq if ins else None, "cyc_per_req": cyc / rq if cyc else None,
         "ipc": ins / cyc if ins and cyc else None, "ins_u_per_req": insu / rq if insu else None,
         "ipc_u": insu / cycu if insu and cycu else None,
         "ins_k_per_req": (ins - insu) / rq if ins and insu else None,
         "ipc_k": (ins - insu) / (cyc - cycu) if ins and insu and cyc and cycu and cyc > cycu else None,
         "busy_max": lw["workers"]["busy_max"], "busy_median": lw["workers"]["busy_median"]}
    for k, v in lw["node_residency"].items():
        m["res_" + k] = v
    for k, v in lw["node_entries_per_cpu_s"].items():
        m["entries_" + k] = v
    return m


def diff_ci(xs):
    return wc2.diff_ci(xs)


def analyze(out):
    d = json.load(open(os.path.join(out, "cs-records.json")))
    recs = [r for r in d["records"] if r.get("ok")]
    by = {(r["round"], r["arm"]): r for r in recs}
    rates = d["meta"]["rates"]
    res = {"attempts": len(d["records"]), "valid": len(recs),
           "invalid_attempts": [(r["round"], r.get("cond"), r["arm"], r.get("attempt"), r["invalid"],
                                 {k: v["invalid"] for k, v in r.get("loads", {}).items()})
                                for r in d["records"] if not r.get("ok")]}
    rounds = sorted({r for r, a in by if (r, "default") in by and (r, "req") in by})
    res["pairs"] = {c: [r for r in rounds if by[(r, "default")]["cond"] == c] for c in ("A", "B")}
    res["cells"] = {}
    res["arm_vs_arm"] = {}
    res["cond_effect"] = {}
    res["interaction"] = {}
    res["idle"] = {}
    for c in ("A", "B"):
        rr = res["pairs"][c]
        D = [by[(r, "default")] for r in rr]
        R = [by[(r, "req")] for r in rr]
        res["idle"][c] = {
            "default_cpus": stats.mean([x["idle"]["envoy_cpus_cgroup"] for x in D]),
            "req_cpus": stats.mean([x["idle"]["envoy_cpus_cgroup"] for x in R]),
            "diff_cpus": diff_ci([a["idle"]["envoy_cpus_cgroup"] - b["idle"]["envoy_cpus_cgroup"] for a, b in zip(D, R)]),
            "node_residency_default": {k: stats.mean([x["idle"]["node_residency"][k] for x in D])
                                       for k in D[0]["idle"]["node_residency"]},
            "node_residency_req": {k: stats.mean([x["idle"]["node_residency"][k] for x in R])
                                   for k in R[0]["idle"]["node_residency"]},
        }
    for rps in rates:
        k = str(rps)
        res["cells"][k], res["arm_vs_arm"][k] = {}, {}
        for c in ("A", "B"):
            rr = res["pairs"][c]
            M = {arm: [leg_metrics(by[(r, arm)]["loads"][k]) for r in rr] for arm in ("default", "req")}
            res["cells"][k][c] = {arm: {m: {"mean": stats.mean([x[m] for x in M[arm] if x[m] is not None]),
                                            "min": min(x[m] for x in M[arm] if x[m] is not None),
                                            "max": max(x[m] for x in M[arm] if x[m] is not None)}
                                        for m in M[arm][0] if M[arm][0][m] is not None}
                                  for arm in M}
            res["arm_vs_arm"][k][c] = {m: dict(ratio([x[m] for x in M["req"]], [x[m] for x in M["default"]]),
                                               won_by_req=sum(1 for a, b in zip(M["default"], M["req"])
                                                              if b[m] < a[m]))
                                       for m in ("cpu_us_per_req", "p50_us", "user_us_per_req", "sys_us_per_req",
                                                 "ins_per_req", "cyc_per_req", "ipc", "ins_u_per_req", "ipc_u",
                                                 "ins_k_per_req", "ipc_k")
                                       if M["default"][0][m] is not None}
            # extra CPU per request beyond the same round's idle gap
            gap = [by[(r, "default")]["loads"][k]["envoy_cpus_cgroup"] - by[(r, "req")]["loads"][k]["envoy_cpus_cgroup"]
                   - (by[(r, "default")]["idle"]["envoy_cpus_cgroup"] - by[(r, "req")]["idle"]["envoy_cpus_cgroup"])
                   for r in rr]
            res["arm_vs_arm"][k][c]["per_req_extra_us_beyond_idle"] = diff_ci([g / rps * 1e6 for g in gap])
        # condition effect per arm, pairing the A and B round of each round pair
        pairs = sorted({(r - 1) // 2 for r in rounds})
        ab = []
        for p in pairs:
            ra = [r for r in (2 * p + 1, 2 * p + 2) if r in res["pairs"]["A"]]
            rb = [r for r in (2 * p + 1, 2 * p + 2) if r in res["pairs"]["B"]]
            if ra and rb:
                ab.append((ra[0], rb[0]))
        res["cond_effect"][k] = {"round_pairs": ab}
        for arm in ("default", "req"):
            res["cond_effect"][k][arm] = {
                m: ratio([leg_metrics(by[(rb, arm)]["loads"][k])[m] for _, rb in ab],
                         [leg_metrics(by[(ra, arm)]["loads"][k])[m] for ra, _ in ab])
                for m in ("cpu_us_per_req", "p50_us", "ins_per_req", "cyc_per_req", "ipc", "user_us_per_req",
                          "sys_us_per_req")}
        # interaction: (default/req under A) vs (default/req under B), per round pair
        inter = []
        for ra, rb in ab:
            la = math.log(by[(ra, "default")]["loads"][k]["cpu_us_per_req"] / by[(ra, "req")]["loads"][k]["cpu_us_per_req"])
            lb = math.log(by[(rb, "default")]["loads"][k]["cpu_us_per_req"] / by[(rb, "req")]["loads"][k]["cpu_us_per_req"])
            inter.append(100 * (la - lb))
        res["interaction"][k] = {"log_pct_A_minus_B": diff_ci(inter), "per_pair": inter}
        # placement of the 2-worker pod
        pl = []
        for r in rounds:
            lw = by[(r, "req")]["loads"][k]
            p_ = lw["placement"]
            node = {c: v for c, v in lw["cpu_run"].items() if int(c) in wc2.NODE_SET}
            top = sorted(node.items(), key=lambda kv: -kv[1])[:4]
            pl.append({"round": r, "cond": by[(r, "req")]["cond"], "same_core_frac": p_.get("two_worker_same_core_frac"),
                       "same_cpu_frac": p_.get("two_worker_same_cpu_frac"),
                       "distinct_cpus": p_.get("distinct_cpus_per_worker"),
                       "top_cpu_share": p_.get("top_cpu_share_per_worker"),
                       "migr_per_s": lw["workers_migr_per_s"], "top_node_cpus": top})
        res.setdefault("placement_req", {})[k] = pl
    wc2.write_json(os.path.join(out, "cs-summary.json"), res)
    brief = {}
    for k in res["arm_vs_arm"]:
        for c in ("A", "B"):
            a = res["arm_vs_arm"][k][c]
            brief["%s-%s" % (k, c)] = {m: [round(a[m][x], 2) for x in ("effect_pct", "lo_pct", "hi_pct")]
                                       for m in ("cpu_us_per_req", "p50_us") if m in a}
        brief[k + "-interaction"] = {x: round(res["interaction"][k]["log_pct_A_minus_B"].get(x, 0), 2)
                                     for x in ("mean", "lo", "hi")}
    print(json.dumps(brief, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "ab":
        cmd_ab(sys.argv[2], int(sys.argv[3]), [int(x) for x in sys.argv[4].split(",")])
    elif cmd == "analyze":
        analyze(sys.argv[2])
    elif cmd == "smoke":
        out = sys.argv[2]
        os.makedirs(out, exist_ok=True)
        os.sched_setaffinity(0, wc2.parse_cpuset(wc2.HARNESS_CPUS))
        set_condition(out, "A")
        print("A readback", len(readback("A")), "B-mismatch-while-A", len(readback("B")), flush=True)
        wc2.DURATION, wc2.WIN_START, wc2.WIN_END, wc2.SETTLE_S, wc2.IDLE_S, WARM_S = 25, 8, 20, 5, 8, 8
        ip = wc2.node_ip()
        wc2.ensure_configmap()
        rec = one_arm(out, ip, 0, "A", "req", [8000], set())
        set_condition(out, "B")
        wc2.write_json(out + "/smoke.json", rec)
        lw = rec["loads"]["8000"]
        print(json.dumps({k: lw[k] for k in ("cpu_us_per_req", "cg_user_us_per_req", "cg_sys_us_per_req",
                                             "workers_vcs_per_req", "workers_ivcs_per_req", "workers_migr_per_s",
                                             "node_residency", "perf", "perf_rc", "perf_err", "invalid")},
                         default=str))
        print(json.dumps({k: v for k, v in lw["placement"].items() if k != "per_worker"}))
        print(rec["warmup"], rec["idle"]["node_residency"])
