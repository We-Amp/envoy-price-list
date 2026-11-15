# lru-one-hop

- Harness: 0.1.0 196755054242
- Window: 2026-11-15T07:23:46Z to 2026-11-15T07:34:10Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2151346,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 4 done (minimum 4, blocks of 6, cap 4, adaptive False), order abba; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 0 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| mru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| lru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |

## s-lo (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 4/4 | 163.8k | 345.8k | 183.0k | 528.8k (0.8%) | 397 | 628 | 31.4% |
| lru | 4/4 | 164.1k | 348.2k | 183.5k | 532.3k (0.8%) | 414 | 648 | 31.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.18% [+0.05, +0.31] | 0.13 | - | 0.08 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | cycles:u / req | exploratory | +0.14% [-1.20, +1.49] | 1.34 | - | 0.84 | 4 | 2/4 | 1.000 | 0.625 | - | insufficient |
| lru vs mru | cycles:k / req | exploratory | +0.10% [-1.84, +2.08] | 1.96 | - | 1.23 | 4 | 3/4 | 0.625 | 0.875 | - | insufficient |
| lru vs mru | cycles (u+k) / req | primary | +0.12% [-1.30, +1.56] | 1.43 | - | 0.90 | 4 | 2/4 | 1.000 | 0.875 | - | insufficient |
| lru vs mru | p50 latency (us) | exploratory | +4.99% [+3.25, +6.75] | 1.67 | - | 1.05 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | p99 latency (us) | exploratory | +4.87% [-0.83, +10.90] | 5.59 | - | 3.51 | 4 | 0/4 | 0.125 | 0.125 | - | insufficient |

## s-hi (`/s4`, proxied, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 4/4 | 163.8k | 324.4k | 166.8k | 491.2k (0.3%) | 418 | 1019 | 44.0% |
| lru | 4/4 | 164.3k | 322.5k | 166.9k | 489.5k (0.6%) | 414 | 882 | 44.0% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.22% [-0.13, +0.57] | 0.35 | - | 0.22 | 4 | 1/4 | 0.625 | 0.250 | - | insufficient |
| lru vs mru | cycles:u / req | exploratory | -0.41% [-1.08, +0.27] | 0.68 | - | 0.43 | 4 | 4/4 | 0.125 | 0.125 | - | insufficient |
| lru vs mru | cycles:k / req | exploratory | +0.20% [-2.21, +2.68] | 2.44 | - | 1.53 | 4 | 2/4 | 1.000 | 0.625 | - | insufficient |
| lru vs mru | cycles (u+k) / req | primary | -0.20% [-0.80, +0.40] | 0.60 | - | 0.38 | 4 | 3/4 | 0.625 | 0.375 | - | insufficient |
| lru vs mru | p50 latency (us) | exploratory | -1.62% [-10.25, +7.84] | 9.18 | - | 5.77 | 4 | 3/4 | 0.625 | 0.625 | - | insufficient |
| lru vs mru | p99 latency (us) | exploratory | -14.03% [-34.22, +12.35] | 26.76 | - | 16.82 | 4 | 3/4 | 0.625 | 0.250 | - | insufficient |

## Validity

16 legs run, 16 valid; 0 legs superseded by a re-run of their round.

