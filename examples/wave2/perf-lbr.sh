#!/bin/bash
# perf wrapper for the wave 2 profiling legs (lbr-w2, lbr-w2-opt), after track A's perf-lbr.sh.
# For the harness's window command `perf stat ... -p PID -- sleep N` it runs the same perf stat over a
# `perf record -b` of the same PID for the same N seconds, so the LBR profile covers exactly the
# measured window under the shape's load. Every other call (`--version`) goes straight to perf.
# One sampling event: br_inst_retired.near_taken (C4/20, PEBS, user) every W2_LBR_PERIOD taken
# branches (default 20,003: five times track A's rate), with the 16-deep LBR branch stack. This is the
# input of perf2bolt (BOLT) and llvm-profgen (AutoFDO). No call chains, no other event.
# The data goes to W2_LBR_OUT (default ~/epl/runs/wave2-prof/lbr-data) with a manifest pid -> exe.
P=${W2_PERF:-perf}
OUT=${W2_LBR_OUT:-$HOME/epl/runs/wave2-prof/lbr-data}
PERIOD=${W2_LBR_PERIOD:-20003}
if [ "${1:-}" = stat ]; then
  pid=""; n=""; pre=(); seen=0
  args=("$@")
  for ((i = 0; i < ${#args[@]}; i++)); do
    a="${args[i]}"
    [ "$a" = -p ] && pid="${args[i+1]}"
    if [ "$a" = -- ]; then seen=1; n="${args[i+2]}"; break; fi
    pre+=("$a")
  done
  if [ -n "$pid" ] && [ -n "$n" ] && [ "$seen" = 1 ]; then
    mkdir -p "$OUT"
    exe=$(readlink "/proc/$pid/exe")
    echo "$(date -u +%FT%TZ) pid=$pid exe=$exe window_s=$n period=$PERIOD" >> "$OUT/manifest.txt"
    exec "$P" "${pre[@]}" -- "$P" record -b -N -q \
      -e "cpu/event=0xc4,umask=0x20,period=$PERIOD/upp" \
      -p "$pid" -o "$OUT/lbr-$pid.data" -- sleep "$n"
  fi
fi
exec "$P" "$@"
