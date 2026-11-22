#!/bin/bash
# Start the wave 3 track E chain on the bench box, detached; run once from the freshly extracted tree
# (~/epl/harness-wave3e), in the same login that copied it. Prints the chain's start line and returns.
# E2 session: RUNS=~/epl/runs/wave3e2 E_RUNS=e2-plain E_HRR=1 bash .../box-start.sh (the variables reach the chain).
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
R=${RUNS:-$HOME/epl/runs/wave3e}
export RUNS=$R
echo "box-start: $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)"
busy=$(ps -eo pid,etime,args | grep -E '[b]in/epl|[r]un-session\.sh|[r]un-w2\.sh|[r]un-e\.sh|[c]hain-e\.sh|[c]hain-w2\.sh|[e]nvoy-static|[e]nvoy-1\.|[n]ighthawk_client')
if [ -n "$busy" ]; then echo "box-start: not idle, nothing started:"; echo "$busy"; exit 10; fi
if [ -e "$R/chain-e.rc" ] || [ -e "$R/chain-e.log" ]; then echo "box-start: $R already has a chain; nothing started"; exit 11; fi
mkdir -p "$R"
cd "$R" && (setsid nohup bash "$H/examples/wave3e/chain-e.sh" </dev/null >chain-e.out 2>&1 &)
sleep 3
grep -m1 'chain e start pid' "$R/chain-e.log" 2>/dev/null || { echo "box-start: no start line yet"; cat "$R/chain-e.out" 2>/dev/null | head -5; }
tail -3 "$R/chain-e.log" 2>/dev/null
