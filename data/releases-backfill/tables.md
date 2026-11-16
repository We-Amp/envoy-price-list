Release run: 392 legs recorded, 392 valid and current, 0 invalid; 14 rounds; primary family 24 rows (Holm).

### A/A of the session (v1.40.2-A2 against v1.40.2)

| Shape @ rps | Metric | Effect [95% CI] | Half-width | Widened half-width | Holm p (run) | Pairs |
|---|---|---|---|---|---|---|
| s @ 5200 | instructions_u | -0.00% [-0.04, +0.03] | 0.04 | 0.67 | – | 14 |
| s @ 5200 | cycles_total | +0.20% [-0.32, +0.72] | 0.52 | 0.82 | 1.000 | 14 |
| s @ 5200 | p50_us | +0.07% [-1.95, +2.13] | 2.04 | 2.04 | – | 14 |
| s @ 5200 | p99_us | -0.04% [-1.64, +1.58] | 1.61 | 1.61 | – | 14 |
| fh @ 8000 | instructions_u | +0.01% [-0.00, +0.01] | 0.01 | 0.67 | – | 14 |
| fh @ 8000 | cycles_total | -0.44% [-1.59, +0.71] | 1.16 | 1.24 | 1.000 | 14 |
| fh @ 8000 | p50_us | -0.31% [-1.21, +0.60] | 0.90 | 1.06 | – | 14 |
| fh @ 8000 | p99_us | -0.20% [-1.05, +0.67] | 0.86 | 1.03 | – | 14 |
| s-hi @ 12000 | instructions_u | -0.01% [-0.11, +0.08] | 0.09 | 0.67 | – | 14 |
| s-hi @ 12000 | cycles_total | +0.58% [-0.48, +1.66] | 1.06 | 1.17 | 1.000 | 14 |
| s-hi @ 12000 | p50_us | +1.17% [-5.03, +7.77] | 6.33 | 6.33 | – | 14 |
| s-hi @ 12000 | p99_us | +3.93% [-10.79, +21.08] | 15.27 | 15.27 | – | 14 |
| fh-hi @ 18400 | instructions_u | -0.01% [-0.02, +0.01] | 0.01 | 0.67 | – | 14 |
| fh-hi @ 18400 | cycles_total | +0.13% [-0.65, +0.91] | 0.78 | 0.97 | 1.000 | 14 |
| fh-hi @ 18400 | p50_us | +1.80% [-0.62, +4.28] | 2.41 | 2.41 | – | 14 |
| fh-hi @ 18400 | p99_us | -1.47% [-7.42, +4.86] | 6.23 | 6.23 | – | 14 |

### Total cycles per request: v1.40.2 against each release (primary)

Negative = v1.40.2 is cheaper. Holm p from the run (24 rows). "Widened" = the interval with the between-session A/A spread added. Medians in k cycles per request.

| Shape @ rps | v1.40.2 vs | Effect [95% CI] | Widened | Holm p | v1.40.2 lower in | Median release → v1.40.2 | Verdict |
|---|---|---|---|---|---|---|---|
| s @ 5200 | v1.32.13 | +1.05% [+0.07, +2.04] | [-0.06, +2.17] | 0.261 | 3/14 | 518.9k → 526.5k | not resolved after Holm (about +1.0%) |
| s @ 5200 | v1.34.14 | +2.38% [+1.73, +3.03] | [+1.48, +3.28] | 3.84e-05 | 0/14 | 514.1k → 526.5k | differs |
| s @ 5200 | v1.36.13 | +2.00% [+1.27, +2.73] | [+1.05, +2.95] | 0.000596 | 1/14 | 515.0k → 526.5k | differs |
| s @ 5200 | v1.37.11 | +1.21% [+0.37, +2.07] | [+0.19, +2.24] | 0.0797 | 4/14 | 519.5k → 526.5k | not resolved after Holm (about +1.2%) |
| s @ 5200 | v1.38.9 | +0.15% [-0.42, +0.73] | [-0.69, +1.00] | 1 | 6/14 | 524.7k → 526.5k | within the A/A spread (< 1%) |
| fh @ 8000 | v1.32.13 | -7.19% [-8.17, -6.20] | [-8.27, -6.09] | 2.87e-08 | 14/14 | 302.8k → 282.0k | differs |
| fh @ 8000 | v1.34.14 | -3.40% [-4.46, -2.32] | [-4.55, -2.23] | 0.000204 | 14/14 | 291.8k → 282.0k | differs |
| fh @ 8000 | v1.36.13 | -3.41% [-4.38, -2.44] | [-4.50, -2.32] | 7.44e-05 | 14/14 | 291.1k → 282.0k | differs |
| fh @ 8000 | v1.37.11 | -2.66% [-3.31, -2.00] | [-3.53, -1.78] | 1.71e-05 | 14/14 | 289.7k → 282.0k | differs |
| fh @ 8000 | v1.38.9 | -4.16% [-4.83, -3.50] | [-5.04, -3.28] | 1.29e-07 | 14/14 | 294.6k → 282.0k | differs |
| s-hi @ 12000 | v1.32.13 | +1.31% [+0.45, +2.17] | [+0.28, +2.35] | 0.0648 | 3/14 | 448.3k → 454.8k | not resolved after Holm (about +1.3%) |
| s-hi @ 12000 | v1.34.14 | +2.04% [+1.23, +2.85] | [+1.04, +3.04] | 0.00124 | 2/14 | 445.0k → 454.8k | differs |
| s-hi @ 12000 | v1.36.13 | +1.44% [+0.44, +2.44] | [+0.31, +2.57] | 0.0797 | 2/14 | 448.3k → 454.8k | not resolved after Holm (about +1.4%) |
| s-hi @ 12000 | v1.37.11 | +0.78% [+0.06, +1.51] | [-0.16, +1.72] | 0.261 | 5/14 | 451.5k → 454.8k | within the A/A spread (< 1%) |
| s-hi @ 12000 | v1.38.9 | -0.68% [-1.30, -0.07] | [-1.55, +0.19] | 0.261 | 10/14 | 457.6k → 454.8k | within the A/A spread (< 1%) |
| fh-hi @ 18400 | v1.32.13 | -7.83% [-8.57, -7.07] | [-8.74, -6.90] | 3.51e-10 | 14/14 | 268.8k → 249.1k | differs |
| fh-hi @ 18400 | v1.34.14 | -3.65% [-4.22, -3.08] | [-4.47, -2.82] | 9.81e-08 | 14/14 | 257.5k → 249.1k | differs |
| fh-hi @ 18400 | v1.36.13 | -3.40% [-4.48, -2.30] | [-4.57, -2.21] | 0.00023 | 14/14 | 256.4k → 249.1k | differs |
| fh-hi @ 18400 | v1.37.11 | -2.57% [-3.25, -1.88] | [-3.46, -1.67] | 3.84e-05 | 14/14 | 255.0k → 249.1k | differs |
| fh-hi @ 18400 | v1.38.9 | -4.52% [-5.50, -3.53] | [-5.61, -3.42] | 5.14e-06 | 14/14 | 259.5k → 249.1k | differs |

### Release-to-release steps, total cycles (exploratory, same paired rounds)

| Shape @ rps | Step | Effect [95% CI] | Widened | Pairs lower | Reading |
|---|---|---|---|---|---|
| s @ 5200 | v1.32.13 → v1.34.14 | -1.30% [-2.05, -0.55] | [-2.24, -0.35] | 11/14 | differs |
| s @ 5200 | v1.34.14 → v1.36.13 | +0.37% [-0.12, +0.87] | [-0.43, +1.18] | 4/14 | within the A/A spread (< 1%) |
| s @ 5200 | v1.36.13 → v1.37.11 | +0.78% [+0.13, +1.43] | [-0.11, +1.67] | 4/14 | within the A/A spread (< 1%) |
| s @ 5200 | v1.37.11 → v1.38.9 | +1.06% [+0.26, +1.85] | [+0.07, +2.05] | 3/14 | differs |
| s @ 5200 | v1.38.9 → v1.40.2 | +0.15% [-0.42, +0.73] | [-0.69, +1.00] | 6/14 | within the A/A spread (< 1%) |
| fh @ 8000 | v1.32.13 → v1.34.14 | -3.93% [-4.73, -3.11] | [-4.89, -2.95] | 14/14 | differs |
| fh @ 8000 | v1.34.14 → v1.36.13 | +0.02% [-1.02, +1.07] | [-1.13, +1.18] | 7/14 | within the A/A spread (< 1%) |
| fh @ 8000 | v1.36.13 → v1.37.11 | -0.78% [-1.81, +0.27] | [-1.92, +0.38] | 10/14 | within the A/A spread (< 1%) |
| fh @ 8000 | v1.37.11 → v1.38.9 | +1.57% [+0.54, +2.62] | [+0.42, +2.74] | 2/14 | differs |
| fh @ 8000 | v1.38.9 → v1.40.2 | -4.16% [-4.83, -3.50] | [-5.04, -3.28] | 14/14 | differs |
| s-hi @ 12000 | v1.32.13 → v1.34.14 | -0.72% [-1.48, +0.06] | [-1.67, +0.25] | 11/14 | within the A/A spread (< 1%) |
| s-hi @ 12000 | v1.34.14 → v1.36.13 | +0.59% [-0.37, +1.56] | [-0.51, +1.70] | 5/14 | within the A/A spread (< 1%) |
| s-hi @ 12000 | v1.36.13 → v1.37.11 | +0.65% [-0.07, +1.38] | [-0.28, +1.60] | 4/14 | within the A/A spread (< 1%) |
| s-hi @ 12000 | v1.37.11 → v1.38.9 | +1.47% [+1.02, +1.93] | [+0.68, +2.27] | 0/14 | differs |
| s-hi @ 12000 | v1.38.9 → v1.40.2 | -0.68% [-1.30, -0.07] | [-1.55, +0.19] | 10/14 | within the A/A spread (< 1%) |
| fh-hi @ 18400 | v1.32.13 → v1.34.14 | -4.33% [-4.91, -3.75] | [-5.16, -3.50] | 14/14 | differs |
| fh-hi @ 18400 | v1.34.14 → v1.36.13 | -0.26% [-1.21, +0.69] | [-1.34, +0.83] | 10/14 | within the A/A spread (< 1%) |
| fh-hi @ 18400 | v1.36.13 → v1.37.11 | -0.85% [-1.73, +0.03] | [-1.88, +0.19] | 10/14 | within the A/A spread (< 1%) |
| fh-hi @ 18400 | v1.37.11 → v1.38.9 | +2.05% [+1.44, +2.66] | [+1.18, +2.93] | 0/14 | differs |
| fh-hi @ 18400 | v1.38.9 → v1.40.2 | -4.52% [-5.50, -3.53] | [-5.61, -3.42] | 14/14 | differs |

### Exploratory: v1.40.2 against each release, other metrics (interval only)

| Shape | v1.40.2 vs | instructions:u | cycles:u | cycles:k | p50 | p99 |
|---|---|---|---|---|---|---|
| s | v1.32.13 | -12.17% [-12.21, -12.13] | +1.65% [+0.82, +2.49] | -0.08% [-1.38, +1.23] | +0.91% [-0.77, +2.62] | +1.34% [-0.20, +2.91] |
| s | v1.34.14 | -5.61% [-5.64, -5.58] | +3.39% [+2.86, +3.93] | +0.49% [-0.43, +1.43] | +1.85% [+0.46, +3.25] | +2.00% [+0.77, +3.23] |
| s | v1.36.13 | -2.81% [-2.85, -2.77] | +2.94% [+2.42, +3.46] | +0.25% [-0.92, +1.43] | +1.89% [+0.45, +3.35] | +1.52% [-0.11, +3.18] |
| s | v1.37.11 | -2.78% [-2.81, -2.75] | +1.83% [+1.18, +2.49] | +0.05% [-1.23, +1.35] | +2.05% [+0.21, +3.92] | +1.51% [-0.20, +3.25] |
| s | v1.38.9 | -6.44% [-6.48, -6.40] | +0.16% [-0.38, +0.72] | +0.14% [-0.54, +0.82] | +0.85% [-0.17, +1.87] | -0.13% [-1.79, +1.55] |
| fh | v1.32.13 | -28.70% [-28.71, -28.69] | -10.15% [-11.10, -9.19] | +0.76% [-0.40, +1.94] | -5.58% [-6.71, -4.44] | -6.07% [-6.98, -5.15] |
| fh | v1.34.14 | -14.57% [-14.58, -14.56] | -5.00% [-6.10, -3.89] | +0.68% [-0.59, +1.97] | -2.72% [-3.75, -1.68] | -3.44% [-4.49, -2.38] |
| fh | v1.36.13 | -13.14% [-13.14, -13.13] | -4.60% [-5.48, -3.71] | -0.46% [-1.78, +0.88] | -2.61% [-3.54, -1.68] | -2.61% [-3.64, -1.57] |
| fh | v1.37.11 | -13.07% [-13.07, -13.06] | -3.72% [-4.38, -3.05] | -0.01% [-0.82, +0.80] | -2.03% [-2.90, -1.16] | -2.56% [-3.45, -1.66] |
| fh | v1.38.9 | -18.68% [-18.69, -18.68] | -5.83% [-6.48, -5.16] | +0.06% [-0.75, +0.88] | -2.97% [-3.85, -2.07] | -3.31% [-4.13, -2.49] |
| s-hi | v1.32.13 | -12.33% [-12.38, -12.27] | +2.31% [+1.58, +3.04] | -0.64% [-1.92, +0.65] | +6.77% [+3.02, +10.65] | +14.71% [+0.17, +31.37] |
| s-hi | v1.34.14 | -5.76% [-5.82, -5.69] | +3.51% [+2.79, +4.23] | -0.78% [-1.94, +0.39] | +5.60% [+1.65, +9.71] | +9.71% [-5.03, +26.74] |
| s-hi | v1.36.13 | -2.90% [-2.97, -2.84] | +2.83% [+1.80, +3.88] | -1.25% [-2.40, -0.08] | +5.88% [+1.77, +10.16] | +9.22% [-4.30, +24.65] |
| s-hi | v1.37.11 | -2.89% [-2.94, -2.84] | +1.63% [+0.98, +2.28] | -0.88% [-1.97, +0.21] | +5.41% [+2.11, +8.82] | +7.84% [-0.79, +17.22] |
| s-hi | v1.38.9 | -6.56% [-6.61, -6.51] | -0.45% [-0.98, +0.09] | -1.15% [-2.12, -0.18] | +2.43% [-1.38, +6.39] | +6.84% [-3.99, +18.88] |
| fh-hi | v1.32.13 | -28.74% [-28.75, -28.73] | -10.89% [-11.64, -10.14] | +1.19% [+0.25, +2.14] | -11.85% [-13.51, -10.15] | -14.89% [-18.73, -10.88] |
| fh-hi | v1.34.14 | -14.59% [-14.60, -14.58] | -5.37% [-5.99, -4.76] | +1.12% [+0.52, +1.71] | -6.73% [-8.96, -4.45] | -7.33% [-13.18, -1.09] |
| fh-hi | v1.36.13 | -13.16% [-13.17, -13.15] | -4.78% [-5.89, -3.65] | +0.38% [-0.79, +1.56] | -5.94% [-7.95, -3.89] | -4.96% [-10.37, +0.77] |
| fh-hi | v1.37.11 | -13.10% [-13.11, -13.08] | -3.70% [-4.46, -2.93] | +0.48% [-0.31, +1.28] | -5.07% [-7.14, -2.95] | -4.38% [-10.11, +1.72] |
| fh-hi | v1.38.9 | -18.72% [-18.73, -18.71] | -6.24% [-7.27, -5.20] | +0.23% [-0.71, +1.19] | -6.74% [-8.85, -4.59] | -4.95% [-10.30, +0.72] |

### Medians per release (valid legs)

| Shape @ rps | Release | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req (CV) | IPC:u | p50 µs | p99 µs | Envoy busy |
|---|---|---|---|---|---|---|---|---|---|
| s @ 5200 | v1.32.13 | 186.6k | 338.4k | 180.3k | 518.9k (1.2%) | 0.55 | 397 | 615 | 30.9% |
| s @ 5200 | v1.34.14 | 173.6k | 333.7k | 180.3k | 514.1k (0.7%) | 0.52 | 392 | 615 | 30.6% |
| s @ 5200 | v1.36.13 | 168.6k | 335.3k | 180.0k | 515.0k (0.8%) | 0.50 | 392 | 619 | 30.7% |
| s @ 5200 | v1.37.11 | 168.6k | 338.7k | 180.9k | 519.5k (0.9%) | 0.50 | 393 | 621 | 30.9% |
| s @ 5200 | v1.38.9 | 175.1k | 344.5k | 180.3k | 524.7k (0.8%) | 0.51 | 394 | 628 | 31.2% |
| s @ 5200 | v1.40.2 | 163.9k | 344.6k | 181.6k | 526.5k (0.8%) | 0.48 | 400 | 623 | 31.2% |
| s @ 5200 | v1.40.2-A2 | 163.9k | 345.1k | 181.5k | 526.4k (0.5%) | 0.47 | 399 | 628 | 31.3% |
| fh @ 8000 | v1.32.13 | 231.1k | 220.5k | 82.4k | 302.8k (1.1%) | 1.05 | 229 | 393 | 27.4% |
| fh @ 8000 | v1.34.14 | 192.8k | 209.1k | 82.4k | 291.8k (1.2%) | 0.92 | 222 | 380 | 26.4% |
| fh @ 8000 | v1.36.13 | 189.7k | 207.9k | 82.9k | 291.1k (1.2%) | 0.91 | 221 | 379 | 26.4% |
| fh @ 8000 | v1.37.11 | 189.5k | 206.6k | 82.9k | 289.7k (1.1%) | 0.92 | 221 | 377 | 26.2% |
| fh @ 8000 | v1.38.9 | 202.6k | 211.4k | 83.0k | 294.6k (1.3%) | 0.96 | 222 | 381 | 26.6% |
| fh @ 8000 | v1.40.2 | 164.8k | 198.6k | 83.0k | 282.0k (1.1%) | 0.83 | 216 | 370 | 25.6% |
| fh @ 8000 | v1.40.2-A2 | 164.8k | 197.2k | 82.5k | 280.1k (1.2%) | 0.84 | 215 | 370 | 25.4% |
| s-hi @ 12000 | v1.32.13 | 185.9k | 296.5k | 152.6k | 448.3k (1.0%) | 0.63 | 410 | 888 | 60.1% |
| s-hi @ 12000 | v1.34.14 | 173.0k | 292.9k | 152.8k | 445.0k (1.0%) | 0.59 | 418 | 918 | 59.6% |
| s-hi @ 12000 | v1.36.13 | 167.9k | 294.6k | 153.7k | 448.3k (1.2%) | 0.57 | 414 | 929 | 59.9% |
| s-hi @ 12000 | v1.37.11 | 167.8k | 298.3k | 153.3k | 451.5k (0.5%) | 0.56 | 413 | 951 | 60.3% |
| s-hi @ 12000 | v1.38.9 | 174.4k | 304.2k | 153.5k | 457.6k (0.5%) | 0.57 | 430 | 999 | 61.2% |
| s-hi @ 12000 | v1.40.2 | 163.0k | 303.1k | 152.3k | 454.8k (1.1%) | 0.54 | 432 | 1026 | 60.7% |
| s-hi @ 12000 | v1.40.2-A2 | 163.0k | 304.7k | 152.4k | 457.1k (1.1%) | 0.54 | 436 | 1082 | 61.0% |
| fh-hi @ 18400 | v1.32.13 | 230.9k | 200.7k | 68.1k | 268.8k (0.8%) | 1.15 | 277 | 573 | 55.1% |
| fh-hi @ 18400 | v1.34.14 | 192.6k | 189.2k | 68.4k | 257.5k (0.6%) | 1.02 | 264 | 525 | 52.9% |
| fh-hi @ 18400 | v1.36.13 | 189.5k | 187.3k | 68.9k | 256.4k (1.6%) | 1.01 | 261 | 505 | 52.7% |
| fh-hi @ 18400 | v1.37.11 | 189.3k | 186.2k | 68.8k | 255.0k (0.6%) | 1.02 | 257 | 514 | 52.3% |
| fh-hi @ 18400 | v1.38.9 | 202.4k | 190.6k | 68.8k | 259.5k (1.2%) | 1.06 | 261 | 503 | 53.4% |
| fh-hi @ 18400 | v1.40.2 | 164.5k | 179.7k | 69.5k | 249.1k (0.9%) | 0.92 | 246 | 493 | 51.0% |
| fh-hi @ 18400 | v1.40.2-A2 | 164.5k | 179.9k | 69.4k | 248.9k (1.0%) | 0.91 | 248 | 474 | 51.1% |

### Filter rows: total cycles per request against the baseline (primary)

Holm across the 6 primary rows of the two rows. "A/A reach" = far end of the release run's A/A interval for the shape (same session, same baseline). Δ = difference of medians.

| Row | Arm vs base | Shape @ rps | Total cycles/req [95% CI] | Widened | Holm p | A/A reach | Δ cycles/req | instructions:u | p50 | p99 | Base busy → arm busy | Pairs higher | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| wk4-jwt-authn | jwt vs jwt-off | s @ 5200 | +32.07% [+31.51, +32.63] | [+31.06, +33.08] | 0 | 0.72 | +173.7k | +146.16% [+146.08, +146.24] | +37.81% [+34.02, +41.72] | +150.85% [+107.37, +203.46] | 31.9% → 41.2% | 12/12 | differs |
| wk4-jwt-authn | jwt-cache vs jwt-off | s @ 5200 | +4.29% [+3.91, +4.67] | [+3.52, +5.06] | 1.73e-10 | 0.72 | +23.6k | +4.76% [+4.73, +4.79] | +4.23% [+2.36, +6.14] | +9.04% [+3.75, +14.59] | 31.9% → 33.1% | 12/12 | differs |
| wk4-jwt-authn | jwt vs jwt-off | fh @ 8000 | +60.30% [+58.06, +62.57] | [+58.04, +62.59] | 2.22e-15 | 1.60 | +174.7k | +148.91% [+148.89, +148.93] | +75.45% [+69.73, +81.37] | +151.05% [+123.24, +182.32] | 26.2% → 41.1% | 12/12 | differs |
| wk4-jwt-authn | jwt-cache vs jwt-off | fh @ 8000 | +9.21% [+7.79, +10.65] | [+7.75, +10.69] | 3.97e-08 | 1.60 | +25.1k | +4.86% [+4.86, +4.87] | +6.85% [+5.74, +7.97] | +7.11% [+6.09, +8.14] | 26.2% → 28.4% | 12/12 | differs |
| wk4-local-ratelimit | ratelimit-on vs ratelimit-off | s @ 5200 | +1.93% [+1.25, +2.62] | [+1.02, +2.85] | 5.97e-05 | 0.72 | +9.7k | +2.30% [+2.28, +2.32] | +0.57% [-1.47, +2.66] | +2.71% [+0.27, +5.21] | 31.2% → 31.8% | 11/12 | differs |
| wk4-local-ratelimit | ratelimit-on vs ratelimit-off | fh @ 8000 | +3.97% [+3.00, +4.95] | [+2.87, +5.09] | 3.59e-06 | 1.60 | +10.6k | +2.18% [+2.18, +2.19] | +2.93% [+1.96, +3.91] | +4.22% [+3.05, +5.40] | 25.5% → 26.4% | 12/12 | differs |

### Filter rows: what the setting did (counter deltas per request in the window, mean over valid legs)

| Row | Arm | Shape | Counter | Per request |
|---|---|---|---|---|
| wk4-jwt-authn | jwt | fh | `http.ingress_http.jwt_authn.allowed` | 1.0000 |
| wk4-jwt-authn | jwt | fh | `http.ingress_http.jwt_authn.denied` | 0.0000 |
| wk4-jwt-authn | jwt | fh | `http.ingress_http.jwt_authn.jwt_cache_hit` | 0.0000 |
| wk4-jwt-authn | jwt | fh | `http.ingress_http.jwt_authn.jwt_cache_miss` | 1.0000 |
| wk4-jwt-authn | jwt-cache | fh | `http.ingress_http.jwt_authn.allowed` | 1.0000 |
| wk4-jwt-authn | jwt-cache | fh | `http.ingress_http.jwt_authn.denied` | 0.0000 |
| wk4-jwt-authn | jwt-cache | fh | `http.ingress_http.jwt_authn.jwt_cache_hit` | 1.0000 |
| wk4-jwt-authn | jwt-cache | fh | `http.ingress_http.jwt_authn.jwt_cache_miss` | 0.0000 |
| wk4-jwt-authn | jwt-off | fh | `http.ingress_http.jwt_authn.allowed` | 0.0000 |
| wk4-jwt-authn | jwt-off | fh | `http.ingress_http.jwt_authn.denied` | 0.0000 |
| wk4-jwt-authn | jwt-off | fh | `http.ingress_http.jwt_authn.jwt_cache_hit` | 0.0000 |
| wk4-jwt-authn | jwt-off | fh | `http.ingress_http.jwt_authn.jwt_cache_miss` | 0.0000 |
| wk4-jwt-authn | jwt | s | `http.ingress_http.jwt_authn.allowed` | 1.0000 |
| wk4-jwt-authn | jwt | s | `http.ingress_http.jwt_authn.denied` | 0.0000 |
| wk4-jwt-authn | jwt | s | `http.ingress_http.jwt_authn.jwt_cache_hit` | 0.0000 |
| wk4-jwt-authn | jwt | s | `http.ingress_http.jwt_authn.jwt_cache_miss` | 1.0000 |
| wk4-jwt-authn | jwt-cache | s | `http.ingress_http.jwt_authn.allowed` | 1.0000 |
| wk4-jwt-authn | jwt-cache | s | `http.ingress_http.jwt_authn.denied` | 0.0000 |
| wk4-jwt-authn | jwt-cache | s | `http.ingress_http.jwt_authn.jwt_cache_hit` | 1.0000 |
| wk4-jwt-authn | jwt-cache | s | `http.ingress_http.jwt_authn.jwt_cache_miss` | 0.0000 |
| wk4-jwt-authn | jwt-off | s | `http.ingress_http.jwt_authn.allowed` | 0.0000 |
| wk4-jwt-authn | jwt-off | s | `http.ingress_http.jwt_authn.denied` | 0.0000 |
| wk4-jwt-authn | jwt-off | s | `http.ingress_http.jwt_authn.jwt_cache_hit` | 0.0000 |
| wk4-jwt-authn | jwt-off | s | `http.ingress_http.jwt_authn.jwt_cache_miss` | 0.0000 |
| wk4-local-ratelimit | ratelimit-off | fh | `http_local_rate_limiter.http_local_rate_limit.enabled` | 0.0000 |
| wk4-local-ratelimit | ratelimit-off | fh | `http_local_rate_limiter.http_local_rate_limit.enforced` | 0.0000 |
| wk4-local-ratelimit | ratelimit-off | fh | `http_local_rate_limiter.http_local_rate_limit.ok` | 0.0000 |
| wk4-local-ratelimit | ratelimit-off | fh | `http_local_rate_limiter.http_local_rate_limit.rate_limited` | 0.0000 |
| wk4-local-ratelimit | ratelimit-on | fh | `http_local_rate_limiter.http_local_rate_limit.enabled` | 1.0000 |
| wk4-local-ratelimit | ratelimit-on | fh | `http_local_rate_limiter.http_local_rate_limit.enforced` | 0.0000 |
| wk4-local-ratelimit | ratelimit-on | fh | `http_local_rate_limiter.http_local_rate_limit.ok` | 1.0000 |
| wk4-local-ratelimit | ratelimit-on | fh | `http_local_rate_limiter.http_local_rate_limit.rate_limited` | 0.0000 |
| wk4-local-ratelimit | ratelimit-off | s | `http_local_rate_limiter.http_local_rate_limit.enabled` | 0.0000 |
| wk4-local-ratelimit | ratelimit-off | s | `http_local_rate_limiter.http_local_rate_limit.enforced` | 0.0000 |
| wk4-local-ratelimit | ratelimit-off | s | `http_local_rate_limiter.http_local_rate_limit.ok` | 0.0000 |
| wk4-local-ratelimit | ratelimit-off | s | `http_local_rate_limiter.http_local_rate_limit.rate_limited` | 0.0000 |
| wk4-local-ratelimit | ratelimit-on | s | `http_local_rate_limiter.http_local_rate_limit.enabled` | 1.0000 |
| wk4-local-ratelimit | ratelimit-on | s | `http_local_rate_limiter.http_local_rate_limit.enforced` | 0.0000 |
| wk4-local-ratelimit | ratelimit-on | s | `http_local_rate_limiter.http_local_rate_limit.ok` | 1.0000 |
| wk4-local-ratelimit | ratelimit-on | s | `http_local_rate_limiter.http_local_rate_limit.rate_limited` | 0.0000 |

