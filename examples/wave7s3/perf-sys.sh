#!/bin/bash
# perf wrapper for the syscall legs (non-scored). For `perf stat ... -p PID -- sleep N` (the harness's
# window command) it runs the same perf stat over mech-inner.sh, which counts PID's syscalls for the same
# N seconds (perf trace -s, and tracepoint counts with filters). Every other call goes straight to perf.
#   PERF          perf binary     W7_MECH_OUT   output directory
P=${PERF:-perf}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${W7_MECH_OUT:?W7_MECH_OUT not set}
KIND=${W7_MECH_KIND:-sys}
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
    echo "$(date -u +%FT%TZ) kind=$KIND pid=$pid exe=$(readlink "/proc/$pid/exe") cpus=$(awk '/^Cpus_allowed_list/{print $2}' "/proc/$pid/status") window_s=$n" >> "$OUT/manifest.txt"
    exec "$P" "${pre[@]}" -- bash "$HERE/mech-inner.sh" "$KIND" "$pid" "$n"
  fi
fi
exec "$P" "$@"
