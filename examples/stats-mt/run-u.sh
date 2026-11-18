#!/bin/bash
# The multi-threaded stats study on one machine (configs from make.py, box from boxes/$BOX.json).
#
#   run-u.sh calibrate [EPL_ARGS...]   step 0: base at the 1-worker rung and at the top rung, per-worker
#                                     rates CAL_R (default 800,1000,1300,1600,2000): busy share and
#                                     client headroom; r* is then written into RATES_JSON by hand
#   run-u.sh smoke [EPL_ARGS...]       one round of base, stats-reject and base-A2 at every rung
#   run-u.sh check                     the configs calibrated, the evidence checked against the smoke
#   run-u.sh queue [EPL_ARGS...]       run U, then the HITM evidence legs (boxes that list hitm_events)
#   run-u.sh micro-smoke [MICRO_ARGS...] the microbenchmark pre-flight (micro.py smoke; exits 1 loudly)
#   run-u.sh micro [MICRO_ARGS...]     the microbenchmarks (micro.py run), after a passing smoke
#
# Before check and queue: RATES_JSON={"<box>": {"r_star": .., "k": ..}}; the configs are rewritten
# from it (make.py --rates). Hard stop STOP_S (default 3 h 15 min) after the queue starts, through
# `timeout --foreground` (the harness process only). Runs go to $RUNS/<box> (default
# ~/epl/runs/stats-mt/<box>), progress to queue.log there.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/stats-mt
EPL="python3 $H/bin/epl"
BOX=${BOX:-bench-x86_64}
C=$S/$BOX
R=${RUNS:-$HOME/epl/runs/stats-mt}/$BOX
STOP_S=${STOP_S:-11700}
CAL_R=${CAL_R:-800,1000,1300,1600,2000}
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/queue.log"; }

rewrite() {
  if [ -n "${RATES_JSON:-}" ]; then
    python3 "$S/make.py" --box "$S/boxes/$BOX.json" --rates "$RATES_JSON" >> "$R/queue.log" 2>&1 \
      || { log "make.py failed"; exit 1; }
  fi
}

check() {
  local bad=0
  if grep -q '"uncalibrated": true' "$C/u.json"; then
    log "u.json is uncalibrated: set RATES_JSON from step 0"
    bad=1
  fi
  log "evidence-check u against smoke-u"
  if ! $EPL evidence-check "$C/u.json" "$R/smoke-u" >> "$R/queue.log" 2>&1; then
    log "evidence-check u FAILED (details in queue.log)"
    bad=1
  fi
  return $bad
}

mode=${1:-}
shift || true
case "$mode" in
  calibrate)
    log "calibrate start box $BOX harness $(cat "$H/VERSION" 2>/dev/null)"
    first=$(python3 -c "import json;print(json.load(open('$S/boxes/$BOX.json'))['rungs'][0]['name'])")
    top=$(python3 -c "import json;r=json.load(open('$S/boxes/$BOX.json'))['rungs'];print(max(r,key=lambda x:x['workers'])['name'])")
    ntop=$(python3 -c "import json;r=json.load(open('$S/boxes/$BOX.json'))['rungs'];print(max(x['workers'] for x in r))")
    $EPL calibrate "$C/u.json" --arm base --shape "mt-$first" --rps "$CAL_R" --out "$R/cal-$first" "$@" \
      >> "$R/queue.log" 2>&1
    log "end calibrate $first rc=$?"
    top_rps=$(python3 -c "print(','.join(str(int(x)*$ntop) for x in '$CAL_R'.split(',')))")
    $EPL calibrate "$C/u.json" --arm base --shape "mt-$top" --rps "$top_rps" --out "$R/cal-$top" "$@" \
      >> "$R/queue.log" 2>&1
    log "end calibrate $top rc=$?; pick r* (30% busy on base, or the top rung's 25% headroom limit) into RATES_JSON"
    ;;
  smoke)
    rewrite
    log "smoke start box $BOX"
    $EPL run "$C/smoke-u.json" --out "$R/smoke-u" --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end smoke rc=$?"
    check
    log "smoke done rc=$?"
    ;;
  check)
    rewrite
    check
    exit $?
    ;;
  queue)
    rewrite
    check || { log "queue not started (calibration or evidence; no override)"; exit 1; }
    T0=$(date +%s)
    left() { echo $(( STOP_S - ($(date +%s) - T0) )); }
    for run in u u-hitm; do
      [ -f "$C/$run.json" ] || continue
      L=$(left)
      if [ "$L" -le 60 ]; then
        log "skip $run: session stop reached"
        continue
      fi
      log "start $run (${L}s left)"
      timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$C/$run.json" --out "$R/$run" \
        --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end $run rc=$?"
    done
    log "queue done; tables: python3 $S/u_table.py $R/u --hitm $R/u-hitm > $R/u.md"
    ;;
  micro-smoke)
    log "micro smoke start box $BOX"
    python3 "$S/micro.py" smoke "$C/micro.json" "$R/micro-smoke-$(date -u +%Y%m%dT%H%M%SZ)" "$@" 2>&1 | tee -a "$R/queue.log"
    rc=${PIPESTATUS[0]}
    log "micro smoke rc=$rc"
    exit "$rc"
    ;;
  micro)
    log "micro start box $BOX"
    python3 "$S/micro.py" run "$C/micro.json" "$R/micro" "$@" >> "$R/queue.log" 2>&1
    log "micro done rc=$?; table: python3 $S/micro.py table $R/micro > $R/micro.md"
    ;;
  *)
    sed -n '2,20p' "$0"
    exit 2
    ;;
esac
