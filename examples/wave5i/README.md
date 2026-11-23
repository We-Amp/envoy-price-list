# Wave 5, track I: code layout on arm64 (cloud VM)

The code-layout question of wave 2 ([`examples/wave2`](../wave2)) on arm64: what the official arm64 v1.40.2
release gives up to instrumented PGO + ThinLTO (and an ordering file, held: see below), on a current Arm server
core in a cloud VM. Data: the `arm-vm-layout` archive of the third wave release
(`python3 tools/fetch-wave-data.py arm-vm-layout`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)).
Build scripts: [`tools/code-layout/arm`](../../tools/code-layout/arm).

## Conditions

- Box (`boxes/arm-vm-w5i.json`): a current Arm server core (Neoverse V2 class) in a cloud VM, 16 vCPU (16
  cores, no SMT), PMU on. Envoy on CPUs 0-3 (4 workers), client on 4-11, origin (`nginx:alpine` for arm64,
  pinned digest) on 12-15; the harness is not pinned (no core left). `perf_event_paranoid` lowered at runtime
  on the VM only.
- Binaries (`bins.json`, pinned by sha256, checked before the first leg of every run):
  - `official`: the official `envoy-1.40.2-linux-aarch_64` release asset (sha256 `b9d6d1e0…213baf`). Our own
    `-c opt` build of v1.40.2 is byte-identical to it, so `opt` is not a separate arm;
  - `order`: the `opt` objects relinked with an lld call-graph ordering file (cdsort) made from frame-pointer
    call chains of `opt` (`perf-fp.sh`, `fp2order.py`; the VM exposes no SPE, BRBE or trace unit, so no
    branch-sample profile, AutoFDO or BOLT here);
  - `pgolto`: instrumented PGO (the nine-leg trainer of the `pgo-recipe-v1` kit, run on this VM) + ThinLTO;
  - `pgolto-v2`: `pgolto` with `-mcpu=neoverse-v2` (same profile).
  The binaries are not published; their sha256 are in `bins.json` and in the data archive.
- Shapes `s` (4 KB proxied), `fh` (direct response, 57 + 52 headers) and `fl` (the same headers on a proxied
  route), all at 5,200 req/s (on this VM `fh` queued client requests in bursts at 8,000 req/s); 64
  connections per client worker.
- Method: Williams order, 10 rounds (5 s client warm-up per leg); paired per-round log ratios with the
  95% t and widened 1.96 x sqrt(SE^2 + 0.34^2) intervals, the wider one deciding.

**Held, not confirmed: the ordering-file (`order`) figures of this run.** The control (the same code in a separate file, where no effect is expected) was not run on this host, so the run cannot tell a code-layout effect from a file-placement effect. On bare metal ([`examples/wave6j`](../wave6j)) the file control was null and the ordering file gave 4-7%. The VM figures stay in the data; we do not quote them as a result.

## Runs

| Config | Arms | Rounds |
|---|---|---|
| `arm-vm-w5i/fp-w5i.json` | `opt`, `opt-2` (frame-pointer profiling legs through `perf-fp.sh`) | 1 |
| `arm-vm-w5i/w5i.json` | `official` (base), `official-A2`, `order`, `pgolto`, `pgolto-v2` | 10 |

`arm-vm-w5i/smoke-w5i.json` is one round of the A/B run, evidence frozen from it.

## Files

- `make.py` writes the configs (`--box`, `--bins`).
- `run-w5i.sh`, `chain-w5i.sh`: the sessions. With `SELF_SHUTDOWN=1` (opt-in, default off; needs passwordless
  sudo) the A/B chain powers the machine off 20 minutes after it ends unless `~/w5i/KEEP` exists, so a rented VM
  does not idle and bill.
- `perf-fp.sh`: the perf wrapper of the profiling legs (`perf record --call-graph=fp` for the window).
- `fp2order.py edges|span`: frame-pointer call chains to the ordering file and the hot-set page span.
- `analysis/analyse_w5i.py RUN_DIR OUT_MD`: the table and the decision rules fixed before the run; it marks the
  `order` rows as held.
