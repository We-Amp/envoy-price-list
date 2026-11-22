#!/bin/bash
# The v2 confirmation session: one detached chain, one login.
#   0 idle check and sha256 of the binaries   1 smoke-v2c and its check   2 v2c (8 rounds)
# Exit code in $R/chain-v2c.rc, progress in $R/chain-v2c.log (and run-b.sh's queue.log).
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave1-b
R=${RUNS:-$HOME/epl/runs/wave1-b-v2c}
export RUNS=$R
ARGS=(--set 'client.binary="~/nighthawk-dogfood/bazel-bin/nighthawk_client"')
mkdir -p "$R"
L=$R/chain-v2c.log
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-v2c.rc"; exit "$1"; }
log "chain start pid $$ harness $H ($(git -C "$H" rev-parse --short HEAD 2>/dev/null))"
# (the login shell that started this chain names it, so lines naming chain-v2c.sh are not other work)
busy=$(ps -eo pid,args | grep -E '[b]in/epl|[r]un-session\.sh|[r]un-u\.sh|[r]un-b\.sh|[e]nvoy-static|[e]nvoy-1\.|[e]nvoy-p[12v]|[n]ighthawk_client' | grep -v 'chain-v2c\.sh')
l1=$(cut -d' ' -f1 /proc/loadavg)
if [ -n "$busy" ] || ! python3 -c "import sys;sys.exit(0 if float('$l1') < 0.5 else 1)"; then
  log "box not idle (load $l1): $busy"; fin 10
fi
log "idle: load $l1"
sha256sum ~/epl/bin/envoy-1.40.2 ~/epl/bins/wave1b/envoy-v2 | tee -a "$L"
python3 "$S/make.py" >> "$L" 2>&1 || fin 11
B_RUNS=v2c bash "$S/run-b.sh" smoke "${ARGS[@]}"
B_RUNS=v2c bash "$S/run-b.sh" check || { log "smoke check v2c FAILED: stop"; fin 12; }
log "smoke passed; start v2c"
B_RUNS=v2c B_STOP_S=${B_STOP_S:-3000} bash "$S/run-b.sh" queue "${ARGS[@]}"
rc=$?
last=$(grep -E "end v2c rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
[ "$rc" -eq 0 ] && [ "${last:-x}" = 0 ] || { log "v2c failed (script rc=$rc, run rc=${last:-none})"; fin 20; }
fin 0
