#!/bin/bash
# Wave 7 session S4 chain (one detached chain, one login; start it with box-start.sh):
#   0 idle (load and CPU only; waits up to 10 min), pins (the official Envoy and the four staged binaries by
#     sha256, client md5, origin and collector image digests), ports free, default boot state
#   1 the on-box evidence the OpenTelemetry run waits for (non-scored): ev-span-path (the unstripped twin at
#     0% sampling under a user-space profile, guard on and off), span-post.sh (reports; perf.data deleted),
#     ev-export (official and patched at 100% sampling, the collector prints every span), s4_evidence.py.
#     When it fails, s4a-otel is NOT run (the patched arms are not scored); s4b-pgo still runs.
#   2 the smokes of both runs and their state checks (s4_check.py; s4b: the profile took)
#   3 per run: check (smoke valid, evidence frozen), then the run; a run whose check fails is skipped
# No rate is changed by the chain. Exit code in $R/chain-s4.rc (0: both scored runs ended rc=0), progress in
# $R/chain-s4.log and queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave7s4
R=${RUNS:-$HOME/epl/runs/wave7s4}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-s4.log
export PERF=${PERF:-/usr/lib/linux-tools/6.8.0-149-generic/perf}
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-s4.rc"; exit "$1"; }
log "chain s4 start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)) uptime $(cut -d' ' -f1 /proc/uptime)s"
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
col=otel/opentelemetry-collector:0.120.0@sha256:1daa4312b48312dbae2d543e67b77e897dd5d9c48e7651d1416cdb417026ad06
docker image inspect "$col" >/dev/null 2>&1 || { log "collector image $col not present (nothing is pulled)"; fin 14; }
log "pins checked (five Envoy binaries by sha256, client md5, origin image digest, collector image digest)"
for p in 10110 9921 8092 4317 8888; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
cs=$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource)
if grep -q 'mitigations=' /proc/cmdline || [ "$cs" != tsc ] || ! grep -q '^Mitigation: PTI' /sys/devices/system/cpu/vulnerabilities/meltdown; then
  log "boot state is not the default (cmdline $(cat /proc/cmdline); clocksource $cs)"; fin 13
fi
log "boot state default: kernel $(uname -r), clocksource $cs, meltdown $(cat /sys/devices/system/cpu/vulnerabilities/meltdown)"
sudo -n true 2>/dev/null && log "sudo -n works (the span-path profile runs under it)" || log "sudo -n does NOT work: the span-path evidence will fail and s4a-otel will not run"

# 1. the on-box evidence (non-scored)
mkdir -p "$R/mech"
export W7_MECH_OUT=$R/mech/out-ev-span-path
bash "$S/run-s4.sh" mech ev-span-path
bash "$S/span-post.sh" "$W7_MECH_OUT" >> "$L" 2>&1
bash "$S/run-s4.sh" mech ev-export
python3 -I "$S/s4_evidence.py" "$R" --json "$R/evidence-otel.json" > "$R/evidence-otel.txt" 2>&1
OTEL=$?
cat "$R/evidence-otel.txt" >> "$L"
log "on-box evidence for the patched arms: rc=$OTEL (0 = pass; anything else: s4a-otel is not run)"
log "perf.data left under mech: $(find "$R/mech" -name '*.data' 2>/dev/null | wc -l)"

# 2. smokes
if [ "$OTEL" = 0 ]; then
  bash "$S/run-s4.sh" smoke smoke-s4a-otel
  python3 -I "$S/s4_check.py" "$R/smoke/smoke-s4a-otel" >> "$L" 2>&1
  log "s4a smoke state check rc=$?"
fi
bash "$S/run-s4.sh" smoke smoke-s4b-pgo
python3 -I "$S/s4_check.py" "$R/smoke/smoke-s4b-pgo" >> "$L" 2>&1
log "s4b smoke state check rc=$? (the tests profile took: at least 5% fewer user instructions per request)"

# 3. scored runs
bad=0
run_one() {
  local run=$1 smoke=$2
  if ! python3 -I "$S/s4_check.py" "$R/smoke/$smoke" > /dev/null 2>&1; then
    log "$run not run (its smoke state check failed: see the lines above)"; bad=1; return
  fi
  if bash "$S/run-s4.sh" queue "$run" "$smoke"; then
    last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; bad=1; }
  else
    log "$run not run (its smoke check failed)"; bad=1
  fi
}
if [ "$OTEL" = 0 ]; then
  run_one s4a-otel smoke-s4a-otel
else
  log "s4a-otel not run: the on-box evidence for the patched arms failed"; bad=1
fi
run_one s4b-pgo smoke-s4b-pgo
echo "$bad" > "$R/scored.rc"
log "scored runs done (bad=$bad): s4a-otel, s4b-pgo"
[ "$bad" = 0 ] && fin 0
fin 20
