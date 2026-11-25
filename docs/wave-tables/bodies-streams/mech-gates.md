## syscalls per streamed event: (per request on the 200-event shape - on the 20-event shape) / 180

| run / arm | all syscalls | readv | readv returning EAGAIN | sendto | writev | epoll_wait | epoll_wait with timeout 0 | epoll_ctl |
|---|---|---|---|---|---|---|---|---|
| mech-sys-stream base | 4.553 | 2.000 | 1.000 | 1.000 | 0.000 | 1.554 | 0.893 | 0.000 |
| mech-sys-stream idle-off | 4.539 | 2.000 | 1.000 | 1.000 | 0.000 | 1.539 | 0.891 | 0.000 |
| mech-sys-grpc base | 4.190 | 1.787 | 0.862 | 0.865 | 0.000 | 1.538 | 0.802 | 0.000 |
| mech-sys-grpc base-A2 | 4.278 | 1.820 | 0.887 | 0.851 | 0.000 | 1.606 | 0.818 | 0.000 |

count gate on base, per event: all in [4.5, 5.5]: met; EAGAIN readv >= 0.9: met; zero-timeout epoll_wait >= 0.9: NOT met
price of the two avoidable calls, share of worker cycles on base/ev200 (99% of them are event work): lower 3.5% (2 x 8.03% entry and exit self time / 4.55 calls), upper 15.4% (plan rule), 11.8% (stricter); midpoints 9.5% / 7.6%; 3% line

## buffer limit: per request (syscall legs)

| shape | arm | all syscalls | epoll_ctl | upstream pauses | upstream resumes | downstream pauses | readv | writev | epoll_wait | of which timeout 0 | cycles per request (this leg, under the tracer) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| l1m | buf-32k | 153.26 | 67.95 | 16.988 | 16.000 | 0.000 | 36.02 | 17.00 | 31.28 | 29.17 | 5239k |
| l1m | buf-default | 28.56 | 4.00 | 1.000 | 1.000 | 0.000 | 12.04 | 4.00 | 5.52 | 3.72 | 3017k |
| l64 | buf-32k | 23.49 | 8.00 | 1.999 | 1.000 | 0.000 | 6.00 | 2.00 | 6.49 | 3.87 | 1141k |
| l64 | buf-default | 10.01 | 0.00 | 0.000 | 0.000 | 0.000 | 4.00 | 1.00 | 4.01 | 2.00 | 876k |
| m | buf-4k | 24.48 | 12.00 | 2.000 | 1.982 | 0.000 | 2.00 | 1.00 | 4.50 | 3.32 | 861k |
| m | buf-default | 9.51 | 0.00 | 0.000 | 0.000 | 0.000 | 4.00 | 1.00 | 3.51 | 1.93 | 641k |

## HTTP/3 at 4 KB: syscalls per request

| arm | all | recvmmsg | recvmmsg returning EAGAIN | sendmsg | sendmmsg | recvfrom | readv | sendto | epoll_wait | epoll_wait with timeout 0 |
|---|---|---|---|---|---|---|---|---|---|---|
| h2tls | 11.03 | 0.00 | 0.00 | 0.00 | 0.00 | 3.00 | 2.00 | 2.00 | 4.03 | 2.00 |
| h3 | 17.35 | 4.00 | 2.00 | 5.02 | 0.00 | 0.00 | 2.00 | 1.00 | 5.33 | 1.00 |

h3/4 KB profile, share of worker-thread cycles (inclusive): handleReadCallback 40.26%, readPacketsFromSocket 39.40%, readFromSocket 38.77%, passPayloadToProcessor 27.50%, sendmsg syscall (kernel) 9.80%, IoSocketHandleImpl::recvmmsg 4.39%, recvmmsg syscall (kernel) 2.06%
receive path = readFromSocket - passPayloadToProcessor = **11.27%** of worker cycles (of which the recvmmsg call 4.39%, its kernel part 2.06%; the rest is buffer set-up and tear-down around the call); 2% line

## chunked at 1 MiB: the libc copy (leaf [libc.so.6]) and its callers, share of worker-thread cycles

cl8k: libc leaf 0.41%; top callers: Envoy::Api::OsSysCallsImpl::readv <- Envoy::Network::IoSocketHandleImpl::readv 0.10%; epoll_dispatch <- event_base_loop 0.05%; inclusive: Http1::ConnectionImpl::dispatch( 12.20%, BalsaFrame::ProcessInput 9.01%, Buffer::OwnedImpl::move( 1.24%, bufferBody 0.47%, Buffer::OwnedImpl::addImpl 0.02%
ch8k: libc leaf 5.95%; top callers: quiche::BalsaFrame::ProcessInput <- nvoy::Http::Http1::ConnectionImpl::dispatchSlice 5.47%; Envoy::Api::OsSysCallsImpl::readv <- Envoy::Network::IoSocketHandleImpl::readv 0.08%; inclusive: Http1::ConnectionImpl::dispatch( 19.68%, BalsaFrame::ProcessInput 15.64%, Buffer::OwnedImpl::move( 1.47%, Buffer::OwnedImpl::addImpl 1.06%, bufferBody 0.09%
