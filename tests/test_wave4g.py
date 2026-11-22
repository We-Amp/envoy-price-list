"""Wave 4 track G: the HTTP/3 listener setting, the client's certificate-directory placeholder, the UDP kernel
counters, and the run configs (arms differ only as named, loopback only, Williams balance, evidence)."""
import base64
import copy
import json
import math
import os
import tempfile
import unittest

from epl import envoy_config as ec
from epl import evidence, experiment, leg, sysprobe

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG = os.path.join(ROOT, "examples", "wave4g", "configs")
SHAPE = [{"name": "s", "kind": "proxied", "path": "/s", "body_bytes": 4096, "rps": 2000}]
ENV = {"listener_port": 10110, "admin_port": 9921, "codec_type": "HTTP2", "tls": {"cert": "ecdsa-p256-san"}}


def boot(**settings):
    return ec.bootstrap(SHAPE, dict(ENV, **settings), 8092, "/certs")


def quic_l(b):
    ls = [x for x in b["static_resources"]["listeners"] if x["name"] == "listener_quic"]
    return ls[0] if ls else None


def load(fn):
    return experiment.load(os.path.join(CFG, fn))


def bootstraps(fn):
    exp = load(fn)
    with tempfile.TemporaryDirectory() as d:
        _, texts, _ = experiment.prepare_bootstraps(exp, d, make_certs=False)
        return exp, {k: json.loads(v.replace(d, "RUN")) for k, v in texts.items()}


def diff_paths(a, b, p=""):
    """Dotted paths where two JSON values differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff_paths(a.get(k, "<none>"), b.get(k, "<none>"), p + "." + k)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff_paths(x, y, p + "[%d]" % i)
        return out
    return [] if a == b else [p]


class QuicListenerTest(unittest.TestCase):
    def test_absent_by_default(self):
        self.assertIsNone(quic_l(boot()))
        self.assertEqual(len(boot()["static_resources"]["listeners"]), 1)

    def test_shape(self):
        b = boot(quic={})
        tcp, q = b["static_resources"]["listeners"][0], quic_l(b)
        sa = q["address"]["socket_address"]
        self.assertEqual((sa["protocol"], sa["address"], sa["port_value"]), ("UDP", "127.0.0.1", 10110))
        self.assertEqual(q["udp_listener_config"], {"quic_options": {}})  # Envoy's defaults: GSO when supported
        ts = q["filter_chains"][0]["transport_socket"]
        self.assertEqual(ts["name"], "envoy.transport_sockets.quic")
        self.assertEqual(ts["typed_config"]["@type"], ec.QUIC_DTS)
        self.assertNotIn("enable_resumption", ts["typed_config"])
        self.assertNotIn("enable_early_data", ts["typed_config"])
        cert = ts["typed_config"]["downstream_tls_context"]["common_tls_context"]["tls_certificates"][0]
        self.assertEqual(cert["certificate_chain"]["filename"], "/certs/ecdsa-p256-san.crt")
        h3 = q["filter_chains"][0]["filters"][0]["typed_config"]
        h2 = tcp["filter_chains"][0]["filters"][0]["typed_config"]
        self.assertEqual(h3["codec_type"], "HTTP3")
        self.assertEqual(h3["http3_protocol_options"], {})
        # same routes, filters and stat prefix as the TCP listener (responses counted in one place)
        for k in ("route_config", "http_filters", "stat_prefix"):
            self.assertEqual(h3[k], h2[k])
        # the TCP listener is unchanged by the setting
        self.assertEqual(tcp, boot()["static_resources"]["listeners"][0])
        # QUIC refuses a connection balancer: none on the UDP listener
        self.assertNotIn("connection_balance_config", q)

    def test_gso_off_and_gro(self):
        q = quic_l(boot(quic={"gso": False, "prefer_gro": True}))
        w = q["udp_listener_config"]["udp_packet_packet_writer_config"]
        self.assertEqual(w["name"], "envoy.udp_packet_writer.default")
        self.assertEqual(w["typed_config"]["@type"], ec.UDP_DEFAULT_WRITER)
        self.assertEqual(q["udp_listener_config"]["downstream_socket_config"], {"prefer_gro": True})
        self.assertNotIn("udp_packet_packet_writer_config", quic_l(boot(quic={"gso": True}))["udp_listener_config"])

    def test_resumption_and_ticket_keys(self):
        ts = quic_l(boot(quic={"resumption": False, "early_data": False}))["filter_chains"][0]["transport_socket"]
        self.assertIs(ts["typed_config"]["enable_resumption"], False)
        self.assertIs(ts["typed_config"]["enable_early_data"], False)
        ts = quic_l(boot(quic={"ticket_keys": True}))["filter_chains"][0]["transport_socket"]
        k = ts["typed_config"]["downstream_tls_context"]["session_ticket_keys"]["keys"]
        self.assertEqual(len(k), 1)
        self.assertEqual(len(base64.b64decode(k[0]["inline_bytes"])), 80)  # Envoy requires 80 bytes
        # the TCP listener's TLS context gets no ticket key
        tcp = boot(quic={"ticket_keys": True})["static_resources"]["listeners"][0]
        self.assertNotIn("session_ticket_keys", tcp["filter_chains"][0]["transport_socket"]["typed_config"])

    def test_errors(self):
        for bad in ({"gzo": True}, {"gso": "yes"}, {"ticket_keys": False}, {"resumption": False, "early_data": True}):
            with self.assertRaises(ValueError):
                boot(quic=bad)
        with self.assertRaises(ValueError):
            ec.bootstrap(SHAPE, dict(ENV, tls=None, quic={}), 8092, "/certs")
        with self.assertRaises(ValueError):
            boot(quic={}, tls={"cert": "ecdsa-p256", "resumption": False})
        with self.assertRaises(ValueError):
            boot(quic={}, listener_fanout=4)

    def test_setting_documented(self):
        self.assertIn("quic", ec.SETTINGS)


class CertDirTest(unittest.TestCase):
    def test_sub(self):
        self.assertIsNone(leg.sub_cert_dir(None, "/r"))
        self.assertEqual(leg.sub_cert_dir(["a", '{"f":"{cert_dir}/x.crt"}'], "/r"), ["a", '{"f":"/r/certs/x.crt"}'])


class KernelUdpTest(unittest.TestCase):
    SNMP = ("Udp: InDatagrams NoPorts InErrors OutDatagrams RcvbufErrors SndbufErrors InCsumErrors IgnoredMulti "
            "MemErrors\nUdp: %d 1 0 %d 0 0 0 5 0\n")

    def test_delta(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "net"))
            for i, (inn, out) in enumerate(((100, 200), (150, 290))):
                with open(os.path.join(d, "net", "snmp"), "w") as f:
                    f.write(self.SNMP % (inn, out))
                if i == 0:
                    a = sysprobe.kernel_net(d)
            b = sysprobe.kernel_net(d)
        dd = sysprobe.kernel_net_delta(a, b)["d"]
        self.assertEqual((dd["UdpInDatagrams"], dd["UdpOutDatagrams"], dd["UdpRcvbufErrors"]), (50, 90, 0))
        self.assertNotIn("InDatagrams", dd)


class ConfigsTest(unittest.TestCase):
    def test_load_and_plan(self):
        for fn in ("g1-proto.json", "g2-resume.json", "smoke-g1-proto.json", "smoke-g2-resume.json"):
            exp = load(fn)
            self.assertEqual(experiment.validate(exp, allow_short=True), [], fn)

    def test_g1_arms_differ_only_as_named(self):
        exp, bs = bootstraps("g1-proto.json")
        # one Envoy shape for the protocol arms: the client alone picks HTTP/2 or HTTP/3
        self.assertEqual(bs["h3"], bs["h3-A2"])
        self.assertEqual(bs["h2tls"], bs["h3"])
        self.assertEqual(diff_paths(bs["h3"], bs["h3-nogso"]),
                         [".static_resources.listeners[1].udp_listener_config.udp_packet_packet_writer_config"])
        arms = {a["name"]: a for a in exp["arms"]}
        self.assertEqual(arms["h3"]["client"], arms["h3-A2"]["client"])
        self.assertEqual(arms["h3"]["client"], arms["h3-nogso"]["client"])
        # the relaxed worker-share gate is on the keep-alive HTTP/3 arms only
        self.assertNotIn("max_worker_share_factor", arms["h2tls"]["validity"])
        for n in ("h3", "h3-A2", "h3-nogso"):
            self.assertEqual(arms[n]["validity"]["max_worker_share_factor"], 2.0)
            self.assertIsNone(arms[n]["validity"]["min_worker_share_factor"])
        x2, x3 = arms["h2tls"]["client"]["extra_args"], arms["h3"]["client"]["extra_args"]
        self.assertEqual(x2[:2], ["--protocol", "http2"])
        self.assertEqual(x3[:2], ["--protocol", "http3"])
        self.assertIn("{cert_dir}/ecdsa-p256-san.crt", x3[3])
        self.assertEqual(json.loads(x3[3])["typed_config"]["upstream_tls_context"]["sni"], "bench.local")
        self.assertEqual(arms["h2tls"]["client"]["base_args"], arms["h3"]["client"]["base_args"])
        self.assertNotIn("--max-requests-per-connection", x2 + x3)
        self.assertEqual({s["rps"] for s in exp["shapes"]}, {2000})

    def test_g2_arms_differ_only_as_named(self):
        exp, bs = bootstraps("smoke-g2-resume.json")
        self.assertEqual(bs["h3r"], bs["h3r-A2"])
        self.assertEqual(bs["h3r"], bs["h3-ka"])
        d = diff_paths(bs["h3r"], bs["h3r-tk"])
        self.assertEqual(len(d), 2, d)
        self.assertTrue(any("quic_session_ticket_support" in p for p in d))
        self.assertTrue(any(p.endswith("downstream_tls_context.session_ticket_keys") for p in d))
        d = diff_paths(bs["h3r"], bs["h3r-nores"])
        self.assertEqual(sorted(p.rsplit(".", 1)[1] for p in d), ["enable_early_data", "enable_resumption"])
        arms = {a["name"]: a for a in exp["arms"]}
        for n in ("h3r", "h3r-A2", "h3r-tk", "h3r-nores"):
            self.assertEqual(arms[n]["client"], arms["h3r"]["client"])
            self.assertIn("--max-requests-per-connection", arms[n]["client"]["extra_args"])
            self.assertNotIn("--prefetch-connections", arms[n]["client"]["base_args"])
        self.assertIn("--prefetch-connections", arms["h3-ka"]["client"]["base_args"])
        self.assertNotIn("max_worker_share_factor", arms["h3r"]["validity"])
        self.assertEqual(arms["h3-ka"]["validity"]["max_worker_share_factor"], 2.0)
        # the calibration arm is smoke-only
        self.assertNotIn("h3r-nores", [a["name"] for a in load("g2-resume.json")["arms"]])

    def test_everything_binds_to_loopback(self):
        for fn in ("g1-proto.json", "smoke-g2-resume.json"):
            _, bs = bootstraps(fn)
            n = 0
            for b in bs.values():
                stack = [b]
                while stack:
                    x = stack.pop()
                    if isinstance(x, dict):
                        if "socket_address" in x:
                            self.assertEqual(x["socket_address"]["address"], "127.0.0.1")
                            n += 1
                        stack.extend(x.values())
                    elif isinstance(x, list):
                        stack.extend(x)
            self.assertGreater(n, 0)

    def test_williams_balance(self):
        for fn in ("g1-proto.json", "g2-resume.json"):
            exp = load(fn)
            order = [[a["name"] for a in experiment.round_order(exp, r)] for r in range(1, exp["rounds"] + 1)]
            arms = [a["name"] for a in exp["arms"]]
            pos = {(a, i): 0 for a in arms for i in range(len(arms))}
            pairs = {}
            for r in order:
                for i, a in enumerate(r):
                    pos[(a, i)] += 1
                for x, y in zip(r, r[1:]):
                    pairs[(x, y)] = pairs.get((x, y), 0) + 1
            self.assertEqual(set(pos.values()), {2}, fn)
            self.assertEqual(len(pairs), 12)
            self.assertEqual(set(pairs.values()), {2}, fn)

    def test_evidence_on_a_synthetic_leg(self):
        exp = load("g1-proto.json")
        arms = {a["name"]: a for a in exp["arms"]}
        L = "listener.127.0.0.1_10110."
        kn = {"d": {"UdpRcvbufErrors": 0, "UdpSndbufErrors": 0, "UdpInErrors": 0, "ListenOverflows": 0,
                    "ListenDrops": 0}}
        m = {"shape": "s", "responses_raw": 40000, "kernel_net": kn,
             "sut_stats_window": {"cluster.origin.upstream_rq_2xx": 40000, "cluster.origin.upstream_cx_total": 0,
                                  L + "downstream_cx_total": 0, L + "total_bytes_sent": 0},
             "sut_stats_leg_end": {"http.ingress_http.downstream_rq_completed": 50000,
                                   "http.ingress_http.downstream_cx_http3_total": 32,
                                   "http.ingress_http.downstream_cx_http2_total": 0, L + "total_bytes_sent": 0}}
        self.assertTrue(evidence.evaluate(m, arms["h3"]["evidence"])["ok"],
                        evidence.evaluate(m, arms["h3"]["evidence"])["failed"])
        # the nogso arm must not have the GSO writer
        self.assertFalse(evidence.evaluate(m, arms["h3-nogso"]["evidence"])["ok"])
        m2 = copy.deepcopy(m)
        del m2["sut_stats_leg_end"][L + "total_bytes_sent"]
        self.assertTrue(evidence.evaluate(m2, arms["h3-nogso"]["evidence"])["ok"])
        # an HTTP/2 connection on an HTTP/3 arm fails it
        m3 = copy.deepcopy(m)
        m3["sut_stats_leg_end"]["http.ingress_http.downstream_cx_http2_total"] = 1
        self.assertFalse(evidence.evaluate(m3, arms["h3"]["evidence"])["ok"])
        # the HTTP/2 arm passes on the same leg shape with HTTP/2 counters and 32 TLS 1.3 connections
        m5 = copy.deepcopy(m2)
        m5["sut_stats_leg_end"].update({"http.ingress_http.downstream_cx_http3_total": 0,
                                        "http.ingress_http.downstream_cx_http2_total": 32,
                                        L + "ssl.versions.TLSv1.3": 32, L + "total_bytes_sent": 0})
        m5["sut_stats_window"][L + "ssl.handshake"] = 0
        self.assertTrue(evidence.evaluate(m5, arms["h2tls"]["evidence"])["ok"],
                        evidence.evaluate(m5, arms["h2tls"]["evidence"])["failed"])
        # a UDP receive-buffer drop anywhere on the box fails it
        m4 = copy.deepcopy(m)
        m4["kernel_net"]["d"]["UdpRcvbufErrors"] = 3
        self.assertFalse(evidence.evaluate(m4, arms["h3"]["evidence"])["ok"])



class TableEffectIsAPercentTest(unittest.TestCase):
    """The table's `effect %` is the log ratio turned back into a percent change, not 100 ln(ratio)."""

    def load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("w4g_table", os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "wave4g", "table.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_conversion(self):
        t = self.load()
        self.assertAlmostEqual(t.pct(100.0 * math.log(1.748)), 74.8, places=9)
        self.assertAlmostEqual(t.pct(0.0), 0.0)

    def test_the_published_row(self):
        # HTTP/3 vs HTTP/2 over TLS in g1-proto: log-% +55.83 [+54.33, +57.33] is +74.8% [+72.2, +77.4]
        t = self.load()
        self.assertEqual("%+.1f" % t.pct(55.83), "+74.8")
        self.assertEqual("%+.1f" % t.pct(54.33), "+72.2")
        self.assertEqual("%+.1f" % t.pct(57.33), "+77.4")

    def test_the_rendered_row_when_the_data_is_there(self):
        run = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "waves", "http3", "wave4g", "g1-proto")
        if not os.path.isfile(os.path.join(run, "legs.jsonl")):
            self.skipTest("data/waves/http3 not fetched")
        _, _, rows = self.load().rows(run)
        r = [o for o in rows if o["row"] == "HTTP/3 vs HTTP/2 over TLS"][0]
        self.assertEqual("%+.1f [%+.1f, %+.1f]" % (r["effect_pct"], r["interval"][0], r["interval"][1]),
                         "+74.8 [+72.2, +77.4]")
        self.assertEqual("%+.2f" % r["log_pct"], "+55.83")

if __name__ == "__main__":
    unittest.main()


class ServerCloseTest(unittest.TestCase):
    def test_g2s_server_closes_client_sets_no_limit(self):
        exp, bs = bootstraps("smoke-g2s-resume.json")
        arms = {a["name"]: a for a in exp["arms"]}
        for n in ("h3r", "h3r-A2", "h3r-tk", "h3r-nores"):
            self.assertNotIn("--max-requests-per-connection", arms[n]["client"]["extra_args"])
            q = quic_l(bs[n])["filter_chains"][0]["filters"][0]["typed_config"]
            self.assertEqual(q["common_http_protocol_options"]["max_requests_per_connection"], 10)
        self.assertNotIn("common_http_protocol_options",
                         quic_l(bs["h3-ka"])["filter_chains"][0]["filters"][0]["typed_config"])
        self.assertEqual(bs["h3r"], bs["h3r-A2"])
        self.assertEqual(len(diff_paths(bs["h3r"], bs["h3r-tk"])), 2)


class WarmLimitTest(unittest.TestCase):
    def test_reconnect_arms_only(self):
        for fn in ("g2s-resume.json", "smoke-g2s-resume.json", "g1-proto.json"):
            for a in load(fn)["arms"]:
                w = [it for it in a["evidence"] if it["stat"] == "cluster.origin.upstream_cx_total"][0]
                rc = bool((a["settings"] or {}).get("downstream_keepalive"))
                self.assertEqual(w["max"], 0.005 if rc else 0.001, (fn, a["name"]))
