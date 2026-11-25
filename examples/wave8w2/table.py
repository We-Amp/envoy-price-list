#!/usr/bin/env python3
"""Wave 8 W8-2 tables: the scored runs, recomputed from the legs (analysis only; nothing here ran on the box).

    python3 examples/wave8w2/table.py RUNS_DIR [--json OUT]

RUNS_DIR holds s-1 and s-2 (shape s, one Williams square of six rounds each, pooled as rounds 1-6 and 7-12; a
round's legs are paired inside their own run only) and shi or shi-half (shape s-hi; hi.txt names which).

FIXED BEFORE ANY DATA (the wave 8 plan, sections 1 and 4.1; nothing below was changed after the run):
  rows      the mean per-round log ratio of cycles (user+kernel, Envoy process) per request, with the 95% t
            interval, the widened interval 1.96*sqrt(SE^2+0.34^2) and the QUOTED interval (the wider of the two).
            `simple %` is expm1 of the log figure; `log points` is 100*ln(ratio).
  confirmatory (Holm over 3): C1 h3-both-on vs h3-off on s; C2 h3-stop-on vs h3-off on s; C3 h3-both-on vs
            h3-off on s-hi.
  lines     anchor gate: h3-official vs h2tls on s inside [+65, +85]% (simple).
            worth proposing: C1 saves 3.0% or more (commit 1 alone when C2 saves 3.0% or more).
            killed: C1 saves under 3.0%.  harm stop: C3 a cost of +1.0% or more, interval excluding 0.
            The point estimate decides; "at the line" when the quoted interval straddles the line.
  same-build check per shape: h3-official-A2 vs h3-official; passes when its quoted interval includes 0 and
            |effect| is under the floor of 2.0 log points. On a miss a row of that shape is decided only when
            |effect| is at least three times the observed excursion; otherwise "Not resolved". Nothing is re-run.
  build control: h3-off vs h3-official. When it reads +1.0% or more (simple) with a quoted interval that
            excludes 0, the headline of the shape's rows is the figure against h3-official.
  basis     Measured (confirmatory row; the shape's same-build check passed, or the three-times rule holds) /
            Not resolved / Exploratory (every other row: against h3-official, parts, per-run rows, shares).
  finding   quoted interval excludes 0, Holm p < 0.05, and the same-build rule.
Costs beside the rows, per arm: latency p99 and maximum, UDP datagrams per request (the kernel's box-wide count
over the window, both directions: a retransmission is one more datagram), Envoy's dropped-datagram counter and
the kernel's UDP error counters. The client reports no retransmission count (departure, stated in the result)."""
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import stats  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


t3 = _load("w7s3_table_for_w8w2", os.path.join(HERE, "..", "wave7s3", "table.py"))
row, med, medf, fmt, HEAD, valid, interval = t3.row, t3.med, t3.medf, t3.fmt, t3.HEAD, t3.valid, t3.interval

FLOOR = 2.0
MET = "cycles_total"
EXTRA = ["cycles_u", "cycles_k", "instructions_u", "instructions_k", "context_switches", "p50_us", "p99_us"]
ARMS = ["h2tls", "h3-official", "h3-official-A2", "h3-off", "h3-stop-on", "h3-both-on"]
H3 = ARMS[1:]
AA = ("h3-official-A2", "h3-official")
CONTROL = ("h3-off", "h3-official")
ANCHOR = ("h3-official", "h2tls")
CONF = {"s": [("C1", "h3-both-on", "h3-off"), ("C2", "h3-stop-on", "h3-off")], "s-hi": [("C3", "h3-both-on", "h3-off")]}
OTHER = [("h3-both-on", "h3-official"), ("h3-stop-on", "h3-official"), ("h3-both-on", "h3-stop-on"), ("h3-off", "h3-official-A2"),
         ("h3-official", "h2tls"), ("h3-both-on", "h2tls")]
LINE, HARM, BAND = -3.0, 1.0, (65.0, 85.0)
DROPPED = "listener.127.0.0.1_10110.udp.downstream_rx_datagram_dropped"
PTO_US = 25000.0  # a QUIC probe timeout is at least the peer's maximum ACK delay (25 ms): a stranded datagram shows above it


def pooled(rd, runs):
    legs, notes, sup = [], [], 0
    for i, r in enumerate(runs):
        p = os.path.join(rd, r, "results.json")
        if not os.path.exists(p):
            notes.append("%s: no results.json (not run)" % r)
            continue
        d = json.load(open(p))
        md = d.get("metadata") or {}
        mine = [dict(m, round=m["round"] + 6 * i, run=r) for m in d["legs"] if not m.get("superseded") and m.get("arm")]
        sup += sum(1 for m in d["legs"] if m.get("superseded"))
        legs += mine
        notes.append("%s: %d current legs, %d valid, evidence failing %d, rounds complete %s, stop reason %s, incomplete %s, "
                     "binaries unchanged at the end %s, started %s, finished %s" % (
                         r, len(mine), sum(1 for m in mine if valid(m)),
                         sum(1 for m in mine if (m.get("evidence") or {"ok": True}).get("ok") is False),
                         md.get("rounds_complete"), md.get("stop_reason"), md.get("incomplete"), md.get("arms_md5_unchanged"),
                         md.get("started_utc"), md.get("finished_utc")))
    return legs, notes, sup


def gate(aa):
    ok = aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] and abs(aa["log_pct"]) < FLOOR
    reach = abs(aa["simple_pct"]) + (aa["simple_quoted"][1] - aa["simple_quoted"][0]) / 2.0
    return ok, reach, abs(aa["log_pct"])


def datagrams(m):
    d = ((m.get("kernel_net") or {}).get("d") or {}).get("UdpInDatagrams")
    n = m.get("responses_raw")
    return (d / n) if (d is not None and n) else None


def rng(v, f="%.4f"):
    v = [x for x in v if x is not None]
    return "-" if not v else (f % min(v)) if max(v) - min(v) < 1e-12 else (f + " to " + f) % (min(v), max(v))


def share_row(legs, shape):
    """Per round: (h3-off - h3-both-on) / (h3-official - h2tls), cycles per request: the share of the HTTP/3 premium
    over HTTP/2-over-TLS that the patch removes. Exploratory."""
    by = {}
    for m in legs:
        if m.get("shape") == shape and valid(m):
            by.setdefault(m["round"], {})[m["arm"]] = (m.get("per_req") or {}).get(MET)
    out = {}
    for name, a, b in (("both guards (h3-off minus h3-both-on)", "h3-off", "h3-both-on"), ("stop guard (h3-off minus h3-stop-on)", "h3-off", "h3-stop-on")):
        d = [(x[a] - x[b]) / (x["h3-official"] - x["h2tls"]) * 100.0 for _, x in sorted(by.items())
             if all(x.get(k) for k in (a, b, "h3-official", "h2tls"))]
        if len(d) >= 3:
            mu, se, hw, _ = interval(d)
            out[name] = {"n": len(d), "share_pct": mu, "t_interval": [mu - hw, mu + hw]}
    return out


def slope(legs, shape, arms):
    """Least squares over the legs of the given arms: cycles per request against the busiest worker's share,
    as % of the mean per 0.1 of share. Exploratory; no row is adjusted by it."""
    pts = [((m.get("envoy_worker_max_share") or 0.0), (m.get("per_req") or {}).get(MET)) for m in legs
           if m.get("shape") == shape and m.get("arm") in arms and valid(m)]
    pts = [(x, y) for x, y in pts if x and y]
    if len(pts) < 6:
        return None
    mx, my = stats.mean([p[0] for p in pts]), stats.mean([p[1] for p in pts])
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    if not sxx:
        return None
    b = sum((x - mx) * (y - my) for x, y in pts) / sxx
    return {"legs": len(pts), "pct_per_0.1_share": 100.0 * b * 0.1 / my, "share_min": min(p[0] for p in pts), "share_max": max(p[0] for p in pts)}


def main(argv):
    rd = argv[0].rstrip("/")
    try:
        hi = open(os.path.join(rd, "hi.txt")).read().strip()
    except OSError:
        hi = "none"
    shapes = {"s": ["s-1", "s-2"], "s-hi": [hi] if hi in ("shi", "shi-half") else []}
    out = {"metric": MET, "floor_log_points": FLOOR, "line_simple_pct": LINE, "s_hi_run": hi, "shapes": {}}
    data = {sh: pooled(rd, runs) for sh, runs in shapes.items()}
    conf = []
    for sh in shapes:
        for tag, a, r in CONF[sh]:
            x = row(data[sh][0], sh, a, r, MET)
            if x:
                conf.append((sh, tag, x))
    hp = stats.holm([x["t_p"] for _, _, x in conf]) if conf else []
    holm = {tag: p for (_, tag, _), p in zip(conf, hp)}
    out["holm_family_size"] = len(conf)
    print("# wave 8 W8-2: cycles (user+kernel) of the Envoy process per request; shape s pooled over two Williams squares; s-hi run: %s" % hi)
    print("\nconfirmatory rows in the Holm family: %d (%s)" % (len(conf), ", ".join(t for _, t, _ in conf)))
    for sh, runs in shapes.items():
        legs, notes, sup = data[sh]
        S = out["shapes"][sh] = {"runs": notes, "medians": {}, "rows": [], "superseded": sup}
        print("\n## shape %s (%s)\n" % (sh, " + ".join(runs) or "not run"))
        for n in notes:
            print("- " + n)
        if not legs:
            print("- no legs")
            continue
        rate = sorted({m.get("target_rps") for m in legs})
        print("- target rate %s req/s; legs replaced by the harness (superseded): %d; rounds pooled: %s" % (rate, sup, sorted({m["round"] for m in legs})))
        print("\n| arm | valid legs | cycles u+k /req (median) | user /req | kernel /req | instr user | instr kernel | ctx sw /req | "
              "p50 µs | p99 µs (median of legs) | latency max µs (median / largest leg) | legs with max over 25 ms | Envoy busy (CPUs of 4) | "
              "busiest worker share (median / max) | UDP datagrams /req, box-wide (min to max) | Envoy datagrams dropped (sum) | kernel "
              "UdpInErrors / RcvbufErrors / SndbufErrors (sum) |")
        print("|" + "---|" * 17)
        for a in ARMS:
            mine = [m for m in legs if m["arm"] == a]
            if not mine:
                continue
            g = lambda k: med(legs, sh, a, k)  # noqa: E731
            k = lambda v, s=1e3, f="%.1fk": (f % (v / s)) if v is not None else "-"  # noqa: E731
            lm = sorted((m.get("latency_us") or {}).get("max") or 0 for m in mine)
            dg = [datagrams(m) for m in mine]
            kn = lambda key: sum(((m.get("kernel_net") or {}).get("d") or {}).get(key) or 0 for m in mine)  # noqa: E731
            drop = sum((m.get("sut_stats_leg_end") or {}).get(DROPPED) or 0 for m in mine)
            busy = medf(legs, sh, a, lambda m: m.get("envoy_cpus_run"))
            shr = sorted(m.get("envoy_worker_max_share") or 0 for m in mine)
            S["medians"][a] = dict({x: g(x) for x in [MET] + EXTRA}, envoy_cpus_run=busy, latency_max_us_median=stats.median(lm),
                                   latency_max_us_largest=lm[-1], legs_latency_max_over_25ms=sum(1 for x in lm if x > PTO_US),
                                   datagrams_per_request=[min(x for x in dg if x is not None), max(x for x in dg if x is not None)] if any(dg) else None,
                                   envoy_datagrams_dropped=drop, kernel_udp_in_errors=kn("UdpInErrors"), kernel_udp_rcvbuf_errors=kn("UdpRcvbufErrors"),
                                   kernel_udp_sndbuf_errors=kn("UdpSndbufErrors"), legs=len(mine), valid=sum(1 for m in mine if valid(m)),
                                   instructions_u_range=[min((m.get("per_req") or {}).get("instructions_u") or 0 for m in mine if valid(m)),
                                                         max((m.get("per_req") or {}).get("instructions_u") or 0 for m in mine if valid(m))],
                                   latency_max_us_per_leg=lm)
            print("| %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %s | %.0f / %.0f | %d | %s | %.3f / %.3f | %s | %d | %d / %d / %d |" % (
                a, sum(1 for m in mine if valid(m)), len(mine), k(g(MET)), k(g("cycles_u")), k(g("cycles_k")), k(g("instructions_u")),
                k(g("instructions_k")), k(g("context_switches"), 1, "%.2f"), k(g("p50_us"), 1, "%.0f"), k(g("p99_us"), 1, "%.0f"),
                stats.median(lm), lm[-1], sum(1 for x in lm if x > PTO_US), "%.3f" % busy if busy is not None else "-",
                stats.median(shr), shr[-1], rng(dg), drop, kn("UdpInErrors"), kn("UdpRcvbufErrors"), kn("UdpSndbufErrors")))
        aa = row(legs, sh, AA[0], AA[1], MET)
        ok, reach, exc = False, None, None
        print("\n" + HEAD % ("same-build check, %s" % MET))
        if aa:
            ok, reach, exc = gate(aa)
            aa.update(kind="same-build", gate_pass=ok, reach_simple_pct=reach, excursion_log_points=exc)
            S["rows"].append(aa)
            print(fmt(aa))
            print("\nsame-build check on %s: %s (effect %+.2f log points against the floor %.1f; quoted interval [%+.2f, %+.2f] log "
                  "points %s 0); reach %.2f%% (simple)" % (sh, "PASS" if ok else "MISS", aa["log_pct"], FLOOR, aa["log_quoted"][0],
                                                          aa["log_quoted"][1], "includes" if aa["log_quoted"][0] <= 0 <= aa["log_quoted"][1] else "EXCLUDES", reach))
        S.update(same_build_pass=ok, same_build_reach_simple_pct=reach, same_build_excursion_log_points=exc)
        bc = row(legs, sh, CONTROL[0], CONTROL[1], MET)
        headline_official = False
        print("\n" + HEAD % ("build control (expected zero), %s" % MET))
        if bc:
            headline_official = bc["simple_pct"] >= 1.0 and not (bc["log_quoted"][0] <= 0 <= bc["log_quoted"][1])
            bc.update(kind="build-control", headline_against_official=headline_official)
            S["rows"].append(bc)
            print(fmt(bc))
            bi = row(legs, sh, CONTROL[0], CONTROL[1], "instructions_u")
            print("\nbuild control on %s: h3-off vs h3-official %+.2f%% [%+.2f, %+.2f] simple. Fixed rule (+1.0%% or more with an interval "
                  "that excludes 0): %s. User instructions per request: h3-off %s, h3-official %s (%s)" % (
                      sh, bc["simple_pct"], bc["simple_quoted"][0], bc["simple_quoted"][1],
                      "MET: the headline of this shape's rows is the figure against h3-official" if headline_official else
                      "not met: the in-binary figure is the headline",
                      "%.0f" % med(legs, sh, "h3-off", "instructions_u"), "%.0f" % med(legs, sh, "h3-official", "instructions_u"),
                      "%+.2f%% [%+.2f, %+.2f]" % (bi["simple_pct"], bi["simple_quoted"][0], bi["simple_quoted"][1]) if bi else "-"))
        S["headline_against_official"] = headline_official
        if sh == "s":
            an = row(legs, sh, ANCHOR[0], ANCHOR[1], MET)
            if an:
                inside = BAND[0] <= an["simple_pct"] <= BAND[1]
                an.update(kind="anchor", inside_band=inside)
                S["rows"].append(an)
                S["anchor"] = {"simple_pct": an["simple_pct"], "quoted": an["simple_quoted"], "inside": inside}
                print("\nANCHOR GATE (h3-official vs h2tls on s, simple %%): %+.1f%% [%+.1f, %+.1f]: %s the band [+65, +85] (published +74.8; "
                      "S2 +77.6)" % (an["simple_pct"], an["simple_quoted"][0], an["simple_quoted"][1], "INSIDE" if inside else "OUTSIDE"))
        print("\n" + HEAD % ("confirmatory, %s" % MET))
        for tag, a, r in CONF[sh]:
            x = row(legs, sh, a, r, MET)
            if not x:
                print("| %s: %s vs %s | no row (legs missing) |" % (tag, a, r))
                continue
            h = holm.get(tag)
            three = exc is not None and abs(x["log_pct"]) >= 3.0 * exc
            decided = ok or three
            basis = "Measured" if ok else ("Measured (same-build check missed its floor; the effect is at least 3 x its excursion)"
                                           if three else "Not resolved (same-build check missed its floor; the effect is under 3 x its excursion)")
            x.update(tag=tag, holm_p=h, kind="confirmatory", basis=basis, decided=decided,
                     finding=bool(decided and not (x["log_quoted"][0] <= 0 <= x["log_quoted"][1]) and h is not None and h < 0.05))
            S["rows"].append(x)
            print(fmt(dict(x, arm="%s: %s" % (tag, a)), h) + (" finding" if x["finding"] else " not a finding") + "; basis: %s" % basis)
            ag = row(legs, sh, a, "h3-official", MET)
            if ag:
                ag.update(kind="other", basis="Exploratory", beside=tag)
                S["rows"].append(ag)
                print("  beside %s, against the stock release [Exploratory]: %s vs h3-official %+.2f%% [%+.2f, %+.2f] simple (%d rounds)" % (
                    tag, a, ag["simple_pct"], ag["simple_quoted"][0], ag["simple_quoted"][1], ag["n"]))
            iu = row(legs, sh, a, r, "instructions_u")
            if iu:
                print("  user instructions per request [Exploratory]: %+.2f%% [%+.2f, %+.2f] simple; paired difference %+.1fk ± %.1fk" % (
                    iu["simple_pct"], iu["simple_quoted"][0], iu["simple_quoted"][1], iu["diff_per_req"] / 1e3, iu["diff_per_req_t_hw"] / 1e3))
        find = lambda tag: next((x for x in S["rows"] if x.get("tag") == tag), None)  # noqa: E731
        if sh == "s":
            c1, c2 = find("C1"), find("C2")
            for tag, x in (("C1", c1), ("C2", c2)):
                if not x:
                    continue
                eff, lo, hi_ = x["simple_pct"], x["simple_quoted"][0], x["simple_quoted"][1]
                at = lo < LINE < hi_
                verdict = ("Not resolved" if not x["decided"] else ("saves 3.0% or more" if eff <= LINE else "saves under 3.0%")) + (
                    " (AT THE LINE: the quoted interval straddles -3.0)" if at else "")
                S.setdefault("lines", {})[tag] = {"effect_simple_pct": eff, "quoted": [lo, hi_], "decided": x["decided"],
                                                  "saves_3_or_more": bool(eff <= LINE) if x["decided"] else None, "at_the_line": at}
                print("\nLINE %s (%s vs %s on s, simple %%): %+.2f%% [%+.2f, %+.2f]: %s. Basis: %s" % (tag, x["arm"], x["ref"], eff, lo, hi_, verdict, x["basis"]))
            if c1:
                d = S["lines"]["C1"]
                word = ("Not resolved" if not d["decided"] else "WORTH PROPOSING (C1 saves 3.0% or more)" if d["saves_3_or_more"]
                        else "KILLED by the line (C1 saves under 3.0%)")
                if c2 and S["lines"]["C2"]["decided"] and S["lines"]["C2"]["saves_3_or_more"]:
                    word += "; C2 alone saves 3.0% or more: commit 1 can be proposed alone, commit 2 is a further step"
                S["verdict"] = word
                print("\nVERDICT on s by the fixed lines: %s" % word)
        else:
            c3 = find("C3")
            if c3:
                harm = c3["simple_pct"] >= HARM and not (c3["log_quoted"][0] <= 0 <= c3["log_quoted"][1])
                S["harm_stop"] = harm
                print("\nHARM STOP (C3: a cost of +1.0%% or more with an interval that excludes 0): %s (C3 %+.2f%% [%+.2f, %+.2f] simple). "
                      "C3 has no kill line. h2tls has no line on s-hi: it is in the run only because six arms balance the square." % (
                          "MET" if harm else "not met", c3["simple_pct"], c3["simple_quoted"][0], c3["simple_quoted"][1]))
        # the marker in the scored legs themselves: user instructions per request, per-leg ranges
        iu = {a: S["medians"][a]["instructions_u_range"] for a in ("h3-off", "h3-stop-on", "h3-both-on") if a in S["medians"]}
        if len(iu) == 3:
            sep1, sep2 = iu["h3-stop-on"][1] < iu["h3-off"][0], iu["h3-both-on"][1] < iu["h3-stop-on"][0]
            S["marker"] = {"ranges": iu, "stop_on_below_off": sep1, "both_on_below_stop_on": sep2}
            print("\nMARKER in the scored legs (user instructions per request, lowest to highest leg): h3-off %.0f to %.0f; h3-stop-on %.0f to "
                  "%.0f; h3-both-on %.0f to %.0f. Ranges apart: stop-on below off %s; both-on below stop-on %s" % (
                      iu["h3-off"][0], iu["h3-off"][1], iu["h3-stop-on"][0], iu["h3-stop-on"][1], iu["h3-both-on"][0], iu["h3-both-on"][1],
                      "YES" if sep1 else "NO", "YES" if sep2 else "NO"))
        print("\n" + HEAD % ("exploratory, %s" % MET))
        for a, r in OTHER:
            x = row(legs, sh, a, r, MET)
            if x and not (sh == "s" and (a, r) == ANCHOR):
                x.update(kind="other", basis="Exploratory")
                S["rows"].append(x)
                print(fmt(x))
        shr = share_row(legs, sh)
        S["premium_share"] = shr
        for name, v in shr.items():
            print("\nshare of the HTTP/3 premium over h2tls removed [Exploratory], %s over (h3-official minus h2tls), cycles per request, per "
                  "round: %.1f%% [%.1f, %.1f] (t interval, %d rounds)" % (name, v["share_pct"], v["t_interval"][0], v["t_interval"][1], v["n"]))
        sl = slope(legs, sh, H3)
        S["worker_share_slope"] = sl
        if sl:
            print("\ncycles per request against the busiest worker's share [Exploratory; no row is adjusted]: %+.2f%% per 0.1 of share over %d "
                  "legs of the five HTTP/3 arms (share %.3f to %.3f)" % (sl["pct_per_0.1_share"], sl["legs"], sl["share_min"], sl["share_max"]))
        print("\n" + HEAD % "parts, exploratory")
        for a, r in [(a, r) for _, a, r in CONF[sh]] + [CONTROL, AA]:
            for mm in EXTRA:
                x = row(legs, sh, a, r, mm)
                if x:
                    x["kind"] = "part"
                    S["rows"].append(x)
                    print(fmt(dict(x, arm="%s [%s]" % (a, mm))))
        if len(runs) > 1:
            print("\n" + HEAD % "per run (one Williams square each), exploratory")
            for r_ in runs:
                sub = [m for m in legs if m.get("run") == r_]
                for a, rf in [(a, r) for _, a, r in CONF[sh]] + [CONTROL, AA, ANCHOR]:
                    x = row(sub, sh, a, rf, MET) if sub else None
                    if x:
                        x.update(kind="per-run", run=r_)
                        S["rows"].append(x)
                        print(fmt(dict(x, arm="%s: %s" % (r_, a))))
        print("\nper-round log points (arm vs ref), for the reviewer:")
        for x in S["rows"]:
            if x.get("kind") in ("confirmatory", "same-build", "build-control", "anchor"):
                print("- %s vs %s: %s" % (x["arm"], x["ref"], " ".join("%+.2f" % v for v in x["per_round_log_pct"])))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
