# s1a-hop: primary metric cycles_total_all (cycles user+kernel per request, both hops)

legs: 64 current, 64 valid; evidence failing: 0

## shape s

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | ctx sw /req | p50 µs | p99 µs | client 2xx/s | upstream conns (end of window) |
|---|---|---|---|---|---|---|---|---|---|---|
| one-ppd | 8/8 | 525.5k | 345.8k | 178.6k | 164.6k | 1.56 | 394 | 639 | 5200.0–5200.0 | 1024–1024 |
| one-uds | 8/8 | 500.9k | 352.2k | 148.4k | 165.2k | 1.94 | 361 | 548 | 5200.0–5200.0 | 0–0 |
| pair | 8/8 | 1042.2k | 342.9k | 169.1k | 163.6k | 1.56 | 641 | 1029 | 5200.0–5200.0 | 1024–1024 |
| pair-A2 | 8/8 | 1041.6k | 343.7k | 169.7k | 163.6k | 1.57 | 647 | 1026 | 5200.0–5200.0 | 1024–1024 |
| pair-l4 | 8/8 | 698.6k | 344.1k | 165.9k | 164.3k | 1.51 | 468 | 760 | 5200.0–5200.0 | 1024–1024 |
| pair-mtls | 8/8 | 1103.7k | 372.7k | 171.5k | 180.0k | 1.51 | 708 | 1169 | 5200.0–5200.0 | 1024–1024 |
| pair-mtls-l4 | 8/8 | 761.8k | 373.0k | 170.3k | 180.7k | 1.49 | 510 | 824 | 5200.0–5200.0 | 1024–1024 |
| pair-uds | 8/8 | 979.5k | 334.0k | 144.5k | 165.1k | 2.46 | 590 | 922 | 5200.0–5200.0 | 1024–1024 |

| arm | hop A cycles /req | hop A user | hop A kernel | hop B cycles /req | hop B user | hop B kernel | hop B instr user |
|---|---|---|---|---|---|---|---|
| pair | 513.0k | 342.9k | 169.1k | 529.3k | 351.8k | 177.4k | 177.4k |
| pair-A2 | 513.4k | 343.7k | 169.7k | 527.6k | 350.7k | 176.7k | 177.4k |
| pair-l4 | 511.1k | 344.1k | 165.9k | 187.4k | 46.7k | 140.8k | 23.6k |
| pair-mtls | 543.9k | 372.7k | 171.5k | 557.5k | 381.0k | 176.3k | 194.7k |
| pair-mtls-l4 | 543.3k | 373.0k | 170.3k | 217.7k | 69.7k | 148.0k | 39.4k |
| pair-uds | 478.7k | 334.0k | 144.5k | 500.8k | 338.5k | 162.3k | 178.9k |

| row (A/A, cycles_total_all) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| pair-A2 vs pair | +0.04 | [-0.82, +0.90] | +0.04 | ±0.65 / ±0.86 (widened) | 3/8 | 0.9 | - |

A/A gate (shape s, floor 1.0% simple): **PASS**; A/A reach 0.89% (simple)

| row (confirmatory, cycles_total_all) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| pair-l4 vs pair | -32.92 | [-33.55, -32.29] | -39.93 | ±0.80 / ±0.94 (widened) | 0/8 | 8.2e-13 | 3.3e-12 | finding
| pair-mtls-l4 vs pair-mtls | -30.83 | [-31.52, -30.14] | -36.87 | ±0.90 / ±1.00 (widened) | 0/8 | 3.4e-12 | 1e-11 | finding
| pair-uds vs pair | -5.98 | [-6.78, -5.17] | -6.16 | ±0.65 / ±0.86 (widened) | 0/8 | 9.1e-08 | 1.8e-07 | finding
| one-uds vs one-ppd | -4.49 | [-5.68, -3.29] | -4.60 | ±1.25 / ±1.23 (t) | 0/8 | 5.4e-05 | 5.4e-05 | finding

| row (anchor and exploratory, cycles_total_all) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| pair vs one-ppd | +98.61 | [+96.60, +100.64] | +68.62 | ±0.93 / ±1.02 (widened) | 8/8 | 5.2e-14 | - |
| pair-mtls vs pair | +5.84 | [+4.88, +6.81] | +5.68 | ±0.75 / ±0.91 (widened) | 8/8 | 4.3e-07 | - |
| pair-l4 vs one-ppd | +33.22 | [+32.06, +34.39] | +28.68 | ±0.68 / ±0.87 (widened) | 8/8 | 2.8e-12 | - |
| pair-mtls-l4 vs pair-l4 | +9.14 | [+8.26, +10.02] | +8.74 | ±0.55 / ±0.81 (widened) | 8/8 | 2.5e-09 | - |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| pair-l4 [cycles_u] vs pair | +0.42 | [-0.59, +1.44] | +0.42 | ±0.92 / ±1.01 (widened) | 4/8 | 0.32 | - |
| pair-l4 [cycles_k] vs pair | -1.48 | [-2.60, -0.34] | -1.49 | ±1.13 / ±1.15 (widened) | 1/8 | 0.017 | - |
| pair-l4 [instructions_u] vs pair | +0.41 | [-0.26, +1.08] | +0.41 | ±0.03 / ±0.67 (widened) | 8/8 | 1.2e-08 | - |
| pair-l4 [instructions_k] vs pair | -0.67 | [-1.47, +0.13] | -0.68 | ±0.55 / ±0.81 (widened) | 1/8 | 0.023 | - |
| pair-l4 [context_switches] vs pair | -4.45 | [-7.41, -1.39] | -4.55 | ±3.15 / ±2.70 (t) | 1/8 | 0.011 | - |
| pair-l4 [hop2:cycles_total] vs pair | -64.58 | [-64.89, -64.28] | -103.80 | ±0.65 / ±0.86 (widened) | 0/8 | 2.2e-16 | - |
| pair-l4 [hop2:cycles_u] vs pair | -86.75 | [-86.87, -86.62] | -202.09 | ±0.80 / ±0.94 (widened) | 0/8 | 0 | - |
| pair-l4 [hop2:cycles_k] vs pair | -20.67 | [-21.51, -19.82] | -23.15 | ±1.00 / ±1.06 (widened) | 0/8 | 1.8e-10 | - |
| pair-l4 [hop2:instructions_u] vs pair | -86.67 | [-86.76, -86.57] | -201.48 | ±0.24 / ±0.70 (widened) | 0/8 | 0 | - |
| pair-l4 [p50_us] vs pair | -26.44 | [-27.64, -25.23] | -30.71 | ±1.64 / ±1.52 (t) | 0/8 | 7.9e-10 | - |
| pair-l4 [p99_us] vs pair | -24.44 | [-27.12, -21.65] | -28.02 | ±3.62 / ±3.07 (t) | 0/8 | 3.6e-07 | - |
| pair-mtls-l4 [cycles_u] vs pair-mtls | -0.01 | [-0.90, +0.88] | -0.01 | ±0.71 / ±0.89 (widened) | 6/8 | 0.96 | - |
| pair-mtls-l4 [cycles_k] vs pair-mtls | -0.88 | [-2.11, +0.37] | -0.88 | ±1.25 / ±1.23 (t) | 2/8 | 0.14 | - |
| pair-mtls-l4 [instructions_u] vs pair-mtls | +0.38 | [-0.29, +1.05] | +0.38 | ±0.03 / ±0.67 (widened) | 8/8 | 5.7e-09 | - |
| pair-mtls-l4 [instructions_k] vs pair-mtls | +0.34 | [-0.40, +1.08] | +0.34 | ±0.39 / ±0.74 (widened) | 6/8 | 0.08 | - |
| pair-mtls-l4 [context_switches] vs pair-mtls | -0.81 | [-2.97, +1.40] | -0.81 | ±2.20 / ±1.94 (t) | 3/8 | 0.41 | - |
| pair-mtls-l4 [hop2:cycles_total] vs pair-mtls | -60.77 | [-61.45, -60.07] | -93.57 | ±1.76 / ±1.60 (t) | 0/8 | 5.3e-13 | - |
| pair-mtls-l4 [hop2:cycles_u] vs pair-mtls | -81.59 | [-81.97, -81.20] | -169.24 | ±2.08 / ±1.85 (t) | 0/8 | 2.7e-14 | - |
| pair-mtls-l4 [hop2:cycles_k] vs pair-mtls | -15.81 | [-17.34, -14.25] | -17.20 | ±1.84 / ±1.66 (t) | 0/8 | 9.6e-08 | - |
| pair-mtls-l4 [hop2:instructions_u] vs pair-mtls | -79.76 | [-79.90, -79.62] | -159.75 | ±0.24 / ±0.70 (widened) | 0/8 | 0 | - |
| pair-mtls-l4 [p50_us] vs pair-mtls | -27.63 | [-28.57, -26.67] | -32.34 | ±1.31 / ±1.28 (t) | 0/8 | 1.2e-10 | - |
| pair-mtls-l4 [p99_us] vs pair-mtls | -30.06 | [-32.20, -27.86] | -35.76 | ±3.10 / ±2.65 (t) | 0/8 | 2.3e-08 | - |
| pair-uds [cycles_u] vs pair | -2.73 | [-3.56, -1.89] | -2.76 | ±0.65 / ±0.86 (widened) | 0/8 | 2.1e-05 | - |
| pair-uds [cycles_k] vs pair | -14.57 | [-15.30, -13.83] | -15.74 | ±0.65 / ±0.86 (widened) | 0/8 | 1.3e-10 | - |
| pair-uds [instructions_u] vs pair | +0.91 | [+0.24, +1.59] | +0.91 | ±0.02 / ±0.67 (widened) | 8/8 | 2.4e-13 | - |
| pair-uds [instructions_k] vs pair | -15.02 | [-15.63, -14.41] | -16.28 | ±0.33 / ±0.72 (widened) | 0/8 | 9.5e-13 | - |
| pair-uds [context_switches] vs pair | +57.56 | [+55.48, +59.68] | +45.47 | ±1.33 / ±1.29 (t) | 8/8 | 1.2e-11 | - |
| pair-uds [hop2:cycles_total] vs pair | -5.34 | [-6.34, -4.32] | -5.48 | ±1.01 / ±1.07 (widened) | 0/8 | 4e-06 | - |
| pair-uds [hop2:cycles_u] vs pair | -3.75 | [-4.75, -2.73] | -3.82 | ±0.98 / ±1.05 (widened) | 0/8 | 3.8e-05 | - |
| pair-uds [hop2:cycles_k] vs pair | -8.49 | [-9.58, -7.38] | -8.87 | ±1.20 / ±1.20 (t) | 0/8 | 5.1e-07 | - |
| pair-uds [hop2:instructions_u] vs pair | +0.86 | [+0.19, +1.53] | +0.85 | ±0.02 / ±0.67 (widened) | 8/8 | 5.2e-13 | - |
| pair-uds [p50_us] vs pair | -8.04 | [-9.26, -6.81] | -8.38 | ±1.33 / ±1.29 (t) | 0/8 | 1.5e-06 | - |
| pair-uds [p99_us] vs pair | -8.77 | [-11.86, -5.57] | -9.18 | ±3.45 / ±2.94 (t) | 0/8 | 0.00041 | - |
| one-uds [cycles_u] vs one-ppd | +1.87 | [+0.72, +3.03] | +1.85 | ±1.11 / ±1.14 (widened) | 7/8 | 0.0056 | - |
| one-uds [cycles_k] vs one-ppd | -16.81 | [-18.15, -15.45] | -18.41 | ±1.62 / ±1.50 (t) | 0/8 | 2.5e-08 | - |
| one-uds [instructions_u] vs one-ppd | +0.36 | [-0.30, +1.03] | +0.36 | ±0.01 / ±0.67 (widened) | 8/8 | 1.9e-11 | - |
| one-uds [instructions_k] vs one-ppd | -23.50 | [-24.09, -22.90] | -26.79 | ±0.48 / ±0.78 (widened) | 0/8 | 3.8e-13 | - |
| one-uds [context_switches] vs one-ppd | +23.30 | [+20.17, +26.52] | +20.95 | ±2.57 / ±2.23 (t) | 8/8 | 2.5e-07 | - |
| one-uds [p50_us] vs one-ppd | -8.53 | [-10.10, -6.93] | -8.91 | ±1.73 / ±1.58 (t) | 0/8 | 5.8e-06 | - |
| one-uds [p99_us] vs one-ppd | -15.26 | [-17.49, -12.96] | -16.55 | ±2.68 / ±2.32 (t) | 0/8 | 1.7e-06 | - |
| pair [cycles_u] vs one-ppd | -0.78 | [-1.69, +0.13] | -0.79 | ±0.76 / ±0.92 (widened) | 1/8 | 0.045 | - |
| pair [cycles_k] vs one-ppd | -5.31 | [-6.45, -4.15] | -5.45 | ±1.22 / ±1.21 (t) | 0/8 | 1.5e-05 | - |
| pair [instructions_u] vs one-ppd | -0.60 | [-1.26, +0.06] | -0.60 | ±0.02 / ±0.67 (widened) | 0/8 | 2.4e-11 | - |
| pair [instructions_k] vs one-ppd | -4.82 | [-5.51, -4.12] | -4.94 | ±0.36 / ±0.73 (widened) | 0/8 | 7.2e-09 | - |
| pair [context_switches] vs one-ppd | -0.38 | [-2.70, +2.00] | -0.38 | ±2.36 / ±2.07 (t) | 3/8 | 0.72 | - |
| pair [p50_us] vs one-ppd | +62.75 | [+59.73, +65.83] | +48.71 | ±1.87 / ±1.69 (t) | 8/8 | 7.9e-11 | - |
| pair [p99_us] vs one-ppd | +58.45 | [+52.86, +64.24] | +46.02 | ±3.59 / ±3.05 (t) | 8/8 | 1.1e-08 | - |
| pair-mtls [cycles_u] vs pair | +8.92 | [+7.79, +10.05] | +8.54 | ±0.96 / ±1.04 (widened) | 8/8 | 1.4e-07 | - |
| pair-mtls [cycles_k] vs pair | +1.63 | [+0.24, +3.05] | +1.62 | ±1.38 / ±1.32 (t) | 6/8 | 0.028 | - |
| pair-mtls [instructions_u] vs pair | +10.04 | [+9.30, +10.77] | +9.56 | ±0.02 / ±0.67 (widened) | 8/8 | 0 | - |
| pair-mtls [instructions_k] vs pair | -0.49 | [-1.22, +0.24] | -0.49 | ±0.37 / ±0.74 (widened) | 2/8 | 0.017 | - |
| pair-mtls [context_switches] vs pair | -3.64 | [-5.60, -1.64] | -3.70 | ±2.05 / ±1.83 (t) | 0/8 | 0.0037 | - |
| pair-mtls [hop2:cycles_total] vs pair | +5.19 | [+4.11, +6.28] | +5.06 | ±0.96 / ±1.04 (widened) | 8/8 | 4.8e-06 | - |
| pair-mtls [hop2:cycles_u] vs pair | +8.18 | [+7.20, +9.16] | +7.86 | ±0.74 / ±0.91 (widened) | 8/8 | 4.1e-08 | - |
| pair-mtls [hop2:cycles_k] vs pair | -0.73 | [-2.41, +0.98] | -0.73 | ±1.71 / ±1.56 (t) | 4/8 | 0.34 | - |
| pair-mtls [hop2:instructions_u] vs pair | +9.76 | [+9.04, +10.50] | +9.32 | ±0.02 / ±0.67 (widened) | 8/8 | 0 | - |
| pair-mtls [p50_us] vs pair | +10.51 | [+8.05, +13.03] | +9.99 | ±2.25 / ±1.98 (t) | 8/8 | 1.6e-05 | - |
| pair-mtls [p99_us] vs pair | +14.98 | [+10.38, +19.77] | +13.96 | ±4.08 / ±3.45 (t) | 8/8 | 8.5e-05 | - |
