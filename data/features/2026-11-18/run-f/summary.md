# features-run-f

- Harness: 0.x 4fc7986fe46f week5-s2
- Window: 2026-11-18T02:18:21Z to 2026-11-18T04:26:46Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 20 done (minimum 20, blocks of 10, cap 30, adaptive True), order rotate; stop: widest cycles_total half-width against its target 0.86% (fh lua-header vs filter-off) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 8 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| filter-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| lua-empty | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| lua-header | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| wasm-empty | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| wasm-header | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| filter-off | 20/20 | 163.8k | 344.5k | 181.4k | 526.9k (0.5%) | 398 | 621 | 31.2% |
| lua-empty | 20/20 | 181.5k | 382.1k | 182.5k | 564.7k (0.5%) | 428 | 708 | 33.2% |
| lua-header | 20/20 | 195.4k | 403.7k | 183.9k | 587.5k (0.6%) | 436 | 783 | 34.6% |
| wasm-empty | 20/20 | 184.2k | 393.6k | 183.6k | 577.6k (0.8%) | 433 | 738 | 34.0% |
| wasm-header | 20/20 | 203.0k | 423.8k | 183.8k | 607.9k (0.8%) | 459 | 829 | 35.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lua-empty vs filter-off | instructions:u / req | exploratory | +10.76% [+10.73, +10.78] | 0.02 | 0.02 | 0.05 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-empty vs filter-off | cycles:u / req | exploratory | +10.79% [+10.52, +11.06] | 0.24 | 0.47 | 0.52 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-empty vs filter-off | cycles:k / req | exploratory | +0.42% [-0.23, +1.07] | 0.65 | 0.78 | 1.38 | 20 | 8/20 | 0.503 | 0.177 | - | exploratory |
| lua-empty vs filter-off | cycles (u+k) / req | primary | +7.21% [+6.91, +7.52] | 0.28 | 0.54 | 0.61 | 20 | 0/20 | 0.000 | 0.000 | 0.000 | differs |
| lua-empty vs filter-off | p50 latency (us) | exploratory | +7.63% [+5.92, +9.37] | 1.60 | 1.22 | 3.42 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-empty vs filter-off | p99 latency (us) | exploratory | +14.12% [+11.33, +16.98] | 2.47 | 1.43 | 5.28 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-header vs filter-off | instructions:u / req | exploratory | +19.27% [+19.25, +19.29] | 0.02 | 0.02 | 0.03 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-header vs filter-off | cycles:u / req | exploratory | +17.25% [+16.86, +17.64] | 0.33 | 0.47 | 0.70 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-header vs filter-off | cycles:k / req | exploratory | +1.31% [+0.78, +1.85] | 0.52 | 0.78 | 1.12 | 20 | 2/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-header vs filter-off | cycles (u+k) / req | primary | +11.75% [+11.40, +12.10] | 0.31 | 0.54 | 0.67 | 20 | 0/20 | 0.000 | 0.000 | 0.000 | differs |
| lua-header vs filter-off | p50 latency (us) | exploratory | +10.30% [+8.70, +11.91] | 1.45 | 1.22 | 3.11 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-header vs filter-off | p99 latency (us) | exploratory | +25.56% [+21.38, +29.88] | 3.39 | 1.43 | 7.23 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-empty vs filter-off | instructions:u / req | exploratory | +12.43% [+12.40, +12.45] | 0.02 | 0.02 | 0.05 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-empty vs filter-off | cycles:u / req | exploratory | +14.26% [+13.81, +14.71] | 0.39 | 0.47 | 0.84 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-empty vs filter-off | cycles:k / req | exploratory | +0.95% [+0.40, +1.51] | 0.55 | 0.78 | 1.17 | 20 | 4/20 | 0.012 | 0.002 | - | exploratory: interval excludes 0 |
| wasm-empty vs filter-off | cycles (u+k) / req | primary | +9.67% [+9.23, +10.11] | 0.40 | 0.54 | 0.86 | 20 | 0/20 | 0.000 | 0.000 | 0.000 | differs |
| wasm-empty vs filter-off | p50 latency (us) | exploratory | +8.86% [+7.64, +10.09] | 1.12 | 1.22 | 2.40 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-empty vs filter-off | p99 latency (us) | exploratory | +21.44% [+17.15, +25.88] | 3.59 | 1.43 | 7.68 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-header vs filter-off | instructions:u / req | exploratory | +23.91% [+23.88, +23.93] | 0.02 | 0.02 | 0.05 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-header vs filter-off | cycles:u / req | exploratory | +23.11% [+22.73, +23.50] | 0.31 | 0.47 | 0.67 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-header vs filter-off | cycles:k / req | exploratory | +1.35% [+0.67, +2.03] | 0.67 | 0.78 | 1.43 | 20 | 5/20 | 0.041 | 0.001 | - | exploratory: interval excludes 0 |
| wasm-header vs filter-off | cycles (u+k) / req | primary | +15.60% [+15.19, +16.01] | 0.35 | 0.54 | 0.75 | 20 | 0/20 | 0.000 | 0.000 | 0.000 | differs |
| wasm-header vs filter-off | p50 latency (us) | exploratory | +16.11% [+14.87, +17.37] | 1.08 | 1.22 | 2.30 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-header vs filter-off | p99 latency (us) | exploratory | +36.66% [+30.44, +43.18] | 4.66 | 1.43 | 9.96 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| filter-off | 20/20 | 164.7k | 198.9k | 83.2k | 282.1k (1.3%) | 216 | 370 | 25.6% |
| lua-empty | 20/20 | 181.9k | 226.6k | 82.6k | 309.5k (1.2%) | 232 | 403 | 27.9% |
| lua-header | 20/20 | 195.2k | 245.5k | 84.4k | 330.1k (1.1%) | 243 | 427 | 29.6% |
| wasm-empty | 20/20 | 182.8k | 239.1k | 82.5k | 321.9k (1.3%) | 238 | 410 | 28.9% |
| wasm-header | 20/20 | 201.0k | 263.9k | 83.8k | 347.7k (1.0%) | 256 | 449 | 31.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lua-empty vs filter-off | instructions:u / req | exploratory | +10.42% [+10.42, +10.43] | 0.01 | 0.00 | 0.02 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-empty vs filter-off | cycles:u / req | exploratory | +14.08% [+13.12, +15.04] | 0.84 | 0.94 | 1.80 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-empty vs filter-off | cycles:k / req | exploratory | -0.52% [-1.27, +0.23] | 0.76 | 0.98 | 1.62 | 20 | 11/20 | 0.824 | 0.231 | - | exploratory |
| lua-empty vs filter-off | cycles (u+k) / req | primary | +9.77% [+8.93, +10.63] | 0.78 | 0.92 | 1.66 | 20 | 0/20 | 0.000 | 0.000 | 0.000 | differs |
| lua-empty vs filter-off | p50 latency (us) | exploratory | +7.00% [+6.03, +7.98] | 0.91 | 0.55 | 1.94 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-empty vs filter-off | p99 latency (us) | exploratory | +9.09% [+8.44, +9.75] | 0.60 | 0.60 | 1.29 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-header vs filter-off | instructions:u / req | exploratory | +18.46% [+18.44, +18.47] | 0.01 | 0.00 | 0.02 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-header vs filter-off | cycles:u / req | exploratory | +23.10% [+21.90, +24.32] | 0.98 | 0.94 | 2.10 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-header vs filter-off | cycles:k / req | exploratory | +1.32% [+0.64, +2.00] | 0.67 | 0.98 | 1.43 | 20 | 2/20 | 0.000 | 0.001 | - | exploratory: interval excludes 0, inside the A/A interval |
| lua-header vs filter-off | cycles (u+k) / req | primary | +16.68% [+15.69, +17.68] | 0.86 | 0.92 | 1.83 | 20 | 0/20 | 0.000 | 0.000 | 0.000 | differs |
| lua-header vs filter-off | p50 latency (us) | exploratory | +12.32% [+11.22, +13.44] | 0.99 | 0.55 | 2.12 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lua-header vs filter-off | p99 latency (us) | exploratory | +15.49% [+14.22, +16.77] | 1.11 | 0.60 | 2.36 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-empty vs filter-off | instructions:u / req | exploratory | +10.97% [+10.96, +10.98] | 0.01 | 0.00 | 0.01 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-empty vs filter-off | cycles:u / req | exploratory | +19.66% [+18.44, +20.89] | 1.02 | 0.94 | 2.19 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-empty vs filter-off | cycles:k / req | exploratory | -0.80% [-1.64, +0.05] | 0.85 | 0.98 | 1.82 | 20 | 14/20 | 0.115 | 0.070 | - | exploratory |
| wasm-empty vs filter-off | cycles (u+k) / req | primary | +13.63% [+12.57, +14.69] | 0.93 | 0.92 | 1.99 | 20 | 0/20 | 0.000 | 0.000 | 0.000 | differs |
| wasm-empty vs filter-off | p50 latency (us) | exploratory | +9.30% [+8.36, +10.25] | 0.86 | 0.55 | 1.84 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-empty vs filter-off | p99 latency (us) | exploratory | +11.00% [+10.18, +11.83] | 0.74 | 0.60 | 1.59 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-header vs filter-off | instructions:u / req | exploratory | +21.98% [+21.98, +21.99] | 0.01 | 0.00 | 0.01 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-header vs filter-off | cycles:u / req | exploratory | +32.50% [+31.32, +33.69] | 0.89 | 0.94 | 1.91 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-header vs filter-off | cycles:k / req | exploratory | +1.09% [+0.34, +1.84] | 0.74 | 0.98 | 1.58 | 20 | 6/20 | 0.115 | 0.008 | - | exploratory: interval excludes 0, inside the A/A interval |
| wasm-header vs filter-off | cycles (u+k) / req | primary | +23.24% [+22.25, +24.24] | 0.81 | 0.92 | 1.73 | 20 | 0/20 | 0.000 | 0.000 | 0.000 | differs |
| wasm-header vs filter-off | p50 latency (us) | exploratory | +18.02% [+16.61, +19.44] | 1.20 | 0.55 | 2.56 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| wasm-header vs filter-off | p99 latency (us) | exploratory | +21.47% [+20.10, +22.85] | 1.14 | 0.60 | 2.43 | 20 | 0/20 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

200 legs run, 200 valid; 0 legs superseded by a re-run of their round.

