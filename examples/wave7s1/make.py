#!/usr/bin/env python3
"""Wave 7, session S1: the proxy pair with an L4 second hop, a TCP relay of small messages, and Unix
sockets for the hops. Config only, on the official v1.40.2 binary (~/epl/bin/envoy-1.40.2, sha256 enforced)
in every arm and on both hops.

    python3 examples/wave7s1/make.py

Configs (in configs/):

  s1a-hop.json      shape s (HTTP/1.1 GET, 4 KB proxied, 5,200 req/s), one upstream pool per downstream
                    connection on every HTTP hop; primary metric: the cycles of both hops per request.
                    one-ppd (one proxy), pair (two HTTP hops; base), pair-A2 (A/A), pair-l4 (hop B relays
                    with tcp_proxy), pair-mtls (ECDSA P-256 mTLS between the hops), pair-mtls-l4 (the same
                    mTLS on hop B's listener, then tcp_proxy), pair-uds (the hop between the proxies is a
                    Unix socket), one-uds (one proxy, the origin hop is a Unix socket);
                    8 arms, 8 rounds (one Williams square), seed 701
  s1a-hop-no-pair-uds.json, s1a-hop-no-one-uds.json, s1a-hop-no-uds.json
                    the same run with a Unix-socket arm that failed its smoke replaced by a second copy of
                    one-ppd (one-ppd-B2, one-ppd-B3), so the run keeps 8 arms and 8 rounds
  s1b-relay.json    one proxy; the origin answers from memory in one write. Shapes p64 (64-byte body) and
                    p1k (1,024-byte body), both 8,000 req/s (one request = two relayed messages).
                    tcp (tcp_proxy, defaults; base), tcp-A2 (A/A), tcp-noidle (idle_timeout 0s), http (the
                    baseline HTTP proxy on the same traffic); responses counted at the origin in every arm;
                    the http arm has one upstream pool per downstream connection, so every arm holds 512
                    upstream connections; 4 arms x 2 shapes, 8 rounds, seed 702
  s1b-relay-half.json  the same at 4,000 req/s (used only when the 8,000 smoke fails a load gate)
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

RUNS = "~/epl/runs/wave7s1"
HARNESS = "~/epl/harness-wave7s1"
CLIENT = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"  # Nighthawk 0.3.0, md5 310df412
SEEDS = {"s1a": 701, "s1b": 702}
ROUNDS = 8
ORIGIN_CERT = "ecdsa-p256-san"     # hop B's certificate: SAN bench.local
CLIENT_CERT = "ecdsa-p256-client"  # hop A's client certificate: SAN client.bench.local
SNI = "bench.local"
HOP2_PORT = 10120
H2_LISTENER = "listener.127.0.0.1_%d." % HOP2_PORT
RELAY = "tcp.relay."
# stats the evidence reads that the fixed filter leaves out: the tcp_proxy counters and the cluster TLS ones
STAT_EXTRA = (r"^tcp\.relay\.|cluster\.origin\.ssl\.(handshake|connection_error|fail_verify_san|"
              r"fail_verify_error|versions\.)")

Z = {"tol_abs": 0}
ONE = {"per_request": 1.0, "tol": 0.002}
WARM = {"stat": "cluster.origin.upstream_cx_total", "scope": "window", "max": 0.001, "per": "field:responses_raw",
        "label": "warm upstream pool: at most 0.001 new connections per request in the window"}
RQ2XX = dict({"stat": "cluster.origin.upstream_rq_2xx"}, **ONE)
NO_TLS = {"stat": "cluster.origin.ssl.handshake", "scope": "leg", "absent": True, "label": "no TLS to the upstream"}


# Plan review, S1 item 2: proof that requests succeeded where Envoy sees no HTTP status, and that the
# upstream connections are one per client connection and none comes or goes in the window
CLIENT_2XX = {"stat": "client_rate_2xx", "scope": "field", "min": 0.99, "max": 1.01, "per": "field:target_rps",
              "label": "client: 2xx responses per second within 1% of the target rate"}
UP_512 = {"stat": "cluster.origin.upstream_cx_total", "scope": "leg", "min": 512,
          "label": "upstream connections opened over the leg: at least 512"}
# (an HTTP hop with one pool per downstream connection also still holds the warm-up client's 512: F3 read 1024)
UP_512_NOW = {"stat": "conn_upstream.conns", "scope": "field", "min": 512, "max": 1024,
              "label": "established TCP connections to the origin at the end of the window: 512 to 1024"}


def zero(stat, scope="window", **kw):
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


def at_least(stat, n, scope="leg", **kw):
    return dict({"stat": stat, "scope": scope, "min": n}, **kw)


def absent(stat, scope="leg", **kw):
    return dict({"stat": stat, "scope": scope, "absent": True}, **kw)


def base(name, run):
    b = json.loads(json.dumps(sm.BASE))
    b.pop("floor_from")
    b.pop("stop")
    b["client"]["binary"] = CLIENT
    b["origin"].update(stub_status=True)
    # idleness by load and CPU only: no process is matched by its command line
    b["idle"] = dict(b["idle"], procs=[])
    b["measure"] = dict(b["measure"], stat_filter_extra=STAT_EXTRA)
    b.update(workdir=RUNS, name=name, order="williams", order_seed=SEEDS[run], rounds=ROUNDS,
             rounds_block=ROUNDS, rounds_max=ROUNDS, adaptive=False, comparisons="all_pairs",
             short_run_note="short run: %d fixed rounds in Williams order, run with --allow-short" % ROUNDS)
    return b


def arm(name, settings=None, ev=None):
    a = sm.arm(name, settings)
    if ev:
        a["evidence"] = copy.deepcopy(ev)
    return a


# ---------------------------------------------------------------- s1a: the pair

PPD = {"upstream_pool_per_downstream": True}
HOP2_HTTP_2XX = dict({"stat": "http.ingress_http.downstream_rq_2xx", "scope": "hop2_window"}, **ONE)
# hop B as a relay: one relayed connection per hop A connection, none new in the window, no HTTP at all
HOP2_L4 = [at_least(RELAY + "downstream_cx_total", 512, scope="hop2_leg",
                    label="hop B: tcp_proxy carried the connections (at least 512 over the leg)"),
           zero(RELAY + "downstream_cx_total", scope="hop2_window", label="hop B: no new relayed connection in the window"),
           zero("cluster.origin.upstream_cx_total", scope="hop2_window",
                label="hop B: no new connection to the origin in the window"),
           zero("cluster.origin.upstream_cx_destroy", scope="hop2_window",
                label="hop B: no connection to the origin destroyed in the window"),
           at_least("cluster.origin.upstream_cx_total", 512, scope="hop2_leg",
                    label="hop B: at least 512 connections to the origin over the leg"),
           CLIENT_2XX, UP_512_NOW,
           absent("http.ingress_http.*", scope="hop2_leg", label="hop B: no HTTP connection manager stats")]
HOP2_TCP_LISTENER_GONE = absent(H2_LISTENER + "*", scope="hop2_leg", label="hop B: no TCP listener on %d" % HOP2_PORT)
PIPE = {"stat": "pipe", "scope": "config", "present": True, "label": "a pipe (Unix socket) address in the config"}
NO_PIPE = {"stat": "pipe", "scope": "config", "absent": True, "label": "no pipe address in the config"}


def mtls_ev(l4):
    ev = [RQ2XX, WARM,
          at_least("cluster.origin.ssl.handshake", 512, label="hop A: one TLS connection per client connection"),
          zero("cluster.origin.ssl.connection_error", scope="leg"), zero("cluster.origin.ssl.fail_verify_san", scope="leg"),
          zero("cluster.origin.ssl.fail_verify_error", scope="leg"),
          zero("cluster.origin.ssl.handshake", label="hop A: no handshake in the window (warm)"),
          at_least(H2_LISTENER + "ssl.handshake", 512, scope="hop2_leg", label="hop B: TLS handshakes"),
          zero(H2_LISTENER + "ssl.handshake", scope="hop2_window", label="hop B: no handshake in the window"),
          zero(H2_LISTENER + "ssl.connection_error", scope="hop2_window"),
          zero(H2_LISTENER + "ssl.no_certificate", scope="hop2_window"),
          at_least(H2_LISTENER + "ssl.versions.TLSv1.2", 512, scope="hop2_leg",
                   label="hop B: TLS 1.2 (hop A's client default)"), NO_PIPE]
    return ev + (HOP2_L4 if l4 else [HOP2_HTTP_2XX])


def s1a_arms():
    plain = [RQ2XX, WARM, NO_TLS]
    pair_ev = plain + [absent(H2_LISTENER + "ssl.handshake", scope="hop2_leg", label="hop B: plaintext listener"),
                       HOP2_HTTP_2XX, NO_PIPE,
                       at_least(H2_LISTENER + "downstream_cx_total", 512, scope="hop2_leg",
                                label="hop B: connections on its TCP port")]
    utls = {"ca": ORIGIN_CERT, "sni": SNI, "san": SNI, "cert": CLIENT_CERT}
    hop_b_tls = {"cert": ORIGIN_CERT, "client_ca": CLIENT_CERT, "client_san": "client.bench.local"}
    two = dict(PPD, two_hop=True)
    one = lambda n: arm(n, dict(PPD), plain + [NO_PIPE])  # noqa: E731
    arms = {
        "one-ppd": one("one-ppd"),
        "pair": arm("pair", dict(two, hop2_settings=dict(PPD)), pair_ev),
        "pair-A2": arm("pair-A2", dict(two, hop2_settings=dict(PPD)), pair_ev),
        "pair-l4": arm("pair-l4", dict(two, hop2_settings={"tcp_proxy": True}),
                       plain + HOP2_L4 + [NO_PIPE, at_least(H2_LISTENER + "downstream_cx_total", 512, scope="hop2_leg")]),
        "pair-mtls": arm("pair-mtls", dict(two, upstream_tls=utls, hop2_settings=dict(PPD, tls=hop_b_tls)),
                         mtls_ev(False)),
        "pair-mtls-l4": arm("pair-mtls-l4", dict(two, upstream_tls=utls,
                                                 hop2_settings={"tcp_proxy": True, "tls": hop_b_tls}), mtls_ev(True)),
        "pair-uds": arm("pair-uds", dict(two, hop_uds=True, hop2_settings=dict(PPD)),
                        plain + [HOP2_HTTP_2XX, PIPE, HOP2_TCP_LISTENER_GONE,
                                 at_least("http.ingress_http.downstream_cx_total", 512, scope="hop2_leg",
                                          label="hop B: connections arrived (on the Unix socket)"),
                                 {"stat": "conn_hop2_downstream.conns", "scope": "field", "equals": 0, "tol_abs": 0,
                                  "label": "0 TCP connections on hop B's port"}]),
        "one-uds": arm("one-uds", dict(PPD, origin_uds=True),
                       plain + [PIPE, {"stat": "conn_upstream.conns", "scope": "field", "equals": 0, "tol_abs": 0,
                                       "label": "0 TCP connections on the origin's port"}]),
        "one-ppd-B2": one("one-ppd-B2"),
        "one-ppd-B3": one("one-ppd-B3"),
    }
    return arms


S1A_FULL = ["one-ppd", "pair", "pair-A2", "pair-l4", "pair-mtls", "pair-mtls-l4", "pair-uds", "one-uds"]
# a Unix-socket arm that fails its smoke is replaced by a second copy of one-ppd (plan rule R7)
S1A_VARIANTS = {
    "s1a-hop": {},
    "s1a-hop-no-pair-uds": {"pair-uds": "one-ppd-B2"},
    "s1a-hop-no-one-uds": {"one-uds": "one-ppd-B3"},
    "s1a-hop-no-uds": {"pair-uds": "one-ppd-B2", "one-uds": "one-ppd-B3"},
}


def s1a(name, names):
    c = base(name, "s1a")
    c["cpus"] = dict(c["cpus"], hop2="4-7")
    c["primary_metric"] = "cycles_total_all"
    c["origin"].update(uds=True)
    A = s1a_arms()
    c.update(base_arm="pair", arms=[A[n] for n in names], shapes=[sm.shapes({})["s"]])
    return c


# ---------------------------------------------------------------- s1b: the relay

def relay_shapes(rps):
    return [{"name": "p64", "path": "/p64", "kind": "proxied", "origin_inline": True, "body_bytes": 64, "rps": rps},
            {"name": "p1k", "path": "/p1k", "kind": "proxied", "origin_inline": True, "body_bytes": 1024, "rps": rps}]


UPSTREAM_1TO1 = [CLIENT_2XX, UP_512, UP_512_NOW,
                 zero("cluster.origin.upstream_cx_total", label="no upstream connection created in the window"),
                 zero("cluster.origin.upstream_cx_destroy", label="no upstream connection destroyed in the window")]


def s1b_arms():
    self_ref = lambda stat, what: {"stat": RELAY + stat, "scope": "window", "ref": {"arm": "self"}, "tol": 0.01,  # noqa: E731
                                   "label": "%s bytes per request within 1%% of this arm's smoke" % what}
    tcp_ev = [at_least(RELAY + "downstream_cx_total", 512, label="tcp_proxy carried the client's connections"),
              self_ref("downstream_cx_rx_bytes_total", "request-side"),
              self_ref("downstream_cx_tx_bytes_total", "response-side"),
              absent("http.ingress_http.*", label="no HTTP connection manager stats"), WARM] + UPSTREAM_1TO1
    idle = lambda v: {"stat": "idle_timeout", "scope": "config", "equals": v, "label": "tcp_proxy idle_timeout %s" % v}  # noqa: E731
    no_idle = {"stat": "idle_timeout", "scope": "config", "absent": True, "label": "tcp_proxy idle_timeout at its default (1 h)"}
    return [arm("tcp", {"tcp_proxy": True}, tcp_ev + [no_idle]),
            arm("tcp-A2", {"tcp_proxy": True}, tcp_ev + [no_idle]),
            arm("tcp-noidle", {"tcp_proxy": {"idle_timeout_s": 0}}, tcp_ev + [idle("0s")]),
            # Plan review, S1 item 1: one upstream connection per client connection, as the tcp arms have
            arm("http", dict(PPD), [RQ2XX, WARM, absent(RELAY + "*", label="no tcp_proxy stats")] + UPSTREAM_1TO1)]


def s1b(name, rps=8000):
    c = base(name, "s1b")
    c["measure"] = dict(c["measure"], responses_from="origin")
    c.update(base_arm="tcp", arms=s1b_arms(), shapes=relay_shapes(rps))
    return c


# ---------------------------------------------------------------- mechanism legs (non-scored)

def mech(name, src, picks, wrapper):
    """One round, fixed order, of some (arm, shapes) cells of a scored config, under a perf wrapper."""
    c = copy.deepcopy(src)
    arms = {a["name"]: a for a in c["arms"]}
    out = []
    for an, shapes in picks:
        a = copy.deepcopy(arms[an])
        if shapes is not None:
            a["shapes"] = list(shapes)
        out.append(a)
    c.update(name=name, arms=out, base_arm=out[0]["name"], smoke=True, evidence_mode="record", order="fixed",
             rounds=1, rounds_block=1, rounds_max=1, comparisons="base")
    c.pop("short_run_note", None)
    c["measure"] = dict(c["measure"], perf="bash %s/examples/wave7s1/%s" % (HARNESS, wrapper))
    # a profiler runs beside these legs: its CPU time is not Envoy's, and nothing here is scored
    c["validity"] = dict(c.get("validity") or {}, require_perf_unmultiplexed=False)
    return c


def configs():
    out = {}
    for name, swap in S1A_VARIANTS.items():
        out[name] = s1a(name, [swap.get(n, n) for n in S1A_FULL])
    out["smoke-s1a-hop"] = s1a("smoke-s1a-hop", S1A_FULL + ["one-ppd-B2", "one-ppd-B3"])
    for name, rps in (("s1b-relay", 8000), ("s1b-relay-half", 4000)):
        out[name] = s1b(name, rps)
        out["smoke-" + name] = s1b("smoke-" + name, rps)
    for k, c in out.items():
        if k.startswith("smoke-"):
            c.update(smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1)
            c.pop("short_run_note", None)
    relay, hop = out["s1b-relay"], out["s1a-hop"]
    for rname, src in (("relay", relay), ("relay-half", out["s1b-relay-half"])):
        # the harness wants two arms in every shape: http runs beside tcp in each (one leg more than planned)
        out["mech-sys-" + rname] = mech("mech-sys-" + rname, src, [("tcp", None), ("http", None)], "perf-sys.sh")
        k = mech("mech-kcg-" + rname, src, [("tcp", None), ("http", None)], "perf-kcg.sh")
        k["shapes"] = [x for x in k["shapes"] if x["name"] == "p64"]
        out["mech-kcg-" + rname] = k
    out["mech-sys-hop"] = mech("mech-sys-hop", hop, [("pair", None), ("pair-l4", None)], "perf-sys.sh")
    out["mech-kcg-hop"] = mech("mech-kcg-hop", hop, [("pair", None), ("pair-l4", None)], "perf-kcg.sh")
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
