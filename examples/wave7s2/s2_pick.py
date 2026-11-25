#!/usr/bin/env python3
"""Decisions the S2 chain takes from a smoke, fixed before the run (plan rule R3 and plan section 3.2, "the Go origin
is not the limit").

    s2_pick.py s2a SMOKE_DIR   prints the s2a config to run: s2a-chunked when every smoke leg is valid with
                               its evidence; s2a-chunked-h64 / -h1m / -hh when the legs of b64k, b1m or both
                               fail and every failure is a load reason; fail otherwise
    s2_pick.py s2b SMOKE_DIR   prints s2b-stream, s2b-stream-half (the two shapes share one event rate, so
                               they are halved together) or fail
    s2_pick.py headroom SMOKE_DIR   prints one line per leg: the origin-headroom evidence of the smoke

Load reasons (one halving of that shape's rate, then report): the client headroom, pending and overflow
gates, uneven worker load, the side-service CPU gate (the stream origin over 50% of its 16 CPUs), the rate
gate, and the evidence items read from the stream origin's own counters (responses per request, events or
chunks per response, late events)."""
import json
import os
import sys

LOAD = ("client headroom", "client pending", "client overflow", "Envoy load uneven", "side service stream_origin used",
        "side service origin used", "achieved rate", "rate ")
EV_LOAD = ("origin:",)


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


def problems(m):
    """(not load-related, load-related) reasons a smoke leg is not usable."""
    hard, load = [], []
    v = m.get("verdict") or {}
    if not v.get("valid"):
        for r in v.get("reasons") or ["?"]:
            (load if r.startswith(LOAD) else hard).append(r)
    ev = m.get("evidence") or {}
    if ev.get("ok") is False:
        for r in ev.get("failed") or ["?"]:
            (load if r.startswith(EV_LOAD) else hard).append("evidence: " + r)
    return hard, load


def decide(legs, shapes):
    """{shape: ok | halve | fail}."""
    out = {}
    for sh in shapes:
        mine = [m for (s, _), m in legs.items() if s == sh]
        hard = [r for m in mine for r in problems(m)[0]]
        load = [r for m in mine for r in problems(m)[1]]
        out[sh] = "fail" if hard or not mine else "halve" if load else "ok"
    return out


def headroom(legs):
    rows = []
    for (sh, arm), m in sorted(legs.items()):
        so = (m.get("side_services") or {}).get("stream_origin") or {}
        d = (m.get("stream_origin") or {}).get("d") or {}
        resp = d.get("responses") or 0
        rows.append("%s/%s: origin CPU %s of its set (limit 0.50), responses per request %s, writes per response %s, "
                    "chunks per response %s, events per response %s, body bytes per response %s, late events %s of %s "
                    "(max late %s us); valid %s, evidence %s" % (
                        sh, arm, so.get("busy_of_set"),
                        "%.4f" % (resp / m["responses_raw"]) if m.get("responses_raw") else "-",
                        "%.3f" % (d.get("write_calls", 0) / resp) if resp else "-",
                        "%.3f" % (d.get("chunks", 0) / resp) if resp else "-",
                        "%.3f" % (d.get("events", 0) / resp) if resp else "-",
                        "%.1f" % (d.get("body_bytes", 0) / resp) if resp else "-",
                        d.get("late_events"), d.get("events"), (m.get("stream_origin") or {}).get("max_late_us"),
                        (m.get("verdict") or {}).get("valid"), (m.get("evidence") or {}).get("ok")))
    return rows


def main(argv):
    kind, d = argv
    legs = latest(d)
    if kind == "headroom":
        print("\n".join(headroom(legs)))
        return 0
    if kind == "s2a":
        r = decide(legs, ["b64k", "b1m"])
        if "fail" in r.values():
            print("fail")
        else:
            sfx = {(False, False): "", (True, False): "-h64", (False, True): "-h1m", (True, True): "-hh"}[
                (r["b64k"] == "halve", r["b1m"] == "halve")]
            print("s2a-chunked" + sfx)
        return 0
    r = decide(legs, ["ev20", "ev200"])
    print("fail" if "fail" in r.values() else "s2b-stream-half" if "halve" in r.values() else "s2b-stream")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
