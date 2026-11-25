# s3a-stack: primary metric cycles_total (cycles user+kernel per request, Envoy process)

legs: 36 current, 36 valid; evidence failing: 0; superseded (replaced by the harness): 0; target rates: sx [5200]/s

## shape sx

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | side services, CPU share of their set (max) | busiest worker share (max) | statsd datagrams /req (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bare | 6/6 | 536.7k | 357.1k | 179.1k | 199.2k | 71.2k | 1.55 | 415 | 645 | 1.277 | 5200.0–5200.0 | 0.023 | 0.253 | - |
| bare-A2 | 6/6 | 537.9k | 357.0k | 180.5k | 199.2k | 71.7k | 1.61 | 409 | 642 | 1.280 | 5200.0–5200.0 | 0.022 | 0.254 | - |
| lean | 6/6 | 656.4k | 472.7k | 183.8k | 257.1k | 71.0k | 1.42 | 499 | 970 | 1.535 | 5200.0–5200.0 | 0.023 | 0.253 | - |
| typical | 6/6 | 742.1k | 503.4k | 237.8k | 279.4k | 105.3k | 1.35 | 569 | 1542 | 1.724 | 5200.0–5200.0 | 0.024 | 0.255 | 3.010 |
| typical-A2 | 6/6 | 744.7k | 506.6k | 237.9k | 279.5k | 105.2k | 1.34 | 574 | 1409 | 1.728 | 5200.0–5200.0 | 0.023 | 0.253 | 3.010 |
| typical-nosink | 6/6 | 659.2k | 476.0k | 183.0k | 260.0k | 71.3k | 1.37 | 513 | 1038 | 1.538 | 5200.0–5200.0 | 0.023 | 0.253 | - |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| bare-A2 vs bare | +0.14 | [-0.79, +1.07] | +0.14 | ±0.85 / ±0.93 (widened) | 3/6 | 0.69 | - | +0.7k ± 4.6k | PASS
| typical-A2 vs typical | +0.30 | [-0.49, +1.10] | +0.30 | ±0.56 / ±0.79 (widened) | 4/6 | 0.23 | - | +2.2k ± 4.2k | PASS

A/A gate (shape sx, floor 1.0%): **PASS**; A/A reach 1.09% (simple); largest A/A excursion 0.30 log-%

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| typical vs bare | +38.17 | [+36.91, +39.44] | +32.33 | ±0.82 / ±0.92 (widened) | 6/6 | 1.8e-09 | 7.2e-09 | +204.8k ± 5.8k | finding
| typical-nosink vs bare | +22.93 | [+21.77, +24.09] | +20.64 | ±0.87 / ±0.94 (widened) | 6/6 | 2.3e-08 | 6.8e-08 | +123.0k ± 5.4k | finding
| lean vs bare | +22.23 | [+20.90, +23.58] | +20.08 | ±1.10 / ±1.07 (t) | 6/6 | 8.3e-08 | 1.7e-07 | +119.3k ± 6.9k | finding
| lean vs typical | -11.54 | [-12.45, -10.62] | -12.26 | ±1.04 / ±1.03 (t) | 0/6 | 7.2e-07 | 7.2e-07 | -85.5k ± 7.1k | finding

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| typical vs typical-nosink | +12.40 | [+10.92, +13.91] | +11.69 | ±1.33 / ±1.22 (t) | 6/6 | 3.2e-06 | - | +81.8k ± 9.4k |
| lean vs typical-nosink | -0.56 | [-1.55, +0.44] | -0.57 | ±0.98 / ±1.00 (widened) | 2/6 | 0.2 | - | -3.7k ± 6.4k |
| typical-A2 vs bare | +38.59 | [+37.43, +39.75] | +32.63 | ±0.67 / ±0.84 (widened) | 6/6 | 6.2e-10 | - | +207.1k ± 4.4k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| typical [cycles_u] vs bare | +41.02 | [+39.77, +42.28] | +34.37 | ±0.78 / ±0.89 (widened) | 6/6 | 9.9e-10 | - | +146.5k ± 3.7k |
| typical [cycles_k] vs bare | +32.50 | [+30.85, +34.17] | +28.14 | ±1.26 / ±1.17 (t) | 6/6 | 3e-08 | - | +58.3k ± 2.7k |
| typical [instructions_u] vs bare | +40.26 | [+39.32, +41.20] | +33.83 | ±0.07 / ±0.67 (widened) | 6/6 | 8.4e-15 | - | +80.2k ± 0.2k |
| typical [instructions_k] vs bare | +47.34 | [+45.93, +48.77] | +38.76 | ±0.91 / ±0.96 (widened) | 6/6 | 1.2e-09 | - | +33.7k ± 0.9k |
| typical [context_switches] vs bare | -15.30 | [-22.17, -7.81] | -16.60 | ±8.47 / ±6.49 (t) | 0/6 | 0.004 | - | -0.0k ± 0.0k |
| typical [p50_us] vs bare | +38.75 | [+33.87, +43.80] | +32.75 | ±3.58 / ±2.81 (t) | 6/6 | 2.6e-06 | - | +0.2k ± 0.0k |
| typical [p99_us] vs bare | +129.25 | [+68.72, +211.50] | +82.97 | ±30.66 / ±23.38 (t) | 6/6 | 0.00094 | - | +0.9k ± 0.5k |
| typical-nosink [cycles_u] vs bare | +33.32 | [+32.29, +34.36] | +28.76 | ±0.52 / ±0.77 (widened) | 6/6 | 3.1e-10 | - | +119.0k ± 2.3k |
| typical-nosink [cycles_k] vs bare | +2.23 | [+0.34, +4.15] | +2.20 | ±1.86 / ±1.57 (t) | 6/6 | 0.029 | - | +4.0k ± 3.4k |
| typical-nosink [instructions_u] vs bare | +30.52 | [+29.65, +31.40] | +26.64 | ±0.10 / ±0.67 (widened) | 6/6 | 1.1e-13 | - | +60.8k ± 0.2k |
| typical-nosink [instructions_k] vs bare | +0.13 | [-0.83, +1.11] | +0.13 | ±0.92 / ±0.97 (widened) | 4/6 | 0.72 | - | +0.1k ± 0.7k |
| typical-nosink [context_switches] vs bare | -11.44 | [-15.88, -6.77] | -12.15 | ±5.14 / ±3.97 (t) | 0/6 | 0.0017 | - | -0.0k ± 0.0k |
| typical-nosink [p50_us] vs bare | +24.28 | [+20.84, +27.82] | +21.74 | ±2.81 / ±2.24 (t) | 6/6 | 5.9e-06 | - | +0.1k ± 0.0k |
| typical-nosink [p99_us] vs bare | +61.27 | [+42.54, +82.45] | +47.79 | ±12.34 / ±9.43 (t) | 6/6 | 0.00017 | - | +0.4k ± 0.1k |
| lean [cycles_u] vs bare | +32.35 | [+31.18, +33.53] | +28.03 | ±0.77 / ±0.89 (widened) | 6/6 | 2.7e-09 | - | +115.6k ± 3.6k |
| lean [cycles_k] vs bare | +2.08 | [+0.17, +4.03] | +2.06 | ±1.89 / ±1.59 (t) | 5/6 | 0.038 | - | +3.7k ± 3.4k |
| lean [instructions_u] vs bare | +29.06 | [+28.20, +29.93] | +25.51 | ±0.07 / ±0.67 (widened) | 6/6 | 2.3e-14 | - | +57.9k ± 0.1k |
| lean [instructions_k] vs bare | -0.31 | [-1.24, +0.63] | -0.31 | ±0.87 / ±0.94 (widened) | 2/6 | 0.4 | - | -0.2k ± 0.6k |
| lean [context_switches] vs bare | -8.82 | [-13.19, -4.23] | -9.24 | ±4.91 / ±3.80 (t) | 0/6 | 0.0047 | - | -0.0k ± 0.0k |
| lean [p50_us] vs bare | +21.36 | [+18.60, +24.19] | +19.36 | ±2.30 / ±1.88 (t) | 6/6 | 3.9e-06 | - | +0.1k ± 0.0k |
| lean [p99_us] vs bare | +52.60 | [+40.02, +66.30] | +42.26 | ±8.60 / ±6.59 (t) | 6/6 | 5.5e-05 | - | +0.3k ± 0.1k |
| lean [cycles_u] vs typical | -6.15 | [-7.14, -5.14] | -6.34 | ±1.06 / ±1.05 (t) | 0/6 | 2.1e-05 | - | -31.0k ± 5.2k |
| lean [cycles_k] vs typical | -22.96 | [-23.79, -22.12] | -26.08 | ±1.08 / ±1.06 (t) | 0/6 | 2e-08 | - | -54.6k ± 2.1k |
| lean [instructions_u] vs typical | -7.98 | [-8.59, -7.36] | -8.32 | ±0.07 / ±0.67 (widened) | 0/6 | 5.1e-12 | - | -22.3k ± 0.2k |
| lean [instructions_k] vs typical | -32.34 | [-33.07, -31.60] | -39.07 | ±1.09 / ±1.06 (t) | 0/6 | 2.8e-09 | - | -33.9k ± 1.0k |
| lean [context_switches] vs typical | +7.64 | [-2.61, +18.98] | +7.37 | ±10.02 / ±7.67 (t) | 4/6 | 0.12 | - | +0.0k ± 0.0k |
| lean [p50_us] vs typical | -12.53 | [-16.03, -8.87] | -13.39 | ±4.09 / ±3.19 (t) | 0/6 | 0.00039 | - | -0.1k ± 0.0k |
| lean [p99_us] vs typical | -33.44 | [-54.60, -2.40] | -40.70 | ±38.27 / ±29.19 (t) | 1/6 | 0.041 | - | -0.6k ± 0.6k |
| typical [cycles_u] vs typical-nosink | +5.78 | [+4.71, +6.85] | +5.62 | ±1.00 / ±1.01 (widened) | 6/6 | 2.8e-05 | - | +27.5k ± 4.9k |
| typical [cycles_k] vs typical-nosink | +29.62 | [+26.74, +32.56] | +25.94 | ±2.24 / ±1.84 (t) | 6/6 | 8.1e-07 | - | +54.3k ± 4.7k |
| typical [instructions_u] vs typical-nosink | +7.46 | [+6.74, +8.18] | +7.19 | ±0.08 / ±0.67 (widened) | 6/6 | 3.7e-11 | - | +19.4k ± 0.2k |
| typical [instructions_k] vs typical-nosink | +47.14 | [+45.70, +48.60] | +38.62 | ±0.95 / ±0.98 (widened) | 6/6 | 1.5e-09 | - | +33.6k ± 0.9k |
| typical [context_switches] vs typical-nosink | -4.36 | [-11.98, +3.93] | -4.45 | ±8.31 / ±6.37 (t) | 1/6 | 0.23 | - | -0.0k ± 0.0k |
| typical [p50_us] vs typical-nosink | +11.64 | [+9.71, +13.59] | +11.01 | ±1.74 / ±1.48 (t) | 6/6 | 1.6e-05 | - | +0.1k ± 0.0k |
| typical [p99_us] vs typical-nosink | +42.16 | [+9.32, +84.86] | +35.18 | ±26.27 / ±20.04 (t) | 5/6 | 0.018 | - | +0.5k ± 0.4k |
| bare-A2 [cycles_u] vs bare | -0.04 | [-0.98, +0.91] | -0.04 | ±0.88 / ±0.95 (widened) | 2/6 | 0.91 | - | -0.1k ± 3.1k |
| bare-A2 [cycles_k] vs bare | +0.49 | [-0.49, +1.48] | +0.49 | ±0.94 / ±0.98 (widened) | 3/6 | 0.24 | - | +0.9k ± 1.7k |
| bare-A2 [instructions_u] vs bare | +0.01 | [-0.66, +0.68] | +0.01 | ±0.07 / ±0.67 (widened) | 4/6 | 0.7 | - | +0.0k ± 0.1k |
| bare-A2 [instructions_k] vs bare | +0.50 | [-0.37, +1.38] | +0.50 | ±0.74 / ±0.88 (widened) | 3/6 | 0.14 | - | +0.4k ± 0.5k |
| bare-A2 [context_switches] vs bare | +2.92 | [-1.31, +7.32] | +2.88 | ±4.19 / ±3.26 (t) | 3/6 | 0.14 | - | +0.0k ± 0.0k |
| bare-A2 [p50_us] vs bare | -0.65 | [-3.94, +2.75] | -0.65 | ±3.36 / ±2.65 (t) | 3/6 | 0.64 | - | -0.0k ± 0.0k |
| bare-A2 [p99_us] vs bare | -0.07 | [-5.19, +5.33] | -0.07 | ±5.26 / ±4.07 (t) | 2/6 | 0.98 | - | -0.0k ± 0.0k |
| typical-A2 [cycles_u] vs typical | +0.43 | [-0.35, +1.22] | +0.43 | ±0.54 / ±0.78 (widened) | 5/6 | 0.097 | - | +2.2k ± 2.7k |
| typical-A2 [cycles_k] vs typical | +0.02 | [-0.87, +0.92] | +0.02 | ±0.78 / ±0.89 (widened) | 3/6 | 0.95 | - | +0.0k ± 1.8k |
| typical-A2 [instructions_u] vs typical | +0.02 | [-0.65, +0.69] | +0.02 | ±0.08 / ±0.67 (widened) | 3/6 | 0.58 | - | +0.0k ± 0.2k |
| typical-A2 [instructions_k] vs typical | +0.08 | [-1.14, +1.32] | +0.08 | ±1.23 / ±1.15 (t) | 4/6 | 0.87 | - | +0.1k ± 1.3k |
| typical-A2 [context_switches] vs typical | +0.27 | [-11.53, +13.64] | +0.27 | ±12.52 / ±9.57 (t) | 4/6 | 0.96 | - | +0.0k ± 0.0k |
| typical-A2 [p50_us] vs typical | +0.74 | [-3.93, +5.64] | +0.74 | ±4.75 / ±3.68 (t) | 2/6 | 0.71 | - | +0.0k ± 0.0k |
| typical-A2 [p99_us] vs typical | -1.70 | [-40.82, +63.29] | -1.71 | ±50.74 / ±38.70 (t) | 2/6 | 0.93 | - | -0.0k ± 0.8k |

## the compounding claim (plan 4.2): the stack against the sum of the published single rows

| arm vs bare | measured, simple % [quoted 95%] | predicted sum, simple % | measured − predicted, points | band ±3 | predicted in cycles (published differences summed / this run's bare median) | measured, cycles (paired difference) | reading |
|---|---|---|---|---|---|---|---|
| typical-nosink | +22.93 [+21.77, +24.09] | +24.5 | -1.57 | inside | 130.2k = +24.26% (agrees with the simple-% sum within 1 point) | +123.0k ± 5.4k | the rows add up |
| typical | +38.17 [+36.91, +39.44] | +40.5 | -2.33 | inside | 212.7k = +39.64% (agrees with the simple-% sum within 1 point) | +204.8k ± 5.8k | the rows add up (the quoted interval reaches a band edge) |
| lean | +22.23 [+20.90, +23.58] | +23.6 | -1.37 | inside | 125.3k = +23.34% (agrees with the simple-% sum within 1 point) | +119.3k ± 6.9k | the rows add up |

what settings give back: lean vs typical -11.54% [-12.45, -10.62] (simple), -85.5k ± 7.1k cycles per request
the statsd sink inside the stack: typical vs typical-nosink +12.40% [+10.92, +13.91] of the no-sink stack, +81.8k ± 9.4k cycles per request = +15.25% of bare (published worker figure +16.0%, 82.6k cycles)
