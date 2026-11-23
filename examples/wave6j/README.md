# Wave 6, track J: code layout on arm64 bare metal, with SPE profiles and a file control

Track I ([`examples/wave5i`](../wave5i)) on arm64 bare metal, where the Statistical Profiling Extension (SPE)
gives branch samples: AutoFDO and BOLT from SPE profiles, beside the ordering file and PGO + ThinLTO of track I,
and a file control (`opt-file`: the same bytes as `official` in a separate file) that separates a code-layout
effect from a file-placement effect. Data: the `arm-metal-layout` archive of the third wave release
(`python3 tools/fetch-wave-data.py arm-metal-layout`, see [`docs/wave-studies.md`](../../docs/wave-studies.md)).
Build scripts: [`tools/code-layout/arm`](../../tools/code-layout/arm).

## Conditions

- Box (`boxes/arm-metal.json`): a current Arm server core (reports Neoverse N3), bare metal, 96 cores (one socket,
  one NUMA node, no SMT). Envoy on CPUs 0-3 (4 workers), client on 4-11, origin (`nginx:alpine` for arm64,
  pinned digest) on 12-15, the rest idle; the harness is not pinned. `perf_event_paranoid` lowered at runtime.
- Binaries (`bins.json`, pinned by sha256, checked before the first leg of every run):
  - `official`: the official arm64 release asset (sha256 `b9d6d1e0…213baf`);
  - `opt-file`: track I's own `-c opt` build, byte-identical to `official`, as a separate file (the file control);
  - `order`, `pgolto`, `pgolto-relocs`: track I's builds (built on the Neoverse V2 VM);
  - `autofdo`: v1.40.2 + ThinLTO + `-fprofile-sample-use` with a profile from `create_llvm_prof
    --profiler=perf_spe` (google/autofdo `f95d1a170dfe`) on six SPE legs of `official` on this host;
  - `bolt`: `llvm-bolt` 22.1.8 on `pgolto-relocs` with an SPE profile (`perf2bolt --spe`) from this host.
  The binaries and profiles are not published; their sha256 are in `bins.json` and in the data archive.
- Shapes `s`, `fh`, `fl` at 5,200 req/s, as track I.
- Method: Williams order of 7 arms, 14 rounds (two squares), 5 s client warm-up per leg; decision
  interval the wider of t and widened.
- The profiles of `order`, `autofdo` and `bolt` were recorded on the measured traffic (in sample); `pgolto`'s
  trainer is out of sample. SPE records one taken branch per sample and no fall-through ranges, so the `bolt`
  row is about that profile source, not about BOLT with a branch-history profile.

## Runs

| Config | Arms | Rounds |
|---|---|---|
| `arm-metal/spe-w6j-official.json` | `official`, `official-2` (SPE profiling legs through `perf-spe.sh`: the AutoFDO input) | 1 |
| `arm-metal/spe-w6j-relocs.json` | `pgolto-relocs`, `pgolto-relocs-2` (SPE legs: the BOLT input) | 1 |
| `arm-metal/w6j.json` | `official` (base), `official-A2`, `opt-file`, `order`, `pgolto`, `autofdo`, `bolt` | 14 |

`arm-metal/smoke-w6j.json` is one round of the A/B run, evidence frozen from it.

## Files

- `make.py` writes the configs; `run-w6j.sh`, `chain-w6j.sh` the sessions. With `SELF_SHUTDOWN=1` (opt-in,
  default off; needs passwordless sudo) the A/B chain powers the host off 20 minutes after it ends unless
  `~/w6j/KEEP` exists.
- `perf-spe.sh`: the perf wrapper of the SPE legs. `fp2order.py`: as in track I.
- `analysis/analyse_w6j.py RUN_DIR OUT_MD`: the table (file control, layout row, AutoFDO share of the PGO gain,
  BOLT) and the decision rules fixed before the run.
