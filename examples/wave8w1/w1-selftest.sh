#!/bin/bash
# The perf selftest of W8-1's tracepoint legs: w1-selftest.sh OUTDIR. OUTDIR/sys.ok marks that the exact command
# of a traced leg (mech-inner.sh sys) counts what W8-1 reads, on a test process whose calls are known. The test
# process listens on W1_LISTEN_PORT (loopback), holds 2 accepted sockets (local port = the listener's: the
# "client side") and 3 sockets it connected itself (the "origin side"), and every millisecond makes: one writev
# of 1 iovec on each of the 3 origin-side sockets, one writev of 2 iovecs on the first accepted socket, one writev
# of 16 iovecs on the second, one readv on each origin-side socket, one read that returns EAGAIN and one epoll
# wait with timeout 0. Required over 2 s: 3 origin-side fds found; 33 rows; writev rows in the shares 3:1:1 for
# vlen 1, 2 and 16 (1% tolerance) and nothing in any other vlen row; writev on the origin-side fds = writev with
# vlen 1 = the same with both filters; readv on the origin-side fds at least 100; EAGAIN readv and zero-timeout
# waits at least 100. OUTDIR/eagain.filter is the EAGAIN filter that parsed. Installs nothing; changes no setting.
P=${PERF:-perf}
D=${1:?output directory}
HERE=$(cd "$(dirname "$0")" && pwd)
TC=${W7_TOOL_CPUS:-8-19}
PORT=${W1_LISTEN_PORT:-10110}
mkdir -p "$D"
say() { echo "w1 selftest: $*"; }
sudo -n true || { say "sudo -n not available"; exit 1; }
tp() {
  taskset -c "$TC" python3 -I -c '
import os, select, socket, sys, time
port = int(sys.argv[1])
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", port)); srv.listen(8)
cl, ac = [], []
for _ in range(3):
    c = socket.create_connection(("127.0.0.1", port)); cl.append(c)
    a, _x = srv.accept(); ac.append(a)
ac.pop().close(); cl.pop().close()
cl.append(socket.create_connection(("127.0.0.1", port))); extra, _x = srv.accept()
# cl: 3 sockets this process connected (origin side); ac: 2 accepted (client side); extra: accepted, only read
for s in cl + ac + [extra]:
    s.setblocking(False)
ep = select.epoll(); ep.register(srv.fileno(), select.EPOLLIN)
buf = bytearray(65536)
end = time.time() + 7
while time.time() < end:
    for c in cl:
        os.writev(c.fileno(), [b"y"])
    os.writev(ac[0].fileno(), [b"x"] * 2)
    os.writev(ac[1].fileno(), [b"x"] * 16)
    for c in cl:
        try: os.readv(c.fileno(), [buf])
        except BlockingIOError: pass
    for s in ac + [extra]:
        try: s.recv(65536)
        except BlockingIOError: pass
    try: os.readv(extra.fileno(), [buf])
    except BlockingIOError: pass
    ep.poll(0)
    time.sleep(0.001)
' "$PORT" &
  local tpid=$!
  sleep 1.5
  rm -f "$D"/sys-"$tpid".* "$D"/fds-"$tpid".txt "$D"/ss-"$tpid".txt
  W7_MECH_OUT=$D W7_EAGAIN_FILTER=$1 W1_LISTEN_PORT=$PORT bash "$HERE/mech-inner.sh" sys "$tpid" 2
  wait "$tpid"
  echo "$tpid"
}
ok=0
for flt in 'ret==-11' 'ret<0'; do
  tpid=$(tp "$flt" | tail -1)
  s=$D/sys-$tpid.stat.csv
  nfd=$(wc -l < "$D/fds-$tpid.txt" 2>/dev/null | tr -d ' ')
  res=$(python3 -I - "$s" <<'PYEOF'
import sys
rows = []
try:
    for line in open(sys.argv[1]):
        f = line.strip().split(",")
        if len(f) >= 3 and f[2] and not line.startswith("#"):
            try:
                rows.append((f[2].split(":")[-1], float(f[0])))
            except ValueError:
                pass
except OSError:
    pass
wv = [v for k, v in rows if k == "sys_enter_writev"]
rv = [v for k, v in rows if k == "sys_enter_readv"]
get = lambda name: next((v for k, v in rows if k == name), 0.0)
ok, why = True, []
if len(rows) != 33 or len(wv) != 20 or len(rv) != 2:
    ok = False; why.append("rows %d (33), writev rows %d (20), readv rows %d (2)" % (len(rows), len(wv), len(rv)))
else:
    tot, hist, over, up, up1 = wv[0], wv[1:17], wv[17], wv[18], wv[19]
    n = tot / 5.0
    near = lambda x, y: y > 0 and abs(x / y - 1.0) <= 0.01
    if tot < 500: ok = False; why.append("writev %d under 500" % tot)
    if not (near(hist[0], 3 * n) and near(hist[1], n) and near(hist[15], n)): ok = False; why.append("vlen rows 1, 2, 16: %s %s %s of %s" % (hist[0], hist[1], hist[15], tot))
    if sum(hist[2:15]) + over != 0: ok = False; why.append("other vlen rows not 0")
    if not (near(up, 3 * n) and up1 == up): ok = False; why.append("origin-side writev %s, with vlen 1 %s, expected %s" % (up, up1, 3 * n))
    if rv[1] < 100 or rv[1] > rv[0]: ok = False; why.append("origin-side readv %s of %s" % (rv[1], rv[0]))
    if get("sys_exit_readv") < 100: ok = False; why.append("EAGAIN readv %s" % get("sys_exit_readv"))
    if get("sys_enter_epoll_wait") < 100: ok = False; why.append("zero-timeout epoll_wait %s" % get("sys_enter_epoll_wait"))
    why.append("writev %d = vlen1 %d + vlen2 %d + vlen16 %d; origin-side writev %d (vlen 1: %d), readv %d of %d; EAGAIN readv %d; zero-timeout waits %d; syscalls %d" % (
        tot, hist[0], hist[1], hist[15], up, up1, rv[1], rv[0], get("sys_exit_readv"), get("sys_enter_epoll_wait"), get("sys_enter")))
print(("OK " if ok else "BAD ") + "; ".join(why))
PYEOF
)
  say "filter '$flt': origin-side fds ${nfd:-none} (3 expected); $res"
  if [ "${nfd:-0}" = 3 ] && [ "${res%% *}" = OK ]; then echo "$flt" > "$D/eagain.filter"; ok=1; break; fi
  say "stat stderr: $(head -c 600 "$D/sys-$tpid.stat.err" 2>/dev/null)"
  say "manifest: $(tail -2 "$D/manifest.txt" 2>/dev/null | tr '\n' ' '); ss lines: $(head -3 "$D/ss-$tpid.txt" 2>/dev/null | tr '\n' '|')"
done
if [ "$ok" = 1 ]; then touch "$D/sys.ok"; say "PASS"; exit 0; fi
say "FAILED: the traced leg's command does not count what W8-1 reads"
exit 2
