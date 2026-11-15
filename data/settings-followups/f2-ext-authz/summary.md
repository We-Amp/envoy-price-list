# smf-ext-authz

- Harness: 0.1.0 ed217ec477fa
- Window: 2026-11-14T13:06:50Z to 2026-11-14T13:30:08Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1774167,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order rotate; stop: widest cycles_total half-width 0.74% (s authz-http vs authz-off) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| authz-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| authz-http | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| authz-grpc | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| authz-off | 12/12 | 163.9k | 344.4k | 181.1k | 525.3k (0.7%) | 398 | 619 | 31.1% |
| authz-http | 12/12 | 286.6k | 574.0k | 235.9k | 810.7k (0.7%) | 710 | 1990 | 47.1% |
| authz-grpc | 12/12 | 338.5k | 695.2k | 255.5k | 949.6k (0.8%) | 923 | 2884 | 54.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| authz-http vs authz-off | instructions:u / req | exploratory | +74.90% [+74.82, +74.99] | 0.05 | - | 0.08 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | cycles:u / req | exploratory | +67.22% [+66.43, +68.00] | 0.47 | - | 0.74 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | cycles:k / req | exploratory | +30.36% [+28.58, +32.15] | 1.37 | - | 2.15 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | cycles (u+k) / req | primary | +54.52% [+53.37, +55.67] | 0.74 | - | 1.17 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| authz-http vs authz-off | p50 latency (us) | exploratory | +78.33% [+74.30, +82.45] | 2.29 | - | 3.60 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | p99 latency (us) | exploratory | +206.87% [+173.37, +244.49] | 11.56 | - | 18.20 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | instructions:u / req | exploratory | +106.50% [+106.31, +106.69] | 0.09 | - | 0.14 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | cycles:u / req | exploratory | +101.80% [+101.08, +102.52] | 0.36 | - | 0.56 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | cycles:k / req | exploratory | +40.48% [+38.58, +42.41] | 1.36 | - | 2.14 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | cycles (u+k) / req | primary | +80.68% [+79.67, +81.69] | 0.56 | - | 0.88 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| authz-grpc vs authz-off | p50 latency (us) | exploratory | +133.71% [+125.32, +142.42] | 3.66 | - | 5.76 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | p99 latency (us) | exploratory | +367.01% [+327.25, +410.48] | 8.90 | - | 14.01 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

36 legs run, 36 valid; 0 legs superseded by a re-run of their round.

