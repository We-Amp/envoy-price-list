"""The stats study's data as release assets: reproducible archives, the fetch with its checks,
and the manifest in the repository. None of these tests needs the archives themselves."""
import gzip
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import stats_data as sd  # noqa: E402

FETCH = os.path.join(HERE, "tools", "fetch-stats-data.py")
BUILD = os.path.join(HERE, "tools", "build-stats-data.py")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.tree = os.path.join(self.d, "tree")
        write(os.path.join(self.tree, "contention", "dose-2", "legs.jsonl"), '{"leg_id": "r01-a-b", "cycles": 5}\n')
        write(os.path.join(self.tree, "contention", "dose-2.md"), "| cell | rho |\n")
        write(os.path.join(self.tree, "top.md"), "about\n")
        self.assets = os.path.join(self.d, "assets")
        os.makedirs(self.assets)
        self.members = [("README.md", os.path.join(self.tree, "top.md"))] + [
            ("contention/" + r, os.path.join(self.tree, "contention", r))
            for r in sd.tree_files(os.path.join(self.tree, "contention"))]
        self.asset = os.path.join(self.assets, sd.ASSET % "contention")
        sd.write_archive(self.asset, self.members)
        self.manifest = os.path.join(self.d, "manifest")
        self.sums = os.path.join(self.d, "sums")
        self.write_lists()
        self.dest = os.path.join(self.d, "dest")

    def write_lists(self):
        with open(self.manifest, "w") as f:
            f.write("# comment\n")
            for arc, src in self.members:
                f.write("%s  %d  contention  %s\n" % (sd.sha256_file(src), os.path.getsize(src), arc))
        with open(self.sums, "w") as f:
            f.write("%s  %s\n" % (sd.sha256_file(self.asset), os.path.basename(self.asset)))

    def fetch(self, *args):
        return subprocess.run([sys.executable, FETCH, "--manifest", self.manifest, "--sums", self.sums,
                               "--dest", self.dest] + list(args), capture_output=True, text=True)


class ArchiveTest(Base):
    def test_same_input_same_bytes(self):
        other = os.path.join(self.d, "again.tar.gz")
        os.utime(self.members[1][1], (1, 1))  # file times do not reach the archive
        sd.write_archive(other, list(reversed(self.members)))
        with open(self.asset, "rb") as a, open(other, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_members_are_plain(self):
        with tarfile.open(self.asset) as tar:
            infos = tar.getmembers()
        self.assertEqual([t.name for t in infos], ["README.md", "contention/dose-2.md", "contention/dose-2/legs.jsonl"])
        for t in infos:
            self.assertEqual((t.mtime, t.uid, t.gid, t.mode, t.uname, t.isfile()), (0, 0, 0, 0o644, "", True))

    def test_a_link_in_the_tree_is_refused(self):
        os.symlink("/etc/hosts", os.path.join(self.tree, "contention", "link"))
        with self.assertRaises(ValueError):
            sd.tree_files(os.path.join(self.tree, "contention"))


class FetchTest(Base):
    def test_fetch_from_a_directory_and_verify(self):
        r = self.fetch("--from", self.assets, "contention")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3 files of 1 studies checked against the manifest, 0 problems", r.stdout)
        with open(os.path.join(self.dest, "contention", "dose-2", "legs.jsonl")) as f:
            self.assertIn("r01-a-b", f.read())
        self.assertEqual(self.fetch("--verify").returncode, 0)
        with open(os.path.join(self.dest, "contention", "dose-2.md"), "a") as f:
            f.write("changed\n")
        r = self.fetch("--verify")
        self.assertEqual(r.returncode, 1)
        self.assertIn("differs from the manifest: contention/dose-2.md", r.stdout)
        os.remove(os.path.join(self.dest, "README.md"))
        self.assertIn("missing: README.md", self.fetch("--verify").stdout)

    def test_a_changed_archive_is_not_unpacked(self):
        with open(self.asset, "ab") as f:
            f.write(b"x")
        r = self.fetch("--from", self.assets)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nothing unpacked", r.stderr)
        self.assertFalse(os.path.exists(self.dest))

    def test_a_member_outside_the_manifest_is_refused(self):
        evil = os.path.join(self.d, "evil.txt")
        write(evil, "x")
        for name in ("../escape.txt", "contention/not-listed.txt"):
            sd.write_archive(self.asset, self.members + [(name, evil)])
            with open(self.sums, "w") as f:
                f.write("%s  %s\n" % (sd.sha256_file(self.asset), os.path.basename(self.asset)))
            r = self.fetch("--from", self.assets)
            self.assertNotEqual(r.returncode, 0, name)
            self.assertIn("unexpected member", r.stderr, name)
        self.assertFalse(os.path.exists(os.path.join(self.d, "escape.txt")))

    def test_a_link_member_is_refused(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            ti = tarfile.TarInfo("README.md")
            ti.type, ti.linkname = tarfile.SYMTYPE, "/etc/hosts"
            tar.addfile(ti)
        with open(self.asset, "wb") as f:
            f.write(gzip.compress(buf.getvalue()))
        with open(self.sums, "w") as f:
            f.write("%s  %s\n" % (sd.sha256_file(self.asset), os.path.basename(self.asset)))
        r = self.fetch("--from", self.assets)
        self.assertIn("unexpected member", r.stderr)

    def test_missing_asset_and_unknown_study(self):
        os.remove(self.asset)
        r = self.fetch("--from", self.assets)   # the only archive is absent: nothing to fetch
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("is skipped", r.stdout)
        self.assertIn("no study could be fetched", r.stderr)
        r = self.fetch("--from", self.assets, "contention")   # named: an error
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not at", r.stderr)
        self.assertIn("unknown study", self.fetch("--from", self.assets, "nope").stderr)

    def add_second_study(self):
        """A second study in the manifest and the checksum list, its archive in self.assets."""
        src = os.path.join(self.tree, "arm-codegen", "codegen.md")
        write(src, "| rung | effect |\n")
        other = os.path.join(self.assets, sd.ASSET % "arm-codegen")
        sd.write_archive(other, [("arm-codegen/codegen.md", src)])
        with open(self.manifest, "a") as f:
            f.write("%s  %d  arm-codegen  arm-codegen/codegen.md\n" % (sd.sha256_file(src), os.path.getsize(src)))
        with open(self.sums, "a") as f:
            f.write("%s  %s\n" % (sd.sha256_file(other), os.path.basename(other)))
        return other

    def test_a_withheld_archive_does_not_fail_the_others(self):
        os.remove(self.add_second_study())
        r = self.fetch("--from", self.assets)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("the study arm-codegen is skipped", r.stdout)
        self.assertIn("3 files of 1 studies checked against the manifest, 0 problems; skipped (absent): arm-codegen", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.dest, "arm-codegen")))
        r = self.fetch("--verify")           # the unpacked tree without that study verifies
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("skipped (absent): arm-codegen", r.stdout)
        self.assertEqual(self.fetch("--verify", "arm-codegen").returncode, 1)   # asked for by name: missing files

    def test_a_corrupt_archive_among_several_fails(self):
        other = self.add_second_study()
        with open(other, "r+b") as f:
            f.seek(20)
            b = f.read(1)
            f.seek(20)
            f.write(bytes([b[0] ^ 1]))
        r = self.fetch("--from", self.assets)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nothing unpacked", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.dest, "arm-codegen")))

    def test_fetch_twice_is_the_same(self):
        self.assertEqual(self.fetch("--from", self.assets).returncode, 0)
        snap = {r: sd.sha256_file(os.path.join(self.dest, r)) for r in sd.tree_files(self.dest)}
        self.assertEqual(self.fetch("--from", self.assets).returncode, 0)
        self.assertEqual({r: sd.sha256_file(os.path.join(self.dest, r)) for r in sd.tree_files(self.dest)}, snap)

    def test_list(self):
        self.assertIn("contention", self.fetch("--list").stdout)


class BuildTest(Base):
    def build(self, *args):
        return subprocess.run([sys.executable, BUILD, self.tree, os.path.join(self.d, "out"), "--study", "contention"]
                              + list(args), capture_output=True, text=True)

    def test_a_scrubbed_tree_builds_and_nothing_in_the_repository_changes(self):
        before = {p: sd.sha256_file(p) for p in (sd.MANIFEST, sd.SUMS)}
        r = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = os.path.join(self.d, "out")
        self.assertEqual(sorted(os.listdir(out)), ["SHA256SUMS", sd.ASSET % "contention"])
        with tarfile.open(os.path.join(out, sd.ASSET % "contention")) as tar:
            names = tar.getnames()
        self.assertEqual(names[:2], ["README.md", "WHAT-WAS-CHANGED.md"])
        self.assertIn("contention/dose-2/legs.jsonl", names)
        self.assertEqual({p: sd.sha256_file(p) for p in (sd.MANIFEST, sd.SUMS)}, before)

    def test_an_unscrubbed_tree_is_refused(self):
        write(os.path.join(self.tree, "contention", "queue.console"), "cd /home/bob/epl\n")
        r = self.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not scrubbed", r.stderr)
        self.assertIn("contention/queue.console would change", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.d, "out", sd.ASSET % "contention")))

    def test_a_wrong_host_label_is_refused(self):
        write(os.path.join(self.tree, "contention", "bench.json"), '{"host_name": "some-box"}')
        self.assertIn("would change", self.build().stderr)


class RepositoryListsTest(unittest.TestCase):
    """What git keeps about the archives is consistent with itself."""

    def setUp(self):
        self.manifest = sd.read_manifest()
        self.sums = sd.read_sums()

    def test_one_asset_per_study(self):
        self.assertEqual(sorted(self.sums), sorted(sd.ASSET % s for s in sd.STUDIES))
        self.assertEqual({m[2] for m in self.manifest}, set(sd.STUDIES))
        for h in list(self.sums.values()) + [m[0] for m in self.manifest]:
            self.assertRegex(h, "^[0-9a-f]{64}$")

    def test_paths_are_inside_their_study_or_the_two_top_files(self):
        top = {dst for _, dst in sd.TOP_FILES}
        for _, _, study, rel in self.manifest:
            self.assertTrue(rel in top or rel.startswith(study + "/"), rel)
            self.assertNotIn("..", rel.split("/"))

    def test_top_files_are_the_ones_in_the_repository(self):
        for src, dst in sd.TOP_FILES:
            want = sd.sha256_file(os.path.join(HERE, src))
            got = {m[0] for m in self.manifest if m[3] == dst}
            self.assertEqual(got, {want}, "%s changed after the archives were built: build them again" % src)

    def test_tables_in_git_are_the_ones_in_the_archives(self):
        by = {m[3]: m[0] for m in self.manifest}
        root = os.path.join(HERE, "docs", "stats-tables")
        files = sd.tree_files(root)
        self.assertGreater(len(files), 20)
        for rel in files:
            self.assertEqual(sd.sha256_file(os.path.join(root, rel)), by.get(rel), rel)
            self.assertLessEqual(os.path.getsize(os.path.join(root, rel)), 200 * 1024, rel)

    def test_the_labels_file_is_the_study_table(self):
        want = sorted("%s=%s" % ((st + "/" + sub).rstrip("/"), lab) for st, subs in sd.STUDIES.items() for sub, lab in subs)
        with open(os.path.join(HERE, "tools", "stats-data.labels")) as f:
            got = sorted(ln.strip() for ln in f if ln.strip() and not ln.startswith("#"))
        self.assertEqual(got, want)

    def test_the_data_directory_is_ignored_by_git(self):
        with open(os.path.join(HERE, ".gitignore")) as f:
            self.assertIn("data/stats/", f.read().split())


if __name__ == "__main__":
    unittest.main()
