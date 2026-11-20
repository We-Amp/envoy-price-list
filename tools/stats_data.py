"""The data of the stats study as release assets: shared pieces of build-stats-data.py and
fetch-stats-data.py.

The raw records of the stats study (about 320 MB) are not in git. They are published as one
gzip-compressed tar archive per study on the release of the tag below. Git keeps the manifest
(every file of every archive with its size and SHA-256), the checksums of the archives and the
small rendered tables (docs/stats-tables/).
"""
import gzip
import hashlib
import io
import os
import tarfile

TAG = "stats-2026-11"
# PLANNED: the release of this tag does not exist until the branch is published
BASE_URL = "https://github.com/We-Amp/envoy-price-list/releases/download/%s/" % TAG
ASSET = TAG + "-data-%s.tar.gz"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "data", "stats-data.manifest")
SUMS = os.path.join(REPO, "data", "stats-data.SHA256SUMS")
DEST = os.path.join(REPO, "data", "stats")
# files of the repository that go into every archive, at its top level
TOP_FILES = [("docs/stats-data/README.md", "README.md"),
             ("docs/stats-data/WHAT-WAS-CHANGED.md", "WHAT-WAS-CHANGED.md")]

# study directory -> [(sub directory, the machine label its host names carry)]; the build checks
# each sub tree with `epl scrub --check` under that label
STUDIES = {
    "sink-flush-cost": [("", "bench-x86_64")],
    "sink-types": [("", "bench-x86_64")],
    "flush-latency": [("", "bench-x86_64")],
    "multi-worker": [("", "bench-x86_64")],
    "multi-worker-high-load": [("", "bench-x86_64")],
    "contention": [("", "bench-x86_64")],
    "microbenchmarks": [("bench-x86_64", "bench-x86_64"), ("x86-vm", "x86-vm"), ("arm-vm", "arm-vm"),
                        ("arm-vm-b", "arm-vm"), ("reeval/x86-vm-r5", "x86-vm"), ("reeval/arm-vm-r5", "arm-vm"),
                        ("reeval/arm-vm-r5b", "arm-vm")],
    "microbenchmarks-flush-overlap": [("x86-vm", "x86-vm"), ("arm-vm", "arm-vm")],
    "arm-lse-llsc": [("", "arm-vm")],
    "arm-codegen": [("", "arm-vm")],
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_files(root):
    """Relative paths of the regular files under root, sorted; a symbolic link is an error."""
    out = []
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for fn in files:
            p = os.path.join(d, fn)
            if os.path.islink(p) or not os.path.isfile(p):
                raise ValueError("%s: not a regular file" % p)
            out.append(os.path.relpath(p, root).replace(os.sep, "/"))
    return sorted(out)


def write_archive(path, members):
    """A tar.gz of [(name in the archive, source file)], the same bytes for the same input:
    names sorted, no owner, mode 0644, time 0, no time or name in the gzip header."""
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for name, src in sorted(members):
                    with open(src, "rb") as f:
                        data = f.read()
                    ti = tarfile.TarInfo(name)
                    ti.size, ti.mode, ti.mtime = len(data), 0o644, 0
                    ti.uid = ti.gid = 0
                    ti.uname = ti.gname = ""
                    tar.addfile(ti, io.BytesIO(data))


def read_manifest(path=MANIFEST):
    """[(sha256, size, study, path)] from the manifest; lines starting with # are comments."""
    out = []
    with open(path) as f:
        for ln in f:
            if not ln.strip() or ln.startswith("#"):
                continue
            h, size, study, rel = ln.rstrip("\n").split("  ", 3)
            out.append((h, int(size), study, rel))
    return out


def read_sums(path=SUMS):
    """{asset file name: sha256}."""
    out = {}
    with open(path) as f:
        for ln in f:
            if ln.strip() and not ln.startswith("#"):
                h, name = ln.split()
                out[name] = h
    return out
