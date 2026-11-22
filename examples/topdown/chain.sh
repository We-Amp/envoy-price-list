#!/bin/bash
# Top-down study chain on the bench box: idle check, records, counter run (topdown-a), LBR run (lbr-a).
# Start it once, detached, from a harness checkout:
#   nohup examples/topdown/chain.sh > /dev/null 2>&1 &
# Writes chain.log and chain.rc (counter rc, LBR rc; 90 = not idle, 91 = no harness) in TD_DIR.
#   TD_DIR      run directory (default ~/epl/runs/topdown-a; the configs' workdir)
#   PERF        perf binary (default: perf on PATH; topdown-a.json names its own, see make.py --perf)
#   CHECK_CPUS  CPUs whose governor and frequency limits are recorded (default: the SUT CPUs 0-3
#               of the configs and their SMT siblings 40-43)
#   STOCK_BIN, PGOLTO_BIN  the two arms' binaries, hashed into bins.sha256 / bins.md5
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
H=$(cd "$HERE/../.." && pwd)
D=${TD_DIR:-$HOME/epl/runs/topdown-a}
P=${PERF:-perf}
CHECK_CPUS=${CHECK_CPUS:-0 1 2 3 40 41 42 43}
STOCK_BIN=${STOCK_BIN:-$HOME/epl/bin/envoy-1.40.2}
PGOLTO_BIN=${PGOLTO_BIN:-$HOME/epl/bins/pgolto/envoy-pgolto-prodalloc}
mkdir -p "$D"
exec > "$D/chain.log" 2>&1
echo "chain start $(date -u +%FT%TZ) pid $$"
uptime
L1=$(cut -d' ' -f1 /proc/loadavg)
if ! awk "BEGIN{exit !($L1 < 1.0)}"; then
  echo "NOT IDLE: load1 $L1"; ps -eo pid,user,pcpu,etime,args --sort=-pcpu | head -12; echo 90 > "$D/chain.rc"; exit 90
fi
ps -eo pid,user,pcpu,etime,args --sort=-pcpu | head -8
echo "no_turbo $(cat /sys/devices/system/cpu/intel_pstate/no_turbo)"
for c in $CHECK_CPUS; do
  echo "cpu$c $(cat "/sys/devices/system/cpu/cpu$c/cpufreq/scaling_governor") $(cat "/sys/devices/system/cpu/cpu$c/cpufreq/scaling_min_freq") $(cat "/sys/devices/system/cpu/cpu$c/cpufreq/scaling_max_freq")"
done
cat /proc/sys/kernel/perf_event_paranoid /proc/sys/kernel/nmi_watchdog
cat /sys/kernel/mm/transparent_hugepage/enabled
uname -r; "$P" --version
grep -r . /sys/devices/system/cpu/vulnerabilities/ > "$D/vulnerabilities.txt" 2>&1
"$P" list -j > "$D/perf-list.json" 2>/dev/null
sha256sum "$STOCK_BIN" "$PGOLTO_BIN" > "$D/bins.sha256"
md5sum "$STOCK_BIN" "$PGOLTO_BIN" > "$D/bins.md5"
cat "$D/bins.md5"
# the lbr-a config runs the perf wrapper from the run directory
install -m 755 "$HERE/perf-lbr.sh" "$D/perf-lbr.sh"
export TD_LBR_OUT=$D/lbr-data PERF="$P"
cd "$H" || { echo 91 > "$D/chain.rc"; exit 91; }
echo "counter run start $(date -u +%FT%TZ)"
python3 bin/epl run "$HERE/topdown-a.json" --out "$D/td"
rc1=$?
echo "counter run rc $rc1 $(date -u +%FT%TZ)"
echo "lbr run start $(date -u +%FT%TZ)"
python3 bin/epl run "$HERE/lbr-a.json" --out "$D/lbr"
rc2=$?
echo "lbr run rc $rc2 $(date -u +%FT%TZ)"
ls -la "$D/lbr-data" 2>&1
echo "$rc1 $rc2" > "$D/chain.rc"
echo "chain end $(date -u +%FT%TZ)"
