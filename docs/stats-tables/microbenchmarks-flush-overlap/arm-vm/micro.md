# Stats microbenchmarks (mt-micro-arm-vm)

Time per iteration, median of the repetitions per round; paired log ratio over the rounds with a 95% t interval (negative: the arm is faster). Binaries unchanged during the run: None.

## Arm against arm

| Benchmark | Placement | Arm vs ref | Effect [95% CI] | Rounds | Ref ns |
|---|---|---|---|---|---|
| bmFlushContended/100000/0/0/real_time | vm | fix-relaxed vs fix | -4.63% [-8.47, -0.63] | 3 (descriptive) | 7853970.66 |
| bmFlushContended/100000/0/1/real_time | vm | fix-relaxed vs fix | -4.20% [-8.19, -0.03] | 3 (descriptive) | 7875329.15 |
| bmFlushContended/100000/0/2/real_time | vm | fix-relaxed vs fix | -4.03% [-7.46, -0.48] | 3 (descriptive) | 7864165.24 |
| bmFlushContended/100000/1/0/real_time | vm | fix-relaxed vs fix | -4.42% [-10.64, +2.24] | 3 (descriptive) | 7866252.27 |
| bmFlushContended/100000/1/1/real_time | vm | fix-relaxed vs fix | -5.42% [-9.63, -1.02] | 3 (descriptive) | 8480459.36 |
| bmFlushContended/100000/1/2/real_time | vm | fix-relaxed vs fix | -4.10% [-7.86, -0.18] | 3 (descriptive) | 7869965.60 |
| bmFlushContended/100000/12/0/real_time | vm | fix-relaxed vs fix | -4.19% [-8.50, +0.32] | 3 (descriptive) | 7868897.24 |
| bmFlushContended/100000/12/1/real_time | vm | fix-relaxed vs fix | -5.39% [-11.49, +1.14] | 3 (descriptive) | 24326347.97 |
| bmFlushContended/100000/12/2/real_time | vm | fix-relaxed vs fix | -4.34% [-7.26, -1.33] | 3 (descriptive) | 7893891.51 |
| bmFlushContended/100000/15/0/real_time | vm | fix-relaxed vs fix | -4.03% [-8.72, +0.92] | 3 (descriptive) | 7902272.35 |
| bmFlushContended/100000/15/1/real_time | vm | fix-relaxed vs fix | -4.43% [-7.09, -1.70] | 3 (descriptive) | 26576383.12 |
| bmFlushContended/100000/15/2/real_time | vm | fix-relaxed vs fix | -4.56% [-7.94, -1.06] | 3 (descriptive) | 7916450.57 |
| bmFlushContended/100000/4/0/real_time | vm | fix-relaxed vs fix | -4.11% [-8.02, -0.03] | 3 (descriptive) | 7863356.57 |
| bmFlushContended/100000/4/1/real_time | vm | fix-relaxed vs fix | -8.60% [-15.21, -1.48] | 3 (descriptive) | 11701946.40 |
| bmFlushContended/100000/4/2/real_time | vm | fix-relaxed vs fix | -3.64% [-8.99, +2.03] | 3 (descriptive) | 7872713.32 |
| bmFlushContended/100000/7/0/real_time | vm | fix-relaxed vs fix | -3.74% [-8.63, +1.41] | 3 (descriptive) | 7867375.51 |
| bmFlushContended/100000/7/1/real_time | vm | fix-relaxed vs fix | -4.38% [-13.40, +5.58] | 3 (descriptive) | 17281317.44 |
| bmFlushContended/100000/7/2/real_time | vm | fix-relaxed vs fix | -4.41% [-8.75, +0.14] | 3 (descriptive) | 7884087.93 |
| bmHammerOnly/100000/1/0/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10001153.39 |
| bmHammerOnly/100000/1/1/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10001160.67 |
| bmHammerOnly/100000/1/2/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10001147.73 |
| bmHammerOnly/100000/12/0/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000727.64 |
| bmHammerOnly/100000/12/1/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000820.40 |
| bmHammerOnly/100000/12/2/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000957.96 |
| bmHammerOnly/100000/15/0/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000768.59 |
| bmHammerOnly/100000/15/1/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000884.71 |
| bmHammerOnly/100000/15/2/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10001029.44 |
| bmHammerOnly/100000/4/0/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000727.04 |
| bmHammerOnly/100000/4/1/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000730.93 |
| bmHammerOnly/100000/4/2/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000741.51 |
| bmHammerOnly/100000/7/0/real_time | vm | fix-relaxed vs fix | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000722.84 |
| bmHammerOnly/100000/7/1/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000781.14 |
| bmHammerOnly/100000/7/2/real_time | vm | fix-relaxed vs fix | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000804.99 |
| bmFlushContended/100000/0/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +1.20% [-0.50, +2.93] | 3 (descriptive) | 7546411.55 |
| bmFlushContended/100000/0/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.78% [-0.49, +2.06] | 3 (descriptive) | 7578935.34 |
| bmFlushContended/100000/0/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.51% [-0.57, +1.60] | 3 (descriptive) | 7591031.61 |
| bmFlushContended/100000/1/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.71% [-1.24, +2.70] | 3 (descriptive) | 7579263.61 |
| bmFlushContended/100000/1/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -2.23% [-4.78, +0.39] | 3 (descriptive) | 8042138.61 |
| bmFlushContended/100000/1/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.49% [-0.39, +1.38] | 3 (descriptive) | 7570236.96 |
| bmFlushContended/100000/12/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.89% [-0.30, +2.09] | 3 (descriptive) | 7559790.98 |
| bmFlushContended/100000/12/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.43% [-3.95, +3.22] | 3 (descriptive) | 22973005.80 |
| bmFlushContended/100000/12/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.61% [-0.11, +1.33] | 3 (descriptive) | 7587945.42 |
| bmFlushContended/100000/15/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.59% [-0.39, +1.57] | 3 (descriptive) | 7604731.70 |
| bmFlushContended/100000/15/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +2.07% [-1.81, +6.10] | 3 (descriptive) | 25341339.52 |
| bmFlushContended/100000/15/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.81% [-0.05, +1.67] | 3 (descriptive) | 7593353.39 |
| bmFlushContended/100000/4/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.53% [-1.03, +2.12] | 3 (descriptive) | 7591294.61 |
| bmFlushContended/100000/4/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.48% [-2.35, +1.42] | 3 (descriptive) | 10666738.00 |
| bmFlushContended/100000/4/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.04% [-2.31, +2.27] | 3 (descriptive) | 7589835.73 |
| bmFlushContended/100000/7/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.24% [-3.19, +3.79] | 3 (descriptive) | 7590478.11 |
| bmFlushContended/100000/7/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +1.31% [-1.68, +4.40] | 3 (descriptive) | 16451602.95 |
| bmFlushContended/100000/7/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +1.19% [-1.14, +3.58] | 3 (descriptive) | 7558403.12 |
| bmHammerOnly/100000/1/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10001133.60 |
| bmHammerOnly/100000/1/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10001166.47 |
| bmHammerOnly/100000/1/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10001162.80 |
| bmHammerOnly/100000/12/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000738.01 |
| bmHammerOnly/100000/12/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000869.76 |
| bmHammerOnly/100000/12/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000873.74 |
| bmHammerOnly/100000/15/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000744.01 |
| bmHammerOnly/100000/15/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000823.93 |
| bmHammerOnly/100000/15/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000861.31 |
| bmHammerOnly/100000/4/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000722.04 |
| bmHammerOnly/100000/4/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000760.09 |
| bmHammerOnly/100000/4/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000743.49 |
| bmHammerOnly/100000/7/0/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000737.77 |
| bmHammerOnly/100000/7/1/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000774.57 |
| bmHammerOnly/100000/7/2/real_time | vm | fix-relaxed-p1 vs fix-relaxed | +0.00% [+0.00, +0.00] | 3 (descriptive) | 10000780.43 |
| bmFlushContended/100000/0/0/real_time | vm | base-relaxed vs base | -2.87% [-13.06, +8.52] | 2 (descriptive) | 26513180.87 |
| bmFlushContended/100000/0/1/real_time | vm | base-relaxed vs base | -1.47% [-17.09, +17.09] | 2 (descriptive) | 26347609.31 |
| bmFlushContended/100000/0/2/real_time | vm | base-relaxed vs base | -2.65% [-13.89, +10.05] | 2 (descriptive) | 26406412.81 |
| bmFlushContended/100000/1/0/real_time | vm | base-relaxed vs base | -1.04% [-29.85, +39.59] | 2 (descriptive) | 26542894.20 |
| bmFlushContended/100000/1/1/real_time | vm | base-relaxed vs base | -2.54% [-7.73, +2.94] | 2 (descriptive) | 27115008.14 |
| bmFlushContended/100000/1/2/real_time | vm | base-relaxed vs base | -1.46% [-9.11, +6.83] | 2 (descriptive) | 26291305.37 |
| bmFlushContended/100000/12/0/real_time | vm | base-relaxed vs base | -1.56% [-18.50, +18.89] | 2 (descriptive) | 26337004.20 |
| bmFlushContended/100000/12/1/real_time | vm | base-relaxed vs base | -0.56% [-8.35, +7.89] | 2 (descriptive) | 73369336.50 |
| bmFlushContended/100000/12/2/real_time | vm | base-relaxed vs base | -0.37% [-12.15, +12.98] | 2 (descriptive) | 26423799.81 |
| bmFlushContended/100000/15/0/real_time | vm | base-relaxed vs base | -1.20% [-7.93, +6.02] | 2 (descriptive) | 26408542.07 |
| bmFlushContended/100000/15/1/real_time | vm | base-relaxed vs base | -2.22% [-5.22, +0.88] | 2 (descriptive) | 77205619.61 |
| bmFlushContended/100000/15/2/real_time | vm | base-relaxed vs base | -1.60% [-19.21, +19.84] | 2 (descriptive) | 26604228.69 |
| bmFlushContended/100000/4/0/real_time | vm | base-relaxed vs base | -1.96% [-13.82, +11.54] | 2 (descriptive) | 26748372.59 |
| bmFlushContended/100000/4/1/real_time | vm | base-relaxed vs base | +1.71% [-20.68, +30.43] | 2 (descriptive) | 36915366.74 |
| bmFlushContended/100000/4/2/real_time | vm | base-relaxed vs base | -1.27% [-26.25, +32.16] | 2 (descriptive) | 26447063.24 |
| bmFlushContended/100000/7/0/real_time | vm | base-relaxed vs base | -2.23% [-16.33, +14.24] | 2 (descriptive) | 26441392.39 |
| bmFlushContended/100000/7/1/real_time | vm | base-relaxed vs base | -1.01% [-11.16, +10.30] | 2 (descriptive) | 57497937.07 |
| bmFlushContended/100000/7/2/real_time | vm | base-relaxed vs base | -2.70% [-3.76, -1.64] | 2 (descriptive) | 26622136.91 |
| bmHammerOnly/100000/1/0/real_time | vm | base-relaxed vs base | -0.00% [-0.01, +0.01] | 2 (descriptive) | 10001152.66 |
| bmHammerOnly/100000/1/1/real_time | vm | base-relaxed vs base | -0.00% [-0.00, -0.00] | 2 (descriptive) | 10001244.04 |
| bmHammerOnly/100000/1/2/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 2 (descriptive) | 10001154.57 |
| bmHammerOnly/100000/12/0/real_time | vm | base-relaxed vs base | -0.00% [-0.01, +0.01] | 2 (descriptive) | 10000748.54 |
| bmHammerOnly/100000/12/1/real_time | vm | base-relaxed vs base | +0.00% [-0.01, +0.01] | 2 (descriptive) | 10000859.42 |
| bmHammerOnly/100000/12/2/real_time | vm | base-relaxed vs base | +0.00% [-0.01, +0.01] | 2 (descriptive) | 10000797.74 |
| bmHammerOnly/100000/15/0/real_time | vm | base-relaxed vs base | -0.00% [-0.01, +0.01] | 2 (descriptive) | 10000851.86 |
| bmHammerOnly/100000/15/1/real_time | vm | base-relaxed vs base | +0.00% [-0.01, +0.01] | 2 (descriptive) | 10000985.71 |
| bmHammerOnly/100000/15/2/real_time | vm | base-relaxed vs base | -0.00% [-0.02, +0.02] | 2 (descriptive) | 10001072.76 |
| bmHammerOnly/100000/4/0/real_time | vm | base-relaxed vs base | -0.00% [-0.00, +0.00] | 2 (descriptive) | 10000756.63 |
| bmHammerOnly/100000/4/1/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 2 (descriptive) | 10000761.54 |
| bmHammerOnly/100000/4/2/real_time | vm | base-relaxed vs base | -0.00% [-0.00, +0.00] | 2 (descriptive) | 10000747.13 |
| bmHammerOnly/100000/7/0/real_time | vm | base-relaxed vs base | -0.00% [-0.00, +0.00] | 2 (descriptive) | 10000741.33 |
| bmHammerOnly/100000/7/1/real_time | vm | base-relaxed vs base | +0.00% [-0.00, +0.00] | 2 (descriptive) | 10000792.00 |
| bmHammerOnly/100000/7/2/real_time | vm | base-relaxed vs base | -0.00% [-0.00, +0.00] | 2 (descriptive) | 10000767.47 |
| bmFlushContended/100000/0/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +1.88% [-3.50, +7.55] | 3 (descriptive) | 25902882.41 |
| bmFlushContended/100000/0/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +2.77% [-1.27, +6.97] | 3 (descriptive) | 25777140.74 |
| bmFlushContended/100000/0/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +2.67% [-9.23, +16.13] | 3 (descriptive) | 25882554.78 |
| bmFlushContended/100000/1/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +1.40% [-2.37, +5.32] | 3 (descriptive) | 26391336.78 |
| bmFlushContended/100000/1/1/real_time | vm | base-relaxed-p1 vs base-relaxed | -0.07% [-5.33, +5.48] | 3 (descriptive) | 26445870.31 |
| bmFlushContended/100000/1/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +2.69% [-10.71, +18.12] | 3 (descriptive) | 25901670.11 |
| bmFlushContended/100000/12/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +1.35% [-2.85, +5.74] | 3 (descriptive) | 25996554.29 |
| bmFlushContended/100000/12/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +6.45% [+0.44, +12.82] | 3 (descriptive) | 72533417.00 |
| bmFlushContended/100000/12/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +1.36% [-9.34, +13.33] | 3 (descriptive) | 26338322.04 |
| bmFlushContended/100000/15/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +1.62% [-1.70, +5.05] | 3 (descriptive) | 26062355.07 |
| bmFlushContended/100000/15/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +13.85% [+12.94, +14.76] | 3 (descriptive) | 75631494.89 |
| bmFlushContended/100000/15/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +1.16% [-5.68, +8.48] | 3 (descriptive) | 26208169.81 |
| bmFlushContended/100000/4/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.77% [-1.74, +3.35] | 3 (descriptive) | 26118136.70 |
| bmFlushContended/100000/4/1/real_time | vm | base-relaxed-p1 vs base-relaxed | -4.64% [-12.30, +3.69] | 3 (descriptive) | 36834614.21 |
| bmFlushContended/100000/4/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +2.00% [-4.93, +9.44] | 3 (descriptive) | 25818427.67 |
| bmFlushContended/100000/7/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +2.47% [-1.21, +6.29] | 3 (descriptive) | 25929909.04 |
| bmFlushContended/100000/7/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +1.25% [+0.32, +2.19] | 3 (descriptive) | 56491142.20 |
| bmFlushContended/100000/7/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +2.13% [-9.17, +14.84] | 3 (descriptive) | 26038175.08 |
| bmHammerOnly/100000/1/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10001160.37 |
| bmHammerOnly/100000/1/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10001200.16 |
| bmHammerOnly/100000/1/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10001162.61 |
| bmHammerOnly/100000/12/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000739.76 |
| bmHammerOnly/100000/12/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000817.24 |
| bmHammerOnly/100000/12/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000784.20 |
| bmHammerOnly/100000/15/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000888.87 |
| bmHammerOnly/100000/15/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.01, +0.01] | 3 (descriptive) | 10001107.70 |
| bmHammerOnly/100000/15/2/real_time | vm | base-relaxed-p1 vs base-relaxed | -0.00% [-0.00, +0.00] | 3 (descriptive) | 10000927.64 |
| bmHammerOnly/100000/4/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000738.76 |
| bmHammerOnly/100000/4/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000764.71 |
| bmHammerOnly/100000/4/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000750.04 |
| bmHammerOnly/100000/7/0/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000717.83 |
| bmHammerOnly/100000/7/1/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000803.17 |
| bmHammerOnly/100000/7/2/real_time | vm | base-relaxed-p1 vs base-relaxed | +0.00% [-0.00, +0.00] | 3 (descriptive) | 10000743.01 |
| bmFlushContended/100000/0/0/real_time | vm | fix vs base | -69.98% [-75.54, -63.16] | 2 (descriptive) | 26513180.87 |
| bmFlushContended/100000/0/1/real_time | vm | fix vs base | -69.77% [-74.75, -63.81] | 2 (descriptive) | 26347609.31 |
| bmFlushContended/100000/0/2/real_time | vm | fix vs base | -69.88% [-74.42, -64.54] | 2 (descriptive) | 26406412.81 |
| bmFlushContended/100000/1/0/real_time | vm | fix vs base | -69.81% [-80.61, -52.98] | 2 (descriptive) | 26542894.20 |
| bmFlushContended/100000/1/1/real_time | vm | fix vs base | -68.35% [-73.94, -61.57] | 2 (descriptive) | 27115008.14 |
| bmFlushContended/100000/1/2/real_time | vm | fix vs base | -69.79% [-73.51, -65.55] | 2 (descriptive) | 26291305.37 |
| bmFlushContended/100000/12/0/real_time | vm | fix vs base | -69.78% [-76.18, -61.67] | 2 (descriptive) | 26337004.20 |
| bmFlushContended/100000/12/1/real_time | vm | fix vs base | -67.06% [-69.49, -64.45] | 2 (descriptive) | 73369336.50 |
| bmFlushContended/100000/12/2/real_time | vm | fix vs base | -69.85% [-69.91, -69.79] | 2 (descriptive) | 26423799.81 |
| bmFlushContended/100000/15/0/real_time | vm | fix vs base | -69.73% [-74.34, -64.29] | 2 (descriptive) | 26408542.07 |
| bmFlushContended/100000/15/1/real_time | vm | fix vs base | -65.62% [-68.20, -62.81] | 2 (descriptive) | 77205619.61 |
| bmFlushContended/100000/15/2/real_time | vm | fix vs base | -69.94% [-74.40, -64.71] | 2 (descriptive) | 26604228.69 |
| bmFlushContended/100000/4/0/real_time | vm | fix vs base | -70.24% [-75.58, -63.74] | 2 (descriptive) | 26748372.59 |
| bmFlushContended/100000/4/1/real_time | vm | fix vs base | -68.73% [-73.85, -62.61] | 2 (descriptive) | 36915366.74 |
| bmFlushContended/100000/4/2/real_time | vm | fix vs base | -69.92% [-75.13, -63.61] | 2 (descriptive) | 26447063.24 |
| bmFlushContended/100000/7/0/real_time | vm | fix vs base | -69.89% [-76.20, -61.93] | 2 (descriptive) | 26441392.39 |
| bmFlushContended/100000/7/1/real_time | vm | fix vs base | -70.59% [-77.97, -60.75] | 2 (descriptive) | 57497937.07 |
| bmFlushContended/100000/7/2/real_time | vm | fix vs base | -70.04% [-75.49, -63.38] | 2 (descriptive) | 26622136.91 |
| bmHammerOnly/100000/1/0/real_time | vm | fix vs base | +0.00% [-0.00, +0.00] | 2 (descriptive) | 10001152.66 |
| bmHammerOnly/100000/1/1/real_time | vm | fix vs base | -0.00% [-0.01, +0.01] | 2 (descriptive) | 10001244.04 |
| bmHammerOnly/100000/1/2/real_time | vm | fix vs base | +0.00% [-0.00, +0.01] | 2 (descriptive) | 10001154.57 |
| bmHammerOnly/100000/12/0/real_time | vm | fix vs base | -0.00% [-0.00, +0.00] | 2 (descriptive) | 10000748.54 |
| bmHammerOnly/100000/12/1/real_time | vm | fix vs base | +0.00% [-0.01, +0.01] | 2 (descriptive) | 10000859.42 |
| bmHammerOnly/100000/12/2/real_time | vm | fix vs base | +0.00% [-0.01, +0.01] | 2 (descriptive) | 10000797.74 |
| bmHammerOnly/100000/15/0/real_time | vm | fix vs base | -0.00% [-0.00, -0.00] | 2 (descriptive) | 10000851.86 |
| bmHammerOnly/100000/15/1/real_time | vm | fix vs base | -0.00% [-0.01, +0.01] | 2 (descriptive) | 10000985.71 |
| bmHammerOnly/100000/15/2/real_time | vm | fix vs base | -0.00% [-0.02, +0.02] | 2 (descriptive) | 10001072.76 |
| bmHammerOnly/100000/4/0/real_time | vm | fix vs base | -0.00% [-0.00, -0.00] | 2 (descriptive) | 10000756.63 |
| bmHammerOnly/100000/4/1/real_time | vm | fix vs base | -0.00% [-0.00, +0.00] | 2 (descriptive) | 10000761.54 |
| bmHammerOnly/100000/4/2/real_time | vm | fix vs base | +0.00% [-0.01, +0.01] | 2 (descriptive) | 10000747.13 |
| bmHammerOnly/100000/7/0/real_time | vm | fix vs base | -0.00% [-0.00, +0.00] | 2 (descriptive) | 10000741.33 |
| bmHammerOnly/100000/7/1/real_time | vm | fix vs base | -0.00% [-0.01, +0.01] | 2 (descriptive) | 10000792.00 |
| bmHammerOnly/100000/7/2/real_time | vm | fix vs base | +0.00% [-0.00, +0.00] | 2 (descriptive) | 10000767.47 |

## Hammer update rate during and between flushes, share of the hammer-only rate (M6)

Median over rounds. Private-hot is the mode that can show ordering; walk measures memory traffic.

| Arm | Stats | Hammers | Mode | During / hammer-only | Between / hammer-only | Rounds |
|---|---|---|---|---|---|---|
| base | 100000 | 1 | shared-hot | 1.005 | 1.000 | 2 |
| base | 100000 | 1 | walk (memory traffic) | 0.860 | 0.935 | 2 |
| base | 100000 | 1 | private-hot | 1.000 | 1.000 | 2 |
| base | 100000 | 4 | shared-hot | 1.020 | 1.018 | 2 |
| base | 100000 | 4 | walk (memory traffic) | 0.602 | 0.798 | 2 |
| base | 100000 | 4 | private-hot | 1.053 | 1.002 | 2 |
| base | 100000 | 7 | shared-hot | 0.991 | 0.988 | 2 |
| base | 100000 | 7 | walk (memory traffic) | 0.492 | 0.688 | 2 |
| base | 100000 | 7 | private-hot | 1.142 | 1.000 | 2 |
| base | 100000 | 12 | shared-hot | 1.010 | 1.007 | 2 |
| base | 100000 | 12 | walk (memory traffic) | 0.698 | 0.790 | 2 |
| base | 100000 | 12 | private-hot | 1.599 | 1.001 | 2 |
| base | 100000 | 15 | shared-hot | 0.990 | 0.988 | 2 |
| base | 100000 | 15 | walk (memory traffic) | 0.823 | 0.885 | 2 |
| base | 100000 | 15 | private-hot | 1.783 | 1.003 | 2 |
| base-relaxed | 100000 | 1 | shared-hot | 0.998 | 1.000 | 3 |
| base-relaxed | 100000 | 1 | walk (memory traffic) | 0.859 | 0.929 | 3 |
| base-relaxed | 100000 | 1 | private-hot | 1.000 | 1.000 | 3 |
| base-relaxed | 100000 | 4 | shared-hot | 1.001 | 0.999 | 3 |
| base-relaxed | 100000 | 4 | walk (memory traffic) | 0.598 | 0.792 | 3 |
| base-relaxed | 100000 | 4 | private-hot | 1.026 | 1.003 | 3 |
| base-relaxed | 100000 | 7 | shared-hot | 0.997 | 0.999 | 3 |
| base-relaxed | 100000 | 7 | walk (memory traffic) | 0.486 | 0.679 | 3 |
| base-relaxed | 100000 | 7 | private-hot | 1.186 | 1.000 | 3 |
| base-relaxed | 100000 | 12 | shared-hot | 0.996 | 0.998 | 3 |
| base-relaxed | 100000 | 12 | walk (memory traffic) | 0.680 | 0.769 | 3 |
| base-relaxed | 100000 | 12 | private-hot | 1.570 | 1.002 | 3 |
| base-relaxed | 100000 | 15 | shared-hot | 1.003 | 1.006 | 3 |
| base-relaxed | 100000 | 15 | walk (memory traffic) | 0.815 | 0.878 | 3 |
| base-relaxed | 100000 | 15 | private-hot | 1.681 | 1.002 | 3 |
| base-relaxed-p1 | 100000 | 1 | shared-hot | 0.998 | 0.999 | 3 |
| base-relaxed-p1 | 100000 | 1 | walk (memory traffic) | 0.791 | 0.915 | 3 |
| base-relaxed-p1 | 100000 | 1 | private-hot | 1.004 | 1.000 | 3 |
| base-relaxed-p1 | 100000 | 4 | shared-hot | 0.989 | 0.992 | 3 |
| base-relaxed-p1 | 100000 | 4 | walk (memory traffic) | 0.496 | 0.697 | 3 |
| base-relaxed-p1 | 100000 | 4 | private-hot | 1.247 | 1.007 | 3 |
| base-relaxed-p1 | 100000 | 7 | shared-hot | 1.005 | 1.006 | 3 |
| base-relaxed-p1 | 100000 | 7 | walk (memory traffic) | 0.363 | 0.564 | 3 |
| base-relaxed-p1 | 100000 | 7 | private-hot | 1.462 | 0.997 | 3 |
| base-relaxed-p1 | 100000 | 12 | shared-hot | 0.999 | 0.999 | 3 |
| base-relaxed-p1 | 100000 | 12 | walk (memory traffic) | 0.576 | 0.663 | 3 |
| base-relaxed-p1 | 100000 | 12 | private-hot | 1.731 | 0.995 | 3 |
| base-relaxed-p1 | 100000 | 15 | shared-hot | 1.021 | 1.024 | 3 |
| base-relaxed-p1 | 100000 | 15 | walk (memory traffic) | 0.755 | 0.811 | 3 |
| base-relaxed-p1 | 100000 | 15 | private-hot | 1.889 | 1.003 | 3 |
| fix | 100000 | 1 | shared-hot | 0.998 | 1.000 | 3 |
| fix | 100000 | 1 | walk (memory traffic) | 0.863 | 0.984 | 3 |
| fix | 100000 | 1 | private-hot | 1.023 | 0.998 | 3 |
| fix | 100000 | 4 | shared-hot | 0.998 | 0.995 | 3 |
| fix | 100000 | 4 | walk (memory traffic) | 0.602 | 0.827 | 3 |
| fix | 100000 | 4 | private-hot | 1.195 | 1.000 | 3 |
| fix | 100000 | 7 | shared-hot | 0.994 | 0.991 | 3 |
| fix | 100000 | 7 | walk (memory traffic) | 0.512 | 0.736 | 3 |
| fix | 100000 | 7 | private-hot | 1.419 | 1.003 | 3 |
| fix | 100000 | 12 | shared-hot | 0.983 | 0.980 | 3 |
| fix | 100000 | 12 | walk (memory traffic) | 0.653 | 0.781 | 3 |
| fix | 100000 | 12 | private-hot | 1.743 | 1.004 | 3 |
| fix | 100000 | 15 | shared-hot | 1.012 | 1.010 | 3 |
| fix | 100000 | 15 | walk (memory traffic) | 0.779 | 0.879 | 3 |
| fix | 100000 | 15 | private-hot | 1.845 | 1.003 | 3 |
| fix-relaxed | 100000 | 1 | shared-hot | 0.996 | 1.000 | 3 |
| fix-relaxed | 100000 | 1 | walk (memory traffic) | 0.818 | 1.033 | 3 |
| fix-relaxed | 100000 | 1 | private-hot | 1.000 | 1.000 | 3 |
| fix-relaxed | 100000 | 4 | shared-hot | 1.000 | 1.000 | 3 |
| fix-relaxed | 100000 | 4 | walk (memory traffic) | 0.610 | 0.805 | 3 |
| fix-relaxed | 100000 | 4 | private-hot | 1.026 | 1.001 | 3 |
| fix-relaxed | 100000 | 7 | shared-hot | 0.995 | 0.996 | 3 |
| fix-relaxed | 100000 | 7 | walk (memory traffic) | 0.479 | 0.681 | 3 |
| fix-relaxed | 100000 | 7 | private-hot | 1.216 | 1.002 | 3 |
| fix-relaxed | 100000 | 12 | shared-hot | 0.997 | 1.000 | 3 |
| fix-relaxed | 100000 | 12 | walk (memory traffic) | 0.643 | 0.779 | 3 |
| fix-relaxed | 100000 | 12 | private-hot | 1.502 | 1.000 | 3 |
| fix-relaxed | 100000 | 15 | shared-hot | 1.019 | 1.020 | 3 |
| fix-relaxed | 100000 | 15 | walk (memory traffic) | 0.778 | 0.884 | 3 |
| fix-relaxed | 100000 | 15 | private-hot | 1.592 | 1.000 | 3 |
| fix-relaxed-p1 | 100000 | 1 | shared-hot | 0.996 | 1.000 | 3 |
| fix-relaxed-p1 | 100000 | 1 | walk (memory traffic) | 0.786 | 0.959 | 3 |
| fix-relaxed-p1 | 100000 | 1 | private-hot | 1.001 | 1.000 | 3 |
| fix-relaxed-p1 | 100000 | 4 | shared-hot | 1.000 | 1.002 | 3 |
| fix-relaxed-p1 | 100000 | 4 | walk (memory traffic) | 0.478 | 0.677 | 3 |
| fix-relaxed-p1 | 100000 | 4 | private-hot | 1.243 | 0.997 | 3 |
| fix-relaxed-p1 | 100000 | 7 | shared-hot | 0.987 | 0.988 | 3 |
| fix-relaxed-p1 | 100000 | 7 | walk (memory traffic) | 0.366 | 0.539 | 3 |
| fix-relaxed-p1 | 100000 | 7 | private-hot | 1.449 | 0.995 | 3 |
| fix-relaxed-p1 | 100000 | 12 | shared-hot | 0.991 | 0.993 | 3 |
| fix-relaxed-p1 | 100000 | 12 | walk (memory traffic) | 0.530 | 0.662 | 3 |
| fix-relaxed-p1 | 100000 | 12 | private-hot | 1.780 | 1.004 | 3 |
| fix-relaxed-p1 | 100000 | 15 | shared-hot | 1.003 | 1.005 | 3 |
| fix-relaxed-p1 | 100000 | 15 | walk (memory traffic) | 0.700 | 0.799 | 3 |
| fix-relaxed-p1 | 100000 | 15 | private-hot | 1.898 | 1.005 | 3 |

## Shared against per-thread spaced, per arm (H1)

| Benchmark | Threads | Placement | Arm | Shared / spaced [95% CI] | Rounds |
|---|---|---|---|---|---|

