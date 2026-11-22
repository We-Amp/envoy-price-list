#!/usr/bin/env python3
"""Track G of wave 4: HTTP/3 against HTTP/2 over TLS per request, and the QUIC session-ticket default.
Config only, on the official v1.40.2 binary (~/epl/bin/envoy-1.40.2, sha256 enforced) in every arm.

    python3 examples/wave4g/make.py [--rate N]

--rate: the request rate of both runs (default 2,000 req/s; the smoke fallback is 1,000).

Every arm runs the same Envoy shape: the published TCP listener (127.0.0.1:10110, TLS with the ECDSA
P-256 certificate whose SAN is bench.local, HTTP/2 codec) and, beside it, an HTTP/3 listener on UDP at
127.0.0.1:10110 (the `quic` setting: same routes, same router, same certificate). The arms differ only
in the client protocol or in one named QUIC setting. Loopback only: nothing listens on another address.

Configs (in configs/):

  g1-proto.json   shape s (GET 4 KB proxied), keep-alive, 4 arms, 8 rounds (two 4-arm Williams squares):
                  h2tls (HTTP/2 over TLS 1.3, base), h3 (HTTP/3, Envoy's default UDP writer choice: the
                  GSO batch writer), h3-A2 (A/A, on HTTP/3: it carries QUIC's random worker placement),
                  h3-nogso (HTTP/3, the plain sendmsg writer)
  g2-resume.json  shape s, HTTP/3 only, a new QUIC connection every 10 requests in the reconnect arms,
                  4 arms, 8 rounds: h3r (v1.40.2 defaults: quic_session_ticket_support off, base),
                  h3r-A2 (A/A), h3r-tk (the guard on, one fixed session-ticket key on the QUIC listener),
                  h3-ka (keep-alive HTTP/3, the per-connection reference)
  smoke-*.json    one round of every arm (order fixed), evidence recorded; smoke-g2 adds h3r-nores
                  (resumption and early data off), the "no resumption" level of the bytes-per-connection
                  reading
"""

import argparse
import copy
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

RUNS = "~/epl/runs/wave4g"
CLIENT = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"  # the box's working client (tracks A-F)
SEEDS = {"g1": 81, "g2": 82, "g2s": 83}
ROUNDS = 8
RATE = 2000
REQS_PER_CONN = 10
CERT = "ecdsa-p256-san"  # SAN bench.local: the HTTP/3 client checks the name even with a CA
SNI = "bench.local"
PORT = 10110
LISTENER = "listener.127.0.0.1_%d." % PORT
GUARD = envoy_config.QUIC_TICKET_GUARD

# The HTTP/3 client socket: trusts the run's listener certificate, SNI bench.local. "{cert_dir}" is
# replaced per leg by the run's certificate directory (leg.sub_cert_dir).
H3_SOCKET = json.dumps({"name": "envoy.transport_sockets.quic", "typed_config": {
    "@type": "type.googleapis.com/envoy.extensions.transport_sockets.quic.v3.QuicUpstreamTransport",
    "upstream_tls_context": {"sni": SNI, "common_tls_context": {"validation_context": {
        "trusted_ca": {"filename": "{cert_dir}/%s.crt" % CERT}}}}}}, separators=(",", ":"))
# keep-alive client of the published HTTP/2 rows (aa-h2): no LRU flag (an HTTP/1 option); the box client's
# --help says --prefetch-connections is HTTP/1 only, so HTTP/2 and HTTP/3 open one connection per client
# worker (16), as in the published HTTP/2 rows
KA_BASE = ["--prefetch-connections", "--max-pending-requests", "1000"]
# reconnect: no prefetch; each connection carries REQS_PER_CONN requests, then the client closes it
RC_BASE = ["--max-pending-requests", "1000"]
H2_EXTRA = ["--protocol", "http2", "--transport-socket", sm.CLIENT_TLS]  # TLS 1.2-1.3, no cert check
H3_EXTRA = ["--protocol", "http3", "--transport-socket", H3_SOCKET]

# stats the evidence reads that the fixed filter leaves out: the GSO batch writer's byte counter (exists
# only when that writer is installed, listener scope) and the HTTP/3 downstream close/reset codes
STAT_EXTRA = r"listener\..*\.total_bytes_sent$|^http3\.downstream\."
GSO_BYTES = LISTENER + "total_bytes_sent"

Z = {"tol_abs": 0}


def zero(stat, scope="window", **kw):
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


def base(name, run, rate):
    b = json.loads(json.dumps(sm.BASE))
    for k in ("floor_from", "stop"):
        b.pop(k)
    b["client"]["binary"] = CLIENT
    b["client"]["extra_args"] = list(KA_BASE)
    b["envoy"]["codec_type"] = "HTTP2"
    b["origin"].update(stub_status=True)
    b["measure"] = dict(b["measure"], stat_filter_extra=STAT_EXTRA, kernel_net=True)
    b.update(workdir=RUNS, name=name, order="williams", order_seed=SEEDS[run], rounds=ROUNDS,
             rounds_block=ROUNDS, rounds_max=ROUNDS, adaptive=False, comparisons="all_pairs",
             short_run_note="short run: %d fixed rounds in Williams order, run with --allow-short"
                            % ROUNDS)
    b["shapes"] = [dict(sm.shapes({})["s"], rps=int(rate))]
    return b


def settings(quic=None, runtime=None):
    """Every arm: TLS listener with the SAN certificate plus the HTTP/3 listener, the guard written out."""
    s = {"tls": {"cert": CERT}, "quic": dict(quic or {}), "runtime": {GUARD: False}}
    if runtime:
        s["runtime"].update(runtime)
    return s


# ---------------------------------------------------------------- evidence

RQ2XX = {"stat": "cluster.origin.upstream_rq_2xx", "per_request": 1.0, "tol": 0.002}
WARM = {"stat": "cluster.origin.upstream_cx_total", "scope": "window", "max": 0.001, "per": "field:responses_raw",
        "label": "warm upstream pool: at most 0.001 new connections per request in the window"}


def ev_kernel():
    """Box-wide UDP and TCP drop counters over the window: none (client and Envoy share the box)."""
    return [zero("kernel_net.d." + k, scope="field")
            for k in ("UdpRcvbufErrors", "UdpSndbufErrors", "UdpInErrors", "ListenOverflows", "ListenDrops")]


def ev_proto(h3):
    used, unused = ("http3", "http2") if h3 else ("http2", "http3")
    # the client opens one HTTP/2 or HTTP/3 connection per client worker (16; --prefetch-connections is
    # HTTP/1 only in this client), in the warm-up and again in the measured run
    return [{"stat": "http.ingress_http.downstream_cx_%s_total" % used, "scope": "leg", "min": 16,
             "label": "downstream %s connections" % used},
            zero("http.ingress_http.downstream_cx_%s_total" % unused, scope="leg", label="no %s connection" % unused)]


def ev_gso(gso):
    """Which UDP writer the HTTP/3 listener installed. The GSO batch writer creates its counter in the
    listener scope when it is built; on the QUIC path QUICHE calls the writer directly, past Envoy's
    writePacket wrapper, so the counter exists but stays 0 (active_quic_listener.cc:138-141 at v1.40.2,
    seen locally). Whether it batched is the local check's sniffer reading (datagrams over the MTU)."""
    if not gso:
        return [{"stat": GSO_BYTES, "scope": "leg", "absent": True, "label": "default writer: no GSO batch writer"}]
    return [{"stat": GSO_BYTES, "scope": "leg", "min": 0, "label": "GSO batch writer installed"}]


def ev_conn(reconnect):
    if reconnect:
        return [{"stat": LISTENER + "downstream_cx_total", "per_request": 1.0 / REQS_PER_CONN, "tol": 0.03,
                 "label": "one new connection per %d requests" % REQS_PER_CONN}]
    return [{"stat": LISTENER + "downstream_cx_total", "per_request": 0.0, "tol_abs": 0.001,
             "label": "keep-alive: no new connection in the window"}]


def ev_tls_tcp():
    # one TLS connection per client worker, warm-up and measured run: 32 at the leg's end
    return [{"stat": LISTENER + "ssl.versions.TLSv1.3", "scope": "leg", "min": 16},
            {"stat": LISTENER + "ssl.versions.TLSv1.2", "scope": "leg", "absent": True},
            {"stat": LISTENER + "ssl.handshake", "per_request": 0.0, "tol_abs": 0.001}]


def arm(name, h3, reconnect=False, quic=None, runtime=None, server_close=False):
    """server_close: the reconnect comes from Envoy, which closes each downstream connection after
    REQS_PER_CONN requests (HCM max_requests_per_connection, GOAWAY on HTTP/3); the client sets no limit.
    Used after the client's own per-connection limit hit a pool assertion on HTTP/3."""
    st = settings(quic, runtime)
    if server_close:
        st["downstream_keepalive"] = {"max_requests": REQS_PER_CONN}
    a = sm.arm(name, st)
    gso = (quic or {}).get("gso", True)
    a["client"] = {"base_args": list(RC_BASE if reconnect else KA_BASE),
                   "extra_args": list(H3_EXTRA if h3 else H2_EXTRA)
                   + (["--max-requests-per-connection", str(REQS_PER_CONN)] if reconnect and not server_close else [])}
    # keep-alive: the 512 start-up handshakes queue requests before the window (bounded at twice the
    # connections); reconnect: the request that opens a connection waits for it
    a["validity"] = {"max_pending_total": "client_cx" if reconnect else 1024}
    if h3 and not reconnect:
        # 16 keep-alive QUIC connections land on workers at random (QUIC takes no connection balancer;
        # the kernel's BPF routing follows the client's random connection ID), so an even 4/4/4/4 is
        # rare: the standard 1.2x / 0.5x worker-share gate is replaced, for these arms only, by busiest
        # worker <= 0.50 of worker CPU and no floor (fixed before the run). The A/A
        # pair is HTTP/3 for this reason: it carries the placement noise.
        a["validity"]["max_worker_share_factor"] = 2.0
        a["validity"]["min_worker_share_factor"] = None
    # reconnect arms: 0.005 (set 2026-11-22, once, after a failed smoke freeze: requests held for a new
    # handshake reach the origin together and the origin pool sometimes grows inside the window; 13 of 15
    # reconnect smoke legs 0-0.0005, 2 at 0.0013-0.0015). Keep-alive arms keep 0.001.
    warm = dict(WARM, max=0.005, label="warm upstream pool (reconnect): at most 0.005 new connections per request"
                " in the window") if reconnect else WARM
    a["evidence"] = ([RQ2XX, warm] + ev_kernel() + ev_proto(h3) + ev_gso(gso) + ev_conn(reconnect)
                     + ([] if h3 else ev_tls_tcp()))
    return a


# ---------------------------------------------------------------- runs

def g1(smoke, rate):
    c = base(("smoke-" if smoke else "") + "g1-proto", "g1", rate)
    arms = [arm("h2tls", False), arm("h3", True), arm("h3-A2", True), arm("h3-nogso", True, quic={"gso": False})]
    c.update(base_arm="h2tls", arms=arms)
    return c


def g2(smoke, rate):
    c = base(("smoke-" if smoke else "") + "g2-resume", "g2", rate)
    tk = {"ticket_keys": True}
    arms = [arm("h3r", True, True), arm("h3r-A2", True, True),
            arm("h3r-tk", True, True, quic=tk, runtime={GUARD: True}),
            arm("h3-ka", True)]
    if smoke:
        # calibration only (never scored): the bytes a server sends on a connection with no resumption
        # and no ticket
        arms.append(arm("h3r-nores", True, True, quic={"resumption": False, "early_data": False}))
    c.update(base_arm="h3r", arms=arms)
    return c


def g2s(smoke, rate):
    """g2 with server-side reconnects: Envoy closes each HTTP/3 connection after 10 requests."""
    c = base(("smoke-" if smoke else "") + "g2s-resume", "g2s", rate)
    tk = {"ticket_keys": True}
    arms = [arm("h3r", True, True, server_close=True), arm("h3r-A2", True, True, server_close=True),
            arm("h3r-tk", True, True, quic=tk, runtime={GUARD: True}, server_close=True),
            arm("h3-ka", True)]
    if smoke:
        arms.append(arm("h3r-nores", True, True, quic={"resumption": False, "early_data": False}, server_close=True))
    c.update(base_arm="h3r", arms=arms)
    return c


def configs(rate=RATE):
    out = {}
    for smoke in (False, True):
        for c in (g1(smoke, rate), g2(smoke, rate), g2s(smoke, rate)):
            if smoke:
                c.update(smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1)
                c.pop("short_run_note", None)
            out[c["name"] + ".json"] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=int, default=RATE)
    a = ap.parse_args()
    if a.rate % 16:
        raise SystemExit("--rate must divide by the 16 client workers")
    os.makedirs(OUT, exist_ok=True)
    for fn, c in sorted(configs(a.rate).items()):
        with open(os.path.join(OUT, fn), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
