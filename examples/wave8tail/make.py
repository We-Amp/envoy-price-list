#!/usr/bin/env python3
"""Wave 8, the QUIC tail add-on that ran after session W8-3 (W8-2's follow-up): writes configs/tail-*.json.

    python3 examples/wave8tail/make.py

The configs are those of tail_make.py; this file gives it what it reads from the session's set-up: the two
binaries (bins.json), the four runtime guard names of the build, and the runs directory the session used
(`~/epl/runs/wave8w3`, as recorded). The arms hold the build's chunked and relay-write guards false and set the
two UDP guards per arm, as W8-2 named its arms.
"""
import copy
import importlib.util
import json
import os
import types

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "configs")
ROOT = os.path.dirname(os.path.dirname(HERE))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


s5 = _load("w7s5_make_for_w8tail", os.path.join(ROOT, "examples", "wave7s5", "make.py"))

RUNS = "~/epl/runs/wave8w3"
CH = "envoy.reloadable_features.http1_zero_copy_body_fragments"
ST = "envoy.reloadable_features.udp_stop_reading_on_short_recvmmsg"
RU = "envoy.reloadable_features.udp_recvmmsg_reuse_buffers"
WR = "envoy.reloadable_features.connection_write_in_current_iteration"
RUNTIME_KEYS = {"ch": CH, "st": ST, "ru": RU, "wr": WR}
ALL_KEYS = (CH, ST, RU, WR, s5.SR)

with open(os.path.join(HERE, "bins.json")) as _f:
    BINS = json.load(_f)


def is_guard_item(it):
    st = str(it.get("stat"))
    return (it.get("scope") == "field" and st.startswith("runtime_")) or st in ALL_KEYS or st in ("layered_runtime", "runtime.num_keys")


def strip(ev):
    return [copy.deepcopy(it) for it in ev if not is_guard_item(it) and "ref" not in it]


def configs():
    mk = types.SimpleNamespace(BINS=BINS, CH=CH, ST=ST, RU=RU, WR=WR, RUNTIME_KEYS=RUNTIME_KEYS, RUNS=RUNS, strip=strip)
    return _load("w8tail_tail_make", os.path.join(HERE, "tail_make.py")).configs(mk)


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn, c in sorted(configs().items()):
        with open(os.path.join(OUT, fn + ".json"), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
        print(fn + ".json")


if __name__ == "__main__":
    main()
