## Primary rows (LRU against MRU, Holm across all 4)

| Run | Rate | Metric | Effect [95% CI] | raw p | Holm p | pairs |
|---|---|---|---|---|---|---|
| two-hop | 5200 | cycles_total_all | +3.4% [+2.0, +4.8] | 3.8e-05 | 0.00015 | 24 |
| two-hop | 8000 | cycles_total_all | +1.4% [+0.2, +2.6] | 0.02 | 0.059 | 24 |
| one-hop | 5200 | cycles_total | +0.1% [-0.5, +0.7] | 0.66 | 0.91 | 12 |
| one-hop | 8000 | cycles_total | +0.3% [-0.5, +1.1] | 0.45 | 0.91 | 12 |

## Two hops: load spread on hop B (medians over valid legs; ranges)

| Rate | Arm | valid legs | hop B worker shares, sorted (median per rank) | busiest share (range) | busiest worker busy, of a core (range) | hop B busy (mean of 4) | A->B conns carrying traffic | A->B conns open | hop A worker share max |
|---|---|---|---|---|---|---|---|---|---|
| 5200 | mru | 24 | 0.65 / 0.27 / 0.00 / 0.00 | 0.65 (0.48 to 1.00) | 0.75 (0.59 to 0.98) | 0.29 | 648 (490 to 719) | 1024 | 0.25 |
| 5200 | lru | 24 | 0.26 / 0.25 / 0.25 / 0.24 | 0.26 (0.25 to 0.27) | 0.31 (0.30 to 0.31) | 0.30 | 1024 (940 to 1024) | 1024 | 0.26 |
| 8000 | mru | 24 | 0.50 / 0.35 / 0.14 / 0.00 | 0.50 (0.36 to 0.69) | 0.84 (0.64 to 1.00) | 0.42 | 685 (423 to 750) | 1024 | 0.25 |
| 8000 | lru | 24 | 0.26 / 0.25 / 0.25 / 0.24 | 0.26 (0.25 to 0.26) | 0.43 (0.40 to 0.44) | 0.41 | 1024 (1024 to 1024) | 1024 | 0.26 |

## Two hops: CPU and latency (medians; LRU against MRU, paired 95% intervals)

| Rate | hop A cycles/req MRU -> LRU | effect | hop B cycles/req MRU -> LRU | effect | both hops MRU -> LRU | effect | p50 us MRU -> LRU | effect | p99 us MRU -> LRU | effect |
|---|---|---|---|---|---|---|---|---|---|---|
| 5200 | 504.8k -> 515.4k | +2.1% [+1.6, +2.5] | 494.4k -> 512.3k | +4.8% [+2.0, +7.6] | 999.7k -> 1026.5k | +3.4% [+2.0, +4.8] | 689 -> 692 | -5.2% [-10.2, -0.1] | 1095 -> 1117 | +0.5% [-3.7, +4.9] |
| 8000 | 457.4k -> 471.7k | +3.6% [+3.0, +4.2] | 467.3k -> 465.1k | -0.6% [-2.8, +1.6] | 925.2k -> 937.6k | +1.4% [+0.2, +2.6] | 787 -> 838 | -2.7% [-15.2, +11.6] | 1557 -> 1782 | -2.0% [-18.7, +18.2] |

## One hop (control): CPU, latency, upstream connections

| Rate | cycles/req MRU -> LRU | effect | instructions:u effect | p50 us MRU -> LRU | effect | p99 us MRU -> LRU | effect | upstream conns carrying traffic MRU / LRU | worker share max MRU / LRU |
|---|---|---|---|---|---|---|---|---|---|
| 5200 | 527.7k -> 530.3k | +0.1% [-0.5, +0.7] | +0.1% [+0.1, +0.2] | 400 -> 408 | +1.8% [+0.0, +3.5] | 628 -> 642 | +2.5% [+0.2, +4.9] | 67 / 587 | 0.25 / 0.25 |
| 8000 | 489.0k -> 491.1k | +0.3% [-0.5, +1.1] | +0.2% [+0.1, +0.3] | 406 -> 412 | +1.0% [-1.4, +3.5] | 896 -> 931 | -1.1% [-21.1, +24.0] | 210 / 1018 | 0.25 / 0.25 |

## Two hops: user and kernel cycles per request (medians MRU -> LRU, paired 95% intervals)

| Rate | Part | MRU -> LRU | effect | delta cycles/req |
|---|---|---|---|---|
| 5200 | hop A user | 345.4k -> 344.0k | -0.4% [-0.8, -0.0] | -1.4k |
| 5200 | hop A kernel | 159.8k -> 171.5k | +7.5% [+6.9, +8.0] | +11.7k |
| 5200 | hop B user | 331.1k -> 343.0k | +4.0% [+1.9, +6.2] | +11.9k |
| 5200 | hop B kernel | 163.1k -> 169.5k | +6.5% [+2.3, +10.8] | +6.4k |
| 5200 | hop B context switches/req | 1.25 -> 1.34 | +52.6% [+9.3, +113.0] | +0.09 |
| 5200 | hop A context switches/req | 1.58 -> 1.56 | -1.2% [-2.2, -0.2] | -0.02 |
| 8000 | hop A user | 315.1k -> 317.5k | +1.0% [+0.4, +1.6] | +2.4k |
| 8000 | hop A kernel | 142.2k -> 155.3k | +9.3% [+8.6, +10.1] | +13.1k |
| 8000 | hop B user | 316.8k -> 316.8k | -0.3% [-2.0, +1.5] | +0.0k |
| 8000 | hop B kernel | 150.1k -> 148.0k | -1.3% [-4.6, +2.1] | -2.1k |
| 8000 | hop B context switches/req | 0.89 -> 0.81 | -4.3% [-17.4, +10.8] | -0.08 |
| 8000 | hop A context switches/req | 1.27 -> 1.25 | -1.1% [-3.2, +1.0] | -0.01 |

## Two hops: idle-state residency on the Envoy CPUs during the window (sum over CPUs, medians)

(not recorded in this run)

## One hop: user and kernel cycles per request (medians MRU -> LRU, paired 95% intervals)

| Rate | Part | MRU -> LRU | effect | delta cycles/req |
|---|---|---|---|---|
| 5200 | user | 346.2k -> 346.5k | +0.0% [-0.6, +0.6] | +0.3k |
| 5200 | kernel | 181.9k -> 183.5k | +0.3% [-0.4, +1.1] | +1.6k |
| 5200 | context switches/req | 1.61 -> 1.60 | -1.2% [-2.9, +0.6] | -0.01 |
| 8000 | user | 322.8k -> 324.0k | +0.2% [-0.6, +1.1] | +1.2k |
| 8000 | kernel | 166.3k -> 167.3k | +0.4% [-0.7, +1.4] | +0.9k |
| 8000 | context switches/req | 1.24 -> 1.23 | +0.7% [-2.7, +4.2] | -0.02 |

## One hop: idle-state residency on the Envoy CPUs during the window (sum over CPUs, medians)

| Rate | Arm | legs | per state: residency (CPUs) and entries per second |
|---|---|---|---|
| 5200 | mru | 12 | C1 0.08 CPU, 618/s; C1E 1.42 CPU, 7421/s; C3 0.00 CPU, 0/s; C6 1.10 CPU, 2701/s; POLL 0.00 CPU, 20/s |
| 5200 | lru | 12 | C1 0.05 CPU, 447/s; C1E 1.50 CPU, 7712/s; C3 0.00 CPU, 0/s; C6 1.07 CPU, 2529/s; POLL 0.00 CPU, 20/s |
| 8000 | mru | 12 | C1 0.18 CPU, 1396/s; C1E 1.46 CPU, 8896/s; C3 0.00 CPU, 0/s; C6 0.48 CPU, 1222/s; POLL 0.00 CPU, 17/s |
| 8000 | lru | 12 | C1 0.11 CPU, 1057/s; C1E 1.57 CPU, 9452/s; C3 0.00 CPU, 0/s; C6 0.41 CPU, 1073/s; POLL 0.00 CPU, 18/s |

## Saturation probe, probe-two-hop (end-to-end p99 limit 2 ms; every rep valid and under)

| Arm | Rate | p99 us per rep | p50 us per rep | valid | hop A busy | hop B busy | hop B busiest share |
|---|---|---|---|---|---|---|---|
| lru | 5200 | 1126 / 1126 / 1088 | 691 / 695 / 683 | y / y / y | 0.30 | 0.30 | 0.25 |
| lru | 6400 | 1298 / 1284 / 1781 | 718 / 732 / 833 | y / y / y | 0.36 | 0.35 | 0.25 |
| lru | 8000 | 1814 / 1780 / 1814 | 830 / 909 / 888 | y / y / y | 0.42 | 0.41 | 0.26 |
| lru | 9600 | 1751 / 1813 / 1754 | 851 / 825 / 839 | y / n: client overflow/pool-exhausted counters 136 (upstream_cx_ove / n: client overflow/pool-exhausted counters 210 (upstream_cx_ove | 0.49 | 0.49 | 0.25 |
| lru | 11200 | 1763 / 1667 / 1766 | 888 / 899 / 904 | n: client overflow/pool-exhausted counters 4 (upstream_cx_overf / n: client overflow/pool-exhausted counters 31 (upstream_cx_over / y | 0.56 | 0.56 | 0.25 |
| mru | 5200 | 1245 / 972 / 1089 | 841 / 661 / 687 | y / y / y | 0.30 | 0.29 | 0.68 |
| mru | 6400 | 3054 / 1134 / 1739 | 1513 / 704 / 803 | y / y / y | 0.35 | 0.33 | 0.66 |
| mru | 8000 | 1429 / 1955 / 2250 | 747 / 778 / 867 | y / y / y | 0.42 | 0.42 | 0.53 |
| mru | 9600 | 1393 / 1462 / 1599 | 788 / 766 / 787 | y / y / n: client overflow/pool-exhausted counters 13 (upstream_cx_over | 0.48 | 0.51 | 0.39 |
| mru | 11200 | 1617 / 2837 / 5748 | 844 / 915 / 2904 | n: client overflow/pool-exhausted counters 2 (upstream_cx_overf / n: client overflow/pool-exhausted counters 486 (upstream_cx_ove / n: client overflow/pool-exhausted counters 534 (upstream_cx_ove | 0.53 | 0.56 | 0.41 |

Highest rate with every rep valid and p99 < 2 ms (no failure below it): lru 8000, mru 5200

## Saturation probe, probe-one-hop (end-to-end p99 limit 2 ms; every rep valid and under)

| Arm | Rate | p99 us per rep | p50 us per rep | valid | hop A busy | hop B busy | hop B busiest share |
|---|---|---|---|---|---|---|---|
| lru | 5200 | 633 / 666 / 667 | 410 / 416 / 410 | y / y / y | 0.31 | - | - |
| lru | 8000 | 870 / 1000 / 840 | 413 / 407 / 432 | y / y / y | 0.44 | - | - |
| lru | 11200 | 1100 / 1423 / 1522 | 460 / 466 / 507 | y / y / y | 0.57 | - | - |
| lru | 14400 | 1519 / 1506 / 1434 | 587 / 718 / 679 | n: client overflow/pool-exhausted counters 283 (upstream_cx_ove / n: client overflow/pool-exhausted counters 373 (upstream_cx_ove / n: client overflow/pool-exhausted counters 337 (upstream_cx_ove | 0.71 | - | - |
| mru | 5200 | 625 / 617 / 643 | 398 / 390 / 403 | y / y / y | 0.31 | - | - |
| mru | 8000 | 1122 / 1352 / 1239 | 428 / 430 / 386 | y / y / y | 0.44 | - | - |
| mru | 11200 | 1116 / 1501 / 1164 | 460 / 501 / 486 | n: client overflow/pool-exhausted counters 134 (upstream_cx_ove / y / n: client overflow/pool-exhausted counters 123 (upstream_cx_ove | 0.57 | - | - |
| mru | 14400 | 1479 / 1600 / 1354 | 610 / 713 / 666 | n: client overflow/pool-exhausted counters 386 (upstream_cx_ove / n: client overflow/pool-exhausted counters 182 (upstream_cx_ove / y | 0.71 | - | - |

Highest rate with every rep valid and p99 < 2 ms (no failure below it): lru 11200, mru 8000
