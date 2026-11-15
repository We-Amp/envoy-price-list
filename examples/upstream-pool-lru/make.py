#!/usr/bin/env python3
"""Write the upstream-pool LRU experiment configs:

    python3 examples/upstream-pool-lru/make.py BINARY MD5 LO_RPS HI_RPS

One patched binary serves every arm: ENVOY_EXP_UPSTREAM_POOL_LRU=1 makes Envoy's
upstream connection pool attach a new stream to the least recently freed ready
connection instead of the most recently freed one (the default).

  two-hop.json   client -> hop A -> hop B -> origin. Arm "mru": default pool on both
                 hops. Arm "lru": the variable on hop A only, so hop B (and its own
                 pool towards the origin) is the same in both arms and only the way
                 hop A spreads its requests over hop B's connections changes.
                 Primary: cycles per request of both hops together. The worker-share
                 gate stays on for hop B in the LRU arm and is off (recorded) in the
                 MRU arm, whose hop B concentrates by construction.
  one-hop.json   client -> Envoy -> origin, MRU against LRU: what LRU costs a hop that
                 has no Envoy behind it.
  probe-*.json   the same arms for the saturation probe (`epl probe`).
"""

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "settings-matrix"))
import make as sm  # noqa: E402

LRU = {"ENVOY_EXP_UPSTREAM_POOL_LRU": "1"}


def main():
    binary, md5, lo, hi = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    base = copy.deepcopy(sm.BASE)
    base.pop("floor_from")
    base.update(workdir="~/epl/runs/lru", rounds=12, rounds_block=6, rounds_max=24,
                stop={"target_half_width_pct": 1.5}, comparisons="base", base_arm="mru",
                order_seed=20261114)
    bin_ = {"binary": binary, "md5": md5,
            "source": "envoy v1.40.2 + an experimental upstream pool reuse-order patch, -c opt, stripped"}
    shapes = [{"name": "s-lo", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": lo},
              {"name": "s-hi", "path": "/s4", "kind": "proxied", "body_bytes": 4096, "rps": hi}]
    out = {}

    two = copy.deepcopy(base)
    two.update(name="lru-two-hop", primary_metric="cycles_total_all", shapes=shapes,
               cpus=dict(base["cpus"], hop2="4-7"))
    two["arms"] = [
        dict(bin_, name="mru", settings={"two_hop": True}, validity={"hop2_worker_share_gate": False}),
        dict(bin_, name="lru", settings={"two_hop": True}, env=dict(LRU), hop2_env={}),
    ]
    out["two-hop.json"] = two

    one = copy.deepcopy(base)
    one.update(name="lru-one-hop", primary_metric="cycles_total", shapes=shapes)
    one["arms"] = [dict(bin_, name="mru"), dict(bin_, name="lru", env=dict(LRU))]
    out["one-hop.json"] = one

    # saturation probe: one shape, its rate set per step by `epl probe --rps`; the gates
    # stay as recorded (a probe leg's verdict is reported next to its p99)
    for k, src in (("probe-two-hop.json", two), ("probe-one-hop.json", one)):
        p = copy.deepcopy(src)
        # The client stays at 16 x 32 connections: 16 x 64 (1024) failed client connections
        # (benchmark.pool_connection_failure) on every leg, the client stopped early and no leg
        # met its rate (run probe-two-hop-c64-aborted). The gates stay on; only valid legs count.
        p.update(name=src["name"] + "-sat",
                 shapes=[{"name": "s-sat", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": lo}])
        out[k] = p

    # probe with raised limits (same for both arms): the c64 probe failed on the client's
    # open-file soft limit of 1024 ("socket(2) failed ... Too many open files"), and at 16 x 32
    # the client's own pool overflowed from 9,600 req/s. The queue raises the soft limit to the
    # hard limit for every process (ulimit -n), the client gets 16 x 64 connections, and every
    # cluster of both hops gets circuit breakers of 1e6 instead of the default 1024.
    p = copy.deepcopy(out["probe-two-hop.json"])
    p["name"] = "lru-two-hop-sat-limits"
    p["client"] = dict(p["client"], connections_per_worker=64)
    p["envoy"] = dict(p["envoy"], circuit_breakers_max=1000000)
    out["probe-two-hop-limits.json"] = p

    for fn, c in out.items():
        with open(os.path.join(HERE, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
