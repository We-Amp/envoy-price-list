#!/bin/sh
# epl-agentd's stdio entry on the box. The agent's MCP client starts it as its stdio command over ssh
# (docs/loop.md, "The stdio route"):  ssh -T ... <box> 'exec ~/epl/loop/run-mcp.sh agentd'
#
#   run-mcp.sh CONFIG     CONFIG is a name under $EPL_HOME/loop/ ("agentd" or "agentd.json" for
#                         $EPL_HOME/loop/agentd.json) or a path to a config file
#
# EPL_HOME (default ~/epl) is read once here and passed to the daemon as --home; the harness copy is
# $EPL_HOME/loop/harness. Nothing may print to stdout before the exec: stdout is the MCP channel. The housekeeping
# CPUs come from the config (housekeeping_cpus, no default: a config without them is refused here); the daemon
# re-pins itself to them before any thread starts.
#
# The login-session gate is opt-in. With EPL_SESSION_RECORD=<file>, the daemon starts only when this login's logind
# session is already recorded as ours in that file on a "master" or "login-*" line (written by `state.py master` or
# a login script); only then is "<id> loop-<config> <utc>" appended, as an audit note (verify, not append: an
# unverified append would let any invocation whitelist its own session). Without it, the script logs one audit line
# to stderr and starts the daemon. Every refusal: rc 2, nothing on stdout.
set -eu
refuse() { echo "run-mcp.sh: $*; not started" >&2; exit 2; }
[ "$#" -eq 1 ] || refuse "one argument expected (a config name under \$EPL_HOME/loop/ or a path)"
EH=${EPL_HOME:-$HOME/epl}
case "$1" in
  */*) C=$1 ;;
  ""|.*|*[!A-Za-z0-9._-]*) refuse "argument '$1' refused (a config name: letters, digits, '.', '_', '-')" ;;
  *.json) C="$EH/loop/$1" ;;
  *) C="$EH/loop/$1.json" ;;
esac
[ -f "$C" ] || refuse "no config $C"
NAME=$(basename "$C" .json)
SID=${XDG_SESSION_ID:-$(cat /proc/self/sessionid 2>/dev/null || true)}
if [ -n "${EPL_SESSION_RECORD:-}" ]; then
  [ -n "$SID" ] && [ "$SID" != 4294967295 ] || refuse "no logind session id (XDG_SESSION_ID or /proc/self/sessionid)"
  [ -f "$EPL_SESSION_RECORD" ] || refuse "no session record $EPL_SESSION_RECORD"
  awk -v s="$SID" '$1 == s && ($2 == "master" || $2 ~ /^login-/) { f = 1 } END { exit f ? 0 : 1 }' \
    "$EPL_SESSION_RECORD" 2>/dev/null || refuse "session $SID is not recorded as ours (master or login-*)"
  echo "$SID loop-$NAME $(date -u +%FT%TZ)" >> "$EPL_SESSION_RECORD"
else
  echo "run-mcp.sh: session ${SID:-unknown} loop-$NAME $(date -u +%FT%TZ) (no EPL_SESSION_RECORD: session not checked)" >&2
fi
H="$EH/loop/harness"
HK=$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1])).get("housekeeping_cpus") or "")' "$C") \
  || refuse "config $C not readable as JSON"
[ -n "$HK" ] || refuse "config $C names no housekeeping_cpus (there is no default)"
exec taskset -c "$HK" python3 -I "$H/loop/agentd.py" --config "$C" --home "$EH"
