# pilot-releases

- Harness: 0.1.0 279b1f3dd943
- Window: 2026-11-13T19:17:06Z to 2026-11-13T19:51:50Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz) 2300000
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3,40-43
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 6, order abba; base arm v1.32.13; alpha 0.05

| Arm | Version | md5 |
|---|---|---|
| v1.32.13 | 0c686a2237a51b1a07cdc4911dcf90c75f02f82d/1.32.13/Clean/RELEASE/BoringSSL | `dfd8f773a8dbfc0aeb97139e2fbf0f1a` |
| v1.36.13 | eb0a95ba450a3e29a9a8e75f672e2c294493eea2/1.36.13/Clean/RELEASE/BoringSSL | `da94b2d687fd73fe9ae3e746297c8909` |
| v1.40.2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 6/6 | 185.7k | 334.3k | 173.7k | 504.9k | 417 | 606 | 29.7% |
| v1.36.13 | 6/6 | 168.0k | 338.6k | 177.3k | 515.9k | 405 | 585 | 30.5% |
| v1.40.2 | 6/6 | 163.1k | 337.2k | 168.6k | 505.8k | 428 | 694 | 29.8% |

| Arm vs v1.32.13 | metric | delta mean | delta median | won | sign p | Wilcoxon p | differs |
|---|---|---|---|---|---|---|---|
| v1.36.13 | instructions:u / req | -9.54% | -9.53% | 6/6 | 0.031 | 0.031 | yes |
| v1.36.13 | cycles:u / req | +1.08% | +1.29% | 3/6 | 1.000 | 0.438 | no |
| v1.36.13 | cycles:k / req | +3.55% | +2.07% | 2/6 | 0.688 | 0.312 | no |
| v1.36.13 | cycles (u+k) / req | +1.92% | +2.19% | 3/6 | 1.000 | 0.438 | no |
| v1.36.13 | p50 latency (us) | +1.01% | -2.99% | 3/6 | 1.000 | 1.000 | no |
| v1.36.13 | p99 latency (us) | -0.70% | -3.43% | 3/6 | 1.000 | 1.000 | no |
| v1.40.2 | instructions:u / req | -12.20% | -12.17% | 6/6 | 0.031 | 0.031 | yes |
| v1.40.2 | cycles:u / req | +1.44% | +0.87% | 2/6 | 0.688 | 0.688 | no |
| v1.40.2 | cycles:k / req | -1.14% | -2.95% | 3/6 | 1.000 | 1.000 | no |
| v1.40.2 | cycles (u+k) / req | +0.56% | +0.18% | 2/6 | 0.688 | 0.562 | no |
| v1.40.2 | p50 latency (us) | +6.15% | +2.56% | 3/6 | 1.000 | 0.562 | no |
| v1.40.2 | p99 latency (us) | +16.56% | +14.70% | 0/6 | 0.031 | 0.031 | yes |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 6/6 | 230.3k | 206.8k | 73.8k | 277.7k | 215 | 388 | 25.1% |
| v1.36.13 | 6/6 | 189.1k | 190.8k | 75.0k | 265.3k | 204 | 370 | 24.2% |
| v1.40.2 | 6/6 | 164.1k | 185.0k | 75.8k | 261.1k | 201 | 351 | 23.5% |

| Arm vs v1.32.13 | metric | delta mean | delta median | won | sign p | Wilcoxon p | differs |
|---|---|---|---|---|---|---|---|
| v1.36.13 | instructions:u / req | -17.91% | -17.92% | 6/6 | 0.031 | 0.031 | yes |
| v1.36.13 | cycles:u / req | -6.90% | -7.74% | 5/6 | 0.219 | 0.094 | no |
| v1.36.13 | cycles:k / req | +3.13% | +1.72% | 3/6 | 1.000 | 0.438 | no |
| v1.36.13 | cycles (u+k) / req | -4.28% | -4.46% | 5/6 | 0.219 | 0.438 | no |
| v1.36.13 | p50 latency (us) | -4.42% | -4.80% | 5/6 | 0.219 | 0.062 | no |
| v1.36.13 | p99 latency (us) | -7.01% | -4.53% | 6/6 | 0.031 | 0.031 | yes |
| v1.40.2 | instructions:u / req | -28.73% | -28.74% | 6/6 | 0.031 | 0.031 | yes |
| v1.40.2 | cycles:u / req | -10.94% | -10.55% | 6/6 | 0.031 | 0.031 | yes |
| v1.40.2 | cycles:k / req | +3.22% | +2.79% | 0/6 | 0.031 | 0.031 | yes |
| v1.40.2 | cycles (u+k) / req | -7.24% | -5.98% | 6/6 | 0.031 | 0.031 | yes |
| v1.40.2 | p50 latency (us) | -6.22% | -6.34% | 6/6 | 0.031 | 0.031 | yes |
| v1.40.2 | p99 latency (us) | -10.19% | -9.58% | 6/6 | 0.031 | 0.031 | yes |

## m (`/m`, proxied, 5440 rps)

Medians over valid legs.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| v1.32.13 | 6/6 | 189.2k | 340.2k | 185.3k | 525.1k | 472 | 698 | 32.1% |
| v1.36.13 | 6/6 | 170.9k | 331.7k | 179.6k | 511.3k | 485 | 764 | 31.2% |
| v1.40.2 | 6/6 | 166.4k | 342.5k | 186.0k | 529.0k | 433 | 649 | 32.2% |

| Arm vs v1.32.13 | metric | delta mean | delta median | won | sign p | Wilcoxon p | differs |
|---|---|---|---|---|---|---|---|
| v1.36.13 | instructions:u / req | -9.59% | -9.67% | 6/6 | 0.031 | 0.031 | yes |
| v1.36.13 | cycles:u / req | -2.44% | -2.50% | 3/6 | 1.000 | 0.562 | no |
| v1.36.13 | cycles:k / req | -2.57% | -3.11% | 4/6 | 0.688 | 0.438 | no |
| v1.36.13 | cycles (u+k) / req | -2.49% | -2.64% | 5/6 | 0.219 | 0.312 | no |
| v1.36.13 | p50 latency (us) | +3.01% | +2.72% | 2/6 | 0.688 | 0.562 | no |
| v1.36.13 | p99 latency (us) | -0.76% | +9.47% | 2/6 | 0.688 | 0.688 | no |
| v1.40.2 | instructions:u / req | -12.03% | -12.06% | 6/6 | 0.031 | 0.031 | yes |
| v1.40.2 | cycles:u / req | +0.10% | +0.67% | 2/6 | 0.688 | 1.000 | no |
| v1.40.2 | cycles:k / req | +0.41% | +0.34% | 3/6 | 1.000 | 1.000 | no |
| v1.40.2 | cycles (u+k) / req | +0.21% | +0.73% | 2/6 | 0.688 | 1.000 | no |
| v1.40.2 | p50 latency (us) | -8.80% | -8.31% | 4/6 | 0.688 | 0.438 | no |
| v1.40.2 | p99 latency (us) | -5.85% | -7.02% | 3/6 | 1.000 | 1.000 | no |

## Validity

54 of 54 legs valid.

