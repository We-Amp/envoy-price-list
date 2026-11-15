## Primary rows (LRU against MRU, Holm across all 2)

| Run | Rate | Metric | Effect [95% CI] | raw p | Holm p | pairs |
|---|---|---|---|---|---|---|
| two-hop | 5200 | cycles_total_all | +3.6% [+2.2, +5.0] | 2.7e-05 | 5.4e-05 | 24 |
| two-hop | 8000 | cycles_total_all | +1.7% [+0.5, +3.0] | 0.0067 | 0.0067 | 24 |

## Two hops: load spread on hop B (medians over valid legs; ranges)

| Rate | Arm | valid legs | hop B worker shares, sorted (median per rank) | busiest share (range) | busiest worker busy, of a core (range) | hop B busy (mean of 4) | A->B conns carrying traffic | A->B conns open | hop A worker share max |
|---|---|---|---|---|---|---|---|---|---|
| 5200 | mru | 24 | 0.73 / 0.22 / 0.00 / 0.00 | 0.73 (0.39 to 1.00) | 0.84 (0.50 to 0.98) | 0.28 | 666 (602 to 748) | 1024 | 0.25 |
| 5200 | lru | 24 | 0.25 / 0.25 / 0.25 / 0.25 | 0.25 (0.25 to 0.26) | 0.31 (0.30 to 0.31) | 0.30 | 1024 (994 to 1024) | 1024 | 0.25 |
| 8000 | mru | 24 | 0.50 / 0.35 / 0.14 / 0.00 | 0.50 (0.40 to 0.71) | 0.85 (0.71 to 1.00) | 0.43 | 720 (604 to 810) | 1024 | 0.25 |
| 8000 | lru | 24 | 0.26 / 0.25 / 0.25 / 0.24 | 0.26 (0.25 to 0.26) | 0.43 (0.41 to 0.44) | 0.41 | 1024 (1024 to 1024) | 1024 | 0.26 |

## Two hops: CPU and latency (medians; LRU against MRU, paired 95% intervals)

| Rate | hop A cycles/req MRU -> LRU | effect | hop B cycles/req MRU -> LRU | effect | both hops MRU -> LRU | effect | p50 us MRU -> LRU | effect | p99 us MRU -> LRU | effect |
|---|---|---|---|---|---|---|---|---|---|---|
| 5200 | 505.4k -> 516.3k | +2.0% [+1.6, +2.4] | 489.0k -> 511.9k | +5.3% [+2.4, +8.3] | 992.8k -> 1030.0k | +3.6% [+2.2, +5.0] | 729 -> 690 | -7.6% [-12.3, -2.7] | 1158 -> 1106 | -1.5% [-5.6, +2.8] |
| 8000 | 457.4k -> 473.8k | +3.8% [+3.3, +4.4] | 476.6k -> 465.3k | -0.3% [-2.5, +2.0] | 931.4k -> 940.0k | +1.7% [+0.5, +3.0] | 795 -> 825 | -2.0% [-12.9, +10.1] | 1662 -> 1698 | -7.4% [-19.7, +6.7] |

## Two hops: user and kernel cycles per request (medians MRU -> LRU, paired 95% intervals)

| Rate | Part | MRU -> LRU | effect | delta cycles/req |
|---|---|---|---|---|
| 5200 | hop A user | 346.3k -> 344.8k | -0.5% [-0.9, -0.1] | -1.5k |
| 5200 | hop A kernel | 159.5k -> 171.5k | +7.6% [+7.1, +8.0] | +12.0k |
| 5200 | hop B user | 329.7k -> 342.4k | +4.1% [+1.8, +6.4] | +12.7k |
| 5200 | hop B kernel | 159.3k -> 170.2k | +8.0% [+3.5, +12.6] | +10.9k |
| 5200 | hop B context switches/req | 1.01 -> 1.35 | +68.0% [+22.0, +131.3] | +0.35 |
| 5200 | hop A context switches/req | 1.57 -> 1.57 | -0.8% [-1.9, +0.3] | -0.01 |
| 8000 | hop A user | 313.8k -> 318.2k | +1.3% [+0.8, +1.9] | +4.4k |
| 8000 | hop A kernel | 142.3k -> 155.1k | +9.4% [+8.6, +10.2] | +12.8k |
| 8000 | hop B user | 321.4k -> 316.4k | -0.1% [-1.9, +1.7] | -5.0k |
| 8000 | hop B kernel | 153.7k -> 148.6k | -0.5% [-3.6, +2.7] | -5.1k |
| 8000 | hop B context switches/req | 0.90 -> 0.85 | +4.2% [-8.4, +18.6] | -0.05 |
| 8000 | hop A context switches/req | 1.27 -> 1.22 | -3.9% [-5.3, -2.5] | -0.05 |

## Two hops: idle-state residency on the Envoy CPUs during the window (sum over CPUs, medians)

| Rate | Arm | legs | per state: residency (CPUs) and entries per second |
|---|---|---|---|
| 5200 | mru | 24 | C1 0.08 CPU, 1558/s; C1E 1.56 CPU, 8360/s; C3 0.00 CPU, 0/s; C6 3.82 CPU, 6482/s; POLL 0.00 CPU, 26/s |
| 5200 | lru | 24 | C1 0.10 CPU, 1088/s; C1E 2.41 CPU, 12224/s; C3 0.00 CPU, 0/s; C6 2.82 CPU, 6594/s; POLL 0.00 CPU, 33/s |
| 8000 | mru | 24 | C1 0.12 CPU, 1998/s; C1E 1.91 CPU, 12185/s; C3 0.00 CPU, 0/s; C6 2.35 CPU, 6212/s; POLL 0.00 CPU, 29/s |
| 8000 | lru | 24 | C1 0.14 CPU, 1594/s; C1E 2.55 CPU, 14556/s; C3 0.00 CPU, 0/s; C6 1.72 CPU, 4039/s; POLL 0.00 CPU, 31/s |
