#!/usr/bin/env python3
"""POST-HOC re-evaluation of stored microbenchmark outputs under the current gates (no new runs).

    python3 examples/stats-mt/micro_reeval.py OUT_DIR --data NAME DATA_DIR CFG_JSON [--data ...]

DATA_DIR holds a micro run (meta.json, runs.jsonl, kept r*.json and rejected r*.json.tmp);
CFG_JSON is the micro.json it ran with (its run entries give the expected names and kinds, its
gate fields the gates at the time). Every process output is checked twice with check_output:
with the gates it ran under ("before") and with the current gates of make.py ("after"; only the
gate fields change). A process whose exit or steal failed at the time stays rejected. Per data
set: processes and repetitions accepted before and after, and the reasons left after; the
accepted-after outputs are copied to OUT_DIR/NAME/ with the run's meta.json and tabulated there
(micro.md, table.json). Every file written says POST-HOC.

Rationale: the benchmark reads the clock once per 256
operations, so a starved thread's window edges are only known to within one batch (1 to 18 ms
at 12 contended threads). Threads whose skew is within that granularity count as concurrent:
every thread runs at full load before and after its own window. The gate was sized for
sub-millisecond batches and rejected the contention it is meant to measure.
"""

import argparse
import glob
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make  # noqa: E402
import micro  # noqa: E402

LABEL = "POST-HOC re-evaluation under the second revision of the gates (no new runs)"
GATE_KEYS = ("ops_floor_per_s", "min_thread_ops_abs", "max_nonoverlap_s", "max_nonoverlap_share",
             "nonoverlap_batches", "ops_per_batch")
# the gates of 7f6a041..c0e3b5b, for configs that predate the fields
OLD_GATES = {"ops_floor_per_s": 20000, "min_thread_ops_abs": 1024, "max_nonoverlap_s": 0.002,
             "max_nonoverlap_share": 0.005, "nonoverlap_batches": 0, "ops_per_batch": 256}


def gates_of(cfg):
    return {k: cfg.get(k, OLD_GATES[k]) for k in GATE_KEYS}


def processes(data_dir):
    """{tag: (path, kept)}: the kept output where there is one, else the rejected one."""
    out = {}
    for p in sorted(glob.glob(os.path.join(data_dir, "r*.json.tmp"))):
        out[os.path.basename(p)[:-9]] = (p, False)
    for p in sorted(glob.glob(os.path.join(data_dir, "r*.json"))):
        out[os.path.basename(p)[:-5]] = (p, True)
    return out


def last_records(data_dir):
    recs = {}
    p = os.path.join(data_dir, "runs.jsonl")
    if os.path.exists(p):
        for line in open(p):
            r = json.loads(line)
            recs[r["tag"]] = r
    return recs


def run_problems(rec):
    """Problems of the process itself (exit, steal, missing JSON) that no gate change touches."""
    if rec is None:
        return []
    return [p for p in rec.get("problems", []) if p.startswith(("exit ", "steal ", "no JSON output"))]


def reps(d, cfg, rc):
    ok = bad = 0
    for b in d.get("benchmarks", []):
        if b.get("run_type") != "iteration":
            continue
        if micro.gate_problems(b, cfg, rc):
            bad += 1
        else:
            ok += 1
    return ok, bad


def evaluate(data_dir, cfg):
    before = dict(cfg, **gates_of(cfg))
    after = dict(cfg, **make.MICRO_GATES)
    recs = last_records(data_dir)
    rows, kept_after = [], []
    for tag, (path, kept) in sorted(processes(data_dir).items()):
        i = int(tag.split("-")[1])
        rc = cfg["runs"][i]
        with open(path) as f:
            d = json.load(f)
        fixed = run_problems(recs.get(tag))
        pb, pa = fixed + micro.check_output(d, before, rc), fixed + micro.check_output(d, after, rc)
        rb, ra = reps(d, before, rc), reps(d, after, rc)
        rows.append({"tag": tag, "kept_at_the_time": kept, "accepted_before": not pb, "accepted_after": not pa,
                     "reps_ok_before": rb[0], "reps_ok_after": ra[0], "reps": rb[0] + rb[1],
                     "problems_after": pa[:6]})
        if not pa:
            kept_after.append((tag, path))
    return rows, kept_after


def summary(rows):
    return {"processes": len(rows), "kept_at_the_time": sum(r["kept_at_the_time"] for r in rows),
            "accepted_before": sum(r["accepted_before"] for r in rows),
            "accepted_after": sum(r["accepted_after"] for r in rows),
            "repetitions": sum(r["reps"] for r in rows),
            "reps_ok_before": sum(r["reps_ok_before"] for r in rows),
            "reps_ok_after": sum(r["reps_ok_after"] for r in rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--data", nargs=3, action="append", metavar=("NAME", "DATA_DIR", "CFG_JSON"), required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    report = {"label": LABEL, "rationale": __doc__.split("Rationale")[1].strip(), "gates_after": make.MICRO_GATES,
              "sets": {}}
    L = ["# %s\n" % LABEL,
         "Rationale: a thread reads the clock once per 256 operations, so a starved thread's window edges are known only "
         "to within one batch; threads whose skew is within that granularity count as concurrent (every thread is at "
         "full load before and after its own window). New gates: time outside the common window at most 2 ms + 0.5% of "
         "the window + 3 batches of the slowest thread; slowest thread at least 1,024 operations. Nothing was re-run; "
         "the outputs are the ones on disk, checked with the gates they ran under (before) and with the new gates "
         "(after). Headline numbers in the per-set tables are pooled cycles per operation and pooled throughput.\n",
         "| Set | Processes | Kept at the time | Accepted before | Accepted after | Repetitions | Valid before | "
         "Valid after |", "|---|---|---|---|---|---|---|---|"]
    for name, data_dir, cfg_path in a.data:
        with open(cfg_path) as f:
            cfg = json.load(f)
        rows, kept = evaluate(data_dir, cfg)
        sm = summary(rows)
        left = {}
        for r in rows:
            for p in r["problems_after"]:
                th = micro.threads_of(p.split(": ", 1)[0])
                kind = "window overlap" if "outside the common window" in p else (
                    "too few valid repetitions" if "repetitions valid" in p else re.sub(r"[0-9.]+", "N", p.split(": ", 1)[-1])[:50])
                k = "%s at %s threads" % (kind, th)
                left[k] = left.get(k, 0) + 1
        report["sets"][name] = {"data_dir": data_dir, "config": cfg_path, "gates_before": gates_of(cfg),
                                "summary": sm, "processes": rows, "problems_after": left}
        L.append("| %s | %d | %d | %d | %d | %d | %d | %d |" % (
            name, sm["processes"], sm["kept_at_the_time"], sm["accepted_before"], sm["accepted_after"],
            sm["repetitions"], sm["reps_ok_before"], sm["reps_ok_after"]))
        d = os.path.join(a.out, name)
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
        meta = json.load(open(os.path.join(data_dir, "meta.json")))
        meta.update(post_hoc=LABEL, pairs=cfg.get("pairs", meta.get("pairs")))
        meta["config"] = "%s (POST-HOC)" % meta.get("config")
        with open(os.path.join(d, "meta.json"), "w") as f:
            json.dump(meta, f, indent=1)
        for tag, p in kept:
            shutil.copy(p, os.path.join(d, tag + ".json"))
        if kept:
            text, js = micro.table(d)
            with open(os.path.join(d, "micro.md"), "w") as f:
                f.write("> %s\n\n" % LABEL + text)
            with open(os.path.join(d, "table.json"), "w") as f:
                json.dump(dict(js, post_hoc=LABEL), f, indent=1)
    L.append("")
    for name, st in report["sets"].items():
        if st["problems_after"]:
            L.append("Left after, %s: %s" % (name, "; ".join("%d x %s" % (v, k) for k, v in
                                                            sorted(st["problems_after"].items(), key=lambda x: -x[1]))))
    L.append("")
    with open(os.path.join(a.out, "reeval.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(a.out, "reeval.json"), "w") as f:
        json.dump(report, f, indent=1)
    sys.stdout.write("\n".join(L) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
