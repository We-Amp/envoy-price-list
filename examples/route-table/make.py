#!/usr/bin/env python3
"""Write the route-table and constant-header re-measure: recorded route tables and a
recorded 109-header route, three or four Envoy builds, two load levels.

    python3 examples/route-table/make.py [RATES_JSON]

The tables in tables/ are the ones the first end-to-end runs used (converted from their
YAML by tables/from_yaml.py; each keeps the md5 of its source):

  routes1.json, routes200.json, routes1000.json
      One virtual host with 8 response headers added and N direct-response routes. Routes
      1..N-1 are 60% prefix, 20% exact path and 20% safe_regex routes (seed 7), 30% of
      them also require a header the client never sends; route N is `prefix: /target/`.
      The request `GET /target/x` matches the last route, so every route before it is
      evaluated and rejected by a linear scan.
  fh109.json
      The direct-response route that adds 57 request headers and 52 response headers
      (54- and 62-byte constant values), under the same 8 virtual-host response headers.

Experiments (one run each, because each needs its own table):

  rt-n1000.json, rt-n200.json
      base, path first (D1 v4), an unpublished route index prototype (D2 v3) and a second copy of base
      (`base-A2`, the A/A of the run), at a low and a high rate.
  rt-n1.json
      the one-route control: base, D1 v4, D2 v3 (identical instructions expected).
  hdr.json
      base, the header change, and base-A2, on the 109-header route.
  smoke-rt.json, smoke-hdr.json
      two rounds of D1 v4 / D2 v3 on rt-n1000's shapes and of base / the header change
      on hdr's, for the gates.

The A/A floor of rt-n1000, rt-n200 and hdr is their own base-A2 arm:
`epl report RUN/results.json --floor RUN/results.json --floor-arm base-A2`.

Binaries are local builds (`-c opt`, stripped) whose md5 the config enforces; the
paths are the bench box's.
"""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("sm_make", os.path.join(HERE, "..", "settings-matrix", "make.py"))
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)

RUNS = "~/epl/runs/route-table"
BIN = "~/epl/bin/"
# name: (file, md5, commit)
BUILDS = {
    "base": ("envoy-routes-base", "e59880d7374383c6df4dcaad6c71dd7e", "8ce942ce56"),
    "d1v4": ("envoy-routes-path-first", "7fac057ec1629117f7ebcccfbf52b923", "28f612622a"),
    # an unpublished route index prototype, identified by its md5 only
    "d2v3": ("envoy-routes-index-prototype", "bf9fd4b39b85602a840480224fe3a1b2", "patched-build"),
    # the same base build under the header experiment's file name (same md5)
    "hbase": ("envoy-headers-base", "e59880d7374383c6df4dcaad6c71dd7e", "8ce942ce56"),
    # 60556c39ef: same tree as the published header branch commit 75887067de
    "s1": ("envoy-headers-reference", "a1da0f89183496870b9f9c1657bbe931", "60556c39ef"),
}
RAMP = json.dumps({"name": "nighthawk.linear-ramping-rate-limiter-plugin",
                   "typed_config": {"@type": "type.googleapis.com/nighthawk.rate_limiter.LinearRampingRateLimiterConfig",
                                    "ramp_time": "1s"}}, separators=(",", ":"))
# low = the rate of the first end-to-end runs; high = the rate of the second route run
# (22,000 and 16,000 req/s); the header route at 20,000 (calibration 2026-11-16, base: N=1000
# 16,000 = 67% busy, N=200 22,000 = 58%, fh109 20,000 = 56%)
DEFAULT_RATES = {"lo": 2000, "n1-hi": 22000, "n200-hi": 22000, "n1000-hi": 16000, "hdr-hi": 20000}


def table(name):
    with open(os.path.join(HERE, "tables", name + ".json")) as f:
        return json.load(f)


def arm(build, name=None):
    fn, md5, commit = BUILDS[build]
    return {"name": name or build, "binary": BIN + fn, "md5": md5, "commit": commit}


def shapes(prefix, path, tbl, lo, hi):
    base = {"path": path, "kind": "routes", "route_table": tbl}
    return [dict(base, name=prefix + "-lo", rps=int(lo)),
            dict(base, name=prefix + "-hi", rps=int(hi), client_extra_args=["--rate-limiter-plugin-config", RAMP])]


def configs(rates):
    R = dict(DEFAULT_RATES, **rates)
    base = json.loads(json.dumps(sm.BASE))
    base.pop("floor_from")
    base["workdir"] = RUNS
    # the Nighthawk build of the method-v2 runs (md5 310df412...)
    base["client"]["binary"] = "~/nighthawk/bazel-bin/nighthawk_client"
    # direct responses only: no origin starts
    route_arms = [arm("base"), arm("d1v4"), arm("d2v3"), arm("base", "base-A2")]
    out = {}
    for n, seed in (("1000", 11), ("200", 12)):
        out["rt-n%s.json" % n] = dict(
            base, name="rt-n" + n, base_arm="base", arms=route_arms,
            shapes=shapes("n" + n, "/target/x", table("routes" + n), R["lo"], R["n%s-hi" % n]),
            # rotate over 4 arms balances every 8 rounds
            rounds=16, rounds_block=8, rounds_max=24, order_seed=seed, stop={"target_half_width_pct": 1.5})
    out["rt-n1.json"] = dict(
        base, name="rt-n1", base_arm="base", arms=route_arms[:3],
        shapes=shapes("n1", "/target/x", table("routes1"), R["lo"], R["n1-hi"]),
        rounds=12, rounds_block=6, rounds_max=12, adaptive=False, order_seed=13)
    out["hdr.json"] = dict(
        base, name="hdr", base_arm="base", arms=[arm("hbase", "base"), arm("s1"), arm("hbase", "base-A2")],
        shapes=shapes("fh109", "/fh", table("fh109"), R["lo"], R["hdr-hi"]),
        rounds=12, rounds_block=6, rounds_max=36, order_seed=14, stop={"target_half_width_pct": 1.0})
    # smoke: two rounds of two arms each (abba), both rates; base is covered by hdr's base
    # (the same md5)
    rt = out["rt-n1000.json"]
    out["smoke-rt.json"] = dict(rt, name="smoke-rt", base_arm="d1v4", arms=route_arms[1:3],
                                rounds=2, rounds_block=2, rounds_max=2, adaptive=False)
    hd = out["hdr.json"]
    out["smoke-hdr.json"] = dict(hd, name="smoke-hdr", arms=hd["arms"][:2],
                                 rounds=2, rounds_block=2, rounds_max=2, adaptive=False)
    return out


def main():
    rates = {}
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            rates = json.load(f)
    for fn, c in configs(rates).items():
        with open(os.path.join(HERE, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
