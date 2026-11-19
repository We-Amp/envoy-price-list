#!/bin/bash
# The stats-flush row on the bench box (configs from make.py, box from boxes/$BOX.json).
#
#   run-session.sh calibrate [EPL_ARGS...]  step 0: one idle leg per rung for nosink and statsd
#                                          (N by kind, used share, start time, admin read times,
#                                          flush length, memory, fd peak), the 3M probe in a 10 min
#                                          box; rungs.json; the configs rewritten from it
#   run-session.sh smoke [EPL_ARGS...]      one round of every arm at its rungs, the main-thread
#                                          profile at 1M, the per-rung statsd interval from the
#                                          smoke's drops (configs rewritten), then check
#   run-session.sh check                    freeze each run's evidence from its smoke into
#                                          $RUNS/frozen/, check every smoke leg, recompute the budget
#   run-session.sh mfix [EPL_ARGS...]       run M-fix (two own builds, boxes with fix_binaries), after
#                                          the queue: freeze and check against its own smoke, then
#                                          mfix-10k, mfix-100k, mfix-1m within MFIX_STOP_S (default 80 min)
#   run-session.sh s-smoke [EPL_ARGS...]    run S (the sinks; needs rungs.json from calibrate): one round
#                                          at 100k, 1M and under load (smoke-s-100k, smoke-s-1m, smoke-sw),
#                                          then s-check
#   run-session.sh s-check                  freeze s-100k, s-1m and sw from their smokes and check every
#                                          smoke leg (no override)
#   run-session.sh s-queue [EPL_ARGS...]    s-check and the time estimate, then s-100k, s-1m and sw within S_STOP_S (default 3 h 30 min)
#   run-session.sh s-otlp-smoke [EPL_ARGS...] the 1M smoke again, checked for s-1m-otlp (after the
#                                          collector receive limit fix)
#   run-session.sh s-otlp [EPL_ARGS...]     s-1m-otlp (otlp and nosink-20s at 1M, 8 rounds) after it
#   run-session.sh lat-smoke [EPL_ARGS...]  run L (flush latency; needs rungs.json): the configs written
#                                          again (with $RUNS/lat-knobs.json when it exists: a cut or a
#                                          rate step), one round of the five cells with the queue's own
#                                          config and gates (smoke-lat), then lat-check
#   run-session.sh lat-check                every smoke leg valid, the queue config's evidence on the
#                                          smoke legs (nothing frozen), the unit tests on this Python,
#                                          lat_table.py on the smoke, the smoke rules and the budget;
#                                          a pass is recorded for this harness and config
#   run-session.sh lat-queue [EPL_ARGS...]  lat (5 rounds) within LAT_STOP_S (default 65 min); refuses
#                                          without a recorded lat-check of this harness and this lat.json
#   run-session.sh restore                  put net.core.rmem_max back to the recorded original (after
#                                          a session that was killed before its trap could run)
#   run-session.sh queue [EPL_ARGS...]      run M (10k, 100k, 1M), W, M at 300k, then S and X
#                                          only if they fit; PROBE10M=1 adds the 10M probe after
#                                          the queue in its own 30 min box if it still fits
#
# net.core.rmem_max: calibrate, smoke and queue raise it to GUARD_VALUE (256 MiB) for their
# own duration and restore the value they found on exit, failure, the hard stop or an
# operator's TERM (forwarded to the running child first; sysctl-guard.sh); a failed restore
# exits 70 and says so; they refuse to start when the value is not the one recorded at step 0.
#
# Queue rules: no start unless every config is calibrated and every smoke leg passes its run's
# frozen evidence (no override), and the mandatory part is at most 2 h 30 min (FORCE=1
# overrides only that, a decision the operator records). Hard stop STOP_S (default 3 h 15 min) after
# the queue starts: each run gets the time left and then SIGTERM through `timeout
# --foreground` (the harness process only). Before W the prediction from M at 100k decides
# whether W's nosink row is confirmatory (written to $RUNS/w-prediction.json).
#
# Runs go to $RUNS (default ~/epl/runs/stats-flush), progress to $RUNS/queue.log. Extra
# arguments go to every `epl` call.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/stats-flush
EPL="python3 $H/bin/epl"
SESSION="python3 $S/session.py"
BOX=${BOX:-bench-x86_64}
C=$S/$BOX
R=${RUNS:-$HOME/epl/runs/stats-flush}
FROZEN=$R/frozen
STOP_S=${STOP_S:-11700}
RUNGS="10k 100k 300k 1m"
MANDATORY="m-10k m-100k m-1m w m-300k"
OPTIONAL=${QUEUE_OPTIONAL-x-1m}
SRUNS="s-100k s-1m sw"
SSMOKES="smoke-s-100k smoke-s-1m smoke-sw"
MFIX="mfix-10k mfix-100k mfix-1m"
SMOKES="smoke-m-10k smoke-100k smoke-m-300k smoke-1m smoke-w"
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/queue.log"; }
GUARD_DIR=$R
# shellcheck source=sysctl-guard.sh
. "$S/sysctl-guard.sh"

smoke_of() {  # the smoke a run is checked against; the 5 s statsd fallback has a merged one
  local s
  case "$1" in
    m-10k) s=smoke-m-10k;; m-300k) s=smoke-m-300k;; w) s=smoke-w;;
    m-100k) s=smoke-100k;; m-1m|x-1m) s=smoke-1m;;
    s-100k) s=smoke-s-100k;; s-1m|s-1m-otlp) s=smoke-s-1m;; sw) s=smoke-sw;;
    mfix-*) s=smoke-$1;;
  esac
  if [ -d "$R/smoke/$s.statsd5" ]; then echo "$s.statsd5"; else echo "$s"; fi
}

rung_of_smoke() {
  case "$1" in smoke-m-10k) echo 10k;; smoke-100k) echo 100k;; smoke-m-300k) echo 300k;; smoke-1m) echo 1m;; esac
}

# The child of a run in the background, so an operator's TERM reaches this script at once: it
# forwards TERM to the child (timeout passes it on to the harness, which stops its own Envoy,
# client and containers) and the guard restores rmem_max before the script exits.
CHILD=
on_term() {
  if [ -n "$CHILD" ] && kill -0 "$CHILD" 2>/dev/null; then
    log "TERM: forwarding to the running child $CHILD"
    kill -TERM "$CHILD" 2>/dev/null
    wait "$CHILD" 2>/dev/null
  fi
  guard_end
  exit 143
}
bg_wait() {  # run a command in the background, wait for it, return its status
  "$@" &
  CHILD=$!
  wait "$CHILD"
  local rc=$?
  CHILD=
  return $rc
}

rewrite() {
  python3 "$S/make.py" --box "$S/boxes/$BOX.json" --rungs "$R/rungs.json" >> "$R/queue.log" 2>&1 \
    || { log "make.py failed"; exit 1; }
}

check() {
  local bad=0 run
  $SESSION calibrated "$C" | tee -a "$R/queue.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || bad=1
  mkdir -p "$FROZEN"
  for run in $MANDATORY $OPTIONAL; do
    log "freeze and check $run against $(smoke_of "$run")"
    if ! $EPL evidence-check "$C/$run.json" "$R/smoke/$(smoke_of "$run")" --freeze "$FROZEN/$run.json" \
        >> "$R/queue.log" 2>&1; then
      log "evidence-check $run FAILED (details in queue.log)"
      bad=1
    fi
  done
  $SESSION budget "$FROZEN" "$R/smoke" | tee -a "$R/queue.log"
  local brc=${PIPESTATUS[0]}
  [ "$brc" -eq 3 ] && log "mandatory part above 2 h 30 min: decide before the queue (FORCE=1 starts it)"
  [ "$brc" -ne 0 ] && [ "$brc" -ne 3 ] && bad=1
  return $(( bad ? 1 : (brc == 3 ? 3 : 0) ))
}

s_check() {
  local bad=0 run
  for run in $SRUNS; do
    if grep -q '"uncalibrated": true' "$C/$run.json"; then log "$run uncalibrated"; bad=1; fi
  done
  mkdir -p "$FROZEN"
  for run in $SRUNS; do
    # every smoke leg must be valid, not only its evidence
    $SESSION smoke-valid "$C/$(smoke_of "$run").json" "$R/smoke/$(smoke_of "$run")" 2>&1 | tee -a "$R/queue.log"
    [ "${PIPESTATUS[0]}" -eq 0 ] || bad=1
    log "freeze and check $run against $(smoke_of "$run")"
    if ! $EPL evidence-check "$C/$run.json" "$R/smoke/$(smoke_of "$run")" --freeze "$FROZEN/$run.json" \
        >> "$R/queue.log" 2>&1; then
      log "evidence-check $run FAILED (details in queue.log)"
      bad=1
    fi
  done
  return $bad
}

lat_check() {
  local bad=0
  local sm=$R/smoke/smoke-lat
  rm -f "$R/lat-check.json"
  if grep -q '"uncalibrated": true' "$C/lat.json"; then log "lat uncalibrated"; bad=1; fi
  # every smoke leg valid under the queue's own gates
  $SESSION smoke-valid "$C/smoke-lat.json" "$sm" 2>&1 | tee -a "$R/queue.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || bad=1
  # the queue config's evidence on the smoke legs; nothing is frozen: no expectation comes from the smoke
  if ! $EPL evidence-check "$C/lat.json" "$sm" >> "$R/queue.log" 2>&1; then
    log "evidence-check lat FAILED (details in queue.log)"
    bad=1
  fi
  if ! (cd "$H" && python3 -m unittest tests.test_latency) >> "$R/queue.log" 2>&1; then
    log "unit tests of run L FAILED on this Python (details in queue.log)"
    bad=1
  fi
  if ! python3 "$S/lat_table.py" "$sm" --min-rounds 1 --json "$R/smoke-lat-table.json" > "$R/smoke-lat-table.md" \
      2>> "$R/queue.log"; then
    log "lat_table.py did not run end to end on the smoke"
    bad=1
  fi
  $SESSION lat-rules "$C/lat.json" "$sm" 2>&1 | tee -a "$R/queue.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || bad=1
  if [ "$bad" = 0 ]; then
    $SESSION lat-stamp "$C/lat.json" "$R/lat-check.json" >> "$R/queue.log" 2>&1 || bad=1
  fi
  return $bad
}

rewrite_lat() {
  local knobs=()
  [ -f "$R/lat-knobs.json" ] && knobs=(--lat "$R/lat-knobs.json") && log "run L knobs: $(tr -d '\n' < "$R/lat-knobs.json")"
  python3 "$S/make.py" --box "$S/boxes/$BOX.json" --rungs "$R/rungs.json" ${knobs[@]+"${knobs[@]}"} >> "$R/queue.log" 2>&1 \
    || { log "make.py failed"; exit 1; }
}

mode=${1:-}
shift || true
case "$mode" in
  calibrate)
    log "calibrate start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX"
    guard_begin || exit 1
    trap on_term TERM INT
    for rung in $RUNGS; do
      for arm in nosink statsd; do
        log "calibrate $rung $arm"
        bg_wait $EPL stats-calibrate "$C/cal-$rung.json" --arm "$arm" --shapes "idle-$rung" --out "$R/cal/$rung-$arm" \
          --ready-timeout 600 --admin-timeout 300 "$@" >> "$R/queue.log" 2>&1
        log "end calibrate $rung $arm rc=$?"
      done
    done
    log "3M probe (10 min box, not measured)"
    bg_wait timeout --foreground --signal=TERM --kill-after=60 600 $EPL stats-calibrate "$C/cal-3m.json" --arm nosink \
      --shapes idle-3m --out "$R/cal/3m-nosink" --ready-timeout 540 --admin-timeout 300 "$@" >> "$R/queue.log" 2>&1
    log "end 3M probe rc=$?"
    $SESSION rungs "$R/rungs.json" "$R"/cal/*-nosink "$R"/cal/*-statsd >> "$R/queue.log" 2>&1
    rewrite
    log "calibrate done; rungs in $R/rungs.json"
    ;;
  smoke)
    log "smoke start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX"
    guard_begin || exit 1
    trap on_term TERM INT
    mkdir -p "$R/smoke"
    for s in $SMOKES; do
      log "start $s"
      bg_wait $EPL run "$C/$s.json" --out "$R/smoke/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end $s rc=$?"
    done
    for s in smoke-mfix-10k smoke-mfix-100k smoke-mfix-1m; do
      [ -f "$C/$s.json" ] || continue
      log "start $s"
      bg_wait $EPL run "$C/$s.json" --out "$R/smoke/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end $s rc=$?"
    done
    log "main-thread profile at 1M (not measured)"
    bg_wait $EPL flush-profile "$C/m-1m.json" --arm nosink --shape idle-1m --out "$R/profile-1m" "$@" >> "$R/queue.log" 2>&1
    log "end profile rc=$?"
    $SESSION statsd-interval "$R/rungs.json" "$R"/smoke/smoke-* >> "$R/queue.log" 2>&1
    rewrite
    # the 5 s fallback: smoke the rung's statsd arm again at 5 s and check against that leg
    for s in smoke-m-10k smoke-100k smoke-m-300k smoke-1m; do
      rung=$(rung_of_smoke "$s")
      if [ -f "$C/smoke-statsd5-$rung.json" ]; then
        log "statsd at 5 s for $rung: smoke again"
        rm -rf "$R/smoke/smoke-statsd5-$rung" "$R/smoke/$s.statsd5"
        bg_wait $EPL run "$C/smoke-statsd5-$rung.json" --out "$R/smoke/smoke-statsd5-$rung" --allow-short "$@" \
          >> "$R/queue.log" 2>&1
        $SESSION merge-smoke "$R/smoke/$s.statsd5" "$R/smoke/$s" "$R/smoke/smoke-statsd5-$rung" statsd \
          >> "$R/queue.log" 2>&1
      fi
    done
    check
    log "smoke done rc=$?"
    ;;
  check)
    check
    exit $?
    ;;
  s-smoke)
    log "S smoke start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX"
    [ -f "$R/rungs.json" ] || { log "no rungs.json: calibrate first"; exit 1; }
    rewrite
    guard_begin || exit 1
    trap on_term TERM INT
    for s in $SSMOKES; do
      log "smoke $s"
      rm -rf "$R/smoke/$s"
      bg_wait $EPL run "$C/$s.json" --out "$R/smoke/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end smoke $s rc=$?"
    done
    guard_end
    trap - TERM INT
    s_check
    log "S smoke done rc=$?"
    ;;
  s-otlp-smoke)
    # the 1M smoke again (after the collector's receive limit was raised), then its check
    log "S 1M smoke start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX"
    rewrite
    guard_begin || exit 1
    trap on_term TERM INT
    # the first 1M smoke is the record of the OTLP loss: moved aside, never deleted
    if [ -d "$R/smoke/smoke-s-1m" ]; then
      aside="$R/smoke/smoke-s-1m.first"
      [ -e "$aside" ] && aside="$R/smoke/smoke-s-1m.$(date -u +%Y%m%dT%H%M%SZ)"
      mv "$R/smoke/smoke-s-1m" "$aside" && log "previous 1M smoke kept as $aside"
    fi
    bg_wait $EPL run "$C/smoke-s-1m.json" --out "$R/smoke/smoke-s-1m" --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end smoke smoke-s-1m rc=$?"
    guard_end
    trap - TERM INT
    SRUNS="s-1m-otlp" s_check
    log "S 1M smoke done rc=$?"
    ;;
  s-otlp)
    # the 1M otlp row again: otlp and nosink-20s, 8 rounds, after a clean 1M smoke
    log "S otlp re-run start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX args: $*"
    SRUNS="s-1m-otlp" s_check || { log "S otlp re-run not started (smoke or evidence; no override)"; exit 1; }
    guard_begin || exit 1
    trap on_term TERM INT
    L=${S_STOP_S:-5400}
    log "start s-1m-otlp (${L}s stop)"
    bg_wait timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$FROZEN/s-1m-otlp.json" \
      --out "$R/s-1m-otlp" --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end s-1m-otlp rc=$?"
    ;;
  s-check)
    s_check
    exit $?
    ;;
  s-queue)
    log "S queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX args: $*"
    s_check || { log "S queue not started (calibration or evidence; no override)"; exit 1; }
    STOP_S=${S_STOP_S:-12600}
    $SESSION s-budget "$C" "$R/smoke" "$STOP_S" 2>&1 | tee -a "$R/queue.log"
    [ "${PIPESTATUS[0]}" -eq 0 ] || { log "S queue not started: expected time above the stop or unknown"; exit 1; }
    guard_begin || exit 1
    trap on_term TERM INT
    T0=$(date +%s)
    left() { echo $(( STOP_S - ($(date +%s) - T0) )); }
    for run in $SRUNS; do
      L=$(left)
      if [ "$L" -le 60 ]; then
        log "skip $run: S stop reached"
        continue
      fi
      log "start $run (${L}s left before the S stop)"
      bg_wait timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$FROZEN/$run.json" \
        --out "$R/$run" --allow-short "$@" >> "$R/queue.log" 2>&1
      rc=$?
      [ "$rc" -eq 124 ] && log "$run stopped at the S stop (SIGTERM); partial results, incomplete"
      log "end $run rc=$rc"
    done
    log "S queue done"
    ;;
  lat-smoke)
    log "L smoke start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX"
    [ -f "$R/rungs.json" ] || { log "no rungs.json: calibrate first"; exit 1; }
    rewrite_lat
    guard_begin || exit 1
    trap on_term TERM INT
    mkdir -p "$R/smoke"
    # an earlier smoke is kept beside the new one, never deleted
    if [ -d "$R/smoke/smoke-lat" ]; then
      aside="$R/smoke/smoke-lat.$(date -u +%Y%m%dT%H%M%SZ)"
      mv "$R/smoke/smoke-lat" "$aside" && log "previous L smoke kept as $aside"
    fi
    log "smoke smoke-lat"
    bg_wait $EPL run "$C/smoke-lat.json" --out "$R/smoke/smoke-lat" --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end smoke smoke-lat rc=$?"
    guard_end
    trap - TERM INT
    lat_check
    log "L smoke done rc=$?"
    ;;
  lat-check)
    lat_check
    rc=$?
    log "L check rc=$rc"
    exit $rc
    ;;
  lat-queue)
    log "L queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX args: $*"
    # the check that passed must be of this harness and this lat.json (the configs are not rewritten here)
    $SESSION lat-stamp-ok "$C/lat.json" "$R/lat-check.json" 2>&1 | tee -a "$R/queue.log"
    [ "${PIPESTATUS[0]}" -eq 0 ] || { log "L queue not started: no passed lat-check of this harness and config (no override)"; exit 1; }
    guard_begin || exit 1
    trap on_term TERM INT
    L=${LAT_STOP_S:-3900}
    log "start lat (${L}s stop)"
    bg_wait timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$C/lat.json" \
      --out "$R/lat" --allow-short "$@" >> "$R/queue.log" 2>&1
    rc=$?
    [ "$rc" -eq 124 ] && log "lat stopped at the L stop (SIGTERM); only complete rounds count, under 4 is incomplete"
    log "end lat rc=$rc; table: python3 $S/lat_table.py $R/lat --json $R/lat-table.json > $R/lat-table.md"
    ;;
  restore)
    guard_restore
    exit $?
    ;;
  mfix)
    log "M-fix start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX args: $*"
    bad=0
    $SESSION calibrated "$C" | tee -a "$R/queue.log"
    for run in $MFIX; do
      [ -f "$C/$run.json" ] || { log "no $run config (box without fix_binaries)"; exit 1; }
      if grep -q '"uncalibrated": true' "$C/$run.json"; then log "$run uncalibrated"; bad=1; fi
      log "freeze and check $run against $(smoke_of "$run")"
      if ! $EPL evidence-check "$C/$run.json" "$R/smoke/$(smoke_of "$run")" --freeze "$FROZEN/$run.json" \
          >> "$R/queue.log" 2>&1; then
        log "evidence-check $run FAILED (details in queue.log)"
        bad=1
      fi
    done
    [ "$bad" = 0 ] || { log "M-fix not started (calibration or evidence; no override)"; exit 1; }
    guard_begin || exit 1
    trap on_term TERM INT
    STOP_S=${MFIX_STOP_S:-4800}
    T0=$(date +%s)
    left() { echo $(( STOP_S - ($(date +%s) - T0) )); }
    for run in $MFIX; do
      L=$(left)
      if [ "$L" -le 60 ]; then
        log "skip $run: M-fix stop reached"
        continue
      fi
      log "start $run (${L}s left before the M-fix stop)"
      bg_wait timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$FROZEN/$run.json" \
        --out "$R/$run" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end $run rc=$?"
    done
    log "M-fix done"
    ;;
  queue)
    log "queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX args: $*"
    check
    rc=$?
    if [ "$rc" -eq 3 ] && [ "${FORCE:-0}" = 1 ]; then
      log "mandatory part above 2 h 30 min: FORCE=1 given, starting"
    elif [ "$rc" -ne 0 ]; then
      log "queue not started (check rc=$rc: 1 = calibration or evidence, no override; 3 = budget)"
      exit 1
    fi
    guard_begin || exit 1
    trap on_term TERM INT
    T0=$(date +%s)
    left() { echo $(( STOP_S - ($(date +%s) - T0) )); }
    runone() {
      local run=$1 L
      shift
      L=$(left)
      if [ "$L" -le 60 ]; then
        log "skip $run: session stop reached"
        return
      fi
      log "start $run (${L}s left before the stop)"
      bg_wait timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$FROZEN/$run.json" \
        --out "$R/$run" --allow-short "$@" >> "$R/queue.log" 2>&1
      local rc=$?
      [ "$rc" -eq 124 ] && log "$run stopped at the session stop (SIGTERM); partial results, incomplete"
      log "end $run rc=$rc"
    }
    for run in $MANDATORY; do
      if [ "$run" = w ]; then
        $SESSION predict-w "$R/m-100k" "$R/smoke/smoke-w" > "$R/w-prediction.json" 2>> "$R/queue.log"
        log "run W prediction: $(tr -d '\n' < "$R/w-prediction.json")"
      fi
      runone "$run" "$@"
    done
    for run in $OPTIONAL; do
      E=$($SESSION expected "$run" "$FROZEN" "$R/smoke")
      L=$(left)
      if [ "$E" -le "$L" ]; then
        runone "$run" "$@"
      else
        log "skip $run: expected ${E}s does not fit in the ${L}s left"
      fi
    done
    if [ "${PROBE10M:-0}" = 1 ]; then
      L=$(left)
      if [ "$L" -ge 1800 ]; then
        log "10M probe (30 min box, not a priced row)"
        bg_wait timeout --foreground --signal=TERM --kill-after=60 1800 $EPL stats-calibrate "$C/cal-10m.json" --arm nosink \
          --shapes idle-10m --out "$R/cal/10m-nosink" --ready-timeout 1500 --admin-timeout 600 "$@" \
          >> "$R/queue.log" 2>&1
        log "end 10M probe rc=$?"
      else
        log "skip the 10M probe: ${L}s left, it needs 1800"
      fi
    fi
    log "queue done; tables: python3 $S/table.py $R > $R/tables.md"
    ;;
  *)
    sed -n '2,30p' "$0"
    exit 2
    ;;
esac
