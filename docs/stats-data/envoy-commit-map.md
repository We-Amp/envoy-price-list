# Envoy source for the stats study: measured commits and published commits

The stats study built Envoy from local commits on top of upstream `main` at
`5e1439980a5ad11e144e596fff589cac13144a82` (2026-11-17, version string `1.41.0-dev`). The raw results, the
harness configs and the binary names identify each build by the commit it was built from ("measured commit").

Those commits are not published. What is published is a cleaned copy of the same source ("published commit"),
on the same base. This file maps one to the other and states exactly how they differ.

## Mapping

| Arm (name in the data) | Measured commit | Published commit | Branch | Tag | Tree difference |
|---|---|---|---|---|---|
| upstream base (`main`, `base`) | `5e1439980a5ad11e144e596fff589cac13144a82` | the same commit (upstream) | upstream `main` | `stats-2026-11/base` | none |
| sink fix (`top`) | `3c9cce2f2c7d9807709f035a2decb691e4f38916` | `de9f64a916608dd2db3070a219545f71618da546` | `stats-study/sink-fix` | `stats-2026-11/sink-fix` | none: the two commits have the same tree, `bf55dd5dcd96eed3230efc1e5422175ef19565c5` |
| benchmarks on the sink fix (`fix`) | `d2f22389745ba76bc56de2d2dac40ec72b9d7441` | `75deb70c33e9f3aa543d6333beedc3b7cf4f0f8a` | `stats-study/bench-fix` | `stats-2026-11/bench-fix` | five comment lines in two test files (below) |
| relaxed ordering (`fix-relaxed`) | `e74e595e3c060adb3b5ed841b0b9e028891bdbc4` | `1d7e497c81e18f937d093e573744b650bfa3ae39` | `stats-study/bench-fix-relaxed` | `stats-2026-11/bench-fix-relaxed` | the same five comment lines |
| relaxed ordering plus test-before-set (`fix-relaxed-p1`) | `f8bd66d7e7bf362287eb66990b68afcb91253505` | `7c693f5a8ed0e6e9c21e817bb12f152891731d23` | `stats-study/bench-fix-relaxed-p1` | `stats-2026-11/bench-fix-relaxed-p1` | the same five comment lines |
| source of the Arm atomics pair (`fix-lse`, `fix-llsc`) | `964d72f7a603ecea7218dcd311bfc8f6db1010ef` | `58a717cd97e40fc78ff1882ecadfd2e645293ea0` | `stats-study/bench-lse-source` | `stats-2026-11/bench-lse-source` | the same five comment lines |

How the published branches relate: `sink-fix` is an ancestor of `bench-fix`; `bench-fix` is an ancestor of
`bench-fix-relaxed` and of `bench-lse-source`; `bench-fix-relaxed` is an ancestor of `bench-fix-relaxed-p1`.

## What differs between a measured and a published commit

1. **History and commit messages.** The measured history had 44 commits. The published history has 31: three
   groups of fix-up commits were combined with the change they fix (16 commits became 3). The messages were
   rewritten to say what was tested and where, and to describe upstream issues and pull requests in words.
   Authors and author dates are unchanged.
2. **Four comment places** (five lines) in two test-only benchmark files, in every arm except the sink fix. They referred to a
   test machine and to a document that are not published. No code,
   build file or other comment differs.

   The published lines read as follows.

   `test/common/stats/bench_pinning.h`, lines 3, 100 and 101, and 560 (594 in the source of the Arm atomics pair):

   ```
   // Shared mechanics for the multi-threaded stats benchmarks.
   // Thread (or worker) counts: one per physical core, so the default spans the measured rungs
   // (x86 VM and Arm VM tops 12 and 15, the x86 server one socket 14 and both sockets 28).
   // Registers the thread counts above with the time-bounded window: one Google Benchmark
   ```

   `test/common/stats/stat_update_speed_test.cc`, line 16:

   ```
   // <primitive gauge inc/dec pairs>:<histogram samples>" (counts come from a running proxy). There
   ```

   That is five changed lines in four places (one sentence spans two lines). The commit messages on the
   published branches call them "four comment lines".

Because the measured commits are not published, a reader cannot repeat the comparison. We made it with
`git diff <measured commit> <published commit>` for each arm before publishing: the output was empty for the
sink fix and was exactly these five lines, in these two files, for each of the other four.

## What a rebuild will and will not reproduce

- A build from a published commit compiles the same source as the measured build. Comments do not reach the
  compiler's output; the embedded revision differs (next point).
- The binaries will not be bit-identical to ours. Envoy embeds the source revision in the binary, and the
  toolchain and build host also leave traces. The harness configs pin our binaries by SHA-256, so a
  reproduction has to pin its own.
- The benchmark outputs and harness configs keep the measured commit ids. Use the table above to find the
  published source for each.

## Which results depend on which arm

| Arm | Study | Results that depend on it |
|---|---|---|
| upstream base and sink fix | Stats sink study, run "M-fix": flush cost with and without the sink fix, own builds, no sink configured | Main-thread run time with the sink fix against the base at about 12,000, 118,000 and 1.18 million stats, and the time saved per flush at the largest size |
| benchmarks on the sink fix | Microbenchmarks, round 5, on an x86 server, an x86 cloud VM and an Arm cloud VM | Cycles per operation of a counter increment, shared against per-thread; the shared-against-spaced ratios; the model variants (one read-modify-write, per-thread cells); the baseline of both comparisons below |
| relaxed ordering | Microbenchmarks, round 5 | Relaxed against sequentially consistent ordering: real counters and primitive counters, `Gauge::set`, the histogram per-sample store; the instruction counts on x86 |
| relaxed ordering plus test-before-set | Microbenchmarks, round 5 | Skipping the used-flag write when the flag is already set: counter increments and gauge sets, shared and spaced |
| source of the Arm atomics pair | Arm atomics flag experiment: one source, two arm64 builds that differ only in compiler flags | Every LSE against load-/store-exclusive ratio: uncontended and shared counters, `Gauge::set`, primitive counters, the model; the instruction counts per operation |

Results that depend on no patch (official release binaries or upstream development images only): the sink
runs on the official release, the flush latency run, the multi-worker runs, the shared against per-connection
counter run, the Arm code generation end-to-end run and the Arm atomics bisect.

## Build options that are part of what was measured

| Arm | Targets | Options, as recorded | Part of the measurement? |
|---|---|---|---|
| upstream base, sink fix | `//source/exe:envoy-static.stripped` | `-c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib`, the default `.bazelrc`, Envoy's hermetic clang 22.1.8, Bazel 9.3.2, x86-64 | No. Both binaries of the comparison were built the same way; only the source differs |
| benchmarks on the sink fix, relaxed ordering, relaxed ordering plus test-before-set | `//test/common/stats:atomic_model_benchmark`, `//test/common/stats:stat_update_benchmark`, `//test/common/stats:histogram_record_benchmark`, `//test/server:server_stats_flush_contended_benchmark` | `-c opt` with the same release options as above, hermetic clang 22.1.8; built for x86-64, and for arm64 on the Arm VM. For x86-64 the literal command line was not kept: the build notes say "`-c opt` with the release options" | No. The arms of a comparison were built the same way on the same host; only the source differs. The Arm binaries of these runs were not disassembled; the Arm atomics pair below is the controlled comparison |
| source of the Arm atomics pair | `//test/common/stats:atomic_model_benchmark`, `//test/common/stats:stat_update_benchmark` | arm64, `-c opt`, hermetic clang 22.1.8, built twice from the same source, each in its own output base: `fix-lse` with `--copt=-march=armv8-a+lse --copt=-mno-outline-atomics`; `fix-llsc` with `--copt=-march=armv8-a --copt=-mno-outline-atomics` | **Yes. The two flag sets are the experiment**; the source is the same for both |

Check of the Arm pair, from the build record: disassembly of the increment paths with `llvm-objdump` showed
14 (`atomic_model`) and 24 (`stat_update`) LSE instructions and no exclusive pairs in the `fix-lse` build,
34 and 54 exclusive pairs and no LSE instructions in the `fix-llsc` build, and no calls to out-of-line
atomics helpers in either.

Runtime environment of the benchmarks (not a build option, but needed to repeat a run): `STATS_BENCH_CPUS`
(the CPU list threads are pinned to), `STATS_BENCH_WARMUP` and `STATS_BENCH_SECONDS` (the windows),
`STATS_BENCH_THREADS` and `STATS_BENCH_HAMMERS` (the thread counts). The harness configs record the values
used.

## Credits

Five commits of the sink fix are authored by Joshua Marantz: they port code from his upstream work-in-progress
pull request 44285, which marks the shared-pointer stat functions deprecated rather than removing them. The
code of those five is his. Their commit messages were written by us during the port; each says so, and keeps
our text under the heading "Notes by We-Amp (port and testing)". Five more
commits adapt code or a rule from that pull request and from his upstream pull request "stats: remove storm of refcount
bumping during metrics snapshot."; their messages say so and name him as co-author. As of 2026-11 both pull requests are closed and were not merged,
so this is not upstream code and not part of any Envoy release. The relaxed-ordering changes follow his
suggestion in the upstream issue "stats: excessive ref-count inc/dec causing performance bottleneck".
