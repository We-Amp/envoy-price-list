# smf-buffer-limit

- Harness: 0.1.0 ed217ec477fa
- Window: 2026-11-14T12:35:54Z to 2026-11-14T13:06:49Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1679467,1917602,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total half-width 0.83% (s2k buffer-4k vs buffer-default) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| buffer-default | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| buffer-4k | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## m (`/m`, proxied, 5440 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| buffer-default | 12/12 | 166.5k | 344.8k | 193.0k | 537.8k (0.5%) | 406 | 641 | 33.2% |
| buffer-4k | 12/12 | 182.0k | 384.3k | 264.4k | 648.2k (0.6%) | 483 | 1124 | 39.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| buffer-4k vs buffer-default | instructions:u / req | exploratory | +9.32% [+9.21, +9.42] | 0.10 | - | 0.15 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| buffer-4k vs buffer-default | cycles:u / req | exploratory | +11.17% [+10.70, +11.64] | 0.42 | - | 0.66 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| buffer-4k vs buffer-default | cycles:k / req | exploratory | +37.42% [+36.45, +38.41] | 0.71 | - | 1.12 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| buffer-4k vs buffer-default | cycles (u+k) / req | primary | +20.58% [+20.02, +21.13] | 0.46 | - | 0.72 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| buffer-4k vs buffer-default | p50 latency (us) | exploratory | +19.60% [+16.81, +22.45] | 2.36 | - | 3.71 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| buffer-4k vs buffer-default | p99 latency (us) | exploratory | +76.22% [+58.13, +96.39] | 10.83 | - | 17.05 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## s2k (`/s2k`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| buffer-default | 12/12 | 164.2k | 346.3k | 181.3k | 527.4k (0.9%) | 397 | 624 | 31.3% |
| buffer-4k | 12/12 | 160.6k | 344.4k | 180.6k | 525.4k (0.8%) | 397 | 619 | 31.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| buffer-4k vs buffer-default | instructions:u / req | exploratory | -2.20% [-2.23, -2.17] | 0.03 | - | 0.05 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| buffer-4k vs buffer-default | cycles:u / req | exploratory | -0.63% [-1.36, +0.10] | 0.74 | - | 1.16 | 12 | 8/12 | 0.388 | 0.110 | - | exploratory |
| buffer-4k vs buffer-default | cycles:k / req | exploratory | -0.24% [-1.36, +0.90] | 1.13 | - | 1.78 | 12 | 6/12 | 1.000 | 0.677 | - | exploratory |
| buffer-4k vs buffer-default | cycles (u+k) / req | primary | -0.50% [-1.32, +0.33] | 0.83 | - | 1.30 | 12 | 7/12 | 0.774 | 0.339 | 0.210 | not resolved |
| buffer-4k vs buffer-default | p50 latency (us) | exploratory | -0.09% [-2.21, +2.08] | 2.15 | - | 3.38 | 12 | 6/12 | 1.000 | 0.622 | - | exploratory |
| buffer-4k vs buffer-default | p99 latency (us) | exploratory | -0.94% [-2.73, +0.88] | 1.82 | - | 2.87 | 12 | 7/12 | 0.774 | 0.569 | - | exploratory |

## Validity

48 legs run, 48 valid; 0 legs superseded by a re-run of their round.

