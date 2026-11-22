#!/bin/bash
# Box idleness without matching any process by its command line: the 1-minute load and the CPU busy share
# over 3 s from /proc/stat. Prints "idle load L busy B%" and exits 0, or "not idle ..." and exits 10.
read -r l1 _ < /proc/loadavg
s() { awk '/^cpu /{print $2+$3+$4+$6+$7+$8, $2+$3+$4+$5+$6+$7+$8}' /proc/stat; }
read -r b0 t0 < <(s); sleep 3; read -r b1 t1 < <(s)
busy=$(awk -v a="$b0" -v b="$b1" -v c="$t0" -v d="$t1" 'BEGIN{printf "%.2f", 100*(b-a)/((d-c)>0?(d-c):1)}')
if awk -v l="$l1" -v p="$busy" 'BEGIN{exit !(l < 0.5 && p < 2.0)}'; then echo "idle load $l1 busy $busy%"; exit 0; fi
echo "not idle: load $l1 busy $busy%"; exit 10
