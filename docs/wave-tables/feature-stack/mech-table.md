
## syscalls: mech-sys-stack bare/sx hop A (pid 75779, 104027 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.487, enter_epoll_wait 1.928, exit_epoll_wait 3.486, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.001, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.897 | 1.947 |
| epoll_wait | 3.398 | 0.000 |
| sendto | 0.975 | 0.000 |
| writev | 0.975 | 0.000 |
| **all** | **9.247** | **1.948** |

## syscalls: mech-sys-stack typical/sx hop A (pid 75884, 104030 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 12.336, enter_epoll_wait 1.871, exit_epoll_wait 3.207, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.007, exit_readv 2.003, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.002, enter_write 0.097, enter_sendto 1.002, enter_sendmsg 3.010, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.011

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.903 | 1.950 |
| epoll_wait | 3.123 | 0.000 |
| sendmsg | 2.935 | 0.000 |
| sendto | 0.977 | 0.000 |
| writev | 0.977 | 0.000 |
| write | 0.094 | 0.000 |
| futex | 0.011 | 0.000 |
| **all** | **12.021** | **1.950** |

## syscalls: smoke-mech-sys f0/s hop A (pid 62138, 104021 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.540, enter_epoll_wait 1.930, exit_epoll_wait 3.539, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.002, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.899 | 1.948 |
| epoll_wait | 3.449 | 0.000 |
| writev | 0.975 | 0.000 |
| sendto | 0.975 | 0.000 |
| **all** | **9.299** | **1.948** |

## syscalls: smoke-mech-sys f10/s hop A (pid 62243, 104021 responses in 20 s, leg valid: True)

tracepoint counts per request: enter 9.485, enter_epoll_wait 1.939, exit_epoll_wait 3.478, enter_epoll_pwait 0.000, exit_epoll_pwait 0.000, enter_epoll_pwait2 0.000, enter_readv 4.006, exit_readv 2.000, enter_read 0.000, exit_read 0.000, enter_recvfrom 0.000, exit_recvfrom 0.000, enter_recvmsg 0.000, enter_recvmmsg 0.000, enter_writev 1.000, enter_write 0.000, enter_sendto 1.000, enter_sendmsg 0.000, enter_epoll_ctl 0.000, enter_accept4 0.000, enter_close 0.000, enter_sendmmsg 0.000, exit_recvmsg 0.000, exit_recvmmsg 0.000, enter_epoll_ctl#2 0.000, enter_timerfd_settime 0.000, enter_futex 0.000

| syscall (perf trace -s, all threads) | calls /request | errors /request |
|---|---|---|
| readv | 3.903 | 1.947 |
| epoll_wait | 3.390 | 0.000 |
| writev | 0.975 | 0.000 |
| sendto | 0.975 | 0.000 |
| **all** | **9.244** | **1.947** |

## call graph: mech-kcg-chain f0/s hop A (pid 76751)

worker-thread cycles sampled: 5.54e+10 (of 6.1e+10 on these CPUs); user 64.6%, kernel 35.4%
syscall subtrees (inclusive, %% of worker cycles): writev 8.62, readv 8.40, sendto 7.96, epoll_wait 5.94
scheduling inside epoll_wait: 4.18%; self time of syscall entry and exit symbols: 2.99%
top kernel self: entry_SYSRETQ_unsafe_stack 1.22, rep_movs_alternative 0.87, syscall_return_via_sysret 0.55, entry_SYSCALL_64 0.46, __tcp_transmit_skb 0.42, __raw_spin_lock_irqsave 0.42, tcp_recvmsg_locked 0.40, tcp_sendmsg_locked 0.37, psi_group_change 0.34, tcp_in_window 0.33, page_counter_cancel 0.31, __nf_conntrack_find_get 0.31, nf_conntrack_tcp_packet 0.30, nf_nat_inet_fn 0.30
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 47.40 (0.40), http1 bufferBody 0.13 (0.00), http1 dispatch (ConnectionImpl::dispatch) 52.19 (0.53), Buffer::OwnedImpl::add 0.09 (0.00), Buffer::OwnedImpl::move 0.48 (0.01), Buffer::OwnedImpl::read (socket read) 0.56 (0.00), timers (enableTimer / TimerImpl) 2.20 (0.02)
leaf symbols: memmove/memcpy (leaf) 0.02, malloc/free (leaf, tcmalloc) 2.78
top user self: [libc.so.6] 1.55, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.03, [[vdso]] 0.78, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.62, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.60, operator_new[](unsigned_long) 0.57, pthread_mutex_lock 0.54, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 0.47, event_queue_remove_timeout 0.47, operator_delete[](void*,_unsigned_long) 0.43, event_add_nolock_ 0.42, quiche::BalsaFrame::ProcessHeaders(char_const*,_unsigned_long) 0.42

## call graph: mech-kcg-chain f10/s hop A (pid 76856)

worker-thread cycles sampled: 6.03e+10 (of 6.58e+10 on these CPUs); user 67.9%, kernel 32.1%
syscall subtrees (inclusive, %% of worker cycles): writev 8.10, readv 7.63, sendto 7.16, epoll_wait 5.38
scheduling inside epoll_wait: 3.76%; self time of syscall entry and exit symbols: 2.55%
top kernel self: entry_SYSRETQ_unsafe_stack 1.11, rep_movs_alternative 0.79, syscall_return_via_sysret 0.43, entry_SYSCALL_64 0.43, tcp_in_window 0.37, __tcp_transmit_skb 0.36, __raw_spin_lock_irqsave 0.33, tcp_sendmsg_locked 0.33, tcp_ack 0.33, __mod_memcg_state 0.33, tcp_recvmsg_locked 0.32, __nf_conntrack_find_get 0.32, nf_conntrack_tcp_packet 0.31, page_counter_cancel 0.30
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 50.60 (0.43), http1 bufferBody 0.09 (0.00), http1 dispatch (ConnectionImpl::dispatch) 55.14 (0.55), Buffer::OwnedImpl::add 0.07 (0.00), Buffer::OwnedImpl::move 0.40 (0.00), Buffer::OwnedImpl::read (socket read) 0.60 (0.00), timers (enableTimer / TimerImpl) 2.10 (0.02)
leaf symbols: memmove/memcpy (leaf) 0.02, malloc/free (leaf, tcmalloc) 3.44
top user self: [libc.so.6] 1.45, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.17, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.83, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.80, [[vdso]] 0.77, operator_new[](unsigned_long) 0.62, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 0.55, event_queue_remove_timeout 0.53, pthread_mutex_lock 0.50, operator_delete[](void*,_unsigned_long) 0.48, quiche::BalsaFrame::ProcessHeaders(char_const*,_unsigned_long) 0.45, Envoy::ConstSingleton<Envoy::Http::RequestHeaderMapImpl::HeaderHandleV 0.44

## call graph: mech-kcg-chain f0/fh hop A (pid 76964)

worker-thread cycles sampled: 4.54e+10 (of 5.13e+10 on these CPUs); user 69.8%, kernel 30.2%
syscall subtrees (inclusive, %% of worker cycles): sendto 16.64, epoll_wait 5.75, readv 3.31, write 0.00
scheduling inside epoll_wait: 3.98%; self time of syscall entry and exit symbols: 2.68%
top kernel self: entry_SYSRETQ_unsafe_stack 1.13, syscall_return_via_sysret 0.49, entry_SYSCALL_64 0.47, clear_page_erms 0.40, __raw_spin_lock_irqsave 0.39, tcp_recvmsg_locked 0.37, rep_movs_alternative 0.35, psi_group_change 0.33, ep_poll 0.32, tcp_sendmsg_locked 0.30, __fdget 0.28, nf_conntrack_tcp_packet 0.27, __tcp_transmit_skb 0.27, tcp_rcv_established 0.25
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 48.88 (0.55), http1 dispatch (ConnectionImpl::dispatch) 56.17 (0.57), Buffer::OwnedImpl::add 0.24 (0.01), Buffer::OwnedImpl::move 0.49 (0.03), Buffer::OwnedImpl::read (socket read) 0.70 (0.00), timers (enableTimer / TimerImpl) 2.35 (0.04)
leaf symbols: memmove/memcpy (leaf) 0.05, malloc/free (leaf, tcmalloc) 6.02
top user self: tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 2.30, [libc.so.6] 2.27, void_absl::lts_20260817::inlined_vector_internal::Storage<char,_128ul, 1.72, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 1.42, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.23, operator_new[](unsigned_long) 1.09, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 0.95, Envoy::Buffer::OwnedImpl::addFragments(absl::lts_20260817::Span<std::_ 0.94, operator_delete[](void*,_unsigned_long) 0.79, Envoy::Router::HeaderParser::evaluateHeaders(Envoy::Http::HeaderMap&,_ 0.77, [[vdso]] 0.76, Envoy::UnionStringBase<Envoy::Http::HeaderStringValidator>::setCopy(ch 0.71

## call graph: mech-kcg-chain f10/fh hop A (pid 77070)

worker-thread cycles sampled: 5.28e+10 (of 5.81e+10 on these CPUs); user 74.3%, kernel 25.7%
syscall subtrees (inclusive, %% of worker cycles): sendto 14.37, epoll_wait 5.01, readv 2.99
scheduling inside epoll_wait: 3.47%; self time of syscall entry and exit symbols: 2.37%
top kernel self: entry_SYSRETQ_unsafe_stack 0.97, entry_SYSCALL_64 0.43, syscall_return_via_sysret 0.39, clear_page_erms 0.38, __raw_spin_lock_irqsave 0.38, rep_movs_alternative 0.32, psi_group_change 0.32, tcp_recvmsg_locked 0.31, tcp_sendmsg_locked 0.29, __tcp_transmit_skb 0.29, aa_inet_msg_perm 0.28, __nf_conntrack_find_get 0.27, ep_poll 0.27, __fdget 0.23
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 53.55 (0.15), http1 dispatch (ConnectionImpl::dispatch) 59.75 (0.17), Buffer::OwnedImpl::add 0.20 (0.00), Buffer::OwnedImpl::move 0.44 (0.00), Buffer::OwnedImpl::read (socket read) 0.47 (0.00), timers (enableTimer / TimerImpl) 2.21 (0.01)
leaf symbols: memmove/memcpy (leaf) 0.04, malloc/free (leaf, tcmalloc) 6.59
top user self: tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 2.17, [libc.so.6] 2.06, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 1.58, void_absl::lts_20260817::inlined_vector_internal::Storage<char,_128ul, 1.55, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.52, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 1.22, operator_new[](unsigned_long) 1.17, operator_delete[](void*,_unsigned_long) 1.00, Envoy::Buffer::OwnedImpl::addFragments(absl::lts_20260817::Span<std::_ 0.80, Envoy::Router::HeaderParser::evaluateHeaders(Envoy::Http::HeaderMap&,_ 0.69, [[vdso]] 0.69, event_queue_remove_timeout 0.68

## call graph: mech-kcg-stack bare/sx hop A (pid 76318)

worker-thread cycles sampled: 5.66e+10 (of 6.22e+10 on these CPUs); user 66.3%, kernel 33.7%
syscall subtrees (inclusive, %% of worker cycles): readv 8.24, writev 8.17, sendto 7.61, epoll_wait 5.45
scheduling inside epoll_wait: 3.78%; self time of syscall entry and exit symbols: 2.86%
top kernel self: entry_SYSRETQ_unsafe_stack 1.25, rep_movs_alternative 0.85, syscall_return_via_sysret 0.48, entry_SYSCALL_64 0.46, __tcp_transmit_skb 0.43, tcp_sendmsg_locked 0.42, tcp_recvmsg_locked 0.39, __raw_spin_lock_irqsave 0.35, page_counter_cancel 0.33, __nf_conntrack_find_get 0.32, psi_group_change 0.31, tcp_in_window 0.30, tcp_ack 0.30, nf_conntrack_tcp_packet 0.30
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 49.29 (0.42), http1 bufferBody 0.13 (0.00), http1 dispatch (ConnectionImpl::dispatch) 54.16 (0.55), Buffer::OwnedImpl::add 0.06 (0.00), Buffer::OwnedImpl::move 0.45 (0.00), Buffer::OwnedImpl::read (socket read) 0.53 (0.00), timers (enableTimer / TimerImpl) 2.18 (0.01)
leaf symbols: memmove/memcpy (leaf) 0.03, malloc/free (leaf, tcmalloc) 2.85
top user self: [libc.so.6] 1.61, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.06, [[vdso]] 0.91, quiche::BalsaFrame::ProcessHeaders(char_const*,_unsigned_long) 0.72, quiche::header_properties::IsInvalidHeaderChar(unsigned_char) 0.69, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.63, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.60, http2::adapter::HeaderValidator::IsValidHeaderValue(std::__1::basic_st 0.60, operator_new[](unsigned_long) 0.59, quiche::BalsaFrame::FindColonsAndParseIntoKeyValue(std::__1::vector<st 0.55, pthread_mutex_lock 0.54, event_queue_remove_timeout 0.53

## call graph: mech-kcg-stack typical/sx hop A (pid 76424)

worker-thread cycles sampled: 7.94e+10 (of 8.42e+10 on these CPUs); user 67.4%, kernel 32.6%
syscall subtrees (inclusive, %% of worker cycles): sendmsg 7.16, readv 6.21, writev 6.07, sendto 5.23, epoll_wait 3.85
scheduling inside epoll_wait: 2.57%; self time of syscall entry and exit symbols: 2.76%
top kernel self: entry_SYSRETQ_unsafe_stack 1.23, rep_movs_alternative 0.71, syscall_return_via_sysret 0.48, entry_SYSCALL_64 0.43, kmem_cache_alloc_node 0.36, memset_orig 0.35, __tcp_transmit_skb 0.32, __nf_conntrack_find_get 0.31, nf_hook_slow 0.31, tcp_recvmsg_locked 0.30, nf_nat_inet_fn 0.30, tcp_sendmsg_locked 0.29, tcp_in_window 0.29, nf_conntrack_tcp_packet 0.29
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 61.24 (8.36), http1 bufferBody 0.09 (0.00), http1 dispatch (ConnectionImpl::dispatch) 64.72 (8.46), http2 dispatch 0.06 (0.01), Buffer::OwnedImpl::add 0.09 (0.00), Buffer::OwnedImpl::move 0.34 (0.00), Buffer::OwnedImpl::read (socket read) 0.47 (0.00), timers (enableTimer / TimerImpl) 1.88 (0.02)
leaf symbols: memmove/memcpy (leaf) 0.05, malloc/free (leaf, tcmalloc) 3.78
top user self: [libc.so.6] 1.99, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.28, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.86, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.84, [[vdso]] 0.79, operator_new[](unsigned_long) 0.77, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 0.72, quiche::BalsaFrame::ProcessHeaders(char_const*,_unsigned_long) 0.58, quiche::header_properties::IsInvalidHeaderChar(unsigned_char) 0.55, Envoy::ThreadLocal::InstanceImpl::SlotImpl::get() 0.48, operator_delete[](void*,_unsigned_long) 0.48, http2::adapter::HeaderValidator::IsValidHeaderValue(std::__1::basic_st 0.47

## call graph: smoke-mech-kcg f0/s hop A (pid 62534)

worker-thread cycles sampled: 5.55e+10 (of 6.12e+10 on these CPUs); user 64.8%, kernel 35.2%
syscall subtrees (inclusive, %% of worker cycles): writev 8.71, readv 8.46, sendto 7.87, epoll_wait 5.85
scheduling inside epoll_wait: 4.15%; self time of syscall entry and exit symbols: 2.78%
top kernel self: entry_SYSRETQ_unsafe_stack 1.17, rep_movs_alternative 0.80, syscall_return_via_sysret 0.53, entry_SYSCALL_64 0.48, tcp_recvmsg_locked 0.42, __tcp_transmit_skb 0.40, __raw_spin_lock_irqsave 0.36, tcp_sendmsg_locked 0.36, tcp_ack 0.35, psi_group_change 0.35, nf_conntrack_tcp_packet 0.34, tcp_in_window 0.33, __nf_conntrack_find_get 0.33, __mod_memcg_state 0.30
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 47.56 (0.45), http1 bufferBody 0.11 (0.00), http1 dispatch (ConnectionImpl::dispatch) 52.48 (0.58), Buffer::OwnedImpl::add 0.09 (0.00), Buffer::OwnedImpl::move 0.45 (0.01), Buffer::OwnedImpl::read (socket read) 0.54 (0.01), timers (enableTimer / TimerImpl) 2.42 (0.02)
leaf symbols: memmove/memcpy (leaf) 0.02, malloc/free (leaf, tcmalloc) 2.96
top user self: [libc.so.6] 1.79, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.06, [[vdso]] 0.89, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.64, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.62, event_queue_remove_timeout 0.58, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 0.56, operator_new[](unsigned_long) 0.55, pthread_mutex_lock 0.53, quiche::BalsaFrame::FindColonsAndParseIntoKeyValue(std::__1::vector<st 0.47, event_add_nolock_ 0.47, quiche::BalsaFrame::ProcessHeaders(char_const*,_unsigned_long) 0.45

## call graph: smoke-mech-kcg f10/s hop A (pid 62640)

worker-thread cycles sampled: 6.12e+10 (of 6.67e+10 on these CPUs); user 68.6%, kernel 31.4%
syscall subtrees (inclusive, %% of worker cycles): writev 7.91, readv 7.48, sendto 7.04, epoll_wait 5.02
scheduling inside epoll_wait: 3.46%; self time of syscall entry and exit symbols: 2.56%
top kernel self: entry_SYSRETQ_unsafe_stack 1.11, rep_movs_alternative 0.81, syscall_return_via_sysret 0.43, entry_SYSCALL_64 0.40, tcp_sendmsg_locked 0.34, __tcp_transmit_skb 0.34, nf_conntrack_tcp_packet 0.33, tcp_recvmsg_locked 0.33, __nf_conntrack_find_get 0.33, __raw_spin_lock_irqsave 0.33, psi_group_change 0.31, tcp_in_window 0.30, page_counter_cancel 0.29, nf_nat_inet_fn 0.29
user frames, inclusive (kernel part inside): http1 parser (BalsaFrame::ProcessInput) 51.08 (0.48), http1 bufferBody 0.11 (0.00), http1 dispatch (ConnectionImpl::dispatch) 55.82 (0.56), Buffer::OwnedImpl::add 0.07 (0.00), Buffer::OwnedImpl::move 0.40 (0.00), Buffer::OwnedImpl::read (socket read) 0.52 (0.01), timers (enableTimer / TimerImpl) 2.12 (0.01)
leaf symbols: memmove/memcpy (leaf) 0.03, malloc/free (leaf, tcmalloc) 3.37
top user self: [libc.so.6] 1.55, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 1.27, [[vdso]] 0.80, tcmalloc::tcmalloc_internal::FreeWithHooksOrPerThread(void*,_std::__1: 0.73, tcmalloc::tcmalloc_internal::TCMallocPolicy<tcmalloc::tcmalloc_interna 0.70, operator_new[](unsigned_long) 0.64, tcmalloc::tcmalloc_internal::FreeSmallSlow(void*,_std::__1::optional<u 0.60, event_queue_remove_timeout 0.57, pthread_mutex_lock 0.51, operator_delete[](void*,_unsigned_long) 0.45, Envoy::ConstSingleton<Envoy::Http::RequestHeaderMapImpl::HeaderHandleV 0.43, quiche::BalsaFrame::ProcessHeaders(char_const*,_unsigned_long) 0.42
