# release-record-a

- Harness: 0.1.0 e3caa9b1319f
- Window: 2026-11-16T08:17:47Z to 2026-11-16T19:13:31Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 32 done (minimum 16, blocks of 16, cap 32, adaptive True), order rotate; stop: widest cycles_total half-width 0.66% (s-hi v1.38.0 vs v1.37.11) <= target 0.80%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 28 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| v1.37.0 | 6d9bb7d9a85d616b220d1f8fe67b61f82bbdb8d3/1.37.0/Clean/RELEASE/BoringSSL | `d47c2851db6f7a124f29244b08987294` |
| v1.37.11 | 0ce6eee982e6df4a873b28184b396eeacfad938f/1.37.11/Clean/RELEASE/BoringSSL | `54525e87b6e9422e1474bc1554e433c3` |
| v1.38.0 | f1dd21b16c244bda00edfb5ffce577e12d0d2ec2/1.38.0/Clean/RELEASE/BoringSSL | `909c9394315c4ae97e176bbe20de124f` |
| v1.38.9 | 17e27840396c1fa3196f184fcb5db1ab13850504/1.38.9/Clean/RELEASE/BoringSSL | `2358b9b2f859b5f0f050181e0b295c35` |
| v1.39.6 | aacd0340210b536e99ec44ebe59ab9d16b259552/1.39.6/Clean/RELEASE/BoringSSL | `28eea1b267d880517e4c4ee042e504b8` |
| v1.40.0 | 9e5580933739775e8bce696a57a2e1bc99368f23/1.40.0/Clean/RELEASE/BoringSSL | `e970a516b7c3b678bb63070f2d154bf4` |
| v1.40.2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| v1.40.2-A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.37.0 | 32/32 | 168.3k | 337.9k | 181.1k | 518.8k (0.9%) | 390 | 617 | 30.9% |
| v1.37.11 | 32/32 | 168.6k | 337.9k | 180.8k | 518.0k (0.9%) | 391 | 618 | 30.9% |
| v1.38.0 | 32/32 | 175.0k | 343.4k | 179.6k | 522.5k (0.7%) | 398 | 625 | 31.1% |
| v1.38.9 | 32/32 | 175.2k | 345.8k | 182.6k | 528.7k (0.6%) | 397 | 627 | 31.4% |
| v1.39.6 | 32/32 | 167.7k | 342.2k | 181.9k | 524.0k (0.7%) | 396 | 626 | 31.1% |
| v1.40.0 | 32/32 | 163.9k | 344.3k | 180.6k | 524.8k (0.6%) | 400 | 630 | 31.2% |
| v1.40.2 | 32/32 | 163.9k | 344.8k | 180.8k | 526.2k (0.7%) | 400 | 630 | 31.2% |
| v1.40.2-A2 | 32/32 | 163.8k | 345.0k | 180.6k | 525.9k (0.7%) | 399 | 631 | 31.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.37.0 vs v1.40.2 | instructions:u / req | exploratory | +2.74% [+2.72, +2.76] | 0.02 | - | 0.06 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | cycles:u / req | exploratory | -2.23% [-2.59, -1.87] | 0.37 | - | 1.02 | 32 | 32/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | cycles:k / req | exploratory | +0.03% [-0.60, +0.66] | 0.63 | - | 1.74 | 32 | 18/32 | 0.597 | 1.000 | - | exploratory |
| v1.37.0 vs v1.40.2 | cycles (u+k) / req | primary | -1.45% [-1.87, -1.03] | 0.42 | - | 1.18 | 32 | 27/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.0 vs v1.40.2 | p50 latency (us) | exploratory | -2.36% [-3.32, -1.39] | 0.99 | - | 2.74 | 32 | 27/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | p99 latency (us) | exploratory | -2.81% [-4.07, -1.53] | 1.31 | - | 3.63 | 32 | 26/32 | 0.001 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +2.87% [+2.85, +2.89] | 0.02 | - | 0.06 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:u / req | exploratory | -2.08% [-2.46, -1.70] | 0.38 | - | 1.07 | 32 | 31/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:k / req | exploratory | -0.05% [-0.53, +0.43] | 0.48 | - | 1.33 | 32 | 15/32 | 0.860 | 0.978 | - | exploratory |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | -1.38% [-1.75, -1.01] | 0.37 | - | 1.03 | 32 | 28/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | -1.71% [-2.67, -0.73] | 0.98 | - | 2.73 | 32 | 24/32 | 0.007 | 0.002 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | -1.98% [-3.24, -0.70] | 1.30 | - | 3.60 | 32 | 20/32 | 0.215 | 0.005 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | instructions:u / req | exploratory | +6.81% [+6.80, +6.83] | 0.02 | - | 0.04 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles:u / req | exploratory | -0.49% [-0.83, -0.15] | 0.34 | - | 0.95 | 32 | 22/32 | 0.050 | 0.006 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles:k / req | exploratory | -0.58% [-1.13, -0.02] | 0.56 | - | 1.55 | 32 | 23/32 | 0.020 | 0.043 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles (u+k) / req | primary | -0.52% [-0.90, -0.14] | 0.38 | - | 1.06 | 32 | 24/32 | 0.007 | 0.008 | 0.123 | not resolved |
| v1.38.0 vs v1.40.2 | p50 latency (us) | exploratory | -0.33% [-1.43, +0.78] | 1.11 | - | 3.07 | 32 | 17/32 | 0.860 | 0.573 | - | exploratory |
| v1.38.0 vs v1.40.2 | p99 latency (us) | exploratory | -1.03% [-2.39, +0.34] | 1.38 | - | 3.82 | 32 | 16/32 | 1.000 | 0.350 | - | exploratory |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +6.91% [+6.89, +6.93] | 0.02 | - | 0.05 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:u / req | exploratory | +0.23% [-0.09, +0.55] | 0.32 | - | 0.89 | 32 | 10/32 | 0.050 | 0.084 | - | exploratory |
| v1.38.9 vs v1.40.2 | cycles:k / req | exploratory | +0.71% [+0.19, +1.22] | 0.51 | - | 1.41 | 32 | 11/32 | 0.110 | 0.012 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | +0.39% [+0.04, +0.74] | 0.35 | - | 0.96 | 32 | 10/32 | 0.050 | 0.045 | 0.309 | not resolved |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | -0.56% [-1.51, +0.40] | 0.96 | - | 2.67 | 32 | 19/32 | 0.377 | 0.119 | - | exploratory |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | -0.65% [-2.09, +0.82] | 1.46 | - | 4.06 | 32 | 16/32 | 1.000 | 0.465 | - | exploratory |
| v1.39.6 vs v1.40.2 | instructions:u / req | exploratory | +2.35% [+2.33, +2.36] | 0.02 | - | 0.05 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles:u / req | exploratory | -0.98% [-1.32, -0.64] | 0.34 | - | 0.94 | 32 | 28/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles:k / req | exploratory | +0.47% [-0.02, +0.96] | 0.49 | - | 1.36 | 32 | 11/32 | 0.110 | 0.062 | - | exploratory |
| v1.39.6 vs v1.40.2 | cycles (u+k) / req | primary | -0.48% [-0.83, -0.13] | 0.35 | - | 0.98 | 32 | 20/32 | 0.215 | 0.012 | 0.123 | not resolved |
| v1.39.6 vs v1.40.2 | p50 latency (us) | exploratory | -1.02% [-1.97, -0.06] | 0.96 | - | 2.67 | 32 | 22/32 | 0.050 | 0.021 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | p99 latency (us) | exploratory | -0.82% [-2.20, +0.58] | 1.40 | - | 3.89 | 32 | 19/32 | 0.377 | 0.432 | - | exploratory |
| v1.40.0 vs v1.40.2 | instructions:u / req | exploratory | -0.00% [-0.02, +0.01] | 0.01 | - | 0.04 | 32 | 21/32 | 0.110 | 0.524 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles:u / req | exploratory | -0.27% [-0.57, +0.03] | 0.30 | - | 0.83 | 32 | 19/32 | 0.377 | 0.111 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles:k / req | exploratory | -0.38% [-0.86, +0.10] | 0.48 | - | 1.33 | 32 | 18/32 | 0.597 | 0.172 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles (u+k) / req | primary | -0.31% [-0.64, +0.02] | 0.33 | - | 0.91 | 32 | 20/32 | 0.215 | 0.071 | 0.637 | not resolved |
| v1.40.0 vs v1.40.2 | p50 latency (us) | exploratory | -0.13% [-0.96, +0.70] | 0.83 | - | 2.31 | 32 | 18/32 | 0.597 | 0.432 | - | exploratory |
| v1.40.0 vs v1.40.2 | p99 latency (us) | exploratory | +0.17% [-1.37, +1.72] | 1.54 | - | 4.28 | 32 | 16/32 | 1.000 | 0.875 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | instructions:u / req | exploratory | -0.01% [-0.03, +0.01] | 0.02 | - | 0.06 | 32 | 17/32 | 0.860 | 0.561 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:u / req | exploratory | -0.03% [-0.37, +0.30] | 0.34 | - | 0.93 | 32 | 17/32 | 0.860 | 0.761 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:k / req | exploratory | +0.02% [-0.53, +0.58] | 0.56 | - | 1.54 | 32 | 17/32 | 0.860 | 0.993 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles (u+k) / req | primary | -0.01% [-0.40, +0.37] | 0.38 | - | 1.06 | 32 | 17/32 | 0.860 | 0.861 | 1.000 | not resolved |
| v1.40.2-A2 vs v1.40.2 | p50 latency (us) | exploratory | -0.64% [-1.72, +0.45] | 1.09 | - | 3.03 | 32 | 18/32 | 0.597 | 0.322 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | p99 latency (us) | exploratory | -0.05% [-1.41, +1.33] | 1.37 | - | 3.80 | 32 | 14/32 | 0.597 | 0.761 | - | exploratory |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.37.0 | 32/32 | 189.4k | 207.1k | 82.1k | 289.0k (0.9%) | 220 | 377 | 26.2% |
| v1.37.11 | 32/32 | 189.5k | 206.8k | 82.9k | 289.7k (1.2%) | 222 | 378 | 26.3% |
| v1.38.0 | 32/32 | 202.5k | 211.3k | 82.0k | 293.3k (1.2%) | 223 | 384 | 26.6% |
| v1.38.9 | 32/32 | 202.6k | 210.1k | 82.5k | 292.7k (1.1%) | 222 | 380 | 26.5% |
| v1.39.6 | 32/32 | 203.5k | 215.4k | 82.5k | 298.1k (1.0%) | 226 | 386 | 27.0% |
| v1.40.0 | 32/32 | 164.8k | 197.8k | 82.3k | 280.0k (1.3%) | 217 | 371 | 25.5% |
| v1.40.2 | 32/32 | 164.8k | 197.5k | 82.3k | 280.1k (1.4%) | 215 | 370 | 25.5% |
| v1.40.2-A2 | 32/32 | 164.8k | 197.6k | 82.5k | 279.8k (1.4%) | 216 | 369 | 25.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.37.0 vs v1.40.2 | instructions:u / req | exploratory | +14.98% [+14.97, +14.98] | 0.00 | - | 0.01 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | cycles:u / req | exploratory | +4.43% [+3.76, +5.11] | 0.65 | - | 1.80 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | cycles:k / req | exploratory | -0.42% [-1.06, +0.22] | 0.65 | - | 1.79 | 32 | 21/32 | 0.110 | 0.197 | - | exploratory |
| v1.37.0 vs v1.40.2 | cycles (u+k) / req | primary | +3.00% [+2.37, +3.64] | 0.62 | - | 1.72 | 32 | 1/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.0 vs v1.40.2 | p50 latency (us) | exploratory | +1.73% [+1.08, +2.37] | 0.63 | - | 1.76 | 32 | 5/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | p99 latency (us) | exploratory | +1.89% [+1.40, +2.37] | 0.48 | - | 1.32 | 32 | 2/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +15.03% [+15.02, +15.03] | 0.01 | - | 0.01 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:u / req | exploratory | +4.78% [+4.10, +5.45] | 0.64 | - | 1.79 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:k / req | exploratory | +0.58% [-0.08, +1.24] | 0.66 | - | 1.83 | 32 | 14/32 | 0.597 | 0.139 | - | exploratory |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | +3.54% [+2.89, +4.19] | 0.63 | - | 1.74 | 32 | 0/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | +2.64% [+1.97, +3.31] | 0.65 | - | 1.81 | 32 | 3/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | +2.64% [+2.11, +3.18] | 0.52 | - | 1.44 | 32 | 1/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | instructions:u / req | exploratory | +22.92% [+22.92, +22.93] | 0.00 | - | 0.01 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles:u / req | exploratory | +7.25% [+6.62, +7.88] | 0.59 | - | 1.63 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles:k / req | exploratory | -0.48% [-1.11, +0.16] | 0.64 | - | 1.77 | 32 | 20/32 | 0.215 | 0.172 | - | exploratory |
| v1.38.0 vs v1.40.2 | cycles (u+k) / req | primary | +4.97% [+4.39, +5.56] | 0.56 | - | 1.54 | 32 | 0/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.38.0 vs v1.40.2 | p50 latency (us) | exploratory | +3.32% [+2.74, +3.91] | 0.57 | - | 1.58 | 32 | 1/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | p99 latency (us) | exploratory | +3.90% [+3.40, +4.39] | 0.48 | - | 1.33 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +22.98% [+22.97, +22.98] | 0.00 | - | 0.01 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:u / req | exploratory | +6.27% [+5.61, +6.93] | 0.62 | - | 1.72 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:k / req | exploratory | +0.21% [-0.41, +0.83] | 0.62 | - | 1.72 | 32 | 13/32 | 0.377 | 0.573 | - | exploratory |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | +4.48% [+3.86, +5.11] | 0.59 | - | 1.65 | 32 | 0/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | +2.93% [+2.28, +3.60] | 0.64 | - | 1.78 | 32 | 1/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | +2.95% [+2.47, +3.44] | 0.47 | - | 1.31 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | instructions:u / req | exploratory | +23.54% [+23.53, +23.55] | 0.00 | - | 0.01 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles:u / req | exploratory | +9.02% [+8.34, +9.70] | 0.62 | - | 1.73 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles:k / req | exploratory | +0.11% [-0.55, +0.76] | 0.65 | - | 1.81 | 32 | 16/32 | 1.000 | 0.747 | - | exploratory |
| v1.39.6 vs v1.40.2 | cycles (u+k) / req | primary | +6.40% [+5.76, +7.04] | 0.60 | - | 1.67 | 32 | 0/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.39.6 vs v1.40.2 | p50 latency (us) | exploratory | +4.69% [+4.08, +5.31] | 0.58 | - | 1.62 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | p99 latency (us) | exploratory | +4.53% [+3.95, +5.11] | 0.56 | - | 1.54 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.0 vs v1.40.2 | instructions:u / req | exploratory | +0.00% [-0.00, +0.00] | 0.00 | - | 0.01 | 32 | 15/32 | 0.860 | 0.761 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles:u / req | exploratory | +0.13% [-0.48, +0.74] | 0.61 | - | 1.68 | 32 | 14/32 | 0.597 | 0.625 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles:k / req | exploratory | -0.00% [-0.59, +0.59] | 0.59 | - | 1.63 | 32 | 14/32 | 0.597 | 0.818 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles (u+k) / req | primary | +0.09% [-0.46, +0.65] | 0.55 | - | 1.54 | 32 | 17/32 | 0.860 | 0.719 | 1.000 | not resolved |
| v1.40.0 vs v1.40.2 | p50 latency (us) | exploratory | +0.17% [-0.31, +0.65] | 0.48 | - | 1.33 | 32 | 15/32 | 1.000 | 0.468 | - | exploratory |
| v1.40.0 vs v1.40.2 | p99 latency (us) | exploratory | +0.33% [-0.09, +0.75] | 0.42 | - | 1.16 | 32 | 11/32 | 0.110 | 0.092 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | instructions:u / req | exploratory | +0.00% [-0.00, +0.01] | 0.00 | - | 0.01 | 32 | 11/32 | 0.110 | 0.246 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:u / req | exploratory | -0.25% [-0.96, +0.46] | 0.71 | - | 1.98 | 32 | 18/32 | 0.597 | 0.443 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:k / req | exploratory | +0.18% [-0.50, +0.87] | 0.68 | - | 1.90 | 32 | 13/32 | 0.377 | 0.548 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles (u+k) / req | primary | -0.13% [-0.80, +0.55] | 0.68 | - | 1.88 | 32 | 18/32 | 0.597 | 0.651 | 1.000 | not resolved |
| v1.40.2-A2 vs v1.40.2 | p50 latency (us) | exploratory | -0.11% [-0.75, +0.54] | 0.65 | - | 1.79 | 32 | 16/32 | 1.000 | 0.625 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | p99 latency (us) | exploratory | -0.09% [-0.55, +0.37] | 0.46 | - | 1.27 | 32 | 19/32 | 0.377 | 0.500 | - | exploratory |

## s-hi (`/s`, proxied, 12000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.37.0 | 32/32 | 167.6k | 296.4k | 153.3k | 450.3k (1.2%) | 415 | 958 | 60.2% |
| v1.37.11 | 32/32 | 167.8k | 299.4k | 153.3k | 452.3k (1.2%) | 423 | 892 | 60.7% |
| v1.38.0 | 32/32 | 174.2k | 301.8k | 151.6k | 453.2k (1.0%) | 420 | 967 | 60.7% |
| v1.38.9 | 32/32 | 174.3k | 303.4k | 152.7k | 456.4k (1.0%) | 429 | 965 | 61.2% |
| v1.39.6 | 32/32 | 166.9k | 301.8k | 153.6k | 455.4k (0.9%) | 423 | 957 | 61.0% |
| v1.40.0 | 32/32 | 162.9k | 304.1k | 152.9k | 457.4k (0.9%) | 435 | 1080 | 61.3% |
| v1.40.2 | 32/32 | 163.0k | 302.9k | 152.4k | 456.0k (0.9%) | 426 | 938 | 61.1% |
| v1.40.2-A2 | 32/32 | 162.9k | 303.6k | 152.6k | 455.8k (1.0%) | 435 | 1024 | 61.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.37.0 vs v1.40.2 | instructions:u / req | exploratory | +2.81% [+2.78, +2.84] | 0.03 | - | 0.09 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | cycles:u / req | exploratory | -2.41% [-2.92, -1.90] | 0.52 | - | 1.45 | 32 | 31/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | cycles:k / req | exploratory | +0.14% [-0.65, +0.93] | 0.79 | - | 2.18 | 32 | 13/32 | 0.377 | 0.692 | - | exploratory |
| v1.37.0 vs v1.40.2 | cycles (u+k) / req | primary | -1.56% [-2.13, -0.98] | 0.58 | - | 1.61 | 32 | 26/32 | 0.001 | 0.000 | 0.000 | differs |
| v1.37.0 vs v1.40.2 | p50 latency (us) | exploratory | -3.06% [-4.91, -1.18] | 1.92 | - | 5.34 | 32 | 22/32 | 0.050 | 0.003 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | p99 latency (us) | exploratory | +1.11% [-6.15, +8.94] | 7.45 | - | 20.67 | 32 | 15/32 | 0.860 | 0.905 | - | exploratory |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +2.92% [+2.88, +2.96] | 0.04 | - | 0.12 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:u / req | exploratory | -1.35% [-1.89, -0.80] | 0.55 | - | 1.53 | 32 | 27/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:k / req | exploratory | +0.29% [-0.55, +1.14] | 0.84 | - | 2.34 | 32 | 12/32 | 0.215 | 0.197 | - | exploratory |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | -0.80% [-1.40, -0.19] | 0.61 | - | 1.69 | 32 | 25/32 | 0.002 | 0.006 | 0.140 | not resolved |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | -0.87% [-3.24, +1.56] | 2.42 | - | 6.70 | 32 | 19/32 | 0.377 | 0.231 | - | exploratory |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | -2.10% [-11.23, +7.98] | 9.79 | - | 27.16 | 32 | 17/32 | 0.860 | 0.599 | - | exploratory |
| v1.38.0 vs v1.40.2 | instructions:u / req | exploratory | +6.88% [+6.85, +6.92] | 0.03 | - | 0.09 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles:u / req | exploratory | -0.61% [-1.00, -0.21] | 0.40 | - | 1.10 | 32 | 22/32 | 0.050 | 0.004 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles:k / req | exploratory | -0.69% [-1.34, -0.03] | 0.66 | - | 1.83 | 32 | 20/32 | 0.215 | 0.025 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles (u+k) / req | primary | -0.63% [-1.08, -0.18] | 0.45 | - | 1.25 | 32 | 23/32 | 0.020 | 0.005 | 0.112 | not resolved |
| v1.38.0 vs v1.40.2 | p50 latency (us) | exploratory | -1.16% [-3.04, +0.76] | 1.92 | - | 5.33 | 32 | 20/32 | 0.215 | 0.074 | - | exploratory |
| v1.38.0 vs v1.40.2 | p99 latency (us) | exploratory | +3.55% [-3.67, +11.31] | 7.23 | - | 20.05 | 32 | 13/32 | 0.377 | 0.278 | - | exploratory |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +6.96% [+6.93, +6.98] | 0.02 | - | 0.07 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:u / req | exploratory | +0.14% [-0.24, +0.52] | 0.38 | - | 1.05 | 32 | 15/32 | 0.860 | 0.488 | - | exploratory |
| v1.38.9 vs v1.40.2 | cycles:k / req | exploratory | +0.26% [-0.31, +0.83] | 0.57 | - | 1.59 | 32 | 14/32 | 0.597 | 0.278 | - | exploratory |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | +0.18% [-0.22, +0.58] | 0.40 | - | 1.12 | 32 | 15/32 | 0.860 | 0.369 | 1.000 | not resolved |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | +0.57% [-1.11, +2.27] | 1.68 | - | 4.65 | 32 | 16/32 | 1.000 | 0.512 | - | exploratory |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | +5.42% [-2.21, +13.64] | 7.51 | - | 20.82 | 32 | 12/32 | 0.215 | 0.190 | - | exploratory |
| v1.39.6 vs v1.40.2 | instructions:u / req | exploratory | +2.38% [+2.35, +2.41] | 0.03 | - | 0.08 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles:u / req | exploratory | -0.55% [-1.00, -0.10] | 0.45 | - | 1.25 | 32 | 22/32 | 0.050 | 0.039 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles:k / req | exploratory | +0.78% [+0.12, +1.44] | 0.66 | - | 1.82 | 32 | 9/32 | 0.020 | 0.016 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles (u+k) / req | primary | -0.11% [-0.57, +0.36] | 0.47 | - | 1.30 | 32 | 16/32 | 1.000 | 0.875 | 1.000 | not resolved |
| v1.39.6 vs v1.40.2 | p50 latency (us) | exploratory | -0.48% [-2.33, +1.41] | 1.88 | - | 5.22 | 32 | 16/32 | 1.000 | 0.651 | - | exploratory |
| v1.39.6 vs v1.40.2 | p99 latency (us) | exploratory | +1.10% [-7.60, +10.62] | 9.00 | - | 24.96 | 32 | 16/32 | 1.000 | 0.747 | - | exploratory |
| v1.40.0 vs v1.40.2 | instructions:u / req | exploratory | -0.03% [-0.06, +0.00] | 0.03 | - | 0.09 | 32 | 21/32 | 0.110 | 0.060 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles:u / req | exploratory | +0.42% [+0.05, +0.79] | 0.37 | - | 1.01 | 32 | 12/32 | 0.215 | 0.038 | - | exploratory: interval excludes 0 |
| v1.40.0 vs v1.40.2 | cycles:k / req | exploratory | +0.06% [-0.55, +0.69] | 0.62 | - | 1.72 | 32 | 17/32 | 0.860 | 0.625 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles (u+k) / req | primary | +0.30% [-0.12, +0.72] | 0.42 | - | 1.16 | 32 | 12/32 | 0.215 | 0.154 | 1.000 | not resolved |
| v1.40.0 vs v1.40.2 | p50 latency (us) | exploratory | +2.02% [+0.47, +3.60] | 1.54 | - | 4.26 | 32 | 10/32 | 0.050 | 0.011 | - | exploratory: interval excludes 0 |
| v1.40.0 vs v1.40.2 | p99 latency (us) | exploratory | +10.79% [+1.81, +20.55] | 8.45 | - | 23.44 | 32 | 12/32 | 0.215 | 0.036 | - | exploratory: interval excludes 0 |
| v1.40.2-A2 vs v1.40.2 | instructions:u / req | exploratory | -0.04% [-0.07, -0.01] | 0.03 | - | 0.08 | 32 | 21/32 | 0.110 | 0.010 | - | exploratory: interval excludes 0 |
| v1.40.2-A2 vs v1.40.2 | cycles:u / req | exploratory | +0.08% [-0.36, +0.53] | 0.44 | - | 1.22 | 32 | 14/32 | 0.597 | 0.586 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:k / req | exploratory | -0.14% [-0.73, +0.46] | 0.59 | - | 1.65 | 32 | 17/32 | 0.860 | 0.586 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles (u+k) / req | primary | +0.01% [-0.45, +0.47] | 0.46 | - | 1.27 | 32 | 16/32 | 1.000 | 0.963 | 1.000 | not resolved |
| v1.40.2-A2 vs v1.40.2 | p50 latency (us) | exploratory | +2.52% [+0.56, +4.51] | 1.93 | - | 5.35 | 32 | 11/32 | 0.110 | 0.022 | - | exploratory: interval excludes 0 |
| v1.40.2-A2 vs v1.40.2 | p99 latency (us) | exploratory | +6.18% [-0.98, +13.86] | 6.99 | - | 19.37 | 32 | 14/32 | 0.597 | 0.190 | - | exploratory |

## fh-hi (`/fh`, direct_headers, 18400 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.37.0 | 32/32 | 189.1k | 186.3k | 68.5k | 255.0k (1.1%) | 255 | 494 | 52.6% |
| v1.37.11 | 32/32 | 189.2k | 186.0k | 68.7k | 254.6k (0.9%) | 257 | 494 | 52.5% |
| v1.38.0 | 32/32 | 202.2k | 192.8k | 68.5k | 261.3k (1.2%) | 263 | 515 | 53.8% |
| v1.38.9 | 32/32 | 202.3k | 190.2k | 68.2k | 258.3k (0.9%) | 264 | 519 | 53.1% |
| v1.39.6 | 32/32 | 203.2k | 196.0k | 68.5k | 264.6k (1.3%) | 267 | 542 | 54.3% |
| v1.40.0 | 32/32 | 164.4k | 179.6k | 69.4k | 249.2k (1.1%) | 249 | 486 | 51.3% |
| v1.40.2 | 32/32 | 164.4k | 179.3k | 69.4k | 248.4k (1.2%) | 241 | 481 | 51.3% |
| v1.40.2-A2 | 32/32 | 164.4k | 179.5k | 69.4k | 248.9k (1.1%) | 247 | 478 | 51.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.37.0 vs v1.40.2 | instructions:u / req | exploratory | +15.02% [+15.01, +15.03] | 0.01 | - | 0.03 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | cycles:u / req | exploratory | +4.28% [+3.60, +4.96] | 0.65 | - | 1.80 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | cycles:k / req | exploratory | -1.17% [-1.96, -0.37] | 0.81 | - | 2.24 | 32 | 21/32 | 0.110 | 0.010 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | cycles (u+k) / req | primary | +2.76% [+2.10, +3.42] | 0.64 | - | 1.78 | 32 | 2/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.0 vs v1.40.2 | p50 latency (us) | exploratory | +4.24% [+2.32, +6.19] | 1.85 | - | 5.14 | 32 | 9/32 | 0.020 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.0 vs v1.40.2 | p99 latency (us) | exploratory | +4.32% [+0.50, +8.29] | 3.73 | - | 10.35 | 32 | 10/32 | 0.050 | 0.031 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +15.07% [+15.06, +15.08] | 0.01 | - | 0.03 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:u / req | exploratory | +3.96% [+3.34, +4.58] | 0.60 | - | 1.66 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles:k / req | exploratory | -1.01% [-1.64, -0.38] | 0.64 | - | 1.77 | 32 | 21/32 | 0.110 | 0.003 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | +2.57% [+1.98, +3.16] | 0.57 | - | 1.59 | 32 | 1/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | +4.95% [+2.99, +6.95] | 1.89 | - | 5.23 | 32 | 7/32 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | +3.16% [-0.47, +6.92] | 3.58 | - | 9.94 | 32 | 12/32 | 0.215 | 0.038 | - | exploratory |
| v1.38.0 vs v1.40.2 | instructions:u / req | exploratory | +22.98% [+22.96, +22.99] | 0.01 | - | 0.03 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles:u / req | exploratory | +7.72% [+7.20, +8.25] | 0.49 | - | 1.35 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles:k / req | exploratory | -1.53% [-2.31, -0.74] | 0.80 | - | 2.22 | 32 | 25/32 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | cycles (u+k) / req | primary | +5.14% [+4.58, +5.70] | 0.54 | - | 1.48 | 32 | 0/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.38.0 vs v1.40.2 | p50 latency (us) | exploratory | +8.06% [+6.10, +10.05] | 1.83 | - | 5.06 | 32 | 2/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.0 vs v1.40.2 | p99 latency (us) | exploratory | +9.94% [+3.88, +16.34] | 5.66 | - | 15.71 | 32 | 7/32 | 0.002 | 0.001 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +23.03% [+23.02, +23.04] | 0.01 | - | 0.03 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:u / req | exploratory | +5.93% [+5.34, +6.51] | 0.55 | - | 1.53 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles:k / req | exploratory | -1.65% [-2.21, -1.10] | 0.56 | - | 1.56 | 32 | 28/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | +3.81% [+3.28, +4.34] | 0.51 | - | 1.40 | 32 | 0/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | +7.39% [+5.58, +9.23] | 1.70 | - | 4.72 | 32 | 2/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | +6.88% [+3.46, +10.41] | 3.25 | - | 9.02 | 32 | 7/32 | 0.002 | 0.001 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | instructions:u / req | exploratory | +23.59% [+23.57, +23.61] | 0.02 | - | 0.04 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles:u / req | exploratory | +9.31% [+8.68, +9.94] | 0.58 | - | 1.60 | 32 | 0/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles:k / req | exploratory | -1.48% [-2.32, -0.64] | 0.85 | - | 2.36 | 32 | 25/32 | 0.002 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | cycles (u+k) / req | primary | +6.29% [+5.66, +6.93] | 0.60 | - | 1.66 | 32 | 0/32 | 0.000 | 0.000 | 0.000 | differs |
| v1.39.6 vs v1.40.2 | p50 latency (us) | exploratory | +9.93% [+7.79, +12.11] | 1.97 | - | 5.46 | 32 | 1/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.39.6 vs v1.40.2 | p99 latency (us) | exploratory | +14.52% [+8.42, +20.97] | 5.47 | - | 15.18 | 32 | 5/32 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.40.0 vs v1.40.2 | instructions:u / req | exploratory | -0.01% [-0.02, +0.00] | 0.01 | - | 0.03 | 32 | 20/32 | 0.215 | 0.074 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles:u / req | exploratory | +0.41% [-0.22, +1.05] | 0.63 | - | 1.76 | 32 | 13/32 | 0.377 | 0.224 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles:k / req | exploratory | -0.40% [-1.02, +0.22] | 0.62 | - | 1.72 | 32 | 17/32 | 0.860 | 0.313 | - | exploratory |
| v1.40.0 vs v1.40.2 | cycles (u+k) / req | primary | +0.18% [-0.40, +0.77] | 0.59 | - | 1.62 | 32 | 15/32 | 0.860 | 0.488 | 1.000 | not resolved |
| v1.40.0 vs v1.40.2 | p50 latency (us) | exploratory | +1.96% [+0.06, +3.89] | 1.88 | - | 5.20 | 32 | 11/32 | 0.110 | 0.048 | - | exploratory: interval excludes 0 |
| v1.40.0 vs v1.40.2 | p99 latency (us) | exploratory | +2.33% [-1.32, +6.12] | 3.63 | - | 10.08 | 32 | 16/32 | 1.000 | 0.262 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | instructions:u / req | exploratory | -0.00% [-0.01, +0.01] | 0.01 | - | 0.03 | 32 | 20/32 | 0.215 | 0.536 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:u / req | exploratory | -0.02% [-0.63, +0.60] | 0.61 | - | 1.70 | 32 | 15/32 | 0.860 | 0.978 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles:k / req | exploratory | -0.19% [-0.77, +0.39] | 0.58 | - | 1.62 | 32 | 16/32 | 1.000 | 0.665 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | cycles (u+k) / req | primary | -0.07% [-0.63, +0.50] | 0.57 | - | 1.58 | 32 | 14/32 | 0.597 | 0.905 | 1.000 | not resolved |
| v1.40.2-A2 vs v1.40.2 | p50 latency (us) | exploratory | +1.08% [-0.46, +2.64] | 1.53 | - | 4.25 | 32 | 12/32 | 0.215 | 0.142 | - | exploratory |
| v1.40.2-A2 vs v1.40.2 | p99 latency (us) | exploratory | -0.01% [-4.36, +4.55] | 4.45 | - | 12.35 | 32 | 13/32 | 0.377 | 0.832 | - | exploratory |

## Validity

1024 legs run, 1024 valid; 0 legs superseded by a re-run of their round.

