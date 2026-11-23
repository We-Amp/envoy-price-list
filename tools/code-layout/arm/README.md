# Code-layout builds of Envoy v1.40.2 on arm64

Scripts that build the arm64 binaries of wave 5 track I ([`examples/wave5i`](../../../examples/wave5i)) and
wave 6 track J ([`examples/wave6j`](../../../examples/wave6j)). They are the arm64 side of
[`tools/code-layout`](../README.md) (x86-64, wave 2) and follow its layout: one settings file (`common.sh`),
environment parameters with defaults, sha256 records of everything built.

Every arm is a build of upstream tag `v1.40.2` (`b2d89e0ae5`) for aarch64 with the release options

```
-c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib
```

and Envoy's default hermetic toolchain (clang and lld 22.1.8, `ca7933e47d3a`; Bazel 8.8.1 through bazelisk
1.27.0). The flags, tool versions and checksums in the scripts are the method: change them and you build
something else.

The two tracks ran on different arm64 hosts:

- **Track I**: an Arm cloud VM, Neoverse V2, 16 vCPU, 64 GiB. The guest had the PMU (cycle counter plus
  programmable counters) but **no SPE, no BRBE and no CoreSight trace**. So the ordering file came from
  frame-pointer call chains (`perf record --call-graph=fp`, `fp2order.py`), and there were **no autofdo and no
  bolt arms**. Track I built `opt`, `order`, `pgolto`, `pgolto-v2`, `pgolto-relocs` and `nighthawk_client`.
- **Track J**: arm64 bare metal (it reports Neoverse N3; 96 cores, SPEv1.2, no BRBE). The binaries `opt`
  (measured as `opt-file`), `order`, `pgolto`, `pgolto-relocs` and `nighthawk_client` were **track I's files**,
  copied to the host. Track J built only `autofdo` (from SPE samples) and `bolt` (from SPE samples).

## The arms

| Arm | Script | Track | What it is |
|---|---|---|---|
| `official` | `setup.sh` | I, J | the release asset `envoy-1.40.2-linux-aarch_64`, sha256 `b9d6d1e0…213baf` (outline atomics), saved as `envoy-1.40.2-aarch64` |
| `opt` / `opt-file` | `build-arms.sh` | I (built), J (measured) | plain `-c opt`. The stripped binary is **byte-identical** to `official`, so on track I it was not a separate arm, and its unstripped build (`fd29623c…`) and `.dwp` (`ff432eaa…`) symbolize `official`. On track J the same bytes as a separate file are the `opt-file` arm: a file control for `order` |
| `order` | `build-arms.sh` | I (built), I and J (measured) | the `opt` objects relinked (link only, same output base) with `--call-graph-ordering-file` + `--call-graph-profile-sort=cdsort`; the ordering file comes from `fp2order.py` on frame-pointer legs of `official` |
| `pgolto` | `build-arms.sh` | I (built), I and J (measured) | instrumented PGO: a `-fprofile-generate` build, the nine-leg trainer of `pgo-recipe-v1` run on the host, merged, then `--fdo_optimize` + ThinLTO + `-Wno-backend-plugin -Wno-profile-instr-out-of-date -Wno-profile-instr-unprofiled` |
| `pgolto-v2` | `build-arms.sh` | I | `pgolto` plus `--copt=-mcpu=neoverse-v2 --ltobackendopt=-mcpu=neoverse-v2`, the same profile, with a codegen gate. **Not portable:** it needs Armv9.0 with SVE2 and traps with SIGILL on Neoverse N1-class cores |
| `pgolto-relocs` | `build-arms.sh` | I (built), J (profiled only) | `pgolto` relinked with `--emit-relocs`, debug stripped: the BOLT input |
| `autofdo` | `autofdo.sh` | J | sampled PGO from SPE: `create_llvm_prof --profiler=perf_spe` (google/autofdo `f95d1a170dfe`) on six SPE legs of `official`, merged with `llvm-profdata` 22.1.8, built with `-fprofile-sample-use` + ThinLTO (wave 2's configuration) |
| `bolt` | `bolt.sh` | J | `llvm-bolt` 22.1.8 (aarch64 release) on `pgolto-relocs` with an SPE profile of `pgolto-relocs` (`perf2bolt --spe`): ext-tsp block order, cdsort function order, split functions, ICF, tcmalloc/allocator functions skipped |

`fp2order.py` ([`examples/wave5i/fp2order.py`](../../../examples/wave5i/fp2order.py); the same file is in
`examples/wave6j`) turns `perf script --show-mmap-events -F ip` output of frame-pointer samples into the ordering
file (`cg.txt`: every adjacent frame pair is a weighted call edge) and a hot-function list (`hot.json`), and
reports the 4 KB / 2 MB page span of the hot set in a given binary (`span`). It replaces wave 2's `lbr2order.py`
on a host without branch records. Its docstring states the method and its gates (half of the leaf frames must map
into the binary; median chain depth at least 4).

## Prerequisites

- Linux aarch64 (Ubuntu 24.04 was used) with the build tools Envoy needs; `setup.sh` installs the packages
  (`apt-get`, with sudo) and fetches the rest.
- bazelisk v1.27.0 (`bazelisk-linux-arm64`, sha256 `bb608519…5c113a5d`), installed by `setup.sh` into the work
  dir when `bazel` is not on PATH. Envoy's `.bazelversion` gives Bazel 8.8.1; Nighthawk's gives 9.3.1.
- Envoy source: tag `v1.40.2` of `https://github.com/envoyproxy/envoy.git` into `$ARM_SRC` with a detached
  worktree `$ARM_WT`.
- The PGO trainer kit: `tools/pgo` from branch `pgo-recipe-v1` (`59a7efb32a`) of the public fork
  `https://github.com/We-Amp/envoy`, used as plain scripts (`tools/pgo/train.sh`). The trainer needs a
  `nighthawk_client` (`NIGHTHAWK`, or `BUILD_NIGHTHAWK=1` to build `d5d185d5d1` of
  `https://github.com/envoyproxy/nighthawk.git`).
- LLVM 22.1.8 aarch64 release tools: `setup.sh` downloads
  `https://github.com/llvm/llvm-project/releases/download/llvmorg-22.1.8/LLVM-22.1.8-Linux-ARM64.tar.xz`,
  checks sha256 `805efad2bb91cb4967fa569e0881d10c0f69c04461cf671cccbae19f547acc34`, and extracts only
  `llvm-profgen`, `llvm-bolt`, `perf2bolt`, `merge-fdata`, `llvm-profdata`, `llvm-objdump`, `llvm-nm`,
  `llvm-readelf`, `llvm-readobj`, `llvm-objcopy` and their libraries. A mismatching tarball is deleted.
- `perf` from `linux-tools-$(uname -r)`. Profiling other processes and SPE need perf access: either run the legs
  with enough privilege or opt in to `SETUP_PERF_SYSCTL=1` (below), which **lowers the host's perf and kernel
  pointer restrictions for every user until reboot**. Use that on a dedicated host only.
- SPE (`/sys/bus/event_source/devices/arm_spe_0`) for `autofdo.sh` and `bolt.sh`. Not available in most VMs.
- The harness origin: `nginx:alpine@sha256:fb4658584bd9a916ffb6f6e365f97c25cfdb2923801f551ea08356e695f14ff7`
  for linux/arm64 (`setup.sh` pulls it with `DOCKER`, default `docker`; set `DOCKER="sudo docker"` if needed).
- Disk and time: large. Each output base takes tens of GB; the scripts stop below `DISK_FLOOR_G` GB free. On
  16 jobs each full Envoy build took about 27 min, a ThinLTO/PGO build about 55 min (two in parallel at 8 jobs
  each); the autofdo build took 29 min on 88 jobs; create_llvm_prof builds in about a minute on 88 jobs.

## Order of steps (track J, bare metal with SPE)

1. **`setup.sh`**: packages, bazelisk, source, trainer kit, LLVM tools, the official binary, the origin image.
2. **`build-arms.sh`** (first pass): `opt` (checked against the official sha256), `opt.dwp`, optionally
   `nighthawk_client`, the instrumented build, the nine-leg training, `pgolto`, `pgolto-v2` (with the codegen gate)
   and `pgolto-relocs`. `order` is skipped until the frame-pointer legs exist. (On track J these binaries were
   track I's files, checked by sha256 against [`examples/wave6j/bins.json`](../../../examples/wave6j/bins.json).)
3. **Frame-pointer legs of `official`** with the harness: [`examples/wave5i`](../../../examples/wave5i)
   `chain-w5i.sh prof` (run `fp-w5i`) with the perf wrapper `perf-fp.sh`
   (`perf record -N -q --call-graph=fp -e cycles:u -c 1000003`, two legs per shape). Put the `fp-<pid>.data`
   files in `FP_DIR` and run **`build-arms.sh`** again: it computes the ordering file and relinks `order`.
4. **SPE legs** with the harness: [`examples/wave6j`](../../../examples/wave6j) `chain-w6j.sh prof` with the perf
   wrapper `perf-spe.sh` (`perf record -N -q -e arm_spe_0/branch_filter=1,jitter=1/u -c 10007`). It records two
   runs of six legs (two per shape): `spe-w6j-official` (the `official` binary) and `spe-w6j-relocs`
   (`envoy-pgolto-relocs`). The data lands in the wrapper's output dir (`W6J_SPE_OUT`), one subdirectory per run.
5. **`autofdo.sh <dir of spe-w6j-official>`**: builds create_llvm_prof, makes the profile, applies the body-sample
   gate, builds `autofdo` in its own output base.
6. **`bolt.sh <dir of spe-w6j-relocs>`**: `perf2bolt --spe`, `merge-fdata`, `llvm-bolt`. No Bazel.

The binaries are then pinned by sha256 in the box's `bins.json` and the A/B run goes through the harness
(`chain-w6j.sh ab`; configs in `examples/wave6j/arm-metal` and `examples/wave6j/boxes`). A finished A/B chain in
the examples can power the host off (`sudo shutdown -h +20` unless a `KEEP` file exists); that is host
housekeeping for a rented machine, not part of the method.

### How track I differed (VM, no SPE or BRBE)

- Steps 1-3 only, and in the order opt, nighthawk_client, instrumented build, frame-pointer legs, training,
  then `order`, `pgolto` and `pgolto-v2` (the two ThinLTO builds in parallel at 8 jobs each), and later `opt.dwp`
  and `pgolto-relocs` as hand-over files for track J.
- No `autofdo` and no `bolt`: without SPE, BRBE or trace in the guest there are no taken-branch records, and
  frame-pointer samples give call edges but no branch counts.
- The harness configs are in `examples/wave5i/arm-vm-w5i` and `examples/wave5i/boxes`.

## Parameters

All are environment variables; `common.sh` holds the shared ones.

| Variable | Default | Used by | Meaning |
|---|---|---|---|
| `ARM_WORK` | `./code-layout-arm-work` | all | work dir: source, output bases, logs, binaries |
| `ARM_SRC` | `$ARM_WORK/src` | all | git dir with tag `v1.40.2` (created when absent) |
| `ARM_WT` | `$ARM_WORK/wt` | all | worktree of `v1.40.2` where Bazel runs |
| `ARM_LLVM` | `$ARM_WORK/llvm-22.1.8` | all | LLVM 22.1.8 aarch64 release tools |
| `ARM_OFFICIAL` | `$ARM_WORK/official/envoy-1.40.2-aarch64` | `setup.sh` | where the official binary is saved |
| `PERF` | `perf` | `build-arms.sh`, `autofdo.sh`, `bolt.sh` | perf binary |
| `JOBS` | `16` | builds | Bazel `--jobs` and `--local_resources=cpu`, ninja `-j` (track I used 16, 8 for the two parallel ThinLTO builds; track J 88) |
| `PIN_CPUS` | empty | all | when set, Bazel, the profile tools, BOLT and binary calls run under `taskset -c "$PIN_CPUS"` |
| `DISK_FLOOR_G` | `65` | builds | stop (exit 3) below this many GB free in the work dir's file system |
| `NIGHTHAWK` | empty | `build-arms.sh` | `nighthawk_client` for the trainer; empty (and no `BUILD_NIGHTHAWK`) skips the PGO arms |
| `BUILD_NIGHTHAWK` | `0` | `build-arms.sh` | `1` builds `nighthawk_client` `d5d185d5d1` (`bazel build -c opt //:nighthawk_client`) when `NIGHTHAWK` is empty |
| `FP_DIR` | `$ARM_WORK/prof/fp` | `build-arms.sh` | the `fp-<pid>.data` legs of `official` (step 3) |
| `FP2ORDER` | `examples/wave5i/fp2order.py` | `build-arms.sh` | the ordering-file tool |
| `MCPU_ARM` | `1` | `build-arms.sh` | `0` skips `pgolto-v2` |
| `CONCURRENCY`, `ENVOY_CPUS`, `ORIGIN_CPUS`, `CLIENT_CPUS` | trainer defaults (4 workers, unpinned) | `build-arms.sh` | read by `train.sh` from the environment: Envoy workers and disjoint CPU lists for the trained Envoy, the origin Envoy and the client |
| `HTTP_PORT`, `H3_PORT`, `ORIGIN_PORT` | trainer defaults (`19080`, `19443`, `19081`) | `build-arms.sh` | trainer ports |
| `AFDO_TOOL` | `clp` | `autofdo.sh` | `clp` (create_llvm_prof, the measured route) or `profgen` (llvm-profgen; no body samples on track J) |
| `AUTOFDO_DIR` | `$ARM_WORK/autofdo-tool` | `autofdo.sh` | google/autofdo clone and build |
| `AUTOFDO_ALLOW_OTHER` | `0` | `autofdo.sh` | `1` accepts a google/autofdo HEAD other than `f95d1a170dfe` |
| `OPT_UNSTRIPPED`, `OPT_DWP` | `$ARM_WORK/side/envoy-opt.unstripped`, `.dwp` | `autofdo.sh` | the profile binary and its split DWARF |
| `ARM_BIN` | `$ARM_WORK/bins/envoy-pgolto-relocs` | `bolt.sh` | the BOLT input |
| `SETUP_APT` | `1` | `setup.sh` | `0` skips the package install |
| `SETUP_DOCKER_GROUP` | `0` | `setup.sh` | `1` adds the current user to the `docker` group |
| `SETUP_PERF_SYSCTL` | `0` | `setup.sh` | `1` sets `kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0` at runtime. **Warning:** this lets every local user profile every process and read kernel addresses until reboot or until reset |
| `SETUP_NGINX`, `DOCKER` | `1`, `docker` | `setup.sh` | pull the pinned origin image, and with which command |

Housekeeping steps of the original host scripts that are not part of the method were dropped: a wait for the
load average to fall below 0.4 before the profiling legs (the harness chain does its own idle check), and the
power-off timer.

## Outputs

- `$ARM_WORK/bins/`: `envoy-opt`, `envoy-order`, `envoy-pgolto`, `envoy-pgolto-v2`, `envoy-pgolto-relocs`,
  `envoy-autofdo`, `envoy-bolt`, `nighthawk_client` (when built); the official binary in
  `$ARM_WORK/official/`.
- `$ARM_WORK/side/`: unstripped binaries, `llvm-nm` listings, `envoy-opt.dwp`.
- `$ARM_WORK/prof/`: `order/cg.txt`, `order/hot.json`; `envoy2.afdo` (create_llvm_prof) or `envoy.afdo`
  (llvm-profgen); `bolt/merged.fdata`; `$ARM_WORK/pgo/envoy.profdata`.
- Records: `$ARM_WORK/logs/bins.txt` (sha256, size and `--version` of every binary), `driver.log` (stages,
  toolchain, `.text` sizes, layout spans, codegen counts), `stages.txt`, `SHA256SUMS.bins`, `SHA256SUMS.side`;
  `setup.log`, `autofdo.log` (with `afdo-top.txt`), `bolt.log`.
- Exit codes, also written to `rc`, `rc-setup`, `rc-autofdo`: see each script's header.

The measured sha256 of each arm:

| File | sha256 |
|---|---|
| `envoy-1.40.2-aarch64` (official), `envoy-opt` | `b9d6d1e06dd5838a3506de9f4deebad3de9a2ce6cadb87cd76222ca286213baf` |
| `envoy-opt.unstripped` | `fd29623ce0aef22c74e2300a2c8054259ec0584e40df5ac1873c80bdf2b0ae7c` |
| `envoy-opt.dwp` | `ff432eaa6783247959a49250952a4e679c835258e00bebaa1943860f2ffd14c2` |
| `envoy-order` | `b623d72ed8ae89c9fca7f018c07768b381c46650ea1800f86f36fd3ca95c10b6` |
| `envoy-pgolto` | `916d83419433552ef07fc5024af4d4ae65aa9578e681d06b19462a853010e8ea` |
| `envoy-pgolto-v2` | `ac77cdc728d196742a084db36d9ba7e700b8e16f9f140a3d08702760ae5caaa0` |
| `envoy-pgolto-relocs` | `41baf40c590e6bb8dd149a2f471a44731858f798894c34c38cb0578c272cc843` |
| `envoy-pgolto.profdata` | `c721b757dde626a42392cc9ab8ed6b1960232864a651750a92b5777db5fd786a` |
| `envoy-autofdo` | `ab47f18b3af29aa6384004681f359c360f89235590e2db1195004ee6c4b67000` |
| `envoy-bolt` | `f6476336b34f632dc2e6bbc95c902a5f4c2927bc482502ed275b611905ecb63c` |
| `nighthawk_client` (`d5d185d5d1`, 0.3.0) | `77cf42f549c0aae967f3a06c68cbd9ae9aaecb7e559a2e816e802bae7d3669fd` |

The PGO and AutoFDO builds depend on a profile recorded on a particular host, so a rebuild reproduces these
bytes only from the same profile; `opt` should match `official` anywhere.

## Track I build commands as recorded

Track I's driver script was **not kept**. These are the commands as its logs recorded them (build logs,
`driver.log`, `bins.txt`, `train.log`, `pgo-merge.log`, `order-edges.*`, `clang-version.txt`). `build-arms.sh`
re-assembles them. Where the logs do not show a command or a flag, it says so.

Setup: `apt-get install -y git curl unzip patch python3 python3-venv docker.io linux-tools-$(uname -r) jq`;
bazelisk v1.27.0 `bazelisk-linux-arm64`, sha256 `bb608519a440d45d10304eb684a73a2b6bb7699c5b0e5434361661b25f113a5d`;
Envoy `v1.40.2` = `b2d89e0ae5`; the official asset, sha256 `b9d6d1e0…213baf`, version
`b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL`; the trainer kit `tools/pgo` of
`pgo-recipe-v1` `59a7efb32a`. Toolchain: clang 22.1.8 (`ca7933e47d3a3451d81e72ac174dcb5aa28b59d1`), target
`aarch64-unknown-linux-gnu`, from the output base's
`external/envoy_toolshed++llvm_minimal_extension+llvm_minimal_linux_arm64/bin`; LLD 22.1.8.

1. **opt**, output base `ob-opt`, 16 jobs, 1,595 s, 14,454 actions:
   `bazel build -c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib //source/exe:envoy-static.stripped //source/exe:envoy-static`.
   Stripped `b9d6d1e0…213baf`: identical to official. Unstripped `fd29623c…` (447,936,960 bytes). 1,265
   function sections in `conn_manager_impl.o` (`-ffunction-sections` is on, as ordering needs).
2. **nighthawk_client** `d5d185d5d1`, Bazel 9.3.1, 1,619 s, 15,280 actions: `bazel build -c opt //:nighthawk_client`
   (the job count is not in the log). sha256 `77cf42f5…`, version 0.3.0.
3. **instrumented**, output base `ob-inst`, 16 jobs, 1,604 s:
   `bazel build -c opt --copt=-fprofile-generate --linkopt=-fprofile-generate //source/exe:envoy-static`;
   sha256 `998256158a0e541ad48600d705e7fe73b4f03b6e4deeefc7ef62774632c4a2e2`.
4. **frame-pointer legs** of `official` through the harness (`fp-w5i`, six legs, `perf-fp.sh`), then per leg
   `perf script` into a text file (1.2 M / 0.9 M / 0.7 M lines for the three shapes; the exact `perf script`
   options are not in the logs; `build-arms.sh` uses `--show-mmap-events -F ip`, the input `fp2order.py`
   documents), then `fp2order.py edges` on the unstripped `opt` named `envoy-1.40.2-aarch64`: 209,707 samples,
   195,150 with the leaf frame in the binary, median chain depth 26, 4,386 edges, 1,389 hot functions.
5. **training**: `tools/pgo/train.sh --envoy envoy-instrumented --nighthawk nighthawk_client --out train`
   (nine legs of 60 s, 4 workers x 500 requests/s, the trainer's default ports), 569 s. All nine legs 2xx only
   (the two HTTP/3 legs 119,997 of 120,000 completed). Merged with `llvm-profdata merge -output=envoy.profdata
   train/profiles/*.profraw` (rc 0, 58,864,904 bytes; IR instrumentation, 188,145 functions, total count
   40,715,752,048), sha256 `c721b757…`.
6. **order**, output base `ob-opt` (link only), 16 jobs, 169 s, 20 actions: the opt command plus
   `--linkopt=-Wl,--call-graph-ordering-file=prof/order/cg.txt --linkopt=-Wl,--call-graph-profile-sort=cdsort`.
   sha256 `b623d72e…`, 0 link warnings.
7. **pgolto**, output base `ob-pgo`, 8 jobs, 3,321 s, 19,954 actions: the opt command plus
   `--fdo_optimize=pgo/envoy.profdata --features=thin_lto --ltobackendopt=-Wno-unused-command-line-argument --copt=-Wno-backend-plugin --copt=-Wno-profile-instr-out-of-date --copt=-Wno-profile-instr-unprofiled`.
   sha256 `916d8341…`, 0 profile warnings.
8. **pgolto-v2**, output base `ob-v2`, 8 jobs, in parallel with pgolto, 3,323 s: the pgolto command plus
   `--copt=-mcpu=neoverse-v2 --ltobackendopt=-mcpu=neoverse-v2`. sha256 `ac77cdc7…`. Codegen counts recorded with
   `llvm-objdump`: 43,330 inline LSE and 14,842 SVE instructions in `pgolto-v2` against 56 and 0 in `pgolto`;
   outline-atomic calls 50,343 down to 7,105 (the counting commands are not in the logs; `build-arms.sh` counts
   with its own patterns, so its numbers may differ). The `-Wno-profile-*` flags suppress clang's profile
   mismatch diagnostics, so "0 profile warnings" says nothing about mismatches.
9. `.text` sizes: opt `0x3c446e0`, order `0x3c4fd50`, pgolto `0x3a7dfe0`, pgolto-v2 `0x3b83160`.
10. **opt.dwp**, later, 75 s, 53 actions: the opt command with target `//source/exe:envoy-static.dwp`;
    sha256 `ff432eaa…`.
11. **pgolto-relocs**, later, 385 s (5,519 actions, 14,485 action cache hits), target `//source/exe:envoy-static`,
    debug stripped; sha256 `41baf40c…`. The flags and the output base are not printed in the logs; the build is
    the pgolto command plus `--linkopt=-Wl,--emit-relocs`, then `llvm-objcopy --strip-debug`, as on x86 (inferred).
    Its `.text` bytes differ from pgolto's (`b39c37e3d853e29c` against `cab2bdf4c2d9f45f`), while the text symbol
    table, `.text` address and size are identical and `.rodata` moved: the same pattern as on x86.

## Track J commands as run

The host scripts of track J are what `setup.sh`, `autofdo.sh` and `bolt.sh` are made from; the recorded values:
bazelisk sha256 `bb608519…5c113a5d`; LLVM aarch64 tarball sha256 `805efad2…f547acc34`, all tools
`LLVM version 22.1.8`; the origin image digest above.

- **llvm-profgen route first** (`AFDO_TOOL=profgen`): six `spe-w6j-official` legs,
  `perf script --itrace=bl -F ip,brstack --show-mmap-events`, then `llvm-profgen --format=extbinary --binary=...
  --dwp=envoy-opt.dwp --ignore-stack-samples`. Every leg: "No samples in perf script!", 3,198 invalid
  instructions, DWO data not loaded for 234 modules. The profile had no body samples, so this route was dropped.
- **create_llvm_prof route** (`AFDO_TOOL=clp`, the measured `autofdo`): google/autofdo `f95d1a170dfe`
  (2026-09-30), `git clone --recursive --depth 1 --shallow-submodules`, `cmake -G Ninja -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DLLVM_PATH=third_party/llvm-project -DENABLE_TOOL=LLVM`,
  `ninja create_llvm_prof` (69 s on 88 jobs). Per leg `create_llvm_prof --profiler=perf_spe --profile=spe-<pid>.data
  --binary=envoy-1.40.2-aarch64 --disassemble_arm_branches=true --format=extbinary`, then
  `llvm-profdata merge --sample --extbinary`. The `autofdo` build: output base `ob-afdo`, 88 jobs, 1,757 s.
- **bolt**: six `spe-w6j-relocs` legs, `perf2bolt -p spe-<pid>.data -o spe-<pid>.fdata --spe envoy-pgolto-relocs`
  (about 368 K samples per leg, 0.0% ignored), `merge-fdata`, `llvm-bolt` with the flags in `bolt.sh`.
