# wk4-releases

- Harness: 0.1.0 57bbabf18abe
- Window: 2026-11-15T18:34:34Z to 2026-11-15T22:45:39Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 14 done (minimum 14, blocks of 14, cap 28, adaptive True), order rotate; stop: widest cycles_total half-width 1.16% (fh v1.40.2-A2 vs v1.40.2) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 24 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| v1.32.13 | 0c686a2237a51b1a07cdc4911dcf90c75f02f82d/1.32.13/Clean/RELEASE/BoringSSL | `dfd8f773a8dbfc0aeb97139e2fbf0f1a` |
| v1.34.14 | 3b1e52dadbbee013dc674d30906f6bc63c3dee38/1.34.14/Clean/RELEASE/BoringSSL | `f639502bb6d8abcd8e1e8b1206f87e21` |
| v1.36.13 | eb0a95ba450a3e29a9a8e75f672e2c294493eea2/1.36.13/Clean/RELEASE/BoringSSL | `da94b2d687fd73fe9ae3e746297c8909` |
| v1.37.11 | 0ce6eee982e6df4a873b28184b396eeacfad938f/1.37.11/Clean/RELEASE/BoringSSL | `54525e87b6e9422e1474bc1554e433c3` |
| v1.38.9 | 17e27840396c1fa3196f184fcb5db1ab13850504/1.38.9/Clean/RELEASE/BoringSSL | `2358b9b2f859b5f0f050181e0b295c35` |
| v1.40.2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| v1.40.2-A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 14/14 | 186.6k | 338.4k | 180.3k | 518.9k (1.2%) | 397 | 615 | 30.9% |
| v1.34.14 | 14/14 | 173.6k | 333.7k | 180.3k | 514.1k (0.7%) | 392 | 615 | 30.6% |
| v1.36.13 | 14/14 | 168.6k | 335.3k | 180.0k | 515.0k (0.8%) | 392 | 619 | 30.7% |
| v1.37.11 | 14/14 | 168.6k | 338.7k | 180.9k | 519.5k (0.9%) | 393 | 621 | 30.9% |
| v1.38.9 | 14/14 | 175.1k | 344.5k | 180.3k | 524.7k (0.8%) | 394 | 628 | 31.2% |
| v1.40.2 | 14/14 | 163.9k | 344.6k | 181.6k | 526.5k (0.8%) | 400 | 623 | 31.2% |
| v1.40.2-A2 | 14/14 | 163.9k | 345.1k | 181.5k | 526.4k (0.5%) | 399 | 628 | 31.3% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.32.13 vs v1.40.2 | instructions:u / req | exploratory | +13.86% [+13.80, +13.91] | 0.05 | - | 0.08 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles:u / req | exploratory | -1.62% [-2.43, -0.81] | 0.82 | - | 1.42 | 14 | 12/14 | 0.013 | 0.002 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles:k / req | exploratory | +0.08% [-1.22, +1.40] | 1.31 | - | 2.26 | 14 | 9/14 | 0.424 | 0.855 | - | exploratory |
| v1.32.13 vs v1.40.2 | cycles (u+k) / req | primary | -1.04% [-1.99, -0.07] | 0.97 | - | 1.68 | 14 | 11/14 | 0.057 | 0.049 | 0.261 | not resolved |
| v1.32.13 vs v1.40.2 | p50 latency (us) | exploratory | -0.90% [-2.55, +0.78] | 1.68 | - | 2.91 | 14 | 8/14 | 0.791 | 0.241 | - | exploratory |
| v1.32.13 vs v1.40.2 | p99 latency (us) | exploratory | -1.32% [-2.82, +0.20] | 1.53 | - | 2.66 | 14 | 11/14 | 0.057 | 0.058 | - | exploratory |
| v1.34.14 vs v1.40.2 | instructions:u / req | exploratory | +5.94% [+5.91, +5.98] | 0.03 | - | 0.06 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | cycles:u / req | exploratory | -3.28% [-3.78, -2.78] | 0.52 | - | 0.90 | 14 | 14/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | cycles:k / req | exploratory | -0.49% [-1.41, +0.44] | 0.93 | - | 1.61 | 14 | 8/14 | 0.791 | 0.426 | - | exploratory |
| v1.34.14 vs v1.40.2 | cycles (u+k) / req | primary | -2.32% [-2.94, -1.70] | 0.63 | - | 1.10 | 14 | 14/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.34.14 vs v1.40.2 | p50 latency (us) | exploratory | -1.81% [-3.15, -0.46] | 1.37 | - | 2.37 | 14 | 11/14 | 0.057 | 0.017 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | p99 latency (us) | exploratory | -1.96% [-3.13, -0.77] | 1.21 | - | 2.09 | 14 | 12/14 | 0.013 | 0.004 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | instructions:u / req | exploratory | +2.89% [+2.85, +2.93] | 0.04 | - | 0.07 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | cycles:u / req | exploratory | -2.85% [-3.35, -2.36] | 0.51 | - | 0.88 | 14 | 14/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | cycles:k / req | exploratory | -0.25% [-1.41, +0.92] | 1.17 | - | 2.03 | 14 | 10/14 | 0.180 | 0.426 | - | exploratory |
| v1.36.13 vs v1.40.2 | cycles (u+k) / req | primary | -1.96% [-2.66, -1.25] | 0.71 | - | 1.24 | 14 | 13/14 | 0.002 | 0.001 | 0.001 | differs |
| v1.36.13 vs v1.40.2 | p50 latency (us) | exploratory | -1.85% [-3.24, -0.45] | 1.42 | - | 2.46 | 14 | 11/14 | 0.057 | 0.025 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | p99 latency (us) | exploratory | -1.50% [-3.08, +0.11] | 1.62 | - | 2.80 | 14 | 8/14 | 0.791 | 0.153 | - | exploratory |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +2.86% [+2.82, +2.89] | 0.03 | - | 0.05 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:u / req | exploratory | -1.80% [-2.43, -1.16] | 0.65 | - | 1.12 | 14 | 13/14 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:k / req | exploratory | -0.05% [-1.33, +1.25] | 1.29 | - | 2.23 | 14 | 6/14 | 0.791 | 0.952 | - | exploratory |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | -1.20% [-2.02, -0.36] | 0.84 | - | 1.45 | 14 | 10/14 | 0.180 | 0.013 | 0.080 | not resolved |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | -2.01% [-3.77, -0.21] | 1.82 | - | 3.15 | 14 | 12/14 | 0.013 | 0.005 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | -1.49% [-3.15, +0.20] | 1.70 | - | 2.94 | 14 | 9/14 | 0.424 | 0.057 | - | exploratory |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +6.88% [+6.84, +6.93] | 0.04 | - | 0.07 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:u / req | exploratory | -0.16% [-0.71, +0.39] | 0.55 | - | 0.95 | 14 | 7/14 | 1.000 | 0.626 | - | exploratory |
| v1.38.9 vs v1.40.2 | cycles:k / req | exploratory | -0.14% [-0.81, +0.54] | 0.68 | - | 1.17 | 14 | 7/14 | 1.000 | 0.808 | - | exploratory |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | -0.15% [-0.72, +0.42] | 0.57 | - | 0.99 | 14 | 8/14 | 0.791 | 0.626 | 1.000 | not resolved |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | -0.84% [-1.84, +0.17] | 1.01 | - | 1.75 | 14 | 8/14 | 0.791 | 0.104 | - | exploratory |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | +0.13% [-1.53, +1.82] | 1.68 | - | 2.90 | 14 | 7/14 | 1.000 | 0.808 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | instructions:u / req | exploratory | -0.00% [-0.04, +0.03] | 0.04 | - | 0.06 | 14 | 6/14 | 0.791 | 0.952 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:u / req | exploratory | +0.17% [-0.25, +0.58] | 0.41 | - | 0.72 | 14 | 6/14 | 0.791 | 0.426 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:k / req | exploratory | +0.26% [-0.56, +1.08] | 0.82 | - | 1.42 | 14 | 6/14 | 0.791 | 0.426 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles (u+k) / req | primary | +0.20% [-0.32, +0.72] | 0.52 | - | 0.90 | 14 | 6/14 | 0.791 | 0.391 | 1.000 | not resolved |
| v1.40.2-A2 vs v1.40.2 | p50 latency (us) | exploratory | +0.07% [-1.95, +2.13] | 2.04 | - | 3.53 | 14 | 7/14 | 1.000 | 0.903 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | p99 latency (us) | exploratory | -0.04% [-1.64, +1.58] | 1.61 | - | 2.79 | 14 | 5/14 | 0.424 | 0.715 | - | exploratory |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 14/14 | 231.1k | 220.5k | 82.4k | 302.8k (1.1%) | 229 | 393 | 27.4% |
| v1.34.14 | 14/14 | 192.8k | 209.1k | 82.4k | 291.8k (1.2%) | 222 | 380 | 26.4% |
| v1.36.13 | 14/14 | 189.7k | 207.9k | 82.9k | 291.1k (1.2%) | 221 | 379 | 26.4% |
| v1.37.11 | 14/14 | 189.5k | 206.6k | 82.9k | 289.7k (1.1%) | 221 | 377 | 26.2% |
| v1.38.9 | 14/14 | 202.6k | 211.4k | 83.0k | 294.6k (1.3%) | 222 | 381 | 26.6% |
| v1.40.2 | 14/14 | 164.8k | 198.6k | 83.0k | 282.0k (1.1%) | 216 | 370 | 25.6% |
| v1.40.2-A2 | 14/14 | 164.8k | 197.2k | 82.5k | 280.1k (1.2%) | 215 | 370 | 25.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.32.13 vs v1.40.2 | instructions:u / req | exploratory | +40.25% [+40.24, +40.27] | 0.01 | - | 0.01 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles:u / req | exploratory | +11.30% [+10.12, +12.49] | 1.07 | - | 1.85 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles:k / req | exploratory | -0.75% [-1.90, +0.41] | 1.16 | - | 2.01 | 14 | 10/14 | 0.180 | 0.217 | - | exploratory |
| v1.32.13 vs v1.40.2 | cycles (u+k) / req | primary | +7.75% [+6.60, +8.90] | 1.07 | - | 1.85 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.32.13 vs v1.40.2 | p50 latency (us) | exploratory | +5.91% [+4.65, +7.19] | 1.20 | - | 2.08 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | p99 latency (us) | exploratory | +6.46% [+5.43, +7.51] | 0.97 | - | 1.69 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | instructions:u / req | exploratory | +17.05% [+17.04, +17.06] | 0.01 | - | 0.02 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | cycles:u / req | exploratory | +5.27% [+4.05, +6.50] | 1.16 | - | 2.02 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | cycles:k / req | exploratory | -0.68% [-1.93, +0.59] | 1.27 | - | 2.19 | 14 | 10/14 | 0.180 | 0.391 | - | exploratory |
| v1.34.14 vs v1.40.2 | cycles (u+k) / req | primary | +3.52% [+2.38, +4.67] | 1.11 | - | 1.92 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.34.14 vs v1.40.2 | p50 latency (us) | exploratory | +2.80% [+1.71, +3.89] | 1.06 | - | 1.84 | 14 | 1/14 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | p99 latency (us) | exploratory | +3.57% [+2.44, +4.70] | 1.09 | - | 1.89 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | instructions:u / req | exploratory | +15.12% [+15.11, +15.13] | 0.01 | - | 0.01 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | cycles:u / req | exploratory | +4.82% [+3.85, +5.80] | 0.93 | - | 1.61 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | cycles:k / req | exploratory | +0.46% [-0.88, +1.82] | 1.34 | - | 2.32 | 14 | 5/14 | 0.424 | 0.542 | - | exploratory |
| v1.36.13 vs v1.40.2 | cycles (u+k) / req | primary | +3.54% [+2.50, +4.58] | 1.00 | - | 1.74 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.36.13 vs v1.40.2 | p50 latency (us) | exploratory | +2.68% [+1.70, +3.67] | 0.96 | - | 1.66 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | p99 latency (us) | exploratory | +2.68% [+1.59, +3.78] | 1.06 | - | 1.84 | 14 | 1/14 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +15.03% [+15.02, +15.04] | 0.01 | - | 0.01 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:u / req | exploratory | +3.86% [+3.15, +4.58] | 0.69 | - | 1.20 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:k / req | exploratory | +0.01% [-0.79, +0.82] | 0.81 | - | 1.40 | 14 | 9/14 | 0.424 | 0.670 | - | exploratory |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | +2.73% [+2.04, +3.42] | 0.67 | - | 1.16 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | +2.08% [+1.18, +2.98] | 0.88 | - | 1.53 | 14 | 1/14 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | +2.63% [+1.69, +3.57] | 0.92 | - | 1.59 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +22.97% [+22.97, +22.98] | 0.01 | - | 0.01 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:u / req | exploratory | +6.19% [+5.44, +6.93] | 0.70 | - | 1.21 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:k / req | exploratory | -0.06% [-0.87, +0.76] | 0.82 | - | 1.42 | 14 | 8/14 | 0.791 | 0.670 | - | exploratory |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | +4.35% [+3.63, +5.07] | 0.69 | - | 1.20 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | +3.06% [+2.12, +4.00] | 0.91 | - | 1.58 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | +3.43% [+2.55, +4.31] | 0.85 | - | 1.47 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.2-A2 vs v1.40.2 | instructions:u / req | exploratory | +0.01% [-0.00, +0.01] | 0.01 | - | 0.01 | 14 | 6/14 | 0.791 | 0.173 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:u / req | exploratory | -0.49% [-1.54, +0.57] | 1.06 | - | 1.84 | 14 | 9/14 | 0.424 | 0.358 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:k / req | exploratory | -0.33% [-1.80, +1.16] | 1.48 | - | 2.57 | 14 | 8/14 | 0.791 | 0.808 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles (u+k) / req | primary | -0.44% [-1.59, +0.71] | 1.16 | - | 2.00 | 14 | 8/14 | 0.791 | 0.502 | 1.000 | not resolved |
| v1.40.2-A2 vs v1.40.2 | p50 latency (us) | exploratory | -0.31% [-1.21, +0.60] | 0.90 | - | 1.57 | 14 | 8/14 | 0.791 | 0.502 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | p99 latency (us) | exploratory | -0.20% [-1.05, +0.67] | 0.86 | - | 1.49 | 14 | 9/14 | 0.424 | 0.626 | - | exploratory |

## s-hi (`/s`, proxied, 12000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 14/14 | 185.9k | 296.5k | 152.6k | 448.3k (1.0%) | 410 | 888 | 60.1% |
| v1.34.14 | 14/14 | 173.0k | 292.9k | 152.8k | 445.0k (1.0%) | 418 | 918 | 59.6% |
| v1.36.13 | 14/14 | 167.9k | 294.6k | 153.7k | 448.3k (1.2%) | 414 | 929 | 59.9% |
| v1.37.11 | 14/14 | 167.8k | 298.3k | 153.3k | 451.5k (0.5%) | 413 | 951 | 60.3% |
| v1.38.9 | 14/14 | 174.4k | 304.2k | 153.5k | 457.6k (0.5%) | 430 | 999 | 61.2% |
| v1.40.2 | 14/14 | 163.0k | 303.1k | 152.3k | 454.8k (1.1%) | 432 | 1026 | 60.7% |
| v1.40.2-A2 | 14/14 | 163.0k | 304.7k | 152.4k | 457.1k (1.1%) | 436 | 1082 | 61.0% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.32.13 vs v1.40.2 | instructions:u / req | exploratory | +14.06% [+13.99, +14.13] | 0.06 | - | 0.11 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles:u / req | exploratory | -2.26% [-2.95, -1.56] | 0.71 | - | 1.23 | 14 | 14/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles:k / req | exploratory | +0.65% [-0.64, +1.96] | 1.29 | - | 2.24 | 14 | 6/14 | 0.791 | 0.463 | - | exploratory |
| v1.32.13 vs v1.40.2 | cycles (u+k) / req | primary | -1.29% [-2.13, -0.44] | 0.85 | - | 1.48 | 14 | 11/14 | 0.057 | 0.013 | 0.065 | not resolved |
| v1.32.13 vs v1.40.2 | p50 latency (us) | exploratory | -6.34% [-9.62, -2.93] | 3.57 | - | 6.19 | 14 | 14/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | p99 latency (us) | exploratory | -12.83% [-23.88, -0.17] | 13.55 | - | 23.48 | 14 | 11/14 | 0.057 | 0.078 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | instructions:u / req | exploratory | +6.11% [+6.03, +6.18] | 0.07 | - | 0.12 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | cycles:u / req | exploratory | -3.39% [-4.05, -2.71] | 0.69 | - | 1.20 | 14 | 14/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | cycles:k / req | exploratory | +0.79% [-0.39, +1.98] | 1.17 | - | 2.03 | 14 | 6/14 | 0.791 | 0.296 | - | exploratory |
| v1.34.14 vs v1.40.2 | cycles (u+k) / req | primary | -2.00% [-2.77, -1.22] | 0.79 | - | 1.37 | 14 | 12/14 | 0.013 | 0.001 | 0.001 | differs |
| v1.34.14 vs v1.40.2 | p50 latency (us) | exploratory | -5.30% [-8.85, -1.62] | 3.81 | - | 6.60 | 14 | 12/14 | 0.013 | 0.009 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | p99 latency (us) | exploratory | -8.85% [-21.10, +5.30] | 14.43 | - | 24.99 | 14 | 10/14 | 0.180 | 0.217 | - | exploratory |
| v1.36.13 vs v1.40.2 | instructions:u / req | exploratory | +2.99% [+2.92, +3.06] | 0.07 | - | 0.11 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | cycles:u / req | exploratory | -2.75% [-3.73, -1.77] | 1.01 | - | 1.75 | 14 | 13/14 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | cycles:k / req | exploratory | +1.26% [+0.08, +2.46] | 1.17 | - | 2.03 | 14 | 4/14 | 0.180 | 0.042 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | cycles (u+k) / req | primary | -1.42% [-2.38, -0.44] | 0.98 | - | 1.70 | 14 | 12/14 | 0.013 | 0.009 | 0.080 | not resolved |
| v1.36.13 vs v1.40.2 | p50 latency (us) | exploratory | -5.56% [-9.22, -1.74] | 3.96 | - | 6.85 | 14 | 13/14 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | p99 latency (us) | exploratory | -8.44% [-19.77, +4.50] | 13.22 | - | 22.89 | 14 | 9/14 | 0.424 | 0.296 | - | exploratory |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +2.98% [+2.92, +3.03] | 0.05 | - | 0.09 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:u / req | exploratory | -1.60% [-2.23, -0.97] | 0.64 | - | 1.10 | 14 | 13/14 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:k / req | exploratory | +0.89% [-0.21, +2.01] | 1.10 | - | 1.91 | 14 | 5/14 | 0.424 | 0.135 | - | exploratory |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | -0.77% [-1.48, -0.06] | 0.72 | - | 1.25 | 14 | 9/14 | 0.424 | 0.078 | 0.261 | not resolved |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | -5.14% [-8.11, -2.07] | 3.18 | - | 5.51 | 14 | 14/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | -7.27% [-14.69, +0.79] | 8.34 | - | 14.44 | 14 | 8/14 | 0.791 | 0.135 | - | exploratory |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +7.02% [+6.96, +7.08] | 0.05 | - | 0.09 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:u / req | exploratory | +0.45% [-0.09, +0.99] | 0.54 | - | 0.93 | 14 | 4/14 | 0.180 | 0.104 | - | exploratory |
| v1.38.9 vs v1.40.2 | cycles:k / req | exploratory | +1.16% [+0.18, +2.16] | 0.98 | - | 1.70 | 14 | 2/14 | 0.013 | 0.017 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | +0.69% [+0.07, +1.31] | 0.62 | - | 1.07 | 14 | 4/14 | 0.180 | 0.042 | 0.261 | not resolved |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | -2.37% [-6.01, +1.40] | 3.79 | - | 6.57 | 14 | 9/14 | 0.424 | 0.241 | - | exploratory |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | -6.40% [-15.88, +4.16] | 10.69 | - | 18.51 | 14 | 8/14 | 0.791 | 0.358 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | instructions:u / req | exploratory | -0.01% [-0.11, +0.08] | 0.09 | - | 0.16 | 14 | 7/14 | 1.000 | 1.000 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:u / req | exploratory | +0.45% [-0.44, +1.34] | 0.89 | - | 1.53 | 14 | 5/14 | 0.424 | 0.241 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:k / req | exploratory | +0.86% [-0.82, +2.56] | 1.68 | - | 2.91 | 14 | 5/14 | 0.424 | 0.296 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles (u+k) / req | primary | +0.58% [-0.48, +1.66] | 1.06 | - | 1.84 | 14 | 5/14 | 0.424 | 0.217 | 1.000 | not resolved |
| v1.40.2-A2 vs v1.40.2 | p50 latency (us) | exploratory | +1.17% [-5.03, +7.77] | 6.33 | - | 10.95 | 14 | 7/14 | 1.000 | 0.761 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | p99 latency (us) | exploratory | +3.93% [-10.79, +21.08] | 15.27 | - | 26.45 | 14 | 6/14 | 0.791 | 0.583 | - | exploratory |

## fh-hi (`/fh`, direct_headers, 18400 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 14/14 | 230.9k | 200.7k | 68.1k | 268.8k (0.8%) | 277 | 573 | 55.1% |
| v1.34.14 | 14/14 | 192.6k | 189.2k | 68.4k | 257.5k (0.6%) | 264 | 525 | 52.9% |
| v1.36.13 | 14/14 | 189.5k | 187.3k | 68.9k | 256.4k (1.6%) | 261 | 505 | 52.7% |
| v1.37.11 | 14/14 | 189.3k | 186.2k | 68.8k | 255.0k (0.6%) | 257 | 514 | 52.3% |
| v1.38.9 | 14/14 | 202.4k | 190.6k | 68.8k | 259.5k (1.2%) | 261 | 503 | 53.4% |
| v1.40.2 | 14/14 | 164.5k | 179.7k | 69.5k | 249.1k (0.9%) | 246 | 493 | 51.0% |
| v1.40.2-A2 | 14/14 | 164.5k | 179.9k | 69.4k | 248.9k (1.0%) | 248 | 474 | 51.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.32.13 vs v1.40.2 | instructions:u / req | exploratory | +40.33% [+40.31, +40.34] | 0.01 | - | 0.02 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles:u / req | exploratory | +12.22% [+11.28, +13.17] | 0.84 | - | 1.46 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles:k / req | exploratory | -1.18% [-2.10, -0.25] | 0.94 | - | 1.62 | 14 | 10/14 | 0.180 | 0.017 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles (u+k) / req | primary | +8.49% [+7.61, +9.38] | 0.82 | - | 1.41 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.32.13 vs v1.40.2 | p50 latency (us) | exploratory | +13.44% [+11.30, +15.62] | 1.90 | - | 3.30 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | p99 latency (us) | exploratory | +17.50% [+12.21, +23.04] | 4.61 | - | 7.98 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | instructions:u / req | exploratory | +17.08% [+17.06, +17.10] | 0.01 | - | 0.02 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | cycles:u / req | exploratory | +5.68% [+5.00, +6.37] | 0.65 | - | 1.12 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | cycles:k / req | exploratory | -1.10% [-1.69, -0.52] | 0.59 | - | 1.02 | 14 | 11/14 | 0.057 | 0.002 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | cycles (u+k) / req | primary | +3.79% [+3.18, +4.40] | 0.59 | - | 1.02 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.34.14 vs v1.40.2 | p50 latency (us) | exploratory | +7.22% [+4.66, +9.85] | 2.42 | - | 4.19 | 14 | 1/14 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.34.14 vs v1.40.2 | p99 latency (us) | exploratory | +7.91% [+1.10, +15.18] | 6.52 | - | 11.30 | 14 | 4/14 | 0.180 | 0.042 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | instructions:u / req | exploratory | +15.16% [+15.15, +15.17] | 0.01 | - | 0.02 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | cycles:u / req | exploratory | +5.02% [+3.79, +6.26] | 1.18 | - | 2.04 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | cycles:k / req | exploratory | -0.38% [-1.54, +0.80] | 1.17 | - | 2.03 | 14 | 10/14 | 0.180 | 0.217 | - | exploratory |
| v1.36.13 vs v1.40.2 | cycles (u+k) / req | primary | +3.52% [+2.36, +4.69] | 1.13 | - | 1.95 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.36.13 vs v1.40.2 | p50 latency (us) | exploratory | +6.32% [+4.05, +8.64] | 2.16 | - | 3.74 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.36.13 vs v1.40.2 | p99 latency (us) | exploratory | +5.22% [-0.76, +11.57] | 5.85 | - | 10.14 | 14 | 2/14 | 0.013 | 0.068 | - | exploratory |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +15.07% [+15.05, +15.08] | 0.01 | - | 0.02 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:u / req | exploratory | +3.84% [+3.02, +4.66] | 0.79 | - | 1.37 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:k / req | exploratory | -0.48% [-1.27, +0.31] | 0.79 | - | 1.37 | 14 | 10/14 | 0.180 | 0.194 | - | exploratory |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | +2.63% [+1.92, +3.35] | 0.70 | - | 1.21 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | +5.34% [+3.04, +7.69] | 2.20 | - | 3.82 | 14 | 1/14 | 0.002 | 0.001 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | +4.58% [-1.69, +11.25] | 6.18 | - | 10.70 | 14 | 5/14 | 0.424 | 0.173 | - | exploratory |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +23.03% [+23.01, +23.05] | 0.01 | - | 0.02 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:u / req | exploratory | +6.65% [+5.48, +7.84] | 1.10 | - | 1.91 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:k / req | exploratory | -0.23% [-1.18, +0.72] | 0.95 | - | 1.64 | 14 | 9/14 | 0.424 | 0.463 | - | exploratory |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | +4.74% [+3.66, +5.82] | 1.03 | - | 1.79 | 14 | 0/14 | 0.000 | 0.000 | 0.000 | differs |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | +7.23% [+4.81, +9.71] | 2.28 | - | 3.96 | 14 | 0/14 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | +5.21% [-0.71, +11.48] | 5.79 | - | 10.03 | 14 | 2/14 | 0.013 | 0.035 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | instructions:u / req | exploratory | -0.01% [-0.02, +0.01] | 0.01 | - | 0.03 | 14 | 8/14 | 0.791 | 0.296 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:u / req | exploratory | +0.15% [-0.72, +1.03] | 0.87 | - | 1.51 | 14 | 7/14 | 1.000 | 0.715 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:k / req | exploratory | +0.06% [-0.79, +0.92] | 0.85 | - | 1.48 | 14 | 7/14 | 1.000 | 0.952 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles (u+k) / req | primary | +0.13% [-0.65, +0.91] | 0.78 | - | 1.35 | 14 | 9/14 | 0.424 | 0.903 | 1.000 | not resolved |
| v1.40.2-A2 vs v1.40.2 | p50 latency (us) | exploratory | +1.80% [-0.62, +4.28] | 2.41 | - | 4.17 | 14 | 6/14 | 0.791 | 0.326 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | p99 latency (us) | exploratory | -1.47% [-7.42, +4.86] | 6.23 | - | 10.78 | 14 | 8/14 | 0.791 | 0.583 | - | exploratory |

## Validity

392 legs run, 392 valid; 0 legs superseded by a re-run of their round.

