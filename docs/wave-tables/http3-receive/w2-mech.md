
## mech-sys-s: syscalls per request (Measured [mechanism]; one traced leg per arm, not scored)

| arm | all syscalls | recvmmsg | recvmmsg returning EAGAIN | recvmsg | sendmsg | sendmmsg | readv | readv returning EAGAIN | writev | sendto | epoll_wait | epoll_wait with timeout 0 | epoll_ctl | timerfd_settime | futex | EAGAIN share of recvmmsg | UDP datagrams /req (box-wide) | responses in the perf window | valid | busiest worker (of a CPU) | user instr /req under the tracer | latency max µs | guards (ch, st, ru) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2tls | 11.0299 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.9998 | 0.9999 | 0.0000 | 1.9997 | 4.0297 | 1.9997 | 0.0000 | 0.0000 | 0.0006 | 0.000 | 0.0000 | 40010.4 | yes | 0.1882 | 202723 | 4567.807 | -1, -1, -1 |
| h3-official | 16.6692 | 3.7574 | 1.8747 | 0.0000 | 5.0194 | 0.0000 | 2.0004 | 1.0000 | 0.0000 | 0.9999 | 4.8908 | 0.9998 | 0.0000 | 0.0000 | 0.0008 | 0.499 | 7.0167 | 40009.9 | yes | 0.4398 | 521643 | 11468.287 | -1, -1, -1 |
| h3-off | 15.9183 | 3.2075 | 1.5647 | 0.0000 | 5.0192 | 0.0000 | 2.0009 | 0.9999 | 0.0000 | 0.9999 | 4.6894 | 0.9988 | 0.0000 | 0.0000 | 0.0008 | 0.488 | 7.0166 | 40010.3 | yes | 0.4796 | 503219 | 12079.103000000001 | 1, 0, 0 |
| h3-stop-on | 14.8929 | 1.8158 | 0.0000 | 0.0000 | 5.0194 | 0.0000 | 1.9997 | 0.9999 | 0.0000 | 0.9999 | 5.0569 | 0.9999 | 0.0000 | 0.0000 | 0.0006 | 0.000 | 7.0166 | 40010.3 | yes | 0.4158 | 449820 | 4413.183 | 1, 1, 0 |
| h3-both-on | 15.1857 | 1.8378 | 0.0000 | 0.0000 | 5.0194 | 0.0000 | 1.9998 | 0.9999 | 0.0000 | 0.9999 | 5.3279 | 0.9998 | 0.0000 | 0.0000 | 0.0005 | 0.000 | 7.0166 | 40010.1 | yes | 0.4464 | 394357 | 16421.375 | 1, 1, 1 |
| h3-reuse-on | 16.4527 | 3.3986 | 1.6409 | 0.0000 | 5.0192 | 0.0000 | 2.0106 | 1.0044 | 0.0000 | 0.9999 | 5.0233 | 0.9997 | 0.0000 | 0.0000 | 0.0006 | 0.483 | 7.0165 | 40010.8 | yes | 0.4547 | 401493 | 18181.119 | 1, 0, 1 |

## mech-kcg-s: share of worker-thread cycles, inclusive (Measured [mechanism]; one profiled leg per arm, 999 Hz)

| arm | worker samples (period sum) | handleReadCallback | readPacketsFromSocket | readFromSocket | readFromSocketRecvMmsg (either form) | passPayloadToProcessor | processPacket | IoSocketHandleImpl::recvmmsg | recvmmsg syscall (kernel) | sendmsg syscall (kernel) | reserveSingleSlice | QuicDispatcher::ProcessPacket | packet handling under readFromSocket | receive path (readFromSocket minus the packet handling under it) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h3-off | 50246822204 | 36.93% | 36.25% | 35.56% | 1.62% | 25.29% | 25.11% | 3.89% | 1.66% | 10.13% | 0.90% | 24.46% | 25.30% | 10.26% |
| h3-stop-on | 49360629700 | 36.58% | 35.73% | 35.12% | 0.98% | 27.06% | 26.77% | 3.06% | 1.60% | 10.65% | 0.76% | 25.93% | 27.07% | 8.06% |
| h3-both-on | 49707664364 | 36.23% | 35.15% | 34.64% | 0.03% | 29.54% | 29.23% | 3.65% | 1.94% | 11.10% | 0.08% | 28.36% | 29.55% | 5.09% |

post-check: OK ~/epl/runs/wave8w2/mech/out-mech-kcg-s/kcg-150850.data samples_perf=44601 samples_folded=44601 stacks_with_envoy_symbols=20164 stacks_with_kernel_symbols=6350; OK ~/epl/runs/wave8w2/mech/out-mech-kcg-s/kcg-150956.data samples_perf=46244 samples_folded=46244 stacks_with_envoy_symbols=21196 stacks_with_kernel_symbols=6585; OK ~/epl/runs/wave8w2/mech/out-mech-kcg-s/kcg-151065.data samples_perf=53352 samples_folded=53352 stacks_with_envoy_symbols=23328 stacks_with_kernel_symbols=7164

## loss-s: Envoy's QUIC connection statistics over the whole leg (Exploratory; one untraced leg per arm with the statistics visitor on; counters are written when a connection closes)

| arm | cx_tx_packets_total | cx_tx_packets_retransmitted_total | cx_rx_packets_total | cx_path_degrading_total | cx_tx_amplification_throttling_total | completed requests over the leg | retransmitted per 100,000 packets sent | latency max µs | p99 µs | UDP datagrams /req in the window | valid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| h3-official | 421440 | 5 | 121114 | 0 | 0 | 60000 | 1.19 | 13552.127 | 717.343 | 7.0163 | True |
| h3-off | 421444 | 6 | 121115 | 0 | 0 | 60000 | 1.42 | 4836.095 | 722.495 | 7.0166 | True |
| h3-stop-on | 421448 | 16 | 121132 | 0 | 0 | 60000 | 3.80 | 2410.111 | 728.6709999999999 | 7.0163 | True |
| h3-both-on | 421457 | 15 | 121118 | 0 | 0 | 60000 | 3.56 | 3121.407 | 675.135 | 7.0164 | True |

## smokes: one line per leg

- smoke-s/h2tls: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.1751 of a CPU; latency max 4963.839 µs; datagrams/req 0.0000
- smoke-s/h3-official: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.3841 of a CPU; latency max 4970.751 µs; datagrams/req 7.0165
- smoke-s/h3-official-A2: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.454 of a CPU; latency max 13951.999 µs; datagrams/req 7.0164
- smoke-s/h3-off: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.5049 of a CPU; latency max 15497.726999999999 µs; datagrams/req 7.0165
- smoke-s/h3-stop-on: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.3388 of a CPU; latency max 2815.487 µs; datagrams/req 7.0166
- smoke-s/h3-both-on: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.3293 of a CPU; latency max 3698.047 µs; datagrams/req 7.0166
- smoke-shi/h2tls: valid True; client 2xx/s 6000.0 of 6000; busiest worker 0.4481 of a CPU; latency max 4329.727 µs; datagrams/req 0.0000
- smoke-shi/h3-official: valid True; client 2xx/s 5999.8 of 6000; busiest worker 0.999 of a CPU; latency max 24967.166999999998 µs; datagrams/req 6.6691
- smoke-shi/h3-official-A2: valid True; client 2xx/s 6000.0 of 6000; busiest worker 0.9896 of a CPU; latency max 20576.255 µs; datagrams/req 6.8640
- smoke-shi/h3-off: valid True; client 2xx/s 6000.0 of 6000; busiest worker 0.955 of a CPU; latency max 13093.375 µs; datagrams/req 6.9170
- smoke-shi/h3-stop-on: valid True; client 2xx/s 6000.0 of 6000; busiest worker 0.9673 of a CPU; latency max 12669.951000000001 µs; datagrams/req 6.7489
- smoke-shi/h3-both-on: valid True; client 2xx/s 6000.0 of 6000; busiest worker 0.8987 of a CPU; latency max 10041.855000000001 µs; datagrams/req 6.9046
