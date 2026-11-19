import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from epl import envoy_config, experiment, portability
from epl.__main__ import classify_profile, parse_perf_report
from epl.sim import SimBackend

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF = os.path.join(HERE, "examples", "stats-flush")
X86 = os.path.join(SF, "bench-x86_64")
ARM = os.path.join(SF, "example-aarch64")


def _mod(name, path):
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.path.pop(0)


MK = _mod("sf_make", os.path.join(SF, "make.py"))
SESS = _mod("sf_session", os.path.join(SF, "session.py"))
TAB = _mod("sf_table", os.path.join(SF, "table.py"))


def box(name):
    with open(os.path.join(SF, "boxes", name + ".json")) as f:
        return json.load(f)


class ConfigsTest(unittest.TestCase):
    def test_written_configs_are_current(self):
        for b, d in ((box("bench-x86_64"), X86), (box("example-aarch64"), ARM)):
            for fn, c in MK.configs(b).items():
                with open(os.path.join(d, fn)) as f:
                    self.assertEqual(json.load(f), json.loads(json.dumps(c)), fn + ": rerun make.py")

    def test_validate_and_legs(self):
        want = {"m-10k": 16, "m-100k": 16, "m-300k": 16, "m-1m": 16, "w": 32, "s-100k": 50, "s-1m": 64, "sw": 50, "x-1m": 16}
        for fn in sorted(os.listdir(X86)):
            if fn == "box.json":
                continue
            exp = experiment.load(os.path.join(X86, fn))
            self.assertEqual(experiment.validate(exp, allow_short=True), [], fn)
            if fn[:-5] in want:
                self.assertEqual(len(experiment.schedule(exp)), want[fn[:-5]], fn)
                self.assertEqual(exp["order_seed"], 31)
                self.assertTrue(exp.get("uncalibrated"))
                for a in exp["arms"]:
                    self.assertTrue(a["evidence"], fn + " " + a["name"])
                    self.assertEqual(a["source_sha256"], box("bench-x86_64")["binaries"]["x86_64"]["source_sha256"])

    def test_latin_order(self):
        exp = experiment.load(os.path.join(X86, "m-1m.json"))
        pos = {}
        for r in range(1, 5):
            for i, a in enumerate(experiment.round_order(exp, r)):
                pos.setdefault(a["name"], set()).add(i)
        self.assertEqual({k: len(v) for k, v in pos.items()}, {"flush-off": 4, "nosink": 4, "statsd": 4,
                                                                "nosink-A2": 4})

    def test_arm_settings(self):
        exp = experiment.load(os.path.join(X86, "m-100k.json"))
        a = {x["name"]: x for x in exp["arms"]}
        self.assertEqual(a["flush-off"]["settings"]["stats_flush"], {"on_admin": True})
        self.assertEqual(a["nosink"]["settings"]["stats_flush"], {"interval_s": 1})
        self.assertEqual(a["statsd"]["settings"]["stats_sink"], {"kind": "statsd"})
        self.assertEqual(a["nosink"]["settings"]["stats_clusters"]["count"], 1000)
        b = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, a["statsd"], "/r"), 8092)
        self.assertEqual(b["stats_sinks"][0]["typed_config"]["address"]["socket_address"]["port_value"], 8125)
        self.assertEqual(len(b["static_resources"]["clusters"]), 1001)
        s = experiment.load(os.path.join(X86, "s-1m.json"))
        sa = {x["name"]: x for x in s["arms"]}
        self.assertEqual(sorted(sa), ["dogstatsd-buf", "nosink", "nosink-20s", "nosink-5s", "nosink-5s-A2", "nosink-A2",
                                      "otlp", "statsd"])  # prom dropped; same-interval references at 1M (S2)
        self.assertEqual(s["s_refs"], {"statsd": "nosink-5s", "dogstatsd-buf": "nosink-5s", "otlp": "nosink-20s"})
        self.assertEqual((sa["nosink-20s"]["settings"]["stats_flush"], sa["nosink-20s"]["window_s"]),
                         ({"interval_s": 20}, 60))
        self.assertEqual((s["rounds"], experiment.load(os.path.join(X86, "s-100k.json"))["rounds"]), (8, 10))
        ot_fit = [i for i in sa["otlp"]["evidence"] if i["stat"] == "collector_delta.fit.n_error"][0]
        self.assertEqual(ot_fit["max"], 1)  # S3: one flush in flight at a non-atomic read
        self.assertEqual(sa["otlp"]["settings"]["stats_sink"]["kind"], "otlp")
        # at 1M by the saturation rule: dogstatsd-buf every 5 s, otlp every 20 s with a 60 s window
        self.assertEqual(sa["dogstatsd-buf"]["settings"]["stats_flush"], {"interval_s": 5})
        self.assertEqual(sa["dogstatsd-buf"]["settings"]["stats_sink"]["max_bytes_per_datagram"], 1432)
        self.assertEqual((sa["otlp"]["settings"]["stats_flush"], sa["otlp"]["window_s"]), ({"interval_s": 20}, 60))
        s100 = {x["name"]: x for x in experiment.load(os.path.join(X86, "s-100k.json"))["arms"]}
        self.assertEqual(s100["otlp"]["settings"]["stats_flush"], {"interval_s": 1})
        for name in ("dogstatsd-buf", "otlp"):
            st = {i["stat"] for i in sa[name]["evidence"]}
            self.assertTrue({"quiesce.before_ok", "quiesce.after_ok", "span_flushes.partial"} <= st, name)
        ot = [i for i in sa["otlp"]["evidence"] if i["stat"] == "collector_delta.accepted_metric_points_per_flush"][0]
        self.assertEqual((ot["per"], ot["tol"]), ("field:used_total", 0.01))  # one basis: every used stat
        st = {i["stat"] for i in sa["otlp"]["evidence"]}
        self.assertNotIn("collector_delta.fit.basis", st)
        self.assertTrue({"otlp_cluster.rx_reset", "otlp_cluster.whole_error", "otlp_cluster.estimate_error",
                         "collector_log.error_lines"} <= st)
        self.assertEqual(s["collector"]["max_recv_msg_size_mib"], 64)
        sw = experiment.load(os.path.join(X86, "sw.json"))
        self.assertEqual([a["name"] for a in sw["arms"]], ["nosink", "nosink-A2", "statsd", "dogstatsd-buf", "otlp"])
        self.assertEqual((sw["shapes"][0]["rps"], sw["rounds"], sw["primary_metric"]), (5200, 10, "cycles_total"))
        self.assertTrue(experiment.needs_collector(sw))
        self.assertTrue(experiment.needs_collector(s))
        x = experiment.load(os.path.join(X86, "x-1m.json"))
        xa = {y["name"]: y for y in x["arms"]}
        self.assertFalse(xa["statsd-cold"]["prime"])
        self.assertEqual(xa["statsd-5s"]["window_s"], 30)
        w = experiment.load(os.path.join(X86, "w.json"))
        self.assertEqual(w["confirmatory"], [["statsd", "flush-off"]])
        self.assertTrue(w["measure"]["per_thread"] and w["measure"]["main_sampler"])
        self.assertGreaterEqual(w["client"]["duration_s"],
                                2 + w["shapes"][0]["pre_window_settle_s"] + w["measure"]["window_s"] + 1)

    def test_calibration_numbers_reach_the_configs(self):
        cal = {"1m": {"ready_timeout_s": 150, "admin_timeout_s": 90, "settle_s": 2.7, "stats_total": 1100300,
                      "used_total": 640000, "used_cg_lines": 600000, "statsd_interval_s": 5}}
        c = MK.configs(box("bench-x86_64"), cal)["m-1m.json"]
        self.assertNotIn("uncalibrated", c)
        self.assertEqual(c["shapes"][0]["ready_timeout_s"], 150)
        st = [a for a in c["arms"] if a["name"] == "statsd"][0]
        self.assertEqual(st["settings"]["stats_flush"], {"interval_s": 5})
        items = {i.get("label"): i for i in st["evidence"]}
        self.assertEqual(items["N within 0.5% of the calibration"]["per_request"], 1100300)


class PortabilityTest(unittest.TestCase):
    def copy(self):
        d = tempfile.mkdtemp()
        a, b = os.path.join(d, "x"), os.path.join(d, "a")
        shutil.copytree(X86, a)
        shutil.copytree(ARM, b)
        return a, b

    def test_pass(self):
        self.assertEqual(portability.check_dirs([X86, ARM]), [])

    def test_hard_coded_cpu_set_and_event_fail(self):
        a, b = self.copy()
        p = os.path.join(b, "m-1m.json")
        c = json.load(open(p))
        c["cpus"]["sut"] = "0-3"  # the x86 box's set, hard-coded into an arm64 config
        c["measure"]["main_perf_events"] = "instructions:u,cycles,uops_issued.any"
        json.dump(c, open(p, "w"), indent=1)
        probs = portability.check_dirs([a, b])
        self.assertTrue(any("another box's literal '0-3'" in x for x in probs), probs)
        self.assertTrue(any("uops_" in x for x in probs), probs)

    def test_machine_dependent_bootstrap_fails(self):
        a, b = self.copy()
        p = os.path.join(b, "m-10k.json")
        c = json.load(open(p))
        c["arms"][1]["settings"]["stats_flush"] = {"interval_s": 2}
        json.dump(c, open(p, "w"), indent=1)
        self.assertTrue(any("bootstrap differs" in x for x in portability.check_dirs([a, b])))

    def test_arch_pick_and_elf(self):
        exp = experiment.load(os.path.join(ARM, "m-1m.json"))
        self.assertTrue(exp["arms"][0]["source"].endswith("linux-aarch_64"))
        d = tempfile.mkdtemp()
        f = os.path.join(d, "bin")
        with open(f, "wb") as fh:
            fh.write(b"\x7fELF\x02\x01\x01" + b"\x00" * 11 + (183).to_bytes(2, "little") + b"\x00" * 40)
        self.assertEqual(experiment.elf_arch(f), "aarch64")
        exp["arms"][0]["binary"] = f
        exp["box"]["arch"] = "x86_64"
        self.assertTrue(any("binary is aarch64" in e for e in experiment.check_arch(exp)))
        self.assertIsNone(experiment.elf_arch(os.path.join(SF, "make.py")))

    def test_cli(self):
        r = subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "portability-check", X86, ARM],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class SysctlGuardTest(unittest.TestCase):
    def run_guard(self, script, value_file, gdir):
        sh = ("set -u; GUARD_FILE=%s; GUARD_DIR=%s; GUARD_VALUE=268435456; . %s; %s" % (
            value_file, gdir, os.path.join(SF, "sysctl-guard.sh"), script))
        return subprocess.run(["bash", "-c", sh], capture_output=True, text=True, timeout=60)

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, "rmem_max")
        with open(self.f, "w") as fh:
            fh.write("212992\n")

    def val(self):
        return open(self.f).read().strip()

    def test_set_and_restore_on_exit(self):
        r = self.run_guard('guard_begin || exit 9; cat "$GUARD_FILE" > %s/during' % self.d, self.f, self.d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(open(os.path.join(self.d, "during")).read().strip(), "268435456")
        self.assertEqual(self.val(), "212992")
        rec = json.load(open(os.path.join(self.d, "sysctl-session.json")))
        self.assertTrue(rec["restore_ok"])
        self.assertEqual((rec["rmem_max_original"], rec["rmem_max_session"]), (212992, 268435456))

    def test_restore_on_failure_and_term(self):
        r = self.run_guard("guard_begin || exit 9; false; exit 3", self.f, self.d)
        self.assertEqual(r.returncode, 3)
        self.assertEqual(self.val(), "212992")
        p = subprocess.Popen(["bash", "-c", "GUARD_FILE=%s; GUARD_DIR=%s; . %s; guard_begin; echo up; sleep 30 >/dev/null 2>&1 & wait" % (
            self.f, self.d, os.path.join(SF, "sysctl-guard.sh"))], stdout=subprocess.PIPE, text=True)
        p.stdout.readline()  # the guard's log line: it has set the value
        import time
        for _ in range(100):
            if self.val() == "268435456":
                break
            time.sleep(0.05)
        self.assertEqual(self.val(), "268435456")
        p.terminate()
        p.wait(timeout=10)
        self.assertEqual(self.val(), "212992")

    def test_refuses_when_changed_since_step0(self):
        with open(os.path.join(self.d, "rmem_max.step0"), "w") as fh:
            fh.write("212992\n")
        with open(self.f, "w") as fh:
            fh.write("4194304\n")
        r = self.run_guard("guard_begin || exit 9", self.f, self.d)
        self.assertEqual(r.returncode, 9)
        self.assertEqual(self.val(), "4194304")
        self.assertIn("REFUSED", r.stdout)


class SessionHelpersTest(unittest.TestCase):
    def test_merge_and_statsd_interval(self):
        d = tempfile.mkdtemp()
        for arm, ready, total in (("nosink", 100, 1100300), ("statsd", 130, None)):
            os.makedirs(os.path.join(d, "1m-" + arm))
            json.dump({"idle-1m": {"ready_timeout_s": ready, "admin_timeout_s": 40, "settle_s": 2.5,
                                   "stats_total": total, "used_total": 600000 if total else None}},
                      open(os.path.join(d, "1m-" + arm, "rungs.json"), "w"))
        out = os.path.join(d, "rungs.json")
        r = SESS.merge_rungs(out, [os.path.join(d, "1m-nosink"), os.path.join(d, "1m-statsd")])
        self.assertEqual(r["1m"]["ready_timeout_s"], 130)
        self.assertEqual(r["1m"]["stats_total"], 1100300)
        sm = os.path.join(d, "smoke-1m")
        os.makedirs(sm)
        with open(os.path.join(sm, "legs.jsonl"), "w") as f:
            f.write(json.dumps({"leg_id": "a", "arm": "statsd", "shape": "idle-1m", "udp": {"drop_share": 0.03}}) + "\n")
        r = SESS.statsd_interval(out, [sm])
        self.assertEqual(r["1m"]["statsd_interval_s"], 5)
        # a saturated main thread moves the rung to 5 s too; a later smoke at 5 s never lowers it
        with open(os.path.join(sm, "legs.jsonl"), "w") as f:
            f.write(json.dumps({"leg_id": "b", "arm": "statsd", "shape": "idle-300k", "udp": {"drop_share": 0.0},
                                "main": {"run_ms_per_s": 999.0}}) + "\n")
        r = SESS.statsd_interval(out, [sm])
        self.assertEqual(r["300k"]["statsd_interval_s"], 5)
        with open(os.path.join(sm, "legs.jsonl"), "w") as f:
            f.write(json.dumps({"leg_id": "c", "arm": "statsd", "shape": "idle-300k", "udp": {"drop_share": 0.0},
                                "main": {"run_ms_per_s": 480.0}}) + "\n")
        self.assertEqual(SESS.statsd_interval(out, [sm])["300k"]["statsd_interval_s"], 5)

    def test_predict_w(self):
        d = tempfile.mkdtemp()
        legs = []
        for arm, cps in (("nosink", 70e6), ("flush-off", 2e6)):
            for r in (1, 2):
                legs.append({"arm": arm, "round": r, "verdict": {"valid": True}, "main_perf": {"cycles_per_s": cps}})
        json.dump({"legs": legs}, open(os.path.join(d, "results.json"), "w"))
        p = SESS.predict_w(d)
        # 68M cycles per flush at 5 s over 5,200 x 270k cycles per second: about 0.97%
        self.assertAlmostEqual(p["predicted_effect_pct"], 100 * 68e6 / 5 / (5200 * 270e3), places=6)
        self.assertEqual(p["nosink_row"], "secondary")

    def test_run_session_script(self):
        txt = open(os.path.join(SF, "run-session.sh")).read()
        self.assertIn('if [ "$rc" -eq 3 ] && [ "${FORCE:-0}" = 1 ]; then', txt)
        self.assertIn("timeout --foreground --signal=TERM", txt)
        self.assertIn("guard_begin || exit 1", txt)
        for s in ("smoke-m-10k", "smoke-100k", "smoke-m-300k", "smoke-1m", "smoke-w"):
            self.assertIn(s, txt)
        self.assertEqual(SESS.MANDATORY, ["m-10k", "m-100k", "m-1m", "w", "m-300k"])
        self.assertEqual(SESS.OPTIONAL, ["x-1m"])
        for mode in ("s-smoke)", "s-check)", "s-queue)", 'SRUNS="s-100k s-1m sw"', "S_STOP_S:-12600"):
            self.assertIn(mode, txt)
        r = subprocess.run(["bash", "-n", os.path.join(SF, "run-session.sh")], capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0)


class ProfileParseTest(unittest.TestCase):
    def test_report_and_classes(self):
        txt = ("# Overhead  Symbol\n    41.20%  [.] Envoy::Stats::RefcountHelper::decRefCount\n"
               "    20.00%  [.] Envoy::Stats::ParentHistogramImpl::merge\n     9.00%  [k] _raw_spin_lock\n"
               "     2.00%  [.] 0x0000000001234567\n")
        rows = parse_perf_report(txt)
        self.assertEqual(len(rows), 4)
        c = classify_profile(rows)
        self.assertAlmostEqual(c["reference counting and latching"], 41.2)
        self.assertAlmostEqual(c["histogram accumulate and quantiles"], 20.0)
        self.assertAlmostEqual(c["other"], 11.0)


class TableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.sess = os.path.join(cls.tmp, "sess")
        flush_ms = {"10k": 1.0, "100k": 8.0, "300k": 25.0, "1m": 80.0}
        for rung in ("10k", "100k", "300k", "1m"):
            c = json.load(open(os.path.join(X86, "m-%s.json" % rung)))
            for a in c["arms"]:
                a["sim_flush_ms"] = flush_ms[rung] * (1.9 if a["name"] == "statsd" else 1.0)
            c["sim_cycles_noise"] = 0.01
            p = os.path.join(cls.tmp, "m-%s.json" % rung)
            json.dump(c, open(p, "w"))
            experiment.Runner(experiment.load(p), os.path.join(cls.sess, "m-" + rung), SimBackend).run(simulate=True)
        c = json.load(open(os.path.join(X86, "w.json")))
        for a in c["arms"]:
            a["sim_factor"] = 1.03 if a["name"] == "statsd" else 1.0
        c["sim_cycles_noise"] = 0.004
        p = os.path.join(cls.tmp, "w.json")
        json.dump(c, open(p, "w"))
        experiment.Runner(experiment.load(p), os.path.join(cls.sess, "w"), SimBackend).run(simulate=True)
        cls.text, cls.js = TAB.tables(cls.sess)

    def test_curve_and_fit(self):
        nos = {r["rung"]: r for r in self.js["curve"]["nosink"]}
        self.assertAlmostEqual(nos["1m"]["ms"]["mean"], 80.0, delta=3.0)
        self.assertAlmostEqual(nos["10k"]["ms"]["mean"], 1.0, delta=0.3)
        self.assertAlmostEqual(nos["1m"]["share_at_5s_pct"], 100 * nos["1m"]["ms"]["mean"] / 5000.0, places=6)
        self.assertAlmostEqual(TAB.share_of_core_pct(80.0, 5.0), 1.6)
        self.assertEqual(TAB.share_of_core_pct(7400.0, 5.0), 100.0)  # a flush longer than the interval
        self.assertIsNone(TAB.share_of_core_pct(None, 5.0))
        self.assertIn("Fit cost = a + b N", self.text)
        self.assertIsNotNone(self.js["fit"]["nosink"])

    def test_families(self):
        conf = self.js["confirmatory"]
        self.assertEqual(len(conf), 5)  # statsd vs nosink at 4 rungs + run W's statsd row
        st1m = [r for r in conf if r["shape"] == "idle-1m"][0]
        self.assertGreater(st1m["effect_pct"], 50)
        self.assertTrue(st1m["verdict"].startswith("differs"), st1m["verdict"])
        w = [r for r in conf if r["metric"] == "cycles_total"][0]
        self.assertEqual((w["arm"], w["ref"]), ("statsd", "flush-off"))
        sec = self.js["secondary"]
        nos_w = [r for r in sec if r["arm"] == "nosink" and r["shape"] == "s"][0]
        self.assertIn("at most", nos_w["verdict"])
        self.assertIn("A/A per rung", self.text)


if __name__ == "__main__":
    unittest.main()


class ReviewRTest(unittest.TestCase):
    def test_r1_flush_fit_and_counters(self):
        from epl import statsrow
        f = statsrow.flush_fit(3 * 1000 + 5, 1000, 3)
        self.assertEqual((f["n"], f["n_error"]), (3, 0))
        self.assertAlmostEqual(f["residual"], 0.005)
        self.assertAlmostEqual(statsrow.flush_fit(2500, 1000, 3)["residual"], 0.5)
        self.assertIn("error", statsrow.flush_fit(10, 0, 1))
        bad = {"snmp": {"InDatagrams": 1}, "sock": None}
        self.assertIn("RcvbufErrors", statsrow.udp_window(bad, bad, 1)["error"])
        th0 = {100: ("envoy", 0), 101: ("wrk:worker_0", 0), 102: ("x", 0)}
        th1 = {100: ("envoy", 50e6), 101: ("wrk:worker_0", 4e6), 102: ("x", 1e6)}
        self.assertAlmostEqual(statsrow.busiest_other_ratio(th0, th1, 100), 12.5)
        ok, _ = statsrow.quiesce(999999999, None, timeout_s=0.1)
        self.assertFalse(ok)  # no such thread: never quiescent, bounded

    def test_r1_configs(self):
        c = MK.configs(box("bench-x86_64"))
        sh = c["m-10k.json"]["shapes"][0]
        self.assertFalse(sh["bursts_visible"])
        self.assertTrue(c["m-1m.json"]["shapes"][0]["bursts_visible"])
        st = [a for a in c["m-100k.json"]["arms"] if a["name"] == "statsd"][0]
        stats_ = [i["stat"] for i in st["evidence"]]
        self.assertIn("udp.sent_per_flush", stats_)
        self.assertIn("udp.fit.n_error", stats_)
        self.assertNotIn("main_over_busiest_other", stats_)
        st1m = [a for a in c["m-1m.json"]["arms"] if a["name"] == "statsd"][0]
        self.assertIn("main_over_busiest_other", [i["stat"] for i in st1m["evidence"]])

    def test_r2_flush_price_forms(self):
        off = {1: {"main": {"run_ms_per_s": 0.5}, "main_perf": {"cycles_per_s": 1e6}}}
        good = {1: {"flush_interval_s": 1, "flushes_from": "bursts",
                    "main": {"run_ms_per_s": 10.5, "run_ms_per_period": 10.6, "period_s": 1.01, "burst_count_error": 0},
                    "main_perf": {"cycles_per_s": 2.3e7}}}
        ms, _ = TAB.flush_price(off, good)
        self.assertAlmostEqual(ms[0], 10.6 - 0.5 * 1.01)
        missed = {1: dict(good[1], main=dict(good[1]["main"], burst_count_error=4, run_ms_per_period=21.0))}
        ms, _ = TAB.flush_price(off, missed)
        self.assertAlmostEqual(ms[0], (10.5 - 0.5) * 1)  # per-second form
        invisible = {1: dict(good[1], flushes_from="interval")}
        self.assertAlmostEqual(TAB.flush_price(off, invisible)[0][0], 10.0)

    def test_r2_price_ratio_across_intervals(self):
        def leg(arm, r, interval, ms_s, per_ms):
            return {"leg_id": "%s%d" % (arm, r), "arm": arm, "shape": "idle-1m", "round": r,
                    "verdict": {"valid": True}, "flush_interval_s": interval, "flushes_from": "bursts",
                    "main": {"run_ms_per_s": ms_s, "run_ms_per_period": per_ms, "period_s": interval,
                             "burst_count_error": 0}}
        legs = []
        for r in range(1, 5):
            legs += [leg("flush-off", r, None, 0.5, None), leg("nosink", r, 1, 80.5 + r * 0.1, 80.5 + r * 0.1),
                     leg("statsd", r, 5, 0, 160.0 * 1.0 + 2.5 + r * 0.2)]
        res = {"legs": legs, "metadata": {"rounds_complete": 4}, "analysis": {},
               "experiment": {"arms": [{"name": n} for n in ("flush-off", "nosink", "statsd")],
                              "shapes": [{"name": "idle-1m"}], "order": "latin"}}
        r = TAB.price_ratio_row(res, "idle-1m", "statsd", "nosink", "x", "confirmatory")
        self.assertIn("intervals differ", r["note"])
        self.assertAlmostEqual(r["effect_pct"], 100.0, delta=2.0)  # 160 ms against 80 ms per flush

    def test_r3_statsd5_smoke_and_merge(self):
        cal = {rr: {"stats_total": 1, "used_total": 1, "settle_s": 2, "ready_timeout_s": 60, "admin_timeout_s": 10}
               for rr, _ in MK.RUNGS}
        cal["1m"]["statsd_interval_s"] = 5
        c = MK.configs(box("bench-x86_64"), cal)
        self.assertIn("smoke-statsd5-1m.json", c)
        self.assertNotIn("smoke-statsd5-100k.json", c)
        st = [a for a in c["smoke-statsd5-1m.json"]["arms"] if a["name"] == "statsd"][0]
        self.assertEqual(st["settings"]["stats_flush"], {"interval_s": 5})
        d = tempfile.mkdtemp()
        for name, arms in (("orig", ("statsd", "nosink", "flush-off")), ("new", ("statsd", "nosink"))):
            os.makedirs(os.path.join(d, name, "config_dump"))
            with open(os.path.join(d, name, "legs.jsonl"), "w") as f:
                for a in arms:
                    f.write(json.dumps({"leg_id": "%s-%s" % (name, a), "arm": a}) + "\n")
                    open(os.path.join(d, name, "config_dump", a + ".json.gz"), "w").write(name)
        n = SESS.merge_smoke(os.path.join(d, "out"), os.path.join(d, "orig"), os.path.join(d, "new"), "statsd")
        self.assertEqual(n, 3)
        ids = [json.loads(x)["leg_id"] for x in open(os.path.join(d, "out", "legs.jsonl")) if x.strip()]
        self.assertEqual(sorted(ids), ["new-statsd", "orig-flush-off", "orig-nosink"])
        self.assertEqual(open(os.path.join(d, "out", "config_dump", "statsd.json.gz")).read(), "new")
        txt = open(os.path.join(SF, "run-session.sh")).read()
        self.assertIn("merge-smoke", txt)
        self.assertIn('echo "$s.statsd5"', txt)

    def test_r4_partial_calibration(self):
        cal = {"1m": {"stats_total": 1100300, "used_total": 600000, "settle_s": 2.5, "ready_timeout_s": 150,
                      "admin_timeout_s": 60}, "10k": {"stats_total": 11000, "used_total": 6000}}
        c = MK.configs(box("bench-x86_64"), cal)
        self.assertNotIn("uncalibrated", c["m-1m.json"])
        self.assertTrue(c["m-10k.json"].get("uncalibrated"))  # settle and timeouts missing
        self.assertTrue(c["m-300k.json"].get("uncalibrated"))
        self.assertTrue(c["w.json"].get("uncalibrated"))
        d = tempfile.mkdtemp()
        for fn, cc in c.items():
            json.dump(cc, open(os.path.join(d, fn), "w"))
        self.assertIn("m-10k", SESS.uncalibrated(d))
        self.assertNotIn("m-1m", SESS.uncalibrated(d))

    def test_r5_guard_edges(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "rmem_max")
        open(f, "w").write("212992\n")
        guard = os.path.join(SF, "sysctl-guard.sh")
        # a value the kernel clamps: the read-back differs, the guard fails, and still restores
        sh = ("GUARD_FILE=%s; GUARD_DIR=%s; . %s; real_set() { echo \"$1\" > \"$GUARD_FILE\"; }; "
              "guard_set() { if [ \"$1\" = 268435456 ]; then echo 1048576 > \"$GUARD_FILE\"; else real_set \"$1\"; fi; }; "
              "guard_begin || exit 9" % (f, d, guard))
        r = subprocess.run(["bash", "-c", sh], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 9)
        self.assertEqual(open(f).read().strip(), "212992")
        # a restore that fails: loud and non-zero
        sh = ("GUARD_FILE=%s; GUARD_DIR=%s; . %s; guard_begin || exit 9; guard_set() { return 1; }; exit 0"
              % (f, d, guard))
        r = subprocess.run(["bash", "-c", sh], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 70)
        self.assertIn("SYSCTL RESTORE FAILED", r.stderr)
        self.assertEqual(open(f).read().strip(), "268435456")
        # the restore command puts the recorded original back
        sh = "GUARD_FILE=%s; GUARD_DIR=%s; . %s; guard_restore" % (f, d, guard)
        r = subprocess.run(["bash", "-c", sh], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(open(f).read().strip(), "212992")
        txt = open(os.path.join(SF, "run-session.sh")).read()
        self.assertIn("trap on_term TERM INT", txt)
        self.assertIn('kill -TERM "$CHILD"', txt)
        self.assertIn("restore)", txt)

    def test_r5_operator_term_forwards_and_restores(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "rmem_max")
        open(f, "w").write("212992\n")
        # the queue's pattern: guard, TERM trap, a child in the background
        txt = open(os.path.join(SF, "run-session.sh")).read()
        funcs = txt.split("# The child of a run in the background")[1].split("mode=${1:-}")[0]
        script = ("set -u; R=%s; log() { echo \"$*\"; }; GUARD_FILE=%s; GUARD_DIR=%s; . %s\n#%s\n"
                  "guard_begin || exit 9; trap on_term TERM INT; echo started; bg_wait sleep 30; echo done"
                  % (d, f, d, os.path.join(SF, "sysctl-guard.sh"), funcs))
        p = subprocess.Popen(["bash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        import time
        for _ in range(200):
            if open(f).read().strip() == "268435456":
                break
            time.sleep(0.05)
        time.sleep(0.3)
        t = time.monotonic()
        p.terminate()
        p.wait(timeout=10)
        self.assertLess(time.monotonic() - t, 5)  # not after the child's 30 s
        self.assertEqual(p.returncode, 143)
        self.assertEqual(open(f).read().strip(), "212992")

    def test_r6_w_flush_evidence(self):
        c = MK.configs(box("bench-x86_64"))["w.json"]
        ev = {a["name"]: a["evidence"] for a in c["arms"]}
        self.assertIn({"stat": "main.bursts", "scope": "field", "max": 0, "label": "no flush in the window"},
                      ev["flush-off"])
        for a in ("nosink", "statsd"):
            self.assertTrue(any(i["stat"] == "main.bursts" and i.get("min") == 3 for i in ev[a]))
        self.assertTrue(any(i["stat"] == "udp.datagrams_per_request" and "ref" in i for i in ev["statsd"]))

    def test_r7_run_refuses_templates_and_uncalibrated(self):
        for fn, needle in (("sibling.json", "template"), ("m-1m.json", "uncalibrated")):
            r = subprocess.run([sys.executable, os.path.join(HERE, "bin", "epl"), "run", os.path.join(X86, fn),
                                "--dry-run", "--allow-short", "--out", tempfile.mkdtemp()],
                               capture_output=True, text=True, timeout=120)
            self.assertNotEqual(r.returncode, 0, fn)
            self.assertIn(needle, r.stderr)


class MfixTest(unittest.TestCase):
    def test_configs(self):
        c = MK.configs(box("bench-x86_64"))
        self.assertNotIn("mfix-1m.json", MK.configs(box("example-aarch64")))
        for rung in ("10k", "100k", "1m"):
            m = c["mfix-%s.json" % rung]
            self.assertTrue(m["box_specific"])
            self.assertEqual(m["order_seed"], 32)
            self.assertEqual([a["name"] for a in m["arms"]],
                             ["nosink-main", "nosink-top", "statsd-main", "statsd-top", "nosink-main-A2"])
            fb = box("bench-x86_64")["fix_binaries"]
            for a in m["arms"]:
                b = a["binaries"]["x86_64"]
                self.assertIn(b["source_sha256"], (fb["main"]["source_sha256"], fb["top"]["source_sha256"]))
                self.assertEqual("top" in a["name"], b["source_sha256"] == fb["top"]["source_sha256"])
                st = [i for i in a["evidence"] if i["stat"] == "stats_total"]
                self.assertTrue(st and "ref" in st[0])  # frozen from its own smoke, not the release's calibration
            self.assertIn("smoke-mfix-%s.json" % rung, c)
        exp = experiment.load(os.path.join(X86, "mfix-1m.json"))
        self.assertEqual(experiment.validate(exp, allow_short=True), [])
        self.assertEqual(len(experiment.schedule(exp)), 25)
        pos = {}
        for r in range(1, 6):
            for i, a in enumerate(experiment.round_order(exp, r)):
                pos.setdefault(a["name"], set()).add(i)
        self.assertTrue(all(len(v) == 5 for v in pos.values()))
        self.assertEqual(portability.check_dirs([X86, ARM]), [])
        txt = open(os.path.join(SF, "run-session.sh")).read()
        self.assertIn("  mfix)", txt)
        self.assertIn("MFIX_STOP_S:-4800", txt)

    def test_table(self):
        tmp = tempfile.mkdtemp()
        sess = os.path.join(tmp, "s")
        for rung in ("100k", "1m"):
            c = json.load(open(os.path.join(X86, "mfix-%s.json" % rung)))
            for a in c["arms"]:
                a["sim_flush_ms"] = {"nosink-top": 40.0, "statsd-top": 70.0, "statsd-main": 140.0}.get(a["name"], 80.0)
            c["sim_cycles_noise"] = 0.01
            p = os.path.join(tmp, "c-%s.json" % rung)
            json.dump(c, open(p, "w"))
            experiment.Runner(experiment.load(p), os.path.join(sess, "mfix-" + rung), SimBackend).run(simulate=True)
        text, js = TAB.tables(sess)
        self.assertIn("Run M-fix", text)
        fix = [r for r in js["mfix"] if r["family"] == "mfix" and r["shape"] == "idle-1m" and r["arm"] == "nosink-top"][0]
        self.assertLess(fix["effect_pct"], -20)
        self.assertTrue(fix["verdict"].startswith("differs"), fix["verdict"])


class ObservationTest(unittest.TestCase):
    def test_saturation_observation_and_labels(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "cal", "1m-statsd"))
        leg = {"stats_total": 1180396, "main": {"run_ms_per_s": 999.8}, "quiesce": {"span_s": 26.5},
               "udp": {"fit": {"n": 11}, "dropped": 0}}
        with open(os.path.join(d, "cal", "1m-statsd", "calibrate-legs.jsonl"), "w") as f:
            f.write(json.dumps(leg) + "\n")
        text, js = TAB.tables(d)
        self.assertIn("busy 100% of the time", text)
        self.assertIn("about 2.4 s", text)
        self.assertIn("flushes start one interval apart", text)
        txt = open(os.path.join(SF, "table.py")).read()
        self.assertIn("own builds (5e1439980a / 3c9cce2f2c)", txt)


class RunSTableTest(unittest.TestCase):
    def test_span_rows(self):
        import random
        rng = random.Random(4)
        exp = experiment.load(os.path.join(X86, "s-1m.json"))
        price = {"nosink": 280.0, "nosink-A2": 280.0, "nosink-5s": 300.0, "nosink-5s-A2": 300.0, "nosink-20s": 320.0,
                 "statsd": 2400.0,
                 "dogstatsd-buf": 900.0, "otlp": 12000.0}
        legs = []
        for r in range(1, 9):
            for a, v in price.items():
                legs.append({"leg_id": "r%02d-idle-1m-%s" % (r, a), "round": r, "shape": "idle-1m", "arm": a,
                             "verdict": {"valid": True}, "flush_interval_s": 1,
                             "span_flushes": {"n": 4, "partial": 0, "run_ms_per_flush": v * rng.gauss(1, 0.005)}})
        res = {"experiment": exp, "legs": legs, "metadata": {"rounds_complete": 8, "incomplete": False}}
        lines, js = TAB.run_s_tables({"s-1m": res})
        rows = {r["arm"]: r for r in js["rows"]}
        self.assertEqual(rows["statsd"]["ref"], "nosink-5s")
        self.assertEqual(rows["otlp"]["ref"], "nosink-20s")
        self.assertAlmostEqual(rows["statsd"]["effect_pct"], 100 * (2400 / 300 - 1), delta=5)
        self.assertAlmostEqual(rows["otlp"]["price_ms_per_flush"]["mean"], 12000 - 320, delta=150)
        self.assertIn("1m", js["aa"])
        self.assertIn("1m@5s", js["aa"])
        self.assertEqual(rows["statsd"]["aa_key"], "1m@5s")
        self.assertIn("A/A reach of the 5 s reference", rows["otlp"]["note"])
        self.assertNotIn("flush-off", " ".join(lines))
        self.assertTrue(any("Run S" in x for x in lines))

    def test_smoke_valid_and_s_budget(self):
        d = tempfile.mkdtemp()
        cfgp = os.path.join(X86, "smoke-s-100k.json")
        exp = experiment.load(cfgp)
        legs = [{"leg_id": a["name"], "shape": "idle-100k", "arm": a["name"], "round": 1, "verdict": {"valid": True}}
                for a in exp["arms"]]
        with open(os.path.join(d, "legs.jsonl"), "w") as f:
            for m in legs:
                f.write(json.dumps(m) + "\n")
            f.write(json.dumps(dict(legs[2], verdict={"valid": False, "reasons": ["drops 2%"]})) + "\n")
        probs = SESS.smoke_problems(cfgp, d)
        self.assertEqual(len(probs), 1)
        self.assertIn("drops 2%", probs[0])
        txt = open(os.path.join(SF, "run-session.sh")).read()
        self.assertIn("S_STOP_S:-12600", txt)
        self.assertIn("s-budget", txt)
        self.assertIn('smoke-valid "$C/$(smoke_of "$run").json"', txt)


class OtlpRerunTest(unittest.TestCase):
    def test_config_script_table(self):
        c = experiment.load(os.path.join(X86, "s-1m-otlp.json"))
        self.assertEqual([a["name"] for a in c["arms"]], ["nosink-20s", "otlp"])
        self.assertEqual((c["rounds"], c["collector"]["max_recv_msg_size_mib"]), (8, 64))
        txt = open(os.path.join(SF, "run-session.sh")).read()
        for m in ("s-otlp-smoke)", "s-otlp)", 'SRUNS="s-1m-otlp" s_check', "s-1m|s-1m-otlp) s=smoke-s-1m"):
            self.assertIn(m, txt)
        exp1 = experiment.load(os.path.join(X86, "s-1m.json"))

        def res_of(exp, arms, otlp_ms):
            legs = []
            for r in range(1, 9):
                for a in arms:
                    v = otlp_ms if a == "otlp" else 300.0 + r
                    legs.append({"leg_id": "r%02d-%s" % (r, a), "round": r, "shape": "idle-1m", "arm": a,
                                 "verdict": {"valid": True}, "span_flushes": {"n": 3, "partial": 0,
                                                                              "run_ms_per_flush": v + r}})
            return {"experiment": exp, "legs": legs, "metadata": {"rounds_complete": 8, "incomplete": False}}
        old = res_of(exp1, [a["name"] for a in exp1["arms"]], 1271.0)
        new = res_of(c, ["nosink-20s", "otlp"], 1500.0)
        lines, js = TAB.run_s_tables({"s-1m": old, "s-1m-otlp": new})
        ot = [r for r in js["rows"] if r["arm"] == "otlp"][0]
        self.assertIn("re-run", ot["label"])
        self.assertAlmostEqual(ot["arm_ms_per_flush"], 1500.0 + 4.5)
