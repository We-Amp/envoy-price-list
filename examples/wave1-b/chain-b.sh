#!/bin/bash
# Track B session chain (one detached chain, one login). Stages, each gated on the previous one:
#   0 idle check   1 smokes of b-statsd, b-statsd-nosink, b-fl (+ one b-fl fallback at a lower rate)
#   2 b-statsd     3 b-statsd-nosink     4 b-fl
# Exit code in $R/chain.rc. Progress in $R/chain.log (and run-b.sh's queue.log).
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave1-b
R=${RUNS:-$HOME/epl/runs/wave1-b}
export RUNS=$R
FL_FALLBACK_RPS=${FL_FALLBACK_RPS:-1500}
ARGS=(--set 'client.binary="~/nighthawk-dogfood/bazel-bin/nighthawk_client"')
mkdir -p "$R"
L=$R/chain.log
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain.rc"; exit "$1"; }
log "chain start pid $$ harness $H ($(git -C "$H" rev-parse --short HEAD 2>/dev/null))"
# (the login shell that started this chain names it, so lines naming chain-b.sh are not other work)
busy=$(ps -eo pid,args | grep -E '[b]in/epl|[r]un-session\.sh|[r]un-u\.sh|[r]un-b\.sh|[e]nvoy-static|[e]nvoy-1\.|[n]ighthawk_client' | grep -v 'chain-b\.sh')
l1=$(cut -d' ' -f1 /proc/loadavg)
if [ -n "$busy" ] || ! python3 -c "import sys;sys.exit(0 if float('$l1') < 0.5 else 1)"; then
  log "box not idle (load $l1): $busy"; fin 10
fi
log "idle: load $l1"
( cd "$H" && sha256sum ~/epl/bin/envoy-1.40.2 ~/epl/bins/wave1b/envoy-p1 ~/epl/bins/wave1b/envoy-p2 ) | tee -a "$L"
python3 "$S/make.py" >> "$L" 2>&1 || fin 11
# 1. smokes
B_RUNS="b-statsd b-statsd-nosink b-fl" bash "$S/run-b.sh" smoke "${ARGS[@]}"
for run in b-statsd b-statsd-nosink; do
  B_RUNS=$run bash "$S/run-b.sh" check || { log "smoke check $run FAILED: stop"; fin 12; }
done
if ! B_RUNS=b-fl bash "$S/run-b.sh" check; then
  log "smoke check b-fl FAILED at the default rate: fallback to $FL_FALLBACK_RPS req/s (once)"
  FL_RPS=$FL_FALLBACK_RPS python3 "$S/make.py" >> "$L" 2>&1 || fin 11
  log "b-fl rate now $(python3 -c "import json;print(json.load(open('$S/bench-x86_64/b-fl.json'))['shapes'][0]['rps'])")"
  B_RUNS=b-fl bash "$S/run-b.sh" smoke "${ARGS[@]}"
  B_RUNS=b-fl bash "$S/run-b.sh" check || { log "smoke check b-fl FAILED at the fallback rate too: stop"; fin 13; }
fi
log "smokes passed"
# 2-4. the runs, in order, each only after the previous one ended with rc 0
for run in b-statsd b-statsd-nosink b-fl; do
  log "start $run"
  B_RUNS=$run bash "$S/run-b.sh" queue "${ARGS[@]}"
  rc=$?
  grep -E "end $run rc=" "$R/queue.log" | tail -1 | tee -a "$L"
  last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
  if [ "$rc" -ne 0 ] || [ "${last:-x}" != 0 ]; then log "$run failed (script rc=$rc, run rc=${last:-none}): stop"; fin 20; fi
  log "end $run ok"
done
fin 0
