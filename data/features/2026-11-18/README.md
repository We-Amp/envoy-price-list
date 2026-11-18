# Feature rows, session 2 (18 November 2026)

Compression, Lua and Wasm filters and the load-curve rows, measured in one session on 18 November, on the same
machine as the earlier sessions (a bare-metal dual-socket Intel Xeon E5-2673 v4 server at a fixed 2.3 GHz, turbo
off; the proxy pinned to four cores of one socket, load generator and origin on the other socket, all on
loopback). See `../../README.md` for the box and for the edits made for publication.

Harness: the `epl` code at commit `4fc7986` of this repository (recorded per run as `harness` in
`results.json`). The configs are in `examples/settings-matrix/features2/`, written by
`examples/settings-matrix/features2.py`; the session was driven by `examples/settings-matrix/run-session-2.sh`.
Method and protocol: [README.md](../../../README.md) and, for the fixed-protocol rules the session followed,
[RELEASE-RECORD.md](../../../RELEASE-RECORD.md).

| Directory | Contents |
|---|---|
| `aa-2/` | the session A/A |
| `run-f/` | run F: Lua and Wasm filters, five arms |
| `14-compression/` | gzip, brotli and zstd against compression off, on the 4 KB and 16 KB JSON shapes |
| `14b/` | the follow-up compression rows |
| `lc-j16/`, `lc-sfh/` | load-curve runs |
| `jit-check/` | the JIT warm-up check |
| `probe/` | one request per arm and shape through a throw-away Envoy (response headers checked) |
| `cal-j16-*/`, `cal2.log`, `rates.json` | calibration legs and the rates they set |
| `frozen/` | each run's evidence spec, frozen from its smoke runs |
| `tables.md` | the session's tables (written by `examples/settings-matrix/features_table2.py`) |
| `queue.log`, `jit-check.rc` | the run queue and the JIT check exit code |

Each run directory has `results.json`, `legs.jsonl`, `summary.md`, `experiment.json`, `envoy-bootstrap*.json`,
`status.json`, `log.txt`, `config_dump/`, `stats/`, `perf/` and `origin/`. Left out: the raw Nighthawk output of
every leg, the proxy and client logs, the socket listings and the smoke runs.
