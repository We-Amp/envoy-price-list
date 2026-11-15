import itertools
import math
import unittest

from epl import stats


def brute_wilcoxon(d):
    d = [x for x in d if x != 0]
    ranks = stats._ranks_abs(d)
    obs = sum(r for r, x in zip(ranks, d) if x > 0)
    sums = [sum(r for r, s in zip(ranks, signs) if s) for signs in itertools.product([0, 1], repeat=len(d))]
    lo = sum(1 for s in sums if s <= obs + 1e-9) / len(sums)
    hi = sum(1 for s in sums if s >= obs - 1e-9) / len(sums)
    return min(1.0, 2 * min(lo, hi))


class StatsTest(unittest.TestCase):
    def test_sign_test_known_values(self):
        self.assertAlmostEqual(stats.sign_test_p(6, 0), 2 / 64)
        self.assertAlmostEqual(stats.sign_test_p(0, 6), 2 / 64)
        self.assertAlmostEqual(stats.sign_test_p(5, 1), 2 * 7 / 64)
        self.assertAlmostEqual(stats.sign_test_p(3, 3), 1.0)
        self.assertAlmostEqual(stats.sign_test_p(8, 0), 2 / 256)
        self.assertEqual(stats.sign_test_p(0, 0), 1.0)

    def test_wilcoxon_matches_brute_force(self):
        cases = [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, -6], [-1, 2, -3, 4, -5, 6],
                 [0.5, 0.5, -0.5, 1, 2, -2, 3], [1, 1, 1, 1, -1, 1], [3, -1, 4, -1, 5, -9, 2, 6]]
        for c in cases:
            self.assertAlmostEqual(stats.wilcoxon_p(c), brute_wilcoxon(c), msg=str(c))

    def test_wilcoxon_known(self):
        self.assertAlmostEqual(stats.wilcoxon_p([1, 2, 3, 4, 5, 6]), 2 / 64)
        self.assertEqual(stats.wilcoxon_p([0, 0]), 1.0)

    def test_compare_paired(self):
        base = [100, 102, 98, 101, 99, 100]
        arm = [90, 93, 88, 91, 89, 90]
        c = stats.compare_paired(base, arm)
        self.assertEqual(c["pairs_won"], 6)
        self.assertAlmostEqual(c["sign_p"], 2 / 64)
        self.assertLess(c["delta_mean_pct"], -9)
        self.assertTrue(0.88 < c["ratio_median"] < 0.92)
        self.assertTrue(-11 < c["paired"]["effect_pct"] < -9)

    def test_t_quantiles(self):
        # textbook values
        for df, q, want in ((1, 0.975, 12.7062), (5, 0.975, 2.5706), (11, 0.975, 2.2010), (35, 0.975, 2.0301),
                            (11, 0.8, 0.8755), (1000, 0.975, 1.9623)):
            self.assertAlmostEqual(stats.t_ppf(q, df), want, places=3)
        self.assertAlmostEqual(stats.t_cdf(0.0, 7), 0.5)
        self.assertAlmostEqual(stats.t_ppf(0.025, 5), -2.5706, places=3)

    def test_paired_log_ratio_matches_hand_computation(self):
        # the A/A /s cycles pairs from the week-1 review: mean -3.1, SD 7.6, t95 8.0
        d = [1.7, -13.1, 6.5, -11.4, -0.5, -2.0]
        p = stats.paired_log_ratio([1.0] * 6, [math.exp(x / 100) for x in d])
        self.assertAlmostEqual(p["log_mean_pct"], -3.133, places=2)
        self.assertAlmostEqual(p["log_sd_pct"], 7.643, places=2)
        self.assertAlmostEqual(p["half_width_pct"], 8.02, places=1)
        self.assertGreater(p["t_p"], 0.3)
        self.assertLess(p["lo_pct"], 0)
        self.assertGreater(p["hi_pct"], 0)

    def test_paired_log_ratio_zero_spread(self):
        p = stats.paired_log_ratio([100.0] * 6, [90.0] * 6)
        self.assertEqual(p["t_p"], 0.0)
        p = stats.paired_log_ratio([100.0] * 6, [100.0] * 6)
        self.assertEqual(p["t_p"], 1.0)

    def test_holm(self):
        self.assertEqual(stats.holm([0.01, 0.04, 0.03, 0.2]), [0.04, 0.09, 0.09, 0.2])
        self.assertEqual(stats.holm([]), [])
        self.assertEqual(stats.holm([0.5, 0.6]), [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
