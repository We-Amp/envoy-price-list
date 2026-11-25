#!/bin/bash
# The inner command of an S5 mechanism leg: mech-inner.sh PID SECONDS. Tracepoint counts on PID for SECONDS
# (the event list and filters of S1's syscall leg; no perf trace beside it, so a loaded leg carries less tracer
# cost). The tool runs under sudo -n, pinned to CPUs no measured process uses (W7_TOOL_CPUS, default 8-19).
P=${PERF:-perf}
OUT=${W7_MECH_OUT:?W7_MECH_OUT not set}
TC=${W7_TOOL_CPUS:-8-19}
EAGAIN=${W7_EAGAIN_FILTER:-ret==-11}
pid=$1; n=$2
taskset -c "$TC" sudo -n "$P" stat -x , -o "$OUT/sys-$pid.stat.csv" \
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
  -p "$pid" -- sleep "$n" > "$OUT/sys-$pid.stat.err" 2>&1
echo "$(date -u +%FT%TZ) sys pid=$pid stat_rc=$? counts=$(grep -c ',syscalls:\|,raw_syscalls:' "$OUT/sys-$pid.stat.csv" 2>/dev/null) raw_sys_enter=$(awk -F, '$3 == "raw_syscalls:sys_enter" {print $1}' "$OUT/sys-$pid.stat.csv" 2>/dev/null)" >> "$OUT/manifest.txt"
exit 0
