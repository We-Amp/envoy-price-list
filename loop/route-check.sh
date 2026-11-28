#!/bin/sh
# The stdio route's local check (no box contact when HOST is localhost).
#
#     route-check.sh HOST CONTROLPATH [all|local|box]      e.g. route-check.sh "$EPL_BOX" "$EPL_CM" local
#
# local (checks 1 and 3) sends nothing to HOST: run it from the agent's context any time. box (check 2) runs one
# command on HOST (`exec cat`: an sshd session process and a shell): against the measurement box it belongs INSIDE
# the pre-flight login, before the session's first pre-flight snapshot, so the foreign-activity check never sees it.
# all (the default) runs the three, for a localhost master.
#
# Run it from the agent's own context (a sandbox or a background job). A ControlMaster for HOST must already be up
# on CONTROLPATH, started from a shell that can reach HOST and kept in a long-lived terminal (docs/loop.md, "The
# stdio route"). Checks:
#   1. `ssh -O check` through the Unix socket: "Master running";
#   2. a stdio round trip through the master as a mux client (-T, ProxyCommand=/usr/bin/false): one JSON line in,
#      the same bytes out (no tty, no CR);
#   3. fail closed: with no master on the path, the same client command fails at once (rc 255) and never opens a
#      direct TCP connection.
# rc 0 when all three hold. It prints only its own verdicts.
set -u
H=${1:?host}
CP=${2:?controlpath}
MODE=${3:-all}
case "$MODE" in all|local|box) ;; *) echo "mode must be all, local or box"; exit 2 ;; esac
fail=0
if [ "$MODE" != box ]; then
out=$(ssh -o ControlPath="$CP" -O check "$H" 2>&1)
case "$out" in
  *"Master running"*) echo "1 PASS master running on the socket" ;;
  *) echo "1 FAIL -O check: $out"; fail=1 ;;
esac
fi
line='{"jsonrpc":"2.0","id":1,"method":"ping"}'
if [ "$MODE" != local ]; then
got=$(printf '%s\n' "$line" | ssh -T -o ControlMaster=no -o ControlPath="$CP" -o ProxyCommand=/usr/bin/false \
      -o BatchMode=yes "$H" 'exec cat' 2>/dev/null)
if [ "$got" = "$line" ]; then echo "2 PASS stdio round trip through the master, bytes equal"
else echo "2 FAIL round trip: got [$got]"; fail=1; fi
fi
if [ "$MODE" != box ]; then
nomaster="$CP.none.$$"
t0=$(date +%s)
printf '%s\n' "$line" | ssh -T -o ControlMaster=no -o ControlPath="$nomaster" -o ProxyCommand=/usr/bin/false \
    -o BatchMode=yes -o ConnectTimeout=5 "$H" 'exec cat' >/dev/null 2>&1
rc=$?
t1=$(date +%s)
if [ "$rc" -ne 0 ] && [ $((t1 - t0)) -le 5 ]; then echo "3 PASS no master: rc $rc in $((t1 - t0)) s (fails closed)"
else echo "3 FAIL no master: rc $rc after $((t1 - t0)) s"; fail=1; fi
fi
exit $fail
