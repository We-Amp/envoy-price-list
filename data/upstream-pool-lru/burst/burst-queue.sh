#!/bin/sh
L=~/epl/runs/lru/burst-queue.log
H=$HOME/epl/harness
X=$H/examples/upstream-pool-lru
echo "$(date -u +%FT%TZ) queue start pid $$ harness $(cat $H/VERSION)" >> $L
for c in two-hop one-hop; do
  echo "$(date -u +%FT%TZ) start sockets-$c (nofile $(ulimit -n))" >> $L
  python3 $H/bin/epl run $X/$c.json --out ~/epl/runs/lru/sockets-$c --rounds 4 --max-rounds 4 --fixed --allow-short >> $L 2>&1
  echo "$(date -u +%FT%TZ) end sockets-$c rc=$?" >> $L
done
ulimit -n 1048576
echo "$(date -u +%FT%TZ) start burst-smoke2 (nofile $(ulimit -n))" >> $L
python3 $H/bin/epl run $X/burst-smoke.json --out ~/epl/runs/lru/burst-smoke2 --fixed --allow-short >> $L 2>&1
echo "$(date -u +%FT%TZ) end burst-smoke2 rc=$?" >> $L
if ! python3 -c "
import json,sys
L=[json.loads(l) for l in open(\"$HOME/epl/runs/lru/burst-smoke2/legs.jsonl\")]
L=[m for m in L if \"shape\" in m and m.get(\"attempt\",0)==0]
ok=all(m[\"verdict\"][\"valid\"] for m in L) and len(L)==4
print(\"smoke2 first-attempt valid:\", sum(m[\"verdict\"][\"valid\"] for m in L), \"of\", len(L))
sys.exit(0 if ok else 1)" >> $L 2>&1; then
  echo "$(date -u +%FT%TZ) GATE FAILED, burst not started" >> $L
  exit 1
fi
echo "$(date -u +%FT%TZ) start burst (nofile $(ulimit -n))" >> $L
python3 $H/bin/epl run $X/burst.json --out ~/epl/runs/lru/burst --fixed >> $L 2>&1
echo "$(date -u +%FT%TZ) end burst rc=$?" >> $L
