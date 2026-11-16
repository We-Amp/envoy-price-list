#!/bin/bash
# The route-table and constant-header session on the bench box, after calibration and
# the smoke runs: rt-n1000, rt-n200, hdr, then the one-route control rt-n1. A run is not
# started once the session has used BUDGET_H hours (default 9). Extra arguments go to
# every `epl run`. Progress goes to $RUNS/queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
EPL="python3 $H/bin/epl"
R=${RUNS:-$HOME/epl/runs/route-table}
BUDGET_S=$(( ${BUDGET_H:-9} * 3600 ))
T0=$(date +%s)
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" >> "$R/queue.log"; }
log "queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) args: $*"
for run in rt-n1000 rt-n200 hdr rt-n1; do
  if [ $(( $(date +%s) - T0 )) -ge "$BUDGET_S" ]; then
    log "skip $run: session budget used"
    continue
  fi
  log "start $run"
  $EPL run "$H/examples/route-table/$run.json" --out "$R/$run" "$@" >> "$R/queue.log" 2>&1
  log "end $run rc=$?"
done
log "queue done"
