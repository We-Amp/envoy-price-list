# f2-grpc: primary cycles_total, rounds 8

## shape g

| arm | valid | median cycles_total |
|---|---|---|
| grpc | 8/8 | 711.6k |
| grpc-A2 | 8/8 | 716.0k |
| grpc-og | 8/8 | 775.7k |
| grpc-stats | 8/8 | 767.7k |

| comparison (cycles_total) | effect [95% t] | widened +/- (log-%) | holm p | won | status | arm med | ref med |
|---|---|---|---|---|---|---|---|
| grpc-A2 vs grpc | +0.62% [-2.48, +3.82] | 2.68 | 0.654 | 5/8 | not resolved | 716.0k | 711.6k |
| grpc-stats vs grpc | +6.14% [+2.84, +9.54] | 2.70 | 0.00878 | 1/8 | differs | 767.7k | 711.6k |
| grpc-og vs grpc | +8.72% [+6.26, +11.24] | 2.01 | 0.000336 | 0/8 | differs | 775.7k | 711.6k |
| grpc-stats vs grpc-A2 | +5.48% [+2.95, +8.07] | 2.12 | 0.00501 | 0/8 | differs | 767.7k | 716.0k |
| grpc-og vs grpc-A2 | +8.05% [+5.39, +10.78] | 2.17 | 0.000782 | 0/8 | differs | 775.7k | 716.0k |
| grpc-og vs grpc-stats | +2.43% [+0.54, +4.36] | 1.68 | 0.0371 | 0/8 | differs | 775.7k | 767.7k |

## confirmatory rows, Holm over 3 (plan)

| row | effect | log-%% [95%% t] | widened +/- | t p | Holm p |
|---|---|---|---|---|---|
| grpc-og vs grpc | +8.72% | +8.36 [+6.07, +10.65] | 2.01 | 5.6e-05 | 0.000168 |
| grpc-stats vs grpc | +6.14% | +5.96 [+2.80, +9.11] | 2.70 | 0.00293 | 0.00585 |
