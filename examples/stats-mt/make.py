#!/usr/bin/env python3
"""Write the configs of the multi-threaded stats study, run U and the microbenchmarks, per
machine description in boxes/.

    python3 examples/stats-mt/make.py [--box BOX_JSON ...] [--rates RATES_JSON]

RATES_JSON (from step 0, per box name): {"<box>": {"r_star": per-worker rate, "k":
connections per worker}}; the same per-worker rate and connections at every rung of a
machine. Without it the configs carry placeholders and are marked uncalibrated (run-u.sh
refuses to queue them).

Per box (directory named after it, with box.json):

  u.json         run U: the official release with every store stat (base), with
                 stats_config reject_all (stats-reject: store stats become null objects; the
                 per-host primitive stats stay on, so this is the price of store stats, a
                 lower bound on all stat updates), and a second copy of base; every rung in
                 every round, rung order rotated; 15 fixed rounds (the rung and arm rotations
                 both balance at 15); worker-only cycles per request is the primary metric;
                 responses counted at the origin
  smoke-u.json   one round of the three arms at every rung (evidence recorded)
  u-hitm.json    evidence legs outside the timed run (machines whose box lists hitm_events):
                 local and remote HITM loads per request, base and stats-reject, 2 rounds
  micro.json     the microbenchmark runs: arms mapped to build directories by commit, the
                 benchmarks with the box's thread placements, 5 interleaved rounds of 5
                 repetitions

Shape mt-s: the 4 KB proxied request to one cluster with one upstream host, one listener,
one route, HTTP/1.1, round robin, no decision reader of stats (`audit: mt-s`).
"""

import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER_SEED = 41
RUNS = "~/epl/runs/stats-mt"
DEFAULT_R_STAR = 1300  # placeholder until step 0: the 4 KB shape's per-worker rate on four workers
DEFAULT_K = 16         # placeholder: client connections per Envoy worker
NOFILE = 65536         # soft fd limit of the harness's own Envoy and client (1,024 is too few at 28 workers)
REJECT_EVIDENCE = [{"stat": "reject_all", "scope": "config", "equals": True, "label": "stats_matcher reject_all"},
                   {"stat": "http.ingress_http.downstream_rq_2xx", "scope": "leg", "absent": True,
                    "label": "store stats absent at the end of the leg (the read succeeded, the stat is not there)"}]
# The fix arm of later runs: the envoy-static built from 3c9cce2f2c (71a80bcaab); between that
# and 977c664058 only files under test/ change (benchmarks, their BUILD entries, three tests),
# which //source/exe:envoy-static does not depend on: the same source tree outside test/.
FIX_ENVOY_STATIC = {"binary": "~/epl/bins/stats/envoy-static-top-3c9cce2f2c",
                    "sha256": "1c0f3ccfc81045d49ff0fce238e9094e1bf7c0894e19470a8a7b51fd8fb9133c",
                    "record": "built from 3c9cce2f2c / 71a80bcaab; source tree outside test/ identical to 977c664058"}
BASE_EVIDENCE = [{"stat": "reject_all", "scope": "config", "absent": True, "label": "no stats matcher"},
                 {"stat": "http.ingress_http.downstream_rq_2xx", "scope": "leg", "min": 1,
                  "label": "store stats present"}]

# Microbenchmark arms: build directories by commit (section 4 of the plan)
MICRO_ARMS = {"base": "18fa8fc6fa", "fix": "977c664058", "fix-relaxed": "d2c62bf670",
              "fix-relaxed-p1": "8c8d7169ae", "base-relaxed": "18676f7806", "base-relaxed-p1": "1f1a299743"}
# (arm, reference, rows): the ordering contrast at every N, P1 on its own, the base stack at N = 1
MICRO_PAIRS = [["fix-relaxed", "fix", "all"], ["fix-relaxed-p1", "fix-relaxed", "all"],
               ["base-relaxed", "base", "n1"], ["base-relaxed-p1", "base-relaxed", "n1"], ["fix", "base", "n1"]]
STAT_BENCHES = ["bmCounterIncShared", "bmCounterIncPerThreadSpaced", "bmCounterIncPerThread", "bmGaugeIncDecShared",
                "bmGaugeIncDecPerThreadSpaced", "bmGaugeSetShared", "bmGaugeSetPerThreadSpaced",
                "bmPrimitiveCounterIncShared", "bmPrimitiveCounterIncPerThreadSpaced"]
MIX_BENCHES = ["bmRequestMixShared", "bmRequestMixPerThreadSpaced"]
MODEL_VARIANTS = ["Current", "Relaxed", "TestFlag", "RelaxedTestFlag", "OneRmw", "Sharded"]


def arm(box, name, settings=None, ev=None):
    a = {"name": name, "binaries": json.loads(json.dumps(box["binaries"]))}
    if settings:
        a["settings"] = settings
    if ev is not None:
        a["evidence"] = json.loads(json.dumps(ev))
    return a


def rung_shapes(box, r_star, k):
    out = []
    for r in box["rungs"]:
        n = r["workers"]
        conc = r["client_concurrency"]
        if (n * k) % conc or (n * r_star) % conc:
            raise ValueError("rung %s: rate %d x %d and connections %d x %d must divide by %d client workers"
                             % (r["name"], n, r_star, n, k, conc))
        out.append({"name": "mt-" + r["name"], "path": "/s", "kind": "proxied", "body_bytes": 4096,
                    "rps": n * r_star, "workers": n, "worker_cpus": r["worker_cpus"], "main_cpu": box["main_cpu"],
                    "client_concurrency": conc, "client_connections_per_worker": n * k // conc})
    return out


def base_cfg(box, name):
    return {
        "name": name, "machine_label": box["machine_label"], "workdir": RUNS, "box": box,
        "envoy": {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True, "nofile": NOFILE},
        "cpus": dict(box["cpus"]),
        "client": {"binary": box["client_binary"], "concurrency": 4, "connections_per_worker": 16, "warmup_s": 5,
                   "nofile": NOFILE,
                   "duration_s": 25, "idle_strategy": "poll",
                   "extra_args": ["--prefetch-connections", "--max-pending-requests", "1000",
                                  "--experimental-h1-connection-reuse-strategy", "lru"]},
        "measure": {"lead_in_s": 2, "window_s": 20, "perf": box["perf"], "perf_events": box["perf_events"],
                    "per_thread": True, "numastat": box["kind"] == "bare-metal", "responses_from": "origin"},
        "validity": {"max_steal_share": box.get("steal_gate"), "max_non2xx": 0},
        "idle": {"max_load1": 8.0, "max_busy_pct": 2.0},
        "origin": {"mode": "docker", "image": box["origin_image"], "platform": box["image_platform"], "port": 8092,
                   "workers": 8, "stub_status": True},
        "audit": "mt-s", "order": "latin", "shape_order": "latin", "order_seed": ORDER_SEED,
        "primary_metric": "workers_cycles_per_req", "comparisons": "base",
    }


def micro_config(box):
    mc = box["micro"]
    runs = []
    for pname, p in mc["placements"].items():
        th = "|".join(str(t) for t in p["threads"])
        runs.append({"binary": "atomic_model_benchmark", "placement": pname, "cpus": p["cpus"],
                     "filter": "^bmModel(%s)(Shared|PerThreadSpaced)/real_time/threads:(%s)$" % (
                         "|".join(MODEL_VARIANTS), th)})
        runs.append({"binary": "stat_update_benchmark", "placement": pname, "cpus": p["cpus"],
                     "filter": "^(%s)/real_time/threads:(%s)$" % ("|".join(STAT_BENCHES), th)})
        runs.append({"binary": "stat_update_benchmark", "placement": pname, "cpus": p["cpus"], "needs_mix": True,
                     "filter": "^(%s)/real_time/threads:(%s)$" % ("|".join(MIX_BENCHES), th)})
    first = list(mc["placements"].values())[0]
    hw = "|".join(str(w) for w in mc["histogram_workers"])
    runs.append({"binary": "histogram_record_benchmark", "placement": list(mc["placements"])[0], "cpus": first["cpus"],
                 "filter": "^bmHistogramRecord/(%s)/[01]/[01]/manual_time$" % hw})
    hk = "|".join(str(h) for h in mc["flush_hammers"])
    runs.append({"binary": "server_stats_flush_contended_benchmark", "placement": list(mc["placements"])[0],
                 "cpus": first["cpus"], "filter": "^bmFlushContended/100000/(%s)/[012]/real_time$" % hk})
    return {"name": "mt-micro-" + box["name"], "box": box, "root": mc["root"], "arms": dict(MICRO_ARMS),
            # the benchmark revision the rebuilt overlay reports in its context (M1-M9); runs refuse a
            # binary that reports another (or none), and refuse to start while it is unset
            "revision": {"context_key": "stats_bench_revision", "value": None},
            "spread_counter": "finish_spread", "max_spread": 0.10,
            "thread_counters": {"cycles": "cycles_per_op", "instructions": "instructions_per_op"},
            "mix_fields": 6,
            "pairs": MICRO_PAIRS, "runs": runs, "rounds": 5, "repetitions": 5, "min_time": "0.2s",
            "mix": None, "order_seed": ORDER_SEED, "workdir": RUNS + "/micro",
            "idle": {"max_load1": 4.0, "max_busy_pct": 2.0}, "steal_gate": box.get("steal_gate"),
            "note": "mix (STATS_BENCH_MIX) is '<counter incs>:<gauge pairs>:<gauge sets>:<primitive counter incs>:"
                    "<primitive gauge pairs>:<histogram samples>' (M7), no default: the request-mix benchmarks are "
                    "skipped until step 0 sets it from the uprobe counts"}


def configs(box, rates=None):
    rr = (rates or {}).get(box["name"]) or {}
    r_star, k = int(rr.get("r_star", DEFAULT_R_STAR)), int(rr.get("k", DEFAULT_K))
    shapes = rung_shapes(box, r_star, k)
    out = {}
    arms = [arm(box, "base", ev=BASE_EVIDENCE), arm(box, "stats-reject", {"stats_reject_all": True}, REJECT_EVIDENCE),
            arm(box, "base-A2", ev=BASE_EVIDENCE)]
    u = base_cfg(box, "mt-u-" + box["name"])
    # 15 fixed rounds: the rung rotation (period 5) and the arm rotation (period 3) both balance
    u.update(base_arm="base", arms=arms, shapes=shapes, rounds=15, rounds_block=15, rounds_max=15, adaptive=False,
             r_star=r_star, k=k, session_record={"fix_envoy_static": FIX_ENVOY_STATIC})
    if not rr:
        u["uncalibrated"] = True
    out["u.json"] = u
    s = json.loads(json.dumps(u))
    s.update(name="mt-smoke-u-" + box["name"], rounds=1, rounds_block=1, rounds_max=1, smoke=True,
             evidence_mode="record", adaptive=False)
    s.pop("uncalibrated", None)
    out["smoke-u.json"] = s
    if box.get("hitm_events"):
        h = json.loads(json.dumps(u))
        h.update(name="mt-u-hitm-" + box["name"], arms=[x for x in h["arms"] if x["name"] != "base-A2"],
                 rounds=2, rounds_block=2, rounds_max=2, adaptive=False, box_specific=True,
                 primary_metric="cycles_total")
        h["measure"].update(perf_events=box["hitm_events"], per_thread=False)
        out["u-hitm.json"] = h
    out["micro.json"] = micro_config(box)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", action="append")
    ap.add_argument("--rates")
    a = ap.parse_args()
    rates = json.load(open(a.rates)) if a.rates else None
    for bp in a.box or sorted(glob.glob(os.path.join(HERE, "boxes", "*.json"))):
        with open(bp) as f:
            box = json.load(f)
        d = os.path.join(HERE, box["name"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "box.json"), "w") as f:
            json.dump(box, f, indent=1)
            f.write("\n")
        cs = configs(box, rates)
        for fn, c in cs.items():
            with open(os.path.join(d, fn), "w") as f:
                json.dump(c, f, indent=1)
                f.write("\n")
        print("%s: %d configs" % (box["name"], len(cs)))


if __name__ == "__main__":
    main()
