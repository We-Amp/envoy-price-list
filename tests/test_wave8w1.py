"""Wave 8 W8-1: configs, the state rules (smoke, pick, traced legs, the copy signature) and the tail add-on's rule."""
import collections
import gzip
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from epl import experiment  # noqa: E402

W = os.path.join(ROOT, "examples", "wave8w1")


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(W, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


chk = _load("w8w1_check_t", "w1_check.py")
tc = _load("w8w1_tail_t", "tail_check.py")
mk = chk.mk


def leg(shape, arm, run="a", valid=True, reasons=(), failed=(), guards=None, pin=None, bytes_=1000.0):
    items = [{"label": "x", "ok": True}] + [{"label": f, "ok": False, "value": 1, "why": "w"} for f in failed]
    g = mk.GUARDS[run][arm] if guards is None else guards
    return {"shape": shape, "arm": arm, "leg_id": "r01-%s-%s" % (shape, arm), "verdict": {"valid": valid, "reasons": list(reasons)},
            "evidence": {"items": items}, "envoy_exit": 0, "binary_sha256": pin or mk.PIN[run][arm], "runtime_start": g, "runtime_end": g,
            "responses_raw": 100, "sut_stats_window": {s: bytes_ * 100 for _, s in mk.BYTES}, "per_req": {}, "latency_us": {}}


def smoke_dir(d, name, legs):
    p = os.path.join(d, name)
    os.makedirs(p)
    with open(os.path.join(p, "experiment.json"), "w") as f:
        json.dump(mk.configs()[name], f)
    with open(os.path.join(p, "legs.jsonl"), "w") as f:
        for m in legs:
            f.write(json.dumps(m) + "\n")
    return p


class Configs(unittest.TestCase):
    def test_on_disk(self):
        for name, c in mk.configs().items():
            with open(os.path.join(W, "configs", name + ".json")) as f:
                self.assertEqual(json.load(f), json.loads(json.dumps(c)), name)

    def test_arms_and_guards(self):
        for run, arms in mk.ARMS.items():
            c = mk.configs()[run]
            self.assertEqual([a["name"] for a in c["arms"]], list(arms))
            for a in c["arms"]:
                build, g, _ = arms[a["name"]]
                rt = (a.get("settings") or {}).get("runtime")
                if build == "official":
                    self.assertIsNone(rt)
                    self.assertEqual(a["source_sha256"], "1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc")
                else:
                    self.assertEqual(rt, {mk.CH: g, mk.ST: True, mk.RU: True})
                    self.assertEqual(a["source_sha256"], "46c98673eddc4f480cfc79cf8b6cfb620b6fec97245dcc0332535d43475d3971")
        self.assertEqual(mk.GUARDS["a"]["frag-on-ch8k"], {"ch": 1, "st": 1, "ru": 1})
        self.assertEqual(mk.GUARDS["a"]["off-cl8k"], {"ch": 0, "st": 1, "ru": 1})

    def test_rates_rounds_order(self):
        cs = mk.configs()
        for name, c in cs.items():
            for s in c["shapes"]:
                self.assertEqual(s["rps"] % 16, 0, name)
        self.assertEqual([cs[k]["rounds"] for k in "abdc"], [6, 8, 4, 6])
        self.assertEqual([[s["rps"] for s in cs[k]["shapes"]] for k in "abdc"], [[4000, 800], [2000], [400], [2000, 800]])
        self.assertEqual(cs["a"]["shape_order"], "latin")
        self.assertEqual(cs["c"]["shape_order"], "latin")
        for k in "abd":
            c, pos = cs[k], collections.Counter()
            n = len(c["arms"])
            for r in range(1, c["rounds"] + 1):
                for i, a in enumerate(experiment.round_order(c, r)):
                    pos[(a["name"], i)] += 1
            self.assertEqual(set(pos.values()), {c["rounds"] // n}, k)

    def test_every_config_validates(self):
        for name in mk.configs():
            experiment.load(os.path.join(W, "configs", name + ".json"))

    def test_scripts_parse(self):
        for fn in os.listdir(W):
            if fn.endswith(".sh"):
                self.assertEqual(subprocess.run(["bash", "-n", os.path.join(W, fn)]).returncode, 0, fn)

    def test_nginx_chunked_location(self):
        from epl import envoy_config as ec
        sh = mk.configs()["b"]["shapes"]
        conf = ec.nginx_conf(8092, 8, stub_status=True, chunked=ec.chunked_paths(sh))
        self.assertIn("location = /ngx-ch64 { ssi on; ssi_types *; }", conf)
        self.assertEqual(ec.nginx_conf(8092, 8), ec.nginx_conf(8092, 8, chunked=[]))


class Rules(unittest.TestCase):
    def all_legs(self, over=None):
        over = over or {}
        out = []
        for sh in ("b64k", "b1m"):
            for arm in mk.ARMS["a"]:
                out.append(leg(sh, arm, **over.get((sh, arm), {})))
        return out

    def test_pick(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(chk.pick(smoke_dir(d, "smoke-a", self.all_legs())), "a")
        with tempfile.TemporaryDirectory() as d:
            legs = self.all_legs({("b1m", "off-ch8k"): dict(valid=False, reasons=["client headroom 20% under 25%"],
                                                               failed=["upstream 2xx"])})
            p = smoke_dir(d, "smoke-a", legs)
            self.assertEqual(chk.pick(p), "a-h1m")
            self.assertEqual(chk.main(["smoke", p]), 3)
        with tempfile.TemporaryDirectory() as d:
            legs = self.all_legs({("b64k", "frag-on-ch8k"): dict(failed=["no upstream connection destroyed in the window"])})
            p = smoke_dir(d, "smoke-a", legs)
            self.assertEqual(chk.pick(p), "fail")
            self.assertEqual(chk.main(["smoke", p]), 1)
        with tempfile.TemporaryDirectory() as d:
            legs = self.all_legs({("b1m", "off-ch8k"): dict(valid=False, reasons=["achieved rate 700.0 misses target 400 by 2.00%"])})
            self.assertEqual(chk.pick(smoke_dir(d, "smoke-a-h1m", legs)), "fail")
        with tempfile.TemporaryDirectory() as d:
            legs = self.all_legs({("b1m", "frag-on-ch8k"): dict(guards={"ch": 0, "st": 1, "ru": 1})})
            self.assertEqual(chk.pick(smoke_dir(d, "smoke-a", legs)), "fail")
        with tempfile.TemporaryDirectory() as d:
            legs = self.all_legs({("b1m", "frag-on-ch8k"): dict(bytes_=1010.0)})
            self.assertEqual(chk.pick(smoke_dir(d, "smoke-a", legs)), "fail")
        with tempfile.TemporaryDirectory() as d:
            legs = [leg("ngx-ch64", a, run="b", valid=False, reasons=["Envoy load uneven: busiest worker did 40%"]) for a in mk.ARMS["b"]]
            self.assertEqual(chk.pick(smoke_dir(d, "smoke-b", legs)), "b-half")

    def test_counts(self):
        rows = [("sys_enter", 5000.0), ("sys_enter_epoll_wait", 10.0), ("sys_exit_epoll_wait", 400.0), ("sys_enter_readv", 3600.0),
                ("sys_exit_readv", 100.0), ("sys_enter_read", 0.0), ("sys_enter_recvfrom", 0.0), ("sys_enter_write", 0.0),
                ("sys_enter_sendto", 0.0), ("sys_enter_sendmsg", 0.0), ("sys_enter_epoll_ctl", 2.0), ("sys_enter_close", 0.0),
                ("sys_enter_writev", 1000.0)]
        hist = [100.0] + [0.0] * 14 + [900.0]
        rows += [("sys_enter_writev", v) for v in hist] + [("sys_enter_writev", 0.0), ("sys_enter_writev", 100.0), ("sys_enter_writev", 100.0),
                                                              ("sys_enter_readv", 3500.0)]
        x = chk.counts(rows, 100.0)
        self.assertAlmostEqual(x["writev"], 10.0)
        self.assertAlmostEqual(x["writev_client_side"], 9.0)
        self.assertAlmostEqual(x["iovecs"], (100 + 900 * 16) / 100.0)
        self.assertAlmostEqual(x["iovecs_client_side"], 144.0)
        self.assertAlmostEqual(x["readv_origin_side"], 35.0)
        self.assertIsNone(chk.counts(rows[:-1], 100.0))

    def sig_dir(self, d, shares):
        os.makedirs(os.path.join(d, "mech-kcg-a"))
        os.makedirs(os.path.join(d, "out-mech-kcg-a"))
        with open(os.path.join(d, "mech-kcg-a", "legs.jsonl"), "w") as f:
            for i, (arm, s) in enumerate(shares.items()):
                m = leg("b1m", arm)
                m["envoy_pid"] = 100 + i
                f.write(json.dumps(m) + "\n")
                with gzip.open(os.path.join(d, "out-mech-kcg-a", "kcg-%d.folded.gz" % (100 + i)), "wt") as g:
                    g.write("wrk:worker_0;a;Envoy::Http::Http1::ConnectionImpl::dispatchSlice;[libc.so.6]\t%d\t1\n" % int(s * 10000))
                    g.write("wrk:worker_0;a;copy_user_[k]\t%d\t1\n" % int((1 - s) * 10000))
                    g.write("envoy;main;[libc.so.6]\t99999\t1\n")
        return d

    def test_signature(self):
        for shares, rc in (({"official-ch8k": 0.055, "off-ch8k": 0.06, "frag-on-ch8k": 0.004}, 0),
                           ({"official-ch8k": 0.055, "off-ch8k": 0.06, "frag-on-ch8k": 0.04}, 1),
                           ({"official-ch8k": 0.055, "off-ch8k": 0.01, "frag-on-ch8k": 0.004}, 1),
                           ({"official-ch8k": 0.004, "off-ch8k": 0.004, "frag-on-ch8k": 0.004}, 1),
                           ({"official-ch8k": 0.055, "off-ch8k": 0.06}, 2)):
            with tempfile.TemporaryDirectory() as d:
                self.assertEqual(chk.main(["sig", self.sig_dir(d, shares), "mech-kcg-a"]), rc, shares)

    def test_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(chk.main(["smoke", d]), 1)
            self.assertEqual(chk.pick(d), "fail")
            self.assertEqual(chk.main(["mech", d, "mech-sys-a"]), 2)
            self.assertEqual(chk.main(["sig", d, "mech-kcg-a"]), 2)


class Tail(unittest.TestCase):
    def test_configs(self):
        cs = mk.configs()
        durs = [cs["tail-a-r%d" % r]["client"]["duration_s"] for r in range(1, 9)]
        self.assertEqual(durs, [10, 40] * 4)
        pos = collections.Counter()
        for r in range(1, 9):
            c = cs["tail-a-r%d" % r]
            self.assertEqual(sorted(a["name"] for a in c["arms"]), sorted(mk.TAIL_A))
            for i, a in enumerate(c["arms"]):
                pos[(a["name"], i)] += 1
                self.assertTrue(a["settings"]["quic"]["stats"])
                if a["build"] == "w8-A":
                    self.assertEqual(a["binary"], "~/epl/bins/wave8w1/envoy-w8-A")
        self.assertEqual(set(pos.values()), {2})
        self.assertEqual([[a["name"] for a in cs["tail-c-r%d" % r]["arms"]] for r in (1, 2)], [["h3-off", "h3-both-on"], ["h3-both-on", "h3-off"]])
        self.assertEqual(cs["tail-c-r1"]["shapes"][0]["rps"], 16)
        self.assertEqual(cs["tail-c-r1"]["client"]["duration_s"], 60)

    def test_rule(self):
        obs, p, n = tc.perm_p([[5, 6, 16, 15]])
        self.assertEqual((obs, n), (20, 6))
        self.assertAlmostEqual(p, 1 / 6.0)
        obs, p, n = tc.perm_p([[5, 6, 16, 15]] * 8)
        self.assertEqual(n, 6 ** 8)
        self.assertLess(p, 0.05)
        _, p, _ = tc.perm_p([[5, 6, 5, 6], [7, 4, 5, 6], [5, 5, 5, 5], [3, 9, 6, 6]])
        self.assertGreater(p, 0.05)
        self.assertEqual(tc.hist_nonzero(["x.cx_tx_percent_retransmitted_packets: totals=0,0.1:20, 1.2,0.1:12 intervals=0,0.1:1"]), (32, 12))
        self.assertIsNone(tc.hist_nonzero(["nothing"]))


if __name__ == "__main__":
    unittest.main()
