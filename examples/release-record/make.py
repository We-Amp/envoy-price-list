#!/usr/bin/env python3
"""Write the configs of release record/1, first session (one-off closing run).

    python3 examples/release-record/make.py

  run-a.json     record + locate: v1.37.0, v1.37.11, v1.38.0, v1.38.9, v1.39.6, v1.40.0,
                 v1.40.2 and a second copy of v1.40.2 (`v1.40.2-A2`, the A/A of the
                 session), four cells (4 KB proxied and the header-heavy direct response,
                 each at two rates). Rotated order, order seed 7, 16 rounds minimum, blocks
                 of 16, cap 32. Confirmatory rows, named before the run: v1.38.0 against
                 v1.37.11 in each cell, Holm across those four; the run stops when their
                 95% half-width is at or under 0.8%. Every arm is also compared with
                 v1.40.2 (the record rows, Holm across those 28).
  run-c.json     counters (exploratory): v1.32.13, v1.37.11, v1.38.9, v1.40.2 on the two
                 higher-rate cells, 24 fixed rounds; the perf event list rotates by round
                 over three groups (top-down level 1, front end, back end and speculation),
                 each with instructions:u and total cycles, never multiplexed.
  run-b.json     patch bisection (only if run A places the step inside the v1.38 patch
                 line): v1.38.0, .2, .5, .7, .9 on the two higher-rate cells, 20 fixed rounds.
  smoke-1.json, smoke-2.json   two rounds of the four new binaries on all four cells
  smoke-c.json   four rounds of the counter groups on one cell (every group once, one twice)

Same base, client, CPUs and generated bootstrap as the release back-fill
(examples/releases/make.py). Change against it, disclosed: a 3 s lead-in on the ramped
shapes (the end of the client's 1 s ramp fell inside the window there).
"""

import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("rel_make", os.path.join(HERE, "..", "releases", "make.py"))
rel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rel)

RUNS = "~/epl/runs/release-record"
DIGESTS = {
    "1.32.13": "27150dfd35c89b69e5db38366bca4025f30311416d83ea5f5b83cabc76613265",
    "1.37.0": "0a5729ee4e980d346ebcee80f18e7efe5232b91141bb4c776ec3adcca786e60c",
    "1.37.11": "b9ebeed3ba6febcc0943810bddc27f66807ceaf9b1538d3e6db14284fbcb1ce8",
    "1.38.0": "cca312a7c3f91852f2849995c895130c59842e21ba787dc90bafa4026d6c5ecc",
    "1.38.2": "87744a1fc998d677078c9703113a192d0830badc6888662441632847fcb38899",
    "1.38.5": "28a22586738e591bd15d072a346704c581b4783cb59eea8a83118e75da44f485",
    "1.38.7": "10be648a3d1a82c8c60bc3ce6fc53793ac12f95853fff9fda4b49c28d6e35929",
    "1.38.9": "3c70be6f1c5704c1d78e034828a9ef9501fbd7b6ea7992c75b62f6b13846dcb4",
    "1.39.6": "116ef1d0d4e0685bbb0749134aa84ebd6d56a37c568ce6418f1242138d9d10cf",
    "1.40.0": "8aa137a7d00994ce43f613556f5a120709229f63bedb86eedde5ccbc402c2b80",
    "1.40.2": "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc",
}
ANCHOR = "v1.40.2"
AA_ARM = "v1.40.2-A2"
RAMPED_LEAD_IN_S = 3
ORDER_SEED = 7
SW = "task-clock,context-switches,cpu-migrations"
# Broadwell, SMT on: 4 programmable counters per thread. instructions:u and cycles (user +
# kernel) sit on fixed counters, so each group's four events fit without multiplexing.
COUNTER_GROUPS = [
    "instructions:u,cycles,uops_issued.any,uops_retired.retire_slots,idq_uops_not_delivered.core,"
    "int_misc.recovery_cycles," + SW,
    "instructions:u,cycles,icache.misses,itlb_misses.walk_completed,itlb_misses.walk_duration,"
    "dsb2mite_switches.penalty_cycles," + SW,
    "instructions:u,cycles,br_misp_retired.all_branches,mem_load_uops_retired.l1_miss,"
    "mem_load_uops_retired.l3_miss,dtlb_load_misses.walk_duration," + SW,
]


def arm(v, name=None):
    return rel.arm(v, DIGESTS[v], name)


def shapes():
    S = rel.shapes({})
    for k in ("s-hi", "fh-hi"):
        S[k] = dict(S[k], lead_in_s=RAMPED_LEAD_IN_S)
    return S


def configs():
    S = shapes()
    base = json.loads(json.dumps(rel.sm.BASE))
    base.pop("floor_from")
    four = [S[k] for k in ("s", "fh", "s-hi", "fh-hi")]
    hi = [S["s-hi"], S["fh-hi"]]
    a_arms = [arm(v) for v in ("1.37.0", "1.37.11", "1.38.0", "1.38.9", "1.39.6", "1.40.0", "1.40.2")] \
        + [arm("1.40.2", AA_ARM)]
    run_a = dict(base, workdir=RUNS, name="release-record-a", base_arm=ANCHOR, arms=a_arms, shapes=four,
                 confirmatory=[["v1.38.0", "v1.37.11"]],
                 rounds=16, rounds_block=16, rounds_max=32, order_seed=ORDER_SEED,
                 stop={"target_half_width_pct": 0.8, "rows": "confirmatory"})
    run_c = dict(base, workdir=RUNS, name="release-record-c", base_arm=ANCHOR,
                 arms=[arm(v) for v in ("1.32.13", "1.37.11", "1.38.9", "1.40.2")], shapes=hi,
                 measure=dict(base["measure"], perf_event_groups=COUNTER_GROUPS),
                 rounds=24, rounds_block=24, rounds_max=24, adaptive=False, order_seed=ORDER_SEED)
    run_b = dict(base, workdir=RUNS, name="release-record-b", base_arm="v1.38.0",
                 arms=[arm(v) for v in ("1.38.0", "1.38.2", "1.38.5", "1.38.7", "1.38.9")], shapes=hi,
                 rounds=20, rounds_block=20, rounds_max=20, adaptive=False, order_seed=ORDER_SEED)
    smoke = lambda n, a, b: dict(base, workdir=RUNS, name=n, base_arm="v" + b,  # noqa: E731
                                 arms=[arm(a), arm(b)], shapes=four,
                                 rounds=2, rounds_block=2, rounds_max=2, adaptive=False)
    smoke_c = dict(base, workdir=RUNS, name="release-record-smoke-c", base_arm=ANCHOR,
                   arms=[arm("1.37.11"), arm("1.40.2")], shapes=[S["s-hi"]],
                   measure=dict(base["measure"], perf_event_groups=COUNTER_GROUPS),
                   rounds=4, rounds_block=4, rounds_max=4, adaptive=False)
    return {"run-a.json": run_a, "run-c.json": run_c, "run-b.json": run_b,
            "smoke-1.json": smoke("release-record-smoke-1", "1.37.0", "1.38.0"),
            "smoke-2.json": smoke("release-record-smoke-2", "1.39.6", "1.40.0"),
            "smoke-c.json": smoke_c}


def main():
    for fn, c in configs().items():
        with open(os.path.join(HERE, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
