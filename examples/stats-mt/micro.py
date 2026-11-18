#!/usr/bin/env python3
"""Microbenchmark runner and table of the multi-threaded stats study (make.py writes micro.json).

    python3 examples/stats-mt/micro.py run CFG OUT_DIR [--root DIR] [--mix C:G] [--dry-run]
    python3 examples/stats-mt/micro.py table OUT_DIR [--json OUT.json] > micro.md
    python3 examples/stats-mt/micro.py check CFG [--root DIR]    binaries present, sha256 as pinned

Identity: micro.json pins the sha256 of every arm's every binary (`expected_sha256`, from the
build record); a run refuses to start when one is unpinned, missing or different, or when two
arms carry the same binary. The binaries report no revision of their own.

Runs: for each of `rounds` rounds, every run entry (binary, filter, thread placement), every
arm in a rotated order (seeded; a different first arm each round), one process per (round,
entry, arm): `<root>/<commit>/<binary> --benchmark_filter=F --benchmark_repetitions=R`, JSON
out (the benchmarks set their own minimum time). The benchmarks pin their own threads from
STATS_BENCH_CPUS (one thread per physical core, siblings idle: checked against `lscpu` at the
start unless the placement is marked `smt`) and register the thread and hammer counts the
entry passes in STATS_BENCH_THREADS and STATS_BENCH_HAMMERS; STATS_BENCH_PLACEMENT labels the
placement. An output is accepted only when every expected benchmark (name and count) has all
its repetitions and a median, no repetition errored or was skipped, and no thread finish
spread is above the limit; otherwise the entry is re-run on the next start. Before each
process the box must be idle (load and busy share; on a VM the steal share over the process
is recorded and gated). Every binary's sha256 is checked at the start and at the end. The
request-mix benchmarks need --mix (STATS_BENCH_MIX) and are skipped without it.

Table: per benchmark (name and thread count) and arm, the median over the repetitions of
each round; per pair of arms (micro.json `pairs`) the paired log ratio of the time per
iteration over the rounds (df = rounds - 1) with its 95% t interval; per arm the shared
against the per-thread spaced ratio at each thread count (H1); per arm, hammer count and
mode the hammers' update rate during and between flushes as a share of the hammer-only
baseline (M6). Per-thread counters below zero (no PMU) are shown as unavailable. Fewer than 5
complete rounds are labelled descriptive.
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


# Google Benchmark puts the registered minimum and warm-up time into the name
# ("bmX/min_time:1.000/min_warmup_time:0.200/real_time/threads:4"); names are compared without them.
_TIME_PARTS = re.compile(r"/min_(?:warmup_)?time:[0-9.]+")


def norm_name(name):
    return _TIME_PARTS.sub("", name or "")


def identity(cfg, root):
    """({"arm/binary": sha256 or None}, [problem]): every arm's binaries present and equal to the
    pinned sha256, and no two arms with the same binary (MB1)."""
    exp = cfg.get("expected_sha256") or {}
    hashes, probs = {}, []
    for a, commit in sorted(cfg["arms"].items()):
        for b in sorted({r["binary"] for r in cfg["runs"]}):
            p = binary_path(root, commit, b)
            got = sha256(p) if os.path.exists(p) else None
            hashes["%s/%s" % (a, b)] = got
            want = (exp.get(a) or {}).get(b)
            if got is None:
                probs.append("%s/%s: missing (%s)" % (a, b, p))
            elif not want:
                probs.append("%s/%s: no sha256 pinned in the config" % (a, b))
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
    """[problem]: a placement (not marked smt) lists two CPUs of one core, or a CPU the box lacks."""
    probs = []
    for rc in cfg["runs"]:
        if rc.get("smt"):
            continue
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


def check_mix(mix, fields):
    """None or the reason a STATS_BENCH_MIX value is unusable (M7: `fields` non-negative integers)."""
    parts = (mix or "").split(":")
    if len(parts) != fields or not all(p.isdigit() for p in parts):
        return "STATS_BENCH_MIX %r: needs %d colon-separated non-negative integers" % (mix, fields)
    return None


def check_output(d, cfg, rc=None):
    """[problem] of one benchmark JSON output: no repetition errored or was skipped (MB3); every
    expected benchmark of the run entry has all its repetitions and a median (MB2); no
    repetition finished with a spread between threads above max_spread (M2)."""
    probs = []
    bms = d.get("benchmarks", [])
    for b in bms:
        if b.get("error_occurred"):
            probs.append("%s: %s" % (norm_name(b.get("name")), b.get("error_message") or "error"))
    if rc is not None and rc.get("expect"):
        reps = int(cfg.get("repetitions", 1))
        n_it, med = {}, set()
        for b in bms:
            if b.get("error_occurred"):
                continue
            nm = norm_name(b.get("run_name") or b.get("name"))
            if b.get("run_type") == "iteration":
                n_it[nm] = n_it.get(nm, 0) + 1
            elif b.get("run_type") == "aggregate" and b.get("aggregate_name") == "median":
                med.add(nm)
        for nm in rc["expect"]:
            if n_it.get(nm, 0) < reps or nm not in med:
                probs.append("%s: %d of %d repetitions%s" % (nm, n_it.get(nm, 0), reps,
                                                               "" if nm in med else ", no median"))
    key, lim = cfg.get("spread_counter"), cfg.get("max_spread")
    if key and lim is not None:
        for b in d.get("benchmarks", []):
            if b.get("run_type") == "iteration" and b.get(key) is not None and float(b[key]) > lim:
                probs.append("%s: thread finish spread %.1f%% above %.0f%%" % (b.get("name"), 100 * float(b[key]),
                                                                               100 * lim))
    return probs


def run_env(rc, mix=None):
    """The environment of one run entry: CPUs, placement label, and the thread and hammer counts
    the benchmarks register (MB2)."""
    env = {"STATS_BENCH_CPUS": rc["cpus"], "STATS_BENCH_PLACEMENT": rc["placement"]}
    if rc.get("threads"):
        env["STATS_BENCH_THREADS"] = ",".join(str(t) for t in rc["threads"])
    if rc.get("hammers"):
        env["STATS_BENCH_HAMMERS"] = ",".join(str(h) for h in rc["hammers"])
    if mix:
        env["STATS_BENCH_MIX"] = mix
    return env


def read_steal():
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    return sum(v[:8]), v[7]


def run(cfg, out, root, mix=None, dry_run=False, log=print):
    if mix:
        why = check_mix(mix, int(cfg.get("mix_fields", 6)))
        if why:
            raise SystemExit(why)
    hashes, probs = identity(cfg, root)
    if probs and not dry_run:
        raise SystemExit("binary identity (not run):\n  " + "\n  ".join(probs))
    for p in probs:
        log("identity: " + p)
    lscpu_p = None
    if not dry_run:
        lscpu_p = subprocess.run(["lscpu", "-p=CPU,CORE"], capture_output=True, text=True).stdout
        probs = check_cores(cfg, parse_lscpu(lscpu_p))
        if probs:
            raise SystemExit("placement (not run):\n  " + "\n  ".join(probs))
    os.makedirs(out, exist_ok=True)
    meta = {"config": cfg["name"], "root": root, "arms": cfg["arms"], "pairs": cfg["pairs"], "sha256_start": hashes,
            "expected_sha256": cfg.get("expected_sha256"), "thread_counters": cfg.get("thread_counters"),
            "mix": mix, "rounds": cfg["rounds"], "repetitions": cfg["repetitions"],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not dry_run:
        meta["lscpu_e"] = subprocess.run(["lscpu", "-e"], capture_output=True, text=True).stdout
        meta["lscpu_p"] = lscpu_p
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    steps = plan(cfg, mix)
    for n, (r, i, a) in enumerate(steps, 1):
        rc = cfg["runs"][i]
        tag = "r%02d-%s-%s-%s-%s" % (r, i, rc["binary"].replace("_benchmark", ""), rc["placement"], a)
        dst = os.path.join(out, tag + ".json")
        if os.path.exists(dst):
            continue  # resumable: a finished process is not run again
        env = dict(os.environ, **run_env(rc, mix))
        cmd = [binary_path(root, cfg["arms"][a], rc["binary"]), "--benchmark_filter=" + rc["filter"],
               "--benchmark_repetitions=%d" % int(cfg["repetitions"]),
               "--benchmark_format=json", "--benchmark_out=" + dst + ".tmp", "--benchmark_out_format=json"]
        if dry_run:
            log("%d/%d %s: %s %s" % (n, len(steps), tag, " ".join("%s=%s" % kv for kv in sorted(run_env(rc, mix).items())),
                                     " ".join(cmd)))
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
        if p.returncode == 0 and not rec.get("invalid"):
            try:
                with open(dst + ".tmp") as f:
                    probs = check_output(json.load(f), cfg, rc)
            except (OSError, ValueError) as ex:
                probs = ["no JSON output: %s" % ex]
            if probs:
                rec["invalid"] = "; ".join(probs[:4])
                with open(os.path.join(out, "runs.jsonl"), "a") as f:
                    f.write(json.dumps(dict(rec, checked=True, problems=probs)) + "\n")
        if p.returncode != 0 or rec.get("invalid"):
            log("%s FAILED: exit %s %s" % (tag, p.returncode, rec.get("invalid", "")))
            # the round's entry is re-run on the next start (no output file was kept)
            continue
        os.replace(dst + ".tmp", dst)
        log("%d/%d %s done in %.0f s" % (n, len(steps), tag, rec["seconds"]))
    if dry_run:
        return meta
    end = {k: sha256(binary_path(root, cfg["arms"][k.split("/")[0]], k.split("/")[1])) for k in hashes}
    meta["sha256_end"] = end
    meta["sha256_unchanged"] = end == hashes
    meta["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


# ---------------------------------------------------------------- table

UNIT = {"ns": 1.0, "us": 1e3, "ms": 1e6, "s": 1e9}


def parse_counters(out, names):
    """{(round, arm, benchmark): {counter: median or None}} of the per-thread counters (M4) the
    rebuilt benchmarks report, from the median aggregates; a negative value (the counter could
    not be opened, as on a VM without a PMU) is None (MB5)."""
    res = {}
    with open(os.path.join(out, "meta.json")) as f:
        arms = sorted(json.load(f)["arms"], key=len, reverse=True)
    for p in sorted(glob.glob(os.path.join(out, "r*.json"))):
        base = os.path.basename(p)[:-5]
        arm = next((a for a in arms if base.endswith("-" + a)), None)
        with open(p) as f:
            d = json.load(f)
        for b in d.get("benchmarks", []):
            if b.get("run_type") == "aggregate" and b.get("aggregate_name") == "median":
                c = {k: (None if float(b[v]) < 0 else float(b[v])) for k, v in (names or {}).items() if v in b}
                if c:
                    res[(int(base[1:3]), arm, norm_name(b["run_name"]))] = c
    return res


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
            rows.append((rnd, arm, pm.group(1) if pm else "-", norm_name(b["run_name"]),
                         float(b["real_time"]) * UNIT.get(b.get("time_unit", "ns"), 1.0)))
    return rows


def by_key(rows):
    out = {}
    for rnd, arm, pl, name, ns in rows:
        out.setdefault((name, pl), {}).setdefault(arm, {})[rnd] = ns
    return out


FLUSH_MODES = {0: "shared-hot", 1: "walk (memory traffic)", 2: "private-hot"}


def flush_rates(out):
    """[{arm, stats, hammers, mode, during, between, rounds}]: per round the flush benchmark's
    hammer_rate_during and hammer_rate_between over the hammer-only baseline's rate (same arm,
    stats, hammers, mode and round), median over rounds (MB4)."""
    with open(os.path.join(out, "meta.json")) as f:
        arms = sorted(json.load(f)["arms"], key=len, reverse=True)
    vals = {}
    for p in sorted(glob.glob(os.path.join(out, "r*.json"))):
        base = os.path.basename(p)[:-5]
        rnd, arm = int(base[1:3]), next((a for a in arms if base.endswith("-" + a)), None)
        with open(p) as f:
            d = json.load(f)
        for b in d.get("benchmarks", []):
            if b.get("run_type") != "aggregate" or b.get("aggregate_name") != "median" or b.get("error_occurred"):
                continue
            m = re.match(r"(bmFlushContended|bmHammerOnly)/(\d+)/(\d+)/(\d+)/", norm_name(b["run_name"]))
            if not m or int(m.group(3)) == 0:
                continue
            k = (arm, int(m.group(2)), int(m.group(3)), int(m.group(4)))
            vals.setdefault(k, {}).setdefault(rnd, {})[m.group(1)] = (b.get("hammer_rate_during"),
                                                                        b.get("hammer_rate_between"))
    rows = []
    for (arm, st, k, mode), per in sorted(vals.items()):
        dur, btw = [], []
        for r, v in per.items():
            ho = (v.get("bmHammerOnly") or (None,))[0]
            fl = v.get("bmFlushContended")
            if not ho or not fl:
                continue
            if fl[0] is not None:
                dur.append(float(fl[0]) / float(ho))
            if fl[1] is not None:
                btw.append(float(fl[1]) / float(ho))
        if dur or btw:
            rows.append({"arm": arm, "stats": st, "hammers": k, "mode": FLUSH_MODES.get(mode, str(mode)),
                         "during": stats.median(dur) if dur else None, "between": stats.median(btw) if btw else None,
                         "rounds": max(len(dur), len(btw))})
    return rows


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
    cnt = parse_counters(out, meta.get("thread_counters"))
    if cnt:
        L.append("## Per-thread counters per operation (M4; medians over rounds)\n")
        L.append("| Benchmark | Arm | Counter | Median per op |\n|---|---|---|---|")
        agg = {}
        for (r, arm, name), c in cnt.items():
            for k, v in c.items():
                agg.setdefault((name, arm, k), [])
                if v is not None:
                    agg[(name, arm, k)].append(v)
        js["counters"] = {"%s|%s|%s" % k: (stats.median(v) if v else None) for k, v in agg.items()}
        for (name, arm, k), v in sorted(agg.items()):
            L.append("| %s | %s | %s | %s |" % (name, arm, k, "%.2f" % stats.median(v) if v else "unavailable (no PMU)"))
        L.append("")
    fl = flush_rates(out)
    if fl:
        js["flush"] = fl
        L.append("## Hammer update rate during and between flushes, share of the hammer-only rate (M6)\n")
        L.append("Median over rounds. Private-hot is the mode that can show ordering; walk measures memory "
                 "traffic.\n")
        L.append("| Arm | Stats | Hammers | Mode | During / hammer-only | Between / hammer-only | Rounds |\n"
                 "|---|---|---|---|---|---|---|")
        for row in fl:
            L.append("| %s | %d | %d | %s | %s | %s | %d |" % (
                row["arm"], row["stats"], row["hammers"], row["mode"],
                "%.3f" % row["during"] if row["during"] is not None else "-",
                "%.3f" % row["between"] if row["between"] is not None else "-", row["rounds"]))
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
        hashes, probs = identity(cfg, root)
        for k, v in sorted(hashes.items()):
            print("%-48s %s" % (k, v or "MISSING"))
        for p in probs:
            print("PROBLEM " + p)
        print("identity %s" % ("OK" if not probs else "FAILED"))
        return 1 if probs else 0
    if not a.out:
        sys.exit("run needs OUT_DIR")
    mix = a.mix or cfg.get("mix")
    meta = run(cfg, a.out, root, mix, a.dry_run)
    return 0 if a.dry_run or meta.get("sha256_unchanged") else 1


if __name__ == "__main__":
    sys.exit(main())
