"""Client pinning (an arm-level client binary pinned by md5 and sha256, with client floors keyed by the client md5)
and the phase path (Nighthawk --phases, warm then measure). Code tests only; no box, no
Nighthawk build."""
import hashlib
import json
import os
import tempfile
import unittest

from epl import experiment, leg, nighthawk, validity
from tests.test_experiment import cfg, load
from tests.test_client_window import leg_record

OLD = "310df412f0907e3df4ad5530872b1e84"
NEW = "245bf838ee2972c958ef2ed31d8f66de"
OLD_SHA = "a9c6542128763ef3e464019b063ffc2f7b3319641f14ba40ed3bdf866f8ee6ba"
NEW_SHA = "bd2d2c3d05ba09c6d5f5968851876ab55c93ed546f2a609b043db340408746b3"


def two_clients(**over):
    """Two arms, the second on its own client binary ."""
    c = cfg(client={"binary": "/bin/true", "md5": NEW, "sha256": NEW_SHA})
    c["arms"][1]["client"] = {"binary": "/bin/sh", "md5": OLD, "sha256": OLD_SHA}
    c.update(over)
    return c


class ArmClientBinaryValidateTest(unittest.TestCase):
    """Validate fails closed on every unpinned or half-pinned client (md5 and sha256)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def errs(self, c):
        return experiment.validate(load(c, self.tmp))

    def has(self, c, text):
        e = self.errs(c)
        self.assertTrue(any(text in x for x in e), (text, e))

    def test_pinned_arm_client_ok(self):
        self.assertEqual(self.errs(two_clients()), [])

    def test_binary_without_a_hash_refused(self):
        c = two_clients()
        del c["arms"][1]["client"]["md5"]
        self.has(c, "client.binary needs client.md5")
        c = two_clients()
        del c["arms"][1]["client"]["sha256"]
        self.has(c, "client.binary needs client.sha256")

    def test_bad_hashes_refused(self):
        for bad in ("310DF412F0907E3DF4AD5530872B1E84", "310df412", 12, ""):
            c = two_clients()
            c["arms"][1]["client"]["md5"] = bad
            self.has(c, "client.binary needs client.md5")
        c = two_clients()
        c["arms"][1]["client"]["sha256"] = OLD
        self.has(c, "client.binary needs client.sha256")
        self.has(two_clients(client={"binary": "/bin/true", "md5": "nope", "sha256": NEW_SHA}),
                 "client.md5 must be 32 lowercase hex")
        self.has(two_clients(client={"binary": "/bin/true", "md5": NEW, "sha256": "x"}),
                 "client.sha256 must be 64 lowercase hex")

    def test_hash_without_binary_refused(self):
        c = cfg(client={"binary": "/bin/true", "md5": NEW, "sha256": NEW_SHA})
        c["arms"][1]["client"] = {"md5": OLD}
        self.has(c, "client.md5 without client.binary")

    def test_experiment_client_must_be_pinned_too(self):
        self.has(two_clients(client={"binary": "/bin/true"}), "must pin the experiment's client too")
        self.has(two_clients(client={"binary": "/bin/true", "md5": NEW}), "must pin the experiment's client too")

    def test_unknown_arm_client_key_still_refused(self):
        c = two_clients()
        c["arms"][1]["client"]["sha1"] = "x"
        self.has(c, "unknown client keys ['sha1']")

    def test_calibration_arms(self):
        self.assertEqual(self.errs(two_clients(client_calibration={"arm": ["a", "b"]})), [])
        self.assertEqual(self.errs(two_clients(client_calibration={"arm": "b"})), [])
        for bad in ("zz", ["a", "a"], [], ["a", 3]):
            self.has(two_clients(client_calibration={"arm": bad}), "client_calibration.arm")

    def test_old_configs_unchanged(self):
        # no pin anywhere: nothing new is required
        self.assertEqual(self.errs(cfg()), [])
        self.assertEqual(self.errs(cfg(client={"binary": "/bin/true", "md5": NEW})), [])

    def test_load_expands_arm_client_binary(self):
        c = two_clients()
        c["arms"][1]["client"]["binary"] = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"
        exp = load(c, self.tmp)
        self.assertEqual(exp["arms"][1]["client"]["binary"],
                         os.path.expanduser("~/nighthawk-dogfood/bazel-bin/nighthawk_client"))

    def test_client_pin(self):
        exp = load(two_clients(), self.tmp)
        self.assertEqual(experiment.client_pin(exp, exp["arms"][0]), ("/bin/true", NEW))
        self.assertEqual(experiment.client_pin(exp, exp["arms"][1]), ("/bin/sh", OLD))
        self.assertEqual(experiment.client_pin_sha256(exp, exp["arms"][1]), OLD_SHA)
        self.assertEqual(experiment.client_pin_sha256(exp, exp["arms"][0]), NEW_SHA)
        exp2 = load(cfg(), self.tmp)
        self.assertEqual(experiment.client_pin(exp2, exp2["arms"][1]), ("/bin/true", None))


class ClientSignatureMd5Test(unittest.TestCase):
    """A floor carries the client md5 and applies only to legs with the same md5 and flags."""

    def args(self, rps=1600):
        return nighthawk.client_args({"concurrency": 16}, rps, "http://127.0.0.1:1/s", None, True, ["--h2"])

    def test_md5_in_signature(self):
        a = self.args()
        self.assertEqual(nighthawk.client_signature(a, "u"), nighthawk.client_signature(a, "u", None))
        s_new = nighthawk.client_signature(a, "u", NEW)
        self.assertEqual(s_new[0], "md5:" + NEW)
        self.assertEqual(s_new[1:], nighthawk.client_signature(a, "u"))
        self.assertNotEqual(s_new, nighthawk.client_signature(a, "u", OLD))
        # the rate still drops out with a pin
        self.assertEqual(nighthawk.client_signature(self.args(16), "u", NEW), s_new)

    def test_floor_per_md5(self):
        a = self.args()
        f_new = {"leg_id": "r00-s-floor-off", "ok": True, "thread_busy_max": 0.25,
                 "client_signature": nighthawk.client_signature(a, "u", NEW)}
        f_old = dict(f_new, leg_id="r00-s-floor-off-old", thread_busy_max=0.30,
                     client_signature=nighthawk.client_signature(a, "u", OLD))
        x = leg.above_floor([f_new, f_old], 0.40, None, nighthawk.client_signature(a, "u", OLD))
        self.assertEqual(x["client_floor_leg"], "r00-s-floor-off-old")
        self.assertAlmostEqual(x["client_busy_above_floor"], 0.10)
        y = leg.above_floor([f_new, f_old], 0.40, None, nighthawk.client_signature(a, "u", NEW))
        self.assertEqual(y["client_floor_leg"], "r00-s-floor-off")
        # a third binary, or the same flags without the pin: no floor
        z = leg.above_floor([f_new, f_old], 0.40, None, nighthawk.client_signature(a, "u", "0" * 32))
        self.assertTrue(z["client_floor_mismatch"])
        self.assertTrue(leg.above_floor([f_new, f_old], 0.40, None, nighthawk.client_signature(a, "u"))
                        ["client_floor_mismatch"])

    def test_floor_record_carries_pin_and_refuses_a_wrong_file(self):
        m = leg_record(client_thread_busy_max=0.2, client_sending={"ok": True}, client_signature=["md5:" + NEW],
                       client_md5_pin=NEW, client_exe_ok=True)
        f = leg.client_floor_record(m, "r00-s-floor-a")
        self.assertTrue(f["ok"], f)
        self.assertEqual(f["client_md5_pin"], NEW)
        f2 = leg.client_floor_record(dict(m, client_exe_ok=False, client_md5=OLD, client_sha256=OLD_SHA),
                                     "r00-s-floor-a")
        self.assertFalse(f2["ok"])
        self.assertIn("client binary not the pinned one (md5 %s sha256 %s)" % (OLD, OLD_SHA), f2["why"])


class ExeHashTest(unittest.TestCase):
    """The md5 and sha256 of the measured client's own executed
    inode, read after the client ended, against both pins; (st_dev, st_ino) recorded beside it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "nighthawk_client")
        with open(self.path, "wb") as f:
            f.write(b"\x7fELF" + os.urandom(3 << 20))
        with open(self.path, "rb") as f:
            b = f.read()
        self.md5, self.sha = hashlib.md5(b).hexdigest(), hashlib.sha256(b).hexdigest()

    def test_record_from_descriptor(self):
        fd = os.open(self.path, os.O_RDONLY)
        r = leg.exe_hash_record(fd, self.path, self.md5, self.sha, self.path)
        self.assertEqual((r["client_md5"], r["client_sha256"], r["client_exe_ok"]), (self.md5, self.sha, True))
        self.assertEqual(r["client_exe_dev_ino"], r["client_pin_dev_ino"])
        with self.assertRaises(OSError):
            os.fstat(fd)  # closed
        self.assertTrue(validity.verdict(leg_record(**r))["valid"])

    def test_descriptor_keeps_the_executed_file(self):
        fd = os.open(self.path, os.O_RDONLY)
        other = self.path + ".other"
        with open(other, "wb") as f:
            f.write(b"other")
        os.replace(other, self.path)  # replaced after the process started: the executed inode is still hashed
        r = leg.exe_hash_record(fd, self.path, self.md5, self.sha, self.path)
        self.assertTrue(r["client_exe_ok"])
        self.assertNotEqual(r["client_exe_dev_ino"], r["client_pin_dev_ino"])  # recorded beside the hash

    def test_mismatch_of_either_hash_invalidates(self):
        for md5, sha in ((OLD, self.sha), (self.md5, OLD_SHA)):
            fd = os.open(self.path, os.O_RDONLY)
            r = leg.exe_hash_record(fd, self.path, md5, sha)
            self.assertFalse(r["client_exe_ok"])
            v = validity.verdict(leg_record(**r))
            self.assertFalse(v["valid"])
            self.assertTrue(any(x.startswith("client binary not the pinned one") for x in v["reasons"]))

    def test_unreadable_fails_closed(self):
        fd = os.open(self.path, os.O_RDONLY)
        os.close(fd)
        r = leg.exe_hash_record(fd, self.path, NEW, NEW_SHA)
        self.assertEqual((r["client_md5"], r["client_exe_ok"]), (None, False))
        self.assertIn("client_exe_error", r)
        self.assertFalse(validity.verdict(leg_record(**r))["valid"])
        self.assertFalse(validity.verdict(leg_record(client_md5_pin=NEW))["valid"])  # nothing recorded

    def test_no_pin_no_gate(self):
        self.assertTrue(validity.verdict(leg_record(client_md5=OLD, client_exe_ok=False))["valid"])

    @unittest.skipUnless(os.path.exists("/proc/self/exe"), "needs /proc (Linux)")
    def test_open_exe_and_identity_of_a_process(self):
        import subprocess
        import sys
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
        try:
            exe = os.path.realpath(sys.executable)
            fd, path = leg.open_exe(p.pid)
            b = open(exe, "rb").read()
            r = leg.exe_hash_record(fd, path, hashlib.md5(b).hexdigest(), hashlib.sha256(b).hexdigest(), exe)
            self.assertTrue(r["client_exe_ok"], r)
            self.assertTrue(leg.exe_identity(p.pid, exe)["client_exe_ok"])
        finally:
            p.kill()
            p.wait()

    def test_identity_fails_closed(self):
        r = leg.exe_identity(2 ** 22 + 12345, "/bin/sh")
        self.assertFalse(r["client_exe_ok"])
        self.assertIn("client_exe_error", r)

    def test_run_leg_hashes_after_the_client_ended(self):
        import inspect
        src = inspect.getsource(leg.RealBackend.run_leg)
        i = src.index("cl_exe = open_exe(cl.pid)")
        self.assertLess(src.index("time.sleep(lead_wait)"), i)  # after taskset has exec'd
        j = src.index("self.own.stop(cl)", i)
        self.assertIn("exe_hash_record(cl_exe[0], cl_exe[1], cl_pin, _exp.client_pin_sha256(e, arm), nh)",
                      src[j:j + 300])  # in the finally, after the client ended
        self.assertIn("nighthawk.client_signature(ma, url, cl_pin)", src)


class BinaryProofTest(unittest.TestCase):
    """The run's binary proof covers every pinned client binary (md5 and sha256) at the start and the end."""

    def test_check_binaries(self):
        tmp = tempfile.mkdtemp()
        exp = load(two_clients(), tmp)
        md = {"arms": {a["name"]: {"md5": "x", "sha256": "y"} for a in exp["arms"]},
              "client": {"md5": NEW, "sha256": NEW_SHA},
              "client_arms": {"b": {"md5": OLD, "md5_pin": OLD, "sha256": OLD_SHA, "sha256_pin": OLD_SHA}}}
        self.assertEqual(experiment.check_binaries(exp, md), [])
        md["client"]["md5"] = OLD
        md["client_arms"]["b"]["md5"] = NEW
        md["client_arms"]["b"]["sha256"] = NEW_SHA
        e = experiment.check_binaries(exp, md)
        self.assertEqual(len(e), 3, e)
        self.assertTrue(e[0].startswith("client md5 %s != pinned %s" % (OLD, NEW)))
        self.assertTrue(e[1].startswith("arm b client md5 %s != pinned %s" % (NEW, OLD)))
        self.assertTrue(e[2].startswith("arm b client sha256"))

    def test_metadata_and_end_hash(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "nh_old")
        with open(p, "wb") as f:
            f.write(b"old client")
        want = hashlib.md5(b"old client").hexdigest()
        want_sha = hashlib.sha256(b"old client").hexdigest()
        sh = os.path.join(tmp, "envoy")
        with open(sh, "w") as f:
            f.write("#!/bin/sh\necho 'version: stand-in/1.0'\n")
        os.chmod(sh, 0o755)
        with open(sh, "rb") as f:
            b = f.read()
        c = two_clients(client={"binary": sh, "md5": hashlib.md5(b).hexdigest(),
                                "sha256": hashlib.sha256(b).hexdigest()})
        for a in c["arms"]:
            a["binary"] = sh
        c["arms"][1]["client"] = {"binary": p, "md5": want, "sha256": want_sha}
        exp = load(c, tmp)
        md = experiment.collect_metadata(exp, "{}")
        self.assertEqual((md["client_arms"]["b"]["md5"], md["client_arms"]["b"]["sha256_pin"]), (want, want_sha))
        self.assertEqual(experiment.check_binaries(exp, dict(md, arms={a["name"]: {"md5": "", "sha256": ""}
                                                                       for a in exp["arms"]})), [])
        end = experiment.client_md5s_at_end(exp)
        self.assertEqual(end[p], {"md5": want, "sha256": want_sha})
        self.assertTrue(experiment.client_pins_unchanged(exp, end))
        with open(p, "ab") as f:
            f.write(b"!")
        self.assertFalse(experiment.client_pins_unchanged(exp, experiment.client_md5s_at_end(exp)))


class CalibrationPerArmTest(unittest.TestCase):
    """One floor per (arm, shape), each keyed by its client signature (md5 and flags)."""

    def test_runner(self):
        from epl.sim import SimBackend

        class Sending(SimBackend):
            def run_leg(self, arm, shape, rnd, bp, lid):
                m = SimBackend.run_leg(self, arm, shape, rnd, bp, lid)
                pin = experiment.client_pin(self.exp, arm)[1]
                m.update(client_sending={"ok": True, "reasons": []}, client_thread_busy_max=0.2,
                         client_md5_pin=pin, client_exe_ok=True, client_signature=["md5:%s" % pin])
                return m
        tmp = tempfile.mkdtemp()
        exp = load(two_clients(client_calibration={"arm": ["a", "b"]}), tmp)
        self.assertEqual([a["name"] for a in experiment.calibration_arms(exp)], ["a", "b"])
        res = experiment.Runner(exp, os.path.join(tmp, "run"), Sending).run(simulate=True)
        fl = res["metadata"]["client_floors"]
        self.assertEqual([f["leg_id"] for f in fl], ["r00-s-floor-a", "r00-s-floor-b"])
        self.assertEqual([f["client_md5_pin"] for f in fl], [NEW, OLD])
        self.assertTrue(all(f["ok"] for f in fl))
        self.assertEqual(len([m for m in res["legs"] if m.get("client_calibration")]), 2)
        exp1 = load(two_clients(client_calibration={}), tmp)
        self.assertEqual([a["name"] for a in experiment.calibration_arms(exp1)], ["a"])


class SimPinTest(unittest.TestCase):
    """Client pinning in a dry run: the simulator records the pin, and the fault "client_md5" (another file) invalidates."""

    def test_sim(self):
        from epl.sim import SimBackend
        tmp = tempfile.mkdtemp()
        exp = load(two_clients(sim_faults={"r01-s-b": "client_md5"}), tmp)
        sb = SimBackend(exp, tmp, lambda m: None)
        m = sb.run_leg(exp["arms"][1], exp["shapes"][0], 1, None, "r01-s-a")
        self.assertEqual((m["client_md5_pin"], m["client_exe_ok"]), (OLD, True))
        self.assertTrue(m["verdict"]["valid"], m["verdict"])
        bad = sb.run_leg(exp["arms"][1], exp["shapes"][0], 1, None, "r01-s-b")
        self.assertFalse(bad["verdict"]["valid"])
        plain = SimBackend(load(cfg(), tmp), tmp, lambda m: None).run_leg(
            exp["arms"][0], exp["shapes"][0], 1, None, "r01-s-a")
        self.assertNotIn("client_md5_pin", plain)
        self.assertNotIn("client_sequencer", plain)



# ---------------------------------------------------------------- the phase path

def phase_json(workers=2, warm_start="2026-11-26T10:00:00.5Z", measure_start="2026-11-26T10:00:05.7Z",
               measure_dur="22.5s", completed=None, graceful=0, md_over=None, blocking=0, drop_phase_result=None,
               connections=4, extra_counters=None):
    """A Nighthawk --phases JSON output as the fork writes it (process_impl.cc at epl-client-2026-11/v1): the
    global result (the run's counters; the last phase's execution), one result per worker (its LAST phase's rate
    limiter start and sequencer elapsed; its live statistic sets are empty), one result per phase
    (phase_<i>_<name>, phase_id set, statistics merged over the workers, no counters, no execution_start), and
    one phase_metadata entry per phase (proto JSON: uint64 as strings, defaults left out)."""
    rate = 200
    completed = completed if completed is not None else int(rate * 22.5)
    c = {"benchmark.http_2xx": rate * 5 + completed, "upstream_rq_total": rate * 5 + completed,
         "upstream_cx_total": workers * connections, "upstream_cx_http1_total": workers * connections,
         "upstream_rq_pending_total": workers}
    if graceful:
        c["graceful_stop_requested"] = graceful
    c.update(extra_counters or {})

    def stats(blk, r2r_max):
        return [{"id": "benchmark_http_client.request_to_response", "count": "900", "mean": "0.0004s",
                 "max": r2r_max, "percentiles": [{"percentile": 0.5, "duration": "0.0004s"},
                                                 {"percentile": 0.99, "duration": "0.002s"}]},
                {"id": "sequencer.blocking", "count": str(blk), "max": "0.003s" if blk else "0s"},
                {"id": "sequencer.callback", "count": "900", "max": "0.012s"}]
    res = [{"name": "global", "execution_start": measure_start, "execution_duration": measure_dur,
            "statistics": stats(blocking, "0.009s"),
            "counters": [{"name": k, "value": str(v)} for k, v in c.items()]}]
    if workers > 1:
        res += [{"name": "worker_%d" % i, "execution_start": measure_start, "execution_duration": measure_dur,
                 "statistics": [], "counters": []} for i in range(workers)]
    for i, (name, dur, r2r) in enumerate((("warm", "5s", "0.031s"), ("measure", measure_dur, "0.007s"))):
        if name == drop_phase_result:
            continue
        res.append({"name": "phase_%d_%s" % (i, name), "execution_duration": dur, "phase_id": name,
                    "statistics": stats(blocking if name == "measure" else 0, r2r), "counters": []})
    md = []
    for i, (name, n) in enumerate((("warm", rate * 5), ("measure", completed))):
        x = {"phase_id": name, "worker_count": workers, "initiated": str(n), "completed": str(n),
             "completion_ratio": 1, "pool_health": [{"worker_id": w, "connections_created": str(connections),
                                                     "connections_active": str(connections)}
                                                    for w in range(workers)]}
        if i:
            x["phase_index"] = i
        else:
            x.update(drain_duration="0.004s", idle_gap="0.001s")
        x.update((md_over or {}).get(name, {}))
        md.append(x)
    return {"results": res, "phase_metadata": md,
            "version": {"version": {"major_number": 0, "minor_number": 3, "patch": 0}}}


def write(tmp, obj, name="nh.json"):
    p = os.path.join(tmp, name)
    with open(p, "w") as f:
        json.dump(obj, f)
    return p


class PhaseArgsTest(unittest.TestCase):
    def test_vector_and_args(self):
        v = nighthawk.phase_vector(5200, 16, 5, 120)
        self.assertEqual(v, [{"name": "warm", "duration": "5s", "requests_per_second": 5200, "concurrency": "16"},
                             {"name": "measure", "duration": "120s", "requests_per_second": 5200,
                              "concurrency": "16"}])
        a = nighthawk.client_args({"concurrency": 16, "connections_per_worker": 32}, 5200, "http://127.0.0.1:1/s",
                                  None, True, ["--prefetch-connections"], phases=v)
        for flag in ("--rps", "--concurrency", "--duration", "--no-duration"):
            self.assertNotIn(flag, a)  # Nighthawk refuses each of them beside --phases
        self.assertEqual(a[:2], ["--connections", "32"])
        self.assertEqual(json.loads(a[a.index("--phases") + 1]), v)
        self.assertEqual(a[-1], "http://127.0.0.1:1/s")
        self.assertIn("--prefetch-connections", a)
        # the plain path is unchanged
        self.assertEqual(nighthawk.client_args({"concurrency": 16}, 1600, "u", 25, True)[:8],
                         ["--rps", "100", "--connections", "16", "--concurrency", "16", "--duration", "25"])

    def test_divisibility_rule_per_phase_at_leg_time(self):
        with self.assertRaises(ValueError) as cm:
            nighthawk.client_args({"concurrency": 16}, 5201, "u", None, True,
                                  phases=nighthawk.phase_vector(5201, 16, 5, 120))
        self.assertIn("phase warm: planned total rate 5201 is not divisible by the 16", str(cm.exception))
        bad = [{"name": "warm", "requests_per_second": 5200, "concurrency": "16"},
               {"name": "measure", "requests_per_second": 5200, "concurrency": "12"}]
        e = experiment.phase_rate_errors(bad, 16)
        self.assertEqual(len(e), 1)
        self.assertTrue(e[0].startswith("phase measure: planned total rate 5200 is not divisible by the 12"))

    def test_signature_drops_phase_rates(self):
        c = {"concurrency": 16, "connections_per_worker": 32}
        full = nighthawk.client_args(c, 5200, "u", None, True, phases=nighthawk.phase_vector(5200, 16, 5, 120))
        floor = nighthawk.client_args(c, 16, "v", None, True, phases=nighthawk.phase_vector(16, 16, 5, 120))
        self.assertEqual(nighthawk.client_signature(full, "u", NEW), nighthawk.client_signature(floor, "v", NEW))
        other = nighthawk.client_args(c, 5200, "u", None, True, phases=nighthawk.phase_vector(5200, 16, 3, 120))
        self.assertNotEqual(nighthawk.client_signature(full, "u"), nighthawk.client_signature(other, "u"))
        plain = nighthawk.client_args(c, 5200, "u", None, True)
        self.assertNotEqual(nighthawk.client_signature(full, "u"), nighthawk.client_signature(plain, "u"))


class PhaseOutputTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_measure_phase_only(self):
        p = write(self.tmp, phase_json(workers=2, blocking=3))
        d = nighthawk.parse_output(p, measure_phase="measure")
        self.assertEqual([w["name"] for w in d["worker_exec"]], ["worker_0", "worker_1"])  # no phase results
        self.assertEqual(d["worker_exec"][0]["duration_s"], 22.5)
        self.assertEqual(d["responses_2xx"], 4500)  # measure completed, not the run's 2xx
        self.assertAlmostEqual(d["rate_2xx"], 200.0)
        self.assertEqual(d["execution_duration_s"], 22.5)
        self.assertEqual(d["latency_us"]["max"], 7000.0)  # the measure phase's, not the warm phase's 31 ms
        self.assertEqual(d["sequencer"]["blocking_count_total"], 3)
        self.assertEqual(list(d["sequencer"]["per_worker"]), ["phase:measure"])
        self.assertEqual(d["counters"]["benchmark.http_2xx"], 5500)  # run-wide counters stay run-wide
        self.assertEqual(d["cx_total"], 8)
        self.assertEqual([x["phase_id"] for x in d["phases"]["metadata"]], ["warm", "measure"])
        self.assertEqual(d["phases"]["metadata"][1]["completed"], 4500)
        self.assertEqual(d["phases"]["metadata"][0]["drain_s"], 0.004)
        self.assertEqual(d["phases"]["metadata"][1]["phase_index"], 1)
        self.assertEqual(d["phases"]["metadata"][0]["connections_created"], 8)

    def test_phase_results_never_count_as_workers_without_measure(self):
        d = nighthawk.parse_output(write(self.tmp, phase_json(workers=2)))
        self.assertEqual(len(d["worker_exec"]), 2)
        self.assertIn("phases", d)

    def test_missing_measure_result(self):
        d = nighthawk.parse_output(write(self.tmp, phase_json(drop_phase_result="measure")), measure_phase="measure")
        self.assertIsNone(d["sequencer"]["blocking_count_total"])
        self.assertIsNone(d["latency_us"]["max"])
        self.assertEqual(d["execution_duration_s"], 0.0)

    def test_plain_output_unchanged(self):
        from tests.test_client_window import nh_json
        d = nighthawk.parse_output(write(self.tmp, nh_json(workers=2)))
        self.assertNotIn("phases", d)
        self.assertEqual(d["responses_2xx"], 1000)
        self.assertAlmostEqual(d["rate_2xx"], 1000 / 24.5)
        self.assertEqual(sorted(d["sequencer"]["per_worker"]), ["worker_0", "worker_1"])


class PhaseCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.vec = nighthawk.phase_vector(400, 2, 5, 60)
        # wall clock of the measure start (10:00:05.7Z) put at monotonic 1005.7: window opens at 1008.0
        self.mono = 1005.7 - nighthawk.parse_timestamp("2026-11-26T10:00:05.7Z")

    def check(self, obj, t_q0=1008.0, min_lead=1.5, cx=8, workers=2):
        d = nighthawk.parse_output(write(self.tmp, obj), measure_phase="measure")
        return nighthawk.phase_check(d, self.vec, workers, d["worker_exec"], self.mono, t_q0, min_lead, cx)

    def test_ok(self):
        r = self.check(phase_json())
        self.assertTrue(r["ok"], r["reasons"])
        self.assertAlmostEqual(r["measure_lead_in_s"], 2.3, places=3)

    def test_each_failure_is_named(self):
        cases = [
            (phase_json(md_over={"measure": {"worker_count": 1}}), "phase measure ran on 1 workers, planned 2"),
            (phase_json(md_over={"measure": {"new_workers_cold_started": True}}), "workers cold-started"),
            (phase_json(md_over={"measure": {"workers_changed_vs_prior_phase": True}}), "worker set changed"),
            (phase_json(md_over={"warm": {"drain_censored": True}}), "phase warm: its ending drain was censored"),
            (phase_json(md_over={"measure": {"gate_exceeded": "7"}}), "7 starts refused by a per-phase gate"),
            (phase_json(drop_phase_result="warm"), "no per-phase result for ['warm']"),
            (phase_json(connections=5), "the client opened 10 connections, expected 8"),
        ]
        for obj, want in cases:
            r = self.check(obj)
            self.assertFalse(r["ok"], want)
            self.assertTrue(any(want in x for x in r["reasons"]), (want, r["reasons"]))

    def test_metadata_order_and_lead_in(self):
        obj = phase_json()
        obj["phase_metadata"].reverse()
        self.assertIn("phase_metadata lists ['measure', 'warm'], planned ['warm', 'measure']",
                      self.check(obj)["reasons"])
        r = self.check(phase_json(), t_q0=1006.5)
        self.assertFalse(r["ok"])
        self.assertIn("the measure phase began 0.800 s before the window's first read", r["reasons"][0])
        obj = phase_json()
        del obj["phase_metadata"]
        self.assertFalse(self.check(obj)["ok"])

    def test_sending_check_on_measure_phase(self):
        d = nighthawk.parse_output(write(self.tmp, phase_json(graceful=2)), measure_phase="measure")
        # the measure phase ends at 1005.7 + 22.5 = 1028.2: 1.7 s after a last read at 1026.5, 0.4 s after 1027.8
        cs = nighthawk.sending_check("window", d["worker_exec"], self.mono, 1008.0, 1026.5, 0.0, 1.0, True, 0,
                                     d["graceful_stop_requested"], d["failed_terminations"], workers=2)
        self.assertTrue(cs["ok"], cs["reasons"])
        self.assertAlmostEqual(cs["first_end_after_last_read_s"], 1.7, places=3)
        late = nighthawk.sending_check("window", d["worker_exec"], self.mono, 1008.0, 1027.8, 0.0, 1.0, True, 0,
                                       d["graceful_stop_requested"], d["failed_terminations"], workers=2)
        self.assertFalse(late["ok"])


def ph_cfg(**arm_client):
    """Two arms: the old recipe (base) and the phase recipe with the window lifetime."""
    c = cfg(client={"binary": "/bin/true", "concurrency": 16, "connections_per_worker": 32,
                    "extra_args": ["--prefetch-connections"]})
    c["shapes"] = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200}]
    ac = {"recipe": "phases", "lifetime": "window", "phases": {"warm_s": 5, "measure_cap_s": 120}}
    ac.update(arm_client)
    c["arms"][1]["client"] = ac
    return c


class PhaseValidateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def errs(self, c):
        return experiment.validate(load(c, self.tmp))

    def has(self, c, text):
        e = self.errs(c)
        self.assertTrue(any(text in x for x in e), (text, e))

    def test_ok(self):
        self.assertEqual(self.errs(ph_cfg()), [])
        self.assertEqual(self.errs(ph_cfg(lifetime="duration", phases={"warm_s": 5, "measure_cap_s": 30})), [])
        exp = load(ph_cfg(), self.tmp)
        c = experiment.arm_client_cfg(exp, exp["arms"][1])
        self.assertEqual((c["recipe"], c["lifetime"], c["concurrency"]), ("phases", "window", 16))
        self.assertEqual(experiment.arm_client_cfg(exp, exp["arms"][0]).get("recipe", "plain"), "plain")

    def test_divisibility_rule_wired_at_plan_time(self):
        c = ph_cfg()
        c["shapes"][0]["rps"] = 5208  # divisible by 16 but then by a 12-worker rung
        c["shapes"][0]["client_concurrency"] = 12
        self.assertEqual(self.errs(c), [])
        c["shapes"][0]["rps"] = 5200
        self.has(c, "arm b, shape s: phase warm: planned total rate 5200 is not divisible by the 12")

    def test_measure_cap(self):
        self.has(ph_cfg(phases={"warm_s": 5, "measure_cap_s": 25}), "measure_cap_s 25 must be at least 30.5")
        self.has(ph_cfg(lifetime="duration", phases={"warm_s": 5, "measure_cap_s": 23}),
                 "measure_cap_s 23 must be at least 24.0")

    def test_phase_settings(self):
        self.has(ph_cfg(phases={"warm_s": 5}), "client.phases ['measure_cap_s']")
        self.has(ph_cfg(phases={"warm_s": 0.5, "measure_cap_s": 120}), "client.phases ['warm_s']")
        self.has(ph_cfg(phases={"warm_s": 5, "measure_cap_s": 120, "rps_total": 1}), "client.phases takes")
        self.has(ph_cfg(phases={"warm_s": 5, "measure_cap_s": 120, "min_lead_in_s": 3}),
                 "min_lead_in_s above the lead-in")
        self.has(ph_cfg(recipe="plain"), "client.phases without client.recipe phases")
        self.has(ph_cfg(recipe="burst"), "client.recipe must be plain or phases")
        self.has(ph_cfg(lifetime="forever"), "client.lifetime must be duration or window")

    def test_refused_combinations(self):
        c = ph_cfg()
        c["shapes"][0]["warmup_s"] = 5
        self.has(c, "a shape warm-up process with recipe phases")
        ramp = ('--rate-limiter-plugin={"typed_config":{"@type":"type.googleapis.com/nighthawk.'
                'LinearRampingRateLimiterConfig","ramp_time":"1s"}}')
        c = ph_cfg()
        c["shapes"][0]["client_extra_args"] = [ramp]
        self.has(c, "a ramping rate limiter with recipe phases")
        # a phase vector in any argument list is still refused (the harness builds it, and checks it)
        c = ph_cfg(extra_args=["--phases", "[]"])
        self.has(c, "client phases are refused")

    def test_window_arithmetic_per_arm(self):
        # the experiment's lifetime is window, but the base arm runs the duration recipe: its arithmetic applies
        c = ph_cfg()
        c["client"].update(lifetime="window", duration_s=10)
        c["arms"][0]["client"] = {"lifetime": "duration"}
        self.has(c, "client duration must exceed lead_in + window + 1 s")
        c["arms"][0]["client"] = {}
        self.assertEqual(self.errs(c), [])


class PhaseLegTest(unittest.TestCase):
    def test_run_leg_phase_path(self):
        import inspect
        src = inspect.getsource(leg.RealBackend.run_leg)
        self.assertIn("ccfg, mcfg = e[\"envoy\"], _exp.arm_client_cfg(e, arm), e[\"measure\"]", src)
        i = src.index("pvec = _exp.leg_phase_vector(ccfg, shape)")
        self.assertLess(i, src.index("if warm_s > 0:"))  # no separate warm-up process with phases
        self.assertIn("cbase, phases=pvec)", src)
        self.assertIn('lead_wait = mcfg["lead_in_s"] + (pset["warm_s"] + pset["boundary_allow_s"] if pvec else 0)',
                      src)
        self.assertIn("measure_phase=nighthawk.MEASURE if pvec else None", src)
        self.assertIn("nighthawk.phase_check(", src)

    def test_validity(self):
        ok = {"ok": True, "reasons": []}
        self.assertTrue(validity.verdict(leg_record(client_recipe="phases", client_phases=ok))["valid"])
        v = validity.verdict(leg_record(client_recipe="phases"))
        self.assertIn("no client-phases record (recipe phases)", v["reasons"])
        v = validity.verdict(leg_record(client_phases={"ok": False, "reasons": ["phase warm: x"]}))
        self.assertIn("client phases: phase warm: x", v["reasons"])
        self.assertTrue(validity.verdict(leg_record())["valid"])


class PhaseStandInTest(unittest.TestCase):
    """A stand-in client that keeps Nighthawk's phase-run output contract and its SIGTERM contract: one SIGTERM ends
    the measure phase, the output is complete, the exit code 0; the harness then reads the measure phase."""

    STANDIN = r"""
import json, signal, sys, time, datetime
args = sys.argv[1:]
ph = json.loads(args[args.index("--phases") + 1])
workers = int(ph[0]["concurrency"])
stop = {"t": None}
signal.signal(signal.SIGTERM, lambda *a: stop.__setitem__("t", time.time()))
def iso(t):
    return datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
t0 = time.time()
warm = float(ph[0]["duration"].rstrip("s"))
time.sleep(warm)
m0 = time.time()
cap = float(ph[1]["duration"].rstrip("s"))
while stop["t"] is None and time.time() < m0 + cap:
    time.sleep(0.01)
end = stop["t"] or time.time()
rps = ph[1]["requests_per_second"]
done = int(rps * (end - m0))
res = [{"name": "global", "execution_start": iso(m0), "execution_duration": "%.6fs" % (end - m0),
        "statistics": [], "counters": [{"name": "benchmark.http_2xx", "value": str(done + int(rps * warm))},
                                       {"name": "upstream_cx_total", "value": str(workers * 4)},
                                       {"name": "graceful_stop_requested", "value": str(workers if stop["t"] else 0)}]}]
res += [{"name": "worker_%d" % i, "execution_start": iso(m0), "execution_duration": "%.6fs" % (end - m0),
         "statistics": [], "counters": []} for i in range(workers)]
for i, p in enumerate(ph):
    d = warm if i == 0 else end - m0
    res.append({"name": "phase_%d_%s" % (i, p["name"]), "phase_id": p["name"], "execution_duration": "%.6fs" % d,
                "statistics": [{"id": "sequencer.blocking", "count": "0"},
                               {"id": "sequencer.callback", "count": "10", "max": "0.001s"}], "counters": []})
md = [{"phase_id": p["name"], "phase_index": i, "worker_count": workers,
       "completed": str(int(rps * warm) if i == 0 else done)} for i, p in enumerate(ph)]
print(json.dumps({"results": res, "phase_metadata": md}))
"""

    def test_sigterm_in_measure_phase(self):
        import subprocess
        import sys
        import time
        tmp = tempfile.mkdtemp()
        script = os.path.join(tmp, "nh_standin.py")
        with open(script, "w") as f:
            f.write(self.STANDIN)
        vec = nighthawk.phase_vector(400, 2, 1, 60)
        args = nighthawk.client_args({"concurrency": 2, "connections_per_worker": 4}, 400, "http://x/s", None, True,
                                     ["--prefetch-connections"], phases=vec)
        own = leg.OwnProcesses()
        out_path = os.path.join(tmp, "nh.json")
        cl_clock = leg.clock_pair()
        with open(out_path, "w") as out:
            p = own.start([sys.executable, "-I", script] + args, stdout=out)
            time.sleep(1 + 0.3 + 0.5)            # warm + allowance + lead-in
            t_q0 = time.monotonic()
            time.sleep(0.6)                       # the window
            t2 = time.monotonic()
            time.sleep(1.2)                       # margin + slack
            rc = own.terminate(p, grace_s=10)
            own.stop(p)
        self.assertEqual(rc, 0)
        d = nighthawk.parse_output(out_path, measure_phase="measure")
        mono = (cl_clock["monotonic_ns"] - cl_clock["time_ns"]) / 1e9
        cs = nighthawk.sending_check("window", d["worker_exec"], mono, t_q0, t2, 0.0, 1.0, True, rc,
                                     d["graceful_stop_requested"], d["failed_terminations"], workers=2)
        self.assertTrue(cs["ok"], cs["reasons"])
        pc = nighthawk.phase_check(d, vec, 2, d["worker_exec"], mono, t_q0, 0.3, cx_expected=8)
        self.assertTrue(pc["ok"], pc["reasons"])
        self.assertGreater(pc["measure_lead_in_s"], 0.3)
        self.assertEqual(d["sequencer"]["blocking_count_total"], 0)
        self.assertGreater(d["responses_2xx"], 0)
        self.assertLess(d["execution_duration_s"], 5)  # the measure phase ended by the SIGTERM, not its cap


class TrafficWindowTest(unittest.TestCase):
    def test_http(self):
        q0 = {"http.ingress_http.downstream_cx_rx_bytes_total": 1000, "http.ingress_http.downstream_cx_tx_bytes_total":
              5000, "listener.127.0.0.1_10110.downstream_cx_total": 512, "listener.admin.downstream_cx_total": 9,
              "cluster.origin.upstream_cx_tx_bytes_total": 700, "cluster.origin.upstream_cx_rx_bytes_total": 4000}
        q1 = {k: v for k, v in q0.items()}
        q1.update({"http.ingress_http.downstream_cx_rx_bytes_total": 1000 + 104000 * 80,
                   "http.ingress_http.downstream_cx_tx_bytes_total": 5000 + 104000 * 4300,
                   "listener.127.0.0.1_10110.downstream_cx_total": 514, "listener.admin.downstream_cx_total": 15,
                   "cluster.origin.upstream_cx_tx_bytes_total": 700 + 104000 * 164})
        t = leg.traffic_window(q0, q1)
        self.assertEqual(t["client_to_envoy_bytes"], 104000 * 80)
        self.assertEqual(t["envoy_to_client_bytes"], 104000 * 4300)
        self.assertEqual(t["listener_cx_total"], 2)  # the admin listener is not counted
        self.assertEqual(t["upstream_tx_bytes"], 104000 * 164)
        self.assertEqual(t["upstream_rx_bytes"], 0)
        self.assertEqual(t["source"], "downstream")

    def test_tcp_proxy_and_missing(self):
        q0 = {"tcp.relay.downstream_cx_rx_bytes_total": 10, "listener.127.0.0.1_10110.downstream_cx_total": 16}
        q1 = {"tcp.relay.downstream_cx_rx_bytes_total": 110, "listener.127.0.0.1_10110.downstream_cx_total": 32}
        t = leg.traffic_window(q0, q1)
        self.assertEqual((t["client_to_envoy_bytes"], t["listener_cx_total"]), (100, 16))
        self.assertIsNone(t["envoy_to_client_bytes"])
        self.assertIsNone(t["upstream_tx_bytes"])
        # nothing recorded: None (never 0), no source
        e = leg.traffic_window({}, {})
        self.assertEqual(e, {"client_to_envoy_bytes": None, "envoy_to_client_bytes": None, "listener_cx_total": None,
                             "upstream_tx_bytes": None, "upstream_rx_bytes": None, "source": None})
        # only the upstream bytes: the backup source
        b = leg.traffic_window({"cluster.origin.upstream_cx_tx_bytes_total": 1},
                               {"cluster.origin.upstream_cx_tx_bytes_total": 9})
        self.assertEqual((b["upstream_tx_bytes"], b["source"]), (8, "upstream (backup)"))

    def test_filter_and_leg(self):
        import inspect
        import re
        f = re.compile(leg.STAT_FILTER)
        for k in ("http.ingress_http.downstream_cx_rx_bytes_total", "tcp.relay.downstream_cx_rx_bytes_total",
                  "tcp.relay.downstream_cx_tx_bytes_total", "listener.127.0.0.1_10110.downstream_cx_total",
                  "cluster.origin.upstream_cx_tx_bytes_total"):
            self.assertTrue(f.search(k), k)
        src = inspect.getsource(leg.RealBackend.run_leg)
        self.assertIn('m["traffic_window"] = traffic_window(q0, q1)', src)
        # bytes per in-window 2xx, and connections over the leg (Envoy is new per leg)
        self.assertIn('m["traffic_window"][k + "_per_request"]', src)
        self.assertIn('m["traffic_leg"] = traffic_window({k: 0 for k in q1}, q1)', src)
        self.assertIn('m["traffic_leg"]["client_cx_total"] = nhp["cx_total"]', src)

    def test_per_worker_listener_keys_not_counted(self):
        # Envoy's per-handler copies count every connection a second time
        q1 = {"listener.127.0.0.1_10110.downstream_cx_total": 512, "http.ingress_http.downstream_cx_rx_bytes_total": 9}
        for w in range(4):
            q1["listener.127.0.0.1_10110.worker_%d.downstream_cx_total" % w] = 128
        t = leg.traffic_window({k: 0 for k in q1}, q1)
        self.assertEqual((t["listener_cx_total"], t["client_to_envoy_bytes"]), (512, 9))


# ---------------------------------------------------------------- phase resets

class PhaseResetsTest(unittest.TestCase):
    """The measure-phase count is labelled, and both phases' resets are recorded."""

    def test(self):
        tmp = tempfile.mkdtemp()
        d = nighthawk.parse_output(write(tmp, phase_json(md_over={"warm": {"reset_or_timed_out": "3"}})),
                                   measure_phase="measure")
        self.assertEqual(d["measure_completed"], d["responses_2xx"])
        self.assertIn("every status", d["responses_basis"])
        vec = nighthawk.phase_vector(400, 2, 5, 60)
        mono = 1005.7 - nighthawk.parse_timestamp("2026-11-26T10:00:05.7Z")
        r = nighthawk.phase_check(d, vec, 2, d["worker_exec"], mono, 1008.0, 1.5, 8)
        self.assertEqual(r["reset_or_timed_out"], {"warm": 3, "measure": 0})
        self.assertTrue(r["ok"])  # recorded, not gated
        self.assertNotIn("measure_completed", nighthawk.parse_output(write(tmp, phase_json())))


if __name__ == "__main__":
    unittest.main()
