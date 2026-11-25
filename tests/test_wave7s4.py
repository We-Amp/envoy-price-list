"""Wave 7 S4: the collector's span printing, the S4 configs, the span comparison, the state and kill-line rules."""
import importlib.util
import json
import os
import tempfile
import unittest

from epl import experiment, origin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S4 = os.path.join(ROOT, "examples", "wave7s4")
CFG = os.path.join(S4, "configs")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mk = _load("w7s4_make_t", os.path.join(S4, "make.py"))
chk = _load("w7s4_check_t", os.path.join(S4, "s4_check.py"))
tbl = _load("w7s4_table_t", os.path.join(S4, "table.py"))
cmp_ = _load("w7s4_cmp_t", os.path.join(S4, "span_compare.py"))
evd = _load("w7s4_evd_t", os.path.join(S4, "s4_evidence.py"))


class Collector(unittest.TestCase):
    def test_debug_spans_adds_the_debug_exporter(self):
        plain = origin.collector_conf(4317, 8888)
        self.assertIn("exporters: [nop]", plain)
        self.assertNotIn("debug", plain)
        dbg = origin.collector_conf(4317, 8888, debug_spans=True)
        self.assertIn("exporters: [nop, debug]", dbg)
        self.assertIn("verbosity: detailed", dbg)
        self.assertIn("port: 8888", dbg)


class Configs(unittest.TestCase):
    def test_generated_configs_are_current_and_load(self):
        for name, c in mk.configs().items():
            with open(os.path.join(CFG, name + ".json")) as f:
                self.assertEqual(json.load(f), json.loads(json.dumps(c)), name)
            exp = experiment.load(os.path.join(CFG, name + ".json"))
            self.assertEqual(experiment.validate(exp, allow_short=True), [], name)

    def test_s4a_arms_binaries_and_order(self):
        exp = experiment.load(os.path.join(CFG, "s4a-otel.json"))
        arms = {a["name"]: a for a in exp["arms"]}
        self.assertEqual(len(arms), 8)
        dfs = "88a127e872851947e849ad580bdb6716f1d9cf25b0e0f77036b70a1a601a266d"
        for n, a in arms.items():
            self.assertEqual(a["source_sha256"] == dfs, n.startswith("patched"), n)
        self.assertEqual(arms["patched-0-guard-off"]["settings"]["runtime"],
                         {"envoy.reloadable_features.otel_tracer_deferred_span": False})
        self.assertNotIn("runtime", arms["patched-0"]["settings"])
        sched = experiment.schedule(exp)
        self.assertEqual(len(sched), 128)
        # one Williams square: every arm in every position once, every ordered pair adjacent once (per shape)
        first = [[a["name"] for r, sh, a in sched if r == rr and sh["name"] == "s"] for rr in range(1, 9)]
        for pos in range(8):
            self.assertEqual(len({o[pos] for o in first}), 8)
        self.assertEqual(len({(o[i], o[i + 1]) for o in first for i in range(7)}), 56)
        # the shape order rotates by round
        lead = [next(sh["name"] for r, sh, a in sched if r == rr) for rr in range(1, 9)]
        self.assertEqual(sorted(set(lead)), ["fh", "s"])
        self.assertTrue(all(lead[i] != lead[i + 1] for i in range(7)))

    def test_s4b_arms(self):
        exp = experiment.load(os.path.join(CFG, "s4b-pgo.json"))
        self.assertEqual([a["name"] for a in exp["arms"]], ["official", "official-A2", "pgolto-trainer", "pgolto-tests"])
        self.assertEqual(len(experiment.schedule(exp)), 64)
        sha = {a["name"]: a["source_sha256"][:8] for a in exp["arms"]}
        self.assertEqual(sha, {"official": "1d64506e", "official-A2": "1d64506e", "pgolto-trainer": "d1b4f16e",
                               "pgolto-tests": "7a47b051"})


def span_log(n, version="v1", status="200", extra=""):
    out = []
    for i in range(n):
        out.append("2026-11-23T10:00:0%d.000Z\tinfo\tResourceSpans #0" % (i % 10))
        out += ["Resource SchemaURL: ", "Resource attributes:", "     -> telemetry.sdk.version: Str(%s)" % version,
                "     -> service.name: Str(epl)", "ScopeSpans #0", "ScopeSpans SchemaURL: ", "InstrumentationScope envoy %s" % version,
                "Span #0", "    Trace ID       : %032x" % (i + 1), "    Parent ID      : ", "    ID             : %016x" % (i + 7),
                "    Name           : ingress", "    Kind           : Server", "    Start time     : 2026-11-23 10:00:00.%06d +0000 UTC" % i,
                "    End time       : 2026-11-23 10:00:00.%06d +0000 UTC" % (i + 5), "    Status code    : Unset", "    Status message : ",
                "Attributes:", "     -> node_id: Str()", "     -> guid:x-request-id: Str(id-%d)" % i,
                "     -> http.status_code: Str(%s)" % status] + ([extra] if extra else []) + [
                    "\t{\"kind\": \"exporter\", \"data_type\": \"traces\", \"name\": \"debug\"}"]
    return "\n".join(out) + "\n"


class SpanCompare(unittest.TestCase):
    def _cmp(self, a, b, ea=None, eb=None):
        with tempfile.TemporaryDirectory() as d:
            pa, pb = os.path.join(d, "a"), os.path.join(d, "b")
            open(pa, "w").write(a)
            open(pb, "w").write(b)
            return cmp_.compare(pa, pb, ea, eb)

    def test_same_spans_from_two_builds(self):
        ok, lines, det = self._cmp(span_log(50, "b2d8"), span_log(52, "ec72"), 50, 52)
        self.assertTrue(ok, lines)
        self.assertEqual(det["volatile"], {"guid:x-request-id": 52})

    def test_differences_are_caught(self):
        self.assertFalse(self._cmp(span_log(50), span_log(50, status="503"))[0])
        self.assertFalse(self._cmp(span_log(50), span_log(50, extra="     -> zone: Str(z)"))[0])
        self.assertFalse(self._cmp(span_log(50), span_log(50), 50, 80)[0])
        self.assertFalse(self._cmp(span_log(50), "")[0])


def leg(shape, arm, rnd, cyc, instr=1000.0):
    return {"shape": shape, "arm": arm, "round": rnd, "leg_id": "r%02d-%s-%s" % (rnd, shape, arm), "target_rps": 1,
            "verdict": {"valid": True}, "per_req": {"cycles_total": cyc, "instructions_u": instr}}


class Rules(unittest.TestCase):
    def test_profile_took_gate(self):
        with tempfile.TemporaryDirectory() as d:
            sd = os.path.join(d, "smoke-s4b-pgo")
            os.makedirs(sd)

            def write(t_s, t_fh):
                with open(os.path.join(sd, "legs.jsonl"), "w") as f:
                    for sh, t in (("s", t_s), ("fh", t_fh)):
                        f.write(json.dumps(leg(sh, "official", 1, 100.0, 1000.0)) + "\n")
                        f.write(json.dumps(leg(sh, "pgolto-tests", 1, 90.0, t)) + "\n")
            write(940.0, 990.0)
            self.assertEqual(chk.check(sd)[1], [])
            write(960.0, 990.0)
            self.assertEqual(len(chk.check(sd)[1]), 1)

    def test_kept_share_from_medians(self):
        legs = []
        for r in range(1, 9):
            legs += [leg("s", "official", r, 500.0 + r), leg("s", "pgolto-trainer", r, 320.0 + r), leg("s", "pgolto-tests", r, 430.0 + r)]
        share, per, (mo, mt, mx) = tbl.kept_share(legs, "s")
        self.assertAlmostEqual(share, 100.0 * (1 - mx / mo) / (1 - mt / mo))
        self.assertTrue(38.0 < share < 40.0)
        self.assertEqual(len(per), 8)

    def test_basis_label_follows_the_three_times_rule(self):
        self.assertEqual(tbl.basis({"log_pct": 0.5}, True, 0.2), "Measured")
        self.assertTrue(tbl.basis({"log_pct": -4.0}, False, 1.2).startswith("Measured (A/A missed"))
        self.assertTrue(tbl.basis({"log_pct": -3.0}, False, 1.2).startswith("Not resolved"))

    def test_evidence_span_rules(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "mech", "ev-span-path"))
            od = os.path.join(d, "mech", "out-ev-span-path")
            os.makedirs(od)

            def write(on, off):
                with open(os.path.join(d, "mech", "ev-span-path", "legs.jsonl"), "w") as f, open(os.path.join(od, "span-check.txt"), "w") as g:
                    pid = 100
                    for sh in ("s", "fh"):
                        for arm, (o, c, df) in (("sym-0", on), ("sym-0-guard-off", off)):
                            pid += 1
                            f.write(json.dumps(dict(leg(sh, arm, 1, 1.0), envoy_pid=pid, responses_raw=1000, sut_non2xx=0,
                                                    client_non2xx={}, evidence={"ok": True, "items": [1]})) + "\n")
                            g.write("OK span-%d samples=90000 symbol_lines=4000 otlp_span_symbols=%d otlp_span_pct=0.1 "
                                    "recording_span_symbols=%d recording_span_pct=0.1 deferred_span_symbols=%d deferred_span_pct=0.2 "
                                    "data_left=0\n" % (pid, o, c, df))
            for on, off, want in (((0, 0, 8), (4, 9, 0), 0), ((1, 0, 8), (4, 9, 0), 2), ((0, 0, 0), (4, 9, 0), 2),
                                  ((0, 0, 8), (0, 9, 0), 2)):
                write(on, off)
                lines, bad = [], []
                evd.part_a(d, lines, bad)
                self.assertEqual(len(bad), want, (on, off, bad))


if __name__ == "__main__":
    unittest.main()
