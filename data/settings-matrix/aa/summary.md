# sm-aa

- Harness: 0.1.0 80a47b3f1aa1 dirty
- Window: 2026-11-14T05:44:48Z to 2026-11-14T06:54:07Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2295494,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 18 done (minimum 12, blocks of 6, cap 36, adaptive True), order abba; stop: widest cycles_total half-width 0.94% (fh A2 vs A) <= target 1.00%
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
| A | 18/18 | 163.9k | 343.5k | 181.7k | 525.5k (0.7%) | 398 | 627 | 31.2% |
| A2 | 18/18 | 163.9k | 346.1k | 183.2k | 530.0k (0.7%) | 398 | 629 | 31.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | +0.02% [+0.00, +0.05] | 0.02 | - | 0.05 | 18 | 6/18 | 0.238 | 0.054 | - | exploratory: interval excludes 0 |
| A2 vs A | cycles:u / req | exploratory | +0.49% [-0.09, +1.08] | 0.58 | - | 1.17 | 18 | 7/18 | 0.481 | 0.142 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | +0.81% [+0.18, +1.45] | 0.63 | - | 1.26 | 18 | 4/18 | 0.031 | 0.024 | - | exploratory: interval excludes 0 |
| A2 vs A | cycles (u+k) / req | primary | +0.60% [+0.05, +1.16] | 0.56 | - | 1.12 | 18 | 5/18 | 0.096 | 0.038 | 0.107 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | +0.44% [-1.25, +2.16] | 1.70 | - | 3.41 | 18 | 9/18 | 1.000 | 0.799 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | +0.73% [-1.42, +2.93] | 2.16 | - | 4.34 | 18 | 7/18 | 0.481 | 0.369 | - | exploratory |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 18/18 | 164.8k | 198.8k | 82.9k | 281.7k (1.6%) | 217 | 371 | 25.5% |
| A2 | 18/18 | 164.8k | 198.2k | 82.7k | 281.3k (1.4%) | 217 | 371 | 25.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | +0.00% [-0.00, +0.01] | 0.01 | - | 0.01 | 18 | 11/18 | 0.481 | 0.966 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | -0.05% [-1.08, +0.98] | 1.03 | - | 2.08 | 18 | 8/18 | 0.815 | 1.000 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | +0.07% [-0.82, +0.98] | 0.90 | - | 1.81 | 18 | 10/18 | 0.815 | 0.734 | - | exploratory |
| A2 vs A | cycles (u+k) / req | primary | -0.02% [-0.95, +0.93] | 0.94 | - | 1.90 | 18 | 8/18 | 0.815 | 0.966 | 1.000 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | -0.01% [-0.87, +0.86] | 0.87 | - | 1.74 | 18 | 8/18 | 0.815 | 1.000 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | -0.03% [-0.66, +0.61] | 0.64 | - | 1.28 | 18 | 7/18 | 0.481 | 0.799 | - | exploratory |

## m (`/m`, proxied, 5440 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 18/18 | 167.1k | 345.2k | 191.9k | 537.5k (0.8%) | 404 | 646 | 33.1% |
| A2 | 18/18 | 167.0k | 344.7k | 191.9k | 536.2k (0.7%) | 406 | 657 | 33.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | -0.01% [-0.04, +0.02] | 0.03 | - | 0.06 | 18 | 10/18 | 0.815 | 0.551 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | +0.13% [-0.32, +0.58] | 0.45 | - | 0.90 | 18 | 9/18 | 1.000 | 0.523 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | +0.25% [-0.54, +1.05] | 0.79 | - | 1.60 | 18 | 9/18 | 1.000 | 0.551 | - | exploratory |
| A2 vs A | cycles (u+k) / req | primary | +0.17% [-0.37, +0.72] | 0.54 | - | 1.09 | 18 | 9/18 | 1.000 | 0.580 | 1.000 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | +0.70% [-0.98, +2.40] | 1.68 | - | 3.37 | 18 | 9/18 | 1.000 | 0.832 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | +3.01% [+0.51, +5.58] | 2.46 | - | 4.94 | 18 | 6/18 | 0.238 | 0.043 | - | exploratory: interval excludes 0 |

## Validity

108 legs run, 108 valid; 0 legs superseded by a re-run of their round.

## A/A self-test: PASS

Rule: no Holm-significant difference and 95% half-width within the limit on every check.

| Shape | metric | effect [95% CI] | hw | limit | pair SD | 80%-power bias | n | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|---|
| s | instructions_u | +0.02% [+0.00, +0.05] | 0.02 | 0.50 | 0.05 | 0.03% | 18 | 0.225 | ok |
| s | cycles_total | +0.60% [+0.05, +1.16] | 0.56 | 1.00 | 1.12 | 0.78% | 18 | 0.213 | ok |
| fh | instructions_u | +0.00% [-0.00, +0.01] | 0.01 | 0.50 | 0.01 | 0.01% | 18 | 1.000 | ok |
| fh | cycles_total | -0.02% [-0.95, +0.93] | 0.94 | 1.00 | 1.90 | 1.33% | 18 | 1.000 | ok |
| m | instructions_u | -0.01% [-0.04, +0.02] | 0.03 | 0.50 | 0.06 | 0.04% | 18 | 1.000 | ok |
| m | cycles_total | +0.17% [-0.37, +0.72] | 0.54 | 1.00 | 1.09 | 0.76% | 18 | 1.000 | ok |

