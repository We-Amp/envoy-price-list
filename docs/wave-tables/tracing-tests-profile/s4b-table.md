# s4b-pgo: primary metric cycles_total (cycles user+kernel per request, Envoy process)

legs: 64 current, 64 valid; evidence failing: 0; superseded (replaced by the harness): 0; target rates: s [5200]/s, fh [8000]/s

shape order by round (as run): r1 fh then s; r2 s then fh; r3 fh then s; r4 s then fh; r5 fh then s; r6 s then fh; r7 fh then s; r8 s then fh

| arm | binary sha256 (as started) | md5 unchanged at the end | version |
|---|---|---|---|
| official | 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc | True | b2d89e0ae539 |
| official-A2 | 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc | True | b2d89e0ae539 |
| pgolto-tests | 7a47b051a37c4f9db0e2866c0125605e027b9b2c58563630afec046f493b8760 | True | b2d89e0ae539 |
| pgolto-trainer | d1b4f16e650345957eca97ef690adf149f19ae0ca1d4a1388d6154312270487d | True | b2d89e0ae539 |

## shape s

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official | 8/8 | 525.6k | 344.9k | 180.8k | 163.8k | 71.6k | 1.61 | 395 | 617 | 1.254 | 5200.0–5200.0 | 0.253 |
| official-A2 | 8/8 | 523.1k | 344.7k | 178.8k | 163.9k | 71.4k | 1.60 | 394 | 625 | 1.249 | 5200.0–5200.0 | 0.254 |
| pgolto-tests | 8/8 | 433.7k | 262.3k | 171.2k | 137.1k | 72.0k | 1.71 | 347 | 554 | 1.060 | 5200.0–5200.0 | 0.254 |
| pgolto-trainer | 8/8 | 316.8k | 154.4k | 162.5k | 119.9k | 72.9k | 1.86 | 265 | 440 | 0.804 | 5200.0–5200.0 | 0.255 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| official-A2 vs official | -0.36 | [-1.13, +0.41] | -0.36 | ±0.47 / ±0.77 (widened) | 3/8 | 0.11 | - | -1.9k ± 2.5k | PASS

A/A gate (shape s, floor 1.0 log points): **PASS**; A/A effect 0.36 log points; A/A reach 1.13% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer vs official | -39.56 | [-40.29, -38.82] | -50.35 | ±1.22 / ±1.21 (t) | 0/8 | 3.1e-12 | 1.8e-11 | -207.7k ± 3.7k | finding; basis: Measured
| pgolto-tests vs official | -17.26 | [-17.96, -16.56] | -18.95 | ±0.63 / ±0.84 (widened) | 0/8 | 2.7e-11 | 1.4e-10 | -90.6k ± 2.7k | finding; basis: Measured
| pgolto-tests vs pgolto-trainer | +36.90 | [+35.05, +38.77] | +31.41 | ±1.36 / ±1.31 (t) | 8/8 | 1.8e-10 | 7.1e-10 | +117.1k ± 4.6k | finding; basis: Measured

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer vs official-A2 | -39.34 | [-40.23, -38.44] | -49.99 | ±1.48 / ±1.39 (t) | 0/8 | 1.3e-11 | - | -205.9k ± 5.0k |
| pgolto-tests vs official-A2 | -16.96 | [-17.67, -16.25] | -18.59 | ±0.65 / ±0.86 (widened) | 0/8 | 4.1e-11 | - | -88.8k ± 2.9k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer [cycles_u] vs official | -55.23 | [-55.67, -54.78] | -80.36 | ±0.90 / ±1.00 (widened) | 0/8 | 1.4e-14 | - | -190.3k ± 0.9k |
| pgolto-trainer [cycles_k] vs official | -9.69 | [-11.27, -8.08] | -10.19 | ±1.76 / ±1.61 (t) | 0/8 | 2.7e-06 | - | -17.5k ± 2.9k |
| pgolto-trainer [instructions_u] vs official | -26.83 | [-27.32, -26.34] | -31.24 | ±0.09 / ±0.67 (widened) | 0/8 | 0 | - | -44.0k ± 0.1k |
| pgolto-trainer [instructions_k] vs official | +1.79 | [+1.06, +2.54] | +1.78 | ±0.35 / ±0.73 (widened) | 8/8 | 6.8e-06 | - | +1.3k ± 0.3k |
| pgolto-trainer [context_switches] vs official | +14.23 | [+12.26, +16.24] | +13.31 | ±1.74 / ±1.59 (t) | 8/8 | 4e-07 | - | +0.0k ± 0.0k |
| pgolto-trainer [p50_us] vs official | -32.50 | [-34.57, -30.37] | -39.31 | ±3.11 / ±2.66 (t) | 0/8 | 1.2e-08 | - | -0.1k ± 0.0k |
| pgolto-trainer [p99_us] vs official | -28.75 | [-30.55, -26.90] | -33.90 | ±2.56 / ±2.22 (t) | 0/8 | 8.7e-09 | - | -0.2k ± 0.0k |
| pgolto-tests [cycles_u] vs official | -23.69 | [-24.34, -23.05] | -27.04 | ±0.63 / ±0.85 (widened) | 0/8 | 2.3e-12 | - | -81.6k ± 1.8k |
| pgolto-tests [cycles_k] vs official | -4.99 | [-6.00, -3.97] | -5.12 | ±1.01 / ±1.07 (widened) | 0/8 | 6.3e-06 | - | -9.0k ± 1.7k |
| pgolto-tests [instructions_u] vs official | -16.35 | [-16.90, -15.79] | -17.85 | ±0.05 / ±0.67 (widened) | 0/8 | 0 | - | -26.8k ± 0.1k |
| pgolto-tests [instructions_k] vs official | +0.46 | [-0.30, +1.22] | +0.46 | ±0.43 / ±0.76 (widened) | 7/8 | 0.039 | - | +0.3k ± 0.3k |
| pgolto-tests [context_switches] vs official | +5.49 | [+3.26, +7.77] | +5.34 | ±2.14 / ±1.89 (t) | 8/8 | 0.00059 | - | +0.0k ± 0.0k |
| pgolto-tests [p50_us] vs official | -12.03 | [-12.80, -11.24] | -12.81 | ±0.71 / ±0.89 (widened) | 0/8 | 1e-09 | - | -0.0k ± 0.0k |
| pgolto-tests [p99_us] vs official | -10.92 | [-13.11, -8.68] | -11.57 | ±2.48 / ±2.16 (t) | 0/8 | 1.1e-05 | - | -0.1k ± 0.0k |
| pgolto-tests [cycles_u] vs pgolto-trainer | +70.44 | [+68.29, +72.61] | +53.32 | ±1.27 / ±1.24 (t) | 8/8 | 2.7e-12 | - | +108.6k ± 2.3k |
| pgolto-tests [cycles_k] vs pgolto-trainer | +5.20 | [+3.40, +7.03] | +5.07 | ±1.73 / ±1.58 (t) | 8/8 | 0.00022 | - | +8.5k ± 2.9k |
| pgolto-tests [instructions_u] vs pgolto-trainer | +14.33 | [+13.57, +15.10] | +13.39 | ±0.06 / ±0.67 (widened) | 8/8 | 0 | - | +17.2k ± 0.1k |
| pgolto-tests [instructions_k] vs pgolto-trainer | -1.31 | [-1.99, -0.62] | -1.32 | ±0.24 / ±0.69 (widened) | 0/8 | 3.5e-06 | - | -1.0k ± 0.2k |
| pgolto-tests [context_switches] vs pgolto-trainer | -7.66 | [-8.85, -6.45] | -7.97 | ±1.30 / ±1.27 (t) | 0/8 | 1.8e-06 | - | -0.0k ± 0.0k |
| pgolto-tests [p50_us] vs pgolto-trainer | +30.34 | [+26.09, +34.73] | +26.49 | ±3.31 / ±2.83 (t) | 8/8 | 2.9e-07 | - | +0.1k ± 0.0k |
| pgolto-tests [p99_us] vs pgolto-trainer | +25.02 | [+22.18, +27.93] | +22.33 | ±2.30 / ±2.02 (t) | 8/8 | 7.5e-08 | - | +0.1k ± 0.0k |
| official-A2 [cycles_u] vs official | +0.00 | [-0.83, +0.84] | +0.00 | ±0.61 / ±0.83 (widened) | 3/8 | 0.99 | - | +0.0k ± 2.1k |
| official-A2 [cycles_k] vs official | -1.05 | [-1.87, -0.24] | -1.06 | ±0.58 / ±0.82 (widened) | 0/8 | 0.0036 | - | -1.9k ± 1.0k |
| official-A2 [instructions_u] vs official | +0.01 | [-0.65, +0.68] | +0.01 | ±0.06 / ±0.67 (widened) | 5/8 | 0.66 | - | +0.0k ± 0.1k |
| official-A2 [instructions_k] vs official | -0.22 | [-0.98, +0.55] | -0.22 | ±0.46 / ±0.77 (widened) | 2/8 | 0.3 | - | -0.2k ± 0.3k |
| official-A2 [context_switches] vs official | -1.28 | [-4.10, +1.63] | -1.28 | ±2.90 / ±2.50 (t) | 2/8 | 0.33 | - | -0.0k ± 0.0k |
| official-A2 [p50_us] vs official | +0.32 | [-2.06, +2.77] | +0.32 | ±2.41 / ±2.10 (t) | 4/8 | 0.76 | - | +0.0k ± 0.0k |
| official-A2 [p99_us] vs official | +0.71 | [-2.17, +3.67] | +0.71 | ±2.90 / ±2.49 (t) | 5/8 | 0.58 | - | +0.0k ± 0.0k |

## shape fh

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official | 8/8 | 280.3k | 197.9k | 82.8k | 164.8k | 29.4k | 0.84 | 215 | 368 | 1.024 | 8000.0–8000.0 | 0.256 |
| official-A2 | 8/8 | 280.4k | 197.4k | 83.0k | 164.7k | 29.2k | 0.83 | 215 | 368 | 1.027 | 8000.0–8000.0 | 0.257 |
| pgolto-tests | 8/8 | 237.1k | 156.3k | 80.9k | 149.8k | 29.8k | 0.91 | 198 | 334 | 0.885 | 8000.0–8000.0 | 0.255 |
| pgolto-trainer | 8/8 | 185.1k | 106.7k | 78.0k | 125.5k | 30.2k | 0.96 | 175 | 301 | 0.712 | 8000.0–8000.0 | 0.255 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| official-A2 vs official | -0.18 | [-1.69, +1.36] | -0.18 | ±1.53 / ±1.43 (t) | 4/8 | 0.79 | - | -0.5k ± 4.3k | PASS

A/A gate (shape fh, floor 1.0 log points): **PASS**; A/A effect 0.18 log points; A/A reach 1.70% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer vs official | -34.40 | [-35.60, -33.18] | -42.16 | ±1.85 / ±1.67 (t) | 0/8 | 2e-10 | 7.1e-10 | -96.7k ± 4.2k | finding; basis: Measured
| pgolto-tests vs official | -15.65 | [-16.89, -14.39] | -17.02 | ±1.48 / ±1.40 (t) | 0/8 | 2.3e-08 | 2.3e-08 | -44.0k ± 3.9k | finding; basis: Measured
| pgolto-tests vs pgolto-trainer | +28.58 | [+26.77, +30.42] | +25.14 | ±1.42 / ±1.35 (t) | 8/8 | 1.2e-09 | 2.3e-09 | +52.7k ± 2.8k | finding; basis: Measured

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer vs official-A2 | -34.28 | [-35.20, -33.34] | -41.98 | ±1.41 / ±1.35 (t) | 0/8 | 3.1e-11 | - | -96.1k ± 3.0k |
| pgolto-tests vs official-A2 | -15.50 | [-16.39, -14.59] | -16.84 | ±1.00 / ±1.07 (widened) | 0/8 | 1.7e-09 | - | -43.5k ± 2.6k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer [cycles_u] vs official | -46.26 | [-47.14, -45.36] | -62.10 | ±1.66 / ±1.53 (t) | 0/8 | 6.2e-12 | - | -91.7k ± 2.6k |
| pgolto-trainer [cycles_k] vs official | -6.01 | [-7.98, -3.99] | -6.19 | ±2.12 / ±1.88 (t) | 0/8 | 0.00023 | - | -5.0k ± 1.7k |
| pgolto-trainer [instructions_u] vs official | -23.82 | [-24.33, -23.31] | -27.21 | ±0.00 / ±0.67 (widened) | 0/8 | 0 | - | -39.2k ± 0.0k |
| pgolto-trainer [instructions_k] vs official | +2.52 | [+1.45, +3.60] | +2.49 | ±0.97 / ±1.05 (widened) | 8/8 | 0.00052 | - | +0.7k ± 0.3k |
| pgolto-trainer [context_switches] vs official | +13.73 | [+12.10, +15.38] | +12.87 | ±1.44 / ±1.37 (t) | 8/8 | 1.4e-07 | - | +0.0k ± 0.0k |
| pgolto-trainer [p50_us] vs official | -18.60 | [-19.60, -17.59] | -20.58 | ±1.24 / ±1.22 (t) | 0/8 | 1.8e-09 | - | -0.0k ± 0.0k |
| pgolto-trainer [p99_us] vs official | -18.98 | [-20.24, -17.70] | -21.05 | ±1.57 / ±1.46 (t) | 0/8 | 8.1e-09 | - | -0.1k ± 0.0k |
| pgolto-tests [cycles_u] vs official | -21.12 | [-22.45, -19.76] | -23.72 | ±1.71 / ±1.56 (t) | 0/8 | 6.3e-09 | - | -41.9k ± 3.1k |
| pgolto-tests [cycles_k] vs official | -2.56 | [-3.68, -1.43] | -2.59 | ±1.14 / ±1.15 (widened) | 0/8 | 0.001 | - | -2.1k ± 0.9k |
| pgolto-tests [instructions_u] vs official | -9.09 | [-9.69, -8.48] | -9.53 | ±0.01 / ±0.67 (widened) | 0/8 | 0 | - | -15.0k ± 0.0k |
| pgolto-tests [instructions_k] vs official | +1.77 | [+0.75, +2.80] | +1.75 | ±0.90 / ±1.00 (widened) | 8/8 | 0.0025 | - | +0.5k ± 0.3k |
| pgolto-tests [context_switches] vs official | +8.16 | [+6.00, +10.36] | +7.84 | ±2.01 / ±1.80 (t) | 8/8 | 3.7e-05 | - | +0.0k ± 0.0k |
| pgolto-tests [p50_us] vs official | -8.47 | [-9.29, -7.64] | -8.85 | ±0.73 / ±0.90 (widened) | 0/8 | 1.6e-08 | - | -0.0k ± 0.0k |
| pgolto-tests [p99_us] vs official | -9.71 | [-10.68, -8.73] | -10.21 | ±1.02 / ±1.08 (widened) | 0/8 | 6.1e-08 | - | -0.0k ± 0.0k |
| pgolto-tests [cycles_u] vs pgolto-trainer | +46.79 | [+44.82, +48.78] | +38.38 | ±1.35 / ±1.30 (t) | 8/8 | 4.2e-11 | - | +49.8k ± 1.6k |
| pgolto-tests [cycles_k] vs pgolto-trainer | +3.67 | [+1.74, +5.64] | +3.60 | ±1.88 / ±1.70 (t) | 8/8 | 0.0027 | - | +2.9k ± 1.5k |
| pgolto-tests [instructions_u] vs pgolto-trainer | +19.34 | [+18.55, +20.14] | +17.68 | ±0.01 / ±0.67 (widened) | 8/8 | 0 | - | +24.3k ± 0.0k |
| pgolto-tests [instructions_k] vs pgolto-trainer | -0.73 | [-1.75, +0.30] | -0.73 | ±0.95 / ±1.03 (widened) | 2/8 | 0.11 | - | -0.2k ± 0.3k |
| pgolto-tests [context_switches] vs pgolto-trainer | -4.90 | [-6.79, -2.97] | -5.02 | ±2.01 / ±1.79 (t) | 0/8 | 0.00059 | - | -0.0k ± 0.0k |
| pgolto-tests [p50_us] vs pgolto-trainer | +12.45 | [+11.38, +13.54] | +11.73 | ±0.83 / ±0.96 (widened) | 8/8 | 5.7e-09 | - | +0.0k ± 0.0k |
| pgolto-tests [p99_us] vs pgolto-trainer | +11.44 | [+9.85, +13.05] | +10.83 | ±1.44 / ±1.37 (t) | 8/8 | 4.3e-07 | - | +0.0k ± 0.0k |
| official-A2 [cycles_u] vs official | -0.11 | [-1.84, +1.65] | -0.11 | ±1.75 / ±1.59 (t) | 4/8 | 0.88 | - | -0.2k ± 3.5k |
| official-A2 [cycles_k] vs official | -0.34 | [-1.51, +0.85] | -0.34 | ±1.18 / ±1.18 (widened) | 3/8 | 0.52 | - | -0.3k ± 1.0k |
| official-A2 [instructions_u] vs official | -0.01 | [-0.67, +0.66] | -0.01 | ±0.01 / ±0.67 (widened) | 3/8 | 0.11 | - | -0.0k ± 0.0k |
| official-A2 [instructions_k] vs official | -0.02 | [-0.93, +0.90] | -0.02 | ±0.76 / ±0.92 (widened) | 4/8 | 0.95 | - | -0.0k ± 0.2k |
| official-A2 [context_switches] vs official | -0.51 | [-2.81, +1.85] | -0.51 | ±2.34 / ±2.05 (t) | 4/8 | 0.62 | - | -0.0k ± 0.0k |
| official-A2 [p50_us] vs official | -0.14 | [-1.40, +1.13] | -0.14 | ±1.27 / ±1.24 (t) | 3/8 | 0.8 | - | -0.0k ± 0.0k |
| official-A2 [p99_us] vs official | +0.06 | [-1.13, +1.27] | +0.06 | ±1.20 / ±1.19 (t) | 4/8 | 0.9 | - | +0.0k ± 0.0k |

## candidate 2: kept share of the trainer gain (from medians of cycles per request; simple ratios)

- s: medians official 525.6k, pgolto-trainer 316.8k (-39.73%), pgolto-tests 433.7k (-17.48%): kept share **44.0%** of the trainer gain (under the 50% line); per-round kept share mean 43.6% [95% t ±1.5] over 8 rounds; basis: Measured; in the 40-60% window: yes
  - paired rows: pgolto-trainer vs official -39.56% [-40.29, -38.82]; pgolto-tests vs official -17.26% [-17.96, -16.56] (simple)
  - validity band (pgolto-trainer vs official on s inside -30% to -45%): -39.56%: inside
- fh: medians official 280.3k, pgolto-trainer 185.1k (-33.95%), pgolto-tests 237.1k (-15.41%): kept share **45.4%** of the trainer gain (under the 50% line); per-round kept share mean 45.4% [95% t ±2.8] over 8 rounds; basis: Measured; in the 40-60% window: yes
  - paired rows: pgolto-trainer vs official -34.40% [-35.60, -33.18]; pgolto-tests vs official -15.65% [-16.89, -14.39] (simple)

kill line (under 50% on s and on fh): KILLED by the line: the kept share is under 50% on s and on fh
