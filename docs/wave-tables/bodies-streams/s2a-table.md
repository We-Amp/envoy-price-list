# s2a-chunked: primary metric cycles_total (cycles user+kernel per request, Envoy process)

legs: 72 current, 72 valid; evidence failing: 0; target rates: b1m [800]/s, b64k [4000]/s

## shape b1m

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | origin CPU share of its set (max) | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ch4k | 6/6 | 5085.1k | 1319.2k | 3774.8k | 1262.6k | 1764.2k | 1.37 | 2763 | 4778 | 1.783 | 800.0–800.0 | 0.112 | 0.256 |
| ch8k | 6/6 | 3671.1k | 985.2k | 2681.8k | 731.8k | 1062.2k | 1.52 | 2605 | 3970 | 1.292 | 800.0–800.0 | 0.066 | 0.253 |
| cl | 6/6 | 2623.9k | 555.6k | 2069.3k | 344.2k | 680.0k | 1.87 | 1353 | 1593 | 0.939 | 800.0–800.0 | 0.029 | 0.252 |
| cl-A2 | 6/6 | 2627.8k | 556.8k | 2072.0k | 344.1k | 680.8k | 1.87 | 1353 | 1597 | 0.942 | 800.0–800.0 | 0.029 | 0.252 |
| cl8k | 6/6 | 3370.7k | 693.7k | 2677.3k | 445.9k | 1086.6k | 1.60 | 2242 | 3036 | 1.188 | 800.0–800.0 | 0.066 | 0.252 |
| h2in | 6/6 | 4144.0k | 1303.3k | 2842.1k | 829.9k | 1088.9k | 2.86 | 3662 | 7625 | 1.472 | 800.0–800.0 | 0.194 | 0.252 |

| arm | up paused /req | up resumed /req | up backed up /req | up drained /req | down paused /req | down resumed /req |
|---|---|---|---|---|---|---|
| ch4k | 0.0012 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| ch8k | 0.0011 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| cl | 0.0568 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| cl-A2 | 0.0637 | 0.0001 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| cl8k | 0.0001 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| h2in | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| cl-A2 vs cl | -0.05 | [-0.75, +0.65] | -0.05 | ±0.28 / ±0.70 (widened) | 3/6 | 0.65 | - | -1.4k ± 7.4k |

A/A gate (shape b1m, floor 1.5% simple): **PASS**; A/A reach 0.75% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| ch8k vs cl8k | +8.76 | [+7.99, +9.53] | +8.40 | ±0.30 / ±0.71 (widened) | 6/6 | 1.1e-08 | 5.3e-08 | +295.3k ± 11.0k | finding
| ch8k vs cl | +39.47 | [+38.47, +40.48] | +33.27 | ±0.36 / ±0.72 (widened) | 6/6 | 2.4e-11 | 1.7e-10 | +1037.8k ± 10.0k | finding
| ch4k vs cl | +93.45 | [+91.84, +95.07] | +65.98 | ±0.66 / ±0.84 (widened) | 6/6 | 1.7e-11 | 1.4e-10 | +2457.1k ± 23.5k | finding
| h2in vs cl | +57.64 | [+56.36, +58.94] | +45.52 | ±0.62 / ±0.82 (widened) | 6/6 | 8.1e-11 | 4.8e-10 | +1515.7k ± 20.3k | finding

| row (anchor and exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| cl8k vs cl | +28.24 | [+27.31, +29.17] | +24.87 | ±0.37 / ±0.72 (widened) | 6/6 | 1.2e-10 | - | +742.5k ± 9.4k |
| ch4k vs ch8k | +38.70 | [+37.63, +39.79] | +32.72 | ±0.53 / ±0.78 (widened) | 6/6 | 1.8e-10 | - | +1419.4k ± 23.0k |
| h2in vs cl8k | +22.93 | [+22.04, +23.83] | +20.65 | ±0.38 / ±0.73 (widened) | 6/6 | 3.4e-10 | - | +773.2k ± 15.1k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| ch8k [cycles_u] vs cl8k | +41.88 | [+40.32, +43.47] | +34.98 | ±1.11 / ±1.08 (t) | 6/6 | 5.4e-09 | - | +290.8k ± 9.4k |
| ch8k [cycles_k] vs cl8k | +0.17 | [-0.52, +0.86] | +0.17 | ±0.21 / ±0.69 (widened) | 4/6 | 0.1 | - | +4.5k ± 5.7k |
| ch8k [instructions_u] vs cl8k | +64.31 | [+62.31, +66.32] | +49.66 | ±1.22 / ±1.14 (t) | 6/6 | 1.5e-09 | - | +286.9k ± 5.9k |
| ch8k [instructions_k] vs cl8k | -2.17 | [-2.95, -1.38] | -2.19 | ±0.58 / ±0.80 (widened) | 0/6 | 0.0002 | - | -23.6k ± 6.3k |
| ch8k [context_switches] vs cl8k | -4.64 | [-6.20, -3.06] | -4.75 | ±1.65 / ±1.42 (t) | 0/6 | 0.0007 | - | -0.0k ± 0.0k |
| ch8k [p50_us] vs cl8k | +16.38 | [+15.16, +17.62] | +15.17 | ±1.06 / ±1.05 (t) | 6/6 | 2.7e-07 | - | +0.4k ± 0.0k |
| ch8k [p99_us] vs cl8k | +28.14 | [+20.67, +36.07] | +24.80 | ±6.01 / ±4.63 (t) | 6/6 | 0.00013 | - | +0.9k ± 0.2k |
| ch8k [cycles_u] vs cl | +76.94 | [+75.29, +78.60] | +57.06 | ±0.86 / ±0.94 (widened) | 6/6 | 1.3e-10 | - | +428.4k ± 6.6k |
| ch8k [cycles_k] vs cl | +29.40 | [+28.52, +30.29] | +25.78 | ±0.20 / ±0.68 (widened) | 6/6 | 4.6e-12 | - | +609.4k ± 3.6k |
| ch8k [instructions_u] vs cl | +112.96 | [+111.40, +114.53] | +75.60 | ±0.41 / ±0.73 (widened) | 6/6 | 7.5e-13 | - | +388.8k ± 3.0k |
| ch8k [instructions_k] vs cl | +56.23 | [+55.14, +57.33] | +44.61 | ±0.29 / ±0.70 (widened) | 6/6 | 1.8e-12 | - | +382.5k ± 2.7k |
| ch8k [context_switches] vs cl | -18.64 | [-19.69, -17.57] | -20.62 | ±1.31 / ±1.20 (t) | 0/6 | 1.7e-07 | - | -0.0k ± 0.0k |
| ch8k [p50_us] vs cl | +92.45 | [+90.79, +94.12] | +65.47 | ±0.73 / ±0.87 (widened) | 6/6 | 2.9e-11 | - | +1.3k ± 0.0k |
| ch8k [p99_us] vs cl | +144.50 | [+130.04, +159.87] | +89.41 | ±6.10 / ±4.70 (t) | 6/6 | 2.5e-07 | - | +2.3k ± 0.2k |
| ch4k [cycles_u] vs cl | +137.03 | [+134.00, +140.10] | +86.30 | ±1.29 / ±1.19 (t) | 6/6 | 1.2e-10 | - | +763.0k ± 12.2k |
| ch4k [cycles_k] vs cl | +81.74 | [+80.25, +83.24] | +59.74 | ±0.63 / ±0.82 (widened) | 6/6 | 2.3e-11 | - | +1694.2k ± 19.1k |
| ch4k [instructions_u] vs cl | +264.94 | [+260.62, +269.31] | +129.46 | ±1.19 / ±1.13 (t) | 6/6 | 1.1e-11 | - | +912.0k ± 14.9k |
| ch4k [instructions_k] vs cl | +158.10 | [+154.92, +161.32] | +94.82 | ±1.24 / ±1.16 (t) | 6/6 | 6.5e-11 | - | +1075.5k ± 20.4k |
| ch4k [context_switches] vs cl | -26.90 | [-28.75, -25.01] | -31.34 | ±2.56 / ±2.06 (t) | 0/6 | 6.1e-07 | - | -0.0k ± 0.0k |
| ch4k [p50_us] vs cl | +104.71 | [+102.28, +107.18] | +71.64 | ±1.20 / ±1.13 (t) | 6/6 | 2.2e-10 | - | +1.4k ± 0.0k |
| ch4k [p99_us] vs cl | +208.88 | [+182.85, +237.32] | +112.78 | ±8.81 / ±6.75 (t) | 6/6 | 4.9e-07 | - | +3.3k ± 0.4k |
| h2in [cycles_u] vs cl | +133.98 | [+131.75, +136.24] | +85.01 | ±0.91 / ±0.96 (widened) | 6/6 | 2.3e-11 | - | +746.0k ± 7.5k |
| h2in [cycles_k] vs cl | +37.14 | [+36.06, +38.23] | +31.58 | ±0.56 / ±0.79 (widened) | 6/6 | 2.9e-10 | - | +769.7k ± 13.5k |
| h2in [instructions_u] vs cl | +141.03 | [+139.26, +142.81] | +87.97 | ±0.41 / ±0.74 (widened) | 6/6 | 3.9e-13 | - | +485.4k ± 3.5k |
| h2in [instructions_k] vs cl | +60.16 | [+58.90, +61.42] | +47.10 | ±0.55 / ±0.79 (widened) | 6/6 | 3.6e-11 | - | +409.2k ± 6.2k |
| h2in [context_switches] vs cl | +54.17 | [+47.63, +61.00] | +43.29 | ±4.34 / ±3.37 (t) | 6/6 | 1.7e-06 | - | +0.0k ± 0.0k |
| h2in [p50_us] vs cl | +171.44 | [+167.71, +175.21] | +99.86 | ±1.38 / ±1.25 (t) | 6/6 | 8.6e-11 | - | +2.3k ± 0.0k |
| h2in [p99_us] vs cl | +379.04 | [+362.82, +395.82] | +156.66 | ±3.44 / ±2.71 (t) | 6/6 | 8.7e-10 | - | +6.1k ± 0.3k |
| cl8k [cycles_u] vs cl | +24.71 | [+23.64, +25.78] | +22.08 | ±0.71 / ±0.86 (widened) | 6/6 | 5.8e-09 | - | +137.6k ± 4.3k |
| cl8k [cycles_k] vs cl | +29.19 | [+28.26, +30.12] | +25.61 | ±0.36 / ±0.72 (widened) | 6/6 | 9.8e-11 | - | +604.9k ± 7.7k |
| cl8k [instructions_u] vs cl | +29.61 | [+28.13, +31.12] | +25.94 | ±1.15 / ±1.10 (t) | 6/6 | 2.9e-08 | - | +102.0k ± 5.2k |
| cl8k [instructions_k] vs cl | +59.69 | [+58.39, +61.01] | +46.81 | ±0.63 / ±0.82 (widened) | 6/6 | 7.4e-11 | - | +406.1k ± 6.6k |
| cl8k [context_switches] vs cl | -14.68 | [-16.45, -12.87] | -15.87 | ±2.09 / ±1.73 (t) | 0/6 | 6.6e-06 | - | -0.0k ± 0.0k |
| cl8k [p50_us] vs cl | +65.36 | [+63.68, +67.05] | +50.29 | ±1.01 / ±1.02 (widened) | 6/6 | 5.5e-10 | - | +0.9k ± 0.0k |
| cl8k [p99_us] vs cl | +90.81 | [+88.65, +92.99] | +64.61 | ±1.14 / ±1.09 (t) | 6/6 | 2.9e-10 | - | +1.4k ± 0.0k |
| cl-A2 [cycles_u] vs cl | -0.13 | [-0.93, +0.68] | -0.13 | ±0.60 / ±0.81 (widened) | 3/6 | 0.61 | - | -0.7k ± 3.3k |
| cl-A2 [cycles_k] vs cl | -0.03 | [-0.72, +0.66] | -0.03 | ±0.23 / ±0.69 (widened) | 3/6 | 0.72 | - | -0.7k ± 4.8k |
| cl-A2 [instructions_u] vs cl | -0.03 | [-0.69, +0.64] | -0.03 | ±0.04 / ±0.67 (widened) | 2/6 | 0.14 | - | -0.1k ± 0.1k |
| cl-A2 [instructions_k] vs cl | +0.05 | [-0.64, +0.75] | +0.05 | ±0.28 / ±0.70 (widened) | 3/6 | 0.64 | - | +0.4k ± 1.9k |
| cl-A2 [context_switches] vs cl | +0.14 | [-0.86, +1.14] | +0.14 | ±0.98 / ±1.00 (widened) | 4/6 | 0.74 | - | +0.0k ± 0.0k |
| cl-A2 [p50_us] vs cl | -0.05 | [-0.77, +0.68] | -0.05 | ±0.38 / ±0.73 (widened) | 3/6 | 0.75 | - | -0.0k ± 0.0k |
| cl-A2 [p99_us] vs cl | +0.04 | [-0.69, +0.77] | +0.04 | ±0.40 / ±0.73 (widened) | 3/6 | 0.81 | - | +0.0k ± 0.0k |

## shape b64k

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | origin CPU share of its set (max) | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ch4k | 6/6 | 812.4k | 420.3k | 392.6k | 219.2k | 157.9k | 1.55 | 527 | 785 | 1.455 | 4000.0–4000.0 | 0.047 | 0.254 |
| ch8k | 6/6 | 734.8k | 396.3k | 338.4k | 189.8k | 124.9k | 1.67 | 477 | 737 | 1.322 | 4000.0–4000.0 | 0.034 | 0.255 |
| cl | 6/6 | 634.1k | 351.4k | 282.3k | 153.3k | 90.9k | 1.67 | 459 | 677 | 1.158 | 4000.0–4000.0 | 0.020 | 0.255 |
| cl-A2 | 6/6 | 635.0k | 352.5k | 282.2k | 153.3k | 91.1k | 1.67 | 458 | 685 | 1.160 | 4000.0–4000.0 | 0.020 | 0.255 |
| cl8k | 6/6 | 698.9k | 363.5k | 334.7k | 164.3k | 124.3k | 1.69 | 443 | 660 | 1.261 | 4000.0–4000.0 | 0.033 | 0.255 |
| h2in | 6/6 | 780.9k | 441.1k | 338.7k | 196.7k | 117.5k | 1.53 | 622 | 1271 | 1.409 | 4000.0–4000.0 | 0.168 | 0.253 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| cl-A2 vs cl | +0.02 | [-0.83, +0.87] | +0.02 | ±0.70 / ±0.85 (widened) | 4/6 | 0.95 | - | +0.1k ± 4.4k |

A/A gate (shape b64k, floor 1.5% simple): **PASS**; A/A reach 0.87% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| ch8k vs cl8k | +5.36 | [+4.12, +6.61] | +5.22 | ±1.18 / ±1.12 (t) | 6/6 | 9.4e-05 | 9.4e-05 | +37.4k ± 8.7k | finding
| ch8k vs cl | +16.26 | [+14.78, +17.76] | +15.07 | ±1.28 / ±1.18 (t) | 6/6 | 7.4e-07 | 1.5e-06 | +102.9k ± 9.0k | finding
| ch4k vs cl | +28.67 | [+27.11, +30.25] | +25.21 | ±1.22 / ±1.15 (t) | 6/6 | 4.5e-08 | 1.8e-07 | +181.4k ± 8.5k | finding
| h2in vs cl | +23.16 | [+21.72, +24.63] | +20.84 | ±1.18 / ±1.12 (t) | 6/6 | 9.7e-08 | 2.9e-07 | +146.6k ± 9.1k | finding

| row (anchor and exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| cl8k vs cl | +10.35 | [+9.27, +11.44] | +9.85 | ±0.95 / ±0.98 (widened) | 6/6 | 1.4e-06 | - | +65.5k ± 6.1k |
| ch4k vs ch8k | +10.67 | [+9.06, +12.32] | +10.14 | ±1.47 / ±1.31 (t) | 6/6 | 1.1e-05 | - | +78.5k ± 11.2k |
| h2in vs cl8k | +11.61 | [+9.67, +13.59] | +10.99 | ±1.76 / ±1.50 (t) | 6/6 | 1.7e-05 | - | +81.1k ± 13.3k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| ch8k [cycles_u] vs cl8k | +8.98 | [+7.65, +10.32] | +8.60 | ±1.22 / ±1.15 (t) | 6/6 | 9.5e-06 | - | +32.7k ± 4.7k |
| ch8k [cycles_k] vs cl8k | +1.42 | [+0.02, +2.84] | +1.41 | ±1.39 / ±1.25 (t) | 5/6 | 0.048 | - | +4.8k ± 4.7k |
| ch8k [instructions_u] vs cl8k | +15.54 | [+14.76, +16.32] | +14.44 | ±0.13 / ±0.67 (widened) | 6/6 | 9.8e-12 | - | +25.5k ± 0.2k |
| ch8k [instructions_k] vs cl8k | +0.75 | [-0.18, +1.69] | +0.75 | ±0.85 / ±0.93 (widened) | 6/6 | 0.073 | - | +0.9k ± 1.1k |
| ch8k [context_switches] vs cl8k | -0.80 | [-3.56, +2.04] | -0.80 | ±2.83 / ±2.26 (t) | 1/6 | 0.5 | - | -0.0k ± 0.0k |
| ch8k [p50_us] vs cl8k | +8.05 | [+5.20, +10.97] | +7.74 | ±2.67 / ±2.14 (t) | 6/6 | 0.00068 | - | +0.0k ± 0.0k |
| ch8k [p99_us] vs cl8k | +12.49 | [+7.81, +17.36] | +11.77 | ±4.24 / ±3.30 (t) | 6/6 | 0.00084 | - | +0.1k ± 0.0k |
| ch8k [cycles_u] vs cl | +12.88 | [+11.45, +14.33] | +12.12 | ±1.28 / ±1.18 (t) | 6/6 | 2.2e-06 | - | +45.2k ± 4.7k |
| ch8k [cycles_k] vs cl | +20.48 | [+18.65, +22.33] | +18.63 | ±1.53 / ±1.34 (t) | 6/6 | 6.2e-07 | - | +57.7k ± 5.1k |
| ch8k [instructions_u] vs cl | +23.82 | [+23.00, +24.66] | +21.37 | ±0.10 / ±0.67 (widened) | 6/6 | 4.1e-13 | - | +36.5k ± 0.2k |
| ch8k [instructions_k] vs cl | +37.57 | [+36.29, +38.86] | +31.90 | ±0.86 / ±0.93 (widened) | 6/6 | 2.4e-09 | - | +34.2k ± 1.0k |
| ch8k [context_switches] vs cl | +0.24 | [-2.47, +3.02] | +0.24 | ±2.74 / ±2.19 (t) | 2/6 | 0.83 | - | +0.0k ± 0.0k |
| ch8k [p50_us] vs cl | +4.15 | [+1.43, +6.95] | +4.07 | ±2.65 / ±2.13 (t) | 6/6 | 0.011 | - | +0.0k ± 0.0k |
| ch8k [p99_us] vs cl | +9.07 | [+4.02, +14.37] | +8.68 | ±4.74 / ±3.67 (t) | 6/6 | 0.0053 | - | +0.1k ± 0.0k |
| ch4k [cycles_u] vs cl | +20.00 | [+18.56, +21.46] | +18.23 | ±1.21 / ±1.14 (t) | 6/6 | 2.2e-07 | - | +70.2k ± 4.5k |
| ch4k [cycles_k] vs cl | +39.48 | [+37.66, +41.33] | +33.28 | ±1.31 / ±1.20 (t) | 6/6 | 1.6e-08 | - | +111.2k ± 4.3k |
| ch4k [instructions_u] vs cl | +43.01 | [+41.96, +44.07] | +35.78 | ±0.42 / ±0.74 (widened) | 6/6 | 3.6e-11 | - | +65.9k ± 0.9k |
| ch4k [instructions_k] vs cl | +73.42 | [+71.96, +74.90] | +55.06 | ±0.69 / ±0.85 (widened) | 6/6 | 5.3e-11 | - | +66.8k ± 0.9k |
| ch4k [context_switches] vs cl | -6.72 | [-10.38, -2.90] | -6.95 | ±4.01 / ±3.13 (t) | 0/6 | 0.0067 | - | -0.0k ± 0.0k |
| ch4k [p50_us] vs cl | +14.52 | [+12.17, +16.91] | +13.56 | ±2.07 / ±1.71 (t) | 6/6 | 1.3e-05 | - | +0.1k ± 0.0k |
| ch4k [p99_us] vs cl | +16.10 | [+11.74, +20.63] | +14.92 | ±3.83 / ±2.99 (t) | 6/6 | 0.00017 | - | +0.1k ± 0.0k |
| h2in [cycles_u] vs cl | +25.75 | [+24.17, +27.35] | +22.91 | ±1.26 / ±1.17 (t) | 6/6 | 8.5e-08 | - | +90.4k ± 5.4k |
| h2in [cycles_k] vs cl | +19.94 | [+18.10, +21.81] | +18.18 | ±1.54 / ±1.35 (t) | 6/6 | 7.3e-07 | - | +56.2k ± 5.1k |
| h2in [instructions_u] vs cl | +28.36 | [+27.50, +29.24] | +24.97 | ±0.17 / ±0.68 (widened) | 6/6 | 2.6e-12 | - | +43.5k ± 0.3k |
| h2in [instructions_k] vs cl | +29.71 | [+28.00, +31.45] | +26.01 | ±1.33 / ±1.21 (t) | 6/6 | 5.8e-08 | - | +27.0k ± 1.5k |
| h2in [context_switches] vs cl | -8.90 | [-12.03, -5.65] | -9.32 | ±3.50 / ±2.75 (t) | 0/6 | 0.001 | - | -0.0k ± 0.0k |
| h2in [p50_us] vs cl | +36.41 | [+29.53, +43.65] | +31.05 | ±5.17 / ±4.00 (t) | 6/6 | 2.1e-05 | - | +0.2k ± 0.0k |
| h2in [p99_us] vs cl | +88.90 | [+77.60, +100.92] | +63.60 | ±6.17 / ±4.75 (t) | 6/6 | 1.4e-06 | - | +0.6k ± 0.1k |
| cl8k [cycles_u] vs cl | +3.58 | [+2.40, +4.77] | +3.52 | ±1.14 / ±1.10 (t) | 6/6 | 0.00052 | - | +12.6k ± 4.0k |
| cl8k [cycles_k] vs cl | +18.79 | [+17.69, +19.90] | +17.22 | ±0.85 / ±0.93 (widened) | 6/6 | 4.9e-08 | - | +52.9k ± 2.4k |
| cl8k [instructions_u] vs cl | +7.17 | [+6.45, +7.89] | +6.92 | ±0.14 / ±0.67 (widened) | 6/6 | 5.2e-10 | - | +11.0k ± 0.2k |
| cl8k [instructions_k] vs cl | +36.55 | [+35.55, +37.56] | +31.15 | ±0.41 / ±0.73 (widened) | 6/6 | 6.4e-11 | - | +33.2k ± 0.5k |
| cl8k [context_switches] vs cl | +1.05 | [-3.63, +5.95] | +1.04 | ±4.74 / ±3.67 (t) | 4/6 | 0.6 | - | +0.0k ± 0.0k |
| cl8k [p50_us] vs cl | -3.60 | [-6.87, -0.22] | -3.67 | ±3.45 / ±2.72 (t) | 1/6 | 0.041 | - | -0.0k ± 0.0k |
| cl8k [p99_us] vs cl | -3.04 | [-6.41, +0.46] | -3.08 | ±3.54 / ±2.78 (t) | 1/6 | 0.076 | - | -0.0k ± 0.0k |
| cl-A2 [cycles_u] vs cl | +0.02 | [-0.92, +0.96] | +0.02 | ±0.87 / ±0.94 (widened) | 3/6 | 0.96 | - | +0.1k ± 3.0k |
| cl-A2 [cycles_k] vs cl | +0.01 | [-0.90, +0.94] | +0.01 | ±0.83 / ±0.92 (widened) | 3/6 | 0.97 | - | +0.0k ± 2.3k |
| cl-A2 [instructions_u] vs cl | -0.00 | [-0.67, +0.67] | -0.00 | ±0.04 / ±0.67 (widened) | 3/6 | 0.97 | - | -0.0k ± 0.1k |
| cl-A2 [instructions_k] vs cl | +0.20 | [-0.57, +0.97] | +0.20 | ±0.49 / ±0.77 (widened) | 4/6 | 0.35 | - | +0.2k ± 0.5k |
| cl-A2 [context_switches] vs cl | +0.94 | [-2.04, +4.01] | +0.94 | ±3.00 / ±2.38 (t) | 4/6 | 0.46 | - | +0.0k ± 0.0k |
| cl-A2 [p50_us] vs cl | -0.71 | [-2.55, +1.17] | -0.71 | ±1.87 / ±1.58 (t) | 2/6 | 0.37 | - | -0.0k ± 0.0k |
| cl-A2 [p99_us] vs cl | -0.14 | [-3.60, +3.44] | -0.14 | ±3.52 / ±2.77 (t) | 3/6 | 0.92 | - | -0.0k ± 0.0k |

## patch gate (candidate 5): ch8k vs cl8k, simple %; no patch when under 3% at 64 KiB and under 6% at 1 MiB

b64k: +5.36% [+4.12, +6.61] against 3%: at or above 
b1m: +8.76% [+7.99, +9.53] against 6%: at or above 

## per-byte slopes from 64 KiB to 1 MiB: (cycles per request on b1m - on b64k) / 983,040 bytes, per round

| arm | cycles per body byte, mean | 95% t interval | user | kernel | rounds |
|---|---|---|---|---|---|
| ch4k | 4.346 | [4.329, 4.364] | 0.914 | 3.432 | 6 |
| ch8k | 2.982 | [2.963, 3.001] | 0.599 | 2.383 | 6 |
| cl | 2.031 | [2.015, 2.047] | 0.209 | 1.822 | 6 |
| cl-A2 | 2.030 | [2.018, 2.042] | 0.208 | 1.821 | 6 |
| cl8k | 2.720 | [2.711, 2.729] | 0.336 | 2.383 | 6 |
| h2in | 3.424 | [3.404, 3.444] | 0.876 | 2.548 | 6 |
