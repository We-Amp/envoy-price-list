# Feature rows, session 2

## Runs

- aa-2: 120 legs, 0 invalid; 20 complete rounds; stop: widest cycles_total half-width against its target 0.92% (fh base-A2 vs base) <= target 1.00%
- run-f: 200 legs, 0 invalid; 20 complete rounds; stop: widest cycles_total half-width against its target 0.86% (fh lua-header vs filter-off) <= target 1.50%; Wasm modules unchanged at the end: True
- 14-compression: 128 legs, 0 invalid; 16 complete rounds; stop: widest cycles_total half-width against its target 0.76% (j4 zstd vs comp-off) <= target 1.50%
- lc-j16: 72 legs, 0 invalid; 12 complete rounds; stop: fixed rounds
- 14b: 32 legs, 0 invalid; 16 complete rounds; stop: widest cycles_total half-width against its target 0.56% (s-ae gzip vs comp-off) <= target 0.80%
- lc-sfh: 48 legs, 0 invalid; 12 complete rounds; stop: fixed rounds

## A/A (AA-2, same session, an earlier run)

| Run / shape | A/A row | Half-width | Reach | Holm p | Pass |
|---|---|---|---|---|---|
| 14-compression / j16 | base-A2 on j16 | 0.78 | 0.92 | 1 | yes |
| 14-compression / j4 | base-A2 on s (borrowed) | 0.54 | 0.58 | 1 | yes |
| 14b / s-ae | base-A2 on s (borrowed) | 0.54 | 0.58 | 1 | yes |
| aa-2 / fh | base-A2 on fh | 0.92 | 1.12 | 1 | yes |
| aa-2 / j16 | base-A2 on j16 | 0.78 | 0.92 | 1 | yes |
| aa-2 / s | base-A2 on s | 0.54 | 0.58 | 1 | yes |
| run-f / fh | base-A2 on fh | 0.92 | 1.12 | 1 | yes |
| run-f / s | base-A2 on s | 0.54 | 0.58 | 1 | yes |

## Confirmatory rows (Holm over 10 rows, 10 with data)

| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| compression, gzip | j4 | gzip vs comp-off | +49.55% [+48.80, +50.31] | [+48.34, +50.77] | 0 | 16 | differs |
| compression, brotli | j4 | brotli vs comp-off | +52.98% [+51.94, +54.03] | [+51.59, +54.39] | 0 | 16 | differs |
| compression, zstd | j4 | zstd vs comp-off | +53.96% [+52.79, +55.13] | [+52.48, +55.45] | 0 | 16 | differs |
| compression, gzip | j16 | gzip vs comp-off | +130.97% [+129.78, +132.16] | [+129.09, +132.87] | 0 | 16 | differs |
| compression, brotli | j16 | brotli vs comp-off | +113.57% [+112.40, +114.75] | [+111.79, +115.37] | 0 | 16 | differs |
| compression, zstd | j16 | zstd vs comp-off | +80.16% [+78.99, +81.35] | [+78.56, +81.79] | 0 | 16 | differs |
| Lua, header script | s | lua-header vs filter-off | +11.75% [+11.40, +12.10] | [+10.94, +12.57] | 0 | 20 | differs |
| Wasm, header module | s | wasm-header vs filter-off | +15.60% [+15.19, +16.01] | [+14.74, +16.46] | 0 | 20 | differs |
| Lua, header script | fh | lua-header vs filter-off | +16.68% [+15.69, +17.68] | [+15.47, +17.90] | 0 | 20 | differs |
| Wasm, header module | fh | wasm-header vs filter-off | +23.24% [+22.25, +24.24] | [+22.00, +24.49] | 0 | 20 | differs |

## Secondary rows (Holm over 7 rows, 7 with data)

| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| Lua, empty script | s | lua-empty vs filter-off | +7.21% [+6.91, +7.52] | [+6.44, +7.98] | 0 | 20 | differs |
| Wasm, empty module | s | wasm-empty vs filter-off | +9.67% [+9.23, +10.11] | [+8.83, +10.51] | 0 | 20 | differs |
| Lua, empty script | fh | lua-empty vs filter-off | +9.77% [+8.93, +10.63] | [+8.70, +10.86] | 1.78e-15 | 20 | differs |
| Wasm, empty module | fh | wasm-empty vs filter-off | +13.63% [+12.57, +14.69] | [+12.39, +14.88] | 0 | 20 | differs |
| A/A | s | base-A2 vs base | -0.03% [-0.58, +0.51] | [-0.87, +0.81] | 1 | 20 | within the A/A spread (< 1%) |
| A/A | fh | base-A2 vs base | +0.20% [-0.71, +1.12] | [-0.88, +1.29] | 1 | 20 | within the A/A spread (< 1%) |
| A/A | j16 | base-A2 vs base | -0.14% [-0.91, +0.65] | [-1.12, +0.86] | 1 | 20 | within the A/A spread (< 1%) |

## Row 14b (Holm over 1 rows, 1 with data)

| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Holm p | Pairs | Verdict |
|---|---|---|---|---|---|---|---|
| gzip in the chain, nothing compressible | s-ae | gzip vs comp-off | +5.25% [+4.66, +5.84] | [+4.36, +6.14] | 5.13e-12 | 16 | differs |

## Absolute cost, user and kernel split, both busy levels (exploratory)

On loopback the kernel cycles include part of the client's receive work, which shrinks with a compressed response; the user-cycle difference is the transferable part. A percentage whose arm runs busier than its reference is a lower bound.

| Row | Shape | Ref -> arm total (k) | Added (k) | cycles:u effect | Added user (k) | cycles:k effect | instructions:u effect | Busy ref -> arm |
|---|---|---|---|---|---|---|---|---|
| compression, gzip | j4 | 528.4 -> 792.2 | +262.59 | +76.01% | +264.78 | -1.20% | +246.48% | 31.5% -> 45.9% |
| compression, brotli | j4 | 528.4 -> 810.4 | +280.77 | +81.62% | +284.36 | -1.98% | +217.08% | 31.5% -> 46.9% |
| compression, zstd | j4 | 528.4 -> 816.7 | +285.95 | +83.23% | +289.94 | -2.20% | +138.72% | 31.5% -> 47.2% |
| compression, gzip | j16 | 568.4 -> 1317.5 | +746.89 | +205.57% | +757.10 | -5.05% | +858.39% | 26.3% -> 58.2% |
| compression, brotli | j16 | 568.4 -> 1218.3 | +647.66 | +178.36% | +656.89 | -4.56% | +616.51% | 26.3% -> 53.8% |
| compression, zstd | j16 | 568.4 -> 1029.2 | +457.17 | +126.00% | +464.04 | -3.40% | +341.52% | 26.3% -> 45.7% |
| Lua, header script | s | 526.9 -> 587.5 | +61.83 | +17.25% | +59.44 | +1.31% | +19.27% | 31.2% -> 34.6% |
| Wasm, header module | s | 526.9 -> 607.9 | +82.10 | +23.11% | +79.65 | +1.35% | +23.91% | 31.2% -> 35.6% |
| Lua, header script | fh | 282.1 -> 330.1 | +47.05 | +23.10% | +45.95 | +1.32% | +18.46% | 25.6% -> 29.6% |
| Wasm, header module | fh | 282.1 -> 347.7 | +65.55 | +32.50% | +64.64 | +1.09% | +21.98% | 25.6% -> 31.2% |
| Lua, empty script | s | 526.9 -> 564.7 | +37.94 | +10.79% | +37.18 | +0.42% | +10.76% | 31.2% -> 33.2% |
| Wasm, empty module | s | 526.9 -> 577.6 | +50.88 | +14.26% | +49.15 | +0.95% | +12.43% | 31.2% -> 34.0% |
| Lua, empty script | fh | 282.1 -> 309.5 | +27.57 | +14.08% | +28.00 | -0.52% | +10.42% | 25.6% -> 27.9% |
| Wasm, empty module | fh | 282.1 -> 321.9 | +38.45 | +19.66% | +39.11 | -0.80% | +10.97% | 25.6% -> 28.9% |
| A/A | s | 526.3 -> 525.4 | -0.18 | +0.02% | +0.05 | -0.13% | -0.01% | 31.3% -> 31.2% |
| A/A | fh | 282.2 -> 280.7 | +0.56 | +0.04% | +0.08 | +0.58% | +0.00% | 25.5% -> 25.5% |
| A/A | j16 | 569.9 -> 567.7 | -0.76 | -0.32% | -1.18 | +0.20% | -0.00% | 26.2% -> 26.2% |
| gzip in the chain, nothing compressible | s-ae | 527.6 -> 555.6 | +27.70 | +7.36% | +25.51 | +1.21% | +8.07% | 31.3% -> 32.8% |

## Exploratory rows (interval only)

| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Pairs |
|---|---|---|---|---|---|
| Wasm against Lua, header | s | wasm-header vs lua-header | +3.45% [+3.07, +3.82] | [+2.68, +4.22] | 20 |
| Wasm against Lua, header | fh | wasm-header vs lua-header | +5.62% [+4.93, +6.32] | [+4.66, +6.59] | 20 |
| Wasm against Lua, empty | s | wasm-empty vs lua-empty | +2.29% [+1.81, +2.77] | [+1.48, +3.11] | 20 |
| Wasm against Lua, empty | fh | wasm-empty vs lua-empty | +3.51% [+2.77, +4.26] | [+2.54, +4.50] | 20 |
| brotli against gzip | j4 | brotli vs gzip | +2.29% [+1.85, +2.74] | [+1.50, +3.09] | 16 |
| zstd against gzip | j4 | zstd vs gzip | +2.95% [+2.52, +3.37] | [+2.16, +3.74] | 16 |
| zstd against brotli | j4 | zstd vs brotli | +0.64% [+0.13, +1.15] | [-0.18, +1.46] | 16 |
| brotli against gzip | j16 | brotli vs gzip | -7.53% [-7.75, -7.32] | [-8.18, -6.88] | 16 |
| zstd against gzip | j16 | zstd vs gzip | -22.00% [-22.33, -21.66] | [-22.60, -21.39] | 16 |
| zstd against brotli | j16 | zstd vs brotli | -15.64% [-15.94, -15.34] | [-16.27, -15.01] | 16 |

## Compression: ratio, minor faults, upstream segments (means over valid legs)

| Arm | Shape | Ratio (uncompressed / compressed) | Minor faults / req | Upstream segments in / response |
|---|---|---|---|---|
| comp-off | j4 | - | 0.068 | 2.01 |
| gzip | j4 | - | 0.076 | 2.01 |
| brotli | j4 | - | 0.054 | 2.01 |
| zstd | j4 | - | 0.097 | 2.01 |
| comp-off | j16 | - | 0.048 | 2.01 |
| gzip | j16 | - | 0.013 | 2.01 |
| brotli | j16 | - | 0.104 | 2.01 |
| zstd | j16 | - | 0.121 | 2.01 |

## Load curve of the j16 reference (internal, exploratory)

Points (busy, k cycles per request): j16 26.3% 570.3, j16-a 32.2% 543.8, j16-b 43.4% 507.4, j16-c 59.6% 477.0

| Arm | Busy | Arm cycles (k) | Reference at that busy (k) | Load-matched added (k) | As % |
|---|---|---|---|---|---|
| gzip | 58.2% | 1317.2 | 479.8 | +837.4 | +174.5% |
| brotli | 53.8% | 1218.0 | 487.9 | +730.1 | +149.7% |
| zstd | 45.7% | 1027.5 | 503.2 | +524.3 | +104.2% |

## Evidence and side services (every current leg)

- 14-compression j16/brotli: evidence ok on 16 of 16 legs
- 14-compression j16/comp-off: evidence ok on 16 of 16 legs
- 14-compression j16/gzip: evidence ok on 16 of 16 legs
- 14-compression j16/zstd: evidence ok on 16 of 16 legs
- 14-compression j4/brotli: evidence ok on 16 of 16 legs
- 14-compression j4/comp-off: evidence ok on 16 of 16 legs
- 14-compression j4/gzip: evidence ok on 16 of 16 legs
- 14-compression j4/zstd: evidence ok on 16 of 16 legs
- 14b s-ae/comp-off: evidence ok on 16 of 16 legs
- 14b s-ae/gzip: evidence ok on 16 of 16 legs
- aa-2 fh/base: evidence ok on 20 of 20 legs
- aa-2 fh/base-A2: evidence ok on 20 of 20 legs
- aa-2 j16/base: evidence ok on 20 of 20 legs
- aa-2 j16/base-A2: evidence ok on 20 of 20 legs
- aa-2 s/base: evidence ok on 20 of 20 legs
- aa-2 s/base-A2: evidence ok on 20 of 20 legs
- jit-check s-wu30/lua-header: evidence ok on 2 of 2 legs
- jit-check s-wu30/wasm-header: evidence ok on 2 of 2 legs
- jit-check s-wu5/lua-header: evidence ok on 2 of 2 legs
- jit-check s-wu5/wasm-header: evidence ok on 2 of 2 legs
- lc-j16 j16-a/comp-off: evidence ok on 12 of 12 legs
- lc-j16 j16-a/comp-off-A2: evidence ok on 12 of 12 legs
- lc-j16 j16-b/comp-off: evidence ok on 12 of 12 legs
- lc-j16 j16-b/comp-off-A2: evidence ok on 12 of 12 legs
- lc-j16 j16-c/comp-off: evidence ok on 12 of 12 legs
- lc-j16 j16-c/comp-off-A2: evidence ok on 12 of 12 legs
- lc-sfh fh-13600/base: evidence ok on 12 of 12 legs
- lc-sfh fh-13600/base-A2: evidence ok on 12 of 12 legs
- lc-sfh s-9600/base: evidence ok on 12 of 12 legs
- lc-sfh s-9600/base-A2: evidence ok on 12 of 12 legs
- run-f fh/filter-off: evidence ok on 20 of 20 legs
- run-f fh/lua-empty: evidence ok on 20 of 20 legs
- run-f fh/lua-header: evidence ok on 20 of 20 legs
- run-f fh/wasm-empty: evidence ok on 20 of 20 legs
- run-f fh/wasm-header: evidence ok on 20 of 20 legs
- run-f s/filter-off: evidence ok on 20 of 20 legs
- run-f s/lua-empty: evidence ok on 20 of 20 legs
- run-f s/lua-header: evidence ok on 20 of 20 legs
- run-f s/wasm-empty: evidence ok on 20 of 20 legs
- run-f s/wasm-header: evidence ok on 20 of 20 legs
- smoke-sfh.first fh-13600/base: evidence ok on 2 of 2 legs
- smoke-sfh.first fh-13600/base-A2: evidence ok on 2 of 2 legs
- smoke-sfh.first s-9600/base: evidence ok on 2 of 2 legs
- smoke-sfh.first s-9600/base-A2: evidence ok on 2 of 2 legs

