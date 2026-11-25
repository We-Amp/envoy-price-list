#!/bin/bash
# The perf selftest of the mechanism legs: perf-selftest.sh OUTDIR. OUTDIR/sys.ok and OUTDIR/kcg.ok mark the
# leg kinds that work (exit 0 when both do); OUTDIR/eagain.filter and OUTDIR/sys.set are the EAGAIN filter
# and the tracepoint list that parsed. Checked when: sudo -n works; the syscall leg's exact event list
# counts on a test process (EAGAIN reads and zero-timeout epoll waits counted, by the tracepoints and by
# perf trace -s); a 1 s system-wide call-graph record of a CPU that runs a syscall loop of this script
# resolves at least one kernel symbol (S1's first chain asked for three from an idle CPU and dropped its
# call-graph legs). Installs nothing; changes no setting.
P=${PERF:-perf}
D=${1:?output directory}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$D"
say() { echo "selftest: $*"; }
sudo -n true || { say "sudo -n not available"; exit 1; }
tp() {  # one run of the syscall leg on a process that reads EAGAIN and waits with timeout 0
  taskset -c 8-19 python3 -I -c '
import os, select, time
r, w = os.pipe(); os.set_blocking(r, False)
ep = select.epoll(); ep.register(r, select.EPOLLIN)
end = time.time() + 6
while time.time() < end:
    try: os.read(r, 1)
    except BlockingIOError: pass
    ep.poll(0)
    time.sleep(0.001)
' &
  local tpid=$!
  sleep 1
  rm -f "$D"/sys-"$tpid".*
  W7_MECH_OUT=$D W7_EAGAIN_FILTER=$1 W7_SYS_SET=$2 bash "$HERE/mech-inner.sh" sys "$tpid" 2
  wait "$tpid"
  echo "$tpid"
}
ok=0
for try in 'ret==-11 full' 'ret==-11 s1' 'ret<0 s1'; do
  flt=${try% *}; set_=${try#* }
  tpid=$(tp "$flt" "$set_" | tail -1)
  s=$D/sys-$tpid.stat.csv
  eag=$(awk -F, '$3 ~ /sys_exit_read$/ {print int($1)}' "$s" 2>/dev/null | head -1)
  ep0=$(awk -F, '$3 ~ /sys_enter_epoll_wait$/ {print int($1)}' "$s" 2>/dev/null | head -1)
  tot=$(awk -F, '$3 ~ /raw_syscalls:sys_enter$/ {print int($1)}' "$s" 2>/dev/null | head -1)
  tr=$(grep -cE '^ +(read|epoll_wait) +[0-9]+ +[0-9]+' "$D/sys-$tpid.trace.txt" 2>/dev/null)
  say "filter '$flt', list $set_: EAGAIN reads ${eag:-none}, zero-timeout epoll_wait ${ep0:-none}, syscalls ${tot:-none}, perf trace rows ${tr:-0}"
  if [ "${eag:-0}" -ge 100 ] && [ "${ep0:-0}" -ge 100 ] && [ "${tot:-0}" -ge 300 ]; then
    echo "$flt" > "$D/eagain.filter"; echo "$set_" > "$D/sys.set"; ok=1
    # perf trace -s is the by-name table; the tracepoint counts carry the count gates without it
    if [ "${tr:-0}" -ge 2 ]; then say "perf trace -s prints its table"; else say "perf trace -s gave no table (tracepoint counts only): $(head -c 300 "$D/sys-$tpid.trace.err" 2>/dev/null)"; fi
    break
  fi
  say "stat stderr: $(head -c 600 "$D/sys-$tpid.stat.err" 2>/dev/null)"
  say "trace stderr: $(head -c 600 "$D/sys-$tpid.trace.err" 2>/dev/null)"
done
if [ "$ok" = 1 ]; then touch "$D/sys.ok"; else say "syscall leg does not work"; fi
# a syscall loop of our own on CPU 8 for the 1 s record (an idle CPU gives a handful of samples)
taskset -c 8 timeout 4 dd if=/dev/zero of=/dev/null bs=512 > /dev/null 2>&1 &
ddpid=$!
sleep 0.5
taskset -c 9-19 sudo -n "$P" record -a -g -F 999 -C 8 -o "$D/selftest.data" -- sleep 1 > "$D/selftest.record.err" 2>&1
wait "$ddpid" 2>/dev/null
taskset -c 8-19 sudo -n "$P" report -i "$D/selftest.data" --stdio --no-children --sort sym 2>/dev/null > "$D/selftest.report.txt"
k=$(grep -cE '\[k\] [A-Za-z_]' "$D/selftest.report.txt")
taskset -c 8-19 sudo -n "$P" script -i "$D/selftest.data" -F comm,pid,tid,cpu,period,event,ip,sym,dso 2>/dev/null \
  | taskset -c 8-19 python3 -I "$HERE/fold.py" 2> "$D/selftest.fold.err" | gzip > "$D/selftest.folded.gz"
sudo -n rm -f "$D/selftest.data"
say "call-graph record: $k kernel symbols resolved; $(cat "$D/selftest.fold.err" 2>/dev/null)"
if [ "$k" -ge 1 ]; then touch "$D/kcg.ok"; else say "kernel symbols do not resolve: $(head -c 400 "$D/selftest.record.err")"; fi
[ -e "$D/sys.ok" ] && [ -e "$D/kcg.ok" ] && { say "PASS"; exit 0; }
say "PARTIAL or FAILED (sys: $([ -e "$D/sys.ok" ] && echo ok || echo no), kcg: $([ -e "$D/kcg.ok" ] && echo ok || echo no))"
exit 2
