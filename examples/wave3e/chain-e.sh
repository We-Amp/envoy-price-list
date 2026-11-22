#!/bin/bash
# Wave 3 track E session chain (one detached chain, one login):
#   0 idle check, sha256 of the Envoy binary, md5 of the client, a read-only record of the kernel limits
#   1 e-plain: smoke, check, run      2 e-tls: smoke, check, run
# A failed smoke or evidence check skips that run (rc 12) and the chain goes on to the next; a run
# that ends with a non-zero rc (abort, invalid-leg streak, stop) ends the chain (rc 20). An A/A
# failure is read afterwards from results.json and invalidates that run only.
# E_RUNS="e-tls" runs one only. E_HRR=1 first runs hrr_check.py (about 30 s, idle box, own processes only):
# the direct HelloRetryRequest check with the runs' Nighthawk; its result is logged and never stops the chain. Exit code in $R/chain-e.rc, progress in $R/chain-e.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave3e
R=${RUNS:-$HOME/epl/runs/wave3e}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-e.log
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-e.rc"; exit "$1"; }
log "chain e start pid $$ harness $H ($(git -C "$H" rev-parse --short HEAD 2>/dev/null || cat "$H/HARNESS_COMMIT" 2>/dev/null))"
busy=$(ps -eo pid,args | grep -E '[b]in/epl|[r]un-session\.sh|[r]un-w2\.sh|[r]un-e\.sh|[e]nvoy-static|[e]nvoy-1\.|[n]ighthawk_client' | grep -v 'chain-e\.sh')
l1=$(cut -d' ' -f1 /proc/loadavg)
if [ -n "$busy" ] || ! python3 -c "import sys;sys.exit(0 if float('$l1') < 0.5 else 1)"; then
  log "box not idle (load $l1): $busy"; fin 10
fi
log "idle: load $l1"
want=1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc
got=$(sha256sum "$HOME/epl/bin/envoy-1.40.2" 2>/dev/null | cut -d' ' -f1)
[ "$got" = "$want" ] || { log "envoy-1.40.2 sha256 ${got:-missing}, want $want"; fin 14; }
nh=$(md5sum "$HOME/nighthawk-dogfood/bazel-bin/nighthawk_client" 2>/dev/null | cut -c1-8)
[ "$nh" = 310df412 ] || { log "nighthawk_client md5 ${nh:-missing}, want 310df412"; fin 14; }
log "pins: envoy OK, client OK"
for k in net.ipv4.tcp_tw_reuse net.ipv4.ip_local_port_range net.ipv4.tcp_max_tw_buckets net.ipv4.tcp_timestamps \
         net.core.somaxconn net.ipv4.tcp_max_syn_backlog net.netfilter.nf_conntrack_max \
         net.netfilter.nf_conntrack_count net.netfilter.nf_conntrack_tcp_timeout_time_wait; do
  log "sysctl $k = $(sysctl -n $k 2>/dev/null | tr '\t' ' ')"
done
log "sockstat $(grep '^TCP:' /proc/net/sockstat)"
rc=0
if [ "${E_HRR:-0}" = 1 ]; then
  log "hrr check start"
  python3 -I "$S/hrr_check.py" --envoy "$HOME/epl/bin/envoy-1.40.2" \
    --nighthawk "$HOME/nighthawk-dogfood/bazel-bin/nighthawk_client" --out "$R/hrr" >> "$L" 2>&1
  log "hrr check rc=$?"
fi
for run in ${E_RUNS:-e-plain e-tls}; do
  export E_RUN=$run
  bash "$S/run-e.sh" smoke || true
  if ! bash "$S/run-e.sh" check; then log "smoke check $run FAILED: $run not run"; rc=12; continue; fi
  log "smoke passed; start $run"
  bash "$S/run-e.sh" queue
  last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
  [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none}): stop"; fin 20; }
done
fin $rc
