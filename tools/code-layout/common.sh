#!/bin/bash
# Shared settings of the code-layout build scripts. Sourced, not run. Every value can be set in the
# environment; see README.md for what each one means.
# shellcheck disable=SC2034,SC2054  # variables used by the sourcing scripts; commas are inside flags

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

W=${W2_WORK:-./code-layout-work}
mkdir -p "$W"
W=$(cd "$W" && pwd)
SRC=${W2_SRC:-$W/src}                    # git dir holding tag v1.40.2 (created when absent)
WT=${W2_WT:-$W/wt}                       # detached worktree of v1.40.2: where Bazel runs
LLVM_VER=22.1.8
LLVM_SHA=df0e1ecf16caf3489a272a5eea4eec9b0d82878f6477fa309504f918a0006384
LLVM_TGZ=LLVM-$LLVM_VER-Linux-X64.tar.xz
LX=${W2_LLVM:-$W/llvm-$LLVM_VER}         # LLVM release tools (llvm-profgen, llvm-bolt, perf2bolt, ...)
PERF=${PERF:-perf}                       # perf binary (perf 6.8 was used)
JOBS=${JOBS:-32}                         # Bazel --jobs and --local_resources=cpu
DISK_FLOOR_G=${DISK_FLOOR_G:-65}         # stop when the work dir's file system has less free space (GB)
PIN_CPUS=${PIN_CPUS:-}                   # optional CPU list for taskset; empty = no pinning
OFFICIAL_SHA=1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc  # envoy-1.40.2-linux-x86_64

COMMON=(--jobs="$JOBS" --local_resources=cpu="$JOBS")
REL=(-c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib)
THIN=(--features=thin_lto --ltobackendopt=-Wno-unused-command-line-argument)
SKIP_FUNCS='.*tcmalloc.*,malloc.*,free.*,calloc.*,realloc.*,_Zn[wa].*,_Zd[la].*'

# pin CMD...: run CMD, under `taskset -c "$PIN_CPUS"` when PIN_CPUS is set
pin() {
  if [ -n "$PIN_CPUS" ]; then taskset -c "$PIN_CPUS" "$@"; else "$@"; fi
}
strip_ansi() { sed 's/\x1b\[[0-9;]*m//g' "$1"; }
avail() { df -BG --output=avail "$W" | tail -1 | tr -dc 0-9; }

# fetch_source: tag v1.40.2 of upstream Envoy into $SRC, worktree at $WT (no-op when $SRC exists)
fetch_source() {
  [ -d "$SRC" ] && return 0
  git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/envoyproxy/envoy.git || return 1
  git -C "$SRC" fetch -q --depth 1 origin 'refs/tags/v1.40.2:refs/tags/v1.40.2' || return 1
  git -C "$SRC" worktree add -q --detach "$WT" refs/tags/v1.40.2
}
