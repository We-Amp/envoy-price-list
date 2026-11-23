# Wave 1, track B: statsd datagram batching and the header-validation ceiling

Two own builds of Envoy v1.40.2 against a control built the same way, plus a confirmation run of a
second version of the statsd change. Data: the `statsd-batching` archive of the wave studies
(`python3 tools/fetch-wave-data.py statsd-batching`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Bench box (`bench-x86_64/box.json`): two-socket Xeon E5-2673 v4 (2 x 20 cores, SMT on), bare metal,
  2.3 GHz fixed, turbo off, default idle states. Envoy on CPUs 0-3 (4 workers) with their SMT siblings
  idle; client (Nighthawk) on 20-31,60-71; origin (`nginx:alpine`, pinned digest, in Docker) on
  32-39,72-79.
- Binaries (`bins.json`, each pinned by sha256 and checked by the harness before the first leg of every
  run): own builds of tag v1.40.2 with the release options (`-c opt --stripopt=--strip-all
  --linkopt=-Wl,--compress-debug-sections=zlib`, `//source/exe:envoy-static.stripped`):
  - `control`: v1.40.2 as tagged; byte-identical to the official release asset (sha256 `1d64506e…`);
  - `p1`: the statsd sink sends the histogram samples of one event-loop turn as one datagram per
    thread, over a connected UDP socket;
  - `p2`: request-header re-validation on the upstream encode path switched off (a ceiling for what
    that check costs, measurement only);
  - `v2`: the statsd change as an opt-in setting (`max_bytes_per_datagram` on the plain statsd sink).
  The source of `v2` is public: tag `statsd-batch-2026-11/v2` of https://github.com/We-Amp/envoy (branch
  `statsd-batch/v2`, commits `77fdeb8484` and `ee71e0583f`). The source of the `p1` build (`7979fa6063`,
  superseded by `v2`) is public too: tag `statsd-batch-2026-11/v1` (branch `candidates/statsd-batch-v1`) of
  the same repository. The source of the `p2` header-validation ceiling (`af3172d385`, measurement only, its
  result dropped) is not published; the records name its commit id and the configs pin its sha256.
- Shapes, from the stats study ([`examples/stats-flush`](../stats-flush)):
  - `sw`: 1,000 primed clusters (about 118k stats), 4 KB proxied at 5,200 req/s, default 5 s flush
    interval, plain statsd sink to the harness's discard sink (which counts datagrams by kind);
  - `/fl`: 57 request and 52 response headers added by the route on a proxied route, no stats sink.
- Method: paired rounds; arms in Latin squares (an A/A copy of the base arm in every run); the effect is
  the mean per-round log ratio, shown as %, with the 95% t interval and the widened interval
  1.96 x sqrt(SE^2 + 0.34^2). `net.core.rmem_max` is raised for the statsd runs and restored on exit
  (`../stats-flush/sysctl-guard.sh`).

## Runs

| Config | Arms | Rounds |
|---|---|---|
| `b-statsd.json` | `ctl-statsd` (base), `p1-statsd`, `ctl-statsd-A2` | 6 |
| `b-statsd-nosink.json` | the same plus `ctl-nosink` (the sink's price on our own build) | 8 |
| `b-fl.json` | `ctl` (base), `p2`, `ctl-A2`, on `/fl` | 6 |
| `v2c.json` | `ctl-statsd` (base), `v2-statsd-512` (`max_bytes_per_datagram` 512), `ctl-statsd-A2`, `ctl-nosink`; shape `sw` | 8 |

Each `smoke-*.json` is one round of its run; the run is checked against the evidence frozen from its
smoke.

## Files

- `make.py` writes the configs from the stats-flush base and `bins.json` (`python3 examples/wave1-b/make.py`).
- `run-b.sh smoke|check|queue`: the smokes, the evidence freeze and check, the queue of runs.
- `chain-b.sh`, `chain-v2c.sh`: the two sessions as one detached chain each (idle check, sha256 of the
  binaries, smokes, runs; exit code in `$RUNS/chain*.rc`).
- `analysis/analyse.py RUN_DIR ...`: per arm the cycles per request (total, workers, the rest),
  datagrams per request, drop share; paired comparisons against the base (and against `ctl-nosink`
  when present). `B_TABLES_JSON=FILE` also writes the numbers as JSON.
- `analysis/classes.py RUN_DIR`: datagrams per request by kind (sample datagrams against flush
  datagrams) from the discard sink's counts, over whole legs.

The commands that render every table from the data are in [`docs/wave-studies.md`](../../docs/wave-studies.md).
