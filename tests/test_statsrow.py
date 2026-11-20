import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from epl import envoy_config, evidence, leg, origin, statsrow, validity

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 1600}]
IDLE = [{"name": "idle-10k", "path": "/idle", "kind": "idle", "rps": 0}]
E = {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True}


def series(pattern, dt=0.02):
    """[(t, ns)] from a list of per-interval busy fractions."""
    out, t, ns = [(0.0, 0)], 0.0, 0
    for f in pattern:
        t += dt
        ns += int(f * dt * 1e9)
        out.append((round(t, 6), ns))
    return out


class BurstTest(unittest.TestCase):
    def test_bursts_and_periods(self):
        # 1 s period: 3 busy samples (60 ms at 100%) every 50 samples, 1% baseline
        pat = []
        for k in range(5):
            pat += [1.0, 1.0, 1.0] + [0.01] * 47
        s = series(pat)
        b = statsrow.find_bursts(s)
        self.assertEqual(len(b), 5)
        self.assertAlmostEqual(b[0]["start_t"], 0.0)
        self.assertAlmostEqual(b[1]["start_t"], 1.0)
        m = statsrow.summarize_main(s, b, 5.0)
        self.assertEqual(m["periods"], 4)
        self.assertAlmostEqual(m["period_s"], 1.0)
        # per period: 60 ms of burst + 47 x 0.2 ms of baseline
        self.assertAlmostEqual(m["run_ms_per_period"], 60 + 47 * 0.2, places=3)
        self.assertAlmostEqual(m["burst_run_ms_max"], 60, places=3)
        self.assertAlmostEqual(m["stall_ms_max"], 60, places=3)

    def test_sub_bursts_across_the_merge_are_joined(self):
        pat = [0.01] * 10 + [1.0, 1.0] + [0.01] * 2 + [1.0] + [0.01] * 30
        b = statsrow.find_bursts(series(pat), join_gap_s=0.1)
        self.assertEqual(len(b), 1)
        self.assertAlmostEqual(b[0]["wall_s"], 0.1, places=6)
        self.assertEqual(len(statsrow.find_bursts(series(pat), join_gap_s=0.01)), 2)

    def test_idle_series_has_no_burst(self):
        s = series([0.01] * 1000)
        self.assertEqual(statsrow.find_bursts(s), [])
        m = statsrow.summarize_main(s, [], 20.0)
        self.assertAlmostEqual(m["run_ms_per_s"], 10.0, places=3)
        self.assertNotIn("run_ms_per_period", m)

    def test_expected_flushes(self):
        # flush starts are one interval apart whatever the flush takes (measured on the bench box)
        self.assertEqual(statsrow.expected_flushes(20.0, 1.0, 0.74), 20)
        self.assertTrue(statsrow.saturated(999.8))
        self.assertFalse(statsrow.saturated(738.7))
        self.assertEqual(statsrow.expected_flushes(20.0, None, 0.05), 0)


SNMP = ("Udp: InDatagrams NoPorts InErrors OutDatagrams RcvbufErrors SndbufErrors InCsumErrors IgnoredMulti MemErrors\n"
        "Udp: %d 0 %d 900 %d 0 0 0 0\n")
UDP = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode ref pointer drops\n"
       " 1234: 0100007F:1FBD 00000000:0000 07 00000000:00000400 00:00000000 00000000  1000        0 99 2 0000 %d\n"
       " 1235: 00000000:0044 00000000:0000 07 00000000:00000000 00:00000000 00000000     0        0 98 2 0000 7\n")


class UdpCountersTest(unittest.TestCase):
    def test_parse_and_window(self):
        a = statsrow.parse_snmp_udp(SNMP % (1000, 3, 10))
        self.assertEqual((a["InDatagrams"], a["RcvbufErrors"], a["InErrors"]), (1000, 10, 3))
        sock = statsrow.parse_udp_socket(UDP % 5, 8125)
        self.assertEqual(sock, {"rx_queue": 1024, "drops": 5})
        self.assertIsNone(statsrow.parse_udp_socket(UDP % 5, 9999))
        c0 = {"snmp": a, "sock": sock}
        c1 = {"snmp": statsrow.parse_snmp_udp(SNMP % (201000, 3, 1010)), "sock": statsrow.parse_udp_socket(UDP % 1005, 8125)}
        w = statsrow.udp_window(c0, c1, 20, used_lines=10500)
        self.assertEqual((w["delivered"], w["dropped"], w["sent"]), (200000, 1000, 201000))
        self.assertAlmostEqual(w["drop_share"], 1000 / 201000)
        self.assertAlmostEqual(w["sent_per_flush"], 10050)
        self.assertIn("error", statsrow.udp_window({}, {}, 1))


class StatsTextTest(unittest.TestCase):
    def test_parse(self):
        txt = ("cluster.a.upstream_rq_total: 4\nserver.uptime: 12\nserver.version: \"1.40.2\"\n"
               "cluster.a.upstream_rq_time: P0(nan,1) P25(nan,1.025)\nhttp.x.downstream_rq_time: No recorded values\n"
               "server.memory_allocated: 123456\n")
        p = statsrow.parse_stats_text(txt)
        self.assertEqual((p["total"], p["histograms"], p["text_readouts"]), (6, 2, 1))
        self.assertEqual(p["numeric"]["server.uptime"], 12)
        names = ["a", "b"]
        self.assertEqual(statsrow.generated_sum(p["numeric"], names, "upstream_rq_total"), 4)

    def test_limits_and_status(self):
        lim = ("Limit                     Soft Limit           Hard Limit           Units\n"
               "Max open files            48096                1048576              files\n")
        self.assertEqual(statsrow.parse_limits(lim), (48096, 1048576))
        self.assertEqual(statsrow.parse_limits("Max open files unlimited unlimited files"), (None, None))
        st = "Name:\tenvoy\nVmHWM:\t  204800 kB\nVmRSS:\t  102400 kB\n"
        self.assertEqual(statsrow.parse_status_kb(st, "VmRSS"), 102400)
        self.assertEqual(statsrow.parse_status_kb(st, "VmHWM"), 204800)


class GeneratorAndSettingsTest(unittest.TestCase):
    def test_names(self):
        a = envoy_config.stats_cluster_names(1000, 31)
        self.assertEqual(a, envoy_config.stats_cluster_names(1000, 31))
        self.assertNotEqual(a, envoy_config.stats_cluster_names(1000, 32))
        self.assertEqual(len(set(a)), 1000)
        for n in a:
            self.assertTrue(n.endswith(".cluster.test"))
            full = "cluster.%s.upstream_rq_total" % n
            self.assertTrue(45 <= len(full) <= 75, full)

    def test_bootstrap(self):
        b = envoy_config.bootstrap(IDLE, dict(E, stats_clusters={"count": 3, "seed": 31}), 8092)
        cl = b["static_resources"]["clusters"]
        self.assertEqual(len(cl), 4)
        gen = cl[1]
        self.assertEqual(gen["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"]
                         ["socket_address"]["port_value"], 8092)
        opts = gen["typed_extension_protocol_options"]["envoy.extensions.upstreams.http.v3.HttpProtocolOptions"]
        self.assertEqual(opts["common_http_protocol_options"], {"idle_timeout": "1s"})
        routes = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"][
            "route_config"]["virtual_hosts"][0]["routes"]
        self.assertEqual(routes, [{"match": {"path": "/epl-prime"}, "route": {"cluster_header": "x-epl-cluster"}}])
        self.assertNotIn("stats_flush_interval", b)
        b = envoy_config.bootstrap(IDLE, dict(E, stats_flush={"interval_s": 1}), 8092)
        self.assertEqual(b["stats_flush_interval"], "1s")
        b = envoy_config.bootstrap(IDLE, dict(E, stats_flush={"on_admin": True}), 8092)
        self.assertTrue(b["stats_flush_on_admin"])
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(IDLE, dict(E, stats_flush={"on_admin": True}, stats_sink={"kind": "statsd"},
                                              stats_sink_port=8125), 8092)

    def test_sinks(self):
        b = envoy_config.bootstrap(IDLE, dict(E, stats_sink={"kind": "statsd"}, stats_sink_port=8125), 8092)
        sk = b["stats_sinks"][0]
        self.assertEqual(sk["name"], "envoy.stat_sinks.statsd")
        self.assertEqual(sk["typed_config"]["address"]["socket_address"],
                         {"protocol": "UDP", "address": "127.0.0.1", "port_value": 8125})
        b = envoy_config.bootstrap(IDLE, dict(E, stats_sink={"kind": "dog_statsd", "max_bytes_per_datagram": 1432},
                                              stats_sink_port=8125), 8092)
        self.assertEqual(b["stats_sinks"][0]["typed_config"]["max_bytes_per_datagram"], 1432)
        b = envoy_config.bootstrap(IDLE, dict(E, stats_sink={"kind": "otlp", "max_data_points_per_request": 5000},
                                              collector_port=4317), 8092)
        tc = b["stats_sinks"][0]["typed_config"]
        self.assertEqual(tc["grpc_service"], {"envoy_grpc": {"cluster_name": "otel_collector"}})
        self.assertIn("otel_collector", [c["name"] for c in b["static_resources"]["clusters"]])
        b = envoy_config.bootstrap(S, dict(E, stats_reject_all=True), 8092)
        self.assertEqual(b["stats_config"], {"stats_matcher": {"reject_all": True}})
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(IDLE, dict(E, stats_sink={"kind": "graphite"}), 8092)

    def test_origin_and_collector_options(self):
        self.assertIn("events { worker_connections 65536; }",
                      envoy_config.nginx_conf(8092, 8, worker_connections=65536, worker_rlimit_nofile=200000))
        self.assertIn("worker_rlimit_nofile 200000;", envoy_config.nginx_conf(8092, 8, worker_rlimit_nofile=200000))
        c = origin.collector_conf(4317, 8888, metrics=True)
        self.assertIn("    metrics:\n      receivers: [otlp]", c)
        self.assertEqual(origin.collector_conf(4317, 8888), origin.collector_conf(4317, 8888, metrics=False))
        self.assertEqual(origin.parse_collector_metrics(
            'otelcol_receiver_accepted_metric_points{receiver="otlp"} 52000\n'
            'otelcol_receiver_refused_metric_points{receiver="otlp"} 0\n'),
            {"accepted_metric_points": 52000, "refused_metric_points": 0})

    def test_nofile_and_prime_flags(self):
        self.assertEqual(leg.nofile_for({"stats_clusters": {"count": 10000}}), 4 * 10000 + 4096 + 1024)
        self.assertIsNone(leg.nofile_for({}))
        self.assertEqual(leg.nofile_for({}, {"envoy": {"nofile": 5000}}), 5000)
        self.assertTrue(leg._primes({}, {}))
        self.assertFalse(leg._primes({"prime": False}, {}))

    def test_per_thread_perf(self):
        txt = ("envoy-100,5000,,cycles,1000,100.00,,\nwrk:worker_0-101,7000,,cycles,1000,100.00,,\n"
               "wrk:worker_0-101,3000,,instructions:u,1000,99.50,,\n")
        pt = leg.parse_perf_per_thread(txt)
        self.assertEqual(pt[101]["comm"], "wrk:worker_0")
        tot, run = leg.perf_totals(pt)
        self.assertEqual(tot["cycles"], 12000)
        self.assertEqual(run["instructions:u"], 99.5)


def idle_leg(**over):
    m = {"idle_leg": True, "idle_ok": True, "preflight_ok": True, "pinning_ok": True, "perf_ok": True,
         "main_tid_ok": True, "sut_foreign_cpus": 0.0, "sut_sibling_cpus": 0.0, "envoy_exit": 0,
         "perf_min_running_pct": 100.0, "main": {"samples": 1000, "bursts": 19}}
    m.update(over)
    return m


class IdleValidityTest(unittest.TestCase):
    def test_idle_leg_has_no_request_gates(self):
        self.assertTrue(validity.verdict(idle_leg())["valid"])

    def test_idle_gates(self):
        for mut, needle in (({"main_tid_ok": False}, "main thread"), ({"perf_ok": False}, "perf"),
                            ({"sut_foreign_cpus": 0.2}, "other tasks"), ({"error": "boom"}, "boom"),
                            ({"perf_min_running_pct": 80.0}, "multiplexed"),
                            ({"side_services": {"udpsink": {"busy_of_set": 0.7, "cpuset_ok": True,
                                                            "pids_ok": True}}}, "udpsink"),
                            ({"evidence": {"ok": False, "gate": True, "failed": ["x: y"]}}, "evidence")):
            v = validity.verdict(idle_leg(**mut))
            self.assertFalse(v["valid"], needle)
            self.assertTrue(any(needle in r for r in v["reasons"]), (needle, v["reasons"]))


class UdpSinkTest(unittest.TestCase):
    def test_drain_and_record(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "sink.json")
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = 0
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.bind(("127.0.0.1", 0))
        port = u.getsockname()[1]
        u.close()
        s.close()
        p = subprocess.Popen([sys.executable, os.path.join(HERE, "epl", "udpsink.py"), "--port", str(port),
                              "--rcvbuf", "1048576", "--out", out])
        try:
            for _ in range(100):
                if os.path.exists(out + ".ready"):
                    break
                time.sleep(0.05)
            c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for i in range(50):
                c.sendto(b"envoy.cluster.x.upstream_rq_total:%d|c" % i, ("127.0.0.1", port))
            c.sendto(b"envoy.server.uptime:42|g", ("127.0.0.1", port))
            c.sendto(b"a:1|c\nb:2|c\n", ("127.0.0.1", port))
            time.sleep(0.3)
        finally:
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=10)
        with open(out) as f:
            r = json.load(f)
        self.assertEqual(r["datagrams"], 52)
        self.assertEqual(r["newlines"], 2)
        self.assertEqual(r["uptime_samples"][0][1], 42.0)
        self.assertGreater(r["rcvbuf_granted"], 0)


class FieldEvidenceTest(unittest.TestCase):
    def test_field_ratio_and_ref(self):
        m = {"shape": "idle-1m", "udp": {"sent_per_flush": 10100}, "used_cg_lines": 10050,
             "main": {"bursts": 0, "burst_count_error": 1}}
        it = {"stat": "udp.sent_per_flush", "scope": "field", "per": "field:used_cg_lines", "per_request": 1.0,
              "tol": 0.01}
        self.assertTrue(evidence.check_item(m, it)["ok"])
        self.assertTrue(evidence.check_item(m, {"stat": "main.bursts", "scope": "field", "max": 0})["ok"])
        it = {"stat": "udp.sent_per_flush", "scope": "field", "ref": {"arm": "self"}, "tol": 0.01}
        frozen, problems = evidence.freeze({"x": [it]}, [dict(m, arm="x", verdict={"valid": True})])
        self.assertEqual(problems, [])
        self.assertAlmostEqual(frozen["x"][0]["per_request"], 10100)
        self.assertTrue(evidence.evaluate(dict(m, udp={"sent_per_flush": 10150}), frozen["x"])["ok"])
        self.assertFalse(evidence.evaluate(dict(m, udp={"sent_per_flush": 10300}), frozen["x"])["ok"])


if __name__ == "__main__":
    unittest.main()


class SpanFlushTest(unittest.TestCase):
    """T5: the flushes between two quiescent points are counted whole, and the collector is read
    until it settles."""

    def test_span_flushes(self):
        from epl import statsrow as sr
        bursts = [{"start_t": a, "end_t": b, "wall_s": b - a, "run_ns": int((b - a) * 1e9)}
                  for a, b in ((0.5, 0.8), (1.5, 1.9), (2.5, 2.7), (3.9, 4.2))]
        f = sr.span_flushes(bursts, 1.0, 3.0)
        self.assertEqual((f["n"], f["partial"]), (2, 0))
        self.assertAlmostEqual(f["run_ms_per_flush"], 300.0, places=3)  # (400 + 200) / 2
        f = sr.span_flushes(bursts, 1.0, 4.0)
        self.assertEqual((f["n"], f["partial"]), (2, 1))  # 4.0 is inside a flush
        f = sr.span_flushes([], 0.0, 9.0)
        self.assertEqual((f["n"], f["partial"], f["run_ms_per_flush"]), (0, 0, None))

    def test_settled_scrape(self):
        from epl import statsrow as sr

        class C:
            def __init__(self, seq):
                self.seq = list(seq)

            def scrape(self):
                return dict(self.seq.pop(0) if len(self.seq) > 1 else self.seq[0])
        c = sr.settled_scrape(C([{"p": 1}, {"p": 5}, {"p": 9}, {"p": 9}]), tries=5, step_s=0)
        self.assertEqual((c["p"], c["_settled"]), (9, True))
        c = sr.settled_scrape(C([{"p": i} for i in range(10)]), tries=3, step_s=0)
        self.assertFalse(c["_settled"])


class OtlpEvidenceTest(unittest.TestCase):
    """The 1M OTLP loss of run S: 31 full requests of counters and gauges and the 146-point
    tail accepted, the mixed and the four histogram requests refused below the receiver (an
    oversized message), 5 stream resets per flush."""

    def test_loss_fails_the_single_basis(self):
        from epl import statsrow as sr
        used = 360146
        f = sr.flush_fit(3 * 310146, used, 3)  # three flushes of the lossy export
        self.assertGreater(f["residual"], 0.01)
        f = sr.flush_fit(3 * used, used, 3)  # every used stat arrives
        self.assertEqual((f["n"], f["n_error"], f["residual"]), (3, 0, 0.0))

    def test_otlp_cluster(self):
        from epl import statsrow as sr
        c = "cluster.otel_collector."
        n0 = {c + "upstream_rq_total": 100, c + "http2.rx_reset": 0, c + "upstream_cx_tx_bytes_total": 0}
        n1 = {c + "upstream_rq_total": 100 + 3 * 37, c + "http2.rx_reset": 15, c + "upstream_cx_tx_bytes_total": 9}
        o = sr.otlp_cluster(n0, n1, 360146, 10000, 61.0, 20.0)
        self.assertEqual((o["requests_per_flush_expected"], o["requests"], o["rx_reset"]), (37, 111, 15))
        self.assertEqual((o["whole_error"], o["estimate_error"]), (0.0, round(abs(3 - 61 / 20.0), 3)))
        self.assertTrue(o["http2_stats_present"])
        n1.pop(c + "http2.rx_reset")  # the used-only read leaves an unmoved counter out: 0
        n1[c + "http2.streams_active"] = 0
        self.assertEqual(sr.otlp_cluster(n0, n1, 360146, 10000, 61.0, 20.0)["rx_reset"], 0)
        self.assertIn("error", sr.otlp_cluster({}, n1, 360146, 10000, 61.0, 20.0))
        # the smoke of 2026-11-19: the codec stats appeared after the pre-window read
        n0b = {c + "upstream_rq_total": 100}
        o = sr.otlp_cluster(n0b, n1, 360146, 10000, 61.0, 20.0)
        self.assertEqual((o["rx_reset"], o["http2_stats_present"]), (0, True))
        n1b = {c + "upstream_rq_total": 211}
        self.assertFalse(sr.otlp_cluster(n0b, n1b, 360146, 10000, 61.0, 20.0)["http2_stats_present"])

    def test_collector_conf_and_log(self):
        from epl import origin
        conf = origin.collector_conf(4317, 8888, True, 64)
        self.assertIn("max_recv_msg_size_mib: 64", conf)
        self.assertNotIn("max_recv_msg_size_mib", origin.collector_conf(4317, 8888, True))
        s = origin.log_summary("2026-11-19T12:00:00Z\tinfo\tok\n2026-11-19T12:00:01Z\terror\tgrpc: received message "
                               "larger than max\n")
        self.assertEqual((s["lines"], s["error_lines"]), (2, 1))
        self.assertIn("larger than max", s["first_error"])


class PreReadTimeTest(unittest.TestCase):
    def test_one_t_pre(self):
        # R1: the uptime check's time base is assigned once, before the pre-window read; the
        # otlp_cluster span has its own start
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "epl", "leg.py")).read()
        self.assertEqual(src.count("t_pre = time.monotonic()"), 1)
        self.assertIn("t_post - t_cl0", src)
