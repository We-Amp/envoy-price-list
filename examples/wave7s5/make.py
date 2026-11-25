#!/usr/bin/env python3
"""Wave 7, session S5: the CPU price of two empty kernel calls per relayed message (candidate 3's patch arm).
One patched binary (bins.json: relay-sc) whose two runtime guards remove the calls one at a time, against
the official v1.40.2 binary.

    python3 examples/wave7s5/make.py

Arms (the same six in every scored run; the guards are set in the bootstrap's static runtime layer and are
read when a connection is created):
  official      the official v1.40.2 release, no runtime layer (base)
  official-A2   the same (the same-build check)
  patched-off   relay-sc, both guards false (the build control: must read as official)
  read-only     relay-sc, raw_buffer_socket_stop_on_short_read true, connection_write_in_current_iteration false
  write-only    relay-sc, the short-read guard false, the write guard true
  both-on       relay-sc, both guards true (the candidate)

Scored runs. The harness takes settings per arm, so the relay and the HTTP shape are separate runs; each
run is one Williams square (6 arms, 6 rounds) and the chain alternates them: relay-1, http-1, relay-2, http-2.
  relay-1.json, relay-2.json   shape p64 of S1's s1b-relay: one proxy as tcp_proxy, the origin answers a
                               64-byte body from memory in one write, 8,000 req/s, 512 connections; one
                               request = two relayed messages; responses counted at the origin. Seeds 751, 753
  http-1.json, http-2.json     shape s of S4: HTTP/1.1 GET, 4 KB proxied, 5,200 req/s. Seeds 752, 754
  smoke-relay.json, smoke-http.json   one round of every arm (order fixed), evidence recorded

Mechanism legs (non-scored; one round, order fixed, five arms: official-A2 is left out), under perf-sys.sh
(tracepoint counts on the Envoy process over the window):
  mech-sys-relay.json, mech-sys-http.json   the two scored shapes at their scored load
  mech-load-p64-{16k,24k,32k}.json
                               the relay shape at 2, 3 and 4 times the scored rate (the same 512 connections;
                               a request and its response alternate on a connection, so two messages for one
                               socket never meet here: these legs show what a busier loop does to the counts)
  mech-load-h2-{16k,32k,48k}.json
                               a relay whose sockets carry several messages at once: the client speaks HTTP/2
                               (prior knowledge) over 16 connections through tcp_proxy to the origin's HTTP/2
                               cleartext port, 64-byte body from a file, 16,000 to 48,000 req/s. This is the
                               shape where two messages for one socket can meet, for the question whether the
                               write guard adds send calls when writes of consecutive iterations are no longer
                               combined.

CONFIRMATORY ROWS, fixed before any data (in the scored configs and in table.py):
  relay (p64), cycles (user+kernel) of the Envoy process per relayed message, simple %:
     both-on vs patched-off, read-only vs patched-off, write-only vs patched-off
     LINE: the two calls are "worth a patch" when both-on saves 3% or more of CPU per relayed message.
     PREDICTION (S1, Exploratory): both-on saves 7 to 11%.
  http (s): both-on vs patched-off, no line (S1's estimate, Exploratory: about 3%).
  Build control: patched-off vs official on both shapes (expect zero).
  Same-build check per shape: official-A2 vs official, floor 1.0 log points. When a shape misses it, a line
  on that shape is decided only when the effect is at least three times the observed excursion; otherwise
  "Not resolved". Intervals: the wider of the 95% t interval and 1.96*sqrt(SE^2+0.34^2). Nothing is re-run.
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

RUNS = "~/epl/runs/wave7s5"
HARNESS = "~/epl/harness-wave7s5"
CLIENT = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"  # Nighthawk 0.3.0, md5 310df412
SEEDS = {"relay-1": 751, "http-1": 752, "relay-2": 753, "http-2": 754, "smoke-relay": 751, "smoke-http": 752}
ROUNDS = 6
SR = "envoy.reloadable_features.raw_buffer_socket_stop_on_short_read"
WR = "envoy.reloadable_features.connection_write_in_current_iteration"
RUNTIME_KEYS = {"sr": SR, "wr": WR}
H2C_PORT = 8096
RELAY = "tcp.relay."
H = "http.ingress_http."
L = "listener.127.0.0.1_10110."
# stats the evidence reads that the fixed filter leaves out
STAT_EXTRA = (r"^tcp\.relay\.|^runtime\.|^listener\.127\.0\.0\.1_10110\.downstream_cx_(destroy|overflow|overload_reject|"
              r"transport_socket_connect_timeout)$|^cluster\.origin\.upstream_(cx_connect_timeout|rq_rx_reset|rq_tx_reset|"
              r"cx_http1_total|cx_http2_total)$|^server\.(envoy_bug_failures|debug_assertion_failures)$")

with open(os.path.join(HERE, "bins.json")) as _f:
    BINS = json.load(_f)

# arm -> (build, short-read guard, write guard); None: no runtime layer
ARMS = [("official", "official", None, None), ("official-A2", "official", None, None),
        ("patched-off", "relay-sc", False, False), ("read-only", "relay-sc", True, False),
        ("write-only", "relay-sc", False, True), ("both-on", "relay-sc", True, True)]
MECH_ARMS = ["official", "patched-off", "read-only", "write-only", "both-on"]
# (the build control, patched-off vs official, and the same-build check, official-A2 vs official, are read
# beside the rows; they are not in the Holm family)
CONF_RELAY = [["both-on", "patched-off"], ["read-only", "patched-off"], ["write-only", "patched-off"]]
CONF_HTTP = [["both-on", "patched-off"]]

Z = {"tol_abs": 0}
ONE = {"per_request": 1.0, "tol": 0.002}


def zero(stat, scope="window", **kw):
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


def at_least(stat, n, scope="leg", **kw):
    return dict({"stat": stat, "scope": scope, "min": n}, **kw)


def absent(stat, scope="leg", **kw):
    return dict({"stat": stat, "scope": scope, "absent": True}, **kw)


def same_bytes(stat, what):
    """Bytes per request equal to the official arm's in the smoke (frozen by evidence-check): end-to-end byte
    counts agree across the arms."""
    return {"stat": stat, "scope": "window", "ref": {"arm": "official", "offset": 0}, "tol": 0.005,
            "label": "%s bytes per request within 0.5%% of the official arm's smoke" % what}


def guard_ev(sr, wr):
    """The two guards as this leg's process reads them (admin /runtime at the start of the leg, before any
    client connection, and at its end), and as the bootstrap sets them."""
    f = lambda k, v, when: {"stat": "runtime_%s.%s" % (when, k), "scope": "field", "equals": v, "tol_abs": 0,  # noqa: E731
                            "label": "admin /runtime at the leg's %s: %s is %s" % (
                                when, RUNTIME_KEYS[k], {1: "true", 0: "false", -1: "not set"}[v])}
    code = lambda v: -1 if v is None else int(bool(v))  # noqa: E731
    ev = [f(k, code(v), when) for when in ("start", "end") for k, v in (("sr", sr), ("wr", wr))]
    if sr is None:
        ev += [{"stat": "layered_runtime", "scope": "config", "absent": True, "label": "no runtime layer in the config"},
               {"stat": "runtime.num_keys", "scope": "leg", "equals": 0, "tol_abs": 0, "label": "runtime.num_keys 0"}]
    else:
        ev += [{"stat": SR, "scope": "config", "equals": bool(sr), "label": "the static runtime layer sets the short-read guard %s" % sr},
               {"stat": WR, "scope": "config", "equals": bool(wr), "label": "the static runtime layer sets the write guard %s" % wr},
               {"stat": "runtime.num_keys", "scope": "leg", "equals": 2, "tol_abs": 0, "label": "runtime.num_keys 2"}]
    return ev


NO_ERRORS = [zero("cluster.origin.upstream_cx_total", label="no upstream connection created in the window"),
             zero("cluster.origin.upstream_cx_destroy", label="no upstream connection destroyed in the window"),
             zero("cluster.origin.upstream_cx_destroy_remote"), zero("cluster.origin.upstream_cx_destroy_local"),
             zero("cluster.origin.upstream_cx_connect_fail", "leg", label="no upstream connect failure over the leg"),
             zero("cluster.origin.upstream_cx_connect_timeout", "leg"), zero("cluster.origin.upstream_cx_overflow", "leg"),
             zero("cluster.origin.upstream_cx_protocol_error", "leg"), zero("cluster.origin.upstream_rq_timeout", "leg"),
             zero("cluster.origin.upstream_flow_control_paused_reading_total"),
             zero("cluster.origin.upstream_flow_control_backed_up_total"),
             zero(L + "downstream_cx_destroy", label="no client connection destroyed in the window"),
             zero(L + "downstream_cx_total", label="no client connection accepted in the window"),
             zero(L + "downstream_cx_overflow", "leg"), zero(L + "downstream_cx_overload_reject", "leg"),
             zero("server.envoy_bug_failures", "leg"), zero("server.debug_assertion_failures", "leg"),
             {"stat": "client_rate_2xx", "scope": "field", "min": 0.99, "max": 1.01, "per": "field:target_rps",
              "label": "client: 2xx responses per second within 1% of the target rate (open loop, fixed rate)"},
             {"stat": "envoy_exit", "scope": "field", "equals": 0, "tol_abs": 0, "label": "Envoy exit code 0"}]


def relay_ev(sr, wr):
    return [at_least(RELAY + "downstream_cx_total", 512, label="tcp_proxy carried the client's connections"),
            same_bytes(RELAY + "downstream_cx_rx_bytes_total", "request-side (client to Envoy)"),
            same_bytes(RELAY + "downstream_cx_tx_bytes_total", "response-side (Envoy to client)"),
            same_bytes("cluster.origin.upstream_cx_tx_bytes_total", "request-side (Envoy to origin)"),
            same_bytes("cluster.origin.upstream_cx_rx_bytes_total", "response-side (origin to Envoy)"),
            absent(H + "*", label="no HTTP connection manager stats"),
            at_least("cluster.origin.upstream_cx_total", 512, label="upstream connections opened over the leg: at least 512"),
            {"stat": "conn_upstream.conns", "scope": "field", "min": 512, "max": 1024,
             "label": "established TCP connections to the origin at the end of the window: 512 to 1024"},
            zero(RELAY + "idle_timeout", "leg"), zero(RELAY + "downstream_cx_no_route", "leg"),
            zero(RELAY + "upstream_flush_total"), zero(RELAY + "downstream_flow_control_paused_reading_total"),
            {"stat": "idle_timeout", "scope": "config", "absent": True, "label": "tcp_proxy idle_timeout at its default (1 h)"},
            ] + NO_ERRORS + guard_ev(sr, wr)


def http_ev(sr, wr):
    return [dict({"stat": "cluster.origin.upstream_rq_2xx", "label": "upstream 2xx 1.000 per request"}, **ONE),
            dict({"stat": H + "downstream_rq_2xx", "label": "downstream 2xx 1.000 per request"}, **ONE),
            same_bytes(H + "downstream_cx_rx_bytes_total", "request-side (client to Envoy)"),
            same_bytes(H + "downstream_cx_tx_bytes_total", "response-side (Envoy to client)"),
            same_bytes("cluster.origin.upstream_cx_tx_bytes_total", "request-side (Envoy to origin)"),
            same_bytes("cluster.origin.upstream_cx_rx_bytes_total", "response-side (origin to Envoy)"),
            absent(RELAY + "*", label="no tcp_proxy stats"),
            zero(H + "downstream_cx_destroy"), zero(H + "downstream_cx_destroy_remote"), zero(H + "downstream_cx_destroy_local"),
            zero(H + "downstream_cx_delayed_close_timeout", "leg"), zero(H + "downstream_cx_protocol_error", "leg"),
            zero(H + "downstream_rq_rx_reset", "leg"), zero(H + "downstream_rq_tx_reset", "leg"),
            zero(H + "downstream_rq_timeout", "leg"), zero(H + "downstream_rq_5xx", "leg"), zero(H + "downstream_rq_4xx", "leg"),
            zero(H + "downstream_flow_control_paused_reading_total"),
            zero("cluster.origin.upstream_rq_rx_reset", "leg"), zero("cluster.origin.upstream_rq_tx_reset", "leg"),
            ] + NO_ERRORS + guard_ev(sr, wr)


def base(name, relay):
    b = json.loads(json.dumps(sm.BASE))
    b.pop("floor_from")
    b.pop("stop")
    b["client"]["binary"] = CLIENT
    b["origin"].update(stub_status=True)
    # idleness by load and CPU only: no process is matched by its command line
    b["idle"] = dict(b["idle"], procs=[])
    b["measure"] = dict(b["measure"], stat_filter_extra=STAT_EXTRA, runtime_keys=dict(RUNTIME_KEYS), leg_binary_sha256=True)
    if relay:
        b["measure"]["responses_from"] = "origin"
    b.update(workdir=RUNS, name=name, order="williams", order_seed=SEEDS.get(name, 750), rounds=ROUNDS,
             rounds_block=ROUNDS, rounds_max=ROUNDS, adaptive=False, comparisons="all_pairs", base_arm="official",
             short_run_note="short run: %d fixed rounds in Williams order, run with --allow-short" % ROUNDS)
    return b


def arm(name, build, sr, wr, relay, ev=None, extra=None):
    b = BINS[build]
    st = dict(extra or {})
    if relay:
        st["tcp_proxy"] = True
    if sr is not None:
        st["runtime"] = {SR: bool(sr), WR: bool(wr)}
    a = {"name": name, "binary": b["binary"], "source": b["source"], "source_sha256": b["source_sha256"], "build": build}
    if st:
        a["settings"] = st
    a["evidence"] = copy.deepcopy(ev if ev is not None else (relay_ev(sr, wr) if relay else http_ev(sr, wr)))
    return a


P64 = {"name": "p64", "path": "/p64", "kind": "proxied", "origin_inline": True, "body_bytes": 64, "rps": 8000}


def relay(name):
    c = base(name, True)
    c.update(arms=[arm(n, b, sr, wr, True) for n, b, sr, wr in ARMS], shapes=[dict(P64)], confirmatory=CONF_RELAY)
    return c


def http(name):
    c = base(name, False)
    c.update(arms=[arm(n, b, sr, wr, False) for n, b, sr, wr in ARMS], shapes=[sm.shapes({})["s"]], confirmatory=CONF_HTTP)
    return c


def as_one_round(c):
    c.update(smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1)
    c.pop("short_run_note", None)
    c.pop("confirmatory", None)
    return c


def under_tracer(c):
    c["measure"] = dict(c["measure"], perf="bash %s/examples/wave7s5/perf-sys.sh" % HARNESS)
    # a tracer runs beside these legs: nothing here is scored
    c["validity"] = dict(c.get("validity") or {}, require_perf_unmultiplexed=False)
    return c


def mech(name, src):
    """One round, fixed order, of the five arms of a scored config under the tracepoint wrapper."""
    c = as_one_round(copy.deepcopy(src))
    arms = {a["name"]: a for a in c["arms"]}
    c.update(name=name, arms=[arms[n] for n in MECH_ARMS], comparisons="base")
    for a in c["arms"]:
        # (the byte references are frozen from a smoke; a mechanism leg has none)
        a["evidence"] = [e for e in a["evidence"] if "ref" not in e]
    return under_tracer(c)


def load_p64(name, rps):
    c = mech(name, relay(name))
    c["shapes"] = [dict(P64, rps=rps)]
    return c


def load_h2(name, rps):
    """The client's HTTP/2 connections relayed by tcp_proxy to the origin's HTTP/2 cleartext port: 16
    connections (one per client worker, four per Envoy worker), many requests in flight on each."""
    c = base(name, True)
    c["origin"].update(h2c_port=H2C_PORT)
    c["client"]["extra_args"] = ["--h2", "--prefetch-connections", "--max-pending-requests", "1000"]
    c["client"]["connections_per_worker"] = 1
    ev = lambda sr, wr: [  # noqa: E731
        at_least(RELAY + "downstream_cx_total", 16, label="tcp_proxy carried the client's connections"),
        absent(H + "*", label="no HTTP connection manager stats"),
        zero(RELAY + "idle_timeout", "leg"), zero(RELAY + "downstream_cx_no_route", "leg"),
        zero("cluster.origin.upstream_cx_total", label="no upstream connection created in the window"),
        zero("cluster.origin.upstream_cx_destroy", label="no upstream connection destroyed in the window"),
        zero("cluster.origin.upstream_cx_connect_fail", "leg"), zero(L + "downstream_cx_destroy"),
        {"stat": "client_rate_2xx", "scope": "field", "min": 0.99, "max": 1.01, "per": "field:target_rps",
         "label": "client: 2xx responses per second within 1% of the target rate"},
        {"stat": "envoy_exit", "scope": "field", "equals": 0, "tol_abs": 0, "label": "Envoy exit code 0"}] + guard_ev(sr, wr)
    by = {n: (b, sr, wr) for n, b, sr, wr in ARMS}
    c.update(arms=[arm(n, by[n][0], by[n][1], by[n][2], True, ev(by[n][1], by[n][2]), {"origin_server": "h2c"})
                   for n in MECH_ARMS],
             shapes=[{"name": "h64", "path": "/h64", "kind": "proxied", "body_bytes": 64, "rps": rps}])
    as_one_round(c)
    c.update(comparisons="base")
    return under_tracer(c)


def configs():
    return {"relay-1": relay("relay-1"), "relay-2": relay("relay-2"), "http-1": http("http-1"), "http-2": http("http-2"),
            "smoke-relay": as_one_round(relay("smoke-relay")), "smoke-http": as_one_round(http("smoke-http")),
            "mech-sys-relay": mech("mech-sys-relay", relay("mech-sys-relay")),
            "mech-sys-http": mech("mech-sys-http", http("mech-sys-http")),
            "mech-load-p64-16k": load_p64("mech-load-p64-16k", 16000),
            "mech-load-p64-24k": load_p64("mech-load-p64-24k", 24000),
            "mech-load-p64-32k": load_p64("mech-load-p64-32k", 32000),
            "mech-load-h2-16k": load_h2("mech-load-h2-16k", 16000),
            "mech-load-h2-32k": load_h2("mech-load-h2-32k", 32000),
            "mech-load-h2-48k": load_h2("mech-load-h2-48k", 48000)}


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn, c in sorted(configs().items()):
        with open(os.path.join(OUT, fn + ".json"), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
        print(fn + ".json")


if __name__ == "__main__":
    main()
