#!/usr/bin/env python3
"""Configs of wave 6 track K: track H's three-boot mitigation price (h-pl, h-c1, h-spec) on a current x86 CPU in
a cloud VM. The runs, arms, rates, gates, rounds and warm-ups are H's (examples/wave5h/make.py); what differs is the
box (CPU sets, perf), the Williams seeds (611, 612, 613) and a per-leg steal gate (2% of the window's CPU time).

    python3 examples/wave6k/make.py [--box BOX_JSON] [--rates JSON]

Writes examples/wave6k/<box name>/ (h-pl, h-c1, h-spec and their smokes). The configs are the same files in every
boot of the series (A, B, C).
"""
import argparse
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location("wave5h_make", os.path.join(ROOT, "examples", "wave5h", "make.py"))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

SEEDS = {"h-pl": 611, "h-c1": 612, "h-spec": 613}
RUNS = ("h-pl", "h-c1", "h-spec")
MAX_STEAL = 0.02


def configs(box, rates=None):
    h.SEEDS.update(SEEDS)
    out = {}
    for fn, c in h.configs(box, rates).items():
        stem = fn[:-5].replace("smoke-", "")
        if stem not in RUNS:
            continue
        c["workdir"] = "~/epl/runs/wave6k"
        c["validity"] = dict(c.get("validity") or {}, max_steal_share=MAX_STEAL)
        out[fn] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", default=os.path.join(HERE, "box-c4-32.json"))
    ap.add_argument("--rates", default=None)
    a = ap.parse_args()
    box = json.load(open(a.box))
    d = os.path.join(HERE, box["name"])
    os.makedirs(d, exist_ok=True)
    cfgs = configs(box, json.loads(a.rates) if a.rates else None)
    for fn, c in sorted(cfgs.items()):
        with open(os.path.join(d, fn), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
    print("%s: %d configs (%s)" % (box["name"], len(cfgs), ", ".join(sorted(cfgs))))


if __name__ == "__main__":
    main()
