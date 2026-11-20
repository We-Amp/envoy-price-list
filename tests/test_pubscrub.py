"""The scrub for a tree that is published: what `epl scrub` alone does not reach."""
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from epl import pubscrub, sysprobe

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPL = os.path.join(HERE, "bin", "epl")
VM = "bench-vm-1.zone-9-a.c.some-project.internal"
BENCH = {"context": {"date": "2026-11-18T19:00:00+00:00", "host_name": "boxname",
                     "executable": "/home/bob/epl/bins/stats/atomic_model_benchmark-fix-0123456789",
                     "num_cpus": 28},
         "benchmarks": [{"name": "bmCurrent/threads:4", "real_time": 12.5, "cpu_time": 49.9}]}


def write(path, text, gz=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if gz:
        with gzip.open(path, "wt") as f:
            f.write(text)
    else:
        with open(path, "w") as f:
            f.write(text)


def read(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rt") as f:
            return f.read()
    with open(path) as f:
        return f.read()


def raw(path):
    with open(path, "rb") as f:
        return f.read()


class TextRulesTest(unittest.TestCase):
    def test_host_name_field(self):
        t, n = pubscrub.scrub_publish_text(json.dumps(BENCH, indent=2), host_label="bench-x86_64")
        d = json.loads(t)
        self.assertEqual(d["context"]["host_name"], "bench-x86_64")
        self.assertEqual(n["host_name"], 1)
        # every other field is byte for byte what it was
        self.assertEqual(d["benchmarks"], BENCH["benchmarks"])
        self.assertEqual(d["context"]["num_cpus"], 28)

    def test_host_name_field_compact_and_escaped(self):
        t, n = pubscrub.scrub_publish_text('{"host_name":"a\\"b","x":1}', host_label="h")
        self.assertEqual(json.loads(t), {"host_name": "h", "x": 1})
        self.assertEqual(n, {"host_name": 1})

    def test_executable_field(self):
        t, n = pubscrub.scrub_publish_text(json.dumps(BENCH))
        self.assertEqual(json.loads(t)["context"]["executable"],
                         "~/epl/bins/stats/atomic_model_benchmark-fix-0123456789")
        self.assertEqual(n["executable"], 1)
        self.assertNotIn("home", n)  # counted as executable, once

    def test_cloud_vm_name_with_zone_and_project(self):
        t, n = pubscrub.scrub_publish_text('{"host_name": "%s"}\nssh %s uptime\n' % (VM, VM), host_label="arm-vm")
        self.assertNotIn("some-project", t)
        self.assertNotIn("zone-9-a", t)
        self.assertEqual(t, '{"host_name": "arm-vm"}\nssh arm-vm uptime\n')
        self.assertEqual((n["host_name"], n["cloud_vm"]), (1, 1))

    def test_cloud_vm_rule_leaves_stat_names_alone(self):
        for s in ("cluster.a.b.c.internal.upstream_rq_200: 4", "http.x.rq.c.d.internal_redirect: 1",
                  "listener.internal: 2"):
            self.assertEqual(pubscrub.scrub_publish_text(s)[0], s)

    def test_home_paths_in_console_text(self):
        t, n = pubscrub.scrub_publish_text("bob@box:~$ ls /home/bob/epl/runs /Users/al/x /root/y\n")
        self.assertEqual(t, "bob@box:~$ ls ~/epl/runs ~/x ~/y\n")
        self.assertEqual(n, {"home": 3})

    def test_names_are_whole_tokens(self):
        names = pubscrub.parse_names(["box=bench", "bob=user"])
        t, n = pubscrub.scrub_publish_text("bob@box:~$ sandbox boxes box-2 a_box box. (box) bobby\n", names=names)
        self.assertEqual(t, "user@bench:~$ sandbox boxes box-2 a_box bench. (bench) bobby\n")
        self.assertEqual(n, {"name": 4})
        for bad in ("box", "=x", ""):
            with self.assertRaises(ValueError):
                pubscrub.parse_names([bad])

    def test_exact_replacements(self):
        t, n = pubscrub.scrub_publish_text('{"note": "see NOTE-7: rule"}', replace=[("see NOTE-7: rule", "rule")])
        self.assertEqual((t, n), ('{"note": "rule"}', {"replace": 1}))

    def test_clean_text_is_untouched(self):
        s = json.dumps({"context": {"host_name": "host", "executable": "~/b/x"}, "v": [1.5, "~/epl/runs"]})
        self.assertEqual(pubscrub.scrub_publish_text(s), (s, {}))

    def test_measured_values_do_not_change(self):
        t, _ = pubscrub.scrub_publish_text(json.dumps(BENCH), host_label="h")
        a, b = json.loads(t), json.loads(json.dumps(BENCH))
        for d in (a, b):
            d["context"].pop("host_name")
            d["context"].pop("executable")
        self.assertEqual(a, b)


class TreeTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        j = json.dumps(BENCH, indent=1)
        write(os.path.join(self.d, "micro", "r01-0-atomic_model.json"), j)
        write(os.path.join(self.d, "micro", "r01-0-atomic_model.json.gz"), j, gz=True)
        write(os.path.join(self.d, "queue.console"), "+ cd /home/bob/epl/harness\nok on %s\n" % VM)
        write(os.path.join(self.d, "codegen.out"), "wrote /home/bob/epl/runs/x/codegen.md\n")
        write(os.path.join(self.d, "no-suffix"), "HOME=/Users/al\n")
        write(os.path.join(self.d, "probe", "r02.jsonl.gz"), '{"argv": ["/home/bob/epl/harness/epl/latprobe.py"]}\n'
                                                           '{"t": 1.25}\n', gz=True)
        write(os.path.join(self.d, "clean", "legs.jsonl"), '{"leg_id": "r01-s-a", "cycles": 123}\n')
        write(os.path.join(self.d, "clean", "main.json.gz"), '{"samples": [1, 2, 3]}', gz=True)
        with open(os.path.join(self.d, "perf.data"), "wb") as f:
            f.write(b"PERFILE2\0\0\xff\xfe/home/bob")
        with open(os.path.join(self.d, "broken.gz"), "wb") as f:
            f.write(b"not gzip /home/bob")

    def all_text(self):
        out = []
        for d, _, fs in os.walk(self.d):
            for fn in fs:
                p = os.path.join(d, fn)
                if fn not in ("perf.data", "broken.gz"):
                    out.append(read(p))
        return "\n".join(out)

    def test_what_epl_scrub_alone_misses(self):
        # the starting point: the suffix-based scrub leaves all of these behind
        sysprobe.scrub_tree(self.d)
        left = self.all_text()
        self.assertIn('"host_name": "boxname"', left)
        self.assertIn("some-project", left)
        self.assertIn("/home/bob/epl/harness", left)       # .console and the .gz member
        self.assertIn("/home/bob/epl/runs/x/codegen.md", left)  # .out
        self.assertIn("/home/bob/epl/bins/stats/", read(os.path.join(self.d, "micro", "r01-0-atomic_model.json.gz")))

    def test_publish_scrub_covers_them(self):
        rep = pubscrub.scrub_publish_tree(self.d, host_label="bench")
        left = self.all_text()
        for s in ("/home/", "/Users/", "boxname", "some-project", "zone-9-a", VM):
            self.assertNotIn(s, left, s)
        self.assertEqual(sorted(rep["changed"]), ["codegen.out", "micro/r01-0-atomic_model.json",
                                                  "micro/r01-0-atomic_model.json.gz", "no-suffix",
                                                  "probe/r02.jsonl.gz", "queue.console"])
        self.assertEqual(rep["changed"]["micro/r01-0-atomic_model.json.gz"], {"executable": 1, "host_name": 1})
        self.assertEqual(rep["changed"]["queue.console"], {"cloud_vm": 1, "home": 1})
        self.assertEqual(sorted(rep["binary"]), ["broken.gz", "perf.data"])
        self.assertEqual(rep["files"], 10)
        # gzip members are still gzip, with the other lines intact
        self.assertEqual(read(os.path.join(self.d, "probe", "r02.jsonl.gz")),
                         '{"argv": ["~/epl/harness/epl/latprobe.py"]}\n{"t": 1.25}\n')
        self.assertEqual(json.loads(read(os.path.join(self.d, "micro", "r01-0-atomic_model.json.gz")))["benchmarks"],
                         BENCH["benchmarks"])

    def test_untouched_files_keep_their_bytes_and_a_second_pass_is_a_no_op(self):
        keep = [os.path.join(self.d, "clean", "main.json.gz"), os.path.join(self.d, "clean", "legs.jsonl"),
                os.path.join(self.d, "perf.data"), os.path.join(self.d, "broken.gz")]
        before = {p: raw(p) for p in keep}
        pubscrub.scrub_publish_tree(self.d)
        self.assertEqual({p: raw(p) for p in keep}, before)
        snap = {}
        for d, _, fs in os.walk(self.d):
            for fn in fs:
                snap[os.path.join(d, fn)] = raw(os.path.join(d, fn))
        rep = pubscrub.scrub_publish_tree(self.d)
        self.assertEqual(rep["changed"], {})
        for p, b in snap.items():
            self.assertEqual(raw(p), b, p)

    def test_check_writes_nothing(self):
        snap = {}
        for d, _, fs in os.walk(self.d):
            for fn in fs:
                snap[os.path.join(d, fn)] = raw(os.path.join(d, fn))
        rep = pubscrub.scrub_publish_tree(self.d, check=True)
        self.assertEqual(len(rep["changed"]), 6)
        for p, b in snap.items():
            self.assertEqual(raw(p), b, p)

    def test_gzip_output_is_deterministic(self):
        self.assertEqual(pubscrub.gzip_bytes(b"abc" * 100), pubscrub.gzip_bytes(b"abc" * 100))
        self.assertEqual(gzip.decompress(pubscrub.gzip_bytes(b"abc")), b"abc")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, EPL, "scrub", self.d] + list(args), capture_output=True, text=True)

    def test_cli(self):
        r = self.run_cli("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("6 would change", r.stdout)
        names = os.path.join(tempfile.mkdtemp(), "names.txt")
        self.addCleanup(shutil.rmtree, os.path.dirname(names))
        with open(names, "w") as f:
            f.write("# private\nbob=user\n")
        r = self.run_cli("--publish", "--host-label", "bench", "--names-file", names, "--name", "al=user2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("queue.console cloud_vm=1 home=1", r.stdout)
        self.assertIn("not text, untouched: perf.data", r.stdout)
        r = self.run_cli("--check", "--host-label", "bench", "--names-file", names)
        self.assertEqual((r.returncode, r.stdout.strip().splitlines()[-1]), (0, "10 files, 0 would change, 2 not text"))
        r = self.run_cli("--publish", "--name", "broken")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("OLD=NEW", r.stderr)

    def test_plain_scrub_is_unchanged(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(sorted(r.stdout.split()), ["micro/r01-0-atomic_model.json"])
        self.assertIn("/home/bob", read(os.path.join(self.d, "queue.console")))

    def test_a_label_per_directory(self):
        # three machines in one tree: one label per sub tree, the longest directory wins
        for sub, host in (("a/micro", "box-a"), ("b", "box-b"), ("b/deep/er", "box-c"), ("top", "box-d")):
            write(os.path.join(self.d, "multi", sub, "r01.json"), json.dumps({"context": {"host_name": host}}))
        root = os.path.join(self.d, "multi")
        default, by_dir = pubscrub.parse_labels(["a=bench", "b=vm", "b/deep=vm-2", "other"])
        self.assertEqual((default, by_dir), ("other", {"a": "bench", "b": "vm", "b/deep": "vm-2"}))
        pubscrub.scrub_publish_tree(root, default, labels=by_dir)
        got = {sub: json.loads(read(os.path.join(root, sub, "r01.json")))["context"]["host_name"]
               for sub in ("a/micro", "b", "b/deep/er", "top")}
        self.assertEqual(got, {"a/micro": "bench", "b": "vm", "b/deep/er": "vm-2", "top": "other"})
        # the gate on the whole tree: clean with the labels, 3 false alarms with one label
        self.assertEqual(pubscrub.scrub_publish_tree(root, default, labels=by_dir, check=True)["changed"], {})
        self.assertEqual(len(pubscrub.scrub_publish_tree(root, "bench", check=True)["changed"]), 3)
        for bad in ("=x", "a=", "/=x"):
            with self.assertRaises(ValueError):
                pubscrub.parse_labels([bad])

    def test_cli_labels_file(self):
        root = os.path.join(self.d, "multi")
        write(os.path.join(root, "a", "r.json"), '{"host_name": "bench"}')
        write(os.path.join(root, "b", "r.json"), '{"host_name": "vm"}')
        lf = os.path.join(self.d, "labels.txt")
        write(lf, "# labels\na=bench\nb=vm\n")
        run = lambda *a: subprocess.run([sys.executable, EPL, "scrub", root, "--check"] + list(a),  # noqa: E731
                                        capture_output=True, text=True)
        self.assertEqual(run("--labels-file", lf).returncode, 0)
        self.assertEqual(run("--host-label", "a=bench", "--host-label", "b=vm").returncode, 0)
        r = run("--host-label", "bench")
        self.assertEqual(r.returncode, 1)
        self.assertIn("b/r.json host_name=1", r.stdout)
        self.assertIn("DIR=LABEL", run("--host-label", "a=").stderr)

    def test_replace_file_must_be_pairs(self):
        p = os.path.join(self.d, "r.json")
        for bad in ('{"a": "b"}', '[["a"]]', '[["", "b"]]', '[["a", 1]]'):
            with open(p, "w") as f:
                f.write(bad)
            with self.assertRaises(ValueError):
                pubscrub.load_replace_file(p)
        with open(p, "w") as f:
            f.write('[["a", "b"]]')
        self.assertEqual(pubscrub.load_replace_file(p), [("a", "b")])


if __name__ == "__main__":
    unittest.main()
