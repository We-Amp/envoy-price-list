#!/bin/bash
# Wave 5 track H on the bench box; configs from make.py.
#
#   run-h.sh smoke RUN [EPL_ARGS...]   one round of RUN (h-pl, h-c1, h-spec, h-defer-deep, h-defer-c1only), then check
#   run-h.sh check RUN                 every smoke leg valid; the run's evidence frozen from its smoke
#   run-h.sh queue RUN [EPL_ARGS...]   check, then the run, within H_STOP_S (default 1 h)
#
# Runs go to $RUNS (one directory per boot block, set by chain-h.sh), progress to $RUNS/queue.log.
# Extra arguments go to every `epl` call. No sysctl change; the idle states are chain-h.sh's business.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave5h
SF=$H/examples/stats-flush
EPL="python3 $H/bin/epl"
SESSION="python3 $SF/session.py"
BOX=${BOX:-bench-x86_64}
C=${H_CONF_DIR:-$S/$BOX}
R=${RUNS:?RUNS (the block directory) must be set}
FROZEN=$R/frozen
MODE=${1:-}
[ $# -gt 0 ] && shift
RUN=${1:-}
[ $# -gt 0 ] && shift
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
    if [ "${H_DRY:-0}" = 1 ] && [ -f "$FROZEN/$RUN.json" ]; then
      # a chain dry run (H_DRY=1, off the box): simulated legs carry no counters, so every item fails
      log "dry run: evidence-check $RUN failed on simulated legs, as it must; ignored"
    else
      log "evidence-check $RUN FAILED (details in queue.log)"
      bad=1
    fi
  fi
  return $bad
}

[ -f "$C/$RUN.json" ] || { sed -n '2,9p' "$0"; echo "unknown run '$RUN'"; exit 2; }
trap on_term TERM INT
case "$MODE" in
  smoke)
    log "H smoke start pid $$ harness $(git -C "$H" rev-parse --short HEAD 2>/dev/null || cat "$H/HARNESS_COMMIT" 2>/dev/null) box $BOX run $RUN"
    s=smoke-$RUN
    if [ -d "$R/smoke/$s" ]; then
      aside="$R/smoke/$s.$(date -u +%Y%m%dT%H%M%SZ)"; mv "$R/smoke/$s" "$aside" && log "previous $s kept as $aside"
    fi
    bg_wait $EPL run "$C/$s.json" --out "$R/smoke/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end smoke $s rc=$?"
    check
    log "H smoke done rc=$?"
    ;;
  check)
    check
    exit $?
    ;;
  queue)
    log "H queue start pid $$ run $RUN args: $*"
    check || { log "H queue not started (smoke or evidence; no override)"; exit 1; }
    STOP_S=${H_STOP_S:-3600}
    bg_wait timeout --foreground --signal=TERM --kill-after=300 "$STOP_S" $EPL run "$FROZEN/$RUN.json" \
      --out "$R/$RUN" --allow-short "$@" >> "$R/queue.log" 2>&1
    rc=$?
    [ "$rc" -eq 124 ] && log "$RUN stopped at the H stop (SIGTERM); partial results, incomplete"
    log "end $RUN rc=$rc"
    ;;
  *)
    sed -n '2,9p' "$0"
    exit 2
    ;;
esac
