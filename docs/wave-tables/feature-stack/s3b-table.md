# s3b-chain: primary metric cycles_total (cycles user+kernel per request, Envoy process)

legs: 72 current, 72 valid; evidence failing: 0; superseded (replaced by the harness): 0; target rates: fh [8000]/s, s [5200]/s

## shape fh

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | side services, CPU share of their set (max) | busiest worker share (max) | statsd datagrams /req (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f0 | 6/6 | 279.9k | 197.6k | 82.2k | 164.7k | 29.4k | 0.85 | 215 | 367 | 1.025 | 8000.0–8000.0 | 0.000 | 0.254 | - |
| f0-A2 | 6/6 | 278.6k | 196.8k | 81.9k | 164.7k | 29.4k | 0.84 | 214 | 369 | 1.018 | 8000.0–8000.0 | 0.000 | 0.257 | - |
| f10 | 6/6 | 327.4k | 244.2k | 83.2k | 190.6k | 29.0k | 0.76 | 243 | 413 | 1.184 | 8000.0–8000.0 | 0.000 | 0.255 | - |
| f10-off | 6/6 | 283.2k | 200.6k | 82.8k | 165.9k | 29.3k | 0.83 | 216 | 369 | 1.033 | 8000.0–8000.0 | 0.000 | 0.259 | - |
| idle-off | 6/6 | 269.8k | 187.9k | 82.4k | 159.0k | 29.5k | 0.86 | 211 | 361 | 0.991 | 8000.0–8000.0 | 0.000 | 0.255 | - |
| timers-off-all | 6/6 | 270.8k | 188.3k | 82.2k | 159.0k | 29.4k | 0.85 | 212 | 361 | 0.994 | 8000.0–8000.0 | 0.000 | 0.259 | - |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| f0-A2 vs f0 | +0.03 | [-2.16, +2.26] | +0.03 | ±2.21 / ±1.81 (t) | 3/6 | 0.98 | - | +0.1k ± 6.2k | PASS

A/A gate (shape fh, floor 1.0%): **PASS**; A/A reach 2.24% (simple); largest A/A excursion 0.03 log-%

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| f10 vs f0 | +17.01 | [+15.13, +18.93] | +15.71 | ±1.63 / ±1.41 (t) | 6/6 | 2e-06 | 1.4e-05 | +47.6k ± 4.9k | finding
| f10-off vs f0 | +0.94 | [-0.94, +2.85] | +0.93 | ±1.87 / ±1.58 (t) | 3/6 | 0.26 | 0.51 | +2.6k ± 5.3k | not a finding
| idle-off vs f0 | -3.48 | [-5.22, -1.71] | -3.54 | ±1.82 / ±1.54 (t) | 0/6 | 0.004 | 0.012 | -9.7k ± 5.0k | finding
| timers-off-all vs f0 | -3.26 | [-4.13, -2.38] | -3.31 | ±0.79 / ±0.90 (widened) | 0/6 | 0.00012 | 0.00061 | -9.1k ± 2.2k | finding

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| timers-off-all vs idle-off | +0.23 | [-1.23, +1.72] | +0.23 | ±1.47 / ±1.31 (t) | 4/6 | 0.7 | - | +0.6k ± 4.0k |
| f10-off vs f10 | -13.74 | [-15.39, -12.06] | -14.78 | ±1.93 / ±1.62 (t) | 0/6 | 6.3e-06 | - | -45.0k ± 5.7k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| f10 [cycles_u] vs f0 | +23.51 | [+21.51, +25.55] | +21.12 | ±1.64 / ±1.41 (t) | 6/6 | 4.7e-07 | - | +46.5k ± 3.5k |
| f10 [cycles_k] vs f0 | +1.43 | [-0.73, +3.63] | +1.42 | ±2.15 / ±1.77 (t) | 4/6 | 0.15 | - | +1.2k ± 1.8k |
| f10 [instructions_u] vs f0 | +15.72 | [+14.95, +16.49] | +14.60 | ±0.02 / ±0.67 (widened) | 6/6 | 2.2e-16 | - | +25.9k ± 0.0k |
| f10 [instructions_k] vs f0 | -1.09 | [-2.57, +0.40] | -1.10 | ±1.50 / ±1.32 (t) | 1/6 | 0.12 | - | -0.3k ± 0.4k |
| f10 [context_switches] vs f0 | -9.13 | [-14.77, -3.12] | -9.57 | ±6.41 / ±4.93 (t) | 1/6 | 0.012 | - | -0.0k ± 0.0k |
| f10 [p50_us] vs f0 | +12.91 | [+10.56, +15.31] | +12.14 | ±2.10 / ±1.74 (t) | 6/6 | 2.5e-05 | - | +0.0k ± 0.0k |
| f10 [p99_us] vs f0 | +12.40 | [+9.92, +14.93] | +11.69 | ±2.23 / ±1.82 (t) | 6/6 | 4e-05 | - | +0.0k ± 0.0k |
| f10-off [cycles_u] vs f0 | +1.10 | [-0.78, +3.02] | +1.09 | ±1.88 / ±1.58 (t) | 5/6 | 0.19 | - | +2.2k ± 3.7k |
| f10-off [cycles_k] vs f0 | +0.55 | [-1.37, +2.51] | +0.55 | ±1.93 / ±1.61 (t) | 3/6 | 0.5 | - | +0.5k ± 1.6k |
| f10-off [instructions_u] vs f0 | +0.70 | [+0.03, +1.37] | +0.70 | ±0.01 / ±0.67 (widened) | 6/6 | 5.9e-12 | - | +1.2k ± 0.0k |
| f10-off [instructions_k] vs f0 | +0.06 | [-0.71, +0.83] | +0.06 | ±0.49 / ±0.77 (widened) | 4/6 | 0.78 | - | +0.0k ± 0.1k |
| f10-off [context_switches] vs f0 | -1.17 | [-2.34, +0.01] | -1.18 | ±1.19 / ±1.13 (t) | 1/6 | 0.052 | - | -0.0k ± 0.0k |
| f10-off [p50_us] vs f0 | +0.42 | [-0.54, +1.38] | +0.41 | ±0.90 / ±0.96 (widened) | 5/6 | 0.29 | - | +0.0k ± 0.0k |
| f10-off [p99_us] vs f0 | +0.37 | [-0.73, +1.49] | +0.37 | ±1.10 / ±1.07 (t) | 3/6 | 0.42 | - | +0.0k ± 0.0k |
| idle-off [cycles_u] vs f0 | -5.03 | [-6.95, -3.08] | -5.16 | ±2.03 / ±1.69 (t) | 0/6 | 0.0013 | - | -9.9k ± 3.9k |
| idle-off [cycles_k] vs f0 | +0.24 | [-1.62, +2.14] | +0.24 | ±1.87 / ±1.58 (t) | 3/6 | 0.75 | - | +0.2k ± 1.5k |
| idle-off [instructions_u] vs f0 | -3.51 | [-4.15, -2.86] | -3.57 | ±0.01 / ±0.67 (widened) | 0/6 | 1.8e-14 | - | -5.8k ± 0.0k |
| idle-off [instructions_k] vs f0 | +0.62 | [-0.62, +1.88] | +0.62 | ±1.24 / ±1.16 (t) | 4/6 | 0.26 | - | +0.2k ± 0.4k |
| idle-off [context_switches] vs f0 | +3.07 | [-0.24, +6.49] | +3.02 | ±3.26 / ±2.58 (t) | 5/6 | 0.063 | - | +0.0k ± 0.0k |
| idle-off [p50_us] vs f0 | -1.71 | [-2.92, -0.48] | -1.73 | ±1.24 / ±1.16 (t) | 1/6 | 0.016 | - | -0.0k ± 0.0k |
| idle-off [p99_us] vs f0 | -2.32 | [-4.50, -0.09] | -2.35 | ±2.26 / ±1.84 (t) | 1/6 | 0.044 | - | -0.0k ± 0.0k |
| timers-off-all [cycles_u] vs f0 | -4.68 | [-5.55, -3.81] | -4.80 | ±0.82 / ±0.91 (widened) | 0/6 | 2.4e-05 | - | -9.3k ± 1.6k |
| timers-off-all [cycles_k] vs f0 | +0.16 | [-1.53, +1.88] | +0.16 | ±1.70 / ±1.46 (t) | 3/6 | 0.82 | - | +0.1k ± 1.4k |
| timers-off-all [instructions_u] vs f0 | -3.51 | [-4.15, -2.87] | -3.58 | ±0.01 / ±0.67 (widened) | 0/6 | 8e-15 | - | -5.8k ± 0.0k |
| timers-off-all [instructions_k] vs f0 | +0.30 | [-0.76, +1.36] | +0.30 | ±1.05 / ±1.04 (t) | 3/6 | 0.5 | - | +0.1k ± 0.3k |
| timers-off-all [context_switches] vs f0 | +0.57 | [-2.11, +3.33] | +0.57 | ±2.70 / ±2.17 (t) | 3/6 | 0.61 | - | +0.0k ± 0.0k |
| timers-off-all [p50_us] vs f0 | -1.46 | [-2.37, -0.55] | -1.47 | ±0.84 / ±0.92 (widened) | 0/6 | 0.0063 | - | -0.0k ± 0.0k |
| timers-off-all [p99_us] vs f0 | -1.94 | [-3.83, -0.02] | -1.96 | ±1.95 / ±1.63 (t) | 1/6 | 0.049 | - | -0.0k ± 0.0k |
| timers-off-all [cycles_u] vs idle-off | +0.37 | [-1.24, +2.00] | +0.37 | ±1.61 / ±1.40 (t) | 4/6 | 0.58 | - | +0.7k ± 3.0k |
| timers-off-all [cycles_k] vs idle-off | -0.08 | [-1.51, +1.37] | -0.08 | ±1.44 / ±1.29 (t) | 3/6 | 0.89 | - | -0.1k ± 1.2k |
| timers-off-all [instructions_u] vs idle-off | -0.01 | [-0.67, +0.66] | -0.01 | ±0.01 / ±0.67 (widened) | 2/6 | 0.1 | - | -0.0k ± 0.0k |
| timers-off-all [instructions_k] vs idle-off | -0.32 | [-1.31, +0.68] | -0.32 | ±0.98 / ±1.00 (widened) | 1/6 | 0.44 | - | -0.1k ± 0.3k |
| timers-off-all [context_switches] vs idle-off | -2.42 | [-4.36, -0.44] | -2.45 | ±2.01 / ±1.67 (t) | 1/6 | 0.026 | - | -0.0k ± 0.0k |
| timers-off-all [p50_us] vs idle-off | +0.25 | [-0.56, +1.07] | +0.25 | ±0.61 / ±0.81 (widened) | 4/6 | 0.34 | - | +0.0k ± 0.0k |
| timers-off-all [p99_us] vs idle-off | +0.38 | [-0.44, +1.21] | +0.38 | ±0.64 / ±0.83 (widened) | 3/6 | 0.18 | - | +0.0k ± 0.0k |
| f0-A2 [cycles_u] vs f0 | +0.08 | [-2.14, +2.36] | +0.08 | ±2.25 / ±1.84 (t) | 3/6 | 0.93 | - | +0.2k ± 4.5k |
| f0-A2 [cycles_k] vs f0 | -0.10 | [-2.37, +2.23] | -0.10 | ±2.31 / ±1.88 (t) | 2/6 | 0.92 | - | -0.1k ± 1.9k |
| f0-A2 [instructions_u] vs f0 | -0.00 | [-0.67, +0.67] | -0.00 | ±0.01 / ±0.67 (widened) | 3/6 | 0.46 | - | -0.0k ± 0.0k |
| f0-A2 [instructions_k] vs f0 | +0.11 | [-1.07, +1.32] | +0.11 | ±1.19 / ±1.13 (t) | 4/6 | 0.82 | - | +0.0k ± 0.3k |
| f0-A2 [context_switches] vs f0 | -0.54 | [-4.39, +3.47] | -0.54 | ±3.95 / ±3.09 (t) | 4/6 | 0.74 | - | -0.0k ± 0.0k |
| f0-A2 [p50_us] vs f0 | +0.12 | [-1.24, +1.50] | +0.12 | ±1.37 / ±1.24 (t) | 3/6 | 0.83 | - | +0.0k ± 0.0k |
| f0-A2 [p99_us] vs f0 | +0.18 | [-1.54, +1.93] | +0.18 | ±1.73 / ±1.48 (t) | 3/6 | 0.8 | - | +0.0k ± 0.0k |

## shape s

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | side services, CPU share of their set (max) | busiest worker share (max) | statsd datagrams /req (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f0 | 6/6 | 527.3k | 345.6k | 180.6k | 163.8k | 71.4k | 1.59 | 404 | 634 | 1.256 | 5200.0–5200.0 | 0.022 | 0.254 | - |
| f0-A2 | 6/6 | 525.9k | 345.6k | 179.8k | 163.9k | 71.6k | 1.62 | 399 | 625 | 1.257 | 5200.0–5200.0 | 0.022 | 0.253 | - |
| f10 | 6/6 | 575.0k | 394.2k | 180.8k | 191.1k | 71.4k | 1.56 | 432 | 715 | 1.360 | 5200.0–5200.0 | 0.022 | 0.254 | - |
| f10-off | 6/6 | 523.6k | 345.0k | 179.0k | 165.1k | 71.5k | 1.59 | 398 | 624 | 1.251 | 5200.0–5200.0 | 0.022 | 0.255 | - |
| idle-off | 6/6 | 511.2k | 331.4k | 179.6k | 155.8k | 71.5k | 1.62 | 389 | 605 | 1.219 | 5200.0–5200.0 | 0.022 | 0.253 | - |
| timers-off-all | 6/6 | 505.1k | 325.8k | 179.6k | 152.2k | 71.7k | 1.65 | 386 | 603 | 1.214 | 5200.0–5200.0 | 0.022 | 0.253 | - |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| f0-A2 vs f0 | -0.20 | [-0.99, +0.60] | -0.20 | ±0.57 / ±0.80 (widened) | 2/6 | 0.41 | - | -1.0k ± 3.0k | PASS

A/A gate (shape s, floor 1.0%): **PASS**; A/A reach 0.99% (simple); largest A/A excursion 0.20 log-%

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| f10 vs f0 | +9.50 | [+8.48, +10.53] | +9.08 | ±0.87 / ±0.94 (widened) | 6/6 | 1.3e-06 | 1.1e-05 | +50.0k ± 4.9k | finding
| f10-off vs f0 | -0.34 | [-1.29, +0.63] | -0.34 | ±0.91 / ±0.96 (widened) | 1/6 | 0.38 | 0.51 | -1.8k ± 4.8k | not a finding
| idle-off vs f0 | -2.81 | [-3.61, -2.01] | -2.85 | ±0.64 / ±0.83 (widened) | 0/6 | 8.8e-05 | 0.00053 | -14.8k ± 3.3k | finding
| timers-off-all vs f0 | -4.05 | [-5.10, -2.99] | -4.14 | ±1.10 / ±1.07 (t) | 0/6 | 0.0002 | 0.0008 | -21.3k ± 5.6k | finding

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| timers-off-all vs idle-off | -1.27 | [-2.12, -0.42] | -1.28 | ±0.71 / ±0.86 (widened) | 0/6 | 0.0055 | - | -6.5k ± 3.6k |
| f10-off vs f10 | -8.98 | [-9.82, -8.14] | -9.41 | ±0.83 / ±0.92 (widened) | 0/6 | 9.2e-07 | - | -51.8k ± 4.7k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| f10 [cycles_u] vs f0 | +14.23 | [+13.18, +15.30] | +13.31 | ±0.85 / ±0.93 (widened) | 6/6 | 1.8e-07 | - | +49.2k ± 3.2k |
| f10 [cycles_k] vs f0 | +0.43 | [-0.59, +1.46] | +0.43 | ±1.01 / ±1.02 (widened) | 4/6 | 0.32 | - | +0.8k ± 1.8k |
| f10 [instructions_u] vs f0 | +16.65 | [+15.87, +17.43] | +15.40 | ±0.05 / ±0.67 (widened) | 6/6 | 9.7e-14 | - | +27.3k ± 0.1k |
| f10 [instructions_k] vs f0 | +0.21 | [-0.71, +1.14] | +0.21 | ±0.84 / ±0.92 (widened) | 3/6 | 0.54 | - | +0.2k ± 0.6k |
| f10 [context_switches] vs f0 | -0.01 | [-5.22, +5.48] | -0.01 | ±5.35 / ±4.13 (t) | 2/6 | 1 | - | -0.0k ± 0.0k |
| f10 [p50_us] vs f0 | +6.00 | [+2.84, +9.26] | +5.83 | ±3.03 / ±2.40 (t) | 6/6 | 0.0043 | - | +0.0k ± 0.0k |
| f10 [p99_us] vs f0 | +12.65 | [+4.37, +21.58] | +11.91 | ±7.63 / ±5.86 (t) | 6/6 | 0.01 | - | +0.1k ± 0.1k |
| f10-off [cycles_u] vs f0 | -0.12 | [-1.07, +0.83] | -0.12 | ±0.89 / ±0.95 (widened) | 1/6 | 0.74 | - | -0.4k ± 3.1k |
| f10-off [cycles_k] vs f0 | -0.75 | [-2.15, +0.68] | -0.75 | ±1.42 / ±1.27 (t) | 2/6 | 0.23 | - | -1.3k ± 2.6k |
| f10-off [instructions_u] vs f0 | +0.75 | [+0.07, +1.42] | +0.74 | ±0.07 / ±0.67 (widened) | 6/6 | 1.2e-06 | - | +1.2k ± 0.1k |
| f10-off [instructions_k] vs f0 | +0.22 | [-0.66, +1.11] | +0.22 | ±0.76 / ±0.88 (widened) | 3/6 | 0.49 | - | +0.2k ± 0.5k |
| f10-off [context_switches] vs f0 | +1.65 | [-3.18, +6.72] | +1.64 | ±4.87 / ±3.77 (t) | 3/6 | 0.43 | - | +0.0k ± 0.0k |
| f10-off [p50_us] vs f0 | -2.04 | [-4.92, +0.94] | -2.06 | ±2.99 / ±2.38 (t) | 2/6 | 0.14 | - | -0.0k ± 0.0k |
| f10-off [p99_us] vs f0 | -2.68 | [-6.68, +1.49] | -2.72 | ±4.19 / ±3.27 (t) | 1/6 | 0.16 | - | -0.0k ± 0.0k |
| idle-off [cycles_u] vs f0 | -4.13 | [-4.91, -3.34] | -4.22 | ±0.62 / ±0.82 (widened) | 0/6 | 1.1e-05 | - | -14.3k ± 2.1k |
| idle-off [cycles_k] vs f0 | -0.29 | [-1.29, +0.73] | -0.29 | ±1.01 / ±1.02 (widened) | 1/6 | 0.5 | - | -0.5k ± 1.8k |
| idle-off [instructions_u] vs f0 | -4.89 | [-5.52, -4.25] | -5.02 | ±0.05 / ±0.67 (widened) | 0/6 | 2.1e-11 | - | -8.0k ± 0.1k |
| idle-off [instructions_k] vs f0 | +0.24 | [-0.80, +1.29] | +0.24 | ±1.05 / ±1.04 (t) | 3/6 | 0.58 | - | +0.2k ± 0.7k |
| idle-off [context_switches] vs f0 | +2.71 | [-3.78, +9.64] | +2.68 | ±6.53 / ±5.02 (t) | 3/6 | 0.34 | - | +0.0k ± 0.0k |
| idle-off [p50_us] vs f0 | -3.78 | [-7.23, -0.20] | -3.85 | ±3.65 / ±2.86 (t) | 0/6 | 0.042 | - | -0.0k ± 0.0k |
| idle-off [p99_us] vs f0 | -5.67 | [-9.41, -1.77] | -5.83 | ±4.04 / ±3.15 (t) | 0/6 | 0.014 | - | -0.0k ± 0.0k |
| timers-off-all [cycles_u] vs f0 | -5.86 | [-6.91, -4.80] | -6.04 | ±1.12 / ±1.08 (t) | 0/6 | 3.5e-05 | - | -20.3k ± 3.7k |
| timers-off-all [cycles_k] vs f0 | -0.58 | [-1.80, +0.66] | -0.58 | ±1.24 / ±1.16 (t) | 1/6 | 0.28 | - | -1.0k ± 2.2k |
| timers-off-all [instructions_u] vs f0 | -7.11 | [-7.73, -6.49] | -7.38 | ±0.07 / ±0.67 (widened) | 0/6 | 1.4e-11 | - | -11.7k ± 0.1k |
| timers-off-all [instructions_k] vs f0 | +0.60 | [-0.39, +1.61] | +0.60 | ±0.97 / ±1.00 (widened) | 5/6 | 0.17 | - | +0.4k ± 0.7k |
| timers-off-all [context_switches] vs f0 | +5.28 | [-1.27, +12.26] | +5.14 | ±6.42 / ±4.94 (t) | 5/6 | 0.095 | - | +0.0k ± 0.0k |
| timers-off-all [p50_us] vs f0 | -5.33 | [-9.70, -0.74] | -5.47 | ±4.73 / ±3.67 (t) | 0/6 | 0.031 | - | -0.0k ± 0.0k |
| timers-off-all [p99_us] vs f0 | -6.90 | [-12.31, -1.15] | -7.15 | ±5.99 / ±4.61 (t) | 0/6 | 0.028 | - | -0.0k ± 0.0k |
| timers-off-all [cycles_u] vs idle-off | -1.80 | [-2.64, -0.96] | -1.82 | ±0.70 / ±0.85 (widened) | 0/6 | 0.0011 | - | -6.0k ± 2.3k |
| timers-off-all [cycles_k] vs idle-off | -0.30 | [-1.21, +0.63] | -0.30 | ±0.84 / ±0.92 (widened) | 1/6 | 0.4 | - | -0.5k ± 1.5k |
| timers-off-all [instructions_u] vs idle-off | -2.34 | [-2.99, -1.68] | -2.36 | ±0.08 / ±0.67 (widened) | 0/6 | 5.5e-09 | - | -3.6k ± 0.1k |
| timers-off-all [instructions_k] vs idle-off | +0.36 | [-0.51, +1.25] | +0.36 | ±0.74 / ±0.88 (widened) | 3/6 | 0.26 | - | +0.3k ± 0.5k |
| timers-off-all [context_switches] vs idle-off | +2.50 | [-1.63, +6.79] | +2.47 | ±4.10 / ±3.20 (t) | 4/6 | 0.18 | - | +0.0k ± 0.0k |
| timers-off-all [p50_us] vs idle-off | -1.61 | [-3.35, +0.17] | -1.62 | ±1.79 / ±1.52 (t) | 0/6 | 0.067 | - | -0.0k ± 0.0k |
| timers-off-all [p99_us] vs idle-off | -1.30 | [-4.77, +2.29] | -1.31 | ±3.58 / ±2.81 (t) | 3/6 | 0.39 | - | -0.0k ± 0.0k |
| f0-A2 [cycles_u] vs f0 | +0.00 | [-0.95, +0.97] | +0.00 | ±0.90 / ±0.96 (widened) | 2/6 | 0.99 | - | +0.0k ± 3.1k |
| f0-A2 [cycles_k] vs f0 | -0.59 | [-1.43, +0.26] | -0.59 | ±0.69 / ±0.85 (widened) | 1/6 | 0.079 | - | -1.1k ± 1.2k |
| f0-A2 [instructions_u] vs f0 | +0.03 | [-0.64, +0.70] | +0.03 | ±0.04 / ±0.67 (widened) | 5/6 | 0.19 | - | +0.0k ± 0.1k |
| f0-A2 [instructions_k] vs f0 | +0.51 | [-0.35, +1.39] | +0.51 | ±0.72 / ±0.87 (widened) | 5/6 | 0.13 | - | +0.4k ± 0.5k |
| f0-A2 [context_switches] vs f0 | +3.22 | [-1.67, +8.34] | +3.17 | ±4.85 / ±3.76 (t) | 4/6 | 0.15 | - | +0.0k ± 0.0k |
| f0-A2 [p50_us] vs f0 | -1.84 | [-4.56, +0.95] | -1.86 | ±2.81 / ±2.24 (t) | 2/6 | 0.15 | - | -0.0k ± 0.0k |
| f0-A2 [p99_us] vs f0 | -2.40 | [-5.68, +1.00] | -2.42 | ±3.42 / ±2.69 (t) | 2/6 | 0.13 | - | -0.0k ± 0.0k |

## kill lines (simple %; the point estimate decides; plan 4.3)

- candidate 11, f10 vs f0 on s: +9.50% [+8.48, +10.53], at or beyond the +6% line; basis: Measured
- f10-off vs f0 on s: -0.34% [-1.29, +0.63] (reads as f0 when the interval includes 0 and |effect| is under the floor: yes)
- candidate 7, idle-off vs f0 on s (a saving of 3% or more keeps the patch): -2.81% [-3.61, -2.01], short of the -3% line (AT THE LINE: the quoted interval straddles it; not decided by the table); basis: Measured
- the full ceiling, timers-off-all vs f0 on s: -4.05% [-5.10, -2.99] (never decides the patch)
- the route timeout's own price, timers-off-all vs idle-off on s: -1.27% [-2.12, -0.42], -6.5k ± 3.6k cycles
- candidate 11, f10 vs f0 on fh (no line on this shape; reading): +17.01% [+15.13, +18.93], at or beyond the +6% line; basis: Measured
- f10-off vs f0 on fh: +0.94% [-0.94, +2.85] (reads as f0 when the interval includes 0 and |effect| is under the floor: yes)
- candidate 7, idle-off vs f0 on fh (a saving of 3% or more keeps the patch): -3.48% [-5.22, -1.71], at or beyond the -3% line (AT THE LINE: the quoted interval straddles it; not decided by the table); basis: Measured
- the full ceiling, timers-off-all vs f0 on fh: -3.26% [-4.13, -2.38] (never decides the patch)
- the route timeout's own price, timers-off-all vs idle-off on fh: +0.23% [-1.23, +1.72], +0.6k ± 4.0k cycles
