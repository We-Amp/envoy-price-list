#!/usr/bin/env python3
"""Wave 7 S3 mechanism legs (the S2 script, unchanged but for this line and the path below) (non-scored): syscalls per request from the syscall legs, and the cycle shares
of the syscall subtrees from the call-graph legs.

    python3 examples/wave7s3/mech_table.py MECH_DIR [--json OUT] [--check]

MECH_DIR holds mech-<name>/ (the harness's run directory of the legs) and out-mech-<name>/ (the wrappers'
output: sys-<pid>.stat.csv, sys-<pid>.trace.txt, kcg-<pid>.folded.gz). A leg's processes are found by the
PIDs its record carries (envoy_pid, hop2_pid). --check (the chain's pipeline smoke): exit 1 unless every
syscall leg has tracepoint counts and every call-graph leg has folded worker stacks with user and kernel time. Counts are divided by the leg's responses in the window
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
         "syscall_enter_from_user_mode", "entry_SYSRETQ_unsafe_stack", "syscall_exit_work", "arch_exit_to_user_mode_prepare",
         "native_irq_return_iret")
SUB = {"readv": ("__x64_sys_readv", "do_readv"), "writev": ("__x64_sys_writev", "do_writev"),
       "epoll_wait": ("__x64_sys_epoll_wait", "do_epoll_wait", "__x64_sys_epoll_pwait"),
       "epoll_ctl": ("__x64_sys_epoll_ctl",), "read": ("__x64_sys_read",), "recvfrom": ("__x64_sys_recvfrom",),
       "sendto": ("__x64_sys_sendto",), "write": ("__x64_sys_write",), "recvmmsg": ("__x64_sys_recvmmsg",),
       "recvmsg": ("__x64_sys_recvmsg",), "sendmsg": ("__x64_sys_sendmsg",), "sendmmsg": ("__x64_sys_sendmmsg",)}
SCHED = ("schedule", "__schedule", "schedule_hrtimeout_range", "schedule_hrtimeout_range_clock")
# user-space frames whose inclusive share is reported (a stack counts once per name it contains)
USER = {
    # the UDP read callback is the root of all QUIC packet handling: its share is the read plus everything the
    # packets cause; the receive path proper is readFromSocket minus passPayloadToProcessor (mech_gates.py)
    "udp read callback (UdpListenerImpl::handleReadCallback)": re.compile(r"UdpListenerImpl::handleReadCallback"),
    "Utility::readFromSocket": re.compile(r"Network::Utility::readFromSocket\("),
    "passPayloadToProcessor (packet handling)": re.compile(r"passPayloadToProcessor"),
    "IoSocketHandleImpl::recvmmsg": re.compile(r"IoSocketHandleImpl::recvmmsg"),
    "http1 parser (BalsaFrame::ProcessInput)": re.compile(r"BalsaFrame::ProcessInput"),
    "http1 bufferBody": re.compile(r"bufferBody"),
    "http1 dispatch (ConnectionImpl::dispatch)": re.compile(r"Http1::ConnectionImpl::dispatch"),
    "http2 dispatch": re.compile(r"Http2::ConnectionImpl::dispatch"),
    "Buffer::OwnedImpl::add": re.compile(r"Buffer::OwnedImpl::add(Impl)?\("),
    "Buffer::OwnedImpl::move": re.compile(r"Buffer::OwnedImpl::move\("),
    "Buffer::OwnedImpl::read (socket read)": re.compile(r"Buffer::OwnedImpl::(read|reserve\w*)\("),
    "timers (enableTimer / TimerImpl)": re.compile(r"TimerImpl::enable|::enableTimer|resetIdleTimer|event_add|evtimer|event_del"),
    "quic (quic:: or Envoy::Quic frames)": re.compile(r"(^|;)quic::|Envoy::Quic"),
    "readDisable": re.compile(r"readDisable"),
}
LEAF = {"memmove/memcpy (leaf)": re.compile(r"mem(move|cpy)|__memcpy|__memmove"),
        "malloc/free (leaf, tcmalloc)": re.compile(r"tcmalloc|operator new|operator delete|^free$|^malloc$")}


def folded(p, comm_ok=lambda c: c.startswith("wrk:")):
    """Cycle shares of the Envoy worker threads' samples: user, kernel, each syscall subtree (inclusive), the
    scheduling part of epoll_wait, the self time of the syscall entry and exit symbols, the inclusive share of
    the named user frames, and the top self symbols."""
    if not os.path.exists(p):
        return None
    tot = user = 0
    sub = {k: 0 for k in SUB}
    usr = {k: 0 for k in USER}
    usr_k = {k: 0 for k in USER}
    leafs = {k: 0 for k in LEAF}
    sched_in_epoll = entry = 0
    selfk, selfu = {}, {}
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
            leaf = fr[-1]
            ufr = [x for x in fr[1:] if not x.endswith("_[k]")]
            ujoin = ";".join(ufr)
            kern = leaf.endswith("_[k]")
            for k, rx in USER.items():
                if rx.search(ujoin):
                    usr[k] += per
                    if kern:
                        usr_k[k] += per
            if not kern:
                user += per
                selfu[leaf] = selfu.get(leaf, 0) + per
                for k, rx in LEAF.items():
                    if rx.search(leaf):
                        leafs[k] += per
                continue
            ks = set(x[:-4] for x in fr[1:] if x.endswith("_[k]"))
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
    top = lambda d, n: [(k[:160], v / tot) for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]]  # noqa: E731
    return {"total": tot, "box": box, "user_share": user / tot, "kernel_share": 1 - user / tot,
            "subtree_share": {k: v / tot for k, v in sub.items()}, "epoll_wait_sched_share": sched_in_epoll / tot,
            "entry_exit_self_share": entry / tot, "user_frame_share": {k: v / tot for k, v in usr.items()},
            "user_frame_kernel_part": {k: v / tot for k, v in usr_k.items()},
            "leaf_share": {k: v / tot for k, v in leafs.items()},
            "top_kernel_self": top(selfk, 30), "top_user_self": top(selfu, 40)}


FLOW = ("cluster.origin.upstream_flow_control_paused_reading_total", "cluster.origin.upstream_flow_control_resumed_reading_total",
        "cluster.origin.upstream_flow_control_backed_up_total", "cluster.origin.upstream_flow_control_drained_total",
        "http.ingress_http.downstream_flow_control_paused_reading_total",
        "http.ingress_http.downstream_flow_control_resumed_reading_total")


def main(argv):
    M = argv[0].rstrip("/")
    out = {"sys": [], "kcg": []}
    for name in sorted(os.listdir(M)):
        # mech-<name> and the pipeline smoke's smoke-mech-<kind>; out-<name> holds the wrappers' output
        if "mech-" not in name or name.startswith("out-") or not os.path.isdir(os.path.join(M, name)):
            continue
        od = os.path.join(M, "out-" + name)
        for m in legs_of(os.path.join(M, name)):
            resp = m.get("responses") or 0
            for hop, pid in (("A", m.get("envoy_pid")), ("B", m.get("hop2_pid"))):
                if not pid:
                    continue
                rec = {"run": name, "arm": m["arm"], "shape": m["shape"], "hop": hop, "pid": pid, "responses_20s": resp,
                       "valid": (m.get("verdict") or {}).get("valid"), "reasons": (m.get("verdict") or {}).get("reasons"),
                       "per_req": m.get("per_req") if hop == "A" else m.get("hop2_per_req"),
                       "events_per_response": ((m.get("stream_origin") or {}).get("d") or {}).get("events", 0)
                       / max(1, ((m.get("stream_origin") or {}).get("d") or {}).get("responses", 0)),
                       "flow_per_req": {k: (m.get("sut_stats_window") or {}).get(k, 0) / (m.get("responses_raw") or 1)
                                        for k in FLOW},
                       "udp_per_req": {k: v / (m.get("responses_raw") or 1) for k, v in
                                       ((m.get("kernel_net") or {}).get("d") or {}).items() if k.startswith("Udp")},
                       "worker_max_share": m.get("envoy_worker_max_share")}
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
        if any(r["flow_per_req"].values()):
            print("flow control per request: " + ", ".join("%s %.4f" % (k.split(".")[-1].replace("_total", "") + (
                " (up)" if k.startswith("cluster") else " (down)"), v) for k, v in r["flow_per_req"].items()))
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
        print("user frames, inclusive (kernel part inside): " + ", ".join("%s %.2f (%.2f)" % (
            k, 100 * v, 100 * p["user_frame_kernel_part"][k]) for k, v in p["user_frame_share"].items() if v))
        print("leaf symbols: " + ", ".join("%s %.2f" % (k, 100 * v) for k, v in p["leaf_share"].items()))
        print("top user self: " + ", ".join("%s %.2f" % (k[:70], 100 * v) for k, v in p["top_user_self"][:12]))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    if "--check" in argv:
        bad = []
        for r in out["sys"]:
            if (r["tracepoints_per_req"].get("sys_enter") or 0) < 1:
                bad.append("%s %s/%s: no tracepoint counts" % (r["run"], r["arm"], r["shape"]))
            if not r["trace_per_req"]:
                bad.append("%s %s/%s: no perf trace table (tracepoint counts are the figures)" % (r["run"], r["arm"], r["shape"]))
        for r in out["kcg"]:
            p = r["profile"] or {}
            if not p.get("total") or not p.get("user_share") or not p.get("kernel_share"):
                bad.append("%s %s/%s: no folded worker stacks with user and kernel time" % (r["run"], r["arm"], r["shape"]))
        if not out["sys"] or not out["kcg"]:
            bad.append("no syscall leg or no call-graph leg found")
        print("\nCHECK %s%s" % ("OK" if not bad else "FAILED: ", "; ".join(bad)))
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
