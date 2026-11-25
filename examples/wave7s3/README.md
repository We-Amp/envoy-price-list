# Wave 7, session S3: a typical feature stack, ten inert filters, the idle timers

What a stack of common features costs together against the bare proxy, and whether the published single rows
add up; what leaner settings of the same stack save; what ten HTTP filters that are configured but do nothing
cost, with and without `disabled: true`; and what the idle timers and the route timeout cost. Config only: the
official binary in every arm. Data: the `feature-stack` archive of the fourth wave release
(`python3 tools/fetch-wave-data.py feature-stack`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Box: the bench box of the earlier waves (label `bench-x86_64`): two Xeon E5-2673 v4 (2 x 20 cores, SMT on),
  bare metal, 2.3 GHz fixed, turbo off, default idle states. Envoy on CPUs 0-3 with their SMT siblings idle;
  client on 20-31,60-71; origin on 32-39,72-79.
- Binary: the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…f03cc`, enforced). Client:
  Nighthawk 0.3.0. Origin: `nginx:alpine@sha256:713fc2eb…`. Collector:
  `otel/opentelemetry-collector:0.120.0@sha256:1daa4312…` (the image of the published tracing row).
- `s3a-stack`: shape `sx` = `s` (4 KB proxied, 5,200 req/s) with the `accept-encoding` and `authorization`
  request headers of the published compressor and JWT rows, in every arm. Arms: `bare` (base), `bare-A2`,
  `typical` (JSON file access log, OpenTelemetry tracer at 1%, plain statsd sink over UDP, an idle gzip
  compressor, JWT with its token cache, a local rate limit, a retry policy), `typical-A2`, `typical-nosink`,
  `lean` (`typical` with the text access log and the OpenTelemetry stats sink in place of JSON and statsd).
  The stats flush at Envoy's default 5 s. 6 arms, 6 rounds, Williams order, seed 721. The JWT is a fixture
  signed with a key made for the bench (issuer `epl.example`), the same as in the published JWT row.
- `s3b-chain`: shapes `s` (5,200 req/s) and `fh` (109 headers, direct response, 8,000 req/s). Arms: `f0` (router
  only; base), `f0-A2`, `f10` (the ten inert filters of `epl/envoy_config.py` `INERT_FILTERS` before the router),
  `f10-off` (the same, each `disabled: true`), `idle-off` (stream, downstream and upstream idle timeouts 0 s),
  `timers-off-all` (`idle-off` plus route timeout 0 s). 6 arms x 2 shapes, 6 rounds, seed 722.
- Mechanism legs (`mech-*`, one round, not scored): syscall counts and kernel call-graph profiles.
- Rules fixed before the run: A/A per shape (every A/A passed), the additive band for the stack against the sum
  of the published single rows, the kill lines; `s3_check.py` checks the state the predictions rest on from
  the smokes; `table.py` applies the rest.

## Files

- `make.py` writes `configs/`; `run-s3.sh`, `chain-s3.sh`, `box-start.sh`: the session on the box;
  `local_check.py validate|functional WORKDIR [s3a|s3b]`: Docker checks off the box.
- `perf-selftest.sh`, `perf-sys.sh`, `perf-kcg.sh`, `mech-inner.sh`, `mech-post.sh`, `fold.py`: mechanism legs.
- Tables (from the fetched data), for each run `s3a-stack`, `s3b-chain`:
  - `python3 examples/wave7s3/table.py data/waves/feature-stack/wave7s3/RUN --json OUT.json`
  - `python3 examples/wave7s3/evidence_summary.py data/waves/feature-stack/wave7s3/RUN --json OUT.json`
  - `python3 examples/wave7s3/mech_table.py data/waves/feature-stack/wave7s3/mech --json OUT.json`

## Results

The stack: +22.9% [21.8, 24.1] without a stats sink, +38.2% [36.9, 39.4] with plain statsd (simple %,
Measured), within 3 points of the sum of the single rows. The lean settings: −11.5% [−12.5, −10.6] (Measured).
Ten inert filters: +9.5% [8.5, 10.5] on `s`, +17.0% [15.1, 18.9] on `fh`; with `disabled: true` they read as no
filters (Measured). Idle timers off: −2.8% [−3.6, −2.0] on `s`, −3.5% [−5.2, −1.7] on `fh` (Measured, at the 3%
line).
