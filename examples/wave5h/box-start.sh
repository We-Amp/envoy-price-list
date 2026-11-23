#!/bin/bash
# Start one track H block on the bench box, detached; run from the extracted tree (~/epl/harness-wave5h)
# in the login that starts the block. Prints the chain's start line and returns at once.
#   H_BLOCK=H0|A|B|C bash ~/epl/harness-wave5h/examples/wave5h/box-start.sh
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
TOP=${H_TOP:-$HOME/epl/runs/wave5h}
B=${H_BLOCK:?H_BLOCK must be H0, A, B, C or D}
R=$TOP/$B
echo "box-start: $(date -u +%FT%TZ) block $B load $(cut -d' ' -f1-3 /proc/loadavg) uptime $(cut -d' ' -f1 /proc/uptime)s"
# idleness by load and CPU only; no process is matched by its command line
st=$(bash "$H/examples/wave4g/idle.sh") || { echo "box-start: $st; nothing started"; exit 10; }
echo "box-start: $st"
if [ -e "$R/chain-h.rc" ] || [ -e "$R/chain-h.log" ]; then echo "box-start: $R already has a chain; nothing started"; exit 11; fi
mkdir -p "$R"
cd "$R" && (H_BLOCK=$B H_TOP=$TOP setsid nohup bash "$H/examples/wave5h/chain-h.sh" </dev/null >chain-h.out 2>&1 &)
sleep 5
grep -m1 'chain h start pid' "$R/chain-h.log" 2>/dev/null || { echo "box-start: no start line yet"; head -5 "$R/chain-h.out" 2>/dev/null; }
tail -3 "$R/chain-h.log" 2>/dev/null
