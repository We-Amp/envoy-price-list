#!/usr/bin/env python3
"""Write the configs of the stats-flush row: what N stats cost Envoy's main thread per
flush, with and without a sink.

    python3 examples/stats-flush/make.py [--box BOX_JSON ...] [--rungs RUNGS_JSON]

For every box description (default: every file in boxes/) the configs go to a directory
named after the box, with a copy of box.json; everything machine-specific (CPU sets, perf
path and event list, labels, client binary, Envoy binary and release asset per
architecture, image digests and platform) comes from the box, so the same configs run on
an x86_64 and an aarch64 machine (`epl portability-check` verifies it).

RUNGS_JSON comes from `epl stats-calibrate` (run-session.sh calibrate): per rung the ready
and admin timeouts, the settle after the pre-window read, the calibrated stat counts and,
where the smoke decides it, the statsd interval of that rung. Without it the configs are
marked uncalibrated and run-session.sh refuses to queue them.

Rungs (K generated clusters, target N stats): 10k (100), 100k (1,000), 300k (3,000),
1m (10,000); the 3M probe (30,000 clusters) is a calibration config only.

  cal-<rung>.json    calibration: nosink and statsd, one idle leg each (stats-calibrate)
  cal-3m.json, cal-10m.json   the 3M probe at step 0 and the 10M probe after the queue
  smoke-100k.json, smoke-1m.json   one round of every arm (evidence recorded, not gated)
  smoke-m-10k.json, smoke-m-300k.json, smoke-w.json   one round of run M's arms at the
                     other two rungs and of run W, so every arm is checked at its own rung
  m-<rung>.json      run M, the curve: flush-off, nosink, statsd, nosink-A2; 4 rounds, one
                     Latin square, seed 31; 1 s flush interval, 20 s window
  w.json             run W, workers under load at 100k: flush-off, nosink, statsd,
                     flush-off-A2 on the 4 KB proxied shape at 5,200 req/s, default 5 s
                     interval, 8 rounds
  s-100k.json, s-1m.json   run S, the sinks: nosink, nosink-A2 (A/A), statsd (unbuffered),
                     dogstatsd-buf (dog_statsd, max_bytes_per_datagram 1432), otlp (envoy_grpc to
                     the local null collector, its CPU gated as a side service); at 1M
                     statsd and dogstatsd-buf flush every 5 s, otlp every 20 s (60 s window), by
                     the saturation rule (S_INTERVALS); 10 rounds at 100k, 7 at 1M; each with a nosink at its own interval
                     (nosink-5s, nosink-20s); per-flush prices from each leg's quiescent span;
                     smoke-s-<rung>.json one round each
  sw.json            run S under load: run W's shape (1,000 clusters, 5,200 req/s, 5 s interval)
                     with the same five arms, worker cycles per request; 10 rounds; smoke-sw.json
  x-1m.json          run X, conditions: statsd, statsd-5s (30 s window), statsd-cold,
                     nosink-cold; 4 rounds (one Latin square; the plan's 3 would not balance)
  mfix-<rung>.json   run M-fix (boxes with fix_binaries only): the run-M design at 10k, 100k
                     and 1M with two own builds instead of the release: base (upstream main at
                     the fix's base) and top (the fix on that base), each with nosink and the
                     statsd sink, plus a second copy of base nosink as the A/A; 5 rounds, one
                     Latin square, seed 32; N and used counts frozen from its own smoke
                     (smoke-mfix-<rung>.json), since the builds' stat sets may differ
  sibling.json       the sibling row (stats updates per request): base, stats-reject on s
                     and fh, 12 rounds (not in this session's queue)
  ab-template.json   the fix A/B (base, fix, base-A2, official): a template for the later
                     session; the fix and base binaries are filled in when they are built

Evidence per arm (fields of the idle leg; numbers from the calibration where the plan
says so; ref items frozen from the smoke).
"""

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import envoy_config  # noqa: E402

ORDER_SEED = 31
RUNS = "~/epl/runs/stats-flush"
RUNGS = [("10k", 100), ("100k", 1000), ("300k", 3000), ("1m", 10000)]
PROBE = ("3m", 30000)
PROBE_10M = ("10m", 100000)  # a probe after the queue, never a priced row
SINK_PORT = 8125
INTERVAL_S = 1
WINDOW_S = 20
# run S at 1M: the smoke of 2026-11-17 ran dogstatsd-buf at 914 and otlp at 1,000 ms of main-thread
# time per second at 1 s (saturated by the plan's 900 ms rule), and otlp took about 12 s per flush
# (4.3 flushes of 1.55M points in a 51 s span); so at 1M dogstatsd-buf flushes every 5 s (as statsd
# by the saturation rule) and otlp every 20 s with a 60 s window (3 flushes)
S_INTERVALS = {"1m": {"dogstatsd-buf": 5, "otlp": 20}}
S_WINDOWS = {"1m": {"otlp": 60}}
S_ARMS = ["nosink", "nosink-A2", "statsd", "dogstatsd-buf", "otlp"]
# S2: at 1M every sink has a nosink reference at its own interval (statsd and dogstatsd-buf at 5 s,
# otlp at 20 s); the per-flush price of each arm comes from its own quiescent span (S1)
S_ARMS_1M = S_ARMS + ["nosink-5s", "nosink-20s"]
S_REF = {"statsd": {"1m": "nosink-5s"}, "dogstatsd-buf": {"1m": "nosink-5s"}, "otlp": {"1m": "nosink-20s"}}
# about 8 rounds on the unloaded S rungs; a Latin order balances only in whole squares,
# so 10 (two squares of 5 arms) at 100k and 7 (one square of 7 arms) at 1M
S_ROUNDS = {"100k": 10, "1m": 7}
OTLP_MAX_POINTS = 10000  # data points per OTLP request: under the collector's 4 MiB message limit
DOG_MAX_BYTES = 1432

# ---------------------------------------------------------------- evidence


def zero(stat, scope="field"):
    return {"stat": stat, "scope": scope, "equals": 0, "tol_abs": 0}


def ev_common(k, rung, cal, primed=True, otlp=False):
    """N, clusters, priming, fd limit, log; calibrated counts when there is a calibration."""
    out = [{"stat": "active_clusters", "scope": "field", "equals": k + 1 + (1 if otlp else 0), "tol_abs": 0,
            "label": "clusters: the generated ones, the origin%s" % (" and the collector" if otlp else "")},
           zero("gen_cx_connect_fail"), zero("gen_cx_overflow"),
           zero("gen_cx_active_pre", "field"),
           {"stat": "nofile_soft", "scope": "field", "min": 4 * k + 4096, "label": "fd limit >= 4 x clusters + 4096"},
           zero("envoy_log_emfile"),
           zero("dropped_stat_flushes_delta")]
    if primed:
        out += [{"stat": "prime.ok", "scope": "field", "equals": k, "tol_abs": 0, "label": "one 200 per cluster"},
                zero("prime.non200"), zero("prime.errors")]
        c = (cal or {}).get(rung) or {}
        if c.get("used_total"):
            out.append({"stat": "used_total", "scope": "field", "per_request": c["used_total"], "tol": 0.01,
                        "label": "used stats within 1% of the calibration"})
    else:
        out += [{"stat": "primed", "scope": "field", "equals": False},
                {"stat": "used_total", "scope": "field", "ref": {"arm": "self"}, "tol": 0.01,
                 "label": "used stats (cold) as in the smoke"}]
    c = (cal or {}).get(rung) or {}
    if not primed:
        # an unprimed store lacks the stats a first request creates: N as in the cold smoke
        out.append({"stat": "stats_total", "scope": "field", "ref": {"arm": "self"}, "tol": 0.005,
                    "label": "N (cold) as in the smoke, +/-0.5%"})
    elif c.get("stats_total"):
        out.append({"stat": "stats_total", "scope": "field", "per_request": c["stats_total"], "tol": 0.005,
                    "label": "N within 0.5% of the calibration"})
    return out


def ev_periodic(interval, visible=True):
    out = [{"stat": "uptime.error_s", "scope": "field", "max": interval + 1.0,
            "label": "server.uptime advanced with the clock between the two reads"}]
    if visible:
        out.append({"stat": "main.burst_count_error", "scope": "field", "max": 1,
                    "label": "flush bursts in the window as the interval says, +/-1"})
    return out


EV_FLUSH_OFF = [{"stat": "main.bursts", "scope": "field", "max": 0, "label": "no main-thread burst in the window"},
                {"stat": "flush_interval_s", "scope": "field", "absent": True}]
# Between two quiescent points (no flush in progress, the sink's queue read empty) the
# datagrams are a whole number n of flushes (n = the nearest whole number of used-line
# counts); per flush they are the used counter and gauge lines within 1% (the smoke showed
# a flush sending 16 to 20 lines more than the used-only count, 0.05% to 0.6%), and n is
# the number of flushes the span holds by the measured period, +/-1 (where one exists).
EV_STATSD = [{"stat": "udp.sent_per_flush", "scope": "field", "per": "field:used_cg_lines", "per_request": 1.0,
              "tol": 0.01, "label": "datagrams per whole flush = used counters and gauges, +/-1%"},
             {"stat": "udp.fit.n_error", "scope": "field", "max": 1,
              "label": "that number of flushes as the span and the measured period say, +/-1"},
             {"stat": "udp.drop_share", "scope": "field", "max": 0.01, "label": "drops under 1%"}]
TOP_RUNG_MAIN = {"stat": "main_over_busiest_other", "scope": "field", "min": 10,
                 "label": "the main thread is the busiest thread by a factor of 10 (idle statsd leg, top rung)"}
# T5: both quiescent points held, and the flushes between them counted whole (no burst crosses
# a quiescent point); the per-flush figures divide by that count
EV_QUIESCENT = [{"stat": "quiesce.before_ok", "scope": "field", "equals": True, "label": "quiescent point before"},
                {"stat": "quiesce.after_ok", "scope": "field", "equals": True, "label": "quiescent point after"},
                zero("span_flushes.partial"),
                {"stat": "span_flushes.n", "scope": "field", "min": 2, "label": "at least two whole flushes"}]
EV_DOG = EV_QUIESCENT + [
    {"stat": "udp.sent_per_flush", "scope": "field", "ref": {"arm": "self"}, "tol": 0.01,
     "label": "datagrams per whole flush as in the smoke, +/-1%"},
    {"stat": "udp.span_fit.n_error", "scope": "field", "max": 1,
     "label": "whole flushes counted as the span and the measured period say, +/-1"},
    {"stat": "udp.drop_share", "scope": "field", "max": 0.01, "label": "drops under 1%"}]
EV_OTLP = EV_QUIESCENT + [
    {"stat": "collector_delta.accepted_metric_points_per_flush", "scope": "field", "per": "field:used_total",
     "per_request": 1.0, "tol": 0.01, "label": "metric points per whole flush = used stats, +/-1%"},
    {"stat": "collector_delta.fit.n_error", "scope": "field", "max": 1,
     "label": "the whole flushes the points hold within one of the flushes counted in the span (one in flight)"},
    {"stat": "collector_delta.fit.residual", "scope": "field", "max": 0.01,
     "label": "points are whole flushes of the used stats (residual under 1% of one flush): no loss"},
    {"stat": "collector_delta.settled", "scope": "field", "equals": True,
     "label": "collector read settled at both quiescent points"},
    zero("collector_delta.refused_metric_points")]
EV_PROM = [{"stat": "prom.all_200", "scope": "field", "equals": True},
           {"stat": "prom.lines_p50", "scope": "field", "ref": {"arm": "self"}, "tol": 0.005},
           {"stat": "prom.count_error", "scope": "field", "max": 1}]


# ---------------------------------------------------------------- configs

def arm(box, name, settings, ev, **extra):
    a = {"name": name, "binaries": json.loads(json.dumps(box["binaries"])), "settings": settings, "evidence": ev}
    a.update(extra)
    return a


def base_cfg(box, name):
    return {
        "name": name, "machine_label": box["machine_label"], "workdir": RUNS, "box": box,
        "envoy": {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True},
        "cpus": dict(box["cpus"]),
        "client": {"binary": box["client_binary"], "concurrency": 16, "connections_per_worker": 32, "warmup_s": 5,
                   "duration_s": 25, "idle_strategy": "poll",
                   "extra_args": ["--prefetch-connections", "--max-pending-requests", "1000",
                                  "--experimental-h1-connection-reuse-strategy", "lru"]},
        "measure": {"lead_in_s": 2, "window_s": WINDOW_S, "perf": box["perf"], "main_perf_events": box["perf_events"],
                    "main_sample_s": 0.02},
        "idle": {"max_load1": 8.0, "max_busy_pct": 2.0},
        "origin": {"mode": "docker", "image": box["origin_image"], "platform": box["image_platform"], "port": 8092,
                   "workers": 8, "prime_file": True, "worker_connections": 65536, "worker_rlimit_nofile": 200000},
        "collector": {"image": box["collector_image"], "platform": box["image_platform"], "port": 4317,
                      "metrics_port": 8888, "metrics": True},
        "stats_sink": {"port": SINK_PORT, "rcvbuf": 268435456, "sample_every": 1},
        "order": "latin", "order_seed": ORDER_SEED, "adaptive": False,
        "primary_metric": "main_ms_per_s", "comparisons": "base",
    }


def idle_shape(rung, cal):
    c = (cal or {}).get(rung) or {}
    sh = {"name": "idle-" + rung, "path": "/idle", "kind": "idle", "rps": 0, "bursts_visible": rung != "10k",
          "ready_timeout_s": c.get("ready_timeout_s", 60 if rung in ("10k", "100k") else 180),
          "admin_timeout_s": c.get("admin_timeout_s", 30 if rung in ("10k", "100k") else 120),
          "settle_s": c.get("settle_s", 3.0)}
    return sh


def stats_set(k, **kw):
    s = {"stats_clusters": {"count": k, "seed": ORDER_SEED, "idle_timeout_s": 1}}
    s.update(kw)
    return s


def rung_arms(box, k, rung, cal, names):
    c = (cal or {}).get(rung) or {}
    visible = rung != "10k"  # at 10k a flush is under the sampler's 20 ms resolution
    sd_int = c.get("statsd_interval_s", INTERVAL_S)
    dog_int = S_INTERVALS.get(rung, {}).get("dogstatsd-buf", INTERVAL_S)
    otlp_int = S_INTERVALS.get(rung, {}).get("otlp", INTERVAL_S)
    otlp_win = S_WINDOWS.get(rung, {}).get("otlp")
    every = {
        "flush-off": lambda: arm(box, "flush-off", stats_set(k, stats_flush={"on_admin": True}),
                                 ev_common(k, rung, cal) + EV_FLUSH_OFF),
        "flush-off-A2": lambda: arm(box, "flush-off-A2", stats_set(k, stats_flush={"on_admin": True}),
                                    ev_common(k, rung, cal) + EV_FLUSH_OFF),
        "nosink": lambda: arm(box, "nosink", stats_set(k, stats_flush={"interval_s": INTERVAL_S}),
                              ev_common(k, rung, cal) + ev_periodic(INTERVAL_S, visible)),
        "nosink-A2": lambda: arm(box, "nosink-A2", stats_set(k, stats_flush={"interval_s": INTERVAL_S}),
                                 ev_common(k, rung, cal) + ev_periodic(INTERVAL_S, visible)),
        "nosink-5s": lambda: arm(box, "nosink-5s", stats_set(k, stats_flush={"interval_s": 5}),
                                 ev_common(k, rung, cal) + ev_periodic(5, visible) + EV_QUIESCENT),
        "nosink-20s": lambda: arm(box, "nosink-20s", stats_set(k, stats_flush={"interval_s": 20}),
                                  ev_common(k, rung, cal) + ev_periodic(20, visible) + EV_QUIESCENT, window_s=60),
        "statsd": lambda: arm(box, "statsd", stats_set(k, stats_flush={"interval_s": sd_int},
                                                       stats_sink={"kind": "statsd"}),
                              ev_common(k, rung, cal) + ev_periodic(sd_int, visible) + EV_STATSD
                              + ([TOP_RUNG_MAIN] if rung == RUNGS[-1][0] else [])),
        "dogstatsd-buf": lambda: arm(box, "dogstatsd-buf", stats_set(
            k, stats_flush={"interval_s": dog_int},
            stats_sink={"kind": "dog_statsd", "max_bytes_per_datagram": DOG_MAX_BYTES}),
            ev_common(k, rung, cal) + ev_periodic(dog_int, visible) + EV_DOG),
        "otlp": lambda: arm(box, "otlp", stats_set(k, stats_flush={"interval_s": otlp_int}, stats_sink={
            "kind": "otlp", "max_data_points_per_request": OTLP_MAX_POINTS}),
            ev_common(k, rung, cal, otlp=True) + ev_periodic(otlp_int, visible) + EV_OTLP,
            **({"window_s": otlp_win} if otlp_win else {})),
        "prom": lambda: arm(box, "prom", stats_set(k, stats_flush={"interval_s": INTERVAL_S}),
                            ev_common(k, rung, cal) + ev_periodic(INTERVAL_S, visible) + EV_PROM, prom_scrape_s=5),
        "statsd-5s": lambda: arm(box, "statsd-5s", stats_set(k, stats_flush={"interval_s": 5},
                                                             stats_sink={"kind": "statsd"}),
                                 ev_common(k, rung, cal) + ev_periodic(5, visible) + EV_STATSD, window_s=30),
        "statsd-cold": lambda: arm(box, "statsd-cold", stats_set(k, stats_flush={"interval_s": INTERVAL_S},
                                                                 stats_sink={"kind": "statsd"}),
                                   ev_common(k, rung, cal, primed=False) + ev_periodic(INTERVAL_S, visible)
                                   + EV_STATSD, prime=False),
        "nosink-cold": lambda: arm(box, "nosink-cold", stats_set(k, stats_flush={"interval_s": INTERVAL_S}),
                                   ev_common(k, rung, cal, primed=False) + ev_periodic(INTERVAL_S, visible),
                                   prime=False),
    }
    return [every[n]() for n in names]


CAL_KEYS = ("stats_total", "used_total", "settle_s", "ready_timeout_s", "admin_timeout_s")


def rung_calibrated(cal, rung):
    """A rung is calibrated only when its calibration produced every number the configs use."""
    c = (cal or {}).get(rung) or {}
    return all(c.get(k) is not None for k in CAL_KEYS)


MFIX_RUNGS = [("10k", 100), ("100k", 1000), ("1m", 10000)]
MFIX_SEED = 32


def mfix_arms(box, k, rung, cal):
    """nosink and statsd on each of the two builds, and a second copy of base nosink."""
    fb = box["fix_binaries"]
    c = (cal or {}).get(rung) or {}
    visible = rung != "10k"
    sd_int = c.get("statsd_interval_s", INTERVAL_S)
    common = [it for it in ev_common(k, rung, None) if it.get("stat") not in ("stats_total", "used_total")] + [
        {"stat": "stats_total", "scope": "field", "ref": {"arm": "self"}, "tol": 0.005,
         "label": "N as in this build's smoke, +/-0.5%"},
        {"stat": "used_total", "scope": "field", "ref": {"arm": "self"}, "tol": 0.01,
         "label": "used stats as in this build's smoke, +/-1%"}]
    out = []
    for name, build, sink in (("nosink-main", "main", None), ("nosink-top", "top", None),
                              ("statsd-main", "main", "statsd"), ("statsd-top", "top", "statsd"),
                              ("nosink-main-A2", "main", None)):
        st = stats_set(k, stats_flush={"interval_s": sd_int if sink else INTERVAL_S})
        ev = common + ev_periodic(sd_int if sink else INTERVAL_S, visible)
        if sink:
            st["stats_sink"] = {"kind": "statsd"}
            ev = ev + EV_STATSD + ([TOP_RUNG_MAIN] if rung == RUNGS[-1][0] else [])
        a = {"name": name, "binaries": {box["arch"]: dict(fb[build])}, "settings": st, "evidence": ev}
        out.append(a)
    return out


def configs(box, cal=None):
    out = {}

    def cfg(fname, name, rung, k, arms, shapes, **kw):
        c = base_cfg(box, name)
        arms = rung_arms(box, k, rung, cal, arms) if rung else arms
        c.update(base_arm=arms[0]["name"], arms=arms, shapes=shapes)
        if not rung_calibrated(cal, rung or "100k"):
            c["uncalibrated"] = True
        c.update(kw)
        out[fname] = c
        return c

    for rung, k in RUNGS + [PROBE, PROBE_10M]:
        cfg("cal-%s.json" % rung, "sf-cal-" + rung, rung, k, ["nosink", "statsd"], [idle_shape(rung, cal)],
            rounds=1, rounds_block=1, rounds_max=1, smoke=True, evidence_mode="record")
    for rung, k in RUNGS:
        if rung in ("10k", "300k"):
            # the smoke runs every arm of run M at these rungs too, so each arm's evidence is checked
            # at its own rung before the queue
            cfg("smoke-m-%s.json" % rung, "sf-smoke-m-" + rung, rung, k, ["flush-off", "nosink", "statsd", "nosink-A2"],
                [idle_shape(rung, cal)], rounds=1, rounds_block=1, rounds_max=1, smoke=True, evidence_mode="record")
        cfg("m-%s.json" % rung, "sf-m-" + rung, rung, k, ["flush-off", "nosink", "statsd", "nosink-A2"],
            [idle_shape(rung, cal)], rounds=4, rounds_block=4, rounds_max=4)
    for rung, k in (("100k", 1000), ("1m", 10000)):
        allarms = ["flush-off", "nosink", "nosink-A2", "statsd", "dogstatsd-buf", "otlp", "prom", "statsd-5s",
                   "statsd-cold", "nosink-cold"]
        cfg("smoke-%s.json" % rung, "sf-smoke-" + rung, rung, k, allarms, [idle_shape(rung, cal)],
            rounds=1, rounds_block=1, rounds_max=1, smoke=True, evidence_mode="record")
        # run S: the sinks at the two rungs, with the A/A; 5 rounds (one Latin square of 5 arms)
        sarms = S_ARMS_1M if rung == "1m" else S_ARMS
        cfg("smoke-s-%s.json" % rung, "sf-smoke-s-" + rung, rung, k, sarms, [idle_shape(rung, cal)],
            rounds=1, rounds_block=1, rounds_max=1, smoke=True, evidence_mode="record")
        cfg("s-%s.json" % rung, "sf-s-" + rung, rung, k, sarms, [idle_shape(rung, cal)],
            rounds=S_ROUNDS[rung], rounds_block=S_ROUNDS[rung], rounds_max=S_ROUNDS[rung], comparisons="base",
            s_refs={a: S_REF.get(a, {}).get(rung, "nosink") for a in sarms if a not in ("nosink", "nosink-A2")
                    and not a.startswith("nosink-")})
    # 4 rounds (one Latin square) rather than 3, so every arm sits in every position once
    cfg("x-1m.json", "sf-x-1m", "1m", 10000, ["statsd", "statsd-5s", "statsd-cold", "nosink-cold"],
        [idle_shape("1m", cal)], rounds=4, rounds_block=4, rounds_max=4)
    # run W: the 4 KB proxied shape under load at 100k, default 5 s interval
    c100 = (cal or {}).get("100k") or {}
    wsh = {"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200,
           "ready_timeout_s": c100.get("ready_timeout_s", 60), "admin_timeout_s": c100.get("admin_timeout_s", 30),
           "pre_window_settle_s": c100.get("settle_s", 3.0)}
    w_ev = [zero("gen_cx_connect_fail"), {"stat": "prime.ok", "scope": "field", "equals": 1000, "tol_abs": 0},
            {"stat": "nofile_soft", "scope": "field", "min": 4 * 1000 + 4096}]
    # flushes over the window: none without the timer, at least 3 at 5 s in 20 s with it
    w_off = [{"stat": "main.bursts", "scope": "field", "max": 0, "label": "no flush in the window"}]
    w_on = [{"stat": "main.bursts", "scope": "field", "min": 3, "label": "at least 3 flushes in the window"}]
    w_statsd = [{"stat": "udp.drop_share", "scope": "field", "max": 0.01},
                {"stat": "udp.datagrams_per_request", "scope": "field", "min": 1.0,
                 "label": "per-request statsd datagrams (histogram values) present"},
                {"stat": "udp.datagrams_per_request", "scope": "field", "ref": {"arm": "self"}, "tol": 0.1,
                 "label": "datagrams per request as in the smoke, +/-10%"}]
    warms = [arm(box, "flush-off", stats_set(1000, stats_flush={"on_admin": True}), w_ev + w_off),
             arm(box, "nosink", stats_set(1000), w_ev + w_on),
             arm(box, "statsd", stats_set(1000, stats_sink={"kind": "statsd"}), w_ev + w_on + w_statsd),
             arm(box, "flush-off-A2", stats_set(1000, stats_flush={"on_admin": True}), w_ev + w_off)]
    w = cfg("w.json", "sf-w", None, 1000, warms, [wsh], rounds=8, rounds_block=8, rounds_max=8,
            primary_metric="cycles_total", confirmatory=[["statsd", "flush-off"]])
    # v2 timings, with the settle after the pre-window read inside the client's run
    w["client"]["duration_s"] = 28
    w["measure"].update(main_sampler=True, per_thread=True)
    # run S under load (the worker-side cost of each sink): run W's shape and rung (1,000
    # clusters, about 118k stats, 5,200 req/s, default 5 s interval) with every sink of run S;
    # nosink is the reference, nosink-A2 the A/A; 10 rounds (two Latin squares of 5 arms)
    w_dog = [{"stat": "udp.drop_share", "scope": "field", "max": 0.01},
             {"stat": "udp.datagrams_per_request", "scope": "field", "ref": {"arm": "self"}, "tol": 0.1,
              "label": "datagrams per request as in the smoke, +/-10%"}]
    w_otlp = [zero("collector_delta.refused_metric_points"),
              {"stat": "collector_delta.accepted_metric_points", "scope": "field", "min": 1,
               "label": "the collector accepted points in the window"}]
    swarms = [arm(box, "nosink", stats_set(1000), w_ev + w_on),
              arm(box, "nosink-A2", stats_set(1000), w_ev + w_on),
              arm(box, "statsd", stats_set(1000, stats_sink={"kind": "statsd"}), w_ev + w_on + w_statsd),
              arm(box, "dogstatsd-buf", stats_set(1000, stats_sink={"kind": "dog_statsd",
                                                                    "max_bytes_per_datagram": DOG_MAX_BYTES}),
                  w_ev + w_on + w_dog),
              arm(box, "otlp", stats_set(1000, stats_sink={"kind": "otlp", "max_data_points_per_request": OTLP_MAX_POINTS}),
                  w_ev + w_on + w_otlp)]
    for fn, name, kw in (("sw.json", "sf-sw", dict(rounds=10, rounds_block=10, rounds_max=10)),
                         ("smoke-sw.json", "sf-smoke-sw", dict(rounds=1, rounds_block=1, rounds_max=1, smoke=True,
                                                                evidence_mode="record"))):
        x = cfg(fn, name, None, 1000, json.loads(json.dumps(swarms)), [dict(wsh)], primary_metric="cycles_total",
                comparisons="base", **kw)
        x["client"]["duration_s"] = 28
        x["measure"].update(main_sampler=True, per_thread=True)
    # the 5 s fallback (decided from the smoke's drops): the rung's statsd arm is smoked again
    # at 5 s, and its check reads that leg instead of the 1 s one
    for rung, k in RUNGS:
        if ((cal or {}).get(rung) or {}).get("statsd_interval_s") == 5:
            cfg("smoke-statsd5-%s.json" % rung, "sf-smoke-statsd5-" + rung, rung, k, ["statsd", "nosink"],
                [idle_shape(rung, cal)], rounds=1, rounds_block=1, rounds_max=1, smoke=True,
                evidence_mode="record")
    if box.get("fix_binaries"):
        for rung, k in MFIX_RUNGS:
            for fn, name, kw in (("mfix-%s.json" % rung, "sf-mfix-" + rung, dict(rounds=5, rounds_block=5, rounds_max=5)),
                                 ("smoke-mfix-%s.json" % rung, "sf-smoke-mfix-" + rung,
                                  dict(rounds=1, rounds_block=1, rounds_max=1, smoke=True, evidence_mode="record"))):
                c = base_cfg(box, name)
                arms = mfix_arms(box, k, rung, cal)
                c.update(base_arm="nosink-main", arms=arms, shapes=[idle_shape(rung, cal)], order_seed=MFIX_SEED,
                         box_specific=True, **kw)
                if not rung_calibrated(cal, rung):
                    c["uncalibrated"] = True
                out[fn] = c
    sw = json.loads(json.dumps(w))
    sw.update(name="sf-smoke-w", rounds=1, rounds_block=1, rounds_max=1, smoke=True, evidence_mode="record")
    sw.pop("confirmatory")
    out["smoke-w.json"] = sw
    # the sibling row and the fix A/B template (not in this session's queue)
    sib_sh = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200},
              {"name": "fh", "path": "/fh", "kind": "direct_headers", "body_bytes": 128, "request_headers_added": 57,
               "response_headers_added": 52, "rps": 8000}]
    sib = cfg("sibling.json", "sf-sibling", None, 0, [
        arm(box, "base", {}, [{"stat": "http.ingress_http.downstream_rq_2xx", "scope": "leg", "min": 1}]),
        arm(box, "stats-reject", {"stats_reject_all": True},
            [{"stat": "reject_all", "scope": "config", "equals": True}])], sib_sh,
        rounds=12, rounds_block=12, rounds_max=12, order="abba", primary_metric="cycles_total", template=True,
        template_note="not runnable as it is: with every stat rejected the harness's response count (an Envoy "
                      "counter) does not exist; the row needs the count from the client first")
    sib["origin"].pop("prime_file")
    ab = cfg("ab-template.json", "sf-ab-template", "1m", 10000, ["nosink", "nosink-A2"], [idle_shape("1m", cal)],
             rounds=8, rounds_block=8, rounds_max=8, template=True,
             template_note="the fix A/B: add arms `base` and `fix` (own builds, sha256 pinned, built off the bench "
                           "box with upstream's release flags) and `official` (this release) beside base-A2; the "
                           "same configs then run at 100k and 1m with the nosink and the statsd setting")
    ab["arms"][0]["name"], ab["arms"][1]["name"] = "official", "base-A2"
    ab["base_arm"] = "official"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", action="append")
    ap.add_argument("--rungs")
    a = ap.parse_args()
    boxes = a.box or sorted(glob.glob(os.path.join(HERE, "boxes", "*.json")))
    cal = None
    if a.rungs:
        with open(a.rungs) as f:
            cal = json.load(f)
    for bp in boxes:
        with open(bp) as f:
            box = json.load(f)
        d = os.path.join(HERE, box["name"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "box.json"), "w") as f:
            json.dump(box, f, indent=1)
            f.write("\n")
        for fn, c in configs(box, cal).items():
            with open(os.path.join(d, fn), "w") as f:
                json.dump(c, f, indent=1)
                f.write("\n")
        print("%s: %d configs" % (box["name"], len(configs(box, cal))))


if __name__ == "__main__":
    main()
