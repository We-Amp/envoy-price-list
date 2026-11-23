#!/bin/bash
# Host prerequisites for the arm64 code-layout builds (Linux aarch64, Ubuntu 24.04 was used). Resumable: every
# step is skipped when its result is already there.
#
#   setup.sh
#
# Steps:
#   1 apt packages (SETUP_APT=1, the default; needs sudo): the build and profiling tools, plus what
#     autofdo.sh needs to build create_llvm_prof
#   2 add the current user to the docker group (opt-in: SETUP_DOCKER_GROUP=1; needs sudo and a new login)
#   3 perf access for SPE and kernel symbols (opt-in: SETUP_PERF_SYSCTL=1; see the warning below)
#   4 bazelisk v1.27.0 (arm64 release, sha256 checked) as $ARM_WORK/tools/bin/bazel, unless bazel is on PATH
#   5 Envoy tag v1.40.2 into $ARM_SRC with a detached worktree $ARM_WT
#   6 the PGO trainer kit (tools/pgo of pgo-recipe-v1) into $ARM_WORK/pgo-tools
#   7 the LLVM 22.1.8 aarch64 release tarball (sha256 checked; a mismatching file is deleted), only the tools
#   8 the official arm64 release binary (sha256 checked) as $ARM_OFFICIAL
#   9 the pinned nginx:alpine origin image for linux/arm64 (SETUP_NGINX=1, the default; DOCKER, default docker)
# Log $ARM_WORK/logs/setup.log; exit code also in $ARM_WORK/rc-setup: 0 done, 4 package/fetch failure,
# 5 LLVM tarball missing or mismatching, 6 image pull failed, 7 checksum mismatch.
set -u
# shellcheck source-path=SCRIPTDIR source=common.sh
. "$(dirname "$0")/common.sh"
mkdir -p "$W/logs" "$W/tmp" "$W/tools/bin" "$(dirname "$OFFICIAL")"; export TMPDIR=$W/tmp
LOGF=$W/logs/setup.log
fin() { log "setup end rc=$1"; echo "$1" > "$W/rc-setup"; exit "$1"; }
SETUP_APT=${SETUP_APT:-1}
SETUP_DOCKER_GROUP=${SETUP_DOCKER_GROUP:-0}
SETUP_PERF_SYSCTL=${SETUP_PERF_SYSCTL:-0}
SETUP_NGINX=${SETUP_NGINX:-1}
DOCKER=${DOCKER:-docker}
log "start"

# shellcheck disable=SC2024  # the logs belong to the user; only apt-get needs root
# 1. packages (the first list is the host setup, the second what create_llvm_prof needs)
if [ "$SETUP_APT" = 1 ]; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git curl unzip patch python3 python3-venv docker.io jq \
    build-essential "linux-tools-$(uname -r)" linux-tools-common > "$W/logs/apt.log" 2>&1 || fin 4
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cmake ninja-build clang libunwind-dev libgflags-dev \
    libssl-dev libelf-dev protobuf-compiler libprotobuf-dev libzstd-dev zlib1g-dev pkg-config > "$W/logs/apt2.log" 2>&1 \
    || log "apt warnings for the create_llvm_prof packages (see apt2.log)"
fi

# 2. docker without sudo (opt-in)
if [ "$SETUP_DOCKER_GROUP" = 1 ]; then sudo usermod -aG docker "$USER"; log "added $USER to the docker group (log in again)"; fi

# 3. perf access (opt-in). WARNING: perf_event_paranoid=-1 lets every local user profile every process and the
# kernel, and kptr_restrict=0 shows kernel addresses to every user. Runtime only (lost at reboot). Use it on a
# dedicated host only, and set the old values back when done (Ubuntu's defaults: 4 and 1).
if [ "$SETUP_PERF_SYSCTL" = 1 ]; then
  log "WARNING: setting kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0 (was $(cat /proc/sys/kernel/perf_event_paranoid) $(cat /proc/sys/kernel/kptr_restrict))"
  sudo sysctl -q kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0
fi

# 4. bazelisk
if ! command -v bazel >/dev/null; then
  curl -sSfL -o "$W/tmp/bazelisk" "$BAZELISK_URL" || fin 4
  got=$(sha_of "$W/tmp/bazelisk"); log "bazelisk sha256 $got"
  [ "$got" = "$BAZELISK_SHA" ] || { log "bazelisk sha256 MISMATCH (expected $BAZELISK_SHA)"; rm -f "$W/tmp/bazelisk"; fin 7; }
  install -m755 "$W/tmp/bazelisk" "$W/tools/bin/bazel" && rm -f "$W/tmp/bazelisk"
fi

# 5. Envoy source
fetch_source || fin 4
got=$(git -C "$SRC" rev-parse --short=10 'refs/tags/v1.40.2^{commit}'); log "v1.40.2 = $got"
[ "$got" = "$ENVOY_COMMIT" ] || { log "v1.40.2 is not $ENVOY_COMMIT"; fin 7; }

# 6. trainer kit, used as plain scripts (tools/pgo/train.sh)
if [ ! -f "$W/pgo-tools/tools/pgo/train.sh" ]; then
  git -C "$SRC" fetch -q --depth 1 "$PGO_KIT_REPO" "$PGO_KIT_REF" || { log "trainer kit fetch failed"; fin 4; }
  log "pgo-recipe-v1 = $(git -C "$SRC" rev-parse --short=10 FETCH_HEAD)"
  mkdir -p "$W/pgo-tools"
  git -C "$SRC" archive FETCH_HEAD tools/pgo | tar -x -C "$W/pgo-tools" || fin 4
fi

# 7. LLVM release tools
if [ ! -x "$LX/bin/llvm-bolt" ]; then
  curl -sSfL -o "$W/tmp/$LLVM_TGZ" "$LLVM_URL" || { log "LLVM download failed"; fin 5; }
  got=$(sha_of "$W/tmp/$LLVM_TGZ"); log "LLVM tarball sha256 $got"
  [ "$got" = "$LLVM_SHA" ] || { log "LLVM tarball sha256 MISMATCH (expected $LLVM_SHA)"; rm -f "$W/tmp/$LLVM_TGZ"; fin 5; }
  mkdir -p "$LX" && tar -xJf "$W/tmp/$LLVM_TGZ" -C "$LX" --strip-components=1 --wildcards \
    '*/bin/llvm-profgen' '*/bin/llvm-bolt' '*/bin/perf2bolt' '*/bin/merge-fdata' '*/bin/llvm-profdata' '*/bin/llvm-objdump' '*/bin/llvm-nm' '*/bin/llvm-readelf' '*/bin/llvm-readobj' '*/bin/llvm-objcopy' '*/lib/libLLVM*' '*/lib/libbolt_rt*' 2>> "$LOGF"
  rm -f "$W/tmp/$LLVM_TGZ"
fi
for t in llvm-profgen llvm-bolt perf2bolt llvm-profdata llvm-objdump; do log "tool $t: $("$LX/bin/$t" --version 2>&1 | grep -m1 -i version)"; done

# 8. the official binary
if [ "$(sha_of "$OFFICIAL")" != "$OFFICIAL_SHA" ]; then
  curl -sSfL -o "$OFFICIAL" "$OFFICIAL_URL" || fin 4
  chmod 755 "$OFFICIAL"
  got=$(sha_of "$OFFICIAL"); log "official sha256 $got"
  [ "$got" = "$OFFICIAL_SHA" ] || { log "official sha256 MISMATCH (expected $OFFICIAL_SHA)"; rm -f "$OFFICIAL"; fin 7; }
fi
log "official $("$OFFICIAL" --version 2>&1 | grep -m1 version)"

# 9. the origin image of the harness, by digest
if [ "$SETUP_NGINX" = 1 ]; then
  $DOCKER pull -q --platform linux/arm64 "$NGINX_IMAGE" >> "$LOGF" 2>&1 || fin 6
  log "nginx pinned digest pulled"
fi
fin 0
