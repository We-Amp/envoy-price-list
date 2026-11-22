#!/bin/bash
# Wave 3 track F session chain (one detached chain, one login):
#   0 idle check; the client sends a file as the request body (--request-body-file), or stop
#   1 the three smokes (f1-upstream, f2-grpc, f3-mtls)
#   2 per run: check (smoke valid, evidence frozen), then the run; a run whose check fails is skipped and
#     the next one still runs (each run has its own A/A)
# Exit code in $R/chain-f.rc (0: all three runs ended rc=0), progress in $R/chain-f.log and queue.log.
# Start (from ~/epl/runs/wave3f):  (setsid nohup bash ~/epl/harness-wave3f/examples/wave3f/chain-f.sh \
#   </dev/null >chain-f.out 2>&1 &)   then exit; the chain PID is in the "chain f start pid" log line.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave3f
R=${RUNS:-$HOME/epl/runs/wave3f}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-f.log
RUNS_F=${F_RUNS:-"f1-upstream f2-grpc f3-mtls"}
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-f.rc"; exit "$1"; }
log "chain f start pid $$ harness $H ($(git -C "$H" rev-parse --short HEAD 2>/dev/null || cat "$H/HARNESS_COMMIT" 2>/dev/null)) runs: $RUNS_F"
# (lines naming chain-f.sh are this chain and the login shell that started it, not other work)
busy=$(ps -eo pid,args | grep -E '[b]in/epl|[r]un-session\.sh|[r]un-u\.sh|[r]un-b\.sh|[r]un-w2\.sh|[r]un-f\.sh|[e]nvoy-static|[e]nvoy-1\.|[e]nvoy-(opt|order|autofdo|pgolto|bolt)|[n]ighthawk_client' | grep -v 'chain-f\.sh')
l1=$(cut -d' ' -f1 /proc/loadavg)
if [ -n "$busy" ] || ! python3 -c "import sys;sys.exit(0 if float('$l1') < 0.5 else 1)"; then
  log "box not idle (load $l1): $busy"; fin 10
fi
log "idle: load $l1"
NH=$(python3 -c "import json,os,sys; print(os.path.expanduser(json.load(open(sys.argv[1]))['client']['binary']))" "$S/configs/f2-grpc.json")
if grep -q '"request_body_file"' "$S/configs/f2-grpc.json" && ! "$NH" --help 2>/dev/null | grep -q -- '--request-body-file'; then
  log "client $NH has no --request-body-file: regenerate with make.py --no-body-file (stop)"; fin 15
fi
for run in $RUNS_F; do bash "$S/run-f.sh" smoke "$run"; done
bad=0
for run in $RUNS_F; do
  if bash "$S/run-f.sh" queue "$run"; then
    last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; bad=1; }
  else
    log "$run not run (its smoke check failed)"; bad=1
  fi
done
[ "$bad" = 0 ] && fin 0
fin 20
