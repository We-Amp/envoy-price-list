#!/bin/bash
# perf wrapper for the wave 5 track I profiling legs (fp-w5i), after wave 2's perf-lbr.sh. For the harness's
# window command `perf stat ... -p PID -- sleep N` it runs the same perf stat over a `perf record` of the same
# PID for the same N seconds: cycles:u every W5I_FP_PERIOD cycles (default 1,000,003) with frame-pointer call
# chains (this guest has no LBR, BRBE or SPE). Every other call goes straight to perf.
P=${W5I_PERF:-/usr/bin/perf}
OUT=${W5I_FP_OUT:-$HOME/epl/runs/wave5i-prof/fp-data}
PERIOD=${W5I_FP_PERIOD:-1000003}
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
    exec "$P" "${pre[@]}" -- "$P" record -N -q --call-graph=fp -e cycles:u -c "$PERIOD" \
      -p "$pid" -o "$OUT/fp-$pid.data" -- sleep "$n"
  fi
fi
exec "$P" "$@"
