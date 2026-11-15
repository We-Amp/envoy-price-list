# sm-tls-cert

- Harness: 0.1.0 7e3abbe874af
- Window: 2026-11-14T07:10:09Z to 2026-11-14T07:41:21Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1988897,2294558,2295170,2300000
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
| rsa2048 | 12/12 | 181.4k | 378.0k | 181.5k | 559.8k (1.0%) | 458 | 894 | 30.5% |
| ecdsa-p256 | 12/12 | 181.1k | 376.3k | 182.4k | 558.8k (0.9%) | 442 | 723 | 30.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ecdsa-p256 vs rsa2048 | instructions:u / req | exploratory | -0.11% [-0.18, -0.05] | 0.07 | - | 0.10 | 12 | 10/12 | 0.039 | 0.003 | - | exploratory: interval excludes 0 |
| ecdsa-p256 vs rsa2048 | cycles:u / req | exploratory | -0.56% [-1.30, +0.18] | 0.74 | - | 1.17 | 12 | 11/12 | 0.006 | 0.034 | - | exploratory |
| ecdsa-p256 vs rsa2048 | cycles:k / req | exploratory | +0.09% [-1.24, +1.43] | 1.33 | - | 2.10 | 12 | 7/12 | 0.774 | 0.910 | - | exploratory |
| ecdsa-p256 vs rsa2048 | cycles (u+k) / req | primary | -0.35% [-1.22, +0.52] | 0.87 | - | 1.37 | 12 | 9/12 | 0.146 | 0.204 | 0.391 | not resolved |
| ecdsa-p256 vs rsa2048 | p50 latency (us) | exploratory | -2.47% [-4.49, -0.40] | 2.10 | - | 3.30 | 12 | 9/12 | 0.146 | 0.042 | - | exploratory: interval excludes 0 |
| ecdsa-p256 vs rsa2048 | p99 latency (us) | exploratory | -21.65% [-27.65, -15.14] | 7.97 | - | 12.55 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## tls-hs (`/sh`, proxied, 2800 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| rsa2048 | 12/12 | 950.4k | 700.9k | 233.7k | 934.1k (0.4%) | 480 | 18765 | 29.7% |
| ecdsa-p256 | 12/12 | 346.5k | 520.2k | 245.4k | 765.6k (0.3%) | 479 | 1553 | 24.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ecdsa-p256 vs rsa2048 | instructions:u / req | exploratory | -63.54% [-63.54, -63.53] | 0.01 | - | 0.01 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ecdsa-p256 vs rsa2048 | cycles:u / req | exploratory | -25.71% [-25.92, -25.50] | 0.29 | - | 0.45 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ecdsa-p256 vs rsa2048 | cycles:k / req | exploratory | +5.11% [+4.45, +5.78] | 0.63 | - | 1.00 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| ecdsa-p256 vs rsa2048 | cycles (u+k) / req | primary | -18.01% [-18.26, -17.76] | 0.31 | - | 0.48 | 12 | 12/12 | 0.000 | 0.000 | 0.000 | differs |
| ecdsa-p256 vs rsa2048 | p50 latency (us) | exploratory | -0.35% [-0.72, +0.03] | 0.38 | - | 0.59 | 12 | 10/12 | 0.039 | 0.042 | - | exploratory |
| ecdsa-p256 vs rsa2048 | p99 latency (us) | exploratory | -91.84% [-92.85, -90.69] | 13.19 | - | 20.75 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

48 legs run, 48 valid; 0 legs superseded by a re-run of their round.

