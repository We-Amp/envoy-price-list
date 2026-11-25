# Waves 7 and 8 data: what was changed in the raw records before publication

The archives hold the records as the harness and the session chains wrote them, with the changes listed
here. No measured value was changed: every change is inside a text string. The changes were made with
`epl scrub --publish` (`epl/pubscrub.py`) and checked with its `--check` mode, which
`tools/build-wave-data.py` runs again before it writes an archive.

## Left out

- **Binaries**: no Envoy, Nighthawk or stream-origin binary is published. Their sha256 are in the example
  directories' `bins.json` and in the records.
- **Raw perf samples**: none were in the data directories (the mechanism chains folded them on the bench box
  and deleted them there).
- **Eleven packed copies** (`.tgz`) of session directories that are published unpacked.
- **The operator's login transcripts** of each session (46 files: the outputs of the logins that started a chain,
  waited for it and collected its directory). They hold no record the tables read; the box state before and after
  each chain is in the session's `box-state*.txt`.
- **Local check outputs** (17 files): the configs' validation and rehearsal runs on the preparation machine,
  before the session. The checks themselves are the examples' `local_check.py`.
- **The tail add-ons' copies of their sessions' earlier runs.** The two tail chains copied the bench box's whole
  runs directory; `http3-receive/tail-w8-1/` and `tail-w8-3/` keep only the tail part (`tail/`, the tail chain's
  log, output and exit code, `box-state-tail.txt` and the tail's go files). The session's own runs are in
  `chunked-copy` (W8-1); the records of session W8-3 itself are not in this release. In
  `tail-w8-3/wave8w3/queue.log` the lines written before the tail chain started (2026-11-24T22:39:41Z, W8-3's own
  legs) are left out; the lines from then on are as written.

## What was changed

328 of the files of this release differ from the files the runs wrote (the rendered tables below not counted).

- **Home directory prefixes** are written `~` (2485 places in 301 files).
- **The user name** outside a path is written `user` (16 places in 12 files: process lists
  in the box-state files).
- **Local network addresses** are written `<box address>` (the bench box) and `<operator address>` (the machine
  the sessions were started from) (64 places in 38 files: the listener lists of the box-state files and the
  socket lists `ss-*.txt` of mechanism legs, which show the operator's SSH session).
- **The directory listings of the bench box** in the box-state files (`~/epl:`, `runs:`, `bins:`, written before
  and after each chain) keep only what the session needs (`bin`, `bins`, `runs`, `sym` and the session's own
  harness, runs and binaries directories); the other entries, those of other studies on the same box, are
  counted and not named: "(and N entries of other studies, not listed)" (32 lines in 11 files).
- **The copy of the second chain's script** in `second-hop/wave7s1/chain-s1-kcg.sh` carries the published
  wording of its header comment (1 place), as in `examples/wave7s1`.

## Rendered again

- `feature-stack/s3a-table.md`, `feature-stack/s3b-table.md`, `tracing-tests-profile/s4a-table.md` and
  `s4a-table.json` were rendered again with the published `table.py` of `examples/wave7s3` and
  `examples/wave7s4`. Against the tables rendered when the runs were analysed, only labels differ: references to
  an unpublished planning document now read "plan", and the verdict text of a row at a decision line reads "not
  decided by the table" where it named who decides. Every number and verdict is the same.
- Every other table of these archives is as rendered when the runs were analysed; the scripts of the
  repository render each of them again byte for byte (`docs/wave-studies.md`).

## Commit ids

The records read `0.1.0 (uncommitted)` for the harness commit; `docs/wave-data/harness-commit-map.md` names
the commit each session ran.
