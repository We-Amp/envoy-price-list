# features-tracing

- Harness: 0.x bb8aa8144e69 week5
- Window: 2026-11-17T16:07:26Z to 2026-11-17T17:29:40Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1781126,1851830,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 16 done (minimum 16, blocks of 16, cap 16, adaptive False), order rotate; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 6 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| trace-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| trace-1 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| trace-10 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| trace-100 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| trace-off | 16/16 | 163.9k | 344.0k | 180.6k | 524.8k (0.9%) | 400 | 623 | 31.2% |
| trace-1 | 16/16 | 186.6k | 380.4k | 182.9k | 564.5k (0.8%) | 428 | 708 | 33.2% |
| trace-10 | 16/16 | 198.3k | 390.8k | 185.2k | 576.3k (0.8%) | 435 | 793 | 33.9% |
| trace-100 | 16/16 | 315.2k | 498.3k | 203.4k | 702.6k (0.7%) | 492 | 1036 | 41.0% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| trace-1 vs trace-off | instructions:u / req | exploratory | +13.86% [+13.81, +13.91] | 0.04 | 0.02 | 0.08 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-1 vs trace-off | cycles:u / req | exploratory | +10.41% [+9.62, +11.21] | 0.72 | 0.32 | 1.36 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-1 vs trace-off | cycles:k / req | exploratory | +1.11% [+0.36, +1.87] | 0.75 | 0.41 | 1.41 | 16 | 4/16 | 0.077 | 0.005 | - | exploratory: interval excludes 0 |
| trace-1 vs trace-off | cycles (u+k) / req | primary | +7.21% [+6.48, +7.95] | 0.68 | 0.33 | 1.28 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| trace-1 vs trace-off | p50 latency (us) | exploratory | +6.94% [+5.90, +7.98] | 0.97 | 1.00 | 1.83 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-1 vs trace-off | p99 latency (us) | exploratory | +13.70% [+11.30, +16.14] | 2.13 | 1.24 | 4.00 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | instructions:u / req | exploratory | +21.04% [+20.98, +21.10] | 0.05 | 0.02 | 0.09 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | cycles:u / req | exploratory | +13.48% [+12.82, +14.15] | 0.59 | 0.32 | 1.10 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | cycles:k / req | exploratory | +2.14% [+1.24, +3.04] | 0.89 | 0.41 | 1.66 | 16 | 1/16 | 0.001 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | cycles (u+k) / req | primary | +9.58% [+8.88, +10.28] | 0.64 | 0.33 | 1.19 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| trace-10 vs trace-off | p50 latency (us) | exploratory | +8.31% [+6.86, +9.78] | 1.35 | 1.00 | 2.53 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | p99 latency (us) | exploratory | +26.35% [+23.36, +29.42] | 2.40 | 1.24 | 4.50 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | instructions:u / req | exploratory | +92.37% [+92.31, +92.43] | 0.03 | 0.02 | 0.06 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | cycles:u / req | exploratory | +44.76% [+43.91, +45.61] | 0.59 | 0.32 | 1.10 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | cycles:k / req | exploratory | +12.46% [+11.48, +13.44] | 0.87 | 0.41 | 1.63 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | cycles (u+k) / req | primary | +33.64% [+32.81, +34.48] | 0.63 | 0.33 | 1.18 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| trace-100 vs trace-off | p50 latency (us) | exploratory | +22.63% [+21.21, +24.07] | 1.17 | 1.00 | 2.19 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | p99 latency (us) | exploratory | +71.59% [+59.04, +85.14] | 7.60 | 1.24 | 14.26 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| trace-off | 16/16 | 164.7k | 198.3k | 82.2k | 280.9k (1.4%) | 216 | 372 | 25.5% |
| trace-1 | 16/16 | 180.9k | 225.9k | 83.4k | 309.7k (1.4%) | 231 | 399 | 27.8% |
| trace-10 | 16/16 | 191.5k | 239.1k | 85.2k | 324.6k (0.7%) | 237 | 481 | 29.2% |
| trace-100 | 16/16 | 297.0k | 340.4k | 101.3k | 441.3k (0.8%) | 320 | 697 | 39.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| trace-1 vs trace-off | instructions:u / req | exploratory | +9.80% [+9.79, +9.81] | 0.01 | 0.00 | 0.02 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-1 vs trace-off | cycles:u / req | exploratory | +13.55% [+12.27, +14.85] | 1.14 | 0.79 | 2.13 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-1 vs trace-off | cycles:k / req | exploratory | +1.12% [-0.15, +2.39] | 1.26 | 0.62 | 2.36 | 16 | 4/16 | 0.077 | 0.117 | - | exploratory |
| trace-1 vs trace-off | cycles (u+k) / req | primary | +9.91% [+8.66, +11.16] | 1.14 | 0.69 | 2.14 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| trace-1 vs trace-off | p50 latency (us) | exploratory | +6.95% [+6.14, +7.77] | 0.76 | 0.70 | 1.43 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-1 vs trace-off | p99 latency (us) | exploratory | +7.72% [+6.78, +8.68] | 0.88 | 0.67 | 1.66 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | instructions:u / req | exploratory | +16.23% [+16.21, +16.25] | 0.02 | 0.00 | 0.03 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | cycles:u / req | exploratory | +20.56% [+19.59, +21.54] | 0.81 | 0.79 | 1.52 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | cycles:k / req | exploratory | +3.70% [+2.88, +4.52] | 0.79 | 0.62 | 1.49 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | cycles (u+k) / req | primary | +15.61% [+14.74, +16.49] | 0.76 | 0.69 | 1.42 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| trace-10 vs trace-off | p50 latency (us) | exploratory | +10.04% [+8.98, +11.11] | 0.97 | 0.70 | 1.81 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-10 vs trace-off | p99 latency (us) | exploratory | +30.87% [+28.76, +33.00] | 1.62 | 0.67 | 3.04 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | instructions:u / req | exploratory | +80.27% [+80.23, +80.31] | 0.02 | 0.00 | 0.04 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | cycles:u / req | exploratory | +71.32% [+69.91, +72.74] | 0.83 | 0.79 | 1.55 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | cycles:k / req | exploratory | +23.07% [+21.79, +24.36] | 1.05 | 0.62 | 1.96 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | cycles (u+k) / req | primary | +57.17% [+55.84, +58.51] | 0.85 | 0.69 | 1.59 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| trace-100 vs trace-off | p50 latency (us) | exploratory | +48.99% [+46.85, +51.16] | 1.45 | 0.70 | 2.72 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| trace-100 vs trace-off | p99 latency (us) | exploratory | +99.02% [+80.59, +119.34] | 9.72 | 0.67 | 18.24 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

128 legs run, 128 valid; 0 legs superseded by a re-run of their round.

