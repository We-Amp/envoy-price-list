# features-compression

- Harness: 0.x 4fc7986fe46f week5-s2
- Window: 2026-11-18T04:26:46Z to 2026-11-18T05:49:13Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2294582,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 16 done (minimum 16, blocks of 8, cap 24, adaptive True), order rotate; stop: widest cycles_total half-width against its target 0.76% (j4 zstd vs comp-off) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 6 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| comp-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| gzip | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| brotli | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| zstd | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## j4 (`/j4`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| comp-off | 16/16 | 168.6k | 347.4k | 181.0k | 528.4k (1.0%) | 401 | 628 | 31.5% |
| gzip | 16/16 | 584.1k | 613.0k | 179.1k | 792.2k (0.5%) | 607 | 1583 | 45.9% |
| brotli | 16/16 | 534.5k | 632.8k | 177.7k | 810.4k (0.6%) | 622 | 1625 | 46.9% |
| zstd | 16/16 | 402.5k | 638.9k | 178.0k | 816.7k (0.8%) | 628 | 1570 | 47.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gzip vs comp-off | instructions:u / req | exploratory | +246.48% [+246.43, +246.53] | 0.01 | - | 0.03 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | cycles:u / req | exploratory | +76.01% [+75.27, +76.74] | 0.42 | - | 0.79 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | cycles:k / req | exploratory | -1.20% [-2.07, -0.32] | 0.89 | - | 1.66 | 16 | 12/16 | 0.077 | 0.011 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | cycles (u+k) / req | primary | +49.55% [+48.80, +50.31] | 0.50 | - | 0.95 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| gzip vs comp-off | p50 latency (us) | exploratory | +51.48% [+48.98, +54.02] | 1.66 | - | 3.12 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | p99 latency (us) | exploratory | +145.84% [+126.14, +167.26] | 8.35 | - | 15.68 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | instructions:u / req | exploratory | +217.08% [+217.03, +217.12] | 0.02 | - | 0.03 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | cycles:u / req | exploratory | +81.62% [+80.59, +82.66] | 0.57 | - | 1.07 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | cycles:k / req | exploratory | -1.98% [-3.07, -0.87] | 1.12 | - | 2.10 | 16 | 14/16 | 0.004 | 0.001 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | cycles (u+k) / req | primary | +52.98% [+51.94, +54.03] | 0.68 | - | 1.28 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| brotli vs comp-off | p50 latency (us) | exploratory | +56.34% [+52.55, +60.23] | 2.46 | - | 4.61 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | p99 latency (us) | exploratory | +165.24% [+142.34, +190.31] | 9.03 | - | 16.94 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | instructions:u / req | exploratory | +138.72% [+138.66, +138.79] | 0.03 | - | 0.05 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | cycles:u / req | exploratory | +83.23% [+82.03, +84.43] | 0.65 | - | 1.23 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | cycles:k / req | exploratory | -2.20% [-3.27, -1.12] | 1.10 | - | 2.07 | 16 | 14/16 | 0.004 | 0.001 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | cycles (u+k) / req | primary | +53.96% [+52.79, +55.13] | 0.76 | - | 1.42 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| zstd vs comp-off | p50 latency (us) | exploratory | +57.44% [+54.45, +60.49] | 1.92 | - | 3.60 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | p99 latency (us) | exploratory | +148.82% [+129.81, +169.40] | 7.95 | - | 14.91 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## j16 (`/j16`, proxied, 4000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| comp-off | 16/16 | 171.6k | 368.0k | 200.8k | 568.4k (1.0%) | 416 | 623 | 26.3% |
| gzip | 16/16 | 1644.9k | 1125.4k | 191.5k | 1317.5k (0.3%) | 1041 | 3378 | 58.2% |
| brotli | 16/16 | 1229.8k | 1025.6k | 192.7k | 1218.3k (0.3%) | 905 | 3036 | 53.8% |
| zstd | 16/16 | 762.9k | 833.2k | 195.2k | 1029.2k (0.6%) | 720 | 1690 | 45.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gzip vs comp-off | instructions:u / req | exploratory | +858.39% [+858.13, +858.64] | 0.03 | 0.03 | 0.05 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | cycles:u / req | exploratory | +205.57% [+204.18, +206.97] | 0.46 | 0.81 | 0.86 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | cycles:k / req | exploratory | -5.05% [-5.82, -4.27] | 0.82 | 0.80 | 1.53 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | cycles (u+k) / req | primary | +130.97% [+129.78, +132.16] | 0.52 | 0.78 | 0.97 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| gzip vs comp-off | p50 latency (us) | exploratory | +149.31% [+137.91, +161.27] | 4.68 | 2.17 | 8.79 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | p99 latency (us) | exploratory | +431.67% [+381.99, +486.47] | 9.81 | 1.82 | 18.41 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | instructions:u / req | exploratory | +616.51% [+616.30, +616.72] | 0.03 | 0.03 | 0.05 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | cycles:u / req | exploratory | +178.36% [+176.96, +179.77] | 0.50 | 0.81 | 0.95 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | cycles:k / req | exploratory | -4.56% [-5.29, -3.83] | 0.77 | 0.80 | 1.44 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | cycles (u+k) / req | primary | +113.57% [+112.40, +114.75] | 0.55 | 0.78 | 1.03 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| brotli vs comp-off | p50 latency (us) | exploratory | +119.12% [+113.71, +124.66] | 2.50 | 2.17 | 4.69 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| brotli vs comp-off | p99 latency (us) | exploratory | +406.01% [+367.99, +447.12] | 7.81 | 1.82 | 14.66 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | instructions:u / req | exploratory | +341.52% [+338.65, +344.41] | 0.65 | 0.03 | 1.23 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | cycles:u / req | exploratory | +126.00% [+124.66, +127.34] | 0.59 | 0.81 | 1.11 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | cycles:k / req | exploratory | -3.40% [-4.28, -2.50] | 0.92 | 0.80 | 1.73 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | cycles (u+k) / req | primary | +80.16% [+78.99, +81.35] | 0.65 | 0.78 | 1.23 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| zstd vs comp-off | p50 latency (us) | exploratory | +74.54% [+70.94, +78.21] | 2.08 | 2.17 | 3.91 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| zstd vs comp-off | p99 latency (us) | exploratory | +188.03% [+158.47, +220.97] | 10.83 | 1.82 | 20.32 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

128 legs run, 128 valid; 0 legs superseded by a re-run of their round.

