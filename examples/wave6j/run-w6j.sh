#!/bin/bash
# Wave 6 track J (arm64 bare metal): run-w2.sh of wave 2 with the wave6j configs and the frame-pointer profiling wrapper.
#
#   run-w2.sh prof [EPL_ARGS...]    profiling legs: lbr-w2 (pgolto-relocs, the BOLT input); with
#                                   PROF_OPT=1 also lbr-w2-opt; PROF_RUNS="..." overrides the list. perf-lbr.sh is installed under
#                                   $PROF_DIR (default ~/epl/runs/wave2-prof); data in $PROF_DIR/lbr-data/<run>/
#   run-w2.sh smoke [EPL_ARGS...]   one round of the A/B run ($W2_RUN: w2, or w2-nobolt), then check
#   run-w2.sh check                 every smoke leg valid; the run's evidence frozen from its smoke
#   run-w2.sh queue [EPL_ARGS...]   check, then the run, within W2_STOP_S (default 2 h)
#
# Runs go to $RUNS (default ~/epl/runs/wave2), progress to $RUNS/queue.log. Extra arguments go to
# every `epl` call. Start it by hand on the bench box. No sysctl change.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave6j
SF=$H/examples/stats-flush
EPL="python3 $H/bin/epl"
SESSION="python3 $SF/session.py"
BOX=${BOX:-arm-metal}
C=$S/$BOX
R=${RUNS:-$HOME/epl/runs/wave6j}
PROF_DIR=${PROF_DIR:-$HOME/epl/runs/wave6j-prof}
FROZEN=$R/frozen
RUN=${W2_RUN:-w6j}
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
  prof)
    mkdir -p "$PROF_DIR/spe-data"
    install -m 755 "$S/perf-spe.sh" "$PROF_DIR/perf-spe.sh"
    runs=${PROF_RUNS:-spe-w6j-official spe-w6j-relocs}
    for run in $runs; do
      export W6J_SPE_OUT=$PROF_DIR/spe-data/$run   # read by perf-spe.sh (inherited through epl)
      log "prof $run start (data in $W6J_SPE_OUT)"
      bg_wait $EPL run "$C/$run.json" --out "$PROF_DIR/$run" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end prof $run rc=$?"
    done
    ls -lR "$PROF_DIR/spe-data" | tee -a "$R/queue.log"
    ;;
  smoke)
    log "W2 smoke start pid $$ harness $(git -C "$H" rev-parse --short HEAD 2>/dev/null) box $BOX run $RUN"
    s=smoke-$RUN
    if [ -d "$R/smoke/$s" ]; then
      aside="$R/smoke/$s.$(date -u +%Y%m%dT%H%M%SZ)"; mv "$R/smoke/$s" "$aside" && log "previous $s kept as $aside"
    fi
    bg_wait $EPL run "$C/$s.json" --out "$R/smoke/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end smoke $s rc=$?"
    check
    log "W2 smoke done rc=$?"
    ;;
  check)
    check
    exit $?
    ;;
  queue)
    log "W2 queue start pid $$ run $RUN args: $*"
    check || { log "W2 queue not started (smoke or evidence; no override)"; exit 1; }
    STOP_S=${W2_STOP_S:-7200}
    bg_wait timeout --foreground --signal=TERM --kill-after=300 "$STOP_S" $EPL run "$FROZEN/$RUN.json" \
      --out "$R/$RUN" --allow-short "$@" >> "$R/queue.log" 2>&1
    rc=$?
    [ "$rc" -eq 124 ] && log "$RUN stopped at the W2 stop (SIGTERM); partial results, incomplete"
    log "end $RUN rc=$rc"
    ;;
  *)
    sed -n '2,12p' "$0"
    exit 2
    ;;
esac
