# features-access-log

- Harness: 0.x bb8aa8144e69 week5
- Window: 2026-11-17T14:57:22Z to 2026-11-17T16:07:26Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2148155,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 18 done (minimum 18, blocks of 6, cap 30, adaptive True), order rotate; stop: widest cycles_total half-width against its target 1.02% (fh log-text vs log-off) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 4 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| log-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| log-text | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| log-json | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| log-off | 18/18 | 163.9k | 344.8k | 181.2k | 526.0k (0.5%) | 400 | 626 | 31.2% |
| log-text | 18/18 | 170.5k | 362.3k | 183.1k | 545.4k (0.6%) | 407 | 646 | 32.3% |
| log-json | 18/18 | 173.6k | 366.9k | 183.8k | 550.9k (0.5%) | 415 | 661 | 32.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| log-text vs log-off | instructions:u / req | exploratory | +4.04% [+4.01, +4.07] | 0.03 | 0.02 | 0.06 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | cycles:u / req | exploratory | +5.07% [+4.73, +5.42] | 0.32 | 0.32 | 0.65 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | cycles:k / req | exploratory | +1.02% [+0.46, +1.59] | 0.56 | 0.41 | 1.12 | 18 | 3/18 | 0.008 | 0.002 | - | exploratory: interval excludes 0 |
| log-text vs log-off | cycles (u+k) / req | primary | +3.68% [+3.33, +4.03] | 0.34 | 0.33 | 0.69 | 18 | 0/18 | 0.000 | 0.000 | 0.000 | differs |
| log-text vs log-off | p50 latency (us) | exploratory | +1.62% [+0.34, +2.92] | 1.27 | 1.00 | 2.55 | 18 | 5/18 | 0.096 | 0.030 | - | exploratory: interval excludes 0 |
| log-text vs log-off | p99 latency (us) | exploratory | +3.80% [+2.30, +5.32] | 1.45 | 1.24 | 2.92 | 18 | 1/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | instructions:u / req | exploratory | +5.93% [+5.91, +5.96] | 0.02 | 0.02 | 0.04 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles:u / req | exploratory | +6.25% [+5.89, +6.62] | 0.34 | 0.32 | 0.69 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles:k / req | exploratory | +1.49% [+0.96, +2.03] | 0.53 | 0.41 | 1.07 | 18 | 1/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles (u+k) / req | primary | +4.61% [+4.26, +4.97] | 0.34 | 0.33 | 0.68 | 18 | 0/18 | 0.000 | 0.000 | 0.000 | differs |
| log-json vs log-off | p50 latency (us) | exploratory | +3.99% [+2.83, +5.17] | 1.12 | 1.00 | 2.26 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | p99 latency (us) | exploratory | +7.11% [+5.53, +8.72] | 1.49 | 1.24 | 3.00 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| log-off | 18/18 | 164.7k | 197.9k | 83.3k | 281.1k (1.5%) | 216 | 369 | 25.5% |
| log-text | 18/18 | 171.2k | 212.8k | 83.0k | 295.9k (1.4%) | 224 | 385 | 26.8% |
| log-json | 18/18 | 173.8k | 215.6k | 84.1k | 299.4k (1.1%) | 225 | 390 | 27.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| log-text vs log-off | instructions:u / req | exploratory | +3.92% [+3.92, +3.93] | 0.01 | 0.00 | 0.01 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | cycles:u / req | exploratory | +7.82% [+6.72, +8.94] | 1.03 | 0.79 | 2.07 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | cycles:k / req | exploratory | +0.16% [-1.00, +1.34] | 1.17 | 0.62 | 2.35 | 18 | 8/18 | 0.815 | 0.899 | - | exploratory |
| log-text vs log-off | cycles (u+k) / req | primary | +5.56% [+4.49, +6.64] | 1.02 | 0.69 | 2.05 | 18 | 0/18 | 0.000 | 0.000 | 0.000 | differs |
| log-text vs log-off | p50 latency (us) | exploratory | +3.24% [+2.31, +4.18] | 0.91 | 0.70 | 1.82 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | p99 latency (us) | exploratory | +3.92% [+2.84, +5.00] | 1.04 | 0.67 | 2.09 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | instructions:u / req | exploratory | +5.51% [+5.50, +5.51] | 0.01 | 0.00 | 0.01 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles:u / req | exploratory | +9.45% [+8.51, +10.39] | 0.86 | 0.79 | 1.73 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles:k / req | exploratory | +1.37% [+0.50, +2.25] | 0.86 | 0.62 | 1.73 | 18 | 5/18 | 0.096 | 0.005 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles (u+k) / req | primary | +7.06% [+6.19, +7.93] | 0.81 | 0.69 | 1.63 | 18 | 0/18 | 0.000 | 0.000 | 0.000 | differs |
| log-json vs log-off | p50 latency (us) | exploratory | +4.25% [+3.55, +4.97] | 0.68 | 0.70 | 1.37 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | p99 latency (us) | exploratory | +5.65% [+4.78, +6.52] | 0.82 | 0.67 | 1.66 | 18 | 0/18 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

108 legs run, 108 valid; 0 legs superseded by a re-run of their round.

