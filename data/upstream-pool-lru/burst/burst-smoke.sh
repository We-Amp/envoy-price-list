#!/bin/sh
L=~/epl/runs/lru/burst-queue.log
echo "$(date -u +%FT%TZ) smoke start pid $$ harness $(cat $HOME/epl/harness/VERSION)" >> $L
python3 $HOME/epl/harness/bin/epl run $HOME/epl/harness/examples/upstream-pool-lru/burst-smoke.json --out ~/epl/runs/lru/burst-smoke --fixed --allow-short >> $L 2>&1
echo "$(date -u +%FT%TZ) smoke end rc=$?" >> $L
