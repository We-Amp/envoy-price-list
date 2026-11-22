#!/bin/bash
# shellcheck disable=SC2054  # commas are inside compiler and linker flags
# autofdo-order: autofdo v2 rebuilt (a reproducibility check against the measured autofdo-v2 binary)
# and the same objects relinked with the call-graph ordering file, plus a packing gate.
#
#   build-autofdo-order.sh
#
# Own work dir and Bazel output base: W2B_WORK (default ./code-layout-work-b); a fresh v1.40.2
# checkout in it (W2_SRC / W2_WT override as in common.sh). Inputs in W2B_IN (default $W2B_WORK/in):
#   envoy-v2.afdo          the merged profile of autofdo-v2.sh ($W2_WORK/prof2/envoy.afdo)
#   cg.txt                 the ordering file of build-arms.sh ($W2_WORK/prof/order/cg.txt)
#   envoy-opt.unstripped   $W2_WORK/side/envoy-opt.unstripped
#   lbr-s.data, lbr-fh.data, lbr-fl.data   the LBR legs of the official binary (LBR_A_DIR of build-arms.sh)
# EXPECT_V2_SHA: sha256 the plain autofdo v2 rebuild is compared with (default: the measured binary).
#
# PACKING GATE (set before the build): over the functions holding 90% of opt's LBR branch weight
# (the LBR legs above, matched by name in both binaries), autofdo+order must cover at most 0.70 x
# the 4 KB pages that plain autofdo v2 covers. Else the arm is dropped. Verdict in $W2B_WORK/gate.txt.
# Exit code also in $W2B_WORK/rc: 0 done, 3 disk stop, 4 setup, 5 v2 build, 6 order build.
set -u
W2_WORK=${W2B_WORK:-./code-layout-work-b}
# shellcheck source-path=SCRIPTDIR source=common.sh
. "$(dirname "$0")/common.sh"
R=$W/logs; BIN=$W/bins; OB=$W/ob; IN=${W2B_IN:-$W/in}
EXPECT_V2_SHA=${EXPECT_V2_SHA:-c706fe0aedfaa33988324d519f6de90bc5a24c3f5ca87c041628f795e5f4d0a3}
mkdir -p "$R" "$BIN" "$W/tmp"; export TMPDIR=$W/tmp
AF=(--copt=-fprofile-sample-use="$IN/envoy-v2.afdo" --copt=-Wno-backend-plugin)
ORD=(--linkopt=-Wl,--call-graph-ordering-file="$IN/cg.txt" --linkopt=-Wl,--call-graph-profile-sort=cdsort)
log() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "$R/driver.log"; }
fin() { ( cd "$WT" && pin bazel --output_base="$OB" shutdown ) >> "$R/shutdown.log" 2>&1; echo "$1" > "$W/rc"; log "DRIVER-END rc=$1"; exit "$1"; }
diskok() { local a; a=$(avail); log "disk avail=${a}G load=$(cut -d' ' -f1-3 /proc/loadavg)"; [ "$a" -ge "$DISK_FLOOR_G" ] || { log "DISK-STOP"; fin 3; }; }
bb() { ( cd "$WT" && pin bazel --output_base="$OB" info "${COMMON[@]}" "$@" bazel-bin 2>/dev/null ); }
build() {
  local name=$1; shift; local f=() t=()
  while [ $# -gt 0 ] && [ "$1" != -- ]; do f+=("$1"); shift; done; shift; t=("$@")
  diskok; log "BUILD $name start"; local s=$SECONDS
  ( cd "$WT" && pin bazel --output_base="$OB" build "${COMMON[@]}" "${f[@]}" "${t[@]}" ) > "$R/build-$name.log" 2>&1
  local rc=$?; log "BUILD $name rc=$rc wall=$((SECONDS-s))s"
  strip_ansi "$R/build-$name.log" | grep -E "error:|^ERROR" | head -10 | tee -a "$R/driver.log"
  return $rc
}
log "START"; diskok
fetch_source || fin 4
log "v1.40.2 = $(git -C "$SRC" rev-parse --short=10 'refs/tags/v1.40.2^{commit}')"
( cd "$IN" && sha256sum envoy-v2.afdo cg.txt ) | tee -a "$R/driver.log"
# 1. plain autofdo v2 (stripped must reproduce the measured binary; unstripped for the gate)
build v2 "${REL[@]}" "${THIN[@]}" "${AF[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static || fin 5
BB=$(bb "${REL[@]}" "${THIN[@]}" "${AF[@]}"); TC=$(ls -d "$OB"/external/+envoy_llvm_extension+llvm_toolchain_llvm/bin)
cp -L "$BB/source/exe/envoy-static.stripped" "$BIN/envoy-autofdo-v2"; cp -L "$BB/source/exe/envoy-static" "$BIN/envoy-autofdo-v2.unstripped"
got=$(sha256sum "$BIN/envoy-autofdo-v2" | cut -d' ' -f1); log "v2 stripped sha256 $got"
if [ "$got" = "$EXPECT_V2_SHA" ]; then log "v2 REPRODUCES the measured binary"; else log "v2 DIFFERS from the measured binary (${EXPECT_V2_SHA:0:8})"; fi
# 2. the same objects relinked with the order file
build order "${REL[@]}" "${THIN[@]}" "${AF[@]}" "${ORD[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static || fin 6
BB=$(bb "${REL[@]}" "${THIN[@]}" "${AF[@]}" "${ORD[@]}")
cp -L "$BB/source/exe/envoy-static.stripped" "$BIN/envoy-autofdo-order"; cp -L "$BB/source/exe/envoy-static" "$BIN/envoy-autofdo-order.unstripped"
chmod 755 "$BIN"/*; ( cd "$BIN" && sha256sum envoy-autofdo-order envoy-autofdo-v2 ) | tee -a "$R/driver.log"
"$BIN/envoy-autofdo-order" --version 2>&1 | grep -m1 version | tee -a "$R/driver.log"
log "lld ordering warnings: $(strip_ansi "$R/build-order.log" | grep -c 'warning:')"
strip_ansi "$R/build-order.log" | grep 'warning:' | sed 's/.*warning: //' | cut -c1-60 | sort | uniq -c | sort -rn | head -5 | tee -a "$R/driver.log"
# 3. hot set from the LBR legs of opt (== official), then the packing gate
for b in opt autofdo-v2 autofdo-order; do
  u=$IN/envoy-opt.unstripped; [ "$b" != opt ] && u=$BIN/envoy-$b.unstripped
  "$TC/llvm-nm" --defined-only --numeric-sort --print-size --no-demangle "$u" > "$W/tmp/$b.nm"
done
mkdir -p "$W/prof/pbin" && cp "$IN/envoy-opt.unstripped" "$W/prof/pbin/envoy-1.40.2"
for sh in s fh fl; do "$PERF" script -i "$IN/lbr-$sh.data" --show-mmap-events -F ip,brstack > "$W/prof/$sh.script" 2>/dev/null; done
python3 -I "$HERE/lbr2order.py" edges "$W/prof/pbin/envoy-1.40.2" "$W/tmp/opt.nm" "$W/prof/order" "$W/prof/s.script" "$W/prof/fh.script" "$W/prof/fl.script" > "$R/edges.json" 2>&1
if cmp -s "$W/prof/order/cg.txt" "$IN/cg.txt"; then log "cg.txt regenerated identically"; else log "cg.txt regenerated DIFFERENTLY (gate still uses the hot set)"; fi
for b in opt autofdo-v2 autofdo-order; do python3 -I "$HERE/lbr2order.py" span "$W/prof/order/hot.json" "$W/tmp/$b.nm" "$b" > "$R/span-$b.json"; done
python3 -I - "$R/span-autofdo-v2.json" "$R/span-autofdo-order.json" <<'EOF' | tee "$W/gate.txt" | tee -a "$R/driver.log"
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
ra = b["c90"]["pages_4k"] / a["c90"]["pages_4k"]
print("gate: c90 4K pages autofdo-v2 %d, autofdo+order %d, ratio %.2f (limit 0.70); names missing %d / %d"
      % (a["c90"]["pages_4k"], b["c90"]["pages_4k"], ra, a["names_missing"], b["names_missing"]))
print("GATE " + ("PASS: keep the arm" if ra <= 0.70 else "FAIL: drop the arm"))
EOF
rm -rf "$W"/prof/*.script
fin 0
