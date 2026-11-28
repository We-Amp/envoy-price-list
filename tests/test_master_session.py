"""The master-session check (loop/state.py): which logind session a ControlMaster's mux logins share, against fake
/proc trees. RFC 5737 documentation addresses for the workstation and the box."""
import importlib.util
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("state_m", os.path.join(ROOT, "loop", "state.py"))
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

UID = 1000
PEER = "192.0.2.20"
ENV = {"XDG_SESSION_ID": "912", "SSH_CONNECTION": PEER + " 50122 198.51.100.30 22"}

# (pid, comm, uid, ppid, start ticks): the listener, the per-connection monitor (L), our sshd, bash, python3
OLD = [(1180, "sshd", 0, 1, 2100), (448001, "sshd", 0, 1180, 9000100), (448010, "sshd", UID, 448001, 9000140),
       (448011, "bash", UID, 448010, 9000150), (448200, "python3", UID, 448011, 9000400)]   # OpenSSH < 9.8
NEW = [(1180, "sshd", 0, 1, 2100), (448001, "sshd-session", 0, 1180, 9000100),
       (448010, "sshd-session", UID, 448001, 9000140), (448011, "bash", UID, 448010, 9000150),
       (448200, "python3", UID, 448011, 9000400)]                                            # OpenSSH >= 9.8
LEADER = 448001


def stat_line(pid, comm, ppid, ticks):
    # fields 3.. : state ppid pgrp session tty_nr tpgid flags minflt cminflt majflt cmajflt utime stime cutime cstime
    # priority nice num_threads itrealvalue starttime (field 22) ...
    rest = ["S", str(ppid)] + ["0"] * 17 + [str(ticks)] + ["0"] * 10
    return "%d (%s) %s\n" % (pid, comm, " ".join(rest))


def show(sid="912", leader=LEADER, user=UID, remote="yes", host=PEER, service="sshd", state="active"):
    return ("Id=%s\nLeader=%s\nUser=%s\nRemote=%s\nRemoteHost=%s\nService=%s\nState=%s\n"
            % (sid, leader, user, remote, host, service, state))


class Fake:
    def __init__(self, sessions):
        self.sessions = sessions     # {id: show-session text}
        self.calls = []

    def __call__(self, argv, timeout=30):
        self.calls.append(argv)
        if argv[:2] == ["loginctl", "list-sessions"]:
            return 0, "".join("%7s %d bench - - active no -\n" % (s, UID) for s in self.sessions) + \
                "\n%d sessions listed.\n" % len(self.sessions)
        if argv[:2] == ["loginctl", "show-session"]:
            t = self.sessions.get(argv[2])
            return (0, t) if t is not None else (1, "")
        return 99, "unexpected %s" % argv


def ssh_v(argv, timeout=30):
    return 0, "OpenSSH_9.6p1 Ubuntu-3ubuntu13.14, OpenSSL 3.0.13 30 Jan 2024\n"


class MasterSessionTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)

    def tree(self, procs, sessionid="912", exe_readable=True):
        p = tempfile.mkdtemp(prefix="proc", dir=self.d)
        for pid, comm, uid, ppid, ticks in procs:
            q = os.path.join(p, str(pid))
            os.makedirs(q)
            with open(os.path.join(q, "stat"), "w") as f:
                f.write(stat_line(pid, comm, ppid, ticks))
            with open(os.path.join(q, "status"), "w") as f:
                f.write("Name:\t%s\nPPid:\t%d\nUid:\t%d\t%d\t%d\t%d\n" % (comm, ppid, uid, uid, uid, uid))
            if uid == 0 and not exe_readable:
                os.symlink("/nonexistent-root-only", os.path.join(q, "exe"))
                os.symlink("/nonexistent-root-only", os.path.join(q, "cwd"))
        os.symlink(str(procs[-1][0]), os.path.join(p, "self"))
        with open(os.path.join(p, str(procs[-1][0]), "sessionid"), "w") as f:
            f.write(sessionid)
        return p

    def check(self, procs=OLD, sessions=None, env=ENV, **kw):
        p = self.tree(procs, **kw)
        fake = Fake(sessions if sessions is not None else {"912": show()})
        return st.master_session(proc=p, runner=fake, env=env, uid=UID, ssh_runner=ssh_v), fake

    # the ten cases of the check
    def test_old_layout_priv_monitor_passes(self):
        r, _ = self.check(OLD)
        self.assertEqual((r["result"], r["id"], r["leader"]), ("PASS", "912", LEADER), r["evidence"])

    def test_new_layout_sshd_session_passes(self):
        r, _ = self.check(NEW)
        self.assertEqual((r["result"], r["leader"]), ("PASS", LEADER), r["evidence"])

    def test_exe_not_readable_must_pass(self):
        r, fake = self.check(OLD, exe_readable=False)
        self.assertEqual(r["result"], "PASS", r["evidence"])

    def test_remote_host_mismatch_refused(self):
        r, _ = self.check(sessions={"912": show(host="192.0.2.9")})
        self.assertEqual(r["result"], "REFUSED")
        self.assertIn("RemoteHost", r["reason"])

    def test_id_not_xdg_session_id_refused(self):
        r, _ = self.check(sessions={"912": show(sid="913")})
        self.assertEqual(r["result"], "REFUSED")
        self.assertIn("Id=913", r["reason"])
        r, _ = self.check(env={"XDG_SESSION_ID": "913", "SSH_CONNECTION": ENV["SSH_CONNECTION"]})
        self.assertEqual(r["result"], "REFUSED")
        self.assertIn("audit session id", r["reason"])

    def test_matching_master_session(self):
        r, fake = self.check(sessions={"912": show(), "c3": show(sid="c3", leader=2222, user=0, remote="no",
                                                                  service="crond")})
        self.assertEqual(r["result"], "PASS", r["evidence"])
        self.assertIn(["loginctl", "show-session", "912", "-p", "Id", "-p", "Leader", "-p", "User", "-p", "Remote",
                       "-p", "RemoteHost", "-p", "Service", "-p", "State", "--no-pager"], fake.calls)

    def test_no_master_session_refused(self):
        r, _ = self.check(sessions={})                       # show-session of our id fails: no such session
        self.assertEqual(r["result"], "REFUSED")
        no_sshd = [(1, "systemd", 0, 0, 1), (5000, "bash", UID, 1, 70), (5001, "python3", UID, 5000, 80)]
        r, _ = self.check(no_sshd)
        self.assertEqual(r["result"], "REFUSED")
        self.assertIn("no uid-0 sshd ancestor", r["reason"])

    def test_second_session_same_leader_refused(self):
        r, _ = self.check(sessions={"912": show(), "915": show(sid="915")})
        self.assertEqual(r["result"], "REFUSED")
        self.assertIn("session 915 also has Leader %d" % LEADER, r["reason"])

    def test_other_users_session_refused(self):
        r, _ = self.check(sessions={"912": show(user=1001)})
        self.assertEqual(r["result"], "REFUSED")
        self.assertIn("User=1001", r["reason"])
        # our login under another user's sshd child (L's child not ours)
        other = [(1180, "sshd", 0, 1, 2100), (448001, "sshd", 0, 1180, 9000100), (448010, "sshd", 1001, 448001, 1),
                 (448011, "bash", UID, 448010, 2), (448200, "python3", UID, 448011, 3)]
        r, _ = self.check(other)
        self.assertEqual(r["result"], "REFUSED")
        self.assertIn("not our uid's sshd", r["reason"])

    def test_unreadable_stat_or_status_refused(self):
        for name in ("stat", "status"):
            p = self.tree(OLD)
            os.remove(os.path.join(p, "448010", name))
            r = st.master_session(proc=p, runner=Fake({"912": show()}), env=ENV, uid=UID, ssh_runner=ssh_v)
            self.assertEqual(r["result"], "REFUSED", name)
            self.assertIn("pid 448010: %s not readable" % name, r["reason"])

    # the other PASS conditions, the end recheck and the record
    def test_other_conditions(self):
        for kw, word in ((dict(remote="no"), "Remote=no"), (dict(service="cron"), "Service=cron"),
                         (dict(state="closing"), "State=closing"), (dict(leader=448010), "Leader=448010")):
            r, _ = self.check(sessions={"912": show(**kw)})
            self.assertEqual(r["result"], "REFUSED", kw)
            self.assertIn(word, r["reason"])
        r, _ = self.check(env={"XDG_SESSION_ID": "912"})       # no $SSH_CONNECTION
        self.assertEqual(r["result"], "REFUSED")
        r, _ = self.check(sessionid="4294967295", env={"XDG_SESSION_ID": "4294967295",
                                                       "SSH_CONNECTION": ENV["SSH_CONNECTION"]})
        self.assertEqual(r["result"], "REFUSED")

    def test_leader_start_ticks_rechecked(self):
        p = self.tree(OLD)
        fake = Fake({"912": show()})

        def runner(argv, timeout=30):
            if argv[:2] == ["loginctl", "list-sessions"]:      # L restarts between the walk and the end
                with open(os.path.join(p, str(LEADER), "stat"), "w") as f:
                    f.write(stat_line(LEADER, "sshd", 1180, 9999999))
            return fake(argv)
        r = st.master_session(proc=p, runner=runner, env=ENV, uid=UID, ssh_runner=ssh_v)
        self.assertEqual(r["result"], "REFUSED")
        self.assertIn("start ticks changed", r["reason"])

    def test_record_and_proof_item(self):
        rd = os.path.join(self.d, "runs")
        os.makedirs(os.path.join(rd, "state"))
        r, _ = self.check(OLD)
        head = st.record_master(rd, r, now="2026-11-27T08:00:00Z")
        self.assertEqual(head, "result: PASS session 912")
        with open(os.path.join(rd, "state", "own-sessions.txt")) as f:
            self.assertEqual(f.read(), "912 master 2026-11-27T08:00:00Z\n")
        rec = os.path.join(rd, "state", "master-session.txt")
        with open(rec) as f:
            txt = f.read()
        self.assertIn("ssh -V: rc 0: OpenSSH_9.6p1", txt)
        self.assertIn("chain: pid 448001 comm 'sshd' uid 0 start_ticks 9000100", txt)
        self.assertIn("show-session: Leader=448001", txt)
        self.assertEqual(st.master_item(rec), "master-session check: PASS, session 912")
        # a refusal appends nothing
        r2, _ = self.check(sessions={"912": show(host="192.0.2.9")})
        st.record_master(rd, r2)
        with open(os.path.join(rd, "state", "own-sessions.txt")) as f:
            self.assertEqual(f.read().count("master"), 1)
        self.assertTrue(st.master_item(rec).startswith("master-session check: no master session (REFUSED: "))
        self.assertIn("no master session (no record", st.master_item(os.path.join(rd, "nope.txt")))

    def test_proof_prints_item_only_when_given(self):
        start = {"listeners": [], "mem_available_kb": 10, "dm": [], "loop": [], "modules": [], "mounts": [],
                 "uprobe_events": [], "home": [], "watched": {"epl": []}}
        now = dict(start)
        kw = dict(procs=[], containers=0, logins=[], perf_data=0, sessions=[])
        base, _ = st.proof(start, now, self.d, **kw)
        self.assertFalse(any("master-session" in x for x in base))
        lines, res = st.proof(start, now, self.d, master="master-session check: PASS, session 912", **kw)
        self.assertIn("clean: master-session check: PASS, session 912", lines)
        self.assertEqual([x for x in lines if "master-session" not in x], base)
        self.assertEqual(res, "CLEAN")
        lines, res = st.proof(start, now, self.d, master="master-session check: no master session (x)", **kw)
        self.assertIn("clean: master-session check: no master session (x)  <-- NOT-CLEAN", lines)
        self.assertEqual(res, "NOT-CLEAN")

    def test_cli_no_master_session_refuses(self):
        rd = os.path.join(self.d, "runs")
        os.makedirs(os.path.join(rd, "state"))
        p = self.tree([(1, "systemd", 0, 0, 1), (5000, "bash", UID, 1, 70), (5001, "python3", UID, 5000, 80)])
        real = st.master_session
        st.master_session = lambda: real(proc=p, runner=Fake({"912": show()}), env=ENV, uid=UID, ssh_runner=ssh_v)
        try:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = st.main(["master", "--run-dir", rd])
        finally:
            st.master_session = real
        self.assertEqual(rc, 1)
        self.assertIn("master-session check: REFUSED: no uid-0 sshd ancestor", out.getvalue())
        self.assertFalse(os.path.exists(os.path.join(rd, "state", "own-sessions.txt")))
        self.assertIn("no master session", st.master_item(os.path.join(rd, "state", "master-session.txt")))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(st.main(["master", "--run-dir", os.path.join(self.d, "none")]), 2)


if __name__ == "__main__":
    unittest.main()
