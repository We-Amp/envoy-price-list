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
                 entries (smoke threads plus the box's top count, every row); the sha256 of every binary used, pinned
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

  codegen*.json  (boxes with a `codegen` section) the arm64 atomics codegen run: official
                 release against the main dev-image build, each with and without store stats,
                 plus an A/A copy; 4w and 12w (codegen-8w.json: 4w and 8w, the fallback when
                 the 12-worker smoke fails the client or rate gates); 20 fixed rounds; tables
                 from codegen_table.py

  dose*.json     (boxes with a `dose` section) run R1 ("dose"):
                 K counter increments per request from the stats access logger, on counter
                 objects shared by every worker (shared-K: the tag value is the listener port)
                 against one set of objects per downstream connection (own-K, the reference:
                 the tag value is the client's port; a connection belongs to one worker), and a
                 second copy of own-K (own-K-A2) for the A/A. Same code path, formatter and name
                 length in both. Every dose arm sets a stats flush interval longer than a leg.
                 Every dose arm listens on the wildcard address (a local-address object per
                 connection; the client still targets loopback).
                 Cells are rungs with their own per-worker rate (the box's dose.cells); the slot
                 runs dose.slot_cells, each at K or at its own dose (dose.cell_counters), with
                 own, shared and an A/A copy of own at that dose, and in dose.low.cell also own
                 and shared at the second dose (dose.low.counters). K and the client connections
                 per worker are the choice recorded in RATES_JSON, key dose.rates_key:
                 {"counters": K, "connections": c}; without both dose.json, the smokes and
                 dose-evidence.json carry placeholders and are marked uncalibrated. A shape at
                 other than 16 connections per worker is mt-<rung>-c<c>.
                   dose-pilot.json     one round: base and own/shared at every K of
                                       dose.counters_choices in cell A; a loopback pair at the
                                       middle K; own/shared at the middle K at 16 and 8
                                       connections per worker in cells A and D; the load cell
                                       (exploratory); the deciding legs first, never stopped
                                       by invalid legs; the HITM events (dose_pilot.py prints
                                       the answers and writes the record the queue checks)
                   smoke-dose.json     one round of dose.json (evidence recorded)
                   smoke-dose-evidence.json  one round of the evidence legs in the cells
                                       that show every one of their arms
                   dose.json           15 fixed rounds, 11 legs per round
                   dose-evidence.json  evidence legs outside the timed run: base,
                                       stats-reject, own and shared at the cell's dose, 4
                                       rounds per slot cell,
                                       HITM events counted in user mode, store-stat operations
                 Tables from u_table.py (statements S1-S5 and the model row).

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
# second revision: the overlap allowance adds 3 batches of the slowest thread; the floor is 1,024 operations
MICRO_GATES = {"ops_floor_per_s": 0, "min_thread_ops_abs": 1024, "max_nonoverlap_s": 0.002,
               "max_nonoverlap_share": 0.005, "nonoverlap_batches": 3, "ops_per_batch": 256}


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
            if "/" in name:
                # "<sha256>  <build directory>/<target>" (the build record's other form)
                d, _, target = name.rpartition("/")
                arm_name = next((a for a, c in arms.items() if c == d), None)
                if arm_name is None or target not in MICRO_BINARIES or len(h) != 64:
                    continue
                out.setdefault(arm_name, {})[target] = h
                continue
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


def micro_runs(placement, cpus, rows, threads, hist_workers, arms, model_arms=None):
    runs = []
    th = "|".join(str(t) for t in threads)
    common = {"placement": placement, "cpus": cpus, "threads": threads}
    if "model" in rows:
        runs.append(dict(common, binary="atomic_model_benchmark", kind="window", arms=list(model_arms or [MODEL_ARM]), row="1",
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


def micro_config(box, sha_list=None, section="micro"):
    mc = box[section]
    arms = dict(mc.get("arms") or MICRO_ARMS)
    model_arms = sorted(arms) if mc.get("model_all_arms") else None
    smoke_arm = mc.get("smoke_arm", MODEL_ARM)
    n = ncpus(mc["cpus"])
    for what, ts in (("threads", mc["threads"]), ("histogram_workers", mc["histogram_workers"]),
                     ("smoke threads", mc["smoke"]["threads"]),
                     ("smoke histogram_workers", mc["smoke"]["histogram_workers"])):
        if max(ts) > n:
            raise SystemExit("%s: %s up to %d on %d CPUs" % (box["name"], what, max(ts), n))
    runs = micro_runs(mc["placement"], mc["cpus"], mc["rows"], mc["threads"], mc["histogram_workers"], arms,
                      model_arms)
    # the smoke always includes the box's top count beside its own (1, 2, 4)
    smoke_threads = sorted(set(mc["smoke"]["threads"]) | {max(mc["threads"])})
    smoke_hist = sorted(set(mc["smoke"]["histogram_workers"]) | {max(mc["histogram_workers"])})
    smoke_runs = micro_runs(mc["placement"], mc["cpus"], mc["rows"], smoke_threads, smoke_hist, arms, model_arms)
    pinned = sha_list or {}
    used = sorted({(a, r["binary"]) for r in runs + smoke_runs for a in r["arms"]})
    expected = {}
    for a, b in used:
        # null is the placeholder: `check` and `run` refuse it; pins come from boxes/sha256/<box>.txt
        expected.setdefault(a, {})[b] = (pinned.get(a) or {}).get(b)
    pairs = mc.get("pairs") or [p for p in MICRO_PAIRS if p[0] in arms and p[1] in arms]
    return dict({"name": "mt-%s-%s" % (section.replace("_", "-"), box["name"]), "box": box, "root": mc["root"],
                 "arms": arms, "expect_atomics": mc.get("expect_atomics"),
                 "expected_sha256": expected, "pinned": all(v for x in expected.values() for v in x.values()),
                 "model_reference": "bmModelCurrent", "pmu": bool(mc.get("pmu", True)),
                 "max_invol_switches": mc.get("max_invol_switches"),
                 "invol_switches_per_s": mc.get("invol_switches_per_s"),
                 "invol_bound_record": mc.get("invol_bound_record"),
                 "pairs": pairs, "runs": runs,
                 "smoke": {"arm": smoke_arm, "runs": smoke_runs},
                 "rounds": 5, "repetitions": 5, "warmup_s": 0.2, "window_s": 1.0,
                 "order_seed": ORDER_SEED, "workdir": RUNS + "/micro",
                 "idle": {"max_load1": 4.0, "max_busy_pct": 2.0}, "steal_gate": box.get("steal_gate"),
                 "note": "involuntary-switch bound per repetition: per thread max(max_invol_switches, "
                         "invol_switches_per_s x window) where the box sets a rate, else max_invol_switches (frozen "
                         "from the box's smoke), times the threads; run refuses while it is null"}, **MICRO_GATES)


def codegen_configs(box):
    """The arm64 atomics codegen run (boxes with a `codegen` section): the official release
    (out-of-line atomics helpers) against the main dev-image build (inline LL/SC atomics), each
    with every store stat and with stats_config reject_all, and an A/A copy of the official arm.
    The primary contrast is the difference of the two binaries' stats prices,
    ln(dev / dev-reject) - ln(official / official-reject), paired by round: the other
    differences between the two builds (1.40.2 against main) cancel in it to the extent they do
    not touch stat updates. The direct dev / official ratio is reported, labelled confounded.
    {file: config} for the main rung set and its fallback (top rung 8 workers)."""
    cg = box["codegen"]
    rungs = {r["name"]: r for r in box["rungs"] + cg.get("extra_rungs", [])}
    dev = {"name": "dev", "binaries": json.loads(json.dumps(cg["dev_binaries"])),
           "evidence": json.loads(json.dumps(BASE_EVIDENCE))}
    dev_rej = dict(json.loads(json.dumps(dev)), name="dev-reject", settings={"stats_reject_all": True},
                   evidence=json.loads(json.dumps(REJECT_EVIDENCE)))
    arms = [arm(box, "official", ev=BASE_EVIDENCE),
            arm(box, "official-reject", {"stats_reject_all": True}, REJECT_EVIDENCE),
            dev, dev_rej, arm(box, "official-A2", ev=BASE_EVIDENCE)]
    out = {}
    for suffix, names in (("", cg["rungs"]), ("-8w", cg["fallback_rungs"])):
        b = dict(box, rungs=[rungs[n] for n in names])
        c = base_cfg(b, "codegen%s-%s" % (suffix, box["name"]))
        c["box"] = box
        # 20 fixed rounds (the method needs 12 or more): the arm rotation (period 5) and the rung
        # rotation (period 2) both balance at 10
        c.update(base_arm="official", arms=json.loads(json.dumps(arms)), shapes=rung_shapes(b, cg["r_star"], cg["k"]),
                 rounds=20, rounds_block=20, rounds_max=20, adaptive=False, r_star=cg["r_star"], k=cg["k"],
                 box_specific=True,
                 contrast={"primary": "ln(dev / dev-reject) - ln(official / official-reject), paired by round",
                           "aa": ["official-A2", "official"], "direct": ["dev", "official"],
                           "direct_label": "confounded: 1.40.2 against main 5e1439980a differ beyond the atomics",
                           # checked from the binaries before the smoke (codegen_check.py atomics)
                           "expect_style": {"official": "outline", "dev": "llsc-inline"},
                           # store-stat operations per request compared between these arms in the smoke
                           "stat_ops_pair": ["official", "dev"]})
        out["codegen%s.json" % suffix] = c
        sm = json.loads(json.dumps(c))
        sm.update(name="smoke-codegen%s-%s" % (suffix, box["name"]), rounds=1, rounds_block=1, rounds_max=1, smoke=True,
                  evidence_mode="record")
        sm["measure"]["stat_ops_probe"] = True
        out["smoke-codegen%s.json" % suffix] = sm
    return out


def u_hi_configs(box, rates, arms):
    """Run U at high load (boxes with a `u_hi` section): run U's design (base, stats-reject,
    base-A2; 16 connections per worker; the same per-worker rate at every rung; 15 fixed
    rounds) on the top rungs only, at a per-worker rate calibrated to the target worker busy
    share (RATES_JSON key "<box>-hi"; without it the configs carry a placeholder and are marked
    uncalibrated). cal-u-hi.json is the calibration config (calibrate with --arm base)."""
    hi = box["u_hi"]
    # the rates key: the box's u_hi.rates_key (one key per attempt, so an earlier attempt's rate
    # stays recorded), else "<box>-hi"
    rr = (rates or {}).get(hi.get("rates_key") or box["name"] + "-hi") or {}
    r_star, k = int(rr.get("r_star", hi["placeholder_r_star"])), int(rr.get("k", DEFAULT_K))
    b = dict(box, rungs=[r for r in box["rungs"] if r["name"] in hi["rungs"]])
    out = {}
    u = base_cfg(b, "mt-u-hi-" + box["name"])
    u["box"] = box
    # 15 fixed rounds: the rung rotation (period 3) and the arm rotation (period 3) both balance
    u.update(base_arm="base", arms=json.loads(json.dumps(arms)), shapes=rung_shapes(b, r_star, k), rounds=15,
             rounds_block=15, rounds_max=15, adaptive=False, r_star=r_star, k=k, box_specific=True,
             target_worker_busy=hi["target_busy"], session_record={"fix_envoy_static": FIX_ENVOY_STATIC},
             # H1: the contrasts of this run (no 1w rung): growth at high load and cross-socket
             growth=hi["growth"], cross_socket=hi["cross_socket"])
    if not rr:
        u["uncalibrated"] = True
    out["u-hi.json"] = u
    sm = json.loads(json.dumps(u))
    sm.update(name="mt-smoke-u-hi-" + box["name"], rounds=1, rounds_block=1, rounds_max=1, smoke=True,
              evidence_mode="record", adaptive=False)
    sm.pop("uncalibrated", None)
    out["smoke-u-hi.json"] = sm
    cal = json.loads(json.dumps(sm))
    cal.update(name="mt-cal-u-hi-" + box["name"], arms=[a for a in cal["arms"] if a["name"] != "base-A2"])
    out["cal-u-hi.json"] = cal
    return out


# Run R1 ("dose"): the stats access logger's scope, tag and tag values (epl/envoy_config.py
# renders them; the tests hold the two files to the same names)
DOSE_SCOPE = "dose"
DOSE_TAG = "port"
DOSE_TAG_VALUES = {"shared": "%DOWNSTREAM_LOCAL_PORT%", "own": "%DOWNSTREAM_REMOTE_PORT%"}
DOSE_ROUNDS = 15           # the cell rotation (period 3) and the arm rotations (5 and 3 arms) all balance
DOSE_EVIDENCE_ROUNDS = 4   # the arm rotation of the evidence legs (4 arms) balances once
DOSE_LOOPBACK = "127.0.0.1"


def dose_shape_name(rung, k):
    """A cell's shape: mt-<rung> at the default connections per worker, else mt-<rung>-c<k>."""
    return "mt-%s%s" % (rung, "" if k == DEFAULT_K else "-c%d" % k)


def dose_shapes(box, cells, k):
    """One shape per cell: the cell's rung at the cell's own per-worker rate, k client
    connections per worker. A cell's rung may be one of the dose run's own (dose.extra_rungs)."""
    d = box["dose"]
    rungs = {r["name"]: r for r in box["rungs"] + d.get("extra_rungs", [])}
    by = {c["cell"]: c for c in d["cells"]}
    out = []
    for c in [by[x] for x in cells]:
        s = rung_shapes(dict(box, rungs=[rungs[c["rung"]]]), int(c["rate_per_worker"]), k)[0]
        # the own arms hold K counters per connection: a full admin stats read takes longer
        s.update(name=dose_shape_name(c["rung"], k), admin_timeout_s=d["admin_timeout_s"], cell=c["cell"],
                 connections_per_worker=k)
        out.append(s)
    return out


def dose_shared_counter(port):
    """The flat name of the first counter of a shared arm: one object, written by every worker."""
    return "%s.c000.%s.%d" % (DOSE_SCOPE, DOSE_TAG, port)


def dose_evidence(kind, K, port, shapes, address, flush, sum_tol):
    """Fail-closed evidence of a dose arm. Config: the tag value, the flush interval (no flush
    during a leg) and the listener's address (the wildcard address gives every connection its
    own local-address object). shared: exactly K dose counters before and after the window and
    one increment per request on one of them. own: K counters per downstream connection (at
    least the measured client's connections, at most those plus the warm-up client's, which stay
    in the store), none created during the window, and no shared object. Both: no downstream
    connection opened inside the window, and K increments per request summed over every dose
    counter, within sum_tol of K (a counter over a scope limit would be a null object and add
    nothing)."""
    ev = [{"stat": "value_format", "scope": "config", "equals": DOSE_TAG_VALUES[kind],
           "label": "tag value %s" % DOSE_TAG_VALUES[kind]},
          {"stat": "stats_flush_interval", "scope": "config", "equals": "%ds" % flush,
           "label": "stats flush interval %d s (no flush during the leg)" % flush},
          {"stat": "address", "scope": "config", "where": {"port_value": port}, "equals": address,
           "label": "listener address %s (%s)" % (address, "one local-address object for every connection"
                                                  if address == DOSE_LOOPBACK else
                                                  "a local-address object per connection")}]
    if kind == "shared":
        ev += [{"stat": "stat_count.start_n", "scope": "field", "equals": K, "tol_abs": 0,
                "label": "%d dose counters before the window" % K},
               {"stat": "stat_count.end_n", "scope": "field", "equals": K, "tol_abs": 0,
                "label": "%d dose counters after the window" % K},
               {"stat": dose_shared_counter(port), "scope": "window", "per_request": 1.0, "tol": 0.01,
                "label": "one increment per request on a shared counter"}]
    else:
        for s in shapes:
            conns = s["workers"] * s["connections_per_worker"]
            ev.append({"stat": "stat_count.start_n", "scope": "field", "min": K * conns, "max": 2 * K * conns,
                       "shape": s["name"],
                       "label": "%d dose counters per connection (%d connections; the warm-up client's stay)"
                                % (K, conns)})
        ev += [{"stat": "stat_count.new_in_window", "scope": "field", "equals": 0, "tol_abs": 0,
                "label": "no dose counter created during the window (no reconnect)"},
               {"stat": dose_shared_counter(port), "scope": "window", "absent": True,
                "label": "no counter object shared by the workers"}]
    ev.append({"stat": "http.ingress_http.downstream_cx_total", "scope": "window", "equals": 0, "tol_abs": 0,
               "label": "no downstream connection opened during the window"})
    # the sum and Envoy's completed-request counter come from the same two admin reads
    ev.append({"stat": "stat_count.sum_per_request", "scope": "field", "min": K - sum_tol, "max": K + sum_tol,
               "label": "%d increments per request over all dose counters (within %g)" % (K, sum_tol)})
    return ev


def dose_arm(box, kind, K, port, shapes, suffix="", only=None, address=None):
    """One dose arm. Every dose arm sets the box's long stats flush interval, so the main
    thread's flush does not latch the counters during a leg, and listens on the box's dose
    listener address (the wildcard address) unless `address` says otherwise (the pilot's
    loopback pair). `only`: the shapes the arm runs in."""
    d = box["dose"]
    address = address or d["listener_address"]
    mine = [s for s in shapes if only is None or s["name"] in only]
    a = arm(box, "%s-%d%s" % (kind, K, suffix),
            {"stats_access_log": {"counters": K, "tag": DOSE_TAG_VALUES[kind]},
             "stats_flush": {"interval_s": d["flush_interval_s"]}, "listener_address": address},
            dose_evidence(kind, K, port, mine, address, d["flush_interval_s"], d["sum_tol_abs"]))
    if only is not None:
        a["shapes"] = list(only)
    return a


def dose_configs(box, rates):
    """Run R1 ("dose", boxes with a `dose` section):
    {file: config}. K and the connections per worker are the pilot's choice (RATES_JSON key
    dose.rates_key: {"counters": K, "connections": c}); without both every config but the
    pilot's carries the placeholders and is marked uncalibrated."""
    d = box["dose"]
    rr = (rates or {}).get(d["rates_key"]) or {}
    calibrated = rr.get("counters") is not None and rr.get("connections") is not None
    K = int(rr["counters"]) if rr.get("counters") is not None else int(d["placeholder_counters"])
    k = int(rr["connections"]) if rr.get("connections") is not None else int(d["placeholder_connections"])
    if K not in d["counters_choices"]:
        raise SystemExit("%s: dose counters %d is not one of %s" % (box["name"], K, d["counters_choices"]))
    if k not in d["connections_choices"]:
        raise SystemExit("%s: dose connections %d is not one of %s" % (box["name"], k, d["connections_choices"]))
    Klow = int(d["low"]["counters"])
    if Klow == K:
        raise SystemExit("%s: dose counters %d is also the second dose of cell %s" % (box["name"], K, d["low"]["cell"]))
    shapes = dose_shapes(box, d["slot_cells"], k)
    shape_of = {s["cell"]: s["name"] for s in shapes}
    # the dose of each cell: K, or the cell's own (dose.cell_counters)
    dose_of = {c: int(d.get("cell_counters", {}).get(c, K)) for c in d["slot_cells"]}
    doses = [K] + sorted({n for n in list(dose_of.values()) + [Klow] if n != K}, reverse=True)
    cells_by = {c["cell"]: c for c in d["cells"]}
    no_dose = {"stat": "stat_count.start_n", "scope": "field", "equals": 0, "tol_abs": 0, "label": "no dose counters"}

    def cfg(name, arms, base_arm, shp, rounds, **over):
        c = base_cfg(box, name)
        port = c["envoy"]["listener_port"]
        c.update(base_arm=base_arm, arms=json.loads(json.dumps(arms(port, shp))), shapes=json.loads(json.dumps(shp)),
                 rounds=rounds, rounds_block=rounds, rounds_max=rounds, adaptive=False, box_specific=True,
                 # no leg inside the daily window in which a timer runs on the box
                 avoid_utc=json.loads(json.dumps(d["avoid_utc"])))
        # the admin reads before the window (tens of thousands of counters in an own arm) come out
        # of the client run's slack: a longer client run, the same 20 s window
        c["client"]["duration_s"] = d["client_duration_s"]
        # the dose counters around the window, and one shared counter in the window's snapshots
        c["measure"].update(stat_count_prefix=DOSE_SCOPE + ".",
                            stat_filter_extra="^" + dose_shared_counter(port).replace(".", "\\.") + "$")
        c.update(over)
        return c

    def cell(s, **more):
        c = cells_by[s["cell"]]
        return dict({"cell": c["cell"], "shape": s["name"], "rung": c["rung"], "role": c["role"],
                     "sockets": c["sockets"], "workers": s["workers"], "rate_per_worker": c["rate_per_worker"],
                     "connections": s["connections_per_worker"]}, **more)

    def slot_cell(s, aa):
        # every cell names its own dose and arms: nothing downstream may assume one K for the run
        n = dose_of[s["cell"]]
        return cell(s, counters=n, reference="own-%d" % n, shared="shared-%d" % n,
                    aa=["own-%d-A2" % n, "own-%d" % n] if aa else None)

    def block(shp, aa, low=None):
        return {"counters": K, "connections": k, "rates_key": d["rates_key"],
                "cells": [slot_cell(s, aa) for s in shp], "socket": d["socket"], "workers": d["workers"], "low": low,
                "flush_interval_s": d["flush_interval_s"], "listener_address": d["listener_address"]}

    def only(cells, shp):
        mine = [s["name"] for s in shp if s["cell"] in cells]
        return None if len(mine) == len(shp) else mine

    def slot_arms(port, shp):
        # per dose: own and shared where a cell runs that dose or has it as its second dose; the
        # A/A copy of own where it is the cell's own dose
        out = []
        for n in doses:
            ref = [c for c in d["slot_cells"] if dose_of[c] == n]
            pair = ref + ([d["low"]["cell"]] if n == Klow and d["low"]["cell"] not in ref else [])
            out += [dose_arm(box, "own", n, port, shp, only=only(pair, shp)),
                    dose_arm(box, "shared", n, port, shp, only=only(pair, shp))]
            if ref:
                out.append(dose_arm(box, "own", n, port, shp, "-A2", only=only(ref, shp)))
        return out

    def evidence_arms(port, shp):
        out = [arm(box, "base", ev=BASE_EVIDENCE + [no_dose]),
               arm(box, "stats-reject", {"stats_reject_all": True}, REJECT_EVIDENCE)]
        for n in doses:
            ref = [c for c in d["slot_cells"] if dose_of[c] == n and c in {s["cell"] for s in shp}]
            if ref:
                out += [dose_arm(box, "own", n, port, shp, only=only(ref, shp)),
                        dose_arm(box, "shared", n, port, shp, only=only(ref, shp))]
        return out

    out = {}
    low = {"cell": d["low"]["cell"], "counters": Klow, "reference": "own-%d" % Klow, "shared": "shared-%d" % Klow}
    # 11 legs per round: own, shared and the A/A copy at the cell's dose in every cell, and the
    # second dose's pair in its cell. No arm runs in every cell, so the harness's own rows are
    # between the arms of a cell (all_pairs); the statements are u_table's.
    u = cfg("mt-dose-" + box["name"], slot_arms, "own-%d" % K, shapes, DOSE_ROUNDS, k=k, comparisons="all_pairs",
            dose=block(shapes, True, low))
    if not calibrated:
        u["uncalibrated"] = True
    out["dose.json"] = u
    sm = json.loads(json.dumps(u))
    # the smoke keeps the mark: no dose leg runs at a choice nobody made
    sm.update(name="mt-smoke-dose-" + box["name"], rounds=1, rounds_block=1, rounds_max=1, smoke=True,
              evidence_mode="record")
    out["smoke-dose.json"] = sm
    # the evidence legs: base and stats-reject (the plain config: the default flush interval, the
    # loopback listener) and own and shared at the cell's dose, in every cell
    ev = cfg("mt-dose-evidence-" + box["name"], evidence_arms, "base", shapes, DOSE_EVIDENCE_ROUNDS, k=k,
             dose=block(shapes, False))
    ev["measure"].update(perf_events=d["hitm_events"], stat_ops_probe=True)
    if not calibrated:
        ev["uncalibrated"] = True
    out["dose-evidence.json"] = ev
    # one round of the evidence legs in as few cells as show every arm once: the event list and
    # the stat-operation probe are exercised before the slot
    need, picked = {n for n in dose_of.values()}, []
    for c in d["slot_cells"]:
        if dose_of[c] in need:
            picked.append(c)
            need.discard(dose_of[c])
    es = [s for s in shapes if s["cell"] in picked]
    sme = cfg("mt-smoke-dose-evidence-" + box["name"], evidence_arms, "base", es, 1, k=k, smoke=True,
              evidence_mode="record", dose=block(es, False))
    sme["measure"].update(perf_events=d["hitm_events"], stat_ops_probe=True)
    if not calibrated:
        sme["uncalibrated"] = True
    out["smoke-dose-evidence.json"] = sme
    out["dose-pilot.json"] = dose_pilot_config(box, cfg, cell, no_dose)
    return out


def dose_pilot_config(box, cfg, cell, no_dose):
    """The pilot (it does not depend on the choices it informs). One round, in this order, so
    that the legs that decide run first whatever fails later:
      1. the K cell at the first connection count, wildcard listener: base, then own/shared at
         every K of the choice list (the K rule);
      2. own/shared at the middle K in the other connection cells at that count (the 28-worker
         client gates), then in every connection cell at the other count (the footprint of own);
      3. one loopback own/shared pair at the middle K (exploratory: the size of the shared
         local-address object's effect), in a shape of its own so that it runs here;
      4. own/shared at the middle K in the exploratory cells.
    Arms run in the listed order (order fixed), an invalid leg is not re-run and consecutive
    invalid legs do not stop the run: a pilot is there to find out which shapes fail.
    `pairs` names every own/shared pair with its cell, connection count, K and role."""
    d = box["dose"]
    p = d["pilot"]
    ks, mid, c0 = d["counters_choices"], p["mid"], p["connections"][0]
    shapes = []
    for kc in p["connections"]:
        shapes += dose_shapes(box, p["connection_cells"], kc)
    first = [s for s in shapes if s["cell"] == p["k_cell"] and s["connections_per_worker"] == c0]
    shapes = first + [s for s in shapes if s not in first]
    kshape = first[0]["name"]
    lo = dict(json.loads(json.dumps([s for s in shapes if s["cell"] == p["loopback_cell"]
                                     and s["connections_per_worker"] == c0][0])))
    lo.update(name=lo["name"] + "-lo", loopback=True)
    expl = dose_shapes(box, p["exploratory_cells"], c0)
    wild = [s["name"] for s in shapes + expl]
    shapes = shapes + [lo] + expl

    def arms(port, shp):
        out = [dict(arm(box, "base", ev=BASE_EVIDENCE + [no_dose]), shapes=[kshape])]
        for n in ks:
            for kind in ("own", "shared"):
                out.append(dose_arm(box, kind, n, port, shp, only=wild if n == mid else [kshape]))
        for kind in ("own", "shared"):
            out.append(dict(dose_arm(box, kind, mid, port, shp, "-lo", only=[lo["name"]], address=DOSE_LOOPBACK),
                            exploratory=True))
        return out
    pairs = []
    for n in ks:
        pairs.append({"cell": p["k_cell"], "shape": kshape, "connections": c0, "k": n, "own": "own-%d" % n,
                      "shared": "shared-%d" % n, "address": d["listener_address"], "role": "k"})
    for s in shapes:
        if s["name"] == kshape:
            continue
        if s.get("loopback"):
            pairs.append({"cell": s["cell"], "shape": s["name"], "connections": c0, "k": mid, "own": "own-%d-lo" % mid,
                          "shared": "shared-%d-lo" % mid, "address": DOSE_LOOPBACK, "role": "loopback",
                          "exploratory": True})
            continue
        ex = s["cell"] in p["exploratory_cells"]
        pairs.append(dict({"cell": s["cell"], "shape": s["name"], "connections": s["connections_per_worker"], "k": mid,
                           "own": "own-%d" % mid, "shared": "shared-%d" % mid, "address": d["listener_address"],
                           "role": "load" if ex else "connections"}, **({"exploratory": True} if ex else {})))
    pilot = cfg("mt-dose-pilot-" + box["name"], arms, "own-%d" % mid, shapes, 1, smoke=True, evidence_mode="record",
                # the listed order; every leg once; never stopped by invalid legs (17 legs)
                order="fixed", shape_order="fixed", rerun_invalid=0, abort_after_invalid=1000,
                # no arm runs in every shape (the loopback pair has its own): rows between the arms of a shape
                comparisons="all_pairs",
                dose={"rates_key": d["rates_key"], "counters_choices": ks, "connections_choices": d["connections_choices"],
                      "mid": mid, "k_cell": p["k_cell"], "connection_cells": p["connection_cells"],
                      "cells": [cell(s, **({"exploratory": True} if s["cell"] in p["exploratory_cells"] else {}))
                                for s in shapes],
                      "pairs": pairs, "pilot_rule": d["pilot_rule"], "flush_interval_s": d["flush_interval_s"],
                      "listener_address": d["listener_address"]})
    # measured as the evidence legs will be: the HITM events, the store-stat operation probe
    pilot["measure"].update(perf_events=d["hitm_events"], stat_ops_probe=True)
    return pilot


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
    if box.get("u_hi"):
        out.update(u_hi_configs(box, rates, arms))
    if box.get("dose"):
        out.update(dose_configs(box, rates))
    sl = os.path.join(HERE, "boxes", "sha256", box["name"] + ".txt")
    arms = (box.get("micro") or {}).get("arms") or MICRO_ARMS
    out["micro.json"] = micro_config(box, read_sha_list(sl, arms) if os.path.exists(sl) else None)
    if box.get("micro_lse"):
        # the LSE against LL/SC build of the same benchmark source
        sl2 = os.path.join(HERE, "boxes", "sha256", box["name"] + "-lse.txt")
        out["micro-lse.json"] = micro_config(box, read_sha_list(sl2, box["micro_lse"]["arms"])
                                             if os.path.exists(sl2) else None, "micro_lse")
    if box.get("codegen"):
        out.update(codegen_configs(box))
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
