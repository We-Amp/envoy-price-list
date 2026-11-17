#!/usr/bin/env python3
"""Tables of the feature rows, session 2 (features2.py).

    python3 examples/settings-matrix/features_table2.py SESSION_DIR [--json OUT.json] > tables.md
    python3 examples/settings-matrix/features_table2.py jit JIT_RUN_DIR

SESSION_DIR holds aa-2, run-f, 14-compression, lc-j16 and, if they ran, 14b and lc-sfh.
The rules are those of features_table.py (session 1): comparisons recomputed from the legs
of complete rotation blocks, widened intervals, named families with their own Holm step
(a row that is missing or from an incomplete run counts as p = 1), verdicts below an A/A
that failed its limit are not findings, incomplete runs carry no verdict.

- confirmatory (10 rows): gzip, brotli, zstd against comp-off on j4 and j16; lua-header
  and wasm-header against filter-off on s and fh;
- secondary (7 rows): lua-empty and wasm-empty against filter-off on s and fh; the AA-2
  rows on s, fh, j16;
- row 14b (1 row), if it ran;
- exploratory: Wasm against Lua (paired, same rounds), one library against another, the
  compression ratio each library reached, user and kernel split (the user-cycle difference
  is the transferable part: on loopback, kernel cycles include the client's receive work,
  which shrinks with the response), minor faults and upstream segments per response,
  both busy levels, and the load-curve estimate for row 14 (internal): the arm's cycles
  minus the reference's cycles at the arm's own busy level, read off the reference's curve
  through j16, j16-a, j16-b, j16-c (linear between points).

A/A per shape: run F's s and fh and row 14's j16 use AA-2 on the same shape; j4 and s-ae
borrow AA-2's s (stated); LC runs have none.

`jit`: user instructions per request of each arm with a 5 s and a 30 s warm-up; exit 4
when any arm differs by more than 0.5% (run F then uses a 15 s warm-up).
"""

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")
sys.path.insert(0, REPO)
from epl import experiment, stats  # noqa: E402

_spec = importlib.util.spec_from_file_location("features_table", os.path.join(HERE, "features_table.py"))
FT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FT)

JIT_LIMIT_PCT = 0.5
LIBS = ("gzip", "brotli", "zstd")
CONFIRMATORY = [("14-compression", s, lib, "comp-off", "compression, %s" % lib) for s in ("j4", "j16") for lib in LIBS] \
    + [("run-f", s, a, "filter-off", label) for s in ("s", "fh")
       for a, label in (("lua-header", "Lua, header script"), ("wasm-header", "Wasm, header module"))]
SECONDARY = [("run-f", s, a, "filter-off", label) for s in ("s", "fh")
             for a, label in (("lua-empty", "Lua, empty script"), ("wasm-empty", "Wasm, empty module"))] \
    + [("aa-2", s, "base-A2", "base", "A/A") for s in ("s", "fh", "j16")]
ROW_14B = [("14b", "s-ae", "gzip", "comp-off", "gzip in the chain, nothing compressible")]
AA_ROWS = {
    ("run-f", "s"): ("aa-2", "s", "base-A2", "base"), ("run-f", "fh"): ("aa-2", "fh", "base-A2", "base"),
    ("14-compression", "j16"): ("aa-2", "j16", "base-A2", "base"),
    ("14-compression", "j4"): ("aa-2", "s", "base-A2", "base"),  # borrowed: j4 has no A/A
    ("14b", "s-ae"): ("aa-2", "s", "base-A2", "base"),  # borrowed
    ("aa-2", "s"): ("aa-2", "s", "base-A2", "base"), ("aa-2", "fh"): ("aa-2", "fh", "base-A2", "base"),
    ("aa-2", "j16"): ("aa-2", "j16", "base-A2", "base"),
}
EXPLORATORY = [("run-f", s, "wasm-header", "lua-header", "Wasm against Lua, header") for s in ("s", "fh")] \
    + [("run-f", s, "wasm-empty", "lua-empty", "Wasm against Lua, empty") for s in ("s", "fh")] \
    + [("14-compression", s, a, b, "%s against %s" % (a, b)) for s in ("j4", "j16")
       for a, b in (("brotli", "gzip"), ("zstd", "gzip"), ("zstd", "brotli"))]
LC_SHAPES = ("j16-a", "j16-b", "j16-c")


def aa_status(runs, secondary):
    out = {}
    sec = {(r["run"], r["shape"], r["arm"], r["ref"]): r for r in secondary}
    for key, spec in AA_ROWS.items():
        r = sec.get(spec) or FT.row(runs, spec + ("A/A",))
        if r.get("missing"):
            out[key] = {"ok": None, "why": r["missing"]}
            continue
        hp = r.get("holm_p", r.get("t_p"))
        ok = (not r.get("incomplete")) and hp is not None and r["hw"] <= FT.AA_LIMIT_PCT and hp > 0.05
        out[key] = {"ok": ok, "reach": max(abs(r["lo"]), abs(r["hi"])), "hw": r["hw"], "holm_p": hp, "spec": spec,
                    "borrowed": key[1] != spec[1]}
    return out


def leg_means(res, shape, arm, get):
    vals = []
    for (s, a, r), m in FT.usable_legs(res).items():
        if s == shape and a == arm:
            try:
                v = get(m)
            except (KeyError, TypeError, ZeroDivisionError):
                v = None
            if v is not None:
                vals.append(v)
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def ratio_getter(lib):
    def g(m):
        w = m["sut_stats_window"]
        c = w["http.ingress_http.compressor.epl.%s.total_compressed_bytes" % lib]
        u = w["http.ingress_http.compressor.epl.%s.total_uncompressed_bytes" % lib]
        return u / c if c else None
    return g


def busy_of(res, shape, arm):
    return leg_means(res, shape, arm, lambda m: m.get("sut_busy"))[0]


def cycles_of(res, shape, arm):
    return leg_means(res, shape, arm, lambda m: m["per_req"]["cycles_total"])[0]


def load_curve(runs):
    """[(busy, cycles per request)] of the j16 reference: row 14's comp-off on j16 and the LC
    run's comp-off at j16-a, j16-b, j16-c, sorted by busy."""
    pts = []
    r14, lc = runs.get("14-compression"), runs.get("lc-j16")
    if r14:
        b, c = busy_of(r14, "j16", "comp-off"), cycles_of(r14, "j16", "comp-off")
        if b is not None and c is not None:
            pts.append((b, c, "j16"))
    if lc and not lc.get("metadata", {}).get("incomplete"):
        for s in LC_SHAPES:
            b, c = busy_of(lc, s, "comp-off"), cycles_of(lc, s, "comp-off")
            if b is not None and c is not None:
                pts.append((b, c, s))
    return sorted(pts)


def interpolate(pts, busy):
    """Reference cycles at `busy`, linear between the two points around it; None outside."""
    for (b0, c0, _), (b1, c1, _) in zip(pts, pts[1:]):
        if b0 <= busy <= b1 and b1 > b0:
            return c0 + (c1 - c0) * (busy - b0) / (b1 - b0)
    return None


def tables(runs):
    L, js = [], {"runs": {}, "families": {}}
    L.append("# Feature rows, session 2\n")
    L.append("## Runs\n")
    for name in ("aa-2", "run-f", "14-compression", "lc-j16", "14b", "lc-sfh"):
        res = runs.get(name)
        if res is None:
            L.append("- %s: not run" % name)
            continue
        md = res.get("metadata", {})
        inv = sum(1 for m in res["legs"] if not m.get("verdict", {}).get("valid"))
        js["runs"][name] = {"rounds_complete": md.get("rounds_complete"), "incomplete": md.get("incomplete"),
                            "legs": len(res["legs"]), "invalid": inv, "stop": md.get("stop_reason"),
                            "aborted": md.get("aborted"), "wasm_unchanged_at_end": md.get("wasm_unchanged_at_end")}
        L.append("- %s: %d legs, %d invalid; %s complete rounds%s; stop: %s%s" % (
            name, len(res["legs"]), inv, md.get("rounds_complete"),
            " (**incomplete, no verdict**)" if md.get("incomplete") else "", md.get("stop_reason"),
            "; Wasm modules unchanged at the end: %s" % md["wasm_unchanged_at_end"]
            if "wasm_unchanged_at_end" in md else ""))
    L.append("")
    secondary = [FT.row(runs, s, "secondary") for s in SECONDARY]
    FT.holm(secondary)
    aa = aa_status(runs, secondary)
    L.append("## A/A (AA-2, same session, an earlier run)\n")
    L.append("| Run / shape | A/A row | Half-width | Reach | Holm p | Pass |\n|---|---|---|---|---|---|")
    for key, st in sorted(aa.items()):
        if "reach" not in st:
            L.append("| %s / %s | - | - | - | - | %s |" % (key[0], key[1], st.get("why")))
            continue
        L.append("| %s / %s | %s on %s%s | %.2f | %.2f | %s | %s |" % (
            key[0], key[1], st["spec"][2], st["spec"][1], " (borrowed)" if st["borrowed"] else "", st["hw"],
            st["reach"], "%.3g" % st["holm_p"] if st.get("holm_p") is not None else "-", "yes" if st["ok"] else "no"))
    L.append("")
    js["aa"] = {"%s/%s" % k: v for k, v in aa.items()}

    def family(title, name, rows):
        k = FT.holm(rows)
        have = sum(1 for r in rows if r.get("t_p") is not None)
        for r in rows:
            r["verdict"] = FT.verdict(r, aa.get((r["run"], r["shape"])))
        L.append("## %s (Holm over %d rows, %d with data)\n" % (title, k, have))
        L.append(FT.HDR)
        for r in rows:
            L.append(FT.fmt_row(r))
        L.append("")
        js["families"][name] = {"size": k, "with_data": have, "rows": rows}
        return rows

    conf = family("Confirmatory rows", "confirmatory", [FT.row(runs, s, "confirmatory") for s in CONFIRMATORY])
    for r in secondary:
        r["verdict"] = FT.verdict(r, aa.get((r["run"], r["shape"])))
    L.append("## Secondary rows (Holm over %d rows, %d with data)\n" % (
        len(secondary), sum(1 for r in secondary if r.get("t_p") is not None)))
    L.append(FT.HDR)
    for r in secondary:
        L.append(FT.fmt_row(r))
    L.append("")
    js["families"]["secondary"] = {"size": len(secondary), "rows": secondary}
    r14b = family("Row 14b", "14b", [FT.row(runs, s, "14b") for s in ROW_14B]) if "14b" in runs else []

    inc = [r for r in conf + secondary + r14b if r.get("incomplete") and r.get("t_p_incomplete") is not None]
    if inc:
        L.append("## Rows of incomplete runs (no verdict, not in any Holm step)\n")
        for r in inc:
            L.append("- %s %s %s vs %s: %+.2f%% [%+.2f, %+.2f], raw p %.3g" % (
                r["label"], r["shape"], r["arm"], r["ref"], r["effect_pct"], r["lo_pct"], r["hi_pct"],
                r["t_p_incomplete"]))
        L.append("")

    L.append("## Absolute cost, user and kernel split, both busy levels (exploratory)\n")
    L.append("On loopback the kernel cycles include part of the client's receive work, which shrinks with a "
             "compressed response; the user-cycle difference is the transferable part. A percentage whose arm runs "
             "busier than its reference is a lower bound.\n")
    L.append("| Row | Shape | Ref -> arm total (k) | Added (k) | cycles:u effect | Added user (k) | cycles:k effect | "
             "instructions:u effect | Busy ref -> arm |\n|---|---|---|---|---|---|---|---|---|")
    for r in conf + secondary + r14b:
        if r.get("missing"):
            continue
        e = lambda k: ("%+.2f%%" % r[k]["effect_pct"]) if k in r else "-"  # noqa: E731
        au = r["cycles_u"]["abs_diff_mean"] / 1e3 if "cycles_u" in r else None
        L.append("| %s | %s | %.1f -> %.1f | %+.2f | %s | %s | %s | %s | %s -> %s |" % (
            r["label"], r["shape"], r["ref_median"] / 1e3, r["arm_median"] / 1e3, r["abs_diff_mean"] / 1e3,
            e("cycles_u"), "-" if au is None else "%+.2f" % au, e("cycles_k"), e("instructions_u"),
            FT.busy(r["busy"].get(r["ref"])), FT.busy(r["busy"].get(r["arm"]))))
    L.append("")

    L.append("## Exploratory rows (interval only)\n")
    L.append("| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Pairs |\n|---|---|---|---|---|---|")
    expl = []
    for spec in EXPLORATORY:
        r = FT.row(runs, spec, "exploratory")
        expl.append(r)
        if r.get("missing"):
            L.append("| %s | %s | %s vs %s | - | - | - |" % (r["label"], r["shape"], r["arm"], r["ref"]))
            continue
        L.append("| %s | %s | %s vs %s | %+.2f%% [%+.2f, %+.2f] | [%+.2f, %+.2f] | %d |" % (
            r["label"], r["shape"], r["arm"], r["ref"], r["effect_pct"], r["lo_pct"], r["hi_pct"],
            r["widened_lo_pct"], r["widened_hi_pct"], r["n"]))
    L.append("")
    js["exploratory"] = expl

    r14 = runs.get("14-compression")
    js["compression"] = {}
    if r14:
        L.append("## Compression: ratio, minor faults, upstream segments (means over valid legs)\n")
        L.append("| Arm | Shape | Ratio (uncompressed / compressed) | Minor faults / req | Upstream segments in / "
                 "response |\n|---|---|---|---|---|")
        for s in ("j4", "j16"):
            for a in ("comp-off",) + LIBS:
                ratio = leg_means(r14, s, a, ratio_getter(a))[0] if a in LIBS else None
                mf = leg_means(r14, s, a, lambda m: m["per_req"]["events"]["minor-faults"])[0]
                sg = leg_means(r14, s, a, lambda m: m.get("upstream_segs_in_per_response"))[0]
                js["compression"]["%s/%s" % (s, a)] = {"ratio": ratio, "minor_faults_per_req": mf,
                                                       "upstream_segs_per_response": sg}
                L.append("| %s | %s | %s | %s | %s |" % (a, s, "-" if ratio is None else "%.2f" % ratio,
                                                         "-" if mf is None else "%.3f" % mf,
                                                         "-" if sg is None else "%.2f" % sg))
        L.append("")

    pts = load_curve(runs)
    js["load_curve"] = {"points": pts, "rows": []}
    L.append("## Load curve of the j16 reference (internal, exploratory)\n")
    if len(pts) < 2:
        L.append("Not enough points (%d).\n" % len(pts))
    else:
        L.append("Points (busy, k cycles per request): %s\n" % ", ".join(
            "%s %.1f%% %.1f" % (n, 100 * b, c / 1e3) for b, c, n in pts))
        L.append("| Arm | Busy | Arm cycles (k) | Reference at that busy (k) | Load-matched added (k) | As % |\n"
                 "|---|---|---|---|---|---|")
        for a in LIBS:
            b, c = busy_of(r14, "j16", a), cycles_of(r14, "j16", a)
            ref = interpolate(pts, b) if b is not None else None
            row = {"arm": a, "busy": b, "cycles": c, "ref_at_busy": ref}
            if ref is not None and c is not None:
                row["added"] = c - ref
                row["pct"] = 100.0 * (c / ref - 1.0)
                L.append("| %s | %.1f%% | %.1f | %.1f | %+.1f | %+.1f%% |" % (
                    a, 100 * b, c / 1e3, ref / 1e3, row["added"] / 1e3, row["pct"]))
            else:
                L.append("| %s | %s | %s | outside the curve | - | - |" % (
                    a, FT.busy(b), "-" if c is None else "%.1f" % (c / 1e3)))
            js["load_curve"]["rows"].append(row)
        L.append("")

    L.append("## Evidence and side services (every current leg)\n")
    js["evidence"] = {}
    for name, res in runs.items():
        ev = FT.evidence_summary(res)
        js["evidence"][name] = ev
        for k, v in sorted(ev.items()):
            L.append("- %s %s: evidence ok on %d of %d legs" % (name, k, v["evidence_ok"], v["legs"]))
    L.append("")
    return "\n".join(L) + "\n", js


def jit(run_dir):
    """{arm: {wu5, wu30, diff_pct}} of user instructions per request; and whether all are within the limit."""
    res = FT.load_run(run_dir)
    if res is None:
        raise SystemExit("no results.json in %s" % run_dir)
    out, ok = {}, True
    legs = [m for m in res["legs"] if not m.get("superseded") and (m.get("verdict") or {}).get("valid")]
    for arm in sorted({m["arm"] for m in legs}):
        v = {}
        for s in ("s-wu5", "s-wu30"):
            xs = [m["per_req"]["instructions_u"] for m in legs if m["arm"] == arm and m["shape"] == s]
            v[s] = stats.mean(xs) if xs else None
        d = 100.0 * (v["s-wu5"] / v["s-wu30"] - 1.0) if v["s-wu5"] and v["s-wu30"] else None
        if d is None or abs(d) > JIT_LIMIT_PCT:
            ok = False
        out[arm] = {"wu5": v["s-wu5"], "wu30": v["s-wu30"], "diff_pct": d}
    return out, ok


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "jit":
        out, ok = jit(sys.argv[2])
        for a, v in out.items():
            print("JIT %s: instructions:u per request, 5 s warm-up %s, 30 s %s, difference %s" % (
                a, "-" if v["wu5"] is None else "%.0f" % v["wu5"], "-" if v["wu30"] is None else "%.0f" % v["wu30"],
                "-" if v["diff_pct"] is None else "%+.3f%%" % v["diff_pct"]))
        print("JIT check: %s (limit %.1f%%)%s" % ("PASS" if ok else "FAIL", JIT_LIMIT_PCT,
                                                 "" if ok else "; run F should use a 15 s warm-up (f_warmup_s 15)"))
        sys.exit(0 if ok else 4)
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--json")
    a = ap.parse_args()
    text, js = tables(FT.load_session(a.session))
    sys.stdout.write(text)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(js, f, indent=1, default=str)


if __name__ == "__main__":
    main()
