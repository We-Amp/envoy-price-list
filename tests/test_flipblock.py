"""Flip blocks (loop/flipblock.py). One Envoy, one continuous client, a runtime guard flipped
through admin POST /runtime_modify between windows. Driven here against a stand-in Envoy admin (an HTTP server
that keeps a runtime admin layer and a 2xx counter), a stand-in client (keeps Nighthawk's SIGTERM and output
contract) and a stand-in perf (counts that depend on the guard's value, read from the stand-in admin)."""
import copy
import http.server
import importlib.util
import json
import math
import os
import socketserver
import sys
import tempfile
import threading
import time
import unittest

from epl import envoy_config, experiment, leg

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP_DIR = os.path.join(os.path.dirname(HERE), "loop")
CONFIGS = os.path.join(os.path.dirname(HERE), "examples", "flip")


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LOOP_DIR, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fb = _load("flipblock", "flipblock.py")
KEY = "envoy.reloadable_features.otel_tracer_deferred_span"


# the two published templates, and the A/A and smoke blocks derived from the control template (the same block
# with another kind and values: an A/A block writes one value twice, the smoke runs an A/A pair then a control pair)
VARIANTS = {
    "flip-aa20a": ("flip-ctl20a", {"flip.kind": "aa", "flip.values": {"A": True, "B": True}, "flip.gates": {}}),
    "flip-smoke": ("flip-ctl20a", {"flip.kind": "pairs", "flip.counterbalanced": False, "flip.order": "AB CD",
                                   "flip.values": {"A": True, "B": True, "C": False, "D": True}, "flip.window_s": 10,
                                   "flip.gates": {}}),
}


def example(name, **sets):
    base, extra = VARIANTS.get(name, (name, {}))
    p = os.path.join(CONFIGS, base + ".json")
    allsets = dict(extra, **sets)
    exp, errs = fb.load(p, experiment.parse_sets(["%s=%s" % (k, json.dumps(v)) for k, v in allsets.items()]))
    if name in VARIANTS:
        exp["name"] = name
    return exp, errs


class OrderTest(unittest.TestCase):
    def test_counterbalanced(self):
        self.assertEqual(fb.counterbalanced_order(8), "AB BA BA AB AB BA BA AB")
        self.assertEqual(fb.counterbalanced_order(4), "AB BA BA AB")
        o = fb.parse_order(fb.counterbalanced_order(8))
        self.assertEqual(len(o), 16)
        # a linear drift cancels over every four windows: the mean position of A equals that of B in each block
        for i in range(0, 16, 8):
            blk = o[i:i + 8]
            pa = [j for j, x in enumerate(blk) if x == "A"]
            pb = [j for j, x in enumerate(blk) if x == "B"]
            self.assertEqual(sum(pa), sum(pb))

    def test_parse(self):
        self.assertEqual(fb.parse_order("AB BA"), ["A", "B", "B", "A"])
        for bad in ("ABA", "AB B", "", None, "ABBA"):
            with self.assertRaises(ValueError):
                fb.parse_order(bad)

    def test_runtime_text(self):
        self.assertEqual((fb.runtime_text(True), fb.runtime_text(False), fb.runtime_text(7)), ("true", "false", "7"))


class AdminLayerTest(unittest.TestCase):
    SH = [{"name": "s", "path": "/s", "kind": "proxied", "body_bytes": 4096, "rps": 5200}]
    E = {"workers": 4, "listener_port": 10110, "admin_port": 9921}

    def test_layers(self):
        b = envoy_config.bootstrap(self.SH, dict(self.E, runtime_admin_layer=True), 8092, "/c")
        self.assertEqual(b["layered_runtime"], {"layers": [{"name": "epl-admin", "admin_layer": {}}]})
        b = envoy_config.bootstrap(self.SH, dict(self.E, runtime_admin_layer=True, runtime={"k": False}), 8092, "/c")
        self.assertEqual([x["name"] for x in b["layered_runtime"]["layers"]], ["epl-static", "epl-admin"])
        with self.assertRaises(ValueError):
            envoy_config.bootstrap(self.SH, dict(self.E, runtime_admin_layer=False), 8092, "/c")
        # without the setting the bootstrap is the one every earlier config wrote
        self.assertNotIn("layered_runtime", envoy_config.bootstrap(self.SH, dict(self.E), 8092, "/c"))
        b = envoy_config.bootstrap(self.SH, dict(self.E, runtime={"k": False}), 8092, "/c")
        self.assertEqual(b["layered_runtime"], {"layers": [{"name": "epl-static", "static_layer": {"k": False}}]})

    def test_arm_setting_known(self):
        self.assertIn("runtime_admin_layer", envoy_config.SETTINGS)


class FlipValidateTest(unittest.TestCase):
    BLOCKS = ("flip-aa20a", "flip-ctl20a", "flip-smoke", "flip-rw20")

    def test_examples(self):
        for name in self.BLOCKS:
            exp, errs = example(name)
            self.assertEqual(errs, [], name)
            self.assertEqual(experiment.validate(exp), [], name)
            self.assertTrue(exp["template"])
            if name != "flip-rw20":
                # X and the A/A bound are in every block of the deferred-span key
                self.assertEqual((exp["flip"]["marker_min"], exp["flip"]["aa_marker_max"]), (4450.0, 1110.0))
        exp, _ = example("flip-ctl20a")
        self.assertEqual(exp["flip"]["order"], "AB BA BA AB AB BA BA AB")
        self.assertEqual(exp["flip"]["values"], {"A": False, "B": True})
        b = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, exp["arms"][0], "/r"), 8092, "/c")
        self.assertEqual(b["layered_runtime"], {"layers": [{"name": "epl-admin", "admin_layer": {}}]})
        rw, _ = example("flip-rw20")
        self.assertTrue(rw["flip"]["cycle_connections"])
        self.assertFalse(rw["flip"]["gating"])
        self.assertNotIn(rw["flip"]["key"], rw["arms"][0]["settings"]["runtime"])

    def test_x_and_the_aa_bound_required(self):
        for name, key, text in (("flip-ctl20a", "marker_min", "a control block needs flip.marker_min"),
                                ("flip-aa20a", "aa_marker_max", "an aa block needs") ,
                                ("flip-smoke", "marker_min", "a pairs block needs flip.marker_min"),
                                ("flip-smoke", "aa_marker_max", "a pairs block needs flip.aa_marker_max")):
            exp, _ = example(name)
            exp = copy.deepcopy(exp)
            exp["flip"].pop(key)
            e = fb.flip_errors(exp)
            self.assertTrue(any(text.replace("an aa", "a aa") in x for x in e), (name, key, e))

    def test_admin_address_loopback_only(self):
        ok = {"admin": {"address": {"socket_address": {"address": "127.0.0.1", "port_value": 9921}}}}
        envoy_config.check_admin_loopback(ok)
        for bad in ("0.0.0.0", "192.0.2.5", None):
            with self.assertRaises(ValueError):
                envoy_config.check_admin_loopback({"admin": {"address": {"socket_address": {"address": bad}}}})
        import inspect
        src = inspect.getsource(envoy_config.bootstrap)
        self.assertLess(src.index("check_admin_loopback(out)"), src.index('"admin_layer": {}'))

    def errs(self, change):
        exp, _ = example("flip-aa20a")
        exp = copy.deepcopy(exp)
        change(exp)
        return fb.flip_errors(exp)

    def has(self, change, text):
        e = self.errs(change)
        self.assertTrue(any(text in x for x in e), (text, e))

    def test_refusals(self):
        f = lambda **kw: (lambda e: e["flip"].update(kw))  # noqa: E731
        self.has(lambda e: e["arms"][0]["settings"].pop("runtime_admin_layer"), "runtime_admin_layer true")
        self.has(lambda e: e["arms"][0]["settings"].update(runtime={KEY: True}), "one source of truth")
        self.has(f(values={"A": True, "B": False}), "an aa block writes the same value for A and B")
        self.has(f(kind="control", values={"A": True, "B": True}, marker_min=1),
                 "a control block writes different values")
        self.has(f(order="AB AB BA BA AB AB BA BA"), "not the counterbalanced order")
        self.has(f(order="AA BB BA AB"), "every pair of a scored block has one A and one B")
        self.has(f(order="AB"), "at least 2 pairs")
        self.has(f(order="AB CD"), "labels without a value")
        self.has(f(window_s=0), "flip.window_s")
        self.has(f(window_s=2.5), "flip.window_s")
        self.has(f(gap_s=0.5), "flip.gap_s")
        self.has(f(lead_in_s=0), "flip.lead_in_s")
        self.has(f(perf_interval_ms=1000), "perf_interval_ms is for timeline blocks only")
        self.has(f(kind="timeline", values={"A": True, "B": True}), "a timeline block sets flip.perf_interval_ms")
        self.has(f(kind="burst"), "flip.kind must be one of")
        self.has(f(key="otel_tracer_deferred_span"), "flip.key must be a runtime key")
        self.has(f(cycle_connections="yes"), "cycle_connections must be true or false")
        self.has(f(window_items="tcp"), "flip.window_items must be http or bulk")
        self.has(f(window_items="bulk"), "flip.window_items bulk needs a tcp_proxy arm")
        self.has(f(marker_min=None), "an aa block needs flip.marker_min".replace("an aa", "a aa"))
        self.has(f(gates={"max_sd": 1}), "flip.gates takes")
        self.has(f(gates={"reference_lp": [-2, -3]}), "reference_lp is [lo, hi]")
        self.has(f(bogus=1), "flip: unknown keys ['bogus']")
        self.has(lambda e: e.pop("template"), "template true")
        self.has(lambda e: e["arms"].append(dict(e["arms"][0], name="two")), "exactly one arm")
        self.has(lambda e: e["measure"].update(perf=["bash", "wrapper-perf.sh"]), "one perf binary, no wrapper")
        self.has(lambda e: e["measure"].update(perf_events="cycles,task-clock"), "need instructions:u")
        self.has(lambda e: e["cpus"].pop("flip_tools"), "cpus.flip_tools")
        self.has(lambda e: e["client"].update(lifetime="window"), "drives its client itself")
        self.has(lambda e: e["arms"][0].update(client={"binary": "/x", "md5": "0" * 32}), "no arm client settings")
        self.assertEqual(fb.flip_errors({"arms": []})[0], "a flip-block config needs a flip section")

    def test_plan(self):
        exp, _ = example("flip-aa20a")
        order, s = fb.plan(exp)
        self.assertEqual(len(order), 16)
        self.assertAlmostEqual(s, 20 + 5 + 2 + 16 * 22.0)
        rw, _ = example("flip-rw20")
        self.assertGreater(fb.plan(rw)[1], s)  # a new client per window


def win(label, cyc, ins, k=1, **kw):
    w = {"k": k, "label": label, "per_req": {"cycles_total": cyc, "instructions_u": ins}}
    w.update(kw)
    return w


class SummaryTest(unittest.TestCase):
    def test_control_pairs_whatever_the_order(self):
        flip = {"kind": "control", "values": {"A": False, "B": True}, "marker_min": 50,
                "gates": {"max_sd_lp": 1.15, "reference_lp": [-3.77, -2.08]}}
        ws = []
        for i, pair in enumerate(fb.counterbalanced_order(8).split()):
            noise = [0.2, -0.3, 0.1, 0.0, -0.1, 0.25, -0.2, 0.05][i]
            ca = 1000.0
            cb = ca * math.exp((-2.9 + noise) / 100.0)
            for lab in pair:
                ws.append(win(lab, ca if lab == "A" else cb, 2000.0 if lab == "A" else 1880.0))
        s = fb.summarize(ws, flip, True)
        self.assertEqual(s["n"], 8)
        self.assertEqual([p["order"] for p in s["pairs"]], ["AB", "BA", "BA", "AB", "AB", "BA", "BA", "AB"])
        self.assertTrue(all(p["ref"] == "A" for p in s["pairs"]))
        self.assertAlmostEqual(s["pairs"][1]["d_lp"], -3.2, places=3)
        self.assertAlmostEqual(s["mean_lp"], -2.9, places=3)
        self.assertEqual(s["df"], 7)
        hw = 2.3646 * s["sd_lp"] / math.sqrt(8)
        self.assertAlmostEqual(s["t_hw_lp"], hw, places=3)
        self.assertEqual(s["marker_mean_ins_per_req"], 120.0)
        self.assertEqual(s["gates"], {"block_valid": True, "block_sd_within": True, "block_point_negative": True,
                                      "block_excludes_0_overlaps_reference": True, "block_marker": True})
        self.assertEqual(s["basis"], "Exploratory, steering only")
        # the marker below X: the flip did not reach the request path
        s2 = fb.summarize(ws, dict(flip, marker_min=150), True)
        self.assertFalse(s2["gates"]["block_marker"])
        self.assertFalse(fb.summarize(ws, flip, False)["gates"]["block_valid"])

    def test_aa(self):
        flip = {"kind": "aa", "values": {"A": True, "B": True}, "aa_marker_max": 2, "gates": {"max_sd_lp": 0.5}}
        ws = []
        for i, pair in enumerate(fb.counterbalanced_order(4).split()):
            d = [0.6, -0.5, 0.3, -0.4][i]
            for lab in pair:
                ws.append(win(lab, 1000.0 if lab == "A" else 1000.0 * math.exp(d / 100), 2000.0 + (lab == "B")))
        s = fb.summarize(ws, flip, True)
        self.assertTrue(s["gates"]["block_t_interval_contains_0"])
        self.assertFalse(s["gates"]["block_sd_within"])  # SD 0.51 > 0.5
        self.assertTrue(s["gates"]["block_marker"])  # mean |A - B| 1 < 2
        self.assertFalse(fb.summarize(ws, dict(flip, aa_marker_max=1), True)["gates"]["block_marker"])
        # mean |A - B|, not |mean(A - B)|: alternating +-2,000 differences fail the 1,110 bound
        alt = []
        for i, pair in enumerate(fb.counterbalanced_order(4).split()):
            for lab in pair:
                alt.append(win(lab, 1000.0, 2000.0 if lab == "A" else 2000.0 + (2000 if i % 2 else -2000)))
        s3 = fb.summarize(alt, dict(flip, aa_marker_max=1110), True)
        self.assertEqual(s3["marker_mean_ins_per_req"], 0.0)
        self.assertFalse(s3["gates"]["block_marker"])
        self.assertIsNotNone(s["trend_slope_lp_per_pair"])

    def test_pairs_kind_k7(self):
        flip = {"kind": "pairs", "values": {"A": True, "B": True, "C": False, "D": True}, "marker_min": 100,
                "aa_marker_max": 25}
        ws = [win("A", 1000, 1900), win("B", 1001, 1890), win("C", 1000, 2000), win("D", 970, 1880)]
        g = fb.summarize(ws, flip, True)["gates"]
        self.assertEqual(g, {"smoke-pair1-aa": True, "smoke-pair2-control": True, "smoke-valid": True})
        g = fb.summarize(ws, dict(flip, marker_min=None, aa_marker_max=None), True)["gates"]
        self.assertFalse(g["smoke-pair1-aa"] or g["smoke-pair2-control"])  # no X, no bound: fail closed
        self.assertFalse(fb.summarize(ws, dict(flip, aa_marker_max=5), True)["gates"]["smoke-pair1-aa"])

    def test_missing_counts(self):
        ws = [win("A", 1000, 1), {"k": 2, "label": "B", "per_req": None}]
        s = fb.summarize(ws + ws, {"kind": "aa", "values": {"A": 1, "B": 1}}, False)
        self.assertEqual(s["n"], 0)
        self.assertEqual(s["gates"], {})


class WindowVerdictTest(unittest.TestCase):
    def good(self, **kw):
        w = {"k": 1, "window_s": 20, "client_alive_at_q1": True, "client_alive_after_s": 1.01, "envoy_alive": True,
             "responses": 104000.0, "sut_non2xx": 0, "sut_overflow": {}, "perf_rc": 0,
             "per_req": {"cycles_total": 1.0}, "perf_min_running_pct": 100.0, "sut_foreign_cpus": 0.0,
             "sut_sibling_cpus": 0.0, "runtime_value": "true", "value_text": "true"}
        w.update(kw)
        return w

    def test_each_reason(self):
        v = dict(leg.validity.DEFAULTS)
        self.assertEqual(fb.window_verdict(self.good(), 5200, 0.005, v), [])
        cases = [({"client_alive_at_q1": False}, "client not alive at the window's last read"),
                 ({"client_alive_after_s": 0.5}, "1.0 s after"), ({"client_alive_after_s": None}, "1.0 s after"),
                 ({"envoy_alive": False}, "envoy not running"),
                 ({"responses": 104000 * 1.006}, "misses 104000"),
                 ({"sut_non2xx": 3}, "non-2xx 3"), ({"sut_overflow": {"x": 1}}, "overflow"),
                 ({"perf_rc": 1}, "perf exited 1"), ({"per_req": None}, "perf counters missing"),
                 ({"perf_min_running_pct": 80.0}, "multiplexed"),
                 ({"sut_foreign_cpus": None}, "no scheduler run time"),
                 ({"sut_foreign_cpus": 0.2}, "other tasks"), ({"sut_sibling_cpus": 0.2}, "SMT siblings"),
                 ({"runtime_value": "false"}, "/runtime showed 'false'")]
        for over, text in cases:
            r = fb.window_verdict(self.good(**over), 5200, 0.005, v)
            self.assertTrue(any(text in x for x in r), (over, r))

    def test_perf_intervals(self):
        txt = ("# started\n1.000123,1000,,instructions:u,1000000,100.00,,\n1.000123,900,,cycles,1000000,100.00,,\n"
               "2.000200,1100,,instructions:u,1000000,100.00,,\n2.000200,950,,cycles,1000000,99.50,,\n")
        rows, tot, run = fb.parse_perf_intervals(txt)
        self.assertEqual(len(rows), 2)
        self.assertEqual(tot, {"instructions:u": 2100.0, "cycles": 1850.0})
        self.assertEqual(run["cycles"], 99.5)
        self.assertEqual(rows[1]["instructions:u"], 1100.0)


# ---------------------------------------------------------------- stand-ins for an integration run

class Admin:
    """A stand-in Envoy admin: GET /ready /stats /runtime, POST /runtime_modify (an admin layer). The 2xx counter
    grows at `rate` per second; `refuse_post` answers 503; `ignore_after` POSTs leave the value as it was."""

    def __init__(self, rate, initial="true", refuse_post=False, ignore_after=None):
        self.rate, self.t0 = rate, time.monotonic()
        self.values = {KEY: initial}
        self.posts = []
        self.exports_per_s = 0.0
        outer = self

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
                if self.path.startswith("/stats"):
                    n = int(outer.rate * (time.monotonic() - outer.t0))
                    self._send(200, "http.ingress_http.downstream_rq_2xx: %d\nhttp.ingress_http.downstream_rq_5xx: 0\n"
                               "cluster.otel_collector.upstream_rq_total: %d\n"
                               "cluster.otel_collector.upstream_cx_connect_fail: 0\n" % (
                                   n, int(outer.exports_per_s * (time.monotonic() - outer.t0))))
                elif self.path.startswith("/runtime"):
                    self._send(200, json.dumps({"layers": ["epl-admin"], "entries": {
                        k: {"final_value": v, "layer_values": [v]} for k, v in outer.values.items()}}))
                elif self.path.startswith("/ready"):
                    self._send(200, "LIVE\n")
                else:
                    self._send(404, "no")

            def do_POST(self):
                from urllib.parse import parse_qsl, urlsplit
                u = urlsplit(self.path)
                outer.posts.append((time.monotonic(), u.query))
                if u.path != "/runtime_modify":
                    return self._send(404, "no")
                if refuse_post:
                    return self._send(503, "No admin layer specified")
                if ignore_after is None or len(outer.posts) <= ignore_after:
                    outer.values.update(dict(parse_qsl(u.query)))
                self._send(200, "OK\n")

        class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
        self.srv = S(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


CLIENT = r"""
import json, signal, sys, time, datetime
args = sys.argv[1:]
workers = int(args[args.index("--concurrency") + 1])
stop = {"t": None}
signal.signal(signal.SIGTERM, lambda *a: stop.__setitem__("t", time.time()))
iso = lambda t: datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
t0 = time.time()
while stop["t"] is None and time.time() < t0 + 120:
    time.sleep(0.01)
d = "%.6fs" % (stop["t"] - t0)
res = [{"name": "global", "execution_start": iso(t0), "execution_duration": d, "statistics": [],
        "counters": [{"name": "benchmark.http_2xx", "value": "1000"}, {"name": "upstream_cx_total", "value": "8"},
                     {"name": "graceful_stop_requested", "value": str(workers)}]}]
blk = int(sys.argv[-2]) if sys.argv[-2].isdigit() else 0
res += [{"name": "worker_%d" % i, "execution_start": iso(t0), "execution_duration": d,
         "statistics": [{"id": "sequencer.blocking", "count": str(blk if i == 0 else 0)}], "counters": []}
        for i in range(workers)]
print(json.dumps({"results": res}))
"""

PERF = r"""
import json, sys, time, urllib.request
args = sys.argv[1:]
port, key, rate = int(args[0]), args[1], float(args[2])
ms = int(args[args.index("--timeout") + 1])
time.sleep(ms / 1000.0)
v = json.load(urllib.request.urlopen("http://127.0.0.1:%d/runtime" % port))["entries"][key]["final_value"]
on = v == "true"
n = rate * ms / 1000.0
if "-I" in args:
    iv = int(args[args.index("-I") + 1]) / 1000.0
    k = max(1, int(round(ms / 1000.0 / iv)))
    for i in range(k):
        for ev, per in (("instructions:u", 1880.0 if on else 2000.0), ("cycles", 970.0 if on else 1000.0)):
            sys.stderr.write("%.6f,%.0f,,%s,%d,100.00,,\n" % ((i + 1) * iv, per * n / k, ev, iv * 1e9))
    sys.exit(0)
for ev, per in (("instructions:u", 1880.0 if on else 2000.0), ("cycles:u", 600.0 if on else 620.0),
                ("cycles:k", 370.0 if on else 380.0), ("instructions:k", 500.0), ("task-clock", 0.0)):
    val = per * n if ev != "task-clock" else ms * 4.0
    sys.stderr.write("%.0f,,%s,%d,100.00,,\n" % (val, ev, ms * 1000000))
"""


class FakeEnvoy:
    def __init__(self):
        self.pid = os.getpid()

    def poll(self):
        return None


class StandInOps(fb.RealOps):
    """RealOps with the box parts replaced: no Envoy binary, no taskset, no /proc. The admin reads, the POST, the
    client's SIGTERM path (OwnProcesses), the event log and every verdict are the real code."""

    def __init__(self, exp, run_dir, admin, tmp):
        self.exp, self.run_dir, self.log = exp, run_dir, lambda m: None
        self.own = leg.OwnProcesses()
        self.admin_port = admin.port
        self.admin = admin
        self.client_py = os.path.join(tmp, "nh_standin.py")
        self.perf_py = os.path.join(tmp, "perf_standin.py")
        with open(self.client_py, "w") as f:
            f.write(CLIENT)
        with open(self.perf_py, "w") as f:
            f.write(PERF)
        self.started = []

    def preflight(self, shape):
        return True, {"stand-in": True}

    def validate_bootstrap(self, path):
        with open(path) as f:
            b = json.load(f)
        self.bootstrap = b
        return {"ok": True}

    def start_envoy(self, arm, bootstrap):
        return FakeEnvoy()

    def stop_envoy(self, p):
        return 0

    def exe_identity(self, pid, path):
        return {"client_exe_ok": True, "client_exe": path}

    def cpus_ok(self, pid, want):
        return True

    blocking = 0

    def start_client(self, args, out, err):
        p = self.own.start([sys.executable, "-I", self.client_py] + args[:-1] + [str(self.blocking), args[-1]],
                           stdout=out, stderr=err)
        self.started.append(p)
        return p

    def perf_cmd(self, pid, events, window_s, interval_ms=None):
        return [sys.executable, "-I", self.perf_py, str(self.admin.port), KEY, str(self.exp["shapes"][0]["rps"]),
                "stat", "-x", ",", "-e", events, "-p", str(pid), "--timeout", str(int(window_s * 1000))] + (
                    ["-I", str(int(interval_ms))] if interval_ms else [])

    def sched(self, envoy_pid):
        return 0, {0: 0, 40: 0}, None

    def sut_sets(self):
        return {0}, {40}

    def stats(self):
        return leg.admin_stats(self.admin_port, 5.0)


def standin_exp(tmp, **flip):
    exp, _ = example("flip-ctl20a", **{"flip.marker_min": 60.0})
    exp = copy.deepcopy(exp)
    exp["shapes"][0]["rps"] = 400
    exp["client"]["concurrency"] = 2
    exp["measure"]["lead_in_s"] = 0.3
    f = exp["flip"]
    f.update(window_s=1, gap_s=1.0, warm_s=0.2, lead_in_s=0.3, order="AB BA", rate_tolerance=0.05, hang_factor=3.0,
             counterbalanced=False)
    f.update(flip)
    exp["origin"]["port"] = 1
    exp["client"].pop("md5", None)  # the stand-in client is not the pinned binary (the pin check is covered in the harness tests)
    return exp


class FlipBlockStandInTest(unittest.TestCase):
    def run_block(self, admin_kw=None, exports_per_s=0.0, blocking=0, **flip):
        tmp = tempfile.mkdtemp()
        exp = standin_exp(tmp, **flip)
        initial = fb.runtime_text(exp["flip"]["values"]["A"]) if "values" not in flip else "x"
        admin = Admin(exp["shapes"][0]["rps"], initial=initial, **(admin_kw or {}))
        admin.exports_per_s = exports_per_s
        try:
            ops = StandInOps(exp, tmp, admin, tmp)
            ops.blocking = blocking
            res = fb.FlipBlock(exp, os.path.join(tmp, "block"), ops, log=lambda m: None).run()
            res["_dir"] = os.path.join(tmp, "block")
        finally:
            admin.close()
        return res, tmp, ops, admin

    def test_control_block(self):
        res, tmp, ops, admin = self.run_block()
        self.assertTrue(res["valid"], res["reasons"])
        self.assertEqual([w["label"] for w in res["windows"]], ["A", "B", "B", "A"])
        self.assertEqual([w["runtime_value"] for w in res["windows"]], ["false", "true", "true", "false"])
        self.assertTrue(all(w["valid"] for w in res["windows"]))
        # four POSTs: the first value before the client, then one in each of the three gaps
        self.assertEqual([q for _, q in admin.posts], ["%s=false" % KEY, "%s=true" % KEY, "%s=true" % KEY,
                                                       "%s=false" % KEY])
        s = res["summary"]
        self.assertEqual(s["n"], 2)
        want = 100 * math.log((600 + 370) / (620 + 380.0))
        self.assertAlmostEqual(s["mean_lp"], want, delta=0.3)  # the stand-in count has timing noise
        self.assertAlmostEqual(s["marker_mean_ins_per_req"], 120.0, delta=8.0)
        self.assertTrue(s["gates"]["block_marker"])
        self.assertTrue(s["gates"]["block_valid"])
        self.assertEqual(s["gates_label"], "per block, not a build decision (that pools the blocks)")
        # one continuous client, ended by one SIGTERM, output complete, exit 0
        self.assertEqual(len(ops.started), 1)
        c = res["clients"][0]
        self.assertTrue(c["ok"], c["reasons"])
        self.assertEqual(c["exit"], 0)
        self.assertTrue(c["sending"]["ok"])
        self.assertEqual(ops.own.procs, {})
        # the bootstrap had the admin layer; the events and the record are on disk
        self.assertEqual(ops.bootstrap["layered_runtime"]["layers"][-1]["name"], "epl-admin")
        with open(os.path.join(tmp, "block", "events.log")) as f:
            ev = [ln.split() for ln in f]
        names = [x[2] for x in ev]
        for n in ("block_start", "post_sent", "post_answered", "runtime_read", "client_started",
                  "window_perf_start", "window_perf_end", "gap_start", "client_sigterm", "client_exit", "block_end"):
            self.assertIn(n, names)
        self.assertEqual(names.count("window_perf_start"), 4)
        self.assertTrue(all(x[0].endswith("Z") and x[1].isdigit() for x in ev))
        mono = [int(x[1]) for x in ev]
        self.assertEqual(mono, sorted(mono))
        with open(os.path.join(tmp, "block", "block.json")) as f:
            self.assertTrue(json.load(f)["valid"])
        # every flip lands in the gap: after the previous window's perf ended, before the next one started
        posts = [t for t, _ in admin.posts[1:]]
        for i, t in enumerate(posts):
            self.assertGreater(t, res["windows"][i]["t_perf_end"])
            self.assertLess(t, res["windows"][i + 1]["t_perf_start"])

    def test_collector_export_fails_the_block(self):
        res, _, _, _ = self.run_block(exports_per_s=2.0)
        self.assertFalse(res["valid"])
        self.assertTrue(any(r.startswith("cluster.otel_collector.upstream_rq_total over the block:") for r in res["reasons"]),
                        res["reasons"])
        self.assertTrue(all(w["valid"] for w in res["windows"]))  # a block item, not a window item

    def test_client_blocking_fails_the_block(self):
        res, _, _, _ = self.run_block(blocking=3)
        self.assertFalse(res["valid"])
        self.assertTrue(any("client sequencer blocked: {'worker_0': 3}" in r for r in res["reasons"]), res["reasons"])

    def test_timeline_per_nominal_request(self):
        res, _, _, _ = self.run_block(kind="timeline", values={"A": True, "B": True, "C": False, "D": True},
                                      order="AB CD", perf_interval_ms=500, window_s=1)
        self.assertTrue(res["valid"], res["reasons"])
        w = res["windows"][2]  # guard false: 2,000 instructions:u per request
        self.assertEqual(len(w["perf_intervals"]), 2)
        self.assertAlmostEqual(w["perf_intervals"][0]["instructions_u_per_nominal_request"], 2000.0, places=3)
        self.assertEqual(w["perf_intervals_denominator"], "per nominal request (400 req/s, open loop)")
        self.assertFalse(res["summary"]["scored"])
        self.assertEqual(res["summary"]["gates"], {})

    def test_refused_post_fails_the_block(self):
        res, _, ops, _ = self.run_block(admin_kw={"refuse_post": True})
        self.assertFalse(res["valid"])
        self.assertTrue(any("POST /runtime_modify" in r and "503" in r for r in res["reasons"]), res["reasons"])
        self.assertEqual(res["windows"], [])
        self.assertEqual(ops.started, [])  # nothing started before the runtime path was proven

    def test_runtime_mismatch_invalidates_the_window_and_the_block(self):
        res, _, ops, _ = self.run_block(admin_kw={"ignore_after": 1})  # only the first POST takes effect
        self.assertFalse(res["valid"])
        bad = [w for w in res["windows"] if not w["valid"]]
        self.assertEqual([w["k"] for w in bad], [2, 3])
        self.assertTrue(any("/runtime showed 'false' at the window's start, not 'true'" in r for r in res["reasons"]))
        self.assertEqual(ops.own.procs, {})

    def test_cycle_connections(self):
        res, _, ops, admin = self.run_block(cycle_connections=True)
        self.assertTrue(res["valid"], res["reasons"])
        self.assertEqual(len(ops.started), 4)  # a new client per window
        self.assertEqual(len(res["clients"]), 4)
        self.assertTrue(all(c["ok"] and c["exit"] == 0 for c in res["clients"]))
        self.assertEqual(len(admin.posts), 4)
        self.assertEqual(ops.own.procs, {})
        # each flip lands while no client runs: after the previous client's exit, before the next one's start
        with open(os.path.join(res["_dir"], "events.log")) as f:
            ev = [ln.split()[2] for ln in f]
        seq = [x for x in ev if x in ("client_started", "client_exit", "post_answered")]
        self.assertEqual(seq, ["post_answered", "client_started", "client_exit", "post_answered", "client_started",
                               "client_exit", "post_answered", "client_started", "client_exit", "post_answered",
                               "client_started", "client_exit"])


class ReviewFixesTest(unittest.TestCase):
    """The ledger, the signal path and the cycling client on the stand-in block."""

    def setUp(self):
        self.t = FlipBlockStandInTest()

    def test_missing_collector_counter_is_named(self):
        tmp = tempfile.mkdtemp()
        exp = standin_exp(tmp)
        admin = Admin(exp["shapes"][0]["rps"], initial="false")
        try:
            ops = StandInOps(exp, tmp, admin, tmp)
            real = ops.stats
            ops.stats = lambda: {k: v for k, v in real().items() if "otel_collector.upstream_cx_connect_fail" not in k}
            res = fb.FlipBlock(exp, os.path.join(tmp, "block"), ops, log=lambda m: None).run()
        finally:
            admin.close()
        self.assertFalse(res["valid"])
        self.assertIn("collector counter not recorded: cluster.otel_collector.upstream_cx_connect_fail", res["reasons"])

    def test_signal_in_the_warm_up_leaves_no_process(self):
        tmp = tempfile.mkdtemp()
        exp = standin_exp(tmp)
        admin = Admin(exp["shapes"][0]["rps"], initial="false")
        ops = StandInOps(exp, tmp, admin, tmp)
        real_sleep = fb.time.sleep
        calls = []

        def sleep(s):
            calls.append(s)
            if len(calls) == 1:
                raise SystemExit(143)  # the chain's SIGTERM arrives in the client's warm-up
            real_sleep(s)
        fb.time.sleep = sleep
        try:
            with self.assertRaises(SystemExit):
                fb.FlipBlock(exp, os.path.join(tmp, "block"), ops, log=lambda m: None).run()
        finally:
            fb.time.sleep = real_sleep
            admin.close()
        self.assertEqual(len(ops.started), 1)
        self.assertEqual(ops.own.pids(), set())
        self.assertIsNotNone(ops.started[0].poll())
        with open(os.path.join(tmp, "block", "ledger.jsonl")) as f:
            led = [json.loads(x) for x in f]
        self.assertEqual([x["pid"] for x in led], [ops.started[0].pid])
        self.assertTrue(all(k in led[0] for k in ("role", "pid", "start_ticks", "argv", "utc")))

    def test_a_failed_envoy_start_leaves_no_process(self):
        tmp = tempfile.mkdtemp()
        exp = standin_exp(tmp)
        admin = Admin(exp["shapes"][0]["rps"], initial="false")
        ops = StandInOps(exp, tmp, admin, tmp)

        def start_envoy(arm, bootstrap):
            ops.own.start([sys.executable, "-I", "-c", "import time; time.sleep(60)"], role="envoy")
            raise RuntimeError("envoy (bootstrap) not ready (exit None)")
        ops.start_envoy = start_envoy
        try:
            res = fb.FlipBlock(exp, os.path.join(tmp, "block"), ops, log=lambda m: None).run()
        finally:
            admin.close()
        self.assertFalse(res["valid"])
        self.assertEqual(ops.own.pids(), set())
        self.assertTrue(any("stopped by PID" in r for r in res["reasons"]), res["reasons"])

    def test_bulk_window_items(self):
        v = dict(leg.validity.DEFAULTS)
        w = WindowVerdictTest().good(bulk_window={k: 0 for k in fb.BULK_WINDOW_ZEROS}, sut_non2xx=5,
                                     responses=128 * 20.0, window_s=20)
        self.assertEqual(fb.window_verdict(w, 128, 0.01, v, "bulk"), [])  # the HTTP items do not apply
        w["bulk_window"]["cluster.origin.upstream_cx_total"] = 2
        self.assertTrue(any("upstream_cx_total in the window: 2" in x for x in fb.window_verdict(w, 128, 0.01, v,
                                                                                                 "bulk")))
        del w["bulk_window"]["listener.127.0.0.1_10110.downstream_cx_total"]
        self.assertTrue(any("downstream_cx_total in the window: None" in x for x in fb.window_verdict(
            w, 128, 0.01, v, "bulk")))
        rw, errs = example("flip-rw20")
        self.assertEqual(errs, [])
        self.assertEqual((rw["flip"]["window_items"], rw["flip"]["rate_tolerance"]), ("bulk", 0.01))
        rw2 = copy.deepcopy(rw)
        rw2["flip"]["window_items"] = "http"
        self.assertTrue(any("tcp_proxy arm has no HTTP stats" in x for x in fb.flip_errors(rw2)))

    def test_plan_counts_the_hash_in_cycle_mode(self):
        rw, _ = example("flip-rw20")
        order, s = fb.plan(rw)
        self.assertAlmostEqual(s, 20 + 5 + 2 + 16 * (20 + 2.0 + 5 + 2 + 2.0 + 1.0))


if __name__ == "__main__":
    unittest.main()
