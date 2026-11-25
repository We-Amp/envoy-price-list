"""Wave 8, the QUIC tail add-on after W8-3: configs on disk, arms and guards, the scripts parse."""
import importlib.util
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from epl import experiment  # noqa: E402

W = os.path.join(ROOT, "examples", "wave8tail")


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(W, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mk = _load("w8tail_make_t", "make.py")


class Configs(unittest.TestCase):
    def test_on_disk(self):
        cs = mk.configs()
        self.assertEqual(sorted(cs), ["tail-c4", "tail-p1-r1", "tail-p1-r2", "tail-p1-r3", "tail-p1-r4"])
        for name, c in cs.items():
            with open(os.path.join(W, "configs", name + ".json")) as f:
                self.assertEqual(json.load(f), json.loads(json.dumps(c)), name)

    def test_arms_and_guards(self):
        c = mk.configs()["tail-c4"]
        self.assertEqual([a["name"] for a in c["arms"]], ["h3-official", "h3-official-A2", "h3-off", "h3-reuse-on"])
        self.assertEqual((c["rounds"], c["order"], c["order_seed"]), (8, "williams", 851))
        for a in c["arms"]:
            rt = (a.get("settings") or {}).get("runtime")
            if a["build"] == "official":
                self.assertIsNone(rt)
            else:
                self.assertEqual(rt, {mk.CH: False, mk.ST: False, mk.RU: a["name"] == "h3-reuse-on", mk.WR: False})
        p1 = mk.configs()["tail-p1-r1"]
        self.assertEqual([a["name"] for a in p1["arms"]], ["h3-off", "h3-both-on"])
        self.assertEqual(p1["arms"][1]["settings"]["quic"], {"stats": True, "stats_update_period_ms": 50})

    def test_every_config_loads(self):
        for fn in sorted(os.listdir(os.path.join(W, "configs"))):
            experiment.load(os.path.join(W, "configs", fn))

    def test_scripts_parse(self):
        for fn in os.listdir(W):
            if fn.endswith(".sh"):
                subprocess.check_call(["bash", "-n", os.path.join(W, fn)])

    def test_tail_check_loads(self):
        t = _load("w8tail_check_t", "tail_check.py")
        self.assertEqual((t.FLOOR, t.LINE), (2.0, -3.0))


if __name__ == "__main__":
    unittest.main()
