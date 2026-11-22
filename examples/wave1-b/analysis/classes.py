#!/usr/bin/env python3
"""Per arm: datagrams by last-line class from the discard sink's own counts (udpsink/<leg>.json), split
into sample datagrams (ms/h) and flush datagrams (c/g), scaled to per request with the leg's kernel
datagrams per request. Read-only.   python3 -I classes.py RUN_DIR"""
import json, os, sys, statistics as st
run = sys.argv[1]
legs = [json.loads(l) for l in open(os.path.join(run, "legs.jsonl"))]
by = {}
for m in legs:
    if not m.get("arm") or not (m.get("verdict") or {}).get("valid"):
        continue
    p = os.path.join(run, "udpsink", m["leg_id"] + ".json")
    if not os.path.exists(p):
        continue
    u = json.load(open(p))
    c = u.get("classes") or {}
    tot = sum(c.get(k, 0) for k in ("c", "g", "ms", "h", "other"))
    if not tot:
        continue
    dpr = (m.get("udp") or {}).get("datagrams_per_request")
    samp = (c.get("ms", 0) + c.get("h", 0)) / tot
    lines = u.get("datagrams", 0) + u.get("newlines", 0)
    by.setdefault(m["arm"], []).append((dpr, dpr * samp, dpr * (1 - samp), lines / max(u.get("datagrams", 1), 1)))
print("| Arm | legs | datagrams/req | sample (worker) datagrams/req | flush (main) datagrams/req | lines per datagram (receiver, whole leg) |")
print("|---|---|---|---|---|---|")
for a, v in by.items():
    f = lambda i: st.mean(x[i] for x in v)
    print("| %s | %d | %.3f | %.3f | %.3f | %.2f |" % (a, len(v), f(0), f(1), f(2), f(3)))
