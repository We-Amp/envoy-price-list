#!/bin/bash
# Feature rows, session 2, on the bench box (configs from features2.py).
#
#   run-session-2.sh smoke [EPL_ARGS...]   step 2.1: calibrate j16 (gzip arm, CAL_J16) and the
#                                         j16 reference at the load-curve rates (comp-off,
#                                         CAL_LC); the JIT warm-up check; one probe request per
#                                         filter arm (response header, and the Lua and Wasm
#                                         trace log of the empty arms); every smoke config (two
#                                         rounds, evidence recorded, not gated); then check
#   run-session-2.sh check                 freeze every run's evidence from its smokes into
#                                         $RUNS/frozen/, check the frozen spec against those
#                                         smoke legs (every arm, every leg), print the budget
#   run-session-2.sh queue [EPL_ARGS...]   steps 2.2 to 2.7 with the frozen configs: AA-2, F,
#                                         14, LC-j16, then 14b and LC-sfh if they fit
#
# Before `check` and `queue`: write the calibrated rates (and f_warmup_s 15 if the JIT check
# asked for it) into a JSON file and set RATES_JSON=that file; the configs are then rewritten
# from it (features2.py write) before anything is frozen. The smoke ran at the default rates;
# evidence does not depend on the rate.
#
# Queue rules: it does not start unless every arm has smoke legs and every smoke leg passes
# its run's frozen evidence (no override), and the mandatory worst case is at most 9 h 30
# min (FORCE=1 overrides only this budget question, after the lead said so). Hard stop
# STOP_H hours (default 10) after the queue starts; each run gets the time that is left
# and is then sent SIGTERM through `timeout --foreground` (the harness process only; it
# stops its own Envoy, client and containers and writes partial results, incomplete). If
# AA-2 ends without a complete result, the queue stops. Optional runs start only if the
# time used plus their worst case fits: 14b first, LC-sfh last (it is cut first).
#
# Runs go to $RUNS (default ~/epl/runs/wk5-s2), smokes to $RUNS/smoke, progress to
# $RUNS/queue.log. Extra arguments go to every `epl run`, `calibrate` and `request-probe`.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
EPL="python3 $H/bin/epl"
FEAT=$H/examples/settings-matrix/features2.py
TABLE=$H/examples/settings-matrix/features_table2.py
C=$H/examples/settings-matrix/features2
R=${RUNS:-$HOME/epl/runs/wk5-s2}
SMOKE=$R/smoke
FROZEN=$R/frozen
STOP_S=$(( ${STOP_H:-10} * 3600 ))
CAL_J16=${CAL_J16:-2000,2400,2800}
CAL_LC=${CAL_LC:-5200,7600,10400}
MANDATORY="aa-2 run-f 14-compression lc-j16"
OPTIONAL="14b lc-sfh"
SMOKES="smoke-aa smoke-f1 smoke-f2 smoke-f3 smoke-14a smoke-14b smoke-lc smoke-14bidle smoke-sfh"
mkdir -p "$R"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/queue.log"; }

rewrite() {
  if [ -n "${RATES_JSON:-}" ]; then
    log "configs rewritten from $RATES_JSON"
    python3 "$FEAT" write "$RATES_JSON" >> "$R/queue.log" 2>&1 || { log "features2.py write failed"; exit 1; }
  fi
}

check() {
  local bad=0 run dirs s
  mkdir -p "$FROZEN"
  for run in $MANDATORY $OPTIONAL; do
    dirs=""
    for s in $(python3 "$FEAT" check-list "$run"); do dirs="$dirs $SMOKE/$s"; done
    log "freeze and check $run against$dirs"
    # shellcheck disable=SC2086
    if ! $EPL evidence-check "$C/$run.json" $dirs --freeze "$FROZEN/$run.json" >> "$R/queue.log" 2>&1; then
      log "evidence-check $run FAILED (details in queue.log)"
      bad=1
    fi
  done
  python3 "$FEAT" budget "$SMOKE" "$FROZEN" | tee -a "$R/queue.log"
  local brc=${PIPESTATUS[0]}
  [ "$brc" -eq 3 ] && log "mandatory worst case above 9 h 30 min: ask the lead before the queue"
  [ "$brc" -ne 0 ] && [ "$brc" -ne 3 ] && bad=1
  return $(( bad ? 1 : (brc == 3 ? 3 : 0) ))
}

probe() {  # probe ARM SHAPE CONFIG [request-probe args]
  local arm=$1 shape=$2 cfg=$3
  shift 3
  log "probe $arm $shape"
  $EPL request-probe "$C/$cfg.json" --arm "$arm" --shape "$shape" --out "$R/probe/$arm-$shape" "$@" \
    >> "$R/queue.log" 2>&1
  log "end probe $arm $shape rc=$?"
}

mode=${1:-}
shift || true
case "$mode" in
  smoke)
    log "smoke start pid $$ harness $(cat "$H/VERSION" 2>/dev/null)"
    mkdir -p "$SMOKE" "$R/probe"
    log "calibrate j16 gzip at $CAL_J16"
    $EPL calibrate "$C/14-compression.json" --arm gzip --shape j16 --rps "$CAL_J16" --out "$R/cal-j16-gzip" "$@" \
      >> "$R/queue.log" 2>&1
    log "calibrate j16 comp-off at $CAL_LC (ramped shape)"
    $EPL calibrate "$C/lc-j16.json" --arm comp-off --shape j16-c --rps "$CAL_LC" --out "$R/cal-j16-comp-off" "$@" \
      >> "$R/queue.log" 2>&1
    log "JIT warm-up check"
    $EPL run "$C/jit-check.json" --out "$R/jit-check" --allow-short "$@" >> "$R/queue.log" 2>&1
    python3 "$TABLE" jit "$R/jit-check" | tee -a "$R/queue.log"
    for lib in gzip brotli zstd; do probe "$lib" j4 14-compression --expect "content-encoding=$( \
      case $lib in gzip) echo gzip;; brotli) echo br;; zstd) echo zstd;; esac)" "$@"; done
    probe comp-off j4 14-compression --expect "content-encoding=" "$@"
    probe gzip s-ae 14b --expect "content-encoding=" "$@"
    for a in lua-header wasm-header; do probe "$a" s run-f --expect "x-epl-filter=1" "$@"; done
    probe filter-off s run-f --expect "x-epl-filter=" "$@"
    probe lua-empty s run-f --trace lua:trace "$@"
    probe wasm-empty s run-f --trace wasm:trace "$@"
    for s in $SMOKES; do
      log "start $s"
      $EPL run "$C/$s.json" --out "$SMOKE/$s" --allow-short "$@" >> "$R/queue.log" 2>&1
      log "end $s rc=$?"
    done
    rewrite
    check
    log "smoke done rc=$?"
    ;;
  check)
    rewrite
    check
    exit $?
    ;;
  queue)
    log "queue start pid $$ harness $(cat "$H/VERSION" 2>/dev/null) args: $*"
    rewrite
    check
    rc=$?
    if [ "$rc" -eq 3 ] && [ "${FORCE:-0}" = 1 ]; then
      log "budget above 9 h 30 min: FORCE=1 given, starting (the lead agreed)"
    elif [ "$rc" -ne 0 ]; then
      log "queue not started (check rc=$rc: 1 = evidence check failed, no override; 3 = budget, FORCE=1 after the lead agreed)"
      exit 1
    fi
    T0=$(date +%s)
    left() { echo $(( STOP_S - ($(date +%s) - T0) )); }
    for run in $MANDATORY; do
      L=$(left)
      if [ "$L" -le 60 ]; then
        log "skip $run: session stop reached"
        continue
      fi
      log "start $run (${L}s left before the stop)"
      timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$FROZEN/$run.json" --out "$R/$run" "$@" \
        >> "$R/queue.log" 2>&1
      rc=$?
      [ "$rc" -eq 124 ] && log "$run stopped at the session stop (SIGTERM); partial results, incomplete"
      log "end $run rc=$rc"
      if [ "$run" = aa-2 ]; then
        if ! why=$(python3 "$FEAT" has-floor "$R/aa-2"); then
          log "AA-2 has no complete result ($why): the queue stops, no row runs without its floor"
          exit 1
        fi
        log "AA-2 floor: $why"
      fi
    done
    for run in $OPTIONAL; do
      CAP=$(python3 "$FEAT" cap "$run" "$SMOKE" "$FROZEN")
      L=$(left)
      if [ "$CAP" -le "$L" ]; then
        log "start $run (worst case ${CAP}s, ${L}s left)"
        timeout --foreground --signal=TERM --kill-after=300 "$L" $EPL run "$FROZEN/$run.json" --out "$R/$run" "$@" \
          >> "$R/queue.log" 2>&1
        log "end $run rc=$?"
      else
        log "skip $run: worst case ${CAP}s does not fit in the ${L}s left"
      fi
    done
    log "queue done; tables: python3 $TABLE $R > $R/tables.md"
    ;;
  *)
    sed -n '2,33p' "$0"
    exit 2
    ;;
esac
