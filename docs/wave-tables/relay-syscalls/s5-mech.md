
## mech-load-h2-16k

| arm / shape | rate, req/s (2xx/s at the client) | per relayed message: all syscalls | readv (+recvfrom) | returning EAGAIN | sendto | writev + sendmsg + write | epoll_wait | with timeout 0 | epoll_ctl | bytes per send call | Envoy busy under the tracer (CPUs of 4) | cycles u+k per request under the tracer | leg valid | guards at start / end | MPTCP sockets on the box, TCP sockets on the listener port, to the origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official / h64 | 16000 (16000) | 6.605 | 2.846 (+0.000) | 1.349 | 1.320 | 0.000 | 2.440 | 1.254 | 0.0000 | 81.1 | 1.4787 | 187.3k | True | {"sr": -1, "wr": -1} / {"sr": -1, "wr": -1} | 0, 16, 16 |
| patched-off / h64 | 16000 (16000) | 6.166 | 2.769 (+0.000) | 1.285 | 1.262 | 0.000 | 2.135 | 1.135 | 0.0000 | 84.8 | 1.411 | 180.3k | True | {"sr": 0, "wr": 0} / {"sr": 0, "wr": 0} | 0, 16, 16 |
| read-only / h64 | 16000 (16000) | 5.084 | 1.499 (+0.000) | 0.000 | 1.264 | 0.000 | 2.321 | 1.196 | 0.0000 | 84.7 | 1.4275 | 176.4k | True | {"sr": 1, "wr": 0} / {"sr": 1, "wr": 0} | 0, 16, 16 |
| write-only / h64 | 16000 (16000) | 5.411 | 2.780 (+0.000) | 1.283 | 1.283 | 0.000 | 1.348 | 0.000 | 0.0000 | 83.4 | 1.4536 | 182.8k | True | {"sr": 0, "wr": 1} / {"sr": 0, "wr": 1} | 0, 16, 16 |
| both-on / h64 | 16000 (16000) | 4.297 | 1.496 (+0.000) | 0.000 | 1.496 | 0.000 | 1.305 | 0.000 | 0.0000 | 71.8 | 1.4225 | 179.2k | True | {"sr": 1, "wr": 1} / {"sr": 1, "wr": 1} | 0, 16, 16 |

## mech-load-h2-32k

| arm / shape | rate, req/s (2xx/s at the client) | per relayed message: all syscalls | readv (+recvfrom) | returning EAGAIN | sendto | writev + sendmsg + write | epoll_wait | with timeout 0 | epoll_ctl | bytes per send call | Envoy busy under the tracer (CPUs of 4) | cycles u+k per request under the tracer | leg valid | guards at start / end | MPTCP sockets on the box, TCP sockets on the listener port, to the origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official / h64 | 32000 (32000) | 5.906 | 2.765 (+0.000) | 1.280 | 1.245 | 0.000 | 1.896 | 1.060 | 0.0000 | 86.1 | 2.4241 | 159.0k | True | {"sr": -1, "wr": -1} / {"sr": -1, "wr": -1} | 0, 16, 16 |
| patched-off / h64 | 32000 (32000) | 6.017 | 2.807 (+0.000) | 1.312 | 1.279 | 0.000 | 1.931 | 1.091 | 0.0000 | 83.7 | 2.4943 | 165.2k | True | {"sr": 0, "wr": 0} / {"sr": 0, "wr": 0} | 0, 16, 16 |
| read-only / h64 | 32000 (32000) | 4.597 | 1.497 (+0.000) | 0.000 | 1.268 | 0.000 | 1.832 | 1.028 | 0.0000 | 84.5 | 2.2279 | 145.5k | True | {"sr": 1, "wr": 0} / {"sr": 1, "wr": 0} | 0, 16, 16 |
| write-only / h64 | 32000 (32000) | 5.275 | 2.772 (+0.000) | 1.273 | 1.273 | 0.000 | 1.230 | 0.000 | 0.0000 | 84.0 | 2.5924 | 166.6k | True | {"sr": 0, "wr": 1} / {"sr": 0, "wr": 1} | 0, 16, 16 |
| both-on / h64 | 32000 (32000) | 4.197 | 1.500 (+0.000) | 0.000 | 1.500 | 0.000 | 1.198 | 0.000 | 0.0000 | 71.4 | 2.5045 | 161.7k | True | {"sr": 1, "wr": 1} / {"sr": 1, "wr": 1} | 0, 16, 16 |

## mech-load-h2-48k

| arm / shape | rate, req/s (2xx/s at the client) | per relayed message: all syscalls | readv (+recvfrom) | returning EAGAIN | sendto | writev + sendmsg + write | epoll_wait | with timeout 0 | epoll_ctl | bytes per send call | Envoy busy under the tracer (CPUs of 4) | cycles u+k per request under the tracer | leg valid | guards at start / end | MPTCP sockets on the box, TCP sockets on the listener port, to the origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official / h64 | 48000 (47999) | 5.562 | 2.769 (+0.000) | 1.279 | 1.239 | 0.000 | 1.554 | 0.952 | 0.0000 | 86.4 | 3.2417 | 146.1k | True | {"sr": -1, "wr": -1} / {"sr": -1, "wr": -1} | 0, 16, 16 |
| patched-off / h64 | 48000 (47999) | 5.598 | 2.770 (+0.000) | 1.281 | 1.237 | 0.000 | 1.590 | 0.972 | 0.0000 | 86.5 | 3.3641 | 152.9k | True | {"sr": 0, "wr": 0} / {"sr": 0, "wr": 0} | 0, 16, 16 |
| read-only / h64 | 48000 (48000) | 4.512 | 1.482 (+0.000) | 0.000 | 1.248 | 0.000 | 1.783 | 1.030 | 0.0000 | 85.7 | 3.1317 | 138.0k | True | {"sr": 1, "wr": 0} / {"sr": 1, "wr": 0} | 0, 16, 16 |
| write-only / h64 | 48000 (47999) | 4.996 | 2.745 (+0.000) | 1.260 | 1.260 | 0.000 | 0.992 | 0.000 | 0.0000 | 84.9 | 3.2156 | 142.6k | True | {"sr": 0, "wr": 1} / {"sr": 0, "wr": 1} | 0, 16, 16 |
| both-on / h64 | 48000 (47999) | 3.883 | 1.468 (+0.000) | 0.000 | 1.468 | 0.000 | 0.947 | 0.000 | 0.0000 | 72.9 | 3.1355 | 140.8k | True | {"sr": 1, "wr": 1} / {"sr": 1, "wr": 1} | 0, 16, 16 |

## mech-load-p64-16k

| arm / shape | rate, req/s (2xx/s at the client) | per relayed message: all syscalls | readv (+recvfrom) | returning EAGAIN | sendto | writev + sendmsg + write | epoll_wait | with timeout 0 | epoll_ctl | bytes per send call | Envoy busy under the tracer (CPUs of 4) | cycles u+k per request under the tracer | leg valid | guards at start / end | MPTCP sockets on the box, TCP sockets on the listener port, to the origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official / p64 | 16000 (16000) | 4.767 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 1.767 | 0.922 | 0.0000 | 135.0 | 1.1793 | 141.4k | False (client overflow/pool-exhausted counters 169 (upstream_cx_overflow=169); client pending total 126 above 16 (queue absorbed a burst)) | {"sr": -1, "wr": -1} / {"sr": -1, "wr": -1} | 0, 512, 512 |
| patched-off / p64 | 16000 (16000) | 4.709 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 1.709 | 0.903 | 0.0000 | 135.0 | 1.1672 | 141.2k | False (client overflow/pool-exhausted counters 277 (upstream_cx_overflow=277); client pending total 209 above 16 (queue absorbed a burst)) | {"sr": 0, "wr": 0} / {"sr": 0, "wr": 0} | 0, 512, 512 |
| read-only / p64 | 16000 (16000) | 3.753 | 1.000 (+0.000) | 0.000 | 1.000 | 0.000 | 1.754 | 0.912 | 0.0000 | 135.0 | 1.1406 | 135.9k | False (client overflow/pool-exhausted counters 196 (upstream_cx_overflow=196); client pending total 156 above 16 (queue absorbed a burst)) | {"sr": 1, "wr": 0} / {"sr": 1, "wr": 0} | 0, 512, 512 |
| write-only / p64 | 16000 (16000) | 3.912 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 0.913 | 0.000 | 0.0000 | 135.0 | 1.163 | 139.0k | False (client overflow/pool-exhausted counters 90 (upstream_cx_overflow=90); client pending total 71 above 16 (queue absorbed a burst)) | {"sr": 0, "wr": 1} / {"sr": 0, "wr": 1} | 0, 512, 512 |
| both-on / p64 | 16000 (16000) | 2.931 | 1.000 (+0.000) | 0.000 | 1.000 | 0.000 | 0.931 | 0.000 | 0.0000 | 135.0 | 1.1064 | 128.3k | False (client overflow/pool-exhausted counters 85 (upstream_cx_overflow=85); client pending total 69 above 16 (queue absorbed a burst)) | {"sr": 1, "wr": 1} / {"sr": 1, "wr": 1} | 0, 512, 512 |

## mech-load-p64-24k

| arm / shape | rate, req/s (2xx/s at the client) | per relayed message: all syscalls | readv (+recvfrom) | returning EAGAIN | sendto | writev + sendmsg + write | epoll_wait | with timeout 0 | epoll_ctl | bytes per send call | Envoy busy under the tracer (CPUs of 4) | cycles u+k per request under the tracer | leg valid | guards at start / end | MPTCP sockets on the box, TCP sockets on the listener port, to the origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official / p64 | 24000 (24000) | 4.678 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 1.679 | 0.898 | 0.0000 | 135.0 | 1.6211 | 132.9k | False (client overflow/pool-exhausted counters 444 (upstream_cx_overflow=444); client pending total 295 above 16 (queue absorbed a burst)) | {"sr": -1, "wr": -1} / {"sr": -1, "wr": -1} | 0, 512, 512 |
| patched-off / p64 | 24000 (24000) | 4.661 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 1.662 | 0.893 | 0.0000 | 135.0 | 1.5993 | 131.3k | False (client overflow/pool-exhausted counters 463 (upstream_cx_overflow=463); client pending total 292 above 16 (queue absorbed a burst)) | {"sr": 0, "wr": 0} / {"sr": 0, "wr": 0} | 0, 512, 512 |
| read-only / p64 | 24000 (24000) | 3.734 | 1.000 (+0.000) | 0.000 | 1.000 | 0.000 | 1.734 | 0.909 | 0.0000 | 135.0 | 1.5571 | 124.8k | False (client overflow/pool-exhausted counters 488 (upstream_cx_overflow=488); client pending total 358 above 16 (queue absorbed a burst)) | {"sr": 1, "wr": 0} / {"sr": 1, "wr": 0} | 0, 512, 512 |
| write-only / p64 | 24000 (24000) | 3.899 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 0.899 | 0.000 | 0.0000 | 135.0 | 1.558 | 126.0k | False (client overflow/pool-exhausted counters 501 (upstream_cx_overflow=501); client pending total 321 above 16 (queue absorbed a burst)) | {"sr": 0, "wr": 1} / {"sr": 0, "wr": 1} | 0, 512, 512 |
| both-on / p64 | 24000 (24000) | 2.887 | 1.000 (+0.000) | 0.000 | 1.000 | 0.000 | 0.887 | 0.000 | 0.0000 | 135.0 | 1.5055 | 120.5k | False (client overflow/pool-exhausted counters 471 (upstream_cx_overflow=471); client pending total 381 above 16 (queue absorbed a burst)) | {"sr": 1, "wr": 1} / {"sr": 1, "wr": 1} | 0, 512, 512 |

## mech-load-p64-32k

| arm / shape | rate, req/s (2xx/s at the client) | per relayed message: all syscalls | readv (+recvfrom) | returning EAGAIN | sendto | writev + sendmsg + write | epoll_wait | with timeout 0 | epoll_ctl | bytes per send call | Envoy busy under the tracer (CPUs of 4) | cycles u+k per request under the tracer | leg valid | guards at start / end | MPTCP sockets on the box, TCP sockets on the listener port, to the origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official / p64 | 32000 (32000) | 4.571 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 1.571 | 0.866 | 0.0000 | 135.0 | 1.9966 | 125.3k | False (client overflow/pool-exhausted counters 1198 (upstream_cx_overflow=1198); client pending total 710 above 16 (queue absorbed a burst)) | {"sr": -1, "wr": -1} / {"sr": -1, "wr": -1} | 0, 512, 512 |
| patched-off / p64 | 32000 (32000) | 4.585 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 1.586 | 0.871 | 0.0000 | 135.0 | 1.9699 | 122.9k | False (client overflow/pool-exhausted counters 873 (upstream_cx_overflow=873); client pending total 549 above 16 (queue absorbed a burst)) | {"sr": 0, "wr": 0} / {"sr": 0, "wr": 0} | 0, 512, 512 |
| read-only / p64 | 32000 (32000) | 3.560 | 1.000 (+0.000) | 0.000 | 1.000 | 0.000 | 1.560 | 0.848 | 0.0000 | 135.0 | 1.9705 | 122.9k | False (client overflow/pool-exhausted counters 819 (upstream_cx_overflow=819); client pending total 529 above 16 (queue absorbed a burst)) | {"sr": 1, "wr": 0} / {"sr": 1, "wr": 0} | 0, 512, 512 |
| write-only / p64 | 32000 (32000) | 3.811 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 0.811 | 0.000 | 0.0000 | 135.0 | 1.8545 | 116.3k | False (client overflow/pool-exhausted counters 917 (upstream_cx_overflow=917); client pending total 680 above 16 (queue absorbed a burst)) | {"sr": 0, "wr": 1} / {"sr": 0, "wr": 1} | 0, 512, 512 |
| both-on / p64 | 32000 (32000) | 2.836 | 1.000 (+0.000) | 0.000 | 1.000 | 0.000 | 0.836 | 0.000 | 0.0000 | 135.0 | 1.8015 | 110.6k | False (client overflow/pool-exhausted counters 760 (upstream_cx_overflow=760); client pending total 539 above 16 (queue absorbed a burst)) | {"sr": 1, "wr": 1} / {"sr": 1, "wr": 1} | 0, 512, 512 |

## mech-sys-http

| arm / shape | rate, req/s (2xx/s at the client) | per relayed message: all syscalls | readv (+recvfrom) | returning EAGAIN | sendto | writev + sendmsg + write | epoll_wait | with timeout 0 | epoll_ctl | bytes per send call | Envoy busy under the tracer (CPUs of 4) | cycles u+k per request under the tracer | leg valid | guards at start / end | MPTCP sockets on the box, TCP sockets on the listener port, to the origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official / s | 5200 (5200) | 4.817 | 2.009 (+0.000) | 1.001 | 0.500 | 0.500 | 1.808 | 0.966 | 0.0000 | 2256.0 | 1.3117 | 545.4k | True | {"sr": -1, "wr": -1} / {"sr": -1, "wr": -1} | 0, 512, 219 |
| patched-off / s | 5200 (5200) | 4.795 | 2.008 (+0.000) | 1.001 | 0.500 | 0.500 | 1.787 | 0.960 | 0.0000 | 2256.0 | 1.3089 | 544.9k | True | {"sr": 0, "wr": 0} / {"sr": 0, "wr": 0} | 0, 512, 318 |
| read-only / s | 5200 (5200) | 3.778 | 1.007 (+0.000) | 0.000 | 0.500 | 0.500 | 1.770 | 0.961 | 0.0000 | 2256.0 | 1.2799 | 532.9k | True | {"sr": 1, "wr": 0} / {"sr": 1, "wr": 0} | 0, 512, 295 |
| write-only / s | 5200 (5200) | 4.080 | 2.003 (+0.000) | 1.000 | 0.500 | 0.500 | 1.076 | 0.000 | 0.0000 | 2255.5 | 1.2892 | 535.5k | True | {"sr": 0, "wr": 1} / {"sr": 0, "wr": 1} | 0, 512, 278 |
| both-on / s | 5200 (5200) | 3.044 | 1.005 (+0.000) | 0.000 | 0.509 | 0.495 | 1.034 | 0.000 | 0.0000 | 2245.7 | 1.2639 | 526.5k | True | {"sr": 1, "wr": 1} / {"sr": 1, "wr": 1} | 0, 512, 364 |

## mech-sys-relay

| arm / shape | rate, req/s (2xx/s at the client) | per relayed message: all syscalls | readv (+recvfrom) | returning EAGAIN | sendto | writev + sendmsg + write | epoll_wait | with timeout 0 | epoll_ctl | bytes per send call | Envoy busy under the tracer (CPUs of 4) | cycles u+k per request under the tracer | leg valid | guards at start / end | MPTCP sockets on the box, TCP sockets on the listener port, to the origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| official / p64 | 8000 (8000) | 4.878 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 1.879 | 0.959 | 0.0000 | 135.0 | 0.7051 | 160.9k | True | {"sr": -1, "wr": -1} / {"sr": -1, "wr": -1} | 0, 512, 512 |
| patched-off / p64 | 8000 (8000) | 4.875 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 1.875 | 0.958 | 0.0000 | 135.0 | 0.7042 | 160.7k | True | {"sr": 0, "wr": 0} / {"sr": 0, "wr": 0} | 0, 512, 512 |
| read-only / p64 | 8000 (8000) | 3.917 | 1.000 (+0.000) | 0.000 | 1.000 | 0.000 | 1.917 | 0.971 | 0.0000 | 135.0 | 0.6813 | 152.1k | True | {"sr": 1, "wr": 0} / {"sr": 1, "wr": 0} | 0, 512, 512 |
| write-only / p64 | 8000 (8000) | 3.954 | 2.000 (+0.000) | 1.000 | 1.000 | 0.000 | 0.954 | 0.000 | 0.0000 | 135.0 | 0.6856 | 155.6k | True | {"sr": 0, "wr": 1} / {"sr": 0, "wr": 1} | 0, 512, 512 |
| both-on / p64 | 8000 (8000) | 2.961 | 1.000 (+0.000) | 0.000 | 1.000 | 0.000 | 0.961 | 0.000 | 0.0000 | 135.0 | 0.6619 | 147.7k | True | {"sr": 1, "wr": 1} / {"sr": 1, "wr": 1} | 0, 512, 512 |
