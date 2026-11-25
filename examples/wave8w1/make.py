#!/usr/bin/env python3
"""Wave 8, session W8-1: the chunked HTTP/1 body handed on as fragments (no copy). One patched binary (bins.json:
w8-A = v1.40.2 + the chunked body patch + the two UDP receive commits, each behind a runtime guard) against the
official v1.40.2 binary, on S2's rig (HTTP/1.1 both sides, 512 client connections, loopback).

    python3 examples/wave8w1/make.py

Guards. Only envoy.reloadable_features.http1_zero_copy_body_fragments varies (`off`: false, `frag-on`: true). The
two UDP guards do nothing on HTTP/1 over TCP; they are left at their default (true) and written explicitly, the
same in every w8-A arm (a decision for this session, fixed before data; plan section 1 wrote "every other guard false").
Official arms carry no runtime layer.

Runs (the wave 8 plan, section 4.2; chain order a, b, d, c):
  a   w8-1a. Stream origin. Shapes b64k (64 KiB, 4,000 req/s) and b1m (1 MiB, 800 req/s). Arms official-ch8k,
      official-ch8k-A2, off-ch8k, frag-on-ch8k (chunked, one 8 KiB chunk per origin write), off-cl8k,
      frag-on-cl8k (the same bytes in the same writes with a content-length). 6 x 2 x 6 rounds, seed 811.
      Variants a-h64, a-h1m, a-hh: one or both shapes at half rate (rule R3: a load gate failing in the smoke).
  b   w8-1b. nginx origin. Shape ngx-ch64: a 64 KiB file that nginx itself sends chunked (SSI filter on the
      location: two 32 KiB chunks), 2,000 req/s. Arms official, official-A2, off, frag-on. 4 x 8, seed 812.
      Variant b-half (1,008 req/s).
  d   w8-1d. Shape b1m-h2tls: the 1 MiB ch8k response from the stream origin, delivered as HTTP/2 over TLS 1.3 on
      16 client connections, 400 req/s. Arms official, official-A2, off, frag-on. 4 x 4, seed 813. Variant
      d-half (208 req/s).
  c   w8-1c, the rider (official binary only). nginx origin, shapes l64 (64 KiB, 2,000 req/s) and l1m (1 MiB,
      800 req/s; the plan names no rates: S2's rates for these files). Arms cl-ngx, cl-ngx-A2 (HTTP/1.1 upstream),
      h2in-ngx (HTTP/2 cleartext upstream to the same nginx). 3 x 2 x 6, seed 814. Variants c-h64, c-h1m, c-hh.
  smoke-<run>    one round (order fixed), evidence recorded
  mech-sys-<run> tracepoint legs (perf-sys.sh; non-scored): a: official-ch8k, off-ch8k, frag-on-ch8k on both shapes
                 (the official arm is added to the plan's list: it gives the box's own reading); b, d: off,
                 frag-on; c: cl-ngx, h2in-ngx
  mech-kcg-a*    call-graph legs (perf-kcg.sh) of official-ch8k, off-ch8k, frag-on-ch8k on b1m: THE SIGNATURE
                 (the libc copy leaf's share of worker cycles; w1_check.py)

CONFIRMATORY ROWS, fixed in the wave 8 plan, 4.2. Patch family (Holm over 3): C1 frag-on-ch8k vs off-ch8k on b1m; C2 the
same on b64k; C3 frag-on vs off on ngx-ch64. Rider family (Holm over 2): R1, R2 h2in-ngx vs cl-ngx on l64, l1m.
Pre-registered, no kill line, in no family: T1 frag-on vs off on b1m-h2tls. Floors: 1.0 log points on b64k and
b1m, 1.5 on ngx-ch64, b1m-h2tls, l64, l1m. Lines and labels: table.py.

The tail add-on (not W8-1; W8-2's open retransmission flag, the design of the W8-2 result review): tail-a-r1 to
tail-a-r8 and tail-c-r1 to tail-c-r4, from wave8w2/make.py's arms with Envoy's QUIC statistics on. See tail_check.py.
"""

import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "configs")
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "examples", "settings-matrix"))
sys.path.insert(0, ROOT)
import make as sm  # noqa: E402
from epl import experiment as _exp  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


s2 = _load("w7s2_make_for_w8w1", os.path.join(ROOT, "examples", "wave7s2", "make.py"))
w2 = _load("w8w2_make_for_w8w1", os.path.join(ROOT, "examples", "wave8w2", "make.py"))

RUNS = "~/epl/runs/wave8w1"
HARNESS = "~/epl/harness-wave8w1"
SEEDS = {"a": 811, "b": 812, "d": 813, "c": 814}
ROUNDS = {"a": 6, "b": 8, "d": 4, "c": 6}
K64, M1 = 65536, 1048576
H2C_PORT = 8096
CH = "envoy.reloadable_features.http1_zero_copy_body_fragments"
ST = "envoy.reloadable_features.udp_stop_reading_on_short_recvmmsg"
RU = "envoy.reloadable_features.udp_recvmmsg_reuse_buffers"
RUNTIME_KEYS = {"ch": CH, "st": ST, "ru": RU}
H = "http.ingress_http."
L = "listener.127.0.0.1_10110."
CERT = "ecdsa-p256-san"
STAT_EXTRA = (r"^runtime\.|^listener\.127\.0\.0\.1_10110\.downstream_cx_(destroy|overflow|overload_reject|"
              r"transport_socket_connect_timeout)$|^listener\.127\.0\.0\.1_10110\.ssl\.|^cluster\.origin\.upstream_("
              r"cx_connect_timeout|rq_rx_reset|rq_tx_reset|cx_http1_total|cx_http2_total|rq_completed)$|"
              r"^server\.(envoy_bug_failures|debug_assertion_failures|memory_allocated|memory_heap_size|memory_physical_size)$")
# nginx 1.31.8 of the pinned image, a 65,536-byte file through the SSI filter, as Envoy's upstream connection reads
# it: a 170-byte head, two chunks of 0x8000 with their framing, the last-chunk marker (measured in the local check)
NGX_CH64_WIRE = 170 + 65536 + 2 * 8 + 5
NGX_CL64_WIRE = 257 + 65536

with open(os.path.join(HERE, "bins.json")) as _f:
    BINS = json.load(_f)

# run -> arm -> (build, chunked guard or None for no runtime layer, kind)
ARMS = {
    "a": {"official-ch8k": ("official", None, "ch8k"), "official-ch8k-A2": ("official", None, "ch8k"),
          "off-ch8k": ("w8-A", False, "ch8k"), "frag-on-ch8k": ("w8-A", True, "ch8k"),
          "off-cl8k": ("w8-A", False, "cl8k"), "frag-on-cl8k": ("w8-A", True, "cl8k")},
    "b": {"official": ("official", None, "ngx"), "official-A2": ("official", None, "ngx"),
          "off": ("w8-A", False, "ngx"), "frag-on": ("w8-A", True, "ngx")},
    "d": {"official": ("official", None, "h2tls"), "official-A2": ("official", None, "h2tls"),
          "off": ("w8-A", False, "h2tls"), "frag-on": ("w8-A", True, "h2tls")},
    "c": {"cl-ngx": ("official", None, "cl-ngx"), "cl-ngx-A2": ("official", None, "cl-ngx"),
          "h2in-ngx": ("official", None, "h2in-ngx")},
}
MECH_SYS = {"a": ["official-ch8k", "off-ch8k", "frag-on-ch8k"], "b": ["off", "frag-on"], "d": ["off", "frag-on"],
            "c": ["cl-ngx", "h2in-ngx"]}
KCG = ["official-ch8k", "off-ch8k", "frag-on-ch8k"]
CONF = {"a": [["frag-on-ch8k", "off-ch8k"]], "b": [["frag-on", "off"]], "d": [["frag-on", "off"]], "c": [["h2in-ngx", "cl-ngx"]]}
# bytes-per-request reference arm (the smoke's): arms of one wire format must agree
REF = {"ch8k": "official-ch8k", "cl8k": "off-cl8k", "ngx": "official", "h2tls": "official", "cl-ngx": "cl-ngx", "h2in-ngx": "h2in-ngx"}
VARIANTS = {"a": {"a": (4000, 800), "a-h64": (2000, 800), "a-h1m": (4000, 400), "a-hh": (2000, 400)},
            "b": {"b": (2000,), "b-half": (1008,)},
            "d": {"d": (400,), "d-half": (208,)},
            "c": {"c": (2000, 800), "c-h64": (1008, 800), "c-h1m": (2000, 400), "c-hh": (1008, 400)}}
SHAPES = {"a": ["b64k", "b1m"], "b": ["ngx-ch64"], "d": ["b1m-h2tls"], "c": ["l64", "l1m"]}
BYTES = [("client to Envoy", H + "downstream_cx_rx_bytes_total"), ("Envoy to origin", "cluster.origin.upstream_cx_tx_bytes_total"),
         ("origin to Envoy", "cluster.origin.upstream_cx_rx_bytes_total"), ("Envoy to client", H + "downstream_cx_tx_bytes_total")]


def guards(g):
    return {"ch": -1, "st": -1, "ru": -1} if g is None else {"ch": int(g), "st": 1, "ru": 1}


GUARDS = {run: {a: guards(v[1]) for a, v in arms.items()} for run, arms in ARMS.items()}
PIN = {run: {a: BINS[v[0]]["source_sha256"] for a, v in arms.items()} for run, arms in ARMS.items()}
zero, at_least, ONE = w2.zero, s2.at_least, w2.ONE


def guard_ev(g):
    code = guards(g)
    ev = [{"stat": "runtime_%s.%s" % (when, k), "scope": "field", "equals": code[k], "tol_abs": 0,
           "label": "admin /runtime at the leg's %s: %s is %s" % (when, RUNTIME_KEYS[k], {1: "true", 0: "false", -1: "not set"}[code[k]])}
          for when in ("start", "end") for k in ("ch", "st", "ru")]
    if g is None:
        ev += [{"stat": "layered_runtime", "scope": "config", "absent": True, "label": "no runtime layer in the config"},
               {"stat": "runtime.num_keys", "scope": "leg", "equals": 0, "tol_abs": 0, "label": "runtime.num_keys 0"}]
    else:
        ev += [{"stat": RUNTIME_KEYS[k], "scope": "config", "equals": bool(code[k]),
                "label": "the static runtime layer sets %s %s" % (RUNTIME_KEYS[k], str(bool(code[k])).lower())} for k in ("ch", "st", "ru")]
        ev += [{"stat": "runtime.num_keys", "scope": "leg", "equals": 3, "tol_abs": 0, "label": "runtime.num_keys 3"}]
    return ev


def no_errors(h2_down=False):
    ev = [dict({"stat": H + "downstream_rq_2xx", "label": "downstream 2xx 1.000 per request"}, **ONE),
          {"stat": "client_rate_2xx", "scope": "field", "min": 0.99, "max": 1.01, "per": "field:target_rps",
           "label": "client: 2xx responses per second within 1% of the target rate (open loop, fixed rate)"},
          zero(H + "downstream_cx_destroy", label="no client connection destroyed in the window"),
          zero(H + "downstream_cx_destroy_remote"), zero(H + "downstream_cx_destroy_local"),
          zero(L + "downstream_cx_destroy"), zero(L + "downstream_cx_total", label="no client connection accepted in the window"),
          zero(L + "downstream_cx_overflow", "leg"), zero(L + "downstream_cx_overload_reject", "leg"),
          zero(H + "downstream_cx_delayed_close_timeout"), zero(H + "downstream_cx_protocol_error"),
          zero(H + "downstream_rq_rx_reset"), zero(H + "downstream_rq_tx_reset"),
          zero(H + "downstream_rq_timeout", "leg"), zero(H + "downstream_rq_5xx", "leg"), zero(H + "downstream_rq_4xx", "leg"),
          zero("cluster.origin.upstream_cx_destroy", label="no upstream connection destroyed in the window"),
          zero("cluster.origin.upstream_cx_destroy_remote"), zero("cluster.origin.upstream_cx_destroy_local"),
          zero("cluster.origin.upstream_cx_connect_fail", "leg"), zero("cluster.origin.upstream_cx_connect_timeout", "leg"),
          zero("cluster.origin.upstream_cx_overflow", "leg"), zero("cluster.origin.upstream_cx_protocol_error", "leg"),
          zero("cluster.origin.upstream_rq_timeout", "leg"), zero("cluster.origin.upstream_rq_rx_reset"),
          zero("cluster.origin.upstream_rq_tx_reset"), zero("cluster.origin.upstream_rq_pending_overflow", "leg"),
          zero("cluster.origin.upstream_rq_retry", "leg"),
          zero("server.envoy_bug_failures", "leg"), zero("server.debug_assertion_failures", "leg"),
          {"stat": "envoy_exit", "scope": "field", "equals": 0, "tol_abs": 0, "label": "Envoy exit code 0"}]
    if not h2_down:
        ev += [at_least(H + "downstream_cx_http1_total", 16, label="client hop: HTTP/1.1 connections"),
               zero(H + "downstream_cx_http2_total", "leg", label="client hop: no HTTP/2 connection")]
    return ev


def same_bytes(ref):
    return [{"stat": stat, "scope": "window", "ref": {"arm": ref, "offset": 0}, "tol": 0.005,
             "label": "%s bytes per request within 0.5%% of the %s arm's in the smoke" % (what, ref)} for what, stat in BYTES]


_S2A = {a["name"]: a for a in s2.s2a_arms()}
H1_UP = [at_least("cluster.origin.upstream_cx_http1_total", 1, label="HTTP/1.1 to the origin"),
         zero("cluster.origin.upstream_cx_http2_total", scope="leg", label="no HTTP/2 connection to the origin")]


def stream_ev(kind, rename=None):
    """S2's evidence of its ch8k / cl8k arm (the origin's own counts: body bytes, writes and chunks per response,
    exact; upstream bytes read per request; HTTP/1.1 to the origin)."""
    ev = copy.deepcopy(_S2A[kind]["evidence"])
    if rename:
        ev = [dict(it, shape=rename[1]) if it.get("shape") == rename[0] else it for it in ev if it.get("shape") in (None, rename[0])]
    return ev


def arm(run, name, refs=True):
    build, g, kind = ARMS[run][name]
    b = BINS[build]
    a = {"name": name, "binary": b["binary"], "source": b["source"], "source_sha256": b["source_sha256"], "build": build}
    st = {}
    if kind in ("ch8k", "cl8k"):
        st["origin_server"] = "stream"
        ev = stream_ev(kind)
        a["client"] = {"paths": dict(_S2A[kind]["client"]["paths"])}
    elif kind == "h2tls":
        st.update(origin_server="stream", tls={"cert": CERT, "alpn": ["h2"]})
        ev = stream_ev("ch8k", ("b1m", "b1m-h2tls"))
        a["client"] = {"base_args": list(s2.KA_BASE), "extra_args": ["--protocol", "http2", "--transport-socket", _GATE_TLS],
                       "paths": {"b1m-h2tls": _S2A["ch8k"]["client"]["paths"]["b1m"]}}
        a["validity"] = {"max_pending_total": 1024}
        ev += [at_least(H + "downstream_cx_http2_total", 16, label="client hop: HTTP/2 connections, at least 16 over the leg"),
               zero(H + "downstream_cx_http1_total", "leg", label="client hop: no HTTP/1.1 connection"),
               at_least(L + "ssl.versions.TLSv1.3", 16, label="client hop: TLS 1.3 handshakes, at least 16 over the leg"),
               {"stat": L + "ssl.versions.TLSv1.2", "scope": "leg", "absent": True, "label": "client hop: no TLS 1.2 handshake"},
               zero(L + "ssl.handshake", label="client hop: no TLS handshake in the window"),
               zero(L + "ssl.connection_error", "leg", label="client hop: no TLS connection error"),
               {"stat": "alpn_protocols", "scope": "config", "equals": ["h2"], "label": "the listener offers ALPN h2"},
               {"stat": "conn_downstream.conns", "scope": "field", "min": 16, "max": 16,
                "label": "established TCP connections on the listener port at the end of the window: 16"}]
    elif kind == "ngx":
        ev = [s2.RQ2XX, s2.warm(0.001)] + copy.deepcopy(H1_UP) + [
            {"stat": "cluster.origin.upstream_cx_rx_bytes_total", "scope": "leg", "min": NGX_CH64_WIRE - 8, "max": NGX_CH64_WIRE + 8,
             "per": "leg:cluster.origin.upstream_rq_completed",
             "label": "the origin answers chunked: upstream bytes read per upstream request over the leg %d +/- 8 (head, body, two "
                      "chunk frames, the end marker; with a content-length it would be %d)" % (NGX_CH64_WIRE, NGX_CL64_WIRE)}]
    elif kind == "cl-ngx":
        ev = [s2.RQ2XX, dict(s2.warm(0.001), shape="l64"), dict(s2.warm(0.005), shape="l1m")] + copy.deepcopy(H1_UP)
    elif kind == "h2in-ngx":
        st.update(origin_server="h2c", upstream_http2=True)
        ev = [s2.RQ2XX, dict(s2.warm(0.001), shape="l64"), dict(s2.warm(0.005), shape="l1m"),
              at_least("cluster.origin.upstream_cx_http2_total", 1, label="HTTP/2 to the origin"),
              zero("cluster.origin.upstream_cx_http1_total", scope="leg", label="no HTTP/1 connection to the origin")]
    if g is not None:
        st["runtime"] = {CH: bool(g), ST: True, RU: True}
    if st:
        a["settings"] = st
    ev = copy.deepcopy(ev) + no_errors(h2_down=(kind == "h2tls")) + guard_ev(g)
    if refs:
        ev += same_bytes(REF[kind])
    a["evidence"] = ev
    return a


_GATE_TLS = json.dumps({"name": "envoy.transport_sockets.tls", "typed_config": {
    "@type": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext",
    "common_tls_context": {"alpn_protocols": ["h2"],
                           "tls_params": {"tls_minimum_protocol_version": "TLSv1_2",
                                          "tls_maximum_protocol_version": "TLSv1_3"}}}}, separators=(",", ":"))


def shapes(run, rates):
    if run == "a":
        return s2.s2a_shapes(*rates)
    if run == "b":
        return [{"name": "ngx-ch64", "path": "/ngx-ch64", "kind": "proxied", "body_bytes": K64, "rps": rates[0], "origin_chunked": True}]
    if run == "d":
        return [{"name": "b1m-h2tls", "path": "/b1m-h2tls", "route_match": {"prefix": "/c"}, "kind": "proxied", "stream": True,
                 "body_bytes": M1, "rps": rates[0]}]
    return [dict(s2.L64, rps=rates[0]), dict(s2.L1M, rps=rates[1])]


def scored(run, name, rates, arms=None, refs=True):
    c = s2.base(name, "s2a", stream=run in ("a", "d"), extra_stats=STAT_EXTRA)
    if run == "d":
        c["client"]["extra_args"] = list(s2.KA_BASE)
        c["client"]["connections_per_worker"] = 1
        c["envoy"]["codec_type"] = "HTTP2"
    if run == "c":
        c["origin"].update(h2c_port=H2C_PORT)
    c["measure"] = dict(c["measure"], runtime_keys=dict(RUNTIME_KEYS), leg_binary_sha256=True)
    names = arms or list(ARMS[run])
    n = ROUNDS[run]
    c.update(workdir=RUNS, order_seed=SEEDS[run], rounds=n, rounds_block=n, rounds_max=n, base_arm=names[0],
             arms=[arm(run, x, refs) for x in names], shapes=shapes(run, rates), confirmatory=CONF[run],
             short_run_note="short run: %d fixed rounds in Williams order, run with --allow-short" % n)
    if len(c["shapes"]) > 1:
        c["shape_order"] = "latin"
    return c


def one_round(c, name, rerun):
    c.update(name=name, smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1,
             rerun_invalid=rerun)
    c.pop("short_run_note", None)
    c.pop("confirmatory", None)
    c.pop("shape_order", None)
    return c


def mech(run, name, rates, arms, wrapper, only=None):
    c = one_round(scored(run, name, rates, arms, refs=False), name, 1)
    c.update(comparisons="base")
    if only:
        c["shapes"] = [x for x in c["shapes"] if x["name"] in only]
        for a in c["arms"]:
            a["evidence"] = [it for it in a["evidence"] if s2.envoy_shape_ok(it, only)]
            if (a.get("client") or {}).get("paths"):
                a["client"]["paths"] = {k: v for k, v in a["client"]["paths"].items() if k in only}
    c["measure"] = dict(c["measure"], perf="bash %s/examples/wave8w1/%s" % (HARNESS, wrapper))
    c["validity"] = dict(c.get("validity") or {}, require_perf_unmultiplexed=False)
    return c


# ------------------------------------------------------------------ the tail add-on (W8-2's retransmission count)

TAIL_A = ["h3-official", "h3-off", "h3-stop-on", "h3-both-on"]
TAIL_C = ["h3-off", "h3-both-on"]
TAIL_HIST = r"^listener\.127\.0\.0\.1_10110\.quic_stats\."


def tail(name, arms, rps, duration, window):
    c = w2.mech(name, dict(sm.shapes({})["s"], rps=rps), arms, None, stats=True)
    for a in c["arms"]:
        if a["build"] == "w8-A":
            a["binary"] = BINS["w8-A"]["binary"]
    c["client"] = dict(c["client"], duration_s=duration)
    c["measure"] = dict(c["measure"], window_s=window, leg_end_histograms=TAIL_HIST)
    c.update(workdir=RUNS, rerun_invalid=0)
    return c


def tail_configs():
    out = {}
    for r in range(1, 9):
        # two 4x4 Williams squares (seeds 831, 832); odd rounds 10 s of traffic, even rounds 40 s
        seq = _exp.williams_sequence(4, (r - 1) % 4 + 1, 831 if r <= 4 else 832)
        dur, win = (10, 6) if r % 2 else (40, 20)
        out["tail-a-r%d" % r] = tail("tail-a-r%d" % r, [TAIL_A[i] for i in seq], 2000, dur, win)
    for r in range(1, 5):
        # the quiet shape: 16 connections at 1 request per second each, 60 s; arm order alternates by round
        out["tail-c-r%d" % r] = tail("tail-c-r%d" % r, TAIL_C if r % 2 else TAIL_C[::-1], 16, 60, 50)
    return out


def configs():
    out = {}
    for run, var in VARIANTS.items():
        for name, rates in var.items():
            full = name == run
            out[name] = scored(run, name, rates)
            # a full-rate smoke is not re-run: a failing load gate there is the signal for rule R3
            out["smoke-" + name] = one_round(scored(run, "smoke-" + name, rates), "smoke-" + name, 0 if full else 1)
            out["mech-sys-" + name] = mech(run, "mech-sys-" + name, rates, MECH_SYS[run], "perf-sys.sh")
            if run == "a":
                out["mech-kcg-" + name] = mech(run, "mech-kcg-" + name, rates, KCG, "perf-kcg.sh", ["b1m"])
    out.update(tail_configs())
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn, c in sorted(configs().items()):
        with open(os.path.join(OUT, fn + ".json"), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
        print(fn + ".json")


if __name__ == "__main__":
    main()
