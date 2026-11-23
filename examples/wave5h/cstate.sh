#!/bin/bash
# Idle states for the TCP_DEFER_ACCEPT check (track H). Needs sudo without a password prompt (sudo -n);
# it never prompts and never changes anything else.
#
#   cstate.sh show    CPUS                 every idle state's name and disable flag on CPUS
#   cstate.sh pin     CPUS SAVE NAME...    save the disable flags of CPUS to SAVE, then disable the
#                                          states called NAME (for example C1E C6) on CPUS; verify
#   cstate.sh restore SAVE                 write the saved flags back; verify
#
# CPUS is a list such as 0-3,40-43. A state is found by its name, never by its index; an unknown name,
# an existing SAVE (pin) or a failed write or verification exits non-zero (rc 30 pin, 31 restore).
# The harness itself never changes idle states; it records them, and every leg of a run checks that
# they did not change after the run started.
set -u
MODE=${1:-}
expand() {  # 0-3,40-43 -> 0 1 2 3 40 41 42 43
  local IFS=, part out=""
  for part in $1; do
    if [[ $part == *-* ]]; then out="$out $(seq "${part%-*}" "${part#*-}" | tr '\n' ' ')"; else out="$out $part"; fi
  done
  echo $out
}
write() {  # write VALUE to FILE as root
  printf '%s' "$2" | sudo -n tee "$1" >/dev/null
}
case "$MODE" in
  show)
    for c in $(expand "${2:?CPUS}"); do
      line="cpu$c:"
      for d in /sys/devices/system/cpu/cpu$c/cpuidle/state*; do line="$line $(cat "$d/name")=$(cat "$d/disable")"; done
      echo "$line"
    done
    ;;
  pin)
    CPUS=${2:?CPUS}; SAVE=${3:?SAVE}; shift 3
    [ $# -gt 0 ] || { echo "cstate pin: no state names"; exit 30; }
    [ -e "$SAVE" ] && { echo "cstate pin: $SAVE exists (restore first)"; exit 30; }
    sudo -n true 2>/dev/null || { echo "cstate pin: sudo needs a password; nothing changed"; exit 30; }
    : > "$SAVE"
    for c in $(expand "$CPUS"); do
      for d in /sys/devices/system/cpu/cpu$c/cpuidle/state*; do echo "$d/disable $(cat "$d/disable")" >> "$SAVE"; done
    done
    for name in "$@"; do
      found=0
      for c in $(expand "$CPUS"); do
        for d in /sys/devices/system/cpu/cpu$c/cpuidle/state*; do
          if [ "$(cat "$d/name")" = "$name" ]; then
            found=1
            write "$d/disable" 1 || { echo "cstate pin: write $d/disable failed"; exit 30; }
            [ "$(cat "$d/disable")" = 1 ] || { echo "cstate pin: $d/disable did not take"; exit 30; }
          fi
        done
      done
      [ "$found" = 1 ] || { echo "cstate pin: no idle state called $name on $CPUS"; exit 30; }
    done
    echo "cstate pin: disabled $* on $CPUS (saved to $SAVE)"
    ;;
  restore)
    SAVE=${2:?SAVE}
    [ -s "$SAVE" ] || { echo "cstate restore: nothing saved in $SAVE"; exit 31; }
    bad=0
    while read -r f v; do
      [ "$(cat "$f")" = "$v" ] && continue
      write "$f" "$v" || bad=1
      [ "$(cat "$f")" = "$v" ] || { echo "cstate restore: $f is $(cat "$f"), want $v"; bad=1; }
    done < "$SAVE"
    [ "$bad" = 0 ] || exit 31
    mv "$SAVE" "$SAVE.restored"
    echo "cstate restore: every saved flag is back ($SAVE.restored)"
    ;;
  *)
    sed -n '2,10p' "$0"
    exit 2
    ;;
esac
