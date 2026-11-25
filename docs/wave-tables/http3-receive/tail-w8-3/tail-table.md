## Part 1: where the stop arm's retransmissions fall (Exploratory)

| config | arm | valid | retransmitted before / inside / after the window (total) | packets sent before / inside / after | p99 µs | max µs |
|---|---|---|---|---|---|---|
| tail-p1-r1 | h3-off | True | 1 / 0 / 0 (1) | 78967 / 84763 / 47116 | 784.703 | 4558.847000000001 |
| tail-p1-r1 | h3-both-on | True | 16 / 0 / 0 (16) | 78988 / 84751 / 47124 | 706.975 | 5113.855 |
| tail-p1-r2 | h3-both-on | True | 16 / 0 / 0 (16) | 78984 / 84906 / 46966 | 755.359 | 33679.359 |
| tail-p1-r2 | h3-off | True | 2 / 0 / 0 (2) | 78976 / 84683 / 47191 | 740.735 | 3647.7430000000004 |
| tail-p1-r3 | h3-off | True | 2 / 0 / 0 (2) | 78974 / 84686 / 47188 | 729.2470000000001 | 12585.471000000001 |
| tail-p1-r3 | h3-both-on | True | 14 / 0 / 0 (14) | 78988 / 84861 / 47011 | 701.407 | 4907.263 |
| tail-p1-r4 | h3-both-on | True | 14 / 0 / 0 (14) | 78992 / 84781 / 47091 | 738.8149999999999 | 4895.999 |
| tail-p1-r4 | h3-off | True | 1 / 0 / 0 (1) | 78974 / 84717 / 47155 | 797.6310000000001 | 13887.487000000001 |

sums: h3-off {'before': 6, 'inside': 0, 'after': 0}; h3-both-on {'before': 60, 'inside': 0, 'after': 0}; excess {'before': 54, 'inside': 0, 'after': 0}; E = 54
PART 1 RULE: AT THE START (100% of the excess before the window); no h3-both-on leg has more than 2 inside the window

## Part 2: row C4, h3-reuse-on vs h3-off on s (fixed before data)

- legs 32, valid 32, rounds complete 8, incomplete False, replaced 0

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user /req | p50 µs | p99 µs | retransmitted per leg | sent per leg (median) | per 100,000 sent (pooled) |
|---|---|---|---|---|---|---|---|---|---|---|
| h3-official | 8/8 | 1294.1k | 950.9k | 342.1k | 513.1k | 577.3109999999999 | 734.335 | 5 1 3 2 4 3 2 3 | 421444 | 0.68 |
| h3-official-A2 | 8/8 | 1280.8k | 940.5k | 339.1k | 512.5k | 573.471 | 738.415 | 4 5 1 0 4 4 2 1 | 421445 | 0.62 |
| h3-off | 8/8 | 1293.0k | 950.6k | 343.3k | 512.7k | 566.095 | 725.1189999999999 | 0 2 2 0 1 2 0 2 | 421446 | 0.27 |
| h3-reuse-on | 8/8 | 1209.3k | 870.6k | 338.7k | 399.8k | 545.119 | 721.935 | 2 3 1 0 2 2 4 2 | 421442 | 0.47 |

| row (rows, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h3-official-A2 vs h3-official | -0.91 | [-3.44, +1.68] | -0.92 | ±2.58 / ±2.24 (t) | 1/8 | 0.43 | - | -11.7k ± 33.5k |
| h3-off vs h3-official | +0.47 | [-1.61, +2.60] | +0.47 | ±2.09 / ±1.86 (t) | 4/8 | 0.61 | - | +6.1k ± 27.4k |
| h3-reuse-on vs h3-off | -6.50 | [-9.42, -3.48] | -6.72 | ±3.17 / ±2.71 (t) | 0/8 | 0.0016 | - | -84.3k ± 39.9k |

same-build check on s: PASS (effect -0.92 log points, quoted [-3.50, +1.66], floor 2.0)
  C4 [cycles_u, Exploratory]: -8.16% [-10.83, -5.41] simple; -77.59k ± 26.87k per request
  C4 [cycles_k, Exploratory]: -1.92% [-5.89, +2.21] simple; -6.67k ± 14.18k per request
  C4 [instructions_u, Exploratory]: -22.11% [-22.95, -21.27] simple; -113.62k ± 5.07k per request
  C4 [p50_us, Exploratory]: -2.99% [-5.46, -0.46] simple; -0.02k ± 0.01k per request
  C4 [p99_us, Exploratory]: -1.06% [-3.25, +1.19] simple; -0.01k ± 0.02k per request
  C4 against the stock release [Exploratory]: h3-reuse-on vs h3-official -6.06% [-8.10, -3.97]
per-round log points: C4 -2.50 -3.51 -14.60 -7.44 -5.31 -9.05 -6.24 -5.10; same-build -3.35 -0.31 -2.20 -2.13 +6.28 -3.17 -1.48 -0.97

C4 RULE: -6.50% [-9.42, -3.48] simple, 8 rounds; label MEASURED; by the 3.0% line: saves 3.0% or more: worth proposing on cycles
