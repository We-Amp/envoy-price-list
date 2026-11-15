#!/usr/bin/env python3
"""Envoy worker count in a pod, bare metal (bench-host): default workers vs --concurrency 2.

One kind node pinned to a fixed CPU set; Nighthawk on disjoint CPUs with LRU
connection reuse and prefetched connections, so traffic spreads over every
connection and every Envoy worker that holds one.

Per round and arm: deploy the pod, settle, measure idle CPU and RSS, then run
every rate once (rate order alternates per round pair, same order for both
arms of a round), then RSS after load. ABBA over rounds with a seeded coin per
round pair. Every leg gets a validity verdict.

Touches only what it creates: the pod "wc2" in the cluster of $KUBECONFIG and
the Nighthawk processes it starts (own Popen handles).

  wc2.py calib OUT ARM RPS[,RPS...]      one deploy, short runs, per-worker busy
  wc2.py ab OUT ROUNDS RPS[,RPS...]      the A/B
  wc2.py analyze OUT
"""
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "harness"))
from epl import nighthawk as nhp  # noqa: E402
from epl import stats  # noqa: E402

IMAGE = "envoyproxy/envoy:v1.40.2"
KUBECTL = os.path.expanduser("~/bin/kubectl-wc")
NH = os.path.expanduser("~/nighthawk/bazel-bin/nighthawk_client")
NODE_CONTAINER = "wc2-control-plane"
NODE_CPUS = "0-19,40-59"
CLIENT_CPUS = "20-39"
HARNESS_CPUS = "76-79"
NH_CONC = 16
NH_CONNS = int(os.environ.get("WC2_CONNS", "32"))
DURATION = 60
WIN_START, WIN_END = 15, 55
SETTLE_S = 20
IDLE_S = 30
PAUSE_S = 10
HZ = os.sysconf("SC_CLK_TCK")
SEED = 20261114

GATES = {
    "rate_tolerance": 0.01,
    "min_client_headroom": 0.25,
    "max_client_cpus_other": 0.10,   # other tasks on the client CPUs during the window, CPUs
    "max_node_other_cpus": 0.60,     # node CPUs minus Envoy (control plane, kubelet, ...), CPUs
    "max_rest_cpus": 0.50,           # every other CPU of the box (harness, dockerd, ...), CPUs
}


def parse_cpuset(spec):
    out = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


NODE_SET, CLIENT_SET = parse_cpuset(NODE_CPUS), parse_cpuset(CLIENT_CPUS)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log(out, msg):
    line = now() + " " + msg
    print(line, flush=True)
    with open(os.path.join(out, "log.txt"), "a") as f:
        f.write(line + "\n")


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def sh(args, timeout=120, check=True, inp=None):
    r = subprocess.run(args, input=inp, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError("%s failed: %s %s" % (args[:3], r.stdout[-500:], r.stderr[-500:]))
    return r.stdout


def http_get(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode()


def node_ip():
    return sh(["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
               NODE_CONTAINER]).strip()


# ------------------------------------------------------------------ /proc readers

def cpu_run_ns():
    """{cpu: ns tasks ran} from /proc/schedstat; fails closed on an unknown version."""
    out, ver = {}, None
    with open("/proc/schedstat") as f:
        for line in f:
            p = line.split()
            if p and p[0] == "version":
                ver = int(p[1])
            elif p and p[0].startswith("cpu") and len(p) > 7:
                out[int(p[0][3:])] = int(p[7])
    if ver != 15:
        raise RuntimeError("/proc/schedstat version %s, expected 15" % ver)
    return out


def task_run_ns(pid):
    """{tid: (comm, run ns)} for every thread of pid."""
    out = {}
    base = "/proc/%d/task" % pid
    for t in os.listdir(base):
        try:
            with open("%s/%s/schedstat" % (base, t)) as f:
                ns = int(f.read().split()[0])
            with open("%s/%s/comm" % (base, t)) as f:
                comm = f.read().strip()
            out[int(t)] = (comm, ns)
        except (OSError, ValueError, IndexError):
            continue
    return out


def proc_status(pid):
    d = {}
    with open("/proc/%d/status" % pid) as f:
        for line in f:
            k, _, v = line.partition(":")
            d[k] = v.strip()
    return d


def cgroup_dir(pid):
    with open("/proc/%d/cgroup" % pid) as f:
        for line in f:
            if line.startswith("0::"):
                return "/sys/fs/cgroup" + line.strip()[3:]
    return None


def cg_read(pid, name):
    try:
        with open(os.path.join(cgroup_dir(pid), name)) as f:
            return f.read().strip()
    except OSError as e:
        return "ERR %s" % e


def cg_usage_ns(pid):
    for line in cg_read(pid, "cpu.stat").splitlines():
        if line.startswith("usage_usec"):
            return int(line.split()[1]) * 1000
    return None


def pgrep(pattern):
    out = sh(["pgrep", "-f", pattern], check=False).split()
    return [int(p) for p in out if p.strip() and int(p) != os.getpid()]


def comm(pid):
    try:
        with open("/proc/%d/comm" % pid) as f:
            return f.read().strip()
    except OSError:
        return None


def foreign_procs(own):
    """Envoy or Nighthawk processes on the box that this script did not start."""
    bad = []
    for pat, name in ((r"(^|/)envoy( |$)", "envoy"), (r"(^|/)nighthawk_client( |$)", "nighthawk_client")):
        for p in pgrep(pat):
            if p in own or comm(p) != name:
                continue
            bad.append((p, name))
    return bad


SEGS_RE = re.compile(r"\bsegs_in:(\d+)")


def client_conns(ip):
    """{local port: segs_in} for the client's established connections to the listener."""
    r = subprocess.run(["ss", "-tinH", "state", "established", "( dport = :10000 and dst %s )" % ip],
                       capture_output=True, text=True, timeout=10)
    out, cur = {}, None
    for line in r.stdout.splitlines():
        if not line.startswith(("\t", " ")):
            f = line.split()
            # state filter drops the State column: Recv-Q Send-Q Local Peer
            try:
                cur = int(f[2].rsplit(":", 1)[1])
            except (IndexError, ValueError):
                cur = None
            m = SEGS_RE.search(line)
            if cur is not None and m:
                out[cur] = int(m.group(1))
                cur = None
            continue
        m = SEGS_RE.search(line)
        if cur is not None and m:
            out[cur] = int(m.group(1))
            cur = None
    return out


def admin_stats(ip, filt):
    txt = http_get("http://%s:9901/stats?filter=%s" % (ip, filt))
    out = {}
    for line in txt.splitlines():
        k, _, v = line.partition(": ")
        try:
            out[k.strip()] = int(v)
        except ValueError:
            pass
    return out


def admin_2xx(ip):
    v = admin_stats(ip, "^http.ingress.downstream_rq_2xx$").get("http.ingress.downstream_rq_2xx")
    if v is None:
        raise RuntimeError("no 2xx counter")
    return v


def worker_cx(ip):
    st = admin_stats(ip, r"^listener\.0\.0\.0\.0_10000\.worker_[0-9]+\.downstream_cx_active$")
    return {int(re.search(r"worker_(\d+)", k).group(1)): v for k, v in st.items()}


# ------------------------------------------------------------------ pod

def pod_manifest(tag, extra_args):
    return {
        "apiVersion": "v1", "kind": "Pod",
        "metadata": {"name": "wc2", "labels": {"app": "wc2"}},
        "spec": {
            "terminationGracePeriodSeconds": 2,
            "containers": [{
                "name": "envoy", "image": IMAGE, "imagePullPolicy": "IfNotPresent",
                "command": ["envoy"],
                "args": ["-c", "/etc/wc/envoy-wc.yaml", "--service-node", "wc2-" + tag,
                         "--service-cluster", "wc2", "-l", "warn"] + extra_args,
                "ports": [{"containerPort": 10000, "hostPort": 10000},
                          {"containerPort": 9901, "hostPort": 9901}],
                # request 2 CPUs, no CPU limit (Burstable)
                "resources": {"requests": {"cpu": "2", "memory": "256Mi"}},
                "volumeMounts": [{"name": "cfg", "mountPath": "/etc/wc"}],
            }],
            "volumes": [{"name": "cfg", "configMap": {"name": "wc-envoy"}}],
        },
    }


def ensure_configmap():
    y = sh([KUBECTL, "create", "configmap", "wc-envoy", "--from-file=" + os.path.join(HERE, "envoy-wc.yaml"),
            "--dry-run=client", "-o", "json"])
    sh([KUBECTL, "apply", "-f", "-"], inp=y)


def delete_pod():
    sh([KUBECTL, "delete", "pod", "wc2", "--ignore-not-found", "--wait=true", "--timeout=90s"],
       timeout=120, check=False)


def deploy(ip, tag, extra_args):
    delete_pod()
    sh([KUBECTL, "apply", "-f", "-"], inp=json.dumps(pod_manifest(tag, extra_args)))
    sh([KUBECTL, "wait", "--for=condition=Ready", "pod/wc2", "--timeout=120s"], timeout=150)
    for _ in range(60):
        try:
            if http_get("http://%s:9901/ready" % ip).strip() == "LIVE":
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    else:
        raise RuntimeError("envoy admin not ready")
    pids = [p for p in pgrep("service-node wc2-%s " % tag) if comm(p) == "envoy"]
    if len(pids) != 1:
        raise RuntimeError("expected one envoy pid for %s, got %s" % (tag, pids))
    return pids[0]


ARMS = {"default": [], "req": ["--concurrency", "2"]}


# ------------------------------------------------------------------ measurement

def snapshot(pid, ip, client_pid=None, conns=False):
    s = {"t": time.monotonic(), "cpu": cpu_run_ns(), "envoy_tasks": task_run_ns(pid),
         "cg": cg_usage_ns(pid)}
    if ip is not None:
        s["rq2xx"] = admin_2xx(ip)
    if client_pid is not None:
        s["nh_tasks"] = task_run_ns(client_pid)
    if conns:
        s["conns"] = client_conns(ip)
        s["worker_cx"] = worker_cx(ip)
    return s


def window(s0, s1):
    dt = s1["t"] - s0["t"]
    cpu = {c: (s1["cpu"][c] - s0["cpu"][c]) / 1e9 / dt for c in s1["cpu"] if c in s0["cpu"]}
    env = sum(ns - s0["envoy_tasks"].get(t, ("", 0))[1] for t, (_, ns) in s1["envoy_tasks"].items()) / 1e9 / dt
    node = sum(v for c, v in cpu.items() if c in NODE_SET)
    client = sum(v for c, v in cpu.items() if c in CLIENT_SET)
    rest = sum(v for c, v in cpu.items() if c not in NODE_SET and c not in CLIENT_SET)
    w = {"window_s": round(dt, 3), "envoy_cpus_sched": env,
         "envoy_cpus_cgroup": (s1["cg"] - s0["cg"]) / 1e9 / dt if s0["cg"] is not None else None,
         "node_cpus_run": node, "node_other_cpus": node - env, "client_cpus_run": client,
         "rest_cpus": rest}
    workers = {}
    for t, (cm, ns) in s1["envoy_tasks"].items():
        if cm.startswith("wrk:"):
            workers[cm] = (ns - s0["envoy_tasks"].get(t, ("", ns))[1]) / 1e9 / dt
    w["worker_busy"] = workers
    if "nh_tasks" in s1:
        nh = {t: (ns - s0["nh_tasks"].get(t, ("", 0))[1]) / 1e9 / dt for t, (cm, ns) in s1["nh_tasks"].items()}
        w["nh_cpus"] = sum(nh.values())
        w["nh_thread_busy_max"] = max(nh.values()) if nh else None
        w["client_cpus_other"] = client - w["nh_cpus"]
    if "rq2xx" in s1:
        w["requests"] = s1["rq2xx"] - s0["rq2xx"]
        w["rps"] = w["requests"] / dt
    if "conns" in s1:
        d = sorted((s1["conns"][p] - s0["conns"].get(p, 0) for p in s1["conns"]), reverse=True)
        tot = float(sum(d)) or 1.0
        w["client_conns"] = len(d)
        w["hot_conns"] = sum(1 for x in d if x > 0)
        w["hot_conns_over_10pct_of_mean"] = sum(1 for x in d if x > 0.1 * tot / max(1, len(d)))
        w["top16_conn_share"] = round(sum(d[:16]) / tot, 4)
        w["worker_cx_active"] = s1["worker_cx"]
    return w


def worker_summary(wb, n_workers):
    vals = sorted(wb.values(), reverse=True) + [0.0] * max(0, n_workers - len(wb))
    tot = sum(vals) or 1.0
    return {"workers": n_workers, "threads_found": len(wb), "max_share": round(vals[0] / tot, 4),
            "min_share": round(vals[-1] / tot, 4), "busy_max": round(vals[0], 4),
            "busy_median": round(vals[len(vals) // 2], 4), "busy_min": round(vals[-1], 4)}


def run_client(out, tag, ip, rps, duration, pid, own):
    conc = NH_CONC
    if rps % conc:
        raise ValueError("rps %d not divisible by %d" % (rps, conc))
    args = ["taskset", "-c", CLIENT_CPUS, NH, "--rps", str(rps // conc), "--connections", str(NH_CONNS),
            "--concurrency", str(conc), "--duration", str(duration), "--sequencer-idle-strategy", "poll",
            "--open-loop", "--prefetch-connections", "--max-pending-requests", "1000",
            "--experimental-h1-connection-reuse-strategy", "lru", "--output-format", "json",
            "http://%s:10000/" % ip]
    jout = os.path.join(out, tag + ".nh.json")
    with open(jout, "w") as jf, open(os.path.join(out, tag + ".nh.err"), "w") as ef:
        p = subprocess.Popen(args, stdout=jf, stderr=ef)
        own.add(p.pid)
        try:
            time.sleep(WIN_START)
            ncpus = None
            with open("/proc/%d/status" % p.pid) as f:
                for line in f:
                    if line.startswith("Cpus_allowed_list:"):
                        ncpus = line.split(":", 1)[1].strip()
            s0 = snapshot(pid, ip, p.pid, conns=True)
            time.sleep(WIN_END - WIN_START)
            s1 = snapshot(pid, ip, p.pid, conns=True)
            p.wait(timeout=duration + 60)
        except BaseException:
            if p.poll() is None:
                p.terminate()  # own Popen handle only
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=20)
            raise
        finally:
            own.discard(p.pid)
    w = window(s0, s1)
    w["client_cpus_allowed"] = ncpus
    w["client_exit"] = p.returncode
    w["nh"] = nhp.parse_output(jout)
    return w


def verdict_load(leg, rps):
    bad = []
    w = leg
    nh = w["nh"]
    if w.get("client_exit") != 0:
        bad.append("client exit %s" % w.get("client_exit"))
    if abs(nh["rate_2xx"] / rps - 1) > GATES["rate_tolerance"]:
        bad.append("client rate %.1f off target %d" % (nh["rate_2xx"], rps))
    if abs(w["rps"] / rps - 1) > GATES["rate_tolerance"]:
        bad.append("envoy window rate %.1f off target %d" % (w["rps"], rps))
    if nh["overflow"]:
        bad.append("overflow %s" % nh["overflow"])
    if nh["non2xx"]:
        bad.append("non2xx %s" % nh["non2xx"])
    if nh.get("pending_total") is not None and nh.get("workers") and nh["pending_total"] > nh["workers"]:
        bad.append("client pending total %d above %d" % (nh["pending_total"], nh["workers"]))
    if w["nh_thread_busy_max"] is None or 1 - w["nh_thread_busy_max"] < GATES["min_client_headroom"]:
        bad.append("client headroom under %.0f%%" % (GATES["min_client_headroom"] * 100))
    if w["client_cpus_allowed"] != CLIENT_CPUS:
        bad.append("client not on %s (%s)" % (CLIENT_CPUS, w["client_cpus_allowed"]))
    if w["client_cpus_other"] > GATES["max_client_cpus_other"] or w["client_cpus_other"] < -0.01:
        bad.append("client CPUs: other tasks %.3f CPUs" % w["client_cpus_other"])
    bad += verdict_box(w)
    return bad


def verdict_box(w):
    bad = []
    if w["node_other_cpus"] > GATES["max_node_other_cpus"] or w["node_other_cpus"] < -0.01:
        bad.append("node CPUs: other tasks %.3f CPUs" % w["node_other_cpus"])
    if w["rest_cpus"] > GATES["max_rest_cpus"]:
        bad.append("rest of the box %.3f CPUs" % w["rest_cpus"])
    return bad


def pre_check(own):
    f = foreign_procs(own)
    c0 = cpu_run_ns()
    t0 = time.monotonic()
    time.sleep(3)
    c1 = cpu_run_ns()
    dt = time.monotonic() - t0
    busy = sum(c1[c] - c0[c] for c in c1) / 1e9 / dt
    return {"foreign_procs": f, "box_busy_cpus": round(busy, 3)}


def one_arm(out, ip, rnd, arm, rates, own, idle_s=IDLE_S):
    tag = "r%02d-%s" % (rnd, arm)
    rec = {"round": rnd, "arm": arm, "tag": tag, "started_utc": now(), "invalid": [], "loads": {}}
    pid = deploy(ip, tag, ARMS[arm])
    own.add(pid)
    try:
        si = json.loads(http_get("http://%s:9901/server_info" % ip))
        st = proc_status(pid)
        tasks = task_run_ns(pid)
        rec.update(concurrency=si["command_line_options"]["concurrency"],
                   envoy_version=si.get("version"),
                   worker_threads=sum(1 for c, _ in tasks.values() if c.startswith("wrk:")),
                   threads_total=len(tasks), cpus_allowed=st.get("Cpus_allowed_list"),
                   cgroup_cpu_max=cg_read(pid, "cpu.max"),
                   cgroup_cpuset_effective=cg_read(pid, "cpuset.cpus.effective"),
                   qos=sh([KUBECTL, "get", "pod", "wc2", "-o", "jsonpath={.status.qosClass}"]))
        if parse_cpuset(rec["cpus_allowed"]) != NODE_SET:
            rec["invalid"].append("envoy not on the node CPUs (%s)" % rec["cpus_allowed"])
        time.sleep(SETTLE_S)
        rec["pre_idle"] = pre_check(own)
        if rec["pre_idle"]["foreign_procs"]:
            rec["invalid"].append("foreign envoy/nighthawk %s" % rec["pre_idle"]["foreign_procs"])
        s0 = snapshot(pid, None)
        time.sleep(idle_s)
        s1 = snapshot(pid, None)
        iw = window(s0, s1)
        iw["rss_kb"] = int(proc_status(pid)["VmRSS"].split()[0])
        iw["workers"] = worker_summary(iw["worker_busy"], rec["concurrency"])
        iw["invalid"] = verdict_box(iw)
        rec["idle"] = iw
        for i, rps in enumerate(rates):
            if i:
                time.sleep(PAUSE_S)
            pc = pre_check(own)
            lw = run_client(out, "%s-%d" % (tag, rps), ip, rps, DURATION, pid, own)
            lw["pre_idle"] = pc
            lw["cpu_us_per_req"] = lw["envoy_cpus_cgroup"] / lw["rps"] * 1e6 if lw["rps"] else None
            lw["cpu_us_per_req_sched"] = lw["envoy_cpus_sched"] / lw["rps"] * 1e6 if lw["rps"] else None
            lw["workers"] = worker_summary(lw["worker_busy"], rec["concurrency"])
            lw["p50_us"] = lw["nh"]["latency_us"]["p50"]
            lw["p99_us"] = lw["nh"]["latency_us"]["p99"]
            lw["invalid"] = verdict_load(lw, rps) + (
                ["foreign envoy/nighthawk %s" % pc["foreign_procs"]] if pc["foreign_procs"] else [])
            rec["loads"][str(rps)] = lw
            log(out, "  %s %d rps: %.2f us/req (sched %.2f) envoy %.3f CPUs p50 %.0f p99 %.0f hot conns %d/%d "
                     "workers busy max/med/min %.3f/%.3f/%.3f node_other %.3f invalid=%s" % (
                         tag, rps, lw["cpu_us_per_req"], lw["cpu_us_per_req_sched"], lw["envoy_cpus_cgroup"],
                         lw["p50_us"], lw["p99_us"], lw["hot_conns"], lw["client_conns"],
                         lw["workers"]["busy_max"], lw["workers"]["busy_median"], lw["workers"]["busy_min"],
                         lw["node_other_cpus"], lw["invalid"]))
        rec["rss_kb_after_load"] = int(proc_status(pid)["VmRSS"].split()[0])
    finally:
        own.discard(pid)
        delete_pod()
    log(out, "  %s idle %.4f CPUs (sched %.4f) rss %d kB after-load rss %s kB workers=%s invalid=%s %s" % (
        tag, rec["idle"]["envoy_cpus_cgroup"], rec["idle"]["envoy_cpus_sched"], rec["idle"]["rss_kb"],
        rec.get("rss_kb_after_load"), rec["concurrency"], rec["invalid"], rec["idle"]["invalid"]))
    return rec


def round_order(rnd, rng_cache={}):
    """ABBA: round pair p runs (default, req) and (req, default); a seeded coin picks which first."""
    p = (rnd - 1) // 2
    if p not in rng_cache:
        rng_cache[p] = random.Random(SEED + p).random() < 0.5
    first = ["default", "req"] if rng_cache[p] else ["req", "default"]
    return first if rnd % 2 == 1 else first[::-1]


def rate_order(rnd, rates):
    p = (rnd - 1) // 2
    return list(rates) if p % 2 == 0 else list(rates)[::-1]


def cmd_ab(out, rounds, rates, max_attempts=3):
    os.makedirs(out, exist_ok=True)
    os.sched_setaffinity(0, parse_cpuset(HARNESS_CPUS))
    ip = node_ip()
    ensure_configmap()
    own = set()
    path = os.path.join(out, "ab-records.json")
    recs = json.load(open(path))["records"] if os.path.exists(path) else []
    meta = {"image": IMAGE, "node_cpus": NODE_CPUS, "client_cpus": CLIENT_CPUS, "harness_cpus": HARNESS_CPUS,
            "nh": NH, "nh_conc": NH_CONC, "nh_conns_per_worker": NH_CONNS, "duration_s": DURATION,
            "window": [WIN_START, WIN_END], "settle_s": SETTLE_S, "idle_s": IDLE_S, "rates": rates,
            "gates": GATES, "seed": SEED, "started_utc": now()}
    done = {(r["round"], r["arm"]) for r in recs if r.get("ok")}
    for rnd in range(1, rounds + 1):
        rr = rate_order(rnd, rates)
        for arm in round_order(rnd):
            if (rnd, arm) in done:
                continue
            for attempt in range(1, max_attempts + 1):
                log(out, "round %d arm %s attempt %d rates %s" % (rnd, arm, attempt, rr))
                try:
                    rec = one_arm(out, ip, rnd, arm, rr, own)
                except Exception as e:  # noqa: BLE001 - recorded as an invalid attempt
                    rec = {"round": rnd, "arm": arm, "invalid": ["error %s: %s" % (type(e).__name__, e)],
                           "loads": {}}
                    log(out, "  error %s" % e)
                rec["attempt"] = attempt
                rec["rate_order"] = rr
                rec["ok"] = not rec["invalid"] and not rec.get("idle", {}).get("invalid") and \
                    all(not lw["invalid"] for lw in rec["loads"].values()) and len(rec["loads"]) == len(rates)
                recs.append(rec)
                write_json(path, {"meta": meta, "records": recs})
                if rec["ok"]:
                    break
                time.sleep(30)
    analyze(out)


def cmd_calib(out, arm, rates):
    os.makedirs(out, exist_ok=True)
    os.sched_setaffinity(0, parse_cpuset(HARNESS_CPUS))
    ip = node_ip()
    ensure_configmap()
    own = set()
    global DURATION, WIN_START, WIN_END
    DURATION, WIN_START, WIN_END = 30, 8, 26
    rec = one_arm(out, ip, 0, arm, rates, own, idle_s=10)
    write_json(os.path.join(out, "calib-%s.json" % arm), rec)


# ------------------------------------------------------------------ analysis

def diff_ci(xs, alpha=0.05):
    n = len(xs)
    if n < 2:
        return {"n": n}
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    hw = stats.t_ppf(1 - alpha / 2, n - 1) * sd / math.sqrt(n)
    t = m / (sd / math.sqrt(n)) if sd > 0 else float("inf")
    p = 2 * (1 - stats.t_cdf(abs(t), n - 1)) if sd > 0 else 0.0
    return {"n": n, "mean": m, "sd": sd, "lo": m - hw, "hi": m + hw, "t_p": p}


def analyze(out):
    d = json.load(open(os.path.join(out, "ab-records.json")))
    recs = [r for r in d["records"] if r.get("ok")]
    by = {(r["round"], r["arm"]): r for r in recs}
    rounds = sorted({r for r, a in by if (r, "default") in by and (r, "req") in by})
    rates = d["meta"]["rates"]
    res = {"pairs": len(rounds), "rounds": rounds, "attempts": len(d["records"]),
           "invalid_attempts": [(r["round"], r["arm"], r.get("attempt"), r["invalid"],
                                 r.get("idle", {}).get("invalid"),
                                 {k: v["invalid"] for k, v in r.get("loads", {}).items()})
                                for r in d["records"] if not r.get("ok")]}
    D = [by[(r, "default")] for r in rounds]
    R = [by[(r, "req")] for r in rounds]
    res["concurrency"] = {"default": sorted({x["concurrency"] for x in D}), "req": sorted({x["concurrency"] for x in R})}
    res["threads_total"] = {"default": sorted({x["threads_total"] for x in D}),
                            "req": sorted({x["threads_total"] for x in R})}
    idle_d = [x["idle"]["envoy_cpus_cgroup"] for x in D]
    idle_r = [x["idle"]["envoy_cpus_cgroup"] for x in R]
    res["idle"] = {
        "default_cpus": stats.mean(idle_d), "req_cpus": stats.mean(idle_r),
        "default_cpus_median": stats.median(idle_d), "req_cpus_median": stats.median(idle_r),
        "diff_cpus": diff_ci([a - b for a, b in zip(idle_d, idle_r)]),
        "ratio": stats.paired_log_ratio(idle_r, idle_d),
        "default_sched_cpus": stats.mean([x["idle"]["envoy_cpus_sched"] for x in D]),
        "req_sched_cpus": stats.mean([x["idle"]["envoy_cpus_sched"] for x in R]),
        "rss_kb_default": [x["idle"]["rss_kb"] for x in D], "rss_kb_req": [x["idle"]["rss_kb"] for x in R],
        "rss_diff_kb": diff_ci([a["idle"]["rss_kb"] - b["idle"]["rss_kb"] for a, b in zip(D, R)]),
        "rss_after_load_diff_kb": diff_ci([a["rss_kb_after_load"] - b["rss_kb_after_load"] for a, b in zip(D, R)]),
        "rss_after_load_default_kb": [x["rss_kb_after_load"] for x in D],
        "rss_after_load_req_kb": [x["rss_kb_after_load"] for x in R],
    }
    res["rates"] = {}
    for rps in rates:
        k = str(rps)
        ld = [x["loads"][k] for x in D]
        lr = [x["loads"][k] for x in R]
        o = {}
        for met in ("cpu_us_per_req", "cpu_us_per_req_sched", "p50_us", "p99_us", "envoy_cpus_cgroup"):
            a = [x[met] for x in ld]
            b = [x[met] for x in lr]
            o[met] = {"default_mean": stats.mean(a), "req_mean": stats.mean(b),
                      "default_median": stats.median(a), "req_median": stats.median(b),
                      "ratio": stats.paired_log_ratio(b, a), "won_by_req": sum(1 for x, y in zip(a, b) if y < x)}
        # absolute gap in CPUs under load vs the same round's idle gap
        gap = [a["envoy_cpus_cgroup"] - b["envoy_cpus_cgroup"] for a, b in zip(ld, lr)]
        igap = [a - b for a, b in zip(idle_d, idle_r)]
        o["load_gap_cpus"] = diff_ci(gap)
        o["load_gap_minus_idle_gap_cpus"] = diff_ci([g - i for g, i in zip(gap, igap)])
        o["per_req_extra_us"] = diff_ci([(g - i) / rps * 1e6 for g, i in zip(gap, igap)])
        o["idle_share_of_gap"] = (stats.mean(igap) / stats.mean(gap)) if stats.mean(gap) else None
        for arm, L in (("default", ld), ("req", lr)):
            o["workers_" + arm] = {
                "busy_max_median": stats.median([x["workers"]["busy_max"] for x in L]),
                "busy_median_median": stats.median([x["workers"]["busy_median"] for x in L]),
                "busy_min_median": stats.median([x["workers"]["busy_min"] for x in L]),
                "max_share_median": stats.median([x["workers"]["max_share"] for x in L]),
                "workers_with_cx_median": stats.median([sum(1 for v in x["worker_cx_active"].values() if v > 0)
                                                        for x in L]),
                "hot_conns_median": stats.median([x["hot_conns"] for x in L]),
                "client_conns_median": stats.median([x["client_conns"] for x in L]),
                "top16_conn_share_median": stats.median([x["top16_conn_share"] for x in L]),
                "client_headroom_min": min(1 - x["nh_thread_busy_max"] for x in L),
                "node_other_cpus_max": max(x["node_other_cpus"] for x in L),
                "rest_cpus_max": max(x["rest_cpus"] for x in L),
                "client_cpus_other_max": max(x["client_cpus_other"] for x in L),
                "rate_dev_max_pct": max(abs(x["rps"] / rps - 1) * 100 for x in L),
                "sched_vs_cgroup_max_pct": max(abs(x["envoy_cpus_sched"] / x["envoy_cpus_cgroup"] - 1) * 100
                                               for x in L),
            }
        res["rates"][k] = o
    write_json(os.path.join(out, "ab-summary.json"), res)
    brief = {"pairs": res["pairs"], "idle": {k: res["idle"][k] for k in ("default_cpus", "req_cpus")},
             "idle_diff": {k: res["idle"]["diff_cpus"].get(k) for k in ("mean", "lo", "hi")}}
    for k, o in res["rates"].items():
        brief[k] = {"cpu_ratio": [round(o["cpu_us_per_req"]["ratio"].get(x) or 0, 2)
                                  for x in ("effect_pct", "lo_pct", "hi_pct")],
                    "gap_minus_idle": [round(o["load_gap_minus_idle_gap_cpus"].get(x, 0), 4) for x in ("mean", "lo", "hi")]}
    print(json.dumps(brief, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "ab":
        cmd_ab(sys.argv[2], int(sys.argv[3]), [int(x) for x in sys.argv[4].split(",")])
    elif cmd == "calib":
        cmd_calib(sys.argv[2], sys.argv[3], [int(x) for x in sys.argv[4].split(",")])
    elif cmd == "analyze":
        analyze(sys.argv[2])
