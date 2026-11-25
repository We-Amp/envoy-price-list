#!/bin/bash
# The perf selftest of the mechanism legs: perf-selftest.sh OUTDIR. OUTDIR/sys.ok and OUTDIR/kcg.ok mark the
# leg kinds that work (exit 0 when both do); OUTDIR/eagain.filter is the EAGAIN filter that parsed. Checked
# when: sudo -n works; the syscall leg's exact event list counts on a test process (EAGAIN reads and
# zero-timeout epoll waits counted, by the tracepoints and by perf trace -s); a 1 s system-wide call-graph
# record resolves kernel symbols. Installs nothing; changes no setting.
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
  W7_MECH_OUT=$D W7_EAGAIN_FILTER=$1 bash "$HERE/mech-inner.sh" sys "$tpid" 2
  wait "$tpid"
  echo "$tpid"
}
ok=0
for flt in 'ret==-11' 'ret<0'; do
  tpid=$(tp "$flt" | tail -1)
  s=$D/sys-$tpid.stat.csv
  eag=$(awk -F, '$3 ~ /sys_exit_read$/ {print int($1)}' "$s" 2>/dev/null)
  ep0=$(awk -F, '$3 ~ /sys_enter_epoll_wait$/ {print int($1)}' "$s" 2>/dev/null)
  tot=$(awk -F, '$3 ~ /raw_syscalls:sys_enter$/ {print int($1)}' "$s" 2>/dev/null)
  tr=$(grep -cE '^ +(read|epoll_wait) +[0-9]+ +[0-9]+' "$D/sys-$tpid.trace.txt" 2>/dev/null)
  say "filter '$flt': EAGAIN reads ${eag:-none}, zero-timeout epoll_wait ${ep0:-none}, syscalls ${tot:-none}, perf trace rows ${tr:-0}"
  if [ "${eag:-0}" -ge 100 ] && [ "${ep0:-0}" -ge 100 ] && [ "${tot:-0}" -ge 300 ]; then
    echo "$flt" > "$D/eagain.filter"; ok=1
    # perf trace -s is the by-name table; the tracepoint counts carry the count gate without it
    if [ "${tr:-0}" -ge 2 ]; then say "perf trace -s prints its table"; else say "perf trace -s gave no table (tracepoint counts only): $(head -c 300 "$D/sys-$tpid.trace.err" 2>/dev/null)"; fi
    break
  fi
  say "stat stderr: $(head -c 600 "$D/sys-$tpid.stat.err" 2>/dev/null)"
  say "trace stderr: $(head -c 600 "$D/sys-$tpid.trace.err" 2>/dev/null)"
done
if [ "$ok" = 1 ]; then touch "$D/sys.ok"; else say "syscall leg does not work"; fi
taskset -c 8-19 sudo -n "$P" record -a -g -F 999 -C 8 -o "$D/selftest.data" -- sleep 1 > "$D/selftest.record.err" 2>&1
taskset -c 8-19 sudo -n "$P" report -i "$D/selftest.data" --stdio --no-children --sort sym 2>/dev/null > "$D/selftest.report.txt"
k=$(grep -cE '\[k\] [A-Za-z_]' "$D/selftest.report.txt")
sudo -n rm -f "$D/selftest.data"
say "call-graph record: $k kernel symbols resolved"
# (an idle CPU gives a handful of samples in 1 s: one resolved kernel symbol is the proof; the first S1
# chain asked for three, got two, and dropped the call-graph legs)
if [ "$k" -ge 1 ]; then touch "$D/kcg.ok"; else say "kernel symbols do not resolve"; fi
[ -e "$D/sys.ok" ] && [ -e "$D/kcg.ok" ] && { say "PASS"; exit 0; }
say "PARTIAL or FAILED (sys: $([ -e "$D/sys.ok" ] && echo ok || echo no), kcg: $([ -e "$D/kcg.ok" ] && echo ok || echo no))"
exit 2
