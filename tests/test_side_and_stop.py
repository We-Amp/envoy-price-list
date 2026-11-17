import json
import os
import tempfile
import unittest

from epl import envoy_config, experiment, leg, origin, sideservice, sysprobe, validity
from epl.sim import SimBackend

from .test_evidence import good
from .test_experiment import cfg, load, three_arms


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class FakeHost:
    """A cgroup v2 tree and /proc for one container: main pid 500, workers 501, 502."""

    def __init__(self, cpus="32-39,72-79", worker_cpus=None):
        self.root = tempfile.mkdtemp()
        self.cg = os.path.join(self.root, "cg")
        self.proc = os.path.join(self.root, "proc")
        d = os.path.join(self.cg, "system.slice", "docker-abc.scope")
        write(os.path.join(d, "cpu.stat"), "usage_usec 1000000\nuser_usec 600000\nsystem_usec 400000\n")
        write(os.path.join(d, "cpuset.cpus.effective"), cpus + "\n")
        write(os.path.join(d, "cgroup.procs"), "500\n501\n502\n")
        self.dir = d
        for p in (500, 501, 502):
            write(os.path.join(self.proc, str(p), "cgroup"), "0::/system.slice/docker-abc.scope\n")
            write(os.path.join(self.proc, str(p), "status"),
                  "Name:\tnginx\nCpus_allowed_list:\t%s\n" % ((worker_cpus or {}).get(p, cpus)))

    def usage(self, us):
        write(os.path.join(self.dir, "cpu.stat"), "usage_usec %d\n" % us)

    def svc(self, want="32-39,72-79"):
        return sideservice.SideService("origin", 500, want, root=self.cg, proc=self.proc)


class SideServiceTest(unittest.TestCase):
    def test_parse_proc_cgroup(self):
        self.assertEqual(sideservice.parse_proc_cgroup("0::/system.slice/docker-x.scope\n"),
                         {"": "/system.slice/docker-x.scope"})
        m = sideservice.parse_proc_cgroup("12:cpuset:/docker/x\n4:cpu,cpuacct:/docker/x\n0::/\n")
        self.assertEqual(m["cpuset"], "/docker/x")
        self.assertEqual(m["cpuacct"], "/docker/x")

    def test_placement_and_usage(self):
        h = FakeHost()
        s = h.svc()
        pl = s.placement()
        self.assertTrue(pl["cpuset_ok"] and pl["pids_ok"], pl)
        self.assertEqual(pl["pids"], 3)
        self.assertEqual(s.usage_us(), 1000000)
        h.usage(5000000)  # 4 CPU-seconds over a 20 s window on 16 CPUs: 1.25% of the set
        r = sideservice.window_record(s, 1000000, s.usage_us(), 20.0, 104000)
        self.assertAlmostEqual(r["busy_of_set"], 4.0 / 20 / 16, places=5)
        self.assertAlmostEqual(r["cpu_us_per_request"], 4e6 / 104000, places=2)
        self.assertIn("error", sideservice.window_record(s, None, 1, 20.0, 1))

    def test_placement_off_set(self):
        s = FakeHost(worker_cpus={502: "0-79"}).svc()
        pl = s.placement()
        self.assertFalse(pl["pids_ok"])
        self.assertEqual(pl["bad_pids"][0]["pid"], 502)
        s = FakeHost(cpus="0-79").svc()
        self.assertFalse(s.placement()["cpuset_ok"])

    def test_gate(self):
        ok = {"busy_of_set": 0.02, "cpuset_ok": True, "pids_ok": True}
        m = dict(good(), side_services={"origin": dict(ok), "collector": dict(ok)})
        self.assertTrue(validity.verdict(m)["valid"])
        for bad, needle in ((dict(ok, busy_of_set=0.51), "CPU set in the window"),
                            (dict(ok, cpuset_ok=False), "container cpuset"),
                            (dict(ok, pids_ok=False), "processes off"),
                            ({"error": "cgroup not readable"}, "cgroup not readable"),
                            ({"cpuset_ok": True, "pids_ok": True}, "no CPU time")):
            m = dict(good(), side_services={"origin": dict(ok), "collector": bad})
            v = validity.verdict(m)
            self.assertFalse(v["valid"], needle)
            self.assertTrue(any(needle in r for r in v["reasons"]), v["reasons"])
        m = dict(good(), side_services={"origin": dict(ok, busy_of_set=0.9)})
        self.assertTrue(validity.verdict(m, {"max_side_service_busy": None})["valid"])


class CollectorTest(unittest.TestCase):
    def test_level_none_config_is_unchanged(self):
        # the config row 4 ran with, byte for byte
        old = ("receivers:\n  otlp:\n    protocols:\n      grpc:\n        endpoint: 127.0.0.1:4317\nexporters:\n"
               "  nop:\nservice:\n  telemetry:\n    metrics:\n      level: none\n  pipelines:\n    traces:\n"
               "      receivers: [otlp]\n      exporters: [nop]\n")
        self.assertEqual(origin.collector_conf(4317), old)
        basic = origin.collector_conf(4317, 8888)
        self.assertIn("level: basic", basic)
        self.assertIn("host: 127.0.0.1", basic)
        self.assertIn("port: 8888", basic)

    def test_parse_metrics(self):
        txt = ("# HELP otelcol_receiver_accepted_spans x\n# TYPE otelcol_receiver_accepted_spans counter\n"
               'otelcol_receiver_accepted_spans{receiver="otlp",service_name="otelcol",transport="grpc"} 1530\n'
               'otelcol_receiver_refused_spans_total{receiver="otlp",transport="grpc"} 0\n'
               'otelcol_exporter_sent_spans{exporter="nop"} 1530\n')
        self.assertEqual(origin.parse_collector_metrics(txt), {"accepted_spans": 1530, "refused_spans": 0})
        self.assertEqual(origin.parse_collector_metrics(""), {})


class LegHelpersTest(unittest.TestCase):
    def test_stat_window_keeps_zeros(self):
        q0 = {"a": 5, "b": 1}
        q1 = {"a": 5, "b": 4, "c": 2}
        self.assertEqual(leg._stat_window(q0, q1), {"a": 0, "b": 3, "c": 2})

    def test_new_stats_in_filter(self):
        import re
        f = re.compile(leg.STAT_FILTER)
        for k in ("filesystem.write_failed", "filesystem.reopen_failed", "http.ingress_http.downstream_rq_completed",
                  "http.ingress_http.downstream_cx_idle_timeout", "cluster.origin.upstream_cx_tx_bytes_total",
                  "http.ingress_http.downstream_cx_tx_bytes_total", "tracing.opentelemetry.spans_sent",
                  "cluster.otel_collector.upstream_rq_timeout"):
            self.assertTrue(f.search(k), k)
        for k in ("filesystem.write_failed", "http.ingress_http.downstream_rq_completed",
                  "cluster.origin.upstream_cx_tx_bytes_total"):
            self.assertTrue(leg.DELTA_KEYS_RE.search(k), k)

    def test_json_lines_check(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "a.alog")
        with open(p, "w") as f:
            for i in range(500):
                f.write(json.dumps({"i": i, "path": "/s"}) + "\n")
        r = leg.json_lines_check(p)
        self.assertEqual(r, {"checked": 200, "bad": 0})
        small = os.path.join(d, "b.alog")
        with open(small, "w") as f:
            for i in range(50):
                f.write(json.dumps({"i": i}) + "\n")
        self.assertEqual(leg.json_lines_check(small), {"checked": 50, "bad": 0})
        big = os.path.join(d, "c.alog")
        with open(big, "w") as f:
            for i in range(5000):
                f.write(json.dumps({"i": i, "pad": "x" * 200}) + "\n")
        self.assertEqual(leg.json_lines_check(big), {"checked": 200, "bad": 0})
        with open(p, "a") as f:
            f.write("[2026-11-17T00:00:00.000Z] \"GET /s HTTP/1.1\" 200\n")
        r = leg.json_lines_check(p)
        self.assertEqual(r["bad"], 1)

    def test_fs_of(self):
        mi = ("22 1 8:2 / / rw,relatime shared:1 - ext4 /dev/sda2 rw\n"
              "30 22 0:26 / /run rw shared:5 - tmpfs tmpfs rw\n"
              "40 22 8:17 / /home/u/epl rw shared:9 - xfs /dev/sdb1 rw\n")
        d = tempfile.mkdtemp()
        p = os.path.join(d, "mountinfo")
        with open(p, "w") as f:
            f.write(mi)
        self.assertEqual(sysprobe.parse_mountinfo(mi)[2], ("/home/u/epl", "xfs", "/dev/sdb1", "8:17"))
        r = sysprobe.fs_of("/run/x", p)
        self.assertEqual((r["fstype"], r["mount_point"]), ("tmpfs", "/run"))
        self.assertEqual(sysprobe.fs_of("/home/u/eplx", p)["fstype"], "ext4")


S = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 1600},
     {"name": "fh", "path": "/fh", "kind": "direct_headers", "body_bytes": 128, "request_headers_added": 57,
      "response_headers_added": 52, "rps": 1600}]
E = {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True}


def hcm(b):
    return b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]


class SettingsTest(unittest.TestCase):
    def test_idle_timers_off(self):
        h = hcm(envoy_config.bootstrap(S, dict(E, idle_timers_off=True), 8092))
        self.assertEqual(h["stream_idle_timeout"], "0s")
        self.assertEqual(h["common_http_protocol_options"], {"idle_timeout": "0s"})
        h0 = hcm(envoy_config.bootstrap(S, E, 8092))
        self.assertNotIn("stream_idle_timeout", h0)
        self.assertNotIn("common_http_protocol_options", h0)
        h = hcm(envoy_config.bootstrap(S, dict(E, idle_timers_off=True, downstream_keepalive={"max_requests": 9}),
                                       8092))
        self.assertEqual(h["common_http_protocol_options"], {"max_requests_per_connection": 9, "idle_timeout": "0s"})
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S, dict(E, idle_timers_off=True, downstream_keepalive={"idle_timeout_s": 5}), 8092)
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S, dict(E, idle_timers_off="yes"), 8092)

    def test_tracing_on_direct_response_shape(self):
        b = envoy_config.bootstrap(S[1:], dict(E, tracing={"sampling_pct": 1}, collector_port=4317), 8092)
        h = hcm(b)
        self.assertEqual(h["tracing"]["random_sampling"], {"value": 1.0})
        self.assertIn("direct_response", h["route_config"]["virtual_hosts"][0]["routes"][0])
        # the collector is the only cluster that is used: the direct response has no upstream
        self.assertIn("otel_collector", [c["name"] for c in b["static_resources"]["clusters"]])


class StopRuleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def analysis(self, hws):
        """A fake analysis: {shape: [(arm, ref, half-width)]}, rows in confirmatory."""
        sh = {}
        for s, rows in hws.items():
            sh[s] = {"comparisons": [], "confirmatory": [
                {"arm": a, "ref": r, "cycles_total": {"n": 20, "paired": {"half_width_pct": hw}}}
                for a, r, hw in rows]}
        return {"shapes": sh}

    def test_per_shape_target(self):
        c = cfg(stop={"target_half_width_pct": 0.8, "rows": "confirmatory"}, confirmatory=[["b", "a"]])
        c["shapes"][1]["stop_target_half_width_pct"] = 1.5
        exp = load(c, self.tmp)
        self.assertEqual(experiment.validate(exp), [])
        stop, why = experiment.stop_check(exp, self.analysis({"s": [("b", "a", 0.7)], "fh": [("b", "a", 1.4)]}))
        self.assertTrue(stop, why)
        stop, why = experiment.stop_check(exp, self.analysis({"s": [("b", "a", 0.9)], "fh": [("b", "a", 1.0)]}))
        self.assertFalse(stop)
        self.assertIn("s b vs a", why)
        stop, why = experiment.stop_check(exp, self.analysis({"s": [("b", "a", 0.5)], "fh": [("b", "a", 1.6)]}))
        self.assertFalse(stop)
        self.assertIn("fh b vs a", why)
        # without shape targets: one target for all, as before
        exp = load(cfg(stop={"target_half_width_pct": 1.5}), self.tmp)
        an = {"shapes": {"s": {"comparisons": [{"arm": "b", "ref": "a", "cycles_total": {
            "n": 12, "paired": {"half_width_pct": 1.4}}}]}}}
        self.assertTrue(experiment.stop_check(exp, an)[0])

    def test_confirmatory_shapes(self):
        c = three_arms(confirmatory=[["y", "x", "s"], ["z", "x", ["s", "fh"]]], comparisons="base")
        exp = load(c, self.tmp)
        self.assertEqual(experiment.validate(exp), [])
        bad = load(three_arms(confirmatory=[["y", "x", "nope"]]), self.tmp)
        self.assertTrue(any("confirmatory" in e for e in experiment.validate(bad)))
        bad = load(cfg(shapes=[dict(cfg()["shapes"][0], stop_target_half_width_pct=-1)]), self.tmp)
        self.assertTrue(any("stop_target" in e for e in experiment.validate(bad)))
        legs = []
        be = SimBackend(exp, self.tmp, lambda m: None)
        for r, sh, a in experiment.schedule(exp, 1, 12):
            legs.append(be.run_leg(a, sh, r, None, experiment.leg_id(r, sh, a)))
        an = experiment.analyse(exp, legs)
        self.assertEqual([(c["arm"], c["ref"]) for c in an["shapes"]["s"]["confirmatory"]], [("y", "x"), ("z", "x")])
        self.assertEqual([(c["arm"], c["ref"]) for c in an["shapes"]["fh"]["confirmatory"]], [("z", "x")])
        self.assertEqual(an["confirmatory_family_size"], 3)

    def test_complete_rounds(self):
        exp = load(three_arms(), self.tmp)  # rotate, period 6
        legs = []
        be = SimBackend(exp, self.tmp, lambda m: None)
        for r, sh, a in experiment.schedule(exp, 1, 14):
            legs.append(be.run_leg(a, sh, r, None, experiment.leg_id(r, sh, a)))
        self.assertEqual(experiment.complete_rounds(exp, legs), 12)
        self.assertEqual(experiment.complete_rounds(exp, legs[:-1][:6 * 6 - 1]), 0)
        # a superseded leg without its re-run leaves a hole
        legs2 = [dict(m) for m in legs]
        legs2[0]["superseded"] = True
        self.assertEqual(experiment.complete_rounds(exp, legs2), 0)


class Stopper(SimBackend):
    """Raises SystemExit (as the SIGTERM handler does) when leg number `at` starts."""
    at = None

    def run_leg(self, arm, shape, rnd, bootstrap_path, leg_id):
        self.n = getattr(self, "n", 0) + 1
        if self.n == self.at:
            raise SystemExit("terminated by signal 15")
        return SimBackend.run_leg(self, arm, shape, rnd, bootstrap_path, leg_id)


class IncompleteRunTest(unittest.TestCase):
    def run_until(self, c, at):
        tmp = tempfile.mkdtemp()
        exp = load(c, tmp)
        self.assertEqual(experiment.validate(exp), [])
        Stopper.at = at
        r = experiment.Runner(exp, os.path.join(tmp, "run"), Stopper)
        with self.assertRaises(RuntimeError):
            r.run(simulate=True)
        with open(os.path.join(tmp, "run", "results.json")) as f:
            return json.load(f)

    def test_stopped_before_minimum(self):
        # 3 arms x 2 shapes x 12 rounds minimum; stop in round 8
        res = self.run_until(three_arms(rounds=12, rounds_block=6, rounds_max=24), 8 * 6 - 2)
        md = res["metadata"]
        self.assertTrue(md["incomplete"])
        self.assertEqual(md["rounds_complete"], 6)
        self.assertIn("SystemExit", md["aborted"])
        an = res["analysis"]
        self.assertTrue(an["incomplete"])
        st = {c["cycles_total"]["status"] for s in an["shapes"].values() for c in s["comparisons"]}
        self.assertEqual(st, {experiment.INCOMPLETE})
        self.assertNotIn("aa_selftest", res)
        self.assertLessEqual(max(r for c in an["shapes"]["s"]["comparisons"] for r in c["rounds_paired"]), 6)

    def test_stopped_inside_a_later_block(self):
        # minimum 12 done, stop inside the block 13..18 before the stop target: analysed on the
        # 12 complete rounds, but incomplete (the stop rule was never met), so no verdicts
        c = three_arms(rounds=12, rounds_block=6, rounds_max=24, stop={"target_half_width_pct": 0.01})
        res = self.run_until(c, 14 * 6 - 3)
        md = res["metadata"]
        self.assertTrue(md["incomplete"])
        self.assertIn("stopped before its stop rule", md["stopped_early"])
        self.assertEqual(md["rounds_complete"], 12)
        self.assertGreater(md["legs_after_last_complete_block"], 0)
        an = res["analysis"]
        self.assertTrue(an["incomplete"])
        self.assertEqual(max(r for c in an["shapes"]["s"]["comparisons"] for r in c["rounds_paired"]), 12)

    def test_complete_rounds_and_invalid_legs(self):
        exp = load(three_arms(), tempfile.mkdtemp())
        legs = []
        be = SimBackend(exp, tempfile.mkdtemp(), lambda m: None)
        for r, sh, a in experiment.schedule(exp, 1, 12):
            legs.append(be.run_leg(a, sh, r, None, experiment.leg_id(r, sh, a)))
        self.assertEqual(experiment.complete_rounds(exp, legs), 12)
        # an invalid leg of round 8 still waiting for its re-run: block 7..12 is not complete
        bad = [m for m in legs if m["round"] == 8][0]
        bad["verdict"] = {"valid": False, "reasons": ["x"]}
        self.assertEqual(experiment.complete_rounds(exp, legs), 6)
        # after its re-run (still invalid) the method drops the pair; the block is complete
        bad["superseded"] = True
        legs.append(dict(bad, superseded=False, attempt=1, leg_id=bad["leg_id"] + ".rr1"))
        self.assertEqual(experiment.complete_rounds(exp, legs), 12)

    def test_evidence_fault_invalidates(self):
        tmp = tempfile.mkdtemp()
        c = cfg(sim_faults={"r01-s-b": "evidence"})
        c["arms"][1]["evidence"] = [{"stat": "x", "min": 1}]
        exp = load(c, tmp)
        res = experiment.Runner(exp, os.path.join(tmp, "run"), SimBackend).run(simulate=True)
        bad = [m for m in res["legs"] if not m["verdict"]["valid"]]
        self.assertEqual([m["leg_id"] for m in bad], ["r01-s-b"])
        self.assertTrue(any("evidence" in r for r in bad[0]["verdict"]["reasons"]))


if __name__ == "__main__":
    unittest.main()
