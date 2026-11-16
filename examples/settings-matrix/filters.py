#!/usr/bin/env python3
"""Write two more settings rows, each against the settings-matrix baseline (make.py):

    python3 examples/settings-matrix/filters.py [RATES_JSON]

  11-jwt-authn        JWT authentication with a local JWKS (no fetch), RS256: every
                      token verified, and with the filter's cache of verified tokens
  12-local-ratelimit  local rate limit, one shared token bucket, enabled and enforced
                      on every request, with a budget far above the test rate
  smoke               two rounds of the JWT (cached) and rate-limit arms, to check the
                      arms boot, pass the gates and move their counters

Both rows run the 4 KB proxied shape and the header-heavy direct response at the
matrix rates. In the JWT row every arm's client sends the same Authorization header
(the token from filters/jwt.json, made by jwt_token.py), so the baseline carries the
same request bytes and only the filter differs; the filter forwards the header, so
the origin sees the same request too. The A/A floor comes from the second copy of
v1.40.2 in the release run of the same session (`floor_arm`), whose shapes and
baseline config are the same.
"""

import json
import os
import sys

import make

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "filters")
RUNS = "~/epl/runs/wk4"
F = dict(make.BASE, workdir=RUNS, floor_from=RUNS + "/releases/results.json", floor_arm="v1.40.2-A2")

with open(os.path.join(OUT, "jwt.json")) as f:
    JWT = json.load(f)
JWT_SETTING = {"jwks": JWT["jwks"], "issuer": JWT["issuer"], "audience": JWT["audience"]}
AUTH_HEADER = ["--request-header", "authorization:Bearer " + JWT["token"]]
# a budget about ten times the highest rate any shape runs at: nothing is rejected
RL_TOKENS_PER_S = 100000


def shapes(rates):
    S = make.shapes(rates)
    out = {"s": S["s"], "fh": S["fh"]}
    for k in ("s", "fh"):
        out[k + "-auth"] = dict(S[k], client_extra_args=list(AUTH_HEADER))
    return out


def configs(rates):
    S = shapes(rates)
    out = {}

    def row(fname, name, arms, shp, **kw):
        c = json.loads(json.dumps(F))
        c.update(name=name, base_arm=arms[0]["name"], arms=arms, shapes=[S[x] for x in shp])
        c.update(kw)
        out[fname] = c

    row("11-jwt-authn.json", "wk4-jwt-authn",
        [make.arm("jwt-off"), make.arm("jwt", {"jwt_authn": dict(JWT_SETTING)}),
         make.arm("jwt-cache", {"jwt_authn": dict(JWT_SETTING, cache=True)})], ["s-auth", "fh-auth"])
    row("12-local-ratelimit.json", "wk4-local-ratelimit",
        [make.arm("ratelimit-off"), make.arm("ratelimit-on", {"local_ratelimit": {"tokens_per_s": RL_TOKENS_PER_S}})],
        ["s", "fh"])
    row("smoke.json", "wk4-filters-smoke",
        [make.arm("jwt-cache", {"jwt_authn": dict(JWT_SETTING, cache=True)}),
         make.arm("ratelimit-on", {"local_ratelimit": {"tokens_per_s": RL_TOKENS_PER_S}})], ["s-auth", "fh-auth"],
        rounds=2, rounds_block=2, rounds_max=2, adaptive=False)
    out["smoke.json"].pop("floor_from")
    out["smoke.json"].pop("floor_arm")
    return out


def main():
    rates = {}
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            rates = json.load(f)
    for fn, c in configs(rates).items():
        with open(os.path.join(OUT, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
