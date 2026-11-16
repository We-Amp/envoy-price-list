## rt-n1000

128 legs recorded, 128 valid and current, 0 invalid; 16 rounds; Holm over 6 primary rows.

### n1000-lo @ 2000 req/s

| Arm | valid | busy (of 4 workers) | instructions:u/req (k) | total cycles/req (k) | p50 (us) | p99 (us) |
|---|---|---|---|---|---|---|
| base | 16 | 12.8% | 410.9 | 526.4 | 315 | 537 |
| d1v4 | 16 | 11.7% | 290.3 | 462.8 | 292 | 489 |
| d2v3 | 16 | 8.8% | 77.2 | 325.1 | 233 | 368 |
| base-A2 | 16 | 12.8% | 410.9 | 517.3 | 313 | 535 |

| Arm vs base | Metric | Effect [95% CI] | Widened | Arm lower | Holm p | Verdict |
|---|---|---|---|---|---|---|
| d1v4 | instructions:u | -29.3% [-29.3, -29.3] | [-29.8, -28.9] | 16/16 | – | differs |
| d1v4 | cycles:u | -14.3% [-15.1, -13.5] | [-15.2, -13.4] | 16/16 | – | differs |
| d1v4 | cycles:k | -1.2% [-3.4, +1.0] | [-3.4, +1.0] | 8/16 | – | not resolved |
| d1v4 | total cycles | -11.4% [-12.4, -10.3] | [-12.5, -10.3] | 16/16 | 2e-12 | differs |
| d1v4 | p50 | -7.1% [-8.0, -6.3] | [-8.2, -6.1] | 16/16 | – | differs |
| d1v4 | p99 | -8.9% [-10.5, -7.3] | [-10.5, -7.3] | 16/16 | – | differs |
| d2v3 | instructions:u | -81.2% [-81.2, -81.2] | [-81.3, -81.1] | 16/16 | – | differs |
| d2v3 | cycles:u | -47.9% [-48.5, -47.4] | [-48.5, -47.3] | 16/16 | – | differs |
| d2v3 | cycles:k | -2.6% [-4.2, -0.9] | [-4.2, -0.9] | 12/16 | – | differs |
| d2v3 | total cycles | -37.8% [-38.4, -37.2] | [-38.5, -37.1] | 16/16 | 0 | differs |
| d2v3 | p50 | -25.6% [-26.1, -25.1] | [-26.3, -25.0] | 16/16 | – | differs |
| d2v3 | p99 | -31.3% [-32.3, -30.3] | [-32.4, -30.3] | 16/16 | – | differs |
| base-A2 | instructions:u | +0.0% [-0.0, +0.0] | [-0.7, +0.7] | 7/16 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:u | -0.5% [-1.4, +0.4] | [-1.6, +0.5] | 9/16 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:k | -0.4% [-2.4, +1.6] | [-2.4, +1.6] | 7/16 | – | within the A/A spread (< 1%) |
| base-A2 | total cycles | -0.5% [-1.5, +0.5] | [-1.7, +0.7] | 8/16 | 0.62 | within the A/A spread (< 1%) |
| base-A2 | p50 | -0.1% [-0.8, +0.5] | [-1.0, +0.8] | 6/16 | – | within the A/A spread (< 1%) |
| base-A2 | p99 | -0.4% [-1.7, +0.9] | [-1.8, +1.0] | 8/16 | – | within the A/A spread (< 1%) |
| d2v3 vs d1v4 | instructions:u | -73.4% [-73.4, -73.4] | [-73.6, -73.2] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | cycles:u | -39.2% [-39.7, -38.7] | [-39.9, -38.6] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | cycles:k | -1.3% [-3.3, +0.7] | [-3.3, +0.7] | 9/16 | – | not resolved (exploratory) |
| d2v3 vs d1v4 | total cycles | -29.8% [-30.4, -29.2] | [-30.5, -29.1] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | p50 | -19.9% [-20.6, -19.2] | [-20.7, -19.1] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | p99 | -24.6% [-26.0, -23.2] | [-26.0, -23.2] | 16/16 | – | differs (exploratory) |

### n1000-hi @ 16000 req/s

| Arm | valid | busy (of 4 workers) | instructions:u/req (k) | total cycles/req (k) | p50 (us) | p99 (us) |
|---|---|---|---|---|---|---|
| base | 16 | 66.5% | 410.3 | 378.3 | 397 | 1024 |
| d1v4 | 16 | 59.5% | 289.9 | 338.2 | 319 | 778 |
| d2v3 | 16 | 39.9% | 76.9 | 220.8 | 167 | 330 |
| base-A2 | 16 | 66.6% | 410.3 | 378.9 | 384 | 1022 |

| Arm vs base | Metric | Effect [95% CI] | Widened | Arm lower | Holm p | Verdict |
|---|---|---|---|---|---|---|
| d1v4 | instructions:u | -29.4% [-29.4, -29.3] | [-29.8, -28.9] | 16/16 | – | differs |
| d1v4 | cycles:u | -14.1% [-14.7, -13.5] | [-14.9, -13.3] | 16/16 | – | differs |
| d1v4 | cycles:k | +4.6% [+3.1, +6.1] | [+3.0, +6.1] | 1/16 | – | differs |
| d1v4 | total cycles | -11.0% [-11.7, -10.3] | [-11.8, -10.1] | 16/16 | 1.4e-14 | differs |
| d1v4 | p50 | -21.1% [-25.4, -16.7] | [-25.4, -16.7] | 16/16 | – | differs |
| d1v4 | p99 | -23.3% [-29.9, -16.1] | [-29.9, -16.1] | 15/16 | – | differs |
| d2v3 | instructions:u | -81.3% [-81.3, -81.3] | [-81.4, -81.1] | 16/16 | – | differs |
| d2v3 | cycles:u | -52.9% [-53.2, -52.6] | [-53.3, -52.5] | 16/16 | – | differs |
| d2v3 | cycles:k | +15.1% [+13.6, +16.6] | [+13.5, +16.7] | 0/16 | – | differs |
| d2v3 | total cycles | -41.6% [-42.0, -41.2] | [-42.1, -41.1] | 16/16 | 0 | differs |
| d2v3 | p50 | -59.0% [-60.9, -57.0] | [-60.9, -57.0] | 16/16 | – | differs |
| d2v3 | p99 | -68.5% [-69.9, -67.1] | [-69.9, -67.1] | 16/16 | – | differs |
| base-A2 | instructions:u | +0.0% [-0.0, +0.0] | [-0.7, +0.7] | 7/16 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:u | +0.1% [-0.6, +0.7] | [-0.8, +1.0] | 7/16 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:k | +0.6% [-1.4, +2.5] | [-1.4, +2.5] | 6/16 | – | within the A/A spread (< 1%) |
| base-A2 | total cycles | +0.1% [-0.7, +1.0] | [-0.9, +1.2] | 7/16 | 0.71 | within the A/A spread (< 1%) |
| base-A2 | p50 | -1.3% [-9.6, +7.9] | [-9.6, +7.9] | 10/16 | – | not resolved |
| base-A2 | p99 | +0.9% [-6.3, +8.6] | [-6.3, +8.6] | 8/16 | – | within the A/A spread (< 1%) |
| d2v3 vs d1v4 | instructions:u | -73.5% [-73.5, -73.5] | [-73.6, -73.3] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | cycles:u | -45.2% [-45.7, -44.7] | [-45.8, -44.6] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | cycles:k | +10.1% [+8.4, +11.8] | [+8.4, +11.8] | 0/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | total cycles | -34.4% [-35.0, -33.8] | [-35.1, -33.7] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | p50 | -48.0% [-49.5, -46.5] | [-49.5, -46.5] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | p99 | -58.9% [-62.1, -55.5] | [-62.1, -55.5] | 16/16 | – | differs (exploratory) |

## rt-n200

128 legs recorded, 128 valid and current, 0 invalid; 16 rounds; Holm over 6 primary rows.

### n200-lo @ 2000 req/s

| Arm | valid | busy (of 4 workers) | instructions:u/req (k) | total cycles/req (k) | p50 (us) | p99 (us) |
|---|---|---|---|---|---|---|
| base | 16 | 9.7% | 143.0 | 370.5 | 250 | 406 |
| d1v4 | 16 | 9.4% | 118.7 | 357.1 | 247 | 397 |
| d2v3 | 16 | 8.8% | 77.2 | 323.8 | 232 | 366 |
| base-A2 | 16 | 9.6% | 143.0 | 369.5 | 249 | 394 |

| Arm vs base | Metric | Effect [95% CI] | Widened | Arm lower | Holm p | Verdict |
|---|---|---|---|---|---|---|
| d1v4 | instructions:u | -17.0% [-17.0, -17.0] | [-17.5, -16.4] | 16/16 | – | differs |
| d1v4 | cycles:u | -5.6% [-6.4, -4.8] | [-6.6, -4.6] | 16/16 | – | differs |
| d1v4 | cycles:k | +0.7% [-0.9, +2.3] | [-0.9, +2.4] | 5/16 | – | within the A/A spread (< 1%) |
| d1v4 | total cycles | -3.7% [-4.5, -2.8] | [-4.7, -2.7] | 16/16 | 4.6e-07 | differs |
| d1v4 | p50 | -1.9% [-2.7, -1.0] | [-2.9, -0.9] | 15/16 | – | differs |
| d1v4 | p99 | -1.7% [-3.2, -0.2] | [-3.3, -0.2] | 12/16 | – | differs |
| d2v3 | instructions:u | -46.0% [-46.0, -46.0] | [-46.4, -45.6] | 16/16 | – | differs |
| d2v3 | cycles:u | -17.9% [-18.5, -17.4] | [-18.6, -17.2] | 16/16 | – | differs |
| d2v3 | cycles:k | -0.5% [-2.0, +1.0] | [-2.0, +1.1] | 8/16 | – | within the A/A spread (< 1%) |
| d2v3 | total cycles | -12.6% [-13.2, -12.0] | [-13.4, -11.8] | 16/16 | 0 | differs |
| d2v3 | p50 | -7.2% [-8.0, -6.4] | [-8.2, -6.2] | 16/16 | – | differs |
| d2v3 | p99 | -9.1% [-10.2, -8.0] | [-10.3, -7.9] | 16/16 | – | differs |
| base-A2 | instructions:u | -0.0% [-0.0, +0.0] | [-0.7, +0.7] | 7/16 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:u | -0.1% [-0.7, +0.6] | [-1.0, +0.8] | 7/16 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:k | -0.5% [-2.1, +1.2] | [-2.1, +1.2] | 10/16 | – | within the A/A spread (< 1%) |
| base-A2 | total cycles | -0.2% [-1.0, +0.6] | [-1.2, +0.8] | 9/16 | 1 | within the A/A spread (< 1%) |
| base-A2 | p50 | -0.1% [-0.8, +0.6] | [-1.0, +0.8] | 10/16 | – | within the A/A spread (< 1%) |
| base-A2 | p99 | -0.9% [-2.1, +0.3] | [-2.2, +0.4] | 11/16 | – | within the A/A spread (< 1%) |
| d2v3 vs d1v4 | instructions:u | -35.0% [-35.0, -35.0] | [-35.4, -34.5] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | cycles:u | -13.0% [-13.7, -12.3] | [-13.9, -12.2] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | cycles:k | -1.2% [-2.4, +0.1] | [-2.5, +0.2] | 12/16 | – | not resolved (exploratory) |
| d2v3 vs d1v4 | total cycles | -9.2% [-9.9, -8.6] | [-10.1, -8.4] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | p50 | -5.4% [-5.9, -4.9] | [-6.2, -4.6] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | p99 | -7.5% [-8.7, -6.3] | [-8.7, -6.2] | 16/16 | – | differs (exploratory) |

### n200-hi @ 22000 req/s

| Arm | valid | busy (of 4 workers) | instructions:u/req (k) | total cycles/req (k) | p50 (us) | p99 (us) |
|---|---|---|---|---|---|---|
| base | 16 | 58.5% | 142.4 | 238.6 | 233 | 530 |
| d1v4 | 16 | 56.1% | 118.2 | 228.7 | 216 | 462 |
| d2v3 | 16 | 50.0% | 76.7 | 201.8 | 177 | 359 |
| base-A2 | 16 | 58.4% | 142.4 | 238.7 | 230 | 521 |

| Arm vs base | Metric | Effect [95% CI] | Widened | Arm lower | Holm p | Verdict |
|---|---|---|---|---|---|---|
| d1v4 | instructions:u | -17.0% [-17.0, -17.0] | [-17.5, -16.4] | 16/16 | – | differs |
| d1v4 | cycles:u | -6.5% [-7.2, -5.8] | [-7.4, -5.6] | 16/16 | – | differs |
| d1v4 | cycles:k | +1.6% [+0.8, +2.3] | [+0.6, +2.5] | 2/16 | – | differs |
| d1v4 | total cycles | -4.4% [-5.0, -3.7] | [-5.2, -3.5] | 16/16 | 1.7e-09 | differs |
| d1v4 | p50 | -7.3% [-9.1, -5.4] | [-9.1, -5.4] | 15/16 | – | differs |
| d1v4 | p99 | -10.6% [-16.8, -3.8] | [-16.8, -3.8] | 12/16 | – | differs |
| d2v3 | instructions:u | -46.1% [-46.1, -46.1] | [-46.5, -45.8] | 16/16 | – | differs |
| d2v3 | cycles:u | -22.2% [-22.7, -21.6] | [-22.9, -21.4] | 16/16 | – | differs |
| d2v3 | cycles:k | +3.7% [+3.0, +4.3] | [+2.7, +4.6] | 0/16 | – | differs |
| d2v3 | total cycles | -15.3% [-15.8, -14.8] | [-16.0, -14.6] | 16/16 | 0 | differs |
| d2v3 | p50 | -23.9% [-26.0, -21.7] | [-26.0, -21.7] | 16/16 | – | differs |
| d2v3 | p99 | -30.2% [-34.2, -26.0] | [-34.2, -26.0] | 16/16 | – | differs |
| base-A2 | instructions:u | +0.0% [-0.0, +0.0] | [-0.7, +0.7] | 8/16 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:u | -0.3% [-1.1, +0.5] | [-1.3, +0.7] | 9/16 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:k | +0.1% [-1.0, +1.3] | [-1.1, +1.4] | 10/16 | – | within the A/A spread (< 1%) |
| base-A2 | total cycles | -0.2% [-1.0, +0.6] | [-1.2, +0.8] | 8/16 | 1 | within the A/A spread (< 1%) |
| base-A2 | p50 | -1.4% [-2.9, +0.1] | [-2.9, +0.2] | 10/16 | – | not resolved |
| base-A2 | p99 | +1.1% [-5.6, +8.2] | [-5.6, +8.2] | 8/16 | – | not resolved |
| d2v3 vs d1v4 | instructions:u | -35.1% [-35.1, -35.1] | [-35.5, -34.6] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | cycles:u | -16.7% [-17.4, -16.1] | [-17.5, -15.9] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | cycles:k | +2.1% [+1.6, +2.5] | [+1.3, +2.9] | 0/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | total cycles | -11.4% [-11.9, -10.9] | [-12.2, -10.7] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | p50 | -17.9% [-20.0, -15.7] | [-20.0, -15.7] | 16/16 | – | differs (exploratory) |
| d2v3 vs d1v4 | p99 | -22.0% [-26.6, -17.1] | [-26.6, -17.1] | 16/16 | – | differs (exploratory) |

## hdr

144 legs recorded, 144 valid and current, 0 invalid; 24 rounds; Holm over 4 primary rows.

### fh109-lo @ 2000 req/s

| Arm | valid | busy (of 4 workers) | instructions:u/req (k) | total cycles/req (k) | p50 (us) | p99 (us) |
|---|---|---|---|---|---|---|
| base | 24 | 9.7% | 166.3 | 369.3 | 304 | 453 |
| s1 | 24 | 9.4% | 133.4 | 356.8 | 296 | 440 |
| base-A2 | 24 | 9.7% | 166.3 | 367.2 | 303 | 452 |

| Arm vs base | Metric | Effect [95% CI] | Widened | Arm lower | Holm p | Verdict |
|---|---|---|---|---|---|---|
| s1 | instructions:u | -19.8% [-19.8, -19.8] | [-20.3, -19.3] | 24/24 | – | differs |
| s1 | cycles:u | -4.8% [-5.4, -4.1] | [-5.6, -3.9] | 24/24 | – | differs |
| s1 | cycles:k | -0.7% [-2.6, +1.2] | [-2.6, +1.3] | 13/24 | – | within the A/A spread (< 1%) |
| s1 | total cycles | -3.4% [-4.4, -2.5] | [-4.5, -2.3] | 23/24 | 3.3e-07 | differs |
| s1 | p50 | -2.1% [-2.7, -1.5] | [-3.0, -1.2] | 24/24 | – | differs |
| s1 | p99 | -2.7% [-3.5, -1.8] | [-3.7, -1.6] | 22/24 | – | differs |
| base-A2 | instructions:u | +0.0% [-0.0, +0.0] | [-0.7, +0.7] | 10/24 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:u | -0.2% [-0.7, +0.4] | [-1.0, +0.7] | 14/24 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:k | -0.5% [-2.4, +1.5] | [-2.4, +1.5] | 14/24 | – | within the A/A spread (< 1%) |
| base-A2 | total cycles | -0.2% [-1.1, +0.6] | [-1.3, +0.8] | 14/24 | 1 | within the A/A spread (< 1%) |
| base-A2 | p50 | -0.1% [-0.8, +0.5] | [-1.0, +0.8] | 16/24 | – | within the A/A spread (< 1%) |
| base-A2 | p99 | -0.3% [-1.2, +0.7] | [-1.4, +0.8] | 16/24 | – | within the A/A spread (< 1%) |

### fh109-hi @ 20000 req/s

| Arm | valid | busy (of 4 workers) | instructions:u/req (k) | total cycles/req (k) | p50 (us) | p99 (us) |
|---|---|---|---|---|---|---|
| base | 24 | 55.5% | 165.8 | 249.2 | 278 | 532 |
| s1 | 24 | 53.4% | 132.9 | 239.8 | 265 | 506 |
| base-A2 | 24 | 55.4% | 165.8 | 248.3 | 279 | 538 |

| Arm vs base | Metric | Effect [95% CI] | Widened | Arm lower | Holm p | Verdict |
|---|---|---|---|---|---|---|
| s1 | instructions:u | -19.8% [-19.9, -19.8] | [-20.4, -19.3] | 24/24 | – | differs |
| s1 | cycles:u | -6.0% [-6.7, -5.4] | [-6.9, -5.2] | 24/24 | – | differs |
| s1 | cycles:k | +0.9% [+0.1, +1.7] | [-0.1, +1.9] | 9/24 | – | within the A/A spread (< 1%) |
| s1 | total cycles | -4.0% [-4.7, -3.4] | [-4.9, -3.2] | 23/24 | 2.3e-11 | differs |
| s1 | p50 | -4.5% [-6.1, -3.0] | [-6.1, -2.9] | 21/24 | – | differs |
| s1 | p99 | -6.3% [-11.4, -1.0] | [-11.4, -1.0] | 17/24 | – | differs |
| base-A2 | instructions:u | -0.0% [-0.0, +0.0] | [-0.7, +0.7] | 13/24 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:u | -0.2% [-0.8, +0.4] | [-1.1, +0.7] | 16/24 | – | within the A/A spread (< 1%) |
| base-A2 | cycles:k | -0.1% [-0.9, +0.6] | [-1.1, +0.8] | 13/24 | – | within the A/A spread (< 1%) |
| base-A2 | total cycles | -0.2% [-0.7, +0.4] | [-1.0, +0.7] | 15/24 | 1 | within the A/A spread (< 1%) |
| base-A2 | p50 | -0.2% [-2.0, +1.7] | [-2.0, +1.7] | 13/24 | – | within the A/A spread (< 1%) |
| base-A2 | p99 | -1.0% [-6.5, +4.9] | [-6.5, +4.9] | 13/24 | – | within the A/A spread (< 1%) |

## rt-n1

72 legs recorded, 72 valid and current, 0 invalid; 12 rounds; Holm over 4 primary rows.

### n1-lo @ 2000 req/s

| Arm | valid | busy (of 4 workers) | instructions:u/req (k) | total cycles/req (k) | p50 (us) | p99 (us) |
|---|---|---|---|---|---|---|
| base | 12 | 8.7% | 76.3 | 324.7 | 233 | 361 |
| d1v4 | 12 | 8.7% | 76.3 | 321.6 | 231 | 365 |
| d2v3 | 12 | 8.7% | 76.4 | 322.3 | 230 | 356 |

| Arm vs base | Metric | Effect [95% CI] | Widened | Arm lower | Holm p | Verdict |
|---|---|---|---|---|---|---|
| d1v4 | instructions:u | +0.0% [+0.0, +0.0] | [-0.6, +0.7] | 0/12 | – | within the A/A spread (< 1%) |
| d1v4 | cycles:u | -1.6% [-2.4, -0.7] | [-2.6, -0.5] | 10/12 | – | differs |
| d1v4 | cycles:k | -0.5% [-2.2, +1.2] | [-2.2, +1.2] | 5/12 | – | within the A/A spread (< 1%) |
| d1v4 | total cycles | -1.2% [-2.2, -0.2] | [-2.3, -0.1] | 9/12 | 0.089 | not resolved after Holm |
| d1v4 | p50 | -0.5% [-1.3, +0.3] | [-1.5, +0.5] | 8/12 | – | within the A/A spread (< 1%) |
| d1v4 | p99 | +0.9% [-0.5, +2.4] | [-0.5, +2.4] | 5/12 | – | within the A/A spread (< 1%) |
| d2v3 | instructions:u | +0.0% [+0.0, +0.0] | [-0.6, +0.7] | 0/12 | – | within the A/A spread (< 1%) |
| d2v3 | cycles:u | -1.2% [-1.7, -0.6] | [-2.0, -0.3] | 11/12 | – | differs |
| d2v3 | cycles:k | +0.2% [-2.0, +2.5] | [-2.0, +2.5] | 4/12 | – | within the A/A spread (< 1%) |
| d2v3 | total cycles | -0.7% [-1.6, +0.3] | [-1.8, +0.4] | 10/12 | 0.32 | within the A/A spread (< 1%) |
| d2v3 | p50 | -0.8% [-1.7, +0.1] | [-1.8, +0.3] | 8/12 | – | within the A/A spread (< 1%) |
| d2v3 | p99 | -0.7% [-2.5, +1.1] | [-2.5, +1.1] | 10/12 | – | within the A/A spread (< 1%) |
| d2v3 vs d1v4 | instructions:u | +0.0% [+0.0, +0.0] | [-0.6, +0.7] | 0/12 | – | within the A/A spread (< 1%) (exploratory) |
| d2v3 vs d1v4 | cycles:u | +0.4% [-0.4, +1.2] | [-0.5, +1.4] | 5/12 | – | within the A/A spread (< 1%) (exploratory) |
| d2v3 vs d1v4 | cycles:k | +0.7% [-0.8, +2.2] | [-0.8, +2.2] | 5/12 | – | within the A/A spread (< 1%) (exploratory) |
| d2v3 vs d1v4 | total cycles | +0.5% [-0.3, +1.3] | [-0.4, +1.5] | 5/12 | – | within the A/A spread (< 1%) (exploratory) |
| d2v3 vs d1v4 | p50 | -0.3% [-1.2, +0.7] | [-1.4, +0.8] | 7/12 | – | within the A/A spread (< 1%) (exploratory) |
| d2v3 vs d1v4 | p99 | -1.6% [-3.4, +0.2] | [-3.4, +0.2] | 9/12 | – | not resolved (exploratory) |

### n1-hi @ 22000 req/s

| Arm | valid | busy (of 4 workers) | instructions:u/req (k) | total cycles/req (k) | p50 (us) | p99 (us) |
|---|---|---|---|---|---|---|
| base | 12 | 49.7% | 75.9 | 201.0 | 176 | 361 |
| d1v4 | 12 | 50.1% | 75.9 | 202.1 | 173 | 357 |
| d2v3 | 12 | 49.3% | 75.9 | 199.5 | 170 | 352 |

| Arm vs base | Metric | Effect [95% CI] | Widened | Arm lower | Holm p | Verdict |
|---|---|---|---|---|---|---|
| d1v4 | instructions:u | +0.0% [-0.0, +0.1] | [-0.6, +0.7] | 4/12 | – | within the A/A spread (< 1%) |
| d1v4 | cycles:u | +0.5% [-0.9, +1.9] | [-0.9, +1.9] | 5/12 | – | within the A/A spread (< 1%) |
| d1v4 | cycles:k | +1.0% [-0.1, +2.1] | [-0.2, +2.2] | 2/12 | – | within the A/A spread (< 1%) |
| d1v4 | total cycles | +0.7% [-0.5, +1.8] | [-0.6, +1.9] | 4/12 | 0.32 | within the A/A spread (< 1%) |
| d1v4 | p50 | -0.9% [-5.6, +4.2] | [-5.6, +4.2] | 6/12 | – | within the A/A spread (< 1%) |
| d1v4 | p99 | -2.5% [-6.3, +1.5] | [-6.3, +1.5] | 7/12 | – | not resolved |
| d2v3 | instructions:u | +0.1% [+0.0, +0.1] | [-0.6, +0.7] | 2/12 | – | within the A/A spread (< 1%) |
| d2v3 | cycles:u | -1.2% [-2.3, -0.1] | [-2.4, -0.1] | 9/12 | – | differs |
| d2v3 | cycles:k | -0.1% [-1.4, +1.2] | [-1.4, +1.3] | 6/12 | – | within the A/A spread (< 1%) |
| d2v3 | total cycles | -0.9% [-1.9, +0.2] | [-2.0, +0.3] | 8/12 | 0.32 | within the A/A spread (< 1%) |
| d2v3 | p50 | -2.6% [-6.7, +1.7] | [-6.7, +1.7] | 7/12 | – | not resolved |
| d2v3 | p99 | -2.3% [-7.1, +2.8] | [-7.1, +2.8] | 8/12 | – | not resolved |
| d2v3 vs d1v4 | instructions:u | +0.0% [-0.0, +0.1] | [-0.6, +0.7] | 3/12 | – | within the A/A spread (< 1%) (exploratory) |
| d2v3 vs d1v4 | cycles:u | -1.7% [-2.8, -0.6] | [-2.9, -0.5] | 9/12 | – | differs (exploratory) |
| d2v3 vs d1v4 | cycles:k | -1.1% [-1.8, -0.3] | [-2.0, -0.1] | 11/12 | – | differs (exploratory) |
| d2v3 vs d1v4 | total cycles | -1.5% [-2.4, -0.6] | [-2.6, -0.4] | 11/12 | – | differs (exploratory) |
| d2v3 vs d1v4 | p50 | -1.7% [-5.0, +1.6] | [-5.0, +1.6] | 8/12 | – | not resolved (exploratory) |
| d2v3 vs d1v4 | p99 | +0.2% [-4.2, +4.8] | [-4.2, +4.8] | 4/12 | – | within the A/A spread (< 1%) (exploratory) |

