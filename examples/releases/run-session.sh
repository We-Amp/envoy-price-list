#!/bin/bash
# The release back-fill session on the bench box, after calibration and the smoke runs:
# the release run (six releases and the A/A arm), then the two filter rows, whose A/A
# floor is the release run's A/A arm. Extra arguments go to every `epl run` (for example
# --set client.binary=PATH). Progress goes to $RUNS/queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
EPL="python3 $H/bin/epl"
R=${RUNS:-$HOME/epl/runs/wk4}
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" >> "$R/queue.log"; }
log "queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) args: $*"
log "start releases"
$EPL run "$H/examples/releases/releases.json" --out "$R/releases" "$@" >> "$R/queue.log" 2>&1
log "end releases rc=$?"
FLOOR=()
if [ ! -s "$R/releases/results.json" ]; then
  log "no releases/results.json: the filter rows run without a floor (apply it later with report --floor)"
  FLOOR=(--set floor_from=null --set floor_arm=null)
fi
for row in 11-jwt-authn 12-local-ratelimit; do
  log "start $row"
  $EPL run "$H/examples/settings-matrix/filters/$row.json" --out "$R/$row" "$@" "${FLOOR[@]}" >> "$R/queue.log" 2>&1
  log "end $row rc=$?"
done
log "queue done"
