# sm-retries

- Harness: 0.1.0 7e3abbe874af
- Window: 2026-11-14T09:47:17Z to 2026-11-14T10:02:47Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total half-width 0.64% (s retry-policy vs no-retry-policy) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 1 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| no-retry-policy | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| retry-policy | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| no-retry-policy | 12/12 | 163.9k | 345.6k | 182.2k | 527.5k (0.7%) | 397 | 629 | 31.3% |
| retry-policy | 12/12 | 165.9k | 352.6k | 182.3k | 535.8k (0.8%) | 402 | 631 | 31.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| retry-policy vs no-retry-policy | instructions:u / req | exploratory | +1.21% [+1.17, +1.24] | 0.03 | 0.02 | 0.05 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| retry-policy vs no-retry-policy | cycles:u / req | exploratory | +2.05% [+1.53, +2.57] | 0.51 | 0.58 | 0.81 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| retry-policy vs no-retry-policy | cycles:k / req | exploratory | +0.47% [-0.56, +1.51] | 1.03 | 0.63 | 1.62 | 12 | 6/12 | 1.000 | 0.424 | - | exploratory |
| retry-policy vs no-retry-policy | cycles (u+k) / req | primary | +1.50% [+0.85, +2.16] | 0.64 | 0.56 | 1.01 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| retry-policy vs no-retry-policy | p50 latency (us) | exploratory | +1.75% [+0.66, +2.85] | 1.08 | 1.70 | 1.70 | 12 | 2/12 | 0.039 | 0.007 | - | exploratory: interval excludes 0, inside the A/A interval |
| retry-policy vs no-retry-policy | p99 latency (us) | exploratory | +0.71% [-0.65, +2.10] | 1.37 | 2.16 | 2.15 | 12 | 6/12 | 1.000 | 0.380 | - | exploratory |

## Validity

24 legs run, 24 valid; 0 legs superseded by a re-run of their round.

