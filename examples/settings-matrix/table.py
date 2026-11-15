#!/usr/bin/env python3
"""Matrix table from the settings-matrix runs.

    python3 examples/settings-matrix/table.py RUNS_DIR [--aa AA_DIR] [--json OUT.json]

RUNS_DIR holds one run directory per row (each with results.json). Each row's
own analysis already has paired intervals and a Holm step inside the row; this
script applies Holm once more across every primary total-cycles comparison of
the whole matrix (the family the price list draws from) and prints the table,
the per-row evidence (TLS handshakes and resumptions, spans, ext_authz checks,
retries, access-log lines, tcmalloc per-CPU bytes, second-hop cost) and the
validity summary.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from epl import experiment, stats  # noqa: E402

GHZ = 2.3


def load(d):
    with open(os.path.join(d, "results.json")) as f:
        return json.load(f)


def pct(c):
    p = (c or {}).get("paired") or {}
    if p.get("effect_pct") is None:
        return "-"
    if p.get("half_width_pct") is None:
        return "%+.2f%%" % p["effect_pct"]
    return "%+.2f%% [%+.2f, %+.2f]" % (p["effect_pct"], p["lo_pct"], p["hi_pct"])


def med(sres, arm, key):
    return ((sres["arms"].get(arm) or {}).get(key) or {}).get("median")


def legs_of(res, shape, arm):
    by = experiment.current_legs(res["legs"])
    return [m for (s, a, r), m in sorted(by.items()) if s == shape and a == arm]


def mean_of(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def evidence(res, shape, arm):
    """Per-request counters that show the setting did what it says, means over valid legs."""
    L = legs_of(res, shape, arm)
    out = {}
    if not L:
        return out

    def per_req(key):
        return mean_of([(m.get("sut_stats_delta") or {}).get(key, 0) / m["responses_raw"]
                        for m in L if m.get("responses_raw")])

    ks = set()
    for m in L:
        ks |= set((m.get("sut_stats_delta") or {}).keys())
    hs = [k for k in ks if k.endswith("ssl.handshake") and k.startswith("listener.")]
    ru = [k for k in ks if k.endswith("ssl.session_reused") and k.startswith("listener.")]
    if hs:
        out["handshakes_per_req"] = per_req(hs[0])
    if ru and hs:
        out["resumed_share"] = mean_of([(m["sut_stats_delta"].get(ru[0], 0) / m["sut_stats_delta"][hs[0]])
                                        for m in L if (m.get("sut_stats_delta") or {}).get(hs[0])])
    for k, name in (("http.ingress_http.ext_authz.ok", "authz_ok_per_req"),
                    ("cluster.origin.upstream_rq_retry", "retries_per_req"),
                    ("http.ingress_http.tracing.random_sampling", "sampled_per_req"),
                    ("http.ingress_http.tracing.not_traceable", "not_traced_per_req")):
        if k in ks:
            out[name] = per_req(k)
    sp = [k for k in ks if "opentelemetry.spans_sent" in k]
    if sp:
        out["spans_sent_per_req"] = per_req(sp[0])
    al = [m for m in L if m.get("access_log_lines") is not None]
    if al:
        # lines over the whole leg (warm-up excluded: the file is emptied before the leg; the
        # measured run's requests are about rps x duration)
        out["access_log_bytes_per_line"] = mean_of([m["access_log_bytes"] / m["access_log_lines"]
                                                    for m in al if m["access_log_lines"]])
        out["access_log_lines_per_measured_req"] = mean_of([
            m["access_log_lines"] / (m["target_rps"] * res["experiment"]["client"]["duration_s"] +
                                     m["target_rps"] * res["experiment"]["client"]["warmup_s"]) for m in al])
    tc = [m.get("tcmalloc_percpu_slab_bytes") for m in L if m.get("tcmalloc_percpu_slab_bytes") is not None]
    if tc:
        out["tcmalloc_percpu_slab_bytes"] = mean_of(tc)
    h2 = [m["hop2_per_req"]["cycles_total"] for m in L if m.get("hop2_per_req")]
    if h2:
        out["hop2_cycles_total"] = mean_of(h2)
        out["hop1_cycles_total"] = mean_of([m["per_req"]["cycles_total"] for m in L if m.get("hop2_per_req")])
    out["busy"] = mean_of([m.get("sut_busy") for m in L])
    out["ctx_switches_per_req"] = mean_of([m["per_req"].get("context_switches") for m in L])
    out["eff_ghz"] = mean_of([m.get("eff_ghz") for m in L])
    out["worker_max_share"] = max(m.get("envoy_worker_max_share") or 0 for m in L)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("--json")
    args = ap.parse_args()
    rows = []
    for d in sorted(os.listdir(args.runs)):
        p = os.path.join(args.runs, d)
        if d == "aa" or not os.path.exists(os.path.join(p, "results.json")):
            continue
        res = load(p)
        exp = res["experiment"]
        an = res["analysis"]
        prim = an["primary_metric"]
        for s, sres in an["shapes"].items():
            for comp in sres["comparisons"]:
                c = comp.get(prim)
                if not c:
                    continue
                rows.append({"run": d, "name": exp["name"], "shape": s, "arm": comp["arm"], "ref": comp["ref"],
                             "primary_metric": prim, "primary": c, "comp": comp, "sres": sres,
                             "ev_arm": evidence(res, s, comp["arm"]), "ev_ref": evidence(res, s, comp["ref"]),
                             "rps": [x for x in exp["shapes"] if x["name"] == s][0]["rps"],
                             "rounds": res["metadata"].get("rounds_done"),
                             "stop": res["metadata"].get("stop_reason"),
                             "legs": len(res["legs"]),
                             "invalid": sum(1 for m in res["legs"] if not m["verdict"]["valid"]),
                             "cpuidle": (res["metadata"]["machine"].get("cpuidle_sut_summary") or {}).get("text"),
                             "cpuidle_unchanged": res["metadata"].get("cpuidle_unchanged"),
                             "harness": res["metadata"].get("harness"),
                             "window": (res["metadata"].get("started_utc"), res["metadata"].get("finished_utc"))})
    live = [r for r in rows if r["primary"]["paired"].get("t_p") is not None and r["primary"]["n"] >= 6]
    for r, a in zip(live, stats.holm([r["primary"]["paired"]["t_p"] for r in live])):
        r["matrix_holm_p"] = a
    print("Matrix Holm family: %d primary rows\n" % len(live))
    print("| Row | Shape @ rps | Arm vs base | Total cycles/req [95% CI] | Holm p (matrix) | A/A hw | "
          "Instructions:u/req | p50 | p99 | Base cyc/req | Arm cyc/req | Base busy | n | Status |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        c, comp, sres = r["primary"], r["comp"], r["sres"]
        mk = r["primary_metric"]
        ins = comp.get("instructions_u_all") if mk == "cycles_total_per_hop" else comp.get("instructions_u")
        hp = r.get("matrix_holm_p")
        print("| %s | %s @ %d | %s vs %s | %s | %s | %s | %s | %s | %s | %.1fk | %.1fk | %.1f%% | %d | %s |" % (
            r["name"][3:], r["shape"], r["rps"], r["arm"], r["ref"], pct(c),
            "-" if hp is None else ("<0.001" if hp < 0.001 else "%.3f" % hp),
            "-" if c.get("aa_floor_half_width_pct") is None else "%.2f" % c["aa_floor_half_width_pct"],
            pct(ins), pct(comp.get("p50_us")), pct(comp.get("p99_us")),
            (med(sres, r["ref"], mk) or 0) / 1e3, (med(sres, r["arm"], mk) or 0) / 1e3,
            100 * (r["ev_ref"].get("busy") or 0), c["n"], c.get("status")))
    print()
    print("Evidence (means over valid legs, arm / base):")
    for r in rows:
        keys = sorted(set(r["ev_arm"]) | set(r["ev_ref"]))
        parts = []
        for k in keys:
            a, b = r["ev_arm"].get(k), r["ev_ref"].get(k)
            f = lambda x: "-" if x is None else ("%.4g" % x)  # noqa: E731
            parts.append("%s %s / %s" % (k, f(a), f(b)))
        print("- %s %s %s: %s" % (r["name"][3:], r["shape"], r["arm"], "; ".join(parts)))
    print()
    print("Runs:")
    seen = set()
    for r in rows:
        if r["run"] in seen:
            continue
        seen.add(r["run"])
        print("- %s: %s rounds (%s), %d legs, %d invalid; %s to %s; idle states %s, unchanged %s; harness %s" % (
            r["run"], r["rounds"], r["stop"], r["legs"], r["invalid"], r["window"][0], r["window"][1],
            r["cpuidle"], r["cpuidle_unchanged"], r["harness"]))
    if args.json:
        out = []
        for r in rows:
            c, comp = r["primary"], r["comp"]
            mk = r["primary_metric"]
            o = {k: r[k] for k in ("run", "name", "shape", "arm", "ref", "rps", "primary_metric", "rounds",
                                   "legs", "invalid", "ev_arm", "ev_ref", "cpuidle", "matrix_holm_p")
                 if k in r}
            for key in (mk, "instructions_u", "instructions_u_all", "cycles_u", "cycles_k", "cycles_total",
                        "cycles_total_all", "p50_us", "p99_us"):
                if comp.get(key):
                    o[key] = {x: comp[key]["paired"].get(x) for x in ("effect_pct", "lo_pct", "hi_pct",
                                                                       "half_width_pct", "t_p")}
                    o[key]["n"] = comp[key]["n"]
                    o[key]["won"] = comp[key]["pairs_won"]
                    o[key]["status"] = comp[key].get("status")
                    o[key]["aa_hw"] = comp[key].get("aa_floor_half_width_pct")
                    o[key]["ref_median"] = med(r["sres"], r["ref"], key)
                    o[key]["arm_median"] = med(r["sres"], r["arm"], key)
            out.append(o)
        with open(args.json, "w") as f:
            json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
