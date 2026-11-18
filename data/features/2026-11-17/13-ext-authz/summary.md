# features-ext-authz

- Harness: 0.x bb8aa8144e69 week5
- Window: 2026-11-17T17:29:41Z to 2026-11-17T18:51:58Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2295515,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 16 done (minimum 16, blocks of 16, cap 16, adaptive False), order rotate; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 6 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| authz-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| authz-http | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| authz-grpc | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| authz-off-A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| authz-off | 16/16 | 163.9k | 345.0k | 181.5k | 525.9k (1.0%) | 398 | 624 | 31.3% |
| authz-http | 16/16 | 286.8k | 575.1k | 237.0k | 812.4k (0.9%) | 689 | 1648 | 47.3% |
| authz-grpc | 16/16 | 338.7k | 693.6k | 255.3k | 947.4k (0.8%) | 910 | 2583 | 54.8% |
| authz-off-A2 | 16/16 | 163.9k | 344.7k | 180.9k | 525.7k (0.6%) | 397 | 624 | 31.2% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| authz-http vs authz-off | instructions:u / req | exploratory | +74.98% [+74.93, +75.03] | 0.03 | - | 0.06 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | cycles:u / req | exploratory | +66.56% [+65.43, +67.69] | 0.68 | - | 1.28 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | cycles:k / req | exploratory | +30.55% [+29.12, +32.00] | 1.10 | - | 2.07 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | cycles (u+k) / req | primary | +54.14% [+52.95, +55.34] | 0.78 | - | 1.46 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| authz-http vs authz-off | p50 latency (us) | exploratory | +74.62% [+71.71, +77.58] | 1.68 | - | 3.16 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | p99 latency (us) | exploratory | +179.29% [+152.95, +208.36] | 9.90 | - | 18.59 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | instructions:u / req | exploratory | +106.76% [+106.51, +107.01] | 0.12 | - | 0.23 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | cycles:u / req | exploratory | +100.88% [+99.77, +101.98] | 0.55 | - | 1.03 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | cycles:k / req | exploratory | +40.34% [+38.72, +41.98] | 1.16 | - | 2.18 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | cycles (u+k) / req | primary | +80.00% [+78.79, +81.23] | 0.68 | - | 1.27 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| authz-grpc vs authz-off | p50 latency (us) | exploratory | +128.16% [+122.47, +134.00] | 2.53 | - | 4.74 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | p99 latency (us) | exploratory | +312.99% [+290.05, +337.28] | 5.71 | - | 10.72 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-off-A2 vs authz-off | instructions:u / req | exploratory | -0.01% [-0.03, +0.01] | 0.02 | - | 0.03 | 16 | 10/16 | 0.454 | 0.231 | - | exploratory |
| authz-off-A2 vs authz-off | cycles:u / req | exploratory | -0.20% [-0.70, +0.30] | 0.50 | - | 0.94 | 16 | 8/16 | 1.000 | 0.782 | - | exploratory |
| authz-off-A2 vs authz-off | cycles:k / req | exploratory | -0.34% [-1.23, +0.56] | 0.90 | - | 1.68 | 16 | 9/16 | 0.804 | 0.433 | - | exploratory |
| authz-off-A2 vs authz-off | cycles (u+k) / req | primary | -0.25% [-0.84, +0.35] | 0.60 | - | 1.12 | 16 | 9/16 | 0.804 | 0.632 | 0.768 | not resolved |
| authz-off-A2 vs authz-off | p50 latency (us) | exploratory | -0.03% [-1.24, +1.20] | 1.22 | - | 2.29 | 16 | 8/16 | 1.000 | 1.000 | - | exploratory |
| authz-off-A2 vs authz-off | p99 latency (us) | exploratory | +0.04% [-1.36, +1.45] | 1.41 | - | 2.64 | 16 | 7/16 | 0.804 | 0.940 | - | exploratory |

## fh6 (`/fh`, direct_headers, 6000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| authz-off | 16/16 | 164.8k | 212.1k | 88.8k | 301.1k (1.2%) | 227 | 409 | 20.8% |
| authz-http | 16/16 | 286.6k | 457.5k | 149.3k | 606.5k (0.8%) | 511 | 1043 | 40.8% |
| authz-grpc | 16/16 | 339.6k | 566.6k | 172.1k | 738.8k (1.1%) | 655 | 1411 | 49.1% |
| authz-off-A2 | 16/16 | 164.8k | 211.3k | 88.4k | 299.9k (1.1%) | 227 | 411 | 20.8% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| authz-http vs authz-off | instructions:u / req | exploratory | +73.88% [+73.85, +73.91] | 0.02 | - | 0.03 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | cycles:u / req | exploratory | +116.62% [+115.04, +118.22] | 0.74 | - | 1.38 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | cycles:k / req | exploratory | +68.37% [+66.68, +70.08] | 1.01 | - | 1.90 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | cycles (u+k) / req | primary | +102.37% [+100.93, +103.82] | 0.71 | - | 1.34 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| authz-http vs authz-off | p50 latency (us) | exploratory | +125.65% [+122.36, +128.99] | 1.47 | - | 2.76 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-http vs authz-off | p99 latency (us) | exploratory | +170.78% [+145.02, +199.25] | 10.00 | - | 18.76 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | instructions:u / req | exploratory | +105.94% [+105.67, +106.21] | 0.13 | - | 0.25 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | cycles:u / req | exploratory | +167.98% [+166.22, +169.74] | 0.66 | - | 1.23 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | cycles:k / req | exploratory | +92.84% [+89.97, +95.76] | 1.50 | - | 2.82 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | cycles (u+k) / req | primary | +145.79% [+143.93, +147.66] | 0.76 | - | 1.42 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| authz-grpc vs authz-off | p50 latency (us) | exploratory | +186.82% [+180.60, +193.17] | 2.19 | - | 4.11 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-grpc vs authz-off | p99 latency (us) | exploratory | +276.80% [+233.71, +325.46] | 12.14 | - | 22.79 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| authz-off-A2 vs authz-off | instructions:u / req | exploratory | -0.00% [-0.00, +0.00] | 0.00 | - | 0.01 | 16 | 10/16 | 0.454 | 0.433 | - | exploratory |
| authz-off-A2 vs authz-off | cycles:u / req | exploratory | -0.07% [-0.98, +0.85] | 0.92 | - | 1.72 | 16 | 7/16 | 0.804 | 0.940 | - | exploratory |
| authz-off-A2 vs authz-off | cycles:k / req | exploratory | -0.19% [-1.17, +0.80] | 0.99 | - | 1.86 | 16 | 10/16 | 0.454 | 0.562 | - | exploratory |
| authz-off-A2 vs authz-off | cycles (u+k) / req | primary | -0.10% [-1.00, +0.80] | 0.90 | - | 1.69 | 16 | 7/16 | 0.804 | 0.900 | 0.811 | not resolved |
| authz-off-A2 vs authz-off | p50 latency (us) | exploratory | +0.11% [-0.93, +1.17] | 1.05 | - | 1.96 | 16 | 8/16 | 1.000 | 0.821 | - | exploratory |
| authz-off-A2 vs authz-off | p99 latency (us) | exploratory | +0.58% [-0.46, +1.63] | 1.04 | - | 1.95 | 16 | 4/16 | 0.077 | 0.117 | - | exploratory |

## Validity

128 legs run, 128 valid; 0 legs superseded by a re-run of their round.

