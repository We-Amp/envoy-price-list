#!/bin/bash
# Idle-state knobs for the node CPUs. Run as root (sudo -n).
#   cstate.sh cap            disable every state with exit latency > 2 us (C1E, C3, C6) on 0-19,40-59
#   cstate.sh restore FILE   write back the saved "path value" lines, then verify by read-back
#   cstate.sh verify FILE    read back and compare only
set -u
NODE_CPUS="$(seq 0 19) $(seq 40 59)"
case "${1:-}" in
cap)
  for c in $NODE_CPUS; do
    for s in /sys/devices/system/cpu/cpu$c/cpuidle/state*; do
      lat=$(cat $s/latency)
      if [ "$lat" -gt 2 ]; then echo 1 > $s/disable; fi
    done
  done
  ;;
restore)
  f="$2"
  [ "$(wc -l < "$f")" -eq 400 ] || { echo "bad snapshot $f"; exit 2; }
  while read -r p v; do
    case "$p" in
      /sys/devices/system/cpu/cpu*/cpuidle/state*/disable) echo "$v" > "$p" ;;
      *) echo "skip $p"; exit 2 ;;
    esac
  done < "$f"
  "$0" verify "$f"
  ;;
verify)
  f="$2"; bad=0
  while read -r p v; do
    [ "$(cat "$p")" = "$v" ] || { echo "MISMATCH $p now $(cat "$p") want $v"; bad=1; }
  done < "$f"
  [ $bad -eq 0 ] && echo "VERIFIED $(wc -l < "$f") knobs match $f"
  exit $bad
  ;;
*) echo "usage"; exit 2 ;;
esac
