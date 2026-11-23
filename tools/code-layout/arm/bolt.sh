#!/bin/bash
# The bolt arm on arm64 (wave 6 track J, examples/wave6j): llvm-bolt (LLVM 22.1.8 aarch64 release) on pgolto-relocs
# with an SPE branch profile of pgolto-relocs (perf2bolt --spe). No Bazel.
#
#   bolt.sh SPE_DIR
#
# SPE_DIR holds the spe-<pid>.data legs of envoy-pgolto-relocs (the spe-w6j-relocs run of the harness, recorded with
# examples/wave6j/perf-spe.sh) and manifest.txt. Needs $ARM_WORK/bins/envoy-pgolto-relocs (or ARM_BIN; from
# build-arms.sh) and the LLVM tools of setup.sh. perf2bolt runs `perf` from PATH; PERF (default perf) is put first
# on PATH for it. Writes $ARM_WORK/bins/envoy-bolt and $ARM_WORK/prof/bolt/merged.fdata; log logs/bolt.log.
# Exit 2: perf not found, 3: no profile, 4: llvm-bolt failed.
set -u
SPE=${1:?usage: bolt.sh SPE_DIR}
# shellcheck source-path=SCRIPTDIR source=common.sh
. "$(dirname "$0")/common.sh"
R=$W/logs; B=$W/bins; IN=${ARM_BIN:-$B/envoy-pgolto-relocs}
PERFDIR=$W/tmp/perfbin; mkdir -p "$PERFDIR" "$R" "$B"
PERF_PATH=$(command -v "$PERF") || { echo "perf not found: $PERF" >&2; exit 2; }
ln -sf "$PERF_PATH" "$PERFDIR/perf"; export PATH=$PERFDIR:$PATH
LOGF=$R/bolt.log
# perf2bolt matches the profiled mapping by file name: keep the name the legs were recorded with
BD=$W/prof/bolt; mkdir -p "$BD" && cp "$IN" "$BD/envoy-pgolto-relocs" && BI=$BD/envoy-pgolto-relocs
log "input $(sha_of "$BI" | cut -c1-16)"; [ -f "$SPE/manifest.txt" ] && tee -a "$LOGF" < "$SPE/manifest.txt"
fd=()
for f in "$SPE"/spe-*.data; do
  n=$(basename "$f" .data); o=$BD/$n.fdata
  pin "$LX/bin/perf2bolt" -p "$f" -o "$o" --spe "$BI" > "$R/bolt-p2b-$n.log" 2>&1
  log "perf2bolt $(basename "$f") rc=$? $(grep -E -m3 -i 'samples|branch|SPE' "$R/bolt-p2b-$n.log" | tr '\n' ' ' | cut -c1-300)"
  [ -s "$o" ] && fd+=("$o")
done
[ ${#fd[@]} -gt 0 ] || { log "BOLT: no fdata"; exit 3; }
"$LX/bin/merge-fdata" "${fd[@]}" > "$BD/merged.fdata" 2> "$R/bolt-merge.log"; log "merge-fdata rc=$? files=${#fd[@]}"
pin "$LX/bin/llvm-bolt" "$BI" -o "$B/envoy-bolt" -data="$BD/merged.fdata" \
  -reorder-blocks=ext-tsp -reorder-functions=cdsort -split-functions -split-all-cold -split-eh -icf=1 \
  -dyno-stats -skip-funcs="$SKIP_FUNCS" > "$R/bolt-opt.log" 2>&1
rc=$?; log "llvm-bolt rc=$rc"
grep -E "BOLT-INFO: (profile|[0-9]+ out of|basic block reordering|ICF)|BOLT-ERROR|BOLT-WARNING" "$R/bolt-opt.log" | head -20 | tee -a "$LOGF"
[ $rc -eq 0 ] || exit 4
chmod 755 "$B/envoy-bolt"; rec bolt "$B/envoy-bolt"
( cd "$BD" && sha256sum merged.fdata ) | tee -a "$LOGF"
log "BOLT-DONE"
