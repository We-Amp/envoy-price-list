# it-pgo: primary metric cycles_total (cycles user+kernel per request, Envoy process)

legs: 64 current, 64 valid; evidence failing: 0; superseded (replaced by the harness): 0; target rates: s [5200]/s, fh [8000]/s

shape order by round (as run): r1 fh then s; r2 s then fh; r3 fh then s; r4 s then fh; r5 fh then s; r6 s then fh; r7 fh then s; r8 s then fh

| arm | binary sha256 (as started) | md5 unchanged at the end | version |
|---|---|---|---|
| official | 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc | True | b2d89e0ae539 |
| pgolto-tests | 7a47b051a37c4f9db0e2866c0125605e027b9b2c58563630afec046f493b8760 | True | b2d89e0ae539 |
| pgolto-tests-it | 000daec46da56764a37475bc73b29b52079cebd17dffc98c83c58a3b80245902 | True | b2d89e0ae539 |
| pgolto-trainer | d1b4f16e650345957eca97ef690adf149f19ae0ca1d4a1388d6154312270487d | True | b2d89e0ae539 |

## shape s

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official | 8/8 | 524.4k | 344.7k | 179.4k | 163.9k | 71.6k | 1.61 | 397 | 618 | 1.250 | 5200.0–5200.0 | 0.253 |
| pgolto-tests | 8/8 | 433.2k | 262.4k | 171.4k | 137.0k | 71.8k | 1.70 | 344 | 550 | 1.059 | 5200.0–5200.0 | 0.253 |
| pgolto-tests-it | 8/8 | 438.3k | 265.9k | 171.8k | 136.5k | 72.0k | 1.73 | 343 | 546 | 1.067 | 5200.0–5200.0 | 0.254 |
| pgolto-trainer | 8/8 | 318.7k | 154.7k | 164.7k | 119.8k | 72.7k | 1.84 | 275 | 452 | 0.809 | 5200.0–5200.0 | 0.254 |

A/A: none in this run. Reference, S4's s4b-pgo on this shape: gate PASS, A/A reach 1.13% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer vs official | -39.08 | [-39.80, -38.35] | -49.55 | ±1.19 / ±1.19 (t) | 0/8 | 3e-12 | 3e-11 | -204.8k ± 4.2k | finding
| pgolto-tests-it vs official | -16.32 | [-17.30, -15.34] | -17.82 | ±1.16 / ±1.17 (widened) | 0/8 | 3.1e-09 | 1.9e-08 | -85.5k ± 5.3k | finding
| pgolto-tests vs official | -17.32 | [-18.09, -16.54] | -19.02 | ±0.80 / ±0.94 (widened) | 0/8 | 1.4e-10 | 1.2e-09 | -90.8k ± 3.6k | finding
| pgolto-tests-it vs pgolto-tests | +1.20 | [+0.12, +2.29] | +1.20 | ±1.01 / ±1.07 (widened) | 7/8 | 0.027 | 0.054 | +5.2k ± 4.4k | not a finding
| pgolto-tests-it vs pgolto-trainer | +37.34 | [+35.35, +39.36] | +31.73 | ±1.46 / ±1.38 (t) | 8/8 | 2.8e-10 | 1.9e-09 | +119.2k ± 5.5k | finding

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-tests vs pgolto-trainer | +35.71 | [+34.23, +37.20] | +30.53 | ±1.05 / ±1.10 (widened) | 8/8 | 3.6e-11 | - | +114.0k ± 3.7k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer [cycles_u] vs official | -55.03 | [-55.54, -54.51] | -79.91 | ±1.11 / ±1.14 (widened) | 0/8 | 6.6e-14 | - | -189.6k ± 1.9k |
| pgolto-trainer [cycles_k] vs official | -8.46 | [-9.90, -6.99] | -8.84 | ±1.59 / ±1.48 (t) | 0/8 | 3.4e-06 | - | -15.2k ± 2.7k |
| pgolto-trainer [instructions_u] vs official | -26.86 | [-27.35, -26.37] | -31.28 | ±0.05 / ±0.67 (widened) | 0/8 | 0 | - | -44.0k ± 0.1k |
| pgolto-trainer [instructions_k] vs official | +1.64 | [+0.92, +2.37] | +1.63 | ±0.30 / ±0.71 (widened) | 8/8 | 4e-06 | - | +1.2k ± 0.2k |
| pgolto-trainer [context_switches] vs official | +14.31 | [+12.39, +16.26] | +13.37 | ±1.69 / ±1.55 (t) | 8/8 | 3.1e-07 | - | +0.0k ± 0.0k |
| pgolto-trainer [p50_us] vs official | -31.04 | [-33.08, -28.93] | -37.16 | ±3.01 / ±2.58 (t) | 0/8 | 1.4e-08 | - | -0.1k ± 0.0k |
| pgolto-trainer [p99_us] vs official | -27.55 | [-28.62, -26.48] | -32.23 | ±1.48 / ±1.39 (t) | 0/8 | 2.7e-10 | - | -0.2k ± 0.0k |
| pgolto-tests-it [cycles_u] vs official | -22.82 | [-23.55, -22.08] | -25.90 | ±0.83 / ±0.96 (widened) | 0/8 | 2.2e-11 | - | -78.6k ± 2.4k |
| pgolto-tests-it [cycles_k] vs official | -3.86 | [-5.66, -2.03] | -3.94 | ±1.89 / ±1.70 (t) | 0/8 | 0.0017 | - | -6.9k ± 3.3k |
| pgolto-tests-it [instructions_u] vs official | -16.67 | [-17.23, -16.12] | -18.24 | ±0.04 / ±0.67 (widened) | 0/8 | 0 | - | -27.3k ± 0.1k |
| pgolto-tests-it [instructions_k] vs official | +0.55 | [-0.18, +1.29] | +0.55 | ±0.36 / ±0.73 (widened) | 8/8 | 0.0084 | - | +0.4k ± 0.3k |
| pgolto-tests-it [context_switches] vs official | +6.82 | [+4.65, +9.03] | +6.60 | ±2.05 / ±1.83 (t) | 8/8 | 0.00013 | - | +0.0k ± 0.0k |
| pgolto-tests-it [p50_us] vs official | -13.67 | [-15.87, -11.42] | -14.70 | ±2.58 / ±2.24 (t) | 0/8 | 2.9e-06 | - | -0.1k ± 0.0k |
| pgolto-tests-it [p99_us] vs official | -11.99 | [-14.66, -9.23] | -12.77 | ±3.09 / ±2.64 (t) | 0/8 | 2.5e-05 | - | -0.1k ± 0.0k |
| pgolto-tests [cycles_u] vs official | -23.94 | [-24.59, -23.28] | -27.36 | ±0.66 / ±0.86 (widened) | 0/8 | 3.1e-12 | - | -82.5k ± 1.9k |
| pgolto-tests [cycles_k] vs official | -4.61 | [-5.89, -3.32] | -4.72 | ±1.35 / ±1.30 (t) | 0/8 | 7.3e-05 | - | -8.3k ± 2.4k |
| pgolto-tests [instructions_u] vs official | -16.38 | [-16.94, -15.82] | -17.89 | ±0.04 / ±0.67 (widened) | 0/8 | 0 | - | -26.8k ± 0.1k |
| pgolto-tests [instructions_k] vs official | +0.44 | [-0.30, +1.20] | +0.44 | ±0.40 / ±0.74 (widened) | 7/8 | 0.035 | - | +0.3k ± 0.3k |
| pgolto-tests [context_switches] vs official | +6.23 | [+3.93, +8.58] | +6.04 | ±2.19 / ±1.93 (t) | 8/8 | 0.00032 | - | +0.0k ± 0.0k |
| pgolto-tests [p50_us] vs official | -14.11 | [-16.72, -11.42] | -15.21 | ±3.09 / ±2.64 (t) | 0/8 | 7.7e-06 | - | -0.1k ± 0.0k |
| pgolto-tests [p99_us] vs official | -12.17 | [-14.68, -9.58] | -12.97 | ±2.90 / ±2.49 (t) | 0/8 | 1.5e-05 | - | -0.1k ± 0.0k |
| pgolto-tests-it [cycles_u] vs pgolto-tests | +1.47 | [+0.59, +2.37] | +1.46 | ±0.69 / ±0.88 (widened) | 7/8 | 0.0015 | - | +3.9k ± 1.8k |
| pgolto-tests-it [cycles_k] vs pgolto-tests | +0.79 | [-0.79, +2.40] | +0.79 | ±1.58 / ±1.47 (t) | 7/8 | 0.28 | - | +1.4k ± 2.7k |
| pgolto-tests-it [instructions_u] vs pgolto-tests | -0.35 | [-1.01, +0.32] | -0.35 | ±0.07 / ±0.67 (widened) | 0/8 | 8.9e-06 | - | -0.5k ± 0.1k |
| pgolto-tests-it [instructions_k] vs pgolto-tests | +0.10 | [-0.69, +0.91] | +0.10 | ±0.53 / ±0.80 (widened) | 5/8 | 0.66 | - | +0.1k ± 0.4k |
| pgolto-tests-it [context_switches] vs pgolto-tests | +0.56 | [-1.87, +3.04] | +0.55 | ±2.44 / ±2.13 (t) | 5/8 | 0.61 | - | +0.0k ± 0.0k |
| pgolto-tests-it [p50_us] vs pgolto-tests | +0.51 | [-2.12, +3.21] | +0.51 | ±2.65 / ±2.30 (t) | 4/8 | 0.66 | - | +0.0k ± 0.0k |
| pgolto-tests-it [p99_us] vs pgolto-tests | +0.21 | [-4.34, +4.97] | +0.21 | ±4.65 / ±3.91 (t) | 4/8 | 0.92 | - | +0.0k ± 0.0k |
| pgolto-tests-it [cycles_u] vs pgolto-trainer | +71.62 | [+69.22, +74.05] | +54.01 | ±1.41 / ±1.34 (t) | 8/8 | 5.2e-12 | - | +111.0k ± 2.7k |
| pgolto-tests-it [cycles_k] vs pgolto-trainer | +5.03 | [+3.13, +6.95] | +4.90 | ±1.82 / ±1.65 (t) | 8/8 | 0.00038 | - | +8.3k ± 3.1k |
| pgolto-tests-it [instructions_u] vs pgolto-trainer | +13.93 | [+13.17, +14.69] | +13.04 | ±0.07 / ±0.67 (widened) | 8/8 | 0 | - | +16.7k ± 0.1k |
| pgolto-tests-it [instructions_k] vs pgolto-trainer | -1.08 | [-1.78, -0.37] | -1.08 | ±0.30 / ±0.71 (widened) | 0/8 | 5.6e-05 | - | -0.8k ± 0.2k |
| pgolto-tests-it [context_switches] vs pgolto-trainer | -6.55 | [-7.63, -5.47] | -6.78 | ±1.14 / ±1.15 (widened) | 0/8 | 2.1e-06 | - | -0.0k ± 0.0k |
| pgolto-tests-it [p50_us] vs pgolto-trainer | +25.18 | [+20.76, +29.76] | +22.46 | ±3.60 / ±3.06 (t) | 8/8 | 1.6e-06 | - | +0.1k ± 0.0k |
| pgolto-tests-it [p99_us] vs pgolto-trainer | +21.49 | [+17.22, +25.91] | +19.47 | ±3.57 / ±3.04 (t) | 8/8 | 4e-06 | - | +0.1k ± 0.0k |

## shape fh

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official | 8/8 | 279.4k | 197.2k | 82.3k | 164.8k | 29.3k | 0.85 | 214 | 368 | 1.022 | 8000.0–8000.0 | 0.256 |
| pgolto-tests | 8/8 | 238.4k | 157.6k | 81.0k | 149.8k | 29.8k | 0.91 | 198 | 334 | 0.889 | 8000.0–8000.0 | 0.256 |
| pgolto-tests-it | 8/8 | 235.8k | 155.9k | 80.5k | 149.2k | 29.9k | 0.92 | 196 | 332 | 0.879 | 8000.0–8000.0 | 0.257 |
| pgolto-trainer | 8/8 | 182.7k | 105.5k | 76.9k | 125.5k | 30.3k | 0.95 | 173 | 302 | 0.704 | 8000.0–8000.0 | 0.258 |

A/A: none in this run. Reference, S4's s4b-pgo on this shape: gate PASS, A/A reach 1.70% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer vs official | -34.87 | [-35.78, -33.95] | -42.88 | ±1.40 / ±1.34 (t) | 0/8 | 2.6e-11 | 2.3e-10 | -97.5k ± 3.2k | finding
| pgolto-tests-it vs official | -15.20 | [-16.60, -13.78] | -16.49 | ±1.66 / ±1.53 (t) | 0/8 | 6.6e-08 | 2e-07 | -42.5k ± 4.2k | finding
| pgolto-tests vs official | -14.60 | [-15.79, -13.38] | -15.78 | ±1.41 / ±1.35 (t) | 0/8 | 2.9e-08 | 1.1e-07 | -40.8k ± 3.6k | finding
| pgolto-tests-it vs pgolto-tests | -0.71 | [-2.81, +1.44] | -0.71 | ±2.14 / ±1.90 (t) | 3/8 | 0.46 | 0.46 | -1.7k ± 5.1k | not a finding
| pgolto-tests-it vs pgolto-trainer | +30.21 | [+27.65, +32.81] | +26.40 | ±1.98 / ±1.77 (t) | 8/8 | 8.3e-09 | 4.2e-08 | +55.0k ± 4.3k | finding

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-tests vs pgolto-trainer | +31.14 | [+29.28, +33.02] | +27.11 | ±1.43 / ±1.36 (t) | 8/8 | 7.2e-10 | - | +56.7k ± 3.0k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| pgolto-trainer [cycles_u] vs official | -46.61 | [-47.22, -46.00] | -62.76 | ±1.13 / ±1.15 (widened) | 0/8 | 3.8e-13 | - | -92.0k ± 1.8k |
| pgolto-trainer [cycles_k] vs official | -6.69 | [-8.51, -4.84] | -6.93 | ±1.96 / ±1.76 (t) | 0/8 | 7e-05 | - | -5.5k ± 1.5k |
| pgolto-trainer [instructions_u] vs official | -23.82 | [-24.33, -23.31] | -27.21 | ±0.01 / ±0.67 (widened) | 0/8 | 0 | - | -39.2k ± 0.0k |
| pgolto-trainer [instructions_k] vs official | +2.54 | [+1.32, +3.76] | +2.50 | ±1.19 / ±1.19 (widened) | 8/8 | 0.0016 | - | +0.7k ± 0.4k |
| pgolto-trainer [context_switches] vs official | +12.93 | [+9.96, +15.98] | +12.16 | ±2.67 / ±2.31 (t) | 8/8 | 1.3e-05 | - | +0.0k ± 0.0k |
| pgolto-trainer [p50_us] vs official | -19.36 | [-20.42, -18.28] | -21.51 | ±1.33 / ±1.29 (t) | 0/8 | 2.2e-09 | - | -0.0k ± 0.0k |
| pgolto-trainer [p99_us] vs official | -18.41 | [-19.61, -17.20] | -20.35 | ±1.48 / ±1.39 (t) | 0/8 | 6.6e-09 | - | -0.1k ± 0.0k |
| pgolto-tests-it [cycles_u] vs official | -20.75 | [-22.19, -19.28] | -23.26 | ±1.84 / ±1.66 (t) | 0/8 | 1.2e-08 | - | -40.9k ± 3.2k |
| pgolto-tests-it [cycles_k] vs official | -1.89 | [-3.64, -0.10] | -1.90 | ±1.80 / ±1.63 (t) | 1/8 | 0.041 | - | -1.5k ± 1.5k |
| pgolto-tests-it [instructions_u] vs official | -9.45 | [-10.05, -8.84] | -9.92 | ±0.01 / ±0.67 (widened) | 0/8 | 0 | - | -15.6k ± 0.0k |
| pgolto-tests-it [instructions_k] vs official | +1.62 | [+0.52, +2.73] | +1.61 | ±1.04 / ±1.09 (widened) | 7/8 | 0.0082 | - | +0.5k ± 0.3k |
| pgolto-tests-it [context_switches] vs official | +8.40 | [+5.30, +11.58] | +8.06 | ±2.90 / ±2.49 (t) | 8/8 | 0.00031 | - | +0.0k ± 0.0k |
| pgolto-tests-it [p50_us] vs official | -8.49 | [-9.96, -7.00] | -8.87 | ±1.62 / ±1.50 (t) | 0/8 | 3.8e-06 | - | -0.0k ± 0.0k |
| pgolto-tests-it [p99_us] vs official | -9.98 | [-11.48, -8.46] | -10.52 | ±1.68 / ±1.54 (t) | 0/8 | 1.5e-06 | - | -0.0k ± 0.0k |
| pgolto-tests [cycles_u] vs official | -20.17 | [-21.42, -18.91] | -22.53 | ±1.57 / ±1.46 (t) | 0/8 | 5e-09 | - | -39.8k ± 2.8k |
| pgolto-tests [cycles_k] vs official | -1.20 | [-2.55, +0.16] | -1.21 | ±1.37 / ±1.32 (t) | 2/8 | 0.075 | - | -1.0k ± 1.1k |
| pgolto-tests [instructions_u] vs official | -9.09 | [-9.69, -8.48] | -9.53 | ±0.01 / ±0.67 (widened) | 0/8 | 0 | - | -15.0k ± 0.0k |
| pgolto-tests [instructions_k] vs official | +1.50 | [+0.33, +2.68] | +1.49 | ±1.14 / ±1.16 (widened) | 6/8 | 0.018 | - | +0.4k ± 0.3k |
| pgolto-tests [context_switches] vs official | +8.18 | [+5.26, +11.18] | +7.86 | ±2.74 / ±2.37 (t) | 8/8 | 0.00026 | - | +0.0k ± 0.0k |
| pgolto-tests [p50_us] vs official | -7.89 | [-9.15, -6.62] | -8.22 | ±1.37 / ±1.32 (t) | 0/8 | 2.1e-06 | - | -0.0k ± 0.0k |
| pgolto-tests [p99_us] vs official | -9.82 | [-11.36, -8.26] | -10.34 | ±1.72 / ±1.57 (t) | 0/8 | 2e-06 | - | -0.0k ± 0.0k |
| pgolto-tests-it [cycles_u] vs pgolto-tests | -0.72 | [-2.85, +1.45] | -0.72 | ±2.17 / ±1.92 (t) | 3/8 | 0.46 | - | -1.1k ± 3.4k |
| pgolto-tests-it [cycles_k] vs pgolto-tests | -0.69 | [-3.12, +1.80] | -0.69 | ±2.47 / ±2.16 (t) | 3/8 | 0.53 | - | -0.6k ± 2.0k |
| pgolto-tests-it [instructions_u] vs pgolto-tests | -0.39 | [-1.05, +0.28] | -0.39 | ±0.01 / ±0.67 (widened) | 0/8 | 2.2e-13 | - | -0.6k ± 0.0k |
| pgolto-tests-it [instructions_k] vs pgolto-tests | +0.12 | [-0.80, +1.05] | +0.12 | ±0.78 / ±0.93 (widened) | 5/8 | 0.72 | - | +0.0k ± 0.2k |
| pgolto-tests-it [context_switches] vs pgolto-tests | +0.20 | [-1.59, +2.03] | +0.20 | ±1.81 / ±1.64 (t) | 5/8 | 0.8 | - | +0.0k ± 0.0k |
| pgolto-tests-it [p50_us] vs pgolto-tests | -0.65 | [-1.70, +0.41] | -0.65 | ±1.00 / ±1.06 (widened) | 2/8 | 0.17 | - | -0.0k ± 0.0k |
| pgolto-tests-it [p99_us] vs pgolto-tests | -0.18 | [-1.67, +1.34] | -0.18 | ±1.51 / ±1.42 (t) | 2/8 | 0.78 | - | -0.0k ± 0.0k |
| pgolto-tests-it [cycles_u] vs pgolto-trainer | +48.45 | [+45.64, +51.31] | +39.51 | ±1.91 / ±1.72 (t) | 8/8 | 3.9e-10 | - | +51.0k ± 2.6k |
| pgolto-tests-it [cycles_k] vs pgolto-trainer | +5.15 | [+2.53, +7.85] | +5.03 | ±2.53 / ±2.20 (t) | 8/8 | 0.0022 | - | +4.0k ± 2.0k |
| pgolto-tests-it [instructions_u] vs pgolto-trainer | +18.87 | [+18.08, +19.67] | +17.29 | ±0.00 / ±0.67 (widened) | 8/8 | 0 | - | +23.7k ± 0.0k |
| pgolto-tests-it [instructions_k] vs pgolto-trainer | -0.89 | [-2.03, +0.26] | -0.90 | ±1.14 / ±1.16 (widened) | 3/8 | 0.1 | - | -0.3k ± 0.3k |
| pgolto-tests-it [context_switches] vs pgolto-trainer | -4.01 | [-5.76, -2.24] | -4.10 | ±1.83 / ±1.66 (t) | 0/8 | 0.0011 | - | -0.0k ± 0.0k |
| pgolto-tests-it [p50_us] vs pgolto-trainer | +13.48 | [+12.37, +14.59] | +12.64 | ±0.87 / ±0.98 (widened) | 8/8 | 4.5e-09 | - | +0.0k ± 0.0k |
| pgolto-tests-it [p99_us] vs pgolto-trainer | +10.33 | [+9.12, +11.55] | +9.83 | ±1.06 / ±1.10 (widened) | 8/8 | 1e-07 | - | +0.0k ± 0.0k |

## kept share of the trainer gain (from medians of cycles per request; simple ratios; share in %)

- s, pgolto-tests-it: medians official 524.4k, pgolto-trainer 318.7k (-39.22%), pgolto-tests-it 438.3k (-16.42%): kept share **41.9%** (under the 50% line); per-round mean 41.8%, 95% t ±2.4, widened ±2.5 (term 0.76 share points), quoted [39.3, 44.3] (widened), rounds 8, range 36.6 to 45.2; in the 40-60% window: yes; basis: Measured (8 paired rounds, Williams order; no A/A arm in this run: S4's A/A on the shape is the reference)
- s, pgolto-tests: medians official 524.4k, pgolto-trainer 318.7k (-39.22%), pgolto-tests 433.2k (-17.38%): kept share **44.3%** (under the 50% line); per-round mean 44.3%, 95% t ±1.5, widened ±1.9 (term 0.75 share points), quoted [42.4, 46.2] (widened), rounds 8, range 41.8 to 47.4; in the 40-60% window: yes; basis: Measured (8 paired rounds, Williams order; no A/A arm in this run: S4's A/A on the shape is the reference)
  - integration-tests-only against full tests, s: kept share -2.6 share points (per-round mean, 95% t ±2.2, 8 rounds; from medians -2.5); cycles per request +1.20% [+0.12, +2.29] (simple, quoted), +1.20 log points, +5.2k ± 4.4k
  - validity band (pgolto-trainer vs official on s inside -30% to -45%): -39.08%: inside
- fh, pgolto-tests-it: medians official 279.4k, pgolto-trainer 182.7k (-34.60%), pgolto-tests-it 235.8k (-15.60%): kept share **45.1%** (under the 50% line); per-round mean 43.6%, 95% t ±4.0, widened ±3.7 (term 0.88 share points), quoted [39.6, 47.6] (t), rounds 8, range 35.0 to 49.4; in the 40-60% window: yes; basis: Measured (8 paired rounds, Williams order; no A/A arm in this run: S4's A/A on the shape is the reference)
- fh, pgolto-tests: medians official 279.4k, pgolto-trainer 182.7k (-34.60%), pgolto-tests 238.4k (-14.66%): kept share **42.4%** (under the 50% line); per-round mean 41.8%, 95% t ±3.0, widened ±3.0 (term 0.88 share points), quoted [38.8, 44.9] (widened), rounds 8, range 36.3 to 47.2; in the 40-60% window: yes; basis: Measured (8 paired rounds, Williams order; no A/A arm in this run: S4's A/A on the shape is the reference)
  - integration-tests-only against full tests, fh: kept share +1.8 share points (per-round mean, 95% t ±5.2, 8 rounds; from medians +2.7); cycles per request -0.71% [-2.81, +1.44] (simple, quoted), -0.71 log points, -1.7k ± 5.1k

line (50%, pgolto-tests-it, share from medians): UNDER the line on s and on fh: the integration-tests-only profile is also under 50%

## the repeated arms against S4's s4b-pgo (session-to-session check)

| shape | item | S4 | this run | difference | allowance | reproduces |
|---|---|---|---|---|---|---|
| s | pgolto-trainer vs official, simple % (log points) | -39.56 (-50.35) | -39.08 (-49.55) | +0.80 log points | ±1.70 log points (root-sum-square of the two quoted half-widths) | yes |
| s | pgolto-tests vs official, simple % (log points) | -17.26 (-18.95) | -17.32 (-19.02) | -0.07 log points | ±1.26 log points (root-sum-square of the two quoted half-widths) | yes |
| s | pgolto-tests vs pgolto-trainer, simple % (log points) | +36.90 (+31.41) | +35.71 (+30.53) | -0.87 log points | ±1.74 log points (root-sum-square of the two quoted half-widths) | yes |
| s | official median, cycles per request | 525.6k | 524.4k | -0.24% (simple) | (reading; S4 A/A reach 1.13%) | - |
| s | pgolto-trainer median, cycles per request | 316.8k | 318.7k | +0.61% (simple) | (reading; S4 A/A reach 1.13%) | - |
| s | pgolto-tests median, cycles per request | 433.7k | 433.2k | -0.12% (simple) | (reading; S4 A/A reach 1.13%) | - |
| s | kept share, pgolto-tests, from medians (per-round mean), % | 44.0 (43.6) | 44.3 (44.3) | +0.3 (+0.7) share points | ±2.4 share points on the per-round mean (root-sum-square of S4's t half-width and this run's quoted half-width) | yes |
| fh | pgolto-trainer vs official, simple % (log points) | -34.40 (-42.16) | -34.87 (-42.88) | -0.73 log points | ±2.32 log points (root-sum-square of the two quoted half-widths) | yes |
| fh | pgolto-tests vs official, simple % (log points) | -15.65 (-17.02) | -14.60 (-15.78) | +1.24 log points | ±2.05 log points (root-sum-square of the two quoted half-widths) | yes |
| fh | pgolto-tests vs pgolto-trainer, simple % (log points) | +28.58 (+25.14) | +31.14 (+27.11) | +1.97 log points | ±2.02 log points (root-sum-square of the two quoted half-widths) | yes |
| fh | official median, cycles per request | 280.3k | 279.4k | -0.31% (simple) | (reading; S4 A/A reach 1.70%) | - |
| fh | pgolto-trainer median, cycles per request | 185.1k | 182.7k | -1.28% (simple) | (reading; S4 A/A reach 1.70%) | - |
| fh | pgolto-tests median, cycles per request | 237.1k | 238.4k | +0.57% (simple) | (reading; S4 A/A reach 1.70%) | - |
| fh | kept share, pgolto-tests, from medians (per-round mean), % | 45.4 (45.4) | 42.4 (41.8) | -3.0 (-3.6) share points | ±4.1 share points on the per-round mean (root-sum-square of S4's t half-width and this run's quoted half-width) | yes |
