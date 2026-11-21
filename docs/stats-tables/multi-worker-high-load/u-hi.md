# Run U: store stats by worker count (bench-host)

Legs 159, invalid 10, complete rounds 15. Primary metric: worker-only cycles per request (the wrk: threads). stats-reject removes the store stats; the per-host primitive stats stay on, so the level and growth are the price of store stats, a lower bound on the price of all stat updates.

## Level per rung (descriptive)

| Rung | Workers | Base worker cycles/req (k) | Δ base − reject (k) [95% CI] | reject / base | A/A hw | A/A pass | Freq ratio base | Busy base | Steal max |
|---|---|---|---|---|---|---|---|---|---|
| mt-14w-one | 14 | 537.9 | 7.88 [4.11, 11.65] | -1.47% | 1.11 | no | 1.000 | 36.6% | 0.00% |
| mt-14w-split | 14 | 539.6 | 10.74 [7.43, 14.05] | -1.99% | 1.19 | no | 1.000 | 36.6% | 0.00% |
| mt-28w | 28 | 532.6 | 10.53 [6.22, 14.84] | -1.98% | 0.62 | yes | 1.000 | 36.1% | 0.00% |

## Confirmatory contrasts (Holm over 2 rows)

| Contrast | Kind | k cycles/req [95% CI] | Rounds | Holm p | Verdict |
|---|---|---|---|---|---|
| Δ(28w) − Δ(14w-one) | growth | +3.12 [-3.15, +9.39] | 14 | 0.41 | no verdict: an A/A of its rungs failed (reach 1.27%) |
| Δ(14w-split) − Δ(14w-one) | cross-socket | +2.51 [-1.56, +6.59] | 14 | 0.41 | no verdict: an A/A of its rungs failed (reach 1.64%) |

Host stats (per-host primitive counters and gauges) are not in these figures: their price is a model estimate (operation counts per request from step 0 times the microbenchmark cost per operation), given beside the row once both are measured.

## Envoy memory per NUMA node (base, MB, mean)

- mt-14w-one: node0 24, node1 48
- mt-14w-split: node0 21, node1 53
- mt-28w: node0 25, node1 57

