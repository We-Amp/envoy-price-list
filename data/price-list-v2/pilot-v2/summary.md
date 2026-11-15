# pilot-releases

- Harness: 0.1.0 8358578961a2
- Window: 2026-11-14T00:57:53Z to 2026-11-14T02:07:12Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 36, adaptive True), order rotate; stop: widest cycles_total half-width 1.16% (fh v1.40.2 vs v1.32.13) <= target 3.00%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 9 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| v1.32.13 | 0c686a2237a51b1a07cdc4911dcf90c75f02f82d/1.32.13/Clean/RELEASE/BoringSSL | `dfd8f773a8dbfc0aeb97139e2fbf0f1a` |
| v1.36.13 | eb0a95ba450a3e29a9a8e75f672e2c294493eea2/1.36.13/Clean/RELEASE/BoringSSL | `da94b2d687fd73fe9ae3e746297c8909` |
| v1.40.2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 12/12 | 186.6k | 337.3k | 178.1k | 515.0k (0.8%) | 388 | 611 | 30.7% |
| v1.36.13 | 12/12 | 168.6k | 334.7k | 178.6k | 513.3k (0.9%) | 388 | 611 | 30.5% |
| v1.40.2 | 12/12 | 163.9k | 343.1k | 178.8k | 521.4k (0.7%) | 392 | 615 | 31.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.36.13 vs v1.32.13 | instructions:u / req | exploratory | -9.64% [-9.66, -9.61] | 0.03 | 0.05 | 0.05 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.32.13 | cycles:u / req | exploratory | -0.87% [-1.33, -0.41] | 0.47 | 0.81 | 0.73 | 12 | 10/12 | 0.039 | 0.005 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.32.13 | cycles:k / req | exploratory | +0.15% [-0.38, +0.68] | 0.53 | 1.13 | 0.83 | 12 | 5/12 | 0.774 | 0.569 | - | exploratory |
| v1.36.13 vs v1.32.13 | cycles (u+k) / req | primary | -0.52% [-0.94, -0.09] | 0.43 | 0.90 | 0.68 | 12 | 7/12 | 0.774 | 0.064 | 0.045 | differs |
| v1.36.13 vs v1.32.13 | p50 latency (us) | exploratory | +0.44% [-0.61, +1.50] | 1.05 | 2.00 | 1.66 | 12 | 5/12 | 0.774 | 0.380 | - | exploratory |
| v1.36.13 vs v1.32.13 | p99 latency (us) | exploratory | -0.06% [-1.36, +1.25] | 1.31 | 1.18 | 2.06 | 12 | 6/12 | 1.000 | 0.970 | - | exploratory |
| v1.40.2 vs v1.32.13 | instructions:u / req | exploratory | -12.16% [-12.19, -12.12] | 0.04 | 0.05 | 0.06 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.32.13 | cycles:u / req | exploratory | +1.74% [+1.14, +2.35] | 0.59 | 0.81 | 0.93 | 12 | 1/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.32.13 | cycles:k / req | exploratory | +0.08% [-0.67, +0.84] | 0.75 | 1.13 | 1.18 | 12 | 5/12 | 0.774 | 1.000 | - | exploratory |
| v1.40.2 vs v1.32.13 | cycles (u+k) / req | primary | +1.17% [+0.59, +1.75] | 0.57 | 0.90 | 0.90 | 12 | 1/12 | 0.006 | 0.002 | 0.004 | differs |
| v1.40.2 vs v1.32.13 | p50 latency (us) | exploratory | +1.43% [-0.47, +3.37] | 1.89 | 2.00 | 2.98 | 12 | 5/12 | 0.774 | 0.233 | - | exploratory |
| v1.40.2 vs v1.32.13 | p99 latency (us) | exploratory | +0.73% [-1.06, +2.56] | 1.80 | 1.18 | 2.83 | 12 | 5/12 | 0.774 | 0.733 | - | exploratory |
| v1.40.2 vs v1.36.13 | instructions:u / req | exploratory | -2.79% [-2.83, -2.75] | 0.04 | 0.05 | 0.06 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.36.13 | cycles:u / req | exploratory | +2.63% [+2.03, +3.24] | 0.59 | 0.81 | 0.93 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.36.13 | cycles:k / req | exploratory | -0.07% [-0.73, +0.60] | 0.66 | 1.13 | 1.04 | 12 | 6/12 | 1.000 | 1.000 | - | exploratory |
| v1.40.2 vs v1.36.13 | cycles (u+k) / req | primary | +1.69% [+1.10, +2.29] | 0.58 | 0.90 | 0.92 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| v1.40.2 vs v1.36.13 | p50 latency (us) | exploratory | +0.99% [-0.80, +2.81] | 1.79 | 2.00 | 2.81 | 12 | 5/12 | 0.774 | 0.339 | - | exploratory |
| v1.40.2 vs v1.36.13 | p99 latency (us) | exploratory | +0.80% [-0.80, +2.42] | 1.60 | 1.18 | 2.51 | 12 | 4/12 | 0.388 | 0.301 | - | exploratory |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 12/12 | 231.1k | 219.4k | 81.3k | 300.5k (1.1%) | 228 | 390 | 27.2% |
| v1.36.13 | 12/12 | 189.7k | 206.7k | 80.7k | 287.4k (1.0%) | 219 | 378 | 26.1% |
| v1.40.2 | 12/12 | 164.8k | 199.7k | 82.5k | 282.2k (1.1%) | 217 | 370 | 25.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.36.13 vs v1.32.13 | instructions:u / req | exploratory | -17.92% [-17.93, -17.91] | 0.01 | 0.01 | 0.02 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.32.13 | cycles:u / req | exploratory | -6.20% [-7.24, -5.14] | 1.12 | 1.45 | 1.76 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.32.13 | cycles:k / req | exploratory | -0.32% [-1.23, +0.60] | 0.92 | 1.30 | 1.44 | 12 | 8/12 | 0.388 | 0.233 | - | exploratory |
| v1.36.13 vs v1.32.13 | cycles (u+k) / req | primary | -4.61% [-5.55, -3.67] | 0.99 | 1.37 | 1.55 | 12 | 12/12 | 0.000 | 0.000 | 0.000 | differs |
| v1.36.13 vs v1.32.13 | p50 latency (us) | exploratory | -3.70% [-4.67, -2.73] | 1.01 | 1.04 | 1.59 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.32.13 | p99 latency (us) | exploratory | -2.95% [-3.42, -2.47] | 0.49 | 0.89 | 0.77 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.32.13 | instructions:u / req | exploratory | -28.70% [-28.71, -28.70] | 0.01 | 0.01 | 0.01 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.32.13 | cycles:u / req | exploratory | -9.21% [-10.29, -8.13] | 1.19 | 1.45 | 1.87 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.32.13 | cycles:k / req | exploratory | +1.60% [+0.32, +2.89] | 1.27 | 1.30 | 1.99 | 12 | 2/12 | 0.039 | 0.021 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.32.13 | cycles (u+k) / req | primary | -6.31% [-7.39, -5.21] | 1.16 | 1.37 | 1.83 | 12 | 12/12 | 0.000 | 0.000 | 0.000 | differs |
| v1.40.2 vs v1.32.13 | p50 latency (us) | exploratory | -4.78% [-5.93, -3.62] | 1.21 | 1.04 | 1.91 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.32.13 | p99 latency (us) | exploratory | -5.26% [-6.03, -4.49] | 0.81 | 0.89 | 1.28 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.36.13 | instructions:u / req | exploratory | -13.13% [-13.14, -13.12] | 0.01 | 0.01 | 0.01 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.36.13 | cycles:u / req | exploratory | -3.22% [-4.34, -2.08] | 1.16 | 1.45 | 1.83 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.36.13 | cycles:k / req | exploratory | +1.92% [+0.96, +2.89] | 0.95 | 1.30 | 1.50 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.36.13 | cycles (u+k) / req | primary | -1.77% [-2.76, -0.78] | 1.01 | 1.37 | 1.59 | 12 | 10/12 | 0.039 | 0.003 | 0.007 | differs |
| v1.40.2 vs v1.36.13 | p50 latency (us) | exploratory | -1.12% [-2.29, +0.08] | 1.20 | 1.04 | 1.89 | 12 | 8/12 | 0.388 | 0.064 | - | exploratory |
| v1.40.2 vs v1.36.13 | p99 latency (us) | exploratory | -2.39% [-3.03, -1.74] | 0.66 | 0.89 | 1.04 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## m (`/m`, proxied, 5440 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 12/12 | 190.1k | 338.4k | 188.0k | 526.2k (0.7%) | 397 | 636 | 32.5% |
| v1.36.13 | 12/12 | 172.1k | 335.0k | 188.8k | 524.2k (0.9%) | 399 | 631 | 32.4% |
| v1.40.2 | 12/12 | 167.0k | 344.4k | 189.6k | 534.1k (0.8%) | 404 | 653 | 32.9% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.36.13 vs v1.32.13 | instructions:u / req | exploratory | -9.47% [-9.50, -9.43] | 0.04 | 0.03 | 0.06 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.32.13 | cycles:u / req | exploratory | -0.92% [-1.54, -0.29] | 0.63 | 0.40 | 0.99 | 12 | 10/12 | 0.039 | 0.012 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.32.13 | cycles:k / req | exploratory | +0.19% [-0.46, +0.85] | 0.66 | 0.60 | 1.03 | 12 | 4/12 | 0.388 | 0.424 | - | exploratory |
| v1.36.13 vs v1.32.13 | cycles (u+k) / req | primary | -0.52% [-1.12, +0.08] | 0.60 | 0.43 | 0.95 | 12 | 8/12 | 0.388 | 0.129 | 0.083 | not resolved |
| v1.36.13 vs v1.32.13 | p50 latency (us) | exploratory | +0.44% [-1.20, +2.11] | 1.65 | 1.78 | 2.59 | 12 | 6/12 | 1.000 | 0.677 | - | exploratory |
| v1.36.13 vs v1.32.13 | p99 latency (us) | exploratory | -1.50% [-3.97, +1.03] | 2.53 | 4.59 | 3.99 | 12 | 6/12 | 1.000 | 0.339 | - | exploratory |
| v1.40.2 vs v1.32.13 | instructions:u / req | exploratory | -12.12% [-12.16, -12.08] | 0.05 | 0.03 | 0.07 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.32.13 | cycles:u / req | exploratory | +1.85% [+1.40, +2.30] | 0.44 | 0.40 | 0.69 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.32.13 | cycles:k / req | exploratory | +0.33% [-0.25, +0.92] | 0.58 | 0.60 | 0.92 | 12 | 4/12 | 0.388 | 0.301 | - | exploratory |
| v1.40.2 vs v1.32.13 | cycles (u+k) / req | primary | +1.31% [+0.91, +1.71] | 0.39 | 0.43 | 0.62 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| v1.40.2 vs v1.32.13 | p50 latency (us) | exploratory | +1.64% [-0.52, +3.85] | 2.15 | 1.78 | 3.39 | 12 | 5/12 | 0.774 | 0.176 | - | exploratory |
| v1.40.2 vs v1.32.13 | p99 latency (us) | exploratory | +3.82% [-2.22, +10.23] | 5.99 | 4.59 | 9.43 | 12 | 5/12 | 0.774 | 0.266 | - | exploratory |
| v1.40.2 vs v1.36.13 | instructions:u / req | exploratory | -2.93% [-2.94, -2.91] | 0.02 | 0.03 | 0.03 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.36.13 | cycles:u / req | exploratory | +2.80% [+2.19, +3.40] | 0.59 | 0.40 | 0.92 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2 vs v1.36.13 | cycles:k / req | exploratory | +0.14% [-0.71, +0.99] | 0.85 | 0.60 | 1.33 | 12 | 5/12 | 0.774 | 0.910 | - | exploratory |
| v1.40.2 vs v1.36.13 | cycles (u+k) / req | primary | +1.84% [+1.18, +2.50] | 0.65 | 0.43 | 1.02 | 12 | 1/12 | 0.006 | 0.001 | 0.000 | differs |
| v1.40.2 vs v1.36.13 | p50 latency (us) | exploratory | +1.20% [-0.12, +2.53] | 1.31 | 1.78 | 2.06 | 12 | 3/12 | 0.146 | 0.077 | - | exploratory |
| v1.40.2 vs v1.36.13 | p99 latency (us) | exploratory | +5.40% [+0.29, +10.78] | 4.97 | 4.59 | 7.83 | 12 | 4/12 | 0.388 | 0.064 | - | exploratory: interval excludes 0 |

## Validity

108 legs run, 108 valid; 0 legs superseded by a re-run of their round.

