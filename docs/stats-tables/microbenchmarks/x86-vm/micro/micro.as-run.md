# Stats microbenchmarks (mt-micro-x86-vm)

Per round the median over the repetitions; paired log ratio over the rounds with a 95% t interval (negative: faster or cheaper than the reference). Cycles per operation are the primary measure (ns per sample for the histogram); ns per operation beside them. Binaries unchanged during the run: True.

## Arm against arm

| Benchmark | Placement | Arm vs ref | Measure | Effect [95% CI] | Rounds | Ref |
|---|---|---|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | cycles_per_op | +0.01% [-0.05, +0.06] | 5 | 60.49 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | ns_per_op | +0.13% [-17.27, +21.19] | 5 | 16.49 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | cycles_per_op | -0.93% [-2.70, +0.88] | 5 | 61.88 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | ns_per_op | -4.47% [-13.99, +6.11] | 5 | 18.35 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | cycles_per_op | -0.12% [-0.42, +0.18] | 5 | 60.51 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | ns_per_op | -2.06% [-11.44, +8.31] | 5 | 18.13 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | cycles_per_op | +0.00% [-0.04, +0.05] | 5 | 61.49 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | ns_per_op | -1.34% [-18.32, +19.17] | 5 | 17.10 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | cycles_per_op | +0.67% [-7.75, +9.85] | 5 | 906.00 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | ns_per_op | -0.71% [-18.82, +21.43] | 5 | 273.12 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed vs fix | cycles_per_op | -0.45% [-4.86, +4.18] | 5 | 1664.36 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed vs fix | ns_per_op | -0.10% [-16.09, +18.94] | 5 | 500.84 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | cycles_per_op | -38.63% [-38.64, -38.61] | 5 | 41.47 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | ns_per_op | -41.64% [-46.92, -35.84] | 5 | 12.85 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | cycles_per_op | -38.63% [-38.65, -38.61] | 5 | 41.48 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | ns_per_op | -40.68% [-46.30, -34.48] | 5 | 13.22 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | cycles_per_op | -38.63% [-38.64, -38.62] | 5 | 41.48 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | ns_per_op | -41.47% [-44.05, -38.77] | 5 | 13.36 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed vs fix | cycles_per_op | -36.01% [-43.03, -28.11] | 5 | 41.47 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed vs fix | ns_per_op | -39.71% [-45.33, -33.52] | 5 | 12.85 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed vs fix | cycles_per_op | -35.43% [-37.88, -32.88] | 5 | 636.14 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed vs fix | ns_per_op | -37.07% [-39.92, -34.09] | 5 | 192.75 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed vs fix | cycles_per_op | -32.48% [-36.41, -28.30] | 5 | 1105.43 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed vs fix | ns_per_op | -34.20% [-40.92, -26.72] | 5 | 356.78 |
| bmHistogramRecordOnly/1/manual_time | vm | fix-relaxed vs fix | ns_per_sample | -3.80% [-8.34, +0.97] | 5 | 43.09 |
| bmHistogramRecordOnly/7/manual_time | vm | fix-relaxed vs fix | ns_per_sample | -18.87% [-47.33, +24.98] | 5 | 47.39 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | cycles_per_op | -0.03% [-0.06, +0.00] | 5 | 38.47 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | ns_per_op | -10.45% [-18.85, -1.18] | 5 | 11.84 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | cycles_per_op | -0.03% [-0.06, +0.01] | 5 | 38.47 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | ns_per_op | -8.21% [-16.39, +0.76] | 5 | 12.27 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | cycles_per_op | +0.43% [-1.91, +2.82] | 5 | 38.48 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | ns_per_op | -6.50% [-14.23, +1.92] | 5 | 12.41 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | cycles_per_op | -0.02% [-0.04, +0.01] | 5 | 39.48 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | ns_per_op | -7.69% [-15.55, +0.90] | 5 | 12.25 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | cycles_per_op | +1.58% [-7.41, +11.45] | 5 | 451.37 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | ns_per_op | -2.96% [-10.41, +5.11] | 5 | 141.38 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed vs fix | cycles_per_op | +0.96% [-5.77, +8.16] | 5 | 810.18 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed vs fix | ns_per_op | -0.56% [-6.61, +5.89] | 5 | 265.58 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -28.13% [-28.16, -28.10] | 5 | 60.50 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -26.87% [-33.36, -19.76] | 5 | 16.66 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -28.44% [-28.94, -27.94] | 5 | 60.57 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -25.26% [-30.49, -19.64] | 5 | 17.37 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -28.13% [-28.15, -28.10] | 5 | 60.50 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -26.62% [-30.14, -22.92] | 5 | 17.76 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -29.30% [-29.32, -29.27] | 5 | 61.49 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -25.98% [-36.07, -14.30] | 5 | 17.12 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -26.28% [-30.17, -22.18] | 5 | 888.31 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -24.10% [-34.70, -11.78] | 5 | 267.34 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -27.46% [-30.49, -24.30] | 5 | 1634.95 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -25.60% [-35.16, -14.62] | 5 | 498.73 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -59.26% [-59.58, -58.93] | 5 | 25.45 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -58.88% [-60.91, -56.74] | 5 | 7.00 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -59.76% [-59.93, -59.59] | 5 | 25.46 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -60.57% [-63.35, -57.59] | 5 | 7.41 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -59.82% [-59.99, -59.65] | 5 | 25.46 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -60.38% [-62.25, -58.42] | 5 | 7.48 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -62.06% [-66.42, -57.13] | 5 | 25.45 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -61.34% [-66.43, -55.48] | 5 | 7.17 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -79.39% [-80.19, -78.57] | 5 | 408.47 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -79.90% [-82.60, -76.78] | 5 | 122.16 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -79.13% [-80.17, -78.03] | 5 | 726.36 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -79.00% [-80.98, -76.81] | 5 | 225.07 |
| bmHistogramRecordOnly/1/manual_time | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_sample | -2.55% [-8.72, +4.04] | 5 | 42.16 |
| bmHistogramRecordOnly/7/manual_time | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_sample | +1.45% [-10.08, +14.45] | 5 | 45.33 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | +0.01% [-0.01, +0.02] | 5 | 38.46 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | +2.36% [-0.60, +5.40] | 5 | 10.13 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | +0.01% [-0.01, +0.03] | 5 | 38.46 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | +0.48% [-4.01, +5.19] | 5 | 10.65 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -0.98% [-2.93, +1.00] | 5 | 38.47 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -0.62% [-7.29, +6.54] | 5 | 11.42 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | +0.00% [-0.01, +0.02] | 5 | 39.47 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | +0.77% [-1.81, +3.43] | 5 | 10.51 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | +0.46% [-6.86, +8.36] | 5 | 461.56 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | +0.98% [-6.83, +9.44] | 5 | 131.01 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | cycles_per_op | -1.54% [-8.36, +5.79] | 5 | 806.77 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_op | -3.62% [-13.83, +7.78] | 5 | 256.86 |

## Model variants against Current (one build)

| Benchmark | Threads | Placement | Effect on cycles/op [95% CI] | Rounds |
|---|---|---|---|---|
| bmModelOneRmwPerThreadSpaced | 1 | vm | -66.05% [-66.06, -66.05] | 5 |
| bmModelOneRmwPerThreadSpaced | 4 | vm | -66.05% [-66.06, -66.05] | 5 |
| bmModelOneRmwPerThreadSpaced | 7 | vm | -66.06% [-66.07, -66.05] | 5 |
| bmModelOneRmwShared | 1 | vm | -66.06% [-66.07, -66.05] | 5 |
| bmModelOneRmwShared | 4 | vm | -66.93% [-67.36, -66.50] | 5 |
| bmModelOneRmwShared | 7 | vm | -67.07% [-67.36, -66.78] | 5 |
| bmModelRelaxedPerThreadSpaced | 1 | vm | +0.01% [-0.01, +0.03] | 5 |
| bmModelRelaxedPerThreadSpaced | 4 | vm | +0.01% [-0.00, +0.03] | 5 |
| bmModelRelaxedPerThreadSpaced | 7 | vm | -0.01% [-0.04, +0.03] | 5 |
| bmModelRelaxedShared | 1 | vm | +0.02% [-0.01, +0.04] | 5 |
| bmModelRelaxedShared | 4 | vm | +0.01% [-0.68, +0.71] | 5 |
| bmModelRelaxedShared | 7 | vm | +0.27% [-1.17, +1.73] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 1 | vm | -33.02% [-33.04, -33.00] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 4 | vm | -33.02% [-33.04, -33.00] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 7 | vm | -33.03% [-33.06, -33.00] | 5 |
| bmModelRelaxedTestFlagShared | 1 | vm | -33.02% [-33.04, -33.01] | 5 |
| bmModelRelaxedTestFlagShared | 4 | vm | -10.32% [-14.11, -6.36] | 5 |
| bmModelRelaxedTestFlagShared | 7 | vm | -13.29% [-15.79, -10.72] | 5 |
| bmModelShardedPerThreadSpaced | 1 | vm | -66.05% [-66.06, -66.05] | 5 |
| bmModelShardedPerThreadSpaced | 4 | vm | -66.05% [-66.06, -66.05] | 5 |
| bmModelShardedPerThreadSpaced | 7 | vm | -66.06% [-66.07, -66.05] | 5 |
| bmModelShardedShared | 1 | vm | -66.06% [-66.06, -66.05] | 5 |
| bmModelShardedShared | 4 | vm | -97.25% [-97.40, -97.09] | 5 |
| bmModelShardedShared | 7 | vm | -98.42% [-98.51, -98.34] | 5 |

## Shared against per-thread spaced, per arm (H1; cycles/op)

| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |
|---|---|---|---|---|---|
| bmCounterIncShared | 1 | vm | fix | 1.02x [1.02, 1.02] | 5 |
| bmCounterIncShared | 1 | vm | fix-relaxed | 1.02x [1.02, 1.02] | 5 |
| bmCounterIncShared | 1 | vm | fix-relaxed-p1 | 1.00x [1.00, 1.00] | 5 |
| bmCounterIncShared | 4 | vm | fix | 14.76x [14.13, 15.41] | 5 |
| bmCounterIncShared | 4 | vm | fix-relaxed | 15.00x [13.89, 16.19] | 5 |
| bmCounterIncShared | 4 | vm | fix-relaxed-p1 | 15.45x [15.09, 15.82] | 5 |
| bmCounterIncShared | 7 | vm | fix | 26.95x [25.64, 28.34] | 5 |
| bmCounterIncShared | 7 | vm | fix-relaxed | 26.86x [25.81, 27.97] | 5 |
| bmCounterIncShared | 7 | vm | fix-relaxed-p1 | 27.11x [26.74, 27.50] | 5 |
| bmGaugeSetShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmGaugeSetShared | 1 | vm | fix-relaxed | 1.04x [0.93, 1.17] | 5 |
| bmGaugeSetShared | 1 | vm | fix-relaxed-p1 | 0.97x [0.96, 0.98] | 5 |
| bmGaugeSetShared | 4 | vm | fix | 15.29x [14.70, 15.91] | 5 |
| bmGaugeSetShared | 4 | vm | fix-relaxed | 16.09x [15.67, 16.52] | 5 |
| bmGaugeSetShared | 4 | vm | fix-relaxed-p1 | 8.24x [7.79, 8.72] | 5 |
| bmGaugeSetShared | 7 | vm | fix | 26.70x [26.43, 26.96] | 5 |
| bmGaugeSetShared | 7 | vm | fix-relaxed | 29.37x [27.46, 31.42] | 5 |
| bmGaugeSetShared | 7 | vm | fix-relaxed-p1 | 15.26x [14.44, 16.12] | 5 |
| bmModelCurrentShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelCurrentShared | 4 | vm | fix | 12.35x [11.68, 13.06] | 5 |
| bmModelCurrentShared | 7 | vm | fix | 21.54x [20.43, 22.70] | 5 |
| bmModelOneRmwShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelOneRmwShared | 4 | vm | fix | 12.03x [11.34, 12.77] | 5 |
| bmModelOneRmwShared | 7 | vm | fix | 20.89x [19.81, 22.03] | 5 |
| bmModelRelaxedShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelRelaxedShared | 4 | vm | fix | 12.35x [11.73, 13.00] | 5 |
| bmModelRelaxedShared | 7 | vm | fix | 21.60x [20.76, 22.47] | 5 |
| bmModelRelaxedTestFlagShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelRelaxedTestFlagShared | 4 | vm | fix | 16.53x [15.80, 17.31] | 5 |
| bmModelRelaxedTestFlagShared | 7 | vm | fix | 27.89x [26.56, 29.28] | 5 |
| bmModelShardedShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 4 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 7 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmPrimitiveCounterIncShared | 1 | vm | fix | 1.03x [1.03, 1.03] | 5 |
| bmPrimitiveCounterIncShared | 1 | vm | fix-relaxed | 1.03x [1.03, 1.03] | 5 |
| bmPrimitiveCounterIncShared | 1 | vm | fix-relaxed-p1 | 1.03x [1.03, 1.03] | 5 |
| bmPrimitiveCounterIncShared | 4 | vm | fix | 11.95x [11.08, 12.89] | 5 |
| bmPrimitiveCounterIncShared | 4 | vm | fix-relaxed | 12.14x [11.49, 12.83] | 5 |
| bmPrimitiveCounterIncShared | 4 | vm | fix-relaxed-p1 | 12.20x [11.81, 12.60] | 5 |
| bmPrimitiveCounterIncShared | 7 | vm | fix | 21.22x [19.91, 22.61] | 5 |
| bmPrimitiveCounterIncShared | 7 | vm | fix-relaxed | 21.33x [19.73, 23.06] | 5 |
| bmPrimitiveCounterIncShared | 7 | vm | fix-relaxed-p1 | 21.21x [20.71, 21.72] | 5 |

## Spacing of the spaced cases (min_distance_bytes, the smallest seen over rounds)

| Benchmark | Placement | Arm | Bytes |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 320 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 320 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 320 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 320 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 320 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 | 256 |
| bmHistogramRecordOnly/7/manual_time | vm | fix | 352 |
| bmHistogramRecordOnly/7/manual_time | vm | fix-relaxed | 352 |
| bmHistogramRecordOnly/7/manual_time | vm | fix-relaxed-p1 | 352 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 | 256 |

## Fairness (slowest thread's operations over the fastest's; a result, not a gate)

| Benchmark | Placement | Arm | Median over rounds |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.910 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 0.996 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 1.000 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix | 0.999 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed | 1.000 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 | 0.999 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix | 0.902 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed | 0.891 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.899 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix | 0.866 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed | 0.859 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 | 0.846 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix | 1.000 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 1.000 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.968 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix | 0.999 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed | 0.999 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 | 0.962 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix | 0.930 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed | 0.906 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.902 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix | 0.837 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed | 0.731 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed-p1 | 0.739 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:4 | vm | fix | 1.000 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:7 | vm | fix | 0.999 |
| bmModelCurrentShared/manual_time/threads:4 | vm | fix | 0.786 |
| bmModelCurrentShared/manual_time/threads:7 | vm | fix | 0.669 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:7 | vm | fix | 0.999 |
| bmModelOneRmwShared/manual_time/threads:4 | vm | fix | 0.815 |
| bmModelOneRmwShared/manual_time/threads:7 | vm | fix | 0.687 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:4 | vm | fix | 1.000 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:7 | vm | fix | 0.999 |
| bmModelRelaxedShared/manual_time/threads:4 | vm | fix | 0.804 |
| bmModelRelaxedShared/manual_time/threads:7 | vm | fix | 0.748 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:7 | vm | fix | 1.000 |
| bmModelRelaxedTestFlagShared/manual_time/threads:4 | vm | fix | 0.880 |
| bmModelRelaxedTestFlagShared/manual_time/threads:7 | vm | fix | 0.873 |
| bmModelShardedPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmModelShardedPerThreadSpaced/manual_time/threads:7 | vm | fix | 0.999 |
| bmModelShardedShared/manual_time/threads:4 | vm | fix | 0.999 |
| bmModelShardedShared/manual_time/threads:7 | vm | fix | 0.999 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 1.000 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 1.000 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 1.000 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix | 0.999 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed | 0.999 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 | 0.999 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix | 0.846 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed | 0.662 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.868 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix | 0.534 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed | 0.485 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 | 0.555 |

