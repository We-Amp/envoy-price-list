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
| Releases | `price-list-v2/pilot-v2/` | the first release session: three releases, 12 rounds in rotated order, Holm across 9 comparisons. The figures the post quotes from it (−6.3%, +1.2% and the 16 KB shape) are here; the second session is in the week-4 table below |
| Surplus worker threads in a container pod | `worker-count/ab/` | `ab-records.json` (every arm attempt and leg), `ab-summary.json`, `log.txt` |
| | `worker-count/calib/` | calibration |
| | `worker-count/cstate/` | the idle-state follow-up: `run/cs-records.json`, `run/cs-summary.json`, per-leg `perf` CSVs, `idle-orig.txt` (the idle-state configuration that was restored), `restore.log` |
| | `worker-count/scripts/`, `worker-count/cstate/scripts/` | the pod driver (`wc2.py`, `wc3.py`), the table scripts and the pod manifest. They import the harness's `epl` package (statistics, Nighthawk parsing), which is not duplicated here |
| Upstream connection reuse order | `upstream-pool-lru/two-hop/`, `two-hop-r2/` | pool much larger than the load needs, and its repeat run; `tables.md`/`tables.json`, `tables-r2.md`/`tables-r2.json` |
| | `upstream-pool-lru/one-hop/` | a proxy whose upstream is a web server |
| | `upstream-pool-lru/demand-pool/` | pool grown with the load (`demand-pool/`), with keep-alive limits (`demand-pool-ka/`), a short pilot, and `tables.md` |
| | `upstream-pool-lru/burst/` | the 40 ms stall of the second proxy (`burst/`), its smoke runs, socket-count runs (`sockets-*`), and `tables-burst.md`/`tables-burst.json` |
| | `upstream-pool-lru/probe-*/`, `smoke-limits/`, `tables-limits.md` | saturation probes; the post does not publish maximum rates from them |

## Week 4 update (16 November 2026)

The update of the post on 16 November added a second release session at two load levels and two setting
rows. All three were measured in one session on 15 November, on the same machine. Their tables are in
`releases-backfill/tables.md` and `releases-backfill/tables.json` (written by `examples/releases/table.py`).

| Post section | Directory | Notes |
|---|---|---|
| How every number is measured: the A/A floor (0.7% to 1.7% in the second release session) | `releases-backfill/releases/` | arm `v1.40.2-A2`, a second copy of v1.40.2 run in the same rounds as the releases; the "A/A of the session" table at the top of `tables.md`, per shape and load level |
| Settings: JWT authentication (local JWKS, RS256) | `settings-filters/11-jwt-authn/` | three arms: `jwt-off` (the reference; its client sends the same token), `jwt` (every token verified) and `jwt-cache` (the filter's cache of verified tokens, one token in use); 4 KB proxied at 5,200 req/s and the header-heavy direct response at 8,000 req/s |
| Settings: Local rate limit, never triggered | `settings-filters/12-local-ratelimit/` | two arms, `ratelimit-off` and `ratelimit-on` (one token bucket shared by the workers, enforced on every request, budget far above the rate); same two shapes and rates |
| Releases | `releases-backfill/releases/` | the second release session: six releases (v1.32.13, v1.34.14, v1.36.13, v1.37.11, v1.38.9, v1.40.2) and the A/A arm, 7 arms in rotated order, 14 rounds. Two shapes, each at two load levels: `s` (4 KB proxied) at 5,200 and `s-hi` at 12,000 req/s, `fh` (header-heavy direct response) at 8,000 and `fh-hi` at 18,400 req/s. Holm across 24 rows, the 20 comparisons and the 4 A/A checks. On the two higher-rate shapes the client ramps its rate over the first second |
| | `releases-backfill/cal/` | the calibration legs that set the two higher rates, with the client ramp (`*-ramp*`) and without it |
| | `releases-backfill/queue.log` | the run queue of the session, in the order the three runs ran |

The two setting rows take their A/A floor from the `v1.40.2-A2` arm of the release run (`floor_arm` in
their `experiment.json`); the tables print it next to every row. The configs are in the harness repository
under `examples/releases/` and `examples/settings-matrix/filters/`.

## Route table and constant-header re-measure (16 November 2026)

The route-table and header changes measured again with the full method, in one session on 16 November on the
same machine. Envoy serves direct responses only (no origin). Tables: `route-table/tables.md` and
`route-table/tables.json` (written by `examples/route-table/table.py`).

| Run | Directory | Notes |
|---|---|---|
| 1,000 routes | `route-table/rt-n1000/` | one virtual host, the request `GET /target/x` matching the last of 1,000 routes. Arms `base`, `d1v4` (path first), `d2v3` (a route index prototype, not proposed upstream) and `base-A2` (a second copy of base, the A/A of the run); 16 rounds in rotated order at 2,000 and 16,000 req/s; Holm across the run's primary rows |
| 200 routes | `route-table/rt-n200/` | the same four arms on 200 routes, 16 rounds at 2,000 and 22,000 req/s |
| One route | `route-table/rt-n1/` | the control: `base`, `d1v4`, `d2v3` on a single route, 12 rounds at 2,000 and 22,000 req/s; no A/A arm |
| 109 constant headers | `route-table/hdr/` | arms `base`, `s1` (the header change) and `base-A2` on a direct-response route that adds 57 request and 52 response constant headers; 24 rounds at 2,000 and 20,000 req/s |

The builds, by file name and md5 (the md5 identifies the binary):

| Arm | File | md5 | Source |
|---|---|---|---|
| `base` (route runs) | `envoy-routes-base` | `e59880d7374383c6df4dcaad6c71dd7e` | Envoy main 8ce942ce56 |
| `base` (header run) | `envoy-headers-base` | `e59880d7374383c6df4dcaad6c71dd7e` | the same binary under a second name |
| `d1v4` | `envoy-routes-path-first` | `7fac057ec1629117f7ebcccfbf52b923` | branch `patches/route-match-path-first-v4` of https://github.com/We-Amp/envoy (28f612622a) |
| `d2v3` | `envoy-routes-index-prototype` | `bf9fd4b39b85602a840480224fe3a1b2` | a route index prototype, not proposed upstream; its source revision is written as `patched-build` |
| `s1` | `envoy-headers-reference` | `a1da0f89183496870b9f9c1657bbe931` | 60556c39ef, the same source tree as branch `patches/router-header-reference-v3` of https://github.com/We-Amp/envoy (75887067de) |

Each run directory has the files listed under "File formats" below, with `perf/` and `ss/`. The route tables
and the header route are in the harness repository under `examples/route-table/tables/`, each with the md5 of
the recorded config it was converted from. On the higher-rate shapes the client ramps its rate over the first
second.

Left out of this set: the raw Nighthawk output of every leg, the proxy and client logs, the calibration legs,
the two smoke runs, and the session's queue logs.

## Release record, first session (16 November 2026)

The Releases section of the post from 17 November. The protocol (record/1), the arms, the rows named before the
runs, the deviations and the results are in `RELEASE-RECORD.md` in the harness repository. One session on 16 and
17 November, on the same machine, all under `release-record/2026-11-16/`.

| Post section | Directory | Notes |
|---|---|---|
| Releases: the binaries | `release-record/2026-11-16/static.json` | static record of 13 official release binaries (v1.32.13 to v1.40.2): size, sha256 and the published digest it matched, `--version`, GNU build id, section sizes, `.comment` strings, symbol table presence |
| | `release-record/2026-11-16/sha256-*.txt` | sha256 of every binary at the start and end of the two run queues |
| Releases: the table, the header-heavy and proxied bullets, patch releases | `release-record/2026-11-16/run-a/` | Run A: v1.37.0, v1.37.11, v1.38.0, v1.38.9, v1.39.6, v1.40.0, v1.40.2 and `v1.40.2-A2` (a second copy of v1.40.2, the A/A of the session), 8 arms in rotated order, 32 rounds on the four cells `s` 5,200, `fh` 8,000, `s-hi` 12,000 and `fh-hi` 18,400 req/s. Confirmatory rows (v1.38.0 against v1.37.11, Holm over 4) in `analysis.shapes.*.confirmatory`; record rows Holm over 28. A 3 s lead-in on the two higher-rate cells |
| Releases: patch releases one by one | `release-record/2026-11-16/run-b/` | Run B: v1.38.0, v1.38.2, v1.38.5, v1.38.7, v1.38.9 on `s-hi` and `fh-hi`, 20 fixed rounds, no A/A arm |
| Releases: hardware counters, and the exploratory v1.32.13 reading at 12,000 req/s | `release-record/2026-11-16/run-c/` | Run C: v1.32.13, v1.37.11, v1.38.9, v1.40.2 on `s-hi` and `fh-hi`, 24 fixed rounds, no A/A arm; the perf event list rotates over three groups by round (`perf_events` per leg in `legs.jsonl`, the extra events per request under `per_req.events`); cycles are counted as one `cycles` event (user and kernel together) |
| | `release-record/2026-11-16/tables-a.md`, `tables-c.md`, `tables-b.md` (and `.json`) | the tables of the three runs, written by `examples/release-record/table.py` |
| | `release-record/2026-11-16/queue-1.log`, `queue-2.log` | the two run queues: the three smoke runs and Run A; then Runs C and B (this queue logs itself as `queue3`; a queue in between only waited for a start time and was stopped before it ran anything) |

Each run directory has `results.json`, `legs.jsonl`, `summary.md`, `experiment.json`, `envoy-bootstrap.json`,
`status.json`, `log.txt`, `perf/` and `origin/`. Left out of this set: the raw Nighthawk output of every leg, the
proxy and client logs, the socket listings, and the three smoke runs (their legs appear in `queue-1.log`).

Also included, not cited by the post:

- `price-list-wk1/`: the first release comparison and A/A, measured with the first version of the method
  (6 rounds, fixed order, median ratios). Superseded by `price-list-v2/`; kept for completeness.
- `noise-hunt/`: the A/A noise hunt behind the method table in the harness README (one change at a time,
  12 rounds each). Only `legs.jsonl` is kept per step.

Left out: the raw Nighthawk output of every leg (about 1 GB; the parsed counters are in `legs.jsonl`), the
proxy and origin logs, the generated test certificates and the static files the origin served, a saturation
probe that was aborted, and an earlier run of the worker-thread measurement on a different, virtualised
machine whose A/B the bare-metal run replaced.

## Feature rows (17 and 18 November 2026)

Two sessions of setting rows, each in one directory with its own `README.md` (harness commit, machine, what is
in it): `features/2026-11-17/` (access log, tracing, external authorization, retries, idle timers, per-CPU
memory caches) and `features/2026-11-18/` (compression, Lua and Wasm filters, load curves). The protocol is
described in the harness repository's `README.md` and `RELEASE-RECORD.md`; the configs are in
`examples/settings-matrix/features/` and `features2/`. Each has `tables.md`. As in the earlier sets, the raw
Nighthawk output, the proxy and client logs, the socket listings and the smoke runs are left out.

Edits made for publication, in addition to those below: the run label is replaced by `features-2026-11-17` and
`features-2026-11-18` in run names and paths, and `host_id` is `bench-host`.

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
- In `route-table/`, the run labels are dropped from run names and paths (`~/epl/runs/route-table`), the
  builds carry the file names in the table above (thread names cut to 15 characters, such as
  `envoy-routes-ba`), the prototype's source revision is `patched-build`, and the recorded config of the
  header route is called `headers109.yaml`. Its md5 is unchanged.
- In `release-record/`, the session label is dropped from run names and paths (`release-record-a`,
  `~/epl/runs/release-record`), the second run queue's files are numbered 2 (`queue-2.log`,
  `sha256-start-2.txt`, `sha256-end-2.txt`), a container on the machine that the harness did not start is written as
  "1 foreign, untouched", and the `version` field in `static.json` keeps only the text after `version: ` (the
  line also carried the local binary path; `static.py` now writes it that way).
- `config_sha256` and `bootstrap_sha256` were computed on the text as run, so they may not match an edited
  file. The `harness` version strings name revisions from before the harness was published.

No measured value was changed.

## Licence

See `LICENSE`.
