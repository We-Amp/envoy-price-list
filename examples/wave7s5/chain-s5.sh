#!/bin/bash
# Wave 7 session S5 chain (one detached chain, one login; start it with box-start.sh):
#   0 idle (load and CPU only; waits up to 10 min), pins (the official Envoy and the staged binary by sha256,
#     client md5, origin image digest), ports free, default boot state, sudo -n, what the box says about
#     MPTCP and socket-redirect BPF programs (plain-tcp.sh; again between the runs and at the end)
#   1 the perf selftest of the tracepoint legs (S1's). When it fails NOTHING is scored: the arms' syscall
#     signature could not be shown.
#   2 the two smokes (one round of the six arms on each shape) and their state check (s5_check.py smoke: the
#     pinned binary and both guards in every leg, no reset, lost byte or error). When it fails NOTHING is
#     scored and the chain ends (rc 30): a failure of a patched arm there would be a patch defect.
#   3 the tracepoint legs at the scored load: mech-sys-relay, its signature check (s5_check.py mech; blocking,
#     rc 31: an arm that does not show its syscall signature is not the arm it claims to be), mech-sys-http
#     (printed, not blocking)
#   4 the scored runs, each one Williams square of six rounds, alternating the shapes: relay-1, http-1,
#     relay-2, http-2. The run happens once: nothing is repeated by the chain, no rate is changed. Time rule
#     (target 2.5 h, cap 3 h; the confirmatory shape is never cut): http-2 is skipped when it would start
#     later than 115 min after the chain's start.
#   5 the loaded relay legs (non-scored, tracepoints): skipped one by one when they would start later than
#     165 min after the chain's start
# Exit code in $R/chain-s5.rc (0: every scored run that was started ended rc=0 and both relay runs ran),
# progress in $R/chain-s5.log and queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave7s5
R=${RUNS:-$HOME/epl/runs/wave7s5}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-s5.log
export PERF=${PERF:-/usr/lib/linux-tools/6.8.0-149-generic/perf}
T0=$(date +%s)
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
el() { echo $(( ($(date +%s) - T0) / 60 )); }
fin() { bash "$S/plain-tcp.sh" "end" >> "$L" 2>&1; log "perf.data under the run directory: $(find "$R" -name '*.data' 2>/dev/null | wc -l)"; log "chain end rc=$1 after $(el) min"; echo "$1" > "$R/chain-s5.rc"; exit "$1"; }
log "chain s5 start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)) uptime $(cut -d' ' -f1 /proc/uptime)s"
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
for p in 10110 9921 8092 8096; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
cs=$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource)
if grep -q 'mitigations=' /proc/cmdline || [ "$cs" != tsc ] || ! grep -q '^Mitigation: PTI' /sys/devices/system/cpu/vulnerabilities/meltdown; then
  log "boot state is not the default (cmdline $(cat /proc/cmdline); clocksource $cs)"; fin 13
fi
log "boot state default: kernel $(uname -r), clocksource $cs, meltdown $(cat /sys/devices/system/cpu/vulnerabilities/meltdown)"
sudo -n true 2>/dev/null || { log "sudo -n does NOT work: the tracepoint legs cannot run; nothing is scored"; fin 15; }
bash "$S/plain-tcp.sh" "start" >> "$L" 2>&1

# 1. perf selftest
mkdir -p "$R/mech"
bash "$H/examples/wave7s1/perf-selftest.sh" "$R/mech/selftest" >> "$L" 2>&1
[ -e "$R/mech/selftest/sys.ok" ] || { log "perf selftest: the tracepoint leg does not work; nothing is scored"; fin 15; }
read -r W7_EAGAIN_FILTER < "$R/mech/selftest/eagain.filter"; export W7_EAGAIN_FILTER
log "perf selftest: tracepoint legs work (EAGAIN filter '$W7_EAGAIN_FILTER')"

# 2. smokes and their state check
for sm in smoke-relay smoke-http; do
  bash "$S/run-s5.sh" smoke "$sm"
  python3 -I "$S/s5_check.py" smoke "$R/smoke/$sm" >> "$L" 2>&1
  rc=$?
  log "$sm state check rc=$rc (pinned binary and both guards in every leg; no reset, lost byte or error)"
  [ "$rc" = 0 ] || { log "STOP: the $sm state check failed; nothing is scored (see the STATE RULE FAILED lines above)"; echo 1 > "$R/scored.rc"; fin 30; }
done

# 3. tracepoint legs at the scored load
mech() {
  export W7_MECH_OUT=$R/mech/out-$1
  bash "$S/run-s5.sh" mech "$1"
  python3 -I "$S/s5_check.py" mech "$R/mech" "$1" >> "$L" 2>&1
  local rc=$?
  log "$1 signature check rc=$rc (0 pass; 1 a rule failed; 2 counts missing)"
  return $rc
}
mech mech-sys-relay || { log "STOP: an arm does not show its syscall signature on the relay shape; nothing is scored"; echo 1 > "$R/scored.rc"; fin 31; }
mech mech-sys-http
bash "$S/plain-tcp.sh" "before the scored runs" >> "$L" 2>&1
log "smokes and tracepoint legs done after $(el) min"

# 4. scored runs
bad=0
run_one() {
  local run=$1 smoke=$2
  log "scored run $run starts $(el) min after the chain's start"
  if bash "$S/run-s5.sh" queue "$run" "$smoke"; then
    last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; bad=1; }
  else
    log "$run not run (its smoke check failed)"; bad=1
  fi
  bash "$S/plain-tcp.sh" "after $run" >> "$L" 2>&1
}
run_one relay-1 smoke-relay
run_one http-1 smoke-http
run_one relay-2 smoke-relay
if [ "$(el)" -le 115 ]; then
  run_one http-2 smoke-http
else
  log "http-2 SKIPPED by the time rule ($(el) min after the chain's start, limit 115): the HTTP shape keeps 6 rounds"
fi
echo "$bad" > "$R/scored.rc"
log "scored runs done (bad=$bad) after $(el) min"

# 5. loaded relay legs (non-scored)
for m in mech-load-p64-16k mech-load-h2-16k mech-load-p64-24k mech-load-h2-32k mech-load-p64-32k mech-load-h2-48k; do
  if [ "$(el)" -le 165 ]; then
    mech "$m"
  else
    log "$m SKIPPED by the time rule ($(el) min after the chain's start, limit 165)"
  fi
done
log "loaded legs done (non-scored) after $(el) min"
[ "$bad" = 0 ] && fin 0
fin 20
