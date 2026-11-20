import importlib.util
import json
import math
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
                "instructions_per_op": 9.0, "ns_per_op": 6.0, "fairness": 0.9, "ns_per_sample": 30.0,
                "ops_per_sec": 1.0e8}
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
        self.assertEqual(by["atomic_model_benchmark"]["threads"], [1, 4, 8, 12])
        self.assertNotIn("TestFlagShared/", " ".join(x for x in by["atomic_model_benchmark"]["expect"]
                                                    if not x.startswith("bmModelRelaxedTestFlag")))
        self.assertEqual(len(by["atomic_model_benchmark"]["expect"]), 5 * 2 * 4)
        self.assertIn("bmPrimitiveCounterIncShared/manual_time/threads:4", by["stat_update_benchmark"]["expect"])
        self.assertIn("bmGaugeSetPerThreadSpaced/manual_time/threads:12", by["stat_update_benchmark"]["expect"])
        self.assertFalse(any("GaugeIncDec" in x or "RequestMix" in x for x in by["stat_update_benchmark"]["expect"]))
        self.assertEqual(by["histogram_record_benchmark"]["expect"],
                         ["bmHistogramRecordOnly/1/manual_time", "bmHistogramRecordOnly/12/manual_time"])
        self.assertNotIn("server_stats_flush_contended_benchmark", by)
        self.assertEqual([r["threads"] for r in a["smoke"]["runs"]], [[1, 2, 4, 12], [1, 2, 4, 12], [1, 2, 12]])
        x = _micro("x86-vm")
        self.assertEqual([r["threads"] for r in x["runs"]], [[1, 4, 7], [1, 4, 7], [1, 7]])
        z = _micro("bench-x86_64")
        self.assertEqual([r["binary"] for r in z["runs"]], ["atomic_model_benchmark"])  # bare metal: row 1 only
        self.assertEqual(z["runs"][0]["threads"], [1, 4, 19])
        self.assertEqual(z["smoke"]["runs"][0]["threads"], [1, 2, 4, 19])  # smoke includes the top count
        self.assertEqual([r["threads"] for r in x["smoke"]["runs"]], [[1, 2, 4, 7], [1, 2, 4, 7], [1, 2, 7]])
        self.assertEqual((z["max_invol_switches"], z["invol_switches_per_s"]), (5, 25))
        self.assertEqual(MICRO.invol_limit(z), 25.0)  # 1 s window
        self.assertEqual(MICRO.invol_limit(MICRO.smoke_config(z)), 5.0)  # 0.2 s smoke
        self.assertIn("18:43:40Z", z["invol_bound_record"])
        self.assertEqual(MICRO.invol_limit(MICRO.smoke_config(z), 4), 20.0)
        self.assertEqual(MICRO.invol_limit(z, 19), 475.0)
        for vm in ("x86-vm", "arm-vm"):  # the rule's values on every box, nothing VM-local
            v = _micro(vm)
            self.assertEqual((v["max_invol_switches"], v["invol_switches_per_s"]), (5, 25))
            self.assertEqual(MICRO.invol_limit(v, 12), 300.0)
        self.assertNotIn("spread_counter", a)

    def test_placeholders_refused(self):
        c = _micro("arm-vm")  # round 5b arm64, from the build record
        self.assertTrue(c["pinned"])
        self.assertEqual(c["expected_sha256"]["fix"]["atomic_model_benchmark"][:12], "c70704f22adf")
        self.assertEqual(c["expected_sha256"]["fix"]["stat_update_benchmark"][:12], "9c2618e65488")
        for b in ("x86-vm", "bench-x86_64"):  # round 5, from the build record
            c = _micro(b)
            self.assertTrue(c["pinned"])
            self.assertEqual(c["expected_sha256"]["fix"]["atomic_model_benchmark"][:12], "64247742b7b6")
        self.assertEqual(_micro("x86-vm")["expected_sha256"]["fix-relaxed-p1"]["stat_update_benchmark"][:12],
                         "1d70718cb9cf")
        d = tempfile.mkdtemp()
        cfg = _micro("arm-vm")
        cfg["expected_sha256"] = {a: {b: None for b in x} for a, x in cfg["expected_sha256"].items()}
        cfg["pinned"] = False
        cfgp = os.path.join(d, "unpinned.json")
        json.dump(cfg, open(cfgp, "w"))
        for a, bn in MICRO.needed(cfg):
            os.makedirs(os.path.join(d, cfg["arms"][a]), exist_ok=True)
            open(os.path.join(d, cfg["arms"][a], bn), "w").write(a + bn)
        _, probs = MICRO.identity(cfg, d)
        self.assertEqual(len(probs), len(MICRO.needed(cfg)))
        self.assertTrue(all("not pinned" in p for p in probs))
        self.assertEqual(MICRO.identity(cfg, d, require_pins=False)[1], [])  # the smoke runs before the pins
        r = subprocess.run([sys.executable, os.path.join(MT, "micro.py"), "check", cfgp,
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
        self.cfg = dict(_micro("arm-vm"), max_invol_switches=2, invol_switches_per_s=None)
        self.rc = [r for r in self.cfg["runs"] if r["binary"] == "stat_update_benchmark"][0]

    def test_pass_and_env(self):
        self.assertEqual(MICRO.check_output(_bench_out(self.rc["expect"], self.cfg), self.cfg, self.rc), [])
        env = MICRO.run_env(self.cfg, self.rc)
        self.assertEqual(env["STATS_BENCH_THREADS"], "1,4,8,12")
        self.assertEqual((env["STATS_BENCH_WARMUP"], env["STATS_BENCH_SECONDS"]), ("0.2", "1"))

    def _fails(self, bad, word, extra=None):
        probs = MICRO.check_output(_bench_out(self.rc["expect"], self.cfg, bad=(self.rc["expect"][0], bad),
                                              extra=extra), self.cfg, self.rc)
        self.assertTrue(any(word in p for p in probs), probs)

    def test_each_gate(self):
        self._fails({"window_overlap": 0.98}, "window overlap")
        self._fails({"invol_switches": 3}, "involuntary switches, bound 2")
        bm = dict(self.cfg, max_invol_switches=5, invol_switches_per_s=25)
        one = [n for n in self.rc["expect"] if n.endswith("threads:1")]
        four = [n for n in self.rc["expect"] if n.endswith("threads:4")]
        rc1, rc4 = dict(self.rc, expect=one), dict(self.rc, expect=four)
        self.assertEqual(MICRO.check_output(_bench_out(one, bm, extra={"invol_switches": 25}), bm, rc1), [])
        self.assertTrue(MICRO.check_output(_bench_out(one, bm, extra={"invol_switches": 26}), bm, rc1))
        self.assertEqual(MICRO.check_output(_bench_out(four, bm, extra={"invol_switches": 100}), bm, rc4), [])
        self.assertTrue(MICRO.check_output(_bench_out(four, bm, extra={"invol_switches": 101}), bm, rc4))
        self._fails({"invol_switches": -1}, "unavailable")
        self._fails({"min_thread_ops": 1023}, "floor 1024")
        self._fails({"window_overlap": 0.992}, "outside the common window")  # 8 ms > 7 ms + 3 x 0.128 ms
        # a starved slowest thread (13,824 operations: 18.5 ms per batch) gets 3 batches more
        slow = {"min_thread_ops": 13824}
        self.assertEqual(MICRO.check_output(_bench_out(self.rc["expect"], self.cfg,
                                                       extra=dict(slow, window_overlap=0.95)), self.cfg, self.rc), [])
        self._fails(dict(slow, window_overlap=0.93), "outside the common window")
        self._fails({"cycles_per_op": -1}, "cycles_per_op unavailable")
        self._fails({"error_occurred": True, "error_message": "Skipping"}, "Skipping")
        self.assertEqual(MICRO.check_output(_bench_out(self.rc["expect"], self.cfg,
                                                       extra={"window_overlap": 0.9927, "min_thread_ops": 1024 * 1000}),
                                            self.cfg, self.rc), [])
        # fairness is a result, not a gate
        self.assertEqual(MICRO.check_output(_bench_out(self.rc["expect"], self.cfg, extra={"fairness": 0.2}),
                                            self.cfg, self.rc), [])

    def test_pooled_cycles(self):
        # 12 threads at 3 GHz, 3.74 M operations per second in all: about 9,626 cycles per operation
        m = {"cycles_per_op": 30000.0, "ns_per_op": 10000.0, "ops_per_sec": 3.74e6}
        self.assertAlmostEqual(MICRO.pooled_cycles(m, 12), 12 * 3e9 / 3.74e6)
        self.assertIsNone(MICRO.pooled_cycles(dict(m, cycles_per_op=None), 12))
        self.assertIsNone(MICRO.pooled_cycles(m, None))

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
            MICRO.run(dict(_micro("arm-vm"), max_invol_switches=None), tempfile.mkdtemp(), "/nonexistent")

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
        self.assertEqual(MICRO.ops_floor(s), 1024)
        self.assertAlmostEqual(MICRO.max_nonoverlap_s(s), 0.003)
        self.assertAlmostEqual(MICRO.max_nonoverlap_s(cfg), 0.007)
        self.assertAlmostEqual(MICRO.max_nonoverlap_s(cfg, 256000), 0.007 + 3 * 0.001)
        self.assertEqual([r["binary"] for r in s["runs"]], ["atomic_model_benchmark", "stat_update_benchmark",
                                                           "histogram_record_benchmark"])
        self.assertTrue(all(r["arms"] == ["fix"] for r in s["runs"]))
        self.assertEqual(MICRO.run_env(s, s["runs"][0])["STATS_BENCH_THREADS"], "1,2,4,12")
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
        row = [p for p in js["pairs"] if p["metric"] == "pooled_cycles_per_op" and p["benchmark"].startswith("bmCounterIncShared")][0]
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


CGT = _mod("mt_codegen_table", os.path.join(MT, "codegen_table.py"))


class CodegenTest(unittest.TestCase):
    def test_configs(self):
        c = json.load(open(os.path.join(MT, "arm-vm", "codegen.json")))
        self.assertEqual([a["name"] for a in c["arms"]],
                         ["official", "official-reject", "dev", "dev-reject", "official-A2"])
        by = {a["name"]: a for a in c["arms"]}
        self.assertEqual(by["official"]["binaries"]["aarch64"]["source_sha256"][:12], "b9d6d1e06dd5")
        self.assertEqual(by["dev"]["binaries"]["aarch64"]["source_sha256"][:12], "8c6afaf50a7a")
        self.assertEqual(by["dev-reject"]["settings"], {"stats_reject_all": True})
        self.assertEqual(by["dev-reject"]["binaries"], by["dev"]["binaries"])
        self.assertTrue(any(e.get("absent") for e in by["dev-reject"]["evidence"]))
        self.assertEqual([s["name"] for s in c["shapes"]], ["mt-4w", "mt-12w"])
        self.assertEqual([s["rps"] for s in c["shapes"]], [4000, 12000])
        self.assertEqual((c["rounds"], c["base_arm"], c["primary_metric"]), (20, "official", "workers_cycles_per_req"))
        self.assertTrue(c["box_specific"])
        self.assertEqual(c["cpus"], {"sut": "0-12", "client": "13-14", "origin": "15"})
        f = json.load(open(os.path.join(MT, "arm-vm", "codegen-8w.json")))
        self.assertEqual([(s["name"], s["worker_cpus"]) for s in f["shapes"]], [("mt-4w", "0-3"), ("mt-8w", "0-7")])
        sm = json.load(open(os.path.join(MT, "arm-vm", "smoke-codegen.json")))
        self.assertEqual((sm["rounds"], sm["smoke"], sm["evidence_mode"]), (1, True, "record"))
        e = experiment.load(os.path.join(MT, "arm-vm", "codegen.json"))
        self.assertEqual(experiment.validate(e), [])
        self.assertFalse(os.path.exists(os.path.join(MT, "x86-vm", "codegen.json")))

    def _res(self, dev_price=0.02, aa_noise=0.001, rounds=20):
        import random
        rng = random.Random(5)
        legs = []
        for r in range(1, rounds + 1):
            for s in ("mt-4w", "mt-12w"):
                off = 30e3 * rng.gauss(1, 0.003)
                dev = off * 1.03
                vals = {"official": off, "official-A2": off * rng.gauss(1, aa_noise),
                        "official-reject": off * (1 - 0.05) * rng.gauss(1, 0.001),
                        "dev": dev, "dev-reject": dev * (1 - 0.05 - dev_price) * rng.gauss(1, 0.001)}
                for a, v in vals.items():
                    legs.append({"leg_id": "r%02d-%s-%s" % (r, s, a), "round": r, "shape": s, "arm": a,
                                 "verdict": {"valid": True}, "workers_cycles_per_req": v,
                                 "per_req": {"instructions_u": 1000.0 if a.startswith("official") else 1010.0}})
        exp = json.load(open(os.path.join(MT, "arm-vm", "codegen.json")))
        return {"experiment": exp, "legs": legs, "metadata": {"rounds_complete": rounds, "incomplete": False}}

    def test_table_primary(self):
        d = tempfile.mkdtemp()
        json.dump(self._res(), open(os.path.join(d, "results.json"), "w"))
        text, js = CGT.table(d)
        row = js["rungs"]["mt-12w"]
        self.assertTrue(row["aa_pass"])
        self.assertAlmostEqual(row["primary"]["mean"], 100 * (math.log(1 / 0.93) - math.log(1 / 0.95)), delta=0.2)
        self.assertEqual(row["primary_verdict"], "finding")
        self.assertAlmostEqual(row["direct_confounded"]["mean"], 100 * math.log(1.03), delta=0.01)
        self.assertAlmostEqual(row["instructions_u_dev_over_official"], 1.01)
        self.assertIn("confounded", text)
        self.assertIn("Absolute", text)
        self.assertAlmostEqual(row["absolute"]["mean"], 30e3 * 1.03 * 0.07 - 30e3 * 0.05, delta=150)
        json.dump(self._res(dev_price=0.0), open(os.path.join(d, "results.json"), "w"))
        self.assertTrue(CGT.table(d)[1]["rungs"]["mt-4w"]["primary_verdict"].startswith("no resolved difference"))
        json.dump(self._res(aa_noise=0.03), open(os.path.join(d, "results.json"), "w"))
        self.assertEqual(CGT.table(d)[1]["rungs"]["mt-4w"]["primary_verdict"], "no verdict (A/A did not pass)")
        r = self._res()
        r["metadata"]["incomplete"] = True
        json.dump(r, open(os.path.join(d, "results.json"), "w"))
        self.assertEqual(CGT.table(d)[1]["rungs"]["mt-4w"]["primary_verdict"], experiment.INCOMPLETE)

    def test_script_modes(self):
        txt = open(os.path.join(MT, "run-u.sh")).read()
        self.assertIn("codegen-smoke)", txt)
        self.assertIn('evidence-check "$C/codegen$CG.json"', txt)
        self.assertNotIn("CG=${CG:-}", txt)


CGC = _mod("mt_codegen_check", os.path.join(MT, "codegen_check.py"))


class CodegenCheckTest(unittest.TestCase):
    def test_count_and_style(self):
        lines = ["  4005d0:\tldaxr\tx1, [x0]", "  4005d4:\tstlxr\tw2, x1, [x0]", "  4005d8:\tldaddal\tx1, x2, [x0]",
                 "  4005dc: \tcasal\tx1, x2, [x0]", "  4005e0:\tldr\tx1, [x0]",
                 "  4005e4:\t885ffc01 \tldaxr\tw1, [x0]", "Disassembly of section .text:"]
        c = CGC.count_atomics(lines)
        self.assertEqual((c["exclusive"], c["lse"]), (3, 2))
        self.assertEqual(CGC.style({"exclusive": 90034, "lse": 38}), "llsc-inline")
        self.assertEqual(CGC.style({"exclusive": 224, "lse": 56}), "outline")
        self.assertEqual(CGC.style({"exclusive": 224, "lse": 0}), "unclear")
        self.assertEqual(CGC.style({"exclusive": 5000, "lse": 10}), "unclear")

    def test_config_contrast(self):
        c = json.load(open(os.path.join(MT, "arm-vm", "codegen.json")))
        self.assertEqual(c["contrast"]["expect_style"], {"official": "outline", "dev": "llsc-inline"})
        self.assertFalse(c["measure"].get("stat_ops_probe"))
        sm = json.load(open(os.path.join(MT, "arm-vm", "smoke-codegen.json")))
        self.assertTrue(sm["measure"]["stat_ops_probe"])

    def test_prometheus_stat_ops(self):
        t0 = ("# TYPE envoy_cluster_upstream_rq_total counter\nenvoy_cluster_upstream_rq_total{envoy_cluster_name=\"o\"} 10\n"
              "# TYPE envoy_cluster_upstream_cx_tx_bytes_total counter\nenvoy_cluster_upstream_cx_tx_bytes_total{} 100\n"
              "# TYPE envoy_cluster_upstream_rq_active gauge\nenvoy_cluster_upstream_rq_active{} 1\n"
              "# TYPE envoy_cluster_upstream_rq_time histogram\nenvoy_cluster_upstream_rq_time_bucket{le=\"1\"} 3\n"
              "envoy_cluster_upstream_rq_time_sum{} 7\nenvoy_cluster_upstream_rq_time_count{} 5\n")
        t1 = t0.replace("} 10", "} 30").replace("} 100", "} 9000").replace("_count{} 5", "_count{} 25")
        p0, p1 = leg.parse_prometheus(t0), leg.parse_prometheus(t1)
        so = leg.stat_ops(p0, p1)
        self.assertEqual(so["counter_incs"], 20.0)  # byte counters left out
        self.assertEqual(so["histogram_samples"], 20.0)
        self.assertEqual(len(so["counters_changed"]), 2)

    def _smoke(self, d, cfg, bad=None, dev_incs=20.0, invalid=()):
        legs = []
        for s in cfg["shapes"]:
            for a in cfg["arms"]:
                m = {"leg_id": "r01-%s-%s" % (s["name"], a["name"]), "round": 1, "shape": s["name"], "arm": a["name"],
                     "attempt": 1, "verdict": {"valid": (s["name"], a["name"]) not in invalid,
                                               "reasons": ["client headroom 0.10 below 0.25"]
                                               if (s["name"], a["name"]) in invalid else []},
                     "responses": 10000}
                if a["name"] in ("official", "dev"):
                    m["stat_ops"] = {"counter_incs": 10000 * (dev_incs if a["name"] == "dev" else 20.0),
                                     "histogram_samples": 10000 * 3.0, "counters_changed": ["a", "b"]}
                legs.append(m)
        json.dump({"experiment": cfg, "legs": legs, "metadata": {}}, open(os.path.join(d, "results.json"), "w"))

    def test_smoke_check(self):
        cfg = json.load(open(os.path.join(MT, "arm-vm", "smoke-codegen.json")))
        d = tempfile.mkdtemp()
        self._smoke(d, cfg)
        self.assertTrue(CGC.smoke(cfg, d)["ok"])
        self._smoke(d, cfg, dev_incs=20.5)
        r = CGC.smoke(cfg, d)
        self.assertFalse(r["ok"])
        self.assertFalse(r["capacity_only"])
        self.assertTrue(any("counter_incs_per_req" in p for p in r["problems"]))
        self._smoke(d, cfg, invalid=[("mt-12w", "dev")])
        r = CGC.smoke(cfg, d)
        self.assertFalse(r["ok"])
        self.assertTrue(r["capacity_only"])  # only the top rung: the fallback applies
        self._smoke(d, cfg, invalid=[("mt-4w", "dev")])
        self.assertFalse(CGC.smoke(cfg, d)["capacity_only"])

    def test_script_gates(self):
        txt = open(os.path.join(MT, "run-u.sh")).read()
        self.assertIn('codegen_check.py" atomics', txt)
        self.assertIn("codegen.choice", txt)
        self.assertIn("no passing smoke", txt)


RE = _mod("mt_micro_reeval", os.path.join(MT, "micro_reeval.py"))


class MicroReevalTest(unittest.TestCase):
    def test_post_hoc(self):
        cfg = _micro("arm-vm")
        for k in MK.MICRO_GATES:
            cfg.pop(k)
        cfg.update(RE.OLD_GATES, nonoverlap_batches=0)
        cfg["runs"] = cfg["runs"][1:2]  # stat_update
        rc = cfg["runs"][0]
        d, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        json.dump({"arms": cfg["arms"], "pairs": cfg["pairs"], "config": "x"}, open(os.path.join(d, "meta.json"), "w"))
        starved = {"min_thread_ops": 13824, "window_overlap": 0.95}  # 50 ms outside: old limit 7 ms, new 62.5 ms
        json.dump(_bench_out(rc["expect"], cfg, extra=starved), open(os.path.join(d, "r01-0-stat_update-vm-fix.json.tmp"), "w"))
        json.dump(_bench_out(rc["expect"], cfg), open(os.path.join(d, "r01-0-stat_update-vm-fix-relaxed.json"), "w"))
        json.dump(_bench_out(rc["expect"], cfg, extra=starved),
                  open(os.path.join(d, "r01-0-stat_update-vm-fix-relaxed-p1.json.tmp"), "w"))
        open(os.path.join(d, "runs.jsonl"), "w").write(json.dumps({"tag": "r01-0-stat_update-vm-fix-relaxed-p1",
                                                                   "problems": ["steal 3.00% above 2.0%"]}) + "\n")
        cp = os.path.join(d, "cfg.json")
        json.dump(cfg, open(cp, "w"))
        r = subprocess.run([sys.executable, os.path.join(MT, "micro_reeval.py"), out, "--data", "set", d, cp],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        rep = json.load(open(os.path.join(out, "reeval.json")))
        sm = rep["sets"]["set"]["summary"]
        self.assertEqual((sm["processes"], sm["accepted_before"], sm["accepted_after"]), (3, 1, 2))  # steal stays out
        self.assertIn("POST-HOC", open(os.path.join(out, "reeval.md")).read())
        self.assertIn("POST-HOC", open(os.path.join(out, "set", "micro.md")).read())
        self.assertEqual(sorted(os.listdir(os.path.join(out, "set")))[:2], ["meta.json", "micro.md"])


class MicroLseTest(unittest.TestCase):
    def test_config(self):
        c = _micro("arm-vm")
        lse = json.load(open(os.path.join(MT, "arm-vm", "micro-lse.json")))
        self.assertEqual(lse["arms"], {"fix-lse": "964d72f7a6-lse", "fix-llsc": "964d72f7a6-llsc"})
        self.assertEqual(lse["root"], "~/arm/bins6")
        self.assertEqual(lse["pairs"], [["fix-llsc", "fix-lse", "all"]])
        self.assertEqual([(r["binary"], r["arms"], r["threads"]) for r in lse["runs"]],
                         [("atomic_model_benchmark", ["fix-llsc", "fix-lse"], [1, 4, 8, 12]),
                          ("stat_update_benchmark", ["fix-llsc", "fix-lse"], [1, 4, 8, 12])])
        self.assertTrue(all(12 in r["threads"] for r in lse["smoke"]["runs"]))
        self.assertFalse(lse["pinned"])  # placeholders until the r6 build record is in boxes/sha256
        self.assertEqual(lse["nonoverlap_batches"], 3)
        self.assertEqual(c["name"], "mt-micro-arm-vm")

    def test_sha_list_dir_form(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "l.txt")
        open(p, "w").write("# r6\n%s  964d72f7a6-lse/stat_update_benchmark\n%s  964d72f7a6-llsc/atomic_model_benchmark\n"
                           "%s  other/stat_update_benchmark\n" % ("a" * 64, "b" * 64, "c" * 64))
        got = MK.read_sha_list(p, {"fix-lse": "964d72f7a6-lse", "fix-llsc": "964d72f7a6-llsc"})
        self.assertEqual(got, {"fix-lse": {"stat_update_benchmark": "a" * 64},
                               "fix-llsc": {"atomic_model_benchmark": "b" * 64}})

    def test_label_gate_pooled_and_batch(self):
        lse = dict(json.load(open(os.path.join(MT, "arm-vm", "micro-lse.json"))))
        rc = lse["runs"][1]
        out = _bench_out(rc["expect"], lse, extra={"label": "cpus=0-15 placement=vm clocksource=arch_sys_counter "
                                                            "atomics=lse"})
        self.assertEqual(MICRO.check_output(out, lse, rc, "fix-lse"), [])
        probs = MICRO.check_output(out, lse, rc, "fix-llsc")
        self.assertTrue(any("atomics label lse, expected base" in p for p in probs))
        # the time-batched builds report pooled cycles themselves
        self.assertEqual(MICRO.pooled_cycles({"cycles_per_op": 9000.0, "cycles_per_op_thread_mean": 14000.0,
                                              "ns_per_op": 1.0, "ops_per_sec": 1.0}, 12), 9000.0)
        # a halved batch: the slowest thread's batch time from min_batch_ops
        self.assertAlmostEqual(MICRO.batch_s(lse, 10000, 8), 8 * 1.0 / 10000)
        self.assertAlmostEqual(MICRO.batch_s(lse, 10000), 256 * 1.0 / 10000)


class UHiTest(unittest.TestCase):
    def test_configs(self):
        u = json.load(open(os.path.join(MT, "bench-x86_64", "u-hi.json")))
        self.assertEqual([s["name"] for s in u["shapes"]], ["mt-14w-one", "mt-14w-split", "mt-28w"])
        self.assertEqual([a["name"] for a in u["arms"]], ["base", "stats-reject", "base-A2"])
        self.assertTrue(u["uncalibrated"])
        self.assertEqual((u["rounds"], u["k"]), (15, 16))
        self.assertEqual([s["client_connections_per_worker"] * s["client_concurrency"] // s["workers"]
                          for s in u["shapes"]], [16, 16, 16])
        cal = json.load(open(os.path.join(MT, "bench-x86_64", "cal-u-hi.json")))
        self.assertEqual([a["name"] for a in cal["arms"]], ["base", "stats-reject"])
        c = MK.configs(box("bench-x86_64"), {"bench-x86_64-hi-1800": {"r_star": 2100, "k": 16}})
        self.assertNotIn("uncalibrated", c["u-hi.json"])
        self.assertEqual([s["rps"] for s in c["u-hi.json"]["shapes"]], [29400, 29400, 58800])
        self.assertTrue(c["u.json"]["uncalibrated"])  # run U's own key is separate
        self.assertFalse(os.path.exists(os.path.join(MT, "arm-vm", "u-hi.json")))
        txt = open(os.path.join(MT, "run-u.sh")).read()
        for m in ("hi-calibrate)", "hi-smoke)", "hi-queue)", "HI_STOP_S:-9000"):
            self.assertIn(m, txt)
        self.assertIn("smoke_valid.py", txt)
        self.assertIn('--out "$R/u-hi$HI_TAG"', txt)
        # one rates key per attempt: the keys of the stopped 1,800 attempt and of the 1,500 attempt do not feed the configs
        c18 = MK.configs(box("bench-x86_64"), {"bench-x86_64-hi": {"r_star": 1800, "k": 16}})["u-hi.json"]
        self.assertTrue(c18["uncalibrated"])
        c15 = MK.configs(box("bench-x86_64"), {"bench-x86_64-hi-1500": {"r_star": 1500, "k": 16}})["u-hi.json"]
        self.assertTrue(c15["uncalibrated"])
        self.assertEqual((u["growth"], u["cross_socket"]), ([["28w", "14w-one"]], [["14w-split", "14w-one"]]))

    def test_table_contrasts_and_smoke_valid(self):
        import random
        rng = random.Random(9)
        exp = MK.configs(box("bench-x86_64"), {"bench-x86_64-hi-1800": {"r_star": 1900, "k": 16}})["u-hi.json"]
        legs = []
        price = {"mt-14w-one": 20e3, "mt-14w-split": 26e3, "mt-28w": 30e3}
        for r in range(1, 16):
            for s in exp["shapes"]:
                b = 300e3 * rng.gauss(1, 0.002)
                for arm, v in (("base", b), ("base-A2", b * rng.gauss(1, 0.002)),
                               ("stats-reject", b - price[s["name"]] * rng.gauss(1, 0.01))):
                    legs.append({"leg_id": "r%02d-%s-%s" % (r, s["name"], arm), "round": r, "shape": s["name"],
                                 "arm": arm, "verdict": {"valid": True}, "workers_cycles_per_req": v,
                                 "freq_ratio": 1.0, "sut_busy": 0.5, "steal_share": 0.0})
        text, js = UT.tables({"experiment": exp, "legs": legs, "metadata": {"rounds_complete": 15, "incomplete": False}})
        names = [r["contrast"] for r in js["contrasts"]]
        self.assertEqual(names, ["Δ(28w) − Δ(14w-one)", "Δ(14w-split) − Δ(14w-one)"])
        self.assertNotIn("1w)", " ".join(names).replace("14w", ""))
        SV = _mod("mt_smoke_valid", os.path.join(MT, "smoke_valid.py"))
        sm = MK.configs(box("bench-x86_64"), {"bench-x86_64-hi-1800": {"r_star": 1900, "k": 16}})["smoke-u-hi.json"]
        ok = [{"shape": s["name"], "arm": a["name"], "round": 1, "verdict": {"valid": True}}
              for s in sm["shapes"] for a in sm["arms"]]
        self.assertEqual(SV.check(sm, {"legs": ok}), [])
        bad = ok[:-1] + [dict(ok[-1], verdict={"valid": False, "reasons": ["client headroom 0.12 below 0.25"]})]
        self.assertTrue(any("client headroom" in p for p in SV.check(sm, {"legs": bad})))
        self.assertTrue(any(p.startswith("missing") for p in SV.check(sm, {"legs": ok[:-1]})))


class StatsAccessLogSettingTest(unittest.TestCase):
    def hcm(self, settings):
        b = envoy_config.bootstrap([{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 16}],
                                   dict({"listener_port": 10110, "admin_port": 9921}, **settings), 8092)
        return b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]

    def test_default_has_no_access_log(self):
        self.assertNotIn("access_log", self.hcm({}))
        self.assertIn("stats_access_log", envoy_config.SETTINGS)
        # every arm of the existing runs renders without the logger
        for fn in ("u.json", "u-hi.json", "u-hitm.json", "smoke-u.json"):
            exp = experiment.load(os.path.join(MT, "bench-x86_64", fn))
            for a in exp["arms"]:
                t = envoy_config.bootstrap_text(exp["shapes"], experiment.arm_envoy(exp, a, "/r"), 8092)
                self.assertNotIn("access_log", t)
                self.assertNotIn("dose", t)

    def test_rendered_shape(self):
        al = self.hcm({"stats_access_log": {"counters": 3, "tag": "%DOWNSTREAM_REMOTE_PORT%"}})["access_log"]
        self.assertEqual(al, [{"name": "envoy.access_loggers.stats", "typed_config": {
            "@type": "type.googleapis.com/envoy.extensions.access_loggers.stats.v3.Config",
            "stats_scope": {"prefix": "dose"},
            "counters": [{"stat": {"name": n, "tags": [{"name": "port", "value_format": "%DOWNSTREAM_REMOTE_PORT%"}]},
                          "value_fixed": 1} for n in ("c000", "c001", "c002")]}}])
        tc = al[0]["typed_config"]
        # exactly one of stat_prefix and stats_scope (the factory throws otherwise); no limit, no eviction
        self.assertNotIn("stat_prefix", tc)
        self.assertEqual(tc["stats_scope"], {"prefix": "dose"})
        for c in tc["counters"]:
            self.assertNotIn("value_format", c)  # value_fixed and value_format together are rejected
        # the two arms differ in the tag value only, and both values have the same length in the name
        own = self.hcm({"stats_access_log": {"counters": 64, "tag": "%DOWNSTREAM_REMOTE_PORT%"}})
        sh = self.hcm({"stats_access_log": {"counters": 64, "tag": "%DOWNSTREAM_LOCAL_PORT%"}})
        self.assertEqual(json.loads(json.dumps(own).replace("REMOTE", "LOCAL")), sh)
        self.assertEqual(len(own["access_log"][0]["typed_config"]["counters"]), 64)
        # beside a file access log, the stats logger is a second entry
        both = self.hcm({"access_log": {"path": "/r/a.log"}, "stats_access_log": {
            "counters": 1, "tag": "%DOWNSTREAM_LOCAL_PORT%"}})["access_log"]
        self.assertEqual([x["name"] for x in both], ["envoy.access_loggers.file", "envoy.access_loggers.stats"])

    def test_bad_setting(self):
        for bad in ({"counters": 0, "tag": "%DOWNSTREAM_LOCAL_PORT%"}, {"counters": 64},
                    {"counters": 64, "tag": "%REQ(X)%"}, {"counters": "64", "tag": "%DOWNSTREAM_LOCAL_PORT%"},
                    {"counters": True, "tag": "%DOWNSTREAM_LOCAL_PORT%"},
                    {"counters": 2000, "tag": "%DOWNSTREAM_LOCAL_PORT%"},
                    {"counters": 64, "tag": "%DOWNSTREAM_LOCAL_PORT%", "max_counters": 10}):
            with self.assertRaises(ValueError, msg=bad):
                envoy_config.stats_access_log(bad)


class DoseLegTest(unittest.TestCase):
    def test_parse_and_record(self):
        body = ("dose.c000.port.10110: 5\ndose.c001.port.10110: 7\nhttp.ingress_http.downstream_rq_2xx: 9\n"
                "dose.h: P0(nan,0) P25(nan,0)\ndosex.c: 1\nhttp.ingress_http.downstream_rq_completed: 40\n\n")
        self.assertEqual(leg.parse_stat_count(body, "dose."), (2, 12, 40))
        self.assertEqual(leg.parse_stat_count("", "dose."), (0, 0, None))
        a = {"n": 448, "sum": 1000, "requests": 100, "read_s": 0.1}
        b = {"n": 512, "sum": 65000, "requests": 1100, "read_s": 0.2}
        r = leg.stat_count_record("dose.", a, b, 0.31)
        self.assertEqual((r["start_n"], r["end_n"], r["new_in_window"], r["sum_delta"]), (448, 512, 64, 64000))
        # the sum per request uses the request counter of the same two reads
        self.assertEqual((r["requests_delta"], r["sum_per_request"], r["pre_window_s"]), (1000, 64.0, 0.31))
        # an arm that rejects every stat has no request counter: no ratio, never a division by zero
        r = leg.stat_count_record("dose.", dict(a, requests=None, n=0, sum=0), dict(b, requests=None, n=0, sum=0))
        self.assertEqual((r["start_n"], r["sum_per_request"]), (0, None))
        self.assertIsNone(leg.stat_count_record("dose.", a, dict(b, requests=100))["sum_per_request"])

    def test_admin_reads(self):
        from unittest import mock
        seen = []

        def get(port, path, timeout=5.0):
            seen.append((path, timeout))
            return 200, "dose.c000.port.10110: 3\nother: 1\nhttp.ingress_http.downstream_rq_completed: 8\n"
        with mock.patch.object(leg, "admin_get", get):
            import urllib.parse
            sc = leg.stat_count(9921, "dose.", 30.0)
            self.assertEqual((sc["n"], sc["sum"], sc["requests"]), (1, 3, 8))
            self.assertEqual(seen[-1][1], 30.0)
            self.assertTrue(seen[-1][0].startswith("/stats?type=Counters&filter="))
            self.assertEqual(urllib.parse.unquote(seen[-1][0].split("filter=", 1)[1]),
                             "^(dose\\.|http\\.ingress_http\\.downstream_rq_completed$)")
            q = leg.admin_stats(9921, 30.0, "^dose\\.c000\\.port\\.10110$")
            self.assertEqual(q["dose.c000.port.10110"], 3)
            flt = urllib.parse.unquote(seen[-1][0].split("filter=", 1)[1])
            self.assertEqual(flt, leg.STAT_FILTER + "|^dose\\.c000\\.port\\.10110$")
            leg.admin_stats(9921)
            self.assertEqual(urllib.parse.unquote(seen[-1][0].split("filter=", 1)[1]), leg.STAT_FILTER)  # unchanged
        with mock.patch.object(leg, "admin_get", lambda *a, **k: (503, "")):
            with self.assertRaises(RuntimeError):  # a failed read is an invalid leg, never zero stats
                leg.stat_count(9921, "dose.")

    def test_reads_outside_the_time_base(self):
        src = open(os.path.join(HERE, "epl", "leg.py")).read()
        i_q0 = src.index("                    t_q0 = time.monotonic()")
        i_t2 = src.index("                    t2 = time.monotonic()")
        self.assertLess(src.index("sc0 = stat_count(ecfg[\"admin_port\"], scp, adm_t) if scp else None"), i_q0)
        self.assertGreater(src.index('m["stat_count"] = stat_count_record('), i_t2)
        self.assertEqual(src.count("admin_stats(ecfg[\"admin_port\"], adm_t, sfx)"), 3)  # q0, q1, leg end

    def test_stat_ops_apart(self):
        p0 = {("counter", 'envoy_dose_c000{port="40000"}'): 10.0, ("counter", "envoy_http_rq_total"): 5.0}
        p1 = {("counter", 'envoy_dose_c000{port="40000"}'): 110.0, ("counter", 'envoy_dose_c001{port="40000"}'): 100.0,
              ("counter", "envoy_http_rq_total"): 105.0}
        self.assertEqual(leg.prometheus_prefix("dose."), "envoy_dose_")
        r = leg.stat_ops(p0, p1, "envoy_dose_")
        self.assertEqual((r["counter_incs"], r["counters_changed"]), (100.0, ["envoy_http_rq_total"]))
        self.assertEqual((r["apart_incs"], r["apart_changed"]), (200.0, 2))
        r = leg.stat_ops(p0, p1)
        self.assertEqual(r["counter_incs"], 300.0)
        self.assertNotIn("apart_incs", r)


DOSE_RATES = {"bench-x86_64-dose-1": {"counters": 128}}


class DoseConfigTest(unittest.TestCase):
    def test_bad_setting_in_a_config(self):
        raw = json.load(open(os.path.join(MT, "bench-x86_64", "dose.json")))
        raw["arms"][0]["settings"]["stats_access_log"]["tag"] = "%REQ(X)%"
        d = tempfile.mkdtemp()
        json.dump(raw, open(os.path.join(d, "d.json"), "w"))
        errs = experiment.validate(experiment.load(os.path.join(d, "d.json")), allow_short=True)
        self.assertTrue(any("stats_access_log.tag" in e for e in errs), errs)

    def test_names_agree(self):
        self.assertEqual((MK.DOSE_SCOPE, MK.DOSE_TAG), (envoy_config.STATS_LOG_SCOPE, envoy_config.STATS_LOG_TAG))
        self.assertEqual(sorted(MK.DOSE_TAG_VALUES.values()), sorted(envoy_config.STATS_LOG_TAG_VALUES))
        self.assertEqual(MK.dose_shared_counter(10110), envoy_config.stats_access_log_flat(0, 10110))
        self.assertEqual(MK.dose_shared_counter(10110), "dose.c000.port.10110")
        self.assertEqual(envoy_config.stats_access_log_names(3), ["c000", "c001", "c002"])

    def test_box_and_existing_runs(self):
        b = box("bench-x86_64")
        self.assertNotIn("7w-one", [r["name"] for r in b["rungs"]])  # run U's rung set is unchanged
        c = MK.configs(b)
        self.assertEqual([s["name"] for s in c["u.json"]["shapes"]],
                         ["mt-1w", "mt-4w", "mt-14w-one", "mt-14w-split", "mt-28w"])
        for fn in ("u.json", "u-hi.json", "smoke-u.json", "u-hitm.json", "cal-u-hi.json"):
            self.assertNotIn("stat_count_prefix", c[fn]["measure"], fn)
            self.assertNotIn("dose", c[fn], fn)
        for other in ("arm-vm", "x86-vm"):
            self.assertFalse([fn for fn in MK.configs(box(other)) if "dose" in fn])
        self.assertIn(":u", b["dose"]["hitm_events"])
        self.assertIn(b["dose"]["hitm_events"], portability.box_literals(b))
        ev = b["dose"]["hitm_events"].split(",")
        self.assertEqual(len([e for e in ev if e.startswith("mem_load")]), 3)
        self.assertTrue(all(e.endswith(":u") for e in ev if e.startswith("mem_load")))

    def test_uncalibrated_without_k(self):
        c = MK.configs(box("bench-x86_64"))
        for fn in ("dose.json", "smoke-dose.json", "dose-evidence.json"):
            self.assertTrue(c[fn].get("uncalibrated"), fn)
            self.assertTrue(json.load(open(os.path.join(MT, "bench-x86_64", fn))).get("uncalibrated"), fn)
        self.assertNotIn("uncalibrated", c["dose-pilot.json"])  # the pilot runs every K of the choice list
        # another attempt's key, or run U's keys, do not calibrate the dose run
        for rates in ({"bench-x86_64-dose": {"counters": 128}}, {"bench-x86_64": {"r_star": 1000, "k": 16}},
                      {"bench-x86_64-hi-1800": {"r_star": 1800, "k": 16}}):
            self.assertTrue(MK.configs(box("bench-x86_64"), rates)["dose.json"].get("uncalibrated"), rates)
        with self.assertRaises(SystemExit):
            MK.configs(box("bench-x86_64"), {"bench-x86_64-dose-1": {"counters": 100}})
        # `epl run` refuses an uncalibrated config
        r = subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "run",
                            os.path.join(MT, "bench-x86_64", "smoke-dose.json"), "--dry-run", "--allow-short",
                            "--out", tempfile.mkdtemp()], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("uncalibrated", r.stderr + r.stdout)

    def test_calibrated(self):
        for K in (64, 128, 256):
            c = MK.configs(box("bench-x86_64"), {"bench-x86_64-dose-1": {"counters": K}})
            u = c["dose.json"]
            self.assertNotIn("uncalibrated", u)
            self.assertEqual([a["name"] for a in u["arms"]], ["own-%d" % K, "shared-%d" % K, "own-%d-A2" % K])
            self.assertEqual(u["base_arm"], "own-%d" % K)
            tags = [a["settings"]["stats_access_log"] for a in u["arms"]]
            self.assertEqual(tags, [{"counters": K, "tag": "%DOWNSTREAM_REMOTE_PORT%"},
                                    {"counters": K, "tag": "%DOWNSTREAM_LOCAL_PORT%"},
                                    {"counters": K, "tag": "%DOWNSTREAM_REMOTE_PORT%"}])
            self.assertEqual(u["arms"][0]["evidence"], u["arms"][2]["evidence"])  # the A/A arm is a copy
            self.assertEqual(u["dose"]["counters"], K)
            self.assertEqual((u["dose"]["reference"], u["dose"]["shared"], u["dose"]["aa"]),
                             ("own-%d" % K, "shared-%d" % K, ["own-%d-A2" % K, "own-%d" % K]))
            self.assertNotIn("uncalibrated", c["smoke-dose.json"])
            self.assertEqual(c["smoke-dose.json"]["dose"], u["dose"])  # dose-check compares the two
            self.assertEqual([a["name"] for a in c["dose-evidence.json"]["arms"]],
                             ["base", "stats-reject", "own-%d" % K, "shared-%d" % K])
            self.assertTrue(c["u.json"]["uncalibrated"])  # run U's key is separate
        # the same configs whatever K is chosen
        self.assertEqual(MK.configs(box("bench-x86_64"), DOSE_RATES)["dose-pilot.json"],
                         MK.configs(box("bench-x86_64"))["dose-pilot.json"])

    def test_cells(self):
        u = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
        got = [(s["cell"], s["name"], s["workers"], s["worker_cpus"], s["rps"], s["client_concurrency"],
                s["client_connections_per_worker"]) for s in u["shapes"]]
        self.assertEqual(got, [("A", "mt-14w-one", 14, "0-13", 21000, 14, 16),
                               ("B", "mt-14w-split", 14, "0-6,20-26", 21000, 14, 16),
                               ("C", "mt-7w-one", 7, "0-6", 21000, 14, 8)])
        for s in u["shapes"]:
            self.assertEqual(s["client_concurrency"] * s["client_connections_per_worker"], 16 * s["workers"])
            self.assertEqual((s["main_cpu"], s["admin_timeout_s"], s["lead_in_s"]), (19, 30, 3))
        self.assertEqual([(c["cell"], c["rate_per_worker"], c["role"]) for c in u["dose"]["cells"]],
                         [("A", 1500, "reference"), ("B", 1500, "socket"), ("C", 3000, "load")])
        self.assertEqual((u["dose"]["socket"], u["dose"]["load"]), (["B", "A"], ["C", "A"]))
        self.assertEqual((u["rounds"], u["rounds_max"], u["adaptive"], u["order"], u["shape_order"]),
                         (15, 15, False, "latin", "latin"))
        self.assertEqual(u["primary_metric"], "workers_cycles_per_req")
        self.assertEqual(u["measure"]["stat_count_prefix"], "dose.")
        self.assertEqual(u["measure"]["stat_filter_extra"], "^dose\\.c000\\.port\\.10110$")
        self.assertEqual(u["measure"]["perf_events"], box("bench-x86_64")["perf_events"])
        # the same 20 s window as run U; the client runs longer, for the admin reads before the window
        self.assertEqual((u["measure"]["window_s"], u["client"]["duration_s"]), (20, 30))
        self.assertEqual(MK.configs(box("bench-x86_64"))["u-hi.json"]["client"]["duration_s"], 25)
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "dose.json"))
        self.assertEqual(experiment.validate(exp), [])
        self.assertEqual(len(experiment.schedule(exp)), 135)  # 3 cells x 3 arms x 15 rounds
        firsts = {experiment.shape_order(exp, r)[0]["name"] for r in range(1, 4)}
        self.assertEqual(len(firsts), 3)
        for a in exp["arms"]:
            b = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, a, "/r"), 8092)
            self.assertEqual(envoy_config.audit_mt_s(b), [], a["name"])

    def test_pilot_smoke_evidence_configs(self):
        c = MK.configs(box("bench-x86_64"), DOSE_RATES)
        p = c["dose-pilot.json"]
        self.assertEqual([a["name"] for a in p["arms"]],
                         ["base", "own-64", "shared-64", "own-128", "shared-128", "own-256", "shared-256"])
        self.assertEqual([s["cell"] for s in p["shapes"]], ["A", "C"])
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "dose-pilot.json"))
        self.assertEqual(len(experiment.schedule(exp)), 14)  # within about 18 legs
        self.assertTrue(p["smoke"])
        self.assertEqual(p["evidence_mode"], "record")
        self.assertEqual(p["measure"]["perf_events"], box("bench-x86_64")["dose"]["hitm_events"])
        self.assertTrue(p["measure"]["stat_ops_probe"] and p["measure"]["per_thread"])
        self.assertEqual(p["dose"]["pilot_rule"], {"cell": "A", "cycles_per_transfer": 100, "min_share": 0.025,
                                                   "h_expected": [1.0, 1.4], "instructions_tol": 0.005})
        sm = c["smoke-dose.json"]
        self.assertEqual((sm["rounds"], sm["smoke"], sm["evidence_mode"]), (1, True, "record"))
        self.assertEqual(sm["arms"], c["dose.json"]["arms"])
        ev = c["dose-evidence.json"]
        self.assertEqual((ev["rounds"], ev["base_arm"]), (4, "base"))
        self.assertEqual(len(experiment.schedule(experiment.load(os.path.join(MT, "bench-x86_64",
                                                                             "dose-evidence.json")))), 48)
        self.assertEqual(ev["measure"]["perf_events"], box("bench-x86_64")["dose"]["hitm_events"])
        self.assertTrue(ev["measure"]["stat_ops_probe"])
        self.assertEqual(experiment.validate(experiment.load(os.path.join(MT, "bench-x86_64", "dose-evidence.json")),
                                             allow_short=True), [])

    def leg(self, arm, shape="mt-14w-one", **sc):
        m = {"shape": shape, "arm": arm, "responses_raw": 420000,
             "sut_stats_window": {"http.ingress_http.downstream_rq_2xx": 420000}, "sut_stats_window_ok": True,
             "stat_count": dict({"start_n": 128, "end_n": 128, "new_in_window": 0, "sum_per_request": 128.4}, **sc)}
        return m

    def test_evidence_items(self):
        from epl import evidence
        u = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
        arms = {a["name"]: a for a in u["arms"]}
        for a in u["arms"]:
            self.assertEqual(evidence.validate_items(a["evidence"], list(arms)), [], a["name"])
        dump = lambda tag: {"x": [{"value_format": tag}] * 128}  # noqa: E731
        sh, own = arms["shared-128"]["evidence"], arms["own-128"]["evidence"]
        good = self.leg("shared-128")
        good["sut_stats_window"]["dose.c000.port.10110"] = 420100
        self.assertTrue(evidence.evaluate(good, sh, dump("%DOWNSTREAM_LOCAL_PORT%"))["ok"])
        # the other arm's tag, a counter set that grew, a missing or slow shared counter, no stat count
        self.assertFalse(evidence.evaluate(good, sh, dump("%DOWNSTREAM_REMOTE_PORT%"))["ok"])
        self.assertFalse(evidence.evaluate(dict(good, stat_count=dict(good["stat_count"], end_n=129)), sh,
                                           dump("%DOWNSTREAM_LOCAL_PORT%"))["ok"])
        half = dict(good, sut_stats_window=dict(good["sut_stats_window"], **{"dose.c000.port.10110": 210000}))
        self.assertFalse(evidence.evaluate(half, sh, dump("%DOWNSTREAM_LOCAL_PORT%"))["ok"])
        self.assertFalse(evidence.evaluate(self.leg("shared-128"), sh, dump("%DOWNSTREAM_LOCAL_PORT%"))["ok"])
        none = dict(good)
        none.pop("stat_count")
        self.assertFalse(evidence.evaluate(none, sh, dump("%DOWNSTREAM_LOCAL_PORT%"))["ok"])
        # own: K per connection (224 connections at 14 workers, 112 at 7), with or without the warm-up client's
        rd = dump("%DOWNSTREAM_REMOTE_PORT%")
        for shape, conns in (("mt-14w-one", 224), ("mt-14w-split", 224), ("mt-7w-one", 112)):
            for sets in (1, 2):
                n = sets * 128 * conns
                self.assertTrue(evidence.evaluate(self.leg("own-128", shape, start_n=n, end_n=n), own, rd)["ok"],
                                (shape, sets))
            n = 128 * conns
            # fewer sets than connections; a reconnect inside the window; a shared object; a scope
            # limit (null counters add nothing); the 7-worker count at a 14-worker cell
            self.assertFalse(evidence.evaluate(self.leg("own-128", shape, start_n=n - 128, end_n=n - 128), own, rd)["ok"])
            r = evidence.evaluate(self.leg("own-128", shape, start_n=n, end_n=n + 128, new_in_window=128), own, rd)
            self.assertTrue(any("reconnect" in f for f in r["failed"]), r["failed"])
            shared_obj = self.leg("own-128", shape, start_n=n, end_n=n)
            shared_obj["sut_stats_window"]["dose.c000.port.10110"] = 5
            self.assertFalse(evidence.evaluate(shared_obj, own, rd)["ok"])
            self.assertFalse(evidence.evaluate(self.leg("own-128", shape, start_n=n, end_n=n, sum_per_request=64.0),
                                               own, rd)["ok"])
        self.assertFalse(evidence.evaluate(self.leg("own-128", "mt-14w-one", start_n=128 * 112 - 128, end_n=1), own,
                                           rd)["ok"])
        # the evidence legs' base arm: no dose counters at all
        base = [a for a in MK.configs(box("bench-x86_64"), DOSE_RATES)["dose-evidence.json"]["arms"]
                if a["name"] == "base"][0]["evidence"]
        self.assertIn({"stat": "stat_count.start_n", "scope": "field", "equals": 0, "tol_abs": 0,
                       "label": "no dose counters"}, base)


HITM_U = ("mem_load_uops_l3_hit_retired.xsnp_hitm:u", "mem_load_uops_l3_miss_retired.remote_hitm:u")


def _dose_run(rho, rounds=15, aa_noise=0.003, ins_shared=200.2e3, seed=5):
    """A synthetic dose run: per cell (shape name) the true ln(shared / own)."""
    import random
    rng = random.Random(seed)
    exp = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
    legs = []
    for r in range(1, rounds + 1):
        for s in exp["shapes"]:
            b = 540e3 * rng.gauss(1, 0.004)
            for arm, v, ins in (("own-128", b, 200e3), ("own-128-A2", b * rng.gauss(1, aa_noise), 200e3),
                                ("shared-128", b * math.exp(rho[s["name"]]) * rng.gauss(1, 0.003), ins_shared)):
                legs.append({"leg_id": "r%02d-%s-%s" % (r, s["name"], arm), "round": r, "shape": s["name"], "arm": arm,
                             "verdict": {"valid": True}, "workers_cycles_per_req": v,
                             "per_req": {"instructions_u": ins}, "sut_busy": 0.4})
    return {"experiment": exp, "legs": legs, "metadata": {"rounds_complete": rounds, "incomplete": False}}


def _dose_evidence(h=1.2, events=HITM_U, seed=6):
    import random
    rng = random.Random(seed)
    exp = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose-evidence.json"]
    per = {"base": 7.0, "stats-reject": 0.5, "own-128": 8.0, "shared-128": 8.0 + h * 128}
    legs = []
    for r in range(1, 5):
        for s in exp["shapes"]:
            for arm, x in per.items():
                x = x * rng.gauss(1, 0.02)
                legs.append({"leg_id": "e", "round": r, "shape": s["name"], "arm": arm, "verdict": {"valid": True},
                             "workers_cycles_per_req": 540e3, "sut_busy": 0.68 if "7w" in s["name"] else 0.36,
                             "responses": 420000,
                             "stat_ops": {"counter_incs": 25 * 420000, "histogram_samples": 4 * 420000,
                                          "counters_changed": []},
                             "per_req": {"events": {events[0]: 0.7 * x, events[1]: 0.3 * x}}})
    return {"experiment": exp, "legs": legs, "metadata": {"rounds_complete": 4, "incomplete": False}}


RHO = {"mt-14w-one": 0.02, "mt-14w-split": 0.05, "mt-7w-one": 0.022}


class DoseTableTest(unittest.TestCase):
    def rows(self, res, ev=None):
        text, js = UT.render(res, None, ev)
        return text, js, {r["id"]: r for r in js["statements"]}

    def test_widened(self):
        xs = [1.0, 2.0, 3.0, 2.0, 2.0]
        se = (sum((x - 2.0) ** 2 for x in xs) / 4) ** 0.5 / 5 ** 0.5
        w = UT.widened(xs)
        self.assertAlmostEqual(w["hi"] - w["mean"], 1.96 * math.sqrt(se ** 2 + 0.34 ** 2))
        w2 = UT.widened(xs, terms=2)
        self.assertAlmostEqual(w2["mean"] - w2["lo"], 1.96 * math.sqrt(se ** 2 + 2 * 0.34 ** 2))
        self.assertAlmostEqual(w["p"], math.erfc(2.0 / math.sqrt(se ** 2 + 0.34 ** 2) / math.sqrt(2)))
        # with no spread at all the interval is still +/- 1.96 x 0.34
        self.assertAlmostEqual(UT.widened([1.0, 1.0, 1.0])["lo"], 1.0 - 1.96 * 0.34)
        self.assertEqual((UT.DOSE_SYS_PCT, UT.DOSE_Z, UT.AA_LIMIT_PCT, UT.DOSE_MIN_EFFECT_PCT,
                          UT.DOSE_INSTR_TOL_PCT, UT.DOSE_HITM_SHARE), (0.34, 1.96, 1.0, 1.0, 0.5, 0.5))

    def test_findings_and_line_transfer(self):
        text, js, st = self.rows(_dose_run(RHO), _dose_evidence())
        self.assertEqual(list(st), ["S1", "S2", "S3", "S4", "S5"])
        self.assertIn("Holm over 5", text)
        for i, (cell, rho) in enumerate((("A", 2.0), ("B", 5.0), ("C", 2.2))):
            r = st["S%d" % (i + 1)]
            self.assertEqual((r["kind"], r["cell"]), ("cell", cell))
            self.assertAlmostEqual(r["w"]["mean"], rho, delta=0.4)
            self.assertEqual(r["verdict"], "finding: line transfer")
            self.assertTrue(js["cells"][cell]["aa"]["ok"])
        self.assertEqual((st["S4"]["kind"], st["S4"]["cells"]), ("socket", ["B", "A"]))
        self.assertAlmostEqual(st["S4"]["w"]["mean"], 3.0, delta=0.5)
        self.assertEqual(st["S4"]["verdict"], "resolved: higher across sockets")
        self.assertIn("+2 to +4 points", text)
        self.assertEqual((st["S5"]["kind"], st["S5"]["cells"]), ("load", ["C", "A"]))
        self.assertTrue(st["S5"]["verdict"].startswith("not resolved"))
        # S4 and S5 are paired by round and carry two widening terms
        ra, rb = js["cells"]["A"]["rho_rounds"], js["cells"]["B"]["rho_rounds"]
        d = [rb[r] - ra[r] for r in sorted(ra)]
        self.assertAlmostEqual(st["S4"]["w"]["hi"], UT.widened(d, terms=2)["hi"])
        self.assertAlmostEqual(st["S1"]["w"]["hi"], UT.widened(list(ra.values()))["hi"])
        # Holm over the five statements
        hp = UT.stats.holm([st[k]["w"]["p"] for k in st])
        self.assertEqual([st[k]["holm_p"] for k in st], hp)
        # cycles per shared update: about ln-ratio x cycles / K
        self.assertAlmostEqual(js["cells"]["A"]["price"]["mean"], 540e3 * (math.exp(0.02) - 1) / 128, delta=8)
        # either spelling of the HITM events
        _, _, st2 = self.rows(_dose_run(RHO), _dose_evidence(events=UT.HITM))
        self.assertEqual(st2["S1"]["verdict"], "finding: line transfer")

    def test_not_called_line_transfer(self):
        res = _dose_run(RHO)
        _, _, st = self.rows(res)  # no evidence legs
        self.assertTrue(st["S1"]["verdict"].startswith("finding, not called line transfer"))
        self.assertIn("no HITM:u evidence", st["S1"]["verdict"])
        _, _, st = self.rows(res, _dose_evidence(h=0.3))  # 38 HITM per request, under 0.5 x 128
        self.assertIn("under 0.5 x K = 64", st["S1"]["verdict"])
        self.assertFalse(st["S1"]["line_transfer"])
        _, _, st = self.rows(_dose_run(RHO, ins_shared=202e3), _dose_evidence())  # 1% more instructions
        self.assertIn("instructions:u per request differ", st["S2"]["verdict"])
        self.assertTrue(st["S2"]["verdict"].startswith("finding, not called line transfer"))

    def test_bounds(self):
        # under 1%: a bound with the widened interval's upper end, never "no effect"
        text, js, st = self.rows(_dose_run({"mt-14w-one": 0.004, "mt-14w-split": 0.02, "mt-7w-one": 0.0}),
                                 _dose_evidence())
        r = st["S1"]
        self.assertEqual(r["verdict"].split(" (")[0], "bound: rho_A <= %+.2f%%" % r["w"]["hi"])
        self.assertIn("under 1%", r["verdict"])
        self.assertFalse(r["finding"])
        self.assertIn("includes 0", st["S3"]["verdict"])
        self.assertTrue(st["S3"]["verdict"].startswith("bound: rho_C <= "))
        self.assertEqual(st["S2"]["verdict"], "finding: line transfer")
        self.assertIn("is a bound on rho, not evidence of no cost", text)
        # a failed A/A (half-width over 1%): the cell is a bound, its contrasts carry no verdict
        _, js, st = self.rows(_dose_run(RHO, aa_noise=0.03), _dose_evidence())
        self.assertFalse(js["cells"]["A"]["aa"]["ok"])
        self.assertGreater(js["cells"]["A"]["aa"]["hw"], 1.0)
        self.assertTrue(st["S1"]["verdict"].startswith("bound: rho_A <= "))
        self.assertIn("A/A gate failed", st["S1"]["verdict"])
        self.assertTrue(st["S4"]["verdict"].startswith("no verdict: an A/A of its cells failed"))
        # an estimate over 1% but inside the A/A's reach is a bound too
        res = _dose_run({"mt-14w-one": 0.012, "mt-14w-split": 0.05, "mt-7w-one": 0.02})
        own = {m["round"]: m["workers_cycles_per_req"] for m in res["legs"]
               if m["arm"] == "own-128" and m["shape"] == "mt-14w-one"}
        for m in res["legs"]:
            if m["arm"] == "own-128-A2" and m["shape"] == "mt-14w-one":
                m["workers_cycles_per_req"] = own[m["round"]] * (1.005 + (0.016 if m["round"] % 2 else -0.016))
        _, js, st = self.rows(res, _dose_evidence())
        aa = js["cells"]["A"]["aa"]
        self.assertTrue(aa["ok"] and aa["hw"] <= 1.0)
        self.assertGreater(st["S1"]["w"]["mean"], 1.0)
        self.assertGreater(aa["reach"], st["S1"]["w"]["mean"])
        self.assertIn("within the A/A's reach", st["S1"]["verdict"])
        self.assertTrue(st["S1"]["verdict"].startswith("bound: rho_A <= "))

    def test_load_statement(self):
        _, _, st = self.rows(_dose_run({"mt-14w-one": 0.02, "mt-14w-split": 0.05, "mt-7w-one": 0.06}),
                             _dose_evidence())
        self.assertIn("refutes the \"no queueing\" reading", st["S5"]["verdict"])
        self.assertIn("load ladder", st["S5"]["verdict"])
        _, _, st = self.rows(_dose_run({"mt-14w-one": 0.02, "mt-14w-split": 0.05, "mt-7w-one": 0.02}),
                             _dose_evidence())
        self.assertFalse(st["S5"]["resolved"])
        self.assertNotIn("refutes", st["S5"]["verdict"])

    def test_incomplete(self):
        res = _dose_run(RHO)
        res["metadata"]["incomplete"] = True
        text, js, st = self.rows(res, _dose_evidence())
        self.assertEqual({r["verdict"] for r in st.values()}, {experiment.INCOMPLETE})
        self.assertNotIn("x_pct", js["model"])
        self.assertIn("no model row", text)

    def test_model_row(self):
        text, js, _ = self.rows(_dose_run(RHO), _dose_evidence())
        self.assertIn("## Model row for the plain config (a MODEL, not a measurement)", text)
        self.assertIn("**MODEL:** sharing store stats across 7-14 workers, one or two sockets, 36-68% busy, costs at "
                      "most ", text)
        self.assertIn("not measured in the plain config", text)
        m, e, c = js["model"]["cells"]["B"], js["evidence"]["B"], js["cells"]["B"]
        self.assertAlmostEqual(e["h"], 1.2, delta=0.05)
        self.assertAlmostEqual(m["T"], e["hitm_base_minus_reject"]["hi"] / e["h"])
        self.assertAlmostEqual(m["P"], c["price"]["hi"])
        self.assertAlmostEqual(m["x_pct"], 100 * m["T"] * m["P"] / 540e3)
        self.assertEqual(js["model"]["x_pct"], max(r["x_pct"] for r in js["model"]["cells"].values()))
        self.assertFalse(m["T_above_ops"])
        self.assertAlmostEqual(e["stat_ops_per_req"], 29.0)
        # without the evidence legs there is no model row, and the text says what is missing
        text, js, _ = self.rows(_dose_run(RHO))
        self.assertIn("No evidence legs given", text)
        self.assertEqual(js["model"], {"cells": {}})
        self.assertNotIn("**MODEL:**", text)
        # h not positive: no model
        text, js, _ = self.rows(_dose_run(RHO), _dose_evidence(h=-0.1))
        self.assertEqual(js["model"]["cells"]["A"]["why"], "h is not positive")
        self.assertIn("no model row", text)

    def test_hitm_needs_both_events(self):
        self.assertIsNone(UT.hitm_per_req({"per_req": {"events": {HITM_U[0]: 3.0}}}))
        self.assertEqual(UT.hitm_per_req({"per_req": {"events": {HITM_U[0]: 3.0, HITM_U[1]: 1.0}}}), 4.0)
        self.assertEqual(UT.hitm_per_req({"per_req": {"events": {UT.HITM[0]: 3.0, UT.HITM[1]: 0.0}}}), 3.0)
        self.assertIsNone(UT.hitm_per_req({}))

    def test_run_u_table_unchanged_path(self):
        # a run without a dose block still renders run U's tables
        exp = json.load(open(os.path.join(MT, "bench-x86_64", "u-hi.json")))
        text, js = UT.render({"experiment": exp, "legs": [], "metadata": {"rounds_complete": 0}})
        self.assertTrue(text.startswith("# Run U:"))
        self.assertIn("contrasts", js)


class DosePilotTest(unittest.TestCase):
    DP = _mod("mt_dose_pilot", os.path.join(MT, "dose_pilot.py"))

    def run_(self, h=1.2, base=540e3, ins_extra=0.0, mut=None):
        cfg = MK.configs(box("bench-x86_64"))["dose-pilot.json"]
        legs = []
        for s in cfg["shapes"]:
            conns = s["workers"] * 16
            for a in cfg["arms"]:
                n = a["name"]
                k = int(n.split("-")[1]) if "-" in n else 0
                sh = n.startswith("shared")
                m = {"shape": s["name"], "arm": n, "round": 1, "verdict": {"valid": True},
                     "workers_cycles_per_req": base, "responses": 420000, "sut_busy": 0.36, "client_headroom": 0.5,
                     "client_pending_total": 14, "client_workers": 14, "sut_foreign_cpus": 0.01,
                     "perf_min_running_pct": 100.0,
                     "per_req": {"instructions_u": 200e3 + 300 * k + (ins_extra if sh else 0.0),
                                 "events": {HITM_U[0]: 7.0 + (h * k if sh else 0.0), HITM_U[1]: 0.0}},
                     "stat_ops": {"counter_incs": 25 * 420000, "histogram_samples": 4 * 420000},
                     "stat_count": {"start_n": k if sh else 2 * k * conns, "end_n": k if sh else 2 * k * conns,
                                    "new_in_window": 0, "sum_per_request": 1.002 * k, "start_read_s": 0.05,
                                    "end_read_s": 0.05, "pre_window_s": 0.4},
                     "evidence": {"ok": True, "failed": []}}
                if mut:
                    mut(m)
                legs.append(m)
        res = {"legs": legs, "metadata": {"bootstrap_validate": {a["name"]: {"ok": True} for a in cfg["arms"]}}}
        return cfg, res

    def test_answers(self):
        cfg, res = self.run_()
        rep = self.DP.answers(cfg, res, {a["name"]: [] for a in cfg["arms"]})
        self.assertTrue(rep["ok"], rep["problems"])
        # 1.2 x K x 100 / 540,000: 1.42% at 64, 2.84% at 128
        self.assertEqual(rep["q4"]["k"], 128)
        self.assertAlmostEqual(rep["q4"]["rows"][0]["share"], 1.2 * 64 * 100 / 540e3)
        self.assertEqual([r["ok"] for r in rep["q4"]["rows"]], [False, True, True])
        self.assertAlmostEqual(rep["q3"]["rows"][0]["h"], 1.2)
        self.assertEqual(len(rep["q2"]["rows"]), 6)  # 3 K x 2 cells
        self.assertAlmostEqual(rep["stat_ops"]["A"], 29.0)
        self.assertEqual(rep["q6"]["counters"], [2 * 256 * 224, 2 * 256 * 112])
        t = self.DP.text(rep, cfg)
        for needle in ("1. bootstrap --mode validate: base OK", "-> K = 128", "pilot OK: K = 128", "h = 1.200",
                       "load cell PASS", "own-256 held 114688, 57344 counters", "client slack 7.0 s"):
            self.assertIn(needle, t)
        self.assertNotIn("OVER HALF THE SLACK", t)

        def slow(m):
            m["stat_count"]["pre_window_s"] = 4.2
        cfg, res = self.run_(mut=slow)
        self.assertIn("OVER HALF THE SLACK", self.DP.text(self.DP.answers(cfg, res, {}), cfg))

    def test_k_choice(self):
        ov = lambda cfg: {a["name"]: [] for a in cfg["arms"]}  # noqa: E731
        cfg, res = self.run_(h=1.4, base=300e3)   # 1.4 x 64 x 100 / 300,000 = 2.99%
        self.assertEqual(self.DP.answers(cfg, res, ov(cfg))["q4"]["k"], 64)
        cfg, res = self.run_(h=1.0, base=600e3)   # 2.13% at 128, 4.27% at 256
        self.assertEqual(self.DP.answers(cfg, res, ov(cfg))["q4"]["k"], 256)
        cfg, res = self.run_(h=0.2)               # under 2.5% even at 256
        rep = self.DP.answers(cfg, res, ov(cfg))
        self.assertIsNone(rep["q4"]["k"])
        self.assertFalse(rep["ok"])
        self.assertIn("NO K", self.DP.text(rep, cfg))
        self.assertIn("outside the expected range", self.DP.text(rep, cfg))

    def test_failures(self):
        ov = lambda cfg: {a["name"]: [] for a in cfg["arms"]}  # noqa: E731
        cfg, res = self.run_(ins_extra=3000.0)  # more than 0.5% more instructions in shared
        rep = self.DP.answers(cfg, res, ov(cfg))
        self.assertFalse(rep["q2"]["ok"] or rep["ok"])

        def bad_load(m):
            if m["shape"] == "mt-7w-one" and m["arm"] == "shared-256":
                m["verdict"] = {"valid": False, "reasons": ["client headroom 12% under 25%"]}
        cfg, res = self.run_(mut=bad_load)
        rep = self.DP.answers(cfg, res, ov(cfg))
        self.assertFalse(rep["q5"]["ok"] or rep["ok"])
        self.assertTrue(any("client headroom" in p for p in rep["problems"]))

        def limit(m):
            if m["arm"] == "own-256":
                m["evidence"] = {"ok": False, "failed": ["256 increments per request over all dose counters: short"]}
        cfg, res = self.run_(mut=limit)
        rep = self.DP.answers(cfg, res, ov(cfg))
        self.assertFalse(rep["q1"]["ok"] or rep["q6"]["ok"] or rep["ok"])
        cfg, res = self.run_()
        o = ov(cfg)
        o["own-256"] = ["server.stats_overflow.counter: 12"]
        self.assertFalse(self.DP.answers(cfg, res, o)["q6"]["ok"])
        self.assertFalse(self.DP.answers(cfg, res, None)["q6"]["ok"])  # no stat dumps read: not a pass
        res["metadata"] = {}
        self.assertFalse(self.DP.answers(cfg, res, ov(cfg))["q1"]["ok"])  # validate not recorded
        res["legs"] = res["legs"][:-1]
        self.assertTrue(any(p.startswith("missing leg") for p in self.DP.answers(cfg, res, ov(cfg))["problems"]))

    def test_overflow_lines_and_script(self):
        import gzip
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "stats"))
        with gzip.open(os.path.join(d, "stats", "own-64.txt.gz"), "wt") as f:
            f.write("dose.c000.port.40000: 3\nserver.stats_overflow.counter: 2\n")
        with gzip.open(os.path.join(d, "stats", "base.txt.gz"), "wt") as f:
            f.write("server.uptime: 3\n")
        self.assertEqual(self.DP.overflow_lines(d, ["base", "own-64", "shared-64"]),
                         {"base": [], "own-64": ["server.stats_overflow.counter: 2"], "shared-64": None})
        cfg, res = self.run_()
        json.dump(res, open(os.path.join(d, "results.json"), "w"))
        r = subprocess.run([sys.executable, os.path.join(MT, "dose_pilot.py"),
                            os.path.join(MT, "bench-x86_64", "dose-pilot.json"), d, "--json", os.path.join(d, "o.json")],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)  # an overflow stat and missing dumps: not clean
        self.assertIn("pilot NOT clean", r.stdout)
        self.assertFalse(json.load(open(os.path.join(d, "o.json")))["ok"])

    def test_script_modes(self):
        txt = open(os.path.join(MT, "run-u.sh")).read()
        for m in ("dose-pilot)", "dose-smoke)", "dose-check)", "dose-queue)", "DOSE_STOP_S:-9000",
                  "DOSE_EV_STOP_S:-3600", "dose_pilot.py", '--out "$R/dose$DOSE_TAG"',
                  '--evidence $R/dose-evidence$DOSE_TAG', "dose not started (K, smoke or evidence; no override)"):
            self.assertIn(m, txt)
        # the smoke refuses an uncalibrated K before it runs anything; the queue runs only after dose_check
        sm = txt[txt.index("  dose-smoke)"):txt.index("  dose-check)")]
        self.assertLess(sm.index("uncalibrated"), sm.index("$EPL run"))
        q = txt[txt.index("  dose-queue)"):txt.index("  codegen-smoke)")]
        self.assertLess(q.index("dose_check ||"), q.index("$EPL run"))
        self.assertLess(q.index('"$C/dose.json"'), q.index('"$C/dose-evidence.json"'))
        chk = txt[txt.index("dose_check() {"):txt.index("mode=${1:-}")]
        for m in ("smoke_valid.py", "evidence-check", "a.get('dose')==b.get('dose')"):
            self.assertIn(m, chk)
        r = subprocess.run(["bash", "-n", os.path.join(MT, "run-u.sh")], capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0)


class ArmShapesTest(unittest.TestCase):
    """Arms that run in some shapes only (`shapes` on an arm)."""

    def exp(self, order="latin", **over):
        raw = json.load(open(os.path.join(MT, "bench-x86_64", "u-hi.json")))
        raw.pop("uncalibrated", None)
        raw["arms"].append(dict(json.loads(json.dumps(raw["arms"][0])), name="extra-1", shapes=["mt-14w-one"]))
        raw["arms"].append(dict(json.loads(json.dumps(raw["arms"][0])), name="extra-2", shapes=["mt-14w-one"]))
        raw.update(order=order, **over)
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "x.json"), "w") as f:
            json.dump(raw, f)
        return experiment.load(os.path.join(d, "x.json"))

    def test_unrestricted_runs_are_unchanged(self):
        for fn in ("u.json", "u-hi.json", "u-hitm.json"):
            exp = experiment.load(os.path.join(MT, "bench-x86_64", fn))
            self.assertFalse(experiment.restricted(exp))
            self.assertEqual(experiment.order_period(exp), len(exp["arms"]))
            for r in range(1, exp["rounds"] + 1):
                for sh in exp["shapes"]:
                    self.assertEqual(experiment.shape_round_order(exp, r, sh), experiment.round_order(exp, r))
            plan = experiment.schedule(exp)
            want = [(r, sh["name"], a["name"]) for r in range(1, exp["rounds"] + 1)
                    for sh in experiment.shape_order(exp, r) for a in experiment.round_order(exp, r)]
            self.assertEqual([(r, sh["name"], a["name"]) for r, sh, a in plan], want)

    def test_schedule_and_balance(self):
        exp = self.exp()
        self.assertEqual(experiment.validate(exp), [])
        self.assertEqual(experiment.order_period(exp), 15)  # lcm of 5 arms in one shape and 3 in the others
        plan = experiment.schedule(exp)
        self.assertEqual(len(plan), 15 * (5 + 3 + 3))
        pos = {}
        for r in range(1, 16):
            for sh in exp["shapes"]:
                names = [a["name"] for a in experiment.shape_round_order(exp, r, sh)]
                self.assertEqual("extra-1" in names, sh["name"] == "mt-14w-one")
                for i, n in enumerate(names):
                    pos[(sh["name"], n, i)] = pos.get((sh["name"], n, i), 0) + 1
        self.assertEqual({v for (s, n, i), v in pos.items() if s == "mt-14w-one"}, {3})
        self.assertEqual({v for (s, n, i), v in pos.items() if s != "mt-14w-one"}, {5})
        # another order: the round's order with the absent arms left out
        rot = self.exp(order="rotate", rounds=30, rounds_block=30, rounds_max=30)
        for r in (1, 2, 7):
            full = [a["name"] for a in experiment.round_order(rot, r)]
            got = [a["name"] for a in experiment.shape_round_order(rot, r, rot["shapes"][1])]
            self.assertEqual(got, [n for n in full if not n.startswith("extra")])

    def test_complete_rounds_and_analysis(self):
        exp = self.exp()
        legs = [{"round": r, "shape": sh["name"], "arm": a["name"], "verdict": {"valid": True}, "leg_id": "x",
                 "workers_cycles_per_req": 100.0 + r, "per_req": {"cycles_total": 100.0 + r, "instructions_u": 50.0}}
                for r, sh, a in experiment.schedule(exp)]
        self.assertEqual(experiment.complete_rounds(exp, legs), 15)  # no leg expected where an arm does not run
        short = [m for m in legs if not (m["round"] == 15 and m["arm"] == "extra-2")]
        self.assertEqual(experiment.complete_rounds(exp, short), 0)
        an = experiment.analyse(exp, legs)
        rows = lambda s: [c["arm"] for c in an["shapes"][s]["comparisons"]]  # noqa: E731
        self.assertEqual(rows("mt-14w-one"), ["stats-reject", "base-A2", "extra-1", "extra-2"])
        self.assertEqual(rows("mt-28w"), ["stats-reject", "base-A2"])
        self.assertEqual(an["shapes"]["mt-28w"]["arms"]["extra-1"]["legs"], 0)

    def test_validate(self):
        bad = self.exp()
        bad["arms"][-1]["shapes"] = ["mt-1w"]
        self.assertTrue(any("shapes must be a non-empty list of shape names" in e for e in experiment.validate(bad)))
        bad = self.exp()
        bad["arms"][0]["shapes"] = ["mt-14w-one"]
        self.assertTrue(any("base_arm must run in every shape" in e for e in experiment.validate(bad)))
        bad = self.exp()
        for a in bad["arms"][1:3]:
            a["shapes"] = ["mt-14w-one"]
        self.assertTrue(any("fewer than 2 arms run in it" in e for e in experiment.validate(bad)))
        bad = self.exp(rounds=12, rounds_block=12, rounds_max=12)
        self.assertTrue(any("multiple of 15" in e for e in experiment.validate(bad)))

    def test_rerun_keeps_the_shape_order(self):
        src = open(os.path.join(HERE, "epl", "experiment.py")).read()
        i = src.index("    def _rerun_invalid(")
        self.assertIn("for a in shape_round_order(self.exp, r, sh):", src[i:src.index("    def run(self", i)])


if __name__ == "__main__":
    unittest.main()
