# Wave 4 (HTTP/3) data: what was changed in the raw records before publication

The archive holds the records as the harness wrote them, with the changes listed here. No measured value
was changed: every change is inside a text string. The changes were made with `epl scrub --publish`
(`epl/pubscrub.py`) and checked with its `--check` mode, which `tools/build-wave-data.py` runs again
before it writes the archive.

## Left out

- **TLS private keys and certificates** generated per run directory (the `certs/` directories of every run
  and smoke; 14 files). The configs and records still name their paths.
- **Four packed copies** (`wave4g.tgz`, `wave4g-s.tgz`, `wave4g-s2.tgz`, `wave4g-s3.tgz`) of the session
  directories that are published unpacked.

## What was changed

53 of the published files differ from the files the runs wrote.

- **Home directory prefixes** are written `~` (158 places in 44 files).
- **The `short_run_note`** that the configs copied into each run referred to who decided the short run; it
  now reads "short run: 8 fixed rounds in Williams order, run with --allow-short" (9 places in 9 files). The
  configs in `examples/wave4g/configs/` carry the same wording.
- Because of these edits `config_sha256`, `bootstrap_sha256` and the frozen evidence configs may not match
  a published file.

## Written for the publication

`wave4g/tables.md` and `wave4g-s3/tables.md`, rendered from the records with `examples/wave4g/table.py`.
The two `*-worker-shares.csv` files are as written when the runs were analysed; no published script writes
them (every value is in the legs' records).

## Commit ids

The records name the harness commits that were measured, left as recorded; see
`docs/wave-data/harness-commit-map.md`.
