# aa-selftest

- Harness: 0.1.0 310d7e30fb57
- Window: 2026-11-13T18:53:09Z to 2026-11-13T19:16:20Z
- Machine: 2x Xeon E5-2673 v4 (2x20 cores, SMT on), bare metal, fixed 2.3 GHz, turbo off
- CPU: Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz; kernel 6.8.0-149-generic; governor performance; clock (kHz) 2059941,2294584,2295391,2300000
- CPU sets: client 20-31,60-71, origin 32-39,72-79, sut 0-3,40-43
- Envoy: 4 workers, exact_balance True; client concurrency 16 x 32 connections, idle strategy poll, open loop True; warm-up 5s, run 25s, perf window 20s after 2s lead-in
- Rounds: 6, order abba; base arm A; alpha 0.05

| Arm | Version | md5 |
|---|---|---|
| A | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |
| A2 | b2d89e0ae53916f28770771fbdd49c5c99c5c5a2/1.40.2/Clean/RELEASE/BoringSSL | `a9c0f798a3f31752492d1843b66d85aa` |

## s (`/s`, proxied, 5200 rps)

Medians over valid legs.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 6/6 | 163.2k | 339.9k | 170.6k | 510.5k | 422 | 621 | 30.6% |
| A2 | 6/6 | 163.2k | 334.1k | 167.7k | 500.8k | 436 | 703 | 29.6% |

| Arm vs A | metric | delta mean | delta median | won | sign p | Wilcoxon p | differs |
|---|---|---|---|---|---|---|---|
| A2 | instructions:u / req | -0.03% | -0.04% | 3/6 | 1.000 | 1.000 | no |
| A2 | cycles:u / req | -3.31% | -1.70% | 4/6 | 0.688 | 0.312 | no |
| A2 | cycles:k / req | -2.97% | -1.69% | 3/6 | 1.000 | 0.688 | no |
| A2 | cycles (u+k) / req | -3.20% | -1.89% | 4/6 | 0.688 | 0.438 | no |
| A2 | p50 latency (us) | +0.34% | +3.41% | 4/6 | 0.688 | 1.000 | no |
| A2 | p99 latency (us) | +11.60% | +13.22% | 1/6 | 0.219 | 0.156 | no |

## fh (`/fh`, direct_headers, 8000 rps)

Medians over valid legs.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 6/6 | 164.2k | 192.6k | 78.5k | 271.1k | 202 | 346 | 24.7% |
| A2 | 6/6 | 164.2k | 188.0k | 73.8k | 261.6k | 204 | 356 | 23.8% |

| Arm vs A | metric | delta mean | delta median | won | sign p | Wilcoxon p | differs |
|---|---|---|---|---|---|---|---|
| A2 | instructions:u / req | -0.03% | -0.00% | 5/6 | 0.219 | 0.438 | no |
| A2 | cycles:u / req | -2.91% | -2.38% | 4/6 | 0.688 | 0.562 | no |
| A2 | cycles:k / req | -4.37% | -6.06% | 5/6 | 0.219 | 0.156 | no |
| A2 | cycles (u+k) / req | -3.33% | -3.52% | 4/6 | 0.688 | 0.562 | no |
| A2 | p50 latency (us) | +0.03% | +0.85% | 3/6 | 1.000 | 1.000 | no |
| A2 | p99 latency (us) | +0.81% | +3.11% | 3/6 | 1.000 | 1.000 | no |

## m (`/m`, proxied, 5440 rps)

Medians over valid legs.

| Arm | valid | ins:u/req | cyc:u/req | cyc:k/req | cyc total/req | p50 us | p99 us | SUT busy |
|---|---|---|---|---|---|---|---|---|
| A | 6/6 | 166.4k | 352.5k | 191.0k | 544.8k | 457 | 697 | 33.1% |
| A2 | 6/6 | 166.4k | 346.7k | 190.3k | 536.0k | 420 | 665 | 32.7% |

| Arm vs A | metric | delta mean | delta median | won | sign p | Wilcoxon p | differs |
|---|---|---|---|---|---|---|---|
| A2 | instructions:u / req | +0.11% | +0.01% | 1/6 | 0.219 | 0.219 | no |
| A2 | cycles:u / req | -2.40% | -1.63% | 3/6 | 1.000 | 0.438 | no |
| A2 | cycles:k / req | +0.18% | -0.39% | 3/6 | 1.000 | 0.844 | no |
| A2 | cycles (u+k) / req | -1.50% | -1.62% | 3/6 | 1.000 | 0.438 | no |
| A2 | p50 latency (us) | -8.98% | -8.07% | 5/6 | 0.219 | 0.062 | no |
| A2 | p99 latency (us) | -4.80% | -4.69% | 3/6 | 1.000 | 0.844 | no |

## Validity

36 of 36 legs valid.

## A/A self-test: PASS (no difference)

- s A2 instructions_u: sign p 1.000, Wilcoxon p 1.000, delta mean -0.03%, won 3/6
- s A2 cycles_total: sign p 0.688, Wilcoxon p 0.438, delta mean -3.20%, won 4/6
- fh A2 instructions_u: sign p 0.219, Wilcoxon p 0.438, delta mean -0.03%, won 5/6
- fh A2 cycles_total: sign p 0.688, Wilcoxon p 0.562, delta mean -3.33%, won 4/6
- m A2 instructions_u: sign p 0.219, Wilcoxon p 0.219, delta mean +0.11%, won 1/6
- m A2 cycles_total: sign p 1.000, Wilcoxon p 0.438, delta mean -1.50%, won 3/6

