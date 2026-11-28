"""The foreign-activity check (loop/foreign.py) and the clean proof (loop/state.py) see every login, with or without a
terminal (loginctl list-sessions and show-session; logind's "New session" lines), count only our recorded session ids
as expected, and classify the journal's session-scope lines instead of dropping them. Sample outputs as systemd 255
writes them. The clean proof's expected-new list comes from the operator's state file."""
import importlib.util
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "loop")


def mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


st = mod("state_t", os.path.join(S, "state.py"))
fo = mod("foreign_t", os.path.join(S, "foreign.py"))

# `loginctl list-sessions --no-legend --no-pager` (systemd 255): ours (41: the pre-flight login that holds the
# detached chain; 57: a later login), another user's non-interactive ssh login (63, no tty), and a cron session (c2)
LIST = """     41 1000 bench -    -     active no   -
     57 1000 bench -    -     active no   -
     63 1001 runner  -    -     active no   -
     c2    0 root    -    -     active no   -
"""
SHOW = {"41": "Id=41\nName=bench\nUser=1000\nRemote=yes\nService=sshd\nType=tty\nClass=user\nState=active\nTTY=\n",
        "57": "Id=57\nName=bench\nUser=1000\nRemote=yes\nService=sshd\nType=tty\nClass=user\nState=active\nTTY=\n",
        "63": "Id=63\nName=runner\nUser=1001\nRemote=yes\nService=sshd\nType=tty\nClass=user\nState=active\nTTY=\n",
        "c2": "Id=c2\nName=root\nUser=0\nRemote=no\nService=crond\nType=unspecified\nClass=background\nState=active\nTTY=\n"}

# journalctl _PID=1 -o cat since the chain's start
JOURNAL = """Started session-57.scope - Session 57 of User bench.
Starting user@1001.service - User Manager for UID 1001...
Started user@1001.service - User Manager for UID 1001.
Started session-63.scope - Session 63 of User runner.
Started docker-%s.scope - libcontainer container %s.
Started apt-daily.service - Daily apt download activities.
Started Session 70 of User root.
""" % ("a" * 64, "a" * 64)
LOGIND = """New session 57 of user bench.
Session 41 logged out. Waiting for processes to exit.
New session 63 of user runner.
"""


def runner(outputs):
    def run(argv, timeout=30):
        key = " ".join(argv[:3])
        if argv[:2] == ["loginctl", "list-sessions"]:
            return outputs.get("list", (0, LIST))
        if argv[:2] == ["loginctl", "show-session"]:
            return 0, SHOW.get(argv[2], "")
        return outputs.get(key, (1, ""))
    return run


class LoginctlParseTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(st.parse_list_sessions(LIST), ["41", "57", "63", "c2"])
        self.assertEqual(st.parse_list_sessions("SESSION  UID USER SEAT TTY\n\n4 sessions listed.\n"), [])
        d = st.parse_show_session(SHOW["63"])
        self.assertEqual((d["Id"], d["Name"], d["Service"], d["TTY"]), ("63", "runner", "sshd", ""))

    def test_sessions_and_ours(self):
        sess = st.login_sessions(runner({}))
        self.assertEqual([d["Id"] for d in sess], ["41", "57", "63", "c2"])
        f = st.foreign_sessions(sess, {"41", "57"})
        self.assertEqual([d["Id"] for d in f], ["63", "c2"])
        self.assertIn("login session 63: user runner, service sshd", st.describe_session(f[0]))
        self.assertIn("tty none", st.describe_session(f[0]))  # no terminal: who and last never list it
        self.assertIsNone(st.login_sessions(runner({"list": (1, "")})))  # unreadable: nothing can be claimed

    def test_own_ids_file(self):
        p = os.path.join(tempfile.mkdtemp(), "own-sessions.txt")
        with open(p, "w") as f:
            f.write("41 login-pre 2026-01-01T10:00:00Z\n57 login-collect 2026-01-01T11:00:00Z\n\n")
        self.assertEqual(st.own_session_ids(p), {"41", "57"})
        self.assertEqual(st.own_session_ids(p + ".missing"), set())


class CleanProofSessionsTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.home, "epl", "bin"))
        self.start = dict(st.snapshot_state(self.home), mem_available_kb=8 << 20, uprobe_events="")
        self.kw = dict(procs=["1 bash"], containers=0, logins=[], perf_data=0)

    def proof(self, **kw):
        return st.proof(self.start, dict(self.start), self.home, **dict(self.kw, **kw))

    def test_items(self):
        sess = st.login_sessions(runner({}))
        lines, res = self.proof(sessions=sess, own_sessions={"41", "57"})
        self.assertEqual(res, "NOT-CLEAN")
        self.assertTrue(any("login sessions that are not ours" in x and "login session 63" in x for x in lines))
        _, res = self.proof(sessions=[d for d in sess if d["Id"] in ("41", "57")], own_sessions={"41", "57"})
        self.assertEqual(res, "CLEAN")
        lines, res = self.proof(sessions=None, own_sessions={"41"})
        self.assertEqual(res, "NOT-CHECKABLE")
        self.assertTrue(any("login sessions NOT CHECKABLE" in x for x in lines))
        # our own session without its id recorded is not ours: fail closed
        _, res = self.proof(sessions=[d for d in sess if d["Id"] == "57"], own_sessions=set())
        self.assertEqual(res, "NOT-CLEAN")


class JournalClassifyTest(unittest.TestCase):
    def items(self, journal=JOURNAL, logind=LOGIND):
        return ([fo.UNIT_PREFIX + ln for ln in journal.splitlines() if ln.startswith(("Started", "Starting"))]
                + [fo.LOGIND_PREFIX + ln for ln in logind.splitlines() if fo.NEW_SESSION.match(ln)])

    def test_nothing_is_dropped(self):
        real = fo.run
        fo.run = lambda argv, timeout=20: (0, JOURNAL)
        try:
            hits = fo.units_since(0)
        finally:
            fo.run = real
        self.assertEqual(len(hits), 7)
        self.assertTrue(any("session-63.scope" in x for x in hits))  # the old filter dropped this one

    def test_classify(self):
        bad, exp = fo.classify(self.items(), ours={"a" * 12}, timer_units={"apt-daily.service"},
                               own_sessions={"41", "57"}, uid=1000)
        b = "\n".join(bad)
        self.assertIn("session-63.scope - Session 63 of User runner", b)
        self.assertIn("Started Session 70 of User root", b)
        self.assertIn("user@1001.service", b)           # another uid's first login
        self.assertIn("New session 63 of user runner", b)
        e = "\n".join(exp)
        self.assertIn("our login session (recorded id): unit started since the chain's start: Started session-57.scope", e)
        self.assertIn("our login session (recorded id): logind since the chain's start: New session 57", e)
        self.assertIn("our container (ledger)", e)
        self.assertIn("accepted timer run", e)
        self.assertEqual(len(bad) + len(exp), len(self.items()))

    def test_background_scope_id(self):
        # a background session's scope (c<digits>) yields its id, the same form as logind's "New session c2"
        self.assertEqual(fo.session_id_of("Started session-c2.scope - Session c2 of User bench."), "c2")
        self.assertEqual(fo.session_id_of("Started Session c2 of User bench."), "c2")
        line = fo.UNIT_PREFIX + "Started session-c2.scope - Session c2 of User bench."
        bad, exp = fo.classify([line], own_sessions={"c2"}, uid=1000)
        self.assertEqual((bad, len(exp)), ([], 1))
        bad, exp = fo.classify([line], own_sessions={"41"}, uid=1000)
        self.assertEqual((len(bad), exp), (1, []))

    def test_our_user_manager(self):
        mgr = fo.UNIT_PREFIX + "Started user@1000.service - User Manager for UID 1000."
        own = fo.UNIT_PREFIX + "Started session-57.scope - Session 57 of User bench."
        self.assertEqual(fo.classify([mgr, own], own_sessions={"57"}, uid=1000)[0], [])
        # our uid's manager with no session of ours started: some other login of our uid started it
        bad, _ = fo.classify([mgr], own_sessions={"57"}, uid=1000)
        self.assertEqual(bad, [mgr])
        bad, _ = fo.classify([mgr, own], own_sessions={"99"}, uid=1000)
        self.assertEqual(len(bad), 2)


class ForeignCliTest(unittest.TestCase):
    def setUp(self):
        self.runs = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.runs, "state"))
        with open(os.path.join(self.runs, "state", "own-sessions.txt"), "w") as f:
            f.write("41 login-pre x\n")
        self.real = fo.state
        fo.state = lambda: {"services": [], "user_services": [], "timers": [], "user_timers": [],
                            "timer_units": {"apt-daily.timer": "apt-daily.service"}, "procs": [], "runner": [],
                            "logins": []}

    def tearDown(self):
        fo.state = self.real

    def test_snapshot_and_check(self):
        out = os.path.join(self.runs, "state", "foreign-start.json")
        sess = st.login_sessions(runner({}))
        self.assertEqual(fo.snapshot(out, self.runs, sessions=[d for d in sess if d["Id"] == "41"]), 0)
        with open(out) as f:
            snap = json.load(f)
        self.assertEqual(snap["own_sessions"], ["41"])
        self.assertEqual(snap["timer_units"], {"apt-daily.timer": "apt-daily.service"})
        self.assertEqual(fo.snapshot(out, self.runs, sessions=sess), 1)  # 57, 63 and c2 are not ours at the start
        self.assertEqual(fo.check(out, self.runs, sessions=[d for d in sess if d["Id"] == "41"]), 0)
        self.assertEqual(fo.check(out, self.runs, sessions=sess), 1)
        self.assertEqual(fo.check(out, self.runs, sessions=None), 1)  # loginctl unreadable: fail closed

    def test_process_and_own_comms(self):
        snap = os.path.join(self.runs, "snap.json")
        with open(snap, "w") as f:
            json.dump({"procs": [], "services": [], "timers": []}, f)
        base = fo.state()
        fo.state = lambda: dict(base, procs=["bench mytool", "bench envoy-x", "bench bash"])
        self.assertEqual(fo.check(snap), 1)                           # mytool is not one of ours
        self.assertEqual(fo.check(snap, cfg={"own_comms": ["mytool"]}), 0)
        fo.state = lambda: dict(base, services=["new.service"])
        self.assertEqual(fo.check(snap), 1)                           # a service not in the start state

    def test_endcheck(self):
        snap = os.path.join(self.runs, "snap.json")
        with open(snap, "w") as f:
            json.dump({"procs": [], "timer_units": {"apt-daily.timer": "apt-daily.service"}}, f)
        saved = (fo.logins_since, fo.logind_since, fo.units_since)
        fo.logins_since = lambda since: []
        fo.logind_since = lambda since: [fo.LOGIND_PREFIX + "New session 41 of user bench."]
        fo.units_since = lambda since: [fo.UNIT_PREFIX + "Started session-41.scope - Session 41 of User bench."]
        try:
            sess = st.login_sessions(runner({}))
            self.assertEqual(fo.endcheck(snap, 0, self.runs, sessions=[d for d in sess if d["Id"] == "41"]), 0)
            self.assertEqual(fo.endcheck(snap, 0, self.runs, sessions=sess), 1)
            fo.units_since = lambda since: [fo.UNIT_PREFIX + "Started session-63.scope - Session 63 of User runner."]
            self.assertEqual(fo.endcheck(snap, 0, self.runs, sessions=[d for d in sess if d["Id"] == "41"]), 1)
            # an accepted timer's run is expected only through the state file
            fo.units_since = lambda since: [fo.UNIT_PREFIX + "Started apt-daily.service - Daily apt download activities."]
            one = [d for d in sess if d["Id"] == "41"]
            self.assertEqual(fo.endcheck(snap, 0, self.runs, sessions=one), 1)
            self.assertEqual(fo.endcheck(snap, 0, self.runs, sessions=one, cfg={"accepted_timers": ["apt-daily.timer"]}),
                             0)
        finally:
            fo.logins_since, fo.logind_since, fo.units_since = saved

    def test_cli(self):
        with self.assertRaises(SystemExit):
            fo.main(["endcheck", "x"])                                # endcheck needs SINCE
        with self.assertRaises(SystemExit):
            fo.main(["check", "x", "5"])                              # SINCE is endcheck's
        with self.assertRaises(SystemExit):
            fo.main(["check", "x", "--own-timedated"])


class StateFileTest(unittest.TestCase):
    """The clean proof's expected-new list comes from the operator's state file (loop/state.example.json)."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.pins = os.path.join(self.home, "epl", "pins", "client")
        os.makedirs(os.path.join(self.home, "epl", "bin"))
        self.cfg = {"watch": ["epl"], "transient": ["epl/loop"], "staged": {"envoy-x": None},
                    "pinned": {"dir": "epl/pins/client", "required": True,
                               "files": {"nighthawk_client": {"mode": "0555", "sha256": None}}}}
        self.start = self.snap()
        self.kw = dict(procs=["1 bash"], containers=0, logins=[], perf_data=0, sessions=[])

    def snap(self):
        return dict(st.snapshot_state(self.home, self.cfg), mem_available_kb=8 << 20, uprobe_events="", dm=[],
                    loop=[], modules=[], mounts=[], listeners=[])

    def write(self, rel, text, mode=0o644):
        p = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        os.chmod(p, mode)
        return st.sha256(p)

    def proof(self, **kw):
        return st.proof(self.start, self.snap(), self.home, self.cfg, **dict(self.kw, **kw))

    def test_example_file_loads(self):
        cfg = st.load_state(os.path.join(S, "state.example.json"))
        self.assertIn("apt-daily.timer", cfg["accepted_timers"])
        self.assertEqual(cfg["transient"], ["epl/loop"])

    def test_load_refuses(self):
        d = tempfile.mkdtemp()
        for bad in ({"unknown": 1}, {"watch": ["/etc"]}, {"transient": ["../x"]}, {"pinned": {"dir": "p"}}, []):
            p = os.path.join(d, "s.json")
            with open(p, "w") as f:
                json.dump(bad, f)
            with self.assertRaises(ValueError):
                st.load_state(p)

    def test_pinned_and_transient(self):
        lines, res = self.proof()
        self.assertEqual(res, "NOT-CLEAN")                            # the required pinned directory is missing
        self.assertTrue(any("epl/pins/client is missing" in x for x in lines))
        h = self.write("epl/pins/client/nighthawk_client", "client", 0o555)
        self.cfg["pinned"]["files"]["nighthawk_client"]["sha256"] = h
        self.write("epl/loop/harness/README.md", "x")
        self.write("epl/runs/loop/x.log", "x")
        _, res = self.proof(runs=["epl/runs/loop"])
        self.assertEqual(res, "CLEAN")                                # pinned, transient and a run dir: allowed
        lines, res = self.proof(runs=["epl/runs/loop"], final=True)
        self.assertEqual(res, "NOT-CLEAN")                            # at the final proof they must be gone
        self.assertTrue(any("still present at the final proof: ~/epl/loop" in x for x in lines))
        self.assertTrue(any("still present at the final proof: ~/epl/runs/loop" in x for x in lines))
        os.chmod(os.path.join(self.pins, "nighthawk_client"), 0o755)
        lines, _ = self.proof(runs=["epl/runs/loop"])
        self.assertTrue(any("mode 755 (want 555)" in x for x in lines))

    def test_new_names_and_staged(self):
        self.cfg["pinned"]["required"] = False
        self.write("epl/stray.txt", "x")
        lines, res = self.proof()
        self.assertEqual(res, "NOT-CLEAN")
        self.assertTrue(any("new under ~/epl: stray.txt" in x for x in lines))
        os.remove(os.path.join(self.home, "epl", "stray.txt"))
        h = self.write("epl/bin/envoy-x", "envoy")
        self.assertEqual(self.proof()[1], "NOT-CLEAN")                # staged but not named with --staged
        self.cfg["staged"]["envoy-x"] = h
        self.assertEqual(self.proof(staged=["envoy-x"])[1], "CLEAN")
        lines, res = self.proof(staged=["envoy-x"], removal=True)
        self.assertEqual(res, "NOT-CLEAN")
        self.assertTrue(any("still present at the cleanup login: ~/epl/bin/envoy-x" in x for x in lines))

    def test_kept(self):
        self.cfg["pinned"] = None
        h = self.write("epl/bin/old", "kept")
        self.cfg["kept"] = {"epl/bin/old": h}
        self.start = self.snap()
        self.assertEqual(self.proof()[1], "CLEAN")
        self.write("epl/bin/old", "changed")
        lines, res = self.proof()
        self.assertEqual(res, "NOT-CLEAN")
        self.assertTrue(any("kept from the start, now sha256" in x for x in lines))


if __name__ == "__main__":
    unittest.main()
