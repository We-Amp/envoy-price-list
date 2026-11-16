# wk4-local-ratelimit

- Harness: 0.1.0 57bbabf18abe
- Window: 2026-11-15T23:32:06Z to 2026-11-16T00:02:58Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total half-width 0.94% (fh ratelimit-on vs ratelimit-off) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| ratelimit-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| ratelimit-on | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| ratelimit-off | 12/12 | 163.9k | 344.5k | 180.9k | 525.5k (0.9%) | 398 | 629 | 31.2% |
| ratelimit-on | 12/12 | 167.6k | 354.4k | 181.2k | 535.2k (0.6%) | 406 | 649 | 31.8% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ratelimit-on vs ratelimit-off | instructions:u / req | exploratory | +2.30% [+2.28, +2.32] | 0.02 | 0.04 | 0.03 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ratelimit-on vs ratelimit-off | cycles:u / req | exploratory | +2.85% [+2.21, +3.49] | 0.62 | 0.41 | 0.98 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ratelimit-on vs ratelimit-off | cycles:k / req | exploratory | +0.17% [-0.70, +1.06] | 0.88 | 0.82 | 1.38 | 12 | 5/12 | 0.774 | 0.677 | - | exploratory |
| ratelimit-on vs ratelimit-off | cycles (u+k) / req | primary | +1.93% [+1.25, +2.62] | 0.67 | 0.52 | 1.05 | 12 | 1/12 | 0.006 | 0.001 | 0.000 | differs |
| ratelimit-on vs ratelimit-off | p50 latency (us) | exploratory | +0.57% [-1.47, +2.66] | 2.05 | 2.04 | 3.23 | 12 | 5/12 | 0.774 | 0.470 | - | exploratory |
| ratelimit-on vs ratelimit-off | p99 latency (us) | exploratory | +2.71% [+0.27, +5.21] | 2.40 | 1.61 | 3.78 | 12 | 4/12 | 0.388 | 0.064 | - | exploratory: interval excludes 0 |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| ratelimit-off | 12/12 | 164.7k | 198.0k | 82.7k | 280.9k (1.0%) | 216 | 368 | 25.5% |
| ratelimit-on | 12/12 | 168.3k | 209.1k | 82.8k | 291.5k (1.3%) | 221 | 384 | 26.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ratelimit-on vs ratelimit-off | instructions:u / req | exploratory | +2.18% [+2.18, +2.19] | 0.00 | 0.01 | 0.01 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ratelimit-on vs ratelimit-off | cycles:u / req | exploratory | +5.70% [+4.67, +6.74] | 0.98 | 1.06 | 1.54 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ratelimit-on vs ratelimit-off | cycles:k / req | exploratory | -0.15% [-1.11, +0.82] | 0.96 | 1.48 | 1.52 | 12 | 6/12 | 1.000 | 1.000 | - | exploratory |
| ratelimit-on vs ratelimit-off | cycles (u+k) / req | primary | +3.97% [+3.00, +4.95] | 0.94 | 1.16 | 1.48 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| ratelimit-on vs ratelimit-off | p50 latency (us) | exploratory | +2.93% [+1.96, +3.91] | 0.94 | 0.90 | 1.49 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ratelimit-on vs ratelimit-off | p99 latency (us) | exploratory | +4.22% [+3.05, +5.40] | 1.12 | 0.86 | 1.77 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

48 legs run, 48 valid; 0 legs superseded by a re-run of their round.

