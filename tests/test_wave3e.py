"""Wave 3 track E: multi-target client arguments, arm-level client settings, the TLS groups
setting, the kernel TCP counter probe, and the wave3e configs."""
import copy
import json
import os
import unittest

from epl import envoy_config, evidence, experiment, leg, nighthawk, sysprobe

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "..", "examples", "wave3e", "bench-x86_64")

NETSTAT = """TcpExt: SyncookiesSent ListenOverflows ListenDrops TCPSynRetrans TCPTimeWaitOverflow TCPReqQFullDrop
TcpExt: 0 3 4 5 0 0
IpExt: InNoRoutes
IpExt: 7
"""
SNMP = """Ip: Forwarding DefaultTTL
Ip: 1 64
Tcp: RtoAlgorithm ActiveOpens PassiveOpens AttemptFails EstabResets CurrEstab RetransSegs
Tcp: 1 100 200 1 2 6 9
"""
SOCKSTAT = """sockets: used 201
TCP: inuse 6 orphan 0 tw 1234 alloc 7 mem 0
UDP: inuse 3 mem 1125
"""


class MultiTargetTest(unittest.TestCase):
    def test_args(self):
        a = nighthawk.multi_target_args("https", 10110, "/s", {"count": 3})
        self.assertEqual(a, ["--multi-target-endpoint", "127.0.0.1:10110", "--multi-target-endpoint",
                             "127.0.0.2:10110", "--multi-target-endpoint", "127.0.0.3:10110",
                             "--multi-target-path", "/s", "--multi-target-use-https"])
        self.assertNotIn("--multi-target-use-https", nighthawk.multi_target_args("http", 1, "/", {"count": 1}))

    def test_bounds(self):
        with self.assertRaises(ValueError):
            nighthawk.multi_target_args("http", 1, "/", {"count": 0})
        with self.assertRaises(ValueError):
            nighthawk.multi_target_args("http", 1, "/", {"count": 2, "base": "127.255.255.255"})
        with self.assertRaises(ValueError):
            nighthawk.multi_target_args("http", 1, "/", {"count": 1, "base": "10.0.0.1"})

    def test_client_args_replace_uri(self):
        t = nighthawk.multi_target_args("http", 10110, "/s", {"count": 2})
        a = nighthawk.client_args({"concurrency": 16}, 1600, t, 25, True, ["--max-requests-per-connection", "1"],
                                  ["--max-pending-requests", "1000"])
        self.assertEqual(a[-len(t):], t)
        self.assertFalse(any(x.startswith("http://") for x in a))
        self.assertIn("--max-requests-per-connection", a)
        self.assertNotIn("--prefetch-connections", a)
        u = nighthawk.client_args({"concurrency": 16}, 1600, "http://127.0.0.1:1/s", 25, True)
        self.assertEqual(u[-1], "http://127.0.0.1:1/s")

    def test_connect_failures_count_as_overflow(self):
        self.assertIn("upstream_cx_connect_fail", nighthawk.OVERFLOW_COUNTERS)
        self.assertIn("upstream_cx_connect_timeout", nighthawk.OVERFLOW_COUNTERS)


class ArmClientTest(unittest.TestCase):
    def test_unknown_key(self):
        with self.assertRaises(ValueError):
            leg.arm_client({"name": "x", "client": {"multitarget": {}}})
        self.assertEqual(leg.arm_client({"name": "x"}), {})

    def test_validate(self):
        exp = experiment.load(os.path.join(CFG, "e-plain.json"))
        self.assertEqual(experiment.validate(exp, allow_short=True), [])
        bad = copy.deepcopy(exp)
        bad["envoy"]["listener_fanout"] = 8
        self.assertTrue(any("listener_fanout >= 16" in e for e in experiment.validate(bad, allow_short=True)))
        b = envoy_config.bootstrap(exp["shapes"], dict(exp["envoy"], admin_port=1), 8092)
        lst = b["static_resources"]["listeners"][0]
        self.assertEqual(lst["address"]["socket_address"]["address"], "127.0.0.1")
        self.assertEqual([x["address"]["socket_address"]["address"] for x in lst["additional_addresses"]],
                         ["127.0.0.%d" % i for i in range(2, 17)])
        self.assertEqual(len(b["static_resources"]["listeners"]), 1)
        for v in (1, 0):
            with self.assertRaises(ValueError):
                envoy_config.bootstrap(exp["shapes"], dict(exp["envoy"], admin_port=1, listener_fanout=v), 8092)
        bad = copy.deepcopy(exp)
        bad["arms"][2]["client"]["extra_args"] = "--x"
        self.assertTrue(any("list of strings" in e for e in experiment.validate(bad, allow_short=True)))
        bad = copy.deepcopy(exp)
        bad["arms"][2]["client"]["foo"] = 1
        self.assertTrue(any("unknown client keys" in e for e in experiment.validate(bad, allow_short=True)))


class TlsGroupsTest(unittest.TestCase):
    def test_groups(self):
        t = envoy_config.tls_socket({"cert": "ecdsa-p256", "groups": ["X25519", "P-256"]}, "/c")
        self.assertEqual(t["typed_config"]["common_tls_context"]["tls_params"], {"ecdh_curves": ["X25519", "P-256"]})
        d = envoy_config.tls_socket({"cert": "ecdsa-p256"}, "/c")
        self.assertNotIn("tls_params", d["typed_config"]["common_tls_context"])
        for bad in ({"groups": []}, {"groups": ["x448"]}, {"groups": "X25519"}, {"curves": ["X25519"]}):
            with self.assertRaises(ValueError):
                envoy_config.tls_socket(dict(bad, cert="ecdsa-p256"), "/c")


class AcceptSettingsTest(unittest.TestCase):
    def test_defer_and_reuse_port(self):
        exp = experiment.load(os.path.join(CFG, "e2-plain.json"))
        by = {a["name"]: a for a in exp["arms"]}

        def lst(name):
            b = envoy_config.bootstrap(exp["shapes"], dict(experiment.arm_envoy(exp, by[name]), admin_port=1), 8092)
            return b["static_resources"]["listeners"][0]
        self.assertEqual(lst("c1-defer")["socket_options"], [{"description": "TCP_DEFER_ACCEPT", "level": 6, "name": 9,
                                                              "int_value": 1, "state": "STATE_PREBIND"}])
        self.assertIs(lst("c1-shared")["enable_reuse_port"], False)
        self.assertIn("exact_balance", lst("c1-xb")["connection_balance_config"])
        for n in ("c1", "c1-A2"):
            L = lst(n)
            self.assertNotIn("socket_options", L)
            self.assertNotIn("enable_reuse_port", L)
            self.assertNotIn("connection_balance_config", L)
            self.assertEqual(len(L["additional_addresses"]), 15)
        for bad in ({"tcp_defer_accept_s": 0}, {"reuse_port": True}):
            with self.assertRaises(ValueError):
                envoy_config.bootstrap(exp["shapes"], dict(exp["envoy"], admin_port=1, **bad), 8092)
        strip = lambda a: {k: v for k, v in a.items() if k not in ("name", "evidence", "settings")}  # noqa: E731
        for n in ("c1-A2", "c1-defer", "c1-shared", "c1-xb"):
            self.assertEqual(strip(by[n]), strip(by["c1"]), n)  # the same client in every churn arm


class DeferEvidenceTest(unittest.TestCase):
    def test_defer_counter_expected_once_per_connection(self):
        """TCPDeferAcceptDrop is the ignored bare handshake ACK: 1.00 per request in c1-defer, 0 elsewhere
        (the e2-plain smoke of 2026-11-22 read 32,069 = 1.000 per request and failed a gate written as 0)."""
        for fn in ("e2-plain.json", "e2b-plain.json"):
            exp = experiment.load(os.path.join(CFG, fn))
            for a in exp["arms"]:
                its = [i for i in a["evidence"] if i["stat"] == "kernel_net.d.TCPDeferAcceptDrop"]
                self.assertEqual(len(its), 1, (fn, a["name"]))
                want = 1.0 if a["name"] == "c1-defer" else 0.0
                self.assertEqual(its[0]["per_request"], want)
                m = {"kernel_net": {"d": {"TCPDeferAcceptDrop": 32069 if want else 0}}, "responses_raw": 32066}
                self.assertTrue(evidence.check_item(m, its[0])["ok"], (a["name"], its[0]))
                m["kernel_net"]["d"]["TCPDeferAcceptDrop"] = 0 if want else 32069
                self.assertFalse(evidence.check_item(m, its[0])["ok"], a["name"])
        e2b = experiment.load(os.path.join(CFG, "e2b-plain.json"))
        self.assertEqual([a["name"] for a in e2b["arms"]], ["c1", "c1-A2", "c1-defer", "ka"])
        self.assertEqual(e2b["rounds"], 8)
        self.assertEqual(e2b["order"], "williams")


class KernelNetTest(unittest.TestCase):
    def test_parse(self):
        p = sysprobe.parse_proc_net_pairs(NETSTAT + SNMP)
        self.assertEqual(p["TcpExt.ListenOverflows"], 3)
        self.assertEqual(p["Tcp.PassiveOpens"], 200)
        self.assertEqual(p["IpExt.InNoRoutes"], 7)
        self.assertEqual(sysprobe.parse_sockstat_tcp(SOCKSTAT)["tw"], 1234)

    def test_snapshot_and_delta(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "net"))
            os.makedirs(os.path.join(d, "sys", "net", "netfilter"))
            for name, text in (("net/netstat", NETSTAT), ("net/snmp", SNMP), ("net/sockstat", SOCKSTAT),
                               ("sys/net/netfilter/nf_conntrack_count", "1000\n"),
                               ("sys/net/netfilter/nf_conntrack_max", "262144\n")):
                with open(os.path.join(d, name), "w") as f:
                    f.write(text)
            a = sysprobe.kernel_net(d)
            with open(os.path.join(d, "net/snmp"), "w") as f:
                f.write(SNMP.replace("Tcp: 1 100 200", "Tcp: 1 100 1800"))
            b = sysprobe.kernel_net(d)
        r = sysprobe.kernel_net_delta(a, b)
        self.assertEqual(r["d"]["PassiveOpens"], 1600)
        self.assertEqual(r["d"]["ListenOverflows"], 0)
        self.assertNotIn("TCPAbortOnData", r["d"])  # missing in the file: left out, so a gate fails closed
        self.assertEqual(r["end"]["conntrack_fill"], round(1000 / 262144.0, 4))
        m = {"kernel_net": r, "responses_raw": 1600}
        ok = evidence.check_item(m, {"stat": "kernel_net.d.PassiveOpens", "scope": "field",
                                     "per": "field:responses_raw", "min": 0.97, "max": 1.03})
        self.assertTrue(ok["ok"], ok)
        miss = evidence.check_item(m, {"stat": "kernel_net.d.TCPAbortOnData", "scope": "field", "equals": 0,
                                       "tol_abs": 0})
        self.assertFalse(miss["ok"])


class Wave3eConfigsTest(unittest.TestCase):
    def test_configs(self):
        for fn in ("e-plain.json", "e-tls.json", "smoke-e-plain.json", "smoke-e-tls.json", "e2-plain.json",
                   "smoke-e2-plain.json", "e2b-plain.json", "smoke-e2b-plain.json"):
            exp = experiment.load(os.path.join(CFG, fn))
            self.assertEqual(experiment.validate(exp, allow_short=True), [], fn)
            names = [a["name"] for a in exp["arms"]]
            for a in exp["arms"]:
                self.assertEqual(evidence.validate_items(a["evidence"], names), [], (fn, a["name"]))
                self.assertEqual(a["source_sha256"],
                                 "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc")
            self.assertFalse(exp["envoy"]["exact_balance"])
            self.assertTrue(exp["measure"]["kernel_net"])
            if not fn.startswith("smoke"):
                self.assertEqual(exp["order"], "williams")
                self.assertEqual(exp["rounds"] % experiment.order_period(exp), 0)

    def test_arms_differ_only_as_named(self):
        tls = experiment.load(os.path.join(CFG, "e-tls.json"))
        by = {a["name"]: a for a in tls["arms"]}
        strip = lambda a: {k: v for k, v in a.items() if k not in ("name", "evidence")}  # noqa: E731
        self.assertEqual(strip(by["ecdsa-full"]), strip(by["ecdsa-full-A2"]))
        # every churn arm runs the same client; only the server's settings differ
        for n in ("rsa-full", "ecdsa-res", "ecdsa-x25519"):
            self.assertEqual(by[n]["client"], by["ecdsa-full"]["client"], n)
        self.assertEqual(by["tls-ka"]["settings"], by["ecdsa-full"]["settings"])
        self.assertNotIn("multi_target", by["tls-ka"]["client"])
        plain = experiment.load(os.path.join(CFG, "e-plain.json"))
        p = {a["name"]: a for a in plain["arms"]}
        self.assertEqual(strip(p["ka"]), strip(p["ka-A2"]))
        self.assertEqual(p["c1"]["client"]["multi_target"]["count"], 16)
        self.assertNotIn("settings", p["c1"])


if __name__ == "__main__":
    unittest.main()
