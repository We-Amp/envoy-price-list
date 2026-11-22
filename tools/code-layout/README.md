# Code-layout builds of Envoy v1.40.2

Scripts that build the binaries of wave 2 (code layout, [`examples/wave2`](../../examples/wave2)):
what a stock-like Envoy build gives up to a better code layout, and how much of the PGO gain comes
without a training harness. Every arm is a build of upstream tag `v1.40.2` with the release options

```
-c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib
```

and Envoy's default hermetic toolchain (clang and lld from the tree; no `--config`). The flags,
tool versions and checksums in the scripts are the method: change them and you build something else.

## The arms

| Arm | Script | What it is |
|---|---|---|
| `opt` | `build-arms.sh` | plain `-c opt`. The stripped binary is byte-identical to the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…f03cc`); the unstripped binary, its `llvm-nm` listing and the `.dwp` split-DWARF file are kept as side files |
| `order` | `build-arms.sh` | the `opt` objects relinked with an lld call-graph ordering file (`--call-graph-ordering-file`, `--call-graph-profile-sort=cdsort`) computed by `lbr2order.py` from LBR legs of the official binary |
| `autofdo` | `build-arms.sh` | sampled PGO: `llvm-profgen` (LLVM 22.1.8 release) on the same LBR legs, merged with `llvm-profdata`, built with `-fprofile-sample-use` + ThinLTO (v1; superseded by v2) |
| `pgolto` | `build-arms.sh` | instrumented PGO: a `-fprofile-generate` build, trained with the nine-leg trainer of the `pgo-recipe-v1` kit, merged, then `--fdo_optimize` + ThinLTO |
| `pgolto-relocs` | `build-arms.sh` | `pgolto` relinked with `--emit-relocs`, debug info stripped: the BOLT input. The script checks that its `.text` equals `pgolto`'s and runs a BOLT smoke test without a profile |
| `bolt` | `bolt.sh` | `llvm-bolt` 22.1.8 on `pgolto-relocs` with an LBR profile of `pgolto-relocs` (ext-tsp block order, cdsort function order, split functions, ICF, tcmalloc/allocator functions skipped) |
| `autofdo-v2` | `autofdo-v2.sh` | the `autofdo` arm rebuilt from about 15x more samples: the `lbr-w2-opt` legs of `opt` |
| `autofdo-order` | `build-autofdo-order.sh` | the `autofdo-v2` objects relinked with the ordering file of `order`, behind a packing gate (below) |

`lbr2order.py` turns `perf script --show-mmap-events -F ip,brstack` output into the ordering file
(`cg.txt`: `caller callee weight`, an edge for every branch that lands on a function's entry) and a
hot-function list (`hot.json`), and reports how many 4 KB / 2 MB pages the hottest functions span in
a given binary (`span`). Its docstring states the method.

## Prerequisites

- Linux x86-64, the build tools Envoy needs, `bazel` (bazelisk with the tree's `.bazelversion`),
  `git`, `curl`, `python3`, `sha256sum`, `taskset` (only with `PIN_CPUS`).
- Envoy source: the scripts fetch tag `v1.40.2` of `https://github.com/envoyproxy/envoy.git` into
  `$W2_WORK/src` with a detached worktree in `$W2_WORK/wt` (or point `W2_SRC` / `W2_WT` at an
  existing checkout of that tag).
- The PGO trainer kit: `tools/pgo` from branch `pgo-recipe-v1` of the public fork
  `https://github.com/We-Amp/envoy`, fetched by `build-arms.sh` into `$W2_WORK/pgo-tools` and used as
  plain scripts (`tools/pgo/train.sh`). The trainer also needs a `nighthawk_client` (`NIGHTHAWK`).
- LLVM 22.1.8 release tools: `build-arms.sh` downloads
  `https://github.com/llvm/llvm-project/releases/download/llvmorg-22.1.8/LLVM-22.1.8-Linux-X64.tar.xz`,
  checks sha256 `df0e1ecf16caf3489a272a5eea4eec9b0d82878f6477fa309504f918a0006384`, and extracts only
  `llvm-profgen`, `llvm-bolt`, `perf2bolt`, `merge-fdata`, `llvm-profdata` and their libraries into
  `$W2_WORK/llvm-22.1.8`. A mismatching tarball is deleted and not used.
- `perf` that can read the LBR data (perf 6.8 was used), and LBR legs recorded with the harness on
  the bench box (next section).
- Disk and time: large. Each Bazel output base of a ThinLTO/PGO build takes tens of GB and the
  scripts stop below `DISK_FLOOR_G` (default 65) GB free. `build-arms.sh` runs seven Envoy builds
  plus nine 60 s training legs: plan for many hours on 32 jobs. `autofdo-v2.sh` uses its own output
  base: about 70 minutes cold on 32 jobs under load.

## Order of steps

1. **LBR legs of the official binary.** Record the `lbr-a` run of
   [`examples/topdown`](../../examples/topdown) on the bench box (`chain.sh`). Copy the three legs
   of the `stock` arm off the box and name them by shape: `lbr-s.data`, `lbr-fh.data`,
   `lbr-fl.data` in `$W2_WORK/prof/a` (or `LBR_A_DIR`). The pid in each file name
   (`lbr-<pid>.data`) is the leg's `envoy_pid` in `lbr/legs.jsonl`, which also names its arm and
   shape. Because `opt` is byte-identical to the official binary, these legs describe `opt`.
2. **`build-arms.sh`** builds `opt` (and checks it against the official sha256), the ordering file and
   the AutoFDO profile from step 1, then `order`, `autofdo`, the instrumented build, the training,
   `pgolto` and `pgolto-relocs`. If `opt` differs from the official binary, `order` and `autofdo` are
   skipped: record LBR legs of your `opt` build instead and run again.
3. **Profiling legs on the bench box** with the harness: `examples/wave2/run-w2.sh prof` records
   `lbr-w2` (`pgolto-relocs`, the BOLT input); with `PROF_OPT=1` also `lbr-w2-opt` (`opt`). Copy the
   `lbr-<pid>.data` files and `manifest.txt` of each run off the box.
4. **`bolt.sh LBR_W2_DIR`** builds `bolt` from the `lbr-w2` data. No Bazel.
5. **`autofdo-v2.sh LBR_W2_OPT_DIR`** builds `autofdo-v2` from the `lbr-w2-opt` data, in its own
   output base. To free disk first, wait for `$W2_WORK/rc`, run
   `bazel --output_base="$W2_WORK/ob" shutdown` in `$W2_WORK/wt`, and remove `$W2_WORK/ob`.
6. **`build-autofdo-order.sh`** (own work dir `W2B_WORK`): copy `$W2_WORK/prof2/envoy.afdo` to
   `$W2B_WORK/in/envoy-v2.afdo`, `$W2_WORK/prof/order/cg.txt`, `$W2_WORK/side/envoy-opt.unstripped`
   and the three legs of step 1 into `$W2B_WORK/in`. It rebuilds `autofdo-v2` (and reports whether the
   rebuild reproduces the measured binary), relinks it with the ordering file, and applies the
   packing gate: over the functions holding 90% of `opt`'s LBR branch weight, `autofdo-order` must
   touch at most 0.70 x the 4 KB pages `autofdo-v2` touches, else the arm is dropped (`gate.txt`).

The binaries are then pinned by sha256 in [`examples/wave2/bins.json`](../../examples/wave2/bins.json)
and copied to the bench box for the A/B runs.

## Parameters

All are environment variables; `common.sh` holds the shared ones.

| Variable | Default | Used by | Meaning |
|---|---|---|---|
| `W2_WORK` | `./code-layout-work` | all but `build-autofdo-order.sh` | work dir: source, output bases, logs, binaries |
| `W2B_WORK` | `./code-layout-work-b` | `build-autofdo-order.sh` | its work dir (fresh checkout and output base) |
| `W2B_IN` | `$W2B_WORK/in` | `build-autofdo-order.sh` | its inputs (step 6) |
| `W2_SRC` | `$W2_WORK/src` | all builds | git dir with tag `v1.40.2` (created when absent) |
| `W2_WT` | `$W2_WORK/wt` | all builds | worktree of `v1.40.2` where Bazel runs |
| `W2_LLVM` | `$W2_WORK/llvm-22.1.8` | all | LLVM 22.1.8 release tools |
| `PERF` | `perf` | all | perf binary |
| `JOBS` | `32` | builds | Bazel `--jobs` and `--local_resources=cpu` |
| `PIN_CPUS` | empty | all | when set, every Bazel, profgen, BOLT and binary call runs under `taskset -c "$PIN_CPUS"` |
| `DISK_FLOOR_G` | `65` | builds | stop (exit 3) below this many GB free in the work dir's file system |
| `LBR_A_DIR` | `$W2_WORK/prof/a` | `build-arms.sh` | LBR legs of the official binary (step 1) |
| `NIGHTHAWK` | empty | `build-arms.sh` | `nighthawk_client` for the trainer; empty skips `pgolto` and `pgolto-relocs` |
| `ENVOY_CPUS`, `ORIGIN_CPUS`, `CLIENT_CPUS` | trainer defaults | `build-arms.sh` | read by `train.sh` from the environment: disjoint CPU lists for the trained Envoy (4 CPUs were used), the origin Envoy (4) and the client (8) |
| `HTTP_PORT`, `H3_PORT`, `ORIGIN_PORT` | `29080`, `29443`, `29081` | `build-arms.sh` | trainer ports |
| `BOLT_FALLBACK` | `/usr/bin/llvm-bolt-20` | `build-arms.sh` | BOLT for the smoke test when the tarball has none |
| `W2_BIN` | `$W2_WORK/bins/envoy-pgolto-relocs` | `bolt.sh` | the BOLT input |
| `EXPECT_V2_SHA` | `c706fe0a…d0a3` (the measured `autofdo-v2`) | `build-autofdo-order.sh` | sha256 the rebuild is compared with |

## Outputs

- `$W2_WORK/bins/`: `envoy-opt`, `envoy-order`, `envoy-autofdo`, `envoy-pgolto`,
  `envoy-pgolto-relocs`, `envoy-bolt`, `envoy-autofdo-v2` (the measured binaries).
- `$W2_WORK/side/`: unstripped binaries, `llvm-nm` listings, `envoy-opt.dwp`.
- `$W2_WORK/prof/`: per-shape AutoFDO profiles, merged `envoy.afdo`, `order/cg.txt`, `order/hot.json`;
  `$W2_WORK/prof2/envoy.afdo` (v2); `$W2_WORK/pgo/envoy.profdata`; `$W2_WORK/bolt/merged.fdata`.
- Records: `$W2_WORK/logs/bins.txt` (sha256, size and `--version` of every binary), `driver.log`
  (toolchain versions, `.text` sizes, layout spans), `stages.txt` (status per stage),
  `SHA256SUMS.bins` and `SHA256SUMS.side`; `v2.log`, `bolt.log`; for `build-autofdo-order.sh`
  `$W2B_WORK/logs/driver.log` and `$W2B_WORK/gate.txt`.
- Exit codes, also written to `rc` (`rc-v2` for `autofdo-v2.sh`): 0 done, 3 disk stop, 4 setup or
  profile failure, 5/6 build failure (see each script's header).
