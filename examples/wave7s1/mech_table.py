#!/usr/bin/env python3
"""Wave 7 S1 mechanism legs (non-scored): syscalls per request from the syscall legs, and the cycle shares
of the syscall subtrees from the call-graph legs.

    python3 examples/wave7s1/mech_table.py MECH_DIR [--json OUT]

MECH_DIR holds mech-<name>/ (the harness's run directory of the legs) and out-mech-<name>/ (the wrappers'
output: sys-<pid>.stat.csv, sys-<pid>.trace.txt, kcg-<pid>.folded.gz). A leg's processes are found by the
PIDs its record carries (envoy_pid, hop2_pid). Counts are divided by the leg's responses in the window
(`responses`, the harness's own count scaled to the 20 s perf window); the tools' windows are the same 20 s,
started a few milliseconds apart, so per-request figures carry about 1% of timing slack."""
import gzip
import json
import os
import re
import sys


def legs_of(d):
    p = os.path.join(d, "legs.jsonl")
    out = []
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line:
                m = json.loads(line)
                if m.get("arm") and m.get("envoy_pid"):
                    out.append(m)
    return out


def stat_csv(p):
    out = {}
    if not os.path.exists(p):
        return out
    seen = {}
    for line in open(p):
        f = line.strip().split(",")
        if len(f) < 3 or not f[2] or line.startswith("#"):
            continue
        try:
            v = float(f[0])
        except ValueError:
            continue
        k = f[2].split(":")[-1]
        seen[k] = seen.get(k, 0) + 1
        out[k if seen[k] == 1 else "%s#%d" % (k, seen[k])] = v
    return out


THREAD = re.compile(r"^\s*(\S.*?) \((\d+)\), (\d+) events")
ROW = re.compile(r"^\s+([a-z_0-9]+)\s+(\d+)\s+(\d+)\s+([\d.]+)")


def trace_txt(p):
    """{syscall: [calls, errors, total_ms]} summed over threads, and the same for wrk: threads only."""
    allt, wrk, cur = {}, {}, None
    if not os.path.exists(p):
        return allt, wrk
    for line in open(p, errors="replace"):
        m = THREAD.match(line)
        if m:
            cur = m.group(1)
            continue
        m = ROW.match(line)
        if m and cur is not None:
            for d in ([allt, wrk] if cur.startswith("wrk:") else [allt]):
                x = d.setdefault(m.group(1), [0, 0, 0.0])
                x[0] += int(m.group(2))
                x[1] += int(m.group(3))
                x[2] += float(m.group(4))
    return allt, wrk


ENTRY = ("entry_SYSCALL_64", "entry_SYSCALL_64_after_hwframe", "entry_SYSCALL_64_safe_stack", "syscall_return_via_sysret",
         "do_syscall_64", "x64_sys_call", "syscall_exit_to_user_mode", "syscall_exit_to_user_mode_prepare",
         "syscall_enter_from_user_mode", "entry_SYSRETQ_unsafe_stack", "__x64_sys_readv", "__x64_sys_epoll_wait",
         "__x64_sys_writev", "syscall_exit_work", "arch_exit_to_user_mode_prepare", "native_irq_return_iret",
         "entry_SYSCALL_64_after_hwframe")
SUB = {"readv": ("__x64_sys_readv", "do_readv"), "writev": ("__x64_sys_writev", "do_writev"),
       "epoll_wait": ("__x64_sys_epoll_wait", "do_epoll_wait", "__x64_sys_epoll_pwait"),
       "epoll_ctl": ("__x64_sys_epoll_ctl",), "read": ("__x64_sys_read",), "recvfrom": ("__x64_sys_recvfrom",),
       "sendto": ("__x64_sys_sendto",), "write": ("__x64_sys_write",)}
SCHED = ("schedule", "__schedule", "schedule_hrtimeout_range", "schedule_hrtimeout_range_clock")


def folded(p, comm_ok=lambda c: c.startswith("wrk:")):
    """Cycle shares of the Envoy worker threads' samples: user, kernel, each syscall subtree (inclusive), the
    scheduling part of epoll_wait, and the self time of the syscall entry and exit symbols."""
    if not os.path.exists(p):
        return None
    tot = user = 0
    sub = {k: 0 for k in SUB}
    sched_in_epoll = entry = softirq_in = 0
    selfk = {}
    box = 0
    with gzip.open(p, "rt", errors="replace") as f:
        for line in f:
            try:
                st, per, _n = line.rstrip("\n").split("\t")
            except ValueError:
                continue
            per = int(per)
            fr = st.split(";")
            box += per
            if not comm_ok(fr[0]):
                continue
            tot += per
            names = [x[:-4] if x.endswith("_[k]") else None for x in fr[1:]]
            leaf = fr[-1]
            if not leaf.endswith("_[k]"):
                user += per
                continue
            ks = set(n for n in names if n)
            hit = None
            for k, syms in SUB.items():
                if ks & set(syms):
                    sub[k] += per
                    hit = k
            if hit == "epoll_wait" and ks & set(SCHED):
                sched_in_epoll += per
            lf = leaf[:-4]
            selfk[lf] = selfk.get(lf, 0) + per
            if lf in ENTRY:
                entry += per
    if not tot:
        return {"total": 0, "box": box}
    top = sorted(selfk.items(), key=lambda kv: -kv[1])[:25]
    return {"total": tot, "box": box, "user_share": user / tot, "kernel_share": 1 - user / tot,
            "subtree_share": {k: v / tot for k, v in sub.items()}, "epoll_wait_sched_share": sched_in_epoll / tot,
            "entry_exit_self_share": entry / tot, "top_kernel_self": [(k, v / tot) for k, v in top]}


def main(argv):
    M = argv[0].rstrip("/")
    out = {"sys": [], "kcg": []}
    for name in sorted(os.listdir(M)):
        if not name.startswith("mech-") or not os.path.isdir(os.path.join(M, name)):
            continue
        od = os.path.join(M, "out-" + name)
        for m in legs_of(os.path.join(M, name)):
            resp = m.get("responses") or 0
            for hop, pid in (("A", m.get("envoy_pid")), ("B", m.get("hop2_pid"))):
                if not pid:
                    continue
                rec = {"run": name, "arm": m["arm"], "shape": m["shape"], "hop": hop, "pid": pid, "responses_20s": resp,
                       "valid": (m.get("verdict") or {}).get("valid"), "reasons": (m.get("verdict") or {}).get("reasons"),
                       "per_req": m.get("per_req") if hop == "A" else m.get("hop2_per_req")}
                if "sys" in name:
                    st = stat_csv(os.path.join(od, "sys-%d.stat.csv" % pid))
                    allt, wrk = trace_txt(os.path.join(od, "sys-%d.trace.txt" % pid))
                    rec["tracepoints_per_req"] = {k: v / resp for k, v in st.items()} if resp else {}
                    rec["trace_per_req"] = {k: {"calls": v[0] / resp, "errors": v[1] / resp, "ms_total": v[2]}
                                            for k, v in sorted(allt.items(), key=lambda kv: -kv[1][0])} if resp else {}
                    rec["trace_workers_per_req"] = {k: {"calls": v[0] / resp, "errors": v[1] / resp}
                                                    for k, v in sorted(wrk.items(), key=lambda kv: -kv[1][0])} if resp else {}
                    out["sys"].append(rec)
                else:
                    rec["profile"] = folded(os.path.join(od, "kcg-%d.folded.gz" % pid))
                    out["kcg"].append(rec)
    for r in out["sys"]:
        print("\n## syscalls: %s %s/%s hop %s (pid %d, %.0f responses in 20 s, leg valid: %s)\n" % (
            r["run"], r["arm"], r["shape"], r["hop"], r["pid"], r["responses_20s"], r["valid"]))
        tp = r["tracepoints_per_req"]
        print("tracepoint counts per request: " + ", ".join("%s %.3f" % (k.replace("sys_", ""), v) for k, v in tp.items()))
        print("\n| syscall (perf trace -s, all threads) | calls /request | errors /request |\n|---|---|---|")
        tc = te = 0
        for k, v in r["trace_per_req"].items():
            tc += v["calls"]
            te += v["errors"]
            if v["calls"] >= 0.005:
                print("| %s | %.3f | %.3f |" % (k, v["calls"], v["errors"]))
        print("| **all** | **%.3f** | **%.3f** |" % (tc, te))
    for r in out["kcg"]:
        p = r["profile"]
        print("\n## call graph: %s %s/%s hop %s (pid %d)\n" % (r["run"], r["arm"], r["shape"], r["hop"], r["pid"]))
        if not p or not p.get("total"):
            print("no worker samples")
            continue
        print("worker-thread cycles sampled: %.3g (of %.3g on these CPUs); user %.1f%%, kernel %.1f%%" % (
            p["total"], p["box"], 100 * p["user_share"], 100 * p["kernel_share"]))
        print("syscall subtrees (inclusive, %% of worker cycles): " + ", ".join(
            "%s %.2f" % (k, 100 * v) for k, v in sorted(p["subtree_share"].items(), key=lambda kv: -kv[1]) if v))
        print("scheduling inside epoll_wait: %.2f%%; self time of syscall entry and exit symbols: %.2f%%" % (
            100 * p["epoll_wait_sched_share"], 100 * p["entry_exit_self_share"]))
        print("top kernel self: " + ", ".join("%s %.2f" % (k, 100 * v) for k, v in p["top_kernel_self"][:14]))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1:])
