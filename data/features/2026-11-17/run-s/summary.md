# features-run-s

- Harness: 0.x bb8aa8144e69 week5
- Window: 2026-11-17T11:44:58Z to 2026-11-17T14:57:20Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1559326,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 30 done (minimum 20, blocks of 10, cap 30, adaptive True), order rotate; stop: widest cycles_total half-width against its target 0.71% (fh percpu-on vs base) <= target 0.80%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 8 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| base | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| retry-on | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| idle-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| percpu-on | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| base-A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 30/30 | 163.9k | 344.9k | 181.1k | 525.9k (0.6%) | 398 | 625 | 31.3% |
| retry-on | 30/30 | 165.8k | 351.6k | 182.0k | 533.2k (0.7%) | 401 | 638 | 31.6% |
| idle-off | 30/30 | 156.8k | 333.7k | 180.8k | 514.6k (0.7%) | 391 | 613 | 30.6% |
| percpu-on | 30/30 | 147.1k | 340.7k | 182.9k | 523.6k (0.8%) | 398 | 627 | 31.1% |
| base-A2 | 30/30 | 163.9k | 345.8k | 181.6k | 527.3k (0.7%) | 398 | 628 | 31.3% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| retry-on vs base | instructions:u / req | exploratory | +1.21% [+1.19, +1.23] | 0.02 | - | 0.05 | 30 | 0/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| retry-on vs base | cycles:u / req | exploratory | +1.94% [+1.63, +2.26] | 0.31 | - | 0.83 | 30 | 1/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| retry-on vs base | cycles:k / req | exploratory | +0.20% [-0.23, +0.63] | 0.43 | - | 1.14 | 30 | 11/30 | 0.200 | 0.318 | - | exploratory |
| retry-on vs base | cycles (u+k) / req | primary | +1.34% [+1.01, +1.68] | 0.33 | - | 0.88 | 30 | 1/30 | 0.000 | 0.000 | 0.000 | differs |
| retry-on vs base | p50 latency (us) | exploratory | +1.31% [+0.00, +2.63] | 1.30 | - | 3.47 | 30 | 10/30 | 0.099 | 0.039 | - | exploratory: interval excludes 0 |
| retry-on vs base | p99 latency (us) | exploratory | +2.36% [+1.01, +3.72] | 1.32 | - | 3.54 | 30 | 9/30 | 0.043 | 0.002 | - | exploratory: interval excludes 0 |
| idle-off vs base | instructions:u / req | exploratory | -4.30% [-4.32, -4.29] | 0.02 | - | 0.05 | 30 | 30/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| idle-off vs base | cycles:u / req | exploratory | -3.30% [-3.63, -2.96] | 0.34 | - | 0.92 | 30 | 30/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| idle-off vs base | cycles:k / req | exploratory | -0.18% [-0.68, +0.32] | 0.50 | - | 1.35 | 30 | 15/30 | 1.000 | 0.626 | - | exploratory |
| idle-off vs base | cycles (u+k) / req | primary | -2.22% [-2.58, -1.86] | 0.37 | - | 0.99 | 30 | 30/30 | 0.000 | 0.000 | 0.000 | differs |
| idle-off vs base | p50 latency (us) | exploratory | -1.81% [-3.01, -0.60] | 1.23 | - | 3.29 | 30 | 21/30 | 0.043 | 0.007 | - | exploratory: interval excludes 0 |
| idle-off vs base | p99 latency (us) | exploratory | -1.75% [-2.77, -0.71] | 1.05 | - | 2.81 | 30 | 23/30 | 0.005 | 0.002 | - | exploratory: interval excludes 0 |
| percpu-on vs base | instructions:u / req | exploratory | -10.22% [-10.25, -10.18] | 0.04 | - | 0.10 | 30 | 30/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| percpu-on vs base | cycles:u / req | exploratory | -1.30% [-1.62, -0.98] | 0.32 | - | 0.87 | 30 | 28/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| percpu-on vs base | cycles:k / req | exploratory | +0.90% [+0.52, +1.29] | 0.38 | - | 1.03 | 30 | 6/30 | 0.001 | 0.000 | - | exploratory: interval excludes 0 |
| percpu-on vs base | cycles (u+k) / req | primary | -0.54% [-0.85, -0.22] | 0.32 | - | 0.85 | 30 | 23/30 | 0.005 | 0.002 | 0.008 | differs |
| percpu-on vs base | p50 latency (us) | exploratory | -0.92% [-2.35, +0.53] | 1.46 | - | 3.90 | 30 | 17/30 | 0.585 | 0.339 | - | exploratory |
| percpu-on vs base | p99 latency (us) | exploratory | -0.53% [-1.83, +0.79] | 1.32 | - | 3.54 | 30 | 15/30 | 1.000 | 0.612 | - | exploratory |
| base-A2 vs base | instructions:u / req | exploratory | -0.00% [-0.02, +0.02] | 0.02 | - | 0.04 | 30 | 17/30 | 0.585 | 0.655 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | +0.11% [-0.21, +0.43] | 0.32 | - | 0.85 | 30 | 14/30 | 0.856 | 0.503 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | +0.21% [-0.20, +0.63] | 0.41 | - | 1.11 | 30 | 15/30 | 1.000 | 0.289 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | +0.15% [-0.18, +0.48] | 0.33 | - | 0.88 | 30 | 14/30 | 0.856 | 0.440 | 1.000 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | +0.10% [-0.90, +1.10] | 1.00 | - | 2.67 | 30 | 14/30 | 0.856 | 0.984 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | +0.42% [-0.81, +1.68] | 1.24 | - | 3.32 | 30 | 14/30 | 0.856 | 0.503 | - | exploratory |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 30/30 | 164.8k | 198.2k | 82.9k | 281.1k (1.5%) | 216 | 369 | 25.5% |
| retry-on | 30/30 | 164.7k | 198.5k | 82.6k | 280.7k (1.7%) | 216 | 371 | 25.5% |
| idle-off | 30/30 | 159.0k | 188.5k | 82.9k | 271.0k (1.8%) | 212 | 361 | 24.6% |
| percpu-on | 30/30 | 133.1k | 199.8k | 83.2k | 283.4k (1.3%) | 217 | 372 | 25.7% |
| base-A2 | 30/30 | 164.8k | 197.7k | 82.8k | 281.0k (1.1%) | 217 | 371 | 25.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| retry-on vs base | instructions:u / req | exploratory | -0.01% [-0.01, -0.00] | 0.00 | - | 0.01 | 30 | 22/30 | 0.016 | 0.016 | - | exploratory: interval excludes 0 |
| retry-on vs base | cycles:u / req | exploratory | -0.02% [-0.72, +0.68] | 0.70 | - | 1.87 | 30 | 14/30 | 0.856 | 0.871 | - | exploratory |
| retry-on vs base | cycles:k / req | exploratory | -0.52% [-1.25, +0.23] | 0.74 | - | 1.99 | 30 | 19/30 | 0.200 | 0.140 | - | exploratory |
| retry-on vs base | cycles (u+k) / req | primary | -0.17% [-0.83, +0.50] | 0.67 | - | 1.79 | 30 | 17/30 | 0.585 | 0.529 | 1.000 | not resolved |
| retry-on vs base | p50 latency (us) | exploratory | -0.11% [-0.68, +0.46] | 0.57 | - | 1.53 | 30 | 17/30 | 0.585 | 0.570 | - | exploratory |
| retry-on vs base | p99 latency (us) | exploratory | +0.50% [-0.02, +1.02] | 0.52 | - | 1.40 | 30 | 12/30 | 0.362 | 0.095 | - | exploratory |
| idle-off vs base | instructions:u / req | exploratory | -3.49% [-3.49, -3.48] | 0.00 | - | 0.01 | 30 | 30/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| idle-off vs base | cycles:u / req | exploratory | -5.24% [-6.04, -4.44] | 0.85 | - | 2.27 | 30 | 30/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| idle-off vs base | cycles:k / req | exploratory | -0.17% [-0.82, +0.48] | 0.65 | - | 1.75 | 30 | 14/30 | 0.856 | 0.570 | - | exploratory |
| idle-off vs base | cycles (u+k) / req | primary | -3.75% [-4.47, -3.02] | 0.75 | - | 2.02 | 30 | 29/30 | 0.000 | 0.000 | 0.000 | differs |
| idle-off vs base | p50 latency (us) | exploratory | -2.09% [-2.74, -1.44] | 0.66 | - | 1.77 | 30 | 28/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| idle-off vs base | p99 latency (us) | exploratory | -2.24% [-2.78, -1.69] | 0.55 | - | 1.49 | 30 | 27/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| percpu-on vs base | instructions:u / req | exploratory | -19.20% [-19.26, -19.14] | 0.07 | - | 0.18 | 30 | 30/30 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| percpu-on vs base | cycles:u / req | exploratory | +0.74% [-0.08, +1.56] | 0.81 | - | 2.18 | 30 | 8/30 | 0.016 | 0.080 | - | exploratory |
| percpu-on vs base | cycles:k / req | exploratory | +0.47% [-0.19, +1.13] | 0.65 | - | 1.75 | 30 | 11/30 | 0.200 | 0.092 | - | exploratory |
| percpu-on vs base | cycles (u+k) / req | primary | +0.66% [-0.06, +1.37] | 0.71 | - | 1.90 | 30 | 8/30 | 0.016 | 0.077 | 0.279 | not resolved |
| percpu-on vs base | p50 latency (us) | exploratory | +0.52% [-0.25, +1.29] | 0.77 | - | 2.06 | 30 | 13/30 | 0.585 | 0.271 | - | exploratory |
| percpu-on vs base | p99 latency (us) | exploratory | +0.67% [+0.19, +1.16] | 0.48 | - | 1.29 | 30 | 8/30 | 0.016 | 0.003 | - | exploratory: interval excludes 0 |
| base-A2 vs base | instructions:u / req | exploratory | -0.00% [-0.01, +0.00] | 0.00 | - | 0.01 | 30 | 16/30 | 0.856 | 0.839 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | +0.00% [-0.79, +0.80] | 0.79 | - | 2.12 | 30 | 16/30 | 0.856 | 0.792 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | -0.17% [-0.79, +0.45] | 0.62 | - | 1.67 | 30 | 13/30 | 0.585 | 0.529 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | -0.05% [-0.74, +0.64] | 0.69 | - | 1.85 | 30 | 15/30 | 1.000 | 0.730 | 1.000 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | +0.17% [-0.53, +0.88] | 0.70 | - | 1.87 | 30 | 12/30 | 0.458 | 0.468 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | +0.53% [-0.14, +1.20] | 0.67 | - | 1.79 | 30 | 9/30 | 0.043 | 0.105 | - | exploratory |

## Validity

300 legs run, 300 valid; 0 legs superseded by a re-run of their round.

