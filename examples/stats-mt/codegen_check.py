#!/usr/bin/env python3
"""Fail-closed checks of the arm64 atomics codegen run (make.py codegen*.json).

    python3 examples/stats-mt/codegen_check.py atomics CFG OUT.json [--objdump objdump]
    python3 examples/stats-mt/codegen_check.py smoke CFG SMOKE_DIR [--json OUT.json]

atomics: per arm binary, the counts of every atomic instruction in the whole executable
(`objdump -d`; the release binaries are stripped, so the stats functions cannot be singled
out): load/store-exclusive (LL/SC: ldxr, ldaxr, stxr, stlxr and their byte and halfword
forms) and LSE (ldadd, ldset, ldclr, ldeor, swp, cas families), plus `--version` and whether the
executable is static (no PT_INTERP). The style is "llsc-inline" with at least 10,000
exclusive instructions, "outline" with fewer than 1,000 exclusive instructions and LSE
instructions present (the out-of-line helpers carry both forms behind a runtime check), else
"unclear". Exit 1 unless every arm's binary has the style the config expects
(`contrast.expect_style`).

smoke: every leg of the smoke valid (the latest attempt of each rung and arm), and the
store-stat operations per request (measure.stat_ops_probe: counter increments without the
byte counters, histogram samples) equal between the two stats-on builds within 1% at every
rung, with the counters that changed in one build but not the other listed. Gauge updates are
not counted (an inc and a dec cancel in snapshots); the report says so. Exit 0 when it passes,
2 when only top-rung legs are invalid (capacity: the fallback config applies), 1 otherwise.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import experiment  # noqa: E402

LLSC = re.compile(r"^(ldx|ldax|stx|stlx)r[bh]?$")
LSE = re.compile(r"^(ldadd|ldset|ldclr|ldeor|swp|cas)(a|l|al)?[bh]?$|^casp(a|l|al)?$")
INSN = re.compile(r"^\s*[0-9a-f]+:\s+(?:(?:[0-9a-f]{2} ){4}\s*|[0-9a-f]{8}\s+)?([a-z][a-z0-9.]*)\b")
LLSC_INLINE_MIN = 10000
OUTLINE_LLSC_MAX = 1000
STAT_OPS_TOL = 0.01


def count_atomics(lines):
    llsc, lse, by = 0, 0, {}
    for ln in lines:
        m = INSN.match(ln)
        if not m:
            continue
        mn = m.group(1)
        if LLSC.match(mn):
            llsc += 1
        elif LSE.match(mn):
            lse += 1
        else:
            continue
        by[mn] = by.get(mn, 0) + 1
    return {"exclusive": llsc, "lse": lse, "by_mnemonic": dict(sorted(by.items()))}


def style(c):
    if c["exclusive"] >= LLSC_INLINE_MIN:
        return "llsc-inline"
    if c["exclusive"] < OUTLINE_LLSC_MAX and c["lse"] > 0:
        return "outline"
    return "unclear"


def is_static(path):
    """True when the ELF executable has no PT_INTERP program header."""
    with open(path, "rb") as f:
        h = f.read(64)
        if h[:4] != b"\x7fELF" or h[4] != 2:
            return None
        order = "little" if h[5] == 1 else "big"
        phoff = int.from_bytes(h[32:40], order)
        phentsize = int.from_bytes(h[54:56], order)
        phnum = int.from_bytes(h[56:58], order)
        f.seek(phoff)
        ph = f.read(phentsize * phnum)
    return not any(int.from_bytes(ph[i * phentsize:i * phentsize + 4], order) == 3 for i in range(phnum))


def arm_binaries(cfg):
    arch = experiment.box_arch(cfg)
    out = {}
    for a in cfg["arms"]:
        b = (a.get("binaries") or {}).get(arch) or {}
        out[a["name"]] = os.path.expanduser(b.get("binary") or a.get("binary"))
    return out


def atomics(cfg, out, objdump="objdump"):
    want = cfg["contrast"]["expect_style"]
    bins = arm_binaries(cfg)
    rep, probs, seen = {"arms": {}}, [], {}
    for arm, exp_style in sorted(want.items()):
        path = bins[arm]
        if path not in seen:
            p = subprocess.Popen([objdump, "-d", "--no-show-raw-insn", path], stdout=subprocess.PIPE, text=True,
                                 errors="replace")
            c = count_atomics(p.stdout)
            rc = p.wait()
            if rc != 0:
                raise SystemExit("%s -d %s exited %d" % (objdump, path, rc))
            try:
                v = subprocess.run([path, "--version"], capture_output=True, text=True).stdout.strip().splitlines()
            except OSError as ex:
                v = ["not runnable here: %s" % ex.strerror]
            seen[path] = dict(c, style=style(c), version=(v[-1] if v else ""), static=is_static(path), path=path)
        r = dict(seen[path], expected=exp_style)
        rep["arms"][arm] = r
        if r["style"] != exp_style:
            probs.append("%s: atomics style %s (exclusive %d, LSE %d), expected %s" % (
                arm, r["style"], r["exclusive"], r["lse"], exp_style))
    rep["problems"] = probs
    rep["ok"] = not probs
    with open(out, "w") as f:
        json.dump(rep, f, indent=1)
    return rep


def smoke(cfg, smoke_dir):
    with open(os.path.join(smoke_dir, "results.json")) as f:
        res = json.load(f)
    # the latest attempt of each (rung, arm, round), valid or not (current_legs keeps valid ones only)
    legs = {}
    for m in res["legs"]:
        legs[(m.get("shape"), m.get("arm"), m.get("round"))] = m
    shapes = [s["name"] for s in cfg["shapes"]]
    top = max(cfg["shapes"], key=lambda s: s["workers"])["name"]
    arms = [a["name"] for a in cfg["arms"]]
    invalid, missing = [], []
    for s in shapes:
        for a in arms:
            m = next((m for (ls, la, r), m in legs.items() if ls == s and la == a), None)
            if m is None:
                missing.append("%s %s" % (s, a))
            elif not (m.get("verdict") or {}).get("valid"):
                invalid.append({"shape": s, "arm": a, "reasons": (m.get("verdict") or {}).get("reasons", [])})
    ops, ops_probs = {}, []
    pair = cfg["contrast"]["stat_ops_pair"]
    for s in shapes:
        row = {}
        for a in pair:
            m = next((m for (ls, la, r), m in legs.items() if ls == s and la == a), None)
            so = (m or {}).get("stat_ops")
            resp = (m or {}).get("responses") or 0
            if not so or not resp:
                row[a] = None
                continue
            row[a] = {"counter_incs_per_req": so["counter_incs"] / resp,
                      "histogram_samples_per_req": so["histogram_samples"] / resp,
                      "counters_changed": so["counters_changed"]}
        ops[s] = row
        x, y = row.get(pair[0]), row.get(pair[1])
        if x is None or y is None:
            ops_probs.append("%s: no stat_ops probe for %s" % (s, " and ".join(a for a in pair if not row.get(a))))
            continue
        for k in ("counter_incs_per_req", "histogram_samples_per_req"):
            ref = max(abs(x[k]), abs(y[k]), 1e-9)
            if abs(x[k] - y[k]) / ref > STAT_OPS_TOL:
                ops_probs.append("%s: %s %.3f (%s) against %.3f (%s), more than %.0f%% apart" % (
                    s, k, x[k], pair[0], y[k], pair[1], 100 * STAT_OPS_TOL))
        only = sorted(set(x["counters_changed"]) ^ set(y["counters_changed"]))
        row["counters_in_one_build_only"] = only
    probs = ["missing leg: " + m for m in missing] + \
        ["invalid leg: %s %s: %s" % (i["shape"], i["arm"], "; ".join(i["reasons"])) for i in invalid] + ops_probs
    # capacity: only top-rung legs invalid, and the stat-op comparison clean on the other rungs
    capacity_only = (bool(invalid) and not missing and all(i["shape"] == top for i in invalid)
                     and not [p for p in ops_probs if not p.startswith(top + ":")])
    return {"ok": not probs, "capacity_only": capacity_only, "problems": probs, "stat_ops": ops,
            "gauges": "not counted (snapshots cannot count gauge updates)", "tolerance": STAT_OPS_TOL}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["atomics", "smoke"])
    ap.add_argument("cfg")
    ap.add_argument("path")
    ap.add_argument("--objdump", default="objdump")
    ap.add_argument("--json")
    a = ap.parse_args()
    with open(a.cfg) as f:
        cfg = json.load(f)
    if a.cmd == "atomics":
        rep = atomics(cfg, a.path, a.objdump)
        for arm, r in rep["arms"].items():
            print("%-16s %-12s exclusive %6d  LSE %4d  static %s  %s" % (arm, r["style"], r["exclusive"], r["lse"],
                                                                       r["static"], r["version"]))
        for p in rep["problems"]:
            print("PROBLEM " + p)
        print("atomics %s" % ("OK" if rep["ok"] else "FAILED"))
        return 0 if rep["ok"] else 1
    rep = smoke(cfg, a.path)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(rep, f, indent=1)
    for s, row in rep["stat_ops"].items():
        for arm in cfg["contrast"]["stat_ops_pair"]:
            r = row.get(arm)
            if r:
                print("%-8s %-10s counter incs/req %.3f  histogram samples/req %.3f" % (
                    s, arm, r["counter_incs_per_req"], r["histogram_samples_per_req"]))
        if row.get("counters_in_one_build_only"):
            print("%-8s counters changing in one build only: %s" % (s, ", ".join(row["counters_in_one_build_only"])))
    print("gauges: " + rep["gauges"])
    for p in rep["problems"]:
        print("PROBLEM " + p)
    if rep["ok"]:
        print("smoke OK")
        return 0
    print("smoke FAILED%s" % (" (top-rung capacity only: the fallback applies)" if rep["capacity_only"] else ""))
    return 2 if rep["capacity_only"] else 1


if __name__ == "__main__":
    sys.exit(main())
