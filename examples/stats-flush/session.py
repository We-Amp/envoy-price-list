#!/usr/bin/env python3
"""Helpers of run-session.sh (stats-flush row).

    python3 session.py rungs OUT CAL_DIR...         merge stats-calibrate rungs.json files into OUT
    python3 session.py statsd-interval RUNGS SMOKE_DIR...   per rung: 1 s, or 5 s when the
                                                    smoke's statsd drops reached 1% at 1 s
    python3 session.py budget CFG_DIR SMOKE_ROOT    seconds per leg per rung from the smoke;
                                                    expected time per run; exit 3 when the
                                                    mandatory part is above 2 h 30 min
    python3 session.py expected RUN CFG_DIR SMOKE_ROOT   expected seconds of one run
    python3 session.py predict-w M100K_DIR [W_SMOKE_DIR]  the run-W prediction: the nosink
                                                    flush's share of the loaded cycles at 5 s;
                                                    confirmatory only at 1% or more
    python3 session.py calibrated CFG_DIR           exit 1 when a queued config is uncalibrated
"""

import glob
import json
import os
import sys

MANDATORY = ["m-10k", "m-100k", "m-1m", "w", "m-300k"]
OPTIONAL = ["s-100k", "s-1m", "x-1m"]  # run in this order; the cut order drops them from the end
ASK_LEAD_ABOVE_S = 2.5 * 3600
STOP_S = 3.25 * 3600
SMOKE_OF = {"m-10k": "smoke-m-10k", "m-100k": "smoke-100k", "m-1m": "smoke-1m", "m-300k": "smoke-m-300k",
            "w": "smoke-w", "s-100k": "smoke-100k", "s-1m": "smoke-1m", "x-1m": "smoke-1m"}
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
            if share is None:
                continue
            r = rungs.setdefault(rung, {})
            r["statsd_drop_share_smoke"] = share
            r["statsd_interval_s"] = 5 if share >= 0.01 else 1
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
