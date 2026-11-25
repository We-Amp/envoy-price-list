# s4a-otel: primary metric cycles_total (cycles user+kernel per request, Envoy process)

legs: 128 current, 128 valid; evidence failing: 0; superseded (replaced by the harness): 0; target rates: s [5200]/s, fh [8000]/s

shape order by round (as run): r1 fh then s; r2 s then fh; r3 fh then s; r4 s then fh; r5 fh then s; r6 s then fh; r7 fh then s; r8 s then fh

| arm | binary sha256 (as started) | md5 unchanged at the end | version |
|---|---|---|---|
| notrace | 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc | True | b2d89e0ae539 |
| patched-0 | 88a127e872851947e849ad580bdb6716f1d9cf25b0e0f77036b70a1a601a266d | True | ec7206bbb33a |
| patched-0-guard-off | 88a127e872851947e849ad580bdb6716f1d9cf25b0e0f77036b70a1a601a266d | True | ec7206bbb33a |
| patched-1 | 88a127e872851947e849ad580bdb6716f1d9cf25b0e0f77036b70a1a601a266d | True | ec7206bbb33a |
| patched-notrace | 88a127e872851947e849ad580bdb6716f1d9cf25b0e0f77036b70a1a601a266d | True | ec7206bbb33a |
| stock-0 | 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc | True | b2d89e0ae539 |
| stock-0-A2 | 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc | True | b2d89e0ae539 |
| stock-1 | 1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc | True | b2d89e0ae539 |

## shape s

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| notrace | 8/8 | 525.0k | 344.5k | 180.1k | 163.9k | 71.7k | 1.65 | 391 | 618 | 1.255 | 5200.0–5200.0 | 0.253 |
| patched-0 | 8/8 | 545.3k | 365.8k | 179.0k | 176.8k | 71.3k | 1.58 | 408 | 666 | 1.294 | 5200.0–5200.0 | 0.254 |
| patched-0-guard-off | 8/8 | 560.9k | 378.1k | 181.8k | 185.7k | 71.3k | 1.57 | 416 | 688 | 1.329 | 5200.0–5200.0 | 0.253 |
| patched-1 | 8/8 | 547.8k | 368.0k | 180.3k | 178.1k | 71.3k | 1.54 | 422 | 688 | 1.300 | 5200.0–5200.0 | 0.254 |
| patched-notrace | 8/8 | 522.7k | 344.6k | 178.5k | 163.8k | 71.5k | 1.60 | 400 | 627 | 1.245 | 5200.0–5200.0 | 0.254 |
| stock-0 | 8/8 | 561.2k | 379.6k | 181.7k | 185.2k | 71.3k | 1.56 | 418 | 695 | 1.329 | 5200.0–5200.0 | 0.254 |
| stock-0-A2 | 8/8 | 555.6k | 376.1k | 179.6k | 185.2k | 71.0k | 1.53 | 420 | 706 | 1.315 | 5200.0–5200.0 | 0.253 |
| stock-1 | 8/8 | 561.4k | 378.8k | 181.9k | 186.5k | 71.5k | 1.58 | 426 | 687 | 1.329 | 5200.0–5200.0 | 0.253 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| stock-0-A2 vs stock-0 | -0.79 | [-1.64, +0.08] | -0.79 | ±0.67 / ±0.87 (widened) | 2/8 | 0.028 | - | -4.4k ± 3.8k | PASS

A/A gate (shape s, floor 1.0 log points): **PASS**; A/A effect 0.79 log points; A/A reach 1.65% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| patched-0 vs notrace | +3.62 | [+2.36, +4.90] | +3.56 | ±1.23 / ±1.22 (t) | 8/8 | 0.00024 | 0.0015 | +19.0k ± 6.5k | finding; basis: Measured
| stock-0 vs notrace | +6.70 | [+5.51, +7.89] | +6.48 | ±1.08 / ±1.12 (widened) | 8/8 | 2e-06 | 2.5e-05 | +35.2k ± 5.8k | finding; basis: Measured
| patched-0 vs stock-0 | -2.88 | [-3.70, -2.06] | -2.92 | ±0.63 / ±0.85 (widened) | 0/8 | 1.1e-05 | 0.00011 | -16.2k ± 3.5k | finding; basis: Measured
| patched-0-guard-off vs stock-0 | -0.10 | [-0.94, +0.74] | -0.10 | ±0.62 / ±0.84 (widened) | 3/8 | 0.7 | 1 | -0.6k ± 3.4k | not a finding; basis: Measured
| patched-1 vs stock-1 | -2.13 | [-2.95, -1.30] | -2.16 | ±0.62 / ±0.84 (widened) | 0/8 | 8e-05 | 0.00058 | -12.0k ± 3.5k | finding; basis: Measured
| patched-notrace vs notrace | -0.24 | [-1.21, +0.73] | -0.24 | ±0.85 / ±0.97 (widened) | 3/8 | 0.52 | 1 | -1.3k ± 4.5k | not a finding; basis: Measured

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| patched-0 vs patched-0-guard-off | -2.78 | [-3.81, -1.74] | -2.82 | ±1.00 / ±1.07 (widened) | 0/8 | 0.00029 | - | -15.6k ± 5.6k |
| patched-0 vs patched-notrace | +3.87 | [+2.78, +4.98] | +3.80 | ±0.99 / ±1.06 (widened) | 8/8 | 4.1e-05 | - | +20.3k ± 5.3k |
| stock-1 vs notrace | +6.54 | [+5.29, +7.81] | +6.34 | ±1.18 / ±1.18 (widened) | 8/8 | 4.3e-06 | - | +34.4k ± 6.4k |
| patched-1 vs notrace | +4.27 | [+3.15, +5.40] | +4.18 | ±1.03 / ±1.08 (widened) | 8/8 | 2.8e-05 | - | +22.4k ± 5.5k |
| patched-0-guard-off vs notrace | +6.59 | [+5.29, +7.89] | +6.38 | ±1.22 / ±1.21 (t) | 8/8 | 5.2e-06 | - | +34.6k ± 6.6k |
| stock-1 vs stock-0 | -0.14 | [-1.07, +0.79] | -0.14 | ±0.79 / ±0.93 (widened) | 5/8 | 0.68 | - | -0.8k ± 4.4k |
| patched-1 vs patched-0 | +0.62 | [-0.22, +1.48] | +0.62 | ±0.62 / ±0.84 (widened) | 7/8 | 0.05 | - | +3.4k ± 3.4k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| patched-0 [cycles_u] vs notrace | +5.99 | [+4.78, +7.20] | +5.81 | ±1.12 / ±1.14 (widened) | 8/8 | 5.4e-06 | - | +20.7k ± 3.9k |
| patched-0 [cycles_k] vs notrace | -0.90 | [-2.36, +0.58] | -0.90 | ±1.48 / ±1.40 (t) | 2/8 | 0.19 | - | -1.6k ± 2.7k |
| patched-0 [instructions_u] vs notrace | +7.87 | [+7.15, +8.59] | +7.57 | ±0.05 / ±0.67 (widened) | 8/8 | 4.4e-16 | - | +12.9k ± 0.1k |
| patched-0 [instructions_k] vs notrace | -0.86 | [-1.66, -0.05] | -0.86 | ±0.56 / ±0.81 (widened) | 0/8 | 0.0084 | - | -0.6k ± 0.4k |
| patched-0 [context_switches] vs notrace | -5.51 | [-9.01, -1.88] | -5.67 | ±3.77 / ±3.19 (t) | 0/8 | 0.0093 | - | -0.0k ± 0.0k |
| patched-0 [p50_us] vs notrace | +5.14 | [+2.08, +8.30] | +5.01 | ±2.96 / ±2.54 (t) | 7/8 | 0.0051 | - | +0.0k ± 0.0k |
| patched-0 [p99_us] vs notrace | +8.92 | [+3.41, +14.73] | +8.55 | ±5.20 / ±4.36 (t) | 8/8 | 0.006 | - | +0.1k ± 0.0k |
| stock-0 [cycles_u] vs notrace | +9.98 | [+8.71, +11.27] | +9.51 | ±1.15 / ±1.16 (widened) | 8/8 | 2.3e-07 | - | +34.4k ± 4.1k |
| stock-0 [cycles_k] vs notrace | +0.41 | [-0.72, +1.56] | +0.41 | ±1.12 / ±1.14 (widened) | 5/8 | 0.41 | - | +0.7k ± 2.0k |
| stock-0 [instructions_u] vs notrace | +13.03 | [+12.28, +13.78] | +12.25 | ±0.04 / ±0.67 (widened) | 8/8 | 0 | - | +21.3k ± 0.1k |
| stock-0 [instructions_k] vs notrace | -0.60 | [-1.40, +0.22] | -0.60 | ±0.57 / ±0.81 (widened) | 1/8 | 0.041 | - | -0.4k ± 0.4k |
| stock-0 [context_switches] vs notrace | -4.85 | [-8.37, -1.20] | -4.97 | ±3.77 / ±3.19 (t) | 1/8 | 0.017 | - | -0.0k ± 0.0k |
| stock-0 [p50_us] vs notrace | +6.28 | [+4.01, +8.61] | +6.09 | ±2.16 / ±1.91 (t) | 8/8 | 0.00029 | - | +0.0k ± 0.0k |
| stock-0 [p99_us] vs notrace | +11.55 | [+6.58, +16.75] | +10.93 | ±4.56 / ±3.84 (t) | 8/8 | 0.00076 | - | +0.1k ± 0.0k |
| patched-0 [cycles_u] vs stock-0 | -3.63 | [-4.40, -2.86] | -3.70 | ±0.53 / ±0.80 (widened) | 0/8 | 7.2e-07 | - | -13.8k ± 2.0k |
| patched-0 [cycles_k] vs stock-0 | -1.31 | [-2.43, -0.17] | -1.32 | ±1.13 / ±1.15 (widened) | 2/8 | 0.028 | - | -2.4k ± 2.0k |
| patched-0 [instructions_u] vs stock-0 | -4.56 | [-5.20, -3.92] | -4.67 | ±0.03 / ±0.67 (widened) | 0/8 | 6.7e-16 | - | -8.5k ± 0.1k |
| patched-0 [instructions_k] vs stock-0 | -0.26 | [-1.27, +0.75] | -0.26 | ±0.92 / ±1.01 (widened) | 4/8 | 0.52 | - | -0.2k ± 0.7k |
| patched-0 [context_switches] vs stock-0 | -0.70 | [-6.42, +5.38] | -0.70 | ±5.94 / ±4.97 (t) | 4/8 | 0.79 | - | -0.0k ± 0.0k |
| patched-0 [p50_us] vs stock-0 | -1.08 | [-4.14, +2.08] | -1.08 | ±3.14 / ±2.69 (t) | 3/8 | 0.44 | - | -0.0k ± 0.0k |
| patched-0 [p99_us] vs stock-0 | -2.35 | [-9.20, +5.02] | -2.38 | ±7.28 / ±6.07 (t) | 2/8 | 0.46 | - | -0.0k ± 0.0k |
| patched-0-guard-off [cycles_u] vs stock-0 | -0.33 | [-1.15, +0.49] | -0.33 | ±0.58 / ±0.82 (widened) | 1/8 | 0.22 | - | -1.3k ± 2.2k |
| patched-0-guard-off [cycles_k] vs stock-0 | +0.37 | [-0.64, +1.39] | +0.37 | ±0.92 / ±1.01 (widened) | 6/8 | 0.37 | - | +0.7k ± 1.7k |
| patched-0-guard-off [instructions_u] vs stock-0 | +0.25 | [-0.42, +0.92] | +0.25 | ±0.04 / ±0.67 (widened) | 8/8 | 1.9e-06 | - | +0.5k ± 0.1k |
| patched-0-guard-off [instructions_k] vs stock-0 | -0.02 | [-0.83, +0.81] | -0.02 | ±0.57 / ±0.82 (widened) | 5/8 | 0.95 | - | -0.0k ± 0.4k |
| patched-0-guard-off [context_switches] vs stock-0 | +0.24 | [-3.29, +3.90] | +0.24 | ±3.59 / ±3.05 (t) | 5/8 | 0.88 | - | +0.0k ± 0.0k |
| patched-0-guard-off [p50_us] vs stock-0 | -0.01 | [-1.94, +1.96] | -0.01 | ±1.95 / ±1.75 (t) | 3/8 | 0.99 | - | -0.0k ± 0.0k |
| patched-0-guard-off [p99_us] vs stock-0 | +2.32 | [-5.20, +10.44] | +2.29 | ±7.63 / ±6.36 (t) | 4/8 | 0.5 | - | +0.0k ± 0.1k |
| patched-1 [cycles_u] vs stock-1 | -2.81 | [-3.58, -2.04] | -2.85 | ±0.51 / ±0.79 (widened) | 0/8 | 3.2e-06 | - | -10.7k ± 1.9k |
| patched-1 [cycles_k] vs stock-1 | -0.71 | [-1.76, +0.35] | -0.71 | ±1.00 / ±1.07 (widened) | 2/8 | 0.14 | - | -1.3k ± 1.8k |
| patched-1 [instructions_u] vs stock-1 | -4.50 | [-5.14, -3.86] | -4.61 | ±0.04 / ±0.67 (widened) | 0/8 | 4.4e-15 | - | -8.4k ± 0.1k |
| patched-1 [instructions_k] vs stock-1 | -0.29 | [-1.01, +0.44] | -0.29 | ±0.36 / ±0.73 (widened) | 2/8 | 0.1 | - | -0.2k ± 0.3k |
| patched-1 [context_switches] vs stock-1 | -1.46 | [-3.45, +0.57] | -1.47 | ±2.04 / ±1.82 (t) | 3/8 | 0.13 | - | -0.0k ± 0.0k |
| patched-1 [p50_us] vs stock-1 | -0.51 | [-2.12, +1.11] | -0.52 | ±1.62 / ±1.50 (t) | 4/8 | 0.48 | - | -0.0k ± 0.0k |
| patched-1 [p99_us] vs stock-1 | +0.29 | [-3.06, +3.75] | +0.29 | ±3.39 / ±2.89 (t) | 4/8 | 0.85 | - | +0.0k ± 0.0k |
| patched-notrace [cycles_u] vs notrace | +0.00 | [-0.92, +0.93] | +0.00 | ±0.77 / ±0.92 (widened) | 4/8 | 0.99 | - | +0.0k ± 2.7k |
| patched-notrace [cycles_k] vs notrace | -0.71 | [-1.86, +0.45] | -0.71 | ±1.15 / ±1.16 (widened) | 2/8 | 0.18 | - | -1.3k ± 2.1k |
| patched-notrace [instructions_u] vs notrace | -0.02 | [-0.68, +0.65] | -0.02 | ±0.03 / ±0.67 (widened) | 1/8 | 0.3 | - | -0.0k ± 0.1k |
| patched-notrace [instructions_k] vs notrace | -0.46 | [-1.17, +0.26] | -0.46 | ±0.32 / ±0.72 (widened) | 0/8 | 0.011 | - | -0.3k ± 0.2k |
| patched-notrace [context_switches] vs notrace | -2.77 | [-4.98, -0.51] | -2.81 | ±2.30 / ±2.02 (t) | 0/8 | 0.023 | - | -0.0k ± 0.0k |
| patched-notrace [p50_us] vs notrace | +1.99 | [-0.69, +4.74] | +1.97 | ±2.66 / ±2.30 (t) | 7/8 | 0.12 | - | +0.0k ± 0.0k |
| patched-notrace [p99_us] vs notrace | +1.88 | [-1.41, +5.28] | +1.86 | ±3.28 / ±2.80 (t) | 4/8 | 0.22 | - | +0.0k ± 0.0k |
| stock-0-A2 [cycles_u] vs stock-0 | -0.84 | [-1.61, -0.06] | -0.84 | ±0.48 / ±0.78 (widened) | 0/8 | 0.0046 | - | -3.2k ± 1.8k |
| stock-0-A2 [cycles_k] vs stock-0 | -0.67 | [-1.94, +0.61] | -0.68 | ±1.29 / ±1.26 (t) | 4/8 | 0.25 | - | -1.2k ± 2.3k |
| stock-0-A2 [instructions_u] vs stock-0 | -0.02 | [-0.69, +0.65] | -0.02 | ±0.07 / ±0.67 (widened) | 4/8 | 0.42 | - | -0.0k ± 0.1k |
| stock-0-A2 [instructions_k] vs stock-0 | -0.49 | [-1.41, +0.44] | -0.49 | ±0.78 / ±0.93 (widened) | 3/8 | 0.18 | - | -0.3k ± 0.6k |
| stock-0-A2 [context_switches] vs stock-0 | -2.63 | [-7.42, +2.40] | -2.67 | ±5.04 / ±4.23 (t) | 3/8 | 0.25 | - | -0.0k ± 0.0k |
| stock-0-A2 [p50_us] vs stock-0 | +0.77 | [-1.94, +3.56] | +0.77 | ±2.73 / ±2.36 (t) | 4/8 | 0.53 | - | +0.0k ± 0.0k |
| stock-0-A2 [p99_us] vs stock-0 | +3.12 | [-3.65, +10.36] | +3.07 | ±6.79 / ±5.67 (t) | 5/8 | 0.32 | - | +0.0k ± 0.0k |

## shape fh

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| notrace | 8/8 | 280.2k | 198.3k | 82.2k | 164.7k | 29.3k | 0.84 | 216 | 370 | 1.023 | 8000.0–8000.0 | 0.255 |
| patched-0 | 8/8 | 296.7k | 214.4k | 82.8k | 170.3k | 29.1k | 0.79 | 225 | 382 | 1.078 | 8000.0–8000.0 | 0.255 |
| patched-0-guard-off | 8/8 | 305.9k | 222.5k | 83.3k | 180.1k | 29.1k | 0.79 | 229 | 394 | 1.111 | 8000.0–8000.0 | 0.254 |
| patched-1 | 8/8 | 299.7k | 216.1k | 83.0k | 171.5k | 29.3k | 0.81 | 225 | 388 | 1.091 | 8000.0–8000.0 | 0.256 |
| patched-notrace | 8/8 | 278.9k | 196.8k | 82.2k | 164.7k | 29.3k | 0.84 | 215 | 368 | 1.022 | 8000.0–8000.0 | 0.254 |
| stock-0 | 8/8 | 305.8k | 222.2k | 83.5k | 179.7k | 29.1k | 0.78 | 229 | 393 | 1.111 | 8000.0–8000.0 | 0.260 |
| stock-0-A2 | 8/8 | 307.4k | 223.7k | 83.6k | 179.7k | 29.2k | 0.80 | 230 | 391 | 1.115 | 8000.0–8000.0 | 0.255 |
| stock-1 | 8/8 | 311.0k | 226.3k | 84.1k | 180.9k | 29.2k | 0.80 | 230 | 395 | 1.128 | 8000.0–8000.0 | 0.254 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| stock-0-A2 vs stock-0 | +0.66 | [-0.11, +1.44] | +0.66 | ±0.47 / ±0.77 (widened) | 7/8 | 0.013 | - | +2.0k ± 1.4k | PASS

A/A gate (shape fh, floor 1.0 log points): **PASS**; A/A effect 0.66 log points; A/A reach 1.44% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| patched-0 vs notrace | +5.37 | [+3.96, +6.80] | +5.23 | ±1.35 / ±1.30 (t) | 8/8 | 3.7e-05 | 0.00033 | +15.1k ± 3.9k | finding; basis: Measured
| stock-0 vs notrace | +8.40 | [+6.88, +9.94] | +8.07 | ±1.41 / ±1.35 (t) | 8/8 | 2.8e-06 | 3.1e-05 | +23.6k ± 4.1k | finding; basis: Measured
| patched-0 vs stock-0 | -2.80 | [-3.90, -1.67] | -2.84 | ±1.12 / ±1.15 (widened) | 0/8 | 0.00056 | 0.0028 | -8.5k ± 3.4k | finding; basis: Measured
| patched-0-guard-off vs stock-0 | +0.01 | [-1.37, +1.42] | +0.01 | ±1.40 / ±1.34 (t) | 4/8 | 0.98 | 1 | +0.1k ± 4.3k | not a finding; basis: Measured
| patched-1 vs stock-1 | -3.36 | [-4.36, -2.34] | -3.41 | ±0.97 / ±1.05 (widened) | 0/8 | 7.3e-05 | 0.00058 | -10.4k ± 3.0k | finding; basis: Measured
| patched-notrace vs notrace | -0.73 | [-2.39, +0.95] | -0.73 | ±1.68 / ±1.55 (t) | 3/8 | 0.34 | 1 | -2.1k ± 4.7k | not a finding; basis: Measured

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| patched-0 vs patched-0-guard-off | -2.81 | [-4.47, -1.12] | -2.85 | ±1.72 / ±1.58 (t) | 1/8 | 0.0058 | - | -8.6k ± 5.2k |
| patched-0 vs patched-notrace | +6.15 | [+4.89, +7.42] | +5.97 | ±1.19 / ±1.19 (t) | 8/8 | 7e-06 | - | +17.2k ± 3.4k |
| stock-1 vs notrace | +10.11 | [+8.69, +11.53] | +9.63 | ±1.29 / ±1.26 (t) | 8/8 | 4.6e-07 | - | +28.4k ± 3.7k |
| patched-1 vs notrace | +6.41 | [+5.16, +7.67] | +6.21 | ±1.18 / ±1.18 (widened) | 8/8 | 4.9e-06 | - | +18.0k ± 3.3k |
| patched-0-guard-off vs notrace | +8.42 | [+6.93, +9.92] | +8.08 | ±1.38 / ±1.32 (t) | 8/8 | 2.4e-06 | - | +23.7k ± 4.1k |
| stock-1 vs stock-0 | +1.57 | [+0.47, +2.68] | +1.56 | ±1.04 / ±1.09 (widened) | 7/8 | 0.0093 | - | +4.8k ± 3.2k |
| patched-1 vs patched-0 | +0.98 | [-0.16, +2.15] | +0.98 | ±1.12 / ±1.14 (widened) | 5/8 | 0.078 | - | +2.9k ± 3.3k |

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| patched-0 [cycles_u] vs notrace | +7.50 | [+5.99, +9.03] | +7.23 | ±1.41 / ±1.35 (t) | 8/8 | 6e-06 | - | +14.9k ± 2.9k |
| patched-0 [cycles_k] vs notrace | +0.25 | [-1.27, +1.79] | +0.25 | ±1.53 / ±1.43 (t) | 3/8 | 0.71 | - | +0.2k ± 1.3k |
| patched-0 [instructions_u] vs notrace | +3.35 | [+2.66, +4.04] | +3.30 | ±0.01 / ±0.67 (widened) | 8/8 | 0 | - | +5.5k ± 0.0k |
| patched-0 [instructions_k] vs notrace | -0.49 | [-1.49, +0.52] | -0.49 | ±0.92 / ±1.01 (widened) | 2/8 | 0.25 | - | -0.1k ± 0.3k |
| patched-0 [context_switches] vs notrace | -4.51 | [-7.17, -1.77] | -4.62 | ±2.83 / ±2.44 (t) | 1/8 | 0.0062 | - | -0.0k ± 0.0k |
| patched-0 [p50_us] vs notrace | +3.70 | [+2.35, +5.07] | +3.63 | ±1.31 / ±1.28 (t) | 8/8 | 0.00032 | - | +0.0k ± 0.0k |
| patched-0 [p99_us] vs notrace | +3.61 | [+2.41, +4.83] | +3.55 | ±1.15 / ±1.16 (widened) | 8/8 | 0.00016 | - | +0.0k ± 0.0k |
| stock-0 [cycles_u] vs notrace | +11.61 | [+9.94, +13.31] | +10.99 | ±1.51 / ±1.42 (t) | 8/8 | 5.5e-07 | - | +23.1k ± 3.1k |
| stock-0 [cycles_k] vs notrace | +0.67 | [-0.63, +1.99] | +0.67 | ±1.30 / ±1.27 (t) | 5/8 | 0.26 | - | +0.6k ± 1.1k |
| stock-0 [instructions_u] vs notrace | +9.10 | [+8.37, +9.83] | +8.71 | ±0.01 / ±0.67 (widened) | 8/8 | 0 | - | +15.0k ± 0.0k |
| stock-0 [instructions_k] vs notrace | -0.50 | [-1.50, +0.51] | -0.50 | ±0.92 / ±1.01 (widened) | 3/8 | 0.24 | - | -0.1k ± 0.3k |
| stock-0 [context_switches] vs notrace | -6.31 | [-8.60, -3.96] | -6.52 | ±2.48 / ±2.16 (t) | 0/8 | 0.00044 | - | -0.0k ± 0.0k |
| stock-0 [p50_us] vs notrace | +6.06 | [+4.51, +7.63] | +5.88 | ±1.47 / ±1.39 (t) | 8/8 | 3.1e-05 | - | +0.0k ± 0.0k |
| stock-0 [p99_us] vs notrace | +6.18 | [+5.13, +7.24] | +5.99 | ±0.89 / ±0.99 (widened) | 8/8 | 9.4e-07 | - | +0.0k ± 0.0k |
| patched-0 [cycles_u] vs stock-0 | -3.69 | [-4.70, -2.65] | -3.75 | ±1.00 / ±1.06 (widened) | 0/8 | 4.7e-05 | - | -8.2k ± 2.2k |
| patched-0 [cycles_k] vs stock-0 | -0.42 | [-2.05, +1.24] | -0.42 | ±1.65 / ±1.52 (t) | 3/8 | 0.56 | - | -0.3k ± 1.4k |
| patched-0 [instructions_u] vs stock-0 | -5.27 | [-5.89, -4.63] | -5.41 | ±0.01 / ±0.67 (widened) | 0/8 | 0 | - | -9.5k ± 0.0k |
| patched-0 [instructions_k] vs stock-0 | +0.01 | [-1.03, +1.07] | +0.01 | ±0.98 / ±1.05 (widened) | 3/8 | 0.98 | - | +0.0k ± 0.3k |
| patched-0 [context_switches] vs stock-0 | +1.92 | [-1.87, +5.86] | +1.90 | ±3.79 / ±3.21 (t) | 6/8 | 0.27 | - | +0.0k ± 0.0k |
| patched-0 [p50_us] vs stock-0 | -2.22 | [-3.19, -1.25] | -2.25 | ±0.88 / ±0.99 (widened) | 0/8 | 0.00054 | - | -0.0k ± 0.0k |
| patched-0 [p99_us] vs stock-0 | -2.42 | [-3.33, -1.49] | -2.45 | ±0.80 / ±0.94 (widened) | 0/8 | 0.00018 | - | -0.0k ± 0.0k |
| patched-0-guard-off [cycles_u] vs stock-0 | +0.15 | [-1.23, +1.54] | +0.15 | ±1.39 / ±1.33 (t) | 4/8 | 0.81 | - | +0.3k ± 3.1k |
| patched-0-guard-off [cycles_k] vs stock-0 | -0.33 | [-1.85, +1.20] | -0.33 | ±1.53 / ±1.43 (t) | 3/8 | 0.62 | - | -0.3k ± 1.3k |
| patched-0-guard-off [instructions_u] vs stock-0 | +0.22 | [-0.45, +0.89] | +0.22 | ±0.01 / ±0.67 (widened) | 8/8 | 2.2e-10 | - | +0.4k ± 0.0k |
| patched-0-guard-off [instructions_k] vs stock-0 | +0.03 | [-0.80, +0.87] | +0.03 | ±0.60 / ±0.83 (widened) | 5/8 | 0.9 | - | +0.0k ± 0.2k |
| patched-0-guard-off [context_switches] vs stock-0 | +0.21 | [-1.69, +2.15] | +0.21 | ±1.92 / ±1.72 (t) | 5/8 | 0.8 | - | +0.0k ± 0.0k |
| patched-0-guard-off [p50_us] vs stock-0 | -0.19 | [-1.51, +1.15] | -0.19 | ±1.33 / ±1.29 (t) | 5/8 | 0.74 | - | -0.0k ± 0.0k |
| patched-0-guard-off [p99_us] vs stock-0 | -0.17 | [-1.18, +0.84] | -0.17 | ±0.92 / ±1.01 (widened) | 3/8 | 0.67 | - | -0.0k ± 0.0k |
| patched-1 [cycles_u] vs stock-1 | -4.25 | [-5.25, -3.24] | -4.34 | ±0.97 / ±1.05 (widened) | 0/8 | 1.5e-05 | - | -9.6k ± 2.2k |
| patched-1 [cycles_k] vs stock-1 | -0.95 | [-2.14, +0.25] | -0.96 | ±1.21 / ±1.20 (t) | 2/8 | 0.1 | - | -0.8k ± 1.0k |
| patched-1 [instructions_u] vs stock-1 | -5.17 | [-5.80, -4.54] | -5.31 | ±0.03 / ±0.67 (widened) | 0/8 | 2.2e-16 | - | -9.4k ± 0.1k |
| patched-1 [instructions_k] vs stock-1 | -0.10 | [-0.88, +0.69] | -0.10 | ±0.49 / ±0.78 (widened) | 5/8 | 0.65 | - | -0.0k ± 0.1k |
| patched-1 [context_switches] vs stock-1 | +2.76 | [+0.68, +4.88] | +2.72 | ±2.04 / ±1.82 (t) | 7/8 | 0.016 | - | +0.0k ± 0.0k |
| patched-1 [p50_us] vs stock-1 | -2.49 | [-3.38, -1.60] | -2.53 | ±0.74 / ±0.91 (widened) | 0/8 | 9e-05 | - | -0.0k ± 0.0k |
| patched-1 [p99_us] vs stock-1 | -2.34 | [-3.27, -1.40] | -2.37 | ±0.83 / ±0.96 (widened) | 0/8 | 0.00027 | - | -0.0k ± 0.0k |
| patched-notrace [cycles_u] vs notrace | -0.84 | [-2.63, +0.99] | -0.84 | ±1.82 / ±1.65 (t) | 3/8 | 0.31 | - | -1.7k ± 3.6k |
| patched-notrace [cycles_k] vs notrace | -0.47 | [-2.10, +1.19] | -0.47 | ±1.65 / ±1.52 (t) | 4/8 | 0.52 | - | -0.4k ± 1.4k |
| patched-notrace [instructions_u] vs notrace | +0.00 | [-0.66, +0.67] | +0.00 | ±0.01 / ±0.67 (widened) | 4/8 | 0.86 | - | +0.0k ± 0.0k |
| patched-notrace [instructions_k] vs notrace | +0.37 | [-0.52, +1.27] | +0.37 | ±0.71 / ±0.89 (widened) | 5/8 | 0.26 | - | +0.1k ± 0.2k |
| patched-notrace [context_switches] vs notrace | +0.65 | [-1.82, +3.18] | +0.64 | ±2.48 / ±2.16 (t) | 3/8 | 0.56 | - | +0.0k ± 0.0k |
| patched-notrace [p50_us] vs notrace | -0.49 | [-2.13, +1.17] | -0.49 | ±1.65 / ±1.52 (t) | 3/8 | 0.5 | - | -0.0k ± 0.0k |
| patched-notrace [p99_us] vs notrace | -0.19 | [-1.15, +0.78] | -0.19 | ±0.85 / ±0.97 (widened) | 3/8 | 0.61 | - | -0.0k ± 0.0k |
| stock-0-A2 [cycles_u] vs stock-0 | +0.69 | [-0.17, +1.56] | +0.69 | ±0.65 / ±0.86 (widened) | 6/8 | 0.042 | - | +1.5k ± 1.5k |
| stock-0-A2 [cycles_k] vs stock-0 | +0.58 | [-0.34, +1.50] | +0.58 | ±0.76 / ±0.92 (widened) | 5/8 | 0.12 | - | +0.5k ± 0.6k |
| stock-0-A2 [instructions_u] vs stock-0 | -0.00 | [-0.67, +0.67] | -0.00 | ±0.01 / ±0.67 (widened) | 3/8 | 0.73 | - | -0.0k ± 0.0k |
| stock-0-A2 [instructions_k] vs stock-0 | +0.39 | [-0.53, +1.33] | +0.39 | ±0.77 / ±0.92 (widened) | 6/8 | 0.27 | - | +0.1k ± 0.2k |
| stock-0-A2 [context_switches] vs stock-0 | +1.55 | [-1.35, +4.53] | +1.54 | ±2.90 / ±2.49 (t) | 5/8 | 0.25 | - | +0.0k ± 0.0k |
| stock-0-A2 [p50_us] vs stock-0 | +0.29 | [-0.60, +1.18] | +0.29 | ±0.71 / ±0.89 (widened) | 5/8 | 0.37 | - | +0.0k ± 0.0k |
| stock-0-A2 [p99_us] vs stock-0 | +0.03 | [-0.74, +0.81] | +0.03 | ±0.48 / ±0.78 (widened) | 4/8 | 0.89 | - | +0.0k ± 0.0k |

## candidate 4: the kill line and its readings (simple %; the point estimate decides)

- s: patched-0 vs notrace +3.62% [+2.36, +4.90]: AT THE LINE (within 1.5 points of +4%, or the quoted interval straddles it): not decided by the table; basis: Measured
  - anchor, stock-0 vs notrace: +6.70% [+5.51, +7.89] (published +6.7% on s); points recovered by the patch: 3.07 of 6.70
  - patched-0 vs stock-0 (the patch against the official binary at 0%): -2.88% [-3.70, -2.06], -16.2k ± 3.5k cycles per request; reads as no difference: no
  - patched-0-guard-off vs stock-0 (the control: guard off should read as the official binary): -0.10% [-0.94, +0.74], -0.6k ± 3.4k cycles per request; reads as no difference: yes
  - patched-0 vs patched-0-guard-off (the patch inside one binary (guard on vs off)): -2.78% [-3.81, -1.74], -15.6k ± 5.6k cycles per request; reads as no difference: no
  - patched-1 vs stock-1 (sampled at 1%: cost unchanged?): -2.13% [-2.95, -1.30], -12.0k ± 3.5k cycles per request; reads as no difference: no
  - patched-notrace vs notrace (the build's layout shift without a tracer): -0.24% [-1.21, +0.73], -1.3k ± 4.5k cycles per request; reads as no difference: yes
  - patched-0 vs patched-notrace (the tracer at 0% inside the patched binary): +3.87% [+2.78, +4.98], +20.3k ± 5.3k cycles per request; reads as no difference: no
- fh: patched-0 vs notrace +5.37% [+3.96, +6.80]: no line on this shape (reading); basis: Measured
  - anchor, stock-0 vs notrace: +8.40% [+6.88, +9.94] (published +6.7% on s); points recovered by the patch: 3.03 of 8.40
  - patched-0 vs stock-0 (the patch against the official binary at 0%): -2.80% [-3.90, -1.67], -8.5k ± 3.4k cycles per request; reads as no difference: no
  - patched-0-guard-off vs stock-0 (the control: guard off should read as the official binary): +0.01% [-1.37, +1.42], +0.1k ± 4.3k cycles per request; reads as no difference: yes
  - patched-0 vs patched-0-guard-off (the patch inside one binary (guard on vs off)): -2.81% [-4.47, -1.12], -8.6k ± 5.2k cycles per request; reads as no difference: no
  - patched-1 vs stock-1 (sampled at 1%: cost unchanged?): -3.36% [-4.36, -2.34], -10.4k ± 3.0k cycles per request; reads as no difference: no
  - patched-notrace vs notrace (the build's layout shift without a tracer): -0.73% [-2.39, +0.95], -2.1k ± 4.7k cycles per request; reads as no difference: yes
  - patched-0 vs patched-notrace (the tracer at 0% inside the patched binary): +6.15% [+4.89, +7.42], +17.2k ± 3.4k cycles per request; reads as no difference: no
