#!/bin/bash
# Reports of the call-graph legs, on the box, after the last leg: mech-post.sh MECH_DIR. For every
# out-*/kcg-<pid>.data: perf report text (self time by comm, dso and symbol; inclusive time by symbol) and
# folded stacks (fold.py). Envoy's own frames resolve when the unstripped twin of the official binary sits
# in the build-id cache at ~/epl/sym/buildid (best effort; kernel frames come from kallsyms either way).
# The perf.data files stay on the box (deleted in the cleanup), they are never copied.
P=${PERF:-perf}
M=${1:?mech dir}
HERE=$(cd "$(dirname "$0")" && pwd)
BD=$HOME/epl/sym/buildid
T=(taskset -c 8-19)
if [ -f "$HOME/epl/sym/envoy-opt.unstripped" ] && [ ! -d "$BD/.build-id" ]; then
  "${T[@]}" "$P" --buildid-dir "$BD" buildid-cache -a "$HOME/epl/sym/envoy-opt.unstripped" 2>&1 | tail -2
fi
for f in "$M"/out-*/kcg-*.data; do
  [ -e "$f" ] || continue
  b=${f%.data}
  "${T[@]}" sudo -n "$P" --buildid-dir "$BD" report -i "$f" --stdio --no-children --sort comm,dso,sym -g none \
    --percent-limit 0.05 > "$b.report.txt" 2> "$b.report.err"
  "${T[@]}" sudo -n "$P" --buildid-dir "$BD" report -i "$f" --stdio --children --sort sym -g none \
    --percent-limit 0.3 > "$b.children.txt" 2>> "$b.report.err"
  # (no tee/head on this pipe: a reader that exits early ends the stream; the first run lost its stacks so)
  "${T[@]}" sudo -n "$P" --buildid-dir "$BD" script -i "$f" -F comm,pid,tid,cpu,period,event,ip,sym,dso 2>> "$b.report.err" \
    | "${T[@]}" python3 -I "$HERE/fold.py" 2> "$b.fold.err" | gzip > "$b.folded.gz"
  echo "mech-post: $f -> $(wc -l < "$b.report.txt") report lines, $(zcat "$b.folded.gz" | wc -l) folded stacks; $(cat "$b.fold.err")"
done
exit 0
