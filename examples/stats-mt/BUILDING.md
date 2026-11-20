# Building the Envoy arms of the stats study

Most of the stats study runs the official Envoy v1.40.2 release binary and needs no build. Four
parts use builds of our own. This file gives their build options as recorded when they were built,
and says what was not recorded.

The source of each arm is a tag on the fork `https://github.com/We-Amp/envoy` (**PLANNED** until
the tags exist). The published commits are a cleaned copy of the commits that were measured; the
configs, binary names and raw results name the measured ones.
[`docs/stats-data/envoy-commit-map.md`](../../docs/stats-data/envoy-commit-map.md) maps one to the
other and states how they differ (commit messages, and five comment lines in two test-only files).

| Arm (name in the data) | Measured commit | Published tag |
|---|---|---|
| upstream base (`main`, `base`) | `5e1439980a` (upstream `main`) | `stats-2026-11/base` |
| sink fix (`top`) | `3c9cce2f2c` | `stats-2026-11/sink-fix` |
| benchmarks on the sink fix (`fix`) | `d2f2238974` | `stats-2026-11/bench-fix` |
| relaxed ordering (`fix-relaxed`) | `e74e595e3c` | `stats-2026-11/bench-fix-relaxed` |
| relaxed ordering plus test-before-set (`fix-relaxed-p1`) | `f8bd66d7e7` | `stats-2026-11/bench-fix-relaxed-p1` |
| source of the Arm atomics pair (`fix-lse`, `fix-llsc`) | `964d72f7a6` | `stats-2026-11/bench-lse-source` |

## Toolchain

- Bazel 9.3.2 (the tree's `.bazelversion`, through bazelisk).
- Envoy's default hermetic toolchain: clang 22.1.8 with libc++. No `--config` beyond the tree's
  default `.bazelrc`.
- x86-64 builds were made on another x86-64 machine than the one measured, arm64 builds on the Arm VM
  itself.
- The Bazel server was stopped before any measurement (`bazel shutdown`).

## The proxy (run M-fix: upstream base against the sink fix)

Recorded:

```
bazel build -c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib \
    //source/exe:envoy-static.stripped
```

Both binaries of the comparison were built this way, so the options are not part of what was
measured; only the source differs.

## The benchmark binaries (microbenchmarks, round 5)

Per arm (`fix`, `fix-relaxed`, `fix-relaxed-p1`). Recorded as a command line for arm64 (the build
script of the Arm VM has it); for x86-64 the build notes say "`-c opt` with the release options", which
are the options of the proxy build above, and the literal command line was not kept:

```
bazel build -c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib \
    //test/common/stats:atomic_model_benchmark //test/common/stats:stat_update_benchmark \
    //test/common/stats:histogram_record_benchmark //test/server:server_stats_flush_contended_benchmark
```

The targets are test-only. `atomic_model_benchmark` contains no Envoy stat code, so it ran from the
`fix` build only. On the Arm VM the four `*_benchmark_test` targets were run with the same options
on the `fix` arm before the builds (4 of 4 passed). The arms differ in source only, so here too the
options are not part of what was measured.

## The Arm atomics pair (LSE against LL/SC)

Here the options are the experiment: one source, built twice for arm64, each variant in its own
Bazel output base.

| Variant | Options, as recorded | Built |
|---|---|---|
| `fix-lse` | `-c opt --jobs=16 --copt=-march=armv8-a+lse --copt=-mno-outline-atomics` | yes |
| `fix-llsc` | `-c opt --jobs=16 --copt=-march=armv8-a --copt=-mno-outline-atomics` | yes |
| outline atomics (`-moutline-atomics`, the form of the official release binaries) | | **never built** |

```
bazel --output_base=$HOME/ob-lse  build -c opt --jobs=16 --copt=-march=armv8-a+lse --copt=-mno-outline-atomics \
    //test/common/stats:atomic_model_benchmark //test/common/stats:stat_update_benchmark
bazel --output_base=$HOME/ob-llsc build -c opt --jobs=16 --copt=-march=armv8-a --copt=-mno-outline-atomics \
    //test/common/stats:atomic_model_benchmark //test/common/stats:stat_update_benchmark
```

Not recorded for the pair: whether the `--stripopt` and `--linkopt` options of the other builds
were also passed. The build script of that session has the lines above without them, and no log
says otherwise. They affect symbols and debug sections, not generated code.

The two flag sets are in no file a run writes. They are kept in `build-record.txt`, in the data
asset `stats-2026-11-data-arm-lse-llsc.tar.gz` (unpacked: `data/stats/arm-lse-llsc/build-record.txt`),
with the sha256 of the four binaries.

### Checking what the compiler emitted

Do this before running. The toolchain's `llvm-objdump` is under the output base's `external/`
directory:

```
OBJDUMP=$(find "$(bazel --output_base=$HOME/ob-lse info output_base)/external" -path '*bin/llvm-objdump' | head -1)
$OBJDUMP -d -C --no-show-raw-insn BINARY | awk '
  /^[0-9a-f]+ <.*>:$/ { f = ($0 ~ /CounterImpl|GaugeImpl|PrimitiveCounter|PrimitiveGauge|timedLoop/) }
  f && /\t(ldxr|ldaxr|stxr|stlxr)[bh]?\t/ { llsc++ }
  f && /\t(ldadd|ldaddal|ldaddl|ldadda|swp|swpal|swpl|ldset|ldsetal|ldsetl|ldsetb|ldsetalb|ldsetlb|cas|casal)[a-z]*\t/ { lse++ }
  f && /bl\t.*__aarch64_(ldadd|swp|ldset|cas)/ { outline++ }
  END { printf "llsc=%d lse=%d outline=%d\n", llsc, lse, outline }'
```

It counts, in the stat and model increment paths, exclusive-pair instructions, LSE instructions and
calls of the out-of-line helpers. Ours: `fix-llsc` 34 (`atomic_model_benchmark`) and 54
(`stat_update_benchmark`) exclusive-pair sites, no LSE instruction, no helper call; `fix-lse` 14 and
24 LSE sites, no exclusive pair, no helper call. The benchmark also prints `atomics=lse` or
`atomics=base` in its label, and the runner refuses an arm whose label is not the expected one.

## What a rebuild cannot match

- The sha256 of a binary. Envoy embeds the source revision, and the toolchain and build host leave
  traces. The configs pin the hashes of our binaries (`expected_sha256`, from
  `examples/stats-mt/boxes/sha256/*.txt`) and `micro.py check` refuses others. Put the hashes of
  your builds into that file, one line per binary in the form `<sha256>  <target>-<arm>-<commit>`,
  and write the configs again with `make.py`.
- The commit id. A build from a published tag has the published commit's id, the data has the
  measured one. The mapping file pairs them.

## Running the benchmarks

The benchmarks read their environment: `STATS_BENCH_CPUS` (the CPU list threads are pinned to),
`STATS_BENCH_WARMUP` and `STATS_BENCH_SECONDS` (the windows), `STATS_BENCH_THREADS` and
`STATS_BENCH_HAMMERS` (the thread counts). `examples/stats-mt/micro.py` sets them from the config;
see [`docs/stats-study.md`](../../docs/stats-study.md), "Microbenchmarks".
