# Stats study: raw data

The per-run records behind the measurements of Envoy's stats subsystem: what a stats flush and a
sink cost the main thread, whether a flush delays requests, what the store stats cost on the request
path at 1 to 28 workers, shared against per-connection counters, the atomics microbenchmarks on x86
and Arm, and the Arm code-generation checks.

These records are not in the git repository. They are the assets of the release of tag
`stats-2026-11` of `https://github.com/We-Amp/envoy-price-list`, one archive per study
(`stats-2026-11-data-<study>.tar.gz`); this file is at the top of every archive. From a clone of the
repository,

```
python3 tools/fetch-stats-data.py              # every study, about 320 MB unpacked
python3 tools/fetch-stats-data.py contention   # or the studies you name
```

downloads them, checks each archive and every file against the checksums kept in git
(`data/stats-data.SHA256SUMS`, `data/stats-data.manifest`) and unpacks them into `data/stats/`. Every
path below is relative to that directory, and every command assumes it is filled. Each archive
unpacks on its own; a few commands read two studies and say so.

How to run each study, which Envoy binary or patch it needs and how the tables are rendered:
`docs/stats-study.md` in the repository. The configs are under `examples/stats-flush/` and
`examples/stats-mt/`. What was changed in the raw records before publication, and what was left
out: `WHAT-WAS-CHANGED.md` beside this file. The small rendered tables are also in the repository
under `docs/stats-tables/`, at the same relative paths.

## Machines

- `bench-x86_64`: the bare-metal server of the other data in the repository (dual-socket Intel Xeon
  E5-2673 v4, 2 x 20 cores, fixed 2.3 GHz, turbo off, Ubuntu 24.04, kernel 6.8). Every end-to-end run
  on x86 is from this machine. Client, origin and sinks are on loopback.
- `x86-vm`: a current x86 cloud VM, 8 cores used with one thread per core, spot, PMU on.
- `arm-vm`: a current Arm server core in a cloud VM, 16 vCPU = 16 cores, no SMT, spot, PMU on.

Absolute times, cycles and rates are not comparable across machines. Only ratios and differences
within one machine are.

## Directories

| Directory (= archive) | Study | Harness commit of the run | Envoy | Tables in the directory |
|---|---|---|---|---|
| `sink-flush-cost/` | Runs M and W: main-thread cost per flush at 10k to 1M stats, with and without the statsd sink (`m-10k` ... `m-1m`), and the same under load (`w`). Run M-fix: two own builds (`mfix-*`) | `72e9f5d` | official v1.40.2; M-fix: `main` at `5e1439980a` against the sink stack at `3c9cce2f2c` | `tables.md`, `tables.json` |
| `sink-types/` | Run S: statsd, buffered dog_statsd and OTLP against no sink at 100k and 1M stats (`s-100k`, `s-1m`) and under load (`sw`); the OTLP re-run at 1M (`s-1m-otlp-rerun`) | `bf0f8a9`; re-run `6136250` | official v1.40.2 | `s-tables.md`, `s-tables.json` (harness); `analysis/` (the independent analysis the reported figures come from) |
| `flush-latency/` | Run L: request latency inside and outside a flush, main thread on its own core and on a worker's core (`lat`) | `e33b9be` | official v1.40.2 | `lat-table.md`, `lat-table.json` (harness); `analysis/` (reported figures) |
| `multi-worker/` | Run U: the store stats removed (`reject_all`) against the default, 1,000 req/s per worker, at 1, 4, 14 and 28 workers (`u`); HITM evidence legs (`u-hitm`) | `9858ffc` | official v1.40.2 | `u.md`, `u.json`; `analysis/extras.txt` (figures quoted beside the table) |
| `multi-worker-high-load/` | Run U-hi: the same at 1,500 req/s per worker, 14 and 28 workers (`u-hi-1500`) | `6136250` | official v1.40.2 | `u-hi.md`, `u-hi.json` (harness); `analysis/` (reported figures) |
| `contention/` | Run R1 ("dose"): K counters per request from the stats access logger, shared by all workers against one set per connection (`dose-2`), its evidence legs (`dose-evidence-2`) and pilot (`dose-pilot-2`) | `0764feb`; pilot `9e63292` | official v1.40.2 | `dose-2.md`, `dose-2.table.json`; `analysis/` (the checks of the numbers review) |
| `microbenchmarks/` | Round 5: atomic model, counter, gauge and histogram benchmarks on the three machines (`bench-x86_64/`, `x86-vm/`, `arm-vm/`, `arm-vm-b/`), and the post-hoc re-evaluation of the stored outputs (`reeval/`) | `852e127`, `2de6b98` | own builds `d2f2238974`, `e74e595e3c`, `f8bd66d7e7` | `micro.md`, `table.json` per set; `reeval/reeval.md` |
| `microbenchmarks-flush-overlap/` | Round 4, exploratory: a flush while workers update stats (`flush_contended`), x86 VM and Arm VM | `c4f709b` | own builds of round 4 (six arms) | `micro.md` |
| `arm-lse-llsc/` | One benchmark source built twice for arm64, LSE against LL/SC atomics | `bf0f8a9` | own build `964d72f7a6`, two flag sets (`build-record.txt`) | `analysis/`; `micro-lse/micro.md` |
| `arm-codegen/` | The official release against the `main` dev image on the Arm VM, end to end at 4 and 12 workers | archive of `62120c2` | release v1.40.2 (arm64) and the dev image of `5e1439980a` | `arm-vm/codegen.md`, `codegen.json` |

The record of when the arm64 builds of `main` changed their atomics has no raw files; it is in the
repository as `docs/stats-data/arm-atomics-bisect.md`.

Every `results.json` names the harness commit it ran on (`metadata.harness`); all of them are in the
repository's history. The Arm VM ran the harness from an archive, so its records say
`0.1.0 (uncommitted)`.

## Conditions that belong to the data

A reader who recomputes from `legs.jsonl` needs these, or gets figures the tables do not print.

- **Run S, OTLP at 1M stats.** The eight OTLP legs of `s-1m` are marked valid by the harness and are
  not valid: the collector rejected about 14% of the points of every flush (its 4 MiB gRPC receive
  limit). They are in no table and no test family. The OTLP price at 1M comes from
  `s-1m-otlp-rerun` (collector limit 64 MiB, delivery checked per leg). `analysis/extra.txt` and
  `analysis/rerun.txt` show the evidence.
- **Run S, receive buffer.** `net.core.rmem_max` was raised for the session and every sink leg was
  granted a 512 MiB receive buffer. Sinks and the collector are local discard receivers on loopback
  (the collector with a `nop` exporter), so the prices include the local receive path.
- **Run S, A/A.** The 2% A/A half-width target is missed at 100k (2.28%) and at 1M at 5 s (2.64%);
  the affected rows carry an interval widened by the rung's own A/A.
- **Runs L, U-hi, the OTLP re-run: a condition found after the runs.** From about 14:15 UTC on
  2026-11-19 until 00:37 UTC on 2026-11-20 an unrelated monitoring loop on another machine logged in
  to the bench box about nine times a minute. Run L and the OTLP re-run ran entirely under it and
  passed every gate; they were not re-analysed. The first attempt at a higher load (1,800 req/s per
  worker, `multi-worker-high-load/stopped-1800/`, leg records only) was stopped after 8 of 15 legs at
  28 workers failed the "other tasks on the proxy's CPUs" gate; no gate was changed. Run U-hi at
  1,500 ran after the loop was stopped. `analysis/tables.txt` of run U-hi tests the attribution and
  finds it is not the whole explanation.
- **Run L.** Three `shared/statsd` legs fail the exact request-count gate by one or two requests and
  stay invalid; their rounds were run again. The run has 4 complete rounds, not the planned 5 (the
  hard stop was moved from 3,900 s to 5,100 s during the session; at the planned stop it would have
  had 2). The harness's own `summary.md` counts blocks of five and says "0 complete rounds".
- **Run U.** The 1-worker rung fails its A/A (half-width 3.19%), so the planned growth test has no
  verdict; the A/A is just over the 1% limit at 4 workers (1.24%) and 28 workers (1.02%). Two legs
  are invalid (SMT siblings busy) and their blocks were run again.
- **Run U-hi.** The A/A gate fails in the two 14-worker cells; those rows have no verdict.
- **Run R1.** A short run: 6 rounds instead of 15. 106 leg records: 78 current, 28 superseded by
  re-run rounds; 8 legs invalid. The chain of the second attempt stopped after its smoke and the
  timed run was started without a second smoke (`chain-dose-3.sh`, `chain-dose-3.log`). The A/A is
  one-sided in all three cells (the second copy is lower), as large as the effects, so no cell has a
  formal verdict. The K = 64 row of cell A is printed with "5 valid rounds" and uses 6.
- **Microbenchmarks.** On the Arm VM most real-stat processes at 12 and 15 threads were rejected by
  the runner as run (`r*.json.tmp` is the output of a rejected process). `reeval/` re-evaluates the
  stored outputs under later gates without new runs: post hoc, tuned on the data it judges, and
  labelled so in every file. The Arm real-stat rows at 1 and 4 threads are descriptive.
- **Arm LSE against LL/SC.** The involuntary-switch bound of the smoke was changed after a first
  smoke failed it (both smokes are here); at the run's 1 s window both rules give the same bound.
- **Arm codegen.** The 4-worker row's A/A fails; that row has no verdict.

## Rendering the tables again

From the repository root, after `python3 tools/fetch-stats-data.py`. The harness tables need Python 3.8 or later and nothing else; the scripts
in the `analysis-*` directories also need `numpy` and `scipy`.

```
D=data/stats
python3 examples/stats-flush/table.py $D/sink-flush-cost --json tables.json > tables.md
python3 examples/stats-flush/lat_table.py $D/flush-latency/lat --json lat-table.json > lat-table.md
python3 examples/stats-mt/u_table.py $D/multi-worker/u --hitm $D/multi-worker/u-hitm --json u.json > u.md
python3 examples/stats-mt/u_table.py $D/multi-worker-high-load/u-hi-1500 --json u-hi.json > u-hi.md
python3 examples/stats-mt/u_table.py $D/contention/dose-2 --evidence $D/contention/dose-evidence-2 \
    --json dose-2.table.json > dose-2.md
python3 examples/stats-mt/codegen_table.py $D/arm-codegen/arm-vm/codegen --json codegen.json > codegen.md
python3 examples/stats-mt/micro.py table $D/microbenchmarks/x86-vm/micro --json table.json > micro.md
```

Run S's harness table was rendered from one session directory that also held runs M and W. To get
`sink-types/s-tables.md` byte for byte, give `table.py` such a directory (needs the archives
`sink-types` and `sink-flush-cost`):

```
mkdir session && ln -s "$PWD"/data/stats/sink-flush-cost/* session/
for r in s-100k s-1m sw; do ln -s "$PWD/data/stats/sink-types/$r" session/; done
python3 examples/stats-flush/table.py session > s-tables.md
```

The independent analyses (each prints what it reads; the directory arguments are the defaults).
`latency.py` also reads `sink-flush-cost/w`, and the run U-hi scripts also read `multi-worker`:

```
A=examples/stats-flush/analysis-s          # run S
python3 $A/analyze.py $D/sink-types > analysis.txt
python3 $A/extra.py   $D/sink-types > extra.txt
python3 $A/holm9.py   $D/sink-types > holm9.txt
python3 $A/latency.py $D/sink-types $D/sink-flush-cost/w > latency.txt
python3 $A/rerun.py   $D/sink-types/s-1m-otlp-rerun > rerun.txt

A=examples/stats-flush/analysis-l          # run L; perleg.py first (it reads every probe log; a few minutes)
python3 $A/perleg.py $D/flush-latency/lat OUT_DIR
python3 $A/analyze.py $D/flush-latency/lat OUT_DIR > analysis.txt
python3 $A/extra.py $D/flush-latency/lat OUT_DIR > extra.txt
python3 $A/review_fixes.py $D/flush-latency/lat OUT_DIR > review-fixes.txt

python3 examples/stats-mt/analysis-u/extras.py $D/multi-worker > extras.txt       # run U

A=examples/stats-mt/analysis-u-hi          # run U-hi; writes tables.txt, results.json, review-checks.txt
python3 $A/analyze.py $D/multi-worker-high-load $D/multi-worker OUT_DIR
python3 $A/verify_review.py $D/multi-worker-high-load $D/multi-worker OUT_DIR

A=examples/stats-mt/analysis-r1            # run R1
for s in cells aa_and_split levels_and_hot evidence; do python3 $A/$s.py $D/contention > $s.txt; done

python3 examples/stats-mt/analysis-lse/analyse.py $D/arm-lse-llsc OUT_DIR > analysis.txt

M=$D/microbenchmarks                       # the post-hoc re-evaluation
python3 examples/stats-mt/micro_reeval.py OUT_DIR \
    --data arm-vm-r5  $M/arm-vm/micro-r5    $M/arm-vm/micro.json.reconstructed \
    --data arm-vm-r5b $M/arm-vm-b/micro-r5b $M/arm-vm-b/micro-r5b/micro.json.used \
    --data x86-vm-r5  $M/x86-vm/micro       $M/x86-vm/micro.json
```

After rendering, `python3 tools/fetch-stats-data.py --verify` compares every file with the manifest
again: a table that renders differently shows up there.

What was checked when the archives were built, with the harness at the commit that added the manifest:

- `sink-flush-cost/tables.md`, `sink-types/s-tables.md`, `multi-worker/u.md`, `contention/dose-2.md`
  and `dose-2.table.json`, `arm-codegen/arm-vm/codegen.md`: rendered again from this tree, identical
  to the tables rendered when the runs were analysed.
- The `analysis/` outputs of runs S, L and U-hi and of the LSE experiment: produced again from this
  tree, identical to the reviewed outputs except for directory names in three label lines and the
  home-directory prefix in one line that prints executable paths.
- `multi-worker/analysis/extras.txt` comes from a script written for the publication
  (`examples/stats-mt/analysis-u/extras.py`): the shares, instruction counts, differences between
  rungs and HITM totals that were computed by hand beside run U's table. It reproduces them.
- `microbenchmarks/*/micro.md` is rendered with the current `micro.py`. Where the runner also wrote
  a table at run time it is kept as `micro.as-run.md`: the layout and the headline measure changed
  afterwards (pooled cycles per operation), the data did not. `microbenchmarks/reeval/` was
  generated again from this tree; `reeval.md` is identical to the reviewed one except for its label
  line.
- `microbenchmarks-flush-overlap/*/micro.md` is rendered with `micro.py` of commit `c4f709b`, the
  runner of that round (`git show c4f709b:examples/stats-mt/micro.py`). Later revisions of
  `micro.py` do not tabulate these rows. For the x86 VM this reproduces the run-time table exactly.
