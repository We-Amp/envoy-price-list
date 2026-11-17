## Run C (counters, exploratory)

Legs recorded 192, valid and current 192, invalid 0, superseded 0; rounds 24; stop: fixed rounds.

- s-hi: in-window rate +0.02% to +0.02% of target; overflow max 0; headroom min 0.69
- fh-hi: in-window rate +0.02% to +0.02% of target; overflow max 0; headroom min 0.65

Lowest counter running share over all valid legs: 100.00% (100 = never multiplexed).

### Per arm means (top-down shares in % of slots; events per request)

**s-hi @ 12000**

| Metric | v1.32.13 | v1.37.11 | v1.38.9 | v1.40.2 |
|---|---|---|---|---|
| bad_spec | 4.50 | 4.63 | 4.66 | 4.80 |
| be_bound | 11.31 | 10.49 | 10.56 | 10.53 |
| cycles_total | 448.7k | 449.8k | 455.4k | 457.8k |
| ev:br_misp_retired.all_branches | 1703.24 | 1797.41 | 1815.44 | 1857.40 |
| ev:dsb2mite_switches.penalty_cycles | 3748.77 | 3357.46 | 3794.54 | 3502.40 |
| ev:dtlb_load_misses.walk_duration | 8373.80 | 9328.41 | 9017.49 | 9285.73 |
| ev:icache.misses | 11.3k | 11.4k | 11.5k | 11.7k |
| ev:idq_uops_not_delivered.core | 1236.8k | 1277.0k | 1279.0k | 1295.2k |
| ev:int_misc.recovery_cycles | 10.5k | 11.1k | 11.0k | 11.6k |
| ev:itlb_misses.walk_completed | 199.97 | 205.42 | 229.65 | 200.54 |
| ev:itlb_misses.walk_duration | 7304.65 | 7472.39 | 8431.29 | 8096.47 |
| ev:mem_load_uops_retired.l1_miss | 3691.67 | 3650.08 | 3711.37 | 3761.92 |
| ev:mem_load_uops_retired.l3_miss | 132.51 | 134.51 | 134.59 | 132.41 |
| ev:uops_issued.any | 316.5k | 298.1k | 305.6k | 294.1k |
| ev:uops_retired.retire_slots | 277.5k | 258.6k | 265.0k | 252.5k |
| fe_bound | 68.76 | 70.58 | 70.23 | 70.85 |
| instructions_u | 185.8k | 167.7k | 174.3k | 163.0k |
| retiring | 15.43 | 14.30 | 14.55 | 13.82 |

**fh-hi @ 18400**

| Metric | v1.32.13 | v1.37.11 | v1.38.9 | v1.40.2 |
|---|---|---|---|---|
| bad_spec | 3.86 | 4.19 | 4.01 | 4.38 |
| be_bound | 15.16 | 14.48 | 14.64 | 14.12 |
| cycles_total | 267.3k | 255.4k | 259.5k | 248.1k |
| ev:br_misp_retired.all_branches | 860.78 | 893.71 | 868.47 | 919.46 |
| ev:dsb2mite_switches.penalty_cycles | 2922.03 | 2584.34 | 2462.75 | 2050.47 |
| ev:dtlb_load_misses.walk_duration | 6011.96 | 6234.19 | 6196.41 | 6298.21 |
| ev:icache.misses | 5518.63 | 5489.66 | 5566.12 | 5571.75 |
| ev:idq_uops_not_delivered.core | 596.7k | 601.3k | 604.1k | 603.4k |
| ev:int_misc.recovery_cycles | 5427.62 | 5653.57 | 5521.62 | 5830.20 |
| ev:itlb_misses.walk_completed | 135.41 | 119.93 | 129.84 | 128.09 |
| ev:itlb_misses.walk_duration | 4612.85 | 4392.61 | 4629.82 | 4599.05 |
| ev:mem_load_uops_retired.l1_miss | 2409.58 | 2330.00 | 2419.63 | 2238.55 |
| ev:mem_load_uops_retired.l3_miss | 61.33 | 60.27 | 60.92 | 60.80 |
| ev:uops_issued.any | 290.9k | 247.7k | 259.7k | 222.1k |
| ev:uops_retired.retire_slots | 271.2k | 227.6k | 240.1k | 202.2k |
| fe_bound | 55.67 | 59.00 | 58.21 | 61.05 |
| instructions_u | 230.7k | 189.2k | 202.3k | 164.4k |
| retiring | 25.31 | 22.33 | 23.14 | 20.45 |

### Paired comparisons (later against earlier; shares: difference in points, t interval; events and cycles: log ratio %)

| Cell | Pair | Metric | Effect [95% CI] | n |
|---|---|---|---|---|
| s-hi | v1.37.11 → v1.38.9 | bad_spec | +0.02 pt [-0.04, +0.09] | 8 |
| s-hi | v1.37.11 → v1.38.9 | be_bound | +0.07 pt [-0.10, +0.25] | 8 |
| s-hi | v1.37.11 → v1.38.9 | cycles_total | +1.24% [+0.78, +1.70] | 24 |
| s-hi | v1.37.11 → v1.38.9 | ev:br_misp_retired.all_branches | +1.01% [+0.10, +1.92] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:dsb2mite_switches.penalty_cycles | +13.02% [+11.71, +14.34] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:dtlb_load_misses.walk_duration | -3.40% [-10.35, +4.09] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:icache.misses | +1.18% [+0.09, +2.29] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:idq_uops_not_delivered.core | +0.15% [-1.21, +1.54] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:int_misc.recovery_cycles | -0.41% [-1.38, +0.57] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:itlb_misses.walk_completed | +13.02% [-7.58, +38.22] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:itlb_misses.walk_duration | +13.31% [+0.14, +28.21] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:mem_load_uops_retired.l1_miss | +1.68% [+1.33, +2.03] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:mem_load_uops_retired.l3_miss | +0.06% [-1.30, +1.44] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:uops_issued.any | +2.51% [+2.19, +2.84] | 8 |
| s-hi | v1.37.11 → v1.38.9 | ev:uops_retired.retire_slots | +2.45% [+2.27, +2.64] | 8 |
| s-hi | v1.37.11 → v1.38.9 | fe_bound | -0.35 pt [-0.70, -0.00] | 8 |
| s-hi | v1.37.11 → v1.38.9 | instructions_u | +3.92% [+3.90, +3.94] | 24 |
| s-hi | v1.37.11 → v1.38.9 | retiring | +0.26 pt [+0.13, +0.38] | 8 |
| s-hi | v1.38.9 → v1.40.2 | bad_spec | +0.15 pt [+0.07, +0.22] | 8 |
| s-hi | v1.38.9 → v1.40.2 | be_bound | -0.03 pt [-0.30, +0.23] | 8 |
| s-hi | v1.38.9 → v1.40.2 | cycles_total | +0.54% [-0.01, +1.09] | 24 |
| s-hi | v1.38.9 → v1.40.2 | ev:br_misp_retired.all_branches | +2.31% [+2.03, +2.59] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:dsb2mite_switches.penalty_cycles | -7.70% [-9.25, -6.13] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:dtlb_load_misses.walk_duration | +2.99% [-5.08, +11.74] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:icache.misses | +1.22% [-0.85, +3.33] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:idq_uops_not_delivered.core | +1.28% [-0.50, +3.10] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:int_misc.recovery_cycles | +4.69% [+3.64, +5.75] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:itlb_misses.walk_completed | -13.01% [-26.09, +2.39] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:itlb_misses.walk_duration | -4.30% [-16.63, +9.84] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:mem_load_uops_retired.l1_miss | +1.36% [+1.01, +1.71] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:mem_load_uops_retired.l3_miss | -1.62% [-2.86, -0.37] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:uops_issued.any | -3.77% [-4.21, -3.33] | 8 |
| s-hi | v1.38.9 → v1.40.2 | ev:uops_retired.retire_slots | -4.69% [-5.02, -4.36] | 8 |
| s-hi | v1.38.9 → v1.40.2 | fe_bound | +0.62 pt [+0.15, +1.09] | 8 |
| s-hi | v1.38.9 → v1.40.2 | instructions_u | -6.51% [-6.54, -6.48] | 24 |
| s-hi | v1.38.9 → v1.40.2 | retiring | -0.74 pt [-0.89, -0.58] | 8 |
| s-hi | v1.32.13 → v1.40.2 | bad_spec | +0.30 pt [+0.25, +0.35] | 8 |
| s-hi | v1.32.13 → v1.40.2 | be_bound | -0.78 pt [-1.00, -0.56] | 8 |
| s-hi | v1.32.13 → v1.40.2 | cycles_total | +2.03% [+1.56, +2.50] | 24 |
| s-hi | v1.32.13 → v1.40.2 | ev:br_misp_retired.all_branches | +9.05% [+8.37, +9.74] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:dsb2mite_switches.penalty_cycles | -6.58% [-7.96, -5.18] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:dtlb_load_misses.walk_duration | +11.11% [+2.33, +20.65] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:icache.misses | +3.77% [+2.80, +4.75] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:idq_uops_not_delivered.core | +4.72% [+3.07, +6.41] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:int_misc.recovery_cycles | +10.10% [+9.12, +11.09] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:itlb_misses.walk_completed | -0.32% [-8.55, +8.65] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:itlb_misses.walk_duration | +10.38% [-3.35, +26.06] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:mem_load_uops_retired.l1_miss | +1.90% [+1.48, +2.33] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:mem_load_uops_retired.l3_miss | -0.07% [-2.02, +1.91] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:uops_issued.any | -7.09% [-7.32, -6.85] | 8 |
| s-hi | v1.32.13 → v1.40.2 | ev:uops_retired.retire_slots | -8.99% [-9.13, -8.84] | 8 |
| s-hi | v1.32.13 → v1.40.2 | fe_bound | +2.09 pt [+1.69, +2.49] | 8 |
| s-hi | v1.32.13 → v1.40.2 | instructions_u | -12.28% [-12.31, -12.26] | 24 |
| s-hi | v1.32.13 → v1.40.2 | retiring | -1.61 pt [-1.76, -1.46] | 8 |
| s-hi | v1.37.11 → v1.40.2 | bad_spec | +0.17 pt [+0.13, +0.20] | 8 |
| s-hi | v1.37.11 → v1.40.2 | be_bound | +0.04 pt [-0.18, +0.27] | 8 |
| s-hi | v1.37.11 → v1.40.2 | cycles_total | +1.78% [+1.27, +2.29] | 24 |
| s-hi | v1.37.11 → v1.40.2 | ev:br_misp_retired.all_branches | +3.34% [+2.27, +4.42] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:dsb2mite_switches.penalty_cycles | +4.31% [+2.84, +5.80] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:dtlb_load_misses.walk_duration | -0.51% [-5.84, +5.12] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:icache.misses | +2.42% [+0.88, +3.98] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:idq_uops_not_delivered.core | +1.43% [+0.05, +2.83] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:int_misc.recovery_cycles | +4.26% [+3.62, +4.91] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:itlb_misses.walk_completed | -1.69% [-22.46, +24.65] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:itlb_misses.walk_duration | +8.43% [-5.02, +23.79] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:mem_load_uops_retired.l1_miss | +3.06% [+2.70, +3.43] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:mem_load_uops_retired.l3_miss | -1.56% [-3.42, +0.33] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:uops_issued.any | -1.35% [-1.59, -1.11] | 8 |
| s-hi | v1.37.11 → v1.40.2 | ev:uops_retired.retire_slots | -2.35% [-2.61, -2.10] | 8 |
| s-hi | v1.37.11 → v1.40.2 | fe_bound | +0.27 pt [-0.09, +0.63] | 8 |
| s-hi | v1.37.11 → v1.40.2 | instructions_u | -2.85% [-2.87, -2.82] | 24 |
| s-hi | v1.37.11 → v1.40.2 | retiring | -0.48 pt [-0.60, -0.36] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | bad_spec | -0.18 pt [-0.38, +0.02] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | be_bound | +0.16 pt [-0.16, +0.48] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | cycles_total | +1.61% [+1.09, +2.14] | 24 |
| fh-hi | v1.37.11 → v1.38.9 | ev:br_misp_retired.all_branches | -2.82% [-4.47, -1.13] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:dsb2mite_switches.penalty_cycles | -4.70% [-5.89, -3.50] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:dtlb_load_misses.walk_duration | -0.50% [-4.84, +4.05] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:icache.misses | +1.39% [+0.10, +2.70] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:idq_uops_not_delivered.core | +0.45% [-1.32, +2.26] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:int_misc.recovery_cycles | -2.33% [-6.54, +2.07] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:itlb_misses.walk_completed | +7.71% [-7.73, +25.74] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:itlb_misses.walk_duration | +5.34% [-6.26, +18.37] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:mem_load_uops_retired.l1_miss | +3.85% [+3.39, +4.31] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:mem_load_uops_retired.l3_miss | +1.07% [+0.28, +1.87] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:uops_issued.any | +4.84% [+4.56, +5.12] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | ev:uops_retired.retire_slots | +5.52% [+5.29, +5.75] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | fe_bound | -0.79 pt [-1.37, -0.21] | 8 |
| fh-hi | v1.37.11 → v1.38.9 | instructions_u | +6.92% [+6.90, +6.93] | 24 |
| fh-hi | v1.37.11 → v1.38.9 | retiring | +0.81 pt [+0.60, +1.02] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | bad_spec | +0.37 pt [+0.27, +0.46] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | be_bound | -0.52 pt [-0.77, -0.27] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | cycles_total | -4.40% [-4.89, -3.91] | 24 |
| fh-hi | v1.38.9 → v1.40.2 | ev:br_misp_retired.all_branches | +5.88% [+3.11, +8.72] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:dsb2mite_switches.penalty_cycles | -16.74% [-17.73, -15.74] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:dtlb_load_misses.walk_duration | +1.44% [-4.96, +8.27] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:icache.misses | +0.10% [-1.09, +1.31] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:idq_uops_not_delivered.core | -0.10% [-1.47, +1.28] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:int_misc.recovery_cycles | +5.60% [+2.67, +8.62] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:itlb_misses.walk_completed | -1.19% [-16.12, +16.39] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:itlb_misses.walk_duration | -0.74% [-10.42, +9.98] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:mem_load_uops_retired.l1_miss | -7.48% [-7.89, -7.07] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:mem_load_uops_retired.l3_miss | -0.18% [-1.01, +0.65] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:uops_issued.any | -14.46% [-14.57, -14.35] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | ev:uops_retired.retire_slots | -15.81% [-15.93, -15.70] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | fe_bound | +2.84 pt [+2.45, +3.23] | 8 |
| fh-hi | v1.38.9 → v1.40.2 | instructions_u | -18.72% [-18.73, -18.71] | 24 |
| fh-hi | v1.38.9 → v1.40.2 | retiring | -2.69 pt [-2.88, -2.49] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | bad_spec | +0.52 pt [+0.40, +0.63] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | be_bound | -1.04 pt [-1.27, -0.82] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | cycles_total | -7.16% [-7.79, -6.51] | 24 |
| fh-hi | v1.32.13 → v1.40.2 | ev:br_misp_retired.all_branches | +6.90% [+1.57, +12.51] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:dsb2mite_switches.penalty_cycles | -29.82% [-30.93, -28.70] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:dtlb_load_misses.walk_duration | +4.79% [-4.25, +14.69] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:icache.misses | +0.97% [-1.07, +3.05] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:idq_uops_not_delivered.core | +1.13% [-0.31, +2.59] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:int_misc.recovery_cycles | +7.41% [+3.93, +11.01] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:itlb_misses.walk_completed | -5.17% [-17.34, +8.79] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:itlb_misses.walk_duration | -0.26% [-8.79, +9.07] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:mem_load_uops_retired.l1_miss | -7.10% [-7.61, -6.58] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:mem_load_uops_retired.l3_miss | -0.86% [-1.62, -0.09] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:uops_issued.any | -23.65% [-23.75, -23.54] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | ev:uops_retired.retire_slots | -25.46% [-25.59, -25.34] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | fe_bound | +5.38 pt [+5.02, +5.74] | 8 |
| fh-hi | v1.32.13 → v1.40.2 | instructions_u | -28.74% [-28.75, -28.73] | 24 |
| fh-hi | v1.32.13 → v1.40.2 | retiring | -4.85 pt [-5.07, -4.64] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | bad_spec | +0.19 pt [+0.04, +0.33] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | be_bound | -0.36 pt [-0.55, -0.18] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | cycles_total | -2.86% [-3.34, -2.37] | 24 |
| fh-hi | v1.37.11 → v1.40.2 | ev:br_misp_retired.all_branches | +2.89% [-0.25, +6.14] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:dsb2mite_switches.penalty_cycles | -20.66% [-21.44, -19.87] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:dtlb_load_misses.walk_duration | +0.93% [-5.51, +7.82] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:icache.misses | +1.49% [-0.08, +3.10] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:idq_uops_not_delivered.core | +0.35% [-0.85, +1.56] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:int_misc.recovery_cycles | +3.14% [-0.31, +6.72] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:itlb_misses.walk_completed | +6.43% [-4.28, +18.34] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:itlb_misses.walk_duration | +4.56% [-4.91, +14.97] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:mem_load_uops_retired.l1_miss | -3.92% [-4.29, -3.55] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:mem_load_uops_retired.l3_miss | +0.88% [-0.10, +1.88] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:uops_issued.any | -10.32% [-10.50, -10.15] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | ev:uops_retired.retire_slots | -11.17% [-11.36, -10.97] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | fe_bound | +2.05 pt [+1.71, +2.39] | 8 |
| fh-hi | v1.37.11 → v1.40.2 | instructions_u | -13.10% [-13.11, -13.09] | 24 |
| fh-hi | v1.37.11 → v1.40.2 | retiring | -1.88 pt [-2.04, -1.71] | 8 |

