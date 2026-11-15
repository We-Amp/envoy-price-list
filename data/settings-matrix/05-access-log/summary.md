# sm-access-log

- Harness: 0.1.0 7e3abbe874af
- Window: 2026-11-14T09:08:29Z to 2026-11-14T09:31:44Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order rotate; stop: widest cycles_total half-width 0.85% (s log-text vs log-off) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| log-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| log-text | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| log-json | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| log-off | 12/12 | 163.8k | 345.1k | 181.4k | 526.3k (0.9%) | 396 | 627 | 31.2% |
| log-text | 12/12 | 170.5k | 363.3k | 182.7k | 546.0k (0.7%) | 409 | 658 | 32.3% |
| log-json | 12/12 | 173.6k | 365.6k | 183.9k | 549.4k (0.7%) | 411 | 656 | 32.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| log-text vs log-off | instructions:u / req | exploratory | +4.07% [+4.03, +4.10] | 0.03 | 0.02 | 0.05 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | cycles:u / req | exploratory | +5.07% [+4.21, +5.94] | 0.82 | 0.58 | 1.30 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-text vs log-off | cycles:k / req | exploratory | +0.83% [-0.24, +1.92] | 1.07 | 0.63 | 1.69 | 12 | 4/12 | 0.388 | 0.204 | - | exploratory |
| log-text vs log-off | cycles (u+k) / req | primary | +3.61% [+2.74, +4.49] | 0.85 | 0.56 | 1.33 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| log-text vs log-off | p50 latency (us) | exploratory | +3.07% [+1.33, +4.85] | 1.71 | 1.70 | 2.69 | 12 | 2/12 | 0.039 | 0.005 | - | exploratory: interval excludes 0 |
| log-text vs log-off | p99 latency (us) | exploratory | +5.44% [+1.61, +9.42] | 3.70 | 2.16 | 5.83 | 12 | 2/12 | 0.039 | 0.009 | - | exploratory: interval excludes 0 |
| log-json vs log-off | instructions:u / req | exploratory | +5.97% [+5.94, +6.00] | 0.03 | 0.02 | 0.04 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles:u / req | exploratory | +6.07% [+5.34, +6.82] | 0.70 | 0.58 | 1.10 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles:k / req | exploratory | +1.55% [+0.81, +2.29] | 0.73 | 0.63 | 1.15 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| log-json vs log-off | cycles (u+k) / req | primary | +4.52% [+3.82, +5.21] | 0.67 | 0.56 | 1.05 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| log-json vs log-off | p50 latency (us) | exploratory | +3.38% [+0.87, +5.95] | 2.46 | 1.70 | 3.87 | 12 | 3/12 | 0.146 | 0.009 | - | exploratory: interval excludes 0 |
| log-json vs log-off | p99 latency (us) | exploratory | +4.15% [+1.42, +6.96] | 2.66 | 2.16 | 4.19 | 12 | 1/12 | 0.006 | 0.007 | - | exploratory: interval excludes 0 |

## Validity

36 legs run, 36 valid; 0 legs superseded by a re-run of their round.

