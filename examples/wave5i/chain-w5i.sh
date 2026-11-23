#!/bin/bash
# Wave 5 track I session chain (from wave 2) (one detached chain, one login). Two kinds of session, chosen by the first argument:
#   chain-w2.sh prof   0 idle check, sha256 of the binaries   1 profiling legs (run-w5i.sh prof)
#   chain-w2.sh ab     0 idle check, sha256   1 smoke of $W2_RUN (w2 or w2-nobolt) and check
#                      2 the run (run-w5i.sh queue)
# Exit code in $R/chain-<kind>.rc, progress in $R/chain-<kind>.log (and run-w5i.sh's queue.log).
set -u
KIND=${1:?prof or ab}
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave5i
R=${RUNS:-$HOME/epl/runs/wave5i}
export RUNS=$R
mkdir -p "$R"
L=$R/chain-$KIND.log
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() {
  log "chain end rc=$1"; echo "$1" > "$R/chain-$KIND.rc"
  # a finished A/B chain powers the VM off 20 min later unless ~/w5i/KEEP exists (a cloud VM must not idle)
  if [ "$KIND" = ab ] && [ ! -e "$HOME/w5i/KEEP" ]; then log "self-shutdown in 20 min"; sudo shutdown -h +20 >/dev/null 2>&1; fi
  exit "$1"
}
log "chain $KIND start pid $$ harness $H ($(git -C "$H" rev-parse --short HEAD 2>/dev/null || cat "$H/HARNESS_COMMIT" 2>/dev/null))"
# (the login shell that started this chain names it, so lines naming chain-w2.sh are not other work)
busy=$(ps -eo pid,args | grep -E '[b]in/epl|[r]un-session\.sh|[r]un-u\.sh|[r]un-b\.sh|[r]un-w2\.sh|[e]nvoy-static|[e]nvoy-1\.|[e]nvoy-(opt|order|pgolto)|[n]ighthawk_client' | grep -v 'chain-w5i\.sh')
l1=$(cut -d' ' -f1 /proc/loadavg)
if [ -n "$busy" ] || ! python3 -c "import sys;sys.exit(0 if float('$l1') < 0.5 else 1)"; then
  log "box not idle (load $l1): $busy"; fin 10
fi
log "idle: load $l1"
python3 - "$S/bins.json" <<'EOF' 2>&1 | tee -a "$L"
import hashlib, json, os, sys
bad = 0
for k, b in json.load(open(sys.argv[1])).items():
    p = os.path.expanduser(b["binary"])
    if "PENDING" in b["source_sha256"]:
        print("%-14s PENDING (not used)" % k)
        continue
    try:
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    except OSError as e:
        print("%-14s MISSING %s (%s)" % (k, p, e)); bad = 1; continue
    ok = h == b["source_sha256"]
    print("%-14s %s %s" % (k, "OK" if ok else "MISMATCH " + h, p)); bad |= not ok
sys.exit(bad)
EOF
[ "${PIPESTATUS[0]}" -eq 0 ] || { log "binary pins: a binary is missing or differs (the configs fail closed on it too)"; [ "$KIND" = ab ] && fin 14; }
case "$KIND" in
  prof)
    bash "$S/run-w5i.sh" prof
    runs=${PROF_RUNS:-fp-w5i}
    for run in $runs; do grep -q "end prof $run rc=0" "$R/queue.log" || { log "prof $run did not end rc=0"; fin 20; }; done
    fin 0
    ;;
  ab)
    bash "$S/run-w5i.sh" smoke || true
    bash "$S/run-w5i.sh" check || { log "smoke check ${W2_RUN:-w5i} FAILED: stop"; fin 12; }
    log "smoke passed; start ${W2_RUN:-w5i}"
    bash "$S/run-w5i.sh" queue
    last=$(grep -E "end ${W2_RUN:-w5i} rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "${W2_RUN:-w5i} failed (rc=${last:-none})"; fin 20; }
    fin 0
    ;;
  *) fin 2 ;;
esac
