# envoy-price-list

A small A/B harness that runs beside [Nighthawk](https://github.com/envoyproxy/nighthawk) and measures what an
Envoy binary, setting or release costs in CPU per request, measured the same way every time.

It is not a fork of Nighthawk. Nighthawk generates the load; this tool decides the order of the runs, pins the
processes, counts CPU on the Envoy side, throws out runs that were not clean, and does the paired statistics.

Python 3.8+, standard library only. Linux on the bench box (it reads `/proc`, uses `taskset` and `perf`).

## Requirements

Offline (`selftest`, `plan`, `render`, `run --dry-run`): Python 3.8 or later on any OS. Nothing to install.

On the bench box, in addition:

- Linux with `/proc/schedstat` (format version 15 to 17) and the cpufreq and cpuidle sysfs files readable;
- `perf` able to count hardware events on the Envoy process, kernel cycles included (`cycles:k`): check
  `kernel.perf_event_paranoid` (1 or lower) or give the user `CAP_PERFMON`. The path is in `measure.perf`;
- `taskset`, `pgrep` and `ss` (util-linux, procps, iproute2);
- Docker, for the origin (an nginx container the harness starts and stops) and, for the tracing rows, the
  null OpenTelemetry collector; or `origin.mode: external` with your own origin;
- `openssl`, for the TLS rows (self-signed test certificates are made in the run directory);
- the Envoy binaries to compare, and a Nighthawk `nighthawk_client` build. The examples expect the
  Envoy release binaries at `~/epl/bin/envoy-<version>` (from the Envoy GitHub releases; the sha256 of each
  download is in the config and enforced) and Nighthawk at the path in `client.binary`;
  the published runs used a `nighthawk_client` built from We-Amp's public Nighthawk fork (commit
  `5fc3897`), with only client options that upstream Nighthawk also has;
- enough CPUs for disjoint Envoy, client and origin sets. The example configs are written for a
  2 x 20-core machine with SMT (CPUs n and n+40 are siblings); change `cpus` for yours, then `calibrate` to
  pick rates for your machine.

`remote` needs `ssh` and `tar` on both ends.

## The method in one screen

- **Arms and rounds.** Two or more arms (binaries, or the same binary with different arguments) are measured in
  rounds; one round runs every arm once per shape. Rounds come in pairs that run the arms forward and reversed,
  so position effects cancel: `abba` for two arms, `rotate` for three or more (round pair p starts at arm
  p mod k, so over 2k rounds every arm sits in every position equally often). A seeded coin decides which half
  of each pair runs first. Cycles on this class of machine drift with run position, so a fixed order would bias
  the result.
- **Adaptive length.** At least 12 rounds, then blocks of 6, until the 95% interval of every primary comparison
  is at most a target half-width (3% by default), capped at 36. The run stops on interval width, never on a
  p-value, so stopping does not bias the estimate. Round counts are always even and a multiple of the order's
  balance period.
- **Every leg gets a validity verdict.** A leg (one arm, one shape, one round) is invalid, and contributes no
  number, if any of these hold:
  - the achieved rate at Envoy misses the target by more than 1%;
  - the client shows overflow or pool-exhausted counters, or more requests waited in the client queue than
    there are client workers (each worker queues one request while its connections come up; more means the
    queue absorbed a burst);
  - the busiest client thread has less headroom than the configured minimum (default 25%);
  - the port preflight fails (listener and admin ports must be free before start, the origin must accept
    connections; checked with a Python socket connect);
  - the box was not idle before the leg (1-minute load, CPU busy share from `/proc/stat`, every SUT CPU and its
    SMT sibling under 5% busy, and `pgrep -f` for stray proxies or load generators);
  - during the perf window, tasks other than Envoy ran for more than 0.05 CPU on the SUT CPUs, or anything ran
    on the SUT CPUs' SMT siblings outside the SUT set (scheduler run time from `/proc/schedstat`; the
    tick-sampled `/proc/stat` is biased when a worker wakes once per request). The probe fails closed: an
    unreadable file, a format version other than 15 to 17, or a value under −0.01 CPU (run time cannot be
    negative beyond snapshot skew of about 1e-4 CPU) makes the leg invalid. Where the kernel accounts
    interrupt time, per-CPU run time includes interrupts that hit while a task runs and per-task run time does
    not; that error reads high, so it can only invalidate legs, not pass them;
  - any non-2xx response, at the client or at Envoy;
  - the busiest Envoy worker did more than 1.2 times its even share of worker CPU, or the least busy one less
    than half of it (the worker count comes from the config, and a configured worker without a `wrk:` thread
    counts as idle; no `wrk:` thread at all makes the leg invalid);
  - perf counters missing or multiplexed, Envoy not on its configured CPUs, Envoy exiting non-zero, or any
    error.
  - the idle-state configuration of the SUT CPUs or their SMT siblings (cpuidle driver, governor, every
    state's `disable` flag) differs from the one recorded at the start of the run.
  An invalid leg re-runs its whole round for that shape (every arm, in the round's own order) at the end of the
  block, so the order stays balanced. Six invalid legs in a row abort the run; partial results are still written.
- **SUT-side counters.** `perf stat -e instructions:u,cycles:u,cycles:k,instructions:k,task-clock,
  context-switches,cpu-migrations -p <envoy pid>` for a steady window inside the client run, divided by the
  2xx responses Envoy's admin stats counted over the same window. Per Envoy thread CPU, the SUT CPUs' busy
  time and per-connection use (`ss`) are recorded with every leg.
- **Statistics.** Per shape, for each comparison (every arm against the base arm, or all pairs): the mean of
  the per-round log ratios arm / reference with a two-sided 95% t interval is the headline. One metric per row
  is primary (total cycles by default) and Holm's adjustment runs across the primary rows; every other metric
  is exploratory and reported as an interval only. Pairs won, the exact sign test and the exact Wilcoxon
  signed-rank test are kept as support. A comparison with fewer than 6 valid pairs is reported as
  insufficient. Given an A/A run (`floor_from`, or `report --floor`), its interval half-width is printed next to
  every row.
- **Instructions or cycles.** Instructions per request are tight (A/A spread 0.1 to 0.3%) and are the right
  first look when one setting changes on one build. Across differently built binaries (releases) they are not
  a cost: fewer instructions can cost the same cycles. Release rows use total cycles.
- **Kernel cycles are loopback cycles.** On loopback the receive path of a packet runs in the sender's
  context, so Envoy's `cycles:k` contains part of the client's and origin's receive work and misses part of its
  own. Kernel and total cycles compare arms; they are not what a deployment behind a network card pays.
- **Pinning.** Envoy, client and origin run on disjoint CPU sets from the config; overlapping sets are rejected.
  The harness verifies `Cpus_allowed_list` of the running processes and pins itself (and perf) to the CPUs no
  set uses.
- **Binary proof.** md5 and sha256 of every Envoy binary are recorded at the start and checked again at the end;
  an expected md5 or source sha256 in the config is enforced. `envoy --mode validate` runs on the generated
  bootstrap with every arm before the first leg.
- **Own processes only.** The harness signals only processes it started (it keeps the `Popen` handles) and stops
  only the origin container whose ID `docker run` returned to it. It never uses `pkill` or `killall`; `status`
  reads `/proc/<pid>/cmdline` and signals nothing.
- **Client idle strategy `poll`.** With `sleep`, Nighthawk's sequencer oversleeps and releases bursts that
  exhaust the connection pool (overflow counters on an almost idle proxy); with the default `spin`, every client
  thread is 100% busy and headroom cannot be measured. `poll` gives zero overflow and a measurable headroom.
- **LRU connection reuse.** Nighthawk's default (`mru`) keeps reusing the most recently used connection, so only
  some of the prefetched connections carry traffic, and `exact_balance` (which evens out connection counts, not
  busy connections) then leaves 2, 3 or 4 Envoy workers busy, differently on every leg. Fewer, busier workers batch
  more and cost fewer cycles per request, so that alone moved total cycles by 8 to 10% between legs of the same
  binary. The examples pass `--experimental-h1-connection-reuse-strategy lru`, which spreads the traffic over every
  connection and every worker, and a leg whose busiest worker does more than 1.2 times its even share, or whose
  least busy worker does less than half of it, is invalid (under LRU the busiest share stayed under 1.04 times).
- **Client queue at start-up.** With Nighthawk's default of no client-side queue, requests issued while the
  prefetched connections are still being set up overflow on every client worker at once (more connections make
  it worse). The examples set `--max-pending-requests 1000`: those requests wait instead of dropping, and the
  pending-total gate shows that nothing else ever waited.
- **Every wait is bounded.** Client runs, perf, readiness and idle waits all have timeouts, and progress goes to
  `status.json` and `log.txt` after every leg, so a long run can be followed by polling files.
- **Publishable output.** Home directory paths are replaced with `~` in every file of a run directory, and the
  host is identified by a keyed hash whose key stays on the bench box.

## Method v2 (2026-11)

What changed against the first version, and why:

- **Paired effect with an interval as the headline.** v1 reported the ratio of the two arms' medians, which
  ignores the pairing the schedule pays for. v2 reports the mean per-round log ratio with a 95% t interval, one
  primary metric per row with Holm across the rows, everything else exploratory.
- **Balanced, longer, adaptive runs.** v1 ran 6 rounds of `abba`, which pins the middle arm of three to one
  position, and where an exact test can only reject at 6 of 6. v2 uses `rotate` for 3 or more arms, a seeded coin
  per round pair, even round counts, re-runs of invalid rounds, and 12 to 36 rounds stopped on interval width.
- **An A/A rule with power.** v1 passed when the sign test found nothing on 6 pairs, which a 3% bias passes most
  of the time. v2 requires no Holm-significant difference and a 95% half-width of at most 0.5% (instructions) and
  1% (total cycles; 3% until the release rows started claiming cycle effects of about 1%).
- **The verdict marks effects the A/A could not exclude.** Given an A/A run, a difference whose size is within the
  A/A half-width is reported as "differs, inside the A/A floor", and one within the far end of the A/A interval
  as "differs, inside the A/A interval". Such a row is not a finding on its own.
- **More gates.** Pending total, during-window idle on the SUT CPUs and their SMT siblings, uneven Envoy
  worker load, multiplexed counters, Envoy exit code.
- **Less noise.** A noise hunt on the A/A configuration (one change at a time, 12 rounds each) found the main
  source: with Nighthawk's default MRU connection reuse, 2, 3 or 4 Envoy workers carry the load, differently on
  every leg, and per-request cycles follow the busiest worker's share. LRU reuse removes it. Keeping the SUT's SMT
  siblings idle helped a little more; arrival jitter and fewer client connections did not.

  | Step (pair SD of total cycles, log-%) | /s | /fh |
  |---|---|---|
  | v1 settings | 5.8 | 6.4 |
  | v1 settings, v2 harness | 6.9 | 6.5 |
  | + SUT without SMT siblings | 7.1 | 5.2 |
  | + LRU connection reuse (SMT siblings in the SUT set) | 1.3 | 1.9 |
  | LRU + arrival jitter | 1.6 | 1.6 |
  | LRU + SUT without SMT siblings (kept) | 0.8 | 1.9 |
  | LRU + half the client connections | 1.8 | 3.1 |

- **The >10 ms latency maxima are start-up.** A 6 s run shows the same maximum as a 25 s run; it falls with the
  number of connections the client sets up at once. Latency comes from the whole client run, so p99.9 and the
  maximum describe connection set-up, not steady state; p50 and p99 are steady state.

With these settings the A/A (12 rounds, 72 of 72 legs valid) gives a 95% half-width on the mean of the paired log
ratios of 0.01 to 0.05% for instructions, 0.4 to 1.4% for total cycles, 1.0 to 2.0% for p50 and 0.9 to 4.6% for
p99, on this machine. A release or setting row needs an effect clearly outside those to be called a difference.

## Layout

```
bin/epl                 launcher (no install needed)
epl/experiment.py       config defaults and checks, balanced schedule, adaptive run loop, metadata, analysis
epl/leg.py              one leg: idle check, preflight, start Envoy pinned, warm-up, perf window, stop, verdict
epl/validity.py         the per-leg validity verdict
epl/stats.py            paired log ratio with t interval, Holm, sign test, Wilcoxon signed-rank (exact)
epl/sysprobe.py         /proc readers, port probe, pgrep -f, hashes, machine metadata
epl/nighthawk.py        client arguments and JSON parsing
epl/envoy_config.py     generated Envoy bootstrap (shapes) and origin config
epl/origin.py           origin: own nginx container (pinned) or an external port
epl/sim.py              simulated backend for --dry-run
epl/report.py           Markdown summary
tests/                  offline tests (statistics, gates, schedule, dry runs)
examples/               experiment configs and their generators (see below)
```

## Example config sets

| Path | What it measures |
|---|---|
| `examples/aa-selftest.json` | A/A: one release binary against itself, the harness self-test |
| `examples/pilot-releases.json` | three official Envoy releases (v1.32.13, v1.36.13, v1.40.2) on three shapes |
| `examples/settings-matrix/` | one experiment per setting against the baseline v1.40.2 config: TLS certificate type, session resumption, HPACK table size, tracing, access logs, external authorization, retries, buffer limits, tcmalloc per-CPU caches, a second hop (`01-` to `10-`), and the A/A that serves as their floor (`aa.json`). Written by `make.py`; `run-all.sh` queues rows; `table.py` builds the matrix-wide table with Holm across every primary row |
| `examples/settings-matrix/followups/` | follow-ups to the first matrix runs: the second hop with both proxies evenly loaded, the buffer limit with a body that fits, ext_authz over HTTP and gRPC, the TLS rows with reconnects spread out in time, and A/A runs on the TLS and HTTP/2 shapes. Written by `followups.py`; `run-followups.sh` queues them; `followups_table.py` builds their table; `saturation.py` is a short saturation probe |
| `examples/settings-matrix/filters/` | two more setting rows against the same baseline: the JWT authentication filter with a local JWKS (RS256, every token verified, and with the filter's cache of verified tokens; every arm's client sends the same token) and the local rate-limit filter (enabled and enforced, budget far above the test rate). Written by `filters.py`; `jwt_token.py` made the test JWKS and token in `filters/jwt.json` (the private key was not kept). Their A/A floor is the A/A arm of the release run below (`floor_arm`) |
| `examples/releases/` | six official releases (v1.32.13, v1.34.14, v1.36.13, v1.37.11, v1.38.9, v1.40.2) at two load levels, each shape at the matrix rate and at a higher one, with a second copy of v1.40.2 as an A/A arm interleaved in the same rounds. Written by `make.py`; `run-session.sh` queues the release run and the two filter rows; `table.py` builds the tables, with the A/A-spread half-widths |
| `examples/release-record/` | release record/1 (see [RELEASE-RECORD.md](RELEASE-RECORD.md)): the configs of its first session, written by `make.py` (Run A: seven releases and the A/A copy of v1.40.2 on four cells, with confirmatory rows named before the run; Run C: hardware counters in three event groups; Run B: the v1.38 patches one by one; three smoke runs), `static.py` for the per-tag static record (size, sections, compiler string, digest, build id) and `table.py` for the tables |
| `examples/upstream-pool-lru/` | an experimental Envoy build that can reuse the least recently freed upstream connection instead of the most recently freed one (selected per process by an environment variable). The patch is one commit on Envoy v1.40.2, branch [`exp/upstream-pool-lru`](https://github.com/We-Amp/envoy/tree/exp/upstream-pool-lru) of We-Amp's Envoy fork (set `ENVOY_EXP_UPSTREAM_POOL_LRU=1` to switch the order); build it yourself and point the config at the binary. `make.py` writes the two-hop, one-hop and probe configs, `make_demand.py` the demand-grown pool follow-up, `make_burst.py` the stall-recovery runs; `table*.py` build their tables |
| `examples/route-table/` | recorded route tables and a recorded route with 109 constant headers (57 request, 52 response; because the route is a direct response, Envoy applies only the 52 response headers and the virtual host's 8, so 60 headers run per request), used as they are (shape kind `routes`: `route_table.routes` in order, optional `route_table.vhost` header fields). One virtual host of direct responses with 1, 200 or 1,000 routes, the request matching the last one; base, path first (branch `patches/route-match-path-first-v4` of We-Amp's Envoy fork), a route index prototype that is not proposed upstream (identified by its md5 only), and a second copy of base as the A/A arm; and base against the header change (branch `patches/router-header-reference-v3`) on the 109-header route. Each at 2,000 req/s and at a higher calibrated rate. `tables/` holds the tables, converted by `tables/from_yaml.py` (each keeps the md5 of its source); `make.py` writes the configs, `run-session.sh` queues the four runs, `table.py` builds the tables |
| `examples/stats-flush/` | the stats-flush row: what N stats cost Envoy's main thread per flush, with and without a sink. Idle legs (shape kind `idle`: no client; the main thread's scheduler run time sampled at 50 Hz, its flush bursts found in the series, perf on that thread), K generated static clusters per rung (`stats_clusters`, seeded service-like names, primed with one paced request each), the flush on a timer or on admin reads only (`stats_flush`), the plain statsd sink to a drain-only UDP discard sink whose evidence is the kernel's own UDP counters, dog_statsd with a datagram buffer, the OTLP sink to a null collector, and the Prometheus scrape path (`stats_sink`, `prom_scrape_s`); a loaded run at one rung. `make.py` writes the configs per machine description in `boxes/` (everything machine-specific comes from there; `epl portability-check` verifies that an x86_64 and an aarch64 description give the same Envoy bootstraps and no foreign literal); `run-session.sh` runs calibration (`epl stats-calibrate`), the smoke (with `epl flush-profile`), the offline evidence check and the queue, and raises `net.core.rmem_max` to 256 MiB for the discard sink for its own duration only (`sysctl-guard.sh` restores it on exit); `table.py` builds the curve, the fit and the rows. `sibling.json` (stat updates per request) and `ab-template.json` (a later A/B of a fix) are templates, not part of the session |

The configs carry the paths, CPU sets and rates of the machine they were run on; treat them as templates.

The stats-flush row builds on the analysis of the stats snapshot's cost at high stat counts by Joshua Marantz in
upstream Envoy issue 43836, with a proposed approach in upstream pull request 43958 (and 44031, 44285) and in his
public design document "Improving Stats Sink Efficiency"
(https://docs.google.com/document/d/1NTChsnybxyG04rqhEKoG39O43ibNKntAn1Ts8EbmKcM/edit). Two lock-free release fast
paths were merged upstream since, pull requests 45821 (by `ebm`) and 46001 (by `davidvo-lyft`); both are in v1.39.0
and later, so v1.40.2 has them: its curve is the cost with those fast paths, which his microbenchmark predates. His
figures are quoted from pull request 43958; ours are end-to-end measurements of a running proxy and are not directly comparable.

## Usage

```sh
# offline: statistics, validity gates, schedule, simulated A/A and A/B runs
python3 bin/epl selftest

# check a config and print the schedule (values can be overridden with --set key=value)
python3 bin/epl plan examples/pilot-releases.json
python3 bin/epl plan examples/aa-selftest.json --set client.binary=/opt/nighthawk/nighthawk_client

# simulated end-to-end run (no Envoy needed)
python3 bin/epl run examples/aa-selftest.json --dry-run --out /tmp/epl-dry

# on the bench box itself
python3 bin/epl calibrate examples/pilot-releases.json --arm v1.32.13 --shape fh --rps 4000,8000
python3 bin/epl run examples/pilot-releases.json              # foreground
python3 bin/epl run examples/pilot-releases.json --detach     # prints the run dir, keeps running
python3 bin/epl status ~/epl/runs/pilot-releases-20261113T190000Z
python3 bin/epl report ~/epl/runs/pilot-releases-20261113T190000Z/results.json --floor ~/epl/runs/aa-selftest-20261113T180000Z/results.json

# from a workstation: ships the harness and config over ssh, runs detached there
python3 bin/epl remote --root epl benchbox run examples/pilot-releases.json
python3 bin/epl remote benchbox status epl/runs/pilot-releases-20261113T190000Z
python3 bin/epl remote benchbox fetch  epl/runs/pilot-releases-20261113T190000Z ./results
```

Paths in a config (binaries, client, workdir) are paths on the machine that runs the experiment. A bare program
name (`nighthawk_client`, `perf`) is looked up on that machine's PATH.

## Config

See `examples/pilot-releases.json`. Main sections:

| Key | Meaning |
|---|---|
| `arms[]` | `name`, `binary`, optional `md5`, `source`, `source_sha256`, `extra_args` |
| `base_arm` | the arm every other arm is compared against |
| `rounds`, `rounds_block`, `rounds_max`, `adaptive` | minimum rounds (>= 12), block size, cap (<= 36); `adaptive: false` runs exactly `rounds` |
| `stop` | `target_half_width_pct` (default 3.0) for the primary metric |
| `confirmatory` | `[arm, reference]` pairs named before the run: their own Holm family, reported apart from the other comparisons |
| `stop.rows` | `confirmatory`: the stop rule looks at the confirmatory rows only (default: every comparison) |
| `order`, `order_seed` | `auto` (default: `abba` for 2 arms, `rotate` for 3+), `abba` or `rotate`; the seed of the per-pair coin |
| `comparisons` | `base` (every arm against `base_arm`) or `all_pairs` |
| `primary_metric` | the metric Holm runs over (default `cycles_total`); the rest is exploratory |
| `floor_from` | an A/A `results.json` whose half-widths are printed next to every row and used to mark effects inside the A/A floor or interval |
| `floor_arm` | with `floor_from`: take the floor only from this arm's comparisons (an A/A arm inside another experiment, such as a second copy of the base binary in a release run); `report --floor-arm` does the same |
| `shapes[]` | `proxied` (origin serves `body_bytes`) or `direct_headers` (direct response plus N request / M response headers added); `rps` is the total target rate |
| `envoy` | workers, listener and admin ports, `exact_balance` |
| `cpus` | `sut`, `client`, `origin` CPU lists; must be disjoint; optional `harness` (default: every CPU no set uses) |
| `client` | Nighthawk binary, concurrency, connections per worker, idle strategy, warm-up and run length, extra args |
| `measure` | lead-in and perf window in seconds, perf command |
| `measure.perf_events`, `measure.perf_event_groups` | a perf event list for every leg, or several lists rotated by round (every arm of a round counts the same list, so paired rounds compare like with like). Each list needs `instructions:u` and either `cycles:u` + `cycles:k` or `cycles` (user and kernel on one counter, which frees a programmable counter); further events are stored per request. One-hop experiments only; the default list is unchanged |
| `shapes[].lead_in_s` | a later start of the window for one shape (for a client that ramps its rate up) |
| `validity` | rate tolerance, minimum client headroom, maximum overflow and non-2xx, pending total, foreign and sibling CPU during the window, exit code, multiplexing, optional `min_eff_ghz` and latency-only `max_latency_ms` |
| `idle` | load, busy and per-CPU busy thresholds, `pgrep -f` patterns, timeout |
| `origin` | `docker` (own nginx container) or `external` |
| `expect: "aa"`, `aa` | mark an A/A run; `aa.metrics` and `aa.max_half_width_pct` set the self-test |
| `arms[].settings` | one generic setting merged into `envoy` for this arm's own bootstrap (see below) |
| `arms[].env` | environment variables for this arm's Envoy (for example a glibc tunable) |
| `shapes[].client_extra_args`, `shapes[].validity` | client arguments and gate overrides for one shape (TLS parameters, a new connection every N requests) |
| `shapes[].client_base_args` | replaces `client.extra_args` for one shape (for example no prefetch and the client's default connection reuse, so reconnects spread out in time) |
| `arms[].validity` | gate overrides for one arm, applied after the shape's (for example the second hop's share gate for an arm meant to measure a concentrated chain) |
| `cpus.hop2`, `hop2` | CPUs and ports of the second Envoy of a two-hop arm |
| `collector` | image (pinned by digest) and port of the null OpenTelemetry collector for tracing arms |

## Settings rows

An arm can differ from the baseline config in one generic setting (`arms[].settings`), and every arm gets
its own bootstrap (`envoy-bootstrap-<arm>.json`, each validated with `--mode validate` and hashed in the
metadata). The settings are:

| Setting | What the arm gets |
|---|---|
| `tls` | TLS on the listener with a self-signed `rsa2048` or `ecdsa-p256` certificate made with openssl in the run directory; `resumption: false` disables stateless and stateful session resumption. The client URL becomes `https`; TLS client parameters are per shape |
| `hpack_table_size` | `http2_protocol_options.hpack_table_size` (with `codec_type: HTTP2` and an `--h2` client) |
| `tracing` | the OpenTelemetry tracer over gRPC to a local null collector (OTLP receiver, `nop` exporter, own container on the origin CPUs) with `random_sampling` at `sampling_pct` |
| `access_log` | a file access log in Envoy's default text format, or JSON with the same fields; the harness empties the file before each leg and records its line count after |
| `ext_authz` | `true`/`"http"`: the HTTP ext_authz filter against a local allow service (a second nginx server in the origin container, `origin.authz_port`, answering 200); `"grpc"`: the gRPC form against a third nginx server (`origin.authz_grpc_port`, h2c) that answers every Check with an empty CheckResponse and `grpc-status: 0` |
| `retries` | a retry policy on proxied routes (`5xx,reset,connect-failure`, 2 retries); the leg records the retry counter, which should stay 0 |
| `buffer_limit_bytes` | `per_connection_buffer_limit_bytes` on the listener and the origin cluster |
| `upstream_pool_per_downstream` | `connection_pool_per_downstream_connection` on the origin cluster: one upstream pool, so one upstream connection, per downstream connection |
| `jwt_authn` | the JWT authentication filter before the router, one provider with a local JWKS (`jwks`, `issuer`, `audience`; no fetch), required on every route; the token is forwarded upstream. `cache: true` adds the filter's cache of verified tokens (`jwt_cache_config`). The client sends the token per shape (`client_extra_args`); the leg records `jwt_authn` allowed and denied counts |
| `local_ratelimit` | the local rate-limit filter before the router, one token bucket shared by the workers (`tokens_per_s` per second), enabled and enforced on 100% of requests; the leg records its `ok`, `enforced` and `rate_limited` counts |
| `hop2_settings` | settings for the second Envoy of a two-hop arm (by default it runs the baseline config) |
| `two_hop` | client → this Envoy → a second Envoy on `cpus.hop2` (baseline config) → origin. perf runs on both; the extra metrics `cycles_total_all` (every hop) and `cycles_total_per_hop` exist only in an experiment with `cpus.hop2`, where a one-hop arm counts as one hop. Gates (worker share, during-window idle, pinning, exit code) cover both hops |

Each leg also records the deltas of the relevant Envoy counters (`sut_stats_delta`: TLS handshakes and
resumed sessions, ext_authz results, tracing decisions, retries, flow-control pauses and resumes), the
cumulative TLS version, cipher, group and signature-algorithm counters and the open-connection gauges at the end
of the window (`sut_stats_end`, `hop2_stats_end`), the busiest and least busy worker as a fraction of one CPU,
the connection spread towards the second hop (`conn_hop2_downstream`) and the bytes in tcmalloc's per-CPU slabs
from `/memory/tcmalloc` (0 means the per-CPU caches are inactive). `examples/settings-matrix/make.py` writes
one experiment per row of the settings matrix, and the A/A that serves as its floor.

## Output

Each run writes a directory with:

- `results.json`: metadata (harness version, kernel, CPU model, topology, governor and clock per pinned CPU,
  the cpuidle driver and governor and, per idle state, its exit latency and the SUT CPUs it is disabled on
  (`cpuidle_sut_summary`, also printed in `summary.md`, with a fingerprint checked on every leg and at the end;
  deep idle states change what a request costs when the load is spread thin, and the harness never changes them),
  binaries with md5/sha256/version, Nighthawk version/md5/settings and its commit (from the config
  `client.commit`, or from `--version` when the build prints one; otherwise none, and the md5 identifies it), perf version, config and bootstrap hashes,
  origin image ID), every leg with its raw counters and verdict, and the analysis;
- `summary.md`: medians and per-leg CV per arm and shape, comparisons with paired effect and 95% interval,
  invalid and superseded legs with reasons;
- `legs.jsonl`, `status.json`, `log.txt`: written as the run progresses;
- `envoy-bootstrap.json`, `experiment.json`, `nighthawk/`, `perf/`, `logs/`, `origin/`: raw inputs and outputs.

The host is recorded as `host_id`, an HMAC of the host name under a random key kept in
`~/.config/epl/host-salt` on the bench box, unless `record_hostname` is set. Home directory paths are written as
`~`; `epl scrub RUN_DIR` does the same for a run directory recorded by an older version.

## Self-test

`selftest` runs the offline tests. The real check is an A/A run of one binary against itself
(`examples/aa-selftest.json`). It passes when, on every shape, for instructions and total cycles:

- the difference is not significant after Holm across all the A/A checks (paired t), so a harness without bias
  fails at most 5% of the time overall; and
- the 95% interval half-width is at most 0.5% (instructions) or 1% (total cycles), so the run could have seen a
  bias of that size. The summary prints, per check, the bias the run detects with 80% power. An A/A run keeps
  adding rounds (up to the cap) until it reaches these limits.

Set the limits (`aa.max_half_width_pct`) from the smallest effect the runs that rely on the A/A intend to claim:
an A/A that passes at ±3% says nothing about a +1.2% release row. The old rule (sign test p > 0.05 on 6 pairs)
failed only on a 6 to 0 split, so it passed a real 3% bias most of the time. In the simulator (pair SD of total
cycles about 2.2%, median 30 rounds) the current rule passes 96 of 100 unbiased runs, catches a 1% cycle bias in
42 of 100 and a 2% bias in 100 of 100.

An earlier 12-round A/A passed under the 3% limit but not under the 1% limit (its `/fh` cycle row had a
half-width of 1.37%), so A/A runs are now longer.

## Data

`data/` holds the measurement records, tables and configs behind the published price list, one folder per
experiment; see [data/README.md](data/README.md).

### Week 4 update (16 November 2026)

The update of the post on 16 November added a second release session at two load levels and two setting
rows, all measured in one session. Where each section of the post comes from:

| Post section | Configs | Data |
|---|---|---|
| How every number is measured: the A/A floor of the second release session | `examples/releases/releases.json`, arm `v1.40.2-A2` | `data/releases-backfill/releases/` |
| Settings: JWT authentication (local JWKS, RS256) | `examples/settings-matrix/filters/11-jwt-authn.json`, with the test JWKS and token in `filters/jwt.json` | `data/settings-filters/11-jwt-authn/` |
| Settings: Local rate limit, never triggered | `examples/settings-matrix/filters/12-local-ratelimit.json` | `data/settings-filters/12-local-ratelimit/` |
| Releases | `examples/releases/releases.json` (written by `make.py`) | `data/releases-backfill/` |

Harness changes for this session: the `jwt_authn` and `local_ratelimit` settings (see "Settings rows"),
`floor_arm` (an A/A floor taken from one arm of another run), and a client rate ramp over the first second on
the two higher-rate release shapes (`client_extra_args` in `examples/releases/make.py`). The session ran as

```bash
examples/releases/run-session.sh --set client.binary=~/nighthawk/bazel-bin/nighthawk_client
python3 examples/releases/table.py ~/epl/runs/wk4/releases ~/epl/runs/wk4/11-jwt-authn \
    ~/epl/runs/wk4/12-local-ratelimit --json tables.json > tables.md
```

### Route table and constant-header re-measure (16 November 2026)

The route-table and header changes re-measured with the full method: 16 to 24 rounds, the load spread over
every client connection, an A/A arm in the same rounds, 95% intervals. Four runs in one session:

| Run | Configs | Data |
|---|---|---|
| 1,000 routes: base, path first, route index prototype, A/A | `examples/route-table/rt-n1000.json` | `data/route-table/rt-n1000/` |
| 200 routes: the same four arms | `examples/route-table/rt-n200.json` | `data/route-table/rt-n200/` |
| One route, the control (three builds, no A/A arm) | `examples/route-table/rt-n1.json` | `data/route-table/rt-n1/` |
| 109 constant headers (60 applied on the direct response): base, the header change, A/A | `examples/route-table/hdr.json` | `data/route-table/hdr/` |

The tables of all four runs are in `data/route-table/tables.md` and `tables.json`. The session ran as

```bash
python3 examples/route-table/make.py
examples/route-table/run-session.sh
python3 examples/route-table/table.py ~/epl/runs/route-table/rt-n1000 ~/epl/runs/route-table/rt-n200 \
    ~/epl/runs/route-table/hdr ~/epl/runs/route-table/rt-n1 --json tables.json > tables.md
```

### Release record (16 November 2026)

The Releases section of the post, from 17 November, is kept as a release record: a fixed protocol, an anchor
release and an A/A copy in every session, and one entry per session. The protocol (record/1) and the first entry
are in [RELEASE-RECORD.md](RELEASE-RECORD.md).

| Run | Configs | Data |
|---|---|---|
| Static record of 13 release binaries | `examples/release-record/static.py` | `data/release-record/2026-11-16/static.json` |
| A: seven releases and the A/A copy, four cells, confirmatory rows v1.38.0 against v1.37.11 | `examples/release-record/run-a.json` | `data/release-record/2026-11-16/run-a/` |
| C: hardware counters (exploratory) | `examples/release-record/run-c.json` | `data/release-record/2026-11-16/run-c/` |
| B: the v1.38 patches one by one (exploratory) | `examples/release-record/run-b.json` | `data/release-record/2026-11-16/run-b/` |

The tables are in `data/release-record/2026-11-16/tables-a.md`, `tables-c.md` and `tables-b.md` (and `.json`).
Harness changes for this session: `confirmatory` rows and `stop.rows`, `measure.perf_events` and
`measure.perf_event_groups`, and `shapes[].lead_in_s` (see "Config").

## License

Copyright 2026 We-Amp B.V.

The code is licensed under the Apache License 2.0; see [LICENSE](LICENSE). The measurement data in `data/` is
licensed under Creative Commons Attribution 4.0 International (CC BY 4.0); see [data/LICENSE](data/LICENSE).
