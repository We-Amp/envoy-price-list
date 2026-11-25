
## syscalls: mech-sys-buf buf-default/m hop A (pid 58648, 108823 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.511, enter_epoll_wait 1.927, exit_epoll_wait 3.507, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.004, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.901 | 1.947 |
| epoll_wait | 3.418 | 0.000 |
| writev | 0.976 | 0.000 |
| sendto | 0.976 | 0.000 |
| **all** | **9.271** | **1.948** |

## syscalls: mech-sys-buf buf-4k/m hop A (pid 58752, 108825 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 24.484, enter_epoll_wait 3.319, exit_epoll_wait 4.501, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 2.000, exit_readv 1.985, enter_read 0.000, exit_read 0.000, enter_recvfrom 3.001, exit_recvfrom 0.016, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.984, enter_sendmsg 0.000, enter_epoll_ctl 11.999, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.000
flow control per request: upstream_flow_control_paused_reading (up) 2.0000, upstream_flow_control_resumed_reading (up) 1.9819, upstream_flow_control_backed_up (up) 0.0000, upstream_flow_control_drained (up) 0.0000, downstream_flow_control_paused_reading (down) 0.0000, downstream_flow_control_resumed_reading (down) 0.0000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| epoll_ctl | 11.660 | 0.000 |
| epoll_wait | 4.374 | 0.000 |
| recvfrom | 2.926 | 0.015 |
| readv | 1.947 | 1.933 |
| sendto | 1.936 | 0.000 |
| writev | 0.976 | 0.000 |
| **all** | **23.820** | **1.948** |

## syscalls: mech-sys-buf buf-default/l64 hop A (pid 58856, 40008 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 10.015, enter_epoll_wait 1.999, exit_epoll_wait 4.013, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.000, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| epoll_wait | 3.913 | 0.000 |
| readv | 3.899 | 1.949 |
| writev | 0.975 | 0.000 |
| sendto | 0.975 | 0.000 |
| **all** | **9.764** | **1.949** |

## syscalls: mech-sys-buf buf-32k/l64 hop A (pid 58960, 40008 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 23.486, enter_epoll_wait 3.865, exit_epoll_wait 6.486, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 6.000, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 2.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 7.999, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001
flow control per request: upstream_flow_control_paused_reading (up) 1.9990, upstream_flow_control_resumed_reading (up) 1.0000, upstream_flow_control_backed_up (up) 0.0000, upstream_flow_control_drained (up) 0.0000, downstream_flow_control_paused_reading (down) 0.0000, downstream_flow_control_resumed_reading (down) 0.0000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| epoll_ctl | 7.751 | 0.000 |
| epoll_wait | 6.311 | 0.000 |
| readv | 5.839 | 1.945 |
| writev | 1.950 | 0.000 |
| sendto | 0.975 | 0.000 |
| **all** | **22.827** | **1.945** |

## syscalls: mech-sys-buf buf-default/l1m hop A (pid 59064, 16003 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 28.563, enter_epoll_wait 3.723, exit_epoll_wait 5.521, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 12.040, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 4.000, enter_write 0.001, enter_sendto 3.000, enter_sendmsg 0.000, enter_epoll_ctl 4.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.002
flow control per request: upstream_flow_control_paused_reading (up) 1.0000, upstream_flow_control_resumed_reading (up) 0.9996, upstream_flow_control_backed_up (up) 0.0000, upstream_flow_control_drained (up) 0.0000, downstream_flow_control_paused_reading (down) 0.0000, downstream_flow_control_resumed_reading (down) 0.0000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 11.716 | 1.946 |
| epoll_wait | 5.385 | 0.000 |
| writev | 3.903 | 0.000 |
| epoll_ctl | 3.886 | 0.000 |
| sendto | 2.927 | 0.000 |
| **all** | **27.819** | **1.947** |

## syscalls: mech-sys-buf buf-32k/l1m hop A (pid 59168, 16004 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 153.258, enter_epoll_wait 29.168, exit_epoll_wait 31.281, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 36.018, exit_readv 2.003, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 16.999, enter_write 0.001, enter_sendto 1.008, enter_sendmsg 0.000, enter_epoll_ctl 67.948, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.002
flow control per request: upstream_flow_control_paused_reading (up) 16.9879, upstream_flow_control_resumed_reading (up) 15.9998, upstream_flow_control_backed_up (up) 0.0000, upstream_flow_control_drained (up) 0.0000, downstream_flow_control_paused_reading (down) 0.0000, downstream_flow_control_resumed_reading (down) 0.0000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| epoll_ctl | 66.029 | 0.000 |
| readv | 35.133 | 1.947 |
| epoll_wait | 30.408 | 0.000 |
| writev | 16.589 | 0.000 |
| sendto | 0.984 | 0.000 |
| **all** | **149.146** | **1.949** |

## syscalls: mech-sys-chunked cl/b64k hop A (pid 56119, 80018 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.682, enter_epoll_wait 1.945, exit_epoll_wait 3.682, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.000, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.893 | 1.946 |
| epoll_wait | 3.587 | 0.000 |
| sendto | 0.975 | 0.000 |
| writev | 0.975 | 0.000 |
| **all** | **9.430** | **1.946** |

## syscalls: mech-sys-chunked cl8k/b64k hop A (pid 56238, 80017 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 11.640, enter_epoll_wait 1.918, exit_epoll_wait 3.598, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 6.041, exit_readv 2.071, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 5.854 | 2.001 |
| epoll_wait | 3.507 | 0.000 |
| writev | 0.976 | 0.000 |
| sendto | 0.976 | 0.000 |
| **all** | **11.312** | **2.001** |

## syscalls: mech-sys-chunked ch8k/b64k hop A (pid 56342, 80018 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 11.846, enter_epoll_wait 1.930, exit_epoll_wait 3.620, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 6.225, exit_readv 2.085, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 6.036 | 2.016 |
| epoll_wait | 3.528 | 0.000 |
| writev | 0.976 | 0.000 |
| sendto | 0.975 | 0.000 |
| **all** | **11.516** | **2.016** |

## syscalls: mech-sys-chunked cl/b1m hop A (pid 56446, 16004 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 30.600, enter_epoll_wait 2.503, exit_epoll_wait 5.338, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 17.241, exit_readv 3.582, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.023, exit_recvfrom 0.002, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 4.665, enter_write 0.001, enter_sendto 1.670, enter_sendmsg 0.000, enter_epoll_ctl 1.661, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001
flow control per request: upstream_flow_control_paused_reading (up) 0.3888, upstream_flow_control_resumed_reading (up) 0.0007, upstream_flow_control_backed_up (up) 0.0000, upstream_flow_control_drained (up) 0.0000, downstream_flow_control_paused_reading (down) 0.0000, downstream_flow_control_resumed_reading (down) 0.0000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 16.827 | 3.481 |
| epoll_wait | 5.188 | 0.000 |
| writev | 4.550 | 0.000 |
| epoll_ctl | 1.658 | 0.000 |
| sendto | 1.629 | 0.000 |
| recvfrom | 0.023 | 0.002 |
| **all** | **29.878** | **3.484** |

## syscalls: mech-sys-chunked cl8k/b1m hop A (pid 56552, 16005 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 56.222, enter_epoll_wait 4.268, exit_epoll_wait 8.303, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 40.825, exit_readv 7.189, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 5.814, enter_write 0.001, enter_sendto 1.248, enter_sendmsg 0.000, enter_epoll_ctl 0.027, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.003
flow control per request: upstream_flow_control_paused_reading (up) 0.0061, upstream_flow_control_resumed_reading (up) 0.0005, upstream_flow_control_backed_up (up) 0.0000, upstream_flow_control_drained (up) 0.0000, downstream_flow_control_paused_reading (down) 0.0000, downstream_flow_control_resumed_reading (down) 0.0000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 39.689 | 6.870 |
| epoll_wait | 7.939 | 0.000 |
| writev | 5.640 | 0.000 |
| sendto | 1.215 | 0.000 |
| epoll_ctl | 0.027 | 0.000 |
| **all** | **54.513** | **6.872** |

## syscalls: mech-sys-chunked ch8k/b1m hop A (pid 56657, 16002 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 53.801, enter_epoll_wait 3.698, exit_epoll_wait 7.235, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 35.620, exit_readv 6.063, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 9.707, enter_write 0.001, enter_sendto 1.126, enter_sendmsg 0.000, enter_epoll_ctl 0.107, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.003
flow control per request: upstream_flow_control_paused_reading (up) 0.0245, upstream_flow_control_resumed_reading (up) 0.0018, upstream_flow_control_backed_up (up) 0.0000, upstream_flow_control_drained (up) 0.0000, downstream_flow_control_paused_reading (down) 0.0000, downstream_flow_control_resumed_reading (down) 0.0000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 34.796 | 5.856 |
| writev | 9.453 | 0.000 |
| epoll_wait | 6.999 | 0.000 |
| sendto | 1.097 | 0.000 |
| epoll_ctl | 0.106 | 0.000 |
| **all** | **52.456** | **5.858** |

## syscalls: mech-sys-grpc base/g20 hop A (pid 57941, 41611 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 81.875, enter_epoll_wait 15.570, exit_epoll_wait 27.723, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 34.547, exit_readv 16.484, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.000, enter_sendto 19.603, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 33.676 | 16.043 |
| epoll_wait | 27.068 | 0.000 |
| sendto | 19.162 | 0.000 |
| **all** | **79.908** | **16.044** |

## syscalls: mech-sys-grpc base-A2/g20 hop A (pid 58109, 41611 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 80.991, enter_epoll_wait 15.377, exit_epoll_wait 27.227, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 34.201, exit_readv 16.263, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.000, enter_sendto 19.561, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 33.320 | 15.823 |
| epoll_wait | 26.561 | 0.000 |
| sendto | 19.097 | 0.000 |
| **all** | **78.981** | **15.824** |

## syscalls: mech-sys-grpc base/g200 hop A (pid 58214, 4162 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 836.049, enter_epoll_wait 159.965, exit_epoll_wait 304.533, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 356.154, exit_readv 171.654, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.005, enter_sendto 175.350, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.010

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 346.170 | 166.574 |
| epoll_wait | 296.195 | 0.000 |
| sendto | 170.768 | 0.000 |
| futex | 0.009 | 0.006 |
| **all** | **813.147** | **166.580** |

## syscalls: mech-sys-grpc base-A2/g200 hop A (pid 58318, 4163 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 850.973, enter_epoll_wait 162.622, exit_epoll_wait 316.302, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 361.846, exit_readv 175.961, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.005, enter_sendto 172.805, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.010

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 351.995 | 170.957 |
| epoll_wait | 308.272 | 0.000 |
| sendto | 168.304 | 0.000 |
| futex | 0.010 | 0.006 |
| **all** | **828.586** | **170.962** |

## syscalls: mech-sys-h3 h2tls/s hop A (pid 59459, 40010 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 11.027, enter_epoll_wait 2.000, exit_epoll_wait 4.026, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 2.000, exit_readv 1.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 3.000, exit_recvfrom 1.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.000, enter_sendto 2.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| epoll_wait | 3.928 | 0.000 |
| recvfrom | 2.924 | 0.973 |
| sendto | 1.951 | 0.000 |
| readv | 1.951 | 0.975 |
| **all** | **10.754** | **1.949** |

## syscalls: mech-sys-h3 h3/s hop A (pid 59566, 40009 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 17.350, enter_epoll_wait 1.000, exit_epoll_wait 5.330, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 2.000, exit_readv 1.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 4.000, enter_writev 0.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 5.019, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 2.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| epoll_wait | 5.195 | 0.000 |
| sendmsg | 4.896 | 0.000 |
| recvmmsg | 3.900 | 1.950 |
| readv | 1.951 | 0.975 |
| sendto | 0.976 | 0.000 |
| **all** | **16.920** | **2.926** |

## syscalls: mech-sys-stream base/ev20 hop A (pid 57055, 41608 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 91.081, enter_epoll_wait 17.414, exit_epoll_wait 28.084, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 41.997, exit_readv 20.999, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.000, enter_sendto 20.999, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 40.868 | 20.410 |
| epoll_wait | 27.242 | 0.000 |
| sendto | 20.484 | 0.000 |
| **all** | **88.596** | **20.411** |

## syscalls: mech-sys-stream idle-off/ev20 hop A (pid 57321, 41608 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 90.350, enter_epoll_wait 17.054, exit_epoll_wait 27.351, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 41.998, exit_readv 20.999, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.000, enter_sendto 20.999, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 40.863 | 20.404 |
| epoll_wait | 26.519 | 0.000 |
| sendto | 20.485 | 0.000 |
| **all** | **87.869** | **20.405** |

## syscalls: mech-sys-stream base/ev200 hop A (pid 57437, 4161 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 910.688, enter_epoll_wait 178.221, exit_epoll_wait 307.768, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 401.935, exit_readv 200.968, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.005, enter_sendto 200.967, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.011

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 391.048 | 195.247 |
| epoll_wait | 299.076 | 0.000 |
| sendto | 196.072 | 0.000 |
| futex | 0.009 | 0.006 |
| **all** | **886.212** | **195.253** |

## syscalls: mech-sys-stream idle-off/ev200 hop A (pid 57541, 4161 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 907.419, enter_epoll_wait 177.518, exit_epoll_wait 304.413, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 401.987, exit_readv 200.993, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.005, enter_sendto 200.991, enter_sendmsg 0.000, enter_epoll_ctl 0.001, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.011

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 391.251 | 195.408 |
| epoll_wait | 295.620 | 0.000 |
| sendto | 196.061 | 0.000 |
| futex | 0.011 | 0.006 |
| **all** | **882.952** | **195.415** |

## syscalls: smoke-mech-sys buf-default/l64 hop A (pid 35159, 40008 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 10.020, enter_epoll_wait 1.999, exit_epoll_wait 4.017, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.002, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| epoll_wait | 3.917 | 0.000 |
| readv | 3.895 | 1.945 |
| sendto | 0.975 | 0.000 |
| writev | 0.975 | 0.000 |
| **all** | **9.764** | **1.946** |

## syscalls: smoke-mech-sys buf-32k/l64 hop A (pid 35267, 40008 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 23.459, enter_epoll_wait 3.854, exit_epoll_wait 6.459, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 5.999, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 2.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 7.999, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.001
flow control per request: upstream_flow_control_paused_reading (up) 1.9993, upstream_flow_control_resumed_reading (up) 1.0000, upstream_flow_control_backed_up (up) 0.0000, upstream_flow_control_drained (up) 0.0000, downstream_flow_control_paused_reading (down) 0.0000, downstream_flow_control_resumed_reading (down) 0.0000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| epoll_ctl | 7.755 | 0.000 |
| epoll_wait | 6.288 | 0.000 |
| readv | 5.846 | 1.946 |
| writev | 1.951 | 0.000 |
| sendto | 0.976 | 0.000 |
| **all** | **22.817** | **1.946** |

## call graph: mech-kcg-chunked cl8k/b1m hop A (pid 59927)

worker-thread cycles sampled: 5.41e+10 (of 5.79e+10 on these CPUs); user 20.2%, kernel 79.8%
syscall subtrees (inclusive, %% of worker cycles): writev 39.67, readv 33.20, sendto 1.85, epoll_wait 1.78
scheduling inside epoll_wait: 0.77%; self time of syscall entry and exit symbols: 2.73%
top kernel self: rep_movs_alternative 19.26, clear_page_erms 14.58, entry_SYSRETQ_unsafe_stack 1.26, check_heap_object 1.00, __skb_datagram_iter 0.93, __tcp_transmit_skb 0.89, tcp_recvmsg_locked 0.83, sock_rfree 0.77, skb_release_data 0.74, native_queued_spin_lock_slowpath 0.59, tcp_rcv_established 0.58, __raw_spin_lock_irqsave 0.52, __mod_memcg_state 0.52, skb_attempt_defer_free 0.51
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 9.01 (0.11), http1 bufferBody 0.47 (0.01), http1 dispatch (ConnectionImpl::dispatch) 12.22 (0.20), Buffer::OwnedImpl::add 0.02 (0.00), Buffer::OwnedImpl::move 1.24 (0.04), Buffer::OwnedImpl::read (socket read) 0.94 (0.01), timers (enableTimer / TimerImpl) 0.93 (0.01)
leaf symbols: memmove/memcpy (leaf) 0.00, malloc/free (leaf, tcmalloc) 1.04
top user self: Envoy::Buffer::Slice::operator=(Envoy::Buffer::Slice&&) 0.73, Envoy::Buffer::OwnedImpl::reserveWithMaxLength(unsigned_long) 0.50, [libc.so.6] 0.41, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.35, Envoy::Buffer::Slice::callAndClearDrainTrackersAndCharges() 0.32, [[vdso]] 0.26, event_queue_remove_timeout 0.26, std::__1::__function::__value_func<void_()>::swap[abi:nqe220108](std:: 0.25, pthread_mutex_lock 0.22, event_base_loop 0.21, Envoy::Network::ConnectionImpl::onFileEvent(unsigned_int) 0.19, Envoy::Logger::Context::useFineGrainLogger() 0.19

## call graph: mech-kcg-chunked ch8k/b1m hop A (pid 60044)

worker-thread cycles sampled: 5.93e+10 (of 6.3e+10 on these CPUs); user 26.4%, kernel 73.6%
syscall subtrees (inclusive, %% of worker cycles): writev 39.62, readv 28.77, epoll_wait 1.30, sendto 1.19
scheduling inside epoll_wait: 0.62%; self time of syscall entry and exit symbols: 2.06%
top kernel self: rep_movs_alternative 17.82, clear_page_erms 14.61, check_heap_object 0.89, __skb_datagram_iter 0.87, entry_SYSRETQ_unsafe_stack 0.86, skb_release_data 0.78, tcp_recvmsg_locked 0.75, __tcp_transmit_skb 0.75, sock_rfree 0.64, _copy_to_iter 0.55, tcp_rcv_established 0.51, __raw_spin_lock_irqsave 0.51, __mod_memcg_state 0.51, tcp_clean_rtx_queue.constprop.0 0.49
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 15.64 (0.23), http1 bufferBody 0.09 (0.00), http1 dispatch (ConnectionImpl::dispatch) 19.68 (0.29), Buffer::OwnedImpl::add 1.09 (0.02), Buffer::OwnedImpl::move 1.47 (0.05), Buffer::OwnedImpl::read (socket read) 0.68 (0.01), timers (enableTimer / TimerImpl) 0.76 (0.01)
leaf symbols: memmove/memcpy (leaf) 0.01, malloc/free (leaf, tcmalloc) 1.43
top user self: [libc.so.6] 5.95, Envoy::Buffer::Slice::operator=(Envoy::Buffer::Slice&&) 1.19, quiche::BalsaFrame::ProcessInput(char_const*,_unsigned_long) 0.91, Envoy::Buffer::Slice::callAndClearDrainTrackersAndCharges() 0.55, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.44, std::__1::__function::__value_func<void_()>::swap[abi:nqe220108](std:: 0.38, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.36, Envoy::Buffer::OwnedImpl::reserveWithMaxLength(unsigned_long) 0.31, Envoy::Buffer::OwnedImpl::addImpl(void_const*,_unsigned_long) 0.27, operator_delete[](void*,_std::nothrow_t_const&) 0.23, event_queue_remove_timeout 0.21, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.20

## call graph: mech-kcg-h3 h2tls/s hop A (pid 60928)

worker-thread cycles sampled: 2.94e+10 (of 3.56e+10 on these CPUs); user 67.1%, kernel 32.9%
syscall subtrees (inclusive, %% of worker cycles): sendto 14.52, epoll_wait 6.22, readv 5.77, recvfrom 1.72
scheduling inside epoll_wait: 4.40%; self time of syscall entry and exit symbols: 2.45%
top kernel self: entry_SYSRETQ_unsafe_stack 1.01, rep_movs_alternative 0.52, __tcp_transmit_skb 0.42, entry_SYSCALL_64 0.40, syscall_return_via_sysret 0.39, psi_group_change 0.35, tcp_recvmsg_locked 0.33, nf_conntrack_tcp_packet 0.33, __mod_memcg_state 0.32, tcp_sendmsg_locked 0.32, nf_hook_slow 0.31, __nf_conntrack_find_get 0.30, clear_page_erms 0.30, ip_finish_output2 0.30
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 23.81 (0.96), http1 bufferBody 0.15 (0.01), http1 dispatch (ConnectionImpl::dispatch) 24.71 (1.04), http2 dispatch 26.58 (0.04), Buffer::OwnedImpl::add 0.26 (0.01), Buffer::OwnedImpl::move 0.52 (0.04), Buffer::OwnedImpl::read (socket read) 0.75 (0.02), timers (enableTimer / TimerImpl) 1.81 (0.03)
leaf symbols: memmove/memcpy (leaf) 0.06, malloc/free (leaf, tcmalloc) 3.10
top user self: [libc.so.6] 1.64, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.13, [[vdso]] 0.80, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.61, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.50, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 0.49, pthread_mutex_lock 0.48, event_base_loop 0.44, event_add_nolock_ 0.44, _aesni_ctr32_ghash_6x 0.42, Envoy::Logger::Context::useFineGrainLogger() 0.41, Envoy::Buffer::OwnedImpl::reserveWithMaxLength(unsigned_long) 0.41

## call graph: mech-kcg-h3 h3/s hop A (pid 61034)

worker-thread cycles sampled: 5.08e+10 (of 5.68e+10 on these CPUs); user 73.2%, kernel 26.8%
syscall subtrees (inclusive, %% of worker cycles): sendmsg 9.80, epoll_wait 4.67, sendto 3.63, readv 3.00, recvmmsg 2.06
scheduling inside epoll_wait: 3.30%; self time of syscall entry and exit symbols: 2.24%
top kernel self: entry_SYSRETQ_unsafe_stack 0.85, rep_movs_alternative 0.45, syscall_return_via_sysret 0.37, entry_SYSCALL_64 0.35, __fdget 0.33, __raw_spin_lock_irqsave 0.31, memset_orig 0.29, aa_inet_msg_perm 0.28, __ip_append_data 0.27, kmem_cache_alloc_node 0.25, ip_finish_output2 0.25, psi_group_change 0.24, check_heap_object 0.24, __nf_conntrack_find_get 0.24
user frames, inclusive (kernel part inside): udp read callback (UdpListenerImpl::handleReadCallback) 40.26 (2.75), Utility::readFromSocket 38.77 (2.74), passPayloadToProcessor (packet handling) 27.50 (0.10), IoSocketHandleImpl::recvmmsg 4.39 (2.55), http1 parser (BalsaFrame::ProcessInput) 33.06 (8.18), http1 bufferBody 0.14 (0.00), http1 dispatch (ConnectionImpl::dispatch) 33.66 (8.22), Buffer::OwnedImpl::add 0.02 (0.00), Buffer::OwnedImpl::move 0.14 (0.00), Buffer::OwnedImpl::read (socket read) 1.12 (0.02), timers (enableTimer / TimerImpl) 1.70 (0.01), quic (quic:: or Envoy::Quic frames) 56.12 (10.86)
leaf symbols: memmove/memcpy (leaf) 0.03, malloc/free (leaf, tcmalloc) 3.91
top user self: [libc.so.6] 2.26, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.45, Envoy::Buffer::Slice::~Slice() 1.13, Envoy::Buffer::OwnedImpl::OwnedImpl() 1.04, Envoy::Buffer::Slice::callAndClearDrainTrackersAndCharges() 0.95, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.87, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.86, operator_new[](unsigned_long) 0.68, [[vdso]] 0.66, pthread_mutex_lock 0.51, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 0.50, Envoy::Network::IoSocketHandleImpl::recvmmsg(absl::lts_20260817::Fixed 0.48

## call graph: mech-kcg-stream base/ev200 hop A (pid 60444)

worker-thread cycles sampled: 6.64e+10 (of 7.66e+10 on these CPUs); user 29.3%, kernel 70.7%
syscall subtrees (inclusive, %% of worker cycles): sendto 30.30, readv 19.72, epoll_wait 11.09
scheduling inside epoll_wait: 7.31%; self time of syscall entry and exit symbols: 8.03%
top kernel self: entry_SYSRETQ_unsafe_stack 3.88, syscall_return_via_sysret 1.46, tcp_sendmsg_locked 1.32, entry_SYSCALL_64 1.30, __tcp_transmit_skb 1.23, __raw_spin_lock_irqsave 1.04, tcp_recvmsg_locked 1.00, __nf_conntrack_find_get 0.94, net_rx_action 0.88, nf_conntrack_tcp_packet 0.80, aa_inet_msg_perm 0.69, tcp_v4_rcv 0.67, tcp_ack 0.67, __inet_lookup_established 0.67
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 3.08 (0.02), http1 bufferBody 0.12 (0.00), http1 dispatch (ConnectionImpl::dispatch) 12.93 (0.09), Buffer::OwnedImpl::add 0.85 (0.00), Buffer::OwnedImpl::move 0.66 (0.01), Buffer::OwnedImpl::read (socket read) 1.30 (0.01), timers (enableTimer / TimerImpl) 2.65 (0.02)
leaf symbols: memmove/memcpy (leaf) 0.01, malloc/free (leaf, tcmalloc) 1.04
top user self: Envoy::Buffer::OwnedImpl::reserveWithMaxLength(unsigned_long) 0.93, [libc.so.6] 0.83, pthread_mutex_lock 0.68, quiche::BalsaFrame::ProcessInput(char_const*,_unsigned_long) 0.66, event_queue_remove_timeout 0.66, Envoy::Network::ConnectionImpl::onWriteReady() 0.61, event_base_loop 0.56, Envoy::Buffer::Slice::operator=(Envoy::Buffer::Slice&&) 0.55, [[vdso]] 0.47, Envoy::Stats::CounterImpl::add(unsigned_long) 0.46, Envoy::Http::CodecClient::onData(Envoy::Buffer::Instance&) 0.43, Envoy::Network::ConnectionImpl::onReadReady() 0.43

## call graph: mech-kcg-stream idle-off/ev200 hop A (pid 60600)

worker-thread cycles sampled: 6.46e+10 (of 7.48e+10 on these CPUs); user 28.2%, kernel 71.8%
syscall subtrees (inclusive, %% of worker cycles): sendto 30.32, readv 20.55, epoll_wait 11.21
scheduling inside epoll_wait: 7.46%; self time of syscall entry and exit symbols: 8.15%
top kernel self: entry_SYSRETQ_unsafe_stack 3.94, syscall_return_via_sysret 1.50, __tcp_transmit_skb 1.28, entry_SYSCALL_64 1.25, tcp_sendmsg_locked 1.24, __raw_spin_lock_irqsave 1.09, __nf_conntrack_find_get 1.05, tcp_recvmsg_locked 0.98, net_rx_action 0.84, nf_conntrack_tcp_packet 0.82, skb_release_data 0.75, kmem_cache_alloc_node 0.71, tcp_v4_rcv 0.69, __rcu_read_lock 0.67
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 3.16 (0.03), http1 bufferBody 0.11 (0.00), http1 dispatch (ConnectionImpl::dispatch) 12.09 (0.10), Buffer::OwnedImpl::add 0.93 (0.01), Buffer::OwnedImpl::move 0.63 (0.00), Buffer::OwnedImpl::read (socket read) 1.32 (0.00), timers (enableTimer / TimerImpl) 1.25 (0.00)
leaf symbols: memmove/memcpy (leaf) 0.01, malloc/free (leaf, tcmalloc) 0.98
top user self: Envoy::Buffer::OwnedImpl::reserveWithMaxLength(unsigned_long) 0.97, [libc.so.6] 0.81, quiche::BalsaFrame::ProcessInput(char_const*,_unsigned_long) 0.77, Envoy::Network::ConnectionImpl::onWriteReady() 0.57, pthread_mutex_lock 0.57, Envoy::Buffer::Slice::operator=(Envoy::Buffer::Slice&&) 0.56, Envoy::Stats::CounterImpl::add(unsigned_long) 0.51, event_base_loop 0.50, [[vdso]] 0.45, Envoy::Network::ConnectionImpl::onReadReady() 0.44, Envoy::Router::UpstreamRequest::decodeData(Envoy::Buffer::Instance&,_b 0.40, Envoy::Http::Http1::ConnectionImpl::dispatch(Envoy::Buffer::Instance&) 0.39

## call graph: smoke-mech-kcg buf-default/l64 hop A (pid 35564)

worker-thread cycles sampled: 3.06e+10 (of 3.63e+10 on these CPUs); user 55.2%, kernel 44.8%
syscall subtrees (inclusive, %% of worker cycles): writev 17.56, readv 10.68, sendto 7.01, epoll_wait 5.79
scheduling inside epoll_wait: 4.01%; self time of syscall entry and exit symbols: 2.45%
top kernel self: clear_page_erms 4.58, rep_movs_alternative 3.84, entry_SYSRETQ_unsafe_stack 0.95, check_heap_object 0.59, syscall_return_via_sysret 0.46, skb_release_data 0.45, __tcp_transmit_skb 0.45, __skb_datagram_iter 0.41, tcp_clean_rtx_queue.constprop.0 0.41, entry_SYSCALL_64 0.41, __mod_memcg_state 0.40, psi_group_change 0.38, __raw_spin_lock_irqsave 0.37, tcp_recvmsg_locked 0.37
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 39.08 (0.23), http1 bufferBody 0.24 (0.00), http1 dispatch (ConnectionImpl::dispatch) 43.33 (0.35), Buffer::OwnedImpl::add 0.08 (0.00), Buffer::OwnedImpl::move 0.70 (0.01), Buffer::OwnedImpl::read (socket read) 0.69 (0.00), timers (enableTimer / TimerImpl) 1.92 (0.04)
leaf symbols: memmove/memcpy (leaf) 0.02, malloc/free (leaf, tcmalloc) 2.44
top user self: [libc.so.6] 1.39, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.93, [[vdso]] 0.73, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.57, Envoy::Buffer::Slice::operator=(Envoy::Buffer::Slice&&) 0.47, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.46, event_queue_remove_timeout 0.45, operator_new[](unsigned_long) 0.45, quiche::BalsaFrame::ProcessHeaders(char_const*,_unsigned_long) 0.43, pthread_mutex_lock 0.40, event_add_nolock_ 0.39, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 0.38

## call graph: smoke-mech-kcg buf-32k/l64 hop A (pid 35669)

worker-thread cycles sampled: 3.64e+10 (of 4.12e+10 on these CPUs); user 52.0%, kernel 48.0%
syscall subtrees (inclusive, %% of worker cycles): writev 17.50, readv 12.01, sendto 5.70, epoll_wait 4.78, epoll_ctl 2.73, write 0.00
scheduling inside epoll_wait: 3.25%; self time of syscall entry and exit symbols: 3.91%
top kernel self: clear_page_erms 3.86, rep_movs_alternative 3.20, entry_SYSRETQ_unsafe_stack 1.79, syscall_return_via_sysret 0.70, entry_SYSCALL_64 0.58, __tcp_transmit_skb 0.57, check_heap_object 0.52, __raw_spin_lock_irqsave 0.48, skb_release_data 0.47, tcp_ack 0.39, __mod_memcg_state 0.39, __fdget 0.36, __skb_datagram_iter 0.36, tcp_in_window 0.35
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 33.86 (1.64), http1 bufferBody 0.28 (0.00), http1 dispatch (ConnectionImpl::dispatch) 41.26 (3.22), Buffer::OwnedImpl::add 0.07 (0.00), Buffer::OwnedImpl::move 0.68 (0.00), Buffer::OwnedImpl::read (socket read) 0.46 (0.00), timers (enableTimer / TimerImpl) 6.63 (3.78), readDisable 5.52 (3.79)
leaf symbols: memmove/memcpy (leaf) 0.02, malloc/free (leaf, tcmalloc) 2.04
top user self: [libc.so.6] 1.19, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.77, [[vdso]] 0.68, event_queue_remove_timeout 0.57, event_add_nolock_ 0.55, pthread_mutex_lock 0.50, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.45, pthread_mutex_unlock 0.41, event_del_nolock_ 0.40, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.38, Envoy::Buffer::Slice::operator=(Envoy::Buffer::Slice&&) 0.36, quiche::BalsaFrame::ProcessHeaders(char_const*,_unsigned_long) 0.35
