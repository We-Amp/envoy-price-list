#!/usr/bin/env python3
"""Track B tables from the run directories (legs.jsonl). Read-only.

    python3 -I analyse.py RUN_DIR [RUN_DIR ...]

Per arm: mean per-request cycles (total, workers, rest = total - workers: main thread and other
threads), datagrams per request; paired comparisons per round against the base arm on log ratios,
with the Student t interval, the method's widened interval 1.96*sqrt(SE^2 + 0.34^2), and the wider
of the two printed separately; validity counts.
"""
import json
import math
import os
import sys
from collections import defaultdict

T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}


def latest(run):
    out, n_all, n_valid = {}, 0, 0
    for line in open(os.path.join(run, "legs.jsonl")):
        m = json.loads(line)
        if not m.get("arm"):
            continue
        n_all += 1
        v = (m.get("verdict") or {}).get("valid")
        n_valid += bool(v)
        k = (m.get("shape"), m["arm"], m.get("round"))
        if v:
            out[k] = m  # the latest valid attempt of each cell
    return out, n_all, n_valid


def metrics(m):
    pr = m.get("per_req") or {}
    tot = pr.get("cycles_total")
    wk = m.get("workers_cycles_per_req")
    udp = m.get("udp") or {}
    return {"total": tot, "workers": wk, "rest": (tot - wk) if tot is not None and wk is not None else None,
            "dgram_per_req": udp.get("datagrams_per_request"), "drop_share": udp.get("drop_share"),
            "sent_per_flush": udp.get("sent_per_flush"), "flushes": (m.get("main") or {}).get("bursts"),
            "rate": m.get("sut_rate_2xx"), "busy": m.get("sut_busy")}


def paired(cells, arm, base, key):
    rounds = sorted({r for (_, a, r) in cells if a == arm} & {r for (_, a, r) in cells if a == base})
    d = []
    for r in rounds:
        x = [metrics(m)[key] for (s, a, rr), m in cells.items() if a == arm and rr == r]
        y = [metrics(m)[key] for (s, a, rr), m in cells.items() if a == base and rr == r]
        if x and y and x[0] and y[0]:
            d.append(100.0 * math.log(x[0] / y[0]))
    n = len(d)
    if n < 2:
        return None
    mean = sum(d) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in d) / (n - 1))
    se = sd / math.sqrt(n)
    hw = T975.get(n - 1, 1.96) * se
    # the method's widened interval: 1.96*sqrt(SE^2 + 0.34^2), on its own (not the max with t)
    wide = 1.96 * math.sqrt(se ** 2 + 0.34 ** 2)
    pct = lambda v: 100.0 * (math.exp(v / 100.0) - 1)  # noqa: E731
    big = max(hw, wide)
    return {"n": n, "effect": pct(mean), "lo": pct(mean - hw), "hi": pct(mean + hw),
            "wlo": pct(mean - wide), "whi": pct(mean + wide),
            "xlo": pct(mean - big), "xhi": pct(mean + big), "hw": hw, "whw": wide}


def fmt(c):
    if not c:
        return "n/a"
    return ("%+.2f%%, t [%+.2f, %+.2f], widened (method) [%+.2f, %+.2f], wider of the two [%+.2f, %+.2f] (n %d)"
            % (c["effect"], c["lo"], c["hi"], c["wlo"], c["whi"], c["xlo"], c["xhi"], c["n"]))


def main():
    out = {}
    for run in sys.argv[1:]:
        cells, n_all, n_valid = latest(run)
        name = os.path.basename(run.rstrip("/"))
        exp = json.load(open(os.path.join(run, "experiment.json")))
        base = exp["base_arm"]
        arms = [a["name"] for a in exp["arms"]]
        print("\n## %s (base %s): %d legs recorded, %d valid, %d cells used" % (name, base, n_all, n_valid, len(cells)))
        print("\n| Arm | legs | total k cyc/req | workers k | rest (main+other) k | datagrams/req | drop share | sent/flush | rate | busy |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        res = {"arms": {}, "cmp": {}}
        for a in arms:
            ms = [metrics(m) for (s, ar, r), m in cells.items() if ar == a]
            def mean(k):
                v = [x[k] for x in ms if x[k] is not None]
                return sum(v) / len(v) if v else None
            row = {k: mean(k) for k in ("total", "workers", "rest", "dgram_per_req", "drop_share", "sent_per_flush", "rate", "busy")}
            row["legs"] = len(ms)
            res["arms"][a] = row
            f = lambda v, s=1e3, p=1: ("%.*f" % (p, v / s)) if v is not None else "-"  # noqa: E731
            print("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                a, len(ms), f(row["total"]), f(row["workers"]), f(row["rest"]), f(row["dgram_per_req"], 1, 3),
                f(row["drop_share"], 1, 4), f(row["sent_per_flush"], 1, 0), f(row["rate"], 1, 0), f(row["busy"], 1, 3)))
        print()
        pairs = [(a, base) for a in arms if a != base]
        if "ctl-nosink" in arms:
            pairs += [(a, "ctl-nosink") for a in arms if a != "ctl-nosink"]
        for a, b in pairs:
            for k in ("total", "workers", "rest"):
                c = paired(cells, a, b, k)
                res["cmp"]["%s vs %s %s" % (a, b, k)] = c
                print("- %s vs %s, %s: %s" % (a, b, k, fmt(c)))
        out[name] = res
    json.dump(out, open(os.environ.get("B_TABLES_JSON", "/dev/null"), "w"), indent=1)


if __name__ == "__main__":
    main()
