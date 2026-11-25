#!/usr/bin/env python3
"""Wave 7, session S2: one proxy, bodies and streams. Config only, on the official v1.40.2 binary
(~/epl/bin/envoy-1.40.2, sha256 enforced) in every arm.

    python3 examples/wave7s2/make.py

Configs (in configs/):

  s2a-chunked.json  HTTP/1.1 client, the stream origin (tools/streamorigin). Shapes b64k (64 KiB body,
                    4,000 req/s) and b1m (1 MiB body, 800 req/s). Arms: cl (content-length, one origin write;
                    base), cl-A2 (A/A), ch4k and ch8k (chunked, one 4 KiB / 8 KiB chunk per origin write),
                    cl8k (content-length in the same flushed 8 KiB writes as ch8k: the control for the
                    copy), h2in (HTTP/2 cleartext upstream to the same origin). 6 arms x 2 shapes, 6 rounds,
                    seed 711. Every arm's request line has the same length (a `pad` query parameter).
  s2a-chunked-h64 / -h1m / -hh
                    the same with b64k, b1m or both at half rate (plan rule R3; used only when the smoke at
                    the full rate fails a load gate or the origin-headroom evidence on that shape)
  s2b-stream.json   HTTP/1.1, SSE-shaped responses from the stream origin: 200-byte events, 1 ms apart.
                    Shapes ev20 (20 events, 2,080 req/s) and ev200 (200 events, 208 req/s): 41,600 events/s
                    in both (the plan's 2,000 and 200; the client needs a multiple of its 16 workers). Arms: base, base-A2 (A/A), idle-off (stream idle 0, downstream connection idle 0,
                    upstream connection idle 0; route timeout at its default). 3 x 2, 6 rounds, seed 712
  s2b-stream-half   the same at 960 and 96 req/s (R3)
  s2c-buf.json      nginx origin, shape l64 (64 KiB proxied, 2,000 req/s): buf-default (base), buf-default-A2,
                    buf-32k (per_connection_buffer_limit_bytes 32768 on the listener and the origin cluster).
                    6 rounds, seed 713
  s2d-h3.json       G's rig (TLS listener plus HTTP/3 listener, 16 client connections), nginx origin, shapes
                    z0 (0-byte body) and s (4 KB), both 2,000 req/s: h2tls (base), h3, h3-A2 (A/A on HTTP/3).
                    6 rounds, seed 714
  smoke-*.json      one round of every arm (order fixed), evidence recorded
  mech-*.json       the non-scored mechanism legs (one round, order fixed): measure.perf is a wrapper
                    (perf-sys.sh: syscall counts; perf-kcg.sh: a system-wide call-graph profile of the
                    Envoy CPUs). Their legs never enter a table of prices.
"""

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "configs")
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "examples", "settings-matrix"))
sys.path.insert(0, ROOT)
import make as sm  # noqa: E402
from epl import envoy_config  # noqa: E402

RUNS = "~/epl/runs/wave7s2"
HARNESS = "~/epl/harness-wave7s2"
CLIENT = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"  # Nighthawk 0.3.0, md5 310df412
SEEDS = {"s2a": 711, "s2b": 712, "s2c": 713, "s2d": 714}
ROUNDS = 6
STREAM_PORT, STREAM_H2_PORT = 8098, 8099
STREAM_BINARY = "tools/streamorigin/out/epl-streamorigin-linux-amd64"
K64, M1 = 65536, 1048576
EVENT_BYTES, GAP_US = 200, 1000

# the stream origin's response heads (tools/streamorigin/main.go; the functional check compares the
# wire sizes computed here with what Envoy reads)
HEAD_CL = "HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: %d\r\n\r\n"
HEAD_CH = "HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nTransfer-Encoding: chunked\r\n\r\n"
HEAD_SSE = "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n\r\n"

Z = {"tol_abs": 0}
ONE = {"per_request": 1.0, "tol": 0.002}
RQ2XX = dict({"stat": "cluster.origin.upstream_rq_2xx"}, **ONE)
SO = "stream_origin.d."
PER_SO = "field:" + SO + "responses"


def stream_sha256():
    with open(os.path.join(ROOT, "tools", "streamorigin", "SHA256SUMS")) as f:
        return f.read().split()[0]


def warm(mx=0.001):
    return {"stat": "cluster.origin.upstream_cx_total", "scope": "window", "max": mx, "per": "field:responses_raw",
            "label": "warm upstream pool: at most %g new connections per request in the window" % mx}


def zero(stat, scope="window", **kw):
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


def at_least(stat, n, scope="leg", **kw):
    return dict({"stat": stat, "scope": scope, "min": n}, **kw)


def absent(stat, scope="leg", **kw):
    return dict({"stat": stat, "scope": scope, "absent": True}, **kw)


def wire_cl(n):
    return len(HEAD_CL % n) + n


def wire_chunked(n, chunk):
    """Head, per chunk its size line and CRLF, the last-chunk marker."""
    tot = len(HEAD_CH) + n + 5
    for off in range(0, n, chunk):
        tot += len("%x" % min(chunk, n - off)) + 4
    return tot


def wire_sse(events, size=EVENT_BYTES):
    return len(HEAD_SSE) + events * (size + len("%x" % size) + 4) + 5


def base(name, run, stream=False, extra_stats=None):
    b = json.loads(json.dumps(sm.BASE))
    b.pop("floor_from")
    b.pop("stop")
    b["client"]["binary"] = CLIENT
    b["origin"].update(stub_status=True)
    if stream:
        b["origin"].update(stream_port=STREAM_PORT, stream_h2_port=STREAM_H2_PORT, stream_binary=STREAM_BINARY,
                           stream_sha256=stream_sha256())
    # idleness by load and CPU only: no process is matched by its command line
    b["idle"] = dict(b["idle"], procs=[])
    if extra_stats:
        b["measure"] = dict(b["measure"], stat_filter_extra=extra_stats)
    b.update(workdir=RUNS, name=name, order="williams", order_seed=SEEDS[run], rounds=ROUNDS,
             rounds_block=ROUNDS, rounds_max=ROUNDS, adaptive=False, comparisons="all_pairs",
             short_run_note="short run: %d fixed rounds in Williams order, run with --allow-short" % ROUNDS)
    return b


def arm(name, settings=None, ev=None, paths=None, shapes=None):
    a = sm.arm(name, settings)
    if ev:
        a["evidence"] = copy.deepcopy(ev)
    if paths:
        a["client"] = {"paths": dict(paths)}
    if shapes:
        a["shapes"] = list(shapes)
    return a


def so_per_response(counter, value, shape=None, tol=0.001, label=None):
    it = {"stat": SO + counter, "scope": "field", "per_request": float(value), "per": PER_SO,
          "label": label or "origin: %s per response %g" % (counter, value)}
    it.update({"tol": tol} if value else {"tol_abs": tol})
    if shape:
        it["shape"] = shape
    return it


def so_responses(tol=0.002):
    return {"stat": SO + "responses", "scope": "field", "per_request": 1.0, "tol": tol, "per": "field:responses_raw",
            "label": "origin: its own response count per request 1.000"}


SO_OK = {"stat": "stream_origin.ok", "scope": "field", "equals": True, "label": "origin counters read before and after the window"}
SO_NO_ERR = [zero(SO + "write_errors", scope="field", label="origin: no failed write"),
             zero(SO + "bad_requests", scope="field", label="origin: no rejected request")]


# ---------------------------------------------------------------- s2a: chunked bodies

S2A_STATS = r"^cluster\.origin\.upstream_cx_http[12]_total$"
S2A_SHAPES = {"b64k": K64, "b1m": M1}
CHUNK = {"cl": 0, "cl-A2": 0, "ch4k": 4096, "ch8k": 8192, "cl8k": 8192, "h2in": 0}


def s2a_path(a, n):
    """Every arm's path has the length of the longest (/chunked?bytes=N&chunk=8192): a `pad` parameter."""
    p = "/chunked?bytes=%d&chunk=%d" % (n, CHUNK[a]) if a.startswith("ch") else "/cl?bytes=%d&chunk=%d" % (n, CHUNK[a])
    want = len("/chunked?bytes=%d&chunk=8192" % n)
    short = want - len(p)
    if short:
        if short < 5:
            raise ValueError("cannot pad %s by %d" % (p, short))
        p += "&pad=" + "x" * (short - 5)
    assert len(p) == want
    return p


def s2a_shapes(r64=4000, r1m=800):
    mk = lambda n, b, r: {"name": n, "path": "/" + n, "route_match": {"prefix": "/c"}, "kind": "proxied",  # noqa: E731
                          "stream": True, "body_bytes": b, "rps": r}
    return [mk("b64k", K64, r64), mk("b1m", M1, r1m)]


def s2a_arms():
    out = []
    for a in ("cl", "cl-A2", "ch4k", "ch8k", "cl8k", "h2in"):
        h2 = a == "h2in"
        st = {"origin_server": "stream_h2", "upstream_http2": True} if h2 else {"origin_server": "stream"}
        ev = [RQ2XX, so_responses(), SO_OK] + SO_NO_ERR
        for sh, n in S2A_SHAPES.items():
            c = CHUNK[a]
            writes = n // c if c else 1
            chunks = writes if a.startswith("ch") else 0
            wire = wire_chunked(n, c) if a.startswith("ch") else wire_cl(n)
            ev.append(warm(0.001 if sh == "b64k" else 0.005) | {"shape": sh})
            ev.append(so_per_response("body_bytes", n, sh))
            ev.append(so_per_response("write_calls", writes, sh))
            ev.append(so_per_response("chunks", chunks, sh))
            if h2:
                # HTTP/2: the body in DATA frames (9 bytes of frame header each, at most 16 KiB of data)
                ev.append({"stat": "cluster.origin.upstream_cx_rx_bytes_total", "per_request": n * 1.001, "tol": 0.005,
                           "shape": sh, "label": "upstream bytes read per request: the body plus HTTP/2 framing (0.5%)"})
            else:
                # 0.2%: requests in flight at the window's edges move this by up to about 0.1%; the arms are
                # told apart by the origin's own chunk and write counts above (exact), not by this item
                ev.append({"stat": "cluster.origin.upstream_cx_rx_bytes_total", "per_request": wire, "tol": 0.002,
                           "shape": sh, "label": "upstream bytes read per request: %d (head, body, chunk framing)" % wire})
        if h2:
            ev += [at_least("cluster.origin.upstream_cx_http2_total", 1, label="HTTP/2 to the origin"),
                   zero("cluster.origin.upstream_cx_http1_total", scope="leg", label="no HTTP/1 connection to the origin"),
                   {"stat": SO + "h2_responses", "scope": "field", "per_request": 1.0, "tol": 0.002, "per": PER_SO,
                    "label": "origin: every response on its HTTP/2 port"}]
        else:
            ev += [at_least("cluster.origin.upstream_cx_http1_total", 1, label="HTTP/1.1 to the origin"),
                   zero("cluster.origin.upstream_cx_http2_total", scope="leg", label="no HTTP/2 connection to the origin"),
                   {"stat": SO + "h1_responses", "scope": "field", "per_request": 1.0, "tol": 0.002, "per": PER_SO,
                    "label": "origin: every response on its HTTP/1.1 port"}]
        out.append(arm(a, st, ev, paths={sh: s2a_path(a, n) for sh, n in S2A_SHAPES.items()}))
    return out


S2A_VARIANTS = {"s2a-chunked": (4000, 800), "s2a-chunked-h64": (2000, 800), "s2a-chunked-h1m": (4000, 400),
                "s2a-chunked-hh": (2000, 400)}


def s2a(name, r64=4000, r1m=800):
    c = base(name, "s2a", stream=True, extra_stats=S2A_STATS)
    c.update(base_arm="cl", arms=s2a_arms(), shapes=s2a_shapes(r64, r1m))
    return c


# ---------------------------------------------------------------- s2b: streamed events

IDLE_OFF = {"idle_timers_off": True, "upstream_http": {"idle_timeout_s": 0}}


def sse_path(events):
    return "/sse?events=%03d&bytes=%d&gap_us=%d" % (events, EVENT_BYTES, GAP_US)


# The client sends at a multiple of its 16 workers, so the planned 2,000 and 200 req/s (40,000 events/s) are
# 2,080 and 208 req/s (41,600 events/s in both shapes); the R3 fallback is 960 and 96 (19,200 events/s).
EV_RATES = {False: (2080, 208), True: (960, 96)}


def s2b_shapes(half=False):
    mk = lambda n, ev, r: {"name": n, "path": "/" + n, "route_match": {"prefix": "/sse"}, "client_path": sse_path(ev),  # noqa: E731
                           "kind": "proxied", "stream": True, "body_bytes": ev * EVENT_BYTES, "rps": r, "events": ev}
    return [mk("ev20", 20, EV_RATES[half][0]), mk("ev200", 200, EV_RATES[half][1])]


def stream_ev(shapes, grpc=False):
    """Evidence of a streamed arm: Envoy's 2xx, the origin's own counts, late events under 0.1%."""
    ev = [RQ2XX, SO_OK] + SO_NO_ERR
    for s in shapes:
        n, sh = s["events"], s["name"]
        # a stream is open for n ms: the origin counts a response at its end, Envoy at its head, so the two
        # counts differ by the streams in flight at the window's edges
        ev.append(dict(so_responses(0.01 if n <= 20 else 0.03), shape=sh))
        ev.append(so_per_response("events", n, sh, label="origin: %d events per response" % n))
        ev.append(so_per_response("write_calls", n, sh, label="origin: one write per event (%d per response)" % n))
        ev.append(so_per_response("body_bytes", n * EVENT_BYTES, sh))
        ev.append({"stat": SO + "late_events", "scope": "field", "max": 0.001, "per": "field:" + SO + "events", "shape": sh,
                   "label": "origin: events sent more than 0.5 ms late under 0.1% of events"})
        ev.append(warm(0.002 if n <= 20 else 0.02) | {"shape": sh})
        if not grpc:
            ev.append({"stat": "cluster.origin.upstream_cx_rx_bytes_total", "per_request": wire_sse(n), "tol": 0.03,
                       "shape": sh, "label": "upstream bytes read per request: %d (head, %d framed events)" % (wire_sse(n), n)})
    return ev


CHO_OFF = {"stat": "common_http_protocol_options", "scope": "config", "equals": {"idle_timeout": "0s"},
           "label": "connection idle timeout 0s wherever it is set (listener and origin cluster)"}
IDLE_OFF_EV = [{"stat": "stream_idle_timeout", "scope": "config", "equals": "0s", "label": "stream idle timeout 0s"},
               CHO_OFF,
               {"stat": "explicit_http_config", "scope": "config", "present": True,
                "label": "the origin cluster carries its own protocol options (upstream idle timeout)"},
               {"stat": "timeout", "scope": "config", "absent": True, "label": "route timeout at its default (not set)"}]
IDLE_DEFAULT_EV = [{"stat": "stream_idle_timeout", "scope": "config", "absent": True, "label": "stream idle timeout at its default"},
                   {"stat": "common_http_protocol_options", "scope": "config", "absent": True,
                    "label": "connection idle timeouts at their defaults"},
                   {"stat": "timeout", "scope": "config", "absent": True, "label": "route timeout at its default (not set)"}]


def s2b_arms(shapes):
    ev = stream_ev(shapes)
    st = {"origin_server": "stream"}
    return [arm("base", st, ev + IDLE_DEFAULT_EV), arm("base-A2", st, ev + IDLE_DEFAULT_EV),
            arm("idle-off", dict(st, **IDLE_OFF), ev + IDLE_OFF_EV)]


def s2b(name, half=False):
    c = base(name, "s2b", stream=True)
    sh = s2b_shapes(half)
    c.update(base_arm="base", arms=s2b_arms(sh), shapes=sh)
    return c


def grpc_cfg(name):
    """g20 / g200: the same events as gRPC messages, HTTP/2 on both sides (count only: syscall legs)."""
    c = base(name, "s2b", stream=True, extra_stats=S2A_STATS)
    c["envoy"]["codec_type"] = "HTTP2"
    c["client"]["extra_args"] = ["--h2", "--prefetch-connections", "--max-pending-requests", "1000"]
    p = lambda ev: "/epl.bench.Bench/Stream?events=%03d&bytes=%d&gap_us=%d" % (ev, EVENT_BYTES, GAP_US)  # noqa: E731
    mk = lambda n, ev, r: {"name": n, "path": "/" + n, "route_match": {"prefix": "/epl.bench.Bench/"},  # noqa: E731
                           "client_path": p(ev), "kind": "proxied", "stream": True, "body_bytes": ev * EVENT_BYTES,
                           "rps": r, "events": ev}
    sh = [mk("g20", 20, EV_RATES[False][0]), mk("g200", 200, EV_RATES[False][1])]
    st = {"origin_server": "stream_h2", "upstream_http2": True}
    ev = stream_ev(sh, grpc=True) + [at_least("cluster.origin.upstream_cx_http2_total", 1, label="HTTP/2 to the origin"),
                                     at_least("http.ingress_http.downstream_cx_http2_total", 16, label="HTTP/2 from the client")]
    c.update(base_arm="base", arms=[arm("base", st, ev), arm("base-A2", st, ev)], shapes=sh)
    return c


# ---------------------------------------------------------------- s2c: buffer limit (nginx origin)

L64 = {"name": "l64", "path": "/l64", "kind": "proxied", "body_bytes": K64, "rps": 2000}
L1M = {"name": "l1m", "path": "/l1m", "kind": "proxied", "body_bytes": M1, "rps": 800}
BUF_KEY = "per_connection_buffer_limit_bytes"


def buf_ev(limit, mx=0.001):
    ev = [RQ2XX, warm(mx)]
    if limit:
        ev.append({"stat": BUF_KEY, "scope": "config", "equals": limit, "label": "buffer limit %d on the listener and the origin cluster" % limit})
    else:
        ev.append({"stat": BUF_KEY, "scope": "config", "absent": True, "label": "buffer limits at their defaults"})
    return ev


def s2c(name):
    c = base(name, "s2c")
    c.update(base_arm="buf-default", shapes=[dict(L64)],
             arms=[arm("buf-default", None, buf_ev(0)), arm("buf-default-A2", None, buf_ev(0)),
                   arm("buf-32k", {"buffer_limit_bytes": 32768}, buf_ev(32768))])
    return c


def buf_mech(name, wrapper):
    """Syscall legs of 3.4, default against limit: 4 KiB on m (16 KB, 5,440 req/s: the published pair), 32 KiB
    on l64, 32 KiB on a 1 MiB body (800 req/s)."""
    c = base(name, "s2c")
    m = sm.shapes({})["m"]
    c.update(base_arm="buf-default", shapes=[m, dict(L64), dict(L1M)],
             arms=[arm("buf-default", None, buf_ev(0, 0.01)),
                   arm("buf-4k", {"buffer_limit_bytes": 4096}, buf_ev(4096, 0.01), shapes=["m"]),
                   arm("buf-32k", {"buffer_limit_bytes": 32768}, buf_ev(32768, 0.01), shapes=["l64", "l1m"])])
    return as_mech(c, name, wrapper)


# ---------------------------------------------------------------- s2d: HTTP/3 at 0 B and 4 KB (G's rig)

CERT = "ecdsa-p256-san"
SNI = "bench.local"
PORT = 10110
LISTENER = "listener.127.0.0.1_%d." % PORT
GUARD = envoy_config.QUIC_TICKET_GUARD
H3_SOCKET = json.dumps({"name": "envoy.transport_sockets.quic", "typed_config": {
    "@type": "type.googleapis.com/envoy.extensions.transport_sockets.quic.v3.QuicUpstreamTransport",
    "upstream_tls_context": {"sni": SNI, "common_tls_context": {"validation_context": {
        "trusted_ca": {"filename": "{cert_dir}/%s.crt" % CERT}}}}}}, separators=(",", ":"))
KA_BASE = ["--prefetch-connections", "--max-pending-requests", "1000"]
H2_EXTRA = ["--protocol", "http2", "--transport-socket", sm.CLIENT_TLS]
H3_EXTRA = ["--protocol", "http3", "--transport-socket", H3_SOCKET]
S2D_STATS = r"listener\..*\.total_bytes_sent$|^http3\.downstream\."
GSO_BYTES = LISTENER + "total_bytes_sent"


def h3_arm(name, h3):
    a = sm.arm(name, {"tls": {"cert": CERT}, "quic": {}, "runtime": {GUARD: False}})
    a["client"] = {"base_args": list(KA_BASE), "extra_args": list(H3_EXTRA if h3 else H2_EXTRA)}
    a["validity"] = {"max_pending_total": 1024}
    if h3:
        # for G (fixed before the run): 16 keep-alive QUIC connections land on workers at random (no balancer), so the
        # 1.2x / 0.5x worker-share gate is replaced by busiest worker <= 0.50 of worker CPU, no floor
        a["validity"].update(max_worker_share_factor=2.0, min_worker_share_factor=None)
    used, unused = ("http3", "http2") if h3 else ("http2", "http3")
    ev = [RQ2XX, warm()] + [zero("kernel_net.d." + k, scope="field") for k in (
        "UdpRcvbufErrors", "UdpSndbufErrors", "UdpInErrors", "ListenOverflows", "ListenDrops")]
    ev += [at_least("http.ingress_http.downstream_cx_%s_total" % used, 16, label="downstream %s connections" % used),
           zero("http.ingress_http.downstream_cx_%s_total" % unused, scope="leg", label="no %s connection" % unused),
           {"stat": GSO_BYTES, "scope": "leg", "min": 0, "label": "GSO batch writer installed"},
           {"stat": LISTENER + "downstream_cx_total", "per_request": 0.0, "tol_abs": 0.001,
            "label": "keep-alive: no new connection in the window"}]
    if not h3:
        ev += [{"stat": LISTENER + "ssl.versions.TLSv1.3", "scope": "leg", "min": 16},
               {"stat": LISTENER + "ssl.versions.TLSv1.2", "scope": "leg", "absent": True},
               {"stat": LISTENER + "ssl.handshake", "per_request": 0.0, "tol_abs": 0.001}]
    a["evidence"] = ev
    return a


def s2d(name, rate=2000):
    c = base(name, "s2d", extra_stats=S2D_STATS)
    c["client"]["extra_args"] = list(KA_BASE)
    c["envoy"]["codec_type"] = "HTTP2"
    c["measure"] = dict(c["measure"], kernel_net=True)
    z0 = {"name": "z0", "path": "/z0", "kind": "proxied", "body_bytes": 0, "rps": rate}
    c.update(base_arm="h2tls", arms=[h3_arm("h2tls", False), h3_arm("h3", True), h3_arm("h3-A2", True)],
             shapes=[z0, dict(sm.shapes({})["s"], rps=rate)])
    return c


# ---------------------------------------------------------------- mechanism legs (non-scored)

def as_mech(c, name, wrapper):
    c.update(name=name, smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1,
             comparisons="base")
    c.pop("short_run_note", None)
    c["measure"] = dict(c["measure"], perf="bash %s/examples/wave7s2/%s" % (HARNESS, wrapper))
    # a profiler runs beside these legs: its CPU time is not Envoy's, and nothing here is scored
    c["validity"] = dict(c.get("validity") or {}, require_perf_unmultiplexed=False)
    return c


def mech(name, src, picks, wrapper, shapes=None):
    """One round, fixed order, of some arms (and shapes) of a scored config, under a perf wrapper."""
    c = copy.deepcopy(src)
    arms = {a["name"]: a for a in c["arms"]}
    c["arms"] = [copy.deepcopy(arms[n]) for n in picks]
    c["base_arm"] = picks[0]
    if shapes:
        c["shapes"] = [x for x in c["shapes"] if x["name"] in shapes]
        for a in c["arms"]:
            a["evidence"] = [it for it in a.get("evidence", []) if envoy_shape_ok(it, shapes)]
            if (a.get("client") or {}).get("paths"):
                a["client"]["paths"] = {k: v for k, v in a["client"]["paths"].items() if k in shapes}
    return as_mech(c, name, wrapper)


def envoy_shape_ok(it, shapes):
    sh = it.get("shape")
    return sh is None or sh in shapes or (isinstance(sh, list) and any(x in shapes for x in sh))


def configs():
    out = {}
    for name, (r64, r1m) in S2A_VARIANTS.items():
        out[name] = s2a(name, r64, r1m)
        out["smoke-" + name] = s2a("smoke-" + name, r64, r1m)
    for name, half in (("s2b-stream", False), ("s2b-stream-half", True)):
        out[name] = s2b(name, half)
        out["smoke-" + name] = s2b("smoke-" + name, half)
    out["s2c-buf"] = s2c("s2c-buf")
    out["smoke-s2c-buf"] = s2c("smoke-s2c-buf")
    out["s2d-h3"] = s2d("s2d-h3")
    out["smoke-s2d-h3"] = s2d("smoke-s2d-h3")
    # the mechanism pipeline's own smoke (two legs of each kind, before any scored leg)
    pre = {"smoke-mech-sys": "perf-sys.sh", "smoke-mech-kcg": "perf-kcg.sh"}
    for k, c in out.items():
        if k.startswith("smoke-"):
            c.update(smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1)
            c.pop("short_run_note", None)
    # mechanism legs follow the rate variant the chain picked (the suffix of the scored config)
    for name in S2A_VARIANTS:
        sfx = name[len("s2a-chunked"):]
        out["mech-sys-chunked" + sfx] = mech("mech-sys-chunked" + sfx, out[name], ["cl", "cl8k", "ch8k"], "perf-sys.sh")
        out["mech-kcg-chunked" + sfx] = mech("mech-kcg-chunked" + sfx, out[name], ["cl8k", "ch8k"], "perf-kcg.sh", ["b1m"])
    for name in ("s2b-stream", "s2b-stream-half"):
        sfx = name[len("s2b-stream"):]
        # the harness wants two arms in every shape: idle-off runs beside base
        out["mech-sys-stream" + sfx] = mech("mech-sys-stream" + sfx, out[name], ["base", "idle-off"], "perf-sys.sh")
        out["mech-kcg-stream" + sfx] = mech("mech-kcg-stream" + sfx, out[name], ["base", "idle-off"], "perf-kcg.sh", ["ev200"])
    for name, wrapper in pre.items():
        out[name] = mech(name, out["s2c-buf"], ["buf-default", "buf-32k"], wrapper)
    out["mech-sys-grpc"] = as_mech(grpc_cfg("mech-sys-grpc"), "mech-sys-grpc", "perf-sys.sh")
    out["mech-sys-buf"] = buf_mech("mech-sys-buf", "perf-sys.sh")
    out["mech-sys-h3"] = mech("mech-sys-h3", out["s2d-h3"], ["h2tls", "h3"], "perf-sys.sh", ["s"])
    out["mech-kcg-h3"] = mech("mech-kcg-h3", out["s2d-h3"], ["h2tls", "h3"], "perf-kcg.sh", ["s"])
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
