#!/bin/bash
# Wave 8 session W8-2 chain (one detached chain, one login; start it with box-start.sh):
#   0 idle (load and CPU only; waits up to 10 min), pins (the official Envoy and the staged binary by sha256,
#     client md5, origin image digest), ports free, default boot state, sudo -n
#   1 the perf selftest of the mechanism legs (S2's; the tracepoint list is the same). Without the full
#     tracepoint list (recvmmsg returning EAGAIN) NOTHING is scored: the arms' signature could not be shown.
#   Steps 2, 3 and 5 and the lower-rate smoke of step 4 are replaced ONCE when their check fails (a box-wide
#   kernel counter or the worker-share gate fails about one HTTP/3 leg in fifty for reasons that are not the
#   arm's); a second failure is final. The first attempt is kept beside the second.
#   2 smoke-s (one round of the six arms on shape s) and its state check (w2_check.py smoke: the pinned binary
#     and the three guards in every leg, no error, bytes and datagrams equal across the HTTP/3 arms). When it
#     fails NOTHING is scored and the chain ends (rc 30).
#   3 mech-sys-s: tracepoint legs of h2tls and the five HTTP/3 arms on shape s, and their signature check
#     (w2_check.py mech). THE GATE: when an arm does not show what its row assumes, the chain ends (rc 31).
#   4 smoke-shi at 6,000 req/s. A load gate failing there (rule R3): smoke-shi-half at 3,008, once. Any other
#     failure, or a failure at the lower rate: the s-hi run is NOT run (the s runs go on).
#   5 mech-sys-shi[-half] and its signature check; a failure stops the s-hi run only.
#   6 the scored runs s-1 and s-2 (one Williams square of six rounds each; never cut)
#   7 the scored s-hi run, started only up to 85 min after the chain's start (the plan's cut order: the
#     loaded shape goes first)
#   8 mech-kcg-s (call-graph legs) and their reports, started only up to 112 min after the chain's start; the
#     perf.data files are deleted here, after the reports
#   9 loss-s (the four HTTP/3 arms with Envoy's QUIC statistics on), started only up to 116 min
# The scored runs happen once: nothing scored is repeated by the chain.
# Exit code in $R/chain-w2.rc (0: both s runs ran and every scored run that was started ended rc=0),
# progress in $R/chain-w2.log and queue.log; what was run on s-hi in $R/hi.txt (shi, shi-half or none).
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave8w2
R=${RUNS:-$HOME/epl/runs/wave8w2}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-w2.log
export PERF=${PERF:-/usr/lib/linux-tools/6.8.0-149-generic/perf}
T0=$(date +%s)
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
el() { echo $(( ($(date +%s) - T0) / 60 )); }
fin() {
  n=$(find "$R" -name '*.data' 2>/dev/null | wc -l)
  [ "$n" = 0 ] || { find "$R" -name '*.data' -exec sudo -n rm -f {} + 2>/dev/null; log "perf.data files deleted at the end: $n (left: $(find "$R" -name '*.data' 2>/dev/null | wc -l))"; }
  log "chain end rc=$1 after $(el) min"; echo "$1" > "$R/chain-w2.rc"; exit "$1"
}
log "chain w2 start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)) uptime $(cut -d' ' -f1 /proc/uptime)s"
ok=0
for i in $(seq 1 20); do
  if st=$(bash "$H/examples/wave4g/idle.sh"); then ok=1; break; fi
  sleep 30
done
[ "$ok" = 1 ] || { log "box $st"; fin 10; }
log "$st"
python3 -I - "$S/bins.json" <<'PYEOF' >> "$L" 2>&1 || { log "binary pins: a binary is missing or differs"; fin 14; }
import hashlib, json, os, sys
bad = 0
for k, b in sorted(json.load(open(sys.argv[1])).items()):
    p = os.path.expanduser(b["binary"])
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for blk in iter(lambda: f.read(1 << 20), b""):
                h.update(blk)
        h = h.hexdigest()
    except OSError as e:
        print("pin %-9s MISSING %s (%s)" % (k, p, e)); bad = 1; continue
    ok = h == b["source_sha256"]
    print("pin %-9s %s %s %s" % (k, "OK" if ok else "MISMATCH", h, p)); bad |= not ok
sys.exit(bad)
PYEOF
NH=$HOME/nighthawk-dogfood/bazel-bin/nighthawk_client
nh=$(md5sum "$NH" 2>/dev/null | cut -c1-8)
[ "$nh" = 310df412 ] || { log "nighthawk_client md5 ${nh:-missing}, want 310df412"; fin 14; }
img=nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11
docker image inspect "$img" >/dev/null 2>&1 || { log "origin image $img not present (nothing is pulled)"; fin 14; }
log "pins checked (two Envoy binaries by sha256, client md5, origin image digest)"
for p in 10110 9921 8092; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
[ -z "$(ss -Hlun "sport = :10110" 2>/dev/null)" ] || { log "UDP port 10110 in use (stop)"; fin 16; }
cs=$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource)
if grep -q 'mitigations=' /proc/cmdline || [ "$cs" != tsc ] || ! grep -q '^Mitigation: PTI' /sys/devices/system/cpu/vulnerabilities/meltdown; then
  log "boot state is not the default (cmdline $(cat /proc/cmdline); clocksource $cs)"; fin 13
fi
log "boot state default: kernel $(uname -r), clocksource $cs, meltdown $(cat /sys/devices/system/cpu/vulnerabilities/meltdown)"
sudo -n true 2>/dev/null || { log "sudo -n does NOT work: the tracepoint legs cannot run; nothing is scored"; fin 15; }
log "UDP socket buffers: rmem_default $(cat /proc/sys/net/core/rmem_default) rmem_max $(cat /proc/sys/net/core/rmem_max) wmem_default $(cat /proc/sys/net/core/wmem_default); kernel Udp line at the start: $(awk '/^Udp: [0-9]/{print}' /proc/net/snmp)"

# 1. perf selftest
mkdir -p "$R/mech"
bash "$H/examples/wave7s2/perf-selftest.sh" "$R/mech/selftest" >> "$L" 2>&1
[ -e "$R/mech/selftest/sys.ok" ] || { log "perf selftest: the tracepoint leg does not work; nothing is scored"; fin 15; }
read -r W7_EAGAIN_FILTER < "$R/mech/selftest/eagain.filter"; export W7_EAGAIN_FILTER
read -r SYS_SET < "$R/mech/selftest/sys.set"
[ "$SYS_SET" = full ] || { log "perf selftest: the full tracepoint list did not parse (set '$SYS_SET'): recvmmsg returning EAGAIN cannot be counted; nothing is scored"; fin 15; }
KCG=0; [ -e "$R/mech/selftest/kcg.ok" ] && KCG=1
log "perf selftest: tracepoint legs work (EAGAIN filter '$W7_EAGAIN_FILTER', list $SYS_SET); call-graph legs: $KCG"

smoke() {  # smoke NAME: 0 pass; 3 a load gate failed; 1 another rule failed
  bash "$S/run-w2.sh" smoke "$1"
  python3 -I "$S/w2_check.py" smoke "$R/smoke/$1" >> "$L" 2>&1
  local rc=$?
  log "$1 state check rc=$rc (0 pass; 3 a load gate failed; 1 another rule failed)"
  return $rc
}
mech() {  # mech NAME [check]: one mechanism config; with `check`, its signature check
  export W7_MECH_OUT=$R/mech/out-$1
  bash "$S/run-w2.sh" mech "$1"
  [ "${2:-}" = check ] || return 0
  python3 -I "$S/w2_check.py" mech "$R/mech" "$1" >> "$L" 2>&1
  local rc=$?
  log "$1 signature check rc=$rc (0 pass; 1 a rule failed; 2 counts missing)"
  return $rc
}

once_more() {  # once_more smoke|mech NAME: the step, and on a failure the same step ONE more time (the first kept aside)
  local kind=$1 name=$2 rc
  if [ "$kind" = smoke ]; then smoke "$name"; else mech "$name" check; fi; rc=$?
  [ "$rc" = 0 ] && return 0
  log "$name failed its check (rc=$rc): replaced ONCE (the first attempt is kept beside it)"
  if [ "$kind" = mech ]; then
    mv "$R/mech/$name" "$R/mech/$name.first" 2>/dev/null; mv "$R/mech/out-$name" "$R/mech/out-$name.first" 2>/dev/null
  fi
  if [ "$kind" = smoke ]; then smoke "$name"; else mech "$name" check; fi
}

# 2. smoke on shape s
once_more smoke smoke-s || { log "STOP: the smoke-s state check failed twice; nothing is scored (see the lines above)"; echo 1 > "$R/scored.rc"; fin 30; }

# 3. the gate: every arm's syscall signature on shape s
once_more mech mech-sys-s || { log "STOP: an arm does not show what its row assumes on shape s, twice (the smoke contradicts the arm table); nothing is scored"; echo 1 > "$R/scored.rc"; fin 31; }

# 4. smoke on s-hi, with the one rate step of rule R3
HI=
smoke smoke-shi; rc=$?
if [ "$rc" = 0 ]; then
  HI=shi
elif [ "$rc" = 3 ]; then
  log "a load gate failed at 6,000 requests per second: the rate is halved once (3,008; rule R3)"
  if once_more smoke smoke-shi-half; then HI=shi-half; else log "the s-hi smoke failed at the lower rate too: the s-hi run is NOT run"; fi
else
  log "the s-hi smoke failed a rule that is not a load gate: the s-hi run is NOT run"
fi

# 5. tracepoint legs on s-hi
if [ -n "$HI" ]; then
  once_more mech "mech-sys-$HI" || { log "an arm does not show its signature on s-hi: the s-hi run is NOT run"; HI=; }
fi
echo "${HI:-none}" > "$R/hi.txt"
log "smokes and tracepoint legs done after $(el) min; s-hi run: ${HI:-none}"

# 6. scored runs on shape s
bad=0
run_one() {
  local run=$1 smoke=$2
  log "scored run $run starts $(el) min after the chain's start"
  if bash "$S/run-w2.sh" queue "$run" "$smoke"; then
    last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; bad=1; }
  else
    log "$run not run (its smoke check failed)"; bad=1
  fi
}
run_one s-1 smoke-s
run_one s-2 smoke-s

# 7. scored run on s-hi
if [ -z "$HI" ]; then
  log "s-hi: no scored run (see above)"
elif [ "$(el)" -le 85 ]; then
  run_one "$HI" "smoke-$HI"
else
  log "$HI SKIPPED by the time rule ($(el) min after the chain's start, limit 85): the loaded shape is the plan's first cut"
  echo "skipped-by-time" > "$R/hi.txt"
fi
echo "$bad" > "$R/scored.rc"
log "scored runs done (bad=$bad) after $(el) min"

# 8. call-graph legs and their reports
if [ "$KCG" = 1 ] && [ "$(el)" -le 112 ]; then
  mech mech-kcg-s
  bash "$S/mech-post.sh" "$R/mech" >> "$L" 2>&1
  log "call-graph reports: $(cat "$R/mech/post-check.txt" 2>/dev/null | cut -d' ' -f1 | sort | uniq -c | tr '\n' ' ')"
else
  log "mech-kcg-s SKIPPED (call-graph selftest $KCG; $(el) min after the chain's start, limit 112)"
fi

# 9. the QUIC statistics legs (non-scored)
if [ "$(el)" -le 116 ]; then
  bash "$S/run-w2.sh" mech loss-s
else
  log "loss-s SKIPPED by the time rule ($(el) min after the chain's start, limit 116)"
fi
log "kernel Udp line at the end: $(awk '/^Udp: [0-9]/{print}' /proc/net/snmp)"
[ "$bad" = 0 ] && fin 0
fin 20
