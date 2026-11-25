#!/bin/bash
# Wave 7 S1, second chain (a departure from the plan, recorded with the results): only the non-scored kernel call-graph legs,
# which chain-s1.sh dropped because its selftest asked for three distinct kernel symbols from a 1 s profile
# of an idle CPU (it resolved two; resolution itself worked). Scripts and configs are the staged ones,
# unchanged. No scored leg runs here.
set -u
H=$HOME/epl/harness-wave7s1
S=$H/examples/wave7s1
R=$HOME/epl/runs/wave7s1
export RUNS=$R
export PERF=/usr/lib/linux-tools/6.8.0-149-generic/perf
L=$R/chain-s1-kcg.log
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-s1-kcg.rc"; exit "$1"; }
log "chain s1-kcg start pid $$ harness $H ($(cat "$H/HARNESS_COMMIT" 2>/dev/null))"
if ! st=$(bash "$H/examples/wave4g/idle.sh"); then log "box $st"; fin 10; fi
log "$st"
[ "$(sha256sum "$HOME/epl/bin/envoy-1.40.2" | cut -d' ' -f1)" = 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc ] || { log "envoy pin mismatch"; fin 14; }
for m in mech-kcg-relay mech-kcg-hop; do
  export W7_MECH_OUT=$R/mech/out-$m
  bash "$S/run-s1.sh" mech "$m"
done
bash "$S/mech-post.sh" "$R/mech" >> "$L" 2>&1
log "call-graph legs and reports done (non-scored)"
fin 0
