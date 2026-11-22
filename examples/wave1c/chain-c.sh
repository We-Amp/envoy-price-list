#!/bin/bash
# The trimmed track C session as one detached chain (start it with setsid nohup, once):
#
#   chain-c.sh RUNS_DIR [EPL_ARGS...]   (EPL_ARGS go to every `epl run`, e.g. --set client.binary=...)
#
#   1. smokes: smoke-extproc, smoke-xds-small-s (one round of every arm, evidence recorded)
#   2. rate rule: if any ext_proc or ext_authz arm's busiest worker was above 0.80 of a core in the
#      smoke, the ext_proc row runs at 4,000 req/s instead of 5,200 (configs rewritten, recorded)
#   3. evidence freeze and check of both runs against their smokes; the chain stops on a failure
#   4. stage 1: extproc (6 fixed rounds); stage 2 only if stage 1 ended complete
#   5. stage 2: xds-small-s (6 fixed rounds, shape s only)
# Hard stop STOP_H hours (default 5) for the whole chain. Exit code: 0 done, 1 a gate stopped it.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
R=${1:?runs dir}
shift
ARGS=("$@")
EPL="python3 $H/bin/epl"
MAKE=$H/examples/wave1c/make.py
FEAT=$H/examples/settings-matrix/features.py
C=$H/examples/wave1c/configs
STOP_S=$(( ${STOP_H:-5} * 3600 ))
T0=$(date +%s)
mkdir -p "$R/smoke" "$R/frozen"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/chain.log"; }
left() { echo $(( STOP_S - ($(date +%s) - T0) )); }
run() {  # run NAME CONFIG OUTDIR
  local L
  L=$(left)
  [ "$L" -le 60 ] && { log "stop reached before $1"; return 124; }
  log "start $1 (${L}s left)"
  timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$2" --out "$3" --allow-short "${ARGS[@]}" >> "$R/chain.log" 2>&1
  local rc=$?
  log "end $1 rc=$rc"
  return $rc
}
log "chain start pid $$ args ${ARGS[*]} harness $(cat "$H/HARNESS_COMMIT" 2>/dev/null || git -C "$H" rev-parse --short HEAD 2>/dev/null)"
run smoke-extproc "$C/smoke-extproc.json" "$R/smoke/smoke-extproc"
run smoke-xds-small-s "$C/smoke-xds-small-s.json" "$R/smoke/smoke-xds-small-s"
BUSY=$(python3 - "$R/smoke/smoke-extproc" <<'EOF'
import json, os, sys
b = 0.0
with open(os.path.join(sys.argv[1], "legs.jsonl")) as f:
    for line in f:
        m = json.loads(line)
        if m.get("arm", "").startswith(("xp-", "authz-")):
            b = max(b, m.get("envoy_worker_max_busy") or 0.0)
print("%.4f" % b)
EOF
)
log "smoke: busiest ext_proc/ext_authz worker $BUSY of a core"
if python3 -c "import sys; sys.exit(0 if float('$BUSY') > 0.80 else 1)"; then
  echo '{"extproc_s": 4000}' > "$R/rates.json"
  python3 "$MAKE" write "$R/rates.json" >> "$R/chain.log" 2>&1 || { log "rewrite failed"; exit 1; }
  log "rate rule: ext_proc row at 4,000 req/s (configs rewritten from $R/rates.json)"
else
  log "rate rule: ext_proc row at 5,200 req/s"
fi
bad=0
for r in extproc xds-small-s; do
  if $EPL evidence-check "$C/$r.json" "$R/smoke/smoke-$r" --freeze "$R/frozen/$r.json" >> "$R/chain.log" 2>&1; then
    log "evidence $r: PASS"
  else
    log "evidence $r: FAILED"
    bad=1
  fi
done
[ "$bad" -eq 0 ] || { log "chain stopped: evidence check failed"; exit 1; }
run extproc "$R/frozen/extproc.json" "$R/extproc"
if ! why=$(python3 "$FEAT" has-floor "$R/extproc"); then
  log "chain stopped: stage 1 not complete ($why)"
  exit 1
fi
log "stage 1 complete: $why"
run xds-small-s "$R/frozen/xds-small-s.json" "$R/xds-small-s"
why=$(python3 "$FEAT" has-floor "$R/xds-small-s") && log "stage 2 complete: $why" || { log "stage 2 not complete ($why)"; exit 1; }
log "chain done"
exit 0
