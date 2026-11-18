# Feature rows, session 1 (17 November 2026)

Setting rows measured in one session on 17 November, on the same machine as the earlier sessions (a bare-metal
dual-socket Intel Xeon E5-2673 v4 server at a fixed 2.3 GHz, turbo off; the proxy pinned to four cores of one
socket, load generator and origin on the other socket, all on loopback). See `../../README.md` for the box and
for the edits made for publication.

Harness: the `epl` code at commit `bb8aa81` of this repository (recorded per run as `harness` in
`results.json`). The configs are in `examples/settings-matrix/features/`, written by
`examples/settings-matrix/features.py`; the session was driven by `examples/settings-matrix/run-session-1.sh`.
Method and protocol: [README.md](../../../README.md) and, for the fixed-protocol rules the session followed,
[RELEASE-RECORD.md](../../../RELEASE-RECORD.md).

| Directory | Contents |
|---|---|
| `run-s/` | run S: percpu-on, retry-on and idle-timers-off against the base, plus the session A/A (`base-A2`) |
| `18-access-log/` | access log, text and JSON, against log off |
| `18w-access-log-w16/` | the same with 16 workers |
| `17-tracing/` | tracing |
| `13-ext-authz/` | external authorization |
| `cal-w16-log-off/`, `cal-w16-log-json/` | calibration legs for the 16-worker rates |
| `tables.md` | the session's tables (written by `examples/settings-matrix/features_table.py`) |
| `queue.log` | the run queue, in the order it ran (including the smoke runs, which are not included here) |

Each run directory has `results.json`, `legs.jsonl`, `summary.md`, `experiment.json`, `envoy-bootstrap*.json`,
`status.json`, `log.txt`, `config_dump/`, `stats/`, `perf/` and `origin/` (and `alog/` or `collector/` where
the row uses them). Left out: the raw Nighthawk output of every leg, the proxy and client logs, the socket
listings and the smoke runs.
