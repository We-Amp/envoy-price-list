# Wave 7, session S5: two empty kernel calls per relayed message

Envoy relays a small TCP message with about five kernel calls, two of which move no data: a read that returns
EAGAIN, and a zero-timeout wait before the send. This session prices those two calls with an experimental
patched binary whose two runtime guards remove them one at a time, on the relay shape of session S1 and on a
4 KB proxied HTTP/1.1 request. The patch is public as an experiment, not a proposal: tag
`relay-syscalls-2026-11/v1` of https://github.com/We-Amp/envoy. Data: the `relay-syscalls` archive of the fourth
wave release (`python3 tools/fetch-wave-data.py relay-syscalls`, see
[`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Box: the bench box of the earlier waves (label `bench-x86_64`): two Xeon E5-2673 v4 (2 x 20 cores, SMT on),
  bare metal, 2.3 GHz fixed, turbo off, default idle states, kernel page-table isolation on. Envoy on CPUs 0-3
  with their SMT siblings idle; client on 20-31,60-71; origin on 32-39,72-79. Loopback, plain TCP, no TLS.
- Binaries (`bins.json`, sha256 enforced): the official `envoy-1.40.2-linux-x86_64` asset (`1d64506e…f03cc`) and
  `relay-sc` (`778ae56e…`), v1.40.2 with the experiment patch. Guards, set in the bootstrap's static runtime
  layer and read when a connection is created: `envoy.reloadable_features.raw_buffer_socket_stop_on_short_read`
  (skip the read that would return EAGAIN) and `envoy.reloadable_features.connection_write_in_current_iteration`
  (write in the same event-loop turn).
- Client: Nighthawk 0.3.0. Origin: `nginx:alpine@sha256:713fc2eb…`.
- Arms, the same six in every scored run: `official` (base), `official-A2` (same-build check), `patched-off`
  (both guards false: the build control), `read-only`, `write-only`, `both-on`.
- Scored runs, each one Williams square (6 arms, 6 rounds), alternated in the chain relay-1, http-1, relay-2,
  http-2: `relay-1`/`relay-2` (S1's `p64`: one proxy as `tcp_proxy`, a 64-byte body from memory in one write,
  8,000 req/s, 512 connections; seeds 751, 753) and `http-1`/`http-2` (shape `s`, 4 KB proxied, 5,200 req/s;
  seeds 752, 754). A shape's two runs are pooled as 12 rounds.
- Mechanism legs (not scored; five arms): tracepoint counts on the Envoy process (`perf-sys.sh`) at the scored
  loads, on the relay shape at 2 to 4 times the rate (`mech-load-p64-*`), and on a multiplexed relay (HTTP/2
  over 16 connections through `tcp_proxy`, 16,000 to 48,000 req/s, `mech-load-h2-*`). `plain-tcp.sh` records
  between runs whether MPTCP or a socket-redirect BPF program was present.
- Rules fixed before any data (in `table.py`): the rows (each guard and both against `patched-off`), the 3%
  line on the relay shape, the build-control rule, the same-build check per shape and the three-times rule;
  `s5_check.py` (state rules on the smokes and the mechanism legs) stops the chain before a scored leg when one
  fails.

## Files

- `make.py` writes `configs/`; `run-s5.sh`, `chain-s5.sh`, `box-start.sh`: the session on the box;
  `local_check.py validate|functional WORKDIR BINDIR`: Docker checks off the box.
- `perf-sys.sh`, `mech-inner.sh`, `plain-tcp.sh`: the mechanism legs and the socket report.
- Tables (from the fetched data):
  - `python3 examples/wave7s5/table.py data/waves/relay-syscalls/wave7s5 --json OUT.json`
  - `python3 examples/wave7s5/evidence_summary.py data/waves/relay-syscalls/wave7s5/relay-1 data/waves/relay-syscalls/wave7s5/relay-2 data/waves/relay-syscalls/wave7s5/http-1 data/waves/relay-syscalls/wave7s5/http-2 --json OUT.json`
  - `python3 examples/wave7s5/mech_table.py data/waves/relay-syscalls/wave7s5/mech --json OUT.json`

## Results

Both calls removed, per relayed 64-byte message: −12.5% [−13.8, −11.1] of CPU cycles inside one patched binary
(simple %, Measured by the three-times rule: the shape's same-build check missed its floor) and −11.0% [−12.3,
−9.7] against the official binary (Exploratory); the read alone −8.0% [−10.1, −6.0] (Measured), the write alone
−2.9% [−5.2, −0.6] (Not resolved). On a 4 KB HTTP/1.1 request: −3.1% [−3.9, −2.3] inside one binary (Measured).
Under a multiplexed relay load the two guards together make 17 to 19% more send calls (Exploratory; CPU not
scored there).
