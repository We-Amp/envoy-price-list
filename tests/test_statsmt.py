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


DOSE_RATES = {"bench-x86_64-dose-1": {"counters": 128, "connections": 16}}


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
        for rates in ({"bench-x86_64-dose": {"counters": 128, "connections": 16}},
                      {"bench-x86_64": {"r_star": 1000, "k": 16}}, {"bench-x86_64-hi-1800": {"r_star": 1800, "k": 16}},
                      # the choice is K and the connection count together: one alone does not calibrate
                      {"bench-x86_64-dose-1": {"counters": 128}}, {"bench-x86_64-dose-1": {"connections": 8}}):
            self.assertTrue(MK.configs(box("bench-x86_64"), rates)["dose.json"].get("uncalibrated"), rates)
        for bad in ({"counters": 100, "connections": 16}, {"counters": 128, "connections": 4}):
            with self.assertRaises(SystemExit, msg=bad):
                MK.configs(box("bench-x86_64"), {"bench-x86_64-dose-1": bad})
        # `epl run` refuses an uncalibrated config
        r = subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "run",
                            os.path.join(MT, "bench-x86_64", "smoke-dose.json"), "--dry-run", "--allow-short",
                            "--out", tempfile.mkdtemp()], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("uncalibrated", r.stderr + r.stdout)

    def test_calibrated(self):
        c = MK.configs(box("bench-x86_64"), DOSE_RATES)
        u = c["dose.json"]
        self.assertNotIn("uncalibrated", u)
        # the slot's arms per cell: A and B at K = 128, D at 64, and A's second dose at 64
        A, B, D = "mt-14w-one", "mt-14w-split", "mt-28w"
        self.assertEqual([(a["name"], a["shapes"]) for a in u["arms"]],
                         [("own-128", [A, B]), ("shared-128", [A, B]), ("own-128-A2", [A, B]),
                          ("own-64", [A, D]), ("shared-64", [A, D]), ("own-64-A2", [D]),
                          ("hot-own-128", [A]), ("hot-shared-128", [A])])
        self.assertEqual(u["dose"]["hot"], {"cell": "A", "counters": 128, "reference": "hot-own-128",
                                            "shared": "hot-shared-128"})
        self.assertEqual([(a["settings"]["stats_access_log"]["counters"], a["settings"]["stats_access_log"]["tag"])
                          for a in u["arms"]],
                         [(128, "%DOWNSTREAM_REMOTE_PORT%"), (128, "%DOWNSTREAM_LOCAL_PORT%"),
                          (128, "%DOWNSTREAM_REMOTE_PORT%"), (64, "%DOWNSTREAM_REMOTE_PORT%"),
                          (64, "%DOWNSTREAM_LOCAL_PORT%"), (64, "%DOWNSTREAM_REMOTE_PORT%"),
                          (128, "%DOWNSTREAM_REMOTE_PORT%"), (128, "%DOWNSTREAM_LOCAL_PORT%")])
        self.assertEqual([bool(a["settings"]["stats_access_log"].get("hot")) for a in u["arms"]], [False] * 6 + [True] * 2)
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "dose.json"))
        per = {}
        for r, sh, a in experiment.schedule(exp):
            if r == 1:
                per.setdefault(sh["cell"], []).append(a["name"])
        self.assertEqual({k: sorted(v) for k, v in per.items()},
                         {"A": ["hot-own-128", "hot-shared-128", "own-128", "own-128-A2", "own-64", "shared-128",
                                "shared-64"],
                          "B": ["own-128", "own-128-A2", "shared-128"], "D": ["own-64", "own-64-A2", "shared-64"]})
        self.assertEqual(sum(len(v) for v in per.values()), 13)
        # every cell names its own dose, reference, shared arm and A/A; cell D's are at 64
        self.assertEqual([(x["cell"], x["counters"], x["reference"], x["shared"], x["aa"]) for x in u["dose"]["cells"]],
                         [("A", 128, "own-128", "shared-128", ["own-128-A2", "own-128"]),
                          ("B", 128, "own-128", "shared-128", ["own-128-A2", "own-128"]),
                          ("D", 64, "own-64", "shared-64", ["own-64-A2", "own-64"])])
        self.assertEqual(u["dose"]["low"], {"cell": "A", "counters": 64, "reference": "own-64", "shared": "shared-64"})
        self.assertEqual((u["dose"]["counters"], u["dose"]["connections"], u["k"]), (128, 16, 16))
        for stale in ("reference", "shared", "aa"):
            self.assertNotIn(stale, u["dose"])  # nothing run-wide a table could mistake for every cell's
        # the A/A arms are copies of their own arm in the cells they run in
        arms = {a["name"]: a for a in u["arms"]}
        for own, a2 in (("own-128", "own-128-A2"), ("own-64", "own-64-A2")):
            self.assertEqual(arms[own]["settings"], arms[a2]["settings"])
            mine = lambda a: [i for i in arms[a]["evidence"] if i.get("shape") in (None, D if a2.endswith("64-A2") else A)]  # noqa: E731,E501
            self.assertEqual(mine(own), mine(a2))
        # no arm runs in every cell: the harness's own rows are between the arms of a cell
        self.assertEqual((u["comparisons"], u["base_arm"]), ("all_pairs", "own-128"))
        self.assertEqual(experiment.validate(exp, allow_short=True), [])
        self.assertNotIn("uncalibrated", c["smoke-dose.json"])
        self.assertEqual(c["smoke-dose.json"]["dose"], u["dose"])  # dose-check compares the two
        self.assertTrue(c["u.json"]["uncalibrated"])  # run U's key is separate
        # the second dose cannot also be K; another K moves cells A and B only
        with self.assertRaises(SystemExit):
            MK.configs(box("bench-x86_64"), {"bench-x86_64-dose-1": {"counters": 64, "connections": 16}})
        u256 = MK.configs(box("bench-x86_64"), {"bench-x86_64-dose-1": {"counters": 256, "connections": 16}})["dose.json"]
        self.assertEqual([x["counters"] for x in u256["dose"]["cells"]], [256, 256, 64])
        self.assertEqual([a["name"] for a in u256["arms"]],
                         ["own-256", "shared-256", "own-256-A2", "own-64", "shared-64", "own-64-A2", "hot-own-128",
                          "hot-shared-128"])
        # the pilot is the same whatever is chosen
        self.assertEqual(c["dose-pilot.json"], MK.configs(box("bench-x86_64"))["dose-pilot.json"])
        # 8 connections per worker: its own shape names, connection counts and counter expectations
        c8 = MK.configs(box("bench-x86_64"), {"bench-x86_64-dose-1": {"counters": 128, "connections": 8}})
        u = c8["dose.json"]
        self.assertNotIn("uncalibrated", u)
        self.assertEqual((u["k"], u["dose"]["connections"]), (8, 8))
        self.assertEqual([(s["name"], s["client_concurrency"] * s["client_connections_per_worker"]) for s in u["shapes"]],
                         [("mt-14w-one-c8", 112), ("mt-14w-split-c8", 112), ("mt-28w-c8", 224)])
        self.assertEqual([c_["shape"] for c_ in u["dose"]["cells"]], [s["name"] for s in u["shapes"]])
        self.assertEqual(u["arms"][3]["shapes"], ["mt-14w-one-c8", "mt-28w-c8"])
        own = [i for i in u["arms"][0]["evidence"] if i["stat"] == "stat_count.start_n"]
        self.assertEqual([(i["shape"], i["min"], i["max"]) for i in own],
                         [("mt-14w-one-c8", 128 * 112, 2 * 128 * 112), ("mt-14w-split-c8", 128 * 112, 2 * 128 * 112)])
        self.assertEqual(experiment.validate(experiment.load(self.tmp(u)), allow_short=True), [])
        self.assertEqual([s["name"] for s in c8["dose-evidence.json"]["shapes"]], [s["name"] for s in u["shapes"]])

    def test_per_arm_k_in_evidence(self):
        # every dose arm's evidence expects that arm's own K: counters, increments per request, counts per connection
        u = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
        conns = {"mt-14w-one": 224, "mt-14w-split": 224, "mt-28w": 448}
        for a in u["arms"]:
            K = a["settings"]["stats_access_log"]["counters"]
            hot = bool(a["settings"]["stats_access_log"].get("hot"))
            self.assertEqual(K, int([x for x in a["name"].split("-") if x.isdigit()][0]))
            self.assertEqual(hot, a["name"].startswith("hot-"))
            n = 1 if hot else K   # counter objects per set; the increments per request are K either way
            byst = {}
            for i in a["evidence"]:
                byst.setdefault(i["stat"], []).append(i)
            s = byst["stat_count.sum_per_request"][0]
            self.assertEqual((s["min"], s["max"]), (K - 0.5, K + 0.5), a["name"])
            if "shared" in a["name"]:
                self.assertEqual([i["equals"] for i in byst["stat_count.start_n"] + byst["stat_count.end_n"]], [n, n])
                self.assertEqual(byst["dose.c000.port.10110"][0]["per_request"], float(K if hot else 1))
            else:
                self.assertEqual([(i["shape"], i["min"], i["max"]) for i in byst["stat_count.start_n"]],
                                 [(sh, n * conns[sh], 2 * n * conns[sh]) for sh in a["shapes"]], a["name"])
        # cell D's own arm at 64: 28,672 counters for its 448 connections (the pilot's passing size), not 57,344
        d = [i for i in {a["name"]: a for a in u["arms"]}["own-64"]["evidence"] if i.get("shape") == "mt-28w"][0]
        self.assertEqual((d["min"], d["max"]), (28672, 57344))

    def tmp(self, cfg):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "c.json"), "w") as f:
            json.dump(cfg, f)
        return os.path.join(d, "c.json")

    def test_cells(self):
        u = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
        got = [(s["cell"], s["name"], s["workers"], s["worker_cpus"], s["rps"], s["client_concurrency"],
                s["client_connections_per_worker"]) for s in u["shapes"]]
        self.assertEqual(got, [("A", "mt-14w-one", 14, "0-13", 21000, 14, 16),
                               ("B", "mt-14w-split", 14, "0-6,20-26", 21000, 14, 16),
                               ("D", "mt-28w", 28, "0-13,20-33", 42000, 14, 32)])
        hi = MK.configs(box("bench-x86_64"), {"bench-x86_64-hi-1800": {"r_star": 1500, "k": 16}})["u-hi.json"]
        d28 = dict([s for s in u["shapes"] if s["cell"] == "D"][0])
        for extra in ("admin_timeout_s", "cell", "connections_per_worker"):
            d28.pop(extra)
        self.assertEqual(d28, [s for s in hi["shapes"] if s["name"] == "mt-28w"][0])  # run U-hi's 28w rung
        for s in u["shapes"]:
            self.assertEqual(s["client_concurrency"] * s["client_connections_per_worker"], 16 * s["workers"])
            self.assertEqual((s["main_cpu"], s["admin_timeout_s"], s["lead_in_s"]), (19, 30, 3))
        self.assertEqual([(c["cell"], c["rate_per_worker"], c["role"], c["sockets"], c["connections"])
                          for c in u["dose"]["cells"]],
                         [("A", 1500, "reference", 1, 16), ("B", 1500, "socket", 2, 16), ("D", 1500, "workers", 2, 16)])
        # no leg where it would overlap the daily timer window
        self.assertEqual(u["avoid_utc"], [{"from": "00:00", "to": "00:10", "leg_s": 120}])
        self.assertEqual((u["dose"]["socket"], u["dose"]["workers"]), (["B", "A"], ["D", "A"]))
        self.assertNotIn("load", u["dose"])
        self.assertEqual((u["rounds"], u["rounds_max"], u["adaptive"], u["order"], u["shape_order"]),
                         (6, 6, False, "latin", "latin"))
        self.assertEqual(u["primary_metric"], "workers_cycles_per_req")
        self.assertEqual(u["measure"]["stat_count_prefix"], "dose.")
        self.assertEqual(u["measure"]["stat_filter_extra"], "^dose\\.c000\\.port\\.10110$")
        self.assertEqual(u["measure"]["perf_events"], box("bench-x86_64")["perf_events"])
        # the same 20 s window as run U; the client runs longer, for the admin reads before the window
        self.assertEqual((u["measure"]["window_s"], u["client"]["duration_s"]), (20, 30))
        self.assertEqual(MK.configs(box("bench-x86_64"))["u-hi.json"]["client"]["duration_s"], 25)
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "dose.json"))
        # a short run: 6 rounds, so --allow-short; rounds complete in blocks of 3
        self.assertEqual(experiment.validate(exp, allow_short=True), [])
        self.assertTrue(any("rounds must be >= 12" in e for e in experiment.validate(exp)))
        self.assertEqual((u["rotation_block"], experiment.order_period(exp)), (3, 3))
        self.assertEqual((u["dose"]["rounds"], u["dose"]["short_run"]), (6, True))
        plan = experiment.schedule(exp)
        self.assertEqual(len(plan), 78)  # 13 legs per round x 6 rounds
        per = {}
        for r, sh, a in plan:
            per.setdefault((r, sh["cell"]), []).append(a["name"])
        self.assertEqual({len(v) for (r, c), v in per.items() if c == "A"}, {7})
        self.assertEqual({len(v) for (r, c), v in per.items() if c != "A"}, {3})
        self.assertTrue(all("-128" not in n for (r, c), v in per.items() if c == "D" for n in v))
        self.assertTrue(all("-64" not in n and "hot" not in n for (r, c), v in per.items() if c == "B" for n in v))
        # balance as far as 6 rounds allow: in the 3-arm cells every arm is in every position
        # twice; in cell A (7 arms) every arm takes 6 different positions, one each
        pos = {}
        for (r, c), v in per.items():
            for i, n in enumerate(v):
                pos.setdefault((c, n), []).append(i)
        for (c, n), ps in pos.items():
            if c == "A":
                self.assertEqual((len(ps), len(set(ps))), (6, 6), n)
            else:
                self.assertEqual(sorted(ps), [0, 0, 1, 1, 2, 2], (c, n))
        self.assertEqual(len({n for (c, n) in pos if c == "A"}), 7)
        # every cell leads a round twice
        lead = [experiment.shape_order(exp, r)[0]["cell"] for r in range(1, 7)]
        self.assertEqual(sorted(lead), ["A", "A", "B", "B", "D", "D"])
        firsts = {experiment.shape_order(exp, r)[0]["name"] for r in range(1, 4)}
        self.assertEqual(len(firsts), 3)
        for a in exp["arms"]:
            b = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, a, "/r"), 8092)
            self.assertEqual(envoy_config.audit_mt_s(b), [], a["name"])

    def test_flush_interval(self):
        b = box("bench-x86_64")
        iv = b["dose"]["flush_interval_s"]
        c = MK.configs(b, DOSE_RATES)
        # longer than a leg's Envoy lives (warm-up, client run, a minute of reads and start-up),
        # under the 300 s the bootstrap accepts
        self.assertGreater(iv, 5 + b["dose"]["client_duration_s"] + 60)
        self.assertLess(iv, 300)
        for fn in ("dose.json", "smoke-dose.json", "dose-evidence.json", "dose-pilot.json"):
            exp = experiment.load(os.path.join(MT, "bench-x86_64", fn))
            for a in c[fn]["arms"]:
                dose_arm = "stats_access_log" in (a.get("settings") or {})
                self.assertEqual((a.get("settings") or {}).get("stats_flush"),
                                 {"interval_s": iv} if dose_arm else None, (fn, a["name"]))
                arm = [x for x in exp["arms"] if x["name"] == a["name"]][0]
                bs = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, arm, "/r"), 8092)
                # base and stats-reject keep Envoy's default (no key at all)
                self.assertEqual(bs.get("stats_flush_interval"), "%ds" % iv if dose_arm else None, (fn, a["name"]))
                self.assertNotIn("stats_flush_on_admin", bs)
                if dose_arm:
                    self.assertIn({"stat": "stats_flush_interval", "scope": "config", "equals": "%ds" % iv,
                                   "label": "stats flush interval %d s (no flush during the leg)" % iv}, a["evidence"])
                    # nothing a dose arm's evidence reads needs a flush: the config dump, counters
                    # (cumulative at the increment) and the leg's own stat count
                    for it in a["evidence"]:
                        self.assertTrue(it["scope"] == "config" or it["stat"].startswith("stat_count.")
                                        or it["stat"] in ("dose.c000.port.10110",
                                                          "http.ingress_http.downstream_cx_total"), it)
        # the existing runs carry no flush setting
        for fn in ("u.json", "u-hi.json", "u-hitm.json"):
            self.assertFalse([a for a in c[fn]["arms"] if "stats_flush" in (a.get("settings") or {})])

    def test_wildcard_listener(self):
        b = box("bench-x86_64")
        self.assertEqual(b["dose"]["listener_address"], "0.0.0.0")
        self.assertIn("listener_address", envoy_config.SETTINGS)
        c = MK.configs(b, DOSE_RATES)

        def addrs(fn, name):
            exp = experiment.load(os.path.join(MT, "bench-x86_64", fn))
            a = [x for x in exp["arms"] if x["name"] == name][0]
            bs = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, a, "/r"), 8092)
            ls = bs["static_resources"]["listeners"][0]["address"]["socket_address"]
            return ls, bs["admin"]["address"]["socket_address"]["address"], bs
        for fn in ("dose.json", "smoke-dose.json", "dose-evidence.json", "dose-pilot.json"):
            for a in c[fn]["arms"]:
                ls, admin, bs = addrs(fn, a["name"])
                dose_arm = "stats_access_log" in (a.get("settings") or {})
                want = "0.0.0.0" if dose_arm and not a["name"].endswith("-lo") else "127.0.0.1"
                self.assertEqual((ls["address"], ls["port_value"], admin), (want, 10110, "127.0.0.1"), (fn, a["name"]))
                if dose_arm:
                    it = [i for i in a["evidence"] if i["stat"] == "address"]
                    self.assertEqual([(i["scope"], i["where"], i["equals"]) for i in it],
                                     [("config", {"port_value": 10110}, want)])
                    # the item reads the listener's address out of a config dump, not the admin's
                    # or the origin cluster's, and fails on the other listener address
                    from epl import evidence
                    self.assertTrue(evidence.check_item({}, it[0], bs)["ok"], (fn, a["name"]))
                    other = json.loads(json.dumps(bs))
                    other["static_resources"]["listeners"][0]["address"]["socket_address"]["address"] = \
                        "127.0.0.1" if want == "0.0.0.0" else "0.0.0.0"
                    self.assertFalse(evidence.check_item({}, it[0], other)["ok"])
        # the wildcard pair and the loopback pair differ in the listener address only
        ls_w, _, bw = addrs("dose-pilot.json", "shared-128")
        ls_l, _, bl = addrs("dose-pilot.json", "shared-128-lo")
        bw["static_resources"]["listeners"][0]["address"]["socket_address"]["address"] = "127.0.0.1"
        self.assertEqual(bw, bl)
        # no other run binds the wildcard address
        for fn in ("u.json", "u-hi.json", "u-hitm.json", "smoke-u.json"):
            exp = experiment.load(os.path.join(MT, "bench-x86_64", fn))
            for a in exp["arms"]:
                self.assertNotIn("0.0.0.0", envoy_config.bootstrap_text(exp["shapes"], experiment.arm_envoy(exp, a, "/r"),
                                                                        8092))

    def test_pilot_smoke_evidence_configs(self):
        c = MK.configs(box("bench-x86_64"), DOSE_RATES)
        p = c["dose-pilot.json"]
        self.assertEqual([a["name"] for a in p["arms"]],
                         ["base", "own-64", "shared-64", "own-128", "shared-128", "own-256", "shared-256",
                          "own-128-lo", "shared-128-lo"])
        self.assertEqual([(s["cell"], s["name"], s["connections_per_worker"], s["rps"]) for s in p["shapes"]],
                         [("A", "mt-14w-one", 16, 21000), ("D", "mt-28w", 16, 42000), ("A", "mt-14w-one-c8", 8, 21000),
                          ("D", "mt-28w-c8", 8, 42000), ("A", "mt-14w-one-lo", 16, 21000), ("C", "mt-7w-one", 16, 15400)])
        self.assertEqual([s["client_concurrency"] * s["client_connections_per_worker"] for s in p["shapes"]],
                         [224, 448, 112, 224, 224, 112])
        # the loopback pair's shape is cell A's at 16 connections under another name
        a16, lo = dict(p["shapes"][0]), dict(p["shapes"][4])
        self.assertTrue(lo.pop("loopback"))
        self.assertEqual(dict(lo, name="mt-14w-one"), a16)
        wild = ["mt-14w-one", "mt-28w", "mt-14w-one-c8", "mt-28w-c8", "mt-7w-one"]
        k = ["mt-14w-one"]
        self.assertEqual([a.get("shapes") for a in p["arms"]], [k, k, k, wild, wild, k, k, ["mt-14w-one-lo"],
                                                               ["mt-14w-one-lo"]])
        self.assertEqual([bool(a.get("exploratory")) for a in p["arms"]], [False] * 7 + [True, True])
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "dose-pilot.json"))
        self.assertEqual(experiment.validate(exp, allow_short=True), [])
        # the order of the legs: the deciding 16-connection legs of cells A and D, the other
        # connection count, the loopback pair, the exploratory cell last
        plan = [(sh["name"], a["name"]) for r, sh, a in experiment.schedule(exp)]
        self.assertEqual(plan, [("mt-14w-one", n) for n in ("base", "own-64", "shared-64", "own-128", "shared-128",
                                                             "own-256", "shared-256")]
                         + [(s, n) for s in ("mt-28w", "mt-14w-one-c8", "mt-28w-c8") for n in ("own-128", "shared-128")]
                         + [("mt-14w-one-lo", "own-128-lo"), ("mt-14w-one-lo", "shared-128-lo"),
                            ("mt-7w-one", "own-128"), ("mt-7w-one", "shared-128")])
        self.assertEqual(len(plan), 17)
        per = {}
        for sname, aname in plan:
            per.setdefault(sname, []).append(aname)
        # a pilot is not cut short by invalid legs, and does not re-run a shape for one
        self.assertEqual((p["order"], p["shape_order"], p["rerun_invalid"]), ("fixed", "fixed", 0))
        self.assertGreater(p["abort_after_invalid"], len(plan))
        for fn in ("dose.json", "smoke-dose.json", "dose-evidence.json"):  # the timed runs keep the rule
            self.assertNotIn("abort_after_invalid", c[fn])
            self.assertEqual(experiment.load(os.path.join(MT, "bench-x86_64", fn))["abort_after_invalid"], 6)
            self.assertEqual(c[fn]["order"], "latin")
        # the pairs the pilot report walks: every one names legs the config schedules
        pairs = p["dose"]["pairs"]
        self.assertEqual([(x["cell"], x["connections"], x["k"], x["address"], x["role"], bool(x.get("exploratory")))
                          for x in pairs],
                         [("A", 16, 64, "0.0.0.0", "k", False), ("A", 16, 128, "0.0.0.0", "k", False),
                          ("A", 16, 256, "0.0.0.0", "k", False), ("D", 16, 128, "0.0.0.0", "connections", False),
                          ("A", 8, 128, "0.0.0.0", "connections", False), ("D", 8, 128, "0.0.0.0", "connections", False),
                          ("A", 16, 128, "127.0.0.1", "loopback", True), ("C", 16, 128, "0.0.0.0", "load", True)])
        for x in pairs:
            for n in (x["own"], x["shared"]):
                self.assertIn(n, per[x["shape"]])
        self.assertEqual(sum(2 for _ in pairs) + 1, 17)  # every leg but base belongs to a pair
        self.assertEqual({c_["shape"]: c_.get("exploratory", False) for c_ in p["dose"]["cells"]},
                         {"mt-14w-one": False, "mt-28w": False, "mt-14w-one-c8": False, "mt-28w-c8": False,
                          "mt-14w-one-lo": False, "mt-7w-one": True})
        self.assertEqual((p["dose"]["connections_choices"], box("bench-x86_64")["dose"]["pilot"]["connections"]),
                         ([8, 16], [16, 8]))
        # cell C at a rate the logger's cost leaves room for; the slot does not run it
        self.assertEqual([c_["rate_per_worker"] for c_ in p["dose"]["cells"] if c_["cell"] == "C"], [2200])
        self.assertNotIn("C", [c_["cell"] for c_ in c["dose.json"]["dose"]["cells"]])
        self.assertTrue(p["smoke"])
        self.assertEqual(p["evidence_mode"], "record")
        self.assertEqual(p["measure"]["perf_events"], box("bench-x86_64")["dose"]["hitm_events"])
        self.assertTrue(p["measure"]["stat_ops_probe"] and p["measure"]["per_thread"])
        rule = p["dose"]["pilot_rule"]
        self.assertEqual((rule["cell"], rule["cycles_per_transfer"], rule["min_share"], rule["h_expected"],
                          rule["instructions_tol"]), ("A", 100, 0.025, [1.0, 1.4], 0.005))
        self.assertIn("own worker cycles", rule["k_rule"])
        sm = c["smoke-dose.json"]
        self.assertEqual((sm["rounds"], sm["smoke"], sm["evidence_mode"]), (1, True, "record"))
        self.assertEqual(sm["arms"], c["dose.json"]["arms"])
        self.assertEqual(len(experiment.schedule(experiment.load(os.path.join(MT, "bench-x86_64",
                                                                             "smoke-dose.json")))), 13)
        # the evidence legs: base, stats-reject, own and shared at the cell's dose, 1 round per cell
        ev = c["dose-evidence.json"]
        self.assertEqual((ev["rounds"], ev["base_arm"], ev["comparisons"], ev["rotation_block"]), (1, "base", "base", 1))
        self.assertEqual([s["cell"] for s in ev["shapes"]], ["A", "B", "D"])
        eexp = experiment.load(os.path.join(MT, "bench-x86_64", "dose-evidence.json"))
        plan = experiment.schedule(eexp)
        self.assertEqual(len(plan), 12)
        per = {}
        for r, sh, a in plan:
            per.setdefault(sh["cell"], set()).add(a["name"])
        self.assertEqual(per, {"A": {"base", "stats-reject", "own-128", "shared-128"},
                               "B": {"base", "stats-reject", "own-128", "shared-128"},
                               "D": {"base", "stats-reject", "own-64", "shared-64"}})
        self.assertEqual([(x["cell"], x["counters"], x["reference"], x["shared"], x["aa"]) for x in ev["dose"]["cells"]],
                         [("A", 128, "own-128", "shared-128", None), ("B", 128, "own-128", "shared-128", None),
                          ("D", 64, "own-64", "shared-64", None)])
        self.assertEqual(ev["measure"]["perf_events"], box("bench-x86_64")["dose"]["hitm_events"])
        self.assertTrue(ev["measure"]["stat_ops_probe"])
        self.assertEqual(experiment.validate(eexp, allow_short=True), [])
        # the evidence smoke: one round in cell A, the same event list and probe, its own arms only
        se = c["smoke-dose-evidence.json"]
        self.assertEqual(([s["cell"] for s in se["shapes"]], se["rounds"], se["smoke"], se["evidence_mode"]),
                         (["A"], 1, True, "record"))
        self.assertEqual([a["name"] for a in se["arms"]], ["base", "stats-reject", "own-128", "shared-128"])
        self.assertEqual([a.get("settings") for a in se["arms"]], [a.get("settings") for a in ev["arms"][:4]])
        self.assertEqual(se["measure"], ev["measure"])
        self.assertEqual(len(experiment.schedule(experiment.load(os.path.join(MT, "bench-x86_64",
                                                                             "smoke-dose-evidence.json")))), 4)
        # the smoke of the run covers all 11 cell-arm pairs; the smoke check knows which arms run where
        SV = _mod("mt_smoke_valid", os.path.join(MT, "smoke_valid.py"))
        ok = [{"shape": sh["name"], "arm": a["name"], "round": 1, "verdict": {"valid": True}}
              for r, sh, a in experiment.schedule(experiment.load(os.path.join(MT, "bench-x86_64", "smoke-dose.json")))]
        self.assertEqual(len(ok), 13)
        self.assertIn(("mt-14w-one", "hot-shared-128"), {(m["shape"], m["arm"]) for m in ok})
        self.assertEqual({(m["shape"], m["arm"]) for m in ok},
                         {(sh, a["name"]) for a in c["dose.json"]["arms"] for sh in a["shapes"]})
        self.assertEqual(SV.check(sm, {"legs": ok}), [])
        self.assertEqual(SV.check(sm, {"legs": [m for m in ok if not (m["arm"] == "shared-64" and m["shape"] == "mt-28w")]}),
                         ["missing: mt-28w shared-64"])

    def leg(self, arm, shape="mt-14w-one", **sc):
        m = {"shape": shape, "arm": arm, "responses_raw": 420000,
             "sut_stats_window": {"http.ingress_http.downstream_rq_2xx": 420000,
                                  "http.ingress_http.downstream_cx_total": 0}, "sut_stats_window_ok": True,
             "stat_count": dict({"start_n": 128, "end_n": 128, "new_in_window": 0, "sum_per_request": 128.4}, **sc)}
        return m

    def test_evidence_items(self):
        from epl import evidence
        u = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
        arms = {a["name"]: a for a in u["arms"]}
        for a in u["arms"]:
            self.assertEqual(evidence.validate_items(a["evidence"], list(arms)), [], a["name"])
        dump = lambda tag, addr="0.0.0.0": {"x": [{"value_format": tag}] * 128, "stats_flush_interval": "240s",  # noqa: E731
                                            "l": {"address": addr, "port_value": 10110},
                                            "admin": {"address": "127.0.0.1", "port_value": 9921}}
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
        self.assertFalse(evidence.evaluate(good, sh, {"x": [{"value_format": "%DOWNSTREAM_LOCAL_PORT%"}]})["ok"])
        # a loopback listener (one local-address object for every connection of every worker)
        r = evidence.evaluate(good, sh, dump("%DOWNSTREAM_LOCAL_PORT%", "127.0.0.1"))
        self.assertEqual(r["failed"], ["listener address 0.0.0.0 (a local-address object per connection): "
                                       "values ['127.0.0.1']"])
        # a connection opened inside the window, in either arm
        for items, tag, leg_ in ((sh, "%DOWNSTREAM_LOCAL_PORT%", good),
                                 (own, "%DOWNSTREAM_REMOTE_PORT%",
                                  self.leg("own-128", start_n=128 * 224, end_n=128 * 224))):
            self.assertTrue(evidence.evaluate(leg_, items, dump(tag))["ok"])
            opened = dict(leg_, sut_stats_window=dict(leg_["sut_stats_window"],
                                                      **{"http.ingress_http.downstream_cx_total": 1}))
            r = evidence.evaluate(opened, items, dump(tag))
            self.assertEqual(r["failed"], ["no downstream connection opened during the window: 1, expected 0 +/- 0"])
        # increments per request within 0.5 of K, absolute
        for x, ok in ((127.5, True), (128.5, True), (127.4, False), (128.6, False)):
            m = dict(good, stat_count=dict(good["stat_count"], sum_per_request=x))
            self.assertEqual(evidence.evaluate(m, sh, dump("%DOWNSTREAM_LOCAL_PORT%"))["ok"], ok, x)
        self.assertFalse(evidence.evaluate(good, sh, dict(dump("%DOWNSTREAM_LOCAL_PORT%"),
                                                          stats_flush_interval="5s"))["ok"])  # a default flush
        for shape, conns in (("mt-14w-one", 224), ("mt-14w-split", 224)):
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
        # own-128 has no item for the 28-worker cell: a leg of it there would not pass by default
        r = evidence.evaluate(self.leg("own-128", "mt-28w", start_n=128 * 448, end_n=128 * 448), own, rd)
        self.assertTrue(r["ok"] is False or not [i for i in own if i.get("shape") == "mt-28w"])
        # the 64 arms: their own K, in cell A (224 connections) and cell D (448)
        low = arms["own-64"]["evidence"]
        self.assertEqual([i["shape"] for i in low if "shape" in i], ["mt-14w-one", "mt-28w"])
        for shape, conns in (("mt-14w-one", 224), ("mt-28w", 448)):
            leg64 = self.leg("own-64", shape, start_n=64 * conns, end_n=64 * conns, sum_per_request=64.1)
            self.assertTrue(evidence.evaluate(leg64, low, dump("%DOWNSTREAM_REMOTE_PORT%"))["ok"], shape)
            self.assertFalse(evidence.evaluate(dict(leg64, stat_count=dict(leg64["stat_count"], sum_per_request=64.6)),
                                               low, dump("%DOWNSTREAM_REMOTE_PORT%"))["ok"])
            # the 128 arms' increments per request in a 64 arm's leg: not accepted
            self.assertFalse(evidence.evaluate(dict(leg64, stat_count=dict(leg64["stat_count"], sum_per_request=128.0)),
                                               low, dump("%DOWNSTREAM_REMOTE_PORT%"))["ok"])
        self.assertFalse(evidence.evaluate(self.leg("own-64", "mt-28w", start_n=64 * 224, end_n=64 * 224,
                                                    sum_per_request=64.0), low, dump("%DOWNSTREAM_REMOTE_PORT%"))["ok"])
        a2 = arms["own-64-A2"]["evidence"]
        self.assertEqual([i["shape"] for i in a2 if "shape" in i], ["mt-28w"])
        # the evidence legs' base arm: no dose counters at all
        base = [a for a in MK.configs(box("bench-x86_64"), DOSE_RATES)["dose-evidence.json"]["arms"]
                if a["name"] == "base"][0]["evidence"]
        self.assertIn({"stat": "stat_count.start_n", "scope": "field", "equals": 0, "tol_abs": 0,
                       "label": "no dose counters"}, base)


HITM_U = ("mem_load_uops_l3_hit_retired.xsnp_hitm:u", "mem_load_uops_l3_miss_retired.remote_hitm:u")


def _dose_run(rho, rounds=15, aa_noise=0.003, ins_shared=None, seed=5, rho_low=0.01, rho_hot=0.06):
    """A synthetic dose run on the slot's config: per cell (shape name) the true ln(shared / own)
    at the cell's own dose, and in the second dose's cell the true ln(shared / own) at that dose.
    Own cycles are 545,000 plus 1,150 per counter (the logger's own cost). `rounds` decides
    whether it is a short run (under 12), as the box's dose.rounds does for the real config."""
    import random
    rng = random.Random(seed)
    exp = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
    exp["dose"].update(rounds=rounds, short_run=rounds < 12)
    low, hot = exp["dose"]["low"], exp["dose"]["hot"]
    legs = []
    for r in range(1, rounds + 1):
        for c in exp["dose"]["cells"]:
            K = c["counters"]
            b = (545e3 + 1150 * K) * rng.gauss(1, 0.004)
            ins = 162e3 + 2800 * K
            arms = [(c["reference"], b, ins), (c["aa"][0], b * rng.gauss(1, aa_noise), ins),
                    (c["shared"], b * math.exp(rho[c["shape"]]) * rng.gauss(1, 0.003),
                     ins * 1.0003 if ins_shared is None else ins * ins_shared)]
            if c["cell"] == low["cell"]:
                bl = (545e3 + 1150 * low["counters"]) * rng.gauss(1, 0.004)
                il = 162e3 + 2800 * low["counters"]
                arms += [(low["reference"], bl, il), (low["shared"], bl * math.exp(rho_low) * rng.gauss(1, 0.003), il)]
            if c["cell"] == hot["cell"]:
                # the hot counter stays in the worker's cache in own: cheaper than the spread own arm
                bh = (545e3 + 900 * hot["counters"]) * rng.gauss(1, 0.004)
                ih = 162e3 + 2800 * hot["counters"]
                arms += [(hot["reference"], bh, ih), (hot["shared"], bh * math.exp(rho_hot) * rng.gauss(1, 0.003), ih)]
            for arm, v, i in arms:
                legs.append({"leg_id": "r%02d-%s-%s" % (r, c["shape"], arm), "round": r, "shape": c["shape"], "arm": arm,
                             "verdict": {"valid": True}, "workers_cycles_per_req": v,
                             "per_req": {"instructions_u": i}, "sut_busy": 0.47})
    return {"experiment": exp, "legs": legs, "metadata": {"rounds_complete": rounds, "incomplete": False}}


L3_U = "mem_load_uops_retired.l3_hit:u"


def _dose_evidence(h=0.3, events=HITM_U, seed=6, foot=1.4, ops=17.0):
    """The evidence legs: per cell base, stats-reject, own and shared at the cell's dose; h HITM
    loads per update more in shared; `foot` clean L3 hits per update more in own."""
    import random
    rng = random.Random(seed)
    exp = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose-evidence.json"]
    legs = []
    for r in range(1, 5):
        for c in exp["dose"]["cells"]:
            K = c["counters"]
            for arm, x, l3 in (("base", 7.0, 0.0), ("stats-reject", 0.5, 0.0), (c["reference"], 8.0, K * (0.1 + foot)),
                               (c["shared"], 8.0 + h * K, K * 0.1)):
                x = x * rng.gauss(1, 0.02)
                legs.append({"leg_id": "e", "round": r, "shape": c["shape"], "arm": arm, "verdict": {"valid": True},
                             "workers_cycles_per_req": 545e3, "sut_busy": 0.38 if "28w" in c["shape"] else 0.36,
                             "responses": 420000,
                             "stat_ops": {"counter_incs": (ops - 4) * 420000, "histogram_samples": 4 * 420000,
                                          "counters_changed": []},
                             "per_req": {"events": {events[0]: 0.7 * x, events[1]: 0.3 * x, L3_U: 0.7 * x + l3}}})
    return {"experiment": exp, "legs": legs, "metadata": {"rounds_complete": 4, "incomplete": False}}


# true ln(shared / own): cells A and B at K = 128, cell D at K = 64
RHO = {"mt-14w-one": 0.02, "mt-14w-split": 0.05, "mt-28w": 0.025}


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
        self.assertEqual((UT.DOSE_SYS_PCT, UT.DOSE_Z, UT.AA_LIMIT_PCT, UT.DOSE_MIN_EFFECT_PCT, UT.DOSE_INSTR_TOL_PCT,
                          UT.DOSE_HITM_SHARE, UT.DOSE_MIN_ROUNDS, UT.DOSE_AA_ALPHA, UT.DOSE_L3_CYCLES),
                         (0.34, 1.96, 1.0, 1.0, 0.5, 0.15, 12, 0.05, 45.0))

    def test_statements_and_per_cell_dose(self):
        res = _dose_run(RHO)
        text, js, st = self.rows(res, _dose_evidence())
        self.assertEqual(list(st), ["S1", "S2", "S3", "S4", "S5"])
        self.assertIn("Holm over 5", text)
        self.assertEqual([(st[k]["kind"], st[k].get("cell") or st[k]["cells"], st[k]["counters"]) for k in st],
                         [("cell", "A", 128), ("cell", "B", 128), ("cell", "D", 64), ("socket", ["B", "A"], 128),
                          ("workers", ["D", "A"], 64)])
        self.assertEqual([st[k]["statement"] for k in ("S3", "S4", "S5")],
                         ["rho_D at K = 64 (28w, workers)", "socket: rho_B(128) - rho_A(128)",
                          "workers: rho_D(64) - rho_A(64): 28 workers on two sockets against 14 on one socket "
                          "(confounded with the socket split)"])
        for k, rho in (("S1", 2.0), ("S2", 5.0), ("S3", 2.5)):
            self.assertAlmostEqual(st[k]["w"]["mean"], rho, delta=0.4)
            self.assertEqual(st[k]["verdict"], "finding: line transfer")
        # every cell's rho, A/A and price use that cell's own arms and its own K
        legs = lambda shape, arm: {m["round"]: m["workers_cycles_per_req"] for m in res["legs"]  # noqa: E731
                                   if m["shape"] == shape and m["arm"] == arm}
        o, sh, a2 = legs("mt-28w", "own-64"), legs("mt-28w", "shared-64"), legs("mt-28w", "own-64-A2")
        dD = [100 * math.log(sh[r] / o[r]) for r in sorted(o)]
        self.assertAlmostEqual(st["S3"]["w"]["mean"], sum(dD) / 15)
        self.assertAlmostEqual(js["cells"]["D"]["price"]["mean"], sum((sh[r] - o[r]) / 64 for r in o) / 15)
        aa = UT.stats.paired_log_ratio([o[r] for r in sorted(o)], [a2[r] for r in sorted(o)])
        self.assertAlmostEqual(js["cells"]["D"]["aa"]["hw"], aa["half_width_pct"])
        self.assertEqual((js["cells"]["D"]["counters"], js["cells"]["D"]["own"], js["cells"]["A"]["counters"]),
                         (64, "own-64", 128))
        self.assertAlmostEqual(js["cells"]["A"]["price"]["mean"], (545e3 + 1150 * 128) * (math.exp(0.02) - 1) / 128,
                               delta=10)
        # S4: cells B and A at 128, paired by round, two widening terms
        ra, rb = js["cells"]["A"]["rho_rounds"], js["cells"]["B"]["rho_rounds"]
        self.assertAlmostEqual(st["S4"]["w"]["hi"], UT.widened([rb[r] - ra[r] for r in sorted(ra)], terms=2)["hi"])
        self.assertEqual(st["S4"]["verdict"], "resolved: higher across sockets")
        # S5: cell D at 64 against cell A's second dose (own-64 and shared-64 in cell A), not A's 128 pair
        ao, as_ = legs("mt-14w-one", "own-64"), legs("mt-14w-one", "shared-64")
        dA = {r: 100 * math.log(as_[r] / ao[r]) for r in ao}
        self.assertEqual(js["low"]["rho_rounds"], dA)
        want = UT.widened([dD[i] - dA[r] for i, r in enumerate(sorted(o))], terms=2)
        self.assertAlmostEqual(st["S5"]["w"]["mean"], want["mean"])
        self.assertAlmostEqual(st["S5"]["w"]["hi"], want["hi"])
        self.assertAlmostEqual(st["S5"]["w"]["mean"], 1.5, delta=0.4)   # 2.5 - 1.0, not 2.5 - 2.0
        self.assertEqual(st["S5"]["verdict"], "resolved: higher at 28 workers on two sockets against 14 on one socket; the worker count and the socket split are not separated")
        self.assertEqual((js["low"]["counters"], js["low"]["own"], js["low"]["cell"]), (64, "own-64", "A"))
        self.assertAlmostEqual(js["low"]["price"]["mean"], sum((as_[r] - ao[r]) / 64 for r in ao) / 15)
        hp = UT.stats.holm([st[k]["w"]["p"] for k in st])
        self.assertEqual([st[k]["holm_p"] for k in st], hp)
        self.assertIn("The second dose's pair in cell A uses that cell's A/A (own-128-A2 against own-128)", text)
        # either spelling of the HITM events
        _, _, st2 = self.rows(_dose_run(RHO), _dose_evidence(events=UT.HITM))
        self.assertEqual(st2["S1"]["verdict"], "finding: line transfer")

    def test_workers_contrast_gates(self):
        # the A/A of cell A's 64 pair is cell A's own-128 A/A: when it fails, S5 has no verdict
        res = _dose_run(RHO)
        for m in res["legs"]:
            if m["arm"] == "own-128-A2" and m["shape"] == "mt-14w-one":
                m["workers_cycles_per_req"] *= 1.0 + (0.04 if m["round"] % 2 else -0.04)
        _, js, st = self.rows(res, _dose_evidence())
        self.assertTrue(st["S5"]["verdict"].startswith("no verdict: cell A A/A failed"))
        self.assertTrue(st["S1"]["verdict"].startswith("no verdict: cell A A/A failed"))
        self.assertEqual(st["S3"]["verdict"], "finding: line transfer")   # cell D has its own A/A at 64
        # cell D's own A/A (own-64-A2) failing takes S3 and S5, not S1
        res = _dose_run(RHO)
        for m in res["legs"]:
            if m["arm"] == "own-64-A2":
                m["workers_cycles_per_req"] *= 1.0 + (0.04 if m["round"] % 2 else -0.04)
        _, js, st = self.rows(res, _dose_evidence())
        self.assertTrue(st["S3"]["verdict"].startswith("no verdict: cell D A/A failed"))
        self.assertTrue(st["S5"]["verdict"].startswith("no verdict: cell D A/A failed"))
        self.assertEqual(st["S1"]["verdict"], "finding: line transfer")
        # under 12 valid rounds of cell A's 64 pair: S5 incomplete, S1 and S3 untouched
        res = _dose_run(RHO)
        res["legs"] = [m for m in res["legs"] if not (m["shape"] == "mt-14w-one" and m["arm"] == "shared-64"
                                                      and m["round"] > 11)]
        _, js, st = self.rows(res, _dose_evidence())
        self.assertEqual(st["S5"]["verdict"], "incomplete, no verdict (cell A: 11 valid rounds of the 12 a verdict needs)")
        self.assertEqual((st["S1"]["verdict"], st["S3"]["verdict"]), ("finding: line transfer",) * 2)
        # cell A's 64 pair an invalid comparison: no workers verdict
        _, js, st = self.rows(_dose_run(RHO, rho_low=-0.03), _dose_evidence())
        self.assertEqual(st["S5"]["verdict"], "no verdict: cell A at K = 64 comparison invalid (own slower than shared)")
        # at K = 64 an effect near 1% gives bounds, as expected, never "no cost"
        _, js, st = self.rows(_dose_run(dict(RHO, **{"mt-28w": 0.008}), rho_low=0.008), _dose_evidence())
        self.assertTrue(st["S3"]["verdict"].startswith("bound: rho_D <= "))
        self.assertTrue(st["S5"]["verdict"].startswith("not resolved: <= "))

    def test_aa_gate(self):
        # unresolved means the A/A's raw p above 0.05: a small, consistent offset fails it even
        # with a half-width far under 1% (three cells would dilute it under Holm)
        res = _dose_run(RHO)
        own = {m["round"]: m["workers_cycles_per_req"] for m in res["legs"]
               if m["arm"] == "own-128" and m["shape"] == "mt-14w-split"}
        for m in res["legs"]:
            if m["arm"] == "own-128-A2" and m["shape"] == "mt-14w-split":
                m["workers_cycles_per_req"] = own[m["round"]] * (1.00095 + (0.0015 if m["round"] % 2 else -0.0015))
        _, js, st = self.rows(res, _dose_evidence())
        aa = js["cells"]["B"]["aa"]
        self.assertLess(aa["hw"], 0.2)
        self.assertTrue(0.05 / 3 < aa["t_p"] < 0.05, aa["t_p"])  # passes under Holm over three, fails raw
        self.assertFalse(aa["ok"])
        # a cell whose A/A fails has no verdict: never a bound, and neither have its contrasts
        self.assertTrue(st["S2"]["verdict"].startswith("no verdict: cell B A/A failed: half-width "))
        self.assertNotIn("bound", st["S2"]["verdict"])
        self.assertTrue(st["S4"]["verdict"].startswith("no verdict: cell B A/A failed"))
        self.assertNotIn("<=", st["S4"]["verdict"])
        self.assertEqual(st["S1"]["verdict"], "finding: line transfer")
        self.assertEqual(st["S5"]["verdict"], "resolved: higher at 28 workers on two sockets against 14 on one socket; the worker count and the socket split are not separated")
        # a half-width over 1% fails it too
        _, js, st = self.rows(_dose_run(RHO, aa_noise=0.03), _dose_evidence())
        self.assertGreater(js["cells"]["A"]["aa"]["hw"], 1.0)
        self.assertTrue(all(st[k]["verdict"].startswith("no verdict: cell ") for k in st))

    def test_invalid_comparison(self):
        # an interval entirely below 0: own slower than shared; not a bound, no negative price, no model
        text, js, st = self.rows(_dose_run(dict(RHO, **{"mt-28w": -0.03})), _dose_evidence())
        self.assertLess(st["S3"]["w"]["hi"], 0)
        self.assertEqual(st["S3"]["verdict"], "comparison invalid (own slower than shared)")
        self.assertEqual(st["S5"]["verdict"], "no verdict: cell D at K = 64 comparison invalid (own slower than shared)")
        self.assertEqual(st["S4"]["verdict"], "resolved: higher across sockets")
        self.assertEqual([r["why"] for r in js["model"]["cells"]["D"]], ["comparison invalid (own slower than shared)"])
        self.assertNotIn("x_pct", js["model"]["cells"]["D"][0])
        self.assertIn("Cell D has no model row (comparison invalid (own slower than shared))", text)
        self.assertEqual(js["model"]["headline"]["two sockets"], js["model"]["cells"]["B"][0]["x_pct"])
        # an interval that reaches 0 from below is a bound, not invalid
        _, _, st = self.rows(_dose_run(dict(RHO, **{"mt-28w": -0.004})), _dose_evidence())
        self.assertTrue(st["S3"]["verdict"].startswith("bound: rho_D <= "))

    def test_minimum_rounds(self):
        # 12 valid rounds of own, shared and the A/A arm in a cell for a verdict
        res = _dose_run(RHO)
        res["legs"] = [m for m in res["legs"] if not (m["shape"] == "mt-28w" and m["arm"] == "shared-64"
                                                      and m["round"] > 11)]
        text, js, st = self.rows(res, _dose_evidence())
        self.assertEqual(js["cells"]["D"]["valid_rounds"], 11)
        want = "incomplete, no verdict (cell D: 11 valid rounds of the 12 a verdict needs)"
        self.assertEqual((st["S3"]["verdict"], st["S5"]["verdict"]), (want, want))
        self.assertEqual(st["S1"]["verdict"], "finding: line transfer")
        self.assertEqual(js["model"]["cells"]["D"][0]["why"], experiment.INCOMPLETE)
        # the A/A arm counts: 15 pairs of own and shared are not enough when the A/A has 11
        res = _dose_run(RHO)
        res["legs"] = [m for m in res["legs"] if not (m["shape"] == "mt-14w-one" and m["arm"] == "own-128-A2"
                                                      and m["round"] > 11)]
        _, js, st = self.rows(res, _dose_evidence())
        self.assertEqual((js["cells"]["A"]["valid_rounds"], len(js["cells"]["A"]["rho_rounds"])), (11, 15))
        self.assertTrue(st["S1"]["verdict"].startswith("incomplete, no verdict (cell A"))
        self.assertTrue(st["S4"]["verdict"].startswith("incomplete") and st["S5"]["verdict"].startswith("incomplete"))
        # exactly 12 is enough
        res = _dose_run(RHO)
        res["legs"] = [m for m in res["legs"] if not (m["shape"] == "mt-28w" and m["round"] > 12)]
        _, js, st = self.rows(res, _dose_evidence())
        self.assertEqual(js["cells"]["D"]["valid_rounds"], 12)
        self.assertEqual(st["S3"]["verdict"], "finding: line transfer")

    def test_line_transfer_label(self):
        # HITM:u (shared - own) per request >= 0.15 x the cell's own K: 19.2 at 128, 9.6 at 64
        res = _dose_run(RHO)
        _, _, st = self.rows(res)  # no evidence legs
        self.assertTrue(st["S1"]["verdict"].startswith("finding, not called line transfer"))
        self.assertIn("no HITM:u evidence", st["S1"]["verdict"])
        # h = 0.16 passes at both doses; h = 0.14 fails at both, each against its own threshold
        _, _, st = self.rows(res, _dose_evidence(h=0.16))
        self.assertEqual({st[k]["verdict"] for k in ("S1", "S2", "S3")}, {"finding: line transfer"})
        _, js, st = self.rows(res, _dose_evidence(h=0.14))
        self.assertIn("under 0.15 x K = 19.2", st["S1"]["verdict"])
        self.assertIn("under 0.15 x K = 9.6", st["S3"]["verdict"])
        self.assertFalse(st["S1"]["line_transfer"] or st["S3"]["line_transfer"])
        self.assertAlmostEqual(js["evidence"]["D"]["hitm_shared_minus_own"]["mean"], 0.14 * 64, delta=1.0)
        # 12 HITM loads per request in shared over own: enough for cell D's 64 (9.6), not for a 128 cell (19.2)
        ev = _dose_evidence(h=0.3)
        for m in ev["legs"]:
            if m["arm"].startswith("shared"):
                m["per_req"]["events"][HITM_U[0]], m["per_req"]["events"][HITM_U[1]] = 8.0 + 12.0, 0.0
            elif m["arm"].startswith("own"):
                m["per_req"]["events"][HITM_U[0]], m["per_req"]["events"][HITM_U[1]] = 8.0, 0.0
        _, _, st = self.rows(res, ev)
        self.assertEqual(st["S3"]["verdict"], "finding: line transfer")
        self.assertTrue(st["S1"]["verdict"].startswith("finding, not called line transfer"))
        # instructions: 1% more in shared
        _, _, st = self.rows(_dose_run(RHO, ins_shared=1.01), _dose_evidence())
        self.assertIn("instructions:u per request differ", st["S2"]["verdict"])
        self.assertTrue(st["S2"]["verdict"].startswith("finding, not called line transfer"))

    def test_linearity_is_a_description(self):
        # P(K) = (exp(rho_K) - 1) x C / K on the means; unwidened delta-method interval
        rk = {r: 2.0 + 0.1 * (r % 3 - 1) for r in range(1, 16)}
        rl = {r: 0.5 + 0.02 * (r % 5 - 2) for r in range(1, 16)}
        w = UT.linearity(rk, rl, 540e3, 530e3, 128, 32)
        mk, ml = sum(rk.values()) / 1500.0, sum(rl.values()) / 1500.0
        pk, pl = math.expm1(mk) * 540e3 / 128, math.expm1(ml) * 530e3 / 32
        self.assertAlmostEqual(w["price_k"], pk)
        self.assertAlmostEqual(w["price_low"], pl)
        self.assertAlmostEqual(w["mean"], 100 * math.log(pk / pl))
        a, b = math.exp(mk) / math.expm1(mk), math.exp(ml) / math.expm1(ml)
        xs, ys = [rk[r] / 100 for r in sorted(rk)], [rl[r] / 100 for r in sorted(rl)]
        cov = sum((x - mk) * (y - ml) for x, y in zip(xs, ys)) / 14
        var = (a * a * UT.stats.stdev(xs) ** 2 + b * b * UT.stats.stdev(ys) ** 2 - 2 * a * b * cov) / 15
        self.assertAlmostEqual(w["se"], 100 * math.sqrt(var))
        self.assertAlmostEqual(w["hi"] - w["mean"], 1.96 * w["se"])  # no widening term
        self.assertNotIn("p", w)
        same = UT.linearity({r: 2.0 for r in range(1, 16)}, {r: 2.0 for r in range(1, 16)}, 500e3, 500e3, 128, 32)
        self.assertAlmostEqual(same["mean"], 100 * math.log(0.25))
        neg = UT.linearity(rk, {r: -0.2 for r in rk}, 540e3, 530e3, 128, 32)
        self.assertEqual((neg["mean"], neg["why"]), (None, "the price is not positive at Klow"))
        self.assertIsNone(UT.linearity({1: 2.0}, {1: 0.5}, 1.0, 1.0, 128, 32)["mean"])
        # in the table: the two doses of cell A (128 and 64), described, never a statement
        text, js, st = self.rows(_dose_run(RHO), _dose_evidence())
        self.assertIn("Linearity in cell A (a description, not a statement): on the means", text)
        self.assertIn("ln(P(128) / P(64)) = ", text)
        lin = js["low"]["lin"]
        self.assertAlmostEqual(lin["price_k"], math.expm1(lin["rho_k"] / 100) * js["cells"]["A"]["own_k"] / 128)
        self.assertAlmostEqual(lin["price_low"], math.expm1(lin["rho_low"] / 100) * js["low"]["own_k"] / 64)
        self.assertEqual(len(st), 5)
        text, _, _ = self.rows(_dose_run(RHO, rho_low=-0.004), _dose_evidence())
        self.assertIn("not computable (the price is not positive at Klow)", text)

    def test_bounds(self):
        # under 1%: a bound with the widened interval's upper end, never "no effect"
        text, js, st = self.rows(_dose_run({"mt-14w-one": 0.004, "mt-14w-split": 0.02, "mt-28w": 0.0},
                                           rho_low=0.001), _dose_evidence())
        r = st["S1"]
        self.assertEqual(r["verdict"].split(" (")[0], "bound: rho_A <= %+.2f%%" % r["w"]["hi"])
        self.assertIn("under 1%", r["verdict"])
        self.assertFalse(r["finding"])
        self.assertIn("includes 0", st["S3"]["verdict"])
        self.assertTrue(st["S3"]["verdict"].startswith("bound: rho_D <= "))
        self.assertEqual(st["S2"]["verdict"], "finding: line transfer")
        self.assertIn("is a bound on rho, not evidence of no cost", text)
        # an estimate over 1% but inside the A/A's reach is a bound too
        res = _dose_run({"mt-14w-one": 0.012, "mt-14w-split": 0.05, "mt-28w": 0.02})
        own = {m["round"]: m["workers_cycles_per_req"] for m in res["legs"]
               if m["arm"] == "own-128" and m["shape"] == "mt-14w-one"}
        for m in res["legs"]:
            if m["arm"] == "own-128-A2" and m["shape"] == "mt-14w-one":
                m["workers_cycles_per_req"] = own[m["round"]] * (1.005 + (0.016 if m["round"] % 2 else -0.016))
        _, js, st = self.rows(res, _dose_evidence())
        aa = js["cells"]["A"]["aa"]
        self.assertTrue(aa["ok"] and aa["hw"] <= 1.0 and aa["t_p"] > 0.05)
        self.assertGreater(st["S1"]["w"]["mean"], 1.0)
        self.assertGreater(aa["reach"], st["S1"]["w"]["mean"])
        self.assertIn("within the A/A's reach", st["S1"]["verdict"])
        self.assertTrue(st["S1"]["verdict"].startswith("bound: rho_A <= "))

    def test_incomplete(self):
        res = _dose_run(RHO)
        res["metadata"]["incomplete"] = True
        text, js, st = self.rows(res, _dose_evidence())
        self.assertEqual({r["verdict"] for r in st.values()}, {experiment.INCOMPLETE})
        self.assertEqual(len(st), 5)
        self.assertEqual(js["model"]["headline"], {})
        self.assertIn("no model row", text)

    def test_prices_and_footprint_band(self):
        text, js, _ = self.rows(_dose_run(RHO), _dose_evidence(foot=1.4))
        pr = {(p["cell"], p["counters"]): p for p in js["prices"]}
        self.assertEqual(list(pr), [("A", 128), ("A", 64), ("B", 128), ("D", 64)])
        # d: clean L3 hits per update, own minus shared, from the evidence legs of that cell and dose
        for key in (("A", 128), ("B", 128), ("D", 64)):
            p = pr[key]
            self.assertAlmostEqual(p["footprint_d"], 1.4, delta=0.05)
            self.assertAlmostEqual(js["evidence"][key[0]]["footprint"]["mean"], p["footprint_d"])
            # the band: P + d x 45 cycles, on the measured mean price
            self.assertAlmostEqual(p["band"], p["price"]["mean"] + p["footprint_d"] * 45.0)
        self.assertAlmostEqual(pr[("D", 64)]["price"]["mean"], (545e3 + 1150 * 64) * (math.exp(0.025) - 1) / 64, delta=12)
        # the evidence legs run cell A at 128 only: no band for its 64 pair, and none invented
        self.assertEqual((pr[("A", 64)]["footprint_d"], pr[("A", 64)]["band"]), (None, None))
        self.assertIn("MODELLED upper figure", text)
        self.assertIn("P is measured and likely understates the sharing price", text)
        # per update means per that cell's K: 64 x 1.5 extra L3 hits per request in own is d = 1.5 in cell D
        self.assertAlmostEqual(UT.clean_l3({"per_req": {"events": {L3_U: 100.0, HITM_U[0]: 36.0}}}, 64), 1.0)
        self.assertIsNone(UT.clean_l3({"per_req": {"events": {L3_U: 100.0}}}, 64))
        _, js, _ = self.rows(_dose_run(RHO), _dose_evidence(foot=-0.2))
        p = {(x["cell"], x["counters"]): x for x in js["prices"]}[("B", 128)]
        self.assertLess(p["band"], p["price"]["mean"])  # printed as computed
        # no evidence legs: prices, no band
        _, js, _ = self.rows(_dose_run(RHO))
        self.assertTrue(all(x["band"] is None for x in js["prices"]))

    def test_model_row(self):
        text, js, st = self.rows(_dose_run(RHO), _dose_evidence(ops=17.0))
        self.assertIn("## Model row for the plain config (a MODEL, not a measurement)", text)
        self.assertAlmostEqual(UT.model_price({"hi": 2.5}, 500e3, 128), math.expm1(0.025) * 500e3 / 128)
        self.assertIsNone(UT.model_price({"n": 1, "mean": 2.0}, 500e3, 128))
        self.assertIsNone(UT.model_price({"hi": 2.5}, None, 128))
        for cell, i, K in (("A", "S1", 128), ("B", "S2", 128), ("D", "S3", 64)):
            m, e, c = js["model"]["cells"][cell][0], js["evidence"][cell], js["cells"][cell]
            self.assertEqual(m["dose"], K)
            # P from the widened upper end of rho, the cell's own cycles and the cell's own K
            self.assertAlmostEqual(m["P"], math.expm1(st[i]["w"]["hi"] / 100.0) * c["own_k"] / K)
            # T: the plain config's store-stat operations per request from the probe, not a HITM figure
            self.assertAlmostEqual(m["T"], 17.0)
            self.assertAlmostEqual(m["x_pct"], 100 * 17.0 * m["P"] / 545e3)
            # beside it, the HITM-scaled figure: HITM:u (base - reject) x P / h, over C
            self.assertAlmostEqual(m["hitm_scaled_pct"],
                                   100 * e["hitm_base_minus_reject"]["mean"] * m["P"] / e["h"] / 545e3)
            self.assertAlmostEqual(e["h"], 0.3, delta=0.03)
        # T follows the probe
        _, js2, _ = self.rows(_dose_run(RHO), _dose_evidence(ops=25.0))
        self.assertAlmostEqual(js2["model"]["cells"]["B"][0]["x_pct"] / js["model"]["cells"]["B"][0]["x_pct"], 25 / 17.0,
                               delta=0.001)
        # an h that is not positive only drops the comparison figure
        _, js3, _ = self.rows(_dose_run(RHO), _dose_evidence(h=-0.1))
        self.assertNotIn("hitm_scaled_pct", js3["model"]["cells"]["A"][0])
        self.assertIn("x_pct", js3["model"]["cells"]["A"][0])
        # cell A quotes both prices: at 128 and at 64
        a = js["model"]["cells"]["A"]
        self.assertEqual([r["dose"] for r in a], [128, 64])
        self.assertAlmostEqual(a[1]["P"], math.expm1(js["low"]["rho"]["hi"] / 100.0) * js["low"]["own_k"] / 64)
        self.assertEqual([len(js["model"]["cells"][c]) for c in ("B", "D")], [1, 1])
        self.assertIn("cell A %.2f%% with the price at 128 counters (%.2f%% with the band); cell A %.2f%% with the "
                      "price at 64 counters" % (a[0]["x_pct"], a[0]["x_band_pct"], a[1]["x_pct"]), text)
        # one-socket and two-socket figures apart, each marked a model
        self.assertIn("**MODEL, one socket:** sharing store stats across 14 workers (cell A), 36% busy, costs about ",
                      text)
        self.assertIn("**MODEL, two sockets:** sharing store stats across 14 workers (cell B) and 28 workers (cell D), "
                      "36-38% busy, costs about ", text)
        # no "at most" on the P-based figure; the band figure is the "up to"
        self.assertNotIn("at most", text[text.index("## Model row"):])
        for word in ("one socket", "two sockets"):
            x, y = js["model"]["headline"][word], js["model"]["headline_band"][word]
            self.assertIn("costs about %.2f%% of worker cycles per request in the measured-price model, up to %.2f%% "
                          "with the footprint band" % (x, y), text)
            self.assertGreater(y, x)
        # the band column: T x (P + d x 45) / C, d from the evidence legs of that cell and dose
        for cell in ("A", "B", "D"):
            m = js["model"]["cells"][cell][0]
            dd = js["evidence"][cell]["footprint"]["mean"]
            self.assertAlmostEqual(m["footprint_d"], dd)
            self.assertAlmostEqual(m["x_band_pct"], 100 * m["T"] * (m["P"] + dd * 45.0) / m["C"])
        self.assertNotIn("x_band_pct", a[1])  # no evidence legs at cell A's 64: no band figure, none invented
        self.assertEqual(js["model"]["headline_band"]["two sockets"],
                         max(js["model"]["cells"][c][0]["x_band_pct"] for c in ("B", "D")))
        self.assertIn("MODEL with the footprint band, T x (P + d x 45) / C", text)
        self.assertEqual(text.count("not measured in the plain config"), 2)
        self.assertEqual(js["model"]["headline"]["one socket"], max(r["x_pct"] for r in a))
        self.assertEqual(js["model"]["headline"]["two sockets"],
                         max(js["model"]["cells"][c][0]["x_pct"] for c in ("B", "D")))
        # without the evidence legs there is no model row, and the text says what is missing
        text, js, _ = self.rows(_dose_run(RHO))
        self.assertIn("No evidence legs given", text)
        self.assertEqual(js["model"], {"cells": {}})
        self.assertNotIn("**MODEL", text)
        # no probe: no model
        ev = _dose_evidence()
        for m in ev["legs"]:
            m.pop("stat_ops")
        text, js, _ = self.rows(_dose_run(RHO), ev)
        self.assertEqual(js["model"]["cells"]["A"][0]["why"], "no stat-operation probe of base")
        # a cell without a verdict (its A/A failed) has no model row either
        text, js, _ = self.rows(_dose_run(RHO, aa_noise=0.03), _dose_evidence())
        self.assertEqual(js["model"]["cells"]["B"][0]["why"], "the cell has no verdict (A/A failed)")
        self.assertEqual(js["model"]["headline"], {})

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
    GATE = _mod("mt_dose_gate", os.path.join(MT, "dose_gate.py"))

    def run_(self, h=1.2, base=540e3, ins_extra=0.0, mut=None, foot=None):
        """foot: {connections per worker: clean L3 hits per update the own arm has above shared}."""
        foot = foot or {16: 0.30, 8: 0.05}
        cfg = MK.configs(box("bench-x86_64"))["dose-pilot.json"]
        legs = []
        for s in cfg["shapes"]:
            conns, c = s["workers"] * s["connections_per_worker"], s["connections_per_worker"]
            for a in cfg["arms"]:
                if a.get("shapes") is not None and s["name"] not in a["shapes"]:
                    continue
                n = a["name"]
                k = int(n.split("-")[1]) if "-" in n else 0
                sh = n.startswith("shared")
                hitm = 7.0 + (h * k if sh else 0.0)
                m = {"shape": s["name"], "arm": n, "round": 1, "verdict": {"valid": True},
                     "workers_cycles_per_req": base * (1.0 + (0.0002 * k if sh else 0.0)), "responses": 420000,
                     "sut_busy": 0.36, "client_headroom": 0.5, "client_pending_total": 14, "client_workers": 14,
                     "sut_foreign_cpus": 0.01, "perf_min_running_pct": 100.0, "wall_s": 60.0,
                     "per_req": {"instructions_u": 200e3 + 300 * k + (ins_extra if sh else 0.0),
                                 # L3 hits: the HITM loads plus the clean ones (own: its footprint)
                                 "events": {HITM_U[0]: hitm, HITM_U[1]: 0.0,
                                            L3_U: hitm + k * (0.10 + (0.0 if sh else foot.get(c, 0.0)))}},
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

    def ov(self, cfg):
        return {a["name"]: [] for a in cfg["arms"]}

    def test_answers(self):
        cfg, res = self.run_()
        rep = self.DP.answers(cfg, res, self.ov(cfg))
        self.assertTrue(rep["ok"], rep["problems"])
        self.assertEqual(len(res["legs"]), 17)
        self.assertEqual(len(rep["legs"]), 17)
        self.assertEqual(len(rep["pairs"]), 8)
        byp = {(r["cell"], r["connections"], r["k"], r["role"]): r for r in rep["pairs"]}
        p = byp[("A", 16, 128, "k")]
        self.assertAlmostEqual(p["h"], 1.2)
        self.assertAlmostEqual(p["rho_pct"], 100 * math.log(1 + 0.0002 * 128))
        self.assertAlmostEqual(p["instr_pct"], 0.0)
        # clean L3 hits per update: (L3 hits - local HITM) / K; own minus shared is the footprint
        self.assertAlmostEqual(p["clean_l3_own"], 0.40)
        self.assertAlmostEqual(p["clean_l3_shared"], 0.10)
        self.assertAlmostEqual(p["footprint"], 0.30)
        self.assertAlmostEqual(byp[("A", 8, 128, "connections")]["footprint"], 0.05)
        self.assertAlmostEqual(self.DP.clean_l3({"per_req": {"events": {L3_U: 100.0, HITM_U[0]: 36.0}}}, 128), 0.5)
        self.assertIsNone(self.DP.clean_l3({"per_req": {"events": {L3_U: 100.0}}}, 128))
        # K: 1.2 x K x 100 / own cycles (540,000): 1.42% at 64, 2.84% at 128
        self.assertEqual(rep["q3"]["k"], 128)
        self.assertAlmostEqual(rep["q3"]["rows"][0]["share"], 1.2 * 64 * 100 / 540e3)
        # connections: the smaller footprint term, its gates passing
        self.assertEqual(rep["q4"]["terms"], {8: byp[("A", 8, 128, "connections")]["footprint"], 16: p["footprint"]})
        self.assertEqual(rep["q4"]["gates"], {8: True, 16: True})
        self.assertEqual(rep["q4"]["connections"], 8)
        self.assertEqual(rep["recommend"], {"counters": 128, "connections": 8})
        # h with its parts: local and remote HITM loads per request, own and shared apart
        self.assertEqual(p["hitm_own"], {"local": 7.0, "remote": 0.0})
        self.assertEqual(p["hitm_shared"], {"local": 7.0 + 1.2 * 128, "remote": 0.0})
        self.assertEqual(self.DP.hitm_parts({"per_req": {"events": {UT.HITM[0]: 3.0, HITM_U[1]: 1.5}}}), (3.0, 1.5))
        self.assertEqual(self.DP.hitm_parts({}), (None, None))
        self.assertEqual(rep["rates_key"], "bench-x86_64-dose-1")
        # seconds per leg and what that makes of the run
        self.assertEqual((rep["q5"]["mean_s"], rep["q5"]["max_s"]), (60.0, 60.0))
        self.assertAlmostEqual(rep["q5"]["run_h"], 78 * 60 / 3600.0)
        self.assertAlmostEqual(rep["q5"]["evidence_min"], 12.0)
        self.assertEqual(rep["q6"]["largest"]["start_n"], 2 * 128 * 448)
        t = self.DP.text(rep, cfg)
        for needle in ("1. bootstrap --mode validate: base OK", "-> K = 128", "-> 8 connections per worker",
                       "own local 7.00 remote 0.00, shared local 160.60 remote 0.00; (shared - own) local +153.60 remote "
                       "+0.00",
                       "ONE ROUND each (not an estimate)", "loopback against wildcard listener at K = 128",
                       "seconds per leg: mean 60, max 60 over 17 legs; at the mean the 78-leg run takes 1.30 h and the "
                       "12 evidence legs 12 min", "client slack 7.0 s", "(exploratory)",
                       'pilot OK: recommend {"bench-x86_64-dose-1": {"counters": 128, "connections": 8}}'):
            self.assertIn(needle, t)
        self.assertNotIn("OVER HALF THE SLACK", t)

        def slow(m):
            m["stat_count"]["pre_window_s"] = 4.2
        cfg, res = self.run_(mut=slow)
        self.assertIn("OVER HALF THE SLACK", self.DP.text(self.DP.answers(cfg, res, {}), cfg))

    def test_k_rule_divides_by_own_cycles(self):
        rule = {"min_share": 0.025}
        self.assertEqual(self.DP.choose_k([{"k": 256, "share": 0.05}, {"k": 64, "share": 0.02},
                                           {"k": 128, "share": 0.025}], rule), 128)
        self.assertIsNone(self.DP.choose_k([{"k": 64, "share": 0.01}, {"k": 128, "share": None}], rule))
        cfg, res = self.run_(h=1.4, base=300e3)   # 1.4 x 64 x 100 / 300,000 = 2.99%
        self.assertEqual(self.DP.answers(cfg, res, self.ov(cfg))["q3"]["k"], 64)
        cfg, res = self.run_(h=1.0, base=600e3)   # 2.13% at 128, 4.27% at 256
        self.assertEqual(self.DP.answers(cfg, res, self.ov(cfg))["q3"]["k"], 256)
        # the divisor is each K's own arm, not base: a far slower base changes nothing

        def slow_base(m):
            if m["arm"] == "base":
                m["workers_cycles_per_req"] *= 3
        cfg, res = self.run_(mut=slow_base)
        self.assertEqual(self.DP.answers(cfg, res, self.ov(cfg))["q3"]["k"], 128)

        def slow_own(m):   # own-128 costs 30% more than own-64: 128 no longer reaches 2.5%
            if m["arm"] == "own-128" and m["shape"] == "mt-14w-one":
                m["workers_cycles_per_req"] *= 1.3
        cfg, res = self.run_(mut=slow_own)
        rep = self.DP.answers(cfg, res, self.ov(cfg))
        self.assertAlmostEqual(rep["q3"]["rows"][1]["share"], rep["q3"]["h_mean"] * 128 * 100 / (540e3 * 1.3))
        self.assertEqual(rep["q3"]["k"], 256)
        cfg, res = self.run_(h=0.2)               # under 2.5% even at 256
        rep = self.DP.answers(cfg, res, self.ov(cfg))
        self.assertIsNone(rep["q3"]["k"])
        self.assertFalse(rep["ok"])
        t = self.DP.text(rep, cfg)
        self.assertIn("NO K", t)
        self.assertIn("outside the expected range", t)
        self.assertIn("pilot NOT clean", t)

    def test_connections_rule(self):
        ch = self.DP.choose_connections
        self.assertEqual(ch({16: 0.30, 4: 0.05}, {16: True, 4: True}), 4)
        self.assertEqual(ch({16: 0.02, 4: 0.05}, {16: True, 4: True}), 16)
        self.assertEqual(ch({16: -0.40, 4: 0.05}, {16: True, 4: True}), 4)   # the size of the term counts
        self.assertEqual(ch({16: 0.30, 4: 0.05}, {16: True, 4: False}), 16)  # its gates fail: the other count
        self.assertIsNone(ch({16: 0.30, 4: 0.05}, {16: False, 4: False}))
        self.assertIsNone(ch({16: 0.30, 4: None}, {16: True, 4: True}))      # no term: the rule cannot be applied
        self.assertEqual(ch({16: 0.05, 4: 0.05}, {16: True, 4: True}), 16)   # a tie keeps the larger count
        cfg, res = self.run_(foot={16: 0.02, 8: 0.20})
        self.assertEqual(self.DP.answers(cfg, res, self.ov(cfg))["recommend"], {"counters": 128, "connections": 16})

        # an invalid 28-worker leg at 8 connections: the 8-connection gates fail, 16 is chosen;
        # the pilot is not clean (a deciding leg is invalid)
        def bad_d8(m):
            if m["shape"] == "mt-28w-c8" and m["arm"] == "shared-128":
                m["verdict"] = {"valid": False, "reasons": ["client pending total 40 above 14"]}
        cfg, res = self.run_(mut=bad_d8)
        rep = self.DP.answers(cfg, res, self.ov(cfg))
        self.assertEqual(rep["q4"]["gates"], {8: False, 16: True})
        self.assertEqual(rep["q4"]["connections"], 16)
        self.assertFalse(rep["ok"])
        self.assertTrue(any("client pending" in p for p in rep["problems"]))

        # the L3-hit event missing: no footprint term, no choice
        def no_l3(m):
            m["per_req"]["events"].pop(L3_U)
        cfg, res = self.run_(mut=no_l3)
        rep = self.DP.answers(cfg, res, self.ov(cfg))
        self.assertIsNone(rep["recommend"]["connections"])
        self.assertFalse(rep["ok"])
        self.assertIn("NO CHOICE", self.DP.text(rep, cfg))

    def test_exploratory_never_decides(self):
        def bad(pred):
            def f(m):
                if pred(m):
                    m["verdict"] = {"valid": False, "reasons": ["client headroom 12% under 25%"]}
                    m["evidence"] = {"ok": False, "failed": ["x"]}
                    m["per_req"]["instructions_u"] *= 1.05
            return f
        # the load cell and the loopback pair: invalid, evidence failing, instructions off, and the pilot is clean
        for pred in (lambda m: m["shape"] == "mt-7w-one", lambda m: m["arm"].endswith("-lo")):
            cfg, res = self.run_(mut=bad(pred))
            rep = self.DP.answers(cfg, res, self.ov(cfg))
            self.assertTrue(rep["ok"], rep["problems"])
            self.assertIn("INVALID (exploratory)", self.DP.text(rep, cfg))
        # the same in a deciding leg fails it
        cfg, res = self.run_(mut=bad(lambda m: m["shape"] == "mt-28w" and m["arm"] == "own-128"))
        rep = self.DP.answers(cfg, res, self.ov(cfg))
        self.assertFalse(rep["ok"] or rep["q1"]["ok"] or rep["q2"]["ok"] or rep["q5"]["ok"])

    def test_failures(self):
        cfg, res = self.run_(ins_extra=3000.0)  # more than 0.5% more instructions in shared
        rep = self.DP.answers(cfg, res, self.ov(cfg))
        self.assertFalse(rep["q2"]["ok"] or rep["ok"])

        def limit(m):
            if m["arm"] == "own-256":
                m["evidence"] = {"ok": False, "failed": ["256 increments per request over all dose counters: short"]}
        cfg, res = self.run_(mut=limit)
        rep = self.DP.answers(cfg, res, self.ov(cfg))
        self.assertFalse(rep["q1"]["ok"] or rep["q6"]["ok"] or rep["ok"])
        cfg, res = self.run_()
        o = self.ov(cfg)
        o["own-256"] = ["server.stats_overflow.counter: 12"]
        self.assertFalse(self.DP.answers(cfg, res, o)["q6"]["ok"])
        self.assertFalse(self.DP.answers(cfg, res, None)["q6"]["ok"])  # no stat dumps read: not a pass
        res["metadata"] = {}
        self.assertFalse(self.DP.answers(cfg, res, self.ov(cfg))["q1"]["ok"])  # validate not recorded
        res["legs"] = res["legs"][3:]
        probs = self.DP.answers(cfg, res, self.ov(cfg))["problems"]
        self.assertTrue(any(p.startswith("missing leg") for p in probs))

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
        cmd = [sys.executable, os.path.join(MT, "dose_pilot.py"), os.path.join(MT, "bench-x86_64", "dose-pilot.json"), d,
               "--json", os.path.join(d, "o.json")]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)  # an overflow stat and missing dumps: not clean
        self.assertIn("pilot NOT clean", r.stdout)
        self.assertFalse(json.load(open(os.path.join(d, "o.json")))["ok"])
        # with every arm's stat dump and no overflow stat: clean, and the record carries the recommendation
        for a in cfg["arms"]:
            with gzip.open(os.path.join(d, "stats", a["name"] + ".txt.gz"), "wt") as f:
                f.write("server.uptime: 3\n")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout[-400:])
        rec = json.load(open(os.path.join(d, "o.json")))
        self.assertEqual((rec["ok"], rec["recommend"], rec["rates_key"]),
                         (True, {"counters": 128, "connections": 8}, "bench-x86_64-dose-1"))

    def gate_case(self, rec=None, rates=None):
        rates = rates or {"counters": 128, "connections": 8}
        cfg = MK.configs(box("bench-x86_64"), {"bench-x86_64-dose-1": rates})["dose.json"]
        smoke = json.loads(json.dumps(cfg))
        record = {"ok": True, "problems": [], "rates_key": "bench-x86_64-dose-1",
                  "recommend": {"counters": 128, "connections": 8}}
        record.update(rec or {})
        return cfg, smoke, record

    def test_queue_gate(self):
        G = self.GATE.problems
        cfg, smoke, record = self.gate_case()
        self.assertEqual(G(cfg, smoke, record), [])
        # the pilot record: missing, not clean, another attempt's, or recommending something else
        self.assertEqual(G(cfg, smoke, None), ["no pilot record"])
        self.assertTrue(any("not clean" in p for p in G(cfg, smoke, dict(record, ok=False, problems=["invalid leg: x"]))))
        self.assertTrue(any("rates key" in p for p in G(cfg, smoke, dict(record, rates_key="bench-x86_64-dose-0"))))
        for other in ({"counters": 256, "connections": 8}, {"counters": 128, "connections": 16},
                      {"counters": None, "connections": None}, {}):
            p = G(cfg, smoke, dict(record, recommend=other))
            self.assertTrue(any("the pilot recommends" in x for x in p), other)
        # configured against the recommendation (K 128 at 16 connections against 128 at 8)
        cfg16, smoke16, _ = self.gate_case(rates={"counters": 128, "connections": 16})
        self.assertEqual(G(cfg16, smoke16, record),
                         ["the pilot recommends K 128 and 8 connections per worker, the config has K 128 and 16"])
        # the smoke: missing, another K or connection count, or an arm whose settings differ
        self.assertEqual(G(cfg, None, record), ["no smoke results"])
        p = G(cfg, smoke16, record)
        self.assertTrue(any("another dose block" in x for x in p) and any("other shapes" in x for x in p), p)
        for edit, needle in ((lambda a: a["settings"].update(listener_address="127.0.0.1"), "arm shared-128"),
                             (lambda a: a["settings"]["stats_flush"].update(interval_s=5), "arm shared-128"),
                             (lambda a: a["settings"]["stats_access_log"].update(counters=64), "arm shared-128"),
                             (lambda a: a.update(shapes=["mt-14w-one-c8"]), "arm shared-128")):
            sm = json.loads(json.dumps(cfg))
            edit(sm["arms"][1])
            self.assertEqual(G(cfg, sm, record), ["%s: the smoke's settings or cells differ from the config's" % needle])
        sm = json.loads(json.dumps(cfg))
        sm["arms"] = sm["arms"][:3]
        self.assertTrue(any("the smoke ran arms" in x for x in G(cfg, sm, record)))
        # a results.json as the harness writes it (defaults merged, binaries resolved) still passes
        loaded = experiment.load(self.tmp(cfg))
        self.assertEqual(G(cfg, {k: v for k, v in loaded.items() if not k.startswith("_")}, record), [])

    def decision_case(self):
        """The slot's config, a pilot record that is not clean by its own rules but whose checks
        1, 2 and 6 passed, and the decision record."""
        cfg = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
        smoke = json.loads(json.dumps(cfg))
        record = {"ok": False, "problems": ["invalid leg: mt-28w own-128: client overflow"],
                  "rates_key": "bench-x86_64-dose-1", "recommend": {"counters": None, "connections": None},
                  "q1": {"ok": True}, "q2": {"ok": True}, "q5": {"ok": False}, "q6": {"ok": True}}
        decision = {"decision": "revision 3 of the run's plan (2026-11-20)",
                    "pilot_record": "dose-pilot-2.json", "rates_key": "bench-x86_64-dose-1", "counters": 128,
                    "connections": 16, "cell_counters": {"A": 128, "B": 128, "D": 64},
                    "low": {"cell": "A", "counters": 64}}
        return cfg, smoke, record, decision

    def test_decision_record(self):
        G = self.GATE.problems
        cfg, smoke, record, decision = self.decision_case()
        name = "dose-pilot-2.json"
        # without the decision the pilot record blocks; with it, and checks 1, 2 and 6 passed, it does not
        self.assertTrue(any("not clean" in p for p in G(cfg, smoke, record)))
        self.assertEqual(G(cfg, smoke, record, decision, name), [])
        self.assertEqual(self.GATE.configured(cfg["dose"]), {k: decision[k] for k in (
            "rates_key", "counters", "connections", "cell_counters", "low")})
        # what the pilot found is read from the pilot record: a failed check 1, 2 or 6 is not overridden
        for key, label in (("q1", "1 (validate, counts, increments)"), ("q2", "2 (instructions)"),
                           ("q6", "6 (no overflow)")):
            for bad in ({"ok": False}, {}, None):
                rec = dict(record, **{key: bad})
                self.assertEqual(G(cfg, smoke, rec, decision, name),
                                 ["the pilot record's check %s did not pass: a decision record cannot stand in for it"
                                  % label], (key, bad))
            self.assertFalse(G(cfg, smoke, dict(record, **{key: {"ok": True}}), decision, name))
        # a decision that claims the checks itself changes nothing
        self.assertTrue(G(cfg, smoke, dict(record, q6={"ok": False}), dict(decision, q6={"ok": True}), name))
        # it must name this pilot record, and every choice must equal the configured one
        self.assertTrue(any("names pilot record" in p for p in G(cfg, smoke, record, decision, "dose-pilot-3.json")))
        for k, v in (("counters", 256), ("connections", 8), ("cell_counters", {"A": 128, "B": 128, "D": 128}),
                     ("cell_counters", {"A": 128, "B": 128}), ("low", {"cell": "A", "counters": 32}), ("low", None),
                     ("rates_key", "bench-x86_64-dose-0")):
            p = G(cfg, smoke, record, dict(decision, **{k: v}), name)
            self.assertTrue(any(x.startswith("the decision record has %s " % k) for x in p), (k, v, p))
        self.assertEqual(G(cfg, smoke, record, {"counters": 128}, name),
                         ["the decision record does not say what decided (decision)"])
        # the pilot record of another attempt's rates key, and the smoke comparisons, still apply
        self.assertTrue(any("rates key" in p for p in G(cfg, smoke, dict(record, rates_key="x"), decision, name)))
        sm = json.loads(json.dumps(cfg))
        sm["arms"][5]["settings"]["stats_access_log"]["counters"] = 128   # own-64-A2 run at the wrong K
        self.assertEqual(G(cfg, sm, record, decision, name),
                         ["arm own-64-A2: the smoke's settings or cells differ from the config's"])
        self.assertEqual(G(cfg, None, record, decision, name), ["no smoke results"])

    def test_decision_script(self):
        cfg, smoke, record, decision = self.decision_case()
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "smoke"))
        json.dump(cfg, open(os.path.join(d, "dose.json"), "w"))
        json.dump({"experiment": smoke, "legs": []}, open(os.path.join(d, "smoke", "results.json"), "w"))
        json.dump(record, open(os.path.join(d, "dose-pilot-2.json"), "w"))
        json.dump(decision, open(os.path.join(d, "dose-decision-2.json"), "w"))
        cmd = [sys.executable, os.path.join(MT, "dose_gate.py"), os.path.join(d, "dose.json"), os.path.join(d, "smoke"),
               os.path.join(d, "dose-pilot-2.json")]
        r = subprocess.run(cmd + [os.path.join(d, "dose-decision-2.json")], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("dose gate passed", r.stdout)
        # no decision file at that path: the pilot record decides, and it is not clean
        r = subprocess.run(cmd + [os.path.join(d, "absent.json")], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not clean (and there is no decision record)", r.stdout)
        record["q2"] = {"ok": False}
        json.dump(record, open(os.path.join(d, "dose-pilot-2.json"), "w"))
        r = subprocess.run(cmd + [os.path.join(d, "dose-decision-2.json")], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("check 2 (instructions) did not pass", r.stdout)

    def tmp(self, cfg):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "c.json"), "w") as f:
            json.dump(cfg, f)
        return os.path.join(d, "c.json")

    def test_gate_script(self):
        cfg, smoke, record = self.gate_case()
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "smoke"))
        json.dump(cfg, open(os.path.join(d, "dose.json"), "w"))
        json.dump({"experiment": smoke, "legs": []}, open(os.path.join(d, "smoke", "results.json"), "w"))
        json.dump(record, open(os.path.join(d, "pilot.json"), "w"))
        cmd = [sys.executable, os.path.join(MT, "dose_gate.py"), os.path.join(d, "dose.json"), os.path.join(d, "smoke")]
        r = subprocess.run(cmd + [os.path.join(d, "pilot.json")], capture_output=True, text=True, timeout=60)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "dose gate passed"))
        r = subprocess.run(cmd + [os.path.join(d, "none.json")], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no pilot record", r.stdout)

    def test_script_modes(self):
        txt = open(os.path.join(MT, "run-u.sh")).read()
        for m in ("dose-pilot)", "dose-smoke)", "dose-check)", "dose-queue)", "DOSE_STOP_S:-6300",
                  "DOSE_EV_STOP_S:-1500", "dose_pilot.py", '--out "$R/dose$DOSE_TAG"',
                  '--evidence "$R/dose-evidence$DOSE_TAG"',
                  "dose not started (choice, pilot record, smoke or evidence; no override)",
                  'DOSE_PILOT_TAG=${DOSE_PILOT_TAG:-$DOSE_TAG}'):
            self.assertIn(m, txt)
        # the smoke refuses an uncalibrated choice before it runs anything; the queue runs only after dose_check
        sm = txt[txt.index("  dose-smoke)"):txt.index("  dose-check)")]
        self.assertLess(sm.index("dose_uncalibrated"), sm.index("$EPL run"))
        q = txt[txt.index("  dose-queue)"):txt.index("  codegen-smoke)")]
        self.assertLess(q.index("dose_check ||"), q.index("$EPL run"))
        self.assertLess(q.index('"$C/dose.json"'), q.index('"$C/dose-evidence.json"'))
        # the tables follow the evidence legs in the same chain
        self.assertLess(q.index('"$C/dose-evidence.json"'), q.index('u_table.py" "$R/dose$DOSE_TAG" --evidence'))
        chk = txt[txt.index("dose_check() {"):txt.index("mode=${1:-}")]
        for m in ("smoke_valid.py", "evidence-check", 'dose_gate.py" "$C/dose.json" "$R/smoke-dose$DOSE_TAG" '
                  '"$R/dose-pilot$DOSE_PILOT_TAG.json"', '"$R/dose-decision$DOSE_PILOT_TAG.json"',
                  'smoke_valid.py" "$C/smoke-dose-evidence.json" "$R/smoke-dose-evidence$DOSE_TAG"',
                  'evidence-check "$C/smoke-dose-evidence.json" "$R/smoke-dose-evidence$DOSE_TAG"'):
            self.assertIn(m, chk)
        # the smoke runs the run's round and the evidence legs' round
        self.assertLess(sm.index('"$C/smoke-dose.json"'), sm.index('"$C/smoke-dose-evidence.json"'))
        self.assertLess(sm.index('"$C/smoke-dose-evidence.json"'), sm.index("dose_check"))
        # a pilot or a smoke never deletes an earlier attempt's directory: it refuses instead
        dose = txt[txt.index("  dose-pilot)"):txt.index("  codegen-smoke)")] + txt[txt.index("dose_uncalibrated() {"):
                                                                                    txt.index("mode=${1:-}")]
        self.assertNotIn("rm -", dose)
        for mode in ("  dose-pilot)", "  dose-smoke)"):
            part = txt[txt.index(mode):]
            self.assertLess(part.index("dose_fresh "), part.index("$EPL run"))
        r = subprocess.run(["bash", "-n", os.path.join(MT, "run-u.sh")], capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0)

    def test_modes_refuse(self):
        """The dose modes on a scratch runs directory, up to the point where a leg would start."""
        runs = tempfile.mkdtemp()
        env = dict(os.environ, RUNS=runs, BOX="bench-x86_64", DOSE_TAG="-t")
        env.pop("RATES_JSON", None)
        rdir = os.path.join(runs, "bench-x86_64")
        sh = os.path.join(MT, "run-u.sh")
        # an earlier attempt's directory is kept: the pilot refuses and leaves it alone
        os.makedirs(os.path.join(rdir, "dose-pilot-t"))
        open(os.path.join(rdir, "dose-pilot-t", "keep"), "w").close()
        r = subprocess.run(["bash", sh, "dose-pilot"], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("an earlier attempt is kept; set a new DOSE_TAG", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(rdir, "dose-pilot-t", "keep")))
        # the checked-in configs carry no choice: no smoke, no queue
        for mode in ("dose-smoke", "dose-queue", "dose-check"):
            r = subprocess.run(["bash", sh, mode], env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 1, mode)
            self.assertIn("dose.json is uncalibrated", r.stdout)
        self.assertEqual(sorted(os.listdir(rdir)), ["dose-pilot-t", "queue.log"])


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

    def test_dose_dry_run(self):
        c = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "dose.json"), "w") as f:
            json.dump(c, f)
        r = subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "run", os.path.join(d, "dose.json"),
                            "--dry-run", "--allow-short", "--out", os.path.join(d, "run")], capture_output=True,
                           text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        with open(os.path.join(d, "run", "results.json")) as f:
            res = json.load(f)
        self.assertEqual(len(res["legs"]), 78)
        self.assertEqual((res["metadata"]["rounds_complete"], res["metadata"]["incomplete"]), (6, False))
        text, js = UT.render(res)
        self.assertEqual(len(js["statements"]), 5)
        self.assertTrue(all("wall_s" in m for m in res["legs"]))


class ConfigEvidenceHarnessTest(unittest.TestCase):
    def test_config_evidence_where(self):
        from epl import evidence
        dump = {"configs": [{"listener": {"address": {"socket_address": {"address": "0.0.0.0", "port_value": 10110}}}},
                            {"admin": {"address": {"socket_address": {"address": "127.0.0.1", "port_value": 9921}}}},
                            {"cluster": {"socket_address": {"address": "127.0.0.1", "port_value": 8092}}}]}
        self.assertEqual(evidence.config_values(dump, "address", {"port_value": 10110}), ["0.0.0.0"])
        self.assertEqual(evidence.config_values(dump, "address", {"port_value": 9921}), ["127.0.0.1"])
        self.assertEqual(len(evidence.config_values(dump, "address")), 5)  # the objects and the strings, as before
        self.assertEqual(evidence.config_values(dump, "address", {"port_value": 1}), [])
        it = {"stat": "address", "scope": "config", "where": {"port_value": 10110}, "equals": "0.0.0.0"}
        self.assertEqual(evidence.validate_items([it]), [])
        self.assertTrue(evidence.check_item({}, it, dump)["ok"])
        self.assertFalse(evidence.check_item({}, dict(it, equals="127.0.0.1"), dump)["ok"])
        self.assertFalse(evidence.check_item({}, dict(it, where={"port_value": 1}), dump)["ok"])  # none found: not a pass
        self.assertTrue(any("where" in e for e in evidence.validate_items([dict(it, scope="window", tol=0)])))
        self.assertTrue(any("where" in e for e in evidence.validate_items([dict(it, where={})])))

    def test_quiet_window(self):
        w = [{"from": "00:00", "to": "00:10", "leg_s": 120}]
        day = 86400 * 20000
        q = experiment.quiet_wait
        self.assertEqual(q(w, day + 12 * 3600), 0)                 # midday
        self.assertEqual(q(w, day + 300), 300)                     # inside: wait for its end
        self.assertEqual(q(w, day + 1), 599)
        self.assertEqual(q(w, day + 600), 0)                       # the window's end
        self.assertEqual(q(w, day + 86400 - 60), 660)              # a leg started now would run into it
        self.assertEqual(q(w, day + 86400 - 119), 719)
        self.assertEqual(q(w, day + 86400 - 121), 0)               # it ends before the window opens
        self.assertEqual(q([], day + 300), 0)
        self.assertEqual(q(None, day + 300), 0)
        self.assertEqual(q([{"from": "12:30", "to": "12:45", "leg_s": 0}], day + 12 * 3600 + 31 * 60), 14 * 60)
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "u-hi.json"))
        exp.pop("uncalibrated", None)
        exp["avoid_utc"] = w
        self.assertEqual(experiment.validate(exp), [])
        for bad in ([{"from": "00:10", "to": "00:00"}], [{"from": "x", "to": "00:10"}], [{"to": "00:10"}]):
            exp["avoid_utc"] = bad
            self.assertTrue(any("avoid_utc" in e for e in experiment.validate(exp)), bad)

    def test_quiet_window_in_the_dose_configs(self):
        # every dose config carries it; no other run does
        w = [{"from": "00:00", "to": "00:10", "leg_s": 120}]
        self.assertEqual(experiment.load(os.path.join(MT, "bench-x86_64", "dose.json"))["avoid_utc"], w)
        c = MK.configs(box("bench-x86_64"))
        for fn, cfg in c.items():
            if "shapes" in cfg:
                self.assertEqual("avoid_utc" in cfg, "dose" in fn, fn)

    def test_runner_waits_and_times_legs(self):
        src = open(os.path.join(HERE, "epl", "experiment.py")).read()
        i = src.index("    def _leg(self, legs, r, sh, a, bpath, attempt=0):")
        body = src[i:src.index("    def _rerun_invalid", i)]
        self.assertLess(body.index("quiet_wait(self.exp[\"avoid_utc\"], time.time())"), body.index("self.backend.run_leg("))
        self.assertIn("not self._simulate", body)  # a dry run never sleeps
        self.assertIn('m["wall_s"] = round(time.monotonic() - t_leg, 1)', body)


class PilotOrderTest(unittest.TestCase):
    def test_fixed_order(self):
        # a fixed order balances nothing: only a smoke (a pilot) may use it
        u = experiment.load(os.path.join(MT, "bench-x86_64", "u-hi.json"))
        u["order"] = "fixed"
        names = [a["name"] for a in u["arms"]]
        u["arms"][2]["shapes"] = ["mt-28w"]
        for r in (1, 2, 3):
            self.assertEqual([a["name"] for a in experiment.round_order(u, r)], names)  # as listed, every round
            self.assertEqual([a["name"] for a in experiment.shape_round_order(u, r, u["shapes"][0])], names[:2])
            self.assertEqual([a["name"] for a in experiment.shape_round_order(u, r, u["shapes"][2])], names)
        self.assertEqual(experiment.order_period(u), 1)
        u["arms"][2].pop("shapes")
        self.assertTrue(any("order fixed is for a smoke" in e for e in experiment.validate(u, allow_short=True)))
        u["smoke"] = True
        self.assertFalse([e for e in experiment.validate(u, allow_short=True) if "order" in e])
        u["order"] = "sorted"
        self.assertTrue(any("order must be" in e for e in experiment.validate(u, allow_short=True)))

    def test_fixed_order_in_the_pilot(self):
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "dose-pilot.json"))
        names = [a["name"] for a in exp["arms"]]
        for r in (1, 2, 3):
            self.assertEqual([a["name"] for a in experiment.round_order(exp, r)], names)
            self.assertEqual([s["name"] for s in experiment.shape_order(exp, r)], [s["name"] for s in exp["shapes"]])
            self.assertEqual([a["name"] for a in experiment.shape_round_order(exp, r, exp["shapes"][1])],
                             ["own-128", "shared-128"])
        self.assertEqual(experiment.order_period(exp), 1)

    def dry(self, edit=None):
        """A dry run of the pilot whose first eight legs fail a client gate, as attempt 1's first six did."""
        cfg = MK.configs(box("bench-x86_64"))["dose-pilot.json"]
        plan = [experiment.leg_id(r, sh, a) for r, sh, a in experiment.schedule(experiment.load(
            os.path.join(MT, "bench-x86_64", "dose-pilot.json")))]
        cfg["sim_faults"] = {lid: "overflow" for lid in plan[:8]}
        if edit:
            edit(cfg)
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "p.json"), "w") as f:
            json.dump(cfg, f)
        r = subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "run", os.path.join(d, "p.json"),
                            "--dry-run", "--allow-short", "--out", os.path.join(d, "run")],
                           capture_output=True, text=True, timeout=120)
        with open(os.path.join(d, "run", "results.json")) as f:
            return plan, json.load(f), r

    def test_invalid_legs_do_not_cut_the_pilot_short(self):
        plan, res, r = self.dry()
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        self.assertEqual([m["leg_id"] for m in res["legs"]], plan)  # all 17, in order, none re-run
        self.assertEqual([m["verdict"]["valid"] for m in res["legs"]], [False] * 8 + [True] * 9)
        self.assertNotIn("aborted", res["metadata"])
        # the report then has every answer the valid legs give, and names the invalid ones
        DP = _mod("mt_dose_pilot2", os.path.join(MT, "dose_pilot.py"))
        cfg = json.load(open(os.path.join(MT, "bench-x86_64", "dose-pilot.json")))
        rep = DP.answers(cfg, res, None)
        self.assertEqual(len(rep["legs"]), 17)
        self.assertEqual(len([p for p in rep["problems"] if p.startswith("invalid leg")]), 8)
        # without the pilot's settings the runner's rule stops at six, and a shape with an
        # invalid leg is run again: what a timed run does

        def timed(cfg):
            cfg.pop("abort_after_invalid")
            cfg.pop("rerun_invalid")
        plan, res, r = self.dry(timed)
        self.assertEqual(len(res["legs"]), 6)
        self.assertIn("6 consecutive invalid legs", res["metadata"]["aborted"])

        def rerun_only(cfg):
            cfg.pop("rerun_invalid")
        plan, res, r = self.dry(rerun_only)
        self.assertGreater(len(res["legs"]), 17)
        self.assertTrue(any(".rr1" in m["leg_id"] for m in res["legs"]))


class ShortRunAndHotCounterTest(unittest.TestCase):
    """Short run: 6 rounds, and the exploratory pair whose K increments go to one counter."""

    def rows(self, res, ev=None):
        text, js = UT.render(res, None, ev)
        return text, js, {r["id"]: r for r in js["statements"]}

    def test_hot_logger_config(self):
        hot = envoy_config.stats_access_log({"counters": 128, "tag": "%DOWNSTREAM_LOCAL_PORT%", "hot": True})
        spread = envoy_config.stats_access_log({"counters": 128, "tag": "%DOWNSTREAM_LOCAL_PORT%"})
        hc, sc = hot["typed_config"]["counters"], spread["typed_config"]["counters"]
        # 128 entries of the same counter: the same name, tag and value in every entry
        self.assertEqual(len(hc), 128)
        self.assertEqual(hc, [sc[0]] * 128)
        self.assertEqual(len({json.dumps(c, sort_keys=True) for c in sc}), 128)
        # apart from the names the two configs are the same: scope, tag, value per entry, entry count
        self.assertEqual(json.loads(json.dumps(hot).replace('"c000"', '"x"')),
                         json.loads(__import__("re").sub(r'"c\d\d\d"', '"x"', json.dumps(spread))))
        self.assertEqual(envoy_config.stats_access_log({"counters": 2, "tag": "%DOWNSTREAM_LOCAL_PORT%", "hot": False}),
                         envoy_config.stats_access_log({"counters": 2, "tag": "%DOWNSTREAM_LOCAL_PORT%"}))
        for bad in ({"counters": 2, "tag": "%DOWNSTREAM_LOCAL_PORT%", "hot": "yes"},
                    {"counters": 2, "tag": "%DOWNSTREAM_LOCAL_PORT%", "hot": True, "x": 1}, {"counters": 2, "hot": True}):
            with self.assertRaises(ValueError, msg=bad):
                envoy_config.stats_access_log(bad)

    def test_hot_pair_bootstraps(self):
        # in the run: the hot pair differs from cell A's spread pair in the counter names only
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "dose.json"))
        bs = {a["name"]: envoy_config.bootstrap_text(exp["shapes"], experiment.arm_envoy(exp, a, "/r"), 8092)
              for a in exp["arms"]}
        import re
        norm = lambda t: re.sub(r'"c\d\d\d"', '"x"', t)  # noqa: E731
        self.assertEqual(norm(bs["hot-shared-128"]), norm(bs["shared-128"]))
        self.assertEqual(norm(bs["hot-own-128"]), norm(bs["own-128"]))
        self.assertNotEqual(bs["hot-own-128"], bs["own-128"])
        self.assertEqual(bs["hot-own-128"].count('"c000"'), 128)
        self.assertEqual(experiment.validate(exp, allow_short=True), [])

    def test_hot_evidence(self):
        from epl import evidence
        u = MK.configs(box("bench-x86_64"), DOSE_RATES)["dose.json"]
        arms = {a["name"]: a for a in u["arms"]}
        dump = lambda tag: {"x": [{"value_format": tag}] * 128, "stats_flush_interval": "240s",  # noqa: E731
                            "l": {"address": "0.0.0.0", "port_value": 10110}}

        def leg(arm, start, end, per_req, shared_counter=None, new=0):
            w = {"http.ingress_http.downstream_cx_total": 0}
            if shared_counter is not None:
                w["dose.c000.port.10110"] = shared_counter
            return {"shape": "mt-14w-one", "arm": arm, "responses_raw": 420000, "sut_stats_window": w,
                    "sut_stats_window_ok": True,
                    "stat_count": {"start_n": start, "end_n": end, "new_in_window": new, "sum_per_request": per_req}}
        sh, own = arms["hot-shared-128"]["evidence"], arms["hot-own-128"]["evidence"]
        ld, rd = dump("%DOWNSTREAM_LOCAL_PORT%"), dump("%DOWNSTREAM_REMOTE_PORT%")
        # hot shared: one counter object, 128 increments per request on it
        self.assertTrue(evidence.evaluate(leg("hot-shared-128", 1, 1, 128.0, 128 * 420000), sh, ld)["ok"])
        self.assertFalse(evidence.evaluate(leg("hot-shared-128", 128, 128, 128.0, 128 * 420000), sh, ld)["ok"])  # spread
        self.assertFalse(evidence.evaluate(leg("hot-shared-128", 1, 1, 128.0, 420000), sh, ld)["ok"])   # one per request
        self.assertFalse(evidence.evaluate(leg("hot-shared-128", 1, 1, 1.0, 128 * 420000), sh, ld)["ok"])
        # the spread shared arm's evidence does not accept a hot leg, nor the reverse
        self.assertFalse(evidence.evaluate(leg("shared-128", 1, 1, 128.0, 128 * 420000), arms["shared-128"]["evidence"],
                                           ld)["ok"])
        # hot own: one counter per connection (224, or 448 with the warm-up client's), 128 increments per request
        for n in (224, 448):
            self.assertTrue(evidence.evaluate(leg("hot-own-128", n, n, 128.0), own, rd)["ok"], n)
        self.assertFalse(evidence.evaluate(leg("hot-own-128", 223, 223, 128.0), own, rd)["ok"])
        self.assertFalse(evidence.evaluate(leg("hot-own-128", 128 * 224, 128 * 224, 128.0), own, rd)["ok"])  # spread
        self.assertFalse(evidence.evaluate(leg("hot-own-128", 224, 225, 128.0, new=1), own, rd)["ok"])
        self.assertFalse(evidence.evaluate(leg("hot-own-128", 224, 224, 128.0, shared_counter=5), own, rd)["ok"])
        self.assertFalse(evidence.evaluate(leg("hot-own-128", 224, 224, 127.0), own, rd)["ok"])

    def test_rotation_block(self):
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "u-hi.json"))
        exp.pop("uncalibrated", None)
        self.assertEqual(experiment.order_period(exp), 3)
        exp.update(rounds=4, rounds_block=4, rounds_max=4)
        self.assertTrue(any("multiple of 3" in e for e in experiment.validate(exp, allow_short=True)))
        exp["rotation_block"] = 2
        self.assertEqual(experiment.order_period(exp), 2)
        self.assertEqual(experiment.validate(exp, allow_short=True), [])
        for bad in (0, -1, 1.5, True, "3"):
            exp["rotation_block"] = bad
            self.assertTrue(any("rotation_block" in e for e in experiment.validate(exp, allow_short=True)), bad)
        # rounds count as complete in blocks of that size
        exp["rotation_block"] = 2
        legs = [{"round": r, "shape": sh["name"], "arm": a["name"], "verdict": {"valid": True}}
                for r, sh, a in experiment.schedule(exp)]
        self.assertEqual(experiment.complete_rounds(exp, legs), 4)
        self.assertEqual(experiment.complete_rounds(exp, [m for m in legs if m["round"] < 4]), 2)
        # without it nothing changes for the existing runs
        for fn in ("u.json", "u-hi.json", "u-hitm.json"):
            self.assertNotIn("rotation_block", json.load(open(os.path.join(MT, "bench-x86_64", fn))))

    def test_short_run_statements(self):
        # six rounds: no 12-round minimum; the same interval forms and finding rules
        res = _dose_run(RHO, rounds=6)
        text, js, st = self.rows(res, _dose_evidence())
        self.assertTrue(js["short_run"])
        self.assertIn("SHORT RUN of 6 rounds", text.splitlines()[0])
        self.assertIn("no minimum of 12 valid rounds applies", text)
        self.assertEqual(list(st), ["S1", "S2", "S3", "S4", "S5"])
        self.assertIn("Holm over 5", text)
        self.assertFalse([r for r in st.values() if "incomplete" in r["verdict"]])
        self.assertEqual(js["cells"]["A"]["valid_rounds"], 6)
        ra = js["cells"]["A"]["rho_rounds"]
        self.assertEqual(len(ra), 6)
        self.assertAlmostEqual(st["S1"]["w"]["hi"], UT.widened(list(ra.values()))["hi"])   # the same widened form
        self.assertEqual(st["S2"]["verdict"], "finding: line transfer")                   # 5% at K = 128 resolves
        # what six rounds do not resolve: "not resolved in a short run, under X", X the widened upper end
        res = _dose_run({"mt-14w-one": 0.004, "mt-14w-split": 0.05, "mt-28w": 0.006}, rounds=6, rho_low=0.004)
        _, js, st = self.rows(res, _dose_evidence())
        for k in ("S1", "S3"):
            self.assertTrue(st[k]["verdict"].startswith("not resolved in a short run, under %+.2f%% (" % st[k]["w"]["hi"]),
                            st[k]["verdict"])
            self.assertNotIn("bound", st[k]["verdict"])
        self.assertEqual(st["S5"]["verdict"], "not resolved in a short run, under %+.2f points" % st["S5"]["w"]["hi"])
        self.assertEqual(st["S4"]["verdict"], "resolved: higher across sockets")
        # the A/A rule and the invalid-comparison rule are the same in a short run
        _, js, st = self.rows(_dose_run(RHO, rounds=6, aa_noise=0.03), _dose_evidence())
        self.assertTrue(all(st[k]["verdict"].startswith("no verdict: cell ") for k in st))
        _, js, st = self.rows(_dose_run(dict(RHO, **{"mt-28w": -0.03}), rounds=6), _dose_evidence())
        self.assertEqual(st["S3"]["verdict"], "comparison invalid (own slower than shared)")
        # a stopped short run is still incomplete
        res = _dose_run(RHO, rounds=6)
        res["metadata"]["incomplete"] = True
        _, _, st = self.rows(res, _dose_evidence())
        self.assertEqual({r["verdict"] for r in st.values()}, {experiment.INCOMPLETE})
        # the long run's wording and minimum are unchanged
        _, js, st = self.rows(_dose_run({"mt-14w-one": 0.004, "mt-14w-split": 0.05, "mt-28w": 0.006}, rho_low=0.004),
                              _dose_evidence())
        self.assertFalse(js["short_run"])
        self.assertTrue(st["S1"]["verdict"].startswith("bound: rho_A <= "))
        self.assertTrue(st["S5"]["verdict"].startswith("not resolved: <= "))

    def test_one_round_of_evidence(self):
        # the evidence legs are one round per cell: means without intervals still feed the label,
        # the band and the model row
        ev = _dose_evidence()
        ev["legs"] = [m for m in ev["legs"] if m["round"] == 1]
        ev["metadata"]["rounds_complete"] = 1
        text, js, st = self.rows(_dose_run(RHO, rounds=6), ev)
        e = js["evidence"]["A"]
        self.assertEqual((e["hitm_shared_minus_own"]["n"], e["footprint"]["n"]), (1, 1))
        self.assertNotIn("lo", e["hitm_shared_minus_own"])
        self.assertAlmostEqual(e["h"], 0.3, delta=0.05)
        self.assertEqual(e["rounds"], 1)
        # everything resting on the one round says so, and carries no interval header
        self.assertEqual(st["S2"]["verdict"], "finding: line transfer (HITM evidence: one round, no interval)")
        self.assertIn("ONE ROUND, NO INTERVAL: the evidence legs ran once per cell, so h, d, T, the footprint band and "
                      "the line-transfer label all rest on one leg per arm and cell.", text)
        hitm_head = [ln for ln in text.splitlines() if ln.startswith("| Cell | K | base | stats-reject")][0]
        self.assertIn("base - stats-reject (one round, no interval)", hitm_head)
        self.assertNotIn("95% t CI", hitm_head)
        price_head = [ln for ln in text.splitlines() if ln.startswith("| Cell | K | P: (shared - own)")][0]
        self.assertEqual(price_head.count("(one round, no interval)"), 2)   # d and the band; P keeps its interval
        self.assertIn("worker cycles [95% t CI] (measured)", price_head)
        model_head = [ln for ln in text.splitlines() if ln.startswith("| Cell | Sockets | K | P: price")][0]
        self.assertEqual(model_head.count("(one round, no interval)"), 3)   # T, the band column, the HITM-scaled column
        self.assertIn("with the footprint band (one round, no interval)", text)
        ev4 = _dose_evidence(h=0.1)
        ev4["legs"] = [m for m in ev4["legs"] if m["round"] == 1]
        ev4["metadata"]["rounds_complete"] = 1
        _, _, st4 = self.rows(_dose_run(RHO, rounds=6), ev4)
        self.assertTrue(st4["S2"]["verdict"].endswith("(HITM evidence: one round, no interval)"))
        self.assertTrue(st4["S2"]["verdict"].startswith("finding, not called line transfer"))
        # four rounds of evidence: intervals, and no such label anywhere
        text4, js4, st4 = self.rows(_dose_run(RHO, rounds=6), _dose_evidence())
        self.assertNotIn("one round, no interval", text4.lower())
        self.assertIn("base - stats-reject [95% t CI]", text4)
        self.assertEqual(st4["S2"]["verdict"], "finding: line transfer")
        p = {(x["cell"], x["counters"]): x for x in js["prices"]}[("B", 128)]
        self.assertAlmostEqual(p["band"], p["price"]["mean"] + p["footprint_d"] * 45.0)
        m = js["model"]["cells"]["B"][0]
        self.assertAlmostEqual(m["x_pct"], 100 * 17.0 * m["P"] / 545e3)
        self.assertIn("hitm_scaled_pct", m)

    def test_hot_pair_is_exploratory(self):
        res = _dose_run(RHO, rounds=6, rho_hot=0.06)
        text, js, st = self.rows(res, _dose_evidence())
        hot = js["hot"]
        self.assertEqual((hot["cell"], hot["counters"], hot["own"], hot["shared"], hot["valid_rounds"]),
                         ("A", 128, "hot-own-128", "hot-shared-128", 6))
        # its rho and price come from its own two arms, per 128 updates
        legs = lambda arm: {m["round"]: m["workers_cycles_per_req"] for m in res["legs"]  # noqa: E731
                            if m["shape"] == "mt-14w-one" and m["arm"] == arm}
        o, s_ = legs("hot-own-128"), legs("hot-shared-128")
        self.assertAlmostEqual(hot["rho_t"]["mean"], sum(100 * math.log(s_[r] / o[r]) for r in o) / 6)
        self.assertAlmostEqual(hot["price"]["mean"], sum((s_[r] - o[r]) / 128 for r in o) / 6)
        self.assertAlmostEqual(hot["rho"]["hi"], UT.widened([100 * math.log(s_[r] / o[r]) for r in sorted(o)])["hi"])
        # outside the statements: five of them, Holm over five, with or without the hot pair
        self.assertEqual(len(st), 5)
        self.assertFalse([r for r in st.values() if "hot" in r["statement"]])
        res2 = json.loads(json.dumps(res))
        res2["legs"] = [m for m in res2["legs"] if not m["arm"].startswith("hot-")]
        _, js2, st2 = self.rows(res2, _dose_evidence())
        self.assertEqual([st2[k]["holm_p"] for k in st2], [st[k]["holm_p"] for k in st])
        self.assertEqual([st2[k]["verdict"] for k in st2], [st[k]["verdict"] for k in st])
        # printed beside cell A's K = 128 pair, marked exploratory, with the ratio of the two prices
        self.assertIn("| A (HOT COUNTER, exploratory) | 14w-one |", text)
        self.assertIn("| A, HOT COUNTER (exploratory) | 128 on one counter |", text)
        ratio = hot["price"]["mean"] / js["cells"]["A"]["price"]["mean"]
        self.assertIn("Hot counter in cell A (EXPLORATORY, outside the statements, 6 rounds)", text)
        self.assertGreater(ratio, 2.0)
        # the hot price is set against the footprint band of cell A's K = 128 pair, not against its P
        band = {(x["cell"], x["counters"]): x for x in js["prices"]}[("A", 128)]["band"]
        self.assertAlmostEqual(band, js["cells"]["A"]["price"]["mean"] + js["evidence"]["A"]["footprint"]["mean"] * 45.0)
        self.assertAlmostEqual(hot["ratio_to_band"], hot["price"]["mean"] / band)
        self.assertEqual((hot["spread_band"], hot["spread_price"]), (band, js["cells"]["A"]["price"]["mean"]))
        self.assertIn("the hot price is %.2f times the band" % hot["ratio_to_band"], text)
        self.assertNotIn("(%.2f times)" % ratio, text)
        for needle in ("Only a hot price above the band is a sign of writers queuing on a line",
                       "hot-own has no footprint penalty", "while the spread own arm has",
                       "occupied only an estimated 12-20% of the time",
                       "does not show the absence of queuing on wider machines"):
            self.assertIn(needle, text)
        # a hot price under the band is printed as such, and without evidence legs there is no band to compare with
        _, js3, _ = self.rows(_dose_run(RHO, rounds=6, rho_hot=0.01), _dose_evidence())
        self.assertLess(js3["hot"]["ratio_to_band"], 1.0)
        text4, js4, _ = self.rows(res)
        self.assertIsNone(js4["hot"]["ratio_to_band"])
        self.assertIn("the hot price is not comparable to (no band) the band", text4)
        # no model row and no footprint band rest on it
        self.assertNotIn("hot", json.dumps(js["model"]))
        self.assertFalse([p for p in js["prices"] if "hot" in json.dumps(p["cell"])])
        self.assertEqual(len(js["prices"]), 4)


class DoseTableReviewTest(unittest.TestCase):
    """The re-review's table fixes that have no test above: both intervals, the order caveat."""

    def rows(self, res, ev=None):
        text, js = UT.render(res, None, ev)
        return text, js, {r["id"]: r for r in js["statements"]}

    def test_plain_t_beside_widened(self):
        res = _dose_run(RHO, rounds=6)
        text, js, st = self.rows(res, _dose_evidence())
        head = [ln for ln in text.splitlines() if ln.startswith("| # | Statement")][0]
        self.assertIn("| Estimate, widened 95% interval | Plain 95% t interval |", head)
        t5 = UT.stats.t_ppf(0.975, 5)
        self.assertAlmostEqual(t5, 2.5706, places=3)
        for k in ("S1", "S2", "S3"):
            d = list(js["cells"][st[k]["cell"]]["rho_rounds"].values())
            mu = sum(d) / 6
            se = UT.stats.stdev(d) / math.sqrt(6)
            self.assertAlmostEqual(st[k]["t"]["hi"], mu + t5 * se)
            self.assertAlmostEqual(st[k]["w"]["hi"], mu + 1.96 * math.sqrt(se ** 2 + 0.34 ** 2))
        # the contrasts too: the plain t interval of the paired differences
        ra, rb = js["cells"]["A"]["rho_rounds"], js["cells"]["B"]["rho_rounds"]
        d = [rb[r] - ra[r] for r in sorted(ra)]
        self.assertAlmostEqual(st["S4"]["t"]["hi"], sum(d) / 6 + t5 * UT.stats.stdev(d) / math.sqrt(6))
        dl = [js["cells"]["D"]["rho_rounds"][r] - js["low"]["rho_rounds"][r] for r in sorted(ra)]
        self.assertAlmostEqual(st["S5"]["t"]["lo"], sum(dl) / 6 - t5 * UT.stats.stdev(dl) / math.sqrt(6))
        # both intervals are in every statement's row
        for k, r in st.items():
            row = [ln for ln in text.splitlines() if ln.startswith("| %s |" % k)][0]
            self.assertIn("%+.2f [%+.2f, %+.2f]" % (r["w"]["mean"], r["w"]["lo"], r["w"]["hi"]), row)
            self.assertIn("%+.2f [%+.2f, %+.2f]" % (r["t"]["mean"], r["t"]["lo"], r["t"]["hi"]), row)
        self.assertIn("6 rounds give 5 degrees of freedom: the plain t interval (quantile 2.57) is printed beside the "
                      "widened one", text)
        self.assertIn("the reader should take the wider of the two", text)
        # with a small spread the widened one is the wider; with a large spread the plain t one is
        self.assertGreater(st["S1"]["w"]["hi"] - st["S1"]["w"]["lo"], st["S1"]["t"]["hi"] - st["S1"]["t"]["lo"])
        noisy = _dose_run(RHO, rounds=6)
        for m in noisy["legs"]:
            if m["arm"] == "shared-128" and m["shape"] == "mt-14w-one":
                m["workers_cycles_per_req"] *= 1.0 + (0.02 if m["round"] % 2 else -0.02)
        _, _, st2 = self.rows(noisy, _dose_evidence())
        self.assertGreater(st2["S1"]["t"]["hi"] - st2["S1"]["t"]["lo"], st2["S1"]["w"]["hi"] - st2["S1"]["w"]["lo"])
        # 15 rounds: 14 degrees of freedom
        text15, _, _ = self.rows(_dose_run(RHO), _dose_evidence())
        self.assertIn("15 rounds give 14 degrees of freedom", text15)

    def scheduled(self, mutate=None):
        """A synthetic run whose legs are recorded in the order the real config schedules them."""
        res = _dose_run(RHO, rounds=6)
        exp = experiment.load(os.path.join(MT, "bench-x86_64", "dose.json"))
        by = {(m["round"], m["shape"], m["arm"]): m for m in res["legs"]}
        res["legs"] = [by[(r, sh["name"], a["name"])] for r, sh, a in experiment.schedule(exp)]
        self.assertEqual(len(res["legs"]), 78)
        if mutate:
            mutate(res)
        return res, exp

    def test_order_caveat_from_the_run(self):
        res, exp = self.scheduled()
        text, js, st = self.rows(res, _dose_evidence())
        o = {(x["cell"], x["pair"]): x for x in js["order"]}
        self.assertEqual(sorted(o), [("A", "A/A"), ("A", "hot shared / own"), ("A", "shared / own at K = 128"),
                                     ("A", "shared / own at K = 64"), ("B", "A/A"), ("B", "shared / own at K = 128"),
                                     ("D", "A/A"), ("D", "shared / own at K = 64")])
        # recomputed by hand from the schedule: positions of each arm per round and cell
        want = {}
        for r in range(1, 7):
            for sh in exp["shapes"]:
                names = [a["name"] for a in experiment.shape_round_order(exp, r, sh)]
                for later, earlier in (("shared-128", "own-128"), ("own-128-A2", "own-128"), ("shared-64", "own-64"),
                                       ("own-64-A2", "own-64"), ("hot-shared-128", "hot-own-128")):
                    if later in names and earlier in names:
                        want.setdefault((sh["cell"], later, earlier), []).append(names.index(later) - names.index(earlier))
        for x in js["order"]:
            d = want[(x["cell"], x["later"], x["earlier"])]
            self.assertEqual((x["rounds"], x["directly_after"]), (6, d.count(1)), x)
            self.assertAlmostEqual(x["mean_diff"], sum(d) / 6.0)
        # what the schedule of this run gives: 7 arms in 6 rounds in cell A
        a = o[("A", "shared / own at K = 128")]
        self.assertEqual((a["arms"], a["rounds"], a["directly_after"]), (7, 6, 5))
        self.assertAlmostEqual(a["mean_diff"], -1 / 6.0)
        self.assertAlmostEqual(o[("A", "shared / own at K = 64")]["mean_diff"], -1 / 6.0)
        self.assertAlmostEqual(o[("A", "A/A")]["mean_diff"], -2 / 6.0)
        self.assertEqual([o[(c, p)]["directly_after"] for c, p in (("B", "shared / own at K = 128"),
                                                                  ("D", "shared / own at K = 64"))], [4, 4])
        self.assertEqual(o[("B", "shared / own at K = 128")]["arms"], 3)
        self.assertIn("Order (from the legs as they ran): cell A (7 arms, 6 rounds) shared / own at K = 128: "
                      "shared-128 ran -0.17 slots from own-128 on average and directly after it in 5 of 6 rounds", text)
        self.assertIn("cell A (7 arms, 6 rounds) A/A: own-128-A2 ran -0.33 slots from own-128", text)
        self.assertIn("directly after it in 4 of 6 rounds", text)
        self.assertIn("a carry-over from the leg before is not averaged out", text)

    def test_order_follows_the_legs_not_the_config(self):
        # computed from the legs in the run directory: another run order gives other numbers
        def reverse_cell_a(res):
            for r in range(1, 7):
                idx = [i for i, m in enumerate(res["legs"]) if m["round"] == r and m["shape"] == "mt-14w-one"]
                legs = [res["legs"][i] for i in idx][::-1]
                for i, m in zip(idx, legs):
                    res["legs"][i] = m
        res, _ = self.scheduled(reverse_cell_a)
        _, js, _ = self.rows(res, _dose_evidence())
        o = {(x["cell"], x["pair"]): x for x in js["order"]}
        self.assertAlmostEqual(o[("A", "shared / own at K = 128")]["mean_diff"], 1 / 6.0)
        self.assertEqual(o[("A", "shared / own at K = 128")]["directly_after"], 0)
        self.assertEqual(o[("B", "shared / own at K = 128")]["directly_after"], 4)   # cell B untouched
        # a re-run of a round and cell replaces its first attempt; superseded legs do not count
        res, _ = self.scheduled()
        first = [m for m in res["legs"] if m["round"] == 2 and m["shape"] == "mt-14w-split"]
        rerun = [dict(m, attempt=1, leg_id=m["leg_id"] + ".rr1") for m in first][::-1]
        for m in first:
            m["superseded"] = True
        res["legs"] += rerun
        pos = UT.run_positions(res)
        self.assertEqual(pos[("mt-14w-split", 2)], [m["arm"] for m in rerun])
        self.assertEqual(len(pos), 18)
        self.assertEqual(UT.order_stats(pos, "mt-14w-split", "nobody", "own-128"), None)
        self.assertEqual(UT.order_stats({("s", 1): ["a", "b"], ("s", 2): ["b", "x", "a"]}, "s", "b", "a"),
                         {"rounds": 2, "mean_diff": -0.5, "directly_after": 1})


if __name__ == "__main__":
    unittest.main()
