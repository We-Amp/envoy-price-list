#!/bin/bash
# Wave 4 track G on the bench box (configs from make.py; official v1.40.2 only, sha256 enforced by the harness).
#
#   run-g.sh smoke RUN [EPL_ARGS...]   one round of RUN (g1-proto | g2-resume | g2s-resume), evidence recorded
#   run-g.sh check RUN                 every smoke leg valid; RUN's evidence frozen from its smoke
#   run-g.sh queue RUN [EPL_ARGS...]   check, then the run, within G_STOP_S (default 1 h)
#
# Runs go to $RUNS (default ~/epl/runs/wave4g), progress to $RUNS/queue.log. Extra arguments go to every
# `epl` call. Start it by hand on the bench box. No sysctl change.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave4g
SF=$H/examples/stats-flush
EPL="python3 $H/bin/epl"
SESSION="python3 $SF/session.py"
C=$S/configs
R=${RUNS:-$HOME/epl/runs/wave4g}
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
  local run=$1 bad=0
  mkdir -p "$FROZEN"
  $SESSION smoke-valid "$C/smoke-$run.json" "$R/smoke/smoke-$run" 2>&1 | tee -a "$R/queue.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || bad=1
  log "freeze and check $run against smoke-$run"
  if ! $EPL evidence-check "$C/$run.json" "$R/smoke/smoke-$run" --freeze "$FROZEN/$run.json" >> "$R/queue.log" 2>&1; then
    log "evidence-check $run FAILED (details in queue.log)"
    bad=1
  fi
  return $bad
}

MODE=${1:-}
RUN=${2:-}
case "$RUN" in g1-proto|g2-resume|g2s-resume) ;; *) sed -n '2,9p' "$0"; exit 2 ;; esac
shift 2
trap on_term TERM INT
case "$MODE" in
  smoke)
    log "G smoke $RUN start pid $$ harness $(git -C "$H" rev-parse --short HEAD 2>/dev/null || cat "$H/HARNESS_COMMIT" 2>/dev/null)"
    s=smoke-$RUN
    if [ -d "$R/smoke/$s" ]; then
      aside="$R/smoke/$s.$(date -u +%Y%m%dT%H%M%SZ)"; mv "$R/smoke/$s" "$aside" && log "previous $s kept as $aside"
    fi
    bg_wait $EPL run "$C/$s.json" --out "$R/smoke/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end smoke $s rc=$?"
    ;;
  check)
    check "$RUN"
    exit $?
    ;;
  queue)
    log "G queue start pid $$ run $RUN args: $*"
    check "$RUN" || { log "G queue $RUN not started (smoke or evidence; no override)"; exit 1; }
    STOP_S=${G_STOP_S:-3600}
    bg_wait timeout --foreground --signal=TERM --kill-after=300 "$STOP_S" $EPL run "$FROZEN/$RUN.json" \
      --out "$R/$RUN" --allow-short "$@" >> "$R/queue.log" 2>&1
    rc=$?
    [ "$rc" -eq 124 ] && log "$RUN stopped at the G stop (SIGTERM); partial results, incomplete"
    log "end $RUN rc=$rc"
    ;;
  *)
    sed -n '2,9p' "$0"
    exit 2
    ;;
esac
