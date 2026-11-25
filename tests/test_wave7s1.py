"""Wave 7 S1: tcp_proxy, Unix-socket hops, inline-body origin, and the S1 configs."""
import json
import os
import re
import tempfile
import unittest

from epl import envoy_config as ec
from epl import experiment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "examples", "wave7s1", "configs")
SHAPE = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200}]
ENV = {"listener_port": 10110, "admin_port": 9921}


class Settings(unittest.TestCase):
    def test_tcp_proxy_replaces_the_hcm(self):
        b = ec.bootstrap(SHAPE, dict(ENV, tcp_proxy=True), 8092)
        f = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"]
        self.assertEqual([x["name"] for x in f], ["envoy.filters.network.tcp_proxy"])
        self.assertEqual(f[0]["typed_config"], {"@type": ec.TCP_PROXY, "stat_prefix": "relay", "cluster": "origin"})
        self.assertIn("connection_balance_config", b["static_resources"]["listeners"][0])
        b = ec.bootstrap(SHAPE, dict(ENV, tcp_proxy={"idle_timeout_s": 0}), 8092)
        self.assertEqual(b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]["idle_timeout"], "0s")
        with self.assertRaises(ValueError):
            ec.bootstrap(SHAPE, dict(ENV, tcp_proxy=True, retries=True), 8092)
        with self.assertRaises(ValueError):
            ec.bootstrap(SHAPE, dict(ENV, tcp_proxy={"x": 1}), 8092)

    def test_pipe_addresses(self):
        b = ec.bootstrap(SHAPE, dict(ENV, upstream_pipe="/run/x/o.sock", listener_pipe="/run/x/h.sock"), 8092)
        self.assertEqual(b["static_resources"]["listeners"][0]["address"], {"pipe": {"path": "/run/x/h.sock"}})
        ep = b["static_resources"]["clusters"][0]["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]
        self.assertEqual(ep["address"], {"pipe": {"path": "/run/x/o.sock"}})
        for bad in ("rel/x.sock", "/" + "a" * 120):
            with self.assertRaises(ValueError):
                ec.pipe_address(bad)

    def test_inline_origin(self):
        sh = [{"name": "p64", "path": "/p64", "kind": "proxied", "origin_inline": True, "body_bytes": 64, "rps": 8000}]
        self.assertEqual(ec.origin_files(sh), {})
        conf = ec.nginx_conf(8092, 8, inline=ec.inline_bodies(sh), uds="/uds/origin.sock")
        self.assertEqual(conf.count('location = /p64 { return 200 "%s"; }' % ("a" * 64)), 2)
        self.assertIn("listen unix:/uds/origin.sock;", conf)
        self.assertNotIn("unix:", ec.nginx_conf(8092, 8))
        with self.assertRaises(ValueError):
            ec.inline_bodies([dict(sh[0], path='/p"x')])


class Configs(unittest.TestCase):
    def test_arms_and_rounds(self):
        legs = {}
        for fn in sorted(os.listdir(CFG)):
            e = experiment.load(os.path.join(CFG, fn))
            self.assertEqual(experiment.validate(e, allow_short=True), [], fn)
            legs[fn[:-5]] = len(experiment.cells(e)) * e["rounds"]
            self.assertEqual(e["idle"]["procs"], [], fn)
        self.assertEqual(legs["s1a-hop"], 64)
        self.assertEqual(legs["s1b-relay"], 64)
        self.assertEqual(legs["smoke-s1a-hop"], 10)
        self.assertEqual(legs["smoke-s1b-relay"], 8)
        for v in ("s1a-hop-no-pair-uds", "s1a-hop-no-one-uds", "s1a-hop-no-uds"):
            self.assertEqual(legs[v], 64)

    def test_hop_b_and_uds_bootstraps(self):
        e = experiment.load(os.path.join(CFG, "s1a-hop.json"))
        with tempfile.TemporaryDirectory(dir="/tmp") as d:
            _, texts, _ = experiment.prepare_bootstraps(e, d, make_certs=False)
            self.assertEqual(oct(os.stat(os.path.join(d, "uds")).st_mode & 0o777), "0o700")
        chain = lambda k: json.loads(texts[k])["static_resources"]["listeners"][0]["filter_chains"][0]  # noqa: E731
        self.assertEqual(chain("_hop2:pair-l4")["filters"][0]["name"], "envoy.filters.network.tcp_proxy")
        self.assertEqual(chain("_hop2:pair")["filters"][0]["name"], "envoy.filters.network.http_connection_manager")
        m = chain("_hop2:pair-mtls-l4")
        self.assertEqual(m["filters"][0]["name"], "envoy.filters.network.tcp_proxy")
        self.assertTrue(m["transport_socket"]["typed_config"]["require_client_certificate"])
        a, b = json.loads(texts["pair-uds"]), json.loads(texts["_hop2:pair-uds"])
        up = a["static_resources"]["clusters"][0]["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"]
        self.assertEqual(up, b["static_resources"]["listeners"][0]["address"])
        self.assertIn("pipe", up)
        self.assertIn("pipe", json.dumps(json.loads(texts["one-uds"])["static_resources"]["clusters"][0]))
        # the http arm of the relay run holds one upstream pool per client connection, like the tcp arms
        r = experiment.load(os.path.join(CFG, "s1b-relay.json"))
        self.assertTrue(experiment.arm_settings([x for x in r["arms"] if x["name"] == "http"][0])["upstream_pool_per_downstream"])
        self.assertEqual(r["measure"]["responses_from"], "origin")

    def test_everything_binds_to_loopback_or_a_run_directory_socket(self):
        for fn in sorted(os.listdir(CFG)):
            e = experiment.load(os.path.join(CFG, fn))
            with tempfile.TemporaryDirectory(dir="/tmp") as d:
                _, texts, _ = experiment.prepare_bootstraps(e, d, make_certs=False)
                addrs, pipes = [], []

                def walk(x):
                    if isinstance(x, dict):
                        if "address" in x and "port_value" in x:
                            addrs.append(str(x["address"]))
                        if "pipe" in x:
                            pipes.append(x["pipe"]["path"])
                        for v in x.values():
                            walk(v)
                    elif isinstance(x, list):
                        for v in x:
                            walk(v)
                for t in texts.values():
                    walk(json.loads(t))
                self.assertTrue(addrs, fn)
                self.assertEqual([a for a in addrs if not a.startswith("127.")], [], fn)
                self.assertEqual([p for p in pipes if not p.startswith(os.path.realpath(d) + "/") and not p.startswith(d + "/")], [], fn)
            conf = ec.nginx_conf(e["origin"]["port"], 8, stub_status=True, inline=ec.inline_bodies(e["shapes"]),
                                 uds="/uds/origin.sock" if e["origin"].get("uds") else None)
            ls = re.findall(r"listen ([^ ;]+)", conf)
            self.assertEqual([x for x in ls if not x.startswith("127.") and x != "unix:/uds/origin.sock"], [], fn)
            self.assertNotIn("include", conf)


if __name__ == "__main__":
    unittest.main()
