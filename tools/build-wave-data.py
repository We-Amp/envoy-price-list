#!/usr/bin/env python3
"""Build the release assets of the wave studies' data from a scrubbed tree.

    python3 tools/build-wave-data.py TREE OUT_DIR [--study NAME ...] [--no-write]
        [--names-file F] [--replace-file F]

TREE holds one directory per study (the layout of data/waves: statsd-batching/, ext-proc-xds/,
...), already scrubbed with `epl scrub --publish`. Per study the script

- refuses the tree when `epl scrub --check` would still change a file under the bench box's machine
  label (home paths, host names, cloud VM names; with --names-file and --replace-file also the
  private names and strings the scrub was given, which stay outside the tree), when a file is not
  text or gzip of text (except the gRPC bodies of wave_data.BINARY_OK), and when a file holds a
  private key or sits in a certs/ directory;
- writes OUT_DIR/<tag>-data-<study>.tar.gz (the tag of the study's release, wave_data.TAG_OF): the
  study's directory plus the release's README.md and WHAT-WAS-CHANGED.md (wave_data.TOP_FILES_OF). The archive is reproducible: the
  same tree gives the same bytes;
- and, unless --no-write, rewrites data/wave-data.manifest (every file of every archive: sha256,
  size, study, path), data/wave-data.SHA256SUMS (the archives), docs/wave-data/ASSETS.md (the
  archives with sizes and checksums, for readers) and docs/wave-tables/ (the rendered tables and
  analysis outputs under 200 KB, copied from the tree).

OUT_DIR/SHA256SUMS is written beside the archives. With --study only those archives are built and
nothing in the repository is rewritten.
"""
import argparse
import gzip
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import wave_data as wd  # noqa: E402
from epl import pubscrub  # noqa: E402

TABLE_MAX = 200 * 1024
TABLES_DIR = os.path.join(wd.REPO, "docs", "wave-tables")
# the PEM header of a private key, built so that this file does not carry it
KEY_MARK = ("-----BEGIN " + "PRIVATE KEY").encode(), (" PRIVATE KEY-----").encode()


def is_table(rel):
    """The rendered tables and analysis outputs that git keeps a copy of."""
    fn = rel.split("/")[-1]
    return fn.endswith(".md") and fn != "summary.md" and not fn.startswith("README")


def holds_key(path):
    with open(path, "rb") as f:
        data = f.read()
    if path.endswith(".gz"):
        try:
            data = gzip.decompress(data)
        except OSError:
            return False
    return any(m in data for m in KEY_MARK)


def check_tree(tree, study, names=(), replace=()):
    root = os.path.join(tree, study)
    if not os.path.isdir(root):
        return ["%s: missing" % root]
    rep = pubscrub.scrub_publish_tree(root, host_label=wd.HOST_LABEL_OF.get(study, wd.HOST_LABEL), names=names, replace=replace, check=True)
    probs = ["%s/%s would change: %s" % (study, p, c) for p, c in sorted(rep["changed"].items())]
    probs += ["%s/%s is not text" % (study, p) for p in rep["binary"]
              if not any(b in "/" + p.replace(os.sep, "/") for b in wd.BINARY_OK)]
    for rel in wd.tree_files(root):
        parts = rel.split("/")
        if "certs" in parts[:-1] or parts[-1].endswith((".key", ".pem", ".crt", ".p12")):
            probs.append("%s/%s: certificate or key file" % (study, rel))
        elif holds_key(os.path.join(root, rel)):
            probs.append("%s/%s: holds a private key" % (study, rel))
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tree")
    ap.add_argument("out")
    ap.add_argument("--study", action="append")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--names-file")
    ap.add_argument("--replace-file")
    a = ap.parse_args()
    names = pubscrub.parse_names(pubscrub.load_names_file(a.names_file)) if a.names_file else []
    replace = pubscrub.load_replace_file(a.replace_file) if a.replace_file else []
    studies = a.study or sorted(wd.STUDIES)
    bad = [s for s in studies if s not in wd.STUDIES]
    if bad:
        sys.exit("unknown study %s; known: %s" % (bad, ", ".join(sorted(wd.STUDIES))))
    partial = bool(a.study) or a.no_write
    os.makedirs(a.out, exist_ok=True)
    extra = sorted(d for d in os.listdir(a.tree) if os.path.isdir(os.path.join(a.tree, d)) and d not in wd.STUDIES)
    if extra and not a.study:
        sys.exit("directories in the tree that are no study: %s" % extra)
    manifest, sums, tables = [], [], []
    for study in studies:
        probs = check_tree(a.tree, study, names, replace)
        if probs:
            sys.exit("not publishable, nothing written for %s:\n  %s" % (study, "\n  ".join(probs[:20])))
        tops = wd.top_files(study)
        members = [(dst, os.path.join(wd.REPO, src)) for src, dst in tops]
        root = os.path.join(a.tree, study)
        clash = sorted({dst for _, dst in tops} & {study + "/" + rel for rel in wd.tree_files(root)})
        if clash:
            sys.exit("%s: the tree has files the archive takes from docs/: %s" % (study, clash))
        members += [(study + "/" + rel, os.path.join(root, rel)) for rel in wd.tree_files(root)]
        name = wd.asset(study)
        wd.write_archive(os.path.join(a.out, name), members)
        sums.append((wd.sha256_file(os.path.join(a.out, name)), name))
        for arc, src in sorted(members):
            size = os.path.getsize(src)
            manifest.append((wd.sha256_file(src), size, study, arc))
            if arc.startswith(study + "/") and is_table(arc) and size <= TABLE_MAX and \
                    arc not in {dst for _, dst in tops}:
                tables.append((arc, src))
        print("%s  %d files  %.1f MB" % (name, len(members), os.path.getsize(os.path.join(a.out, name)) / 1e6))
    with open(os.path.join(a.out, "SHA256SUMS"), "w") as f:
        f.write("".join("%s  %s\n" % s for s in sums))
    if partial:
        return
    with open(wd.SUMS, "w") as f:
        f.write("# sha256 of the release assets of tags %s (tools/build-wave-data.py)\n" % ", ".join(sorted(wd.TOP_FILES_OF)))
        f.write("".join("%s  %s\n" % s for s in sums))
    for path in wd.manifests():
        tags = sorted({wd.tag_of(st) for st in wd.STUDIES if wd.manifest_of(st) == path})
        with open(path, "w") as f:
            f.write("# every file of the release assets of tags %s: sha256, size in bytes, study (the asset\n"
                    "# <tag>-data-<study>.tar.gz), path inside the asset. Written by tools/build-wave-data.py.\n" % (
                        ", ".join(tags)))
            f.write("".join("%s  %d  %s  %s\n" % m for m in manifest if wd.manifest_of(m[2]) == path))
    if os.path.isdir(TABLES_DIR):
        shutil.rmtree(TABLES_DIR)
    for arc, src in tables:
        dst = os.path.join(TABLES_DIR, arc)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
    with open(os.path.join(wd.REPO, "docs", "wave-data", "ASSETS.md"), "w") as f:
        f.write("# Wave studies data: the release assets\n\n"
                "Assets of the releases of tags %s (`%s<asset>`), written by\n"
                "`tools/build-wave-data.py`. `python3 tools/fetch-wave-data.py` downloads, checks and unpacks them.\n\n"
                "| Asset | Release | Wave | Size | Files | Unpacked | sha256 |\n|---|---|---|---|---|---|---|\n" % (
                    ", ".join("`%s`" % t for t in sorted(wd.TOP_FILES_OF)), wd.RELEASE_URL % "<tag>"))
        for (h, name), study in zip(sums, studies):
            mine = [m for m in manifest if m[2] == study]
            f.write("| `%s` | `%s` | %s | %.1f MB | %d | %.1f MB | `%s` |\n" % (
                name, wd.tag_of(study), wd.STUDIES[study][0], os.path.getsize(os.path.join(a.out, name)) / 1e6,
                len(mine), sum(m[1] for m in mine) / 1e6, h))
        f.write("\nTogether: %.0f MB to download, %.0f MB unpacked, %d files (`README.md` and `WHAT-WAS-CHANGED.md`\n"
                "are in every archive: at the top in those of `waves-2026-11`, in the study's directory in the later ones). The same checksums are in `data/wave-data.SHA256SUMS`;\n"
                "every file of every archive is in a manifest in `data/` (`wave-data.manifest`, and one per study of the later releases)\n"
                "with its size and sha256.\n" % (
                    sum(os.path.getsize(os.path.join(a.out, n)) for _, n in sums) / 1e6, sum(m[1] for m in manifest) / 1e6,
                    len(manifest)))
    print("manifest: %d files, %.1f MB; tables kept in git: %d files, %.2f MB" % (
        len(manifest), sum(m[1] for m in manifest) / 1e6, len(tables), sum(os.path.getsize(s) for _, s in tables) / 1e6))


if __name__ == "__main__":
    main()
