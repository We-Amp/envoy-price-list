> POST-HOC re-evaluation under the second revision of the gates (no new runs)

# Stats microbenchmarks (mt-micro-arm-vm (POST-HOC))

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
| bmModelOneRmwPerThreadSpaced | 1 | vm | -70.68% [-70.72, -70.65] | 2 (descriptive) |
| bmModelOneRmwPerThreadSpaced | 15 | vm | -70.68% [-70.70, -70.66] | 2 (descriptive) |
| bmModelOneRmwPerThreadSpaced | 4 | vm | -70.68% [-70.69, -70.67] | 2 (descriptive) |
| bmModelOneRmwShared | 1 | vm | -70.68% [-70.74, -70.61] | 2 (descriptive) |
| bmModelOneRmwShared | 15 | vm | -70.21% [-76.70, -61.91] | 2 (descriptive) |
| bmModelOneRmwShared | 4 | vm | -70.59% [-78.26, -60.22] | 2 (descriptive) |
| bmModelRelaxedPerThreadSpaced | 1 | vm | +0.00% [-0.06, +0.07] | 2 (descriptive) |
| bmModelRelaxedPerThreadSpaced | 15 | vm | +0.00% [-0.01, +0.01] | 2 (descriptive) |
| bmModelRelaxedPerThreadSpaced | 4 | vm | +0.00% [-0.02, +0.03] | 2 (descriptive) |
| bmModelRelaxedShared | 1 | vm | +0.02% [-0.33, +0.37] | 2 (descriptive) |
| bmModelRelaxedShared | 15 | vm | -1.53% [-8.21, +5.65] | 2 (descriptive) |
| bmModelRelaxedShared | 4 | vm | -0.32% [-28.01, +38.02] | 2 (descriptive) |
| bmModelRelaxedTestFlagPerThreadSpaced | 1 | vm | -35.21% [-35.73, -34.68] | 2 (descriptive) |
| bmModelRelaxedTestFlagPerThreadSpaced | 15 | vm | -35.19% [-35.57, -34.80] | 2 (descriptive) |
| bmModelRelaxedTestFlagPerThreadSpaced | 4 | vm | -35.18% [-35.58, -34.77] | 2 (descriptive) |
| bmModelRelaxedTestFlagShared | 1 | vm | -35.11% [-35.48, -34.74] | 2 (descriptive) |
| bmModelRelaxedTestFlagShared | 15 | vm | -41.81% [-55.64, -23.67] | 2 (descriptive) |
| bmModelRelaxedTestFlagShared | 4 | vm | -40.87% [-53.97, -24.05] | 2 (descriptive) |
| bmModelShardedPerThreadSpaced | 1 | vm | -70.70% [-70.73, -70.66] | 2 (descriptive) |
| bmModelShardedPerThreadSpaced | 15 | vm | -70.68% [-70.76, -70.61] | 2 (descriptive) |
| bmModelShardedPerThreadSpaced | 4 | vm | -70.69% [-70.71, -70.67] | 2 (descriptive) |
| bmModelShardedShared | 1 | vm | -70.69% [-70.78, -70.61] | 2 (descriptive) |
| bmModelShardedShared | 15 | vm | -99.89% [-99.90, -99.87] | 2 (descriptive) |
| bmModelShardedShared | 4 | vm | -98.57% [-98.83, -98.24] | 2 (descriptive) |

## Shared against per-thread spaced, per arm (H1; pooled cycles/op)

| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |
|---|---|---|---|---|---|
| bmCounterIncShared | 1 | vm | fix | 0.99x [0.99, 0.99] | 3 |
| bmCounterIncShared | 1 | vm | fix-relaxed-p1 | 1.00x [0.99, 1.02] | 3 |
| bmCounterIncShared | 15 | vm | fix | 244.01x [241.46, 246.58] | 3 |
| bmCounterIncShared | 15 | vm | fix-relaxed-p1 | 232.00x [231.24, 232.76] | 3 |
| bmCounterIncShared | 4 | vm | fix | 20.57x [20.39, 20.75] | 3 |
| bmCounterIncShared | 4 | vm | fix-relaxed-p1 | 19.55x [19.23, 19.88] | 3 |
| bmGaugeSetShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 3 |
| bmGaugeSetShared | 1 | vm | fix-relaxed-p1 | 1.00x [1.00, 1.00] | 3 |
| bmGaugeSetShared | 15 | vm | fix | 182.88x [76.76, 435.75] | 3 |
| bmGaugeSetShared | 15 | vm | fix-relaxed-p1 | 17.77x [17.22, 18.34] | 3 |
| bmGaugeSetShared | 4 | vm | fix | 19.77x [19.63, 19.92] | 3 |
| bmGaugeSetShared | 4 | vm | fix-relaxed-p1 | 3.02x [2.82, 3.24] | 3 |
| bmModelCurrentShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 2 |
| bmModelCurrentShared | 15 | vm | fix | 255.46x [225.08, 289.93] | 2 |
| bmModelCurrentShared | 4 | vm | fix | 20.46x [16.70, 25.07] | 2 |
| bmModelOneRmwShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 2 |
| bmModelOneRmwShared | 15 | vm | fix | 259.52x [230.51, 292.18] | 2 |
| bmModelOneRmwShared | 4 | vm | fix | 20.52x [18.58, 22.67] | 2 |
| bmModelRelaxedShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 2 |
| bmModelRelaxedShared | 15 | vm | fix | 251.55x [237.77, 266.14] | 2 |
| bmModelRelaxedShared | 4 | vm | fix | 20.40x [18.04, 23.06] | 2 |
| bmModelRelaxedTestFlagShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 2 |
| bmModelRelaxedTestFlagShared | 15 | vm | fix | 229.36x [197.26, 266.67] | 2 |
| bmModelRelaxedTestFlagShared | 4 | vm | fix | 18.67x [17.69, 19.69] | 2 |
| bmModelShardedShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 2 |
| bmModelShardedShared | 15 | vm | fix | 1.00x [1.00, 1.00] | 2 |
| bmModelShardedShared | 4 | vm | fix | 1.00x [1.00, 1.00] | 2 |
| bmPrimitiveCounterIncShared | 1 | vm | fix | 0.99x [0.97, 1.02] | 3 |
| bmPrimitiveCounterIncShared | 1 | vm | fix-relaxed-p1 | 1.01x [0.96, 1.05] | 3 |
| bmPrimitiveCounterIncShared | 15 | vm | fix | 256.28x [245.33, 267.71] | 3 |
| bmPrimitiveCounterIncShared | 15 | vm | fix-relaxed-p1 | 253.55x [237.81, 270.33] | 3 |
| bmPrimitiveCounterIncShared | 4 | vm | fix | 21.01x [20.42, 21.61] | 3 |
| bmPrimitiveCounterIncShared | 4 | vm | fix-relaxed-p1 | 20.92x [19.25, 22.73] | 3 |

## Spacing of the spaced cases (min_distance_bytes, the smallest seen over rounds)

| Benchmark | Placement | Arm | Bytes |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed-p1 | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 384 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 640 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 640 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:15 | vm | fix | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed-p1 | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix | 384 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 768 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 448 |
| bmHistogramRecordOnly/15/manual_time | vm | fix | 352 |
| bmHistogramRecordOnly/15/manual_time | vm | fix-relaxed | 352 |
| bmHistogramRecordOnly/15/manual_time | vm | fix-relaxed-p1 | 352 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed-p1 | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 256 |

## Fairness (slowest thread's operations over the fastest's; a result, not a gate)

| Benchmark | Placement | Arm | Median over rounds |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix | 0.996 |
| bmCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed | 0.987 |
| bmCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed-p1 | 0.970 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.997 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 0.990 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.984 |
| bmCounterIncShared/manual_time/threads:15 | vm | fix | 0.188 |
| bmCounterIncShared/manual_time/threads:15 | vm | fix-relaxed | 0.208 |
| bmCounterIncShared/manual_time/threads:15 | vm | fix-relaxed-p1 | 0.200 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix | 0.913 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed | 0.779 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.844 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:15 | vm | fix | 0.998 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed | 0.993 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed-p1 | 0.987 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 0.999 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 1.000 |
| bmGaugeSetShared/manual_time/threads:15 | vm | fix | 0.262 |
| bmGaugeSetShared/manual_time/threads:15 | vm | fix-relaxed | 0.267 |
| bmGaugeSetShared/manual_time/threads:15 | vm | fix-relaxed-p1 | 0.751 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix | 0.463 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed | 0.500 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.906 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:15 | vm | fix | 0.999 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmModelCurrentShared/manual_time/threads:15 | vm | fix | 0.738 |
| bmModelCurrentShared/manual_time/threads:4 | vm | fix | 0.756 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:15 | vm | fix | 0.998 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmModelOneRmwShared/manual_time/threads:15 | vm | fix | 0.650 |
| bmModelOneRmwShared/manual_time/threads:4 | vm | fix | 0.538 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:15 | vm | fix | 0.999 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmModelRelaxedShared/manual_time/threads:15 | vm | fix | 0.704 |
| bmModelRelaxedShared/manual_time/threads:4 | vm | fix | 0.671 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:15 | vm | fix | 0.999 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:4 | vm | fix | 1.000 |
| bmModelRelaxedTestFlagShared/manual_time/threads:15 | vm | fix | 0.764 |
| bmModelRelaxedTestFlagShared/manual_time/threads:4 | vm | fix | 0.810 |
| bmModelShardedPerThreadSpaced/manual_time/threads:15 | vm | fix | 0.998 |
| bmModelShardedPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmModelShardedShared/manual_time/threads:15 | vm | fix | 0.999 |
| bmModelShardedShared/manual_time/threads:4 | vm | fix | 0.999 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix | 0.960 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed | 0.934 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:15 | vm | fix-relaxed-p1 | 0.931 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.977 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 0.958 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.958 |
| bmPrimitiveCounterIncShared/manual_time/threads:15 | vm | fix | 0.294 |
| bmPrimitiveCounterIncShared/manual_time/threads:15 | vm | fix-relaxed | 0.670 |
| bmPrimitiveCounterIncShared/manual_time/threads:15 | vm | fix-relaxed-p1 | 0.672 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix | 0.954 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed | 0.776 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.769 |

