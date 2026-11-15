#!/usr/bin/env python3
"""Markdown tables from ab-summary.json and ab-records.json (wc2.py)."""
import json
import os
import sys

out = sys.argv[1]
S = json.load(open(os.path.join(out, "ab-summary.json")))
R = json.load(open(os.path.join(out, "ab-records.json")))


def ci(r, k="ratio"):
    p = r[k]
    return "%+.1f%% [%+.1f, %+.1f]" % (p["effect_pct"], p["lo_pct"], p["hi_pct"])


def d(x, f="%.4f", scale=1.0):
    return "%s [%s, %s]" % (f % (x["mean"] * scale), f % (x["lo"] * scale), f % (x["hi"] * scale))


n = S["pairs"]
print("pairs %d, attempts %d, invalid attempts %d" % (n, S["attempts"], len(S["invalid_attempts"])))
for x in S["invalid_attempts"]:
    print("  invalid:", x)
print("concurrency", S["concurrency"], "threads", S["threads_total"])
print()
print("| Rate | Metric | default (40) mean / median | req (2) mean / median | default vs req, paired [95% CI] | pairs req lower |")
print("|---|---|---|---|---|---|")
lab = {"cpu_us_per_req": "Envoy CPU per request (µs)", "p50_us": "p50 latency (µs)", "p99_us": "p99 latency (µs)",
       "envoy_cpus_cgroup": "Envoy CPU (CPUs)"}
for k, o in S["rates"].items():
    for met in ("cpu_us_per_req", "p50_us", "p99_us"):
        m = o[met]
        f = "%.1f" if met == "cpu_us_per_req" else "%.0f"
        print("| %s rps | %s | %s / %s | %s / %s | %s | %d/%d |" % (
            k, lab[met], f % m["default_mean"], f % m["default_median"], f % m["req_mean"], f % m["req_median"],
            ci(m), m["won_by_req"], n))
print()
print("| Rate | Envoy CPU default | req | load gap (CPUs) [95% CI] | idle gap | gap minus same-round idle gap (CPUs) [95% CI] | per-request extra (µs) [95% CI] | idle share of gap |")
print("|---|---|---|---|---|---|---|---|")
ig = S["idle"]["diff_cpus"]
for k, o in S["rates"].items():
    e = o["envoy_cpus_cgroup"]
    print("| %s rps | %.3f | %.3f | %s | %.4f | %s | %s | %.0f%% |" % (
        k, e["default_mean"], e["req_mean"], d(o["load_gap_cpus"]), ig["mean"],
        d(o["load_gap_minus_idle_gap_cpus"]), d(o["per_req_extra_us"], "%.1f"), 100 * o["idle_share_of_gap"]))
print()
print("Workers and connections (medians over valid legs)")
print("| Rate | Arm | busiest worker | median worker | least busy | busiest share | workers holding a connection | hot client conns | top-16 conn share | min client headroom | node other CPUs max | sched vs cgroup max |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for k, o in S["rates"].items():
    for arm in ("default", "req"):
        w = o["workers_" + arm]
        print("| %s | %s | %.3f | %.3f | %.3f | %.3f | %d | %d/%d | %.3f | %.0f%% | %.3f | %.2f%% |" % (
            k, arm, w["busy_max_median"], w["busy_median_median"], w["busy_min_median"], w["max_share_median"],
            w["workers_with_cx_median"], w["hot_conns_median"], w["client_conns_median"],
            w["top16_conn_share_median"], 100 * w["client_headroom_min"], w["node_other_cpus_max"],
            w["sched_vs_cgroup_max_pct"]))
print()
i = S["idle"]
print("idle CPUs default mean %.4f median %.4f (sched %.4f); req mean %.4f median %.4f (sched %.4f)" % (
    i["default_cpus"], i["default_cpus_median"], i["default_sched_cpus"], i["req_cpus"], i["req_cpus_median"],
    i["req_sched_cpus"]))
print("idle diff CPUs", d(i["diff_cpus"]), "ratio", ci(i))
print("rss idle default", i["rss_kb_default"])
print("rss idle req    ", i["rss_kb_req"])
print("rss idle diff kB", d(i["rss_diff_kb"], "%.0f"))
print("rss after load default", i["rss_after_load_default_kb"])
print("rss after load req    ", i["rss_after_load_req_kb"])
print("rss after load diff kB", d(i["rss_after_load_diff_kb"], "%.0f"))
recs = [r for r in R["records"] if r.get("ok")]
print("rate dev max %%: %s" % {k: max(o["workers_default"]["rate_dev_max_pct"], o["workers_req"]["rate_dev_max_pct"])
                               for k, o in S["rates"].items()})
print("first/last record", recs[0]["started_utc"], recs[-1]["started_utc"])
print("worker_cx default sample", sorted(recs[0]["loads"]["2000"]["worker_cx_active"].values()) if recs[0]["arm"] == "default" else "")
