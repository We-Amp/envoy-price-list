# Run U: store stats by worker count (bench-host)

Legs 231, invalid 2, complete rounds 15. Primary metric: worker-only cycles per request (the wrk: threads). stats-reject removes the store stats; the per-host primitive stats stay on, so the level and growth are the price of store stats, a lower bound on the price of all stat updates.

## Level per rung (descriptive)

| Rung | Workers | Base worker cycles/req (k) | Δ base − reject (k) [95% CI] | reject / base | A/A hw | A/A pass | Freq ratio base | Busy base | Steal max |
|---|---|---|---|---|---|---|---|---|---|
| mt-1w | 1 | 634.7 | 16.95 [-7.62, 41.51] | -2.63% | 3.19 | no | 0.999 | 29.1% | 0.00% |
| mt-4w | 4 | 580.2 | 13.47 [7.13, 19.80] | -2.33% | 1.24 | no | 1.000 | 26.5% | 0.00% |
| mt-14w-one | 14 | 569.5 | 13.06 [8.87, 17.24] | -2.29% | 0.88 | yes | 1.000 | 25.9% | 0.00% |
| mt-14w-split | 14 | 570.2 | 15.06 [9.59, 20.53] | -2.64% | 0.82 | yes | 1.000 | 25.9% | 0.00% |
| mt-28w | 28 | 572.1 | 13.05 [8.03, 18.06] | -2.28% | 1.02 | no | 1.000 | 26.0% | 0.00% |

## Confirmatory contrasts (Holm over 3 rows)

| Contrast | Kind | k cycles/req [95% CI] | Rounds | Holm p | Verdict |
|---|---|---|---|---|---|
| Δ(28w) − Δ(1w) | growth | -3.90 [-29.82, +22.02] | 15 | 1 | no verdict: an A/A of its rungs failed (reach 4.24%) |
| Δ(14w-one) − Δ(1w) | growth | -3.89 [-28.98, +21.20] | 15 | 1 | no verdict: an A/A of its rungs failed (reach 4.24%) |
| Δ(14w-split) − Δ(14w-one) | cross-socket | +2.00 [-4.74, +8.74] | 15 | 1 | not resolved |

Host stats (per-host primitive counters and gauges) are not in these figures: their price is a model estimate (operation counts per request from step 0 times the microbenchmark cost per operation), given beside the row once both are measured.

## HITM loads per request (evidence legs, outside the timed run)

| Rung | Arm | local HITM / req | remote HITM / req |
|---|---|---|---|
| mt-1w | base | 37.529 | 55.395 |
| mt-1w | stats-reject | 36.527 | 53.704 |
| mt-4w | base | 39.068 | 58.431 |
| mt-4w | stats-reject | 37.575 | 58.651 |
| mt-14w-one | base | 32.579 | 61.847 |
| mt-14w-one | stats-reject | 25.380 | 62.773 |
| mt-14w-split | base | 39.233 | 52.453 |
| mt-14w-split | stats-reject | 37.395 | 46.473 |
| mt-28w | base | 40.806 | 41.847 |
| mt-28w | stats-reject | 33.814 | 40.725 |

## Envoy memory per NUMA node (base, MB, mean)

- mt-14w-one: node0 24, node1 49
- mt-14w-split: node0 21, node1 52
- mt-1w: node0 17, node1 48
- mt-28w: node0 25, node1 56
- mt-4w: node0 18, node1 48

