#!/usr/bin/env python3
"""Wave 8, session W8-2: the HTTP/3 receive path. One patched binary (bins.json: w8-A = v1.40.2 + the chunked
HTTP/1 body patch + the two UDP receive commits, each behind a runtime guard) against the official v1.40.2
binary, on G's rig (TLS listener plus HTTP/3 listener, 16 client connections, nginx origin, 4 KB proxied).

    python3 examples/wave8w2/make.py

Arms (six in every scored run; the guards sit in the bootstrap's static runtime layer):
  h2tls            official v1.40.2, HTTP/2 over TLS: the anchor (no line on s-hi; kept so six arms balance)
  h3-official      official v1.40.2, HTTP/3, no runtime layer
  h3-official-A2   the same (the same-build check of the shape)
  h3-off           w8-A, both UDP guards false: the build control (old read loop in the rebuilt binary)
  h3-stop-on       w8-A, udp_stop_reading_on_short_recvmmsg true, udp_recvmmsg_reuse_buffers false (commit 1)
  h3-both-on       w8-A, both UDP guards true (commits 1 and 2)
  h3-reuse-on      w8-A, stop false, reuse true (commit 2 alone): ONLY in the traced smoke on shape s, so that
                   every guard combination of the build record's arm table is exercised once. Not scored.
The chunked guard (http1_zero_copy_body_fragments) is written explicitly TRUE, the same in every w8-A arm (the
a decision for this session, fixed before data: left at its default, set explicitly; plan 4.1 wrote false). It acts in the
HTTP/1 codec, here the origin side; the origin answers with a content-length, so the fragment path is idle.

Scored runs (Williams order, six rounds = one square each):
  s-1.json, s-2.json   shape s: 4 KB proxied over HTTP/3, 2,000 req/s, 16 connections. Seeds 821 and 823; the
                       two squares are pooled as rounds 1-6 and 7-12 (run w8-2a of the plan)
  shi.json             shape s-hi: the same request at 6,000 req/s. Seed 822 (run w8-2b)
  shi-half.json        the same at 3,008 req/s (rule R3; the client needs a multiple of its 16 workers: used when a load gate fails in the smoke at 6,000)
  smoke-s, smoke-shi, smoke-shi-half   one round of the six arms (order fixed), evidence recorded
Mechanism legs (non-scored; one round, order fixed):
  mech-sys-s           tracepoint counts (perf-sys.sh) on h2tls and the five HTTP/3 arms, shape s: THE GATE
  mech-sys-shi[-half]  the same on the four HTTP/3 arms of the scored runs, shape s-hi
  mech-kcg-s           call-graph profile (perf-kcg.sh) of h3-off, h3-stop-on, h3-both-on on shape s
  loss-s               the four scored HTTP/3 arms on shape s with Envoy's QUIC connection statistics on
                       (quic.stats: packets sent, received and retransmitted by the server side). Added by the
                       runner because the client reports no retransmission count; Exploratory.

CONFIRMATORY ROWS, fixed in the wave 8 plan, section 4.1 (Holm over 3): C1 h3-both-on vs h3-off on s;
C2 h3-stop-on vs h3-off on s; C3 h3-both-on vs h3-off on s-hi. Lines: anchor gate h3-official vs h2tls on s
inside [+65, +85]%; worth proposing when C1 saves 3.0% or more (commit 1 alone when C2 does); killed when C1
saves under 3.0%; harm stop when C3 reads a cost of +1.0% or more with an interval that excludes 0. Same-build
floor 2.0 log points on both shapes; three-times rule on a miss; nothing is re-run.
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


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


s2 = _load("w7s2_make_for_w8w2", os.path.join(ROOT, "examples", "wave7s2", "make.py"))

RUNS = "~/epl/runs/wave8w2"
HARNESS = "~/epl/harness-wave8w2"
SEEDS = {"s-1": 821, "s-2": 823, "shi": 822, "shi-half": 822}
ROUNDS = 6
# the client sends at a multiple of its 16 workers: half of 6,000 is run as 3,008
RATE_S, RATE_HI, RATE_HALF = 2000, 6000, 3008
CH = "envoy.reloadable_features.http1_zero_copy_body_fragments"
ST = "envoy.reloadable_features.udp_stop_reading_on_short_recvmmsg"
RU = "envoy.reloadable_features.udp_recvmmsg_reuse_buffers"
RUNTIME_KEYS = {"ch": CH, "st": ST, "ru": RU}
H = "http.ingress_http."
L = "listener.127.0.0.1_10110."
DROPPED = L + "udp.downstream_rx_datagram_dropped"
QS = L + "quic_stats."
STAT_EXTRA = (r"listener\..*\.total_bytes_sent$|^http3\.downstream\.|^runtime\.|^listener\.127\.0\.0\.1_10110\.udp\.|"
              r"^listener\.127\.0\.0\.1_10110\.quic_stats\.|^listener\.127\.0\.0\.1_10110\.downstream_cx_(destroy|overflow|"
              r"overload_reject|transport_socket_connect_timeout)$|^cluster\.origin\.upstream_(cx_connect_timeout|rq_rx_reset|"
              r"rq_tx_reset|cx_http1_total|cx_http2_total)$|^server\.(envoy_bug_failures|debug_assertion_failures)$")

with open(os.path.join(HERE, "bins.json")) as _f:
    BINS = json.load(_f)

# arm -> (build, HTTP/3?, (chunked, stop, reuse) or None for no runtime layer)
ARMS = {"h2tls": ("official", False, None),
        "h3-official": ("official", True, None),
        "h3-official-A2": ("official", True, None),
        "h3-off": ("w8-A", True, (True, False, False)),
        "h3-stop-on": ("w8-A", True, (True, True, False)),
        "h3-both-on": ("w8-A", True, (True, True, True)),
        "h3-reuse-on": ("w8-A", True, (True, False, True))}
SCORED = ["h2tls", "h3-official", "h3-official-A2", "h3-off", "h3-stop-on", "h3-both-on"]
H3_SCORED = [a for a in SCORED if ARMS[a][1]]
MECH_S = ["h2tls", "h3-official", "h3-off", "h3-stop-on", "h3-both-on", "h3-reuse-on"]
MECH_HI = ["h3-official", "h3-off", "h3-stop-on", "h3-both-on"]
KCG = ["h3-off", "h3-stop-on", "h3-both-on"]
CONF = {"s": [["h3-both-on", "h3-off"], ["h3-stop-on", "h3-off"]], "s-hi": [["h3-both-on", "h3-off"]]}


def guards(a):
    g = ARMS[a][2]
    return {k: -1 if g is None else int(v) for k, v in zip(("ch", "st", "ru"), g or (None, None, None))}


GUARDS = {a: guards(a) for a in ARMS}
# bytes per request that must agree across the HTTP/3 arms. The connection manager does not count the bytes
# it reads from a QUIC connection (the counter stays 0), so the client-to-Envoy segment is read as datagrams
# (box-wide kernel UDP counters over the window) by w2_check.py and the table, not here.
BYTES = [("Envoy to origin", "cluster.origin.upstream_cx_tx_bytes_total"),
         ("origin to Envoy", "cluster.origin.upstream_cx_rx_bytes_total"),
         ("Envoy to client (HTTP/3 stream bytes; plaintext on h2tls)", H + "downstream_cx_tx_bytes_total")]

Z = {"tol_abs": 0}
ONE = {"per_request": 1.0, "tol": 0.002}


def zero(stat, scope="window", **kw):
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


def guard_ev(g):
    """The three guards as this leg's process reads them (admin /runtime at the start of the leg, before any
    client connection, and at its end), and as the bootstrap sets them."""
    code = {k: -1 if g is None else int(v) for k, v in zip(("ch", "st", "ru"), g or (None, None, None))}
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


def same_bytes(stat, what, ref):
    return {"stat": stat, "scope": "window", "ref": {"arm": ref, "offset": 0}, "tol": 0.005,
            "label": "%s bytes per request within 0.5%% of %s in the smoke" % (what, "its own" if ref == "self" else "the %s arm's" % ref)}


NO_ERRORS = [
    dict({"stat": H + "downstream_rq_2xx", "label": "downstream 2xx 1.000 per request"}, **ONE),
    {"stat": "client_rate_2xx", "scope": "field", "min": 0.99, "max": 1.01, "per": "field:target_rps",
     "label": "client: 2xx responses per second within 1% of the target rate (open loop, fixed rate)"},
    zero(H + "downstream_cx_destroy", label="no client connection destroyed in the window"),
    zero(H + "downstream_cx_destroy_remote"), zero(H + "downstream_cx_destroy_local"),
    zero(L + "downstream_cx_destroy"), zero(L + "downstream_cx_overflow", "leg"), zero(L + "downstream_cx_overload_reject", "leg"),
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
    # the UDP listener's own drop counter (truncated datagrams and the kernel's SO_RXQ_OVFL count). Its name is
    # required to exist: the item fails when the counter is missing.
    zero(DROPPED, "leg", label="Envoy's UDP listener dropped no datagram over the leg (downstream_rx_datagram_dropped 0)"),
    {"stat": "kernel_net.d.UdpInCsumErrors", "scope": "field", "equals": 0, "tol_abs": 0},
    {"stat": "kernel_net.d.UdpMemErrors", "scope": "field", "equals": 0, "tol_abs": 0},
    {"stat": "envoy_exit", "scope": "field", "equals": 0, "tol_abs": 0, "label": "Envoy exit code 0"}]


def arm(name, refs=True, stats=False):
    build, h3, g = ARMS[name]
    b = BINS[build]
    a = s2.h3_arm(name, h3)  # S2's arm: TLS + QUIC listeners, client socket, validity gates, protocol evidence
    st = {"tls": {"cert": s2.CERT}, "quic": {"stats": True} if stats else {}}
    if g is not None:
        st["runtime"] = {CH: bool(g[0]), ST: bool(g[1]), RU: bool(g[2])}
    a["settings"] = st
    a.update(binary=b["binary"], source=b["source"], source_sha256=b["source_sha256"], build=build)
    ev = a["evidence"] + copy.deepcopy(NO_ERRORS) + guard_ev(g)
    if refs:
        ref = "h3-official" if h3 else "self"
        ev += [same_bytes(stat, what, ref) for what, stat in BYTES]
    a["evidence"] = ev
    return a


def shape(name, rps):
    return dict(sm.shapes({})["s"], name=name, rps=rps)


def scored(name, shp, arms=SCORED):
    c = s2.base(name, "s2d", extra_stats=STAT_EXTRA)
    c["client"]["extra_args"] = list(s2.KA_BASE)
    c["envoy"]["codec_type"] = "HTTP2"
    c["measure"] = dict(c["measure"], kernel_net=True, runtime_keys=dict(RUNTIME_KEYS), leg_binary_sha256=True)
    c.update(workdir=RUNS, order_seed=SEEDS.get(name, 820), rounds=ROUNDS, rounds_block=ROUNDS, rounds_max=ROUNDS,
             base_arm=arms[0], arms=[arm(n) for n in arms], shapes=[shp], confirmatory=CONF[shp["name"]])
    return c


def one_round(c, name):
    c.update(name=name, smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1)
    c.pop("short_run_note", None)
    c.pop("confirmatory", None)
    return c


def mech(name, shp, arms, wrapper=None, stats=False):
    """One round, fixed order, of some arms; under a perf wrapper when given. No frozen references."""
    c = one_round(scored(name, shp, SCORED), name)
    # a traced leg that fails a validity gate (the worker-share gate fails about one HTTP/3 leg in a hundred, by
    # where the 16 connections land) gets the harness's one automatic replacement of its round
    c.update(arms=[arm(n, refs=False, stats=stats) for n in arms], base_arm=arms[0], comparisons="base",
             rerun_invalid=1 if wrapper == "perf-sys.sh" else 0)
    if wrapper:
        c["measure"] = dict(c["measure"], perf="bash %s/examples/wave8w2/%s" % (HARNESS, wrapper))
        # a tracer or profiler runs beside these legs: nothing here is scored
        c["validity"] = dict(c.get("validity") or {}, require_perf_unmultiplexed=False)
    return c


def configs():
    S, HI, HALF = shape("s", RATE_S), shape("s-hi", RATE_HI), shape("s-hi", RATE_HALF)
    out = {"s-1": scored("s-1", S), "s-2": scored("s-2", S), "shi": scored("shi", HI), "shi-half": scored("shi-half", HALF),
           "smoke-s": one_round(scored("smoke-s", S), "smoke-s"),
           "smoke-shi": one_round(scored("smoke-shi", HI), "smoke-shi"),
           "smoke-shi-half": one_round(scored("smoke-shi-half", HALF), "smoke-shi-half"),
           "mech-sys-s": mech("mech-sys-s", S, MECH_S, "perf-sys.sh"),
           "mech-sys-shi": mech("mech-sys-shi", HI, MECH_HI, "perf-sys.sh"),
           "mech-sys-shi-half": mech("mech-sys-shi-half", HALF, MECH_HI, "perf-sys.sh"),
           "mech-kcg-s": mech("mech-kcg-s", S, KCG, "perf-kcg.sh"),
           "loss-s": mech("loss-s", S, MECH_HI, None, stats=True)}
    # smokes: the harness's one automatic replacement of a round with a leg that fails a validity gate, except
    # at 6,000 req/s, where a failing load gate is the signal for rule R3 and is not retried
    for k, n in (("smoke-s", 1), ("smoke-shi", 0), ("smoke-shi-half", 1)):
        out[k]["rerun_invalid"] = n
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
