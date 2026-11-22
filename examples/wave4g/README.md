# Wave 4, track G: HTTP/3 against HTTP/2 over TLS

What HTTP/3 (QUIC) costs Envoy v1.40.2 per request against HTTP/2 over TLS 1.3, what the GSO batch writer
saves, and what one new QUIC connection costs with the v1.40.2 session-ticket default and with the ticket
guard on. Config only: the official binary in every arm. Data: the `http3` archive of the second wave
release (`python3 tools/fetch-wave-data.py http3`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Bench box: two-socket Xeon E5-2673 v4 (2 x 20 cores, SMT on), bare metal, 2.3 GHz fixed, turbo off,
  kernel 6.8. Envoy on CPUs 0-3 (4 workers) with their SMT siblings idle; client on 20-31,60-71; origin
  (`nginx:alpine`, pinned digest) on 32-39,72-79.
- Binaries: the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…`) in every arm;
  Nighthawk 0.3.0 (md5 `310df412…`), which speaks HTTP/3 (`--protocol http3`), as the client. `chain-g.sh`
  stops when the client cannot.
- Envoy shape, the same in every arm: the TCP listener on 127.0.0.1:10110 (TLS with an ECDSA P-256
  certificate whose SAN is `bench.local`, HTTP/2 codec) and beside it an HTTP/3 listener on UDP
  127.0.0.1:10110 (the `quic` setting: same routes, router and certificate). Arms differ only in the client
  protocol or one named QUIC setting. Loopback only. Certificates are generated per run directory and are
  not part of the published data.
- Shape `s`: GET, 4 KB proxied, 2,000 req/s (smoke fallback 1,000). HTTP/2 and HTTP/3 keep one connection
  per client worker (16 connections).
- Worker-share gate: QUIC takes no connection balancer, so 16 keep-alive QUIC connections land on the 4
  workers at random. For the keep-alive HTTP/3 arms only, the standard gate (busiest worker at most 1.2x,
  least at least 0.5x of an even share) is replaced by busiest worker at most 0.50 of worker CPU, no floor;
  fixed before the run. The A/A pair is HTTP/3 so that it carries this placement noise. `h2tls` keeps the
  standard gate.
- Warm upstream pool gate: at most 0.001 new origin connections per request in keep-alive arms; 0.005 in the
  reconnect arms (set once, before the `g2s-resume` run, after a smoke whose evidence freeze failed: requests
  held for a new handshake reach the origin together and the pool sometimes grows inside the window).
- Order: Williams squares (8 rounds = two 4-arm squares), paired rounds; effect = mean per-round log ratio
  with the 95% t and the widened 1.96 x sqrt(SE^2 + 0.34^2) half-widths, the wider one quoted. UDP kernel
  counters are recorded per window (a reading, and `UdpInErrors` an evidence item).

## Runs

| Config | Arms | What |
|---|---|---|
| `configs/g1-proto.json` | `h2tls` (base), `h3` (Envoy's default UDP writer: GSO batch writer), `h3-A2`, `h3-nogso` (plain sendmsg writer) | per request, keep-alive |
| `configs/g2-resume.json` | `h3r` (new QUIC connection every 10 requests, client-side limit; v1.40.2 defaults, base), `h3r-A2`, `h3r-tk` (`quic_session_ticket_support` on, one fixed bench ticket key), `h3-ka` (keep-alive reference) | its smoke failed (the client's own per-connection limit hit a pool assertion on HTTP/3): not run |
| `configs/g2s-resume.json` | the same arms, but Envoy closes each HTTP/3 connection after 10 requests (`max_requests_per_connection`, GOAWAY); the client sets no limit | per connection: (`h3r` - `h3-ka`) x 10 |

Each `configs/smoke-*.json` is one round of every arm; `smoke-g2*` add `h3r-nores` (resumption and early
data off), the no-resumption level of the bytes-per-connection reading.

## Files

- `make.py [--rate N]` writes the configs.
- `run-g.sh smoke|queue RUN`, `chain-g.sh` (`G_RUNS`, `G_SMOKE_ONLY=1` for smokes only), `box-start.sh`,
  `idle.sh` (idle by load and CPU busy): the sessions as run.
- `local_check.py`: checks in Docker off the bench box (every bootstrap validates; per arm the protocol
  counters, the GSO writer's byte counter, and in reconnect arms bytes sent per QUIC connection).
  `udp_sniff.py` is its loopback datagram counter (local check only, never on the bench box).
- `table.py RUN_DIR ...`: the rows of a run.

The commands that render every table from the data are in [`docs/wave-studies.md`](../../docs/wave-studies.md).
