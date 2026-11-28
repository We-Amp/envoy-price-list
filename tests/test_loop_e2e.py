"""End to end: epl-agentd as a real process, driven over its stdio MCP channel (one channel, as over the one ssh
session), against the local stand-ins. A full screen (6 instances), an explore session with live steering, and
the teardown paths: stdin EOF mid-step, SIGTERM, the session time limit, a refused start."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from tests.test_loop import KEY, LOOP, ROOT, alive, ledger_pids, spec, standin_cfg


class Session:
    def __init__(self, cfg):
        self.tmp = tempfile.mkdtemp()
        self.cfg = cfg
        self.path = os.path.join(self.tmp, "agentd.json")
        with open(self.path, "w") as f:
            json.dump(cfg, f)
        self.p = subprocess.Popen([sys.executable, "-I", os.path.join(LOOP, "agentd.py"), "--config", self.path,
                                   "--standin"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        self.n = 0

    def rpc(self, method, params=None):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method,
                                       "params": params or {}}) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        m = json.loads(line)
        assert m["id"] == self.n, m
        return m

    def tool(self, name, **a):
        r = self.rpc("tools/call", {"name": name, "arguments": a})["result"]
        return r["structuredContent"], r["isError"]

    def sdir(self):
        wd = self.cfg["workdir"]
        return os.path.join(wd, [d for d in os.listdir(wd) if d.startswith("session-")][0])

    def close(self, timeout=120):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        rc = self.p.wait(timeout)
        self.p.stdout.close()
        self.p.stderr.close()
        return rc


def files_under(root):
    return {os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs}


class EndToEndTest(unittest.TestCase):
    def test_screen_then_explore_then_eof(self):
        wd = os.path.join(tempfile.mkdtemp(), "wd")
        tree_before = files_under(os.path.join(ROOT, "data"))
        s = Session(standin_cfg(wd))
        r = s.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "test", "version": "0"}})
        self.assertEqual(r["result"]["serverInfo"]["name"], "epl-agentd")
        self.assertGreaterEqual(len(s.rpc("tools/list")["result"]["tools"]), 16)
        # a screen: 6 instances, 2 control pairs + 1 A/A pair each, 1 s windows
        p, err = s.tool("screen_start", **spec())
        self.assertFalse(err, p)
        self.assertEqual(p["basis"], "in-process effect, Exploratory")
        self.assertEqual(p["orders"][:2], ["AB BA BC", "CB BA AB"])  # A/A first on instance 2
        p, err = s.tool("screen_step", count=2, wait_s=120)
        self.assertFalse(err, p)
        self.assertEqual((p["instances_run"], p["status"]), (2, "open"))
        r, _ = s.tool("screen_result")
        self.assertEqual(r["status"], "interim")
        # the interim read is blinded
        self.assertTrue(r["reading"].startswith("INTERIM: effects are hidden"))
        self.assertFalse(r["candidate"])
        for k in ("across", "within", "instance_sd_lp", "marker", "aa"):
            self.assertNotIn(k, r)
        self.assertEqual(sorted(r["instances"][0]), ["envoy_pid", "instance", "n_pairs", "ours", "reasons",
                                                     "valid"])
        t, err = s.tool("screen_telemetry", instance=1)
        self.assertTrue(err)
        p, err = s.tool("screen_step", count=4, wait_s=300)
        self.assertFalse(err, p)
        self.assertEqual(p["status"], "complete")
        self.assertTrue(p["result"]["candidate"], p["result"])
        r, _ = s.tool("screen_result")
        self.assertEqual(r["status"], "complete")
        self.assertTrue(r["validity"]["valid"], r["validity"])
        lo, hi = r["across"]["t95_lp"]
        self.assertLess(hi, 0.0)
        self.assertAlmostEqual(r["across"]["mean_lp"], -1.8, delta=0.4)
        self.assertEqual(r["across"]["n"], 6)
        self.assertEqual(r["span_tolerance_ms"], 250.0)  # the tolerance used is printed with the result
        self.assertEqual({i["ours"] is not None for i in r["instances"]}, {True})
        self.assertTrue(r["aa"]["ok"], r["aa"])
        self.assertTrue(r["marker"]["reached"])
        self.assertIn("in-process effect, exploratory", r["reading"].lower())
        self.assertIn("not a published row", r["reading"])
        self.assertTrue(all(i["ours"]["placement_violations"] == [] for i in r["instances"]))
        self.assertTrue(all(i["ours"].get("agentd_cpu_s") is not None for i in r["instances"]))
        t, err = s.tool("screen_telemetry", instance=3, max_rows=5)
        self.assertFalse(err, t)
        self.assertEqual(len(t["timeline"]["rows"]), 5)
        self.assertGreater(t["timeline"]["rows_total"], 5)
        # a second screen cannot extend the first; a new one starts from scratch
        p, err = s.tool("screen_step")
        self.assertTrue(err)
        # explore: one warm Envoy, a flip, live traffic, steering, the merged timeline
        p, err = s.tool("explore_start", arm="si", shape="s")
        self.assertFalse(err, p)
        p, err = s.tool("screen_start", **spec())
        self.assertTrue(err)
        self.assertIn("not idle", p["refused"])
        p, _ = s.tool("runtime_set", key=KEY, value=True)
        self.assertTrue(p["ok"], p)
        p, err = s.tool("runtime_set", key="envoy.reloadable_features.other", value=True)
        self.assertTrue(err)
        p, err = s.tool("traffic_start", rps=3000)
        self.assertFalse(err, p)
        self.assertTrue(p["args"]["uri"].startswith("http://127.0.0.1:"))
        p, err = s.tool("traffic_start", rps=50000)
        self.assertTrue(err)
        t1, err = s.tool("telemetry_read", seconds=3)
        self.assertFalse(err, t1)
        p, err = s.tool("traffic_steer", rps=1000)
        self.assertFalse(err, p)
        t2, _ = s.tool("telemetry_read", seconds=3)

        def rate(t, k):
            # the median bin: the first and last admin deltas cover part of a second (the reads are phase-locked)
            xs = sorted(r[k] for r in t["timeline"]["rows"] if r.get(k))
            return xs[len(xs) // 2] if xs else None
        self.assertAlmostEqual(rate(t1, "envoy_2xx"), 3000, delta=200)
        self.assertAlmostEqual(rate(t2, "envoy_2xx"), 1000, delta=200)
        self.assertIn("benchmark.http_2xx", t1["client_series"])
        self.assertIsNotNone(rate(t1, "client_benchmark_http_2xx"))
        self.assertEqual(t1["basis"], "Exploratory, steering only; not a screen")
        st, _ = s.tool("traffic_status")
        self.assertTrue(st["get_status"]["in_flight"])
        st, _ = s.tool("session_status")
        self.assertEqual(st["state"], "explore")
        # the channel drops with the explore Envoy and its traffic running: full teardown, rc 0
        sd = s.sdir()
        t0 = time.monotonic()
        self.assertEqual(s.close(), 0)
        self.assertLess(time.monotonic() - t0, 60)
        with open(os.path.join(sd, "teardown.json")) as f:
            td = json.load(f)
        self.assertEqual(td["reason"], "eof")
        self.assertIn("explore", td)
        pids = ledger_pids(sd)
        roles = {r for r, _ in pids}
        self.assertTrue({"instance-runner", "envoy", "client", "nighthawk_mcp"} <= roles, roles)
        self.assertFalse([x for x in pids if alive(x[1])])
        with open(os.path.join(sd, "candidates.jsonl")) as f:
            cands = [json.loads(x) for x in f]
        self.assertEqual(len(cands), 1)
        self.assertTrue(cands[0]["candidate"])
        self.assertIn("not a published row", cands[0]["not_published"])
        # it wrote nothing in the harness tree's data
        self.assertEqual(files_under(os.path.join(ROOT, "data")), tree_before)
        with open(os.path.join(sd, "events.log")) as f:
            names = [ln.split()[2] for ln in f]
        for n in ("session_start", "screen_start", "instance_start", "instance_end", "screen_end",
                  "explore_start", "runtime_set", "traffic_start", "traffic_steer", "explore_stop", "session_end"):
            self.assertIn(n, names)

    def test_eof_mid_step_tears_down(self):
        wd = os.path.join(tempfile.mkdtemp(), "wd")
        s = Session(standin_cfg(wd))
        s.rpc("initialize", {})
        p, err = s.tool("screen_start", **spec(window_s=2))
        self.assertFalse(err, p)
        p, err = s.tool("screen_step", count=6, wait_s=0)
        self.assertTrue(p["step_running"])
        time.sleep(4.0)
        sd = s.sdir()
        t0 = time.monotonic()
        self.assertEqual(s.close(), 0)
        self.assertLess(time.monotonic() - t0, 90)
        with open(os.path.join(sd, "teardown.json")) as f:
            td = json.load(f)
        self.assertEqual(td["screen"]["status"], "aborted")
        with open(os.path.join(sd, "scr01", "result.json")) as f:
            res = json.load(f)
        self.assertEqual(res["status"], "aborted")
        self.assertFalse(res["candidate"])
        self.assertFalse(res["validity"]["valid"])
        pids = ledger_pids(sd)
        self.assertTrue(pids)
        self.assertFalse([x for x in pids if alive(x[1])])

    def test_sigterm_and_ttl(self):
        wd = os.path.join(tempfile.mkdtemp(), "wd")
        s = Session(standin_cfg(wd))
        s.rpc("initialize", {})
        p, err = s.tool("explore_start", arm="si", shape="s")
        self.assertFalse(err, p)
        sd = s.sdir()
        s.p.send_signal(signal.SIGTERM)
        self.assertEqual(s.p.wait(60), 143)
        s.close()
        with open(os.path.join(sd, "teardown.json")) as f:
            self.assertEqual(json.load(f)["reason"], "signal %d" % signal.SIGTERM)
        self.assertFalse([x for x in ledger_pids(sd) if alive(x[1])])
        # the session time limit ends a session that nobody closes
        wd2 = os.path.join(tempfile.mkdtemp(), "wd")
        s2 = Session(standin_cfg(wd2, ttl=3))
        s2.rpc("initialize", {})
        s2.tool("explore_start", arm="si", shape="s")
        self.assertEqual(s2.p.wait(60), 4)
        sd2 = s2.sdir()
        s2.close()
        with open(os.path.join(sd2, "teardown.json")) as f:
            self.assertEqual(json.load(f)["reason"], "ttl")
        self.assertFalse([x for x in ledger_pids(sd2) if alive(x[1])])

    def test_idle_limit(self):
        # no message for idle_ttl_s and no step running: rc 5, reason idle
        wd = os.path.join(tempfile.mkdtemp(), "wd")
        cfg = standin_cfg(wd)
        cfg["idle_ttl_s"] = 3
        s = Session(cfg)
        s.rpc("initialize", {})
        p, err = s.tool("explore_start", arm="si", shape="s")
        self.assertFalse(err, p)
        self.assertEqual(s.p.wait(60), 5)
        sd = s.sdir()
        s.close()
        with open(os.path.join(sd, "teardown.json")) as f:
            self.assertEqual(json.load(f)["reason"], "idle")
        self.assertFalse([x for x in ledger_pids(sd) if alive(x[1])])

    def test_exception_still_tears_down(self):
        # serve raising after an Envoy started: teardown runs, rc 6
        wd = os.path.join(tempfile.mkdtemp(), "wd")
        tmp = tempfile.mkdtemp()
        cp = os.path.join(tmp, "agentd.json")
        with open(cp, "w") as f:
            json.dump(standin_cfg(wd), f)
        code = ("import os, sys; sys.path.insert(0, %r); import agentd\n"
                "def bad(d, inp):\n"
                "    d.t_explore_start(arm='si', shape='s')\n"
                "    raise RuntimeError('boom in serve')\n"
                "agentd.serve = bad\n"
                "rc = agentd.main(['--config', %r, '--standin'])\n"
                "os._exit(rc)\n") % (LOOP, cp)
        p = subprocess.run([sys.executable, "-I", "-c", code], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=120)
        self.assertEqual(p.returncode, 6, p.stderr[-500:])
        sd = os.path.join(wd, [x for x in os.listdir(wd) if x.startswith("session-")][0])
        with open(os.path.join(sd, "teardown.json")) as f:
            td = json.load(f)
        self.assertIn("boom in serve", td["reason"])
        self.assertIn("explore", td)
        pids = ledger_pids(sd)
        self.assertIn("envoy", {r for r, _ in pids})
        self.assertFalse([x for x in pids if alive(x[1])])

    def test_refused_start(self):
        s = Session(standin_cfg(os.path.join(ROOT, "data", "loop-refused")))
        self.assertEqual(s.p.wait(30), 2)
        self.assertIn("inside the harness tree", s.p.stderr.read())
        s.close()
        self.assertFalse(os.path.exists(os.path.join(ROOT, "data", "loop-refused")))


if __name__ == "__main__":
    unittest.main()
