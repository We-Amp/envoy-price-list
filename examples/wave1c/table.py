#!/usr/bin/env python3
"""Tables of track C, from the run directories (offline, no box).

    python3 examples/wave1c/table.py extproc RUN_DIR
    python3 examples/wave1c/table.py xds RUN_DIR [RUN_DIR ...]
    python3 examples/wave1c/table.py pairs RUN_DIR       (ext_proc arms against each other)
    python3 examples/wave1c/table.py validity|threads RUN_DIR ...

extproc   per arm against `off`: the harness's own paired effect on total cycles per request
          (results.json, the widened interval 1.96 sqrt(SE^2 + 0.34^2) next to it), the added
          cycles per request (= per side call), user/kernel split, the cycles of threads other
          than main and workers (the gRPC C++ client's own threads), worker busy, and the side
          service's own CPU per request (exploratory; never added to Envoy's).
xds       per update arm against its size's `ref`, per shape, paired by round: cycles per update
          = (arm window cycles - ref window cycles) / updates in the window, split into the main
          thread, the workers and the other threads; mean and 95% t interval over the pairs; the
          A/A (ref-A2 against ref, divided by the same update count) beside it as the floor; the
          connections the origin accepted per update (cds-active: does an update drain the pool?).
Only valid, current legs count. A pair needs both legs valid in the same round and shape.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import evidence, stats  # noqa: E402

FLOOR_PCT = 0.34  # the published method's between-session term, log-%


def mean_ci(xs):
    """(mean, half-width of the 95% t interval, n); half-width None below 2 values."""
    n = len(xs)
    if not n:
        return None, None, 0
    m = sum(xs) / n
    if n < 2:
        return m, None, n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return m, stats.t_ppf(0.975, n - 1) * sd / math.sqrt(n), n


def valid(legs):
    return [m for m in legs if (m.get("verdict") or {}).get("valid")]


def by_cell(legs):
    out = {}
    for m in valid(legs):
        out[(m["shape"], m["arm"], m["round"])] = m
    return out


def window_cycles(m):
    """{main, workers, other, total} cycles in the perf window of a leg (per-thread perf)."""
    tc = m.get("thread_cycles")
    if not tc:
        return None
    return {"main": tc["main"], "workers": tc["workers"], "other": tc["other"],
            "total": tc["main"] + tc["workers"] + tc["other"]}


def pairs(cells, arm, ref, shape):
    rounds = sorted({r for (s, a, r) in cells if s == shape and a == arm})
    return [(cells[(shape, arm, r)], cells[(shape, ref, r)]) for r in rounds if (shape, ref, r) in cells]


def xds_rows(run_dir):
    legs = evidence.load_legs(run_dir)
    cells = by_cell(legs)
    arms = sorted({m["arm"] for m in legs})
    shapes = sorted({m["shape"] for m in legs})
    rows = []
    for sh in shapes:
        for a in arms:
            if a == "ref":
                continue
            ps = pairs(cells, a, "ref", sh)
            if not ps:
                continue
            n_up = [((x.get("xds") or {}).get("expected_in_window") or 0) for x, _ in ps]
            # the A/A arm has no updates: express it per update of the size's update arms
            per = max(n_up) if max(n_up) else None
            if per is None:
                upd = [m for m in valid(legs) if (m.get("xds") or {}).get("expected_in_window")]
                per = upd[0]["xds"]["expected_in_window"] if upd else None
            row = {"run": os.path.basename(run_dir.rstrip("/")), "shape": sh, "arm": a, "pairs": len(ps),
                   "updates_per_window": per}
            for part in ("main", "workers", "other", "total"):
                d = []
                for x, y in ps:
                    cx, cy = window_cycles(x), window_cycles(y)
                    if cx and cy and per:
                        d.append((cx[part] - cy[part]) / per)
                row[part] = mean_ci(d)
            acc = [(x.get("origin_accepts_window") or 0) - (y.get("origin_accepts_window") or 0) for x, y in ps
                   if x.get("origin_accepts_window") is not None and y.get("origin_accepts_window") is not None]
            row["accepts_per_update"] = mean_ci([v / per for v in acc]) if per and acc else (None, None, 0)
            row["main_busy"] = max((x.get("envoy_main_busy") or 0) for x, _ in ps)
            row["per_req_effect"] = [((math.log(x["per_req"]["cycles_total"] / y["per_req"]["cycles_total"])) * 100)
                                     for x, y in ps if x.get("per_req") and y.get("per_req")]
            rows.append(row)
    return rows


def fmt_ci(t, scale=1e6, unit="M"):
    m, hw, n = t
    if m is None:
        return "n/a"
    return "%+.2f%s" % (m / scale, unit) + (" ±%.2f" % (hw / scale) if hw is not None else "")


def xds_table(run_dirs, out=sys.stdout):
    out.write("| run | shape | arm | pairs | upd/window | main cycles/update | workers | other | total | "
              "accepts/update | main busy max | per-request effect |\n|" + "---|" * 12 + "\n")
    for rd in run_dirs:
        for r in xds_rows(rd):
            pe = mean_ci(r["per_req_effect"])
            out.write("| %s | %s | %s | %d | %s | %s | %s | %s | %s | %s | %.3f | %s |\n" % (
                r["run"], r["shape"], r["arm"], r["pairs"], r["updates_per_window"], fmt_ci(r["main"]),
                fmt_ci(r["workers"]), fmt_ci(r["other"]), fmt_ci(r["total"]),
                fmt_ci(r["accepts_per_update"], 1, ""), r["main_busy"],
                ("%+.2f%% ±%.2f" % (pe[0], pe[1]) if pe[1] is not None else "n/a")))
    out.write("\nThe A/A row (ref-A2) is the floor: a per-update price inside its interval is not a finding.\n")


def extproc_table(run_dir, out=sys.stdout):
    with open(os.path.join(run_dir, "results.json")) as f:
        res = json.load(f)
    legs = evidence.load_legs(run_dir)
    cells = by_cell(legs)
    out.write("| arm | arm cycles/req | effect (cycles/req) [95%] | widened ± | added cycles per request | user | "
              "kernel | workers | main | other threads | worker busy max | service CPU us/req |\n|" + "---|" * 12 + "\n")
    for sh, sres in res["analysis"]["shapes"].items():
        for comp in sres.get("comparisons", []):
            if comp.get("ref") != "off":
                continue
            a = comp["arm"]
            pm = (comp.get("cycles_total") or {}).get("paired") or {}
            ps = pairs(cells, a, "off", sh)
            add = mean_ci([x["per_req"]["cycles_total"] - y["per_req"]["cycles_total"] for x, y in ps])
            u = mean_ci([x["per_req"]["cycles_u"] - y["per_req"]["cycles_u"] for x, y in ps])
            k = mean_ci([x["per_req"]["cycles_k"] - y["per_req"]["cycles_k"] for x, y in ps])
            def cls(part):
                return mean_ci([x["thread_cycles"][part] / x["responses"] - y["thread_cycles"][part] / y["responses"]
                                for x, y in ps if x.get("thread_cycles") and y.get("thread_cycles")])
            oth, wk, mn = cls("other"), cls("workers"), cls("main")
            busy = max((x.get("envoy_worker_max_busy") or 0) for x, _ in ps) if ps else None
            side = "ext_proc" if a.startswith("xp-") else "origin"
            svc = mean_ci([((x.get("side_services") or {}).get(side) or {}).get("cpu_us_per_request") or 0
                           for x, _ in ps])
            se = pm["log_sd_pct"] / math.sqrt(pm["n"]) if pm.get("log_sd_pct") is not None and pm.get("n") else None
            wide = 1.96 * math.sqrt(se ** 2 + FLOOR_PCT ** 2) if se is not None else None
            absm = mean_ci([x["per_req"]["cycles_total"] for x, _ in ps])
            out.write("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n" % (
                a, fmt_ci(absm, 1e3, "k").lstrip("+"), ("%+.2f%% [%+.2f, %+.2f]" % (pm["effect_pct"], pm["lo_pct"], pm["hi_pct"])
                    if pm.get("effect_pct") is not None else "n/a"),
                ("%.2f" % wide) if wide is not None else "n/a", fmt_ci(add, 1e3, "k"), fmt_ci(u, 1e3, "k"),
                fmt_ci(k, 1e3, "k"), fmt_ci(wk, 1e3, "k"), fmt_ci(mn, 1e3, "k"), fmt_ci(oth, 1e3, "k"), busy,
                fmt_ci(svc, 1, "")))
    out.write("\nService CPU: the ext_proc container's cgroup for xp-* arms, the origin container (nginx: origin "
              "plus the ext_authz gRPC service) otherwise; exploratory, outside Envoy's number.\n")


EXTPROC_PAIRS = [("xp-default", "xp-reqhdr"), ("xp-default", "authz-grpc"), ("xp-reqhdr", "authz-grpc"),
                 ("authz-grpc-google", "authz-grpc"), ("xp-default-google", "xp-default"),
                 ("xp-reqhdr-google", "xp-reqhdr"), ("xp-default-google", "xp-reqhdr-google")]


def ratio_pct(log_pct):
    """A mean or bound of 100 ln(ratio) as the percent change of the ratio."""
    return (math.exp(log_pct / 100.0) - 1.0) * 100.0


def direct_pairs(run_dir, pairs_=EXTPROC_PAIRS, out=sys.stdout):
    """Arm against arm (not against `off`), paired by round: the effect is the mean of 100 ln(arm / ref)
    turned back into a percent change of the ratio, with its 95% t interval treated the same way (as
    every other Effect in the tables); widened = 1.96 sqrt(SE^2 + 0.34^2) stays in log-%. Added cycles per
    request in total and split into workers and the other (non-main, non-worker) threads."""
    cells = by_cell(evidence.load_legs(run_dir))
    out.write("| comparison | effect [95%] (ratio) | widened ± (log-%) | Δ cycles/req | Δ workers | Δ other threads |\n"
              "|" + "---|" * 6 + "\n")
    for a, b in pairs_:
        sh = sorted({s for (s, x, _) in cells if x == a})[0]
        ps = pairs(cells, a, b, sh)
        lg = [100.0 * math.log(x["per_req"]["cycles_total"] / y["per_req"]["cycles_total"]) for x, y in ps]
        m, hw, n = mean_ci(lg)
        se = hw / stats.t_ppf(0.975, n - 1) if hw is not None else None
        wide = 1.96 * math.sqrt(se ** 2 + FLOOR_PCT ** 2) if se is not None else None

        def per_req(part):
            return mean_ci([x["thread_cycles"][part] / x["responses"] - y["thread_cycles"][part] / y["responses"]
                            for x, y in ps])
        add = mean_ci([x["per_req"]["cycles_total"] - y["per_req"]["cycles_total"] for x, y in ps])
        out.write("| %s against %s | %+.2f%% [%+.2f, %+.2f] | %.2f | %s | %s | %s |\n" % (
            a, b, ratio_pct(m), ratio_pct(m - hw), ratio_pct(m + hw), wide, fmt_ci(add, 1e3, "k"),
            fmt_ci(per_req("workers"), 1e3, "k"), fmt_ci(per_req("other"), 1e3, "k")))


def validity_table(run_dirs, out=sys.stdout):
    """Valid and invalid legs per run and arm, with the invalid legs' reasons."""
    for rd in run_dirs:
        legs = evidence.load_legs(rd)
        out.write("%s: %d legs, %d valid\n" % (os.path.basename(rd.rstrip("/")), len(legs), len(valid(legs))))
        for m in legs:
            if not (m.get("verdict") or {}).get("valid"):
                out.write("  invalid %s: %s\n" % (m.get("leg_id"), "; ".join(m["verdict"].get("reasons", []))[:300]))


def other_threads(run_dir, out=sys.stdout):
    """Cycles per request of the threads other than main and workers, by thread name, per arm (means)."""
    legs = valid(evidence.load_legs(run_dir))
    acc = {}
    for m in legs:
        tc = m.get("thread_cycles")
        if not tc or not m.get("responses"):
            continue
        for k, v in tc["other_by_comm"].items():
            acc.setdefault(m["arm"], {}).setdefault(k, []).append(v / m["responses"])
    for a in sorted(acc):
        out.write("%s: %s\n" % (a, ", ".join("%s %.1fk" % (k, sum(v) / len(v) / 1e3)
                                             for k, v in sorted(acc[a].items(), key=lambda kv: -sum(kv[1])))))


def main(argv):
    if len(argv) >= 2 and argv[0] == "validity":
        validity_table(argv[1:])
        return 0
    if len(argv) >= 2 and argv[0] == "pairs":
        direct_pairs(argv[1])
        return 0
    if len(argv) >= 2 and argv[0] == "threads":
        other_threads(argv[1])
        return 0
    if len(argv) < 2 or argv[0] not in ("extproc", "xds"):
        print(__doc__)
        return 2
    if argv[0] == "extproc":
        extproc_table(argv[1])
    else:
        xds_table(argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
