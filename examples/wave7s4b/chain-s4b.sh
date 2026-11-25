#!/bin/bash
# Wave 7 session S4b chain (one detached chain, one login; start it with box-start.sh):
#   0 idle (load and CPU only; waits up to 10 min), pins (the official Envoy and the three staged binaries by
#     sha256, client md5, origin image digest), ports free, default boot state
#   1 the smoke (one round of the four arms on both shapes) and its state check (s4b_check.py: every arm ran
#     its pinned binary, and each profiled binary runs at least 5% fewer user instructions per request than
#     the official one on at least one shape)
#   2 check (smoke valid, evidence frozen), then the one scored run; when the check fails nothing is scored
# The run happens once: nothing is repeated by the chain. No rate is changed by the chain. Exit code in
# $R/chain-s4b.rc (0: the scored run ended rc=0), progress in $R/chain-s4b.log and queue.log.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave7s4b
R=${RUNS:-$HOME/epl/runs/wave7s4b}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-s4b.log
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-s4b.rc"; exit "$1"; }
log "chain s4b start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)) uptime $(cut -d' ' -f1 /proc/uptime)s"
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
log "pins checked (four Envoy binaries by sha256, client md5, origin image digest)"
for p in 10110 9921 8092; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
cs=$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource)
if grep -q 'mitigations=' /proc/cmdline || [ "$cs" != tsc ] || ! grep -q '^Mitigation: PTI' /sys/devices/system/cpu/vulnerabilities/meltdown; then
  log "boot state is not the default (cmdline $(cat /proc/cmdline); clocksource $cs)"; fin 13
fi
log "boot state default: kernel $(uname -r), clocksource $cs, meltdown $(cat /sys/devices/system/cpu/vulnerabilities/meltdown)"

# 1. smoke
bash "$S/run-s4b.sh" smoke smoke-it-pgo
python3 -I "$S/s4b_check.py" "$R/smoke/smoke-it-pgo" >> "$L" 2>&1
log "smoke state check rc=$? (pinned binary per arm; each profiled binary at least 5% fewer user instructions per request than official on a shape)"

# 2. the one scored run
bad=0
if ! python3 -I "$S/s4b_check.py" "$R/smoke/smoke-it-pgo" > /dev/null 2>&1; then
  log "it-pgo not run (its smoke state check failed: see the lines above)"; bad=1
elif bash "$S/run-s4b.sh" queue it-pgo smoke-it-pgo; then
  last=$(grep -E "end it-pgo rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
  [ "${last:-x}" = 0 ] || { log "it-pgo failed (rc=${last:-none})"; bad=1; }
else
  log "it-pgo not run (its smoke check failed)"; bad=1
fi
echo "$bad" > "$R/scored.rc"
log "scored run done (bad=$bad): it-pgo"
[ "$bad" = 0 ] && fin 0
fin 20
