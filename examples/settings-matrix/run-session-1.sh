#!/bin/bash
# Feature rows, session 1, on the bench box (configs from features.py).
#
#   run-session-1.sh smoke [EPL_ARGS...]   step 1.1: calibrate s-w16 (CAL_RPS, arms log-off and
#                                         log-json), run every smoke config (two rounds, evidence
#                                         recorded, not gated), check every run config's evidence
#                                         offline against the smoke legs, print the budget
#   run-session-1.sh check                 the offline evidence check and the budget again (after
#                                         features.py was rerun with corrected counter names)
#   run-session-1.sh queue [EPL_ARGS...]   steps 1.2 to 1.6: run S, 18, 17, 13, then 18w
#
# Queue rules: it does not start unless every arm has smoke legs and every smoke leg passes
# the evidence check (no override), and the mandatory worst case (smoke seconds per leg x
# cap legs) is at most 9 h 30 min (FORCE=1 overrides only this budget question, after the
# lead said so). Hard stop STOP_H hours (default 10) after the queue starts: each run gets
# the time that is left and is then sent SIGTERM through `timeout --foreground`, which
# signals the harness process only; the harness stops its own Envoy, client and
# containers, writes its partial results and marks the run incomplete. If run S ends without a complete result, the queue
# stops: no row runs without a floor from its own session. 18w (optional) starts only if
# the time used plus its worst case fits inside the stop.
#
# Runs go to $RUNS (default ~/epl/runs/wk5), smoke runs to $RUNS/smoke; progress to
# $RUNS/queue.log. Extra arguments go to every `epl run`.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
EPL="python3 $H/bin/epl"
FEAT=$H/examples/settings-matrix/features.py
C=$H/examples/settings-matrix/features
R=${RUNS:-$HOME/epl/runs/wk5}
SMOKE=$R/smoke
STOP_S=$(( ${STOP_H:-10} * 3600 ))
CAL_RPS=${CAL_RPS:-19200,20800,22400}
RUNS_MANDATORY="run-s 18-access-log 17-tracing 13-ext-authz"
RUN_OPTIONAL="18w-access-log-w16"
SMOKES="smoke-s1 smoke-s2 smoke-18 smoke-17a smoke-17b smoke-13 smoke-18w smoke-ref1 smoke-ref2 smoke-ref3"
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/queue.log"; }

check() {
  local bad=0 run
  for run in $RUNS_MANDATORY $RUN_OPTIONAL; do
    log "evidence-check $run against the smoke legs"
    if ! $EPL evidence-check "$C/$run.json" "$SMOKE"/smoke-* >> "$R/queue.log" 2>&1; then
      log "evidence-check $run FAILED (details in queue.log)"
      bad=1
    fi
  done
  python3 "$FEAT" budget "$SMOKE" | tee -a "$R/queue.log"
  local brc=${PIPESTATUS[0]}
  [ "$brc" -eq 3 ] && log "mandatory worst case above 9 h 30 min: ask the lead before the queue"
  [ "$brc" -ne 0 ] && [ "$brc" -ne 3 ] && bad=1
  return $(( bad ? 1 : (brc == 3 ? 3 : 0) ))
}

mode=${1:-}
shift || true
case "$mode" in
  smoke)
    log "smoke start pid $$ harness $(cat "$H/VERSION" 2>/dev/null)"
    mkdir -p "$SMOKE"
    for arm in log-off log-json; do
      log "calibrate s-w16 $arm at $CAL_RPS"
      $EPL calibrate "$C/18w-access-log-w16.json" --arm "$arm" --shape s-w16 --rps "$CAL_RPS" \
        --out "$R/cal-w16-$arm" >> "$R/queue.log" 2>&1
      log "end calibrate $arm rc=$?"
    done
    for s in $SMOKES; do
      log "start $s"
      $EPL run "$C/$s.json" --out "$SMOKE/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end $s rc=$?"
    done
    check
    log "smoke done rc=$?"
    ;;
  check)
    check
    exit $?
    ;;
  queue)
    log "queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) args: $*"
    check
    rc=$?
    if [ "$rc" -eq 3 ] && [ "${FORCE:-0}" = 1 ]; then
      log "budget above 9 h 30 min: FORCE=1 given, starting (the lead agreed)"
    elif [ "$rc" -ne 0 ]; then
      log "queue not started (check rc=$rc: 1 = evidence check failed, no override; 3 = budget, FORCE=1 after the lead agreed)"
      exit 1
    fi
    T0=$(date +%s)
    left() { echo $(( STOP_S - ($(date +%s) - T0) )); }
    for run in $RUNS_MANDATORY; do
      L=$(left)
      if [ "$L" -le 60 ]; then
        log "skip $run: session stop reached"
        continue
      fi
      log "start $run (${L}s left before the stop)"
      timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$C/$run.json" --out "$R/$run" "$@" >> "$R/queue.log" 2>&1
      rc=$?
      [ "$rc" -eq 124 ] && log "$run stopped at the session stop (SIGTERM); partial results, incomplete if short"
      log "end $run rc=$rc"
      if [ "$run" = run-s ]; then
        if ! why=$(python3 "$FEAT" has-floor "$R/run-s"); then
          log "run S has no complete result ($why): the queue stops, no row runs without its floor"
          exit 1
        fi
        log "run S floor: $why"
      fi
    done
    CAP=$(python3 "$FEAT" cap "$RUN_OPTIONAL" "$SMOKE")
    L=$(left)
    if [ "$CAP" -le "$L" ]; then
      log "start $RUN_OPTIONAL (worst case ${CAP}s, ${L}s left)"
      timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$C/$RUN_OPTIONAL.json" --out "$R/$RUN_OPTIONAL" "$@" \
        >> "$R/queue.log" 2>&1
      log "end $RUN_OPTIONAL rc=$?"
    else
      log "skip $RUN_OPTIONAL: worst case ${CAP}s does not fit in the ${L}s left"
    fi
    log "queue done; tables: python3 $H/examples/settings-matrix/features_table.py $R > $R/tables.md"
    ;;
  *)
    sed -n '2,20p' "$0"
    exit 2
    ;;
esac
