#!/usr/bin/env python3
"""What the dose queue requires before it starts, beside a smoke whose every leg is valid
(smoke_valid.py) and the evidence check. Exit 0 when all hold; else each problem and exit 1.

    python3 examples/stats-mt/dose_gate.py DOSE_CFG SMOKE_DIR PILOT_RECORD [DECISION]

- the pilot record (dose_pilot.py --json) exists and is for this attempt's rates key, and either
  it is clean and its recommended K and connections per worker equal the configured ones, or a
  decision record stands in for the recommendation: a JSON the operator writes,
    {"decision": what decided (a dated note), "pilot_record": the pilot record's file name,
     "rates_key": ..., "counters": K, "connections": c,
     "cell_counters": {cell: its dose}, "low": {"cell": ..., "counters": ...}}
  It is accepted only when it names this pilot record, its choices equal the configured ones
  (K, connections, every cell's dose, the second dose), and the pilot record itself shows its
  checks 1 (validate, counts, increments), 2 (instructions) and 6 (no overflow) as passed: the
  file is never trusted for what the pilot found;
- the smoke ran what the run will: the same dose block (K, connections, cells, contrasts), the
  same shapes (name, rate, client threads and connections) and, arm by arm, the same name,
  settings and cells.
"""

import json
import os
import sys


def arm_key(a):
    return {"name": a.get("name"), "settings": a.get("settings") or {}, "shapes": a.get("shapes")}


def shape_key(s):
    return {k: s.get(k) for k in ("name", "rps", "workers", "worker_cpus", "client_concurrency",
                                  "client_connections_per_worker")}


DECISION_CHECKS = (("q1", "1 (validate, counts, increments)"), ("q2", "2 (instructions)"), ("q6", "6 (no overflow)"))


def configured(d):
    """The choices a dose config carries, in the decision record's form."""
    return {"rates_key": d.get("rates_key"), "counters": d.get("counters"), "connections": d.get("connections"),
            "cell_counters": {c["cell"]: c.get("counters") for c in d.get("cells") or []},
            "low": None if not d.get("low") else {"cell": d["low"].get("cell"), "counters": d["low"].get("counters")}}


def decision_problems(d, record, decision, record_name):
    """Why a decision record does not stand in for the pilot's recommendation."""
    out = []
    if not isinstance(decision, dict) or not decision.get("decision"):
        return ["the decision record does not say what decided (decision)"]
    if decision.get("pilot_record") != record_name:
        out.append("the decision record names pilot record %s, the pilot record is %s" % (
            decision.get("pilot_record"), record_name))
    want = configured(d)
    for k, v in want.items():
        if decision.get(k) != v:
            out.append("the decision record has %s %s, the config %s" % (k, json.dumps(decision.get(k), sort_keys=True),
                                                                        json.dumps(v, sort_keys=True)))
    # what the pilot found is read from the pilot record, never from the decision
    for key, label in DECISION_CHECKS:
        if (record.get(key) or {}).get("ok") is not True:
            out.append("the pilot record's check %s did not pass: a decision record cannot stand in for it" % label)
    return out


def problems(cfg, smoke_exp, record, decision=None, record_name=None):
    out = []
    d = cfg.get("dose") or {}
    if record is None:
        out.append("no pilot record")
    else:
        if record.get("rates_key") != d.get("rates_key"):
            out.append("the pilot record is for rates key %s, the config for %s" % (
                record.get("rates_key"), d.get("rates_key")))
        if decision is not None:
            out += decision_problems(d, record, decision, record_name)
        else:
            if not record.get("ok"):
                out.append("the pilot record is not clean (and there is no decision record): %s" % (
                    "; ".join(record.get("problems") or []) or "see the pilot"))
            rec = record.get("recommend") or {}
            want = {"counters": d.get("counters"), "connections": d.get("connections")}
            if {k: rec.get(k) for k in want} != want:
                out.append("the pilot recommends K %s and %s connections per worker, the config has K %s and %s" % (
                    rec.get("counters"), rec.get("connections"), want["counters"], want["connections"]))
    if smoke_exp is None:
        out.append("no smoke results")
        return out
    if smoke_exp.get("dose") != d:
        out.append("the smoke ran with another dose block (K, connections, cells or contrasts) than the config")
    if [shape_key(s) for s in smoke_exp.get("shapes", [])] != [shape_key(s) for s in cfg.get("shapes", [])]:
        out.append("the smoke ran other shapes (rung, rate or client connections) than the config")
    sa, ca = [arm_key(a) for a in smoke_exp.get("arms", [])], [arm_key(a) for a in cfg.get("arms", [])]
    if [a["name"] for a in sa] != [a["name"] for a in ca]:
        out.append("the smoke ran arms %s, the config has %s" % ([a["name"] for a in sa], [a["name"] for a in ca]))
    else:
        for x, y in zip(sa, ca):
            if x != y:
                out.append("arm %s: the smoke's settings or cells differ from the config's" % x["name"])
    return out


def _load(p):
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def main():
    cfg = _load(sys.argv[1])
    res = _load(os.path.join(sys.argv[2], "results.json"))
    decision = None
    if len(sys.argv) > 4 and os.path.exists(sys.argv[4]):
        decision = _load(sys.argv[4])
        print("decision record %s" % sys.argv[4])
    probs = problems(cfg, (res or {}).get("experiment"), _load(sys.argv[3]), decision, os.path.basename(sys.argv[3]))
    for p in probs:
        print(p)
    print("dose gate %s" % ("passed" if not probs else "NOT passed (%d problems)" % len(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
