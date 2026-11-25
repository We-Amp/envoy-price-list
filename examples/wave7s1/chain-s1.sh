#!/bin/bash
# Wave 7 session S1 chain (one detached chain, one login; start it with box-start.sh):
#   0 idle (load and CPU only; waits up to 10 min), pins (Envoy sha256, client md5, origin image digest),
#     ports free, default boot state (no mitigations argument, clocksource tsc)
#   1 perf selftest of the mechanism legs (a failure drops those legs only)
#   2 the two smokes; s1a: a Unix-socket arm that fails is replaced (s1_pick.py, plan rule R7); s1b: a load-gate
#     failure halves the rate once (R3)
#   3 per run: check (smoke valid, evidence frozen), then the run; a run whose check fails is skipped
#   4 after every scored run's exit code is written: the non-scored mechanism legs, then their reports
# Exit code in $R/chain-s1.rc (0: both scored runs ended rc=0), progress in $R/chain-s1.log and queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave7s1
R=${RUNS:-$HOME/epl/runs/wave7s1}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-s1.log
export PERF=${PERF:-/usr/lib/linux-tools/6.8.0-149-generic/perf}
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-s1.rc"; exit "$1"; }
log "chain s1 start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)) uptime $(cut -d' ' -f1 /proc/uptime)s"
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
nh=$(md5sum "$HOME/nighthawk-dogfood/bazel-bin/nighthawk_client" 2>/dev/null | cut -c1-8)
[ "$nh" = 310df412 ] || { log "nighthawk_client md5 ${nh:-missing}, want 310df412"; fin 14; }
img=nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11
docker image inspect "$img" >/dev/null 2>&1 || { log "origin image $img not present (nothing is pulled)"; fin 14; }
log "pins checked (envoy sha256, client md5, origin image digest)"
for p in 10110 9921 10120 9931 8092; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
cs=$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource)
if grep -q 'mitigations=' /proc/cmdline || [ "$cs" != tsc ] || ! grep -q '^Mitigation: PTI' /sys/devices/system/cpu/vulnerabilities/meltdown; then
  log "boot state is not the default (cmdline $(cat /proc/cmdline); clocksource $cs)"; fin 13
fi
log "boot state default: kernel $(uname -r), clocksource $cs, meltdown $(cat /sys/devices/system/cpu/vulnerabilities/meltdown)"

mkdir -p "$R/mech"
bash "$S/perf-selftest.sh" "$R/mech/selftest" >> "$L" 2>&1
MSYS=0; MKCG=0
if [ -e "$R/mech/selftest/sys.ok" ]; then MSYS=1; read -r W7_EAGAIN_FILTER < "$R/mech/selftest/eagain.filter"; export W7_EAGAIN_FILTER; fi
[ -e "$R/mech/selftest/kcg.ok" ] && MKCG=1
log "perf selftest: syscall legs $MSYS, call-graph legs $MKCG (1 = will run; a 0 drops those legs only; EAGAIN filter '${W7_EAGAIN_FILTER:-none}')"

bash "$S/run-s1.sh" smoke smoke-s1a-hop
A=$(python3 -I "$S/s1_pick.py" s1a "$R/smoke/smoke-s1a-hop")
log "s1a config picked from the smoke: $A"
bash "$S/run-s1.sh" smoke smoke-s1b-relay
B=s1b-relay; BS=smoke-s1b-relay; HALF=
pick=$(python3 -I "$S/s1_pick.py" s1b "$R/smoke/smoke-s1b-relay")
log "s1b smoke at 8,000 req/s: $pick"
if [ "$pick" = halve ]; then
  bash "$S/run-s1.sh" smoke smoke-s1b-relay-half
  B=s1b-relay-half; BS=smoke-s1b-relay-half; HALF=-half
  log "s1b runs at 4,000 req/s in every arm (smoke at 8,000 failed a load gate; plan rule R3)"
fi

bad=0
run_one() {
  local run=$1 smoke=$2
  if bash "$S/run-s1.sh" queue "$run" "$smoke"; then
    last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; bad=1; }
  else
    log "$run not run (its smoke check failed)"; bad=1
  fi
}
run_one "$A" smoke-s1a-hop
run_one "$B" "$BS"
echo "$bad" > "$R/scored.rc"
log "scored runs done (bad=$bad): $A, $B"

if [ "$MSYS" = 1 ]; then
  for m in mech-sys-relay$HALF mech-sys-hop; do
    export W7_MECH_OUT=$R/mech/out-$m
    bash "$S/run-s1.sh" mech "$m"
  done
fi
if [ "$MKCG" = 1 ]; then
  for m in mech-kcg-relay$HALF mech-kcg-hop; do
    export W7_MECH_OUT=$R/mech/out-$m
    bash "$S/run-s1.sh" mech "$m"
  done
  bash "$S/mech-post.sh" "$R/mech" >> "$L" 2>&1
fi
log "mechanism legs done (non-scored)"
[ "$bad" = 0 ] && fin 0
fin 20
