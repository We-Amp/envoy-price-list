#!/usr/bin/env python3
"""Wave 7, session S4b: one more arm for candidate 2, the PGO + ThinLTO build whose profile comes from Envoy's
integration tests alone. Pre-registered after S4 (kept share 44.0% on s, 45.4% on fh: under the
50% line, inside the 40-60% window).

    python3 examples/wave7s4b/make.py

One run, the rig, shapes, rates, leg length and rounds of S4's s4b-pgo:
  it-pgo.json        4 arms, 8 rounds (two Williams squares), seed 733, shapes s (5,200 req/s) and fh (8,000
                     req/s), shape order rotates by round:
                       official          the official v1.40.2 release (base)
                       pgolto-trainer    wave 2's PGO + ThinLTO build (trainer profile)
                       pgolto-tests      the same options, profile from 12 integration + 10 benchmark tests
                       pgolto-tests-it   the same options, profile from the 12 integration tests alone
                     No same-build A/A arm: a fifth arm needs ten rounds in Williams order. S4's s4b-pgo A/A
                     (both shapes passed) is the reference, and the three repeated arms are the
                     session-to-session check.
  smoke-it-pgo.json  one round of every arm (order fixed), evidence recorded
"""
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "configs")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


m4 = _load("w7s4_make_for_s4b", os.path.join(HERE, "..", "wave7s4", "make.py"))
RUNS = "~/epl/runs/wave7s4b"
SEED = 733
with open(os.path.join(HERE, "bins.json")) as _f:
    BINS = json.load(_f)
CONF = [["pgolto-trainer", "official"], ["pgolto-tests-it", "official"], ["pgolto-tests", "official"],
        ["pgolto-tests-it", "pgolto-tests"], ["pgolto-tests-it", "pgolto-trainer"]]


def arm(name, build, ev):
    b = BINS[build]
    return {"name": name, "binary": b["binary"], "source": b["source"], "source_sha256": b["source_sha256"],
            "build": build, "evidence": json.loads(json.dumps(ev))}


def it(name):
    c = m4.base(name, "s4b")
    S = m4.sm.shapes({})
    ev = m4.COMMON + m4.EV_GUARD_DEFAULT
    c.update(workdir=RUNS, order_seed=SEED, base_arm="official", shapes=[S["s"], S["fh"]],
             arms=[arm("official", "official", ev), arm("pgolto-trainer", "trainer", ev),
                   arm("pgolto-tests", "tests", ev), arm("pgolto-tests-it", "tests-it", ev)],
             confirmatory=CONF)
    return c


def configs():
    return {"it-pgo": it("it-pgo"), "smoke-it-pgo": m4.as_one_round(it("smoke-it-pgo"))}


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn, c in sorted(configs().items()):
        with open(os.path.join(OUT, fn + ".json"), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
        print(fn + ".json")


if __name__ == "__main__":
    main()
