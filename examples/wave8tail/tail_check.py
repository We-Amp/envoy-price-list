#!/usr/bin/env python3
"""The tail add-on after W8-3 (W8-2's follow-up), FIXED BEFORE THE FIRST LEG. Analysis only.

    tail_check.py TAIL_DIR [--json OUT]

PART 1 (W8-2's follow-up; Exploratory): legs of tail-p1-r1..r4 (h3-off, h3-both-on; QUIC
  statistics visitor with update_period 0.05 s). Per leg, server retransmitted packets
  (listener.127.0.0.1_10110.quic_stats.cx_tx_packets_retransmitted_total) split in three by the harness's snapshots:
    before = absolute at the window's end (sut_stats_end) minus the window's change (sut_stats_window)
    inside = the window's change
    after  = the end of the leg (sut_stats_leg_end) minus the absolute at the window's end
  The stop-arm EXCESS per segment = sum over the h3-both-on legs minus sum over the h3-off legs; E = the sum over the
  three segments. RULE: "at the end" when E > 0 and excess(after) >= 0.80 E; "at the start" when E > 0 and
  excess(before) >= 0.80 E; otherwise "not resolved" (also when E <= 0: no excess to place). Any h3-both-on leg with
  more than 2 retransmitted packets inside the window REOPENS the steady-state question (printed beside the rule).
PART 2 (row C4, fixed before data; the plan's 3.0% line; W8-2's rules): tail-c4, h3-reuse-on vs h3-off on s, cycles
  (user + kernel) of the Envoy process per request, mean per-round log ratio, quoted interval = the wider of the t
  interval and 1.96*sqrt(SE^2+0.34^2). Same-build check: h3-official-A2 vs h3-official, floor 2.0 log points (quoted
  interval includes 0 and |effect| under 2.0). Label MEASURED only when the same-build check passes (or |effect| is
  at least 3 times its excursion), the quoted interval excludes 0 and the row's own t p < 0.05; otherwise
  EXPLORATORY. Line: saves 3.0% or more = worth proposing on cycles; "at the line" when the quoted interval
  straddles -3.0; under 3.0% = under the line. Retransmitted and sent packets per leg (end of leg) per arm are
  printed beside the row."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import importlib.util  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


t3 = _load("w7s3_table_for_w8tail", os.path.join(HERE, "..", "wave7s3", "table.py"))
QS = "listener.127.0.0.1_10110.quic_stats."
RT, TX = QS + "cx_tx_packets_retransmitted_total", QS + "cx_tx_packets_total"
FLOOR, LINE, SHARE, INSIDE_MAX = 2.0, -3.0, 0.80, 2


def legs_of(d):
    p = os.path.join(d, "legs.jsonl")
    out, sup = [], set()
    if not os.path.exists(p):
        return out
    rows = []
    for line in open(p):
        line = line.strip()
        if line:
            m = json.loads(line)
            if "supersede" in m:
                sup.update(m["supersede"])
            elif m.get("arm"):
                rows.append(m)
    return [m for m in rows if m.get("leg_id") not in sup and not m.get("superseded")]


def split(m, k=RT):
    w = (m.get("sut_stats_window") or {}).get(k)
    e = (m.get("sut_stats_end") or {}).get(k, 0)
    le = (m.get("sut_stats_leg_end") or {}).get(k)
    if w is None or le is None:
        return None
    return {"before": e - w, "inside": w, "after": le - e, "total": le}


def part1(td, out):
    print("## Part 1: where the stop arm's retransmissions fall (Exploratory)\n")
    print("| config | arm | valid | retransmitted before / inside / after the window (total) | packets sent before / inside / after | p99 µs | max µs |")
    print("|---|---|---|---|---|---|---|")
    seg = {"h3-off": {"before": 0, "inside": 0, "after": 0}, "h3-both-on": {"before": 0, "inside": 0, "after": 0}}
    n, inside_hi, legs = {"h3-off": 0, "h3-both-on": 0}, [], []
    for r in range(1, 5):
        name = "tail-p1-r%d" % r
        for m in legs_of(os.path.join(td, name)):
            x, y = split(m), split(m, TX)
            lat = m.get("latency_us") or {}
            print("| %s | %s | %s | %s | %s | %s | %s |" % (name, m["arm"], (m.get("verdict") or {}).get("valid"),
                  "-" if x is None else "%d / %d / %d (%d)" % (x["before"], x["inside"], x["after"], x["total"]),
                  "-" if y is None else "%d / %d / %d" % (y["before"], y["inside"], y["after"]), lat.get("p99"), lat.get("max")))
            legs.append({"config": name, "arm": m["arm"], "valid": (m.get("verdict") or {}).get("valid"), "retransmitted": x, "sent": y,
                         "envoy_exit": m.get("envoy_exit"), "latency_us": lat})
            if x is None or m["arm"] not in seg or m.get("envoy_exit") != 0:
                continue
            n[m["arm"]] += 1
            for k in seg[m["arm"]]:
                seg[m["arm"]][k] += x[k]
            if m["arm"] == "h3-both-on" and x["inside"] > INSIDE_MAX:
                inside_hi.append("%s %d" % (name, x["inside"]))
    exc = {k: seg["h3-both-on"][k] - seg["h3-off"][k] for k in ("before", "inside", "after")}
    E = sum(exc.values())
    if n["h3-off"] != 4 or n["h3-both-on"] != 4:
        verdict = "NOT RESOLVED: legs with counts h3-off %d, h3-both-on %d (4 each wanted)" % (n["h3-off"], n["h3-both-on"])
    elif E <= 0:
        verdict = "NOT RESOLVED: no excess to place (E = %d)" % E
    elif exc["after"] >= SHARE * E:
        verdict = "AT THE END (%.0f%% of the excess after the window)" % (100.0 * exc["after"] / E)
    elif exc["before"] >= SHARE * E:
        verdict = "AT THE START (%.0f%% of the excess before the window)" % (100.0 * exc["before"] / E)
    else:
        verdict = "NOT RESOLVED (before %.0f%%, inside %.0f%%, after %.0f%% of the excess)" % tuple(100.0 * exc[k] / E for k in ("before", "inside", "after"))
    steady = ("REOPENS the steady-state question: h3-both-on legs with more than 2 inside the window: %s" % ", ".join(inside_hi)) if inside_hi else \
        "no h3-both-on leg has more than 2 inside the window"
    print("\nsums: h3-off %s; h3-both-on %s; excess %s; E = %d" % (seg["h3-off"], seg["h3-both-on"], exc, E))
    print("PART 1 RULE: %s; %s" % (verdict, steady))
    out["part1"] = {"legs": legs, "sums": seg, "excess": exc, "E": E, "verdict": verdict, "steady_state": steady}


def part2(td, out):
    print("\n## Part 2: row C4, h3-reuse-on vs h3-off on s (fixed before data)\n")
    d = os.path.join(td, "tail-c4", "results.json")
    if not os.path.exists(d):
        print("- not run (no results.json)")
        out["part2"] = None
        return
    res = json.load(open(d))
    legs = [m for m in res["legs"] if not m.get("superseded") and m.get("arm")]
    md = res.get("metadata") or {}
    print("- legs %d, valid %d, rounds complete %s, incomplete %s, replaced %d" % (
        len(legs), sum(1 for m in legs if t3.valid(m)), md.get("rounds_complete"), md.get("incomplete"), sum(1 for m in res["legs"] if m.get("superseded"))))
    print("\n| arm | valid legs | cycles u+k /req (median) | user | kernel | instr user /req | p50 µs | p99 µs | retransmitted per leg | sent per leg (median) | per 100,000 sent (pooled) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    arms = {}
    for a in ("h3-official", "h3-official-A2", "h3-off", "h3-reuse-on"):
        mine = [m for m in legs if m["arm"] == a]
        ok = [m for m in mine if t3.valid(m)]
        rt = [(m.get("sut_stats_leg_end") or {}).get(RT) for m in mine]
        tx = [(m.get("sut_stats_leg_end") or {}).get(TX) for m in mine]
        g = lambda k: t3.med(legs, "s", a, k)  # noqa: E731
        pooled = 1e5 * sum(x for x in rt if x) / sum(x for x in tx if x) if any(tx) else None
        arms[a] = {"legs": len(mine), "valid": len(ok), "retransmitted": rt, "sent": tx, "per_100k": pooled,
                   "cycles_total": g("cycles_total"), "cycles_u": g("cycles_u"), "cycles_k": g("cycles_k"), "instructions_u": g("instructions_u")}
        k = lambda v: "-" if v is None else "%.1fk" % (v / 1e3)  # noqa: E731
        print("| %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            a, len(ok), len(mine), k(g("cycles_total")), k(g("cycles_u")), k(g("cycles_k")), k(g("instructions_u")), g("p50_us"), g("p99_us"),
            " ".join(str(x) for x in rt), "-" if not [x for x in tx if x] else sorted(x for x in tx if x)[len([x for x in tx if x]) // 2],
            "-" if pooled is None else "%.2f" % pooled))
    aa = t3.row(legs, "s", "h3-official-A2", "h3-official", "cycles_total")
    c4 = t3.row(legs, "s", "h3-reuse-on", "h3-off", "cycles_total")
    bc = t3.row(legs, "s", "h3-off", "h3-official", "cycles_total")
    print("\n" + t3.HEAD % "rows, cycles_total")
    for x in (aa, bc, c4):
        if x:
            print(t3.fmt(x))
    if not c4:
        out["part2"] = {"arms": arms, "c4": None}
        print("\nC4: no row")
        return
    ok = bool(aa) and aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] and abs(aa["log_pct"]) < FLOOR
    three = bool(aa) and abs(c4["log_pct"]) >= 3 * abs(aa["log_pct"])
    excl = not (c4["log_quoted"][0] <= 0 <= c4["log_quoted"][1])
    measured = bool((ok or three) and excl and c4["t_p"] < 0.05)
    lo, hi = c4["simple_quoted"]
    # the point estimate decides; a quoted interval that straddles the line is "at the line"
    line = ("AT THE LINE (the quoted interval straddles -3.0)" if lo < LINE < hi else
            "saves 3.0% or more: worth proposing on cycles" if c4["simple_pct"] <= LINE else "under the 3.0% line")
    parts = {mm: t3.row(legs, "s", "h3-reuse-on", "h3-off", mm) for mm in ("cycles_u", "cycles_k", "instructions_u", "p50_us", "p99_us")}
    ag = t3.row(legs, "s", "h3-reuse-on", "h3-official", "cycles_total")
    print("\nsame-build check on s: %s (%s)" % ("PASS" if ok else "MISS", "effect %+.2f log points, quoted [%+.2f, %+.2f], floor %.1f" % (
        aa["log_pct"], aa["log_quoted"][0], aa["log_quoted"][1], FLOOR) if aa else "no row"))
    for mm, y in parts.items():
        if y:
            print("  C4 [%s, Exploratory]: %+.2f%% [%+.2f, %+.2f] simple; %+.2fk ± %.2fk per request" % (mm, y["simple_pct"], y["simple_quoted"][0],
                  y["simple_quoted"][1], y["diff_per_req"] / 1e3, y["diff_per_req_t_hw"] / 1e3))
    if ag:
        print("  C4 against the stock release [Exploratory]: h3-reuse-on vs h3-official %+.2f%% [%+.2f, %+.2f]" % (ag["simple_pct"], ag["simple_quoted"][0], ag["simple_quoted"][1]))
    print("per-round log points: C4 %s; same-build %s" % (" ".join("%+.2f" % v for v in c4["per_round_log_pct"]),
                                                          " ".join("%+.2f" % v for v in aa["per_round_log_pct"]) if aa else "-"))
    lab = "MEASURED" if measured else "EXPLORATORY"
    print("\nC4 RULE: %+.2f%% [%+.2f, %+.2f] simple, %d rounds; label %s; by the 3.0%% line: %s" % (c4["simple_pct"], lo, hi, c4["n"], lab, line))
    out["part2"] = {"arms": arms, "same_build": aa, "build_control": bc, "c4": c4, "same_build_pass": ok, "label": lab, "line": line,
                    "parts": parts, "against_official": ag}


def main(argv):
    td = argv[0].rstrip("/")
    out = {}
    part1(td, out)
    part2(td, out)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
