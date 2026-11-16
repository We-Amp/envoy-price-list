# wk4-jwt-authn

- Harness: 0.1.0 57bbabf18abe
- Window: 2026-11-15T22:45:40Z to 2026-11-15T23:32:06Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order rotate; stop: widest cycles_total half-width 1.41% (fh jwt vs jwt-off) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 4 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| jwt-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| jwt | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| jwt-cache | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| jwt-off | 12/12 | 194.3k | 355.9k | 182.8k | 538.4k (0.6%) | 404 | 634 | 31.9% |
| jwt | 12/12 | 478.2k | 532.8k | 178.3k | 712.1k (0.7%) | 553 | 1493 | 41.2% |
| jwt-cache | 12/12 | 203.5k | 379.7k | 182.2k | 562.0k (0.4%) | 425 | 691 | 33.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jwt vs jwt-off | instructions:u / req | exploratory | +146.16% [+146.08, +146.24] | 0.03 | 0.04 | 0.05 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt vs jwt-off | cycles:u / req | exploratory | +49.86% [+49.36, +50.37] | 0.34 | 0.41 | 0.53 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt vs jwt-off | cycles:k / req | exploratory | -2.58% [-3.65, -1.50] | 1.10 | 0.82 | 1.74 | 12 | 11/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| jwt vs jwt-off | cycles (u+k) / req | primary | +32.07% [+31.51, +32.63] | 0.42 | 0.52 | 0.67 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| jwt vs jwt-off | p50 latency (us) | exploratory | +37.81% [+34.02, +41.72] | 2.79 | 2.04 | 4.40 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt vs jwt-off | p99 latency (us) | exploratory | +150.85% [+107.37, +203.46] | 19.04 | 1.61 | 29.97 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt-cache vs jwt-off | instructions:u / req | exploratory | +4.76% [+4.73, +4.79] | 0.03 | 0.04 | 0.05 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt-cache vs jwt-off | cycles:u / req | exploratory | +6.69% [+6.32, +7.05] | 0.34 | 0.41 | 0.54 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt-cache vs jwt-off | cycles:k / req | exploratory | -0.39% [-1.03, +0.26] | 0.65 | 0.82 | 1.02 | 12 | 8/12 | 0.388 | 0.204 | - | exploratory |
| jwt-cache vs jwt-off | cycles (u+k) / req | primary | +4.29% [+3.91, +4.67] | 0.37 | 0.52 | 0.58 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| jwt-cache vs jwt-off | p50 latency (us) | exploratory | +4.23% [+2.36, +6.14] | 1.81 | 2.04 | 2.85 | 12 | 1/12 | 0.006 | 0.003 | - | exploratory: interval excludes 0 |
| jwt-cache vs jwt-off | p99 latency (us) | exploratory | +9.04% [+3.75, +14.59] | 4.97 | 1.61 | 7.83 | 12 | 1/12 | 0.006 | 0.002 | - | exploratory: interval excludes 0 |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| jwt-off | 12/12 | 190.7k | 206.4k | 83.7k | 290.2k (1.9%) | 219 | 376 | 26.2% |
| jwt | 12/12 | 474.7k | 382.6k | 81.7k | 464.9k (1.1%) | 378 | 956 | 41.1% |
| jwt-cache | 12/12 | 200.0k | 231.5k | 84.6k | 315.2k (1.4%) | 234 | 402 | 28.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jwt vs jwt-off | instructions:u / req | exploratory | +148.91% [+148.89, +148.93] | 0.01 | 0.01 | 0.02 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt vs jwt-off | cycles:u / req | exploratory | +85.78% [+83.23, +88.37] | 1.38 | 1.06 | 2.18 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt vs jwt-off | cycles:k / req | exploratory | -2.40% [-4.16, -0.61] | 1.82 | 1.48 | 2.86 | 12 | 10/12 | 0.039 | 0.012 | - | exploratory: interval excludes 0 |
| jwt vs jwt-off | cycles (u+k) / req | primary | +60.30% [+58.06, +62.57] | 1.41 | 1.16 | 2.22 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| jwt vs jwt-off | p50 latency (us) | exploratory | +75.45% [+69.73, +81.37] | 3.32 | 0.90 | 5.22 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt vs jwt-off | p99 latency (us) | exploratory | +151.05% [+123.24, +182.32] | 11.74 | 0.86 | 18.48 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt-cache vs jwt-off | instructions:u / req | exploratory | +4.86% [+4.86, +4.87] | 0.01 | 0.01 | 0.01 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt-cache vs jwt-off | cycles:u / req | exploratory | +12.51% [+11.02, +14.03] | 1.34 | 1.06 | 2.10 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt-cache vs jwt-off | cycles:k / req | exploratory | +1.09% [-0.28, +2.47] | 1.36 | 1.48 | 2.13 | 12 | 1/12 | 0.006 | 0.027 | - | exploratory |
| jwt-cache vs jwt-off | cycles (u+k) / req | primary | +9.21% [+7.79, +10.65] | 1.31 | 1.16 | 2.06 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| jwt-cache vs jwt-off | p50 latency (us) | exploratory | +6.85% [+5.74, +7.97] | 1.05 | 0.90 | 1.65 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| jwt-cache vs jwt-off | p99 latency (us) | exploratory | +7.11% [+6.09, +8.14] | 0.95 | 0.86 | 1.50 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

72 legs run, 72 valid; 0 legs superseded by a re-run of their round.

