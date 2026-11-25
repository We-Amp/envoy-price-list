# wave 8 W8-1: cycles (user+kernel) of the Envoy process per request

variants: a=a, b=b, d=d, c=c; rider: c
Holm families: patch ['C1', 'C2', 'C3']; rider ['R1', 'R2']
- a: 72 current legs, 72 valid, evidence failing 0, rounds complete 6, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-24T16:24:54Z, finished 2026-11-24T17:11:24Z; legs replaced by the harness 0
- b: 32 current legs, 32 valid, evidence failing 0, rounds complete 8, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-24T17:11:25Z, finished 2026-11-24T17:32:06Z; legs replaced by the harness 0
- d: 16 current legs, 16 valid, evidence failing 0, rounds complete 4, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-24T17:32:06Z, finished 2026-11-24T17:42:25Z; legs replaced by the harness 0
- c: 36 current legs, 36 valid, evidence failing 0, rounds complete 6, stop reason fixed rounds, incomplete False, binaries unchanged at the end True, started 2026-11-24T17:42:25Z, finished 2026-11-24T18:05:39Z; legs replaced by the harness 0

## shape b1m (run a, floor 1.0 log points)

- target rate [800] req/s; rounds [1, 2, 3, 4, 5, 6]

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs (median of legs / highest leg) | latency max µs (median / largest leg) | Envoy busy (CPUs of 4) | busiest worker share (max) | memory allocated at the window's end, MiB (median / largest) | heap size MiB (median / largest) | user cycles /req, lowest to highest leg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frag-on-ch8k | 6/6 | 3611.4k | 882.2k | 2729.4k | 825.7k | 1110.1k | 1.50 | 2569 | 3678 / 3966 | 11417 / 16264 | 1.271 | 0.252 | 36.9 / 37.6 | 64.0 / 80.0 | 874.9k to 897.7k |
| frag-on-cl8k | 6/6 | 3393.1k | 710.5k | 2682.6k | 450.5k | 1087.0k | 1.62 | 2227 | 3032 / 3103 | 10012 / 13712 | 1.195 | 0.253 | 20.9 / 21.4 | 48.0 / 58.0 | 695.0k to 714.0k |
| off-ch8k | 6/6 | 3669.3k | 989.6k | 2680.2k | 733.5k | 1058.3k | 1.50 | 2627 | 3870 / 4151 | 12001 / 13862 | 1.291 | 0.253 | 30.5 / 31.0 | 56.0 / 58.0 | 985.4k to 994.9k |
| off-cl8k | 6/6 | 3369.9k | 701.8k | 2669.3k | 448.9k | 1084.4k | 1.57 | 2244 | 3023 / 3079 | 10278 / 14275 | 1.187 | 0.253 | 21.0 / 21.4 | 46.0 / 54.0 | 696.5k to 706.1k |
| official-ch8k | 6/6 | 3684.3k | 994.0k | 2690.5k | 730.7k | 1062.5k | 1.53 | 2614 | 3770 / 4121 | 11568 / 13139 | 1.297 | 0.254 | 30.7 / 31.0 | 58.0 / 70.0 | 988.3k to 1004.9k |
| official-ch8k-A2 | 6/6 | 3683.0k | 995.9k | 2687.1k | 729.6k | 1059.2k | 1.51 | 2629 | 3910 / 4163 | 10029 / 16611 | 1.296 | 0.252 | 30.5 / 31.5 | 59.0 / 64.0 | 982.3k to 1000.0k |

| row (same-build check, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| official-ch8k-A2 vs official-ch8k | -0.23 | [-1.22, +0.76] | -0.23 | ±0.96 / ±0.99 (widened) | 2/6 | 0.56 | - | -8.6k ± 35.3k |

same-build check on b1m: PASS (effect -0.23 log points against the floor 1.0; quoted interval [-1.22, +0.76] log points includes 0); reach 1.22% (simple)

| row (build control (expected zero), cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| off-ch8k vs official-ch8k | -0.40 | [-1.17, +0.37] | -0.40 | ±0.52 / ±0.78 (widened) | 1/6 | 0.1 | - | -14.8k ± 19.1k |

build control on b1m: -0.40% [-1.17, +0.37] simple. Fixed rule (+1.0% or more, interval excluding 0): not met: the in-binary figure is the headline. User instructions per request: off-ch8k 733480, official-ch8k 730668 (+0.24% [-0.51, +0.99])

| row (fixed rows, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| C1: frag-on-ch8k vs off-ch8k | -1.40 | [-2.31, -0.48] | -1.41 | ±0.84 / ±0.92 (widened) | 1/6 | 0.0076 | 0.023 | -51.3k ± 30.5k | finding; basis: Measured
  C1 [cycles_u, Exploratory]: -10.73% [-11.55, -9.91] simple; paired difference -106.2k ± 7.3k per request
  C1 [cycles_k, Exploratory]: +2.05% [+1.09, +3.01] simple; paired difference +54.9k ± 23.7k per request
  C1 [instructions_u, Exploratory]: +12.74% [+11.85, +13.64] simple; paired difference +93.4k ± 4.4k per request
  beside C1, against the stock release [Exploratory]: frag-on-ch8k vs official-ch8k -1.80% [-2.77, -0.82] simple (6 rounds)
  C1 [p50_us, Exploratory]: -2.79% [-4.75, -0.79] simple
  C1 [p99_us, Exploratory]: -5.74% [-13.44, +2.64] simple
| CL-b1m: frag-on-cl8k vs off-cl8k | +0.51 | [-0.36, +1.39] | +0.51 | ±0.73 / ±0.87 (widened) | 5/6 | 0.13 | - | +17.3k ± 24.6k | not a finding; basis: Measured
  CL-b1m [cycles_u, Exploratory]: +0.91% [-0.53, +2.37] simple; paired difference +6.4k ± 10.1k per request
  CL-b1m [cycles_k, Exploratory]: +0.41% [-0.38, +1.20] simple; paired difference +10.9k ± 14.6k per request
  CL-b1m [instructions_u, Exploratory]: +1.00% [-0.34, +2.36] simple; paired difference +4.5k ± 6.0k per request
  CL-b1m [p50_us, Exploratory]: -0.38% [-2.39, +1.67] simple
  CL-b1m [p99_us, Exploratory]: +0.15% [-1.24, +1.56] simple

recovered share [Exploratory]: (off-ch8k minus frag-on-ch8k) over (off-ch8k minus off-cl8k), cycles per request, per round: 17.2% [7.1, 27.3] (t interval, 6 rounds)
marker in the scored legs [the plan's instruction marker does not apply: the copy is one instruction per run]: user cycles per request, lowest to highest leg: off-ch8k 985.4k to 994.9k, frag-on-ch8k 874.9k to 897.7k: ranges apart YES. User instructions: off-ch8k 728.7k to 733.8k, frag-on-ch8k 823.5k to 829.7k

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| frag-on-ch8k vs official-ch8k | -1.80 | [-2.77, -0.82] | -1.81 | ±0.97 / ±0.99 (widened) | 0/6 | 0.0048 | - | -66.1k ± 35.3k |
| off-ch8k vs off-cl8k | +8.81 | [+7.97, +9.66] | +8.44 | ±0.53 / ±0.78 (widened) | 6/6 | 1.6e-07 | - | +297.1k ± 18.8k |
| frag-on-ch8k vs frag-on-cl8k | +6.74 | [+5.76, +7.72] | +6.52 | ±0.83 / ±0.92 (widened) | 6/6 | 5.5e-06 | - | +228.5k ± 29.5k |
| frag-on-ch8k vs off-cl8k | +7.29 | [+6.25, +8.33] | +7.03 | ±0.92 / ±0.97 (widened) | 6/6 | 6.4e-06 | - | +245.8k ± 33.2k |

per-round log points (arm vs ref), for the reviewer:
- official-ch8k-A2 vs official-ch8k: -0.09 -0.32 +0.68 -1.94 +0.38 -0.11
- off-ch8k vs official-ch8k: -0.31 -0.22 +0.40 -0.79 -0.46 -1.03
- frag-on-ch8k vs off-ch8k: -1.78 +0.13 -1.86 -1.66 -2.04 -1.24
- frag-on-cl8k vs off-cl8k: +0.16 +1.06 -0.64 +1.28 +0.46 +0.74

## shape b64k (run a, floor 1.0 log points)

- target rate [4000] req/s; rounds [1, 2, 3, 4, 5, 6]

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs (median of legs / highest leg) | latency max µs (median / largest leg) | Envoy busy (CPUs of 4) | busiest worker share (max) | memory allocated at the window's end, MiB (median / largest) | heap size MiB (median / largest) | user cycles /req, lowest to highest leg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frag-on-ch8k | 6/6 | 733.3k | 389.1k | 343.4k | 195.3k | 125.5k | 1.69 | 466 | 710 / 761 | 8550 / 9589 | 1.321 | 0.254 | 20.8 / 21.1 | 39.0 / 42.0 | 383.9k to 393.3k |
| frag-on-cl8k | 6/6 | 703.7k | 366.5k | 337.9k | 165.7k | 124.7k | 1.70 | 443 | 647 / 663 | 8143 / 9730 | 1.271 | 0.254 | 17.8 / 18.6 | 39.0 / 44.0 | 364.1k to 370.9k |
| off-ch8k | 6/6 | 734.2k | 395.8k | 338.4k | 191.4k | 125.1k | 1.68 | 473 | 773 / 879 | 9241 / 10377 | 1.322 | 0.253 | 20.1 / 20.6 | 36.0 / 40.0 | 389.9k to 398.9k |
| off-cl8k | 6/6 | 701.5k | 365.7k | 335.8k | 165.6k | 124.8k | 1.69 | 448 | 651 / 727 | 9138 / 10723 | 1.267 | 0.255 | 17.6 / 18.2 | 38.0 / 42.0 | 363.5k to 370.7k |
| official-ch8k | 6/6 | 736.2k | 396.2k | 339.5k | 189.8k | 124.8k | 1.65 | 480 | 773 / 834 | 9492 / 10850 | 1.325 | 0.255 | 20.5 / 21.7 | 39.0 / 48.0 | 393.0k to 402.1k |
| official-ch8k-A2 | 6/6 | 732.6k | 395.3k | 336.8k | 189.8k | 125.0k | 1.67 | 471 | 719 / 786 | 8008 / 10499 | 1.319 | 0.254 | 20.5 / 21.0 | 39.0 / 42.0 | 392.9k to 397.1k |

| row (same-build check, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| official-ch8k-A2 vs official-ch8k | -0.46 | [-1.46, +0.55] | -0.46 | ±0.99 / ±1.01 (widened) | 2/6 | 0.28 | - | -3.4k ± 7.3k |

same-build check on b64k: PASS (effect -0.46 log points against the floor 1.0; quoted interval [-1.47, +0.55] log points includes 0); reach 1.47% (simple)

| row (build control (expected zero), cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| off-ch8k vs official-ch8k | -0.24 | [-1.23, +0.76] | -0.24 | ±0.97 / ±1.00 (widened) | 2/6 | 0.55 | - | -1.8k ± 7.1k |

build control on b64k: -0.24% [-1.23, +0.76] simple. Fixed rule (+1.0% or more, interval excluding 0): not met: the in-binary figure is the headline. User instructions per request: off-ch8k 191405, official-ch8k 189763 (+0.81% [+0.13, +1.50])

| row (fixed rows, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| C2: frag-on-ch8k vs off-ch8k | -0.36 | [-1.65, +0.94] | -0.36 | ±1.30 / ±1.20 (t) | 3/6 | 0.5 | 1 | -2.7k ± 9.5k | not a finding; basis: Measured
  C2 [cycles_u, Exploratory]: -1.57% [-2.82, -0.30] simple; paired difference -6.2k ± 5.0k per request
  C2 [cycles_k, Exploratory]: +1.04% [-0.36, +2.46] simple; paired difference +3.5k ± 4.7k per request
  C2 [instructions_u, Exploratory]: +2.05% [+1.35, +2.76] simple; paired difference +3.9k ± 0.4k per request
  beside C2, against the stock release [Exploratory]: frag-on-ch8k vs official-ch8k -0.61% [-1.91, +0.72] simple (6 rounds)
  C2 [p50_us, Exploratory]: -1.74% [-4.15, +0.73] simple
  C2 [p99_us, Exploratory]: -8.56% [-14.57, -2.14] simple
| CL-b64k: frag-on-cl8k vs off-cl8k | +0.01 | [-1.11, +1.15] | +0.01 | ±1.13 / ±1.09 (t) | 3/6 | 0.98 | - | +0.1k ± 8.0k | not a finding; basis: Measured
  CL-b64k [cycles_u, Exploratory]: +0.15% [-1.10, +1.42] simple; paired difference +0.6k ± 4.6k per request
  CL-b64k [cycles_k, Exploratory]: -0.14% [-1.23, +0.97] simple; paired difference -0.5k ± 3.7k per request
  CL-b64k [instructions_u, Exploratory]: +0.06% [-0.60, +0.74] simple; paired difference +0.1k ± 0.1k per request
  CL-b64k [p50_us, Exploratory]: -0.75% [-2.92, +1.48] simple
  CL-b64k [p99_us, Exploratory]: -2.74% [-8.21, +3.05] simple

recovered share [Exploratory]: (off-ch8k minus frag-on-ch8k) over (off-ch8k minus off-cl8k), cycles per request, per round: 8.2% [-27.4, 43.8] (t interval, 6 rounds)
marker in the scored legs [the plan's instruction marker does not apply: the copy is one instruction per run]: user cycles per request, lowest to highest leg: off-ch8k 389.9k to 398.9k, frag-on-ch8k 383.9k to 393.3k: ranges apart NO. User instructions: off-ch8k 190.7k to 191.6k, frag-on-ch8k 194.9k to 195.4k

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| frag-on-ch8k vs official-ch8k | -0.61 | [-1.91, +0.72] | -0.61 | ±1.32 / ±1.21 (t) | 3/6 | 0.29 | - | -4.5k ± 9.7k |
| off-ch8k vs off-cl8k | +4.24 | [+3.15, +5.34] | +4.15 | ±1.05 / ±1.04 (t) | 6/6 | 0.00016 | - | +29.9k ± 7.5k |
| frag-on-ch8k vs frag-on-cl8k | +3.85 | [+2.64, +5.07] | +3.78 | ±1.17 / ±1.11 (t) | 6/6 | 0.00041 | - | +27.1k ± 8.3k |
| frag-on-ch8k vs off-cl8k | +3.86 | [+2.22, +5.53] | +3.79 | ±1.59 / ±1.39 (t) | 6/6 | 0.0017 | - | +27.2k ± 11.4k |

per-round log points (arm vs ref), for the reviewer:
- official-ch8k-A2 vs official-ch8k: +0.26 -0.10 -1.19 -1.30 -1.34 +0.88
- off-ch8k vs official-ch8k: -0.92 +0.91 -0.44 -0.51 -1.35 +0.84
- frag-on-ch8k vs off-ch8k: +1.23 -0.58 +0.08 -2.45 +0.29 -0.76
- frag-on-cl8k vs off-cl8k: +1.59 -0.88 +0.72 -1.39 -0.20 +0.24

## shape ngx-ch64 (run b, floor 1.5 log points)

- target rate [2000] req/s; rounds [1, 2, 3, 4, 5, 6, 7, 8]

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs (median of legs / highest leg) | latency max µs (median / largest leg) | Envoy busy (CPUs of 4) | busiest worker share (max) | memory allocated at the window's end, MiB (median / largest) | heap size MiB (median / largest) | user cycles /req, lowest to highest leg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frag-on | 8/8 | 815.6k | 456.7k | 359.7k | 185.6k | 132.0k | 1.86 | 578 | 785 / 802 | 3938 / 4925 | 0.759 | 0.254 | 16.0 / 16.5 | 24.0 / 28.0 | 446.4k to 469.7k |
| off | 8/8 | 819.6k | 459.9k | 359.7k | 183.5k | 132.7k | 1.88 | 563 | 788 / 811 | 4660 / 5262 | 0.766 | 0.255 | 15.9 / 16.4 | 24.0 / 28.0 | 457.8k to 464.4k |
| official | 8/8 | 827.9k | 467.2k | 362.0k | 182.1k | 132.4k | 1.88 | 570 | 782 / 799 | 4360 / 5056 | 0.770 | 0.253 | 15.8 / 16.4 | 24.0 / 28.0 | 460.0k to 471.3k |
| official-A2 | 8/8 | 819.5k | 460.6k | 359.5k | 182.1k | 132.6k | 1.88 | 563 | 788 / 809 | 4465 / 5416 | 0.763 | 0.254 | 15.8 / 16.5 | 24.0 / 28.0 | 455.7k to 467.1k |

| row (same-build check, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| official-A2 vs official | -1.00 | [-2.07, +0.08] | -1.01 | ±1.04 / ±1.09 (widened) | 2/8 | 0.055 | - | -8.3k ± 8.5k |

same-build check on ngx-ch64: PASS (effect -1.01 log points against the floor 1.5; quoted interval [-2.09, +0.08] log points includes 0); reach 2.08% (simple)

| row (build control (expected zero), cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| off vs official | -1.13 | [-2.03, -0.23] | -1.14 | ±0.74 / ±0.91 (widened) | 0/8 | 0.0084 | - | -9.4k ± 6.1k |

build control on ngx-ch64: -1.13% [-2.03, -0.23] simple. Fixed rule (+1.0% or more, interval excluding 0): not met: the in-binary figure is the headline. User instructions per request: off 183548, official 182077 (+0.82% [+0.12, +1.52])

| row (fixed rows, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| C3: frag-on vs off | -0.02 | [-1.26, +1.24] | -0.02 | ±1.25 / ±1.24 (t) | 3/8 | 0.97 | 1 | -0.1k ± 10.3k | not a finding; basis: Measured
  C3 [cycles_u, Exploratory]: -0.48% [-1.91, +0.98] simple; paired difference -2.1k ± 6.7k per request
  C3 [cycles_k, Exploratory]: +0.56% [-0.72, +1.87] simple; paired difference +2.1k ± 4.7k per request
  C3 [instructions_u, Exploratory]: +1.12% [+0.41, +1.83] simple; paired difference +2.0k ± 0.5k per request
  beside C3, against the stock release [Exploratory]: frag-on vs official -1.15% [-2.75, +0.47] simple (8 rounds)
  C3 [p50_us, Exploratory]: +1.26% [-2.71, +5.40] simple
  C3 [p99_us, Exploratory]: -0.44% [-1.43, +0.55] simple

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| frag-on vs official | -1.15 | [-2.75, +0.47] | -1.16 | ±1.63 / ±1.51 (t) | 3/8 | 0.14 | - | -9.5k ± 13.4k |

per-round log points (arm vs ref), for the reviewer:
- official-A2 vs official: -1.94 -2.23 -0.06 -1.78 +0.46 +0.44 -0.43 -2.53
- off vs official: -2.64 -1.16 -0.03 -1.88 -0.78 -0.58 -0.30 -1.74
- frag-on vs off: -1.37 -1.93 +1.87 -0.14 -0.94 -0.38 +0.41 +2.34

## shape b1m-h2tls (run d, floor 1.5 log points)

- target rate [400] req/s; rounds [1, 2, 3, 4]

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs (median of legs / highest leg) | latency max µs (median / largest leg) | Envoy busy (CPUs of 4) | busiest worker share (max) | memory allocated at the window's end, MiB (median / largest) | heap size MiB (median / largest) | user cycles /req, lowest to highest leg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frag-on | 4/4 | 5820.4k | 2391.1k | 3429.3k | 3886.8k | 1718.9k | 2.25 | 2742 | 2943 / 2952 | 4435 / 7085 | 1.026 | 0.252 | 8.2 / 8.3 | 18.0 / 18.0 | 2361.8k to 2430.0k |
| off | 4/4 | 5855.1k | 2473.5k | 3381.6k | 3768.7k | 1710.9k | 2.25 | 2759 | 2958 / 2962 | 4085 / 6882 | 1.032 | 0.252 | 8.6 / 8.7 | 20.0 / 20.0 | 2469.6k to 2489.5k |
| official | 4/4 | 5877.1k | 2493.5k | 3385.5k | 3766.4k | 1709.3k | 2.25 | 2770 | 2965 / 2996 | 7247 / 7403 | 1.035 | 0.252 | 8.2 / 8.4 | 20.0 / 20.0 | 2482.9k to 2509.7k |
| official-A2 | 4/4 | 5885.2k | 2499.4k | 3385.8k | 3765.7k | 1707.8k | 2.25 | 2775 | 2969 / 2987 | 5520 / 7128 | 1.037 | 0.252 | 8.1 / 8.4 | 20.0 / 20.0 | 2485.6k to 2515.9k |

| row (same-build check, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| official-A2 vs official | +0.09 | [-1.90, +2.11] | +0.09 | ±2.00 / ±1.40 (t) | 2/4 | 0.9 | - | +5.1k ± 117.8k |

same-build check on b1m-h2tls: PASS (effect +0.09 log points against the floor 1.5; quoted interval [-1.91, +2.08] log points includes 0); reach 2.09% (simple)

| row (build control (expected zero), cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| off vs official | -0.46 | [-1.28, +0.37] | -0.46 | ±0.81 / ±0.83 (widened) | 0/4 | 0.17 | - | -27.2k ± 47.3k |

build control on b1m-h2tls: -0.46% [-1.28, +0.37] simple. Fixed rule (+1.0% or more, interval excluding 0): not met: the in-binary figure is the headline. User instructions per request: off 3768671, official 3766428 (+0.06% [-0.60, +0.73])

| row (fixed rows, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| T1: frag-on vs off | -0.65 | [-3.21, +1.97] | -0.66 | ±2.61 / ±1.74 (t) | 2/4 | 0.48 | - | -38.0k ± 151.9k | not a finding; basis: Measured
  T1 [cycles_u, Exploratory]: -3.36% [-5.60, -1.07] simple; paired difference -83.0k ± 56.6k per request
  T1 [cycles_k, Exploratory]: +1.32% [-1.52, +4.26] simple; paired difference +45.1k ± 97.3k per request
  T1 [instructions_u, Exploratory]: +3.14% [+2.45, +3.83] simple; paired difference +118.2k ± 1.1k per request
  beside T1, against the stock release [Exploratory]: frag-on vs official -1.11% [-3.93, +1.79] simple (4 rounds)
  T1 [p50_us, Exploratory]: -0.61% [-2.14, +0.94] simple
  T1 [p99_us, Exploratory]: -0.68% [-1.77, +0.43] simple

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| frag-on vs official | -1.11 | [-3.93, +1.79] | -1.12 | ±2.89 / ±1.90 (t) | 1/4 | 0.31 | - | -65.1k ± 168.8k |

per-round log points (arm vs ref), for the reviewer:
- official-A2 vs official: -0.50 +0.77 -1.36 +1.43
- off vs official: -1.10 -0.11 -0.64 -0.00
- frag-on vs off: +0.14 -0.87 -2.85 +0.95

## shape l64 (run c, floor 1.5 log points)

- target rate [2000] req/s; rounds [1, 2, 3, 4, 5, 6]

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs (median of legs / highest leg) | latency max µs (median / largest leg) | Envoy busy (CPUs of 4) | busiest worker share (max) | memory allocated at the window's end, MiB (median / largest) | heap size MiB (median / largest) | user cycles /req, lowest to highest leg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cl-ngx | 6/6 | 759.7k | 428.9k | 329.2k | 176.6k | 114.6k | 1.98 | 517 | 735 / 746 | 3532 / 4278 | 0.718 | 0.253 | 16.1 / 16.4 | 28.0 / 28.0 | 424.0k to 433.8k |
| cl-ngx-A2 | 6/6 | 755.7k | 430.4k | 326.1k | 176.6k | 113.2k | 1.99 | 520 | 733 / 760 | 3469 / 4623 | 0.718 | 0.255 | 15.9 / 16.3 | 27.0 / 30.0 | 424.3k to 435.2k |
| h2in-ngx | 6/6 | 884.3k | 525.4k | 359.0k | 230.4k | 133.3k | 1.89 | 552 | 803 / 4413 | 13129 / 15915 | 0.817 | 0.253 | 15.9 / 16.0 | 26.0 / 28.0 | 521.0k to 532.3k |

| row (same-build check, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| cl-ngx-A2 vs cl-ngx | -0.35 | [-1.43, +0.75] | -0.35 | ±1.09 / ±1.07 (t) | 3/6 | 0.45 | - | -2.6k ± 8.3k |

same-build check on l64: PASS (effect -0.35 log points against the floor 1.5; quoted interval [-1.44, +0.75] log points includes 0); reach 1.44% (simple)

| row (fixed rows, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| R1: h2in-ngx vs cl-ngx | +16.55 | [+15.12, +17.99] | +15.31 | ±1.23 / ±1.15 (t) | 6/6 | 5.7e-07 | 5.7e-07 | +125.5k ± 10.0k | finding; basis: Measured
  R1 [cycles_u, Exploratory]: +22.31% [+20.38, +24.27] simple; paired difference +95.8k ± 7.6k per request
  R1 [cycles_k, Exploratory]: +9.02% [+7.66, +10.39] simple; paired difference +29.6k ± 4.2k per request
  R1 [instructions_u, Exploratory]: +30.55% [+29.67, +31.44] simple; paired difference +53.9k ± 0.4k per request
  R1 [p50_us, Exploratory]: +6.44% [+5.09, +7.80] simple
  R1 [p99_us, Exploratory]: +43.76% [-31.05, +199.76] simple

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h2in-ngx vs cl-ngx-A2 | +16.95 | [+15.85, +18.06] | +15.66 | ±0.88 / ±0.95 (widened) | 6/6 | 9.4e-08 | - | +128.1k ± 7.4k |

per-round log points (arm vs ref), for the reviewer:
- cl-ngx-A2 vs cl-ngx: -1.69 -0.70 -1.35 +0.77 +0.32 +0.55
- h2in-ngx vs cl-ngx: +13.83 +15.22 +15.11 +17.13 +14.47 +16.11

## shape l1m (run c, floor 1.5 log points)

- target rate [800] req/s; rounds [1, 2, 3, 4, 5, 6]

| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs (median of legs / highest leg) | latency max µs (median / largest leg) | Envoy busy (CPUs of 4) | busiest worker share (max) | memory allocated at the window's end, MiB (median / largest) | heap size MiB (median / largest) | user cycles /req, lowest to highest leg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cl-ngx | 6/6 | 2699.7k | 593.5k | 2105.9k | 359.4k | 862.7k | 1.86 | 1370 | 1640 / 1646 | 7107 / 10525 | 0.963 | 0.251 | 31.5 / 32.9 | 56.0 / 66.0 | 588.8k to 596.1k |
| cl-ngx-A2 | 6/6 | 2700.9k | 594.5k | 2106.1k | 359.4k | 861.9k | 1.88 | 1369 | 1631 / 1639 | 8319 / 12121 | 0.965 | 0.252 | 30.8 / 31.6 | 47.0 / 60.0 | 588.2k to 602.5k |
| h2in-ngx | 6/6 | 3563.3k | 1296.3k | 2266.9k | 1181.0k | 937.9k | 1.94 | 1800 | 14142 / 15337 | 33546 / 37806 | 1.255 | 0.255 | 34.7 / 35.3 | 56.0 / 56.0 | 1280.7k to 1312.5k |

| row (same-build check, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| cl-ngx-A2 vs cl-ngx | +0.07 | [-0.65, +0.79] | +0.07 | ±0.35 / ±0.72 (widened) | 5/6 | 0.63 | - | +1.9k ± 9.4k |

same-build check on l1m: PASS (effect +0.07 log points against the floor 1.5; quoted interval [-0.65, +0.79] log points includes 0); reach 0.79% (simple)

| row (fixed rows, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| R2: h2in-ngx vs cl-ngx | +31.99 | [+30.70, +33.29] | +27.75 | ±0.95 / ±0.98 (widened) | 6/6 | 7.8e-09 | 1.6e-08 | +863.7k ± 33.2k | finding; basis: Measured
  R2 [cycles_u, Exploratory]: +118.53% [+116.31, +120.78] simple; paired difference +702.8k ± 12.2k per request
  R2 [cycles_k, Exploratory]: +7.63% [+6.54, +8.74] simple; paired difference +160.9k ± 22.9k per request
  R2 [instructions_u, Exploratory]: +227.81% [+224.90, +230.74] simple; paired difference +818.7k ± 9.1k per request
  R2 [p50_us, Exploratory]: +31.29% [+29.79, +32.81] simple
  R2 [p99_us, Exploratory]: +761.17% [+714.34, +810.69] simple

| row (exploratory, cycles_total) | effect, simple % | quoted 95% interval, simple % | effect, log-% | half-width t / widened, log-% (wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row names another metric) |
|---|---|---|---|---|---|---|---|---|
| h2in-ngx vs cl-ngx-A2 | +31.90 | [+30.57, +33.24] | +27.68 | ±1.00 / ±1.01 (widened) | 6/6 | 1.1e-08 | - | +861.9k ± 34.5k |

per-round log points (arm vs ref), for the reviewer:
- cl-ngx-A2 vs cl-ngx: +0.04 -0.46 +0.57 +0.03 +0.05 +0.18
- h2in-ngx vs cl-ngx: +28.22 +26.81 +26.59 +28.18 +27.77 +28.95

## the fixed lines

- C1 (frag-on-ch8k vs off-ch8k): -1.40% [-2.31, -0.48] simple, 6 rounds; basis Measured
- C2 (frag-on-ch8k vs off-ch8k): -0.36% [-1.65, +0.94] simple, 6 rounds; basis Measured
- C3 (frag-on vs off): -0.02% [-1.26, +1.24] simple, 8 rounds; basis Measured
- T1 (frag-on vs off): -0.65% [-3.21, +1.97] simple, 4 rounds; basis Measured
- CL-b1m (frag-on-cl8k vs off-cl8k): +0.51% [-0.36, +1.39] simple, 6 rounds; basis Measured
- CL-b64k (frag-on-cl8k vs off-cl8k): +0.01% [-1.11, +1.15] simple, 6 rounds; basis Measured
- R1 (h2in-ngx vs cl-ngx): +16.55% [+15.12, +17.99] simple, 6 rounds; basis Measured; HARM line met (+1.0% or more, interval excluding 0)
- R2 (h2in-ngx vs cl-ngx): +31.99% [+30.70, +33.29] simple, 6 rounds; basis Measured; HARM line met (+1.0% or more, interval excluding 0)

VERDICT by the fixed lines: KILLED by the line (C1 and C2 both under 3.0%)
RIDER by the fixed line: published row (R1 +10% or more and R2 +25% or more)
