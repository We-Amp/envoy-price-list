# The stats study: how to run it again

What each part of the stats study needs to be reproduced: the commands, the Envoy binary or patch,
how the tables are rendered, how the own-build arms are built and what hardware it takes.

## Get the data first

The raw records of our runs (about 320 MB) are not in git. They are assets of the release of tag
`stats-2026-11`, one archive per study, and every command below that reads our data starts from a
filled `data/stats/`:

```
python3 tools/fetch-stats-data.py                # every study
python3 tools/fetch-stats-data.py contention     # or only the studies you name
python3 tools/fetch-stats-data.py --list         # the studies, their sizes and asset names
```

The script downloads `stats-2026-11-data-<study>.tar.gz` from
`https://github.com/We-Amp/envoy-price-list/releases/download/stats-2026-11/` (**PLANNED**), checks
each archive against `data/stats-data.SHA256SUMS`, unpacks into `data/stats/` (ignored by git) and
checks every file against `data/stats-data.manifest`. `--from DIR` takes archives you already have.
`--verify` checks the unpacked tree again, for example after rendering tables into it.

What is in the archives, with the conditions that belong to each run and the commands that render
every table again: [`docs/stats-data/README.md`](stats-data/README.md) (the same file is at the top
of every archive). What was changed in the raw records before publication:
[`docs/stats-data/WHAT-WAS-CHANGED.md`](stats-data/WHAT-WAS-CHANGED.md). The rendered tables and the
text outputs of the analyses are small and are also in git: [`docs/stats-tables/`](stats-tables/),
at the paths they have inside the archives.

The data directories of the earlier studies (`data/features/`, `data/route-table/` and the others
listed in `data/README.md`) are in git as before.

Links marked **PLANNED** name tags that are created when this branch is published; until then they
do not resolve.

- Harness and data: tag `stats-2026-11` on this repository and its release (**PLANNED**).
- Envoy patches: tags on the fork `https://github.com/We-Amp/envoy` (**PLANNED**; table below).

## What you need

Common to every end-to-end run:

- Linux on the machine under test, `perf` able to count hardware events for the Envoy process
  (see the README's requirements), `taskset`, Python 3.8 or later.
- Nighthawk (`nighthawk_client`) as the load generator, and Docker for the origin (an nginx
  container) and, in the sink runs, the OpenTelemetry collector (`otel/opentelemetry-collector:0.120.0`,
  digest in the box description).
- The official Envoy v1.40.2 release binary. The configs pin its sha256 and refuse another binary.
- A box description of your machine. Ours are `examples/stats-flush/boxes/bench-x86_64.json` and
  `examples/stats-mt/boxes/*.json`: CPU sets, binary paths, rates. Copy one, edit it, and write the
  configs with `make.py --box YOUR_BOX.json`. `epl portability-check` checks that a box's configs
  carry no literal of another box. `examples/stats-flush/example-aarch64/` is a second box written
  to show what changes.

Hardware:

| Study | What it needs |
|---|---|
| Sink runs M, W, S; flush latency L | 4 cores for Envoy's workers with their SMT siblings idle, one more core for the main thread in run L, about 20 cores for client, origin, sinks and probe on another socket or far from the proxy; 125 GB of memory was enough for the 3M-stat probe of the calibration and for 1M stats in the runs. Root for one sysctl: the session raises `net.core.rmem_max` and restores it (in our session every sink socket was granted a 512 MiB receive buffer) |
| Multi-worker U, U-hi, contention R1 | two sockets with at least 14 cores each to repeat the 14-worker one-socket, 14-worker split and 28-worker rungs; SMT siblings of the proxy's cores idle; about ten further cores for client and origin. HITM evidence legs need `perf` events for HITM loads (Intel) |
| Microbenchmarks | any machine with one core per benchmark thread and an idle sibling; the runner needs `perf` counters (PMU passed through on a VM) |
| Arm experiments | an arm64 machine with LSE (ARMv8.1 or later); 16 cores were used |

The gates do not move with the hardware. A leg in which other tasks used more than 0.05 CPU on the
proxy's cores, or in which the client lacked headroom, is invalid on any machine.

## Envoy binaries and patches

| Used by | Binary | Source | Published as |
|---|---|---|---|
| Every end-to-end run on x86 (M, W, S, L, U, U-hi, R1) | official v1.40.2 release binary | upstream release asset | upstream |
| Arm codegen run, arm `official` | official v1.40.2 release binary, arm64 | upstream release asset | upstream |
| Arm codegen run, arm `dev` | the binary of the official dev image of `main` at `5e1439980a` (linux/arm64) | upstream image | upstream |
| Run M-fix, arm `main` | own build of upstream `main` at `5e1439980a` | upstream commit | tag `stats-2026-11/base` (**PLANNED**) |
| Run M-fix, arm `top` | own build of the sink stack at `3c9cce2f2c` (the approach of the upstream pull requests 43958 and 44285 by Joshua Marantz, ported to `main`) | fork | tag `stats-2026-11/sink-fix` (**PLANNED**) |
| Microbenchmarks round 5, arm `fix` | benchmark overlay on the sink stack, `d2f2238974` | fork | tag `stats-2026-11/bench-fix` (**PLANNED**) |
| arm `fix-relaxed` | `fix` plus relaxed memory ordering on the stat updates, `e74e595e3c` | fork | tag `stats-2026-11/bench-fix-relaxed` (**PLANNED**) |
| arm `fix-relaxed-p1` | `fix-relaxed` plus the test-before-set of the used flag, `f8bd66d7e7` | fork | tag `stats-2026-11/bench-fix-relaxed-p1` (**PLANNED**) |
| Arm LSE against LL/SC | one source, `964d72f7a6` (the `fix` arm with time-based batching), built twice | fork | tag `stats-2026-11/bench-lse-source` (**PLANNED**) |
| Microbenchmarks round 4 (flush overlapping updates, exploratory) | `fix` `7d877d4424`, `fix-relaxed` `f5eae01224`, `fix-relaxed-p1` `2b94594e18`, `base` `3a80b1543c`, `base-relaxed` `e6e0544805`, `base-relaxed-p1` `ba1e983c9d` | fork | **PLANNED** only if those rows are quoted |

The commit ids are the ones the runs measured; the configs and the raw data name the arms by them.
If a published tag points at a commit with another id (a history with reworded messages or comment
lines), the mapping from measured id to published id is listed here when the tags exist, with the
`git diff` between the two trees.

The benchmark targets are test-only: `//test/common/stats:atomic_model_benchmark` (with
`bench_pinning.h`), `//test/common/stats:stat_update_benchmark`,
`//test/common/stats:histogram_record_benchmark` and
`//test/server:server_stats_flush_contended_benchmark`.

### Building the own-build arms

As built for the runs (x86 on a build host, arm64 on the Arm VM):

- Bazel 9.3.2 (the tree's `.bazelversion`, through bazelisk), Envoy's default hermetic toolchain:
  clang 22.1.8 with libc++. No `--config` beyond the tree's default `.bazelrc`.
- The proxy, release-like:

  ```
  bazel build -c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib \
      //source/exe:envoy-static.stripped
  ```

- The four benchmark binaries, per arm, with the same flags:

  ```
  bazel build -c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib \
      //test/common/stats:atomic_model_benchmark //test/common/stats:stat_update_benchmark \
      //test/common/stats:histogram_record_benchmark //test/server:server_stats_flush_contended_benchmark
  ```

  On the Arm VM the four `*_benchmark_test` targets were run with the same flags on the `fix` arm
  before the round-5 builds (4 of 4 passed).
- Stop the Bazel server before measuring (`bazel shutdown`).

The Arm flag pair (one source, `964d72f7a6`, each variant in its own output base):

| Variant | Flags | Built |
|---|---|---|
| `fix-lse` | `-c opt --jobs=16 --copt=-march=armv8-a+lse --copt=-mno-outline-atomics` | yes |
| `fix-llsc` | `-c opt --jobs=16 --copt=-march=armv8-a --copt=-mno-outline-atomics` | yes |
| outline atomics (`-moutline-atomics`, the form of the official release binaries) | | **not built** |

```
bazel --output_base=$HOME/ob-lse  build -c opt --jobs=16 --copt=-march=armv8-a+lse --copt=-mno-outline-atomics \
    //test/common/stats:atomic_model_benchmark //test/common/stats:stat_update_benchmark
bazel --output_base=$HOME/ob-llsc build -c opt --jobs=16 --copt=-march=armv8-a --copt=-mno-outline-atomics \
    //test/common/stats:atomic_model_benchmark //test/common/stats:stat_update_benchmark
```

Check what the compiler emitted before running. The toolchain's `llvm-objdump` is under the output
base's `external/` directory. Count, in the disassembly of the stat and model increment paths,
exclusive-pair instructions (`ldxr`, `ldaxr`, `stxr`, `stlxr`), LSE instructions (`ldadd*`, `swp*`,
`ldset*`, `cas*`) and calls of the outline helpers (`__aarch64_ldadd*` and the like). Ours:
`fix-llsc` 34 and 54 exclusive-pair sites in the two binaries with no LSE and no helper call;
`fix-lse` 14 and 24 LSE sites with no exclusive pair and no helper call
(`arm-lse-llsc/build-record.txt` in the asset `stats-2026-11-data-arm-lse-llsc.tar.gz`). The benchmark also prints `atomics=lse` or
`atomics=base` in its label, and the runner refuses an arm whose label is not the expected one.

Two things a rebuild cannot match:

- The sha256 of a binary. The configs pin the hashes of our binaries (`expected_sha256`, from
  `examples/stats-mt/boxes/sha256/*.txt`) and `micro.py check` refuses others. Put the hashes of
  your builds into that file, one line per binary in the form `<sha256>  <target>-<arm>-<commit>`,
  and write the configs again.
- The compile flags are in no file a run writes. Keep your own build record beside the data, as
  `build-record.txt` does.

## The studies

Paths are relative to the repository root. `RUNS` is where the run directories go (default
`~/epl/runs/stats-flush` and `~/epl/runs/stats-mt/<box>`); `BOX` selects the box description
(default `bench-x86_64`). Every session script prints its progress to `queue.log` in `RUNS`.

### Runs M and W: the flush-cost curve and the workers under load

Envoy: official v1.40.2. Run M: idle legs at 10k, 100k, 300k and 1M stats, arms `flush-off`,
`nosink`, `statsd`. Run W: 100k stats at 5,200 req/s.

```
python3 examples/stats-flush/make.py                    # configs from the box description
examples/stats-flush/run-session.sh calibrate           # step 0: one idle leg per rung, rungs.json
examples/stats-flush/run-session.sh smoke               # one round of every arm, then the check
examples/stats-flush/run-session.sh check
examples/stats-flush/run-session.sh queue               # M (10k, 100k, 1M), W, M at 300k
python3 examples/stats-flush/table.py ~/epl/runs/stats-flush --json tables.json > tables.md
```

Run M-fix (the two own builds; set their paths in the box's `fix_binaries`):

```
examples/stats-flush/run-session.sh mfix
```

Our data: asset `stats-2026-11-data-sink-flush-cost.tar.gz` (unpacked: `data/stats/sink-flush-cost/`); table `docs/stats-tables/sink-flush-cost/tables.md`.

### Run S: statsd, buffered dog_statsd and OTLP

Envoy: official v1.40.2. Needs `rungs.json` from `calibrate`. The OTLP arm at 1M stats needs the
collector's gRPC receive limit raised (`max_recv_msg_size_mib: 64`); with the default 4 MiB the
collector rejects part of every flush and the leg still looks valid. The `s-otlp` steps are that
re-run.

```
examples/stats-flush/run-session.sh s-smoke
examples/stats-flush/run-session.sh s-check
examples/stats-flush/run-session.sh s-queue              # s-100k, s-1m, sw
examples/stats-flush/run-session.sh s-otlp-smoke
examples/stats-flush/run-session.sh s-otlp               # otlp and nosink-20s at 1M
python3 examples/stats-flush/table.py ~/epl/runs/stats-flush > s-tables.md
A=examples/stats-flush/analysis-s
python3 $A/analyze.py ~/epl/runs/stats-flush > analysis.txt
python3 $A/extra.py ~/epl/runs/stats-flush > extra.txt
python3 $A/holm9.py ~/epl/runs/stats-flush > holm9.txt
python3 $A/latency.py ~/epl/runs/stats-flush ~/epl/runs/stats-flush/w > latency.txt
python3 $A/rerun.py ~/epl/runs/stats-flush/s-1m-otlp > rerun.txt
```

The reported figures of run S come from `analysis-s/` (it does not import the harness and needs
`scipy`); `holm9.py` expects the re-run in a directory named `s-1m-otlp-rerun` beside `s-1m`. Our
data: asset `stats-2026-11-data-sink-types.tar.gz` (unpacked: `data/stats/sink-types/`); outputs under `docs/stats-tables/sink-types/`.

### Run L: does a flush delay requests?

Envoy: official v1.40.2, 1M stats, a 10 s flush interval in every arm. Shapes `own` (main thread on
its own core) and `shared` (main thread on a worker's core); arms `nosink`, `statsd`, `otlp`; five
cells, one Latin rotation over the cells. Beside the Nighthawk background load a probe process
(`epl/latprobe.py`) sends open-loop requests on connections whose worker it has identified.

```
examples/stats-flush/run-session.sh lat-smoke
examples/stats-flush/run-session.sh lat-check
examples/stats-flush/run-session.sh lat-queue
python3 examples/stats-flush/lat_table.py ~/epl/runs/stats-flush/lat --json lat-table.json > lat-table.md
A=examples/stats-flush/analysis-l
python3 $A/perleg.py ~/epl/runs/stats-flush/lat OUT_DIR
python3 $A/analyze.py ~/epl/runs/stats-flush/lat OUT_DIR > analysis.txt
python3 $A/extra.py ~/epl/runs/stats-flush/lat OUT_DIR > extra.txt
python3 $A/review_fixes.py ~/epl/runs/stats-flush/lat OUT_DIR > review-fixes.txt
```

`lat-queue` refuses to start without a recorded `lat-check` of the same harness and config. The
reported figures come from `analysis-l/` (`numpy`, `scipy`). Our data: asset `stats-2026-11-data-flush-latency.tar.gz` (unpacked: `data/stats/flush-latency/`);
outputs under `docs/stats-tables/flush-latency/`.

### Run U: the store stats at 1 to 28 workers

Envoy: official v1.40.2. Arms `base`, `stats-reject` (`stats_config` with `reject_all: true`: the
store stats become null objects, the per-host stats stay) and `base-A2` (a second copy of `base`).
Rungs 1, 4, 14 on one socket, 14 split over two sockets, 28 workers; 1,000 req/s per worker; 15
rounds. Removing the store stats is a lower bound on the cost of all stat updates on the request
path, not a total.

```
python3 examples/stats-mt/make.py --rates RATES.json     # {"bench-x86_64": {"r_star": 1000, "k": 16}}
examples/stats-mt/run-u.sh calibrate
examples/stats-mt/run-u.sh smoke
examples/stats-mt/run-u.sh check
examples/stats-mt/run-u.sh queue                         # run U, then the HITM evidence legs
python3 examples/stats-mt/u_table.py ~/epl/runs/stats-mt/bench-x86_64/u \
    --hitm ~/epl/runs/stats-mt/bench-x86_64/u-hitm --json u.json > u.md
python3 examples/stats-mt/analysis-u/extras.py ~/epl/runs/stats-mt/bench-x86_64 > extras.txt
```

`extras.py` prints the figures quoted beside the table: the price as a share of the base level,
the instructions removed, the differences between rungs and the HITM totals. Our data:
asset `stats-2026-11-data-multi-worker.tar.gz` (unpacked: `data/stats/multi-worker/`); table `docs/stats-tables/multi-worker/u.md`.

### Run U-hi: the same at 1,500 req/s per worker

Envoy: official v1.40.2, same arms; rungs 14 one socket, 14 split, 28.

```
examples/stats-mt/run-u.sh hi-calibrate
examples/stats-mt/run-u.sh hi-smoke
examples/stats-mt/run-u.sh hi-queue
python3 examples/stats-mt/u_table.py ~/epl/runs/stats-mt/bench-x86_64/u-hi --json u-hi.json > u-hi.md
A=examples/stats-mt/analysis-u-hi
python3 $A/analyze.py U_HI_DIR U_DIR OUT_DIR STOPPED_ATTEMPT_DIR
python3 $A/verify_review.py U_HI_DIR U_DIR OUT_DIR STOPPED_ATTEMPT_DIR
```

`analyze.py` expects the run in `U_HI_DIR/u-hi-1500` and its smoke in `U_HI_DIR/smoke-u-hi-1500`,
as in the asset `stats-2026-11-data-multi-worker-high-load.tar.gz` (unpacked: `data/stats/multi-worker-high-load/`); it also reads run U and the leg records of our stopped
first attempt for one comparison. The reported figures come from this analysis.

### Run R1 ("dose"): shared against per-connection counters

Envoy: official v1.40.2, configuration only. The stats access logger
(`envoy.extensions.access_loggers.stats.v3.Config`) on the HTTP connection manager adds K counter
increments per request. The counters carry a tag: `%DOWNSTREAM_LOCAL_PORT%` gives one set shared by
all workers (arms `shared-K`), `%DOWNSTREAM_REMOTE_PORT%` one set per connection (arms `own-K`). The
listener binds the wildcard address. Cells: 14 workers on one socket, 14 split, 28; 1,500 req/s per
worker; 20 s windows.

```
examples/stats-mt/run-u.sh dose-pilot                    # 17 legs; dose_pilot.py recommends K and connections
python3 examples/stats-mt/make.py --rates RATES.json     # with the choice under the box's dose.rates_key
examples/stats-mt/run-u.sh dose-smoke
examples/stats-mt/run-u.sh dose-check
examples/stats-mt/run-u.sh dose-queue                    # the run, then the evidence legs, then the tables
python3 examples/stats-mt/u_table.py DOSE_DIR --evidence DOSE_EVIDENCE_DIR --json dose.table.json > dose.md
for s in cells aa_and_split levels_and_hot evidence; do
  python3 examples/stats-mt/analysis-r1/$s.py CONTENTION_DIR > $s.txt
done
```

Our pilot record was not clean by its own rules, so K and the connections per worker were chosen by
hand and recorded (`dose-decision-2.json`); `dose-check` accepts such a record only when the pilot's
own checks support it. `analysis-r1/` expects the directory names of the asset `stats-2026-11-data-contention.tar.gz` (unpacked: `data/stats/contention/`)
(`dose-2`, `dose-evidence-2`). Our run is a short one (6 rounds instead of 15).

### Microbenchmarks

Envoy: the own builds of the table above. Threads are pinned one per core with idle siblings; each
benchmark measures a 1 s window after a 0.2 s warm-up, inside one Google Benchmark iteration; 5
interleaved rounds of 5 repetitions.

```
python3 examples/stats-mt/micro.py check examples/stats-mt/<box>/micro.json     # binaries present, sha256 as pinned
examples/stats-mt/run-u.sh micro-smoke
examples/stats-mt/run-u.sh micro
python3 examples/stats-mt/micro.py table OUT_DIR --json table.json > micro.md
python3 examples/stats-mt/micro_reeval.py OUT --data NAME DATA_DIR CFG_JSON     # post hoc, no new runs
```

The Arm LSE against LL/SC run uses `examples/stats-mt/arm-vm/micro-lse.json` with the same runner
(`micro.py smoke`, then `micro.py run`), and
`python3 examples/stats-mt/analysis-lse/analyse.py DATA_DIR OUT_DIR` for its tables. Our run used
that config with a VM-local bound on involuntary context switches, kept as
`arm-lse-llsc/micro-lse.json.vm-local-floor25` in the asset `stats-2026-11-data-arm-lse-llsc.tar.gz`.

The round-4 rows (a flush while workers update stats) were run and tabulated with the harness at
commit `c4f709b`; the current `micro.py` runs the round-5 set only.

Our data: the assets `stats-2026-11-data-microbenchmarks.tar.gz`,
`stats-2026-11-data-microbenchmarks-flush-overlap.tar.gz` and `stats-2026-11-data-arm-lse-llsc.tar.gz`
(unpacked under `data/stats/` in directories of the same names); tables under `docs/stats-tables/`.

### Arm codegen, end to end

Envoy: the official v1.40.2 arm64 release binary against the binary of the official dev image of
`main` at `5e1439980a`, each with its own `reject_all` arm, and a second copy of the release as A/A.
Rungs 4 and 12 workers, 1,000 req/s per worker, 20 rounds.

```
examples/stats-mt/run-u.sh codegen-smoke                 # the atomics check of both binaries, one round
examples/stats-mt/run-u.sh codegen
python3 examples/stats-mt/codegen_table.py RUN_DIR --json codegen.json > codegen.md
```

Our data: asset `stats-2026-11-data-arm-codegen.tar.gz` (unpacked: `data/stats/arm-codegen/`). Where the arm64 builds changed
form: [`docs/stats-data/arm-atomics-bisect.md`](stats-data/arm-atomics-bisect.md) (a table and the
method; it has no raw files).

## Publishing a results tree

`epl scrub RUN_DIR` rewrites home directory paths in a run's text files. Before a tree is published
run `epl scrub RUN_DIR --publish` as well: it covers console captures and other suffixes, gzip
members, the `host_name` and `executable` fields of Google Benchmark's output and cloud VM names;
`--check` is the gate (see `epl/pubscrub.py`).

Raw records do not go into git. `python3 tools/build-stats-data.py TREE OUT_DIR` builds the release
assets from a scrubbed tree (one directory per study): it refuses a tree that `epl scrub --check`
would still change, writes one reproducible `tar.gz` per study (the same tree gives the same bytes)
with `SHA256SUMS`, and rewrites `data/stats-data.manifest`, `data/stats-data.SHA256SUMS` and
`docs/stats-tables/`. The assets are then uploaded to the release of the tag.
