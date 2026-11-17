#!/usr/bin/env python3
"""Tables of the feature rows, session 1 (features.py).

    python3 examples/settings-matrix/features_table.py SESSION_DIR [--old DATA_DIR] [--json OUT.json] > tables.md

SESSION_DIR holds the run directories run-s, 18-access-log, 17-tracing, 13-ext-authz and,
if it ran, 18w-access-log-w16. DATA_DIR (default: the repo's data/) holds the published
first sessions, for the replication rule.

Every comparison is recomputed here from the legs: valid, current legs of complete
rotation blocks only, paired per round, 100*ln(arm/ref), mean with a 95% t interval, and
the same interval widened by the between-session A/A spread, 1.96*sqrt(SE^2 + 0.34^2)
(never narrower than the run's own). The per-run Holm values in results.json are not
used. Families, named before the session:

- confirmatory (16 rows, CONFIRMATORY): one Holm step across all runs of the session;
  a row whose run did not produce it counts as p = 1, so the family size stays 16;
- secondary (7 rows, SECONDARY): its own Holm step;
- row 18w (2 rows, W16), if it ran: its own Holm step;
- everything else is exploratory, interval only.

Verdicts (as the week-4 tables): under 1% = within the A/A spread, not a finding; Holm p
above 0.05 = not resolved; "differs" only when the widened interval excludes zero; a
smaller interval that excludes zero reads "about N%, not resolved". A row below the
reach of its shape's A/A, where that A/A failed its 1% limit, is not a finding. A row of
an incomplete run gets no verdict. Closing an R17/R18 item: "no measurable cost" only
when the widened upper end is under 1.5%; otherwise "not resolved; at most N%".

Replication (rows that repeat a published one): z = (new - old) / sqrt(SE_new^2 +
SE_old^2 + 2*0.34^2). "Replicated" needs |z| <= 2, the same sign and a new verdict that
is neither "within the A/A spread" nor "not resolved"; otherwise the row reads "second
session: X (first: Y)" and is held for review. Nothing is pooled.
"""

import argparse
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")
sys.path.insert(0, REPO)
from epl import experiment, stats  # noqa: E402

_spec = importlib.util.spec_from_file_location("rel_table", os.path.join(HERE, "..", "releases", "table.py"))
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

TAU = T.TAU
AA_LIMIT_PCT = 1.0
NO_COST_BELOW_PCT = 1.5
METRIC = "cycles_total"

# (run, shape, arm, ref, label)
CONFIRMATORY = [
    ("13-ext-authz", "s", "authz-http", "authz-off", "ext_authz HTTP"),
    ("13-ext-authz", "s", "authz-grpc", "authz-off", "ext_authz gRPC"),
    ("13-ext-authz", "fh6", "authz-http", "authz-off", "ext_authz HTTP"),
    ("13-ext-authz", "fh6", "authz-grpc", "authz-off", "ext_authz gRPC"),
    ("17-tracing", "s", "trace-1", "trace-off", "tracing 1%"),
    ("17-tracing", "s", "trace-100", "trace-off", "tracing 100%"),
    ("17-tracing", "fh", "trace-1", "trace-off", "tracing 1%"),
    ("17-tracing", "fh", "trace-100", "trace-off", "tracing 100%"),
    ("18-access-log", "s", "log-text", "log-off", "access log, text"),
    ("18-access-log", "s", "log-json", "log-off", "access log, JSON"),
    ("18-access-log", "fh", "log-text", "log-off", "access log, text"),
    ("18-access-log", "fh", "log-json", "log-off", "access log, JSON"),
    ("run-s", "s", "retry-on", "base", "retry policy, never triggered"),
    ("run-s", "s", "idle-off", "base", "idle timers off"),
    ("run-s", "s", "percpu-on", "base", "tcmalloc per-CPU caches"),
    ("run-s", "fh", "percpu-on", "base", "tcmalloc per-CPU caches"),
]
SECONDARY = [
    ("17-tracing", "s", "trace-10", "trace-off", "tracing 10%"),
    ("17-tracing", "fh", "trace-10", "trace-off", "tracing 10%"),
    ("run-s", "fh", "idle-off", "base", "idle timers off"),
    ("run-s", "s", "base-A2", "base", "A/A"),
    ("run-s", "fh", "base-A2", "base", "A/A"),
    ("13-ext-authz", "s", "authz-off-A2", "authz-off", "A/A"),
    ("13-ext-authz", "fh6", "authz-off-A2", "authz-off", "A/A"),
]
W16 = [
    ("18w-access-log-w16", "s-w16", "log-text", "log-off", "access log, text, 16 workers"),
    ("18w-access-log-w16", "s-w16", "log-json", "log-off", "access log, JSON, 16 workers"),
]
# The A/A of each shape: (run, shape, arm, ref). Rows 17 and 18 use run S's floor.
AA_ROWS = {
    ("run-s", "s"): ("run-s", "s", "base-A2", "base"),
    ("run-s", "fh"): ("run-s", "fh", "base-A2", "base"),
    ("17-tracing", "s"): ("run-s", "s", "base-A2", "base"),
    ("17-tracing", "fh"): ("run-s", "fh", "base-A2", "base"),
    ("18-access-log", "s"): ("run-s", "s", "base-A2", "base"),
    ("18-access-log", "fh"): ("run-s", "fh", "base-A2", "base"),
    ("13-ext-authz", "s"): ("13-ext-authz", "s", "authz-off-A2", "authz-off"),
    ("13-ext-authz", "fh6"): ("13-ext-authz", "fh6", "authz-off-A2", "authz-off"),
    ("18w-access-log-w16", "s-w16"): ("18w-access-log-w16", "s-w16", "log-off-A2", "log-off"),
}
# Rows that repeat a published one: new (run, shape, arm, ref) -> old (data dir, shape, arm, ref, name)
OLD = {
    ("13-ext-authz", "s", "authz-http", "authz-off"): [
        ("settings-matrix/06-ext-authz", "s", "authz-http", "authz-off", "row 6"),
        ("settings-followups/f2-ext-authz", "s", "authz-http", "authz-off", "F2")],
    ("13-ext-authz", "s", "authz-grpc", "authz-off"): [
        ("settings-followups/f2-ext-authz", "s", "authz-grpc", "authz-off", "F2")],
    ("17-tracing", "s", "trace-1", "trace-off"): [
        ("settings-matrix/04-tracing", "s", "sampling-1", "no-tracer", "row 4")],
    ("17-tracing", "s", "trace-100", "trace-off"): [
        ("settings-matrix/04-tracing", "s", "sampling-100", "no-tracer", "row 4")],
    ("18-access-log", "s", "log-text", "log-off"): [
        ("settings-matrix/05-access-log", "s", "log-text", "log-off", "row 5")],
    ("18-access-log", "s", "log-json", "log-off"): [
        ("settings-matrix/05-access-log", "s", "log-json", "log-off", "row 5")],
    ("run-s", "s", "retry-on", "base"): [
        ("settings-matrix/07-retries", "s", "retry-policy", "no-retry-policy", "row 7")],
    ("run-s", "s", "percpu-on", "base"): [
        ("settings-matrix/09-tcmalloc-percpu", "s", "rseq-off", "tcmalloc-default", "row 9")],
    ("run-s", "fh", "percpu-on", "base"): [
        ("settings-matrix/09-tcmalloc-percpu", "fh", "rseq-off", "tcmalloc-default", "row 9")],
}
# R17 / R18 items and the rows that close them
CLOSES = {
    ("17-tracing", "s", "trace-1", "trace-off"): "R17 OTel 1%",
    ("17-tracing", "fh", "trace-1", "trace-off"): "R17 OTel 1%",
    ("18-access-log", "s", "log-text", "log-off"): "R17 access log text",
    ("18-access-log", "fh", "log-text", "log-off"): "R17 access log text",
    ("18-access-log", "s", "log-json", "log-off"): "R17 access log JSON",
    ("18-access-log", "fh", "log-json", "log-off"): "R17 access log JSON",
    ("18w-access-log-w16", "s-w16", "log-text", "log-off"): "R17 access log at W16",
    ("18w-access-log-w16", "s-w16", "log-json", "log-off"): "R17 access log at W16",
    ("run-s", "s", "retry-on", "base"): "R17 retries",
    ("run-s", "s", "idle-off", "base"): "R17 idle timeout",
    ("run-s", "fh", "idle-off", "base"): "R17 idle timeout",
    ("run-s", "s", "percpu-on", "base"): "R18",
    ("run-s", "fh", "percpu-on", "base"): "R18",
}
EXPLORATORY = [
    ("13-ext-authz", "s", "authz-grpc", "authz-http", "gRPC against HTTP"),
    ("13-ext-authz", "fh6", "authz-grpc", "authz-http", "gRPC against HTTP"),
    ("18-access-log", "s", "log-json", "log-text", "JSON against text"),
    ("18-access-log", "fh", "log-json", "log-text", "JSON against text"),
    ("run-s", "fh", "retry-on", "base", "retry policy on the direct response (near A/A: the policy sits on /s)"),
]
SPLIT_METRICS = ("cycles_u", "cycles_k", "instructions_u")


def getter(key):
    return dict((k, g) for k, _, g in experiment.METRICS)[key]


def load_run(d):
    p = os.path.join(d, "results.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def usable_legs(res):
    """{(shape, arm, round): leg} over complete rotation blocks only."""
    md = res.get("metadata", {})
    rc = md.get("rounds_complete")
    if rc is None:
        rc = experiment.complete_rounds(res["experiment"], res["legs"])
    return {k: m for k, m in experiment.current_legs(res["legs"]).items() if k[2] <= rc}


def paired(by, shape, arm, ref, key=METRIC):
    g = getter(key)
    rv, av = [], []
    for (s, a, r) in sorted(by):
        if s != shape or a != arm or (shape, ref, r) not in by:
            continue
        try:
            x, y = g(by[(s, a, r)]), g(by[(shape, ref, r)])
        except (KeyError, TypeError):
            continue
        if x is None or y is None:
            continue
        av.append(x)
        rv.append(y)
    p = stats.paired_log_ratio(rv, av)
    p["arm_median"] = stats.median(av) if av else None
    p["ref_median"] = stats.median(rv) if rv else None
    p["abs_diff_mean"] = stats.mean([a - b for a, b in zip(av, rv)]) if av else None
    return p


def se(p):
    return T.se_of(p)


def row(runs, spec, family=None):
    run, shape, arm, ref, label = spec
    out = {"run": run, "shape": shape, "arm": arm, "ref": ref, "label": label, "family": family}
    res = runs.get(run)
    if res is None:
        out["missing"] = "run not found"
        return out
    out["incomplete"] = bool(res.get("metadata", {}).get("incomplete"))
    by = usable_legs(res)
    p = paired(by, shape, arm, ref)
    out["n"] = p["n"]
    if p.get("half_width_pct") is None:
        out["missing"] = "fewer than 2 pairs"
        return out
    w = T.widened(p)
    out.update(log_mean=p["log_mean_pct"], lo=p["log_lo_pct"], hi=p["log_hi_pct"], hw=p["half_width_pct"],
               t_p=p["t_p"], se=se(p), widened=w, effect_pct=T.pct(p["log_mean_pct"]),
               lo_pct=T.pct(p["log_lo_pct"]), hi_pct=T.pct(p["log_hi_pct"]),
               widened_lo_pct=T.pct(p["log_mean_pct"] - w), widened_hi_pct=T.pct(p["log_mean_pct"] + w),
               arm_median=p["arm_median"], ref_median=p["ref_median"], abs_diff_mean=p["abs_diff_mean"])
    for k in SPLIT_METRICS:
        q = paired(by, shape, arm, ref, k)
        if q.get("half_width_pct") is not None:
            out[k] = {"effect_pct": T.pct(q["log_mean_pct"]), "lo_pct": T.pct(q["log_lo_pct"]),
                      "hi_pct": T.pct(q["log_hi_pct"]), "arm_median": q["arm_median"],
                      "ref_median": q["ref_median"], "abs_diff_mean": q["abs_diff_mean"]}
    an = (res.get("analysis") or {}).get("shapes", {}).get(shape, {}).get("arms", {})
    out["busy"] = {a: (an.get(a) or {}).get("sut_busy_mean") for a in (arm, ref)}
    return out


def holm(rows):
    """Holm over a named family; a row without a p-value counts as p = 1."""
    ps = [r.get("t_p", 1.0) if r.get("t_p") is not None else 1.0 for r in rows]
    for r, a in zip(rows, stats.holm(ps)):
        r["holm_p"] = a
    return len(rows)


def aa_status(runs, secondary):
    """{(run, shape): {reach, hw, holm_p, ok}} from the A/A rows. The Holm p of an A/A row
    is the one of the secondary family; the 18w A/A, outside that family, uses its own p."""
    out = {}
    sec = {(r["run"], r["shape"], r["arm"], r["ref"]): r for r in secondary}
    for key, spec in AA_ROWS.items():
        r = sec.get(spec) or row(runs, spec + ("A/A",))
        if r.get("missing"):
            out[key] = {"ok": None, "why": r["missing"]}
            continue
        hp = r.get("holm_p", r.get("t_p"))
        reach = max(abs(r["lo"]), abs(r["hi"]))
        out[key] = {"ok": r["hw"] <= AA_LIMIT_PCT and hp > 0.05, "reach": reach, "hw": r["hw"], "holm_p": hp,
                    "spec": spec}
    return out


def verdict(r, aa=None):
    if r.get("missing"):
        return "no data (%s)" % r["missing"]
    if r.get("incomplete"):
        return experiment.INCOMPLETE
    p = {"log_mean_pct": r["log_mean"], "log_lo_pct": r["lo"], "log_hi_pct": r["hi"]}
    v = T.verdict(p, r["widened"], r.get("holm_p"))
    if v == "differs" and abs(r["effect_pct"]) < 2.0:
        v = "differs: about %+.1f%%, near the floor" % r["effect_pct"]
    if aa and aa.get("ok") is False and abs(r["log_mean"]) < aa["reach"]:
        v += "; below the A/A reach %.2f%%, not a finding" % aa["reach"]
    return v


def is_finding(v):
    """Only a "differs" verdict is a finding; under 1%, not resolved, below the A/A reach and
    incomplete rows are not."""
    return v.startswith("differs") and "not a finding" not in v


def closing(r):
    """How an R17/R18 item closes on this row (review S8)."""
    if r.get("missing") or r.get("incomplete"):
        return "open (no verdict)"
    if is_finding(r["verdict"]):
        return "costs about %+.1f%%" % r["effect_pct"]
    if r["widened_hi_pct"] < NO_COST_BELOW_PCT:
        return "no measurable cost (widened upper end %+.2f%%)" % r["widened_hi_pct"]
    return "not resolved; at most %+.1f%%" % r["widened_hi_pct"]


def old_row(data_dir, spec):
    d, shape, arm, ref, name = spec
    res = load_run(os.path.join(data_dir, d))
    if res is None:
        return {"name": name, "missing": "no results.json in %s" % d}
    p = paired(experiment.current_legs(res["legs"]), shape, arm, ref)
    if p.get("half_width_pct") is None:
        return {"name": name, "missing": "no pairs"}
    return {"name": name, "log_mean": p["log_mean_pct"], "se": se(p), "effect_pct": T.pct(p["log_mean_pct"]),
            "lo_pct": T.pct(p["log_lo_pct"]), "hi_pct": T.pct(p["log_hi_pct"]), "n": p["n"]}


def replication(new, old):
    """The review-S7 rule: |z| <= 2, the same sign, and an own verdict that is a finding."""
    if new.get("missing") or new.get("incomplete") or old.get("missing"):
        return {"z": None, "replicated": False, "wording": "no comparison (%s)" % (
            new.get("missing") or old.get("missing") or "incomplete")}
    z = (new["log_mean"] - old["log_mean"]) / math.sqrt(new["se"] ** 2 + old["se"] ** 2 + 2 * TAU ** 2)
    same_sign = (new["log_mean"] > 0) == (old["log_mean"] > 0)
    finding = is_finding(new["verdict"])
    rep = abs(z) <= 2 and same_sign and finding
    if rep:
        wording = "second session: %+.2f%% (first, %s: %+.2f%%)" % (new["effect_pct"], old["name"], old["effect_pct"])
    else:
        wording = "second session: %+.2f%% (first, %s: %+.2f%%); held for review" % (
            new["effect_pct"], old["name"], old["effect_pct"])
    return {"z": z, "same_sign": same_sign, "own_verdict_is_finding": finding, "replicated": rep,
            "wording": wording}


def fmt_row(r):
    if r.get("missing"):
        return "| %s | %s | %s | - | - | - | - | %s |" % (r["label"], r["shape"], r["arm"], verdict(r))
    return "| %s | %s | %s vs %s | %+.2f%% [%+.2f, %+.2f] | [%+.2f, %+.2f] | %.3g | %d | %s |" % (
        r["label"], r["shape"], r["arm"], r["ref"], r["effect_pct"], r["lo_pct"], r["hi_pct"],
        r["widened_lo_pct"], r["widened_hi_pct"], r.get("holm_p", float("nan")), r["n"], r["verdict"])


HDR = ("| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Holm p | Pairs | Verdict |\n"
       "|---|---|---|---|---|---|---|---|")


def busy(x):
    return "-" if x is None else "%.1f%%" % (100 * x)


def evidence_summary(res):
    out = {}
    for m in experiment.current_legs(res["legs"]).values():
        ev = m.get("evidence")
        k = "%s/%s" % (m["shape"], m["arm"])
        e = out.setdefault(k, {"legs": 0, "evidence_ok": 0, "side_cpu_us_per_req": []})
        e["legs"] += 1
        e["evidence_ok"] += 1 if (ev is None or ev.get("ok")) else 0
        for name, sv in (m.get("side_services") or {}).items():
            if sv.get("cpu_us_per_request") is not None:
                e["side_cpu_us_per_req"].append((name, sv["cpu_us_per_request"]))
    for e in out.values():
        per = {}
        for name, v in e.pop("side_cpu_us_per_req"):
            per.setdefault(name, []).append(v)
        e["side_cpu_us_per_request_mean"] = {n: round(sum(v) / len(v), 2) for n, v in per.items()}
    return out


def tables(runs, data_dir):
    L, js = [], {"runs": {}, "families": {}}
    L.append("# Feature rows, session 1\n")
    L.append("## Runs\n")
    for name in ("run-s", "18-access-log", "17-tracing", "13-ext-authz", "18w-access-log-w16"):
        res = runs.get(name)
        if res is None:
            L.append("- %s: not run" % name)
            continue
        md = res.get("metadata", {})
        legs = res["legs"]
        inv = sum(1 for m in legs if not m.get("verdict", {}).get("valid"))
        js["runs"][name] = {"rounds_complete": md.get("rounds_complete"), "incomplete": md.get("incomplete"),
                            "legs": len(legs), "invalid": inv, "stop": md.get("stop_reason"),
                            "aborted": md.get("aborted")}
        L.append("- %s: %d legs, %d invalid; %s complete rounds%s; stop: %s%s" % (
            name, len(legs), inv, md.get("rounds_complete"),
            " (**incomplete, no verdict**)" if md.get("incomplete") else "", md.get("stop_reason"),
            "; aborted: %s" % md["aborted"] if md.get("aborted") else ""))
    L.append("")

    secondary = [row(runs, s, "secondary") for s in SECONDARY]
    holm(secondary)
    aa = aa_status(runs, secondary)
    L.append("## A/A of the session\n")
    L.append("Pass: half-width at most %.1f%% and no Holm-significant difference (secondary family). Rows 17 and 18 "
             "take run S's A/A (same session, an earlier run: a same-session floor, not a same-run one).\n" % AA_LIMIT_PCT)
    L.append("| Run / shape | A/A row | Half-width | Reach (far end) | Holm p | Pass |\n|---|---|---|---|---|---|")
    for key, st in sorted(aa.items()):
        if "reach" not in st:
            L.append("| %s / %s | - | - | - | - | %s |" % (key[0], key[1], st.get("why")))
            continue
        L.append("| %s / %s | %s vs %s (%s) | %.2f | %.2f | %s | %s |" % (
            key[0], key[1], st["spec"][2], st["spec"][3], st["spec"][0], st["hw"], st["reach"],
            "%.3g" % st["holm_p"] if st.get("holm_p") is not None else "-", "yes" if st["ok"] else "no"))
    L.append("")
    js["aa"] = {"%s/%s" % k: v for k, v in aa.items()}

    def family(title, name, specs):
        rows = [row(runs, s, name) for s in specs]
        k = holm(rows)
        have = sum(1 for r in rows if r.get("t_p") is not None)
        for r in rows:
            r["verdict"] = verdict(r, aa.get((r["run"], r["shape"])))
            key = (r["run"], r["shape"], r["arm"], r["ref"])
            if key in CLOSES:
                r["closes"] = CLOSES[key]
                r["closing"] = closing(r)
        L.append("## %s (Holm over %d rows, %d with data)\n" % (title, k, have))
        L.append(HDR)
        for r in rows:
            L.append(fmt_row(r))
        L.append("")
        js["families"][name] = {"size": k, "with_data": have, "rows": rows}
        return rows

    conf = family("Confirmatory rows", "confirmatory", CONFIRMATORY)
    for r in secondary:
        r["verdict"] = verdict(r, aa.get((r["run"], r["shape"])))
        key = (r["run"], r["shape"], r["arm"], r["ref"])
        if key in CLOSES:
            r["closes"], r["closing"] = CLOSES[key], closing(r)
    L.append("## Secondary rows (Holm over %d rows, %d with data)\n" % (
        len(secondary), sum(1 for r in secondary if r.get("t_p") is not None)))
    L.append(HDR)
    for r in secondary:
        L.append(fmt_row(r))
    L.append("")
    js["families"]["secondary"] = {"size": len(secondary), "rows": secondary}
    w16 = family("Row 18w, 16 workers", "w16", W16) if "18w-access-log-w16" in runs else []

    L.append("## R17 and R18\n")
    L.append("\"No measurable cost\" only when the widened upper end is under %.1f%% (review S8).\n" % NO_COST_BELOW_PCT)
    L.append("| Item | Row | Shape | Verdict | Closes as |\n|---|---|---|---|---|")
    for r in conf + secondary + w16:
        if r.get("closes"):
            L.append("| %s | %s | %s | %s | %s |" % (r["closes"], r["label"], r["shape"], r["verdict"], r["closing"]))
    L.append("")

    L.append("## Replication against the published first sessions\n")
    L.append("| Row | Shape | First session | z | Same sign | Own verdict a finding | Wording |\n"
             "|---|---|---|---|---|---|---|")
    js["replication"] = []
    for r in conf:
        key = (r["run"], r["shape"], r["arm"], r["ref"])
        for spec in OLD.get(key, []):
            o = old_row(data_dir, spec)
            rp = replication(r, o)
            js["replication"].append(dict(rp, row=key, old=o))
            L.append("| %s | %s | %s %s | %s | %s | %s | %s |" % (
                r["label"], r["shape"], o["name"],
                "%+.2f%% [%+.2f, %+.2f]" % (o["effect_pct"], o["lo_pct"], o["hi_pct"]) if "effect_pct" in o else "-",
                "%.2f" % rp["z"] if rp["z"] is not None else "-", rp.get("same_sign", "-"),
                rp.get("own_verdict_is_finding", "-"), rp["wording"]))
    L.append("")

    L.append("## Absolute cost, user and kernel split, load (exploratory)\n")
    L.append("Kernel cycles are measured on loopback: they include part of the peer's receive work. Cycles per "
             "request are medians over the paired legs; the difference is the mean paired difference.\n")
    L.append("| Row | Shape | Ref -> arm total (k) | Added (k) | cycles:u effect | cycles:k effect | "
             "instructions:u effect | Busy ref -> arm |\n|---|---|---|---|---|---|---|---|")
    for r in conf + secondary + w16:
        if r.get("missing"):
            continue
        e = lambda k: ("%+.2f%%" % r[k]["effect_pct"]) if k in r else "-"  # noqa: E731
        L.append("| %s | %s | %.1f -> %.1f | %+.2f | %s | %s | %s | %s -> %s |" % (
            r["label"], r["shape"], r["ref_median"] / 1e3, r["arm_median"] / 1e3, r["abs_diff_mean"] / 1e3,
            e("cycles_u"), e("cycles_k"), e("instructions_u"), busy(r["busy"].get(r["ref"])),
            busy(r["busy"].get(r["arm"]))))
    L.append("")

    L.append("## Exploratory rows (interval only)\n")
    L.append("| Row | Shape | Arm vs ref | Total cycles [95% CI] | Widened | Pairs |\n|---|---|---|---|---|---|")
    expl = []
    for spec in EXPLORATORY:
        r = row(runs, spec, "exploratory")
        expl.append(r)
        if r.get("missing"):
            L.append("| %s | %s | %s vs %s | - | - | - |" % (r["label"], r["shape"], r["arm"], r["ref"]))
            continue
        L.append("| %s | %s | %s vs %s | %+.2f%% [%+.2f, %+.2f] | [%+.2f, %+.2f] | %d |" % (
            r["label"], r["shape"], r["arm"], r["ref"], r["effect_pct"], r["lo_pct"], r["hi_pct"],
            r["widened_lo_pct"], r["widened_hi_pct"], r["n"]))
    L.append("")
    # tracing: is 10% on the line through 1% and 100%?
    byk = {(r["run"], r["shape"], r["arm"]): r for r in conf + secondary}
    lin = []
    for s in ("s", "fh"):
        a, b, c = (byk.get(("17-tracing", s, x)) for x in ("trace-1", "trace-10", "trace-100"))
        if a and b and c and not any(x.get("missing") for x in (a, b, c)):
            pred = a["effect_pct"] + (c["effect_pct"] - a["effect_pct"]) * 9.0 / 99.0
            lin.append({"shape": s, "predicted_pct": pred, "measured_pct": b["effect_pct"],
                        "measured_lo_pct": b["lo_pct"], "measured_hi_pct": b["hi_pct"]})
            L.append("- tracing 10%% on %s: line through 1%% and 100%% predicts %+.2f%%, measured %+.2f%% "
                     "[%+.2f, %+.2f]" % (s, pred, b["effect_pct"], b["lo_pct"], b["hi_pct"]))
    # authorization: one absolute price on s and fh6? (approximate: different load gaps)
    for arm in ("authz-http", "authz-grpc"):
        a, b = byk.get(("13-ext-authz", "s", arm)), byk.get(("13-ext-authz", "fh6", arm))
        if a and b and not a.get("missing") and not b.get("missing"):
            L.append("- %s added cycles per request: s %+.1fk, fh6 %+.1fk (approximate: the two shapes have "
                     "different load gaps)" % (arm, a["abs_diff_mean"] / 1e3, b["abs_diff_mean"] / 1e3))
    # 18w against 18: absolute cycles added per request, unpaired across runs
    for arm in ("log-text", "log-json"):
        a = next((r for r in conf if (r["run"], r["shape"], r["arm"]) == ("18-access-log", "s", arm)), None)
        b = next((r for r in w16 if r["arm"] == arm), None)
        if a and b and not a.get("missing") and not b.get("missing"):
            L.append("- %s, added cycles per request: 4 workers %+.1fk, 16 workers %+.1fk; difference %+.1fk "
                     "(exploratory, unpaired across runs)" % (arm, a["abs_diff_mean"] / 1e3, b["abs_diff_mean"] / 1e3,
                                                              (b["abs_diff_mean"] - a["abs_diff_mean"]) / 1e3))
    L.append("")
    js["exploratory"] = expl
    js["tracing_linearity"] = lin

    L.append("## Evidence and side services (current legs)\n")
    js["evidence"] = {}
    for name, res in runs.items():
        ev = evidence_summary(res)
        js["evidence"][name] = ev
        for k, v in sorted(ev.items()):
            L.append("- %s %s: evidence ok on %d of %d legs; side-service CPU per request (us) %s" % (
                name, k, v["evidence_ok"], v["legs"], v["side_cpu_us_per_request_mean"] or "-"))
    L.append("")
    return "\n".join(L) + "\n", js


def load_session(d):
    runs = {}
    for name in sorted(os.listdir(d)):
        res = load_run(os.path.join(d, name))
        if res is not None:
            runs[name] = res
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--old", default=os.path.join(REPO, "data"))
    ap.add_argument("--json")
    a = ap.parse_args()
    text, js = tables(load_session(a.session), a.old)
    sys.stdout.write(text)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(js, f, indent=1, default=str)


if __name__ == "__main__":
    main()
