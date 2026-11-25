#!/bin/bash
# perf wrapper for the span-path evidence legs (non-scored). For `perf stat ... -p PID -- sleep N` (the
# harness's window command) it runs the same perf stat over span-inner.sh, which records a user-space profile
# of PID for the same N seconds. Every other call goes straight to perf.
#   PERF          perf binary     W7_MECH_OUT   output directory
P=${PERF:-perf}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${W7_MECH_OUT:?W7_MECH_OUT not set}
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
    echo "$(date -u +%FT%TZ) kind=span pid=$pid exe=$(readlink "/proc/$pid/exe") bootstrap=$(tr '\0' '\n' < "/proc/$pid/cmdline" | grep -m1 'envoy-bootstrap') cpus=$(awk '/^Cpus_allowed_list/{print $2}' "/proc/$pid/status") window_s=$n" >> "$OUT/manifest.txt"
    exec "$P" "${pre[@]}" -- bash "$HERE/span-inner.sh" "$pid" "$n"
  fi
fi
exec "$P" "$@"
