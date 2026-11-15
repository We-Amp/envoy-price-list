# lru-burst-smoke

- Harness: 0.1.0 196755054242
- Window: 2026-11-15T07:34:10Z to 2026-11-15T07:38:54Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1609855,2295799,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 64 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru --rate-limiter-plugin-config {"name":"nighthawk.linear-ramping-rate-limiter-plugin","typed_config":{"@type":"type.googleapis.com/nighthawk.rate_limiter.LinearRampingRateLimiterConfig","ramp_time":"2s"}}; warm-up 5s, run 55s, perf window 40s after 12s lead-in
- Rounds: 2 done (minimum 2, blocks of 2, cap 2, adaptive False), order abba; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total_all, Holm across 0 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| mru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| lru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |

## s-lo (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 2/2 | 163.9k | 345.0k | 160.3k | 505.3k (0.3%) | 665 | 1033 | 29.8% |
| lru | 2/2 | 164.0k | 347.6k | 169.7k | 517.3k (0.0%) | 678 | 1073 | 30.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.04% [-0.01, +0.09] | 0.05 | - | 0.01 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | cycles:u / req | exploratory | +0.77% [-0.05, +1.60] | 0.82 | - | 0.09 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | cycles:k / req | exploratory | +5.85% [-2.84, +15.31] | 8.56 | - | 0.95 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | cycles (u+k) / req | exploratory | +2.38% [+0.14, +4.67] | 2.21 | - | 0.25 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | cycles (u+k) / req, all hops | primary | +1.94% [+1.18, +2.71] | 0.75 | - | 0.08 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +1.94% [+1.18, +2.71] | 0.75 | - | 0.08 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | instructions:u / req, all hops | exploratory | +0.11% [-0.07, +0.28] | 0.17 | - | 0.02 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | +1.52% [+0.83, +2.21] | 0.68 | - | 0.08 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | second hop: busiest worker's share | exploratory | -47.45% [-73.89, +5.75] | 69.94 | - | 7.78 | 2 | 2/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -46.61% [-73.64, +8.14] | 70.58 | - | 7.86 | 2 | 2/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +964.39% [+423.16, +2065.54] | 71.03 | - | 7.91 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | p50 latency (us) | exploratory | +1.85% [-3.43, +7.41] | 5.32 | - | 0.59 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| lru vs mru | p99 latency (us) | exploratory | +3.83% [-3.06, +11.22] | 6.87 | - | 0.76 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |

## Validity

4 legs run, 4 valid; 0 legs superseded by a re-run of their round.

