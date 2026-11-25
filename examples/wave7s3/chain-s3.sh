#!/bin/bash
# Wave 7 session S3 chain (one detached chain, one login; start it with box-start.sh):
#   0 idle (load and CPU only; waits up to 10 min), pins (Envoy sha256, client md5, origin image digest,
#     collector image digest), ports free, default boot state
#   1 perf selftest of the mechanism legs, then a smoke of the whole mechanism pipeline on two non-scored
#     legs of each kind (wrapper, reports, folded stacks, post-check, table), before any scored leg
#   2 the smokes of both runs; s3_check.py logs what the stack's state rests on (statsd datagrams per request,
#     stats per arm, spans, log lines)
#   3 per run: check (smoke valid, evidence frozen), then the run; a run whose check fails is skipped
#   4 after every scored run's exit code is written: the non-scored mechanism legs, then their reports
# No rate is changed by the chain: sx, s and fh run at the published rates of s and fh.
# Exit code in $R/chain-s3.rc (0: both scored runs ended rc=0), progress in $R/chain-s3.log and queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave7s3
R=${RUNS:-$HOME/epl/runs/wave7s3}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-s3.log
export PERF=${PERF:-/usr/lib/linux-tools/6.8.0-149-generic/perf}
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-s3.rc"; exit "$1"; }
log "chain s3 start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)) uptime $(cut -d' ' -f1 /proc/uptime)s"
ok=0
for i in $(seq 1 20); do
  if st=$(bash "$H/examples/wave4g/idle.sh"); then ok=1; break; fi
  sleep 30
done
[ "$ok" = 1 ] || { log "box $st"; fin 10; }
log "$st"
want=1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc
got=$(sha256sum "$HOME/epl/bin/envoy-1.40.2" 2>/dev/null | cut -d' ' -f1)
[ "$got" = "$want" ] || { log "envoy-1.40.2 sha256 ${got:-missing}, want $want"; fin 14; }
NH=$HOME/nighthawk-dogfood/bazel-bin/nighthawk_client
nh=$(md5sum "$NH" 2>/dev/null | cut -c1-8)
[ "$nh" = 310df412 ] || { log "nighthawk_client md5 ${nh:-missing}, want 310df412"; fin 14; }
img=nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11
docker image inspect "$img" >/dev/null 2>&1 || { log "origin image $img not present (nothing is pulled)"; fin 14; }
col=otel/opentelemetry-collector:0.120.0@sha256:1daa4312b48312dbae2d543e67b77e897dd5d9c48e7651d1416cdb417026ad06
docker image inspect "$col" >/dev/null 2>&1 || { log "collector image $col not present (nothing is pulled)"; fin 14; }
log "pins checked (envoy sha256, client md5, origin image digest, collector image digest)"
for p in 10110 9921 8092 4317 8888; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
[ -z "$(ss -Hlun 'sport = :8125' 2>/dev/null)" ] || { log "UDP port 8125 in use (stop)"; fin 16; }
cs=$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource)
if grep -q 'mitigations=' /proc/cmdline || [ "$cs" != tsc ] || ! grep -q '^Mitigation: PTI' /sys/devices/system/cpu/vulnerabilities/meltdown; then
  log "boot state is not the default (cmdline $(cat /proc/cmdline); clocksource $cs)"; fin 13
fi
log "boot state default: kernel $(uname -r), clocksource $cs, meltdown $(cat /sys/devices/system/cpu/vulnerabilities/meltdown)"
log "udp rmem_max $(cat /proc/sys/net/core/rmem_max) wmem_max $(cat /proc/sys/net/core/wmem_max) (read only)"

mkdir -p "$R/mech"
bash "$S/perf-selftest.sh" "$R/mech/selftest" >> "$L" 2>&1
MSYS=0; MKCG=0
[ -e "$R/mech/selftest/sys.ok" ] && MSYS=1
[ -e "$R/mech/selftest/kcg.ok" ] && MKCG=1
W7_EAGAIN_FILTER='ret==-11'; W7_SYS_SET=s1
[ -s "$R/mech/selftest/eagain.filter" ] && read -r W7_EAGAIN_FILTER < "$R/mech/selftest/eagain.filter"
[ -s "$R/mech/selftest/sys.set" ] && read -r W7_SYS_SET < "$R/mech/selftest/sys.set"
export W7_EAGAIN_FILTER W7_SYS_SET
log "perf selftest: syscall legs $MSYS, call-graph legs $MKCG (1 = works; the legs run either way; EAGAIN filter '$W7_EAGAIN_FILTER', tracepoint list $W7_SYS_SET)"

mech_run() {  # mech_run CONFIG: one non-scored config under its wrapper
  export W7_MECH_OUT=$R/mech/out-$1
  bash "$S/run-s3.sh" mech "$1"
}
# the mechanism pipeline on smoke legs, before any scored leg (wrappers, reports, folded stacks, tables)
mech_run smoke-mech-sys
mech_run smoke-mech-kcg
bash "$S/mech-post.sh" "$R/mech" >> "$L" 2>&1
python3 -I "$S/mech_table.py" "$R/mech" --check >> "$L" 2>&1
log "mechanism pipeline smoke: mech_table --check rc=$? (post-check: $(tr '\n' ';' < "$R/mech/post-check.txt" 2>/dev/null | cut -c1-400))"

bash "$S/run-s3.sh" smoke smoke-s3a-stack
python3 -I "$S/s3_check.py" "$R/smoke/smoke-s3a-stack" >> "$L" 2>&1
log "s3a smoke state check rc=$? (statsd datagrams per request in the band, stats per arm under 2,000)"
bash "$S/run-s3.sh" smoke smoke-s3b-chain
python3 -I "$S/s3_check.py" "$R/smoke/smoke-s3b-chain" >> "$L" 2>&1
log "s3b smoke state check rc=$?"

bad=0
run_one() {
  local run=$1 smoke=$2
  if ! python3 -I "$S/s3_check.py" "$R/smoke/$smoke" > /dev/null 2>&1; then
    log "$run not run (its smoke state check failed: see the lines above)"; bad=1; return
  fi
  if bash "$S/run-s3.sh" queue "$run" "$smoke"; then
    last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; bad=1; }
  else
    log "$run not run (its smoke check failed)"; bad=1
  fi
}
run_one s3a-stack smoke-s3a-stack
run_one s3b-chain smoke-s3b-chain
echo "$bad" > "$R/scored.rc"
log "scored runs done (bad=$bad): s3a-stack, s3b-chain"

for m in mech-sys-stack mech-kcg-stack mech-kcg-chain; do
  mech_run "$m"
done
bash "$S/mech-post.sh" "$R/mech" >> "$L" 2>&1
log "mechanism legs done (non-scored); post-check: $(grep -c '^OK' "$R/mech/post-check.txt" 2>/dev/null) OK, $(grep -c '^BAD' "$R/mech/post-check.txt" 2>/dev/null) BAD"
[ "$bad" = 0 ] && fin 0
fin 20
