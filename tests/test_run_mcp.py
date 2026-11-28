"""run-mcp.sh: one config argument, EPL_HOME, no housekeeping default, and the opt-in login-session gate
(EPL_SESSION_RECORD: verify, not append)."""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "loop", "run-mcp.sh")

# the stand-ins for the exec: python3 answers the housekeeping read from the config (as the real one-liner does);
# taskset marks the exec on stdout
PY = ('#!/bin/sh\nif [ "$1" = -I ] && [ "$2" = -c ]; then '
      'if grep -q housekeeping_cpus "$4"; then echo 18-19; else echo; fi; exit 0; fi\necho "PY $*"\n')
TASKSET = '#!/bin/sh\necho "EXEC taskset $*"\n'


class RunMcpTest(unittest.TestCase):
    SHELL = "sh"

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.home = os.path.join(self.d, "home")
        self.bin = os.path.join(self.d, "bin")
        self.eh = os.path.join(self.home, "epl")
        os.makedirs(os.path.join(self.eh, "loop"))
        os.makedirs(self.bin)
        for name, text in (("python3", PY), ("taskset", TASKSET)):
            p = os.path.join(self.bin, name)
            with open(p, "w") as f:
                f.write(text)
            os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
        for name in ("agentd", "agentd-idle"):
            self.config(os.path.join(self.eh, "loop", name + ".json"))
        self.record = os.path.join(self.d, "state", "own-sessions.txt")

    def config(self, path, hk=True):
        with open(path, "w") as f:
            f.write('{"housekeeping_cpus": "18-19"}\n' if hk else '{"workdir": "x"}\n')
        return path

    def own(self, text):
        os.makedirs(os.path.dirname(self.record), exist_ok=True)
        with open(self.record, "w") as f:
            f.write(text)

    def own_text(self):
        with open(self.record) as f:
            return f.read()

    def run_it(self, *args, sid="912", env_extra=None, gate=True):
        env = {"HOME": self.home, "PATH": self.bin + ":/usr/bin:/bin"}
        if sid is not None:
            env["XDG_SESSION_ID"] = sid
        if gate:
            env["EPL_SESSION_RECORD"] = self.record
        env.update(env_extra or {})
        return subprocess.run([self.SHELL, SCRIPT] + list(args), env=env, capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL)

    def refused(self, r, needle):
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertIn(needle, r.stderr)

    def exec_line(self, cfg, eh=None):
        eh = eh or self.eh
        return "EXEC taskset -c 18-19 python3 -I %s/loop/harness/loop/agentd.py --config %s --home %s\n" % (eh, cfg, eh)

    # ---------------------------------------------------------------- without the gate (the default)
    def test_no_gate_starts_and_logs_one_audit_line(self):
        r = self.run_it("agentd", gate=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, self.exec_line(os.path.join(self.eh, "loop", "agentd.json")))
        lines = r.stderr.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("session 912 loop-agentd", lines[0])
        self.assertIn("session not checked", lines[0])
        self.assertFalse(os.path.exists(self.record))

    def test_config_forms(self):
        r = self.run_it("agentd-idle.json", gate=False)
        self.assertEqual(r.stdout, self.exec_line(os.path.join(self.eh, "loop", "agentd-idle.json")))
        p = self.config(os.path.join(self.d, "elsewhere.json"))
        r = self.run_it(p, gate=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, self.exec_line(p))

    def test_epl_home(self):
        eh = os.path.join(self.d, "other-home")
        os.makedirs(os.path.join(eh, "loop"))
        self.config(os.path.join(eh, "loop", "agentd.json"))
        r = self.run_it("agentd", gate=False, env_extra={"EPL_HOME": eh})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, self.exec_line(os.path.join(eh, "loop", "agentd.json"), eh))

    def test_no_housekeeping_default(self):
        self.config(os.path.join(self.eh, "loop", "nohk.json"), hk=False)
        self.refused(self.run_it("nohk", gate=False), "names no housekeeping_cpus")

    def test_refused_argument(self):
        for args in ((), ("agentd", "agentd-idle")):
            self.refused(self.run_it(*args, gate=False), "one argument expected")
        for arg in ("", ".hidden", "a b", "x;y"):
            self.refused(self.run_it(arg, gate=False), "argument '%s' refused" % arg)
        self.refused(self.run_it("missing", gate=False), "no config")
        self.refused(self.run_it("../x", gate=False), "no config")

    # ---------------------------------------------------------------- with EPL_SESSION_RECORD (opt-in)
    def test_gate_success_audit_line_and_nothing_before_exec(self):
        self.own("912 login-pre 2026-01-01T08:00:00Z\n912 master 2026-01-01T08:00:01Z\n")
        r = self.run_it("agentd")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, self.exec_line(os.path.join(self.eh, "loop", "agentd.json")))
        last = self.own_text().splitlines()[-1].split()
        self.assertEqual(last[:2], ["912", "loop-agentd"])
        self.assertRegex(last[2], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        r = self.run_it("agentd-idle")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.own_text().splitlines()[-1].split()[1], "loop-agentd-idle")

    def test_master_line_alone_is_enough(self):
        self.own("912 master 2026-01-01T08:00:01Z\n")
        self.assertEqual(self.run_it("agentd").returncode, 0)

    def test_no_record_file(self):
        self.refused(self.run_it("agentd"), "no session record %s" % self.record)
        self.assertFalse(os.path.exists(self.record))

    def test_unrecorded_session(self):
        before = "913 login-pre 2026-01-01T08:00:00Z\n"
        self.own(before)
        self.refused(self.run_it("agentd"), "session 912 is not recorded as ours")
        self.assertEqual(self.own_text(), before)                      # nothing appended

    def test_only_master_or_login_lines_count(self):
        before = "912 loop-agentd 2026-01-01T08:00:00Z\n912 other 2026-01-01T08:00:00Z\nx 912 login-b\n"
        self.own(before)
        self.refused(self.run_it("agentd"), "not recorded as ours")
        self.assertEqual(self.own_text(), before)
        self.own("")                                                    # an empty record
        self.refused(self.run_it("agentd"), "not recorded as ours")

    def test_empty_or_unknown_id(self):
        self.own("4294967295 master x\n 912 master x\n")
        # an empty XDG_SESSION_ID falls back to /proc/self/sessionid; where that is absent (macOS) the id is empty
        r = self.run_it("agentd", sid="")
        self.refused(r, "no logind session id" if not os.path.exists("/proc/self/sessionid") else "not started")
        self.refused(self.run_it("agentd", sid="4294967295"), "no logind session id")
        self.assertNotIn("loop-", self.own_text())

    def test_gate_refusals_append_nothing(self):
        self.own("912 master x\n")
        for args in ((), ("agentd", "agentd-idle"), ("../x",), ("",)):
            self.assertEqual(self.run_it(*args).returncode, 2)
        self.assertNotIn("loop-", self.own_text())


@unittest.skipUnless(os.path.exists("/bin/dash"), "no dash (Debian's and Ubuntu's /bin/sh)")
class RunMcpDashTest(RunMcpTest):
    SHELL = "/bin/dash"


if __name__ == "__main__":
    unittest.main()
