"""Wave 8 W8-2: the configs, the arms' guards, the QUIC statistics setting, and the state rules on made-up legs."""
import importlib.util
import json
import os
import tempfile
import unittest

from epl import envoy_config, experiment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "examples", "wave8w2")
CFG = os.path.join(G, "configs")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


chk = _load("w8w2_check_test", os.path.join(G, "w2_check.py"))
mk = chk.mk
PIN_A = "46c98673eddc4f480cfc79cf8b6cfb620b6fec97245dcc0332535d43475d3971"
PIN_O = "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc"


class Configs(unittest.TestCase):
    def test_configs_match_make(self):
        made = mk.configs()
        self.assertEqual(sorted(made), sorted(f[:-5] for f in os.listdir(CFG)))
        for name, c in made.items():
            with open(os.path.join(CFG, name + ".json")) as f:
                self.assertEqual(json.load(f), json.loads(json.dumps(c)), name)

    def test_pins_and_guards(self):
        self.assertEqual(mk.BINS["w8-A"]["source_sha256"], PIN_A)
        self.assertEqual(mk.BINS["official"]["source_sha256"], PIN_O)
        self.assertEqual(mk.GUARDS["h3-off"], {"ch": 1, "st": 0, "ru": 0})
        self.assertEqual(mk.GUARDS["h3-stop-on"], {"ch": 1, "st": 1, "ru": 0})
        self.assertEqual(mk.GUARDS["h3-both-on"], {"ch": 1, "st": 1, "ru": 1})
        self.assertEqual(mk.GUARDS["h3-reuse-on"], {"ch": 1, "st": 0, "ru": 1})
        for a in ("h2tls", "h3-official", "h3-official-A2"):
            self.assertEqual(mk.GUARDS[a], {"ch": -1, "st": -1, "ru": -1})

    def test_scored_runs(self):
        for name, shape, rps in (("s-1", "s", 2000), ("s-2", "s", 2000), ("shi", "s-hi", 6000), ("shi-half", "s-hi", 3008)):
            exp = experiment.load(os.path.join(CFG, name + ".json"))
            sched = experiment.schedule(exp)
            self.assertEqual(len(sched), 36)
            self.assertEqual({s["name"] for _, s, _ in sched}, {shape})
            self.assertEqual({s["rps"] for _, s, _ in sched}, {rps})
            self.assertEqual(exp["order"], "williams")
            self.assertEqual([a["name"] for a in exp["arms"]], mk.SCORED)
            for a in exp["arms"]:
                build, h3, g = mk.ARMS[a["name"]]
                self.assertEqual(a["source_sha256"], PIN_O if build == "official" else PIN_A)
                rt = (a["settings"].get("runtime") or {})
                if g is None:
                    self.assertEqual(rt, {})
                else:
                    self.assertEqual(rt, {mk.CH: True, mk.ST: g[1], mk.RU: g[2]})
                self.assertEqual(a["settings"]["quic"], {})
                self.assertEqual("http3" in a["client"]["extra_args"], h3)
            # every arm once per round, every position once per arm over the square, each arm after each other once
            pos, follows = {}, set()
            for r in range(1, 7):
                order = [a["name"] for rr, _, a in sched if rr == r]
                self.assertEqual(sorted(order), sorted(mk.SCORED))
                for i, a in enumerate(order):
                    pos.setdefault(a, set()).add(i)
                    if i:
                        follows.add((order[i - 1], a))
            self.assertTrue(all(len(v) == 6 for v in pos.values()))
            self.assertEqual(len(follows), 30)
        a = [x for _, _, x in experiment.schedule(experiment.load(os.path.join(CFG, "s-1.json")))]
        b = [x for _, _, x in experiment.schedule(experiment.load(os.path.join(CFG, "s-2.json")))]
        self.assertNotEqual([x["name"] for x in a], [x["name"] for x in b])

    def test_mech_and_loss(self):
        e = experiment.load(os.path.join(CFG, "mech-sys-s.json"))
        self.assertEqual([a["name"] for _, _, a in experiment.schedule(e)], mk.MECH_S)
        self.assertIn("wave8w2/perf-sys.sh", " ".join(e["measure"]["perf"]) if isinstance(e["measure"]["perf"], list) else e["measure"]["perf"])
        self.assertFalse(any("ref" in it for a in e["arms"] for it in a["evidence"]))
        k = experiment.load(os.path.join(CFG, "mech-kcg-s.json"))
        self.assertEqual([a["name"] for a in k["arms"]], mk.KCG)
        lo = experiment.load(os.path.join(CFG, "loss-s.json"))
        self.assertTrue(all(a["settings"]["quic"] == {"stats": True} for a in lo["arms"]))
        for name in ("s-1", "s-2", "shi", "shi-half", "smoke-s", "mech-sys-s", "mech-kcg-s"):
            ex = experiment.load(os.path.join(CFG, name + ".json"))
            self.assertTrue(all(a["settings"]["quic"] == {} for a in ex["arms"]), name)

    def test_quic_stats_setting(self):
        hcm = {"codec_type": "HTTP2", "stat_prefix": "ingress_http"}
        cfg = {"tls": {"cert": "ecdsa-p256-san"}, "listener_port": 10110, "quic": {"stats": True}}
        q = envoy_config.quic_listener(cfg, hcm, "/c")
        v = q["udp_listener_config"]["quic_options"]["connection_debug_visitor_config"]
        self.assertEqual(v["name"], "envoy.quic.connection_debug_visitor.quic_stats")
        q = envoy_config.quic_listener(dict(cfg, quic={}), hcm, "/c")
        self.assertEqual(q["udp_listener_config"], {"quic_options": {}})
        with self.assertRaises(ValueError):
            envoy_config.quic_listener(dict(cfg, quic={"stats": "yes"}), hcm, "/c")


def leg(arm, **kw):
    m = {"arm": arm, "shape": "s", "leg_id": "r01-s-" + arm, "verdict": {"valid": True, "reasons": []}, "envoy_exit": 0,
         "binary_sha256": chk.PIN[arm], "runtime_start": dict(mk.GUARDS[arm]), "runtime_end": dict(mk.GUARDS[arm]),
         "responses_raw": 40000, "responses": 40000.0, "envoy_pid": 1000 + list(mk.ARMS).index(arm),
         "evidence": {"items": [{"ok": True, "label": "x"}], "ok": True},
         "sut_stats_window": {s: 40000 * 100 for _, s in mk.BYTES}, "kernel_net": {"d": {"UdpInDatagrams": 280680}},
         "per_req": {"cycles_total": 1.2e6, "instructions_u": 5.0e5}, "latency_us": {"p99": 700.0, "max": 4000.0}}
    m.update(kw)
    return m


def write_run(d, legs, arms):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "legs.jsonl"), "w") as f:
        for m in legs:
            f.write(json.dumps(m) + "\n")
    with open(os.path.join(d, "experiment.json"), "w") as f:
        json.dump({"arms": [{"name": a, "evidence": []} for a in arms]}, f)


class Smoke(unittest.TestCase):
    def run_smoke(self, legs):
        with tempfile.TemporaryDirectory() as t:
            write_run(t, legs, mk.SCORED)
            rows, load, other = chk.smoke(t)
            return (1 if other else 3 if load else 0), load, other

    def test_pass(self):
        self.assertEqual(self.run_smoke([leg(a) for a in mk.SCORED])[0], 0)

    def test_load(self):
        legs = [leg(a) for a in mk.SCORED]
        legs[3] = leg("h3-off", verdict={"valid": False, "reasons": ["client pending total 2000 above 1024 (queue absorbed a burst)", "evidence: x"]},
                      evidence={"items": [{"ok": False, "label": "downstream 2xx 1.000 per request"}], "ok": False})
        self.assertEqual(self.run_smoke(legs)[0], 3)

    def test_other(self):
        for kw in ({"binary_sha256": "0" * 64}, {"runtime_end": {"ch": 1, "st": 1, "ru": 1}}, {"envoy_exit": 1},
                   {"verdict": {"valid": False, "reasons": ["evidence: no reset"]}, "evidence": {"items": [{"ok": False, "label": "no reset"}], "ok": False}},
                   {"kernel_net": {"d": {"UdpInDatagrams": 290000}}},
                   {"sut_stats_window": {s: 40000 * 102 for _, s in mk.BYTES}}):
            legs = [leg(a) for a in mk.SCORED]
            legs[3] = leg("h3-off", **kw)
            rc, load, other = self.run_smoke(legs)
            self.assertEqual(rc, 1, kw)
        self.assertEqual(self.run_smoke([leg(a) for a in mk.SCORED[:-1]])[0], 1)

    def test_a_pin_mismatch_is_never_load(self):
        legs = [leg(a) for a in mk.SCORED]
        legs[4] = leg("h3-stop-on", binary_sha256="0" * 64, verdict={"valid": False, "reasons": ["client headroom 10% under 25%"]})
        self.assertEqual(self.run_smoke(legs)[0], 1)


CSV = "%d,,raw_syscalls:sys_enter,1,100.00,,\n%d,,syscalls:sys_enter_recvmmsg,1,100.00,,\n%d,,syscalls:sys_exit_recvmmsg,1,100.00,,\n%d,,syscalls:sys_enter_sendmsg,1,100.00,,\n"


class Mech(unittest.TestCase):
    def run_mech(self, name, counts, shape="s"):
        """counts: {arm: (recvmmsg, eagain, sendmsg)} per request."""
        with tempfile.TemporaryDirectory() as t:
            legs = [leg(a, shape=shape) for a in counts]
            write_run(os.path.join(t, name), legs, list(counts))
            os.makedirs(os.path.join(t, "out-" + name))
            for m in legs:
                r, e, s = counts[m["arm"]]
                with open(os.path.join(t, "out-" + name, "sys-%d.stat.csv" % m["envoy_pid"]), "w") as f:
                    f.write(CSV % (40000 * 20, int(40000 * r), int(40000 * e), int(40000 * s)))
            rows, bad, missing = chk.mech(t, name)
            return (2 if missing else 1 if bad else 0), bad

    GOOD = {"h2tls": (0, 0, 0), "h3-official": (4.0, 2.0, 3.0), "h3-off": (4.0, 2.0, 3.0), "h3-stop-on": (2.0, 0.0, 3.0),
            "h3-both-on": (2.0, 0.0, 3.0), "h3-reuse-on": (4.0, 2.0, 3.0)}

    def test_pass(self):
        self.assertEqual(self.run_mech("mech-sys-s", self.GOOD)[0], 0)

    def test_a_guard_that_does_not_act(self):
        for arm, v in (("h3-stop-on", (4.0, 2.0, 3.0)), ("h3-both-on", (2.0, 0.5, 3.0)), ("h3-off", (2.0, 0.0, 3.0)),
                       ("h3-reuse-on", (2.0, 0.0, 3.0)), ("h3-official", (4.0, 1.0, 3.0)), ("h3-both-on", (2.0, 0.0, 3.3))):
            rc, bad = self.run_mech("mech-sys-s", dict(self.GOOD, **{arm: v}))
            self.assertEqual(rc, 1, (arm, v))
            self.assertTrue(any(b.startswith(arm) for b in bad), bad)

    def test_the_old_loop_is_read_by_its_share(self):
        # what the box showed on 2026-11-24: fewer calls per request than 4.0, half of them empty
        box = dict(self.GOOD, **{"h3-official": (3.41, 1.69, 3.0), "h3-off": (3.75, 1.84, 3.0), "h3-reuse-on": (3.52, 1.70, 3.0),
                                 "h3-stop-on": (1.94, 0.0, 3.0), "h3-both-on": (1.82, 0.0, 3.0)})
        self.assertEqual(self.run_mech("mech-sys-s", box)[0], 0)

    def test_shi(self):
        hi = {"h3-official": (3.0, 1.4, 3.0), "h3-off": (3.0, 1.4, 3.0), "h3-stop-on": (1.6, 0.01, 3.0), "h3-both-on": (1.6, 0.0, 3.2)}
        self.assertEqual(self.run_mech("mech-sys-shi-half", hi, "s-hi")[0], 0)
        self.assertEqual(self.run_mech("mech-sys-shi-half", dict(hi, **{"h3-stop-on": (3.0, 1.4, 3.0)}), "s-hi")[0], 1)
        self.assertEqual(self.run_mech("mech-sys-shi-half", dict(hi, **{"h3-off": (3.0, 0.9, 3.0)}), "s-hi")[0], 1)

    def test_missing_counts(self):
        with tempfile.TemporaryDirectory() as t:
            write_run(os.path.join(t, "mech-sys-s"), [leg(a) for a in self.GOOD], list(self.GOOD))
            self.assertTrue(chk.mech(t, "mech-sys-s")[2])
        with tempfile.TemporaryDirectory() as t:
            self.assertTrue(chk.mech(t, "mech-sys-s")[2])


if __name__ == "__main__":
    unittest.main()
