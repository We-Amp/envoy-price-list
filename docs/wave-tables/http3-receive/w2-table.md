# wave 8 W8-2: cycles (user+kernel) of the Envoy process per request; shape s pooled over two Williams squares; s-hi run: none

confirmatory rows in the Holm family: 2 (C1, C2)

## shape s (s-1 + s-2)

- s-1: 36 current legs, 36 valid, evidence failing 0, rounds complete 6, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-24T14:08:15Z, finished 2026-11-24T14:42:39Z
- s-2: 36 current legs, 36 valid, evidence failing 0, rounds complete 6, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-24T14:42:40Z, finished 2026-11-24T15:09:28Z
- target rate [2000] req/s; legs replaced by the harness (superseded): 24; rounds pooled: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

| arm | valid legs | cycles u+k /req (median) | user /req | kernel /req | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs (median of legs) | latency max µs (median / largest leg) | legs with max over 25 ms | Envoy busy (CPUs of 4) | busiest worker share (median / max) | UDP datagrams /req, box-wide (min to max) | Envoy datagrams dropped (sum) | kernel UdpInErrors / RcvbufErrors / SndbufErrors (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2tls | 12/12 | 738.9k | 513.2k | 225.0k | 200.4k | 75.7k | 2.03 | 505 | 692 | 1264 / 1370 | 0 | 0.701 | 0.259 / 0.279 | 0.0000 to 0.0000 | 0 | 0 / 0 / 0 |
| h3-official | 12/12 | 1279.9k | 944.5k | 340.0k | 504.8k | 130.8k | 2.59 | 568 | 736 | 4076 / 8172 | 0 | 1.163 | 0.356 / 0.416 | 7.0163 to 7.0167 | 0 | 0 / 0 / 0 |
| h3-official-A2 | 12/12 | 1291.9k | 951.4k | 343.2k | 505.5k | 130.6k | 2.54 | 575 | 738 | 5188 / 14590 | 0 | 1.174 | 0.356 / 0.461 | 7.0163 to 7.0167 | 0 | 0 / 0 / 0 |
| h3-off | 12/12 | 1299.4k | 957.4k | 342.0k | 515.2k | 131.0k | 2.58 | 565 | 743 | 4514 / 23177 | 0 | 1.180 | 0.360 / 0.463 | 7.0163 to 7.0166 | 0 | 0 / 0 / 0 |
| h3-stop-on | 12/12 | 1230.0k | 901.4k | 328.6k | 446.8k | 128.9k | 2.58 | 546 | 713 | 6736 / 18323 | 0 | 1.121 | 0.359 / 0.416 | 7.0164 to 7.0166 | 0 | 0 / 0 / 0 |
| h3-both-on | 12/12 | 1177.9k | 848.6k | 329.8k | 390.9k | 129.2k | 2.67 | 529 | 695 | 7209 / 26452 | 1 | 1.075 | 0.404 / 0.472 | 7.0163 to 7.0167 | 0 | 0 / 0 / 0 |

| row (same-build check, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3-official-A2 vs h3-official | +0.39 | [-1.47, +2.29] | +0.39 | ±1.88 / ±1.80 (t) | 8/12 | 0.66 | - | +5.2k ± 24.2k |

same-build check on s: PASS (effect +0.39 log points against the floor 2.0; quoted interval [-1.48, +2.27] log points includes 0); reach 2.27% (simple)

| row (build control (expected zero), cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3-off vs h3-official | +0.44 | [-1.58, +2.51] | +0.44 | ±2.03 / ±1.93 (t) | 7/12 | 0.64 | - | +5.9k ± 26.3k |

build control on s: h3-off vs h3-official +0.44% [-1.58, +2.51] simple. Fixed rule (+1.0% or more with an interval that excludes 0): not met: the in-binary figure is the headline. User instructions per request: h3-off 515152, h3-official 504759 (+1.22% [+0.07, +2.39])

ANCHOR GATE (h3-official vs h2tls on s, simple %): +74.6% [+71.4, +77.8]: INSIDE the band [+65, +85] (published +74.8; S2 +77.6)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| C1: h3-both-on vs h3-off | -8.04 | [-10.24, -5.78] | -8.38 | ±2.42 / ±2.26 (t) | 0/12 | 1e-05 | 2.1e-05 | -103.7k ± 30.0k | finding; basis: Measured
  beside C1, against the stock release [Exploratory]: h3-both-on vs h3-official -7.63% [-9.77, -5.43] simple (12 rounds)
  user instructions per request [Exploratory]: -23.76% [-24.53, -22.97] simple; paired difference -121.8k ± 4.4k
| C2: h3-stop-on vs h3-off | -4.19 | [-6.32, -2.01] | -4.28 | ±2.25 / ±2.11 (t) | 2/12 | 0.0015 | 0.0015 | -54.1k ± 28.5k | finding; basis: Measured
  beside C2, against the stock release [Exploratory]: h3-stop-on vs h3-official -3.76% [-5.29, -2.21] simple (12 rounds)
  user instructions per request [Exploratory]: -12.73% [-13.78, -11.67] simple; paired difference -65.3k ± 5.6k

LINE C1 (h3-both-on vs h3-off on s, simple %): -8.04% [-10.24, -5.78]: saves 3.0% or more. Basis: Measured

LINE C2 (h3-stop-on vs h3-off on s, simple %): -4.19% [-6.32, -2.01]: saves 3.0% or more (AT THE LINE: the quoted interval straddles -3.0). Basis: Measured

VERDICT on s by the fixed lines: WORTH PROPOSING (C1 saves 3.0% or more); C2 alone saves 3.0% or more: commit 1 can be proposed alone, commit 2 is a further step

MARKER in the scored legs (user instructions per request, lowest to highest leg): h3-off 496180 to 520668; h3-stop-on 441444 to 452842; h3-both-on 389263 to 391661. Ranges apart: stop-on below off YES; both-on below stop-on YES

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3-both-on vs h3-official | -7.63 | [-9.77, -5.43] | -7.94 | ±2.35 / ±2.20 (t) | 0/12 | 1.3e-05 | - | -97.8k ± 28.9k |
| h3-stop-on vs h3-official | -3.76 | [-5.29, -2.21] | -3.84 | ±1.60 / ±1.57 (t) | 0/12 | 0.00026 | - | -48.2k ± 20.0k |
| h3-both-on vs h3-stop-on | -4.02 | [-6.14, -1.84] | -4.10 | ±2.24 / ±2.10 (t) | 1/12 | 0.002 | - | -49.6k ± 27.3k |
| h3-off vs h3-official-A2 | +0.05 | [-2.29, +2.45] | +0.05 | ±2.37 / ±2.21 (t) | 7/12 | 0.96 | - | +0.8k ± 30.5k |
| h3-both-on vs h2tls | +61.27 | [+58.34, +64.25] | +47.79 | ±1.83 / ±1.76 (t) | 12/12 | 5.6e-15 | - | +451.3k ± 20.7k |

share of the HTTP/3 premium over h2tls removed [Exploratory], both guards (h3-off minus h3-both-on) over (h3-official minus h2tls), cycles per request, per round: 18.9% [13.3, 24.4] (t interval, 12 rounds)

share of the HTTP/3 premium over h2tls removed [Exploratory], stop guard (h3-off minus h3-stop-on) over (h3-official minus h2tls), cycles per request, per round: 10.0% [4.9, 15.1] (t interval, 12 rounds)

cycles per request against the busiest worker's share [Exploratory; no row is adjusted]: -3.47% per 0.1 of share over 60 legs of the five HTTP/3 arms (share 0.299 to 0.472)

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3-both-on [cycles_u] vs h3-off | -9.74 | [-11.83, -7.61] | -10.25 | ±2.33 / ±2.18 (t) | 0/12 | 1e-06 | - | -92.5k ± 21.2k |
| h3-both-on [cycles_k] vs h3-off | -3.30 | [-6.01, -0.51] | -3.36 | ±2.84 / ±2.62 (t) | 2/12 | 0.025 | - | -11.2k ± 9.6k |
| h3-both-on [instructions_u] vs h3-off | -23.76 | [-24.53, -22.97] | -27.12 | ±0.87 / ±1.02 (widened) | 0/12 | 8.9e-16 | - | -121.8k ± 4.4k |
| h3-both-on [instructions_k] vs h3-off | -1.91 | [-3.28, -0.52] | -1.93 | ±1.39 / ±1.40 (widened) | 2/12 | 0.011 | - | -2.5k ± 1.8k |
| h3-both-on [context_switches] vs h3-off | +2.71 | [-4.50, +10.47] | +2.67 | ±7.28 / ±6.52 (t) | 6/12 | 0.44 | - | +0.0k ± 0.0k |
| h3-both-on [p50_us] vs h3-off | -6.04 | [-7.94, -4.10] | -6.23 | ±2.05 / ±1.94 (t) | 0/12 | 3.4e-05 | - | -0.0k ± 0.0k |
| h3-both-on [p99_us] vs h3-off | -5.49 | [-7.41, -3.53] | -5.65 | ±2.05 / ±1.94 (t) | 0/12 | 8.1e-05 | - | -0.0k ± 0.0k |
| h3-stop-on [cycles_u] vs h3-off | -4.67 | [-6.83, -2.47] | -4.78 | ±2.29 / ±2.14 (t) | 1/12 | 0.00076 | - | -44.4k ± 21.3k |
| h3-stop-on [cycles_k] vs h3-off | -2.85 | [-5.11, -0.53] | -2.89 | ±2.36 / ±2.20 (t) | 2/12 | 0.021 | - | -9.7k ± 7.9k |
| h3-stop-on [instructions_u] vs h3-off | -12.73 | [-13.78, -11.67] | -13.62 | ±1.14 / ±1.21 (widened) | 0/12 | 2.8e-11 | - | -65.3k ± 5.6k |
| h3-stop-on [instructions_k] vs h3-off | -1.78 | [-2.78, -0.78] | -1.80 | ±0.86 / ±1.01 (widened) | 0/12 | 0.00075 | - | -2.3k ± 1.1k |
| h3-stop-on [context_switches] vs h3-off | +1.56 | [-4.22, +7.70] | +1.55 | ±5.86 / ±5.26 (t) | 5/12 | 0.57 | - | +0.0k ± 0.0k |
| h3-stop-on [p50_us] vs h3-off | -2.35 | [-4.25, -0.42] | -2.38 | ±1.96 / ±1.87 (t) | 3/12 | 0.021 | - | -0.0k ± 0.0k |
| h3-stop-on [p99_us] vs h3-off | -2.54 | [-6.19, +1.26] | -2.57 | ±3.82 / ±3.46 (t) | 4/12 | 0.17 | - | -0.0k ± 0.0k |
| h3-off [cycles_u] vs h3-official | +0.50 | [-1.56, +2.60] | +0.50 | ±2.07 / ±1.96 (t) | 7/12 | 0.61 | - | +4.9k ± 19.6k |
| h3-off [cycles_k] vs h3-official | +0.29 | [-1.83, +2.45] | +0.29 | ±2.13 / ±2.01 (t) | 6/12 | 0.77 | - | +1.0k ± 7.3k |
| h3-off [instructions_u] vs h3-official | +1.22 | [+0.07, +2.39] | +1.22 | ±1.05 / ±1.15 (widened) | 8/12 | 0.027 | - | +6.2k ± 5.3k |
| h3-off [instructions_k] vs h3-official | +0.40 | [-0.77, +1.59] | +0.40 | ±1.09 / ±1.18 (widened) | 7/12 | 0.43 | - | +0.5k ± 1.4k |
| h3-off [context_switches] vs h3-official | -1.98 | [-7.82, +4.23] | -2.00 | ±6.14 / ±5.51 (t) | 6/12 | 0.49 | - | -0.0k ± 0.0k |
| h3-off [p50_us] vs h3-official | +0.09 | [-1.84, +2.06] | +0.09 | ±1.94 / ±1.86 (t) | 6/12 | 0.92 | - | +0.0k ± 0.0k |
| h3-off [p99_us] vs h3-official | +0.87 | [-1.51, +3.32] | +0.87 | ±2.39 / ±2.23 (t) | 7/12 | 0.44 | - | +0.0k ± 0.0k |
| h3-official-A2 [cycles_u] vs h3-official | +0.49 | [-1.38, +2.40] | +0.49 | ±1.88 / ±1.80 (t) | 8/12 | 0.58 | - | +4.7k ± 17.8k |
| h3-official-A2 [cycles_k] vs h3-official | +0.12 | [-1.91, +2.19] | +0.12 | ±2.04 / ±1.94 (t) | 7/12 | 0.9 | - | +0.5k ± 7.0k |
| h3-official-A2 [instructions_u] vs h3-official | +0.19 | [-0.70, +1.08] | +0.19 | ±0.66 / ±0.89 (widened) | 7/12 | 0.55 | - | +1.0k ± 3.4k |
| h3-official-A2 [instructions_k] vs h3-official | -0.34 | [-1.30, +0.64] | -0.34 | ±0.80 / ±0.98 (widened) | 4/12 | 0.37 | - | -0.4k ± 1.0k |
| h3-official-A2 [context_switches] vs h3-official | -1.96 | [-5.07, +1.26] | -1.98 | ±3.23 / ±2.95 (t) | 4/12 | 0.2 | - | -0.0k ± 0.0k |
| h3-official-A2 [p50_us] vs h3-official | +1.87 | [+0.02, +3.76] | +1.86 | ±1.84 / ±1.77 (t) | 10/12 | 0.048 | - | +0.0k ± 0.0k |
| h3-official-A2 [p99_us] vs h3-official | +1.82 | [+0.04, +3.63] | +1.80 | ±1.76 / ±1.71 (t) | 8/12 | 0.046 | - | +0.0k ± 0.0k |

| row (per run (one Williams square each), exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| s-1: h3-both-on vs h3-off | -7.72 | [-11.43, -3.86] | -8.04 | ±4.10 / ±3.20 (t) | 0/6 | 0.004 | - | -99.4k ± 51.4k |
| s-1: h3-stop-on vs h3-off | -3.29 | [-6.78, +0.33] | -3.35 | ±3.68 / ±2.88 (t) | 1/6 | 0.066 | - | -42.2k ± 46.9k |
| s-1: h3-off vs h3-official | -0.12 | [-4.02, +3.93] | -0.12 | ±3.98 / ±3.11 (t) | 3/6 | 0.94 | - | -1.5k ± 51.4k |
| s-1: h3-official-A2 vs h3-official | -0.68 | [-3.42, +2.15] | -0.68 | ±2.80 / ±2.24 (t) | 3/6 | 0.56 | - | -8.7k ± 35.6k |
| s-1: h3-official vs h2tls | +74.82 | [+67.78, +82.16] | +55.86 | ±4.11 / ±3.20 (t) | 6/6 | 3.6e-07 | - | +550.6k ± 41.9k |
| s-2: h3-both-on vs h3-off | -8.35 | [-12.16, -4.37] | -8.72 | ±4.25 / ±3.31 (t) | 0/6 | 0.0033 | - | -108.1k ± 52.2k |
| s-2: h3-stop-on vs h3-off | -5.08 | [-8.64, -1.38] | -5.21 | ±3.82 / ±2.99 (t) | 1/6 | 0.017 | - | -66.0k ± 48.1k |
| s-2: h3-off vs h3-official | +1.01 | [-1.83, +3.94] | +1.01 | ±2.85 / ±2.28 (t) | 4/6 | 0.41 | - | +13.3k ± 36.9k |
| s-2: h3-official-A2 vs h3-official | +1.47 | [-1.72, +4.77] | +1.46 | ±3.20 / ±2.53 (t) | 5/6 | 0.29 | - | +19.0k ± 41.8k |
| s-2: h3-official vs h2tls | +74.35 | [+71.11, +77.66] | +55.59 | ±1.88 / ±1.58 (t) | 6/6 | 7.4e-09 | - | +547.6k ± 20.8k |

per-round log points (arm vs ref), for the reviewer:
- h3-official-A2 vs h3-official: +0.94 +0.16 -0.57 -2.56 +2.76 -4.80 -2.58 +6.49 +0.24 +0.06 +2.23 +2.31
- h3-off vs h3-official: -2.35 +3.11 -0.87 -5.90 +4.54 +0.73 +0.26 -1.62 +1.77 -2.26 +3.28 +4.63
- h3-official vs h2tls: +54.38 +56.13 +52.74 +61.67 +51.27 +58.99 +58.88 +54.11 +56.23 +55.41 +54.44 +54.47
- h3-both-on vs h3-off: -5.19 -13.52 -2.61 -7.90 -10.98 -8.02 -10.93 -1.55 -10.96 -9.80 -12.56 -6.51
- h3-stop-on vs h3-off: -3.26 -4.96 -3.45 +3.29 -6.87 -4.82 -9.75 +0.10 -3.74 -3.75 -8.87 -5.25

## shape s-hi (not run)

- no legs
