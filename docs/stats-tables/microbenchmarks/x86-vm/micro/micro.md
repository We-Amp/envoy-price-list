# Stats microbenchmarks (mt-micro-x86-vm)

Per round the median over the repetitions; paired log ratio over the rounds with a 95% t interval (negative: cheaper than the reference; for throughput, negative is slower). The headline is the pooled cost, cycles per operation over all threads together, with the pooled throughput beside it (ns per sample for the histogram); fairness is a result in its own table. Binaries unchanged during the run: True.

## Arm against arm

| Benchmark | Placement | Arm vs ref | Measure | Effect [95% CI] | Rounds | Ref |
|---|---|---|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +0.01% [-0.05, +0.06] | 5 | 60.49 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | -0.13% [-17.49, +20.87] | 5 | 60654748.79 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -0.93% [-2.70, +0.88] | 5 | 61.88 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +4.61% [-5.90, +16.30] | 5 | 217947004.08 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -0.12% [-0.42, +0.18] | 5 | 60.51 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | ops_per_sec | +2.08% [-7.73, +12.93] | 5 | 386427431.27 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +0.00% [-0.04, +0.05] | 5 | 61.49 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | +1.36% [-16.09, +22.44] | 5 | 58470636.30 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +0.67% [-7.75, +9.85] | 5 | 906.00 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +1.53% [-17.20, +24.48] | 5 | 14915452.84 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -0.45% [-4.86, +4.18] | 5 | 1664.36 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed vs fix | ops_per_sec | +1.65% [-13.82, +19.91] | 5 | 13997510.74 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -38.63% [-38.64, -38.61] | 5 | 41.47 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | +71.35% [+55.85, +88.39] | 5 | 77825987.53 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -38.63% [-38.65, -38.61] | 5 | 41.48 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +68.58% [+52.62, +86.20] | 5 | 302466799.66 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -38.63% [-38.64, -38.62] | 5 | 41.48 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | ops_per_sec | +70.87% [+63.34, +78.76] | 5 | 523773197.54 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -36.01% [-43.03, -28.11] | 5 | 41.47 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | +65.87% [+50.41, +82.92] | 5 | 77838727.28 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -35.43% [-37.88, -32.88] | 5 | 636.14 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +58.78% [+52.18, +65.67] | 5 | 20761235.31 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -32.48% [-36.41, -28.30] | 5 | 1105.43 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed vs fix | ops_per_sec | +53.02% [+35.95, +72.23] | 5 | 19698915.62 |
| bmHistogramRecordOnly/1/manual_time | vm | fix-relaxed vs fix | ns_per_sample | -3.80% [-8.34, +0.97] | 5 | 43.09 |
| bmHistogramRecordOnly/7/manual_time | vm | fix-relaxed vs fix | ns_per_sample | -18.87% [-47.33, +24.98] | 5 | 47.39 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -0.03% [-0.06, +0.00] | 5 | 38.47 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | +11.67% [+1.20, +23.23] | 5 | 84471622.20 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -0.03% [-0.06, +0.01] | 5 | 38.47 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +8.95% [-0.75, +19.60] | 5 | 325928986.52 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +0.43% [-1.91, +2.82] | 5 | 38.48 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed vs fix | ops_per_sec | +7.15% [-1.22, +16.23] | 5 | 564051175.94 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | pooled_cycles_per_op | -0.02% [-0.04, +0.01] | 5 | 39.48 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed vs fix | ops_per_sec | +8.33% [-0.89, +18.41] | 5 | 81619785.21 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +1.58% [-7.41, +11.45] | 5 | 451.37 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed vs fix | ops_per_sec | +4.39% [-3.47, +12.90] | 5 | 28522810.54 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed vs fix | pooled_cycles_per_op | +0.96% [-5.77, +8.16] | 5 | 810.18 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed vs fix | ops_per_sec | +3.37% [-0.13, +6.99] | 5 | 27610057.16 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -28.13% [-28.16, -28.10] | 5 | 60.50 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +36.75% [+24.62, +50.06] | 5 | 60037508.44 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -28.44% [-28.94, -27.94] | 5 | 60.57 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +33.78% [+24.44, +43.82] | 5 | 230645967.48 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -28.13% [-28.15, -28.10] | 5 | 60.50 |
| bmCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +36.29% [+29.75, +43.16] | 5 | 394149197.85 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -29.30% [-29.32, -29.27] | 5 | 61.49 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +35.10% [+16.69, +56.42] | 5 | 58418513.84 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -26.28% [-30.17, -22.18] | 5 | 888.31 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +31.09% [+15.11, +49.27] | 5 | 15022862.99 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -27.46% [-30.49, -24.30] | 5 | 1634.95 |
| bmCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +33.05% [+16.29, +52.24] | 5 | 14457753.49 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -59.26% [-59.58, -58.93] | 5 | 25.45 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +143.20% [+131.19, +155.83] | 5 | 142856449.57 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -59.76% [-59.93, -59.59] | 5 | 25.46 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +153.68% [+135.82, +172.89] | 5 | 539912091.77 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -59.82% [-59.99, -59.65] | 5 | 25.46 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +152.41% [+140.43, +164.98] | 5 | 935476074.14 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -62.06% [-66.42, -57.13] | 5 | 25.45 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +158.67% [+124.62, +197.88] | 5 | 139484649.82 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -79.39% [-80.19, -78.57] | 5 | 408.47 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +397.72% [+339.53, +463.61] | 5 | 32759845.02 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -79.13% [-80.17, -78.03] | 5 | 726.36 |
| bmGaugeSetShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +377.11% [+338.66, +418.93] | 5 | 31943467.79 |
| bmHistogramRecordOnly/1/manual_time | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_sample | -2.55% [-8.72, +4.04] | 5 | 42.16 |
| bmHistogramRecordOnly/7/manual_time | vm | fix-relaxed-p1 vs fix-relaxed | ns_per_sample | +1.45% [-10.08, +14.45] | 5 | 45.33 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | +0.01% [-0.01, +0.02] | 5 | 38.46 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | -2.30% [-5.12, +0.61] | 5 | 98734044.55 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | +0.01% [-0.01, +0.03] | 5 | 38.46 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | -0.48% [-4.93, +4.18] | 5 | 375509294.13 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -0.98% [-2.93, +1.00] | 5 | 38.47 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +0.44% [-5.98, +7.29] | 5 | 613851509.29 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | +0.00% [-0.01, +0.02] | 5 | 39.47 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | -0.77% [-3.31, +1.85] | 5 | 95110969.98 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | +0.46% [-6.86, +8.36] | 5 | 461.56 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | -2.31% [-10.85, +7.04] | 5 | 30999162.56 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | pooled_cycles_per_op | -1.54% [-8.36, +5.79] | 5 | 806.77 |
| bmPrimitiveCounterIncShared/manual_time/threads:7 | vm | fix-relaxed-p1 vs fix-relaxed | ops_per_sec | +1.04% [-6.92, +9.67] | 5 | 28758354.18 |

## Model variants against Current (one build; pooled cycles/op)

| Benchmark | Threads | Placement | Effect on pooled cycles/op [95% CI] | Rounds |
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

## Shared against per-thread spaced, per arm (H1; pooled cycles/op)

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

