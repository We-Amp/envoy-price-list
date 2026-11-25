#!/bin/bash
# Wave 7 session S2 chain (one detached chain, one login; start it with box-start.sh):
#   0 idle (load and CPU only; waits up to 10 min), pins (Envoy sha256, client md5, origin image digest,
#     stream-origin sha256), the client lists http3, ports free, default boot state
#   1 perf selftest of the mechanism legs, then a smoke of the whole mechanism pipeline on two non-scored
#     legs of each kind (wrapper, reports, folded stacks, post-check), before any scored leg
#   2 the smokes; s2a and s2b: a load-gate or origin-headroom failure halves that shape's rate once (R3,
#     s2_pick.py) and the halved config is smoked again; the origin-headroom evidence is logged
#   3 per run: check (smoke valid, evidence frozen), then the run; a run whose check fails is skipped
#   4 after every scored run's exit code is written: the non-scored mechanism legs, then their reports
# The mechanism legs run whatever the selftest said (a leg kind whose selftest failed is still tried and
# its output says what happened): they are not scored, and a dropped leg cost S1 a second chain.
# Exit code in $R/chain-s2.rc (0: the four scored runs ended rc=0), progress in $R/chain-s2.log and queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave7s2
R=${RUNS:-$HOME/epl/runs/wave7s2}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-s2.log
export PERF=${PERF:-/usr/lib/linux-tools/6.8.0-149-generic/perf}
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-s2.rc"; exit "$1"; }
log "chain s2 start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)) uptime $(cut -d' ' -f1 /proc/uptime)s"
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
so_want=$(cut -d' ' -f1 "$H/tools/streamorigin/SHA256SUMS")
so_got=$(sha256sum "$H/tools/streamorigin/out/epl-streamorigin-linux-amd64" 2>/dev/null | cut -d' ' -f1)
[ -n "$so_want" ] && [ "$so_got" = "$so_want" ] || { log "stream origin sha256 ${so_got:-missing}, want $so_want"; fin 14; }
log "pins checked (envoy sha256, client md5, origin image digest, stream origin sha256 $so_got)"
if ! "$NH" --help 2>/dev/null | grep -q 'http3'; then log "client does not list http3 (stop)"; fin 15; fi
for p in 10110 9921 8092 8098 8099; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
[ -z "$(ss -Hlun 'sport = :10110' 2>/dev/null)" ] || { log "UDP port 10110 in use (stop)"; fin 16; }
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
  bash "$S/run-s2.sh" mech "$1"
}
# the mechanism pipeline on smoke legs, before any scored leg (wrappers, reports, folded stacks, tables)
mech_run smoke-mech-sys
mech_run smoke-mech-kcg
bash "$S/mech-post.sh" "$R/mech" >> "$L" 2>&1
python3 -I "$S/mech_table.py" "$R/mech" --check >> "$L" 2>&1
log "mechanism pipeline smoke: mech_table --check rc=$? (post-check: $(tr '\n' ';' < "$R/mech/post-check.txt" 2>/dev/null | cut -c1-400))"

bash "$S/run-s2.sh" smoke smoke-s2a-chunked
A=$(python3 -I "$S/s2_pick.py" s2a "$R/smoke/smoke-s2a-chunked")
log "s2a smoke at 4,000 and 800 req/s: picked $A"
python3 -I "$S/s2_pick.py" headroom "$R/smoke/smoke-s2a-chunked" >> "$L" 2>&1
AS=smoke-s2a-chunked
if [ "$A" != s2a-chunked ] && [ "$A" != fail ]; then
  AS=smoke-$A
  bash "$S/run-s2.sh" smoke "$AS"
  log "s2a runs as $A (a shape's smoke at the full rate failed a load gate or the origin-headroom evidence; plan rule R3); headroom of the halved smoke:"
  python3 -I "$S/s2_pick.py" headroom "$R/smoke/$AS" >> "$L" 2>&1
fi
[ "$A" = fail ] && A=s2a-chunked   # the run's own check then fails and reports why
MSFX_A=${A#s2a-chunked}

bash "$S/run-s2.sh" smoke smoke-s2b-stream
B=$(python3 -I "$S/s2_pick.py" s2b "$R/smoke/smoke-s2b-stream")
log "s2b smoke at 2,080 and 208 req/s: picked $B"
python3 -I "$S/s2_pick.py" headroom "$R/smoke/smoke-s2b-stream" >> "$L" 2>&1
BS=smoke-s2b-stream
if [ "$B" = s2b-stream-half ]; then
  BS=smoke-s2b-stream-half
  bash "$S/run-s2.sh" smoke "$BS"
  log "s2b runs at 960 and 96 req/s (plan rule R3); headroom of the halved smoke:"
  python3 -I "$S/s2_pick.py" headroom "$R/smoke/$BS" >> "$L" 2>&1
fi
[ "$B" = fail ] && B=s2b-stream
MSFX_B=${B#s2b-stream}

bash "$S/run-s2.sh" smoke smoke-s2c-buf
bash "$S/run-s2.sh" smoke smoke-s2d-h3

bad=0
run_one() {
  local run=$1 smoke=$2
  if bash "$S/run-s2.sh" queue "$run" "$smoke"; then
    last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; bad=1; }
  else
    log "$run not run (its smoke check failed)"; bad=1
  fi
}
run_one "$A" "$AS"
run_one "$B" "$BS"
run_one s2c-buf smoke-s2c-buf
run_one s2d-h3 smoke-s2d-h3
echo "$bad" > "$R/scored.rc"
log "scored runs done (bad=$bad): $A, $B, s2c-buf, s2d-h3"

for m in "mech-sys-chunked$MSFX_A" "mech-sys-stream$MSFX_B" mech-sys-grpc mech-sys-buf mech-sys-h3 \
         "mech-kcg-chunked$MSFX_A" "mech-kcg-stream$MSFX_B" mech-kcg-h3; do
  mech_run "$m"
done
bash "$S/mech-post.sh" "$R/mech" >> "$L" 2>&1
log "mechanism legs done (non-scored); post-check: $(grep -c '^OK' "$R/mech/post-check.txt" 2>/dev/null) OK, $(grep -c '^BAD' "$R/mech/post-check.txt" 2>/dev/null) BAD"
[ "$bad" = 0 ] && fin 0
fin 20
