# smf-aa-tls

- Harness: 0.1.0 ed217ec477fa
- Window: 2026-11-14T14:16:33Z to 2026-11-14T14:48:58Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 2296652,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-3,40-43): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 12 done (minimum 12, blocks of 6, cap 36, adaptive True), order abba; stop: widest cycles_total half-width 0.82% (tls-ka A2 vs A) <= target 1.00%
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total, Holm across 2 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| A | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## tls-ka (`/s`, proxied, 4800 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 12/12 | 181.3k | 375.2k | 180.6k | 555.5k (1.4%) | 449 | 936 | 30.2% |
| A2 | 12/12 | 181.3k | 378.2k | 183.2k | 561.7k (1.0%) | 450 | 911 | 30.6% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | +0.04% [-0.02, +0.11] | 0.07 | - | 0.10 | 12 | 7/12 | 0.774 | 0.622 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | +0.85% [+0.16, +1.55] | 0.69 | - | 1.08 | 12 | 3/12 | 0.146 | 0.027 | - | exploratory: interval excludes 0 |
| A2 vs A | cycles:k / req | exploratory | +1.55% [+0.27, +2.85] | 1.27 | - | 2.00 | 12 | 2/12 | 0.039 | 0.009 | - | exploratory: interval excludes 0 |
| A2 vs A | cycles (u+k) / req | primary | +1.08% [+0.26, +1.91] | 0.82 | - | 1.29 | 12 | 2/12 | 0.039 | 0.009 | 0.030 | differs |
| A2 vs A | p50 latency (us) | exploratory | -0.69% [-3.36, +2.05] | 2.73 | - | 4.29 | 12 | 6/12 | 1.000 | 0.791 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | -10.20% [-33.04, +20.44] | 29.35 | - | 46.20 | 12 | 7/12 | 0.774 | 0.569 | - | exploratory |

## tls-hs-st (`/sh`, proxied, 2800 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 12/12 | 944.8k | 711.9k | 243.3k | 955.5k (0.3%) | 483 | 3032 | 30.6% |
| A2 | 12/12 | 945.0k | 712.0k | 242.2k | 954.2k (0.3%) | 481 | 3030 | 30.5% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 vs A | instructions:u / req | exploratory | +0.01% [-0.03, +0.05] | 0.04 | - | 0.06 | 12 | 5/12 | 0.774 | 0.677 | - | exploratory |
| A2 vs A | cycles:u / req | exploratory | -0.06% [-0.36, +0.24] | 0.30 | - | 0.48 | 12 | 6/12 | 1.000 | 0.791 | - | exploratory |
| A2 vs A | cycles:k / req | exploratory | -0.33% [-0.91, +0.25] | 0.58 | - | 0.92 | 12 | 9/12 | 0.146 | 0.301 | - | exploratory |
| A2 vs A | cycles (u+k) / req | primary | -0.13% [-0.47, +0.22] | 0.34 | - | 0.54 | 12 | 7/12 | 0.774 | 0.622 | 0.425 | not resolved |
| A2 vs A | p50 latency (us) | exploratory | -0.34% [-0.73, +0.06] | 0.40 | - | 0.63 | 12 | 9/12 | 0.146 | 0.092 | - | exploratory |
| A2 vs A | p99 latency (us) | exploratory | +0.06% [-0.60, +0.73] | 0.67 | - | 1.05 | 12 | 6/12 | 1.000 | 0.850 | - | exploratory |

## Validity

50 legs run, 49 valid; 2 legs superseded by a re-run of their round.
- r11-tls-ka-A2 (superseded): client pending total 1043 above 1024 (queue absorbed a burst)

## A/A self-test: PASS

Rule: no Holm-significant difference and 95% half-width within the limit on every check.

| Shape | metric | effect [95% CI] | hw | limit | pair SD | 80%-power bias | n | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|---|
| tls-ka | instructions_u | +0.04% [-0.02, +0.11] | 0.07 | 0.50 | 0.10 | 0.09% | 12 | 0.559 | ok |
| tls-ka | cycles_total | +1.08% [+0.26, +1.91] | 0.82 | 1.00 | 1.29 | 1.14% | 12 | 0.059 | ok |
| tls-hs-st | instructions_u | +0.01% [-0.03, +0.05] | 0.04 | 0.50 | 0.06 | 0.05% | 12 | 0.851 | ok |
| tls-hs-st | cycles_total | -0.13% [-0.47, +0.22] | 0.34 | 1.00 | 0.54 | 0.48% | 12 | 0.851 | ok |

