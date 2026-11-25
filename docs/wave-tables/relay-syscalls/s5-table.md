# wave 7 S5: cycles (user+kernel) of the Envoy process per request; pooled Williams squares per shape

confirmatory rows in the Holm family: 4

## shape p64 (relay-1 + relay-2; unit of the price: one relayed message)

- relay-1: 36 current legs, 36 valid, evidence failing 0, rounds complete 6, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-23T22:13:07Z, finished 2026-11-23T22:36:29Z
- relay-2: 36 current legs, 36 valid, evidence failing 0, rounds complete 6, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-23T22:59:52Z, finished 2026-11-23T23:23:14Z
- legs replaced by the harness (superseded): 0; rounds pooled: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

| arm | valid legs | cycles u+k /req (median) | per relayed message | user /req | kernel /req | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official | 12/12 | 148.1k | 74.1k | 34.8k | 113.4k | 22.5k | 68.6k | 1.84 | 192 | 302 | 0.633 | 8000.0–8000.0 | 0.258 |
| official-A2 | 12/12 | 150.9k | 75.4k | 35.4k | 115.3k | 22.5k | 68.7k | 1.83 | 192 | 301 | 0.639 | 8000.0–8000.0 | 0.258 |
| patched-off | 12/12 | 150.0k | 75.0k | 34.8k | 115.5k | 22.7k | 68.7k | 1.84 | 193 | 301 | 0.637 | 8000.0–8000.0 | 0.258 |
| read-only | 12/12 | 139.3k | 69.7k | 30.2k | 108.9k | 18.7k | 64.9k | 1.85 | 188 | 298 | 0.600 | 8000.0–8000.0 | 0.258 |
| write-only | 12/12 | 147.5k | 73.7k | 33.2k | 114.2k | 19.9k | 67.4k | 1.81 | 191 | 300 | 0.627 | 8000.0–8000.0 | 0.257 |
| both-on | 12/12 | 132.9k | 66.4k | 27.1k | 105.5k | 15.9k | 64.0k | 1.84 | 185 | 293 | 0.579 | 8000.0–8000.0 | 0.258 |

| row (same-build check, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| official-A2 vs official | +1.15 | [-0.47, +2.80] | +1.14 | ±1.62 / ±1.59 (t) | 8/12 | 0.15 | - | +1.7k ± 2.4k |

same-build check on p64: FAIL (effect +1.14 log points against the floor 1.0; quoted interval [-0.48, +2.76] log points includes 0); reach 2.78% (simple)

| row (build control (expected zero), cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| patched-off vs official | +1.68 | [-0.39, +3.79] | +1.67 | ±2.06 / ±1.95 (t) | 8/12 | 0.1 | - | +2.5k ± 3.1k |

build control on p64: patched-off DOES NOT read as official (+1.68% [-0.39, +3.79] simple; +1.3k ± 1.5k cycles per relayed message)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| both-on vs patched-off | -12.46 | [-13.81, -11.10] | -13.31 | ±1.55 / ±1.53 (t) | 0/12 | 9.8e-10 | 3.9e-09 | -18.9k ± 2.4k | finding; -9.44k ± 1.18k cycles per relayed message; basis: Measured (same-build check missed its floor; the effect is at least 3 x its excursion)
| read-only vs patched-off | -8.02 | [-10.05, -5.95] | -8.36 | ±2.23 / ±2.09 (t) | 0/12 | 4.8e-06 | 9.6e-06 | -12.2k ± 3.3k | finding; -6.08k ± 1.65k cycles per relayed message; basis: Measured (same-build check missed its floor; the effect is at least 3 x its excursion)
| write-only vs patched-off | -2.90 | [-5.19, -0.55] | -2.94 | ±2.39 / ±2.23 (t) | 2/12 | 0.02 | 0.02 | -4.4k ± 3.6k | finding; -2.20k ± 1.80k cycles per relayed message; basis: Not resolved (same-build check missed its floor; the effect is under 3 x its excursion)

LINE (relay, both-on vs patched-off, simple %, cycles per relayed message): -12.46% [-13.81, -11.10]: saves 3% or more: WORTH A PATCH by the line. Against S1's prediction: LARGER than the predicted 7 to 11% (the quoted interval does not overlap the predicted range). Basis: Measured (same-build check missed its floor; the effect is at least 3 x its excursion)

per-guard split [the two rows are confirmatory; their sum is Exploratory], cycles per relayed message: read-only -6.08k, write-only -2.20k, sum -8.28k; both-on -9.44k (both-on minus the sum -1.16k)

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| both-on vs official | -10.99 | [-12.30, -9.67] | -11.65 | ±1.48 / ±1.48 (t) | 0/12 | 2.4e-09 | - | -16.4k ± 2.1k |
| read-only vs official | -6.48 | [-7.80, -5.14] | -6.70 | ±1.42 / ±1.43 (widened) | 0/12 | 4.9e-07 | - | -9.6k ± 2.0k |
| write-only vs official | -1.27 | [-3.11, +0.61] | -1.28 | ±1.89 / ±1.81 (t) | 4/12 | 0.16 | - | -1.9k ± 2.8k |
| both-on vs read-only | -4.83 | [-6.44, -3.19] | -4.95 | ±1.71 / ±1.66 (t) | 0/12 | 5.2e-05 | - | -6.7k ± 2.3k |
| both-on vs write-only | -9.85 | [-11.16, -8.53] | -10.37 | ±1.46 / ±1.46 (widened) | 0/12 | 7.2e-09 | - | -14.5k ± 2.1k |
| patched-off vs official-A2 | +0.53 | [-1.96, +3.07] | +0.52 | ±2.50 / ±2.33 (t) | 6/12 | 0.65 | - | +0.8k ± 3.8k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| both-on [cycles_u] vs patched-off | -22.95 | [-24.28, -21.60] | -26.07 | ±1.74 / ±1.69 (t) | 0/12 | 2.4e-12 | - | -8.1k ± 0.7k |
| both-on [cycles_k] vs patched-off | -9.27 | [-10.65, -7.87] | -9.73 | ±1.53 / ±1.52 (t) | 0/12 | 2.4e-08 | - | -10.8k ± 1.8k |
| both-on [instructions_u] vs patched-off | -29.79 | [-30.25, -29.31] | -35.36 | ±0.07 / ±0.67 (widened) | 0/12 | 0 | - | -6.7k ± 0.0k |
| both-on [instructions_k] vs patched-off | -6.91 | [-7.60, -6.22] | -7.16 | ±0.36 / ±0.74 (widened) | 0/12 | 1e-13 | - | -4.7k ± 0.2k |
| both-on [context_switches] vs patched-off | +0.60 | [-0.64, +1.85] | +0.59 | ±1.17 / ±1.24 (widened) | 6/12 | 0.29 | - | +0.0k ± 0.0k |
| both-on [p50_us] vs patched-off | -4.15 | [-5.19, -3.10] | -4.24 | ±0.97 / ±1.09 (widened) | 0/12 | 1.1e-06 | - | -0.0k ± 0.0k |
| both-on [p99_us] vs patched-off | -2.55 | [-3.70, -1.39] | -2.58 | ±1.10 / ±1.19 (widened) | 1/12 | 0.00031 | - | -0.0k ± 0.0k |
| read-only [cycles_u] vs patched-off | -14.21 | [-17.20, -11.12] | -15.33 | ±3.54 / ±3.22 (t) | 0/12 | 1.2e-06 | - | -5.0k ± 1.2k |
| read-only [cycles_k] vs patched-off | -6.14 | [-7.91, -4.33] | -6.33 | ±1.91 / ±1.83 (t) | 0/12 | 1.6e-05 | - | -7.1k ± 2.2k |
| read-only [instructions_u] vs patched-off | -17.44 | [-17.99, -16.88] | -19.16 | ±0.08 / ±0.67 (widened) | 0/12 | 0 | - | -4.0k ± 0.0k |
| read-only [instructions_k] vs patched-off | -5.34 | [-6.01, -4.67] | -5.49 | ±0.26 / ±0.71 (widened) | 0/12 | 5.5e-14 | - | -3.7k ± 0.2k |
| read-only [context_switches] vs patched-off | +1.16 | [-0.10, +2.44] | +1.16 | ±1.20 / ±1.26 (widened) | 9/12 | 0.057 | - | +0.0k ± 0.0k |
| read-only [p50_us] vs patched-off | -2.67 | [-4.09, -1.22] | -2.70 | ±1.48 / ±1.47 (t) | 1/12 | 0.002 | - | -0.0k ± 0.0k |
| read-only [p99_us] vs patched-off | -0.99 | [-2.82, +0.87] | -1.00 | ±1.86 / ±1.79 (t) | 4/12 | 0.26 | - | -0.0k ± 0.0k |
| write-only [cycles_u] vs patched-off | -5.96 | [-9.37, -2.43] | -6.14 | ±3.69 / ±3.35 (t) | 2/12 | 0.0037 | - | -2.1k ± 1.3k |
| write-only [cycles_k] vs patched-off | -1.96 | [-3.96, +0.08] | -1.98 | ±2.06 / ±1.95 (t) | 2/12 | 0.058 | - | -2.3k ± 2.4k |
| write-only [instructions_u] vs patched-off | -12.27 | [-12.86, -11.68] | -13.09 | ±0.09 / ±0.67 (widened) | 0/12 | 0 | - | -2.8k ± 0.0k |
| write-only [instructions_k] vs patched-off | -1.68 | [-2.40, -0.95] | -1.69 | ±0.36 / ±0.74 (widened) | 0/12 | 4.9e-07 | - | -1.2k ± 0.2k |
| write-only [context_switches] vs patched-off | -0.79 | [-2.50, +0.95] | -0.79 | ±1.74 / ±1.69 (t) | 1/12 | 0.34 | - | -0.0k ± 0.0k |
| write-only [p50_us] vs patched-off | -1.07 | [-2.42, +0.29] | -1.08 | ±1.34 / ±1.37 (widened) | 5/12 | 0.1 | - | -0.0k ± 0.0k |
| write-only [p99_us] vs patched-off | +0.09 | [-1.28, +1.47] | +0.08 | ±1.34 / ±1.37 (widened) | 4/12 | 0.89 | - | +0.0k ± 0.0k |
| patched-off [cycles_u] vs official | +0.99 | [-2.41, +4.51] | +0.98 | ±3.42 / ±3.12 (t) | 6/12 | 0.54 | - | +0.3k ± 1.2k |
| patched-off [cycles_k] vs official | +1.89 | [+0.10, +3.72] | +1.87 | ±1.78 / ±1.72 (t) | 10/12 | 0.041 | - | +2.2k ± 2.1k |
| patched-off [instructions_u] vs official | +0.53 | [-0.14, +1.21] | +0.53 | ±0.09 / ±0.67 (widened) | 12/12 | 7.4e-08 | - | +0.1k ± 0.0k |
| patched-off [instructions_k] vs official | -0.05 | [-0.77, +0.67] | -0.05 | ±0.31 / ±0.72 (widened) | 6/12 | 0.73 | - | -0.0k ± 0.2k |
| patched-off [context_switches] vs official | -0.62 | [-1.91, +0.69] | -0.62 | ±1.26 / ±1.31 (widened) | 5/12 | 0.3 | - | -0.0k ± 0.0k |
| patched-off [p50_us] vs official | +0.47 | [-0.64, +1.60] | +0.47 | ±1.00 / ±1.11 (widened) | 7/12 | 0.32 | - | +0.0k ± 0.0k |
| patched-off [p99_us] vs official | -0.44 | [-1.80, +0.94] | -0.45 | ±1.35 / ±1.38 (widened) | 5/12 | 0.48 | - | -0.0k ± 0.0k |
| official-A2 [cycles_u] vs official | +0.76 | [-1.73, +3.32] | +0.76 | ±2.51 / ±2.33 (t) | 8/12 | 0.52 | - | +0.3k ± 0.9k |
| official-A2 [cycles_k] vs official | +1.27 | [-0.17, +2.73] | +1.26 | ±1.42 / ±1.43 (widened) | 8/12 | 0.076 | - | +1.5k ± 1.6k |
| official-A2 [instructions_u] vs official | -0.02 | [-0.69, +0.65] | -0.02 | ±0.05 / ±0.67 (widened) | 3/12 | 0.36 | - | -0.0k ± 0.0k |
| official-A2 [instructions_k] vs official | +0.04 | [-0.67, +0.74] | +0.04 | ±0.26 / ±0.71 (widened) | 6/12 | 0.77 | - | +0.0k ± 0.2k |
| official-A2 [context_switches] vs official | -0.55 | [-1.51, +0.41] | -0.55 | ±0.79 / ±0.97 (widened) | 3/12 | 0.15 | - | -0.0k ± 0.0k |
| official-A2 [p50_us] vs official | +0.01 | [-1.19, +1.23] | +0.01 | ±1.13 / ±1.21 (widened) | 5/12 | 0.99 | - | +0.0k ± 0.0k |
| official-A2 [p99_us] vs official | -0.04 | [-1.54, +1.49] | -0.04 | ±1.52 / ±1.51 (t) | 6/12 | 0.96 | - | -0.0k ± 0.0k |

| row (per run (one Williams square each), exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| relay-1: both-on vs patched-off | -11.25 | [-13.45, -8.98] | -11.93 | ±2.52 / ±2.03 (t) | 0/6 | 6.6e-05 | - | -16.9k ± 3.7k |
| relay-1: read-only vs patched-off | -6.64 | [-8.04, -5.21] | -6.87 | ±1.51 / ±1.33 (t) | 0/6 | 8.1e-05 | - | -10.0k ± 2.3k |
| relay-1: write-only vs patched-off | -1.52 | [-4.37, +1.41] | -1.53 | ±2.93 / ±2.33 (t) | 2/6 | 0.24 | - | -2.3k ± 4.3k |
| relay-1: patched-off vs official | +0.48 | [-3.13, +4.23] | +0.48 | ±3.66 / ±2.87 (t) | 3/6 | 0.75 | - | +0.7k ± 5.5k |
| relay-1: official-A2 vs official | +1.96 | [-0.99, +5.00] | +1.94 | ±2.94 / ±2.34 (t) | 4/6 | 0.15 | - | +2.9k ± 4.5k |
| relay-2: both-on vs patched-off | -13.66 | [-15.16, -12.15] | -14.69 | ±1.74 / ±1.49 (t) | 0/6 | 3.9e-06 | - | -20.9k ± 3.0k |
| relay-2: read-only vs patched-off | -9.39 | [-13.50, -5.07] | -9.86 | ±4.65 / ±3.61 (t) | 0/6 | 0.0028 | - | -14.4k ± 6.9k |
| relay-2: write-only vs patched-off | -4.26 | [-8.48, +0.17] | -4.35 | ±4.51 / ±3.51 (t) | 0/6 | 0.056 | - | -6.5k ± 6.9k |
| relay-2: patched-off vs official | +2.89 | [-0.03, +5.90] | +2.85 | ±2.88 / ±2.30 (t) | 5/6 | 0.052 | - | +4.3k ± 4.4k |
| relay-2: official-A2 vs official | +0.34 | [-1.96, +2.69] | +0.34 | ±2.31 / ±1.89 (t) | 4/6 | 0.72 | - | +0.5k ± 3.4k |

## shape s (http-1 + http-2; unit of the price: one request)

- http-1: 36 current legs, 36 valid, evidence failing 0, rounds complete 6, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-23T22:36:30Z, finished 2026-11-23T22:59:51Z
- http-2: 36 current legs, 36 valid, evidence failing 0, rounds complete 6, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-23T23:23:15Z, finished 2026-11-23T23:46:36Z
- legs replaced by the harness (superseded): 0; rounds pooled: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

| arm | valid legs | cycles u+k /req (median) | per request | user /req | kernel /req | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official | 12/12 | 523.7k | 523.7k | 344.8k | 178.6k | 163.9k | 71.4k | 1.58 | 400 | 623 | 1.247 | 5200.0–5200.0 | 0.255 |
| official-A2 | 12/12 | 522.3k | 522.3k | 344.0k | 178.8k | 163.8k | 71.4k | 1.59 | 399 | 623 | 1.247 | 5200.0–5200.0 | 0.255 |
| patched-off | 12/12 | 527.9k | 527.9k | 347.5k | 180.6k | 165.3k | 71.3k | 1.59 | 400 | 631 | 1.258 | 5200.0–5200.0 | 0.254 |
| read-only | 12/12 | 515.1k | 515.1k | 341.1k | 174.2k | 161.3k | 67.7k | 1.61 | 390 | 611 | 1.230 | 5200.0–5200.0 | 0.255 |
| write-only | 12/12 | 522.1k | 522.1k | 344.0k | 178.6k | 163.2k | 70.8k | 1.59 | 370 | 535 | 1.248 | 5200.0–5200.0 | 0.253 |
| both-on | 12/12 | 512.4k | 512.4k | 338.0k | 173.6k | 159.2k | 66.9k | 1.57 | 366 | 537 | 1.223 | 5200.0–5200.0 | 0.254 |

| row (same-build check, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| official-A2 vs official | -0.32 | [-1.21, +0.57] | -0.32 | ±0.67 / ±0.89 (widened) | 6/12 | 0.31 | - | -1.7k ± 3.5k |

same-build check on s: PASS (effect -0.32 log points against the floor 1.0; quoted interval [-1.22, +0.57] log points includes 0); reach 1.21% (simple)

| row (build control (expected zero), cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| patched-off vs official | +0.68 | [-0.23, +1.60] | +0.68 | ±0.70 / ±0.91 (widened) | 9/12 | 0.055 | - | +3.6k ± 3.7k |

build control on s: patched-off READS AS official (+0.68% [-0.23, +1.60] simple; +3.6k ± 3.7k cycles per request)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| both-on vs patched-off | -3.10 | [-3.87, -2.32] | -3.14 | ±0.50 / ±0.80 (widened) | 0/12 | 2.5e-08 | 7.6e-08 | -16.3k ± 2.6k | finding; -16.34k ± 2.58k cycles per request; basis: Measured

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| both-on vs official | -2.43 | [-3.29, -1.57] | -2.46 | ±0.64 / ±0.88 (widened) | 0/12 | 3.9e-06 | - | -12.8k ± 3.4k |
| read-only vs official | -1.83 | [-2.67, -0.98] | -1.85 | ±0.62 / ±0.86 (widened) | 0/12 | 3.9e-05 | - | -9.6k ± 3.2k |
| write-only vs official | -0.37 | [-1.41, +0.68] | -0.37 | ±0.91 / ±1.05 (widened) | 5/12 | 0.39 | - | -2.0k ± 4.8k |
| both-on vs read-only | -0.62 | [-1.44, +0.21] | -0.62 | ±0.56 / ±0.83 (widened) | 5/12 | 0.033 | - | -3.2k ± 2.9k |
| both-on vs write-only | -2.07 | [-2.90, -1.24] | -2.09 | ±0.58 / ±0.85 (widened) | 0/12 | 7.5e-06 | - | -10.8k ± 3.0k |
| patched-off vs official-A2 | +1.01 | [+0.24, +1.78] | +1.00 | ±0.42 / ±0.77 (widened) | 12/12 | 0.00029 | - | +5.3k ± 2.2k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| both-on [cycles_u] vs patched-off | -2.56 | [-3.29, -1.82] | -2.59 | ±0.40 / ±0.75 (widened) | 0/12 | 1.7e-08 | - | -8.9k ± 1.4k |
| both-on [cycles_k] vs patched-off | -4.12 | [-5.12, -3.12] | -4.21 | ±0.90 / ±1.04 (widened) | 0/12 | 5.7e-07 | - | -7.5k ± 1.6k |
| both-on [instructions_u] vs patched-off | -3.70 | [-4.34, -3.05] | -3.77 | ±0.05 / ±0.67 (widened) | 0/12 | 0 | - | -6.1k ± 0.1k |
| both-on [instructions_k] vs patched-off | -6.27 | [-6.98, -5.56] | -6.48 | ±0.41 / ±0.76 (widened) | 0/12 | 1.4e-12 | - | -4.5k ± 0.3k |
| both-on [context_switches] vs patched-off | -1.20 | [-3.49, +1.14] | -1.21 | ±2.34 / ±2.19 (t) | 5/12 | 0.28 | - | -0.0k ± 0.0k |
| both-on [p50_us] vs patched-off | -8.55 | [-10.06, -7.02] | -8.94 | ±1.67 / ±1.63 (t) | 0/12 | 1.4e-07 | - | -0.0k ± 0.0k |
| both-on [p99_us] vs patched-off | -15.45 | [-16.97, -13.89] | -16.78 | ±1.82 / ±1.75 (t) | 0/12 | 4.6e-10 | - | -0.1k ± 0.0k |
| patched-off [cycles_u] vs official | +0.60 | [-0.21, +1.43] | +0.60 | ±0.53 / ±0.82 (widened) | 9/12 | 0.03 | - | +2.1k ± 1.8k |
| patched-off [cycles_k] vs official | +0.83 | [-0.38, +2.06] | +0.83 | ±1.13 / ±1.21 (widened) | 8/12 | 0.13 | - | +1.5k ± 2.0k |
| patched-off [instructions_u] vs official | +0.88 | [+0.21, +1.55] | +0.87 | ±0.04 / ±0.67 (widened) | 12/12 | 9.9e-14 | - | +1.4k ± 0.1k |
| patched-off [instructions_k] vs official | -0.06 | [-0.86, +0.76] | -0.06 | ±0.52 / ±0.81 (widened) | 5/12 | 0.82 | - | -0.0k ± 0.4k |
| patched-off [context_switches] vs official | -0.33 | [-3.42, +2.86] | -0.33 | ±3.15 / ±2.88 (t) | 5/12 | 0.82 | - | -0.0k ± 0.0k |
| patched-off [p50_us] vs official | -0.15 | [-2.45, +2.20] | -0.15 | ±2.33 / ±2.18 (t) | 6/12 | 0.89 | - | -0.0k ± 0.0k |
| patched-off [p99_us] vs official | +1.26 | [-1.29, +3.87] | +1.25 | ±2.55 / ±2.37 (t) | 6/12 | 0.3 | - | +0.0k ± 0.0k |
| official-A2 [cycles_u] vs official | -0.33 | [-1.13, +0.47] | -0.33 | ±0.50 / ±0.80 (widened) | 4/12 | 0.18 | - | -1.1k ± 1.7k |
| official-A2 [cycles_k] vs official | -0.31 | [-1.47, +0.87] | -0.31 | ±1.08 / ±1.17 (widened) | 5/12 | 0.54 | - | -0.6k ± 1.9k |
| official-A2 [instructions_u] vs official | -0.01 | [-0.68, +0.66] | -0.01 | ±0.03 / ±0.67 (widened) | 4/12 | 0.47 | - | -0.0k ± 0.1k |
| official-A2 [instructions_k] vs official | +0.04 | [-0.67, +0.76] | +0.04 | ±0.29 / ±0.72 (widened) | 6/12 | 0.75 | - | +0.0k ± 0.2k |
| official-A2 [context_switches] vs official | +0.32 | [-1.74, +2.43] | +0.32 | ±2.08 / ±1.97 (t) | 6/12 | 0.74 | - | +0.0k ± 0.0k |
| official-A2 [p50_us] vs official | -0.36 | [-2.35, +1.67] | -0.36 | ±2.01 / ±1.91 (t) | 6/12 | 0.7 | - | -0.0k ± 0.0k |
| official-A2 [p99_us] vs official | -0.70 | [-2.63, +1.28] | -0.70 | ±1.97 / ±1.88 (t) | 6/12 | 0.45 | - | -0.0k ± 0.0k |

| row (per run (one Williams square each), exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| http-1: both-on vs patched-off | -3.20 | [-3.97, -2.43] | -3.26 | ±0.57 / ±0.80 (widened) | 0/6 | 2.7e-05 | - | -16.9k ± 2.9k |
| http-1: patched-off vs official | +0.43 | [-1.00, +1.89] | +0.43 | ±1.44 / ±1.28 (t) | 4/6 | 0.48 | - | +2.2k ± 7.6k |
| http-1: official-A2 vs official | -0.61 | [-1.89, +0.68] | -0.62 | ±1.29 / ±1.19 (t) | 2/6 | 0.28 | - | -3.3k ± 6.8k |
| http-2: both-on vs patched-off | -2.99 | [-4.01, -1.95] | -3.03 | ±1.06 / ±1.05 (t) | 0/6 | 0.00073 | - | -15.8k ± 5.5k |
| http-2: patched-off vs official | +0.93 | [+0.01, +1.86] | +0.93 | ±0.82 / ±0.91 (widened) | 5/6 | 0.034 | - | +4.9k ± 4.3k |
| http-2: official-A2 vs official | -0.03 | [-0.97, +0.91] | -0.03 | ±0.87 / ±0.94 (widened) | 4/6 | 0.93 | - | -0.2k ± 4.6k |
