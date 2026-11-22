"""Nighthawk client arguments and output parsing."""

import json

# Counters that mean the client did not send what it was asked to send.
OVERFLOW_COUNTERS = (
    "benchmark.pool_overflow",
    "benchmark.pool_connection_failure",
    "upstream_rq_pending_overflow",
    "upstream_cx_overflow",
    "upstream_cx_pool_overflow",
    "benchmark.stream_resets",
    # a connect that failed or timed out (churn shapes: an exhausted port range or a full
    # conntrack table shows here first); zero on every clean leg of any shape
    "upstream_cx_connect_fail",
    "upstream_cx_connect_timeout",
)
NON2XX_COUNTERS = ("benchmark.http_1xx", "benchmark.http_3xx", "benchmark.http_4xx",
                   "benchmark.http_5xx", "benchmark.http_xxx")


def multi_target_args(scheme, port, path, mt):
    """The target arguments that replace the URI when a leg spreads its connections over several
    loopback destination addresses: one --multi-target-endpoint per address (Nighthawk's one
    cluster per client worker, round robin over the hosts), the path, and HTTPS for TLS arms.
    mt = {"count": N, "base": "127.0.0.1"}: addresses base, base+1, ... (all inside 127/8)."""
    import ipaddress
    n = int(mt.get("count", 0))
    if n < 1:
        raise ValueError("multi_target.count must be at least 1")
    first = ipaddress.IPv4Address(mt.get("base", "127.0.0.1"))
    last = first + (n - 1)
    lo = ipaddress.IPv4Network("127.0.0.0/8")
    if first not in lo or last not in lo:
        raise ValueError("multi_target addresses must stay inside 127.0.0.0/8")
    args = []
    for i in range(n):
        args += ["--multi-target-endpoint", "%s:%d" % (first + i, int(port))]
    args += ["--multi-target-path", path]
    if scheme == "https":
        args.append("--multi-target-use-https")
    return args


def client_args(client_cfg, total_rps, url, duration_s, json_out, shape_extra=None, base_extra=None):
    """`url` is a URI string, or a list of target arguments (multi_target_args) that replaces it."""
    conc = int(client_cfg.get("concurrency", 4))
    per_worker = total_rps / conc
    if abs(per_worker - round(per_worker)) > 1e-9:
        raise ValueError("rps %s not divisible by client concurrency %d" % (total_rps, conc))
    args = [
        "--rps", str(int(round(per_worker))),
        "--connections", str(int(client_cfg.get("connections_per_worker", 16))),
        "--concurrency", str(conc),
        "--duration", str(int(duration_s)),
        "--sequencer-idle-strategy", client_cfg.get("idle_strategy", "poll"),
    ]
    if client_cfg.get("open_loop", True):
        args.append("--open-loop")
    if json_out:
        args += ["--output-format", "json"]
    # a shape may replace the experiment's client arguments (base_extra), e.g. to drop
    # prefetch and LRU reuse so that connection churn is spread out in time
    args += list(client_cfg.get("extra_args", []) if base_extra is None else base_extra)
    args += list(shape_extra or [])  # per-shape client settings (TLS parameters, connection churn, h2)
    if isinstance(url, (list, tuple)):
        args += list(url)
    else:
        args.append(url)
    return args


def _dur_s(txt):
    return float(str(txt).rstrip("s"))


def parse_output(path):
    """Extract counters, rate and latency from a Nighthawk JSON file."""
    with open(path) as f:
        d = json.load(f)
    g = [r for r in d["results"] if r["name"] == "global"][0]
    counters = {c["name"]: int(c["value"]) for c in g.get("counters", [])}
    duration = _dur_s(g.get("execution_duration", "0s"))
    lat = {}
    count = 0
    mean_us = max_us = None
    maxes = {}
    for st in g.get("statistics", []):
        if st["id"] in ("benchmark_http_client.queue_to_connect", "sequencer.callback") and "max" in st:
            maxes[st["id"]] = _dur_s(st["max"]) * 1e6
        if st["id"] != "benchmark_http_client.request_to_response":
            continue
        count = int(st.get("count", 0))
        if "mean" in st:
            mean_us = _dur_s(st["mean"]) * 1e6
        if "max" in st:
            max_us = _dur_s(st["max"]) * 1e6
        for pc in st.get("percentiles", []):
            p = float(pc["percentile"])
            for t in (0.5, 0.9, 0.99, 0.999):
                if t not in lat and p >= t:
                    lat[t] = _dur_s(pc["duration"]) * 1e6
    worker_max = []
    for r in d["results"]:
        if r["name"] == "global":
            continue
        for st in r.get("statistics", []):
            if st["id"] == "benchmark_http_client.request_to_response" and "max" in st:
                worker_max.append(round(_dur_s(st["max"]) * 1e6, 1))
    v = d.get("version", {}).get("version", {})
    return {
        "pending_total": counters.get("upstream_rq_pending_total"),
        "cx_total": counters.get("upstream_cx_total"),
        "workers": len(worker_max) or None,
        "worker_r2r_max_us": worker_max,
        "queue_to_connect_max_us": maxes.get("benchmark_http_client.queue_to_connect"),
        "callback_max_us": maxes.get("sequencer.callback"),
        "counters": counters,
        "execution_duration_s": duration,
        "responses_2xx": counters.get("benchmark.http_2xx", 0),
        "rate_2xx": counters.get("benchmark.http_2xx", 0) / duration if duration else 0.0,
        "overflow": {k: counters[k] for k in OVERFLOW_COUNTERS if counters.get(k)},
        "non2xx": {k: counters[k] for k in NON2XX_COUNTERS if counters.get(k)},
        "latency_us": {"p50": lat.get(0.5), "p90": lat.get(0.9), "p99": lat.get(0.99),
                       "p999": lat.get(0.999), "mean": mean_us, "max": max_us, "count": count},
        "client_version": "%s.%s.%s" % (v.get("major_number"), v.get("minor_number"), v.get("patch")),
    }
