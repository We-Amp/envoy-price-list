"""The client split test (flip.kind "split"): the same total load from one client process and from two at half the
load each, window pairs in one Envoy process, on the flip-block stand-ins."""
import json
import os
import tempfile
import time
import unittest

from epl import experiment

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class SplitBlockTest(unittest.TestCase):
    """The split test as a flip block (loop/flipblock.py, kind split) on the flip-block stand-ins."""

    @classmethod
    def setUpClass(cls):
        from tests import test_flipblock as tsf
        cls.tsf = tsf
        cls.fb = tsf.fb

    def example(self, **sets):
        return self.fb.load(os.path.join(FIX, "split-s.json"),
                            experiment.parse_sets(["%s=%s" % (k, json.dumps(v)) for k, v in sets.items()]))

    def test_example_and_refusals(self):
        exp, errs = self.example()
        self.assertEqual(errs, [])
        self.assertEqual(self.fb.plan(exp)[0], list("ABBABAABABBABAAB"))
        has = lambda sets, text: self.assertTrue(any(text in e for e in self.example(**sets)[1]),  # noqa: E731
                                                 (text, self.example(**sets)[1]))
        has({"flip.key": "envoy.x"}, "a split block flips no runtime key")
        has({"flip.values": {"A": 1, "B": 3}}, "a split block's flip.values are")
        has({"flip.cycle_connections": False}, "a split block sets flip.cycle_connections true")
        has({"flip.split_bound_lp": None}, "a split block needs flip.split_bound_lp")
        has({"shapes": [{"name": "s", "kind": "proxied", "path": "/s", "body_bytes": 4100, "rps": 5201}]},
            "divisible by client.concurrency")
        has({"flip.split_connections": "halve"}, "flip: unknown keys ['split_connections']")
        has({"flip.split_max_client_cpus_per_worker": None}, "a split block needs flip.split_max_client_cpus_per_worker")
        has({"cpus.client": "20-30"}, "has an odd length: the split test cannot halve it")
        has({"flip.order": "AA BB"}, "every pair of a split block has one A and one B window")

    def test_block_runs_two_processes_at_half_load(self):
        tsf = self.tsf
        tmp = tempfile.mkdtemp()
        exp = tsf.standin_exp(tmp)
        f = exp["flip"]
        for k in ("key", "marker_min", "aa_marker_max", "gates"):
            f.pop(k, None)
        f.update(kind="split", values={"A": 1, "B": 2}, cycle_connections=True, split_bound_lp=1.0,
                 split_max_client_cpus_per_worker=0.6)
        exp["client"]["connections_per_worker"] = 4
        exp["cpus"]["client"] = "20-23,60-63"
        self.assertEqual(self.fb.split_errors(exp), [])
        admin = tsf.Admin(exp["shapes"][0]["rps"])
        cpus_seen = []

        class Ops(tsf.StandInOps):
            def start_client(self, args, out, err, cpus=None):
                cpus_seen.append(cpus)
                return tsf.StandInOps.start_client(self, args, out, err)

            def client_cpu_s(self, pid):
                return time.monotonic() * 0.1  # 0.1 CPU per process: 0.05 or 0.1 per worker
        try:
            ops = Ops(exp, tmp, admin, tmp)
            res = self.fb.FlipBlock(exp, os.path.join(tmp, "block"), ops, log=lambda m: None).run()
        finally:
            admin.close()
        self.assertTrue(res["valid"], res["reasons"])
        self.assertEqual(admin.posts, [])  # no runtime write in a split block
        self.assertEqual(len(ops.started), 6)  # A B B A: 1 + 2 + 2 + 1 processes
        self.assertEqual(len(res["clients"]), 6)
        self.assertTrue(all(c["ok"] for c in res["clients"]), [c.get("reasons") for c in res["clients"]])
        # the B windows' processes ran half the workers each, at the same rate and connections per worker,
        # each on its own half of cpus.client; every client process's CPU was read and gated per window
        rates = {c["args"][c["args"].index("--rps") + 1] for c in res["clients"]}
        self.assertEqual(rates, {"200"})  # 400 req/s over 2 workers, or 200 over 1 worker
        conc = sorted(c["args"][c["args"].index("--concurrency") + 1] for c in res["clients"])
        self.assertEqual(conc, ["1", "1", "1", "1", "2", "2"])
        self.assertEqual({c["args"][c["args"].index("--connections") + 1] for c in res["clients"]}, {"4"})
        self.assertEqual(cpus_seen, [None, "20-21,60-61", "22-23,62-63", "20-21,60-61", "22-23,62-63", None])
        self.assertEqual([len(w["client_cpu"]) for w in res["windows"]], [1, 2, 2, 1])
        self.assertTrue(all(c["ok"] for w in res["windows"] for c in w["client_cpu"]))
        s = res["summary"]
        self.assertEqual(s["split"]["reading"], "client not the bottleneck")  # the stand-in's cost is the same
        self.assertTrue(s["gates"]["split_client_not_bottleneck"])
        self.assertEqual(ops.own.procs, {})

    def test_summary_flags_a_bottleneck(self):
        tsf = self.tsf
        f = {"kind": "split", "values": {"A": 1, "B": 2}, "split_bound_lp": 1.0}
        ws = [tsf.win("A", 1000.0, 2000.0, 1), tsf.win("B", 980.0, 2000.0, 2), tsf.win("B", 981.0, 2000.0, 3),
              tsf.win("A", 1000.0, 2000.0, 4)]
        s = self.fb.summarize(ws, f, True)
        self.assertLess(s["mean_lp"], -1.0)
        self.assertEqual(s["split"]["reading"], "client bottleneck")
        self.assertFalse(s["gates"]["split_client_not_bottleneck"])
        self.assertEqual(self.fb.summarize(ws, f, False)["split"]["reading"], "not resolved")


if __name__ == "__main__":
    unittest.main()
