#!/bin/bash
# The inner command of a mechanism leg: mech-inner.sh sys|kcg PID SECONDS. The tools run under sudo -n,
# pinned to CPUs no measured process uses (W7_TOOL_CPUS, default 8-19).
P=${PERF:-perf}
OUT=${W7_MECH_OUT:?W7_MECH_OUT not set}
TC=${W7_TOOL_CPUS:-8-19}
EAGAIN=${W7_EAGAIN_FILTER:-ret==-11}
kind=$1; pid=$2; n=$3
T=(taskset -c "$TC" sudo -n)
if [ "$kind" = sys ]; then
  "${T[@]}" "$P" stat -x , -o "$OUT/sys-$pid.stat.csv" \
    -e raw_syscalls:sys_enter \
    -e syscalls:sys_enter_epoll_wait --filter 'timeout==0' -e syscalls:sys_exit_epoll_wait \
    -e syscalls:sys_enter_epoll_pwait --filter 'timeout==0' -e syscalls:sys_exit_epoll_pwait \
    -e syscalls:sys_enter_epoll_pwait2 \
    -e syscalls:sys_enter_readv -e syscalls:sys_exit_readv --filter "$EAGAIN" \
    -e syscalls:sys_enter_read -e syscalls:sys_exit_read --filter "$EAGAIN" \
    -e syscalls:sys_enter_recvfrom -e syscalls:sys_exit_recvfrom --filter "$EAGAIN" \
    -e syscalls:sys_enter_recvmsg -e syscalls:sys_enter_recvmmsg \
    -e syscalls:sys_enter_writev -e syscalls:sys_enter_write -e syscalls:sys_enter_sendto \
    -e syscalls:sys_enter_sendmsg -e syscalls:sys_enter_epoll_ctl -e syscalls:sys_enter_accept4 \
    -e syscalls:sys_enter_close \
    -p "$pid" -- sleep "$n" > "$OUT/sys-$pid.stat.err" 2>&1 &
  a=$!
  "${T[@]}" timeout -s INT "$n" "$P" trace -s -p "$pid" -o "$OUT/sys-$pid.trace.txt" > "$OUT/sys-$pid.trace.err" 2>&1 &
  b=$!
  wait "$a"; ra=$?
  wait "$b"; rb=$?
  echo "$(date -u +%FT%TZ) sys pid=$pid stat_rc=$ra trace_rc=$rb (124: ended by the timer)" >> "$OUT/manifest.txt"
elif [ "$kind" = kcg ]; then
  cpus=$(awk '/^Cpus_allowed_list/{print $2}' "/proc/$pid/status")
  "${T[@]}" "$P" record -a -g -F 999 -C "$cpus" -o "$OUT/kcg-$pid.data" -- sleep "$n" > "$OUT/kcg-$pid.record.err" 2>&1
  echo "$(date -u +%FT%TZ) kcg pid=$pid cpus=$cpus record_rc=$?" >> "$OUT/manifest.txt"
else
  sleep "$n"
fi
exit 0
