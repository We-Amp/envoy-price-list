# Harness history: measured commits and published commits

The runs of the stats study record the harness commit they ran on: `metadata.harness` in every
`results.json`, the same string in `summary.md`, and `harness` in the microbenchmarks' `meta.json`. A few
code comments, configs and commit messages quote harness commits too. All of these are ids of the history
as it was when the runs were made ("measured commits").

That history is not published. What is published, as the history of this repository above the commit
`94528e6` (the previous public `main`), is a copy of it with reworded text ("published commits"). This file
maps one to the other and states exactly how they differ. Nothing at or before `94528e6` was changed.

## What differs between a measured and a published commit

1. **Text inside files.** Comments, docstrings, log messages and record strings in the configs referred to
   documents that are not published. They were replaced by wording
   that states the rule or the fact itself, and one paragraph of the README that cited upstream issues and
   pull requests in reference syntax was rewritten with the numbers as plain words: 46 fixed strings, the same replacement wherever a string
   occurs. One test class was renamed and one test fixture string changed with them. No code path,
   setting, rate, gate, schedule or measured number differs; the numbers of plan revisions inside the
   replaced strings went with the words. The published wording of every replaced string is listed at
   the end of this file.
2. **Commit messages.** 16 of the 68 inherited messages had words of the same kind replaced (for example
   "Micro gates, second revision: ..." for a subject that referred to such a document). Subject and body are otherwise the
   same.
3. **Commit ids.** A commit's id covers its files, its message and its parents, so every commit from the
   first changed one onwards has a new id.

What does not differ: the set of files and their modes in every commit, the order and structure of the
commits (68 commits before, 68 after, the same parents), authors, committers and all dates.

Because the measured commits are not published, a reader cannot repeat the comparison. We made it before
publishing, for every pair in the table: the author and committer lines are equal; the two trees have the same
paths; every file that differs equals the measured file with the listed replacements applied and has the same
number of lines; and the message equals the measured message with its replacements applied. For a sample of
pairs (the commits of runs M, L, U, U-hi, R1, S and of the two microbenchmark rounds) the table and analysis
commands were run with the harness of both commits on the published data: the outputs are identical, and the
offline tests give the same counts. The post-hoc re-evaluation prints its label line, which is one of the
replaced strings, and differs in that line only.

## How to use the map

- A `results.json` says `"harness": "0.x 9858ffc3b5d8 stats-mt"`: look up `9858ffc3b5d8` in the first column;
  the second column is the commit to check out.
- The two Arm VM runs say `0.1.0 (uncommitted)`: that VM ran the harness from an archive of the commit
  measured as `62120c2`.
- A code comment, a config note or a commit message in this repository that quotes a harness commit quotes
  the measured id. Branch names in the records (`stats-sink`, `stats-lat`, `stats-mt`) are the names of the
  three lines of work that the merges of this history join.

## Commits that the data records

| Measured commit | Published commit | Recorded by |
|---|---|---|
| `3cca8b432f9d` | `76a64d750dd6219efba15644d509de0edac7748d` | sink-flush-cost |
| `4ebb37a1072c` | `246731d8c119e867cb7655860d97547d76ca0c93` | sink-flush-cost |
| `72e9f5d38f72` | `19aeffb578e4f4a64b0dc4fe8fcad5e6705a552e` | sink-flush-cost |
| `9858ffc3b5d8` | `1726bc3922f98c039aa5c7e5b400135ac0e431fd` | multi-worker |
| `c4f709b14413` | `1b05a3df6061d5fd298b12ef88311c1bca06a5b7` | microbenchmarks-flush-overlap (its tables are rendered with this commit's `micro.py`) |
| `62120c2e4907` | `bf3fe07c4e93df812b9a79d7ceb4a49a84dfb398` | arm-codegen (run from an archive of this commit; recorded as `0.1.0 (uncommitted)`) |
| `3666716ede64` | `1d3376edfa7986ad7a228390d6d239a2f5699cca` | microbenchmarks (the first post-hoc re-evaluation) |
| `bf0f8a99d531` | `3756f72b9f42af114290da333204e65bd2e45eea` | sink-types |
| `e33b9be53dd4` | `c7593b818988b6bce901cf81caef6778aa0762aa` | flush-latency |
| `6136250229d7` | `c39a665c1b02461abecd0416a3c23fee053941a1` | multi-worker-high-load, sink-types |
| `9e6329225b2b` | `bc6c743b64f8b47028882cd656b6d71d141dc6c4` | contention |
| `0764feb1894a` | `b9b1c9e233754e7f5b6a308c986ec98c880cd3bc` | contention |

## Every commit of the inherited history

Oldest first. Two commits have the same id on both sides: nothing in them or before them was reworded.

| Measured commit | Published commit | Subject (published) |
|---|---|---|
| `ab7902078961` | `ab7902078961d10ef4bd46dfba1960a8e776818e` | Stats row: idle legs, the cluster generator, flush and sink settings, discard sink |
| `2726cf3b9a9b` | `2726cf3b9a9be9dc43872d10c6d4869491b203b0` | Stats row tests: bursts, UDP counters, /stats text, generator, sinks, idle gates, sink process |
| `eed25838218f` | `e69f32a8e738d556d67bc3ea337b2c20a6429587` | Stats row: per-box configs, calibration, profile, portability check, session and tables |
| `479fa623dd5c` | `ef7debf7138b992125cf466d018a7c9215fc8146` | Stats row: whole-flush sink counts between quiescent points, flush count by visibility |
| `a5cb0e88cfed` | `4b490a28e6816bd6be2c219dd1bc664e4f2642ea` | Stats row session: 5 s fallback smoke, per-rung calibration, guard edges, W flush evidence, tables |
| `8928f5dcb970` | `121bb4a2f8ca5642f8034a921c3836010debee61` | Stats row: run M-fix, the run-M design with two own builds (base and fix) |
| `3cca8b432f9d` | `76a64d750dd6219efba15644d509de0edac7748d` | Stats row: flush counts from the measured timer, saturated main thread |
| `44494f22e139` | `9f0870382a65b53ba6326816fdf39b29143c85f6` | Stats row: statsd lines per whole flush within 1% of the used count (a flush sends a few lines more) |
| `4ebb37a1072c` | `246731d8c119e867cb7655860d97547d76ca0c93` | Stats row: run W records the fd limit and the generated clusters' connect failures; cold N from the cold smoke |
| `d58b63d437f5` | `1592cde30e9af15ea2674b62ef321248fe9c355e` | Stats table: the derived share of a core is d / interval, capped at 1 |
| `72e9f5d38f72` | `19aeffb578e4f4a64b0dc4fe8fcad5e6705a552e` | Stats row: W's used-only read fails closed on a non-200; tables print the 1 s saturation observation; M-fix rows labelled as own builds |
| `1a70d989981d` | `96717d0605f9630cef63ba1ff3643c3463f5a252` | Rungs for the multi-threaded stats study: main thread pinned before config load, workers moved to their set |
| `b753d3c96058` | `8c28ed19ce10364b9ce88dfcd34931e9ca509e1d` | Multi-threaded stats study: run U configs per machine, microbenchmark runner, tables |
| `8673fb411424` | `572804b82bf2d2975192727fddc48f3316212ad9` | Run U review fixes: time base, origin count, worker coverage, reject evidence, 15 rounds; micro checks |
| `4b63598ffc78` | `ad172fa23fa397d3926eb5a77e6ad000f3722445` | Run U: soft fd limit for the harness's own Envoy and client; 16 connections per worker by default |
| `9858ffc3b5d8` | `1726bc3922f98c039aa5c7e5b400135ac0e431fd` | Run U: every rung's client ramps over the first second, window 3 s in (start-up overflow at 28 workers) |
| `8453b1dd0d04` | `2b7770687caa2b31058edd7806ebf7d3e3ccbce8` | Micro runner: pinned sha256 identity, passed thread and hammer counts, coverage; VM boxes |
| `c4f709b14413` | `1b05a3df6061d5fd298b12ef88311c1bca06a5b7` | Micro: pin the x86 round-4 binaries (bench box and x86 VM) from the build record |
| `fe1a1545deee` | `8a2bad3e670bff7c2843e1827a4080db105dbb47` | Micro runner for the time-bounded benchmarks and the narrowed set |
| `36aff7efc32c` | `6de983b1653d7b554df5ca5a29bac556c5060d38` | Micro: final arm SHAs after the benchmark fixup; the Arm VM's binary directory |
| `7f6a0416065c` | `773f4fbdc34f5593ac71ba498b4f05b9871d5bce` | Micro gates, first revision: rate floor, absolute overlap, 0.2 s smoke, per-binary smoke |
| `e1c0b8fec59b` | `229ecd704479d60406089e7b586e12873580f846` | Micro: round-5 arms (fix d2f2238974, fix-relaxed e74e595e3c, fix-relaxed-p1 f8bd66d7e7); pin the x86 binaries |
| `af8887da739a` | `64aa60dc953934e1b0ea50d38f1a8d86cc8792c9` | Tests: the bench box pins only the model build |
| `09e9fa6e1416` | `f31b2e879c2d13a910de1849a6c761c604c26f80` | Micro: bare-metal involuntary-switch bound max(5, 25/s x window), frozen from the bench-box smoke; switches per repetition recorded |
| `2de6b9839417` | `76affdbe77263812f89ffd56d9065e1b3c9b49d9` | Micro: involuntary-switch bound per thread (max(5, 25/s x window) x threads); the counter is summed over the threads |
| `852e12779e33` | `c0f9e864044d53d3fb43321845291985b5156e4d` | Micro: Arm VM top count 12; the smoke always includes each box's top count; pin the arm64 round-5b binaries |
| `ffe6b9c38a70` | `abeff0680781cf2f6426c293654e7a920aadb070` | Micro: the involuntary-switch bound's values (5 per thread, 25/s) in every box config |
| `c0e3b5b0b971` | `6ec591ab1166219635a9efe818517e99e6f4da81` | Tests: the flat-bound gate test sets no switch rate |
| `50e8e1ad368c` | `eead27ac54310e124f6a4fde011a7d200a86e7d0` | arm64 atomics codegen run: official release against the main dev-image build |
| `62120c2e4907` | `bf3fe07c4e93df812b9a79d7ceb4a49a84dfb398` | Codegen run review fixes: atomics premise checked, absolute contrast, stat-op parity, smoke gate |
| `2297a60eb734` | `44f77c800e32d645e5d660fcf08344e83aba3cac` | Micro gates, second revision: overlap allowance in batches, 1,024 floor, pooled headline, 8-thread rung |
| `3666716ede64` | `1d3376edfa7986ad7a228390d6d239a2f5699cca` | Micro: POST-HOC re-evaluation of stored outputs under the current gates (micro_reeval.py) |
| `525db1b9103a` | `89aa6e6b206d1a0a8a375e87c45d5dedb5115065` | Stats row: whole-flush counting between quiescent points for dog_statsd and OTLP |
| `c2c0509d6ac5` | `66c5e2143fed63925a726c283e87a2f0eea03324` | Run S: the sinks at 100k and 1M with an A/A, and under load |
| `d47e32103f3a` | `9322bcfb98816ac37e292bfcd75ada27b72761d0` | Micro: LSE against LL/SC builds of the same benchmark on the Arm VM |
| `ca00ee537565` | `1c134cfeccc9afd624a8dd4db5e47ecebfe810d5` | Run U at high load on the bench box: top rungs at a calibrated per-worker rate |
| `f77030cfebc8` | `fc47f6050722000227653f19641ab3ee6f27696f` | Run S review fixes: per-flush prices from the span, same-interval references, OTLP read tolerance |
| `dafc82ff3db6` | `7b564e58a1f3b7fafebb70432e46f974f2597394` | High-load run U review fixes: its own contrasts, queue only after a clean smoke |
| `d54517f4a81e` | `72bec9c4bb8bd36203daeb912c1ace510a5d6d44` | Run S: 3.5 h stop with a time estimate, all-valid smoke required, A/A at 5 s at 1M |
| `bf0f8a99d531` | `3756f72b9f42af114290da333204e65bd2e45eea` | Run S: OTLP points per flush on the basis the flush exports |
| `34ea2a6f9d51` | `669a4b850dfccc55ff89dce9f5c533bb1d6b4f62` | Run S: OTLP receive limit raised, one basis again, Envoy-side export evidence (replaces bf0f8a9's fit) |
| `15add64ed1bd` | `6cdde0aaf727eeab02ccf78ae42480b0d4e79e32` | Run S OTLP fix, review follow-up: own span start, first 1M smoke kept, exact request count, A/A in the re-run |
| `b2b295f3f19e` | `226e0c4930809944be760d37db5669ba99390560` | Run S: the 1M smoke also smokes nosink-20s-A2, the re-run's A/A arm (s-1m keeps its arm set) |
| `4459e8b4df36` | `081d86f62416795c463fd57cc74fe24e45424860` | Tests: plain form of the s-1m arm-set check |
| `b47220c1e2ba` | `fa1756c828a80d1b7c3a89eed1987e31b8fba8dc` | Run L: open-loop latency probe, thread series, one CPU per worker, cells |
| `39c73ff6c8fa` | `47e9462600e0b552b55432c3921d0f5307c4e12e` | Run L: configs, lat-smoke / lat-check / lat-queue, the table, tests |
| `b585a741d571` | `598bba5b50a3a760b00397a43c0189ca4fc2f293` | Run L review fixes: exact request count gate, smoke bound to its check, timer lines from the leg's counters |
| `0403d01b45d5` | `97fd7805b7554be38a74902cf5bd08d105dfb159` | Run L: the OTLP cluster fix of run S ported (6136250), budget 70 min, stop 85 min |
| `e33b9be53dd4` | `c7593b818988b6bce901cf81caef6778aa0762aa` | Run L: the pin check after the window uses the one-CPU-per-worker rule too |
| `3d4ce5d1d203` | `9885f9e1d7700919563680e669f2e25f58ef6983` | High-load run U: one rates key per attempt (u_hi.rates_key, 1,500 next; the stopped 1,800 attempt recorded) and HI_TAG run directories |
| `6136250229d7` | `c39a665c1b02461abecd0416a3c23fee053941a1` | Run S OTLP evidence: the collector cluster's HTTP/2 stats may appear after the pre-window read |
| `4fa3da70cacf` | `a4a90d6e06012e1257fadbef6faa32f09d6a6b75` | High-load run U: the second 1,800 attempt under its own rates key (bench-x86_64-hi-1800, HI_TAG=-1800); the 1,500 attempt's key recorded |
| `72972aaf36c0` | `be6879196c23d85d8fa7f93c327090145f69fbdd` | Setting stats_access_log: the stats access logger on the HCM (K counters, one tag from a command operator) |
| `0d889c05ebf2` | `707f27f842c659e339ece72c9da26548d147bfff` | Leg: stat count by prefix before and after the window, one extra stat in the window snapshots |
| `4dcac86bcf12` | `da768a735d565f7c496df5b178942689dd5a63c0` | Run R1 (dose) on the bench box: shared against per-connection counters, pilot, smoke, run and evidence configs |
| `047df8644a5a` | `11868255b0c98b8cb29da8928aea4dfd540445a8` | u_table: run R1 (dose) statements S1-S5 and the model row; HITM events under either spelling |
| `27d3bfb88dc3` | `d0aedc2e722b8dd28f13816897ec16c78d620bcc` | Run R1 (dose): dose-pilot, dose-smoke, dose-check and dose-queue; the pilot's answers printed |
| `ad581602913f` | `8a2174b494b5484feff1762e94bd4cef1e61ddf0` | Arms that run in some shapes only (`shapes` on an arm) |
| `0e7939cbcd79` | `07c19e1b5aab07e42336b736eeea74ac5c08e5b0` | Run R1 (dose): cells A, B and 28 workers, a second dose in cell A, statements S1-S6, no flush during a leg |
| `c30d1d10a73f` | `4abf78e7617ba9d8347a0416dd8834534c12cd21` | Harness: listener_address as an arm setting, config evidence `where`, seconds per leg, no leg inside a daily UTC window |
| `76496ba853ca` | `2eb2a627e04aa6d21b3133724c1dfefb884f8433` | u_table, run R1 (dose): five statements, no verdict on a failed A/A, invalid comparisons, 12 valid rounds, the model's price |
| `bba256c80c18` | `ddb0f2b48cf776e9743f49800636e59ff9c00061` | Run R1 (dose): wildcard listener, connections per worker from the pilot, the pilot record the queue checks |
| `e9be08abb109` | `38502c22f9d6096d4164da99cfaf6459f6e875fb` | Order fixed: the arms as listed, every round (a smoke or pilot only) |
| `9e6329225b2b` | `bc6c743b64f8b47028882cd656b6d71d141dc6c4` | Run R1 (dose) pilot, attempt 2: the deciding legs first, never cut short by invalid legs, 8 connections as the alternative, cell C at 2,200 |
| `5541d571a99d` | `0a9d9ab0573afc2c559c29406dc161df7f765a47` | Run R1 (dose): a dose per cell, the decision record, probe-based model row, footprint band |
| `01074121a05f` | `63041ca712b9db5411514ba941fb05714228bc58` | Harness: rotation_block for a run shorter than its full rotation; stats_access_log hot (one counter, K entries) |
| `0764feb1894a` | `b9b1c9e233754e7f5b6a308c986ec98c880cd3bc` | Run R1 (dose): a short run of 6 rounds, one round of evidence legs, an exploratory hot-counter pair in cell A |
| `3532a2aefb72` | `819dab651c6ee73ed967228ad067251bdd7e1329` | u_table, run R1 (dose): six rendering fixes from the re-review (no config or schedule change) |

## The published wording of the replaced strings

Each line is the text that now stands where a replaced string stood, with the number of files of the
published tip that carry it. A string that no longer occurs at the tip was replaced in older commits only.
An empty replacement means the reference was removed and the sentence around it kept.

| Published wording | Files at the tip |
|---|---|
| `(as statsd # by the saturation rule)` | 1 |
| `# about 8 rounds on the unloaded S rungs;` | 1 |
| `overrides only that, a decision the operator records)` | 1 |
| `mandatory part above 2 h 30 min: decide before the queue (FORCE=1 starts it)` | 1 |
| `FORCE=1 given, starting` | 3 |
| `mandatory %.2f h (a decision is needed above %.2f h);` | 1 |
| `# the 60 s window stays;` | 1 |
| `above %.0f min: over budget (cut order:` | 1 |
| `# observation, not a result: the plain statsd` | 1 |
| `decision record stands in` | 1 |
| `{"decision": what decided (a dated note),` | 1 |
| `"""Why a decision record does not` | 1 |
| `#                                     decision record (` | 1 |
| `the microbenchmarks (time-bounded windows, narrowed set):` | 1 |
| `run R1 ("dose"):` | 1 |
| `# Microbenchmark arms: the` | 1 |
| `row 2b: the shared` | 1 |
| `# gates, first revision: the operations floor` | 1 |
| `# second revision: the overlap allowance` | 1 |
| boxes with a `dose` section): | 1 |
| `of the same benchmark source` | 1 |
| `where the box sets a rate (max(5, 25/s x window) on every box)` | 6 |
| `batches of the slowest thread (the second revision of the gates: a thread` | 1 |
| `Rationale: the benchmark` | 1 |
| `under the second revision of the gates (no new runs)` | 1 |
| `# limit 70 min: legs` | 1 |
| `# the rule's values on every box` | 1 |
| `1, 2 and 6 passed, and the decision record.` | 1 |
| `"revision 3 of the run's plan (2026-11-20)"` | 1 |
| `rule of 2026-11-18: per thread max(5, 25/s x window)` | 15 |
| `summed over the threads; rule: per thread` | 14 |
| `8 invalid; kept as a failed attempt` | 14 |
| `short run: 6 rounds instead of 15` | 14 |
| `the choice was made by hand and is in the decision record: 16 connections` | 14 |
| `run R1 (dose), a short run:` | 14 |
| `run R1 (dose):` | 0 |
| `Short run: 6 rounds, and the exploratory pair` | 1 |
| `class ConfigEvidenceHarnessTest` | 1 |
| `limit 62 min: legs` | 0 |
| `(bare metal: max(` | 0 |
| (a clause removed, nothing put in its place) | - |
| the README paragraph on the work this builds on, quoted in full in `README.md` | 0 |
