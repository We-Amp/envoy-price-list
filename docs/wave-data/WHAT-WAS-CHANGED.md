# Wave studies data: what was changed in the raw records before publication

The archives hold the records as the harness wrote them, with the changes listed here. No measured
value was changed: every change is inside a text string, and no number, boolean, timestamp, leg id,
validity field or key differs from the record as run. The changes were made with
`epl scrub --publish` (`epl/pubscrub.py`) and checked with its `--check` mode, which
`tools/build-wave-data.py` runs again on every study before it writes an archive.

## Left out

- **TLS private keys and certificates** that the harness generated per run directory for the TLS arms
  (`connection-churn`: the `certs/` directories of `e-tls`, its smoke and the handshake check `e2/hrr`;
  10 files). They are test material made fresh for each run, and a private key is never published.
  The configs and records still name their paths. `tools/build-wave-data.py` refuses a tree that has a
  `certs/` directory, a key or certificate file, or a file that holds a PEM private key.
- **The `perf.data` files of the LBR legs** (`topdown/lbr-data/`, 6 files, and the profiling legs of
  `code-layout`, `prof/` and `prof2/`, 12 files; about 1 GB together). They are binary, and their headers
  carry the paths of the machine they were recorded on. The legs' records (`legs.jsonl`, `results.json`,
  `manifest.txt` with pid and executable per file, and `lbr-summary.json` for the top-down legs) are
  published; the profiles can be recorded again with `examples/topdown/perf-lbr.sh` and
  `examples/wave2/perf-lbr.sh`, and the builds that used them are in `tools/code-layout`.
- **Two packed copies** (`statsd-batching/wave1-b-runs.tgz`, `statsd-batching/v2-confirm/v2c.tgz`) of
  run directories that are published unpacked beside them.
- **Scripts that were kept beside the data** (the configs and scripts of the top-down study and the
  table script of the upstream-protocols study): they are in the repository, cleaned, under
  `examples/topdown/` and `examples/wave3f/table.py`.
- One process id file of a finished session chain.

## What was changed in the raw records

102 of the published files differ from the files the runs wrote.

- **Home directory prefixes** are written `~` (400 places in 77 files: log and console lines, the paths
  in config dumps and bootstraps, and the `binary`, `path` and `run_dir` fields), in every file and gzip
  member.
- **The user name** in `ls -l` listings of the profiling legs' data directories is written `user`
  (184 places in 6 files).
- **The pgolto binary of the top-down study** was recorded under a path and file name that named a
  person's role. It is written `~/epl/bins/pgolto/envoy-pgolto-prodalloc` (15 places in 11 files), and
  the process name the kernel shows for it, 15 characters long, `envoy-pgolto-pr` (150 places in 4 files).
  Its md5 and sha256 are unchanged.
- **Fixed strings that the configs copied into each run** referred to a person's decision. The
  `short_run_note` of the `ext-proc-xds` runs now reads "short run: 6 fixed rounds (large effects: stop
  when the answer is clear); ..." (6 places in 6 files) and that of the `upstream-protocols` runs
  "short run: N fixed rounds in Williams order, ..." (10 places in 10 files). The configs in
  `examples/wave1c/configs/` and `examples/wave3f/configs/` carry the same wording.
- One sentence of `statsd-batching/v2-confirm/classes.md` referred to a review document that is not
  published; the reference is gone (1 place).
- Because of these edits `config_sha256`, `bootstrap_sha256` and the frozen evidence configs, which were
  computed on the text as run, may not match a published file.

No host name, IP address outside the loopback range, cloud VM name or credential was found in the
records; `epl scrub --publish --check` finds nothing to change in the published tree.

## Rendered again or written for the publication

- `topdown/tables.md` and `topdown/tables.json` were rendered again from `topdown/td` with
  `examples/topdown/analyse.py`. Against the tables rendered when the run was analysed, only labels
  differ: the title, and the decision rows' labels (internal item numbers replaced by what each row
  decides). Every number and verdict is the same.
- `code-layout/ab/analysis.md` and `code-layout/w2b/analysis.md` were rendered again with
  `examples/wave2/analysis/analyse_w2.py` and `analyse_w2b.py`. Only the heading of the decision rules
  differs (a document reference replaced by "fixed before the run").
- Written for the publication from the records, with the scripts of the repository:
  `connection-churn/tables.md` and `connection-churn/e2b/tables.md` (`examples/wave3e/table.py`), and
  `upstream-protocols/run1/f1-upstream-tables.md`, `run1/f3-mtls-tables.md` and
  `run2-f2/f2-grpc-tables.md` (`examples/wave3f/table.py`).
- `statsd-batching/tables.md`, `tables.json`, `v2-confirm/tables.md`, `v2-confirm/tables.json` and
  `ext-proc-xds/tables.md` are as rendered when the runs were analysed; the commands in
  `docs/wave-studies.md` render them again byte for byte.
- `statsd-batching/v2-confirm/classes.md` (the datagram split from the receiver's 5 s marks) was
  computed when the run was analysed by a script that is not in the repository; no published command
  renders it. `examples/wave1-b/analysis/classes.py` gives the whole-leg split it replaced.

## What was not changed: commit ids

The records name the harness commit each run used (`metadata.harness`, and the same string in
`summary.md`) and the Envoy commits of the own builds (in the binaries' `source` fields). These are the
ids of the commits that were measured, left as recorded. The measured harness commits are not in the
published history; `docs/wave-data/harness-commit-map.md` says where their code is.
