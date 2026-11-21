#!/usr/bin/env python3
"""Independent analysis of the Arm LSE vs LL/SC microbenchmark run (no new runs).

  python3 analyse.py [DATA_DIR [OUT_DIR]] > analysis.txt   (also writes OUT_DIR/analysis.json)

DATA_DIR: the experiment's directory (micro-lse/ with the per-process benchmark output, the
config the run used micro-lse.json.vm-local-floor25, and build-record.txt with the sha256 of
the four binaries); default data/stats/arm-lse-llsc. OUT_DIR: default DATA_DIR/analysis.

Gates: micro.check_output / micro.gate_problems of the runner in this repository (unchanged), with the
config the run used, plus an independent per-gate recount written here. Ratios: per round the
median over the 5 repetitions, then the paired log ratio llsc / lse over the 5 rounds with a
95% t interval (df 4), epl.stats.paired_log_ratio."""
import glob
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(WT, "examples", "stats-mt"))
sys.path.insert(0, WT)
import micro  # noqa: E402
from epl import stats  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WT, "data", "stats", "arm-lse-llsc")
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, "analysis")
os.makedirs(OUT_DIR, exist_ok=True)
D = os.path.join(BASE, "micro-lse")
cfg = json.load(open(os.path.join(BASE, "micro-lse.json.vm-local-floor25")))
meta = json.load(open(os.path.join(D, "meta.json")))
W = cfg["window_s"]
P = print
ARMS = ("fix-lse", "fix-llsc")


def med(x):
    return stats.median(list(x))


def fm(x):
    return "%.1f" % x if x < 100 else "{:,.0f}".format(x)


# ---- identity
pins = {}
for line in open(os.path.join(BASE, "build-record.txt")):
    m = re.match(r"([0-9a-f]{64})\s+964d72f7a6-(\w+)/(\S+)", line)
    if m:
        pins["fix-%s/%s" % (m.group(2), m.group(3))] = m.group(1)
ident_ok = len(pins) == 4 and len(set(pins.values())) == 4 and all(
    pins[k] == meta["sha256_start"][k] == meta["sha256_end"][k]
    == cfg["expected_sha256"][k.split("/")[0]][k.split("/")[1]] for k in pins)
P("IDENTITY build record == config pin == sha256_start == sha256_end, 4 distinct:", ident_ok)

# ---- gates
recs = {}
for line in open(os.path.join(D, "runs.jsonl")):
    r = json.loads(line)
    recs[r["tag"]] = r
files = sorted(glob.glob(os.path.join(D, "r*.json")))
GATES = ("error", "label", "overlap", "invol", "ops_floor", "pmu", "steal_ticks", "clocksource")
gate = {k: [0, 0] for k in GATES}
case_fail = {}
proc_fail = reps_ok = reps_bad = 0
rows, execs, loads = [], {}, []
worst = {"nonoverlap_ms": (0, None), "overlap_margin_ms": (9e9, None), "invol_per_thread": (0, None),
         "min_ops": (1e18, None)}
for p in files:
    tag = os.path.basename(p)[:-5]
    rnd, idx = int(tag[1:3]), int(tag.split("-")[1])
    arm = "fix-lse" if tag.endswith("fix-lse") else "fix-llsc"
    rc = cfg["runs"][idx]
    d = json.load(open(p))
    execs.setdefault(arm, set()).add(d["context"]["executable"])
    loads.append("%s=%.1f" % (tag[:3] + ("M" if idx == 0 else "S") + arm[4:], d["context"]["load_avg"][0]))
    rec = recs[tag]
    probs = micro.check_output(d, cfg, rc, arm)
    if rec["exit"] != 0 or rec["steal_share"] > cfg["steal_gate"] or rec["problems"]:
        probs.append("process")
    proc_fail += bool(probs)
    n_it = 0
    for b in d["benchmarks"]:
        if b["run_type"] != "iteration":
            continue
        n_it += 1
        nm = micro.norm_name(b["name"])
        th = b["threads"]
        bad_runner = bool(micro.gate_problems(b, cfg, rc, arm))
        reps_bad += bad_runner
        reps_ok += not bad_runner
        # independent recount, gate by gate
        batch = (b.get("min_batch_ops") or 256) * W / b["min_thread_ops"]
        lim = 0.002 + 0.005 * W + 3 * batch
        non = (1 - b["window_overlap"]) * W
        mine = {"error": bool(b.get("error_occurred")),
                "label": ("atomics=lse" if arm == "fix-lse" else "atomics=base") not in b["label"].split(),
                "overlap": non > lim,
                "invol": b["invol_switches"] < 0 or b["invol_switches"] > 25 * th,
                "ops_floor": b["min_thread_ops"] < 1024,
                "pmu": b["cycles_per_op"] < 0 or b["instructions_per_op"] < 0,
                "steal_ticks": b["steal_ticks"] != 0,
                "clocksource": b.get("clocksource_ok") != 1.0}
        for k, v in mine.items():
            gate[k][v] += 1
        assert bad_runner == any(mine[k] for k in ("error", "label", "overlap", "invol", "ops_floor", "pmu")), (tag, nm)
        if bad_runner:
            case_fail[(nm, arm)] = case_fail.get((nm, arm), 0) + 1
        if non * 1000 > worst["nonoverlap_ms"][0]:
            worst["nonoverlap_ms"] = (non * 1000, "%s %s, limit %.2f ms" % (tag, nm, lim * 1000))
        if (lim - non) * 1000 < worst["overlap_margin_ms"][0]:
            worst["overlap_margin_ms"] = ((lim - non) * 1000, "%s %s: %.3f ms outside, limit %.3f ms" % (
                tag, nm, non * 1000, lim * 1000))
        if b["invol_switches"] / th > worst["invol_per_thread"][0]:
            worst["invol_per_thread"] = (b["invol_switches"] / th, "%s %s (%d over %d threads, bound %d)" % (
                tag, nm, b["invol_switches"], th, 25 * th))
        if b["min_thread_ops"] < worst["min_ops"][0]:
            worst["min_ops"] = (b["min_thread_ops"], "%s %s" % (tag, nm))
        rows.append((rnd, arm, nm, b))
    assert n_it == 5 * len(rc["expect"]), tag
P("FILES %d; processes failing any gate: %d; repetitions valid %d, invalid %d; (case, arm) with an invalid repetition: %d"
  % (len(files), proc_fail, reps_ok, reps_bad, len(case_fail)))
for k in GATES:
    P("  gate %-12s pass %4d fail %d" % (k, gate[k][0], gate[k][1]))
for k, v in worst.items():
    P("  worst %-17s %.4f  %s" % (k, v[0], v[1]))
P("  process: exit!=0 %d, steal_share max %.4f, runner problems %d" % (
    sum(r["exit"] != 0 for r in recs.values()), max(r["steal_share"] for r in recs.values()),
    sum(bool(r["problems"]) for r in recs.values())))
P("  executables:", {a: sorted(v) for a, v in execs.items()})
P("  load1 at process start (M model, S stat):", " ".join(loads))
# sensitivity of the involuntary-switch gate (reported, not applied)
for bound in (5, 10, 15, 20, 25):
    P("  sensitivity: repetitions over %d switches per thread: %d" % (
        bound, sum(b["invol_switches"] > bound * b["threads"] for _, _, _, b in rows)))
for k in (0, 1, 2, 3):
    n = 0
    for _, _, _, b in rows:
        batch = (b.get("min_batch_ops") or 256) * W / b["min_thread_ops"]
        n += (1 - b["window_overlap"]) * W > 0.002 + 0.005 * W + k * batch
    P("  sensitivity: repetitions failing overlap with %d batches allowed: %d" % (k, n))

# ---- order
order = {}
for p in files:
    d = json.load(open(p))
    tag = os.path.basename(p)[:-5]
    order.setdefault((int(tag[1:3]), tag.split("-")[2]), []).append(
        (d["context"]["date"], "lse" if tag.endswith("-lse") else "llsc"))
first = {k: sorted(v)[0][1] for k, v in order.items()}
P("ARM ORDER (first arm per round, from the JSON start times):",
  {("r%d %s" % k): v for k, v in sorted(first.items())})
for k in order:
    assert first[k] == micro.arm_order(list(ARMS), k[0], cfg["order_seed"])[0][4:]

# ---- per-round medians
M = ("cycles_per_op", "instructions_per_op", "ns_per_op", "ops_per_sec", "fairness", "cycles_per_op_thread_mean",
     "min_thread_ops", "invol_switches", "min_batch_ops")
rep, per = {}, {}
for rnd, arm, nm, b in rows:
    for m in M:
        rep.setdefault((nm, arm, m, rnd), []).append(b[m])
for (nm, arm, m, rnd), v in rep.items():
    assert len(v) == 5
    per.setdefault((nm, arm, m), {})[rnd] = med(v)
names = sorted({r[2] for r in rows},
               key=lambda n: (0 if n.startswith("bmModel") else 1, n.split("/")[0], micro.threads_of(n)))


def verdict(lo_pct, hi_pct):
    if lo_pct <= 0 <= hi_pct:
        return "not resolved"
    if max(abs(lo_pct), abs(hi_pct)) < 1:
        return "resolved, under 1%: not a finding"
    if min(abs(lo_pct), abs(hi_pct)) < 1:
        return "sign resolved; interval reaches under 1%"
    return "resolved"


res = []
P("\nTABLE (pooled cycles/op; per-arm value = median over rounds of the round medians; ratio = exp(mean log), 95% t, df 4)")
P("| Case | Thr | LSE cyc/op | LL/SC cyc/op | LL/SC / LSE | 95% interval | per-round ratios | Verdict | LSE ns/op* | "
  "LL/SC ns/op* | instr/op LSE | instr/op LL/SC | fairness LSE | fairness LL/SC | LSE Mops/s | LL/SC Mops/s |")
P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for nm in names:
    th = micro.threads_of(nm)
    case = nm.split("/")[0]
    a, b = per[(nm, "fix-lse", "cycles_per_op")], per[(nm, "fix-llsc", "cycles_per_op")]
    rr = sorted(a)
    assert rr == sorted(b) == [1, 2, 3, 4, 5]
    p = stats.paired_log_ratio([a[r] for r in rr], [b[r] for r in rr])
    ratio, lo, hi = (math.exp(p[k] / 100) for k in ("log_mean_pct", "log_lo_pct", "log_hi_pct"))
    v = verdict(p["lo_pct"], p["hi_pct"])

    def g(arm, m):
        return med(per[(nm, arm, m)].values())
    nsl, nsb = th * 1e9 / g("fix-lse", "ops_per_sec"), th * 1e9 / g("fix-llsc", "ops_per_sec")
    row = dict(case=case, threads=th, lse=g("fix-lse", "cycles_per_op"), llsc=g("fix-llsc", "cycles_per_op"),
               ratio=ratio, lo=lo, hi=hi, per_round=[b[r] / a[r] for r in rr], verdict=v, sd_log_pct=p["log_sd_pct"],
               lse_round=[a[r] for r in rr], llsc_round=[b[r] for r in rr],
               ins_lse=g("fix-lse", "instructions_per_op"), ins_llsc=g("fix-llsc", "instructions_per_op"),
               fair_lse=g("fix-lse", "fairness"), fair_llsc=g("fix-llsc", "fairness"),
               ops_lse=g("fix-lse", "ops_per_sec"), ops_llsc=g("fix-llsc", "ops_per_sec"), ns_lse=nsl, ns_llsc=nsb,
               batch_lse=g("fix-lse", "min_batch_ops"), batch_llsc=g("fix-llsc", "min_batch_ops"),
               tm_lse=g("fix-lse", "cycles_per_op_thread_mean"), tm_llsc=g("fix-llsc", "cycles_per_op_thread_mean"))
    # time ratio from throughput (no PMU): lse / llsc throughput = llsc / lse time per op
    oa, ob = per[(nm, "fix-lse", "ops_per_sec")], per[(nm, "fix-llsc", "ops_per_sec")]
    q = stats.paired_log_ratio([ob[r] for r in rr], [oa[r] for r in rr])
    row.update(time_ratio=math.exp(q["log_mean_pct"] / 100), time_lo=math.exp(q["log_lo_pct"] / 100),
               time_hi=math.exp(q["log_hi_pct"] / 100))
    bin_ = "atomic_model" if case.startswith("bmModel") else "stat_update"
    lf = [math.log(b[r] / a[r]) for r in rr if first[(r, bin_)] == "llsc"]
    sf = [math.log(b[r] / a[r]) for r in rr if first[(r, bin_)] == "lse"]
    row["order_diff_pct"] = 100 * (sum(lf) / len(lf) - sum(sf) / len(sf))
    row["range_lse_pct"] = 100 * (max(a.values()) / min(a.values()) - 1)
    row["range_llsc_pct"] = 100 * (max(b.values()) / min(b.values()) - 1)
    # trend: round 5 against round 1
    row["r5_r1_lse_pct"] = 100 * (a[5] / a[1] - 1)
    row["r5_r1_llsc_pct"] = 100 * (b[5] / b[1] - 1)
    res.append(row)
    P("| %s | %d | %s | %s | %.3fx | [%.3f, %.3f] | %s | %s | %.2f | %.2f | %.1f | %.1f | %.2f | %.2f | %.1f | %.1f |" % (
        case, th, fm(row["lse"]), fm(row["llsc"]), ratio, lo, hi, " ".join("%.2f" % x for x in row["per_round"]), v,
        nsl, nsb, row["ins_lse"], row["ins_llsc"], row["fair_lse"], row["fair_llsc"], row["ops_lse"] / 1e6,
        row["ops_llsc"] / 1e6))
P("* ns/op pooled = threads x 1e9 / pooled ops per second")

P("\nCROSS-CHECK, ORDER, DRIFT")
P("| Case | Thr | cycles ratio | time ratio [95%] | order: llsc-first minus lse-first rounds, % | LSE range % | "
  "LL/SC range % | LSE r5/r1 % | LL/SC r5/r1 % | LSE per round | LL/SC per round | batch LSE/LLSC |")
P("|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in res:
    P("| %s | %d | %.3f | %.3f [%.3f, %.3f] | %+.2f | %.2f | %.2f | %+.2f | %+.2f | %s | %s | %g/%g |" % (
        r["case"], r["threads"], r["ratio"], r["time_ratio"], r["time_lo"], r["time_hi"], r["order_diff_pct"],
        r["range_lse_pct"], r["range_llsc_pct"], r["r5_r1_lse_pct"], r["r5_r1_llsc_pct"],
        " ".join("%.4g" % x for x in r["lse_round"]), " ".join("%.4g" % x for x in r["llsc_round"]),
        r["batch_lse"], r["batch_llsc"]))

P("\nSHARED / SPACED per arm (pooled cycles/op, paired by round)")
P("| Case | Thr | LSE shared/spaced [95%] | LL/SC shared/spaced [95%] |")
P("|---|---|---|---|")
h1 = []
for nm in names:
    if "Shared" not in nm:
        continue
    sp = nm.replace("Shared", "PerThreadSpaced")
    cells = []
    for arm in ARMS:
        a, b = per[(sp, arm, "cycles_per_op")], per[(nm, arm, "cycles_per_op")]
        rr = sorted(a)
        p = stats.paired_log_ratio([a[r] for r in rr], [b[r] for r in rr])
        cells.append(tuple(math.exp(p[k] / 100) for k in ("log_mean_pct", "log_lo_pct", "log_hi_pct")))
    h1.append(dict(case=nm.split("/")[0], threads=micro.threads_of(nm), lse=cells[0], llsc=cells[1]))
    P("| %s | %d | %.2fx [%.2f, %.2f] | %.2fx [%.2f, %.2f] |" % (
        (nm.split("/")[0], micro.threads_of(nm)) + cells[0] + cells[1]))

P("\nREPETITION SPREAD within a process, (max-min)/median of cycles/op over 5 reps: median and max over the 5 processes")
P("| Case | Thr | LSE med % | LSE max % | LL/SC med % | LL/SC max % |")
P("|---|---|---|---|---|---|")
for nm in names:
    c = []
    for arm in ARMS:
        s = [100 * (max(v) - min(v)) / med(v) for (n, a, m, r), v in rep.items()
             if n == nm and a == arm and m == "cycles_per_op"]
        c += [med(s), max(s)]
    P("| %s | %d | %.2f | %.2f | %.2f | %.2f |" % ((nm.split("/")[0], micro.threads_of(nm)) + tuple(c)))

json.dump({"identity_ok": ident_ok, "gate": gate, "reps_ok": reps_ok, "reps_bad": reps_bad, "proc_fail": proc_fail,
           "first_arm": {"r%d %s" % k: v for k, v in first.items()}, "cases": res, "shared_over_spaced": h1},
          open(os.path.join(OUT_DIR, "analysis.json"), "w"), indent=1)
