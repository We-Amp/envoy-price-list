# The wave studies: how to run them again

Waves 1 to 8 of the price list, and the code-layout work of waves 2, 5 and 6: what each study needs to be
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
| Mitigations | 5 | the kernel's CPU-vulnerability mitigations across three boots; the prctl speculation arms; TCP_DEFER_ACCEPT against idle states | [`examples/wave5h`](../examples/wave5h) | `mitigations` (third release) |
| Arm code layout, cloud VM | 5 | PGO + ThinLTO (and `-mcpu`) on arm64, Neoverse V2 class VM; its ordering-file figure is held (no file control) | [`examples/wave5i`](../examples/wave5i), [`tools/code-layout/arm`](../tools/code-layout/arm) | `arm-vm-layout` (third release) |
| Arm code layout, bare metal | 6 | the same plus AutoFDO and BOLT from SPE profiles, with a file control, Neoverse N3 | [`examples/wave6j`](../examples/wave6j), [`tools/code-layout/arm`](../tools/code-layout/arm) | `arm-metal-layout` (third release) |
| Mitigations, cloud VM | 6 | the mitigation price on a current x86 CPU in a cloud VM, four boots | [`examples/wave6k`](../examples/wave6k) | `mitigations-cloud` (third release) |
| Second hop | 7 | a second Envoy hop: HTTP against a TCP relay, Unix sockets between hops and to the origin; a relayed small message | [`examples/wave7s1`](../examples/wave7s1) | `second-hop` (fourth release) |
| Bodies and streams | 7 | chunked bodies against the same bytes with a length, streamed events, a 32 KiB buffer limit, HTTP/3 at 0 B and 4 KB | [`examples/wave7s2`](../examples/wave7s2), [`tools/streamorigin`](../tools/streamorigin) | `bodies-streams` (fourth release) |
| Feature stack | 7 | seven common features together against the lean config, with and without a statsd sink; ten inert filters; idle timers | [`examples/wave7s3`](../examples/wave7s3) | `feature-stack` (fourth release) |
| Tracing and tests profile | 7 | a deferred OpenTelemetry span at 0% sampling; PGO + ThinLTO trained on Envoy's own tests | [`examples/wave7s4`](../examples/wave7s4) | `tracing-tests-profile` (fourth release) |
| Integration-tests profile | 7 | PGO + ThinLTO trained on the integration tests alone | [`examples/wave7s4b`](../examples/wave7s4b) | `tests-profile-integration` (fourth release) |
| Relay syscalls | 7 | an experiment build without two empty kernel calls per relayed message | [`examples/wave7s5`](../examples/wave7s5) | `relay-syscalls` (fourth release) |
| Chunked copy | 8 | an HTTP/1 chunked body passed as fragments instead of copied | [`examples/wave8w1`](../examples/wave8w1) | `chunked-copy` (fourth release) |
| HTTP/3 receive path | 8 | two QUIC receive commits (stop guard, buffer reuse); server-side retransmission counts | [`examples/wave8w2`](../examples/wave8w2), [`examples/wave8tail`](../examples/wave8tail) | `http3-receive` (fourth release) |

Each example directory has a README with the conditions of its runs (box, CPUs, binaries, shapes,
rates, rounds, order). This page has what is common and the commands.

Envoy patch sources: the `v2` statsd batching build of the statsd-batching study is tag
`statsd-batch-2026-11/v2` of https://github.com/We-Amp/envoy (branch `statsd-batch/v2`, commits
`77fdeb8484` and `ee71e0583f`). The first batching build (`7979fa6063`, superseded by v2) is tag
`statsd-batch-2026-11/v1` (branch `candidates/statsd-batch-v1`) of the same repository. The source of the
header-validation ceiling build (`af3172d385`, measurement only, result dropped) is not published. The code-layout arms are builds of tag v1.40.2 (`tools/code-layout`).
The relay syscall experiment of wave 7 is tag `relay-syscalls-2026-11/v1` of the same repository (an
experiment, not a proposal); the QUIC receive-buffer reuse commit of wave 8 is branch
`candidates/quic-udp-reuse`. The sources of the other wave 7 and 8 builds (the deferred span, the
tests-trained profiles, the chunked fragments, the QUIC stop guard) are not published; their sha256 are in
the example directories' `bins.json`.

## Get the data first

The raw records (about 2.3 GB unpacked) are not in git. They are assets of four releases, one archive
per study: tag `waves-2026-11` (waves 1 to 3 and the code-layout work), tag `waves-2026-11b` (wave 4,
HTTP/3), tag `waves-2026-11c` (waves 5 and 6) and tag `waves-2026-11d` (waves 7 and 8):

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
against the manifests in `data/`. `--from DIR` takes archives you already have; `--verify` checks the
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

### Mitigations (`mitigations`)

```
M=$D/mitigations
( cd $M && python3 ../../../examples/wave5h/table.py cross A B C --json cross.json > cross.md &&
  python3 ../../../examples/wave5h/table.py defer H0 --json H0-defer.json > H0-defer.md )
python3 examples/wave5h/table.py block $M/A        # and B, C: the same-boot rows of one block (printed)
```

`cross`: per run and shape the level of each boot (mean over rounds of the per-round mean of 100 ln(cycles
per request) over the A/A pair), P = (A + C)/2 - B, the price of the boot-time mitigations ("on minus off"),
A - C as the boot-to-boot floor, user instructions per request across the boots, and the verdicts by the
rules fixed before the runs. `defer`: the median-latency effect of `TCP_DEFER_ACCEPT` against `c1` with
default idle states and with C1 only on Envoy's CPUs, their difference and the verdict. `block`: the A/A of
every run and shape, `c1 - ka` per connection and, in C, `ssbd` and `ibp` against `base`. The boot records are
`bootstate-*.json` (written by `examples/wave5h/bootstate.py record`).

### Mitigations, cloud VM (`mitigations-cloud`)

```
K=$D/mitigations-cloud
( cd $K && python3 ../../../examples/wave5h/table.py cross A B C --json cross-plain-ABC.json > cross-plain-ABC.md &&
  python3 ../../../examples/wave5h/table.py cross A B C --pl-off D --json cross.json > cross-D-for-B-hpl.md )
```

The same tables as `mitigations`: `cross-plain-ABC` as the blocks were planned (B's `h-pl` A/A failed),
and with block D's `h-pl` in place of B's. On this VM the clock moved between blocks (cycles over task-clock
per leg, in `legs.jsonl`); read the levels with it.

### Arm code layout, cloud VM (`arm-vm-layout`)

```
python3 examples/wave5i/analysis/analyse_w5i.py $D/arm-vm-layout/epl/runs/wave5i/w5i $D/arm-vm-layout/analysis-w5i.md
```

Per shape: cycles (user + kernel) per response against `official` (the A/A, `order`, `pgolto`, `pgolto-v2`),
with the t and widened intervals as percent changes, and the decision rules fixed before the run. **The
`order` figures of this run are held, not confirmed:** the control (the same code in a separate file, where no
effect is expected) was not run on this host; on bare metal the control was null and the ordering file gave
4-7%. They stay in the data; we do not quote them as a result.

### Arm code layout, bare metal (`arm-metal-layout`)

```
python3 examples/wave6j/analysis/analyse_w6j.py $D/arm-metal-layout/epl/runs/wave6j/w6j $D/arm-metal-layout/analysis-w6j.md
```

Per shape: the file control (`opt-file` against `official`), the layout row, `order`, `autofdo`, `pgolto`,
`bolt`, the AutoFDO share of the PGO gain, and the decision rules fixed before the run. The arms' builds:
[`tools/code-layout/arm/README.md`](../tools/code-layout/arm/README.md).

### Second hop (`second-hop`)

```
S=$D/second-hop
python3 examples/wave7s1/table.py $S/wave7s1/s1a-hop --json $S/s1a-table.json > $S/s1a-table.md
python3 examples/wave7s1/table.py $S/wave7s1/s1b-relay --json $S/s1b-table.json > $S/s1b-table.md
python3 examples/wave7s1/mech_table.py $S/wave7s1/mech --json $S/mech-table.json > $S/mech-table.md
```

`s1a-hop`: cycles (user + kernel, both Envoys) per request of the pair, the second hop as HTTP against a TCP
relay, with mTLS on the hop, and with Unix sockets between the hops and to the origin, each against its base with
its A/A. `s1b-relay`: one Envoy as a TCP relay of small messages. `mech-table`: syscalls per request or message
and the kernel call-graph shares of the non-scored mechanism legs.

### Bodies and streams (`bodies-streams`)

```
B=$D/bodies-streams
for r in s2a-chunked s2b-stream s2c-buf s2d-h3; do
  python3 examples/wave7s2/table.py $B/wave7s2/$r --json $B/${r%%-*}-table.json > $B/${r%%-*}-table.md; done
python3 examples/wave7s2/mech_table.py $B/wave7s2/mech --json $B/mech-table.json > $B/mech-table.md
python3 examples/wave7s2/mech_gates.py $B/wave7s2/mech $B/mech-table.json --json $B/mech-gates.json > $B/mech-gates.md
```

Chunked bodies against content-length bodies in the same writes (the control for the copy), streamed
events, the buffer limit and HTTP/3 against HTTP/2 over TLS. Three shapes failed their A/A; their rows are
decided only by the three-times rule (the table says which). `mech-gates`: the mechanism gates (events,
buffer limit, the HTTP/3 receive path, the chunked copy).

### Feature stack (`feature-stack`)

```
F=$D/feature-stack
for r in s3a-stack s3b-chain; do k=${r%%-*}
  python3 examples/wave7s3/table.py $F/wave7s3/$r --json $F/$k-table.json > $F/$k-table.md
  python3 examples/wave7s3/evidence_summary.py $F/wave7s3/$r --json $F/$k-evidence.json > $F/$k-evidence.md; done
python3 examples/wave7s3/mech_table.py $F/wave7s3/mech --json $F/mech-table.json > $F/mech-table.md
```

`s3a`: the stack and the lean config against the bare config, and the stack against the sum of the published
single rows (the compounding claim, with its band fixed before the run). `s3b`: ten inert filters, the same with
`disabled: true`, and the idle timers off; the kill lines.

### Tracing and tests profile (`tracing-tests-profile`)

```
T=$D/tracing-tests-profile
for r in s4a-otel s4b-pgo; do k=${r%%-*}
  python3 examples/wave7s4/table.py $T/wave7s4/$r --json $T/$k-table.json > $T/$k-table.md
  python3 examples/wave7s4/evidence_summary.py $T/wave7s4/$r --json $T/$k-evidence.json > $T/$k-evidence.md; done
python3 examples/wave7s4/extra.py $T/wave7s4/s4a-otel > $T/s4a-extra.md
```

`s4a`: tracing at 0% sampling with the deferred span against no tracing and against the official binary's
tracer; the share of the unsampled cost it removes; both build controls. `s4b`: the profile trained on Envoy's
tests against the trainer profile, as the kept share of the trainer's gain. `s4a-extra.md`: supplementary
readings of the same run (analysis only).

### Integration-tests profile (`tests-profile-integration`)

```
I=$D/tests-profile-integration
python3 examples/wave7s4b/table.py $I/wave7s4b/it-pgo --s4 $D/tracing-tests-profile/s4b-table.json \
    --json $I/it-pgo-table.json > $I/it-pgo-table.md
python3 examples/wave7s4/evidence_summary.py $I/wave7s4b/it-pgo --json $I/it-pgo-evidence.json > $I/it-pgo-evidence.md
```

The kept share of the profile from the integration tests alone; it reads the `s4b` table of
`tracing-tests-profile` for the trainer's gain (fetch both archives).

### Relay syscalls (`relay-syscalls`)

```
R=$D/relay-syscalls
python3 examples/wave7s5/table.py $R/wave7s5 --json $R/s5-table.json > $R/s5-table.md
python3 examples/wave7s5/mech_table.py $R/wave7s5/mech --json $R/s5-mech.json > $R/s5-mech.md
python3 examples/wave7s5/evidence_summary.py $R/wave7s5/relay-1 $R/wave7s5/relay-2 $R/wave7s5/http-1 \
    $R/wave7s5/http-2 --json $R/s5-evidence.json > $R/s5-evidence.md
```

The experiment build with both guards on against both off (inside one binary) and against the official binary,
each guard alone, on the 64-byte relay and on 4 KB HTTP; the relay's same-build check missed its floor, so its rows
are decided by the three-times rule. `s5-mech`: syscalls per relayed message and send calls under load.

### Chunked copy (`chunked-copy`)

```
C=$D/chunked-copy
python3 examples/wave8w1/table.py $C/w1/wave8w1 --json $C/w1-table.json > $C/w1-table.md
python3 examples/wave8w1/evidence_summary.py $C/w1/wave8w1 --json $C/w1-evidence.json > $C/w1-evidence.md
```

The fragment build's guard on against off at 1 MiB and 64 KiB, an nginx origin sending chunked, and the rider
rows; user and kernel cycles beside every row; writev calls and iovecs per MiB from the traced legs. The patch is
killed by the 3% line.

### HTTP/3 receive path (`http3-receive`)

```
H=$D/http3-receive
python3 examples/wave8w2/table.py $H/wave8w2 --json $H/w2-table.json > $H/w2-table.md
python3 examples/wave8w2/mech_table.py $H/wave8w2 --json $H/w2-mech.json > $H/w2-mech.md
python3 examples/wave8w2/evidence_summary.py $H/wave8w2/s-1 $H/wave8w2/s-2 --json $H/w2-evidence.json > $H/w2-evidence.md
python3 examples/wave8w1/tail_check.py $H/tail-w8-1/wave8w1/tail --json $H/tail-w8-1/tail-table.json > $H/tail-w8-1/tail-table.md
python3 examples/wave8tail/tail_check.py $H/tail-w8-3/wave8w3/tail --json $H/tail-w8-3/tail-table.json > $H/tail-w8-3/tail-table.md
```

`w2`: both commits against the old receive loop, the stop guard alone, at low load; the same-build check and the
HTTP/3 anchor. `w2-mech`: `recvmmsg` calls per request and the empty share, by arm. The two tails (Exploratory,
unscored for CPU): server-side QUIC retransmissions per 100,000 packets sent, by arm, and in `tail-w8-3` where the
stop arm's excess falls in the run and row C4 (the buffer-reuse commit alone). `visit1/` holds the first visit,
which stopped at its signature gate; nothing in it is scored.

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
