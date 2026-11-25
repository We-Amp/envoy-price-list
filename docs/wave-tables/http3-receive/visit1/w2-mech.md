
## mech-sys-s: syscalls per request (Measured [mechanism]; one traced leg per arm, not scored)

| arm | all syscalls | recvmmsg | recvmmsg returning EAGAIN | recvmsg | sendmsg | sendmmsg | readv | readv returning EAGAIN | writev | sendto | epoll_wait | epoll_wait with timeout 0 | epoll_ctl | timerfd_settime | futex | EAGAIN share of recvmmsg | UDP datagrams /req (box-wide) | responses in the perf window | valid | busiest worker (of a CPU) | user instr /req under the tracer | latency max µs | guards (ch, st, ru) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2tls | 11.0309 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.9998 | 0.9999 | 0.0000 | 1.9997 | 4.0306 | 1.9997 | 0.0000 | 0.0000 | 0.0005 | 0.000 | 0.0000 | 40009.5 | yes | 0.1854 | 202595 | 1135.2949999999998 | -1, -1, -1 |
| h3-official | 16.3572 | 3.4133 | 1.6890 | 0.0000 | 5.0193 | 0.0000 | 2.0000 | 0.9999 | 0.0000 | 0.9999 | 4.9232 | 0.9998 | 0.0000 | 0.0000 | 0.0009 | 0.495 | 7.0167 | 40009.9 | yes | 0.4356 | 508926 | 3939.4549999999995 | -1, -1, -1 |
| h3-off | 17.0490 | 3.7461 | 1.8354 | 0.0000 | 5.0193 | 0.0000 | 1.9998 | 0.9999 | 0.0000 | 0.9999 | 5.2823 | 0.9999 | 0.0000 | 0.0000 | 0.0009 | 0.490 | 7.0165 | 40010.5 | yes | 0.4187 | 523866 | 12614.655 | 1, 0, 0 |
| h3-stop-on | 15.4002 | 1.9997 | 0.0000 | 0.0000 | 5.0194 | 0.0000 | 2.0004 | 0.9999 | 0.0000 | 0.9999 | 5.3795 | 0.9999 | 0.0000 | 0.0000 | 0.0007 | 0.000 | 7.0166 | 40010.1 | yes | 0.4268 | 457177 | 3112.447 | 1, 1, 0 |
| h3-both-on | 15.0705 | 1.8235 | 0.0000 | 0.0000 | 5.0193 | 0.0000 | 1.9997 | 0.9999 | 0.0000 | 0.9999 | 5.2267 | 0.9998 | 0.0000 | 0.0000 | 0.0005 | 0.000 | 7.0165 | 40010.3 | yes | 0.4 | 394351 | 13702.143 | 1, 1, 1 |
| h3-reuse-on | 16.8883 | 3.6873 | 1.8129 | 0.0000 | 5.0194 | 0.0000 | 1.9998 | 0.9999 | 0.0000 | 0.9999 | 5.1804 | 0.9998 | 0.0000 | 0.0000 | 0.0007 | 0.492 | 7.0168 | 40009.7 | yes | 0.4117 | 403183 | 2635.519 | 1, 0, 1 |

## mech-sys-s.first: syscalls per request (Measured [mechanism]; one traced leg per arm, not scored)

| arm | all syscalls | recvmmsg | recvmmsg returning EAGAIN | recvmsg | sendmsg | sendmmsg | readv | readv returning EAGAIN | writev | sendto | epoll_wait | epoll_wait with timeout 0 | epoll_ctl | timerfd_settime | futex | EAGAIN share of recvmmsg | UDP datagrams /req (box-wide) | responses in the perf window | valid | busiest worker (of a CPU) | user instr /req under the tracer | latency max µs | guards (ch, st, ru) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2tls | 11.0277 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.9997 | 0.9998 | 0.0000 | 1.9997 | 4.0276 | 1.9997 | 0.0000 | 0.0000 | 0.0005 | 0.000 | 0.0000 | 40010.6 | yes | 0.1854 | 202054 | 4441.599 | -1, -1, -1 |
| h3-official | 16.5810 | 3.4752 | 1.6910 | 0.0000 | 5.0192 | 0.0000 | 2.0049 | 0.9999 | 0.0000 | 0.9999 | 5.0801 | 0.9999 | 0.0000 | 0.0000 | 0.0010 | 0.487 | 7.0166 | 40010.4 | yes | 0.428 | 512197 | 4430.847 | -1, -1, -1 |
| h3-off | 16.9732 | 3.6690 | 1.8126 | 0.0000 | 5.0193 | 0.0000 | 2.0021 | 1.0008 | 0.0000 | 0.9998 | 5.2810 | 0.9999 | 0.0000 | 0.0000 | 0.0013 | 0.494 | 7.0167 | 40010.1 | yes | 0.4357 | 521545 | 4468.223 | 1, 0, 0 |
| h3-stop-on | 15.2287 | 1.9350 | 0.0000 | 0.0000 | 5.0193 | 0.0000 | 1.9998 | 0.9999 | 0.0000 | 0.9998 | 5.2735 | 0.9998 | 0.0000 | 0.0000 | 0.0007 | 0.000 | 7.0165 | 40010.8 | yes | 0.4661 | 455019 | 4743.423 | 1, 1, 0 |
| h3-both-on | 15.2742 | 1.9369 | 0.0000 | 0.0000 | 5.0193 | 0.0000 | 2.0085 | 0.9999 | 0.0000 | 0.9999 | 5.3084 | 0.9999 | 0.0000 | 0.0000 | 0.0005 | 0.000 | 7.0166 | 40010.2 | yes | 0.4168 | 395797 | 3938.559 | 1, 1, 1 |
| h3-reuse-on | 16.2964 | 3.5176 | 1.6981 | 0.0000 | 5.0193 | 0.0000 | 2.0006 | 0.9999 | 0.0000 | 0.9999 | 4.7579 | 0.9998 | 0.0000 | 0.0000 | 0.0006 | 0.483 | 7.0165 | 40010.5 | yes | 0.4306 | 402243 | 2796.159 | 1, 0, 1 |

## smokes: one line per leg

- smoke-s/h2tls: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.1811 of a CPU; latency max 1091.0710000000001 µs; datagrams/req 0.0000
- smoke-s/h3-official: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.3608 of a CPU; latency max 2933.119 µs; datagrams/req 7.0166
- smoke-s/h3-official-A2: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.4226 of a CPU; latency max 4232.703 µs; datagrams/req 7.0164
- smoke-s/h3-off: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.4715 of a CPU; latency max 7926.271000000001 µs; datagrams/req 7.0165
- smoke-s/h3-stop-on: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.4446 of a CPU; latency max 5244.159 µs; datagrams/req 7.0164
- smoke-s/h3-both-on: valid True; client 2xx/s 2000.0 of 2000; busiest worker 0.4287 of a CPU; latency max 5645.311 µs; datagrams/req 7.0164
