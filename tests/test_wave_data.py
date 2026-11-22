"""The wave studies' data as release assets: the fetch with its checks, the build's refusals, and the
manifest in the repository. None of these tests needs the archives themselves."""
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import wave_data as wd  # noqa: E402

FETCH = os.path.join(HERE, "tools", "fetch-wave-data.py")
BUILD = os.path.join(HERE, "tools", "build-wave-data.py")


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as f:
        f.write(text)


class Base(unittest.TestCase):
    STUDY = "connection-churn"

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.tree = os.path.join(self.d, "tree")
        root = os.path.join(self.tree, self.STUDY)
        write(os.path.join(root, "e-plain", "legs.jsonl"), '{"leg_id": "r01-s-ka", "cycles": 5}\n')
        write(os.path.join(root, "tables.md"), "| Row | n |\n")
        self.assets = os.path.join(self.d, "assets")
        os.makedirs(self.assets)
        self.members = [("README.md", os.path.join(HERE, "docs", "wave-data", "README.md"))] + [
            (self.STUDY + "/" + r, os.path.join(root, r)) for r in wd.tree_files(root)]
        self.asset = os.path.join(self.assets, wd.ASSET % self.STUDY)
        wd.write_archive(self.asset, self.members)
        self.manifest = os.path.join(self.d, "manifest")
        self.sums = os.path.join(self.d, "sums")
        with open(self.manifest, "w") as f:
            f.write("# comment\n")
            for arc, src in self.members:
                f.write("%s  %d  %s  %s\n" % (wd.sha256_file(src), os.path.getsize(src), self.STUDY, arc))
        with open(self.sums, "w") as f:
            f.write("%s  %s\n" % (wd.sha256_file(self.asset), os.path.basename(self.asset)))
        self.dest = os.path.join(self.d, "dest")

    def fetch(self, *args):
        return subprocess.run([sys.executable, FETCH, "--manifest", self.manifest, "--sums", self.sums,
                               "--dest", self.dest] + list(args), capture_output=True, text=True)

    def build(self, *args):
        return subprocess.run([sys.executable, BUILD, self.tree, os.path.join(self.d, "out"), "--study", self.STUDY]
                              + list(args), capture_output=True, text=True)


class FetchTest(Base):
    def test_fetch_from_a_directory_and_verify(self):
        r = self.fetch("--from", self.assets)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3 files of 1 studies checked against the manifest, 0 problems", r.stdout)
        self.assertEqual(self.fetch("--verify").returncode, 0)
        write(os.path.join(self.dest, self.STUDY, "tables.md"), "changed\n", "a")
        r = self.fetch("--verify")
        self.assertEqual(r.returncode, 1)
        self.assertIn("differs from the manifest: connection-churn/tables.md", r.stdout)

    def test_a_changed_archive_is_not_unpacked(self):
        with open(self.asset, "ab") as f:
            f.write(b"x")
        r = self.fetch("--from", self.assets)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("data/wave-data.SHA256SUMS; nothing unpacked", r.stderr)
        self.assertFalse(os.path.exists(self.dest))

    def test_a_member_outside_the_manifest_is_refused(self):
        evil = os.path.join(self.d, "evil.txt")
        write(evil, "x")
        wd.write_archive(self.asset, self.members + [("../escape.txt", evil)])
        with open(self.sums, "w") as f:
            f.write("%s  %s\n" % (wd.sha256_file(self.asset), os.path.basename(self.asset)))
        r = self.fetch("--from", self.assets)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unexpected member", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.d, "escape.txt")))

    def test_absent_asset_and_unknown_study(self):
        os.remove(self.asset)
        r = self.fetch("--from", self.assets)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("is skipped", r.stdout)
        r = self.fetch("--from", self.assets, self.STUDY)
        self.assertIn("not at", r.stderr)
        self.assertIn("unknown study", self.fetch("--from", self.assets, "nope").stderr)

    def test_list_names_the_wave(self):
        out = self.fetch("--list").stdout
        self.assertIn("connection-churn     wave 3", out)
        self.assertIn(wd.ASSET % self.STUDY, out)


class BuildTest(Base):
    def test_a_clean_tree_builds_and_nothing_in_the_repository_changes(self):
        before = {p: wd.sha256_file(p) for p in (wd.MANIFEST, wd.SUMS)}
        r = self.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = os.path.join(self.d, "out")
        self.assertEqual(sorted(os.listdir(out)), ["SHA256SUMS", wd.ASSET % self.STUDY])
        with tarfile.open(os.path.join(out, wd.ASSET % self.STUDY)) as tar:
            names = tar.getnames()
        self.assertEqual(names[:2], ["README.md", "WHAT-WAS-CHANGED.md"])
        self.assertIn("connection-churn/e-plain/legs.jsonl", names)
        self.assertEqual({p: wd.sha256_file(p) for p in (wd.MANIFEST, wd.SUMS)}, before)

    def test_a_home_path_is_refused(self):
        write(os.path.join(self.tree, self.STUDY, "queue.log"), "cd /home/bob/epl\n")
        r = self.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("connection-churn/queue.log would change", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.d, "out", wd.ASSET % self.STUDY)))

    def test_keys_and_certificates_are_refused(self):
        head = "-----BEGIN " + "PRIVATE KEY-----\nMII\n"
        for rel, text in (("e-tls/certs/ecdsa-p256.crt", "x\n"), ("e-tls/server.key", "x\n"),
                          ("e-tls/log.txt", "loaded\n" + head)):
            d = os.path.join(self.tree, self.STUDY)
            write(os.path.join(d, rel), text)
            r = self.build()
            self.assertNotEqual(r.returncode, 0, rel)
            self.assertTrue("certificate or key file" in r.stderr or "holds a private key" in r.stderr, r.stderr)
            shutil.rmtree(os.path.join(d, "e-tls"))
        self.assertEqual(self.build().returncode, 0)

    def test_a_private_name_is_refused_when_given(self):
        write(os.path.join(self.tree, self.STUDY, "ls.txt"), "-rw------- 1 bob bob 10 lbr-1.data\n")
        names = os.path.join(self.d, "names.txt")
        write(names, "bob=user\n")
        self.assertEqual(self.build().returncode, 0)          # the name is private: only the file knows it
        r = self.build("--names-file", names)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ls.txt would change", r.stderr)

    def test_binary_files_only_where_allowed(self):
        d = os.path.join(self.tree, self.STUDY)
        write(os.path.join(d, "f2-grpc", "origin", "www", "_grpc", "g.grpc"), b"\x00\x00\x00\x00\x05abcde", "wb")
        self.assertEqual(self.build().returncode, 0)
        write(os.path.join(d, "blob.bin"), b"\x00\x01\x02", "wb")
        r = self.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("blob.bin is not text", r.stderr)


class RepositoryListsTest(unittest.TestCase):
    """What git keeps about the archives is consistent with itself and with the docs."""

    def setUp(self):
        self.manifest = wd.read_manifest()
        self.sums = wd.read_sums()

    def test_one_asset_per_study(self):
        self.assertEqual(sorted(self.sums), sorted(wd.ASSET % s for s in wd.STUDIES))
        self.assertEqual({m[2] for m in self.manifest}, set(wd.STUDIES))
        for h in list(self.sums.values()) + [m[0] for m in self.manifest]:
            self.assertRegex(h, "^[0-9a-f]{64}$")

    def test_paths_are_inside_their_study_or_the_two_top_files(self):
        top = {dst for _, dst in wd.TOP_FILES}
        for _, _, study, rel in self.manifest:
            self.assertTrue(rel in top or rel.startswith(study + "/"), rel)
            self.assertNotIn("..", rel.split("/"))

    def test_no_key_or_certificate_in_the_archives(self):
        for _, _, _, rel in self.manifest:
            parts = rel.split("/")
            self.assertNotIn("certs", parts[:-1], rel)
            self.assertFalse(parts[-1].endswith((".key", ".pem", ".crt", ".p12", ".data")), rel)

    def test_top_files_are_the_ones_in_the_repository(self):
        for src, dst in wd.TOP_FILES:
            want = wd.sha256_file(os.path.join(HERE, src))
            got = {m[0] for m in self.manifest if m[3] == dst}
            self.assertEqual(got, {want}, "%s changed after the archives were built: build them again" % src)

    def test_tables_in_git_are_the_ones_in_the_archives(self):
        by = {m[3]: m[0] for m in self.manifest}
        root = os.path.join(HERE, "docs", "wave-tables")
        files = wd.tree_files(root)
        self.assertGreaterEqual(len(files), 12)
        for rel in files:
            self.assertEqual(wd.sha256_file(os.path.join(root, rel)), by.get(rel), rel)

    def test_every_study_has_its_example_directory_and_a_docs_section(self):
        with open(os.path.join(HERE, "docs", "wave-studies.md")) as f:
            doc = f.read()
        for study, (_, _, ex) in wd.STUDIES.items():
            self.assertTrue(os.path.isfile(os.path.join(HERE, ex, "README.md")), ex)
            self.assertIn("(`%s`)" % study, doc)

    def test_the_data_directory_is_ignored_by_git(self):
        with open(os.path.join(HERE, ".gitignore")) as f:
            self.assertIn("data/waves/", f.read().split())


if __name__ == "__main__":
    unittest.main()
