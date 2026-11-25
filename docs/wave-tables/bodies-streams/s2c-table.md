# s2c-buf: primary metric cycles_total (cycles user+kernel per request, Envoy process)

legs: 18 current, 18 valid; evidence failing: 0; target rates: l64 [2000]/s

## shape l64

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | Envoy busy (CPUs of 4) | client 2xx/s | origin CPU share of its set (max) | busiest worker share (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| buf-32k | 6/6 | 883.4k | 468.4k | 414.3k | 194.9k | 165.5k | 1.89 | 526 | 768 | 0.820 | 2000.0–2000.0 | 0.011 | 0.257 |
| buf-default | 6/6 | 742.7k | 416.6k | 327.8k | 176.5k | 114.4k | 2.00 | 511 | 722 | 0.709 | 2000.0–2000.0 | 0.011 | 0.254 |
| buf-default-A2 | 6/6 | 747.1k | 419.8k | 326.6k | 176.6k | 113.9k | 2.00 | 512 | 724 | 0.712 | 2000.0–2000.0 | 0.011 | 0.255 |

| arm | up paused /req | up resumed /req | up backed up /req | up drained /req | down paused /req | down resumed /req |
|---|---|---|---|---|---|---|
| buf-32k | 1.9943 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| buf-default | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| buf-default-A2 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| buf-default-A2 vs buf-default | +0.54 | [-0.41, +1.50] | +0.54 | ±0.89 / ±0.95 (widened) | 5/6 | 0.18 | - | +4.0k ± 6.6k |

A/A gate (shape l64, floor 1.5% simple): **PASS**; A/A reach 1.50% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| buf-32k vs buf-default | +19.02 | [+17.86, +20.18] | +17.41 | ±0.93 / ±0.97 (widened) | 6/6 | 7.4e-08 | 7.4e-08 | +141.4k ± 7.8k | finding

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| buf-32k [cycles_u] vs buf-default | +12.72 | [+11.49, +13.95] | +11.97 | ±1.09 / ±1.07 (t) | 6/6 | 1.1e-06 | - | +52.9k ± 4.9k |
| buf-32k [cycles_k] vs buf-default | +27.01 | [+25.72, +28.31] | +23.91 | ±1.01 / ±1.02 (widened) | 6/6 | 2.3e-08 | - | +88.5k ± 4.2k |
| buf-32k [instructions_u] vs buf-default | +10.41 | [+9.68, +11.15] | +9.90 | ±0.02 / ±0.67 (widened) | 6/6 | 1.8e-15 | - | +18.4k ± 0.0k |
| buf-32k [instructions_k] vs buf-default | +44.37 | [+43.26, +45.48] | +36.72 | ±0.50 / ±0.77 (widened) | 6/6 | 7.9e-11 | - | +50.7k ± 0.8k |
| buf-32k [context_switches] vs buf-default | -5.73 | [-6.89, -4.56] | -5.90 | ±1.24 / ±1.15 (t) | 0/6 | 6.4e-05 | - | -0.0k ± 0.0k |
| buf-32k [p50_us] vs buf-default | +4.02 | [+1.78, +6.32] | +3.95 | ±2.18 / ±1.79 (t) | 6/6 | 0.0056 | - | +0.0k ± 0.0k |
| buf-32k [p99_us] vs buf-default | +5.85 | [+4.89, +6.83] | +5.69 | ±0.82 / ±0.91 (widened) | 6/6 | 1e-05 | - | +0.0k ± 0.0k |
| buf-default-A2 [cycles_u] vs buf-default | +1.12 | [+0.00, +2.25] | +1.11 | ±1.11 / ±1.08 (t) | 5/6 | 0.05 | - | +4.7k ± 4.6k |
| buf-default-A2 [cycles_k] vs buf-default | -0.19 | [-1.35, +0.98] | -0.19 | ±1.16 / ±1.11 (t) | 2/6 | 0.69 | - | -0.6k ± 3.8k |
| buf-default-A2 [instructions_u] vs buf-default | -0.00 | [-0.67, +0.67] | -0.00 | ±0.05 / ±0.67 (widened) | 3/6 | 0.96 | - | -0.0k ± 0.1k |
| buf-default-A2 [instructions_k] vs buf-default | -0.32 | [-1.27, +0.63] | -0.32 | ±0.89 / ±0.95 (widened) | 2/6 | 0.39 | - | -0.4k ± 1.0k |
| buf-default-A2 [context_switches] vs buf-default | +0.07 | [-0.71, +0.87] | +0.07 | ±0.55 / ±0.79 (widened) | 4/6 | 0.74 | - | +0.0k ± 0.0k |
| buf-default-A2 [p50_us] vs buf-default | +0.60 | [-0.77, +1.98] | +0.60 | ±1.36 / ±1.23 (t) | 3/6 | 0.31 | - | +0.0k ± 0.0k |
| buf-default-A2 [p99_us] vs buf-default | +0.12 | [-1.39, +1.65] | +0.12 | ±1.52 / ±1.33 (t) | 3/6 | 0.85 | - | +0.0k ± 0.0k |
