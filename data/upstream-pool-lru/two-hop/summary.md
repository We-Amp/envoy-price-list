# lru-two-hop

- Harness: 0.1.0 ff019f02ba36
- Window: 2026-11-14T15:39:36Z to 2026-11-14T16:42:17Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 24 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total_all half-width 1.35% (s-lo lru vs mru) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total_all, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| mru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| lru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |

## s-lo (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 24/24 | 163.1k | 345.4k | 159.8k | 504.8k (0.6%) | 689 | 1095 | 29.8% |
| lru | 24/24 | 163.3k | 344.0k | 171.5k | 515.4k (0.7%) | 692 | 1117 | 30.3% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.17% [+0.14, +0.20] | 0.03 | - | 0.08 | 24 | 1/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:u / req | exploratory | -0.43% [-0.84, -0.03] | 0.41 | - | 0.96 | 24 | 19/24 | 0.007 | 0.042 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:k / req | exploratory | +7.46% [+6.93, +8.01] | 0.50 | - | 1.19 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req | exploratory | +2.06% [+1.64, +2.48] | 0.41 | - | 0.97 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, all hops | primary | +3.37% [+1.98, +4.77] | 1.35 | - | 3.19 | 24 | 3/24 | 0.000 | 0.000 | 0.000 | differs |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +3.37% [+1.98, +4.77] | 1.35 | - | 3.19 | 24 | 3/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | instructions:u / req, all hops | exploratory | +0.24% [+0.16, +0.33] | 0.09 | - | 0.21 | 24 | 1/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | +4.80% [+2.04, +7.64] | 2.67 | - | 6.32 | 24 | 3/24 | 0.000 | 0.001 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker's share | exploratory | -61.93% [-65.52, -57.97] | 9.90 | - | 23.43 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -59.81% [-62.64, -56.77] | 7.29 | - | 17.27 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +57.69% [+52.23, +63.35] | 3.52 | - | 8.35 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | p50 latency (us) | exploratory | -5.25% [-10.16, -0.06] | 5.33 | - | 12.61 | 24 | 12/24 | 1.000 | 0.229 | - | exploratory: interval excludes 0 |
| lru vs mru | p99 latency (us) | exploratory | +0.51% [-3.66, +4.87] | 4.25 | - | 10.06 | 24 | 9/24 | 0.307 | 0.790 | - | exploratory |

## s-hi (`/s4`, proxied, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 24/24 | 162.9k | 315.1k | 142.2k | 457.4k (0.7%) | 787 | 1557 | 41.1% |
| lru | 24/24 | 163.1k | 317.5k | 155.3k | 471.7k (0.9%) | 838 | 1782 | 42.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.13% [+0.10, +0.16] | 0.03 | - | 0.07 | 24 | 1/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:u / req | exploratory | +1.00% [+0.40, +1.60] | 0.59 | - | 1.40 | 24 | 8/24 | 0.152 | 0.004 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:k / req | exploratory | +9.32% [+8.56, +10.08] | 0.69 | - | 1.64 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req | exploratory | +3.59% [+2.99, +4.19] | 0.58 | - | 1.38 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, all hops | primary | +1.42% [+0.25, +2.61] | 1.17 | - | 2.76 | 24 | 8/24 | 0.152 | 0.023 | 0.020 | differs |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +1.42% [+0.25, +2.61] | 1.17 | - | 2.76 | 24 | 8/24 | 0.152 | 0.023 | - | exploratory: interval excludes 0 |
| lru vs mru | instructions:u / req, all hops | exploratory | +0.09% [-0.00, +0.18] | 0.09 | - | 0.22 | 24 | 8/24 | 0.152 | 0.079 | - | exploratory |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | -0.65% [-2.85, +1.61] | 2.24 | - | 5.31 | 24 | 13/24 | 0.839 | 0.565 | - | exploratory |
| lru vs mru | second hop: busiest worker's share | exploratory | -48.87% [-52.09, -45.43] | 6.51 | - | 15.43 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -49.27% [-51.47, -46.96] | 4.44 | - | 10.52 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +55.50% [+47.36, +64.08] | 5.37 | - | 12.73 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | p50 latency (us) | exploratory | -2.71% [-15.17, +11.59] | 13.71 | - | 32.47 | 24 | 6/24 | 0.023 | 0.095 | - | exploratory |
| lru vs mru | p99 latency (us) | exploratory | -1.96% [-18.71, +18.25] | 18.74 | - | 44.38 | 24 | 11/24 | 0.839 | 0.527 | - | exploratory |

## Validity

96 legs run, 96 valid; 0 legs superseded by a re-run of their round.

