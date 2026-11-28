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
import re

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
STDOUT_LOG = "type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog"
LUA_PER_ROUTE = "type.googleapis.com/envoy.extensions.filters.http.lua.v3.LuaPerRoute"
# access-log study: a critical line and a warning line from the worker that runs the request
AL_LUA_CRIT = 'function envoy_on_request(h) h:logCritical("al crit probe") end'
AL_LUA_WARN = 'function envoy_on_request(h) h:logWarn("al warn probe") end'
AL_LUA_NOOP = 'function envoy_on_request(h) end'
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
           "(tls_params.ecdh_curves; unset = Envoy's default X25519MLKEM768:X25519:P-256), alpn: [protocols] "
           "(common_tls_context.alpn_protocols, e.g. [h2]; unset = the listener offers none)}",
    "hpack_table_size": "HTTP/2 HPACK dynamic table size in bytes (http2_protocol_options); unset = default",
    "tracing": "OpenTelemetry tracer over gRPC to the local collector: {sampling_pct: 0..100}",
    "access_log": "file access log: {format: text (Envoy's default format) | json (the same fields)}; the "
                  "harness sets the path unless `path` (absolute: a dedicated mount, or /dev/null) is given; "
                  "`extra`: [{format, path}] more file loggers on the same HCM, in order; `stdout`: {format} one "
                  "envoy.access_loggers.stdout logger (Envoy's stdout); `sink: stdout` makes the stdout logger the "
                  "only one (no file logger); `runtime_key`: K: every logger gets a runtime_filter on K, "
                  "percent_sampled default 0 (off), so runtime value 0..100 logs that percent of requests",
    "al_lua_crit": "access-log study: a Lua filter; per-route scripts call logCritical on GET /crit and logWarn on "
                   "GET /warn (both direct responses, 200, body ok); every other route has the Lua filter disabled",
    "memory_allocator_manager": "bootstrap memory_allocator_manager: {bytes_to_release, memory_release_interval_s}",
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
                       "on every request: {tokens_per_s} (set far above the test rate, so nothing is rejected); "
                       "`filter_enabled_key`: K: filter_enabled is read from runtime key K with default 0% "
                       "(off; runtime value 100: on), filter_enforced stays 100%",
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
                     "(origin.h2c_port) | tls (origin.tls_port, TLS with ALPN h2 and http/1.1) | stream (the "
                     "stream origin's HTTP/1.1 port, origin.stream_port) | stream_h2 (its HTTP/2 cleartext port, "
                     "origin.stream_h2_port; with upstream_http2); ignored by the first hop of a two-hop arm",
    "runtime": "a layered_runtime static layer: {key: value} (e.g. envoy.reloadable_features.http2_use_oghttp2)",
    "runtime_admin_layer": "true: an admin layer (epl-admin) after the static layer, so admin POST /runtime_modify "
                           "can change a runtime key in the running process (the flip blocks)",
    "grpc_stats": "grpc_stats filter before the router: {stats_for_all_methods: bool}",
    "tcp_proxy": "the listener carries a tcp_proxy network filter to the origin cluster instead of the HTTP "
                 "connection manager (stat_prefix relay; no HTTP stats, routes or HTTP filters): true (the "
                 "filter's defaults, idle timeout 1 h) | {idle_timeout_s: N} (0 disables the idle timer)",
    "hop_uds": "true, on a two-hop arm: the hop between the two Envoys is a Unix socket in the run directory "
               "(the first hop's origin cluster and the second hop's listener both use a pipe address)",
    "origin_uds": "true: the origin cluster targets the origin's Unix socket (origin.uds: a second nginx server "
                  "that listens on a socket in a directory of the run, bind-mounted into the origin container)",
    "inert_filters": "the ten core HTTP filters of INERT_FILTERS before the router, each in its documented "
                     "do-nothing state: true | {disabled: true} (every entry carries `disabled: true`: the "
                     "filters are configured and not instantiated on a request)",
    "route_timeout_s": "the route timeout of every proxied route in seconds (0 disables it; unset = Envoy's "
                       "default of 15 s)",
    # runtime switches for in-process screens, and bootstrap-only settings for a restart screen. Each is opt-in:
    # unset, the bootstrap is the one before these settings existed, byte for byte
    "route_switch": "each proxied route is duplicated; the first copy matches only when runtime key K's "
                    "runtime_fraction says so (default 0%: off; runtime value 100: on) and carries the settings "
                    "under test, the second is the plain route: {runtime_key: K (envoy.*), response_headers_to_add: "
                    "[HeaderValueOption], request_headers_to_add: [HeaderValueOption], timeout: \"0s\", "
                    "retry_policy: {RetryPolicy}, stat_prefix: name, tracing: {random_sampling_pct: 0..100}, "
                    "typed_per_filter_config_disabled: [HTTP filter names] (each FilterConfig {disabled: true})}",
    "router_dynamic_stats": "false: the router filter's dynamic_stats off (no per-route/virtual-cluster upstream "
                            "stats); unset = Envoy's default (true)",
    "generate_request_id": "false: HCM generate_request_id false (no x-request-id generated); unset = Envoy's "
                           "default (true)",
    "suppress_envoy_headers": "true: the router filter's suppress_envoy_headers (no x-envoy-* response or upstream "
                              "request headers); unset = Envoy's default (false)",
    "stats_matcher_inclusion": "bootstrap stats_config.stats_matcher.inclusion_list: [{prefix: p} | {exact: name}] "
                               "(only the matching stats are instantiated; every other stat is a null object)",
    "quic": "a second listener, HTTP/3 over QUIC on UDP at the TCP listener's address and port number, with the "
            "same routes and filters and the listener's `tls` certificate: {gso: true (Envoy's default: the GSO "
            "batch writer when the kernel supports it) | false (the default sendmsg writer), prefer_gro: bool "
            "(unset = Envoy's listener default, false), resumption: bool, early_data: bool (unset = Envoy's "
            "defaults, both on without client-certificate validation), ticket_keys: true (one fixed 80-byte "
            "session-ticket key on the QUIC TLS context; used only with the quic_session_ticket_support "
            "runtime guard on), stats: true (the quic_stats connection debug visitor: packet and "
            "retransmission counters per listener, written when a connection closes)}. Needs tls; the TCP "
            "listener stays as it is",
}

ADMIN_LAYER = "epl-admin"


def check_admin_loopback(bootstrap_dict):
    """A writable runtime (an admin layer) only behind an admin listener on 127.0.0.1."""
    adm = ((bootstrap_dict.get("admin") or {}).get("address") or {}).get("socket_address") or {}
    if adm.get("address") != "127.0.0.1":
        raise ValueError("runtime_admin_layer needs the admin address 127.0.0.1, not %r" % adm.get("address"))
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
    # `route_match` (a proxied shape whose client path differs per arm, or carries a query): the
    # route's match object as written; default: the exact path
    r = {"match": copy.deepcopy(shape["route_match"]) if shape.get("route_match") else {"path": shape["path"]}}
    if kind == "proxied":
        r["route"] = {"cluster": cluster}
        if (envoy_cfg or {}).get("retries"):
            r["route"]["retry_policy"] = {"retry_on": "5xx,reset,connect-failure", "num_retries": 2}
        if (envoy_cfg or {}).get("route_timeout_s") is not None:
            r["route"]["timeout"] = "%gs" % float(envoy_cfg["route_timeout_s"])
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
    out, seen, seen_rm = [], {}, []
    for s in shapes:
        r = shape_routes(s, envoy_cfg)
        if s["path"] in seen:
            if seen[s["path"]] != r:
                raise ValueError("shapes on path %s differ in their route" % s["path"])
            continue
        seen[s["path"]] = r
        if s.get("route_match") and any(r == x for x in seen_rm):
            continue  # shapes that share one `route_match` share its route
        if s.get("route_match"):
            seen_rm.append(r)
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
    bad = sorted(set(rl) - {"tokens_per_s", "filter_enabled_key"})
    if bad:
        raise ValueError("local_ratelimit: unknown keys %s" % bad)
    n = int(rl["tokens_per_s"])
    if n < 1:
        raise ValueError("local_ratelimit.tokens_per_s must be positive")
    pct = {"numerator": 100, "denominator": "HUNDRED"}
    enabled = {"runtime_key": "local_rate_limit_enabled", "default_value": pct}
    if rl.get("filter_enabled_key") is not None:
        # the filter's enable dial on runtime key K, default 0% (off); runtime 100 turns it on
        enabled = {"runtime_key": runtime_key_of(rl["filter_enabled_key"], "local_ratelimit.filter_enabled_key"),
                   "default_value": {"numerator": 0, "denominator": "HUNDRED"}}
    return {"name": "envoy.filters.http.local_ratelimit", "typed_config": {
        "@type": LOCAL_RL, "stat_prefix": "http_local_rate_limiter",
        "token_bucket": {"max_tokens": n, "tokens_per_fill": n, "fill_interval": "1s"},
        "filter_enabled": enabled,
        "filter_enforced": {"runtime_key": "local_rate_limit_enforced", "default_value": pct}}}


FILTER_CONFIG = "type.googleapis.com/envoy.config.route.v3.FilterConfig"
ROUTE_SWITCH_KEYS = {"runtime_key", "response_headers_to_add", "request_headers_to_add", "timeout", "retry_policy",
                     "stat_prefix", "tracing", "typed_per_filter_config_disabled"}


def runtime_key_of(k, what):
    """A runtime switch key: an `envoy.*` runtime key, as flipblock requires of a flipped key."""
    if not (isinstance(k, str) and k.startswith("envoy.") and " " not in k and len(k) > len("envoy.")):
        raise ValueError("%s must be a runtime key envoy.* (got %r)" % (what, k))
    return k


def route_switch(routes_, rs, filter_names):
    """Every proxied route (one with a `route` action) is duplicated. The first copy matches only when
    runtime key K's runtime_fraction says so (default 0%: off; runtime value 100: on) and carries the settings under
    test; the second copy is the plain route. Routes without a `route` action are left alone."""
    if not isinstance(rs, dict) or not rs.get("runtime_key"):
        raise ValueError("route_switch takes {runtime_key, ...settings}")
    bad = sorted(set(rs) - ROUTE_SWITCH_KEYS)
    if bad:
        raise ValueError("route_switch: unknown keys %s (allowed: %s)" % (bad, sorted(ROUTE_SWITCH_KEYS)))
    if set(rs) == {"runtime_key"}:
        raise ValueError("route_switch names no setting to switch")
    k = runtime_key_of(rs["runtime_key"], "route_switch.runtime_key")
    out, n = [], 0
    for r in routes_:
        if "route" not in r:
            out.append(r)
            continue
        sw = copy.deepcopy(r)
        sw["match"]["runtime_fraction"] = {"default_value": {"numerator": 0, "denominator": "HUNDRED"},
                                           "runtime_key": k}
        for f in ("response_headers_to_add", "request_headers_to_add"):
            if rs.get(f) is not None:
                if not isinstance(rs[f], list) or not rs[f]:
                    raise ValueError("route_switch.%s takes a non-empty list of HeaderValueOption" % f)
                sw[f] = copy.deepcopy(sw.get(f, [])) + copy.deepcopy(rs[f])
        if rs.get("timeout") is not None:
            sw["route"]["timeout"] = str(rs["timeout"])
        if rs.get("retry_policy") is not None:
            if not isinstance(rs["retry_policy"], dict):
                raise ValueError("route_switch.retry_policy takes a RetryPolicy object")
            sw["route"]["retry_policy"] = copy.deepcopy(rs["retry_policy"])
        if rs.get("stat_prefix") is not None:
            sw["stat_prefix"] = str(rs["stat_prefix"])
        if rs.get("tracing") is not None:
            tr = rs["tracing"]
            pct = tr.get("random_sampling_pct") if isinstance(tr, dict) else None
            if set(tr if isinstance(tr, dict) else {"x"}) != {"random_sampling_pct"} or not (
                    isinstance(pct, (int, float)) and not isinstance(pct, bool) and 0 <= pct <= 100):
                raise ValueError("route_switch.tracing takes {random_sampling_pct: 0..100}")
            # the route's random sampling, in ten-thousandths so 1% and 10% are exact
            sw["tracing"] = {"random_sampling": {"numerator": int(round(pct * 100)), "denominator": "TEN_THOUSAND"}}
        if rs.get("typed_per_filter_config_disabled") is not None:
            names = rs["typed_per_filter_config_disabled"]
            if not isinstance(names, list) or not names or any(x not in filter_names for x in names):
                raise ValueError("route_switch.typed_per_filter_config_disabled names HTTP filters of this HCM "
                                 "(%s), got %r" % (filter_names, names))
            sw.setdefault("typed_per_filter_config", {})
            for x in names:
                sw["typed_per_filter_config"][x] = {"@type": FILTER_CONFIG, "disabled": True}
        out += [sw, r]
        n += 1
    if not n:
        raise ValueError("route_switch: no proxied route to switch")
    return out


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


_HF = "type.googleapis.com/envoy.extensions.filters.http."
# Ten core (non-contrib) HTTP filters, each in a state in which it does nothing to a request of the
# measured shapes (protos read at v1.40.2; the fields validation requires are written out):
# cors without a policy on the route, fault without a fault, rbac without rules, a health check on a
# path the load never requests, header_mutation without mutations, csrf enabled for 0% of requests,
# grpc_web (acts on grpc-web content types only), stateful_session without a session state,
# bandwidth_limit in its DISABLED mode, grpc_http1_bridge (acts on gRPC content types only). The tenth was
# planned as kill_request: that filter is not in the official binary (extensions_build_config.bzl at the
# tag: "Disabled by default. kill_request is not built into most prebuilt images"; `--mode validate`
# rejects its type).
INERT_HEALTH_PATH = "/epl-inert-healthz"
INERT_FILTERS = (
    ("envoy.filters.http.cors", {"@type": _HF + "cors.v3.Cors"}),
    ("envoy.filters.http.fault", {"@type": _HF + "fault.v3.HTTPFault"}),
    ("envoy.filters.http.rbac", {"@type": _HF + "rbac.v3.RBAC"}),
    ("envoy.filters.http.health_check", {"@type": _HF + "health_check.v3.HealthCheck", "pass_through_mode": False,
                                         "headers": [{"name": ":path",
                                                      "string_match": {"exact": INERT_HEALTH_PATH}}]}),
    ("envoy.filters.http.header_mutation", {"@type": _HF + "header_mutation.v3.HeaderMutation"}),
    ("envoy.filters.http.csrf", {"@type": _HF + "csrf.v3.CsrfPolicy",
                                 "filter_enabled": {"default_value": {"numerator": 0, "denominator": "HUNDRED"}}}),
    ("envoy.filters.http.grpc_web", {"@type": _HF + "grpc_web.v3.GrpcWeb"}),
    ("envoy.filters.http.stateful_session", {"@type": _HF + "stateful_session.v3.StatefulSession"}),
    ("envoy.filters.http.bandwidth_limit", {"@type": _HF + "bandwidth_limit.v3.BandwidthLimit",
                                            "stat_prefix": "epl_inert", "enable_mode": "DISABLED"}),
    ("envoy.filters.http.grpc_http1_bridge", {"@type": _HF + "grpc_http1_bridge.v3.Config"}),
)


def inert_filters(spec):
    """The HCM filter entries of the `inert_filters` setting, in INERT_FILTERS order."""
    if spec is True:
        spec = {}
    if not isinstance(spec, dict) or set(spec) - {"disabled"} or spec.get("disabled", True) is not True:
        raise ValueError("inert_filters takes true or {disabled: true}")
    out = []
    for name, cfg in INERT_FILTERS:
        f = {"name": name, "typed_config": copy.deepcopy(cfg)}
        if spec.get("disabled"):
            f["disabled"] = True
        out.append(f)
    return out


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


UDS_MAX_PATH = 107  # sun_path holds 108 bytes with the terminator


def pipe_address(path):
    if not path or not os.path.isabs(path) or len(path.encode()) > UDS_MAX_PATH:
        raise ValueError("a Unix socket path must be absolute and at most %d bytes: %r" % (UDS_MAX_PATH, path))
    return {"pipe": {"path": path}}


def _static_cluster(name, port, http2=False, pipe=None):
    addr = pipe_address(pipe) if pipe else {"socket_address": {"address": "127.0.0.1", "port_value": int(port)}}
    c = {"name": name, "connect_timeout": "1s", "type": "STATIC", "lb_policy": "ROUND_ROBIN",
         "load_assignment": {"cluster_name": name, "endpoints": [{"lb_endpoints": [{
             "endpoint": {"address": addr}}]}]}}
    if http2:
        c["typed_extension_protocol_options"] = {"envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
            "@type": UPSTREAM_HTTP, "explicit_http_config": {"http2_protocol_options": {}}}}
    return c


TLS_KEYS = {"cert", "resumption", "groups", "client_ca", "client_san", "alpn"}


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
    alpn = tls.get("alpn")
    if alpn is not None:
        # the protocols the listener offers in ALPN (common_tls_context.alpn_protocols); unset = none offered
        if not (isinstance(alpn, list) and alpn and all(isinstance(x, str) and x for x in alpn)):
            raise ValueError("tls.alpn must be a non-empty list of protocol names")
        ctx["common_tls_context"]["alpn_protocols"] = list(alpn)
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


def file_logger(fmt, path):
    fl = {"@type": FILE_LOG, "path": path}
    if fmt == "json":
        fl["log_format"] = {"json_format": dict(JSON_LOG_FIELDS)}
    elif fmt != "text":
        raise ValueError("access_log.format must be text or json")
    return {"name": "envoy.access_loggers.file", "typed_config": fl}


def al_lua_crit(hcm):
    """The access-log study's per-route Lua: /crit and /warn are direct responses whose scripts log at critical and
    warning level on the worker that runs them; every other route disables the filter."""
    vh = hcm["route_config"]["virtual_hosts"][0]
    for r in vh["routes"]:
        r.setdefault("typed_per_filter_config", {})["envoy.filters.http.lua"] = {"@type": LUA_PER_ROUTE,
                                                                                 "disabled": True}
    own = []
    for path, src in (("/crit", AL_LUA_CRIT), ("/warn", AL_LUA_WARN)):
        own.append({"match": {"path": path}, "direct_response": {"status": 200, "body": {"inline_string": "ok"}},
                    "typed_per_filter_config": {"envoy.filters.http.lua": {
                        "@type": LUA_PER_ROUTE, "source_code": {"inline_string": src}}}})
    vh["routes"][0:0] = own
    hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, {"name": "envoy.filters.http.lua", "typed_config": {
        "@type": LUA, "default_source_code": {"inline_string": AL_LUA_NOOP}}})


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
    clusters = [_static_cluster("origin", envoy_cfg.get("upstream_port") or origin_port,
                                pipe=envoy_cfg.get("upstream_pipe"))]
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
        bad = sorted(set(al) - {"format", "path", "extra", "stdout", "sink", "runtime_key"})
        if bad:
            raise ValueError("access_log: unknown keys %s" % bad)
        if al.get("sink", "file") not in ("file", "stdout"):
            raise ValueError("access_log.sink must be file or stdout")
        hcm["access_log"] = []
        if al.get("sink", "file") == "file":
            hcm["access_log"].append(file_logger(al.get("format", "text"), al["path"]))
        for x in al.get("extra") or []:
            if not isinstance(x, dict) or set(x) - {"format", "path"} or not str(x.get("path", "")).startswith("/"):
                raise ValueError("access_log.extra takes [{format, path (absolute)}]")
            hcm["access_log"].append(file_logger(x.get("format", "text"), x["path"]))
        so = al.get("stdout")
        if al.get("sink") == "stdout" and so is None:
            so = {"format": al.get("format", "text")}
        if so is not None:
            sl = {"@type": STDOUT_LOG}
            if so.get("format", "text") == "json":
                sl["log_format"] = {"json_format": dict(JSON_LOG_FIELDS)}
            elif so.get("format", "text") != "text":
                raise ValueError("access_log.stdout.format must be text or json")
            hcm["access_log"].append({"name": "envoy.access_loggers.stdout", "typed_config": sl})
        if al.get("runtime_key") is not None:
            k = runtime_key_of(al["runtime_key"], "access_log.runtime_key")
            for lg in hcm["access_log"]:
                lg["filter"] = {"runtime_filter": {"runtime_key": k, "percent_sampled": {
                    "numerator": 0, "denominator": "HUNDRED"}}}
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
    if envoy_cfg.get("al_lua_crit"):
        if envoy_cfg["al_lua_crit"] is not True or envoy_cfg.get("lua"):
            raise ValueError("al_lua_crit must be true and cannot be combined with lua")
        al_lua_crit(hcm)
    if envoy_cfg.get("compressor"):
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, compressor_filter(envoy_cfg["compressor"]))
    if envoy_cfg.get("inert_filters"):
        hcm["http_filters"][-1:-1] = inert_filters(envoy_cfg["inert_filters"])
    rsw = envoy_cfg.get("route_switch")
    if rsw is not None:
        if rsw.get("tracing") is not None and not envoy_cfg.get("tracing"):
            raise ValueError("route_switch.tracing needs the tracing setting (a tracer on the HCM)")
        vh = hcm["route_config"]["virtual_hosts"][0]
        vh["routes"] = route_switch(vh["routes"], rsw, [f["name"] for f in hcm["http_filters"]])
    rds = envoy_cfg.get("router_dynamic_stats")
    if rds is not None:
        if rds is not False:
            raise ValueError("router_dynamic_stats takes false (unset = Envoy's default, true)")
        hcm["http_filters"][-1]["typed_config"]["dynamic_stats"] = False
    sup = envoy_cfg.get("suppress_envoy_headers")
    if sup is not None:
        if sup is not True:
            raise ValueError("suppress_envoy_headers takes true (unset = Envoy's default, false)")
        hcm["http_filters"][-1]["typed_config"]["suppress_envoy_headers"] = True
    gri = envoy_cfg.get("generate_request_id")
    if gri is not None:
        if gri is not False:
            raise ValueError("generate_request_id takes false (unset = Envoy's default, true)")
        hcm["generate_request_id"] = False
    chain = {"filters": [{"name": "envoy.filters.network.http_connection_manager", "typed_config": hcm}]}
    tp = envoy_cfg.get("tcp_proxy")
    if tp:
        chain = {"filters": [tcp_proxy_filter(tp, envoy_cfg)]}
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
    if envoy_cfg.get("listener_pipe"):
        # a Unix socket in the run directory (the harness sets the path): no TCP listener at all
        if envoy_cfg.get("listener_fanout") is not None or envoy_cfg.get("quic") is not None:
            raise ValueError("a pipe listener cannot be combined with listener_fanout or quic")
        listener["address"] = pipe_address(envoy_cfg["listener_pipe"])
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
    mam = envoy_cfg.get("memory_allocator_manager")
    if mam is not None:
        if set(mam) != {"bytes_to_release", "memory_release_interval_s"}:
            raise ValueError("memory_allocator_manager takes {bytes_to_release, memory_release_interval_s}")
        out["memory_allocator_manager"] = {"bytes_to_release": str(int(mam["bytes_to_release"])),
                                           "memory_release_interval": "%gs" % float(mam["memory_release_interval_s"])}
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
    smi = envoy_cfg.get("stats_matcher_inclusion")
    if smi is not None:
        if envoy_cfg.get("stats_reject_all"):
            raise ValueError("stats_matcher_inclusion and stats_reject_all both set the stats matcher")
        if not isinstance(smi, list) or not smi or not all(
                isinstance(x, dict) and len(x) == 1 and list(x)[0] in ("prefix", "exact")
                and isinstance(list(x.values())[0], str) and list(x.values())[0] for x in smi):
            raise ValueError("stats_matcher_inclusion takes a non-empty list of {prefix: p} or {exact: name}")
        out["stats_config"] = {"stats_matcher": {"inclusion_list": {"patterns": copy.deepcopy(smi)}}}
    rt = envoy_cfg.get("runtime")
    if rt is not None:
        if not isinstance(rt, dict) or not rt or not all(
                isinstance(v, (bool, int, float, str)) for v in rt.values()):
            raise ValueError("runtime takes a non-empty {key: bool | number | string}")
        out["layered_runtime"] = {"layers": [{"name": "epl-static", "static_layer": dict(rt)}]}
    ra = envoy_cfg.get("runtime_admin_layer")
    if ra is not None:
        # an admin layer last (it overrides the static layer), so admin POST /runtime_modify can flip a guard
        # in a running process; only for the arms that ask for it, so every other bootstrap is unchanged
        if ra is not True:
            raise ValueError("runtime_admin_layer takes true")
        check_admin_loopback(out)
        layers = (out.get("layered_runtime") or {}).get("layers") or []
        out["layered_runtime"] = {"layers": layers + [{"name": ADMIN_LAYER, "admin_layer": {}}]}
    if envoy_cfg.get("xds_update") and not envoy_cfg.get("xds"):
        raise ValueError("xds_update needs xds")
    if envoy_cfg.get("xds"):
        _xds_bootstrap(out, hcm, shapes, envoy_cfg)
    if envoy_cfg.get("quic") is not None:
        if envoy_cfg.get("listener_fanout") is not None:
            raise ValueError("quic and listener_fanout: not supported together")
        out["static_resources"]["listeners"].append(quic_listener(envoy_cfg, hcm, cert_dir))
    return out


ORIGIN_SERVERS = ("plain", "h2c", "tls", "stream", "stream_h2")

QUIC_DTS = "type.googleapis.com/envoy.extensions.transport_sockets.quic.v3.QuicDownstreamTransport"
UDP_DEFAULT_WRITER = "type.googleapis.com/envoy.extensions.udp_packet_writer.v3.UdpDefaultWriterFactory"
QUIC_KEYS = {"gso", "prefer_gro", "resumption", "early_data", "ticket_keys", "stats", "stats_update_period_ms"}
QUIC_STATS = "type.googleapis.com/envoy.extensions.quic.connection_debug_visitor.quic_stats.v3.Config"
# The v1.40.2 guard that switches QUIC to Envoy's own handshaker and session-ticket keys
# (runtime_features.cc:248-249, FALSE_RUNTIME_GUARD, "Flip to true once QUIC session ticket support is
# stable"). Off: QUICHE's handshaker, no ticket crypter (EnvoyQuicProofSourceBase::GetTicketCrypter
# returns nullptr), so BoringSSL's own ticket keys, one SSL_CTX per worker's QuicCryptoServerConfig.
QUIC_TICKET_GUARD = "envoy.reloadable_features.quic_session_ticket_support"
# A fixed bench session-ticket key (80 bytes, as Envoy requires): not a secret, it protects nothing.
QUIC_TICKET_KEY = bytes(range(80))


def quic_listener(envoy_cfg, hcm, cert_dir):
    """The HTTP/3 listener of the `quic` setting: UDP at the TCP listener's address and port, the same
    HCM (routes, filters, stat_prefix) with codec HTTP3, the listener's TLS certificate."""
    import base64
    q = envoy_cfg["quic"]
    if q is True:
        q = {}
    if not isinstance(q, dict):
        raise ValueError("quic takes {} or {%s}" % ", ".join(sorted(QUIC_KEYS)))
    bad = sorted(set(q) - QUIC_KEYS)
    if bad:
        raise ValueError("quic: unknown keys %s" % bad)
    for k in ("gso", "prefer_gro", "resumption", "early_data", "ticket_keys", "stats"):
        if k in q and q[k] not in (True, False):
            raise ValueError("quic.%s must be true or false" % k)
    if q.get("stats_update_period_ms") is not None and not q.get("stats"):
        raise ValueError("quic.stats_update_period_ms needs quic.stats")
    if q.get("ticket_keys") is False:
        raise ValueError("quic.ticket_keys: leave it out for none")
    tls = envoy_cfg.get("tls")
    if not tls:
        raise ValueError("quic needs tls (the listener's certificate)")
    if set(tls) - {"cert"}:
        # the TCP knobs (resumption off, groups, client certificates) would mean something else here
        raise ValueError("quic uses only tls.cert; set resumption through quic.resumption")
    if q.get("early_data") and q.get("resumption") is False:
        raise ValueError("quic.early_data needs resumption (Envoy refuses the config)")
    dtls = tls_socket({"cert": tls.get("cert", "rsa2048")}, cert_dir)["typed_config"]
    dtls.pop("@type")
    if q.get("ticket_keys"):
        dtls["session_ticket_keys"] = {"keys": [{"inline_bytes": base64.b64encode(QUIC_TICKET_KEY).decode()}]}
    ts = {"@type": QUIC_DTS, "downstream_tls_context": dtls}
    if "resumption" in q:
        ts["enable_resumption"] = q["resumption"]
    if "early_data" in q:
        ts["enable_early_data"] = q["early_data"]
    h3 = copy.deepcopy(hcm)
    h3["codec_type"] = "HTTP3"
    h3.pop("http2_protocol_options", None)
    h3["http3_protocol_options"] = {}
    udp = {"quic_options": {}}
    if q.get("stats"):
        # Envoy's per-listener QUIC connection statistics (listener.<address>.quic_stats.*: packets sent,
        # received and retransmitted, written when a connection closes). Off unless asked for: it adds a
        # visitor to every QUIC connection, so no scored arm sets it.
        qs = {"@type": QUIC_STATS}
        if q.get("stats_update_period_ms") is not None:
            # the visitor also writes the counters of open connections every update_period (default: only at close)
            n = q["stats_update_period_ms"]
            if not isinstance(n, int) or isinstance(n, bool) or n < 1:
                raise ValueError("quic.stats_update_period_ms must be a positive integer")
            qs["update_period"] = "%.3fs" % (n / 1000.0)
        udp["quic_options"]["connection_debug_visitor_config"] = {
            "name": "envoy.quic.connection_debug_visitor.quic_stats", "typed_config": qs}
    if "prefer_gro" in q:
        udp["downstream_socket_config"] = {"prefer_gro": q["prefer_gro"]}
    if q.get("gso", True) is False:
        # an explicit writer: Envoy then never installs the GSO batch writer (listener_impl.cc:785)
        udp["udp_packet_packet_writer_config"] = {"name": "envoy.udp_packet_writer.default",
                                                  "typed_config": {"@type": UDP_DEFAULT_WRITER}}
    return {
        "name": "listener_quic",
        "address": {"socket_address": {"protocol": "UDP", "address": envoy_cfg.get("listener_address", "127.0.0.1"),
                                       "port_value": int(envoy_cfg["listener_port"])}},
        "udp_listener_config": udp,
        "filter_chains": [{"transport_socket": {"name": "envoy.transport_sockets.quic", "typed_config": ts},
                           "filters": [{"name": "envoy.filters.network.http_connection_manager",
                                        "typed_config": h3}]}],
    }


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


TCP_PROXY = "type.googleapis.com/envoy.extensions.filters.network.tcp_proxy.v3.TcpProxy"
# settings that live in the HTTP connection manager: meaningless on a listener that only relays bytes
TCP_PROXY_EXCLUSIVE = ("tracing", "access_log", "stats_access_log", "ext_authz", "ext_proc", "jwt_authn",
                       "local_ratelimit", "lua", "wasm", "compressor", "grpc_stats", "retries", "xds", "quic",
                       "downstream_keepalive", "idle_timers_off", "hpack_table_size", "stats_clusters",
                       "upstream_http", "upstream_http2", "inert_filters", "route_timeout_s")


def tcp_proxy_filter(tp, envoy_cfg):
    """The listener's only network filter of a `tcp_proxy` arm: bytes relayed to the origin cluster."""
    if tp is True:
        tp = {}
    if not isinstance(tp, dict) or set(tp) - {"idle_timeout_s"}:
        raise ValueError("tcp_proxy takes true or {idle_timeout_s}")
    bad = [k for k in TCP_PROXY_EXCLUSIVE if envoy_cfg.get(k)]
    if bad:
        raise ValueError("tcp_proxy cannot be combined with %s" % bad)
    cfg = {"@type": TCP_PROXY, "stat_prefix": "relay", "cluster": "origin"}
    if tp.get("idle_timeout_s") is not None:
        cfg["idle_timeout"] = "%ds" % int(tp["idle_timeout_s"])
    return {"name": "envoy.filters.network.tcp_proxy", "typed_config": cfg}


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
        if s["kind"] == "proxied" and not s.get("grpc") and not s.get("origin_inline") and not s.get("stream"):
            # a gRPC shape's body is grpc_files'; an inline shape's body is in nginx.conf
            out[s["path"].lstrip("/")] = int(s["body_bytes"])
    return out


def inline_bodies(shapes):
    """{path: body bytes count} of the proxied shapes the origin answers from memory (`origin_inline`:
    nginx `return 200 "<body>"`, headers and body in one write)."""
    out = {}
    for s in shapes:
        if s["kind"] == "proxied" and s.get("origin_inline"):
            n = int(s["body_bytes"])
            if not 1 <= n <= 4096 or not re.match(r"^/[A-Za-z0-9_-]+$", s["path"]):
                raise ValueError("shape %s: origin_inline needs 1..4096 body bytes and a plain path" % s.get("name"))
            out[s["path"]] = n
    return out


def chunked_paths(shapes):
    """Paths of the proxied shapes the nginx origin sends chunked (`origin_chunked`)."""
    out = []
    for s in shapes:
        if s["kind"] == "proxied" and s.get("origin_chunked"):
            if not re.match(r"^/[A-Za-z0-9_-]+$", s["path"]):
                raise ValueError("shape %s: origin_chunked needs a plain path" % s.get("name"))
            out.append(s["path"])
    return sorted(set(out))


def _inline_locations(inline):
    return "".join("\n    location = %s { return 200 \"%s\"; }" % (p, "a" * n) for p, n in sorted((inline or {}).items()))


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
               stub_status=False, h2c_port=None, tls_port=None, tls_cert=None, grpc=None, inline=None,
               uds=None, chunked=None):
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
    iloc = _inline_locations(inline)
    # a file the origin itself sends chunked (`origin_chunked` shapes): the SSI filter takes the response
    # through memory buffers and drops its Content-Length, so nginx frames it with its own chunk sizes
    iloc += "".join("\n    location = %s { ssi on; ssi_types *; }" % p for p in sorted(chunked or ()))
    if uds:
        # the same content on a Unix socket (the path as the container sees it)
        authz += "  server { listen unix:%s; root /www;%s%s\n  }\n" % (uds, tloc, iloc)
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
                 + iloc
                 + ("\n " if (types or stub_status or iloc) else ""), authz)
    )
