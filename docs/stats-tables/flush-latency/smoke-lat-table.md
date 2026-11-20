# Run L: request latency in and out of a stats flush

Run ~/epl/runs/stats-latency/smoke/smoke-lat. Cells own/nosink, own/statsd, own/otlp, shared/nosink, shared/statsd. Complete rounds 1 ([1]), legs recorded 5, invalid 0. **Incomplete (under 4 complete rounds): no verdict.**


## p99 (primary; Holm over 6 rows)

| Row | Rounds | Mean | 95% interval | % of OUT | p | Holm p | Reach (shifts) | Floor | Status |
|---|---|---|---|---|---|---|---|---|---|
| L1 own/nosink | 1 | -2 us | - | -0.3% | - | - | 44 us (17) | 120 us | incomplete, no verdict |
| L1 own/statsd | 1 | -22 us | - | -2.6% | - | - | 23 us (9) | 120 us | incomplete, no verdict |
| L1 own/otlp | 1 | -8 us | - | -1.1% | - | - | 10 us (13) | 120 us | incomplete, no verdict |
| L2 own, arms pooled | 1 | 196 us | - | 26.2% | - | - | 31 us (9) | 120 us | incomplete, no verdict |
| L3 shared/nosink | 1 | 3615 us | - | 548.6% | - | - | 89 us (17) | 120 us | incomplete, no verdict |
| L3 shared/statsd | 1 | 3618 us | - | 427.3% | - | - | 18 us (3) | 120 us | incomplete, no verdict |
| placebo: L3 own/nosink | 1 | 65 us | - | - | - | - | 98 us (17) | 120 us | incomplete, no verdict |
| placebo: L3 own/statsd | 1 | 7 us | - | - | - | - | 22 us (9) | 120 us | incomplete, no verdict |
| placebo: L3 own/otlp | 1 | 0 us | - | - | - | - | 30 us (13) | 120 us | incomplete, no verdict |
| descriptive: L1 shared/nosink | 1 | 2815 us | - | - | - | - | 23 us (17) | 120 us | incomplete, no verdict |
| descriptive: L1 shared/statsd | 1 | 2980 us | - | - | - | - | 16 us (3) | 120 us | incomplete, no verdict |
| sensitivity: L1 own/nosink, background bins removed | 1 | -2 us | - | - | - | - | - (0) | 120 us | incomplete, no verdict |
| sensitivity: L1 own/statsd, background bins removed | 1 | -22 us | - | - | - | - | - (0) | 120 us | incomplete, no verdict |
| sensitivity: L1 own/otlp, background bins removed | 1 | -8 us | - | - | - | - | - (0) | 120 us | incomplete, no verdict |

## p50 (secondary)

| Row | Rounds | Mean | 95% interval | % of OUT | p | Holm p | Reach (shifts) | Floor | Status |
|---|---|---|---|---|---|---|---|---|---|
| L1 own/nosink | 1 | -6 us | - | -1.4% | - | - | 6 us (17) | 20 us | incomplete, no verdict |
| L1 own/statsd | 1 | -5 us | - | -1.1% | - | - | 2 us (9) | 20 us | incomplete, no verdict |
| L1 own/otlp | 1 | -2 us | - | -0.5% | - | - | 5 us (13) | 20 us | incomplete, no verdict |
| L2 own, arms pooled | 1 | -5 us | - | -1.1% | - | - | 12 us (9) | 20 us | incomplete, no verdict |
| L3 shared/nosink | 1 | 47 us | - | 11.9% | - | - | 10 us (17) | 20 us | incomplete, no verdict |
| L3 shared/statsd | 1 | 174 us | - | 38.1% | - | - | 4 us (3) | 20 us | incomplete, no verdict |
| placebo: L3 own/nosink | 1 | -2 us | - | - | - | - | 14 us (17) | 20 us | incomplete, no verdict |
| placebo: L3 own/statsd | 1 | 2 us | - | - | - | - | 2 us (9) | 20 us | incomplete, no verdict |
| placebo: L3 own/otlp | 1 | 2 us | - | - | - | - | 4 us (13) | 20 us | incomplete, no verdict |
| descriptive: L1 shared/nosink | 1 | 3 us | - | - | - | - | 5 us (17) | 20 us | incomplete, no verdict |
| descriptive: L1 shared/statsd | 1 | 7 us | - | - | - | - | 1 us (3) | 20 us | incomplete, no verdict |
| sensitivity: L1 own/nosink, background bins removed | 1 | -6 us | - | - | - | - | - (0) | 20 us | incomplete, no verdict |
| sensitivity: L1 own/statsd, background bins removed | 1 | -5 us | - | - | - | - | - (0) | 20 us | incomplete, no verdict |
| sensitivity: L1 own/otlp, background bins removed | 1 | -2 us | - | - | - | - | - (0) | 20 us | incomplete, no verdict |

## share over 2 ms (secondary)

| Row | Rounds | Mean | 95% interval | % of OUT | p | Holm p | Reach (shifts) | Floor | Status |
|---|---|---|---|---|---|---|---|---|---|
| L1 own/nosink | 1 | -0.020 pt | - | - | - | - | 0.155 pt (17) | 0.200 pt | incomplete, no verdict |
| L1 own/statsd | 1 | 0.009 pt | - | - | - | - | 0.017 pt (9) | 0.200 pt | incomplete, no verdict |
| L1 own/otlp | 1 | 0.061 pt | - | - | - | - | 0.017 pt (13) | 0.200 pt | incomplete, no verdict |
| L2 own, arms pooled | 1 | 0.485 pt | - | - | - | - | 0.089 pt (9) | 0.200 pt | incomplete, no verdict |
| L3 shared/nosink | 1 | 18.890 pt | - | - | - | - | 0.086 pt (17) | 0.200 pt | incomplete, no verdict |
| L3 shared/statsd | 1 | 23.857 pt | - | - | - | - | 0.028 pt (3) | 0.200 pt | incomplete, no verdict |
| placebo: L3 own/nosink | 1 | 0.003 pt | - | - | - | - | 0.232 pt (17) | 0.200 pt | incomplete, no verdict |
| placebo: L3 own/statsd | 1 | -0.028 pt | - | - | - | - | 0.054 pt (9) | 0.200 pt | incomplete, no verdict |
| placebo: L3 own/otlp | 1 | -0.007 pt | - | - | - | - | 0.084 pt (13) | 0.200 pt | incomplete, no verdict |
| descriptive: L1 shared/nosink | 1 | 4.713 pt | - | - | - | - | 0.065 pt (17) | 0.200 pt | incomplete, no verdict |
| descriptive: L1 shared/statsd | 1 | 5.996 pt | - | - | - | - | 0.021 pt (3) | 0.200 pt | incomplete, no verdict |
| sensitivity: L1 own/nosink, background bins removed | 1 | -0.020 pt | - | - | - | - | - (0) | 0.200 pt | incomplete, no verdict |
| sensitivity: L1 own/statsd, background bins removed | 1 | 0.009 pt | - | - | - | - | - (0) | 0.200 pt | incomplete, no verdict |
| sensitivity: L1 own/otlp, background bins removed | 1 | 0.061 pt | - | - | - | - | - (0) | 0.200 pt | incomplete, no verdict |

## Invalid legs (every one the run recorded, re-run ones included)

A gate that the effect under study can trip (a stalled worker: client rate, probe drain, flush count) removes the leg and its round is run again; those legs are listed here, not hidden. Legs run: 5, invalid: 0.

| Cell | Invalid legs | Leg | Re-run later | Reasons |
|---|---|---|---|---|
| own/nosink | 0 | - | - | - |
| own/statsd | 0 | - | - | - |
| own/otlp | 0 | - | - | - |
| shared/nosink | 0 | - | - | - |
| shared/statsd | 0 | - | - | - |

## Per cell (descriptive; pooled over the complete rounds)

| | own/nosink | own/statsd | own/otlp | shared/nosink | shared/statsd |
|---|---|---|---|---|---|
| whole flushes | 6 | 6 | 6 | 6 | 6 |
| flush wall s, mean | 0.2825 | 2.351 | 1.298 | 0.3975 | 3.64 |
| flush wall s, max | 0.325 | 2.42 | 1.335 | 0.495 | 3.75 |
| probes IN | 1164 | 11092 | 6040 | 1716 | 17280 |
| probes OUT | 44582 | 34650 | 39699 | 44025 | 28461 |
| IN p50 us | 395.3 | 457.2 | 398.6 | 395.4 | 462.3 |
| OUT p50 us | 400.9 | 462.3 | 400.6 | 392.8 | 455.5 |
| IN p99 us | 706.8 | 825.8 | 680.4 | 3474 | 3827 |
| OUT p99 us | 708.7 | 848.2 | 688.1 | 659.1 | 846.7 |
| IN p99.9 us (no verdict) | 857.7 | 983 | 1621 | 4567 | 4732 |
| OUT p99.9 us (no verdict) | 878.9 | 1004 | 820.8 | 788.1 | 983 |
| IN max us | 875.1 | 6860 | 6624 | 4632 | 7319 |
| OUT max us | 8883 | 6732 | 3781 | 6594 | 4538 |
| IN over 20 ms | 0 | 0 | 0 | 0 | 0 |
| OUT over 20 ms | 0 | 0 | 0 | 0 | 0 |
| IN over 100 ms | 0 | 0 | 0 | 0 | 0 |
| OUT over 100 ms | 0 | 0 | 0 | 0 | 0 |
| admin /ready IN p50 us | 1.394e+05 | 1.186e+06 | 5.786e+05 | 1.976e+05 | 1.806e+06 |
| admin IN max us | 2.605e+05 | 2.384e+06 | 1.228e+06 | 4.738e+05 | 3.673e+06 |
| admin OUT p50 us | 268.1 | 339.7 | 267.8 | 290.4 | 339.8 |
| admin OUT max us | 377.2 | 503.5 | 350.7 | 789.8 | 1212 |
| admin unanswered | 0 | 0 | 0 | 0 | 0 |
| longest admin wait / flush wall, mean | 0.9427 | 0.9844 | 0.9539 | 0.9264 | 0.9949 |
| longest admin wait / flush wall, max | 0.9553 | 0.9869 | 0.9635 | 0.9573 | 0.9959 |
| control (origin direct) p50 us | 124.2 | 124.4 | 123.9 | 96.56 | 125.3 |
| control p99 us | 163.5 | 166.5 | 168.8 | 171.1 | 164.2 |
| control max us | 191.8 | 186.4 | 2573 | 201.6 | 727.7 |
| 20 ms bins with a slow control probe | 0 | 0 | 0 | 0 | 0 |
| probes dropped for a loop gap | 0 | 0 | 0 | 0 | 2 |
| worker busy share | 0.3117 | 0.3587 | 0.313 | 0.3092 | 0.3497 |
| worker on shared CPU: wait in / out, per leg | [0.5] | [0.9] | [4.3] | [198.2] | [176.7] |
| same: against the other workers in flush | [2.1] | [0.3] | [1.9] | [2030.0] | [2367.7] |
| Nighthawk p50 us (background load) | 410.7 | 485.4 | 403.5 | 410 | 475.6 |
| Nighthawk p99 us | 676.6 | 838.5 | 666 | 765.9 | 3459 |
| Nighthawk pending total, per leg | [16] | [16] | [16] | [16] | [16] |
| Nighthawk overflow counters, per leg | [0] | [0] | [0] | [0] | [0] |
| Nighthawk queue_to_connect max us, per leg | [31668.223] | [41392.127] | [31596.542999999998] | [34086.911] | [33169.407] |
| cycles per request (context only) | 5.381e+05 | 7.17e+05 | 5.857e+05 | 5.343e+05 | 7.176e+05 |
| watchdog counters, change | main_thread.watchdog_miss 8, server.main_thread.watchdog_miss 8 | main_thread.watchdog_mega_miss 10, main_thread.watchdog_miss 14, server.main_thread.watchdog_mega_miss 10, server.main_thread.watchdog_miss 14 | main_thread.watchdog_mega_miss 10, main_thread.watchdog_miss 14, server.main_thread.watchdog_mega_miss 10, server.main_thread.watchdog_miss 14 | main_thread.watchdog_mega_miss 2, main_thread.watchdog_miss 11, server.main_thread.watchdog_mega_miss 2, server.main_thread.watchdog_miss 11 | main_thread.watchdog_mega_miss 12, main_thread.watchdog_miss 14, server.main_thread.watchdog_mega_miss 12, server.main_thread.watchdog_miss 14 |

## Probe latency by intended time since the flush start (10 ms bins; n / p50 us / p99 us)

| Bin start ms | own/nosink | own/statsd | own/otlp | shared/nosink | shared/statsd |
|---|---|---|---|---|---|
| -20 | 48 / 395 / 600 | 48 / 468 / 682 | 48 / 394 / 653 | 48 / 418 / 675 | 48 / 455 / 898 |
| -10 | 48 / 396 / 2420 | 48 / 477 / 2148 | 48 / 410 / 2696 | 48 / 396 / 2478 | 48 / 457 / 1664 |
| 0 | 48 / 392 / 2104 | 48 / 479 / 1290 | 48 / 401 / 860 | 48 / 417 / 4863 | 48 / 544 / 6989 |
| 10 | 48 / 412 / 721 | 48 / 463 / 975 | 48 / 391 / 643 | 48 / 417 / 3911 | 48 / 448 / 4360 |
| 20 | 48 / 387 / 561 | 48 / 464 / 750 | 48 / 393 / 617 | 48 / 409 / 3204 | 48 / 480 / 4161 |
| 30 | 48 / 376 / 725 | 48 / 447 / 717 | 48 / 384 / 657 | 48 / 375 / 2857 | 48 / 503 / 5001 |
| 40 | 48 / 353 / 629 | 48 / 457 / 742 | 48 / 407 / 671 | 48 / 397 / 3369 | 48 / 459 / 2579 |
| 50 | 48 / 407 / 715 | 48 / 434 / 826 | 48 / 413 / 625 | 48 / 380 / 4185 | 48 / 441 / 4151 |
| 60 | 48 / 396 / 671 | 48 / 473 / 671 | 48 / 393 / 654 | 48 / 382 / 4215 | 48 / 454 / 3301 |
| 70 | 48 / 407 / 853 | 48 / 429 / 747 | 48 / 408 / 647 | 48 / 393 / 1301 | 48 / 468 / 3997 |
| 80 | 48 / 375 / 600 | 48 / 430 / 980 | 48 / 395 / 580 | 48 / 413 / 3985 | 48 / 501 / 3641 |
| 90 | 48 / 385 / 666 | 48 / 462 / 849 | 48 / 400 / 641 | 48 / 371 / 1952 | 48 / 438 / 3435 |
