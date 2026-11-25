#!/usr/bin/env python3
"""State rules on the S4b smoke directory, fixed before the run.

    s4b_check.py SMOKE_DIR     one line per leg; exit 1 when a rule fails

  binary    every arm started the binary its row assumes: the sha256 the run recorded for the arm equals the pin
            in bins.json, and the four pins are four different files
  profile   each profiled binary (pgolto-trainer, pgolto-tests, pgolto-tests-it) runs at least 5% fewer user
            instructions per request than official on at least one of the two shapes (both are printed): the
            profile took and the binary is not the official one under another name. When pgolto-tests-it misses
            the gate on both shapes the run is not scored (the session measures that arm)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = {"official": "official", "pgolto-trainer": "trainer", "pgolto-tests": "tests", "pgolto-tests-it": "tests-it"}
PROFILED = ("pgolto-trainer", "pgolto-tests", "pgolto-tests-it")


def latest(d):
    out, sup = {}, set()
    p = os.path.join(d, "legs.jsonl")
    if not os.path.exists(p):
        return out
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        m = json.loads(line)
        if "supersede" in m:
            sup.update(m["supersede"])
        elif m.get("arm") and m.get("leg_id") not in sup:
            out[(m.get("shape"), m["arm"])] = m
    return out


def arm_sha(d):
    try:
        md = json.load(open(os.path.join(d, "results.json"))).get("metadata") or {}
    except (OSError, ValueError):
        return {}
    return {k: (v or {}).get("sha256") for k, v in (md.get("arms") or {}).items()}


def check(d, bins):
    legs = latest(d)
    rows, bad = [], []
    if not legs:
        return ["no legs in %s" % d], ["no legs"]
    sha = arm_sha(d)
    for (sh, arm), m in sorted(legs.items()):
        pr = m.get("per_req") or {}
        ev = m.get("evidence") or {}
        rows.append("%s/%s: sha256 %s; responses in the window %s; non-2xx (Envoy) %s; cycles u+k per request %s, user "
                    "instructions per request %s; Envoy busy %s CPUs; valid %s, evidence %s%s" % (
                        sh, arm, (sha.get(arm) or "-")[:12], m.get("responses_raw"), m.get("sut_non2xx"),
                        pr.get("cycles_total"), pr.get("instructions_u"), m.get("envoy_cpus_run"),
                        (m.get("verdict") or {}).get("valid"), ev.get("ok"),
                        "" if ev.get("ok") is not False else " FAILED: " + "; ".join((ev.get("failed") or [])[:6])))
    pins = {a: bins[b]["source_sha256"] for a, b in BUILD.items()}
    if len(set(pins.values())) != len(pins):
        bad.append("two arms pin the same binary")
    for a, want in sorted(pins.items()):
        got = sha.get(a)
        rows.append("binary %s: started %s, pin %s: %s" % (a, got, want, "equal" if got == want else "DIFFERENT"))
        if got != want:
            bad.append("%s did not start its pinned binary" % a)
    for a in PROFILED:
        took = []
        for sh in sorted({k[0] for k in legs}):
            t = ((legs.get((sh, a)) or {}).get("per_req") or {}).get("instructions_u")
            o = ((legs.get((sh, "official")) or {}).get("per_req") or {}).get("instructions_u")
            if not t or not o:
                rows.append("%s: user instructions missing (%s %s, official %s)" % (sh, a, t, o))
                continue
            took.append(t <= 0.95 * o)
            rows.append("%s: user instructions per request, %s / official = %.4f (%+.2f%%; the gate wants -5%% or lower)" % (
                sh, a, t / o, 100.0 * (t / o - 1.0)))
        if not any(took):
            bad.append("%s runs under 5%% fewer user instructions per request than official on every shape: the "
                       "profile did not take, or the binary is not the profiled one" % a)
    return rows, bad


def main(argv):
    with open(os.path.join(HERE, "bins.json")) as f:
        bins = json.load(f)
    rows, bad = check(argv[0].rstrip("/"), bins)
    print("\n".join(rows))
    for b in bad:
        print("STATE RULE FAILED: " + b)
    print("s4b_check %s: %s" % (os.path.basename(argv[0].rstrip("/")), "OK" if not bad else "FAILED (%d)" % len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
