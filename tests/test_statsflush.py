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
        want = {"m-10k": 16, "m-100k": 16, "m-300k": 16, "m-1m": 16, "w": 32, "s-100k": 16, "s-1m": 16, "x-1m": 16}
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
        self.assertEqual(sa["prom"]["prom_scrape_s"], 5)
        self.assertEqual(sa["otlp"]["settings"]["stats_sink"]["kind"], "otlp")
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
        self.assertEqual(SESS.OPTIONAL, ["s-100k", "s-1m", "x-1m"])
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
        self.assertAlmostEqual(nos["1m"]["share_at_5s_pct"], 100 * 80 / 5080.0, delta=0.1)
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
