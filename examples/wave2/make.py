#!/usr/bin/env python3
"""Write the configs of wave 2 (code layout): what a stock-like Envoy build gives up, and how much of
the PGO gain comes without a training harness. Every binary is an own build of tag v1.40.2 with the
release options (`-c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib`,
//source/exe:envoy-static.stripped), pinned by sha256 in bins.json:

  opt            plain -c opt; byte-identical to the official v1.40.2 release asset, so the box's
                 ~/epl/bin/envoy-1.40.2 is used (the base and, as opt-A2, the A/A arm)
  order          the opt objects relinked with an lld call-graph ordering file (cdsort) computed from
                 LBR call edges of opt on the three shapes below
  autofdo        sampled PGO: llvm-profgen on the same LBR samples, -fprofile-sample-use + ThinLTO
  pgolto         instrumented PGO (the nine-leg trainer of pgo-recipe-v1) + ThinLTO
  pgolto-relocs  pgolto relinked with --emit-relocs, debug info stripped: the BOLT input (profiled only)
  bolt           optional: llvm-bolt on pgolto-relocs with the LBR profile from lbr-w2

    python3 examples/wave2/make.py [--box BOX_JSON] [--bins BINS_JSON]

Configs (in a directory named after the box):
  lbr-w2.json        profiling legs (two legs per shape, two processes of one binary, order fixed,
                     smoke): `perf record -b` of pgolto-relocs (the BOLT input) through perf-lbr.sh,
                     30 s window each
  lbr-w2-opt.json    the same for opt, only if the AutoFDO profile from track A's 20 s legs fails its
                     quality gate
  smoke-w2.json, w2.json            the A/B run with bolt: opt (base), opt-A2, order, autofdo, pgolto,
                     bolt; shapes s, fh, fl (as track A); 6 rounds = one Latin square of 6 arms;
                     perf event groups rotated by round (TMA level 1 user / i-cache)
  smoke-w2-nobolt.json, w2-nobolt.json   the same without bolt: 5 arms, 6 rounds (a 6-round
                     rotation block: round 6 repeats round 1's order)

Each smoke is one round of its run with evidence recorded; the run is checked against the frozen
smoke (run-w2.sh).
"""

import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl.envoy_config import _headers  # noqa: E402

RUNS = "~/epl/runs/wave2"
ORDER_SEED = 52
ROUNDS = 6
CLIENT = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"  # the box's working client (track A)
# Two event groups, rotated by round: every leg carries instructions:u, cycles:u and cycles:k (so
# cycles_total is the primary metric in every leg), plus at most 3 more programmable counters
# (cycles:k takes one of the 4). The groups are track A's decisive ones:
#   GA = A's G2: TMA level 1 user (frontend bound = idq_uops_not_delivered.core / (4 x cycles:u))
#   GB = i-cache misses and stall cycles, front-end resteers (A's G5/G6/G4 mix)
GROUPS = [
    "instructions:u,cycles:u,cycles:k,idq_uops_not_delivered.core:u,uops_issued.any:u,uops_retired.retire_slots:u",
    "instructions:u,cycles:u,cycles:k,icache.misses:u,icache.ifdata_stall:u,baclears.any:u",
]
# track A's shapes and rates, verbatim (the order and AutoFDO profiles come from these shapes)
FL_ROUTE = {"match": {"path": "/fl"}, "route": {"cluster": "origin", "prefix_rewrite": "/s"},
            "request_headers_to_add": _headers("req", 57), "response_headers_to_add": _headers("rsp", 52)}
SHAPES = [
    {"name": "s", "kind": "proxied", "path": "/s", "body_bytes": 4096, "rps": 5200},
    {"name": "fh", "kind": "direct_headers", "path": "/fh", "body_bytes": 128, "request_headers_added": 57,
     "response_headers_added": 52, "rps": 8000},
    {"name": "fl", "kind": "routes", "path": "/fl", "rps": 5200, "route_table": {"routes": [FL_ROUTE]}},
]
EV = [{"stat": "http.ingress_http.downstream_rq_2xx", "scope": "leg", "min": 1}]


def base(box, name):
    return {
        "name": name, "machine_label": box["machine_label"], "workdir": RUNS,
        "envoy": {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True,
                  "log_level": "warn", "codec_type": "HTTP1"},
        "cpus": dict(box["cpus"]),
        "client": {"binary": CLIENT, "concurrency": 16, "connections_per_worker": 32, "warmup_s": 5,
                   "duration_s": 25, "idle_strategy": "poll", "open_loop": True,
                   "extra_args": ["--prefetch-connections", "--max-pending-requests", "1000",
                                  "--experimental-h1-connection-reuse-strategy", "lru"]},
        "idle": {"max_load1": 8.0, "max_busy_pct": 2.0},
        "origin": {"mode": "docker", "port": 8092, "workers": 8, "image": box["origin_image"],
                   "platform": box["image_platform"]},
        "primary_metric": "cycles_total", "comparisons": "all_pairs", "base_arm": "opt",
        "shapes": copy.deepcopy(SHAPES), "shape_order": "latin", "adaptive": False, "order": "latin", "order_seed": ORDER_SEED,
    }


def arm(bins, name, build):
    b = bins[build]
    if not b.get("source_sha256") or "PENDING" in b["source_sha256"]:
        raise SystemExit("bins.json: no sha256 for %s yet" % build)
    return {"name": name, "binary": b["binary"], "source": b["source"], "source_sha256": b["source_sha256"],
            "build": build, "evidence": copy.deepcopy(EV)}


def ab_configs(box, bins, stem, names):
    builds = {"opt-A2": "opt"}
    arms = [arm(bins, n, builds.get(n, n)) for n in names]
    out = {}
    for smoke in (True, False):
        c = base(box, ("smoke-" if smoke else "") + stem)
        # 6 rounds for every run: the harness's minimum of 6 pairs, 3 rounds per event group, one
        # Latin square of 6 arms (w2); with 5 arms (w2-nobolt) a 6-round block, so round 6 repeats
        # round 1's arm order
        c.update(arms=copy.deepcopy(arms), rounds=1 if smoke else ROUNDS, rounds_block=1 if smoke else ROUNDS,
                 rounds_max=1 if smoke else ROUNDS,
                 measure={"lead_in_s": 2, "window_s": 20, "perf": box["perf"], "perf_event_groups": GROUPS})
        if smoke:
            c.update(smoke=True, evidence_mode="record", order="fixed")
        elif len(arms) != ROUNDS:
            c["rotation_block"] = ROUNDS
        out[c["name"] + ".json"] = c
    return out


def w2b_configs(box, bins):
    """W2B, the follow-up run: shape s only, 6 arms in a Williams square (balanced first-order carryover),
    one unscored warm-up leg of the base arm before every round, base pgolto with an A/A copy."""
    names = ["pgolto", "pgolto-A2", "pgolto-relocs", "bolt", "autofdo", "autofdo-order"]
    builds = {"pgolto-A2": "pgolto"}
    arms = [arm(bins, n, builds.get(n, n)) for n in names]
    s = [copy.deepcopy(x) for x in SHAPES if x["name"] == "s"]
    out = {}
    for smoke in (True, False):
        c = base(box, ("smoke-" if smoke else "") + "w2b")
        c.update(arms=copy.deepcopy(arms), base_arm="pgolto", shapes=s, warmup_legs=1, order_seed=62,
                 rounds=1 if smoke else ROUNDS, rounds_block=1 if smoke else ROUNDS, rounds_max=1 if smoke else ROUNDS,
                 measure={"lead_in_s": 2, "window_s": 20, "perf": box["perf"], "perf_event_groups": GROUPS})
        c.pop("shape_order", None)
        if smoke:
            c.update(smoke=True, evidence_mode="record", order="fixed")
        else:
            c["order"] = "williams"
        out[c["name"] + ".json"] = c
    return out


def lbr_config(box, bins, name, build, perf_wrapper):
    c = base(box, name)
    c.pop("comparisons")
    a = arm(bins, build, build)
    # a second arm is required by the schema; the A/A copy also checks the wrapper on a second process
    c.update(arms=[a, dict(copy.deepcopy(a), name=build + "-2")], base_arm=build, smoke=True, order="fixed",
             rounds=1, rounds_max=1, rounds_block=1, comparisons="base", evidence_mode="record",
             measure={"lead_in_s": 2, "window_s": 30, "perf": perf_wrapper})
    c["client"]["duration_s"] = 35
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", default=os.path.join(HERE, "..", "stats-flush", "boxes", "bench-x86_64.json"))
    ap.add_argument("--bins", default=os.path.join(HERE, "bins.json"))
    ap.add_argument("--perf-wrapper", default="~/epl/runs/wave2-prof/perf-lbr.sh",
                    help="where run-w2.sh prof installs perf-lbr.sh on the box")
    a = ap.parse_args()
    with open(a.box) as f:
        box = json.load(f)
    with open(a.bins) as f:
        bins = json.load(f)
    d = os.path.join(HERE, box["name"])
    os.makedirs(d, exist_ok=True)
    def ready(*builds):  # a config is written only when every binary it runs is pinned
        return all("PENDING" not in bins.get(b, {}).get("source_sha256", "PENDING") for b in builds)
    cfgs = {}
    nobolt = ["opt", "opt-A2", "order", "autofdo", "pgolto"]
    if ready("pgolto-relocs"):
        cfgs["lbr-w2.json"] = lbr_config(box, bins, "lbr-w2", "pgolto-relocs", a.perf_wrapper)
    if ready("opt"):
        cfgs["lbr-w2-opt.json"] = lbr_config(box, bins, "lbr-w2-opt", "opt", a.perf_wrapper)
    if ready("opt", "order", "autofdo", "pgolto"):
        cfgs.update(ab_configs(box, bins, "w2-nobolt", nobolt))
    if ready("opt", "order", "autofdo", "pgolto", "bolt"):
        cfgs.update(ab_configs(box, bins, "w2", nobolt + ["bolt"]))
    if ready("pgolto", "pgolto-relocs", "bolt", "autofdo", "autofdo-order"):
        cfgs.update(w2b_configs(box, bins))
    for fn, c in sorted(cfgs.items()):
        with open(os.path.join(d, fn), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
    print("%s: %d configs (%s)" % (box["name"], len(cfgs), ", ".join(sorted(cfgs))))


if __name__ == "__main__":
    main()
