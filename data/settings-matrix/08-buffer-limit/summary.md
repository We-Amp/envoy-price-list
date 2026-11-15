# sm-buffer-limit

- Harness: 0.1.0 7e3abbe874af
- Window: 2026-11-14T10:02:47Z to 2026-11-14T10:18:19Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total half-width 0.63% (m buffer-4k vs buffer-default) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 1 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| buffer-default | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| buffer-4k | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## m (`/m`, proxied, 5440 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| buffer-default | 12/12 | 166.5k | 345.3k | 192.5k | 537.7k (0.6%) | 403 | 648 | 33.2% |
| buffer-4k | 12/12 | 182.0k | 381.4k | 264.3k | 645.5k (0.8%) | 479 | 993 | 39.3% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| buffer-4k vs buffer-default | instructions:u / req | exploratory | +9.30% [+9.24, +9.36] | 0.05 | 0.03 | 0.08 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| buffer-4k vs buffer-default | cycles:u / req | exploratory | +10.47% [+9.78, +11.16] | 0.62 | 0.45 | 0.98 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| buffer-4k vs buffer-default | cycles:k / req | exploratory | +37.34% [+36.31, +38.38] | 0.75 | 0.79 | 1.18 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| buffer-4k vs buffer-default | cycles (u+k) / req | primary | +20.09% [+19.34, +20.84] | 0.63 | 0.54 | 0.99 | 12 | 0/12 | 0.000 | 0.000 | 0.000 | differs |
| buffer-4k vs buffer-default | p50 latency (us) | exploratory | +18.76% [+16.55, +21.01] | 1.88 | 1.68 | 2.96 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| buffer-4k vs buffer-default | p99 latency (us) | exploratory | +68.89% [+42.67, +99.92] | 16.87 | 2.46 | 26.55 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

24 legs run, 24 valid; 0 legs superseded by a re-run of their round.

