# POST-HOC re-evaluation under the second revision of the gates (no new runs)

Rationale: a thread reads the clock once per 256 operations, so a starved thread's window edges are known only to within one batch; threads whose skew is within that granularity count as concurrent (every thread is at full load before and after its own window). New gates: time outside the common window at most 2 ms + 0.5% of the window + 3 batches of the slowest thread; slowest thread at least 1,024 operations. Nothing was re-run; the outputs are the ones on disk, checked with the gates they ran under (before) and with the new gates (after). Headline numbers in the per-set tables are pooled cycles per operation and pooled throughput.

| Set | Processes | Kept at the time | Accepted before | Accepted after | Repetitions | Valid before | Valid after |
|---|---|---|---|---|---|---|---|
| arm-vm-r5 | 35 | 15 | 15 | 24 | 2250 | 2118 | 2233 |
| arm-vm-r5b | 20 | 8 | 8 | 19 | 2100 | 2077 | 2099 |
| x86-vm-r5 | 35 | 35 | 35 | 35 | 2250 | 2250 | 2250 |

Left after, arm-vm-r5: 17 x window overlap at 15 threads; 15 x too few valid repetitions at 15 threads
Left after, arm-vm-r5b: 1 x window overlap at 12 threads; 1 x too few valid repetitions at 12 threads

