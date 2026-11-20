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

## Scrubbed

With `epl scrub --publish` (`epl/pubscrub.py`):

- Home directory prefixes are `~`, in every file and gzip member.
- `host_name` in the benchmark outputs is the machine label of the table above. VM names are that
  label too.
- The record strings that the configs copied into each run (`invol_bound_record`, `short_run_note`,
  the dose notes, the label of the re-evaluation, one line in the queue logs) referred to planning
  notes that are not published; they carry the wording of the current configs instead. The decision
  record `contention/dose-decision-2.json` has its `decision` text replaced the same way.
- The kernel release of the Arm VM is written as `7.0.0-1017-cloud` (the image's flavour suffix
  replaced).
- `arm-lse-llsc/build-record.txt` is written for the publication from the build record of the session (the
  four sha256 lines are unchanged).
- `config_sha256`, `bootstrap_sha256` and the recorded check of run L's config were computed on the
  text as run, so they may not match a scrubbed file.

## Rendered again

The tables and analysis outputs in the archives (`*.md`, `analysis/*`, `table.json`, the
`microbenchmarks/reeval/` tree) were rendered from the scrubbed records with the harness of the
repository; `README.md` says which of them are identical to the tables rendered when the runs were
analysed.
