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
  proxied         GET <path> proxied to the origin, which serves body_bytes.
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
OTEL = "type.googleapis.com/envoy.config.trace.v3.OpenTelemetryConfig"
FILE_LOG = "type.googleapis.com/envoy.extensions.access_loggers.file.v3.FileAccessLog"
UPSTREAM_HTTP = "type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions"
JWT_AUTHN = "type.googleapis.com/envoy.extensions.filters.http.jwt_authn.v3.JwtAuthentication"
LOCAL_RL = "type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit"

# Settings an arm may change, with what each one does. All are generic Envoy
# settings; none is off by default in the sense of costing work.
SETTINGS = {
    "tls": "TLS on the listener: {cert: rsa2048|ecdsa-p256, resumption: true (Envoy default) | false "
           "(stateless and stateful session resumption disabled)}",
    "hpack_table_size": "HTTP/2 HPACK dynamic table size in bytes (http2_protocol_options); unset = default",
    "tracing": "OpenTelemetry tracer over gRPC to the local collector: {sampling_pct: 0..100}",
    "access_log": "file access log: {format: text (Envoy's default format) | json (the same fields)}; the "
                  "harness sets the path",
    "ext_authz": "ext_authz filter against the local allow service in the origin container: true or \"http\" "
                 "(HTTP service, authz_port) | \"grpc\" (gRPC service over h2c, authz_grpc_port)",
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
    "upstream_http": "HTTP/1 pool limits on the origin cluster (HttpProtocolOptions "
                     "common_http_protocol_options): {idle_timeout_s, max_requests, max_connection_duration_s}",
}

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
    """The routes a shape contributes, in order."""
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


def _static_cluster(name, port, http2=False):
    c = {"name": name, "connect_timeout": "1s", "type": "STATIC", "lb_policy": "ROUND_ROBIN",
         "load_assignment": {"cluster_name": name, "endpoints": [{"lb_endpoints": [{
             "endpoint": {"address": {"socket_address": {"address": "127.0.0.1", "port_value": int(port)}}}}]}]}}
    if http2:
        c["typed_extension_protocol_options"] = {"envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
            "@type": UPSTREAM_HTTP, "explicit_http_config": {"http2_protocol_options": {}}}}
    return c


def tls_socket(tls, cert_dir):
    kind = tls.get("cert", "rsa2048")
    if kind not in CERT_KINDS:
        raise ValueError("tls.cert must be one of %s" % sorted(CERT_KINDS))
    ctx = {"@type": DTLS, "common_tls_context": {"tls_certificates": [{
        "certificate_chain": {"filename": os.path.join(cert_dir, kind + ".crt")},
        "private_key": {"filename": os.path.join(cert_dir, kind + ".key")}}]}}
    if tls.get("resumption", True) is False:
        ctx["disable_stateless_session_resumption"] = True
        ctx["disable_stateful_session_resumption"] = True
    return {"name": "envoy.transport_sockets.tls", "typed_config": ctx}


CERT_KINDS = {
    # openssl genpkey arguments for the key of a self-signed leaf; generated per run
    # directory (named curve: BoringSSL rejects explicit curve parameters)
    "rsa2048": ["-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048"],
    "ecdsa-p256": ["-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-pkeyopt", "ec_param_enc:named_curve"],
}


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
    az = envoy_cfg.get("ext_authz")
    if az:
        if az not in (True, "http", "grpc"):
            raise ValueError("ext_authz must be true, \"http\" or \"grpc\"")
        cfg = {"@type": EXT_AUTHZ, "transport_api_version": "V3", "failure_mode_allow": False}
        if az == "grpc":
            port = int(envoy_cfg["authz_grpc_port"])
            cfg["grpc_service"] = {"envoy_grpc": {"cluster_name": "ext_authz"}, "timeout": "0.5s"}
            clusters.append(_static_cluster("ext_authz", port, http2=True))
        else:
            port = int(envoy_cfg["authz_port"])
            cfg["http_service"] = {"server_uri": {"uri": "http://127.0.0.1:%d" % port, "cluster": "ext_authz",
                                                  "timeout": "0.5s"}}
            clusters.append(_static_cluster("ext_authz", port))
        hcm["http_filters"].insert(0, {"name": "envoy.filters.http.ext_authz", "typed_config": cfg})
    if envoy_cfg.get("jwt_authn"):
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, jwt_filter(envoy_cfg["jwt_authn"]))
    if envoy_cfg.get("local_ratelimit"):
        hcm["http_filters"].insert(len(hcm["http_filters"]) - 1, local_ratelimit_filter(envoy_cfg["local_ratelimit"]))
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
    if envoy_cfg.get("upstream_pool_per_downstream"):
        clusters[0]["connection_pool_per_downstream_connection"] = True
    return {
        "admin": {"address": {"socket_address": {"address": "127.0.0.1",
                                                 "port_value": int(envoy_cfg["admin_port"])}}},
        "static_resources": {"listeners": [listener], "clusters": clusters},
    }


# keys that look like settings but are not (typos of the real ones)
SETTINGS_ALIASES = {"tracer", "accesslog", "access_logs", "extauthz", "retry", "retry_policy", "buffer_limit",
                    "hpack", "twohop", "hop2"}


def bootstrap_text(shapes, envoy_cfg, origin_port, cert_dir=None):
    return json.dumps(bootstrap(shapes, envoy_cfg, origin_port, cert_dir), indent=1, sort_keys=True) + "\n"


def origin_files(shapes):
    """{relative path under www: size} for proxied shapes."""
    out = {}
    for s in shapes:
        if s["kind"] == "proxied":
            out[s["path"].lstrip("/")] = int(s["body_bytes"])
    return out


# gRPC allow service (ext_authz "grpc"): one static gRPC message of length 0 (an empty
# CheckResponse, whose status code 0 means OK) with grpc-status 0 as a trailer, over h2c.
# The static module answers POST with 405; error_page turns that into an internal GET of
# the message file.
AUTHZ_GRPC_FILE = "_authz/ok.grpc"
AUTHZ_GRPC_BODY = b"\x00\x00\x00\x00\x00"


def nginx_conf(port, workers, authz_port=None, authz_grpc_port=None, keepalive_timeout_s=600,
               keepalive_requests=10000000):
    authz = ("  server { listen 127.0.0.1:%d; location / { return 200; } }\n" % int(authz_port)) if authz_port else ""
    if authz_grpc_port:
        authz += ("  server { listen 127.0.0.1:%d; http2 on; root /www;\n"
                  "    location / { error_page 405 =200 /%s; return 405; }\n"
                  "    location = /%s { internal; types { } default_type application/grpc;\n"
                  "      add_trailer grpc-status 0 always; }\n"
                  "  }\n" % (int(authz_grpc_port), AUTHZ_GRPC_FILE, AUTHZ_GRPC_FILE))
    return (
        "worker_processes %d;\n"
        "pid /tmp/nginx.pid;\n"
        "error_log stderr warn;\n"
        "events { worker_connections 8192; }\n"
        "http {\n"
        "  access_log off;\n"
        "  sendfile on;\n"
        "  default_type application/octet-stream;\n"
        "  keepalive_requests %d;\n"
        "  keepalive_timeout %ds;\n"
        "  open_file_cache max=64;\n"
        "  server { listen 127.0.0.1:%d; root /www; }\n"
        "%s"
        "}\n" % (int(workers), int(keepalive_requests), int(keepalive_timeout_s), int(port), authz)
    )
