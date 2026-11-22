# Wave 3, track F: HTTP/2, gRPC and TLS upstreams, and mTLS between hops

What the upstream protocol costs Envoy v1.40.2 per request (HTTP/1.1, HTTP/2 cleartext with nghttp2 or
oghttp2, TLS with HTTP/1.1 or HTTP/2), what a unary gRPC call and the grpc_stats filter cost, and how a
two-hop chain's price splits when the hops talk mTLS. Config only: the official binary in every arm.
Data: the `upstream-protocols` archive of the wave studies
(`python3 tools/fetch-wave-data.py upstream-protocols`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Bench box: two-socket Xeon E5-2673 v4 (2 x 20 cores, SMT on), bare metal, 2.3 GHz fixed, turbo off.
  Envoy on CPUs 0-3 (4 workers) with their SMT siblings idle; the second hop of `f3-mtls` on 4-7;
  client on 20-31,60-71; origin (`nginx:alpine`, pinned digest, and the harness's gRPC responder) on
  32-39,72-79. Every listener, admin address, cluster address and origin server binds to loopback
  (a test checks this for every config).
- Binaries: the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…`) in every arm and
  on both hops; Nighthawk 0.3.0 with `--request-body-file` as the client (`chain-f.sh` stops when the
  client lacks it; `make.py --no-body-file` writes configs for such a client).
- Certificates (TLS and mTLS arms) are generated per run directory by the harness (ECDSA P-256 with DNS
  SANs, verified by name both ways for mTLS); they are not part of the published data.
- Every arm that can run oghttp2 carries the same `layered_runtime` static layer with the oghttp2 key
  written out, false or true, so the runtime structure is the same in every arm.
- Order: Williams squares, paired rounds; the effect is the mean per-round log ratio with the 95% t
  interval and the widened interval 1.96 x sqrt(SE^2 + 0.34^2); Holm over the confirmatory rows fixed
  before the run (`table.py`).

## Runs

| Config | Arms | Shape | Rounds |
|---|---|---|---|
| `configs/f1-upstream.json` | `h1` (base), `h1-A2`, `h2c` (nghttp2), `h2c-og` (oghttp2), `tls-h1`, `tls-h2` | `s`: HTTP/1.1 GET, 4 KB proxied, 5,200 req/s | 6 |
| `configs/f2-grpc.json` | `grpc` (router only, base), `grpc-A2`, `grpc-stats` (per-method stats), `grpc-og` (oghttp2 on both sides) | `g`: HTTP/2 client, unary gRPC POST, 66-byte request (`grpc-unary-request.bin`), 4,096-byte response plus the grpc-status trailer, 5,200 req/s; h2c upstream | 8 |
| `configs/f3-mtls.json` | `one-ppd` (one hop), `pair` (two hops, plaintext between them; base), `pair-A2`, `pair-mtls` (ECDSA P-256 mTLS between the hops, client certificate required); one upstream pool per downstream connection on every hop; primary metric the cycles of both hops per request | `s` | 8 |

Each `configs/smoke-*.json` is one round of every arm, evidence recorded.

## Files

- `make.py` writes the configs (`python3 examples/wave3f/make.py [--no-body-file]`).
- `run-f.sh smoke|queue RUN`, `chain-f.sh`: the sessions as run (`F_RUNS` picks the runs).
- `local_check.py validate|functional WORKDIR`: checks of every arm with the official v1.40.2 image in
  Docker, off the bench box (certificates made as the harness makes them); no measurement.
- `table.py RUN_DIR [METRIC ...]`: every paired comparison of a run, and the confirmatory rows with
  Holm-adjusted p.

The commands that render every table from the data are in [`docs/wave-studies.md`](../../docs/wave-studies.md).
