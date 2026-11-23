#!/bin/bash
# perf wrapper for the wave 6 track J profiling legs (spe-w6j-*), after wave 2's perf-lbr.sh. For the harness's
# window command `perf stat ... -p PID -- sleep N` it runs the same perf stat over a `perf record` of the same PID for
# the same N seconds with SPE branch sampling (arm_spe_0, branch_filter=1, jitter=1, user only, every W6J_SPE_PERIOD
# operations, default 10,007). Every other call goes straight to perf.
P=${W6J_PERF:-/usr/bin/perf}
OUT=${W6J_SPE_OUT:-$HOME/epl/runs/wave6j-prof/spe-data}
PERIOD=${W6J_SPE_PERIOD:-10007}
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
    exec "$P" "${pre[@]}" -- "$P" record -N -q -e "arm_spe_0/branch_filter=1,jitter=1/u" -c "$PERIOD" \
      -p "$pid" -o "$OUT/spe-$pid.data" -- sleep "$n"
  fi
fi
exec "$P" "$@"
