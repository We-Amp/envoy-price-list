# Stats microbenchmarks (mt-micro-arm-vm)

Per round the median over the repetitions; paired log ratio over the rounds with a 95% t interval (negative: cheaper than the reference; for throughput, negative is slower). The headline is the pooled cost, cycles per operation over all threads together, with the pooled throughput beside it (ns per sample for the histogram); fairness is a result in its own table. Binaries unchanged during the run: True.

## Arm against arm

| Benchmark | Placement | Arm vs ref | Measure | Effect [95% CI] | Rounds | Ref |
|---|---|---|---|---|---|---|
| bmHistogramRecordOnly/1/manual_time | vm | fix-relaxed vs fix | ns_per_sample | -0.71% [-0.95, -0.47] | 5 | 47.59 |
| bmHistogramRecordOnly/15/manual_time | vm | fix-relaxed vs fix | ns_per_sample | -30.30% [-52.84, +3.02] | 5 | 79.17 |
| bmHistogramRecordOnly/1/manual_time | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_sample | +0.16% [+0.06, +0.26] | 5 | 47.29 |
| bmHistogramRecordOnly/15/manual_time | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_sample | +5.94% [-10.87, +25.91] | 5 | 48.99 |

## Model variants against Current (one build; pooled cycles/op)

| Benchmark | Threads | Placement | Effect on pooled cycles/op [95% CI] | Rounds |
|---|---|---|---|---|

## Shared against per-thread spaced, per arm (H1; pooled cycles/op)

| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |
|---|---|---|---|---|---|

## Spacing of the spaced cases (min_distance_bytes, the smallest seen over rounds)

| Benchmark | Placement | Arm | Bytes |
|---|---|---|---|
| bmHistogramRecordOnly/15/manual_time | vm | fix | 352 |
| bmHistogramRecordOnly/15/manual_time | vm | fix-relaxed | 352 |
| bmHistogramRecordOnly/15/manual_time | vm | fix-relaxed-p1 | 352 |

## Fairness (slowest thread's operations over the fastest's; a result, not a gate)

| Benchmark | Placement | Arm | Median over rounds |
|---|---|---|---|

