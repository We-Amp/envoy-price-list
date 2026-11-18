# features-lc-sfh

- Harness: 0.x 4fc7986fe46f week5-s2
- Window: 2026-11-18T06:56:10Z to 2026-11-18T07:26:57Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2295453,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 12, cap 12, adaptive False), order abba; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| base | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| base-A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s-9600 (`/s`, proxied, 9600 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 12/12 | 163.4k | 311.3k | 159.9k | 472.1k (0.6%) | 381 | 739 | 50.8% |
| base-A2 | 12/12 | 163.4k | 311.9k | 161.1k | 472.7k (1.1%) | 383 | 811 | 51.0% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base-A2 vs base | instructions:u / req | exploratory | +0.01% [-0.04, +0.05] | 0.05 | - | 0.07 | 12 | 6/12 | 1.000 | 0.910 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | +0.33% [-0.15, +0.81] | 0.48 | - | 0.76 | 12 | 5/12 | 0.774 | 0.204 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | +0.86% [-0.33, +2.06] | 1.18 | - | 1.86 | 12 | 5/12 | 0.774 | 0.266 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | +0.51% [-0.14, +1.16] | 0.64 | - | 1.01 | 12 | 5/12 | 0.774 | 0.129 | 0.221 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | +0.18% [-1.73, +2.13] | 1.93 | - | 3.03 | 12 | 7/12 | 0.774 | 0.970 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | +8.83% [-16.62, +42.05] | 26.64 | - | 41.93 | 12 | 3/12 | 0.146 | 0.380 | - | exploratory |

## fh-13600 (`/fh`, direct_headers, 13600 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| base | 12/12 | 164.6k | 190.1k | 75.0k | 264.9k (0.8%) | 232 | 417 | 40.7% |
| base-A2 | 12/12 | 164.6k | 189.8k | 74.9k | 265.2k (0.6%) | 230 | 414 | 40.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base-A2 vs base | instructions:u / req | exploratory | +0.01% [-0.01, +0.02] | 0.01 | - | 0.02 | 12 | 4/12 | 0.388 | 0.301 | - | exploratory |
| base-A2 vs base | cycles:u / req | exploratory | -0.12% [-0.82, +0.57] | 0.70 | - | 1.10 | 12 | 8/12 | 0.388 | 0.733 | - | exploratory |
| base-A2 vs base | cycles:k / req | exploratory | +0.08% [-0.87, +1.04] | 0.95 | - | 1.50 | 12 | 7/12 | 0.774 | 1.000 | - | exploratory |
| base-A2 vs base | cycles (u+k) / req | primary | -0.06% [-0.69, +0.56] | 0.63 | - | 0.99 | 12 | 7/12 | 0.774 | 0.733 | 0.824 | not resolved |
| base-A2 vs base | p50 latency (us) | exploratory | -0.82% [-2.84, +1.25] | 2.06 | - | 3.24 | 12 | 7/12 | 0.774 | 0.622 | - | exploratory |
| base-A2 vs base | p99 latency (us) | exploratory | -1.50% [-5.34, +2.49] | 3.97 | - | 6.25 | 12 | 7/12 | 0.774 | 0.470 | - | exploratory |

## Validity

48 legs run, 48 valid; 0 legs superseded by a re-run of their round.

