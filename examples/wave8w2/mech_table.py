#!/usr/bin/env python3
"""Wave 8 W8-2: the mechanism legs (non-scored) as tables, from the copied run directory (analysis only).

    python3 examples/wave8w2/mech_table.py RUNS_DIR [--json OUT]

  syscalls   per arm of mech/mech-sys-s and mech/mech-sys-shi[-half]: tracepoint counts over the tracer's 20 s
             window divided by the leg's responses in the perf window; UDP datagrams per request (the kernel's
             box-wide count over the harness window); the leg's validity, guards and binary
  profile    per arm of mech/mech-kcg-s: inclusive share of worker-thread cycles of the UDP read path, from the
             folded stacks. S2's definition D7: Utility::readFromSocket (inclusive) minus the handling of the
             packets read under it; the handling is taken as the frames of the packet processor
             (passPayloadToProcessor in v1.40.2's path; processPacket where the patched path calls it directly)
  loss       per arm of mech/loss-s: Envoy's QUIC connection statistics at the end of the leg (packets sent,
             received and retransmitted by the server side), per request of the whole leg
  smokes     one line per smoke leg: latency maximum and UDP datagrams per request"""
import collections
import gzip
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


chk = _load("w8w2_check_for_mech_table", os.path.join(HERE, "w2_check.py"))
mk = chk.mk
QS = mk.QS
SYS = [("all syscalls", "sys_enter"), ("recvmmsg", "sys_enter_recvmmsg"), ("recvmmsg returning EAGAIN", "sys_exit_recvmmsg"),
       ("recvmsg", "sys_enter_recvmsg"), ("sendmsg", "sys_enter_sendmsg"), ("sendmmsg", "sys_enter_sendmmsg"),
       ("readv", "sys_enter_readv"), ("readv returning EAGAIN", "sys_exit_readv"), ("writev", "sys_enter_writev"),
       ("sendto", "sys_enter_sendto"), ("epoll_wait", "sys_exit_epoll_wait"), ("epoll_wait with timeout 0", "sys_enter_epoll_wait"),
       ("epoll_ctl", "sys_enter_epoll_ctl"), ("timerfd_settime", "sys_enter_timerfd_settime"), ("futex", "sys_enter_futex")]
PAT = collections.OrderedDict([
    ("handleReadCallback", "UdpListenerImpl::handleReadCallback"),
    ("readPacketsFromSocket", "Utility::readPacketsFromSocket"),
    ("readFromSocket", "Network::Utility::readFromSocket("),
    ("readFromSocketRecvMmsg (either form)", "readFromSocketRecvMmsg"),
    ("passPayloadToProcessor", "passPayloadToProcessor"),
    ("processPacket", "::processPacket("),
    ("IoSocketHandleImpl::recvmmsg", "IoSocketHandleImpl::recvmmsg"),
    ("recvmmsg syscall (kernel)", "__x64_sys_recvmmsg"),
    ("sendmsg syscall (kernel)", "__x64_sys_sendmsg"),
    ("reserveSingleSlice", "reserveSingleSlice"),
    ("QuicDispatcher::ProcessPacket", "QuicDispatcher::ProcessPacket"),
])


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


def profile(path):
    tot = 0
    inc = collections.Counter()
    handled_under_read = 0
    for fr, per in stacks(path):
        tot += per
        seen = set()
        for x in fr:
            for name, k in PAT.items():
                if k in x and name not in seen:
                    seen.add(name)
                    inc[name] += per
        # packet handling under the read: a stack that has readFromSocket and, below it, the packet processor
        i = next((n for n, x in enumerate(fr) if PAT["readFromSocket"] in x), None)
        if i is not None and any(("passPayloadToProcessor" in x or "::processPacket(" in x) for x in fr[i + 1:]):
            handled_under_read += per
    if not tot:
        return None
    sh = {k: v / tot for k, v in inc.items()}
    sh["packet handling under readFromSocket"] = handled_under_read / tot
    sh["receive path (readFromSocket minus the packet handling under it)"] = sh.get("readFromSocket", 0.0) - handled_under_read / tot
    return {"worker_cycles": tot, "share": sh}


def main(argv):
    R = argv[0].rstrip("/")
    M = os.path.join(R, "mech")
    out = {"sys": {}, "profile": {}, "loss": {}, "smoke": {}}
    for name in ("mech-sys-s", "mech-sys-shi", "mech-sys-shi-half", "mech-sys-s.first", "mech-sys-shi.first", "mech-sys-shi-half.first"):
        d = os.path.join(M, name)
        if not os.path.isdir(d):
            continue
        legs = chk.latest(d)
        arms = chk.arms_of(d) or sorted(legs)
        od = os.path.join(M, "out-" + name)
        print("\n## %s: syscalls per request (Measured [mechanism]; one traced leg per arm, not scored)\n" % name)
        print("| arm | " + " | ".join(n for n, _ in SYS) + " | EAGAIN share of recvmmsg | UDP datagrams /req (box-wide) | responses in the perf window | valid | "
              "busiest worker (of a CPU) | user instr /req under the tracer | latency max µs | guards (ch, st, ru) |")
        print("|---|" + "---|" * (len(SYS) + 8))
        out["sys"][name] = {}
        for a in arms:
            m = legs.get(a)
            if m is None:
                continue
            st = chk.stat_csv(os.path.join(od, "sys-%s.stat.csv" % m.get("envoy_pid")))
            resp = m.get("responses") or 0
            if not st or not resp:
                print("| %s | no counts |" % a)
                continue
            g = {n: (st.get(k) or 0.0) / resp for n, k in SYS}
            dg = chk.datagrams(m)
            v = m.get("verdict") or {}
            rs = m.get("runtime_start") or {}
            out["sys"][name][a] = dict(g, datagrams=dg, responses=resp, valid=bool(v.get("valid")), reasons=v.get("reasons"),
                                       raw={k: st.get(k) for _, k in SYS}, envoy_pid=m.get("envoy_pid"), binary_sha256=m.get("binary_sha256"),
                                       runtime_start=rs, runtime_end=m.get("runtime_end"), worker_max_busy=m.get("envoy_worker_max_busy"),
                                       instructions_u=(m.get("per_req") or {}).get("instructions_u"), latency_max_us=(m.get("latency_us") or {}).get("max"))
            print("| %s | " % a + " | ".join("%.4f" % g[n] for n, _ in SYS) + " | %.3f | %s | %.1f | %s | %s | %s | %s | %s |" % (
                (g["recvmmsg returning EAGAIN"] / g["recvmmsg"]) if g["recvmmsg"] else 0.0, "-" if dg is None else "%.4f" % dg, resp,
                "yes" if v.get("valid") else "NO: %s" % v.get("reasons"), m.get("envoy_worker_max_busy"),
                "%.0f" % ((m.get("per_req") or {}).get("instructions_u") or 0), (m.get("latency_us") or {}).get("max"),
                "%s, %s, %s" % (rs.get("ch"), rs.get("st"), rs.get("ru"))))
    d = os.path.join(M, "mech-kcg-s")
    if os.path.isdir(d):
        legs = chk.latest(d)
        print("\n## mech-kcg-s: share of worker-thread cycles, inclusive (Measured [mechanism]; one profiled leg per arm, 999 Hz)\n")
        names = list(PAT) + ["packet handling under readFromSocket", "receive path (readFromSocket minus the packet handling under it)"]
        print("| arm | worker samples (period sum) | " + " | ".join(names) + " |")
        print("|---|---|" + "---|" * len(names))
        for a in chk.arms_of(d) or sorted(legs):
            m = legs.get(a)
            p = os.path.join(M, "out-mech-kcg-s", "kcg-%s.folded.gz" % (m or {}).get("envoy_pid"))
            if m is None or not os.path.exists(p):
                print("| %s | no folded stacks |" % a)
                continue
            pr = profile(p)
            if not pr:
                print("| %s | no worker stacks |" % a)
                continue
            out["profile"][a] = dict(pr, valid=bool((m.get("verdict") or {}).get("valid")), envoy_pid=m.get("envoy_pid"),
                                     cycles_per_request=(m.get("per_req") or {}).get("cycles_total"))
            print("| %s | %d | " % (a, pr["worker_cycles"]) + " | ".join("%.2f%%" % (100 * pr["share"].get(n, 0.0)) for n in names) + " |")
        try:
            print("\npost-check: " + open(os.path.join(M, "post-check.txt")).read().strip().replace("\n", "; "))
        except OSError:
            pass
    d = os.path.join(M, "loss-s")
    if os.path.isdir(d):
        legs = chk.latest(d)
        print("\n## loss-s: Envoy's QUIC connection statistics over the whole leg (Exploratory; one untraced leg per arm with the "
              "statistics visitor on; counters are written when a connection closes)\n")
        keys = ["cx_tx_packets_total", "cx_tx_packets_retransmitted_total", "cx_rx_packets_total", "cx_path_degrading_total",
                "cx_tx_amplification_throttling_total"]
        print("| arm | " + " | ".join(keys) + " | completed requests over the leg | retransmitted per 100,000 packets sent | latency max µs | p99 µs | UDP "
              "datagrams /req in the window | valid |")
        print("|---|" + "---|" * (len(keys) + 6))
        for a in chk.arms_of(d) or sorted(legs):
            m = legs.get(a)
            if m is None:
                continue
            le = m.get("sut_stats_leg_end") or {}
            v = {k: le.get(QS + k) for k in keys}
            rq = le.get("http.ingress_http.downstream_rq_completed")
            dg = chk.datagrams(m)
            out["loss"][a] = dict(v, requests=rq, latency_max_us=(m.get("latency_us") or {}).get("max"), datagrams=dg,
                                  valid=bool((m.get("verdict") or {}).get("valid")))
            tx, rt = v["cx_tx_packets_total"], v["cx_tx_packets_retransmitted_total"]
            print("| %s | " % a + " | ".join(str(v[k]) for k in keys) + " | %s | %s | %s | %s | %s | %s |" % (
                rq, "-" if not tx or rt is None else "%.2f" % (1e5 * rt / tx), (m.get("latency_us") or {}).get("max"),
                (m.get("latency_us") or {}).get("p99"), "-" if dg is None else "%.4f" % dg, (m.get("verdict") or {}).get("valid")))
    sd = os.path.join(R, "smoke")
    if os.path.isdir(sd):
        print("\n## smokes: one line per leg\n")
        for name in sorted(os.listdir(sd)):
            legs = chk.latest(os.path.join(sd, name))
            for a, m in legs.items():
                dg = chk.datagrams(m)
                v = m.get("verdict") or {}
                out["smoke"]["%s/%s" % (name, a)] = {"valid": bool(v.get("valid")), "reasons": v.get("reasons"), "datagrams": dg,
                                                      "latency_max_us": (m.get("latency_us") or {}).get("max"),
                                                      "cycles": (m.get("per_req") or {}).get("cycles_total"),
                                                      "worker_max_busy": m.get("envoy_worker_max_busy"), "client_rate_2xx": m.get("client_rate_2xx")}
                print("- %s/%s: valid %s%s; client 2xx/s %.1f of %s; busiest worker %s of a CPU; latency max %s µs; datagrams/req %s" % (
                    name, a, v.get("valid"), "" if v.get("valid") else " (%s)" % "; ".join(str(x)[:110] for x in v.get("reasons") or []),
                    m.get("client_rate_2xx") or 0.0, m.get("target_rps"), m.get("envoy_worker_max_busy"),
                    (m.get("latency_us") or {}).get("max"), "-" if dg is None else "%.4f" % dg))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
