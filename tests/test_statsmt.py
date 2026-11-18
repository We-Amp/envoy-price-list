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


def _micro(box_name="arm-vm"):
    return json.load(open(os.path.join(MT, box_name, "micro.json")))


def _bench_out(names, cfg, reps=None, bad=None, extra=None):
    """A synthetic benchmark JSON: every name with `reps` passing repetitions and a median."""
    reps = reps or cfg["repetitions"]
    bm = []
    for nm in names:
        raw = nm.replace("/manual_time", "/iterations:1/manual_time") if "threads:" in nm else \
            nm.replace("/manual_time", "/min_time:1.000/manual_time")
        good = {"window_overlap": 0.999, "invol_switches": 0, "min_thread_ops": 2e6, "cycles_per_op": 20.0,
                "instructions_per_op": 9.0, "ns_per_op": 6.0, "fairness": 0.9, "ns_per_sample": 30.0}
        good.update(extra or {})
        for i in range(reps):
            e = dict(good, name=raw, run_name=raw, run_type="iteration")
            if bad and bad[0] == nm and i == 0:
                e.update(bad[1])
            bm.append(e)
        bm.append(dict(good, name=raw + "_median", run_name=raw, run_type="aggregate", aggregate_name="median",
                       label="cpus=0-15 placement=vm"))
    return {"benchmarks": bm}


class MicroConfigTest(unittest.TestCase):
    def test_narrowed_set(self):
        a = _micro("arm-vm")
        self.assertEqual(a["arms"], {"fix": "d2f2238974", "fix-relaxed": "e74e595e3c", "fix-relaxed-p1": "f8bd66d7e7"})
        self.assertEqual(a["pairs"], [["fix-relaxed", "fix", "all"], ["fix-relaxed-p1", "fix-relaxed", "all"]])
        by = {r["binary"]: r for r in a["runs"]}
        self.assertEqual(by["atomic_model_benchmark"]["arms"], ["fix"])
        self.assertEqual(by["atomic_model_benchmark"]["threads"], [1, 4, 15])
        self.assertNotIn("TestFlagShared/", " ".join(x for x in by["atomic_model_benchmark"]["expect"]
                                                    if not x.startswith("bmModelRelaxedTestFlag")))
        self.assertEqual(len(by["atomic_model_benchmark"]["expect"]), 5 * 2 * 3)
        self.assertIn("bmPrimitiveCounterIncShared/manual_time/threads:4", by["stat_update_benchmark"]["expect"])
        self.assertIn("bmGaugeSetPerThreadSpaced/manual_time/threads:15", by["stat_update_benchmark"]["expect"])
        self.assertFalse(any("GaugeIncDec" in x or "RequestMix" in x for x in by["stat_update_benchmark"]["expect"]))
        self.assertEqual(by["histogram_record_benchmark"]["expect"],
                         ["bmHistogramRecordOnly/1/manual_time", "bmHistogramRecordOnly/15/manual_time"])
        self.assertNotIn("server_stats_flush_contended_benchmark", by)
        self.assertEqual([r["threads"] for r in a["smoke"]["runs"]], [[1, 2, 4], [1, 2, 4], [1, 2]])
        x = _micro("x86-vm")
        self.assertEqual([r["threads"] for r in x["runs"]], [[1, 4, 7], [1, 4, 7], [1, 7]])
        z = _micro("bench-x86_64")
        self.assertEqual([r["binary"] for r in z["runs"]], ["atomic_model_benchmark"])  # bare metal: row 1 only
        self.assertEqual(z["runs"][0]["threads"], [1, 4, 19])
        self.assertEqual(z["max_invol_switches"], 0)
        self.assertIsNone(a["max_invol_switches"])
        self.assertNotIn("spread_counter", a)

    def test_placeholders_refused(self):
        c = _micro("arm-vm")
        self.assertFalse(c["pinned"])
        self.assertTrue(all(v is None for x in c["expected_sha256"].values() for v in x.values()))
        for b in ("x86-vm", "bench-x86_64"):  # round 5, from the build record
            c = _micro(b)
            self.assertTrue(c["pinned"])
            self.assertEqual(c["expected_sha256"]["fix"]["atomic_model_benchmark"][:12], "64247742b7b6")
            self.assertEqual(c["expected_sha256"]["fix-relaxed-p1"]["stat_update_benchmark"][:12], "1d70718cb9cf")
        d = tempfile.mkdtemp()
        cfg = _micro("arm-vm")
        for a, bn in MICRO.needed(cfg):
            os.makedirs(os.path.join(d, cfg["arms"][a]), exist_ok=True)
            open(os.path.join(d, cfg["arms"][a], bn), "w").write(a + bn)
        _, probs = MICRO.identity(cfg, d)
        self.assertEqual(len(probs), len(MICRO.needed(cfg)))
        self.assertTrue(all("not pinned" in p for p in probs))
        self.assertEqual(MICRO.identity(cfg, d, require_pins=False)[1], [])  # the smoke runs before the pins
        r = subprocess.run([sys.executable, os.path.join(MT, "micro.py"), "check", os.path.join(MT, "arm-vm", "micro.json"),
                            "--root", d], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("identity FAILED", r.stdout)
        with self.assertRaises(SystemExit):
            MICRO.run(dict(cfg, max_invol_switches=5), os.path.join(d, "out"), d)

    def test_identity_pins(self):
        d = tempfile.mkdtemp()
        cfg = {"arms": {"fix": "c1", "fix-relaxed": "c2"}, "runs": [{"binary": "b1"}], "expected_sha256": {}}
        for c, body in (("c1", b"one"), ("c2", b"two")):
            os.makedirs(os.path.join(d, c))
            open(os.path.join(d, c, "b1"), "wb").write(body)
        h, probs = MICRO.identity(cfg, d)
        self.assertEqual(len(probs), 2)
        cfg["expected_sha256"] = {"fix": {"b1": h["fix/b1"]}, "fix-relaxed": {"b1": h["fix-relaxed/b1"]}}
        self.assertEqual(MICRO.identity(cfg, d)[1], [])
        cfg["expected_sha256"]["fix-relaxed"]["b1"] = h["fix/b1"]
        self.assertTrue(any("pinned" in p for p in MICRO.identity(cfg, d)[1]))
        open(os.path.join(d, "c2", "b1"), "wb").write(b"one")
        self.assertTrue(any("same binary" in p for p in MICRO.identity(cfg, d)[1]))

    def test_sha_list(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "l.txt")
        open(p, "w").write("%s  stat_update_benchmark-fix-0000000000\n" % ("a" * 64))
        with self.assertRaises(SystemExit):
            MK.read_sha_list(p, MK.MICRO_ARMS)
        open(p, "w").write("%s  stat_update_benchmark-fix-relaxed-p1-f8bd66d7e7\n" % ("b" * 64))
        self.assertEqual(MK.read_sha_list(p, MK.MICRO_ARMS), {"fix-relaxed-p1": {"stat_update_benchmark": "b" * 64}})

    def test_filters_match_registered_names(self):
        import re
        for b in ("arm-vm", "x86-vm", "bench-x86_64"):
            c = _micro(b)
            for r in c["runs"] + c["smoke"]["runs"]:
                rx = re.compile(r["filter"])
                for nm in r["expect"]:
                    raw = nm.replace("/manual_time", "/iterations:1/manual_time") if "threads:" in nm else \
                        nm.replace("/manual_time", "/min_time:1.000/manual_time")
                    self.assertTrue(rx.search(raw), (b, raw))
                    self.assertEqual(MICRO.norm_name(raw), nm)
                self.assertFalse(rx.search("bmHistogramRecord/4/1/0/min_time:1.000/manual_time"))
                self.assertFalse(rx.search("bmGaugeIncDecShared/iterations:1/manual_time/threads:4"))

    def test_too_many_threads_refused(self):
        b = box("x86-vm")
        b["micro"]["threads"] = [1, 12]
        with self.assertRaises(SystemExit):
            MK.micro_config(b)


class MicroGateTest(unittest.TestCase):
    def setUp(self):
        self.cfg = dict(_micro("arm-vm"), max_invol_switches=2)
        self.rc = [r for r in self.cfg["runs"] if r["binary"] == "stat_update_benchmark"][0]

    def test_pass_and_env(self):
        self.assertEqual(MICRO.check_output(_bench_out(self.rc["expect"], self.cfg), self.cfg, self.rc), [])
        env = MICRO.run_env(self.cfg, self.rc)
        self.assertEqual(env["STATS_BENCH_THREADS"], "1,4,15")
        self.assertEqual((env["STATS_BENCH_WARMUP"], env["STATS_BENCH_SECONDS"]), ("0.2", "1"))

    def _fails(self, bad, word, extra=None):
        probs = MICRO.check_output(_bench_out(self.rc["expect"], self.cfg, bad=(self.rc["expect"][2], bad),
                                              extra=extra), self.cfg, self.rc)
        self.assertTrue(any(word in p for p in probs), probs)

    def test_each_gate(self):
        self._fails({"window_overlap": 0.98}, "window overlap")
        self._fails({"invol_switches": 3}, "involuntary switches, bound 2")
        self._fails({"invol_switches": -1}, "unavailable")
        self._fails({"min_thread_ops": 19999}, "floor 20000")
        self._fails({"window_overlap": 0.9929}, "outside the common window")
        self._fails({"cycles_per_op": -1}, "cycles_per_op unavailable")
        self._fails({"error_occurred": True, "error_message": "Skipping"}, "Skipping")
        self.assertEqual(MICRO.check_output(_bench_out(self.rc["expect"], self.cfg,
                                                       extra={"window_overlap": 0.9931, "min_thread_ops": 20000}),
                                            self.cfg, self.rc), [])
        # fairness is a result, not a gate
        self.assertEqual(MICRO.check_output(_bench_out(self.rc["expect"], self.cfg, extra={"fairness": 0.2}),
                                            self.cfg, self.rc), [])

    def test_completeness(self):
        probs = MICRO.check_output(_bench_out(self.rc["expect"][:-1], self.cfg), self.cfg, self.rc)
        self.assertTrue(any(self.rc["expect"][-1] in p and "0 of 5" in p for p in probs))
        self.assertTrue(MICRO.check_output(_bench_out(self.rc["expect"], self.cfg, reps=4), self.cfg, self.rc))

    def test_no_pmu_box(self):
        cfg = dict(self.cfg, pmu=False)
        self.assertEqual(MICRO.check_output(_bench_out(self.rc["expect"], cfg, extra={"cycles_per_op": -1,
                                                                                      "instructions_per_op": -1}),
                                            cfg, self.rc), [])

    def test_histogram_gates(self):
        rc = [r for r in self.cfg["runs"] if r["kind"] == "histogram"][0]
        self.assertEqual(MICRO.check_output(_bench_out(rc["expect"], self.cfg, extra={"window_overlap": None}),
                                            self.cfg, rc), [])
        probs = MICRO.check_output(_bench_out(rc["expect"], self.cfg, bad=(rc["expect"][0], {"ns_per_sample": 0})),
                                   self.cfg, rc)
        self.assertTrue(any("ns_per_sample" in p for p in probs))

    def test_run_refuses_without_switch_bound(self):
        with self.assertRaises(SystemExit):
            MICRO.run(_micro("arm-vm"), tempfile.mkdtemp(), "/nonexistent")

    def test_cores(self):
        cores = MICRO.parse_lscpu("# CPU,CORE\n" + "".join("%d,%d\n" % (c, c % 8) for c in range(16)))
        rc = {"placement": "vm", "cpus": "0-7"}
        self.assertEqual(MICRO.check_cores({"runs": [rc]}, cores), [])
        self.assertTrue(MICRO.check_cores({"runs": [dict(rc, cpus="0-8")]}, cores))
        self.assertTrue(MICRO.check_cores({"runs": [dict(rc, cpus="0-16")]}, cores))


class MicroPlanSmokeTableTest(unittest.TestCase):
    def test_plan_dry_run(self):
        cfg = dict(_micro("arm-vm"), rounds=3)
        steps = MICRO.plan(cfg)
        self.assertEqual(len(steps), 3 * (1 + 3 + 3))
        self.assertEqual({a for _, i, a in steps if i == 0}, {"fix"})
        firsts = {MICRO.arm_order(["fix", "fix-relaxed", "fix-relaxed-p1"], r)[0] for r in range(1, 6)}
        self.assertGreaterEqual(len(firsts), 2)
        lines = []
        MICRO.run(cfg, tempfile.mkdtemp(), "/nonexistent", dry_run=True, log=lines.append)
        lines = [x for x in lines if not x.startswith("identity: ")]
        self.assertEqual(len(lines), len(steps))
        self.assertIn("STATS_BENCH_SECONDS=1 ", lines[0])

    def test_smoke_config(self):
        cfg = _micro("arm-vm")
        s = MICRO.smoke_config(cfg)
        self.assertEqual((s["rounds"], s["repetitions"], s["warmup_s"], s["window_s"]), (1, 2, 0.05, 0.2))
        self.assertEqual(MICRO.ops_floor(s), 4000)
        self.assertAlmostEqual(MICRO.max_nonoverlap_s(s), 0.003)
        self.assertEqual(MICRO.ops_floor(dict(s, window_s=0.01)), 1024)
        self.assertAlmostEqual(MICRO.max_nonoverlap_s(cfg), 0.007)
        self.assertEqual([r["binary"] for r in s["runs"]], ["atomic_model_benchmark", "stat_update_benchmark",
                                                           "histogram_record_benchmark"])
        self.assertTrue(all(r["arms"] == ["fix"] for r in s["runs"]))
        self.assertEqual(MICRO.run_env(s, s["runs"][0])["STATS_BENCH_THREADS"], "1,2,4")
        with self.assertRaises(SystemExit):
            MICRO.smoke_config(cfg, "base")

    def test_smoke_per_binary_and_select(self):
        cfg = _micro("arm-vm")
        c2 = MICRO.select_binaries(cfg, ["atomic_model_benchmark", "histogram_record_benchmark"])
        self.assertEqual([r["binary"] for r in c2["runs"]], ["atomic_model_benchmark", "histogram_record_benchmark"])
        self.assertEqual(len(c2["smoke"]["runs"]), 2)
        self.assertEqual({b for _, b in MICRO.needed(c2)}, {"atomic_model_benchmark", "histogram_record_benchmark"})
        with self.assertRaises(SystemExit):
            MICRO.select_binaries(cfg, ["nope"])
        d = tempfile.mkdtemp()
        saved = (MICRO.start, MICRO.finish, MICRO.one_process)

        def fake_start(c, out, root, require_pins, dry_run, log):
            os.makedirs(out, exist_ok=True)
            return {}, {}

        def fake_finish(c, out, root, meta, hashes):
            return dict(meta, sha256_end={}, sha256_unchanged=True)

        def fake_one(c, rc, arm, root, dst, log):
            probs = ["%s: spacing" % rc["expect"][0]] if rc["binary"] == "stat_update_benchmark" else []
            open(dst + ".tmp", "w").write("{}")
            return {"exit": 0, "seconds": 1.0, "problems": probs, "max_invol_switches_seen": 1,
                    "min_distance_bytes": {"x": 704.0}}, {}
        MICRO.start, MICRO.finish, MICRO.one_process = fake_start, fake_finish, fake_one
        try:
            ok, probs, worst, per_bin = MICRO.smoke(cfg, d, "/x", log=lambda *a: None)
        finally:
            MICRO.start, MICRO.finish, MICRO.one_process = saved
        self.assertFalse(ok)
        self.assertEqual(per_bin["atomic_model_benchmark"], [])
        self.assertEqual(per_bin["histogram_record_benchmark"], [])
        self.assertEqual(len(per_bin["stat_update_benchmark"]), 1)
        meta = json.load(open(os.path.join(d, "meta.json")))
        self.assertEqual(meta["smoke_binaries"], {"atomic_model_benchmark": True, "histogram_record_benchmark": True,
                                                  "stat_update_benchmark": False})
        self.assertEqual(worst, 1)

    def test_smoke_fails_loudly_without_binaries(self):
        d = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, os.path.join(MT, "micro.py"), "smoke", os.path.join(MT, "arm-vm", "micro.json"),
                            os.path.join(d, "out"), "--root", os.path.join(d, "none")], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("missing", r.stdout + r.stderr)

    def test_table(self):
        d = tempfile.mkdtemp()
        json.dump({"arms": {"fix": "x", "fix-relaxed": "y"}, "pairs": [["fix-relaxed", "fix", "all"]]},
                  open(os.path.join(d, "meta.json"), "w"))
        cfg = dict(_micro("arm-vm"), repetitions=1)
        for r in (1, 2, 3):
            for arm in ("fix", "fix-relaxed"):
                f = 0.9 if arm == "fix-relaxed" else 1.0
                bm = []
                for nm, cyc in (("bmCounterIncShared/manual_time/threads:4", 100.0 * f * (1 + 0.01 * r)),
                                ("bmCounterIncPerThreadSpaced/manual_time/threads:4", 20.0 * (1 + 0.01 * r)),
                                ("bmModelRelaxedShared/manual_time/threads:4", 80.0 * (1 + 0.01 * r)),
                                ("bmModelCurrentShared/manual_time/threads:4", 100.0 * (1 + 0.01 * r))):
                    o = _bench_out([nm], cfg, extra={"cycles_per_op": cyc, "fairness": 0.5,
                                                     "min_distance_bytes": 512.0 + r})
                    bm.extend(o["benchmarks"])
                json.dump({"benchmarks": bm}, open(os.path.join(d, "r%02d-1-stat_update-vm-%s.json" % (r, arm)), "w"))
        text, js = MICRO.table(d)
        row = [p for p in js["pairs"] if p["metric"] == "cycles_per_op" and p["benchmark"].startswith("bmCounterIncShared")][0]
        self.assertAlmostEqual(row["effect_pct"], -10.0, places=6)
        self.assertTrue(row["descriptive"])
        h1 = [x for x in js["h1"] if x["arm"] == "fix" and x["benchmark"].startswith("bmCounterInc")][0]
        self.assertAlmostEqual(h1["ratio"], 5.0, places=6)
        mo = [x for x in js["model"] if x["arm"] == "fix"][0]
        self.assertAlmostEqual(mo["effect_pct"], -20.0, places=6)
        self.assertIn("Fairness", text)
        self.assertIn("Spacing", text)
        self.assertEqual(js["min_distance_bytes"]["bmCounterIncShared/manual_time/threads:4|vm|fix"], 513.0)
        self.assertEqual(js["fairness"]["bmCounterIncShared/manual_time/threads:4|vm|fix"], 0.5)


if __name__ == "__main__":
    unittest.main()
