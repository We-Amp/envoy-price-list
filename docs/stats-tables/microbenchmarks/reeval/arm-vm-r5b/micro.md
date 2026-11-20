> POST-HOC re-evaluation under the second revision of the gates (no new runs)

# Stats microbenchmarks (mt-micro-arm-vm (POST-HOC))

Per round the median over the repetitions; paired log ratio over the rounds with a 95% t interval (negative: cheaper than the reference; for throughput, negative is slower). The headline is the pooled cost, cycles per operation over all threads together, with the pooled throughput beside it (ns per sample for the histogram); fairness is a result in its own table. Binaries unchanged during the run: True.

## Arm against arm

| Benchmark | Placement | Arm vs ref | Measure | Effect [95% CI] | Rounds | Ref |
|---|---|---|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +0.12% [+0.06, +0.18] | 5 | 58.82 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | -0.13% [-0.21, -0.04] | 5 | 50634188.20 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -0.03% [-0.11, +0.05] | 5 | 58.84 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed vs fix | ops_per_sec | +0.05% [-0.03, +0.13] | 5 | 607481492.85 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -0.03% [-0.12, +0.06] | 5 | 58.83 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +0.03% [-0.06, +0.12] | 5 | 202569609.63 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -0.45% [-0.46, -0.45] | 5 | 58.27 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | +0.46% [+0.44, +0.47] | 5 | 51114704.62 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -1.83% [-5.96, +2.47] | 5 | 9681.84 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-relaxed vs fix | ops_per_sec | +1.80% [-2.48, +6.26] | 5 | 3689496.90 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +0.15% [-3.56, +4.00] | 5 | 1250.54 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | -0.18% [-3.93, +3.71] | 5 | 9526005.60 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -20.59% [-20.80, -20.37] | 5 | 42.35 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | +25.94% [+25.59, +26.28] | 5 | 70318180.13 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -20.65% [-20.73, -20.58] | 5 | 42.37 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed vs fix | ops_per_sec | +26.03% [+25.92, +26.14] | 5 | 843551773.11 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -20.70% [-20.75, -20.64] | 5 | 42.36 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +26.15% [+25.94, +26.35] | 5 | 281226418.79 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -20.38% [-20.43, -20.34] | 5 | 42.32 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | +25.70% [+25.57, +25.82] | 5 | 70354121.69 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -19.63% [-29.39, -8.51] | 5 | 6039.37 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-relaxed vs fix | ops_per_sec | +24.43% [+9.27, +41.70] | 5 | 5916222.59 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -19.49% [-21.73, -17.18] | 5 | 858.16 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +24.29% [+20.81, +27.86] | 5 | 13883930.43 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +0.43% [-3.35, +4.36] | 5 | 32.20 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | -0.47% [-4.19, +3.39] | 5 | 92523758.61 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +2.36% [+2.07, +2.66] | 5 | 32.39 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed vs fix | ops_per_sec | -2.34% [-2.62, -2.07] | 5 | 1103615712.56 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +1.04% [+0.33, +1.75] | 5 | 32.32 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | -1.04% [-1.70, -0.37] | 5 | 368730059.47 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +2.50% [-0.40, +5.48] | 5 | 32.29 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | -2.43% [-5.19, +0.41] | 5 | 92243202.49 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +0.45% [-1.57, +2.52] | 5 | 5360.08 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-relaxed vs fix | ops_per_sec | -0.47% [-2.49, +1.58] | 5 | 6665951.58 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -1.68% [-3.87, +0.57] | 5 | 710.03 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +1.72% [-0.55, +4.04] | 5 | 16779052.34 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -40.16% [-40.40, -39.92] | 4 (descriptive) | 58.90 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +67.09% [+66.48, +67.70] | 4 (descriptive) | 50565075.45 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -39.94% [-39.98, -39.89] | 4 (descriptive) | 58.81 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +66.48% [+66.32, +66.65] | 4 (descriptive) | 607822877.07 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -40.05% [-40.33, -39.76] | 4 (descriptive) | 58.82 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +66.79% [+66.00, +67.59] | 4 (descriptive) | 202610863.53 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -39.25% [-39.26, -39.24] | 4 (descriptive) | 58.00 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +64.59% [+64.53, +64.66] | 4 (descriptive) | 51352738.45 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -43.13% [-47.24, -38.70] | 4 (descriptive) | 9459.51 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +75.80% [+63.11, +89.47] | 4 (descriptive) | 3775712.08 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -42.88% [-44.51, -41.21] | 4 (descriptive) | 1241.16 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +75.04% [+70.06, +80.17] | 4 (descriptive) | 9603512.24 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -72.42% [-72.54, -72.31] | 4 (descriptive) | 33.64 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +262.42% [+260.66, +264.20] | 4 (descriptive) | 88535101.37 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -72.35% [-72.48, -72.21] | 4 (descriptive) | 33.62 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +261.62% [+259.89, +263.37] | 4 (descriptive) | 1062949158.73 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -72.31% [-72.47, -72.15] | 4 (descriptive) | 33.59 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +261.17% [+258.97, +263.40] | 4 (descriptive) | 354685793.55 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -72.36% [-72.38, -72.34] | 4 (descriptive) | 33.69 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +261.73% [+261.39, +262.08] | 4 (descriptive) | 88398339.58 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -97.14% [-97.37, -96.88] | 4 (descriptive) | 4586.48 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +3390.54% [+3108.44, +3697.43] | 4 (descriptive) | 7793662.75 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -95.70% [-95.87, -95.52] | 4 (descriptive) | 693.81 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +2223.40% [+2130.65, +2320.01] | 4 (descriptive) | 17175821.29 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -1.20% [-4.96, +2.71] | 4 (descriptive) | 32.37 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +1.27% [-2.52, +5.20] | 4 (descriptive) | 92008063.55 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -0.02% [-0.14, +0.10] | 4 (descriptive) | 33.14 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +0.07% [-0.19, +0.34] | 4 (descriptive) | 1078181602.28 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -0.07% [-1.07, +0.95] | 4 (descriptive) | 32.58 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +0.08% [-0.91, +1.08] | 4 (descriptive) | 365757776.79 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -1.42% [-6.34, +3.76] | 4 (descriptive) | 33.10 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +1.44% [-3.62, +6.78] | 4 (descriptive) | 89989051.11 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | +1.78% [-1.15, +4.80] | 4 (descriptive) | 5377.50 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | -1.71% [-4.58, +1.24] | 4 (descriptive) | 6641650.88 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | +3.92% [-5.86, +14.70] | 4 (descriptive) | 701.75 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | -3.76% [-12.82, +6.24] | 4 (descriptive) | 16983464.09 |

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
| bmCounterIncShared | 1 | vm | fix | 0.99x [0.99, 0.99] | 5 |
| bmCounterIncShared | 1 | vm | fix-relaxed | 0.98x [0.98, 0.98] | 5 |
| bmCounterIncShared | 1 | vm | fix-relaxed-p1 | 1.00x [1.00, 1.00] | 4 |
| bmCounterIncShared | 12 | vm | fix | 165.52x [160.60, 170.60] | 5 |
| bmCounterIncShared | 12 | vm | fix-relaxed | 162.55x [156.07, 169.29] | 5 |
| bmCounterIncShared | 12 | vm | fix-relaxed-p1 | 154.34x [149.94, 158.86] | 4 |
| bmCounterIncShared | 4 | vm | fix | 21.15x [20.75, 21.56] | 5 |
| bmCounterIncShared | 4 | vm | fix-relaxed | 21.19x [20.75, 21.64] | 5 |
| bmCounterIncShared | 4 | vm | fix-relaxed-p1 | 20.12x [19.95, 20.30] | 4 |
| bmGaugeSetShared | 1 | vm | fix | 1.00x [1.00, 1.00] | 5 |
| bmGaugeSetShared | 1 | vm | fix-relaxed | 1.00x [1.00, 1.00] | 5 |
| bmGaugeSetShared | 1 | vm | fix-relaxed-p1 | 1.00x [1.00, 1.00] | 4 |
| bmGaugeSetShared | 12 | vm | fix | 136.62x [120.21, 155.27] | 5 |
| bmGaugeSetShared | 12 | vm | fix-relaxed | 138.39x [127.97, 149.65] | 5 |
| bmGaugeSetShared | 12 | vm | fix-relaxed-p1 | 14.05x [13.90, 14.20] | 4 |
| bmGaugeSetShared | 4 | vm | fix | 20.29x [20.01, 20.57] | 5 |
| bmGaugeSetShared | 4 | vm | fix-relaxed | 20.60x [20.14, 21.07] | 5 |
| bmGaugeSetShared | 4 | vm | fix-relaxed-p1 | 3.22x [3.10, 3.34] | 4 |
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
| bmPrimitiveCounterIncShared | 1 | vm | fix | 0.99x [0.97, 1.01] | 5 |
| bmPrimitiveCounterIncShared | 1 | vm | fix-relaxed | 1.01x [1.00, 1.03] | 5 |
| bmPrimitiveCounterIncShared | 1 | vm | fix-relaxed-p1 | 1.01x [0.99, 1.03] | 4 |
| bmPrimitiveCounterIncShared | 12 | vm | fix | 165.47x [162.95, 168.04] | 5 |
| bmPrimitiveCounterIncShared | 12 | vm | fix-relaxed | 162.39x [159.96, 164.85] | 5 |
| bmPrimitiveCounterIncShared | 12 | vm | fix-relaxed-p1 | 165.55x [163.02, 168.13] | 4 |
| bmPrimitiveCounterIncShared | 4 | vm | fix | 22.12x [21.34, 22.92] | 5 |
| bmPrimitiveCounterIncShared | 4 | vm | fix-relaxed | 21.52x [21.05, 22.01] | 5 |
| bmPrimitiveCounterIncShared | 4 | vm | fix-relaxed-p1 | 22.29x [20.54, 24.19] | 4 |

## Spacing of the spaced cases (min_distance_bytes, the smallest seen over rounds)

| Benchmark | Placement | Arm | Bytes |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 320 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 512 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 384 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix | 320 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 320 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 320 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 256 |

## Fairness (slowest thread's operations over the fastest's; a result, not a gate)

| Benchmark | Placement | Arm | Median over rounds |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.996 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed | 0.988 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 | 0.976 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.997 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 0.990 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.985 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix | 0.237 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-relaxed | 0.269 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-relaxed-p1 | 0.168 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix | 0.710 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed | 0.743 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.710 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix | 0.998 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed | 0.993 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 | 0.986 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.999 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 0.999 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.992 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix | 0.239 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-relaxed | 0.128 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-relaxed-p1 | 0.707 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix | 0.506 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed | 0.445 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.855 |
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
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed | 0.932 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-relaxed-p1 | 0.930 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix | 0.978 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed | 0.959 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.960 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix | 0.226 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-relaxed | 0.293 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-relaxed-p1 | 0.309 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix | 0.764 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed | 0.750 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 | 0.823 |

