## demand-pool

Legs (current / valid): 5200 lru 12/12, 5200 mru 12/12, 5200 mru-noeb 12/12, 8000 lru 12/12, 8000 mru 12/12, 8000 mru-noeb 12/12

| Comparison | Rate | cycles/req, both hops (medians, k) | effect [95% CI] | raw p | Holm p | pairs |
|---|---|---|---|---|---|---|
| lru vs mru (primary) | 5200 | 1058.7 → 1065.1 | +0.6% [+0.1, +1.2] | 0.027 | 0.053 | 12 |
| lru vs mru (primary) | 8000 | 970.3 → 969.6 | +0.1% [-0.4, +0.6] | 0.57 | 0.57 | 12 |
| mru-noeb vs mru (exploratory) | 5200 | 1058.7 → 1041.7 | -1.6% [-2.6, -0.7] | 0.0028 | – | 12 |
| mru-noeb vs mru (exploratory) | 8000 | 970.3 → 960.2 | -0.9% [-1.4, -0.4] | 0.0024 | – | 12 |

| Rate | Arm | hop A pool (gauge) | hop B pool to origin | hop B conns per worker (median leg) | hop B shares sorted (median per rank) | busiest share median (min–max) | busiest worker, of a core | hop B busy | legs with busiest share > 0.30 |
|---|---|---|---|---|---|---|---|---|---|
| 5200 | lru | 18–32 | 12–26 | 6/6/5/5 (widest 8/8/7/7) | 0.28/0.26/0.24/0.23 | 0.28 (0.25–0.29) | 0.36 (0.34–0.38) | 0.33 (0.33–0.33) | 0 of 12 |
| 5200 | mru | 18–34 | 12–28 | 5/5/4/4 (widest 5/5/5/4) | 0.31/0.27/0.24/0.18 | 0.31 (0.27–0.38) | 0.41 (0.36–0.49) | 0.33 (0.31–0.33) | 8 of 12 |
| 5200 | mru-noeb | 18–30 | 13–28 | 10/8/6/5 (widest 13/9/5/3) | 0.41/0.33/0.19/0.09 | 0.41 (0.33–0.52) | 0.52 (0.43–0.63) | 0.32 (0.30–0.33) | 12 of 12 |
| 8000 | lru | 25–34 | 19–32 | 7/6/6/6 (widest 8/8/8/7) | 0.27/0.25/0.25/0.24 | 0.27 (0.25–0.28) | 0.49 (0.47–0.53) | 0.46 (0.46–0.47) | 0 of 12 |
| 8000 | mru | 28–48 | 16–39 | 9/9/8/8 (widest 10/9/9/9) | 0.30/0.27/0.24/0.19 | 0.30 (0.26–0.39) | 0.56 (0.48–0.69) | 0.46 (0.45–0.47) | 7 of 12 |
| 8000 | mru-noeb | 28–35 | 19–32 | 12/8/8/7 (widest 11/9/8/4) | 0.35/0.31/0.23/0.14 | 0.35 (0.33–0.40) | 0.64 (0.59–0.70) | 0.45 (0.44–0.46) | 12 of 12 |

| Comparison | Rate | hop A cycles/req | hop B cycles/req | p50 µs (medians) | p50 effect | p99 µs (medians) | p99 effect |
|---|---|---|---|---|---|---|---|
| lru vs mru | 5200 | 505.8k → 505.3k, -0.2% [-0.6, +0.1] | 553.9k → 560.9k, +1.4% [+0.4, +2.5] | 651 → 673 | +3.1% [+2.3, +3.9] | 953 → 1011 | +5.5% [+4.3, +6.8] |
| lru vs mru | 8000 | 457.1k → 454.4k, -0.7% [-1.2, -0.2] | 511.4k → 515.1k, +0.9% [+0.1, +1.7] | 664 → 685 | +2.6% [+1.5, +3.7] | 1047 → 1092 | +4.3% [+1.8, +6.8] |
| mru-noeb vs mru | 5200 | 505.8k → 503.6k, -0.3% [-0.8, +0.3] | 553.9k → 538.3k, -2.9% [-4.7, -1.1] | 651 → 650 | +0.0% [-0.9, +1.0] | 953 → 965 | +1.8% [+0.5, +3.1] |
| mru-noeb vs mru | 8000 | 457.1k → 455.7k, -0.5% [-1.1, +0.2] | 511.4k → 504.2k, -1.3% [-2.2, -0.3] | 664 → 670 | +0.8% [+0.1, +1.5] | 1047 → 1070 | +3.5% [+0.2, +6.8] |

| Rate | Arm | hop A upstream cx opened in window (median, max) | hop A remote closes | hop A retries | hop A 5xx/resets | hop B max-requests closes | p99 > 2 ms legs |
|---|---|---|---|---|---|---|---|
| 5200 | lru | 0.0, 2 | 0 | 0 | 0 | 0 | 0 of 12 |
| 5200 | mru | 0.0, 1 | 0 | 0 | 0 | 0 | 0 of 12 |
| 5200 | mru-noeb | 0.0, 1 | 0 | 0 | 0 | 0 | 0 of 12 |
| 8000 | lru | 0.0, 2 | 0 | 0 | 0 | 0 | 0 of 12 |
| 8000 | mru | 0.0, 3 | 0 | 0 | 0 | 0 | 0 of 12 |
| 8000 | mru-noeb | 0.0, 1 | 0 | 0 | 0 | 0 | 0 of 12 |

## demand-pool-ka

Legs (current / valid): 8000 lru 12/12, 8000 mru 12/12

| Comparison | Rate | cycles/req, both hops (medians, k) | effect [95% CI] | raw p | Holm p | pairs |
|---|---|---|---|---|---|---|
| lru vs mru (primary) | 8000 | 971.4 → 975.8 | +0.4% [-0.1, +0.8] | 0.12 | 0.12 | 12 |

| Rate | Arm | hop A pool (gauge) | hop B pool to origin | hop B conns per worker (median leg) | hop B shares sorted (median per rank) | busiest share median (min–max) | busiest worker, of a core | hop B busy | legs with busiest share > 0.30 |
|---|---|---|---|---|---|---|---|---|---|
| 8000 | lru | 16–20 | 12–16 | 5/5/5/4 (widest 6/5/5/4) | 0.26/0.26/0.25/0.23 | 0.26 (0.26–0.27) | 0.50 (0.48–0.51) | 0.47 (0.46–0.47) | 0 of 12 |
| 8000 | mru | 15–22 | 11–13 | 5/5/4/4 (widest 5/5/4/2) | 0.26/0.25/0.25/0.23 | 0.26 (0.26–0.28) | 0.49 (0.48–0.52) | 0.46 (0.46–0.47) | 0 of 12 |

| Comparison | Rate | hop A cycles/req | hop B cycles/req | p50 µs (medians) | p50 effect | p99 µs (medians) | p99 effect |
|---|---|---|---|---|---|---|---|
| lru vs mru | 8000 | 457.8k → 459.0k, +0.1% [-0.5, +0.7] | 515.6k → 517.8k, +0.6% [-0.1, +1.4] | 648 → 671 | +3.4% [+2.2, +4.7] | 1028 → 1076 | +4.3% [+1.4, +7.4] |

| Rate | Arm | hop A upstream cx opened in window (median, max) | hop A remote closes | hop A retries | hop A 5xx/resets | hop B max-requests closes | p99 > 2 ms legs |
|---|---|---|---|---|---|---|---|
| 8000 | lru | 158.5, 162 | 0 | 0 | 0 | 1972 | 0 of 12 |
| 8000 | mru | 158.5, 161 | 0 | 0 | 0 | 1928 | 0 of 12 |

