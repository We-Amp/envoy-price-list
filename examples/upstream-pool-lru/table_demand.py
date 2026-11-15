#!/usr/bin/env python3
"""Tables for the demand-grown pool follow-up.

    python3 examples/upstream-pool-lru/table_demand.py RUN_DIR [RUN_DIR_KA]

Current legs only (the highest attempt per round, shape and arm); a pair needs both
legs valid. Primary rows: lru against mru on cycles_total_all at each rate, Holm across
those rows. Everything else is exploratory (paired intervals, no multiplicity control).
"""

import json
import math
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import stats  # noqa: E402


def load(run_dir):
    cur = {}
    with open(os.path.join(run_dir, "legs.jsonl")) as f:
        for line in f:
            m = json.loads(line)
            k = (m["shape"], m["round"], m["arm"])
            if k not in cur or m.get("attempt", 0) >= cur[k].get("attempt", 0):
                cur[k] = m
    return cur


def pairs(cur, shape, base, arm, fn):
    b, a = [], []
    for (s, r, x), m in sorted(cur.items()):
        if s != shape or x != arm:
            continue
        mb = cur.get((s, r, base))
        if not (mb and m["verdict"]["valid"] and mb["verdict"]["valid"]):
            continue
        vb, va = fn(mb), fn(m)
        if vb is None or va is None:
            continue
        b.append(vb)
        a.append(va)
    return b, a


def fmt_ci(r):
    return "%+.1f%% [%+.1f, %+.1f]" % (r["effect_pct"], r["lo_pct"], r["hi_pct"])


def rng(xs, nd=2):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "–"
    return ("%%.%df (%%.%df–%%.%df)" % (nd, nd, nd)) % (st.median(xs), min(xs), max(xs))


def hop_b_workers(m):
    be = m.get("hop2_stats_end") or {}
    return sorted((v for k, v in be.items() if ".worker_" in k and k.endswith("downstream_cx_active")
                   and k.startswith("listener.127.0.0.1")), reverse=True)


def per_req(m, key):
    pr = m.get("per_req") or {}
    return pr.get(key)


def lat(m, p):
    return (m.get("latency_us") or {}).get(p)


def run(run_dir, base="mru", primary_arms=("lru",)):
    cur = load(run_dir)
    shapes = sorted({k[0] for k in cur}, key=lambda s: min(m["target_rps"] for kk, m in cur.items() if kk[0] == s))
    arms = []
    for k in sorted(cur):
        if k[2] not in arms:
            arms.append(k[2])
    out = []
    rate = {s: next(m["target_rps"] for kk, m in cur.items() if kk[0] == s) for s in shapes}
    legs = {}
    for s in shapes:
        for a in arms:
            ls = [m for (ss, r, x), m in cur.items() if ss == s and x == a]
            legs[(s, a)] = ls
    out.append("Legs (current / valid): " + ", ".join(
        "%d %s %d/%d" % (rate[s], a, len(legs[(s, a)]), sum(m["verdict"]["valid"] for m in legs[(s, a)]))
        for s in shapes for a in arms))
    inval = [(m["leg_id"], m["verdict"]["reasons"]) for ls in legs.values() for m in ls if not m["verdict"]["valid"]]
    if inval:
        out.append("")
        out.append("Invalid current legs: " + "; ".join("%s: %s" % (i, " / ".join(r)) for i, r in inval))
    # primary
    rows = []
    for a in arms:
        if a == base:
            continue
        for s in shapes:
            b, x = pairs(cur, s, base, a, lambda m: per_req(m, "cycles_total_all"))
            if len(b) < 3:
                continue
            r = stats.paired_log_ratio(b, x)
            rows.append((a, s, r, len(b), st.median(b), st.median(x)))
    prim = [i for i, row in enumerate(rows) if row[0] in primary_arms]
    hp = stats.holm([rows[i][2]["t_p"] for i in prim]) if prim else []
    hmap = {i: hp[j] for j, i in enumerate(prim)}
    out.append("")
    out.append("| Comparison | Rate | cycles/req, both hops (medians, k) | effect [95% CI] | raw p | Holm p | pairs |")
    out.append("|---|---|---|---|---|---|---|")
    for i, (a, s, r, n, mb, mx) in enumerate(rows):
        out.append("| %s vs %s%s | %d | %.1f → %.1f | %s | %.2g | %s | %d |" % (
            a, base, " (primary)" if i in hmap else " (exploratory)", rate[s], mb / 1e3, mx / 1e3, fmt_ci(r),
            r["t_p"], ("%.2g" % hmap[i]) if i in hmap else "–", n))
    # pool and hop B spread
    out.append("")
    out.append("| Rate | Arm | hop A pool (gauge) | hop B pool to origin | hop B conns per worker (median leg) | "
               "hop B shares sorted (median per rank) | busiest share median (min–max) | busiest worker, of a core | "
               "hop B busy | legs with busiest share > 0.30 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for s in shapes:
        for a in arms:
            ls = [m for m in legs[(s, a)] if m["verdict"]["valid"]]
            if not ls:
                continue
            pa = [(m.get("sut_stats_end") or {}).get("cluster.origin.upstream_cx_active") for m in ls]
            pb = [(m.get("hop2_stats_end") or {}).get("cluster.origin.upstream_cx_active") for m in ls]
            wk = [hop_b_workers(m) for m in ls]
            wk_s = sorted(wk, key=lambda w: (max(w) - min(w)) if w else 0)
            shares = [sorted((m.get("hop2_workers") or {}).get("worker_share") or [], reverse=True) for m in ls]
            rank_med = [st.median(sh[i] for sh in shares if len(sh) > i) for i in range(4)]
            mx = [sh[0] for sh in shares if sh]
            mb = [(m.get("hop2_workers") or {}).get("worker_max_busy") for m in ls]
            hb = [m.get("hop2_busy") for m in ls]
            out.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %d of %d |" % (
                rate[s], a, "%d–%d" % (min(pa), max(pa)), "%d–%d" % (min(pb), max(pb)),
                "/".join(str(x) for x in wk_s[len(wk_s) // 2]) + " (widest %s)" % "/".join(str(x) for x in wk_s[-1]),
                "/".join("%.2f" % x for x in rank_med), rng(mx), rng(mb), rng(hb), sum(1 for x in mx if x > 0.30),
                len(mx)))
    # exploratory: per hop, latency
    out.append("")
    out.append("| Comparison | Rate | hop A cycles/req | hop B cycles/req | p50 µs (medians) | p50 effect | "
               "p99 µs (medians) | p99 effect |")
    out.append("|---|---|---|---|---|---|---|---|")
    for a in arms:
        if a == base:
            continue
        for s in shapes:
            cells = []
            for key in ("cycles_total", "cycles_total_hop2"):
                b, x = pairs(cur, s, base, a, lambda m, key=key: per_req(m, key))
                cells.append("%.1fk → %.1fk, %s" % (st.median(b) / 1e3, st.median(x) / 1e3,
                                                     fmt_ci(stats.paired_log_ratio(b, x))) if len(b) >= 3 else "–")
            for p in ("p50", "p99"):
                b, x = pairs(cur, s, base, a, lambda m, p=p: lat(m, p))
                if len(b) >= 3:
                    cells.append("%.0f → %.0f" % (st.median(b), st.median(x)))
                    cells.append(fmt_ci(stats.paired_log_ratio(b, x)))
                else:
                    cells += ["–", "–"]
            out.append("| %s vs %s | %d | %s |" % (a, base, rate[s], " | ".join(cells)))
    # keep-alive / connection churn counters (deltas in the window)
    out.append("")
    out.append("| Rate | Arm | hop A upstream cx opened in window (median, max) | hop A remote closes | "
               "hop A retries | hop A 5xx/resets | hop B max-requests closes | p99 > 2 ms legs |")
    out.append("|---|---|---|---|---|---|---|---|")
    for s in shapes:
        for a in arms:
            ls = legs[(s, a)]
            if not ls:
                continue
            def d(m, *keys, src="sut_stats_delta"):
                dd = m.get(src) or {}
                return sum(v for k, v in dd.items() if any(k.endswith(x) for x in keys))
            op = [m.get("upstream_cx_opened") or 0 for m in ls]
            out.append("| %d | %s | %s, %s | %d | %d | %d | %d | %d of %d |" % (
                rate[s], a, st.median(op), max(op),
                sum(d(m, "upstream_cx_destroy_remote") for m in ls),
                sum(d(m, "upstream_rq_retry") for m in ls),
                sum(d(m, "upstream_rq_5xx", "upstream_rq_reset", "upstream_cx_destroy_remote_with_active_rq",
                      "upstream_cx_destroy_local_with_active_rq") for m in ls),
                sum(d(m, "downstream_cx_max_requests_reached", src="hop2_stats_delta") for m in ls),
                sum(1 for m in ls if (lat(m, "p99") or 0) > 2000), len(ls)))
    return "\n".join(out)


if __name__ == "__main__":
    for rd in sys.argv[1:]:
        print("## " + os.path.basename(rd.rstrip("/")))
        print()
        print(run(rd))
        print()
