# Wave 7, session S4b: a profile trained on Envoy's integration tests alone

A follow-up to session S4 ([`examples/wave7s4`](../wave7s4)), registered before it ran: one more PGO + ThinLTO
arm, whose profile comes from the 12 integration tests alone, against the trainer profile and the
integration-plus-benchmark tests profile of S4. Data: the `tests-profile-integration` archive of the fourth wave
release (`python3 tools/fetch-wave-data.py tests-profile-integration`, see
[`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Box: the bench box of the earlier waves (label `bench-x86_64`): two Xeon E5-2673 v4 (2 x 20 cores, SMT on),
  bare metal, 2.3 GHz fixed, turbo off, default idle states. Envoy on CPUs 0-3 with their SMT siblings idle;
  client on 20-31,60-71; origin on 32-39,72-79.
- Binaries (`bins.json`, sha256 enforced): the official `envoy-1.40.2-linux-x86_64` asset (`1d64506e…f03cc`);
  `trainer` (`d1b4f16e…`) and `tests` (`7a47b051…`), the builds of S4; `tests-it`, the same options with a
  profile from the 12 integration tests alone (`000daec4…`). Own builds, not published; sha256 in `bins.json`.
- Client: Nighthawk 0.3.0. Origin: `nginx:alpine@sha256:713fc2eb…`.
- `it-pgo`: S4's rig, shapes, rates, leg length and rounds: shapes `s` (4 KB proxied, 5,200 req/s) and `fh` (109
  headers, direct response, 8,000 req/s), the shape order rotating by round; arms `official` (base),
  `pgolto-trainer`, `pgolto-tests`, `pgolto-tests-it`; 8 rounds (two Williams squares), seed 733. No same-build
  A/A arm of its own (a fifth arm needs ten rounds in Williams order): S4's `s4b-pgo` A/A is the reference, and
  the three arms repeated from S4 are the session-to-session check.
- Rules fixed before the run: the 50% line on the kept share; the check that the repeated arms reproduce S4;
  `s4b_check.py` (state rules on the smoke) and `table.py` apply them. The run happened once.

## Files

- `make.py` writes `configs/` (it reuses S4's `make.py`); `run-s4b.sh`, `chain-s4b.sh`, `box-start.sh`: the
  session on the box.
- Table (from the fetched data; `--s4` takes S4's `s4b-pgo` table for the session-to-session check):
  - `python3 examples/wave7s4/table.py data/waves/tracing-tests-profile/wave7s4/s4b-pgo --json S4B.json`
  - `python3 examples/wave7s4b/table.py data/waves/tests-profile-integration/wave7s4b/it-pgo --s4 S4B.json --json OUT.json`

## Results

The integration-tests-only profile keeps 41.9% (`s`) and 45.1% (`fh`) of the trainer profile's gain, under the
50% line on both shapes (simple %, Measured, without an A/A arm of its own); it reads as the full tests profile,
and the three repeated arms reproduce S4.
