#!/usr/bin/env python3
"""Build the release assets of the stats study's data from a scrubbed tree.

    python3 tools/build-stats-data.py TREE OUT_DIR [--study NAME ...] [--no-write]

TREE holds one directory per study (the layout of data/stats: sink-flush-cost/, sink-types/, ...),
already scrubbed with `epl scrub --publish`. Per study the script

- refuses the tree when `epl scrub --check` would still change a file under the study's machine
  label (home paths, host names, cloud VM names), or when a file is not text or gzip of text;
- writes OUT_DIR/stats-2026-11-data-<study>.tar.gz: the study's directory plus README.md and
  WHAT-WAS-CHANGED.md from docs/stats-data/ at the top level. The archive is reproducible: the
  same tree gives the same bytes;
- and, unless --no-write, rewrites data/stats-data.manifest (every file of every archive: sha256,
  size, study, path), data/stats-data.SHA256SUMS (the archives) and docs/stats-tables/ (the
  rendered tables and analysis outputs under 200 KB, copied from the tree).

OUT_DIR/SHA256SUMS is written beside the archives. With --study only those archives are built and
nothing in the repository is rewritten.
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import stats_data as sd  # noqa: E402
from epl import pubscrub  # noqa: E402

TABLE_MAX = 200 * 1024
TABLES_DIR = os.path.join(sd.REPO, "docs", "stats-tables")


def is_table(rel):
    """The rendered tables and analysis outputs that git keeps a copy of."""
    parts = rel.split("/")
    fn = parts[-1]
    if "analysis" in parts[:-1] and fn.endswith(".txt"):
        return True
    return fn.endswith(".md") and fn != "summary.md" and not fn.startswith("README")


def check_scrubbed(tree, study):
    probs = []
    for sub, label in sd.STUDIES[study]:
        root = os.path.join(tree, study, sub) if sub else os.path.join(tree, study)
        if not os.path.isdir(root):
            probs.append("%s: missing" % root)
            continue
        rep = pubscrub.scrub_publish_tree(root, host_label=label, check=True)
        probs += ["%s/%s would change: %s" % (study, os.path.join(sub, p), c) for p, c in sorted(rep["changed"].items())]
        probs += ["%s/%s is not text" % (study, os.path.join(sub, p)) for p in rep["binary"]]
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tree")
    ap.add_argument("out")
    ap.add_argument("--study", action="append")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    studies = a.study or sorted(sd.STUDIES)
    partial = bool(a.study) or a.no_write
    os.makedirs(a.out, exist_ok=True)
    extra = sorted(d for d in os.listdir(a.tree) if os.path.isdir(os.path.join(a.tree, d)) and d not in sd.STUDIES)
    if extra and not a.study:
        sys.exit("directories in the tree that are no study: %s" % extra)
    manifest, sums, tables = [], [], []
    for study in studies:
        probs = check_scrubbed(a.tree, study)
        if probs:
            sys.exit("not scrubbed, nothing written for %s:\n  %s" % (study, "\n  ".join(probs[:20])))
        members = [(dst, os.path.join(sd.REPO, src)) for src, dst in sd.TOP_FILES]
        root = os.path.join(a.tree, study)
        members += [(study + "/" + rel, os.path.join(root, rel)) for rel in sd.tree_files(root)]
        name = sd.ASSET % study
        sd.write_archive(os.path.join(a.out, name), members)
        sums.append((sd.sha256_file(os.path.join(a.out, name)), name))
        for arc, src in sorted(members):
            size = os.path.getsize(src)
            manifest.append((sd.sha256_file(src), size, study, arc))
            if arc.startswith(study + "/") and is_table(arc) and size <= TABLE_MAX:
                tables.append((arc, src))
        print("%s  %d files  %.1f MB" % (name, len(members), os.path.getsize(os.path.join(a.out, name)) / 1e6))
    with open(os.path.join(a.out, "SHA256SUMS"), "w") as f:
        f.write("".join("%s  %s\n" % s for s in sums))
    if partial:
        return
    with open(sd.SUMS, "w") as f:
        f.write("# sha256 of the release assets of tag %s (tools/build-stats-data.py)\n" % sd.TAG)
        f.write("".join("%s  %s\n" % s for s in sums))
    with open(sd.MANIFEST, "w") as f:
        f.write("# every file of the release assets of tag %s: sha256, size in bytes, study (the asset\n"
                "# %s), path inside the asset. Written by tools/build-stats-data.py.\n" % (sd.TAG, sd.ASSET % "<study>"))
        f.write("".join("%s  %d  %s  %s\n" % m for m in manifest))
    if os.path.isdir(TABLES_DIR):
        shutil.rmtree(TABLES_DIR)
    for arc, src in tables:
        dst = os.path.join(TABLES_DIR, arc)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
    print("manifest: %d files, %.1f MB; tables kept in git: %d files, %.2f MB" % (
        len(manifest), sum(m[1] for m in manifest) / 1e6, len(tables), sum(os.path.getsize(s) for _, s in tables) / 1e6))


if __name__ == "__main__":
    main()
