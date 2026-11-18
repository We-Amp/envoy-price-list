# features-lc-j16

- Harness: 0.x 4fc7986fe46f week5-s2
- Window: 2026-11-18T05:49:14Z to 2026-11-18T06:35:30Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 12, cap 12, adaptive False), order abba; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 3 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| comp-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| comp-off-A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## j16-a (`/j16`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| comp-off | 12/12 | 171.4k | 349.9k | 193.9k | 543.9k (0.7%) | 411 | 649 | 32.2% |
| comp-off-A2 | 12/12 | 171.4k | 348.4k | 193.4k | 541.0k (0.5%) | 409 | 645 | 32.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| comp-off-A2 vs comp-off | instructions:u / req | exploratory | -0.01% [-0.04, +0.03] | 0.04 | - | 0.06 | 12 | 7/12 | 0.774 | 0.470 | - | exploratory |
| comp-off-A2 vs comp-off | cycles:u / req | exploratory | -0.38% [-0.95, +0.19] | 0.57 | - | 0.90 | 12 | 8/12 | 0.388 | 0.204 | - | exploratory |
| comp-off-A2 vs comp-off | cycles:k / req | exploratory | -0.48% [-1.22, +0.26] | 0.74 | - | 1.17 | 12 | 8/12 | 0.388 | 0.176 | - | exploratory |
| comp-off-A2 vs comp-off | cycles (u+k) / req | primary | -0.42% [-1.02, +0.19] | 0.61 | - | 0.96 | 12 | 7/12 | 0.774 | 0.129 | 0.482 | not resolved |
| comp-off-A2 vs comp-off | p50 latency (us) | exploratory | -0.47% [-2.01, +1.09] | 1.55 | - | 2.45 | 12 | 6/12 | 1.000 | 0.733 | - | exploratory |
| comp-off-A2 vs comp-off | p99 latency (us) | exploratory | -0.95% [-3.16, +1.31] | 2.26 | - | 3.55 | 12 | 6/12 | 1.000 | 0.519 | - | exploratory |

## j16-b (`/j16`, proxied, 7600 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| comp-off | 12/12 | 171.2k | 325.6k | 181.0k | 506.4k (0.8%) | 382 | 692 | 43.4% |
| comp-off-A2 | 12/12 | 171.2k | 324.9k | 180.8k | 505.0k (0.7%) | 383 | 679 | 43.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| comp-off-A2 vs comp-off | instructions:u / req | exploratory | +0.01% [-0.04, +0.06] | 0.05 | - | 0.08 | 12 | 6/12 | 1.000 | 0.677 | - | exploratory |
| comp-off-A2 vs comp-off | cycles:u / req | exploratory | -0.20% [-0.89, +0.49] | 0.69 | - | 1.08 | 12 | 5/12 | 0.774 | 0.791 | - | exploratory |
| comp-off-A2 vs comp-off | cycles:k / req | exploratory | -0.60% [-1.38, +0.19] | 0.79 | - | 1.24 | 12 | 9/12 | 0.146 | 0.151 | - | exploratory |
| comp-off-A2 vs comp-off | cycles (u+k) / req | primary | -0.34% [-1.01, +0.32] | 0.67 | - | 1.05 | 12 | 6/12 | 1.000 | 0.519 | 0.563 | not resolved |
| comp-off-A2 vs comp-off | p50 latency (us) | exploratory | -0.06% [-1.22, +1.12] | 1.17 | - | 1.84 | 12 | 7/12 | 0.774 | 0.850 | - | exploratory |
| comp-off-A2 vs comp-off | p99 latency (us) | exploratory | -4.71% [-10.74, +1.74] | 6.54 | - | 10.30 | 12 | 7/12 | 0.774 | 0.266 | - | exploratory |

## j16-c (`/j16`, proxied, 11200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| comp-off | 12/12 | 170.6k | 308.9k | 167.7k | 476.9k (0.5%) | 433 | 942 | 59.6% |
| comp-off-A2 | 12/12 | 170.5k | 309.3k | 167.4k | 476.6k (0.6%) | 438 | 1016 | 59.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| comp-off-A2 vs comp-off | instructions:u / req | exploratory | -0.05% [-0.09, -0.01] | 0.04 | - | 0.06 | 12 | 9/12 | 0.146 | 0.034 | - | exploratory: interval excludes 0 |
| comp-off-A2 vs comp-off | cycles:u / req | exploratory | +0.16% [-0.47, +0.80] | 0.64 | - | 1.00 | 12 | 5/12 | 0.774 | 0.470 | - | exploratory |
| comp-off-A2 vs comp-off | cycles:k / req | exploratory | -0.57% [-1.11, -0.02] | 0.55 | - | 0.87 | 12 | 8/12 | 0.388 | 0.052 | - | exploratory: interval excludes 0 |
| comp-off-A2 vs comp-off | cycles (u+k) / req | primary | -0.09% [-0.64, +0.46] | 0.55 | - | 0.87 | 12 | 7/12 | 0.774 | 0.791 | 0.718 | not resolved |
| comp-off-A2 vs comp-off | p50 latency (us) | exploratory | +1.84% [-0.49, +4.23] | 2.31 | - | 3.64 | 12 | 5/12 | 0.774 | 0.176 | - | exploratory |
| comp-off-A2 vs comp-off | p99 latency (us) | exploratory | +1.17% [-8.90, +12.35] | 10.48 | - | 16.50 | 12 | 5/12 | 0.774 | 0.733 | - | exploratory |

## Validity

72 legs run, 72 valid; 0 legs superseded by a re-run of their round.

