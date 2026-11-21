#!/usr/bin/env python3
"""Microbenchmarks, round 5: figures quoted beside the tables of micro.py, from the per-process
benchmark output.

    python3 examples/stats-mt/analysis-micro/extras.py [MICRO_DIR [U_DIR [CODEGEN_DIR]]] > extras.txt

MICRO_DIR: data/stats/microbenchmarks (bench-x86_64/micro, x86-vm/micro, arm-vm/micro-r5,
arm-vm-b/micro-r5b). U_DIR (data/stats/multi-worker) and CODEGEN_DIR (data/stats/arm-codegen) give
section 5 its cycles per request; without them their rows say so.

Estimator, everywhere: per process (one round of one arm) the median over its repetitions; a
"level" is the mean of those round medians unless a line says median. A ratio is the paired log
ratio over the rounds with a 95% t interval, printed as a percentage. Only processes the runner
accepted are read (r*.json), except where a line says "descriptive", which also reads the
outputs of rejected processes (r*.json.tmp).

1. Histogram sample, record only: cycles per sample (micro.py prints this row in ns per sample).
2. Instructions per operation of a counter increment, per arm.
3. The model counter on the bare-metal server: cycles per operation, spaced and shared.
4. Relaxed against current ordering on the shared model counter at 4 threads, x86 VM against
   Arm VM: difference of the two mean log ratios with a Welch interval (unpaired: two machines).
5. The end-to-end model: cycles saved per operation x operations per request / cycles per
   request. A prediction by arithmetic, not a measurement.
"""
import collections
import glob
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)
from epl import stats  # noqa: E402

# counter increments per request used for the first prediction: a proxy from an instruction
# profile of the x86 proxy, taken before the increments were counted. It is not in the data. The
# counted figure is read from the codegen run's pre-run check.
PROXY_INCREMENTS = 12.6
SETS = [("server", "bench-x86_64/micro"), ("x86 VM", "x86-vm/micro"), ("Arm VM", "arm-vm/micro-r5"),
        ("Arm VM, second set", "arm-vm-b/micro-r5b")]


def load(d, binary, arm, rejected=False):
    """{round: {benchmark name: {metric: [value per repetition]}}} of one binary and arm."""
    out = {}
    files = glob.glob(os.path.join(d, "r*-%s-*-%s.json" % (binary, arm)))
    if rejected:
        files += glob.glob(os.path.join(d, "r*-%s-*-%s.json.tmp" % (binary, arm)))
    for f in sorted(files):
        m = re.match(r"r(\d+)-\d+-%s-(.+)-%s\.json" % (binary, re.escape(arm)), os.path.basename(f))
        if not m:
            continue
        with open(f) as fh:
            doc = json.load(fh)
        for b in doc["benchmarks"]:
            if b.get("run_type") != "iteration":
                continue
            name = re.sub(r"/min_time:[\d.]+|/min_warmup_time:[\d.]+|/iterations:\d+", "", b["name"])
            o = out.setdefault(int(m.group(1)), {}).setdefault(name, collections.defaultdict(list))
            for k, v in b.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    o[k].append(v)
    return out


def round_medians(data, name, metric):
    return {r: stats.median(v[name][metric]) for r, v in sorted(data.items()) if name in v and v[name].get(metric)}


def level(data, name, metric):
    m = round_medians(data, name, metric)
    return stats.mean(list(m.values())) if m else None


def t_interval(xs):
    """(n, mean, low, high) with a 95% t interval."""
    n, m = len(xs), stats.mean(xs)
    hw = stats.t_ppf(0.975, n - 1) * stats.stdev(xs) / math.sqrt(n)
    return n, m, m - hw, m + hw


def pct(x):
    return 100.0 * (math.exp(x / 100.0) - 1.0)


def paired_ratio(ref, arm):
    """arm against ref, {round: value} each: (n, effect %, low %, high %) or None under 2 pairs."""
    rs = sorted(set(ref) & set(arm))
    if len(rs) < 2:
        return None
    n, m, lo, hi = t_interval([100.0 * math.log(arm[r] / ref[r]) for r in rs])
    return n, pct(m), pct(lo), pct(hi)


def welch(x, y):
    """mean(x) - mean(y) with a 95% Welch interval: (difference, low, high, degrees of freedom)."""
    vx, vy = stats.stdev(x) ** 2 / len(x), stats.stdev(y) ** 2 / len(y)
    df = (vx + vy) ** 2 / (vx ** 2 / (len(x) - 1) + vy ** 2 / (len(y) - 1))
    d, hw = stats.mean(x) - stats.mean(y), stats.t_ppf(0.975, df) * math.sqrt(vx + vy)
    return d, d - hw, d + hw, df


def model_pct(saved_per_op, ops_per_request, cycles_per_request):
    """Predicted share of the cycles per request, in percent."""
    return 100.0 * saved_per_op * ops_per_request / cycles_per_request


def threads_of(name):
    """Threads of a benchmark name: .../threads:N, or the worker count of bmHistogramRecordOnly/N/..."""
    m = re.search(r"threads:(\d+)$", name) or re.match(r"bmHistogramRecord(?:Only)?/(\d+)/", name)
    return int(m.group(1))


def names(data, pattern):
    return sorted({n for v in data.values() for n in v if re.search(pattern, n)}, key=lambda n: (n.split("/")[0], threads_of(n)))


def section_histogram(M, P):
    P("1. Histogram sample, record only: cycles per sample, fix-relaxed against fix")
    for label, sub in SETS[1:3]:
        d = os.path.join(M, sub)
        fx, rl = load(d, "histogram_record", "fix"), load(d, "histogram_record", "fix-relaxed")
        for n in names(fx, r"^bmHistogramRecordOnly/"):
            a, b = round_medians(fx, n, "cycles_per_sample"), round_medians(rl, n, "cycles_per_sample")
            r = paired_ratio(a, b)
            if r is None:
                P("   %-7s %2d worker(s): fewer than 2 accepted rounds in both arms, no row" % (label, threads_of(n)))
                continue
            P("   %-7s %2d worker(s): %.1f to %.1f cycles per sample; %+.1f%% [%+.1f, %+.1f]  (%+.2f%% [%+.2f, %+.2f], %d rounds)" % (
                label, threads_of(n), stats.mean(list(a.values())), stats.mean(list(b.values())), r[1], r[2], r[3],
                r[1], r[2], r[3], r[0]))


def section_instructions(M, P):
    P("\n2. Counter increment: instructions per operation (level; the same value in every round)")
    for label, sub in SETS[1:]:
        d = os.path.join(M, sub)
        for arm in ("fix", "fix-relaxed", "fix-relaxed-p1"):
            su, desc = load(d, "stat_update", arm), ""
            if not su:
                su, desc = load(d, "stat_update", arm, rejected=True), "  (descriptive: rejected processes)"
            row = []
            for n in names(su, r"^bmCounterInc(PerThreadSpaced|Shared)/manual_time/threads:1$"):
                v = level(su, n, "instructions_per_op")
                row.append("%s %.2f" % ("spaced" if "Spaced" in n else "shared", v))
            if row:
                P("   %-18s %-14s 1 thread: %s%s" % (label, arm, ", ".join(row), desc))


def section_server_model(M, P):
    P("\n3. Model counter with the current ordering, bare-metal server: cycles per operation")
    am = load(os.path.join(M, SETS[0][1]), "atomic_model", "fix")
    for n in names(am, r"^bmModelCurrent(PerThreadSpaced|Shared)/manual_time/threads:\d+$"):
        m = list(round_medians(am, n, "cycles_per_op").values())
        P("   %-6s %2d thread(s): median over the %d rounds %s, mean %s  (%.1f / %.1f)" % (
            "spaced" if "Spaced" in n else "shared", threads_of(n), len(m), "{:,.0f}".format(stats.median(m))
            if stats.median(m) >= 100 else "%.1f" % stats.median(m),
            "{:,.0f}".format(stats.mean(m)) if stats.mean(m) >= 100 else "%.1f" % stats.mean(m), stats.median(m),
            stats.mean(m)))
    sp = round_medians(am, "bmModelCurrentPerThreadSpaced/manual_time/threads:1", "cycles_per_op")
    for th in (4, 19):
        sh = round_medians(am, "bmModelCurrentShared/manual_time/threads:%d" % th, "cycles_per_op")
        rs = sorted(set(sp) & set(sh))
        if len(rs) >= 2:
            n, m, lo, hi = t_interval([math.log(sh[r] / sp[r]) for r in rs])
            P("   shared at %d over spaced at 1, paired log ratio over the rounds: %.2f [%.2f, %.2f] times. This is a mean over "
              "rounds; the median level above over the spaced level is %.2f times" % (
                  th, math.exp(m), math.exp(lo), math.exp(hi), stats.median(list(sh.values())) / stats.mean(list(sp.values()))))


def ordering_log_ratios(d, threads):
    am = load(d, "atomic_model", "fix")
    cur = round_medians(am, "bmModelCurrentShared/manual_time/threads:%d" % threads, "cycles_per_op")
    rel = round_medians(am, "bmModelRelaxedShared/manual_time/threads:%d" % threads, "cycles_per_op")
    return [100.0 * math.log(rel[r] / cur[r]) for r in sorted(set(cur) & set(rel))]


def section_cross_machine(M, P):
    P("\n4. Relaxed against current ordering, shared model counter, 4 threads: x86 VM minus Arm VM, log-percent")
    x = ordering_log_ratios(os.path.join(M, SETS[1][1]), 4)
    P("   x86 VM: mean log ratio %+.2f over %d rounds" % (stats.mean(x), len(x)))
    for label, sub in SETS[2:]:
        a = ordering_log_ratios(os.path.join(M, sub), 4)
        if len(a) < 2:
            P("   %s: fewer than 2 accepted rounds" % label)
            continue
        d, lo, hi, df = welch(x, a)
        P("   %-18s mean log ratio %+.2f over %d rounds; x86 minus Arm: %+.2f [%+.2f, %+.2f] (Welch, %.1f degrees of freedom)" % (
            label + ":", stats.mean(a), len(a), d, lo, hi, df))


def u_base_cycles(u_dir):
    """Mean worker-only cycles per request of run U's base arm at 28 workers (valid, current legs)."""
    with open(os.path.join(u_dir, "u", "results.json")) as f:
        legs = json.load(f)["legs"]
    return stats.mean([m["workers_cycles_per_req"] for m in legs if m["verdict"]["valid"] and not m.get("superseded")
                       and m["shape"] == "mt-28w" and m["arm"] == "base"])


def codegen_inputs(cg_dir):
    """(mean worker-only cycles per request of the release at 12 workers, counted counter
    increments per request: the mean of the pre-run check's four figures, both builds at 4 and
    12 workers)."""
    with open(os.path.join(cg_dir, "arm-vm", "codegen", "results.json")) as f:
        legs = json.load(f)["legs"]
    cyc = stats.mean([m["workers_cycles_per_req"] for m in legs if m["verdict"]["valid"] and not m.get("superseded")
                      and m["shape"] == "mt-12w" and m["arm"] == "official"])
    incs = []
    with open(os.path.join(cg_dir, "arm-vm", "codegen-smoke.out")) as f:
        for ln in f:
            m = re.match(r"mt-\d+w\s+\S+\s+counter incs/req ([\d.]+)", ln)
            if m:
                incs.append(float(m.group(1)))
    return cyc, (stats.mean(incs) if incs else None)


def diff_level(d, binary, arm_a, name_a, arm_b, name_b, metric="cycles_per_op", how="mean", rejected=False):
    a = list(round_medians(load(d, binary, arm_a, rejected), name_a, metric).values())
    b = list(round_medians(load(d, binary, arm_b, rejected), name_b, metric).values())
    f = stats.median if how == "median" else stats.mean
    return f(a) - f(b)


def section_model(M, u_dir, cg_dir, P):
    P("\n5. End-to-end model (a prediction by arithmetic): saved cycles per operation x operations per request / cycles per request")
    xcyc = u_base_cycles(u_dir) if u_dir and os.path.exists(os.path.join(u_dir, "u", "results.json")) else None
    acyc, counted = (codegen_inputs(cg_dir) if cg_dir and os.path.exists(os.path.join(cg_dir, "arm-vm", "codegen", "results.json"))
                     else (None, None))
    P("   inputs: %.1f counter increments per request (a proxy from a profile, not in the data)%s" % (
        PROXY_INCREMENTS, "" if counted is None else "; %.2f counted on the Arm VM in the codegen run's pre-run check" % counted))
    P("   inputs: cycles per request, worker threads only: x86 %s (run U, base, 28 workers); Arm VM %s (codegen run, release, 12 workers)" % (
        "not available (needs data/stats/multi-worker)" if xcyc is None else "%.1fk" % (xcyc / 1e3),
        "not available (needs data/stats/arm-codegen)" if acyc is None else "%.1fk" % (acyc / 1e3)))

    def row(label, what, saved, ops, cyc):
        saved = max(0.0, saved)  # a difference below zero is noise around "nothing saved"
        if cyc is None:
            P("   %-52s %s: %.1f cycles x %.2f; cycles per request not available" % (label, what, saved, ops))
        else:
            v = model_pct(saved, ops, cyc)
            P("   %-52s %s: %.1f cycles x %.2f = %.0f cycles, %.3f%% (%.2f%%) of the cycles per request" % (
                label, what, saved, ops, saved * ops, v, v))

    b, x, a = (os.path.join(M, SETS[0][1]), os.path.join(M, SETS[1][1]), os.path.join(M, SETS[3][1]))
    sp1, sh = "PerThreadSpaced/manual_time/threads:1", "Shared/manual_time/threads:%d"
    P("   test the used flag before setting it (fix-relaxed-p1 against fix-relaxed; model: RelaxedTestFlag against Relaxed), 1 thread, spaced:")
    row("server, model counter", "saved", diff_level(b, "atomic_model", "fix", "bmModelRelaxed" + sp1, "fix", "bmModelRelaxedTestFlag" + sp1),
        PROXY_INCREMENTS, xcyc)
    row("x86 VM, real counter", "saved", diff_level(x, "stat_update", "fix-relaxed", "bmCounterInc" + sp1, "fix-relaxed-p1", "bmCounterInc" + sp1),
        PROXY_INCREMENTS, xcyc)
    am = diff_level(a, "atomic_model", "fix", "bmModelRelaxed" + sp1, "fix", "bmModelRelaxedTestFlag" + sp1)
    row("Arm VM (second set), model counter", "saved", am, PROXY_INCREMENTS, acyc)
    if counted is not None:
        row("Arm VM (second set), model counter, counted increments", "saved", am, counted, acyc)
        row("Arm VM (second set), real counter, descriptive", "saved",
            diff_level(a, "stat_update", "fix-relaxed", "bmCounterInc" + sp1, "fix-relaxed-p1", "bmCounterInc" + sp1, rejected=True),
            counted, acyc)
    P("   relaxed ordering (model: Relaxed against Current; real counter: fix-relaxed against fix):")
    row("server, model counter, 1 thread, spaced", "saved",
        diff_level(b, "atomic_model", "fix", "bmModelCurrent" + sp1, "fix", "bmModelRelaxed" + sp1), PROXY_INCREMENTS, xcyc)
    row("server, model counter, shared by 19 (the most it can be)", "saved, median levels",
        diff_level(b, "atomic_model", "fix", "bmModelCurrent" + sh % 19, "fix", "bmModelRelaxed" + sh % 19, how="median"),
        PROXY_INCREMENTS, xcyc)
    fx = round_medians(load(x, "stat_update", "fix"), "bmCounterInc" + sp1, "cycles_per_op")
    rl = round_medians(load(x, "stat_update", "fix-relaxed"), "bmCounterInc" + sp1, "cycles_per_op")
    rs = sorted(set(fx) & set(rl))
    n, m, lo, hi = t_interval([fx[r] - rl[r] for r in rs])
    row("x86 VM, real counter, 1 thread, spaced, interval edge", "saved at most", max(abs(lo), abs(hi)), PROXY_INCREMENTS, xcyc)
    row("Arm VM (second set), model counter, 1 thread, spaced", "saved",
        max(0.0, diff_level(a, "atomic_model", "fix", "bmModelCurrent" + sp1, "fix", "bmModelRelaxed" + sp1)),
        counted if counted is not None else PROXY_INCREMENTS, acyc)


def main():
    M = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "data", "stats", "microbenchmarks")
    u_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(M, "..", "multi-worker")
    cg_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(M, "..", "arm-codegen")
    P = print
    section_histogram(M, P)
    section_instructions(M, P)
    section_server_model(M, P)
    section_cross_machine(M, P)
    section_model(M, u_dir, cg_dir, P)


if __name__ == "__main__":
    main()
