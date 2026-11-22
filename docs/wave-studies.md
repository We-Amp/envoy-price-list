# The wave studies: how to run them again

Waves 1 to 4 of the price list, and the code-layout work of wave 2: what each study needs to be
reproduced, where its configs and scripts are, and the commands that render every table from our
data. The studies:

| Study | Wave | Prices | Configs and scripts | Data archive |
|---|---|---|---|---|
| Statsd batching | 1 | the statsd sink sending one datagram per thread and event-loop turn; the request-header re-validation ceiling | [`examples/wave1-b`](../examples/wave1-b) | `statsd-batching` |
| ext_proc and xDS | 1 | the ext_proc filter (default mode and request headers only, envoy_grpc and google_grpc); one RDS, CDS or EDS update | [`examples/wave1c`](../examples/wave1c), [`tools/extproc`](../tools/extproc) | `ext-proc-xds` |
| Top-down counters | 1 | where the cycles of the official binary go (TMA level 1, i-cache, iTLB), against PGO + ThinLTO | [`examples/topdown`](../examples/topdown) | `topdown` |
| Code layout | 2 | call-graph order, AutoFDO, instrumented PGO + ThinLTO, BOLT, on v1.40.2 | [`examples/wave2`](../examples/wave2), [`tools/code-layout`](../tools/code-layout) | `code-layout` |
| Connection churn | 3 | one new connection, plaintext and TLS 1.3; listener accept settings under churn | [`examples/wave3e`](../examples/wave3e) | `connection-churn` |
| Upstream protocols | 3 | HTTP/2 (nghttp2, oghttp2) and TLS upstreams; unary gRPC and grpc_stats; mTLS between two hops | [`examples/wave3f`](../examples/wave3f) | `upstream-protocols` |
| HTTP/3 | 4 | HTTP/3 (QUIC) against HTTP/2 over TLS per request; the GSO writer; one new QUIC connection and the session-ticket default | [`examples/wave4g`](../examples/wave4g) | `http3` (second release) |

Each example directory has a README with the conditions of its runs (box, CPUs, binaries, shapes,
rates, rounds, order). This page has what is common and the commands.

Envoy patch sources: the `v2` statsd batching build of the statsd-batching study is tag
`statsd-batch-2026-11/v2` of https://github.com/We-Amp/envoy (branch `statsd-batch/v2`, commits
`77fdeb8484` and `ee71e0583f`). The sources of the first batching build (`7979fa6063`, superseded by v2)
and of the header-validation ceiling build (`af3172d385`, measurement only, result dropped) are not
published. The code-layout arms are builds of tag v1.40.2 (`tools/code-layout`).

## Get the data first

The raw records (about 650 MB unpacked) are not in git. They are assets of two releases, one archive
per study: tag `waves-2026-11` (waves 1 to 3 and the code-layout work) and tag `waves-2026-11b`
(wave 4, HTTP/3):

```
python3 tools/fetch-wave-data.py                      # every study
python3 tools/fetch-wave-data.py connection-churn     # or only the studies you name
python3 tools/fetch-wave-data.py --tag waves-2026-11b # or only the studies of one release
python3 tools/fetch-wave-data.py --list               # the studies, their sizes and asset names
```

The script downloads `<tag>-data-<study>.tar.gz` from
`https://github.com/We-Amp/envoy-price-list/releases/download/<tag>/` (each study from its own
release), checks each archive
against `data/wave-data.SHA256SUMS`, unpacks into `data/waves/` (ignored by git) and checks every file
against `data/wave-data.manifest`. `--from DIR` takes archives you already have; `--verify` checks the
unpacked tree again, for example after rendering the tables into it. The assets, sizes and checksums:
[`docs/wave-data/ASSETS.md`](wave-data/ASSETS.md). What is in the archives:
[`docs/wave-data/README.md`](wave-data/README.md) (also at the top of every archive). What was changed
in the records before publication: [`docs/wave-data/WHAT-WAS-CHANGED.md`](wave-data/WHAT-WAS-CHANGED.md).
The rendered tables are small and also in git, at their paths inside the archives:
[`docs/wave-tables/`](wave-tables/).

## What every study has in common

- **Hardware.** One bench box for all of them: a two-socket Xeon E5-2673 v4 (2 x 20 cores, SMT on),
  bare metal, 2.3 GHz fixed, turbo off, default idle states, kernel 6.8, perf 6.8. Envoy on CPUs 0-3
  (4 workers) with their SMT siblings idle; the client on 20-31,60-71; the origin and side services on
  32-39,72-79 (the second hop of a two-hop arm on 4-7). The CPU sets are in every config's `cpus`.
  Other hardware gives other cycle counts; the method carries over.
- **Software.** The official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…f03cc`) unless an
  arm names an own build; own builds are pinned by sha256 in the configs and checked by the harness
  before the first leg of every run. Nighthawk 0.3.0 as the client; `nginx:alpine` at a pinned digest
  as the origin, in Docker.
- **Method.** As the rest of the price list: every arm runs in every round, in an order the config
  fixes (Latin squares, a rotation, or Williams squares that balance first-order carryover, with an
  optional unscored warm-up leg before every round); each run has an A/A copy of its base arm; a run
  starts only after its one-round smoke passes and the run's evidence (stats that show each arm did
  what it should) is frozen from that smoke; every leg passes the harness's validity gates or the leg
  is invalid. Effects are mean per-round log ratios, shown as %, with the 95% t interval and the
  widened interval 1.96 x sqrt(SE^2 + 0.34^2); the quoted interval is the wider of the two.
- **Sessions.** Each session ran as one detached chain on the bench box (`chain-*.sh` in the example
  directory): idle check, binary checks, smokes, evidence freeze and check, then the runs, each only
  after the previous one ended cleanly. A bench box that is not a git checkout gets the harness as a
  `git archive` with a `HARNESS_COMMIT` file (`examples/wave2/pack.sh`), so the records name the commit.

## Regenerate the tables

From the repository root, after `python3 tools/fetch-wave-data.py`. Every command below writes the file
at its path in the archive; `python3 tools/fetch-wave-data.py --verify` afterwards confirms that each
one came out byte for byte as published.

```
D=data/waves
```

### Statsd batching (`statsd-batching`)

```
B_TABLES_JSON=$D/statsd-batching/tables.json python3 examples/wave1-b/analysis/analyse.py \
    $D/statsd-batching/wave1-b/b-statsd $D/statsd-batching/wave1-b/b-statsd-nosink \
    $D/statsd-batching/wave1-b/b-fl > $D/statsd-batching/tables.md
B_TABLES_JSON=$D/statsd-batching/v2-confirm/tables.json python3 examples/wave1-b/analysis/analyse.py \
    $D/statsd-batching/v2-confirm/wave1-b-v2c/v2c > $D/statsd-batching/v2-confirm/tables.md
python3 examples/wave1-b/analysis/classes.py $D/statsd-batching/v2-confirm/wave1-b-v2c/v2c
```

`tables.md`: per arm the cycles per request (total, the workers, the rest: main and other threads),
datagrams per request, drop share, and the paired comparisons against the base arm and, in
`b-statsd-nosink` and `v2c`, against `ctl-nosink`. `classes.py` prints datagrams per request split into
sample and flush datagrams over whole legs. `v2-confirm/classes.md`, the split inside the window from
the discard sink's 5 s marks, was computed by a script that is not published (see
`WHAT-WAS-CHANGED.md`).

### ext_proc and xDS (`ext-proc-xds`)

```
R=$D/ext-proc-xds
{ python3 examples/wave1c/table.py validity $R/extproc $R/xds-small-s; echo
  python3 examples/wave1c/table.py extproc $R/extproc; echo
  echo "Direct pairs:"; python3 examples/wave1c/table.py pairs $R/extproc; echo
  python3 examples/wave1c/table.py threads $R/extproc; echo
  python3 examples/wave1c/table.py xds $R/xds-small-s; } > $R/tables.md
```

`extproc`: per arm against `off`, total cycles per request (the harness's paired effect, the widened
interval beside it), the added cycles per request, the user and kernel split, the threads other than
main and workers (the gRPC client's own threads), worker busy, and the side service's own CPU per
request. `pairs`: the ext_proc arms against each other. `threads`: the cycles of every other thread by
name. `xds`: per update arm against `ref`, cycles per update split into main thread, workers and other
threads, with the A/A as the floor and the connections the origin accepted per update.

### Top-down counters (`topdown`)

```
python3 examples/topdown/analyse.py $D/topdown/td $D/topdown/tables.md
```

Writes `tables.md` and `tables.json`: per shape and arm the user-space TMA level 1 (frontend bound with
fetch latency and bandwidth, bad speculation, retiring, backend bound), the all-ring TMA, IPC, i-cache
and iTLB per request, and the decision rows for the code-layout follow-ups. `lbr-summary.json` was
written on the bench box from the LBR `perf.data` files (`examples/topdown/lbr-post.py`), which are not
published.

### Code layout (`code-layout`)

```
python3 examples/wave2/analysis/analyse_w2.py $D/code-layout/ab/w2 $D/code-layout/ab/analysis.md
python3 examples/wave2/analysis/analyse_w2b.py $D/code-layout/w2b/w2b $D/code-layout/w2b/analysis.md \
    $D/code-layout/ab/w2
```

`ab/analysis.md`: cycles (user + kernel) per response against `opt` and two direct pairs, per shape,
the A/A, the counter groups per arm, and the decision rules fixed before the run. `w2b/analysis.md`: the
follow-up run on shape `s` (BOLT against its own input `pgolto-relocs`, the `--emit-relocs` relink
alone, the order file on top of AutoFDO), with the AutoFDO share of the PGO gain chained through the
`w2` run (labelled chained). The arms' builds: [`tools/code-layout/README.md`](../tools/code-layout/README.md).

### Connection churn (`connection-churn`)

```
( cd $D/connection-churn && python3 ../../../examples/wave3e/table.py e-plain e-tls > tables.md &&
  python3 ../../../examples/wave3e/table.py e2b/e2b-plain > e2b/tables.md )
```

Per row: the cycles of one new connection (arm minus reference per request, paired by round, divided by
the arm's connections per request), split into user and kernel; the TLS rows give the certificate,
resumption and key-exchange-group differences per full handshake. The HelloRetryRequest check's record
is `e2/hrr/`.

### Upstream protocols (`upstream-protocols`)

```
U=$D/upstream-protocols
python3 examples/wave3f/table.py $U/run1/f1-upstream > $U/run1/f1-upstream-tables.md
python3 examples/wave3f/table.py $U/run1/f3-mtls > $U/run1/f3-mtls-tables.md
python3 examples/wave3f/table.py $U/run2-f2/f2-grpc > $U/run2-f2/f2-grpc-tables.md
```

Every paired comparison of the primary metric (total cycles per request; for `f3-mtls` the cycles of
both hops), with the t interval, the widened interval, Holm p and rounds won, and the confirmatory rows
fixed before the run with Holm-adjusted p. Add metric names (for example `cycles_user`) to print them
too.

### HTTP/3 (`http3`)

```
H=$D/http3
( cd $H && python3 ../../../examples/wave4g/table.py wave4g/g1-proto > wave4g/tables.md &&
  python3 ../../../examples/wave4g/table.py wave4g-s3/g2s-resume > wave4g-s3/tables.md )
```

Per row, paired by round: the effect on cycles (user + kernel) per request as a percent change with the
quoted interval, the same as a log ratio (log-%), the t and widened half-widths (log-%), rounds up, the deltas in total, user, kernel cycles and user instructions,
connections per request, UDP datagrams out per request (box-wide, a reading), the arm's cycles per request
and the busiest worker's share range. `g1-proto`: HTTP/3 against HTTP/2 over TLS and the GSO writer, per
request. `g2s-resume` (labelled `g2-resume`): per QUIC connection, (`h3r` - `h3-ka`) x 10, with the v1.40.2
session-ticket default and with the guard on. The data's own `README.md` is `$D/http3/README.md`.

### Per-run summaries

Every run directory has the harness's `summary.md`; `python3 bin/epl report RUN_DIR/results.json`
writes it again from `results.json` (checked on one run of every study: byte for byte as published).

## Run a study again

1. Build or fetch the binaries the configs pin (`bins.json` in the example directory, or the official
   release asset at `~/epl/bin/envoy-1.40.2`), Nighthawk, and for track C the ext_proc service
   (`tools/extproc/build.sh`). For the code-layout arms: [`tools/code-layout`](../tools/code-layout).
2. Adapt the box description to your machine (`cpus`, `perf`, client binary; the `bench-x86_64/`
   directories and `box.json` files) and write the configs with the example's `make.py`.
3. On the bench box, idle: the example's `chain-*.sh` runs the session (smokes, evidence, runs). Or by
   hand: `python3 bin/epl run CONFIG --out RUN_DIR` for the smoke, `python3 bin/epl evidence-check CONFIG
   SMOKE_DIR --freeze FROZEN.json`, then `python3 bin/epl run FROZEN.json --out RUN_DIR`.
4. Render the tables with the commands above, pointed at your run directories.

`python3 bin/epl selftest` runs the harness's offline tests (no box needed).

## Harness commits

The records name the harness commit that was measured (`metadata.harness`). Those commits were made on
working branches that are not published; the published history carries their code in the commits listed
in [`docs/wave-data/harness-commit-map.md`](wave-data/harness-commit-map.md), with the wording changes
listed there.
