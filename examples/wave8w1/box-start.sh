#!/bin/bash
# Start one chain of the wave 8 session W8-1 on the bench box, detached: box-start.sh pre|w1|tail. Run from the
# staged tree (~/epl/harness-wave8w1) in the login that staged or released it. Prints the chain's start line and
# returns. A chain is started once: its log must not exist yet, and no container may be running.
set -u
K=${1:?pre, w1 or tail}
case "$K" in pre|w1|tail) ;; *) echo "box-start: pre, w1 or tail"; exit 2 ;; esac
H=$(cd "$(dirname "$0")/../.." && pwd)
R=${RUNS:-$HOME/epl/runs/wave8w1}
export RUNS=$R
echo "box-start $K: $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg); containers: $(docker ps -q | wc -l)"
[ "$(docker ps -q | wc -l)" = 0 ] || { echo "box-start: a container is running; nothing started"; docker ps --format '{{.ID}} {{.Image}} {{.Names}}'; exit 12; }
if [ -e "$R/chain-$K.rc" ] || [ -e "$R/chain-$K.log" ]; then echo "box-start: $R already has chain $K; nothing started"; exit 11; fi
mkdir -p "$R"
cd "$R" && (setsid nohup bash "$H/examples/wave8w1/chain-$K.sh" </dev/null >"chain-$K.out" 2>&1 &)
sleep 3
grep -m1 "chain $K start pid" "$R/chain-$K.log" 2>/dev/null || { echo "box-start: no start line yet"; head -5 "$R/chain-$K.out" 2>/dev/null; }
