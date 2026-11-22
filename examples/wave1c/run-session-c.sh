#!/bin/bash
# Track C (wave 1) on the bench box: the ext_proc row and the xDS-update row, official v1.40.2.
#
#   run-session-c.sh smoke [EPL_ARGS...]   one round of every arm of the three runs (evidence
#                                         recorded, not gated), then check
#   run-session-c.sh check                 freeze every run's evidence from its smoke into
#                                         $RUNS/frozen/, check the frozen spec against the smoke
#                                         legs (every arm), print the budget from the smoke's
#                                         seconds per leg
#   run-session-c.sh queue [EPL_ARGS...]   extproc, xds-small, xds-large with the frozen configs,
#                                         6 fixed rounds each (--allow-short)
#
# Before anything: the ext_proc test service must be on the box at the path the config names
# (tools/extproc/out/epl-extproc-linux-amd64 in the harness tree; built off the box with
# tools/extproc/build.sh); the harness refuses to start it unless its sha256 matches. If the smoke
# shows a worker above 80% busy in an ext_proc arm at 5,200 req/s, write {"s": 4000} into a file,
# set RATES_JSON to it and run `check` again: every config is rewritten from it before freezing.
#
# Queue rules: it does not start unless every arm has a smoke leg and every smoke leg passes its
# run's frozen evidence. Hard stop STOP_H hours (default 6) after the queue starts; each run gets
# the time that is left and is then sent SIGTERM through `timeout --foreground` (the harness
# process only; it stops its own Envoy, client and containers and writes partial results).
# xds-large runs only if xds-small ended complete (its A/A is the large run's floor).
#
# Runs go to $RUNS (default ~/epl/runs/wave1c), smokes to $RUNS/smoke, progress to
# $RUNS/queue.log. Extra arguments go to every `epl run`.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
EPL="python3 $H/bin/epl"
MAKE=$H/examples/wave1c/make.py
FEAT=$H/examples/settings-matrix/features.py
C=$H/examples/wave1c/configs
R=${RUNS:-$HOME/epl/runs/wave1c}
SMOKE=$R/smoke
FROZEN=$R/frozen
STOP_S=$(( ${STOP_H:-6} * 3600 ))
RUNS_LIST="extproc xds-small xds-large"
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/queue.log"; }

rewrite() {
  if [ -n "${RATES_JSON:-}" ]; then
    log "configs rewritten from $RATES_JSON"
    python3 "$MAKE" write "$RATES_JSON" >> "$R/queue.log" 2>&1 || { log "make.py write failed"; exit 1; }
  fi
}

check() {
  local bad=0 run spl
  mkdir -p "$FROZEN"
  for run in $RUNS_LIST; do
    log "freeze and check $run against $SMOKE/smoke-$run"
    if ! $EPL evidence-check "$C/$run.json" "$SMOKE/smoke-$run" --freeze "$FROZEN/$run.json" \
        >> "$R/queue.log" 2>&1; then
      log "evidence-check $run FAILED (details in queue.log)"
      bad=1
    fi
  done
  python3 "$MAKE" budget "$SMOKE" | tee -a "$R/queue.log"
  return $bad
}

mode=${1:-}
shift || true
case "$mode" in
  smoke)
    log "smoke start pid $$ harness $(git -C "$H" rev-parse --short HEAD 2>/dev/null)"
    mkdir -p "$SMOKE"
    rewrite
    for run in $RUNS_LIST; do
      log "start smoke-$run"
      $EPL run "$C/smoke-$run.json" --out "$SMOKE/smoke-$run" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end smoke-$run rc=$?"
    done
    check
    log "smoke done rc=$?"
    ;;
  check)
    rewrite
    check
    exit $?
    ;;
  queue)
    log "queue start pid $$ harness $(git -C "$H" rev-parse --short HEAD 2>/dev/null) args: $*"
    rewrite
    if ! check; then
      log "queue not started: evidence check failed (no override)"
      exit 1
    fi
    T0=$(date +%s)
    left() { echo $(( STOP_S - ($(date +%s) - T0) )); }
    for run in $RUNS_LIST; do
      L=$(left)
      if [ "$L" -le 60 ]; then
        log "skip $run: session stop reached"
        continue
      fi
      if [ "$run" = xds-large ] && ! why=$(python3 "$FEAT" has-floor "$R/xds-small"); then
        log "skip xds-large: xds-small has no complete result ($why), so no floor"
        continue
      fi
      log "start $run (${L}s left before the stop)"
      timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$FROZEN/$run.json" --out "$R/$run" \
        --allow-short "$@" >> "$R/queue.log" 2>&1
      rc=$?
      [ "$rc" -eq 124 ] && log "$run stopped at the session stop (SIGTERM); partial results, incomplete"
      log "end $run rc=$rc"
    done
    log "queue done; tables: python3 $H/examples/wave1c/table.py extproc $R/extproc;" \
        "python3 $H/examples/wave1c/table.py xds $R/xds-small $R/xds-large"
    ;;
  *)
    sed -n '2,27p' "$0"
    exit 2
    ;;
esac
