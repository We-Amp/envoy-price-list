# Stats flush row

## Runs

- m-10k: 16 legs, 0 invalid; 4 complete rounds
- m-100k: 16 legs, 0 invalid; 4 complete rounds
- m-300k: 16 legs, 0 invalid; 4 complete rounds
- m-1m: 16 legs, 0 invalid; 4 complete rounds
- w: 32 legs, 0 invalid; 8 complete rounds
- s-100k: 55 legs, 1 invalid; 10 complete rounds
- s-1m: 64 legs, 0 invalid; 8 complete rounds
- sw: 50 legs, 0 invalid; 10 complete rounds

## Calibration (rungs)

| Rung | Clusters | N | Used | Used counter and gauge lines | Share of N sent as statsd lines |
|---|---|---|---|---|---|
| 10k | 100 | 12196 | 3702 | 3193 | 26.2% |
| 100k | 1000 | 118396 | 36103 | 31094 | 26.3% |
| 300k | 3000 | 354396 | 108105 | 93096 | 26.3% |
| 1m | 10000 | 1180396 | 360107 | 310098 | 26.3% |
| 3m | 30000 | 3540396 | 1080112 | 930103 | 26.3% |

## The curve (run M): main-thread price of a flush

Paired by round against flush-off (same wall time); milliseconds always beside cycles. Derived: share of one core at the default 5 s interval, d / 5 s capped at 1: flushes start one interval apart whatever they take (measured), so a flush longer than the interval keeps the main thread busy all the time.

| Rung | N | Arm | ms per flush [95% CI] | M cycles per flush [95% CI] | Share of a core at 5 s (derived) | Stall p50 / max (ms) | /ready max (ms) | VmHWM (MB) |
|---|---|---|---|---|---|---|---|---|
| 10k | 12196 | nosink | 1.39 [1.26, 1.52] | 2.95 [2.88, 3.01] | 0.028% | - / 0 | 1 | 77 |
| 10k | 12196 | statsd | 23.07 [22.37, 23.77] | 52.70 [50.93, 54.46] | 0.461% | 40 / 40 | 1 | 77 |
| 10k | 12196 | nosink-A2 | 1.37 [1.31, 1.44] | 3.01 [2.92, 3.10] | 0.027% | - / 0 | 1 | 77 |
| 100k | 118396 | nosink | 12.73 [12.56, 12.91] | 29.16 [28.50, 29.82] | 0.255% | 20 / 40 | 1 | 163 |
| 100k | 118396 | statsd | 223.73 [216.19, 231.28] | 513.99 [497.13, 530.85] | 4.475% | 235 / 260 | 209 | 162 |
| 100k | 118396 | nosink-A2 | 12.93 [12.66, 13.20] | 29.49 [29.00, 29.98] | 0.259% | 20 / 40 | 1 | 163 |
| 300k | 354396 | nosink | 66.19 [63.56, 68.83] | 152.04 [146.80, 157.28] | 1.324% | 80 / 120 | 59 | 326 |
| 300k | 354396 | statsd | 706.42 [687.90, 724.93] | 1623.88 [1581.46, 1666.31] | 14.128% | 725 / 780 | 642 | 326 |
| 300k | 354396 | nosink-A2 | 66.68 [64.41, 68.95] | 152.74 [146.75, 158.73] | 1.334% | 80 / 120 | 1 | 327 |
| 1m | 1180396 | nosink | 271.29 [264.95, 277.62] | 623.46 [608.57, 638.35] | 5.426% | 280 / 320 | 231 | 871 |
| 1m | 1180396 | statsd | 2430.01 [2342.64, 2517.39] | 5579.06 [5393.48, 5764.64] | 48.600% | 2450 / 2520 | 2422 | 879 |
| 1m | 1180396 | nosink-A2 | 270.48 [260.95, 280.02] | 621.38 [600.30, 642.46] | 5.410% | 285 / 340 | 248 | 870 |

### Fit cost = a + b N (with an intercept; N and the cluster count are collinear here)

- nosink: a = -10.677 ms, b = 0.237 us per stat (27.9 us per cluster of the stock mix); largest measured rung 1180396 stats, nothing beyond it
  scaling exponents (log cost against log N, exploratory): 12196->118396: 0.97; 118396->354396: 1.50; 354396->1180396: 1.17
- statsd: a = -15.375 ms, b = 2.068 us per stat (244.2 us per cluster of the stock mix); largest measured rung 1180396 stats, nothing beyond it
  scaling exponents (log cost against log N, exploratory): 12196->118396: 1.00; 118396->354396: 1.05; 354396->1180396: 1.03

## A/A per rung (nosink-A2 against nosink, main-thread run time per second)

| Rung | Half-width | Reach | Target 2% met |
|---|---|---|---|
| 10k | 3.06 | 3.63 | no |
| 100k | 2.28 | 3.64 | no |
| 300k | 0.66 | 1.15 | yes |
| 1m | 5.46 | 5.75 | no |

Session reach (the largest per-rung reach, used as the pooled floor): 5.75%

## Confirmatory rows (Holm over 5 rows)

Run W prediction from run M at 100k: +0.22% -> the nosink row is secondary.

| Row | Shape | Arm vs ref | Effect [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| statsd sink, marginal price per flush | idle-10k | statsd vs nosink | +1559.59% [+1380.52, +1760.33] | [+1380.52, +1760.33] | 4.59e-06 | 4 | differs |
| statsd sink, marginal price per flush | idle-100k | statsd vs nosink | +1657.12% [+1593.31, +1723.34] | [+1593.31, +1723.34] | 5.88e-07 | 4 | differs |
| statsd sink, marginal price per flush | idle-300k | statsd vs nosink | +967.36% [+913.90, +1023.64] | [+913.90, +1023.64] | 2.1e-06 | 4 | differs |
| statsd sink, marginal price per flush | idle-1m | statsd vs nosink | +795.64% [+749.15, +844.68] | [+749.15, +844.68] | 2.1e-06 | 4 | differs |
| statsd sink, per-request cost on the workers (cycles per request) | s | statsd vs flush-off | +19.93% [+18.23, +21.64] | [+18.23, +21.64] | 5.62e-08 | 8 | differs |

## Secondary rows (Holm over 6 rows)

| Row | Shape | Arm vs ref | Effect [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| the flush, effect on request work | s | nosink vs flush-off | +0.33% [-0.43, +1.10] | [-0.59, +1.26] | 1 | 8 | under the larger of 1% and the A/A reach (1.00%): not a finding; at most +1.26% (widened upper end) |
| A/A, loaded | s | flush-off-A2 vs flush-off | -0.18% [-1.06, +0.71] | [-1.17, +0.81] | 1 | 8 | under the larger of 1% and the A/A reach (1.00%): not a finding |
| A/A | idle-10k | nosink-A2 vs nosink | -0.57% [-3.56, +2.52] | [-3.56, +2.52] | 1 | 4 | under the larger of 1% and the A/A reach (3.63%): not a finding |
| A/A | idle-100k | nosink-A2 vs nosink | +1.38% [-0.90, +3.71] | [-0.90, +3.71] | 0.759 | 4 | under the larger of 1% and the A/A reach (3.64%): not a finding |
| A/A | idle-300k | nosink-A2 vs nosink | +0.49% [-0.17, +1.16] | [-0.29, +1.28] | 0.585 | 4 | under the larger of 1% and the A/A reach (1.15%): not a finding |
| A/A | idle-1m | nosink-A2 vs nosink | -0.28% [-5.58, +5.32] | [-5.58, +5.32] | 1 | 4 | under the larger of 1% and the A/A reach (5.75%): not a finding |

## Run S: the sinks (Holm over 9 rows; per-flush prices from each leg's quiescent span)

Each sink against nosink at its own interval (at 1M: statsd and dogstatsd-buf against nosink-5s, otlp against nosink-20s); a finding must clear the larger of 1% and the A/A reach at the reference's interval (at 1M the 5 s copy nosink-5s-A2; the 20 s rows use that 5 s reach). Under load (sw): total cycles per request against nosink at the default 5 s interval.

| Row | Shape | Arm vs ref | Effect [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| statsd per flush | idle-100k | statsd vs nosink | +1898.93% [+1847.74, +1951.46] | [+1847.74, +1951.46] | 0 | 10 | differs |
| dogstatsd-buf per flush | idle-100k | dogstatsd-buf vs nosink | +553.36% [+542.28, +564.63] | [+542.28, +564.63] | 0 | 10 | differs |
| otlp per flush | idle-100k | otlp vs nosink | +837.11% [+823.21, +851.23] | [+823.21, +851.23] | 0 | 10 | differs |
| A/A 1 s (span, per flush) | idle-100k | nosink-A2 vs nosink | +1.43% [-0.85, +3.77] | [-0.85, +3.77] | - | 10 | under the larger of 1% and the A/A reach (3.70%): not a finding |
| statsd per flush | idle-1m | statsd vs nosink-5s | +815.72% [+793.44, +838.55] | [+793.44, +838.55] | 8.13e-14 | 8 | differs |
| dogstatsd-buf per flush | idle-1m | dogstatsd-buf vs nosink-5s | +250.86% [+243.61, +258.26] | [+243.61, +258.26] | 8.97e-13 | 8 | differs |
| otlp per flush | idle-1m | otlp vs nosink-20s | +376.12% [+360.62, +392.15] | [+360.62, +392.15] | 3.71e-12 | 8 | differs; A/A reach of the 5 s reference (no 20 s copy) |
| A/A 1 s (span, per flush) | idle-1m | nosink-A2 vs nosink | -0.60% [-2.56, +1.41] | [-2.56, +1.41] | - | 8 | under the larger of 1% and the A/A reach (2.60%): not a finding |
| A/A 5 s (span, per flush) | idle-1m | nosink-5s-A2 vs nosink-5s | +1.66% [-0.99, +4.38] | [-0.99, +4.38] | - | 8 | under the larger of 1% and the A/A reach (2.60%): not a finding |
| statsd, cycles per request under load | s | statsd vs nosink | +19.69% [+19.00, +20.39] | [+18.70, +20.69] | 6.15e-13 | 10 | differs |
| dogstatsd-buf, cycles per request under load | s | dogstatsd-buf vs nosink | +17.78% [+16.81, +18.75] | [+16.63, +18.93] | 1.35e-11 | 10 | differs |
| otlp, cycles per request under load | s | otlp vs nosink | +1.66% [+0.85, +2.48] | [+0.69, +2.65] | 0.00119 | 10 | differs |
| A/A, loaded | s | nosink-A2 vs nosink | -0.15% [-0.80, +0.51] | [-1.02, +0.73] | - | 10 | under the larger of 1% and the A/A reach (1.00%): not a finding |

| Row | Shape | Arm ms per flush | Reference ms per flush | Price ms per flush [95% CI] |
|---|---|---|---|---|
| statsd per flush | idle-100k | 220.7 | 11.0 | +209.7 [+206.2, +213.1] |
| dogstatsd-buf per flush | idle-100k | 72.1 | 11.0 | +61.1 [+60.6, +61.6] |
| otlp per flush | idle-100k | 103.5 | 11.0 | +92.4 [+91.7, +93.1] |
| A/A 1 s (span, per flush) | idle-100k | 11.2 | 11.0 | +0.2 [-0.1, +0.4] |
| statsd per flush | idle-1m | 2391.1 | 261.2 | +2129.9 [+2109.0, +2150.8] |
| dogstatsd-buf per flush | idle-1m | 916.2 | 261.2 | +655.0 [+645.7, +664.3] |
| otlp per flush | idle-1m | 1271.0 | 267.0 | +1004.1 [+975.8, +1032.4] |
| A/A 1 s (span, per flush) | idle-1m | 264.9 | 266.5 | -1.6 [-6.9, +3.7] |
| A/A 5 s (span, per flush) | idle-1m | 265.5 | 261.2 | +4.4 [-2.5, +11.3] |

## Observations

- Flush scheduling (measured): flushes start one interval apart whatever they take (1.001 s at 1 s with flushes of 20 to 740 ms); the derived share of a core is d / interval, capped at 1.
- At about 1180396 stats (1M rung) the plain statsd sink at a 1 s interval kept the main thread busy 100% of the time: flushes of about 2.4 s ran back to back (11 whole flushes in 26.5 s), with no drops. Recorded as an observation, not a priced row; the rung's statsd arms run at 5 s.

## Run M-fix: own builds (5e1439980a / 3c9cce2f2c): top (the fix) against main (its base)

Main-thread run time per second and cycles per second at the same interval; the A/A is a second copy of main without a sink. Two own builds, not upstream releases.

| Rung | Arm | main thread ms/s | M cycles/s |
|---|---|---|---|
| 10k | nosink-main | 3.62 | 6.5 |
| 10k | nosink-top | 3.25 | 5.7 |
| 10k | statsd-main | 25.19 | 56.0 |
| 10k | statsd-top | 25.13 | 55.8 |
| 10k | nosink-main-A2 | 3.63 | 6.5 |
| 100k | nosink-main | 15.60 | 34.0 |
| 100k | nosink-top | 11.80 | 25.3 |
| 100k | statsd-main | 221.33 | 506.7 |
| 100k | statsd-top | 224.98 | 515.3 |
| 100k | nosink-main-A2 | 15.66 | 34.1 |
| 1m | nosink-main | 265.62 | 608.9 |
| 1m | nosink-top | 192.78 | 441.2 |
| 1m | statsd-main | 483.82 | 1110.0 |
| 1m | statsd-top | 469.56 | 1077.2 |
| 1m | nosink-main-A2 | 267.38 | 612.9 |

### Fix rows (Holm over 6 rows; a finding must clear the larger of 1% and the rung's own A/A reach)

| Row | Shape | Arm vs ref | Effect [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| own builds (5e1439980a / 3c9cce2f2c), no sink | idle-10k | nosink-top vs nosink-main | -10.26% [-11.93, -8.55] | [-11.93, -8.55] | 0.000449 | 5 | differs |
| own builds (5e1439980a / 3c9cce2f2c), statsd sink | idle-10k | statsd-top vs statsd-main | -0.23% [-4.44, +4.17] | [-4.44, +4.17] | 0.89 | 5 | under the larger of 1% and the A/A reach (3.99%): not a finding |
| own builds (5e1439980a / 3c9cce2f2c), no sink | idle-100k | nosink-top vs nosink-main | -24.39% [-28.83, -19.66] | [-28.83, -19.66] | 0.000858 | 5 | differs |
| own builds (5e1439980a / 3c9cce2f2c), statsd sink | idle-100k | statsd-top vs statsd-main | +1.62% [-1.71, +5.06] | [-1.71, +5.06] | 0.502 | 5 | under the larger of 1% and the A/A reach (4.99%): not a finding |
| own builds (5e1439980a / 3c9cce2f2c), no sink | idle-1m | nosink-top vs nosink-main | -27.41% [-30.22, -24.49] | [-30.22, -24.49] | 0.000138 | 5 | differs |
| own builds (5e1439980a / 3c9cce2f2c), statsd sink | idle-1m | statsd-top vs statsd-main | -2.95% [-4.47, -1.40] | [-4.47, -1.40] | 0.0187 | 5 | under the larger of 1% and the A/A reach (3.87%): not a finding |
| A/A | idle-10k | nosink-main-A2 vs nosink-main | +0.22% [-3.48, +4.07] | [-3.48, +4.07] | - | 5 | A/A half-width 3.77%, reach 3.99% |
| A/A | idle-100k | nosink-main-A2 vs nosink-main | +0.29% [-4.31, +5.11] | [-4.31, +5.11] | - | 5 | A/A half-width 4.70%, reach 4.99% |
| A/A | idle-1m | nosink-main-A2 vs nosink-main | +0.66% [-2.53, +3.95] | [-2.53, +3.95] | - | 5 | A/A half-width 3.21%, reach 3.87% |

## Exploratory

- run W flushes counted in the window, by arm: flush-off [0, 0, 0, 0, 0, 0, 0, 0], flush-off-A2 [0, 0, 0, 0, 0, 0, 0, 0], nosink [4, 4, 4, 4, 4, 4, 4, 4], statsd [4, 4, 4, 4, 4, 4, 4, 4]
- run W statsd datagrams per request: 4.21
- run W worker-only cycles per request: flush-off 516.6k, nosink 516.1k, statsd 599.1k
- 10k nosink: main thread user / kernel cycles per second 4.5M / 1.9M
- 10k statsd: main thread user / kernel cycles per second 16.3M / 39.9M; datagrams per flush 3213
- 100k nosink: main thread user / kernel cycles per second 30.5M / 2.1M
- 100k statsd: main thread user / kernel cycles per second 147.7M / 369.1M; datagrams per flush 31112
- 300k nosink: main thread user / kernel cycles per second 151.5M / 3.7M
- 300k statsd: main thread user / kernel cycles per second 529.0M / 1095.4M; datagrams per flush 93104
- 1m nosink: main thread user / kernel cycles per second 617.7M / 8.1M
- 1m statsd: main thread user / kernel cycles per second 379.3M / 739.2M; datagrams per flush 310152
- 100k otlp: other threads' run time 2.36 ms/s beside the main thread
- 1m otlp: other threads' run time 2.25 ms/s beside the main thread

