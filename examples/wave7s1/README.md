# Wave 7, session S1: a second proxy hop, a TCP relay of small messages, Unix sockets for the hops

What a second proxy in front of the application costs when it relays TCP (`tcp_proxy`) instead of proxying
HTTP, with and without mutual TLS on that hop; what Envoy spends on one small relayed message (syscalls and
cycles, and how many of the calls move no data); and what a Unix domain socket instead of loopback TCP saves on
the hop between two proxies and on the hop to the application. Config only: the official binary in every arm
and on both hops. Data: the `second-hop` archive of the fourth wave release
(`python3 tools/fetch-wave-data.py second-hop`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Box: the bench box of the earlier waves (label `bench-x86_64`): two Xeon E5-2673 v4 (2 x 20 cores, SMT on),
  bare metal, clock fixed at 2.3 GHz, turbo off, default idle states. The proxy under test on CPUs 0-3 with
  their SMT siblings idle; the second hop (pair arms) on 4-7; client on 20-31,60-71; origin on 32-39,72-79.
- Binary: the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…f03cc`, enforced by the
  harness) on both hops. Client: Nighthawk 0.3.0. Origin: `nginx:alpine@sha256:713fc2eb…`; for `s1b-relay` the
  origin answers from memory in one write; for `one-uds` a second nginx server listens on a Unix socket in the
  run directory.
- `s1a-hop`: shape `s` (HTTP/1.1 GET, 4 KB proxied, 5,200 req/s), one upstream pool per downstream connection on
  every HTTP hop; primary metric: the cycles of both hops per request. Arms: `one-ppd` (one proxy), `pair`
  (two HTTP hops; base), `pair-A2` (A/A), `pair-l4` (hop B relays with `tcp_proxy`), `pair-mtls` (ECDSA P-256
  mTLS between the hops), `pair-mtls-l4`, `pair-uds` (the hop between the proxies is a Unix socket), `one-uds`
  (one proxy, the origin hop is a Unix socket). 8 arms, 8 rounds (one Williams square), seed 701. A Unix-socket
  arm that fails its smoke is replaced by a second copy of `one-ppd` (the `s1a-hop-no-*` configs), so the run
  keeps 8 arms.
- `s1b-relay`: one proxy; shapes `p64` (64-byte body) and `p1k` (1,024 bytes), one request = two relayed
  messages, both at 8,000 req/s, responses counted at the origin in every arm. Arms: `tcp` (`tcp_proxy`
  defaults; base), `tcp-A2`, `tcp-noidle` (idle timeout 0 s), `http` (the plain HTTP proxy on the same
  traffic). 4 arms x 2 shapes, 8 rounds, seed 702. `s1b-relay-half` (4,000 req/s) was the fallback for a smoke
  that fails a load gate; the smoke passed and it did not run. No Unix-socket arm was replaced either.
- Mechanism legs (`mech-*`, one round, not scored, never in a price table): syscall counts (`perf-sys.sh`) and a
  system-wide kernel call-graph profile of the proxy's CPUs (`perf-kcg.sh`). The call-graph legs ran in a
  second chain (`chain-s1-kcg.sh`) after the first chain's perf selftest refused them.
- Rules fixed before the run: A/A per shape, the replacement and rate fallbacks (`s1_pick.py`), and the
  rows and lines that `table.py` applies.

## Files

- `make.py` writes `configs/`; `run-s1.sh smoke|check|queue`, `chain-s1.sh`, `chain-s1-kcg.sh`,
  `box-start.sh`: the session on the box; `local_check.py validate|functional WORKDIR`: the configs checked in
  Docker off the box.
- `perf-selftest.sh`, `perf-sys.sh`, `perf-kcg.sh`, `mech-inner.sh`, `mech-post.sh`, `fold.py`: the mechanism
  legs and their reports.
- Tables (from the fetched data):
  - `python3 examples/wave7s1/table.py data/waves/second-hop/wave7s1/s1a-hop --json OUT.json`
  - `python3 examples/wave7s1/table.py data/waves/second-hop/wave7s1/s1b-relay --json OUT.json`
  - `python3 examples/wave7s1/mech_table.py data/waves/second-hop/wave7s1/mech --json OUT.json`

## Results

Second hop as `tcp_proxy`: the pair's CPU per request −32.9% [−33.6, −32.3] (simple %, Measured; −30.8% with
mTLS on that hop). Unix socket instead of loopback TCP: −6.0% [−6.8, −5.2] of the pair's CPU for the hop
between the proxies and −4.5% [−5.7, −3.3] for the hop to the application (Measured). A relayed 64-byte
message: 4.86 syscalls, about 74k cycles (Measured).
