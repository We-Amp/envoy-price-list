extproc: 48 legs, 48 valid
xds-small-s: 48 legs, 48 valid

| arm | arm cycles/req | effect (cycles/req) [95%] | widened ± | added cycles per request | user | kernel | workers | main | other threads | worker busy max | service CPU us/req |
|---|---|---|---|---|---|---|---|---|---|---|---|
| off-A2 | 526.53k ±8.39 | -0.09% [-1.79, +1.65] | 1.47 | -0.47k ±9.11 | -0.59k ±5.66 | +0.11k ±4.20 | -0.47k ±9.11 | -0.00k ±0.00 | +0.00k ±0.00 | 0.3203 | +62.88 ±3.68 |
| authz-grpc | 949.51k ±6.01 | +80.19% [+77.05, +83.39] | 1.50 | +422.51k ±10.07 | +348.53k ±6.08 | +73.97k ±4.82 | +422.50k ±10.07 | +0.00k ±0.00 | -0.00k ±0.00 | 0.5573 | +131.39 ±9.53 |
| xp-default | 1052.55k ±19.20 | +99.72% [+93.79, +105.84] | 2.39 | +525.55k ±24.54 | +411.44k ±11.41 | +114.10k ±13.44 | +525.55k ±24.55 | -0.00k ±0.00 | -0.00k ±0.00 | 0.6295 | +319.00 ±4.56 |
| xp-reqhdr | 943.07k ±9.97 | +78.96% [+76.30, +81.67] | 1.32 | +416.07k ±9.26 | +332.22k ±4.87 | +83.85k ±6.46 | +416.07k ±9.27 | +0.00k ±0.00 | -0.00k ±0.00 | 0.5533 | +263.59 ±2.41 |
| authz-grpc-google | 1319.09k ±17.47 | +150.31% [+145.08, +155.66] | 1.74 | +792.09k ±19.03 | +477.97k ±8.63 | +314.11k ±10.57 | +383.10k ±13.27 | +0.01k ±0.00 | +408.98k ±8.08 | 0.5448 | +123.76 ±5.58 |
| xp-default-google | 1408.75k ±4.09 | +167.35% [+162.07, +172.73] | 1.66 | +881.75k ±12.61 | +548.03k ±8.03 | +333.71k ±5.08 | +439.44k ±11.51 | +0.00k ±0.00 | +442.30k ±1.84 | 0.5726 | +318.18 ±1.75 |
| xp-reqhdr-google | 1334.18k ±7.25 | +153.19% [+147.60, +158.92] | 1.83 | +807.18k ±15.79 | +472.73k ±7.63 | +334.45k ±8.26 | +403.59k ±13.90 | +0.01k ±0.00 | +403.59k ±3.35 | 0.5539 | +287.76 ±1.40 |

Service CPU: the ext_proc container's cgroup for xp-* arms, the origin container (nginx: origin plus the ext_authz gRPC service) otherwise; exploratory, outside Envoy's number.

Direct pairs:
| comparison | effect [95%] (ratio) | widened ± (log-%) | Δ cycles/req | Δ workers | Δ other threads |
|---|---|---|---|---|---|
| xp-default against xp-reqhdr | +11.60% [+9.36, +13.89] | 1.69 | +109.48k ±20.86 | +109.48k ±20.86 | -0.00k ±0.00 |
| xp-default against authz-grpc | +10.84% [+8.94, +12.77] | 1.48 | +103.04k ±18.23 | +103.04k ±18.23 | -0.00k ±0.00 |
| xp-reqhdr against authz-grpc | -0.68% [-1.77, +0.42] | 1.07 | -6.44k ±10.33 | -6.44k ±10.33 | +0.00k ±0.00 |
| authz-grpc-google against authz-grpc | +38.92% [+37.13, +40.73] | 1.19 | +369.58k ±16.69 | -39.40k ±9.36 | +408.98k ±8.08 |
| xp-default-google against xp-default | +33.86% [+31.53, +36.22] | 1.49 | +356.20k ±18.27 | -86.11k ±18.73 | +442.31k ±1.85 |
| xp-reqhdr-google against xp-reqhdr | +41.48% [+39.72, +43.26] | 1.16 | +391.11k ±13.04 | -12.48k ±12.62 | +403.59k ±3.35 |
| xp-default-google against xp-reqhdr-google | +5.59% [+5.16, +6.02] | 0.73 | +74.57k ±5.38 | +35.85k ±4.79 | +38.72k ±2.93 |

authz-grpc: dog:workers_gua 0.0k, dog:main_thread 0.0k, grpc_global_tim 0.0k
authz-grpc-google: event_engine 307.0k, GrpcGoogClient 101.9k, dog:main_thread 0.0k, dog:workers_gua 0.0k, lifeguard 0.0k, grpc_global_tim 0.0k
off: dog:workers_gua 0.0k, dog:main_thread 0.0k, grpc_global_tim 0.0k
off-A2: dog:main_thread 0.0k, dog:workers_gua 0.0k, grpc_global_tim 0.0k
xp-default: dog:main_thread 0.0k, dog:workers_gua 0.0k, grpc_global_tim 0.0k
xp-default-google: event_engine 328.8k, GrpcGoogClient 113.5k, dog:main_thread 0.0k, dog:workers_gua 0.0k, lifeguard 0.0k, grpc_global_tim 0.0k
xp-reqhdr: dog:workers_gua 0.0k, dog:main_thread 0.0k, grpc_global_tim 0.0k
xp-reqhdr-google: event_engine 296.7k, GrpcGoogClient 106.8k, dog:workers_gua 0.0k, dog:main_thread 0.0k, lifeguard 0.0k, grpc_global_tim 0.0k

| run | shape | arm | pairs | upd/window | main cycles/update | workers | other | total | accepts/update | main busy max | per-request effect |
|---|---|---|---|---|---|---|---|---|---|---|---|
| xds-small-s | s | cds | 6 | 20 | +12.60M ±0.04 | +11.46M ±41.76 | -0.01M ±0.01 | +24.06M ±41.77 | +0.00 ±0.00 | 0.007 | +0.87% ±1.52 |
| xds-small-s | s | cds-active | 6 | 20 | +12.70M ±0.09 | -14.23M ±20.17 | +0.01M ±0.02 | -1.53M ±20.22 | +9.89 ±0.64 | 0.006 | -0.05% ±0.74 |
| xds-small-s | s | cds-same | 6 | 20 | +10.98M ±0.10 | +7.53M ±33.35 | -0.00M ±0.02 | +18.50M ±33.35 | +0.00 ±0.00 | 0.006 | +0.67% ±1.21 |
| xds-small-s | s | eds | 6 | 20 | +3.59M ±0.03 | -0.63M ±26.32 | -0.01M ±0.01 | +2.96M ±26.33 | +0.00 ±0.00 | 0.003 | +0.11% ±0.96 |
| xds-small-s | s | rds | 6 | 20 | +12.68M ±0.05 | -5.94M ±36.96 | -0.00M ±0.02 | +6.74M ±36.92 | +0.00 ±0.00 | 0.007 | +0.25% ±1.35 |
| xds-small-s | s | rds-same | 6 | 20 | +11.58M ±0.04 | +15.78M ±37.08 | +0.00M ±0.01 | +27.35M ±37.10 | +0.00 ±0.00 | 0.006 | +0.99% ±1.34 |
| xds-small-s | s | ref-A2 | 6 | 20 | -0.01M ±0.01 | +13.94M ±12.30 | -0.00M ±0.02 | +13.92M ±12.31 | +0.00 ±0.00 | 0.001 | +0.51% ±0.45 |

The A/A row (ref-A2) is the floor: a per-update price inside its interval is not a finding.
