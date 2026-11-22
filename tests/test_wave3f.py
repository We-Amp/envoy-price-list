"""Wave 3 track F: HTTP/2 and TLS upstreams, the runtime layer, grpc_stats, mTLS between hops, the gRPC
responder, hop-2 evidence scopes, and the run configs."""
import copy
import json
import os
import tempfile
import unittest

from epl import envoy_config as ec
from epl import evidence, experiment

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG = os.path.join(ROOT, "examples", "wave3f", "configs")
SHAPE = [{"name": "s", "kind": "proxied", "path": "/s", "body_bytes": 4096, "rps": 5200}]
ENV = {"listener_port": 10110, "admin_port": 9921}


def boot(**settings):
    return ec.bootstrap(SHAPE, dict(ENV, **settings), 8092, "/certs")


def origin_cluster(b):
    return b["static_resources"]["clusters"][0]


class GrpcFrameTest(unittest.TestCase):
    def test_exact_length_and_prefix(self):
        for total in (7, 8, 66, 133, 134, 135, 4096, 20000):
            f = ec.grpc_frame(total)
            self.assertEqual(len(f), total)
            self.assertEqual(f[0], 0)  # uncompressed
            self.assertEqual(int.from_bytes(f[1:5], "big"), total - 5)
            # one protobuf field: tag 1 / wire type 2, varint length, then that many bytes
            self.assertEqual(f[5], 0x0A)
            n, i, shift = 0, 6, 0
            while True:
                b = f[i]
                n |= (b & 0x7F) << shift
                i += 1
                shift += 7
                if not b & 0x80:
                    break
            # where the varint length steps up, an empty field 2 fills the gap
            self.assertIn(f[i + n:], (b"", b"\x12\x00"))

    def test_every_size(self):
        for total in range(7, 20000):
            self.assertEqual(len(ec.grpc_frame(total)), total)
        self.assertEqual(ec.grpc_frame(66)[:7].hex(), "000000003d0a3b")  # the request file's frame

    def test_too_short(self):
        with self.assertRaises(ValueError):
            ec.grpc_frame(6)

    def test_grpc_shape_is_not_a_plain_file(self):
        g = {"name": "g", "kind": "proxied", "path": "/epl.bench.Bench/Unary", "body_bytes": 4096, "grpc": True}
        self.assertEqual(ec.origin_files([g] + SHAPE), {"s": 4096})
        files = ec.grpc_files([g])
        self.assertEqual(list(files), ["/epl.bench.Bench/Unary"])
        self.assertEqual(files["/epl.bench.Bench/Unary"][0], "_grpc/g.grpc")
        self.assertEqual(len(files["/epl.bench.Bench/Unary"][1]), 4096)


class NginxConfTest(unittest.TestCase):
    def test_default_unchanged(self):
        c = ec.nginx_conf(8092, 8)
        self.assertNotIn("http2 on", c)
        self.assertNotIn("ssl", c)
        self.assertEqual(c.count("server {"), 1)

    def test_h2c_tls_and_grpc(self):
        g = {"name": "g", "kind": "proxied", "path": "/epl.bench.Bench/Unary", "body_bytes": 4096, "grpc": True}
        c = ec.nginx_conf(8092, 8, h2c_port=8096, tls_port=8097, tls_cert="ecdsa-p256-san", grpc=ec.grpc_files([g]))
        self.assertIn("listen 127.0.0.1:8096; http2 on;", c)
        self.assertIn("listen 127.0.0.1:8097 ssl; http2 on;", c)
        self.assertIn("ssl_certificate /certs/ecdsa-p256-san.crt", c)
        # the responder on both HTTP/2 servers, never on the plain one
        self.assertEqual(c.count("location = /epl.bench.Bench/Unary { error_page 405 =200 /_grpc/g.grpc;"), 2)
        self.assertEqual(c.count("add_trailer grpc-status 0 always"), 2)
        plain = c.split("server {")[1]
        self.assertNotIn("Unary", plain)

    def test_tls_needs_cert(self):
        with self.assertRaises(ValueError):
            ec.nginx_conf(8092, 8, tls_port=8097)


class UpstreamTest(unittest.TestCase):
    def test_http2(self):
        c = origin_cluster(boot(upstream_http2=True))
        po = c["typed_extension_protocol_options"]["envoy.extensions.upstreams.http.v3.HttpProtocolOptions"]
        self.assertEqual(po["explicit_http_config"], {"http2_protocol_options": {}})
        self.assertNotIn("transport_socket", c)

    def test_http2_conflicts(self):
        with self.assertRaises(ValueError):
            boot(upstream_http2=True, upstream_http={"max_requests": 10})
        with self.assertRaises(ValueError):
            boot(upstream_http2="yes")

    def test_tls(self):
        c = origin_cluster(boot(upstream_tls={"ca": "ecdsa-p256-san", "sni": "bench.local", "san": "bench.local",
                                              "alpn": ["h2"]}))
        t = c["transport_socket"]["typed_config"]
        self.assertEqual(t["@type"], ec.UTLS)
        self.assertEqual(t["sni"], "bench.local")
        ctc = t["common_tls_context"]
        self.assertEqual(ctc["alpn_protocols"], ["h2"])
        self.assertEqual(ctc["validation_context"]["trusted_ca"]["filename"], "/certs/ecdsa-p256-san.crt")
        self.assertEqual(ctc["validation_context"]["match_typed_subject_alt_names"],
                         [{"san_type": "DNS", "matcher": {"exact": "bench.local"}}])
        self.assertNotIn("tls_certificates", ctc)
        self.assertNotIn("max_session_keys", t)

    def test_tls_client_cert(self):
        t = origin_cluster(boot(upstream_tls={"ca": "ecdsa-p256-san", "cert": "ecdsa-p256-client",
                                              "max_session_keys": 0}))["transport_socket"]["typed_config"]
        self.assertEqual(t["common_tls_context"]["tls_certificates"][0]["certificate_chain"]["filename"],
                         "/certs/ecdsa-p256-client.crt")
        self.assertEqual(t["max_session_keys"], 0)

    def test_tls_errors(self):
        for bad in ({}, {"sni": "x"}, {"ca": "nope"}, {"ca": "ecdsa-p256-san", "extra": 1},
                    {"ca": "ecdsa-p256-san", "cert": "nope"}):
            with self.assertRaises(ValueError, msg=bad):
                boot(upstream_tls=bad)

    def test_origin_server_value(self):
        with self.assertRaises(ValueError):
            boot(origin_server="quic")


class ListenerTlsTest(unittest.TestCase):
    def test_plain_tls_unchanged(self):
        t = ec.tls_socket({"cert": "rsa2048"}, "/certs")["typed_config"]
        self.assertNotIn("require_client_certificate", t)
        self.assertNotIn("validation_context", t["common_tls_context"])

    def test_client_cert_required(self):
        t = ec.tls_socket({"cert": "ecdsa-p256-san", "client_ca": "ecdsa-p256-client",
                           "client_san": "client.bench.local"}, "/certs")["typed_config"]
        self.assertTrue(t["require_client_certificate"])
        v = t["common_tls_context"]["validation_context"]
        self.assertEqual(v["trusted_ca"]["filename"], "/certs/ecdsa-p256-client.crt")
        self.assertEqual(v["match_typed_subject_alt_names"][0]["matcher"], {"exact": "client.bench.local"})

    def test_errors(self):
        for bad in ({"cert": "rsa2048", "client_san": "x"}, {"cert": "rsa2048", "bogus": 1},
                    {"cert": "rsa2048", "client_ca": "nope"}):
            with self.assertRaises(ValueError, msg=bad):
                ec.tls_socket(bad, "/certs")

    def test_cert_kinds(self):
        self.assertEqual(ec.cert_kinds_of({}), set())
        self.assertEqual(ec.cert_kinds_of({"tls": {"cert": "ecdsa-p256-san", "client_ca": "ecdsa-p256-client"},
                                           "upstream_tls": {"ca": "rsa2048", "cert": "ecdsa-p256"}}),
                         {"ecdsa-p256-san", "ecdsa-p256-client", "rsa2048", "ecdsa-p256"})
        self.assertEqual(set(ec.CERT_SAN) - set(ec.CERT_KINDS), set())


class RuntimeAndGrpcStatsTest(unittest.TestCase):
    def test_runtime_layer(self):
        b = boot(runtime={ec.OGHTTP2_KEY: True})
        self.assertEqual(b["layered_runtime"], {"layers": [{"name": "epl-static",
                                                            "static_layer": {ec.OGHTTP2_KEY: True}}]})
        self.assertNotIn("layered_runtime", boot())
        for bad in ({}, {"k": [1]}, "x"):
            with self.assertRaises(ValueError):
                boot(runtime=bad)

    def test_grpc_stats_before_router(self):
        hcm = boot(grpc_stats={"stats_for_all_methods": True})["static_resources"]["listeners"][0][
            "filter_chains"][0]["filters"][0]["typed_config"]
        names = [f["name"] for f in hcm["http_filters"]]
        self.assertEqual(names, ["envoy.filters.http.grpc_stats", "envoy.filters.http.router"])
        self.assertEqual(hcm["http_filters"][0]["typed_config"], {"@type": ec.GRPC_STATS, "stats_for_all_methods": True})
        with self.assertRaises(ValueError):
            boot(grpc_stats={"emit_filter_state": True})


class ExperimentWiringTest(unittest.TestCase):
    def exp(self, name):
        return experiment.load(os.path.join(CFG, name))

    def test_origin_server_ports(self):
        e = self.exp("f1-upstream.json")
        ports = {a["name"]: origin_cluster(ec.bootstrap(e["shapes"], experiment.arm_envoy(e, a), e["origin"]["port"],
                                                        "/c"))["load_assignment"]["endpoints"][0]["lb_endpoints"][0][
            "endpoint"]["address"]["socket_address"]["port_value"] for a in e["arms"]}
        self.assertEqual(ports, {"h1": 8092, "h1-A2": 8092, "h2c": 8096, "h2c-og": 8096, "tls-h1": 8097, "tls-h2": 8097})

    def test_origin_server_needs_port(self):
        e = self.exp("f1-upstream.json")
        e["origin"].pop("h2c_port")
        with self.assertRaises(ValueError):
            experiment.arm_envoy(e, [a for a in e["arms"] if a["name"] == "h2c"][0])

    def test_two_hop_mtls(self):
        e = self.exp("f3-mtls.json")
        a = [x for x in e["arms"] if x["name"] == "pair-mtls"][0]
        ha = experiment.arm_envoy(e, a)
        self.assertEqual(ha["upstream_port"], 10120)  # hop A targets hop B, whatever origin_server says
        hb = experiment.hop2_envoy(e, a)
        self.assertNotIn("upstream_port", hb)  # hop B targets the plain origin
        self.assertEqual(hb["tls"]["client_ca"], "ecdsa-p256-client")
        self.assertEqual(experiment.cert_kinds(e), ["ecdsa-p256-client", "ecdsa-p256-san"])
        with tempfile.TemporaryDirectory() as d:
            paths, texts, certs = experiment.prepare_bootstraps(e, d, make_certs=False)
            self.assertEqual(sorted(certs["certs"]), ["ecdsa-p256-client", "ecdsa-p256-san"])
            b = json.loads(texts[experiment.hop2_key(a)])
            self.assertTrue(b["static_resources"]["listeners"][0]["filter_chains"][0]["transport_socket"][
                "typed_config"]["require_client_certificate"])

    def test_cert_kinds_of_older_configs(self):
        # the TLS rows of the settings matrix make the same certificates as before
        e = experiment.load(os.path.join(ROOT, "examples", "settings-matrix", "01-tls-cert.json"))
        self.assertEqual(experiment.cert_kinds(e), ["ecdsa-p256", "rsa2048"])
        e = experiment.load(os.path.join(ROOT, "examples", "settings-matrix", "04-tracing.json"))
        self.assertEqual(experiment.cert_kinds(e), [])

    def test_request_body(self):
        e = self.exp("f2-grpc.json")
        g = e["shapes"][0]
        p = experiment.request_body_path(g)
        with open(p, "rb") as f:
            self.assertEqual(f.read(), ec.grpc_frame(66))
        bad = dict(g, request_body_sha256="0" * 64)
        with self.assertRaises(ValueError):
            experiment.request_body_path(bad)
        e2 = copy.deepcopy(e)
        e2["shapes"][0] = bad
        self.assertTrue(any("request_body_sha256" in x for x in experiment.validate(e2, allow_short=True)))


class Hop2EvidenceTest(unittest.TestCase):
    def test_scopes(self):
        m = {"responses_raw": 100, "sut_stats_window": {}, "sut_stats_window_ok": True,
             "hop2_stats_window": {"http.ingress_http.downstream_rq_2xx": 100, "x.ssl.handshake": 0},
             "hop2_stats_window_ok": True, "hop2_stats_leg_end": {"x.ssl.handshake": 600}, "hop2_stats_leg_end_ok": True,
             "sut_stats_leg_end": {"http.ingress_http.downstream_rq_completed": 1000}}
        ok = lambda it: evidence.check_item(m, it)["ok"]  # noqa: E731
        self.assertTrue(ok({"stat": "http.ingress_http.downstream_rq_2xx", "scope": "hop2_window",
                            "per_request": 1.0, "tol": 0.002}))
        self.assertTrue(ok({"stat": "x.ssl.handshake", "scope": "hop2_window", "equals": 0, "tol_abs": 0}))
        self.assertTrue(ok({"stat": "x.ssl.handshake", "scope": "hop2_leg", "min": 512}))
        self.assertFalse(ok({"stat": "x.ssl.handshake", "scope": "hop2_leg", "min": 601}))
        self.assertTrue(ok({"stat": "y.ssl.handshake", "scope": "hop2_leg", "absent": True}))
        self.assertEqual(evidence.validate_items([{"stat": "a", "scope": "hop2_leg", "min": 1}]), [])
        # a one-hop leg has no hop-2 snapshot: nothing of that scope passes, absent included
        one = {"responses_raw": 100}
        self.assertFalse(evidence.check_item(one, {"stat": "a", "scope": "hop2_leg", "absent": True})["ok"])


class RunConfigsTest(unittest.TestCase):
    def test_every_config_validates(self):
        for fn in sorted(os.listdir(CFG)):
            e = experiment.load(os.path.join(CFG, fn))
            self.assertEqual(experiment.validate(e, allow_short=True), [], fn)
            self.assertEqual({a["source_sha256"] for a in e["arms"]},
                             {"1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc"}, fn)
            for a in e["arms"]:
                self.assertTrue(a.get("evidence"), (fn, a["name"]))
                self.assertEqual(evidence.validate_items(a["evidence"], [x["name"] for x in e["arms"]]), [],
                                 (fn, a["name"]))
            if fn.startswith("smoke-"):
                self.assertEqual((e["order"], e["rounds"], e.get("evidence_mode")), ("fixed", 1, "record"))
            else:
                self.assertEqual(e["order"], "williams")
                self.assertEqual(e["rounds"] % experiment.order_period(e), 0)

    def test_aa_twins_match(self):
        for fn, a, b in (("f1-upstream.json", "h1", "h1-A2"), ("f2-grpc.json", "grpc", "grpc-A2"),
                         ("f3-mtls.json", "pair", "pair-A2")):
            e = experiment.load(os.path.join(CFG, fn))
            x, y = [[z for z in e["arms"] if z["name"] == n][0] for n in (a, b)]
            self.assertEqual(x.get("settings"), y.get("settings"), fn)
            self.assertEqual(x["evidence"], y["evidence"], fn)

    def test_arms_and_rounds(self):
        legs = {}
        for fn in ("f1-upstream.json", "f2-grpc.json", "f3-mtls.json"):
            e = experiment.load(os.path.join(CFG, fn))
            legs[fn] = len(e["arms"]) * e["rounds"]
        self.assertEqual(legs, {"f1-upstream.json": 36, "f2-grpc.json": 32, "f3-mtls.json": 32})

    def test_runtime_structure_same_in_f1_f2(self):
        for fn in ("f1-upstream.json", "f2-grpc.json"):
            e = experiment.load(os.path.join(CFG, fn))
            self.assertEqual({tuple(experiment.arm_settings(a)["runtime"]) for a in e["arms"]}, {(ec.OGHTTP2_KEY,)})
            og = {a["name"] for a in e["arms"] if experiment.arm_settings(a)["runtime"][ec.OGHTTP2_KEY]}
            self.assertEqual(og, {"h2c-og"} if fn.startswith("f1") else {"grpc-og"})

    def test_everything_binds_to_loopback(self):
        """Every Envoy listener, admin and cluster address, and every origin server, is on 127.0.0.x."""
        import re
        for fn in sorted(os.listdir(CFG)):
            e = experiment.load(os.path.join(CFG, fn))
            with tempfile.TemporaryDirectory() as d:
                _, texts, _ = experiment.prepare_bootstraps(e, d, make_certs=False)
            addrs = []

            def walk(x):
                if isinstance(x, dict):
                    if "address" in x and "port_value" in x:
                        addrs.append(str(x["address"]))
                    for v in x.values():
                        walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
            for t in texts.values():
                walk(json.loads(t))
            o = e["origin"]
            conf = ec.nginx_conf(o["port"], 8, stub_status=True, h2c_port=o.get("h2c_port"), tls_port=o.get("tls_port"),
                                 tls_cert=o.get("tls_cert"), grpc=ec.grpc_files(e["shapes"]))
            addrs += [x.split(":")[0] for x in re.findall(r"listen ([^ ;]+)", conf)]
            self.assertTrue(addrs, fn)
            self.assertEqual([a for a in addrs if not a.startswith("127.")], [], fn)
            self.assertNotIn("include", conf)  # no stock conf.d server (the image's default listens on all addresses)

    def test_no_body_file_variant(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("w3f_make", os.path.join(ROOT, "examples", "wave3f", "make.py"))
        mk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mk)
        c = mk.f2(False, body_file=False)
        self.assertEqual([a["name"] for a in c["arms"]], ["grpc", "grpc-A2", "grpc-og"])
        self.assertEqual(c["rounds"], 6)
        self.assertIn("--request-body-size", c["shapes"][0]["client_extra_args"])
        self.assertNotIn("request_body_file", c["shapes"][0])


if __name__ == "__main__":
    unittest.main()


class OriginStartTest(unittest.TestCase):
    """Origin.start with docker and the port probes faked: the gRPC body's hash and the new ports reach the
    metadata (the box's first F2 smoke died here on a local `import hashlib` shadowing the module one)."""

    def test_start_with_grpc_h2c_tls(self):
        from unittest import mock
        from epl import origin as om
        e = experiment.load(os.path.join(CFG, "f2-grpc.json"))
        calls = []

        def run(args, **kw):
            calls.append(args)
            return mock.Mock(returncode=0, stdout="cid0123456789abcdef\n", stderr="")
        with tempfile.TemporaryDirectory() as d, mock.patch.object(om.subprocess, "run", run), \
                mock.patch.object(om.sysprobe, "port_open", lambda *a: False), \
                mock.patch.object(om.sysprobe, "wait_port", lambda *a: True), \
                mock.patch.object(om, "side_service", lambda *a: None), mock.patch.object(om.time, "sleep", lambda s: None):
            o = om.Origin(e["origin"], "32-39", e["shapes"], d, lambda m: None)
            meta = o.start()
            with open(os.path.join(d, "origin", "www", "_grpc", "g.grpc"), "rb") as f:
                body = f.read()
        import hashlib
        self.assertEqual(meta["grpc_sha256"], {"/epl.bench.Bench/Unary": hashlib.sha256(ec.grpc_frame(4096)).hexdigest()})
        self.assertEqual(body, ec.grpc_frame(4096))
        self.assertEqual((meta["h2c_port"], meta["tls_port"]), (8096, 8097))
        run_args = [a for a in calls if a[:2] == ["docker", "run"]][0]
        self.assertIn("%s:/certs:ro" % os.path.join(d, "certs"), run_args)
