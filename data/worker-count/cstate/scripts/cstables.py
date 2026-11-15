#!/usr/bin/env python3
"""Print the C-state experiment tables from cs-summary.json / cs-records.json."""
import json
import os
import sys

d = sys.argv[1]
S = json.load(open(os.path.join(d, "cs-summary.json")))
R = json.load(open(os.path.join(d, "cs-records.json")))


def f(x, n=1):
    return "-" if x is None else ("%.*f" % (n, x))


def ci(r, n=1):
    return "%+.*f%% [%+.*f, %+.*f]" % (n, r["effect_pct"], n, r["lo_pct"], n, r["hi_pct"])


print("attempts", S["attempts"], "valid", S["valid"], "pairs", S["pairs"])
for x in S["invalid_attempts"]:
    print("invalid:", x)
for k in S["cells"]:
    print("\n## rate", k)
    print("| Condition | Metric | default (40) mean | req (2) mean | default vs req [95% CI] | req lower |")
    for c in ("A", "B"):
        cell, av = S["cells"][k][c], S["arm_vs_arm"][k][c]
        for m, n in (("cpu_us_per_req", 1), ("p50_us", 0), ("ins_per_req", 0), ("cyc_per_req", 0), ("ipc", 3),
                     ("ins_u_per_req", 0), ("ipc_u", 3), ("ins_k_per_req", 0), ("ipc_k", 3),
                     ("user_us_per_req", 1), ("sys_us_per_req", 1)):
            if m not in av:
                continue
            print("| %s | %s | %s | %s | %s | %d/%d |" % (c, m, f(cell["default"][m]["mean"], n),
                                                      f(cell["req"][m]["mean"], n), ci(av[m]),
                                                      av[m]["won_by_req"], av[m]["n"]))
        e = av["per_req_extra_us_beyond_idle"]
        print("| %s | extra us/req beyond idle gap | | | %.1f [%.1f, %.1f] | |" % (c, e["mean"], e["lo"], e["hi"]))
    for c in ("A", "B"):
        cell = S["cells"][k][c]
        for arm in ("default", "req"):
            x = cell[arm]
            print("%s %s vcs/req %.3f ivcs/req %.4f migr/s %.2f busy max %.3f med %.3f | res POLL %.4f C1 %.3f C1E %.3f "
                  "C6 %.3f | entries/cpu-s C1 %.0f C1E %.0f C6 %.0f" % (
                      c, arm, x["vcs_per_req"]["mean"], x["ivcs_per_req"]["mean"], x["migr_per_s"]["mean"],
                      x["busy_max"]["mean"], x["busy_median"]["mean"], x["res_POLL"]["mean"], x["res_C1"]["mean"],
                      x["res_C1E"]["mean"], x["res_C6"]["mean"], x["entries_C1"]["mean"], x["entries_C1E"]["mean"],
                      x["entries_C6"]["mean"]))
    for arm in ("default", "req"):
        ce = S["cond_effect"][k][arm]
        print("cond A vs B, %s: cpu %s  p50 %s  ins %s  cyc %s  ipc %s" % (
            arm, ci(ce["cpu_us_per_req"]), ci(ce["p50_us"]), ci(ce["ins_per_req"]), ci(ce["cyc_per_req"]),
            ci(ce["ipc"])))
    it = S["interaction"][k]["log_pct_A_minus_B"]
    print("interaction (log pct, A minus B): %.1f [%.1f, %.1f] per pair %s" % (
        it["mean"], it["lo"], it["hi"], [round(x, 1) for x in S["interaction"][k]["per_pair"]]))
    for p in S["placement_req"][k]:
        print("placement r%d %s same_core %.2f same_cpu %.2f distinct %s top %s migr/s %.2f topcpus %s" % (
            p["round"], p["cond"], p["same_core_frac"] or 0, p["same_cpu_frac"] or 0,
            list(p["distinct_cpus"].values()), [round(v, 2) for v in p["top_cpu_share"].values()], p["migr_per_s"],
            [(c, round(v, 3)) for c, v in p["top_node_cpus"]]))
print("\nidle")
for c in ("A", "B"):
    i = S["idle"][c]
    print(c, "default %.4f req %.4f diff %.4f [%.4f, %.4f]" % (i["default_cpus"], i["req_cpus"], i["diff_cpus"]["mean"],
                                                             i["diff_cpus"]["lo"], i["diff_cpus"]["hi"]),
          "res default", {k: round(v, 3) for k, v in i["node_residency_default"].items()},
          "res req", {k: round(v, 3) for k, v in i["node_residency_req"].items()})
print("\nwarm-ups")
for r in R["records"]:
    print(r["round"], r.get("cond"), r["arm"], r.get("attempt"), r.get("ok"), r.get("warmup"))
