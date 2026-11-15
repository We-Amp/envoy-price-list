# lru-one-hop

- Harness: 0.1.0 2b8f3fdbf38f
- Window: 2026-11-14T16:42:17Z to 2026-11-14T17:13:14Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2294584,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total half-width 0.83% (s-hi lru vs mru) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| mru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| lru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |

## s-lo (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 12/12 | 163.9k | 346.2k | 181.9k | 527.7k (0.8%) | 400 | 628 | 31.4% |
| lru | 12/12 | 164.1k | 346.5k | 183.5k | 530.3k (0.8%) | 408 | 642 | 31.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.15% [+0.13, +0.17] | 0.02 | - | 0.03 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:u / req | exploratory | +0.01% [-0.56, +0.58] | 0.57 | - | 0.90 | 12 | 7/12 | 0.774 | 0.733 | - | exploratory |
| lru vs mru | cycles:k / req | exploratory | +0.33% [-0.40, +1.07] | 0.74 | - | 1.16 | 12 | 6/12 | 1.000 | 0.380 | - | exploratory |
| lru vs mru | cycles (u+k) / req | primary | +0.12% [-0.47, +0.71] | 0.59 | - | 0.93 | 12 | 5/12 | 0.774 | 0.910 | 0.908 | not resolved |
| lru vs mru | p50 latency (us) | exploratory | +1.77% [+0.03, +3.54] | 1.73 | - | 2.72 | 12 | 3/12 | 0.146 | 0.034 | - | exploratory: interval excludes 0 |
| lru vs mru | p99 latency (us) | exploratory | +2.48% [+0.16, +4.86] | 2.29 | - | 3.61 | 12 | 2/12 | 0.039 | 0.027 | - | exploratory: interval excludes 0 |

## s-hi (`/s4`, proxied, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 12/12 | 164.0k | 322.8k | 166.3k | 489.0k (0.7%) | 406 | 896 | 43.9% |
| lru | 12/12 | 164.2k | 324.0k | 167.3k | 491.1k (1.0%) | 412 | 931 | 44.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lru vs mru | instructions:u / req | exploratory | +0.18% [+0.09, +0.28] | 0.10 | - | 0.15 | 12 | 1/12 | 0.006 | 0.001 | - | exploratory: interval excludes 0 |
| lru vs mru | cycles:u / req | exploratory | +0.25% [-0.61, +1.11] | 0.86 | - | 1.35 | 12 | 4/12 | 0.388 | 0.519 | - | exploratory |
| lru vs mru | cycles:k / req | exploratory | +0.38% [-0.67, +1.44] | 1.05 | - | 1.66 | 12 | 5/12 | 0.774 | 0.424 | - | exploratory |
| lru vs mru | cycles (u+k) / req | primary | +0.29% [-0.53, +1.13] | 0.83 | - | 1.30 | 12 | 5/12 | 0.774 | 0.519 | 0.908 | not resolved |
| lru vs mru | p50 latency (us) | exploratory | +0.99% [-1.42, +3.46] | 2.42 | - | 3.80 | 12 | 4/12 | 0.388 | 0.380 | - | exploratory |
| lru vs mru | p99 latency (us) | exploratory | -1.06% [-21.08, +24.04] | 22.61 | - | 35.58 | 12 | 5/12 | 0.774 | 0.791 | - | exploratory |

## Validity

48 legs run, 48 valid; 0 legs superseded by a re-run of their round.

