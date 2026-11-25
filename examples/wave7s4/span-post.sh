#!/bin/bash
# Reports of the span-path evidence legs, on the box: span-post.sh OUT_DIR. For every span-<pid>.data:
# `perf report --stdio --sort symbol` (self time by symbol; the process ran the unstripped twin, so its own
# symbols resolve from the file it ran), the report's lines that name one of the three span classes, and a
# line in OUT_DIR/span-check.txt with the counts. The perf.data file is deleted once its report holds at
# least 1,000 samples and 100 symbol lines (it is never copied); otherwise it is kept and the line says BAD.
P=${PERF:-perf}
O=${1:?out dir}
T=(taskset -c 8-19)
OTLP='opentelemetry::proto::trace::v1::Span::'
REC='Tracers::OpenTelemetry::Span::'
DEF='Tracers::OpenTelemetry::DeferredSpan::'
for f in "$O"/span-*.data; do
  [ -e "$f" ] || continue
  b=${f%.data}
  "${T[@]}" sudo -n "$P" report -i "$f" --stdio --sort symbol 2> "$b.report.err" | grep -v '^#' | grep . > "$b.report.txt"
  n=$("${T[@]}" sudo -n "$P" report -i "$f" --stats 2>&1 | awk '/SAMPLE events:/{print $3; exit}')
  case "$n" in ''|*[!0-9]*) n=0 ;; esac
  lines=$(wc -l < "$b.report.txt")
  grep -F -e "$OTLP" -e "$REC" -e "$DEF" -e 'OpenTelemetry::Tracer::startSpan' "$b.report.txt" > "$b.span-lines.txt"
  c() { grep -c -F "$1" "$b.report.txt"; }
  pct() { grep -F "$1" "$b.report.txt" | awk '{gsub("%","",$1); s+=$1} END{printf "%.3f", s+0}'; }
  ok=BAD
  if [ "$n" -ge 1000 ] && [ "$lines" -ge 100 ]; then ok=OK; sudo -n rm -f "$f"; fi
  echo "$ok $(basename "$b") samples=$n symbol_lines=$lines otlp_span_symbols=$(c "$OTLP") otlp_span_pct=$(pct "$OTLP") recording_span_symbols=$(c "$REC") recording_span_pct=$(pct "$REC") deferred_span_symbols=$(c "$DEF") deferred_span_pct=$(pct "$DEF") data_left=$([ -e "$f" ] && echo 1 || echo 0)" >> "$O/span-check.txt"
done
cat "$O/span-check.txt" 2>/dev/null
exit 0
