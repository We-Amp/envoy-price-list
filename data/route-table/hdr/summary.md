# hdr

- Harness: 0.1.0 9a35ff71ca41
- Window: 2026-11-16T03:15:54Z to 2026-11-16T04:48:01Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1505325,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 24 done (minimum 12, blocks of 6, cap 36, adaptive True), order rotate; stop: widest cycles_total half-width 0.96% (fh109-lo s1 vs base) <= target 1.00%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 4 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| base | 8ce942ce56c433e352d2657603d7bf33d4dbb4b4/1.41.0-dev/Clean/RELEASE/BoringSSL | `e59880d7374383c6df4dcaad6c71dd7e` |
| s1 | 60556c39efd4fe8e922e7e98bad84f5d22cb9131/1.41.0-dev/Clean/RELEASE/BoringSSL | `a1da0f89183496870b9f9c1657bbe931` |
| base-A2 | 8ce942ce56c433e352d2657603d7bf33d4dbb4b4/1.41.0-dev/Clean/RELEASE/BoringSSL | `e59880d7374383c6df4dcaad6c71dd7e` |

## fh109-lo (`/fh`, routes, 2000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 24/24 | 166.3k | 250.5k | 117.6k | 369.3k (1.6%) | 304 | 453 | 9.7% |
| s1 | 24/24 | 133.4k | 238.9k | 116.9k | 356.8k (1.3%) | 296 | 440 | 9.4% |
| base-A2 | 24/24 | 166.3k | 249.7k | 116.8k | 367.2k (1.5%) | 303 | 452 | 9.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s1 vs base | instructions:u / req | exploratory | -19.79% [-19.79, -19.79] | 0.00 | - | 0.01 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| s1 vs base | cycles:u / req | exploratory | -4.76% [-5.38, -4.13] | 0.66 | - | 1.55 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| s1 vs base | cycles:k / req | exploratory | -0.68% [-2.58, +1.25] | 1.93 | - | 4.56 | 24 | 13/24 | 0.839 | 0.509 | - | exploratory |
| s1 vs base | cycles (u+k) / req | primary | -3.44% [-4.36, -2.51] | 0.96 | - | 2.27 | 24 | 23/24 | 0.000 | 0.000 | 0.000 | differs |
| s1 vs base | p50 latency (us) | exploratory | -2.12% [-2.73, -1.49] | 0.63 | - | 1.50 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| s1 vs base | p99 latency (us) | exploratory | -2.66% [-3.48, -1.83] | 0.85 | - | 2.00 | 24 | 22/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| base-A2 vs base | instructions:u / req | exploratory | +0.00% [-0.00, +0.00] | 0.00 | - | 0.00 | 24 | 10/24 | 0.541 | 0.966 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | -0.15% [-0.72, +0.42] | 0.57 | - | 1.34 | 24 | 14/24 | 0.541 | 0.406 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | -0.45% [-2.36, +1.49] | 1.94 | - | 4.58 | 24 | 14/24 | 0.541 | 0.603 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | -0.25% [-1.13, +0.64] | 0.89 | - | 2.10 | 24 | 14/24 | 0.541 | 0.603 | 1.000 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | -0.12% [-0.77, +0.54] | 0.65 | - | 1.55 | 24 | 16/24 | 0.152 | 0.522 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | -0.28% [-1.21, +0.66] | 0.94 | - | 2.22 | 24 | 16/24 | 0.152 | 0.439 | - | exploratory |

## fh109-hi (`/fh`, routes, 20000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 24/24 | 165.8k | 177.4k | 71.9k | 249.2k (1.1%) | 278 | 532 | 55.5% |
| s1 | 24/24 | 132.9k | 166.8k | 72.8k | 239.8k (0.9%) | 265 | 506 | 53.4% |
| base-A2 | 24/24 | 165.8k | 176.5k | 71.8k | 248.3k (1.2%) | 279 | 538 | 55.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s1 vs base | instructions:u / req | exploratory | -19.84% [-19.86, -19.83] | 0.02 | - | 0.04 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| s1 vs base | cycles:u / req | exploratory | -6.04% [-6.71, -5.38] | 0.71 | - | 1.67 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| s1 vs base | cycles:k / req | exploratory | +0.88% [+0.11, +1.66] | 0.77 | - | 1.83 | 24 | 9/24 | 0.307 | 0.042 | - | exploratory: interval excludes 0 |
| s1 vs base | cycles (u+k) / req | primary | -4.04% [-4.68, -3.40] | 0.67 | - | 1.58 | 24 | 23/24 | 0.000 | 0.000 | 0.000 | differs |
| s1 vs base | p50 latency (us) | exploratory | -4.54% [-6.10, -2.96] | 1.65 | - | 3.90 | 24 | 21/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| s1 vs base | p99 latency (us) | exploratory | -6.32% [-11.38, -0.97] | 5.56 | - | 13.16 | 24 | 17/24 | 0.064 | 0.004 | - | exploratory: interval excludes 0 |
| base-A2 vs base | instructions:u / req | exploratory | -0.00% [-0.02, +0.02] | 0.02 | - | 0.04 | 24 | 13/24 | 0.839 | 0.922 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | -0.20% [-0.79, +0.39] | 0.59 | - | 1.40 | 24 | 16/24 | 0.152 | 0.303 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | -0.13% [-0.86, +0.62] | 0.74 | - | 1.76 | 24 | 13/24 | 0.839 | 0.790 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | -0.18% [-0.73, +0.38] | 0.56 | - | 1.32 | 24 | 15/24 | 0.307 | 0.290 | 1.000 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | -0.15% [-1.98, +1.71] | 1.85 | - | 4.37 | 24 | 13/24 | 0.839 | 0.944 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | -0.95% [-6.46, +4.88] | 5.72 | - | 13.55 | 24 | 13/24 | 0.839 | 0.790 | - | exploratory |

## Validity

144 legs run, 144 valid; 0 legs superseded by a re-run of their round.

