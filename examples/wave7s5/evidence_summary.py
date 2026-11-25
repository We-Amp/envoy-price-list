#!/usr/bin/env python3
"""Per-arm, per-leg evidence of the wave 7 S5 run directories, recomputed from the legs (not from the harness's
own verdicts): what shows that each leg ran the binary and the guards its row assumes, that every byte and
message arrived, and that nothing was reset, timed out or overflowed.

    python3 examples/wave7s5/evidence_summary.py RUN_DIR [RUN_DIR ...] [--json OUT]

Per run, arm and shape over the current legs (min to max unless stated): legs valid and evidence passing; the
sha256 of the file each leg's Envoy ran (read in that leg) against the pin; both runtime guards as the admin
/runtime of each leg's process read them at its start and at its end (1 true, 0 false, -1 not set); responses
in the window (the origin's own count on the relay shape); the client's 2xx per second against the open-loop
target; bytes per request on the four sides; connections; every error counter (sum over the legs: the window's
deltas and the end-of-leg values); Envoy's exit codes; load figures. Legs the harness replaced are listed."""
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R, H, L, C = "tcp.relay.", "http.ingress_http.", "listener.127.0.0.1_10110.", "cluster.origin."
BYTES = {"relay": [("client to Envoy", R + "downstream_cx_rx_bytes_total"), ("Envoy to origin", C + "upstream_cx_tx_bytes_total"),
                   ("origin to Envoy", C + "upstream_cx_rx_bytes_total"), ("Envoy to client", R + "downstream_cx_tx_bytes_total")],
         "http": [("client to Envoy", H + "downstream_cx_rx_bytes_total"), ("Envoy to origin", C + "upstream_cx_tx_bytes_total"),
                  ("origin to Envoy", C + "upstream_cx_rx_bytes_total"), ("Envoy to client", H + "downstream_cx_tx_bytes_total")]}
WINDOW_ZERO = [C + "upstream_cx_total", C + "upstream_cx_destroy", C + "upstream_cx_destroy_remote", C + "upstream_cx_destroy_local",
               C + "upstream_cx_destroy_remote_with_active_rq", C + "upstream_cx_destroy_local_with_active_rq",
               C + "upstream_cx_connect_fail", C + "upstream_cx_connect_timeout", C + "upstream_cx_overflow",
               C + "upstream_cx_protocol_error", C + "upstream_rq_timeout", C + "upstream_rq_pending_overflow", C + "upstream_rq_retry",
               C + "upstream_rq_rx_reset", C + "upstream_rq_tx_reset", C + "upstream_flow_control_paused_reading_total",
               C + "upstream_flow_control_backed_up_total", L + "downstream_cx_destroy", L + "downstream_cx_total",
               L + "downstream_cx_overflow", L + "downstream_cx_overload_reject", R + "idle_timeout", R + "downstream_cx_no_route",
               R + "upstream_flush_total", R + "downstream_flow_control_paused_reading_total", H + "downstream_cx_destroy",
               H + "downstream_cx_destroy_remote", H + "downstream_cx_destroy_local", H + "downstream_cx_delayed_close_timeout",
               H + "downstream_cx_protocol_error", H + "downstream_rq_rx_reset", H + "downstream_rq_tx_reset", H + "downstream_rq_timeout",
               H + "downstream_rq_4xx", H + "downstream_rq_5xx", H + "downstream_flow_control_paused_reading_total"]
LEG_ZERO = [C + "upstream_cx_connect_fail", C + "upstream_cx_connect_timeout", C + "upstream_cx_overflow", C + "upstream_cx_protocol_error",
            C + "upstream_rq_timeout", C + "upstream_rq_rx_reset", C + "upstream_rq_tx_reset", L + "downstream_cx_overflow",
            L + "downstream_cx_overload_reject", R + "idle_timeout", R + "downstream_cx_no_route", H + "downstream_cx_delayed_close_timeout",
            H + "downstream_cx_protocol_error", H + "downstream_rq_rx_reset", H + "downstream_rq_tx_reset", H + "downstream_rq_timeout",
            H + "downstream_rq_4xx", H + "downstream_rq_5xx", "server.envoy_bug_failures", "server.debug_assertion_failures"]


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
        out = {"layered_runtime": config_values(d, "layered_runtime"), "enable_mptcp": config_values(d, "enable_mptcp"),
               "tcp_proxy_filters": sum(1 for v in config_values(d, "name") if v == "envoy.filters.network.tcp_proxy"),
               "http_connection_managers": sum(1 for v in config_values(d, "name") if v == "envoy.filters.network.http_connection_manager")}
    p = os.path.join(rd, "config_dump", arm + ".runtime.json")
    if os.path.exists(p):
        try:
            out["admin_runtime_first_start"] = json.load(open(p))
        except ValueError:
            out["admin_runtime_first_start"] = "unreadable"
    return out


def one(rd, out):
    d = json.load(open(os.path.join(rd, "results.json")))
    md = d.get("metadata") or {}
    with open(os.path.join(HERE, "bins.json")) as f:
        bins = json.load(f)
    legs = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]
    sup = [m for m in d["legs"] if m.get("superseded")]
    name = os.path.basename(rd)
    O = out[name] = {"arms": {}, "arms_md5_unchanged": md.get("arms_md5_unchanged"), "superseded": [
        {"leg_id": m.get("leg_id"), "arm": m.get("arm"), "shape": m.get("shape"), "round": m.get("round"),
         "reasons": (m.get("verdict") or {}).get("reasons"), "evidence_failed": (m.get("evidence") or {}).get("failed")} for m in sup]}
    print("# %s: per-arm evidence (current legs: %d; superseded: %d; binaries unchanged at the end: %s; kernel %s)\n" % (
        name, len(legs), len(sup), md.get("arms_md5_unchanged"), ((md.get("box") or {}).get("kernel") or (md.get("platform") or ""))))
    for m in sup:
        print("superseded: %s (%s/%s round %s): %s %s" % (m.get("leg_id"), m.get("shape"), m.get("arm"), m.get("round"),
                                                         (m.get("verdict") or {}).get("reasons"), (m.get("evidence") or {}).get("failed")))
    arms = d.get("experiment", {}).get("arms") or []
    build = {a["name"]: a.get("build") for a in arms}
    for sh in sorted({m["shape"] for m in legs}):
        for arm in [a["name"] for a in arms if any(m["arm"] == a["name"] and m["shape"] == sh for m in legs)]:
            LG = [m for m in legs if m["arm"] == arm and m["shape"] == sh]
            w = lambda m, k: (m.get("sut_stats_window") or {}).get(k)  # noqa: E731
            e = lambda m, k: (m.get("sut_stats_leg_end") or {}).get(k)  # noqa: E731
            per = lambda k: [w(m, k) / m["responses_raw"] if w(m, k) is not None and m.get("responses_raw") else None for m in LG]  # noqa: E731
            kind = "relay" if any(w(m, R + "downstream_cx_rx_bytes_total") is not None for m in LG) else "http"
            pin = (bins.get(build.get(arm)) or {}).get("source_sha256")
            shas = sorted({m.get("binary_sha256") for m in LG}, key=str)
            b = (md.get("arms") or {}).get(arm) or {}
            r = {
                "kind": kind, "legs": len(LG), "valid": sum(1 for m in LG if (m.get("verdict") or {}).get("valid")),
                "evidence_ok": sum(1 for m in LG if (m.get("evidence") or {}).get("ok")),
                "evidence_items_per_leg": rng([len((m.get("evidence") or {}).get("items") or []) for m in LG], "%d"),
                "binary_sha256_per_leg": shas, "binary_pin": pin, "binary_all_legs_equal_pin": shas == [pin],
                "binary_sha256_at_run_start": b.get("sha256"), "binary_version": b.get("version"),
                "guards_at_leg_start": sorted({json.dumps(m.get("runtime_start"), sort_keys=True) for m in LG}),
                "guards_at_leg_end": sorted({json.dumps(m.get("runtime_end"), sort_keys=True) for m in LG}),
                "runtime_num_keys_leg_end": rng([e(m, "runtime.num_keys") for m in LG], "%d"),
                "responses_window": rng([m.get("responses_raw") for m in LG], "%d"),
                "responses_from": sorted({str(m.get("responses_from")) for m in LG}),
                "target_rps": sorted({m.get("target_rps") for m in LG}),
                "client_2xx_per_s": rng([m.get("client_rate_2xx") for m in LG], "%.1f"),
                "open_loop_flag_in_every_leg": all("--open-loop" in (m.get("client_args") or []) for m in LG),
                "non2xx_envoy": sum(m.get("sut_non2xx") or 0 for m in LG),
                "non2xx_client": sum(sum((m.get("client_non2xx") or {}).values()) for m in LG),
                "client_overflow": sum(sum((m.get("client_overflow") or {}).values()) for m in LG),
                "client_pending_total_max": max([m.get("client_pending_total") or 0 for m in LG] or [0]),
                "envoy_exit_codes": sorted({m.get("envoy_exit") for m in LG}, key=str),
                "bytes_per_request": {what: rng(per(st), "%.3f") for what, st in BYTES[kind]},
                "upstream_2xx_per_req": rng(per(C + "upstream_rq_2xx")), "downstream_2xx_per_req": rng(per(H + "downstream_rq_2xx")),
                "window_counters_summed_over_legs": {k: sum(w(m, k) or 0 for m in LG) for k in WINDOW_ZERO if any(w(m, k) is not None for m in LG)},
                "leg_end_counters_summed_over_legs": {k: sum(e(m, k) or 0 for m in LG) for k in LEG_ZERO if any(e(m, k) is not None for m in LG)},
                "tcp_connections_to_origin_end_of_window": rng([(m.get("conn_upstream") or {}).get("conns") for m in LG], "%d"),
                "tcp_connections_from_client_end_of_window": rng([(m.get("conn_downstream") or {}).get("conns") for m in LG], "%d"),
                "client_headroom_min": min([m.get("client_headroom") for m in LG if m.get("client_headroom") is not None] or [None]),
                "worker_max_share": rng([m.get("envoy_worker_max_share") for m in LG], "%.3f"),
                "envoy_cpus_run": rng([m.get("envoy_cpus_run") for m in LG], "%.3f"),
                "foreign_cpus_on_envoy_cores_max": max([m.get("sut_foreign_cpus") or 0 for m in LG] or [0]),
                "perf_running_pct_min": min([m.get("perf_min_running_pct") for m in LG if m.get("perf_min_running_pct") is not None] or [None]),
                "side_services_busy_max": max([(sv or {}).get("busy_of_set") or 0 for m in LG for sv in (m.get("side_services") or {}).values()] or [0]),
                "config": arm_config(rd, arm),
            }
            r["window_counters_all_zero"] = not any(r["window_counters_summed_over_legs"].values())
            r["leg_end_counters_all_zero"] = not any(r["leg_end_counters_summed_over_legs"].values())
            O["arms"]["%s/%s" % (sh, arm)] = r
            print("## %s / %s / %s\n" % (name, sh, arm))
            for k, v in r.items():
                if k != "config":
                    print("- %s: %s" % (k, json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v))
            print("- config dump and admin /runtime at the arm's first start: %s\n" % json.dumps(r["config"], sort_keys=True))


def main(argv):
    out = {}
    dirs = [a for i, a in enumerate(argv) if a != "--json" and (i == 0 or argv[i - 1] != "--json")]
    for rd in dirs:
        if os.path.exists(os.path.join(rd, "results.json")):
            one(rd.rstrip("/"), out)
        else:
            print("# %s: no results.json\n" % rd)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
