# Wave studies: measured harness commits and where their code is

`metadata.harness` in each run's `results.json` (and the same string in `summary.md`) names the harness
commit the run used, as `0.1.0 <id>`, with `(archive)` when the bench box got the harness as a
`git archive` with a commit file, or `(uncommitted)` when the archive had none. Those commits were made
on working branches, one per study, that are not published. Their code is in the published history in
the commits below: the harness features of all three waves in one commit, and each study's configs and
scripts in its own.

| Measured id (as recorded) | Runs | Published harness | Published configs and scripts |
|---|---|---|---|
| `3ee6aa4e61fe` | `statsd-batching/wave1-b/*` | `d49ca12` | `2f4175f` (`examples/wave1-b`) |
| `274ddc23ce61` | `statsd-batching/v2-confirm/wave1-b-v2c/*` | `d49ca12` | `2f4175f` |
| `5d10ad3fd39d` (recorded with the branch name) | `ext-proc-xds/*` | `d49ca12` | `b80784b` (`examples/wave1c`); `table.py` as of the tables' rendering, which only changed the tables after the run |
| `0764feb` | `topdown/td`, `topdown/lbr` | a commit of the stats study, published as `b9b1c9e` (see `docs/stats-data/harness-commit-map.md`) | `170e84e` (`examples/topdown`) |
| uncommitted: an archive of `bca1e00dbfc7` | `code-layout/prof/*`, `code-layout/prof2/*` | `d49ca12` | `7b4c989` (`examples/wave2`) |
| uncommitted: an archive of `b4999a6c6382` | `code-layout/ab/*` | `d49ca12` | `7b4c989` |
| `e0c23f553f01` | `code-layout/w2b/*` | `d49ca12` | `7b4c989` |
| `6e93287d8ee5` | `connection-churn/e-plain`, `e-tls` and their smokes | `d49ca12` | `f5c6951` (`examples/wave3e`) |
| `4fd13429a7ab` | `connection-churn/e2/*` | `d49ca12` | `f5c6951` |
| `168d2571c5a0` | `connection-churn/e2b/*` | `d49ca12` | `f5c6951` |
| `fd709bd89d5f` | `upstream-protocols/run1/*` | `d49ca12` | `4c89497` (`examples/wave3f`) |
| `ab9f7b141899` | `upstream-protocols/run2-f2/*` | `d49ca12` | `4c89497` |
| `772807bfa1f5` | `http3/wave4g/*` | `d49ca12` + `e88e2bc` | `8a4fa01` (`examples/wave4g`) |
| `3dcbe9602e1d` | `http3/wave4g-s/*`, `http3/wave4g-s2/*` | `d49ca12` + `e88e2bc` | `8a4fa01` |
| `577f19528e39` | `http3/wave4g-s3/*` | `d49ca12` + `e88e2bc` | `8a4fa01` |
| `0bac1592ad9a` | `mitigations/*` | `d49ca12` + `e88e2bc` + `d9940fc` | `984912a` (`examples/wave5h`) |
| `e38cd3cb21f6` | `mitigations-cloud/A`, `B`, `C` | `d49ca12` + `e88e2bc` + `d9940fc` | `e3de128` (`examples/wave6k`) |
| `91d3fbad2097` | `mitigations-cloud/D` | `d49ca12` + `e88e2bc` + `d9940fc` | `e3de128` |
| `a5f1b348607a` | `arm-vm-layout/epl/runs/wave5i-prof/fp-w5i` | `d49ca12` + `e88e2bc` + `d9940fc` | `4cef65e` (`examples/wave5i`) |
| `773e4a0363f2`, `5814d60a7dc5` | `arm-vm-layout/epl/runs/wave5i/smoke/smoke-w5i.<time>` (the two smokes replaced by a later one) | `d49ca12` + `e88e2bc` + `d9940fc` | `4cef65e` |
| `33b56817cdae` | `arm-vm-layout/epl/runs/wave5i/w5i` and its smoke | `d49ca12` + `e88e2bc` + `d9940fc` | `4cef65e` |
| `145e52d51d5c` | `arm-metal-layout/epl/runs/wave6j/*` | `d49ca12` + `e88e2bc` + `d9940fc` | `1fb9a4f` (`examples/wave6j`) |
| uncommitted: an archive of `5e2cee4ed28c` | `second-hop/wave7s1/*` except the second chain | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `875ae4f` (`examples/wave7s1`) |
| uncommitted: an archive of `a3435a1dfd3d` | `second-hop/wave7s1/mech/*-kcg-*` (the second chain, `chain-s1-kcg.*`) | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `875ae4f` |
| uncommitted: an archive of `f4664f4154c4` | `bodies-streams/*` | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `91accca` (`examples/wave7s2`) |
| uncommitted: an archive of `109dee8db917` | `feature-stack/*` | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `3d57495` (`examples/wave7s3`) |
| uncommitted: an archive of `81231c798815` | `tracing-tests-profile/*` | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `97f391e` (`examples/wave7s4`) |
| uncommitted: an archive of `7b0fe311dc0e` | `tests-profile-integration/*` | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `03e777b` (`examples/wave7s4b`) |
| uncommitted: an archive of `98046815d123` | `relay-syscalls/*` | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `1a20982` (`examples/wave7s5`) |
| uncommitted: an archive of `6306f37c0bbb` | `chunked-copy/*`, `http3-receive/tail-w8-1/*` | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `cdb8de9` (`examples/wave8w1`) |
| uncommitted: an archive of `f2e86dbd29aa` | `http3-receive/visit1/*` (stopped at its signature gate, nothing scored) | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `0d842b4` (`examples/wave8w2`) |
| uncommitted: an archive of `05b229aacf8b` | `http3-receive/wave8w2/*` | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `0d842b4` |
| uncommitted: an archive of `26dca714a6ab` | `http3-receive/tail-w8-3/*` | `d49ca12` + `e88e2bc` + `d9940fc` + `5150d55` | `6ffde87` (`examples/wave8tail`) |

The build scripts of the code-layout arms are `1c66f7c` (`tools/code-layout`); the release-asset tools
and this documentation `85dd1d0` and later.

## What differs between a measured commit and the published code

- **Waves 7 and 8.** One working branch for both waves, on top of the combined harness of waves 5 and 6; the
  bench box got each session's harness as a `git archive` without a commit file, so the records read
  `0.1.0 (uncommitted)` and the measured commit is the one named above. The published history takes the
  harness changes in one commit (`5150d55`: tcp_proxy listeners, Unix-socket hops, the stream origin, inert
  filters, route timeouts, ALPN, the QUIC statistics visitor, the runtime read-back) and each session's
  examples in its own. The tail add-on that ran after session W8-3 is published on its own, as
  `examples/wave8tail` (its scripts were in the session's example directory; the configs are byte for byte the
  ones that ran); session W8-3 itself and the gate visit before it are not in this release. In the examples,
  references to unpublished planning and review documents, and to who decided a rule, were replaced by what
  they stand for ("plan", "fixed before the run", "not decided by the table"), in the session commits and in
  `d775885` (comments and docstrings of `examples/wave7s1`, `wave7s2`, `wave8w1` and `wave8tail`); the configs are
  byte for byte the ones that ran (`make.py` regenerates them). Their data is the
  assets of the fourth release, `waves-2026-11d` (`874739f`).

- **Waves 5 and 6.** Their working branches followed each other (wave 5 H, then the arm64 branches I and J
  on top of it; K on top of H); the published history takes their harness changes in one commit
  (`d9940fc`: per-task speculation control, boot-state records, the dry run's steal time). In the examples,
  references to unpublished planning documents and one internal item number in the mitigation tables'
  verdict line were replaced by what they stand for, and the cloud kernel's flavour suffix in the K box
  description reads `cloud`. Their data is the assets of the third release, `waves-2026-11c` (`f1e8b5f`).

- **Wave 4 (HTTP/3).** Its working branch joined the connection-churn harness into the upstream-protocols
  harness on its own; the published history carries only what that branch added on top (`e88e2bc`: the
  HTTP/3 listener, `{cert_dir}` in client arguments, the UDP kernel counters), joined with the published
  harness at the same client-argument code as above. The examples' wording changed as for the other
  studies (who decided a short run, references to unpublished documents). Its data is the asset of the
  second release, `waves-2026-11b` (`f49effc`).

- **Code of the other studies.** Each measured commit has the harness features of its own study and of
  the studies before it on its branch; the published harness has all of them. A feature is used only
  when a config sets it, so a published config runs the code paths its measured commit ran.
- **Two places where two studies touched the same code**, joined in the published harness: the
  listener's TLS settings take the key-exchange groups (connection churn) and the client-certificate
  settings (mTLS) together; the client arguments take the arm-level settings (connection churn) and the
  request body from a file (gRPC) together. xDS arms now refuse `upstream_tls` and an `origin_server` other than
  the plain one, which no xDS run used.
- **One fix, after the first `upstream-protocols` session**: `ab9f7b1` removed a local import in
  `Origin.start` that made the gRPC shape's start fail; the published harness has the fix. The runs of
  `run1` did not reach that line (their gRPC smoke is the one that stopped on it).
- **Wording only**, in comments, docstrings and fixed strings: references to planning and review
  documents that are not published, and to who decided a short run, were replaced by what they decided
  ("short run: 6 fixed rounds (large effects: stop when the answer is clear)", "fixed before the run");
  the `short_run_note` of the `ext-proc-xds` and `upstream-protocols` configs changed with them (see
  `WHAT-WAS-CHANGED.md`). The default `perf` of `examples/wave2/perf-lbr.sh` is `perf` on the path
  instead of a kernel-specific path.
- **The analysis scripts** of the top-down and code-layout studies print other labels for their
  decision rows; the numbers are the same (`WHAT-WAS-CHANGED.md`, "Rendered again").
- **Tests**: one source check of `tests/test_latency.py` reads the datagram-class flag of the statsd
  runs as well.
