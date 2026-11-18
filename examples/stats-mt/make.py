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
  micro.json     the microbenchmarks (time-bounded windows, narrowed set):
                 row 1 atomic_model (Current, Relaxed, RelaxedTestFlag, OneRmw, Sharded;
                 shared and spaced) from one build; rows 2 and 2b stat_update (counter, gauge
                 set, the shared per-host primitive counter and its control) and row 3 the
                 record-only histogram on fix, fix-relaxed and fix-relaxed-p1 (the box's
                 `rows`); threads 1, 4 and top (histogram 1 and top); the gates; the smoke
                 entries (smoke threads, every row); the sha256 of every binary used, pinned
                 from boxes/sha256/<box>.txt (null placeholders until the rebuild: check and
                 run refuse them); 5 interleaved rounds of 5 repetitions, 0.2 s warm-up and
                 1 s windows

boxes/sha256/<box>.txt: one line per binary, "<sha256>  <target>-<arm>-<commit>" (the build
record's form), for example "5149...  atomic_model_benchmark-base-3a80b1543c"; a line whose
commit is not the arm's commit is an error.

Thread counts (M8): one benchmark thread per physical core, siblings idle, on every box. On a
VM without SMT a vCPU is a core; on a VM with SMT only one CPU of each core is listed, so the
same N means the same number of cores on both VMs. "Top" is the largest such count that leaves
a spare core.

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
# every rung's client ramps its rate over the first second (the 28-worker calibration overflowed
# the client pool at start-up without it) and the window opens 3 s in, the same at every rung
RAMP = json.dumps({"name": "nighthawk.linear-ramping-rate-limiter-plugin",
                   "typed_config": {"@type": "type.googleapis.com/nighthawk.rate_limiter.LinearRampingRateLimiterConfig",
                                    "ramp_time": "1s"}}, separators=(",", ":"))
LEAD_IN_S = 3
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

# Microbenchmark arms: the
# benchmark overlay with the time-bounded windows on the fix stack; the base-stacked arms are
# dropped. atomic_model contains no Envoy stat code, so it runs from one build (MODEL_ARM).
MICRO_ARMS = {"fix": "d2f2238974", "fix-relaxed": "e74e595e3c", "fix-relaxed-p1": "f8bd66d7e7"}
MODEL_ARM = "fix"
MICRO_PAIRS = [["fix-relaxed", "fix", "all"], ["fix-relaxed-p1", "fix-relaxed", "all"]]
MICRO_BINARIES = ["atomic_model_benchmark", "stat_update_benchmark", "histogram_record_benchmark",
                  "server_stats_flush_contended_benchmark"]
MODEL_VARIANTS = ["Current", "Relaxed", "RelaxedTestFlag", "OneRmw", "Sharded"]
# row 2: counter and gauge set; row 2b: the shared per-host primitive counter and its control
STAT_BENCHES = ["bmCounterIncShared", "bmCounterIncPerThreadSpaced", "bmGaugeSetShared", "bmGaugeSetPerThreadSpaced",
                "bmPrimitiveCounterIncShared", "bmPrimitiveCounterIncPerThreadSpaced"]
# Google Benchmark adds the registered timing to the name; the filters accept it, names are compared without it
TIME_PARTS = "(/min_time:[0-9.]+)?(/min_warmup_time:[0-9.]+)?(/iterations:[0-9]+)?"
# gates, first revision: the operations floor is a rate (a stalled thread, not a slow
# contended one), the overlap gate an absolute time (batch granularity passes)
MICRO_GATES = {"ops_floor_per_s": 20000, "min_thread_ops_abs": 1024, "max_nonoverlap_s": 0.002,
               "max_nonoverlap_share": 0.005}


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
                    "client_concurrency": conc, "client_connections_per_worker": n * k // conc,
                    "client_extra_args": ["--rate-limiter-plugin-config", RAMP], "lead_in_s": LEAD_IN_S})
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


def ncpus(text):
    n = 0
    for part in text.split(","):
        a, _, b = part.partition("-")
        n += int(b or a) - int(a) + 1
    return n


def read_sha_list(path, arms):
    """{arm: {binary: sha256}} from a build record list ("<sha256>  <target>-<arm>-<commit>")."""
    out = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            h, name = line.split()[:2]
            target = next((b for b in MICRO_BINARIES if name.startswith(b + "-")), None)
            if target is None or len(h) != 64:
                raise SystemExit("%s: not a benchmark line: %r" % (path, line))
            arm_name, _, commit = name[len(target) + 1:].rpartition("-")
            if arm_name not in arms:
                continue
            if arms[arm_name] != commit:
                raise SystemExit("%s: %s is %s, the arm's commit is %s" % (path, name, commit, arms[arm_name]))
            out.setdefault(arm_name, {})[target] = h
    return out


def micro_runs(placement, cpus, rows, threads, hist_workers, arms):
    runs = []
    th = "|".join(str(t) for t in threads)
    common = {"placement": placement, "cpus": cpus, "threads": threads}
    if "model" in rows:
        runs.append(dict(common, binary="atomic_model_benchmark", kind="window", arms=[MODEL_ARM], row="1",
                         filter="^bmModel(%s)(Shared|PerThreadSpaced)%s/manual_time/threads:(%s)$" % (
                             "|".join(MODEL_VARIANTS), TIME_PARTS, th),
                         expect=["bmModel%s%s/manual_time/threads:%d" % (v, l, n) for v in MODEL_VARIANTS
                                 for l in ("Shared", "PerThreadSpaced") for n in threads]))
    if "stat" in rows:
        runs.append(dict(common, binary="stat_update_benchmark", kind="window", arms=sorted(arms), row="2, 2b",
                         filter="^(%s)%s/manual_time/threads:(%s)$" % ("|".join(STAT_BENCHES), TIME_PARTS, th),
                         expect=["%s/manual_time/threads:%d" % (b, n) for b in STAT_BENCHES for n in threads]))
    if "histogram" in rows:
        runs.append(dict(common, binary="histogram_record_benchmark", kind="histogram", arms=sorted(arms), row="3",
                         threads=hist_workers,
                         filter="^bmHistogramRecordOnly/(%s)%s/manual_time$" % (
                             "|".join(str(w) for w in hist_workers), TIME_PARTS),
                         expect=["bmHistogramRecordOnly/%d/manual_time" % w for w in hist_workers]))
    return runs


def micro_config(box, sha_list=None):
    mc = box["micro"]
    arms = dict(mc.get("arms") or MICRO_ARMS)
    n = ncpus(mc["cpus"])
    for what, ts in (("threads", mc["threads"]), ("histogram_workers", mc["histogram_workers"]),
                     ("smoke threads", mc["smoke"]["threads"]),
                     ("smoke histogram_workers", mc["smoke"]["histogram_workers"])):
        if max(ts) > n:
            raise SystemExit("%s: %s up to %d on %d CPUs" % (box["name"], what, max(ts), n))
    runs = micro_runs(mc["placement"], mc["cpus"], mc["rows"], mc["threads"], mc["histogram_workers"], arms)
    smoke_runs = micro_runs(mc["placement"], mc["cpus"], mc["rows"], mc["smoke"]["threads"],
                            mc["smoke"]["histogram_workers"], arms)
    pinned = sha_list or {}
    used = sorted({(a, r["binary"]) for r in runs + smoke_runs for a in r["arms"]})
    expected = {}
    for a, b in used:
        # null is the placeholder: `check` and `run` refuse it; pins come from boxes/sha256/<box>.txt
        expected.setdefault(a, {})[b] = (pinned.get(a) or {}).get(b)
    return dict({"name": "mt-micro-" + box["name"], "box": box, "root": mc["root"], "arms": arms,
                 "expected_sha256": expected, "pinned": all(v for x in expected.values() for v in x.values()),
                 "model_reference": "bmModelCurrent", "pmu": bool(mc.get("pmu", True)),
                 "max_invol_switches": mc.get("max_invol_switches"),
                 "pairs": [p for p in MICRO_PAIRS if p[0] in arms and p[1] in arms], "runs": runs,
                 "smoke": {"arm": MODEL_ARM, "runs": smoke_runs},
                 "rounds": 5, "repetitions": 5, "warmup_s": 0.2, "window_s": 1.0,
                 "order_seed": ORDER_SEED, "workdir": RUNS + "/micro",
                 "idle": {"max_load1": 4.0, "max_busy_pct": 2.0}, "steal_gate": box.get("steal_gate"),
                 "note": "max_invol_switches: 0 on bare metal; on a VM frozen from the smoke's largest count "
                         "(box micro.max_invol_switches), and run refuses while it is null"}, **MICRO_GATES)


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
    sl = os.path.join(HERE, "boxes", "sha256", box["name"] + ".txt")
    arms = (box.get("micro") or {}).get("arms") or MICRO_ARMS
    out["micro.json"] = micro_config(box, read_sha_list(sl, arms) if os.path.exists(sl) else None)
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
