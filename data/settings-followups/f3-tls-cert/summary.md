# smf-tls-cert

- Harness: 0.1.0 ed217ec477fa
- Window: 2026-11-14T13:30:08Z to 2026-11-14T14:01:04Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2296048,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total half-width 0.87% (tls-ka ecdsa-p256 vs rsa2048) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| rsa2048 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| ecdsa-p256 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## tls-ka (`/s`, proxied, 4800 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| rsa2048 | 12/12 | 181.4k | 378.5k | 183.3k | 562.0k (0.9%) | 455 | 925 | 30.6% |
| ecdsa-p256 | 12/12 | 181.2k | 375.7k | 181.8k | 557.5k (1.2%) | 447 | 740 | 30.4% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ecdsa-p256 vs rsa2048 | instructions:u / req | exploratory | -0.05% [-0.13, +0.04] | 0.08 | - | 0.13 | 12 | 9/12 | 0.146 | 0.176 | - | exploratory |
| ecdsa-p256 vs rsa2048 | cycles:u / req | exploratory | -0.71% [-1.49, +0.06] | 0.78 | - | 1.23 | 12 | 8/12 | 0.388 | 0.064 | - | exploratory |
| ecdsa-p256 vs rsa2048 | cycles:k / req | exploratory | -0.60% [-1.74, +0.55] | 1.15 | - | 1.81 | 12 | 8/12 | 0.388 | 0.301 | - | exploratory |
| ecdsa-p256 vs rsa2048 | cycles (u+k) / req | primary | -0.68% [-1.54, +0.19] | 0.87 | - | 1.37 | 12 | 8/12 | 0.388 | 0.151 | 0.115 | not resolved |
| ecdsa-p256 vs rsa2048 | p50 latency (us) | exploratory | -0.00% [-1.71, +1.73] | 1.72 | - | 2.70 | 12 | 6/12 | 1.000 | 1.000 | - | exploratory |
| ecdsa-p256 vs rsa2048 | p99 latency (us) | exploratory | -26.31% [-35.36, -15.99] | 13.11 | - | 20.63 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## tls-hs-st (`/sh`, proxied, 2800 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| rsa2048 | 12/12 | 945.0k | 711.5k | 243.3k | 955.1k (0.3%) | 482 | 3019 | 30.6% |
| ecdsa-p256 | 12/12 | 344.4k | 529.2k | 255.2k | 784.4k (0.3%) | 456 | 626 | 25.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ecdsa-p256 vs rsa2048 | instructions:u / req | exploratory | -63.54% [-63.56, -63.53] | 0.04 | - | 0.06 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ecdsa-p256 vs rsa2048 | cycles:u / req | exploratory | -25.57% [-25.74, -25.39] | 0.24 | - | 0.38 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ecdsa-p256 vs rsa2048 | cycles:k / req | exploratory | +4.58% [+4.10, +5.07] | 0.46 | - | 0.73 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ecdsa-p256 vs rsa2048 | cycles (u+k) / req | primary | -17.87% [-18.05, -17.69] | 0.22 | - | 0.35 | 12 | 12/12 | 0.000 | 0.000 | 0.000 | differs |
| ecdsa-p256 vs rsa2048 | p50 latency (us) | exploratory | -4.55% [-5.91, -3.18] | 1.43 | - | 2.25 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ecdsa-p256 vs rsa2048 | p99 latency (us) | exploratory | -79.29% [-79.38, -79.21] | 0.42 | - | 0.66 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

48 legs run, 48 valid; 0 legs superseded by a re-run of their round.

