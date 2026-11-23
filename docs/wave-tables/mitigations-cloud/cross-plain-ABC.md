## Cross-boot rows (P = (A + C)/2 - B, log points; on minus off)

| Run/shape | Metric | A | B | C | P [hw] | % | A - C | reach |
|---|---|---|---|---|---|---|---|---|
| h-c1/c1 | cycles_total | 1288.65 (6) | 1286.52 (6) | 1287.86 (6) | +1.74 [1.45] | +1.8 | +0.79 | 2.71 |
| h-c1/c1 | cycles_u | 1248.13 (6) | 1248.00 (6) | 1247.40 (6) | -0.23 [1.06] | -0.2 | +0.73 | 2.12 |
| h-c1/c1 | cycles_k | 1178.71 (6) | 1172.46 (6) | 1177.82 (6) | +5.80 [2.64] | +6.0 | +0.89 | 4.36 |
| h-c1/c1 | instructions_u | 1221.79 (6) | 1221.79 (6) | 1221.79 (6) | +0.00 [0.67] | +0.0 | -0.00 | 0.67 |
| h-c1/c1 | instructions_k | 1189.02 (6) | 1189.09 (6) | 1186.86 (6) | -1.15 [0.69] | -1.1 | +2.17 | 2.85 |
| h-c1/ka | cycles_total | 1248.90 (6) | 1248.72 (6) | 1250.20 (6) | +0.83 [1.37] | +0.8 | -1.30 | 3.61 |
| h-c1/ka | cycles_u | 1216.24 (6) | 1217.83 (6) | 1217.09 (6) | -1.17 [1.56] | -1.2 | -0.85 | 2.40 |
| h-c1/ka | cycles_k | 1121.02 (6) | 1116.07 (6) | 1123.56 (6) | +6.22 [4.51] | +6.4 | -2.54 | 7.49 |
| h-c1/ka | instructions_u | 1200.61 (6) | 1200.62 (6) | 1200.61 (6) | -0.01 [0.67] | -0.0 | -0.00 | 0.67 |
| h-c1/ka | instructions_k | 1129.69 (6) | 1129.64 (6) | 1127.15 (6) | -1.23 [0.69] | -1.2 | +2.54 | 3.24 |
| h-pl/fh | cycles_total | 1180.14 (6) | 1180.40 (6) | 1181.14 (6) | +0.24 [0.94] | +0.2 | -1.00 | 1.94 |
| h-pl/fh | cycles_u | 1151.64 (6) | 1152.64 (6) | 1152.87 (6) | -0.39 [0.96] | -0.4 | -1.23 | 2.16 |
| h-pl/fh | cycles_k | 1040.71 (6) | 1038.67 (6) | 1041.01 (6) | +2.19 [0.97] | +2.2 | -0.31 | 1.38 |
| h-pl/fh | instructions_u | 1201.34 (6) | 1201.33 (6) | 1201.34 (6) | +0.00 [0.67] | +0.0 | -0.00 | 0.67 |
| h-pl/fh | instructions_k | 1028.34 (6) | 1028.21 (6) | 1025.02 (6) | -1.53 [0.89] | -1.5 | +3.32 | 4.16 |
| h-pl/s | cycles_total | 1242.68 (6) | 1244.37 (6) | 1245.15 (6) | -0.46 [0.77] | -0.5 | -2.47 | 3.30 |
| h-pl/s | cycles_u | 1212.56 (6) | 1213.60 (6) | 1213.51 (6) | -0.56 [0.74] | -0.6 | -0.95 | 1.76 |
| h-pl/s | cycles_k | 1107.99 (6) | 1111.51 (6) | 1114.65 (6) | -0.19 [1.54] | -0.2 | -6.65 | 8.20 |
| h-pl/s | instructions_u | 1200.50 (6) | 1200.52 (6) | 1200.51 (6) | -0.02 [0.67] | -0.0 | -0.00 | 0.67 |
| h-pl/s | instructions_k | 1116.34 (6) | 1116.45 (6) | 1113.60 (6) | -1.48 [0.67] | -1.5 | +2.74 | 3.41 |

A/A per block: A h-pl/s -0.20 (pass); A h-pl/fh -0.17 (pass); A h-c1/s -0.57 (pass); B h-pl/s -0.09 (pass); B h-pl/fh -1.02 (FAIL); B h-c1/s +1.72 (pass); C h-pl/s +0.11 (pass); C h-pl/fh -0.71 (pass); C h-c1/s +0.71 (pass)
User-instruction identity: h-c1/c1 0.00 ok; h-c1/ka 0.01 ok; h-pl/fh 0.00 ok; h-pl/s 0.02 ok

Verdicts:
- h-c1/c1: under the kill line or inside the boot-to-boot reach (P +1.74, reach 2.71)
- h-pl/fh: invalid: the A/A of block(s) B failed
- h-pl/s: invalid: the A/A of block(s) B failed
- the mitigations as a price-list row: open: at least one confirmatory row has no verdict (see verdicts)
