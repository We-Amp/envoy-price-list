#!/usr/bin/env python3
"""Write the demand-grown pool follow-up configs (run after make.py):

    python3 examples/upstream-pool-lru/make_demand.py

Same topology, binary, rates and client as two-hop.json. What changes: the client
ramps its rate linearly over the first RAMP_S seconds of both the warm-up and the
measured run (Nighthawk's linear ramping rate limiter), so a start-of-run stall
cannot release a burst that grows hop A's upstream pool beyond what the load needs.
The window starts after the ramp (lead_in_s). The pool size of every leg is in its
end gauges (cluster.origin.upstream_cx_active on each hop) and hop B's per-worker
listener gauges.

  demand-pool.json     arms (a) mru: MRU, exact_balance on hop B (the harness default)
                            (b) mru-noeb: MRU, exact_balance off on hop B
                            (c) lru: LRU on hop A, exact_balance on hop B
                       hop B's share gate is off in every arm: its spread is an outcome here.
  demand-pool-ka.json  arms (a) and (c) at the high rate only, with ordinary keep-alive
                       settings on hop A's peer (hop B's listener: idle timeout 60 s,
                       1000 requests per connection) and on the origin (nginx
                       keepalive_timeout 60s, keepalive_requests 1000).
"""

import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RAMP_S = 2
RAMP = json.dumps({"name": "nighthawk.linear-ramping-rate-limiter-plugin",
                   "typed_config": {"@type": "type.googleapis.com/nighthawk.rate_limiter.LinearRampingRateLimiterConfig",
                                    "ramp_time": "%ds" % RAMP_S}}, separators=(",", ":"))
KA = {"idle_timeout_s": 60, "max_requests": 1000}


def main():
    with open(os.path.join(HERE, "two-hop.json")) as f:
        two = json.load(f)
    base = copy.deepcopy(two)
    base["client"]["extra_args"] = list(base["client"]["extra_args"]) + ["--rate-limiter-plugin-config", RAMP]
    base["measure"] = dict(base["measure"], lead_in_s=RAMP_S + 1)
    base["order"] = "auto"  # three arms: rotate
    mru, lru = [copy.deepcopy(a) for a in two["arms"]]
    for a in (mru, lru):
        a["validity"] = {"hop2_worker_share_gate": False}
    noeb = copy.deepcopy(mru)
    noeb["name"] = "mru-noeb"
    noeb["settings"] = dict(noeb["settings"], hop2_settings={"exact_balance": False})
    out = {}
    d = copy.deepcopy(base)
    d["name"] = "lru-demand-pool"
    d["arms"] = [mru, noeb, lru]
    out["demand-pool.json"] = d

    k = copy.deepcopy(base)
    k["name"] = "lru-demand-pool-ka"
    k["shapes"] = [s for s in base["shapes"] if s["name"] == "s-hi"]
    k["origin"] = dict(k["origin"], keepalive_timeout_s=60, keepalive_requests=1000)
    ka_arms = []
    for a in (mru, lru):
        a = copy.deepcopy(a)
        a["settings"] = dict(a["settings"], hop2_settings={"downstream_keepalive": dict(KA)})
        ka_arms.append(a)
    k["arms"] = ka_arms
    out["demand-pool-ka.json"] = k

    for fn, c in out.items():
        with open(os.path.join(HERE, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
