#!/usr/bin/env python3
"""Wave 7 S2 tables from a run directory's results.json, recomputed from the legs.

    python3 examples/wave7s2/table.py RUN_DIR [--json OUT]

Per shape: medians per arm; every pre-registered row as the mean per-round log ratio with the 95% t
interval, the widened interval 1.96*sqrt(SE^2+0.34^2), and the QUOTED interval (the wider of the two).
Units are written on every column: `simple %` is expm1 of the log figure (kill lines, anchor bands and
the A/A floor are read on simple %); `log-%` is 100*ln(ratio). Holm over the run's confirmatory rows.
The A/A gate is per shape: its quoted interval must include 0 and |effect| (simple %) must be under the
floor (1.5% the new HTTP/1 shapes; 2.0% HTTP/3). A finding needs |effect| at or above the floor, outside the
A/A reach (|A/A| + its quoted half-width, simple %), a quoted interval that excludes 0, and Holm p < 0.05.
A shape whose A/A gate fails reports no finding (its rows are printed as void).

Run-specific parts:
  s2a  the patch gate (ch8k vs cl8k, simple %, 3% at 64 KiB and 6% at 1 MiB), the per-byte slope of h2in
  s2b  cycles per event = (cycles per request on ev200 - on ev20) / 180, per round and arm, t interval
  s2c  pauses, resumes per request from Envoy's flow-control counters
  s2d  the anchor band at 4 KB, the 0-byte premium as a share of the 4 KB premium (cycles, per round),
       box-wide UDP datagrams per request"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from epl import stats  # noqa: E402

RUNS = {
    "s2a": {"aa": ("cl-A2", "cl"), "floor": 1.5,
            "conf": [("ch8k", "cl8k"), ("ch8k", "cl"), ("ch4k", "cl"), ("h2in", "cl")],
            "other": [("cl8k", "cl"), ("ch4k", "ch8k"), ("h2in", "cl8k")]},
    "s2b": {"aa": ("base-A2", "base"), "floor": 1.5, "conf": [("idle-off", "base")], "other": []},
    "s2c": {"aa": ("buf-default-A2", "buf-default"), "floor": 1.5, "conf": [("buf-32k", "buf-default")], "other": []},
    "s2d": {"aa": ("h3-A2", "h3"), "floor": 2.0, "conf": [("h3", "h2tls")], "other": [("h3-A2", "h2tls")]},
}
MET = "cycles_total"
EXTRA = ["cycles_u", "cycles_k", "instructions_u", "instructions_k", "context_switches"]
FLOW = {"up paused": "cluster.origin.upstream_flow_control_paused_reading_total",
        "up resumed": "cluster.origin.upstream_flow_control_resumed_reading_total",
        "up backed up": "cluster.origin.upstream_flow_control_backed_up_total",
        "up drained": "cluster.origin.upstream_flow_control_drained_total",
        "down paused": "http.ingress_http.downstream_flow_control_paused_reading_total",
        "down resumed": "http.ingress_http.downstream_flow_control_resumed_reading_total"}


def val(m, metric):
    if metric in ("p50_us", "p99_us"):
        return (m.get("latency_us") or {}).get(metric[:3])
    return (m.get("per_req") or {}).get(metric)


def valid(m):
    return bool((m.get("verdict") or {}).get("valid"))


def interval(d):
    """Mean, t and widened half-widths of per-round values d (log-% or cycles)."""
    n = len(d)
    mu, sd = stats.mean(d), stats.stdev(d)
    se = sd / math.sqrt(n)
    tq = stats.t_ppf(0.975, n - 1)
    p = 2.0 * (1.0 - stats.t_cdf(abs(mu) / se, n - 1)) if se > 0 else 0.0
    return mu, se, tq * se, p


def row(legs, shape, arm, ref, metric):
    """Paired per-round log ratios arm/ref over rounds where both legs are valid."""
    by = {}
    for m in legs:
        if m.get("shape") == shape and m.get("arm") in (arm, ref) and valid(m):
            v = val(m, metric)
            if v:
                by.setdefault(m["round"], {})[m["arm"]] = v
    d = [100.0 * math.log(x[arm] / x[ref]) for r, x in sorted(by.items()) if arm in x and ref in x]
    n = len(d)
    if n < 3:
        return None
    mu, se, t_hw, p = interval(d)
    w_hw = 1.96 * math.sqrt(se * se + 0.34 ** 2)
    hw = max(t_hw, w_hw)
    sp = lambda x: math.expm1(x / 100.0) * 100.0  # noqa: E731
    # the same pairs as a difference in cycles per request (mean and t half-width)
    dc = [x[arm] - x[ref] for r, x in sorted(by.items()) if arm in x and ref in x]
    cmu, _, chw, _ = interval(dc)
    return {"arm": arm, "ref": ref, "metric": metric, "n": n, "log_pct": mu, "log_t_hw": t_hw, "log_widened_hw": w_hw,
            "log_quoted": [mu - hw, mu + hw], "which": "t" if t_hw >= w_hw else "widened",
            "simple_pct": sp(mu), "simple_quoted": [sp(mu - hw), sp(mu + hw)], "t_p": p, "up": sum(1 for x in d if x > 0),
            "diff_per_req": cmu, "diff_per_req_t_hw": chw}


def med(legs, shape, arm, metric):
    v = sorted(x for x in (val(m, metric) for m in legs if m.get("shape") == shape and m.get("arm") == arm and valid(m))
               if x is not None)
    return stats.median(v) if v else None


def medf(legs, shape, arm, fn):
    v = sorted(x for x in (fn(m) for m in legs if m.get("shape") == shape and m.get("arm") == arm and valid(m))
               if x is not None)
    return stats.median(v) if v else None


def fmt(r, holm=None):
    return "| %s vs %s | %+.2f | [%+.2f, %+.2f] | %+.2f | ±%.2f / ±%.2f (%s) | %d/%d | %.2g | %s | %+.1fk ± %.1fk |" % (
        r["arm"], r["ref"], r["simple_pct"], r["simple_quoted"][0], r["simple_quoted"][1], r["log_pct"],
        r["log_t_hw"], r["log_widened_hw"], r["which"], r["up"], r["n"], r["t_p"], "%.2g" % holm if holm is not None else "-",
        r["diff_per_req"] / 1e3, r["diff_per_req_t_hw"] / 1e3)


HEAD = ("| row (%s) | effect, simple %% | quoted 95%% interval, simple %% | effect, log-%% | half-width t / widened, log-%% "
        "(wider) | rounds up | t p | Holm p | paired difference per request (mean ± t half-width; cycles unless the row "
        "names another metric) |\n|---|---|---|---|---|---|---|---|---|")


def paired_shapes(legs, arm, metric, hi, lo, fn):
    """Per round, fn(value on shape hi, value on shape lo) for one arm; rounds where both legs are valid."""
    by = {}
    for m in legs:
        if m.get("arm") == arm and m.get("shape") in (hi, lo) and valid(m):
            v = val(m, metric)
            if v:
                by.setdefault(m["round"], {})[m["shape"]] = v
    return [fn(x[hi], x[lo]) for r, x in sorted(by.items()) if hi in x and lo in x]


def per_event(legs, out):
    print("\n## cycles per streamed event: (per request on ev200 - per request on ev20) / 180, per round\n")
    print("| arm | metric | per event, mean | 95% t interval | rounds |\n|---|---|---|---|---|")
    out["per_event"] = {}
    for arm in sorted({m["arm"] for m in legs}):
        for metric in ("cycles_total", "cycles_u", "cycles_k", "instructions_u", "instructions_k", "context_switches"):
            d = paired_shapes(legs, arm, metric, "ev200", "ev20", lambda a, b: (a - b) / 180.0)
            if len(d) < 3:
                continue
            mu, _, hw, _ = interval(d)
            out["per_event"].setdefault(arm, {})[metric] = {"mean": mu, "t_hw": hw, "n": len(d)}
            f = "%.3f" if metric == "context_switches" else "%.0f"
            print(("| %s | %s | " + f + " | [" + f + ", " + f + "] | %d |") % (arm, metric, mu, mu - hw, mu + hw, len(d)))
    # the per-request part: what a response costs besides its events (ev20 minus 20 events)
    b = out["per_event"].get("base", {}).get("cycles_total")
    if b:
        m20 = med(legs, "ev20", "base", MET)
        print("\nbase: per-request part (median ev20 - 20 events) = %.0f cycles; an event is %.1f%% of an ev200 request / 200" % (
            m20 - 20 * b["mean"], 100.0 * b["mean"] * 200 / med(legs, "ev200", "base", MET)))


def h3_parts(legs, out):
    print("\n## HTTP/3 premium at 0 B as a share of the premium at 4 KB (cycles per request, h3 - h2tls, per round)\n")
    by = {}
    for m in legs:
        if valid(m) and val(m, MET):
            by.setdefault(m["round"], {})[(m["shape"], m["arm"])] = m
    out["h3"] = {}
    for metric in ("cycles_total", "cycles_u", "cycles_k"):
        pz, ps, share = [], [], []
        for r, x in sorted(by.items()):
            if all(k in x for k in (("z0", "h3"), ("z0", "h2tls"), ("s", "h3"), ("s", "h2tls"))):
                a = val(x[("z0", "h3")], metric) - val(x[("z0", "h2tls")], metric)
                b = val(x[("s", "h3")], metric) - val(x[("s", "h2tls")], metric)
                pz.append(a)
                ps.append(b)
                share.append(100.0 * a / b)
        if len(share) < 3:
            continue
        o = {}
        for k, d in (("premium_z0", pz), ("premium_s", ps), ("share_pct", share), ("extra_0_to_4k", [b - a for a, b in zip(pz, ps)])):
            mu, _, hw, _ = interval(d)
            o[k] = {"mean": mu, "t_hw": hw, "n": len(d)}
        out["h3"][metric] = o
        print("%s: premium at 0 B %+.1fk ± %.1fk, at 4 KB %+.1fk ± %.1fk, extra from 0 B to 4 KB %+.1fk ± %.1fk; "
              "0 B premium = %.1f%% of the 4 KB premium [%.1f, %.1f] (per-round ratio, 95%% t, %d rounds)" % (
                  metric, o["premium_z0"]["mean"] / 1e3, o["premium_z0"]["t_hw"] / 1e3, o["premium_s"]["mean"] / 1e3,
                  o["premium_s"]["t_hw"] / 1e3, o["extra_0_to_4k"]["mean"] / 1e3, o["extra_0_to_4k"]["t_hw"] / 1e3,
                  o["share_pct"]["mean"], o["share_pct"]["mean"] - o["share_pct"]["t_hw"],
                  o["share_pct"]["mean"] + o["share_pct"]["t_hw"], o["share_pct"]["n"]))
    print("\n| shape | arm | UDP datagrams out /request (box-wide, median) | in /request | busiest worker share (min-max) |\n|---|---|---|---|---|")
    for sh in ("z0", "s"):
        for arm in ("h2tls", "h3", "h3-A2"):
            u = lambda k: medf(legs, sh, arm, lambda m: ((m.get("kernel_net") or {}).get("d") or {}).get(k, 0) / m["responses_raw"]  # noqa: E731
                               if m.get("responses_raw") else None)
            ws = sorted(m.get("envoy_worker_max_share") or 0 for m in legs if m["shape"] == sh and m["arm"] == arm and valid(m))
            if ws:
                out["h3"].setdefault("udp", {})["%s/%s" % (sh, arm)] = {"out": u("UdpOutDatagrams"), "in": u("UdpInDatagrams")}
                print("| %s | %s | %.3f | %.3f | %.3f-%.3f |" % (sh, arm, u("UdpOutDatagrams") or 0, u("UdpInDatagrams") or 0, ws[0], ws[-1]))


def main(argv):
    rd = argv[0].rstrip("/")
    d = json.load(open(os.path.join(rd, "results.json")))
    legs = [m for m in d["legs"] if not m.get("superseded") and m.get("arm")]
    key = [k for k in RUNS if k in os.path.basename(rd)][0]
    spec = RUNS[key]
    arms = sorted({m["arm"] for m in legs})
    shapes = sorted({m["shape"] for m in legs})
    out = {"run": os.path.basename(rd), "metric": MET, "shapes": {}}
    print("# %s: primary metric %s (cycles user+kernel per request, Envoy process)" % (os.path.basename(rd), MET))
    print("\nlegs: %d current, %d valid; evidence failing: %d; target rates: %s" % (
        len(legs), sum(1 for m in legs if valid(m)),
        sum(1 for m in legs if (m.get("evidence") or {"ok": True}).get("ok") is False),
        ", ".join("%s %s/s" % (s, sorted({m["target_rps"] for m in legs if m["shape"] == s})) for s in shapes)))
    conf = []
    for sh in shapes:
        for a, r in spec["conf"]:
            x = row(legs, sh, a, r, MET)
            if x:
                conf.append((sh, x))
    hp = stats.holm([x["t_p"] for _, x in conf]) if conf else []
    holm = {(sh, x["arm"], x["ref"]): p for (sh, x), p in zip(conf, hp)}
    for sh in shapes:
        S = out["shapes"][sh] = {"medians": {}, "rows": [], "aa": None}
        print("\n## shape %s\n" % sh)
        print("| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user | instr kernel | ctx sw /req | p50 µs | p99 µs | "
              "Envoy busy (CPUs of 4) | client 2xx/s | origin CPU share of its set (max) | busiest worker share (max) |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for a in arms:
            mine = [m for m in legs if m["arm"] == a and m["shape"] == sh]
            if not mine:
                continue
            g = lambda k: med(legs, sh, a, k)  # noqa: E731
            k = lambda v, s=1e3, f="%.1fk": (f % (v / s)) if v is not None else "-"  # noqa: E731
            S["medians"][a] = {x: g(x) for x in [MET, "cycles_u", "cycles_k", "instructions_u", "instructions_k",
                                                 "context_switches", "p50_us", "p99_us"]}
            cr = sorted(m.get("client_rate_2xx") or 0 for m in mine)
            so = [max(((m.get("side_services") or {}).get(n) or {}).get("busy_of_set") or 0 for n in ("stream_origin", "origin"))
                  for m in mine]
            busy = medf(legs, sh, a, lambda m: m.get("envoy_cpus_run"))
            S["medians"][a].update(envoy_cpus_run=busy, origin_busy_max=max(so) if so else None)
            for name, st in FLOW.items():
                S["medians"][a]["flow " + name] = medf(legs, sh, a, lambda m, st=st: (m.get("sut_stats_window") or {}).get(st, 0)
                                                       / m["responses_raw"] if m.get("responses_raw") else None)
            print("| %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %.1f–%.1f | %.3f | %.3f |" % (
                a, sum(1 for m in mine if valid(m)), len(mine), k(g(MET)), k(g("cycles_u")), k(g("cycles_k")),
                k(g("instructions_u")), k(g("instructions_k")), k(g("context_switches"), 1, "%.2f"), k(g("p50_us"), 1, "%.0f"),
                k(g("p99_us"), 1, "%.0f"), "%.3f" % busy if busy is not None else "-", cr[0], cr[-1], max(so) if so else 0,
                max(m.get("envoy_worker_max_share") or 0 for m in mine)))
        if any(S["medians"][a].get("flow up paused") for a in S["medians"]):
            print("\n| arm | " + " | ".join(n + " /req" for n in FLOW) + " |\n|---|" + "---|" * len(FLOW))
            for a in arms:
                if a in S["medians"]:
                    print("| %s | " % a + " | ".join("%.4f" % (S["medians"][a].get("flow " + n) or 0) for n in FLOW) + " |")
        aa = row(legs, sh, spec["aa"][0], spec["aa"][1], MET)
        floor = spec["floor"]
        print("\n" + HEAD % ("A/A, %s" % MET))
        ok, reach = False, None
        if aa:
            ok = aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] and abs(aa["simple_pct"]) < floor
            reach = abs(aa["simple_pct"]) + (aa["simple_quoted"][1] - aa["simple_quoted"][0]) / 2.0
            S["aa"] = dict(aa, floor_simple_pct=floor, gate_pass=ok, reach_simple_pct=reach)
            print(fmt(aa))
            print("\nA/A gate (shape %s, floor %.1f%% simple): **%s**; A/A reach %.2f%% (simple)" % (
                sh, floor, "PASS" if ok else "FAIL: this shape's rows are void", reach))
        else:
            print("| (no A/A row: fewer than 3 paired rounds) |")
            print("\nA/A gate (shape %s): **FAIL (no A/A data)**" % sh)
        print("\n" + HEAD % ("confirmatory, %s" % MET))
        for a, r in spec["conf"]:
            x = row(legs, sh, a, r, MET)
            if not x:
                continue
            h = holm.get((sh, a, r))
            x["holm_p"] = h
            x["finding"] = bool(ok and abs(x["simple_pct"]) >= floor and reach is not None
                                and abs(x["simple_pct"]) > reach and not (x["log_quoted"][0] <= 0 <= x["log_quoted"][1])
                                and h is not None and h < 0.05)
            x["kind"] = "confirmatory"
            x["void"] = not ok
            S["rows"].append(x)
            print(fmt(x, h) + (" VOID (A/A)" if not ok else " finding" if x["finding"] else " not a finding"))
        rows2 = [x for x in (row(legs, sh, a, r, MET) for a, r in spec["other"]) if x]
        if rows2:
            print("\n" + HEAD % ("anchor and exploratory, %s" % MET))
            for x in rows2:
                x["kind"] = "other"
                x["void"] = not ok
                S["rows"].append(x)
                print(fmt(x))
        print("\n" + HEAD % "parts, exploratory")
        for a, r in spec["conf"] + spec["other"][:1] + [spec["aa"]]:
            for mm in EXTRA + ["p50_us", "p99_us"]:
                x = row(legs, sh, a, r, mm)
                if x:
                    x["kind"] = "part"
                    S["rows"].append(x)
                    print(fmt(dict(x, arm="%s [%s]" % (a, mm))))
    if key == "s2a":
        print("\n## patch gate (candidate 5): ch8k vs cl8k, simple %; no patch when under 3% at 64 KiB and under 6% at 1 MiB\n")
        for sh, line in (("b64k", 3.0), ("b1m", 6.0)):
            S = out["shapes"].get(sh) or {}
            r = [x for x in S.get("rows", []) if x["kind"] == "confirmatory" and (x["arm"], x["ref"]) == ("ch8k", "cl8k")]
            if r:
                x = r[0]
                where = "at the line (interval straddles it)" if x["simple_quoted"][0] < line <= x["simple_quoted"][1] and x["simple_pct"] < line \
                    or x["simple_quoted"][0] < line and x["simple_pct"] >= line else ""
                print("%s: %+.2f%% [%+.2f, %+.2f] against %.0f%%: %s %s%s" % (
                    sh, x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1], line,
                    "under" if x["simple_pct"] < line else "at or above", where, " (VOID: A/A)" if x["void"] else ""))
        # h2in per-byte slope from 64 KiB to 1 MiB (per round, cycles per body byte over the cl arm)
        print("\n## per-byte slopes from 64 KiB to 1 MiB: (cycles per request on b1m - on b64k) / 983,040 bytes, per round\n")
        print("| arm | cycles per body byte, mean | 95% t interval | user | kernel | rounds |\n|---|---|---|---|---|---|")
        out["per_byte"] = {}
        for a in arms:
            res = {}
            for metric in ("cycles_total", "cycles_u", "cycles_k"):
                dd = paired_shapes(legs, a, metric, "b1m", "b64k", lambda x, y: (x - y) / (1048576.0 - 65536.0))
                if len(dd) >= 3:
                    mu, _, hw, _ = interval(dd)
                    res[metric] = {"mean": mu, "t_hw": hw, "n": len(dd)}
            if "cycles_total" in res:
                out["per_byte"][a] = res
                t = res["cycles_total"]
                print("| %s | %.3f | [%.3f, %.3f] | %.3f | %.3f | %d |" % (a, t["mean"], t["mean"] - t["t_hw"], t["mean"] + t["t_hw"],
                                                                         res["cycles_u"]["mean"], res["cycles_k"]["mean"], t["n"]))
    if key == "s2b":
        per_event(legs, out)
    if key == "s2d":
        S = out["shapes"].get("s") or {}
        r = [x for x in S.get("rows", []) if x["kind"] == "confirmatory"]
        if r:
            print("\nanchor gate: h3 vs h2tls at 4 KB %+.2f%% simple, band [+65, +85]: **%s**" % (
                r[0]["simple_pct"], "inside" if 65.0 <= r[0]["simple_pct"] <= 85.0 else "OUTSIDE (run held)"))
            out["anchor_inside"] = 65.0 <= r[0]["simple_pct"] <= 85.0
        h3_parts(legs, out)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
