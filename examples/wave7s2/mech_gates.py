#!/usr/bin/env python3
"""Wave 7 S2: the pre-registered readings of the mechanism legs (non-scored), from mech_table.py's JSON and the
folded stacks.

    python3 examples/wave7s2/mech_gates.py MECH_DIR MECH_TABLE_JSON [--json OUT]

  events    syscalls per streamed event = (per request on the 200-event shape - on the 20-event shape) / 180, by
            tracepoint; the count gate (4.5 to 5.5 in all, at least 0.9 readv returning EAGAIN, at least 0.9
            epoll_wait with timeout 0); the price bounds of the two avoidable calls from the call-graph leg of
            base/ev200 (lower: 2 x entry-and-exit self time per call; upper: half of the readv and epoll_wait
            subtrees; stricter upper: half of readv plus half of the non-scheduling part of epoll_wait)
  buffer    epoll_ctl, pauses and resumes per request, default against limit
  http3     syscalls per request, and the receive path of the profile: Utility::readFromSocket (inclusive) minus
            passPayloadToProcessor (the handling of the packets read), as a share of worker-thread cycles
  chunked   the callers of the libc copy in cl8k and ch8k at 1 MiB"""
import collections
import gzip
import json
import os
import re
import sys


def legs(d):
    out = {}
    p = os.path.join(d, "legs.jsonl")
    if os.path.exists(p):
        for line in open(p):
            m = json.loads(line) if line.strip() else {}
            if m.get("arm") and m.get("envoy_pid"):
                out[(m["arm"], m["shape"])] = m
    return out


def stacks(path):
    with gzip.open(path, "rt", errors="replace") as f:
        for line in f:
            try:
                st, per, _ = line.rstrip("\n").split("\t")
            except ValueError:
                continue
            fr = st.split(";")
            if fr[0].startswith("wrk:"):
                yield fr[1:], int(per)


def main(argv):
    M, T = argv[0].rstrip("/"), json.load(open(argv[1]))
    sysl = {(r["run"], r["arm"], r["shape"]): r for r in T["sys"]}
    kcg = {(r["run"], r["arm"], r["shape"]): r for r in T["kcg"]}
    out = {}
    tp = lambda run, arm, shape: sysl[(run, arm, shape)]["tracepoints_per_req"]  # noqa: E731
    NAMES = [("all syscalls", "sys_enter"), ("readv", "sys_enter_readv"), ("readv returning EAGAIN", "sys_exit_readv"),
             ("sendto", "sys_enter_sendto"), ("writev", "sys_enter_writev"), ("epoll_wait", "sys_exit_epoll_wait"),
             ("epoll_wait with timeout 0", "sys_enter_epoll_wait"), ("epoll_ctl", "sys_enter_epoll_ctl")]
    print("## syscalls per streamed event: (per request on the 200-event shape - on the 20-event shape) / 180\n")
    print("| run / arm | " + " | ".join(n for n, _ in NAMES) + " |\n|---|" + "---|" * len(NAMES))
    out["events"] = {}
    for run, arm, hi, lo in (("mech-sys-stream", "base", "ev200", "ev20"), ("mech-sys-stream", "idle-off", "ev200", "ev20"),
                             ("mech-sys-grpc", "base", "g200", "g20"), ("mech-sys-grpc", "base-A2", "g200", "g20")):
        if (run, arm, hi) not in sysl:
            continue
        a, b = tp(run, arm, hi), tp(run, arm, lo)
        row = {n: (a.get(k, 0) - b.get(k, 0)) / 180.0 for n, k in NAMES}
        row["per request part (20-event shape minus 20 events), all syscalls"] = b.get("sys_enter", 0) - 20 * row["all syscalls"]
        out["events"]["%s %s" % (run, arm)] = row
        print("| %s %s | " % (run, arm) + " | ".join("%.3f" % row[n] for n, _ in NAMES) + " |")
    e = out["events"].get("mech-sys-stream base")
    if e:
        gate = {"all in [4.5, 5.5]": 4.5 <= e["all syscalls"] <= 5.5, "EAGAIN readv >= 0.9": e["readv returning EAGAIN"] >= 0.9,
                "zero-timeout epoll_wait >= 0.9": e["epoll_wait with timeout 0"] >= 0.9}
        out["event_count_gate"] = gate
        print("\ncount gate on base, per event: " + "; ".join("%s: %s" % (k, "met" if v else "NOT met") for k, v in gate.items()))
        p = (kcg.get(("mech-kcg-stream", "base", "ev200")) or {}).get("profile")
        if p:
            n = e["all syscalls"]
            lower = 2.0 * p["entry_exit_self_share"] / n
            up_plan = 0.5 * (p["subtree_share"]["readv"] + p["subtree_share"]["epoll_wait"])
            up_strict = 0.5 * p["subtree_share"]["readv"] + 0.5 * (p["subtree_share"]["epoll_wait"] - p["epoll_wait_sched_share"])
            out["event_price"] = {"lower": lower, "upper_plan": up_plan, "upper_strict": up_strict,
                                  "mid_plan": (lower + up_plan) / 2, "mid_strict": (lower + up_strict) / 2,
                                  "shares": {"readv": p["subtree_share"]["readv"], "epoll_wait": p["subtree_share"]["epoll_wait"],
                                             "epoll_wait_sched": p["epoll_wait_sched_share"], "sendto": p["subtree_share"]["sendto"],
                                             "entry_exit_self": p["entry_exit_self_share"], "user": p["user_share"]}}
            print("price of the two avoidable calls, share of worker cycles on base/ev200 (99%% of them are event work): lower "
                  "%.1f%% (2 x %.2f%% entry and exit self time / %.2f calls), upper %.1f%% (plan rule), %.1f%% (stricter); "
                  "midpoints %.1f%% / %.1f%%; 3%% line" % (100 * lower, 100 * p["entry_exit_self_share"], n, 100 * up_plan,
                                                           100 * up_strict, 50 * (lower + up_plan), 50 * (lower + up_strict)))
    print("\n## buffer limit: per request (syscall legs)\n")
    print("| shape | arm | all syscalls | epoll_ctl | upstream pauses | upstream resumes | downstream pauses | readv | writev | "
          "epoll_wait | of which timeout 0 | cycles per request (this leg, under the tracer) |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    out["buffer"] = {}
    for (run, arm, shape), r in sorted(sysl.items(), key=lambda kv: (kv[0][2], kv[0][1])):
        if run != "mech-sys-buf":
            continue
        t, f = r["tracepoints_per_req"], r["flow_per_req"]
        g = lambda k: f.get(k, 0)  # noqa: E731
        row = {"all": t.get("sys_enter", 0), "epoll_ctl": t.get("sys_enter_epoll_ctl", 0),
               "up_paused": g("cluster.origin.upstream_flow_control_paused_reading_total"),
               "up_resumed": g("cluster.origin.upstream_flow_control_resumed_reading_total"),
               "down_paused": g("http.ingress_http.downstream_flow_control_paused_reading_total"),
               "readv": t.get("sys_enter_readv", 0), "writev": t.get("sys_enter_writev", 0),
               "epoll_wait": t.get("sys_exit_epoll_wait", 0), "epoll_wait0": t.get("sys_enter_epoll_wait", 0),
               "cycles": (r.get("per_req") or {}).get("cycles_total")}
        out["buffer"]["%s/%s" % (shape, arm)] = row
        print("| %s | %s | %.2f | %.2f | %.3f | %.3f | %.3f | %.2f | %.2f | %.2f | %.2f | %.0fk |" % (
            shape, arm, row["all"], row["epoll_ctl"], row["up_paused"], row["up_resumed"], row["down_paused"], row["readv"],
            row["writev"], row["epoll_wait"], row["epoll_wait0"], (row["cycles"] or 0) / 1e3))
    print("\n## HTTP/3 at 4 KB: syscalls per request\n")
    H3 = [("all", "sys_enter"), ("recvmmsg", "sys_enter_recvmmsg"), ("recvmmsg returning EAGAIN", "sys_exit_recvmmsg"),
          ("sendmsg", "sys_enter_sendmsg"), ("sendmmsg", "sys_enter_sendmmsg"), ("recvfrom", "sys_enter_recvfrom"),
          ("readv", "sys_enter_readv"), ("sendto", "sys_enter_sendto"), ("epoll_wait", "sys_exit_epoll_wait"),
          ("epoll_wait with timeout 0", "sys_enter_epoll_wait")]
    print("| arm | " + " | ".join(n for n, _ in H3) + " |\n|---|" + "---|" * len(H3))
    out["h3_sys"] = {}
    for arm in ("h2tls", "h3"):
        if ("mech-sys-h3", arm, "s") in sysl:
            t = tp("mech-sys-h3", arm, "s")
            out["h3_sys"][arm] = {n: t.get(k, 0) for n, k in H3}
            print("| %s | " % arm + " | ".join("%.2f" % t.get(k, 0) for _, k in H3) + " |")
    L = legs(os.path.join(M, "mech-kcg-h3"))
    if ("h3", "s") in L:
        tot = 0
        inc = collections.Counter()
        pat = {"UdpListenerImpl::handleReadCallback": "handleReadCallback", "Utility::readPacketsFromSocket": "readPacketsFromSocket",
               "Network::Utility::readFromSocket(": "readFromSocket", "passPayloadToProcessor": "passPayloadToProcessor",
               "IoSocketHandleImpl::recvmmsg": "IoSocketHandleImpl::recvmmsg", "__x64_sys_recvmmsg": "recvmmsg syscall (kernel)",
               "__x64_sys_sendmsg": "sendmsg syscall (kernel)"}
        for fr, per in stacks(os.path.join(M, "out-mech-kcg-h3", "kcg-%d.folded.gz" % L[("h3", "s")]["envoy_pid"])):
            tot += per
            seen = set()
            for x in fr:
                for k, name in pat.items():
                    if k in x and name not in seen:
                        seen.add(name)
                        inc[name] += per
        sh = {k: v / tot for k, v in inc.items()}
        recv = sh.get("readFromSocket", 0) - sh.get("passPayloadToProcessor", 0)
        out["h3_profile"] = dict(sh, receive_path=recv, worker_cycles=tot)
        print("\nh3/4 KB profile, share of worker-thread cycles (inclusive): " + ", ".join(
            "%s %.2f%%" % (k, 100 * v) for k, v in sorted(sh.items(), key=lambda kv: -kv[1])))
        print("receive path = readFromSocket - passPayloadToProcessor = **%.2f%%** of worker cycles (of which the recvmmsg "
              "call %.2f%%, its kernel part %.2f%%; the rest is buffer set-up and tear-down around the call); 2%% line" % (
                  100 * recv, 100 * sh.get("IoSocketHandleImpl::recvmmsg", 0), 100 * sh.get("recvmmsg syscall (kernel)", 0)))
    print("\n## chunked at 1 MiB: the libc copy (leaf [libc.so.6]) and its callers, share of worker-thread cycles\n")
    L = legs(os.path.join(M, "mech-kcg-chunked"))
    out["chunked_copy"] = {}
    for arm in ("cl8k", "ch8k"):
        if (arm, "b1m") not in L:
            continue
        tot = libc = 0
        ch = collections.Counter()
        named = collections.Counter()
        for fr, per in stacks(os.path.join(M, "out-mech-kcg-chunked", "kcg-%d.folded.gz" % L[(arm, "b1m")]["envoy_pid"])):
            tot += per
            for k in ("BalsaFrame::ProcessInput", "Buffer::OwnedImpl::addImpl", "Http1::ConnectionImpl::dispatch(", "bufferBody",
                      "Buffer::OwnedImpl::move("):
                if any(k in x for x in fr):
                    named[k] += per
            if fr and fr[-1] == "[libc.so.6]":
                libc += per
                ch[" <- ".join(re.sub(r"\(.*", "", x)[-48:] for x in fr[-2:-4:-1])] += per
        out["chunked_copy"][arm] = {"libc_leaf": libc / tot, "callers": {k: v / tot for k, v in ch.most_common(3)},
                                    "inclusive": {k: v / tot for k, v in named.items()}}
        print("%s: libc leaf %.2f%%; top callers: %s; inclusive: %s" % (
            arm, 100 * libc / tot, "; ".join("%s %.2f%%" % (k, 100 * v / tot) for k, v in ch.most_common(2)),
            ", ".join("%s %.2f%%" % (k, 100 * v / tot) for k, v in named.most_common())))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
