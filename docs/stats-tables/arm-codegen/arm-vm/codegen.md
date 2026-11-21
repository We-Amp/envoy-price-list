# arm64 atomics codegen: official release against the main dev-image build

Metric: workers_cycles_per_req, valid legs of complete rounds. Log ratios in percent, 95% t interval over rounds. Primary: ln(dev / dev-reject) - ln(official / official-reject) (positive: store stats cost more in the inline LL/SC build). The direct dev / official row is confounded by every other difference between the builds.

| Rung | Rounds | A/A | Stats price, official | Stats price, dev | Primary | Verdict | Direct (confounded) |
|---|---|---|---|---|---|---|---|
| mt-4w | 20 | +0.73% [+0.18, +1.29] (fails) | +3.30% [+2.65, +3.95] | +2.97% [+2.47, +3.47] | -0.33% [-1.27, +0.61] | no verdict (A/A did not pass) | +0.64% [-0.01, +1.29] |
| mt-12w | 20 | +0.03% [-0.80, +0.85] | +3.39% [+2.67, +4.11] | +3.30% [+2.92, +3.67] | -0.09% [-0.85, +0.67] | no resolved difference; at most 0.85% | +0.37% [-0.08, +0.81] |

Absolute (cycles per request, 95%% t interval over rounds):

| Rung | Stats price, official | Stats price, dev | (dev - dev-reject) - (official - official-reject) |
|---|---|---|---|
| mt-4w | +11201 [+8999, +13404] | +10174 [+8475, +11874] | -1027 [-4230, +2176] |
| mt-12w | +11612 [+9159, +14065] | +11351 [+10065, +12638] | -261 [-2861, +2339] |

The two rungs are separate rows with their own A/A gate; no multiplicity correction across them.

| Rung | Arm | Median workers_cycles_per_req | Median user instructions per request |
|---|---|---|---|
| mt-4w | official | 345387.1 | 153454.1 |
| mt-4w | official-reject | 334852.1 | 147041.9 |
| mt-4w | dev | 347202.6 | 148507.8 |
| mt-4w | dev-reject | 337246.4 | 142391.3 |
| mt-4w | official-A2 | 348888.1 | 153438.3 |
| mt-12w | official | 348101.6 | 153443.0 |
| mt-12w | official-reject | 336669.0 | 147016.1 |
| mt-12w | dev | 350363.6 | 148559.4 |
| mt-12w | dev-reject | 338276.5 | 142434.3 |
| mt-12w | official-A2 | 348206.7 | 153429.4 |

