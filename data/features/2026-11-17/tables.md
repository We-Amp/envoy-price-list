# Feature rows, session 1

## Runs

- run-s: 300 legs, 0 invalid; 30 complete rounds; stop: widest cycles_total half-width against its target 0.71% (fh percpu-on vs base) <= target 0.80%
- 18-access-log: 108 legs, 0 invalid; 18 complete rounds; stop: widest cycles_total half-width against its target 1.02% (fh log-text vs log-off) <= target 1.50%
- 17-tracing: 128 legs, 0 invalid; 16 complete rounds; stop: fixed rounds
- 13-ext-authz: 128 legs, 0 invalid; 16 complete rounds; stop: fixed rounds
- 18w-access-log-w16: 64 legs, 0 invalid; 16 complete rounds; stop: widest cycles_total half-width against its target 0.62% (s-w16 log-off-A2 vs log-off) <= target 1.00%

## A/A of the session

Pass: half-width at most 1.0% and no Holm-significant difference (secondary family). Rows 17 and 18 take run S's A/A (same session, an earlier run: a same-session floor, not a same-run one).

| Run / shape | A/A row | Half-width | Reach (far end) | Holm p | Pass |
|---|---|---|---|---|---|
| 13-ext-authz / fh6 | authz-off-A2 vs authz-off (13-ext-authz) | 0.90 | 1.00 | 1 | yes |
| 13-ext-authz / s | authz-off-A2 vs authz-off (13-ext-authz) | 0.60 | 0.85 | 1 | yes |
| 17-tracing / fh | base-A2 vs base (run-s) | 0.69 | 0.74 | 1 | yes |
| 17-tracing / s | base-A2 vs base (run-s) | 0.33 | 0.48 | 1 | yes |
| 18-access-log / fh | base-A2 vs base (run-s) | 0.69 | 0.74 | 1 | yes |
| 18-access-log / s | base-A2 vs base (run-s) | 0.33 | 0.48 | 1 | yes |
| 18w-access-log-w16 / s-w16 | log-off-A2 vs log-off (18w-access-log-w16) | 0.62 | 0.90 | 0.354 | yes |
| run-s / fh | base-A2 vs base (run-s) | 0.69 | 0.74 | 1 | yes |
| run-s / s | base-A2 vs base (run-s) | 0.33 | 0.48 | 1 | yes |

## Confirmatory rows (Holm over 16 rows, 16 with data)

| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| ext_authz HTTP | s | authz-http vs authz-off | +54.14% [+52.95, +55.34] | [+52.64, +55.65] | 0 | 16 | differs |
| ext_authz gRPC | s | authz-grpc vs authz-off | +80.00% [+78.79, +81.23] | [+78.37, +81.65] | 0 | 16 | differs |
| ext_authz HTTP | fh6 | authz-http vs authz-off | +102.37% [+100.93, +103.82] | [+100.49, +104.27] | 0 | 16 | differs |
| ext_authz gRPC | fh6 | authz-grpc vs authz-off | +145.79% [+143.93, +147.66] | [+143.43, +148.17] | 0 | 16 | differs |
| tracing 1% | s | trace-1 vs trace-off | +7.21% [+6.48, +7.95] | [+6.23, +8.20] | 6.61e-12 | 16 | differs |
| tracing 100% | s | trace-100 vs trace-off | +33.64% [+32.81, +34.48] | [+32.47, +34.82] | 0 | 16 | differs |
| tracing 1% | fh | trace-1 vs trace-off | +9.91% [+8.66, +11.16] | [+8.55, +11.28] | 9.26e-11 | 16 | differs |
| tracing 100% | fh | trace-100 vs trace-off | +57.17% [+55.84, +58.51] | [+55.56, +58.79] | 0 | 16 | differs |
| access log, text | s | log-text vs log-off | +3.68% [+3.33, +4.03] | [+2.92, +4.45] | 4.26e-13 | 18 | differs |
| access log, JSON | s | log-json vs log-off | +4.61% [+4.26, +4.97] | [+3.85, +5.39] | 8.88e-15 | 18 | differs |
| access log, text | fh | log-text vs log-off | +5.56% [+4.49, +6.64] | [+4.34, +6.79] | 1.17e-08 | 18 | differs |
| access log, JSON | fh | log-json vs log-off | +7.06% [+6.19, +7.93] | [+5.99, +8.14] | 1.21e-11 | 18 | differs |
| retry policy, never triggered | s | retry-on vs base | +1.34% [+1.01, +1.68] | [+0.60, +2.09] | 1.17e-08 | 30 | differs: about +1.3%, near the floor |
| idle timers off | s | idle-off vs base | -2.22% [-2.58, -1.86] | [-2.96, -1.48] | 2.76e-12 | 30 | differs |
| tcmalloc per-CPU caches | s | percpu-on vs base | -0.54% [-0.85, -0.22] | [-1.26, +0.19] | 0.00337 | 30 | within the A/A spread (< 1%) |
| tcmalloc per-CPU caches | fh | percpu-on vs base | +0.66% [-0.06, +1.37] | [-0.30, +1.62] | 0.0699 | 30 | within the A/A spread (< 1%) |

## Secondary rows (Holm over 7 rows, 7 with data)

| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| tracing 10% | s | trace-10 vs trace-off | +9.58% [+8.88, +10.28] | [+8.61, +10.55] | 3.6e-14 | 16 | differs |
| tracing 10% | fh | trace-10 vs trace-off | +15.61% [+14.74, +16.49] | [+14.50, +16.73] | 0 | 16 | differs |
| idle timers off | fh | idle-off vs base | -3.75% [-4.47, -3.02] | [-4.69, -2.79] | 1.51e-10 | 30 | differs |
| A/A | s | base-A2 vs base | +0.15% [-0.18, +0.48] | [-0.59, +0.89] | 1 | 30 | within the A/A spread (< 1%) |
| A/A | fh | base-A2 vs base | -0.05% [-0.74, +0.64] | [-0.98, +0.89] | 1 | 30 | within the A/A spread (< 1%) |
| A/A | s | authz-off-A2 vs authz-off | -0.25% [-0.84, +0.35] | [-1.11, +0.61] | 1 | 16 | within the A/A spread (< 1%) |
| A/A | fh6 | authz-off-A2 vs authz-off | -0.10% [-1.00, +0.80] | [-1.16, +0.97] | 1 | 16 | within the A/A spread (< 1%) |

## Row 18w, 16 workers (Holm over 2 rows, 2 with data)

| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| access log, text, 16 workers | s-w16 | log-text vs log-off | +3.32% [+2.72, +3.92] | [+2.44, +4.21] | 4.84e-09 | 16 | differs |
| access log, JSON, 16 workers | s-w16 | log-json vs log-off | +3.79% [+3.37, +4.21] | [+3.00, +4.58] | 9.15e-12 | 16 | differs |

## R17 and R18

"No measurable cost" only when the widened upper end is under 1.5% and the shape's A/A is valid (review S8).

| Item | Row | Shape | Verdict | Closes as |
|---|---|---|---|---|
| R17 OTel 1% | tracing 1% | s | differs | costs about +7.2% |
| R17 OTel 1% | tracing 1% | fh | differs | costs about +9.9% |
| R17 access log text | access log, text | s | differs | costs about +3.7% |
| R17 access log JSON | access log, JSON | s | differs | costs about +4.6% |
| R17 access log text | access log, text | fh | differs | costs about +5.6% |
| R17 access log JSON | access log, JSON | fh | differs | costs about +7.1% |
| R17 retries | retry policy, never triggered | s | differs: about +1.3%, near the floor | costs about +1.3% |
| R17 idle timeout | idle timers off | s | differs | costs about -2.2% |
| R18 | tcmalloc per-CPU caches | s | within the A/A spread (< 1%) | no measurable cost (widened upper end +0.19%) |
| R18 | tcmalloc per-CPU caches | fh | within the A/A spread (< 1%) | not resolved; at most +1.6% |
| R17 idle timeout | idle timers off | fh | differs | costs about -3.7% |
| R17 access log at W16 | access log, text, 16 workers | s-w16 | differs | costs about +3.3% |
| R17 access log at W16 | access log, JSON, 16 workers | s-w16 | differs | costs about +3.8% |

## Replication against the published first sessions

| Row | Shape | First session | z | Same sign | Own verdict a finding | Wording |
|---|---|---|---|---|---|---|
| ext_authz HTTP | s | row 6 +54.02% [+52.88, +55.16] | 0.12 | True | True | second session: +54.14% (first, row 6: +54.02%) |
| ext_authz HTTP | s | F2 +54.52% [+53.37, +55.67] | -0.35 | True | True | second session: +54.14% (first, F2: +54.52%) |
| ext_authz gRPC | s | F2 +80.68% [+79.67, +81.69] | -0.59 | True | True | second session: +80.00% (first, F2: +80.68%) |
| tracing 1% | s | row 4 +7.00% [+6.47, +7.53] | 0.32 | True | True | second session: +7.21% (first, row 4: +7.00%) |
| tracing 100% | s | row 4 +33.77% [+33.20, +34.34] | -0.16 | True | True | second session: +33.64% (first, row 4: +33.77%) |
| access log, text | s | row 5 +3.61% [+2.74, +4.49] | 0.11 | True | True | second session: +3.68% (first, row 5: +3.61%) |
| access log, JSON | s | row 5 +4.52% [+3.82, +5.21] | 0.16 | True | True | second session: +4.61% (first, row 5: +4.52%) |
| retry policy, never triggered | s | row 7 +1.50% [+0.85, +2.16] | -0.27 | True | True | second session: +1.34% (first, row 7: +1.50%) |
| tcmalloc per-CPU caches | s | row 9 -0.88% [-1.69, -0.07] | 0.56 | True | False | second session: -0.54% (first, row 9: -0.88%); held for review |
| tcmalloc per-CPU caches | fh | row 9 +1.58% [+0.32, +2.85] | -1.11 | True | False | second session: +0.66% (first, row 9: +1.58%); held for review |

## Absolute cost, user and kernel split, load (exploratory)

Kernel cycles are measured on loopback: they include part of the peer's receive work. Cycles per request are medians over the paired legs; the difference is the mean paired difference.

| Row | Shape | Ref -> arm total (k) | Added (k) | cycles:u effect | cycles:k effect | instructions:u effect | Busy ref -> arm |
|---|---|---|---|---|---|---|---|
| ext_authz HTTP | s | 525.9 -> 812.4 | +285.62 | +66.56% | +30.55% | +74.98% | 31.3% -> 47.3% |
| ext_authz gRPC | s | 525.9 -> 947.4 | +422.06 | +100.88% | +40.34% | +106.76% | 31.3% -> 54.8% |
| ext_authz HTTP | fh6 | 301.1 -> 606.5 | +306.69 | +116.62% | +68.37% | +73.88% | 20.8% -> 40.8% |
| ext_authz gRPC | fh6 | 301.1 -> 738.8 | +436.79 | +167.98% | +92.84% | +105.94% | 20.8% -> 49.1% |
| tracing 1% | s | 524.8 -> 564.5 | +37.90 | +10.41% | +1.11% | +13.86% | 31.2% -> 33.2% |
| tracing 100% | s | 524.8 -> 702.6 | +176.81 | +44.76% | +12.46% | +92.37% | 31.2% -> 41.0% |
| tracing 1% | fh | 280.9 -> 309.7 | +27.81 | +13.55% | +1.12% | +9.80% | 25.5% -> 27.8% |
| tracing 100% | fh | 280.9 -> 441.3 | +160.45 | +71.32% | +23.07% | +80.27% | 25.5% -> 39.4% |
| access log, text | s | 526.0 -> 545.4 | +19.37 | +5.07% | +1.02% | +4.04% | 31.2% -> 32.3% |
| access log, JSON | s | 526.0 -> 550.9 | +24.28 | +6.25% | +1.49% | +5.93% | 31.2% -> 32.5% |
| access log, text | fh | 281.1 -> 295.9 | +15.57 | +7.82% | +0.16% | +3.92% | 25.5% -> 26.8% |
| access log, JSON | fh | 281.1 -> 299.4 | +19.76 | +9.45% | +1.37% | +5.51% | 25.5% -> 27.1% |
| retry policy, never triggered | s | 525.9 -> 533.2 | +7.07 | +1.94% | +0.20% | +1.21% | 31.3% -> 31.6% |
| idle timers off | s | 525.9 -> 514.6 | -11.70 | -3.30% | -0.18% | -4.30% | 31.3% -> 30.6% |
| tcmalloc per-CPU caches | s | 525.9 -> 523.6 | -2.82 | -1.30% | +0.90% | -10.22% | 31.3% -> 31.1% |
| tcmalloc per-CPU caches | fh | 281.1 -> 283.4 | +1.84 | +0.74% | +0.47% | -19.20% | 25.5% -> 25.7% |
| tracing 10% | s | 524.8 -> 576.3 | +50.33 | +13.48% | +2.14% | +21.04% | 31.2% -> 33.9% |
| tracing 10% | fh | 280.9 -> 324.6 | +43.81 | +20.56% | +3.70% | +16.23% | 25.5% -> 29.2% |
| idle timers off | fh | 281.1 -> 271.0 | -10.50 | -5.24% | -0.17% | -3.49% | 25.5% -> 24.6% |
| A/A | s | 525.9 -> 527.3 | +0.77 | +0.11% | +0.21% | -0.00% | 31.3% -> 31.3% |
| A/A | fh | 281.1 -> 281.0 | -0.15 | +0.00% | -0.17% | -0.00% | 25.5% -> 25.5% |
| A/A | s | 525.9 -> 525.7 | -1.33 | -0.20% | -0.34% | -0.01% | 31.3% -> 31.2% |
| A/A | fh6 | 301.1 -> 299.9 | -0.31 | -0.07% | -0.19% | -0.00% | 20.8% -> 20.8% |
| access log, text, 16 workers | s-w16 | 553.8 -> 571.6 | +18.35 | +4.89% | +0.29% | +4.07% | 32.5% -> 33.5% |
| access log, JSON, 16 workers | s-w16 | 553.8 -> 574.3 | +20.95 | +5.54% | +0.41% | +5.98% | 32.5% -> 33.7% |

## Exploratory rows (interval only)

| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Pairs |
|---|---|---|---|---|---|
| gRPC against HTTP | s | authz-grpc vs authz-http | +16.78% [+16.02, +17.55] | [+15.73, +17.83] | 16 |
| gRPC against HTTP | fh6 | authz-grpc vs authz-http | +21.45% [+20.54, +22.37] | [+20.29, +22.63] | 16 |
| JSON against text | s | log-json vs log-text | +0.90% [+0.49, +1.32] | [+0.13, +1.68] | 18 |
| JSON against text | fh | log-json vs log-text | +1.42% [+0.51, +2.33] | [+0.34, +2.51] | 18 |
| retry policy on the direct response (near A/A: the policy sits on /s) | fh | retry-on vs base | -0.17% [-0.83, +0.50] | [-1.09, +0.76] | 30 |

- tracing 10% on s: line through 1% and 100% predicts +9.61%, measured +9.58% [+8.88, +10.28]
- tracing 10% on fh: line through 1% and 100% predicts +14.20%, measured +15.61% [+14.74, +16.49]
- authz-http added cycles per request: s +285.6k, fh6 +306.7k (approximate: the two shapes have different load gaps)
- authz-grpc added cycles per request: s +422.1k, fh6 +436.8k (approximate: the two shapes have different load gaps)
- log-text, added cycles per request: 4 workers +19.4k, 16 workers +18.4k; difference -1.0k (exploratory, unpaired across runs)
- log-json, added cycles per request: 4 workers +24.3k, 16 workers +20.9k; difference -3.3k (exploratory, unpaired across runs)

## Evidence and side services (current legs)

- 13-ext-authz fh6/authz-grpc: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 75.02}
- 13-ext-authz fh6/authz-http: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 49.45}
- 13-ext-authz fh6/authz-off: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 0.0}
- 13-ext-authz fh6/authz-off-A2: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 0.0}
- 13-ext-authz s/authz-grpc: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 133.53}
- 13-ext-authz s/authz-http: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 102.89}
- 13-ext-authz s/authz-off: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 63.12}
- 13-ext-authz s/authz-off-A2: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 62.16}
- 17-tracing fh/trace-1: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'collector': 0.78, 'origin': 0.0}
- 17-tracing fh/trace-10: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'collector': 7.56, 'origin': 0.0}
- 17-tracing fh/trace-100: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'collector': 66.49, 'origin': 0.0}
- 17-tracing fh/trace-off: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'collector': 0.0, 'origin': 0.0}
- 17-tracing s/trace-1: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'collector': 0.79, 'origin': 65.63}
- 17-tracing s/trace-10: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'collector': 7.74, 'origin': 65.15}
- 17-tracing s/trace-100: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'collector': 70.64, 'origin': 64.97}
- 17-tracing s/trace-off: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'collector': 0.0, 'origin': 62.67}
- 18-access-log fh/log-json: evidence ok on 18 of 18 legs; side-service CPU per request (us) {'origin': 0.0}
- 18-access-log fh/log-off: evidence ok on 18 of 18 legs; side-service CPU per request (us) {'origin': 0.0}
- 18-access-log fh/log-text: evidence ok on 18 of 18 legs; side-service CPU per request (us) {'origin': 0.0}
- 18-access-log s/log-json: evidence ok on 18 of 18 legs; side-service CPU per request (us) {'origin': 63.84}
- 18-access-log s/log-off: evidence ok on 18 of 18 legs; side-service CPU per request (us) {'origin': 63.74}
- 18-access-log s/log-text: evidence ok on 18 of 18 legs; side-service CPU per request (us) {'origin': 62.16}
- 18w-access-log-w16 s-w16/log-json: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 44.57}
- 18w-access-log-w16 s-w16/log-off: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 44.68}
- 18w-access-log-w16 s-w16/log-off-A2: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 43.76}
- 18w-access-log-w16 s-w16/log-text: evidence ok on 16 of 16 legs; side-service CPU per request (us) {'origin': 43.96}
- run-s fh/base: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 0.0}
- run-s fh/base-A2: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 0.0}
- run-s fh/idle-off: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 0.0}
- run-s fh/percpu-on: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 0.0}
- run-s fh/retry-on: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 0.0}
- run-s s/base: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 63.74}
- run-s s/base-A2: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 63.41}
- run-s s/idle-off: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 61.47}
- run-s s/percpu-on: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 61.67}
- run-s s/retry-on: evidence ok on 30 of 30 legs; side-service CPU per request (us) {'origin': 62.54}

