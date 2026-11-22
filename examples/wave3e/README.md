# Wave 3, track E: the price of one new connection

What a new downstream connection costs Envoy v1.40.2 per connection, plaintext and TLS 1.3 (full and
resumed handshakes, certificate type, key-exchange group), and what three listener accept settings do
under churn. Config only: the official binary in every arm. Data: the `connection-churn` archive of the
wave studies (`python3 tools/fetch-wave-data.py connection-churn`, see
[`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Bench box (`bench-x86_64/`): two-socket Xeon E5-2673 v4 (2 x 20 cores, SMT on), bare metal, 2.3 GHz
  fixed, turbo off. Envoy on CPUs 0-3 (4 workers) with their SMT siblings idle; client on
  20-31,60-71; origin (`nginx:alpine`, pinned digest) on 32-39,72-79.
- Binaries: the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…`) in every arm;
  Nighthawk 0.3.0 (md5 `310df412…`) as the client. `chain-e.sh` checks both before it starts.
- Every arm differs from its run's base by config only (Envoy settings or the client's connection
  settings). Two changes for churn hold in every arm of a run:
  - one listener on 127.0.0.1 plus 15 `additional_addresses` (127.0.0.1-127.0.0.16: one filter chain,
    one TLS context, nothing reachable from outside the box); the one-request-per-connection arms
    spread their connections over those 16 destinations (Nighthawk `--multi-target-endpoint`, round
    robin), so no source/destination pair runs short of ports;
  - `exact_balance` off (the kernel's reuse-port placement), so the balancer's per-accept work is not
    part of the per-connection price.
- Rates: 1,600 req/s plaintext, 800 req/s TLS. The box's connection-tracking table (`nf_conntrack_max`
  262,144, TIME_WAIT entries live 120 s) puts the sustained ceiling at about 2,000 new connections per
  second with back-to-back legs. The harness reads the kernel TCP counters, the TIME_WAIT count and the
  conntrack fill around every window (`measure.kernel_net`), and the configs gate every leg on them
  (listen overflows and drops, request-queue drops, TIME_WAIT overflows, failed connects, conntrack fill).
- Order: Williams squares (balanced first-order carryover) with one unscored warm-up leg of the base
  arm before every round. Per-connection price = (arm - reference) cycles per request, paired by round,
  divided by the connections per request of the arm (1.000 for a churn arm).

## Runs

| Config | Arms | Rounds |
|---|---|---|
| `e-plain.json` | `ka` (keep-alive, base), `ka-A2`, `c1` (one request per connection) | 6 |
| `e-tls.json` | `ecdsa-full` (base), `ecdsa-full-A2`, `rsa-full`, `ecdsa-res` (resumed), `ecdsa-x25519` (listener groups X25519 and P-256 only), `tls-ka` (keep-alive) | 6 |
| `e2-plain.json` | `c1` (base), `c1-A2`, `c1-defer` (`TCP_DEFER_ACCEPT` 1 s), `c1-shared` (one listen socket shared by the workers), `c1-xb` (`exact_balance`), `ka` | 6 (its smoke failed the gates; not run) |
| `e2b-plain.json` | `c1`, `c1-A2`, `c1-defer`, `ka` (the arms of `e2-plain` that can be priced) | 8 |

Each `smoke-*.json` is one round of its run; the run is checked against the evidence frozen from it.

## Files

- `make.py` writes the configs (`--rates` and `--res-single-target` are the smoke fallbacks fixed
  before the run; none was needed).
- `run-e.sh smoke|check|queue`, `chain-e.sh`, `box-start.sh`: the sessions as run (`E_RUNS` picks the
  runs, `E_HRR=1` runs `hrr_check.py` first).
- `hrr_check.py`: a direct check, with the runs' own client and TLS socket, of whether a listener's
  key-exchange setting makes the client retry its handshake (HelloRetryRequest); it counts the
  retries on a relay between client and Envoy.
- `local_check.py validate|tls|multi|defer WORKDIR`: checks in Docker off the bench box (every
  bootstrap validates; what each TLS arm negotiates; the 16-address listener; the accept settings).
- `table.py RUN_DIR ...`: the per-connection rows of a run.

The commands that render every table from the data are in [`docs/wave-studies.md`](../../docs/wave-studies.md).
