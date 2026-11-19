#!/bin/bash
# The multi-threaded stats study on one machine (configs from make.py, box from boxes/$BOX.json).
#
#   run-u.sh calibrate [EPL_ARGS...]   step 0: base at the 1-worker rung and at the top rung, per-worker
#                                     rates CAL_R (default 800,1000,1300,1600,2000): busy share and
#                                     client headroom; r* is then written into RATES_JSON by hand
#   run-u.sh smoke [EPL_ARGS...]       one round of base, stats-reject and base-A2 at every rung
#   run-u.sh check                     the configs calibrated, the evidence checked against the smoke
#   run-u.sh queue [EPL_ARGS...]       run U, then the HITM evidence legs (boxes that list hitm_events)
#   run-u.sh codegen-smoke [EPL_ARGS...] (boxes with a codegen section) the atomics check of both
#                                     binaries, then one round at 4w/12w; when only 12w legs are
#                                     invalid, one round at 4w/8w; writes codegen.choice
#   run-u.sh codegen [EPL_ARGS...]     the codegen run with the passing smoke's rungs (refuses
#                                     without one; evidence checked against it)
#   run-u.sh hi-calibrate [EPL_ARGS...] (boxes with a u_hi section) run U at high load, step 0: base
#                                     at 14w-one and 28w over the box's calibrate_rates_per_worker;
#                                     r* (the target worker busy, or the highest rate the client
#                                     headroom allows at 28w) goes into RATES_JSON as "<box>-hi"
#   run-u.sh hi-smoke [EPL_ARGS...]    one round of u-hi, then hi-check (calibration, evidence)
#   run-u.sh hi-queue [EPL_ARGS...]    hi-check, then u-hi within HI_STOP_S (default 2 h 30 min)
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

hi_check() {
  local bad=0
  if grep -q '"uncalibrated": true' "$C/u-hi.json"; then
    log "u-hi.json is uncalibrated: set RATES_JSON (\"$BOX-hi\") from hi-calibrate"
    bad=1
  fi
  log "evidence-check u-hi against smoke-u-hi"
  if ! $EPL evidence-check "$C/u-hi.json" "$R/smoke-u-hi" >> "$R/queue.log" 2>&1; then
    log "evidence-check u-hi FAILED (details in queue.log)"
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
  hi-calibrate)
    log "u-hi calibrate start box $BOX harness $(cat "$H/VERSION" 2>/dev/null)"
    for sh in 14w-one 28w; do
      n=$(python3 -c "import json;print([r for r in json.load(open('$S/boxes/$BOX.json'))['rungs'] if r['name']=='$sh'][0]['workers'])")
      rps=$(python3 -c "import json;print(','.join(str(r*$n) for r in json.load(open('$S/boxes/$BOX.json'))['u_hi']['calibrate_rates_per_worker']))")
      $EPL calibrate "$C/cal-u-hi.json" --arm base --shape "mt-$sh" --rps "$rps" --out "$R/cal-hi-$sh" "$@" \
        >> "$R/queue.log" 2>&1
      log "end u-hi calibrate $sh rc=$?"
    done
    log "pick r* (worker busy 60-70% at both rungs with client headroom >= 25% at 28w; else the highest rate the headroom allows) into RATES_JSON as \"$BOX-hi\""
    ;;
  hi-smoke)
    rewrite
    log "u-hi smoke start box $BOX"
    rm -rf "$R/smoke-u-hi"
    $EPL run "$C/smoke-u-hi.json" --out "$R/smoke-u-hi" --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end u-hi smoke rc=$?"
    hi_check
    log "u-hi smoke done rc=$?"
    ;;
  hi-check)
    rewrite
    hi_check
    exit $?
    ;;
  hi-queue)
    rewrite
    hi_check || { log "u-hi not started (calibration or evidence; no override)"; exit 1; }
    L=${HI_STOP_S:-9000}
    log "start u-hi (${L}s stop)"
    timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$C/u-hi.json" --out "$R/u-hi" \
      --allow-short "$@" >> "$R/queue.log" 2>&1
    log "end u-hi rc=$?; tables: python3 $S/u_table.py $R/u-hi > $R/u-hi.md"
    ;;
  codegen-smoke)
    # 1. the premise from the binaries (fail closed); 2. the 12-worker smoke; 3. the 8-worker
    # fallback smoke when only top-rung legs were invalid; the choice is written for `codegen`
    rm -f "$R/codegen.choice"
    log "codegen atomics check box $BOX"
    python3 "$S/codegen_check.py" atomics "$C/codegen.json" "$R/codegen-atomics.json" 2>&1 | tee -a "$R/queue.log"
    [ "${PIPESTATUS[0]}" -eq 0 ] || { log "codegen atomics check FAILED; no smoke"; exit 1; }
    for CG in "" "-8w"; do
      log "codegen smoke$CG start box $BOX"
      rm -rf "$R/smoke-codegen$CG"
      $EPL run "$C/smoke-codegen$CG.json" --out "$R/smoke-codegen$CG" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end codegen smoke$CG rc=$?"
      python3 "$S/codegen_check.py" smoke "$C/smoke-codegen$CG.json" "$R/smoke-codegen$CG" \
        --json "$R/smoke-codegen$CG.check.json" 2>&1 | tee -a "$R/queue.log"
      rc=${PIPESTATUS[0]}
      if [ "$rc" -eq 0 ]; then
        echo "$CG" > "$R/codegen.choice"
        log "codegen smoke$CG passed; codegen will run codegen$CG.json"
        exit 0
      fi
      if [ "$rc" -ne 2 ] || [ -n "$CG" ]; then
        log "codegen smoke$CG FAILED (rc=$rc); no fallback"
        exit 1
      fi
      log "codegen smoke: only 12-worker legs invalid; trying the 8-worker fallback"
    done
    exit 1
    ;;
  codegen)
    [ -f "$R/codegen.choice" ] || { log "codegen: no passing smoke (run codegen-smoke first); not started"; exit 1; }
    CG=$(cat "$R/codegen.choice")
    python3 "$S/codegen_check.py" smoke "$C/smoke-codegen$CG.json" "$R/smoke-codegen$CG" >> "$R/queue.log" 2>&1 \
      || { log "codegen: smoke-codegen$CG does not pass its check; not started"; exit 1; }
    python3 -c "import json,sys;sys.exit(0 if json.load(open('$R/codegen-atomics.json'))['ok'] else 1)" \
      || { log "codegen: atomics check missing or failed; not started"; exit 1; }
    log "evidence-check codegen$CG against smoke-codegen$CG"
    if ! $EPL evidence-check "$C/codegen$CG.json" "$R/smoke-codegen$CG" >> "$R/queue.log" 2>&1; then
      log "evidence-check codegen$CG FAILED (details in queue.log); not started"
      exit 1
    fi
    log "start codegen$CG (${STOP_S}s stop)"
    timeout --foreground --signal=TERM --kill-after=300 "$STOP_S" $EPL run "$C/codegen$CG.json" \
      --out "$R/codegen$CG" "$@" >> "$R/queue.log" 2>&1
    rc=$?
    log "end codegen$CG rc=$rc; table: python3 $S/codegen_table.py $R/codegen$CG > $R/codegen$CG.md"
    exit $rc
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
