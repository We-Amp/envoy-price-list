#!/usr/bin/env python3
"""Helpers of run-session.sh (stats-flush row).

    python3 session.py rungs OUT CAL_DIR...         merge stats-calibrate rungs.json files into OUT
    python3 session.py statsd-interval RUNGS SMOKE_DIR...   per rung: 1 s, or 5 s when the
                                                    smoke's statsd drops reached 1% at 1 s or
                                                    its main thread was saturated (never lowered)
    python3 session.py budget CFG_DIR SMOKE_ROOT    seconds per leg per rung from the smoke;
                                                    expected time per run; exit 3 when the
                                                    mandatory part is above 2 h 30 min
    python3 session.py expected RUN CFG_DIR SMOKE_ROOT   expected seconds of one run
    python3 session.py predict-w M100K_DIR [W_SMOKE_DIR]  the run-W prediction: the nosink
                                                    flush's share of the loaded cycles at 5 s;
                                                    confirmatory only at 1% or more
    python3 session.py calibrated CFG_DIR           exit 1 when a queued config is uncalibrated
    python3 session.py merge-smoke OUT ORIG NEW ARM  a smoke directory for the check: ORIG's
                                                    legs and config dumps with ARM's taken from
                                                    NEW (the 5 s statsd fallback's own smoke)
"""

import glob
import json
import os
import sys

MANDATORY = ["m-10k", "m-100k", "m-1m", "w", "m-300k"]
OPTIONAL = ["x-1m"]  # run S has its own steps (run-session.sh s-smoke, s-queue)
ASK_LEAD_ABOVE_S = 2.5 * 3600
STOP_S = 3.25 * 3600
SMOKE_OF = {"mfix-10k": "smoke-mfix-10k", "mfix-100k": "smoke-mfix-100k", "mfix-1m": "smoke-mfix-1m",
            "m-10k": "smoke-m-10k", "m-100k": "smoke-100k", "m-1m": "smoke-1m", "m-300k": "smoke-m-300k",
            "w": "smoke-w", "s-100k": "smoke-s-100k", "s-1m": "smoke-s-1m", "sw": "smoke-sw", "x-1m": "smoke-1m"}
DEFAULT_LOADED_CYCLES_PER_REQ = 270e3
W_RPS = 5200
W_INTERVAL_S = 5.0


def legs(path):
    with open(path) as f:
        return [json.loads(x) for x in f if x.strip() and '"leg_id"' in x]


def seconds_per_leg(run_dir):
    """Mean seconds from one leg's start to the next in a run directory (needs two legs)."""
    import time
    p = os.path.join(run_dir, "legs.jsonl")
    if not os.path.exists(p):
        return None
    ts = sorted(time.mktime(time.strptime(m["started_utc"], "%Y-%m-%dT%H:%M:%SZ")) for m in legs(p)
                if m.get("started_utc"))
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    return sum(gaps) / len(gaps) if gaps else None


def legs_of(cfg_path):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    from epl import experiment
    exp = experiment.load(cfg_path)
    return len(experiment.schedule(exp, 1, exp["rounds"]))


def expected(run, cfg_dir, smoke_root):
    spl = seconds_per_leg(os.path.join(smoke_root, SMOKE_OF[run]))
    if spl is None:
        return None
    return legs_of(os.path.join(cfg_dir, run + ".json")) * spl


def budget(cfg_dir, smoke_root, out=sys.stdout):
    exp = {}
    for r in MANDATORY + OPTIONAL:
        exp[r] = expected(r, cfg_dir, smoke_root)
        out.write("%-8s expected %s%s\n" % (r, "-" if exp[r] is None else "%5.1f min" % (exp[r] / 60),
                                          "  (optional)" if r in OPTIONAL else ""))
    if any(exp[r] is None for r in MANDATORY):
        out.write("no seconds per leg for some mandatory run: run the smoke first\n")
        return None, exp
    mand = sum(exp[r] for r in MANDATORY)
    out.write("mandatory %.2f h (a decision is needed above %.2f h); with every optional run %.2f h; stop at %.2f h\n" % (
        mand / 3600, ASK_LEAD_ABOVE_S / 3600, (mand + sum(exp[r] or 0 for r in OPTIONAL)) / 3600, STOP_S / 3600))
    return mand, exp


S_RUNS = ["s-100k", "s-1m", "sw"]


def s_budget(cfg_dir, smoke_root, stop_s, out=sys.stdout):
    """Expected run time of run S from its smokes' seconds per leg, against the stop."""
    tot = 0.0
    for r in S_RUNS:
        e = expected(r, cfg_dir, smoke_root)
        out.write("%-8s expected %s\n" % (r, "-" if e is None else "%5.1f min" % (e / 60)))
        if e is None:
            out.write("no seconds per leg for %s: run the S smoke first\n" % r)
            return None
        tot += e
    out.write("run S expected %.2f h; stop at %.2f h\n" % (tot / 3600, stop_s / 3600))
    return tot


def smoke_problems(cfg_path, smoke_dir):
    """[problem]: a smoke leg missing or invalid (the latest attempt of each shape, arm, round)."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    from epl import experiment
    exp = experiment.load(cfg_path)
    latest = {}
    for m in legs(os.path.join(smoke_dir, "legs.jsonl")):
        if m.get("arm"):
            latest[(m.get("shape"), m.get("arm"), m.get("round"))] = m
    probs = []
    for sh in exp["shapes"]:
        for a in exp["arms"]:
            got = [m for (s_, ar, r), m in latest.items() if s_ == sh["name"] and ar == a["name"]]
            if not got:
                probs.append("missing: %s %s" % (sh["name"], a["name"]))
            for m in got:
                v = m.get("verdict") or {}
                if not v.get("valid"):
                    probs.append("invalid: %s %s: %s" % (sh["name"], a["name"], "; ".join(v.get("reasons") or [])))
    return probs


def merge_rungs(out_path, cal_dirs):
    merged = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            merged = json.load(f)
    for d in cal_dirs:
        p = os.path.join(d, "rungs.json")
        if not os.path.exists(p):
            continue
        with open(p) as f:
            for shape, v in json.load(f).items():
                rung = shape.split("idle-", 1)[-1]
                cur = merged.setdefault(rung, {})
                # the largest timeouts and settle any arm needed; counts from the nosink arm
                for k in ("ready_timeout_s", "admin_timeout_s", "settle_s"):
                    if v.get(k) is not None:
                        cur[k] = max(cur.get(k, 0), v[k])
                for k in ("stats_total", "used_total", "used_cg_lines"):
                    if v.get(k) is not None and k not in cur:
                        cur[k] = v[k]
    with open(out_path, "w") as f:
        json.dump(merged, f, indent=1, sort_keys=True)
    return merged


def statsd_interval(rungs_path, smoke_dirs):
    """Per rung, the drop share of the smoke's statsd legs: at 1% or more the rung's statsd
    arm runs at 5 s (the fallback of the plan); the decision is written into rungs.json."""
    with open(rungs_path) as f:
        rungs = json.load(f)
    for d in smoke_dirs:
        p = os.path.join(d, "legs.jsonl")
        if not os.path.exists(p):
            continue
        for m in legs(p):
            if m.get("arm") != "statsd" or not m.get("shape", "").startswith("idle-"):
                continue
            rung = m["shape"].split("idle-", 1)[1]
            share = (m.get("udp") or {}).get("drop_share")
            sat = ((m.get("main") or {}).get("run_ms_per_s") or 0) >= 900.0
            if share is None:
                continue
            r = rungs.setdefault(rung, {})
            r["statsd_drop_share_smoke"] = share
            r["statsd_main_saturated_smoke"] = sat
            # drops of 1% or more, or a main thread busy all the time (flushes longer than the
            # interval), move the rung's statsd to 5 s; a decision is never lowered again
            want = 5 if (share >= 0.01 or sat) else 1
            r["statsd_interval_s"] = max(r.get("statsd_interval_s", 1), want)
    with open(rungs_path, "w") as f:
        json.dump(rungs, f, indent=1, sort_keys=True)
    return rungs


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def predict_w(m100k_dir, w_smoke_dir=None):
    """Expected effect of the nosink flush on run W's cycles per request: the flush's main
    thread cycles per second at 5 s (from run M at 100k: nosink minus flush-off, per second at
    a 1 s interval is per flush), over the loaded process's cycles per second."""
    with open(os.path.join(m100k_dir, "results.json")) as f:
        res = json.load(f)
    by = {}
    for m in res["legs"]:
        if m.get("superseded") or not (m.get("verdict") or {}).get("valid"):
            continue
        by.setdefault(m["arm"], []).append((m.get("main_perf") or {}).get("cycles_per_s"))
    ns, off = mean(by.get("nosink", [])), mean(by.get("flush-off", []))
    if ns is None or off is None:
        return {"error": "no valid nosink and flush-off legs in %s" % m100k_dir}
    per_flush = ns - off  # 1 s interval: one flush per second
    cpr = DEFAULT_LOADED_CYCLES_PER_REQ
    src = "default"
    if w_smoke_dir and os.path.exists(os.path.join(w_smoke_dir, "legs.jsonl")):
        x = mean([(m.get("per_req") or {}).get("cycles_total") for m in legs(os.path.join(w_smoke_dir, "legs.jsonl"))
                  if m.get("arm") == "flush-off"])
        if x:
            cpr, src = x, "run W smoke"
    pct = 100.0 * (per_flush / W_INTERVAL_S) / (W_RPS * cpr)
    return {"cycles_per_flush_100k": per_flush, "loaded_cycles_per_req": cpr, "loaded_cycles_from": src,
            "predicted_effect_pct": pct, "nosink_row": "confirmatory" if pct >= 1.0 else "secondary"}


def uncalibrated(cfg_dir):
    bad = []
    for p in sorted(glob.glob(os.path.join(cfg_dir, "*.json"))):
        name = os.path.basename(p)[:-5]
        if name in MANDATORY + OPTIONAL:
            with open(p) as f:
                if json.load(f).get("uncalibrated"):
                    bad.append(name)
    return bad


def merge_smoke(out, orig, new, arm):
    import shutil
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "config_dump"))
    lines = []
    for src, keep in ((orig, lambda a: a != arm), (new, lambda a: a == arm)):
        p = os.path.join(src, "legs.jsonl")
        if not os.path.exists(p):
            raise SystemExit("no legs in %s" % src)
        with open(p) as f:
            for x in f:
                if not x.strip():
                    continue
                m = json.loads(x)
                if "leg_id" in m and keep(m.get("arm")):
                    lines.append(json.dumps(m))
        d = os.path.join(src, "config_dump")
        for fn in os.listdir(d) if os.path.isdir(d) else []:
            if keep(fn.split(".json")[0]):
                shutil.copy(os.path.join(d, fn), os.path.join(out, "config_dump", fn))
    with open(os.path.join(out, "legs.jsonl"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return len(lines)


def main(argv):
    cmd = argv[0]
    if cmd == "rungs":
        print(json.dumps(merge_rungs(argv[1], argv[2:]), indent=1, sort_keys=True))
        return 0
    if cmd == "statsd-interval":
        print(json.dumps(statsd_interval(argv[1], argv[2:]), indent=1, sort_keys=True))
        return 0
    if cmd == "budget":
        mand, _ = budget(argv[1], argv[2])
        if mand is None:
            return 1
        return 3 if mand > ASK_LEAD_ABOVE_S else 0
    if cmd == "expected":
        e = expected(argv[1], argv[2], argv[3])
        print(int(e) if e is not None else 999999)
        return 0
    if cmd == "predict-w":
        r = predict_w(argv[1], argv[2] if len(argv) > 2 else None)
        print(json.dumps(r, indent=1))
        return 1 if "error" in r else 0
    if cmd == "merge-smoke":
        print("%d legs in %s" % (merge_smoke(argv[1], argv[2], argv[3], argv[4]), argv[1]))
        return 0
    if cmd == "smoke-valid":
        probs = smoke_problems(argv[1], argv[2])
        for p in probs:
            print(p)
        print("smoke %s: %s" % (argv[2], "all legs valid" if not probs else "NOT clean (%d problems)" % len(probs)))
        return 1 if probs else 0
    if cmd == "s-budget":
        t = s_budget(argv[1], argv[2], float(argv[3]))
        if t is None:
            return 1
        return 3 if t > float(argv[3]) else 0
    if cmd == "calibrated":
        bad = uncalibrated(argv[1])
        if bad:
            print("uncalibrated: %s (run the calibrate step and make.py --rungs)" % ", ".join(bad))
            return 1
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
