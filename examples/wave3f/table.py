#!/usr/bin/env python3
"""Track F (wave 3: HTTP/2, gRPC and TLS upstreams, mTLS) tables from a run directory's results.json: every paired comparison of the primary metric (and a few
exploratory ones), with the t interval, the widened interval 1.96*sqrt(SE^2+0.34^2) (log-%) and Holm p.
    python3 examples/wave3f/table.py RUN_DIR [METRIC ...]"""
import json
import math
import sys

d = json.load(open(sys.argv[1] + "/results.json"))
a = d["analysis"]
prim = a["primary_metric"]
mets = sys.argv[2:] or [prim]
print("# %s: primary %s, rounds %s" % (sys.argv[1].rstrip("/").split("/")[-1], prim, a["rounds_done"]))
for sh, s in a["shapes"].items():
    print("\n## shape %s\n" % sh)
    print("| arm | valid | median %s |" % prim)
    print("|---|---|---|")
    for arm, x in s["arms"].items():
        print("| %s | %s/%s | %.1fk |" % (arm, x.get("valid"), x.get("legs"), (x.get(prim) or {}).get("median", float("nan")) / 1e3))
    for m in mets:
        print("\n| comparison (%s) | effect [95%% t] | widened +/- (log-%%) | holm p | won | status | arm med | ref med |" % m)
        print("|---|---|---|---|---|---|---|---|")
        for c in s["comparisons"]:
            r = c.get(m)
            if not r or not r.get("paired"):
                continue
            p = r["paired"]
            se = p["log_sd_pct"] / math.sqrt(p["n"])
            wid = 1.96 * math.sqrt(se ** 2 + 0.34 ** 2)
            hp = r.get("holm_p")
            print("| %s vs %s | %+.2f%% [%+.2f, %+.2f] | %.2f | %s | %s | %s | %.1fk | %.1fk |" % (
                c["arm"], c["ref"], p["effect_pct"], p["lo_pct"], p["hi_pct"], wid,
                "%.3g" % hp if hp is not None else "-", "%d/%d" % (r.get("pairs_won", 0), p["n"]), r.get("status"),
                r["arm_median"] / 1e3, r["base_median"] / 1e3))

# Holm over the confirmatory rows fixed before the run, from the paired t p-values
CONF = {"f1-upstream": [("h2c", "h1"), ("h2c-og", "h2c"), ("tls-h1", "h1"), ("tls-h2", "h2c"), ("tls-h2", "tls-h1")],
        "f2-grpc": [("grpc-stats", "grpc"), ("grpc-og", "grpc")],
        "f3-mtls": [("pair", "one-ppd"), ("pair-mtls", "pair"), ("pair-mtls", "one-ppd")]}
FAM = {"f1-upstream": 5, "f2-grpc": 3, "f3-mtls": 3}  # family sizes as fixed before the run
name = sys.argv[1].rstrip("/").split("/")[-1]
if name in CONF:
    rows = []
    for sh, s in a["shapes"].items():
        for want in CONF[name]:
            for c in s["comparisons"]:
                pair = (c["arm"], c["ref"])
                if pair in (want, want[::-1]) and c.get(prim, {}).get("paired"):
                    p = c[prim]["paired"]
                    sign = 1 if pair == want else -1
                    eff = sign * p["log_mean_pct"]
                    se = p["log_sd_pct"] / math.sqrt(p["n"])
                    rows.append([want, math.expm1(eff / 100) * 100, p["t_p"], 1.96 * math.sqrt(se ** 2 + 0.34 ** 2),
                                 eff, p["log_lo_pct"] if sign == 1 else -p["log_hi_pct"],
                                 p["log_hi_pct"] if sign == 1 else -p["log_lo_pct"]])
    m = FAM[name]
    rows.sort(key=lambda r: r[2])
    run = 0.0
    print("\n## confirmatory rows, Holm over %d (plan)\n" % m)
    print("| row | effect | log-%% [95%% t] | widened +/- | t p | Holm p |")
    print("|---|---|---|---|---|---|")
    for i, r in enumerate(rows):
        run = max(run, min(1.0, (m - i) * r[2]))
        print("| %s vs %s | %+.2f%% | %+.2f [%+.2f, %+.2f] | %.2f | %.3g | %.3g |" % (
            r[0][0], r[0][1], r[1], r[4], r[5], r[6], r[3], r[2], run))
