#!/usr/bin/env python3
"""The foreign-activity check: is anything other than this session running on the box?

    foreign.py snapshot OUT_JSON [--runs R] [--state STATE_JSON]
        the start state: running service units (system and user), active timers (system and user) with the unit each
        activates, every (user, comm) of a non-kernel process; rc 1 (and the list printed) when the start state
        itself holds foreign activity
    foreign.py check SNAP_JSON [--runs R] [--state STATE_JSON]
        rc 0 when nothing foreign is active now; else rc 1 and the list
    foreign.py endcheck SNAP_JSON SINCE [--runs R] [--state STATE_JSON] [--own-timedated]
        the end-of-chain check: `check`, plus every login since SINCE (epoch s; `who` and `last --since`), every
        logind session since SINCE, and every unit the system manager started since SINCE (journal); rc 1 and the
        list when anything is found. A finding MARKS the chain's data (the caller records it); it is not silently
        kept.

With --runs R, every logind session (loginctl list-sessions and show-session: with or without a terminal) that is
not one of the ids this session's logins recorded in R/state/own-sessions.txt is foreign too. At endcheck, these
units started since SINCE are EXPECTED items, listed but not foreign: a docker scope whose container ID is one this
session started (the "container <id> (epl-...) started" lines of R/queue.log and R/chain-*.log, and the IDs in
R/state/side.json*); a run of a timer the state file accepts (`accepted_timers`, mapped to the unit it activates by
the snapshot's timer list); one of our recorded login sessions and our uid's user manager started with it; and,
with --own-timedated, systemd-timedated.service, which a chain's own `timedatectl show` starts. Anything else
still marks the chain.

Foreign: any CI-runner job or process (GitHub Actions runner: comm Runner.Listener, Runner.Worker, or a process
under an actions-runner directory); any service unit or (user, comm) pair that is not in the start-state snapshot
and is not one of this session's own tools (OWN, plus the state file's `own_comms`); any interactive login (who);
any active timer outside the start-state snapshot. `who` and `last` see only logins with a terminal, so the check
also reads loginctl (every session now) and logind's journal ("New session <id>", every session since the start).
Kernel threads are not processes for this check. Read-only: ps, who, last, loginctl, systemctl, journalctl;
nothing is matched by command line and nothing is signalled."""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import state as box_state  # noqa: E402

OWN_SESSIONS = os.path.join("state", "own-sessions.txt")
RUNNER = ("Runner.Listener", "Runner.Worker", "RunnerService", "actions-runner")
# this session's own tools and the login's processes (comm, truncated to 15 characters by the kernel)
OWN = {"bash", "sh", "dash", "sleep", "sshd", "sshd-session", "ps", "python3", "timeout", "taskset", "sudo", "cat",
       "grep", "sed", "awk", "mawk", "gawk", "tee", "head", "tail", "cut", "wc", "sort", "uniq", "tr", "date",
       "setsid", "nohup", "systemd", "(sd-pam)", "docker", "docker-init", "md5sum", "sha256sum", "ss", "find", "du",
       "stat", "containerd-shim", "containerd-shim-runc-v2", "docker-proxy", "perf", "systemd-run", "systemctl",
       "tar", "gzip", "readlink", "xargs", "env", "seq", "ls", "mkdir", "rm", "cp", "mv", "chmod", "dirname",
       "basename", "id", "hostname", "uname", "who", "last", "getconf", "lsmod", "kill", "printf", "chown", "flock",
       "realpath", "test", "nproc", "sync", "zcat", "file", "rmdir", "touch", "ln", "jq", "logger", "pgrep", "true",
       "false", "journalctl", "loginctl", "losetup", "kworker", "(udev-worker)", "systemd-udevd", "udevadm"}
OWN_PREFIXES = ("chain-", "kworker", "nighthawk", "envoy")


def run(argv, timeout=20):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, str(e)


def units(kind, user=False):
    argv = ["systemctl"] + (["--user"] if user else []) + ["list-units", "--type=" + kind,
                                                           "--state=" + ("running" if kind == "service" else "active"),
                                                           "--no-legend", "--plain", "--no-pager"]
    rc, out = run(argv)
    if rc != 0:
        return None
    return sorted({ln.split()[0] for ln in out.splitlines() if ln.split()})


def timer_units():
    """{timer: the unit it activates} from `systemctl list-timers --all` (its last two columns), or {}."""
    rc, out = run(["systemctl", "list-timers", "--all", "--no-legend", "--plain", "--no-pager"])
    if rc != 0:
        return {}
    m = {}
    for ln in out.splitlines():
        f = ln.split()
        if len(f) >= 2 and f[-2].endswith(".timer"):
            m[f[-2]] = f[-1]
    return m


def procs():
    rc, out = run(["ps", "-eo", "pid=,ppid=,user=,comm="])
    rows = []
    for ln in out.splitlines():
        f = ln.split(None, 3)
        if len(f) < 4:
            continue
        pid, ppid, user, comm = f
        if pid == "2" or ppid == "2":
            continue  # kernel threads
        rows.append((int(pid), user, comm.strip()))
    return rows


def runner_procs(rows):
    hit = []
    for pid, user, comm in rows:
        if any(comm.startswith(r[:15]) for r in RUNNER):
            hit.append("%d %s %s" % (pid, user, comm))
            continue
        try:
            cwd = os.readlink("/proc/%d/cwd" % pid)
            if "actions-runner" in cwd:
                hit.append("%d %s %s (cwd %s)" % (pid, user, comm, cwd))
        except OSError:
            pass
    return hit


def logins():
    rc, out = run(["who"])
    return [ln for ln in out.splitlines() if ln.strip()]


def state():
    rows = procs()
    return {"services": units("service"), "user_services": units("service", True), "timers": units("timer"),
            "user_timers": units("timer", True), "timer_units": timer_units(),
            "procs": sorted({"%s %s" % (u, c) for _, u, c in rows}), "runner": runner_procs(rows), "logins": logins()}


def foreign(now, snap, own=()):
    own = OWN | set(own)
    out = []
    out += ["CI-runner process: " + x for x in now["runner"]]
    out += ["interactive login: " + x for x in now["logins"]]
    for k, label in (("services", "service"), ("user_services", "user service"), ("timers", "timer"),
                     ("user_timers", "user timer")):
        if now[k] is None or snap.get(k) is None:
            continue
        new = [u for u in now[k] if u not in snap[k]]
        out += ["%s not in the start state: %s" % (label, u) for u in new]
    sp = set(snap.get("procs") or [])
    for p in now["procs"]:
        if p in sp:
            continue
        user, comm = p.split(" ", 1)
        if comm in own or comm.startswith(OWN_PREFIXES):
            continue
        out.append("process not in the start state: %s (%s)" % (comm, user))
    return out


def logins_since(since):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(since)))
    rc, out = run(["last", "--since", stamp, "-w"])
    if rc != 0:
        return ["last --since not readable (rc %s): logins since the chain's start not checkable" % rc]
    rows = [ln for ln in out.splitlines() if ln.strip() and not ln.startswith(("wtmp", "reboot"))]
    return ["login since the chain's start: " + ln for ln in rows]


UNIT_PREFIX = "unit started since the chain's start: "
LOGIND_PREFIX = "logind since the chain's start: "
# a login's session scope and the per-user manager a first login starts; never filtered out, each classified: ours
# (a recorded session id; our uid's manager when one of our sessions started too) or foreign
SESSION_SCOPE = re.compile(r"^Start(?:ed|ing) (?:session-(c?\d+)\.scope\b|Session (c?\d+) of [Uu]ser (\S+?)\.?$)")
SESSION_NAME = re.compile(r"Session (\d+) of [Uu]ser (\S+?)\.?$")
USER_UNIT = re.compile(r"^Start(?:ed|ing) (?:(?:user|user-runtime-dir)@(\d+)\.service\b"
                       r"|User (?:Manager|Runtime Directory) (?:for )?(?:UID )?/?(?:run/user/)?(\d+))")
NEW_SESSION = re.compile(r"^New session (\S+) of user (\S+?)\.?$")
CONTAINER_LINE = re.compile(r"container ([0-9a-f]{12,64}) \(epl-[^)\s]+\) started")
SCOPE = re.compile(r"^Start(?:ed|ing) docker-([0-9a-f]{64})\.scope\b")
UNIT = re.compile(r"^Start(?:ed|ing) (\S+?)(?: - |\.\.\.|\.$|$)")
TIMEDATED = "systemd-timedated.service"


def units_since(since):
    rc, out = run(["journalctl", "--since", "@%d" % int(float(since)), "--no-pager", "-q", "-o", "cat", "_PID=1"])
    if rc != 0:
        return ["journal not readable (rc %s): units started since the chain's start not checkable" % rc]
    hits = []
    for ln in out.splitlines():
        t = ln.strip()
        # no line is dropped (a filter on "Session" would hide every other login's session-N.scope); classify()
        # decides what is ours
        if t.startswith(("Started ", "Starting ")):
            hits.append(UNIT_PREFIX + t)
    return hits


def logind_since(since):
    """logind's own "New session <id> of user <name>." lines since SINCE: every login, with or without a terminal."""
    rc, out = run(["journalctl", "--since", "@%d" % int(float(since)), "--no-pager", "-q", "-o", "cat",
                   "-u", "systemd-logind.service"])
    if rc != 0:
        return ["logind journal not readable (rc %s): logins since the chain's start not checkable" % rc]
    return [LOGIND_PREFIX + ln.strip() for ln in out.splitlines() if NEW_SESSION.match(ln.strip())]


def session_items(sessions, own):
    """The login sessions now that are not ours (loginctl); unreadable: not checkable."""
    if sessions is None:
        return ["loginctl not readable: login sessions not checkable"]
    return ["%s (loginctl)" % box_state.describe_session(d) for d in box_state.foreign_sessions(sessions, own)]


def our_containers(runs):
    """The container IDs this session started (full IDs, or the 12-digit IDs the run logs print)."""
    ids = set()
    for f in [os.path.join(runs, "queue.log")] + glob.glob(os.path.join(runs, "chain-*.log")):
        try:
            ids |= set(CONTAINER_LINE.findall(open(f, errors="replace").read()))
        except OSError:
            pass
    for f in glob.glob(os.path.join(runs, "state", "side.json*")):
        try:
            ids |= {c["id"] for c in json.load(open(f)).get("containers") or [] if c.get("id")}
        except (OSError, ValueError, AttributeError, TypeError):
            pass
    return {i for i in ids if len(i) >= 12}


def accepted_timer_units(accepted, snap):
    """The units the accepted timers activate, mapped through the snapshot's timer list ({timer: unit})."""
    tu = snap.get("timer_units") or {}
    return {tu[t] for t in accepted or () if t in tu}


def session_id_of(t):
    """The logind session id a journal line names (a session scope, or logind's "New session <id>"), or None."""
    m = SESSION_SCOPE.match(t)
    if m:
        return m.group(1) or m.group(2)
    m = NEW_SESSION.match(t)
    return m.group(1) if m else None


def classify(items, ours=(), timer_units=(), own_timedated=False, own_sessions=(), uid=None):
    """Splits the end-of-chain findings into (foreign, expected). Only a journal line can be expected: our
    container's scope, an accepted timer's unit, the chain's own timedated, one of OUR recorded login sessions (its
    scope or logind's line), and our uid's user manager or runtime directory when one of our own sessions started
    in the same span. Every other finding (another login, a process, an unreadable journal or loginctl) stays
    foreign."""
    own_sessions = {str(x) for x in own_sessions}
    uid = os.getuid() if uid is None else uid
    ours_started = any(session_id_of(x.split(": ", 1)[1]) in own_sessions for x in items
                       if x.startswith((UNIT_PREFIX, LOGIND_PREFIX)))
    foreign_, expected = [], []
    for x in items:
        why = None
        if x.startswith(LOGIND_PREFIX):
            if session_id_of(x[len(LOGIND_PREFIX):]) in own_sessions:
                why = "our login session (recorded id)"
        elif x.startswith(UNIT_PREFIX):
            t = x[len(UNIT_PREFIX):]
            m = SCOPE.match(t)
            sid = session_id_of(t)
            uu = USER_UNIT.match(t)
            if m:
                if any(m.group(1).startswith(i) for i in ours):
                    why = "our container (ledger)"
            elif sid is not None:
                if sid in own_sessions:
                    why = "our login session (recorded id)"
            elif uu:
                if int(uu.group(1) or uu.group(2)) == int(uid) and ours_started:
                    why = "our uid's user manager, started with one of our sessions"
            else:
                u = UNIT.match(t)
                name = u.group(1) if u else None
                if name and name in timer_units:
                    why = "accepted timer run"
                elif own_timedated and name == TIMEDATED:
                    why = "the chain's own timedatectl"
        (expected.append("%s: %s" % (why, x)) if why else foreign_.append(x))
    return foreign_, expected


def own_sessions_of(runs):
    return box_state.own_session_ids(os.path.join(runs, OWN_SESSIONS)) if runs else set()


def _cfg(path):
    return box_state.load_state(path) if path else {}


def endcheck(snap_path, since, runs=None, own_timedated=False, sessions=False, cfg=None):
    cfg = cfg or {}
    snap = json.load(open(snap_path))
    own = own_sessions_of(runs)
    items = foreign(state(), snap, cfg.get("own_comms") or ()) + logins_since(since)
    if runs:
        sess = box_state.login_sessions() if sessions is False else sessions
        items += session_items(sess, own)
    items += logind_since(since) + units_since(since)
    ours = our_containers(runs) if runs else set()
    bad, exp = classify(items, ours, accepted_timer_units(cfg.get("accepted_timers"), snap), own_timedated, own)
    for x in exp:
        print("EXPECTED " + x)
    for x in bad:
        print("FOREIGN " + x)
    print("end-of-chain foreign check: %s%s" % ("none" if not bad else "%d item(s)" % len(bad),
                                                "; %d expected item(s)" % len(exp) if exp else ""))
    return 1 if bad else 0


def snapshot(out, runs=None, sessions=False, cfg=None):
    """The start state; with `runs`, the logind sessions too: rc 1 when the start holds foreign activity."""
    now = state()
    bad = ["CI-runner process: " + x for x in now["runner"]] + ["interactive login: " + x for x in now["logins"]]
    print("foreign-activity snapshot: %d service units, %s user services, %d timers, %s user timers, %d (user, comm)"
          " pairs; runner processes %d; interactive logins %d" % (
              len(now["services"] or []), "n/a" if now["user_services"] is None else len(now["user_services"]),
              len(now["timers"] or []), "n/a" if now["user_timers"] is None else len(now["user_timers"]),
              len(now["procs"]), len(now["runner"]), len(now["logins"])))
    print("timers at the start: %s" % ", ".join(now["timers"] or []))
    if runs:
        own = own_sessions_of(runs)
        sess = box_state.login_sessions() if sessions is False else sessions
        now["login_sessions"] = sess
        now["own_sessions"] = sorted(own)
        sess_bad = session_items(sess, own)
        print("login sessions at the start: %s; ours (recorded): %s; not ours: %d" % (
            "unreadable" if sess is None else len(sess), sorted(own), len(sess_bad)))
        bad += sess_bad
    with open(out, "w") as f:
        json.dump(now, f, indent=1)
    for x in bad:
        print("FOREIGN " + x)
    print("foreign activity at the start: %s" % ("none" if not bad else "%d item(s)" % len(bad)))
    return 1 if bad else 0


def check(snap_path, runs=None, sessions=False, cfg=None):
    """Nothing foreign now against the snapshot; with `runs`, the logind sessions that are not ours too."""
    cfg = cfg or {}
    snap = json.load(open(snap_path))
    bad = foreign(state(), snap, cfg.get("own_comms") or ())
    if runs:
        sess = box_state.login_sessions() if sessions is False else sessions
        bad += session_items(sess, own_sessions_of(runs))
    for x in bad:
        print("FOREIGN " + x)
    print("foreign activity: %s" % ("none" if not bad else "%d item(s)" % len(bad)))
    return 1 if bad else 0


def main(argv):
    ap = argparse.ArgumentParser(prog="foreign.py")
    ap.add_argument("cmd", choices=["snapshot", "check", "endcheck"])
    ap.add_argument("path", help="snapshot: OUT_JSON; check and endcheck: SNAP_JSON")
    ap.add_argument("since", nargs="?", help="endcheck: epoch seconds of the chain's start")
    ap.add_argument("--runs", help="R: the run directory with state/own-sessions.txt")
    ap.add_argument("--state", help="the operator's state.json (accepted_timers, own_comms)")
    ap.add_argument("--own-timedated", action="store_true")
    a = ap.parse_args(argv)
    if (a.cmd == "endcheck") != (a.since is not None):
        ap.error("SINCE is endcheck's, and endcheck needs it")
    if a.own_timedated and a.cmd != "endcheck":
        ap.error("--own-timedated is endcheck's")
    cfg = _cfg(a.state)
    if a.cmd == "snapshot":
        return snapshot(a.path, a.runs, cfg=cfg)
    if a.cmd == "check":
        return check(a.path, a.runs, cfg=cfg)
    return endcheck(a.path, a.since, a.runs, a.own_timedated, cfg=cfg)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
