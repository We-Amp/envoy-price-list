# Stats study: raw data

The per-run records behind the measurements of Envoy's stats subsystem: what a stats flush and a
sink cost the main thread, whether a flush delays requests, what the store stats cost on the request
path at 1 to 28 workers, shared against per-connection counters, the atomics microbenchmarks on x86
and Arm, and the Arm code-generation checks.

These records are not in the git repository. They are the assets of the release of tag
`stats-2026-11` of `https://github.com/We-Amp/envoy-price-list`, one archive per study
(`stats-2026-11-data-<study>.tar.gz`); this file is at the top of every archive. The data is licensed under CC BY 4.0 (`data/LICENSE` in the repository). From a clone of the
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

- `bench-x86_64`: the bare-metal server of the other data in the repository: two Intel Xeon E5-2673 v4
  sockets (2016; 20 cores and 40 threads each), clock fixed at 2.3 GHz, turbo off; 32 KiB L1d and
  256 KiB L2 per core, 50 MiB L3 per socket; Ubuntu 24.04, kernel 6.8. Every end-to-end run on x86 is
  from this machine. Client, origin and sinks are on loopback.
- `x86-vm`: an x86 cloud VM on Intel Xeon Platinum 8581C (Emerald Rapids, 2.3 GHz): 16 virtual CPUs,
  which are 8 cores with two threads each; one thread per core was used and the siblings left idle;
  48 KiB L1d and 2 MiB L2 per core, 260 MiB L3 as the guest reports it; spot, PMU on.
- `arm-vm`: an Arm cloud VM on Neoverse V2 cores: 16 virtual CPUs, one per core, no SMT; 64 KiB L1d
  and 2 MiB L2 per core, 80 MiB L3 as the guest reports it; clock about 3.0 GHz, not fixed; spot, PMU
  on.

The VM CPU models are not in any record of the runs (the benchmark output carries the core count
and cache sizes, not the model); they are stated here.

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

**Harness commit ids in the data are the measured ones.** Every `results.json` names the harness
commit it ran on (`metadata.harness`), and a few records and code comments quote other harness
commits. The published history of the harness is a cleaned copy of the history the runs used:
comments, record strings and commit messages that referred to unpublished documents were reworded, nothing
else. So the recorded ids are not in the repository. `docs/stats-data/harness-commit-map.md` in the
repository pairs every measured id with its published id and lists every string that differs. The
two Arm VM runs (`arm-codegen/`) record `0.1.0 (uncommitted)`: that VM ran the harness from an
archive of the commit measured as `62120c2`. Own builds of Envoy are named by measured commits in
the same way; `docs/stats-data/envoy-commit-map.md` maps those.

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
  2026-11-19 until 00:37 UTC on 2026-11-20 an unrelated periodic process logged in to the bench box
  about nine times a minute. Run L and the OTLP re-run ran entirely under it and
  passed every gate; they were not re-analysed. The first attempt at a higher load (1,800 req/s per
  worker, `multi-worker-high-load/stopped-1800/`, leg records only) was stopped after 8 of 15 legs at
  28 workers failed the "other tasks on the proxy's CPUs" gate; no gate was changed. Run U-hi at
  1,500 ran after that process was stopped. `analysis/tables.txt` of run U-hi tests the attribution and
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

From the repository root, after `python3 tools/fetch-stats-data.py`. The harness tables need Python
3.8 or later and nothing else.

```
D=data/stats; O=OUT_DIR     # a directory of your own, outside the repository
python3 examples/stats-flush/table.py $D/sink-flush-cost --json $O/tables.json > $O/tables.md
python3 examples/stats-flush/lat_table.py $D/flush-latency/lat --json $O/lat-table.json > $O/lat-table.md
python3 examples/stats-mt/u_table.py $D/multi-worker/u --hitm $D/multi-worker/u-hitm --json $O/u.json > $O/u.md
python3 examples/stats-mt/u_table.py $D/multi-worker-high-load/u-hi-1500 --json $O/u-hi.json > $O/u-hi.md
python3 examples/stats-mt/u_table.py $D/contention/dose-2 --evidence $D/contention/dose-evidence-2 \
    --json $O/dose-2.table.json > $O/dose-2.md
python3 examples/stats-mt/codegen_table.py $D/arm-codegen/arm-vm/codegen --json $O/codegen.json > $O/codegen.md
for m in microbenchmarks/bench-x86_64/micro microbenchmarks/x86-vm/micro microbenchmarks/arm-vm/micro-r5 \
         microbenchmarks/arm-vm-b/micro-r5b arm-lse-llsc/micro-lse; do
  mkdir -p $O/$m && python3 examples/stats-mt/micro.py table $D/$m --json $O/$m/table.json > $O/$m/micro.md
done
```

Run S's harness table was rendered from one session directory that also held runs M and W. To get
`sink-types/s-tables.md` byte for byte, give `table.py` such a directory (needs the archives
`sink-types` and `sink-flush-cost`):

```
mkdir session && ln -s "$PWD"/data/stats/sink-flush-cost/* session/
for r in s-100k s-1m sw; do ln -s "$PWD/data/stats/sink-types/$r" session/; done
python3 examples/stats-flush/table.py session > OUT_DIR/s-tables.md
```

The independent analyses (each prints what it reads; the directory arguments are the defaults).
`latency.py` also reads `sink-flush-cost/w`, and the run U-hi scripts also read `multi-worker`:

```
D=data/stats; O=OUT_DIR
A=examples/stats-flush/analysis-s          # run S
python3 $A/analyze.py $D/sink-types > $O/analysis.txt
python3 $A/extra.py   $D/sink-types > $O/extra.txt
python3 $A/holm9.py   $D/sink-types > $O/holm9.txt
python3 $A/latency.py $D/sink-types $D/sink-flush-cost/w > $O/latency.txt
python3 $A/rerun.py   $D/sink-types/s-1m-otlp-rerun > $O/rerun.txt

python3 examples/stats-flush/analysis-mfix/widened.py $D/sink-flush-cost/tables.json > $O/widened.txt   # run M-fix

A=examples/stats-flush/analysis-l          # run L; perleg.py first (it reads every probe log; a few minutes)
python3 $A/perleg.py $D/flush-latency/lat $O
python3 $A/analyze.py $D/flush-latency/lat $O > $O/analysis.txt
python3 $A/extra.py $D/flush-latency/lat $O > $O/extra.txt
python3 $A/review_fixes.py $D/flush-latency/lat $O > $O/review-fixes.txt

python3 examples/stats-mt/analysis-u/extras.py $D/multi-worker > $O/extras.txt       # run U

A=examples/stats-mt/analysis-u-hi          # run U-hi; writes tables.txt, results.json, review-checks.txt to $O
python3 $A/analyze.py $D/multi-worker-high-load $D/multi-worker $O
python3 $A/verify_review.py $D/multi-worker-high-load $D/multi-worker $O

A=examples/stats-mt/analysis-r1            # run R1
for s in cells aa_and_split levels_and_hot evidence; do python3 $A/$s.py $D/contention > $O/$s.txt; done

python3 examples/stats-mt/analysis-lse/analyse.py $D/arm-lse-llsc $O > $O/analysis.txt

# microbenchmarks: figures beside the tables (also reads multi-worker and arm-codegen for its last section)
python3 examples/stats-mt/analysis-micro/extras.py $D/microbenchmarks $D/multi-worker $D/arm-codegen > $O/extras.txt
python3 examples/stats-mt/analysis-codegen/extras.py $D/arm-codegen/arm-vm/codegen > $O/extras.txt   # Arm codegen run

M=$D/microbenchmarks                       # the post-hoc re-evaluation
python3 examples/stats-mt/micro_reeval.py $O/reeval \
    --data arm-vm-r5  $M/arm-vm/micro-r5    $M/arm-vm/micro.json.reconstructed \
    --data arm-vm-r5b $M/arm-vm-b/micro-r5b $M/arm-vm-b/micro-r5b/micro.json.used \
    --data x86-vm-r5  $M/x86-vm/micro       $M/x86-vm/micro.json
```

Each analysis output is in the archives under its study's `analysis/` directory (run U-hi's and run
L's use one `$O` per study). The scripts `analysis-s`, `analysis-l` and `analysis-u-hi` need numpy and
scipy in the versions of `examples/requirements-analysis.txt`; everything else needs only Python.

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
  afterwards (pooled cycles per operation), the data did not.
- `microbenchmarks/reeval/` was generated again from this tree with the current `micro.py`.
  `reeval.md` is identical to the one of 2026-11-19 except for its label line. The per-set tables
  under it (`reeval/*/micro.md`, `table.json`) are not: three hours after that first re-evaluation
  `micro.py` began to read the pooled cycles per operation from the benchmark's own field instead of
  recomputing it from the thread mean, and rows moved in the third digit (for example x86 VM, real
  counter shared by 4 threads, `fix-relaxed` against `fix`: `-0.13% [-8.75, +9.30]` then,
  `+0.67% [-7.75, +9.85]` now). The reported figures are the current ones. The earlier tables come
  back with the harness of the commit measured as `3666716`.
- `microbenchmarks-flush-overlap/*/micro.md` is rendered with `micro.py` of the commit measured as
  `c4f709b`, the runner of that round: look up its published id in
  `docs/stats-data/harness-commit-map.md`, then `git show <published id>:examples/stats-mt/micro.py`.
  Later revisions of `micro.py` do not tabulate these rows. For the x86 VM this reproduces the
  run-time table exactly.
- `microbenchmarks/analysis/extras.txt`, `sink-flush-cost/analysis/widened.txt` and
  `arm-codegen/arm-vm/analysis/extras.txt` come from scripts written for the publication. They print
  figures that had been worked out beside the tables: the histogram row in cycles per sample (the
  table has it in ns per sample), instructions per increment, the server's absolute cycles per
  operation with the estimator named, the x86 against Arm difference, the end-to-end model with its
  inputs, the own-build rows widened by the rung's own A/A, and the instructions removed per build
  on the Arm VM. One line was added to run L's `review-fixes.txt` (the total of the admin probes
  over the no-sink and statsd cells).

## Figures that are one step of arithmetic away from a printed value

Some figures in the write-ups are not printed by a command but follow from printed values:

| Figure | From |
|---|---|
| 6.79 and 6.96 us per statsd line, 211.0 and 2,159 ms per flush (the earlier session, run M) | `sink-flush-cost/tables.md`: the statsd flush minus the no-sink flush (for example 223.73 - 12.73 ms), divided by the lines per flush |
| about +20.1% against flush-off under load | `sink-types/analysis/analysis.txt`: the statsd row against no sink combined with the no-sink row against flush-off of `sink-flush-cost/tables.md` |
| 13.9% of the OTLP points rejected; 50,000 of about 360,000 | `sink-types/analysis/extra.txt`: 1 - 310,146 / 360,147 |
| the interval [2.54, 2.58] of 2.56 us per OTLP point | the interval of the ms per flush divided by 36,141 points |
| 0 of 19,157 | the sum of five printed counts in `flush-latency/analysis/` |
| 50,000 cluster histograms | 5 per cluster x 10,000 clusters (`sink-types/analysis/extra.txt` prints 50,012 histograms) |
| "from 2,100 requests per second per worker" | 58,800 over 28 workers in `multi-worker-high-load/stopped-1800/cal-hi-28w/` |

Three figures are in records the runs wrote and are not regenerated by a command: the pilot levels
617k, 694k and 545k (`contention/dose-pilot-2/summary.md`), the counted increments per request 14.03
to 14.04 (`arm-codegen/arm-vm/codegen-smoke.out`), and the count table of the arm64 atomics record
(`docs/stats-data/arm-atomics-bisect.md`, upstream binaries, no raw files).
