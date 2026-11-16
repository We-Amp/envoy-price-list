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


class AuthAndRateLimitTest(unittest.TestCase):
    JW = {"jwks": '{"keys":[]}', "issuer": "https://epl.example", "audience": "epl"}

    def test_jwt_authn_local_jwks_before_router(self):
        h = hcm(envoy_config.bootstrap(S, dict(E, jwt_authn=self.JW), 8092))
        names = [f["name"] for f in h["http_filters"]]
        self.assertEqual(names, ["envoy.filters.http.jwt_authn", "envoy.filters.http.router"])
        prov = h["http_filters"][0]["typed_config"]["providers"]["epl"]
        self.assertEqual(prov["local_jwks"], {"inline_string": '{"keys":[]}'})
        self.assertTrue(prov["forward"])
        self.assertNotIn("remote_jwks", prov)
        self.assertNotIn("jwt_cache_config", prov)
        rule = h["http_filters"][0]["typed_config"]["rules"][0]
        self.assertEqual(rule, {"match": {"prefix": "/"}, "requires": {"provider_name": "epl"}})
        prov = hcm(envoy_config.bootstrap(S, dict(E, jwt_authn=dict(self.JW, cache=True)), 8092))[
            "http_filters"][0]["typed_config"]["providers"]["epl"]
        self.assertEqual(prov["jwt_cache_config"], {"jwt_cache_size": 100})
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S, dict(E, jwt_authn={"issuer": "x", "audience": "y"}), 8092)
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S, dict(E, jwt_authn=dict(self.JW, cached=True)), 8092)

    def test_local_ratelimit_enabled_and_enforced(self):
        h = hcm(envoy_config.bootstrap(S, dict(E, local_ratelimit={"tokens_per_s": 100000}), 8092))
        f = h["http_filters"][0]
        self.assertEqual(f["name"], "envoy.filters.http.local_ratelimit")
        tc = f["typed_config"]
        self.assertEqual(tc["token_bucket"], {"max_tokens": 100000, "tokens_per_fill": 100000, "fill_interval": "1s"})
        for k in ("filter_enabled", "filter_enforced"):
            self.assertEqual(tc[k]["default_value"], {"numerator": 100, "denominator": "HUNDRED"})
        self.assertEqual(h["http_filters"][-1]["name"], "envoy.filters.http.router")

    def test_both_filters_keep_router_last(self):
        h = hcm(envoy_config.bootstrap(S, dict(E, jwt_authn=self.JW, local_ratelimit={"tokens_per_s": 10}), 8092))
        self.assertEqual([f["name"] for f in h["http_filters"]],
                         ["envoy.filters.http.jwt_authn", "envoy.filters.http.local_ratelimit",
                          "envoy.filters.http.router"])

    def test_stats_are_recorded(self):
        from epl import leg
        import re
        f = re.compile(leg.STAT_FILTER)
        for k in ("http.ingress_http.jwt_authn.allowed", "http.ingress_http.jwt_authn.denied",
                  "http_local_rate_limiter.http_local_rate_limit.ok",
                  "http_local_rate_limiter.http_local_rate_limit.rate_limited"):
            self.assertTrue(f.search(k), k)
            self.assertTrue(leg.DELTA_KEYS_RE.search(k), k)


class SharedPathTest(unittest.TestCase):
    def test_two_rates_share_one_route(self):
        two = S + [dict(S[0], name="s-hi", rps=3200)]
        rs = hcm(envoy_config.bootstrap(two, E, 8092))["route_config"]["virtual_hosts"][0]["routes"]
        self.assertEqual(len(rs), 1)
        self.assertEqual(envoy_config.bootstrap(two, E, 8092), envoy_config.bootstrap(S, E, 8092))
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(S + [dict(S[0], name="d", kind="direct_headers")], E, 8092)


class FloorArmTest(unittest.TestCase):
    def test_floor_from_one_arm_only(self):
        p = lambda lo, hi: {"paired": {"half_width_pct": (hi - lo) / 2, "log_lo_pct": lo, "log_hi_pct": hi}}  # noqa
        res = {"analysis": {"shapes": {"s": {"comparisons": [
            {"arm": "old", "ref": "new", "cycles_total": p(4.0, 6.0)},
            {"arm": "new-A2", "ref": "new", "cycles_total": p(-0.5, 0.7)}]}}}}
        self.assertAlmostEqual(experiment.floor_from_results(res)["s"]["cycles_total"]["far"], 6.0)
        fl = experiment.floor_from_results(res, "new-A2")["s"]["cycles_total"]
        self.assertAlmostEqual(fl["hw"], 0.6)
        self.assertAlmostEqual(fl["far"], 0.7)
        with tempfile.TemporaryDirectory() as d:
            fn = os.path.join(d, "r.json")
            with open(fn, "w") as f:
                json.dump(res, f)
            self.assertIn("s", experiment.load_floor(fn, "new-A2"))
            with self.assertRaises(ValueError):
                experiment.load_floor(fn, "missing")


class NewExampleSetsTest(unittest.TestCase):
    def test_release_and_filter_configs_validate(self):
        dirs = [os.path.join(HERE, "examples", "releases"), os.path.join(SM, "filters")]
        seen = 0
        for d in dirs:
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".json") or fn == "jwt.json":
                    continue
                exp = experiment.load(os.path.join(d, fn))
                self.assertEqual(experiment.validate(exp, allow_short=fn == "smoke.json"), [], fn)
                with tempfile.TemporaryDirectory() as t:
                    _, texts, _ = experiment.prepare_bootstraps(exp, t, make_certs=False)
                if "floor_arm" in exp:
                    self.assertIn(exp["floor_arm"], ("v1.40.2-A2",))
                seen += 1
        self.assertEqual(seen, 5)

    def test_release_arms_share_one_bootstrap_and_aa_arm(self):
        exp = experiment.load(os.path.join(HERE, "examples", "releases", "releases.json"))
        with tempfile.TemporaryDirectory() as t:
            paths, texts, _ = experiment.prepare_bootstraps(exp, t, make_certs=False)
        self.assertEqual(len(set(texts.values())), 1)
        a2 = [a for a in exp["arms"] if a["name"] == "v1.40.2-A2"][0]
        base = [a for a in exp["arms"] if a["name"] == exp["base_arm"]][0]
        self.assertEqual(a2["binary"], base["binary"])
        self.assertEqual(experiment.order_period(exp), 14)


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


class RouteTableShapeTest(unittest.TestCase):
    TABLE = {"vhost": {"response_headers_to_add": [{"header": {"key": "x-fixed-0", "value": "v"}}]},
             "routes": [{"match": {"prefix": "/r1/"}, "direct_response": {"status": 200}},
                        {"match": {"prefix": "/target/"}, "direct_response": {"status": 200}}],
             "source_md5": "not-used-by-the-bootstrap"}

    def shape(self, **kw):
        return dict({"name": "rt", "path": "/target/x", "kind": "routes", "rps": 1600,
                     "route_table": self.TABLE}, **kw)

    def test_table_used_in_order_with_vhost_fields(self):
        b = envoy_config.bootstrap([self.shape(), self.shape(name="rt-hi", rps=3200)], E, 8092)
        vh = hcm(b)["route_config"]["virtual_hosts"][0]
        self.assertEqual(vh["routes"], self.TABLE["routes"])
        self.assertEqual(vh["response_headers_to_add"], self.TABLE["vhost"]["response_headers_to_add"])
        self.assertEqual((vh["name"], vh["domains"]), ("service", ["*"]))
        # generated shapes keep their bootstrap unchanged (no virtual-host fields)
        self.assertEqual(sorted(hcm(envoy_config.bootstrap(S, E, 8092))["route_config"]["virtual_hosts"][0]),
                         ["domains", "name", "routes"])

    def test_rejects_bad_tables(self):
        with self.assertRaises(ValueError):
            envoy_config.bootstrap([self.shape(route_table={"routes": []})], E, 8092)
        with self.assertRaises(ValueError):
            envoy_config.bootstrap([self.shape(route_table=dict(self.TABLE, vhost={"domains": ["x"]}))], E, 8092)
        other = dict(self.TABLE, routes=self.TABLE["routes"][:1])
        with self.assertRaises(ValueError):  # same path, different table
            envoy_config.bootstrap([self.shape(), self.shape(name="b", route_table=other)], E, 8092)
        other = dict(self.TABLE, vhost={"response_headers_to_add": []})
        with self.assertRaises(ValueError):  # different paths, conflicting virtual-host field
            envoy_config.bootstrap([self.shape(), self.shape(name="b", path="/o", route_table=other)], E, 8092)

    def test_validate(self):
        exp = experiment.load(os.path.join(HERE, "examples", "aa-selftest.json"))
        exp["shapes"] = [self.shape(rps=1600)]
        self.assertEqual([e for e in experiment.validate(exp) if "shape" in e], [])
        exp["shapes"] = [self.shape(route_table={"routes": []})]
        self.assertTrue(any("route_table.routes" in e for e in experiment.validate(exp)))
        up = {"routes": [{"match": {"prefix": "/"}, "route": {"cluster": "origin"}}]}
        exp["shapes"] = [self.shape(route_table=up)]
        self.assertTrue(any("upstream routes" in e for e in experiment.validate(exp)))
