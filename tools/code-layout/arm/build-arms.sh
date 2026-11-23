#!/bin/bash
# shellcheck disable=SC2054  # commas are inside linker flags
# Build the arm64 code-layout arms of Envoy v1.40.2 the way wave 5 track I built them (examples/wave5i), all with
# the release options (-c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib) and Envoy's
# hermetic clang/lld 22.1.8:
#   opt            plain -c opt (stripped = the official arm64 release binary; unstripped + .dwp kept as side files)
#   nighthawk      nighthawk_client d5d185d5d1 for the trainer and the harness (only with BUILD_NIGHTHAWK=1)
#   order          opt relinked (link only) with an lld call-graph ordering file that fp2order.py computes from
#                  frame-pointer call chains of the official binary, cdsort
#   pgolto         instrumented PGO (nine-leg trainer of pgo-recipe-v1, run here) + ThinLTO
#   pgolto-v2      pgolto + -mcpu=neoverse-v2, the same profile; with a codegen gate
#   pgolto-relocs  pgolto relinked with --emit-relocs, debug stripped: the BOLT input of bolt.sh
#
# Track I's driver script was not kept. This script puts together the build commands its logs recorded
# (README.md, "Track I build commands as recorded"); the steps the logs do not show are marked "inferred".
#
#   build-arms.sh
#
# Run setup.sh first. Each stage is skipped once done (marker $ARM_WORK/.done-<stage>), so run it again after
# the frame-pointer legs exist to add order. Stage-specific settings:
#   FP_DIR           fp-<pid>.data legs of the official binary, recorded with the harness (examples/wave5i,
#                    perf-fp.sh); default $ARM_WORK/prof/fp. Without them order is skipped.
#   FP2ORDER         default examples/wave5i/fp2order.py of this checkout
#   BUILD_NIGHTHAWK  1 = build nighthawk_client into $ARM_WORK/nighthawk when NIGHTHAWK is empty (default 0)
#   NIGHTHAWK        nighthawk_client for the trainer; empty (and no build) skips pgolto, pgolto-v2, pgolto-relocs
#   MCPU_ARM         1 (default) builds pgolto-v2
#   CONCURRENCY, ENVOY_CPUS, ORIGIN_CPUS, CLIENT_CPUS, HTTP_PORT, H3_PORT, ORIGIN_PORT: read by the trainer
#                    (tools/pgo/train.sh) from the environment; its defaults apply when unset
# Exit code also in $ARM_WORK/rc: 0 done, 3 disk stop, 4 setup missing or opt failed. Status per stage in
# stages.txt, sha256/size/version of every binary in logs/bins.txt, sums in SHA256SUMS.bins / SHA256SUMS.side.
set -u
# shellcheck source-path=SCRIPTDIR source=common.sh
. "$(dirname "$0")/common.sh"
R=$W/logs; BIN=$W/bins; SIDE=$W/side; PROF=$W/prof
FP_DIR=${FP_DIR:-$PROF/fp}
FP2ORDER=${FP2ORDER:-$ROOT/examples/wave5i/fp2order.py}
BUILD_NIGHTHAWK=${BUILD_NIGHTHAWK:-0}
MCPU_ARM=${MCPU_ARM:-1}
mkdir -p "$R" "$BIN" "$SIDE" "$PROF" "$W/tmp"; export TMPDIR=$W/tmp
LOGF=$R/driver.log
TC=
stage() { echo "$1 $2" >> "$W/stages.txt"; log "STAGE $1 $2"; }
fin() { stopall; echo "$1" > "$W/rc"; log "driver end rc=$1"; exit "$1"; }
stopall() {
  local ob
  for ob in "$W"/ob-*; do [ -d "$ob" ] && ( cd "$WT" && pin bazel --output_base="$ob" shutdown ); done >> "$R/shutdown.log" 2>&1
}
diskok() {
  local a; a=$(avail)
  log "disk avail=${a}G load=$(cut -d' ' -f1-3 /proc/loadavg)"
  if [ "$a" -lt "$DISK_FLOOR_G" ]; then log "DISK-STOP (floor ${DISK_FLOOR_G}G)"; fin 3; fi
}
summ() { strip_ansi "$1" | grep -E "error:|^ERROR|Elapsed time|Build completed|Build did NOT|INFO: Found" | head -40 | tee -a "$LOGF"; }
# bb OB FLAGS...: bazel-bin of that configuration
bb() { local ob=$1; shift; ( cd "$WT" && pin bazel --output_base="$ob" info "${COMMON[@]}" "$@" bazel-bin 2>/dev/null ); }
# build NAME OB FLAGS... -- TARGETS...
build() {
  local name=$1 ob=$2; shift 2; local flags=() t=()
  while [ $# -gt 0 ] && [ "$1" != -- ]; do flags+=("$1"); shift; done; shift; t=("$@")
  diskok; log "BUILD $name start (ob=$ob jobs=$JOBS): ${flags[*]} ${t[*]}"; local s=$SECONDS
  ( cd "$WT" && pin bazel --output_base="$ob" build "${COMMON[@]}" "${flags[@]}" "${t[@]}" ) > "$R/build-$name.log" 2>&1
  local rc=$?; log "BUILD $name rc=$rc wall=$((SECONDS-s))s"; summ "$R/build-$name.log"; return $rc
}
# tool NAME: the hermetic toolchain's copy when it has one, else the LLVM 22.1.8 release copy
tool() { if [ -n "$TC" ] && [ -x "$TC/$1" ]; then echo "$TC/$1"; else echo "$LX/bin/$1"; fi; }
nm_of() { "$(tool llvm-nm)" --defined-only --numeric-sort --print-size --no-demangle "$1" > "$2"; }
textsha() {
  "$(tool llvm-objcopy)" --dump-section .text="$W/tmp/text.bin" "$1" "$W/tmp/discard.o" 2>/dev/null && sha256sum "$W/tmp/text.bin" | cut -c1-16
  rm -f "$W/tmp/text.bin" "$W/tmp/discard.o"
}
# keep BB-NAME ARM: copy the stripped and unstripped outputs of a build out of bazel-bin
keep() {
  cp -L "$1/source/exe/envoy-static.stripped" "$BIN/envoy-$2"; cp -L "$1/source/exe/envoy-static" "$SIDE/envoy-$2.unstripped"
  chmod 755 "$BIN/envoy-$2" "$SIDE/envoy-$2.unstripped"; rec "$2" "$BIN/envoy-$2"; nm_of "$SIDE/envoy-$2.unstripped" "$SIDE/envoy-$2.nm"
}

log "START nproc=$(nproc) mem=$(awk '/MemTotal/{print int($2/1048576)}' /proc/meminfo)G"; diskok
[ -d "$WT" ] && [ -x "$LX/bin/llvm-nm" ] || { log "run setup.sh first (no worktree or LLVM tools)"; fin 4; }
log "v1.40.2 = $(git -C "$SRC" rev-parse --short=10 'refs/tags/v1.40.2^{commit}')"
OB_OPT=$W/ob-opt; OB_INST=$W/ob-inst; OB_PGO=$W/ob-pgo; OB_V2=$W/ob-v2
ORD=(--linkopt=-Wl,--call-graph-ordering-file="$PROF/order/cg.txt" --linkopt=-Wl,--call-graph-profile-sort=cdsort)
INST=(-c opt --copt=-fprofile-generate --linkopt=-fprofile-generate)
PG=(--fdo_optimize="$W/pgo/envoy.profdata" "${THIN[@]}" "${PGW[@]}")
RL=(--linkopt=-Wl,--emit-relocs)

# ---------------- 1. opt (control; the identity check against the official binary) ----------------
if ! done_ opt; then
  build opt "$OB_OPT" "${REL[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static || { stage opt FAIL; fin 4; }
  BB=$(bb "$OB_OPT" "${REL[@]}"); keep "$BB" opt; rec opt-unstripped "$SIDE/envoy-opt.unstripped"
  if [ "$(sha_of "$BIN/envoy-opt")" = "$OFFICIAL_SHA" ]; then log "opt identity vs official: MATCHES"; else log "opt identity vs official: DIFFERS"; fi
  f=$(find "$BB/source/common/http" -name 'conn_manager_impl*.o' | head -1)
  log "function sections in $f: $("$LX/bin/llvm-readelf" -SW "$f" | grep -c ' \.text\.')"
  stage opt OK; mark opt
fi
shopt -s nullglob; tcs=("$OB_OPT"/external/*llvm_minimal_linux_arm64/bin); shopt -u nullglob; TC=${tcs[0]:-}
log "hermetic toolchain: ${TC:-not found}"
if ! done_ opt-dwp; then
  # split DWARF side file (for llvm-profgen in autofdo.sh)
  if build opt-dwp "$OB_OPT" "${REL[@]}" -- //source/exe:envoy-static.dwp; then
    cp -L "$(bb "$OB_OPT" "${REL[@]}")/source/exe/envoy-static.dwp" "$SIDE/envoy-opt.dwp"; ( cd "$SIDE" && sha256sum envoy-opt.dwp ) | sed 's/^/opt-dwp /' | tee -a "$R/bins.txt"
    stage opt-dwp OK; mark opt-dwp
  else stage opt-dwp FAIL; fi
fi

# ---------------- 2. nighthawk_client (optional) ----------------
if [ -z "$NIGHTHAWK" ] && [ "$BUILD_NIGHTHAWK" = 1 ]; then
  if ! done_ nh; then
    NH=$W/nighthawk
    if [ ! -d "$NH" ]; then
      if ! { git clone -q "$NIGHTHAWK_REPO" "$NH" && git -C "$NH" checkout -q --detach "$NIGHTHAWK_COMMIT"; }; then stage nh FETCH-FAIL; fin 4; fi
    fi
    diskok; log "BUILD nighthawk start ($(git -C "$NH" rev-parse --short=10 HEAD))"; s=$SECONDS
    ( cd "$NH" && pin bazel --output_base="$W/ob-nh" build "${COMMON[@]}" -c opt //:nighthawk_client ) > "$R/build-nh.log" 2>&1
    rc=$?; log "nighthawk rc=$rc wall=$((SECONDS-s))s"; summ "$R/build-nh.log"
    if [ $rc -eq 0 ]; then
      cp -L "$( cd "$NH" && bazel --output_base="$W/ob-nh" info "${COMMON[@]}" -c opt bazel-bin 2>/dev/null )/nighthawk_client" "$BIN/nighthawk_client"
      chmod 755 "$BIN/nighthawk_client"; rec nighthawk "$BIN/nighthawk_client"
      if [ "$(sha_of "$BIN/nighthawk_client")" = "$NIGHTHAWK_SHA" ]; then log "nighthawk_client MATCHES track I's"; else log "nighthawk_client DIFFERS from track I's"; fi
      stage nh OK; mark nh
    else stage nh FAIL; fi
    ( cd "$NH" && bazel --output_base="$W/ob-nh" shutdown ) >> "$R/shutdown.log" 2>&1
  fi
  [ -x "$BIN/nighthawk_client" ] && NIGHTHAWK=$BIN/nighthawk_client
fi

# ---------------- 3. order: ordering file from frame-pointer chains, then a link-only relink of opt ----------------
if ! done_ order; then
  shopt -s nullglob; fp=("$FP_DIR"/fp-*.data); shopt -u nullglob
  if [ ${#fp[@]} -eq 0 ]; then
    log "no fp-*.data in $FP_DIR: order skipped (record the frame-pointer legs, then run again)"; stage order SKIPPED
  else
    # the legs profiled the official file; fp2order matches the mmap by that basename
    mkdir -p "$PROF/pbin" "$PROF/fp-script" && cp "$SIDE/envoy-opt.unstripped" "$PROF/pbin/envoy-1.40.2-aarch64"
    sc=()
    for f in "${fp[@]}"; do
      n=$(basename "$f" .data)
      "$PERF" script -i "$f" --show-mmap-events -F ip > "$PROF/fp-script/$n.script" 2> "$R/perfscript-$n.err"
      log "perf script $n.data rc=$? lines=$(wc -l < "$PROF/fp-script/$n.script")"; sc+=("$PROF/fp-script/$n.script")
    done
    python3 -I "$FP2ORDER" edges "$PROF/pbin/envoy-1.40.2-aarch64" "$SIDE/envoy-opt.nm" "$PROF/order" "${sc[@]}" > "$R/order-edges.json" 2> "$R/order-edges.err"
    orc=$?; log "fp2order rc=$orc edges=$(wc -l < "$PROF/order/cg.txt" 2>/dev/null)"; tee -a "$LOGF" < "$R/order-edges.err"
    rm -rf "$PROF/fp-script"
    if [ $orc -ne 0 ]; then stage order-file FAIL
    elif build order "$OB_OPT" "${REL[@]}" "${ORD[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static; then
      keep "$(bb "$OB_OPT" "${REL[@]}" "${ORD[@]}")" order
      log "order link warnings: $(strip_ansi "$R/build-order.log" | grep -c 'warning:')"
      python3 -I "$FP2ORDER" span "$PROF/order/hot.json" "$SIDE/envoy-opt.nm" opt > "$R/span-opt.json"
      python3 -I "$FP2ORDER" span "$PROF/order/hot.json" "$SIDE/envoy-order.nm" order > "$R/span-order.json"
      cat "$R/span-opt.json" "$R/span-order.json" >> "$LOGF"; stage order OK; mark order
    else stage order FAIL; fi
  fi
fi

# ---------------- 4. instrumented build and the nine-leg training ----------------
if [ -z "$NIGHTHAWK" ]; then
  log "NIGHTHAWK not set: pgolto, pgolto-v2 and pgolto-relocs skipped"; stage pgo SKIPPED
else
  if ! done_ inst; then
    if build inst "$OB_INST" "${INST[@]}" -- //source/exe:envoy-static; then
      cp -L "$(bb "$OB_INST" "${INST[@]}")/source/exe/envoy-static" "$W/envoy-instrumented"; chmod 755 "$W/envoy-instrumented"
      rec inst "$W/envoy-instrumented"; stage inst OK; mark inst
    else stage inst FAIL; fi
  fi
  if done_ inst && ! done_ train; then
    rm -rf "$W/train"   # the trainer refuses an output dir with profiles of an earlier run
    log "TRAIN start (nine legs x 60 s; CONCURRENCY ${CONCURRENCY:-trainer default}, Envoy ${ENVOY_CPUS:-unpinned}, origin ${ORIGIN_CPUS:-unpinned}, client ${CLIENT_CPUS:-unpinned})"; s=$SECONDS
    bash "$W/pgo-tools/tools/pgo/train.sh" --envoy "$W/envoy-instrumented" --nighthawk "$NIGHTHAWK" --out "$W/train" > "$R/train.log" 2>&1
    trc=$?; nprof=$(find "$W/train/profiles" -maxdepth 1 -name '*.profraw' 2>/dev/null | wc -l)
    log "TRAIN rc=$trc wall=$((SECONDS-s))s profiles=$nprof"; cp "$W/train/legs.txt" "$R/train-legs.txt" 2>/dev/null && tee -a "$LOGF" < "$R/train-legs.txt"
    if [ $trc -eq 0 ] && [ "$nprof" -eq 9 ]; then
      PD=$(tool llvm-profdata); log "merge with $PD"
      mkdir -p "$W/pgo"; "$PD" merge -output="$W/pgo/envoy.profdata" "$W"/train/profiles/*.profraw > "$R/pgo-merge.log" 2>&1
      log "merge rc=$? size=$(stat -c %s "$W/pgo/envoy.profdata" 2>/dev/null)"
      "$PD" show "$W/pgo/envoy.profdata" > "$R/pgo-show.txt" 2>&1; tee -a "$LOGF" < "$R/pgo-show.txt"
      ( cd "$W/pgo" && sha256sum envoy.profdata ) | tee -a "$LOGF"
      [ -s "$W/pgo/envoy.profdata" ] && { stage train OK; mark train; }
    else stage train FAIL; fi
    rm -rf "$W/train/profiles" "$W/train/staging" "$W/train/origin-profile"
  fi
  # ---------------- 5. pgolto ----------------
  if done_ train && ! done_ pgolto; then
    if build pgolto "$OB_PGO" "${REL[@]}" "${PG[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static; then
      keep "$(bb "$OB_PGO" "${REL[@]}" "${PG[@]}")" pgolto
      log "pgolto profile warnings: $(strip_ansi "$R/build-pgolto.log" | grep -c 'warning:.*profile')"; stage pgolto OK; mark pgolto
    else stage pgolto FAIL; fi
  fi
  # ---------------- 6. pgolto-v2: -mcpu=neoverse-v2, the same profile, then the codegen gate ----------------
  if [ "$MCPU_ARM" = 1 ] && done_ train && ! done_ pgolto-v2; then
    if build pgolto-v2 "$OB_V2" "${REL[@]}" "${PG[@]}" "${MCPU[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static; then
      keep "$(bb "$OB_V2" "${REL[@]}" "${PG[@]}" "${MCPU[@]}")" pgolto-v2
      log "pgolto-v2 profile warnings: $(strip_ansi "$R/build-pgolto-v2.log" | grep -c 'warning:.*profile')"; stage pgolto-v2 OK; mark pgolto-v2
    else stage pgolto-v2 FAIL; fi
  fi
  if done_ pgolto && done_ pgolto-v2 && ! done_ mcpu-gate; then
    # the flag must reach the ThinLTO backend: inline LSE atomics and SVE instructions in pgolto-v2, fewer calls to
    # the __aarch64_* outline-atomic helpers than pgolto (counted on the unstripped files; inferred counting rules)
    cnt() {
      "$(tool llvm-objdump)" -d --no-show-raw-insn "$1" 2>/dev/null | awk '
        /[[:space:]](ldadd|ldclr|ldeor|ldset|ldsmax|ldsmin|ldumax|ldumin|cas|swp)[a-z]*[[:space:]]/ {lse++}
        /[[:space:]]z[0-9]+\.[bhsdq]/ {sve++}
        /[[:space:]]bl[[:space:]].*<__aarch64_/ {ol++}
        END {printf "%d %d %d\n", lse, sve, ol}'
    }
    read -r l1 s1 o1 < <(cnt "$SIDE/envoy-pgolto.unstripped"); read -r l2 s2 o2 < <(cnt "$SIDE/envoy-pgolto-v2.unstripped")
    log "codegen: pgolto lse=$l1 sve=$s1 outline_calls=$o1; pgolto-v2 lse=$l2 sve=$s2 outline_calls=$o2"
    if [ "$l2" -gt 0 ] && [ "$s2" -gt 0 ] && [ "$o2" -lt "$o1" ]; then stage mcpu-gate PASS; else stage mcpu-gate FAIL; fi
    mark mcpu-gate
  fi
  # ---------------- 7. pgolto-relocs: the BOLT input (inferred: pgolto's flags + --emit-relocs, debug stripped) --------
  if done_ pgolto && ! done_ pgolto-relocs; then
    if build pgolto-relocs "$OB_PGO" "${REL[@]}" "${PG[@]}" "${RL[@]}" -- //source/exe:envoy-static; then
      "$(tool llvm-objcopy)" --strip-debug "$(bb "$OB_PGO" "${REL[@]}" "${PG[@]}" "${RL[@]}")/source/exe/envoy-static" "$BIN/envoy-pgolto-relocs"
      chmod 755 "$BIN/envoy-pgolto-relocs"; rec pgolto-relocs "$BIN/envoy-pgolto-relocs"
      # on arm64 the .text bytes differ from pgolto's (as on x86: relocated displacements); recorded, not gated
      a=$(textsha "$SIDE/envoy-pgolto.unstripped"); b=$(textsha "$BIN/envoy-pgolto-relocs")
      log ".text sha256 pgolto=$a pgolto-relocs=$b"; if [ "$a" = "$b" ]; then stage pgolto-relocs TEXT-IDENTICAL; else stage pgolto-relocs TEXT-DIFFERS; fi
      mark pgolto-relocs
    else stage pgolto-relocs FAIL; fi
  fi
fi

# ---------------- 8. records ----------------
( cd "$WT" && pin bazel --output_base="$OB_OPT" version ) > "$R/bazel-version.txt" 2>&1
if [ -n "$TC" ]; then "$TC/clang" --version > "$R/clang-version.txt" 2>&1; "$TC/ld.lld" --version >> "$R/clang-version.txt" 2>&1; fi
log "toolchain: $(grep -m1 'Build label' "$R/bazel-version.txt") / $(head -1 "$R/clang-version.txt" 2>/dev/null)"
for f in "$BIN"/envoy-* "$SIDE"/*.unstripped; do
  [ -f "$f" ] && echo "$(basename "$f") $("$LX/bin/llvm-readelf" -SW "$f" | awk '$2==".text"{print "text_hex=" $6}')"
done | tee -a "$LOGF"
( cd "$BIN" && sha256sum -- * ) > "$W/SHA256SUMS.bins"; ( cd "$SIDE" && sha256sum -- * ) > "$W/SHA256SUMS.side"
log "stages: $(tr '\n' ' ' < "$W/stages.txt")"
diskok; fin 0
