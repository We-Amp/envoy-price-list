#!/usr/bin/env python3
"""Microbenchmark runner and table of the multi-threaded stats study (make.py writes micro.json).

    python3 examples/stats-mt/micro.py run CFG OUT_DIR [--root DIR] [--mix C:G] [--dry-run]
    python3 examples/stats-mt/micro.py table OUT_DIR [--json OUT.json] > micro.md
    python3 examples/stats-mt/micro.py check CFG [--root DIR]    binaries present, sha256 recorded

Runs: for each of `rounds` rounds, every run entry (binary, filter, thread placement), every
arm in a rotated order (seeded; a different first arm each round), one process per (round,
entry, arm): `<root>/<commit>/<binary> --benchmark_filter=F --benchmark_repetitions=R
--benchmark_min_time=T`, JSON out. The benchmarks pin their own threads from
STATS_BENCH_CPUS (one thread per physical core, siblings idle); STATS_BENCH_PLACEMENT labels
the placement. Before each process the box must be idle (load and busy share; on a VM the
steal share over the process is recorded and gated). Every binary's sha256 is recorded at
the start and checked at the end. The request-mix benchmarks need --mix (STATS_BENCH_MIX)
and are skipped without it.

Table: per benchmark (name and thread count) and arm, the median over the repetitions of
each round; per pair of arms (micro.json `pairs`) the paired log ratio of the time per
iteration over the rounds (df = rounds - 1) with its 95% t interval; per arm the shared
against the per-thread spaced ratio at each thread count (H1). Fewer than 5 complete rounds
are labelled descriptive.
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


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def binary_path(root, commit, binary):
    return os.path.join(os.path.expanduser(root), commit, binary)


def arm_order(cfg, rnd):
    arms = sorted(cfg["arms"])
    off = random.Random("epl-micro:%s" % cfg.get("order_seed", 1)).randrange(len(arms))
    # round pair p starts at arm p + offset; its second round runs the same order reversed
    s = ((rnd - 1) // 2 + off) % len(arms)
    o = arms[s:] + arms[:s]
    return o if rnd % 2 else list(reversed(o))


def plan(cfg, mix=None):
    """[(round, run index, arm)] in execution order; request-mix entries only with a mix."""
    out = []
    for r in range(1, int(cfg["rounds"]) + 1):
        for i, run in enumerate(cfg["runs"]):
            if run.get("needs_mix") and not mix:
                continue
            for a in arm_order(cfg, r):
                out.append((r, i, a))
    return out


def read_steal():
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    return sum(v[:8]), v[7]


def run(cfg, out, root, mix=None, dry_run=False, log=print):
    os.makedirs(out, exist_ok=True)
    hashes = {}
    for a, commit in cfg["arms"].items():
        for b in {r["binary"] for r in cfg["runs"]}:
            p = binary_path(root, commit, b)
            hashes["%s/%s" % (a, b)] = sha256(p) if os.path.exists(p) else None
    missing = [k for k, v in hashes.items() if v is None]
    if missing:
        raise SystemExit("missing binaries: %s" % ", ".join(missing))
    meta = {"config": cfg["name"], "root": root, "arms": cfg["arms"], "pairs": cfg["pairs"], "sha256_start": hashes,
            "mix": mix, "rounds": cfg["rounds"], "repetitions": cfg["repetitions"],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not dry_run:
        meta["lscpu_e"] = subprocess.run(["lscpu", "-e"], capture_output=True, text=True).stdout
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    steps = plan(cfg, mix)
    for n, (r, i, a) in enumerate(steps, 1):
        rc = cfg["runs"][i]
        tag = "r%02d-%s-%s-%s-%s" % (r, i, rc["binary"].replace("_benchmark", ""), rc["placement"], a)
        dst = os.path.join(out, tag + ".json")
        if os.path.exists(dst):
            continue  # resumable: a finished process is not run again
        env = dict(os.environ, STATS_BENCH_CPUS=rc["cpus"], STATS_BENCH_PLACEMENT=rc["placement"])
        if mix:
            env["STATS_BENCH_MIX"] = mix
        cmd = [binary_path(root, cfg["arms"][a], rc["binary"]), "--benchmark_filter=" + rc["filter"],
               "--benchmark_repetitions=%d" % int(cfg["repetitions"]), "--benchmark_min_time=" + cfg["min_time"],
               "--benchmark_format=json", "--benchmark_out=" + dst + ".tmp", "--benchmark_out_format=json"]
        if dry_run:
            log("%d/%d %s: %s" % (n, len(steps), tag, " ".join(cmd)))
            continue
        ok, det, waited = sysprobe.wait_idle(cfg["idle"], set(), log=log)
        if not ok:
            raise SystemExit("box not idle before %s: %s" % (tag, det))
        s0 = read_steal()
        t0 = time.monotonic()
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=7200)
        s1 = read_steal()
        steal = (s1[1] - s0[1]) / max(1, s1[0] - s0[0])
        rec = {"tag": tag, "round": r, "run": i, "arm": a, "exit": p.returncode, "seconds": round(time.monotonic() - t0, 1),
               "steal_share": steal, "stderr_tail": p.stderr[-600:]}
        if cfg.get("steal_gate") is not None and steal > cfg["steal_gate"]:
            rec["invalid"] = "steal %.2f%% above %.1f%%" % (100 * steal, 100 * cfg["steal_gate"])
        with open(os.path.join(out, "runs.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        if p.returncode != 0 or rec.get("invalid"):
            log("%s FAILED: exit %s %s" % (tag, p.returncode, rec.get("invalid", "")))
            # the round's entry is re-run on the next start (no output file was kept)
            continue
        os.replace(dst + ".tmp", dst)
        log("%d/%d %s done in %.0f s" % (n, len(steps), tag, rec["seconds"]))
    end = {k: sha256(binary_path(root, cfg["arms"][k.split("/")[0]], k.split("/")[1])) for k in hashes}
    meta["sha256_end"] = end
    meta["sha256_unchanged"] = end == hashes
    meta["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


# ---------------------------------------------------------------- table

UNIT = {"ns": 1.0, "us": 1e3, "ms": 1e6, "s": 1e9}


def parse(out):
    """[(round, arm, placement, benchmark, ns per iteration)] from the JSON outputs (the median
    aggregate of each benchmark's repetitions)."""
    rows = []
    with open(os.path.join(out, "meta.json")) as f:
        arms = sorted(json.load(f)["arms"], key=len, reverse=True)
    for p in sorted(glob.glob(os.path.join(out, "r*.json"))):
        base = os.path.basename(p)[:-5]
        rnd = int(base[1:3])
        arm = next((a for a in arms if base.endswith("-" + a)), None)
        with open(p) as f:
            d = json.load(f)
        for b in d.get("benchmarks", []):
            if b.get("run_type") != "aggregate" or b.get("aggregate_name") != "median":
                continue
            if b.get("error_occurred"):
                continue
            lab = b.get("label", "")
            pm = re.search(r"placement=(\S+)", lab)
            rows.append((rnd, arm, pm.group(1) if pm else "-", b["run_name"],
                         float(b["real_time"]) * UNIT.get(b.get("time_unit", "ns"), 1.0)))
    return rows


def by_key(rows):
    out = {}
    for rnd, arm, pl, name, ns in rows:
        out.setdefault((name, pl), {}).setdefault(arm, {})[rnd] = ns
    return out


def threads_of(name):
    m = re.search(r"threads:(\d+)", name)
    if m:
        return int(m.group(1))
    m = re.match(r"bmHistogramRecord/(\d+)/", name)
    return int(m.group(1)) if m else None


def paired(ref, arm):
    rounds = sorted(set(ref) & set(arm))
    return stats.paired_log_ratio([ref[r] for r in rounds], [arm[r] for r in rounds]), rounds


def table(out, rounds_needed=5):
    with open(os.path.join(out, "meta.json")) as f:
        meta = json.load(f)
    cfg_pairs = meta["pairs"]
    data = by_key(parse(out))
    L, js = ["# Stats microbenchmarks (%s)\n" % meta.get("config"), "Time per iteration, median of the "
             "repetitions per round; paired log ratio over the rounds with a 95%% t interval (negative: the arm "
             "is faster). Binaries unchanged during the run: %s.\n" % meta.get("sha256_unchanged")], {"pairs": [], "h1": []}
    L.append("## Arm against arm\n")
    L.append("| Benchmark | Placement | Arm vs ref | Effect [95% CI] | Rounds | Ref ns |\n|---|---|---|---|---|---|")
    for a, ref, rows in cfg_pairs:
        for (name, pl), per in sorted(data.items()):
            if a not in per or ref not in per:
                continue
            if rows == "n1" and threads_of(name) not in (1, None):
                continue
            p, rr = paired(per[ref], per[a])
            if p.get("half_width_pct") is None:
                continue
            row = {"benchmark": name, "placement": pl, "arm": a, "ref": ref, "rounds": len(rr),
                   "effect_pct": p["effect_pct"], "lo_pct": p["lo_pct"], "hi_pct": p["hi_pct"],
                   "ref_ns": stats.median([per[ref][r] for r in rr]),
                   "descriptive": len(rr) < rounds_needed}
            js["pairs"].append(row)
            L.append("| %s | %s | %s vs %s | %+.2f%% [%+.2f, %+.2f] | %d%s | %.2f |" % (
                name, pl, a, ref, row["effect_pct"], row["lo_pct"], row["hi_pct"], len(rr),
                " (descriptive)" if row["descriptive"] else "", row["ref_ns"]))
    L.append("")
    L.append("## Shared against per-thread spaced, per arm (H1)\n")
    L.append("| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |\n|---|---|---|---|---|---|")
    for (name, pl), per in sorted(data.items()):
        if "Shared" not in name:
            continue
        spaced = name.replace("Shared", "PerThreadSpaced")
        if (spaced, pl) not in data:
            continue
        for a in sorted(per):
            if a not in data[(spaced, pl)]:
                continue
            p, rr = paired(data[(spaced, pl)][a], per[a])
            if p.get("half_width_pct") is None:
                continue
            ratio = math.exp(p["log_mean_pct"] / 100.0)
            js["h1"].append({"benchmark": name, "placement": pl, "arm": a, "ratio": ratio,
                             "lo": math.exp(p["log_lo_pct"] / 100.0), "hi": math.exp(p["log_hi_pct"] / 100.0),
                             "rounds": len(rr)})
            L.append("| %s | %s | %s | %s | %.2fx [%.2f, %.2f] | %d |" % (
                name.split("/")[0], threads_of(name), pl, a, ratio, math.exp(p["log_lo_pct"] / 100.0),
                math.exp(p["log_hi_pct"] / 100.0), len(rr)))
    L.append("")
    return "\n".join(L) + "\n", js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "table", "check"])
    ap.add_argument("path")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--root")
    ap.add_argument("--mix")
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
    if a.cmd == "check":
        bad = 0
        for arm, commit in cfg["arms"].items():
            for b in sorted({r["binary"] for r in cfg["runs"]}):
                p = binary_path(root, commit, b)
                ok = os.path.exists(p)
                bad += 0 if ok else 1
                print("%-16s %-40s %s" % (arm, b, sha256(p) if ok else "MISSING"))
        return 1 if bad else 0
    if not a.out:
        sys.exit("run needs OUT_DIR")
    mix = a.mix or cfg.get("mix")
    meta = run(cfg, a.out, root, mix, a.dry_run)
    return 0 if a.dry_run or meta.get("sha256_unchanged") else 1


if __name__ == "__main__":
    sys.exit(main())
