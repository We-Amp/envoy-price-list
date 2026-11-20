# Stats microbenchmarks (mt-micro-lse-arm-vm)

Per round the median over the repetitions; paired log ratio over the rounds with a 95% t interval (negative: cheaper than the reference; for throughput, negative is slower). The headline is the pooled cost, cycles per operation over all threads together, with the pooled throughput beside it (ns per sample for the histogram); fairness is a result in its own table. Binaries unchanged during the run: True.

## Arm against arm

| Benchmark | Placement | Arm vs ref | Measure | Effect [95% CI] | Rounds | Ref |
|---|---|---|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +36.39% [+36.27, +36.52] | 5 | 43.18 |
| bmCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -26.68% [-26.74, -26.62] | 5 | 68973402.77 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +36.40% [+36.32, +36.48] | 5 | 43.18 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -26.65% [-26.74, -26.56] | 5 | 827722326.90 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +36.45% [+36.38, +36.51] | 5 | 43.19 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -26.71% [-26.75, -26.68] | 5 | 275978582.22 |
| bmCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +36.40% [+36.34, +36.46] | 5 | 43.18 |
| bmCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -26.69% [-26.73, -26.66] | 5 | 551932430.13 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +32.94% [+32.92, +32.95] | 5 | 43.59 |
| bmCounterIncShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -24.78% [-24.80, -24.76] | 5 | 68326794.48 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +369.65% [+310.69, +437.07] | 5 | 2003.27 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -78.72% [-81.40, -75.65] | 5 | 17851908.73 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +139.53% [+107.31, +176.77] | 5 | 477.75 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -58.26% [-63.88, -51.77] | 5 | 24951518.00 |
| bmCounterIncShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +224.68% [+177.38, +280.05] | 5 | 1400.45 |
| bmCounterIncShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -69.21% [-73.68, -63.99] | 5 | 17024545.89 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +68.03% [+66.93, +69.14] | 5 | 25.08 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -40.48% [-40.87, -40.08] | 5 | 118745137.40 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +68.33% [+68.29, +68.37] | 5 | 25.08 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -40.59% [-40.59, -40.58] | 5 | 1425286134.50 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +68.35% [+68.27, +68.44] | 5 | 25.08 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -40.57% [-40.64, -40.50] | 5 | 474992086.05 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +68.28% [+68.25, +68.31] | 5 | 25.08 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -40.55% [-40.61, -40.48] | 5 | 950205592.66 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +68.44% [+64.87, +72.08] | 5 | 24.95 |
| bmGaugeSetShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -40.61% [-41.92, -39.27] | 5 | 119354439.85 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +201.35% [+178.24, +226.38] | 5 | 1302.69 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -66.82% [-69.37, -64.07] | 5 | 27451865.42 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +151.16% [+119.47, +187.43] | 5 | 339.27 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -60.19% [-65.21, -54.44] | 5 | 35134013.20 |
| bmGaugeSetShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +218.90% [+183.51, +258.71] | 5 | 837.39 |
| bmGaugeSetShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -68.64% [-72.12, -64.73] | 5 | 28470415.04 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +37.55% [+37.45, +37.64] | 5 | 39.96 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.31% [-27.34, -27.27] | 5 | 74551060.35 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +37.57% [+37.54, +37.60] | 5 | 39.96 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.32% [-27.34, -27.29] | 5 | 894751072.70 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +37.53% [+37.44, +37.61] | 5 | 39.96 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.29% [-27.33, -27.25] | 5 | 298298826.60 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +37.55% [+37.48, +37.61] | 5 | 39.96 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.30% [-27.33, -27.27] | 5 | 596583455.82 |
| bmModelCurrentShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +38.55% [+38.49, +38.60] | 5 | 39.96 |
| bmModelCurrentShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.82% [-27.85, -27.78] | 5 | 74558706.88 |
| bmModelCurrentShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +1161.36% [+1037.54, +1298.66] | 5 | 759.83 |
| bmModelCurrentShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -92.07% [-92.85, -91.21] | 5 | 47005463.96 |
| bmModelCurrentShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +375.23% [+314.94, +444.29] | 5 | 231.07 |
| bmModelCurrentShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -78.96% [-81.63, -75.90] | 5 | 51591616.41 |
| bmModelCurrentShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +765.92% [+710.22, +825.46] | 5 | 496.96 |
| bmModelCurrentShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -88.45% [-89.20, -87.66] | 5 | 47982897.28 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +20.56% [+20.51, +20.60] | 5 | 13.56 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -17.05% [-17.08, -17.03] | 5 | 219610730.23 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +20.57% [+20.53, +20.61] | 5 | 13.56 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -17.06% [-17.22, -16.90] | 5 | 2636517043.79 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +20.54% [+20.49, +20.60] | 5 | 13.56 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -17.04% [-17.08, -17.00] | 5 | 878834878.54 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +20.56% [+20.48, +20.63] | 5 | 13.56 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -17.06% [-17.19, -16.93] | 5 | 1757865101.34 |
| bmModelOneRmwShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +20.35% [+20.33, +20.38] | 5 | 13.59 |
| bmModelOneRmwShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -16.94% [-17.05, -16.84] | 5 | 219271582.97 |
| bmModelOneRmwShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +982.79% [+885.94, +1089.16] | 5 | 254.85 |
| bmModelOneRmwShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -90.77% [-91.59, -89.86] | 5 | 140330240.57 |
| bmModelOneRmwShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +327.56% [+289.96, +368.80] | 5 | 77.17 |
| bmModelOneRmwShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -76.61% [-78.67, -74.36] | 5 | 154493825.32 |
| bmModelOneRmwShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +666.16% [+627.58, +706.79] | 5 | 166.22 |
| bmModelOneRmwShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -86.95% [-87.61, -86.27] | 5 | 143449319.00 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +38.28% [+38.25, +38.30] | 5 | 39.96 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.68% [-27.70, -27.67] | 5 | 74546606.14 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +38.28% [+38.27, +38.29] | 5 | 39.96 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.65% [-27.73, -27.56] | 5 | 894768582.30 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +38.27% [+38.25, +38.30] | 5 | 39.96 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.68% [-27.69, -27.67] | 5 | 298296407.47 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +38.27% [+38.23, +38.31] | 5 | 39.96 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.64% [-27.71, -27.57] | 5 | 596542383.74 |
| bmModelRelaxedShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +38.81% [+38.79, +38.83] | 5 | 40.08 |
| bmModelRelaxedShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -27.98% [-28.04, -27.93] | 5 | 74323343.15 |
| bmModelRelaxedShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +1113.91% [+1032.64, +1201.00] | 5 | 757.97 |
| bmModelRelaxedShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -91.76% [-92.32, -91.17] | 5 | 47185276.90 |
| bmModelRelaxedShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +374.23% [+326.55, +427.25] | 5 | 231.48 |
| bmModelRelaxedShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -78.92% [-81.05, -76.56] | 5 | 51510630.77 |
| bmModelRelaxedShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +758.06% [+698.38, +822.19] | 5 | 497.16 |
| bmModelRelaxedShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -88.35% [-89.16, -87.48] | 5 | 47963129.60 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +33.09% [+33.07, +33.10] | 5 | 27.08 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -24.83% [-24.89, -24.77] | 5 | 109983258.40 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +33.08% [+33.06, +33.11] | 5 | 27.08 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -24.88% [-24.95, -24.81] | 5 | 1320063511.74 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +33.07% [+33.03, +33.11] | 5 | 27.09 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -24.87% [-24.95, -24.80] | 5 | 440053885.68 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +33.08% [+33.05, +33.11] | 5 | 27.08 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -24.88% [-24.93, -24.82] | 5 | 880177342.45 |
| bmModelRelaxedTestFlagShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +33.61% [+33.60, +33.62] | 5 | 27.08 |
| bmModelRelaxedTestFlagShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -25.16% [-25.16, -25.15] | 5 | 109992208.06 |
| bmModelRelaxedTestFlagShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +727.25% [+678.14, +779.46] | 5 | 642.85 |
| bmModelRelaxedTestFlagShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -87.91% [-88.64, -87.14] | 5 | 55634517.22 |
| bmModelRelaxedTestFlagShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +232.55% [+210.90, +255.70] | 5 | 200.82 |
| bmModelRelaxedTestFlagShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -69.94% [-71.90, -67.84] | 5 | 59367994.30 |
| bmModelRelaxedTestFlagShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +492.53% [+464.61, +521.83] | 5 | 422.40 |
| bmModelRelaxedTestFlagShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -83.13% [-83.92, -82.29] | 5 | 56452450.56 |
| bmModelShardedPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +19.33% [+19.30, +19.35] | 5 | 13.70 |
| bmModelShardedPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -16.15% [-16.24, -16.06] | 5 | 217327944.15 |
| bmModelShardedPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +19.33% [+19.30, +19.36] | 5 | 13.71 |
| bmModelShardedPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -16.20% [-16.22, -16.18] | 5 | 2608584463.11 |
| bmModelShardedPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +19.33% [+19.32, +19.34] | 5 | 13.70 |
| bmModelShardedPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -16.20% [-16.21, -16.19] | 5 | 869810450.40 |
| bmModelShardedPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +19.32% [+19.30, +19.34] | 5 | 13.71 |
| bmModelShardedPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -16.19% [-16.22, -16.17] | 5 | 1739255310.67 |
| bmModelShardedShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +19.61% [+19.56, +19.66] | 5 | 13.67 |
| bmModelShardedShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -16.40% [-16.43, -16.37] | 5 | 217910846.76 |
| bmModelShardedShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +19.56% [+19.52, +19.61] | 5 | 13.68 |
| bmModelShardedShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -16.36% [-16.40, -16.33] | 5 | 2614107870.21 |
| bmModelShardedShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +19.58% [+19.55, +19.60] | 5 | 13.68 |
| bmModelShardedShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -16.37% [-16.40, -16.34] | 5 | 871638434.89 |
| bmModelShardedShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +19.57% [+19.52, +19.61] | 5 | 13.68 |
| bmModelShardedShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -16.37% [-16.40, -16.33] | 5 | 1743097100.70 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +11.47% [+10.64, +12.30] | 5 | 29.21 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | -10.30% [-10.96, -9.63] | 5 | 101993444.56 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +10.42% [+9.55, +11.29] | 5 | 30.06 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -9.43% [-10.14, -8.72] | 5 | 1189351091.70 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +13.15% [+12.83, +13.47] | 5 | 29.21 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -11.65% [-11.93, -11.36] | 5 | 408090278.15 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +13.28% [+13.07, +13.50] | 5 | 29.21 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -11.76% [-11.91, -11.60] | 5 | 816054034.61 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | -22.93% [-40.80, +0.34] | 5 | 45.85 |
| bmPrimitiveCounterIncShared/manual_time/threads:1 | vm | fix-llsc vs fix-lse | ops_per_sec | +29.75% [-0.34, +68.93] | 5 | 64970646.03 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +785.00% [+725.22, +849.11] | 5 | 590.16 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-llsc vs fix-lse | ops_per_sec | -88.70% [-89.46, -87.88] | 5 | 60598523.07 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +252.12% [+229.20, +276.64] | 5 | 189.88 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-llsc vs fix-lse | ops_per_sec | -71.61% [-73.45, -69.64] | 5 | 62784115.73 |
| bmPrimitiveCounterIncShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | pooled_cycles_per_op | +523.57% [+484.61, +565.13] | 5 | 387.46 |
| bmPrimitiveCounterIncShared/manual_time/threads:8 | vm | fix-llsc vs fix-lse | ops_per_sec | -83.96% [-84.97, -82.90] | 5 | 61532564.26 |

## Model variants against Current (one build; pooled cycles/op)

| Benchmark | Threads | Placement | Effect on pooled cycles/op [95% CI] | Rounds |
|---|---|---|---|---|
| bmModelOneRmwPerThreadSpaced | 1 | vm | -70.26% [-70.27, -70.24] | 5 |
| bmModelOneRmwPerThreadSpaced | 1 | vm | -66.06% [-66.09, -66.04] | 5 |
| bmModelOneRmwPerThreadSpaced | 12 | vm | -70.26% [-70.26, -70.25] | 5 |
| bmModelOneRmwPerThreadSpaced | 12 | vm | -66.06% [-66.07, -66.06] | 5 |
| bmModelOneRmwPerThreadSpaced | 4 | vm | -70.25% [-70.26, -70.25] | 5 |
| bmModelOneRmwPerThreadSpaced | 4 | vm | -66.06% [-66.09, -66.04] | 5 |
| bmModelOneRmwPerThreadSpaced | 8 | vm | -70.26% [-70.26, -70.25] | 5 |
| bmModelOneRmwPerThreadSpaced | 8 | vm | -66.06% [-66.07, -66.06] | 5 |
| bmModelOneRmwShared | 1 | vm | -70.47% [-70.48, -70.46] | 5 |
| bmModelOneRmwShared | 1 | vm | -66.00% [-66.01, -65.99] | 5 |
| bmModelOneRmwShared | 12 | vm | -71.27% [-72.68, -69.80] | 5 |
| bmModelOneRmwShared | 12 | vm | -66.54% [-66.90, -66.16] | 5 |
| bmModelOneRmwShared | 4 | vm | -69.86% [-71.85, -67.73] | 5 |
| bmModelOneRmwShared | 4 | vm | -66.50% [-66.63, -66.37] | 5 |
| bmModelOneRmwShared | 8 | vm | -70.38% [-70.80, -69.95] | 5 |
| bmModelOneRmwShared | 8 | vm | -66.52% [-66.78, -66.27] | 5 |
| bmModelRelaxedPerThreadSpaced | 1 | vm | +0.52% [+0.46, +0.58] | 5 |
| bmModelRelaxedPerThreadSpaced | 1 | vm | -0.01% [-0.03, +0.01] | 5 |
| bmModelRelaxedPerThreadSpaced | 12 | vm | +0.51% [+0.48, +0.54] | 5 |
| bmModelRelaxedPerThreadSpaced | 12 | vm | -0.00% [-0.02, +0.01] | 5 |
| bmModelRelaxedPerThreadSpaced | 4 | vm | +0.53% [+0.50, +0.55] | 5 |
| bmModelRelaxedPerThreadSpaced | 4 | vm | -0.01% [-0.06, +0.04] | 5 |
| bmModelRelaxedPerThreadSpaced | 8 | vm | +0.51% [+0.47, +0.56] | 5 |
| bmModelRelaxedPerThreadSpaced | 8 | vm | -0.02% [-0.06, +0.03] | 5 |
| bmModelRelaxedShared | 1 | vm | +0.49% [+0.45, +0.53] | 5 |
| bmModelRelaxedShared | 1 | vm | +0.30% [+0.28, +0.32] | 5 |
| bmModelRelaxedShared | 12 | vm | -3.84% [-7.87, +0.37] | 5 |
| bmModelRelaxedShared | 12 | vm | -0.08% [-1.17, +1.02] | 5 |
| bmModelRelaxedShared | 4 | vm | -0.05% [-3.77, +3.82] | 5 |
| bmModelRelaxedShared | 4 | vm | +0.16% [+0.09, +0.24] | 5 |
| bmModelRelaxedShared | 8 | vm | -0.97% [-3.42, +1.55] | 5 |
| bmModelRelaxedShared | 8 | vm | -0.06% [-0.59, +0.47] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 1 | vm | -34.43% [-34.47, -34.39] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 1 | vm | -32.23% [-32.25, -32.21] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 12 | vm | -34.43% [-34.45, -34.41] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 12 | vm | -32.22% [-32.24, -32.20] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 4 | vm | -34.43% [-34.45, -34.40] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 4 | vm | -32.23% [-32.27, -32.19] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 8 | vm | -34.43% [-34.45, -34.40] | 5 |
| bmModelRelaxedTestFlagPerThreadSpaced | 8 | vm | -32.23% [-32.27, -32.19] | 5 |
| bmModelRelaxedTestFlagShared | 1 | vm | -34.64% [-34.67, -34.62] | 5 |
| bmModelRelaxedTestFlagShared | 1 | vm | -32.23% [-32.24, -32.22] | 5 |
| bmModelRelaxedTestFlagShared | 12 | vm | -44.51% [-46.69, -42.23] | 5 |
| bmModelRelaxedTestFlagShared | 12 | vm | -15.38% [-17.81, -12.89] | 5 |
| bmModelRelaxedTestFlagShared | 4 | vm | -40.00% [-43.75, -36.01] | 5 |
| bmModelRelaxedTestFlagShared | 4 | vm | -14.26% [-17.18, -11.23] | 5 |
| bmModelRelaxedTestFlagShared | 8 | vm | -41.89% [-42.77, -41.00] | 5 |
| bmModelRelaxedTestFlagShared | 8 | vm | -15.08% [-17.63, -12.45] | 5 |
| bmModelShardedPerThreadSpaced | 1 | vm | -70.25% [-70.27, -70.23] | 5 |
| bmModelShardedPerThreadSpaced | 1 | vm | -65.71% [-65.72, -65.69] | 5 |
| bmModelShardedPerThreadSpaced | 12 | vm | -70.25% [-70.26, -70.24] | 5 |
| bmModelShardedPerThreadSpaced | 12 | vm | -65.70% [-65.71, -65.70] | 5 |
| bmModelShardedPerThreadSpaced | 4 | vm | -70.25% [-70.26, -70.24] | 5 |
| bmModelShardedPerThreadSpaced | 4 | vm | -65.71% [-65.73, -65.69] | 5 |
| bmModelShardedPerThreadSpaced | 8 | vm | -70.25% [-70.26, -70.24] | 5 |
| bmModelShardedPerThreadSpaced | 8 | vm | -65.71% [-65.72, -65.69] | 5 |
| bmModelShardedShared | 1 | vm | -70.46% [-70.47, -70.45] | 5 |
| bmModelShardedShared | 1 | vm | -65.79% [-65.80, -65.77] | 5 |
| bmModelShardedShared | 12 | vm | -99.83% [-99.84, -99.82] | 5 |
| bmModelShardedShared | 12 | vm | -98.19% [-98.31, -98.06] | 5 |
| bmModelShardedShared | 4 | vm | -98.54% [-98.62, -98.45] | 5 |
| bmModelShardedShared | 4 | vm | -94.19% [-94.70, -93.64] | 5 |
| bmModelShardedShared | 8 | vm | -99.62% [-99.62, -99.61] | 5 |
| bmModelShardedShared | 8 | vm | -97.24% [-97.44, -97.03] | 5 |

## Shared against per-thread spaced, per arm (H1; pooled cycles/op)

| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |
|---|---|---|---|---|---|
| bmCounterIncShared | 1 | vm | fix-llsc | 0.98x [0.98, 0.98] | 5 |
| bmCounterIncShared | 1 | vm | fix-lse | 1.01x [1.01, 1.01] | 5 |
| bmCounterIncShared | 12 | vm | fix-llsc | 158.61x [154.05, 163.30] | 5 |
| bmCounterIncShared | 12 | vm | fix-lse | 46.06x [41.31, 51.37] | 5 |
| bmCounterIncShared | 4 | vm | fix-llsc | 20.13x [19.05, 21.27] | 5 |
| bmCounterIncShared | 4 | vm | fix-lse | 11.47x [10.06, 13.08] | 5 |
| bmCounterIncShared | 8 | vm | fix-llsc | 76.94x [66.36, 89.21] | 5 |
| bmCounterIncShared | 8 | vm | fix-lse | 32.32x [28.38, 36.82] | 5 |
| bmGaugeSetShared | 1 | vm | fix-llsc | 1.00x [1.00, 1.00] | 5 |
| bmGaugeSetShared | 1 | vm | fix-lse | 1.00x [0.98, 1.02] | 5 |
| bmGaugeSetShared | 12 | vm | fix-llsc | 92.75x [86.08, 99.94] | 5 |
| bmGaugeSetShared | 12 | vm | fix-lse | 51.81x [47.25, 56.80] | 5 |
| bmGaugeSetShared | 4 | vm | fix-llsc | 19.51x [18.46, 20.63] | 5 |
| bmGaugeSetShared | 4 | vm | fix-lse | 13.08x [12.05, 14.20] | 5 |
| bmGaugeSetShared | 8 | vm | fix-llsc | 62.73x [57.96, 67.91] | 5 |
| bmGaugeSetShared | 8 | vm | fix-lse | 33.10x [31.56, 34.73] | 5 |
| bmModelCurrentShared | 1 | vm | fix-llsc | 1.01x [1.01, 1.01] | 5 |
| bmModelCurrentShared | 1 | vm | fix-lse | 1.00x [1.00, 1.00] | 5 |
| bmModelCurrentShared | 12 | vm | fix-llsc | 173.42x [165.71, 181.49] | 5 |
| bmModelCurrentShared | 12 | vm | fix-lse | 18.91x [17.61, 20.31] | 5 |
| bmModelCurrentShared | 4 | vm | fix-llsc | 20.37x [19.19, 21.61] | 5 |
| bmModelCurrentShared | 4 | vm | fix-lse | 5.89x [5.38, 6.46] | 5 |
| bmModelCurrentShared | 8 | vm | fix-llsc | 78.08x [77.03, 79.14] | 5 |
| bmModelCurrentShared | 8 | vm | fix-lse | 12.40x [11.51, 13.36] | 5 |
| bmModelOneRmwShared | 1 | vm | fix-llsc | 1.00x [1.00, 1.00] | 5 |
| bmModelOneRmwShared | 1 | vm | fix-lse | 1.00x [1.00, 1.00] | 5 |
| bmModelOneRmwShared | 12 | vm | fix-llsc | 167.49x [161.15, 174.08] | 5 |
| bmModelOneRmwShared | 12 | vm | fix-lse | 18.65x [17.52, 19.85] | 5 |
| bmModelOneRmwShared | 4 | vm | fix-llsc | 20.64x [20.39, 20.89] | 5 |
| bmModelOneRmwShared | 4 | vm | fix-lse | 5.82x [5.32, 6.36] | 5 |
| bmModelOneRmwShared | 8 | vm | fix-llsc | 77.75x [75.97, 79.57] | 5 |
| bmModelOneRmwShared | 8 | vm | fix-lse | 12.23x [11.42, 13.11] | 5 |
| bmModelRelaxedShared | 1 | vm | fix-llsc | 1.01x [1.01, 1.01] | 5 |
| bmModelRelaxedShared | 1 | vm | fix-lse | 1.00x [1.00, 1.00] | 5 |
| bmModelRelaxedShared | 12 | vm | fix-llsc | 165.90x [164.40, 167.42] | 5 |
| bmModelRelaxedShared | 12 | vm | fix-lse | 18.90x [17.71, 20.17] | 5 |
| bmModelRelaxedShared | 4 | vm | fix-llsc | 20.25x [19.77, 20.75] | 5 |
| bmModelRelaxedShared | 4 | vm | fix-lse | 5.90x [5.39, 6.47] | 5 |
| bmModelRelaxedShared | 8 | vm | fix-llsc | 76.93x [75.50, 78.38] | 5 |
| bmModelRelaxedShared | 8 | vm | fix-lse | 12.40x [11.56, 13.30] | 5 |
| bmModelRelaxedTestFlagShared | 1 | vm | fix-llsc | 1.00x [1.00, 1.00] | 5 |
| bmModelRelaxedTestFlagShared | 1 | vm | fix-lse | 1.00x [1.00, 1.00] | 5 |
| bmModelRelaxedTestFlagShared | 12 | vm | fix-llsc | 146.78x [144.47, 149.12] | 5 |
| bmModelRelaxedTestFlagShared | 12 | vm | fix-lse | 23.61x [22.55, 24.72] | 5 |
| bmModelRelaxedTestFlagShared | 4 | vm | fix-llsc | 18.63x [18.32, 18.96] | 5 |
| bmModelRelaxedTestFlagShared | 4 | vm | fix-lse | 7.46x [7.03, 7.90] | 5 |
| bmModelRelaxedTestFlagShared | 8 | vm | fix-llsc | 69.19x [68.60, 69.78] | 5 |
| bmModelRelaxedTestFlagShared | 8 | vm | fix-lse | 15.54x [14.87, 16.24] | 5 |
| bmModelShardedShared | 1 | vm | fix-llsc | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 1 | vm | fix-lse | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 12 | vm | fix-llsc | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 12 | vm | fix-lse | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 4 | vm | fix-llsc | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 4 | vm | fix-lse | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 8 | vm | fix-llsc | 1.00x [1.00, 1.00] | 5 |
| bmModelShardedShared | 8 | vm | fix-lse | 1.00x [1.00, 1.00] | 5 |
| bmPrimitiveCounterIncShared | 1 | vm | fix-llsc | 0.99x [0.98, 0.99] | 5 |
| bmPrimitiveCounterIncShared | 1 | vm | fix-lse | 1.43x [1.11, 1.84] | 5 |
| bmPrimitiveCounterIncShared | 12 | vm | fix-llsc | 153.53x [148.24, 159.01] | 5 |
| bmPrimitiveCounterIncShared | 12 | vm | fix-lse | 19.16x [18.19, 20.17] | 5 |
| bmPrimitiveCounterIncShared | 4 | vm | fix-llsc | 20.49x [20.23, 20.75] | 5 |
| bmPrimitiveCounterIncShared | 4 | vm | fix-lse | 6.58x [6.12, 7.08] | 5 |
| bmPrimitiveCounterIncShared | 8 | vm | fix-llsc | 73.83x [70.91, 76.88] | 5 |
| bmPrimitiveCounterIncShared | 8 | vm | fix-lse | 13.41x [12.81, 14.05] | 5 |

## Spacing of the spaced cases (min_distance_bytes, the smallest seen over rounds)

| Benchmark | Placement | Arm | Bytes |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 320 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 320 |
| bmCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 256 |
| bmCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 320 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 448 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 256 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 256 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 256 |

## Fairness (slowest thread's operations over the fastest's; a result, not a gate)

| Benchmark | Placement | Arm | Median over rounds |
|---|---|---|---|
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 0.997 |
| bmCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 0.999 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 0.999 |
| bmCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 0.999 |
| bmCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 0.996 |
| bmCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 0.999 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-llsc | 0.181 |
| bmCounterIncShared/manual_time/threads:12 | vm | fix-lse | 0.299 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-llsc | 0.029 |
| bmCounterIncShared/manual_time/threads:4 | vm | fix-lse | 0.518 |
| bmCounterIncShared/manual_time/threads:8 | vm | fix-llsc | 0.061 |
| bmCounterIncShared/manual_time/threads:8 | vm | fix-lse | 0.326 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 0.996 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 0.998 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 0.998 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 0.999 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 0.997 |
| bmGaugeSetPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 0.999 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-llsc | 0.200 |
| bmGaugeSetShared/manual_time/threads:12 | vm | fix-lse | 0.332 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-llsc | 0.079 |
| bmGaugeSetShared/manual_time/threads:4 | vm | fix-lse | 0.678 |
| bmGaugeSetShared/manual_time/threads:8 | vm | fix-llsc | 0.115 |
| bmGaugeSetShared/manual_time/threads:8 | vm | fix-lse | 0.344 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 0.999 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 0.999 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 0.999 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 0.999 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 0.999 |
| bmModelCurrentPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 0.999 |
| bmModelCurrentShared/manual_time/threads:12 | vm | fix-llsc | 0.226 |
| bmModelCurrentShared/manual_time/threads:12 | vm | fix-lse | 0.598 |
| bmModelCurrentShared/manual_time/threads:4 | vm | fix-llsc | 0.105 |
| bmModelCurrentShared/manual_time/threads:4 | vm | fix-lse | 0.824 |
| bmModelCurrentShared/manual_time/threads:8 | vm | fix-llsc | 0.137 |
| bmModelCurrentShared/manual_time/threads:8 | vm | fix-lse | 0.629 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 0.999 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 0.998 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 0.999 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 0.999 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 0.999 |
| bmModelOneRmwPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 0.999 |
| bmModelOneRmwShared/manual_time/threads:12 | vm | fix-llsc | 0.135 |
| bmModelOneRmwShared/manual_time/threads:12 | vm | fix-lse | 0.607 |
| bmModelOneRmwShared/manual_time/threads:4 | vm | fix-llsc | 0.627 |
| bmModelOneRmwShared/manual_time/threads:4 | vm | fix-lse | 0.822 |
| bmModelOneRmwShared/manual_time/threads:8 | vm | fix-llsc | 0.097 |
| bmModelOneRmwShared/manual_time/threads:8 | vm | fix-lse | 0.634 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 0.999 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 0.999 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 0.999 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 0.999 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 0.999 |
| bmModelRelaxedPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 0.999 |
| bmModelRelaxedShared/manual_time/threads:12 | vm | fix-llsc | 0.199 |
| bmModelRelaxedShared/manual_time/threads:12 | vm | fix-lse | 0.598 |
| bmModelRelaxedShared/manual_time/threads:4 | vm | fix-llsc | 0.122 |
| bmModelRelaxedShared/manual_time/threads:4 | vm | fix-lse | 0.831 |
| bmModelRelaxedShared/manual_time/threads:8 | vm | fix-llsc | 0.122 |
| bmModelRelaxedShared/manual_time/threads:8 | vm | fix-lse | 0.634 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 0.999 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 0.999 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 0.999 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 0.999 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 0.999 |
| bmModelRelaxedTestFlagPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 0.999 |
| bmModelRelaxedTestFlagShared/manual_time/threads:12 | vm | fix-llsc | 0.122 |
| bmModelRelaxedTestFlagShared/manual_time/threads:12 | vm | fix-lse | 0.593 |
| bmModelRelaxedTestFlagShared/manual_time/threads:4 | vm | fix-llsc | 0.410 |
| bmModelRelaxedTestFlagShared/manual_time/threads:4 | vm | fix-lse | 0.804 |
| bmModelRelaxedTestFlagShared/manual_time/threads:8 | vm | fix-llsc | 0.089 |
| bmModelRelaxedTestFlagShared/manual_time/threads:8 | vm | fix-lse | 0.665 |
| bmModelShardedPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 0.999 |
| bmModelShardedPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 0.999 |
| bmModelShardedPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 0.999 |
| bmModelShardedPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 0.999 |
| bmModelShardedPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 0.999 |
| bmModelShardedPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 0.999 |
| bmModelShardedShared/manual_time/threads:12 | vm | fix-llsc | 0.999 |
| bmModelShardedShared/manual_time/threads:12 | vm | fix-lse | 0.999 |
| bmModelShardedShared/manual_time/threads:4 | vm | fix-llsc | 0.999 |
| bmModelShardedShared/manual_time/threads:4 | vm | fix-lse | 0.999 |
| bmModelShardedShared/manual_time/threads:8 | vm | fix-llsc | 0.999 |
| bmModelShardedShared/manual_time/threads:8 | vm | fix-lse | 0.999 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-llsc | 0.941 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:12 | vm | fix-lse | 0.662 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-llsc | 0.981 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:4 | vm | fix-lse | 0.999 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-llsc | 0.955 |
| bmPrimitiveCounterIncPerThreadSpaced/manual_time/threads:8 | vm | fix-lse | 0.999 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-llsc | 0.064 |
| bmPrimitiveCounterIncShared/manual_time/threads:12 | vm | fix-lse | 0.494 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-llsc | 0.493 |
| bmPrimitiveCounterIncShared/manual_time/threads:4 | vm | fix-lse | 0.719 |
| bmPrimitiveCounterIncShared/manual_time/threads:8 | vm | fix-llsc | 0.041 |
| bmPrimitiveCounterIncShared/manual_time/threads:8 | vm | fix-lse | 0.495 |

