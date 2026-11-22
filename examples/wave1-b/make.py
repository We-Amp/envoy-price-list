#!/usr/bin/env python3
"""Write the configs of wave 1 track B: two own builds of Envoy v1.40.2 against a control built the
same way.

    python3 examples/wave1-b/make.py [--box BOX_JSON] [--bins BINS_JSON]

Binaries (BINS_JSON, default bins.json next to this file): three own builds of tag v1.40.2 with
the same toolchain and release options (`-c opt --stripopt=--strip-all
--linkopt=-Wl,--compress-debug-sections=zlib`, //source/exe:envoy-static.stripped), each pinned by
sha256:
  control   v1.40.2 as tagged
  p1        statsd sink: the histogram samples of one event-loop turn sent as one datagram per
            thread, and a connected UDP socket (a candidate change)
  p2        request-header re-validation on the upstream encode path switched off (a ceiling,
            measurement only, never a candidate)

Configs (in a directory named after the box):
  smoke-b-statsd.json, b-statsd.json   run S's loaded shape (`sw`: 1,000 primed clusters, about
      118k stats, 4 KB proxied at 5,200 req/s, default 5 s flush interval, plain statsd sink):
      ctl-statsd (base), p1-statsd, ctl-statsd-A2 (the A/A); 6 rounds, two Latin squares of 3
  smoke-b-statsd-nosink.json, b-statsd-nosink.json   optional: the same plus ctl-nosink, so the
      sink's price against no sink can be read on our own build; 8 rounds (two Latin squares of 4)
  smoke-b-fl.json, b-fl.json   the `/fl` shape (57 request + 52 response headers added by the
      route, 64 KB proxied body), no stats sink: ctl (base), p2, ctl-A2; 6 rounds

Every smoke is one round of its run, evidence recorded; the run is checked against its frozen
smoke (run-b.sh).
"""

import argparse
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SF = os.path.join(HERE, "..", "stats-flush")
_spec = importlib.util.spec_from_file_location("sf_make", os.path.join(SF, "make.py"))
sf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sf)

RUNS = "~/epl/runs/wave1-b"
ORDER_SEED = 41
ROUNDS = 6           # two Latin squares of 3 arms
ROUNDS_NOSINK = 8    # two Latin squares of 4 arms
FL_RPS = int(os.environ.get("FL_RPS", "2000"))  # the smoke fallback lowers it once (chain-b.sh)


def binaries(bins, arm):
    b = bins[arm]
    if not b.get("source_sha256") or "PENDING" in b["source_sha256"]:
        raise SystemExit("bins.json: no sha256 for %s yet" % arm)
    return {"x86_64": {"binary": b["binary"], "source": b["source"], "source_sha256": b["source_sha256"]}}


def arm(bins, name, build, settings, ev):
    return {"name": name, "binaries": binaries(bins, build), "settings": settings, "evidence": ev,
            "build": build}


def statsd_configs(box, bins):
    w_ev = [sf.zero("gen_cx_connect_fail"), {"stat": "prime.ok", "scope": "field", "equals": 1000, "tol_abs": 0},
            {"stat": "nofile_soft", "scope": "field", "min": 4 * 1000 + 4096},
            {"stat": "main.bursts", "scope": "field", "min": 3, "label": "at least 3 flushes in the window"}]
    sink = [{"stat": "udp.drop_share", "scope": "field", "max": 0.01},
            {"stat": "udp.datagrams_per_request", "scope": "field", "ref": {"arm": "self"}, "tol": 0.1,
             "label": "datagrams per request as in the smoke, +/-10%"}]
    # fail closed on the build: the control sends every sample alone (about 4.2 datagrams per request
    # on the official build), the patched build batches them (about 2.2 expected: one worker datagram
    # per request plus the unchanged flush)
    ctl = [{"stat": "udp.datagrams_per_request", "scope": "field", "min": 3.5,
            "label": "control: one datagram per histogram sample (about 4.2 per request)"}]
    p1 = [{"stat": "udp.datagrams_per_request", "scope": "field", "max": 3.0,
           "label": "p1: samples batched per loop turn (about 2.2 per request expected)"},
          {"stat": "udp.datagrams_per_request", "scope": "field", "min": 1.0,
           "label": "p1: the flush and the batched samples still arrive"}]
    st = sf.stats_set(1000, stats_sink={"kind": "statsd"})
    arms3 = [arm(bins, "ctl-statsd", "control", st, w_ev + sink + ctl),
             arm(bins, "p1-statsd", "p1", st, w_ev + sink + p1),
             arm(bins, "ctl-statsd-A2", "control", st, w_ev + sink + ctl)]
    arms4 = arms3 + [arm(bins, "ctl-nosink", "control", sf.stats_set(1000), w_ev)]
    wsh = {"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200,
           "ready_timeout_s": 60, "admin_timeout_s": 30, "pre_window_settle_s": 3.0}
    out = {}
    for stem, arms, rounds in (("b-statsd", arms3, ROUNDS), ("b-statsd-nosink", arms4, ROUNDS_NOSINK)):
        for smoke in (True, False):
            c = sf.base_cfg(box, ("smoke-" if smoke else "") + stem)
            c.update(workdir=RUNS, order_seed=ORDER_SEED, base_arm="ctl-statsd", arms=json.loads(json.dumps(arms)),
                     shapes=[dict(wsh)], primary_metric="cycles_total", comparisons="base",
                     rounds=1 if smoke else rounds, rounds_block=1 if smoke else rounds,
                     rounds_max=1 if smoke else rounds)
            if smoke:
                c.update(smoke=True, evidence_mode="record")
            c["client"]["duration_s"] = 28
            c["measure"].update(main_sampler=True, per_thread=True)
            out[("smoke-" if smoke else "") + stem + ".json"] = c
    return out


def v2_configs(box, bins):
    """The v2 confirmation run: v2 with max_bytes_per_datagram 512 on plain statsd
    against the control with plain statsd, the control's A/A and a no-sink anchor; `sw` shape;
    8 rounds (two Latin squares of 4). The discard sink classes every datagram by its last line, so
    sample datagrams (ms) and flush datagrams (c, g) can be told apart."""
    w_ev = [sf.zero("gen_cx_connect_fail"), {"stat": "prime.ok", "scope": "field", "equals": 1000, "tol_abs": 0},
            {"stat": "nofile_soft", "scope": "field", "min": 4 * 1000 + 4096},
            {"stat": "main.bursts", "scope": "field", "min": 3, "label": "at least 3 flushes in the window"}]
    sink = [{"stat": "udp.drop_share", "scope": "field", "max": 0.01},
            {"stat": "udp.datagrams_per_request", "scope": "field", "ref": {"arm": "self"}, "tol": 0.1,
             "label": "datagrams per request as in the smoke, +/-10%"}]
    ctl = [{"stat": "udp.datagrams_per_request", "scope": "field", "min": 3.5,
            "label": "control: one datagram per metric (about 4.2 per request)"}]
    v2 = [{"stat": "udp.datagrams_per_request", "scope": "field", "max": 1.8,
           "label": "v2 at 512 bytes: samples and flush batched (about 1.2 per request expected)"},
          {"stat": "udp.datagrams_per_request", "scope": "field", "min": 0.8,
           "label": "v2: the batched samples still arrive"}]
    arms = [arm(bins, "ctl-statsd", "control", sf.stats_set(1000, stats_sink={"kind": "statsd"}), w_ev + sink + ctl),
            arm(bins, "v2-statsd-512", "v2",
                sf.stats_set(1000, stats_sink={"kind": "statsd", "max_bytes_per_datagram": 512}), w_ev + sink + v2),
            arm(bins, "ctl-statsd-A2", "control", sf.stats_set(1000, stats_sink={"kind": "statsd"}),
                w_ev + sink + ctl),
            arm(bins, "ctl-nosink", "control", sf.stats_set(1000), w_ev)]
    wsh = {"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200,
           "ready_timeout_s": 60, "admin_timeout_s": 30, "pre_window_settle_s": 3.0}
    out = {}
    for smoke in (True, False):
        c = sf.base_cfg(box, ("smoke-" if smoke else "") + "v2c")
        c.update(workdir=RUNS, order_seed=ORDER_SEED + 1, base_arm="ctl-statsd", arms=json.loads(json.dumps(arms)),
                 shapes=[dict(wsh)], primary_metric="cycles_total", comparisons="base",
                 rounds=1 if smoke else ROUNDS_NOSINK, rounds_block=1 if smoke else ROUNDS_NOSINK,
                 rounds_max=1 if smoke else ROUNDS_NOSINK)
        if smoke:
            c.update(smoke=True, evidence_mode="record")
        c["client"]["duration_s"] = 28
        c["measure"].update(main_sampler=True, per_thread=True, udp_classes=True)
        out[("smoke-" if smoke else "") + "v2c.json"] = c
    return out


def fl_configs(box, bins):
    sh = {"name": "fl", "path": "/fl", "kind": "proxied", "body_bytes": 65536, "rps": FL_RPS,
          "request_headers_added": 57, "response_headers_added": 52}
    ev = [{"stat": "http.ingress_http.downstream_rq_2xx", "scope": "leg", "min": 1}]
    arms = [arm(bins, "ctl", "control", {}, ev), arm(bins, "p2", "p2", {}, ev), arm(bins, "ctl-A2", "control", {}, ev)]
    out = {}
    for smoke in (True, False):
        c = sf.base_cfg(box, ("smoke-" if smoke else "") + "b-fl")
        for k in ("collector", "stats_sink"):
            c.pop(k, None)
        c["measure"].pop("main_sample_s", None)
        c["measure"].pop("main_perf_events", None)
        c["measure"]["per_thread"] = True
        c["client"]["duration_s"] = 28
        c.update(workdir=RUNS, order_seed=ORDER_SEED, base_arm="ctl", arms=json.loads(json.dumps(arms)),
                 shapes=[dict(sh)], primary_metric="cycles_total", comparisons="base",
                 rounds=1 if smoke else ROUNDS, rounds_block=1 if smoke else ROUNDS,
                 rounds_max=1 if smoke else ROUNDS)
        c["origin"].pop("prime_file", None)
        if smoke:
            c.update(smoke=True, evidence_mode="record")
        out[("smoke-" if smoke else "") + "b-fl.json"] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", default=os.path.join(SF, "boxes", "bench-x86_64.json"))
    ap.add_argument("--bins", default=os.path.join(HERE, "bins.json"))
    a = ap.parse_args()
    with open(a.box) as f:
        box = json.load(f)
    with open(a.bins) as f:
        bins = json.load(f)
    d = os.path.join(HERE, box["name"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "box.json"), "w") as f:
        json.dump(box, f, indent=1)
        f.write("\n")
    cfgs = {}
    cfgs.update(statsd_configs(box, bins))
    cfgs.update(fl_configs(box, bins))
    cfgs.update(v2_configs(box, bins))
    for fn, c in sorted(cfgs.items()):
        with open(os.path.join(d, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
    print("%s: %d configs" % (box["name"], len(cfgs)))


if __name__ == "__main__":
    main()
