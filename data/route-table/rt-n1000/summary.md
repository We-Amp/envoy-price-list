# rt-n1000

- Harness: 0.1.0 9a35ff71ca41
- Window: 2026-11-16T00:31:58Z to 2026-11-16T01:54:02Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1862203,2294576,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 16 done (minimum 16, blocks of 8, cap 24, adaptive True), order rotate; stop: widest cycles_total half-width 1.15% (n1000-lo d1v4 vs base) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 6 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| base | 8ce942ce56c433e352d2657603d7bf33d4dbb4b4/1.41.0-dev/Clean/RELEASE/BoringSSL | `e59880d7374383c6df4dcaad6c71dd7e` |
| d1v4 | 28f612622a9038858664c9118eba90a2b35d2c96/1.41.0-dev/Clean/RELEASE/BoringSSL | `7fac057ec1629117f7ebcccfbf52b923` |
| d2v3 | patched-build/1.41.0-dev/Clean/RELEASE/BoringSSL | `bf9fd4b39b85602a840480224fe3a1b2` |
| base-A2 | 8ce942ce56c433e352d2657603d7bf33d4dbb4b4/1.41.0-dev/Clean/RELEASE/BoringSSL | `e59880d7374383c6df4dcaad6c71dd7e` |

## n1000-lo (`/target/x`, routes, 2000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 16/16 | 410.9k | 407.7k | 118.3k | 526.4k (1.6%) | 315 | 537 | 12.8% |
| d1v4 | 16/16 | 290.3k | 348.3k | 114.7k | 462.8k (1.4%) | 292 | 489 | 11.7% |
| d2v3 | 16/16 | 77.2k | 210.9k | 113.2k | 325.1k (0.9%) | 233 | 368 | 8.8% |
| base-A2 | 16/16 | 410.9k | 403.1k | 115.6k | 517.3k (1.4%) | 313 | 535 | 12.8% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d1v4 vs base | instructions:u / req | exploratory | -29.34% [-29.35, -29.33] | 0.02 | - | 0.03 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:u / req | exploratory | -14.29% [-15.08, -13.50] | 0.92 | - | 1.73 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:k / req | exploratory | -1.23% [-3.40, +1.00] | 2.23 | - | 4.18 | 16 | 8/16 | 1.000 | 0.404 | - | exploratory |
| d1v4 vs base | cycles (u+k) / req | primary | -11.37% [-12.39, -10.34] | 1.15 | - | 2.17 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| d1v4 vs base | p50 latency (us) | exploratory | -7.15% [-8.03, -6.26] | 0.95 | - | 1.78 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | p99 latency (us) | exploratory | -8.92% [-10.51, -7.31] | 1.75 | - | 3.29 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | instructions:u / req | exploratory | -81.21% [-81.21, -81.21] | 0.01 | - | 0.02 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:u / req | exploratory | -47.93% [-48.46, -47.39] | 1.03 | - | 1.93 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:k / req | exploratory | -2.55% [-4.17, -0.91] | 1.67 | - | 3.14 | 16 | 12/16 | 0.077 | 0.006 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles (u+k) / req | primary | -37.79% [-38.37, -37.20] | 0.94 | - | 1.77 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| d2v3 vs base | p50 latency (us) | exploratory | -25.63% [-26.12, -25.13] | 0.67 | - | 1.25 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | p99 latency (us) | exploratory | -31.34% [-32.33, -30.32] | 1.46 | - | 2.75 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| base-A2 vs base | instructions:u / req | exploratory | +0.00% [-0.01, +0.02] | 0.01 | - | 0.03 | 16 | 7/16 | 0.804 | 0.940 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | -0.54% [-1.43, +0.37] | 0.91 | - | 1.70 | 16 | 9/16 | 0.804 | 0.495 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | -0.43% [-2.44, +1.62] | 2.04 | - | 3.83 | 16 | 7/16 | 0.804 | 0.744 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | -0.51% [-1.53, +0.52] | 1.04 | - | 1.94 | 16 | 8/16 | 1.000 | 0.782 | 0.617 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | -0.13% [-0.80, +0.55] | 0.67 | - | 1.27 | 16 | 6/16 | 0.454 | 1.000 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | -0.42% [-1.74, +0.91] | 1.33 | - | 2.49 | 16 | 8/16 | 1.000 | 0.562 | - | exploratory |

## n1000-hi (`/target/x`, routes, 16000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 16/16 | 410.3k | 314.9k | 63.1k | 378.3k (1.2%) | 397 | 1024 | 66.5% |
| d1v4 | 16/16 | 289.9k | 271.6k | 66.0k | 338.2k (1.2%) | 319 | 778 | 59.5% |
| d2v3 | 16/16 | 76.9k | 148.4k | 72.3k | 220.8k (1.0%) | 167 | 330 | 39.9% |
| base-A2 | 16/16 | 410.3k | 315.6k | 63.3k | 378.9k (1.1%) | 384 | 1022 | 66.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d1v4 vs base | instructions:u / req | exploratory | -29.36% [-29.37, -29.34] | 0.03 | - | 0.05 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:u / req | exploratory | -14.08% [-14.66, -13.49] | 0.68 | - | 1.28 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:k / req | exploratory | +4.57% [+3.09, +6.07] | 1.42 | - | 2.67 | 16 | 1/16 | 0.001 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles (u+k) / req | primary | -10.98% [-11.67, -10.28] | 0.78 | - | 1.46 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| d1v4 vs base | p50 latency (us) | exploratory | -21.14% [-25.36, -16.67] | 5.51 | - | 10.34 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | p99 latency (us) | exploratory | -23.32% [-29.94, -16.08] | 9.03 | - | 16.94 | 16 | 15/16 | 0.001 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | instructions:u / req | exploratory | -81.26% [-81.26, -81.26] | 0.02 | - | 0.03 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:u / req | exploratory | -52.90% [-53.21, -52.60] | 0.65 | - | 1.21 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:k / req | exploratory | +15.10% [+13.61, +16.61] | 1.30 | - | 2.45 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles (u+k) / req | primary | -41.60% [-41.99, -41.22] | 0.65 | - | 1.23 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| d2v3 vs base | p50 latency (us) | exploratory | -58.99% [-60.94, -56.96] | 4.85 | - | 9.10 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | p99 latency (us) | exploratory | -68.52% [-69.89, -67.08] | 4.46 | - | 8.37 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| base-A2 vs base | instructions:u / req | exploratory | +0.00% [-0.02, +0.02] | 0.02 | - | 0.04 | 16 | 7/16 | 0.804 | 0.821 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | +0.07% [-0.61, +0.74] | 0.67 | - | 1.26 | 16 | 7/16 | 0.804 | 0.860 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | +0.56% [-1.35, +2.51] | 1.92 | - | 3.60 | 16 | 6/16 | 0.454 | 0.323 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | +0.15% [-0.68, +0.98] | 0.83 | - | 1.55 | 16 | 7/16 | 0.804 | 0.706 | 0.707 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | -1.26% [-9.62, +7.88] | 8.85 | - | 16.61 | 16 | 10/16 | 0.454 | 0.632 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | +0.86% [-6.33, +8.61] | 7.40 | - | 13.89 | 16 | 8/16 | 1.000 | 0.821 | - | exploratory |

## Validity

128 legs run, 128 valid; 0 legs superseded by a re-run of their round.

