# rt-n200

- Harness: 0.1.0 9a35ff71ca41
- Window: 2026-11-16T01:54:02Z to 2026-11-16T03:15:53Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1638704,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 16 done (minimum 16, blocks of 8, cap 24, adaptive True), order rotate; stop: widest cycles_total half-width 0.87% (n200-lo d1v4 vs base) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 6 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| base | 8ce942ce56c433e352d2657603d7bf33d4dbb4b4/1.41.0-dev/Clean/RELEASE/BoringSSL | `e59880d7374383c6df4dcaad6c71dd7e` |
| d1v4 | 28f612622a9038858664c9118eba90a2b35d2c96/1.41.0-dev/Clean/RELEASE/BoringSSL | `7fac057ec1629117f7ebcccfbf52b923` |
| d2v3 | patched-build/1.41.0-dev/Clean/RELEASE/BoringSSL | `bf9fd4b39b85602a840480224fe3a1b2` |
| base-A2 | 8ce942ce56c433e352d2657603d7bf33d4dbb4b4/1.41.0-dev/Clean/RELEASE/BoringSSL | `e59880d7374383c6df4dcaad6c71dd7e` |

## n200-lo (`/target/x`, routes, 2000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 16/16 | 143.0k | 258.0k | 113.2k | 370.5k (1.0%) | 250 | 406 | 9.7% |
| d1v4 | 16/16 | 118.7k | 243.2k | 113.1k | 357.1k (1.3%) | 247 | 397 | 9.4% |
| d2v3 | 16/16 | 77.2k | 210.9k | 112.8k | 323.8k (1.0%) | 232 | 366 | 8.8% |
| base-A2 | 16/16 | 143.0k | 257.2k | 112.5k | 369.5k (1.2%) | 249 | 394 | 9.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d1v4 vs base | instructions:u / req | exploratory | -16.97% [-16.98, -16.96] | 0.01 | - | 0.02 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:u / req | exploratory | -5.61% [-6.41, -4.80] | 0.86 | - | 1.61 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:k / req | exploratory | +0.69% [-0.94, +2.34] | 1.63 | - | 3.05 | 16 | 5/16 | 0.210 | 0.252 | - | exploratory |
| d1v4 vs base | cycles (u+k) / req | primary | -3.67% [-4.51, -2.83] | 0.87 | - | 1.63 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| d1v4 vs base | p50 latency (us) | exploratory | -1.87% [-2.70, -1.02] | 0.85 | - | 1.60 | 16 | 15/16 | 0.001 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | p99 latency (us) | exploratory | -1.73% [-3.24, -0.20] | 1.55 | - | 2.91 | 16 | 12/16 | 0.077 | 0.039 | - | exploratory: interval excludes 0 |
| d2v3 vs base | instructions:u / req | exploratory | -46.01% [-46.01, -46.01] | 0.01 | - | 0.01 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:u / req | exploratory | -17.90% [-18.45, -17.35] | 0.67 | - | 1.26 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:k / req | exploratory | -0.49% [-1.99, +1.03] | 1.52 | - | 2.86 | 16 | 8/16 | 1.000 | 0.744 | - | exploratory |
| d2v3 vs base | cycles (u+k) / req | primary | -12.56% [-13.16, -11.96] | 0.69 | - | 1.29 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| d2v3 vs base | p50 latency (us) | exploratory | -7.19% [-8.00, -6.37] | 0.88 | - | 1.64 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | p99 latency (us) | exploratory | -9.09% [-10.20, -7.97] | 1.23 | - | 2.30 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| base-A2 vs base | instructions:u / req | exploratory | -0.00% [-0.01, +0.01] | 0.01 | - | 0.02 | 16 | 7/16 | 0.804 | 0.821 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | -0.07% [-0.70, +0.55] | 0.63 | - | 1.18 | 16 | 7/16 | 0.804 | 0.821 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | -0.47% [-2.14, +1.23] | 1.69 | - | 3.18 | 16 | 10/16 | 0.454 | 0.528 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | -0.19% [-0.95, +0.57] | 0.76 | - | 1.43 | 16 | 9/16 | 0.804 | 0.669 | 1.000 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | -0.12% [-0.82, +0.57] | 0.70 | - | 1.31 | 16 | 10/16 | 0.454 | 0.597 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | -0.91% [-2.10, +0.30] | 1.21 | - | 2.27 | 16 | 11/16 | 0.210 | 0.252 | - | exploratory |

## n200-hi (`/target/x`, routes, 22000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 16/16 | 142.4k | 175.2k | 63.4k | 238.6k (0.7%) | 233 | 530 | 58.5% |
| d1v4 | 16/16 | 118.2k | 164.2k | 64.5k | 228.7k (1.0%) | 216 | 462 | 56.1% |
| d2v3 | 16/16 | 76.7k | 136.2k | 65.8k | 201.8k (0.9%) | 177 | 359 | 50.0% |
| base-A2 | 16/16 | 142.4k | 174.8k | 63.6k | 238.7k (1.1%) | 230 | 521 | 58.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d1v4 vs base | instructions:u / req | exploratory | -17.00% [-17.02, -16.97] | 0.03 | - | 0.05 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:u / req | exploratory | -6.50% [-7.20, -5.80] | 0.75 | - | 1.40 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:k / req | exploratory | +1.56% [+0.81, +2.31] | 0.74 | - | 1.38 | 16 | 2/16 | 0.004 | 0.001 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles (u+k) / req | primary | -4.36% [-5.00, -3.72] | 0.67 | - | 1.26 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| d1v4 vs base | p50 latency (us) | exploratory | -7.25% [-9.11, -5.36] | 2.02 | - | 3.80 | 16 | 15/16 | 0.001 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | p99 latency (us) | exploratory | -10.58% [-16.84, -3.84] | 7.26 | - | 13.63 | 16 | 12/16 | 0.077 | 0.009 | - | exploratory: interval excludes 0 |
| d2v3 vs base | instructions:u / req | exploratory | -46.12% [-46.13, -46.10] | 0.03 | - | 0.05 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:u / req | exploratory | -22.15% [-22.70, -21.60] | 0.71 | - | 1.33 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:k / req | exploratory | +3.66% [+2.99, +4.34] | 0.65 | - | 1.22 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles (u+k) / req | primary | -15.29% [-15.79, -14.79] | 0.59 | - | 1.10 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| d2v3 vs base | p50 latency (us) | exploratory | -23.87% [-26.02, -21.65] | 2.87 | - | 5.38 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | p99 latency (us) | exploratory | -30.21% [-34.19, -25.99] | 5.88 | - | 11.03 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| base-A2 vs base | instructions:u / req | exploratory | +0.01% [-0.01, +0.03] | 0.02 | - | 0.03 | 16 | 8/16 | 1.000 | 0.597 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | -0.32% [-1.10, +0.47] | 0.79 | - | 1.48 | 16 | 9/16 | 0.804 | 0.495 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | +0.14% [-0.96, +1.26] | 1.10 | - | 2.07 | 16 | 10/16 | 0.454 | 0.980 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | -0.20% [-0.99, +0.61] | 0.80 | - | 1.51 | 16 | 8/16 | 1.000 | 0.669 | 1.000 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | -1.39% [-2.90, +0.15] | 1.55 | - | 2.90 | 16 | 10/16 | 0.454 | 0.058 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | +1.05% [-5.59, +8.16] | 6.80 | - | 12.76 | 16 | 8/16 | 1.000 | 0.980 | - | exploratory |

## Validity

128 legs run, 128 valid; 0 legs superseded by a re-run of their round.

