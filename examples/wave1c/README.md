# Wave 1, track C: the ext_proc filter and the price of one xDS update

Two price-list rows on the official Envoy v1.40.2 binary, config only. Data: the `ext-proc-xds`
archive of the wave studies (`python3 tools/fetch-wave-data.py ext-proc-xds`, see
[`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Bench box: two-socket Xeon E5-2673 v4 (2 x 20 cores, SMT on), bare metal, 2.3 GHz fixed, turbo off.
  Envoy on CPUs 0-3 (4 workers) with their SMT siblings idle; client (Nighthawk) on 20-31,60-71;
  origin (`nginx:alpine`, pinned digest, in Docker) and the side services on 32-39,72-79.
- Binary: the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…`) in every arm,
  at `~/epl/bin/envoy-1.40.2`; the harness checks its sha256.
- The ext_proc side service is [`tools/extproc`](../../tools/extproc): a minimal Go service that
  answers every message with the empty response of its phase, so the row prices Envoy's side of the
  protocol. Built off the box with `tools/extproc/build.sh` (toolchain and image pinned in
  `tools/extproc/TOOLCHAIN`, output checked against `tools/extproc/SHA256SUMS`); the harness refuses to
  start it when its sha256 differs.
- Method: paired rounds, 6 fixed rounds per run (a short run, `--allow-short`: the effects are large),
  rotated arm order, an A/A copy of the base arm in every run; per-thread cycles (main thread, workers,
  other threads) and the side service's own CPU (exploratory, never added to Envoy's).

## Runs

| Config | Arms | Shape |
|---|---|---|
| `configs/extproc.json` | `off` (base), `off-A2`, `authz-grpc` (the published ext_authz row, as anchor), `xp-default` (ext_proc, request and response headers), `xp-reqhdr` (request headers only), and the three filter arms again through `google_grpc` | `s`: 4 KB proxied, 5,200 req/s |
| `configs/xds-small-s.json` | `ref` (no updates, base), `ref-A2`, `rds` (route table changed), `rds-same` (re-sent unchanged), `cds` (a filler cluster changed), `cds-same`, `cds-active` (the cluster in use changed), `eds` (one host replaced); one update per second, state of the world from watched files; 200 filler routes, 50 filler clusters, a filler EDS cluster of 100 endpoints | `s` only |
| `configs/xds-small.json`, `configs/xds-large.json` | the same at shapes `s` and `s-lo` (400 req/s), and at 2,000 routes, 500 clusters, 1,000 endpoints | written, not run in the published session |

Each `configs/smoke-*.json` is one round of every arm in a fixed order, evidence recorded.

## Files

- `make.py` writes the configs (`python3 examples/wave1c/make.py`; a `RATES_JSON` file lowers `s` when
  the smoke shows a worker above 80% busy; `make.py budget` prints the session's time budget).
- `run-session-c.sh smoke|check|queue` and `chain-c.sh RUNS_DIR`: the session as run (smokes, the rate
  rule, evidence freeze and check, then `extproc` and `xds-small-s`).
- `local_check.py validate|functional WORKDIR`: checks of every arm with the official v1.40.2 image
  (`envoyproxy/envoy:v1.40.2`, its binary's sha256 checked) in Docker, off the bench box; no measurement.
- `table.py extproc|pairs|xds|validity|threads RUN_DIR ...`: the tables of the data.

The commands that render every table from the data are in [`docs/wave-studies.md`](../../docs/wave-studies.md).
