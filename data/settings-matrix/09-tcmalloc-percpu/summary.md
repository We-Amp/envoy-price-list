# sm-tcmalloc-percpu

- Harness: 0.1.0 7e3abbe874af
- Window: 2026-11-14T10:18:19Z to 2026-11-14T10:49:11Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total half-width 1.24% (fh rseq-off vs tcmalloc-default) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| tcmalloc-default | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| rseq-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| tcmalloc-default | 12/12 | 163.9k | 345.9k | 182.1k | 528.0k (0.8%) | 402 | 629 | 31.3% |
| rseq-off | 12/12 | 147.2k | 339.6k | 182.9k | 522.3k (0.8%) | 391 | 620 | 31.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rseq-off vs tcmalloc-default | instructions:u / req | exploratory | -10.21% [-10.25, -10.16] | 0.05 | 0.02 | 0.07 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| rseq-off vs tcmalloc-default | cycles:u / req | exploratory | -1.71% [-2.38, -1.04] | 0.68 | 0.58 | 1.07 | 12 | 11/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| rseq-off vs tcmalloc-default | cycles:k / req | exploratory | +0.69% [-0.47, +1.85] | 1.15 | 0.63 | 1.81 | 12 | 5/12 | 0.774 | 0.233 | - | exploratory |
| rseq-off vs tcmalloc-default | cycles (u+k) / req | primary | -0.88% [-1.69, -0.07] | 0.82 | 0.56 | 1.28 | 12 | 10/12 | 0.039 | 0.016 | 0.036 | differs, inside the A/A interval |
| rseq-off vs tcmalloc-default | p50 latency (us) | exploratory | -2.65% [-4.11, -1.16] | 1.52 | 1.70 | 2.38 | 12 | 11/12 | 0.006 | 0.009 | - | exploratory: interval excludes 0 |
| rseq-off vs tcmalloc-default | p99 latency (us) | exploratory | -2.07% [-4.41, +0.33] | 2.42 | 2.16 | 3.81 | 12 | 8/12 | 0.388 | 0.092 | - | exploratory |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| tcmalloc-default | 12/12 | 164.8k | 196.6k | 82.3k | 279.2k (1.7%) | 214 | 368 | 25.3% |
| rseq-off | 12/12 | 133.0k | 198.7k | 83.3k | 281.7k (1.4%) | 217 | 372 | 25.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rseq-off vs tcmalloc-default | instructions:u / req | exploratory | -19.23% [-19.32, -19.15] | 0.10 | 0.01 | 0.16 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| rseq-off vs tcmalloc-default | cycles:u / req | exploratory | +1.62% [+0.17, +3.09] | 1.44 | 1.03 | 2.26 | 12 | 4/12 | 0.388 | 0.052 | - | exploratory: interval excludes 0 |
| rseq-off vs tcmalloc-default | cycles:k / req | exploratory | +1.48% [+0.63, +2.35] | 0.85 | 0.90 | 1.33 | 12 | 1/12 | 0.006 | 0.003 | - | exploratory: interval excludes 0 |
| rseq-off vs tcmalloc-default | cycles (u+k) / req | primary | +1.58% [+0.32, +2.85] | 1.24 | 0.94 | 1.96 | 12 | 4/12 | 0.388 | 0.034 | 0.036 | differs |
| rseq-off vs tcmalloc-default | p50 latency (us) | exploratory | +1.13% [+0.04, +2.24] | 1.09 | 0.87 | 1.72 | 12 | 3/12 | 0.146 | 0.073 | - | exploratory: interval excludes 0 |
| rseq-off vs tcmalloc-default | p99 latency (us) | exploratory | +0.94% [+0.12, +1.76] | 0.81 | 0.64 | 1.28 | 12 | 3/12 | 0.146 | 0.027 | - | exploratory: interval excludes 0 |

## Validity

48 legs run, 48 valid; 0 legs superseded by a re-run of their round.

