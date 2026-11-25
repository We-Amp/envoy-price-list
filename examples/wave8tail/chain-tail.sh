#!/bin/bash
# The tail add-on after session W8-3 (W8-2's follow-up; configs from tail_make.py, rules in
# tail_check.py, fixed before the first leg). One detached chain, one login; start it with box-start.sh, only
# after the session's own chains have ended. $R/tail-go.txt lists the parts the runner released ("p1" or "p1 p2": Part 2 only when
# the scored chain did not overrun its budget).
#   Part 1  tail-p1-r1 .. r4: h3-off and h3-both-on, one leg each, order alternating, 10 s runs, QUIC statistics
#           visitor with update_period 0.05 s. The kernel's Udp line is logged before and after each.
#   Part 2  tail-c4: h3-official, h3-official-A2, h3-off, h3-reuse-on on s, 8 rounds Williams (32 legs). Started only
#           when it can end inside the cap: at most TAIL_P2_START_MAX_S (default 840 s) after this chain's start, so
#           that 32 legs (about 23 minutes) end inside the 40 minutes.
# Nothing is replaced or repeated. Exit code in $R/chain-tail.rc (0: the chain reached its end).
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave8tail
R=${RUNS:-$HOME/epl/runs/wave8w3}
export RUNS=$R
L=$R/chain-tail.log
T0=$(date +%s)
P2MAX=${TAIL_P2_START_MAX_S:-840}
export PERF=${PERF:-/usr/lib/linux-tools/6.8.0-149-generic/perf}
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
els() { echo $(( $(date +%s) - T0 )); }
fin() { log "chain end rc=$1 after $(( $(els) / 60 )) min"; echo "$1" > "$R/chain-tail.rc"; exit "$1"; }
udp() { awk '/^Udp: [0-9]/{print}' /proc/net/snmp; }
GO=$(cat "$R/tail-go.txt" 2>/dev/null)
log "chain tail start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)); released parts: ${GO:-none}; part 2 starts only before ${P2MAX} s"
for k in pre w3; do
  if [ -e "$R/chain-$k.log" ] && [ ! -e "$R/chain-$k.rc" ]; then log "chain-$k has not ended; nothing started"; fin 12; fi
done
ok=0
for i in $(seq 1 10); do
  if st=$(bash "$H/examples/wave4g/idle.sh"); then ok=1; break; fi
  sleep 30
done
[ "$ok" = 1 ] || { log "box $st"; fin 10; }
log "$st"
[ "$(sha256sum "$HOME/epl/bins/wave8w3/envoy-w8-B" | cut -d' ' -f1)" = 14aefebf3c0be38372809382f5a1d7b46229a92e1563e83ca096dbb3843d762e ] || { log "staged binary differs from its pin"; fin 14; }
[ "$(sha256sum "$HOME/epl/bin/envoy-1.40.2" | cut -d' ' -f1)" = 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc ] || { log "official binary differs from its pin"; fin 14; }
for p in 10110 9921 8092; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
[ -z "$(ss -Hlun "sport = :10110" 2>/dev/null)" ] || { log "UDP port 10110 in use (stop)"; fin 16; }
case " $GO " in *" p1 "*) ;; *) log "part 1 not released; nothing run"; fin 0 ;; esac
for r in 1 2 3 4; do
  log "udp before tail-p1-r$r: $(udp)"
  bash "$S/run-tail.sh" "tail-p1-r$r"
  log "udp after tail-p1-r$r: $(udp)"
done
log "part 1 done after $(els) s"
case " $GO " in
  *" p2 "*)
    if [ "$(els)" -gt "$P2MAX" ]; then
      log "part 2 SKIPPED by the cap: $(els) s gone (start limit $P2MAX s)"; echo skipped-by-cap > "$R/tail-p2.txt"
    else
      log "udp before tail-c4: $(udp)"
      bash "$S/run-tail.sh" tail-c4
      log "udp after tail-c4: $(udp)"
      echo ran > "$R/tail-p2.txt"
    fi ;;
  *) log "part 2 not released by the runner"; echo not-released > "$R/tail-p2.txt" ;;
esac
python3 -I "$S/tail_check.py" "$R/tail" >> "$L" 2>&1
log "tail_check rc=$?"
fin 0
