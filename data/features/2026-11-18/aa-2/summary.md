# features-aa-2

- Harness: 0.x 4fc7986fe46f week5-s2
- Window: 2026-11-18T01:01:20Z to 2026-11-18T02:18:20Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 20 done (minimum 16, blocks of 4, cap 32, adaptive True), order abba; stop: widest cycles_total half-width against its target 0.92% (fh base-A2 vs base) <= target 1.00%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 3 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| base | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| base-A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 20/20 | 163.9k | 344.8k | 181.1k | 526.3k (0.8%) | 401 | 630 | 31.3% |
| base-A2 | 20/20 | 163.9k | 344.8k | 180.7k | 525.4k (0.8%) | 399 | 629 | 31.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base-A2 vs base | instructions:u / req | exploratory | -0.01% [-0.03, +0.01] | 0.02 | - | 0.04 | 20 | 11/20 | 0.824 | 0.261 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | +0.02% [-0.45, +0.49] | 0.47 | - | 1.01 | 20 | 10/20 | 1.000 | 0.956 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | -0.13% [-0.90, +0.65] | 0.78 | - | 1.66 | 20 | 11/20 | 0.824 | 0.812 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | -0.03% [-0.58, +0.51] | 0.54 | - | 1.16 | 20 | 10/20 | 1.000 | 0.869 | 1.000 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | -0.78% [-1.98, +0.44] | 1.22 | - | 2.60 | 20 | 12/20 | 0.503 | 0.154 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | -0.67% [-2.07, +0.76] | 1.43 | - | 3.05 | 20 | 13/20 | 0.263 | 0.349 | - | exploratory |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 20/20 | 164.8k | 199.0k | 82.8k | 282.2k (1.7%) | 215 | 370 | 25.5% |
| base-A2 | 20/20 | 164.8k | 197.8k | 83.0k | 280.7k (1.8%) | 216 | 369 | 25.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base-A2 vs base | instructions:u / req | exploratory | +0.00% [-0.00, +0.01] | 0.00 | - | 0.01 | 20 | 10/20 | 1.000 | 0.927 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | +0.04% [-0.90, +0.99] | 0.94 | - | 2.01 | 20 | 9/20 | 0.824 | 0.985 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | +0.58% [-0.40, +1.57] | 0.98 | - | 2.09 | 20 | 7/20 | 0.263 | 0.165 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | +0.20% [-0.71, +1.12] | 0.92 | - | 1.96 | 20 | 9/20 | 0.824 | 0.898 | 1.000 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | +0.01% [-0.54, +0.57] | 0.55 | - | 1.18 | 20 | 9/20 | 0.824 | 0.877 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | -0.37% [-0.96, +0.24] | 0.60 | - | 1.29 | 20 | 12/20 | 0.503 | 0.294 | - | exploratory |

## j16 (`/j16`, proxied, 4000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 20/20 | 171.9k | 368.7k | 201.4k | 569.9k (1.0%) | 423 | 636 | 26.2% |
| base-A2 | 20/20 | 171.9k | 366.1k | 201.5k | 567.7k (1.3%) | 420 | 632 | 26.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base-A2 vs base | instructions:u / req | exploratory | -0.00% [-0.03, +0.02] | 0.03 | - | 0.05 | 20 | 12/20 | 0.503 | 0.812 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | -0.32% [-1.13, +0.49] | 0.81 | - | 1.74 | 20 | 13/20 | 0.263 | 0.330 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | +0.20% [-0.60, +1.01] | 0.80 | - | 1.72 | 20 | 11/20 | 0.824 | 0.812 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | -0.14% [-0.91, +0.65] | 0.78 | - | 1.67 | 20 | 13/20 | 0.263 | 0.452 | 1.000 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | -1.40% [-3.52, +0.76] | 2.17 | - | 4.64 | 20 | 14/20 | 0.064 | 0.225 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | -0.57% [-2.36, +1.26] | 1.82 | - | 3.89 | 20 | 12/20 | 0.503 | 0.475 | - | exploratory |

## Validity

120 legs run, 120 valid; 0 legs superseded by a re-run of their round.

