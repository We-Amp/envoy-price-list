#!/bin/bash
# The inner command of a span-path evidence leg: span-inner.sh PID SECONDS. A user-space cycles profile of
# the Envoy process (all its threads), under sudo -n, pinned to CPUs no measured process uses.
P=${PERF:-perf}
OUT=${W7_MECH_OUT:?W7_MECH_OUT not set}
TC=${W7_TOOL_CPUS:-8-19}
pid=$1; n=$2
taskset -c "$TC" sudo -n "$P" record -e cycles:u -F 1999 -p "$pid" -o "$OUT/span-$pid.data" -- sleep "$n" > "$OUT/span-$pid.record.err" 2>&1
echo "$(date -u +%FT%TZ) span pid=$pid record_rc=$?" >> "$OUT/manifest.txt"
exit 0
