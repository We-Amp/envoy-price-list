#!/usr/bin/env python3
"""Write the burst-recovery configs (run after make_demand.py):

    python3 examples/upstream-pool-lru/make_burst.py

Starts from demand-pool.json (two hops, ramped client, so the pool is grown by
demand), at 5,200 req/s only. Inside a 135 s perf window the harness samples both
hops once a second and, 10 s in, freezes the second hop for 40 ms (SIGSTOP and
SIGCONT to the PID it started; `measure.burst`). Requests that arrive at the first
hop during the freeze find no free connection, so its pool grows by about
rate x stall under live traffic (the chain stalls for longer than the pause).
The 125 s after the freeze show how each arm recovers. Client at 16 x 64
connections and breakers of 1e6 on both hops, so neither limits the stall.

  burst.json        six arms, one binary; exact_balance on hop B unless named:
                      mru         stock order (most recently freed)
                      lru         ENVOY_EXP_UPSTREAM_POOL_LRU=1 on hop A
                      mru-maxreq  hop A's cluster: max_requests_per_connection 1000
                      mru-maxdur  hop A's cluster: max_connection_duration 30 s
                      lru-noeb    LRU on hop A, hop B without exact_balance
                      mru-idle5   hop A's cluster: idle_timeout 5 s
                    12 rounds (the rotation's balance period for 6 arms), fixed.
  burst-smoke.json  mru and lru, a 40 s window, 2 rounds (mechanism check only).
"""

import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LEAD_IN_S = 12          # 2 s ramp, then 10 s at the steady rate
WINDOW_S = 135
BURST = {"at_s": 10, "pause_hop2_ms": 40, "sample_s": 1.0}


def main():
    with open(os.path.join(HERE, "demand-pool.json")) as f:
        dem = json.load(f)
    base = copy.deepcopy(dem)
    base["shapes"] = [s for s in dem["shapes"] if s["name"] == "s-lo"]
    base["measure"] = dict(base["measure"], lead_in_s=LEAD_IN_S, window_s=WINDOW_S, burst=dict(BURST))
    # the freeze stalls the chain for longer than the pause itself (about 0.1 s on the smoke legs),
    # which overran the client's 32 connections per worker; 64 cover it (the queue script raises the
    # open-files soft limit for 16 x 64 client connections), and breakers of 1e6 on every cluster
    # of both hops keep any pool or request limit out of the leg (as in probe-two-hop-limits.json)
    base["client"] = dict(base["client"], duration_s=LEAD_IN_S + WINDOW_S + 3, connections_per_worker=64)
    base["envoy"] = dict(base["envoy"], circuit_breakers_max=1000000)
    base["rounds"] = base["rounds_max"] = base["rounds_block"] = 12
    base["adaptive"] = False
    base["order"] = "rotate"
    base["order_seed"] = 20261115
    arms = {a["name"]: a for a in dem["arms"]}
    mru, lru = copy.deepcopy(arms["mru"]), copy.deepcopy(arms["lru"])

    def mru_with(name, **uh):
        a = copy.deepcopy(mru)
        a["name"] = name
        a["settings"] = dict(a["settings"], upstream_http=uh)
        return a

    noeb = copy.deepcopy(lru)
    noeb["name"] = "lru-noeb"
    noeb["settings"] = dict(noeb["settings"], hop2_settings={"exact_balance": False})
    b = copy.deepcopy(base)
    b["name"] = "lru-burst"
    b["arms"] = [mru, lru, mru_with("mru-maxreq", max_requests=1000),
                 mru_with("mru-maxdur", max_connection_duration_s=30), noeb,
                 mru_with("mru-idle5", idle_timeout_s=5)]
    out = {"burst.json": b}
    sm = copy.deepcopy(base)
    sm["name"] = "lru-burst-smoke"
    sm["arms"] = [copy.deepcopy(mru), copy.deepcopy(lru)]
    sm["order"] = "auto"
    sm["rounds"] = sm["rounds_max"] = sm["rounds_block"] = 2
    sm["measure"] = dict(sm["measure"], window_s=40)
    sm["client"] = dict(sm["client"], duration_s=LEAD_IN_S + 40 + 3)
    out["burst-smoke.json"] = sm
    for fn, c in out.items():
        with open(os.path.join(HERE, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
