#!/usr/bin/env python3
"""Tables for the upstream-pool LRU experiment.

    python3 examples/upstream-pool-lru/table.py RUNS_DIR [--json OUT.json]

RUNS_DIR holds two-hop/, one-hop/ (epl run) and probe-two-hop/, probe-one-hop/
(epl probe). Holm runs once across the primary rows of both runs: total cycles per
request of both hops (two-hop) and of the single hop (one-hop), one row per rate.
"""

import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from epl import experiment, stats  # noqa: E402


def load(d):
    p = os.path.join(d, "results.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def iv(c):
    p = (c or {}).get("paired") or {}
    if p.get("effect_pct") is None:
        return "-"
    return "%+.1f%% [%+.1f, %+.1f]" % (p["effect_pct"], p["lo_pct"], p["hi_pct"])


def med(vals, f="%.0f"):
    vals = [v for v in vals if v is not None]
    return (f % statistics.median(vals)) if vals else "-"


def rng(vals, f="%.2f"):
    vals = [v for v in vals if v is not None]
    return ("%s to %s" % (f % min(vals), f % max(vals))) if vals else "-"


def legs(res, shape, arm):
    by = experiment.current_legs(res["legs"])
    return [m for (s, a, r), m in sorted(by.items()) if s == shape and a == arm]


def g(m, *path):
    for k in path:
        if not isinstance(m, dict) or k not in m:
            return None
        m = m[k]
    return m


def comp(res, shape, arm):
    for c in res["analysis"]["shapes"][shape]["comparisons"]:
        if c["arm"] == arm:
            return c
    return {}


def paired_legs(res, shape, get):
    """Paired LRU/MRU comparison of any per-leg value, by round."""
    by = experiment.current_legs(res["legs"])
    rounds = sorted(r for (s, a, r) in by if s == shape and a == "lru" and (s, "mru", r) in by)
    bv, av = [], []
    for r in rounds:
        x, y = get(by[(shape, "mru", r)]), get(by[(shape, "lru", r)])
        if x is not None and y is not None:
            bv.append(x)
            av.append(y)
    if len(bv) < 6:
        return None
    return {"paired": stats.compare_paired(bv, av)["paired"], "mru": statistics.median(bv),
            "lru": statistics.median(av)}


def split_table(res, title, hops, out):
    print("\n## %s: user and kernel cycles per request (medians MRU -> LRU, paired 95%% intervals)\n" % title)
    print("| Rate | Part | MRU -> LRU | effect | delta cycles/req |")
    print("|---|---|---|---|---|")
    for sh in res["experiment"]["shapes"]:
        for label, get in hops:
            c = paired_legs(res, sh["name"], get)
            if not c:
                continue
            out.setdefault(sh["name"], {})[label] = c
            if "context" in label:
                print("| %d | %s | %.2f -> %.2f | %s | %+.2f |" % (sh["rps"], label, c["mru"], c["lru"], iv(c),
                                                                 c["lru"] - c["mru"]))
            else:
                print("| %d | %s | %.1fk -> %.1fk | %s | %+.1fk |" % (sh["rps"], label, c["mru"] / 1e3, c["lru"] / 1e3,
                                                                    iv(c), (c["lru"] - c["mru"]) / 1e3))


def residency_table(res, title, out):
    print("\n## %s: idle-state residency on the Envoy CPUs during the window (sum over CPUs, medians)\n" % title)
    rows = []
    for sh in res["experiment"]["shapes"]:
        for arm in ("mru", "lru"):
            L = [m for m in legs(res, sh["name"], arm) if m.get("cpuidle_residency")]
            if not L:
                continue
            names = sorted({n for m in L for n in m["cpuidle_residency"]["sum"]})
            cells = []
            for n in names:
                rs = [m["cpuidle_residency"]["sum"].get(n, {}).get("residency") for m in L]
                es = [m["cpuidle_residency"]["sum"].get(n, {}).get("entries_per_s") for m in L]
                cells.append("%s %s CPU, %s/s" % (n, med(rs, "%.2f"), med(es, "%.0f")))
                out.setdefault(sh["name"], {}).setdefault(arm, {})[n] = {"residency": statistics.median(
                    [x for x in rs if x is not None]), "entries_per_s": statistics.median([x for x in es if x is not None])}
            rows.append("| %d | %s | %d | %s |" % (sh["rps"], arm, len(L), "; ".join(cells)))
    if rows:
        print("| Rate | Arm | legs | per state: residency (CPUs) and entries per second |")
        print("|---|---|---|---|")
        print("\n".join(rows))
    else:
        print("(not recorded in this run)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("--json")
    a = ap.parse_args()
    two = load(os.path.join(a.runs, "two-hop"))
    one = load(os.path.join(a.runs, "one-hop"))
    out = {"primary": [], "two_hop": {}, "one_hop": {}, "probe": {}, "split": {}, "residency": {}}
    prim = []
    for name, res, key in (("two-hop", two, "cycles_total_all"), ("one-hop", one, "cycles_total")):
        if not res:
            continue
        for sh in res["experiment"]["shapes"]:
            c = comp(res, sh["name"], "lru").get(key)
            if c and (c.get("paired") or {}).get("t_p") is not None:
                prim.append({"run": name, "shape": sh["name"], "rps": sh["rps"], "metric": key, "c": c})
    for r, h in zip(prim, stats.holm([r["c"]["paired"]["t_p"] for r in prim])):
        r["holm_p"] = h
    print("## Primary rows (LRU against MRU, Holm across all %d)\n" % len(prim))
    print("| Run | Rate | Metric | Effect [95% CI] | raw p | Holm p | pairs |")
    print("|---|---|---|---|---|---|---|")
    for r in prim:
        p = r["c"]["paired"]
        print("| %s | %d | %s | %s | %.2g | %.2g | %d |" % (r["run"], r["rps"], r["metric"], iv(r["c"]),
                                                           p["t_p"], r["holm_p"], p["n"]))
        out["primary"].append({k: r[k] for k in ("run", "shape", "rps", "metric", "holm_p")} |
                              {"paired": {k: v for k, v in p.items() if k != "log_pcts"}})

    if two:
        print("\n## Two hops: load spread on hop B (medians over valid legs; ranges)\n")
        print("| Rate | Arm | valid legs | hop B worker shares, sorted (median per rank) | busiest share (range) "
              "| busiest worker busy, of a core (range) | hop B busy (mean of 4) | A->B conns carrying traffic "
              "| A->B conns open | hop A worker share max |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for sh in two["experiment"]["shapes"]:
            for arm in ("mru", "lru"):
                L = legs(two, sh["name"], arm)
                ranks = [sorted(g(m, "hop2_workers", "worker_share") or [], reverse=True) for m in L]
                ranks = [x for x in ranks if len(x) == 4]
                rk = " / ".join("%.2f" % statistics.median(r[i] for r in ranks) for i in range(4)) if ranks else "-"
                row = {"valid": len(L), "shares_by_rank": rk,
                       "max_share": [g(m, "hop2_workers", "worker_max_share") for m in L],
                       "max_busy": [g(m, "hop2_workers", "worker_max_busy") for m in L],
                       "hop2_busy": [m.get("hop2_busy") for m in L],
                       "conns_used": [g(m, "conn_hop2_downstream", "conns_over_1pct_of_mean") for m in L],
                       "conns_open": [g(m, "conn_hop2_downstream", "conns") for m in L],
                       "hopA_max_share": [m.get("envoy_worker_max_share") for m in L]}
                out["two_hop"].setdefault(sh["name"], {})[arm] = row
                print("| %d | %s | %d | %s | %s (%s) | %s (%s) | %s | %s (%s) | %s | %s |" % (
                    sh["rps"], arm, len(L), rk, med(row["max_share"], "%.2f"), rng(row["max_share"]),
                    med(row["max_busy"], "%.2f"), rng(row["max_busy"]), med(row["hop2_busy"], "%.2f"),
                    med(row["conns_used"]), rng(row["conns_used"], "%d"), med(row["conns_open"]),
                    med(row["hopA_max_share"], "%.2f")))
        print("\n## Two hops: CPU and latency (medians; LRU against MRU, paired 95% intervals)\n")
        print("| Rate | hop A cycles/req MRU -> LRU | effect | hop B cycles/req MRU -> LRU | effect "
              "| both hops MRU -> LRU | effect | p50 us MRU -> LRU | effect | p99 us MRU -> LRU | effect |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for sh in two["experiment"]["shapes"]:
            s = sh["name"]
            A = two["analysis"]["shapes"][s]["arms"]
            c = comp(two, s, "lru")
            cells = []
            for key, f in (("cycles_total", "%.1fk"), ("cycles_total_hop2", "%.1fk"), ("cycles_total_all", "%.1fk"),
                           ("p50_us", "%.0f"), ("p99_us", "%.0f")):
                mm, ml = g(A, "mru", key, "median"), g(A, "lru", key, "median")
                dv = 1e3 if f.endswith("k") else 1.0
                cells.append("%s -> %s" % (f % (mm / dv), f % (ml / dv)) if mm and ml else "-")
                cells.append(iv(c.get(key)))
                out["two_hop"][s].setdefault("cpu_lat", {})[key] = {"mru": mm, "lru": ml,
                                                                   "paired": (c.get(key) or {}).get("paired")}
            print("| %d | %s |" % (sh["rps"], " | ".join(cells)))
    if one:
        print("\n## One hop (control): CPU, latency, upstream connections\n")
        print("| Rate | cycles/req MRU -> LRU | effect | instructions:u effect | p50 us MRU -> LRU | effect "
              "| p99 us MRU -> LRU | effect | upstream conns carrying traffic MRU / LRU | worker share max MRU / LRU |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for sh in one["experiment"]["shapes"]:
            s = sh["name"]
            A = one["analysis"]["shapes"][s]["arms"]
            c = comp(one, s, "lru")
            cells = []
            for key, f in (("cycles_total", "%.1fk"), ("instructions_u", None), ("p50_us", "%.0f"), ("p99_us", "%.0f")):
                if f:
                    mm, ml = g(A, "mru", key, "median"), g(A, "lru", key, "median")
                    dv = 1e3 if f.endswith("k") else 1.0
                    cells.append("%s -> %s" % (f % (mm / dv), f % (ml / dv)) if mm and ml else "-")
                cells.append(iv(c.get(key)))
            cu = [med([g(m, "conn_upstream", "conns_over_1pct_of_mean") for m in legs(one, s, arm)]) for arm in ("mru", "lru")]
            ws = [med([m.get("envoy_worker_max_share") for m in legs(one, s, arm)], "%.2f") for arm in ("mru", "lru")]
            out["one_hop"][s] = {"rps": sh["rps"], "conns_used": cu, "worker_max_share": ws,
                                 "paired": {k: (c.get(k) or {}).get("paired") for k in
                                            ("cycles_total", "instructions_u", "p50_us", "p99_us")}}
            print("| %d | %s | %s | %s |" % (sh["rps"], " | ".join(cells), " / ".join(cu), " / ".join(ws)))
    if two:
        split_table(two, "Two hops", [
            ("hop A user", lambda m: g(m, "per_req", "cycles_u")), ("hop A kernel", lambda m: g(m, "per_req", "cycles_k")),
            ("hop B user", lambda m: g(m, "hop2_per_req", "cycles_u")),
            ("hop B kernel", lambda m: g(m, "hop2_per_req", "cycles_k")),
            ("hop B context switches/req", lambda m: g(m, "hop2_per_req", "context_switches")),
            ("hop A context switches/req", lambda m: g(m, "per_req", "context_switches"))],
            out["split"].setdefault("two-hop", {}))
        residency_table(two, "Two hops", out["residency"].setdefault("two-hop", {}))
    if one:
        split_table(one, "One hop", [
            ("user", lambda m: g(m, "per_req", "cycles_u")), ("kernel", lambda m: g(m, "per_req", "cycles_k")),
            ("context switches/req", lambda m: g(m, "per_req", "context_switches"))],
            out["split"].setdefault("one-hop", {}))
        residency_table(one, "One hop", out["residency"].setdefault("one-hop", {}))
    for name in ("probe-two-hop", "probe-one-hop"):
        p = os.path.join(a.runs, name, "probe.json")
        if not os.path.exists(p):
            continue
        with open(p) as f:
            rows = json.load(f)
        print("\n## Saturation probe, %s (end-to-end p99 limit 2 ms; every rep valid and under)\n" % name)
        print("| Arm | Rate | p99 us per rep | p50 us per rep | valid | hop A busy | hop B busy | hop B busiest share |")
        print("|---|---|---|---|---|---|---|---|")
        res = {}
        for arm in sorted({r["arm"] for r in rows}):
            best, failed = None, False
            for rps in sorted({r["rps"] for r in rows if r["arm"] == arm}):
                R = [r for r in rows if r["arm"] == arm and r["rps"] == rps]
                ok = all(r["valid"] and r["p99_us"] is not None and r["p99_us"] < 2000 for r in R)
                if ok and not failed:
                    best = rps
                failed = failed or not ok
                print("| %s | %d | %s | %s | %s | %s | %s | %s |" % (
                    arm, rps, " / ".join("%.0f" % r["p99_us"] if r["p99_us"] else "-" for r in R),
                    " / ".join("%.0f" % r["p50_us"] if r["p50_us"] else "-" for r in R),
                    " / ".join("y" if r["valid"] else "n: " + ";".join(r["reasons"])[:60] for r in R),
                    med([r["sut_busy"] for r in R], "%.2f"), med([r["hop2_busy"] for r in R], "%.2f"),
                    med([g(r, "hop2_workers", "worker_max_share") for r in R], "%.2f")))
            res[arm] = best
        print("\nHighest rate with every rep valid and p99 < 2 ms (no failure below it): %s" %
              ", ".join("%s %s" % (k, v) for k, v in res.items()))
        out["probe"][name] = {"highest_under_2ms": res, "rows": rows}
    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
