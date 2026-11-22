#!/bin/bash
# The bolt arm: llvm-bolt (LLVM 22.1.8 release) on pgolto-relocs with the LBR profile recorded on
# the bench box with the harness (lbr-w2 in examples/wave2). No Bazel.
#
#   bolt.sh LBR_DIR
#
# LBR_DIR holds lbr-<pid>.data of envoy-pgolto-relocs (the lbr-w2 legs) and manifest.txt.
# Needs $W2_WORK/bins/envoy-pgolto-relocs (or W2_BIN) and the LLVM tools in $W2_WORK/llvm-22.1.8
# (or W2_LLVM). perf2bolt runs `perf` from PATH; PERF (default perf) is put first on PATH for it.
# Writes $W2_WORK/bins/envoy-bolt; logs in $W2_WORK/logs/bolt-*. Exit 3: no profile, 4: llvm-bolt failed.
set -u
LBR=${1:?usage: bolt.sh LBR_DIR}
# shellcheck source-path=SCRIPTDIR source=common.sh
. "$(dirname "$0")/common.sh"
R=$W/logs; IN=${W2_BIN:-$W/bins/envoy-pgolto-relocs}
PERFDIR=$W/tmp/perfbin; mkdir -p "$PERFDIR" "$R" "$W/bins"
PERF_PATH=$(command -v "$PERF") || { echo "perf not found: $PERF" >&2; exit 2; }
ln -sf "$PERF_PATH" "$PERFDIR/perf"; export PATH=$PERFDIR:$PATH
log() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "$R/bolt.log"; }
# perf2bolt matches the profiled mapping by file name: give the input the bench box's name
mkdir -p "$W/bolt" && cp "$IN" "$W/bolt/envoy-pgolto-relocs" && B=$W/bolt/envoy-pgolto-relocs
log "input $(sha256sum "$B" | cut -c1-16) manifest:"; tee -a "$R/bolt.log" < "$LBR/manifest.txt"
fd=()
for f in "$LBR"/lbr-*.data; do
  n=$(basename "$f" .data); o=$W/bolt/$n.fdata
  pin "$LX/bin/perf2bolt" -p "$f" -o "$o" "$B" > "$R/bolt-p2b-$n.log" 2>&1
  log "perf2bolt $(basename "$f") rc=$? $(grep -E -m2 'samples|LBR' "$R/bolt-p2b-$n.log" | tr '\n' ' ')"
  [ -s "$o" ] && fd+=("$o")
done
[ ${#fd[@]} -gt 0 ] || { log "no fdata"; exit 3; }
"$LX/bin/merge-fdata" "${fd[@]}" > "$W/bolt/merged.fdata" 2> "$R/bolt-merge.log"; log "merge-fdata rc=$? files=${#fd[@]}"
pin "$LX/bin/llvm-bolt" "$B" -o "$W/bins/envoy-bolt" -data="$W/bolt/merged.fdata" \
  -reorder-blocks=ext-tsp -reorder-functions=cdsort -split-functions -split-all-cold -split-eh -icf=1 \
  -dyno-stats -skip-funcs="$SKIP_FUNCS" \
  > "$R/bolt-opt.log" 2>&1
rc=$?; log "llvm-bolt rc=$rc"; grep -E "BOLT-INFO: (profile|[0-9]+ out of|basic block reordering|ICF)|BOLT-ERROR|BOLT-WARNING" "$R/bolt-opt.log" | head -20 | tee -a "$R/bolt.log"
[ $rc -eq 0 ] || exit 4
chmod 755 "$W/bins/envoy-bolt"
"$W/bins/envoy-bolt" --version 2>&1 | grep -m1 version | tee -a "$R/bolt.log"
( cd "$W/bins" && sha256sum envoy-bolt ) | tee -a "$R/bolt.log"
log "BOLT-DONE"
