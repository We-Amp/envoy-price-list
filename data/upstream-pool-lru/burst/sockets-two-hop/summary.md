# lru-two-hop

- Harness: 0.1.0 196755054242
- Window: 2026-11-15T07:13:16Z to 2026-11-15T07:23:46Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1197833,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 4 done (minimum 4, blocks of 6, cap 4, adaptive False), order abba; stop: fixed rounds
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
| mru | 4/4 | 163.1k | 345.8k | 160.3k | 505.1k (1.3%) | 680 | 1051 | 29.8% |
| lru | 4/4 | 163.3k | 343.2k | 170.1k | 513.2k (0.4%) | 695 | 1130 | 30.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.14% [+0.10, +0.17] | 0.03 | - | 0.02 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | cycles:u / req | exploratory | -0.94% [-2.84, +1.00] | 1.94 | - | 1.22 | 4 | 3/4 | 0.625 | 0.250 | - | insufficient |
| lru vs mru | cycles:k / req | exploratory | +6.15% [+3.02, +9.37] | 2.99 | - | 1.88 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | cycles (u+k) / req | exploratory | +1.30% [-0.90, +3.56] | 2.21 | - | 1.39 | 4 | 1/4 | 0.625 | 0.250 | - | insufficient |
| lru vs mru | cycles (u+k) / req, all hops | primary | +3.17% [-3.21, +9.96] | 6.38 | - | 4.01 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +3.17% [-3.21, +9.96] | 6.38 | - | 4.01 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | instructions:u / req, all hops | exploratory | +0.27% [-0.11, +0.64] | 0.38 | - | 0.24 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | +5.22% [-7.31, +19.45] | 12.68 | - | 7.97 | 4 | 1/4 | 0.625 | 0.250 | - | insufficient |
| lru vs mru | second hop: busiest worker's share | exploratory | -61.69% [-76.55, -37.42] | 49.08 | - | 30.85 | 4 | 4/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -59.43% [-71.39, -42.49] | 34.91 | - | 21.94 | 4 | 4/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +0.39% [-0.86, +1.66] | 1.25 | - | 0.79 | 4 | 0/4 | 1.000 | 1.000 | - | insufficient |
| lru vs mru | p50 latency (us) | exploratory | -3.51% [-23.45, +21.62] | 23.15 | - | 14.55 | 4 | 1/4 | 0.625 | 0.875 | - | insufficient |
| lru vs mru | p99 latency (us) | exploratory | +3.08% [-15.45, +25.66] | 19.81 | - | 12.45 | 4 | 1/4 | 0.625 | 0.875 | - | insufficient |

## s-hi (`/s4`, proxied, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 4/4 | 163.0k | 312.1k | 142.0k | 454.5k (0.5%) | 762 | 1678 | 40.9% |
| lru | 4/4 | 163.1k | 317.6k | 154.3k | 473.0k (0.6%) | 844 | 1874 | 42.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.11% [-0.20, +0.42] | 0.31 | - | 0.19 | 4 | 2/4 | 1.000 | 0.625 | - | insufficient |
| lru vs mru | cycles:u / req | exploratory | +1.66% [+0.56, +2.76] | 1.08 | - | 0.68 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | cycles:k / req | exploratory | +9.39% [+5.38, +13.55] | 3.73 | - | 2.35 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | cycles (u+k) / req | exploratory | +4.07% [+2.33, +5.84] | 1.69 | - | 1.06 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | cycles (u+k) / req, all hops | primary | +2.44% [-5.94, +11.56] | 8.53 | - | 5.36 | 4 | 1/4 | 0.625 | 0.625 | - | insufficient |
| lru vs mru | cycles (u+k) / req / hop | exploratory | +2.44% [-5.94, +11.56] | 8.53 | - | 5.36 | 4 | 1/4 | 0.625 | 0.625 | - | insufficient |
| lru vs mru | instructions:u / req, all hops | exploratory | +0.17% [-0.67, +1.01] | 0.84 | - | 0.53 | 4 | 2/4 | 1.000 | 1.000 | - | insufficient |
| lru vs mru | cycles (u+k) / req, second hop | exploratory | +0.97% [-13.96, +18.48] | 15.99 | - | 10.05 | 4 | 2/4 | 1.000 | 1.000 | - | insufficient |
| lru vs mru | second hop: busiest worker's share | exploratory | -51.17% [-64.77, -32.32] | 32.65 | - | 20.52 | 4 | 4/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | second hop: busiest worker busy (of a core) | exploratory | -50.68% [-58.01, -42.08] | 16.08 | - | 10.10 | 4 | 4/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | first hop -> second hop: connections carrying traffic | exploratory | +14.51% [+6.08, +23.62] | 7.65 | - | 4.81 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | p50 latency (us) | exploratory | -20.93% [-75.32, +153.26] | 116.41 | - | 73.16 | 4 | 1/4 | 0.625 | 0.875 | - | insufficient |
| lru vs mru | p99 latency (us) | exploratory | -16.73% [-76.33, +192.91] | 125.78 | - | 79.05 | 4 | 1/4 | 0.625 | 0.875 | - | insufficient |

## Validity

16 legs run, 16 valid; 0 legs superseded by a re-run of their round.

