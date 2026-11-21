"""The small analysis scripts that print figures quoted beside the tables: their arithmetic on
synthetic input, and (only when the fetched data is present) their output against the copy that
git keeps under docs/stats-tables/."""
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "stats")
TABLES = os.path.join(HERE, "docs", "stats-tables")


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MICRO = load("examples/stats-mt/analysis-micro/extras.py", "micro_extras")
CODEGEN = load("examples/stats-mt/analysis-codegen/extras.py", "codegen_extras")
MFIX = load("examples/stats-flush/analysis-mfix/widened.py", "mfix_widened")


def bench_file(path, rows):
    """A Google Benchmark output with [(name, {metric: value})] as iteration rows."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"context": {}, "benchmarks": [dict(v, name=n, run_type="iteration") for n, v in rows]
                   + [{"name": rows[0][0] + "_mean", "run_type": "aggregate", "cycles_per_op": 1e9}]}, f)


class MicroExtrasTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)

    def test_load_takes_round_medians_of_accepted_processes(self):
        n = "bmCounterIncShared/min_time:1.000/manual_time/threads:4"
        for rnd, vals in ((1, (10.0, 12.0, 50.0)), (2, (20.0, 22.0, 24.0))):
            bench_file(os.path.join(self.d, "r%02d-1-stat_update-vm-fix.json" % rnd), [(n, {"cycles_per_op": v}) for v in vals])
        bench_file(os.path.join(self.d, "r03-1-stat_update-vm-fix.json.tmp"), [(n, {"cycles_per_op": 999.0})])
        bench_file(os.path.join(self.d, "r01-1-stat_update-vm-fix-relaxed.json"), [(n, {"cycles_per_op": 1.0})])
        clean = "bmCounterIncShared/manual_time/threads:4"
        got = MICRO.round_medians(MICRO.load(self.d, "stat_update", "fix"), clean, "cycles_per_op")
        self.assertEqual(got, {1: 12.0, 2: 22.0})  # the timing suffix is dropped, aggregates and other arms are not read
        self.assertEqual(MICRO.level(MICRO.load(self.d, "stat_update", "fix"), clean, "cycles_per_op"), 17.0)
        with_rejected = MICRO.round_medians(MICRO.load(self.d, "stat_update", "fix", rejected=True), clean, "cycles_per_op")
        self.assertEqual(with_rejected[3], 999.0)

    def test_names_and_threads(self):
        self.assertEqual(MICRO.threads_of("bmModelCurrentShared/manual_time/threads:19"), 19)
        self.assertEqual(MICRO.threads_of("bmHistogramRecordOnly/7/manual_time"), 7)

    def test_paired_ratio(self):
        ref, arm = {1: 100.0, 2: 200.0, 3: 400.0}, {1: 90.0, 2: 180.0, 3: 360.0, 4: 1.0}
        n, eff, lo, hi = MICRO.paired_ratio(ref, arm)
        self.assertEqual(n, 3)
        for v in (eff, lo, hi):
            self.assertAlmostEqual(v, -10.0, places=9)  # the same ratio in every round: no spread
        self.assertIsNone(MICRO.paired_ratio({1: 1.0}, {1: 2.0}))

    def test_t_interval_and_welch(self):
        n, m, lo, hi = MICRO.t_interval([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual((n, m), (5, 3.0))
        self.assertAlmostEqual(hi - m, 2.7764451 * math.sqrt(2.5 / 5), places=5)
        d, lo, hi, df = MICRO.welch([1.0, 2.0, 3.0, 4.0, 5.0], [2.0, 4.0, 6.0, 8.0, 10.0])
        self.assertAlmostEqual(d, -3.0)
        self.assertAlmostEqual(df, 5.882352941, places=6)   # Welch-Satterthwaite
        self.assertAlmostEqual(hi - d, 2.4588 * math.sqrt(0.5 + 2.0), places=3)  # t(0.975, 5.88)
        # equal samples: the classic 2n - 2
        self.assertAlmostEqual(MICRO.welch([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])[3], 4.0)

    def test_model(self):
        self.assertAlmostEqual(MICRO.model_pct(17.0, 12.6, 572100.0), 0.03744, places=4)
        self.assertEqual(MICRO.model_pct(0.0, 12.6, 572100.0), 0.0)

    def test_cycles_per_request_inputs(self):
        legs = [{"shape": "mt-28w", "arm": "base", "workers_cycles_per_req": v, "verdict": {"valid": True}} for v in (10.0, 20.0)]
        legs += [{"shape": "mt-28w", "arm": "base", "workers_cycles_per_req": 500.0, "verdict": {"valid": False}},
                 {"shape": "mt-28w", "arm": "base", "workers_cycles_per_req": 700.0, "verdict": {"valid": True}, "superseded": True},
                 {"shape": "mt-4w", "arm": "base", "workers_cycles_per_req": 900.0, "verdict": {"valid": True}}]
        os.makedirs(os.path.join(self.d, "u"))
        with open(os.path.join(self.d, "u", "results.json"), "w") as f:
            json.dump({"legs": legs}, f)
        self.assertEqual(MICRO.u_base_cycles(self.d), 15.0)
        run = os.path.join(self.d, "arm-vm", "codegen")
        os.makedirs(run)
        with open(os.path.join(run, "results.json"), "w") as f:
            json.dump({"legs": [{"shape": "mt-12w", "arm": "official", "workers_cycles_per_req": 300.0, "verdict": {"valid": True}},
                                {"shape": "mt-12w", "arm": "dev", "workers_cycles_per_req": 1.0, "verdict": {"valid": True}}]}, f)
        with open(os.path.join(self.d, "arm-vm", "codegen-smoke.out"), "w") as f:
            f.write("mt-4w    official   counter incs/req 14.0  histogram samples/req 2.8\n"
                    "mt-12w   dev        counter incs/req 15.0  histogram samples/req 2.8\ngauges: not counted\n")
        self.assertEqual(MICRO.codegen_inputs(self.d), (300.0, 14.5))


class WidenedTest(unittest.TestCase):
    def test_rule(self):
        self.assertEqual(MFIX.widened_half_width(10.0, 1.0, 1.0), 10.0)  # the plain interval when it is wider
        self.assertAlmostEqual(MFIX.widened_half_width(1.0, 3.0, 4.0), 1.96 * 5.0)

    def test_rows_use_the_rungs_own_aa(self):
        t = {"mfix": [
            {"family": "mfix", "shape": "idle-10k", "arm": "nosink-top", "ref": "nosink-main", "n": 5, "log_mean": -10.0,
             "hw": 2.0, "se": 0.7, "effect_pct": MFIX.pct(-10.0), "lo_pct": MFIX.pct(-12.0), "hi_pct": MFIX.pct(-8.0)},
            {"family": "mfix-aa", "shape": "idle-10k", "arm": "nosink-main-A2", "ref": "nosink-main", "hw": 4.0},
            {"family": "mfix-aa", "shape": "idle-1m", "arm": "nosink-main-A2", "ref": "nosink-main", "hw": 99.0},
            {"family": "mfix", "shape": "idle-1m", "arm": "x", "ref": "y", "missing": "fewer than 2 pairs"}]}
        (shape, arm, ref, eff, plain, aa, wide, n), = MFIX.rows(t)
        w = 1.96 * math.sqrt(0.7 ** 2 + 4.0 ** 2)
        self.assertEqual((shape, aa, n), ("idle-10k", 4.0, 5))
        self.assertAlmostEqual(wide[0], MFIX.pct(-10.0 - w))
        self.assertAlmostEqual(wide[1], MFIX.pct(-10.0 + w))
        self.assertLess(wide[0], plain[0])


class CodegenExtrasTest(unittest.TestCase):
    def test_removed_is_paired_by_round(self):
        legs = []
        for r, (a, b) in enumerate(((110.0, 100.0), (120.0, 108.0), (130.0, 116.0)), 1):
            legs += [{"shape": "mt-4w", "arm": "official", "round": r, "v": a}, {"shape": "mt-4w", "arm": "official-reject", "round": r, "v": b}]
        legs.append({"shape": "mt-4w", "arm": "official", "round": 9, "v": 1e9})  # no partner: not used
        n, mean, lo, hi = CODEGEN.removed(legs, "mt-4w", "official", "official-reject", lambda m: m["v"])
        self.assertEqual((n, mean), (3, 12.0))
        self.assertAlmostEqual(hi - mean, 4.3026527 * 2.0 / math.sqrt(3), places=5)


@unittest.skipUnless(os.path.isdir(os.path.join(DATA, "microbenchmarks")) and os.path.isdir(os.path.join(DATA, "multi-worker"))
                     and os.path.isdir(os.path.join(DATA, "arm-codegen")) and os.path.isdir(os.path.join(DATA, "sink-flush-cost")),
                     "needs the fetched data (python3 tools/fetch-stats-data.py)")
class WithDataTest(unittest.TestCase):
    """With data/stats/ filled: each script prints what git keeps."""

    def check(self, script, args, table):
        r = subprocess.run([sys.executable, os.path.join(HERE, script)] + args, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(TABLES, table)) as f:
            self.assertEqual(r.stdout, f.read(), table)

    def test_micro(self):
        self.check("examples/stats-mt/analysis-micro/extras.py", [], "microbenchmarks/analysis/extras.txt")

    def test_codegen(self):
        self.check("examples/stats-mt/analysis-codegen/extras.py", [], "arm-codegen/arm-vm/analysis/extras.txt")

    def test_mfix(self):
        self.check("examples/stats-flush/analysis-mfix/widened.py", [], "sink-flush-cost/analysis/widened.txt")


if __name__ == "__main__":
    unittest.main()
