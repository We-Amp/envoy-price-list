"""Arms that list the shapes they run on (`shapes` on an arm) have two schedules, one per study:
cells (flush latency) and per shape (contention). Both must keep the schedule their runs used."""
import json
import os
import unittest

from epl import experiment

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAT = os.path.join(HERE, "examples", "stats-flush", "bench-x86_64", "lat.json")
DOSE = os.path.join(HERE, "examples", "stats-mt", "bench-x86_64", "dose.json")
U = os.path.join(HERE, "examples", "stats-mt", "bench-x86_64", "u.json")


def raw(path):
    with open(path) as f:
        return json.load(f)


class ArmShapesModeTest(unittest.TestCase):
    def test_neither_study_names_the_mode(self):
        # the configs the runs used are unchanged: the mode follows from the experiment itself
        for p in (LAT, DOSE):
            self.assertNotIn("arm_shapes", raw(p), p)

    def test_latency_config_runs_as_cells(self):
        e = experiment.load(LAT)
        self.assertEqual(experiment.arm_shapes_mode(e), "cells")
        self.assertTrue(experiment.cell_mode(e))
        self.assertFalse(experiment.restricted(e))
        # one rotation over all cells: a round is not grouped by shape
        self.assertEqual(experiment.order_period(e), len(experiment.cells(e)))
        for r in range(1, experiment.order_period(e) + 1):
            self.assertEqual([(s["name"], a["name"]) for rr, s, a in experiment.schedule(e, r, r)],
                             [(s["name"], a["name"]) for s, a in experiment.cell_order(e, r)])

    def test_contention_config_runs_per_shape(self):
        e = experiment.load(DOSE)
        self.assertEqual(experiment.arm_shapes_mode(e), "per_shape")
        self.assertFalse(experiment.cell_mode(e))
        self.assertTrue(experiment.restricted(e))
        self.assertEqual(experiment.order_period(e), e["rotation_block"])
        for r in (1, 2, 3):
            want = [(sh["name"], a["name"]) for sh in experiment.shape_order(e, r)
                    for a in experiment.shape_round_order(e, r, sh)]
            self.assertEqual([(s["name"], a["name"]) for rr, s, a in experiment.schedule(e, r, r)], want)

    def test_no_arm_shapes_no_mode(self):
        e = experiment.load(U)
        self.assertIsNone(experiment.arm_shapes_mode(e))
        self.assertFalse(experiment.cell_mode(e))
        self.assertFalse(experiment.restricted(e))

    def test_the_key_overrides_the_default_and_is_validated(self):
        e = experiment.load(DOSE)
        e["arm_shapes"] = "cells"
        self.assertTrue(experiment.cell_mode(e))
        e = experiment.load(LAT)
        e["arm_shapes"] = "per_shape"
        self.assertTrue(experiment.restricted(e))
        e["arm_shapes"] = "both"
        self.assertTrue(any("arm_shapes must be one of" in x for x in experiment.validate(e, allow_short=True)))

    def test_analysis_rows_per_mode(self):
        # cells keep a row for every comparison in every shape (as the latency results were
        # written); per shape, an arm that does not run in a shape has no row there
        for path, cells in ((LAT, True), (DOSE, False)):
            e = experiment.load(path)
            legs = [{"round": r, "shape": s["name"], "arm": a["name"], "verdict": {"valid": True}}
                    for r, s, a in experiment.schedule(e, 1, experiment.order_period(e))]
            an = experiment.analyse(e, legs)
            pairs = experiment.comparison_pairs(e)
            for sh in e["shapes"]:
                here = {a["name"] for a in experiment.shape_arms(e, sh)}
                rows = [(c["arm"], c["ref"]) for c in an["shapes"][sh["name"]]["comparisons"]]
                want = [p for p in pairs if cells or (p[0] in here and p[1] in here)]
                self.assertEqual(rows, [tuple(p) for p in want], (path, sh["name"]))


if __name__ == "__main__":
    unittest.main()
