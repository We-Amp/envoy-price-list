"""Generate the Envoy bootstrap and the origin content for a set of shapes.

The bootstrap only uses fields that have been stable across Envoy releases for
years (v3 API, static listener, HTTP connection manager, router, STATIC
cluster). It deliberately omits fields later releases deprecated, such as the
admin `access_log_path` and the header `append` boolean, so one file works
from old releases to current ones. `envoy --mode validate` checks it per arm.

Settings: an arm's `settings` are merged into the experiment's `envoy` section
before its bootstrap is generated, so each arm can differ from the baseline in
exactly one generic setting (see `SETTINGS`). Every setting defaults to off,
which is the baseline config.

Shape kinds:
  proxied         GET <path> proxied to the origin, which serves body_bytes;
                  optionally with N request and M response headers added by
                  the route (request_headers_added, response_headers_added),
                  so the added request headers are encoded upstream.
  direct_headers  direct_response of body_bytes, with N request headers and
                  M response headers added by the route (header-map work
                  without an upstream).
  routes          a given route table: `route_table.routes` (a list of Envoy
                  v3 Route objects, used as they are, in order) and optionally
                  `route_table.vhost` (virtual-host fields such as
                  response_headers_to_add). The request goes to `path`, so
                  where it matches in the table is set by the table. Used to
                  measure route matching and header work on a fixed, recorded
                  table instead of a generated one.
"""

import copy
import json
import os

HCM = "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager"
ROUTER = "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"
DTLS = "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.DownstreamTlsContext"
EXT_AUTHZ = "type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz"
EXT_PROC = "type.googleapis.com/envoy.extensions.filters.http.ext_proc.v3.ExternalProcessor"
GRPC_CLIENTS = ("envoy_grpc", "google_grpc")
# ext_proc processing modes an arm may name: the filter's defaults (request and response headers
# sent, bodies and trailers not), or request headers only
EXT_PROC_MODES = {"default": None,
                  "request_headers": {"request_header_mode": "SEND", "response_header_mode": "SKIP"}}
OTEL = "type.googleapis.com/envoy.config.trace.v3.OpenTelemetryConfig"
FILE_LOG = "type.googleapis.com/envoy.extensions.access_loggers.file.v3.FileAccessLog"
STATS_LOG = "type.googleapis.com/envoy.extensions.access_loggers.stats.v3.Config"
UPSTREAM_HTTP = "type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions"
JWT_AUTHN = "type.googleapis.com/envoy.extensions.filters.http.jwt_authn.v3.JwtAuthentication"
LOCAL_RL = "type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit"
COMPRESSOR = "type.googleapis.com/envoy.extensions.filters.http.compressor.v3.Compressor"
LUA = "type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua"
WASM = "type.googleapis.com/envoy.extensions.filters.http.wasm.v3.Wasm"

# Compressor libraries with every field at the filter's documented default, written out so
# the bootstrap states what ran: (extension name, type URL, defaults).
COMPRESSOR_LIBS = {
    "gzip": ("envoy.compression.gzip.compressor",
             "type.googleapis.com/envoy.extensions.compression.gzip.compressor.v3.Gzip",
             {"memory_level": 5, "compression_level": "DEFAULT_COMPRESSION",
              "compression_strategy": "DEFAULT_STRATEGY", "window_bits": 12, "chunk_size": 4096}),
    "brotli": ("envoy.compression.brotli.compressor",
               "type.googleapis.com/envoy.extensions.compression.brotli.compressor.v3.Brotli",
               {"quality": 3, "encoder_mode": "DEFAULT", "window_bits": 18, "input_block_bits": 24,
                "chunk_size": 4096, "disable_literal_context_modeling": False}),
    "zstd": ("envoy.compression.zstd.compressor",
             "type.googleapis.com/envoy.extensions.compression.zstd.compressor.v3.Zstd",
             {"compression_level": 3, "enable_checksum": False, "strategy": "DEFAULT", "chunk_size": 4096}),
}
# the response direction at its defaults (no request direction: requests are not compressed)
COMPRESSOR_RESPONSE = {"common_config": {"min_content_length": 30}, "disable_on_etag_header": False,
                       "remove_accept_encoding_header": False}
WASM_RUNTIMES = ("envoy.wasm.runtime.v8",)
STATSD = "type.googleapis.com/envoy.config.metrics.v3.StatsdSink"
DOG_STATSD = "type.googleapis.com/envoy.config.metrics.v3.DogStatsdSink"
OTLP_SINK = "type.googleapis.com/envoy.extensions.stat_sinks.open_telemetry.v3.SinkConfig"
# Stats-row cluster generator: K extra static clusters to the origin, selected per request by
# a header on one route. Names look like service names (45 to 75 characters as full stat
# names); `.test` is a reserved name.
ORIGIN_STATUS_PATH = "/epl-status"  # nginx stub_status on the origin (responses counted there)
STATS_CLUSTER_HEADER = "x-epl-cluster"
STATS_PRIME_PATH = "/epl-prime"
STATS_WORDS = ["accounts", "billing", "catalog", "checkout", "delivery", "directory", "events", "feedback",
               "gateway", "identity", "inventory", "ledger", "loyalty", "media", "messaging", "metrics",
               "notifications", "orders", "payments", "pricing", "profile", "ratings", "recommend", "refunds",
               "reporting", "returns", "search", "sessions", "shipping", "storage", "telemetry", "wallet"]

# The stats access logger of the dose run: K counters, each incremented by 1 per request, in
# their own scope, with one tag whose value is a command operator. The tag value decides how
# many counter objects exist: the listener port is the same for every request (one object per
# counter, shared by all workers); the client's port is one value per downstream connection
# (one object per counter and connection, and a connection belongs to one worker). Both values
# are five digits here, so the flat names have the same length: dose.c000.port.<port>.
STATS_LOG_SCOPE = "dose"
STATS_LOG_TAG = "port"
STATS_LOG_TAG_VALUES = ("%DOWNSTREAM_LOCAL_PORT%", "%DOWNSTREAM_REMOTE_PORT%")
STATS_LOG_MAX_COUNTERS = 1024

# Settings an arm may change, with what each one does. All are generic Envoy
# settings; none is off by default in the sense of costing work.
SETTINGS = {
    "tls": "TLS on the listener: {cert: rsa2048|ecdsa-p256, resumption: true (Envoy default) | false "
           "(stateless and stateful session resumption disabled), groups: [X25519MLKEM768|X25519|P-256, ...] "
           "(tls_params.ecdh_curves; unset = Envoy's default X25519MLKEM768:X25519:P-256)}",
    "hpack_table_size": "HTTP/2 HPACK dynamic table size in bytes (http2_protocol_options); unset = default",
    "tracing": "OpenTelemetry tracer over gRPC to the local collector: {sampling_pct: 0..100}",
    "access_log": "file access log: {format: text (Envoy's default format) | json (the same fields)}; the "
                  "harness sets the path",
    "ext_authz": "ext_authz filter against the local allow service in the origin container: true or \"http\" "
                 "(HTTP service, authz_port) | \"grpc\" (gRPC service over h2c, authz_grpc_port)",
    "grpc_client": "the gRPC client of the side-service filters (ext_authz \"grpc\", ext_proc): envoy_grpc "
                   "(the default: Envoy's own client over an HTTP/2 cluster) | google_grpc (the gRPC C++ client, "
                   "target 127.0.0.1:<port>, insecure channel, stat_prefix = the filter's name)",
    "ext_proc": "ext_proc filter before the router against the harness's ext_proc test service (origin."
                "ext_proc_port), failure_mode_allow false, every other field at its default: {mode: default "
                "(request and response headers sent: two messages per request on one stream) | request_headers "
                "(request headers only), observability_mode: true (optional)}",
    "xds": "routes, clusters and an optional EDS cluster from watched files (epl/xds.py): {routes: filler routes, "
           "clusters: filler clusters, eds_endpoints: endpoints of the filler EDS cluster (0 = none)}; the origin "
           "cluster comes by CDS; the harness sets the directory",
    "xds_update": "updates during the leg (no bootstrap change): {kind: rds | rds_same | cds | cds_same | "
                  "cds_active | eds, rate_hz}",
    "retries": "retry policy on proxied routes (retry_on 5xx,reset,connect-failure; 2 retries); none triggers",
    "buffer_limit_bytes": "per_connection_buffer_limit_bytes on the listener and the origin cluster",
    "two_hop": "client -> this Envoy -> a second Envoy (cpus.hop2, hop2 ports, baseline config) -> origin",
    "hop2_settings": "settings for the second Envoy of a two-hop arm (default: none, the baseline config)",
    "upstream_pool_per_downstream": "connection_pool_per_downstream_connection on the origin cluster: one "
                                    "upstream connection pool per downstream connection",
    "exact_balance": "connection_balance_config exact_balance on the listener (true = the harness default; "
                     "false = the kernel's reuse-port placement)",
    "downstream_keepalive": "keep-alive limits on the listener's HTTP connections (HCM "
                            "common_http_protocol_options): {idle_timeout_s, max_requests}",
    "jwt_authn": "JWT authentication filter with a local JWKS (no fetch), every route requires the one "
                 "provider: {jwks: JWKS JSON text, issuer, audience, cache: false (default, every token "
                 "verified) | true (jwt_cache_config, verified tokens cached)}; the token is forwarded upstream",
    "local_ratelimit": "local rate-limit filter, one token bucket shared by the workers, enabled and enforced "
                       "on every request: {tokens_per_s} (set far above the test rate, so nothing is rejected)",
    "idle_timers_off": "true: the stream idle timeout (HCM stream_idle_timeout, default 5 min) and the downstream "
                       "connection idle timeout (HCM common_http_protocol_options.idle_timeout, default 1 h) "
                       "both set to 0s, which disables them",
    "compressor": "one compressor filter before the router, response direction only, every library field "
                  "written out at its default: {library: gzip | brotli | zstd, <library field>: value ...}; "
                  "stats under compressor.epl.<library>.",
    "lua": "Lua filter before the router with an inline script: {inline: source}",
    "wasm": "Wasm filter before the router, one VM per worker, module from a local file, fail closed: "
            "{file: path (relative to the harness), sha256: hex, runtime: envoy.wasm.runtime.v8}",
    "stats_clusters": "the stats-row generator: {count, seed, idle_timeout_s (default 1)}: that many extra "
                      "static clusters to the origin, seeded service-like names, one route on "
                      "/epl-prime that picks the cluster by the x-epl-cluster header",
    "stats_flush": "stats flush: {interval_s: seconds} (stats_flush_interval) | {on_admin: true} "
                   "(stats_flush_on_admin: no timer, every admin stats read flushes)",
    "stats_sink": "one stats sink: {kind: statsd | dog_statsd, prefix, max_bytes_per_datagram (dog_statsd)} "
                  "to the harness's UDP discard sink, or {kind: otlp, max_data_points_per_request} over "
                  "envoy_grpc to the collector; the harness sets ports",
    "listener_address": "the listener's address: 127.0.0.1 (the harness default: every accepted connection's local "
                        "address is the listener's one address object) | 0.0.0.0 (the wildcard address: Envoy reads "
                        "each accepted connection's local address into its own object); the client targets loopback",
    "tcp_defer_accept_s": "N: TCP_DEFER_ACCEPT on the listen socket(s) (listener socket_options), N seconds",
    "reuse_port": "false: enable_reuse_port false, one listen socket shared by every worker (default: one socket per "
                  "worker with SO_REUSEPORT)",
    "listener_fanout": "N: the listener also listens on the next N-1 loopback addresses after listener_address "
                       "(additional_addresses: one listener, one filter chain, one TLS context), for clients "
                       "that spread connections over several destinations (multi_target)",
    "stats_access_log": "stats access logger on the HCM (envoy.access_loggers.stats): {counters: K, tag: "
                        "%DOWNSTREAM_LOCAL_PORT% (one counter object per counter) | %DOWNSTREAM_REMOTE_PORT% (one "
                        "per counter and downstream connection)}: K counters dose.c000.. each incremented by 1 "
                        "per request, tag `port`; no scope limit, no eviction. hot: true lists the one counter "
                        "dose.c000 K times instead (the logger keeps every entry and looks up and adds once per "
                        "entry): the same K lookups and adds per request, all on one counter object",
    "stats_reject_all": "true: stats_config.stats_matcher.reject_all (every stat becomes a null object)",
    "upstream_http": "HTTP/1 pool limits on the origin cluster (HttpProtocolOptions "
                     "common_http_protocol_options): {idle_timeout_s, max_requests, max_connection_duration_s}",
    "upstream_http2": "true: the origin cluster speaks HTTP/2 (explicit http2_protocol_options; cleartext "
                      "with prior knowledge, or over upstream_tls with ALPN h2)",
    "upstream_tls": "TLS on the origin cluster (UpstreamTlsContext): {ca: cert kind the peer is verified "
                    "against, sni, san (exact DNS SAN match, optional), cert: client cert kind (mTLS, optional), "
                    "alpn: [protocols] (optional), max_session_keys (optional)}",
    "origin_server": "which origin server the origin cluster targets: plain (the default, HTTP/1.1) | h2c "
                     "(origin.h2c_port) | tls (origin.tls_port, TLS with ALPN h2 and http/1.1); ignored by "
                     "the first hop of a two-hop arm",
    "runtime": "a layered_runtime static layer: {key: value} (e.g. envoy.reloadable_features.http2_use_oghttp2)",
    "grpc_stats": "grpc_stats filter before the router: {stats_for_all_methods: bool}",
}

# The oghttp2 switch of v1.40.2 (runtime_features.cc:326, default false)
OGHTTP2_KEY = "envoy.reloadable_features.http2_use_oghttp2"
UTLS = "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext"
GRPC_STATS = "type.googleapis.com/envoy.extensions.filters.http.grpc_stats.v3.FilterConfig"

# Envoy's default access-log fields, as JSON with the same content.
JSON_LOG_FIELDS = {
    "start_time": "%START_TIME%", "method": "%REQ(:METHOD)%",
    "path": "%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%", "protocol": "%PROTOCOL%",
    "response_code": "%RESPONSE_CODE%", "response_flags": "%RESPONSE_FLAGS%",
    "bytes_received": "%BYTES_RECEIVED%", "bytes_sent": "%BYTES_SENT%", "duration": "%DURATION%",
    "upstream_service_time": "%RESP(X-ENVOY-UPSTREAM-SERVICE-TIME)%",
    "x_forwarded_for": "%REQ(X-FORWARDED-FOR)%", "user_agent": "%REQ(USER-AGENT)%",
    "request_id": "%REQ(X-REQUEST-ID)%", "authority": "%REQ(:AUTHORITY)%", "upstream_host": "%UPSTREAM_HOST%",
}


def _headers(prefix, n, value_len=24):
    out = []
    for i in range(n):
        v = ("%s-value-%02d-" % (prefix, i))
        v = (v + "x" * value_len)[:value_len]
        out.append({"header": {"key": "x-%s-%02d" % (prefix, i), "value": v}})
    return out


def route_for(shape, cluster="origin", envoy_cfg=None):
    kind = shape["kind"]
    r = {"match": {"path": shape["path"]}}
    if kind == "proxied":
        r["route"] = {"cluster": cluster}
        if (envoy_cfg or {}).get("retries"):
            r["route"]["retry_policy"] = {"retry_on": "5xx,reset,connect-failure", "num_retries": 2}
        if shape.get("request_headers_added"):
            r["request_headers_to_add"] = _headers("req", int(shape["request_headers_added"]))
        if shape.get("response_headers_added"):
            r["response_headers_to_add"] = _headers("rsp", int(shape["response_headers_added"]))
    elif kind == "direct_headers":
        r["direct_response"] = {"status": 200,
                                "body": {"inline_string": "a" * int(shape.get("body_bytes", 128))}}
        if shape.get("request_headers_added"):
            r["request_headers_to_add"] = _headers("req", int(shape["request_headers_added"]))
        if shape.get("response_headers_added"):
            r["response_headers_to_add"] = _headers("rsp", int(shape["response_headers_added"]))
    else:
        raise ValueError("unknown shape kind %r" % kind)
    return r


# virtual-host fields a `routes` shape may set; name, domains and routes stay the harness's
VHOST_FIELDS = ("request_headers_to_add", "response_headers_to_add", "request_headers_to_remove",
                "response_headers_to_remove")


def shape_routes(shape, envoy_cfg=None):
    """The routes a shape contributes, in order (an idle shape: none)."""
    if shape["kind"] == "idle":
        return []
    if shape["kind"] == "routes":
        rt = shape.get("route_table") or {}
        rs = rt.get("routes")
        if not isinstance(rs, list) or not rs:
            raise ValueError("shape %s: route_table.routes must be a non-empty list" % shape.get("name"))
        return copy.deepcopy(rs)
    return [route_for(shape, envoy_cfg=envoy_cfg)]


def routes(shapes, envoy_cfg=None):
    """One route (or route table) per path: shapes that share a path (the same request at
    two rates) share its routes; they must then agree on everything the routes are built from."""
    out, seen = [], {}
    for s in shapes:
        r = shape_routes(s, envoy_cfg)
        if s["path"] in seen:
            if seen[s["path"]] != r:
                raise ValueError("shapes on path %s differ in their route" % s["path"])
            continue
        seen[s["path"]] = r
        out.extend(r)
    return out


def vhost_fields(shapes):
    """Virtual-host fields from the `routes` shapes; shapes that set one must agree on it."""
    out = {}
    for s in shapes:
        if s["kind"] != "routes":
            continue
        vh = (s.get("route_table") or {}).get("vhost") or {}
        bad = sorted(set(vh) - set(VHOST_FIELDS))
        if bad:
            raise ValueError("shape %s: route_table.vhost cannot set %s (allowed: %s)" % (
                s.get("name"), bad, list(VHOST_FIELDS)))
        for k, v in vh.items():
            if k in out and out[k] != v:
                raise ValueError("shapes differ in the virtual-host field %s" % k)
            out[k] = copy.deepcopy(v)
    return out


def jwt_filter(jw):
    for k in ("jwks", "issuer", "audience"):
        if not jw.get(k):
            raise ValueError("jwt_authn needs %s" % k)
    bad = sorted(set(jw) - {"jwks", "issuer", "audience", "cache"})
    if bad:
        raise ValueError("jwt_authn: unknown keys %s" % bad)
    prov = {"issuer": jw["issuer"], "audiences": [jw["audience"]], "local_jwks": {"inline_string": jw["jwks"]},
            # keep the Authorization header on the upstream request, as the baseline sends it
            "forward": True}
    if jw.get("cache"):
        prov["jwt_cache_config"] = {"jwt_cache_size": 100}
    return {"name": "envoy.filters.http.jwt_authn", "typed_config": {
        "@type": JWT_AUTHN, "providers": {"epl": prov},
        "rules": [{"match": {"prefix": "/"}, "requires": {"provider_name": "epl"}}]}}


def local_ratelimit_filter(rl):
    n = int(rl["tokens_per_s"])
    if n < 1:
        raise ValueError("local_ratelimit.tokens_per_s must be positive")
    pct = {"numerator": 100, "denominator": "HUNDRED"}
    return {"name": "envoy.filters.http.local_ratelimit", "typed_config": {
        "@type": LOCAL_RL, "stat_prefix": "http_local_rate_limiter",
        "token_bucket": {"max_tokens": n, "tokens_per_fill": n, "fill_interval": "1s"},
        "filter_enabled": {"runtime_key": "local_rate_limit_enabled", "default_value": pct},
        "filter_enforced": {"runtime_key": "local_rate_limit_enforced", "default_value": pct}}}


def compressor_filter(c):
    lib = c.get("library")
    if lib not in COMPRESSOR_LIBS:
        raise ValueError("compressor.library must be one of %s" % sorted(COMPRESSOR_LIBS))
    name, url, defaults = COMPRESSOR_LIBS[lib]
    bad = sorted(set(c) - {"library"} - set(defaults))
    if bad:
        raise ValueError("compressor %s: unknown fields %s" % (lib, bad))
    cfg = dict(defaults)
    cfg.update({k: v for k, v in c.items() if k != "library"})
    cfg["@type"] = url
    return {"name": "envoy.filters.http.compressor", "typed_config": {
        "@type": COMPRESSOR, "response_direction_config": copy.deepcopy(COMPRESSOR_RESPONSE),
        "compressor_library": {"name": "epl", "typed_config": cfg}}}


def lua_filter(lu):
    if set(lu) != {"inline"} or not isinstance(lu["inline"], str) or not lu["inline"].strip():
        raise ValueError("lua takes {inline: source}")
    return {"name": "envoy.filters.http.lua", "typed_config": {
        "@type": LUA, "default_source_code": {"inline_string": lu["inline"]}}}


def wasm_filter(w):
    if not w.get("file") or not w.get("sha256") or w.get("runtime", WASM_RUNTIMES[0]) not in WASM_RUNTIMES:
        raise ValueError("wasm takes {file, sha256, runtime: %s}" % "|".join(WASM_RUNTIMES))
    return {"name": "envoy.filters.http.wasm", "typed_config": {
        "@type": WASM, "config": {
            "name": "epl", "root_id": "",
            "vm_config": {"vm_id": "epl", "runtime": w.get("runtime", WASM_RUNTIMES[0]),
                          "code": {"local": {"filename": w["file"]}}},
            "failure_policy": "FAIL_CLOSED"}}}


def stats_cluster_names(count, seed):
    """Seeded service-like cluster names: svc-<4 digits>-<word>.ns-<2 digits>.cluster.test."""
    import random
    r = random.Random("epl-stats-clusters:%s" % seed)
    return ["svc-%04d-%s.ns-%02d.cluster.test" % (i, r.choice(STATS_WORDS), r.randint(0, 99))
            for i in range(int(count))]


def stats_clusters(sc, origin_port):
    bad = sorted(set(sc) - {"count", "seed", "idle_timeout_s"})
    if bad or int(sc.get("count", 0)) < 1:
        raise ValueError("stats_clusters takes {count >= 1, seed, idle_timeout_s}")
    idle = "%ds" % int(sc.get("idle_timeout_s", 1))
    out = []
    for n in stats_cluster_names(sc["count"], sc.get("seed", 1)):
        c = _static_cluster(n, origin_port)
        c["typed_extension_protocol_options"] = {"envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
            "@type": UPSTREAM_HTTP, "common_http_protocol_options": {"idle_timeout": idle},
            "explicit_http_config": {"http_protocol_options": {}}}}
        out.append(c)
    return out


def stats_access_log_names(count):
    """The counter names of the stats access logger, without scope and tag: c000, c001, ..."""
    return ["c%03d" % i for i in range(int(count))]


def stats_access_log_flat(i, tag_value):
    """The flat stat name of counter i for one tag value (scope, name, tag name, tag value)."""
    return "%s.%s.%s.%s" % (STATS_LOG_SCOPE, stats_access_log_names(i + 1)[i], STATS_LOG_TAG, tag_value)


def stats_access_log(sl):
    """The HCM access-log entry of the `stats_access_log` setting. Shape from
    api/envoy/extensions/access_loggers/stats/v3/stats.proto at v1.40.2: exactly one of the
    deprecated stat_prefix and stats_scope must be set (stats_scope here, with only its prefix:
    max_counters unset means no limit, enable_eviction false); a counter needs value_format or
    value_fixed (value_fixed 1 here: no formatter runs for the value)."""
    if not isinstance(sl, dict) or not {"counters", "tag"} <= set(sl) <= {"counters", "tag", "hot"}:
        raise ValueError("stats_access_log takes {counters, tag} and optionally hot")
    if sl.get("hot", False) not in (True, False):
        raise ValueError("stats_access_log.hot must be true or false")
    n = sl["counters"]
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= STATS_LOG_MAX_COUNTERS:
        raise ValueError("stats_access_log.counters must be an integer from 1 to %d" % STATS_LOG_MAX_COUNTERS)
    if sl["tag"] not in STATS_LOG_TAG_VALUES:
        raise ValueError("stats_access_log.tag must be one of %s" % (STATS_LOG_TAG_VALUES,))
    return {"name": "envoy.access_loggers.stats", "typed_config": {
        "@type": STATS_LOG, "stats_scope": {"prefix": STATS_LOG_SCOPE},
        "counters": [{"stat": {"name": name, "tags": [{"name": STATS_LOG_TAG, "value_format": sl["tag"]}]},
                      "value_fixed": 1}
                     # hot: the first counter, n times. The logger (stats.cc at v1.40.2) builds one
                     # entry per configured counter with no check for repeats and, per request, walks
                     # the entries: one tag format, one lookup and one add each.
                     for name in ([stats_access_log_names(1)[0]] * n if sl.get("hot") else stats_access_log_names(n))]}}


def stats_sink(sk, envoy_cfg):
    kind = sk.get("kind")
    if kind in ("statsd", "dog_statsd"):
        addr = {"socket_address": {"protocol": "UDP", "address": "127.0.0.1",
                                   "port_value": int(envoy_cfg["stats_sink_port"])}}
        if kind == "statsd":
            # max_bytes_per_datagram on StatsdSink exists only in own builds that add it (a release
            # rejects the field), so an arm sets it only with such a binary
            bad = sorted(set(sk) - {"kind", "prefix", "max_bytes_per_datagram"})
            tc = {"@type": STATSD, "address": addr, "prefix": sk.get("prefix", "envoy")}
            if sk.get("max_bytes_per_datagram"):
                tc["max_bytes_per_datagram"] = int(sk["max_bytes_per_datagram"])
            name = "envoy.stat_sinks.statsd"
        else:
            bad = sorted(set(sk) - {"kind", "prefix", "max_bytes_per_datagram"})
            tc = {"@type": DOG_STATSD, "address": addr, "prefix": sk.get("prefix", "envoy")}
            if sk.get("max_bytes_per_datagram"):
                tc["max_bytes_per_datagram"] = int(sk["max_bytes_per_datagram"])
            name = "envoy.stat_sinks.dog_statsd"
    elif kind == "otlp":
        bad = sorted(set(sk) - {"kind", "max_data_points_per_request"})
        tc = {"@type": OTLP_SINK, "grpc_service": {"envoy_grpc": {"cluster_name": "otel_collector"}}}
        if sk.get("max_data_points_per_request"):
            tc["max_data_points_per_request"] = int(sk["max_data_points_per_request"])
        name = "envoy.stat_sinks.open_telemetry"
    else:
        raise ValueError("stats_sink.kind must be statsd, dog_statsd or otlp")
    if bad:
        raise ValueError("stats_sink %s: unknown fields %s" % (kind, bad))
    return {"name": name, "typed_config": tc}


# What the multi-threaded stats shape must not contain: anything that reads a stat to decide
# (least-request or bounded-load balancing, outlier detection, health checks, the fault and
# local rate-limit filters, a stats sink).
AUDIT_LB = {"ROUND_ROBIN"}


def audit_mt_s(b):
    """[problem] of a bootstrap against the decision-reader list of the mt-s shape."""
    probs = []
    clusters = b["static_resources"]["clusters"]
    if [c["name"] for c in clusters] != ["origin"]:
        probs.append("clusters %s, expected the one origin cluster" % [c["name"] for c in clusters])
    for c in clusters:
        if c.get("lb_policy", "ROUND_ROBIN") not in AUDIT_LB:
            probs.append("cluster %s lb_policy %s" % (c["name"], c.get("lb_policy")))
        for k in ("outlier_detection", "health_checks", "common_lb_config", "least_request_lb_config"):
            if c.get(k):
                probs.append("cluster %s has %s" % (c["name"], k))
        eps = [e for ep in c["load_assignment"]["endpoints"] for e in ep["lb_endpoints"]]
        if len(eps) != 1:
            probs.append("cluster %s has %d hosts, expected one" % (c["name"], len(eps)))
    ls = b["static_resources"]["listeners"]
    if len(ls) != 1:
        probs.append("%d listeners, expected one" % len(ls))
    for l_ in ls:
        for ch in l_["filter_chains"]:
            for f in ch["filters"]:
                hf = [x["name"] for x in f["typed_config"].get("http_filters", [])]
                if hf != ["envoy.filters.http.router"]:
                    probs.append("http filters %s, expected the router only" % hf)
    if b.get("stats_sinks"):
        probs.append("a stats sink is configured")
    return probs


def _static_cluster(name, port, http2=False):
    c = {"name": name, "connect_timeout": "1s", "type": "STATIC", "lb_policy": "ROUND_ROBIN",
         "load_assignment": {"cluster_name": name, "endpoints": [{"lb_endpoints": [{
             "endpoint": {"address": {"socket_address": {"address": "127.0.0.1", "port_value": int(port)}}}}]}]}}
    if http2:
        c["typed_extension_protocol_options"] = {"envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
            "@type": UPSTREAM_HTTP, "explicit_http_config": {"http2_protocol_options": {}}}}
    return c


TLS_KEYS = {"cert", "resumption", "groups", "client_ca", "client_san"}


def _cert_kind(kind, what):
    if kind not in CERT_KINDS:
        raise ValueError("%s must be one of %s" % (what, sorted(CERT_KINDS)))
    return kind


def _validation(ca, san, cert_dir):
    v = {"trusted_ca": {"filename": os.path.join(cert_dir, ca + ".crt")}}
    if san:
        v["match_typed_subject_alt_names"] = [{"san_type": "DNS", "matcher": {"exact": san}}]
    return v


def tls_socket(tls, cert_dir):
    """Listener TLS. With client_ca the listener requires a client certificate, verified against
    that cert kind (and its DNS SAN when client_san is set): the mTLS server side."""
    bad = sorted(set(tls) - TLS_KEYS)
    if bad:
        raise ValueError("tls: unknown keys %s" % bad)
    kind = _cert_kind(tls.get("cert", "rsa2048"), "tls.cert")
    ctx = {"@type": DTLS, "common_tls_context": {"tls_certificates": [{
        "certificate_chain": {"filename": os.path.join(cert_dir, kind + ".crt")},
        "private_key": {"filename": os.path.join(cert_dir, kind + ".key")}}]}}
    if tls.get("resumption", True) is False:
        ctx["disable_stateless_session_resumption"] = True
        ctx["disable_stateful_session_resumption"] = True
    groups = tls.get("groups")
    if groups is not None:
        # the key-exchange groups the listener accepts (tls_params.ecdh_curves); unset = Envoy's
        # default, X25519MLKEM768:X25519:P-256 in v1.40.2
        if not (isinstance(groups, list) and groups and all(g in TLS_GROUPS for g in groups)):
            raise ValueError("tls.groups must be a non-empty list of %s" % sorted(TLS_GROUPS))
        ctx["common_tls_context"]["tls_params"] = {"ecdh_curves": list(groups)}
    if tls.get("client_ca"):
        ctx["require_client_certificate"] = True
        ctx["common_tls_context"]["validation_context"] = _validation(
            _cert_kind(tls["client_ca"], "tls.client_ca"), tls.get("client_san"), cert_dir)
    elif tls.get("client_san"):
        raise ValueError("tls.client_san needs tls.client_ca")
    return {"name": "envoy.transport_sockets.tls", "typed_config": ctx}


UTLS_KEYS = {"ca", "sni", "san", "cert", "alpn", "max_session_keys"}


def upstream_tls_socket(ut, cert_dir):
    """Origin-cluster TLS: the peer is verified against cert kind `ca` (and its DNS SAN); with
    `cert`, a client certificate is presented (mTLS)."""
    if not isinstance(ut, dict) or not ut.get("ca"):
        raise ValueError("upstream_tls needs ca (the cert kind the peer is verified against)")
    bad = sorted(set(ut) - UTLS_KEYS)
    if bad:
        raise ValueError("upstream_tls: unknown keys %s" % bad)
    ctc = {"validation_context": _validation(_cert_kind(ut["ca"], "upstream_tls.ca"), ut.get("san"), cert_dir)}
    if ut.get("cert"):
        k = _cert_kind(ut["cert"], "upstream_tls.cert")
        ctc["tls_certificates"] = [{"certificate_chain": {"filename": os.path.join(cert_dir, k + ".crt")},
                                    "private_key": {"filename": os.path.join(cert_dir, k + ".key")}}]
    if ut.get("alpn"):
        ctc["alpn_protocols"] = list(ut["alpn"])
    ctx = {"@type": UTLS, "common_tls_context": ctc}
    if ut.get("sni"):
        ctx["sni"] = ut["sni"]
    if ut.get("max_session_keys") is not None:
        ctx["max_session_keys"] = int(ut["max_session_keys"])
    return {"name": "envoy.transport_sockets.tls", "typed_config": ctx}


def cert_kinds_of(envoy_cfg):
    """Every cert kind an envoy section (listener and origin cluster) names."""
    out = set()
    t = envoy_cfg.get("tls") or {}
    if t:
        out.add(t.get("cert", "rsa2048"))
        if t.get("client_ca"):
            out.add(t["client_ca"])
    u = envoy_cfg.get("upstream_tls") or {}
    out.update(x for x in (u.get("ca"), u.get("cert")) if x)
    return out


TLS_GROUPS = {"X25519MLKEM768", "X25519", "P-256"}

CERT_KINDS = {
    # openssl genpkey arguments for the key of a self-signed leaf; generated per run
    # directory (named curve: BoringSSL rejects explicit curve parameters)
    "rsa2048": ["-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048"],
    "ecdsa-p256": ["-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-pkeyopt", "ec_param_enc:named_curve"],
    # the same key type with a DNS SAN (cert_san below): an origin or a second hop that is verified
    # by name, and the client certificate of an mTLS hop
    "ecdsa-p256-san": ["-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-pkeyopt",
                       "ec_param_enc:named_curve"],
    "ecdsa-p256-client": ["-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-pkeyopt",
                          "ec_param_enc:named_curve"],
}
# DNS subjectAltName written into these kinds' certificates (the older kinds have none, unchanged)
CERT_SAN = {"ecdsa-p256-san": "bench.local", "ecdsa-p256-client": "client.bench.local"}


def bootstrap(shapes, envoy_cfg, origin_port, cert_dir=None):
    """Bootstrap for one arm. envoy_cfg is the experiment's envoy section with the
    arm's settings merged in; `upstream_port` (set by the harness for the first
    hop of a two-hop arm) points the origin cluster somewhere else."""
    unknown = sorted(k for k in envoy_cfg if k in SETTINGS_ALIASES)
    if unknown:
        raise ValueError("unknown settings %s" % unknown)
    hcm = {
        "@type": HCM,
        "stat_prefix": "ingress_http",
        "codec_type": envoy_cfg.get("codec_type", "HTTP1"),
        "route_config": {
            "name": "local",
            "virtual_hosts": [dict(vhost_fields(shapes), name="service", domains=["*"],
                                   routes=routes(shapes, envoy_cfg))],
        },
        "http_filters": [{"name": "envoy.filters.http.router", "typed_config": {"@type": ROUTER}}],
    }
    clusters = [_static_cluster("origin", envoy_cfg.get("upstream_port") or origin_port)]
    ka = envoy_cfg.get("downstream_keepalive")
    if ka:
        cho = {}
        if ka.get("idle_timeout_s") is not None:
            cho["idle_timeout"] = "%ds" % int(ka["idle_timeout_s"])
        if ka.get("max_requests") is not None:
            cho["max_requests_per_connection"] = int(ka["max_requests"])
        hcm["common_http_protocol_options"] = cho
    ito = envoy_cfg.get("idle_timers_off")
    if ito:
        if ito is not True:
            raise ValueError("idle_timers_off must be true")
        if (ka or {}).get("idle_timeout_s") is not None:
            raise ValueError("idle_timers_off and downstream_keepalive.idle_timeout_s set the same field")
        hcm["stream_idle_timeout"] = "0s"
        hcm.setdefault("common_http_protocol_options", {})["idle_timeout"] = "0s"
    if envoy_cfg.get("hpack_table_size") is not None:
        hcm["http2_protocol_options"] = {"hpack_table_size": int(envoy_cfg["hpack_table_size"])}
    tr = envoy_cfg.get("tracing")
    if tr:
        hcm["tracing"] = {"random_sampling": {"value": float(tr.get("sampling_pct", 100.0))},
                          "provider": {"name": "envoy.tracers.opentelemetry", "typed_config": {
                              "@type": OTEL, "service_name": "epl",
                              "grpc_service": {"envoy_grpc": {"cluster_name": "otel_collector"},
                                               "timeout": "0.250s"}}}}
        clusters.append(_static_cluster("otel_collector", envoy_cfg["collector_port"], http2=True))
    al = envoy_cfg.get("access_log")
    if al:
        fl = {"@type": FILE_LOG, "path": al["path"]}
        if al.get("format", "text") == "json":
            fl["log_format"] = {"json_format": dict(JSON_LOG_FIELDS)}
        elif al.get("format", "text") != "text":
            raise ValueError("access_log.format must be text or json")
        hcm["access_log"] = [{"name": "envoy.access_loggers.file", "typed_config": fl}]
    if envoy_cfg.get("stats_access_log"):
        hcm.setdefault("access_log", []).append(stats_access_log(envoy_cfg["stats_access_log"]))
    az = envoy_cfg.get("ext_authz")
    gc = envoy_cfg.get("grpc_client", "envoy_grpc")
    if gc not in GRPC_CLIENTS:
        raise ValueError("grpc_client must be one of %s" % (GRPC_CLIENTS,))
    if gc != "envoy_grpc" and not (az == "grpc" or envoy_cfg.get("ext_proc")):
        raise ValueError("grpc_client applies to ext_authz \"grpc\" and ext_proc only")
    if az:
        if az not in (True, "http", "grpc"):
            raise ValueError("ext_authz must be true, \"http\" or \"grpc\"")
        cfg = {"@type": EXT_AUTHZ, "transport_api_version": "V3", "failure_mode_allow": False}
        if az == "grpc":
            port = int(envoy_cfg["authz_grpc_port"])
            cfg["grpc_service"] = grpc_service(gc, "ext_authz", port, timeout="0.5s")
            if gc == "envoy_grpc":
                clusters.append(_static_cluster("ext_authz", port, http2=True))
        else:
            port = int(envoy_cfg["authz_port"])
            cfg["http_service"] = {"server_uri": {"uri": "http://127.0.0.1:%d" % port, "cluster": "ext_authz",
                                                  "timeout": "0.5s"}}
            clusters.append(_static_cluster("ext_authz", port))
        hcm["http_filters"].insert(0, {"name": "envoy.filters.http.ext_authz", "typed_config": cfg})
    ep = envoy_cfg.get("ext_proc")
    if ep:
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, ext_proc_filter(ep, gc, envoy_cfg))
        if gc == "envoy_grpc":
            clusters.append(_static_cluster("ext_proc", int(envoy_cfg["ext_proc_port"]), http2=True))
    if envoy_cfg.get("jwt_authn"):
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, jwt_filter(envoy_cfg["jwt_authn"]))
    if envoy_cfg.get("local_ratelimit"):
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, local_ratelimit_filter(envoy_cfg["local_ratelimit"]))
    if envoy_cfg.get("lua"):
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, lua_filter(envoy_cfg["lua"]))
    if envoy_cfg.get("wasm"):
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, wasm_filter(envoy_cfg["wasm"]))
    if envoy_cfg.get("compressor"):
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, compressor_filter(envoy_cfg["compressor"]))
    chain = {"filters": [{"name": "envoy.filters.network.http_connection_manager", "typed_config": hcm}]}
    if envoy_cfg.get("tls"):
        if not cert_dir:
            raise ValueError("tls needs a certificate directory")
        chain["transport_socket"] = tls_socket(envoy_cfg["tls"], cert_dir)
    if envoy_cfg.get("circuit_breakers_max"):
        # one threshold for every cluster of this Envoy (default priority), so no pool or
        # request limit of the defaults (1024) caps a leg
        n = int(envoy_cfg["circuit_breakers_max"])
        for c in clusters:
            c["circuit_breakers"] = {"thresholds": [{"max_connections": n, "max_pending_requests": n,
                                                     "max_requests": n, "max_retries": n}]}
    listener = {
        "name": "listener_0",
        "address": {"socket_address": {"address": envoy_cfg.get("listener_address", "127.0.0.1"),
                                       "port_value": int(envoy_cfg["listener_port"])}},
        "filter_chains": [chain],
    }
    fan = envoy_cfg.get("listener_fanout")
    if fan is not None:
        # one listener (one filter chain, one TLS context, one session-ticket key) on N loopback
        # addresses: the listener's address plus additional_addresses, the next N-1 addresses
        import ipaddress
        n = int(fan)
        first = ipaddress.IPv4Address(envoy_cfg.get("listener_address", "127.0.0.1"))
        if n < 2 or first not in ipaddress.IPv4Network("127.0.0.0/8") \
                or first + (n - 1) not in ipaddress.IPv4Network("127.0.0.0/8"):
            raise ValueError("listener_fanout needs N >= 2 addresses inside 127.0.0.0/8 from listener_address")
        listener["additional_addresses"] = [
            {"address": {"socket_address": {"address": str(first + i), "port_value": int(envoy_cfg["listener_port"])}}}
            for i in range(1, n)]
    if envoy_cfg.get("tcp_defer_accept_s") is not None:
        # TCP_DEFER_ACCEPT (IPPROTO_TCP 6, option 9) on the listen socket(s): the kernel hands a
        # connection to accept() only once data has arrived; the additional addresses inherit it
        v = int(envoy_cfg["tcp_defer_accept_s"])
        if v < 1:
            raise ValueError("tcp_defer_accept_s must be at least 1")
        listener["socket_options"] = [{"description": "TCP_DEFER_ACCEPT", "level": 6, "name": 9, "int_value": v,
                                       "state": "STATE_PREBIND"}]
    if envoy_cfg.get("reuse_port") is not None:
        if envoy_cfg["reuse_port"] is not False:
            raise ValueError("reuse_port takes false (one listen socket shared by every worker); unset = default")
        listener["enable_reuse_port"] = False
    if envoy_cfg.get("exact_balance", True):
        listener["connection_balance_config"] = {"exact_balance": {}}
    if envoy_cfg.get("buffer_limit_bytes") is not None:
        listener["per_connection_buffer_limit_bytes"] = int(envoy_cfg["buffer_limit_bytes"])
        clusters[0]["per_connection_buffer_limit_bytes"] = int(envoy_cfg["buffer_limit_bytes"])
    uh = envoy_cfg.get("upstream_http")
    if uh:
        cho = {}
        if uh.get("idle_timeout_s") is not None:
            cho["idle_timeout"] = "%ds" % int(uh["idle_timeout_s"])
        if uh.get("max_requests") is not None:
            cho["max_requests_per_connection"] = int(uh["max_requests"])
        if uh.get("max_connection_duration_s") is not None:
            cho["max_connection_duration"] = "%ds" % int(uh["max_connection_duration_s"])
        bad = sorted(set(uh) - {"idle_timeout_s", "max_requests", "max_connection_duration_s"})
        if bad or not cho:
            raise ValueError("upstream_http takes idle_timeout_s, max_requests, max_connection_duration_s")
        clusters[0]["typed_extension_protocol_options"] = {
            "envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
                "@type": UPSTREAM_HTTP, "common_http_protocol_options": cho,
                "explicit_http_config": {"http_protocol_options": {}}}}
    h2u = envoy_cfg.get("upstream_http2")
    if h2u:
        if h2u is not True:
            raise ValueError("upstream_http2 must be true")
        if uh:
            raise ValueError("upstream_http2 and upstream_http both set the origin cluster's protocol options")
        clusters[0]["typed_extension_protocol_options"] = {
            "envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
                "@type": UPSTREAM_HTTP, "explicit_http_config": {"http2_protocol_options": {}}}}
    if envoy_cfg.get("upstream_tls") is not None:
        if not cert_dir:
            raise ValueError("upstream_tls needs a certificate directory")
        clusters[0]["transport_socket"] = upstream_tls_socket(envoy_cfg["upstream_tls"], cert_dir)
    if envoy_cfg.get("origin_server", "plain") not in ORIGIN_SERVERS:
        raise ValueError("origin_server must be one of %s" % (ORIGIN_SERVERS,))
    gs = envoy_cfg.get("grpc_stats")
    if gs is not None:
        if not isinstance(gs, dict) or set(gs) - {"stats_for_all_methods"}:
            raise ValueError("grpc_stats takes {stats_for_all_methods: bool}")
        f = {"@type": GRPC_STATS}
        if "stats_for_all_methods" in gs:
            f["stats_for_all_methods"] = bool(gs["stats_for_all_methods"])
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1,
                                   {"name": "envoy.filters.http.grpc_stats", "typed_config": f})
    if envoy_cfg.get("upstream_pool_per_downstream"):
        clusters[0]["connection_pool_per_downstream_connection"] = True
    out = {
        "admin": {"address": {"socket_address": {"address": "127.0.0.1",
                                                 "port_value": int(envoy_cfg["admin_port"])}}},
        "static_resources": {"listeners": [listener], "clusters": clusters},
    }
    sc = envoy_cfg.get("stats_clusters")
    if sc:
        clusters.extend(stats_clusters(sc, envoy_cfg.get("upstream_port") or origin_port))
        hcm["route_config"]["virtual_hosts"][0]["routes"].append(
            {"match": {"path": STATS_PRIME_PATH}, "route": {"cluster_header": STATS_CLUSTER_HEADER}})
    sf = envoy_cfg.get("stats_flush")
    if sf:
        if set(sf) == {"interval_s"}:
            v = float(sf["interval_s"])
            out["stats_flush_interval"] = ("%gs" % v) if v >= 0.001 else None
        elif sf == {"on_admin": True}:
            out["stats_flush_on_admin"] = True
        else:
            raise ValueError("stats_flush takes {interval_s} or {on_admin: true}")
    sk = envoy_cfg.get("stats_sink")
    if sk:
        if sf == {"on_admin": True}:
            raise ValueError("a stats sink with stats_flush on_admin flushes only on admin reads")
        out["stats_sinks"] = [stats_sink(sk, envoy_cfg)]
        if sk.get("kind") == "otlp" and not any(c["name"] == "otel_collector" for c in clusters):
            clusters.append(_static_cluster("otel_collector", envoy_cfg["collector_port"], http2=True))
    if envoy_cfg.get("stats_reject_all"):
        out["stats_config"] = {"stats_matcher": {"reject_all": True}}
    rt = envoy_cfg.get("runtime")
    if rt is not None:
        if not isinstance(rt, dict) or not rt or not all(
                isinstance(v, (bool, int, float, str)) for v in rt.values()):
            raise ValueError("runtime takes a non-empty {key: bool | number | string}")
        out["layered_runtime"] = {"layers": [{"name": "epl-static", "static_layer": dict(rt)}]}
    if envoy_cfg.get("xds_update") and not envoy_cfg.get("xds"):
        raise ValueError("xds_update needs xds")
    if envoy_cfg.get("xds"):
        _xds_bootstrap(out, hcm, shapes, envoy_cfg)
    return out


ORIGIN_SERVERS = ("plain", "h2c", "tls")


XDS_EXCLUSIVE = ("two_hop", "buffer_limit_bytes", "upstream_http", "upstream_pool_per_downstream", "stats_clusters",
                 "circuit_breakers_max", "upstream_port", "upstream_tls")


def _xds_bootstrap(out, hcm, shapes, envoy_cfg):
    """Routes by RDS and the origin (with the filler clusters) by CDS, each from its own file."""
    from . import xds
    x = envoy_cfg["xds"]
    xds.check_size(x)
    if not x.get("dir"):
        raise ValueError("xds needs a directory (the harness sets xds.dir)")
    bad = [k for k in XDS_EXCLUSIVE if envoy_cfg.get(k)]
    if envoy_cfg.get("origin_server", "plain") != "plain":
        bad.append("origin_server")
    if bad or vhost_fields(shapes):
        raise ValueError("xds cannot be combined with %s" % (bad or ["route_table.vhost"]))
    up = envoy_cfg.get("xds_update")
    if up:
        xds.kind_type(up.get("kind"))
        if float(up.get("rate_hz", 0)) <= 0:
            raise ValueError("xds_update.rate_hz must be > 0")
        if up["kind"] == "eds" and not int(x.get("eds_endpoints", 0)):
            raise ValueError("an eds update needs xds.eds_endpoints")
    p = xds.paths(x["dir"])
    del hcm["route_config"]
    hcm["rds"] = {"route_config_name": xds.ROUTE_NAME, "config_source": xds.config_source(p["rds"])}
    out["static_resources"]["clusters"] = [c for c in out["static_resources"]["clusters"] if c["name"] != "origin"]
    if not out["static_resources"]["clusters"]:
        del out["static_resources"]["clusters"]
    out["dynamic_resources"] = {"cds_config": xds.config_source(p["cds"])}
    out["node"] = {"id": "epl", "cluster": "epl"}


def grpc_service(client, name, port, timeout=None):
    """GrpcService for a side service on 127.0.0.1:port: envoy_grpc through the static cluster
    `name` (HTTP/2), or google_grpc straight to the address (insecure channel: no credentials
    set; the client's stats under grpc.<name>.)."""
    if client == "envoy_grpc":
        gs = {"envoy_grpc": {"cluster_name": name}}
    elif client == "google_grpc":
        gs = {"google_grpc": {"target_uri": "127.0.0.1:%d" % int(port), "stat_prefix": name}}
    else:
        raise ValueError("grpc_client must be one of %s" % (GRPC_CLIENTS,))
    if timeout:
        gs["timeout"] = timeout
    return gs


def ext_proc_filter(ep, client, envoy_cfg):
    if ep is True:
        ep = {}
    bad = sorted(set(ep) - {"mode", "observability_mode"})
    if bad:
        raise ValueError("ext_proc takes mode and observability_mode (got %s)" % bad)
    mode = ep.get("mode", "default")
    if mode not in EXT_PROC_MODES:
        raise ValueError("ext_proc.mode must be one of %s" % sorted(EXT_PROC_MODES))
    cfg = {"@type": EXT_PROC, "grpc_service": grpc_service(client, "ext_proc", envoy_cfg["ext_proc_port"]),
           "failure_mode_allow": False}
    if EXT_PROC_MODES[mode]:
        cfg["processing_mode"] = dict(EXT_PROC_MODES[mode])
    if ep.get("observability_mode"):
        cfg["observability_mode"] = True
    return {"name": "envoy.filters.http.ext_proc", "typed_config": cfg}


# keys that look like settings but are not (typos of the real ones)
SETTINGS_ALIASES = {"tracer", "accesslog", "access_logs", "extauthz", "retry", "retry_policy", "buffer_limit",
                    "hpack", "twohop", "hop2"}


def bootstrap_text(shapes, envoy_cfg, origin_port, cert_dir=None):
    return json.dumps(bootstrap(shapes, envoy_cfg, origin_port, cert_dir), indent=1, sort_keys=True) + "\n"


def origin_files(shapes):
    """{relative path under www: size} for proxied shapes."""
    out = {}
    for s in shapes:
        if s["kind"] == "proxied" and not s.get("grpc"):  # a gRPC shape's body is grpc_files'
            out[s["path"].lstrip("/")] = int(s["body_bytes"])
    return out


def body_path(shape, root):
    return os.path.join(root, shape["body_file"])


def origin_bodies(shapes, root):
    """{relative path under www: bytes} for proxied shapes that serve a file from the
    harness (`body_file`, checked against `body_sha256` and `body_bytes`)."""
    import hashlib
    out = {}
    for s in shapes:
        if s["kind"] != "proxied" or not s.get("body_file"):
            continue
        with open(body_path(s, root), "rb") as f:
            b = f.read()
        if hashlib.sha256(b).hexdigest() != s.get("body_sha256"):
            raise ValueError("shape %s: %s does not match body_sha256" % (s["name"], s["body_file"]))
        if len(b) != int(s["body_bytes"]):
            raise ValueError("shape %s: body_bytes %s but the file has %d" % (s["name"], s["body_bytes"], len(b)))
        out[s["path"].lstrip("/")] = b
    return out


def content_types(shapes):
    """{path: content type} for proxied shapes that set one (else nginx's default type)."""
    out = {}
    for s in shapes:
        if s["kind"] == "proxied" and s.get("content_type"):
            if out.get(s["path"], s["content_type"]) != s["content_type"]:
                raise ValueError("shapes on path %s differ in content_type" % s["path"])
            out[s["path"]] = s["content_type"]
    return out


# gRPC allow service (ext_authz "grpc"): one static gRPC message of length 0 (an empty
# CheckResponse, whose status code 0 means OK) with grpc-status 0 as a trailer, over h2c.
# The static module answers POST with 405; error_page turns that into an internal GET of
# the message file.
AUTHZ_GRPC_FILE = "_authz/ok.grpc"
AUTHZ_GRPC_BODY = b"\x00\x00\x00\x00\x00"


GRPC_DIR = "_grpc"


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def grpc_frame(total):
    """One uncompressed gRPC length-prefixed message of exactly `total` bytes (5-byte prefix
    included): a protobuf message with one bytes field (field 1) of 'a's."""
    if total < 7:
        raise ValueError("a gRPC frame with a one-field message needs at least 7 bytes")
    m = total - 5
    for pad in (b"", b"\x12\x00"):  # where the varint length steps up, an empty field 2 fills the gap
        n = m - len(pad) - 2
        while n > 0 and 1 + len(_varint(n)) + n > m - len(pad):
            n -= 1
        msg = b"\x0a" + _varint(n) + b"a" * n + pad
        if len(msg) == m:
            return b"\x00" + m.to_bytes(4, "big") + msg
    raise ValueError("cannot make a %d-byte gRPC frame" % total)


def grpc_files(shapes):
    """{origin path: (file under www, bytes)} of the gRPC unary responder, one per gRPC shape."""
    out = {}
    for s in shapes:
        if s.get("grpc"):
            out[s["path"]] = ("%s/%s.grpc" % (GRPC_DIR, s["name"]), grpc_frame(int(s["body_bytes"])))
    return out


def _grpc_locations(grpc):
    """nginx locations of the gRPC unary responder: the ext_authz gRPC pattern (a POST gets 405,
    error_page turns it into an internal GET of the message file, served with the trailer)."""
    out = ""
    for path, (rel, _) in sorted((grpc or {}).items()):
        out += ("\n    location = %s { error_page 405 =200 /%s; return 405; }"
                "\n    location = /%s { internal; types { } default_type application/grpc;"
                " add_trailer grpc-status 0 always; }" % (path, rel, rel))
    return out


def nginx_conf(port, workers, authz_port=None, authz_grpc_port=None, keepalive_timeout_s=600,
               keepalive_requests=10000000, types=None, worker_connections=8192, worker_rlimit_nofile=None,
               stub_status=False, h2c_port=None, tls_port=None, tls_cert=None, grpc=None):
    authz = ("  server { listen 127.0.0.1:%d; location / { return 200; } }\n" % int(authz_port)) if authz_port else ""
    tloc = "".join("\n    location = %s { types { } default_type %s; }" % (p, t) for p, t in sorted((types or {}).items()))
    if h2c_port:
        # HTTP/2 cleartext with prior knowledge (http2 on a plaintext listener), same content
        authz += "  server { listen 127.0.0.1:%d; http2 on; root /www;%s%s\n  }\n" % (
            int(h2c_port), tloc, _grpc_locations(grpc))
    if tls_port:
        if not tls_cert:
            raise ValueError("origin tls_port needs tls_cert")
        # TLS with ALPN h2 and http/1.1 (the client's ALPN list picks); certificate from /certs
        authz += ("  server { listen 127.0.0.1:%d ssl; http2 on; root /www;\n"
                  "    ssl_certificate /certs/%s.crt; ssl_certificate_key /certs/%s.key;%s%s\n  }\n" % (
                      int(tls_port), tls_cert, tls_cert, tloc, _grpc_locations(grpc)))
    if authz_grpc_port:
        authz += ("  server { listen 127.0.0.1:%d; http2 on; root /www;\n"
                  "    location / { error_page 405 =200 /%s; return 405; }\n"
                  "    location = /%s { internal; types { } default_type application/grpc;\n"
                  "      add_trailer grpc-status 0 always; }\n"
                  "  }\n" % (int(authz_grpc_port), AUTHZ_GRPC_FILE, AUTHZ_GRPC_FILE))
    head = ("worker_processes %d;\n"
            "pid /tmp/nginx.pid;\n"
            "error_log stderr warn;\n" % int(workers)
            + ("worker_rlimit_nofile %d;\n" % int(worker_rlimit_nofile) if worker_rlimit_nofile else "")
            + "events { worker_connections %d; }\n" % int(worker_connections))
    return head + (
        "http {\n"
        "  access_log off;\n"
        "  sendfile on;\n"
        "  default_type application/octet-stream;\n"
        "  keepalive_requests %d;\n"
        "  keepalive_timeout %ds;\n"
        "  open_file_cache max=64;\n"
        "  server { listen 127.0.0.1:%d; root /www;%s }\n"
        "%s"
        "}\n" % (int(keepalive_requests), int(keepalive_timeout_s), int(port),
                 "".join("\n    location = %s { types { } default_type %s; }" % (p, t)
                         for p, t in sorted((types or {}).items()))
                 + ("\n    location = %s { stub_status; }" % ORIGIN_STATUS_PATH if stub_status else "")
                 + ("\n " if (types or stub_status) else ""), authz)
    )
