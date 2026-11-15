# sm-two-hop

- Harness: 0.1.0 7e3abbe874af
- Window: 2026-11-14T10:49:12Z to 2026-11-14T11:04:47Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2295479,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total_per_hop half-width 1.25% (s two-hop vs one-hop) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total_per_hop, Holm across 1 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| one-hop | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| two-hop | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| one-hop | 12/12 | 163.9k | 344.6k | 181.0k | 525.4k (0.5%) | 398 | 626 | 31.2% |
| two-hop | 12/12 | 163.0k | 345.2k | 157.8k | 503.3k (0.7%) | 813 | 1207 | 29.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| two-hop vs one-hop | instructions:u / req | exploratory | -0.51% [-0.54, -0.47] | 0.04 | 0.02 | 0.06 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop vs one-hop | cycles:u / req | exploratory | +0.33% [-0.12, +0.78] | 0.45 | 0.58 | 0.71 | 12 | 3/12 | 0.146 | 0.110 | - | exploratory |
| two-hop vs one-hop | cycles:k / req | exploratory | -12.57% [-13.31, -11.82] | 0.85 | 0.63 | 1.34 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop vs one-hop | cycles (u+k) / req | exploratory | -4.11% [-4.63, -3.59] | 0.54 | 0.56 | 0.85 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop vs one-hop | cycles (u+k) / req, all hops | exploratory | +83.73% [+81.44, +86.04] | 1.25 | - | 1.97 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop vs one-hop | cycles (u+k) / req / hop | primary | -8.14% [-9.28, -6.98] | 1.25 | - | 1.97 | 12 | 12/12 | 0.000 | 0.000 | 0.000 | differs |
| two-hop vs one-hop | instructions:u / req, all hops | exploratory | +106.12% [+105.89, +106.36] | 0.12 | - | 0.18 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop vs one-hop | p50 latency (us) | exploratory | +105.13% [+89.11, +122.51] | 8.13 | 1.70 | 12.80 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| two-hop vs one-hop | p99 latency (us) | exploratory | +96.01% [+80.54, +112.80] | 8.22 | 2.16 | 12.94 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

24 legs run, 24 valid; 0 legs superseded by a re-run of their round.

