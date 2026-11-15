#!/bin/bash
# Run the follow-up experiments one after another on the bench box.
#   run-followups.sh f1-two-hop sat f2-buffer-limit ...   ("sat" = saturation probe of f1-two-hop)
# Each writes $RUNS/<name>; progress goes to $RUNS/queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
EPL="python3 $H/bin/epl"
C=$H/examples/settings-matrix/followups
R=${RUNS:-$HOME/epl/runs/smf}
SAT_RPS=${SAT_RPS:-5200,6400,8000,9600,11200,12800,14400,16000}
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" >> "$R/queue.log"; }
log "queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) rows: $*"
for row in "$@"; do
  log "start $row"
  if [ "$row" = sat ]; then
    python3 "$H/examples/settings-matrix/saturation.py" "$C/f1-two-hop.json" "$R/sat" --rps "$SAT_RPS" >> "$R/queue.log" 2>&1
  else
    $EPL run "$C/$row.json" --out "$R/$row" >> "$R/queue.log" 2>&1
  fi
  log "end $row rc=$?"
done
log "queue done"
