
## b-statsd (base ctl-statsd): 18 legs recorded, 18 valid, 18 cells used

| Arm | legs | total k cyc/req | workers k | rest (main+other) k | datagrams/req | drop share | sent/flush | rate | busy |
|---|---|---|---|---|---|---|---|---|---|
| ctl-statsd | 6 | 614.5 | 595.1 | 19.4 | 4.211 | 0.0000 | 109295 | 5180 | 0.359 |
| p1-statsd | 6 | 574.5 | 556.5 | 18.0 | 2.201 | 0.0000 | 55206 | 5180 | 0.337 |
| ctl-statsd-A2 | 6 | 616.1 | 596.4 | 19.7 | 4.212 | 0.0000 | 109290 | 5180 | 0.360 |

- p1-statsd vs ctl-statsd, total: -6.51%, t [-7.87, -5.14], widened (method) [-7.72, -5.29], wider of the two [-7.87, -5.14] (n 6)
- p1-statsd vs ctl-statsd, workers: -6.49%, t [-7.86, -5.09], widened (method) [-7.71, -5.25], wider of the two [-7.86, -5.09] (n 6)
- p1-statsd vs ctl-statsd, rest: -7.29%, t [-9.90, -4.60], widened (method) [-9.38, -5.15], wider of the two [-9.90, -4.60] (n 6)
- ctl-statsd-A2 vs ctl-statsd, total: +0.26%, t [-0.46, +0.98], widened (method) [-0.60, +1.13], wider of the two [-0.60, +1.13] (n 6)
- ctl-statsd-A2 vs ctl-statsd, workers: +0.22%, t [-0.48, +0.94], widened (method) [-0.63, +1.09], wider of the two [-0.63, +1.09] (n 6)
- ctl-statsd-A2 vs ctl-statsd, rest: +1.35%, t [-4.43, +7.49], widened (method) [-3.14, +6.05], wider of the two [-4.43, +7.49] (n 6)

## b-statsd-nosink (base ctl-statsd): 32 legs recorded, 32 valid, 32 cells used

| Arm | legs | total k cyc/req | workers k | rest (main+other) k | datagrams/req | drop share | sent/flush | rate | busy |
|---|---|---|---|---|---|---|---|---|---|
| ctl-statsd | 8 | 615.6 | 595.9 | 19.6 | 4.214 | 0.0000 | 109334 | 5179 | 0.359 |
| p1-statsd | 8 | 575.9 | 557.9 | 18.0 | 2.201 | 0.0000 | 57106 | 5179 | 0.338 |
| ctl-statsd-A2 | 8 | 613.7 | 594.4 | 19.4 | 4.212 | 0.0000 | 106545 | 5179 | 0.358 |
| ctl-nosink | 8 | 518.4 | 516.5 | 1.9 | - | - | - | 5181 | 0.307 |

- p1-statsd vs ctl-statsd, total: -6.44%, t [-6.90, -5.97], widened (method) [-7.17, -5.70], wider of the two [-7.17, -5.70] (n 8)
- p1-statsd vs ctl-statsd, workers: -6.37%, t [-6.81, -5.94], widened (method) [-7.09, -5.65], wider of the two [-7.09, -5.65] (n 8)
- p1-statsd vs ctl-statsd, rest: -8.34%, t [-10.42, -6.20], widened (method) [-10.17, -6.47], wider of the two [-10.42, -6.20] (n 8)
- ctl-statsd-A2 vs ctl-statsd, total: -0.30%, t [-0.71, +0.12], widened (method) [-1.04, +0.46], wider of the two [-1.04, +0.46] (n 8)
- ctl-statsd-A2 vs ctl-statsd, workers: -0.26%, t [-0.73, +0.21], widened (method) [-1.03, +0.51], wider of the two [-1.03, +0.51] (n 8)
- ctl-statsd-A2 vs ctl-statsd, rest: -1.30%, t [-4.02, +1.50], widened (method) [-3.65, +1.11], wider of the two [-4.02, +1.50] (n 8)
- ctl-nosink vs ctl-statsd, total: -15.79%, t [-16.70, -14.87], widened (method) [-16.73, -14.84], wider of the two [-16.73, -14.84] (n 8)
- ctl-nosink vs ctl-statsd, workers: -13.34%, t [-14.29, -12.37], widened (method) [-14.32, -12.35], wider of the two [-14.32, -12.35] (n 8)
- ctl-nosink vs ctl-statsd, rest: -90.29%, t [-90.75, -89.82], widened (method) [-90.68, -89.90], wider of the two [-90.75, -89.82] (n 8)
- ctl-statsd vs ctl-nosink, total: +18.75%, t [+17.46, +20.05], widened (method) [+17.42, +20.09], wider of the two [+17.42, +20.09] (n 8)
- ctl-statsd vs ctl-nosink, workers: +15.39%, t [+14.11, +16.68], widened (method) [+14.08, +16.71], wider of the two [+14.08, +16.71] (n 8)
- ctl-statsd vs ctl-nosink, rest: +930.35%, t [+882.30, +980.75], widened (method) [+889.81, +972.55], wider of the two [+882.30, +980.75] (n 8)
- p1-statsd vs ctl-nosink, total: +11.11%, t [+10.25, +11.97], widened (method) [+10.08, +12.14], wider of the two [+10.08, +12.14] (n 8)
- p1-statsd vs ctl-nosink, workers: +8.03%, t [+7.16, +8.92], widened (method) [+7.01, +9.07], wider of the two [+7.01, +9.07] (n 8)
- p1-statsd vs ctl-nosink, rest: +844.45%, t [+805.48, +885.11], widened (method) [+811.46, +878.64], wider of the two [+805.48, +885.11] (n 8)
- ctl-statsd-A2 vs ctl-nosink, total: +18.40%, t [+17.43, +19.38], widened (method) [+17.28, +19.53], wider of the two [+17.28, +19.53] (n 8)
- ctl-statsd-A2 vs ctl-nosink, workers: +15.09%, t [+14.15, +16.03], widened (method) [+14.00, +16.19], wider of the two [+14.00, +16.19] (n 8)
- ctl-statsd-A2 vs ctl-nosink, rest: +917.00%, t [+881.37, +953.92], widened (method) [+886.65, +948.28], wider of the two [+881.37, +953.92] (n 8)

## b-fl (base ctl): 18 legs recorded, 18 valid, 18 cells used

| Arm | legs | total k cyc/req | workers k | rest (main+other) k | datagrams/req | drop share | sent/flush | rate | busy |
|---|---|---|---|---|---|---|---|---|---|
| ctl | 6 | 855.8 | 855.4 | 0.5 | - | - | - | 2000 | 0.196 |
| p2 | 6 | 851.5 | 851.0 | 0.5 | - | - | - | 2000 | 0.195 |
| ctl-A2 | 6 | 858.2 | 857.7 | 0.5 | - | - | - | 2000 | 0.197 |

- p2 vs ctl, total: -0.51%, t [-1.57, +0.56], widened (method) [-1.55, +0.55], wider of the two [-1.57, +0.56] (n 6)
- p2 vs ctl, workers: -0.51%, t [-1.57, +0.56], widened (method) [-1.56, +0.55], wider of the two [-1.57, +0.56] (n 6)
- p2 vs ctl, rest: +0.44%, t [-2.80, +3.79], widened (method) [-2.13, +3.08], wider of the two [-2.80, +3.79] (n 6)
- ctl-A2 vs ctl, total: +0.28%, t [-0.55, +1.12], widened (method) [-0.64, +1.21], wider of the two [-0.64, +1.21] (n 6)
- ctl-A2 vs ctl, workers: +0.28%, t [-0.55, +1.12], widened (method) [-0.64, +1.21], wider of the two [-0.64, +1.21] (n 6)
- ctl-A2 vs ctl, rest: +2.22%, t [-0.65, +5.17], widened (method) [-0.07, +4.56], wider of the two [-0.65, +5.17] (n 6)
