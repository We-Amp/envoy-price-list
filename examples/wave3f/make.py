#!/usr/bin/env python3
"""Track F of wave 3: HTTP/2 and gRPC upstreams, nghttp2 against oghttp2, and the mTLS hop split. Config
only, on the official v1.40.2 binary (~/epl/bin/envoy-1.40.2, sha256 enforced) in every arm.

    python3 examples/wave3f/make.py [--no-body-file]

--no-body-file: the client cannot send a file as the request body (no --request-body-file): the gRPC
shape sends 66 bytes of 'a' instead (--request-body-size) and the grpc_stats arm is left out, because
that filter parses the length prefix of every request message.

Configs (in configs/):

  f1-upstream.json  shape s (HTTP/1.1 client, GET 4 KB proxied, 5,200 req/s); the origin cluster
                    speaks HTTP/1.1 (h1, and h1-A2: the A/A), HTTP/2 cleartext with nghttp2 (h2c) or
                    oghttp2 (h2c-og, the runtime key), TLS + HTTP/1.1 (tls-h1) or TLS + HTTP/2
                    (tls-h2); 6 arms, 6 rounds, one 6-arm Williams square
  f2-grpc.json      shape g (HTTP/2 client, unary gRPC POST: 66-byte request, 4,096-byte response
                    plus the grpc-status trailer, 5,200 req/s), h2c upstream to the origin's gRPC
                    responder: router only (grpc, and grpc-A2), grpc_stats with per-method stats
                    (grpc-stats), oghttp2 on both sides (grpc-og); 4 arms, 8 rounds (two squares)
  f3-mtls.json      shape s through one hop or two (hop B on CPUs 4-7), one upstream pool per
                    downstream connection on every hop (the evened second-hop device): one-ppd,
                    pair (plaintext between the hops; the published +99.6% chain), pair-A2,
                    pair-mtls (ECDSA P-256 mTLS between the hops, client certificate required,
                    SANs checked both ways); primary metric cycles of both hops per request;
                    4 arms, 8 rounds
  smoke-*.json      one round of every arm (order fixed), evidence recorded

Every oghttp2-capable arm (F1, F2) carries the same layered_runtime static layer with the oghttp2 key
written out, false or true, so the runtime structure is the same in every arm.
"""

import argparse
import copy
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "configs")
ROOT = os.path.dirname(os.path.dirname(HERE))
SM = os.path.join(ROOT, "examples", "settings-matrix")
sys.path.insert(0, SM)
sys.path.insert(0, ROOT)
import make as sm  # noqa: E402
from epl import envoy_config  # noqa: E402

RUNS = "~/epl/runs/wave3f"
CLIENT = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"  # the box's working client (tracks A-C, W2)
SEEDS = {"f1": 71, "f2": 72, "f3": 73}
ROUNDS = {"f1": 6, "f2": 8, "f3": 8}
H2C_PORT, TLS_PORT = 8096, 8097
ORIGIN_CERT = "ecdsa-p256-san"     # the origin's TLS server and hop B: SAN bench.local
CLIENT_CERT = "ecdsa-p256-client"  # hop A's client certificate: SAN client.bench.local
SNI = "bench.local"
HOP2_PORT = 10120
OG = envoy_config.OGHTTP2_KEY
GRPC_PATH = "/epl.bench.Bench/Unary"
GRPC_REQ_BYTES = 66
GRPC_REQ_FILE = "examples/wave3f/grpc-unary-request.bin"
GRPC_STAT = "cluster.origin.grpc.epl.bench.Bench.Unary."
# the stats the evidence reads that the fixed filter leaves out (cluster TLS, protocol and codec counters,
# grpc_stats, the downstream codec counters)
STAT_EXTRA = (r"cluster\.origin\.(ssl\.(handshake|connection_error|session_reused|fail_verify_san|"
              r"fail_verify_error|versions\.|ciphers\.|curves\.)|upstream_cx_http[123]_total|"
              r"http2\.(nghttp2|oghttp2)_upstream_connections|grpc\.)|"
              r"^http2\.(nghttp2|oghttp2)_downstream_connections")

Z = {"tol_abs": 0}
ONE = {"per_request": 1.0, "tol": 0.002}


def zero(stat, scope="window", **kw):
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


def at_least(stat, n, scope="leg", **kw):
    return dict({"stat": stat, "scope": scope, "min": n}, **kw)


def none_of(stat, scope="leg", **kw):
    """A counter that exists and stayed at 0 over the leg (Envoy creates it with its family: the
    cluster's protocol counters, both codec counters with the first HTTP/2 connection, the TLS
    counters with the TLS context)."""
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


def request_body():
    """The gRPC request: one 66-byte length-prefixed message, kept in the harness tree."""
    b = envoy_config.grpc_frame(GRPC_REQ_BYTES)
    p = os.path.join(ROOT, GRPC_REQ_FILE)
    if not os.path.exists(p) or open(p, "rb").read() != b:
        with open(p, "wb") as f:
            f.write(b)
    return hashlib.sha256(b).hexdigest()


def base(name, run):
    b = json.loads(json.dumps(sm.BASE))
    b.pop("floor_from")
    b.pop("stop")
    b["client"]["binary"] = CLIENT
    b["origin"].update(h2c_port=H2C_PORT, tls_port=TLS_PORT, tls_cert=ORIGIN_CERT, stub_status=True)
    b["measure"] = dict(b["measure"], stat_filter_extra=STAT_EXTRA)
    b.update(workdir=RUNS, name=name, order="williams", order_seed=SEEDS[run], rounds=ROUNDS[run],
             rounds_block=ROUNDS[run], rounds_max=ROUNDS[run], adaptive=False, comparisons="all_pairs",
             short_run_note="short run: %d fixed rounds in Williams order, run with --allow-short"
                            % ROUNDS[run])
    return b


def arm(name, settings=None, ev=None):
    a = sm.arm(name, settings)
    if ev:
        a["evidence"] = copy.deepcopy(ev)
    return a


# ---------------------------------------------------------------- evidence

# new upstream connections in the window: warm pools (the smoke tells; a longer warm-up is the fix)
WARM = {"stat": "cluster.origin.upstream_cx_total", "scope": "window", "max": 0.001, "per": "field:responses_raw",
        "label": "warm upstream pool: at most 0.001 new connections per request in the window"}
RQ2XX = dict({"stat": "cluster.origin.upstream_rq_2xx"}, **ONE)


def ev_upstream(proto, codec=None, tls=False):
    ev = [RQ2XX, WARM]
    if proto == "h1":
        ev += [at_least("cluster.origin.upstream_cx_http1_total", 1),
               none_of("cluster.origin.upstream_cx_http2_total")]
    else:
        ev += [at_least("cluster.origin.upstream_cx_http2_total", 1),
               none_of("cluster.origin.upstream_cx_http1_total")]
        used, unused = ("oghttp2", "nghttp2") if codec == "og" else ("nghttp2", "oghttp2")
        ev += [at_least("cluster.origin.http2.%s_upstream_connections" % used, 1,
                        label="upstream codec %s" % used),
               none_of("cluster.origin.http2.%s_upstream_connections" % unused, label="no %s upstream" % unused)]
    if tls:
        # Envoy's client default is TLS 1.2 at most (context_config_impl.cc:365 at v1.40.2): what an
        # operator gets without tls_params, and what these arms run
        ev += [at_least("cluster.origin.ssl.handshake", 1, label="upstream TLS handshakes"),
               at_least("cluster.origin.ssl.versions.TLSv1.2", 1, label="upstream TLS 1.2 (the client default)"),
               none_of("cluster.origin.ssl.connection_error"),
               dict(WARM, stat="cluster.origin.ssl.handshake",
                    label="warm: at most 0.001 upstream handshakes per request in the window")]
    else:
        ev += [{"stat": "cluster.origin.ssl.handshake", "scope": "leg", "absent": True, "label": "no upstream TLS"}]
    return ev


def ev_downstream_h2(codec):
    used, unused = ("oghttp2", "nghttp2") if codec == "og" else ("nghttp2", "oghttp2")
    return [at_least("http2.%s_downstream_connections" % used, 1, label="downstream codec %s" % used),
            none_of("http2.%s_downstream_connections" % unused, label="no %s downstream" % unused)]


# ---------------------------------------------------------------- F1

def f1(smoke):
    c = base(("smoke-" if smoke else "") + "f1-upstream", "f1")
    rt = lambda og=False: {"runtime": {OG: og}}  # noqa: E731
    tls = lambda alpn: {"ca": ORIGIN_CERT, "sni": SNI, "san": SNI, "alpn": [alpn]}  # noqa: E731
    h2 = {"upstream_http2": True}
    arms = [
        arm("h1", rt(), ev_upstream("h1")),
        arm("h1-A2", rt(), ev_upstream("h1")),
        arm("h2c", dict(rt(), origin_server="h2c", **h2), ev_upstream("h2")),
        arm("h2c-og", dict(rt(True), origin_server="h2c", **h2), ev_upstream("h2", "og")),
        arm("tls-h1", dict(rt(), origin_server="tls", upstream_tls=tls("http/1.1")), ev_upstream("h1", tls=True)),
        arm("tls-h2", dict(rt(), origin_server="tls", upstream_tls=tls("h2"), **h2), ev_upstream("h2", tls=True)),
    ]
    c.update(base_arm="h1", arms=arms, shapes=[sm.shapes({})["s"]])
    return c


# ---------------------------------------------------------------- F2

def grpc_shape(body_file):
    s = {"name": "g", "path": GRPC_PATH, "kind": "proxied", "grpc": True, "body_bytes": 4096, "rps": 5200,
         "client_extra_args": ["--request-method", "POST", "--request-header", "content-type:application/grpc",
                               "--request-header", "te:trailers"]}
    if body_file:
        s.update(request_body_file=GRPC_REQ_FILE, request_body_sha256=request_body())
    else:
        s["client_extra_args"] += ["--request-body-size", str(GRPC_REQ_BYTES)]
    return s


def f2(smoke, body_file=True):
    c = base(("smoke-" if smoke else "") + "f2-grpc", "f2")
    c["envoy"]["codec_type"] = "HTTP2"
    # the HTTP/2 client of the published aa-h2 / hpack rows
    c["client"]["extra_args"] = ["--h2", "--prefetch-connections", "--max-pending-requests", "1000"]
    up = {"upstream_http2": True, "origin_server": "h2c"}
    no_stats = [{"stat": "cluster.origin.grpc.*", "scope": "leg", "absent": True, "label": "no grpc_stats"}]
    ev = lambda codec=None: ev_upstream("h2", codec) + ev_downstream_h2(codec)  # noqa: E731
    stats_ev = [dict({"stat": GRPC_STAT + "success"}, **ONE), dict({"stat": GRPC_STAT + "total"}, **ONE),
                dict({"stat": GRPC_STAT + "request_message_count"}, **ONE),
                dict({"stat": GRPC_STAT + "response_message_count"}, **ONE),
                {"stat": GRPC_STAT + "failure", "scope": "leg", "absent": True, "label": "no gRPC failure"}]
    arms = [arm("grpc", dict(up, runtime={OG: False}), ev() + no_stats),
            arm("grpc-A2", dict(up, runtime={OG: False}), ev() + no_stats)]
    if body_file:
        arms.append(arm("grpc-stats", dict(up, runtime={OG: False}, grpc_stats={"stats_for_all_methods": True}),
                        ev() + stats_ev))
    arms.append(arm("grpc-og", dict(up, runtime={OG: True}), ev("og") + no_stats))
    c.update(base_arm="grpc", arms=arms, shapes=[grpc_shape(body_file)])
    if len(arms) % 2:  # 3 arms (no body file): the odd Williams design has period 6
        c.update(rounds=6, rounds_block=6, rounds_max=6)
    return c


# ---------------------------------------------------------------- F3

H2_LISTENER = "listener.127.0.0.1_%d." % HOP2_PORT


def f3(smoke):
    c = base(("smoke-" if smoke else "") + "f3-mtls", "f3")
    c["cpus"] = dict(c["cpus"], hop2="4-7")
    c["primary_metric"] = "cycles_total_all"
    ppd = {"upstream_pool_per_downstream": True}
    plain_ev = [RQ2XX, WARM, {"stat": "cluster.origin.ssl.handshake", "scope": "leg", "absent": True,
                        "label": "no TLS between the hops"}]
    pair_ev = plain_ev + [{"stat": H2_LISTENER + "ssl.handshake", "scope": "hop2_leg", "absent": True,
                           "label": "hop B: plaintext listener"},
                          dict({"stat": "http.ingress_http.downstream_rq_2xx", "scope": "hop2_window"}, **ONE)]
    mtls_ev = [RQ2XX, WARM,
               at_least("cluster.origin.ssl.handshake", 512, label="hop A: one TLS connection per client connection"),
               none_of("cluster.origin.ssl.connection_error"), none_of("cluster.origin.ssl.fail_verify_san"),
               none_of("cluster.origin.ssl.fail_verify_error"),
               zero("cluster.origin.ssl.handshake", label="hop A: no handshake in the window (warm)"),
               dict({"stat": "http.ingress_http.downstream_rq_2xx", "scope": "hop2_window"}, **ONE),
               at_least(H2_LISTENER + "ssl.handshake", 512, scope="hop2_leg", label="hop B: TLS handshakes"),
               zero(H2_LISTENER + "ssl.handshake", scope="hop2_window", label="hop B: no handshake in the window"),
               zero(H2_LISTENER + "ssl.connection_error", scope="hop2_window"),
               zero(H2_LISTENER + "ssl.no_certificate", scope="hop2_window"),
               at_least(H2_LISTENER + "ssl.versions.TLSv1.2", 512, scope="hop2_leg",
                        label="hop B: TLS 1.2 (hop A's client default)")]
    utls = {"ca": ORIGIN_CERT, "sni": SNI, "san": SNI, "cert": CLIENT_CERT}
    hop_b_tls = {"cert": ORIGIN_CERT, "client_ca": CLIENT_CERT, "client_san": "client.bench.local"}
    arms = [arm("one-ppd", dict(ppd), plain_ev),
            arm("pair", dict(ppd, two_hop=True, hop2_settings=dict(ppd)), pair_ev),
            arm("pair-A2", dict(ppd, two_hop=True, hop2_settings=dict(ppd)), pair_ev),
            arm("pair-mtls", dict(ppd, two_hop=True, upstream_tls=utls, hop2_settings=dict(ppd, tls=hop_b_tls)),
                mtls_ev)]
    c.update(base_arm="pair", arms=arms, shapes=[sm.shapes({})["s"]])
    return c


def configs(body_file=True):
    out = {}
    for smoke in (False, True):
        for c in (f1(smoke), f2(smoke, body_file), f3(smoke)):
            if smoke:
                c.update(smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1)
                c.pop("short_run_note", None)
            out[c["name"] + ".json"] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-body-file", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for fn, c in sorted(configs(not a.no_body_file).items()):
        with open(os.path.join(OUT, fn), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
