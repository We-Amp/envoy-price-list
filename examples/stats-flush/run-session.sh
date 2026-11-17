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
#   run-session.sh queue [EPL_ARGS...]      run M (10k, 100k, 1M), W, M at 300k, then S and X
#                                          only if they fit; PROBE10M=1 adds the 10M probe after
#                                          the queue in its own 30 min box if it still fits
#
# net.core.rmem_max: calibrate, smoke and queue raise it to GUARD_VALUE (256 MiB) for their
# own duration and restore the value they found on exit, failure or the hard stop
# (sysctl-guard.sh); they refuse to start when the value is not the one recorded at step 0.
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
OPTIONAL="s-100k s-1m x-1m"
SMOKES="smoke-m-10k smoke-100k smoke-m-300k smoke-1m smoke-w"
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/queue.log"; }
GUARD_DIR=$R
# shellcheck source=sysctl-guard.sh
. "$S/sysctl-guard.sh"

smoke_of() {
  case "$1" in
    m-10k) echo smoke-m-10k;; m-300k) echo smoke-m-300k;; w) echo smoke-w;;
    m-100k|s-100k) echo smoke-100k;; m-1m|s-1m|x-1m) echo smoke-1m;;
  esac
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

mode=${1:-}
shift || true
case "$mode" in
  calibrate)
    log "calibrate start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX"
    guard_begin || exit 1
    for rung in $RUNGS; do
      for arm in nosink statsd; do
        log "calibrate $rung $arm"
        $EPL stats-calibrate "$C/cal-$rung.json" --arm "$arm" --shapes "idle-$rung" --out "$R/cal/$rung-$arm" \
          --ready-timeout 600 --admin-timeout 300 "$@" >> "$R/queue.log" 2>&1
        log "end calibrate $rung $arm rc=$?"
      done
    done
    log "3M probe (10 min box, not measured)"
    timeout --foreground --signal=TERM --kill-after=60 600 $EPL stats-calibrate "$C/cal-3m.json" --arm nosink \
      --shapes idle-3m --out "$R/cal/3m-nosink" --ready-timeout 540 --admin-timeout 300 "$@" >> "$R/queue.log" 2>&1
    log "end 3M probe rc=$?"
    $SESSION rungs "$R/rungs.json" "$R"/cal/*-nosink "$R"/cal/*-statsd >> "$R/queue.log" 2>&1
    rewrite
    log "calibrate done; rungs in $R/rungs.json"
    ;;
  smoke)
    log "smoke start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX"
    guard_begin || exit 1
    mkdir -p "$R/smoke"
    for s in $SMOKES; do
      log "start $s"
      $EPL run "$C/$s.json" --out "$R/smoke/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end $s rc=$?"
    done
    log "main-thread profile at 1M (not measured)"
    $EPL flush-profile "$C/m-1m.json" --arm nosink --shape idle-1m --out "$R/profile-1m" "$@" >> "$R/queue.log" 2>&1
    log "end profile rc=$?"
    $SESSION statsd-interval "$R/rungs.json" "$R"/smoke/smoke-* >> "$R/queue.log" 2>&1
    rewrite
    check
    log "smoke done rc=$?"
    ;;
  check)
    check
    exit $?
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
      timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$FROZEN/$run.json" --out "$R/$run" \
        --allow-short "$@" >> "$R/queue.log" 2>&1
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
        timeout --foreground --signal=TERM --kill-after=60 1800 $EPL stats-calibrate "$C/cal-10m.json" --arm nosink \
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
