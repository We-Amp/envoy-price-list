# Wave 8, session W8-2: the HTTP/3 receive path (stop guard and buffer reuse)

What two changes to Envoy's UDP receive loop save on a 4 KB HTTP/3 request: commit 1 stops reading after a
`recvmmsg` batch that came back short (no extra empty call), commit 2 keeps the receive buffers a batch did not
fill instead of allocating them again. CPU cycles of the Envoy process per request, against the official binary
and against the rebuilt binary with both guards off; plus server-side QUIC retransmission counts in two tail
add-ons. Data: the `http3-receive` archive of the fourth wave release (`python3 tools/fetch-wave-data.py
http3-receive`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)). The archive holds this session's
records (`wave8w2/`, and the first visit's unscored legs in `visit1/`) and the two tail add-ons:
`tail-w8-1/` (run after session W8-1: `examples/wave8w1/chain-tail.sh`, `tail_check.py`) and `tail-w8-3/` (run
after session W8-3: [`examples/wave8tail`](../wave8tail), with row C4, buffer reuse
alone).

## Conditions

- Box: the bench box of the earlier waves (label `bench-x86_64`: two Xeon E5-2673 v4, bare metal, fixed
  2.3 GHz, turbo off, default idle states); Envoy on CPUs 0-3 with their SMT siblings idle, client on
  20-31,60-71, origin on 32-39,72-79, the tracer on 8-19. Wave 4's rig (`examples/wave4g`): TLS listener plus
  HTTP/3 listener on the same port, 16 client connections, nginx origin, 4 KB proxied.
- Binaries (`bins.json`): the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…f03cc`) and
  `w8-A`, an own build of v1.40.2 with the two UDP receive commits and the chunked-body commits of
  `examples/wave8w1`, each behind a runtime guard (sha256 `46c98673…d3971`; an unpatched twin of the same recipe
  is byte-identical to the official binary). The build is not published; commit 2 (buffer reuse) is public on
  the We-Amp/envoy fork, branch `candidates/quic-udp-reuse`. The tail after W8-3 ran `w8-B` (`examples/wave8tail/bins.json`),
  which carries the same two UDP commits unchanged; its other guards are false there. Nighthawk 0.3.0; origin `nginx:alpine` pinned by digest.
- Arms: `h2tls` (official, HTTP/2 over TLS: the anchor), `h3-official`, `h3-official-A2` (the same-build pair),
  `h3-off` (`w8-A`, both UDP guards false: the build control), `h3-stop-on` (commit 1), `h3-both-on` (commits 1
  and 2); `h3-reuse-on` (commit 2 alone) only in the traced smoke here and in the tail's row C4. The chunked guard
  is written explicitly true in every `w8-A` arm; it is idle here (the origin answers with a content-length).
- Scored runs (Williams order, six rounds each): `s-1`, `s-2`, shape `s` (4 KB over HTTP/3, 2,000 req/s, 16
  connections; seeds 821 and 823, pooled as 12 rounds); `shi` (6,000 req/s, seed 822; `shi-half` at 3,008 req/s
  for a failing load gate).
- Rows fixed before any data (applied by `table.py`; Holm over 3): C1 `h3-both-on` vs `h3-off` on `s`; C2
  `h3-stop-on` vs `h3-off` on `s`; C3 `h3-both-on` vs `h3-off` on `s-hi`. Anchor gate: `h3-official` vs `h2tls`
  on `s` inside [+65, +85]%. Worth proposing when C1 saves 3.0% or more; killed under 3.0%; harm stop when C3
  reads +1.0% or more with an interval that excludes 0. Same-build floor 2.0 log points; three-times rule on a
  miss; nothing is re-run. Effects are simple % (expm1 of the mean per-round log ratio); the quoted interval is
  the wider of the 95% t interval and 1.96*sqrt(SE^2+0.34^2) log points.
- Mechanism legs (not scored): tracepoint counts on shape `s` (`perf-sys.sh`, `mech-inner.sh`), the gate on the
  syscall signature of each arm (`w2_check.py mech`), a call-graph profile of three arms (`perf-kcg.sh`,
  `mech-post.sh`, `fold.py`) and `loss-s` with Envoy's QUIC connection statistics on.
- The first visit stopped at its signature gate with nothing scored: the old read loop read 3.4 to 3.5
  `recvmmsg` calls per request, under the gate's 3.6 to 4.4. Before any scored leg the gate was changed to the
  EAGAIN share of all `recvmmsg` calls of the old-path arms (0.40 to 0.55); the patched arms' gate is unchanged.
  The first visit's legs are kept, unscored, in `visit1/`.

## Files

- `make.py` writes `configs/`.
- `box-start.sh` starts `chain-w2.sh` detached (idle and pin checks, the perf selftest, the smokes with their
  state check `w2_check.py smoke`, the signature gate, the scored runs, the profile and the statistics legs);
  `run-w2.sh smoke|check|queue|mech` is the per-run step.
- `local_check.py validate|functional`: checks of the configs in Docker off the bench box.
- Tables, from the unpacked archive:
  - `python3 examples/wave8w2/table.py data/waves/http3-receive/wave8w2` (rows, anchor, same-build check);
  - `python3 examples/wave8w2/mech_table.py data/waves/http3-receive/wave8w2` (syscalls, profile, loss);
  - `python3 examples/wave8w2/evidence_summary.py data/waves/http3-receive/wave8w2/s-1 data/waves/http3-receive/wave8w2/s-2`;
  - the tails: `python3 examples/wave8w1/tail_check.py data/waves/http3-receive/tail-w8-1/wave8w1/tail` and
    `python3 examples/wave8tail/tail_check.py data/waves/http3-receive/tail-w8-3/wave8w3/tail` (C4 is part 2 of the latter).

## Results

- C1, both commits: **-8.04% [-10.24, -5.78]** of CPU cycles per request, Measured, 12 rounds; the same-build
  check passed; anchor HTTP/3 vs HTTP/2 over TLS +74.6%, inside its gate.
- C2, the stop guard alone: at the 3% line; not quoted as a result of its own.
- C3, the loaded shape: No verdict (the run did not start); nothing is said about load.
- Tail add-on after W8-1 (Exploratory, not scored for CPU): server retransmissions per 100,000 packets sent
  0.39 (`h3-official`), 0.59 (`h3-off`), 3.32 (`h3-stop-on`), 3.68 (`h3-both-on`); no drops; the excess comes
  with the stop guard. Tail add-on after W8-3, part 1 (Exploratory): the stop guard's excess falls at the start of
  a connection's run, none inside the measured window; the cause is not measured.
- Row C4 (tail after W8-3), buffer reuse alone (`h3-reuse-on` vs `h3-off` on `s`): **-6.50% [-9.42, -3.48]**,
  Measured, 8 rounds, past the 3% line.
- Outcome: commit 2 (buffer reuse) is proposed alone; commit 1 (the stop guard) is held until its retransmission
  pattern is explained from code.
