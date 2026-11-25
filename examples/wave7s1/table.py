#!/usr/bin/env python3
"""Wave 7 S1 tables from a run directory's results.json, recomputed from the legs.

    python3 examples/wave7s1/table.py RUN_DIR [--json OUT]

Per shape: medians per arm; every pre-registered row as the mean per-round log ratio with the 95% t
interval, the widened interval 1.96*sqrt(SE^2+0.34^2), and the QUOTED interval (the wider of the two).
Units are written on every column: `simple %` is expm1 of the log figure (kill lines, anchor bands and
the A/A floor are read on simple %); `log-%` is 100*ln(ratio). Holm over the run's confirmatory rows.
The A/A gate is per shape: its quoted interval must include 0 and |effect| (simple %) must be under the
floor (1.0% shape s; 1.5% the relay shapes). A finding needs |effect| at or above the floor, outside the
A/A reach (|A/A| + its quoted half-width, simple %), a quoted interval that excludes 0, and Holm p < 0.05."""
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from epl import stats  # noqa: E402

RUNS = {
    "s1a": {"metric": "cycles_total_all", "aa": ("pair-A2", "pair"), "floor": {"s": 1.0},
            "conf": [("pair-l4", "pair"), ("pair-mtls-l4", "pair-mtls"), ("pair-uds", "pair"), ("one-uds", "one-ppd")],
            "other": [("pair", "one-ppd"), ("pair-mtls", "pair"), ("pair-l4", "one-ppd"), ("pair-mtls-l4", "pair-l4"),
                      ("one-ppd-B2", "one-ppd"), ("one-ppd-B3", "one-ppd")]},
    "s1b": {"metric": "cycles_total", "aa": ("tcp-A2", "tcp"), "floor": {"p64": 1.5, "p1k": 1.5},
            "conf": [("tcp-noidle", "tcp"), ("http", "tcp")], "other": []},
}
EXTRA = ["cycles_u", "cycles_k", "instructions_u", "instructions_k", "context_switches"]
HOP = ["cycles_total", "cycles_u", "cycles_k", "instructions_u"]


def val(m, metric):
    if metric.startswith("hop2:"):
        return (m.get("hop2_per_req") or {}).get(metric[5:])
    if metric in ("p50_us", "p99_us"):
        return (m.get("latency_us") or {}).get(metric[:3])
    return (m.get("per_req") or {}).get(metric)


def row(legs, shape, arm, ref, metric):
    """Paired per-round log ratios arm/ref over rounds where both legs are valid."""
    by = {}
    for m in legs:
        if m.get("shape") == shape and m.get("arm") in (arm, ref) and (m.get("verdict") or {}).get("valid"):
            v = val(m, metric)
            if v:
                by.setdefault(m["round"], {})[m["arm"]] = v
    d = [100.0 * math.log(x[arm] / x[ref]) for r, x in sorted(by.items()) if arm in x and ref in x]
    n = len(d)
    if n < 3:
        return None
    mu, sd = stats.mean(d), stats.stdev(d)
    se = sd / math.sqrt(n)
    tq = stats.t_ppf(0.975, n - 1)
    t_hw, w_hw = tq * se, 1.96 * math.sqrt(se * se + 0.34 ** 2)
    hw = max(t_hw, w_hw)
    p = 2.0 * (1.0 - stats.t_cdf(abs(mu) / se, n - 1)) if se > 0 else 0.0
    sp = lambda x: math.expm1(x / 100.0) * 100.0  # noqa: E731
    return {"arm": arm, "ref": ref, "metric": metric, "n": n, "log_pct": mu, "log_t_hw": t_hw, "log_widened_hw": w_hw,
            "log_quoted": [mu - hw, mu + hw], "which": "t" if t_hw >= w_hw else "widened",
            "simple_pct": sp(mu), "simple_quoted": [sp(mu - hw), sp(mu + hw)], "t_p": p, "up": sum(1 for x in d if x > 0)}


def med(legs, shape, arm, metric):
    v = sorted(x for x in (val(m, metric) for m in legs if m.get("shape") == shape and m.get("arm") == arm
                           and (m.get("verdict") or {}).get("valid")) if x is not None)
    return stats.median(v) if v else None


def fmt(r, holm=None):
    return "| %s vs %s | %+.2f | [%+.2f, %+.2f] | %+.2f | ±%.2f / ±%.2f (%s) | %d/%d | %.2g | %s |" % (
        r["arm"], r["ref"], r["simple_pct"], r["simple_quoted"][0], r["simple_quoted"][1], r["log_pct"],
        r["log_t_hw"], r["log_widened_hw"], r["which"], r["up"], r["n"], r["t_p"], "%.2g" % holm if holm is not None else "-")


HEAD = ("| row (%s) | effect, simple %% | quoted 95%% interval, simple %% | effect, log-%% | half-width t / widened, log-%% "
        "(wider) | rounds up | t p | Holm p |\n|---|---|---|---|---|---|---|---|")


def main(argv):
    rd = argv[0].rstrip("/")
    d = json.load(open(os.path.join(rd, "results.json")))
    legs = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]
    name = d.get("config", {}).get("name") or os.path.basename(rd)
    spec = RUNS["s1a" if "s1a" in os.path.basename(rd) else "s1b"]
    met = spec["metric"]
    arms = sorted({m["arm"] for m in legs})
    shapes = sorted({m["shape"] for m in legs})
    out = {"run": os.path.basename(rd), "metric": met, "shapes": {}}
    print("# %s: primary metric %s (cycles user+kernel per request%s)" % (
        os.path.basename(rd), met, ", both hops" if met.endswith("_all") else ""))
    print("\nlegs: %d current, %d valid; evidence failing: %d" % (
        len(legs), sum(1 for m in legs if m["verdict"]["valid"]),
        sum(1 for m in legs if (m.get("evidence") or {"ok": True}).get("ok") is False)))
    # Holm over the confirmatory rows of the whole run (every shape)
    conf = []
    for sh in shapes:
        for a, r in spec["conf"]:
            x = row(legs, sh, a, r, met)
            if x:
                conf.append((sh, x))
    hp = stats.holm([x["t_p"] for _, x in conf]) if conf else []
    holm = {(sh, x["arm"], x["ref"]): p for (sh, x), p in zip(conf, hp)}
    for sh in shapes:
        S = out["shapes"][sh] = {"medians": {}, "rows": [], "aa": None}
        print("\n## shape %s\n" % sh)
        print("| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | ctx sw /req | p50 µs | p99 µs | client 2xx/s | upstream conns (end of window) |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for a in arms:
            mine = [m for m in legs if m["arm"] == a and m["shape"] == sh]
            if not mine:
                continue
            g = lambda k: med(legs, sh, a, k)  # noqa: E731
            k = lambda v, s=1e3, f="%.1fk": (f % (v / s)) if v is not None else "-"  # noqa: E731
            S["medians"][a] = {x: g(x) for x in [met, "cycles_total", "cycles_u", "cycles_k", "instructions_u", "hop2:cycles_total",
                                                 "hop2:cycles_u", "hop2:cycles_k", "hop2:instructions_u", "p50_us", "p99_us"]}
            cr = sorted(m.get("client_rate_2xx") or 0 for m in mine)
            cu = sorted((m.get("conn_upstream") or {}).get("conns", -1) for m in mine)
            print("| %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %.1f–%.1f | %s–%s |" % (
                a, sum(1 for m in mine if m["verdict"]["valid"]), len(mine), k(g(met)), k(g("cycles_u")), k(g("cycles_k")),
                k(g("instructions_u")), k(g("context_switches"), 1, "%.2f"), k(g("p50_us"), 1, "%.0f"), k(g("p99_us"), 1, "%.0f"),
                cr[0], cr[-1], cu[0], cu[-1]))
        if any(val(m, "hop2:cycles_total") for m in legs if m["shape"] == sh):
            print("\n| arm | hop A cycles /req | hop A user | hop A kernel | hop B cycles /req | hop B user | hop B kernel | hop B instr user |")
            print("|---|---|---|---|---|---|---|---|")
            for a in arms:
                g = lambda k: med(legs, sh, a, k)  # noqa: E731
                if g("hop2:cycles_total") is None:
                    continue
                print("| %s | %.1fk | %.1fk | %.1fk | %.1fk | %.1fk | %.1fk | %.1fk |" % (
                    a, g("cycles_total") / 1e3, g("cycles_u") / 1e3, g("cycles_k") / 1e3, g("hop2:cycles_total") / 1e3,
                    g("hop2:cycles_u") / 1e3, g("hop2:cycles_k") / 1e3, g("hop2:instructions_u") / 1e3))
        aa = row(legs, sh, spec["aa"][0], spec["aa"][1], met)
        floor = spec["floor"].get(sh, 1.5)
        print("\n" + HEAD % ("A/A, %s" % met))
        if aa:
            ok = aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] and abs(aa["simple_pct"]) < floor
            reach = abs(aa["simple_pct"]) + (aa["simple_quoted"][1] - aa["simple_quoted"][0]) / 2.0
            S["aa"] = dict(aa, floor_simple_pct=floor, gate_pass=ok, reach_simple_pct=reach)
            print(fmt(aa))
            print("\nA/A gate (shape %s, floor %.1f%% simple): **%s**; A/A reach %.2f%% (simple)" % (
                sh, floor, "PASS" if ok else "FAIL: this shape's rows are void", reach))
        else:
            reach = None
            print("| (no A/A row: fewer than 3 paired rounds) |")
            print("\nA/A gate (shape %s): **FAIL (no A/A data)**" % sh)
        print("\n" + HEAD % ("confirmatory, %s" % met))
        for a, r in spec["conf"]:
            x = row(legs, sh, a, r, met)
            if not x:
                continue
            h = holm.get((sh, a, r))
            x["holm_p"] = h
            x["finding"] = bool(S["aa"] and S["aa"]["gate_pass"] and abs(x["simple_pct"]) >= floor and reach is not None
                                and abs(x["simple_pct"]) > reach and not (x["log_quoted"][0] <= 0 <= x["log_quoted"][1])
                                and h is not None and h < 0.05)
            x["kind"] = "confirmatory"
            S["rows"].append(x)
            print(fmt(x, h) + (" finding" if x["finding"] else " not a finding"))
        rows2 = [x for x in (row(legs, sh, a, r, met) for a, r in spec["other"]) if x]
        if rows2:
            print("\n" + HEAD % ("anchor and exploratory, %s" % met))
            for x in rows2:
                x["kind"] = "other"
                S["rows"].append(x)
                print(fmt(x))
        print("\n" + HEAD % "parts, exploratory")
        for a, r in spec["conf"] + spec["other"][:2]:
            for mm in EXTRA + (["hop2:" + h for h in HOP] if met.endswith("_all") else []) + ["p50_us", "p99_us"]:
                x = row(legs, sh, a, r, mm)
                if x:
                    x["kind"] = "part"
                    S["rows"].append(x)
                    print(fmt(dict(x, arm="%s [%s]" % (a, mm))))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1:])
