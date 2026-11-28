#!/usr/bin/env python3
"""epl-agentd: the loop daemon on the measurement box, an MCP server on stdio.

    python3 -I loop/agentd.py --config agentd.json [--home ~/epl]   # on the box, inside ONE ssh session
    python3 -I loop/agentd.py --config CFG --standin                # local: the stand-ins, no box

The agent's MCP config starts it as its stdio command (`ssh <box> "exec ~/epl/loop/run-mcp.sh agentd"`, the
argument naming a config under $EPL_HOME/loop/ or a path): every MCP frame travels inside that one session, nothing
polls the box, and no second login appears (from the workstation, optionally through an OpenSSH ControlMaster's
socket: docs/loop.md, "The stdio route"). The config must name housekeeping_cpus; there is no default. It
tears everything down (the running instance, every PID in its ledgers verified by start ticks, the side containers
by ID; each step isolated) and exits with:
  rc 0 the channel ended (stdin EOF, or a closed channel)     rc 4 the session time limit (session_ttl_s)
  rc 5 the idle limit (idle_ttl_s with no inbound message)    rc 6 an exception in the daemon's loop
  rc 143 SIGTERM, SIGHUP or SIGINT                            rc 2 refused at start (nothing ran)
It refuses to start while a previous epl-agentd is still alive or a previous session left a process. The next
session starts with a clean proof, never a reconnect into a half state.

What it runs:
- screens (the hybrid design): at least 6 short Envoy instances per candidate, each one flip block with
  counterbalanced control pairs and an in-instance A/A pair; the interval is taken across instances; every number
  is labelled "in-process effect, Exploratory" (screen.py);
- explore: one warm Envoy, runtime flips, live traffic through the fork's nighthawk_mcp (and nighthawk_service),
  per-second telemetry; labelled "Exploratory, steering only; not a screen".
It never writes a published row: it writes only under its session directory, and no tool takes a path.

Placement: the daemon pins itself (and every thread it starts) to the housekeeping CPUs, refuses to start when they
touch a SUT CPU or a SUT sibling, pins its own ssh session ancestors there, and reports its own CPU per step. Its CPU
is not exempt from any gate: the instances' idle pre-flight and per-window SUT-foreign gates count it like any other
task."""
import argparse
import contextlib
import glob
import io
import json
import os
import queue
import resource
import signal
import subprocess
import sys
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import flipblock as fb  # noqa: E402
import instance as inst_mod  # noqa: E402
import ledger  # noqa: E402
import screen as sc  # noqa: E402
import telemetry as tm  # noqa: E402
from epl import experiment, leg, sysprobe  # noqa: E402

PROTOCOL = "2025-06-18"
SERVER = {"name": "epl-agentd", "version": "0.1.0"}
SCREEN_BASIS = sc.BASIS
EXPLORE_BASIS = "Exploratory, steering only; not a screen"
SESSION_BASIS = "session control"
MAX_TTL_S = 12 * 3600
MAX_WAIT_S = 900
RUNNER_GRACE_S = 60.0  # still above flipblock's client grace
STEP_JOIN_S = 90.0


def workdir_error(wd):
    """The daemon writes only under its own work directory, never inside the harness tree (data/, docs/: the
    published rows and their sources)."""
    root = os.path.realpath(ROOT)
    wd = os.path.realpath(os.path.expanduser(wd))
    if os.path.commonpath([wd, root]) == root:
        return "workdir %s is inside the harness tree: the daemon writes nothing next to published data" % wd
    return None


DEFAULT_HOME = "~/epl"
HK_MISSING = ("the config names no housekeeping_cpus: the daemon has no default, a wrong one could put it on a SUT "
              "CPU")


def default_workdir(home=None):
    """HOME/runs/loop, HOME being EPL_HOME (run-mcp.sh passes it as --home; default ~/epl)."""
    return os.path.join(home or os.environ.get("EPL_HOME") or DEFAULT_HOME, "runs", "loop")


DEFAULT_IDLE_TTL_S = 900
IDLE_TTL_RANGE = (300, 3600)


def lscpu_e():
    """The CPU topology (socket, L3) as `lscpu -e` prints it, kept in agentd.json; None off Linux."""
    try:
        r = subprocess.run(["lscpu", "-e"], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def user_sessions():
    """This user's login sessions from logind (`loginctl list-sessions`). `who` and `last` do not list a
    non-pty ssh session such as this one, so they cannot show a stray login; logind does. None when unavailable."""
    try:
        r = subprocess.run(["loginctl", "list-sessions", "--no-legend"], capture_output=True, text=True,
                           timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    me = str(os.getuid())
    out = []
    for line in r.stdout.splitlines():
        f = line.split()
        if len(f) >= 3 and f[1] == me:
            out.append({"session": f[0], "uid": f[1], "user": f[2], "rest": " ".join(f[3:])})
    return out


class ToolError(Exception):
    """A refusal: answered as isError with the reason; nothing was started."""


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------- a child MCP server (the fork's nighthawk_mcp)

class McpChild:
    """Newline-delimited JSON-RPC 2.0 to a child MCP server on its stdio (nighthawk_mcp's transport)."""

    def __init__(self, argv, own, role, err_path):
        self.p = own.start(argv, role=role, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=open(err_path, "a"))
        self.own = own
        self.next_id = 0
        self.replies = {}
        self.cv = threading.Condition()
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if m.get("id") is not None:
                with self.cv:
                    self.replies[m["id"]] = m
                    self.cv.notify_all()
        with self.cv:
            self.cv.notify_all()

    def request(self, method, params=None, timeout=10.0):
        with self.lock:
            self.next_id += 1
            i = self.next_id
            self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": i, "method": method,
                                            "params": params or {}}) + "\n").encode())
            self.p.stdin.flush()
        end = time.monotonic() + timeout
        with self.cv:
            while i not in self.replies:
                left = end - time.monotonic()
                if left <= 0 or self.p.poll() is not None:
                    raise ToolError("nighthawk_mcp gave no reply to %s within %.0f s" % (method, timeout))
                self.cv.wait(min(left, 0.5))
            m = self.replies.pop(i)
        if "error" in m:
            raise ToolError("nighthawk_mcp %s: %s" % (method, m["error"].get("message")))
        return m.get("result") or {}

    def notify(self, method, params=None):
        with self.lock:
            self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}) +
                                "\n").encode())
            self.p.stdin.flush()

    def initialize(self):
        r = self.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                        "clientInfo": SERVER}, timeout=15.0)
        self.notify("notifications/initialized")
        return r

    def call_tool(self, name, args, timeout=40.0):
        r = self.request("tools/call", {"name": name, "arguments": args}, timeout=timeout)
        payload = r.get("structuredContent")
        if payload is None:
            try:
                payload = json.loads((r.get("content") or [{}])[0].get("text") or "null")
            except ValueError:
                payload = (r.get("content") or [{}])[0].get("text")
        return payload, bool(r.get("isError"))

    def read_resource(self, uri, timeout=15.0):
        r = self.request("resources/read", {"uri": uri}, timeout=timeout)
        c = (r.get("contents") or [{}])[0]
        try:
            return json.loads(c.get("text") or "null")
        except ValueError:
            return None

    def close(self):
        try:
            self.p.stdin.close()  # nighthawk_mcp ends on EOF (cancels a run, seals the session)
        except OSError:
            pass
        try:
            self.p.wait(timeout=40.0)
        except subprocess.TimeoutExpired:
            pass
        return self.own.stop(self.p)


# ---------------------------------------------------------------- tool schemas

def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


_I = {"type": "integer"}
_N = {"type": "number"}
_S = {"type": "string"}
_V = {"type": ["boolean", "number", "string"]}

TOOLS = {
    "session_status": ("The session: state, time left, ledger, ours (CPU, placement). Starts nothing.", _obj({})),
    "screen_start": ("Start a screen of one candidate: N >= 6 short Envoy instances, each P counterbalanced "
                     "control pairs (off/on) plus an A/A pair; validated before anything starts. Results are "
                     "'in-process effect, Exploratory'.", _obj({
                         "arm": _S, "key": _S, "off": _V, "on": _V, "shape": _S, "rate": _I, "instances": _I,
                         "pairs": _I, "aa_pairs": _I, "window_s": _I, "gap_s": _N, "warm_s": _N, "lead_in_s": _N,
                         "marker_min": _N, "aa_marker_max": _N, "note": _S, "repeat_of": _S},
                         ["arm", "key", "off", "on", "shape", "rate", "instances", "pairs"])),
    "screen_step": ("Run the next `count` instances (default 1) of the open screen; waits up to wait_s (0 = return "
                    "at once).", _obj({"count": _I, "wait_s": _I})),
    "screen_wait": ("Wait up to wait_s for the running step.", _obj({"wait_s": _I}, ["wait_s"])),
    "screen_result": ("The screen's result: per-instance effects, the across-instance interval, the marker, the "
                      "A/A check, validity. While the screen is open only progress and validity are shown; an "
                      "aborted screen never shows effects.", _obj({"screen": _S})),
    "screen_telemetry": ("One instance's per-second timeline (perf intervals, Envoy admin, on CLOCK_MONOTONIC), of "
                         "a finished screen only.", _obj({"instance": _I, "max_rows": _I, "screen": _S},
                                                         ["instance"])),
    "explore_start": ("Start one warm Envoy of a staged arm for exploration (no screen).",
                      _obj({"arm": _S, "shape": _S}, ["arm", "shape"])),
    "runtime_set": ("Flip an allowed runtime key on the explore Envoy (POST /runtime_modify, /runtime checked).",
                    _obj({"key": _S, "value": _V}, ["key", "value"])),
    "traffic_start": ("Start traffic on the explore Envoy through nighthawk_mcp start_run (target fixed).",
                      _obj({"rps": _I, "connections": _I, "duration_s": _I, "phases": _S, "protocol": _S,
                            "request_body_size": _I, "max_requests_per_connection": _I}, ["rps"])),
    "traffic_steer": ("Change the live rate (nighthawk_mcp steer).", _obj({"rps": _I}, ["rps"])),
    "traffic_stop": ("Cancel the live run (nighthawk_mcp cancel_run).", _obj({})),
    "traffic_status": ("nighthawk_mcp get_status.", _obj({})),
    "telemetry_read": ("Per-second timeline of the explore Envoy for `seconds` (perf -I, admin, Nighthawk "
                       "snapshots), on one clock.", _obj({"seconds": _I}, ["seconds"])),
    "explore_stop": ("Stop the explore Envoy, the traffic and the side services.", _obj({})),
    "abort": ("Stop whatever runs now (screen instance, explore) and the side services. The session stays open.",
              _obj({})),
    "cleanproof": ("Check that nothing of this session runs: no verified ledger PID alive, side containers "
                   "stopped, ports free.", _obj({})),
}


def check_args(name, args):
    props = TOOLS[name][1]["properties"]
    req = TOOLS[name][1]["required"]
    if not isinstance(args, dict):
        raise ToolError("arguments must be an object")
    bad = sorted(set(args) - set(props))
    if bad:
        raise ToolError("unknown arguments %s" % bad)
    miss = [k for k in req if k not in args]
    if miss:
        raise ToolError("missing arguments %s" % miss)
    for k, v in args.items():
        t = props[k]["type"]
        ts = t if isinstance(t, list) else [t]
        ok = any((x == "integer" and isinstance(v, int) and not isinstance(v, bool)) or
                 (x == "number" and isinstance(v, (int, float)) and not isinstance(v, bool)) or
                 (x == "string" and isinstance(v, str)) or (x == "boolean" and isinstance(v, bool)) for x in ts)
        if not ok:
            raise ToolError("%s must be %s" % (k, " or ".join(ts)))


# ---------------------------------------------------------------- the daemon

class Daemon:
    def __init__(self, cfg, out_write, standin=False, log_path=None, home=None):
        self.cfg = cfg
        self.standin = bool(standin)
        self.write_out = out_write
        self.stop_event = threading.Event()
        self.stop_reason = None
        self.lock = threading.RLock()
        self.t_start = time.monotonic()
        self.ttl = min(float(cfg.get("session_ttl_s", 4 * 3600)), MAX_TTL_S)
        self.deadline = self.t_start + self.ttl
        # the idle limit. A half-open channel (the workstation asleep, a dead link with no FIN) sends nothing, so a
        # session that hears no message for idle_ttl_s, with no step running inside its planned time, tears down
        self.idle_ttl = float(cfg.get("idle_ttl_s", DEFAULT_IDLE_TTL_S))
        self.last_msg = time.monotonic()
        wd = os.path.realpath(os.path.expanduser(cfg.get("workdir") or default_workdir(home)))
        err = workdir_error(wd)
        if err:
            raise ValueError(err)
        self.workdir = wd
        base = os.path.join(wd, "session-%s-%d" % (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), os.getpid()))
        self.sdir, n = base, 1
        while True:
            try:
                os.makedirs(self.sdir)
                break
            except FileExistsError:
                n += 1
                self.sdir = "%s-%d" % (base, n)
        self.ledger = os.path.join(self.sdir, "ledger.jsonl")
        self.own = leg.OwnProcesses(ledger=self.ledger)
        self.logf = open(log_path or os.path.join(self.sdir, "agentd.log"), "a")
        self.ev = fb.Evlog(os.path.join(self.sdir, "events.log"))
        if not cfg.get("housekeeping_cpus"):
            raise ValueError(HK_MISSING)
        self.hk = sysprobe.parse_cpuset(cfg["housekeeping_cpus"])
        self.perf_mode = cfg.get("perf_mode", "sleep")
        # the span tolerance: 50 ms on the box; the stand-in configs loosen it (a shared workstation's scheduler is
        # not the box's)
        self.span_tol_ms = float(cfg.get("span_tolerance_ms", inst_mod.SPAN_TOLERANCE_MS))
        self.screen = None
        self.explore = None
        self.screens_done = []
        self.cpu0 = self._self_cpu()
        self.ancestors_pinned = []
        with open(os.path.join(self.sdir, "agentd.json"), "w") as f:
            json.dump({"pid": os.getpid(), "start_ticks": leg.proc_start_ticks(os.getpid()), "utc": utc(),
                       "standin": self.standin, "ttl_s": self.ttl, "idle_ttl_s": self.idle_ttl,
                       "span_tolerance_ms": self.span_tol_ms,
                       "housekeeping_cpus": sorted(self.hk), "lscpu_e": lscpu_e()}, f)
        self.register = []  # every screen_start of the session, refused ones included
        if self.standin:
            self.si_path = os.path.join(self.sdir, "standin.json")
            with open(self.si_path, "w") as f:
                json.dump(cfg.get("standin") or {}, f)

    def close(self):
        for f in (self.ev, self.logf):
            try:
                f.close()
            except (OSError, ValueError):
                pass

    # -- logging (never stdout: stdout is the MCP channel)
    def log(self, msg):
        self.logf.write("%s %s\n" % (utc(), msg))
        self.logf.flush()

    # -- start-up checks (fail closed)
    def startup_errors(self):
        errs = []
        if not (self.cfg.get("arms") and self.cfg.get("shapes")):
            errs.append("the config names no arms or no shapes")
        if self.perf_mode not in tm.PERF_MODES:
            errs.append("perf_mode must be one of %s" % (tm.PERF_MODES,))
        if not (self.standin or 10.0 <= self.span_tol_ms <= 100.0):
            errs.append("span_tolerance_ms must be 10..100 on the box")
        lo, hi = (1, 3600) if self.standin else (IDLE_TTL_RANGE)
        if not lo <= self.idle_ttl <= hi:
            errs.append("idle_ttl_s must be %d..%d s" % (lo, hi))
        for name, arm in sorted((self.cfg.get("arms") or {}).items()):
            try:
                with open(os.path.expanduser(arm["base"])) as f:
                    raw = sc.deep_merge(json.load(f), arm.get("overrides") or {})
            except (OSError, ValueError, KeyError) as ex:
                errs.append("arm %s: base config unreadable: %s" % (name, ex))
                continue
            if self.standin:
                continue
            sut = sysprobe.parse_cpuset(raw["cpus"]["sut"])
            forbid = sut | sysprobe.siblings_of(sut)
            if self.hk & forbid:
                errs.append("arm %s: housekeeping CPUs %s touch the SUT CPUs or their siblings %s" % (
                    name, sorted(self.hk), sorted(self.hk & forbid)))
            if not sysprobe.parse_cpuset(raw["cpus"].get("flip_tools", "")) <= self.hk:
                errs.append("arm %s: cpus.flip_tools must lie inside the housekeeping CPUs" % name)
            # nor the client's or the origin's CPUs, or their siblings
            for role in ("client", "origin"):
                cs = sysprobe.parse_cpuset(raw["cpus"].get(role, ""))
                bad = self.hk & (cs | sysprobe.siblings_of(cs))
                if bad:
                    errs.append("arm %s: housekeeping CPUs %s touch cpus.%s or its siblings" % (name, sorted(bad),
                                                                                             role))
        # a previous epl-agentd that is still alive (a quick reconnect during its teardown, or a half-open
        # survivor) is refused: its agentd.json names its pid and start ticks
        for aj in glob.glob(os.path.join(self.workdir, "session-*", "agentd.json")):
            if aj.startswith(self.sdir + os.sep):
                continue
            try:
                with open(aj) as f:
                    prev = json.load(f)
            except (OSError, ValueError):
                continue
            if ledger.verified(prev):
                errs.append("a previous epl-agentd (pid %s, session %s) is still running: wait for its teardown or "
                            "stop it, then run the clean proof" % (prev.get("pid"),
                                                                   os.path.basename(os.path.dirname(aj))))
        # never a reconnect into a half state: a previous session that left a process is refused
        for led in glob.glob(os.path.join(self.workdir, "session-*", "**", "ledger.jsonl"), recursive=True):
            if led.startswith(self.sdir):
                continue
            live = [e for e in ledger.entries([led]) if ledger.verified(e)]
            if live:
                errs.append("a previous session left running processes (%s): run the clean proof first" % led)
        return errs

    def pin_self(self):
        if self.standin or not hasattr(os, "sched_setaffinity"):
            return
        os.sched_setaffinity(0, self.hk)
        # the ssh session's own processes (ours, same uid) go to the housekeeping CPUs too; never signalled
        uid = os.getuid()
        for pid in sorted(sysprobe.ancestors(os.getppid())):
            try:
                if os.stat("/proc/%d" % pid).st_uid != uid:
                    continue
                os.sched_setaffinity(pid, self.hk)
                self.ancestors_pinned.append({"pid": pid, "comm": open("/proc/%d/comm" % pid).read().strip()})
            except OSError as ex:
                self.ancestors_pinned.append({"pid": pid, "error": str(ex)})

    def _self_cpu(self):
        r = resource.getrusage(resource.RUSAGE_SELF)
        return r.ru_utime + r.ru_stime

    def ours(self):
        """Our CPU so far and our placement now: the daemon, its nighthawk children, the pinned ancestors."""
        pids = [os.getpid()] + [a["pid"] for a in self.ancestors_pinned if "error" not in a]
        kids = {}
        if self.explore and self.explore.get("nh"):
            kids["nighthawk_mcp"] = self.explore["nh"].p.pid
        if self.explore and self.explore.get("service"):
            kids["nighthawk_service"] = self.explore["service"].pid
        forbid = self._forbidden()
        mine = [os.getpid()] + ([kids["nighthawk_mcp"]] if "nighthawk_mcp" in kids else [])
        # the ssh ancestors: their allowed CPUs only (their last CPU may predate the pinning until they next run)
        anc = [x for x in pids if x != os.getpid()]
        return {"agentd_cpu_s": round(self._self_cpu() - self.cpu0, 4),
                "children_cpu_s": {k: tm.proc_cpu_s(v) for k, v in kids.items()},
                "ancestors_pinned": self.ancestors_pinned,
                "placement_violations": tm.placement_violations(mine, forbid) + tm.placement_violations(
                    anc, forbid, check_last=False)}

    def _forbidden(self):
        out = set()
        if self.standin:
            return out
        for arm in (self.cfg.get("arms") or {}).values():
            try:
                with open(os.path.expanduser(arm["base"])) as f:
                    raw = sc.deep_merge(json.load(f), arm.get("overrides") or {})
                sut = sysprobe.parse_cpuset(raw["cpus"]["sut"])
                out |= sut | sysprobe.siblings_of(sut)
            except (OSError, ValueError, KeyError):
                continue
        return out

    def ttl_left(self):
        return round(self.deadline - time.monotonic(), 1)

    def state(self):
        if self.screen and self.screen.get("thread") and self.screen["thread"].is_alive():
            return "screen step running"
        if self.screen:
            return "screen open"
        if self.explore:
            return "explore"
        return "idle"

    # ------------------------------------------------------------ the MCP surface
    def handle(self, msg):
        """One JSON-RPC message -> the reply (None for a notification)."""
        i = msg.get("id")
        meth = msg.get("method")
        if i is None:
            return None
        if meth == "initialize":
            return {"jsonrpc": "2.0", "id": i, "result": {
                "protocolVersion": PROTOCOL, "capabilities": {"tools": {}}, "serverInfo": SERVER,
                "instructions": ("epl-agentd: screens give 'in-process effect, Exploratory' results only; nothing "
                                 "here is a published row. Every screen has >= 6 instances fixed at its start; "
                                 "read the result only when it is complete.")}}
        if meth == "ping":
            return {"jsonrpc": "2.0", "id": i, "result": {}}
        if meth == "tools/list":
            return {"jsonrpc": "2.0", "id": i, "result": {"tools": [
                {"name": n, "description": d, "inputSchema": s} for n, (d, s) in TOOLS.items()]}}
        if meth == "tools/call":
            p = msg.get("params") or {}
            name = p.get("name")
            if name not in TOOLS:
                return {"jsonrpc": "2.0", "id": i, "error": {"code": -32602, "message": "unknown tool %r" % name}}
            self.ev("tool_call", name)
            try:
                check_args(name, p.get("arguments") or {})
                payload = getattr(self, "t_" + name)(**(p.get("arguments") or {}))
                err = False
            except ToolError as ex:
                payload, err = {"refused": str(ex)}, True
            except Exception as ex:  # noqa: BLE001 - answered, logged; the session stays up
                self.log("tool %s failed: %s: %s" % (name, type(ex).__name__, ex))
                payload, err = {"error": "%s: %s" % (type(ex).__name__, ex)}, True
            payload.setdefault("basis", SESSION_BASIS)
            payload["ttl_left_s"] = self.ttl_left()
            self.ev("tool_done", "%s error=%s" % (name, err))
            return {"jsonrpc": "2.0", "id": i, "result": {
                "content": [{"type": "text", "text": json.dumps(payload, sort_keys=True, default=str)}],
                "structuredContent": payload, "isError": err}}
        return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": "method not found: %s" % meth}}

    # ------------------------------------------------------------ session tools
    def t_session_status(self):
        leds = self._all_ledgers()
        live = [e for e in ledger.entries(leds) if ledger.verified(e)]
        return {"state": self.state(), "session_dir": os.path.basename(self.sdir), "standin": self.standin,
                "live_ledger_entries": [{"role": e.get("role"), "pid": e.get("pid")} for e in live],
                "ours": self.ours(), "screens_done": self.screens_done, "logins": user_sessions(),
                "idle_ttl_s": self.idle_ttl, "register": self.register, "span_tolerance_ms": self.span_tol_ms,
                "screen": (self.screen or {}).get("id"), "perf_mode": self.perf_mode}

    def _all_ledgers(self):
        return [self.ledger] + sorted(glob.glob(os.path.join(self.sdir, "**", "ledger.jsonl"), recursive=True))

    def t_cleanproof(self):
        if self.state() != "idle":
            raise ToolError("the session is not idle (%s): abort or finish first" % self.state())
        why = []
        leds = self._all_ledgers()
        live = [e for e in ledger.entries(leds) if ledger.verified(e)]
        if live:
            why.append("verified ledger PIDs alive: %s" % [(e.get("role"), e.get("pid")) for e in live])
        for st in glob.glob(os.path.join(self.sdir, "**", "side.json"), recursive=True):
            why.append("side services not stopped: %s" % os.path.relpath(st, self.sdir))
        if not self.standin:
            ports = set()
            for arm in self.cfg["arms"].values():
                with open(os.path.expanduser(arm["base"])) as f:
                    raw = sc.deep_merge(json.load(f), arm.get("overrides") or {})
                ports |= {raw["envoy"]["listener_port"], raw["envoy"]["admin_port"]}
            busy = [p for p in sorted(ports) if sysprobe.port_open("127.0.0.1", p)]
            if busy:
                why.append("ports in use: %s" % busy)
        return {"proof": "CLEAN" if not why else "NOT-CLEAN", "reasons": why,
                "note": "the session's own view; the clean-proof login still runs the full clean proof (state.py)"}

    # ------------------------------------------------------------ side services (origin, collector) by ID
    def side_start(self, cfg_path, d):
        if self.standin:
            return None
        import side
        st = os.path.join(d, "side.json")
        with contextlib.redirect_stdout(self.logf):
            rc = side.start(cfg_path, st)
        if rc != 0:
            raise ToolError("side services failed to start (rc %s)" % rc)
        return st

    def side_stop(self, st):
        if not st or not os.path.exists(st):
            return 0
        import side
        with contextlib.redirect_stdout(self.logf):
            return side.stop(st)

    # ------------------------------------------------------------ screens
    def _write_register(self):
        with open(os.path.join(self.sdir, "register.json.tmp"), "w") as f:
            json.dump({"basis": SCREEN_BASIS, "screens_in_session": len(self.register), "screens": self.register},
                      f, indent=1, sort_keys=True, default=str)
        os.replace(os.path.join(self.sdir, "register.json.tmp"), os.path.join(self.sdir, "register.json"))

    def _reg(self, sid):
        return next((r for r in self.register if r["screen"] == sid), None)

    def _next_sid(self):
        """One past the highest screen directory, refused ones included (scrNN, scrNN.refused)."""
        n = 0
        for x in glob.glob(os.path.join(self.sdir, "scr[0-9]*")):
            digits = os.path.basename(x)[3:].split(".")[0]
            if digits.isdigit():
                n = max(n, int(digits))
        return "scr%02d" % (n + 1)

    def t_screen_start(self, **spec):
        with self.lock:
            if self.state() != "idle":
                raise ToolError("the session is not idle (%s)" % self.state())
            sid = self._next_sid()
            # a refusal before any directory exists is registered as refNN (its own id), never as a screen id
            ref = "ref%02d" % (1 + sum(1 for r in self.register if r["screen"].startswith("ref")))
            entry = dict({"screen": ref, "key": sc.screen_key(spec), "repeat_of": spec.get("repeat_of"),
                          "status": "refused", "utc": utc()}, **sc.screen_values(spec))
            errs = sc.spec_errors(spec, self.cfg)
            if not errs:
                e = sc.rate_error(self.cfg, spec)
                if e:
                    errs.append(e)
            if not errs:
                # the screen register. A second screen of the same key in one session must say which earlier
                # screen it repeats; the family size goes into every record
                prior = [r for r in self.register if r["key"] == entry["key"] and r["status"] != "refused"]
                ro = spec.get("repeat_of")
                if prior and ro not in [r["screen"] for r in prior]:
                    errs.append("this (arm, key, shape) was already screened in this session (%s): a repeat, or "
                                "another rate or value of it, names repeat_of" %
                                ", ".join("%s %s" % (r["screen"], r["status"]) for r in prior))
                elif ro is not None and not prior:
                    errs.append("repeat_of %s names no earlier screen of this key in this session" % ro)
            if errs:
                entry["reasons"] = errs
                self.register.append(entry)
                self._write_register()
                self.ev("screen_refused", "%s %s" % (ref, "; ".join(errs)[:300]))
                raise ToolError("; ".join(errs))
            d = os.path.join(self.sdir, sid)
            os.makedirs(d)
            try:
                cfgs = []
                for k in range(int(spec["instances"])):
                    raw = sc.instance_raw(self.cfg, spec, sid, k, d)
                    p = os.path.join(d, "i%02d.json" % (k + 1))
                    with open(p, "w") as f:
                        json.dump(raw, f, indent=1, sort_keys=True)
                    _, e1 = fb.load(p)
                    pc = os.path.join(d, "i%02d.control-check.json" % (k + 1))
                    with open(pc, "w") as f:
                        json.dump(sc.control_variant(raw, spec), f)
                    _, e2 = fb.load(pc)
                    os.remove(pc)
                    if e1 or e2:
                        raise ToolError("instance %d config refused: %s" % (k + 1, "; ".join(sorted(set(e1 + e2)))))
                    cfgs.append(p)
                with open(os.path.join(d, "spec.json"), "w") as f:
                    json.dump(spec, f, indent=1, sort_keys=True)
                side = self.side_start(cfgs[0], d)
            except BaseException as ex:
                # the directory is set aside, so the next screen_start is not blocked by it
                os.replace(d, d + ".refused")
                entry["screen"] = sid + ".refused"
                entry["reasons"] = ["%s: %s" % (type(ex).__name__, ex)]
                self.register.append(entry)
                self._write_register()
                self.ev("screen_refused", "%s %s" % (sid, entry["reasons"][0][:300]))
                raise
            entry["status"] = "open"
            entry["screen"] = sid
            self.register.append(entry)
            self._write_register()
            self.screen = {"id": sid, "spec": spec, "dir": d, "cfgs": cfgs, "blocks": [None] * len(cfgs),
                           "next": 0, "thread": None, "abort": threading.Event(), "side": side,
                           "status": "open", "ours": [], "step_deadline": None}
            self.ev("screen_start", "%s %s" % (sid, json.dumps(spec, sort_keys=True)))
            per = sc.planned_instance_s(spec, self.cfg)
            return {"basis": SCREEN_BASIS, "screen": sid, "instances": len(cfgs), "planned_instance_s": round(per),
                    "planned_screen_s": round(per * len(cfgs)), "orders": [
                        json.load(open(c))["flip"]["order"] for c in cfgs],
                    "screens_in_session": len(self.register),
                    "rule": "the instance count is fixed now; the effects cannot be read before all %d ran; a "
                            "screen is never extended; another screen of the same (arm, key, shape) names "
                            "repeat_of" % len(cfgs)}

    def _instance_guard_s(self, scr):
        return 1.5 * sc.planned_instance_s(scr["spec"], self.cfg) + 120.0

    def _run_instances(self, scr, count):
        try:
            for _ in range(count):
                k = scr["next"]
                if k >= len(scr["cfgs"]) or scr["abort"].is_set() or self.stop_event.is_set():
                    break
                try:
                    stop = self._run_one(scr, k)
                except Exception as ex:  # noqa: BLE001 - never a silent replacement
                    self.log("instance %s i%02d: daemon error %s: %s" % (scr["id"], k + 1, type(ex).__name__, ex))
                    self._stop_instance_leftovers(scr, k)
                    scr["blocks"][k] = {"valid": False, "windows": [],
                                        "reasons": ["daemon error: %s: %s" % (type(ex).__name__, ex)]}
                    scr["next"] = k + 1
                    self.ev("instance_end", "%s i%02d valid=False daemon error" % (scr["id"], k + 1))
                    stop = False
                if stop:
                    break
            if scr["next"] >= len(scr["cfgs"]) and scr["status"] == "open":
                self._finish_screen(scr, "complete")
        finally:
            scr["step_deadline"] = None

    def _stop_instance_leftovers(self, scr, k):
        out = os.path.join(scr["dir"], "i%02d" % (k + 1))
        with contextlib.redirect_stdout(self.logf):
            ledger.stop([os.path.join(out, "ledger.jsonl"), self.ledger], grace_s=10.0)
        for pid in list(self.own.procs):
            p, _ = self.own.procs[pid]
            try:
                self.own.stop(p, grace_s=10.0)
            except Exception:  # noqa: BLE001
                pass

    def _run_one(self, scr, k):
        """One instance. Returns True when the step must stop (aborted, hang guard)."""
        out = os.path.join(scr["dir"], "i%02d" % (k + 1))
        if os.path.exists(out):
            # an instance directory that already exists is never run again (no replacement)
            raise RuntimeError("instance directory %s already exists" % os.path.basename(out))
        argv = [sys.executable, "-I", os.path.join(HERE, "instance.py"), scr["cfgs"][k], "--out", out,
                "--perf-mode", self.perf_mode, "--span-tolerance-ms", str(self.span_tol_ms)]
        if self.standin:
            argv += ["--standin", self.si_path]
        elif hasattr(os, "sched_setaffinity"):
            argv = ["taskset", "-c", self.cfg["housekeeping_cpus"]] + argv
        c0 = self._self_cpu()
        ours0 = self.ours()
        self.ev("instance_start", "%s i%02d" % (scr["id"], k + 1))
        with open(os.path.join(scr["dir"], "i%02d.runner.log" % (k + 1)), "w") as lf:
            p = self.own.start(argv, role="instance-runner", stdin=subprocess.DEVNULL, stdout=lf,
                               stderr=subprocess.STDOUT)
        guard = time.monotonic() + self._instance_guard_s(scr)
        why = None
        while p.poll() is None:
            if scr["abort"].is_set() or self.stop_event.is_set():
                why = "aborted"
                break
            if time.monotonic() > guard:
                why = "hang guard"
                break
            time.sleep(0.2)
        if why:
            self.own.terminate(p, grace_s=RUNNER_GRACE_S)  # one SIGTERM: the runner's finally stops its block
        self.own.stop(p)
        led = os.path.join(out, "ledger.jsonl")
        left = [e for e in ledger.entries([led]) if ledger.verified(e)]
        if left:
            with contextlib.redirect_stdout(self.logf):
                ledger.stop([led])
        try:
            with open(os.path.join(out, "block.json")) as f:
                b = json.load(f)
        except (OSError, ValueError):
            b = {"valid": False, "reasons": ["no block record (runner rc %s)" % p.returncode], "windows": []}
        if why:
            b["valid"] = False
            b.setdefault("reasons", []).append("instance stopped by the daemon: %s" % why)
        if left:
            b["valid"] = False
            b.setdefault("reasons", []).append("processes of the instance still ran after its end: %s" % [
                (e.get("role"), e.get("pid")) for e in left])
        o1 = self.ours()
        b.setdefault("loop", {}).setdefault("ours", {})["agentd_cpu_s"] = round(self._self_cpu() - c0, 4)
        viol = o1["placement_violations"] or ours0["placement_violations"]
        if viol:
            b["valid"] = False
            b.setdefault("reasons", []).append("ours on a SUT CPU or sibling (daemon side): %s" % viol[:3])
        scr["blocks"][k] = b
        scr["next"] = k + 1
        self.ev("instance_end", "%s i%02d valid=%s" % (scr["id"], k + 1, b.get("valid")))
        return bool(why)

    def _finish_screen(self, scr, status):
        scr["status"] = status
        try:
            res = sc.analyze(scr["spec"], scr["blocks"], scr["id"], status)
            entry = self._reg(scr["id"])
            if entry is not None:
                entry["status"] = status
                entry["candidate"] = res["candidate"]
            same = [{"screen": r["screen"], "status": r["status"], "repeat_of": r.get("repeat_of"),
                     "off": r.get("off"), "on": r.get("on"), "rate": r.get("rate")}
                    for r in self.register if r["key"] == sc.screen_key(scr["spec"])]
            rec = sc.candidate_record(res, same, len(self.register))
            res["register"] = {"screens_of_this_key": same, "screens_in_session": len(self.register)}
            # the perf span tolerance used, printed with every result (box: 50 ms)
            res["span_tolerance_ms"] = self.span_tol_ms
            scr["result"] = res
            with open(os.path.join(scr["dir"], "result.json"), "w") as f:
                json.dump(sysprobe.scrub(res), f, indent=1, sort_keys=True, default=str)
            with open(os.path.join(self.sdir, "candidates.jsonl"), "a") as f:
                f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
            self._write_register()
            self.ev("screen_end", "%s %s candidate=%s" % (scr["id"], status, res["candidate"]))
        finally:
            # the containers come down whatever the analysis or the writes did
            try:
                self.side_stop(scr.get("side"))
            finally:
                scr["side"] = None

    def _wait_step(self, wait_s):
        scr = self.screen
        t = scr.get("thread")
        end = time.monotonic() + min(int(wait_s), MAX_WAIT_S)
        while t and t.is_alive() and time.monotonic() < end and not self.stop_event.is_set():
            t.join(timeout=0.5)
        return self._progress()

    def _progress(self):
        scr = self.screen
        running = bool(scr.get("thread") and scr["thread"].is_alive())
        out = {"basis": SCREEN_BASIS, "screen": scr["id"], "status": scr["status"], "step_running": running,
               "instances_run": scr["next"], "instances_planned": len(scr["cfgs"]),
               "instances": [{"instance": k + 1, "valid": b.get("valid"), "reasons": (b.get("reasons") or [])[:3]}
                             for k, b in enumerate(scr["blocks"]) if b is not None]}
        if scr["status"] != "open" and not running:
            res = scr.get("result") or {}
            self.screens_done.append(scr["id"])
            out["result"] = {k: res.get(k) for k in ("reading", "candidate", "across", "validity")}
            self.screen = None
        return out

    def t_screen_step(self, count=1, wait_s=0):
        with self.lock:
            scr = self.screen
            if not scr:
                raise ToolError("no open screen")
            if scr.get("thread") and scr["thread"].is_alive():
                raise ToolError("a step is running: screen_wait")
            left = len(scr["cfgs"]) - scr["next"]
            if not (1 <= count <= left):
                raise ToolError("count must be 1..%d (the instances left)" % left)
            scr["step_deadline"] = time.monotonic() + count * self._instance_guard_s(scr)
            scr["thread"] = threading.Thread(target=self._run_instances, args=(scr, count), daemon=True)
            scr["thread"].start()
        return self._wait_step(wait_s)

    def t_screen_wait(self, wait_s):
        if not self.screen:
            raise ToolError("no open screen")
        return self._wait_step(wait_s)

    def t_screen_result(self, screen=None):
        scr = self.screen
        if scr is not None and screen in (None, scr["id"]):
            if scr.get("result"):
                return scr["result"]
            # an open screen shows no effect figure (analyze blinds anything not complete)
            return sc.analyze(scr["spec"], scr["blocks"][:scr["next"]] + [None] * (len(scr["cfgs"]) - scr["next"]),
                              scr["id"], "interim")
        done = sorted(glob.glob(os.path.join(self.sdir, "scr[0-9]*", "result.json")))
        if screen is not None:
            done = [x for x in done if os.path.basename(os.path.dirname(x)) == screen]
        if not done:
            raise ToolError("no finished screen%s" % (" " + screen if screen else ""))
        with open(done[-1]) as f:
            return json.load(f)

    def t_screen_telemetry(self, instance, max_rows=600, screen=None):
        if self.screen is not None and screen in (None, self.screen["id"]):
            # per-second cycles per request with A/B phases would show the effect before the end
            raise ToolError("telemetry of the open screen %s is released when the screen ends" % self.screen["id"])
        done = sorted(x for x in glob.glob(os.path.join(self.sdir, "scr[0-9]*")) if os.path.isdir(x) and
                      not x.endswith(".refused") and os.path.exists(os.path.join(x, "result.json")))
        if screen is not None:
            done = [x for x in done if os.path.basename(x) == screen]
        if not done:
            raise ToolError("no finished screen")
        p = os.path.join(done[-1], "i%02d" % int(instance), "telemetry.json")
        try:
            with open(p) as f:
                t = json.load(f)
        except (OSError, ValueError):
            raise ToolError("no telemetry for instance %s" % instance)
        rows = t["timeline"]["rows"]
        t["timeline"]["rows"] = rows[:max(1, min(int(max_rows), 3600))]
        t["timeline"]["rows_total"] = len(rows)
        t["basis"] = SCREEN_BASIS
        t["screen"] = os.path.basename(done[-1])
        t.pop("perf_runs", None)
        return t

    # ------------------------------------------------------------ explore
    def t_explore_start(self, arm, shape):
        with self.lock:
            if self.state() != "idle":
                raise ToolError("the session is not idle (%s)" % self.state())
            a = (self.cfg.get("arms") or {}).get(arm)
            if a is None or shape not in (self.cfg.get("shapes") or {}):
                raise ToolError("arm must be one of %s and shape one of %s" % (
                    sorted(self.cfg.get("arms") or {}), sorted(self.cfg.get("shapes") or {})))
            n = len(glob.glob(os.path.join(self.sdir, "exp*"))) + 1
            d = os.path.join(self.sdir, "exp%02d" % n)
            for sub in ("", "logs", "perf", "nighthawk"):
                os.makedirs(os.path.join(d, sub), exist_ok=True)
            spec = {"arm": arm, "key": sc.arm_keys(a)[0], "off": False, "on": True, "shape": shape,
                    "rate": int(self.cfg["shapes"][shape]["rps"]), "instances": sc.MIN_INSTANCES, "pairs": 2}
            raw = sc.instance_raw(self.cfg, spec, "exp%02d" % n, 0, d)
            p = os.path.join(d, "envoy-config.json")
            with open(p, "w") as f:
                json.dump(raw, f, indent=1, sort_keys=True)
            exp, errs = fb.load(p)
            if errs:
                raise ToolError("arm config refused: %s" % "; ".join(errs))
            ex = {"dir": d, "exp": exp, "arm": arm, "shape": shape, "side": None, "nh": None, "service": None}
            self.explore = ex
            try:
                ex["side"] = self.side_start(p, d)
                log = self.log
                if self.standin:
                    ops = inst_mod.StandInLoopOps(exp, d, log, dict(self.cfg.get("standin") or {}))
                    ops.si = dict(ops.si, envoy=dict((ops.si.get("envoy") or {}), rate=0))
                else:
                    ops = inst_mod.LoopOps(exp, d, log)
                ops.setup_loop(self.perf_mode, self._forbidden())
                ops.own.ledger = os.path.join(d, "ledger.jsonl")
                ex["ops"] = ops
                # the same idle, foreign-CPU and port pre-flight as every screen instance (flipblock's)
                ok, det = ops.preflight(exp["shapes"][0])
                if not ok:
                    raise ToolError("pre-flight failed: %s" % json.dumps(det, sort_keys=True, default=str)[:600])
                bpath, _, _ = experiment.prepare_bootstraps(exp, d, log, make_certs=False)
                bpath = bpath[exp["arms"][0]["name"]] if isinstance(bpath, dict) else bpath
                bv = ops.validate_bootstrap(bpath)
                if not bv.get("ok"):
                    raise ToolError("envoy --mode validate failed: %s" % bv.get("tail"))
                ex["envoy"] = ops.start_envoy(exp["arms"][0], bpath)
                if not ops.cpus_ok(ex["envoy"].pid, exp["cpus"]["sut"]):
                    raise ToolError("envoy not on cpus.sut")
                ident = ops.exe_identity(ex["envoy"].pid, exp["arms"][0]["binary"])
                if not ident.get("client_exe_ok"):
                    raise ToolError("envoy is not running the arm's binary: %s" % ident)
                self._start_nighthawk(ex)
            except BaseException:
                self._stop_explore()
                raise
            self.ev("explore_start", "%s %s envoy=%d" % (arm, shape, ex["envoy"].pid))
            return {"basis": EXPLORE_BASIS, "explore": os.path.basename(d), "envoy_pid": ex["envoy"].pid,
                    "traffic": "nighthawk_mcp" if ex["nh"] else "none configured",
                    "keys": sc.arm_keys(a)}

    def _start_nighthawk(self, ex):
        nh = self.cfg.get("nighthawk") or {}
        exp = ex["exp"]
        admin_base = "http://127.0.0.1:%d" % exp["envoy"]["admin_port"]
        cap = str(int(self.cfg.get("max_rps", 20000)))
        err = os.path.join(ex["dir"], "logs", "nighthawk.log")
        own = ex["ops"].own
        if self.standin:
            ex["nh"] = McpChild([sys.executable, "-I", os.path.join(HERE, "standin", "nighthawk_mcp.py"),
                                 "--max-rps", cap, "--admin-base", admin_base], own, "nighthawk_mcp", err)
            ex["nh"].initialize()
            return
        if not nh.get("mcp_argv"):
            return
        pins = nh.get("sha256") or {}
        for argv in (nh.get("service_argv"), nh.get("mcp_argv")):
            if argv and argv[0] not in pins:
                raise ToolError("nighthawk binary %s has no sha256 pin in the config" % argv[0])
        for path, want in sorted(pins.items()):
            got = sysprobe.file_hashes(os.path.expanduser(path)).get("sha256") if os.path.exists(
                os.path.expanduser(path)) else None
            if got != want:
                raise ToolError("nighthawk binary %s: sha256 %s, pinned %s" % (path, got, want))
        if nh.get("service_argv"):
            ex["service"] = own.start(["taskset", "-c", exp["cpus"]["client"]] + [
                os.path.expanduser(x) for x in nh["service_argv"]], role="nighthawk_service",
                stdout=open(err, "a"), stderr=subprocess.STDOUT)
            host, port = nh.get("service_address", "127.0.0.1:8443").rsplit(":", 1)
            if not sysprobe.wait_port(host, int(port), 30.0):
                raise ToolError("nighthawk_service did not listen on %s:%s" % (host, port))
        ex["nh"] = McpChild(["taskset", "-c", self.cfg["housekeeping_cpus"]] + [
            os.path.expanduser(x) for x in nh["mcp_argv"]] + ["--max-rps", cap, "--admin-base", admin_base],
            own, "nighthawk_mcp", err)
        ex["nh"].initialize()

    def _need_explore(self, traffic=False):
        if not self.explore:
            raise ToolError("no explore Envoy: explore_start first")
        if traffic and not self.explore.get("nh"):
            raise ToolError("no nighthawk_mcp configured for traffic")
        return self.explore

    def t_runtime_set(self, key, value):
        ex = self._need_explore()
        keys = sc.arm_keys(self.cfg["arms"][ex["arm"]])
        if key not in keys:
            raise ToolError("key must be one of the arm's candidate keys %s" % keys)
        txt = fb.runtime_text(value)
        t0 = tm.mono_ns() / 1e9
        st, body = ex["ops"].admin_post("/runtime_modify?" + urllib.parse.urlencode({key: txt}))
        t1 = tm.mono_ns() / 1e9
        if st != 200:
            raise ToolError("POST /runtime_modify answered %s: %s" % (st, body.strip()[:200]))
        st2, rt = ex["ops"].admin_get("/runtime")
        got = ((json.loads(rt).get("entries") or {}).get(key) or {}).get("final_value") if st2 == 200 else None
        got = None if got is None else str(got).strip().lower() if isinstance(value, bool) else str(got)
        self.ev("runtime_set", "%s=%s final=%s" % (key, txt, got))
        return {"basis": EXPLORE_BASIS, "key": key, "value": txt, "runtime_final_value": got, "ok": got == txt,
                "t_post_mono_s": round(t0, 6), "post_to_answer_ms": round((t1 - t0) * 1000, 3),
                "note": "guards read at connection build need new connections (traffic_stop, traffic_start)"}

    def t_traffic_start(self, rps, **kw):
        ex = self._need_explore(traffic=True)
        if rps > int(self.cfg.get("max_rps", 20000)) or rps <= 0:
            raise ToolError("rps must be 1..%d" % int(self.cfg.get("max_rps", 20000)))
        sh = self.cfg["shapes"][ex["shape"]]
        args = dict(kw, uri="http://127.0.0.1:%d%s" % (ex["exp"]["envoy"]["listener_port"],
                                                        sh.get("client_path") or sh["path"]), rps=int(rps))
        if "duration_s" not in args and "phases" not in args:
            args["duration_s"] = int(self.cfg.get("explore_max_duration_s", 3600))
        payload, err = ex["nh"].call_tool("start_run", args)
        if err:
            raise ToolError("start_run: %s" % payload)
        self.ev("traffic_start", json.dumps(args, sort_keys=True))
        return {"basis": EXPLORE_BASIS, "start_run": payload, "args": args}

    def t_traffic_steer(self, rps):
        ex = self._need_explore(traffic=True)
        if rps > int(self.cfg.get("max_rps", 20000)) or rps <= 0:
            raise ToolError("rps must be 1..%d" % int(self.cfg.get("max_rps", 20000)))
        payload, err = ex["nh"].call_tool("steer", {"rps": int(rps)})
        if err:
            raise ToolError("steer: %s" % payload)
        self.ev("traffic_steer", "rps=%d" % rps)
        return {"basis": EXPLORE_BASIS, "steer": payload}

    def t_traffic_stop(self):
        ex = self._need_explore(traffic=True)
        payload, err = ex["nh"].call_tool("cancel_run", {})
        if err:
            raise ToolError("cancel_run: %s" % payload)
        return {"basis": EXPLORE_BASIS, "cancel_run": payload}

    def t_traffic_status(self):
        ex = self._need_explore(traffic=True)
        payload, err = ex["nh"].call_tool("get_status", {})
        return {"basis": EXPLORE_BASIS, "get_status": payload, "isError": err}

    def t_telemetry_read(self, seconds):
        ex = self._need_explore()
        if not 1 <= seconds <= 60:
            raise ToolError("seconds must be 1..60")
        ops = ex["ops"]
        ops.perf_rows, ops.perf_runs = [], []
        events = ex["exp"]["measure"].get("perf_events") or leg.PERF_EVENTS
        sampler = tm.AdminSampler(ops.admin_get).start()
        ops.sampler = sampler
        t0 = tm.mono_ns() / 1e9
        try:
            cmd = ops.perf_cmd(ex["envoy"].pid, events, seconds)
            rc, _ = ops.run_perf(cmd, seconds + 30)
        finally:
            ops.sampler = None
            samples = sampler.stop()
        t1 = tm.mono_ns() / 1e9
        series = {}
        if ex.get("nh"):
            body = ex["nh"].read_resource("nighthawk://series") or {}
            for s in body.get("series") or []:
                pts = [(p["monotonic_ns"] / 1e9, p["value"]) for p in s.get("points") or []
                       if t0 - 1.0 <= p["monotonic_ns"] / 1e9 <= t1 + 1.0]
                if pts and s.get("name", "").startswith("benchmark."):
                    series[s["name"]] = pts
        tl = tm.timeline(ops.perf_rows, samples, series, None, anchor_s=t0)
        return {"basis": EXPLORE_BASIS, "perf_rc": rc, "perf_mode": self.perf_mode, "timeline": tl,
                "client_series": sorted(series), "ours": self.ours()}

    def t_explore_stop(self):
        if not self.explore:
            raise ToolError("no explore Envoy")
        return dict(self._stop_explore(), basis=EXPLORE_BASIS)

    def _stop_explore(self):
        ex = self.explore
        if not ex:
            return {}
        out = {"explore": os.path.basename(ex["dir"])}
        if ex.get("nh"):
            try:
                ex["nh"].close()
            except Exception as e:  # noqa: BLE001
                out["nighthawk_mcp_stop"] = str(e)
        if ex.get("service") is not None:
            try:
                ex["ops"].own.stop(ex["service"])
            except Exception as e:  # noqa: BLE001
                out["nighthawk_service_stop"] = str(e)
        if ex.get("envoy") is not None:
            try:
                out["envoy_exit"] = ex["ops"].stop_envoy(ex["envoy"])
            except Exception as e:  # noqa: BLE001
                out["envoy_stop"] = str(e)
        if ex.get("ops") is not None:
            out["stopped_at_exit"] = ex["ops"].own.stop_all()
        out["side_stop_rc"] = self.side_stop(ex.get("side"))
        self.explore = None
        self.ev("explore_stop", json.dumps(out, sort_keys=True, default=str))
        return out

    # ------------------------------------------------------------ abort and teardown
    def t_abort(self):
        return dict(self.abort_all("abort tool"), basis=SESSION_BASIS)

    def _step(self, out, name, fn):
        """Every teardown step runs, whatever an earlier one did; errors are recorded, not raised."""
        try:
            return fn()
        except BaseException as ex:  # noqa: BLE001
            out.setdefault("errors", []).append("%s: %s: %s" % (name, type(ex).__name__, ex))
            self.log("abort step %s failed: %s: %s" % (name, type(ex).__name__, ex))
            return None

    def abort_all(self, why):
        out = {"why": why}
        scr = self.screen

        def stop_screen():
            scr["abort"].set()
            t = scr.get("thread")
            if t and t.is_alive():
                t.join(timeout=STEP_JOIN_S)
            if scr["status"] == "open":
                self._finish_screen(scr, "aborted")
            out["screen"] = {"id": scr["id"], "status": scr["status"], "instances_run": scr["next"]}

        if scr:
            self._step(out, "screen", stop_screen)
            self.screens_done.append(scr["id"])
            self.screen = None
        if self.explore:
            out["explore"] = self._step(out, "explore", self._stop_explore)
            self.explore = None

        def ledger_stop():
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = ledger.stop(self._all_ledgers(), grace_s=10.0)
            out["ledger"] = buf.getvalue().strip().splitlines()[-5:]
            return rc
        out["ledger_stop_rc"] = self._step(out, "ledger", ledger_stop)

        def own_stop():
            return self.own.stop_all()
        out["own_stopped"] = self._step(out, "own", own_stop)

        def side_stop_all():
            # idempotent: a stopped side.json is renamed side.json.stopped
            return {os.path.relpath(st, self.sdir): self.side_stop(st)
                    for st in glob.glob(os.path.join(self.sdir, "**", "side.json"), recursive=True)}
        out["side_stop"] = self._step(out, "side", side_stop_all)
        self._step(out, "event", lambda: self.ev("abort", json.dumps(out, sort_keys=True, default=str)))
        return out

    def teardown(self, reason):
        self.log("teardown: %s" % reason)
        out = {}
        try:
            out = self.abort_all("teardown: %s" % reason)
        except BaseException as ex:  # noqa: BLE001 - abort_all isolates its steps; this is the last net
            out = {"errors": ["abort_all: %s: %s" % (type(ex).__name__, ex)]}
        out["ours"] = self._step(out, "ours", self.ours)
        out["reason"] = reason
        out["logins"] = self._step(out, "logins", user_sessions)
        with open(os.path.join(self.sdir, "teardown.json"), "w") as f:
            json.dump(out, f, indent=1, sort_keys=True, default=str)
        self._step(out, "event", lambda: self.ev("session_end", reason))
        return out

    def idle_expired(self, now=None):
        """No inbound message for idle_ttl_s, and no step running inside its planned time plus the guard."""
        now = time.monotonic() if now is None else now
        if now - self.last_msg < self.idle_ttl:
            return False
        scr = self.screen
        if scr and scr.get("thread") and scr["thread"].is_alive():
            dl = scr.get("step_deadline")
            return dl is not None and now > dl
        return True


# ---------------------------------------------------------------- the stdio loop

def serve(daemon, inp, q_timeout=0.5):
    """Read newline-delimited JSON-RPC from `inp` on a reader thread; answer on the dispatcher (this thread). EOF,
    a signal, the session time limit or the idle limit end the loop; the caller tears down."""
    q = queue.Queue()

    def reader():
        for line in inp:
            daemon.last_msg = time.monotonic()
            line = line.strip()
            if line:
                q.put(line)
        daemon.stop_reason = daemon.stop_reason or "eof"
        daemon.stop_event.set()
        q.put(None)
    threading.Thread(target=reader, daemon=True).start()

    def watchdog():
        while not daemon.stop_event.wait(0.5):
            if time.monotonic() >= daemon.deadline:
                daemon.stop_reason = daemon.stop_reason or "ttl"
            elif daemon.idle_expired():
                daemon.stop_reason = daemon.stop_reason or "idle"
            else:
                continue
            daemon.stop_event.set()
            q.put(None)
            return
    threading.Thread(target=watchdog, daemon=True).start()
    while True:
        try:
            line = q.get(timeout=q_timeout)
        except queue.Empty:
            if daemon.stop_event.is_set():
                break
            continue
        if line is None:
            break
        if daemon.stop_event.is_set():
            break
        try:
            msg = json.loads(line)
        except ValueError:
            daemon.write_out({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        r = daemon.handle(msg) if isinstance(msg, dict) else None
        if r is not None:
            daemon.write_out(r)
    return daemon.stop_reason or "eof"


RC = {"eof": 0, "ttl": 4, "idle": 5}
RC_SIGNAL, RC_ERROR = 143, 6


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--standin", action="store_true", help="local stand-ins, no box (tests)")
    ap.add_argument("--home", default=os.environ.get("EPL_HOME") or DEFAULT_HOME,
                    help="EPL_HOME: the default workdir is HOME/runs/loop (default %s)" % DEFAULT_HOME)
    a = ap.parse_args(argv)
    with open(a.config) as f:
        cfg = json.load(f)
    if a.standin and "standin" not in cfg:
        sys.exit("--standin needs a config with a standin section")
    if not a.standin and "standin" in cfg:
        sys.exit("a config with a standin section runs only with --standin")
    err = workdir_error(cfg.get("workdir") or default_workdir(a.home))
    if not err and not cfg.get("housekeeping_cpus"):
        err = HK_MISSING
    if err:
        sys.stderr.write("epl-agentd refused to start:\n  %s\n" % err)
        return 2
    # stdout is the MCP channel: keep a private copy of it and send fd 1 to the session log, so that no stray
    # print from any module can corrupt a frame. stdin too: the reader keeps a private copy of fd 0 and fd 0
    # becomes /dev/null, so no child (the runner, Envoy, the client, perf, docker) can read MCP frames
    chan = os.fdopen(os.dup(1), "w", buffering=1)
    inp = io.TextIOWrapper(os.fdopen(os.dup(0), "rb"), encoding="utf-8")
    nul = os.open(os.devnull, os.O_RDONLY)
    os.dup2(nul, 0)
    os.close(nul)
    d = Daemon(cfg, None, standin=a.standin, home=a.home)
    os.dup2(d.logf.fileno(), 1)
    sys.stdout = d.logf
    wlock = threading.Lock()

    def write_out(obj):
        # a closed channel is the same as EOF: tear down (Python ignores SIGPIPE, so this raises, never kills)
        with wlock:
            try:
                chan.write(json.dumps(obj, default=str) + "\n")
                chan.flush()
            except (BrokenPipeError, OSError, ValueError):
                d.stop_reason = d.stop_reason or "eof"
                d.stop_event.set()
    d.write_out = write_out
    errs = d.startup_errors()
    if errs:
        d.log("refused to start: %s" % errs)
        write_out({"jsonrpc": "2.0", "method": "notifications/message",
                   "params": {"level": "error", "data": "epl-agentd refused to start: %s" % "; ".join(errs)}})
        sys.stderr.write("epl-agentd refused to start:\n  %s\n" % "\n  ".join(errs))
        d.close()
        return 2
    reason = "error: before serve"
    try:
        d.pin_self()

        def on_signal(signum, frame):
            d.stop_reason = d.stop_reason or "signal %d" % signum
            d.stop_event.set()
        signal.signal(signal.SIGTERM, on_signal)
        signal.signal(signal.SIGHUP, on_signal)
        signal.signal(signal.SIGINT, on_signal)
        d.ev("session_start", "pid=%d ttl_s=%.0f idle_ttl_s=%.0f standin=%s" % (os.getpid(), d.ttl, d.idle_ttl,
                                                                                d.standin))
        reason = serve(d, inp)
    except BaseException as ex:  # noqa: BLE001 - an exception still tears down (rc 6)
        reason = "error: %s: %s" % (type(ex).__name__, ex)
        d.log(reason)
    finally:
        try:
            d.teardown(reason)
        except BaseException as ex:  # noqa: BLE001
            d.log("teardown failed: %s: %s" % (type(ex).__name__, ex))
        try:
            d.close()
        except BaseException:  # noqa: BLE001
            pass
    if reason.startswith("error"):
        return RC_ERROR
    return RC.get(reason, RC_SIGNAL)


if __name__ == "__main__":
    rc = main()
    sys.stderr.flush()
    # after the teardown: the stdin reader thread may still block in read() (a signal or a limit ended the session,
    # not EOF), and a normal interpreter exit can then abort on that file's lock. Everything is written and closed.
    os._exit(rc if isinstance(rc, int) else 1)
