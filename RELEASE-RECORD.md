# Release record

A record of what official Envoy release binaries cost in CPU per request, measured with this harness under one
fixed protocol. The protocol is versioned; this file describes **record/1**. Each entry below names the
protocol version it was measured under and every place where it departed from it.

The post that quotes this record is the Releases section of "What Envoy settings and releases cost in CPU: a
measured price list". The data of every entry is under `data/release-record/<date>/`.

## Protocol record/1

### Binaries

- Only official release assets (`envoy-<version>-linux-x86_64` from the upstream GitHub release), never own
  builds. Each binary's sha256 is checked against the asset digest that the GitHub release publishes before it is
  used, and re-hashed when a session's run queue starts and when it ends.
- A release is named by its tag. The `--version` commit of every release measured so far is also its GNU build id.

### Static record (every tag, no measurement legs)

`examples/release-record/static.py` writes, per binary: size, sha256 and the digest it was checked against,
`--version`, GNU build id, section sizes (`.text`, `.rodata`, `.eh_frame`, the rest of the allocated sections,
and every section by name), the `.comment` strings (compiler and linker, when present), and whether a symbol
table or debug sections are present. It needs `readelf` and takes no box time beyond a few seconds per binary.

Tripwire: a patch release whose `.text` differs by more than 2% from the previous patch of its line joins the next
measured session as an arm. Otherwise patch releases get the static record only.

### Cells

Four fixed cells, the same in every session: two shapes, each at two load levels.

| Cell | Shape | Rate | About how busy (v1.40.2) |
|---|---|---|---|
| `s` | 4 KB proxied (an nginx origin serves the body) | 5,200 req/s | 31% |
| `s-hi` | the same | 12,000 req/s | 60% |
| `fh` | 128-byte direct response, 52 response headers added by the route (the route also lists 57 request headers, which a direct response never applies) | 8,000 req/s | 26% |
| `fh-hi` | the same | 18,400 req/s | 51% to 55% |

4 workers, HTTP/1.1 over loopback, no TLS, the client and origin settings of `examples/releases/make.py`. On the
two higher-rate cells the client raises its rate over its first second (at full rate from the start its connection
pool overflowed); from record/1 on these cells start their measurement window after a 3 s lead-in, so the ramp
ends before the window.

### Arms in every session

- **Anchor:** v1.40.2. Every other arm is compared with it (the **record rows**), and every row in this file is
  "v1.40.2 against the arm". The anchor moves forward one line only when its binary can no longer run the
  generated bootstrap, with one session that carries both the old and the new anchor.
- **A/A copy:** a second copy of the anchor (`v1.40.2-A2`) in the same rounds. A session whose A/A shows a
  Holm-significant difference, or a 95% half-width above 1%, in a cell reports that cell's reach next to its rows.
- **A new release line:** its first release (`.0`) and its newest patch at the time of the session, plus the
  newest patch of the line before it, whose row repeats a row of the previous session.

### Families and verdicts

- **Confirmatory rows** are named in the config (`confirmatory`) before the session runs. Holm runs over them
  alone.
- **Record rows** (every arm against the anchor, and the A/A) are the secondary family, with Holm over those rows.
- Everything else from the same paired rounds (steps between releases, other metrics) is **exploratory**:
  intervals only, no test.
- The primary metric is total cycles per request on the proxy (user plus kernel). Each paired round gives one log
  ratio; the figure is their mean with a 95% t interval. The **widened interval**, 1.96·√(SE² + 0.34²), adds the
  between-session A/A spread (0.34%, one standard deviation, from the pooled A/A runs in `data/aa-label-swap/`).
- An effect under 1% is not a finding, whatever its interval. A row **differs** only when its Holm p-value is at
  or under 0.05 and its widened interval excludes zero. Otherwise it is "not resolved" or "under 1%".
- Rows that change between sessions stay visible, with the session that changed them.

### Rounds and stop rule

Rotated balanced order, a new order seed per session. 16 rounds minimum, blocks of 16, cap 32. The session stops
after a block when every confirmatory row has a 95% half-width at or under 0.8% (`stop.rows = confirmatory`), or at
the cap. Shorter follow-up runs use fixed rounds.

### Validity

The harness gates, fail-closed, on every leg: rate at the proxy within 1% of target in the window, zero client
overflow, client headroom at least 25%, the proxy's CPUs and their siblings idle before and during the window,
worker share, zero non-2xx responses, every hardware counter running for the whole window (no multiplexing), the
idle-state configuration unchanged at start and end, and every generated bootstrap passing `--mode validate` on
every arm at run start. An invalid leg re-runs its round. Binaries' sha256 must be identical at queue start and end.

### When an entry is added

An entry is added when a new release is measured; there is no fixed schedule. A new release line's entry follows
"Arms in every session" above. Patch releases get the static record, and join a session only through the
tripwire.

### A change of machine (bridge rule)

Absolute cycles are never compared across machines, only ratios against the anchor. The first session on a
different machine (or kernel) is a **bridge**: it re-measures the releases from v1.37.0 on (v1.37.0, v1.37.11,
v1.38.0, v1.38.9, v1.39.6, v1.40.0, v1.40.2 and the A/A copy) against v1.40.2 before any new release, and its rows
are published next to the earlier machine's, not merged with them. Entries are therefore anchored on re-measured
releases.

## Entries

### 2026-11-16: first record/1 session (record/1, with the deviations listed)

Data: `data/release-record/2026-11-16/`. Configs: `examples/release-record/` (`make.py` writes them). One machine:
the bench machine of every other run in `data/` (bare-metal dual-socket Xeon E5-2673 v4, fixed 2.3 GHz, turbo off,
Ubuntu 24.04, kernel 6.8; Envoy on four cores of one socket with their hyperthread siblings idle, client and origin
on the other socket). This is the third release session on that machine; the first two are
`data/price-list-v2/pilot-v2/` (three releases, lower load) and `data/releases-backfill/` (six releases, both loads,
14 rounds). Rows for v1.32.13, v1.34.14 and v1.36.13 come from the second session; this session did not re-measure
them except in the counter run (Run C).

#### Named before the runs

- Confirmatory rows: total cycles per request, v1.38.0 against v1.37.11, one row per cell (four rows, Holm over
  four). Question: is the v1.37 to v1.38 step already in v1.38.0?
- Stop rule as in the protocol (0.8% on the confirmatory rows, 16/16/32).
- Exploratory steps from the same rounds: the first against the newest patch of three lines (v1.37.0 to v1.37.11, v1.38.0 to
  v1.38.9, v1.40.0 to v1.40.2); v1.38.9 to v1.39.6 to v1.40.0; v1.38.9 against v1.37.11 (a repeat of the second
  session's step with a new seed).
- Run B (the v1.38 patches one by one) only if v1.38.0 reads like v1.37.11 while v1.38.9 is dearer.

The confirmatory field and the stop rule are in `experiment.json` of `run-a/`, and in `results.json` as run.

#### Binaries

| Tag | Published | Bytes | sha256 (first 12) | `--version` commit | Runs |
|---|---|---|---|---|---|
| v1.32.13 | 2025-10-13 | 82,648,456 | 27150dfd35c8 | 0c686a2237 | C |
| v1.37.0 | 2026-01-13 | 90,394,544 | 0a5729ee4e98 | 6d9bb7d9a8 | A |
| v1.37.11 | 2026-10-26 | 90,539,824 | b9ebeed3ba6f | 0ce6eee982 | A, C |
| v1.38.0 | 2026-04-23 | 101,688,536 | cca312a7c3f9 | f1dd21b16c | A, B |
| v1.38.2 | 2026-06-10 | 102,013,080 | 87744a1fc998 | f387231af8 | B |
| v1.38.5 | 2026-10-01 | 102,051,288 | 28a22586738e | 4be7862a2a | B |
| v1.38.7 | 2026-10-12 | 102,133,208 | 10be648a3d1a | 9b5f29d242 | B |
| v1.38.9 | 2026-10-26 | 102,125,016 | 3c70be6f1c57 | 17e2784039 | A, B, C |
| v1.39.6 | 2026-10-27 | 105,105,368 | 116ef1d0d4e0 | aacd034021 | A |
| v1.40.0 | 2026-10-13 | 106,905,560 | 8aa137a7d009 | 9e55809337 | A |
| v1.40.2 | 2026-10-27 | 106,860,504 | 1d64506e25c1 | b2d89e0ae5 | A (anchor and A/A copy), C |

All digests matched; the sha256 of every binary was the same at the start and end of both run queues
(`sha256-start.txt` = `sha256-end.txt`, `sha256-start-2.txt` = `sha256-end-2.txt`).

#### Static record (`static.json`, 13 tags)

| Tag | MB | `.text` MB | `.rodata` MB | `.eh_frame` MB | `.text` against the row above | `.comment` |
|---|---|---|---|---|---|---|
| v1.32.13 | 82.6 | 52.23 | 7.22 | 8.29 | | clang 14.0.0, LLD 14.0.0, GCC 11.4.0 objects |
| v1.34.14 | 83.6 | 53.04 | 7.27 | 7.95 | +1.6% | clang 18.1.8, LLD 18.1.8, GCC 11.4.0 |
| v1.36.13 | 86.5 | 55.20 | 7.48 | 8.18 | +4.1% | clang 18.1.8, LLD 18.1.8, GCC 13.1.0 |
| v1.37.0 | 90.4 | 57.78 | 7.85 | 8.51 | +4.7% | none |
| v1.37.11 | 90.5 | 57.91 | 7.86 | 8.51 | +0.2% | none |
| v1.38.0 | 101.7 | 64.94 | 9.09 | 9.47 | +12.1% | none |
| v1.38.2 | 102.0 | 65.19 | 9.10 | 9.49 | +0.4% | none |
| v1.38.5 | 102.1 | 65.21 | 9.11 | 9.50 | +0.0% | none |
| v1.38.7 | 102.1 | 65.30 | 9.11 | 9.50 | +0.1% | none |
| v1.38.9 | 102.1 | 65.30 | 9.10 | 9.50 | +0.0% | none |
| v1.39.6 | 105.1 | 67.37 | 9.28 | 9.74 | +3.2% | none |
| v1.40.0 | 106.9 | 68.17 | 9.69 | 9.87 | +1.2% | none |
| v1.40.2 | 106.9 | 68.17 | 9.69 | 9.87 | −0.0% | none |

- v1.37.11 to v1.38.0 adds 11.15 MB: `.text` +7.03 MB, `.rodata` +1.24, `.eh_frame` +0.95, `.gcc_except_table`
  +0.58, `.rela.dyn` +0.63, `.data.rel.ro` +0.33, and `.bss` −1.32 MB. The v1.38 patches after it add 0.44 MB.
- From v1.37.0 on the binaries have no `.comment` section and no other compiler string, so a compiler change
  between lines can be neither shown nor excluded from the binaries. No release has a symbol table or debug
  sections, so no profile by symbol was taken.
- Tripwire: `.text` moved by more than 2% only at line boundaries, never inside a patch line (largest inside a
  line: v1.38.0 to v1.38.2, +0.39%).

#### Runs and validity

| Run | Arms | Cells | Rounds | Legs (valid) | Window (UTC) |
|---|---|---|---|---|---|
| A: record and locate | v1.37.0, v1.37.11, v1.38.0, v1.38.9, v1.39.6, v1.40.0, v1.40.2, v1.40.2-A2 | all four | 32 (stop rule) | 1,024 (1,024) | 2026-11-16 08:17:47 to 19:13:34 |
| C: hardware counters (exploratory) | v1.32.13, v1.37.11, v1.38.9, v1.40.2 | `s-hi`, `fh-hi` | 24 fixed | 192 (192) | 2026-11-16 20:23:41 to 22:26:44 |
| B: v1.38 patches one by one (exploratory) | v1.38.0, v1.38.2, v1.38.5, v1.38.7, v1.38.9 | `s-hi`, `fh-hi` | 20 fixed | 200 (200) | 2026-11-16 22:26:44 to 2026-11-17 00:34:52 |

No invalid legs, no re-runs, no gate overridden. In Run A the rate at the proxy in the window was within +0.01% to
+0.02% of target on all four cells, with zero client overflow and client headroom at least 0.64. Every counter ran
for the whole window on every leg. Order seed 7 (the second session used 4).

Stop rule: after 16 rounds the widest confirmatory half-width was 0.93% (`fh-hi`), so Run A ran its second block;
after 32 it was 0.66% (`s-hi`), and the run stopped there, at the cap.

#### Deviations from the protocol and from the plan

- **Runs B and C carried no A/A arm.** Their reach is taken from Run A's A/A in the same cells. Both are
  exploratory.
- **Run B ran at the higher load only** (the cells were fixed in the plan), where the proxied step it was meant to
  locate was smallest: v1.38.9 against v1.37.11 at `s-hi` was +1.0% in Run A, against +1.8% at `s`.
- **Run C counts cycles differently.** To free a programmable counter it counts total cycles with one `cycles`
  event (user plus kernel together) instead of `cycles:u` and `cycles:k`. Its per-arm cycle levels sit about 0.5%
  below Run A's for the same arms; no leg measured both ways. Its ratios between arms are internally consistent.
- **Run C's counter groups are balanced over the whole run, not within each group.** The event list rotates over
  three groups by round, and every arm of a round counts the same group, so pairs compare like with like; each arm
  sits in each position equally often over the 24 rounds, but within one group's 8 rounds the positions are not
  balanced. This can tilt the per-group event ratios slightly; it does not affect cycles or instructions, which
  every group counts.
- **Lead-in.** The two higher-rate cells used a 3 s lead-in instead of the 2 s of the second session, so the
  client's ramp ended before the window (the second session served 0.3% fewer requests than the target there).
- **Run A ran 32 rounds**, not the 16 the plan expected, because the stop rule needed the second block. Runs C and B
  then ran from a second run queue started the same evening; the first queue's attempt to start Run C failed at
  once because its harness copy lacked the Run C config (`queue-1.log`), before any leg.

#### Results

The A/A of the session (v1.40.2-A2 against v1.40.2, Holm over 28):

| Cell | Total cycles [95% CI] | Half-width | Holm p |
|---|---|---|---|
| `s` @ 5,200 | −0.01% [−0.40, +0.37] | 0.38 | 1.0 |
| `fh` @ 8,000 | −0.13% [−0.80, +0.55] | 0.68 | 1.0 |
| `s-hi` @ 12,000 | +0.01% [−0.45, +0.47] | 0.46 | 1.0 |
| `fh-hi` @ 18,400 | −0.07% [−0.63, +0.50] | 0.57 | 1.0 |

All four cells pass the A/A limits.

Confirmatory rows, v1.38.0 against v1.37.11 (Holm over 4):

| Cell | Total cycles [95% CI] | Widened | Holm p | Rounds v1.38.0 dearer | Verdict |
|---|---|---|---|---|---|
| `s` @ 5,200 | +0.87% [+0.46, +1.28] | [+0.10, +1.66] | 0.00027 | 25/32 | under 1% |
| `fh` @ 8,000 | +1.38% [+0.77, +2.00] | [+0.49, +2.29] | 0.00020 | 26/32 | differs |
| `s-hi` @ 12,000 | +0.17% [−0.50, +0.83] | [−0.75, +1.09] | 0.61 | 20/32 | under 1% |
| `fh-hi` @ 18,400 | +2.50% [+1.89, +3.12] | [+1.61, +3.41] | 6.1e-9 | 30/32 | differs |

On the header-heavy direct response the step is in v1.38.0. Its size is less firm than the +2.5% suggests: at the
higher load v1.38.9 is only +1.2% over v1.37.11 in the same run, because the v1.38 patches read −1.3% there, and Run
B did not repeat that patch-line reading. On 4 KB proxied requests v1.38.0 stays under 1% against v1.37.11.
User-space instructions per request rise 3.8% (proxied) and 6.9% (header-heavy) with v1.38.0; the v1.38 patches add
under 0.1%.

Record rows, v1.40.2 against each arm (Holm over 28; negative means v1.40.2 is cheaper), lower load / higher load:

| v1.40.2 against | Header-heavy direct response | 4 KB proxied |
|---|---|---|
| v1.37.0 | −2.9% [−3.5, −2.3] / −2.7% [−3.3, −2.1] | +1.5% [+1.0, +1.9] / +1.6% [+1.0, +2.2] |
| v1.37.11 | −3.4% [−4.0, −2.8] / −2.5% [−3.1, −1.9] | +1.4% [+1.0, +1.8] / under 1% (+0.8%) |
| v1.38.0 | −4.7% [−5.3, −4.2] / −4.9% [−5.4, −4.4] | under 1% / under 1% |
| v1.38.9 | −4.3% [−4.9, −3.7] / −3.7% [−4.2, −3.2] | under 1% / under 1% |
| v1.39.6 | −6.0% [−6.6, −5.4] / −5.9% [−6.5, −5.4] | under 1% / under 1% |
| v1.40.0 | under 1% / under 1% | under 1% / under 1% |

Every "differs" row has a Holm p-value under 0.001 and a widened interval that excludes zero (`tables-a.md`).

Changed against the second session (same binaries, new seed): header-heavy v1.37.11 at the lower load moved from
−2.7% to −3.4% and header-heavy v1.38.9 at the higher load from −4.5% to −3.7%, the two largest moves; proxied v1.37.11 at the lower load moved from +1.2% (not resolved) to +1.4%
(differs). The v1.37.11 and v1.38.9 rows agree between the sessions in all eight cells within the between-session
spread (|z| ≤ 1.2 with the spread counted for each session, ≤ 1.4 counted once).

Exploratory, from the same rounds:

- **v1.38.9 against v1.37.11** (the second session's step, repeated): +1.80% / +0.91% / +0.99% / +1.21% (`s`, `fh`,
  `s-hi`, `fh-hi`), every widened interval excluding zero; the second session read +1.06% / +1.57% / +1.47% /
  +2.05%. Same sign in all four cells in both sessions; the sizes differ by up to 0.8 points (|z| ≤ 1.4 with the
  spread counted for each session, ≤ 1.7 counted once). About 1% to 2%.
- **First against newest patch**: v1.37.0 to v1.37.11 and v1.40.0 to v1.40.2 are under 1% in every cell. v1.38.0 to
  v1.38.9 reads +0.92% / −0.47% / +0.82% / −1.27%; the header-heavy −1.27% at the higher load did not repeat in Run B
  (+0.13%).
- **v1.38.9 to v1.39.6 to v1.40.0**: on the header-heavy shape v1.39.6 is 1.8% and 2.4% dearer than v1.38.9, and
  v1.40.0 is 5.9% and 5.8% cheaper than v1.39.6, with 19% fewer user-space instructions. On proxied requests
  instructions fall 4.3% with v1.39 and 2.3% with v1.40, while cycles stay under 1% at both steps.

Run B, the v1.38 patches one by one (`tables-b.md`; total cycles, `s-hi` / `fh-hi`):

| Step | 4 KB proxied | Header-heavy |
|---|---|---|
| v1.38.0 to v1.38.2 | +0.29% [−0.14, +0.73] | +0.34% [−0.27, +0.97] |
| v1.38.2 to v1.38.5 | +0.16% [−0.39, +0.72] | −1.24% [−1.94, −0.55], widened [−2.17, −0.31] |
| v1.38.5 to v1.38.7 | +0.49% [−0.16, +1.13] | +0.93% [+0.24, +1.62], widened [−0.00, +1.87] |
| v1.38.7 to v1.38.9 | −0.19% [−1.00, +0.62] | +0.11% [−0.53, +0.76] |
| v1.38.0 to v1.38.9 | +0.75% [+0.18, +1.33] (Run A +0.82%) | +0.13% [−0.37, +0.63] (Run A −1.27%) |

User-space instructions moved by at most 0.11% between any two v1.38 patches. One header-heavy step
(v1.38.2 to v1.38.5, −1.2%) read clearly in this run, and the next patch reversed it; no proxied step reached 1%.
The proxied cost drifts up through the patch line by about 0.8%, the same in both runs and under the 1% floor. The
published binaries therefore place the proxied part of the v1.37.11 to v1.38.9 rise no finer than "between those
two releases": v1.38.0 against v1.37.11, and each patch against the one before, stayed under 1%.

Run C, hardware counters (`tables-c.md`; exploratory). The perf event list rotates over three groups by round,
8 rounds each, never multiplexed: (1) `uops_issued.any`, `uops_retired.retire_slots`, `idq_uops_not_delivered.core`,
`int_misc.recovery_cycles`; (2) `icache.misses`, `itlb_misses.walk_completed`, `itlb_misses.walk_duration`,
`dsb2mite_switches.penalty_cycles`; (3) `br_misp_retired.all_branches`, `mem_load_uops_retired.l1_miss`,
`mem_load_uops_retired.l3_miss`, `dtlb_load_misses.walk_duration`. Every group also counts `instructions:u` and
`cycles`, so cycles and instructions rest on all 24 rounds and the events on 8. `tables-c.md` derives top-down
level-1 shares per thread (slots = 4 × cycles, the SMT sibling idle); read those as paired differences between
releases, not as absolute bottleneck figures, because kernel time is inside the counted slots.

- v1.37.11 to v1.38.9: cycles +1.24% [+0.78, +1.70] (proxied) and +1.61% [+1.09, +2.14] (header-heavy), the
  third session with the same sign for this step. Hardware counters on this processor did not single out a cause
  of the v1.38 step: retired uops rose with the instructions, and no top-down share moved with the cycle gap on
  both shapes.
- v1.32.13 to v1.40.2 on proxied requests at 12,000 req/s: cycles +2.03% [+1.56, +2.50], widened [+1.22, +2.84],
  24 rounds. The second session's record row for the same cell is +1.3%, not resolved after Holm. This is a
  further, exploratory reading of that cell; the post gives both.

## Using the record

```bash
python3 examples/release-record/make.py               # writes the configs
python3 -I examples/release-record/static.py static.json ~/epl/bin/envoy-1.40.2:v1.40.2:<sha256> ...
python3 bin/epl run examples/release-record/run-a.json --out ~/epl/runs/release-record/run-a
python3 bin/epl run examples/release-record/run-c.json --out ~/epl/runs/release-record/run-c
python3 bin/epl run examples/release-record/run-b.json --out ~/epl/runs/release-record/run-b
python3 examples/release-record/table.py a ~/epl/runs/release-record/run-a --json tables-a.json > tables-a.md
python3 examples/release-record/table.py c ~/epl/runs/release-record/run-c --json tables-c.json > tables-c.md
python3 examples/release-record/table.py b ~/epl/runs/release-record/run-b --json tables-b.json > tables-b.md
```

The configs carry the paths, CPU sets and rates of the bench machine; treat them as templates. The tables in
`data/release-record/2026-11-16/` are reproduced byte for byte by `table.py` from the run directories there.
