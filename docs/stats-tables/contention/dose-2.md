# Run R1 (dose), SHORT RUN of 6 rounds: shared against worker-exclusive counters (bench-host)

Legs 106, invalid 8, complete rounds 6. In each cell: own (the reference: one set of K counters per downstream connection), shared (the same K counters as one object each, written by every worker) and a second copy of own (A/A), at the cell's own K: cell A K = 128, cell B K = 128, cell D K = 64. rho = mean per-round 100 x ln(shared / own) of worker-only cycles per request.

## Cells (descriptive)

| Cell | Rung | Workers | Rate per worker | Role | K | Own worker cycles/req (k) | rho % [95% t CI] | Busy own | Valid rounds | A/A hw | A/A reach | A/A p | A/A pass | Instructions shared / own |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 14w-one | 14 | 1500 | reference | 128 | 696.8 | +0.27 [-2.36, +2.89] | 46.8% | 5 | 1.53 | 2.05 | 0.398 | no | +0.043% |
| A (second dose) | 14w-one | 14 | 1500 | reference | 64 | 620.0 | +0.53 [-0.03, +1.08] | 41.9% | 5 | 1.53 | 2.05 | 0.398 | no | +0.021% |
| A (HOT COUNTER, exploratory) | 14w-one | 14 | 1500 | reference | 128 | 680.4 | +2.90 [+1.07, +4.73] | 45.8% | 5 | 1.53 | 2.05 | 0.398 | no | -2.031% |
| B | 14w-split | 14 | 1500 | socket | 128 | 698.6 | +0.04 [-1.30, +1.38] | 46.9% | 6 | 1.28 | 2.03 | 0.191 | no | +0.036% |
| D | 28w | 28 | 1500 | workers | 64 | 619.5 | +0.30 [-0.68, +1.29] | 41.7% | 6 | 1.61 | 2.39 | 0.269 | no | +0.024% |

A short run: 6 rounds, by decision; no minimum of 12 valid rounds applies, and nothing is re-run to rescue a statement.

The second dose's pair in cell A uses that cell's A/A (own-128-A2 against own-128).

## Statements (pre-stated 2026-11-20; Holm over 5)

| # | Statement | Estimate, widened 95% interval | Plain 95% t interval | Rounds | Holm p | Predicted | Verdict |
|---|---|---|---|---|---|---|---|
| S1 | rho_A at K = 128 (14w-one, reference) | +0.27 [-1.70, +2.23] | +0.27 [-2.36, +2.89] | 5 | 1 | - | no verdict: cell A A/A failed: half-width 1.53%, reach 2.05%, p 0.398 |
| S2 | rho_B at K = 128 (14w-split, socket) | +0.04 [-1.18, +1.26] | +0.04 [-1.30, +1.38] | 6 | 1 | - | no verdict: cell B A/A failed: half-width 1.28%, reach 2.03%, p 0.191 |
| S3 | rho_D at K = 64 (28w, workers) | +0.30 [-0.70, +1.31] | +0.30 [-0.68, +1.29] | 6 | 1 | - | no verdict: cell D A/A failed: half-width 1.61%, reach 2.39%, p 0.269 |
| S4 | socket: rho_B(128) - rho_A(128) | -0.08 [-2.80, +2.64] | -0.08 [-3.70, +3.54] | 5 | 1 | +2 to +4 points | no verdict: cell B A/A failed: half-width 1.28%, reach 2.03%, p 0.191 |
| S5 | workers: rho_D(64) - rho_A(64): 28 workers on two sockets against 14 on one socket (confounded with the socket split) | -0.22 [-1.40, +0.96] | -0.22 [-1.15, +0.71] | 6 | 1 | no directional prediction | no verdict: cell D A/A failed: half-width 1.61%, reach 2.39%, p 0.269 |

6 rounds give 5 degrees of freedom: the plain t interval (quantile 2.57) is printed beside the widened one (1.96 with the 0.34 term), and the reader should take the wider of the two. The verdicts use the widened interval, as pre-stated.

Estimates are log points x 100 (percent; S4 and S5 in points). Widened: 1.96 x sqrt(SE^2 + 0.34^2) for a cell, 1.96 x sqrt(SE^2 + 2 x 0.34^2) for a difference of two cells. A cell that is not a finding is a bound on rho, not evidence of no cost.

A short run: what its rounds do not resolve is "not resolved in a short run, under X", X the widened interval's upper end; a cell whose A/A fails has no verdict (not a bound); an interval entirely below 0 is an invalid comparison, not a negative price. rho is diluted by the logger's own cost per update (it is in own and in shared alike); the price per update below is not.

Order (from the legs as they ran): cell A (7 arms, 6 rounds) shared / own at K = 128: shared-128 ran -0.17 slots from own-128 on average and directly after it in 5 of 6 rounds; cell A (7 arms, 6 rounds) A/A: own-128-A2 ran -0.33 slots from own-128 on average and directly after it in 0 of 6 rounds; cell A (7 arms, 6 rounds) shared / own at K = 64: shared-64 ran -0.17 slots from own-64 on average and directly after it in 5 of 6 rounds; cell A (7 arms, 6 rounds) hot shared / own: hot-shared-128 ran -0.17 slots from hot-own-128 on average and directly after it in 5 of 6 rounds; cell B (3 arms, 6 rounds) shared / own at K = 128: shared-128 ran +0.00 slots from own-128 on average and directly after it in 4 of 6 rounds; cell B (3 arms, 6 rounds) A/A: own-128-A2 ran +0.00 slots from own-128 on average and directly after it in 0 of 6 rounds; cell D (3 arms, 6 rounds) shared / own at K = 64: shared-64 ran +0.00 slots from own-64 on average and directly after it in 4 of 6 rounds; cell D (3 arms, 6 rounds) A/A: own-64-A2 ran +0.00 slots from own-64 on average and directly after it in 0 of 6 rounds. A mean position difference other than 0, or one arm mostly directly after the other, means a carry-over from the leg before is not averaged out of that pair.

## Cycles per shared update

| Cell | K | P: (shared - own) / K, worker cycles [95% t CI] (measured) | d: clean L3 hits per update, own - shared (evidence legs) (one round, no interval) | P + d x 45 cycles (MODELLED upper figure) (one round, no interval) |
|---|---|---|---|---|
| A | 128 | +14.8 [-128.3, +158.0] | +1.64 | 88.7 |
| A | 64 | +51.3 [-2.9, +105.5] | - | - |
| B | 128 | +2.3 [-70.9, +75.5] | +1.70 | 78.6 |
| D | 64 | +29.4 [-65.6, +124.4] | +1.70 | 105.8 |
| A, HOT COUNTER (exploratory) | 128 on one counter | +156.3 [+58.1, +254.5] | - | - |

Hot counter in cell A (EXPLORATORY, outside the statements, 5 rounds): one counter takes the 128 increments of a request, so the write rate on its line is 128 times a spread counter's. rho +2.90 [+1.07, +4.73]% (widened +2.90 [+1.45, +4.35]), price +156.3 cycles per update. The spread pair at K = 128: P +14.8, footprint band P + d x 45 = 88.7 (one round, no interval); the hot price is 1.76 times the band. Only a hot price above the band is a sign of writers queuing on a line: hot-own has no footprint penalty (its one counter stays in its worker's cache) while the spread own arm has, so the spread P understates the price the hot pair is compared with. At this box's rates the hot line is occupied only an estimated 12-20% of the time, so a hot price at or below the band does not show the absence of queuing on wider machines.

P is measured and likely understates the sharing price: the own arm holds one counter set per connection and pays extra L3 hits for them. The last column adds d L3 hits at an assumed 45 cycles each (no overlap credited): a modelled upper figure, not a measurement. No band where the evidence legs do not run that pair.

Linearity in cell A (a description, not a statement): on the means, P = (exp(rho) - 1) x C / dose is 14.5 cycles per update at K = 128 (rho +0.27%) and 69.4 at K = 64 (rho +0.71%); ln(P(128) / P(64)) = -156.7 [-870.8, +557.5] (log points x 100, unwidened, 5 rounds). At the smaller dose the effect is small and the footprint of the own arm differs, so this has little power.

## HITM:u loads per request (evidence legs, outside the timed run)

| Cell | K | base | stats-reject | own | shared | (shared - own) / K = h | Line-transfer threshold 0.15 x K | base - stats-reject (one round, no interval) | Store-stat operations/req, base |
|---|---|---|---|---|---|---|---|---|---|
| A | 128 | 16.20 | 7.66 | 27.85 | 55.45 | 0.216 | 19.2 per request | +8.53 | 17.0 |
| B | 128 | 19.18 | 9.25 | 32.26 | 73.14 | 0.319 | 19.2 per request | +9.93 | 17.0 |
| D | 64 | 19.35 | 9.82 | 25.08 | 52.04 | 0.421 | 9.6 per request | +9.53 | 17.0 |

ONE ROUND, NO INTERVAL: the evidence legs ran once per cell, so h, d, T, the footprint band and the line-transfer label all rest on one leg per arm and cell.

The HITM load event sees only a fraction of the transfers of locked updates (h well under 1 in the pilot). Gauge updates are not in the operation count (an increment and a decrement cancel in snapshots).

## Model row for the plain config (a MODEL, not a measurement)

| Cell | Sockets | K | P: price per update from the widened upper end of rho, cycles | T: store-stat operations/req of the plain config (probe) (one round, no interval) | C: base worker cycles/req (k) | MODEL T x P / C | MODEL with the footprint band, T x (P + d x 45) / C (one round, no interval) | For comparison, HITM-scaled: HITM:u (base - reject) x P / h, as a share of C (one round, no interval) |
|---|---|---|---|---|---|---|---|---|
| A | 1 | 128 | 123.0 | 17.0 | 542.5 | the cell has no verdict (A/A failed) | - | - |
| A | 1 | 64 | 128.5 | 17.0 | 542.5 | the cell has no verdict (A/A failed) | - | - |
| B | 2 | 128 | 69.1 | 17.0 | 533.8 | the cell has no verdict (A/A failed) | - | - |
| D | 2 | 64 | 127.2 | 17.0 | 528.6 | the cell has no verdict (A/A failed) | - | - |

**MODEL, one socket:** no model row (cell A: the cell has no verdict (A/A failed)).

**MODEL, two sockets:** no model row (cell B: the cell has no verdict (A/A failed); cell D: the cell has no verdict (A/A failed)).

Expected: 0.3-0.8% on one socket, 0.6-1.7% split. P = (exp(the widened interval's upper end of rho) - 1) x own cycles / counters; T counts every store-stat operation of the plain config as a shared update (one round, no interval). P likely understates the sharing price, so the P-based figure is not an upper bound; the band column adds d L3 hits at 45 cycles to P. The HITM-scaled column is printed for comparison only (means, not upper ends).

R1 prices a shared update; the claim about deployments is the model row only. The K updates of a request arrive in one burst.

