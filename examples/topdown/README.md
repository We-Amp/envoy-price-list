# Top-down counter study (track A)

Where the cycles of Envoy v1.40.2 go on three request shapes, in Intel top-down (TMA) terms, for the
official release binary against an instrumented-PGO + ThinLTO build. The counters decide which
code-layout follow-ups are worth building (wave 2, [`examples/wave2`](../wave2) and
[`tools/code-layout`](../../tools/code-layout)), and the LBR legs recorded here are the profile
input of the `order` and `autofdo` arms there.

## Conditions

- A two-socket Broadwell Xeon E5-2673 v4 bench box (2 x 20 cores), bare metal, 2.3 GHz fixed,
  turbo off, SMT on with the SMT siblings of the SUT CPUs left idle; kernel 6.8, perf 6.8.
- CPUs (the configs' `cpus`): Envoy on 0-3 (4 workers, exact connection balance, HTTP/1),
  client on 20-31,60-71, origin on 32-39,72-79.
- Client: Nighthawk, open loop, 16 workers x 32 connections, 5 s warm-up, 25 s duration; the
  harness counts a 20 s window after a 2 s lead-in. Origin: `nginx:alpine` (pinned digest) in
  Docker, 8 workers. Idle gate: load1 at most 8, other CPU use at most 2%.
- CPU vulnerability mitigations: the box's `/sys/devices/system/cpu/vulnerabilities/*` state
  (stock kernel defaults, PTI on) is a run condition, because mitigations change cycle counts;
  `chain.sh` records it, and the data archive has it as `topdown/vulnerabilities.txt`.
- Arms:
  - `stock`: the official `envoy-1.40.2-linux-x86_64` release asset (sha256 `1d64506e…f03cc`),
    at `~/epl/bin/envoy-1.40.2`.
  - `pgolto`: an own build with instrumented PGO + ThinLTO (source commit `24a950b647`), pinned by
    md5 `3e5ee6b301d01089d013fd45cc2f7f5b`, at `~/epl/bins/pgolto/envoy-pgolto-prodalloc`.

## Shapes

| Shape | Kind | Request | Rate |
|---|---|---|---|
| `s` | proxied | `/s`, a 4 KB body from the origin | 5,200 rps |
| `fh` | direct response | `/fh`, 128 B body, 57 request headers and 52 response headers added | 8,000 rps |
| `fl` | route table | `/fl`: the `fh` header sets on a proxied route to the origin's `/s` (4 KB) | 5,200 rps |

## Runs

- `topdown-a.json`: the counter census. 24 rounds (blocks of 6, arm order chosen by the harness,
  seed 21). Every leg counts one of **8 event groups, rotated by round**: round r counts group
  `(r - 1) % 8 + 1`, on every arm and shape, so each group gets 3 rounds. Each group holds the two
  fixed counters (`instructions:u`, `cycles` or `cycles:u`) plus at most four programmable ones
  (`cycles:k` counts as one):
  G1 TMA level 1 user + kernel; G2 TMA level 1 user; G3 fetch latency, recovery cycles, branch
  mispredicts; G4 machine clears, microcode uops, branch resteers; G5 iTLB walks and i-cache stall
  cycles; G6 DSB vs MITE uops, i-cache misses; G7 L1d replacements, L2 and LLC misses; G8 memory,
  store-buffer and total stall cycles. The exact event lists are in `make.py`.
- `lbr-a.json`: one smoke round (fixed order, 2 arms x 3 shapes = 6 legs) whose perf command is
  `perf-lbr.sh`: for the harness's window it runs `perf record -b -g` on the Envoy PID for the same
  20 s, with two sampling events: `br_inst_retired.near_taken` (PEBS, every 100,003 taken
  branches; the AutoFDO / ordering input) and `cycles:u` (every 1,000,003 cycles; inclusive
  attribution). Data goes to `lbr-data/lbr-<pid>.data` with a `manifest.txt`.

`make.py` writes both configs (`python3 examples/topdown/make.py`; `--perf` sets the perf binary of
`topdown-a`, `--lbr-wrapper` where `perf-lbr.sh` is installed for `lbr-a`, default
`~/epl/runs/topdown-a/perf-lbr.sh`).

## How to run

On the bench box, from a harness checkout, once the box is idle:

```
nohup examples/topdown/chain.sh > /dev/null 2>&1 &
```

`chain.sh` refuses to start above load1 1.0, records the box state (governor and frequency limits of
`CHECK_CPUS`, `no_turbo`, perf settings, THP, kernel, perf version, CPU vulnerabilities, the perf
event list, sha256 and md5 of both binaries), installs `perf-lbr.sh` into the run directory, then runs
`topdown-a` (into `td/`) and `lbr-a` (into `lbr/`). Variables: `TD_DIR` (default
`~/epl/runs/topdown-a`, the configs' workdir), `PERF` (default `perf`), `CHECK_CPUS`, `STOCK_BIN`,
`PGOLTO_BIN`. Progress in `chain.log`, the two exit codes in `chain.rc`.

## How to analyse

```
python3 -I examples/topdown/analyse.py ~/epl/runs/topdown-a/td tables.md   # also writes tables.json
python3 -I examples/topdown/lbr-post.py [--perf PERF] ~/epl/runs/topdown-a/lbr-data \
    ~/epl/runs/topdown-a/lbr lbr-summary.json
```

`analyse.py` normalises every counter per response and prints, per shape, the per-round values and
means of TMA level 1 and level 2 pieces, IPC, iTLB, i-cache, DSB/MITE, branch, cache and stall
metrics, then the follow-up verdicts (rules in its docstring), the `cycles_total` ratio of the two
arms and the leg health. `lbr-post.py` (run on the box, when nothing is measured) summarises each
LBR leg: samples per event, whether the branch stacks decode, the top leaf symbols, and the share of
`cycles:u` samples spent in the upstream filter-manager machinery (rules in its docstring).
