#!/usr/bin/env python3
"""Fetch the data of the stats study into data/stats/ (git-ignored), verified against the
manifest in this repository.

    python3 tools/fetch-stats-data.py [--from URL_OR_DIR] [--dest DIR] [--keep DIR] [STUDY ...]
    python3 tools/fetch-stats-data.py --verify [--dest DIR] [STUDY ...]
    python3 tools/fetch-stats-data.py --list

Without STUDY every archive is fetched (about 320 MB unpacked). The archives are the assets of
the release of tag stats-2026-11:

    https://github.com/We-Amp/envoy-price-list/releases/download/stats-2026-11/   (PLANNED)

--from names another base URL, or a directory that already holds the archives. Each archive is
checked against data/stats-data.SHA256SUMS before anything is unpacked, and every unpacked file
against data/stats-data.manifest (sha256 and size). --verify checks an unpacked tree again, for
example after rendering the tables from it. --keep DIR keeps the downloaded archives.

An archive that the release does not have (HTTP 404, or no such file in the directory) is not an
error when no study was named: its study is skipped with a message and the others are fetched and
checked. Naming a study whose archive is absent is an error. Any other failure, and any checksum
that does not match, ends with a non-zero exit.

Python 3.8 or later, standard library only.
"""
import argparse
import gzip
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stats_data as sd  # noqa: E402


class Absent(Exception):
    """The source does not have this asset."""


def obtain(src, name, to):
    """Copy or download one asset to `to`; Absent when the source does not have it."""
    if os.path.isdir(src):
        if not os.path.isfile(os.path.join(src, name)):
            raise Absent(name)
        shutil.copyfile(os.path.join(src, name), to)
        return
    url = src.rstrip("/") + "/" + name
    req = urllib.request.Request(url, headers={"User-Agent": "fetch-stats-data"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(to, "wb") as f:
            shutil.copyfileobj(r, f)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise Absent(name)
        raise


def unpack(archive, dest, expected):
    """Extract regular files only, and only the paths the manifest lists for this archive."""
    with gzip.open(archive, "rb") as gz, tarfile.open(fileobj=gz, mode="r:") as tar:
        for ti in tar:
            name = ti.name
            if not ti.isfile() or name not in expected or name.startswith("/") or ".." in name.split("/"):
                raise ValueError("%s: unexpected member %r" % (os.path.basename(archive), name))
            out = os.path.join(dest, *name.split("/"))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with tar.extractfile(ti) as src, open(out, "wb") as f:
                shutil.copyfileobj(src, f)


def verify(dest, entries):
    """Problems of the unpacked files against the manifest entries [(sha256, size, study, path)]."""
    probs = []
    for h, size, _, rel in entries:
        p = os.path.join(dest, *rel.split("/"))
        if not os.path.isfile(p):
            probs.append("missing: %s" % rel)
        elif os.path.getsize(p) != size or sd.sha256_file(p) != h:
            probs.append("differs from the manifest: %s" % rel)
    return probs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("study", nargs="*")
    ap.add_argument("--from", dest="src", default=sd.BASE_URL)
    ap.add_argument("--dest", default=sd.DEST)
    ap.add_argument("--keep")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--manifest", default=sd.MANIFEST, help=argparse.SUPPRESS)
    ap.add_argument("--sums", default=sd.SUMS, help=argparse.SUPPRESS)
    a = ap.parse_args()
    manifest, sums = sd.read_manifest(a.manifest), sd.read_sums(a.sums)
    known = sorted({m[2] for m in manifest})
    if a.list:
        for s in known:
            mine = [m for m in manifest if m[2] == s]
            print("%-32s %5d files %7.1f MB unpacked  %s" % (s, len(mine), sum(m[1] for m in mine) / 1e6, sd.ASSET % s))
        return
    studies = a.study or known
    bad = [s for s in studies if s not in known]
    if bad:
        sys.exit("unknown study %s; known: %s" % (bad, ", ".join(known)))
    skipped = []
    if a.verify:
        if not a.study:  # an unpacked tree may hold some of the studies only
            skipped = [s for s in studies if not os.path.isdir(os.path.join(a.dest, s))]
    else:
        tmp = a.keep or tempfile.mkdtemp(prefix="stats-data-")
        os.makedirs(tmp, exist_ok=True)
        try:
            for s in studies:
                name = sd.ASSET % s
                path = os.path.join(tmp, name)
                print("fetching %s" % name, flush=True)
                try:
                    obtain(a.src, name, path)
                except Absent:
                    if a.study:
                        sys.exit("%s: not at %s" % (name, a.src))
                    print("%s: not at %s (withheld or not yet published); the study %s is skipped" % (name, a.src, s))
                    skipped.append(s)
                    continue
                except Exception as e:  # noqa: BLE001 (network, file system: say which asset and stop)
                    sys.exit("%s: cannot fetch from %s: %s" % (name, a.src, e))
                if name not in sums or sd.sha256_file(path) != sums[name]:
                    sys.exit("%s: sha256 is not the one in data/stats-data.SHA256SUMS; nothing unpacked from it" % name)
                unpack(path, a.dest, {m[3] for m in manifest if m[2] == s})
        finally:
            if not a.keep:
                shutil.rmtree(tmp, ignore_errors=True)
    studies = [s for s in studies if s not in skipped]
    if not studies:
        sys.exit("no study %s" % ("to verify under %s" % a.dest if a.verify else "could be fetched from %s" % a.src))
    entries = [m for m in manifest if m[2] in studies]
    probs = verify(a.dest, entries)
    for p in probs[:40]:
        print(p)
    print("%d files of %d studies checked against the manifest, %d problems%s" % (
        len(entries), len(studies), len(probs), "; skipped (absent): %s" % ", ".join(skipped) if skipped else ""))
    sys.exit(1 if probs else 0)


if __name__ == "__main__":
    main()
