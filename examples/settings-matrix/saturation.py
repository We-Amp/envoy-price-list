#!/usr/bin/env python3
"""Short saturation probe: for each arm, single legs at rising rates until p99 reaches a
limit or the proxy misses the target rate; reports the highest rate that stayed under.

    python3 examples/settings-matrix/saturation.py CFG OUT_DIR --rps 5200,6400,... [--p99-ms 2]
        [--arms a,b] [--shape s]

One leg per rate (exploratory: no rounds, no interval). Each leg keeps the harness's
gates and records; a leg that fails a gate other than its p99 is still reported, with
its reasons, because at high rates the client's headroom gate is expected to trip.
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EPL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "bin", "epl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("out")
    ap.add_argument("--rps", required=True)
    ap.add_argument("--p99-ms", type=float, default=2.0)
    ap.add_argument("--arms")
    ap.add_argument("--shape", default="s")
    a = ap.parse_args()
    with open(a.config) as f:
        cfg = json.load(f)
    arms = a.arms.split(",") if a.arms else [x["name"] for x in cfg["arms"]]
    os.makedirs(a.out, exist_ok=True)
    res = {}
    for arm in arms:
        rows = []
        for rps in [int(x) for x in a.rps.split(",")]:
            d = os.path.join(a.out, "%s-%d" % (arm, rps))
            r = subprocess.run([sys.executable, EPL, "calibrate", a.config, "--arm", arm, "--shape", a.shape,
                                "--rps", str(rps), "--out", d], capture_output=True, text=True, timeout=900)
            try:
                with open(os.path.join(d, "calibrate.json")) as f:
                    row = json.load(f)[0]
            except (OSError, ValueError, IndexError):
                row = {"rps": rps, "error": r.stderr[-400:]}
            row.pop("stats", None)
            rate_ok = row.get("rate") is not None and abs(row["rate"] / rps - 1.0) <= 0.01
            p99 = row.get("p99_us")
            row["under"] = bool(rate_ok and p99 is not None and p99 < a.p99_ms * 1000.0)
            rows.append(row)
            print(json.dumps(dict(row, arm=arm)), flush=True)
            if not row["under"]:
                break
        ok = [x["rps"] for x in rows if x["under"]]
        res[arm] = {"highest_rps_under": max(ok) if ok else None,
                    "first_rps_over": next((x["rps"] for x in rows if not x["under"]), None), "rows": rows}
    with open(os.path.join(a.out, "saturation.json"), "w") as f:
        json.dump({"p99_limit_ms": a.p99_ms, "shape": a.shape, "arms": res}, f, indent=1)
    for arm, v in res.items():
        print("%s: highest rate with p99 < %.1f ms: %s (first over: %s)"
              % (arm, a.p99_ms, v["highest_rps_under"], v["first_rps_over"]))


if __name__ == "__main__":
    main()
