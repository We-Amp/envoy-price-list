# release-record-c

- Harness: 0.1.0 e3caa9b1319f
- Window: 2026-11-16T20:23:41Z to 2026-11-16T22:26:44Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1504567,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 24 done (minimum 24, blocks of 24, cap 24, adaptive False), order rotate; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 6 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| v1.32.13 | 0c686a2237a51b1a07cdc4911dcf90c75f02f82d/1.32.13/Clean/RELEASE/BoringSSL | `dfd8f773a8dbfc0aeb97139e2fbf0f1a` |
| v1.37.11 | 0ce6eee982e6df4a873b28184b396eeacfad938f/1.37.11/Clean/RELEASE/BoringSSL | `54525e87b6e9422e1474bc1554e433c3` |
| v1.38.9 | 17e27840396c1fa3196f184fcb5db1ab13850504/1.38.9/Clean/RELEASE/BoringSSL | `2358b9b2f859b5f0f050181e0b295c35` |
| v1.40.2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s-hi (`/s`, proxied, 12000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 24/24 | 185.8k | - | - | 448.7k (0.8%) | 409 | 917 | 60.6% |
| v1.37.11 | 24/24 | 167.7k | - | - | 449.4k (0.8%) | 419 | 978 | 60.7% |
| v1.38.9 | 24/24 | 174.3k | - | - | 454.1k (1.0%) | 427 | 982 | 61.3% |
| v1.40.2 | 24/24 | 163.0k | - | - | 457.7k (0.7%) | 432 | 938 | 61.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.32.13 vs v1.40.2 | instructions:u / req | exploratory | +14.00% [+13.98, +14.03] | 0.02 | - | 0.06 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles (u+k) / req | primary | -1.99% [-2.44, -1.54] | 0.46 | - | 1.09 | 24 | 23/24 | 0.000 | 0.000 | 0.000 | differs |
| v1.32.13 vs v1.40.2 | p50 latency (us) | exploratory | -4.93% [-6.15, -3.69] | 1.29 | - | 3.06 | 24 | 22/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | p99 latency (us) | exploratory | -3.24% [-8.62, +2.47] | 5.73 | - | 13.57 | 24 | 16/24 | 0.152 | 0.252 | - | exploratory |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +2.93% [+2.90, +2.96] | 0.03 | - | 0.06 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | -1.75% [-2.24, -1.25] | 0.50 | - | 1.19 | 24 | 23/24 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | -2.39% [-3.59, -1.17] | 1.24 | - | 2.93 | 24 | 19/24 | 0.003 | 0.001 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | -0.88% [-7.74, +6.49] | 7.18 | - | 16.99 | 24 | 13/24 | 0.839 | 0.768 | - | exploratory |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +6.96% [+6.93, +7.00] | 0.03 | - | 0.07 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | -0.53% [-1.08, +0.01] | 0.55 | - | 1.30 | 24 | 16/24 | 0.152 | 0.060 | 0.055 | not resolved |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | -0.52% [-2.15, +1.14] | 1.66 | - | 3.92 | 24 | 14/24 | 0.541 | 0.473 | - | exploratory |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | +1.75% [-4.45, +8.34] | 6.28 | - | 14.87 | 24 | 10/24 | 0.541 | 0.456 | - | exploratory |

## fh-hi (`/fh`, direct_headers, 18400 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 24/24 | 230.7k | - | - | 267.3k (1.4%) | 274 | 555 | 55.1% |
| v1.37.11 | 24/24 | 189.2k | - | - | 255.0k (0.8%) | 258 | 498 | 52.9% |
| v1.38.9 | 24/24 | 202.3k | - | - | 259.5k (0.9%) | 264 | 504 | 53.7% |
| v1.40.2 | 24/24 | 164.4k | - | - | 247.5k (0.9%) | 243 | 476 | 51.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.32.13 vs v1.40.2 | instructions:u / req | exploratory | +40.33% [+40.32, +40.35] | 0.01 | - | 0.03 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | cycles (u+k) / req | primary | +7.71% [+6.97, +8.45] | 0.69 | - | 1.63 | 24 | 0/24 | 0.000 | 0.000 | 0.000 | differs |
| v1.32.13 vs v1.40.2 | p50 latency (us) | exploratory | +12.42% [+10.31, +14.57] | 1.90 | - | 4.49 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.32.13 vs v1.40.2 | p99 latency (us) | exploratory | +15.46% [+9.15, +22.13] | 5.62 | - | 13.31 | 24 | 2/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | instructions:u / req | exploratory | +15.07% [+15.06, +15.08] | 0.01 | - | 0.03 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | cycles (u+k) / req | primary | +2.94% [+2.43, +3.46] | 0.50 | - | 1.19 | 24 | 0/24 | 0.000 | 0.000 | 0.000 | differs |
| v1.37.11 vs v1.40.2 | p50 latency (us) | exploratory | +5.40% [+3.27, +7.57] | 2.04 | - | 4.83 | 24 | 3/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.37.11 vs v1.40.2 | p99 latency (us) | exploratory | +5.27% [+0.33, +10.45] | 4.80 | - | 11.38 | 24 | 9/24 | 0.307 | 0.034 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | instructions:u / req | exploratory | +23.03% [+23.02, +23.04] | 0.01 | - | 0.02 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | cycles (u+k) / req | primary | +4.60% [+4.07, +5.14] | 0.51 | - | 1.21 | 24 | 0/24 | 0.000 | 0.000 | 0.000 | differs |
| v1.38.9 vs v1.40.2 | p50 latency (us) | exploratory | +7.61% [+5.54, +9.73] | 1.95 | - | 4.61 | 24 | 2/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| v1.38.9 vs v1.40.2 | p99 latency (us) | exploratory | +7.94% [+3.81, +12.23] | 3.90 | - | 9.24 | 24 | 6/24 | 0.023 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

192 legs run, 192 valid; 0 legs superseded by a re-run of their round.

