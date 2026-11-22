# Wave studies data: the raw records

The raw records of the wave studies of the Envoy price list: waves 1 to 3 (statsd batching, ext_proc
and xDS updates, top-down counters, connection churn, upstream protocols) and the code-layout work of
wave 2. One archive per study, assets of the release of tag `waves-2026-11` of
https://github.com/We-Amp/envoy-price-list. `python3 tools/fetch-wave-data.py` in that repository
downloads them, checks each archive and every file against the manifest in git, and unpacks them into
`data/waves/`.

Every study ran on one bench box: a two-socket Xeon E5-2673 v4 (2 x 20 cores, SMT on), bare metal,
2.3 GHz fixed, turbo off, kernel 6.8; Envoy on CPUs 0-3 (4 workers) with their SMT siblings idle, the
client (Nighthawk) on 20-31,60-71, the origin (`nginx:alpine`, pinned digest, in Docker) on 32-39,72-79.
The records call it `bench-x86_64`. The configs, the scripts that ran the sessions and the scripts
that render the tables are in the repository under `examples/` (named per study below);
`docs/wave-studies.md` there has the commands that render every table from these records.

What was changed in the records before publication (home paths, a binary's name, a few fixed
strings; keys and `perf.data` left out): `WHAT-WAS-CHANGED.md`, next to this file.

## A run directory

Every run is a directory as `epl run` writes it: `experiment.json` (the config as run), `legs.jsonl`
(one record per leg, the unit every table is computed from), `results.json` (the analysis),
`summary.md`, `status.json`, `log.txt`, the Envoy bootstraps (`envoy-bootstrap*.json`), and per leg
`perf/`, `nighthawk/` (gzip), `stats/`, `config_dump/` (gzip), `logs/`, `ss/`, `origin/` (the origin's
config and files) and, where a run used them, `udpsink/` (the discard sink's counts) or `xds/` (the
xDS files and their update records). `smoke/` holds the one-round smoke of a run and `frozen/` the evidence
configs frozen from it; `queue.log` and `chain*.log` are the session logs.

## The studies

| Archive (`waves-2026-11-data-<study>.tar.gz`) | Wave | Configs and scripts | Runs |
|---|---|---|---|
| `statsd-batching` | 1 | `examples/wave1-b` | `wave1-b/b-statsd`, `wave1-b/b-statsd-nosink`, `wave1-b/b-fl` (and their smokes); the confirmation run `v2-confirm/wave1-b-v2c/v2c`; tables `tables.md`, `tables.json`, `v2-confirm/tables.md`, `v2-confirm/tables.json`, `v2-confirm/classes.md` |
| `ext-proc-xds` | 1 | `examples/wave1c` | `extproc`, `xds-small-s` (and their smokes); `tables.md` |
| `topdown` | 1 | `examples/topdown` | `td` (counter census, 24 rounds), `lbr` (LBR legs: records only, the `perf.data` files are not published), `attempt1` (the first chain, which stopped before its first leg on a binary check); `tables.md`, `tables.json`, `lbr-summary.json`, the binaries' checksums, the box's perf event list and CPU vulnerability state |
| `code-layout` | 2 | `examples/wave2`, `tools/code-layout` | `prof/wave2-prof/lbr-w2-opt` and `prof2/lbr-w2` (profiling legs: records and manifests only), `ab/w2` (the A/B run), `w2b/w2b` (the follow-up run); `ab/analysis.md`, `w2b/analysis.md` |
| `connection-churn` | 3 | `examples/wave3e` | `e-plain`, `e-tls` (and smokes); `e2` (the HelloRetryRequest check `e2/hrr` and the smoke of `e2-plain`, which failed its gates); `e2b/e2b-plain`; `tables.md`, `e2b/tables.md` |
| `upstream-protocols` | 3 | `examples/wave3f` | `run1/f1-upstream`, `run1/f3-mtls` (and smokes; the `f2-grpc` smoke of that session stopped on a harness error), `run2-f2/f2-grpc` (and its smoke); `run1/*-tables.md`, `run2-f2/f2-grpc-tables.md` |

## Binaries

- The official `envoy-1.40.2-linux-x86_64` release asset (sha256
  `1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc`) in every arm of `ext-proc-xds`,
  `connection-churn` and `upstream-protocols`, and as `stock`, `control` or `opt` elsewhere.
- Own builds of tag v1.40.2 (`statsd-batching`, `code-layout`) and of an upstream main commit
  (`topdown`'s `pgolto`): each pinned by sha256 in the configs (`examples/wave1-b/bins.json`,
  `examples/wave2/bins.json`, `examples/topdown/topdown-a.json`) and checked by the harness before the
  first leg of every run. The binaries themselves are not published; `tools/code-layout` builds the
  code-layout arms again.
- Nighthawk 0.3.0 as the client.

## Commit ids

`metadata.harness` in each `results.json` is the harness commit that was measured (or "uncommitted"
for a run from a `git archive` without a commit file). `docs/wave-data/harness-commit-map.md` in the
repository says where that code is in the published history.
