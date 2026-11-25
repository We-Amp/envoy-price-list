#!/bin/bash
# What the box says about the sockets the session measures, printed between runs (never inside a leg):
# plain-tcp.sh LABEL. The kernel, whether MPTCP is on and whether any MPTCP socket or MPTCP counter exists,
# and whether a BPF program of a socket-redirect kind or a sockmap is loaded (bpftool under sudo -n when the
# box has it; otherwise the pinned BPF objects and the fact that the tool is missing are printed). Reads only;
# changes no setting; installs nothing.
T=(taskset -c 8-19)
echo "plain-tcp [$1] $(date -u +%FT%TZ) kernel $(uname -r)"
echo "plain-tcp [$1] net.mptcp.enabled=$(cat /proc/sys/net/mptcp/enabled 2>/dev/null || echo absent) mptcp_sockets=$("${T[@]}" ss -H -M 2>/dev/null | wc -l)"
if command -v nstat >/dev/null 2>&1; then
  echo "plain-tcp [$1] MPTCP counters above zero (nstat -az): $("${T[@]}" nstat -az 2>/dev/null | awk '/MPTcp/ && $2 > 0 {printf "%s=%s ", $1, $2} END {print ""}')(end of list)"
else
  echo "plain-tcp [$1] nstat not on the box; /proc/net/netstat MPTcpExt line: $(grep -c '^MPTcpExt' /proc/net/netstat 2>/dev/null) rows"
fi
BT=$(command -v bpftool 2>/dev/null || ls /usr/lib/linux-tools/*/bpftool 2>/dev/null | head -1)
if [ -n "$BT" ] && sudo -n true 2>/dev/null; then
  progs=$("${T[@]}" sudo -n "$BT" prog show 2>&1)
  maps=$("${T[@]}" sudo -n "$BT" map show 2>&1)
  echo "plain-tcp [$1] bpftool $BT: programs loaded $(echo "$progs" | grep -cE '^[0-9]+:'), of a socket-redirect kind (sk_skb, sk_msg, sock_ops) $(echo "$progs" | grep -cE '^[0-9]+: (sk_skb|sk_msg|sock_ops)'); maps $(echo "$maps" | grep -cE '^[0-9]+:'), sockmap or sockhash $(echo "$maps" | grep -cE '^[0-9]+: (sockmap|sockhash)')"
  echo "plain-tcp [$1] program types: $(echo "$progs" | sed -n 's/^[0-9]*: \([a-z_]*\) .*/\1/p' | sort | uniq -c | tr '\n' ';')"
  echo "plain-tcp [$1] map types: $(echo "$maps" | sed -n 's/^[0-9]*: \([a-z_]*\) .*/\1/p' | sort | uniq -c | tr '\n' ';')"
else
  echo "plain-tcp [$1] bpftool not available (path '${BT:-none}', sudo -n $(sudo -n true 2>/dev/null && echo ok || echo no)): sockmap not checked by tool"
fi
echo "plain-tcp [$1] pinned BPF objects under /sys/fs/bpf: $(sudo -n find /sys/fs/bpf -mindepth 1 2>/dev/null | wc -l)"
exit 0
