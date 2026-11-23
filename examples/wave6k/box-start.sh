#!/bin/bash
# Start one track K block on the VM, detached (one login; returns at once):
#   K_BLOCK=A|B|C|D bash ~/epl/harness-wave6k/examples/wave6k/box-start.sh
# It is track H's block chain (examples/wave5h/chain-h.sh) with K's configs, K's runs directory and the general
# boot-state rule (examples/wave5h/bootstate.py --rule general). Block A has no earlier boot to compare with; B and C are compared strictly with A.
set -u
H=$(cd "$(dirname "$0")/../.." && pwd)
case "${K_BLOCK:-}" in A|B|C|D) ;; *) echo "K_BLOCK must be A, B, C or D"; exit 2 ;; esac
export H_BLOCK=$K_BLOCK H_TOP=${H_TOP:-$HOME/epl/runs/wave6k} H_CONF_DIR=$H/examples/wave6k/c4-32 H_STATE_RULE=general
exec bash "$H/examples/wave5h/box-start.sh"
