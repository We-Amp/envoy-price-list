# lru-demand-pool-ka

- Harness: 0.1.0 ca73f83ab325 dirty
- Window: 2026-11-14T20:58:18Z to 2026-11-14T21:13:51Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1197451,2294596,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru --rate-limiter-plugin-config {"name":"nighthawk.linear-ramping-rate-limiter-plugin","typed_config":{"@type":"type.googleapis.com/nighthawk.rate_limiter.LinearRampingRateLimiterConfig","ramp_time":"2s"}}; warm-up 5s, run 25s, perf window 20s after 3s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total_all half-width 0.47% (s-hi lru vs mru) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total_all, Holm across 1 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| mru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| lru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |

## s-hi (`/s4`, proxied, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 12/12 | 162.7k | 313.5k | 144.2k | 457.8k (0.9%) | 648 | 1028 | 41.2% |
| lru | 12/12 | 162.7k | 314.7k | 143.8k | 459.0k (1.1%) | 671 | 1076 | 41.3% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | -0.00% [-0.02, +0.02] | 0.02 | - | 0.03 | 12 | 7/12 | 0.774 | 0.733 | - | exploratory |
| lru vs mru | cycles:u / req | exploratory | +0.09% [-0.59, +0.78] | 0.68 | - | 1.08 | 12 | 5/12 | 0.774 | 0.622 | - | exploratory |
| lru vs mru | cycles:k / req | exploratory | +0.09% [-0.63, +0.81] | 0.72 | - | 1.13 | 12 | 5/12 | 0.774 | 0.791 | - | exploratory |
| lru vs mru | cycles (u+k) / req | exploratory | +0.09% [-0.54, +0.73] | 0.63 | - | 1.00 | 12 | 6/12 | 1.000 | 0.791 | - | exploratory |
| lru vs mru | cycles (u+k) / req, all hops | primary | +0.36% [-0.10, +0.84] | 0.47 | - | 0.74 | 12 | 5/12 | 0.774 | 0.129 | 0.115 | not resolved |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +0.36% [-0.10, +0.84] | 0.47 | - | 0.74 | 12 | 5/12 | 0.774 | 0.129 | - | exploratory |
| lru vs mru | instructions:u / req, all hops | exploratory | -0.02% [-0.03, -0.01] | 0.01 | - | 0.02 | 12 | 11/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | +0.61% [-0.13, +1.35] | 0.74 | - | 1.16 | 12 | 3/12 | 0.146 | 0.129 | - | exploratory |
| lru vs mru | second hop: busiest worker's share | exploratory | -0.49% [-2.49, +1.55] | 2.03 | - | 3.19 | 12 | 7/12 | 0.774 | 0.677 | - | exploratory |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | +0.04% [-1.94, +2.07] | 2.00 | - | 3.15 | 12 | 7/12 | 0.774 | 0.733 | - | exploratory |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +6.75% [-2.03, +16.32] | 8.58 | - | 13.51 | 12 | 2/12 | 0.109 | 0.113 | - | exploratory |
| lru vs mru | p50 latency (us) | exploratory | +3.44% [+2.23, +4.67] | 1.18 | - | 1.86 | 12 | 1/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| lru vs mru | p99 latency (us) | exploratory | +4.34% [+1.41, +7.36] | 2.85 | - | 4.48 | 12 | 1/12 | 0.006 | 0.021 | - | exploratory: interval excludes 0 |

## Validity

24 legs run, 24 valid; 0 legs superseded by a re-run of their round.

