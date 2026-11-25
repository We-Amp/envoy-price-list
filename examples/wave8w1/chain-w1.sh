#!/bin/bash
# Wave 8 session W8-1, the SECOND chain: the scored runs. Started by the runner (box-start.sh w1) after chain-pre.sh
# ended and its checks were read; $R/go.txt lists the runs the runner released (of a b d c), $R/pick-<run>.txt
# (written by chain-pre.sh) names each run's variant. Order a, b, d, c (plan 4.2: the rider last).
#   per run: run-w1.sh queue (every smoke leg valid, evidence frozen from the smoke, then the run). A run is never
#     cut in the middle (the stop in run-w1.sh is a safety net far above a run's length).
#   after each run: the shape order of every round is printed (plan section 1).
#   the rider c: BEFORE it starts the chain checks the session clock ($R/t0): when fewer than 35 minutes of the
#     2.5 h remain (more than 115 minutes gone) the rider is skipped and the log says so. Its tracepoint legs
#     (mech-sys-<variant>) run after its scored run: they gate no patch row.
# Nothing scored is repeated by the chain. Exit code in $R/chain-w1.rc: 0 when every released run that was
# started ended rc=0 (a rider skipped by the clock does not change it); 20 otherwise.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave8w1
R=${RUNS:-$HOME/epl/runs/wave8w1}
export RUNS=$R
L=$R/chain-w1.log
export PERF=${PERF:-/usr/lib/linux-tools/6.8.0-149-generic/perf}
T0=$(cat "$R/t0" 2>/dev/null || date +%s)
LIMIT_MIN=${W1_RIDER_LIMIT_MIN:-115}
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
el() { echo $(( ($(date +%s) - T0) / 60 )); }
fin() { log "chain end rc=$1, $(el) min after the session's start"; echo "$1" > "$R/chain-w1.rc"; exit "$1"; }
GO=$(cat "$R/go.txt" 2>/dev/null)
log "chain w1 start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null)); released runs: ${GO:-none}; session clock: $(el) min gone"
[ -e "$R/chain-pre.rc" ] || { log "chain-pre has not ended; nothing is scored"; fin 12; }
ok=0
for i in $(seq 1 20); do
  if st=$(bash "$H/examples/wave4g/idle.sh"); then ok=1; break; fi
  sleep 30
done
[ "$ok" = 1 ] || { log "box $st"; fin 10; }
log "$st"
[ "$(sha256sum "$HOME/epl/bins/wave8w1/envoy-w8-A" | cut -d' ' -f1)" = 46c98673eddc4f480cfc79cf8b6cfb620b6fec97245dcc0332535d43475d3971 ] || { log "staged binary differs from its pin"; fin 14; }
[ "$(sha256sum "$HOME/epl/bin/envoy-1.40.2" | cut -d' ' -f1)" = 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc ] || { log "official binary differs from its pin"; fin 14; }
for p in 10110 9921 8092 8096 8098 8099; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; fin 16; }
done
W7_EAGAIN_FILTER='ret==-11'
[ -s "$R/mech/selftest-w1/eagain.filter" ] && read -r W7_EAGAIN_FILTER < "$R/mech/selftest-w1/eagain.filter"
export W7_EAGAIN_FILTER
bad=0
order() {  # the shape order of every round of a finished run
  python3 -I - "$R/$1/legs.jsonl" <<'PYEOF' 2>/dev/null
import json, sys
seen = {}
for line in open(sys.argv[1]):
    line = line.strip()
    if not line:
        continue
    m = json.loads(line)
    if m.get("arm") and m.get("round") is not None and not m.get("attempt"):
        seen.setdefault(m["round"], [])
        if m["shape"] not in seen[m["round"]]:
            seen[m["round"]].append(m["shape"])
print("; ".join("round %d: %s" % (r, " then ".join(s)) for r, s in sorted(seen.items())))
PYEOF
}
run_one() {
  local run=$1 smoke=$2
  log "scored run $run starts, $(el) min after the session's start"
  if bash "$S/run-w1.sh" queue "$run" "$smoke"; then
    last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
    [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; bad=1; }
    log "$run shape order by round: $(order "$run")"
  else
    log "$run not run (its smoke check or evidence freeze failed)"; bad=1
  fi
}
released() { case " $GO " in *" $1 "*) return 0 ;; esac; return 1; }
for run in a b d; do
  v=$(cat "$R/pick-$run.txt" 2>/dev/null || echo none)
  if ! released "$run"; then log "run $run: NOT released by the runner; not run"; continue; fi
  if [ "$v" = none ]; then log "run $run: not settled in the smoke; not run"; continue; fi
  run_one "$v" "smoke-$v"
done
v=$(cat "$R/pick-c.txt" 2>/dev/null || echo none)
if ! released c; then
  log "rider c: NOT released by the runner; not run"; echo "not-released" > "$R/rider.txt"
elif [ "$v" = none ]; then
  log "rider c: not settled in the smoke; not run"; echo "not-settled" > "$R/rider.txt"
elif [ "$(el)" -gt "$LIMIT_MIN" ]; then
  log "rider c SKIPPED by the time rule: $(el) min of the session's 150 are gone (limit $LIMIT_MIN: fewer than 35 minutes remain)"
  echo "skipped-by-time" > "$R/rider.txt"
else
  run_one "$v" "smoke-$v"
  echo "$v" > "$R/rider.txt"
  export W7_MECH_OUT=$R/mech/out-mech-sys-$v
  bash "$S/run-w1.sh" mech "mech-sys-$v"
  python3 -I "$S/w1_check.py" mech "$R/mech" "mech-sys-$v" >> "$L" 2>&1
  log "mech-sys-$v check rc=$? (the rider's tracepoint legs, after its scored run)"
fi
echo "$bad" > "$R/scored.rc"
log "scored runs done (bad=$bad), $(el) min after the session's start"
[ "$bad" = 0 ] && fin 0
fin 20
