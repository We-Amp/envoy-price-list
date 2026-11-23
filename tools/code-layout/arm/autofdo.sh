#!/bin/bash
# shellcheck disable=SC2054  # commas are inside compiler flags
# The autofdo arm on arm64 (wave 6 track J, examples/wave6j): a sampled-PGO profile from SPE branch samples of the
# official binary, then Envoy built with -fprofile-sample-use + ThinLTO (wave 2's autofdo configuration).
#
#   autofdo.sh SPE_DIR
#
# SPE_DIR holds the spe-<pid>.data legs of the official binary (the spe-w6j-official run of the harness, recorded
# with examples/wave6j/perf-spe.sh) and its manifest.txt.
# Profile tools (AFDO_TOOL):
#   clp      (default; the measured binary) create_llvm_prof of google/autofdo f95d1a170dfe, --profiler=perf_spe,
#            built here with cmake + ninja into AUTOFDO_DIR (default $ARM_WORK/autofdo-tool)
#   profgen  llvm-profgen 22.1.8 on `perf script --itrace=bl -F ip,brstack` text. Kept for the record: on track J
#            it gave no body samples ("No samples in perf script!"), so the gate below stops it.
# The profile binary is opt's unstripped build (OPT_UNSTRIPPED, default $ARM_WORK/side/envoy-opt.unstripped, from
# build-arms.sh; opt is byte-identical to the official binary), renamed to the official file name so the mmap name
# matches; OPT_DWP (default $ARM_WORK/side/envoy-opt.dwp) is used by llvm-profgen only.
# Gate: the top 25 functions of the merged profile must carry more than 0 body samples.
# Writes $ARM_WORK/bins/envoy-autofdo and the profile $ARM_WORK/prof/envoy2.afdo (clp) or envoy.afdo (profgen).
# Own Bazel output base $ARM_WORK/ob-afdo. Exit code also in $ARM_WORK/rc-autofdo: 0 done, 3 disk, 4 inputs,
# 30 clone failed, 31 create_llvm_prof build failed, 32 fewer than 3 profiles, 33 merge failed, 34 no body
# samples, 5 Envoy build failed.
set -u
SPE=${1:?usage: autofdo.sh SPE_DIR}
# shellcheck source-path=SCRIPTDIR source=common.sh
. "$(dirname "$0")/common.sh"
R=$W/logs; B=$W/bins; P=$W/prof; OB=$W/ob-afdo
A=${AUTOFDO_DIR:-$W/autofdo-tool}
AFDO_TOOL=${AFDO_TOOL:-clp}
AUTOFDO_ALLOW_OTHER=${AUTOFDO_ALLOW_OTHER:-0}   # 1 = accept a google/autofdo HEAD other than AUTOFDO_COMMIT
OPT_UNSTRIPPED=${OPT_UNSTRIPPED:-$W/side/envoy-opt.unstripped}
OPT_DWP=${OPT_DWP:-$W/side/envoy-opt.dwp}
mkdir -p "$R" "$B" "$P/pbin" "$W/tmp"; export TMPDIR=$W/tmp
LOGF=$R/autofdo.log
fin() { log "end rc=$1"; echo "$1" > "$W/rc-autofdo"; exit "$1"; }
log "start pid $$ tool $AFDO_TOOL"
[ "$(avail)" -ge "$DISK_FLOOR_G" ] || { log "disk under ${DISK_FLOOR_G}G"; fin 3; }
[ -d "$WT" ] && [ -f "$OPT_UNSTRIPPED" ] || { log "need the worktree (setup.sh) and $OPT_UNSTRIPPED (build-arms.sh)"; fin 4; }
[ -f "$SPE/manifest.txt" ] && tee -a "$LOGF" < "$SPE/manifest.txt"
PB=$P/pbin/envoy-1.40.2-aarch64
cp "$OPT_UNSTRIPPED" "$PB"; [ -f "$OPT_DWP" ] && ln -sf "$OPT_DWP" "$PB.dwp"
pr=()
case "$AFDO_TOOL" in
  clp)
    if [ ! -x "$A/build/create_llvm_prof" ]; then
      [ -d "$A" ] || git clone -q --recursive --depth 1 --shallow-submodules "$AUTOFDO_REPO" "$A" > "$R/autofdo-clone.log" 2>&1 || fin 30
      head=$(git -C "$A" rev-parse --short=12 HEAD); log "google/autofdo HEAD $head $(git -C "$A" log -1 --format=%cs)"
      if [ "$head" != "$AUTOFDO_COMMIT" ] && [ "$AUTOFDO_ALLOW_OTHER" != 1 ]; then
        log "google/autofdo HEAD is not $AUTOFDO_COMMIT; set AUTOFDO_ALLOW_OTHER=1 to build it anyway"; fin 30
      fi
      mkdir -p "$A/build"; s=$SECONDS
      ( cd "$A/build" && timeout 2400 bash -c "cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DLLVM_PATH=$A/third_party/llvm-project -DENABLE_TOOL=LLVM .. > $R/autofdo-cmake.log 2>&1 && ninja -j $JOBS create_llvm_prof > $R/autofdo-ninja.log 2>&1" )
      log "create_llvm_prof build rc=$? wall=$((SECONDS-s))s"; tail -5 "$R/autofdo-ninja.log" >> "$LOGF" 2>/dev/null
      [ -x "$A/build/create_llvm_prof" ] || fin 31
    fi
    "$A/build/create_llvm_prof" --version 2>&1 | head -2 | tee -a "$LOGF"
    OUT=$P/envoy2.afdo; mkdir -p "$P/afdo2"
    for f in "$SPE"/spe-*.data; do
      n=$(basename "$f" .data)
      pin "$A/build/create_llvm_prof" --profiler=perf_spe --profile="$f" --binary="$PB" \
        --disassemble_arm_branches=true --format=extbinary --out="$P/afdo2/$n.afdo" > "$R/clp-$n.log" 2>&1
      log "create_llvm_prof $n rc=$? size=$(stat -c %s "$P/afdo2/$n.afdo" 2>/dev/null)"; tail -3 "$R/clp-$n.log" >> "$LOGF"
      [ -s "$P/afdo2/$n.afdo" ] && pr+=("$P/afdo2/$n.afdo")
    done
    ;;
  profgen)
    OUT=$P/envoy.afdo; mkdir -p "$P/afdo"
    for f in "$SPE"/spe-*.data; do
      n=$(basename "$f" .data)
      "$PERF" script -i "$f" --itrace=bl -F ip,brstack --show-mmap-events > "$P/afdo/$n.script" 2> "$R/perfscript-$n.err"
      log "perf script $n rc=$? lines=$(wc -l < "$P/afdo/$n.script") brstack_lines=$(grep -c '/' "$P/afdo/$n.script")"
      pin "$LX/bin/llvm-profgen" --format=extbinary --binary="$PB" --dwp="$OPT_DWP" \
        --ignore-stack-samples --perfscript="$P/afdo/$n.script" --output="$P/afdo/$n.afdo" > "$R/profgen-$n.log" 2>&1
      log "profgen $n rc=$? size=$(stat -c %s "$P/afdo/$n.afdo" 2>/dev/null)"; tail -4 "$R/profgen-$n.log" >> "$LOGF"
      [ -s "$P/afdo/$n.afdo" ] && pr+=("$P/afdo/$n.afdo")
      rm -f "$P/afdo/$n.script"
    done
    ;;
  *) log "AFDO_TOOL must be clp or profgen"; fin 4 ;;
esac
[ ${#pr[@]} -ge 3 ] || fin 32
"$LX/bin/llvm-profdata" merge --sample --extbinary -o "$OUT" "${pr[@]}" > "$R/afdo-merge.log" 2>&1 || fin 33
"$LX/bin/llvm-profdata" show --sample "$OUT" 2>/dev/null | grep "^Function" | awk -F': ' '{split($3,a,","); print a[1], $2}' | sort -n -r | head -25 > "$R/afdo-top.txt"
cut -c1-160 "$R/afdo-top.txt" >> "$LOGF"
tot=$(awk '{s+=$1} END {print s+0}' "$R/afdo-top.txt"); log "top-25 body samples total=$tot"
[ "$tot" -gt 0 ] || { log "PROFILE GATE FAILED: no body samples"; fin 34; }
( cd "$P" && sha256sum "$(basename "$OUT")" ) | tee -a "$LOGF"

# the autofdo build (wave 2's configuration)
AF=(--copt=-fprofile-sample-use="$OUT" --copt=-Wno-backend-plugin)
log "BUILD autofdo start (jobs=$JOBS)"; s=$SECONDS
( cd "$WT" && pin bazel --output_base="$OB" build "${COMMON[@]}" "${REL[@]}" "${THIN[@]}" "${AF[@]}" //source/exe:envoy-static.stripped ) > "$R/build-autofdo.log" 2>&1
rc=$?; log "autofdo build rc=$rc wall=$((SECONDS-s))s"
if [ $rc = 0 ]; then
  BB=$(cd "$WT" && bazel --output_base="$OB" info "${REL[@]}" "${THIN[@]}" "${AF[@]}" bazel-bin 2>/dev/null)
  cp -L "$BB/source/exe/envoy-static.stripped" "$B/envoy-autofdo"; chmod 755 "$B/envoy-autofdo"
  rec autofdo "$B/envoy-autofdo"
else strip_ansi "$R/build-autofdo.log" | grep -E "error:|ERROR" | head -10 >> "$LOGF"; fi
( cd "$WT" && bazel --output_base="$OB" shutdown ) >/dev/null 2>&1
[ $rc = 0 ] || fin 5
fin 0
