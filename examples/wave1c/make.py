#!/usr/bin/env python3
"""Track C of wave 1: two new price-list rows on the official v1.40.2 binary, config only.

    python3 examples/wave1c/make.py [write] [RATES_JSON]
    python3 examples/wave1c/make.py budget SECONDS_PER_LEG | SMOKE_ROOT

RATES_JSON (optional): {"s": req/s, "s-lo": req/s} (the ext_proc row falls back to a lower `s`
when the smoke shows a worker above 80% busy at 5,200; see run-session-c.sh).

Configs (in configs/):

  extproc.json      ext_proc in its default mode (request and response headers: two messages
                    per request on one stream opened per request) and with request headers only,
                    ext_authz gRPC (the published row, the replication anchor), each through
                    envoy_grpc and google_grpc; against no filter, with a second copy of it (the
                    A/A). 8 arms, shape s (4 KB proxied, 5,200 req/s), 6 fixed rounds (a short
                    run: rotation_block 6, run with --allow-short).
  xds-small.json    the price of one xDS update, SotW from watched files, 200 filler routes,
                    50 filler clusters, a filler EDS cluster of 100 endpoints: no updates (ref,
                    and ref-A2, the A/A), RDS changed, RDS re-sent unchanged, CDS one filler
                    cluster changed, CDS re-sent unchanged, CDS the cluster in use changed, EDS
                    one host replaced; 1 update per second; shapes s (5,200 req/s) and s-lo (400
                    req/s, where the workers' share of an update can be told from noise);
                    per-thread cycles (main thread, workers, other threads); 6 fixed rounds.
  xds-small-s.json  xds-small at shape s only (the trimmed first session: one size, one load).
  xds-large.json    the same at 2,000 routes, 500 clusters, 1,000 endpoints (no A/A arm: the
                    A/A of xds-small is the floor, same session).
  smoke-*.json      one round of every arm (order fixed), evidence recorded, not gated.

Every arm runs the same binary: ~/epl/bin/envoy-1.40.2, sha256 enforced.
"""

import importlib.util
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
from epl import xds  # noqa: E402

_spec = importlib.util.spec_from_file_location("features", os.path.join(SM, "features.py"))
F = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F)

RUNS = "~/epl/runs/wave1c"
ORDER_SEED = 31
ROUNDS = 6
EXT_PROC_PORT = 8095
EXT_PROC_BINARY = "tools/extproc/out/epl-extproc-linux-amd64"
UPDATE_HZ = 1.0
SIZES = {"small": {"routes": 200, "clusters": 50, "eds_endpoints": 100},
         "large": {"routes": 2000, "clusters": 500, "eds_endpoints": 1000}}
GUARD_S = 0.5
XDS_CLIENT_S = 27
# main thread at most half busy over the window: an update never waits for the previous one
MAX_MAIN_BUSY = 0.5


def ext_proc_sha256():
    p = os.path.join(ROOT, "tools", "extproc", "SHA256SUMS")
    with open(p) as f:
        for line in f:
            h, _, n = line.strip().partition("  ")
            if n == os.path.basename(EXT_PROC_BINARY):
                return h
    raise SystemExit("no sha256 for %s in %s" % (EXT_PROC_BINARY, p))


zero, ONE = F.zero, F.ONE


def arm(name, settings=None, ev=None):
    a = sm.arm(name, settings)
    if ev:
        a["evidence"] = json.loads(json.dumps(ev))
    return a


def base_cfg(name):
    b = json.loads(json.dumps(sm.BASE))
    b.pop("floor_from")
    b.update(workdir=RUNS, order_seed=ORDER_SEED, name=name, rounds=ROUNDS, rounds_block=ROUNDS,
             rounds_max=ROUNDS, adaptive=False, order="rotate", rotation_block=ROUNDS,
             short_run_note="short run: 6 fixed rounds (large effects: stop when the answer is "
                            "clear); the rotation does not complete, so each arm takes 6 distinct positions; "
                            "run with --allow-short")
    b["measure"] = dict(b["measure"], per_thread=True, thread_set_check=True)
    return b


# ---------------------------------------------------------------- ext_proc row

XP = "http.ingress_http.ext_proc."
EV_NO_FILTER = [{"stat": "http.ingress_http.ext_authz.ok", "absent": True, "label": "no ext_authz counters"},
                {"stat": XP + "streams_started", "absent": True, "label": "no ext_proc counters"}]


def ev_ext_proc(messages, client):
    ev = [dict({"stat": XP + "streams_started"}, **ONE),
          {"stat": XP + "stream_msgs_sent", "per_request": float(messages), "tol": 0.002},
          {"stat": XP + "stream_msgs_received", "per_request": float(messages), "tol": 0.002},
          zero(XP + "streams_failed"), zero(XP + "spurious_msgs_received"), zero(XP + "failure_mode_allowed"),
          zero(XP + "message_timeouts"), zero(XP + "immediate_responses_sent"),
          zero(XP + "rejected_header_mutations")]
    return ev + ev_client(client, "ext_proc")


def ev_client(client, name):
    if client == "envoy_grpc":
        return [dict({"stat": "cluster.%s.upstream_rq_total" % name}, **ONE),
                zero("cluster.%s.upstream_cx_total" % name, label="no new connection to the service in the window"),
                {"stat": "grpc.%s.streams_total" % name, "absent": True, "label": "no google_grpc client"}]
    return [dict({"stat": "grpc.%s.streams_total" % name}, **ONE),
            {"stat": "cluster.%s.upstream_rq_total" % name, "absent": True, "label": "no %s cluster" % name}]


def ev_authz(client):
    ev = [dict({"stat": "http.ingress_http.ext_authz.ok"}, **ONE),
          zero("http.ingress_http.ext_authz.denied"), zero("http.ingress_http.ext_authz.error"),
          zero("http.ingress_http.ext_authz.failure_mode_allowed")]
    if client == "envoy_grpc":
        ev.append(zero("cluster.ext_authz.upstream_rq_timeout"))
    return ev + ev_client(client, "ext_authz")


def ext_proc_arms():
    out = [arm("off", ev=EV_NO_FILTER), arm("off-A2", ev=EV_NO_FILTER)]
    for client, sfx in (("envoy_grpc", ""), ("google_grpc", "-google")):
        g = {"grpc_client": client} if client != "envoy_grpc" else {}
        out.append(arm("authz-grpc" + sfx, dict({"ext_authz": "grpc"}, **g), ev_authz(client)))
        out.append(arm("xp-default" + sfx, dict({"ext_proc": {"mode": "default"}}, **g), ev_ext_proc(2, client)))
        out.append(arm("xp-reqhdr" + sfx, dict({"ext_proc": {"mode": "request_headers"}}, **g),
                       ev_ext_proc(1, client)))
    return out


def ext_proc_cfg(rates):
    # the ext_proc row's own rate (the 4,000 req/s fallback) without moving the xDS row's
    S = sm.shapes(dict(rates, s=rates.get("extproc_s", rates.get("s", 5200))))
    c = base_cfg("c-extproc")
    c["origin"] = dict(c["origin"], authz_grpc_port=8094, ext_proc_port=EXT_PROC_PORT, ext_proc_binary=EXT_PROC_BINARY,
                       ext_proc_sha256=ext_proc_sha256())
    c["measure"]["stat_filter_extra"] = r"cluster\.ext_proc\.upstream_(rq_total|cx_total)$|grpc\.(ext_proc|ext_authz)\."
    c.update(base_arm="off", arms=ext_proc_arms(), shapes=[S["s"]],
             confirmatory=[[a["name"], "off"] for a in ext_proc_arms() if a["name"] not in ("off", "off-A2")])
    return c


# ---------------------------------------------------------------- xDS row

RDS = "http.ingress_http.rds.%s." % xds.ROUTE_NAME
CM = "cluster_manager."
EDS = "cluster.%s." % xds.EDS_CLUSTER
N_WINDOW = int(round(20 * UPDATE_HZ))


def eq(stat, n, **kw):
    return dict({"stat": stat, "scope": "window", "equals": n, "tol_abs": 0}, **kw)


# what each update kind must do in the window, besides the xds record's own checks
XDS_EV = {
    None: [eq(CM + "cluster_modified", 0), eq(EDS + "membership_change", 0)],
    "rds": [eq(CM + "cluster_modified", 0)],
    "rds_same": [eq(CM + "cluster_modified", 0)],
    "cds": [eq(CM + "cluster_modified", N_WINDOW, label="one cluster modified per update")],
    "cds_same": [eq(CM + "cluster_modified", 0, label="unchanged clusters are not modified")],
    "cds_active": [eq(CM + "cluster_modified", N_WINDOW, label="the origin cluster modified per update")],
    "eds": [eq(EDS + "membership_change", N_WINDOW, label="one membership change per update"),
            eq(CM + "cluster_modified", 0)],
}
XDS_ARMS = [("ref", None), ("rds", "rds"), ("rds-same", "rds_same"), ("cds", "cds"), ("cds-same", "cds_same"),
            ("cds-active", "cds_active"), ("eds", "eds")]


def xds_arms(size, with_aa):
    out = []
    names = XDS_ARMS[:1] + ([("ref-A2", None)] if with_aa else []) + XDS_ARMS[1:]
    for name, kind in names:
        s = {"xds": dict(SIZES[size])}
        if kind:
            s["xds_update"] = {"kind": kind, "rate_hz": UPDATE_HZ, "guard_s": GUARD_S}
        out.append(arm(name, s, XDS_EV[kind]))
    return out


def xds_shapes(rates):
    S = sm.shapes(rates)
    lo = dict(S["s"], name="s-lo", rps=int(rates.get("s-lo", 400)), client_concurrency=4,
              client_connections_per_worker=8)
    return [S["s"], lo]


def xds_cfg(size, rates, only_s=False):
    c = base_cfg("c-xds-%s%s" % (size, "-s" if only_s else ""))
    c["origin"] = dict(c["origin"], stub_status=True)
    c["measure"].update(stat_filter_extra=xds.STAT_FILTER_EXTRA + r"|cluster\.origin\.", origin_accepts=True)
    c["validity"] = {"max_main_busy": MAX_MAIN_BUSY}
    # the pre-window guard and the slower stats reads of the large tables come out of the client's
    # slack after the window: 2 s more than the other rows, so the second read ends while it sends
    c["client"] = dict(c["client"], duration_s=XDS_CLIENT_S)
    c.update(base_arm="ref", arms=xds_arms(size, size == "small"),
             shapes=xds_shapes(rates)[:1] if only_s else xds_shapes(rates))
    return c


def smoke(c):
    s = json.loads(json.dumps(c))
    s.update(name="smoke-" + c["name"], smoke=True, order="fixed", rounds=1, rounds_block=1, rounds_max=1,
             adaptive=False, evidence_mode="record")
    for k in ("rotation_block", "short_run_note", "confirmatory"):
        s.pop(k, None)
    return s


def configs(rates):
    runs = {"extproc.json": ext_proc_cfg(rates), "xds-small.json": xds_cfg("small", rates),
            "xds-large.json": xds_cfg("large", rates),
            # the trimmed session: the small size at 5,200 req/s only
            "xds-small-s.json": xds_cfg("small", rates, only_s=True)}
    out = dict(runs)
    for fn, c in runs.items():
        out["smoke-" + fn] = smoke(c)
    return out


def legs(c):
    return c["rounds_max"] * sum(len([a for a in c["arms"] if a.get("shapes") is None or s["name"] in a["shapes"]])
                                 for s in c["shapes"])


def budget(seconds_per_leg, out=sys.stdout):
    tot = 0
    for fn, c in sorted(configs({}).items()):
        n = legs(c)
        tot += n * seconds_per_leg
        out.write("%-24s %4d legs  %5.2f h\n" % (fn, n, n * seconds_per_leg / 3600))
    out.write("total %.2f h at %.0f s per leg (no re-runs)\n" % (tot / 3600, seconds_per_leg))
    return tot


def main(argv):
    cmd = argv[0] if argv and argv[0] in ("write", "budget") else "write"
    args = argv[1:] if argv and argv[0] == cmd else argv
    if cmd == "budget":
        # budget SECONDS_PER_LEG | budget SMOKE_ROOT (seconds per leg measured over its smoke runs)
        if args and os.path.isdir(args[0]):
            spl, n = F.seconds_per_leg(args[0])
            sys.stdout.write("seconds per leg (smoke, %d gaps): %.1f\n" % (n, spl))
        else:
            spl = float(args[0]) if args else 45.0
        budget(spl)
        return 0
    rates = {}
    if args:
        with open(args[0]) as f:
            rates = json.load(f)
    os.makedirs(OUT, exist_ok=True)
    for fn, c in configs(rates).items():
        with open(os.path.join(OUT, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
