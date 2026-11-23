"""arm64 code-layout scripts (tools/code-layout/arm): bash syntax, and hygiene checks on every file there
(no fixed CPU pins, no home-directory paths, no IPv4 addresses other than loopback / any)."""
import glob
import os
import re
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARM = os.path.join(ROOT, "tools", "code-layout", "arm")

IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
ALLOWED_IPV4 = {"127.0.0.1", "0.0.0.0"}
BAD = re.compile(r"taskset -c [0-9]|/home/|/Users/")


def shell_scripts():
    return sorted(glob.glob(os.path.join(ARM, "*.sh")))


def all_files():
    return sorted(p for p in glob.glob(os.path.join(ARM, "*")) if os.path.isfile(p))


class ArmScriptsTest(unittest.TestCase):
    def test_scripts_exist(self):
        names = {os.path.basename(p) for p in shell_scripts()}
        for n in ("common.sh", "setup.sh", "build-arms.sh", "autofdo.sh", "bolt.sh"):
            self.assertIn(n, names)
        self.assertTrue(os.path.isfile(os.path.join(ARM, "README.md")))

    @unittest.skipUnless(shutil.which("bash"), "bash not installed")
    def test_bash_syntax(self):
        for p in shell_scripts():
            r = subprocess.run(["bash", "-n", p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, "%s: %s" % (p, r.stderr))

    def test_no_fixed_pins_or_home_paths(self):
        hits = []
        for p in all_files():
            with open(p, errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if BAD.search(line):
                        hits.append("%s:%d: %s" % (os.path.relpath(p, ROOT), i, line.strip()))
        self.assertEqual(hits, [])

    def test_no_ipv4_addresses(self):
        hits = []
        for p in all_files():
            with open(p, errors="replace") as f:
                for i, line in enumerate(f, 1):
                    for m in IPV4.finditer(line):
                        if m.group(1) not in ALLOWED_IPV4:
                            hits.append("%s:%d: %s" % (os.path.relpath(p, ROOT), i, m.group(1)))
        self.assertEqual(hits, [])

    def test_ipv4_pattern(self):
        addr = ".".join(["10", "1", "2", "3"])  # built here so this file holds no literal address
        found = [m.group(1) for m in IPV4.finditer("a %s b 127.0.0.1 v1.40.2 22.1.8 %s.5" % (addr, addr))]
        self.assertEqual(found, [addr, "127.0.0.1"])


if __name__ == "__main__":
    unittest.main()
