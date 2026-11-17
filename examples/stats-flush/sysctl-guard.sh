# Session guard for net.core.rmem_max (sourced by run-session.sh; bash).
#
# The discard sink asks for a 256 MiB receive buffer; the kernel caps that at rmem_max. For
# the session the guard records the value it finds, raises it, reads it back, and restores the
# original on exit through a trap that also fires on failure and on the hard stop's SIGTERM,
# then reads the restored value back. It refuses to start when the value it finds is not the
# one recorded at step 0 (someone else changed it). Both values go into the session record.
# Envoy's send side is untouched, so the sink's price is unchanged; only drops go away.
#
#   GUARD_FILE   the sysctl file (default /proc/sys/net/core/rmem_max; tests use a plain file)
#   GUARD_VALUE  the session value (default 268435456)
#   GUARD_DIR    where the step-0 value and the session record are kept

GUARD_FILE=${GUARD_FILE:-/proc/sys/net/core/rmem_max}
GUARD_VALUE=${GUARD_VALUE:-268435456}

guard_log() { echo "$(date -u +%FT%TZ) sysctl-guard: $*" | tee -a "$GUARD_DIR/sysctl-guard.log"; }

guard_set() {  # write a value: through sysctl for the real file, directly for a test file
  if [ "$GUARD_FILE" = /proc/sys/net/core/rmem_max ]; then
    sudo -n sysctl -q -w net.core.rmem_max="$1"
  else
    echo "$1" > "$GUARD_FILE"
  fi
}

guard_step0() {  # record the value found at step 0 (once)
  mkdir -p "$GUARD_DIR"
  if [ ! -f "$GUARD_DIR/rmem_max.step0" ]; then
    cat "$GUARD_FILE" > "$GUARD_DIR/rmem_max.step0"
    guard_log "step 0 value $(cat "$GUARD_DIR/rmem_max.step0")"
  fi
}

guard_begin() {
  mkdir -p "$GUARD_DIR"
  guard_step0
  GUARD_ORIG=$(cat "$GUARD_FILE")
  local step0
  step0=$(cat "$GUARD_DIR/rmem_max.step0")
  if [ "$GUARD_ORIG" != "$step0" ]; then
    guard_log "REFUSED: rmem_max is $GUARD_ORIG, step 0 recorded $step0 (changed by someone else?)"
    return 1
  fi
  trap guard_end EXIT
  trap 'guard_end; exit 143' TERM
  trap 'guard_end; exit 130' INT
  if ! guard_set "$GUARD_VALUE"; then
    guard_log "could not set rmem_max to $GUARD_VALUE"
    return 1
  fi
  local now
  now=$(cat "$GUARD_FILE")
  if [ "$now" != "$GUARD_VALUE" ]; then
    guard_log "read back $now, not $GUARD_VALUE"
    return 1
  fi
  GUARD_ACTIVE=1
  printf '{"rmem_max_original": %s, "rmem_max_session": %s, "set_utc": "%s"}\n' \
    "$GUARD_ORIG" "$GUARD_VALUE" "$(date -u +%FT%TZ)" > "$GUARD_DIR/sysctl-session.json"
  guard_log "rmem_max $GUARD_ORIG -> $GUARD_VALUE"
}

guard_end() {
  [ "${GUARD_ACTIVE:-0}" = 1 ] || return 0
  GUARD_ACTIVE=0
  guard_set "$GUARD_ORIG" || true
  local back
  back=$(cat "$GUARD_FILE")
  if [ "$back" = "$GUARD_ORIG" ]; then
    guard_log "restored rmem_max $back"
    printf '{"rmem_max_original": %s, "rmem_max_session": %s, "restored": %s, "restore_ok": true, "restored_utc": "%s"}\n' \
      "$GUARD_ORIG" "$GUARD_VALUE" "$back" "$(date -u +%FT%TZ)" > "$GUARD_DIR/sysctl-session.json"
  else
    guard_log "RESTORE FAILED: rmem_max reads $back, expected $GUARD_ORIG"
    printf '{"rmem_max_original": %s, "rmem_max_session": %s, "restored": %s, "restore_ok": false}\n' \
      "$GUARD_ORIG" "$GUARD_VALUE" "$back" > "$GUARD_DIR/sysctl-session.json"
  fi
}
