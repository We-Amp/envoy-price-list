import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

from epl import envoy_config, experiment, leg, portability, validity

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MT = os.path.join(HERE, "examples", "stats-mt")


def _mod(name, path):
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.path.pop(0)


MK = _mod("mt_make", os.path.join(MT, "make.py"))
MICRO = _mod("mt_micro", os.path.join(MT, "micro.py"))
UT = _mod("mt_u_table", os.path.join(MT, "u_table.py"))


def box(name):
    with open(os.path.join(MT, "boxes", name + ".json")) as f:
        return json.load(f)


class RungTest(unittest.TestCase):
    def test_rung_of_and_client(self):
        e = {"envoy": {"workers": 4}, "cpus": {"sut": "0-3"}}
        r = leg.rung_of(e, {"name": "s"})
        self.assertEqual((r["workers"], r["main_cpu"], r["start_cpus"]), (4, None, "0-3"))
        sh = {"workers": 14, "worker_cpus": "0-6,20-26", "main_cpu": 19}
        r = leg.rung_of(e, sh)
        self.assertEqual(r["workers"], 14)
        self.assertEqual(r["start_cpus"], "19")  # Envoy starts on the main core only
        self.assertEqual(r["sut_set"], set(range(0, 7)) | set(range(20, 27)) | {19})
        c = leg.client_for({"concurrency": 16, "connections_per_worker": 32}, {"client_concurrency": 14,
                                                                                "client_connections_per_worker": 64})
        self.assertEqual((c["concurrency"], c["connections_per_worker"]), (14, 64))

    def test_parsers(self):
        st = "Active connections: 3 \nserver accepts handled requests\n 10 10 12345 \nReading: 0 Writing: 1 Waiting: 2 \n"
        self.assertEqual(leg.parse_stub_status(st), 12345)
        self.assertIsNone(leg.parse_stub_status("nothing"))
        self.assertAlmostEqual(leg.steal_share((1000, 10), (2000, 30)), 0.02)
        self.assertEqual(leg.parse_numastat("x\n Node 0 Node 1 Total\nTotal 10.5 2.0 12.5\n"),
                         {"node0": 10.5, "node1": 2.0})

    def test_gates(self):
        ok = {"idle_ok": True, "preflight_ok": True, "pinning_ok": True, "perf_ok": True, "responses": 40000,
              "target_rps": 2000, "sut_rate_2xx": 2001.0, "client_overflow": {}, "client_non2xx": {}, "sut_non2xx": 0,
              "client_headroom": 0.6, "client_workers": 16, "client_pending_total": 16, "sut_foreign_cpus": 0.0,
              "sut_sibling_cpus": 0.0, "envoy_exit": 0, "perf_min_running_pct": 100.0, "envoy_workers": 4,
              "envoy_worker_max_share": 0.25, "envoy_worker_min_share": 0.25}
        self.assertTrue(validity.verdict(ok)["valid"])
        for mut, needle, cfg in (({"steal_share": 0.05}, "steal", {"max_steal_share": 0.02}),
                                 ({}, "steal time unknown", {"max_steal_share": 0.02}),
                                 ({"rung_pin": {"ok": False}}, "rung threads not on", None),
                                 ({"rung_pin_after": {"ok": False}}, "left their cores", None)):
            v = validity.verdict(dict(ok, **mut), cfg)
            self.assertFalse(v["valid"], needle)
            self.assertTrue(any(needle in r for r in v["reasons"]), v["reasons"])
        self.assertTrue(validity.verdict(dict(ok, steal_share=0.01), {"max_steal_share": 0.02})["valid"])


class AuditAndOriginTest(unittest.TestCase):
    def test_audit(self):
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "u.json"))
        for a in exp["arms"]:
            b = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, a, "/r"), 8092)
            self.assertEqual(envoy_config.audit_mt_s(b), [], a["name"])
        b = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, exp["arms"][0], "/r"), 8092)
        b["static_resources"]["clusters"][0]["lb_policy"] = "LEAST_REQUEST"
        self.assertTrue(envoy_config.audit_mt_s(b))
        b = envoy_config.bootstrap(exp["shapes"], dict(experiment.arm_envoy(exp, exp["arms"][0], "/r"),
                                                       local_ratelimit={"tokens_per_s": 100}), 8092)
        self.assertTrue(any("router only" in p for p in envoy_config.audit_mt_s(b)))
        bad = json.load(open(os.path.join(MT, "bench-x86_64", "u.json")))
        bad["arms"][1]["settings"]["retries"] = True
        bad["arms"][2]["settings"] = {"local_ratelimit": {"tokens_per_s": 100}}
        d = tempfile.mkdtemp()
        p = os.path.join(d, "u.json")
        json.dump(bad, open(p, "w"))
        self.assertTrue(any("audit" in e for e in experiment.validate(experiment.load(p), allow_short=True)))

    def test_stub_status(self):
        self.assertEqual(envoy_config.nginx_conf(8092, 8), envoy_config.nginx_conf(8092, 8, stub_status=False))
        self.assertIn("location = /epl-status { stub_status; }", envoy_config.nginx_conf(8092, 8, stub_status=True))


class ConfigsTest(unittest.TestCase):
    def test_written_and_valid(self):
        for b in ("bench-x86_64", "arm-vm", "x86-vm"):
            for fn, c in MK.configs(box(b)).items():
                with open(os.path.join(MT, b, fn)) as f:
                    self.assertEqual(json.load(f), json.loads(json.dumps(c)), "%s/%s: rerun make.py" % (b, fn))
                if "shapes" in c:
                    self.assertEqual(experiment.validate(experiment.load(os.path.join(MT, b, fn)), allow_short=True),
                                     [], "%s/%s" % (b, fn))
        self.assertEqual(portability.check_dirs([os.path.join(MT, b) for b in ("bench-x86_64", "arm-vm", "x86-vm")]),
                         [])

    def test_rungs_equal_per_worker(self):
        c = MK.configs(box("bench-x86_64"), {"bench-x86_64": {"r_star": 1400, "k": 28}})["u.json"]
        self.assertNotIn("uncalibrated", c)
        self.assertEqual([s["name"] for s in c["shapes"]], ["mt-1w", "mt-4w", "mt-14w-one", "mt-14w-split", "mt-28w"])
        for s in c["shapes"]:
            self.assertEqual(s["rps"], 1400 * s["workers"])
            self.assertEqual(s["client_concurrency"] * s["client_connections_per_worker"], 28 * s["workers"])
            self.assertEqual(s["main_cpu"], 19)
        self.assertEqual(c["measure"]["responses_from"], "origin")
        self.assertTrue(c["origin"]["stub_status"])
        self.assertEqual(c["primary_metric"], "workers_cycles_per_req")
        self.assertEqual([a["name"] for a in c["arms"]], ["base", "stats-reject", "base-A2"])
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "u.json"))
        self.assertEqual(len(experiment.schedule(exp)), 225)  # 15 fixed rounds: rungs and arms both balance
        self.assertFalse(exp["adaptive"])
        self.assertIn("3c9cce2f2c", exp["session_record"]["fix_envoy_static"]["record"])
        first = [experiment.shape_order(exp, r)[0]["name"] for r in range(1, 6)]
        self.assertEqual(len(set(first)), 5)  # every rung leads one round in five
        self.assertIn("u-hitm.json", MK.configs(box("bench-x86_64")))
        self.assertNotIn("u-hitm.json", MK.configs(box("arm-vm")))
        vm = MK.configs(box("arm-vm"))["u.json"]
        self.assertEqual(vm["validity"]["max_steal_share"], 0.02)
        self.assertEqual(vm["measure"]["perf"], "sudo -n /usr/bin/perf")
        with self.assertRaises(ValueError):
            MK.rung_shapes({"main_cpu": 5, "rungs": [{"name": "3w", "workers": 3, "worker_cpus": "0-2",
                                                      "client_concurrency": 2}]}, 1301, 8)

    def test_bad_rung(self):
        c = json.load(open(os.path.join(MT, "bench-x86_64", "u.json")))
        c["shapes"][0]["main_cpu"] = 0
        d = tempfile.mkdtemp()
        p = os.path.join(d, "u.json")
        json.dump(c, open(p, "w"))
        self.assertTrue(any("main_cpu outside" in e for e in experiment.validate(experiment.load(p), allow_short=True)))


class MicroTest(unittest.TestCase):
    def test_plan_and_order(self):
        cfg = json.load(open(os.path.join(MT, "bench-x86_64", "micro.json")))
        self.assertEqual(cfg["arms"]["fix-relaxed"], "d2c62bf670")
        self.assertEqual(cfg["arms"]["fix"], "977c664058")
        no_mix = MICRO.plan(cfg)
        self.assertFalse(any(cfg["runs"][i].get("needs_mix") for _, i, _ in no_mix))
        self.assertGreater(len(MICRO.plan(cfg, "24:4")), len(no_mix))
        firsts = {MICRO.arm_order(cfg, r)[0] for r in range(1, 6)}
        self.assertGreaterEqual(len(firsts), 4)
        vm = json.load(open(os.path.join(MT, "arm-vm", "micro.json")))
        for r in vm["runs"]:
            self.assertNotIn("16", r["filter"].split("threads:")[-1])

    def test_dry_run_and_table(self):
        d = tempfile.mkdtemp()
        root = os.path.join(d, "bins")
        cfg = json.load(open(os.path.join(MT, "bench-x86_64", "micro.json")))
        cfg["rounds"] = 3
        cfg["runs"] = cfg["runs"][:1]
        for c in cfg["arms"].values():
            os.makedirs(os.path.join(root, c))
            open(os.path.join(root, c, "atomic_model_benchmark"), "w").write("x")
        out = os.path.join(d, "out")
        lines = []
        MICRO.run(cfg, out, root, dry_run=True, log=lines.append)
        self.assertEqual(len(lines), 3 * 6)
        self.assertIn("STATS_BENCH" if False else "--benchmark_filter=", lines[0])
        # synthetic outputs: fix-relaxed 10% faster than fix on the shared case, spaced 5x faster than shared
        import math
        for r in range(1, 4):
            for arm in cfg["arms"]:
                f = 0.9 if arm == "fix-relaxed" else 1.0
                bm = []
                for name, ns in (("bmModelCurrentShared/real_time/threads:4", 50.0 * f * (1 + 0.01 * r)),
                                 ("bmModelCurrentPerThreadSpaced/real_time/threads:4", 10.0 * (1 + 0.01 * r))):
                    bm.append({"name": name + "_median", "run_name": name, "run_type": "aggregate",
                               "aggregate_name": "median", "real_time": ns, "time_unit": "ns",
                               "label": "cpus=0-19 placement=one-socket"})
                json.dump({"benchmarks": bm}, open(os.path.join(out, "r%02d-0-atomic_model-one-socket-%s.json" % (r, arm)), "w"))
        text, js = MICRO.table(out)
        row = [p for p in js["pairs"] if p["arm"] == "fix-relaxed" and p["ref"] == "fix" and "Shared" in p["benchmark"]][0]
        self.assertAlmostEqual(row["effect_pct"], -10.0, places=6)
        self.assertTrue(row["descriptive"])  # 3 rounds < 5
        h1 = [x for x in js["h1"] if x["arm"] == "fix"][0]
        self.assertAlmostEqual(h1["ratio"], 5.0, places=6)
        del math


class UTableTest(unittest.TestCase):
    def test_growth_and_aa(self):
        exp = json.load(open(os.path.join(MT, "bench-x86_64", "u.json")))
        legs = []
        import random
        rng = random.Random(3)
        price = {"mt-1w": 20e3, "mt-4w": 24e3, "mt-14w-one": 30e3, "mt-14w-split": 36e3, "mt-28w": 40e3}
        for r in range(1, 13):
            for s in exp["shapes"]:
                base = 300e3 * rng.gauss(1, 0.002)
                for arm, v in (("base", base), ("base-A2", base * rng.gauss(1, 0.002)),
                               ("stats-reject", base - price[s["name"]] * rng.gauss(1, 0.01))):
                    legs.append({"leg_id": "r%02d-%s-%s" % (r, s["name"], arm), "round": r, "shape": s["name"],
                                 "arm": arm, "verdict": {"valid": True}, "workers_cycles_per_req": v,
                                 "freq_ratio": 1.0, "sut_busy": 0.3, "steal_share": 0.0})
        res = {"experiment": exp, "legs": legs, "metadata": {"rounds_complete": 12, "incomplete": False}}
        text, js = UT.tables(res)
        rows = {r["contrast"]: r for r in js["contrasts"]}
        self.assertEqual(len(rows), 3)
        g = rows["Δ(28w) − Δ(1w)"]
        self.assertAlmostEqual(g["t"]["mean"], 20e3, delta=1e3)
        self.assertEqual(g["verdict"], "grows")
        self.assertTrue(js["aa"]["mt-1w"]["ok"])
        self.assertIn("lower bound", text)
        res["metadata"]["incomplete"] = True
        self.assertEqual(UT.tables(res)[1]["contrasts"][0]["verdict"], experiment.INCOMPLETE)

    def test_script(self):
        r = subprocess.run(["bash", "-n", os.path.join(MT, "run-u.sh")], capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        txt = open(os.path.join(MT, "run-u.sh")).read()
        self.assertIn("timeout --foreground --signal=TERM", txt)
        self.assertIn("no override", txt)


class ReviewUTest(unittest.TestCase):
    def ok(self, **over):
        m = {"idle_ok": True, "preflight_ok": True, "pinning_ok": True, "perf_ok": True, "responses": 40000,
             "target_rps": 2000, "sut_rate_2xx": 2001.0, "client_overflow": {}, "client_non2xx": {}, "sut_non2xx": 0,
             "client_headroom": 0.6, "client_workers": 16, "client_pending_total": 16, "sut_foreign_cpus": 0.0,
             "sut_sibling_cpus": 0.0, "envoy_exit": 0, "perf_min_running_pct": 100.0, "envoy_workers": 4,
             "envoy_worker_max_share": 0.25, "envoy_worker_min_share": 0.25}
        m.update(over)
        return validity.verdict(m)

    def test_u1_time_base_before_slow_reads(self):
        src = open(os.path.join(HERE, "epl", "leg.py")).read()
        i_t2 = src.index("                    t2 = time.monotonic()")
        self.assertLess(src.index("o1 = origin_requests(e) if from_origin else None"), i_t2)
        self.assertGreater(src.index('m["numastat"] = numastat_totals(envoy.pid)'), i_t2)
        self.assertGreater(src.index('m["rung_pin_after"] = pin_check('), i_t2)

    def test_u2_origin_reads(self):
        self.assertTrue(self.ok(responses_from="origin", origin_reads_ok=True, responses_raw=40000,
                                responses_admin_raw=40100)["valid"])
        v = self.ok(responses_from="origin", origin_reads_ok=False, responses=0)
        self.assertFalse(v["valid"])
        self.assertTrue(any("stub_status read failed" in r for r in v["reasons"]))
        v = self.ok(responses_from="origin", origin_reads_ok=True, responses_raw=40000, responses_admin_raw=40400)
        self.assertTrue(any("differs from Envoy" in r for r in v["reasons"]))
        # the reject arm has no Envoy count: no consistency check
        self.assertTrue(self.ok(responses_from="origin", origin_reads_ok=True, responses_raw=40000,
                                responses_admin_raw=0)["valid"])

    def test_u3_worker_coverage(self):
        self.assertTrue(self.ok(workers_expected=28, workers_perf_threads=28, workers_cycles_per_req=1.0)["valid"])
        v = self.ok(workers_expected=28, workers_perf_threads=27, workers_cycles_per_req=1.0)
        self.assertTrue(any("27 of 28" in r for r in v["reasons"]))
        self.assertFalse(self.ok(workers_expected=4, workers_perf_threads=4)["valid"])

    def test_u4_reject_absent(self):
        from epl import evidence
        it = {"stat": "http.ingress_http.downstream_rq_2xx", "scope": "leg", "absent": True}
        self.assertTrue(evidence.check_item({"sut_stats_leg_end": {}, "sut_stats_leg_end_ok": True}, it)["ok"])
        self.assertFalse(evidence.check_item({"sut_stats_leg_end": {}}, it)["ok"])
        self.assertFalse(evidence.check_item({}, it)["ok"])
        self.assertFalse(evidence.check_item({"sut_stats_leg_end": {"http.ingress_http.downstream_rq_2xx": 5},
                                              "sut_stats_leg_end_ok": True}, it)["ok"])
        ev = [a for a in MK.configs(box("bench-x86_64"))["u.json"]["arms"] if a["name"] == "stats-reject"][0]["evidence"]
        self.assertIn(it["stat"], [i["stat"] for i in ev if i.get("absent")])


class MicroChecksTest(unittest.TestCase):
    def test_mix_revision_spread_counters(self):
        self.assertIsNone(MICRO.check_mix("24:4:2:9:3:5", 6))
        self.assertIn("6 colon-separated", MICRO.check_mix("24:4", 6))
        cfg = json.load(open(os.path.join(MT, "bench-x86_64", "micro.json")))
        self.assertIsNone(cfg["revision"]["value"])
        with self.assertRaises(SystemExit):
            MICRO.run(cfg, tempfile.mkdtemp(), "/nonexistent")  # no revision: not run
        cfg["revision"]["value"] = "M9"
        good = {"context": {"stats_bench_revision": "M9"},
                "benchmarks": [{"name": "a/threads:4", "run_type": "iteration", "finish_spread": 0.03}]}
        self.assertEqual(MICRO.check_output(good, cfg), [])
        self.assertTrue(MICRO.check_output(dict(good, context={}), cfg))
        bad = dict(good, benchmarks=[{"name": "a/threads:4", "run_type": "iteration", "finish_spread": 0.2}])
        self.assertTrue(any("spread" in p for p in MICRO.check_output(bad, cfg)))
        d = tempfile.mkdtemp()
        json.dump({"arms": {"fix": "x", "fix-relaxed": "y"}, "pairs": [["fix-relaxed", "fix", "all"]],
                   "thread_counters": {"cycles": "cycles_per_op"}}, open(os.path.join(d, "meta.json"), "w"))
        for r in (1, 2):
            for arm in ("fix", "fix-relaxed"):
                json.dump({"benchmarks": [{"name": "bmX/threads:1_median", "run_name": "bmX/threads:1",
                                           "run_type": "aggregate", "aggregate_name": "median", "real_time": 10.0,
                                           "time_unit": "ns", "cycles_per_op": 23.0 if arm == "fix" else 20.0,
                                           "label": "placement=one-socket"}]},
                          open(os.path.join(d, "r%02d-0-x-one-socket-%s.json" % (r, arm)), "w"))
        text, js = MICRO.table(d)
        self.assertIn("Per-thread counters", text)
        self.assertEqual(js["counters"]["bmX/threads:1|fix|cycles"], 23.0)


if __name__ == "__main__":
    unittest.main()
