#!/usr/bin/env python3
"""Fetch the data of the wave studies into data/waves/ (git-ignored), verified against the
manifest in this repository.

    python3 tools/fetch-wave-data.py [--from URL_OR_DIR] [--dest DIR] [--keep DIR] [STUDY ...]
    python3 tools/fetch-wave-data.py --verify [--dest DIR] [STUDY ...]
    python3 tools/fetch-wave-data.py --list

Without STUDY every archive is fetched (about 570 MB unpacked). The archives are the assets of
the release of tag waves-2026-11:

    https://github.com/We-Amp/envoy-price-list/releases/download/waves-2026-11/

--from names another base URL, or a directory that already holds the archives. Each archive is
checked against data/wave-data.SHA256SUMS before anything is unpacked, and every unpacked file
against data/wave-data.manifest (sha256 and size). --verify checks an unpacked tree again, for
example after rendering the tables from it. --keep DIR keeps the downloaded archives.

An archive that the release does not have (HTTP 404, or no such file in the directory) is not an
error when no study was named: its study is skipped with a message and the others are fetched and
checked. Naming a study whose archive is absent is an error. Any other failure, and any checksum
that does not match, ends with a non-zero exit.

The download, the unpacking (regular files listed in the manifest only) and the checks are those
of tools/fetch-stats-data.py. Python 3.8 or later, standard library only.
"""
import argparse
import importlib.util
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wave_data as wd  # noqa: E402

_spec = importlib.util.spec_from_file_location("fetch_stats_data", os.path.join(HERE, "fetch-stats-data.py"))
fsd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fsd)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("study", nargs="*")
    ap.add_argument("--from", dest="src", default=wd.BASE_URL)
    ap.add_argument("--dest", default=wd.DEST)
    ap.add_argument("--keep")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--manifest", default=wd.MANIFEST, help=argparse.SUPPRESS)
    ap.add_argument("--sums", default=wd.SUMS, help=argparse.SUPPRESS)
    a = ap.parse_args()
    manifest, sums = wd.read_manifest(a.manifest), wd.read_sums(a.sums)
    known = sorted({m[2] for m in manifest})
    if a.list:
        for s in known:
            mine = [m for m in manifest if m[2] == s]
            wave, what, _ = wd.STUDIES.get(s, ("?", "", ""))
            print("%-20s wave %s %5d files %7.1f MB unpacked  %s  (%s)" % (
                s, wave, len(mine), sum(m[1] for m in mine) / 1e6, wd.ASSET % s, what))
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
        tmp = a.keep or tempfile.mkdtemp(prefix="wave-data-")
        os.makedirs(tmp, exist_ok=True)
        try:
            for s in studies:
                name = wd.ASSET % s
                path = os.path.join(tmp, name)
                print("fetching %s" % name, flush=True)
                try:
                    fsd.obtain(a.src, name, path)
                except fsd.Absent:
                    if a.study:
                        sys.exit("%s: not at %s" % (name, a.src))
                    print("%s: not at %s (withheld or not yet published); the study %s is skipped" % (name, a.src, s))
                    skipped.append(s)
                    continue
                except Exception as e:  # noqa: BLE001 (network, file system: say which asset and stop)
                    sys.exit("%s: cannot fetch from %s: %s" % (name, a.src, e))
                if name not in sums or wd.sha256_file(path) != sums[name]:
                    sys.exit("%s: sha256 is not the one in data/wave-data.SHA256SUMS; nothing unpacked from it" % name)
                fsd.unpack(path, a.dest, {m[3] for m in manifest if m[2] == s})
        finally:
            if not a.keep:
                shutil.rmtree(tmp, ignore_errors=True)
    studies = [s for s in studies if s not in skipped]
    if not studies:
        sys.exit("no study %s" % ("to verify under %s" % a.dest if a.verify else "could be fetched from %s" % a.src))
    entries = [m for m in manifest if m[2] in studies]
    probs = fsd.verify(a.dest, entries)
    for p in probs[:40]:
        print(p)
    print("%d files of %d studies checked against the manifest, %d problems%s" % (
        len(entries), len(studies), len(probs), "; skipped (absent): %s" % ", ".join(skipped) if skipped else ""))
    sys.exit(1 if probs else 0)


if __name__ == "__main__":
    main()
