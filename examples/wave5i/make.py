#!/usr/bin/env python3
"""Write the configs of wave 5 track I (arm64 on a Neoverse V2 cloud VM): the official arm64
v1.40.2 release against own builds of the same tag with the release options, pinned by sha256 in bins.json:

  official      release asset envoy-1.40.2-linux-aarch_64 (base; official-A2 is the A/A copy)
  order         own opt objects relinked with an lld call-graph ordering file (cdsort) from frame-pointer
                call chains of opt (= official when byte-identical) on the three shapes below (no LBR here)
  pgolto        instrumented PGO (nine-leg trainer of pgo-recipe-v1, trained on this VM) + ThinLTO
  pgolto-v2     pgolto + -mcpu=neoverse-v2 (same profile)
  opt           own -c opt build; an arm only when it is NOT byte-identical to official

    python3 examples/wave5i/make.py [--box BOX_JSON] [--bins BINS_JSON]

Configs (directory named after the box):
  fp-w5i.json            profiling legs: two legs per shape of the opt binary under perf-fp.sh (cycles:u
                         samples with frame-pointer call chains, 30 s window), order fixed, smoke
  smoke-w5i.json, w5i.json   the A/B run: shapes s, fh, fl (W2's, verbatim); Williams order over the arms
                         (5 arms: 10 rounds; 6 arms: 12 rounds = 2 squares); event groups rotated by round
"""

import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl.envoy_config import _headers  # noqa: E402

RUNS = "~/epl/runs/wave5i"
ORDER_SEED = 515
# Every leg: instructions:u, cycles:u (cycle counter), cycles:k, plus 2 more; the guest has 4 programmable
# counters plus the cycle counter (checked on the VM: both groups count at 100%, no multiplexing).
GROUPS = [
    "instructions:u,cycles:u,cycles:k,stall_frontend:u,stall_backend:u",
    "instructions:u,cycles:u,cycles:k,l1i_cache_refill:u,l1i_tlb_refill:u",
]
FL_ROUTE = {"match": {"path": "/fl"}, "route": {"cluster": "origin", "prefix_rewrite": "/s"},
            "request_headers_to_add": _headers("req", 57), "response_headers_to_add": _headers("rsp", 52)}
SHAPES = [
    {"name": "s", "kind": "proxied", "path": "/s", "body_bytes": 4096, "rps": 5200},
    {"name": "fh", "kind": "direct_headers", "path": "/fh", "body_bytes": 128, "request_headers_added": 57,
     "response_headers_added": 52, "rps": 5200},
    {"name": "fl", "kind": "routes", "path": "/fl", "rps": 5200, "route_table": {"routes": [FL_ROUTE]}},
]
EV = [{"stat": "http.ingress_http.downstream_rq_2xx", "scope": "leg", "min": 1}]


def base(box, name):
    return {
        "name": name, "machine_label": box["machine_label"], "workdir": RUNS,
        "envoy": {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True,
                  "log_level": "warn", "codec_type": "HTTP1", "nofile": 65536},
        "cpus": dict(box["cpus"]),
        "client": {"binary": box["client_binary"], "concurrency": 8, "connections_per_worker": 64, "warmup_s": 5,
                   "duration_s": 25, "idle_strategy": "poll", "open_loop": True, "nofile": 65536,
                   "extra_args": ["--prefetch-connections", "--max-pending-requests", "1000",
                                  "--experimental-h1-connection-reuse-strategy", "lru"]},
        "idle": {"max_load1": 8.0, "max_busy_pct": 2.0},
        "validity": {"max_steal_share": 0.02, "max_non2xx": 0},
        "origin": {"mode": "docker", "port": 8092, "workers": 4, "image": box["origin_image"],
                   "platform": box["image_platform"]},
        "primary_metric": "cycles_total", "comparisons": "all_pairs", "base_arm": "official",
        "shapes": copy.deepcopy(SHAPES), "shape_order": "latin", "adaptive": False, "order": "williams",
        "order_seed": ORDER_SEED,
    }


def arm(bins, name, build):
    b = bins[build]
    if not b.get("source_sha256") or "PENDING" in b["source_sha256"]:
        raise SystemExit("bins.json: no sha256 for %s yet" % build)
    return {"name": name, "binary": b["binary"], "source": b["source"], "source_sha256": b["source_sha256"],
            "build": build, "evidence": copy.deepcopy(EV)}


def ab_configs(box, bins, names):
    builds = {"official-A2": "official"}
    arms = [arm(bins, n, builds.get(n, n)) for n in names]
    k = len(arms)
    rounds = 2 * k if k % 2 else 2 * k  # odd k: one full Williams design (2k); even k: two squares (2k)
    out = {}
    for smoke in (True, False):
        c = base(box, ("smoke-" if smoke else "") + "w5i")
        c.update(arms=copy.deepcopy(arms), rounds=1 if smoke else rounds, rounds_block=1 if smoke else rounds,
                 rounds_max=1 if smoke else rounds,
                 measure={"lead_in_s": 2, "window_s": 20, "perf": box["perf"], "perf_event_groups": GROUPS})
        if smoke:
            c.update(smoke=True, evidence_mode="record", order="fixed")
        out[c["name"] + ".json"] = c
    return out


def fp_config(box, bins, build, perf_wrapper):
    c = base(box, "fp-w5i")
    c.pop("comparisons")
    a = arm(bins, build, build)
    c.update(arms=[a, dict(copy.deepcopy(a), name=build + "-2")], base_arm=build, smoke=True, order="fixed",
             rounds=1, rounds_max=1, rounds_block=1, comparisons="base", evidence_mode="record",
             measure={"lead_in_s": 2, "window_s": 30, "perf": perf_wrapper})
    c["client"]["duration_s"] = 35
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", default=os.path.join(HERE, "boxes", "arm-vm-w5i.json"))
    ap.add_argument("--bins", default=os.path.join(HERE, "bins.json"))
    ap.add_argument("--perf-wrapper", default="~/epl/runs/wave5i-prof/perf-fp.sh")
    a = ap.parse_args()
    box = json.load(open(a.box))
    bins = json.load(open(a.bins))
    d = os.path.join(HERE, box["name"])
    os.makedirs(d, exist_ok=True)

    def ready(*builds):
        return all("PENDING" not in bins.get(b, {}).get("source_sha256", "PENDING") for b in builds)
    cfgs = {}
    if ready("opt"):
        cfgs["fp-w5i.json"] = fp_config(box, bins, "opt", a.perf_wrapper)
    names = ["official", "official-A2", "order", "pgolto", "pgolto-v2"]
    if bins.get("opt", {}).get("identical_to_official") is False:
        names.append("opt")
    if ready(*[n for n in names if n != "official-A2"]):
        cfgs.update(ab_configs(box, bins, names))
    for fn, c in sorted(cfgs.items()):
        with open(os.path.join(d, fn), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
    print("%s: %d configs (%s)" % (box["name"], len(cfgs), ", ".join(sorted(cfgs))))


if __name__ == "__main__":
    main()
