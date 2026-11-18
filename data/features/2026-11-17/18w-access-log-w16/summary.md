# features-access-log-w16

- Harness: 0.x bb8aa8144e69 week5
- Window: 2026-11-17T18:51:59Z to 2026-11-17T19:40:48Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1298682,2135608,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-15,40-55): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-15
- Envoy: 16 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 16 done (minimum 16, blocks of 8, cap 32, adaptive True), order rotate; stop: widest cycles_total half-width against its target 0.62% (s-w16 log-off-A2 vs log-off) <= target 1.00%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 3 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| log-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| log-text | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| log-json | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| log-off-A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s-w16 (`/s`, proxied, 20800 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| log-off | 16/16 | 162.8k | 363.9k | 189.6k | 553.8k (0.6%) | 402 | 679 | 32.5% |
| log-text | 16/16 | 169.4k | 381.1k | 189.9k | 571.6k (0.7%) | 413 | 686 | 33.5% |
| log-json | 16/16 | 172.5k | 383.7k | 190.3k | 574.3k (0.6%) | 416 | 720 | 33.7% |
| log-off-A2 | 16/16 | 162.8k | 364.0k | 189.5k | 552.8k (0.9%) | 402 | 652 | 32.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| log-text vs log-off | instructions:u / req | exploratory | +4.07% [+4.04, +4.09] | 0.02 | - | 0.04 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | cycles:u / req | exploratory | +4.89% [+4.29, +5.49] | 0.57 | - | 1.07 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | cycles:k / req | exploratory | +0.29% [-0.40, +0.99] | 0.70 | - | 1.31 | 16 | 7/16 | 0.804 | 0.433 | - | exploratory |
| log-text vs log-off | cycles (u+k) / req | primary | +3.32% [+2.72, +3.92] | 0.58 | - | 1.10 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| log-text vs log-off | p50 latency (us) | exploratory | +2.67% [+1.90, +3.43] | 0.75 | - | 1.40 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | p99 latency (us) | exploratory | +1.91% [-2.20, +6.20] | 4.12 | - | 7.72 | 16 | 7/16 | 0.804 | 0.433 | - | exploratory |
| log-json vs log-off | instructions:u / req | exploratory | +5.98% [+5.96, +6.00] | 0.02 | - | 0.04 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles:u / req | exploratory | +5.54% [+5.13, +5.96] | 0.39 | - | 0.74 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles:k / req | exploratory | +0.41% [-0.08, +0.91] | 0.49 | - | 0.92 | 16 | 6/16 | 0.454 | 0.159 | - | exploratory |
| log-json vs log-off | cycles (u+k) / req | primary | +3.79% [+3.37, +4.21] | 0.41 | - | 0.76 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| log-json vs log-off | p50 latency (us) | exploratory | +3.56% [+2.77, +4.37] | 0.77 | - | 1.45 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | p99 latency (us) | exploratory | +6.10% [+2.83, +9.48] | 3.13 | - | 5.88 | 16 | 2/16 | 0.004 | 0.003 | - | exploratory: interval excludes 0 |
| log-off-A2 vs log-off | instructions:u / req | exploratory | -0.00% [-0.02, +0.01] | 0.02 | - | 0.03 | 16 | 8/16 | 1.000 | 0.900 | - | exploratory |
| log-off-A2 vs log-off | cycles:u / req | exploratory | +0.26% [-0.32, +0.85] | 0.58 | - | 1.10 | 16 | 9/16 | 0.804 | 0.782 | - | exploratory |
| log-off-A2 vs log-off | cycles:k / req | exploratory | +0.30% [-0.43, +1.04] | 0.74 | - | 1.38 | 16 | 8/16 | 1.000 | 0.464 | - | exploratory |
| log-off-A2 vs log-off | cycles (u+k) / req | primary | +0.28% [-0.34, +0.90] | 0.62 | - | 1.16 | 16 | 8/16 | 1.000 | 0.632 | 0.354 | not resolved |
| log-off-A2 vs log-off | p50 latency (us) | exploratory | -0.08% [-0.62, +0.47] | 0.55 | - | 1.03 | 16 | 10/16 | 0.454 | 0.642 | - | exploratory |
| log-off-A2 vs log-off | p99 latency (us) | exploratory | -3.64% [-6.25, -0.95] | 2.75 | - | 5.16 | 16 | 14/16 | 0.004 | 0.013 | - | exploratory: interval excludes 0 |

## Validity

64 legs run, 64 valid; 0 legs superseded by a re-run of their round.

