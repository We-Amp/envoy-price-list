#!/usr/bin/env python3
"""Per-arm success evidence of a wave 7 S3 run directory, recomputed from the legs (not from the harness's own
verdicts): what proves that requests succeeded and that each arm ran in the state its row assumes.

    python3 examples/wave7s3/evidence_summary.py RUN_DIR [--json OUT]

Per arm and shape, over the current legs (min to max unless stated): legs valid, evidence passing, responses
in the window, client 2xx per second, non-2xx, Envoy's upstream 2xx per request, downstream 2xx per request,
new upstream connections per request, access-log lines per completed request, sampled share, spans accepted
per completed request, metric points accepted, statsd datagrams per request, box-wide UDP datagrams sent per
request, compressor / JWT / rate-limit counters per request, retries, the stat count of the arm's saved
/stats, the HTTP filter chain and the timer settings read from the arm's saved /config_dump, client headroom,
busiest worker share, Envoy busy."""
import gzip
import json
import os
import sys

H = "http.ingress_http."
COMP = H + "compressor.epl.gzip."
RL = "http_local_rate_limiter.http_local_rate_limit."


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
    if not os.path.exists(p):
        return {}
    with gzip.open(p, "rt") as f:
        d = json.load(f)
    hf = config_values(d, "http_filters")
    chain = [(f["name"].rsplit(".", 1)[-1] + (" (disabled)" if f.get("disabled") else "")) for f in hf[0]] if hf else []
    return {"http_filters": chain, "stream_idle_timeout": config_values(d, "stream_idle_timeout"),
            "common_http_protocol_options": config_values(d, "common_http_protocol_options"),
            "route_timeout": config_values(d, "timeout"), "retry_policy": bool(config_values(d, "retry_policy")),
            "stats_sinks": [s.get("name") for x in config_values(d, "stats_sinks") for s in x],
            "access_log_json": bool(config_values(d, "json_format")),
            "tracing_sampling": [x.get("value") for x in config_values(d, "random_sampling")],
            "jwt_cache": bool(config_values(d, "jwt_cache_config"))}


def stat_count(rd, arm):
    p = os.path.join(rd, "stats", arm + ".txt.gz")
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt", errors="replace") as f:
        return sum(1 for line in f if ": " in line)


def main(argv):
    rd = argv[0].rstrip("/")
    d = json.load(open(os.path.join(rd, "results.json")))
    legs = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]
    sup = [m for m in d["legs"] if m.get("superseded")]
    out = {"run": os.path.basename(rd), "arms": {}, "superseded": [
        {"leg_id": m.get("leg_id"), "arm": m.get("arm"), "shape": m.get("shape"), "round": m.get("round"),
         "reasons": (m.get("verdict") or {}).get("reasons"), "evidence_failed": (m.get("evidence") or {}).get("failed")} for m in sup]}
    print("# %s: per-arm success evidence (current legs: %d; superseded: %d)\n" % (os.path.basename(rd), len(legs), len(sup)))
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
            r = {
                "legs": len(L), "valid": sum(1 for m in L if (m.get("verdict") or {}).get("valid")),
                "evidence_ok": sum(1 for m in L if (m.get("evidence") or {}).get("ok")),
                "evidence_items_per_leg": rng([len((m.get("evidence") or {}).get("items") or []) for m in L], "%d"),
                "responses_window": rng([m.get("responses_raw") for m in L], "%d"),
                "client_2xx_per_s": rng([m.get("client_rate_2xx") for m in L], "%.1f"),
                "non2xx": sum(m.get("non2xx") or 0 for m in L),
                "upstream_2xx_per_req": rng(per("cluster.origin.upstream_rq_2xx")),
                "downstream_2xx_per_req": rng(per(H + "downstream_rq_2xx")),
                "new_upstream_cx_per_req": rng(per("cluster.origin.upstream_cx_total"), "%.5f"),
                "retries": sum(w(m, "cluster.origin.upstream_rq_retry") or 0 for m in L),
                "access_log_lines_per_completed": rng([m["access_log_lines"] / done(m) if m.get("access_log_lines") is not None and done(m) else None for m in L]),
                "access_log_bytes_per_line": rng([m.get("access_log_bytes_per_line") for m in L], "%.1f"),
                "sampled_share": rng(per(H + "tracing.random_sampling"), "%.5f"),
                "spans_accepted_per_completed": rng([cd(m, "accepted_spans") / done(m) if cd(m, "accepted_spans") is not None and done(m) else None for m in L], "%.5f"),
                "spans_refused": sum(cd(m, "refused_spans") or 0 for m in L),
                "metric_points_accepted": rng([cd(m, "accepted_metric_points") for m in L], "%d"),
                "statsd_datagrams_per_req": rng([(m.get("udp") or {}).get("datagrams_per_request") for m in L]),
                "statsd_dropped": sum((m.get("udp") or {}).get("dropped") or 0 for m in L),
                "udp_out_per_req_boxwide": rng([((m.get("kernel_net") or {}).get("d") or {}).get("UdpOutDatagrams") / m["responses_raw"]
                                                if ((m.get("kernel_net") or {}).get("d") or {}).get("UdpOutDatagrams") is not None and m.get("responses_raw") else None for m in L], "%.5f"),
                "compressor_not_compressed_per_req": rng(per(COMP + "response.not_compressed")),
                "compressor_compressed": sum(w(m, COMP + "response.compressed") or 0 for m in L),
                "compressor_no_accept_header": sum(w(m, COMP + "no_accept_header") or 0 for m in L),
                "jwt_allowed_per_req": rng(per(H + "jwt_authn.allowed")),
                "jwt_cache_hit_per_req": rng(per(H + "jwt_authn.jwt_cache_hit")),
                "jwt_denied": sum(w(m, H + "jwt_authn.denied") or 0 for m in L),
                "ratelimit_ok_per_req": rng(per(RL + "ok")),
                "ratelimit_limited": sum(w(m, RL + "rate_limited") or 0 for m in L),
                "inert_action_counters_sum": sum(v for m in L for k, v in (m.get("sut_stats_leg_end") or {}).items()
                                                 if any(x in k for x in ("fault.aborts", "fault.delays", "rbac.denied", "csrf.request_invalid",
                                                                         "cors.origin_", "health_check.request_total", "http_bandwidth_limit.request_enforced",
                                                                         "http_bandwidth_limit.response_enforced"))),
                "client_headroom_min": min([m.get("client_headroom") for m in L if m.get("client_headroom") is not None] or [None]),
                "worker_max_share": rng([m.get("envoy_worker_max_share") for m in L], "%.3f"),
                "envoy_cpus_run": rng([m.get("envoy_cpus_run") for m in L], "%.3f"),
                "side_services_busy_max": max([(sv or {}).get("busy_of_set") or 0 for m in L for sv in (m.get("side_services") or {}).values()] or [0]),
                "stats_in_saved_snapshot": stat_count(rd, arm), "config": arm_config(rd, arm),
            }
            out["arms"]["%s/%s" % (sh, arm)] = r
            print("## %s / %s\n" % (sh, arm))
            for k, v in r.items():
                if k != "config":
                    print("- %s: %s" % (k, v))
            print("- config dump: %s\n" % json.dumps(r["config"], sort_keys=True))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
