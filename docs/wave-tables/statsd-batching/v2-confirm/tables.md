
## v2c (base ctl-statsd): 32 legs recorded, 32 valid, 32 cells used

| Arm | legs | total k cyc/req | workers k | rest (main+other) k | datagrams/req | drop share | sent/flush | rate | busy |
|---|---|---|---|---|---|---|---|---|---|
| ctl-statsd | 8 | 615.7 | 596.6 | 19.1 | 4.212 | 0.0000 | 109268 | 5179 | 0.360 |
| v2-statsd-512 | 8 | 565.9 | 558.0 | 7.9 | 1.203 | 0.0000 | 31205 | 5181 | 0.332 |
| ctl-statsd-A2 | 8 | 614.6 | 595.1 | 19.5 | 4.212 | 0.0000 | 109275 | 5180 | 0.359 |
| ctl-nosink | 8 | 515.6 | 513.7 | 1.9 | - | - | - | 5181 | 0.305 |

- v2-statsd-512 vs ctl-statsd, total: -8.09%, t [-9.20, -6.98], widened (method) [-9.19, -6.98], wider of the two [-9.20, -6.98] (n 8)
- v2-statsd-512 vs ctl-statsd, workers: -6.47%, t [-7.61, -5.33], widened (method) [-7.60, -5.33], wider of the two [-7.61, -5.33] (n 8)
- v2-statsd-512 vs ctl-statsd, rest: -58.71%, t [-59.47, -57.95], widened (method) [-59.39, -58.02], wider of the two [-59.47, -57.95] (n 8)
- ctl-statsd-A2 vs ctl-statsd, total: -0.19%, t [-0.72, +0.34], widened (method) [-0.98, +0.61], wider of the two [-0.98, +0.61] (n 8)
- ctl-statsd-A2 vs ctl-statsd, workers: -0.25%, t [-0.79, +0.29], widened (method) [-1.05, +0.55], wider of the two [-1.05, +0.55] (n 8)
- ctl-statsd-A2 vs ctl-statsd, rest: +1.84%, t [-0.38, +4.11], widened (method) [-0.12, +3.84], wider of the two [-0.38, +4.11] (n 8)
- ctl-nosink vs ctl-statsd, total: -16.26%, t [-16.64, -15.88], widened (method) [-16.90, -15.62], wider of the two [-16.90, -15.62] (n 8)
- ctl-nosink vs ctl-statsd, workers: -13.90%, t [-14.30, -13.50], widened (method) [-14.56, -13.23], wider of the two [-14.56, -13.23] (n 8)
- ctl-nosink vs ctl-statsd, rest: -90.04%, t [-90.34, -89.73], widened (method) [-90.30, -89.78], wider of the two [-90.34, -89.73] (n 8)
- ctl-statsd vs ctl-nosink, total: +19.42%, t [+18.87, +19.97], widened (method) [+18.51, +20.34], wider of the two [+18.51, +20.34] (n 8)
- ctl-statsd vs ctl-nosink, workers: +16.14%, t [+15.60, +16.69], widened (method) [+15.25, +17.04], wider of the two [+15.25, +17.04] (n 8)
- ctl-statsd vs ctl-nosink, rest: +904.01%, t [+873.90, +935.05], widened (method) [+878.15, +930.56], wider of the two [+873.90, +935.05] (n 8)
- v2-statsd-512 vs ctl-nosink, total: +9.75%, t [+8.59, +10.93], widened (method) [+8.54, +10.98], wider of the two [+8.54, +10.98] (n 8)
- v2-statsd-512 vs ctl-nosink, workers: +8.63%, t [+7.46, +9.80], widened (method) [+7.42, +9.84], wider of the two [+7.42, +9.84] (n 8)
- v2-statsd-512 vs ctl-nosink, rest: +314.51%, t [+297.07, +332.73], widened (method) [+299.76, +329.82], wider of the two [+297.07, +332.73] (n 8)
- ctl-statsd-A2 vs ctl-nosink, total: +19.19%, t [+18.60, +19.79], widened (method) [+18.26, +20.13], wider of the two [+18.26, +20.13] (n 8)
- ctl-statsd-A2 vs ctl-nosink, workers: +15.85%, t [+15.25, +16.45], widened (method) [+14.93, +16.77], wider of the two [+14.93, +16.77] (n 8)
- ctl-statsd-A2 vs ctl-nosink, rest: +922.49%, t [+880.18, +966.63], widened (method) [+886.68, +959.61], wider of the two [+880.18, +966.63] (n 8)
