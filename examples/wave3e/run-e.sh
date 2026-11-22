#!/bin/bash
# Wave 3 track E (connection churn) on the bench box; configs from make.py.
#
#   run-e.sh smoke [EPL_ARGS...]   one round of $E_RUN (e-plain or e-tls), then check
#   run-e.sh check                 every smoke leg valid; the run's evidence frozen from its smoke
#   run-e.sh queue [EPL_ARGS...]   check, then the run, within E_STOP_S (default 1 h)
#
# Runs go to $RUNS (default ~/epl/runs/wave3e), progress to $RUNS/queue.log. Extra arguments go to
# every `epl` call. Start it by hand on the bench box. No sysctl change.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave3e
SF=$H/examples/stats-flush
EPL="python3 $H/bin/epl"
SESSION="python3 $SF/session.py"
BOX=${BOX:-bench-x86_64}
C=$S/$BOX
R=${RUNS:-$HOME/epl/runs/wave3e}
FROZEN=$R/frozen
RUN=${E_RUN:-e-plain}
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
  local bad=0
  mkdir -p "$FROZEN"
  $SESSION smoke-valid "$C/smoke-$RUN.json" "$R/smoke/smoke-$RUN" 2>&1 | tee -a "$R/queue.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || bad=1
  log "freeze and check $RUN against smoke-$RUN"
  if ! $EPL evidence-check "$C/$RUN.json" "$R/smoke/smoke-$RUN" --freeze "$FROZEN/$RUN.json" >> "$R/queue.log" 2>&1; then
    log "evidence-check $RUN FAILED (details in queue.log)"
    bad=1
  fi
  return $bad
}

MODE=${1:-}
[ $# -gt 0 ] && shift
trap on_term TERM INT
case "$MODE" in
  smoke)
    log "E smoke start pid $$ harness $(git -C "$H" rev-parse --short HEAD 2>/dev/null || cat "$H/HARNESS_COMMIT" 2>/dev/null) box $BOX run $RUN"
    s=smoke-$RUN
    if [ -d "$R/smoke/$s" ]; then
      aside="$R/smoke/$s.$(date -u +%Y%m%dT%H%M%SZ)"; mv "$R/smoke/$s" "$aside" && log "previous $s kept as $aside"
    fi
    bg_wait $EPL run "$C/$s.json" --out "$R/smoke/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end smoke $s rc=$?"
    check
    log "E smoke done rc=$?"
    ;;
  check)
    check
    exit $?
    ;;
  queue)
    log "E queue start pid $$ run $RUN args: $*"
    check || { log "E queue not started (smoke or evidence; no override)"; exit 1; }
    STOP_S=${E_STOP_S:-3600}
    bg_wait timeout --foreground --signal=TERM --kill-after=300 "$STOP_S" $EPL run "$FROZEN/$RUN.json" \
      --out "$R/$RUN" --allow-short "$@" >> "$R/queue.log" 2>&1
    rc=$?
    [ "$rc" -eq 124 ] && log "$RUN stopped at the E stop (SIGTERM); partial results, incomplete"
    log "end $RUN rc=$rc"
    ;;
  *)
    sed -n '2,9p' "$0"
    exit 2
    ;;
esac
