#!/bin/bash
# Wave 8 session W8-1, the FIRST of its two chains: every smoke and every gate leg, nothing scored. The runner
# reads its result (w1_check.py, recomputed on the orchestration side) and only then starts chain-w1.sh, which
# scores. One detached chain, one login; start it with box-start.sh pre.
#   0 the session clock ($R/t0, written by the login before this chain), idle (load and CPU only; waits up to
#     10 min), pins (the official Envoy and the staged binary by sha256, client md5, origin image digest, stream
#     origin sha256), ports free, default boot state, sudo -n
#   1 perf selftests: S2's (call-graph legs) and w1-selftest.sh (the tracepoint list of W8-1's traced legs). A
#     failed selftest is logged and the legs of that kind run anyway (they are not scored and say what happened).
#   2 per run a, b, d, c: the smoke at the planned rate, then `w1_check.py pick`: the same variant, or (rule R3,
#     one step) the variant with the failing shape at half rate, smoked once more; `fail` is final for that run.
#     A smoke that fails a rule which is not load is replaced ONCE before it counts.
#     The picked variant is written to $R/pick-<run>.txt (a name, or none).
#   3 tracepoint legs mech-sys-<variant> of a, b and d (the rider's run after its scored run, in chain-w1.sh)
#   4 call-graph legs mech-kcg-<variant of a> on b1m (official-ch8k, off-ch8k, frag-on-ch8k), their reports, and
#     the signature check; the perf.data files are deleted here, after the reports
# Exit code in $R/chain-pre.rc: 0 when every step ran (what the checks said is in the log and in pick-*.txt).
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave8w1
R=${RUNS:-$HOME/epl/runs/wave8w1}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-pre.log
export PERF=${PERF:-/usr/lib/linux-tools/6.8.0-149-generic/perf}
T0=$(cat "$R/t0" 2>/dev/null || date +%s)
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
el() { echo $(( ($(date +%s) - T0) / 60 )); }
fin() {
  n=$(find "$R" -name '*.data' 2>/dev/null | wc -l)
  [ "$n" = 0 ] || { find "$R" -name '*.data' -exec sudo -n rm -f {} + 2>/dev/null; log "perf.data files deleted at the end: $n (left: $(find "$R" -name '*.data' 2>/dev/null | wc -l))"; }
  log "chain end rc=$1, $(el) min after the session's start"; echo "$1" > "$R/chain-pre.rc"; exit "$1"
}
log "chain pre start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)) uptime $(cut -d' ' -f1 /proc/uptime)s; session clock t0 $T0 ($(el) min ago)"
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
so_want=$(cut -d' ' -f1 "$H/tools/streamorigin/SHA256SUMS")
so_got=$(sha256sum "$H/tools/streamorigin/out/epl-streamorigin-linux-amd64" 2>/dev/null | cut -d' ' -f1)
[ -n "$so_want" ] && [ "$so_got" = "$so_want" ] || { log "stream origin sha256 ${so_got:-missing}, want $so_want"; fin 14; }
log "pins checked (two Envoy binaries by sha256, client md5, origin image digest, stream origin sha256 $so_got)"
for p in 10110 9921 8092 8096 8098 8099; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
cs=$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource)
if grep -q 'mitigations=' /proc/cmdline || [ "$cs" != tsc ] || ! grep -q '^Mitigation: PTI' /sys/devices/system/cpu/vulnerabilities/meltdown; then
  log "boot state is not the default (cmdline $(cat /proc/cmdline); clocksource $cs)"; fin 13
fi
log "boot state default: kernel $(uname -r), clocksource $cs, meltdown $(cat /sys/devices/system/cpu/vulnerabilities/meltdown)"
sudo -n true 2>/dev/null || { log "sudo -n does NOT work: no traced or profiled leg can run; nothing is started"; fin 15; }

# 1. perf selftests
mkdir -p "$R/mech"
bash "$H/examples/wave7s2/perf-selftest.sh" "$R/mech/selftest" >> "$L" 2>&1
bash "$S/w1-selftest.sh" "$R/mech/selftest-w1" >> "$L" 2>&1
W7_EAGAIN_FILTER='ret==-11'
[ -s "$R/mech/selftest-w1/eagain.filter" ] && read -r W7_EAGAIN_FILTER < "$R/mech/selftest-w1/eagain.filter"
export W7_EAGAIN_FILTER
KCG=0; [ -e "$R/mech/selftest/kcg.ok" ] && KCG=1
SYS=0; [ -e "$R/mech/selftest-w1/sys.ok" ] && SYS=1
log "perf selftests: W8-1 tracepoint list $SYS, call-graph legs $KCG (1 = works; the legs run either way; EAGAIN filter '$W7_EAGAIN_FILTER')"

smoke() {  # smoke NAME: 0 pass; 3 only load failures; 1 another rule failed
  bash "$S/run-w1.sh" smoke "$1"
  python3 -I "$S/w1_check.py" smoke "$R/smoke/$1" >> "$L" 2>&1
  local rc=$?
  log "$1 state check rc=$rc (0 pass; 3 load only; 1 another rule failed)"
  return $rc
}
smoke_once_more() {  # a failure that is not load is replaced once (the first attempt is kept aside by run-w1.sh)
  smoke "$1"; local rc=$?
  if [ "$rc" = 1 ]; then log "$1 failed a rule that is not load: replaced ONCE"; smoke "$1"; rc=$?; fi
  return $rc
}
settle() {  # settle RUN: smoke, pick, one rate step
  local run=$1 pick
  smoke_once_more "smoke-$run"
  pick=$(python3 -I "$S/w1_check.py" pick "$R/smoke/smoke-$run")
  log "run $run at the planned rate: picked $pick"
  if [ "$pick" != "$run" ] && [ "$pick" != fail ]; then
    log "run $run: a load gate failed in the smoke; one rate step (rule R3): $pick"
    smoke_once_more "smoke-$pick"
    local again
    again=$(python3 -I "$S/w1_check.py" pick "$R/smoke/smoke-$pick")
    if [ "$again" != "$pick" ]; then log "run $run: the smoke of $pick does not pass either ($again): NOT healthy within the rate-step rule"; pick=fail; fi
  fi
  [ "$pick" = fail ] && pick=none
  echo "$pick" > "$R/pick-$run.txt"
  log "run $run settled: $pick ($(el) min after the session's start)"
}

# 2. smokes and rates
for run in a b d c; do settle "$run"; done

mech() {  # mech NAME check|sig|none
  export W7_MECH_OUT=$R/mech/out-$1
  bash "$S/run-w1.sh" mech "$1"
  [ "${2:-none}" = none ] && return 0
  python3 -I "$S/w1_check.py" "$2" "$R/mech" "$1" >> "$L" 2>&1
  log "$1 $2 check rc=$? (0 pass; 1 a rule failed; 2 counts or profiles missing)"
}

# 3. tracepoint legs of the patch's runs
for run in a b d; do
  v=$(cat "$R/pick-$run.txt")
  if [ "$v" = none ]; then log "run $run: no traced legs (not settled)"; else mech "mech-sys-$v" mech; fi
done
log "tracepoint legs done, $(el) min after the session's start"

# 4. the signature: call-graph legs on b1m
v=$(cat "$R/pick-a.txt")
if [ "$v" = none ]; then
  log "run a not settled: no call-graph legs, no signature"
else
  export W7_MECH_OUT=$R/mech/out-mech-kcg-$v
  bash "$S/run-w1.sh" mech "mech-kcg-$v"
  bash "$S/mech-post.sh" "$R/mech" >> "$L" 2>&1
  log "call-graph reports: $(cut -d' ' -f1 "$R/mech/post-check.txt" 2>/dev/null | sort | uniq -c | tr '\n' ' ')"
  python3 -I "$S/w1_check.py" sig "$R/mech" "mech-kcg-$v" >> "$L" 2>&1
  log "mech-kcg-$v signature check rc=$? (0 pass; 1 a rule failed; 2 a profile is missing)"
fi
log "picks: a $(cat "$R/pick-a.txt") b $(cat "$R/pick-b.txt") d $(cat "$R/pick-d.txt") c $(cat "$R/pick-c.txt")"
fin 0
