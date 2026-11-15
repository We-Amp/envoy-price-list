import json
import os
import tempfile
import unittest
from collections import Counter

from epl import envoy_config, experiment, sysprobe
from epl.sim import SimBackend


def cfg(**over):
    c = {
        "name": "t", "rounds": 12, "base_arm": "a",
        "arms": [{"name": "a", "binary": "/bin/true"}, {"name": "b", "binary": "/bin/true"}],
        "shapes": [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 4000},
                   {"name": "fh", "path": "/fh", "kind": "direct_headers", "body_bytes": 128,
                    "request_headers_added": 57, "response_headers_added": 52, "rps": 4000}],
        "cpus": {"sut": "0-3", "client": "20-31", "origin": "32-39"},
        "client": {"binary": "/bin/true"},
    }
    c.update(over)
    return c


def three_arms(**over):
    return cfg(arms=[{"name": n, "binary": "/bin/true"} for n in "xyz"], base_arm="x", **over)


def load(c, tmp):
    p = os.path.join(tmp, "c.json")
    with open(p, "w") as f:
        json.dump(c, f)
    return experiment.load(p)


def positions(exp, rounds):
    pos = Counter()
    for r in range(1, rounds + 1):
        for i, a in enumerate(experiment.round_order(exp, r)):
            pos[(a["name"], i)] += 1
    return pos


class ExperimentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def errs(self, c, **kw):
        return experiment.validate(load(c, self.tmp), **kw)

    def test_validate_ok(self):
        self.assertEqual(self.errs(cfg()), [])
        self.assertEqual(self.errs(three_arms()), [])

    def test_validate_rounds(self):
        self.assertTrue(any(">= 12" in e for e in self.errs(cfg(rounds=6))))
        self.assertEqual(self.errs(cfg(rounds=6), allow_short=True), [])
        self.assertTrue(any("even" in e for e in self.errs(cfg(rounds=13))))
        self.assertTrue(any("even" in e for e in self.errs(cfg(rounds=5), allow_short=True)))
        self.assertTrue(any("multiple of 6" in e for e in self.errs(three_arms(rounds_block=4))))
        self.assertTrue(any("multiple of 6" in e for e in self.errs(three_arms(rounds=14))))
        self.assertTrue(any("capped" in e for e in self.errs(cfg(rounds_max=40))))
        self.assertTrue(any("use rotate" in e for e in self.errs(three_arms(order="abba"))))

    def test_validate_other(self):
        self.assertTrue(any("overlap" in e for e in self.errs(cfg(cpus={"sut": "0-3", "client": "3-5",
                                                                        "origin": "8"}))))
        self.assertTrue(any("2 arms" in e for e in self.errs(cfg(arms=[{"name": "a", "binary": "/bin/true"}]))))
        self.assertTrue(any("primary_metric" in e for e in self.errs(cfg(primary_metric="nope"))))

    def test_default_order(self):
        self.assertEqual(experiment.effective_order(load(cfg(), self.tmp)), "abba")
        self.assertEqual(experiment.effective_order(load(three_arms(), self.tmp)), "rotate")

    def test_two_arm_schedule_is_balanced_per_pair(self):
        exp = load(cfg(), self.tmp)
        plan = experiment.schedule(exp)
        self.assertEqual(len(plan), 12 * 2 * 2)
        firsts = [a["name"] for (r, s, a) in plan if s["name"] == "s"][::2]
        for i in range(0, 12, 2):
            self.assertEqual(sorted(firsts[i:i + 2]), ["a", "b"])
        self.assertEqual(set(positions(exp, 12).values()), {6})
        # the seeded coin flips some pairs, and the schedule is reproducible
        self.assertNotEqual(firsts, ["a", "b"] * 6)
        self.assertEqual(firsts, [a["name"] for (r, s, a) in experiment.schedule(exp) if s["name"] == "s"][::2])

    def test_three_arm_rotate_is_balanced(self):
        exp = load(three_arms(), self.tmp)
        for n in (6, 12, 18, 36):
            self.assertEqual(set(positions(exp, n).values()), {n // 3}, n)
        exp["order_seed"] = None
        self.assertEqual([a["name"] for a in experiment.round_order(exp, 1)], ["x", "y", "z"])
        self.assertEqual([a["name"] for a in experiment.round_order(exp, 2)], ["z", "y", "x"])
        self.assertEqual([a["name"] for a in experiment.round_order(exp, 3)], ["y", "z", "x"])

    def test_schedule_blocks_concatenate(self):
        exp = load(cfg(), self.tmp)
        whole = experiment.schedule(exp, 1, 18)
        parts = experiment.schedule(exp, 1, 12) + experiment.schedule(exp, 13, 18)
        self.assertEqual([(r, s["name"], a["name"]) for r, s, a in whole],
                         [(r, s["name"], a["name"]) for r, s, a in parts])

    def test_remote_root_after_action(self):
        import argparse
        from epl.__main__ import _check_root, _pull_root
        a = argparse.Namespace(root="epl", rest=["--root", "epl2", "x.json", "--fixed"])
        _pull_root(a)
        self.assertEqual((a.root, a.rest), ("epl2", ["x.json", "--fixed"]))
        for bad in ("", "/", "/abs", "~/x", "a/../b"):
            with self.assertRaises(SystemExit):
                _check_root(bad)

    def test_parse_sets(self):
        self.assertEqual(experiment.parse_sets(["cpus.sut=0-3", "rounds=24", "client.extra_args=[\"--x\"]"]),
                         {"cpus": {"sut": "0-3"}, "rounds": 24, "client": {"extra_args": ["--x"]}})

    def test_bootstrap_has_no_deprecated_fields(self):
        exp = load(cfg(), self.tmp)
        txt = envoy_config.bootstrap_text(exp["shapes"], exp["envoy"], 8092)
        self.assertNotIn("access_log_path", txt)
        self.assertNotIn('"append"', txt)
        b = json.loads(txt)
        routes = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"][
            "route_config"]["virtual_hosts"][0]["routes"]
        fh = [r for r in routes if r["match"]["path"] == "/fh"][0]
        self.assertEqual(len(fh["request_headers_to_add"]), 57)
        self.assertEqual(len(fh["response_headers_to_add"]), 52)
        self.assertEqual(envoy_config.origin_files(exp["shapes"]), {"s": 4096})

    def test_nighthawk_commit(self):
        self.assertEqual(experiment.nighthawk_commit("\nnighthawk_client  version: 0.3.0\n"),
                         (None, "not found in --version; the md5 identifies the build"))
        sha = "b2d89e0a" * 5
        self.assertEqual(experiment.nighthawk_commit("nighthawk_client  version: %s/0.3.0/Clean/RELEASE" % sha),
                         (sha, "--version"))
        self.assertEqual(experiment.nighthawk_commit("version: 0.3.0", "abc123"), ("abc123", "config"))

    def test_cpuset(self):
        self.assertEqual(sysprobe.parse_cpuset("0-3,40-41"), {0, 1, 2, 3, 40, 41})

    def test_scrub(self):
        self.assertEqual(sysprobe.scrub_text("/home/bob/epl/bin/envoy x /Users/al/y"), "~/epl/bin/envoy x ~/y")
        self.assertEqual(sysprobe.scrub({"p": ["/home/bob/a"], "/home/c/k": 1}), {"p": ["~/a"], "~/k": 1})
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "x.log"), "w") as f:
            f.write("bootstrap /home/bob/epl/runs/r/envoy-bootstrap.json\n")
        self.assertEqual(sysprobe.scrub_tree(d), ["x.log"])
        with open(os.path.join(d, "x.log")) as f:
            self.assertNotIn("/home/", f.read())


class DryRunTest(unittest.TestCase):
    def run_sim(self, c, expect_abort=False):
        tmp = tempfile.mkdtemp()
        exp = load(c, tmp)
        self.assertEqual(experiment.validate(exp, allow_short=True), [])
        r = experiment.Runner(exp, os.path.join(tmp, "run"), SimBackend)
        if expect_abort:
            with self.assertRaises(RuntimeError):
                r.run(simulate=True)
            with open(os.path.join(tmp, "run", "results.json")) as f:
                return json.load(f), os.path.join(tmp, "run")
        return r.run(simulate=True), os.path.join(tmp, "run")

    def test_aa_passes_a_clean_harness(self):
        passes = 0
        for seed in range(1, 21):
            # pair SD of total cycles about 1.4%, as in the LRU A/A on the bench box
            res, _ = self.run_sim(cfg(expect="aa", sim_seed=seed, sim_cycles_noise=0.014))
            passes += res["aa_selftest"]["pass"]
        # Holm keeps the family-wise false-fail rate at or under alpha
        self.assertGreaterEqual(passes, 18)

    def test_aa_fails_a_biased_harness(self):
        fails = 0
        for seed in range(1, 11):
            c = cfg(expect="aa", sim_seed=seed, sim_cycles_noise=0.014)
            c["arms"][1]["sim_cycles_factor"] = 1.02
            res, _ = self.run_sim(c)
            fails += not res["aa_selftest"]["pass"]
        self.assertGreaterEqual(fails, 9)

    def test_aa_fails_when_too_noisy(self):
        res, _ = self.run_sim(cfg(expect="aa", sim_seed=2, sim_cycles_noise=0.10, adaptive=False))
        self.assertFalse(res["aa_selftest"]["pass"])
        self.assertTrue(any("half-width" in c["why"] for c in res["aa_selftest"]["checks"]))

    def test_aa_limit_follows_the_claimed_effect(self):
        # 3% pair SD: a 12-round A/A has a half-width near 1.9%, which the old 3%
        # limit passed; the adaptive run now goes on to reach 1%, or fails at the cap
        res, _ = self.run_sim(cfg(expect="aa", sim_seed=1, sim_cycles_noise=0.03, adaptive=False))
        self.assertFalse(res["aa_selftest"]["pass"])
        self.assertTrue(any("half-width" in c["why"] and c["metric"] == "cycles_total"
                            for c in res["aa_selftest"]["checks"]))
        res, _ = self.run_sim(cfg(expect="aa", sim_seed=1, sim_cycles_noise=0.014))
        self.assertGreater(res["metadata"]["rounds_done"], 12)

    def test_effects_inside_the_aa_floor_are_marked(self):
        aa, _ = self.run_sim(cfg(expect="aa", sim_seed=7, sim_cycles_noise=0.014))
        floor = experiment.floor_from_results(aa)
        hw = floor["s"]["cycles_total"]["hw"]
        far = floor["s"]["cycles_total"]["far"]
        self.assertGreaterEqual(far, hw)
        c = {"paired": {"log_mean_pct": hw * 0.5}, "aa_floor_half_width_pct": hw, "aa_floor_far_pct": far}
        self.assertEqual(experiment.aa_position(c), "floor")
        c["paired"]["log_mean_pct"] = -(hw + far) / 2 if far > hw else -hw
        self.assertIn(experiment.aa_position(c), ("floor", "interval"))
        c["paired"]["log_mean_pct"] = far + 0.5
        self.assertIsNone(experiment.aa_position(c))
        # end to end: a 2.5% effect against an A/A whose interval reached 3% is flagged
        fake = {"analysis": {"shapes": {"s": {"comparisons": [{"cycles_total": {"paired": {
            "half_width_pct": 1.5, "log_lo_pct": -3.0, "log_hi_pct": 0.0}}}]},
            "fh": {"comparisons": []}}}}
        c = cfg(sim_seed=3, sim_cycles_noise=0.003)
        c["arms"][1]["sim_cycles_factor"] = 1.025
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "aa.json"), "w") as f:
            json.dump(fake, f)
        c["floor_from"] = os.path.join(tmp, "aa.json")
        res, rd = self.run_sim(c)
        cyc = res["analysis"]["shapes"]["s"]["vs_base"]["b"]["cycles_total"]
        self.assertTrue(cyc["differs"])
        self.assertEqual(cyc["inside_aa"], "interval")
        self.assertIn("inside the A/A interval", cyc["status"])
        with open(os.path.join(rd, "summary.md")) as f:
            self.assertIn("inside the A/A interval", f.read())

    def test_ab_detects_five_percent(self):
        c = cfg(sim_seed=3)
        c["arms"][1]["sim_factor"] = 0.95
        res, rd = self.run_sim(c)
        comp = res["analysis"]["shapes"]["s"]["vs_base"]["b"]
        cyc = comp["cycles_total"]
        self.assertEqual(cyc["role"], "primary")
        self.assertTrue(cyc["differs"])
        self.assertLess(cyc["paired"]["hi_pct"], 0)
        self.assertTrue(-7 < cyc["paired"]["effect_pct"] < -3)
        self.assertIn("holm_p", cyc)
        ins = comp["instructions_u"]
        self.assertEqual(ins["role"], "exploratory")
        self.assertNotIn("holm_p", ins)
        self.assertEqual(ins["status"], "exploratory: interval excludes 0")
        with open(os.path.join(rd, "summary.md")) as f:
            self.assertIn("[95% CI]", f.read())

    def test_adaptive_rounds(self):
        res, _ = self.run_sim(cfg(sim_seed=4))
        self.assertEqual(res["metadata"]["rounds_done"], 12)
        res, _ = self.run_sim(cfg(sim_seed=4, sim_cycles_noise=0.07))
        self.assertGreater(res["metadata"]["rounds_done"], 12)
        self.assertEqual(res["metadata"]["rounds_done"] % 6, 0)
        res, _ = self.run_sim(cfg(sim_seed=4, sim_cycles_noise=0.2))
        self.assertEqual(res["metadata"]["rounds_done"], 36)
        self.assertIn("cap", res["metadata"]["stop_reason"])
        res, _ = self.run_sim(cfg(sim_seed=4, sim_cycles_noise=0.2, adaptive=False))
        self.assertEqual(res["metadata"]["rounds_done"], 12)

    def test_faults_rerun_the_round(self):
        faults = {"r01-s-a": "rate", "r02-s-b": "overflow", "r03-s-a": "headroom", "r04-s-b": "port",
                  "r05-s-a": "idle", "r06-s-b": "non2xx", "r07-s-a": "uneven", "r08-s-b": "noworkers",
                  "r09-s-a": "nosched"}
        res, rd = self.run_sim(cfg(sim_faults=faults, adaptive=False))
        bad = {m["leg_id"] for m in res["legs"] if not m["verdict"]["valid"]}
        self.assertEqual(bad, set(faults))
        sup = {m["leg_id"] for m in res["legs"] if m.get("superseded")}
        self.assertEqual(sup, {"r%02d-s-%s" % (r, a) for r in range(1, 10) for a in "ab"})
        self.assertEqual(res["analysis"]["shapes"]["s"]["vs_base"]["b"]["rounds_paired"], list(range(1, 13)))
        reruns = [m for m in res["legs"] if m["attempt"] == 1]
        self.assertEqual(len(reruns), 18)
        # a re-run keeps the round's own order
        exp = load(cfg(), tempfile.mkdtemp())
        for r in range(1, 10):
            got = [m["arm"] for m in reruns if m["round"] == r]
            self.assertEqual(got, [a["name"] for a in experiment.round_order(exp, r)])
        with open(os.path.join(rd, "summary.md")) as f:
            self.assertIn("18 legs superseded", f.read())

    def test_persistent_faults_leave_insufficient_pairs(self):
        faults = {}
        for r in range(1, 8):
            faults["r%02d-s-a" % r] = "rate"
            faults["r%02d-s-a.rr1" % r] = "rate"
        res, _ = self.run_sim(cfg(sim_faults=faults, adaptive=False, abort_after_invalid=100))
        cyc = res["analysis"]["shapes"]["s"]["vs_base"]["b"]["cycles_total"]
        self.assertEqual(cyc["n"], 5)
        self.assertEqual(cyc["status"], "insufficient")
        self.assertIsNone(cyc["differs"])

    def test_abort_after_consecutive_invalid_legs(self):
        faults = {"r01-s-a": "idle", "r01-s-b": "idle", "r01-fh-a": "idle", "r01-fh-b": "idle"}
        res, rd = self.run_sim(cfg(sim_faults=faults, abort_after_invalid=3), expect_abort=True)
        self.assertIn("consecutive invalid", res["metadata"]["aborted"])
        with open(os.path.join(rd, "status.json")) as f:
            self.assertEqual(json.load(f)["state"], "aborted")

    def test_three_arms_all_pairs_holm(self):
        c = three_arms(comparisons="all_pairs", sim_seed=5)
        c["arms"][2]["sim_factor"] = 0.9
        res, _ = self.run_sim(c)
        an = res["analysis"]
        self.assertEqual(an["primary_family_size"], 2 * 3)
        comps = [(x["arm"], x["ref"]) for x in an["shapes"]["s"]["comparisons"]]
        self.assertEqual(comps, [("y", "x"), ("z", "x"), ("z", "y")])
        zx = an["shapes"]["s"]["comparisons"][1]["cycles_total"]
        self.assertTrue(zx["differs"])
        self.assertGreaterEqual(zx["holm_p"], zx["paired"]["t_p"])


if __name__ == "__main__":
    unittest.main()


class SsParseTest(unittest.TestCase):
    def test_segs_in_ignores_data_segs_in(self):
        from epl import leg
        line = ("cubic wscale:7,7 rto:204 rtt:0.02/0.01 mss:65483 cwnd:10 bytes_received:4096 "
                "segs_out:12 segs_in:120 data_segs_out:10 data_segs_in:80 send 2.6Gbps lastsnd:4")
        self.assertEqual(leg.SEGS_RE.findall(line), ["120"])
        two = line + "\n" + line.replace("segs_in:120", "segs_in:7").replace("data_segs_in:80", "data_segs_in:5")
        self.assertEqual(leg.SEGS_RE.findall(two), ["120", "7"])


class TimelineTest(unittest.TestCase):
    def test_quantiles(self):
        from epl import leg
        q = leg.parse_quantiles("x: P0(nan,0.05) P50(1.05,1.1) P99(2.5,3) P99.9(nan,nan) P100(9,12)")
        self.assertEqual(q["50"], (1.05, 1.1))
        self.assertEqual(q["0"], (None, 0.05))
        self.assertEqual(q["99.9"], (None, None))
        self.assertEqual(q["100"], (9.0, 12.0))

    def test_pause_only_own_process_and_resumes(self):
        import socket
        import sys
        import time
        from epl import leg
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        own = leg.OwnProcesses()
        p = own.start([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            t0 = time.monotonic()
            tl = leg.Timeline({"at_s": 0.3, "pause_hop2_ms": 20, "sample_s": 0.1}, own, p, p, port, port, t0)
            tl.start()
            time.sleep(0.8)
            tl.stop_evt.set()
            tl.join(timeout=5)
            self.assertFalse(tl.is_alive())
            self.assertEqual(tl.burst["method"], "pause_hop2")
            self.assertGreaterEqual(tl.burst["pause_ms_actual"], 19.0)
            self.assertGreaterEqual(tl.burst["t"], 0.3)
            self.assertGreaterEqual(len(tl.samples), 6)
            self.assertIsNone(p.poll())  # resumed, still running
            stranger = leg.OwnProcesses()
            tl2 = leg.Timeline({"at_s": 0.05, "pause_hop2_ms": 20}, stranger, p, p, port, port, time.monotonic())
            tl2.start()
            time.sleep(0.3)
            tl2.stop_evt.set()
            tl2.join(timeout=5)
            self.assertIn("error", tl2.burst)
        finally:
            own.stop(p, grace_s=5)
