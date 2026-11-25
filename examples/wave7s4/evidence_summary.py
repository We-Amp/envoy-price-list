#!/usr/bin/env python3
"""Per-arm success evidence of a wave 7 S4 run directory, recomputed from the legs (not from the harness's own
verdicts): what proves that requests succeeded and that each arm ran the binary and the state its row assumes.

    python3 examples/wave7s4/evidence_summary.py RUN_DIR [--json OUT]

Per arm and shape, over the current legs (min to max unless stated): legs valid, evidence passing, responses in
the window, non-2xx (Envoy's and the client's), upstream and downstream 2xx per request, new upstream
connections per request, the tracing decision counters per request (not_traceable, random_sampling), spans
sent over the leg, export requests to the collector over the leg, spans the collector accepted per completed
request, upstream request bytes per request (the traceparent and tracestate headers add 84), runtime.num_keys,
the arm's saved admin /runtime, the tracer in the saved /config_dump, and the binary (sha256, version) the
run started for the arm."""
import gzip
import json
import os
import sys

H = "http.ingress_http."
TX = "cluster.origin.upstream_cx_tx_bytes_total"


def rng(v, f="%.4f"):
    v = [x for x in v if x is not None]
    if not v:
        return "-"
    lo, hi = min(v), max(v)
    return (f % lo) if abs(hi - lo) < 1e-12 else (f + " to " + f) % (lo, hi)


def config_values(dump, key):
    out = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == key:
                    out.append(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(dump)
    return out


def arm_config(rd, arm):
    p = os.path.join(rd, "config_dump", arm + ".json.gz")
    out = {}
    if os.path.exists(p):
        with gzip.open(p, "rt") as f:
            d = json.load(f)
        tr = config_values(d, "tracing")
        out = {"tracer": [t.get("provider", {}).get("name") for t in tr if isinstance(t, dict) and t.get("provider")],
               "random_sampling": [t.get("random_sampling") for t in tr if isinstance(t, dict) and "random_sampling" in t],
               "layered_runtime": config_values(d, "layered_runtime")}
    p = os.path.join(rd, "config_dump", arm + ".runtime.json")
    if os.path.exists(p):
        try:
            out["admin_runtime"] = json.load(open(p))
        except ValueError:
            out["admin_runtime"] = "unreadable"
    return out


def main(argv):
    rd = argv[0].rstrip("/")
    d = json.load(open(os.path.join(rd, "results.json")))
    md = d.get("metadata") or {}
    legs = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]
    sup = [m for m in d["legs"] if m.get("superseded")]
    out = {"run": os.path.basename(rd), "arms": {}, "arms_md5_unchanged": md.get("arms_md5_unchanged"), "superseded": [
        {"leg_id": m.get("leg_id"), "arm": m.get("arm"), "shape": m.get("shape"), "round": m.get("round"),
         "reasons": (m.get("verdict") or {}).get("reasons"), "evidence_failed": (m.get("evidence") or {}).get("failed")} for m in sup]}
    print("# %s: per-arm success evidence (current legs: %d; superseded: %d; binaries unchanged at the end: %s)\n" % (
        os.path.basename(rd), len(legs), len(sup), md.get("arms_md5_unchanged")))
    for m in sup:
        print("superseded: %s (%s/%s round %s): %s %s" % (m.get("leg_id"), m.get("shape"), m.get("arm"), m.get("round"),
                                                         (m.get("verdict") or {}).get("reasons"), (m.get("evidence") or {}).get("failed")))
    for sh in sorted({m["shape"] for m in legs}):
        for arm in sorted({m["arm"] for m in legs if m["shape"] == sh}):
            L = [m for m in legs if m["arm"] == arm and m["shape"] == sh]
            w = lambda m, k: (m.get("sut_stats_window") or {}).get(k)  # noqa: E731
            e = lambda m, k: (m.get("sut_stats_leg_end") or {}).get(k)  # noqa: E731
            per = lambda k: [w(m, k) / m["responses_raw"] if w(m, k) is not None and m.get("responses_raw") else None for m in L]  # noqa: E731
            done = lambda m: e(m, H + "downstream_rq_completed")  # noqa: E731
            cd = lambda m, k: (m.get("collector_delta") or {}).get(k)  # noqa: E731
            b = (md.get("arms") or {}).get(arm) or {}
            r = {
                "binary_sha256": b.get("sha256"), "binary_path": b.get("path"), "binary_version": b.get("version"),
                "legs": len(L), "valid": sum(1 for m in L if (m.get("verdict") or {}).get("valid")),
                "evidence_ok": sum(1 for m in L if (m.get("evidence") or {}).get("ok")),
                "evidence_items_per_leg": rng([len((m.get("evidence") or {}).get("items") or []) for m in L], "%d"),
                "responses_window": rng([m.get("responses_raw") for m in L], "%d"),
                "client_2xx_per_s": rng([m.get("client_rate_2xx") for m in L], "%.1f"),
                "non2xx_envoy": sum(m.get("sut_non2xx") or 0 for m in L),
                "non2xx_client": sum(sum((m.get("client_non2xx") or {}).values()) for m in L),
                "envoy_exit_codes": sorted({m.get("envoy_exit") for m in L}, key=str),
                "upstream_2xx_per_req": rng(per("cluster.origin.upstream_rq_2xx")),
                "downstream_2xx_per_req": rng(per(H + "downstream_rq_2xx")),
                "new_upstream_cx_per_req": rng(per("cluster.origin.upstream_cx_total"), "%.5f"),
                "not_traceable_per_req": rng(per(H + "tracing.not_traceable")),
                "sampled_share": rng(per(H + "tracing.random_sampling"), "%.5f"),
                "spans_sent_leg": rng([e(m, "tracing.opentelemetry.spans_sent") for m in L], "%d"),
                "collector_export_requests_leg": rng([e(m, "cluster.otel_collector.upstream_rq_total") for m in L], "%d"),
                "spans_accepted_per_completed": rng([cd(m, "accepted_spans") / done(m) if cd(m, "accepted_spans") is not None and done(m) else None for m in L], "%.5f"),
                "spans_accepted_leg": rng([cd(m, "accepted_spans") for m in L], "%d"),
                "spans_refused": sum(cd(m, "refused_spans") or 0 for m in L),
                "upstream_tx_bytes_per_req": rng(per(TX), "%.3f"),
                "runtime_num_keys": rng([e(m, "runtime.num_keys") for m in L], "%d"),
                "client_headroom_min": min([m.get("client_headroom") for m in L if m.get("client_headroom") is not None] or [None]),
                "worker_max_share": rng([m.get("envoy_worker_max_share") for m in L], "%.3f"),
                "envoy_cpus_run": rng([m.get("envoy_cpus_run") for m in L], "%.3f"),
                "side_services_busy_max": max([(sv or {}).get("busy_of_set") or 0 for m in L for sv in (m.get("side_services") or {}).values()] or [0]),
                "config": arm_config(rd, arm),
            }
            out["arms"]["%s/%s" % (sh, arm)] = r
            print("## %s / %s\n" % (sh, arm))
            for k, v in r.items():
                if k != "config":
                    print("- %s: %s" % (k, v))
            print("- config dump and admin /runtime: %s\n" % json.dumps(r["config"], sort_keys=True))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
