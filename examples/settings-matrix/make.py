#!/usr/bin/env python3
"""Write the settings-matrix configs: one experiment per row, each row one generic
setting against the baseline config, everything else fixed.

    python3 examples/settings-matrix/make.py [RATES_JSON]

RATES_JSON (optional) maps shape names to target rates from calibration. The
A/A (aa.json) uses the same base, shapes and rates as the rows that run on
plain HTTP/1.1, so its half-widths are the floor for those rows.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

BASE = {
    "machine_label": "2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, "
                     "default idle states; Envoy on 4 cores with their SMT siblings left idle",
    "workdir": "~/epl/runs/sm",
    "envoy": {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True},
    "cpus": {"sut": "0-3", "client": "20-31,60-71", "origin": "32-39,72-79"},
    "client": {"binary": "~/nighthawk/bazel-bin/nighthawk_client", "concurrency": 16,
               "connections_per_worker": 32, "warmup_s": 5, "duration_s": 25, "idle_strategy": "poll",
               "extra_args": ["--prefetch-connections", "--max-pending-requests", "1000",
                              "--experimental-h1-connection-reuse-strategy", "lru"]},
    "measure": {"lead_in_s": 2, "window_s": 20, "perf": "/usr/lib/linux-tools/6.8.0-149-generic/perf"},
    "idle": {"max_load1": 8.0, "max_busy_pct": 2.0},
    "origin": {"mode": "docker",
               "image": "nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11",
               "port": 8092, "workers": 8},
    "rounds": 12, "rounds_block": 6, "rounds_max": 24,
    "stop": {"target_half_width_pct": 1.5},
    "primary_metric": "cycles_total",
    "comparisons": "base",
    "floor_from": "~/epl/runs/sm/aa/results.json",
}

V140 = {"binary": "~/epl/bin/envoy-1.40.2",
        "source": "https://github.com/envoyproxy/envoy/releases/download/v1.40.2/envoy-1.40.2-linux-x86_64",
        "source_sha256": "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc"}

COLLECTOR = "otel/opentelemetry-collector:0.120.0@sha256:1daa4312b48312dbae2d543e67b77e897dd5d9c48e7651d1416cdb417026ad06"

# TLS 1.3 from the client (Nighthawk's own default tops out at TLS 1.2); no certificate check.
CLIENT_TLS = json.dumps({"name": "envoy.transport_sockets.tls", "typed_config": {
    "@type": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext",
    "common_tls_context": {"tls_params": {"tls_minimum_protocol_version": "TLSv1_2",
                                          "tls_maximum_protocol_version": "TLSv1_3"}}}}, separators=(",", ":"))
# Handshake-heavy leg: a client session cache big enough that "resumption on" resumes (the
# default of one key per cluster is used up at once by concurrent new connections).
CLIENT_TLS_HS = json.dumps({"name": "envoy.transport_sockets.tls", "typed_config": {
    "@type": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext",
    "max_session_keys": 1024,
    "common_tls_context": {"tls_params": {"tls_minimum_protocol_version": "TLSv1_2",
                                          "tls_maximum_protocol_version": "TLSv1_3"}}}}, separators=(",", ":"))
REQS_PER_CONN = 10  # handshake-heavy leg: a new connection every N requests


def shapes(rates):
    r = lambda n, d: int(rates.get(n, d))  # noqa: E731
    tls_args = ["--transport-socket", CLIENT_TLS]
    client_hdrs = []
    for i in range(16):
        client_hdrs += ["--request-header", "x-client-hdr-%02d:value-%02d-%s" % (i, i, "x" * 16)]
    return {
        "s": {"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": r("s", 5200)},
        "fh": {"name": "fh", "path": "/fh", "kind": "direct_headers", "body_bytes": 128,
               "request_headers_added": 57, "response_headers_added": 52, "rps": r("fh", 8000)},
        "m": {"name": "m", "path": "/m", "kind": "proxied", "body_bytes": 16384, "rps": r("m", 5440)},
        # the two-hop row: the second hop's load comes from the first hop's upstream pool
        "s-2hop": {"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": r("s", 5200),
                   "validity": {"hop2_worker_share_gate": False}},
        # TLS, keep-alive: per-request cost of TLS on long-lived connections
        "tls-ka": {"name": "tls-ka", "path": "/s", "kind": "proxied", "body_bytes": 4096,
                   "rps": r("tls-ka", 4800), "client_extra_args": tls_args,
                   # all 512 client connections handshake at once at start-up (before the window);
                   # requests wait for them, none is dropped
                   "validity": {"max_pending_total": None, "overflow_ignore": ["upstream_cx_overflow"]}},
        # TLS, handshake-heavy: a new connection every REQS_PER_CONN requests. Requests wait in
        # the client queue while their new connection is set up, so the pending-total gate
        # (meant for keep-alive legs) is off here; overflow must still be zero.
        "tls-hs": {"name": "tls-hs", "path": "/sh", "kind": "proxied", "body_bytes": 4096,
                   "rps": r("tls-hs", 2800),
                   "client_extra_args": ["--transport-socket", CLIENT_TLS_HS,
                                         "--max-requests-per-connection", str(REQS_PER_CONN)],
                   "validity": {"max_pending_total": None, "overflow_ignore": ["upstream_cx_overflow"]}},
        # HTTP/2, header-heavy: 16 client request headers on top of the route's 57 request and
        # 52 response headers
        "fh2": {"name": "fh2", "path": "/fh", "kind": "direct_headers", "body_bytes": 128,
                "request_headers_added": 57, "response_headers_added": 52, "rps": r("fh2", 8000),
                "client_extra_args": client_hdrs},
    }


def arm(name, settings=None, env=None):
    a = dict(V140, name=name)
    if settings:
        a["settings"] = settings
    if env:
        a["env"] = env
    return a


def configs(rates):
    S = shapes(rates)
    out = {}

    def row(fname, name, arms, shp, **kw):
        c = json.loads(json.dumps(BASE))
        c.update(name=name, base_arm=arms[0]["name"], arms=arms, shapes=[S[x] for x in shp])
        for k, v in kw.items():
            if isinstance(v, dict) and isinstance(c.get(k), dict):
                c[k] = dict(c[k], **v)
            else:
                c[k] = v
        out[fname] = c

    out["aa.json"] = dict(json.loads(json.dumps(BASE)), name="sm-aa", base_arm="A", expect="aa",
                          rounds_max=36, arms=[arm("A"), arm("A2")], shapes=[S["s"], S["fh"], S["m"]])
    for k in ("floor_from", "stop", "rounds_block", "primary_metric", "comparisons"):
        out["aa.json"].pop(k)  # harness defaults; aa.json is the exact config the A/A ran with
    full = {"resumption": False}
    row("01-tls-cert.json", "sm-tls-cert",
        [arm("rsa2048", {"tls": dict(full, cert="rsa2048")}),
         arm("ecdsa-p256", {"tls": dict(full, cert="ecdsa-p256")})], ["tls-ka", "tls-hs"])
    row("02-tls-resumption.json", "sm-tls-resumption",
        [arm("resumption-off", {"tls": {"cert": "rsa2048", "resumption": False}}),
         arm("resumption-on", {"tls": {"cert": "rsa2048"}})], ["tls-hs"])
    row("03-hpack.json", "sm-hpack",
        [arm("hpack-default"), arm("hpack-0", {"hpack_table_size": 0})], ["fh2"],
        envoy={"codec_type": "HTTP2"},
        client={"extra_args": ["--h2", "--prefetch-connections", "--max-pending-requests", "1000"]})
    row("04-tracing.json", "sm-tracing",
        [arm("no-tracer"), arm("sampling-0", {"tracing": {"sampling_pct": 0}}),
         arm("sampling-1", {"tracing": {"sampling_pct": 1}}),
         arm("sampling-100", {"tracing": {"sampling_pct": 100}})], ["s"],
        rounds=16, rounds_block=8, rounds_max=32, collector={"image": COLLECTOR, "port": 4317})
    row("05-access-log.json", "sm-access-log",
        [arm("log-off"), arm("log-text", {"access_log": {"format": "text"}}),
         arm("log-json", {"access_log": {"format": "json"}})], ["s"])
    row("06-ext-authz.json", "sm-ext-authz",
        [arm("authz-off"), arm("authz-http", {"ext_authz": True})], ["s"],
        origin=dict(BASE["origin"], authz_port=8093))
    row("07-retries.json", "sm-retries",
        [arm("no-retry-policy"), arm("retry-policy", {"retries": True})], ["s"])
    row("08-buffer-limit.json", "sm-buffer-limit",
        [arm("buffer-default"), arm("buffer-4k", {"buffer_limit_bytes": 4096})], ["m"])
    row("09-tcmalloc-percpu.json", "sm-tcmalloc-percpu",
        [arm("tcmalloc-default"), arm("rseq-off", env={"GLIBC_TUNABLES": "glibc.pthread.rseq=0"})], ["s", "fh"])
    row("10-two-hop.json", "sm-two-hop",
        [arm("one-hop"), arm("two-hop", {"two_hop": True})], ["s-2hop"],
        cpus=dict(BASE["cpus"], hop2="4-7"), primary_metric="cycles_total_per_hop")
    return out


def main():
    rates = {}
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            rates = json.load(f)
    for fn, c in configs(rates).items():
        with open(os.path.join(HERE, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
