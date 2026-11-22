#!/bin/bash
# shellcheck disable=SC2054  # commas are inside compiler and linker flags
# autofdo v2: the autofdo arm rebuilt from the profiling legs of the opt binary recorded with the
# harness (lbr-w2-opt in examples/wave2: two legs per shape, 30 s windows, period 20,003; about 15x
# the samples of the 20 s top-down LBR legs build-arms.sh uses).
#
#   autofdo-v2.sh OPT_LBR_DIR
#
# OPT_LBR_DIR: lbr-<pid>.data of the opt legs (the executable is named envoy-1.40.2 on the bench box)
# and manifest.txt, copied off the bench box. Uses what build-arms.sh left in $W2_WORK (src, wt,
# the LLVM tools, side/envoy-opt.unstripped + .dwp). Own Bazel output base ($W2_WORK/ob2): a cold
# build, about 70 min on 32 jobs under load. Writes $W2_WORK/bins/envoy-autofdo-v2 and the profile
# $W2_WORK/prof2/envoy.afdo. Exit code also in $W2_WORK/rc-v2: 0 done, 3 disk, 4 profile, 5 build.
set -u
LBR=${1:?usage: autofdo-v2.sh OPT_LBR_DIR}
# shellcheck source-path=SCRIPTDIR source=common.sh
. "$(dirname "$0")/common.sh"
R=$W/logs; BIN=$W/bins; SIDE=$W/side; P2=$W/prof2
OB=$W/ob2; mkdir -p "$R" "$BIN" "$P2" "$W/tmp"; export TMPDIR=$W/tmp
log() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "$R/v2.log"; }
fin() { ( cd "$WT" && pin bazel --output_base="$OB" shutdown ) >> "$R/v2-shutdown.log" 2>&1; echo "$1" > "$W/rc-v2"; log "V2-END rc=$1"; exit "$1"; }
[ "$(avail)" -ge "$DISK_FLOOR_G" ] || { log "disk under ${DISK_FLOOR_G}G"; echo 3 > "$W/rc-v2"; exit 3; }
tee -a "$R/v2.log" < "$LBR/manifest.txt"
mkdir -p "$P2/pbin" && cp "$SIDE/envoy-opt.unstripped" "$P2/pbin/envoy-1.40.2" && ln -sf "$SIDE/envoy-opt.dwp" "$P2/pbin/envoy-1.40.2.dwp"
pr=()
for f in "$LBR"/lbr-*.data; do
  b=$(basename "$f" .data)
  "$PERF" script -i "$f" --show-mmap-events -F ip,brstack > "$P2/$b.script" 2> "$R/v2-perfscript-$b.err"
  pin "$LX/bin/llvm-profgen" --format=extbinary --binary="$P2/pbin/envoy-1.40.2" --dwp="$SIDE/envoy-opt.dwp" \
    --ignore-stack-samples --perfscript="$P2/$b.script" --output="$P2/$b.afdo" > "$R/v2-profgen-$b.log" 2>&1
  log "profgen $b rc=$? $(grep -m1 'more samples' "$R/v2-profgen-$b.log")"
  [ -s "$P2/$b.afdo" ] && pr+=("$P2/$b.afdo"); rm -f "$P2/$b.script"
done
[ ${#pr[@]} -ge 3 ] || { log "too few profiles (${#pr[@]})"; fin 4; }
"$LX/bin/llvm-profdata" merge --sample --extbinary -o "$P2/envoy.afdo" "${pr[@]}" > "$R/v2-merge.log" 2>&1 || fin 4
"$LX/bin/llvm-profdata" show --sample --topn=40 "$P2/envoy.afdo" > "$R/v2-afdo-show.txt" 2>&1
AF=(--copt=-fprofile-sample-use="$P2/envoy.afdo" --copt=-Wno-backend-plugin)
log "BUILD autofdo-v2 start"; s=$SECONDS
( cd "$WT" && pin bazel --output_base="$OB" build "${COMMON[@]}" "${REL[@]}" "${THIN[@]}" "${AF[@]}" //source/exe:envoy-static.stripped ) > "$R/build-autofdo-v2.log" 2>&1
rc=$?; log "BUILD autofdo-v2 rc=$rc wall=$((SECONDS-s))s"; [ $rc -eq 0 ] || fin 5
BB=$( cd "$WT" && pin bazel --output_base="$OB" info "${COMMON[@]}" "${REL[@]}" "${THIN[@]}" "${AF[@]}" bazel-bin 2>/dev/null )
cp -L "$BB/source/exe/envoy-static.stripped" "$BIN/envoy-autofdo-v2" && chmod 755 "$BIN/envoy-autofdo-v2"
( cd "$BIN" && sha256sum envoy-autofdo-v2 ) | tee -a "$R/v2.log"; "$BIN/envoy-autofdo-v2" --version 2>&1 | grep -m1 version | tee -a "$R/v2.log"
fin 0
