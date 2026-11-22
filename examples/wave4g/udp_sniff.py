#!/usr/bin/env python3
"""Loopback UDP sniffer for the local check only (never on the bench box): counts the datagrams the SUT
sends from its QUIC port, per destination port (one client socket per QUIC connection), as the kernel
hands them to the device: a GSO batch shows up as one datagram longer than the MTU.

    python3 udp_sniff.py PORT STOPFILE OUT.json      (needs CAP_NET_RAW; runs until STOPFILE exists)
"""
import json
import os
import socket
import struct
import sys

port, stop, out = int(sys.argv[1]), sys.argv[2], sys.argv[3]
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 64 << 20)
s.bind(("lo", 0))
s.settimeout(0.2)
per = {}
big = 0
mx = 0
open(out + ".ready", "w").close()
while not os.path.exists(stop):
    try:
        pkt, addr = s.recvfrom(262144)
    except socket.timeout:
        continue
    if addr[2] == socket.PACKET_OUTGOING:
        continue  # loopback shows each frame twice (out and in); count the inbound copy once
    if len(pkt) < 14 + 20 + 8 or struct.unpack("!H", pkt[12:14])[0] != 0x0800:
        continue
    ihl = (pkt[14] & 0x0F) * 4
    if pkt[23] != 17:
        continue
    sp, dp, ulen = struct.unpack("!HHH", pkt[14 + ihl:14 + ihl + 6])
    if sp != port:
        continue
    n = len(pkt) - 14 - ihl - 8  # UDP payload as captured (a GSO batch: the whole batch)
    d = per.setdefault(str(dp), [0, 0, 0, 0])
    d[0] += 1
    d[1] += n
    if n and pkt[14 + ihl + 8] & 0x80:  # QUIC long header: Initial / Handshake (the handshake flight)
        d[2] += 1
        d[3] += n
    mx = max(mx, n)
    big += 1 if n > 1472 else 0
hs = [v[3] for v in per.values()]
json.dump({"per_dst": per, "long_header_bytes_per_dst": sorted(hs), "datagrams": sum(v[0] for v in per.values()), "bytes": sum(v[1] for v in per.values()),
           "max_payload": mx, "over_mtu": big}, open(out, "w"))
