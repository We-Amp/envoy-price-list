# Stats study data: what was changed in the raw records before publication

The archives hold the records as the harness wrote them, with the changes listed here. No measured
value was changed.

## Left out

To keep the data at about 320 MB:

- `logs/` (Envoy and tool logs per leg) and `ss/` (socket snapshots) of every run: no table or
  analysis reads them.
- Smokes that a later smoke replaced (the first smoke of run L, the first smoke of the OTLP
  re-run), and the full stats dumps of run L's smoke.
- The stopped 1,800 req/s attempt except its leg records and calibration records
  (`multi-worker-high-load/stopped-1800/`), which the run U-hi analysis reads.
- Partial files of interrupted processes (`*.tmp`) outside the round-5 microbenchmark sets, the
  `perf.data` of the main-thread profile (`perf-report.txt` and `profile.json` are kept), the
  binaries, and the rejected rows of round 4 other than `flush_contended`.
- Calibration runs that were repeated, and a smoke that collided with another process.

## Stored in another form

- Envoy bootstraps (`envoy-bootstrap-*.json.gz`) and the load generator's per-leg output
  (`nighthawk/*.json.gz`) are gzip-compressed. A bootstrap at 1M stats is 8 MB of generated clusters;
  `examples/stats-flush/make.py` writes the configs they come from. The analysis scripts read the
  compressed form.

## What was changed in the raw records

273 of the files differ from the files the runs wrote. Every difference is inside a text string. No
number, boolean, timestamp, leg id, validity field, key or line count differs; we checked this by
comparing each published file with its original, field by field, twice, with two separately
written scripts. The changes were made with
`epl scrub --publish` (`epl/pubscrub.py`).

- Home directory prefixes are written `~` (603 places in 238 files: log and console lines, and the
  `executable`, `path`, `run_dir` and `version` fields), in every file and gzip member.
- `host_name` in the benchmark outputs (177 files) is the machine label of the README's table. The
  originals were two cloud VM names and one server host name.
- 15 fixed strings that the configs had copied into each run (`invol_bound_record`,
  `short_run_note`, `note`, `result`, `record`, one `decision`, and a few lines of the queue logs and
  of the `chain-dose-3` script and its log) referred to documents that are not published. They carry the wording of the current configs. Example: a note that
  began with a reference to a plan revision now reads "short run: 6 rounds instead of 15". 93 places in 37 files. The
  numbers inside these strings are unchanged, except that the numbers of the plan's revisions went
  with the words. The `decision` text of `contention/dose-decision-2.json`, which
  was a document reference, now reads "revision 3 of the run's plan (2026-11-20)".
- The kernel release of the Arm VM is written `7.0.0-1017-cloud`; the image's flavour suffix is
  replaced (6 places in 4 files).
- Because of these edits `config_sha256`, `bootstrap_sha256` and the recorded check of run L's
  config, which were computed on the text as run, may not match a published file.

## What was not changed: commit ids

The records name commits: the harness commit a run used (`metadata.harness`, and the same string in
`summary.md`), and the Envoy commits of the own builds (binary names, `expected_sha256` records,
arm names). These are the ids of the commits that were measured, left as recorded. The published
repositories carry cleaned copies of those commits under other ids:

- harness: `docs/stats-data/harness-commit-map.md` (measured id, published id, and the complete
  list of strings that differ between the two histories);
- Envoy: `docs/stats-data/envoy-commit-map.md`.

## Rendered again

Not raw records: the tables (`*.md`, `table.json`, `tables.json`, `codegen.json`, `u.json` and the
like) and everything under `analysis/` and `microbenchmarks/reeval/` were produced again from the
scrubbed records with the harness of the repository; where a run-time table existed and differs in
layout it is kept as `micro.as-run.md`. `README.md` says which of them are identical to the tables
rendered when the runs were analysed and which were written for the publication.
`arm-lse-llsc/build-record.txt` was written for the publication from the session's build record
(its four sha256 lines are unchanged).
