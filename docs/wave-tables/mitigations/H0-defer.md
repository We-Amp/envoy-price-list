## TCP_DEFER_ACCEPT against the idle states

Effects in log points (100 ln ratio) [95%] (n, rounds up; paired raw difference); the latency rows also as a percent change.

- h-defer-deep: A/A cycles -0.41 [-1.22, +0.40] (n 6, 1 up; -3539) (pass); A/A p50 -1.67 [-3.55, +0.20] (n 6, 1 up; -7 us); defer p50 +12.25 [+10.53, +13.97] (n 6, 6 up; +55 us) = +13.0% [+11.1, +15.0]; defer p99 +8.52 [+7.66, +9.37] (n 6, 6 up; +59 us) = +8.9% [+8.0, +9.8]; defer cycles -0.20 [-0.96, +0.57] (n 6, 3 up; -1701); c1 p50 425 us, c1 cycles 874k
- h-defer-c1only: A/A cycles +0.04 [-0.89, +0.96] (n 6, 2 up; +286) (pass); A/A p50 +0.44 [-0.45, +1.33] (n 6, 5 up; +2 us); defer p50 +15.02 [+13.92, +16.13] (n 6, 6 up; +57 us) = +16.2% [+14.9, +17.5]; defer p99 +14.34 [+13.39, +15.28] (n 6, 6 up; +59 us) = +15.4% [+14.3, +16.5]; defer cycles -0.10 [-1.07, +0.86] (n 6, 2 up; -772); c1 p50 354 us, c1 cycles 760k

Verdict: rejected: the shift does not depend on the idle states; interaction -2.77 +/- 2.05 log points (default +12.25, C1 only +15.02)
