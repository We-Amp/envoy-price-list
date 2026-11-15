# sm-hpack

- Harness: 0.1.0 7e3abbe874af
- Window: 2026-11-14T07:57:04Z to 2026-11-14T08:27:16Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --h2 --prefetch-connections --max-pending-requests 1000; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 24 done (minimum 12, blocks of 6, cap 24, adaptive True), order abba; stop: cap of 24 rounds reached; widest cycles_total half-width 1.59% (fh2 hpack-0 vs hpack-default) > target 1.50%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 1 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| hpack-default | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| hpack-0 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## fh2 (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| hpack-default | 24/24 | 242.2k | 277.9k | 85.7k | 362.4k (2.9%) | 265 | 402 | 32.7% |
| hpack-0 | 24/24 | 323.3k | 300.8k | 87.9k | 390.2k (2.4%) | 282 | 444 | 34.9% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hpack-0 vs hpack-default | instructions:u / req | exploratory | +33.49% [+33.46, +33.51] | 0.02 | - | 0.04 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| hpack-0 vs hpack-default | cycles:u / req | exploratory | +8.47% [+6.83, +10.14] | 1.52 | - | 3.61 | 24 | 0/24 | 0.000 | 0.000 | - | exploratory: interval excludes 0 |
| hpack-0 vs hpack-default | cycles:k / req | exploratory | +2.84% [+0.58, +5.15] | 2.22 | - | 5.27 | 24 | 7/24 | 0.064 | 0.021 | - | exploratory: interval excludes 0 |
| hpack-0 vs hpack-default | cycles (u+k) / req | primary | +7.14% [+5.45, +8.86] | 1.59 | - | 3.77 | 24 | 0/24 | 0.000 | 0.000 | 0.000 | differs |
| hpack-0 vs hpack-default | p50 latency (us) | exploratory | +10.33% [+5.12, +15.81] | 4.84 | - | 11.47 | 24 | 7/24 | 0.064 | 0.001 | - | exploratory: interval excludes 0 |
| hpack-0 vs hpack-default | p99 latency (us) | exploratory | +8.99% [+4.28, +13.92] | 4.42 | - | 10.48 | 24 | 4/24 | 0.002 | 0.001 | - | exploratory: interval excludes 0 |

## Validity

48 legs run, 48 valid; 0 legs superseded by a re-run of their round.

