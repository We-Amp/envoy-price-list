#!/usr/bin/env python3
"""The tail add-on after session W8-3 (requested 2026-11-24; not part of W8-3): W8-2's follow-up on w8-B.
Written before the first leg; the rules are in tail_check.py. Called by make.py (configs tail-*.json).

Binary w8-B carries w8-A's two UDP commits unchanged. In every w8-B arm here the relay write guard is FALSE and the
chunked guard is FALSE (a decision fixed before data); the two UDP guards are set per arm as W8-2 named its arms:
  h3-off       stop false, reuse false        h3-both-on   stop true, reuse true
  h3-reuse-on  stop false, reuse true          h3-official, h3-official-A2: the official binary, no runtime layer
Shape `s` over HTTP/3 (W8-2's: 4 KB proxied from nginx, 2,000 req/s, 16 client connections), W8-2's arms otherwise
(S2's h3 arm: TLS + QUIC listeners, the client's QUIC socket, its validity gates and evidence; W8-2's error items).

Part 1 (the QUIC code review's follow-up, "retransmissions with the stop guard", section 2): tail-p1-r1..r4, h3-off and
  h3-both-on, one leg each per config, order alternating by config (r1: off first), 10 s measured runs, 6 s window,
  the 5 s warm-up run as before, Envoy's QUIC statistics visitor ON with update_period 0.05 s (config only), so the
  retransmission counter moves within 50 ms of a probe. Counted from the harness's own snapshots: before the window
  (end-of-window absolute minus the window delta: warm-up plus the measured run's start), inside the window, after it
  (end of leg minus end of window: the last part of the run and its end).
Part 2: tail-c4, row C4 h3-reuse-on vs h3-off on s (the buffer-reuse commit alone), with the same-build pair
  h3-official-A2 vs h3-official; 4 arms x 8 rounds (two Williams squares, seed 851), the QUIC statistics visitor on
  in every arm (retransmitted and sent packets per leg; the visitor is in all four arms alike). No smoke and no
  frozen references (time): evidence recorded, every validity gate as W8-2's, bytes printed by tail_check.py.
"""
import copy
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


w2 = _load("w8w2_make_for_w8tail", os.path.join(ROOT, "examples", "wave8w2", "make.py"))

# arm -> (build, (stop, reuse) or None)
TARMS = {"h3-official": ("official", None), "h3-official-A2": ("official", None), "h3-off": ("w8-B", (False, False)),
         "h3-both-on": ("w8-B", (True, True)), "h3-reuse-on": ("w8-B", (False, True))}
P1 = ["h3-off", "h3-both-on"]
C4 = ["h3-official", "h3-official-A2", "h3-off", "h3-reuse-on"]
C4_ROUNDS, C4_SEED = 8, 851
UPDATE_MS = 50


def tguards(a):
    g = TARMS[a][1]
    return {"ch": -1, "st": -1, "ru": -1, "wr": -1} if g is None else {"ch": 0, "st": int(g[0]), "ru": int(g[1]), "wr": 0}


TGUARDS = {a: tguards(a) for a in TARMS}


def build(mk, name, update_ms=None):
    bld, g = TARMS[name]
    b = mk.BINS[bld]
    src = "h3-off" if g is not None else "h3-official"
    a = w2.arm(src, refs=False, stats=True)
    a["name"] = name
    a.update(binary=b["binary"], source=b["source"], source_sha256=b["source_sha256"], build=bld)
    st = dict(a["settings"])
    st["quic"] = {"stats": True} if update_ms is None else {"stats": True, "stats_update_period_ms": int(update_ms)}
    st.pop("runtime", None)
    code = tguards(name)
    if g is not None:
        st["runtime"] = {mk.CH: False, mk.ST: bool(g[0]), mk.RU: bool(g[1]), mk.WR: False}
    a["settings"] = st
    names = {1: "true", 0: "false", -1: "not set"}
    ev = [{"stat": "runtime_%s.%s" % (when, k), "scope": "field", "equals": code[k], "tol_abs": 0,
           "label": "admin /runtime at the leg's %s: %s is %s" % (when, mk.RUNTIME_KEYS[k], names[code[k]])}
          for when in ("start", "end") for k in ("ch", "st", "ru", "wr")]
    if g is None:
        ev += [{"stat": "layered_runtime", "scope": "config", "absent": True, "label": "no runtime layer in the config"},
               {"stat": "runtime.num_keys", "scope": "leg", "equals": 0, "tol_abs": 0, "label": "runtime.num_keys 0"}]
    else:
        ev += [{"stat": k, "scope": "config", "equals": v, "label": "the static runtime layer sets %s %s" % (k, str(v).lower())}
               for k, v in st["runtime"].items()]
        ev += [{"stat": "runtime.num_keys", "scope": "leg", "equals": 4, "tol_abs": 0, "label": "runtime.num_keys 4"}]
    a["evidence"] = mk.strip(a["evidence"]) + ev
    return a


def base(mk, name, arms, update_ms=None):
    c = w2.scored(name, w2.shape("s", w2.RATE_S), ["h3-official", "h3-off"])
    c["arms"] = [build(mk, n, update_ms) for n in arms]
    c["measure"] = dict(c["measure"], runtime_keys=dict(mk.RUNTIME_KEYS), leg_binary_sha256=True,
                        leg_end_histograms=r"^listener\.127\.0\.0\.1_10110\.quic_stats\.")
    c.pop("confirmatory", None)
    c.update(workdir=mk.RUNS, base_arm=arms[0], evidence_mode="record", rerun_invalid=0)
    return c


def configs(mk):
    out = {}
    for r in range(1, 5):
        arms = P1 if r % 2 else P1[::-1]
        c = base(mk, "tail-p1-r%d" % r, arms, UPDATE_MS)
        c.update(smoke=True, order="fixed", rounds=1, rounds_block=1, rounds_max=1, comparisons="base")
        c.pop("short_run_note", None)
        c["client"] = dict(c["client"], duration_s=10)
        c["measure"] = dict(c["measure"], window_s=6)
        out[c["name"]] = c
    c = base(mk, "tail-c4", C4)
    c.update(order="williams", order_seed=C4_SEED, rounds=C4_ROUNDS, rounds_block=C4_ROUNDS, rounds_max=C4_ROUNDS, adaptive=False,
             comparisons="all_pairs", confirmatory=[["h3-reuse-on", "h3-off"]],
             short_run_note="short run: %d fixed rounds in Williams order, run with --allow-short" % C4_ROUNDS)
    out["tail-c4"] = c
    return copy.deepcopy(out)
