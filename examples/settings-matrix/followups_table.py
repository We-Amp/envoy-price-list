#!/usr/bin/env python3
"""Tables for the settings-matrix follow-ups (followups.py).

    python3 examples/settings-matrix/followups_table.py RUNS_DIR [--json OUT.json]

RUNS_DIR holds one run directory per follow-up (f1-two-hop, f2-buffer-limit,
f2-ext-authz, f3-tls-cert, f3-tls-resumption, aa-tls, aa-h2). Every comparison is
paired per round: 100*ln(arm/ref) per round, mean with a 95% t interval. The
primary rows (PRIMARY) get one Holm step together; everything else is
exploratory. Two-hop comparisons can take a value from a different hop of each
arm (for example the second hop of the two-hop arm against the single hop).
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from epl import experiment, stats  # noqa: E402


def g_total(m):
    return m["per_req"]["cycles_total"]


def g_hop2(m):
    return (m.get("hop2_per_req") or {}).get("cycles_total")


def g_all(m):
    return m["per_req"].get("cycles_total_all", m["per_req"]["cycles_total"])


def g_per_hop(m):
    return m["per_req"].get("cycles_total_per_hop", m["per_req"]["cycles_total"])


def g_key(*path):
    def f(m):
        v = m
        for p in path:
            v = (v or {}).get(p)
        return v
    return f


G = {"cycles_total": g_total, "hop1": g_total, "hop2": g_hop2, "all": g_all, "per_hop": g_per_hop,
     "instructions_u": g_key("per_req", "instructions_u"), "cycles_u": g_key("per_req", "cycles_u"),
     "cycles_k": g_key("per_req", "cycles_k"), "p50": g_key("latency_us", "p50"),
     "p99": g_key("latency_us", "p99")}

# (run, shape, arm, arm metric, ref arm, ref metric, label)
PRIMARY = [
    ("f1-two-hop", "s", "two-hop-ppd", "per_hop", "one-hop-ppd", "cycles_total",
     "two hops, even (pool per downstream connection on both), per hop vs one hop with the same setting"),
    ("f1-two-hop", "s", "two-hop-stock", "per_hop", "one-hop", "cycles_total",
     "two hops, stock pool (second hop concentrated), per hop vs one hop"),
    ("f1-two-hop", "s", "one-hop-ppd", "cycles_total", "one-hop", "cycles_total",
     "one hop: pool per downstream connection vs stock pool"),
    ("f2-buffer-limit", "m", "buffer-4k", "cycles_total", "buffer-default", "cycles_total",
     "buffer limit 4 KiB, 16 KB body"),
    ("f2-buffer-limit", "s2k", "buffer-4k", "cycles_total", "buffer-default", "cycles_total",
     "buffer limit 4 KiB, 2 KB body (fits)"),
    ("f2-ext-authz", "s", "authz-grpc", "cycles_total", "authz-off", "cycles_total", "ext_authz gRPC vs off"),
    ("f2-ext-authz", "s", "authz-http", "cycles_total", "authz-off", "cycles_total", "ext_authz HTTP vs off"),
    ("f3-tls-cert", "tls-ka", "ecdsa-p256", "cycles_total", "rsa2048", "cycles_total", "ECDSA vs RSA, keep-alive"),
    ("f3-tls-cert", "tls-hs-st", "ecdsa-p256", "cycles_total", "rsa2048", "cycles_total",
     "ECDSA vs RSA, handshake-heavy, staggered"),
    ("f3-tls-resumption", "tls-hs-st", "resumption-on", "cycles_total", "resumption-off", "cycles_total",
     "resumption on vs off, staggered"),
]

EXPLORATORY = [
    ("f1-two-hop", "s", "two-hop-ppd", "all", "one-hop-ppd", "cycles_total", "two hops even, both hops together"),
    ("f1-two-hop", "s", "two-hop-ppd", "hop1", "one-hop-ppd", "cycles_total", "two hops even, first hop"),
    ("f1-two-hop", "s", "two-hop-ppd", "hop2", "one-hop-ppd", "cycles_total", "two hops even, second hop"),
    ("f1-two-hop", "s", "two-hop-stock", "all", "one-hop", "cycles_total", "two hops stock, both hops together"),
    ("f1-two-hop", "s", "two-hop-stock", "hop1", "one-hop", "cycles_total", "two hops stock, first hop"),
    ("f1-two-hop", "s", "two-hop-stock", "hop2", "one-hop", "cycles_total", "two hops stock, second hop"),
    ("f1-two-hop", "s", "two-hop-ppd", "all", "one-hop", "cycles_total",
     "two hops even, both hops together vs the stock single hop"),
    ("f1-two-hop", "s", "two-hop-ppd", "all", "two-hop-stock", "all", "even chain vs stock chain, both hops"),
    ("f1-two-hop", "s", "two-hop-ppd", "hop2", "two-hop-stock", "hop2", "even vs stock chain, second hop"),
    ("f1-two-hop", "s", "two-hop-ppd", "p50", "one-hop-ppd", "p50", "two hops even, p50 end to end"),
    ("f1-two-hop", "s", "two-hop-ppd", "p99", "one-hop-ppd", "p99", "two hops even, p99 end to end"),
    ("f1-two-hop", "s", "two-hop-stock", "p50", "one-hop", "p50", "two hops stock, p50 end to end"),
    ("f1-two-hop", "s", "two-hop-stock", "p99", "one-hop", "p99", "two hops stock, p99 end to end"),
    ("f1-two-hop", "s", "two-hop-ppd", "p50", "two-hop-stock", "p50", "even vs stock chain, p50"),
    ("f1-two-hop", "s", "two-hop-ppd", "p99", "two-hop-stock", "p99", "even vs stock chain, p99"),
    ("f2-buffer-limit", "m", "buffer-4k", "cycles_k", "buffer-default", "cycles_k", "buffer 16 KB, kernel cycles"),
    ("f2-buffer-limit", "m", "buffer-4k", "cycles_u", "buffer-default", "cycles_u", "buffer 16 KB, user cycles"),
    ("f2-buffer-limit", "s2k", "buffer-4k", "instructions_u", "buffer-default", "instructions_u",
     "buffer 2 KB, instructions:u"),
    ("f2-ext-authz", "s", "authz-grpc", "cycles_total", "authz-http", "cycles_total", "ext_authz gRPC vs HTTP"),
    ("f2-ext-authz", "s", "authz-grpc", "cycles_u", "authz-off", "cycles_u", "ext_authz gRPC, user cycles"),
    ("f2-ext-authz", "s", "authz-grpc", "cycles_k", "authz-off", "cycles_k", "ext_authz gRPC, kernel cycles"),
    ("f2-ext-authz", "s", "authz-grpc", "p50", "authz-off", "p50", "ext_authz gRPC, p50"),
    ("f2-ext-authz", "s", "authz-http", "p50", "authz-off", "p50", "ext_authz HTTP, p50"),
    ("f3-tls-cert", "tls-hs-st", "ecdsa-p256", "p50", "rsa2048", "p50", "ECDSA vs RSA staggered, p50"),
    ("f3-tls-cert", "tls-hs-st", "ecdsa-p256", "p99", "rsa2048", "p99", "ECDSA vs RSA staggered, p99"),
    ("f3-tls-cert", "tls-ka", "ecdsa-p256", "p99", "rsa2048", "p99", "ECDSA vs RSA keep-alive, p99"),
    ("f3-tls-resumption", "tls-hs-st", "resumption-on", "p50", "resumption-off", "p50", "resumption staggered, p50"),
    ("f3-tls-resumption", "tls-hs-st", "resumption-on", "p99", "resumption-off", "p99", "resumption staggered, p99"),
]


def load(d):
    with open(os.path.join(d, "results.json")) as f:
        return json.load(f)


def by_round(res, shape, arm):
    return {r: m for (s, a, r), m in experiment.current_legs(res["legs"]).items() if s == shape and a == arm}


def compare(runs, row):
    run, shape, arm, am, ref, rm, label = row
    res = runs.get(run)
    if not res:
        return {"label": label, "run": run, "missing": True}
    A, R = by_round(res, shape, arm), by_round(res, shape, ref)
    rounds = sorted(set(A) & set(R))
    av = [G[am](A[r]) for r in rounds]
    rv = [G[rm](R[r]) for r in rounds]
    keep = [(a, b) for a, b in zip(av, rv) if a and b]
    p = stats.paired_log_ratio([b for _, b in keep], [a for a, _ in keep])
    won = sum(1 for a, b in keep if a < b)
    med = lambda xs: stats.median(xs) if xs else None  # noqa: E731
    return {"label": label, "run": run, "shape": shape, "arm": arm, "arm_metric": am, "ref": ref, "ref_metric": rm,
            "n": p.get("n"), "effect_pct": p.get("effect_pct"), "lo_pct": p.get("lo_pct"), "hi_pct": p.get("hi_pct"),
            "half_width_pct": p.get("half_width_pct"), "t_p": p.get("t_p"), "arm_cheaper": won,
            "arm_median": med([a for a, _ in keep]), "ref_median": med([b for _, b in keep])}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def rng(xs):
    xs = [x for x in xs if x is not None]
    return (min(xs), max(xs)) if xs else None


def evidence(res, shape, arm):
    L = list(by_round(res, shape, arm).values())
    if not L:
        return {}
    out = {"legs": len(L)}

    def per_req(src, pred):
        return mean([sum(v for k, v in (m.get(src) or {}).items() if pred(k)) / m["responses_raw"]
                     for m in L if m.get("responses_raw")])

    out["busy"] = mean([m.get("sut_busy") for m in L])
    out["worker_max_share"] = rng([m.get("envoy_worker_max_share") for m in L])
    out["worker_max_busy"] = rng([m.get("envoy_worker_max_busy") for m in L])
    out["p50_us"] = rng([(m.get("latency_us") or {}).get("p50") for m in L])
    out["p99_us"] = rng([(m.get("latency_us") or {}).get("p99") for m in L])
    out["ctx_switches_per_req"] = mean([m["per_req"].get("context_switches") for m in L])
    out["client_pending_total"] = rng([m.get("client_pending_total") for m in L])
    out["client_cx_total"] = rng([m.get("client_cx_total") for m in L])
    out["client_overflow"] = rng([sum((m.get("client_overflow") or {}).values()) for m in L])
    out["upstream_cx_opened_in_window"] = rng([m.get("upstream_cx_opened") for m in L])
    if any(m.get("hop2_workers") for m in L):
        hw = [m["hop2_workers"] for m in L if m.get("hop2_workers")]
        out["hop2_worker_max_share"] = rng([h.get("worker_max_share") for h in hw])
        out["hop2_worker_min_share"] = rng([h.get("worker_min_share") for h in hw])
        out["hop2_worker_max_busy"] = rng([h.get("worker_max_busy") for h in hw])
        out["hop2_busy"] = mean([m.get("hop2_busy") for m in L])
        out["hop1_cycles"] = mean([m["per_req"]["cycles_total"] for m in L])
        out["hop2_cycles"] = mean([(m.get("hop2_per_req") or {}).get("cycles_total") for m in L])
        out["hop2_ctx_switches_per_req"] = mean([(m.get("hop2_per_req") or {}).get("context_switches") for m in L])
        cs = [m.get("conn_hop2_downstream") or {} for m in L]
        out["hop2_conns"] = rng([c.get("conns") for c in cs])
        out["hop2_conns_over_1pct"] = rng([c.get("conns_over_1pct_of_mean") for c in cs])
        out["hop2_top16_share"] = rng([c.get("top16_share") for c in cs])
        out["hop1_upstream_cx_active_end"] = rng([(m.get("sut_stats_end") or {}).get("cluster.origin.upstream_cx_active")
                                                  for m in L])
    fl = lambda k: "flow_control" in k  # noqa: E731
    if any(fl(k) for m in L for k in (m.get("sut_stats_delta") or {})):
        keys = sorted({k for m in L for k in (m.get("sut_stats_delta") or {}) if fl(k)})
        out["flow_control_per_req"] = {k: per_req("sut_stats_delta", lambda x, k=k: x == k) for k in keys}
        out["tcp_segments"] = {"downstream": mean([(m.get("conn_downstream") or {}).get("segs_total", 0) / m["responses_raw"]
                                                   for m in L if m.get("responses_raw")])}
    for k, name in (("http.ingress_http.ext_authz.ok", "authz_ok_per_req"),
                    ("cluster.ext_authz.upstream_cx_total", "authz_cx_opened_per_req"),
                    ("cluster.ext_authz.upstream_rq_total", "authz_rq_per_req")):
        if any(k in (m.get("sut_stats_delta") or {}) for m in L):
            out[name] = per_req("sut_stats_delta", lambda x, k=k: x == k)
    hs = per_req("sut_stats_delta", lambda x: x.startswith("listener.") and x.endswith("ssl.handshake"))
    if hs:
        out["handshakes_per_req"] = hs
        ru = per_req("sut_stats_delta", lambda x: x.startswith("listener.") and x.endswith("ssl.session_reused"))
        out["resumed_share"] = (ru / hs) if hs else None
    tls_end = {}
    for m in L:
        for k, v in (m.get("sut_stats_end") or {}).items():
            if ".ssl." in k:
                short = k.split(".ssl.", 1)[1]
                tls_end.setdefault(short, 0)
                tls_end[short] += v
    if tls_end:
        out["tls_negotiated_counts_sum"] = tls_end
    return out


def fmt(c):
    if c.get("missing"):
        return "| %s | (not run) |" % c["label"]
    if c.get("effect_pct") is None:
        return "| %s | - |" % c["label"]
    return "| %s | %+.2f%% [%+.2f, %+.2f] | %s | %d/%d | %.1fk -> %.1fk |" % (
        c["label"], c["effect_pct"], c["lo_pct"], c["hi_pct"],
        "%.2g" % c["t_p"] if c.get("t_p") is not None else "-", c["arm_cheaper"], c["n"],
        (c["ref_median"] or 0) / 1e3, (c["arm_median"] or 0) / 1e3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("--json")
    a = ap.parse_args()
    runs = {}
    for d in sorted(os.listdir(a.runs)):
        if os.path.exists(os.path.join(a.runs, d, "results.json")):
            runs[d] = load(os.path.join(a.runs, d))
    prim = [compare(runs, r) for r in PRIMARY]
    ps = [c["t_p"] for c in prim if c.get("t_p") is not None]
    adj = iter(stats.holm(ps))
    for c in prim:
        if c.get("t_p") is not None:
            c["holm_p"] = next(adj)
    expl = [compare(runs, r) for r in EXPLORATORY]
    print("Primary rows (Holm across %d)\n" % len(ps))
    print("| Row | Effect [95% CI] | raw p | arm cheaper | ref -> arm median |\n|---|---|---|---|---|")
    for c in prim:
        print(fmt(c) + (" Holm p %.2g" % c["holm_p"] if c.get("holm_p") is not None else ""))
    print("\nExploratory\n")
    print("| Row | Effect [95% CI] | raw p | arm cheaper | ref -> arm median |\n|---|---|---|---|---|")
    for c in expl:
        print(fmt(c))
    ev = {}
    for name, res in runs.items():
        for s in res["experiment"]["shapes"] if "experiment" in res else []:
            for arm in res["experiment"]["arms"]:
                ev["%s/%s/%s" % (name, s["name"], arm["name"])] = evidence(res, s["name"], arm["name"])
    print("\nEvidence (means or [min, max] over valid legs)\n")
    for k, v in ev.items():
        print("- %s: %s" % (k, json.dumps(v, sort_keys=True, default=str)))
    print("\nRuns\n")
    for name, res in runs.items():
        md = res.get("metadata") or {}
        print("- %s: %s rounds, %s legs, %s invalid; %s; %s to %s" % (
            name, md.get("rounds_done"), len(res["legs"]),
            sum(1 for m in res["legs"] if not m.get("verdict", {}).get("valid")), md.get("stop_reason"),
            md.get("started_utc"), md.get("finished_utc")))
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"primary": prim, "exploratory": expl, "evidence": ev}, f, indent=1, default=str)


if __name__ == "__main__":
    main()
