#!/usr/bin/env python3
"""The answers of the dose run's pilot (make.py dose-pilot.json), printed from its legs so that
nobody computes them by hand. Exit 0 when questions 1, 2, 5 and 6 pass, every leg is valid and
question 4 picks a K; else 1.

    python3 examples/stats-mt/dose_pilot.py PILOT_CFG PILOT_DIR [--json OUT.json]

The latest attempt of each cell and arm is used, valid or not (an invalid leg is listed with
its reasons and fails the pilot).

  1. Config and stat count: every arm's bootstrap passed `--mode validate` on the binary; the
     dose counters before and after the window: K in a shared arm, K per downstream connection
     in an own arm, none created during the window, K increments per request (the legs' own
     evidence items decide).
  2. instructions:u per request, shared against own, per K and cell: equal within 0.5%.
  3. h = HITM:u (shared - own) per request / K, per K and cell (local plus remote HITM loads,
     counted in user mode). Expected 1.0-1.4; reported, not gated. Beside it the store-stat
     operations per request of base (the model row's cross-check).
  4. K: the smallest of the choices with h x K x 100 cycles / base worker cycles per request
     >= 2.5% in the rule's cell (h: the mean over the choices in that cell; the per-K values are
     printed beside it).
  5. The load cell: worker busy share, client headroom, client pending, other tasks on the SUT
     CPUs, per leg; passes when every leg of the cell is valid.
  6. Scope limit: the largest own arm's counters all exist and count (a counter over a scope
     limit would be a null object: the sum per request would fall short), and no
     server.stats_overflow stat in the saved stat dumps.
"""

import argparse
import gzip
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import u_table  # noqa: E402


def latest(res):
    legs = {}
    for m in res.get("legs", []):
        legs[(m.get("shape"), m.get("arm"))] = m
    return legs


def _valid(m):
    return bool(m) and bool((m.get("verdict") or {}).get("valid"))


def _ins(m):
    return ((m or {}).get("per_req") or {}).get("instructions_u")


def _cyc(m):
    return (m or {}).get("workers_cycles_per_req") or ((m or {}).get("per_req") or {}).get("cycles_total")


def overflow_lines(run_dir, arms):
    """{arm: [lines]} of server.stats_overflow stats in the saved stat dumps (None: no dump)."""
    out = {}
    for a in arms:
        p = os.path.join(run_dir, "stats", a + ".txt.gz")
        if not os.path.exists(p):
            out[a] = None
            continue
        with gzip.open(p, "rt") as f:
            out[a] = [ln.strip() for ln in f if ln.startswith("server.stats_overflow")]
    return out


def answers(cfg, res, overflow=None):
    d = cfg["dose"]
    rule = d["pilot_rule"]
    ks = d["counters_choices"]
    legs = latest(res)
    cells = d["cells"]
    # what the client run leaves for the admin reads before the window
    lead = max([cfg["measure"]["lead_in_s"]] + [sh.get("lead_in_s") or 0 for sh in cfg["shapes"]])
    rep = {"problems": [], "slack_s": cfg["client"]["duration_s"] - lead - cfg["measure"]["window_s"]}
    arms = [a["name"] for a in cfg["arms"]]
    # every leg present and valid
    rep["legs"] = []
    for c in cells:
        for a in arms:
            m = legs.get((c["shape"], a))
            v = (m or {}).get("verdict") or {}
            rep["legs"].append({"cell": c["cell"], "arm": a, "present": m is not None, "valid": _valid(m),
                                "reasons": v.get("reasons") or []})
            if m is None:
                rep["problems"].append("missing leg: cell %s %s" % (c["cell"], a))
            elif not _valid(m):
                rep["problems"].append("invalid leg: cell %s %s: %s" % (c["cell"], a, "; ".join(v.get("reasons") or [])))
    # 1. validate and stat count
    bv = (res.get("metadata") or {}).get("bootstrap_validate")
    q1 = {"validate": {a: (bv or {}).get(a, {}).get("ok") for a in arms} if bv else None, "counts": [], "ok": True}
    if not bv or not all(q1["validate"].values()):
        q1["ok"] = False
    for c in cells:
        for a in arms:
            m = legs.get((c["shape"], a)) or {}
            sc, ev = m.get("stat_count") or {}, m.get("evidence") or {}
            row = {"cell": c["cell"], "arm": a, "start_n": sc.get("start_n"), "end_n": sc.get("end_n"),
                   "new_in_window": sc.get("new_in_window"), "sum_per_request": sc.get("sum_per_request"), "pre_window_s": sc.get("pre_window_s"),
                   "read_s": [sc.get("start_read_s"), sc.get("end_read_s")],
                   "evidence_ok": ev.get("ok"), "failed": ev.get("failed") or []}
            q1["counts"].append(row)
            if not ev.get("ok"):
                q1["ok"] = False
    rep["q1"] = q1
    # 2 and 3. instructions and h per K and cell
    q2, q3 = {"rows": [], "ok": True}, {"rows": []}
    tol = 100.0 * rule["instructions_tol"]
    for c in cells:
        for k in ks:
            own, sh = legs.get((c["shape"], "own-%d" % k)), legs.get((c["shape"], "shared-%d" % k))
            io, ish = _ins(own), _ins(sh)
            diff = 100.0 * math.log(ish / io) if io and ish else None
            ok = diff is not None and abs(diff) <= tol
            q2["rows"].append({"cell": c["cell"], "k": k, "own": io, "shared": ish, "diff_pct": diff, "ok": ok})
            q2["ok"] = q2["ok"] and ok
            ho, hs = u_table.hitm_per_req(own or {}), u_table.hitm_per_req(sh or {})
            h = (hs - ho) / k if ho is not None and hs is not None else None
            q3["rows"].append({"cell": c["cell"], "k": k, "own": ho, "shared": hs, "h": h,
                               "expected": None if h is None else rule["h_expected"][0] <= h <= rule["h_expected"][1]})
    rep["q2"], rep["q3"] = q2, q3
    # beside 3: the store-stat operations per request of base (the model row's cross-check)
    rep["stat_ops"] = {}
    for c in cells:
        m = legs.get((c["shape"], "base")) or {}
        so, n = m.get("stat_ops"), m.get("responses")
        rep["stat_ops"][c["cell"]] = (so["counter_incs"] + so["histogram_samples"]) / n if so and n else None
    # 4. K
    shape = next((c["shape"] for c in cells if c["cell"] == rule["cell"]), None)
    base = _cyc(legs.get((shape, "base")))
    hs = [r["h"] for r in q3["rows"] if r["cell"] == rule["cell"] and r["h"] is not None]
    q4 = {"cell": rule["cell"], "base_cycles": base, "h_mean": sum(hs) / len(hs) if len(hs) == len(ks) else None,
          "rows": [], "k": None}
    if q4["h_mean"] is not None and base:
        for k in ks:
            own_h = next(r["h"] for r in q3["rows"] if r["cell"] == rule["cell"] and r["k"] == k)
            share = q4["h_mean"] * k * rule["cycles_per_transfer"] / base
            q4["rows"].append({"k": k, "share": share, "share_own_h": own_h * k * rule["cycles_per_transfer"] / base,
                               "ok": share >= rule["min_share"]})
            if q4["k"] is None and share >= rule["min_share"]:
                q4["k"] = k
    rep["q4"] = q4
    # 5. the load cell
    q5 = {"rows": [], "ok": True}
    load_cells = [c for c in cells if c["role"] == "load"]
    for c in cells:
        for a in arms:
            m = legs.get((c["shape"], a)) or {}
            q5["rows"].append({"cell": c["cell"], "arm": a, "busy": m.get("sut_busy"),
                               "headroom": m.get("client_headroom"), "pending": m.get("client_pending_total"),
                               "pending_limit": m.get("client_workers"), "foreign": m.get("sut_foreign_cpus"),
                               "perf_running_pct": m.get("perf_min_running_pct"), "valid": _valid(m)})
            if c in load_cells and not _valid(m):
                q5["ok"] = False
    if not load_cells:
        q5["ok"] = False
    rep["q5"] = q5
    # 6. scope limit
    kmax = max(ks)
    rows = [r for r in q1["counts"] if r["arm"] == "own-%d" % kmax]
    q6 = {"arm": "own-%d" % kmax, "counters": [r["start_n"] for r in rows],
          "sum_per_request": [r["sum_per_request"] for r in rows], "overflow": overflow,
          "ok": bool(rows) and all(r["evidence_ok"] for r in rows)}
    if overflow is None or any(v is None or v for v in overflow.values()):
        q6["ok"] = False
    rep["q6"] = q6
    rep["ok"] = (not rep["problems"] and q1["ok"] and q2["ok"] and q5["ok"] and q6["ok"] and q4["k"] is not None)
    return rep


def _f(v, fmt="%.3f"):
    return "-" if v is None else fmt % v


def text(rep, cfg):
    rule = cfg["dose"]["pilot_rule"]
    L = ["dose pilot: %s" % cfg["name"]]
    v = rep["q1"]["validate"]
    L.append("1. bootstrap --mode validate: %s" % ("not recorded" if v is None else ", ".join(
        "%s %s" % (a, "OK" if ok else "FAILED") for a, ok in v.items())))
    L.append("   dose counters (start, end, new in window, increments per request, read s before/after, s from the "
             "first read to the window; client slack %.1f s):" % rep["slack_s"])
    for r in rep["q1"]["counts"]:
        L.append("   %-2s %-12s %7s %7s %5s %9s  %s/%s  %s%s  %s" % (
            r["cell"], r["arm"], _f(r["start_n"], "%d"), _f(r["end_n"], "%d"), _f(r["new_in_window"], "%d"),
            _f(r["sum_per_request"], "%.2f"), _f(r["read_s"][0], "%.2f"), _f(r["read_s"][1], "%.2f"),
            _f(r["pre_window_s"], "%.2f"),
            " (OVER HALF THE SLACK)" if r["pre_window_s"] is not None and r["pre_window_s"] > rep["slack_s"] / 2 else "",
            "ok" if r["evidence_ok"] else "EVIDENCE: " + ("; ".join(r["failed"]) or "not evaluated")))
    L.append("   -> %s" % ("PASS" if rep["q1"]["ok"] else "FAIL"))
    L.append("2. instructions:u per request, shared against own (limit %.1f%%):" % (100 * rule["instructions_tol"]))
    for r in rep["q2"]["rows"]:
        L.append("   %-2s K=%-4d own %s  shared %s  %s  %s" % (
            r["cell"], r["k"], _f(r["own"], "%.0f"), _f(r["shared"], "%.0f"), _f(r["diff_pct"], "%+.3f%%"),
            "ok" if r["ok"] else "OUTSIDE"))
    L.append("   -> %s" % ("PASS" if rep["q2"]["ok"] else "FAIL"))
    L.append("3. h = HITM:u (shared - own) per request / K (expected %.1f-%.1f; not gated):" % tuple(rule["h_expected"]))
    for r in rep["q3"]["rows"]:
        L.append("   %-2s K=%-4d HITM:u/req own %s  shared %s  h = %s%s" % (
            r["cell"], r["k"], _f(r["own"], "%.2f"), _f(r["shared"], "%.2f"), _f(r["h"]),
            "" if r["expected"] in (True, None) else "  (outside the expected range)"))
    L.append("   store-stat operations per request, base (counter increments and histogram samples): %s" % ", ".join(
        "%s %s" % (c, _f(v, "%.1f")) for c, v in rep["stat_ops"].items()))
    q4 = rep["q4"]
    L.append("4. K: h x K x %d cycles / base worker cycles per request >= %.1f%% in cell %s (base %s cycles, mean h %s):"
             % (rule["cycles_per_transfer"], 100 * rule["min_share"], q4["cell"], _f(q4["base_cycles"], "%.0f"),
                _f(q4["h_mean"])))
    for r in q4["rows"]:
        L.append("   K=%-4d %.2f%% (with this K's own h: %.2f%%)  %s" % (
            r["k"], 100 * r["share"], 100 * r["share_own_h"], "reaches it" if r["ok"] else "under"))
    L.append("   -> %s" % ("K = %d" % q4["k"] if q4["k"] else "NO K: none of the choices reaches the share"
                           if q4["rows"] else "NO K: h or base cycles missing"))
    L.append("5. gates per leg (worker busy, client headroom, client pending / limit, other tasks on the SUT CPUs, "
             "perf running):")
    for r in rep["q5"]["rows"]:
        L.append("   %-2s %-12s busy %s  headroom %s  pending %s/%s  foreign %s  perf %s  %s" % (
            r["cell"], r["arm"], _f(r["busy"] and 100 * r["busy"], "%.1f%%"),
            _f(r["headroom"] and 100 * r["headroom"], "%.0f%%"), _f(r["pending"], "%d"),
            _f(r["pending_limit"], "%d"), _f(r["foreign"]), _f(r["perf_running_pct"], "%.1f%%"),
            "valid" if r["valid"] else "INVALID"))
    L.append("   -> load cell %s" % ("PASS" if rep["q5"]["ok"] else "FAIL"))
    q6 = rep["q6"]
    L.append("6. scope limit: %s held %s counters; increments per request %s; server.stats_overflow in the stat "
             "dumps: %s" % (q6["arm"], ", ".join(_f(n, "%d") for n in q6["counters"]) or "-",
                            ", ".join(_f(x, "%.2f") for x in q6["sum_per_request"]) or "-",
                            "no dumps read" if q6["overflow"] is None else
                            ", ".join("%s: %s" % (a, "no dump" if v is None else "; ".join(v))
                                      for a, v in q6["overflow"].items() if v is None or v) or "none"))
    L.append("   -> %s" % ("PASS" if q6["ok"] else "FAIL"))
    for p in rep["problems"]:
        L.append("PROBLEM " + p)
    L.append("pilot %s" % ("OK: K = %d" % q4["k"] if rep["ok"] else "NOT clean"))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cfg")
    ap.add_argument("run")
    ap.add_argument("--json")
    a = ap.parse_args()
    with open(a.cfg) as f:
        cfg = json.load(f)
    p = os.path.join(a.run, "results.json")
    if not os.path.exists(p):
        print("no results.json in %s" % a.run)
        return 1
    with open(p) as f:
        res = json.load(f)
    rep = answers(cfg, res, overflow_lines(a.run, [x["name"] for x in cfg["arms"]]))
    sys.stdout.write(text(rep, cfg))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(rep, f, indent=1)
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
