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
    python3 session.py lat-rules CFG SMOKE_DIR      run L: the smoke rules S-3 to S-9 on the smoke's
                                                    legs and the budget from its seconds per leg
    python3 session.py lat-smoke-stamp SMOKE_CFG SMOKE_DIR   lat-smoke, before its run: the hash of the
                                                    harness sources and of smoke-lat.json, in the smoke dir
    python3 session.py lat-smoke-stamp-ok CFG SMOKE_CFG SMOKE_DIR   exit 0 only when the smoke dir was
                                                    written with these sources and this smoke-lat.json,
                                                    and CFG differs from it only in name and rounds
    python3 session.py lat-stamp CFG STAMP          record a passed lat-check: harness version, a
                                                    hash of the harness sources and of CFG
    python3 session.py lat-stamp-ok CFG STAMP       exit 0 only when STAMP is of these sources and CFG
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
    # every (shape, arm) the config runs: all pairs, or only the cells its arms list
    for sh, a in experiment.cells(exp):
        got = [m for (s_, ar, r), m in latest.items() if s_ == sh["name"] and ar == a["name"]]
        if not got:
            probs.append("missing: %s %s" % (sh["name"], a["name"]))
        for m in got:
            v = m.get("verdict") or {}
            if not v.get("valid"):
                probs.append("invalid: %s %s: %s" % (sh["name"], a["name"], "; ".join(v.get("reasons") or [])))
    return probs


# ---------------------------------------------------------------- run L (flush latency)

LAT_BUDGET_S = 70 * 60   # the 60 s window stays; the stop is 85 min, so a re-run round fits
LAT_BUSY = (0.25, 0.45)
LAT_FLUSH_WALL_MAX_S = 7.0
LAT_MANIP_MIN = 10.0
LAT_CONTROL_P99_US = 1000.0
LAT_RXQ_MAX_SHARE = 0.5


def _get(m, dotted):
    v = m
    for p in dotted.split("."):
        if not isinstance(v, dict) or p not in v:
            return None
        v = v[p]
    return v


def lat_rules(cfg_path, smoke_dir, out=sys.stdout):
    """[problem] of the run-L smoke rules that are not per-leg gates (plan section 6): S-3 worker
    busy share, S-4 flush length on the shared core, S-5 the manipulation check, S-6 the
    receiver's queue, S-7 the control stream, S-8 the budget, S-9 the otlp leg. A missing leg or
    a missing value is a problem (fail closed). The per-leg gates (S-1, the rest of S-7 and
    S-9) are the legs' own verdicts, checked by smoke-valid and evidence-check."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    from epl import experiment
    exp = experiment.load(cfg_path)
    latest = {}
    p = os.path.join(smoke_dir, "legs.jsonl")
    for m in (legs(p) if os.path.exists(p) else []):
        if m.get("arm"):
            latest[(m.get("shape"), m.get("arm"))] = m
    cells = [(sh["name"], a["name"]) for sh, a in experiment.cells(exp)]
    probs = []

    def need(cell, dotted, rule):
        m = latest.get(cell)
        v = _get(m, dotted) if m else None
        if v is None:
            probs.append("%s: %s/%s has no %s" % (rule, cell[0], cell[1], dotted))
        return v

    def check(rule, cell, dotted, lo=None, hi=None, what=""):
        v = need(cell, dotted, rule)
        if v is None:
            return
        ok = (lo is None or v >= lo) and (hi is None or v <= hi)
        out.write("%s %s/%s %s = %s (%s)%s\n" % (rule, cell[0], cell[1], dotted, v, what, "" if ok else "  FAIL"))
        if not ok:
            probs.append("%s: %s/%s %s = %s, wanted %s" % (rule, cell[0], cell[1], dotted, v, what))

    for cell in cells:
        if cell not in latest:
            probs.append("S-1: no smoke leg of %s/%s" % cell)
    if ("own", "nosink") in cells:
        check("S-3", ("own", "nosink"), "lat.worker_busy_mean", LAT_BUSY[0], LAT_BUSY[1],
              "worker busy share 25%% to 45%%; outside: Nighthawk rate in steps of 400 towards 35%%, lat-smoke again")
    else:
        probs.append("S-3: the config has no own/nosink cell")
    if ("shared", "statsd") in cells:
        check("S-4", ("shared", "statsd"), "lat.flush.wall_s_max", None, LAT_FLUSH_WALL_MAX_S,
              "longest flush at most 7 s; above: shared/statsd is replaced by shared/otlp")
        for k in ("lat.manipulation.in_over_out", "lat.manipulation.in_over_others"):
            check("S-5", ("shared", "statsd"), k, LAT_MANIP_MIN, None,
                  "run-queue wait of the worker on the shared CPU, in flush, at least 10x")
    for cell in cells:
        if cell[1] == "statsd":
            check("S-6", cell, "udp_leg.rcvbuf_errors", None, 0, "kernel drops 0")
            check("S-6", cell, "udp_leg.socket_drops", None, 0, "socket drops 0")
            check("S-6", cell, "lat.rx_queue.max_share", None, LAT_RXQ_MAX_SHARE,
                  "receive queue at most half of the granted buffer")
        check("S-7", cell, "lat.probe.control.p99_us", None, LAT_CONTROL_P99_US, "control stream p99 under 1 ms")
        check("S-7", cell, "lat.probe.lateness.p99_ms", None, 0.2, "probe lateness p99")
        check("S-7", cell, "lat.probe.loop_gaps_window", None, 5, "probe loop gaps")
        if cell[1] == "otlp":
            check("S-9", cell, "otlp_cluster.rx_reset", None, 0, "no export stream reset")
            m = latest.get(cell) or {}
            per, used = _get(m, "collector_delta.accepted_metric_points_per_flush"), m.get("used_total")
            if per is None or not used:
                probs.append("S-9: own/otlp has no points per flush or used count")
            else:
                ok = abs(per / float(used) - 1.0) <= 0.01
                out.write("S-9 own/otlp points per flush %s against %s used stats%s\n" % (per, used, "" if ok else "  FAIL"))
                if not ok:
                    probs.append("S-9: points per flush %s is not the used stats %s" % (per, used))
    spl = seconds_per_leg(smoke_dir)
    n = len(experiment.schedule(exp, 1, exp["rounds"]))
    if spl is None:
        probs.append("S-8: no seconds per leg in the smoke")
    else:
        tot = spl * n
        out.write("S-8 %.0f s per leg x %d legs = %.1f min (limit %.0f min; a re-run round adds %.1f min)\n" % (
            spl, n, tot / 60, LAT_BUDGET_S / 60, spl * len(cells) / 60))
        if tot > LAT_BUDGET_S:
            probs.append("S-8: expected %.1f min above %.0f min: over budget (cut order: window 60 to 50 s, then drop "
                         "own/otlp, with make.py --lat and a new smoke)" % (tot / 60, LAT_BUDGET_S / 60))
    return probs


def source_sha256():
    """One hash over the harness sources a run L uses (so a stamp is of this code whether or not
    the checkout has git)."""
    import hashlib
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    files = sorted(glob.glob(os.path.join(root, "epl", "*.py"))) + \
        sorted(glob.glob(os.path.join(root, "examples", "stats-flush", "*.py"))) + \
        sorted(glob.glob(os.path.join(root, "examples", "stats-flush", "*.sh")))
    h = hashlib.sha256()
    for f in files:
        h.update(os.path.relpath(f, root).encode() + b"\0")
        with open(f, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()


SMOKE_STAMP = "lat-smoke-stamp.json"
SMOKE_DIFF = {"name", "rounds", "rounds_block", "rounds_max", "smoke"}


def _sha(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def smoke_stamp(smoke_cfg):
    return {"source_sha256": source_sha256(), "smoke_config_sha256": _sha(smoke_cfg),
            "smoke_config": os.path.basename(smoke_cfg)}


def smoke_stamp_problems(queue_cfg, smoke_cfg, smoke_dir):
    """[problem]: the smoke directory was not written by lat-smoke with the present harness
    sources and the present smoke-lat.json, or lat.json is no longer that smoke's queue config
    (the two may differ only in name, rounds and the smoke flag)."""
    try:
        with open(os.path.join(smoke_dir, SMOKE_STAMP)) as f:
            st = json.load(f)
    except (OSError, ValueError):
        return ["no %s in %s: the smoke was not run by lat-smoke" % (SMOKE_STAMP, smoke_dir)]
    now = smoke_stamp(smoke_cfg)
    probs = ["the smoke was run with another %s (run lat-smoke again)" % what
             for k, what in (("source_sha256", "harness source"), ("smoke_config_sha256", "smoke-lat.json"))
             if st.get(k) != now[k]]
    with open(queue_cfg) as f:
        q = json.load(f)
    with open(smoke_cfg) as f:
        s = json.load(f)
    diff = sorted(k for k in set(q) | set(s) if q.get(k) != s.get(k) and k not in SMOKE_DIFF)
    if diff:
        probs.append("lat.json is not the queue config of this smoke-lat.json (differs in %s)" % ", ".join(diff))
    return probs


def lat_stamp(cfg_path):
    import hashlib
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    from epl import experiment
    with open(cfg_path, "rb") as f:
        cfg = hashlib.sha256(f.read()).hexdigest()
    return {"harness": experiment.harness_version(), "source_sha256": source_sha256(), "config_sha256": cfg,
            "config": os.path.basename(cfg_path)}


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
    if cmd == "lat-rules":
        probs = lat_rules(argv[1], argv[2])
        for p in probs:
            print("PROBLEM %s" % p)
        print("run L smoke rules: %s" % ("pass" if not probs else "NOT passed (%d problems)" % len(probs)))
        return 1 if probs else 0
    if cmd == "lat-smoke-stamp":
        os.makedirs(argv[2], exist_ok=True)
        st = smoke_stamp(argv[1])
        with open(os.path.join(argv[2], SMOKE_STAMP), "w") as f:
            json.dump(st, f, indent=1, sort_keys=True)
        print(json.dumps(st, sort_keys=True))
        return 0
    if cmd == "lat-smoke-stamp-ok":
        probs = smoke_stamp_problems(argv[1], argv[2], argv[3])
        for p in probs:
            print("PROBLEM %s" % p)
        print("smoke of this harness and config: %s" % ("yes" if not probs else "NO"))
        return 1 if probs else 0
    if cmd == "lat-stamp":
        st = dict(lat_stamp(argv[1]), passed=True)
        with open(argv[2], "w") as f:
            json.dump(st, f, indent=1, sort_keys=True)
        print(json.dumps(st, sort_keys=True))
        return 0
    if cmd == "lat-stamp-ok":
        try:
            with open(argv[2]) as f:
                st = json.load(f)
        except (OSError, ValueError):
            print("no passed lat-check recorded (%s)" % argv[2])
            return 1
        now = lat_stamp(argv[1])
        bad = [k for k in ("source_sha256", "config_sha256", "harness") if st.get(k) != now[k]]
        if bad or not st.get("passed"):
            print("the recorded lat-check is not of this harness and config (differs: %s)" % ", ".join(bad or ["passed"]))
            return 1
        print("lat-check of this harness and config: passed (%s)" % now["harness"])
        return 0
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
