# f3-mtls: primary cycles_total_all, rounds 8

## shape s

| arm | valid | median cycles_total_all |
|---|---|---|
| one-ppd | 8/8 | 522.7k |
| pair | 8/8 | 1039.9k |
| pair-A2 | 8/8 | 1043.6k |
| pair-mtls | 8/8 | 1108.6k |

| comparison (cycles_total_all) | effect [95% t] | widened +/- (log-%) | holm p | won | status | arm med | ref med |
|---|---|---|---|---|---|---|---|
| pair vs one-ppd | +98.73% [+96.70, +100.78] | 1.08 | 4.3e-13 | 0/8 | differs | 1039.9k | 522.7k |
| pair-A2 vs one-ppd | +98.89% [+96.95, +100.84] | 1.05 | 3.76e-13 | 0/8 | differs | 1043.6k | 522.7k |
| pair-mtls vs one-ppd | +111.46% [+110.05, +112.88] | 0.87 | 1.73e-14 | 0/8 | differs | 1108.6k | 522.7k |
| pair-A2 vs pair | +0.08% [-0.45, +0.62] | 0.80 | 0.731 | 3/8 | not resolved | 1043.6k | 1039.9k |
| pair-mtls vs pair | +6.40% [+5.90, +6.92] | 0.78 | 3.08e-08 | 0/8 | differs | 1108.6k | 1039.9k |
| pair-mtls vs pair-A2 | +6.32% [+5.54, +7.10] | 0.90 | 4.19e-07 | 0/8 | differs | 1108.6k | 1043.6k |

## confirmatory rows, Holm over 3 (plan)

| row | effect | log-%% [95%% t] | widened +/- | t p | Holm p |
|---|---|---|---|---|---|
| pair-mtls vs one-ppd | +111.46% | +74.88 [+74.22, +75.55] | 0.87 | 2.89e-15 | 8.66e-15 |
| pair vs one-ppd | +98.73% | +68.68 [+67.65, +69.71] | 1.08 | 1.07e-13 | 2.15e-13 |
| pair-mtls vs pair | +6.40% | +6.21 [+5.73, +6.69] | 0.78 | 1.03e-08 | 1.03e-08 |
