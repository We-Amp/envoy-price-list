# rt-n1

- Harness: 0.1.0 9a35ff71ca41
- Window: 2026-11-16T04:48:02Z to 2026-11-16T05:34:03Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 12, adaptive False), order rotate; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 4 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| base | 8ce942ce56c433e352d2657603d7bf33d4dbb4b4/1.41.0-dev/Clean/RELEASE/BoringSSL | `e59880d7374383c6df4dcaad6c71dd7e` |
| d1v4 | 28f612622a9038858664c9118eba90a2b35d2c96/1.41.0-dev/Clean/RELEASE/BoringSSL | `7fac057ec1629117f7ebcccfbf52b923` |
| d2v3 | patched-build/1.41.0-dev/Clean/RELEASE/BoringSSL | `bf9fd4b39b85602a840480224fe3a1b2` |

## n1-lo (`/target/x`, routes, 2000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 12/12 | 76.3k | 210.9k | 112.7k | 324.7k (1.3%) | 233 | 361 | 8.7% |
| d1v4 | 12/12 | 76.3k | 207.9k | 114.0k | 321.6k (0.8%) | 231 | 365 | 8.7% |
| d2v3 | 12/12 | 76.4k | 209.0k | 113.4k | 322.3k (1.4%) | 230 | 356 | 8.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d1v4 vs base | instructions:u / req | exploratory | +0.02% [+0.01, +0.02] | 0.00 | - | 0.01 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:u / req | exploratory | -1.55% [-2.41, -0.70] | 0.87 | - | 1.37 | 12 | 10/12 | 0.039 | 0.002 | - | exploratory: interval excludes 0 |
| d1v4 vs base | cycles:k / req | exploratory | -0.52% [-2.19, +1.19] | 1.70 | - | 2.68 | 12 | 5/12 | 0.774 | 0.791 | - | exploratory |
| d1v4 vs base | cycles (u+k) / req | primary | -1.19% [-2.17, -0.21] | 0.99 | - | 1.57 | 12 | 9/12 | 0.146 | 0.027 | 0.089 | not resolved |
| d1v4 vs base | p50 latency (us) | exploratory | -0.50% [-1.30, +0.30] | 0.81 | - | 1.27 | 12 | 8/12 | 0.388 | 0.266 | - | exploratory |
| d1v4 vs base | p99 latency (us) | exploratory | +0.93% [-0.55, +2.44] | 1.48 | - | 2.33 | 12 | 5/12 | 0.774 | 0.266 | - | exploratory |
| d2v3 vs base | instructions:u / req | exploratory | +0.04% [+0.04, +0.05] | 0.01 | - | 0.01 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:u / req | exploratory | -1.16% [-1.70, -0.61] | 0.55 | - | 0.87 | 12 | 11/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:k / req | exploratory | +0.21% [-2.02, +2.49] | 2.25 | - | 3.54 | 12 | 4/12 | 0.388 | 0.677 | - | exploratory |
| d2v3 vs base | cycles (u+k) / req | primary | -0.68% [-1.64, +0.29] | 0.97 | - | 1.52 | 12 | 10/12 | 0.039 | 0.129 | 0.323 | not resolved |
| d2v3 vs base | p50 latency (us) | exploratory | -0.78% [-1.70, +0.15] | 0.93 | - | 1.46 | 12 | 8/12 | 0.388 | 0.092 | - | exploratory |
| d2v3 vs base | p99 latency (us) | exploratory | -0.72% [-2.53, +1.11] | 1.83 | - | 2.89 | 12 | 10/12 | 0.039 | 0.204 | - | exploratory |

## n1-hi (`/target/x`, routes, 22000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 12/12 | 75.9k | 135.0k | 65.8k | 201.0k (1.2%) | 176 | 361 | 49.7% |
| d1v4 | 12/12 | 75.9k | 135.4k | 66.6k | 202.1k (0.9%) | 173 | 357 | 50.1% |
| d2v3 | 12/12 | 75.9k | 133.5k | 65.7k | 199.5k (1.0%) | 170 | 352 | 49.3% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d1v4 vs base | instructions:u / req | exploratory | +0.03% [-0.02, +0.09] | 0.05 | - | 0.08 | 12 | 4/12 | 0.388 | 0.233 | - | exploratory |
| d1v4 vs base | cycles:u / req | exploratory | +0.48% [-0.88, +1.86] | 1.36 | - | 2.14 | 12 | 5/12 | 0.774 | 0.519 | - | exploratory |
| d1v4 vs base | cycles:k / req | exploratory | +1.00% [-0.06, +2.07] | 1.05 | - | 1.66 | 12 | 2/12 | 0.039 | 0.064 | - | exploratory |
| d1v4 vs base | cycles (u+k) / req | primary | +0.65% [-0.47, +1.79] | 1.12 | - | 1.77 | 12 | 4/12 | 0.388 | 0.110 | 0.323 | not resolved |
| d1v4 vs base | p50 latency (us) | exploratory | -0.86% [-5.64, +4.17] | 4.94 | - | 7.78 | 12 | 6/12 | 1.000 | 0.677 | - | exploratory |
| d1v4 vs base | p99 latency (us) | exploratory | -2.48% [-6.30, +1.50] | 4.00 | - | 6.29 | 12 | 7/12 | 0.774 | 0.339 | - | exploratory |
| d2v3 vs base | instructions:u / req | exploratory | +0.07% [+0.02, +0.11] | 0.05 | - | 0.08 | 12 | 2/12 | 0.039 | 0.012 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:u / req | exploratory | -1.24% [-2.32, -0.14] | 1.10 | - | 1.74 | 12 | 9/12 | 0.146 | 0.042 | - | exploratory: interval excludes 0 |
| d2v3 vs base | cycles:k / req | exploratory | -0.08% [-1.39, +1.25] | 1.32 | - | 2.08 | 12 | 6/12 | 1.000 | 0.733 | - | exploratory |
| d2v3 vs base | cycles (u+k) / req | primary | -0.86% [-1.93, +0.22] | 1.08 | - | 1.71 | 12 | 8/12 | 0.388 | 0.129 | 0.323 | not resolved |
| d2v3 vs base | p50 latency (us) | exploratory | -2.58% [-6.69, +1.72] | 4.31 | - | 6.79 | 12 | 7/12 | 0.774 | 0.204 | - | exploratory |
| d2v3 vs base | p99 latency (us) | exploratory | -2.25% [-7.09, +2.83] | 5.07 | - | 7.98 | 12 | 8/12 | 0.388 | 0.380 | - | exploratory |

## Validity

72 legs run, 72 valid; 0 legs superseded by a re-run of their round.

