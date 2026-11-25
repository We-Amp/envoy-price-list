# Waves 7 and 8 data: the raw records

The raw records of waves 7 and 8 of the Envoy price list, one archive per study, assets of the release of
tag `waves-2026-11d` of https://github.com/We-Amp/envoy-price-list. `python3 tools/fetch-wave-data.py
--tag waves-2026-11d` in that repository downloads them, checks each archive and every file against the
manifest in git, and unpacks them into `data/waves/<study>/`. This file and `WHAT-WAS-CHANGED.md` are in
each study's directory of this release (the first release's files of the same names are at the top of
`data/waves/`).

Run directories have the layout of the first wave release (`docs/wave-data/README.md`). The conditions of
each study are in its example directory; the commands that render every table are in
`docs/wave-studies.md`. Every study ran on the bench box of the earlier waves (`bench-x86_64`: two-socket
Xeon E5-2673 v4), one detached chain per session.

| Archive (`waves-2026-11d-data-<study>.tar.gz`) | Wave | Configs | Contents |
|---|---|---|---|
| `second-hop` | 7 | `examples/wave7s1` | `wave7s1/s1a-hop` (a second Envoy hop: HTTP, a TCP relay, Unix sockets between the hops and to the origin, mTLS on the hop) and `wave7s1/s1b-relay` (one Envoy as a TCP relay, small messages), their smokes and frozen evidence, `mech/` (non-scored syscall and kernel call-graph legs); tables `s1a-table`, `s1b-table`, `mech-table` (`.md`, `.json`) |
| `bodies-streams` | 7 | `examples/wave7s2` | `wave7s2/s2a-chunked` (chunked against fixed-length bodies from the stream origin), `s2b-stream` (streamed events), `s2c-buf` (a 32 KiB buffer limit), `s2d-h3` (HTTP/3 at 0 B and 4 KB), smokes, `mech/`; tables `s2a`..`s2d-table`, `mech-table`, `mech-gates` |
| `feature-stack` | 7 | `examples/wave7s3` | `wave7s3/s3a-stack` (a stack of seven common features against the lean config, with and without a statsd sink) and `s3b-chain` (ten inert filters, `disabled: true`, the idle timers), smokes, `mech/`; tables `s3a-table`, `s3b-table`, `s3a-evidence`, `s3b-evidence`, `mech-table` |
| `tracing-tests-profile` | 7 | `examples/wave7s4` | `wave7s4/s4a-otel` (OpenTelemetry tracing at 0% sampling: the deferred-span build against the official binary) and `s4b-pgo` (PGO + ThinLTO trained on Envoy's own tests against the trainer profile), smokes, `mech/` (the span-path evidence legs), `evidence-otel.*`; tables `s4a-table`, `s4b-table`, `s4a-evidence`, `s4b-evidence`, `s4a-extra.md` |
| `tests-profile-integration` | 7 | `examples/wave7s4b` | `wave7s4b/it-pgo` (the profile from the integration tests alone) and its smoke; tables `it-pgo-table`, `it-pgo-evidence`, `smoke-check.txt` |
| `relay-syscalls` | 7 | `examples/wave7s5` | `wave7s5/relay-1`, `relay-2` (a TCP relay of 64-byte messages: the experiment build's two guards, official), `http-1`, `http-2` (the same arms on 4 KB HTTP), smokes, `mech/` (syscall counts, loaded send counts); tables `s5-table`, `s5-mech`, `s5-evidence`, `mech-check.txt`, `smoke-check.txt` |
| `chunked-copy` | 8 | `examples/wave8w1` | `pre/wave8w1` (smokes, the copy signature legs), `w1/wave8w1/a`..`d` (the chunked-fragment build's guard off and on, 1 MiB and 64 KiB, nginx sending chunked), `mech/`; tables `w1-table`, `w1-evidence`, `pre-check.txt`, `pre-profile.txt`, `mech-check.txt` |
| `http3-receive` | 8 | `examples/wave8w2`, `examples/wave8w1`, `examples/wave8tail` | `wave8w2/s-1`, `s-2` (the HTTP/3 receive path: stop guard, buffer reuse, both, official), smokes, `mech/`; `visit1/` (the first visit, stopped at its signature gate, nothing scored); `tail-w8-1/` and `tail-w8-3/` (the two tail add-ons: server-side QUIC retransmission counts, and in `tail-w8-3/wave8w3/tail/tail-c4` the buffer-reuse commit alone); tables `w2-table`, `w2-mech`, `w2-evidence`, `tail-w8-1/tail-table`, `tail-w8-3/tail-table` |

The two tail add-ons ran at the end of the W8-1 and W8-3 sessions; their chains copied the session's whole runs
directory, so only the tail part is in `http3-receive` (W8-1's own runs are in `chunked-copy`; the records of
session W8-3 itself, the relay write candidate, are not in this release).

## Binaries

The official Envoy v1.40.2 release asset (x86-64 sha256 `1d64506e…f03cc`) and own builds of tag v1.40.2 with
experiment patches. No binary is in these archives; their sha256 are in the example directories' `bins.json`
and in the records. Patch sources that are published: the relay syscall experiment is tag
`relay-syscalls-2026-11/v1` of https://github.com/We-Amp/envoy; the QUIC receive-buffer reuse commit is branch
`candidates/quic-udp-reuse` of the same repository. The other builds' sources are not published.

`metadata.harness` in each run's `results.json` reads `0.1.0 (uncommitted)`: the bench box got the harness as an
archive without a commit file. `docs/wave-data/harness-commit-map.md` names the commit each session ran and where
that code is in the published history.
