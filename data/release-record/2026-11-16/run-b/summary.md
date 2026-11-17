# release-record-b

- Harness: 0.1.0 e3caa9b1319f
- Window: 2026-11-16T22:26:44Z to 2026-11-17T00:34:51Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1407132,2024903,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 20 done (minimum 20, blocks of 20, cap 20, adaptive False), order rotate; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 8 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| v1.38.0 | f1dd21b16c244bda00edfb5ffce577e12d0d2ec2/1.38.0/Clean/RELEASE/BoringSSL | `909c9394315c4ae97e176bbe20de124f` |
| v1.38.2 | f387231af8dd7274e37c5ae2cc797cb09a948818/1.38.2/Clean/RELEASE/BoringSSL | `0b6768ef490ef6fccc0974bd148fcd16` |
| v1.38.5 | 4be7862a2a6d9a7867f576385d545bb0b47b9181/1.38.5/Clean/RELEASE/BoringSSL | `4aef8fd0b1989fc362b02fa77f1d171c` |
| v1.38.7 | 9b5f29d242e093ab555c8d337127db1d871f5318/1.38.7/Clean/RELEASE/BoringSSL | `cf7e0b6d48b3ad48d06849a18840535a` |
| v1.38.9 | 17e27840396c1fa3196f184fcb5db1ab13850504/1.38.9/Clean/RELEASE/BoringSSL | `2358b9b2f859b5f0f050181e0b295c35` |

## s-hi (`/s`, proxied, 12000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.38.0 | 20/20 | 174.2k | 301.8k | 151.8k | 453.5k (0.7%) | 425 | 939 | 60.8% |
| v1.38.2 | 20/20 | 174.2k | 301.4k | 152.7k | 453.9k (0.8%) | 422 | 960 | 61.0% |
| v1.38.5 | 20/20 | 174.4k | 301.2k | 154.6k | 455.8k (1.1%) | 417 | 898 | 61.1% |
| v1.38.7 | 20/20 | 174.4k | 304.3k | 153.2k | 458.5k (1.1%) | 428 | 987 | 61.4% |
| v1.38.9 | 20/20 | 174.4k | 303.5k | 153.1k | 456.7k (1.1%) | 427 | 957 | 61.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.38.2 vs v1.38.0 | instructions:u / req | exploratory | +0.00% [-0.03, +0.03] | 0.03 | - | 0.06 | 20 | 8/20 | 0.503 | 0.674 | - | exploratory |
| v1.38.2 vs v1.38.0 | cycles:u / req | exploratory | -0.05% [-0.49, +0.38] | 0.44 | - | 0.93 | 20 | 10/20 | 1.000 | 0.869 | - | exploratory |
| v1.38.2 vs v1.38.0 | cycles:k / req | exploratory | +0.99% [+0.46, +1.52] | 0.52 | - | 1.12 | 20 | 2/20 | 0.000 | 0.001 | - | exploratory: interval excludes 0 |
| v1.38.2 vs v1.38.0 | cycles (u+k) / req | primary | +0.29% [-0.14, +0.73] | 0.43 | - | 0.92 | 20 | 6/20 | 0.115 | 0.165 | 0.680 | not resolved |
| v1.38.2 vs v1.38.0 | p50 latency (us) | exploratory | -1.33% [-2.90, +0.27] | 1.61 | - | 3.43 | 20 | 12/20 | 0.503 | 0.105 | - | exploratory |
| v1.38.2 vs v1.38.0 | p99 latency (us) | exploratory | +0.35% [-6.73, +7.95] | 7.31 | - | 15.62 | 20 | 9/20 | 0.824 | 0.841 | - | exploratory |
| v1.38.5 vs v1.38.0 | instructions:u / req | exploratory | +0.11% [+0.08, +0.14] | 0.03 | - | 0.07 | 20 | 1/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.5 vs v1.38.0 | cycles:u / req | exploratory | -0.21% [-0.77, +0.36] | 0.56 | - | 1.21 | 20 | 11/20 | 0.824 | 0.430 | - | exploratory |
| v1.38.5 vs v1.38.0 | cycles:k / req | exploratory | +1.79% [+1.16, +2.42] | 0.62 | - | 1.32 | 20 | 2/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.5 vs v1.38.0 | cycles (u+k) / req | primary | +0.46% [-0.04, +0.96] | 0.50 | - | 1.06 | 20 | 8/20 | 0.503 | 0.097 | 0.343 | not resolved |
| v1.38.5 vs v1.38.0 | p50 latency (us) | exploratory | -1.68% [-3.72, +0.40] | 2.09 | - | 4.47 | 20 | 12/20 | 0.503 | 0.165 | - | exploratory |
| v1.38.5 vs v1.38.0 | p99 latency (us) | exploratory | -2.43% [-9.19, +4.82] | 7.17 | - | 15.33 | 20 | 10/20 | 1.000 | 0.701 | - | exploratory |
| v1.38.7 vs v1.38.0 | instructions:u / req | exploratory | +0.07% [+0.05, +0.10] | 0.03 | - | 0.05 | 20 | 1/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.7 vs v1.38.0 | cycles:u / req | exploratory | +0.81% [+0.23, +1.38] | 0.57 | - | 1.22 | 20 | 5/20 | 0.041 | 0.011 | - | exploratory: interval excludes 0 |
| v1.38.7 vs v1.38.0 | cycles:k / req | exploratory | +1.23% [+0.46, +2.01] | 0.77 | - | 1.64 | 20 | 5/20 | 0.041 | 0.005 | - | exploratory: interval excludes 0 |
| v1.38.7 vs v1.38.0 | cycles (u+k) / req | primary | +0.95% [+0.33, +1.57] | 0.61 | - | 1.31 | 20 | 4/20 | 0.012 | 0.006 | 0.031 | differs |
| v1.38.7 vs v1.38.0 | p50 latency (us) | exploratory | +0.46% [-1.33, +2.28] | 1.79 | - | 3.83 | 20 | 9/20 | 0.824 | 0.452 | - | exploratory |
| v1.38.7 vs v1.38.0 | p99 latency (us) | exploratory | +5.50% [-2.56, +14.23] | 7.95 | - | 16.98 | 20 | 7/20 | 0.263 | 0.105 | - | exploratory |
| v1.38.9 vs v1.38.0 | instructions:u / req | exploratory | +0.06% [+0.01, +0.10] | 0.05 | - | 0.10 | 20 | 4/20 | 0.012 | 0.005 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.38.0 | cycles:u / req | exploratory | +0.61% [+0.10, +1.13] | 0.51 | - | 1.09 | 20 | 7/20 | 0.263 | 0.030 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.38.0 | cycles:k / req | exploratory | +1.03% [+0.22, +1.85] | 0.81 | - | 1.72 | 20 | 4/20 | 0.012 | 0.019 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.38.0 | cycles (u+k) / req | primary | +0.75% [+0.18, +1.33] | 0.57 | - | 1.22 | 20 | 7/20 | 0.263 | 0.019 | 0.077 | not resolved |
| v1.38.9 vs v1.38.0 | p50 latency (us) | exploratory | +1.06% [-1.30, +3.47] | 2.36 | - | 5.05 | 20 | 9/20 | 0.824 | 0.294 | - | exploratory |
| v1.38.9 vs v1.38.0 | p99 latency (us) | exploratory | +2.94% [-4.62, +11.11] | 7.63 | - | 16.31 | 20 | 9/20 | 0.824 | 0.231 | - | exploratory |

## fh-hi (`/fh`, direct_headers, 18400 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.38.0 | 20/20 | 202.2k | 192.2k | 68.2k | 260.5k (0.8%) | 262 | 514 | 53.5% |
| v1.38.2 | 20/20 | 202.2k | 192.5k | 68.4k | 260.5k (0.9%) | 262 | 520 | 53.7% |
| v1.38.5 | 20/20 | 202.3k | 189.3k | 68.2k | 257.7k (1.0%) | 263 | 516 | 53.0% |
| v1.38.7 | 20/20 | 202.3k | 192.0k | 68.5k | 260.4k (1.1%) | 263 | 519 | 53.5% |
| v1.38.9 | 20/20 | 202.3k | 191.1k | 69.0k | 259.9k (1.1%) | 263 | 512 | 53.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.38.2 vs v1.38.0 | instructions:u / req | exploratory | +0.00% [-0.01, +0.01] | 0.01 | - | 0.01 | 20 | 9/20 | 0.824 | 0.927 | - | exploratory |
| v1.38.2 vs v1.38.0 | cycles:u / req | exploratory | +0.28% [-0.38, +0.94] | 0.66 | - | 1.40 | 20 | 10/20 | 1.000 | 0.430 | - | exploratory |
| v1.38.2 vs v1.38.0 | cycles:k / req | exploratory | +0.53% [-0.14, +1.20] | 0.67 | - | 1.43 | 20 | 9/20 | 0.824 | 0.165 | - | exploratory |
| v1.38.2 vs v1.38.0 | cycles (u+k) / req | primary | +0.34% [-0.27, +0.97] | 0.62 | - | 1.32 | 20 | 8/20 | 0.503 | 0.277 | 0.776 | not resolved |
| v1.38.2 vs v1.38.0 | p50 latency (us) | exploratory | -0.68% [-2.53, +1.21] | 1.88 | - | 4.02 | 20 | 9/20 | 0.824 | 0.674 | - | exploratory |
| v1.38.2 vs v1.38.0 | p99 latency (us) | exploratory | +1.41% [-3.35, +6.40] | 4.80 | - | 10.27 | 20 | 7/20 | 0.263 | 0.261 | - | exploratory |
| v1.38.5 vs v1.38.0 | instructions:u / req | exploratory | +0.03% [+0.02, +0.04] | 0.01 | - | 0.02 | 20 | 2/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.5 vs v1.38.0 | cycles:u / req | exploratory | -1.32% [-1.91, -0.72] | 0.61 | - | 1.30 | 20 | 16/20 | 0.012 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.5 vs v1.38.0 | cycles:k / req | exploratory | +0.25% [-0.43, +0.94] | 0.68 | - | 1.45 | 20 | 7/20 | 0.263 | 0.312 | - | exploratory |
| v1.38.5 vs v1.38.0 | cycles (u+k) / req | primary | -0.91% [-1.47, -0.33] | 0.57 | - | 1.23 | 20 | 15/20 | 0.041 | 0.006 | 0.029 | differs |
| v1.38.5 vs v1.38.0 | p50 latency (us) | exploratory | +0.34% [-1.19, +1.89] | 1.54 | - | 3.28 | 20 | 11/20 | 0.824 | 0.898 | - | exploratory |
| v1.38.5 vs v1.38.0 | p99 latency (us) | exploratory | +3.34% [-3.53, +10.71] | 6.88 | - | 14.71 | 20 | 6/20 | 0.115 | 0.216 | - | exploratory |
| v1.38.7 vs v1.38.0 | instructions:u / req | exploratory | +0.04% [+0.02, +0.05] | 0.01 | - | 0.03 | 20 | 4/20 | 0.012 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.7 vs v1.38.0 | cycles:u / req | exploratory | -0.04% [-0.83, +0.74] | 0.78 | - | 1.68 | 20 | 11/20 | 0.824 | 0.898 | - | exploratory |
| v1.38.7 vs v1.38.0 | cycles:k / req | exploratory | +0.18% [-0.57, +0.94] | 0.76 | - | 1.61 | 20 | 9/20 | 0.824 | 0.622 | - | exploratory |
| v1.38.7 vs v1.38.0 | cycles (u+k) / req | primary | +0.01% [-0.71, +0.75] | 0.73 | - | 1.56 | 20 | 11/20 | 0.824 | 0.956 | 1.000 | not resolved |
| v1.38.7 vs v1.38.0 | p50 latency (us) | exploratory | +0.75% [-1.16, +2.69] | 1.91 | - | 4.08 | 20 | 7/20 | 0.263 | 0.368 | - | exploratory |
| v1.38.7 vs v1.38.0 | p99 latency (us) | exploratory | +1.81% [-3.87, +7.82] | 5.74 | - | 12.25 | 20 | 8/20 | 0.503 | 0.498 | - | exploratory |
| v1.38.9 vs v1.38.0 | instructions:u / req | exploratory | +0.04% [+0.03, +0.05] | 0.01 | - | 0.02 | 20 | 1/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.38.0 | cycles:u / req | exploratory | -0.22% [-0.76, +0.32] | 0.54 | - | 1.16 | 20 | 11/20 | 0.824 | 0.349 | - | exploratory |
| v1.38.9 vs v1.38.0 | cycles:k / req | exploratory | +1.11% [+0.50, +1.72] | 0.60 | - | 1.29 | 20 | 4/20 | 0.012 | 0.002 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.38.0 | cycles (u+k) / req | primary | +0.13% [-0.37, +0.63] | 0.50 | - | 1.07 | 20 | 9/20 | 0.824 | 0.452 | 1.000 | not resolved |
| v1.38.9 vs v1.38.0 | p50 latency (us) | exploratory | -0.22% [-2.06, +1.66] | 1.86 | - | 3.98 | 20 | 10/20 | 1.000 | 0.869 | - | exploratory |
| v1.38.9 vs v1.38.0 | p99 latency (us) | exploratory | +0.72% [-4.41, +6.12] | 5.23 | - | 11.16 | 20 | 10/20 | 1.000 | 0.869 | - | exploratory |

## Validity

200 legs run, 200 valid; 0 legs superseded by a re-run of their round.

