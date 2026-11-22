#!/bin/bash
# shellcheck disable=SC2054,SC2012  # commas are inside linker flags; ls -l output is a log record
# Build the code-layout arms of Envoy v1.40.2, all with the release options
# (-c opt --stripopt=--strip-all --linkopt=-Wl,--compress-debug-sections=zlib):
#   opt            plain -c opt (stripped = the release binary; unstripped + .dwp kept as side files)
#   order          opt relinked with an lld call-graph ordering file from LBR legs of the official
#                  binary (== opt stripped), cdsort
#   autofdo        sampled PGO: llvm-profgen (LLVM 22.1.8 release) on the same LBR legs, + ThinLTO
#   pgolto         instrumented PGO (nine-leg trainer of pgo-recipe-v1, run here) + ThinLTO
#   pgolto-relocs  pgolto relinked with --emit-relocs (the BOLT input; same .text checked); BOLT smoke
#
#   build-arms.sh
#
# Settings (environment): see common.sh and README.md. Stage-specific:
#   LBR_A_DIR   LBR legs of the official binary, one per shape: lbr-s.data, lbr-fh.data, lbr-fl.data
#               (default $W2_WORK/prof/a). Without them, order and autofdo are skipped.
#   NIGHTHAWK   nighthawk_client binary for the PGO trainer (required for pgolto)
#   ENVOY_CPUS, ORIGIN_CPUS, CLIENT_CPUS, HTTP_PORT, H3_PORT, ORIGIN_PORT: passed to the trainer
#               (tools/pgo/train.sh of pgo-recipe-v1) through the environment; ports default to
#               29080, 29443 and 29081.
# Exit code also in $W2_WORK/rc: 0 done, 3 disk stop, 4 setup failed. Per-stage status in stages.txt,
# sha256/size/version of every binary in logs/bins.txt, sums in SHA256SUMS.bins / SHA256SUMS.side.
set -u
# shellcheck source-path=SCRIPTDIR source=common.sh
. "$(dirname "$0")/common.sh"
R=$W/logs; BIN=$W/bins; SIDE=$W/side; PROF=$W/prof; OB=$W/ob
LBR_A_DIR=${LBR_A_DIR:-$PROF/a}
NIGHTHAWK=${NIGHTHAWK:-}
mkdir -p "$R" "$BIN" "$SIDE" "$PROF" "$W/tmp"; export TMPDIR=$W/tmp
TC=
log() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "$R/driver.log"; }
stage() { echo "$1 $2" >> "$W/stages.txt"; log "STAGE $1 $2"; }
stopall() { [ -d "$OB" ] && ( cd "$WT" && pin bazel --output_base="$OB" shutdown ) >> "$R/shutdown.log" 2>&1; }
diskok() {
  local a u; a=$(avail); u=$(du -s -BG "$W" 2>/dev/null | cut -f1 | tr -dc 0-9)
  log "disk avail=${a}G used_by_us=${u}G load=$(cut -d' ' -f1-3 /proc/loadavg) mem_avail=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)G"
  if [ "$a" -lt "$DISK_FLOOR_G" ]; then log "DISK-STOP (floor ${DISK_FLOOR_G}G)"; stopall; echo 3 > "$W/rc"; exit 3; fi
}
summ() { strip_ansi "$1" | grep -E "error:|^ERROR|Elapsed time|Build completed|Build did NOT|INFO: Found" | head -40 | tee -a "$R/driver.log"; }
bb() { ( cd "$WT" && pin bazel --output_base="$OB" info "${COMMON[@]}" "$@" bazel-bin 2>/dev/null ); }
# build NAME FLAGS... -- TARGETS...
build() {
  local name=$1; shift; local flags=() t=()
  while [ $# -gt 0 ] && [ "$1" != -- ]; do flags+=("$1"); shift; done; shift; t=("$@")
  diskok; log "BUILD $name start: ${flags[*]} ${t[*]}"; local s=$SECONDS
  ( cd "$WT" && pin bazel --output_base="$OB" build "${COMMON[@]}" "${flags[@]}" "${t[@]}" ) > "$R/build-$name.log" 2>&1
  local rc=$?; log "BUILD $name rc=$rc wall=$((SECONDS-s))s"; summ "$R/build-$name.log"; return $rc
}
rec() {  # rec ARM FILE: sha256, size, version
  ( cd "$(dirname "$2")" && sha256sum "$(basename "$2")" ) | sed "s|^|$1 |" | tee -a "$R/bins.txt" "$R/driver.log"
  echo "$1 size $(stat -c %s "$2")" | tee -a "$R/bins.txt"
  pin "$2" --version 2>&1 | grep -m1 version | sed "s|^|$1 |" | tee -a "$R/bins.txt" "$R/driver.log"
}
textsha() { "$TC/llvm-objcopy" --dump-section .text="$W/tmp/text.bin" "$1" "$W/tmp/discard.o" 2>/dev/null && sha256sum "$W/tmp/text.bin" | cut -c1-16; rm -f "$W/tmp/text.bin" "$W/tmp/discard.o"; }
nm_of() { "$TC/llvm-nm" --defined-only --numeric-sort --print-size --no-demangle "$1" > "$2"; }

log "START nproc=$(nproc)"; diskok
# ---------------- 0. setup ----------------
if [ ! -d "$SRC" ]; then
  fetch_source || { log "FETCH-FAIL"; echo 4 > "$W/rc"; exit 4; }
  # the trainer kit (tools/pgo) from the public fork's pgo-recipe-v1, used as plain scripts
  git -C "$SRC" fetch -q --depth 1 https://github.com/We-Amp/envoy.git refs/heads/pgo-recipe-v1 || { log "FORK-FETCH-FAIL"; echo 4 > "$W/rc"; exit 4; }
  log "pgo-recipe-v1 = $(git -C "$SRC" rev-parse --short=10 FETCH_HEAD)"
  mkdir -p "$W/pgo-tools" && git -C "$SRC" archive FETCH_HEAD tools/pgo | tar -x -C "$W/pgo-tools"
fi
log "v1.40.2 = $(git -C "$SRC" rev-parse --short=10 'refs/tags/v1.40.2^{commit}'); wt status lines=$(git -C "$WT" status --porcelain | wc -l)"
if [ ! -x "$LX/bin/llvm-profgen" ]; then
  ( cd "$W" && curl -sSfL -o "$LLVM_TGZ" "https://github.com/llvm/llvm-project/releases/download/llvmorg-$LLVM_VER/$LLVM_TGZ" ) || log "LLVM-DOWNLOAD-FAIL"
  got=$(sha256sum "$W/$LLVM_TGZ" 2>/dev/null | cut -d' ' -f1)
  if [ "$got" = "$LLVM_SHA" ]; then
    log "LLVM tarball sha256 OK; members with profgen/bolt:"; tar -tJf "$W/$LLVM_TGZ" > "$R/llvm-members.txt"
    grep -E "bin/(llvm-profgen|llvm-bolt|perf2bolt|merge-fdata|llvm-profdata)$|lib/libLLVM|lib/libbolt_rt" "$R/llvm-members.txt" | tee -a "$R/driver.log"
    mkdir -p "$LX" && tar -xJf "$W/$LLVM_TGZ" -C "$LX" --strip-components=1 --wildcards \
      '*/bin/llvm-profgen' '*/bin/llvm-bolt' '*/bin/perf2bolt' '*/bin/merge-fdata' '*/bin/llvm-profdata' '*/lib/libLLVM*' '*/lib/libbolt_rt*' 2>> "$R/setup.log"
    rm -f "${W:?}/$LLVM_TGZ"
  else log "LLVM tarball sha256 MISMATCH or missing ($got)"; rm -f "${W:?}/$LLVM_TGZ"; fi
fi
for t in llvm-profgen llvm-bolt perf2bolt merge-fdata llvm-profdata; do
  if [ -e "$LX/bin/$t" ]; then log "tool $t: $("$LX/bin/$t" --version 2>&1 | grep -m1 -i version)"; ldd "$LX/bin/$t" 2>&1 | grep -i "not found" | sed "s|^|$t ldd |" | tee -a "$R/driver.log"
  else log "tool $t: ABSENT in the release tarball"; fi
done
"$LX/bin/llvm-profgen" --help 2>&1 | grep -E "^\s+--(dwp|binary|perfscript|format)" | tee -a "$R/driver.log"

# ---------------- 1. opt (control) ----------------
if build opt "${REL[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static; then
  BB=$(bb "${REL[@]}"); TC=$(ls -d "$OB"/external/+envoy_llvm_extension+llvm_toolchain_llvm/bin)
  cp -L "$BB/source/exe/envoy-static.stripped" "$BIN/envoy-opt"; cp -L "$BB/source/exe/envoy-static" "$SIDE/envoy-opt.unstripped"
  chmod 755 "$BIN/envoy-opt" "$SIDE/envoy-opt.unstripped"; rec opt "$BIN/envoy-opt"; rec opt-unstripped "$SIDE/envoy-opt.unstripped"
  if [ "$(sha256sum "$BIN/envoy-opt" | cut -d' ' -f1)" = "$OFFICIAL_SHA" ]; then stage opt MATCHES-OFFICIAL; else stage opt DIFFERS-FROM-OFFICIAL; fi
  log "function sections in a sample object: $(f=$(find "$BB/source/common/http" -name 'conn_manager_impl*.o' | head -1); echo "$f"; "$TC/llvm-readelf" -SW "$f" | grep -c ' \.text\.')"
  "$TC/llvm-readelf" -n "$SIDE/envoy-opt.unstripped" | grep -i "build id" | sed 's/^/opt-unstripped /' | tee -a "$R/driver.log"
  "$TC/llvm-readelf" -SW "$SIDE/envoy-opt.unstripped" | grep -E " \.text | \.debug_info " | tee -a "$R/driver.log"
  nm_of "$SIDE/envoy-opt.unstripped" "$SIDE/envoy-opt.nm"
  # split DWARF side file for llvm-profgen's inline frames
  if build opt-dwp "${REL[@]}" -- //source/exe:envoy-static.dwp; then cp -L "$BB/source/exe/envoy-static.dwp" "$SIDE/envoy-opt.dwp"; ls -l "$SIDE/envoy-opt.dwp" | tee -a "$R/driver.log"; stage opt-dwp OK; else stage opt-dwp FAIL; fi
else stage opt FAIL; log "opt failed: nothing else can be built"; stopall; echo 4 > "$W/rc"; exit 4; fi

# ---------------- 2. profiles from the LBR legs of the official binary ----------------
PROF_OK=0
if grep -q "opt MATCHES-OFFICIAL" "$W/stages.txt"; then
  mkdir -p "$PROF/pbin" && cp "$SIDE/envoy-opt.unstripped" "$PROF/pbin/envoy-1.40.2"   # profgen matches the mmap basename
  [ -f "$SIDE/envoy-opt.dwp" ] && ln -sf "$SIDE/envoy-opt.dwp" "$PROF/pbin/envoy-1.40.2.dwp"
  for sh in s fh fl; do
    f=$LBR_A_DIR/lbr-$sh.data; [ -f "$f" ] || { log "missing $f"; continue; }
    log "$sh perf build-id: $("$PERF" buildid-list -i "$f" 2>/dev/null | grep envoy-1.40.2)"
    "$PERF" script -i "$f" --show-mmap-events -F ip,brstack > "$PROF/$sh.script" 2> "$R/perfscript-$sh.err"
    log "$sh perf script rc=$? lines=$(wc -l < "$PROF/$sh.script")"
  done
  python3 -I "$HERE/lbr2order.py" edges "$PROF/pbin/envoy-1.40.2" "$SIDE/envoy-opt.nm" "$PROF/order" "$PROF/s.script" "$PROF/fh.script" "$PROF/fl.script" > "$R/order-edges.json" 2> "$R/order-edges.err"
  orc=$?; log "lbr2order rc=$orc edges=$(wc -l < "$PROF/order/cg.txt" 2>/dev/null)"; tee -a "$R/driver.log" < "$R/order-edges.err"
  if [ $orc -eq 0 ]; then stage order-file OK; else stage order-file FAIL; fi
  DWP=(); [ -f "$SIDE/envoy-opt.dwp" ] && "$LX/bin/llvm-profgen" --help 2>&1 | grep -q -- "--dwp" && DWP=(--dwp="$SIDE/envoy-opt.dwp")
  pr=()
  for sh in s fh fl; do
    [ -s "$PROF/$sh.script" ] || continue
    pin "$LX/bin/llvm-profgen" --format=extbinary --binary="$PROF/pbin/envoy-1.40.2" ${DWP[@]+"${DWP[@]}"} \
      --ignore-stack-samples --perfscript="$PROF/$sh.script" --output="$PROF/$sh.afdo" > "$R/profgen-$sh.log" 2>&1
    log "profgen $sh rc=$? size=$(stat -c %s "$PROF/$sh.afdo" 2>/dev/null)"; tail -5 "$R/profgen-$sh.log" | tee -a "$R/driver.log"
    [ -s "$PROF/$sh.afdo" ] && pr+=("$PROF/$sh.afdo")
  done
  if [ ${#pr[@]} -eq 3 ]; then
    "$LX/bin/llvm-profdata" merge --sample --extbinary -o "$PROF/envoy.afdo" "${pr[@]}" > "$R/afdo-merge.log" 2>&1 && PROF_OK=1
    "$LX/bin/llvm-profdata" show --sample --topn=40 "$PROF/envoy.afdo" > "$R/afdo-show.txt" 2>&1
    "$LX/bin/llvm-profdata" show --sample --show-sec-info-only "$PROF/envoy.afdo" >> "$R/afdo-show.txt" 2>&1
    head -60 "$R/afdo-show.txt" >> "$R/driver.log"
  fi
  if [ $PROF_OK = 1 ]; then stage afdo-profile OK; else stage afdo-profile FAIL; fi
else log "opt differs from the official binary: the official binary's LBR legs do not describe it; order/autofdo need LBR legs of this opt build"; fi
cp "$HERE/lbr2order.py" "$PROF/" 2>/dev/null

# ---------------- 3. order: relink of the opt objects with the ordering file ----------------
if grep -q "order-file OK" "$W/stages.txt"; then
  ORD=(--linkopt=-Wl,--call-graph-ordering-file="$PROF/order/cg.txt" --linkopt=-Wl,--call-graph-profile-sort=cdsort)
  if build order "${REL[@]}" "${ORD[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static; then
    BB=$(bb "${REL[@]}" "${ORD[@]}")
    cp -L "$BB/source/exe/envoy-static.stripped" "$BIN/envoy-order"; cp -L "$BB/source/exe/envoy-static" "$SIDE/envoy-order.unstripped"
    chmod 755 "$BIN/envoy-order" "$SIDE/envoy-order.unstripped"; rec order "$BIN/envoy-order"
    grep -c "warning:" "$R/build-order.log" | sed 's/^/order link warnings: /' | tee -a "$R/driver.log"
    strip_ansi "$R/build-order.log" | grep -m5 "warning:" | tee -a "$R/driver.log"
    nm_of "$SIDE/envoy-order.unstripped" "$SIDE/envoy-order.nm"
    python3 -I "$HERE/lbr2order.py" span "$PROF/order/hot.json" "$SIDE/envoy-opt.nm" opt > "$R/span-opt.json"
    python3 -I "$HERE/lbr2order.py" span "$PROF/order/hot.json" "$SIDE/envoy-order.nm" order > "$R/span-order.json"
    cat "$R/span-opt.json" "$R/span-order.json" >> "$R/driver.log"; stage order OK
  else stage order FAIL; fi
fi

# ---------------- 4. autofdo: sampled profile + ThinLTO ----------------
if [ $PROF_OK = 1 ]; then
  AF=(--copt=-fprofile-sample-use="$PROF/envoy.afdo" --copt=-Wno-backend-plugin)
  if build autofdo "${REL[@]}" "${THIN[@]}" "${AF[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static; then
    BB=$(bb "${REL[@]}" "${THIN[@]}" "${AF[@]}")
    cp -L "$BB/source/exe/envoy-static.stripped" "$BIN/envoy-autofdo"; cp -L "$BB/source/exe/envoy-static" "$SIDE/envoy-autofdo.unstripped"
    chmod 755 "$BIN/envoy-autofdo" "$SIDE/envoy-autofdo.unstripped"; rec autofdo "$BIN/envoy-autofdo"
    nm_of "$SIDE/envoy-autofdo.unstripped" "$SIDE/envoy-autofdo.nm"
    python3 -I "$HERE/lbr2order.py" span "$PROF/order/hot.json" "$SIDE/envoy-autofdo.nm" autofdo > "$R/span-autofdo.json"; cat "$R/span-autofdo.json" >> "$R/driver.log"
    stage autofdo OK
  else stage autofdo FAIL; fi
fi

# ---------------- 5. pgolto: instrumented build, nine-leg training here, merge, optimized build ----------------
INST=(-c opt --copt=-fprofile-generate --linkopt=-fprofile-generate)
if [ -z "$NIGHTHAWK" ]; then
  log "NIGHTHAWK not set: pgolto and pgolto-relocs skipped"; stage inst SKIPPED
elif build inst "${INST[@]}" -- //source/exe:envoy-static; then
  cp -L "$(bb "${INST[@]}")/source/exe/envoy-static" "$W/envoy-instrumented"; chmod 755 "$W/envoy-instrumented"; rec inst "$W/envoy-instrumented"
  stage inst OK
  log "TRAIN start (nine legs x 60 s; Envoy ${ENVOY_CPUS:-trainer default}, origin ${ORIGIN_CPUS:-trainer default}, client ${CLIENT_CPUS:-trainer default})"; s=$SECONDS
  ( export HTTP_PORT=${HTTP_PORT:-29080} H3_PORT=${H3_PORT:-29443} ORIGIN_PORT=${ORIGIN_PORT:-29081}
    bash "$W/pgo-tools/tools/pgo/train.sh" --envoy "$W/envoy-instrumented" --origin-envoy "$BIN/envoy-opt" \
      --nighthawk "$NIGHTHAWK" --out "$W/train" --duration 60 ) > "$R/train.log" 2>&1
  trc=$?; nprof=$(find "$W/train/profiles" -maxdepth 1 -name '*.profraw' 2>/dev/null | wc -l)
  log "TRAIN rc=$trc wall=$((SECONDS-s))s profiles=$nprof"; cat "$W/train/legs.txt" >> "$R/driver.log" 2>/dev/null
  cp "$W/train/legs.txt" "$R/train-legs.txt" 2>/dev/null
  if [ $trc -eq 0 ] && [ "$nprof" -eq 9 ]; then
    mkdir -p "$W/pgo"; "$TC/llvm-profdata" merge -output="$W/pgo/envoy.profdata" "$W"/train/profiles/*.profraw > "$R/pgo-merge.log" 2>&1
    log "merge rc=$? size=$(stat -c %s "$W/pgo/envoy.profdata" 2>/dev/null)"; stage train OK
  else stage train FAIL; fi
  rm -rf "$W/train/profiles" "$W/train/staging" "$W/train/origin-profile"   # ~35 MB per profraw
else stage inst FAIL; fi
if grep -q "train OK" "$W/stages.txt"; then
  PG=(--fdo_optimize="$W/pgo/envoy.profdata" "${THIN[@]}")
  if build pgolto "${REL[@]}" "${PG[@]}" -- //source/exe:envoy-static.stripped //source/exe:envoy-static; then
    BB=$(bb "${REL[@]}" "${PG[@]}")
    cp -L "$BB/source/exe/envoy-static.stripped" "$BIN/envoy-pgolto"; cp -L "$BB/source/exe/envoy-static" "$SIDE/envoy-pgolto.unstripped"
    chmod 755 "$BIN/envoy-pgolto" "$SIDE/envoy-pgolto.unstripped"; rec pgolto "$BIN/envoy-pgolto"
    nm_of "$SIDE/envoy-pgolto.unstripped" "$SIDE/envoy-pgolto.nm"
    python3 -I "$HERE/lbr2order.py" span "$PROF/order/hot.json" "$SIDE/envoy-pgolto.nm" pgolto > "$R/span-pgolto.json" 2>&1; cat "$R/span-pgolto.json" >> "$R/driver.log"
    stage pgolto OK
    # ---- 6. BOLT input: the same link with --emit-relocs (debug stripped, symbols and relocations kept)
    RL=(--linkopt=-Wl,--emit-relocs)
    if build pgolto-relocs "${REL[@]}" "${PG[@]}" "${RL[@]}" -- //source/exe:envoy-static; then
      "$TC/llvm-objcopy" --strip-debug "$(bb "${REL[@]}" "${PG[@]}" "${RL[@]}")/source/exe/envoy-static" "$BIN/envoy-pgolto-relocs"
      chmod 755 "$BIN/envoy-pgolto-relocs"; rec pgolto-relocs "$BIN/envoy-pgolto-relocs"
      a=$(textsha "$SIDE/envoy-pgolto.unstripped"); b=$(textsha "$BIN/envoy-pgolto-relocs")
      log ".text sha256 pgolto=$a pgolto-relocs=$b"; if [ "$a" = "$b" ]; then stage pgolto-relocs TEXT-IDENTICAL; else stage pgolto-relocs TEXT-DIFFERS; fi
      # BOLT smoke without a profile: can BOLT rewrite this binary at all (tcmalloc rseq skip list)?
      BOLT=$LX/bin/llvm-bolt; [ -x "$BOLT" ] || BOLT=${BOLT_FALLBACK:-/usr/bin/llvm-bolt-20}
      pin "$BOLT" "$BIN/envoy-pgolto-relocs" -o "$W/tmp/envoy-bolt-smoke" --reorder-blocks=ext-tsp --reorder-functions=cdsort \
        --split-functions --split-all-cold --split-eh --icf=1 \
        --skip-funcs="$SKIP_FUNCS" > "$R/bolt-smoke.log" 2>&1
      brc=$?; log "BOLT smoke ($BOLT, no profile) rc=$brc"; tail -15 "$R/bolt-smoke.log" | tee -a "$R/driver.log"
      if [ $brc -eq 0 ]; then "$W/tmp/envoy-bolt-smoke" --version 2>&1 | grep -m1 version | tee -a "$R/driver.log"; stage bolt-smoke OK; else stage bolt-smoke FAIL; fi
      rm -f "$W/tmp/envoy-bolt-smoke"
    else stage pgolto-relocs FAIL; fi
  else stage pgolto FAIL; fi
fi

# ---------------- 7. records ----------------
( cd "$WT" && pin bazel --output_base="$OB" version ) > "$R/bazel-version.txt" 2>&1
"$TC/clang" --version > "$R/clang-version.txt" 2>&1; "$TC/ld.lld" --version >> "$R/clang-version.txt" 2>&1
log "toolchain: $(grep -m1 'Build label' "$R/bazel-version.txt") / $(head -1 "$R/clang-version.txt") / $(tail -1 "$R/clang-version.txt")"
for f in "$BIN"/* "$SIDE"/*.unstripped; do echo "$(basename "$f") $("$TC/llvm-readelf" -SW "$f" | awk '$2==".text"{print "text_hex=" $6}')"; done | tee -a "$R/driver.log"
( cd "$BIN" && sha256sum -- * ) > "$W/SHA256SUMS.bins"; ( cd "$SIDE" && sha256sum -- * ) > "$W/SHA256SUMS.side"
diskok; stopall; log "shutdown done"; log "DRIVER-DONE"
echo 0 > "$W/rc"
