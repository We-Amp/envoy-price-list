# Envoy price list: raw data

The per-run records behind "What Envoy settings and releases cost in CPU: a measured price list". Every
directory with a `results.json` was written by the `envoy-price-list` harness; the configs that produced
them are in the harness repository under `examples/`. The worker-thread section used its own driver,
included here under `worker-count/scripts/`.

All runs are from one machine: a bare-metal dual-socket Intel Xeon E5-2673 v4 server, fixed 2.3 GHz, turbo
off, Ubuntu 24.04 with kernel 6.8. The proxy is pinned to four cores of one socket with their hyperthread
siblings left idle, and the load generator and origin run on the other socket. Client and origin are on
loopback.

## What is here, by section of the post

| Post section | Directory | Notes |
|---|---|---|
| How every number is measured: the A/A floor | `settings-matrix/aa/` | HTTP/1 A/A of the settings session (about 1.2%) |
| | `settings-followups/aa-tls/`, `settings-followups/aa-h2/` | A/A on the TLS shapes and on HTTP/2 (about 1.9%) |
| | `price-list-v2/aa-v2/` | A/A of the release session (about 1.7%) |
| | `aa-label-swap/` | a further A/A with the arm labels swapped, plus `aa_decompose.py` and its outputs (`decompose-*.json`, `pooled.txt`): pooled over all A/A runs, the bias bound of about 0.2% and the between-session spread of about 0.34% |
| Settings | `settings-matrix/01-tls-cert/` ... `10-two-hop/` | one experiment per row; `matrix-table.md` and `matrix.json` are the matrix-wide table with Holm across 15 primary rows |
| | `settings-followups/f3-tls-cert/`, `f3-tls-resumption/` | the TLS rows with reconnects spread out in time (the post's headline figures); the matrix rows 01 and 02 are the "earlier run" with reconnects at the same moment |
| | `settings-followups/f2-ext-authz/` | external authorization, HTTP and gRPC service |
| | `settings-followups/f2-buffer-limit/` | buffer limit with flow-control counters, and the 2 KB body that fits |
| | `settings-followups/f1-two-hop/` | the second hop with both proxies evenly loaded; `settings-matrix/10-two-hop/` is the stock chain |
| | `settings-followups/sat/` | short saturation probes; the post does not publish maximum rates from them |
| | `settings-matrix/cal/`, `cal2/` | calibration legs used to pick the rates |
| Releases | `price-list-v2/pilot-v2/` | three releases, 12 rounds in rotated order, Holm across 9 comparisons |
| Surplus worker threads in a container pod | `worker-count/ab/` | `ab-records.json` (every arm attempt and leg), `ab-summary.json`, `log.txt` |
| | `worker-count/calib/` | calibration |
| | `worker-count/cstate/` | the idle-state follow-up: `run/cs-records.json`, `run/cs-summary.json`, per-leg `perf` CSVs, `idle-orig.txt` (the idle-state configuration that was restored), `restore.log` |
| | `worker-count/scripts/`, `worker-count/cstate/scripts/` | the pod driver (`wc2.py`, `wc3.py`), the table scripts and the pod manifest. They import the harness's `epl` package (statistics, Nighthawk parsing), which is not duplicated here |
| Upstream connection reuse order | `upstream-pool-lru/two-hop/`, `two-hop-r2/` | pool much larger than the load needs, and its repeat run; `tables.md`/`tables.json`, `tables-r2.md`/`tables-r2.json` |
| | `upstream-pool-lru/one-hop/` | a proxy whose upstream is a web server |
| | `upstream-pool-lru/demand-pool/` | pool grown with the load (`demand-pool/`), with keep-alive limits (`demand-pool-ka/`), a short pilot, and `tables.md` |
| | `upstream-pool-lru/burst/` | the 40 ms stall of the second proxy (`burst/`), its smoke runs, socket-count runs (`sockets-*`), and `tables-burst.md`/`tables-burst.json` |
| | `upstream-pool-lru/probe-*/`, `smoke-limits/`, `tables-limits.md` | saturation probes; the post does not publish maximum rates from them |

Also included, not cited by the post:

- `price-list-wk1/`: the first release comparison and A/A, measured with the first version of the method
  (6 rounds, fixed order, median ratios). Superseded by `price-list-v2/`; kept for completeness.
- `noise-hunt/`: the A/A noise hunt behind the method table in the harness README (one change at a time,
  12 rounds each). Only `legs.jsonl` is kept per step.

Left out: the raw Nighthawk output of every leg (about 1 GB; the parsed counters are in `legs.jsonl`), the
proxy and origin logs, the generated test certificates and the static files the origin served, a saturation
probe that was aborted, and an earlier run of the worker-thread measurement on a different, virtualised
machine whose A/B the bare-metal run replaced.

## File formats

A harness run directory holds:

- `results.json`: `metadata` (harness version, kernel, CPU model and topology, governor and clock per pinned
  CPU, idle-state configuration, binaries with md5, sha256 and version, Nighthawk version and md5, config and
  bootstrap hashes, origin image), `experiment` (the config as run, defaults filled in), `legs` (every leg
  with its raw counters and validity verdict, including invalid and superseded legs), `analysis` (paired
  log-ratio effects with 95% t intervals, Holm-adjusted p-values, sign and Wilcoxon tests) and, for an A/A,
  `aa_selftest`.
- `legs.jsonl`: one JSON object per leg as it finished (the same records as `results.json` `legs`), plus
  re-run markers that carry no `shape` key. Where a leg was re-run, the record with the highest `attempt`
  counts.
- `summary.md`: the harness's Markdown report.
- `experiment.json`: the config as given.
- `envoy-bootstrap*.json`: the generated Envoy bootstrap, one per arm (and per hop for two-hop arms).
- `status.json`, `log.txt`, `console.log`: progress and the run log.
- `perf/*.csv`: `perf stat -x,` output per leg (`rNN-<shape>-<arm>.csv`).
- `origin/`: the generated nginx configuration; `collector/config.yaml`: the null OpenTelemetry collector.
- `ss/*.txt.gz`, `timeline/`: socket listings and per-second samples kept for the connection-reuse runs.
- `alog/*.sample`: the first lines of each leg's access log (access-log rows only).
- `calibrate.json`, `calibrate-legs.jsonl`, `probe.json`, `probe.jsonl`: single legs at chosen rates.

`queue.log` files and the small `*.sh` files are the run queues as they ran on the bench box.

## Edits made for publication

- Home directory paths are written as `$HOME` (or `~`, as the harness writes them), and the host
  identifier is `bench-host`.
- The patched build of the connection-reuse section is called `envoy-1.40.2-pool-order` (its thread names
  appear as `envoy-1.40.2-po`), and the source revision in its version string is replaced by
  `patched-build`. Its md5 is unchanged and identifies the binary. The patch is branch `exp/upstream-pool-lru` of https://github.com/We-Amp/envoy (one commit on v1.40.2).
- The Nighthawk client path is written as `~/nighthawk/bazel-bin/nighthawk_client`.
- `config_sha256` and `bootstrap_sha256` were computed on the text as run, so they may not match an edited
  file. The `harness` version strings name revisions from before the harness was published.

No measured value was changed.

## Licence

See `LICENSE`.
