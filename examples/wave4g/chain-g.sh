#!/bin/bash
# Wave 4 track G session chain (one detached chain, one login):
#   0 idle check; the client speaks HTTP/3 (--protocol takes http3), UDP 10110 and TCP 10110 free, or stop
#   1 the two smokes (g1-proto, g2-resume)
#   2 per run: check (smoke valid, evidence frozen), then the run; a run whose check fails is skipped and
#     the next one still runs (each run has its own A/A)
# Exit code in $R/chain-g.rc (0: both runs ended rc=0), progress in $R/chain-g.log and queue.log.
# Start with box-start.sh (idle check, detached start, prints the "chain g start pid" line).
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave4g
R=${RUNS:-$HOME/epl/runs/wave4g}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-g.log
RUNS_G=${G_RUNS:-"g1-proto g2-resume"}
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-g.rc"; exit "$1"; }
log "chain g start pid $$ harness $H ($(git -C "$H" rev-parse --short HEAD 2>/dev/null || cat "$H/HARNESS_COMMIT" 2>/dev/null)) runs: $RUNS_G"
# idleness by load and CPU only (idle.sh); no process is matched by its command line
if ! st=$(bash "$S/idle.sh"); then log "box $st"; fin 10; fi
log "$st"
NH=$(python3 -c "import json,os,sys; print(os.path.expanduser(json.load(open(sys.argv[1]))['client']['binary']))" "$S/configs/g1-proto.json")
if ! "$NH" --help 2>/dev/null | grep -q 'http3'; then
  log "client $NH does not list http3 (stop)"; fin 15
fi
if [ -n "$(ss -Hlun 'sport = :10110' 2>/dev/null)" ] || [ -n "$(ss -Hltn 'sport = :10110' 2>/dev/null)" ]; then
  log "port 10110 (UDP or TCP) in use (stop)"; fin 16
fi
log "kernel $(uname -r); udp rmem_max $(cat /proc/sys/net/core/rmem_max) wmem_max $(cat /proc/sys/net/core/wmem_max) (read only)"
for run in $RUNS_G; do bash "$S/run-g.sh" smoke "$run"; done
if [ "${G_SMOKE_ONLY:-0}" = 1 ]; then
  # smoke only (G_SMOKE_ONLY=1): check each smoke, record, run nothing else
  bad=0
  for run in $RUNS_G; do
    if bash "$S/run-g.sh" check "$run"; then log "$run smoke check PASS (run not started: smoke only)"
    else log "$run smoke check FAILED"; bad=1; fi
  done
  [ "$bad" = 0 ] && fin 0
  fin 21
fi
bad=0
for run in $RUNS_G; do
  if bash "$S/run-g.sh" queue "$run"; then
    last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; bad=1; }
  else
    log "$run not run (its smoke check failed)"; bad=1
  fi
done
[ "$bad" = 0 ] && fin 0
fin 20
