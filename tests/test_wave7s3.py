"""Wave 7 S3: the inert filter chain, the route timeout, and the S3 configs."""
import gzip
import importlib.util
import json
import os
import re
import tempfile
import unittest

from epl import envoy_config as ec
from epl import evidence, experiment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S3 = os.path.join(ROOT, "examples", "wave7s3")
CFG = os.path.join(S3, "configs")
ENV = {"listener_port": 10110, "admin_port": 9921}
S = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200}]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mk = _load("w7s3_make_t", os.path.join(S3, "make.py"))
chk = _load("w7s3_check_t", os.path.join(S3, "s3_check.py"))
tbl = _load("w7s3_table_t", os.path.join(S3, "table.py"))


def hcm_of(b):
    return b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]


class Settings(unittest.TestCase):
    def test_inert_filters_sit_before_the_router(self):
        h = hcm_of(ec.bootstrap(S, dict(ENV, inert_filters=True), 8092))
        names = [f["name"] for f in h["http_filters"]]
        self.assertEqual(len(names), 11)
        self.assertEqual(names[-1], "envoy.filters.http.router")
        self.assertEqual(names[:-1], [n for n, _ in ec.INERT_FILTERS])
        self.assertFalse(any("disabled" in f for f in h["http_filters"]))
        # the fields validation requires
        by = {f["name"].rsplit(".", 1)[-1]: f["typed_config"] for f in h["http_filters"]}
        self.assertIs(by["health_check"]["pass_through_mode"], False)
        self.assertEqual(by["csrf"]["filter_enabled"]["default_value"]["numerator"], 0)
        self.assertEqual(by["bandwidth_limit"]["enable_mode"], "DISABLED")
        self.assertTrue(by["bandwidth_limit"]["stat_prefix"])
        # the tenth is not kill_request: that filter is not in the official binary
        self.assertNotIn("kill_request", by)

    def test_inert_filters_disabled(self):
        h = hcm_of(ec.bootstrap(S, dict(ENV, inert_filters={"disabled": True}), 8092))
        self.assertEqual([f.get("disabled") for f in h["http_filters"]], [True] * 10 + [None])
        for bad in ({"disabled": False}, {"x": 1}, "yes"):
            with self.assertRaises(ValueError):
                ec.bootstrap(S, dict(ENV, inert_filters=bad), 8092)
        with self.assertRaises(ValueError):
            ec.bootstrap(S, dict(ENV, inert_filters=True, tcp_proxy=True), 8092)

    def test_inert_filters_follow_the_feature_filters(self):
        e = experiment.load(os.path.join(CFG, "s3a-stack.json"))
        arms = {a["name"]: a for a in e["arms"]}
        env = dict(experiment.arm_envoy(e, arms["typical"], "/r"), inert_filters=True)
        names = [f["name"].rsplit(".", 1)[-1] for f in hcm_of(ec.bootstrap(e["shapes"], env, 8092))["http_filters"]]
        self.assertEqual(names[:3], ["jwt_authn", "local_ratelimit", "compressor"])
        self.assertEqual(names[-1], "router")

    def test_route_timeout(self):
        fh = {"name": "fh", "path": "/fh", "kind": "direct_headers", "body_bytes": 128, "rps": 8000}
        rts = hcm_of(ec.bootstrap(S + [fh], dict(ENV, route_timeout_s=0), 8092))["route_config"]["virtual_hosts"][0]["routes"]
        self.assertEqual(rts[0]["route"]["timeout"], "0s")
        self.assertNotIn("route", rts[1])  # a direct response has no route timeout
        self.assertNotIn("timeout", json.dumps(hcm_of(ec.bootstrap(S, dict(ENV), 8092))["route_config"]))


class Configs(unittest.TestCase):
    def test_arms_rounds_and_rates(self):
        legs = {}
        for fn in sorted(os.listdir(CFG)):
            e = experiment.load(os.path.join(CFG, fn))
            self.assertEqual(experiment.validate(e, allow_short=True), [], fn)
            legs[fn[:-5]] = len(experiment.cells(e)) * e["rounds"]
            self.assertEqual(e["idle"]["procs"], [], fn)
            for a in e["arms"]:
                self.assertEqual(a["source_sha256"], "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc", fn)
                self.assertTrue(a["binary"].endswith("/epl/bin/envoy-1.40.2"), fn)
        self.assertEqual([legs[k] for k in ("s3a-stack", "s3b-chain", "smoke-s3a-stack", "smoke-s3b-chain")], [36, 72, 6, 12])
        self.assertEqual([legs[k] for k in ("smoke-mech-sys", "smoke-mech-kcg", "mech-sys-stack", "mech-kcg-stack",
                                            "mech-kcg-chain")], [2, 2, 2, 2, 4])
        a = experiment.load(os.path.join(CFG, "s3a-stack.json"))
        b = experiment.load(os.path.join(CFG, "s3b-chain.json"))
        self.assertEqual((a["order"], a["order_seed"], a["rounds"], a["base_arm"]), ("williams", 721, 6, "bare"))
        self.assertEqual((b["order"], b["order_seed"], b["rounds"], b["base_arm"]), ("williams", 722, 6, "f0"))
        self.assertEqual({s["name"]: s["rps"] for s in a["shapes"]}, {"sx": 5200})
        self.assertEqual({s["name"]: s["rps"] for s in b["shapes"]}, {"s": 5200, "fh": 8000})
        self.assertEqual([x["name"] for x in a["arms"]], ["bare", "bare-A2", "typical", "typical-A2", "typical-nosink", "lean"])
        self.assertEqual([x["name"] for x in b["arms"]], ["f0", "f0-A2", "f10", "f10-off", "idle-off", "timers-off-all"])
        self.assertEqual(len(a["confirmatory"]), 4)
        self.assertEqual(len(b["confirmatory"]), 4)  # per shape: Holm over 8

    def test_the_stack_is_the_plan_and_no_arm_has_generated_clusters(self):
        e = experiment.load(os.path.join(CFG, "s3a-stack.json"))
        arms = {a["name"]: a.get("settings") or {} for a in e["arms"]}
        self.assertEqual(arms["bare"], {})
        self.assertEqual(arms["bare-A2"], {})
        t = arms["typical"]
        self.assertEqual(t, arms["typical-A2"])
        self.assertEqual(sorted(t), ["access_log", "compressor", "jwt_authn", "local_ratelimit", "retries", "stats_sink", "tracing"])
        self.assertEqual((t["access_log"], t["tracing"], t["stats_sink"], t["compressor"], t["retries"]),
                         ({"format": "json"}, {"sampling_pct": 1}, {"kind": "statsd"}, {"library": "gzip"}, True))
        self.assertIs(t["jwt_authn"]["cache"], True)
        self.assertEqual({k: v for k, v in t.items() if k != "stats_sink"}, arms["typical-nosink"])
        lean = arms["lean"]
        self.assertEqual(lean["access_log"], {"format": "text"})
        self.assertEqual(lean["stats_sink"], {"kind": "otlp"})
        self.assertEqual({k: v for k, v in lean.items() if k not in ("access_log", "stats_sink")},
                         {k: v for k, v in t.items() if k not in ("access_log", "stats_sink")})
        for a in e["arms"]:
            self.assertNotIn("stats_clusters", a.get("settings") or {})
            self.assertNotIn("stats_flush", a.get("settings") or {})  # Envoy's default 5 s in every arm
        # every arm's client sends the two request headers
        args = e["shapes"][0]["client_extra_args"]
        self.assertEqual([args[i + 1].split(":")[0] for i in range(0, len(args), 2)], ["accept-encoding", "authorization"])
        self.assertEqual(e["shapes"][0]["path"], "/s")
        self.assertTrue(e["collector"]["metrics"] and e["collector"]["metrics_port"])

    def test_statsd_band_and_predictions_are_the_plan(self):
        e = experiment.load(os.path.join(CFG, "s3a-stack.json"))
        ev = {a["name"]: a["evidence"] for a in e["arms"]}
        dg = [it for it in ev["typical"] if it["stat"] == "udp.datagrams_per_request"]
        self.assertEqual([(it["min"], it["max"]) for it in dg], [(2.5, 3.5)])
        self.assertEqual(ev["typical"], ev["typical-A2"])
        for a in ("bare", "bare-A2", "typical-nosink", "lean"):
            self.assertFalse([it for it in ev[a] if it["stat"].startswith("udp.")], a)
            self.assertTrue([it for it in ev[a] if it["stat"] == "kernel_net.d.UdpOutDatagrams" and it["max"] == 0.01], a)
        self.assertEqual(chk.BAND, (2.5, 3.5))
        self.assertEqual(chk.STAT_LIMIT, 2000)
        self.assertEqual(tbl.PREDICTED, {"typical": 40.5, "typical-nosink": 24.5, "lean": 23.6})
        self.assertEqual(tbl.BAND, 3.0)
        # the plan's sums: 4.5 + 7.0 + 16.0 + 5.3 + 4.3 + 1.9 + 1.5, without the sink, and lean
        self.assertAlmostEqual(4.5 + 7.0 + 16.0 + 5.3 + 4.3 + 1.9 + 1.5, 40.5)
        self.assertAlmostEqual(4.5 + 7.0 + 5.3 + 4.3 + 1.9 + 1.5, 24.5)
        self.assertAlmostEqual(3.6 + 7.0 + 5.3 + 4.3 + 1.9 + 1.5, 23.6)

    def test_config_evidence_tells_the_arms_apart(self):
        for fn, pairs in (("s3b-chain.json", [("f0", "f10"), ("f10", "f0"), ("f10", "f10-off"), ("f10-off", "f10"),
                                               ("idle-off", "f0"), ("f0", "idle-off"), ("idle-off", "timers-off-all"),
                                               ("timers-off-all", "idle-off")]),
                          ("s3a-stack.json", [("bare", "typical"), ("typical", "bare"), ("typical", "typical-nosink"),
                                              ("typical-nosink", "typical"), ("lean", "typical"), ("typical", "lean"),
                                              ("lean", "typical-nosink"), ("typical-nosink", "lean")])):
            e = experiment.load(os.path.join(CFG, fn))
            arms = {a["name"]: a for a in e["arms"]}
            # the static part of /config_dump is the bootstrap; the dump's list of every extension by name is
            # stood in for by a node section that names every inert filter
            node = {"node": {"extensions": [{"name": n, "category": "envoy.filters.http"} for n, _ in ec.INERT_FILTERS]}}
            boot = {n: dict(json.loads(ec.bootstrap_text(e["shapes"], experiment.arm_envoy(e, a, "/r"), 8092)), **node)
                    for n, a in arms.items()}
            for mine, other in pairs:
                items = [it for it in arms[mine]["evidence"] if it.get("scope") == "config"]
                self.assertTrue(items, mine)
                bad = [it["label"] for it in items if not evidence.check_item({}, it, boot[mine])["ok"]]
                self.assertEqual(bad, [], "%s on its own bootstrap" % mine)
                self.assertFalse(all(evidence.check_item({}, it, boot[other])["ok"] for it in items), "%s on %s" % (mine, other))

    def test_timer_arms(self):
        e = experiment.load(os.path.join(CFG, "s3b-chain.json"))
        arms = {a["name"]: a for a in e["arms"]}
        b = {n: json.loads(ec.bootstrap_text(e["shapes"], experiment.arm_envoy(e, arms[n]), 8092))
             for n in ("f0", "idle-off", "timers-off-all")}
        for n in ("idle-off", "timers-off-all"):
            h = hcm_of(b[n])
            self.assertEqual(h["stream_idle_timeout"], "0s")
            self.assertEqual(h["common_http_protocol_options"], {"idle_timeout": "0s"})
            opts = b[n]["static_resources"]["clusters"][0]["typed_extension_protocol_options"][
                "envoy.extensions.upstreams.http.v3.HttpProtocolOptions"]
            self.assertEqual(opts["common_http_protocol_options"], {"idle_timeout": "0s"})
        self.assertNotIn('"timeout"', json.dumps(hcm_of(b["idle-off"])["route_config"]))
        self.assertEqual(json.dumps(hcm_of(b["timers-off-all"])["route_config"]).count('"timeout": "0s"'), 1)
        self.assertNotIn("idle_timeout", json.dumps(b["f0"]))

    def test_everything_binds_to_loopback(self):
        for fn in sorted(os.listdir(CFG)):
            e = experiment.load(os.path.join(CFG, fn))
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                _, texts, _ = experiment.prepare_bootstraps(e, d, make_certs=False)
            addrs = []

            def walk(x):
                if isinstance(x, dict):
                    if "address" in x and "port_value" in x:
                        addrs.append(str(x["address"]))
                    self.assertNotIn("pipe", x, fn)
                    for v in x.values():
                        walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
            for t in texts.values():
                walk(json.loads(t))
            self.assertTrue(addrs, fn)
            self.assertEqual([a for a in addrs if not a.startswith("127.")], [], fn)
            conf = ec.nginx_conf(e["origin"]["port"], 8, stub_status=True)
            self.assertEqual([x for x in re.findall(r"listen ([^ ;]+)", conf) if not x.startswith("127.")], [], fn)

    def test_mech_configs_use_the_wrappers_and_are_not_scored(self):
        for fn in sorted(os.listdir(CFG)):
            if "mech" not in fn:
                continue
            e = json.load(open(os.path.join(CFG, fn)))
            self.assertTrue(e["smoke"] and e["rounds"] == 1 and e["evidence_mode"] == "record", fn)
            self.assertRegex(e["measure"]["perf"], r"^bash ~/epl/harness-wave7s3/examples/wave7s3/perf-(sys|kcg)\.sh$", fn)
            self.assertEqual(("kcg" in fn), e["measure"]["perf"].endswith("perf-kcg.sh"), fn)
            self.assertNotIn("confirmatory", e, fn)
            for sh in e["shapes"]:
                self.assertGreaterEqual(len(e["arms"]), 2, fn)
        for fn in ("chain-s3.sh", "run-s3.sh", "box-start.sh", "mech-inner.sh", "mech-post.sh", "perf-sys.sh", "perf-kcg.sh"):
            with open(os.path.join(S3, fn)) as f:
                txt = f.read()
            self.assertNotIn("wave7s2", txt, fn)
            self.assertNotIn("pkill", txt, fn)
            self.assertNotIn("killall", txt, fn)
            self.assertNotIn("pgrep", txt, fn)


class Check(unittest.TestCase):
    def smoke(self, d, legs, arms, stats):
        with open(os.path.join(d, "legs.jsonl"), "w") as f:
            for m in legs:
                f.write(json.dumps(m) + "\n")
        with open(os.path.join(d, "experiment.json"), "w") as f:
            json.dump({"arms": arms}, f)
        os.makedirs(os.path.join(d, "stats"))
        for a, n in stats.items():
            with gzip.open(os.path.join(d, "stats", a + ".txt.gz"), "wt") as f:
                f.write("".join("s%d: 1\n" % i for i in range(n)))

    def leg(self, arm, dg=None):
        m = {"leg_id": "sx-" + arm, "shape": "sx", "arm": arm, "responses_raw": 100000,
             "verdict": {"valid": True}, "evidence": {"ok": True}}
        if dg is not None:
            m["udp"] = {"datagrams_per_request": dg}
        return m

    def run_check(self, legs, stats, sink=("typical",)):
        arms = [{"name": a, "settings": {"stats_sink": {"kind": "statsd"}} if a in sink else {}} for a in stats]
        with tempfile.TemporaryDirectory(dir="/tmp") as d:
            self.smoke(d, legs, arms, stats)
            return chk.check(d)[1]

    def test_state_rules(self):
        ok = self.run_check([self.leg("bare"), self.leg("typical", 3.01)], {"bare": 400, "typical": 580})
        self.assertEqual(ok, [])
        self.assertTrue(self.run_check([self.leg("bare"), self.leg("typical", 4.21)], {"bare": 400, "typical": 580}))
        self.assertTrue(self.run_check([self.leg("bare"), self.leg("typical")], {"bare": 400, "typical": 580}))
        self.assertTrue(self.run_check([self.leg("bare"), self.leg("typical", 3.0)], {"bare": 118396, "typical": 580}))
        self.assertTrue(self.run_check([self.leg("bare", 3.0), self.leg("typical", 3.0)], {"bare": 400, "typical": 580}))
        with tempfile.TemporaryDirectory(dir="/tmp") as d:
            self.assertTrue(chk.check(d)[1])  # no legs: fail closed


class Table(unittest.TestCase):
    def test_line_reading_and_three_times_rule(self):
        x = {"simple_pct": -3.8, "simple_quoted": [-4.6, -3.1], "log_pct": -3.9}
        self.assertEqual(tbl.line_reading(x, -3.0, True, 0.2, "c7")[0], "Measured")
        self.assertEqual(tbl.line_reading(x, -3.0, False, 1.4, "c7")[0], "Not resolved")   # 3.9 < 3 x 1.4
        self.assertTrue(tbl.line_reading(x, -3.0, False, 1.2, "c7")[0].startswith("Measured"))  # 3.9 >= 3 x 1.2
        y = {"simple_pct": -2.5, "simple_quoted": [-3.3, -1.7], "log_pct": -2.53}
        self.assertIn("AT THE LINE", tbl.line_reading(y, -3.0, True, 0.2, "c7")[1])
        z = {"simple_pct": 4.9, "simple_quoted": [4.1, 5.7], "log_pct": 4.8}
        self.assertIn("short of the +6% line", tbl.line_reading(z, 6.0, True, 0.2, "c11")[1])
        self.assertNotIn("AT THE LINE", tbl.line_reading(z, 6.0, True, 0.2, "c11")[1])

    def test_aa_gate_is_on_log_points(self):
        aa = {"log_pct": 0.99, "log_quoted": [-0.2, 2.2], "simple_pct": 0.995, "simple_quoted": [-0.2, 2.2]}
        self.assertTrue(tbl.aa_gate(aa)[0])
        self.assertFalse(tbl.aa_gate(dict(aa, log_pct=1.01))[0])
        self.assertFalse(tbl.aa_gate(dict(aa, log_pct=0.9, log_quoted=[0.1, 1.7]))[0])  # interval excludes 0


if __name__ == "__main__":
    unittest.main()
