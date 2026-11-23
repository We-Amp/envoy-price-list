#!/bin/bash
# Shared settings of the arm64 code-layout scripts. Sourced, not run. Every value can be set in the environment;
# see README.md for what each one means.
# shellcheck disable=SC2034,SC2054  # variables used by the sourcing scripts; commas are inside flags

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)        # the harness checkout (examples/wave5i, examples/wave6j)

W=${ARM_WORK:-./code-layout-arm-work}
mkdir -p "$W"
W=$(cd "$W" && pwd)
SRC=${ARM_SRC:-$W/src}                    # git dir holding tag v1.40.2 (created when absent)
WT=${ARM_WT:-$W/wt}                       # detached worktree of v1.40.2: where Bazel runs
ENVOY_COMMIT=b2d89e0ae5                   # v1.40.2

# LLVM 22.1.8 release tools for aarch64 (llvm-profgen, llvm-bolt, perf2bolt, merge-fdata, llvm-profdata, ...)
LLVM_VER=22.1.8
LLVM_TGZ=LLVM-$LLVM_VER-Linux-ARM64.tar.xz
LLVM_URL=https://github.com/llvm/llvm-project/releases/download/llvmorg-$LLVM_VER/$LLVM_TGZ
LLVM_SHA=805efad2bb91cb4967fa569e0881d10c0f69c04461cf671cccbae19f547acc34
LX=${ARM_LLVM:-$W/llvm-$LLVM_VER}

BAZELISK_URL=https://github.com/bazelbuild/bazelisk/releases/download/v1.27.0/bazelisk-linux-arm64
BAZELISK_SHA=bb608519a440d45d10304eb684a73a2b6bb7699c5b0e5434361661b25f113a5d

# the official arm64 release asset; the harness names the file envoy-1.40.2-aarch64
OFFICIAL_URL=https://github.com/envoyproxy/envoy/releases/download/v1.40.2/envoy-1.40.2-linux-aarch_64
OFFICIAL_SHA=b9d6d1e06dd5838a3506de9f4deebad3de9a2ce6cadb87cd76222ca286213baf
OFFICIAL=${ARM_OFFICIAL:-$W/official/envoy-1.40.2-aarch64}

NGINX_IMAGE=nginx:alpine@sha256:fb4658584bd9a916ffb6f6e365f97c25cfdb2923801f551ea08356e695f14ff7
NIGHTHAWK_REPO=https://github.com/envoyproxy/nighthawk.git
NIGHTHAWK_COMMIT=d5d185d5d1
NIGHTHAWK_SHA=77cf42f549c0aae967f3a06c68cbd9ae9aaecb7e559a2e816e802bae7d3669fd   # as built on track I
PGO_KIT_REPO=https://github.com/We-Amp/envoy.git
PGO_KIT_REF=refs/heads/pgo-recipe-v1      # 59a7efb32a when the tracks ran
AUTOFDO_REPO=https://github.com/google/autofdo.git
AUTOFDO_COMMIT=f95d1a170dfe               # google/autofdo HEAD used on track J (2026-09-30)

PERF=${PERF:-perf}                        # perf binary
JOBS=${JOBS:-16}                          # Bazel --jobs and --local_resources=cpu, ninja -j
PIN_CPUS=${PIN_CPUS:-}                    # optional CPU list for taskset; empty = no pinning
DISK_FLOOR_G=${DISK_FLOOR_G:-65}          # stop when the work dir's file system has less free space (GB)
NIGHTHAWK=${NIGHTHAWK:-}                  # nighthawk_client for the PGO trainer

# bazelisk installed by setup.sh (no system-wide install)
[ -x "$W/tools/bin/bazel" ] && PATH=$W/tools/bin:$PATH

COMMON=(--jobs="$JOBS" --local_resources=cpu="$JOBS")
REL=(-c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib)
THIN=(--features=thin_lto --ltobackendopt=-Wno-unused-command-line-argument)
PGW=(--copt=-Wno-backend-plugin --copt=-Wno-profile-instr-out-of-date --copt=-Wno-profile-instr-unprofiled)
MCPU=(--copt=-mcpu=neoverse-v2 --ltobackendopt=-mcpu=neoverse-v2)
SKIP_FUNCS='.*tcmalloc.*,malloc.*,free.*,calloc.*,realloc.*,_Zn[wa].*,_Zd[la].*'

# pin CMD...: run CMD, under `taskset -c "$PIN_CPUS"` when PIN_CPUS is set
pin() {
  if [ -n "$PIN_CPUS" ]; then taskset -c "$PIN_CPUS" "$@"; else "$@"; fi
}
strip_ansi() { sed 's/\x1b\[[0-9;]*m//g' "$1"; }
avail() { df -BG --output=avail "$W" | tail -1 | tr -dc 0-9; }
# log MSG: to stdout and $LOGF (each script sets LOGF)
log() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "${LOGF:-$W/logs/driver.log}"; }
# resumable stages: a marker file per finished stage
mark() { touch "$W/.done-$1"; }
done_() { [ -e "$W/.done-$1" ]; }
sha_of() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }
# rec ARM FILE: sha256, size and --version into logs/bins.txt
rec() {
  ( cd "$(dirname "$2")" && sha256sum "$(basename "$2")" ) | sed "s|^|$1 |" | tee -a "$W/logs/bins.txt"
  echo "$1 size $(stat -c %s "$2")" >> "$W/logs/bins.txt"
  pin "$2" --version 2>&1 | grep -m1 version | sed "s|^.*version: |$1 version: |" | tee -a "$W/logs/bins.txt"
}

# fetch_source: tag v1.40.2 of upstream Envoy into $SRC, worktree at $WT (no-op when $WT exists)
fetch_source() {
  [ -d "$WT" ] && return 0
  if [ ! -d "$SRC" ]; then
    git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/envoyproxy/envoy.git || return 1
  fi
  git -C "$SRC" fetch -q --depth 1 origin 'refs/tags/v1.40.2:refs/tags/v1.40.2' || return 1
  git -C "$SRC" worktree add -q --detach "$WT" refs/tags/v1.40.2
}
