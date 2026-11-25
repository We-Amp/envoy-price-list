#!/bin/bash
# Start the tail chain on the bench box, detached. Run from the staged tree in the login that staged it. Prints the
# chain's start line and returns. The chain is started once: its log must not exist yet, and no container may run.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
R=${RUNS:-$HOME/epl/runs/wave8w3}
export RUNS=$R
echo "box-start tail: $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg); containers: $(docker ps -q | wc -l)"
[ "$(docker ps -q | wc -l)" = 0 ] || { echo "box-start: a container is running; nothing started"; docker ps --format '{{.ID}} {{.Image}} {{.Names}}'; exit 12; }
if [ -e "$R/chain-tail.rc" ] || [ -e "$R/chain-tail.log" ]; then echo "box-start: $R already has the tail chain; nothing started"; exit 11; fi
mkdir -p "$R"
cd "$R" && (setsid nohup bash "$H/examples/wave8tail/chain-tail.sh" </dev/null >"chain-tail.out" 2>&1 &)
sleep 3
grep -m1 "chain tail start pid" "$R/chain-tail.log" 2>/dev/null || { echo "box-start: no start line yet"; head -5 "$R/chain-tail.out" 2>/dev/null; }
