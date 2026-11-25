#!/bin/bash
# perf wrapper for the kernel call-graph legs (non-scored): as perf-sys.sh, but the inner command is a
# system-wide `perf record -a -g -F 999` on the CPUs the Envoy process may run on, for the same window.
export W7_MECH_KIND=kcg
exec bash "$(cd "$(dirname "$0")" && pwd)/perf-sys.sh" "$@"
