"""The faultable origin (epl.faultorigin, origin.mode envoy_fault): validation, the origin Envoy's bootstrap and
container arguments, the live fault write with its read-back (against a stand-in origin admin), the realised-share
check, and the start's fail-closed image check."""
import base64
import copy
import http.server
import json
import os
import socketserver
import tempfile
import threading
import time
import unittest
from unittest import mock

from epl import experiment, faultorigin, origin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIX = os.path.join(ROOT, "tests", "fixtures")


class OriginAdmin:
    """A stand-in for the fault origin's admin: GET /runtime (the four fault keys), POST /runtime_modify (an admin
    layer), GET /stats (downstream_rq_total at `rate` per second; aborts and delays at the runtime's shares).
    `ignore_posts` answers 200 and changes nothing (the read-back must catch it); `refuse` answers 503."""

    def __init__(self, rate=1000.0, ignore_posts=False, refuse=False, scale=1.0):
        self.values = {faultorigin.ABORT_PCT: "0", faultorigin.ABORT_STATUS: "503", faultorigin.DELAY_PCT: "0",
                       faultorigin.DELAY_MS: "0"}
        self.rate, self.scale = rate, scale
        self.c = {"rq": 0.0, "ab": 0.0, "dl": 0.0}
        self.posts = []
        self.lock = threading.Lock()
        self.stop = threading.Event()
        outer = self

        def tick():
            t = time.monotonic()
            while not outer.stop.is_set():
                time.sleep(0.005)
                now = time.monotonic()
                n = outer.rate * (now - t)
                t = now
                with outer.lock:
                    outer.c["rq"] += n
                    outer.c["ab"] += n * float(outer.values[faultorigin.ABORT_PCT]) / 100.0 * outer.scale
                    outer.c["dl"] += n * float(outer.values[faultorigin.DELAY_PCT]) / 100.0 * outer.scale
        threading.Thread(target=tick, daemon=True).start()

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, st, body):
                b = body.encode()
                self.send_response(st)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path.startswith("/runtime"):
                    self._send(200, json.dumps({"entries": {k: {"final_value": v} for k, v in outer.values.items()}}))
                elif self.path.startswith("/stats"):
                    with outer.lock:
                        c = dict(outer.c)
                    self._send(200, "http.origin.downstream_rq_total: %d\nhttp.origin.fault.aborts_injected: %d\n"
                               "http.origin.fault.delays_injected: %d\n" % (c["rq"], c["ab"], c["dl"]))
                else:
                    self._send(404, "no")

            def do_POST(self):
                from urllib.parse import parse_qsl, urlsplit
                u = urlsplit(self.path)
                outer.posts.append(u.query)
                if refuse:
                    return self._send(503, "No admin layer specified")
                if not ignore_posts:
                    with outer.lock:
                        outer.values.update(dict(parse_qsl(u.query)))
                self._send(200, "OK\n")

        class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
        self.srv = S(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.stop.set()
        self.srv.shutdown()
        self.srv.server_close()


def ex(name="fault-abort", **sets):
    exp = experiment.load(os.path.join(FIX, name + ".json"),
                          experiment.parse_sets(["%s=%s" % (k, json.dumps(v)) for k, v in sets.items()]))
    return exp, experiment.validate(exp, allow_short=True)


class ValidateTest(unittest.TestCase):
    def test_examples(self):
        for n in ("fault-abort", "fault-abort-null", "fault-delay"):
            exp, errs = ex(n)
            self.assertEqual(errs, [], n)
            self.assertEqual(exp["origin"]["mode"], "envoy_fault")

    def has(self, text, **sets):
        errs = ex(**sets)[1]
        self.assertTrue(any(text in e for e in errs), (text, errs))

    def test_refusals(self):
        self.has("origin.mode envoy_fault needs origin.image_id", **{"origin.image_id": "abc"})
        self.has("origin.mode envoy_fault needs origin.image (a local Envoy image)", **{"origin.image": "nginx:alpine"})
        self.has("unknown or unsupported origin keys ['stub_status']", **{"origin.stub_status": True})
        self.has("origin.admin_port must differ", **{"origin.admin_port": 9921})
        self.has("origin.admin_port must be a port number", **{"origin.admin_port": 0})
        self.has("origin.workers must be a whole number >= 1", **{"origin.workers": 0})
        self.has("origin.fault.abort_percent must be a whole percent 0-100", **{"origin.fault.abort_percent": 101})
        self.has("origin.fault: unknown keys ['x']", **{"origin.fault.x": 1})
        self.has("origin.fault.abort_status must be an HTTP status 200-599", **{"origin.fault.abort_status": 99})
        self.has("origin.fault.delay_ms must be whole ms 0-60000", **{"origin.fault.delay_ms": -1})
        self.has("origin.fault.delay_percent above 0 needs fault.delay_ms above 0", **{"origin.fault.delay_percent": 5})
        self.has("origin.admin_port must differ from origin.port, the SUT's ports, the collector's",
                 **{"origin.admin_port": 4317})
        exp = copy.deepcopy(ex()[0])
        del exp["cpus"]["origin"]
        self.assertIn("cpus.origin missing for an envoy_fault origin", faultorigin.config_errors(exp))
        self.has("has no stub_status", **{"measure.responses_from": "origin"})
        sh = {"name": "s", "kind": "proxied", "path": "/s", "body_bytes": 4096, "rps": 5200, "origin_chunked": True}
        self.has("shape s: origin_chunked is not served by the envoy_fault origin", shapes=[sh])

    def test_values(self):
        self.assertEqual(faultorigin.fault_values(None), faultorigin.DEFAULT_FAULT)
        with self.assertRaises(ValueError):
            faultorigin.fault_values({"abort_percent": 1.5})  # whole percent: the denominator is HUNDRED
        with self.assertRaises(ValueError):
            faultorigin.fault_values({"delay_percent": True})

    def test_nginx_origin_configs_unchanged(self):
        # a docker origin never reaches the fault origin's checks (the byte-identity check covers every example)
        exp = experiment.load(os.path.join(ROOT, "examples", "aa-selftest.json"))
        with mock.patch.object(faultorigin, "config_errors", side_effect=AssertionError("called")):
            self.assertEqual(experiment.validate(exp, allow_short=True), [])


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.exp, _ = ex()

    def test_bootstrap(self):
        b = faultorigin.bootstrap(self.exp["origin"], self.exp["shapes"])
        self.assertEqual(b["admin"]["address"]["socket_address"], {"address": "127.0.0.1", "port_value": 9941})
        lay = b["layered_runtime"]["layers"]
        self.assertEqual([x["name"] for x in lay], ["epl-origin-static", "epl-origin-admin"])
        self.assertEqual(lay[0]["static_layer"], {faultorigin.ABORT_PCT: 0, faultorigin.ABORT_STATUS: 503,
                                                  faultorigin.DELAY_PCT: 0, faultorigin.DELAY_MS: 0})
        self.assertEqual(lay[1], {"name": "epl-origin-admin", "admin_layer": {}})
        lst = b["static_resources"]["listeners"][0]
        self.assertEqual(lst["address"]["socket_address"], {"address": "127.0.0.1", "port_value": 8092})
        hcm = lst["filter_chains"][0]["filters"][0]["typed_config"]
        self.assertEqual(hcm["stat_prefix"], "origin")
        names = [f["name"] for f in hcm["http_filters"]]
        self.assertEqual(names, ["envoy.filters.http.fault", "envoy.filters.http.router"])  # fault before the router
        fault = hcm["http_filters"][0]["typed_config"]
        self.assertEqual(fault["abort"]["percentage"], {"numerator": 0, "denominator": "HUNDRED"})
        self.assertEqual(fault["delay"]["percentage"], {"numerator": 0, "denominator": "HUNDRED"})
        self.assertEqual(fault["delay"]["fixed_delay"], "0.001s")  # > 0 (required); the runtime key rules
        r0 = hcm["route_config"]["virtual_hosts"][0]["routes"][0]
        self.assertEqual(r0["match"], {"path": "/s"})
        self.assertEqual(len(base64.b64decode(r0["direct_response"]["body"]["inline_bytes"])), 4096)
        self.assertEqual(hcm["route_config"]["max_direct_response_body_size_bytes"], 4096)
        self.assertEqual(hcm["route_config"]["virtual_hosts"][0]["routes"][-1]["direct_response"], {"status": 404})

    def test_content_type_and_large_body(self):
        sh = [{"name": "b", "kind": "proxied", "path": "/b", "body_bytes": 65536, "content_type": "text/html"}]
        b = faultorigin.bootstrap(self.exp["origin"], sh)
        hcm = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]
        r0 = hcm["route_config"]["virtual_hosts"][0]["routes"][0]
        self.assertEqual(r0["response_headers_to_add"][0]["header"], {"key": "content-type", "value": "text/html"})
        self.assertEqual(hcm["route_config"]["max_direct_response_body_size_bytes"], 65536)
        with self.assertRaises(ValueError):
            faultorigin.routes(sh + [dict(sh[0], name="c", body_bytes=10)])

    def test_docker_args(self):
        a = faultorigin.docker_args(self.exp["origin"], "32-39", "epl-fault-origin-1", "/run/origin/fault-origin.json")
        self.assertEqual(a[:10], ["docker", "run", "-d", "--pull", "never", "--name", "epl-fault-origin-1",
                                  "--network", "host", "--cpuset-cpus"])
        self.assertNotIn("--rm", a)  # stop() saves the log, then removes the container by its ID
        # the checked image ID runs, never the tag
        self.assertEqual(a[a.index("--entrypoint") + 2], self.exp["origin"]["image_id"])
        self.assertNotIn(self.exp["origin"]["image"], a)
        self.assertIn("/run/origin/fault-origin.json:%s:ro" % faultorigin.CONTAINER_BOOTSTRAP, a)
        self.assertEqual(a[a.index("--entrypoint") + 1], "/usr/local/bin/envoy")
        self.assertIn("--disable-hot-restart", a)  # host network: the hot-restart socket would collide
        self.assertEqual(a[a.index("--concurrency") + 1], "4")
        self.assertNotIn("sh", a)


class LiveFaultTest(unittest.TestCase):
    def test_set_and_read_back(self):
        adm = OriginAdmin()
        try:
            r = faultorigin.set_fault(adm.port, {"abort_percent": 5})
            self.assertTrue(r["ok"])
            self.assertEqual(adm.values[faultorigin.ABORT_PCT], "5")
            self.assertEqual(r["runtime"][faultorigin.ABORT_STATUS], "503")
            self.assertEqual(adm.posts[-1], faultorigin.query({"abort_percent": 5}))
            self.assertEqual(faultorigin.current(adm.port)["abort_percent"], 5)
            q = adm.posts[-1]
            for k in faultorigin.KEYS:
                self.assertIn(k + "=", q)  # all four keys in one write
        finally:
            adm.close()

    def test_fail_closed(self):
        adm = OriginAdmin(ignore_posts=True)
        try:
            with self.assertRaises(faultorigin.FaultNotApplied) as cm:
                faultorigin.set_fault(adm.port, {"abort_percent": 5})
            self.assertIn("fault.http.abort.abort_percent=0 (wrote 5)", str(cm.exception))
        finally:
            adm.close()
        adm = OriginAdmin(refuse=True)
        try:
            with self.assertRaises(faultorigin.FaultNotApplied) as cm:
                faultorigin.set_fault(adm.port, {"delay_percent": 5, "delay_ms": 200})
            self.assertIn("answered 503", str(cm.exception))
        finally:
            adm.close()
        with self.assertRaises(ValueError):
            faultorigin.set_fault(1, {"abort_percent": 500})  # refused before anything is sent

    def test_stats_and_effect(self):
        adm = OriginAdmin(rate=20000.0)
        try:
            s0 = faultorigin.fault_stats(adm.port)
            faultorigin.set_fault(adm.port, {"abort_percent": 20})
            time.sleep(0.5)
            s1 = faultorigin.fault_stats(adm.port)
            e = faultorigin.effect_check(s0, s1, {"abort_percent": 20})
            self.assertTrue(e["ok"], e)
            self.assertAlmostEqual(e["abort_share"], 0.20, delta=0.03)
            # declared 5% while 20% happened: fails
            self.assertFalse(faultorigin.effect_check(s0, s1, {"abort_percent": 5})["ok"])
        finally:
            adm.close()
        n = {"http.origin.downstream_rq_total": 0, "http.origin.fault.aborts_injected": 0,
             "http.origin.fault.delays_injected": 0}
        few = dict(n, **{"http.origin.downstream_rq_total": 50})
        e = faultorigin.effect_check(n, few, {"abort_percent": 0})
        self.assertFalse(e["ok"])
        self.assertIn("not checkable", e["reasons"][0])
        many = dict(n, **{"http.origin.downstream_rq_total": 10000, "http.origin.fault.aborts_injected": 3})
        self.assertFalse(faultorigin.effect_check(n, many, {"abort_percent": 0})["ok"])  # the null: 0 aborts
        self.assertTrue(faultorigin.effect_check(n, dict(many, **{"http.origin.fault.aborts_injected": 0}),
                                                 {"abort_percent": 0})["ok"])
        self.assertFalse(faultorigin.effect_check(None, many, {})["ok"])
        # at 0% exactly 0 injections (one stray abort in 52,000 fails), at 100% exactly all
        big = dict(n, **{"http.origin.downstream_rq_total": 52000, "http.origin.fault.aborts_injected": 1})
        e = faultorigin.effect_check(n, big, {"abort_percent": 0})
        self.assertFalse(e["ok"])
        self.assertIn("origin abort injected 1 of 52000 requests over the hold, declared 0% (exactly 0)", e["reasons"])
        full = dict(n, **{"http.origin.downstream_rq_total": 1000, "http.origin.fault.aborts_injected": 999})
        self.assertFalse(faultorigin.effect_check(n, full, {"abort_percent": 100})["ok"])
        self.assertTrue(faultorigin.effect_check(n, dict(full, **{"http.origin.fault.aborts_injected": 1000}),
                                                 {"abort_percent": 100})["ok"])
        with self.assertRaises(ValueError):
            faultorigin.fault_values({"delay_percent": 5, "delay_ms": 0})  # could never inject


class OriginStartTest(unittest.TestCase):
    def test_image_id_mismatch_starts_nothing(self):
        exp, _ = ex()
        tmp = tempfile.mkdtemp()
        o = origin.Origin(exp["origin"], "32-39", exp["shapes"], tmp, lambda m: None)
        calls = []

        def run(args, **kw):
            calls.append(args)
            return mock.Mock(returncode=0, stdout="sha256:" + "f" * 64 + "\n", stderr="")
        with mock.patch.object(origin.subprocess, "run", run), \
                mock.patch.object(origin.sysprobe, "port_open", lambda h, p: False):
            with self.assertRaises(RuntimeError) as cm:
                o.start()
        self.assertIn("not the pinned", str(cm.exception))
        self.assertEqual([c[:3] for c in calls], [["docker", "image", "inspect"]])  # no docker run
        self.assertIsNone(o.container_id)

    def test_start_sets_and_proves_the_starting_values(self):
        exp, _ = ex()
        adm = OriginAdmin()
        cfg = copy.deepcopy(exp["origin"])
        cfg["admin_port"] = adm.port
        cfg["image_id"] = "sha256:" + "a" * 64
        tmp = tempfile.mkdtemp()
        o = origin.Origin(cfg, "32-39", exp["shapes"], tmp, lambda m: None)
        calls = []

        def run(args, **kw):
            calls.append(args)
            if args[:3] == ["docker", "image", "inspect"]:
                return mock.Mock(returncode=0, stdout=cfg["image_id"] + "\n", stderr="")
            if args[:2] == ["docker", "run"]:
                return mock.Mock(returncode=0, stdout="c0ffee\n", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")
        try:
            with mock.patch.object(origin.subprocess, "run", run), \
                    mock.patch.object(origin.sysprobe, "port_open", lambda h, p: False), \
                    mock.patch.object(origin.sysprobe, "wait_port", lambda h, p, t: True), \
                    mock.patch.object(origin, "side_service", lambda *a: None):
                meta = o.start()
                self.assertTrue(meta["fault_start"]["ok"])
                self.assertEqual(len(adm.posts), 1)
                with open(os.path.join(tmp, "origin", "fault-origin.json")) as f:
                    self.assertEqual(json.load(f)["admin"]["address"]["socket_address"]["port_value"], adm.port)
                r = o.set_fault({"abort_percent": 20})
                self.assertEqual(r["values"]["abort_percent"], 20)
                o.stop()
            # stop by the ID docker returned, keep its log, then remove it by that ID (no --rm)
            self.assertEqual([c[:2] for c in calls[-3:]], [["docker", "stop"], ["docker", "logs"], ["docker", "rm"]])
            self.assertTrue(all(c[-1] == "c0ffee" for c in calls[-3:]))
            self.assertTrue(os.path.exists(os.path.join(tmp, "origin", "fault-origin.log")))
            run = [c for c in calls if c[:2] == ["docker", "run"]][0]
            self.assertIn(cfg["image_id"], run)
        finally:
            adm.close()

    def test_run_timeout_stops_a_created_container(self):
        exp, _ = ex()
        tmp = tempfile.mkdtemp()
        o = origin.Origin(exp["origin"], "32-39", exp["shapes"], tmp, lambda m: None)
        calls = []

        def run(args, **kw):
            calls.append(args)
            if args[:3] == ["docker", "image", "inspect"]:
                return mock.Mock(returncode=0, stdout=exp["origin"]["image_id"] + "\n", stderr="")
            if args[:2] == ["docker", "run"]:
                raise origin.subprocess.TimeoutExpired(args, 120)
            if args[:2] == ["docker", "ps"]:
                return mock.Mock(returncode=0, stdout="deadbeef\n", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(origin.subprocess, "run", run), \
                mock.patch.object(origin.sysprobe, "port_open", lambda h, p: False):
            with self.assertRaises(RuntimeError) as cm:
                o.start()
        self.assertIn("timed out; container deadbeef stopped", str(cm.exception))
        ps = [c for c in calls if c[:2] == ["docker", "ps"]][0]
        self.assertIn("name=^epl-fault-origin-%d$" % os.getpid(), ps)
        self.assertIn(["docker", "stop", "-t", "5", "deadbeef"], calls)
        self.assertIn(["docker", "rm", "deadbeef"], calls)
        self.assertIsNone(o.container_id)


if __name__ == "__main__":
    unittest.main()
