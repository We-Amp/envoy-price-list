#!/bin/bash
# Run settings-matrix rows one after another on the bench box (after the A/A).
#   run-all.sh 01-tls-cert 02-tls-resumption ...
# Each row writes $RUNS/<row>; progress goes to $RUNS/queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
EPL="python3 $H/bin/epl"
R=${RUNS:-$HOME/epl/runs/sm}
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" >> "$R/queue.log"; }
log "queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) rows: $*"
for row in "$@"; do
  log "start $row"
  $EPL run "$H/examples/settings-matrix/$row.json" --out "$R/$row" >> "$R/queue.log" 2>&1
  log "end $row rc=$?"
done
log "queue done"
