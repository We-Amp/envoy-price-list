# smf-tls-resumption

- Harness: 0.1.0 ed217ec477fa
- Window: 2026-11-14T14:01:04Z to 2026-11-14T14:16:33Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1197346,2296112,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: widest cycles_total half-width 0.34% (tls-hs-st resumption-on vs resumption-off) <= target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 1 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| resumption-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| resumption-on | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## tls-hs-st (`/sh`, proxied, 2800 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| resumption-off | 12/12 | 944.6k | 711.6k | 243.0k | 955.0k (0.2%) | 483 | 3036 | 30.6% |
| resumption-on | 12/12 | 349.8k | 533.1k | 255.2k | 788.4k (0.4%) | 477 | 632 | 25.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| resumption-on vs resumption-off | instructions:u / req | exploratory | -62.97% [-62.99, -62.95] | 0.05 | - | 0.07 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| resumption-on vs resumption-off | cycles:u / req | exploratory | -25.11% [-25.32, -24.91] | 0.28 | - | 0.44 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| resumption-on vs resumption-off | cycles:k / req | exploratory | +5.15% [+4.57, +5.72] | 0.55 | - | 0.86 | 12 | 0/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| resumption-on vs resumption-off | cycles (u+k) / req | primary | -17.42% [-17.70, -17.14] | 0.34 | - | 0.54 | 12 | 12/12 | 0.000 | 0.000 | 0.000 | differs |
| resumption-on vs resumption-off | p50 latency (us) | exploratory | -1.46% [-2.45, -0.46] | 1.01 | - | 1.59 | 12 | 11/12 | 0.006 | 0.003 | - | exploratory: interval excludes 0 |
| resumption-on vs resumption-off | p99 latency (us) | exploratory | -79.21% [-79.33, -79.08] | 0.61 | - | 0.97 | 12 | 12/12 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

24 legs run, 24 valid; 0 legs superseded by a re-run of their round.

