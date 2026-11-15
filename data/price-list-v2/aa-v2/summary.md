# aa-selftest

- Harness: 0.1.0 8358578961a2
- Window: 2026-11-14T00:11:38Z to 2026-11-14T00:57:53Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2294588,2300000
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 36, adaptive True), order abba; stop: widest cycles_total half-width 1.37% (fh A2 vs A) <= target 3.00%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 3 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| A | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 12/12 | 163.8k | 346.2k | 179.8k | 525.6k (0.9%) | 392 | 622 | 31.2% |
| A2 | 12/12 | 163.9k | 343.3k | 177.6k | 521.6k (0.8%) | 399 | 621 | 30.9% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | +0.01% [-0.04, +0.05] | 0.05 | - | 0.08 | 12 | 4/12 | 0.388 | 0.569 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | -0.64% [-1.44, +0.17] | 0.81 | - | 1.28 | 12 | 8/12 | 0.388 | 0.110 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | -1.15% [-2.26, -0.02] | 1.13 | - | 1.78 | 12 | 8/12 | 0.388 | 0.064 | - | exploratory: interval excludes 0 |
| A2 vs A | cycles (u+k) / req | primary | -0.81% [-1.70, +0.08] | 0.90 | - | 1.41 | 12 | 8/12 | 0.388 | 0.092 | 0.210 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | +1.38% [-0.62, +3.43] | 2.00 | - | 3.14 | 12 | 4/12 | 0.388 | 0.129 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | +0.47% [-0.71, +1.66] | 1.18 | - | 1.85 | 12 | 4/12 | 0.549 | 0.413 | - | exploratory |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 12/12 | 164.8k | 199.0k | 81.6k | 280.7k (1.3%) | 216 | 370 | 25.5% |
| A2 | 12/12 | 164.8k | 197.2k | 81.4k | 279.0k (1.6%) | 215 | 367 | 25.3% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | +0.00% [-0.00, +0.01] | 0.01 | - | 0.01 | 12 | 3/12 | 0.146 | 0.176 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | -0.94% [-2.36, +0.51] | 1.45 | - | 2.28 | 12 | 8/12 | 0.388 | 0.176 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | -0.57% [-1.85, +0.73] | 1.30 | - | 2.04 | 12 | 7/12 | 0.774 | 0.569 | - | exploratory |
| A2 vs A | cycles (u+k) / req | primary | -0.83% [-2.18, +0.53] | 1.37 | - | 2.15 | 12 | 8/12 | 0.388 | 0.151 | 0.413 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | -0.68% [-1.71, +0.35] | 1.04 | - | 1.64 | 12 | 8/12 | 0.388 | 0.233 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | -0.34% [-1.23, +0.55] | 0.89 | - | 1.41 | 12 | 8/12 | 0.388 | 0.380 | - | exploratory |

## m (`/m`, proxied, 5440 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 12/12 | 167.0k | 344.8k | 189.9k | 534.4k (0.5%) | 405 | 648 | 32.9% |
| A2 | 12/12 | 167.0k | 344.8k | 188.8k | 533.3k (0.7%) | 405 | 665 | 32.9% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | +0.01% [-0.02, +0.03] | 0.03 | - | 0.04 | 12 | 5/12 | 0.774 | 0.470 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | -0.13% [-0.53, +0.28] | 0.40 | - | 0.64 | 12 | 6/12 | 1.000 | 0.622 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | -0.11% [-0.70, +0.49] | 0.60 | - | 0.94 | 12 | 6/12 | 1.000 | 0.733 | - | exploratory |
| A2 vs A | cycles (u+k) / req | primary | -0.12% [-0.55, +0.31] | 0.43 | - | 0.68 | 12 | 7/12 | 0.774 | 0.622 | 0.551 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | +0.45% [-1.32, +2.25] | 1.78 | - | 2.80 | 12 | 7/12 | 0.774 | 0.850 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | +1.28% [-3.26, +6.04] | 4.59 | - | 7.22 | 12 | 2/12 | 0.039 | 0.092 | - | exploratory |

## Validity

72 legs run, 72 valid; 0 legs superseded by a re-run of their round.

## A/A self-test: PASS

Rule: no Holm-significant difference and 95% half-width within the limit on every check.

| Shape | metric | effect [95% CI] | hw | limit | pair SD | 80%-power bias | n | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|---|
| s | instructions_u | +0.01% [-0.04, +0.05] | 0.05 | 0.50 | 0.08 | 0.07% | 12 | 1.000 | ok |
| s | cycles_total | -0.81% [-1.70, +0.08] | 0.90 | 3.00 | 1.41 | 1.25% | 12 | 0.419 | ok |
| fh | instructions_u | +0.00% [-0.00, +0.01] | 0.01 | 0.50 | 0.01 | 0.01% | 12 | 1.000 | ok |
| fh | cycles_total | -0.83% [-2.18, +0.53] | 1.37 | 3.00 | 2.15 | 1.91% | 12 | 1.000 | ok |
| m | instructions_u | +0.01% [-0.02, +0.03] | 0.03 | 0.50 | 0.04 | 0.04% | 12 | 1.000 | ok |
| m | cycles_total | -0.12% [-0.55, +0.31] | 0.43 | 3.00 | 0.68 | 0.60% | 12 | 1.000 | ok |

