# aa-label-swap

- Harness: 0.1.0 7b6b5c3d7226
- Window: 2026-11-14T21:44:42Z to 2026-11-14T22:46:20Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2015489,2296833,2297023,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 24 done (minimum 24, blocks of 6, cap 24, adaptive False), order abba; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| A | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A2 | 24/24 | 163.8k | 344.6k | 181.3k | 526.0k (0.7%) | 402 | 627 | 31.2% |
| A | 24/24 | 163.9k | 345.3k | 181.3k | 527.2k (0.7%) | 401 | 627 | 31.3% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | -0.01% [-0.03, +0.02] | 0.03 | - | 0.06 | 24 | 11/24 | 0.839 | 0.855 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | -0.23% [-0.64, +0.19] | 0.41 | - | 0.98 | 24 | 16/24 | 0.152 | 0.317 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | -0.10% [-0.72, +0.52] | 0.62 | - | 1.47 | 24 | 11/24 | 0.839 | 0.643 | - | exploratory |
| A2 vs A | cycles (u+k) / req | primary | -0.18% [-0.64, +0.27] | 0.46 | - | 1.09 | 24 | 15/24 | 0.307 | 0.584 | 0.829 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | +0.45% [-0.74, +1.65] | 1.19 | - | 2.82 | 24 | 13/24 | 0.839 | 0.546 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | +0.41% [-0.76, +1.59] | 1.17 | - | 2.78 | 24 | 13/24 | 0.839 | 0.473 | - | exploratory |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A2 | 24/24 | 164.7k | 198.0k | 82.6k | 280.5k (1.2%) | 216 | 369 | 25.5% |
| A | 24/24 | 164.7k | 197.8k | 83.1k | 280.9k (1.5%) | 217 | 370 | 25.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | +0.00% [-0.00, +0.01] | 0.00 | - | 0.01 | 24 | 12/24 | 1.000 | 0.747 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | -0.03% [-0.83, +0.77] | 0.80 | - | 1.90 | 24 | 12/24 | 1.000 | 0.922 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | -0.18% [-0.93, +0.58] | 0.76 | - | 1.79 | 24 | 12/24 | 1.000 | 0.705 | - | exploratory |
| A2 vs A | cycles (u+k) / req | primary | -0.08% [-0.84, +0.69] | 0.77 | - | 1.82 | 24 | 12/24 | 1.000 | 0.944 | 0.841 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | -0.48% [-1.10, +0.15] | 0.63 | - | 1.50 | 24 | 14/24 | 0.541 | 0.160 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | -0.13% [-0.58, +0.33] | 0.46 | - | 1.08 | 24 | 15/24 | 0.307 | 0.623 | - | exploratory |

## Validity

96 legs run, 96 valid; 0 legs superseded by a re-run of their round.

## A/A self-test: PASS

Rule: no Holm-significant difference and 95% half-width within the limit on every check.

| Shape | metric | effect [95% CI] | hw | limit | pair SD | 80%-power bias | n | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|---|
| s | instructions_u | -0.01% [-0.03, +0.02] | 0.03 | 0.50 | 0.06 | 0.04% | 24 | 1.000 | ok |
| s | cycles_total | -0.18% [-0.64, +0.27] | 0.46 | 1.00 | 1.09 | 0.65% | 24 | 1.000 | ok |
| fh | instructions_u | +0.00% [-0.00, +0.01] | 0.00 | 0.50 | 0.01 | 0.01% | 24 | 1.000 | ok |
| fh | cycles_total | -0.08% [-0.84, +0.69] | 0.77 | 1.00 | 1.82 | 1.09% | 24 | 1.000 | ok |

