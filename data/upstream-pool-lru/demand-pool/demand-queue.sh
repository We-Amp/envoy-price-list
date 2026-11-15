#!/bin/sh
L=~/epl/runs/lru/demand-queue.log
echo "$(date -u +%FT%TZ) queue start pid $$ harness $(cat $HOME/epl/harness/VERSION)" >> $L
echo "$(date -u +%FT%TZ) start demand-pool" >> $L
python3 $HOME/epl/harness/bin/epl run $HOME/epl/harness/examples/upstream-pool-lru/demand-pool.json --out ~/epl/runs/lru/demand-pool >> $L 2>&1
echo "$(date -u +%FT%TZ) end demand-pool rc=$?" >> $L
echo "$(date -u +%FT%TZ) start demand-pool-ka" >> $L
python3 $HOME/epl/harness/bin/epl run $HOME/epl/harness/examples/upstream-pool-lru/demand-pool-ka.json --out ~/epl/runs/lru/demand-pool-ka >> $L 2>&1
echo "$(date -u +%FT%TZ) end demand-pool-ka rc=$?" >> $L
