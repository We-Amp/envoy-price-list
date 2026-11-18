#!/usr/bin/env python3
"""Microbenchmark runner and table of the multi-threaded stats study (make.py writes micro.json).

    python3 examples/stats-mt/micro.py smoke CFG OUT_DIR [--root DIR] [--arm ARM] [--binaries B,..]   pre-flight
    python3 examples/stats-mt/micro.py run CFG OUT_DIR [--root DIR] [--binaries B,..] [--dry-run]

--binaries restricts smoke, run and check to the run entries of those binaries (for example
atomic_model_benchmark,histogram_record_benchmark while stat_update_benchmark is rebuilt); the
identity check then covers only those binaries.
    python3 examples/stats-mt/micro.py table OUT_DIR [--json OUT.json] > micro.md
    python3 examples/stats-mt/micro.py check CFG [--root DIR]    binaries present, sha256 as pinned

The benchmarks measure a time-bounded window inside one Google Benchmark iteration (manual time,
no estimation runs; every thread keeps running until all have finished their window) and
report ns_per_op, ops_per_sec, cycles_per_op, instructions_per_op, fairness and min_thread_ops
as results, and window_overlap, invol_switches and steal_ticks as gate inputs. The record-only
histogram benchmark reports ns_per_sample. The runner reads those counters, never the
library's time column; conclusions rest on cycles_per_op.

Identity: micro.json pins the sha256 of every (arm, binary) the runs use (`expected_sha256`,
from the build record). `run` and `check` refuse while a pin is the placeholder (null), when a
binary is missing or different, or when two arms carry the same binary. `smoke` runs before the
pins exist and records the hashes it saw.

Smoke (the pre-flight, first on the build host, then the first action of every VM session):
one arm, every run entry, the smoke thread counts, 50 ms warm-up and 200 ms windows, 2
repetitions, one round. It is judged per binary: each binary prints SMOKE PASSED or SMOKE FAILED
with every problem, so a binary that passes can run while another is rebuilt; the exit status is
1 if any binary failed. It also prints the largest involuntary-switch count it saw (the VM bound
is frozen from that).

Run: for each of `rounds` rounds, every run entry, every arm of that entry in a rotated order
(seeded; a different first arm each round), one process per (round, entry, arm):
`<root>/<commit>/<binary> --benchmark_filter=F --benchmark_repetitions=R`, JSON out. The
benchmarks pin their own threads from STATS_BENCH_CPUS (one CPU per physical core, siblings
idle: checked against `lscpu` at the start) and register the thread counts the entry passes in
STATS_BENCH_THREADS; the windows come from STATS_BENCH_WARMUP / STATS_BENCH_SECONDS. Before
each process the box must be idle; on a VM the steal share over the process is gated.

Gates, per repetition, fail-closed (a failing output is not kept and the entry is re-run on the
next start): exit 0; no repetition errored or skipped; every expected benchmark (name and
count) has all its repetitions and a median; the time outside the common window,
(1 - window_overlap) * window_s, at most 2 ms + 0.5% of the window (overlap about 0.990 at
0.2 s, 0.993 at 1 s: batch granularity passes, a descheduled thread does not); invol_switches
(summed over the threads) known and <= the bound per thread times the threads: per thread
max(max_invol_switches, invol_switches_per_s * window_s) where the box sets a rate
(max(5, 25/s x window) on every box), else max_invol_switches (frozen from the box's own smoke;
`run` refuses while it is unset);
the counts per repetition are recorded in runs.jsonl and the bound in meta.json; the slowest thread's operations at least 20,000 per second
of window and never under 1,024 (a stalled thread, not a slow contended one); cycles_per_op and instructions_per_op non-negative where the box has a PMU;
the per-process steal gate. fairness is a result, never a gate.

Table: per benchmark and arm the median of each round's repetition median; per pair of arms
(micro.json `pairs`) the paired log ratio of cycles_per_op (and of ns_per_op beside it) over
the rounds with its 95% t interval (df = rounds - 1); per model variant against Current, the
same within the one model build; per arm the shared against the per-thread spaced ratio (H1);
fairness medians; the spacing distance (min_distance_bytes) of the spaced stat_update cases,
recorded per process and tabulated as the minimum seen. Fewer than 5 complete rounds are labelled descriptive.
"""

import argparse
import glob
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import stats, sysprobe  # noqa: E402

METRICS = ["cycles_per_op", "instructions_per_op", "ns_per_op", "ops_per_sec", "fairness", "min_thread_ops",
           "window_overlap", "invol_switches", "steal_ticks", "ns_per_sample", "min_distance_bytes"]
SMOKE = {"warmup_s": 0.05, "window_s": 0.2, "repetitions": 2}


def ops_floor(cfg):
    return max(int(cfg["min_thread_ops_abs"]), int(math.ceil(cfg["ops_floor_per_s"] * cfg["window_s"])))


def max_nonoverlap_s(cfg):
    return cfg["max_nonoverlap_s"] + cfg["max_nonoverlap_share"] * cfg["window_s"]


def invol_limit(cfg, threads=1):
    """The involuntary-switch bound of one repetition with `threads` threads (the counter is the
    sum over the threads): the per-thread bound times the threads; None while unset."""
    flat = cfg.get("max_invol_switches")
    if flat is None:
        return None
    rate = cfg.get("invol_switches_per_s")
    per = max(float(flat), float(rate) * cfg["window_s"]) if rate else float(flat)
    return per * max(1, int(threads or 1))


def select_binaries(cfg, binaries):
    """cfg restricted to the run entries (and smoke entries) of the given binaries."""
    if not binaries:
        return cfg
    want = set(binaries)
    known = {r["binary"] for r in cfg["runs"]} | {r["binary"] for r in (cfg.get("smoke") or {}).get("runs", [])}
    if want - known:
        raise SystemExit("unknown binaries: %s" % ", ".join(sorted(want - known)))
    c = json.loads(json.dumps(cfg))
    c["runs"] = [r for r in c["runs"] if r["binary"] in want]
    if c.get("smoke"):
        c["smoke"]["runs"] = [r for r in c["smoke"]["runs"] if r["binary"] in want]
    return c


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def binary_path(root, commit, binary):
    return os.path.join(os.path.expanduser(root), commit, binary)


# Google Benchmark puts the registered timing into the name
# ("bmX/iterations:1/manual_time/threads:4", "bmY/4/min_time:1.000/manual_time"); names are
# compared without those parts.
_TIME_PARTS = re.compile(r"/(?:min_(?:warmup_)?time:[0-9.]+|iterations:[0-9]+)")


def norm_name(name):
    return _TIME_PARTS.sub("", name or "")


def run_arms(cfg, rc):
    return list(rc.get("arms") or sorted(cfg["arms"]))


def needed(cfg):
    """[(arm, binary)] the run entries use."""
    return sorted({(a, rc["binary"]) for rc in cfg["runs"] for a in run_arms(cfg, rc)})


def identity(cfg, root, require_pins=True):
    """({"arm/binary": sha256 or None}, [problem]): every binary the runs use present and equal
    to its pinned sha256, and no two arms with the same binary."""
    exp = cfg.get("expected_sha256") or {}
    hashes, probs = {}, []
    for a, b in needed(cfg):
        p = binary_path(root, cfg["arms"][a], b)
        got = sha256(p) if os.path.exists(p) else None
        hashes["%s/%s" % (a, b)] = got
        want = (exp.get(a) or {}).get(b)
        if got is None:
            probs.append("%s/%s: missing (%s)" % (a, b, p))
        elif not require_pins:
            pass
        elif not want:
            probs.append("%s/%s: sha256 not pinned (placeholder; pin from the build record after the rebuild)"
                         % (a, b))
        elif got != want:
            probs.append("%s/%s: sha256 %s, pinned %s" % (a, b, got[:16], want[:16]))
    seen = {}
    for k, v in sorted(hashes.items()):
        if v is None:
            continue
        b = k.split("/", 1)[1]
        if (b, v) in seen:
            probs.append("%s and %s are the same binary" % (seen[(b, v)], k))
        seen[(b, v)] = k
    return hashes, probs


def parse_lscpu(text):
    """{cpu: core} from `lscpu -p=CPU,CORE`."""
    out = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        c, core = line.split(",")[:2]
        out[int(c)] = int(core)
    return out


def cpu_list(text):
    out = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    return out


def check_cores(cfg, cores):
    """[problem]: a placement lists two CPUs of one core, or a CPU the box lacks."""
    probs = []
    for rc in cfg["runs"]:
        seen = {}
        for c in cpu_list(rc["cpus"]):
            if c not in cores:
                probs.append("%s: CPU %d not on this box" % (rc["placement"], c))
            elif cores[c] in seen:
                probs.append("%s: CPUs %d and %d share core %d (siblings must stay idle)" % (
                    rc["placement"], seen[cores[c]], c, cores[c]))
            else:
                seen[cores[c]] = c
    return sorted(set(probs))


def arm_order(arms, rnd, seed=1):
    arms = sorted(arms)
    off = random.Random("epl-micro:%s" % seed).randrange(len(arms))
    # round pair p starts at arm p + offset; its second round runs the same order reversed
    s = ((rnd - 1) // 2 + off) % len(arms)
    o = arms[s:] + arms[:s]
    return o if rnd % 2 else list(reversed(o))


def plan(cfg):
    """[(round, run index, arm)] in execution order."""
    out = []
    for r in range(1, int(cfg["rounds"]) + 1):
        for i, rc in enumerate(cfg["runs"]):
            for a in arm_order(run_arms(cfg, rc), r, cfg.get("order_seed", 1)):
                out.append((r, i, a))
    return out


def run_env(cfg, rc):
    """The environment of one run entry: CPUs, placement label, thread counts, windows."""
    env = {"STATS_BENCH_CPUS": rc["cpus"], "STATS_BENCH_PLACEMENT": rc["placement"],
           "STATS_BENCH_WARMUP": "%g" % cfg["warmup_s"], "STATS_BENCH_SECONDS": "%g" % cfg["window_s"]}
    if rc.get("threads"):
        env["STATS_BENCH_THREADS"] = ",".join(str(t) for t in rc["threads"])
    return env


def gate_problems(b, cfg, rc):
    """[problem] of one repetition (an iteration entry) against the validity gates."""
    nm = norm_name(b.get("name"))
    if b.get("error_occurred"):
        return ["%s: %s" % (nm, b.get("error_message") or "error")]
    probs = []
    if rc.get("kind") == "window":
        ov = b.get("window_overlap")
        lim_s = max_nonoverlap_s(cfg)
        if ov is None or (1.0 - float(ov)) * cfg["window_s"] > lim_s + 1e-12:
            probs.append("%s: window overlap %s: %s ms outside the common window, limit %.2f ms" % (
                nm, ov, "?" if ov is None else "%.2f" % (1000 * (1.0 - float(ov)) * cfg["window_s"]), 1000 * lim_s))
        sw = b.get("invol_switches")
        lim = invol_limit(cfg, threads_of(nm))
        if sw is None or float(sw) < 0:
            probs.append("%s: involuntary switches unavailable" % nm)
        elif lim is not None and float(sw) > lim:
            probs.append("%s: %d involuntary switches, bound %g" % (nm, float(sw), lim))
        ops = b.get("min_thread_ops")
        if ops is None or float(ops) < ops_floor(cfg):
            probs.append("%s: %s operations on the slowest thread, floor %d" % (nm, ops, ops_floor(cfg)))
        if cfg.get("pmu"):
            for k in ("cycles_per_op", "instructions_per_op"):
                if b.get(k) is None or float(b[k]) < 0:
                    probs.append("%s: %s unavailable on a box with a PMU" % (nm, k))
    elif rc.get("kind") == "histogram":
        v = b.get("ns_per_sample")
        if v is None or float(v) <= 0:
            probs.append("%s: no ns_per_sample" % nm)
    return probs


def check_output(d, cfg, rc):
    """[problem] of one benchmark JSON output: every repetition passes the gates, and every
    expected benchmark has all its repetitions and a median."""
    probs = []
    reps = int(cfg["repetitions"])
    n_it, med = {}, set()
    for b in d.get("benchmarks", []):
        nm = norm_name(b.get("run_name") or b.get("name"))
        if b.get("run_type") == "aggregate":
            if b.get("aggregate_name") == "median" and not b.get("error_occurred"):
                med.add(nm)
            continue
        p = gate_problems(b, cfg, rc)
        probs.extend(p)
        if not p:
            n_it[nm] = n_it.get(nm, 0) + 1
    for nm in rc["expect"]:
        if n_it.get(nm, 0) < reps or nm not in med:
            probs.append("%s: %d of %d repetitions valid%s" % (nm, n_it.get(nm, 0), reps,
                                                               "" if nm in med else ", no median"))
    return probs


def max_switches(d):
    v = [float(b["invol_switches"]) for b in d.get("benchmarks", [])
         if b.get("run_type") == "iteration" and b.get("invol_switches") is not None]
    return max(v) if v else None


def read_steal():
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    return sum(v[:8]), v[7]


def one_process(cfg, rc, arm, root, dst, log):
    """Run one benchmark process into dst.tmp; (record, parsed JSON or None)."""
    env = dict(os.environ, **run_env(cfg, rc))
    cmd = [binary_path(root, cfg["arms"][arm], rc["binary"]), "--benchmark_filter=" + rc["filter"],
           "--benchmark_repetitions=%d" % int(cfg["repetitions"]),
           "--benchmark_format=json", "--benchmark_out=" + dst + ".tmp", "--benchmark_out_format=json"]
    ok, det, waited = sysprobe.wait_idle(cfg["idle"], set(), log=log)
    if not ok:
        raise SystemExit("box not idle before %s: %s" % (os.path.basename(dst), det))
    s0 = read_steal()
    t0 = time.monotonic()
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=7200)
    s1 = read_steal()
    steal = (s1[1] - s0[1]) / max(1, s1[0] - s0[0])
    rec = {"exit": p.returncode, "seconds": round(time.monotonic() - t0, 1), "steal_share": steal,
           "stderr_tail": p.stderr[-600:]}
    probs = []
    if p.returncode != 0:
        probs.append("exit %d" % p.returncode)
    if cfg.get("steal_gate") is not None and steal > cfg["steal_gate"]:
        probs.append("steal %.2f%% above %.1f%%" % (100 * steal, 100 * cfg["steal_gate"]))
    d = None
    try:
        with open(dst + ".tmp") as f:
            d = json.load(f)
    except (OSError, ValueError) as ex:
        probs.append("no JSON output: %s" % ex)
    if d is not None:
        probs.extend(check_output(d, cfg, rc))
        rec["max_invol_switches_seen"] = max_switches(d)
        sw = {}
        for b in d.get("benchmarks", []):
            if b.get("run_type") == "iteration" and b.get("invol_switches") is not None:
                sw.setdefault(norm_name(b.get("name")), []).append(b["invol_switches"])
        rec["invol_switches"] = sw
        dist = {}
        for b in d.get("benchmarks", []):
            if b.get("run_type") == "iteration" and b.get("min_distance_bytes") is not None:
                nm = norm_name(b.get("name"))
                dist[nm] = min(dist.get(nm, float("inf")), float(b["min_distance_bytes"]))
        if dist:
            rec["min_distance_bytes"] = dist
    rec["problems"] = probs
    return rec, d


def start(cfg, out, root, require_pins, dry_run, log):
    hashes, probs = identity(cfg, root, require_pins)
    if probs and not dry_run:
        raise SystemExit("binary identity (not run):\n  " + "\n  ".join(probs))
    for p in probs:
        log("identity: " + p)
    meta = {"config": cfg["name"], "root": root, "arms": cfg["arms"], "pairs": cfg["pairs"],
            "sha256_start": hashes, "expected_sha256": cfg.get("expected_sha256"),
            "model_reference": cfg.get("model_reference"), "rounds": cfg["rounds"],
            "repetitions": cfg["repetitions"], "warmup_s": cfg["warmup_s"], "window_s": cfg["window_s"],
            "invol_bound": {"max_invol_switches": cfg.get("max_invol_switches"),
                            "invol_switches_per_s": cfg.get("invol_switches_per_s"), "limit_per_thread": invol_limit(cfg),
                            "record": cfg.get("invol_bound_record")},
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not dry_run:
        lp = subprocess.run(["lscpu", "-p=CPU,CORE"], capture_output=True, text=True).stdout
        probs = check_cores(cfg, parse_lscpu(lp))
        if probs:
            raise SystemExit("placement (not run):\n  " + "\n  ".join(probs))
        meta["lscpu_e"] = subprocess.run(["lscpu", "-e"], capture_output=True, text=True).stdout
        meta["lscpu_p"] = lp
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta, hashes


def finish(cfg, out, root, meta, hashes):
    end = {}
    for k in hashes:
        a, b = k.split("/", 1)
        p = binary_path(root, cfg["arms"][a], b)
        end[k] = sha256(p) if os.path.exists(p) else None
    meta["sha256_end"] = end
    meta["sha256_unchanged"] = end == hashes
    meta["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


def tag_of(r, i, rc, a):
    return "r%02d-%s-%s-%s-%s" % (r, i, rc["binary"].replace("_benchmark", ""), rc["placement"], a)


def run(cfg, out, root, dry_run=False, log=print):
    if cfg.get("max_invol_switches") is None and not dry_run:
        raise SystemExit("max_invol_switches is unset: freeze it from the smoke (box micro.max_invol_switches); not run")
    meta, hashes = start(cfg, out, root, True, dry_run, log)
    steps = plan(cfg)
    for n, (r, i, a) in enumerate(steps, 1):
        rc = cfg["runs"][i]
        tag = tag_of(r, i, rc, a)
        dst = os.path.join(out, tag + ".json")
        if os.path.exists(dst):
            continue  # resumable: a finished process is not run again
        if dry_run:
            log("%d/%d %s: %s %s" % (n, len(steps), tag, " ".join("%s=%s" % kv for kv in sorted(run_env(cfg, rc).items())),
                                     " ".join([binary_path(root, cfg["arms"][a], rc["binary"]),
                                               "--benchmark_filter=" + rc["filter"],
                                               "--benchmark_repetitions=%d" % int(cfg["repetitions"])])))
            continue
        rec, _ = one_process(cfg, rc, a, root, dst, log)
        rec.update(tag=tag, round=r, run=i, arm=a)
        with open(os.path.join(out, "runs.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        if rec["problems"]:
            log("%s INVALID: %s" % (tag, "; ".join(rec["problems"][:4])))
            continue  # not kept: the entry is re-run on the next start
        os.replace(dst + ".tmp", dst)
        log("%d/%d %s done in %.0f s" % (n, len(steps), tag, rec["seconds"]))
    if dry_run:
        return meta
    return finish(cfg, out, root, meta, hashes)


def smoke_config(cfg, arm=None):
    """The pre-flight configuration: one arm, every run entry, the smoke thread counts, short
    windows, 2 repetitions, one round."""
    sm = cfg["smoke"]
    arm = arm or sm["arm"]
    if arm not in cfg["arms"]:
        raise SystemExit("smoke arm %r is not an arm of %s" % (arm, cfg["name"]))
    c = json.loads(json.dumps(cfg))
    c.update(name=cfg["name"] + "-smoke", rounds=1, repetitions=SMOKE["repetitions"], warmup_s=SMOKE["warmup_s"],
             window_s=SMOKE["window_s"], pairs=[])
    c["runs"] = [r for r in sm["runs"]]
    for r in c["runs"]:
        r["arms"] = [arm]
    return c


def smoke(cfg, out, root, arm=None, log=print):
    """Pre-flight: (passed, problems, largest involuntary-switch count seen, {binary: [problem]})."""
    c = smoke_config(cfg, arm)
    meta, hashes = start(c, out, root, False, False, log)
    problems, worst = [], None
    per_bin = {rc["binary"]: [] for rc in c["runs"]}
    for i, rc in enumerate(c["runs"]):
        a = rc["arms"][0]
        tag = tag_of(1, i, rc, a)
        dst = os.path.join(out, tag + ".json")
        rec, _ = one_process(c, rc, a, root, dst, log)
        rec.update(tag=tag, round=1, run=i, arm=a)
        with open(os.path.join(out, "runs.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        problems.extend("%s: %s" % (tag, p) for p in rec["problems"])
        per_bin[rc["binary"]].extend("%s: %s" % (tag, p) for p in rec["problems"])
        if rec.get("max_invol_switches_seen") is not None:
            worst = max(worst or 0, rec["max_invol_switches_seen"])
        if not rec["problems"]:
            os.replace(dst + ".tmp", dst)
        log("%s %s in %.0f s" % (tag, "ok" if not rec["problems"] else "FAILED", rec["seconds"]))
    meta = finish(c, out, root, meta, hashes)
    for k, v in meta["sha256_end"].items():
        if v != hashes.get(k):
            problems.append("%s changed during the smoke" % k)
            per_bin[k.split("/", 1)[1]].append("%s changed during the smoke" % k)
    meta.update(smoke_passed=not problems, smoke_problems=problems, max_invol_switches_seen=worst,
                smoke_binaries={b: not p for b, p in per_bin.items()})
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return not problems, problems, worst, per_bin


# ---------------------------------------------------------------- table

def arms_of(out):
    with open(os.path.join(out, "meta.json")) as f:
        return sorted(json.load(f)["arms"], key=len, reverse=True)


def parse(out):
    """[(round, arm, placement, benchmark, {metric: value or None})] from the median aggregates
    of the kept outputs; a negative counter (unavailable) is None."""
    rows = []
    arms = arms_of(out)
    for p in sorted(glob.glob(os.path.join(out, "r*.json"))):
        base = os.path.basename(p)[:-5]
        rnd = int(base[1:3])
        arm = next((a for a in arms if base.endswith("-" + a)), None)
        with open(p) as f:
            d = json.load(f)
        for b in d.get("benchmarks", []):
            if b.get("run_type") != "aggregate" or b.get("aggregate_name") != "median" or b.get("error_occurred"):
                continue
            pm = re.search(r"placement=(\S+)", b.get("label", ""))
            m = {k: (None if b.get(k) is None or float(b[k]) < 0 else float(b[k])) for k in METRICS}
            rows.append((rnd, arm, pm.group(1) if pm else "-", norm_name(b["run_name"]), m))
    return rows


def by_key(rows, metric):
    out = {}
    for rnd, arm, pl, name, m in rows:
        if m.get(metric) is not None:
            out.setdefault((name, pl), {}).setdefault(arm, {})[rnd] = m[metric]
    return out


def threads_of(name):
    m = re.search(r"threads:(\d+)", name)
    if m:
        return int(m.group(1))
    m = re.match(r"bmHistogramRecord(?:Only)?/(\d+)", name)
    return int(m.group(1)) if m else None


def paired(ref, arm):
    rounds = sorted(set(ref) & set(arm))
    return stats.paired_log_ratio([ref[r] for r in rounds], [arm[r] for r in rounds]), rounds


def primary(name):
    return "ns_per_sample" if name.startswith("bmHistogramRecord") else "cycles_per_op"


def table(out, rounds_needed=5):
    with open(os.path.join(out, "meta.json")) as f:
        meta = json.load(f)
    rows = parse(out)
    data = {m: by_key(rows, m) for m in METRICS}
    L = ["# Stats microbenchmarks (%s)\n" % meta.get("config"),
         "Per round the median over the repetitions; paired log ratio over the rounds with a 95%% t interval "
         "(negative: faster or cheaper than the reference). Cycles per operation are the primary measure "
         "(ns per sample for the histogram); ns per operation beside them. Binaries unchanged during the "
         "run: %s.\n" % meta.get("sha256_unchanged")]
    js = {"pairs": [], "model": [], "h1": [], "fairness": {}}

    def fmt(p, rr):
        return "%+.2f%% [%+.2f, %+.2f] | %d%s" % (p["effect_pct"], p["lo_pct"], p["hi_pct"], len(rr),
                                                  " (descriptive)" if len(rr) < rounds_needed else "")

    L.append("## Arm against arm\n")
    L.append("| Benchmark | Placement | Arm vs ref | Measure | Effect [95% CI] | Rounds | Ref |\n|---|---|---|---|---|---|---|")
    for a, ref, which in meta["pairs"]:
        for (name, pl) in sorted(set(data["cycles_per_op"]) | set(data["ns_per_sample"])):
            if which == "n1" and threads_of(name) not in (1, None):
                continue
            for metric in (primary(name), "ns_per_op"):
                per = data[metric].get((name, pl)) or {}
                if a not in per or ref not in per:
                    continue
                p, rr = paired(per[ref], per[a])
                if p.get("half_width_pct") is None:
                    continue
                row = {"benchmark": name, "placement": pl, "arm": a, "ref": ref, "metric": metric, "rounds": len(rr),
                       "effect_pct": p["effect_pct"], "lo_pct": p["lo_pct"], "hi_pct": p["hi_pct"],
                       "ref_value": stats.median([per[ref][r] for r in rr]), "descriptive": len(rr) < rounds_needed}
                js["pairs"].append(row)
                L.append("| %s | %s | %s vs %s | %s | %s | %.2f |" % (name, pl, a, ref, metric, fmt(p, rr),
                                                                     row["ref_value"]))
    L.append("")
    L.append("## Model variants against Current (one build)\n")
    L.append("| Benchmark | Threads | Placement | Effect on cycles/op [95% CI] | Rounds |\n|---|---|---|---|---|")
    for (name, pl), per in sorted(data["cycles_per_op"].items()):
        m = re.match(r"bmModel(\w+?)(Shared|PerThreadSpaced)/", name)
        if not m or m.group(1) == "Current":
            continue
        ref_name = name.replace("bmModel" + m.group(1), "bmModelCurrent", 1)
        ref = data["cycles_per_op"].get((ref_name, pl))
        if not ref:
            continue
        for a in sorted(per):
            if a not in ref:
                continue
            p, rr = paired(ref[a], per[a])
            if p.get("half_width_pct") is None:
                continue
            js["model"].append({"benchmark": name, "placement": pl, "arm": a, "effect_pct": p["effect_pct"],
                                "lo_pct": p["lo_pct"], "hi_pct": p["hi_pct"], "rounds": len(rr)})
            L.append("| %s | %s | %s | %s |" % (name.split("/")[0], threads_of(name), pl, fmt(p, rr)))
    L.append("")
    L.append("## Shared against per-thread spaced, per arm (H1; cycles/op)\n")
    L.append("| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |\n|---|---|---|---|---|---|")
    for (name, pl), per in sorted(data["cycles_per_op"].items()):
        if "Shared" not in name:
            continue
        spaced = data["cycles_per_op"].get((name.replace("Shared", "PerThreadSpaced"), pl))
        if not spaced:
            continue
        for a in sorted(per):
            if a not in spaced:
                continue
            p, rr = paired(spaced[a], per[a])
            if p.get("half_width_pct") is None:
                continue
            ratio = math.exp(p["log_mean_pct"] / 100.0)
            lo, hi = math.exp(p["log_lo_pct"] / 100.0), math.exp(p["log_hi_pct"] / 100.0)
            js["h1"].append({"benchmark": name, "placement": pl, "arm": a, "ratio": ratio, "lo": lo, "hi": hi,
                             "rounds": len(rr)})
            L.append("| %s | %s | %s | %s | %.2fx [%.2f, %.2f] | %d |" % (name.split("/")[0], threads_of(name), pl, a,
                                                                        ratio, lo, hi, len(rr)))
    L.append("")
    dist = {}
    for rnd, arm, pl, name, m in rows:
        if m.get("min_distance_bytes") is not None:
            k = (name, pl, arm)
            dist[k] = min(dist.get(k, float("inf")), m["min_distance_bytes"])
    if dist:
        js["min_distance_bytes"] = {"%s|%s|%s" % k: v for k, v in dist.items()}
        L.append("## Spacing of the spaced cases (min_distance_bytes, the smallest seen over rounds)\n")
        L.append("| Benchmark | Placement | Arm | Bytes |\n|---|---|---|---|")
        for (name, pl, arm), v in sorted(dist.items()):
            L.append("| %s | %s | %s | %d |" % (name, pl, arm, v))
        L.append("")
    L.append("## Fairness (slowest thread's operations over the fastest's; a result, not a gate)\n")
    L.append("| Benchmark | Placement | Arm | Median over rounds |\n|---|---|---|---|")
    for (name, pl), per in sorted(data["fairness"].items()):
        if threads_of(name) in (1, None):
            continue
        for a in sorted(per):
            v = stats.median(list(per[a].values()))
            js["fairness"]["%s|%s|%s" % (name, pl, a)] = v
            L.append("| %s | %s | %s | %.3f |" % (name, pl, a, v))
    L.append("")
    return "\n".join(L) + "\n", js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "smoke", "table", "check"])
    ap.add_argument("path")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--root")
    ap.add_argument("--arm")
    ap.add_argument("--binaries", help="comma-separated binaries to restrict to")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.cmd == "table":
        text, js = table(a.path)
        sys.stdout.write(text)
        if a.json:
            with open(a.json, "w") as f:
                json.dump(js, f, indent=1)
        return 0
    with open(a.path) as f:
        cfg = json.load(f)
    root = a.root or cfg["root"]
    cfg = select_binaries(cfg, [b for b in (a.binaries or "").split(",") if b])
    if a.cmd == "check":
        hashes, probs = identity(cfg, root)
        for k, v in sorted(hashes.items()):
            print("%-48s %s" % (k, v or "MISSING"))
        for p in probs:
            print("PROBLEM " + p)
        print("identity %s" % ("OK" if not probs else "FAILED"))
        return 1 if probs else 0
    if not a.out:
        sys.exit("%s needs OUT_DIR" % a.cmd)
    if a.cmd == "smoke":
        ok, probs, worst, per_bin = smoke(cfg, a.out, root, a.arm)
        for b, ps in sorted(per_bin.items()):
            if ps:
                print("SMOKE FAILED %s (%d problems):" % (b, len(ps)))
                for p in ps:
                    print("  " + p)
            else:
                print("SMOKE PASSED %s" % b)
        print("largest involuntary-switch count %s" % worst)
        return 0 if ok else 1
    meta = run(cfg, a.out, root, a.dry_run)
    return 0 if a.dry_run or meta.get("sha256_unchanged") else 1


if __name__ == "__main__":
    sys.exit(main())
