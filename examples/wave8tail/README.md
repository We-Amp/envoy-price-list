# Wave 8, the QUIC tail add-on after session W8-3 (W8-2's follow-up)

Two questions left open by session W8-2 (the HTTP/3 receive path, [`examples/wave8w2`](../wave8w2)): where in a run
the stop guard's extra server retransmissions fall, and what the buffer-reuse commit saves on its own. It ran on the
bench box right after session W8-3, in that session's runs directory. Data: `tail-w8-3/` of the `http3-receive`
archive of the fourth wave release (`python3 tools/fetch-wave-data.py http3-receive`, see
[`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Box, shape and rig: W8-2's (the bench box of the earlier waves, label `bench-x86_64`; shape `s`, 4 KB proxied from
  nginx over HTTP/3, 2,000 req/s, 16 client connections, TLS and QUIC listeners on one port).
- Binaries (`bins.json`): the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…f03cc`) and `w8-B`,
  an own build of v1.40.2 (sha256 `14aefebf…d762e`, not published) that carries W8-2's two UDP receive commits
  unchanged, each behind a runtime guard. In every `w8-B` arm the build's other guards are false; the two UDP guards
  are set per arm as W8-2 named its arms (`h3-off` both false, `h3-both-on` both true, `h3-reuse-on` reuse only).
  The buffer-reuse commit is public on the We-Amp/envoy fork, branch `candidates/quic-udp-reuse`.
- Part 1: `tail-p1-r1` .. `r4`, `h3-off` and `h3-both-on`, one leg each, order alternating, 10 s runs, Envoy's QUIC
  statistics visitor with an update period of 0.05 s; retransmitted packets split into before, inside and after the
  measured window from the harness's snapshots.
- Part 2: `tail-c4`, row C4 `h3-reuse-on` vs `h3-off`, with the same-build pair `h3-official-A2` vs `h3-official`;
  4 arms x 8 rounds in Williams order (seed 851). Part 2 started only if it could end inside the chain's cap.
- The rules (the placement rule of part 1; the 3.0% line, the same-build floor and the labels of row C4) are in
  `tail_check.py` and were fixed before the first leg.

## Files

- `make.py` writes `configs/tail-*.json` with `tail_make.py` (byte for byte the configs that ran).
- `box-start.sh` starts `chain-tail.sh` detached (idle check, binary pins, port checks, the parts, then
  `tail_check.py`); `run-tail.sh NAME` runs one config into `$RUNS/tail/NAME`.
- Table, from the unpacked archive:
  `python3 examples/wave8tail/tail_check.py data/waves/http3-receive/tail-w8-3/wave8w3/tail --json OUT.json`.

## Results

- Part 1 (Exploratory): the stop guard's excess retransmissions fall at the start of a run (54 of 54 before the
  window), none inside the measured window; the cause is not measured.
- Row C4, buffer reuse alone: **-6.50% [-9.42, -3.48]** of CPU cycles per request, Measured, 8 rounds, past the 3%
  line; the same-build pair -0.91% [-3.44, +1.68]. Retransmitted packets over the 8 legs: 16 (`h3-reuse-on`)
  against 9 (`h3-off`), a difference this small count cannot resolve.
