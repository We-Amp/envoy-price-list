import json
import os
import tempfile
import unittest

from epl import envoy_config, experiment

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SM = os.path.join(HERE, "examples", "settings-matrix")
S = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 1600}]
E = {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True}


def hcm(b):
    return b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]


class BootstrapSettingsTest(unittest.TestCase):
    def test_baseline_has_no_setting(self):
        b = envoy_config.bootstrap(S, E, 8092)
        h = hcm(b)
        for k in ("tracing", "access_log", "http2_protocol_options"):
            self.assertNotIn(k, h)
        self.assertEqual([f["name"] for f in h["http_filters"]], ["envoy.filters.http.router"])
        self.assertNotIn("transport_socket", b["static_resources"]["listeners"][0]["filter_chains"][0])
        self.assertNotIn("retry_policy", h["route_config"]["virtual_hosts"][0]["routes"][0]["route"])

    def test_each_setting(self):
        b = envoy_config.bootstrap(S, dict(E, tls={"cert": "ecdsa-p256", "resumption": False}), 8092, "/c")
        ts = b["static_resources"]["listeners"][0]["filter_chains"][0]["transport_socket"]["typed_config"]
        self.assertTrue(ts["disable_stateless_session_resumption"])
        self.assertTrue(ts["common_tls_context"]["tls_certificates"][0]["private_key"]["filename"]
                        .endswith("ecdsa-p256.key"))
        b = envoy_config.bootstrap(S, dict(E, tls={"cert": "rsa2048"}), 8092, "/c")
        ts = b["static_resources"]["listeners"][0]["filter_chains"][0]["transport_socket"]["typed_config"]
        self.assertNotIn("disable_stateless_session_resumption", ts)
        self.assertEqual(hcm(envoy_config.bootstrap(S, dict(E, hpack_table_size=0), 8092))
                         ["http2_protocol_options"], {"hpack_table_size": 0})
        b = envoy_config.bootstrap(S, dict(E, tracing={"sampling_pct": 1}, collector_port=4317), 8092)
        self.assertEqual(hcm(b)["tracing"]["random_sampling"], {"value": 1.0})
        self.assertIn("otel_collector", [c["name"] for c in b["static_resources"]["clusters"]])
        b = envoy_config.bootstrap(S, dict(E, access_log={"format": "json", "path": "/x"}), 8092)
        self.assertIn("json_format", hcm(b)["access_log"][0]["typed_config"]["log_format"])
        b = envoy_config.bootstrap(S, dict(E, ext_authz=True, authz_port=8093), 8092)
        self.assertEqual(hcm(b)["http_filters"][0]["name"], "envoy.filters.http.ext_authz")
        b = envoy_config.bootstrap(S, dict(E, retries=True), 8092)
        self.assertIn("retry_policy", hcm(b)["route_config"]["virtual_hosts"][0]["routes"][0]["route"])
        b = envoy_config.bootstrap(S, dict(E, buffer_limit_bytes=4096), 8092)
        self.assertEqual(b["static_resources"]["listeners"][0]["per_connection_buffer_limit_bytes"], 4096)
        self.assertEqual(b["static_resources"]["clusters"][0]["per_connection_buffer_limit_bytes"], 4096)
        b = envoy_config.bootstrap(S, dict(E, upstream_port=10120), 8092)
        ep = b["static_resources"]["clusters"][0]["load_assignment"]["endpoints"][0]["lb_endpoints"][0]
        self.assertEqual(ep["endpoint"]["address"]["socket_address"]["port_value"], 10120)


class MatrixConfigsTest(unittest.TestCase):
    def test_every_row_validates_and_differs_in_one_setting(self):
        for fn in sorted(os.listdir(SM)):
            if not fn.endswith(".json"):
                continue
            exp = experiment.load(os.path.join(SM, fn))
            self.assertEqual(experiment.validate(exp), [], fn)
            with tempfile.TemporaryDirectory() as d:
                paths, texts, _ = experiment.prepare_bootstraps(exp, d, make_certs=False)
                base = exp["base_arm"]
                for a in exp["arms"]:
                    self.assertLessEqual(len(experiment.arm_settings(a)) + len(a.get("env", {})), 1, fn)
                    if a["name"] != base and experiment.arm_settings(a):
                        self.assertNotEqual(texts[a["name"]], texts[base], fn)

    def test_unknown_setting_rejected(self):
        exp = experiment.load(os.path.join(SM, "07-retries.json"))
        exp["arms"][1]["settings"] = {"retry": True}
        self.assertTrue(any("unknown settings" in e for e in experiment.validate(exp)))

    def test_two_hop_needs_cpus(self):
        exp = experiment.load(os.path.join(SM, "10-two-hop.json"))
        del exp["cpus"]["hop2"]
        self.assertTrue(any("cpus.hop2" in e for e in experiment.validate(exp)))

    def test_dry_run_with_settings(self):
        exp = experiment.load(os.path.join(SM, "04-tracing.json"), {"floor_from": None})
        with tempfile.TemporaryDirectory() as d:
            from epl.sim import SimBackend
            res = experiment.Runner(exp, d, SimBackend).run(simulate=True)
            self.assertEqual(len(res["analysis"]["shapes"]["s"]["comparisons"]), 3)
            self.assertTrue(os.path.exists(os.path.join(d, "envoy-bootstrap-sampling-1.json")))


if __name__ == "__main__":
    unittest.main()


class UpstreamHttpTest(unittest.TestCase):
    def test_pool_limits_on_origin_cluster(self):
        b = envoy_config.bootstrap(S, dict(E, upstream_http={"max_requests": 1000}), 8092)
        po = b["static_resources"]["clusters"][0]["typed_extension_protocol_options"][
            "envoy.extensions.upstreams.http.v3.HttpProtocolOptions"]
        self.assertEqual(po["common_http_protocol_options"], {"max_requests_per_connection": 1000})
        self.assertEqual(po["explicit_http_config"], {"http_protocol_options": {}})
        b = envoy_config.bootstrap(S, dict(E, upstream_http={"idle_timeout_s": 5,
                                                             "max_connection_duration_s": 30}), 8092)
        cho = b["static_resources"]["clusters"][0]["typed_extension_protocol_options"][
            "envoy.extensions.upstreams.http.v3.HttpProtocolOptions"]["common_http_protocol_options"]
        self.assertEqual(cho, {"idle_timeout": "5s", "max_connection_duration": "30s"})
        self.assertNotIn("typed_extension_protocol_options", envoy_config.bootstrap(S, E, 8092)
                         ["static_resources"]["clusters"][0])
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S, dict(E, upstream_http={"max_request": 1}), 8092)
