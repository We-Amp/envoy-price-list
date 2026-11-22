#!/bin/bash
# Wave 1 track B on the bench box (configs from make.py, binaries pinned in bins.json).
#
#   run-b.sh smoke [EPL_ARGS...]   one round of each run (smoke-b-statsd, smoke-b-fl; with
#                                  NOSINK=1 also smoke-b-statsd-nosink), then check
#   run-b.sh check                 every smoke leg valid; each run's evidence frozen from its smoke
#                                  into $RUNS/frozen/ and checked on the smoke legs (no override)
#   B_RUNS="b-statsd b-fl" overrides the list of runs for every mode.
#   run-b.sh queue [EPL_ARGS...]   check, then b-statsd (or b-statsd-nosink with NOSINK=1) and b-fl,
#                                  within B_STOP_S (default 1 h 45 min) after the queue starts; each run
#                                  gets the time left, then SIGTERM through `timeout --foreground`
#
# net.core.rmem_max: smoke and queue raise it for the statsd runs and restore the value they found
# on exit, failure, the stop or an operator's TERM (the stats-flush sysctl-guard.sh).
# Runs go to $RUNS (default ~/epl/runs/wave1-b), progress to $RUNS/queue.log. Extra arguments go
# to every `epl` call. Start it by hand on the bench box.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave1-b
SF=$H/examples/stats-flush
EPL="python3 $H/bin/epl"
SESSION="python3 $SF/session.py"
BOX=${BOX:-bench-x86_64}
C=$S/$BOX
R=${RUNS:-$HOME/epl/runs/wave1-b}
FROZEN=$R/frozen
if [ "${NOSINK:-0}" = 1 ]; then STATSD=b-statsd-nosink; else STATSD=b-statsd; fi
RUNS_B=${B_RUNS:-"$STATSD b-fl"}
mkdir -p "$R" "$R/smoke"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/queue.log"; }
GUARD_DIR=$R
# shellcheck source=../stats-flush/sysctl-guard.sh
. "$SF/sysctl-guard.sh"

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
bg_wait() {
  "$@" &
  CHILD=$!
  wait "$CHILD"
  local rc=$?
  CHILD=
  return $rc
}

check() {
  local bad=0 run
  mkdir -p "$FROZEN"
  for run in $RUNS_B; do
    $SESSION smoke-valid "$C/smoke-$run.json" "$R/smoke/smoke-$run" 2>&1 | tee -a "$R/queue.log"
    [ "${PIPESTATUS[0]}" -eq 0 ] || bad=1
    log "freeze and check $run against smoke-$run"
    if ! $EPL evidence-check "$C/$run.json" "$R/smoke/smoke-$run" --freeze "$FROZEN/$run.json" \
        >> "$R/queue.log" 2>&1; then
      log "evidence-check $run FAILED (details in queue.log)"
      bad=1
    fi
  done
  return $bad
}

MODE=${1:-}
[ $# -gt 0 ] && shift
case "$MODE" in
  smoke)
    log "B smoke start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX runs: $RUNS_B"
    guard_begin || exit 1
    trap on_term TERM INT
    for run in $RUNS_B; do
      s=smoke-$run
      if [ -d "$R/smoke/$s" ]; then
        aside="$R/smoke/$s.$(date -u +%Y%m%dT%H%M%SZ)"; mv "$R/smoke/$s" "$aside" && log "previous $s kept as $aside"
      fi
      log "smoke $s"
      bg_wait $EPL run "$C/$s.json" --out "$R/smoke/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end smoke $s rc=$?"
    done
    guard_end
    trap - TERM INT
    check
    log "B smoke done rc=$?"
    ;;
  check)
    check
    exit $?
    ;;
  queue)
    log "B queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) box $BOX runs: $RUNS_B args: $*"
    check || { log "B queue not started (smoke or evidence; no override)"; exit 1; }
    STOP_S=${B_STOP_S:-6300}
    guard_begin || exit 1
    trap on_term TERM INT
    T0=$(date +%s)
    for run in $RUNS_B; do
      L=$(( STOP_S - ($(date +%s) - T0) ))
      if [ "$L" -le 60 ]; then log "skip $run: B stop reached"; continue; fi
      log "start $run (${L}s left before the B stop)"
      bg_wait timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$FROZEN/$run.json" \
        --out "$R/$run" --allow-short "$@" >> "$R/queue.log" 2>&1
      rc=$?
      [ "$rc" -eq 124 ] && log "$run stopped at the B stop (SIGTERM); partial results, incomplete"
      log "end $run rc=$rc"
    done
    guard_end
    trap - TERM INT
    log "B queue done"
    ;;
  *)
    sed -n '2,15p' "$0"
    exit 2
    ;;
esac
