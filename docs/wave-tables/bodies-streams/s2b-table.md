# s2b-stream: primary metric cycles_total (cycles user+kernel per request, Envoy process)

legs: 36 current, 36 valid; evidence failing: 0; target rates: ev20 [2080]/s, ev200 [208]/s

## shape ev20

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | origin CPU share of its set (max) | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 6/6 | 1981.0k | 732.1k | 1248.9k | 431.7k | 807.0k | 12.24 | 19287 | 19481 | 1.914 | 2078.1–2078.2 | 0.057 | 0.253 |
| base-A2 | 6/6 | 1955.0k | 717.0k | 1237.7k | 431.6k | 806.5k | 12.17 | 19287 | 19463 | 1.890 | 2078.1–2078.2 | 0.057 | 0.254 |
| idle-off | 6/6 | 1947.8k | 694.3k | 1253.5k | 408.4k | 807.5k | 12.30 | 19279 | 19450 | 1.887 | 2078.1–2078.2 | 0.057 | 0.252 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| base-A2 vs base | -1.68 | [-3.82, +0.52] | -1.69 | ±2.20 / ±1.81 (t) | 1/6 | 0.11 | - | -33.6k ± 44.3k |

A/A gate (shape ev20, floor 1.5% simple): **FAIL: this shape's rows are void**; A/A reach 3.84% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| idle-off vs base | -2.19 | [-5.22, +0.95] | -2.21 | ±3.16 / ±2.50 (t) | 1/6 | 0.13 | 0.26 | -43.7k ± 62.7k | VOID (A/A)

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| idle-off [cycles_u] vs base | -5.08 | [-8.70, -1.33] | -5.22 | ±3.88 / ±3.04 (t) | 1/6 | 0.018 | - | -37.3k ± 28.1k |
| idle-off [cycles_k] vs base | -0.50 | [-3.32, +2.41] | -0.50 | ±2.88 / ±2.29 (t) | 3/6 | 0.68 | - | -6.3k ± 36.4k |
| idle-off [instructions_u] vs base | -5.38 | [-6.01, -4.75] | -5.53 | ±0.08 / ±0.67 (widened) | 0/6 | 1.1e-10 | - | -23.2k ± 0.3k |
| idle-off [instructions_k] vs base | +0.09 | [-0.62, +0.81] | +0.09 | ±0.34 / ±0.72 (widened) | 4/6 | 0.52 | - | +0.7k ± 2.8k |
| idle-off [context_switches] vs base | +0.91 | [-2.39, +4.32] | +0.91 | ±3.32 / ±2.62 (t) | 4/6 | 0.51 | - | +0.0k ± 0.0k |
| idle-off [p50_us] vs base | -0.04 | [-0.71, +0.63] | -0.04 | ±0.04 / ±0.67 (widened) | 1/6 | 0.027 | - | -0.0k ± 0.0k |
| idle-off [p99_us] vs base | -0.12 | [-0.79, +0.56] | -0.12 | ±0.15 / ±0.68 (widened) | 2/6 | 0.096 | - | -0.0k ± 0.0k |
| base-A2 [cycles_u] vs base | -2.11 | [-4.60, +0.45] | -2.13 | ±2.58 / ±2.08 (t) | 1/6 | 0.087 | - | -15.5k ± 19.0k |
| base-A2 [cycles_k] vs base | -1.42 | [-3.46, +0.65] | -1.43 | ±2.08 / ±1.72 (t) | 1/6 | 0.14 | - | -18.0k ± 26.5k |
| base-A2 [instructions_u] vs base | -0.01 | [-0.67, +0.67] | -0.01 | ±0.09 / ±0.67 (widened) | 2/6 | 0.88 | - | -0.0k ± 0.4k |
| base-A2 [instructions_k] vs base | +0.03 | [-0.70, +0.77] | +0.03 | ±0.40 / ±0.73 (widened) | 3/6 | 0.85 | - | +0.3k ± 3.2k |
| base-A2 [context_switches] vs base | +0.47 | [-3.03, +4.10] | +0.47 | ±3.55 / ±2.79 (t) | 3/6 | 0.75 | - | +0.0k ± 0.0k |
| base-A2 [p50_us] vs base | -0.01 | [-0.68, +0.66] | -0.01 | ±0.04 / ±0.67 (widened) | 4/6 | 0.38 | - | -0.0k ± 0.0k |
| base-A2 [p99_us] vs base | -0.03 | [-0.70, +0.65] | -0.03 | ±0.14 / ±0.67 (widened) | 3/6 | 0.59 | - | -0.0k ± 0.0k |

## shape ev200

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | origin CPU share of its set (max) | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 6/6 | 15302.8k | 4475.8k | 10804.0k | 3147.5k | 6567.1k | 130.50 | 199307 | 199447 | 1.522 | 206.1–206.1 | 0.050 | 0.253 |
| base-A2 | 6/6 | 15341.0k | 4530.3k | 10806.9k | 3144.6k | 6561.8k | 130.61 | 199303 | 199447 | 1.525 | 206.1–206.1 | 0.050 | 0.253 |
| idle-off | 6/6 | 15172.5k | 4310.2k | 10862.3k | 2975.2k | 6581.9k | 133.34 | 199303 | 199434 | 1.514 | 206.1–206.1 | 0.050 | 0.252 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| base-A2 vs base | -1.66 | [-7.70, +4.77] | -1.68 | ±6.33 / ±4.87 (t) | 4/6 | 0.53 | - | -277.5k ± 1021.0k |

A/A gate (shape ev200, floor 1.5% simple): **FAIL: this shape's rows are void**; A/A reach 7.89% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| idle-off vs base | -2.48 | [-8.63, +4.08] | -2.51 | ±6.51 / ±5.01 (t) | 3/6 | 0.37 | 0.37 | -402.8k ± 1048.1k | VOID (A/A)

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| idle-off [cycles_u] vs base | -6.21 | [-13.18, +1.32] | -6.41 | ±7.72 / ±5.92 (t) | 0/6 | 0.086 | - | -292.7k ± 366.9k |
| idle-off [cycles_k] vs base | -0.92 | [-6.81, +5.34] | -0.93 | ±6.13 / ±4.72 (t) | 4/6 | 0.71 | - | -110.1k ± 694.5k |
| idle-off [instructions_u] vs base | -5.47 | [-6.11, -4.83] | -5.63 | ±0.11 / ±0.67 (widened) | 0/6 | 5.7e-10 | - | -172.2k ± 3.6k |
| idle-off [instructions_k] vs base | +0.11 | [-0.63, +0.85] | +0.11 | ±0.42 / ±0.74 (widened) | 4/6 | 0.54 | - | +7.0k ± 27.5k |
| idle-off [context_switches] vs base | +0.89 | [-1.87, +3.72] | +0.88 | ±2.77 / ±2.21 (t) | 4/6 | 0.45 | - | +0.0k ± 0.0k |
| idle-off [p50_us] vs base | -0.00 | [-0.67, +0.67] | -0.00 | ±0.00 / ±0.67 (widened) | 0/6 | 0.042 | - | -0.0k ± 0.0k |
| idle-off [p99_us] vs base | -0.01 | [-0.67, +0.66] | -0.01 | ±0.01 / ±0.67 (widened) | 1/6 | 0.18 | - | -0.0k ± 0.0k |
| base-A2 [cycles_u] vs base | -1.19 | [-8.78, +7.03] | -1.20 | ±7.99 / ±6.13 (t) | 4/6 | 0.72 | - | -63.0k ± 380.9k |
| base-A2 [cycles_k] vs base | -1.85 | [-7.31, +3.92] | -1.87 | ±5.72 / ±4.41 (t) | 2/6 | 0.44 | - | -214.5k ± 648.5k |
| base-A2 [instructions_u] vs base | -0.04 | [-0.72, +0.64] | -0.04 | ±0.18 / ±0.68 (widened) | 3/6 | 0.59 | - | -1.3k ± 5.8k |
| base-A2 [instructions_k] vs base | -0.07 | [-0.92, +0.79] | -0.07 | ±0.70 / ±0.86 (widened) | 4/6 | 0.81 | - | -4.7k ± 46.3k |
| base-A2 [context_switches] vs base | -0.18 | [-4.42, +4.25] | -0.18 | ±4.34 / ±3.38 (t) | 4/6 | 0.92 | - | -0.0k ± 0.0k |
| base-A2 [p50_us] vs base | -0.00 | [-0.67, +0.67] | -0.00 | ±0.00 / ±0.67 (widened) | 0/6 | 0.076 | - | -0.0k ± 0.0k |
| base-A2 [p99_us] vs base | -0.00 | [-0.67, +0.66] | -0.00 | ±0.02 / ±0.67 (widened) | 3/6 | 0.46 | - | -0.0k ± 0.0k |

## cycles per streamed event: (per request on ev200 - per request on ev20) / 180, per round

| arm | metric | per event, mean | 95% t interval | rounds |
|---|---|---|---|---|
| base | cycles_total | 75558 | [70409, 80707] | 6 |
| base | cycles_u | 21413 | [19482, 23345] | 6 |
| base | cycles_k | 54144 | [50876, 57412] | 6 |
| base | instructions_u | 15086 | [15062, 15111] | 6 |
| base | instructions_k | 32042 | [31847, 32237] | 6 |
| base | context_switches | 0.666 | [0.641, 0.690] | 6 |
| base-A2 | cycles_total | 74203 | [73490, 74916] | 6 |
| base-A2 | cycles_u | 21150 | [20675, 21624] | 6 |
| base-A2 | cycles_k | 53053 | [52564, 53542] | 6 |
| base-A2 | instructions_u | 15079 | [15063, 15095] | 6 |
| base-A2 | instructions_k | 32014 | [31900, 32128] | 6 |
| base-A2 | context_switches | 0.664 | [0.650, 0.678] | 6 |
| idle-off | cycles_total | 73563 | [71715, 75411] | 6 |
| idle-off | cycles_u | 19995 | [19474, 20516] | 6 |
| idle-off | cycles_k | 53568 | [52194, 54942] | 6 |
| idle-off | instructions_u | 14258 | [14248, 14269] | 6 |
| idle-off | instructions_k | 32076 | [31971, 32182] | 6 |
| idle-off | context_switches | 0.671 | [0.657, 0.685] | 6 |

base: per-request part (median ev20 - 20 events) = 469863 cycles; an event is 98.8% of an ev200 request / 200
