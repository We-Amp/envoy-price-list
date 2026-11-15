#!/bin/bash
# Wrapper: the EXIT trap restores the original idle states however the driver ends.
set -u
D=$HOME/wc2/cstate
H=$D/scripts/cstate.sh
restore() {
  echo "$(date -u +%FT%TZ) trap: restoring idle states" >> $D/restore.log
  sudo -n $H restore $D/idle-orig.txt >> $D/restore.log 2>&1
  echo "$(date -u +%FT%TZ) trap: restore exit $?" >> $D/restore.log
}
trap restore EXIT
trap 'exit 130' INT TERM HUP
export KUBECONFIG=$D/kubeconfig
echo $$ > $D/run.pid
python3 $HOME/wc2/scripts/wc3.py "$@"
