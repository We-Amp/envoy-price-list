# Stats microbenchmarks (mt-micro-x86-vm)

Time per iteration, median of the repetitions per round; paired log ratio over the rounds with a 95% t interval (negative: the arm is faster). Binaries unchanged during the run: True.

## Arm against arm

| Benchmark | Placement | Arm vs ref | Effect [95% CI] | Rounds | Ref ns |
|---|---|---|---|---|---|
| bmFlushContended/100000/0/0/real_time | vm | fix-relaxed vs fix | +3.38% [-6.59, +14.41] | 5 | 5967968.75 |
| bmFlushContended/100000/0/1/real_time | vm | fix-relaxed vs fix | +5.46% [-4.62, +16.61] | 5 | 6102623.16 |
| bmFlushContended/100000/0/2/real_time | vm | fix-relaxed vs fix | +0.21% [-3.40, +3.95] | 5 | 6085065.37 |
| bmFlushContended/100000/1/0/real_time | vm | fix-relaxed vs fix | +3.18% [-3.69, +10.53] | 5 | 5970337.17 |
| bmFlushContended/100000/1/1/real_time | vm | fix-relaxed vs fix | +3.83% [-1.37, +9.31] | 5 | 6554158.91 |
| bmFlushContended/100000/1/2/real_time | vm | fix-relaxed vs fix | +2.73% [-1.68, +7.33] | 5 | 6036838.25 |
| bmFlushContended/100000/4/0/real_time | vm | fix-relaxed vs fix | +1.47% [-5.64, +9.11] | 5 | 6580882.66 |
| bmFlushContended/100000/4/1/real_time | vm | fix-relaxed vs fix | +2.60% [-2.75, +8.24] | 5 | 7006341.90 |
| bmFlushContended/100000/4/2/real_time | vm | fix-relaxed vs fix | +4.48% [-0.56, +9.78] | 5 | 6284975.01 |
| bmFlushContended/100000/7/0/real_time | vm | fix-relaxed vs fix | +2.94% [-2.46, +8.65] | 5 | 6607089.43 |
| bmFlushContended/100000/7/1/real_time | vm | fix-relaxed vs fix | +1.03% [-1.78, +3.93] | 5 | 7211432.73 |
| bmFlushContended/100000/7/2/real_time | vm | fix-relaxed vs fix | +3.26% [-5.25, +12.53] | 5 | 6728806.32 |
| bmHammerOnly/100000/1/0/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 5 | 10000978.83 |
| bmHammerOnly/100000/1/1/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 5 | 10000888.31 |
| bmHammerOnly/100000/1/2/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 5 | 10000965.24 |
| bmHammerOnly/100000/4/0/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 5 | 10000627.17 |
| bmHammerOnly/100000/4/1/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 5 | 10000578.93 |
| bmHammerOnly/100000/4/2/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 5 | 10000584.99 |
| bmHammerOnly/100000/7/0/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 5 | 10000665.13 |
| bmHammerOnly/100000/7/1/real_time | vm | fix-relaxed vs fix | +0.00% [+0.00, +0.00] | 5 | 10000609.46 |
| bmHammerOnly/100000/7/2/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 5 | 10000637.01 |
| bmFlushContended/100000/0/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +4.55% [-14.46, +27.79] | 5 | 6135712.75 |
| bmFlushContended/100000/0/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +2.79% [-14.71, +23.89] | 5 | 6093115.85 |
| bmFlushContended/100000/0/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +4.62% [-4.59, +14.71] | 5 | 6046338.90 |
| bmFlushContended/100000/1/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +1.92% [-11.06, +16.78] | 5 | 6395103.11 |
| bmFlushContended/100000/1/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +1.78% [-10.61, +15.89] | 5 | 6775963.42 |
| bmFlushContended/100000/1/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -1.03% [-10.57, +9.52] | 5 | 6325643.82 |
| bmFlushContended/100000/4/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +3.01% [-7.78, +15.06] | 5 | 6779845.67 |
| bmFlushContended/100000/4/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +2.01% [-9.96, +15.57] | 5 | 7115328.85 |
| bmFlushContended/100000/4/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -1.91% [-9.78, +6.65] | 5 | 6542833.90 |
| bmFlushContended/100000/7/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +6.29% [-7.85, +22.61] | 5 | 6785300.24 |
| bmFlushContended/100000/7/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +1.75% [-1.57, +5.18] | 5 | 7236156.06 |
| bmFlushContended/100000/7/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -2.96% [-10.86, +5.65] | 5 | 6638809.15 |
| bmHammerOnly/100000/1/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 5 | 10001008.50 |
| bmHammerOnly/100000/1/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 5 | 10000978.03 |
| bmHammerOnly/100000/1/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 5 | 10001001.97 |
| bmHammerOnly/100000/4/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 5 | 10000628.03 |
| bmHammerOnly/100000/4/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, -0.00] | 5 | 10000607.19 |
| bmHammerOnly/100000/4/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 5 | 10000622.33 |
| bmHammerOnly/100000/7/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 5 | 10000707.91 |
| bmHammerOnly/100000/7/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, -0.00] | 5 | 10000658.00 |
| bmHammerOnly/100000/7/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 5 | 10000672.37 |
| bmFlushContended/100000/0/0/real_time | vm | base-relaxed vs base | -7.25% [-31.64, +25.84] | 5 | 13439362.35 |
| bmFlushContended/100000/0/1/real_time | vm | base-relaxed vs base | -4.61% [-21.76, +16.30] | 5 | 13065685.50 |
| bmFlushContended/100000/0/2/real_time | vm | base-relaxed vs base | +3.45% [-7.76, +16.02] | 5 | 12675281.55 |
| bmFlushContended/100000/1/0/real_time | vm | base-relaxed vs base | -1.41% [-13.29, +12.10] | 5 | 13220176.48 |
| bmFlushContended/100000/1/1/real_time | vm | base-relaxed vs base | +3.89% [-17.39, +30.67] | 5 | 13515183.49 |
| bmFlushContended/100000/1/2/real_time | vm | base-relaxed vs base | -0.59% [-6.85, +6.10] | 5 | 13353718.38 |
| bmFlushContended/100000/4/0/real_time | vm | base-relaxed vs base | -0.24% [-12.12, +13.25] | 5 | 13722918.61 |
| bmFlushContended/100000/4/1/real_time | vm | base-relaxed vs base | -1.71% [-11.34, +8.98] | 5 | 15566843.56 |
| bmFlushContended/100000/4/2/real_time | vm | base-relaxed vs base | +0.95% [-8.55, +11.44] | 5 | 13937876.30 |
| bmFlushContended/100000/7/0/real_time | vm | base-relaxed vs base | -0.70% [-12.80, +13.09] | 5 | 13962060.56 |
| bmFlushContended/100000/7/1/real_time | vm | base-relaxed vs base | +1.60% [-8.31, +12.59] | 5 | 15558783.61 |
| bmFlushContended/100000/7/2/real_time | vm | base-relaxed vs base | +2.48% [-2.98, +8.25] | 5 | 14079621.64 |
| bmHammerOnly/100000/1/0/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 5 | 10000877.37 |
| bmHammerOnly/100000/1/1/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 5 | 10000896.16 |
| bmHammerOnly/100000/1/2/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 5 | 10000954.57 |
| bmHammerOnly/100000/4/0/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 5 | 10000592.90 |
| bmHammerOnly/100000/4/1/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 5 | 10000582.21 |
| bmHammerOnly/100000/4/2/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 5 | 10000548.27 |
| bmHammerOnly/100000/7/0/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 5 | 10000648.20 |
| bmHammerOnly/100000/7/1/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 5 | 10000605.10 |
| bmHammerOnly/100000/7/2/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 5 | 10000601.44 |
| bmFlushContended/100000/0/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +5.73% [-12.07, +27.13] | 5 | 13606141.90 |
| bmFlushContended/100000/0/1/real_time | vm | base-relaxed-p1 vs base-relaxed | -1.02% [-5.75, +3.95] | 5 | 13056259.75 |
| bmFlushContended/100000/0/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +1.38% [-12.55, +17.54] | 5 | 13699095.15 |
| bmFlushContended/100000/1/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +5.13% [-6.52, +18.23] | 5 | 13328272.58 |
| bmFlushContended/100000/1/1/real_time | vm | base-relaxed-p1 vs base-relaxed | -3.95% [-12.49, +5.43] | 5 | 13912983.07 |
| bmFlushContended/100000/1/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +5.28% [-14.99, +30.40] | 5 | 13063161.84 |
| bmFlushContended/100000/4/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +1.39% [-14.69, +20.50] | 5 | 13883524.81 |
| bmFlushContended/100000/4/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +7.65% [+0.63, +15.16] | 5 | 14949038.13 |
| bmFlushContended/100000/4/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +7.70% [-16.48, +38.88] | 5 | 13808941.67 |
| bmFlushContended/100000/7/0/real_time | vm | base-relaxed-p1 vs base-relaxed | -1.83% [-10.93, +8.19] | 5 | 14749750.17 |
| bmFlushContended/100000/7/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +3.55% [-5.38, +13.33] | 5 | 15589824.78 |
| bmFlushContended/100000/7/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +4.67% [-6.35, +16.98] | 5 | 13718469.45 |
| bmHammerOnly/100000/1/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 5 | 10000979.00 |
| bmHammerOnly/100000/1/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 5 | 10000928.77 |
| bmHammerOnly/100000/1/2/real_time | vm | base-relaxed-p1 vs base-relaxed | -0.00% [-0.00, +0.00] | 5 | 10001008.17 |
| bmHammerOnly/100000/4/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 5 | 10000630.31 |
| bmHammerOnly/100000/4/1/real_time | vm | base-relaxed-p1 vs base-relaxed | -0.00% [-0.00, +0.00] | 5 | 10000574.63 |
| bmHammerOnly/100000/4/2/real_time | vm | base-relaxed-p1 vs base-relaxed | -0.00% [-0.00, +0.00] | 5 | 10000642.71 |
| bmHammerOnly/100000/7/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 5 | 10000668.00 |
| bmHammerOnly/100000/7/1/real_time | vm | base-relaxed-p1 vs base-relaxed | -0.00% [-0.00, +0.00] | 5 | 10000645.14 |
| bmHammerOnly/100000/7/2/real_time | vm | base-relaxed-p1 vs base-relaxed | -0.00% [-0.00, +0.00] | 5 | 10000677.90 |
| bmFlushContended/100000/0/0/real_time | vm | fix vs base | -58.11% [-69.49, -42.49] | 5 | 13439362.35 |
| bmFlushContended/100000/0/1/real_time | vm | fix vs base | -56.18% [-64.75, -45.51] | 5 | 13065685.50 |
| bmFlushContended/100000/0/2/real_time | vm | fix vs base | -53.18% [-57.89, -47.94] | 5 | 12675281.55 |
| bmFlushContended/100000/1/0/real_time | vm | fix vs base | -53.80% [-59.35, -47.50] | 5 | 13220176.48 |
| bmFlushContended/100000/1/1/real_time | vm | fix vs base | -52.41% [-58.01, -46.06] | 5 | 13515183.49 |
| bmFlushContended/100000/1/2/real_time | vm | fix vs base | -53.14% [-54.97, -51.23] | 5 | 13353718.38 |
| bmFlushContended/100000/4/0/real_time | vm | fix vs base | -52.79% [-56.60, -48.64] | 5 | 13722918.61 |
| bmFlushContended/100000/4/1/real_time | vm | fix vs base | -53.39% [-58.04, -48.23] | 5 | 15566843.56 |
| bmFlushContended/100000/4/2/real_time | vm | fix vs base | -53.01% [-56.08, -49.73] | 5 | 13937876.30 |
| bmFlushContended/100000/7/0/real_time | vm | fix vs base | -54.47% [-59.45, -48.88] | 5 | 13962060.56 |
| bmFlushContended/100000/7/1/real_time | vm | fix vs base | -52.97% [-56.10, -49.61] | 5 | 15558783.61 |
| bmFlushContended/100000/7/2/real_time | vm | fix vs base | -51.14% [-53.84, -48.27] | 5 | 14079621.64 |
| bmHammerOnly/100000/1/0/real_time | vm | fix vs base | +0.00% [-0.00, +0.00] | 5 | 10000877.37 |
| bmHammerOnly/100000/1/1/real_time | vm | fix vs base | +0.00% [-0.00, +0.00] | 5 | 10000896.16 |
| bmHammerOnly/100000/1/2/real_time | vm | fix vs base | -0.00% [-0.00, +0.00] | 5 | 10000954.57 |
| bmHammerOnly/100000/4/0/real_time | vm | fix vs base | +0.00% [-0.00, +0.00] | 5 | 10000592.90 |
| bmHammerOnly/100000/4/1/real_time | vm | fix vs base | +0.00% [-0.00, +0.00] | 5 | 10000582.21 |
| bmHammerOnly/100000/4/2/real_time | vm | fix vs base | +0.00% [-0.00, +0.00] | 5 | 10000548.27 |
| bmHammerOnly/100000/7/0/real_time | vm | fix vs base | +0.00% [-0.00, +0.00] | 5 | 10000648.20 |
| bmHammerOnly/100000/7/1/real_time | vm | fix vs base | -0.00% [-0.00, +0.00] | 5 | 10000605.10 |
| bmHammerOnly/100000/7/2/real_time | vm | fix vs base | +0.00% [-0.00, +0.00] | 5 | 10000601.44 |

## Hammer update rate during and between flushes, share of the hammer-only rate (M6)

Median over rounds. Private-hot is the mode that can show ordering; walk measures memory traffic.

| Arm | Stats | Hammers | Mode | During / hammer-only | Between / hammer-only | Rounds |
|---|---|---|---|---|---|---|
| base | 100000 | 1 | shared-hot | 1.003 | 1.005 | 5 |
| base | 100000 | 1 | walk (memory traffic) | 0.983 | 0.989 | 5 |
| base | 100000 | 1 | private-hot | 0.965 | 0.975 | 5 |
| base | 100000 | 4 | shared-hot | 1.005 | 0.988 | 5 |
| base | 100000 | 4 | walk (memory traffic) | 1.003 | 1.006 | 5 |
| base | 100000 | 4 | private-hot | 1.004 | 1.005 | 5 |
| base | 100000 | 7 | shared-hot | 1.020 | 1.000 | 5 |
| base | 100000 | 7 | walk (memory traffic) | 0.997 | 0.997 | 5 |
| base | 100000 | 7 | private-hot | 1.011 | 1.013 | 5 |
| base-relaxed | 100000 | 1 | shared-hot | 1.005 | 1.008 | 5 |
| base-relaxed | 100000 | 1 | walk (memory traffic) | 0.982 | 1.007 | 5 |
| base-relaxed | 100000 | 1 | private-hot | 0.999 | 1.002 | 5 |
| base-relaxed | 100000 | 4 | shared-hot | 1.000 | 0.974 | 5 |
| base-relaxed | 100000 | 4 | walk (memory traffic) | 1.004 | 1.008 | 5 |
| base-relaxed | 100000 | 4 | private-hot | 1.028 | 1.024 | 5 |
| base-relaxed | 100000 | 7 | shared-hot | 1.016 | 1.000 | 5 |
| base-relaxed | 100000 | 7 | walk (memory traffic) | 0.995 | 1.004 | 5 |
| base-relaxed | 100000 | 7 | private-hot | 0.993 | 1.000 | 5 |
| base-relaxed-p1 | 100000 | 1 | shared-hot | 1.011 | 1.014 | 5 |
| base-relaxed-p1 | 100000 | 1 | walk (memory traffic) | 1.003 | 1.026 | 5 |
| base-relaxed-p1 | 100000 | 1 | private-hot | 0.996 | 1.002 | 5 |
| base-relaxed-p1 | 100000 | 4 | shared-hot | 1.006 | 0.999 | 5 |
| base-relaxed-p1 | 100000 | 4 | walk (memory traffic) | 1.003 | 1.010 | 5 |
| base-relaxed-p1 | 100000 | 4 | private-hot | 0.999 | 1.007 | 5 |
| base-relaxed-p1 | 100000 | 7 | shared-hot | 1.019 | 1.005 | 5 |
| base-relaxed-p1 | 100000 | 7 | walk (memory traffic) | 1.000 | 1.009 | 5 |
| base-relaxed-p1 | 100000 | 7 | private-hot | 1.006 | 1.008 | 5 |
| fix | 100000 | 1 | shared-hot | 1.001 | 1.005 | 5 |
| fix | 100000 | 1 | walk (memory traffic) | 0.978 | 1.007 | 5 |
| fix | 100000 | 1 | private-hot | 0.996 | 1.003 | 5 |
| fix | 100000 | 4 | shared-hot | 1.025 | 1.002 | 5 |
| fix | 100000 | 4 | walk (memory traffic) | 1.003 | 1.013 | 5 |
| fix | 100000 | 4 | private-hot | 1.012 | 1.022 | 5 |
| fix | 100000 | 7 | shared-hot | 1.025 | 1.006 | 5 |
| fix | 100000 | 7 | walk (memory traffic) | 0.998 | 1.008 | 5 |
| fix | 100000 | 7 | private-hot | 0.987 | 0.989 | 5 |
| fix-relaxed | 100000 | 1 | shared-hot | 1.001 | 1.004 | 5 |
| fix-relaxed | 100000 | 1 | walk (memory traffic) | 0.994 | 1.005 | 5 |
| fix-relaxed | 100000 | 1 | private-hot | 0.983 | 0.982 | 5 |
| fix-relaxed | 100000 | 4 | shared-hot | 1.006 | 0.987 | 5 |
| fix-relaxed | 100000 | 4 | walk (memory traffic) | 0.998 | 1.006 | 5 |
| fix-relaxed | 100000 | 4 | private-hot | 0.977 | 0.976 | 5 |
| fix-relaxed | 100000 | 7 | shared-hot | 1.049 | 1.029 | 5 |
| fix-relaxed | 100000 | 7 | walk (memory traffic) | 0.994 | 1.005 | 5 |
| fix-relaxed | 100000 | 7 | private-hot | 1.005 | 1.008 | 5 |
| fix-relaxed-p1 | 100000 | 1 | shared-hot | 0.997 | 1.003 | 5 |
| fix-relaxed-p1 | 100000 | 1 | walk (memory traffic) | 0.995 | 1.013 | 5 |
| fix-relaxed-p1 | 100000 | 1 | private-hot | 0.985 | 0.990 | 5 |
| fix-relaxed-p1 | 100000 | 4 | shared-hot | 1.005 | 0.994 | 5 |
| fix-relaxed-p1 | 100000 | 4 | walk (memory traffic) | 0.998 | 1.005 | 5 |
| fix-relaxed-p1 | 100000 | 4 | private-hot | 0.984 | 0.989 | 5 |
| fix-relaxed-p1 | 100000 | 7 | shared-hot | 1.000 | 0.995 | 5 |
| fix-relaxed-p1 | 100000 | 7 | walk (memory traffic) | 0.989 | 1.006 | 5 |
| fix-relaxed-p1 | 100000 | 7 | private-hot | 1.003 | 1.004 | 5 |

## Shared against per-thread spaced, per arm (H1)

| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |
|---|---|---|---|---|---|

