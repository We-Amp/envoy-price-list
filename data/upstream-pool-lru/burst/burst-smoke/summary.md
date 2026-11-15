# lru-burst-smoke

- Harness: 0.1.0 0e1f33a83e3f
- Window: 2026-11-15T07:02:23Z to 2026-11-15T07:11:42Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off, default idle states; Envoy on 4 cores with their SMT siblings left idle
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz, one sample at start) 1676500,2300000
- Idle states (SUT CPUs and their SMT siblings, 0-7,40-47): intel_idle/menu; disabled: C3; per state: POLL 0us on, C1 2us on, C1E 10us on, C3 40us off, C6 133us on; unchanged at the end: True
- Client: Nighthawk 0.3.0, md5 `310df412f0907e3df4ad5530872b1e84`, commit not recorded (not found in --version; the md5 identifies the build)
- CPU sets: client 20-31,60-71, hop2 4-7, origin 32-39,72-79, sut 0-3
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True, extra args --prefetch-connections --max-pending-requests 1000 --experimental-h1-connection-reuse-strategy lru --rate-limiter-plugin-config {"name":"nighthawk.linear-ramping-rate-limiter-plugin","typed_config":{"@type":"type.googleapis.com/nighthawk.rate_limiter.LinearRampingRateLimiterConfig","ramp_time":"2s"}}; warm-up 5s, run 55s, perf window 40s after 12s lead-in
- Rounds: 2 done (minimum 2, blocks of 2, cap 2, adaptive False), order abba; stop: fixed rounds
- Headline: mean of per-round log ratios (arm/reference) with a two-sided 95% t interval. Primary metric cycles_total_all, Holm across 0 primary rows at alpha 0.05; every other metric is exploratory (interval only, no multiplicity control).
- Kernel cycles are measured on loopback: the receive path of a packet runs in the sender's context, so cycles:k compares arms but is not what a deployment behind a NIC pays.

| Arm | Version | md5 |
|---|---|---|
| mru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |
| lru | patched-build/1.40.2/Clean/RELEASE/BoringSSL | `ce35a0841952b5c439a254dc6c8b7b6f` |

## s-lo (`/s`, proxied, 5200 rps)

Medians over valid legs; per-leg CV of total cycles in brackets.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| mru | 0/2 | - | - | - | - (-) | - | - | - |
| lru | 1/2 | 163.7k | 340.4k | 166.8k | 507.2k (-) | 680 | 1070 | 29.8% |

Effect = mean paired log ratio as a percent change, [95% interval]. hw = interval half-width (log-%); A/A hw = the same in the reference A/A, where given. A difference whose size is within the A/A half-width is marked "inside the A/A floor"; one within the far end of the A/A interval, "inside the A/A interval": the A/A could not exclude a harness bias that large, so such a row needs support from other rows to count.

| Comparison | metric | role | effect [95% CI] | hw | A/A hw | pair SD | n | won | sign p | Wilcoxon p | Holm p | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Validity

8 legs run, 1 valid; 4 legs superseded by a re-run of their round.
- r01-s-lo-mru (superseded): client overflow/pool-exhausted counters 127 (upstream_cx_overflow=127); client pending total 93 above 16 (queue absorbed a burst)
- r01-s-lo-lru (superseded): client overflow/pool-exhausted counters 120 (upstream_cx_overflow=120); client pending total 85 above 16 (queue absorbed a burst)
- r02-s-lo-lru (superseded): client overflow/pool-exhausted counters 81 (upstream_cx_overflow=81); client pending total 67 above 16 (queue absorbed a burst)
- r02-s-lo-mru (superseded): client overflow/pool-exhausted counters 33 (upstream_cx_overflow=33); client pending total 41 above 16 (queue absorbed a burst)
- r01-s-lo-mru.rr1: client overflow/pool-exhausted counters 12 (upstream_cx_overflow=12); client pending total 28 above 16 (queue absorbed a burst)
- r02-s-lo-lru.rr1: client overflow/pool-exhausted counters 99 (upstream_cx_overflow=99); client pending total 78 above 16 (queue absorbed a burst)
- r02-s-lo-mru.rr1: client overflow/pool-exhausted counters 9 (upstream_cx_overflow=9); client pending total 23 above 16 (queue absorbed a burst)

