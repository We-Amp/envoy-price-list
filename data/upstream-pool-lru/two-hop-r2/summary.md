# lru-two-hop

- Harness: 0.1.0 cad81791f709
- Window: 2026-11-14T17:53:56Z to 2026-11-14T19:01:39Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 24 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total_all half-width 1.40% (s-lo lru vs mru) <= target 1.50%
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
| mru | 24/24 | 163.1k | 346.3k | 159.5k | 505.4k (0.5%) | 729 | 1158 | 29.8% |
| lru | 24/24 | 163.3k | 344.8k | 171.5k | 516.3k (0.6%) | 690 | 1106 | 30.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.15% [+0.13, +0.17] | 0.02 | - | 0.04 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:u / req | exploratory | -0.52% [-0.93, -0.10] | 0.42 | - | 0.99 | 24 | 16/24 | 0.152 | 0.039 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:k / req | exploratory | +7.58% [+7.14, +8.02] | 0.41 | - | 0.97 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req | exploratory | +2.03% [+1.63, +2.44] | 0.39 | - | 0.93 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, all hops | primary | +3.59% [+2.15, +5.04] | 1.40 | - | 3.31 | 24 | 5/24 | 0.007 | 0.000 | 0.000 | differs |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +3.59% [+2.15, +5.04] | 1.40 | - | 3.31 | 24 | 5/24 | 0.007 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | instructions:u / req, all hops | exploratory | +0.26% [+0.18, +0.35] | 0.09 | - | 0.20 | 24 | 1/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | +5.31% [+2.38, +8.33] | 2.82 | - | 6.69 | 24 | 6/24 | 0.023 | 0.003 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker's share | exploratory | -63.21% [-67.26, -58.65] | 11.67 | - | 27.63 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -60.91% [-64.18, -57.34] | 8.73 | - | 20.68 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +53.92% [+49.94, +58.00] | 2.62 | - | 6.20 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | p50 latency (us) | exploratory | -7.63% [-12.30, -2.71] | 5.19 | - | 12.30 | 24 | 15/24 | 0.307 | 0.023 | - | exploratory: interval excludes 0 |
| lru vs mru | p99 latency (us) | exploratory | -1.53% [-5.64, +2.75] | 4.26 | - | 10.09 | 24 | 15/24 | 0.307 | 0.386 | - | exploratory |

## s-hi (`/s4`, proxied, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 24/24 | 162.9k | 313.8k | 142.3k | 457.4k (0.9%) | 795 | 1662 | 41.1% |
| lru | 24/24 | 163.1k | 318.2k | 155.1k | 473.8k (0.8%) | 825 | 1698 | 42.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.10% [+0.07, +0.13] | 0.03 | - | 0.07 | 24 | 1/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:u / req | exploratory | +1.33% [+0.82, +1.85] | 0.51 | - | 1.21 | 24 | 3/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:k / req | exploratory | +9.37% [+8.60, +10.15] | 0.71 | - | 1.69 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req | exploratory | +3.84% [+3.28, +4.40] | 0.54 | - | 1.27 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, all hops | primary | +1.74% [+0.53, +2.97] | 1.20 | - | 2.84 | 24 | 7/24 | 0.064 | 0.013 | 0.007 | differs |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +1.74% [+0.53, +2.97] | 1.20 | - | 2.84 | 24 | 7/24 | 0.064 | 0.013 | - | exploratory: interval excludes 0 |
| lru vs mru | instructions:u / req, all hops | exploratory | +0.11% [+0.02, +0.20] | 0.09 | - | 0.21 | 24 | 7/24 | 0.064 | 0.009 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | -0.25% [-2.46, +2.01] | 2.24 | - | 5.30 | 24 | 13/24 | 0.839 | 0.317 | - | exploratory |
| lru vs mru | second hop: busiest worker's share | exploratory | -49.71% [-52.39, -46.89] | 5.47 | - | 12.96 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -49.83% [-51.61, -47.97] | 3.63 | - | 8.59 | 24 | 24/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +43.47% [+39.19, +47.88] | 3.03 | - | 7.17 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | p50 latency (us) | exploratory | -2.05% [-12.89, +10.14] | 11.73 | - | 27.79 | 24 | 9/24 | 0.307 | 0.160 | - | exploratory |
| lru vs mru | p99 latency (us) | exploratory | -7.40% [-19.68, +6.74] | 14.22 | - | 33.67 | 24 | 12/24 | 1.000 | 0.584 | - | exploratory |

## Validity

104 legs run, 100 valid; 8 legs superseded by a re-run of their round.
- r12-s-hi-lru (superseded): client overflow/pool-exhausted counters 1 (upstream_cx_overflow=1); client pending total 17 above 16 (queue absorbed a burst)
- r13-s-hi-lru (superseded): client overflow/pool-exhausted counters 2 (upstream_cx_overflow=2); client pending total 18 above 16 (queue absorbed a burst)
- r15-s-hi-lru (superseded): client overflow/pool-exhausted counters 52 (upstream_cx_overflow=52); client pending total 49 above 16 (queue absorbed a burst)
- r17-s-hi-mru (superseded): client overflow/pool-exhausted counters 35 (upstream_cx_overflow=35); client pending total 40 above 16 (queue absorbed a burst)

