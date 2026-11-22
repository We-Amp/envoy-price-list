"""Code-layout tools: lbr2order.py's perf-script parsing, ordering file and layout stats on a tiny
synthetic input, plus syntax and hygiene checks of the code-layout and top-down scripts."""
import contextlib
import glob
import importlib.util
import io
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools", "code-layout")
TOPDOWN = os.path.join(ROOT, "examples", "topdown")
ANALYSIS = os.path.join(ROOT, "examples", "wave2", "analysis")


def load_lbr2order():
    spec = importlib.util.spec_from_file_location("lbr2order", os.path.join(TOOLS, "lbr2order.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


L = load_lbr2order()

# One executable PT_LOAD: file offset 0x1000 -> vaddr 0x401000, 0x3000 bytes.
TEXT_OFF, TEXT_VA, TEXT_SZ = 0x1000, 0x401000, 0x3000


def write_elf(path):
    """A minimal ELF64 LE header with two program headers (one RW data, one RX text)."""
    phoff, phentsize, phnum = 64, 56, 2
    h = bytearray(64)
    h[:4] = b"\x7fELF"
    h[4], h[5], h[6] = 2, 1, 1
    struct.pack_into("<Q", h, 32, phoff)
    struct.pack_into("<HH", h, 54, phentsize, phnum)
    ph = struct.pack("<IIQQQQQQ", 1, 6, 0x4000, 0x404000, 0x404000, 0x100, 0x100, 0x1000)  # PF_R|PF_W
    ph += struct.pack("<IIQQQQQQ", 1, 5, TEXT_OFF, TEXT_VA, TEXT_VA, TEXT_SZ, TEXT_SZ, 0x1000)  # PF_R|PF_X
    with open(path, "wb") as f:
        f.write(bytes(h) + ph)


# nm: three functions, an alias at main's address (dropped), a data symbol and a zero-size symbol.
NM = """\
0000000000401000 0000000000000100 T main
0000000000401000 0000000000000100 T main_alias
0000000000401100 0000000000000080 t helper
0000000000403000 0000000000000040 W cold
0000000000404000 0000000000000010 D data
0000000000402000 0000000000000000 T empty
"""

# Runtime mapping: text at 0x7f0000001000 maps file offset 0x1000 (so runtime = vaddr + 0x7effffc00000).
DELTA = 0x7F0000001000 - TEXT_VA


def rt(va):
    return "0x%x" % (va + DELTA)


SCRIPT = "\n".join([
    "PERF_RECORD_MMAP2 1234/1234: [0x7f0000001000(0x3000) @ 0x1000 08:01 42 0]: r-xp /opt/x/envoy-test",
    "PERF_RECORD_MMAP2 1234/1234: [0x7f1000000000(0x1000) @ 0 08:01 43 0]: r-xp /lib/libc.so.6",
    # sample 1: main -> helper entry (a call), twice; helper -> main+0x10 (a return, not an edge)
    "  %s  %s/%s/P/-/-/1  %s/%s/P/-/-/1  %s/%s/P/-/-/1" % (
        rt(0x401000), rt(0x401010), rt(0x401100), rt(0x401020), rt(0x401100), rt(0x401110), rt(0x401010)),
    # sample 2: main -> cold entry (a call); a branch inside main; a branch into libc (skipped)
    "  %s  %s/%s/P/-/-/1  %s/%s/P/-/-/1  %s/0x7f1000000010/P/-/-/1" % (
        rt(0x401000), rt(0x401030), rt(0x403000), rt(0x401040), rt(0x401050), rt(0x401060)),
    "",
])


class Lbr2OrderTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.bin = os.path.join(self.d, "envoy-test")
        write_elf(self.bin)
        self.nm = os.path.join(self.d, "envoy-test.nm")
        with open(self.nm, "w") as f:
            f.write(NM)
        self.script = os.path.join(self.d, "s.script")
        with open(self.script, "w") as f:
            f.write(SCRIPT)

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_pt_loads(self):
        loads = L.pt_loads(self.bin)
        self.assertEqual(loads, [(0x4000, 0x404000, 0x100, 6), (TEXT_OFF, TEXT_VA, TEXT_SZ, 5)])

    def test_load_nm_keeps_first_text_symbol_per_address(self):
        addrs, sizes, names = L.load_nm(self.nm)
        self.assertEqual(names, ["main", "helper", "cold"])
        self.assertEqual(addrs, [0x401000, 0x401100, 0x403000])
        self.assertEqual(sizes, [0x100, 0x80, 0x40])
        self.assertEqual(L.lookup(addrs, sizes, 0x4010FF), 0)
        self.assertEqual(L.lookup(addrs, sizes, 0x401180), -1)  # past helper's end
        self.assertEqual(L.lookup(addrs, sizes, 0x400000), -1)

    def test_mmap_regex(self):
        m = L.MMAP_RE.search(SCRIPT.splitlines()[0])
        self.assertEqual(m.group(1), "0x7f0000001000")
        self.assertEqual(m.group(2), "0x3000")
        self.assertEqual(m.group(3), "0x1000")
        self.assertEqual(m.group(4), "r-xp")
        self.assertEqual(m.group(5).strip(), "/opt/x/envoy-test")

    def run_edges(self):
        out = os.path.join(self.d, "order")
        with contextlib.redirect_stdout(io.StringIO()) as so, contextlib.redirect_stderr(io.StringIO()):
            L.edges(self.bin, self.nm, out, [self.script])
        return out, json.loads(so.getvalue())

    def test_edges_order_file_and_stats(self):
        out, stats = self.run_edges()
        with open(os.path.join(out, "cg.txt")) as f:
            self.assertEqual(f.read(), "main helper 2\nmain cold 1\n")
        self.assertEqual(stats["samples"], 2)
        self.assertEqual(stats["branch_records"], 6)
        self.assertEqual(stats["in_binary"], 5)  # the libc branch is not counted
        self.assertEqual(stats["cg_edges"], 2)
        self.assertEqual(stats["cg_weight"], 3)
        self.assertEqual(stats["scripts"]["s.script"]["exec_maps"], 1)
        with open(os.path.join(out, "hot.json")) as f:
            hot = json.load(f)["hot"]
        # hits: main 5 (each in-binary record touches it), helper 3, cold 1
        self.assertEqual([(h["name"], h["w"]) for h in hot], [("main", 5), ("helper", 3), ("cold", 1)])
        c90 = stats["layout"]["c90"]
        # 90% of 9 needs main + helper + cold (8/9 < 0.9); all in pages 0x401 and 0x403
        self.assertEqual(c90["functions"], 3)
        self.assertEqual(c90["pages_4k"], 2)
        self.assertEqual(c90["pages_2m"], 1)
        self.assertEqual(stats["layout"]["c100"]["bytes"], 0x100 + 0x80 + 0x40)

    def test_span_in_relinked_binary(self):
        out, _ = self.run_edges()
        nm2 = os.path.join(self.d, "relinked.nm")
        with open(nm2, "w") as f:  # cold moved next to helper; main missing from the relinked binary
            f.write("0000000000401100 0000000000000080 t helper\n0000000000401180 0000000000000040 W cold\n")
        with contextlib.redirect_stdout(io.StringIO()):
            r = L.span(os.path.join(out, "hot.json"), nm2, "relinked")
        self.assertEqual(r["label"], "relinked")
        self.assertEqual(r["names_missing"], 1)
        self.assertEqual(r["c100"]["functions"], 2)
        self.assertEqual(r["c100"]["pages_4k"], 1)

    def test_edges_fails_when_under_half_map(self):
        sp = os.path.join(self.d, "mostly-libc.script")
        with open(sp, "w") as f:
            f.write(SCRIPT.splitlines()[0] + "\n")
            f.write("  %s  %s/%s/P/-/-/1  %s/0x7f1000000010/P/-/-/1  0x7f1000000020/%s/P/-/-/1\n" % (
                rt(0x401000), rt(0x401010), rt(0x401100), rt(0x401020), rt(0x401030)))
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as se:
            L.edges(self.bin, self.nm, os.path.join(self.d, "o2"), [sp])
        self.assertEqual(cm.exception.code, 3)
        self.assertIn("under half", se.getvalue())


def shell_scripts():
    return sorted(glob.glob(os.path.join(TOOLS, "*.sh")) + glob.glob(os.path.join(TOPDOWN, "*.sh")))


def all_files():
    out = []
    for d in (TOOLS, TOPDOWN, ANALYSIS):
        for p in sorted(glob.glob(os.path.join(d, "*"))):
            if os.path.isfile(p):
                out.append(p)
    return out


class ScriptHygieneTest(unittest.TestCase):
    def test_scripts_exist(self):
        names = {os.path.basename(p) for p in shell_scripts()}
        for n in ("build-arms.sh", "build-autofdo-order.sh", "autofdo-v2.sh", "bolt.sh", "common.sh",
                  "chain.sh", "perf-lbr.sh"):
            self.assertIn(n, names)

    @unittest.skipUnless(shutil.which("bash"), "bash not installed")
    def test_bash_syntax(self):
        for p in shell_scripts():
            r = subprocess.run(["bash", "-n", p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, "%s: %s" % (p, r.stderr))

    def test_no_fixed_pins_or_home_paths(self):
        # CPU pins are a parameter (PIN_CPUS), perf comes from PATH or PERF, paths from the work dir
        bad = re.compile(r"taskset -c [0-9]|/home/|/Users/|/linux-tools/6\.8\.0-151", re.I)
        hits = []
        for p in all_files():
            with open(p, errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if bad.search(line):
                        hits.append("%s:%d: %s" % (os.path.relpath(p, ROOT), i, line.strip()))
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
