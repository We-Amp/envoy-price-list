#!/bin/bash
# The inner command of a W8-1 mechanism leg: mech-inner.sh sys|kcg PID SECONDS. The tools run under sudo -n,
# pinned to CPUs no measured process uses (W7_TOOL_CPUS, default 8-19).
#   sys   tracepoint counts on PID for SECONDS (perf stat). What W8-1 reads: writev calls, their iovec counts
#         (one filtered row per vlen 1..16 and one for more than 16: Envoy writes at most 16 slices per call) and
#         which of them go to the origin side. The origin-side sockets are PID's established TCP sockets whose
#         local port is not the listener's (W1_LISTEN_PORT, default 10110) nor the admin's (W1_ADMIN_PORT, 9921),
#         read once before the window from `ss -p` (this user's own process); the rows filtered on those fds
#         count writev, writev with one iovec, and readv there. Client-side = all minus origin-side. With no
#         such fd, or more than 380 (the filter text has a page), the filter is fd==-1 and the manifest says so.
#         Also: all syscalls, epoll_wait (and with timeout 0), readv (and returning EAGAIN), read, recvfrom,
#         write, sendto, sendmsg, epoll_ctl, close.
#   kcg   a system-wide call-graph profile (999 Hz) of the CPUs PID may run on
P=${PERF:-perf}
OUT=${W7_MECH_OUT:?W7_MECH_OUT not set}
TC=${W7_TOOL_CPUS:-8-19}
EAGAIN=${W7_EAGAIN_FILTER:-ret==-11}
LP=${W1_LISTEN_PORT:-10110}
AP=${W1_ADMIN_PORT:-9921}
kind=$1; pid=$2; n=$3
T=(taskset -c "$TC" sudo -n)
if [ "$kind" = sys ]; then
  taskset -c "$TC" ss -H -t -n -p state established > "$OUT/ss-$pid.txt" 2>&1
  # column 3 is the local address:port; keep this pid's sockets whose local port is neither the listener's nor the admin's
  awk -v lp=":$LP" -v ap=":$AP" -v pat="pid=$pid,fd=" '
    index($0, pat) { l = $3; sub(/.*:/, ":", l); if (l != lp && l != ap) { s = $0; sub(".*" pat, "", s); sub(/[^0-9].*/, "", s); print s } }' \
    "$OUT/ss-$pid.txt" | sort -n | uniq > "$OUT/fds-$pid.txt"
  nfd=$(wc -l < "$OUT/fds-$pid.txt" | tr -d ' ')
  ndown=$(awk -v lp=":$LP" -v pat="pid=$pid,fd=" 'index($0, pat) { l = $3; sub(/.*:/, ":", l); if (l == lp) c++ } END { print c + 0 }' "$OUT/ss-$pid.txt")
  F=$(awk '{printf "%sfd==%s", (NR > 1 ? "||" : ""), $1}' "$OUT/fds-$pid.txt")
  if [ -z "$F" ] || [ "$nfd" -gt 380 ]; then F='fd==-1'; fi
  echo "$(date -u +%FT%TZ) fds pid=$pid origin_side_fds=$nfd client_side_sockets=$ndown filter_chars=${#F}" >> "$OUT/manifest.txt"
  V=()
  for k in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do V+=(-e syscalls:sys_enter_writev --filter "vlen==$k"); done
  "${T[@]}" "$P" stat -x , -o "$OUT/sys-$pid.stat.csv" \
    -e raw_syscalls:sys_enter \
    -e syscalls:sys_enter_epoll_wait --filter 'timeout==0' -e syscalls:sys_exit_epoll_wait \
    -e syscalls:sys_enter_readv -e syscalls:sys_exit_readv --filter "$EAGAIN" \
    -e syscalls:sys_enter_read -e syscalls:sys_enter_recvfrom \
    -e syscalls:sys_enter_write -e syscalls:sys_enter_sendto -e syscalls:sys_enter_sendmsg \
    -e syscalls:sys_enter_epoll_ctl -e syscalls:sys_enter_close \
    -e syscalls:sys_enter_writev \
    "${V[@]}" \
    -e syscalls:sys_enter_writev --filter 'vlen>16' \
    -e syscalls:sys_enter_writev --filter "$F" \
    -e syscalls:sys_enter_writev --filter "($F)&&vlen==1" \
    -e syscalls:sys_enter_readv --filter "$F" \
    -p "$pid" -- sleep "$n" > "$OUT/sys-$pid.stat.err" 2>&1
  echo "$(date -u +%FT%TZ) sys pid=$pid stat_rc=$? counts=$(grep -c ',syscalls:\|,raw_syscalls:' "$OUT/sys-$pid.stat.csv" 2>/dev/null) raw_sys_enter=$(awk -F, '$3 == "raw_syscalls:sys_enter" {print $1}' "$OUT/sys-$pid.stat.csv" 2>/dev/null)" >> "$OUT/manifest.txt"
elif [ "$kind" = kcg ]; then
  cpus=$(awk '/^Cpus_allowed_list/{print $2}' "/proc/$pid/status")
  "${T[@]}" "$P" record -a -g -F 999 -C "$cpus" -o "$OUT/kcg-$pid.data" -- sleep "$n" > "$OUT/kcg-$pid.record.err" 2>&1
  echo "$(date -u +%FT%TZ) kcg pid=$pid cpus=$cpus record_rc=$?" >> "$OUT/manifest.txt"
else
  sleep "$n"
fi
exit 0
