#!/usr/bin/env python3
"""State rules on an S4 smoke directory, fixed before the run (plan section 5).

    s4_check.py SMOKE_DIR     one line per leg; exit 1 when a rule fails

  every smoke     one line per leg: binary sha256 of the arm, valid, evidence, cycles and user instructions per
                  request, spans, the runtime key count
  smoke-s4b-pgo   the profile took: pgolto-tests runs at least 5% fewer user instructions per request than
                  official on at least one of the two shapes (both are printed). When it does on neither, the
                  arm is dropped, and with it the run (the session measures one tests-profile arm)."""
import json
import os
import sys


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
    """{arm: sha256 of the binary the run started} from the run's results.json metadata."""
    try:
        md = json.load(open(os.path.join(d, "results.json"))).get("metadata") or {}
    except (OSError, ValueError):
        return {}
    return {k: (v or {}).get("sha256") for k, v in (md.get("arms") or {}).items()}


def check(d):
    legs = latest(d)
    rows, bad = [], []
    if not legs:
        return ["no legs in %s" % d], ["no legs"]
    sha = arm_sha(d)
    for (sh, arm), m in sorted(legs.items()):
        pr = m.get("per_req") or {}
        cd = m.get("collector_delta") or {}
        ev = m.get("evidence") or {}
        rows.append("%s/%s: sha256 %s; cycles u+k per request %s, user instructions per request %s; spans accepted %s; "
                    "runtime.num_keys %s; Envoy busy %s CPUs; valid %s, evidence %s%s" % (
                        sh, arm, (sha.get(arm) or "-")[:12], pr.get("cycles_total"), pr.get("instructions_u"),
                        cd.get("accepted_spans", "-"), (m.get("sut_stats_leg_end") or {}).get("runtime.num_keys"),
                        m.get("envoy_cpus_run"), (m.get("verdict") or {}).get("valid"), ev.get("ok"),
                        "" if ev.get("ok") is not False else " FAILED: " + "; ".join((ev.get("failed") or [])[:6])))
    if "s4b" in os.path.basename(d.rstrip("/")):
        took = []
        for sh in sorted({k[0] for k in legs}):
            t = ((legs.get((sh, "pgolto-tests")) or {}).get("per_req") or {}).get("instructions_u")
            o = ((legs.get((sh, "official")) or {}).get("per_req") or {}).get("instructions_u")
            tr = ((legs.get((sh, "pgolto-trainer")) or {}).get("per_req") or {}).get("instructions_u")
            if not t or not o:
                rows.append("%s: user instructions missing (tests %s, official %s)" % (sh, t, o))
                continue
            took.append(t <= 0.95 * o)
            rows.append("%s: user instructions per request, pgolto-tests / official = %.4f (%+.2f%%; the gate wants -5%% or "
                        "lower)%s" % (sh, t / o, 100.0 * (t / o - 1.0),
                                      "; pgolto-trainer / official = %.4f" % (tr / o) if tr else ""))
        if not any(took):
            bad.append("pgolto-tests runs under 5% fewer user instructions per request than official on every shape: "
                       "the profile did not take; the arm is dropped")
    return rows, bad


def main(argv):
    rows, bad = check(argv[0].rstrip("/"))
    print("\n".join(rows))
    for b in bad:
        print("STATE RULE FAILED: " + b)
    print("s4_check %s: %s" % (os.path.basename(argv[0].rstrip("/")), "OK" if not bad else "FAILED (%d)" % len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
