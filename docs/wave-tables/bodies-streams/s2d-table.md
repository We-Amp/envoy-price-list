# s2d-h3: primary metric cycles_total (cycles user+kernel per request, Envoy process)

legs: 36 current, 36 valid; evidence failing: 0; target rates: s [2000]/s, z0 [2000]/s

## shape s

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | origin CPU share of its set (max) | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2tls | 6/6 | 722.0k | 498.3k | 222.0k | 200.7k | 74.8k | 2.03 | 499 | 685 | 0.681 | 2000.0–2000.0 | 0.010 | 0.275 |
| h3 | 6/6 | 1274.4k | 930.7k | 341.5k | 513.3k | 131.7k | 2.59 | 568 | 737 | 1.155 | 2000.0–2000.0 | 0.009 | 0.458 |
| h3-A2 | 6/6 | 1262.2k | 923.7k | 338.5k | 512.6k | 132.1k | 2.66 | 543 | 710 | 1.146 | 2000.0–2000.0 | 0.009 | 0.455 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3-A2 vs h3 | -0.44 | [-3.00, +2.19] | -0.44 | ±2.61 / ±2.10 (t) | 3/6 | 0.68 | - | -5.5k ± 33.5k |

A/A gate (shape s, floor 2.0% simple): **PASS**; A/A reach 3.04% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3 vs h2tls | +77.58 | [+73.31, +81.95] | +57.43 | ±2.43 / ±1.97 (t) | 6/6 | 2.3e-08 | 4.6e-08 | +557.6k ± 26.3k | finding

| row (anchor and exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3-A2 vs h2tls | +76.80 | [+70.61, +83.22] | +56.99 | ±3.56 / ±2.80 (t) | 6/6 | 1.6e-07 | - | +552.1k ± 38.3k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3 [cycles_u] vs h2tls | +88.31 | [+82.79, +93.99] | +63.29 | ±2.97 / ±2.36 (t) | 6/6 | 3.9e-08 | - | +438.4k ± 23.5k |
| h3 [cycles_k] vs h2tls | +53.62 | [+50.12, +57.19] | +42.93 | ±2.30 / ±1.88 (t) | 6/6 | 7.4e-08 | - | +119.1k ± 6.3k |
| h3 [instructions_u] vs h2tls | +156.30 | [+151.24, +161.46] | +94.12 | ±1.99 / ±1.66 (t) | 6/6 | 7.2e-10 | - | +313.8k ± 10.2k |
| h3 [instructions_k] vs h2tls | +76.33 | [+73.89, +78.80] | +56.72 | ±1.39 / ±1.25 (t) | 6/6 | 1.5e-09 | - | +57.1k ± 1.2k |
| h3 [context_switches] vs h2tls | +27.80 | [+19.82, +36.32] | +24.53 | ±6.45 / ±4.96 (t) | 6/6 | 0.00019 | - | +0.0k ± 0.0k |
| h3 [p50_us] vs h2tls | +12.42 | [+6.61, +18.55] | +11.71 | ±5.31 / ±4.10 (t) | 6/6 | 0.0024 | - | +0.1k ± 0.0k |
| h3 [p99_us] vs h2tls | +6.12 | [+2.44, +9.94] | +5.94 | ±3.53 / ±2.78 (t) | 6/6 | 0.0075 | - | +0.0k ± 0.0k |
| h3-A2 [cycles_u] vs h2tls | +87.30 | [+80.45, +94.41] | +62.75 | ±3.73 / ±2.92 (t) | 6/6 | 1.2e-07 | - | +433.4k ± 27.7k |
| h3-A2 [cycles_k] vs h2tls | +53.37 | [+47.67, +59.28] | +42.77 | ±3.79 / ±2.96 (t) | 6/6 | 9.1e-07 | - | +118.7k ± 11.7k |
| h3-A2 [instructions_u] vs h2tls | +153.51 | [+148.16, +158.98] | +93.02 | ±2.14 / ±1.76 (t) | 6/6 | 1.1e-09 | - | +308.2k ± 10.7k |
| h3-A2 [instructions_k] vs h2tls | +76.05 | [+71.72, +80.48] | +56.56 | ±2.49 / ±2.01 (t) | 6/6 | 2.8e-08 | - | +56.9k ± 2.7k |
| h3-A2 [context_switches] vs h2tls | +28.97 | [+19.28, +39.44] | +25.44 | ±7.81 / ±5.99 (t) | 6/6 | 0.0004 | - | +0.0k ± 0.0k |
| h3-A2 [p50_us] vs h2tls | +9.52 | [+3.81, +15.55] | +9.10 | ±5.36 / ±4.14 (t) | 6/6 | 0.0073 | - | +0.0k ± 0.0k |
| h3-A2 [p99_us] vs h2tls | +4.18 | [-1.08, +9.72] | +4.09 | ±5.18 / ±4.00 (t) | 5/6 | 0.098 | - | +0.0k ± 0.0k |
| h3-A2 [cycles_u] vs h3 | -0.54 | [-3.22, +2.22] | -0.54 | ±2.74 / ±2.19 (t) | 3/6 | 0.63 | - | -5.0k ± 25.8k |
| h3-A2 [cycles_k] vs h3 | -0.16 | [-2.98, +2.73] | -0.16 | ±2.86 / ±2.28 (t) | 2/6 | 0.89 | - | -0.5k ± 9.9k |
| h3-A2 [instructions_u] vs h3 | -1.09 | [-4.47, +2.41] | -1.09 | ±3.48 / ±2.74 (t) | 3/6 | 0.46 | - | -5.6k ± 17.7k |
| h3-A2 [instructions_k] vs h3 | -0.16 | [-2.35, +2.08] | -0.16 | ±2.22 / ±1.82 (t) | 5/6 | 0.86 | - | -0.2k ± 2.9k |
| h3-A2 [context_switches] vs h3 | +0.91 | [-10.28, +13.49] | +0.90 | ±11.75 / ±8.98 (t) | 5/6 | 0.85 | - | +0.0k ± 0.0k |
| h3-A2 [p50_us] vs h3 | -2.58 | [-11.52, +7.27] | -2.61 | ±9.63 / ±7.37 (t) | 1/6 | 0.52 | - | -0.0k ± 0.1k |
| h3-A2 [p99_us] vs h3 | -1.83 | [-8.14, +4.91] | -1.85 | ±6.64 / ±5.11 (t) | 1/6 | 0.51 | - | -0.0k ± 0.0k |

## shape z0

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | origin CPU share of its set (max) | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2tls | 6/6 | 654.7k | 466.3k | 188.4k | 172.8k | 60.9k | 2.03 | 464 | 650 | 0.625 | 2000.0–2000.0 | 0.008 | 0.275 |
| h3 | 6/6 | 1104.7k | 844.7k | 260.0k | 439.1k | 85.7k | 2.89 | 500 | 667 | 1.022 | 2000.0–2000.0 | 0.008 | 0.457 |
| h3-A2 | 6/6 | 1047.6k | 802.8k | 245.0k | 434.2k | 84.5k | 2.84 | 472 | 641 | 0.967 | 2000.0–2000.0 | 0.008 | 0.448 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3-A2 vs h3 | -2.77 | [-7.62, +2.33] | -2.81 | ±5.11 / ±3.96 (t) | 2/6 | 0.22 | - | -30.5k ± 55.2k |

A/A gate (shape z0, floor 2.0% simple): **FAIL: this shape's rows are void**; A/A reach 7.74% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3 vs h2tls | +66.91 | [+61.37, +72.64] | +51.23 | ±3.38 / ±2.66 (t) | 6/6 | 2.1e-07 | 2.1e-07 | +437.1k ± 37.6k | VOID (A/A)

| row (anchor and exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3-A2 vs h2tls | +62.29 | [+55.67, +69.19] | +48.42 | ±4.17 / ±3.25 (t) | 6/6 | 7.9e-07 | - | +406.7k ± 38.5k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3 [cycles_u] vs h2tls | +79.40 | [+73.34, +85.67] | +58.44 | ±3.44 / ±2.70 (t) | 6/6 | 1.2e-07 | - | +368.5k ± 28.2k |
| h3 [cycles_k] vs h2tls | +36.26 | [+30.81, +41.94] | +30.94 | ±4.08 / ±3.18 (t) | 6/6 | 6.6e-06 | - | +68.6k ± 10.5k |
| h3 [instructions_u] vs h2tls | +152.85 | [+150.06, +155.68] | +92.76 | ±1.11 / ±1.08 (t) | 6/6 | 4.2e-11 | - | +264.2k ± 4.8k |
| h3 [instructions_k] vs h2tls | +41.07 | [+37.79, +44.43] | +34.41 | ±2.35 / ±1.91 (t) | 6/6 | 2.5e-07 | - | +25.0k ± 1.7k |
| h3 [context_switches] vs h2tls | +43.32 | [+38.84, +47.93] | +35.99 | ±3.17 / ±2.51 (t) | 6/6 | 8.9e-07 | - | +0.0k ± 0.0k |
| h3 [p50_us] vs h2tls | +5.46 | [+0.82, +10.32] | +5.32 | ±4.50 / ±3.50 (t) | 5/6 | 0.029 | - | +0.0k ± 0.0k |
| h3 [p99_us] vs h2tls | +1.66 | [-2.49, +5.99] | +1.65 | ±4.17 / ±3.25 (t) | 4/6 | 0.36 | - | +0.0k ± 0.0k |
| h3-A2 [cycles_u] vs h2tls | +74.88 | [+67.87, +82.17] | +55.89 | ±4.09 / ±3.19 (t) | 6/6 | 3.5e-07 | - | +347.3k ± 28.3k |
| h3-A2 [cycles_k] vs h2tls | +31.40 | [+25.33, +37.77] | +27.31 | ±4.73 / ±3.67 (t) | 6/6 | 2.5e-05 | - | +59.3k ± 10.7k |
| h3-A2 [instructions_u] vs h2tls | +152.18 | [+147.59, +156.85] | +92.50 | ±1.84 / ±1.55 (t) | 6/6 | 5.2e-10 | - | +263.0k ± 8.1k |
| h3-A2 [instructions_k] vs h2tls | +38.86 | [+37.65, +40.08] | +32.83 | ±0.74 / ±0.87 (widened) | 6/6 | 9.9e-10 | - | +23.7k ± 0.5k |
| h3-A2 [context_switches] vs h2tls | +40.53 | [+34.43, +46.90] | +34.02 | ±4.43 / ±3.45 (t) | 6/6 | 6.2e-06 | - | +0.0k ± 0.0k |
| h3-A2 [p50_us] vs h2tls | +2.08 | [-4.49, +9.09] | +2.05 | ±6.65 / ±5.11 (t) | 4/6 | 0.46 | - | +0.0k ± 0.0k |
| h3-A2 [p99_us] vs h2tls | -1.87 | [-4.80, +1.15] | -1.89 | ±3.03 / ±2.40 (t) | 3/6 | 0.17 | - | -0.0k ± 0.0k |
| h3-A2 [cycles_u] vs h3 | -2.52 | [-7.18, +2.38] | -2.55 | ±4.90 / ±3.80 (t) | 2/6 | 0.24 | - | -21.2k ± 40.4k |
| h3-A2 [cycles_k] vs h3 | -3.57 | [-9.06, +2.27] | -3.63 | ±5.87 / ±4.53 (t) | 2/6 | 0.17 | - | -9.3k ± 14.9k |
| h3-A2 [instructions_u] vs h3 | -0.27 | [-2.59, +2.11] | -0.27 | ±2.35 / ±1.92 (t) | 3/6 | 0.78 | - | -1.1k ± 10.3k |
| h3-A2 [instructions_k] vs h3 | -1.57 | [-3.63, +0.54] | -1.58 | ±2.12 / ±1.75 (t) | 1/6 | 0.11 | - | -1.3k ± 1.8k |
| h3-A2 [context_switches] vs h3 | -1.94 | [-8.34, +4.89] | -1.96 | ±6.74 / ±5.18 (t) | 3/6 | 0.49 | - | -0.0k ± 0.0k |
| h3-A2 [p50_us] vs h3 | -3.21 | [-11.30, +5.62] | -3.26 | ±8.73 / ±6.69 (t) | 2/6 | 0.38 | - | -0.0k ± 0.0k |
| h3-A2 [p99_us] vs h3 | -3.47 | [-9.41, +2.85] | -3.54 | ±6.34 / ±4.88 (t) | 1/6 | 0.21 | - | -0.0k ± 0.0k |

anchor gate: h3 vs h2tls at 4 KB +77.58% simple, band [+65, +85]: **inside**

## HTTP/3 premium at 0 B as a share of the premium at 4 KB (cycles per request, h3 - h2tls, per round)

cycles_total: premium at 0 B +437.1k ± 37.6k, at 4 KB +557.6k ± 26.3k, extra from 0 B to 4 KB +120.4k ± 27.6k; 0 B premium = 78.4% of the 4 KB premium [73.1, 83.6] (per-round ratio, 95% t, 6 rounds)
cycles_u: premium at 0 B +368.5k ± 28.2k, at 4 KB +438.4k ± 23.5k, extra from 0 B to 4 KB +69.9k ± 23.5k; 0 B premium = 84.1% of the 4 KB premium [78.7, 89.5] (per-round ratio, 95% t, 6 rounds)
cycles_k: premium at 0 B +68.6k ± 10.5k, at 4 KB +119.1k ± 6.3k, extra from 0 B to 4 KB +50.5k ± 10.6k; 0 B premium = 57.6% of the 4 KB premium [49.1, 66.2] (per-round ratio, 95% t, 6 rounds)

| shape | arm | UDP datagrams out /request (box-wide, median) | in /request | busiest worker share (min-max) |
|---|---|---|---|---|
| z0 | h2tls | 0.000 | 0.000 | 0.251-0.275 |
| z0 | h3 | 3.985 | 3.985 | 0.298-0.457 |
| z0 | h3-A2 | 3.986 | 3.986 | 0.353-0.448 |
| s | h2tls | 0.000 | 0.000 | 0.251-0.275 |
| s | h3 | 7.017 | 7.017 | 0.307-0.458 |
| s | h3-A2 | 7.017 | 7.017 | 0.311-0.455 |
