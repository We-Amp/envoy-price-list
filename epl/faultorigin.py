"""The faultable origin. origin.mode "envoy_fault": the origin is an Envoy with
the HTTP fault filter in front of direct responses, in its own container on the origin CPUs (host network, the image
pinned by its ID), so its CPU time stays outside the measurement and the side-service gate reads it from its cgroup
like the nginx origin's. The abort and delay percentages change live through the origin's own admin
POST /runtime_modify (an admin runtime layer), with the fault filter's default runtime keys:

    fault.http.abort.abort_percent       requests aborted, per hundred (the config's denominator is HUNDRED)
    fault.http.abort.http_status         the abort's status code
    fault.http.delay.fixed_delay_percent requests delayed, per hundred
    fault.http.delay.fixed_duration_ms   the delay

Fail closed:
- `set_fault` POSTs the four keys, then reads /runtime back and requires every key's final_value to equal what was
  written; anything else raises FaultNotApplied. A null write (the event A/A) writes the values already in effect
  through the same call.
- `effect_check` compares the origin's own fault counters over a hold (http.origin.fault.aborts_injected and
  .delays_injected over http.origin.downstream_rq_total) with the declared percentages, within z binomial standard
  errors; too few requests is "not checkable", never a pass.

Config (origin section, mode envoy_fault):

    image        the Envoy image (a local image; nothing is pulled), and image_id its sha256 ID (required: the
                 container must run exactly that image)
    port         the origin listener (the SUT's origin cluster points at it, as with nginx)
    admin_port   the origin's own admin (loopback only; never the SUT's)
    workers      the origin Envoy's --concurrency (default 4)
    envoy_path   the binary inside the image (default /usr/local/bin/envoy)
    fault        the starting values: abort_percent, abort_status, delay_percent, delay_ms (default 0, 503, 0, 0)
    name_prefix, platform  as for the nginx origin

Shapes: proxied shapes with a plain body (body_bytes, optional body_file, content_type); the origin answers from
memory (direct_response). gRPC, stream, chunked and Unix-socket shapes, stub_status, TLS and h2c servers and the
authorization services are refused (they are the nginx origin's).
"""

import base64
import hashlib
import http.client
import json
import math
import re
import urllib.parse

ABORT_PCT = "fault.http.abort.abort_percent"
ABORT_STATUS = "fault.http.abort.http_status"
DELAY_PCT = "fault.http.delay.fixed_delay_percent"
DELAY_MS = "fault.http.delay.fixed_duration_ms"
KEYS = (ABORT_PCT, ABORT_STATUS, DELAY_PCT, DELAY_MS)
FIELDS = {"abort_percent": ABORT_PCT, "abort_status": ABORT_STATUS, "delay_percent": DELAY_PCT, "delay_ms": DELAY_MS}
DEFAULT_FAULT = {"abort_percent": 0, "abort_status": 503, "delay_percent": 0, "delay_ms": 0}
STAT_PREFIX = "origin"
FAULT_STATS = ("http.origin.downstream_rq_total", "http.origin.fault.aborts_injected",
               "http.origin.fault.delays_injected", "http.origin.fault.active_faults")
ORIGIN_KEYS = {"mode", "image", "image_id", "port", "admin_port", "workers", "envoy_path", "fault", "name_prefix",
               "platform"}
# keys of the default origin section (experiment.DEFAULTS) that a fault origin leaves at their defaults
DEFAULT_NULL_KEYS = ("authz_port", "authz_grpc_port")
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
MAX_BODY = 1 << 20


class FaultNotApplied(RuntimeError):
    """The origin's runtime does not show the fault values that were written."""


# ---------------------------------------------------------------- validation

def fault_values(v):
    """The four values, defaults filled in; ValueError on anything out of range."""
    v = dict(DEFAULT_FAULT, **(v or {}))
    bad = sorted(set(v) - set(DEFAULT_FAULT))
    if bad:
        raise ValueError("fault: unknown keys %s (known: %s)" % (bad, sorted(DEFAULT_FAULT)))
    for k in ("abort_percent", "delay_percent"):
        if not (isinstance(v[k], int) and not isinstance(v[k], bool) and 0 <= v[k] <= 100):
            raise ValueError("fault.%s must be a whole percent 0-100 (the filter's denominator is HUNDRED)" % k)
    if not (isinstance(v["abort_status"], int) and not isinstance(v["abort_status"], bool)
            and 200 <= v["abort_status"] <= 599):
        raise ValueError("fault.abort_status must be an HTTP status 200-599")
    if not (isinstance(v["delay_ms"], int) and not isinstance(v["delay_ms"], bool) and 0 <= v["delay_ms"] <= 60000):
        raise ValueError("fault.delay_ms must be whole ms 0-60000")
    if v["delay_percent"] > 0 and v["delay_ms"] == 0:
        # the filter delays only a duration above 0, so this could never inject
        raise ValueError("fault.delay_percent above 0 needs fault.delay_ms above 0 (a 0 ms delay never injects)")
    return v


def config_errors(exp):
    """validate's checks for origin.mode envoy_fault."""
    errs = []
    o = exp.get("origin") or {}
    bad = sorted(k for k in set(o) - ORIGIN_KEYS if not (k in DEFAULT_NULL_KEYS and o[k] is None))
    if bad:
        errs.append("origin.mode envoy_fault: unknown or unsupported origin keys %s (the fault origin takes %s)"
                    % (bad, sorted(ORIGIN_KEYS)))
    if not (isinstance(o.get("image"), str) and o["image"].strip()) or o.get("image") == "nginx:alpine":
        errs.append("origin.mode envoy_fault needs origin.image (a local Envoy image)")
    if not (isinstance(o.get("image_id"), str) and IMAGE_ID_RE.match(o["image_id"])):
        errs.append("origin.mode envoy_fault needs origin.image_id (sha256:<64 hex>): the container must run exactly "
                    "that image")
    for k in ("port", "admin_port"):
        if not (isinstance(o.get(k), int) and not isinstance(o.get(k), bool) and 1 <= o[k] <= 65535):
            errs.append("origin.%s must be a port number" % k)
    ports = [o.get("admin_port"), (exp.get("envoy") or {}).get("admin_port"),
             (exp.get("envoy") or {}).get("listener_port"), o.get("port"), (exp.get("collector") or {}).get("port"),
             (exp.get("collector") or {}).get("metrics_port"), (exp.get("stats_sink") or {}).get("port"),
             (exp.get("hop2") or {}).get("listener_port"), (exp.get("hop2") or {}).get("admin_port")]
    if o.get("admin_port") is not None and ports.count(o["admin_port"]) > 1:
        errs.append("origin.admin_port must differ from origin.port, the SUT's ports, the collector's, the stats "
                    "sink's and the second hop's")
    w = o.get("workers", 4)
    if not (isinstance(w, int) and not isinstance(w, bool) and w >= 1):
        errs.append("origin.workers must be a whole number >= 1")
    try:
        fault_values(o.get("fault"))
    except ValueError as ex:
        errs.append("origin.%s" % ex)
    if "origin" not in (exp.get("cpus") or {}):
        errs.append("cpus.origin missing for an envoy_fault origin")
    if (exp.get("measure") or {}).get("responses_from") == "origin" or (exp.get("measure") or {}).get("origin_accepts"):
        errs.append("origin.mode envoy_fault has no stub_status: measure.responses_from origin and origin_accepts "
                    "are the nginx origin's")
    for s in exp.get("shapes") or []:
        if s.get("kind") != "proxied":
            continue
        for k in ("grpc", "stream", "origin_chunked", "uds"):
            if s.get(k):
                errs.append("shape %s: %s is not served by the envoy_fault origin" % (s.get("name"), k))
        if not re.match(r"^/[A-Za-z0-9_./-]*$", str(s.get("path") or "")):
            errs.append("shape %s: the envoy_fault origin needs a plain path" % s.get("name"))
        n = s.get("body_bytes")
        if not (isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= MAX_BODY):
            errs.append("shape %s: body_bytes 0-%d for the envoy_fault origin" % (s.get("name"), MAX_BODY))
    return errs


# ---------------------------------------------------------------- the origin's bootstrap and container

def routes(shapes, root=None):
    """[(path, body bytes, content type or None)] for the proxied shapes, one per path."""
    from . import envoy_config
    bodies = envoy_config.origin_bodies(shapes, root) if root is not None else {}
    out = {}
    for s in shapes:
        if s.get("kind") != "proxied":
            continue
        rel = s["path"].lstrip("/")
        body = bodies.get(rel, b"a" * int(s["body_bytes"]))
        prev = out.get(s["path"])
        if prev is not None and (prev[0] != body or prev[1] != s.get("content_type")):
            raise ValueError("shapes on path %s differ in body or content_type" % s["path"])
        out[s["path"]] = (body, s.get("content_type"))
    return [(p, b, t) for p, (b, t) in sorted(out.items())]


def bootstrap(cfg, shapes, root=None):
    """The origin Envoy's bootstrap (a dict; written as JSON). One listener on 127.0.0.1:port, the fault filter
    (abort and delay at 0 per hundred in the config, so the runtime keys rule) before the router, a direct response
    per shape path; a static runtime layer with the starting values and an admin layer above it; its admin on
    127.0.0.1:admin_port."""
    f = fault_values(cfg.get("fault"))
    rts, biggest = [], 0
    for path, body, ctype in routes(shapes, root):
        biggest = max(biggest, len(body))
        r = {"match": {"path": path},
             "direct_response": {"status": 200, "body": {"inline_bytes": base64.b64encode(body).decode()}}}
        if ctype:
            r["response_headers_to_add"] = [{"header": {"key": "content-type", "value": ctype},
                                             "append_action": "OVERWRITE_IF_EXISTS_OR_ADD"}]
        rts.append(r)
    rts.append({"match": {"prefix": "/"}, "direct_response": {"status": 404}})
    hcm = {"@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3."
                    "HttpConnectionManager",
           "stat_prefix": STAT_PREFIX, "codec_type": "AUTO",
           "route_config": {"name": "origin", "max_direct_response_body_size_bytes": max(4096, biggest),
                            "virtual_hosts": [{"name": "origin", "domains": ["*"], "routes": rts}]},
           "http_filters": [
               {"name": "envoy.filters.http.fault",
                "typed_config": {"@type": "type.googleapis.com/envoy.extensions.filters.http.fault.v3.HTTPFault",
                                 "abort": {"http_status": f["abort_status"],
                                           "percentage": {"numerator": 0, "denominator": "HUNDRED"}},
                                 "delay": {"fixed_delay": "%.3fs" % (max(f["delay_ms"], 1) / 1000.0),
                                           "percentage": {"numerator": 0, "denominator": "HUNDRED"}}}},
               {"name": "envoy.filters.http.router",
                "typed_config": {"@type": "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"}}]}
    return {
        "admin": {"address": {"socket_address": {"address": "127.0.0.1", "port_value": int(cfg["admin_port"])}}},
        "layered_runtime": {"layers": [
            {"name": "epl-origin-static", "static_layer": {FIELDS[k]: v for k, v in sorted(f.items())}},
            {"name": "epl-origin-admin", "admin_layer": {}}]},
        "static_resources": {"listeners": [{
            "name": "origin",
            "address": {"socket_address": {"address": "127.0.0.1", "port_value": int(cfg["port"])}},
            "filter_chains": [{"filters": [{"name": "envoy.filters.network.http_connection_manager",
                                            "typed_config": hcm}]}]}]}}


def bootstrap_text(cfg, shapes, root=None):
    return json.dumps(bootstrap(cfg, shapes, root), indent=1, sort_keys=True)


CONTAINER_BOOTSTRAP = "/etc/epl-fault-origin.json"


def docker_args(cfg, cpus, name, bootstrap_path):
    """docker run arguments: the checked image by its ID with --pull never (never the tag, which
    a re-tag or the pull policy could point elsewhere), host network, the origin CPUs, the bootstrap read-only, the
    image's Envoy as the entrypoint (no shell, no entrypoint script). --disable-hot-restart: with host networking the
    hot-restart domain socket (an abstract socket, per network namespace) would collide with the SUT Envoy's at base
    id 0. No --rm: stop() saves the container's log, then removes it by its ID."""
    return (["docker", "run", "-d", "--pull", "never", "--name", name, "--network", "host", "--cpuset-cpus", cpus]
            + (["--platform", cfg["platform"]] if cfg.get("platform") else [])
            + ["-v", "%s:%s:ro" % (bootstrap_path, CONTAINER_BOOTSTRAP),
               "--entrypoint", cfg.get("envoy_path", "/usr/local/bin/envoy"), cfg["image_id"],
               "-c", CONTAINER_BOOTSTRAP, "--concurrency", str(int(cfg.get("workers", 4))),
               "--log-level", "warn", "--disable-hot-restart"])


def text_sha256(t):
    return hashlib.sha256(t.encode()).hexdigest()


# ---------------------------------------------------------------- the live fault

def _admin(port, method, path, timeout=5.0):
    c = http.client.HTTPConnection("127.0.0.1", int(port), timeout=timeout)
    try:
        c.request(method, path)
        r = c.getresponse()
        return r.status, r.read().decode(errors="replace")
    finally:
        c.close()


def runtime_read(port, timeout=5.0):
    """{key: final_value as a string} of the four fault keys from the origin's /runtime; a key absent is None."""
    st, body = _admin(port, "GET", "/runtime", timeout)
    if st != 200:
        raise FaultNotApplied("origin admin /runtime returned %s" % st)
    try:
        ent = json.loads(body).get("entries") or {}
    except ValueError:
        raise FaultNotApplied("origin admin /runtime is not JSON")
    out = {}
    for k in KEYS:
        v = (ent.get(k) or {}).get("final_value")
        out[k] = None if v is None else str(v)
    return out


def query(values):
    """The /runtime_modify query for the four values."""
    v = fault_values(values)
    return urllib.parse.urlencode([(FIELDS[k], str(v[k])) for k in sorted(FIELDS)])


def set_fault(port, values, clock=None, timeout=5.0):
    """POST the four fault keys to the origin's admin layer, then read /runtime back. Raises FaultNotApplied unless
    the POST answered 200 and every key's final_value equals the value written. Returns the record (the values, the
    read-back, the POST's answer time in ms). The read-back shows the main thread's snapshot; the workers take it a
    moment later through a post (negligible against a hold of seconds)."""
    import time as _t
    clock = clock or _t.monotonic
    v = fault_values(values)
    t0 = clock()
    st, body = _admin(port, "POST", "/runtime_modify?" + query(v), timeout)
    t1 = clock()
    if st != 200:
        raise FaultNotApplied("origin POST /runtime_modify answered %s: %s" % (st, body.strip()[:200]))
    got = runtime_read(port, timeout)
    t2 = clock()
    want = {FIELDS[k]: str(v[k]) for k in FIELDS}
    bad = {k: (got.get(k), want[k]) for k in KEYS if got.get(k) != want[k]}
    rec = {"values": v, "runtime": got, "post_ms": round((t1 - t0) * 1000, 3), "read_ms": round((t2 - t1) * 1000, 3),
           "ok": not bad}
    if bad:
        raise FaultNotApplied("origin runtime does not show the fault values written: %s" % (
            ", ".join("%s=%s (wrote %s)" % (k, g, w) for k, (g, w) in sorted(bad.items()))))
    return rec


def current(port, timeout=5.0):
    """The fault values in effect, read from the origin's /runtime (for a null write). Raises FaultNotApplied when a
    key is missing or not a whole number."""
    got = runtime_read(port, timeout)
    out = {}
    for f, k in FIELDS.items():
        try:
            out[f] = int(got[k])
        except (TypeError, ValueError):
            raise FaultNotApplied("origin runtime %s is %r, not a whole number" % (k, got.get(k)))
    return fault_values(out)


def fault_stats(port, timeout=5.0):
    """The origin's fault counters, {stat: value} (a stat not yet emitted is 0: Envoy creates the fault counters on
    first use), or raises OSError / FaultNotApplied."""
    st, body = _admin(port, "GET", "/stats?filter=%s" % urllib.parse.quote(r"^http\.origin\.(downstream_rq_total|"
                                                                          r"fault\.)"), timeout)
    if st != 200:
        raise FaultNotApplied("origin admin /stats returned %s" % st)
    out = {k: 0 for k in FAULT_STATS}
    for line in body.splitlines():
        k, _, v = line.partition(":")
        k = k.strip()
        if k in out:
            try:
                out[k] = int(v.strip())
            except ValueError:
                pass
    return out


def effect_check(s0, s1, values, z=5.0, min_requests=200):
    """The realised fault shares over a hold, against the declared percentages: each share within z binomial
    standard errors (plus one request) of its percentage. Fewer than min_requests origin requests: not checkable
    (ok False). {ok, reasons, requests, abort_share, delay_share}."""
    v = fault_values(values)
    why = []
    if not s0 or not s1:
        return {"ok": False, "reasons": ["origin fault counters not read"]}
    n = s1["http.origin.downstream_rq_total"] - s0["http.origin.downstream_rq_total"]
    out = {"requests": n}
    if n < min_requests:
        why.append("origin served %d requests in the hold, fewer than %d: the fault's effect is not checkable"
                   % (n, min_requests))
    for name, stat, pct in (("abort", "http.origin.fault.aborts_injected", v["abort_percent"]),
                            ("delay", "http.origin.fault.delays_injected", v["delay_percent"])):
        k = s1[stat] - s0[stat]
        p = pct / 100.0
        share = k / float(n) if n > 0 else None
        out["%s_share" % name] = share
        out["%s_injected" % name] = k
        if n >= min_requests:
            if pct in (0, 100):
                # at 0% the filter's check is always false and at 100% always true, so any
                # other count is a defect (a null hold must show 0 injections)
                want = 0 if pct == 0 else n
                if k != want:
                    why.append("origin %s injected %d of %d requests over the hold, declared %d%% (exactly %d)"
                               % (name, k, n, pct, want))
            else:
                tol = z * math.sqrt(p * (1 - p) / n) + 1.0 / n
                if abs(share - p) > tol:
                    why.append("origin %s share %.4f over the hold, declared %.2f (tolerance %.4f)" % (
                        name, share, p, tol))
    out["ok"] = not why
    out["reasons"] = why
    return out
