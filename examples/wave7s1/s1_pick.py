#!/usr/bin/env python3
"""Decisions the S1 chain takes from a smoke, fixed before the run (plan rules R3 and R7).

    s1_pick.py s1a SMOKE_DIR   prints the s1a config to run: s1a-hop, or the variant in which a Unix-socket
                               arm whose smoke leg is invalid or fails its evidence is replaced by a copy
                               of one-ppd (s1a-hop-no-pair-uds, s1a-hop-no-one-uds, s1a-hop-no-uds)
    s1_pick.py s1b SMOKE_DIR   prints ok (every smoke leg valid), halve (invalid legs, and every reason is a
                               load gate: client headroom, client pending, uneven workers), or fail
"""
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


def good(m):
    return bool(m) and (m.get("verdict") or {}).get("valid") and (m.get("evidence") or {"ok": True}).get("ok")


LOAD = ("client headroom", "client pending total", "Envoy load uneven")


def main(argv):
    kind, d = argv
    legs = latest(d)
    if kind == "s1a":
        pu = good(legs.get(("s", "pair-uds")))
        ou = good(legs.get(("s", "one-uds")))
        print("s1a-hop" + ("" if pu and ou else "-no-uds" if not pu and not ou else "-no-pair-uds" if not pu else "-no-one-uds"))
        return 0
    bad = [m for m in legs.values() if not (m.get("verdict") or {}).get("valid")]
    if legs and not bad:
        print("ok")
    elif bad and all(r.startswith(LOAD) for m in bad for r in (m.get("verdict") or {}).get("reasons") or ["?"]):
        print("halve")
    else:
        print("fail")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
