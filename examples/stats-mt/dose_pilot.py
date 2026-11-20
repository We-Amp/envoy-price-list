#!/usr/bin/env python3
"""The answers of the dose run's pilot (make.py dose-pilot.json), printed from its legs so that
nobody computes them by hand, and the pilot record the queue checks (--json): the recommended K
and client connections per worker. Exit 0 when the pilot is clean; else 1.

    python3 examples/stats-mt/dose_pilot.py PILOT_CFG PILOT_DIR [--json RECORD.json]

The latest attempt of each cell and arm is used, valid or not. The config's `pairs` name every
own/shared pair (cell, connections per worker, K, listener address, role). A pair or cell
marked exploratory (the loopback pair, the load cell) is printed and never decides.

  1. Config and stat count: every arm's bootstrap passed `--mode validate` on the binary; the
     dose counters before and after the window, increments per request, the admin read times
     (the legs' own evidence items decide).
  2. Per pair, one round each (labelled as such): instructions:u per request shared against own
     (equal within 0.5%); h = HITM:u (shared - own) per request / K (expected 1.0-1.4, not
     gated), with its parts: local and remote HITM loads per request of own and of shared; rho = 100 x ln(shared / own) of worker cycles per request; clean L3 hits per update
     (L3 hits minus local HITM loads, per request and counter), own minus shared: the footprint
     of the own arm's per-connection counter sets.
  3. K: the smallest of the choices with h x K x 100 cycles / own worker cycles per request
     >= 2.5% in the K cell (h: the mean over the choices; own: that K's own arm).
  4. Connections per worker: the count with the smaller |clean L3 hits per update, own - shared|
     at the middle K in the K cell, provided every leg at that count in the connection cells is
     valid and passes its evidence; else the other count if its legs do.
  5. Gates and seconds per leg, per leg; the estimated length of the run and of the evidence
     legs at the mean.
  6. Scope limit: the own arms' counters all exist and count (the evidence items), and no
     server.stats_overflow stat in the saved stat dumps.
The pilot is clean when 1, 2 and 6 pass, every leg outside the exploratory ones is valid, and 3
and 4 each give a value.
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

L3_HIT = "mem_load_uops_retired.l3_hit"
RUN_LEGS, EVIDENCE_LEGS = 165, 48


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


def clean_l3(m, k):
    """L3 hits that are not local HITM loads, per request and counter update; None unless both
    events were counted."""
    e = ((m or {}).get("per_req") or {}).get("events") or {}
    hit, hitm = u_table.ev_get(e, L3_HIT), u_table.ev_get(e, u_table.HITM[0])
    return None if hit is None or hitm is None else (hit - hitm) / k


def hitm_parts(m):
    """(local, remote) HITM loads per request of a leg, either event spelling; None where an
    event was not counted."""
    e = ((m or {}).get("per_req") or {}).get("events") or {}
    return u_table.ev_get(e, u_table.HITM[0]), u_table.ev_get(e, u_table.HITM[1])


def runs_in(arm, shape):
    return arm.get("shapes") is None or shape in arm["shapes"]


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


def choose_k(rows, rule):
    """The smallest K whose share reaches the rule's minimum; rows: [{k, share}]."""
    for r in sorted(rows, key=lambda r: r["k"]):
        if r["share"] is not None and r["share"] >= rule["min_share"]:
            return r["k"]
    return None


def choose_connections(terms, gates):
    """The connection count with the smaller |footprint term| among those whose gates pass;
    terms: {count: clean L3 hits per update, own - shared, or None}, gates: {count: bool}.
    Without a term for every count there is no choice (the rule cannot be applied)."""
    if not terms or any(v is None for v in terms.values()):
        return None
    for c in sorted(terms, key=lambda c: (abs(terms[c]), -c)):
        if gates.get(c):
            return c
    return None


def answers(cfg, res, overflow=None):
    d = cfg["dose"]
    rule = d["pilot_rule"]
    legs = latest(res)
    cells = {c["shape"]: c for c in d["cells"]}
    arms = {a["name"]: a for a in cfg["arms"]}
    lead = max([cfg["measure"]["lead_in_s"]] + [sh.get("lead_in_s") or 0 for sh in cfg["shapes"]])
    rep = {"config": cfg["name"], "rates_key": d["rates_key"], "problems": [],
           "slack_s": cfg["client"]["duration_s"] - lead - cfg["measure"]["window_s"]}

    def exploratory(shape, arm):
        return bool(cells[shape].get("exploratory") or arms[arm].get("exploratory"))
    # every scheduled leg: present, valid, its evidence
    rep["legs"] = []
    for sh in cfg["shapes"]:
        for a in cfg["arms"]:
            if not runs_in(a, sh["name"]):
                continue
            m = legs.get((sh["name"], a["name"]))
            v, sc, ev = (m or {}).get("verdict") or {}, (m or {}).get("stat_count") or {}, (m or {}).get("evidence") or {}
            row = {"cell": cells[sh["name"]]["cell"], "shape": sh["name"], "connections": cells[sh["name"]]["connections"],
                   "arm": a["name"], "exploratory": exploratory(sh["name"], a["name"]), "present": m is not None,
                   "valid": _valid(m), "reasons": v.get("reasons") or [],
                   "start_n": sc.get("start_n"), "end_n": sc.get("end_n"), "new_in_window": sc.get("new_in_window"),
                   "sum_per_request": sc.get("sum_per_request"), "pre_window_s": sc.get("pre_window_s"),
                   "read_s": [sc.get("start_read_s"), sc.get("end_read_s")],
                   "evidence_ok": ev.get("ok"), "failed": ev.get("failed") or [],
                   "busy": (m or {}).get("sut_busy"), "headroom": (m or {}).get("client_headroom"),
                   "pending": (m or {}).get("client_pending_total"), "pending_limit": (m or {}).get("client_workers"),
                   "foreign": (m or {}).get("sut_foreign_cpus"), "perf_running_pct": (m or {}).get("perf_min_running_pct"),
                   "wall_s": (m or {}).get("wall_s")}
            rep["legs"].append(row)
            if row["exploratory"]:
                continue
            if m is None:
                rep["problems"].append("missing leg: %s %s" % (sh["name"], a["name"]))
            elif not row["valid"]:
                rep["problems"].append("invalid leg: %s %s: %s" % (sh["name"], a["name"], "; ".join(row["reasons"])))
    deciding = [r for r in rep["legs"] if not r["exploratory"]]
    # 1. validate and stat count
    bv = (res.get("metadata") or {}).get("bootstrap_validate")
    rep["q1"] = {"validate": {a: (bv or {}).get(a, {}).get("ok") for a in arms} if bv else None,
                 "ok": bool(bv) and all((bv or {}).get(a, {}).get("ok") for a in arms)
                 and all(r["evidence_ok"] for r in deciding)}
    # 2. per pair
    tol = 100.0 * rule["instructions_tol"]
    pairs, q2 = [], True
    for p in d["pairs"]:
        own, sh = legs.get((p["shape"], p["own"])), legs.get((p["shape"], p["shared"]))
        io, ish, co, cs_ = _ins(own), _ins(sh), _cyc(own), _cyc(sh)
        ho, hs = u_table.hitm_per_req(own or {}), u_table.hitm_per_req(sh or {})
        lo, ls = clean_l3(own, p["k"]), clean_l3(sh, p["k"])
        row = dict(p, own_cycles=co, shared_cycles=cs_, own_instructions=io,
                   hitm_own=dict(zip(("local", "remote"), hitm_parts(own))),
                   hitm_shared=dict(zip(("local", "remote"), hitm_parts(sh))),
                   instr_pct=100.0 * math.log(ish / io) if io and ish else None,
                   h=(hs - ho) / p["k"] if ho is not None and hs is not None else None,
                   rho_pct=100.0 * math.log(cs_ / co) if co and cs_ else None,
                   clean_l3_own=lo, clean_l3_shared=ls,
                   footprint=lo - ls if lo is not None and ls is not None else None,
                   valid=_valid(own) and _valid(sh) and bool(((own or {}).get("evidence") or {}).get("ok"))
                   and bool(((sh or {}).get("evidence") or {}).get("ok")))
        row["instr_ok"] = row["instr_pct"] is not None and abs(row["instr_pct"]) <= tol
        row["h_expected"] = None if row["h"] is None else rule["h_expected"][0] <= row["h"] <= rule["h_expected"][1]
        pairs.append(row)
        if not p.get("exploratory") and not row["instr_ok"]:
            q2 = False
    rep["pairs"], rep["q2"] = pairs, {"ok": q2}
    # beside it: the store-stat operations per request of base (the model row's cross-check)
    rep["stat_ops"] = {}
    for (shape, arm), m in legs.items():
        so, n = m.get("stat_ops"), m.get("responses")
        if arm == "base" and so and n:
            rep["stat_ops"][shape] = (so["counter_incs"] + so["histogram_samples"]) / n
    # 3. K
    kp = [r for r in pairs if r["role"] == "k"]
    hs = [r["h"] for r in kp if r["h"] is not None]
    hm = sum(hs) / len(hs) if kp and len(hs) == len(kp) else None
    rows = [{"k": r["k"], "own_cycles": r["own_cycles"], "rho_pct": r["rho_pct"],
             "share": hm * r["k"] * rule["cycles_per_transfer"] / r["own_cycles"] if hm is not None and r["own_cycles"]
             else None,
             "share_own_h": r["h"] * r["k"] * rule["cycles_per_transfer"] / r["own_cycles"]
             if r["h"] is not None and r["own_cycles"] else None} for r in kp]
    rep["q3"] = {"cell": d["k_cell"], "h_mean": hm, "rows": rows, "k": choose_k(rows, rule)}
    # 4. connections per worker
    terms, gates = {}, {}
    for c in d["connections_choices"]:
        mine = [r for r in pairs if r["connections"] == c and r["k"] == d["mid"] and not r.get("exploratory")
                and r["cell"] in d["connection_cells"]]
        at = [r for r in mine if r["cell"] == d["k_cell"]]
        terms[c] = at[0]["footprint"] if at else None
        gates[c] = bool(mine) and all(r["valid"] for r in mine) and {r["cell"] for r in mine} == set(d["connection_cells"])
    rep["q4"] = {"terms": terms, "gates": gates, "connections": choose_connections(terms, gates)}
    # 5. seconds per leg
    ws = [r["wall_s"] for r in rep["legs"] if r["wall_s"] is not None]
    mean_s = sum(ws) / len(ws) if ws else None
    rep["q5"] = {"mean_s": mean_s, "max_s": max(ws) if ws else None, "legs": len(ws),
                 "run_h": None if mean_s is None else RUN_LEGS * mean_s / 3600.0,
                 "evidence_min": None if mean_s is None else EVIDENCE_LEGS * mean_s / 60.0,
                 "ok": all(r["valid"] for r in deciding) and bool(deciding)}
    # 6. scope limit
    owns = [r for r in deciding if r["arm"].startswith("own-") and r["start_n"] is not None]
    big = max(owns, key=lambda r: r["start_n"]) if owns else None
    q6 = {"overflow": overflow, "largest": big and {k: big[k] for k in ("shape", "arm", "start_n", "read_s", "pre_window_s")},
          "ok": bool(owns) and all(r["evidence_ok"] for r in deciding if r["arm"].startswith("own-"))}
    if overflow is None or any(v is None or v for v in overflow.values()):
        q6["ok"] = False
    rep["q6"] = q6
    rec = {"counters": rep["q3"]["k"], "connections": rep["q4"]["connections"]}
    rep["recommend"] = rec
    rep["ok"] = (not rep["problems"] and rep["q1"]["ok"] and q2 and q6["ok"] and rec["counters"] is not None
                 and rec["connections"] is not None)
    return rep


def _f(v, fmt="%.3f"):
    return "-" if v is None else fmt % v


def text(rep, cfg):
    d = cfg["dose"]
    rule = d["pilot_rule"]
    L = ["dose pilot: %s" % cfg["name"]]
    v = rep["q1"]["validate"]
    L.append("1. bootstrap --mode validate: %s" % ("not recorded" if v is None else ", ".join(
        "%s %s" % (a, "OK" if ok else "FAILED") for a, ok in v.items())))
    L.append("   dose counters per leg (start, end, new in window, increments per request, admin read s before/after, "
             "s from the first read to the window; client slack %.1f s):" % rep["slack_s"])
    for r in rep["legs"]:
        L.append("   %-2s c%-2d %-13s %7s %7s %5s %9s  %s/%s  %s%s  %s%s" % (
            r["cell"], r["connections"], r["arm"], _f(r["start_n"], "%d"), _f(r["end_n"], "%d"),
            _f(r["new_in_window"], "%d"), _f(r["sum_per_request"], "%.2f"), _f(r["read_s"][0], "%.2f"),
            _f(r["read_s"][1], "%.2f"), _f(r["pre_window_s"], "%.2f"),
            " (OVER HALF THE SLACK)" if r["pre_window_s"] is not None and r["pre_window_s"] > rep["slack_s"] / 2 else "",
            "ok" if r["evidence_ok"] else "EVIDENCE: " + ("; ".join(r["failed"]) or "not evaluated"),
            " (exploratory)" if r["exploratory"] else ""))
    L.append("   -> %s" % ("PASS" if rep["q1"]["ok"] else "FAIL"))
    L.append("2. per own/shared pair, ONE ROUND each (not an estimate): instructions:u shared against own (limit "
             "%.1f%%), h = HITM:u (shared - own) / K (expected %.1f-%.1f, not gated), rho = 100 x ln(shared / own) "
             "worker cycles, clean L3 hits per update own - shared (the own arm's footprint):" % (
                 100 * rule["instructions_tol"], rule["h_expected"][0], rule["h_expected"][1]))
    for r in rep["pairs"]:
        L.append("   %-2s c%-2d K=%-4d %-9s %-11s instr %s%s  h %s%s  rho %s  clean L3/update own %s shared %s diff %s%s" % (
            r["cell"], r["connections"], r["k"], r["address"], r["role"], _f(r["instr_pct"], "%+.3f%%"),
            "" if r["instr_ok"] else " OUTSIDE", _f(r["h"]),
            "" if r["h_expected"] in (True, None) else " (outside the expected range)", _f(r["rho_pct"], "%+.2f"),
            _f(r["clean_l3_own"], "%.4f"), _f(r["clean_l3_shared"], "%.4f"), _f(r["footprint"], "%+.4f"),
            " (exploratory)" if r.get("exploratory") else ""))
        L.append("         h's parts, HITM:u loads per request: own local %s remote %s, shared local %s remote %s; "
                 "(shared - own) local %s remote %s; worker cycles own %s shared %s, instructions:u own %s" % (
                     _f(r["hitm_own"]["local"], "%.2f"), _f(r["hitm_own"]["remote"], "%.2f"),
                     _f(r["hitm_shared"]["local"], "%.2f"), _f(r["hitm_shared"]["remote"], "%.2f"),
                     _f(None if r["hitm_own"]["local"] is None or r["hitm_shared"]["local"] is None
                        else r["hitm_shared"]["local"] - r["hitm_own"]["local"], "%+.2f"),
                     _f(None if r["hitm_own"]["remote"] is None or r["hitm_shared"]["remote"] is None
                        else r["hitm_shared"]["remote"] - r["hitm_own"]["remote"], "%+.2f"),
                     _f(r["own_cycles"], "%.0f"), _f(r["shared_cycles"], "%.0f"), _f(r["own_instructions"], "%.0f")))
    lb = [r for r in rep["pairs"] if r["role"] == "loopback"]
    wc = [r for r in rep["pairs"] if r["role"] == "k" and lb and r["k"] == lb[0]["k"]]
    if lb and wc and lb[0]["h"] is not None and wc[0]["h"] is not None:
        L.append("   loopback against wildcard listener at K = %d (the shared local-address object; exploratory): h %s "
                 "against %s, rho %s against %s" % (lb[0]["k"], _f(lb[0]["h"]), _f(wc[0]["h"]),
                                                    _f(lb[0]["rho_pct"], "%+.2f"), _f(wc[0]["rho_pct"], "%+.2f")))
    L.append("   store-stat operations per request, base (counter increments and histogram samples): %s" % (
        ", ".join("%s %s" % (c, _f(x, "%.1f")) for c, x in rep["stat_ops"].items()) or "-"))
    L.append("   -> instructions %s" % ("PASS" if rep["q2"]["ok"] else "FAIL"))
    q3 = rep["q3"]
    L.append("3. K: h x K x %d cycles / own worker cycles per request >= %.1f%% in cell %s (mean h %s):" % (
        rule["cycles_per_transfer"], 100 * rule["min_share"], q3["cell"], _f(q3["h_mean"])))
    for r in q3["rows"]:
        L.append("   K=%-4d own %s cycles  %s (with this K's own h: %s; this pair's one-round rho %s)  %s" % (
            r["k"], _f(r["own_cycles"], "%.0f"), _f(r["share"] and 100 * r["share"], "%.2f%%"),
            _f(r["share_own_h"] and 100 * r["share_own_h"], "%.2f%%"), _f(r["rho_pct"], "%+.2f"),
            "reaches it" if r["share"] is not None and r["share"] >= rule["min_share"] else "under"))
    L.append("   own cycles grow with K (the logger's own cost per update), so the share rises more slowly than K")
    L.append("   -> %s" % ("K = %d" % q3["k"] if q3["k"] else "NO K"))
    q4 = rep["q4"]
    L.append("4. connections per worker: |clean L3 hits per update, own - shared| at K = %d in cell %s, and the gates "
             "of every leg at that count in cells %s:" % (d["mid"], d["k_cell"], ", ".join(d["connection_cells"])))
    for c in sorted(q4["terms"], reverse=True):
        L.append("   %2d connections: %s  gates %s" % (c, _f(q4["terms"][c], "%+.4f"), "pass" if q4["gates"][c] else "FAIL"))
    L.append("   -> %s" % ("%d connections per worker" % q4["connections"] if q4["connections"] else "NO CHOICE"))
    L.append("5. gates and seconds per leg (worker busy, client headroom, client pending / limit, other tasks on the "
             "SUT CPUs, perf running, wall s):")
    for r in rep["legs"]:
        L.append("   %-2s c%-2d %-13s busy %s  headroom %s  pending %s/%s  foreign %s  perf %s  %s s  %s%s" % (
            r["cell"], r["connections"], r["arm"], _f(r["busy"] and 100 * r["busy"], "%.1f%%"),
            _f(r["headroom"] and 100 * r["headroom"], "%.0f%%"), _f(r["pending"], "%d"), _f(r["pending_limit"], "%d"),
            _f(r["foreign"]), _f(r["perf_running_pct"], "%.1f%%"), _f(r["wall_s"], "%.0f"),
            "valid" if r["valid"] else "INVALID", " (exploratory)" if r["exploratory"] else ""))
    q5 = rep["q5"]
    L.append("   seconds per leg: mean %s, max %s over %d legs; at the mean the %d-leg run takes %s h and the %d "
             "evidence legs %s min" % (_f(q5["mean_s"], "%.0f"), _f(q5["max_s"], "%.0f"), q5["legs"], RUN_LEGS,
                                       _f(q5["run_h"], "%.2f"), EVIDENCE_LEGS, _f(q5["evidence_min"], "%.0f")))
    L.append("   -> deciding legs %s" % ("PASS" if q5["ok"] else "FAIL"))
    q6 = rep["q6"]
    g = q6["largest"]
    L.append("6. scope limit: largest counter set %s; server.stats_overflow in the stat dumps: %s" % (
        "-" if not g else "%s %s, %d counters, admin read %s s before and %s s after the window" % (
            g["shape"], g["arm"], g["start_n"], _f(g["read_s"][0], "%.2f"), _f(g["read_s"][1], "%.2f")),
        "no dumps read" if q6["overflow"] is None else
        ", ".join("%s: %s" % (a, "no dump" if x is None else "; ".join(x))
                  for a, x in q6["overflow"].items() if x is None or x) or "none"))
    L.append("   -> %s" % ("PASS" if q6["ok"] else "FAIL"))
    for p in rep["problems"]:
        L.append("PROBLEM " + p)
    rec = rep["recommend"]
    if rep["ok"]:
        L.append("pilot OK: recommend {\"%s\": {\"counters\": %d, \"connections\": %d}}" % (
            rep["rates_key"], rec["counters"], rec["connections"]))
    else:
        L.append("pilot NOT clean (K %s, connections %s)" % (rec["counters"], rec["connections"]))
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
