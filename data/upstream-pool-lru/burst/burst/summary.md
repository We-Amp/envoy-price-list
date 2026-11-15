# lru-burst

- Harness: 0.1.0 196755054242
- Window: 2026-11-15T07:38:54Z to 2026-11-15T10:56:07Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1467787,2093873,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 64 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru --rate-limiter-plugin-config {"name":"nighthawk.linear-ramping-rate-limiter-plugin","typed_config":{"@type":"type.googleapis.com/nighthawk.rate_limiter.LinearRampingRateLimiterConfig","ramp_time":"2s"}}; warm-up 5s, run 150s, perf window 135s after 12s lead-in
- Rounds: 12 done (minimum 12, blocks of 12, cap 12, adaptive False), order rotate; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total_all, Holm across 5 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| mru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| lru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| mru-maxreq | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| mru-maxdur | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| lru-noeb | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| mru-idle5 | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |

## s-lo (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 12/12 | 163.8k | 344.6k | 158.7k | 503.8k (0.7%) | 671 | 1008 | 29.7% |
| lru | 12/12 | 163.9k | 345.9k | 171.1k | 516.4k (0.5%) | 684 | 1064 | 30.4% |
| mru-maxreq | 12/12 | 163.9k | 345.6k | 159.7k | 505.2k (0.5%) | 676 | 1015 | 29.8% |
| mru-maxdur | 12/12 | 163.6k | 344.8k | 159.5k | 504.4k (0.8%) | 669 | 991 | 29.8% |
| lru-noeb | 12/12 | 163.9k | 345.4k | 171.5k | 516.5k (0.8%) | 680 | 1070 | 30.4% |
| mru-idle5 | 12/12 | 163.4k | 344.3k | 159.0k | 502.9k (0.8%) | 669 | 993 | 29.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.06% [+0.04, +0.08] | 0.02 | - | 0.03 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:u / req | exploratory | +0.27% [-0.14, +0.69] | 0.41 | - | 0.65 | 12 | 3/12 | 0.146 | 0.151 | - | exploratory |
| lru vs mru | cycles:k / req | exploratory | +7.69% [+6.86, +8.53] | 0.78 | - | 1.22 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req | exploratory | +2.62% [+2.14, +3.09] | 0.46 | - | 0.73 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, all hops | primary | +1.24% [+0.52, +1.97] | 0.72 | - | 1.13 | 12 | 2/12 | 0.039 | 0.005 | 0.011 | differs |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +1.24% [+0.52, +1.97] | 0.72 | - | 1.13 | 12 | 2/12 | 0.039 | 0.005 | - | exploratory: interval excludes 0 |
| lru vs mru | instructions:u / req, all hops | exploratory | +0.07% [+0.04, +0.10] | 0.03 | - | 0.05 | 12 | 1/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | -0.05% [-1.57, +1.49] | 1.53 | - | 2.41 | 12 | 5/12 | 0.774 | 0.910 | - | exploratory |
| lru vs mru | second hop: busiest worker's share | exploratory | -50.51% [-55.33, -45.16] | 10.26 | - | 16.15 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -50.55% [-54.71, -46.00] | 8.80 | - | 13.85 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +1179.20% [+1081.37, +1285.12] | 7.96 | - | 12.52 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | p50 latency (us) | exploratory | +1.53% [+0.39, +2.69] | 1.13 | - | 1.78 | 12 | 3/12 | 0.146 | 0.016 | - | exploratory: interval excludes 0 |
| lru vs mru | p99 latency (us) | exploratory | +4.89% [+2.57, +7.26] | 2.23 | - | 3.51 | 12 | 1/12 | 0.006 | 0.002 | - | exploratory: interval excludes 0 |
| mru-maxreq vs mru | instructions:u / req | exploratory | +0.03% [+0.01, +0.05] | 0.02 | - | 0.03 | 12 | 2/12 | 0.039 | 0.005 | - | exploratory: interval excludes 0 |
| mru-maxreq vs mru | cycles:u / req | exploratory | +0.39% [+0.03, +0.76] | 0.36 | - | 0.57 | 12 | 2/12 | 0.039 | 0.021 | - | exploratory: interval excludes 0 |
| mru-maxreq vs mru | cycles:k / req | exploratory | +0.44% [-0.36, +1.25] | 0.80 | - | 1.26 | 12 | 4/12 | 0.388 | 0.266 | - | exploratory |
| mru-maxreq vs mru | cycles (u+k) / req | exploratory | +0.41% [-0.05, +0.86] | 0.45 | - | 0.71 | 12 | 3/12 | 0.146 | 0.077 | - | exploratory |
| mru-maxreq vs mru | cycles (u+k) / req, all hops | primary | +1.60% [+0.69, +2.53] | 0.91 | - | 1.43 | 12 | 2/12 | 0.039 | 0.005 | 0.011 | differs |
| mru-maxreq vs mru | cycles (u+k) / req / hop | exploratory | +1.60% [+0.69, +2.53] | 0.91 | - | 1.43 | 12 | 2/12 | 0.039 | 0.005 | - | exploratory: interval excludes 0 |
| mru-maxreq vs mru | instructions:u / req, all hops | exploratory | +0.01% [-0.03, +0.05] | 0.04 | - | 0.06 | 12 | 6/12 | 1.000 | 0.622 | - | exploratory |
| mru-maxreq vs mru | cycles (u+k) / req, second hop | exploratory | +2.77% [+1.05, +4.51] | 1.68 | - | 2.65 | 12 | 2/12 | 0.039 | 0.009 | - | exploratory: interval excludes 0 |
| mru-maxreq vs mru | second hop: busiest worker's share | exploratory | -48.79% [-54.03, -42.96] | 10.79 | - | 16.98 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-maxreq vs mru | second hop: busiest worker busy (of a core) | exploratory | -47.25% [-51.84, -42.22] | 9.10 | - | 14.33 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-maxreq vs mru | first hop -> second hop: connections carrying traffic | exploratory | -60.99% [-62.99, -58.87] | 5.28 | - | 8.31 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-maxreq vs mru | p50 latency (us) | exploratory | +0.33% [-0.91, +1.59] | 1.25 | - | 1.96 | 12 | 6/12 | 1.000 | 0.622 | - | exploratory |
| mru-maxreq vs mru | p99 latency (us) | exploratory | +0.80% [-1.97, +3.65] | 2.79 | - | 4.39 | 12 | 5/12 | 0.774 | 0.569 | - | exploratory |
| mru-maxdur vs mru | instructions:u / req | exploratory | -0.14% [-0.16, -0.13] | 0.01 | - | 0.02 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-maxdur vs mru | cycles:u / req | exploratory | +0.24% [-0.37, +0.85] | 0.61 | - | 0.96 | 12 | 5/12 | 0.774 | 0.569 | - | exploratory |
| mru-maxdur vs mru | cycles:k / req | exploratory | +0.44% [-0.35, +1.25] | 0.80 | - | 1.25 | 12 | 3/12 | 0.146 | 0.176 | - | exploratory |
| mru-maxdur vs mru | cycles (u+k) / req | exploratory | +0.30% [-0.31, +0.92] | 0.61 | - | 0.97 | 12 | 3/12 | 0.146 | 0.266 | - | exploratory |
| mru-maxdur vs mru | cycles (u+k) / req, all hops | primary | +2.47% [+1.61, +3.34] | 0.85 | - | 1.33 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| mru-maxdur vs mru | cycles (u+k) / req / hop | exploratory | +2.47% [+1.61, +3.34] | 0.85 | - | 1.33 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-maxdur vs mru | instructions:u / req, all hops | exploratory | -0.07% [-0.11, -0.04] | 0.04 | - | 0.06 | 12 | 11/12 | 0.006 | 0.002 | - | exploratory: interval excludes 0 |
| mru-maxdur vs mru | cycles (u+k) / req, second hop | exploratory | +4.57% [+2.79, +6.37] | 1.71 | - | 2.69 | 12 | 1/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| mru-maxdur vs mru | second hop: busiest worker's share | exploratory | -37.06% [-44.87, -28.14] | 13.25 | - | 20.86 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-maxdur vs mru | second hop: busiest worker busy (of a core) | exploratory | -33.90% [-41.06, -25.86] | 11.48 | - | 18.07 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-maxdur vs mru | first hop -> second hop: connections carrying traffic | exploratory | -56.90% [-59.07, -54.63] | 5.15 | - | 8.10 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-maxdur vs mru | p50 latency (us) | exploratory | -0.41% [-1.75, +0.94] | 1.35 | - | 2.13 | 12 | 7/12 | 0.774 | 0.622 | - | exploratory |
| mru-maxdur vs mru | p99 latency (us) | exploratory | -2.31% [-4.89, +0.35] | 2.68 | - | 4.22 | 12 | 8/12 | 0.388 | 0.092 | - | exploratory |
| lru-noeb vs mru | instructions:u / req | exploratory | +0.07% [+0.05, +0.10] | 0.03 | - | 0.04 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru-noeb vs mru | cycles:u / req | exploratory | +0.16% [-0.53, +0.84] | 0.68 | - | 1.08 | 12 | 5/12 | 0.774 | 0.677 | - | exploratory |
| lru-noeb vs mru | cycles:k / req | exploratory | +7.54% [+6.70, +8.40] | 0.79 | - | 1.24 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru-noeb vs mru | cycles (u+k) / req | exploratory | +2.49% [+1.79, +3.19] | 0.68 | - | 1.08 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru-noeb vs mru | cycles (u+k) / req, all hops | primary | +0.96% [-0.23, +2.17] | 1.19 | - | 1.87 | 12 | 3/12 | 0.146 | 0.110 | 0.104 | not resolved |
| lru-noeb vs mru | cycles (u+k) / req / hop | exploratory | +0.96% [-0.23, +2.17] | 1.19 | - | 1.87 | 12 | 3/12 | 0.146 | 0.110 | - | exploratory |
| lru-noeb vs mru | instructions:u / req, all hops | exploratory | +0.08% [+0.04, +0.12] | 0.04 | - | 0.07 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru-noeb vs mru | cycles (u+k) / req, second hop | exploratory | -0.49% [-2.47, +1.53] | 2.01 | - | 3.16 | 12 | 8/12 | 0.388 | 0.677 | - | exploratory |
| lru-noeb vs mru | second hop: busiest worker's share | exploratory | -46.73% [-52.02, -40.85] | 10.47 | - | 16.48 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru-noeb vs mru | second hop: busiest worker busy (of a core) | exploratory | -47.01% [-51.34, -42.29] | 8.53 | - | 13.43 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru-noeb vs mru | first hop -> second hop: connections carrying traffic | exploratory | +1182.20% [+1082.25, +1290.61] | 8.12 | - | 12.77 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru-noeb vs mru | p50 latency (us) | exploratory | +1.04% [-0.27, +2.35] | 1.30 | - | 2.04 | 12 | 3/12 | 0.146 | 0.110 | - | exploratory |
| lru-noeb vs mru | p99 latency (us) | exploratory | +4.89% [+2.16, +7.68] | 2.63 | - | 4.14 | 12 | 1/12 | 0.006 | 0.003 | - | exploratory: interval excludes 0 |
| mru-idle5 vs mru | instructions:u / req | exploratory | -0.27% [-0.29, -0.26] | 0.02 | - | 0.03 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-idle5 vs mru | cycles:u / req | exploratory | +0.07% [-0.32, +0.46] | 0.39 | - | 0.61 | 12 | 3/12 | 0.146 | 0.569 | - | exploratory |
| mru-idle5 vs mru | cycles:k / req | exploratory | +0.17% [-0.78, +1.12] | 0.95 | - | 1.50 | 12 | 5/12 | 0.774 | 0.677 | - | exploratory |
| mru-idle5 vs mru | cycles (u+k) / req | exploratory | +0.10% [-0.44, +0.64] | 0.54 | - | 0.85 | 12 | 4/12 | 0.388 | 0.470 | - | exploratory |
| mru-idle5 vs mru | cycles (u+k) / req, all hops | primary | +1.58% [+0.48, +2.69] | 1.09 | - | 1.71 | 12 | 2/12 | 0.039 | 0.016 | 0.018 | differs |
| mru-idle5 vs mru | cycles (u+k) / req / hop | exploratory | +1.58% [+0.48, +2.69] | 1.09 | - | 1.71 | 12 | 2/12 | 0.039 | 0.016 | - | exploratory: interval excludes 0 |
| mru-idle5 vs mru | instructions:u / req, all hops | exploratory | -0.17% [-0.21, -0.12] | 0.04 | - | 0.07 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-idle5 vs mru | cycles (u+k) / req, second hop | exploratory | +3.01% [+0.73, +5.33] | 2.23 | - | 3.51 | 12 | 2/12 | 0.039 | 0.016 | - | exploratory: interval excludes 0 |
| mru-idle5 vs mru | second hop: busiest worker's share | exploratory | -17.78% [-28.99, -4.79] | 14.66 | - | 23.07 | 12 | 10/12 | 0.039 | 0.012 | - | exploratory: interval excludes 0 |
| mru-idle5 vs mru | second hop: busiest worker busy (of a core) | exploratory | -15.03% [-24.91, -3.84] | 12.37 | - | 19.46 | 12 | 10/12 | 0.039 | 0.012 | - | exploratory: interval excludes 0 |
| mru-idle5 vs mru | first hop -> second hop: connections carrying traffic | exploratory | -57.35% [-59.21, -55.40] | 4.46 | - | 7.02 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| mru-idle5 vs mru | p50 latency (us) | exploratory | -0.39% [-1.75, +0.98] | 1.37 | - | 2.15 | 12 | 6/12 | 1.000 | 0.677 | - | exploratory |
| mru-idle5 vs mru | p99 latency (us) | exploratory | -1.33% [-4.47, +1.90] | 3.23 | - | 5.08 | 12 | 7/12 | 0.774 | 0.424 | - | exploratory |

## Validity

72 legs run, 72 valid; 0 legs superseded by a re-run of their round.

