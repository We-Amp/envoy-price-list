#!/usr/bin/env python3
"""Top-down study (track A) configs: counter census (topdown-a) and LBR recording (lbr-a).

    python3 examples/topdown/make.py [--perf PERF] [--lbr-wrapper PATH]

Writes topdown-a.json and lbr-a.json next to this file.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl.envoy_config import _headers  # noqa: E402


# 8 groups, rotated by round (round r counts group (r-1) % 8 on every arm and shape).
# Each: 2 fixed counters (instructions:u, cycles[:u]) + at most 4 programmable (cycles:k counts as one).
GROUPS = [
    # G1 TMA level 1, user + kernel (as `perf stat -M TopdownL1` would count it)
    "instructions:u,cycles,idq_uops_not_delivered.core,uops_issued.any,uops_retired.retire_slots,"
    "int_misc.recovery_cycles",
    # G2 TMA level 1, user only (recovery cycles in G3)
    "instructions:u,cycles:u,cycles:k,idq_uops_not_delivered.core:u,uops_issued.any:u,uops_retired.retire_slots:u",
    # G3 fetch latency, recovery, branch mispredicts (user)
    "instructions:u,cycles:u,cycles:k,idq_uops_not_delivered.cycles_0_uops_deliv.core:u,int_misc.recovery_cycles:u,"
    "br_misp_retired.all_branches:u",
    # G4 machine clears, microcode uops, branch resteers (user)
    "instructions:u,cycles:u,cycles:k,machine_clears.count:u,idq.ms_uops:u,baclears.any:u",
    # G5 iTLB walks and i-cache stall cycles (user)
    "instructions:u,cycles:u,cycles:k,itlb_misses.walk_duration:u,itlb_misses.walk_completed:u,icache.ifdata_stall:u",
    # G6 uop source: DSB vs MITE, i-cache misses (user)
    "instructions:u,cycles:u,cycles:k,idq.dsb_uops:u,idq.mite_uops:u,icache.misses:u",
    # G7 data side: L1d lines replaced, L2 misses, LLC misses (user)
    "instructions:u,cycles:u,cycles:k,l1d.replacement:u,l2_rqsts.miss:u,longest_lat_cache.miss:u",
    # G8 backend: memory stall cycles, store-buffer stalls, all stall cycles (user)
    "instructions:u,cycles:u,cycles:k,cycle_activity.stalls_mem_any:u,resource_stalls.sb:u,"
    "cycle_activity.stalls_total:u",
]
# perf 6.8 of the bench box (the kernel's linux-tools perf); override with --perf
PERF = "/usr/lib/linux-tools/6.8.0-149-generic/perf"
ARMS = [
    {"name": "stock", "binary": "~/epl/bin/envoy-1.40.2",
     "source": "https://github.com/envoyproxy/envoy/releases/download/v1.40.2/envoy-1.40.2-linux-x86_64",
     "source_sha256": "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc"},
    {"name": "pgolto", "binary": "~/epl/bins/pgolto/envoy-pgolto-prodalloc", "md5": "3e5ee6b301d01089d013fd45cc2f7f5b",
     "commit": "24a950b647"},
]
# /fl: the /fh header sets (same generator, 57 request + 52 response headers) on a proxied route
# to the origin's /s file (4 KB). The harness serves origin files only for proxied shapes, so
# the 64 KB body of the old /fl is not available without a fourth measured shape.
FL_ROUTE = {"match": {"path": "/fl"}, "route": {"cluster": "origin", "prefix_rewrite": "/s"},
            "request_headers_to_add": _headers("req", 57), "response_headers_to_add": _headers("rsp", 52)}
SHAPES = [
    {"name": "s", "kind": "proxied", "path": "/s", "body_bytes": 4096, "rps": 5200},
    {"name": "fh", "kind": "direct_headers", "path": "/fh", "body_bytes": 128, "request_headers_added": 57,
     "response_headers_added": 52, "rps": 8000},
    {"name": "fl", "kind": "routes", "path": "/fl", "rps": 5200, "route_table": {"routes": [FL_ROUTE]}},
]
BASE = {
    "machine_label": "2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off; "
                     "Envoy on 4 cores with their SMT siblings left idle",
    "workdir": "~/epl/runs/topdown-a",
    "envoy": {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True,
              "log_level": "warn", "codec_type": "HTTP1"},
    "cpus": {"sut": "0-3", "client": "20-31,60-71", "origin": "32-39,72-79"},
    "client": {"binary": "~/nighthawk-dogfood/bazel-bin/nighthawk_client", "concurrency": 16,
               "connections_per_worker": 32, "warmup_s": 5, "duration_s": 25, "idle_strategy": "poll",
               "open_loop": True,
               "extra_args": ["--prefetch-connections", "--max-pending-requests", "1000",
                              "--experimental-h1-connection-reuse-strategy", "lru"]},
    "idle": {"max_load1": 8.0, "max_busy_pct": 2.0},
    "origin": {"mode": "docker", "port": 8092, "workers": 8,
               "image": "nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11"},
    "primary_metric": "cycles_total", "comparisons": "base", "base_arm": "stock",
    "arms": ARMS, "shapes": SHAPES, "adaptive": False, "order": "auto",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perf", default=PERF, help="perf binary on the bench box (topdown-a)")
    ap.add_argument("--lbr-wrapper", default="~/epl/runs/topdown-a/perf-lbr.sh",
                    help="where perf-lbr.sh is installed on the bench box (lbr-a)")
    a = ap.parse_args()
    td = dict(BASE, name="topdown-a", order_seed=21, rounds=24, rounds_max=24, rounds_block=6,
              measure={"lead_in_s": 2, "window_s": 20, "perf": a.perf, "perf_event_groups": GROUPS})
    # LBR legs: the perf "binary" is a wrapper that runs `perf stat` (default events) over a
    # `perf record -b` of the same PID for the same window.
    lbr = dict(BASE, name="lbr-a", smoke=True, order="fixed", rounds=1, rounds_max=1, rounds_block=1,
               measure={"lead_in_s": 2, "window_s": 20, "perf": a.lbr_wrapper})
    for n, e in (("topdown-a.json", td), ("lbr-a.json", lbr)):
        with open(os.path.join(HERE, n), "w") as f:
            json.dump(e, f, indent=1, sort_keys=True)
            f.write("\n")
    print("ok")


if __name__ == "__main__":
    main()
