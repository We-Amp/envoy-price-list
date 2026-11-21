# Stats microbenchmarks (mt-micro-arm-vm)

Per round the median over the repetitions; paired log ratio over the rounds with a 95% t interval (negative: cheaper than the reference; for throughput, negative is slower). The headline is the pooled cost, cycles per operation over all threads together, with the pooled throughput beside it (ns per sample for the histogram); fairness is a result in its own table. Binaries unchanged during the run: True.

## Arm against arm

| Benchmark | Placement | Arm vs ref | Measure | Effect [95% CI] | Rounds | Ref |
|---|---|---|---|---|---|---|

## Model variants against Current (one build; pooled cycles/op)

| Benchmark | Threads | Placement | Effect on pooled cycles/op [95% CI] | Rounds |
|---|---|---|---|---|
| bmModelOneRmwPerThreadSpaced | 1 | vm | -70.66% [-70.71, -70.61] | 5 |
| bmModelOneRmwPerThreadSpaced | 12 | vm | -70.68% [-70.68, -70.67] | 5 |
| bmModelOneRmwPerThreadSpaced | 4 | vm | -70.68% [-70.68, -70.68] | 5 |
| bmModelOneRmwShared | 1 | vm | -70.68% [-70.68, -70.67] | 5 |
| bmModelOneRmwShared | 12 | vm | -69.93% [-71.11, -68.70] | 5 |
| bmModelOneRmwShared | 4 | vm | -70.63% [-71.85, -69.36] | 5 |
| bmModelRelaxedPerThreadSpaced | 1 | vm | -0.03% [-0.04, -0.01] | 5 |
| bmModelRelaxedPerThreadSpaced | 12 | vm | -0.02% [-0.03, -0.00] | 5 |
| bmModelRelaxedPerThreadSpaced | 4 | vm | -0.02% [-0.04, -0.01] | 5 |
| bmModelRelaxedShared | 1 | vm | +0.00% [-0.02, +0.02] | 5 |
| bmModelRelaxedShared | 12 | vm | -0.43% [-3.82, +3.09] | 5 |
| bmModelRelaxedShared | 4 | vm | -0.42% [-4.89, +4.25] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 1 | vm | -35.19% [-35.21, -35.16] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 12 | vm | -35.20% [-35.31, -35.10] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 4 | vm | -35.17% [-35.19, -35.16] | 5 |
| bmModelRelaxedTestFlagShared | 1 | vm | -35.12% [-35.15, -35.09] | 5 |
| bmModelRelaxedTestFlagShared | 12 | vm | -41.10% [-43.29, -38.84] | 5 |
| bmModelRelaxedTestFlagShared | 4 | vm | -40.96% [-43.47, -38.33] | 5 |
| bmModelShardedPerThreadSpaced | 1 | vm | -70.69% [-70.70, -70.69] | 5 |
| bmModelShardedPerThreadSpaced | 12 | vm | -70.69% [-70.69, -70.69] | 5 |
| bmModelShardedPerThreadSpaced | 4 | vm | -70.69% [-70.70, -70.69] | 5 |
| bmModelShardedShared | 1 | vm | -70.70% [-70.70, -70.69] | 5 |
| bmModelShardedShared | 12 | vm | -99.83% [-99.83, -99.83] | 5 |
| bmModelShardedShared | 4 | vm | -98.62% [-98.66, -98.57] | 5 |

## Shared against per-thread spaced, per arm (H1; pooled cycles/op)

| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |
|---|---|---|---|---|---|
| bmCounterIncShared | 1 | vm | fix | 0.99x [0.99, 0.99] | 3 |
| bmCounterIncShared | 12 | vm | fix | 164.77x [152.63, 177.88] | 3 |
| bmCounterIncShared | 4 | vm | fix | 20.96x [20.32, 21.62] | 3 |
| bmGaugeSetShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 3 |
| bmGaugeSetShared | 12 | vm | fix | 142.89x [129.13, 158.11] | 3 |
| bmGaugeSetShared | 4 | vm | fix | 20.17x [19.95, 20.39] | 3 |
| bmModelCurrentShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelCurrentShared | 12 | vm | fix | 171.63x [167.87, 175.49] | 5 |
| bmModelCurrentShared | 4 | vm | fix | 21.21x [20.51, 21.94] | 5 |
| bmModelOneRmwShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelOneRmwShared | 12 | vm | fix | 176.01x [170.30, 181.91] | 5 |
| bmModelOneRmwShared | 4 | vm | fix | 21.25x [20.85, 21.65] | 5 |
| bmModelRelaxedShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelRelaxedShared | 12 | vm | fix | 170.93x [167.85, 174.06] | 5 |
| bmModelRelaxedShared | 4 | vm | fix | 21.13x [20.54, 21.74] | 5 |
| bmModelRelaxedTestFlagShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelRelaxedTestFlagShared | 12 | vm | fix | 156.01x [151.20, 160.97] | 5 |
| bmModelRelaxedTestFlagShared | 4 | vm | fix | 19.32x [18.89, 19.76] | 5 |
| bmModelShardedShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 12 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 4 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmPrimitiveCounterIncShared | 1 | vm | fix | 0.99x [0.95, 1.04] | 3 |
| bmPrimitiveCounterIncShared | 12 | vm | fix | 165.07x [158.52, 171.89] | 3 |
| bmPrimitiveCounterIncShared | 4 | vm | fix | 22.17x [20.07, 24.48] | 3 |

## Spacing of the spaced cases (min_distance_bytes, the smallest seen over rounds)

| Benchmark | Placement | Arm | Bytes |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 384 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix | 320 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 256 |

## Fairness (slowest thread's operations over the fastest's; a result, not a gate)

| Benchmark | Placement | Arm | Median over rounds |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.996 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.998 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix | 0.272 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix | 0.710 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.998 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix | 0.254 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix | 0.581 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.999 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:4 | vm | fix | 1.000 |
| bmModelCurrentShared/manual_time/threads:12 | vm | fix | 0.532 |
| bmModelCurrentShared/manual_time/threads:4 | vm | fix | 0.732 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.999 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:4 | vm | fix | 1.000 |
| bmModelOneRmwShared/manual_time/threads:12 | vm | fix | 0.693 |
| bmModelOneRmwShared/manual_time/threads:4 | vm | fix | 0.582 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.999 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmModelRelaxedShared/manual_time/threads:12 | vm | fix | 0.668 |
| bmModelRelaxedShared/manual_time/threads:4 | vm | fix | 0.746 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.999 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:4 | vm | fix | 1.000 |
| bmModelRelaxedTestFlagShared/manual_time/threads:12 | vm | fix | 0.704 |
| bmModelRelaxedTestFlagShared/manual_time/threads:4 | vm | fix | 0.769 |
| bmModelShardedPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.999 |
| bmModelShardedPerThreadSpaced/manual_time/threads:4 | vm | fix | 1.000 |
| bmModelShardedShared/manual_time/threads:12 | vm | fix | 0.999 |
| bmModelShardedShared/manual_time/threads:4 | vm | fix | 1.000 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.974 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.978 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix | 0.185 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix | 0.790 |

