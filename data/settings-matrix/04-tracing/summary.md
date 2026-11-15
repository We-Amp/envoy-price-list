# sm-tracing

- Harness: 0.1.0 7e3abbe874af
- Window: 2026-11-14T08:27:16Z to 2026-11-14T09:08:29Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 16 done (minimum 16, blocks of 8, cap 32, adaptive True), order rotate; stop: widest cycles_total half-width 0.51% (s sampling-0 vs no-tracer) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 3 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| no-tracer | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| sampling-0 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| sampling-1 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| sampling-100 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| no-tracer | 16/16 | 163.9k | 344.7k | 180.9k | 525.4k (0.8%) | 397 | 623 | 31.3% |
| sampling-0 | 16/16 | 185.3k | 378.3k | 182.8k | 561.0k (0.7%) | 428 | 684 | 33.1% |
| sampling-1 | 16/16 | 186.7k | 380.0k | 183.5k | 562.7k (0.6%) | 422 | 721 | 33.2% |
| sampling-100 | 16/16 | 315.2k | 500.0k | 203.8k | 703.9k (0.4%) | 490 | 1048 | 41.1% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sampling-0 vs no-tracer | instructions:u / req | exploratory | +13.02% [+12.99, +13.05] | 0.02 | 0.02 | 0.04 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-0 vs no-tracer | cycles:u / req | exploratory | +9.80% [+9.26, +10.35] | 0.50 | 0.58 | 0.93 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-0 vs no-tracer | cycles:k / req | exploratory | +0.84% [+0.12, +1.57] | 0.72 | 0.63 | 1.35 | 16 | 4/16 | 0.077 | 0.021 | - | exploratory: interval excludes 0, inside the A/A interval |
| sampling-0 vs no-tracer | cycles (u+k) / req | primary | +6.71% [+6.17, +7.26] | 0.51 | 0.56 | 0.96 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| sampling-0 vs no-tracer | p50 latency (us) | exploratory | +7.31% [+5.56, +9.09] | 1.64 | 1.70 | 3.09 | 16 | 1/16 | 0.001 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-0 vs no-tracer | p99 latency (us) | exploratory | +12.11% [+8.71, +15.62] | 3.08 | 2.16 | 5.79 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-1 vs no-tracer | instructions:u / req | exploratory | +13.86% [+13.83, +13.90] | 0.03 | 0.02 | 0.06 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-1 vs no-tracer | cycles:u / req | exploratory | +10.13% [+9.60, +10.66] | 0.48 | 0.58 | 0.91 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-1 vs no-tracer | cycles:k / req | exploratory | +1.07% [+0.30, +1.84] | 0.76 | 0.63 | 1.43 | 16 | 4/16 | 0.077 | 0.016 | - | exploratory: interval excludes 0, inside the A/A interval |
| sampling-1 vs no-tracer | cycles (u+k) / req | primary | +7.00% [+6.47, +7.53] | 0.50 | 0.56 | 0.93 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| sampling-1 vs no-tracer | p50 latency (us) | exploratory | +5.84% [+4.60, +7.09] | 1.18 | 1.70 | 2.21 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-1 vs no-tracer | p99 latency (us) | exploratory | +15.37% [+11.66, +19.21] | 3.27 | 2.16 | 6.13 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-100 vs no-tracer | instructions:u / req | exploratory | +92.30% [+92.26, +92.34] | 0.02 | 0.02 | 0.03 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-100 vs no-tracer | cycles:u / req | exploratory | +45.16% [+44.56, +45.76] | 0.41 | 0.58 | 0.77 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-100 vs no-tracer | cycles:k / req | exploratory | +12.16% [+11.54, +12.79] | 0.56 | 0.63 | 1.05 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-100 vs no-tracer | cycles (u+k) / req | primary | +33.77% [+33.20, +34.34] | 0.43 | 0.56 | 0.80 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| sampling-100 vs no-tracer | p50 latency (us) | exploratory | +22.92% [+21.25, +24.61] | 1.36 | 1.70 | 2.56 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| sampling-100 vs no-tracer | p99 latency (us) | exploratory | +68.69% [+61.06, +76.69] | 4.63 | 2.16 | 8.69 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

64 legs run, 64 valid; 0 legs superseded by a re-run of their round.

