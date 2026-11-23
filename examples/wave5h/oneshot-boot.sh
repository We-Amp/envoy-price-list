#!/bin/bash
# !!! WARNING: THIS SCRIPT CHANGES THE BOOT LOADER OF THE MACHINE IT RUNS ON. !!!
# It writes /etc/grub.d/42_epl_oneshot, regenerates grub.cfg and can select a boot entry with the kernel's
# CPU-vulnerability mitigations turned OFF (mitigations=off) for the next boot. A machine booted that way is
# exposed to the attacks those mitigations stop. Use it only on a dedicated, isolated bench machine that
# runs nothing else, that you can reach at its console if a boot fails, and only after reading `entries`.
# Remove the entries afterwards (`remove`). Never on a shared, production or internet-facing machine.
# One-shot boot entries for a kernel command-line arm (track H: mitigations=off), for GRUB 2 on a
# Debian/Ubuntu system. Run by the operator, as root (sudo). Nothing here runs from a chain.
#
#   oneshot-boot.sh entries          print the two entries that `install` would add (review first)
#   oneshot-boot.sh install          back up grub.cfg, add /etc/grub.d/42_epl_oneshot, run update-grub,
#                                    show the diff (only the two entries may be new) and verify
#   oneshot-boot.sh next on|off      boot that entry ONCE at the next reboot (grub-reboot); GRUB clears
#                                    the choice before the kernel starts, where it can write grubenv (below)
#   oneshot-boot.sh status           pending one-shot choice, the running command line and mitigation state
#   oneshot-boot.sh remove           clear a pending one-shot choice (next_entry), delete the entries again
#                                    (rm + update-grub) and diff against the backup
#
# The entries are copies of the first menu entry of the current grub.cfg (the default boot: same
# kernel, initrd, root and module loads), with their own title and id; `off` appends mitigations=off
# to the kernel line and is otherwise identical to `on`. The default entry (GRUB_DEFAULT) is never
# touched, so a power cycle or any reboot without `next` boots the default with mitigations on.
#
# CAVEAT: that holds only where GRUB can write its environment block (grubenv). With /boot on LVM, software
# RAID, btrfs or ZFS, GRUB cannot write it (a documented GRUB limitation; not tested by us): next_entry then
# stays set and EVERY later boot comes up with mitigations=off until it is cleared. After the one-shot boot,
# run `status` and confirm next_entry is empty; if not, run `grub-editenv - unset next_entry` (or `remove`).
set -eu
CFG=${GRUB_CFG:-/boot/grub/grub.cfg}
SNIP=${GRUB_SNIPPET:-/etc/grub.d/42_epl_oneshot}
BACKUP=${GRUB_BACKUP:-/boot/grub/grub.cfg.pre-epl-oneshot}
ARG=${ONESHOT_ARG:-mitigations=off}
ID_ON=epl-oneshot-on
ID_OFF=epl-oneshot-off

first_entry() {  # the first top-level menuentry block of grub.cfg, verbatim
  awk 'f==0 && /^menuentry /{f=1} f==1{print} f==1 && /^}/{exit}' "$CFG"
}

entry() {  # entry ID TITLE EXTRA: the first entry with a new title and id, EXTRA appended to the linux line
  local id=$1 title=$2 extra=$3 blk
  blk=$(first_entry)
  [ -n "$blk" ] || { echo "oneshot: no menuentry in $CFG" >&2; return 1; }
  # one linux line, or several (cloud images boot without an initrd first and fall back to one): the
  # argument goes on every linux line of the entry
  [ "$(printf '%s\n' "$blk" | grep -cE '^[[:space:]]*linux[[:space:]]')" -ge 1 ] || {
    echo "oneshot: the first entry has no linux line" >&2; return 1; }
  printf '%s\n' "$blk" | awk -v id="$id" -v title="$title" -v extra="$extra" '
    NR==1 {
      sub(/^menuentry '\''[^'\'']*'\''/, "menuentry '\''" title "'\''")
      if (!sub(/\$menuentry_id_option '\''[^'\'']*'\''/, "$menuentry_id_option '\''" id "'\''")) { print "no id" > "/dev/stderr"; exit 1 }
      print; next }
    /^[[:space:]]*linux[[:space:]]/ { sub(/[[:space:]]+$/, ""); if (extra != "") $0 = $0 " " extra }
    { print }'
}

entries() {
  entry "$ID_ON" "EPL one-shot: default command line" ""
  entry "$ID_OFF" "EPL one-shot: $ARG" "$ARG"
}

need_root() { [ "$(id -u)" = 0 ] || { echo "oneshot: run as root (sudo bash $0 $*)"; exit 1; }; }

case "${1:-}" in
  entries)
    [ -r "$CFG" ] || { echo "oneshot: cannot read $CFG (sudo bash $0 entries)"; exit 1; }
    entries
    ;;
  install)
    need_root install
    [ -e "$SNIP" ] && { echo "oneshot: $SNIP exists; remove first"; exit 1; }
    body=$(entries)
    cp -p "$CFG" "$BACKUP"
    { printf '#!/bin/sh\nexec tail -n +3 $0\n'; printf '%s\n' "$body"; } > "$SNIP"
    chmod 755 "$SNIP"
    update-grub
    echo "--- diff $BACKUP $CFG (only the two EPL entries may be new):"
    diff "$BACKUP" "$CFG" || true
    for id in "$ID_ON" "$ID_OFF"; do grep -q "'$id'" "$CFG" || { echo "oneshot: $id missing from $CFG"; exit 1; }; done
    grep -q 'save_env next_entry' "$CFG" || { echo "oneshot: $CFG has no next_entry handling; do not use next"; exit 1; }
    echo "oneshot: installed ($ID_ON, $ID_OFF); default entry unchanged: $(grep -E '^GRUB_DEFAULT=' /etc/default/grub)"
    ;;
  next)
    need_root next
    case "${2:-}" in on) id=$ID_ON ;; off) id=$ID_OFF ;; *) echo "oneshot: next on|off"; exit 2 ;; esac
    grep -q "'$id'" "$CFG" || { echo "oneshot: $id not in $CFG (install first)"; exit 1; }
    grub-reboot "$id"
    echo "oneshot: next boot (once): $id"; grub-editenv list
    ;;
  status)
    echo "grubenv: $(grub-editenv list 2>/dev/null | tr '\n' ' ')"
    echo "cmdline: $(cat /proc/cmdline)"
    for f in meltdown mds spectre_v2 spec_store_bypass; do echo "$f: $(cat /sys/devices/system/cpu/vulnerabilities/$f)"; done
    ;;
  remove)
    need_root remove
    # a pending one-shot choice must not outlive the entries (and on a /boot GRUB cannot write, it would stick)
    grub-editenv - unset next_entry || true
    rm -f "$SNIP"
    update-grub
    if [ -f "$BACKUP" ]; then
      if diff -q "$BACKUP" "$CFG" >/dev/null; then echo "oneshot: grub.cfg equals the backup again"; else
        echo "oneshot: grub.cfg differs from the backup:"; diff "$BACKUP" "$CFG" || true; fi
    fi
    grub-editenv list
    ;;
  *)
    sed -n '2,/^set -eu$/p' "$0" | sed '$d'
    exit 2
    ;;
esac
