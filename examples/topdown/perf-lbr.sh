#!/bin/bash
# perf wrapper for the lbr-a legs. For `perf stat ... -p PID -- sleep N` (the harness's window
# command) it runs the same perf stat, but over `perf record -b` of the same PID for the same
# N seconds, so the LBR profile covers exactly the measured window under the shape's load.
# Every other call (`--version`) goes straight to perf.
#   PERF        perf binary (default: perf on PATH)
#   TD_LBR_OUT  where the lbr-<pid>.data files and manifest.txt go (default ~/epl/runs/topdown-a/lbr-data)
P=${PERF:-perf}
OUT=${TD_LBR_OUT:-$HOME/epl/runs/topdown-a/lbr-data}
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
    echo "$(date -u +%FT%TZ) pid=$pid exe=$(readlink "/proc/$pid/exe") window_s=$n" >> "$OUT/manifest.txt"
    # two sampling events, both with the LBR branch stack (-b) and frame-pointer call chains (-g):
    #  br_inst_retired.near_taken (C4/20, PEBS) every 100003 taken branches: the AutoFDO/BOLT input
    #  cycles:u every 1000003 cycles: inclusive cycle attribution (the share of cycles spent in the
    #  upstream filter-manager machinery, see lbr-post.py)
    exec "$P" "${pre[@]}" -- "$P" record -b -g -N -q \
      -e cpu/event=0xc4,umask=0x20,period=100003/upp -e cpu/cycles,period=1000003/u \
      -p "$pid" -o "$OUT/lbr-$pid.data" -- sleep "$n"
  fi
fi
exec "$P" "$@"
