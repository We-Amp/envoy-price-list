
## syscalls: mech-sys-hop pair/s hop A (pid 32448, 104036 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.395, enter_epoll_wait 1.908, exit_epoll_wait 3.395, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 3.999, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.891 | 1.944 |
| epoll_wait | 3.304 | 0.000 |
| sendto | 0.974 | 0.000 |
| writev | 0.974 | 0.000 |
| **all** | **9.144** | **1.944** |

## syscalls: mech-sys-hop pair/s hop B (pid 32435, 104036 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.676, enter_epoll_wait 1.952, exit_epoll_wait 3.676, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.001, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.896 | 1.946 |
| epoll_wait | 3.582 | 0.000 |
| sendto | 0.975 | 0.000 |
| writev | 0.975 | 0.000 |
| **all** | **9.429** | **1.946** |

## syscalls: mech-sys-hop pair-l4/s hop A (pid 32582, 104034 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.405, enter_epoll_wait 1.923, exit_epoll_wait 3.406, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 3.999, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.896 | 1.946 |
| epoll_wait | 3.318 | 0.000 |
| writev | 0.976 | 0.000 |
| sendto | 0.975 | 0.000 |
| **all** | **9.165** | **1.947** |

## syscalls: mech-sys-hop pair-l4/s hop B (pid 32569, 104034 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.915, enter_epoll_wait 1.979, exit_epoll_wait 3.908, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.007, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.000, enter_sendto 1.999, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.899 | 1.945 |
| epoll_wait | 3.807 | 0.000 |
| sendto | 1.951 | 0.000 |
| **all** | **9.657** | **1.945** |

## syscalls: mech-sys-relay tcp/p64 hop A (pid 31832, 160033 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.711, enter_epoll_wait 1.921, exit_epoll_wait 3.711, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.000, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.000, enter_sendto 2.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.888 | 1.944 |
| epoll_wait | 3.609 | 0.000 |
| sendto | 1.949 | 0.000 |
| **all** | **9.447** | **1.944** |

## syscalls: mech-sys-relay http/p64 hop A (pid 31938, 160033 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 8.867, enter_epoll_wait 1.757, exit_epoll_wait 2.867, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.000, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.000, enter_sendto 2.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.895 | 1.947 |
| epoll_wait | 2.790 | 0.000 |
| sendto | 1.952 | 0.000 |
| **all** | **8.637** | **1.947** |

## syscalls: mech-sys-relay tcp/p1k hop A (pid 32042, 160033 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.698, enter_epoll_wait 1.926, exit_epoll_wait 3.698, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.000, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 0.000, enter_write 0.000, enter_sendto 2.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.887 | 1.941 |
| epoll_wait | 3.598 | 0.000 |
| sendto | 1.950 | 0.000 |
| **all** | **9.436** | **1.941** |

## syscalls: mech-sys-relay http/p1k hop A (pid 32146, 160033 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 8.678, enter_epoll_wait 1.725, exit_epoll_wait 2.678, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.000, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.896 | 1.947 |
| epoll_wait | 2.605 | 0.000 |
| writev | 0.976 | 0.000 |
| sendto | 0.976 | 0.000 |
| **all** | **8.453** | **1.947** |

## call graph: mech-kcg-hop pair/s hop A (pid 33641)

worker-thread cycles sampled: 5.5e+10 (of 6.07e+10 on these CPUs); user 66.6%, kernel 33.4%
syscall subtrees (inclusive, %% of worker cycles): writev 8.43, readv 7.61, sendto 7.21, epoll_wait 5.72
scheduling inside epoll_wait: 4.09%; self time of syscall entry and exit symbols: 3.05%
top kernel self: entry_SYSRETQ_unsafe_stack 1.20, rep_movs_alternative 0.83, syscall_return_via_sysret 0.50, entry_SYSCALL_64 0.48, __tcp_transmit_skb 0.42, __raw_spin_lock_irqsave 0.38, tcp_in_window 0.36, tcp_sendmsg_locked 0.35, psi_group_change 0.34, tcp_ack 0.34, __mod_memcg_state 0.33, tcp_recvmsg_locked 0.31, __nf_conntrack_find_get 0.30, apparmor_file_permission 0.30

## call graph: mech-kcg-hop pair/s hop B (pid 33628)

worker-thread cycles sampled: 5.62e+10 (of 6.16e+10 on these CPUs); user 65.9%, kernel 34.1%
syscall subtrees (inclusive, %% of worker cycles): readv 7.95, sendto 7.94, writev 7.78, epoll_wait 5.89
scheduling inside epoll_wait: 4.15%; self time of syscall entry and exit symbols: 3.08%
top kernel self: entry_SYSRETQ_unsafe_stack 1.25, rep_movs_alternative 0.59, syscall_return_via_sysret 0.54, __tcp_transmit_skb 0.42, entry_SYSCALL_64 0.42, psi_group_change 0.39, tcp_sendmsg_locked 0.36, __raw_spin_lock_irqsave 0.34, nf_conntrack_tcp_packet 0.33, page_counter_cancel 0.33, tcp_recvmsg_locked 0.33, __mod_memcg_state 0.31, kmem_cache_alloc_node 0.30, tcp_in_window 0.30

## call graph: mech-kcg-hop pair-l4/s hop A (pid 33777)

worker-thread cycles sampled: 5.42e+10 (of 5.99e+10 on these CPUs); user 66.5%, kernel 33.5%
syscall subtrees (inclusive, %% of worker cycles): writev 8.60, readv 7.46, sendto 7.38, epoll_wait 5.56, write 0.00
scheduling inside epoll_wait: 3.95%; self time of syscall entry and exit symbols: 3.07%
top kernel self: entry_SYSRETQ_unsafe_stack 1.28, rep_movs_alternative 0.92, entry_SYSCALL_64 0.51, syscall_return_via_sysret 0.49, __raw_spin_lock_irqsave 0.40, tcp_in_window 0.39, psi_group_change 0.34, __mod_memcg_state 0.34, tcp_recvmsg_locked 0.33, tcp_sendmsg_locked 0.33, aa_inet_msg_perm 0.32, __tcp_transmit_skb 0.31, __nf_conntrack_find_get 0.31, tcp_ack 0.30

## call graph: mech-kcg-hop pair-l4/s hop B (pid 33764)

worker-thread cycles sampled: 2.05e+10 (of 2.68e+10 on these CPUs); user 24.8%, kernel 75.2%
syscall subtrees (inclusive, %% of worker cycles): sendto 30.24, readv 21.63, epoll_wait 13.63, writev 0.03
scheduling inside epoll_wait: 9.52%; self time of syscall entry and exit symbols: 7.69%
top kernel self: entry_SYSRETQ_unsafe_stack 3.40, syscall_return_via_sysret 1.31, entry_SYSCALL_64 1.24, rep_movs_alternative 1.15, __raw_spin_lock_irqsave 1.00, __tcp_transmit_skb 0.94, tcp_sendmsg_locked 0.90, tcp_recvmsg_locked 0.80, page_counter_cancel 0.76, skb_release_data 0.75, tcp_ack 0.71, __nf_conntrack_find_get 0.70, psi_group_change 0.69, nf_nat_inet_fn 0.65

## call graph: mech-kcg-relay tcp/p64 hop A (pid 33145)

worker-thread cycles sampled: 2.47e+10 (of 3.1e+10 on these CPUs); user 22.6%, kernel 77.4%
syscall subtrees (inclusive, %% of worker cycles): sendto 32.02, readv 20.38, epoll_wait 14.06
scheduling inside epoll_wait: 10.08%; self time of syscall entry and exit symbols: 8.99%
top kernel self: entry_SYSRETQ_unsafe_stack 4.10, syscall_return_via_sysret 1.60, entry_SYSCALL_64 1.47, tcp_recvmsg_locked 1.05, __raw_spin_lock_irqsave 1.04, tcp_sendmsg_locked 0.98, __tcp_transmit_skb 0.97, __nf_conntrack_find_get 0.94, net_rx_action 0.90, tcp_ack 0.88, psi_group_change 0.86, skb_release_data 0.79, ep_poll 0.78, nf_conntrack_tcp_packet 0.76

## call graph: mech-kcg-relay http/p64 hop A (pid 33331)

worker-thread cycles sampled: 7.66e+10 (of 8.16e+10 on these CPUs); user 66.5%, kernel 33.5%
syscall subtrees (inclusive, %% of worker cycles): sendto 15.79, readv 8.68, epoll_wait 4.57
scheduling inside epoll_wait: 3.01%; self time of syscall entry and exit symbols: 3.10%
top kernel self: entry_SYSRETQ_unsafe_stack 1.37, entry_SYSCALL_64 0.52, tcp_recvmsg_locked 0.46, __raw_spin_lock_irqsave 0.45, syscall_return_via_sysret 0.45, tcp_sendmsg_locked 0.42, nf_conntrack_tcp_packet 0.38, __tcp_transmit_skb 0.38, tcp_in_window 0.36, tcp_ack 0.35, __fdget 0.35, __nf_conntrack_find_get 0.34, kmem_cache_alloc_node 0.33, net_rx_action 0.32
