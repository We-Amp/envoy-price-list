# features-jit-check

- Harness: 0.x 6dd53317484c week5-s2
- Window: 2026-11-17T23:54:42Z to 2026-11-18T00:01:37Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 2 done (minimum 2, blocks of 2, cap 2, adaptive False), order abba; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 0 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| lua-header | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| wasm-header | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s-wu5 (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| lua-header | 2/2 | 195.4k | 400.0k | 181.1k | 581.1k (0.7%) | 438 | 782 | 34.1% |
| wasm-header | 2/2 | 203.1k | 426.1k | 186.1k | 612.2k (0.1%) | 449 | 835 | 35.9% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| wasm-header vs lua-header | instructions:u / req | exploratory | +3.94% [+3.91, +3.97] | 0.03 | - | 0.00 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| wasm-header vs lua-header | cycles:u / req | exploratory | +6.53% [-0.98, +14.61] | 7.31 | - | 0.81 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| wasm-header vs lua-header | cycles:k / req | exploratory | +2.79% [-4.95, +11.15] | 7.82 | - | 0.87 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| wasm-header vs lua-header | cycles (u+k) / req | primary | +5.36% [-2.25, +13.57] | 7.50 | - | 0.83 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| wasm-header vs lua-header | p50 latency (us) | exploratory | +2.49% [-6.50, +12.36] | 9.19 | - | 1.02 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| wasm-header vs lua-header | p99 latency (us) | exploratory | +6.89% [-7.25, +23.19] | 14.19 | - | 1.58 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |

## s-wu30 (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| lua-header | 2/2 | 195.2k | 403.3k | 183.0k | 586.3k (1.2%) | 449 | 818 | 34.4% |
| wasm-header | 2/2 | 203.1k | 424.0k | 182.6k | 606.6k (0.1%) | 460 | 821 | 35.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| wasm-header vs lua-header | instructions:u / req | exploratory | +4.00% [+3.27, +4.74] | 0.71 | - | 0.08 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| wasm-header vs lua-header | cycles:u / req | exploratory | +5.14% [-3.00, +13.96] | 8.06 | - | 0.90 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| wasm-header vs lua-header | cycles:k / req | exploratory | -0.20% [-14.93, +17.09] | 15.97 | - | 1.78 | 2 | 1/2 | 1.000 | 1.000 | - | insufficient |
| wasm-header vs lua-header | cycles (u+k) / req | primary | +3.47% [-6.76, +14.83] | 10.41 | - | 1.16 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| wasm-header vs lua-header | p50 latency (us) | exploratory | +2.42% [+1.12, +3.74] | 1.28 | - | 0.14 | 2 | 0/2 | 0.500 | 0.500 | - | insufficient |
| wasm-header vs lua-header | p99 latency (us) | exploratory | +0.51% [-20.30, +26.76] | 23.20 | - | 2.58 | 2 | 1/2 | 1.000 | 1.000 | - | insufficient |

## Validity

8 legs run, 8 valid; 0 legs superseded by a re-run of their round.

