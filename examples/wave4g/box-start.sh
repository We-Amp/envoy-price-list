#!/bin/bash
# Start the wave 4 track G chain on the bench box, detached; run once from the freshly extracted tree
# (~/epl/harness-wave4g), in the same login that copied it. Prints the chain's start line and returns.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
R=${RUNS:-$HOME/epl/runs/wave4g}
export RUNS=$R
echo "box-start: $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)"
# idleness by load and CPU only; no process is matched by its command line
st=$(bash "$H/examples/wave4g/idle.sh") || { echo "box-start: $st; nothing started"; exit 10; }
echo "box-start: $st"
if [ -e "$R/chain-g.rc" ] || [ -e "$R/chain-g.log" ]; then echo "box-start: $R already has a chain; nothing started"; exit 11; fi
mkdir -p "$R"
cd "$R" && (setsid nohup bash "$H/examples/wave4g/chain-g.sh" </dev/null >chain-g.out 2>&1 &)
sleep 3
grep -m1 'chain g start pid' "$R/chain-g.log" 2>/dev/null || { echo "box-start: no start line yet"; head -5 "$R/chain-g.out" 2>/dev/null; }
tail -3 "$R/chain-g.log" 2>/dev/null
