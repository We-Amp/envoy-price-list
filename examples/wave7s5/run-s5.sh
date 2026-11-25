#!/bin/bash
# Wave 7 S5 on the bench box (configs from make.py; every arm's binary pinned by sha256, enforced by the harness).
#
#   run-s5.sh smoke SMOKE                  one round of configs/SMOKE.json, evidence recorded
#   run-s5.sh check RUN SMOKE              every smoke leg of RUN's arms valid; RUN's evidence frozen from SMOKE
#   run-s5.sh queue RUN SMOKE              check, then the run, within S5_STOP_S (default 40 min)
#   run-s5.sh mech  NAME                   one non-scored mechanism config (configs/NAME.json) into mech/NAME
#
# Runs go to $RUNS (default ~/epl/runs/wave7s5), progress to $RUNS/queue.log. No sysctl change.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave7s5
EPL="python3 $H/bin/epl"
SESSION="python3 $H/examples/stats-flush/session.py"
C=$S/configs
R=${RUNS:-$HOME/epl/runs/wave7s5}
FROZEN=$R/frozen
mkdir -p "$R" "$R/smoke"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/queue.log"; }
CHILD=
on_term() {
  if [ -n "$CHILD" ] && kill -0 "$CHILD" 2>/dev/null; then
    log "TERM: forwarding to the running child $CHILD"
    kill -TERM "$CHILD" 2>/dev/null
    wait "$CHILD" 2>/dev/null
  fi
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
  local run=$1 smoke=$2 bad=0
  mkdir -p "$FROZEN"
  $SESSION smoke-valid "$C/$run.json" "$R/smoke/$smoke" 2>&1 | tee -a "$R/queue.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || bad=1
  log "freeze and check $run against $smoke"
  if ! $EPL evidence-check "$C/$run.json" "$R/smoke/$smoke" --freeze "$FROZEN/$run.json" >> "$R/queue.log" 2>&1; then
    log "evidence-check $run FAILED (details in queue.log)"
    bad=1
  fi
  return $bad
}
MODE=${1:-}
RUN=${2:-}
[ -n "$RUN" ] && [ -f "$C/$RUN.json" ] || { sed -n 2,9p "$0"; exit 2; }
trap on_term TERM INT
case "$MODE" in
  smoke)
    log "S5 smoke $RUN start pid $$"
    if [ -d "$R/smoke/$RUN" ]; then
      aside="$R/smoke/$RUN.$(date -u +%Y%m%dT%H%M%SZ)"; mv "$R/smoke/$RUN" "$aside" && log "previous $RUN kept as $aside"
    fi
    bg_wait $EPL run "$C/$RUN.json" --out "$R/smoke/$RUN" --allow-short >> "$R/queue.log" 2>&1
    log "end smoke $RUN rc=$?"
    ;;
  check)
    check "$RUN" "${3:?smoke name}"
    exit $?
    ;;
  queue)
    SMOKE=${3:?smoke name}
    log "S5 queue start pid $$ run $RUN (smoke $SMOKE)"
    check "$RUN" "$SMOKE" || { log "S5 queue $RUN not started (smoke or evidence; no override)"; exit 1; }
    STOP_S=${S5_STOP_S:-2400}
    bg_wait timeout --foreground --signal=TERM --kill-after=300 "$STOP_S" $EPL run "$FROZEN/$RUN.json" \
      --out "$R/$RUN" --allow-short >> "$R/queue.log" 2>&1
    rc=$?
    [ "$rc" -eq 124 ] && log "$RUN stopped at the S5 stop (SIGTERM); partial results, incomplete"
    log "end $RUN rc=$rc"
    ;;
  mech)
    log "S5 mechanism legs $RUN start pid $$ (non-scored)"
    mkdir -p "$R/mech"
    bg_wait timeout --foreground --signal=TERM --kill-after=120 900 $EPL run "$C/$RUN.json" --out "$R/mech/$RUN" \
      --allow-short >> "$R/queue.log" 2>&1
    log "end mech $RUN rc=$?"
    ;;
  *)
    sed -n 2,9p "$0"
    exit 2
    ;;
esac
