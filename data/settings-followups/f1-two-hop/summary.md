# smf-two-hop

- Harness: 0.1.0 ed217ec477fa
- Window: 2026-11-14T11:37:38Z to 2026-11-14T12:19:09Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2295236,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 16 done (minimum 16, blocks of 8, cap 32, adaptive True), order rotate; stop: widest cycles_total_per_hop half-width 1.32% (s two-hop-stock vs one-hop) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total_per_hop, Holm across 6 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| one-hop | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| one-hop-ppd | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| two-hop-stock | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| two-hop-ppd | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| one-hop | 16/16 | 163.9k | 345.6k | 181.8k | 528.0k (0.8%) | 398 | 626 | 31.3% |
| one-hop-ppd | 16/16 | 164.7k | 345.3k | 181.2k | 526.2k (0.6%) | 392 | 646 | 31.2% |
| two-hop-stock | 16/16 | 163.1k | 344.7k | 159.0k | 504.0k (0.6%) | 681 | 1072 | 29.7% |
| two-hop-ppd | 16/16 | 163.6k | 344.3k | 171.8k | 515.6k (0.7%) | 648 | 1034 | 30.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| one-hop-ppd vs one-hop | instructions:u / req | exploratory | +0.47% [+0.45, +0.49] | 0.02 | - | 0.04 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| one-hop-ppd vs one-hop | cycles:u / req | exploratory | +0.10% [-0.34, +0.54] | 0.44 | - | 0.83 | 16 | 5/16 | 0.210 | 0.375 | - | exploratory |
| one-hop-ppd vs one-hop | cycles:k / req | exploratory | -0.53% [-1.22, +0.17] | 0.70 | - | 1.31 | 16 | 10/16 | 0.454 | 0.130 | - | exploratory |
| one-hop-ppd vs one-hop | cycles (u+k) / req | exploratory | -0.12% [-0.61, +0.38] | 0.49 | - | 0.93 | 16 | 8/16 | 1.000 | 0.980 | - | exploratory |
| one-hop-ppd vs one-hop | cycles (u+k) / req, all hops | exploratory | -0.12% [-0.61, +0.38] | 0.49 | - | 0.93 | 16 | 8/16 | 1.000 | 0.980 | - | exploratory |
| one-hop-ppd vs one-hop | cycles (u+k) / req / hop | primary | -0.12% [-0.61, +0.38] | 0.49 | - | 0.93 | 16 | 8/16 | 1.000 | 0.980 | 0.614 | not resolved |
| one-hop-ppd vs one-hop | instructions:u / req, all hops | exploratory | +0.47% [+0.45, +0.49] | 0.02 | - | 0.04 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| one-hop-ppd vs one-hop | p50 latency (us) | exploratory | -1.21% [-2.26, -0.15] | 1.07 | - | 2.01 | 16 | 11/16 | 0.210 | 0.044 | - | exploratory: interval excludes 0 |
| one-hop-ppd vs one-hop | p99 latency (us) | exploratory | +3.94% [+1.42, +6.53] | 2.46 | - | 4.61 | 16 | 3/16 | 0.021 | 0.005 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop | instructions:u / req | exploratory | -0.50% [-0.54, -0.45] | 0.04 | - | 0.08 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop | cycles:u / req | exploratory | -0.16% [-0.61, +0.29] | 0.45 | - | 0.85 | 16 | 9/16 | 0.804 | 0.495 | - | exploratory |
| two-hop-stock vs one-hop | cycles:k / req | exploratory | -12.76% [-13.45, -12.06] | 0.80 | - | 1.49 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop | cycles (u+k) / req | exploratory | -4.51% [-5.00, -4.02] | 0.51 | - | 0.96 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop | cycles (u+k) / req, all hops | exploratory | +89.49% [+87.00, +92.02] | 1.32 | - | 2.48 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop | cycles (u+k) / req / hop | primary | -5.25% [-6.50, -3.99] | 1.32 | - | 2.48 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| two-hop-stock vs one-hop | instructions:u / req, all hops | exploratory | +106.55% [+106.40, +106.71] | 0.07 | - | 0.14 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop | p50 latency (us) | exploratory | +79.45% [+70.01, +89.40] | 5.40 | - | 10.14 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop | p99 latency (us) | exploratory | +74.68% [+65.60, +84.25] | 5.34 | - | 10.02 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop | instructions:u / req | exploratory | -0.15% [-0.17, -0.12] | 0.02 | - | 0.04 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop | cycles:u / req | exploratory | -0.15% [-0.61, +0.31] | 0.46 | - | 0.87 | 16 | 10/16 | 0.454 | 0.669 | - | exploratory |
| two-hop-ppd vs one-hop | cycles:k / req | exploratory | -5.56% [-6.37, -4.74] | 0.86 | - | 1.62 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop | cycles (u+k) / req | exploratory | -2.02% [-2.55, -1.48] | 0.54 | - | 1.02 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop | cycles (u+k) / req, all hops | exploratory | +99.32% [+98.29, +100.35] | 0.52 | - | 0.97 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop | cycles (u+k) / req / hop | primary | -0.34% [-0.85, +0.18] | 0.52 | - | 0.97 | 16 | 9/16 | 0.804 | 0.323 | 0.540 | not resolved |
| two-hop-ppd vs one-hop | instructions:u / req, all hops | exploratory | +108.10% [+108.06, +108.14] | 0.02 | - | 0.04 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop | p50 latency (us) | exploratory | +63.04% [+61.50, +64.60] | 0.95 | - | 1.79 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop | p99 latency (us) | exploratory | +66.15% [+62.80, +69.57] | 2.04 | - | 3.82 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop-ppd | instructions:u / req | exploratory | -0.96% [-1.00, -0.93] | 0.03 | - | 0.06 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop-ppd | cycles:u / req | exploratory | -0.26% [-0.68, +0.16] | 0.42 | - | 0.79 | 16 | 10/16 | 0.454 | 0.274 | - | exploratory |
| two-hop-stock vs one-hop-ppd | cycles:k / req | exploratory | -12.29% [-12.78, -11.81] | 0.55 | - | 1.04 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop-ppd | cycles (u+k) / req | exploratory | -4.40% [-4.81, -3.98] | 0.43 | - | 0.81 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop-ppd | cycles (u+k) / req, all hops | exploratory | +89.72% [+87.52, +91.95] | 1.17 | - | 2.19 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop-ppd | cycles (u+k) / req / hop | primary | -5.14% [-6.24, -4.03] | 1.17 | - | 2.19 | 16 | 16/16 | 0.000 | 0.000 | 0.000 | differs |
| two-hop-stock vs one-hop-ppd | instructions:u / req, all hops | exploratory | +105.58% [+105.42, +105.74] | 0.08 | - | 0.14 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop-ppd | p50 latency (us) | exploratory | +81.65% [+72.55, +91.23] | 5.14 | - | 9.64 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-stock vs one-hop-ppd | p99 latency (us) | exploratory | +68.05% [+59.97, +76.53] | 4.92 | - | 9.24 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop-ppd | instructions:u / req | exploratory | -0.62% [-0.63, -0.60] | 0.01 | - | 0.03 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop-ppd | cycles:u / req | exploratory | -0.25% [-0.68, +0.19] | 0.43 | - | 0.81 | 16 | 10/16 | 0.454 | 0.252 | - | exploratory |
| two-hop-ppd vs one-hop-ppd | cycles:k / req | exploratory | -5.05% [-5.69, -4.42] | 0.67 | - | 1.26 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop-ppd | cycles (u+k) / req | exploratory | -1.90% [-2.37, -1.42] | 0.48 | - | 0.91 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop-ppd | cycles (u+k) / req, all hops | exploratory | +99.56% [+98.85, +100.27] | 0.36 | - | 0.67 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop-ppd | cycles (u+k) / req / hop | primary | -0.22% [-0.58, +0.14] | 0.36 | - | 0.67 | 16 | 10/16 | 0.454 | 0.231 | 0.540 | not resolved |
| two-hop-ppd vs one-hop-ppd | instructions:u / req, all hops | exploratory | +107.12% [+107.10, +107.14] | 0.01 | - | 0.02 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop-ppd | p50 latency (us) | exploratory | +65.04% [+63.67, +66.43] | 0.84 | - | 1.57 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs one-hop-ppd | p99 latency (us) | exploratory | +59.84% [+55.85, +63.94] | 2.53 | - | 4.74 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs two-hop-stock | instructions:u / req | exploratory | +0.35% [+0.33, +0.38] | 0.03 | - | 0.05 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs two-hop-stock | cycles:u / req | exploratory | +0.01% [-0.35, +0.37] | 0.36 | - | 0.67 | 16 | 9/16 | 0.804 | 0.900 | - | exploratory |
| two-hop-ppd vs two-hop-stock | cycles:k / req | exploratory | +8.26% [+7.58, +8.93] | 0.62 | - | 1.17 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs two-hop-stock | cycles (u+k) / req | exploratory | +2.61% [+2.18, +3.04] | 0.42 | - | 0.79 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs two-hop-stock | cycles (u+k) / req, all hops | exploratory | +5.19% [+3.85, +6.54] | 1.28 | - | 2.40 | 16 | 1/16 | 0.001 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs two-hop-stock | cycles (u+k) / req / hop | primary | +5.19% [+3.85, +6.54] | 1.28 | - | 2.40 | 16 | 1/16 | 0.001 | 0.000 | 0.000 | differs |
| two-hop-ppd vs two-hop-stock | instructions:u / req, all hops | exploratory | +0.75% [+0.67, +0.83] | 0.08 | - | 0.14 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs two-hop-stock | p50 latency (us) | exploratory | -9.14% [-13.70, -4.35] | 5.14 | - | 9.65 | 16 | 16/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop-ppd vs two-hop-stock | p99 latency (us) | exploratory | -4.88% [-8.96, -0.62] | 4.39 | - | 8.23 | 16 | 11/16 | 0.210 | 0.034 | - | exploratory: interval excludes 0 |

## Validity

64 legs run, 64 valid; 0 legs superseded by a re-run of their round.

