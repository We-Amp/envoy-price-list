# Wave 2: code layout of Envoy v1.40.2

What a stock-like Envoy build gives up to a better code layout, and how much of the PGO gain comes
without a training harness. Every arm is an own build of tag v1.40.2 with the release options; the
build scripts are in [`tools/code-layout`](../../tools/code-layout), the top-down counters and LBR legs
that motivated and fed the builds in [`examples/topdown`](../topdown). Data: the `code-layout` archive
of the wave studies (`python3 tools/fetch-wave-data.py code-layout`, see
[`docs/wave-studies.md`](../../docs/wave-studies.md)).

## Conditions

- Bench box (`bench-x86_64/`, the box of [`examples/wave1-b`](../wave1-b)): two-socket Xeon E5-2673 v4
  (2 x 20 cores, SMT on), bare metal, 2.3 GHz fixed, turbo off. Envoy on CPUs 0-3 (4 workers) with their
  SMT siblings idle; client (Nighthawk) on 20-31,60-71; origin (`nginx:alpine`, pinned digest) on
  32-39,72-79.
- Binaries (`bins.json`, each pinned by sha256; `make.py` writes a config only when all its binaries are
  pinned, and the session chain checks every pin before it starts):

  | Arm | What it is |
  |---|---|
  | `opt` | plain `-c opt`; byte-identical to the official v1.40.2 release asset, so the box's `~/epl/bin/envoy-1.40.2` is used (base, and `opt-A2` as the A/A) |
  | `order` | the `opt` objects relinked with an lld call-graph ordering file (cdsort) from LBR legs of the official binary |
  | `autofdo` | sampled PGO (v2): `llvm-profgen` 22.1.8 on the `lbr-w2-opt` legs, `-fprofile-sample-use` + ThinLTO |
  | `pgolto` | instrumented PGO (the nine-leg trainer of the `pgo-recipe-v1` kit) + ThinLTO |
  | `pgolto-relocs` | `pgolto` relinked with `--emit-relocs`, debug info stripped: the BOLT input |
  | `bolt` | `llvm-bolt` 22.1.8 on `pgolto-relocs` with the `lbr-w2` profile |
  | `autofdo-order` | the `autofdo` objects relinked with the `order` file |

- Shapes (as [`examples/topdown`](../topdown)): `s` (4 KB proxied, 5,200 req/s), `fh` (direct
  response with 57 request and 52 response headers added, 8,000 req/s), `fl` (the same header sets on a
  proxied route, 5,200 req/s).
- Counters: cycles and instructions in user and kernel space per response; two perf event groups
  rotated by round (TMA level 1 in user space, i-cache). Paired rounds; the effect is the mean per-round
  log ratio, with the 95% t interval and the widened interval 1.96 x sqrt(SE^2 + 0.34^2).
- Order of arms: `w2` one 6 x 6 Latin square (6 rounds); `w2b` a Williams square (balanced first-order
  carryover) of 6 arms on shape `s`, with one unscored warm-up leg of the base arm before every round.

## Runs

| Config | What |
|---|---|
| `lbr-w2.json` | profiling legs: `perf record -b` of `pgolto-relocs` through `perf-lbr.sh`, 30 s windows, two legs per shape (the BOLT profile) |
| `lbr-w2-opt.json` | the same for `opt` (the AutoFDO v2 profile, about 15 times the samples of the top-down legs) |
| `w2.json` | `opt` (base), `opt-A2`, `order`, `autofdo`, `pgolto`, `bolt` on `s`, `fh`, `fl`; 6 rounds |
| `w2-nobolt.json` | the same without `bolt` (written, not run) |
| `w2b.json` | shape `s`: `pgolto` (base), `pgolto-A2`, `pgolto-relocs`, `bolt`, `autofdo`, `autofdo-order`; 6 rounds, Williams order, warm-up legs |

Each `smoke-*.json` is one round of its run; the run is checked against the evidence frozen from it.

## Files

- `make.py` writes the configs (`python3 examples/wave2/make.py`).
- `run-w2.sh prof|smoke|check|queue`, `chain-w2.sh prof|ab`: the sessions as run.
- `perf-lbr.sh`: the perf wrapper of the profiling legs; for the harness's window command it records
  `perf record -b` of the same PID for the same seconds (`W2_PERF`, `W2_LBR_OUT`, `W2_LBR_PERIOD`).
- `pack.sh OUT.tgz`: a `git archive` of the harness with `HARNESS_COMMIT` and `VERSION`, for a bench box
  that is not a git checkout, so the run metadata names the commit.
- `analysis/analyse_w2.py RUN_DIR OUT_MD` and `analysis/analyse_w2b.py RUN_DIR OUT_MD [W2_RUN_DIR]`: the
  tables and the decision rules fixed before each run.

The commands that render every table from the data are in [`docs/wave-studies.md`](../../docs/wave-studies.md).
