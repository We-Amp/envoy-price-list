#!/bin/bash
# Reports of the W8-1 call-graph legs, on the box, after the last leg: mech-post.sh MECH_DIR. As S2's, with the
# unstripped twin of the patched binary (the three profiled arms all run w8-A) in a build-id cache of the
# session's own (~/epl/bins/wave8w1/buildid; removed with the staged binaries). For every out-*/kcg-<pid>.data
# without folded stacks yet: perf report text (self time by comm, dso and symbol; inclusive time by symbol)
# and folded stacks (fold.py). One line per file in MECH_DIR/post-check.txt: OK when the folded stacks carry
# at least 90% of the samples perf counted and at least one Envoy symbol and one kernel symbol resolved.
# The perf.data files are never copied; the chain deletes them after this script.
P=${PERF:-perf}
M=${1:?mech dir}
HERE=$(cd "$(dirname "$0")" && pwd)
B=$HOME/epl/bins/wave8w1
BD=$B/buildid
T=(taskset -c 8-19)
if [ -f "$B/envoy-w8-A.unstripped" ] && [ ! -d "$BD/.build-id" ]; then
  "${T[@]}" "$P" --buildid-dir "$BD" buildid-cache -a "$B/envoy-w8-A.unstripped" 2>&1 | tail -2
  [ -f "$HOME/epl/sym/envoy-opt.unstripped" ] && "${T[@]}" "$P" --buildid-dir "$BD" buildid-cache -a "$HOME/epl/sym/envoy-opt.unstripped" 2>&1 | tail -2
fi
for f in "$M"/out-*/kcg-*.data; do
  [ -e "$f" ] || continue
  b=${f%.data}
  [ -s "$b.folded.gz" ] && continue
  "${T[@]}" sudo -n "$P" --buildid-dir "$BD" report -i "$f" --stdio --no-children --sort comm,dso,sym -g none \
    --percent-limit 0.05 > "$b.report.txt" 2> "$b.report.err"
  "${T[@]}" sudo -n "$P" --buildid-dir "$BD" report -i "$f" --stdio --children --sort sym -g none \
    --percent-limit 0.3 > "$b.children.txt" 2>> "$b.report.err"
  # (no tee/head on this pipe: a reader that exits early ends the stream)
  "${T[@]}" sudo -n "$P" --buildid-dir "$BD" script -i "$f" -F comm,pid,tid,cpu,period,event,ip,sym,dso 2>> "$b.report.err" \
    | "${T[@]}" python3 -I "$HERE/fold.py" 2> "$b.fold.err" | gzip > "$b.folded.gz"
  want=$("${T[@]}" sudo -n "$P" report -i "$f" --stats 2>&1 | awk '/SAMPLE events:/{print $3; exit}')
  case "$want" in ''|*[!0-9]*) want=0 ;; esac
  got=$(sed -n 's/^fold: [0-9]* stacks, \([0-9]*\) samples.*/\1/p' "$b.fold.err")
  env_syms=$(zcat "$b.folded.gz" | grep -c 'Envoy::')
  k_syms=$(zcat "$b.folded.gz" | grep -c '_\[k\]')
  ok=BAD
  if [ "${got:-0}" -ge 100 ] && [ "$((${got:-0} * 10))" -ge "$((${want:-0} * 9))" ] && [ "${env_syms:-0}" -ge 1 ] && [ "${k_syms:-0}" -ge 1 ]; then ok=OK; fi
  echo "$ok $f samples_perf=${want:-0} samples_folded=${got:-0} stacks_with_envoy_symbols=${env_syms:-0} stacks_with_kernel_symbols=${k_syms:-0}" >> "$M/post-check.txt"
  echo "mech-post: $ok $f -> $(wc -l < "$b.report.txt") report lines; $(cat "$b.fold.err")"
done
exit 0
