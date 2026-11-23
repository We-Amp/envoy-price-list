#!/bin/bash
# Wave 5 track H: one block of the session, one detached chain, one login (start it with box-start.sh).
#
#   H_BLOCK=H0  the TCP_DEFER_ACCEPT check, within the current boot: h-defer-deep (default idle states),
#               then h-defer-c1only (C1E and C6 disabled on Envoy's CPUs and their SMT siblings for that
#               run only; restored on every exit path)
#   H_BLOCK=A   mitigations on   (fresh boot): h-pl, h-c1
#   H_BLOCK=B   mitigations=off  (one-shot boot): h-pl, h-c1
#   H_BLOCK=C   mitigations on   (fresh boot): h-pl, h-c1, h-spec
#   H_BLOCK=D   mitigations=off  (a second one-shot off boot): h-pl only
#
# Before any leg: idle (load and CPU only, no process matched by its command line), the Envoy and client
# pins, ports 10110 and 9921 free, and the boot state (bootstate.py): the expected mitigation state, the
# same kernel, microcode, frequency and idle-state setup as block A (B and C; A itself is compared with
# H0 as a warning only), and a boot id no earlier block had. Per run: smoke, check (smoke valid, evidence frozen), run. A failed
# smoke check skips that run (rc 12) and the chain goes on; a run that ends non-zero ends the chain (rc 20).
# Exit codes: 10 not idle, 13/14/15 boot state (see bootstate.py), 14 pins, 16 port busy, 30/31 idle-state
# pin/restore. Progress in $TOP/$H_BLOCK/chain-h.log, exit code in $TOP/$H_BLOCK/chain-h.rc.
# H_DRY=1 (off the bench box only): every leg simulated (epl --dry-run); the idle, pin, port and boot-state
# checks are logged but do not stop the chain, and the idle states are not touched.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
S=$H/examples/wave5h
TOP=${H_TOP:-$HOME/epl/runs/wave5h}
B=${H_BLOCK:?H_BLOCK must be H0, A, B, C or D}
case "$B" in H0|A|B|C|D) ;; *) echo "H_BLOCK must be H0, A, B, C or D"; exit 2 ;; esac
R=$TOP/$B
export RUNS=$R
mkdir -p "$R"
L=$R/chain-h.log
DRY=${H_DRY:-0}
export H_DRY=$DRY
EPLX=()
[ "$DRY" = 1 ] && EPLX=(--dry-run)
# a check that fails ends the chain with rc, except in a dry run, where it is logged
gate() { if [ "$DRY" = 1 ]; then log "dry run: would stop here with rc $1"; else fin "$1"; fi; }
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L"; }
fin() { log "chain end rc=$1"; echo "$1" > "$R/chain-h.rc"; exit "$1"; }
log "chain h start pid $$ block $B harness $H ($(git -C "$H" rev-parse --short HEAD 2>/dev/null || cat "$H/HARNESS_COMMIT" 2>/dev/null)) uptime $(cut -d' ' -f1 /proc/uptime)s"
if ! st=$(bash "$H/examples/wave4g/idle.sh"); then log "box $st"; gate 10; fi
log "$st"
want=1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc
got=$(sha256sum "$HOME/epl/bin/envoy-1.40.2" 2>/dev/null | cut -d' ' -f1)
[ "$got" = "$want" ] || { log "envoy-1.40.2 sha256 ${got:-missing}, want $want"; gate 14; }
nh=$(md5sum "$HOME/nighthawk-dogfood/bazel-bin/nighthawk_client" 2>/dev/null | cut -c1-8)
[ "$nh" = 310df412 ] || { log "nighthawk_client md5 ${nh:-missing}, want 310df412"; gate 14; }
log "pins checked"
for p in 10110 9921; do
  [ -z "$(ss -Hltn "sport = :$p" 2>/dev/null)" ] || { log "TCP port $p in use (stop)"; gate 16; }
done

# boot state: expected mitigation state, the reference boot's setup, a new boot id
others=()
case "$B" in
  H0) expect=on; ref= ;;
  A) expect=on; ref=$TOP/bootstate-H0.json ;;
  B) expect=off; ref=$TOP/bootstate-A.json ;;
  C) expect=on; ref=$TOP/bootstate-A.json ;;
  D) expect=off; ref=$TOP/bootstate-A.json ;;
esac
for o in H0 A B C D; do
  [ "$o" = "$B" ] && break
  [ -f "$TOP/bootstate-$o.json" ] && others+=(--other-boot "$TOP/bootstate-$o.json")
done
if [ "$B" = B ] || [ "$B" = C ] || [ "$B" = D ]; then
  [ -f "$ref" ] || { log "no reference boot state $ref (block A must run first)"; gate 14; }
fi
refarg=()
if [ -n "$ref" ] && [ -f "$ref" ]; then
  # A is compared with the long-running boot before the series as a warning only; B and C strictly with A
  if [ "$B" = A ]; then refarg=(--ref-advisory "$ref"); else refarg=(--ref "$ref"); fi
fi
[ "$B" = A ] && [ ${#refarg[@]} -eq 0 ] && log "no H0 boot state: block A is checked for its mitigation state only"
python3 -I "$S/bootstate.py" check --expect "$expect" --rule "${H_STATE_RULE:-h}" ${refarg[@]+"${refarg[@]}"} ${others[@]+"${others[@]}"} "$TOP/bootstate-$B.json" >> "$L" 2>&1
rc=$?
[ "$rc" = 0 ] || { log "boot state check FAILED rc=$rc (details above); nothing run"; gate "$rc"; }
log "boot state OK ($expect): $(grep -h . /sys/devices/system/cpu/vulnerabilities/meltdown /sys/devices/system/cpu/vulnerabilities/mds | tr '\n' ';')"

run_one() {  # smoke, check, run; 0 ran rc 0, 12 smoke check failed, 20 run failed
  local run=$1
  bash "$S/run-h.sh" smoke "$run" ${EPLX[@]+"${EPLX[@]}"} || true
  if ! bash "$S/run-h.sh" check "$run"; then log "smoke check $run FAILED: $run not run"; return 12; fi
  log "smoke passed; start $run"
  bash "$S/run-h.sh" queue "$run" ${EPLX[@]+"${EPLX[@]}"}
  local last
  last=$(grep -E "end $run rc=" "$R/queue.log" | tail -1 | sed 's/.*rc=//')
  [ "${last:-x}" = 0 ] || { log "$run failed (rc=${last:-none})"; return 20; }
  return 0
}

rc=0
if [ "$B" = H0 ]; then
  run_one h-defer-deep; r=$?
  [ "$r" = 20 ] && fin 20
  [ "$r" = 12 ] && rc=12
  # Envoy's CPUs (cpus.sut of the config) and their SMT siblings, from the box's topology
  CPUS=$(python3 -c "import json,sys;sys.path.insert(0,sys.argv[1]);from epl import sysprobe as s;c=s.parse_cpuset(json.load(open(sys.argv[2]))['cpus']['sut']);print(','.join(str(x) for x in sorted(c|s.siblings_of(c))))" "$H" "$S/bench-x86_64/h-defer-c1only.json")
  log "idle-state CPUs: $CPUS"
  SAVE=$R/cstate-saved.txt
  restore() { bash "$S/cstate.sh" restore "$SAVE" >> "$L" 2>&1 || { log "IDLE-STATE RESTORE FAILED: a reboot restores the defaults"; echo 31 > "$R/chain-h.rc"; }; }
  if [ "$DRY" = 1 ]; then
    log "dry run: idle states not touched; h-defer-c1only simulated"
    run_one h-defer-c1only; r=$?
    [ "$r" = 20 ] && fin 20
    [ "$r" = 12 ] && rc=12
  elif bash "$S/cstate.sh" pin "$CPUS" "$SAVE" C1E C6 >> "$L" 2>&1; then
    trap 'restore' EXIT
    trap 'exit 143' TERM INT
    log "idle states now: $(bash "$S/cstate.sh" show "$CPUS" | tr '\n' ';')"
    run_one h-defer-c1only; r=$?
    trap - EXIT
    restore
    [ -f "$SAVE.restored" ] || fin 31
    log "idle states restored: $(bash "$S/cstate.sh" show "$CPUS" | tr '\n' ';')"
    [ "$r" = 20 ] && fin 20
    [ "$r" = 12 ] && rc=12
  else
    log "idle-state pin FAILED (details above): h-defer-c1only not run"
    [ -e "$SAVE" ] && restore
    fin 30
  fi
  fin $rc
fi

RUNS_H="h-pl h-c1"
[ "$B" = C ] && RUNS_H="h-pl h-c1 h-spec"
# D (track K): a second off boot that repeats only h-pl, after an A/A failure of B's h-pl
[ "$B" = D ] && RUNS_H="h-pl"
for run in $RUNS_H; do
  run_one "$run"; r=$?
  [ "$r" = 20 ] && fin 20
  [ "$r" = 12 ] && rc=12
done
fin $rc
