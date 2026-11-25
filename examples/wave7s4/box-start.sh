#!/bin/bash
# Start the wave 7 S4 chain on the bench box, detached; run once from the freshly extracted tree
# (~/epl/harness-wave7s4), in the login that copied it. Prints the chain's start line and returns.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
R=${RUNS:-$HOME/epl/runs/wave7s4}
export RUNS=$R
echo "box-start: $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg); containers: $(docker ps -q | wc -l)"
[ "$(docker ps -q | wc -l)" = 0 ] || { echo "box-start: a container is running; nothing started"; docker ps --format '{{.ID}} {{.Image}} {{.Names}}'; exit 12; }
if [ -e "$R/chain-s4.rc" ] || [ -e "$R/chain-s4.log" ]; then echo "box-start: $R already has a chain; nothing started"; exit 11; fi
mkdir -p "$R"
cd "$R" && (setsid nohup bash "$H/examples/wave7s4/chain-s4.sh" </dev/null >chain-s4.out 2>&1 &)
sleep 3
grep -m1 'chain s4 start pid' "$R/chain-s4.log" 2>/dev/null || { echo "box-start: no start line yet"; head -5 "$R/chain-s4.out" 2>/dev/null; }
