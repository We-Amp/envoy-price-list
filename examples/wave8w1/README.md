# Wave 8, session W8-1: an HTTP/1 chunked body handed on as fragments instead of a copy

What it would save if Envoy stopped copying a chunked HTTP/1 response body and handed the chunks on as buffer
fragments: CPU cycles of the Envoy process per request on 1 MiB and 64 KiB chunked responses from a streaming
origin, on a 64 KiB response that nginx itself sends chunked, and on a 1 MiB chunked upstream delivered as
HTTP/2 over TLS. A rider prices an HTTP/2 cleartext upstream against HTTP/1.1 on the official binary. Data: the
`chunked-copy` archive of the fourth wave release (`python3 tools/fetch-wave-data.py chunked-copy`, see
[`docs/wave-studies.md`](../../docs/wave-studies.md)).

The tail add-on that ran after this session (`chain-tail.sh`, `tail_check.py`, configs `tail-*.json`) is not
part of W8-1: it counts server-side QUIC retransmissions for session W8-2 (`examples/wave8w2`), and its records
are in the `http3-receive` archive under `tail-w8-1/`.

## Conditions

- Box: the bench box of the earlier waves (label `bench-x86_64`: two Xeon E5-2673 v4, bare metal, fixed
  2.3 GHz, turbo off, default idle states); Envoy on CPUs 0-3 with their SMT siblings idle, client on
  20-31,60-71, origin on 32-39,72-79, the tracer on 8-19.
- Binaries (`bins.json`): the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…f03cc`) and
  `w8-A`, an own build of v1.40.2 with the chunked-body commits and the two UDP receive commits of
  `examples/wave8w2`, each behind a runtime guard (sha256 `46c98673…d3971`; an unpatched twin of the same
  recipe is byte-identical to the official binary). Neither the build nor the chunked patch is published.
  Nighthawk 0.3.0; origins: the stream origin (`tools/streamorigin`, wave 7 S2's) and `nginx:alpine` pinned by
  digest.
- Guards: only `envoy.reloadable_features.http1_zero_copy_body_fragments` varies (`off` false, `frag-on` true);
  the two UDP guards are idle on TCP and written explicitly, the same in every `w8-A` arm. Official arms carry no
  runtime layer.
- Runs (chain order a, b, d, c; Williams order; every arm pinned by sha256):
  - `a`: stream origin, shapes `b64k` (64 KiB, 4,000 req/s) and `b1m` (1 MiB, 800 req/s), 8 KiB chunks;
    arms `official-ch8k`, `official-ch8k-A2`, `off-ch8k`, `frag-on-ch8k`, and `off-cl8k`, `frag-on-cl8k` (the same
    bytes in the same writes with a content-length); 6 rounds, seed 811.
  - `b`: nginx sends `ngx-ch64` chunked itself (two 32 KiB chunks), 2,000 req/s; arms `official`,
    `official-A2`, `off`, `frag-on`; 8 rounds, seed 812.
  - `d`: `b1m-h2tls`, the 1 MiB chunked response delivered as HTTP/2 over TLS 1.3 on 16 connections, 400 req/s;
    4 rounds, seed 813.
  - `c`, the rider (official binary only): nginx `l64` (64 KiB, 2,000 req/s) and `l1m` (1 MiB, 800 req/s);
    `cl-ngx`, `cl-ngx-A2` (HTTP/1.1 upstream) and `h2in-ngx` (HTTP/2 cleartext upstream); 6 rounds, seed 814.
  - Half-rate variants (`*-half`, `a-h64`, `a-h1m`, `a-hh`, `c-h*`) were prepared for a load gate failing in a
    smoke; every run ran at its planned rate.
- Rows fixed before any data (applied by `table.py`): metric cycles (user + kernel) of the Envoy process per
  request, user and kernel parts printed beside every row; patch family (Holm over 3) C1 `frag-on-ch8k` vs
  `off-ch8k` on `b1m`, C2 the same on `b64k`, C3 `frag-on` vs `off` on `ngx-ch64`; rider family (Holm over 2) R1,
  R2 `h2in-ngx` vs `cl-ngx` on `l64`, `l1m`; T1 `frag-on` vs `off` on `b1m-h2tls`, pre-registered, no line.
  Kill line: both C1 and C2 saving under 3.0%. Same-build floors 1.0 log points on `b64k`/`b1m`, 1.5 elsewhere;
  a shape that misses its floor decides a row only at three times the observed same-build excursion.
- Effects are simple % (expm1 of the mean per-round log ratio); the quoted interval is the wider of the 95% t
  interval and 1.96*sqrt(SE^2+0.34^2) log points.
- Mechanism legs (not scored): tracepoint counts with writev iovec counts per side (`perf-sys.sh`,
  `mech-inner.sh`, `w1-selftest.sh`) and call-graph legs whose libc copy leaf is the signature of the copy
  (`perf-kcg.sh`, `mech-post.sh`, `fold.py`; `w1_check.py sig`).

## Files

- `make.py` writes `configs/` (runs, smokes, mechanism and tail configs).
- `box-start.sh pre|w1|tail` starts one chain detached: `chain-pre.sh` (every smoke and gate leg, nothing
  scored; `w1_check.py pick` writes each run's variant), `chain-w1.sh` (the scored runs), `chain-tail.sh` (the
  tail add-on). `run-w1.sh smoke|check|queue|mech` is the per-run step.
- `w1_check.py smoke|pick|mech|sig`: the state rules fixed before any leg ran.
- `local_check.py validate|functional`: checks of the configs in Docker off the bench box.
- Tables, from the unpacked archive:
  - `python3 examples/wave8w1/table.py data/waves/chunked-copy/w1/wave8w1` (the rows and lines);
  - `python3 examples/wave8w1/evidence_summary.py data/waves/chunked-copy/w1/wave8w1` (per-arm evidence).

## Results

Killed by the 3% line. C1 (1 MiB): **-1.40% [-2.31, -0.48]**, Measured, 6 rounds; C2 (64 KiB): -0.36%
[-1.65, +0.94], Measured, not a finding; C3 (nginx chunked 64 KiB): -0.02% [-1.26, +1.24], not a finding; T1
(HTTP/2 over TLS downstream): -0.65% [-3.21, +1.97], Not resolved. The copy is gone (the libc leaf drops out of
the profile), but most of its cycles come back as user-space fragment work and as kernel work on more, smaller
writes (writev calls per MiB 10.2 off, 14.0 on). Rider: an HTTP/2 cleartext upstream to nginx costs **+16.55%
[+15.12, +17.99]** on 64 KiB and **+31.99% [+30.70, +33.29]** on 1 MiB against HTTP/1.1, Measured.
