# Wave 7, session S4: a deferred tracing span; a profile trained on Envoy's own tests

Two built binaries against the official one. First: what the OpenTelemetry tracer costs at 0% sampling, and
how much of that a patch saves that builds the span only once a request is sampled. Second: how much of the
gain of a PGO + ThinLTO build is kept when its profile comes from Envoy's own tests instead of the measured
traffic. Data: the `tracing-tests-profile` archive of the fourth wave release
(`python3 tools/fetch-wave-data.py tracing-tests-profile`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Box: the bench box of the earlier waves (label `bench-x86_64`): two Xeon E5-2673 v4 (2 x 20 cores, SMT on),
  bare metal, 2.3 GHz fixed, turbo off, default idle states. Envoy on CPUs 0-3 with their SMT siblings idle;
  client on 20-31,60-71; origin on 32-39,72-79. HTTP/1.1 without TLS over loopback, 4 workers.
- Binaries (`bins.json`; every arm pins its sha256 and the harness refuses a binary that differs): the official
  `envoy-1.40.2-linux-x86_64` asset (`1d64506e…f03cc`); `dfs`, v1.40.2 with the deferred-span patch, release
  options (`88a127e8…`), and `dfs-sym`, its link before stripping (evidence legs only); `trainer`, wave 2's PGO +
  ThinLTO build (`d1b4f16e…`); `tests`, the same options with a profile from 12 integration and 10 benchmark
  tests of Envoy's suite (`7a47b051…`). The patched and tests-trained builds are own builds, not published;
  their sha256 are in `bins.json`. The unpatched twin of the `dfs` build is byte-identical to the official
  binary.
- Client: Nighthawk 0.3.0. Origin: `nginx:alpine@sha256:713fc2eb…`. Collector:
  `otel/opentelemetry-collector:0.120.0@sha256:1daa4312…`.
- Shapes `s` (4 KB proxied, 5,200 req/s) and `fh` (109 headers, direct response, 8,000 req/s); the shape order
  rotates by round.
- `s4a-otel`: 8 arms, 8 rounds (one Williams square), seed 731: `notrace` (official, no tracer; base),
  `stock-0`, `stock-0-A2` (official, tracer at 0% random sampling, no sampler extension), `patched-0` (`dfs`, its
  runtime guard on), `patched-0-guard-off` (`dfs`, guard `envoy.reloadable_features.otel_tracer_deferred_span`
  false: the build control), `stock-1`, `patched-1` (1% sampling), `patched-notrace` (`dfs`, no tracer: the
  second build control).
- `s4b-pgo`: `official` (base), `official-A2`, `pgolto-trainer`, `pgolto-tests`; 8 rounds (two Williams
  squares), seed 732.
- Evidence legs (not scored): `ev-span-path` (the unstripped twin at 0%, guard on and off, under a user-space
  profile, `perf-span.sh`) and `ev-export` (official and `dfs` at 100% sampling, 96 req/s; the collector prints
  every span and `span_compare.py` compares them). `s4_evidence.py` checks them before the scored run.
- Rules fixed before the run: A/A per shape (every A/A passed); the +4% line for the tracer's remainder; the
  50% line and the 40-60% window for the kept share of the tests profile; `s4_check.py` (state rules on the
  smokes) and `table.py` apply them.

## Files

- `make.py` writes `configs/`; `run-s4.sh`, `chain-s4.sh`, `box-start.sh`: the session on the box;
  `local_check.py validate|functional WORKDIR BINDIR [s4a|s4b|span|export]`: Docker checks off the box.
- `perf-span.sh`, `span-inner.sh`, `span-post.sh`, `span_compare.py`, `s4_evidence.py`: the evidence legs.
- Tables (from the fetched data), for each run `s4a-otel`, `s4b-pgo`:
  - `python3 examples/wave7s4/table.py data/waves/tracing-tests-profile/wave7s4/RUN --json OUT.json`
  - `python3 examples/wave7s4/evidence_summary.py data/waves/tracing-tests-profile/wave7s4/RUN --json OUT.json`
  - `python3 examples/wave7s4/extra.py data/waves/tracing-tests-profile/wave7s4/s4a-otel` (supplementary
    readings, written after the run)

## Results

The deferred span at 0% sampling: −2.88% [−3.70, −2.06] on `s` against the stock tracer, about 45% of the
tracer's cost; the remainder +3.62% [+2.36, +4.90] (simple %, Measured; which side of +4% it lies on is Not
resolved); both build controls read as the official binary. The tests-trained profile: −17.26% [−17.96, −16.56]
(`s`) and −15.65% [−16.89, −14.39] (`fh`) against the official binary, a kept share of 44.0% and 45.4% of the
trainer profile's gain, under the 50% line (Measured).
