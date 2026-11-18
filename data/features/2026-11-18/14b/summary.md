# features-compressor-idle

- Harness: 0.x 4fc7986fe46f week5-s2
- Window: 2026-11-18T06:35:31Z to 2026-11-18T06:56:10Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 16 done (minimum 16, blocks of 4, cap 32, adaptive True), order abba; stop: widest cycles_total half-width against its target 0.56% (s-ae gzip vs comp-off) <= target 0.80%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 1 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| comp-off | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| gzip | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s-ae (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| comp-off | 16/16 | 168.9k | 346.9k | 180.6k | 527.6k (0.8%) | 399 | 627 | 31.3% |
| gzip | 16/16 | 182.5k | 372.4k | 183.3k | 555.6k (0.7%) | 413 | 659 | 32.8% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gzip vs comp-off | instructions:u / req | exploratory | +8.07% [+8.04, +8.10] | 0.03 | - | 0.06 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | cycles:u / req | exploratory | +7.36% [+6.88, +7.84] | 0.45 | - | 0.84 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | cycles:k / req | exploratory | +1.21% [+0.31, +2.12] | 0.89 | - | 1.68 | 16 | 4/16 | 0.077 | 0.016 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | cycles (u+k) / req | primary | +5.25% [+4.66, +5.84] | 0.56 | - | 1.06 | 16 | 0/16 | 0.000 | 0.000 | 0.000 | differs |
| gzip vs comp-off | p50 latency (us) | exploratory | +3.57% [+2.19, +4.96] | 1.34 | - | 2.51 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| gzip vs comp-off | p99 latency (us) | exploratory | +6.44% [+4.00, +8.93] | 2.31 | - | 4.34 | 16 | 0/16 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |

## Validity

32 legs run, 32 valid; 0 legs superseded by a re-run of their round.

