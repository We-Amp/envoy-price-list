#!/usr/bin/env python3
"""A flip block. One Envoy process, one continuous client, a runtime guard flipped
through admin POST /runtime_modify in the gap between windows.

    python3 loop/flipblock.py CONFIG [--out RUN_DIR] [--set k=v ...]
    python3 loop/flipblock.py CONFIG --check      # validate and print the plan, start nothing

A flip-block config is an experiment config with one arm and one shape (single_arm, smoke, and `template`, so
`epl run` refuses it) plus a `flip` section:

    flip.key              the runtime key (envoy.*), flipped in the arm's admin layer (settings.runtime_admin_layer
                          true; the key must not also be in the arm's static `runtime`: one source of truth)
    flip.values           {label: value}; a scored block uses the labels A and B
    flip.order            the window order, pairs separated by spaces ("AB BA BA AB AB BA BA AB")
    flip.counterbalanced  true: the order must be counterbalanced_order(pairs) (AB BA BA AB, repeated)
    flip.kind             "aa" (both labels the same value) | "control" | "timeline" (non-scored, per-interval
                          counts) | "pairs" (non-scored, whole windows: the smoke's A/A pair then control pair)
    flip.window_s         the perf window (s); flip.gap_s the gap between windows (s, >= 1)
    flip.warm_s           the client's warm-up before the first window (and per window when cycling)
    flip.cycle_connections  true: a new client process per window, started after the flip (a guard read when a
                          connection is built); false: one client for the whole block
    flip.perf_interval_ms  timeline blocks: perf stat -I (per-interval counts kept, nothing enters a gate)
    flip.rate_tolerance   the SUT 2xx in each window within this share of rate x window (default 0.005)
    flip.marker_min       X (e.g. 4,450): the flip marker, instructions:u per request A - B, must reach it
                          in a control block and in the smoke's control pair
    flip.aa_marker_max    the A/A bound (e.g. 1,110, X/4): the mean |A - B| of an A/A block (and the smoke's A/A
                          pair) must stay under it
    flip.gates            optional per-block lines, applied to the summary (Exploratory): max_sd_lp,
                          reference_lp [lo, hi]; the pooled build decision is read over blocks
    flip.gating           false: a non-gating block (flip-rw20): X and the A/A bound are not required
    flip.window_items     "http" (default: shape s's items) | "bulk" (the bulk items, a tcp_proxy arm: flip-rw20)
    flip.split_bound_lp   kind "split": the bound (log points) on d = 100 ln(c_B / c_A), SUT cycles per request
                          with two client processes at half the load each (B) against one (A); beyond it the client
                          is flagged as the bottleneck. No runtime key: values {"A": 1, "B": 2} are process counts,
                          cycle_connections true (each window starts its own client processes)
                          Each of the two B processes runs half the workers at the same rate and connections per
                          worker, on its own half of cpus.client (clientcheck.cpu_halves)
    flip.split_max_client_cpus_per_worker  kind "split": every client process's CPU per worker in every window (from
                          /proc/<pid>/stat) must stay at or under it; unread fails the window

Per window: the SUT count read q0, perf stat -p <envoy> --timeout W on the tools CPU with its CLOCK_MONOTONIC start
logged, the read q1; in the gap: POST the next window's value, read /runtime and require it, log both instants.
A window is invalid when the client died (at q1, or within 1 s after), the SUT 2xx miss the rate, any non-2xx or
overflow counted, perf multiplexed or incomplete, the SUT CPUs had foreign or sibling load, or /runtime did not show
the window's value. A block with an invalid window is invalid as a whole (no replacement inside a block). Every
figure is "Exploratory, steering only": the t interval at df n-1, no 0.34 widening.
"""

import argparse
import http.client
import signal
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from epl import clientcheck, experiment, leg, nighthawk, stats, sysprobe, validity  # noqa: E402

FLIP_KEYS = {"key", "values", "order", "counterbalanced", "kind", "window_s", "gap_s", "warm_s", "lead_in_s",
             "cycle_connections", "perf_interval_ms", "rate_tolerance", "marker_min", "aa_marker_max", "gates",
             "hang_factor", "gating", "window_items", "split_bound_lp", "split_max_client_cpus_per_worker",
             "acts_stats"}
# a tcp_proxy block's (flip-rw20's) per-window items are the `bulk` per-leg items, not `s`'s:
# tcp_proxy has no HTTP stats; responses are counted at the origin. Window deltas that must be 0 (no connection made
# or lost inside a window), and counters that must stay 0 over the block (examples/wave7s5 NO_ERRORS and relay_ev,
# with the bulk exceptions: the flow-control counters are printed, not gated)
BULK_WINDOW_ZEROS = ("cluster.origin.upstream_cx_total", "cluster.origin.upstream_cx_destroy",
                     "cluster.origin.upstream_cx_destroy_remote", "cluster.origin.upstream_cx_destroy_local",
                     "listener.127.0.0.1_10110.downstream_cx_destroy", "listener.127.0.0.1_10110.downstream_cx_total")
BULK_BLOCK_ZEROS = ("cluster.origin.upstream_cx_connect_fail", "cluster.origin.upstream_cx_connect_timeout",
                    "cluster.origin.upstream_cx_overflow", "cluster.origin.upstream_cx_protocol_error",
                    "cluster.origin.upstream_rq_timeout", "listener.127.0.0.1_10110.downstream_cx_overflow",
                    "listener.127.0.0.1_10110.downstream_cx_overload_reject", "server.envoy_bug_failures",
                    "server.debug_assertion_failures", "tcp.relay.idle_timeout", "tcp.relay.downstream_cx_no_route")
# the stats the bulk items read that the fixed filter leaves out (the bulk items' stat_filter_extra)
BULK_STAT_EXTRA = (r"^tcp\.relay\.|^listener\.127\.0\.0\.1_10110\.downstream_cx_(destroy|overflow|overload_reject)$|"
                   r"^cluster\.origin\.upstream_(cx_connect_timeout|cx_destroy_remote|cx_destroy_local)$|"
                   r"^server\.(envoy_bug_failures|debug_assertion_failures)$")
# per block, over the block (a 0% sampling arm sends nothing to the collector)
COLLECTOR_BLOCK_STATS = ("cluster.otel_collector.upstream_rq_total", "cluster.otel_collector.upstream_cx_connect_fail")
KINDS = ("aa", "control", "timeline", "pairs", "split")
EXPLORATORY = "Exploratory, steering only"


# ---------------------------------------------------------------- order and pairing

def counterbalanced_order(pairs):
    """AB BA BA AB, repeated: a linear drift cancels over every four windows."""
    return " ".join("AB" if i % 4 in (0, 3) else "BA" for i in range(int(pairs)))


def parse_order(text):
    """'AB BA' -> ['A', 'B', 'B', 'A']; pairs are windows (1, 2), (3, 4), ..."""
    if not isinstance(text, str):
        raise ValueError("flip.order must be a string of pairs such as 'AB BA'")
    groups = text.split()
    if not groups or any(len(g) != 2 for g in groups):
        raise ValueError("flip.order must be pairs of two labels separated by spaces, got %r" % text)
    return [c for g in groups for c in g]


def runtime_text(v):
    """A runtime value as admin /runtime_modify takes it and /runtime shows it."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


# ---------------------------------------------------------------- validation (fail closed)

def flip_errors(exp):
    """Everything a flip block needs, checked before anything starts."""
    errs = []
    f = exp.get("flip")
    if not isinstance(f, dict):
        return ["a flip-block config needs a flip section"]
    bad = sorted(set(f) - FLIP_KEYS)
    if bad:
        errs.append("flip: unknown keys %s" % bad)
    arms = exp.get("arms") or []
    if len(arms) != 1 or not exp.get("single_arm") or not exp.get("smoke"):
        errs.append("a flip block has exactly one arm (single_arm true, smoke true)")
    if not exp.get("template"):
        errs.append("a flip-block config sets template true (epl run must refuse it; flipblock.py runs it)")
    shapes = [s for s in exp.get("shapes") or [] if s.get("kind") != "idle"]
    if len(exp.get("shapes") or []) != 1 or len(shapes) != 1:
        errs.append("a flip block has exactly one non-idle shape")
    key = f.get("key")
    split = f.get("kind") == "split"
    if split:
        errs += split_errors(exp)
    elif not (isinstance(key, str) and key.startswith("envoy.") and " " not in key):
        errs.append("flip.key must be a runtime key (envoy.*)")
    vals = f.get("values")
    if not isinstance(vals, dict) or not vals or not all(
            isinstance(k, str) and len(k) == 1 and isinstance(v, (bool, int, float, str)) for k, v in vals.items()):
        errs.append("flip.values maps one-letter labels to runtime values")
        vals = {}
    kind = f.get("kind")
    if kind not in KINDS:
        errs.append("flip.kind must be one of %s" % (KINDS,))
    try:
        order = parse_order(f.get("order"))
    except ValueError as ex:
        errs.append(str(ex))
        order = []
    if order:
        if any(x not in vals for x in order):
            errs.append("flip.order uses labels without a value: %s" % sorted(set(order) - set(vals)))
        if len(order) < 4:
            errs.append("flip.order needs at least 2 pairs")
        if kind in ("aa", "control"):
            if set(vals) != {"A", "B"}:
                errs.append("a scored block uses the labels A and B")
            if any(sorted(order[i:i + 2]) != ["A", "B"] for i in range(0, len(order), 2)):
                errs.append("every pair of a scored block has one A and one B window")
            if kind == "aa" and vals.get("A") != vals.get("B"):
                errs.append("an aa block writes the same value for A and B")
            if kind == "control" and vals.get("A") == vals.get("B"):
                errs.append("a control block writes different values for A and B")
        if f.get("counterbalanced") and " ".join(f["order"].split()) != counterbalanced_order(len(order) // 2):
            errs.append("flip.order is not the counterbalanced order %s" % counterbalanced_order(len(order) // 2))
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    if not (isinstance(f.get("window_s"), int) and not isinstance(f.get("window_s"), bool) and f["window_s"] >= 1):
        errs.append("flip.window_s must be whole seconds >= 1")
    if not (num(f.get("gap_s")) and f["gap_s"] >= 1.0):
        errs.append("flip.gap_s must be a number >= 1.0 (the POST, the /runtime read and the client check)")
    for k, lo in (("warm_s", 0), ("lead_in_s", 1)):
        if f.get(k) is not None and not (num(f[k]) and f[k] >= lo):
            errs.append("flip.%s must be a number >= %s" % (k, lo))
    if f.get("rate_tolerance") is not None and not (num(f["rate_tolerance"]) and 0 < f["rate_tolerance"] < 0.1):
        errs.append("flip.rate_tolerance must be a share in (0, 0.1)")
    if f.get("hang_factor") is not None and not (num(f["hang_factor"]) and f["hang_factor"] >= 1.0):
        errs.append("flip.hang_factor must be >= 1")
    if not isinstance(f.get("cycle_connections", False), bool):
        errs.append("flip.cycle_connections must be true or false")
    pi = f.get("perf_interval_ms")
    if pi is not None and not (isinstance(pi, int) and pi >= 100):
        errs.append("flip.perf_interval_ms must be whole ms >= 100")
    if kind == "timeline" and pi is None:
        errs.append("a timeline block sets flip.perf_interval_ms")
    if kind in ("aa", "control") and pi is not None:
        errs.append("perf_interval_ms is for timeline blocks only (scored blocks count each window whole)")
    wi = f.get("window_items", "http")
    if wi not in ("http", "bulk"):
        errs.append("flip.window_items must be http or bulk")
    tcp = bool(arms and experiment.arm_settings(arms[0]).get("tcp_proxy"))
    if wi == "bulk" and not (tcp and (exp.get("measure") or {}).get("responses_from") == "origin"):
        errs.append("flip.window_items bulk needs a tcp_proxy arm with measure.responses_from origin")
    if tcp and wi != "bulk":
        errs.append("a tcp_proxy arm has no HTTP stats: flip.window_items must be bulk (the bulk items)")
    if wi == "bulk" and BULK_STAT_EXTRA != (exp.get("measure") or {}).get("stat_filter_extra"):
        errs.append("flip.window_items bulk needs measure.stat_filter_extra = flipblock.BULK_STAT_EXTRA")
    if not isinstance(f.get("gating", True), bool):
        errs.append("flip.gating must be true or false")
    gating = f.get("gating", True) is not False
    mk = f.get("marker_min")
    if gating and kind in ("aa", "control", "pairs") and not (num(mk) and mk > 0):
        errs.append("a %s block needs flip.marker_min (X, instructions per request)" % kind)
    if mk is not None and not (num(mk) and mk > 0):
        errs.append("flip.marker_min must be a positive number")
    ab = f.get("aa_marker_max")
    if gating and kind in ("aa", "pairs") and not (num(ab) and ab > 0):
        errs.append("a %s block needs flip.aa_marker_max (the A/A bound, instructions per request)"
                    % kind)
    if ab is not None and not (num(ab) and ab > 0):
        errs.append("flip.aa_marker_max must be a positive number")
    g = f.get("gates") or {}
    if not isinstance(g, dict) or set(g) - {"max_sd_lp", "reference_lp"}:
        errs.append("flip.gates takes max_sd_lp and reference_lp")
    elif g.get("reference_lp") is not None and not (
            isinstance(g["reference_lp"], list) and len(g["reference_lp"]) == 2 and all(num(x) for x in g["reference_lp"])
            and g["reference_lp"][0] < g["reference_lp"][1]):
        errs.append("flip.gates.reference_lp is [lo, hi] in log points")
    if arms:
        st = experiment.arm_settings(arms[0])
        if st.get("runtime_admin_layer") is not True and not split:
            errs.append("the arm needs settings.runtime_admin_layer true (POST /runtime_modify needs an admin layer)")
        if isinstance(key, str) and key in (st.get("runtime") or {}):
            errs.append("flip.key %s is also in the arm's static runtime layer: one source of truth (the admin "
                        "layer)" % key)
        if st.get("two_hop"):
            errs.append("a flip block runs one Envoy (no two_hop)")
        if arms[0].get("client"):
            errs.append("a flip block uses the experiment's client (no arm client settings)")
    c = exp.get("client") or {}
    if c.get("recipe", "plain") != "plain" or c.get("lifetime", "duration") != "duration":
        errs.append("a flip block drives its client itself (--no-duration, one SIGTERM): leave client.recipe and "
                    "client.lifetime unset")
    m = exp.get("measure") or {}
    if m.get("latency") or m.get("burst") or m.get("perf_event_groups"):
        errs.append("a flip block takes none of measure.latency, burst, perf_event_groups")
    if len(m.get("perf") or []) != 1:
        errs.append("a flip block runs measure.perf itself: one perf binary, no wrapper")
    ev = m.get("perf_events") or leg.PERF_EVENTS
    names = set(ev.split(","))
    if "instructions:u" not in names or not ({"cycles:u", "cycles:k"} <= names or "cycles" in names):
        errs.append("the perf events need instructions:u (the flip marker) and the cycles")
    if "flip_tools" not in (exp.get("cpus") or {}):
        errs.append("cpus.flip_tools: the CPU(s) of the driver and perf")
    return errs


def split_errors(exp):
    """The split test (kind "split"): one client process (A) against two at half the load each (B), window pairs
    in one Envoy process, no runtime flip."""
    errs = []
    f = exp["flip"]
    if f.get("key") is not None:
        errs.append("a split block flips no runtime key (leave flip.key out)")
    if f.get("values") != {"A": 1, "B": 2}:
        errs.append("a split block's flip.values are {\"A\": 1, \"B\": 2} (client processes per window)")
    try:
        order = parse_order(f.get("order"))
    except ValueError:
        order = []
    if any(sorted(order[i:i + 2]) != ["A", "B"] for i in range(0, len(order), 2)):
        errs.append("every pair of a split block has one A and one B window")
    if f.get("cycle_connections") is not True:
        errs.append("a split block sets flip.cycle_connections true (each window starts its own client processes)")
    b = f.get("split_bound_lp")
    if not (isinstance(b, (int, float)) and not isinstance(b, bool) and b > 0):
        errs.append("a split block needs flip.split_bound_lp (log points > 0; set it from the in-process A/A)")
    g = f.get("split_max_client_cpus_per_worker")
    if not (isinstance(g, (int, float)) and not isinstance(g, bool) and 0 < g <= 1):
        errs.append("a split block needs flip.split_max_client_cpus_per_worker (a share of a CPU in (0, 1]): every "
                    "client process's CPU per worker is gated per window")
    sh = [x for x in exp.get("shapes") or [] if x.get("kind") != "idle"]
    c = exp.get("client") or {}
    if sh:
        try:
            clientcheck.split_rates(sh[0].get("rps", 0), c.get("concurrency", 4), c.get("connections_per_worker", 16))
        except (ValueError, TypeError) as ex:
            errs.append(str(ex))
    try:
        clientcheck.cpu_halves((exp.get("cpus") or {}).get("client", ""))
    except ValueError as ex:
        errs.append(str(ex))
    return errs


def load(path, overrides=None):
    exp = experiment.load(path, overrides)
    errs = experiment.validate(exp, allow_short=True) + flip_errors(exp)
    return exp, errs


def plan(exp):
    """(windows, planned seconds) of the block."""
    f = exp["flip"]
    order = parse_order(f["order"])
    warm = float(f.get("warm_s", exp["client"].get("warmup_s", 5)))
    lead = float(f.get("lead_in_s", exp["measure"]["lead_in_s"]))
    per = f["window_s"] + float(f["gap_s"])
    if f.get("cycle_connections"):
        # a new client per window, and its executed inode hashed after it ended (about 1 s)
        per += warm + lead + 2.0 + 1.0
    return order, 20.0 + warm + lead + len(order) * per


# ---------------------------------------------------------------- event log (evlog.py's line format)

class Evlog:
    """One line per event: <utc_iso_ms> <monotonic_ns> <event> <detail>, both clocks read together."""

    def __init__(self, path):
        self.f = open(path, "a")

    def __call__(self, event, detail=""):
        mono = time.monotonic_ns()
        wall = time.time_ns()
        iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(wall // 10 ** 9)) + ".%03dZ" % (wall // 10 ** 6 % 1000)
        self.f.write("%s %d %s %s\n" % (iso, mono, event, str(detail).replace("\n", " ")))
        self.f.flush()
        return mono / 1e9

    def close(self):
        self.f.close()


# ---------------------------------------------------------------- the box side (stand-ins replace it in tests)

class RealOps:
    """The block's processes and reads on the box, through the leg harness's helpers: Envoy started and checked
    as in a leg (RealBackend._start_envoy: taskset, ready, /proc exe), our own processes only (OwnProcesses), the
    admin reads of leg.py, the scheduler probes of sysprobe."""

    def __init__(self, exp, run_dir, log):
        self.exp = exp
        self.run_dir = run_dir
        self.log = log
        self.backend = leg.RealBackend(exp, run_dir, log)
        self.own = self.backend.own
        self.admin_port = exp["envoy"]["admin_port"]

    def preflight(self, shape):
        e = self.exp
        sut = sysprobe.parse_cpuset(e["cpus"]["sut"])
        ok, det, _ = sysprobe.wait_idle(e["idle"], self.own.pids(), log=self.log,
                                        watch_cpus=sut | sysprobe.siblings_of(sut))
        must_open = [e["origin"]["port"]] if shape["kind"] == "proxied" else []
        aenv = experiment.arm_envoy(e, e["arms"][0], self.run_dir)
        if aenv.get("tracing"):
            must_open.append(aenv["collector_port"])
        pok, pdet = sysprobe.port_preflight([e["envoy"]["listener_port"], self.admin_port], must_open)
        return ok and pok, {"idle": det, "ports": pdet}

    def start_envoy(self, arm, bootstrap):
        e = self.exp
        elog_path = os.path.join(self.run_dir, "logs", "envoy.log")
        aenv = experiment.arm_envoy(e, arm, self.run_dir)
        p, elog = self.backend._start_envoy(arm["binary"], bootstrap, e["cpus"]["sut"], e["envoy"]["workers"],
                                            self.admin_port, dict(arm.get("env") or {}), arm.get("extra_args", []),
                                            elog_path, nofile=leg.nofile_for(aenv, e))
        self._elog = (elog, elog_path)
        return p

    def stop_envoy(self, p):
        return self.backend._stop_envoy(p, self._elog[0], self._elog[1])["exit"]

    def exe_identity(self, pid, path):
        return leg.exe_identity(pid, path)

    def open_exe(self, pid):
        return leg.open_exe(pid)

    def cpus_ok(self, pid, want):
        return sysprobe.parse_cpuset(sysprobe.cpus_allowed(pid)) == sysprobe.parse_cpuset(want)

    def admin_get(self, path):
        return leg.admin_get(self.admin_port, path, timeout=10.0)

    def admin_post(self, path):
        c = http.client.HTTPConnection("127.0.0.1", int(self.admin_port), timeout=10.0)
        try:
            c.request("POST", path)
            r = c.getresponse()
            return r.status, r.read().decode(errors="replace")
        finally:
            c.close()

    def stats(self):
        return leg.admin_stats(self.admin_port, 10.0, self.exp["measure"].get("stat_filter_extra"))

    def start_client(self, args, out, err, cpus=None):
        e = self.exp
        return self.own.start(["taskset", "-c", cpus or e["cpus"]["client"], e["client"]["binary"]] + args, stdout=out,
                              stderr=err, **leg.client_kw(e["client"]))

    def client_cpu_s(self, pid):
        """A client process's CPU seconds (utime + stime of all its threads)."""
        return clientcheck.proc_cpu_s(pid)

    def terminate_client(self, p, grace_s):
        rc = self.own.terminate(p, grace_s=grace_s)
        self.own.stop(p)
        return rc

    def perf_cmd(self, pid, events, window_s, interval_ms=None):
        e = self.exp
        cmd = ["taskset", "-c", e["cpus"]["flip_tools"]] + list(e["measure"]["perf"]) + [
            "stat", "-x", ",", "-e", events, "-p", str(pid), "--timeout", str(int(round(window_s * 1000)))]
        return cmd + (["-I", str(int(interval_ms))] if interval_ms else [])

    def origin_requests(self):
        return leg.origin_requests(self.exp)

    def validate_bootstrap(self, path):
        return experiment.validate_bootstrap(self.exp, path)[self.exp["arms"][0]["name"]]

    def run_perf(self, cmd, timeout):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stderr

    def sched(self, envoy_pid):
        """(Envoy's run ns, {cpu: run ns}, why) for the SUT foreign and sibling gates (as run_leg)."""
        r, why = sysprobe.cpu_run_ns()
        return sysprobe.proc_run_ns(envoy_pid), r, why

    def sut_sets(self):
        sut = sysprobe.parse_cpuset(self.exp["cpus"]["sut"])
        return sut, sysprobe.siblings_of(sut)


# ---------------------------------------------------------------- per-window record and verdict

def parse_perf_intervals(text):
    """[{t, event: value}] and the per-event totals and min running % from `perf stat -I -x ,` lines
    (<time>,<count>,<unit>,<event>,<run>,<pct>...)."""
    rows, tot, run = {}, {}, {}
    for line in (text or "").splitlines():
        f = line.split(",")
        if len(f) < 6 or line.startswith("#"):
            continue
        try:
            t = float(f[0])
            v = float(f[1])
            pct = float(f[5]) if f[5] else 100.0
        except ValueError:
            continue
        ev = f[3]
        rows.setdefault(t, {"t": t})[ev] = v
        tot[ev] = tot.get(ev, 0.0) + v
        run[ev] = min(run.get(ev, 100.0), pct)
    return [rows[t] for t in sorted(rows)], tot, run


def per_request(pv, resp):
    if not resp or not leg.perf_counts_ok(pv):
        return None
    split = "cycles:u" in pv and "cycles:k" in pv
    ctot = pv["cycles:u"] + pv["cycles:k"] if split else pv["cycles"]
    out = {"cycles_total": ctot / resp, "instructions_u": pv["instructions:u"] / resp}
    if split:
        out.update(cycles_u=pv["cycles:u"] / resp, cycles_k=pv["cycles:k"] / resp)
    return out


def window_verdict(w, rate, tol, vcfg, items="http"):
    """The reasons a window is invalid (a tcp_proxy block: the bulk items)."""
    why = []
    if not w.get("client_alive_at_q1"):
        why.append("client not alive at the window's last read")
    if w.get("client_alive_after_s") is None or w["client_alive_after_s"] < 1.0:
        why.append("client not seen alive 1.0 s after the window's last read (%s)" % w.get("client_alive_after_s"))
    if not w.get("envoy_alive"):
        why.append("envoy not running at the window's end")
    want = rate * w["window_s"]
    if not w.get("responses") or abs(w["responses"] / want - 1.0) > tol:
        why.append("SUT 2xx %.0f in the window misses %.0f by more than %.2f%%" % (w.get("responses") or 0, want,
                                                                                   tol * 100))
    if items == "bulk":
        bz = w.get("bulk_window") or {}
        for k in BULK_WINDOW_ZEROS:
            if bz.get(k) != 0:
                why.append("%s in the window: %s (want 0; bulk item)" % (k, bz.get(k)))
    else:
        if w.get("sut_non2xx"):
            why.append("SUT non-2xx %d in the window" % w["sut_non2xx"])
        if w.get("sut_overflow"):
            why.append("SUT overflow counters %s in the window" % w["sut_overflow"])
    if w.get("perf_rc") != 0:
        why.append("perf exited %s" % w.get("perf_rc"))
    if not w.get("per_req"):
        why.append("perf counters missing")
    if w.get("perf_min_running_pct") is None or w["perf_min_running_pct"] < 99.99:
        why.append("perf counters multiplexed (%s%% running)" % w.get("perf_min_running_pct"))
    if w.get("sut_foreign_cpus") is None or w.get("sut_sibling_cpus") is None:
        why.append("no scheduler run time for the SUT CPUs (%s)" % w.get("sched_probe"))
    else:
        if w["sut_foreign_cpus"] > vcfg["max_sut_foreign_cpus"]:
            why.append("other tasks used %.3f CPUs on the SUT CPUs" % w["sut_foreign_cpus"])
        if w["sut_sibling_cpus"] > vcfg["max_sut_sibling_cpus"]:
            why.append("SMT siblings of the SUT CPUs busy %.3f CPUs" % w["sut_sibling_cpus"])
    if w.get("runtime_value") != w.get("value_text"):
        why.append("/runtime showed %r at the window's start, not %r" % (w.get("runtime_value"), w.get("value_text")))
    return why


# ---------------------------------------------------------------- the block's summary (Exploratory)

def ols_slope(ys):
    n = len(ys)
    if n < 2:
        return None
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def acts_deltas(q0, q1, names):
    """({stat: q1 - q0}, [names matching no stat]) for flip.acts_stats: a plain name, or a regex in /slashes/."""
    out, missing = {}, []
    for n in names:
        if len(n) > 1 and n.startswith("/") and n.endswith("/"):
            rx = re.compile(n[1:-1])
            hits = sorted(k for k in q1 if rx.search(k) and k in q0)
        else:
            hits = [n] if n in q0 and n in q1 else []
        if not hits:
            missing.append(n)
        for k in hits:
            out[k] = q1[k] - q0[k]
    return out, missing


def summarize(windows, flip, block_valid):
    """Pairs (windows 1-2, 3-4, ...): d = 100 ln(c_B / c_A) log points on cycles (u+k) per request, whatever the
    order inside the pair; the flip marker = instructions:u per request A - B. Mean, SD, the 95% t interval at
    df n-1 (no 0.34 widening: loop tier), the per-pair trend slope, and the gate lines when the config gives
    them. Timeline blocks: the pairs' reference is the first window of the pair; nothing is a gate."""
    kind = flip["kind"]
    pairs = []
    for i in range(0, len(windows) - 1, 2):
        a, b = windows[i], windows[i + 1]
        if kind in ("aa", "control", "split"):
            wa, wb = (a, b) if a["label"] == "A" else (b, a)
        else:
            wa, wb = a, b
        pa, pb = wa.get("per_req") or {}, wb.get("per_req") or {}
        rec = {"pair": i // 2 + 1, "order": a["label"] + b["label"], "ref": wa["label"], "other": wb["label"]}
        if pa.get("cycles_total") and pb.get("cycles_total"):
            rec["d_lp"] = round(100.0 * math.log(pb["cycles_total"] / pa["cycles_total"]), 4)
            rec["marker_ins_per_req"] = round(pa["instructions_u"] - pb["instructions_u"], 2)
        pairs.append(rec)
    ds = [p["d_lp"] for p in pairs if "d_lp" in p]
    mk = [p["marker_ins_per_req"] for p in pairs if "marker_ins_per_req" in p]
    out = {"basis": EXPLORATORY, "kind": kind, "scored": kind in ("aa", "control"), "valid": block_valid,
           "gating": flip.get("gating", True) is not False,
           "pairs": pairs, "n": len(ds)}
    if len(ds) >= 2:
        n = len(ds)
        mean = sum(ds) / n
        sd = stats.stdev(ds)
        t = stats.t_ppf(0.975, n - 1)
        hw = t * sd / math.sqrt(n)
        out.update(mean_lp=round(mean, 4), sd_lp=round(sd, 4), df=n - 1, t_hw_lp=round(hw, 4),
                   t_interval_lp=[round(mean - hw, 4), round(mean + hw, 4)],
                   mean_simple_pct=round(math.expm1(mean / 100.0) * 100.0, 4),
                   trend_slope_lp_per_pair=round(ols_slope(ds), 4))
    if mk:
        out["marker_mean_ins_per_req"] = round(sum(mk) / len(mk), 2)
        out["marker_mean_abs_ins_per_req"] = round(sum(abs(x) for x in mk) / len(mk), 2)
    # these are PER BLOCK (one block, df 7). A build decision (a pooled s_p over several blocks, their pooled A/A and
    # control results) is read over the blocks, never from one
    gates = {}
    out["gates_label"] = "per block, not a build decision (that pools the blocks)"
    if out["scored"] and "t_interval_lp" in out:
        g = flip.get("gates") or {}
        lo, hi = out["t_interval_lp"]
        gates["block_valid"] = bool(block_valid)
        if g.get("max_sd_lp") is not None:
            gates["block_sd_within"] = out["sd_lp"] <= g["max_sd_lp"]
        if kind == "aa":
            gates["block_t_interval_contains_0"] = lo <= 0.0 <= hi
            # the A/A marker (4.3): the mean |A - B| under the A/A bound
            gates["block_marker"] = bool(mk) and flip.get("aa_marker_max") is not None and \
                out["marker_mean_abs_ins_per_req"] < flip["aa_marker_max"]
        else:
            gates["block_point_negative"] = out["mean_lp"] < 0.0
            if g.get("reference_lp") is not None:
                rlo, rhi = g["reference_lp"]
                gates["block_excludes_0_overlaps_reference"] = hi < 0.0 and lo <= rhi and hi >= rlo
            if "marker_mean_ins_per_req" in out and flip.get("marker_min") is not None:
                gates["block_marker"] = out["marker_mean_ins_per_req"] >= flip["marker_min"]
            else:
                gates["block_marker"] = False
    if kind == "pairs":
        # the smoke: an A/A pair (both windows the same value) must move the instructions by less than the A/A
        # bound, a control pair (different values) by at least X; without them both fail closed
        x, ab = flip.get("marker_min"), flip.get("aa_marker_max")
        vals = flip["values"]
        for p in pairs:
            same = vals[p["ref"]] == vals[p["other"]]
            name = "smoke-pair%d-%s" % (p["pair"], "aa" if same else "control")
            mkv = p.get("marker_ins_per_req")
            gates[name] = bool(mkv is not None and (
                (ab is not None and abs(mkv) < ab) if same else (x is not None and mkv >= x)))
        gates["smoke-valid"] = bool(block_valid)
    if kind == "split":
        # the split test: d = 100 ln(c_two / c_one); beyond flip.split_bound_lp the client is the bottleneck
        sv = clientcheck.split_verdict(out.get("mean_lp"), len(ds), float(flip["split_bound_lp"]), block_valid)
        out["split"] = dict(sv, bound_lp=flip["split_bound_lp"],
                            d_definition="100 ln(SUT cycles per request, two clients at half load / one client)")
        gates["split_client_not_bottleneck"] = sv["pass"]
    out["gates"] = gates
    return out


# ---------------------------------------------------------------- the block

class _GroupProc:
    """poll() over a split window's client processes: None while every one runs."""

    def __init__(self, procs):
        self.procs = procs
        self.pid = procs[0].pid

    def poll(self):
        for p in self.procs:
            rc = p.poll()
            if rc is not None:
                return rc
        return None


def client_group(members, tag):
    """A split window's two client processes as one client for the window code."""
    return {"members": members, "p": _GroupProc([c["p"] for c in members]), "tag": tag}


class BlockFailed(RuntimeError):
    """The block cannot go on (Envoy died, a POST refused, the hang guard): it is invalid as a whole."""


class FlipBlock:
    def __init__(self, exp, run_dir, ops, log=print):
        self.exp = exp
        self.run_dir = run_dir
        self.ops = ops
        self.log = log
        self.f = exp["flip"]
        self.arm = exp["arms"][0]
        self.shape = exp["shapes"][0]
        for d in ("logs", "perf", "nighthawk"):
            os.makedirs(os.path.join(run_dir, d), exist_ok=True)
        self.ev = Evlog(os.path.join(run_dir, "events.log"))
        self.vcfg = dict(validity.DEFAULTS, **(exp.get("validity") or {}))

    # -- the runtime path
    def flip_to(self, value, k):
        key = self.f["key"]
        txt = runtime_text(value)
        t_post = self.ev("post_sent", "window=%d %s=%s" % (k, key, txt))
        st, body = self.ops.admin_post("/runtime_modify?" + urllib.parse.urlencode({key: txt}))
        t_ans = self.ev("post_answered", "window=%d status=%s" % (k, st))
        if st != 200:
            raise BlockFailed("POST /runtime_modify %s=%s answered %s: %s" % (key, txt, st, body.strip()[:200]))
        st2, rt = self.ops.admin_get("/runtime")
        if st2 != 200:
            raise BlockFailed("admin /runtime returned %s" % st2)
        try:
            ent = (json.loads(rt).get("entries") or {}).get(key) or {}
        except ValueError:
            ent = {}
        got = ent.get("final_value")
        got = None if got is None else str(got).strip().lower() if isinstance(value, bool) else str(got)
        t_rt = self.ev("runtime_read", "window=%d final_value=%s" % (k, got))
        return {"post_status": st, "runtime_value": got, "t_post": t_post, "t_post_answered": t_ans,
                "t_runtime_read": t_rt, "post_to_answer_ms": round((t_ans - t_post) * 1000, 3)}

    # -- the client
    def client_args(self, procs=1):
        e = self.exp
        url = "http://127.0.0.1:%d%s" % (e["envoy"]["listener_port"], self.shape.get("client_path") or
                                         self.shape["path"])
        c = experiment.arm_client_cfg(e, self.arm)
        rps = self.shape["rps"]
        if procs != 1:
            # the split test: each of the two processes runs half the workers at half the rate (the same rate and
            # connections per worker as the one-process arm)
            rps, conc = clientcheck.split_rates(rps, c.get("concurrency", 4), c.get("connections_per_worker", 16))
            c = dict(c, concurrency=conc)
        return nighthawk.client_args(c, rps, url, None, True, self.shape.get("client_extra_args"),
                                     self.shape.get("client_base_args")), url

    def start_client(self, tag, procs=1, cpus=None):
        args, url = self.client_args(procs)
        out = open(os.path.join(self.run_dir, "nighthawk", "client%s.json" % tag), "w")
        err = open(os.path.join(self.run_dir, "logs", "client%s.log" % tag), "w")
        clock = leg.clock_pair()
        # a split process on its own half of cpus.client (the keyword only then, so other ops are unchanged)
        p = self.ops.start_client(args, out, err, cpus=cpus) if cpus else self.ops.start_client(args, out, err)
        t = self.ev("client_started", "pid=%d tag=%s%s" % (p.pid, tag or "-", " cpus=%s" % cpus if cpus else ""))
        conc = int(experiment.arm_client_cfg(self.exp, self.arm).get("concurrency", 1))
        return {"p": p, "out": out, "err": err, "clock": clock, "t_start": t, "args": args, "url": url, "tag": tag,
                "path": out.name, "workers": conc // procs, "cpus": cpus}

    def end_client(self, cl, t_last_read):
        """One SIGTERM after the last read + the margin + the slack; complete output, exit 0, the sending check
        over the client's whole run."""
        e = self.exp
        c = e["client"]
        margin = leg.client_sending_margin(self.vcfg)
        time.sleep(max(0.0, t_last_read + margin + float(c.get("term_slack_s", 0.5)) - time.monotonic()))
        alive = cl["p"].poll() is None
        t = self.ev("client_sigterm", "pid=%d" % cl["p"].pid)
        rc = self.ops.terminate_client(cl["p"], float(c.get("term_grace_s", 60)))
        self.ev("client_exit", "pid=%d rc=%s after %.3f s" % (cl["p"].pid, rc, time.monotonic() - t))
        cl["out"].close()
        cl["err"].close()
        rec = {"tag": cl["tag"], "exit": rc, "alive_before_sigterm": alive, "args": cl["args"],
               "term_after_last_read_s": round(t - t_last_read, 4)}
        if cl.get("exe") is not None:
            # the executed inode hashed after the client ended (its descriptor was opened after the warm-up)
            rec.update(leg.exe_hash_record(cl["exe"][0], cl["exe"][1], cl.get("pin"), cl.get("pin_sha256"),
                                           cl.get("pin_path")))
        elif cl.get("pin"):
            rec.update(client_md5_pin=cl["pin"], client_exe_ok=False,
                       client_exe_error=cl.get("exe_error") or "the client's exe was not opened")
        if rc is None:
            rec["reasons"] = [leg.CLIENT_KILLED]
            rec["ok"] = False
            return rec
        try:
            nhp = nighthawk.parse_output(cl["path"])
        except (OSError, ValueError, KeyError, IndexError) as ex:
            rec.update(ok=False, reasons=["client output unreadable: %s" % ex])
            return rec
        conc = int(cl.get("workers") or c.get("concurrency", 1))  # a split process runs half
        cs = nighthawk.sending_check("window", nhp["worker_exec"],
                                     (cl["clock"]["monotonic_ns"] - cl["clock"]["time_ns"]) / 1e9, cl["t_first_q0"],
                                     t_last_read, nighthawk.ramp_s(cl["args"]), margin, alive, exit_code=rc,
                                     graceful_stops=nhp["graceful_stop_requested"],
                                     failed_terminations=nhp["failed_terminations"], workers=conc)
        why = list(cs["reasons"])
        # at the block's SIGTERM, sequencer.blocking 0 in every worker (no worker without the statistic)
        conc_w = [k for k in nhp["sequencer"]["per_worker"]]
        blk = {k: v.get("blocking_count") for k, v in nhp["sequencer"]["per_worker"].items()}
        if len(conc_w) != conc or any(v is None for v in blk.values()):
            why.append("client sequencer.blocking missing for some of the %d workers (%s)" % (conc, blk))
        elif any(blk.values()):
            why.append("client sequencer blocked: %s" % {k: v for k, v in blk.items() if v})
        if nhp["overflow"]:
            why.append("client overflow counters %s" % nhp["overflow"])
        go = None
        if clientcheck.overflow_gate_on(self.vcfg):
            # every client worker's own pool and pending overflow 0; a window that fails it is invalid, and so is
            # the instance (screen) or block that holds it
            go = clientcheck.leg_worker_overflow(cl["path"], conc)
            why += go["reasons"]
        if nhp["non2xx"]:
            why.append("client non-2xx %s" % nhp["non2xx"])
        if rec.get("client_md5_pin") and not rec.get("client_exe_ok"):
            why.append("client binary not the pinned one (%s)" % (
                rec.get("client_exe_error") or "md5 %s sha256 %s" % (rec.get("client_md5"), rec.get("client_sha256"))))
        rec.update(sending=cs, overflow=nhp["overflow"], non2xx=nhp["non2xx"], cx_total=nhp["cx_total"],
                   graceful_stop_requested=nhp["graceful_stop_requested"], execution_s=nhp["execution_duration_s"],
                   sequencer=nhp["sequencer"], ok=not why, reasons=why)
        if go is not None:
            rec["worker_overflow"] = go
        return rec

    def end_clients(self, cl, t_last_read):
        """end_client for one client, or for each member of a split window's group."""
        if "members" not in cl:
            return [self.end_client(cl, t_last_read)]
        out = []
        for c in cl["members"]:
            c.setdefault("t_first_q0", cl.get("t_first_q0"))
            out.append(self.end_client(c, t_last_read))
        return out

    def split_layout(self, value, k):
        """The split test: no runtime write; the window's value is its client process count."""
        t = self.ev("split_layout", "window=%d processes=%s" % (k + 1, value))
        return {"post_status": None, "runtime_value": runtime_text(value), "t_post": t, "split_processes": value}

    def responses(self, q0, q1, o0, o1):
        """The window's 2xx count: Envoy's own counter, or the origin's request count (measure.responses_from
        origin: a tcp_proxy listener has no HTTP stats; each status read is one request, not counted)."""
        if self.exp["measure"].get("responses_from") == "origin":
            return (o1 - o0 - 1) if o0 is not None and o1 is not None else 0
        return leg._delta(q0, q1, "http.ingress_http.downstream_rq_2xx")

    # -- one window
    def window(self, k, label, envoy, cl, rt):
        e = self.exp
        W = int(self.f["window_s"])
        events = e["measure"].get("perf_events") or leg.PERF_EVENTS
        value = self.f["values"][label]
        w = {"k": k + 1, "label": label, "value": value, "value_text": runtime_text(value), "window_s": W}
        w.update({x: rt[x] for x in ("post_status", "runtime_value", "post_to_answer_ms") if x in rt})
        from_origin = e["measure"].get("responses_from") == "origin"
        t_q0 = time.monotonic()
        q0 = self.ops.stats()
        o0 = self.ops.origin_requests() if from_origin else None
        k0, r0, why0 = self.ops.sched(envoy.pid)
        cmd = self.ops.perf_cmd(envoy.pid, events, W, self.f.get("perf_interval_ms"))
        split = self.f.get("kind") == "split"
        members = (cl["members"] if "members" in cl else [cl]) if split else []
        cc0 = [self.ops.client_cpu_s(c["p"].pid) for c in members]
        t0 = self.ev("window_perf_start", "window=%d label=%s value=%s" % (k + 1, label, w["value_text"]))
        rc, text = self.ops.run_perf(cmd, W + 60)
        t1 = self.ev("window_perf_end", "window=%d rc=%s" % (k + 1, rc))
        if split:
            # every client process's CPU per worker over the perf window, gated per window
            cc1 = [self.ops.client_cpu_s(c["p"].pid) for c in members]
            w["client_cpu"] = [dict(clientcheck.client_cpu_record(a, b, t1 - t0, c["workers"],
                                                                  float(self.f["split_max_client_cpus_per_worker"])),
                                    tag=c["tag"], cpus=c.get("cpus")) for c, a, b in zip(members, cc0, cc1)]
        k1, r1, why1 = self.ops.sched(envoy.pid)
        q1 = self.ops.stats()
        o1 = self.ops.origin_requests() if from_origin else None
        t_q1_end = time.monotonic()
        w["client_alive_at_q1"] = cl["p"].poll() is None
        w["envoy_alive"] = envoy.poll() is None
        with open(os.path.join(self.run_dir, "perf", "w%02d.csv" % (k + 1)), "w") as fh:
            fh.write(text or "")
        if self.f.get("perf_interval_ms"):
            rows, pv, prun = parse_perf_intervals(text)
            # per-second figures over the NOMINAL rate (open loop), labelled "per nominal request"
            nominal = float(self.shape["rps"]) * self.f["perf_interval_ms"] / 1000.0
            for r in rows:
                if "instructions:u" in r:
                    r["instructions_u_per_nominal_request"] = r["instructions:u"] / nominal
            w["perf_intervals"] = rows
            w["perf_intervals_denominator"] = "per nominal request (%s req/s, open loop)" % self.shape["rps"]
        else:
            pv, prun = leg.parse_perf_full(text or "")
        raw = self.responses(q0, q1, o0, o1)
        span = t_q1_end - t_q0
        w.update(t_q0=round(t_q0, 6), t_perf_start=round(t0, 6), t_perf_end=round(t1, 6), t_q1_end=round(t_q1_end, 6),
                 perf_rc=rc, perf_raw=pv, perf_running_pct=prun,
                 perf_min_running_pct=min(prun.values()) if prun else None, responses_raw=raw,
                 count_span_s=round(span, 4), responses=raw * W / span if span > 0 else 0.0,
                 sut_non2xx=sum(leg._delta(q0, q1, "http.ingress_http.downstream_rq_%s" % c)
                                for c in ("1xx", "3xx", "4xx", "5xx")),
                 sut_overflow={x: leg._delta(q0, q1, x) for x in ("cluster.origin.upstream_rq_pending_overflow",
                                                                  "cluster.origin.upstream_cx_overflow")
                               if leg._delta(q0, q1, x)})
        w["per_req"] = per_request(pv, w["responses"])
        w["traffic_window"] = leg.traffic_window(q0, q1)  # the traffic-equivalence counters
        if self.q_ready is not None:
            # the block's counts up to this window's last read (Envoy is new per block)
            w["traffic_block"] = leg.traffic_window(self.q_ready, q1)
        if self.f.get("window_items") == "bulk":
            w["bulk_window"] = {k: (q1[k] - q0[k]) if k in q0 and k in q1 else None for k in BULK_WINDOW_ZEROS}
        if self.f.get("acts_stats"):
            # opt-in: each named stat's change over the window (a regex matches every stat it names);
            # a stat in neither snapshot is listed under acts_missing, never as 0
            w["acts_window"], w["acts_missing"] = acts_deltas(q0, q1, self.f["acts_stats"])
        busy = t1 - t0
        sut, sib = self.ops.sut_sets()
        if why0 or why1 or k0 is None or k1 is None or not (set(sut) <= set(r0 or {}) & set(r1 or {})) or busy <= 0:
            w["sched_probe"] = "; ".join(x for x in (why0, why1) if x) or "no /proc schedstat for Envoy or the SUT CPUs"
        else:
            env = (k1 - k0) / 1e9 / busy
            run = sum(r1[c] - r0[c] for c in sut) / 1e9 / busy
            w["sut_foreign_cpus"] = round(run - env, 4)
            w["sut_sibling_cpus"] = round(sum(r1[c] - r0[c] for c in sib if c in r0 and c in r1) / 1e9 / busy, 4)
        return w, t_q1_end

    # -- the whole block
    def run(self):
        e, f = self.exp, self.f
        order, planned_s = plan(e)
        deadline = time.monotonic() + float(f.get("hang_factor", 1.5)) * planned_s + 60.0
        warm = float(f.get("warm_s", e["client"].get("warmup_s", 5)))
        lead = float(f.get("lead_in_s", e["measure"]["lead_in_s"]))
        res = {"name": e["name"], "flip": f, "order": order, "planned_s": round(planned_s, 1), "basis": EXPLORATORY,
               "windows": [], "clients": [], "errors": []}
        self.ev("block_start", "name=%s windows=%d planned_s=%.0f" % (e["name"], len(order), planned_s))
        envoy = cl = None
        t_last = None
        tracing = False
        q_block0 = None
        self.q_ready = None
        # every process this driver starts goes to ledger.jsonl (role, pid, start ticks) as it starts
        self.ops.own.ledger = os.path.join(self.run_dir, "ledger.jsonl")
        try:
            ok, det = self.ops.preflight(self.shape)
            res["preflight"] = det
            if not ok:
                raise BlockFailed("preflight: %s" % det)
            bpath, _, _ = experiment.prepare_bootstraps(e, self.run_dir, self.log, make_certs=False)
            bpath = bpath[self.arm["name"]] if isinstance(bpath, dict) else bpath
            bv = self.ops.validate_bootstrap(bpath)
            res["bootstrap_validate"] = bv
            if not bv.get("ok"):
                raise BlockFailed("envoy --mode validate failed: %s" % bv.get("tail"))
            envoy = self.ops.start_envoy(self.arm, bpath)
            self.ev("envoy_ready", "pid=%d" % envoy.pid)
            res["envoy_pid"] = envoy.pid
            res["envoy_cpus_ok"] = self.ops.cpus_ok(envoy.pid, e["cpus"]["sut"])
            if not res["envoy_cpus_ok"]:
                raise BlockFailed("envoy not on cpus.sut")
            # identity per block by (st_dev, st_ino) of /proc/<pid>/exe against the arm's binary (the file is
            # hashed at the chain's start and end, never in a block)
            ident = self.ops.exe_identity(envoy.pid, self.arm["binary"])
            res["envoy_exe"] = {k.replace("client_", ""): v for k, v in ident.items()}
            if not ident.get("client_exe_ok"):
                raise BlockFailed("envoy is not running the arm's binary file: %s" % res["envoy_exe"])
            # the counters at the block's start, read right after Envoy is ready (the collector's
            # exports and connect failures over the block must be 0; the bulk block items; the block's traffic)
            tracing = bool(experiment.arm_envoy(e, self.arm).get("tracing"))
            q_block0 = self.q_ready = self.ops.stats()
            split = f.get("kind") == "split"
            if split:
                self.flip_to = self.split_layout  # no runtime flip; the window's value is its process count
            rt = self.flip_to(f["values"][order[0]], 0)
            if rt["runtime_value"] != runtime_text(f["values"][order[0]]):
                raise BlockFailed("/runtime shows %r after the first POST" % rt["runtime_value"])
            pin = experiment.client_pin(e, self.arm)[1]

            def new_client(tag, k=0):
                n = int(f["values"][order[k]]) if split else 1
                halves = clientcheck.cpu_halves(e["cpus"]["client"]) if n == 2 else [None]
                cs = [self.start_client(tag if n == 1 else "%s-p%d" % (tag, i + 1), procs=n, cpus=halves[i])
                      for i in range(n)]
                for c in cs:
                    c["pin"] = pin
                time.sleep(warm + lead)
                for c in cs:
                    if pin:
                        c["pin_sha256"] = experiment.client_pin_sha256(e, self.arm)
                        c["pin_path"] = experiment.client_pin(e, self.arm)[0]
                        try:
                            c["exe"] = self.ops.open_exe(c["p"].pid)
                        except OSError as ex:
                            c["exe_error"] = "cannot open the client's exe: %s" % ex
                self.ev("client_warm", "tag=%s" % (tag or "-"))
                return cs[0] if n == 1 else client_group(cs, tag)
            cycle = bool(f.get("cycle_connections"))
            cl = new_client("-w01" if cycle else "")
            for k, label in enumerate(order):
                if time.monotonic() > deadline:
                    raise BlockFailed("hang guard: the block ran past %.0f s" % (f.get("hang_factor", 1.5) * planned_s))
                cl.setdefault("t_first_q0", time.monotonic())
                w, t_last = self.window(k, label, envoy, cl, rt)
                res["windows"].append(w)
                if envoy.poll() is not None:
                    raise BlockFailed("envoy exited during window %d" % (k + 1))
                if k + 1 == len(order):
                    break
                t_gap = self.ev("gap_start", "window=%d" % (k + 1))
                if cycle:
                    # a guard read when a connection is built: the flip reaches only new connections
                    time.sleep(max(0.0, t_last + 1.0 - time.monotonic()))
                    w["client_alive_after_s"] = round(time.monotonic() - t_last, 4) if cl["p"].poll() is None else None
                    res["clients"] += self.end_clients(cl, t_last)
                    cl = None
                    rt = self.flip_to(f["values"][order[k + 1]], k + 1)
                    cl = new_client("-w%02d" % (k + 2), k + 1)
                else:
                    rt = self.flip_to(f["values"][order[k + 1]], k + 1)
                    time.sleep(max(0.0, t_last + 1.0 - time.monotonic()))
                    w["client_alive_after_s"] = round(time.monotonic() - t_last, 4) if cl["p"].poll() is None else None
                    time.sleep(max(0.0, t_gap + float(f["gap_s"]) - time.monotonic()))
            # the last window's 1 s check happens before the SIGTERM
            time.sleep(max(0.0, t_last + 1.0 - time.monotonic()))
            res["windows"][-1]["client_alive_after_s"] = (round(time.monotonic() - t_last, 4)
                                                          if cl["p"].poll() is None else None)
            res["clients"] += self.end_clients(cl, t_last)
            cl = None
        except BlockFailed as ex:
            res["errors"].append(str(ex))
            self.ev("block_failed", ex)
        except Exception as ex:  # noqa: BLE001 - recorded; the block is invalid
            res["errors"].append("%s: %s" % (type(ex).__name__, ex))
            self.ev("block_failed", "%s: %s" % (type(ex).__name__, ex))
        finally:
            if envoy is not None and envoy.poll() is None and q_block0 is not None:
                try:
                    q_block1 = self.ops.stats()
                    d = lambda keys: {k: (q_block1[k] - q_block0[k]) if k in q_block0 and k in q_block1  # noqa: E731
                                      else None for k in keys}
                    if tracing:
                        res["collector_block"] = d(COLLECTOR_BLOCK_STATS)
                    if f.get("window_items") == "bulk":
                        res["bulk_block"] = d(BULK_BLOCK_ZEROS)
                except Exception as ex:  # noqa: BLE001
                    res["errors"].append("counters at the block's end: %s" % ex)
            if cl is not None:
                try:
                    res["clients"] += self.end_clients(cl, t_last or time.monotonic())
                except Exception as ex:  # noqa: BLE001
                    res["errors"].append("client stop: %s" % ex)
            if envoy is not None:
                try:
                    res["envoy_exit"] = self.ops.stop_envoy(envoy)
                    self.ev("envoy_stopped", "pid=%d exit=%s" % (envoy.pid, res["envoy_exit"]))
                except Exception as ex:  # noqa: BLE001
                    res["errors"].append("envoy stop: %s" % ex)
            # last: anything still registered (an Envoy that failed its ready or exe check, a client started
            # before an exception or a signal in its warm-up) is stopped by its registered PID
            left = self.ops.own.stop_all()
            if left:
                res["stopped_at_exit"] = left
                res["errors"].append("processes still running at the block's end, stopped by PID: %s" % left)
                self.ev("stopped_at_exit", "pids=%s" % left)
        rate = float(self.shape["rps"])
        tol = float(f.get("rate_tolerance", 0.005))
        for w in res["windows"]:
            w["reasons"] = window_verdict(w, rate, tol, self.vcfg, f.get("window_items", "http"))
            if f.get("kind") == "split":
                w["reasons"] += ["client %s: %s" % (c["tag"] or "-", c["reason"]) for c in w.get("client_cpu") or []
                                 if not c["ok"]] or ([] if w.get("client_cpu") else ["no client CPU record"])
            w["valid"] = not w["reasons"]
        why = list(res["errors"])
        if len(res["windows"]) != len(order):
            why.append("%d of %d windows ran" % (len(res["windows"]), len(order)))
        why += ["window %d: %s" % (w["k"], "; ".join(w["reasons"])) for w in res["windows"] if not w["valid"]]
        why += ["client %s: %s" % (c.get("tag") or "-", "; ".join(c.get("reasons") or ["?"]))
                for c in res["clients"] if not c.get("ok")]
        if not res["clients"]:
            why.append("no client record")
        if res.get("envoy_exit") not in (0, None):
            why.append("envoy exit %s" % res["envoy_exit"])
        if tracing:
            cb = res.get("collector_block") or {}
            for k in COLLECTOR_BLOCK_STATS:
                if cb.get(k) is None:
                    why.append("collector counter not recorded: %s" % k)
                elif cb[k] != 0:
                    why.append("%s over the block: %s (want 0)" % (k, cb[k]))
        if f.get("window_items") == "bulk":
            bb = res.get("bulk_block") or {}
            for k in BULK_BLOCK_ZEROS:
                if bb.get(k) != 0:
                    why.append("%s over the block: %s (want 0; bulk item)" % (k, bb.get(k)))
        res["valid"] = not why
        res["reasons"] = why
        res["summary"] = summarize(res["windows"], f, res["valid"])
        self.ev("block_end", "valid=%s" % res["valid"])
        self.ev.close()
        with open(os.path.join(self.run_dir, "block.json"), "w") as fh:
            json.dump(sysprobe.scrub(res), fh, indent=1, sort_keys=True, default=str)
        return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("config")
    ap.add_argument("--out")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--check", action="store_true", help="validate and print the plan only")
    ap.add_argument("--side", choices=("own", "external"), default="own",
                    help="own: start and stop the origin (and the collector) for this block; external: the chain "
                         "started them once (side.py) and the block only checks their ports are open")
    a = ap.parse_args(argv)

    def _on_term(signum, frame):
        # a signal runs every finally (the block's client, Envoy, the registered PIDs, the containers)
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGHUP, _on_term)
    exp, errs = load(a.config, experiment.parse_sets(a.set))
    if errs:
        sys.exit("flip-block config errors:\n  " + "\n  ".join(errs))
    order, planned = plan(exp)
    print("# %s: %d windows (%s), %s, planned %.0f s, hang guard %.0f s" % (
        exp["name"], len(order), exp["flip"]["order"], exp["flip"]["kind"], planned,
        float(exp["flip"].get("hang_factor", 1.5)) * planned + 60))
    if a.check:
        return 0
    run_dir = os.path.abspath(os.path.expanduser(a.out or os.path.join(
        exp["workdir"], "%s-%s" % (exp["name"], time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))))
    if os.path.exists(os.path.join(run_dir, "block.json")):
        sys.exit("run dir %s already has a block; pick another --out" % run_dir)
    os.makedirs(run_dir, exist_ok=True)
    os.sched_setaffinity(0, sysprobe.parse_cpuset(exp["cpus"]["flip_tools"]))
    logf = open(os.path.join(run_dir, "log.txt"), "a")

    def log(msg):
        logf.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg))
        logf.flush()
    from epl.origin import Collector, Origin
    origin = collector = None
    try:
        if a.side == "own":
            origin = Origin(exp["origin"], exp["cpus"].get("origin", ""), exp["shapes"], run_dir, log)
            origin.start()
        if a.side == "own" and experiment.needs_collector(exp):
            collector = Collector(exp["collector"], exp["cpus"]["origin"], run_dir, log)
            collector.start()
        ops = RealOps(exp, run_dir, log)
        res = FlipBlock(exp, run_dir, ops, log).run()
    finally:
        if collector:
            collector.stop()
        if origin:
            origin.stop()
    s = res["summary"]
    print("%s: valid %s; pairs %d; mean %s lp, SD %s lp, t95 %s; marker %s; gates %s" % (
        exp["name"], res["valid"], s["n"], s.get("mean_lp"), s.get("sd_lp"), s.get("t_interval_lp"),
        s.get("marker_mean_ins_per_req"), s.get("gates")))
    return 0 if res["valid"] else 3


if __name__ == "__main__":
    sys.exit(main())
