#!/usr/bin/env python3
"""The box's start state and the clean proof, against an operator's state.json.

    state.py snapshot OUT_JSON --state STATE_JSON
        The box as found, taken BEFORE anything is staged: the names under $HOME (depth 1), every directory the
        state file lists under `watch` (full depth), dm and loop devices, modules, mounts, TCP and UDP listeners,
        uprobe_events (read with `sudo -n cat`; recorded as not checkable if sudo refuses), MemAvailable.
    state.py proof START_JSON --state STATE_JSON [--pack REL] [--runs REL]... [--staged NAME]... [--final]
                      [--removal] [--own-sessions FILE] [--master-session FILE]
        The clean proof against the start state. rc 0 CLEAN, 1 NOT-CLEAN, 3 NOT-CHECKABLE (uprobe_events or
        loginctl could not be read: it is reported for a human decision and never read as clean). Items: no process
        of ours (Envoy, the client, perf), no container (running or stopped), the listeners as at the start, no
        perf.data, MemAvailable within 2 GiB of the start, no terminal login, no login session that is not recorded
        as ours, dm and loop devices, modules and mounts as at the start, uprobe_events as at the start, and the
        expected-new list of the state file (with --master-session, the master-session check's recorded result is
        an item too: PASS with the id, or "no master session", which is NOT-CLEAN). Anything else new under $HOME
        or a watched directory is NOT-CLEAN. Read-only; nothing is changed.
    state.py master-check
        the master-session check for this login's session, printed only: the record's lines on stdout, nothing
        written anywhere; rc 0 only on PASS.
    state.py master-ok FILE
        rc 0 only when FILE (state/master-session.txt) records a PASS (record_master's first line, MASTER_PASS);
        scripts read the record through this, never with their own pattern.
    state.py master --run-dir R
        the master-session check for this login's logind session. Writes R/state/master-session.txt (the result and
        the evidence) and, on PASS only, appends "<id> master <utc>" to R/state/own-sessions.txt. rc 0 PASS,
        1 refused, 2 no R/state.

The state file (see state.example.json) is written by the operator for one box. Every path in it is relative to
$HOME, and nothing about a particular machine is built into this script:

    watch            directories under $HOME walked to their full depth (e.g. ["epl"])
    pinned           {dir, files: {name: {mode, sha256}}, required}: a directory that must hold exactly these files
                     with these modes and hashes (a pinned client binary, say); `required` true: it must exist
    staged           {name: sha256}: binaries under staged_dir (default epl/bin) that a session may stage; each is
                     allowed only when named with --staged, and must then have its sha256
    staged_dir       where the staged binaries live (default "epl/bin")
    kept             {path: sha256}: files that may be in the start state and must then be unchanged
    kept_dirs        [path]: directories that may be in the start state and must then still be there
    transient        [path]: allowed until --final (the daemon's harness copy, say); at --final they must be gone
    accepted_timers  [timer unit]: timers whose runs the foreign-activity check lists as expected (foreign.py)
    own_comms        [comm]: further process names of this box's own tools, for the foreign-activity check
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

OUR_COMMS = ("envoy", "nighthawk", "perf")
STATE_KEYS = ("_note", "watch", "pinned", "staged", "staged_dir", "kept", "kept_dirs", "transient", "accepted_timers",
              "own_comms")


def load_state(path):
    """The operator's state file, checked: a dict with only the known keys, every path relative and inside $HOME."""
    with open(path) as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        raise ValueError("%s: the state file is a JSON object" % path)
    bad = sorted(set(cfg) - set(STATE_KEYS))
    if bad:
        raise ValueError("%s: unknown keys %s" % (path, bad))
    paths = list(cfg.get("watch") or []) + list(cfg.get("kept") or {}) + list(cfg.get("kept_dirs") or []) \
        + list(cfg.get("transient") or []) + [(cfg.get("pinned") or {}).get("dir") or "", cfg.get("staged_dir") or ""]
    for p in paths:
        if p and (os.path.isabs(p) or ".." in p.split("/")):
            raise ValueError("%s: %r must be relative to $HOME, with no '..'" % (path, p))
    if cfg.get("pinned") and not (cfg["pinned"].get("dir") and isinstance(cfg["pinned"].get("files"), dict)):
        raise ValueError("%s: pinned needs dir and files" % path)
    return cfg


def run(argv, timeout=30):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, str(e)


def names(root, depth):
    if not os.path.isdir(root):
        return None
    out = []
    for dirpath, dirs, files in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        d = 0 if rel == "." else rel.count(os.sep) + 1
        for n in dirs + files:
            out.append(n if rel == "." else os.path.join(rel, n))
        if d + 1 >= depth:
            dirs[:] = []
    return sorted(out)


def uprobes():
    rc, out = run(["sudo", "-n", "cat", "/sys/kernel/tracing/uprobe_events"])
    return out if rc == 0 else {"not_checkable": "sudo -n cat refused or failed (rc %s)" % rc}


FULL = 10 ** 6  # the watched directories are walked to their full depth; $HOME itself at depth 1


def snapshot_state(home, cfg=None):
    up = uprobes()  # sudo first: a ~/.sudo_as_admin_successful it may create is then part of the start state
    rc, lst = run(["ss", "-Hltnu"])
    watch = list((cfg or {}).get("watch") or ["epl"])
    return {"home": names(home, 1), "watched": {w: names(os.path.join(home, w), FULL) for w in watch},
            "dm": sorted(os.listdir("/dev/mapper")) if os.path.isdir("/dev/mapper") else [],
            "loop": sorted(run(["losetup", "-a"])[1].splitlines()),
            "modules": sorted(ln.split()[0] for ln in run(["lsmod"])[1].splitlines()[1:] if ln.split()),
            "mounts": sorted(open("/proc/mounts").read().splitlines()) if os.path.exists("/proc/mounts") else [],
            "listeners": sorted({" ".join((ln.split() + ["", "", "", "", ""])[i] for i in (0, 4))
                                 for ln in lst.splitlines()}) if rc == 0 else None,
            "uprobe_events": up, "mem_available_kb": mem_kb()}


def mem_kb():
    try:
        for ln in open("/proc/meminfo"):
            if ln.startswith("MemAvailable:"):
                return int(ln.split()[1])
    except OSError:
        pass
    return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def _split(path, watched):
    """(watched root, rest) of a $HOME-relative path, or ("", path) when no watched root holds it."""
    for w in sorted(watched, key=len, reverse=True):
        if path == w:
            return "", path
        if path.startswith(w + os.sep):
            return w, path[len(w) + 1:]
    return "", path


def _in_start(start, path):
    w, rest = _split(path, (start.get("watched") or {}).keys())
    names_ = (start.get("watched") or {}).get(w) if w else start.get("home")
    return rest in set(names_ or [])


def expected_new(start, now, home, cfg, pack=None, runs=(), staged=(), final=False, removal=False):
    """The items of the expected-new list, and every new name that is not on it. `pack` and `runs` are relative to
    $HOME and allowed until `final`; at `final` they, and every `transient` path, must be gone whatever the start
    state holds (a start state taken after a run directory was made cannot excuse a leftover).
    `removal` (a cleanup login): the proof that exactly the staged set was removed: the pack, the run directories,
    the transient paths, the pinned directory and every --staged binary must all be absent, nothing else new, and
    the kept items as found. It implies `final`."""
    cfg = cfg or {}
    if removal:
        final = True
    pinned = cfg.get("pinned") or None
    staged_pins = cfg.get("staged") or {}
    sdir = cfg.get("staged_dir") or os.path.join("epl", "bin")
    transient = list(cfg.get("transient") or [])
    items, bad = [], []
    allowed = {os.path.join(sdir, n) for n in staged}
    prefixes = [] if final else [r for r in [pack] + list(runs) + transient if r]
    if pinned and not removal:
        prefixes.append(pinned["dir"])
    for r in list(prefixes) + list(allowed):
        d = os.path.dirname(r)
        while d:
            allowed.add(d)  # a parent made for a run directory (~/epl/runs) or a pinned directory
            d = os.path.dirname(d)
    s0w, s1w = start.get("watched") or {}, now.get("watched") or {}
    roots = [("", start.get("home"), now.get("home"))] + [(w, s0w.get(w), s1w.get(w)) for w in sorted(s1w)]
    for root, n0, n1 in roots:
        for n in sorted(set(n1 or []) - set(n0 or [])):
            full = os.path.join(root, n) if root else n
            if not root and full in s1w and s0w.get(full) is None:
                continue  # a watched directory that is new: its contents are checked below
            if full in allowed or any(full == r or full.startswith(r + os.sep) for r in prefixes):
                continue
            bad.append("new under ~%s: %s" % ("/" + root if root else "", n))
    if final:
        for r in [pack] + list(runs) + transient + ([pinned["dir"]] if pinned and removal else []):
            if r and os.path.lexists(os.path.join(home, r)):
                bad.append("still present at %s: ~/%s" % ("the cleanup login" if removal else "the final proof", r))
    for d in cfg.get("kept_dirs") or []:
        if _in_start(start, d):
            ok = os.path.isdir(os.path.join(home, d))
            items.append("kept %s: %s" % (d, "found as at the start" if ok else "GONE"))
            if not ok:
                bad.append("~/%s was in the start state and is gone" % d)
    for f, want in sorted((cfg.get("kept") or {}).items()):
        if not _in_start(start, f):
            continue  # not in the start state on this box; a new one is caught by the new-name check above
        p = os.path.join(home, f)
        h = sha256(p) if os.path.isfile(p) else None
        items.append("kept %s: sha256 %s: %s" % (f, (h or "missing")[:8], "found as at the start" if h == want
                                                  else "NOT as pinned"))
        if h != want:
            bad.append("~/%s: kept from the start, now sha256 %s (want %s)" % (f, h, want))
    for n in staged:
        p = os.path.join(home, sdir, n)
        want = staged_pins.get(n)
        if want is None:
            bad.append("--staged %s is not a stageable binary of this state file" % n)
            continue
        if removal:
            items.append("removed ~/%s: %s" % (os.path.join(sdir, n), "absent" if not os.path.lexists(p)
                                               else "STILL PRESENT"))
            if os.path.lexists(p):
                bad.append("still present at the cleanup login: ~/%s" % os.path.join(sdir, n))
        elif os.path.isfile(p):
            h = sha256(p)
            items.append("staged %s: sha256 %s...: %s" % (n, h[:8], "ok" if h == want else "NOT as pinned"))
            if h != want:
                bad.append("~/%s: sha256 %s, want %s" % (os.path.join(sdir, n), h, want))
    if not pinned or removal:
        return items, bad
    pd = os.path.join(home, pinned["dir"])
    if pinned.get("required") and not os.path.isdir(pd):
        bad.append("~/%s is missing (the pinned directory stays for the whole session)" % pinned["dir"])
    if os.path.isdir(pd):
        files = pinned["files"]
        got = sorted(os.listdir(pd))
        if got != sorted(files):
            bad.append("~/%s holds %s, not exactly %s" % (pinned["dir"], got, sorted(files)))
        for n, spec in sorted(files.items()):
            p = os.path.join(pd, n)
            if not os.path.isfile(p):
                continue
            mode, want = int(str(spec.get("mode", "0444")), 8), spec.get("sha256")
            m = os.stat(p).st_mode & 0o7777
            h = sha256(p)
            ok = m == mode and h == want
            items.append("pinned %s: mode %o, sha256 %s...: %s" % (n, m, h[:8], "ok" if ok else "NOT as pinned"))
            if not ok:
                bad.append("~/%s/%s: mode %o (want %o), sha256 %s (want %s)" % (pinned["dir"], n, m, mode, h, want))
    return items, bad


# ---------------------------------------------------------------- login sessions
# `who` and `last` list only sessions with a terminal: an `ssh host cmd` or `bash -s` login has none, so they miss
# every non-interactive login, ours and anyone else's. logind sees every PAM session, with or without a tty.
SESSION_PROPS = ("Id", "Name", "User", "Remote", "RemoteHost", "Service", "Type", "Class", "State", "TTY", "Leader",
                 "Timestamp", "TimestampMonotonic")


def parse_list_sessions(text):
    """The session ids of `loginctl list-sessions --no-legend` (first column; a header or footer line is skipped)."""
    out = []
    for ln in (text or "").splitlines():
        f = ln.split()
        # a session row: an id (digits, or c<digits> for a background session) then the numeric uid; a legend or
        # footer ("4 sessions listed.") is not one
        if len(f) >= 3 and (f[0].isdigit() or (f[0][:1] == "c" and f[0][1:].isdigit())) and f[1].isdigit():
            out.append(f[0])
    return out


def parse_show_session(text):
    """{prop: value} of `loginctl show-session ID -p ...` (KEY=VALUE lines)."""
    d = {}
    for ln in (text or "").splitlines():
        k, sep, v = ln.partition("=")
        if sep:
            d[k.strip()] = v.strip()
    return d


def login_sessions(runner=None):
    """[{Id, Name, User, Remote, Service, Type, Class, State, TTY, ...}] of every logind session now, or None when
    loginctl cannot be read (then nothing about logins can be claimed: the caller fails closed)."""
    runner = runner or run
    rc, out = runner(["loginctl", "list-sessions", "--no-legend", "--no-pager"])
    if rc != 0:
        return None
    sess = []
    for sid in parse_list_sessions(out):
        rc2, txt = runner(["loginctl", "show-session", sid, "--no-pager"] + ["-p%s" % p for p in SESSION_PROPS])
        d = parse_show_session(txt) if rc2 == 0 else {}
        d.setdefault("Id", sid)
        if rc2 != 0:
            d["error"] = "show-session rc %s" % rc2
        sess.append(d)
    return sess


def own_session_ids(path):
    """The session ids this session's logins recorded (first word of each line of R/state/own-sessions.txt)."""
    try:
        with open(path) as f:
            return {ln.split()[0] for ln in f if ln.split()}
    except (OSError, TypeError):
        return set()


def describe_session(d):
    return "login session %s: user %s, service %s, type %s, class %s, state %s, tty %s, remote %s" % (
        d.get("Id"), d.get("Name") or d.get("User"), d.get("Service") or "?", d.get("Type") or "?",
        d.get("Class") or "?", d.get("State") or "?", d.get("TTY") or "none", d.get("Remote") or "?")


def foreign_sessions(sess, own):
    """The sessions that are not one of our recorded ids (only those count as expected)."""
    return [d for d in sess or [] if str(d.get("Id")) not in own]


# ---------------------------------------------------------------- the master-session check
# Every mux login shares the ControlMaster connection's logind session (OpenSSH opens the PAM session once per TCP
# connection, in the privileged per-connection process). That session counts as ours only when this check passes.
# The walk reads /proc/<pid>/stat and /proc/<pid>/status only, never exe or cwd: the leader is root-owned and its
# exe is not readable as the user.
MASTER_PROPS = ("Id", "Leader", "User", "Remote", "RemoteHost", "Service", "State")
NO_AUDIT_ID = "4294967295"


def run_all(argv, timeout=30):
    """run() with stderr folded into the output (`ssh -V` prints its version on stderr)."""
    try:
        r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, str(e)


def proc_stat(proc, pid):
    """(pid, comm, ppid, start ticks) from <proc>/<pid>/stat, or None when it cannot be read or parsed."""
    try:
        with open(os.path.join(proc, str(pid), "stat")) as f:
            s = f.read()
        head, sep, rest = s.rpartition(")")
        if not sep:
            return None
        p, _, comm = head.partition(" (")
        r = rest.split()
        return int(p), comm, int(r[1]), int(r[19])     # rest starts at field 3: ppid is field 4, starttime field 22
    except (OSError, ValueError, IndexError):
        return None


def proc_uid(proc, pid):
    """The real uid from <proc>/<pid>/status (`Uid:` real effective saved fs), or None."""
    try:
        with open(os.path.join(proc, str(pid), "status")) as f:
            for ln in f:
                if ln.startswith("Uid:"):
                    return int(ln.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def master_session(proc="/proc", runner=None, env=None, uid=None, ssh_runner=None):
    """{"result": "PASS"|"REFUSED", "id", "reason", "leader", "evidence": [lines]}.
    PASS iff: Id = XDG_SESSION_ID = <proc>/self/sessionid; Leader = L (the nearest uid-0 sshd* ancestor whose child
    on the chain is ours and sshd*), L's start ticks unchanged at the end; User = our uid, Remote=yes, RemoteHost =
    the first field of $SSH_CONNECTION, Service=sshd, State=active; no other session has Leader = L."""
    runner = runner or run
    ssh_runner = ssh_runner or run_all
    env = os.environ if env is None else env
    uid = os.getuid() if uid is None else uid
    ev = []
    out = {"result": "REFUSED", "id": None, "reason": None, "leader": None, "evidence": ev}

    def refuse(why):
        out["reason"] = why
        ev.append("refused: %s" % why)
        return out
    rc, v = ssh_runner(["ssh", "-V"])                    # recorded
    ev.append("ssh -V: rc %s: %s" % (rc, " ".join((v or "").split())))
    # the walk
    me = proc_stat(proc, "self")
    if me is None:
        return refuse("%s/self/stat not readable" % proc)
    chain, pid, leader, child = [], me[0], None, None
    for _ in range(64):
        st = proc_stat(proc, pid)
        u = proc_uid(proc, pid)
        if st is None or u is None:
            return refuse("pid %s: %s not readable" % (pid, "stat" if st is None else "status"))
        chain.append((st[0], st[1], u, st[3]))
        ev.append("chain: pid %d comm %r uid %d start_ticks %d ppid %d" % (st[0], st[1], u, st[3], st[2]))
        if u == 0 and st[1].startswith("sshd") and len(chain) >= 2:
            leader, child = chain[-1], chain[-2]
            break
        if st[2] <= 0:
            break
        pid = st[2]
    if leader is None:
        return refuse("no uid-0 sshd ancestor on the chain")
    if not (child[2] == uid and child[1].startswith("sshd")):
        return refuse("L %d's child on the chain is pid %d comm %r uid %d, not our uid's sshd" % (
            leader[0], child[0], child[1], child[2]))
    out["leader"] = leader[0]
    ev.append("L: pid %d comm %r start_ticks %d" % (leader[0], leader[1], leader[3]))
    # the session
    xdg = (env.get("XDG_SESSION_ID") or "").strip()
    try:
        with open(os.path.join(proc, "self", "sessionid")) as f:
            audit = f.read().strip()
    except OSError:
        audit = ""
    ev.append("XDG_SESSION_ID %r; %s/self/sessionid %r" % (xdg, proc, audit))
    if not xdg or xdg != audit or audit == NO_AUDIT_ID:
        return refuse("XDG_SESSION_ID %r and the audit session id %r do not name one session" % (xdg, audit))
    rc, txt = runner(["loginctl", "show-session", xdg, "-p", "Id", "-p", "Leader", "-p", "User", "-p", "Remote",
                      "-p", "RemoteHost", "-p", "Service", "-p", "State", "--no-pager"])
    ev += ["show-session: %s" % ln for ln in (txt or "").splitlines() if ln.strip()]
    if rc != 0:
        return refuse("show-session %s rc %s" % (xdg, rc))
    d = parse_show_session(txt)
    conn = (env.get("SSH_CONNECTION") or "").split()
    want = {"Id": xdg, "Leader": str(leader[0]), "User": str(uid), "Remote": "yes",
            "RemoteHost": conn[0] if conn else None, "Service": "sshd", "State": "active"}
    for k in MASTER_PROPS:
        if want[k] is None or d.get(k) != want[k]:
            return refuse("%s=%s, expected %s" % (k, d.get(k), want[k] if want[k] is not None
                                                   else "the first field of $SSH_CONNECTION (unset)"))
    rc, lst = runner(["loginctl", "list-sessions", "--no-legend", "--no-pager"])
    if rc != 0:
        return refuse("list-sessions rc %s" % rc)
    for sid in parse_list_sessions(lst):
        if sid == xdg:
            continue
        rc, other = runner(["loginctl", "show-session", sid, "-p", "Leader", "--no-pager"])
        if rc != 0:
            return refuse("show-session %s rc %s (its Leader cannot be checked)" % (sid, rc))
        if parse_show_session(other).get("Leader") == str(leader[0]):
            return refuse("session %s also has Leader %d" % (sid, leader[0]))
    end = proc_stat(proc, leader[0])
    if end is None or end[3] != leader[3]:
        return refuse("L %d's start ticks changed or unreadable at the end (%s against %d)" % (
            leader[0], end and end[3], leader[3]))
    ev.append("L %d start ticks at the end: %d (unchanged)" % (leader[0], end[3]))
    out.update(result="PASS", id=xdg)
    return out


def utc_now():
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def record_master(rundir, res, now=None):
    """state/master-session.txt with the evidence; "<id> master <utc>" appended to own-sessions.txt on PASS only.
    Returns the result line."""
    st = os.path.join(rundir, "state")
    head = ("result: PASS session %s" % res["id"]) if res["result"] == "PASS" else (
        "result: REFUSED: %s" % res["reason"])
    with open(os.path.join(st, "master-session.txt"), "w") as f:
        f.write("\n".join([head] + res["evidence"]) + "\n")
    if res["result"] == "PASS":
        with open(os.path.join(st, "own-sessions.txt"), "a") as f:
            f.write("%s master %s\n" % (res["id"], now or utc_now()))
    return head


MASTER_PASS = "result: PASS session "


def master_passed(path):
    """True only when PATH's first line is record_master's PASS line with a session id."""
    try:
        with open(path) as f:
            first = f.readline().strip()
    except OSError:
        return False
    return first.startswith(MASTER_PASS) and len(first) > len(MASTER_PASS)


def master_item(path):
    """The clean proof's master-session item: the recorded result (PASS with the id), or "no master session"."""
    try:
        with open(path) as f:
            first = f.readline().strip()
    except OSError:
        return "master-session check: no master session (no record at %s)" % path
    if first.startswith(MASTER_PASS):
        return "master-session check: PASS, session %s" % first.split()[-1]
    return "master-session check: no master session (%s)" % (first[len("result: "):] or "empty record")


def proof(start, now, home, cfg=None, pack=None, runs=(), staged=(), final=False, procs=None, containers=None,
          logins=None, perf_data=None, sessions=(), own_sessions=(), master=None, removal=False):
    """(lines, result) of the clean proof; result CLEAN, NOT-CLEAN or NOT-CHECKABLE."""
    lines, bad = [], []

    def item(text, ok):
        lines.append("clean: %s%s" % (text, "" if ok else "  <-- NOT-CLEAN"))
        if not ok:
            bad.append(text)
    ours = [p for p in (procs or []) if p.split()[-1].startswith(OUR_COMMS)]
    item("processes of ours (envoy, nighthawk, perf): %d %s" % (len(ours), ours[:5]), not ours)
    # every container, running or stopped (docker ps -aq): a stopped container left behind is NOT-CLEAN
    item("containers (all, running or stopped): %s (0)" % containers, containers == 0)
    item("listeners as at the start: %s" % ("yes" if now["listeners"] == start["listeners"] else "NO (%s)" % sorted(
        set(now["listeners"] or []) ^ set(start["listeners"] or []))), now["listeners"] == start["listeners"])
    item("perf.data files: %s (0)" % perf_data, perf_data == 0)
    m0, m1 = start.get("mem_available_kb"), now.get("mem_available_kb")
    ok = m0 is not None and m1 is not None and m0 - m1 <= 2 * 1024 * 1024
    item("MemAvailable %s MiB (start %s MiB, within 2 GiB)" % (m1 and m1 // 1024, m0 and m0 // 1024), ok)
    item("terminal logins (who): %d (0)" % len(logins or []), not logins)
    if sessions is None:
        lines.append("clean: login sessions NOT CHECKABLE (loginctl not readable): for a human decision, never read "
                     "as clean")
    else:
        fs = foreign_sessions(sessions, set(own_sessions or ()))
        item("login sessions that are not ours (loginctl, %d recorded as ours): %d (0)%s" % (
            len(set(own_sessions or ())), len(fs), "".join("; " + describe_session(d) for d in fs[:5])), not fs)
    if master is not None:
        # PASS with the id, or "no master session", which is NOT-CLEAN
        item(master, ": PASS, session " in master)
    for k, label in (("dm", "dm devices"), ("loop", "loop devices"), ("modules", "modules"), ("mounts", "mounts")):
        item("%s as at the start: %s" % (label, "yes" if now[k] == start[k] else "NO"), now[k] == start[k])
    checkable = True
    u0, u1 = start.get("uprobe_events"), now.get("uprobe_events")
    if isinstance(u0, dict) or isinstance(u1, dict):
        checkable = False
        lines.append("clean: uprobe_events NOT CHECKABLE (%s): for a human decision, never read as clean"
                     % ((u1 if isinstance(u1, dict) else u0).get("not_checkable")))
    else:
        item("uprobe_events as at the start: %s" % ("yes" if u0 == u1 else "NO"), u0 == u1)
    items, new_bad = expected_new(start, now, home, cfg, pack, runs, staged, final, removal)
    lines.append("clean: new names checked under ~ (depth 1) and %s (full depth)" % (
        ", ".join("~/" + w for w in sorted(now.get("watched") or {})) or "no watched directory"))
    lines += ["clean: expected-new %s" % x for x in items]
    for x in new_bad:
        item(x, False)
    if not new_bad:
        lines.append("clean: nothing new outside the expected-new list")
    if sessions is None:
        checkable = False
    result = "NOT-CLEAN" if bad else ("NOT-CHECKABLE" if not checkable else "CLEAN")
    lines.append("result: %s" % result)
    return lines, result


def live(home, runs):
    rc, ps = run(["ps", "-u", str(os.getuid()), "-o", "pid=,comm="])
    rc2, dk = run(["docker", "ps", "-aq"])
    rc3, who = run(["who"])
    n = 0
    for r in runs:
        for dirpath, _, files in os.walk(os.path.join(home, r)):
            n += sum(1 for f in files if f == "perf.data" or f.startswith("perf.data."))
    return {"procs": [ln.strip() for ln in ps.splitlines() if ln.strip()],
            "containers": len(dk.split()) if rc2 == 0 else None,
            "logins": [ln for ln in who.splitlines() if ln.strip()], "perf_data": n, "sessions": login_sessions()}


def main(argv):
    if argv[:1] == ["snapshot"]:
        sp = argparse.ArgumentParser(prog="state.py snapshot")
        sp.add_argument("cmd", choices=["snapshot"])
        sp.add_argument("out")
        sp.add_argument("--state", required=True, help="the operator's state.json")
        a = sp.parse_args(argv)
        st = snapshot_state(os.path.expanduser("~"), load_state(a.state))
        with open(a.out, "w") as f:
            json.dump(st, f, indent=1)
        print("start state: %d names in ~, %s; uprobe_events %s" % (
            len(st["home"] or []), ", ".join("%s in ~/%s" % ("none" if v is None else len(v), w)
                                             for w, v in sorted(st["watched"].items())),
            "not checkable" if isinstance(st["uprobe_events"], dict) else "read"))
        return 0
    if argv == ["master-check"]:
        # the master-session check for this login's session, written to stdout only (record_master's lines: the
        # result line first, then the evidence); nothing is written to any run directory. rc 0 only on PASS
        res = master_session()
        head = ("result: PASS session %s" % res["id"]) if res["result"] == "PASS" else (
            "result: REFUSED: %s" % res["reason"])
        print("\n".join([head] + res["evidence"]))
        return 0 if res["result"] == "PASS" else 1
    if argv[:1] == ["master-ok"] and len(argv) == 2:
        # the one reader of a recorded master-session result: rc 0 only on PASS
        item = master_item(argv[1])
        print(item)
        return 0 if master_passed(argv[1]) else 1
    if argv[:1] == ["master"]:
        mp = argparse.ArgumentParser(prog="state.py master")
        mp.add_argument("cmd", choices=["master"])
        mp.add_argument("--run-dir", required=True, help="R: the run directory holding state/")
        m = mp.parse_args(argv)
        if not os.path.isdir(os.path.join(m.run_dir, "state")):
            print("master-session check: no state directory under %s: refused" % m.run_dir)
            return 2
        res = master_session()
        head = record_master(m.run_dir, res)
        print("master-session check: %s" % head[len("result: "):])
        print("\n".join("  " + x for x in res["evidence"]))
        return 0 if res["result"] == "PASS" else 1
    ap = argparse.ArgumentParser(prog="state.py proof")
    ap.add_argument("cmd", choices=["proof"])
    ap.add_argument("start")
    ap.add_argument("--state", required=True, help="the operator's state.json (the expected-new list)")
    ap.add_argument("--pack", help="the harness copy, relative to $HOME; allowed until --final")
    ap.add_argument("--runs", action="append", default=[], help="a run directory relative to $HOME (repeatable)")
    ap.add_argument("--staged", action="append", default=[], help="a binary of the state file's `staged` list")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--removal", action="store_true",
                    help="a cleanup login: prove the staged set removed (implies --final; the pinned directory and "
                         "every --staged binary must be absent)")
    ap.add_argument("--own-sessions", help="R/state/own-sessions.txt: the logind session ids of this session's logins")
    ap.add_argument("--master-session", help="R/state/master-session.txt: the master-session check's record")
    a = ap.parse_args(argv)
    cfg = load_state(a.state)
    bad = sorted(set(a.staged) - set(cfg.get("staged") or {}))
    if bad:
        ap.error("--staged %s: not in the state file's staged list" % ", ".join(bad))
    home = os.path.expanduser("~")
    start = json.load(open(a.start))
    lv = live(home, a.runs)
    lines, result = proof(start, snapshot_state(home, cfg), home, cfg, a.pack, a.runs, a.staged, a.final,
                          lv["procs"], lv["containers"], lv["logins"], lv["perf_data"],
                          sessions=lv["sessions"], own_sessions=own_session_ids(a.own_sessions),
                          master=master_item(a.master_session) if a.master_session else None, removal=a.removal)
    print("\n".join(lines))
    return {"CLEAN": 0, "NOT-CLEAN": 1, "NOT-CHECKABLE": 3}[result]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
