# Stats microbenchmarks (mt-micro-bench-x86_64)

Per round the median over the repetitions; paired log ratio over the rounds with a 95% t interval (negative: cheaper than the reference; for throughput, negative is slower). The headline is the pooled cost, cycles per operation over all threads together, with the pooled throughput beside it (ns per sample for the histogram); fairness is a result in its own table. Binaries unchanged during the run: True.

## Arm against arm

| Benchmark | Placement | Arm vs ref | Measure | Effect [95% CI] | Rounds | Ref |
|---|---|---|---|---|---|---|

## Model variants against Current (one build; pooled cycles/op)

| Benchmark | Threads | Placement | Effect on pooled cycles/op [95% CI] | Rounds |
|---|---|---|---|---|
| bmModelOneRmwPerThreadSpaced | 1 | one-socket | -72.76% [-72.76, -72.76] | 5 |
| bmModelOneRmwPerThreadSpaced | 19 | one-socket | -72.76% [-72.76, -72.76] | 5 |
| bmModelOneRmwPerThreadSpaced | 4 | one-socket | -72.76% [-72.76, -72.76] | 5 |
| bmModelOneRmwShared | 1 | one-socket | -72.76% [-72.76, -72.76] | 5 |
| bmModelOneRmwShared | 19 | one-socket | -66.86% [-66.87, -66.84] | 5 |
| bmModelOneRmwShared | 4 | one-socket | -66.90% [-67.03, -66.78] | 5 |
| bmModelRelaxedPerThreadSpaced | 1 | one-socket | +0.00% [-0.00, +0.00] | 5 |
| bmModelRelaxedPerThreadSpaced | 19 | one-socket | +0.00% [-0.00, +0.00] | 5 |
| bmModelRelaxedPerThreadSpaced | 4 | one-socket | +0.00% [-0.00, +0.00] | 5 |
| bmModelRelaxedShared | 1 | one-socket | +0.00% [-0.00, +0.00] | 5 |
| bmModelRelaxedShared | 19 | one-socket | -0.53% [-0.71, -0.35] | 5 |
| bmModelRelaxedShared | 4 | one-socket | -0.71% [-1.17, -0.25] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 1 | one-socket | -40.25% [-40.25, -40.25] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 19 | one-socket | -40.25% [-40.25, -40.25] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 4 | one-socket | -40.25% [-40.25, -40.25] | 5 |
| bmModelRelaxedTestFlagShared | 1 | one-socket | -40.25% [-40.25, -40.24] | 5 |
| bmModelRelaxedTestFlagShared | 19 | one-socket | -3.99% [-6.15, -1.78] | 5 |
| bmModelRelaxedTestFlagShared | 4 | one-socket | -5.73% [-8.58, -2.79] | 5 |
| bmModelShardedPerThreadSpaced | 1 | one-socket | -72.76% [-72.76, -72.76] | 5 |
| bmModelShardedPerThreadSpaced | 19 | one-socket | -72.75% [-72.76, -72.75] | 5 |
| bmModelShardedPerThreadSpaced | 4 | one-socket | -72.75% [-72.75, -72.75] | 5 |
| bmModelShardedShared | 1 | one-socket | -72.76% [-72.76, -72.76] | 5 |
| bmModelShardedShared | 19 | one-socket | -99.39% [-99.40, -99.37] | 5 |
| bmModelShardedShared | 4 | one-socket | -97.06% [-97.31, -96.79] | 5 |

## Shared against per-thread spaced, per arm (H1; pooled cycles/op)

| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |
|---|---|---|---|---|---|
| bmModelCurrentShared | 1 | one-socket | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelCurrentShared | 19 | one-socket | fix | 44.37x [43.38, 45.38] | 5 |
| bmModelCurrentShared | 4 | one-socket | fix | 9.28x [8.49, 10.13] | 5 |
| bmModelOneRmwShared | 1 | one-socket | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelOneRmwShared | 19 | one-socket | fix | 53.99x [52.80, 55.20] | 5 |
| bmModelOneRmwShared | 4 | one-socket | fix | 11.27x [10.29, 12.35] | 5 |
| bmModelRelaxedShared | 1 | one-socket | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelRelaxedShared | 19 | one-socket | fix | 44.13x [43.14, 45.15] | 5 |
| bmModelRelaxedShared | 4 | one-socket | fix | 9.21x [8.40, 10.10] | 5 |
| bmModelRelaxedTestFlagShared | 1 | one-socket | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelRelaxedTestFlagShared | 19 | one-socket | fix | 71.29x [69.08, 73.58] | 5 |
| bmModelRelaxedTestFlagShared | 4 | one-socket | fix | 14.63x [13.76, 15.56] | 5 |
| bmModelShardedShared | 1 | one-socket | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 19 | one-socket | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 4 | one-socket | fix | 1.00x [1.00, 1.00] | 5 |

## Fairness (slowest thread's operations over the fastest's; a result, not a gate)

| Benchmark | Placement | Arm | Median over rounds |
|---|---|---|---|
| bmModelCurrentPerThreadSpaced/manual_time/threads:19 | one-socket | fix | 1.000 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:4 | one-socket | fix | 1.000 |
| bmModelCurrentShared/manual_time/threads:19 | one-socket | fix | 0.398 |
| bmModelCurrentShared/manual_time/threads:4 | one-socket | fix | 0.876 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:19 | one-socket | fix | 1.000 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:4 | one-socket | fix | 1.000 |
| bmModelOneRmwShared/manual_time/threads:19 | one-socket | fix | 0.424 |
| bmModelOneRmwShared/manual_time/threads:4 | one-socket | fix | 0.804 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:19 | one-socket | fix | 1.000 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:4 | one-socket | fix | 1.000 |
| bmModelRelaxedShared/manual_time/threads:19 | one-socket | fix | 0.417 |
| bmModelRelaxedShared/manual_time/threads:4 | one-socket | fix | 0.788 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:19 | one-socket | fix | 1.000 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:4 | one-socket | fix | 1.000 |
| bmModelRelaxedTestFlagShared/manual_time/threads:19 | one-socket | fix | 0.533 |
| bmModelRelaxedTestFlagShared/manual_time/threads:4 | one-socket | fix | 0.944 |
| bmModelShardedPerThreadSpaced/manual_time/threads:19 | one-socket | fix | 0.999 |
| bmModelShardedPerThreadSpaced/manual_time/threads:4 | one-socket | fix | 0.999 |
| bmModelShardedShared/manual_time/threads:19 | one-socket | fix | 0.997 |
| bmModelShardedShared/manual_time/threads:4 | one-socket | fix | 1.000 |

