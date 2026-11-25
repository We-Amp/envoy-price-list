#!/bin/bash
# The tail add-on after session W8-1 (not part of it; unscored for CPU): the count for W8-2's open flag on
# server-side QUIC retransmissions, in the design of the W8-2 result review. One detached chain, one login;
# start it with box-start.sh tail, only after chain-w1.sh has ended.
#   part A  tail-a-r1 .. tail-a-r8: h3-official, h3-off, h3-stop-on, h3-both-on on shape s (4 KB over HTTP/3, 2,000
#           req/s, 16 connections) with Envoy's QUIC statistics on; arm order from two 4x4 Williams squares; odd
#           rounds 10 s of traffic, even rounds 40 s (part B: the duration split). Every leg also has the
#           harness's 5 s warm-up client run, so a leg is two client runs of 16 connections: 32 lifetimes.
#   part C  tail-c-r1 .. tail-c-r4: h3-off and h3-both-on at 16 req/s (one request per second per connection) for
#           60 s; arm order alternates by round.
# The kernel's Udp line is logged before and after every round (the whole round, not only the windows). A round
# is started only when it can end inside the cap (TAIL_CAP_MIN, default 35 minutes after this chain's start, by
# the estimates 100 s, 220 s and 170 s for a short, a long and a quiet round); the log says what was skipped.
# Nothing is replaced or repeated. Exit code in $R/chain-tail.rc (0: the chain reached its end).
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave8w1
R=${RUNS:-$HOME/epl/runs/wave8w1}
export RUNS=$R
L=$R/chain-tail.log
T0=$(date +%s)
CAP=$(( ${TAIL_CAP_MIN:-35} * 60 ))
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
els() { echo $(( $(date +%s) - T0 )); }
fin() { log "chain end rc=$1 after $(( $(els) / 60 )) min"; echo "$1" > "$R/chain-tail.rc"; exit "$1"; }
udp() { awk '/^Udp: [0-9]/{print}' /proc/net/snmp; }
log "chain tail start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)); cap $(( CAP / 60 )) min"
if [ -e "$R/chain-pre.log" ] && [ ! -e "$R/chain-pre.rc" ]; then log "chain-pre has not ended; nothing started"; fin 12; fi
if [ -e "$R/chain-w1.log" ] && [ ! -e "$R/chain-w1.rc" ]; then log "chain-w1 has not ended; nothing started"; fin 12; fi
ok=0
for i in $(seq 1 10); do
  if st=$(bash "$H/examples/wave4g/idle.sh"); then ok=1; break; fi
  sleep 30
done
[ "$ok" = 1 ] || { log "box $st"; fin 10; }
log "$st"
[ "$(sha256sum "$HOME/epl/bins/wave8w1/envoy-w8-A" | cut -d' ' -f1)" = 46c98673eddc4f480cfc79cf8b6cfb620b6fec97245dcc0332535d43475d3971 ] || { log "staged binary differs from its pin"; fin 14; }
[ "$(sha256sum "$HOME/epl/bin/envoy-1.40.2" | cut -d' ' -f1)" = 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc ] || { log "official binary differs from its pin"; fin 14; }
for p in 10110 9921 8092; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
[ -z "$(ss -Hlun "sport = :10110" 2>/dev/null)" ] || { log "UDP port 10110 in use (stop)"; fin 16; }
log "UDP socket buffers: rmem_default $(cat /proc/sys/net/core/rmem_default) rmem_max $(cat /proc/sys/net/core/rmem_max)"
one() {  # one CONFIG ESTIMATE_S
  if [ $(( $(els) + $2 )) -gt "$CAP" ]; then log "$1 SKIPPED by the cap ($(els) s gone, estimate $2 s, cap $CAP s)"; echo "$1" >> "$R/tail-skipped.txt"; return 0; fi
  log "udp before $1: $(udp)"
  bash "$S/run-w1.sh" tail "$1"
  log "udp after $1: $(udp)"
}
for r in 1 2 3 4 5 6 7 8; do
  if [ $(( r % 2 )) = 1 ]; then one "tail-a-r$r" 100; else one "tail-a-r$r" 220; fi
done
for r in 1 2 3 4; do one "tail-c-r$r" 170; done
python3 -I "$S/tail_check.py" "$R/tail" >> "$L" 2>&1
log "tail_check rc=$?"
fin 0
