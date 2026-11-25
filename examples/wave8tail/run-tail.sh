#!/bin/bash
# One config of the tail add-on on the bench box (configs from make.py; every arm's binary pinned by sha256,
# enforced by the harness):
#
#   run-tail.sh NAME    configs/NAME.json into $RUNS/tail/NAME (W3_TAIL_STOP_S, default 1800 s)
#
# Runs go to $RUNS (default ~/epl/runs/wave8w3, the session's runs directory), progress to $RUNS/queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave8tail
EPL="python3 $H/bin/epl"
C=$S/configs
R=${RUNS:-$HOME/epl/runs/wave8w3}
mkdir -p "$R"
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
trap on_term TERM INT
bg_wait() {
  "$@" &
  CHILD=$!
  wait "$CHILD"
  local rc=$?
  CHILD=
  return $rc
}
RUN=${1:?NAME (tail-p1-r1 .. tail-p1-r4, tail-c4)}
log "tail add-on leg set $RUN start pid $$ (W8-2 follow-up)"
mkdir -p "$R/tail"
bg_wait timeout --foreground --signal=TERM --kill-after=120 "${W3_TAIL_STOP_S:-1800}" $EPL run "$C/$RUN.json" --out "$R/tail/$RUN" \
  --allow-short >> "$R/queue.log" 2>&1
log "end tail $RUN rc=$?"
