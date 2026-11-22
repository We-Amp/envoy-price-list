"""Track C of wave 1: ext_proc and gRPC client settings, file-based xDS updates, their leg records,
gates and tables."""

import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest

from epl import envoy_config, experiment, leg, origin, validity, xds

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W1C = os.path.join(HERE, "examples", "wave1c")
CFG = os.path.join(W1C, "configs")


def _mod(name, path):
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.path.pop(0)


MK = _mod("wave1c_make", os.path.join(W1C, "make.py"))
TB = _mod("wave1c_table", os.path.join(W1C, "table.py"))
SHAPES = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200}]
ENV = {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True}


def boot(**settings):
    e = dict(ENV, **settings)
    return envoy_config.bootstrap(SHAPES, e, 8092)


def hcm_of(b):
    return b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]


def cluster_names(b):
    return [c["name"] for c in b["static_resources"].get("clusters", [])]


class ConfigsTest(unittest.TestCase):
    def test_written_configs_are_current(self):
        for fn, c in MK.configs({}).items():
            with open(os.path.join(CFG, fn)) as f:
                self.assertEqual(json.load(f), json.loads(json.dumps(c)), fn + ": rerun make.py")

    def test_every_config_validates(self):
        for fn in sorted(os.listdir(CFG)):
            exp = experiment.load(os.path.join(CFG, fn))
            self.assertEqual(experiment.validate(exp, allow_short=True), [], fn)

    def test_ext_proc_sha_matches_sums(self):
        exp = experiment.load(os.path.join(CFG, "extproc.json"))
        with open(os.path.join(HERE, "tools", "extproc", "SHA256SUMS")) as f:
            self.assertIn(exp["origin"]["ext_proc_sha256"], f.read())

    def test_short_run_needs_allow_short(self):
        exp = experiment.load(os.path.join(CFG, "xds-small.json"))
        self.assertTrue(any("rounds must be >= 12" in e for e in experiment.validate(exp)))

    def test_arms_one_binary(self):
        for fn in ("extproc.json", "xds-small.json", "xds-large.json"):
            exp = experiment.load(os.path.join(CFG, fn))
            self.assertEqual({a["source_sha256"] for a in exp["arms"]},
                             {"1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc"})

    def test_budget(self):
        import io
        out = io.StringIO()
        tot = MK.budget(45.0, out)
        self.assertIn("extproc.json", out.getvalue())
        # 48 + 96 + 84 + 48 run legs and 8 + 16 + 14 + 8 smoke legs
        self.assertAlmostEqual(tot, (48 + 96 + 84 + 48 + 8 + 16 + 14 + 8) * 45.0)


class GrpcSideServiceTest(unittest.TestCase):
    def test_ext_proc_default(self):
        b = boot(ext_proc={"mode": "default"}, ext_proc_port=8095)
        fl = hcm_of(b)["http_filters"]
        self.assertEqual([f["name"] for f in fl], ["envoy.filters.http.ext_proc", "envoy.filters.http.router"])
        cfg = fl[0]["typed_config"]
        self.assertEqual(cfg["grpc_service"], {"envoy_grpc": {"cluster_name": "ext_proc"}})
        self.assertNotIn("processing_mode", cfg)  # the filter's defaults: both header phases sent
        self.assertFalse(cfg["failure_mode_allow"])
        c = [x for x in b["static_resources"]["clusters"] if x["name"] == "ext_proc"][0]
        self.assertEqual(c["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"]
                         ["socket_address"]["port_value"], 8095)
        self.assertIn("http2_protocol_options", json.dumps(c))

    def test_ext_proc_request_headers_google(self):
        b = boot(ext_proc={"mode": "request_headers"}, ext_proc_port=8095, grpc_client="google_grpc")
        cfg = hcm_of(b)["http_filters"][0]["typed_config"]
        self.assertEqual(cfg["processing_mode"], {"request_header_mode": "SEND", "response_header_mode": "SKIP"})
        self.assertEqual(cfg["grpc_service"], {"google_grpc": {"target_uri": "127.0.0.1:8095",
                                                                "stat_prefix": "ext_proc"}})
        self.assertNotIn("ext_proc", cluster_names(b))

    def test_authz_google(self):
        b = boot(ext_authz="grpc", authz_grpc_port=8094, grpc_client="google_grpc")
        cfg = hcm_of(b)["http_filters"][0]["typed_config"]
        self.assertEqual(cfg["grpc_service"]["google_grpc"]["target_uri"], "127.0.0.1:8094")
        self.assertEqual(cfg["grpc_service"]["timeout"], "0.5s")
        self.assertNotIn("ext_authz", cluster_names(b))
        # the envoy_grpc default is byte-identical to the published row's filter
        b2 = boot(ext_authz="grpc", authz_grpc_port=8094)
        self.assertEqual(hcm_of(b2)["http_filters"][0]["typed_config"]["grpc_service"],
                         {"envoy_grpc": {"cluster_name": "ext_authz"}, "timeout": "0.5s"})

    def test_bad_settings(self):
        with self.assertRaises(ValueError):
            boot(grpc_client="google_grpc")  # no side-service filter to apply it to
        with self.assertRaises(ValueError):
            boot(grpc_client="other", ext_authz="grpc", authz_grpc_port=1)
        with self.assertRaises(ValueError):
            boot(ext_proc={"mode": "bodies"}, ext_proc_port=1)
        with self.assertRaises(ValueError):
            boot(ext_proc={"processing_mode": {}}, ext_proc_port=1)

    def test_validate_needs_service(self):
        exp = experiment.load(os.path.join(CFG, "extproc.json"))
        exp["origin"].pop("ext_proc_sha256")
        self.assertTrue(any("ext_proc_sha256" in e for e in experiment.validate(exp, allow_short=True)))

    def test_service_args_and_sha_gate(self):
        cfg = {"ext_proc_port": 8095, "image": "img@sha256:x", "platform": "linux/amd64", "ext_proc_gomaxprocs": 16}
        a = origin.ext_proc_args(cfg, "32-39,72-79", "n", "/b/epl-extproc")
        self.assertEqual(a[a.index("--cpuset-cpus") + 1], "32-39,72-79")
        self.assertIn("/b/epl-extproc:/epl-extproc:ro", a)
        self.assertEqual(a[a.index("--entrypoint") + 1], "/epl-extproc")
        self.assertIn("GOMAXPROCS=16", a)
        self.assertEqual(a[-2:], ["-addr", "127.0.0.1:8095"])
        with tempfile.NamedTemporaryFile() as f:
            f.write(b"not the binary")
            f.flush()
            svc = origin.ExtProcService(dict(cfg, ext_proc_binary=f.name, ext_proc_sha256="0" * 64), "1", print)
            with self.assertRaises(RuntimeError):
                svc.start()  # refused before any docker call
            self.assertIsNone(svc.container_id)

    def test_attach_companions(self):
        class S:
            def __init__(self, n):
                self.container_id, self.side = "c-" + n, n

        class O(S):
            companions = [("ext_proc", S("xp"))]
        be = leg.RealBackend.__new__(leg.RealBackend)
        be.attach(O("origin"), None)
        self.assertEqual(be.side_expected, ["origin", "ext_proc"])
        self.assertEqual(be.side, ["origin", "xp"])


class XdsBootstrapTest(unittest.TestCase):
    def test_dynamic_resources(self):
        b = boot(xds={"routes": 3, "clusters": 2, "dir": "/x"})
        h = hcm_of(b)
        self.assertNotIn("route_config", h)
        self.assertEqual(h["rds"]["config_source"]["path_config_source"]["path"], "/x/rds/rds.json")
        self.assertEqual(b["dynamic_resources"]["cds_config"]["path_config_source"]["path"], "/x/cds/cds.json")
        self.assertNotIn("watched_directory", json.dumps(b))  # each file on its own watch
        self.assertNotIn("clusters", b["static_resources"])  # the origin comes by CDS
        self.assertEqual(b["node"]["id"], "epl")

    def test_side_clusters_stay_static(self):
        b = boot(xds={"routes": 3, "clusters": 2, "dir": "/x"}, ext_authz="grpc", authz_grpc_port=8094)
        self.assertEqual(cluster_names(b), ["ext_authz"])

    def test_exclusive_and_bad(self):
        for kw in ({"buffer_limit_bytes": 4096}, {"upstream_pool_per_downstream": True},
                   {"stats_clusters": {"count": 2}}):
            with self.assertRaises(ValueError):
                boot(xds={"routes": 3, "clusters": 2, "dir": "/x"}, **kw)
        with self.assertRaises(ValueError):
            boot(xds={"routes": 3, "clusters": 2})  # no directory
        with self.assertRaises(ValueError):
            boot(xds={"routes": 3, "clusters": 0, "dir": "/x"})
        with self.assertRaises(ValueError):
            boot(xds={"routes": 3, "clusters": 2, "dir": "/x"}, xds_update={"kind": "eds", "rate_hz": 1})
        with self.assertRaises(ValueError):
            boot(xds={"routes": 3, "clusters": 2, "dir": "/x"}, xds_update={"kind": "lds", "rate_hz": 1})
        with self.assertRaises(ValueError):
            boot(xds_update={"kind": "rds", "rate_hz": 1})

    def test_validate_rules(self):
        exp = experiment.load(os.path.join(CFG, "xds-small.json"))
        exp["measure"]["per_thread"] = False
        self.assertTrue(any("per_thread" in e for e in experiment.validate(exp, allow_short=True)))
        exp = experiment.load(os.path.join(CFG, "xds-small.json"))
        exp["arms"][2]["settings"]["xds_update"]["rate_hz"] = 0.33
        self.assertTrue(any("whole number" in e for e in experiment.validate(exp, allow_short=True)))


def state(d, eds=4):
    return xds.State([envoy_config.route_for(SHAPES[0])], {"routes": 5, "clusters": 3, "eds_endpoints": eds}, 8092, d)


def resources(path):
    with open(path) as f:
        return json.load(f)["resources"]


class XdsStateTest(unittest.TestCase):
    def test_initial(self):
        with tempfile.TemporaryDirectory() as d:
            st = state(d)
            xds.write_initial(st)
            rc = resources(st.paths["rds"])[0]
            rs = rc["virtual_hosts"][0]["routes"]
            self.assertEqual(rs[0]["match"], {"path": "/s"})  # the request matches on its first route
            self.assertEqual(len(rs), 6)
            cl = resources(st.paths["cds"])
            self.assertEqual([c["name"] for c in cl], ["origin", "epl-filler-00000", "epl-filler-00001",
                                                       "epl-filler-00002", "epl-eds"])
            self.assertEqual(len(resources(st.paths["eds"])[0]["endpoints"][0]["lb_endpoints"]), 4)
            self.assertEqual(sorted(os.listdir(os.path.dirname(st.paths["rds"]))), ["rds.json"])  # no tmp left
            st2 = state(d, eds=0)
            self.assertNotIn("epl-eds", [c["name"] for c in st2.clusters()])

    def test_kinds_change_one_thing(self):
        with tempfile.TemporaryDirectory() as d:
            st = state(d)
            r0, c0, e0 = st.route_configuration(), st.clusters(), st.load_assignment()
            self.assertEqual(st.apply("rds", 7), "rds")
            r1 = st.route_configuration()
            rs0, rs1 = r0["virtual_hosts"][0]["routes"], r1["virtual_hosts"][0]["routes"]
            diff = [i for i, (a, b) in enumerate(zip(rs0, rs1)) if a != b]
            self.assertEqual(diff, [1 + 7 % 5])
            self.assertEqual(st.apply("rds_same", 8), "rds")
            self.assertEqual(st.route_configuration(), r1)  # unchanged; only version_info moves
            self.assertNotEqual(st.text("rds", 8), st.text("rds", 9))
            st.apply("cds", 4)
            c1 = st.clusters()
            self.assertEqual([c["name"] for a, c in zip(c0, c1) if a != c], ["epl-filler-00001"])
            st.apply("cds_active", 5)
            self.assertEqual([c["name"] for a, c in zip(c1, st.clusters()) if a != c], ["origin"])
            st.apply("cds_same", 6)
            st.apply("eds", 6)
            eps = st.load_assignment()["endpoints"][0]["lb_endpoints"]
            self.assertEqual(len(eps), 3)
            self.assertNotIn(xds.EDS_PORT_BASE + 2, [e["endpoint"]["address"]["socket_address"]["port_value"]
                                                     for e in eps])
            self.assertNotEqual(e0, st.load_assignment())

    def test_updater_schedule(self):
        with tempfile.TemporaryDirectory() as d:
            st = state(d)
            xds.write_initial(st)
            ctr = [1]
            t0 = time.monotonic()
            u = xds.Updater(st, "cds", 40.0, ctr, anchor=t0, count=4)
            u.start()
            u.join(5)
            self.assertIsNone(u.error)
            self.assertEqual([k for k, _, _ in u.renames], [1, 2, 3, 4])
            self.assertEqual(ctr, [5])
            for j, (_, t, _) in enumerate(u.renames):
                self.assertGreaterEqual(t, t0 + (j + 0.5) / 40.0 - 1e-3)
            with open(st.paths["cds"]) as f:
                self.assertEqual(json.load(f)["version_info"], "4")
            # a stopped updater renames nothing more and leaves the counter where it was
            u2 = xds.Updater(st, "cds", 0.5, ctr)
            u2.start()
            u2.stop()
            self.assertEqual((u2.renames, ctr), ([], [5]))


class FakeU:
    def __init__(self, times, error=None):
        self.renames = [(i, t, 0) for i, t in enumerate(times)]
        self.error = error


class WindowRecordTest(unittest.TestCase):
    S = xds.stat_names("cds")

    def q(self, n, t=None):
        d = {self.S["success"]: n}
        if t is not None:
            d[self.S["time"]] = t
        return d

    def test_ok_and_failures(self):
        pre, win = FakeU([0.5, 1.5]), FakeU([10.5 + j for j in range(3)])
        r = xds.window_record("cds", self.q(1), self.q(3), self.q(6, 1000.0 * 99), pre, win, 10.0, 13.2, 100.0, 3)
        self.assertTrue(r["ok"], r["checks"])
        self.assertEqual(r["renames_in_window"], 3)
        bad = xds.window_record("cds", self.q(1), self.q(2), self.q(5, 99000), pre, win, 10.0, 13.2, 100.0, 3)
        self.assertFalse(bad["checks"]["cds_pre_applied"])  # a pre update was not applied before the window
        late = xds.window_record("cds", self.q(1), self.q(3), self.q(6, 101000), pre, win, 10.0, 13.2, 100.0, 3)
        self.assertFalse(late["checks"]["cds_last_update_in_window"])
        short = xds.window_record("cds", self.q(1), self.q(3), self.q(5, 99000), pre, win, 10.0, 13.2, 100.0, 3)
        self.assertFalse(short["checks"]["cds_window_updates"])
        rds_moved = dict(self.q(6, 99000), **{xds.stat_names("rds")["success"]: 1})
        cross = xds.window_record("cds", self.q(1), self.q(3), rds_moved, pre, win, 10.0, 13.2, 100.0, 3)
        self.assertFalse(cross["checks"]["rds_window_updates"])  # one type's rename moved another type

    def test_reference_arm(self):
        r = xds.window_record(None, {}, {}, {}, None, None, 0, 20, 1, 0, eds=True)
        self.assertTrue(r["ok"])
        self.assertEqual(sorted(r["types"]), ["cds", "eds", "rds"])

    def test_verdict(self):
        base = {"idle_ok": True, "preflight_ok": True}
        v = validity.verdict(dict(base, xds={"ok": False, "checks": {"cds_window_updates": False}}))
        self.assertTrue(any("xds: cds_window_updates" in r for r in v["reasons"]))
        v = validity.verdict(dict(base, envoy_thread_set={"unchanged": False, "new": ["GrpcGoogClient"]}))
        self.assertTrue(any("threads changed" in r for r in v["reasons"]))
        v = validity.verdict(dict(base, envoy_main_busy=0.7), {"max_main_busy": 0.5})
        self.assertTrue(any("main thread busy" in r for r in v["reasons"]))
        v = validity.verdict(dict(base, envoy_main_busy=0.7))
        self.assertFalse(any("main thread busy" in r for r in v["reasons"]))  # not gated by default


class LegHelpersTest(unittest.TestCase):
    def test_stub_accepts(self):
        txt = "Active connections: 3\nserver accepts handled requests\n 17 17 905\nReading: 0 Writing: 1 Waiting: 2\n"
        self.assertEqual(leg.parse_stub_accepts(txt), 17)
        self.assertEqual(leg.parse_stub_status(txt), 905)
        self.assertIsNone(leg.parse_stub_accepts("nothing"))

    def test_thread_cycles_and_set(self):
        pt = {100: {"comm": "envoy-1.40.2", "cycles:u": 10.0, "cycles:k": 5.0},
              101: {"comm": "wrk:worker_0", "cycles:u": 100.0, "cycles:k": 50.0},
              102: {"comm": "wrk:worker_1", "cycles": 120.0},
              103: {"comm": "GrpcGoogClient", "cycles:u": 7.0, "cycles:k": 1.0}}
        tc = leg.thread_cycles(pt, 100)
        self.assertEqual((tc["main"], tc["workers"], tc["other"]), (15.0, 270.0, 8.0))
        self.assertEqual(tc["other_by_comm"], {"GrpcGoogClient": 8.0})
        e0 = {1: ("envoy", 0, 0, 0, 0), 2: ("wrk:worker_0", 0, 0, 0, 0)}
        self.assertTrue(leg.thread_set(e0, dict(e0))["unchanged"])
        ch = leg.thread_set(e0, {**e0, 3: ("grpc_global_tim", 0, 0, 0, 0)})
        self.assertFalse(ch["unchanged"])
        self.assertEqual(ch["new"], ["grpc_global_tim"])


class PairsTableTest(unittest.TestCase):
    def test_ratio_not_log(self):
        self.assertAlmostEqual(TB.ratio_pct(100 * __import__("math").log(1.3892)), 38.92, places=2)
        import io
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "legs.jsonl"), "w") as f:
                for r in range(1, 7):
                    for arm, tot in (("a", 1389.2e3 + r), ("b", 1000e3)):
                        f.write(json.dumps({"leg_id": "%s%d" % (arm, r), "arm": arm, "shape": "s", "round": r,
                                            "verdict": {"valid": True}, "responses": 100.0,
                                            "per_req": {"cycles_total": tot},
                                            "thread_cycles": {"main": 0.0, "workers": tot * 100, "other": 0.0}})
                                + "\n")
            out = io.StringIO()
            TB.direct_pairs(d, [("a", "b")], out)
            self.assertIn("+38.92%", out.getvalue())  # the ratio, not the log-% 32.87


class XdsTableTest(unittest.TestCase):
    def leg(self, arm, rnd, main, workers, accepts, shape="s", n=20):
        return {"leg_id": "%s-%s-%d" % (shape, arm, rnd), "arm": arm, "shape": shape, "round": rnd,
                "verdict": {"valid": True}, "thread_cycles": {"main": main, "workers": workers, "other": 0.0},
                "xds": {"expected_in_window": n if arm not in ("ref", "ref-A2") else 0},
                "origin_accepts_window": accepts, "envoy_main_busy": 0.1,
                "per_req": {"cycles_total": 1000.0 + main / 1e6}}

    def test_per_update_price(self):
        with tempfile.TemporaryDirectory() as d:
            legs = []
            for r in range(1, 7):
                legs.append(self.leg("ref", r, 1e8 + r, 5e10, 0))
                legs.append(self.leg("ref-A2", r, 1e8 - r, 5e10, 0))
                legs.append(self.leg("cds-active", r, 1e8 + 20 * 4e7 + 1e5 * r, 5e10 + 20 * 1e6, 20 * 64))
            with open(os.path.join(d, "legs.jsonl"), "w") as f:
                for m in legs:
                    f.write(json.dumps(m) + "\n")
            rows = {r["arm"]: r for r in TB.xds_rows(d)}
            ca = rows["cds-active"]
            self.assertEqual(ca["pairs"], 6)
            self.assertAlmostEqual(ca["main"][0], 4e7 + 1e5 * 3.5 / 20 - 3.5 / 20, delta=1e4)
            self.assertAlmostEqual(ca["workers"][0], 1e6)
            self.assertAlmostEqual(ca["accepts_per_update"][0], 64.0)
            self.assertEqual(rows["ref-A2"]["updates_per_window"], 20)
            import io
            out = io.StringIO()
            TB.xds_table([d], out)
            self.assertIn("| cds-active |", out.getvalue())


if __name__ == "__main__":
    unittest.main()
