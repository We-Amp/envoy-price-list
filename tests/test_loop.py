"""epl-agentd (the loop daemon): unit tests of the screen spec and analysis, the telemetry (perf -I without
--timeout, the one-clock timeline, our placement), the MCP surface, and one instance against the stand-ins
(loop/standin/: a fake Envoy admin process, a fake client and a fake perf)."""
import copy
import importlib.util
import json
import math
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from epl import leg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOOP = os.path.join(ROOT, "loop")
STANDIN = os.path.join(LOOP, "standin")
KEY = "envoy.reloadable_features.standin_guard"
sys.path.insert(0, LOOP)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LOOP, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sc = _load("screen")
tm = _load("telemetry")
inst = _load("instance")
agentd = _load("agentd")
fb = sys.modules["flipblock"]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# the stand-in's draws are seeded per instance (seed * 100003 + instance), never by PID. At
# SEED_PASS the 6-instance screen of spec() is a candidate with its A/A interval well inside 0 (mean 0.06 of a
# half-width from 0, by the exact draws); at SEED_AA_FAIL the A/A interval excludes 0 (2.6 half-widths)
SEED_PASS, SEED_AA_FAIL = 4, 160
STANDIN_SPAN_MS = 250.0


def standin_cfg(workdir, effect_lp=-1.8, ttl=600, **standin):
    si = {"key": KEY, "on": "true", "base_cycles": 1000, "effect_lp": effect_lp, "instance_sd_lp": 0.16,
          "noise_lp": 0.15, "marker": 120, "initial": "false", "seed": SEED_PASS}
    si.update(standin)
    # span_tolerance_ms: the stand-in perf is a Python process on a shared workstation; a 55 ms late wake-up was seen
    # once in a 20-run loop (the box keeps 50 ms)
    return {"workdir": workdir, "session_ttl_s": ttl, "housekeeping_cpus": "18-19", "max_rps": 20000,
            "min_window_s": 1, "rate_tolerance": 0.02, "perf_mode": "sleep", "span_tolerance_ms": STANDIN_SPAN_MS,
            "arms": {"si": {"base": os.path.join(STANDIN, "flip-standin.json"), "keys": [KEY],
                            "overrides": {"envoy": {"admin_port": free_port(), "listener_port": free_port()}}}},
            "shapes": {"s": {"body_bytes": 4096, "kind": "proxied", "name": "s", "path": "/s", "rps": 2000},
                       "s2": {"body_bytes": 1024, "kind": "proxied", "name": "s2", "path": "/s", "rps": 2000}},
            "standin": {"envoy": si}}


def spec(**kw):
    s = {"arm": "si", "key": KEY, "off": False, "on": True, "shape": "s", "rate": 2000, "instances": 6, "pairs": 2,
         "aa_pairs": 1, "window_s": 1, "gap_s": 1.0, "warm_s": 0.2, "lead_in_s": 1.0}
    s.update(kw)
    return s


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # a zombie of a process we did not reap counts as gone
        r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
        return bool(r.stdout.strip()) and not r.stdout.strip().startswith("Z")
    except (OSError, subprocess.TimeoutExpired):
        return True


def ledger_pids(root):
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f == "ledger.jsonl":
                with open(os.path.join(dp, f)) as fh:
                    out += [(json.loads(x)["role"], json.loads(x)["pid"]) for x in fh if x.strip()]
    return out


# ---------------------------------------------------------------- spec and instance configs

class SpecTest(unittest.TestCase):
    def setUp(self):
        self.cfg = standin_cfg(tempfile.mkdtemp())

    def has(self, change, text):
        s = spec()
        s.update(change)
        errs = sc.spec_errors(s, self.cfg)
        self.assertTrue(any(text in e for e in errs), (text, errs))

    def test_ok(self):
        self.assertEqual(sc.spec_errors(spec(), self.cfg), [])
        self.assertIsNone(sc.rate_error(self.cfg, spec()))

    def test_refusals(self):
        self.has({"instances": 5}, "floor is 6 short Envoy instances")
        self.has({"instances": 41}, "instances")
        self.has({"pairs": 1}, "pairs")
        self.has({"aa_pairs": 0}, "every screen carries its A/A check")
        self.has({"arm": "other"}, "arm must be one of")
        self.has({"key": "envoy.reloadable_features.not_listed"}, "candidate keys")
        self.has({"on": False}, "off and on must differ")
        self.has({"shape": "x"}, "shape must be one of")
        self.has({"rate": 30000}, "above the daemon's ceiling")
        self.has({"rate": 1.5}, "whole total")
        self.has({"window_s": 0}, "window_s")
        self.has({"window_s": 61}, "window_s")
        self.has({"gap_s": 0.5}, "gap_s")
        self.has({"lead_in_s": 0.5}, "lead_in_s")
        self.has({"marker_min": -1}, "marker_min")
        self.has({"bogus": 1}, "unknown spec keys")
        self.has({"pairs": 3, "instances": 7}, "pairs odd needs an even number of instances")
        self.has({"repeat_of": "x"}, "repeat_of")
        self.assertEqual(sc.spec_errors(spec(pairs=3, instances=6, repeat_of="scr01"), self.cfg), [])
        self.assertIn("min_window_s", json.dumps(self.cfg))
        c = dict(self.cfg, min_window_s=5)
        self.assertTrue(any("window_s" in e for e in sc.spec_errors(spec(), c)))

    def test_read_points(self):
        c = copy.deepcopy(self.cfg)
        c["arms"]["si"]["keys"] = {KEY: {"read_point": "per_config"}}
        self.assertTrue(any("read when a config is built" in e for e in sc.spec_errors(spec(), c)))
        c["arms"]["si"]["keys"] = {KEY: {"read_point": "per_connection"}}
        self.assertTrue(any("needs flip_extra.cycle_connections" in e for e in sc.spec_errors(spec(), c)))
        c["arms"]["si"]["flip_extra"] = {"cycle_connections": True}
        self.assertEqual(sc.spec_errors(spec(), c), [])
        c["arms"]["si"]["keys"] = {KEY: {"read_point": "per_request"}}
        self.assertEqual(sc.arm_keys(c["arms"]["si"]), [KEY])

    def test_rate_must_divide(self):
        self.assertIn("client workers", sc.rate_error(self.cfg, spec(rate=2001)))

    def test_orders(self):
        self.assertEqual(sc.control_order(4, 0), "AB BA BA AB")
        self.assertEqual(sc.control_order(4, 1), "BA AB AB BA")
        self.assertEqual(sc.control_order(2, 0), "AB BA")
        self.assertEqual((sc.aa_order(1, 0), sc.aa_order(1, 1), sc.aa_order(2, 0)), ("BC", "CB", "BC CB"))
        # over two instances A and B take the same mean position for any P (a linear drift cancels)
        for p in (2, 3, 5):
            pos = [sum(i for i, x in enumerate("".join(sc.control_order(p, k).split())) if x == lab)
                   for k in (0, 1) for lab in "AB"]
            self.assertEqual(pos[0] + pos[2], pos[1] + pos[3])

    def test_instance_configs_pass_flipblock(self):
        d = tempfile.mkdtemp()
        for k in range(2):
            raw = sc.instance_raw(self.cfg, spec(pairs=3, aa_pairs=2), "scr01", k, d)
            self.assertEqual(raw["flip"]["values"], {"A": False, "B": True, "C": True})
            self.assertEqual(raw["flip"]["kind"], "pairs")
            self.assertEqual(raw["shapes"][0]["rps"], 2000)
            self.assertEqual(raw["name"], "scr01-i%02d" % (k + 1))
            for r in (raw, sc.control_variant(raw, spec(pairs=3))):
                p = os.path.join(d, "c.json")
                with open(p, "w") as f:
                    json.dump(r, f)
                self.assertEqual(fb.load(p)[1], [])
        # the A/A pairs first on even-numbered instances (k = 1), last on odd-numbered ones
        self.assertEqual(raw["flip"]["order"], "CB BC BA AB AB")
        self.assertEqual(sc.instance_raw(self.cfg, spec(pairs=2, aa_pairs=1), "scr01", 0, d)["flip"]["order"],
                         "AB BA BC")

    def test_planned(self):
        self.assertAlmostEqual(sc.planned_instance_s(spec(window_s=10, gap_s=2.0, warm_s=5.0, lead_in_s=2.0,
                                                          pairs=4)), 27 + 10 * 12)


# ---------------------------------------------------------------- the analysis

def w(label, cyc, ins):
    return {"label": label, "per_req": {"cycles_total": cyc, "instructions_u": ins}}


def block(effect_lp, inst_lp=0.0, pairs=2, k=0, aa_lp=0.0, marker=100.0, valid=True, noise=()):
    ctl, aa = [], []
    noise = list(noise) or [0.0] * pairs
    base = 1000.0 * math.exp(inst_lp / 100)
    for i, pr in enumerate(sc.control_order(pairs, k).split()):
        for lab in pr:
            on = lab == "B"
            ctl.append(w(lab, base * math.exp(((effect_lp + noise[i]) if on else 0.0) / 100),
                         2000.0 - (marker if on else 0.0)))
    for pr in sc.aa_order(1, k).split():
        for lab in pr:
            aa.append(w(lab, base * math.exp((effect_lp + (aa_lp if lab == "C" else 0.0)) / 100),
                        2000.0 - marker))
    ws = aa + ctl if k % 2 else ctl + aa  # instance_raw's order
    return {"valid": valid, "reasons": [] if valid else ["window 3: perf exited 234"], "windows": ws}


class AnalyzeTest(unittest.TestCase):
    INST = [0.10, -0.12, 0.05, 0.0, -0.08, 0.16]

    def blocks(self, effect=-1.8, **kw):
        return [block(effect + o, inst_lp=o * 10, k=k, noise=(0.01, -0.01), **kw) for k, o in enumerate(self.INST)]

    def test_across_instances(self):
        r = sc.analyze(spec(), self.blocks(), "scr01")
        self.assertEqual(r["status"], "complete")
        self.assertTrue(r["validity"]["valid"], r["validity"])
        e = [-1.8 + o for o in self.INST]
        m = sum(e) / 6
        sd = math.sqrt(sum((x - m) ** 2 for x in e) / 5)
        hw = 2.5706 * sd / math.sqrt(6)
        a = r["across"]
        self.assertEqual((a["n"], a["df"]), (6, 5))
        self.assertAlmostEqual(a["mean_lp"], m, places=3)
        self.assertAlmostEqual(a["sd_between_lp"], sd, places=3)
        self.assertAlmostEqual(a["t95_lp"][0], m - hw, places=3)
        self.assertEqual([i["effect_lp"] for i in r["instances"]], [round(x, 4) for x in e])
        self.assertTrue(r["candidate"])
        self.assertTrue(r["reading"].startswith("In-process effect, Exploratory: "))
        self.assertIn("not a published row", r["reading"])
        self.assertEqual(r["basis"], "in-process effect, Exploratory")
        for k in ("instances", "across", "within", "marker", "aa", "validity"):
            self.assertIn(k, r["labels"])
        self.assertTrue(r["marker"]["reached"])
        self.assertTrue(r["aa"]["ok"])
        # the within-instance SD of the noise (0.01, -0.01): about 0.014 lp
        self.assertAlmostEqual(r["within"]["pooled_sd_lp"], 0.0141, places=3)
        self.assertIsNotNone(r["instance_sd_lp"])
        c = sc.candidate_record(r)
        self.assertIn("between-process confirmation", c["kind"])
        self.assertIn("not a published row", c["not_published"])

    def test_null_effect(self):
        r = sc.analyze(spec(), self.blocks(effect=0.0, marker=100.0), "scr01")
        self.assertFalse(r["candidate"])
        self.assertTrue(r["reading"].startswith("No in-process effect resolved (in-process effect, Exploratory)"))
        self.assertIn("MDE", r["reading"])

    def test_invalid_instance_no_replacement(self):
        b = self.blocks()
        b[3] = block(-1.8, k=3, valid=False)
        r = sc.analyze(spec(), b, "scr01")
        self.assertFalse(r["validity"]["valid"])
        self.assertIn("invalid instances [4] (no replacement)", r["validity"]["reasons"])
        self.assertTrue(r["reading"].startswith("Not resolved (in-process effect, Exploratory)"))
        self.assertFalse(r["candidate"])
        self.assertEqual(r["across"]["n"], 5)  # printed over the valid ones, never a candidate

    def assert_blinded(self, r):
        for k in sc.HIDDEN:
            self.assertNotIn(k, r)
        for i in r["instances"]:
            for k in sc.HIDDEN_INSTANCE:
                self.assertNotIn(k, i)
            self.assertIn("valid", i)
        self.assertFalse(r["candidate"])
        self.assertTrue(r["blinded"])
        txt = json.dumps(r)
        self.assertNotIn("-1.8", txt)

    def test_interim_is_blinded(self):
        b = self.blocks()[:3] + [None] * 3
        r = sc.analyze(spec(), b, "scr01")
        self.assertEqual(r["status"], "interim")
        self.assertEqual(r["reading"], "INTERIM: effects are hidden until the screen is complete (3 of 6 instances "
                                       "ran).")
        self.assertFalse(r["validity"]["valid"])
        self.assert_blinded(r)

    def test_aborted_never_shows_effects(self):
        b = self.blocks()[:4] + [None] * 2
        r = sc.analyze(spec(), b, "scr01", "aborted")
        self.assertTrue(r["reading"].startswith("ABORTED after 4 of 6 instances: Not resolved"))
        self.assert_blinded(r)
        c = sc.candidate_record(r, [{"screen": "scr01", "status": "aborted"}], 1)
        self.assertEqual(c["kind"], "screen record, not a candidate")
        self.assertEqual(c["status"], "aborted")
        for k in ("observed_in_process_lp", "t95_lp", "instance_sd_lp", "marker"):
            self.assertNotIn(k, c)
        self.assertEqual(c["screens_in_session"], 1)
        self.assertTrue(c["validity_reasons"])

    def test_marker_sign(self):
        # a key whose on state ADDS instructions reaches marker_min by |marker|, with one sign everywhere
        r = sc.analyze(spec(marker_min=50.0), self.blocks(marker=-100.0), "scr01")
        self.assertTrue(r["marker"]["reached"])
        self.assertEqual(r["marker"]["sign"], "on adds instructions")
        b = self.blocks(marker=100.0)
        b[2] = block(-1.8, k=2, marker=-100.0)
        r = sc.analyze(spec(marker_min=50.0), b, "scr01")
        self.assertEqual(r["marker"]["sign"], "mixed")
        self.assertFalse(r["marker"]["reached"])

    def test_aa_marker_bound_defaults(self):
        b = self.blocks()
        b[0]["windows"][-1]["per_req"]["instructions_u"] += 30  # an A/A |marker| of 30 at instance 1
        r = sc.analyze(spec(marker_min=100.0), b, "scr01")
        self.assertEqual(r["aa"]["marker_bound"], 25.0)  # marker_min / 4
        self.assertFalse(r["aa"]["marker_ok"])
        r = sc.analyze(spec(), self.blocks(), "scr01")
        self.assertIsNone(r["aa"]["marker_ok"])
        self.assertIn("A/A marker unbounded", r["aa"]["marker_bound_rule"])

    def test_record_kinds(self):
        r = sc.analyze(spec(), self.blocks(), "scr02")
        c = sc.candidate_record(r, [{"screen": "scr01", "status": "aborted"}, {"screen": "scr02",
                                                                                 "status": "complete"}], 3)
        self.assertEqual(c["kind"], "candidate for a pre-registered between-process confirmation session")
        self.assertEqual((c["status"], c["screens_in_session"]), ("complete", 3))
        self.assertEqual([x["screen"] for x in c["screens_of_this_key"]], ["scr01", "scr02"])
        self.assertIsNotNone(c["observed_in_process_lp"])
        r = sc.analyze(spec(), self.blocks(effect=0.0), "scr03")
        self.assertEqual(sc.candidate_record(r)["kind"], "screen record, not a candidate")

    def test_aa_fails(self):
        b = [block(-1.8 + o, k=k, aa_lp=0.6 + 0.01 * k) for k, o in enumerate(self.INST)]
        r = sc.analyze(spec(), b, "scr01")
        self.assertFalse(r["aa"]["contains_0"])
        self.assertIn("A/A check failed", r["reading"])
        self.assertFalse(r["candidate"])

    def test_marker(self):
        r = sc.analyze(spec(), self.blocks(marker=0.0), "scr01")
        self.assertFalse(r["marker"]["reached"])
        self.assertTrue(r["reading"].startswith("No marker"))
        r = sc.analyze(spec(marker_min=150.0), self.blocks(marker=100.0), "scr01")
        self.assertFalse(r["marker"]["reached"])
        r = sc.analyze(spec(marker_min=50.0), self.blocks(marker=100.0), "scr01")
        self.assertTrue(r["marker"]["reached"])
        self.assertTrue(r["candidate"])

    def test_aa_marker_bound(self):
        b = self.blocks()
        b[0]["windows"][-1]["per_req"]["instructions_u"] += 900
        r = sc.analyze(spec(aa_marker_max=500.0), b, "scr01")
        self.assertFalse(r["aa"]["marker_ok"])
        self.assertFalse(r["candidate"])

    def test_missing_counts_invalidate(self):
        b = self.blocks()
        b[2]["windows"][0]["per_req"] = None
        r = sc.analyze(spec(), b, "scr01")
        self.assertFalse(r["instances"][2]["valid"])
        self.assertIn("1 of 2 control pairs", r["instances"][2]["reasons"][-1])


# ---------------------------------------------------------------- telemetry

class TelemetryTest(unittest.TestCase):
    def test_perf_cmd_never_timeout(self):
        c = tm.perf_interval_cmd(["/usr/bin/perf"], "cycles:u,instructions:u", 123, 10, "18-19", "sleep")
        self.assertEqual(c[:3], ["taskset", "-c", "18-19"])
        self.assertNotIn("--timeout", c)
        self.assertEqual(c[c.index("-I") + 1], "1000")
        self.assertEqual(c[-3:], ["--", "sleep", "10"])
        c = tm.perf_interval_cmd(["perf"], "cycles", 1, 10, None, "signal")
        self.assertNotIn("--", c)
        self.assertNotIn("--timeout", c)
        with self.assertRaises(ValueError):
            tm.perf_interval_cmd(["perf"], "cycles", 1, 10, None, "timeout")

    def test_parse_and_totals(self):
        txt = ("# started on x\n1.000123,1000,,instructions:u,1000000,100.00,,\n1.000123,900,,cycles:u,1,100.00,,\n"
               "1.000123,90,,cycles:k,1,100.00,,\n2.000200,1100,,instructions:u,1000000,100.00,,\n"
               "2.000200,950,,cycles:u,1,99.50,,\n2.000200,<not counted>,,cycles:k,0,0.00,,\n")
        rows, tot, run = tm.parse_intervals(txt)
        self.assertEqual(len(rows), 2)
        self.assertEqual(tot["instructions:u"], 2100.0)
        self.assertNotIn("cycles:k", tot)  # a missing interval removes the total: the window fails its counts
        self.assertEqual(run["cycles:k"], 0.0)
        self.assertEqual(run["cycles:u"], 99.5)
        pv, prun = leg.parse_perf_full(tm.totals_text(tot, run))
        self.assertEqual(pv, {"cycles:u": 1850.0, "instructions:u": 2100.0})
        self.assertFalse(leg.perf_counts_ok(pv))
        a = tm.absolute_rows(rows, 5 * 10 ** 9, window=3)
        self.assertEqual((a[0]["t_mono_s"], a[0]["t_mid_mono_s"], a[0]["window"]), (6.000123, 5.500062, 3))

    def test_timeline(self):
        perf = [{"t_mono_s": 101.0, "t_mid_mono_s": 100.5, "cycles:u": 600.0, "cycles:k": 400.0,
                 "instructions:u": 2000.0},
                {"t_mono_s": 102.0, "t_mid_mono_s": 101.5, "cycles": 2000.0}]
        adm = [{"t_mono_s": 100.2, "v": {"http.ingress_http.downstream_rq_2xx": 10}},
               {"t_mono_s": 100.9, "v": {"http.ingress_http.downstream_rq_2xx": 12}},
               {"t_mono_s": 101.9, "v": {"http.ingress_http.downstream_rq_2xx": 16}}]
        nh = {"benchmark.http_2xx": [(100.1, 0), (100.8, 3), (101.7, 7)]}
        win = [{"k": 1, "label": "A", "t_perf_start": 100.0, "t_perf_end": 101.0}]
        t = tm.timeline(perf, adm, nh, win, anchor_s=100.0)
        r = {x["bin"]: x for x in t["rows"]}
        self.assertEqual(r[0]["cycles"], 1000.0)
        self.assertEqual(r[0]["envoy_2xx"], 2)
        self.assertEqual(r[0]["cycles_per_request"], 500.0)
        self.assertEqual(r[0]["client_benchmark_http_2xx"], 3)
        self.assertEqual(r[0]["phase"], "w01:A")
        self.assertEqual(r[1]["phase"], "gap")
        self.assertEqual((r[1]["cycles"], r[1]["envoy_2xx"], r[1]["client_benchmark_http_2xx"]), (2000.0, 4, 4))
        self.assertEqual(t["clock"], "CLOCK_MONOTONIC (box)")
        self.assertEqual(tm.timeline([], [], None)["rows"], [])

    def test_placement(self):
        fake = {1: [(1, {18, 19}, 18), (2, {18, 19}, 2)], 2: [(3, {0, 1, 18}, 18)], 3: [(4, {18}, 19)]}
        bad = tm.placement_violations([1, 2, 3], {0, 1, 2, 3, 40, 41}, placement=lambda p: fake[p])
        self.assertEqual([(b["pid"], b["tid"]) for b in bad], [(1, 2), (2, 3)])
        bad = tm.placement_violations([1], {2}, placement=lambda p: fake[p], check_last=False)
        self.assertEqual(bad, [])

    def standin_perf(self, mode, window_s=1.2):
        si = standin_cfg(tempfile.mkdtemp())["standin"]["envoy"]
        port = free_port()
        env = subprocess.Popen([sys.executable, "-I", os.path.join(STANDIN, "envoy.py"), "--admin-port", str(port),
                                "--params", json.dumps(dict(si, rate=1000))])
        try:
            from epl import sysprobe
            self.assertTrue(sysprobe.wait_port("127.0.0.1", port, 10))
            base = [sys.executable, "-I", os.path.join(STANDIN, "perf.py"), "--standin-admin", str(port)]
            cmd = tm.perf_interval_cmd(base, leg.PERF_EVENTS, env.pid, window_s, None, mode, interval_ms=500)
            r = tm.run_perf_window(cmd, window_s, mode)
            # perf 6.8's refusal, kept by the stand-in: --timeout with -I exits 234
            bad = base + ["stat", "-x", ",", "-I", "1000", "-e", "cycles", "-p", "1", "--timeout", "1000"]
            r2 = subprocess.run(bad, capture_output=True, text=True, timeout=10)
        finally:
            env.terminate()
            env.wait(10)
        return r, r2

    def test_run_perf_both_modes(self):
        for mode in ("sleep", "signal"):
            r, r2 = self.standin_perf(mode)
            self.assertEqual(r["rc"], 0, (mode, r))
            rows, tot, run = tm.parse_intervals(r["text"])
            self.assertGreaterEqual(len(rows), 2, mode)
            self.assertTrue(leg.perf_counts_ok(tot))
            self.assertGreater(r["t1_ns"], r["t0_ns"])
            self.assertGreaterEqual(r["cpu_s"], 0.0)
            self.assertEqual(r2.returncode, 234)
            self.assertIn("not supported with interval-print", r2.stderr)

    def test_perf_span_with_startup(self):
        # a 300 ms perf start-up. Signal mode times W from the first interval line, so the span stays W
        for mode in ("sleep", "signal"):
            si = standin_cfg(tempfile.mkdtemp())["standin"]["envoy"]
            port = free_port()
            env = subprocess.Popen([sys.executable, "-I", os.path.join(STANDIN, "envoy.py"), "--admin-port",
                                    str(port), "--params", json.dumps(dict(si, rate=1000))])
            try:
                from epl import sysprobe
                self.assertTrue(sysprobe.wait_port("127.0.0.1", port, 10))
                base = [sys.executable, "-I", os.path.join(STANDIN, "perf.py"), "--standin-admin", str(port),
                        "--standin-startup-ms", "300"]
                cmd = tm.perf_interval_cmd(base, leg.PERF_EVENTS, env.pid, 2, None, mode)
                r = tm.run_perf_window(cmd, 2, mode)
            finally:
                env.terminate()
                env.wait(10)
            rows, _, _ = tm.parse_intervals(r["text"])
            self.assertEqual(r["rc"], 0, mode)
            # a 300 ms start-up is compensated; the bound leaves room for the stand-in's own scheduling on a workstation
            self.assertLess(abs(rows[-1]["t"] - 2.0) * 1000, 100.0, (mode, rows[-1]["t"]))

    def test_perf_stopped_on_an_exception(self):
        # an exception (or a signal) inside the wait never leaves perf behind; start() is the ledger hook
        started = []

        def start(c, **kw):
            p = subprocess.Popen(c, start_new_session=True, **kw)
            started.append(p.pid)
            return p

        def boom(p):
            raise RuntimeError("signalled")
        cmd = tm.perf_interval_cmd([sys.executable, "-I", os.path.join(STANDIN, "perf.py"), "--standin-admin",
                                    "1"], "cycles", 1, 30, None, "signal")
        with self.assertRaises(RuntimeError):
            tm.run_perf_window(cmd, 30, "signal", on_start=boom, start=start)
        self.assertEqual(len(started), 1)
        self.assertFalse(alive(started[0]))

    def test_sampler_phase_lock(self):
        calls = []

        def get(path):
            calls.append(path)
            return 200, "http.ingress_http.downstream_rq_2xx: %d\n" % len(calls)
        s = tm.AdminSampler(get, period_s=0.2).start()
        t0 = tm.mono_ns() / 1e9 + 0.1
        s.lock_window(t0, 3)
        time.sleep(t0 + 1.1 - tm.mono_ns() / 1e9)
        s.start_gap(tm.mono_ns() / 1e9 + 0.1)
        time.sleep(0.5)
        out = s.stop()
        # inside the window [t0, t0 + 3 periods]: exactly 3 reads, at t0 + 0.5 + j periods... with period 0.2 the
        # lock uses 0.5 s offsets: the reads land at t0 + 0.5, + 0.7, + 0.9
        ts = [x["t_mono_s"] for x in out]
        self.assertEqual(sum(1 for t in ts if t0 + 0.45 <= t <= t0 + 0.95), 3)
        self.assertGreaterEqual(len(ts), 4)

    def test_sampler_read_in_flight_at_the_window_start(self):
        # a 100 ms read due 50 ms before lock_window. The lock waits for it, and counting by start time inside
        # perf's span gives exactly W, never W + 1
        def get(path):
            time.sleep(0.1)
            return 200, "http.ingress_http.downstream_rq_2xx: 1\n"
        s = tm.AdminSampler(get, period_s=1.0).start()
        time.sleep(1.05)  # the second free read was due at +1.0 s (50 ms ago) and is in flight until +1.1 s
        t_lock = tm.mono_ns() / 1e9
        s.lock_window(t_lock, 2)
        t_back = tm.mono_ns() / 1e9
        self.assertGreaterEqual(t_back - t_lock, 0.02)  # it waited for the read in flight
        span_start = t_back  # perf starts after lock_window returns
        time.sleep(2.2)
        span_end = span_start + 2.0
        s.start_gap(tm.mono_ns() / 1e9 + 0.5)
        time.sleep(0.3)
        out = s.stop()
        self.assertEqual(tm.reads_in(out, span_start, span_end), 2)
        # a read was in flight when the window was locked (it started before and ended after t_lock), and it is not
        # counted: it started before perf's span
        self.assertTrue(any(x["t_start_mono_s"] < t_lock <= x["t_mono_s"] for x in out))
        # after the window's planned reads, nothing until start_gap
        self.assertFalse([x for x in out if span_start + 1.6 < x["t_start_mono_s"] < span_end + 0.4])

    def test_sampler_skips_a_read_replanned_under_the_lock(self):
        # a read whose schedule changed while it waited for the lock is skipped
        s = tm.AdminSampler(lambda path: (200, "x: 1\n"))
        s._next = 5.0
        self.assertFalse(s._read(due=4.0))
        self.assertEqual(s.samples, [])
        self.assertTrue(s._read(due=5.0))
        self.assertEqual(len(s.samples), 1)

    def test_sampler(self):
        calls = []

        def get(path):
            calls.append(path)
            return 200, "http.ingress_http.downstream_rq_2xx: %d\n" % (10 * len(calls))
        s = tm.AdminSampler(get, period_s=0.1).start()
        time.sleep(0.45)
        out = s.stop()
        self.assertGreaterEqual(len(out), 3)
        self.assertTrue(calls[0].startswith("/stats?filter="))
        self.assertEqual(out[1]["v"]["http.ingress_http.downstream_rq_2xx"], 20)
        ts = [x["t_mono_s"] for x in out]
        self.assertEqual(ts, sorted(ts))


# ---------------------------------------------------------------- the MCP surface (no process started)

class McpSurfaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = agentd.Daemon(standin_cfg(os.path.join(self.tmp, "wd")), lambda o: None, standin=True)

    def call(self, name, **a):
        r = self.d.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name,
                                                                                         "arguments": a}})
        return r["result"]["structuredContent"], r["result"]["isError"]

    def test_initialize_and_list(self):
        r = self.d.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("nothing here is a published row", r["result"]["instructions"])
        names = [t["name"] for t in self.d.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})[
            "result"]["tools"]]
        for n in ("screen_start", "screen_step", "screen_wait", "screen_result", "screen_telemetry", "runtime_set",
                  "traffic_start", "traffic_steer", "traffic_stop", "telemetry_read", "abort", "cleanproof",
                  "session_status", "explore_start", "explore_stop"):
            self.assertIn(n, names)
        for t in agentd.TOOLS.values():
            self.assertFalse(t[1]["additionalProperties"])
        self.assertIsNone(self.d.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(self.d.handle({"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"], -32601)
        self.assertEqual(self.d.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                        "params": {"name": "rm"}})["error"]["code"], -32602)

    def test_refusals_start_nothing(self):
        p, err = self.call("screen_start", **spec(instances=3))
        self.assertTrue(err)
        self.assertIn("floor is 6", p["refused"])
        p, err = self.call("screen_start", **dict(spec(), path="/etc"))
        self.assertTrue(err)
        self.assertIn("unknown arguments ['path']", p["refused"])
        p, err = self.call("screen_step", count="1")
        self.assertIn("count must be integer", p["refused"])
        p, err = self.call("screen_step")
        self.assertIn("no open screen", p["refused"])
        p, err = self.call("runtime_set", key=KEY, value=True)
        self.assertIn("explore_start first", p["refused"])
        # nothing started, no screen directory made
        self.assertLessEqual(set(os.listdir(self.d.sdir)), {"agentd.json", "agentd.log", "events.log",
                                                            "standin.json", "register.json"})
        with open(os.path.join(self.d.sdir, "register.json")) as f:
            reg = json.load(f)
        # the unknown-argument call is refused by the schema check before it reaches the register
        self.assertEqual([(r["screen"], r["status"]) for r in reg["screens"]], [("ref01", "refused")])
        self.assertEqual(p["basis"], "session control")
        self.assertIn("ttl_left_s", p)
        st, _ = self.call("session_status")
        self.assertEqual(st["state"], "idle")
        cp, _ = self.call("cleanproof")
        self.assertEqual(cp["proof"], "CLEAN")

    def tearDown(self):
        self.d.close()

    def test_refuses_a_workdir_in_the_tree(self):
        wd = os.path.join(ROOT, "data", "loop-should-not-exist")
        self.assertIn("inside the harness tree", agentd.workdir_error(wd))
        with self.assertRaises(ValueError):
            agentd.Daemon(standin_cfg(wd), None, standin=True)
        self.assertFalse(os.path.exists(wd))
        self.assertIsNone(agentd.workdir_error(self.tmp))


class DaemonRulesTest(unittest.TestCase):
    """The register and the blinding, a live previous daemon, the idle limit, the teardown, no replacement of an
    instance, the set-aside refused directory, the housekeeping CPUs and the login sessions, in-process with the
    stand-ins (no instance is run unless the test says so)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = standin_cfg(os.path.join(self.tmp, "wd"))
        self.d = agentd.Daemon(self.cfg, lambda o: None, standin=True)

    def tearDown(self):
        self.d.close()

    def call(self, name, **a):
        r = self.d.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name,
                                                                                         "arguments": a}})
        return r["result"]["structuredContent"], r["result"]["isError"]

    def test_register_and_repeat_of(self):
        p, err = self.call("screen_start", **spec())
        self.assertFalse(err, p)
        self.assertEqual(p["screen"], "scr01")
        # no telemetry of the open screen
        t, err = self.call("screen_telemetry", instance=1)
        self.assertTrue(err)
        self.assertIn("released when the screen ends", t["refused"])
        r, _ = self.call("screen_result")
        self.assertTrue(r["blinded"])
        self.call("abort")
        r, _ = self.call("screen_result", screen="scr01")
        self.assertEqual(r["status"], "aborted")
        self.assertNotIn("across", r)
        # the same key again: refused without repeat_of, accepted with it
        p, err = self.call("screen_start", **spec())
        self.assertTrue(err)
        self.assertIn("names repeat_of", p["refused"])
        p, err = self.call("screen_start", **spec(repeat_of="scr07"))
        self.assertTrue(err)
        p, err = self.call("screen_start", **spec(repeat_of="scr01"))
        self.assertFalse(err, p)
        self.assertEqual(p["screen"], "scr02")
        self.call("abort")
        # another rate (a rung of a rate ladder) and the same values written as text are the same
        # (arm, key, shape): refused without repeat_of; the rung names the screen it repeats
        p, err = self.call("screen_start", **spec(rate=4000, off="false", on="true"))
        self.assertTrue(err)
        p, err = self.call("screen_start", **spec(rate=4000, off="false", on="true", repeat_of="scr02"))
        self.assertFalse(err, p)
        self.assertEqual(p["screen"], "scr03")
        self.call("abort")
        # another shape needs no repeat_of
        p, err = self.call("screen_start", **spec(shape="s2"))
        self.assertFalse(err, p)
        self.call("abort")
        with open(os.path.join(self.d.sdir, "candidates.jsonl")) as f:
            recs = [json.loads(x) for x in f]
        self.assertEqual([r["screen"] for r in recs], ["scr01", "scr02", "scr03", "scr04"])
        self.assertEqual([(x["screen"], x["status"]) for x in recs[1]["screens_of_this_key"]],
                         [("scr01", "aborted"), ("ref01", "refused"), ("ref02", "refused"), ("scr02", "aborted")])
        self.assertEqual(recs[1]["repeat_of"], "scr01")
        self.assertTrue(all(r["status"] == "aborted" and "observed_in_process_lp" not in r for r in recs))
        self.assertEqual(recs[3]["screens_in_session"], 7)  # the family size counts the refused attempts too
        self.assertEqual(recs[3]["screens_of_this_key"][0]["screen"], "scr04")
        with open(os.path.join(self.d.sdir, "register.json")) as f:
            reg = json.load(f)
        self.assertEqual([(r["screen"], r["status"]) for r in reg["screens"]],
                         [("scr01", "aborted"), ("ref01", "refused"), ("ref02", "refused"), ("scr02", "aborted"),
                          ("ref03", "refused"), ("scr03", "aborted"), ("scr04", "aborted")])
        # the values are normalised as Envoy gets them: False and "false" are one
        self.assertEqual({(r["off"], r["on"]) for r in reg["screens"]}, {("false", "true")})
        self.assertEqual(reg["screens"][5]["rate"], 4000)
        rung = [x for x in recs[2]["screens_of_this_key"] if x["screen"] == "scr03"][0]
        self.assertEqual((rung["rate"], rung["repeat_of"]), (4000, "scr02"))

    def test_refused_start_after_mkdir_does_not_block(self):
        # a failure after the screen directory exists sets it aside; the next screen gets the next id
        orig = self.d.side_start
        self.d.side_start = lambda c, d: (_ for _ in ()).throw(agentd.ToolError("side services failed"))
        p, err = self.call("screen_start", **spec())
        self.assertTrue(err)
        self.assertTrue(os.path.isdir(os.path.join(self.d.sdir, "scr01.refused")))
        self.assertEqual(self.d.register[-1]["screen"], "scr01.refused")
        self.d.side_start = orig
        p, err = self.call("screen_start", **spec())
        self.assertFalse(err, p)
        self.assertEqual(p["screen"], "scr02")
        self.call("abort")

    def test_abort_steps_are_isolated(self):
        # an analysis that raises does not skip the ledger stop or the side stop
        p, err = self.call("screen_start", **spec())
        self.assertFalse(err)
        side = os.path.join(self.d.screen["dir"], "side.json")
        with open(side, "w") as f:
            json.dump({"containers": []}, f)
        stopped, ledgers = [], []
        self.d.side_stop = lambda st: stopped.append(st) or 0
        orig_an, orig_stop = sc.analyze, agentd.ledger.stop
        sc.analyze = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("analysis broke"))
        agentd.ledger.stop = lambda paths, grace_s=10.0: ledgers.append(paths) or 0
        try:
            out = self.d.abort_all("test")
        finally:
            sc.analyze, agentd.ledger.stop = orig_an, orig_stop
        self.assertTrue(any("analysis broke" in e for e in out["errors"]), out)
        self.assertTrue(ledgers)
        self.assertIn(side, stopped)
        self.assertIsNone(self.d.screen)

    def test_daemon_error_is_no_replacement(self):
        # an exception in the step thread marks the instance invalid and advances; an existing instance
        # directory is never run again
        p, _ = self.call("screen_start", **spec())
        scr = self.d.screen
        os.makedirs(os.path.join(scr["dir"], "i01"))
        self.d._run_instances(scr, 1)
        self.assertEqual(scr["next"], 1)
        self.assertFalse(scr["blocks"][0]["valid"])
        self.assertIn("already exists", scr["blocks"][0]["reasons"][0])
        orig = self.d.ours
        n = {"k": 0}

        def ours():
            n["k"] += 1
            if n["k"] == 1:
                raise OSError("/proc race")
            return orig()
        self.d.ours = ours
        self.d._run_instances(scr, 1)
        self.assertEqual(scr["next"], 2)
        self.assertIn("daemon error: OSError: /proc race", scr["blocks"][1]["reasons"][0])
        self.d.ours = orig
        self.call("abort")

    def test_previous_daemon_alive_refuses(self):
        # a previous session's agentd.json whose pid and start ticks verify
        prev = os.path.join(self.d.workdir, "session-19700101T000000Z-1")
        os.makedirs(prev)
        with open(os.path.join(prev, "agentd.json"), "w") as f:
            json.dump({"pid": os.getpid(), "start_ticks": leg.proc_start_ticks(os.getpid())}, f)
        orig = agentd.ledger.verified
        agentd.ledger.verified = lambda e: e.get("pid") == os.getpid() and "role" not in e
        try:
            errs = self.d.startup_errors()
        finally:
            agentd.ledger.verified = orig
        self.assertTrue(any("a previous epl-agentd (pid %d" % os.getpid() in e for e in errs), errs)

    @unittest.skipUnless(os.path.exists("/proc/self/stat"), "start ticks need /proc (Linux)")
    def test_previous_daemon_alive_refuses_real_ticks(self):
        prev = os.path.join(self.d.workdir, "session-19700101T000000Z-1")
        os.makedirs(prev)
        with open(os.path.join(prev, "agentd.json"), "w") as f:
            json.dump({"pid": os.getpid(), "start_ticks": leg.proc_start_ticks(os.getpid())}, f)
        self.assertTrue(any("a previous epl-agentd" in e for e in self.d.startup_errors()))

    def test_idle_limit(self):
        d = self.d
        d.idle_ttl = 10.0
        now = d.last_msg
        self.assertFalse(d.idle_expired(now + 5))
        self.assertTrue(d.idle_expired(now + 11))

        class T:
            def is_alive(self):
                return True
        # a running step inside its planned time plus the guard is not cut
        d.screen = {"thread": T(), "step_deadline": now + 100}
        self.assertFalse(d.idle_expired(now + 50))
        self.assertTrue(d.idle_expired(now + 101))
        d.screen = None
        bad = agentd.Daemon(dict(self.cfg, idle_ttl_s=0), None, standin=True)
        self.assertTrue(any("idle_ttl_s" in e for e in bad.startup_errors()))
        bad.close()

    def test_span_tolerance_config(self):
        self.assertEqual(self.d.span_tol_ms, STANDIN_SPAN_MS)
        with open(os.path.join(self.d.sdir, "agentd.json")) as f:
            self.assertEqual(json.load(f)["span_tolerance_ms"], STANDIN_SPAN_MS)
        # the box example states the box's 50 ms explicitly
        with open(os.path.join(LOOP, "agentd.example.json")) as f:
            self.assertEqual(json.load(f)["span_tolerance_ms"], 50)
        c = copy.deepcopy(self.cfg)
        c.pop("standin")
        c["workdir"] = os.path.join(self.tmp, "wd3")
        c["span_tolerance_ms"] = 250
        d = agentd.Daemon(c, None, standin=False)
        try:
            self.assertTrue(any("span_tolerance_ms must be 10..100" in e for e in d.startup_errors()))
        finally:
            d.close()

    def test_housekeeping_cpus_required(self):
        # no default: a config without housekeeping_cpus is refused, by the daemon and by its entry point
        c = copy.deepcopy(self.cfg)
        c.pop("housekeeping_cpus")
        c["workdir"] = os.path.join(self.tmp, "wd4")
        with self.assertRaises(ValueError) as cm:
            agentd.Daemon(c, None, standin=True)
        self.assertIn("no housekeeping_cpus", str(cm.exception))
        p = os.path.join(self.tmp, "nohk.json")
        with open(p, "w") as f:
            json.dump(c, f)
        r = subprocess.run([sys.executable, "-I", os.path.join(LOOP, "agentd.py"), "--config", p, "--standin"],
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("no housekeeping_cpus", r.stderr)
        self.assertEqual(r.stdout, "")
        with open(os.path.join(LOOP, "agentd.example.json")) as f:
            self.assertIn("housekeeping_cpus", json.load(f))

    def test_default_workdir_is_under_epl_home(self):
        self.assertEqual(agentd.default_workdir("/x/epl"), "/x/epl/runs/loop")

    def test_housekeeping_overlap_with_client_cpus(self):
        # not stand-in: the CPU checks run
        c = copy.deepcopy(self.cfg)
        c.pop("standin")
        c["workdir"] = os.path.join(self.tmp, "wd2")
        c["arms"]["si"]["overrides"]["cpus"] = {"client": "18-19,60-71", "flip_tools": "18-19", "sut": "0-3",
                                                "origin": "32-39"}
        d = agentd.Daemon(c, None, standin=False)
        try:
            errs = d.startup_errors()
        finally:
            d.close()
        self.assertTrue(any("touch cpus.client" in e for e in errs), errs)
        with open(os.path.join(d.sdir, "agentd.json")) as f:
            self.assertIn("lscpu_e", json.load(f))

    def test_user_sessions(self):
        orig = agentd.subprocess.run

        class R:
            returncode = 0
            stdout = "  12 %d bench  - pts/0\n  13 0 root\n" % os.getuid()
        agentd.subprocess.run = lambda *a, **k: R()
        try:
            s = agentd.user_sessions()
        finally:
            agentd.subprocess.run = orig
        self.assertEqual([x["session"] for x in s], ["12"])
        st, _ = self.call("session_status")
        self.assertIn("logins", st)
        self.assertIn("register", st)


def run_screen_parallel(seed, n=6):
    """The 6 instances of spec() as 6 runner processes at once (each on its own admin port), at a pinned seed;
    returns the complete screen's analysis."""
    tmp = tempfile.mkdtemp()
    cfg = standin_cfg(tmp, seed=seed)
    sip = os.path.join(tmp, "standin.json")
    with open(sip, "w") as f:
        json.dump(cfg["standin"], f)
    procs, outs = [], []
    for k in range(n):
        raw = sc.instance_raw(cfg, spec(instances=n), "scr01", k, tmp)
        raw["envoy"]["admin_port"], raw["envoy"]["listener_port"] = free_port(), free_port()
        p = os.path.join(tmp, "i%02d.json" % (k + 1))
        with open(p, "w") as f:
            json.dump(raw, f)
        out = os.path.join(tmp, "i%02d" % (k + 1))
        outs.append(out)
        procs.append(subprocess.Popen([sys.executable, "-I", os.path.join(LOOP, "instance.py"), p, "--out", out,
                                       "--standin", sip, "--span-tolerance-ms", str(STANDIN_SPAN_MS)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL))
    for p in procs:
        p.wait(120)
    blocks = []
    for out in outs:
        with open(os.path.join(out, "block.json")) as f:
            blocks.append(json.load(f))
    return sc.analyze(spec(instances=n), blocks, "scr01", "complete")


class PinnedSeedTest(unittest.TestCase):
    def test_aa_fails_at_its_pinned_seed(self):
        # the Not-resolved path of the in-screen A/A check, on real stand-in instances
        r = run_screen_parallel(SEED_AA_FAIL)
        self.assertTrue(r["validity"]["valid"], r["validity"])
        self.assertFalse(r["aa"]["contains_0"], r["aa"])
        self.assertIn("the in-screen A/A check failed", r["reading"])
        self.assertFalse(r["candidate"])

    def test_pass_seed_is_a_candidate(self):
        r = run_screen_parallel(SEED_PASS)
        self.assertTrue(r["aa"]["contains_0"], r["aa"])
        self.assertTrue(r["candidate"], r["reading"])


# ---------------------------------------------------------------- one instance against the stand-ins

class InstanceStandInTest(unittest.TestCase):
    def make(self, **kw):
        tmp = tempfile.mkdtemp()
        cfg = standin_cfg(tmp, **kw)
        raw = sc.instance_raw(cfg, spec(), "scr01", 0, tmp)
        p = os.path.join(tmp, "i01.json")
        with open(p, "w") as f:
            json.dump(raw, f)
        sip = os.path.join(tmp, "standin.json")
        with open(sip, "w") as f:
            json.dump(cfg["standin"], f)
        return tmp, p, cfg["standin"], sip

    def test_valid_instance(self):
        tmp, p, si, _ = self.make()
        res, rc = inst.run_instance(p, os.path.join(tmp, "i01"), "sleep", si, span_tol_ms=STANDIN_SPAN_MS)
        self.assertEqual(rc, 0, res["reasons"])
        self.assertTrue(res["valid"])
        self.assertEqual([x["label"] for x in res["windows"]], ["A", "B", "B", "A", "B", "C"])
        self.assertEqual([x["runtime_value"] for x in res["windows"]], ["false", "true", "true", "false", "true",
                                                                         "true"])
        ctl, mk, aa, _ = sc.instance_figures(res, 2)
        self.assertEqual(len(ctl), 2)
        for d in ctl:
            self.assertAlmostEqual(d, -1.8, delta=0.6)
        self.assertAlmostEqual(sum(mk) / 2, 120.0, delta=10.0)
        self.assertAlmostEqual(aa[0], 0.0, delta=0.6)
        lp = res["loop"]
        self.assertEqual(lp["basis"], "in-process effect, Exploratory")
        self.assertEqual(lp["ours"]["placement_violations"], [])
        self.assertGreater(lp["per_second_rows"], 4)
        with open(os.path.join(tmp, "i01", "telemetry.json")) as f:
            t = json.load(f)
        self.assertEqual(len(t["perf_runs"]), 6)
        self.assertTrue(all(r["rc"] == 0 and r["intervals"] >= 1 for r in t["perf_runs"]))
        self.assertIn("not available with the adopted nighthawk_client", t["client_snapshots"])
        phases = {r["phase"] for r in t["timeline"]["rows"]}
        self.assertTrue({"w01:A", "w02:B"} <= phases, phases)
        roles = [r for r, _ in ledger_pids(os.path.join(tmp, "i01"))]
        self.assertEqual(sorted(set(roles)), ["client", "envoy", "perf"])  # perf is in the ledger
        self.assertEqual(roles.count("perf"), 6)
        self.assertEqual(lp["admin_reads_in_window"], [1] * 6)  # phase-locked, W reads per window
        for r in t["perf_runs"]:
            self.assertLess(abs(r["perf_span_minus_W_ms"]), STANDIN_SPAN_MS)
            self.assertGreaterEqual(r["anchor_end_s"], r["anchor_start_s"])
        self.assertFalse(any(alive(pid) for _, pid in ledger_pids(os.path.join(tmp, "i01"))))

    def test_placement_violation_invalidates(self):
        tmp, p, si, _ = self.make()
        orig = inst.LoopOps.__dict__["placement"]
        inst.LoopOps.placement = staticmethod(lambda pid: [(pid, {0, 18}, 0)])
        try:
            res, rc = inst.run_instance(p, os.path.join(tmp, "i01"), "sleep", si)
        finally:
            inst.LoopOps.placement = orig  # the staticmethod object itself
        self.assertEqual(rc, 3)
        self.assertTrue(any("ours on a SUT CPU or a SUT sibling" in r for r in res["reasons"]), res["reasons"])

    def test_signal_mid_instance_leaves_nothing(self):
        # signal mode, 4 s windows: the SIGTERM lands inside a window, where the stand-in perf would run
        # until a SIGINT; the runner's finally must stop it
        tmp = tempfile.mkdtemp()
        cfg = standin_cfg(tmp)
        raw = sc.instance_raw(cfg, spec(window_s=4), "scr01", 0, tmp)
        p = os.path.join(tmp, "i01.json")
        with open(p, "w") as f:
            json.dump(raw, f)
        sip = os.path.join(tmp, "standin.json")
        with open(sip, "w") as f:
            json.dump(cfg["standin"], f)
        out = os.path.join(tmp, "i01")
        r = subprocess.Popen([sys.executable, "-I", os.path.join(LOOP, "instance.py"), p, "--out", out,
                              "--standin", sip, "--perf-mode", "signal"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        time.sleep(4.5)
        r.send_signal(signal.SIGTERM)
        rc = r.wait(60)
        self.assertNotEqual(rc, 0)
        with open(os.path.join(out, "block.json")) as f:
            b = json.load(f)
        self.assertFalse(b["valid"])
        self.assertIn("aborted: the runner was signalled", b["reasons"])
        pids = ledger_pids(out)
        self.assertIn("perf", {r for r, _ in pids})
        self.assertFalse(any(alive(pid) for _, pid in pids), pids)

    def test_span_off_w_invalidates_the_window(self):
        tmp, p, si, _ = self.make()
        exp, _ = fb.load(p)
        ops = inst.StandInLoopOps(exp, tmp, lambda m: None, si)
        ops.setup_loop("sleep", set())
        ops._pending = 1.0
        txt = "0.500000,10,,cycles,1,100.00,,\n1.200000,10,,cycles,1,100.00,,\n1.200000,5,,instructions:u,1,100.00,,\n"
        orig = tm.run_perf_window

        class P:
            pid = 1
        tm.run_perf_window = lambda *a, **k: {"rc": 0, "rc_raw": 0, "text": txt, "t0_ns": 10 ** 9,
                                              "t1_ns": 3 * 10 ** 9, "pid": 1, "proc": P(), "cpu_s": 0.0}
        try:
            ops.own.stop = lambda p: None
            rc, why = ops.run_perf(["perf"], 30)
        finally:
            tm.run_perf_window = orig
        self.assertEqual(rc, inst.SPAN_RC)
        self.assertIn("+200.0 ms off", why)
        self.assertEqual(ops.perf_runs[-1]["perf_span_minus_W_ms"], 200.0)
        # anchored at the reap: t1 - last interval time
        self.assertEqual(ops.perf_runs[-1]["anchor_end_s"], 1.8)


if __name__ == "__main__":
    unittest.main()
