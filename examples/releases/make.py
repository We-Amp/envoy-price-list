#!/usr/bin/env python3
"""Write the release back-fill: six official Envoy releases, two load levels, and an A/A
arm in the same run.

    python3 examples/releases/make.py [RATES_JSON]

  releases.json  v1.32.13, v1.34.14, v1.36.13, v1.37.11, v1.38.9, v1.40.2 (the newest
                 patch of each line, release lines about 3 to 6 months apart), plus a
                 second copy of v1.40.2 (`v1.40.2-A2`): the A/A of this session,
                 interleaved with the releases in every round. Shapes: the 4 KB
                 proxied request and the header-heavy direct response, each at the
                 settings-matrix rate (about 30% busy on four workers) and at a
                 second, higher rate (`s-hi`, `fh-hi`; RATES_JSON from calibration),
                 with the client's rate ramped over the first second.
                 Every release and the A/A arm is compared with v1.40.2.
  smoke.json     two rounds of two of the releases on the high-rate shapes

Same base, client, CPUs and generated bootstrap as the settings matrix (make.py
there), so the low-rate shapes of the v1.40.2 arms are the settings baseline. The
high-rate shapes use the same paths, so every shape shares one bootstrap per arm.
"""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("sm_make", os.path.join(HERE, "..", "settings-matrix", "make.py"))
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)

RUNS = "~/epl/runs/wk4"
GH = "https://github.com/envoyproxy/envoy/releases/download/v%s/envoy-%s-linux-x86_64"
# sha256 of each asset as the GitHub release lists it (the harness checks the binary against it)
RELEASES = [
    ("1.32.13", "27150dfd35c89b69e5db38366bca4025f30311416d83ea5f5b83cabc76613265"),
    ("1.34.14", "e20f33a568f83b3d927cdaa221f6e212851c49b8fc13f42ce2867365d8a4b2e0"),
    ("1.36.13", "df99ee307371c3e6f812844f23322732430d102775a73263cc3287984291f18c"),
    ("1.37.11", "b9ebeed3ba6febcc0943810bddc27f66807ceaf9b1538d3e6db14284fbcb1ce8"),
    ("1.38.9", "3c70be6f1c5704c1d78e034828a9ef9501fbd7b6ea7992c75b62f6b13846dcb4"),
    ("1.40.2", "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc"),
]
BASE_ARM = "v1.40.2"
# High-rate shapes: the client ramps its rate linearly over the first RAMP_S seconds of the
# warm-up and the measured run (Nighthawk's linear ramping rate limiter). Without it, at
# twice the matrix rates the requests issued while the 512 prefetched connections come up
# overflow the client pool at start-up. The perf window starts at lead_in_s (2 s), after the ramp.
RAMP_S = 1
RAMP = json.dumps({"name": "nighthawk.linear-ramping-rate-limiter-plugin",
                   "typed_config": {"@type": "type.googleapis.com/nighthawk.rate_limiter.LinearRampingRateLimiterConfig",
                                    "ramp_time": "%ds" % RAMP_S}}, separators=(",", ":"))
AA_ARM = "v1.40.2-A2"


def arm(v, sha, name=None):
    return {"name": name or "v" + v, "binary": "~/epl/bin/envoy-" + v, "source": GH % (v, v), "source_sha256": sha}


def shapes(rates):
    S = sm.shapes(rates)
    hi = lambda k, d: dict(S[k], name=k + "-hi", rps=int(rates.get(k + "-hi", d)),  # noqa: E731
                           client_extra_args=["--rate-limiter-plugin-config", RAMP])
    # calibration (2026-11-15, ramped client): s-hi 12000 = 61% busy on v1.40.2 (12800: 64%, p50 +41%,
    # the queueing knee); fh-hi 18400 between 17600 (53%) and 19200 (57%) on v1.32.13 (20800: busy
    # stops rising, p50 +18%)
    return {"s": S["s"], "fh": S["fh"], "s-hi": hi("s", 12000), "fh-hi": hi("fh", 18400)}


def configs(rates):
    S = shapes(rates)
    base = json.loads(json.dumps(sm.BASE))
    base.pop("floor_from")
    arms = [arm(v, h) for v, h in RELEASES] + [arm(*RELEASES[-1], name=AA_ARM)]
    rel = dict(base, workdir=RUNS, name="wk4-releases", base_arm=BASE_ARM, arms=arms,
               shapes=[S[k] for k in ("s", "fh", "s-hi", "fh-hi")],
               # rotate over 7 arms balances every 14 rounds; a new order seed, so this
               # session's schedule differs from the earlier release pilot's
               rounds=14, rounds_block=14, rounds_max=28, order_seed=4,
               stop={"target_half_width_pct": 1.5})
    smoke = dict(base, workdir=RUNS, name="wk4-releases-smoke", base_arm="v1.38.9",
                 arms=[arm(*RELEASES[1]), arm(*RELEASES[4])], shapes=[S["s-hi"], S["fh-hi"]],
                 rounds=2, rounds_block=2, rounds_max=2, adaptive=False)
    return {"releases.json": rel, "smoke.json": smoke}


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
