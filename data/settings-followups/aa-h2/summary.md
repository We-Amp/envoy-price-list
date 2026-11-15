# smf-aa-h2

- Harness: 0.1.0 ed217ec477fa
- Window: 2026-11-14T14:48:58Z to 2026-11-14T15:34:13Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1841601,2274522,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --h2 --prefetch-connections --max-pending-requests 1000; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 36 done (minimum 12, blocks of 6, cap 36, adaptive True), order abba; stop: cap of 36 rounds reached; widest cycles_total half-width 1.02% (fh2 A2 vs A) > target 1.00%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 1 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| A | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## fh2 (`/fh`, direct_headers, 8000 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 36/36 | 242.2k | 275.1k | 84.4k | 358.2k (2.8%) | 254 | 403 | 32.4% |
| A2 | 36/36 | 242.2k | 276.7k | 85.6k | 361.9k (2.1%) | 256 | 404 | 32.7% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | +0.01% [-0.00, +0.02] | 0.01 | - | 0.04 | 36 | 16/36 | 0.618 | 0.135 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | +0.74% [-0.29, +1.79] | 1.03 | - | 3.05 | 36 | 14/36 | 0.243 | 0.209 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | +1.24% [-0.13, +2.62] | 1.36 | - | 4.02 | 36 | 14/36 | 0.243 | 0.131 | - | exploratory |
| A2 vs A | cycles (u+k) / req | primary | +0.86% [-0.17, +1.89] | 1.02 | - | 3.02 | 36 | 14/36 | 0.243 | 0.098 | 0.098 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | -0.30% [-4.58, +4.17] | 4.38 | - | 12.96 | 36 | 20/36 | 0.618 | 0.727 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | -2.79% [-6.80, +1.39] | 4.21 | - | 12.44 | 36 | 22/36 | 0.243 | 0.239 | - | exploratory |

## Validity

72 legs run, 72 valid; 0 legs superseded by a re-run of their round.

## A/A self-test: FAIL

Rule: no Holm-significant difference and 95% half-width within the limit on every check.

| Shape | metric | effect [95% CI] | hw | limit | pair SD | 80%-power bias | n | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|---|
| fh2 | instructions_u | +0.01% [-0.00, +0.02] | 0.01 | 0.50 | 0.04 | 0.02% | 36 | 0.195 | ok |
| fh2 | cycles_total | +0.86% [-0.17, +1.89] | 1.02 | 1.00 | 3.02 | 1.45% | 36 | 0.195 | half-width 1.02% > 1.00% |

