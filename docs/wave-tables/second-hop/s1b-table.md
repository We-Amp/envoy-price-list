# s1b-relay: primary metric cycles_total (cycles user+kernel per request)

legs: 64 current, 64 valid; evidence failing: 0

## shape p1k

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | ctx sw /req | p50 µs | p99 µs | client 2xx/s | upstream conns (end of window) |
|---|---|---|---|---|---|---|---|---|---|---|
| http | 8/8 | 470.0k | 315.2k | 154.8k | 152.6k | 1.19 | 399 | 1089 | 8000.0–8000.0 | 1024–1024 |
| tcp | 8/8 | 152.2k | 35.7k | 116.5k | 22.5k | 1.83 | 195 | 302 | 8000.0–8000.0 | 512–512 |
| tcp-A2 | 8/8 | 150.9k | 34.9k | 116.0k | 22.5k | 1.83 | 194 | 302 | 8000.0–8000.0 | 512–512 |
| tcp-noidle | 8/8 | 144.5k | 31.7k | 113.2k | 20.3k | 1.84 | 193 | 297 | 8000.0–8000.0 | 512–512 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| tcp-A2 vs tcp | -1.42 | [-4.17, +1.41] | -1.43 | ±2.83 / ±2.44 (t) | 2/8 | 0.27 | - |

A/A gate (shape p1k, floor 1.5% simple): **PASS**; A/A reach 4.21% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| tcp-noidle vs tcp | -4.04 | [-8.23, +0.34] | -4.12 | ±4.47 / ±3.76 (t) | 2/8 | 0.065 | 0.13 | not a finding
| http vs tcp | +208.94 | [+199.31, +218.88] | +112.80 | ±3.17 / ±2.71 (t) | 8/8 | 8.7e-12 | 2.6e-11 | finding

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| tcp-noidle [cycles_u] vs tcp | -10.84 | [-16.08, -5.27] | -11.48 | ±6.06 / ±5.07 (t) | 1/8 | 0.0029 | - |
| tcp-noidle [cycles_k] vs tcp | -1.97 | [-5.84, +2.06] | -1.99 | ±4.03 / ±3.41 (t) | 2/8 | 0.28 | - |
| tcp-noidle [instructions_u] vs tcp | -9.68 | [-10.28, -9.07] | -10.18 | ±0.10 / ±0.67 (widened) | 0/8 | 4e-15 | - |
| tcp-noidle [instructions_k] vs tcp | -0.13 | [-0.88, +0.63] | -0.13 | ±0.43 / ±0.76 (widened) | 4/8 | 0.49 | - |
| tcp-noidle [context_switches] vs tcp | +0.72 | [-0.33, +1.79] | +0.72 | ±0.99 / ±1.05 (widened) | 6/8 | 0.13 | - |
| tcp-noidle [p50_us] vs tcp | -1.41 | [-3.31, +0.54] | -1.42 | ±1.95 / ±1.75 (t) | 1/8 | 0.13 | - |
| tcp-noidle [p99_us] vs tcp | -2.65 | [-3.82, -1.47] | -2.69 | ±1.21 / ±1.20 (t) | 0/8 | 0.0012 | - |
| http [cycles_u] vs tcp | +788.49 | [+749.86, +828.88] | +218.44 | ±4.45 / ±3.74 (t) | 8/8 | 9.2e-13 | - |
| http [cycles_k] vs tcp | +32.54 | [+28.40, +36.81] | +28.17 | ±3.17 / ±2.71 (t) | 8/8 | 1.4e-07 | - |
| http [instructions_u] vs tcp | +577.88 | [+573.31, +582.48] | +191.38 | ±0.14 / ±0.68 (widened) | 8/8 | 0 | - |
| http [instructions_k] vs tcp | -4.74 | [-5.84, -3.64] | -4.86 | ±1.14 / ±1.15 (widened) | 0/8 | 2e-05 | - |
| http [context_switches] vs tcp | -34.41 | [-38.53, -30.02] | -42.18 | ±6.48 / ±5.41 (t) | 0/8 | 1.2e-06 | - |
| http [p50_us] vs tcp | +105.51 | [+99.27, +111.94] | +72.03 | ±3.08 / ±2.64 (t) | 8/8 | 1.7e-10 | - |
| http [p99_us] vs tcp | +248.25 | [+181.39, +330.99] | +124.78 | ±21.32 / ±17.68 (t) | 8/8 | 2.4e-06 | - |

## shape p64

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | ctx sw /req | p50 µs | p99 µs | client 2xx/s | upstream conns (end of window) |
|---|---|---|---|---|---|---|---|---|---|---|
| http | 8/8 | 465.0k | 313.9k | 151.3k | 151.9k | 1.16 | 408 | 875 | 8000.0–8000.0 | 1024–1024 |
| tcp | 8/8 | 148.2k | 34.4k | 113.7k | 22.5k | 1.83 | 194 | 300 | 8000.0–8000.0 | 512–512 |
| tcp-A2 | 8/8 | 150.1k | 34.7k | 114.9k | 22.5k | 1.84 | 194 | 300 | 8000.0–8000.0 | 512–512 |
| tcp-noidle | 8/8 | 145.0k | 31.6k | 113.6k | 20.4k | 1.86 | 190 | 298 | 8000.0–8000.0 | 512–512 |

| row (A/A, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| tcp-A2 vs tcp | +0.26 | [-2.13, +2.71] | +0.26 | ±2.41 / ±2.11 (t) | 3/8 | 0.8 | - |

A/A gate (shape p64, floor 1.5% simple): **PASS**; A/A reach 2.68% (simple)

| row (confirmatory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| tcp-noidle vs tcp | -2.38 | [-5.76, +1.13] | -2.41 | ±3.53 / ±3.00 (t) | 2/8 | 0.15 | 0.15 | not a finding
| http vs tcp | +213.16 | [+204.30, +222.28] | +114.16 | ±2.87 / ±2.47 (t) | 8/8 | 4.1e-12 | 1.6e-11 | finding

| row (parts, exploratory) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p |
|---|---|---|---|---|---|---|---|
| tcp-noidle [cycles_u] vs tcp | -8.87 | [-14.50, -2.88] | -9.29 | ±6.37 / ±5.32 (t) | 1/8 | 0.011 | - |
| tcp-noidle [cycles_k] vs tcp | -0.39 | [-3.24, +2.55] | -0.39 | ±2.90 / ±2.50 (t) | 5/8 | 0.76 | - |
| tcp-noidle [instructions_u] vs tcp | -9.61 | [-10.21, -9.00] | -10.10 | ±0.05 / ±0.67 (widened) | 0/8 | 0 | - |
| tcp-noidle [instructions_k] vs tcp | +0.18 | [-0.60, +0.97] | +0.18 | ±0.49 / ±0.78 (widened) | 4/8 | 0.42 | - |
| tcp-noidle [context_switches] vs tcp | +1.53 | [+0.51, +2.55] | +1.52 | ±0.91 / ±1.00 (widened) | 7/8 | 0.0055 | - |
| tcp-noidle [p50_us] vs tcp | -0.96 | [-2.89, +1.00] | -0.97 | ±1.97 / ±1.76 (t) | 3/8 | 0.28 | - |
| tcp-noidle [p99_us] vs tcp | -0.91 | [-2.65, +0.85] | -0.92 | ±1.77 / ±1.61 (t) | 2/8 | 0.26 | - |
| http [cycles_u] vs tcp | +804.80 | [+766.45, +844.85] | +220.25 | ±4.33 / ±3.65 (t) | 8/8 | 7.2e-13 | - |
| http [cycles_k] vs tcp | +32.78 | [+28.96, +36.72] | +28.36 | ±2.92 / ±2.51 (t) | 8/8 | 7.5e-08 | - |
| http [instructions_u] vs tcp | +574.41 | [+569.88, +578.97] | +190.87 | ±0.12 / ±0.67 (widened) | 8/8 | 0 | - |
| http [instructions_k] vs tcp | -6.00 | [-7.44, -4.54] | -6.19 | ±1.54 / ±1.44 (t) | 0/8 | 3e-05 | - |
| http [context_switches] vs tcp | -36.93 | [-42.99, -30.22] | -46.09 | ±10.11 / ±8.41 (t) | 0/8 | 1.3e-05 | - |
| http [p50_us] vs tcp | +109.82 | [+100.31, +119.78] | +74.11 | ±4.64 / ±3.90 (t) | 8/8 | 2.4e-09 | - |
| http [p99_us] vs tcp | +200.10 | [+146.39, +265.51] | +109.89 | ±19.72 / ±16.36 (t) | 8/8 | 3.4e-06 | - |
