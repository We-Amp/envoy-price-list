# Run L: request latency in and out of a stats flush

Run data/stats/flush-latency/lat. Cells own/nosink, own/statsd, own/otlp, shared/nosink, shared/statsd. Complete rounds 4 ([1, 2, 3, 5]), legs recorded 21, invalid 0.


## p99 (primary; Holm over 6 rows)

| Row | Rounds | Mean | 95% interval | % of OUT | p | Holm p | Reach (shifts) | Floor | Status |
|---|---|---|---|---|---|---|---|---|---|
| L1 own/nosink | 4 | -7 us | [-27 us, 13 us] | -1.0% | 0.354 | 0.709 | 18 us (17) | 120 us | not shown (bound 120 us) |
| L1 own/statsd | 4 | -21 us | [-35 us, -6 us] | -2.5% | 0.021 | 0.083 | 6 us (9) | 120 us | not shown (bound 120 us) |
| L1 own/otlp | 4 | -5 us | [-23 us, 13 us] | -0.7% | 0.453 | 0.709 | 8 us (13) | 120 us | not shown (bound 120 us) |
| L2 own, arms pooled | 4 | 531 us | [-112 us, 1173 us] | 72.8% | 0.078 | 0.235 | 858 us (9) | 120 us | not shown (bound 858 us) |
| L3 shared/nosink | 4 | 3562 us | [3385 us, 3739 us] | 526.0% | 0.000 | 0.000 | 32 us (17) | 120 us | finding |
| L3 shared/statsd | 4 | 3727 us | [3508 us, 3947 us] | 438.2% | 0.000 | 0.000 | 6 us (5) | 120 us | finding |
| placebo: L3 own/nosink | 4 | 4 us | [-24 us, 31 us] | - | 0.702 | - | 33 us (17) | 120 us | descriptive |
| placebo: L3 own/statsd | 4 | 2 us | [-7 us, 12 us] | - | 0.512 | - | 9 us (9) | 120 us | descriptive |
| placebo: L3 own/otlp | 4 | 5 us | [-24 us, 33 us] | - | 0.636 | - | 13 us (13) | 120 us | descriptive |
| descriptive: L1 shared/nosink | 4 | 2947 us | [2622 us, 3273 us] | - | 0.000 | - | 18 us (17) | 120 us | descriptive |
| descriptive: L1 shared/statsd | 4 | 3106 us | [3031 us, 3182 us] | - | 0.000 | - | 5 us (5) | 120 us | descriptive |
| sensitivity: L1 own/nosink, background bins removed | 4 | -7 us | [-27 us, 13 us] | - | 0.354 | - | - (0) | 120 us | descriptive |
| sensitivity: L1 own/statsd, background bins removed | 4 | -21 us | [-35 us, -6 us] | - | 0.021 | - | - (0) | 120 us | descriptive |
| sensitivity: L1 own/otlp, background bins removed | 4 | -5 us | [-23 us, 13 us] | - | 0.453 | - | - (0) | 120 us | descriptive |

## p50 (secondary)

| Row | Rounds | Mean | 95% interval | % of OUT | p | Holm p | Reach (shifts) | Floor | Status |
|---|---|---|---|---|---|---|---|---|---|
| L1 own/nosink | 4 | -2 us | [-4 us, -0 us] | -0.5% | 0.042 | - | 3 us (17) | 20 us | not shown (bound 20 us) |
| L1 own/statsd | 4 | -3 us | [-5 us, -1 us] | -0.7% | 0.012 | - | 1 us (9) | 20 us | not shown (bound 20 us) |
| L1 own/otlp | 4 | -1 us | [-2 us, -1 us] | -0.3% | 0.012 | - | 2 us (13) | 20 us | not shown (bound 20 us) |
| L2 own, arms pooled | 4 | 4 us | [1 us, 7 us] | 0.9% | 0.030 | - | 7 us (9) | 20 us | not shown (bound 20 us) |
| L3 shared/nosink | 4 | 72 us | [43 us, 101 us] | 18.3% | 0.004 | - | 7 us (17) | 20 us | secondary: differs |
| L3 shared/statsd | 4 | 190 us | [146 us, 234 us] | 42.0% | 0.001 | - | 2 us (5) | 20 us | secondary: differs |
| placebo: L3 own/nosink | 4 | -2 us | [-10 us, 6 us] | - | 0.482 | - | 10 us (17) | 20 us | descriptive |
| placebo: L3 own/statsd | 4 | -1 us | [-2 us, 1 us] | - | 0.291 | - | 1 us (9) | 20 us | descriptive |
| placebo: L3 own/otlp | 4 | 1 us | [-3 us, 4 us] | - | 0.592 | - | 4 us (13) | 20 us | descriptive |
| descriptive: L1 shared/nosink | 4 | 12 us | [1 us, 22 us] | - | 0.038 | - | 3 us (17) | 20 us | descriptive |
| descriptive: L1 shared/statsd | 4 | 5 us | [1 us, 9 us] | - | 0.028 | - | 1 us (5) | 20 us | descriptive |
| sensitivity: L1 own/nosink, background bins removed | 4 | -2 us | [-4 us, -0 us] | - | 0.042 | - | - (0) | 20 us | descriptive |
| sensitivity: L1 own/statsd, background bins removed | 4 | -3 us | [-5 us, -1 us] | - | 0.012 | - | - (0) | 20 us | descriptive |
| sensitivity: L1 own/otlp, background bins removed | 4 | -1 us | [-2 us, -1 us] | - | 0.012 | - | - (0) | 20 us | descriptive |

## share over 2 ms (secondary)

| Row | Rounds | Mean | 95% interval | % of OUT | p | Holm p | Reach (shifts) | Floor | Status |
|---|---|---|---|---|---|---|---|---|---|
| L1 own/nosink | 4 | 0.066 pt | [-0.083 pt, 0.215 pt] | - | 0.253 | - | 0.057 pt (17) | 0.200 pt | not shown (bound 0.200 pt) |
| L1 own/statsd | 4 | 0.026 pt | [-0.051 pt, 0.103 pt] | - | 0.366 | - | 0.017 pt (9) | 0.200 pt | not shown (bound 0.200 pt) |
| L1 own/otlp | 4 | 0.054 pt | [-0.020 pt, 0.128 pt] | - | 0.105 | - | 0.030 pt (13) | 0.200 pt | not shown (bound 0.200 pt) |
| L2 own, arms pooled | 4 | 0.546 pt | [0.075 pt, 1.018 pt] | - | 0.035 | - | 0.152 pt (9) | 0.200 pt | secondary: differs |
| L3 shared/nosink | 4 | 18.849 pt | [17.845 pt, 19.853 pt] | - | 0.000 | - | 0.206 pt (17) | 0.200 pt | secondary: differs |
| L3 shared/statsd | 4 | 25.652 pt | [24.674 pt, 26.630 pt] | - | 0.000 | - | 0.046 pt (5) | 0.200 pt | secondary: differs |
| placebo: L3 own/nosink | 4 | -0.106 pt | [-0.296 pt, 0.084 pt] | - | 0.174 | - | 0.108 pt (17) | 0.200 pt | descriptive |
| placebo: L3 own/statsd | 4 | 0.026 pt | [-0.066 pt, 0.117 pt] | - | 0.439 | - | 0.044 pt (9) | 0.200 pt | descriptive |
| placebo: L3 own/otlp | 4 | -0.026 pt | [-0.188 pt, 0.137 pt] | - | 0.650 | - | 0.097 pt (13) | 0.200 pt | descriptive |
| descriptive: L1 shared/nosink | 4 | 4.759 pt | [4.443 pt, 5.076 pt] | - | 0.000 | - | 0.082 pt (17) | 0.200 pt | descriptive |
| descriptive: L1 shared/statsd | 4 | 6.413 pt | [6.188 pt, 6.639 pt] | - | 0.000 | - | 0.012 pt (5) | 0.200 pt | descriptive |
| sensitivity: L1 own/nosink, background bins removed | 4 | 0.066 pt | [-0.083 pt, 0.215 pt] | - | 0.253 | - | - (0) | 0.200 pt | descriptive |
| sensitivity: L1 own/statsd, background bins removed | 4 | 0.026 pt | [-0.051 pt, 0.103 pt] | - | 0.366 | - | - (0) | 0.200 pt | descriptive |
| sensitivity: L1 own/otlp, background bins removed | 4 | 0.054 pt | [-0.020 pt, 0.128 pt] | - | 0.105 | - | - (0) | 0.200 pt | descriptive |

## Invalid legs (every one the run recorded, re-run ones included)

A gate that the effect under study can trip (a stalled worker: client rate, probe drain, flush count) removes the leg and its round is run again; those legs are listed here, not hidden. Legs run: 36, invalid: 3.

| Cell | Invalid legs | Leg | Re-run later | Reasons |
|---|---|---|---|---|
| own/nosink | 0 | - | - | - |
| own/statsd | 0 | - | - | - |
| own/otlp | 0 | - | - | - |
| shared/nosink | 0 | - | - | - |
| shared/statsd | 3 | r01-shared-statsd | yes | evidence: listener 2xx between the leg's two quiescent reads = Nighthawk 2xx + probe answered + map requests, exactly: 2, expected 0 +/- 0 |
| shared/statsd | 3 | r02-shared-statsd | yes | evidence: listener 2xx between the leg's two quiescent reads = Nighthawk 2xx + probe answered + map requests, exactly: 1, expected 0 +/- 0 |
| shared/statsd | 3 | r04-shared-statsd | yes | evidence: listener 2xx between the leg's two quiescent reads = Nighthawk 2xx + probe answered + map requests, exactly: 1, expected 0 +/- 0 |

## Per cell (descriptive; pooled over the complete rounds)

| | own/nosink | own/statsd | own/otlp | shared/nosink | shared/statsd |
|---|---|---|---|---|---|
| whole flushes | 24 | 24 | 24 | 24 | 24 |
| flush wall s, mean | 0.2771 | 2.398 | 1.319 | 0.3915 | 3.578 |
| flush wall s, max | 0.38 | 2.555 | 1.425 | 0.5 | 3.695 |
| probes IN | 4552 | 45268 | 24560 | 6748 | 67936 |
| probes OUT | 178412 | 137700 | 158400 | 176224 | 115046 |
| IN p50 us | 391.1 | 446.8 | 393.7 | 405 | 458.5 |
| OUT p50 us | 393.3 | 449.6 | 394.3 | 392.3 | 452.5 |
| IN p99 us | 666.1 | 816.1 | 673.8 | 3556 | 3972 |
| OUT p99 us | 671.8 | 832 | 678.6 | 676.5 | 850.7 |
| IN p99.9 us (no verdict) | 1101 | 985.6 | 1769 | 4701 | 4966 |
| OUT p99.9 us (no verdict) | 835.5 | 976.8 | 848.5 | 829.6 | 1036 |
| IN max us | 9371 | 3.083e+04 | 9654 | 8239 | 1.831e+04 |
| OUT max us | 2.552e+04 | 1.243e+04 | 2.542e+04 | 1.307e+04 | 1.157e+04 |
| IN over 20 ms | 0 | 4 | 0 | 0 | 0 |
| OUT over 20 ms | 1 | 0 | 2 | 0 | 0 |
| IN over 100 ms | 0 | 0 | 0 | 0 | 0 |
| OUT over 100 ms | 0 | 0 | 0 | 0 | 0 |
| admin /ready IN p50 us | 1.32e+05 | 1.19e+06 | 6.101e+05 | 1.922e+05 | 1.788e+06 |
| admin IN max us | 3.251e+05 | 2.504e+06 | 1.323e+06 | 4.766e+05 | 3.631e+06 |
| admin OUT p50 us | 278.5 | 326.2 | 293.6 | 281.3 | 345.5 |
| admin OUT max us | 2019 | 3158 | 834.1 | 1030 | 2335 |
| admin unanswered | 0 | 0 | 0 | 0 | 0 |
| longest admin wait / flush wall, mean | 0.9083 | 0.9894 | 0.9397 | 0.9386 | 0.9934 |
| longest admin wait / flush wall, max | 0.9804 | 0.9983 | 0.9618 | 0.991 | 0.9989 |
| control (origin direct) p50 us | 108.3 | 111.7 | 122.1 | 123.2 | 102.8 |
| control p99 us | 171.2 | 161.1 | 176.5 | 167.2 | 165 |
| control max us | 199.3 | 880.8 | 3236 | 279.8 | 612.6 |
| 20 ms bins with a slow control probe | 0 | 0 | 0 | 0 | 0 |
| probes dropped for a loop gap | 0 | 0 | 0 | 0 | 4 |
| worker busy share | 0.308 | 0.357 | 0.3099 | 0.3088 | 0.3493 |
| worker on shared CPU: wait in / out, per leg | [0.3, 0.5, 0.6, 0.4] | [16.5, 2.3, 17.6, 2.2] | [0.8, 0.9, 1.2, 0.7] | [184.4, 176.6, 173.2, 172.2] | [142.6, 160.5, 146.4, 124.9] |
| same: against the other workers in flush | [1.9, 0.8, 0.2, 0.4] | [0.3, 0.9, 2.0, 0.9] | [0.4, 1.0, 4.0, 0.4] | [7068.6, 5657.4, 6316.7, 1584.5] | [1261.9, 483.6, 2518.6, 3583.1] |
| Nighthawk p50 us (background load) | 403.8 | 460.9 | 398.4 | 405 | 481.8 |
| Nighthawk p99 us | 655.8 | 796.8 | 654.5 | 766.4 | 3650 |
| Nighthawk pending total, per leg | [16, 16, 16, 16] | [16, 16, 16, 16] | [16, 16, 16, 16] | [16, 16, 16, 16] | [16, 16, 16, 16] |
| Nighthawk overflow counters, per leg | [0, 0, 0, 0] | [0, 0, 0, 0] | [0, 0, 0, 0] | [0, 0, 0, 0] | [0, 0, 0, 0] |
| Nighthawk queue_to_connect max us, per leg | [35024.895, 37820.415, 47118.335, 38498.303] | [38201.343, 26999.807, 30570.495, 28027.903] | [31444.990999999998, 39249.919, 43683.839, 41684.990999999995] | [28893.183, 34230.271, 33184.767, 38270.975] | [39497.727000000006, 29726.718999999997, 39993.343, 42092.543000000005] |
| cycles per request (context only) | 5.316e+05 | 7.197e+05 | 5.808e+05 | 5.338e+05 | 7.142e+05 |
| watchdog counters, change | main_thread.watchdog_miss 28, server.main_thread.watchdog_miss 28 | main_thread.watchdog_mega_miss 40, main_thread.watchdog_miss 56, server.main_thread.watchdog_mega_miss 40, server.main_thread.watchdog_miss 56 | main_thread.watchdog_mega_miss 39, main_thread.watchdog_miss 56, server.main_thread.watchdog_mega_miss 39, server.main_thread.watchdog_miss 56 | main_thread.watchdog_mega_miss 8, main_thread.watchdog_miss 44, server.main_thread.watchdog_mega_miss 8, server.main_thread.watchdog_miss 44 | main_thread.watchdog_mega_miss 48, main_thread.watchdog_miss 56, server.main_thread.watchdog_mega_miss 48, server.main_thread.watchdog_miss 56 |

## Probe latency by intended time since the flush start (10 ms bins; n / p50 us / p99 us)

| Bin start ms | own/nosink | own/statsd | own/otlp | shared/nosink | shared/statsd |
|---|---|---|---|---|---|
| -20 | 192 / 396 / 668 | 192 / 417 / 916 | 192 / 408 / 715 | 192 / 367 / 839 | 192 / 455 / 821 |
| -10 | 192 / 394 / 2634 | 192 / 466 / 2918 | 192 / 407 / 6082 | 192 / 397 / 4128 | 192 / 460 / 5508 |
| 0 | 192 / 393 / 1873 | 192 / 459 / 1917 | 192 / 394 / 2613 | 192 / 402 / 4316 | 192 / 468 / 5797 |
| 10 | 192 / 385 / 659 | 192 / 427 / 827 | 192 / 397 / 694 | 192 / 408 / 3946 | 192 / 455 / 4531 |
| 20 | 192 / 402 / 636 | 192 / 456 / 833 | 192 / 384 / 625 | 192 / 402 / 4184 | 192 / 455 / 3660 |
| 30 | 192 / 392 / 660 | 192 / 453 / 709 | 192 / 406 / 617 | 192 / 394 / 3556 | 192 / 465 / 4419 |
| 40 | 192 / 397 / 661 | 192 / 465 / 884 | 192 / 399 / 707 | 192 / 405 / 2450 | 192 / 459 / 2984 |
| 50 | 192 / 400 / 653 | 192 / 449 / 754 | 192 / 388 / 694 | 192 / 402 / 3605 | 192 / 452 / 3796 |
| 60 | 192 / 389 / 708 | 192 / 461 / 781 | 192 / 398 / 625 | 192 / 399 / 3903 | 192 / 451 / 3914 |
| 70 | 192 / 398 / 670 | 192 / 451 / 822 | 192 / 401 / 667 | 192 / 400 / 3923 | 192 / 472 / 4628 |
| 80 | 192 / 389 / 655 | 192 / 462 / 892 | 192 / 371 / 636 | 192 / 399 / 3186 | 192 / 456 / 4982 |
| 90 | 192 / 391 / 707 | 192 / 459 / 808 | 192 / 397 / 672 | 192 / 408 / 3683 | 192 / 472 / 3261 |
