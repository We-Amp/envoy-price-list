#!/usr/bin/env python3
"""Exit 0 when every leg of a smoke run is valid (the latest attempt of each rung, arm and round,
and every rung and arm of its config present); else print each invalid or missing leg with its
reasons and exit 1. A queue that starts only after a clean smoke uses it.

    python3 examples/stats-mt/smoke_valid.py SMOKE_CFG SMOKE_DIR
"""

import json
import os
import sys


def check(cfg, res):
    legs = {}
    for m in res.get("legs", []):
        legs[(m.get("shape"), m.get("arm"), m.get("round"))] = m
    probs = []
    for sh in cfg["shapes"]:
        for a in cfg["arms"]:
            got = [m for (s, ar, r), m in legs.items() if s == sh["name"] and ar == a["name"]]
            if not got:
                probs.append("missing: %s %s" % (sh["name"], a["name"]))
            for m in got:
                v = m.get("verdict") or {}
                if not v.get("valid"):
                    probs.append("invalid: %s %s: %s" % (sh["name"], a["name"], "; ".join(v.get("reasons") or [])))
    return probs


def main():
    cfg = json.load(open(sys.argv[1]))
    p = os.path.join(sys.argv[2], "results.json")
    if not os.path.exists(p):
        print("no results.json in %s" % sys.argv[2])
        return 1
    probs = check(cfg, json.load(open(p)))
    for x in probs:
        print(x)
    print("smoke %s" % ("all legs valid" if not probs else "NOT clean (%d problems)" % len(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
