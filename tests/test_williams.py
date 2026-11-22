"""Williams order (balanced first-order carryover) and unscored warm-up legs."""
import json
import os
import tempfile
import unittest
from collections import Counter

from epl import experiment
from epl.sim import SimBackend

from tests.test_experiment import cfg, load


def arms(k):
    return [{"name": "a%d" % i, "binary": "/bin/true"} for i in range(k)]


class WilliamsSequenceTest(unittest.TestCase):
    def check(self, k, seed):
        period = k if k % 2 == 0 else 2 * k
        rows = [experiment.williams_sequence(k, r, seed) for r in range(1, period + 1)]
        for row in rows:
            self.assertEqual(sorted(row), list(range(k)))
        pos = Counter((a, i) for row in rows for i, a in enumerate(row))
        per = period // k
        self.assertTrue(all(pos[(a, i)] == per for a in range(k) for i in range(k)), pos)
        follow = Counter((row[i], row[i + 1]) for row in rows for i in range(k - 1))
        want = 1 if k % 2 == 0 else 2
        self.assertTrue(all(follow[(x, y)] == want for x in range(k) for y in range(k) if x != y), follow)
        # the next period repeats the first
        self.assertEqual(experiment.williams_sequence(k, period + 1, seed), rows[0])

    def test_even_counts_balance_in_k_rounds(self):
        for k in (2, 4, 6, 8):
            for seed in (1, 52, 7):
                self.check(k, seed)

    def test_odd_counts_balance_in_2k_rounds(self):
        for k in (3, 5, 7):
            self.check(k, 52)

    def test_seed_permutes_arms(self):
        self.assertNotEqual(experiment.williams_sequence(6, 1, 1), experiment.williams_sequence(6, 1, 2))


class WilliamsConfigTest(unittest.TestCase):
    def test_validate_period(self):
        tmp = tempfile.mkdtemp()
        ok = load(cfg(arms=arms(6), base_arm="a0", order="williams", rounds=6, rounds_max=6, rounds_block=6), tmp)
        self.assertEqual(experiment.validate(ok, allow_short=True), [])
        bad = load(cfg(arms=arms(6), base_arm="a0", order="williams", rounds=4, rounds_max=4, rounds_block=4), tmp)
        self.assertTrue(any("multiple of 6" in e for e in experiment.validate(bad, allow_short=True)))
        odd = load(cfg(arms=arms(5), base_arm="a0", order="williams", rounds=10, rounds_max=10, rounds_block=10), tmp)
        self.assertEqual(experiment.validate(odd, allow_short=True), [])

    def test_round_order_uses_williams(self):
        tmp = tempfile.mkdtemp()
        exp = load(cfg(arms=arms(6), base_arm="a0", order="williams", order_seed=3, rounds=6), tmp)
        for r in range(1, 7):
            self.assertEqual([a["name"] for a in experiment.round_order(exp, r)],
                             ["a%d" % i for i in experiment.williams_sequence(6, r, 3)])

    def test_warmup_legs_value(self):
        tmp = tempfile.mkdtemp()
        bad = load(cfg(warmup_legs=2), tmp)
        self.assertTrue(any("warmup_legs" in e for e in experiment.validate(bad, allow_short=True)))


class WarmupDryRunTest(unittest.TestCase):
    def test_warmup_legs_are_recorded_and_never_scored(self):
        tmp = tempfile.mkdtemp()
        c = cfg(arms=arms(6), base_arm="a0", order="williams", rounds=6, rounds_max=6, rounds_block=6,
                adaptive=False, warmup_legs=1, shape_order="latin")
        exp = load(c, tmp)
        self.assertEqual(experiment.validate(exp, allow_short=True), [])
        res = experiment.Runner(exp, os.path.join(tmp, "run"), SimBackend).run(simulate=True)
        with open(os.path.join(tmp, "run", "legs.jsonl")) as f:
            legs = [json.loads(x) for x in f if '"leg_id"' in x]
        warm = [m for m in legs if m.get("warmup")]
        scored = [m for m in legs if not m.get("warmup")]
        self.assertEqual(len(warm), 6 * 2)  # one per round and shape
        self.assertEqual(len(scored), 6 * 2 * 6)
        self.assertTrue(all(m["arm"] == "a0" and m["superseded"] for m in warm))
        # each warm-up leg comes right before its shape block
        order = [(m["round"], m["shape"], bool(m.get("warmup"))) for m in legs]
        for i, (r, s, w) in enumerate(order):
            if w:
                self.assertEqual(order[i + 1][:2], (r, s))
                self.assertFalse(order[i + 1][2])
        an = res["analysis"] if "analysis" in res else res
        for sh in ("s", "fh"):
            a0 = an["shapes"][sh]["arms"]["a0"]
            self.assertEqual(a0["legs"], 6)
            self.assertEqual(a0["warmup"], 6)
            self.assertEqual(a0["superseded"], 0)
            comp = an["shapes"][sh]["comparisons"][0]
            self.assertEqual(comp["cycles_total"]["n"], 6)


if __name__ == "__main__":
    unittest.main()
