#!/usr/bin/env python3
"""Write the configs of wave 3 track E: the price of one new connection.

Official v1.40.2 binary only; every arm differs from its run's base by config (Envoy settings or the
client's connection settings), nothing else.

    python3 examples/wave3e/make.py [--box BOX_JSON] [--rates '{"e-plain": 800}'] [--res-single-target]

--rates and --res-single-target are the smoke fallbacks fixed before the run (a kernel gate
fails at 1,600; rsa-full busier than 0.80; ecdsa-res resumes under 99% across 16 destinations).

Runs (in a directory named after the box), each with its one-round smoke:
  e-plain   plaintext HTTP/1.1, 4 KB proxied (/s) at 1,600 req/s: ka (keep-alive, base), ka-A2 (A/A),
            c1 (one request per connection). 3 arms, Williams (6 rounds = the 3-arm square and its mirror).
  e-tls     TLS 1.3, the same shape at 800 req/s, one request per connection unless named ka:
            ecdsa-full (base), ecdsa-full-A2 (A/A), rsa-full, ecdsa-res (resumed), ecdsa-x25519
            (the listener accepts X25519 and P-256 only, so the hybrid group is not used), tls-ka
            (keep-alive). 6 arms, Williams (6 rounds).
  e2-plain  plaintext churn at 1,600 req/s: c1 (base), c1-A2 (A/A), c1-defer (TCP_DEFER_ACCEPT 1 s),
            c1-shared (one listen socket shared by the workers), c1-xb (exact_balance), ka (keep-alive,
            the plaintext price again). 6 arms, Williams (6 rounds).
  e2b-plain c1, c1-A2, c1-defer, ka of e2-plain (the arms that can be priced). 4 arms, Williams (8 rounds).

The rig, as wave 2 (4 workers on 0-3, siblings idle; client 20-31,60-71; origin 32-39,72-79), with two
changes for churn, the same in every arm of a run:
  - one listener on 127.0.0.1-127.0.0.16 (its address plus 15 additional_addresses: one filter chain,
    one TLS context, one ticket key, nothing reachable from the LAN), and the one-request-per-connection
    arms spread their connections over those 16 destinations (Nighthawk --multi-target-endpoint, round
    robin), so no source/destination pair runs short of ports;
  - exact_balance is off (Envoy's default: the kernel's reuse-port placement), because the exact
    balancer's per-accept work would be part of every per-connection price.
Box limit that sets the rates (read-only probe 2026-11-22): nf_conntrack is loaded, nf_conntrack_max
262,144, TIME_WAIT entries live 120 s, so about 2,000 new connections per second is the sustained
ceiling with back-to-back legs; 1,600 keeps the table under about 55% and the kernel gates check it.
"""

import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "settings-matrix"))
import make as sm  # noqa: E402  (settings-matrix: CLIENT_TLS_HS, the client's TLS 1.3 socket)

RUNS = "~/epl/runs/wave3e"
CLIENT = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"  # Nighthawk 0.3.0, md5 310df412
ROUNDS = 6
LISTENER = "listener.127.0.0.1_10110."  # one listener: its stats sit under its first address
RATES = {"e-plain": 1600, "e-tls": 800, "e2-plain": 1600, "e2b-plain": 1600}
SEEDS = {"e-plain": 71, "e-tls": 72, "e2-plain": 73, "e2b-plain": 74}
ROUNDS_OF = {"e2b-plain": 8}  # 4 arms: a Williams square has period 4; 8 rounds = two squares
FANOUT = {"count": 16, "base": "127.0.0.1"}
# the published rig's keep-alive client (prefetch, LRU reuse: 512 connections carry the load evenly)
KA_BASE = ["--prefetch-connections", "--max-pending-requests", "1000",
           "--experimental-h1-connection-reuse-strategy", "lru"]
# churn: no prefetch, the client's default reuse; each request opens its own connection, which the
# client closes after the response (so TIME_WAIT sits on the client's side, as with real clients)
C1_BASE = ["--max-pending-requests", "1000"]
C1_EXTRA = ["--max-requests-per-connection", "1"]
TLS_CLIENT = ["--transport-socket", sm.CLIENT_TLS_HS]  # TLS 1.2-1.3, 1,024 session keys, no cert check


def ev_common():
    return [{"stat": "http.ingress_http.downstream_rq_2xx", "scope": "leg", "min": 1}]


def ev_kernel(churn):
    """Box-wide kernel counters over the window: no listen-queue drop, no SYN retransmit, no failed
    connect, no TIME_WAIT overflow; the conntrack table under 75% at the window's end."""
    z = [{"stat": "kernel_net.d." + k, "scope": "field", "equals": 0, "tol_abs": 0}
         for k in ("ListenOverflows", "ListenDrops", "TCPTimeWaitOverflow", "TCPReqQFullDrop", "AttemptFails")]
    if churn:
        z.append({"stat": "kernel_net.d.TCPSynRetrans", "scope": "field", "equals": 0, "tol_abs": 0})
        z.append({"stat": "kernel_net.end.conntrack_fill", "scope": "field", "max": 0.75})
        # the kernel's own count of accepted connections, independent of Envoy's stats
        z.append({"stat": "kernel_net.d.PassiveOpens", "scope": "field", "per": "field:responses_raw",
                  "min": 0.97, "max": 1.03})
    return z


def ev_conn(churn):
    if churn:
        return [{"stat": LISTENER + "downstream_cx_total", "per_request": 1.0, "tol": 0.02}]
    return [{"stat": LISTENER + "downstream_cx_total", "per_request": 0.0, "tol_abs": 0.001}]


def ev_tls(churn, resumed, group):
    other = "X25519" if group == "X25519MLKEM768" else "X25519MLKEM768"
    ev = [{"stat": LISTENER + "ssl.handshake", "per_request": 1.0 if churn else 0.0,
           **({"tol": 0.02} if churn else {"tol_abs": 0.001})},
          # every handshake of the leg (warm-up included) used this arm's group, none the other
          {"stat": LISTENER + "ssl.curves." + group, "scope": "leg", "min": 1},
          {"stat": LISTENER + "ssl.curves." + other, "scope": "leg", "absent": True},
          {"stat": LISTENER + "ssl.versions.TLSv1.3", "scope": "leg", "min": 1},
          {"stat": LISTENER + "ssl.versions.TLSv1.2", "scope": "leg", "absent": True}]
    if churn:
        ev.append({"stat": LISTENER + "ssl.curves." + group, "per_request": 1.0, "tol": 0.02})
        ev.append({"stat": LISTENER + "ssl.session_reused", "per_request": 1.0 if resumed else 0.0,
                   **({"tol": 0.01} if resumed else {"tol_abs": 0.0})})
    return ev


def arm(box, name, settings=None, churn=True, tls=None, resumed=False, group="X25519MLKEM768"):
    b = box["binaries"]["x86_64"]
    a = {"name": name, "binary": b["binary"], "source": b["source"], "source_sha256": b["source_sha256"]}
    if settings:
        a["settings"] = settings
    extra = (list(TLS_CLIENT) if tls else []) + (list(C1_EXTRA) if churn else [])
    a["client"] = {"base_args": list(C1_BASE if churn else KA_BASE), "extra_args": extra}
    if churn:
        a["client"]["multi_target"] = dict(FANOUT)
        # the request that opens a connection waits for it; nothing else may wait
        a["validity"] = {"max_pending_total": "client_cx"}
    elif tls:
        # keep-alive TLS: the 512 start-up handshakes queue requests before the window (settings
        # matrix follow-up: ECDSA 200-316 pending, no overflow); bounded at twice the connections
        a["validity"] = {"max_pending_total": 1024}
    a["evidence"] = ev_common() + ev_conn(churn) + ev_kernel(churn)
    if tls:
        a["evidence"] += ev_tls(churn, resumed, group)
    return a


def base(box, name, rate):
    return {
        "name": name, "machine_label": box["machine_label"], "workdir": RUNS,
        "envoy": {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": False,
                  "listener_address": "127.0.0.1", "listener_fanout": 16, "log_level": "warn", "codec_type": "HTTP1"},
        "cpus": dict(box["cpus"]),
        "client": {"binary": CLIENT, "concurrency": 16, "connections_per_worker": 32, "warmup_s": 5,
                   "duration_s": 25, "idle_strategy": "poll", "open_loop": True, "extra_args": list(KA_BASE)},
        "idle": {"max_load1": 8.0, "max_busy_pct": 2.0},
        "origin": {"mode": "docker", "port": 8092, "workers": 8, "image": box["origin_image"],
                   "platform": box["image_platform"]},
        "measure": {"lead_in_s": 2, "window_s": 20, "perf": box["perf"], "kernel_net": True},
        "primary_metric": "cycles_total", "comparisons": "base", "adaptive": False,
        "shapes": [{"name": "s", "kind": "proxied", "path": "/s", "body_bytes": 4096, "rps": rate}],
    }


DEFER_EV = {"stat": "kernel_net.d.TCPDeferAcceptDrop", "scope": "field", "per": "field:responses_raw"}


def runs(box, res_single_target=False):
    full = {"resumption": False}
    plain = [arm(box, "ka", churn=False), arm(box, "ka-A2", churn=False), arm(box, "c1")]
    tls = [
        arm(box, "ecdsa-full", {"tls": dict(full, cert="ecdsa-p256")}, tls=True),
        arm(box, "ecdsa-full-A2", {"tls": dict(full, cert="ecdsa-p256")}, tls=True),
        arm(box, "rsa-full", {"tls": dict(full, cert="rsa2048")}, tls=True),
        arm(box, "ecdsa-res", {"tls": {"cert": "ecdsa-p256"}}, tls=True, resumed=True),
        arm(box, "ecdsa-x25519", {"tls": dict(full, cert="ecdsa-p256", groups=["X25519", "P-256"])},
            tls=True, group="X25519"),
        arm(box, "tls-ka", {"tls": dict(full, cert="ecdsa-p256")}, churn=False, tls=True),
    ]
    # E2: listener accept-path settings under plaintext churn, against c1 at the same rate;
    # ka re-measures the plaintext price in the same session
    e2 = [arm(box, "c1"), arm(box, "c1-A2"),
          arm(box, "c1-defer", {"tcp_defer_accept_s": 1}),
          arm(box, "c1-shared", {"reuse_port": False}),
          arm(box, "c1-xb", {"exact_balance": True}),
          arm(box, "ka", churn=False)]
    # TCPDeferAcceptDrop counts the bare final handshake ACK that a deferring listener ignores: once per
    # connection whose request comes in a later packet (every connection here), 0 without the option
    for a in e2:
        if a["name"] == "c1-defer":
            a["evidence"].append(dict(DEFER_EV, per_request=1.0, tol=0.02))
        else:
            a["evidence"].append(dict(DEFER_EV, per_request=0.0, tol_abs=0.001))
    # E2B (2026-11-22, after e2-plain): the arms that can be priced; c1-shared and c1-xb fail the
    # worker-share gate by construction under churn and stay qualitative
    e2b = [copy.deepcopy(a) for a in e2 if a["name"] in ("c1", "c1-A2", "c1-defer", "ka")]
    if res_single_target:
        tls[3]["client"]["multi_target"] = {"count": 1, "base": "127.0.0.1"}
    return {"e-plain": ("ka", plain), "e-tls": ("ecdsa-full", tls), "e2-plain": ("c1", e2), "e2b-plain": ("c1", e2b)}


def configs(box, rates=None, res_single_target=False):
    out = {}
    rates = dict(RATES, **(rates or {}))
    for stem, (b, arms) in runs(box, res_single_target).items():
        if rates[stem] % 16:
            raise SystemExit("rate %s of %s does not divide by the 16 client workers" % (rates[stem], stem))
        for smoke in (True, False):
            c = base(box, ("smoke-" if smoke else "") + stem, rates[stem])
            c.update(arms=copy.deepcopy(arms), base_arm=b, warmup_legs=1, order_seed=SEEDS[stem],
                     rounds=1 if smoke else ROUNDS_OF.get(stem, ROUNDS),
                     rounds_block=1 if smoke else ROUNDS_OF.get(stem, ROUNDS),
                     rounds_max=1 if smoke else ROUNDS_OF.get(stem, ROUNDS))
            if smoke:
                c.update(smoke=True, evidence_mode="record", order="fixed")
            else:
                c["order"] = "williams"
            out[c["name"] + ".json"] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", default=os.path.join(HERE, "..", "stats-flush", "boxes", "bench-x86_64.json"))
    ap.add_argument("--rates", default=None, help="JSON {run: req/s} overriding RATES")
    ap.add_argument("--res-single-target", action="store_true")
    a = ap.parse_args()
    with open(a.box) as f:
        box = json.load(f)
    d = os.path.join(HERE, box["name"])
    os.makedirs(d, exist_ok=True)
    cfgs = configs(box, json.loads(a.rates) if a.rates else None, a.res_single_target)
    for fn, c in sorted(cfgs.items()):
        with open(os.path.join(d, fn), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
    print("%s: %d configs (%s)" % (box["name"], len(cfgs), ", ".join(sorted(cfgs))))


if __name__ == "__main__":
    main()
