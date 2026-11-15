# lru-demand-pool

- Harness: 0.1.0 ca73f83ab325 dirty
- Window: 2026-11-14T20:11:47Z to 2026-11-14T20:58:18Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2294637,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru --rate-limiter-plugin-config {"name":"nighthawk.linear-ramping-rate-limiter-plugin","typed_config":{"@type":"type.googleapis.com/nighthawk.rate_limiter.LinearRampingRateLimiterConfig","ramp_time":"2s"}}; warm-up 5s, run 25s, perf window 20s after 3s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order rotate; stop: widest cycles_total_all half-width 0.94% (s-lo mru-noeb vs mru) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total_all, Holm across 4 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| mru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| mru-noeb | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| lru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |

## s-lo (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 12/12 | 162.8k | 344.9k | 160.8k | 505.8k (0.9%) | 651 | 953 | 29.8% |
| mru-noeb | 12/12 | 162.8k | 343.9k | 160.0k | 503.6k (0.6%) | 650 | 965 | 29.7% |
| lru | 12/12 | 162.8k | 344.1k | 160.5k | 505.3k (0.7%) | 673 | 1011 | 29.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mru-noeb vs mru | instructions:u / req | exploratory | +0.00% [-0.01, +0.01] | 0.01 | - | 0.02 | 12 | 5/12 | 0.774 | 0.791 | - | exploratory |
| mru-noeb vs mru | cycles:u / req | exploratory | -0.17% [-0.73, +0.39] | 0.56 | - | 0.88 | 12 | 7/12 | 0.774 | 0.519 | - | exploratory |
| mru-noeb vs mru | cycles:k / req | exploratory | -0.45% [-1.14, +0.23] | 0.69 | - | 1.08 | 12 | 7/12 | 0.774 | 0.266 | - | exploratory |
| mru-noeb vs mru | cycles (u+k) / req | exploratory | -0.26% [-0.79, +0.26] | 0.53 | - | 0.83 | 12 | 7/12 | 0.774 | 0.380 | - | exploratory |
| mru-noeb vs mru | cycles (u+k) / req, all hops | primary | -1.63% [-2.55, -0.70] | 0.94 | - | 1.48 | 12 | 10/12 | 0.039 | 0.005 | 0.009 | differs |
| mru-noeb vs mru | cycles (u+k) / req / hop | exploratory | -1.63% [-2.55, -0.70] | 0.94 | - | 1.48 | 12 | 10/12 | 0.039 | 0.005 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | instructions:u / req, all hops | exploratory | -0.02% [-0.04, +0.01] | 0.02 | - | 0.03 | 12 | 9/12 | 0.146 | 0.204 | - | exploratory |
| mru-noeb vs mru | cycles (u+k) / req, second hop | exploratory | -2.88% [-4.65, -1.08] | 1.84 | - | 2.90 | 12 | 10/12 | 0.039 | 0.009 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | second hop: busiest worker's share | exploratory | +27.34% [+11.10, +45.96] | 13.64 | - | 21.48 | 12 | 2/12 | 0.039 | 0.003 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | second hop: busiest worker busy (of a core) | exploratory | +23.39% [+9.31, +39.28] | 12.11 | - | 19.07 | 12 | 2/12 | 0.039 | 0.003 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | first hop -> second hop: connections carrying traffic | exploratory | +0.97% [-6.91, +9.51] | 8.12 | - | 12.78 | 12 | 4/12 | 1.000 | 0.758 | - | exploratory |
| mru-noeb vs mru | p50 latency (us) | exploratory | +0.04% [-0.93, +1.02] | 0.98 | - | 1.54 | 12 | 6/12 | 1.000 | 0.569 | - | exploratory |
| mru-noeb vs mru | p99 latency (us) | exploratory | +1.79% [+0.54, +3.06] | 1.24 | - | 1.95 | 12 | 2/12 | 0.039 | 0.009 | - | exploratory: interval excludes 0 |
| lru vs mru | instructions:u / req | exploratory | +0.00% [-0.01, +0.01] | 0.01 | - | 0.02 | 12 | 4/12 | 0.388 | 0.622 | - | exploratory |
| lru vs mru | cycles:u / req | exploratory | -0.16% [-0.56, +0.24] | 0.40 | - | 0.63 | 12 | 8/12 | 0.388 | 0.301 | - | exploratory |
| lru vs mru | cycles:k / req | exploratory | -0.34% [-0.75, +0.08] | 0.42 | - | 0.66 | 12 | 8/12 | 0.388 | 0.129 | - | exploratory |
| lru vs mru | cycles (u+k) / req | exploratory | -0.22% [-0.57, +0.13] | 0.35 | - | 0.56 | 12 | 8/12 | 0.388 | 0.077 | - | exploratory |
| lru vs mru | cycles (u+k) / req, all hops | primary | +0.63% [+0.09, +1.17] | 0.54 | - | 0.85 | 12 | 3/12 | 0.146 | 0.021 | 0.053 | not resolved |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +0.63% [+0.09, +1.17] | 0.54 | - | 0.85 | 12 | 3/12 | 0.146 | 0.021 | - | exploratory: interval excludes 0 |
| lru vs mru | instructions:u / req, all hops | exploratory | -0.01% [-0.03, +0.02] | 0.02 | - | 0.04 | 12 | 8/12 | 0.388 | 0.733 | - | exploratory |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | +1.41% [+0.35, +2.48] | 1.05 | - | 1.65 | 12 | 2/12 | 0.039 | 0.009 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker's share | exploratory | -14.08% [-19.82, -7.94] | 6.90 | - | 10.87 | 12 | 11/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -12.94% [-18.25, -7.28] | 6.29 | - | 9.91 | 12 | 11/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +48.90% [+29.48, +71.24] | 13.98 | - | 22.00 | 12 | 0/12 | 0.001 | 0.001 | - | exploratory: interval excludes 0 |
| lru vs mru | p50 latency (us) | exploratory | +3.10% [+2.28, +3.93] | 0.80 | - | 1.27 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | p99 latency (us) | exploratory | +5.54% [+4.27, +6.83] | 1.21 | - | 1.91 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## s-hi (`/s4`, proxied, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 12/12 | 162.8k | 313.5k | 143.7k | 457.1k (0.6%) | 664 | 1047 | 41.2% |
| mru-noeb | 12/12 | 162.8k | 312.6k | 143.5k | 455.7k (0.6%) | 670 | 1070 | 41.0% |
| lru | 12/12 | 162.8k | 311.3k | 143.3k | 454.4k (0.7%) | 685 | 1092 | 40.9% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mru-noeb vs mru | instructions:u / req | exploratory | +0.02% [+0.00, +0.04] | 0.02 | - | 0.03 | 12 | 3/12 | 0.146 | 0.034 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | cycles:u / req | exploratory | -0.41% [-1.06, +0.24] | 0.65 | - | 1.02 | 12 | 8/12 | 0.388 | 0.176 | - | exploratory |
| mru-noeb vs mru | cycles:k / req | exploratory | -0.60% [-1.39, +0.21] | 0.81 | - | 1.27 | 12 | 7/12 | 0.774 | 0.151 | - | exploratory |
| mru-noeb vs mru | cycles (u+k) / req | exploratory | -0.47% [-1.11, +0.17] | 0.64 | - | 1.01 | 12 | 8/12 | 0.388 | 0.151 | - | exploratory |
| mru-noeb vs mru | cycles (u+k) / req, all hops | primary | -0.90% [-1.41, -0.40] | 0.51 | - | 0.80 | 12 | 9/12 | 0.146 | 0.007 | 0.009 | differs |
| mru-noeb vs mru | cycles (u+k) / req / hop | exploratory | -0.90% [-1.41, -0.40] | 0.51 | - | 0.80 | 12 | 9/12 | 0.146 | 0.007 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | instructions:u / req, all hops | exploratory | -0.01% [-0.03, +0.01] | 0.02 | - | 0.03 | 12 | 6/12 | 1.000 | 0.424 | - | exploratory |
| mru-noeb vs mru | cycles (u+k) / req, second hop | exploratory | -1.30% [-2.24, -0.35] | 0.96 | - | 1.51 | 12 | 10/12 | 0.039 | 0.016 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | second hop: busiest worker's share | exploratory | +15.58% [+8.53, +23.08] | 6.29 | - | 9.90 | 12 | 1/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | second hop: busiest worker busy (of a core) | exploratory | +13.93% [+7.39, +20.87] | 5.91 | - | 9.31 | 12 | 1/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | first hop -> second hop: connections carrying traffic | exploratory | +1.65% [-4.99, +8.74] | 6.75 | - | 10.62 | 12 | 3/12 | 0.227 | 0.768 | - | exploratory |
| mru-noeb vs mru | p50 latency (us) | exploratory | +0.83% [+0.13, +1.53] | 0.69 | - | 1.09 | 12 | 1/12 | 0.006 | 0.021 | - | exploratory: interval excludes 0 |
| mru-noeb vs mru | p99 latency (us) | exploratory | +3.46% [+0.25, +6.78] | 3.16 | - | 4.97 | 12 | 1/12 | 0.006 | 0.007 | - | exploratory: interval excludes 0 |
| lru vs mru | instructions:u / req | exploratory | +0.02% [+0.01, +0.04] | 0.02 | - | 0.03 | 12 | 2/12 | 0.039 | 0.009 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:u / req | exploratory | -0.76% [-1.31, -0.21] | 0.55 | - | 0.87 | 12 | 10/12 | 0.039 | 0.007 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:k / req | exploratory | -0.59% [-1.38, +0.21] | 0.80 | - | 1.26 | 12 | 9/12 | 0.146 | 0.129 | - | exploratory |
| lru vs mru | cycles (u+k) / req | exploratory | -0.71% [-1.24, -0.17] | 0.54 | - | 0.84 | 12 | 10/12 | 0.039 | 0.016 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, all hops | primary | +0.13% [-0.35, +0.61] | 0.48 | - | 0.76 | 12 | 6/12 | 1.000 | 0.622 | 0.567 | not resolved |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +0.13% [-0.35, +0.61] | 0.48 | - | 0.76 | 12 | 6/12 | 1.000 | 0.622 | - | exploratory |
| lru vs mru | instructions:u / req, all hops | exploratory | -0.03% [-0.05, -0.01] | 0.02 | - | 0.03 | 12 | 10/12 | 0.039 | 0.007 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | +0.88% [+0.11, +1.65] | 0.77 | - | 1.21 | 12 | 2/12 | 0.039 | 0.027 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker's share | exploratory | -11.51% [-18.87, -3.47] | 8.69 | - | 13.68 | 12 | 8/12 | 0.388 | 0.020 | - | exploratory: interval excludes 0 |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -10.77% [-17.61, -3.35] | 7.98 | - | 12.56 | 12 | 8/12 | 0.388 | 0.021 | - | exploratory: interval excludes 0 |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +24.39% [+12.22, +37.87] | 10.29 | - | 16.20 | 12 | 1/12 | 0.006 | 0.002 | - | exploratory: interval excludes 0 |
| lru vs mru | p50 latency (us) | exploratory | +2.58% [+1.51, +3.67] | 1.05 | - | 1.66 | 12 | 2/12 | 0.039 | 0.002 | - | exploratory: interval excludes 0 |
| lru vs mru | p99 latency (us) | exploratory | +4.29% [+1.83, +6.82] | 2.39 | - | 3.77 | 12 | 2/12 | 0.039 | 0.003 | - | exploratory: interval excludes 0 |

## Validity

72 legs run, 72 valid; 0 legs superseded by a re-run of their round.

