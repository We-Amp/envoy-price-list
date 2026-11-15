Matrix Holm family: 15 primary rows

| Row | Shape @ rps | Arm vs base | Total cycles/req [95% CI] | Holm p (matrix) | A/A hw | Instructions:u/req | p50 | p99 | Base cyc/req | Arm cyc/req | Base busy | n | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tls-cert | tls-hs @ 2800 | ecdsa-p256 vs rsa2048 | -18.01% [-18.26, -17.76] | <0.001 | - | -63.54% [-63.54, -63.53] | -0.35% [-0.72, +0.03] | -91.84% [-92.85, -90.69] | 934.1k | 765.6k | 29.7% | 12 | differs |
| tls-cert | tls-ka @ 4800 | ecdsa-p256 vs rsa2048 | -0.35% [-1.22, +0.52] | 0.391 | - | -0.11% [-0.18, -0.05] | -2.47% [-4.49, -0.40] | -21.65% [-27.65, -15.14] | 559.8k | 558.8k | 30.5% | 12 | not resolved |
| tls-resumption | tls-hs @ 2800 | resumption-on vs resumption-off | -18.59% [-19.30, -17.87] | <0.001 | - | -62.99% [-62.99, -62.98] | -0.30% [-1.12, +0.52] | -85.79% [-88.56, -82.34] | 935.4k | 762.0k | 29.7% | 12 | differs |
| hpack | fh2 @ 8000 | hpack-0 vs hpack-default | +7.14% [+5.45, +8.86] | <0.001 | - | +33.49% [+33.46, +33.51] | +10.33% [+5.12, +15.81] | +8.99% [+4.28, +13.92] | 362.4k | 390.2k | 32.7% | 24 | differs |
| tracing | s @ 5200 | sampling-0 vs no-tracer | +6.71% [+6.17, +7.26] | <0.001 | 0.56 | +13.02% [+12.99, +13.05] | +7.31% [+5.56, +9.09] | +12.11% [+8.71, +15.62] | 525.4k | 561.0k | 31.3% | 16 | differs |
| tracing | s @ 5200 | sampling-1 vs no-tracer | +7.00% [+6.47, +7.53] | <0.001 | 0.56 | +13.86% [+13.83, +13.90] | +5.84% [+4.60, +7.09] | +15.37% [+11.66, +19.21] | 525.4k | 562.7k | 31.3% | 16 | differs |
| tracing | s @ 5200 | sampling-100 vs no-tracer | +33.77% [+33.20, +34.34] | <0.001 | 0.56 | +92.30% [+92.26, +92.34] | +22.92% [+21.25, +24.61] | +68.69% [+61.06, +76.69] | 525.4k | 703.9k | 31.3% | 16 | differs |
| access-log | s @ 5200 | log-text vs log-off | +3.61% [+2.74, +4.49] | <0.001 | 0.56 | +4.07% [+4.03, +4.10] | +3.07% [+1.33, +4.85] | +5.44% [+1.61, +9.42] | 526.3k | 546.0k | 31.2% | 12 | differs |
| access-log | s @ 5200 | log-json vs log-off | +4.52% [+3.82, +5.21] | <0.001 | 0.56 | +5.97% [+5.94, +6.00] | +3.38% [+0.87, +5.95] | +4.15% [+1.42, +6.96] | 526.3k | 549.4k | 31.2% | 12 | differs |
| ext-authz | s @ 5200 | authz-http vs authz-off | +54.02% [+52.88, +55.16] | <0.001 | 0.56 | +74.95% [+74.87, +75.04] | +75.39% [+68.52, +82.53] | +205.63% [+165.62, +251.66] | 526.9k | 810.3k | 31.3% | 12 | differs |
| retries | s @ 5200 | retry-policy vs no-retry-policy | +1.50% [+0.85, +2.16] | 0.001 | 0.56 | +1.21% [+1.17, +1.24] | +1.75% [+0.66, +2.85] | +0.71% [-0.65, +2.10] | 527.5k | 535.8k | 31.3% | 12 | differs |
| buffer-limit | m @ 5440 | buffer-4k vs buffer-default | +20.09% [+19.34, +20.84] | <0.001 | 0.54 | +9.30% [+9.24, +9.36] | +18.76% [+16.55, +21.01] | +68.89% [+42.67, +99.92] | 537.7k | 645.5k | 33.2% | 12 | differs |
| tcmalloc-percpu | fh @ 8000 | rseq-off vs tcmalloc-default | +1.58% [+0.32, +2.85] | 0.054 | 0.94 | -19.23% [-19.32, -19.15] | +1.13% [+0.04, +2.24] | +0.94% [+0.12, +1.76] | 279.2k | 281.7k | 25.3% | 12 | differs |
| tcmalloc-percpu | s @ 5200 | rseq-off vs tcmalloc-default | -0.88% [-1.69, -0.07] | 0.071 | 0.56 | -10.21% [-10.25, -10.16] | -2.65% [-4.11, -1.16] | -2.07% [-4.41, +0.33] | 528.0k | 522.3k | 31.3% | 12 | differs, inside the A/A interval |
| two-hop | s @ 5200 | two-hop vs one-hop | -8.14% [-9.28, -6.98] | <0.001 | - | +106.12% [+105.89, +106.36] | +105.13% [+89.11, +122.51] | +96.01% [+80.54, +112.80] | 525.4k | 485.6k | 31.2% | 12 | differs |

Evidence (means over valid legs, arm / base):
- tls-cert tls-hs ecdsa-p256: busy 0.2474 / 0.2969; ctx_switches_per_req 2.025 / 1.697; eff_ghz 2.168 / 2.202; handshakes_per_req 0.1004 / 0.1004; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2544 / 0.2521
- tls-cert tls-ka ecdsa-p256: busy 0.3046 / 0.3053; ctx_switches_per_req 1.518 / 1.482; eff_ghz 2.199 / 2.201; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2576 / 0.2551
- tls-resumption tls-hs resumption-on: busy 0.2454 / 0.2971; ctx_switches_per_req 1.971 / 1.705; eff_ghz 2.172 / 2.203; handshakes_per_req 0.1004 / 0.1004; resumed_share 1 / -; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.258 / 0.2522
- hpack fh2 hpack-0: busy 0.3491 / 0.3266; ctx_switches_per_req 0.8355 / 0.8287; eff_ghz 2.226 / 2.221; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2745 / 0.2852
- tracing s sampling-0: busy 0.3313 / 0.3127; ctx_switches_per_req 1.559 / 1.616; eff_ghz 2.204 / 2.188; not_traced_per_req 1 / -; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2534 / 0.2534
- tracing s sampling-1: busy 0.3322 / 0.3127; ctx_switches_per_req 1.557 / 1.616; eff_ghz 2.204 / 2.188; not_traced_per_req 0.9899 / -; sampled_per_req 0.01007 / -; spans_sent_per_req 0.01007 / -; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2537 / 0.2534
- tracing s sampling-100: busy 0.4106 / 0.3127; ctx_switches_per_req 1.59 / 1.616; eff_ghz 2.229 / 2.188; sampled_per_req 1 / -; spans_sent_per_req 1 / -; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.253 / 0.2534
- access-log s log-text: access_log_bytes_per_line 144 / -; access_log_lines_per_measured_req 1 / -; busy 0.3227 / 0.3123; ctx_switches_per_req 1.575 / 1.591; eff_ghz 2.198 / 2.192; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.254 / 0.2533
- access-log s log-json: access_log_bytes_per_line 366 / -; access_log_lines_per_measured_req 1 / -; busy 0.3252 / 0.3123; ctx_switches_per_req 1.583 / 1.591; eff_ghz 2.2 / 2.192; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2533 / 0.2533
- ext-authz s authz-http: authz_ok_per_req 1 / -; busy 0.4722 / 0.3126; ctx_switches_per_req 1.746 / 1.582; eff_ghz 2.237 / 2.194; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2542 / 0.2533
- retries s retry-policy: busy 0.3175 / 0.3134; ctx_switches_per_req 1.606 / 1.613; eff_ghz 2.192 / 2.187; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2542 / 0.2535
- buffer-limit m buffer-4k: busy 0.3927 / 0.3319; ctx_switches_per_req 1.332 / 1.564; eff_ghz 2.236 / 2.203; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2545 / 0.2537
- tcmalloc-percpu fh rseq-off: busy 0.2565 / 0.2527; ctx_switches_per_req 0.8384 / 0.8454; eff_ghz 2.202 / 2.201; tcmalloc_percpu_slab_bytes 2.622e+06 / 0; worker_max_share 0.2565 / 0.2566
- tcmalloc-percpu s rseq-off: busy 0.311 / 0.3134; ctx_switches_per_req 1.635 / 1.598; eff_ghz 2.186 / 2.189; tcmalloc_percpu_slab_bytes 2.622e+06 / 0; worker_max_share 0.2547 / 0.2552
- two-hop s two-hop: busy 0.2966 / 0.3116; ctx_switches_per_req 1.564 / 1.591; eff_ghz 2.207 / 2.191; hop1_cycles_total 5.034e+05 / -; hop2_cycles_total 4.613e+05 / -; tcmalloc_percpu_slab_bytes 0 / 0; worker_max_share 0.2524 / 0.2538

Runs:
- 01-tls-cert: 12 rounds (widest cycles_total half-width 0.87% (tls-ka ecdsa-p256 vs rsa2048) <= target 1.50%), 48 legs, 0 invalid; 2026-11-14T07:10:09Z to 2026-11-14T07:41:21Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
- 02-tls-resumption: 12 rounds (widest cycles_total half-width 0.88% (tls-hs resumption-on vs resumption-off) <= target 1.50%), 24 legs, 0 invalid; 2026-11-14T07:41:22Z to 2026-11-14T07:57:04Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
- 03-hpack: 24 rounds (cap of 24 rounds reached; widest cycles_total half-width 1.59% (fh2 hpack-0 vs hpack-default) > target 1.50%), 48 legs, 0 invalid; 2026-11-14T07:57:04Z to 2026-11-14T08:27:16Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
- 04-tracing: 16 rounds (widest cycles_total half-width 0.51% (s sampling-0 vs no-tracer) <= target 1.50%), 64 legs, 0 invalid; 2026-11-14T08:27:16Z to 2026-11-14T09:08:29Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
- 05-access-log: 12 rounds (widest cycles_total half-width 0.85% (s log-text vs log-off) <= target 1.50%), 36 legs, 0 invalid; 2026-11-14T09:08:29Z to 2026-11-14T09:31:44Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
- 06-ext-authz: 12 rounds (widest cycles_total half-width 0.74% (s authz-http vs authz-off) <= target 1.50%), 24 legs, 0 invalid; 2026-11-14T09:31:44Z to 2026-11-14T09:47:16Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
- 07-retries: 12 rounds (widest cycles_total half-width 0.64% (s retry-policy vs no-retry-policy) <= target 1.50%), 24 legs, 0 invalid; 2026-11-14T09:47:17Z to 2026-11-14T10:02:47Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
- 08-buffer-limit: 12 rounds (widest cycles_total half-width 0.63% (m buffer-4k vs buffer-default) <= target 1.50%), 24 legs, 0 invalid; 2026-11-14T10:02:47Z to 2026-11-14T10:18:19Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
- 09-tcmalloc-percpu: 12 rounds (widest cycles_total half-width 1.24% (fh rseq-off vs tcmalloc-default) <= target 1.50%), 48 legs, 0 invalid; 2026-11-14T10:18:19Z to 2026-11-14T10:49:11Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
- 10-two-hop: 12 rounds (widest cycles_total_per_hop half-width 1.25% (s two-hop vs one-hop) <= target 1.50%), 24 legs, 0 invalid; 2026-11-14T10:49:12Z to 2026-11-14T11:04:47Z; idle states intel_idle/menu; disabled: C3, unchanged True; harness 0.1.0 7e3abbe874af
