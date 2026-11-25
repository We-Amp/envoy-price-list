# Wave 7, session S2: one proxy, bodies and streams

What a chunked upstream body costs against the same bytes with a content-length; what one small streamed
event costs (cycles and syscalls); what a 32 KiB buffer limit costs on 64 KB responses; and how the HTTP/3
premium splits between a 0-byte and a 4 KB response. Config only: the official binary in every arm. Data: the
`bodies-streams` archive of the fourth wave release (`python3 tools/fetch-wave-data.py bodies-streams`, see
[`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Box: the bench box of the earlier waves (label `bench-x86_64`): two Xeon E5-2673 v4 (2 x 20 cores, SMT on),
  bare metal, 2.3 GHz fixed, turbo off, default idle states. Envoy on CPUs 0-3 with their SMT siblings idle;
  client on 20-31,60-71; origin on 32-39,72-79.
- Binary: the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…f03cc`, enforced). Client:
  Nighthawk 0.3.0. Origins: `nginx:alpine@sha256:713fc2eb…`, and the stream origin of
  [`tools/streamorigin`](../../tools/streamorigin) (Go standard library, static, built in a pinned Go image; it
  runs inside the nginx image on the origin CPUs), which sends chunked bodies and SSE-shaped streams.
- `s2a-chunked`: HTTP/1.1 client, the stream origin. Shapes `b64k` (64 KiB, 4,000 req/s) and `b1m` (1 MiB, 800
  req/s). Arms: `cl` (content-length, one origin write; base), `cl-A2`, `ch4k` and `ch8k` (chunked, one 4 KiB /
  8 KiB chunk per write), `cl8k` (content-length in the same 8 KiB writes as `ch8k`: the control for the copy),
  `h2in` (HTTP/2 cleartext upstream). 6 arms x 2 shapes, 6 rounds, seed 711. Every request line has the same
  length. `-h64`, `-h1m`, `-hh`: the same at half rate on one or both shapes, used only when a smoke at the full
  rate fails a load gate or the origin-headroom evidence.
- `s2b-stream`: 200-byte events 1 ms apart; shapes `ev20` (20 events, 2,080 req/s) and `ev200` (200 events, 208
  req/s). Arms: `base`, `base-A2`, `idle-off` (stream, downstream and upstream idle timeouts 0). 6 rounds, seed
  712; `-half` at 960 and 96 req/s. In the recorded session both smokes passed at the full rate
  (`chain-s2.log`: "picked s2a-chunked", "picked s2b-stream"); no half-rate variant ran.
- `s2c-buf`: nginx origin, `l64` (64 KiB, 2,000 req/s): `buf-default` (base), `buf-default-A2`, `buf-32k`
  (`per_connection_buffer_limit_bytes` 32768 on the listener and the cluster). 6 rounds, seed 713.
- `s2d-h3`: TLS listener plus HTTP/3 listener, 16 client connections, nginx origin; shapes `z0` (0 bytes) and `s`
  (4 KB), both 2,000 req/s: `h2tls` (base), `h3`, `h3-A2`. 6 rounds, seed 714.
- Mechanism legs (`mech-*`, one round, not scored): syscall counts and a kernel call-graph profile of the Envoy
  CPUs. `mech_gates.py` applies the readings fixed before the run.
- Rules fixed before the run: A/A per shape, the rate fallbacks (`s2_pick.py`), the rows and lines of
  `table.py`. Three shapes failed their A/A; their rows carry that label.

## Files

- `make.py` writes `configs/`; `run-s2.sh`, `chain-s2.sh`, `box-start.sh`: the session on the box;
  `local_check.py validate|functional WORKDIR`: Docker checks off the box.
- `perf-selftest.sh`, `perf-sys.sh`, `perf-kcg.sh`, `mech-inner.sh`, `mech-post.sh`, `fold.py`: mechanism legs.
- Tables (from the fetched data), for each run `s2a-chunked`, `s2b-stream`, `s2c-buf`, `s2d-h3`:
  - `python3 examples/wave7s2/table.py data/waves/bodies-streams/wave7s2/RUN --json OUT.json`
  - `python3 examples/wave7s2/mech_table.py data/waves/bodies-streams/wave7s2/mech --json MECH.json`
  - `python3 examples/wave7s2/mech_gates.py data/waves/bodies-streams/wave7s2/mech MECH.json --json OUT.json`

## Results

Chunked against the same bytes in the same writes: +5.4% [4.1, 6.6] at 64 KiB and +8.8% [8.0, 9.5] at 1 MiB
(simple %, Measured). A 32 KiB buffer limit on a 64 KB response: +19.0% [17.9, 20.2] (Measured). HTTP/3 per 4 KB
request: +77.6% [73.3, 82.0] (Measured). One streamed event: 74k to 76k cycles, 4.55 syscalls (the streamed
shapes failed their A/A).
