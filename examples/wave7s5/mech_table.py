#!/usr/bin/env python3
"""Wave 7 S5 mechanism legs (non-scored): tracepoint counts per relayed message, per arm and shape.

    python3 examples/wave7s5/mech_table.py MECH_DIR [--json OUT]

MECH_DIR holds NAME/ (the harness's run directory of the legs) and out-NAME/ (the wrapper's output:
sys-<pid>.stat.csv and manifest.txt) for NAME in mech-sys-relay, mech-sys-http and the mech-load-* legs. A leg's
process is found by the PID its record carries. Counts are divided by the leg's responses in the window
(`responses`, the harness's own count scaled to the 20 s perf window) and, per relayed message, by two messages
per request; the tool's window is the same 20 s started a few milliseconds apart (about 1% of timing slack).
Bytes per send call: the bytes Envoy sent on both sides in the harness's window divided by the send calls
(sendto + writev + sendmsg + write) of the perf window, scaled by the two windows' responses. Every figure here
was read under a tracer: the counts are the finding, cycles and busy shares are inflated and are not prices."""
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


s1 = _load("w7s1_mech_table_for_s5t", os.path.join(HERE, "..", "wave7s1", "mech_table.py"))
ORDER = ["official", "patched-off", "read-only", "write-only", "both-on"]
TX = ["tcp.relay.downstream_cx_tx_bytes_total", "http.ingress_http.downstream_cx_tx_bytes_total", "cluster.origin.upstream_cx_tx_bytes_total"]


def latest(d):
    out, sup = {}, set()
    p = os.path.join(d, "legs.jsonl")
    if not os.path.exists(p):
        return out
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        m = json.loads(line)
        if "supersede" in m:
            sup.update(m["supersede"])
        elif m.get("arm") and m.get("leg_id") not in sup:
            out[(m.get("shape"), m["arm"])] = m
    return out


def main(argv):
    M = argv[0].rstrip("/")
    out = []
    names = sorted(n for n in os.listdir(M) if n.startswith("mech-") and os.path.isdir(os.path.join(M, n)))
    for name in names:
        legs = latest(os.path.join(M, name))
        od = os.path.join(M, "out-" + name)
        socks = {}
        mp = os.path.join(od, "manifest.txt")
        if os.path.exists(mp):
            for line in open(mp):
                if " sockets pid=" in line:
                    kv = dict(x.split("=", 1) for x in line.split()[2:] if "=" in x)
                    socks[kv.get("pid")] = kv
        print("\n## %s\n" % name)
        print("| arm / shape | rate, req/s (2xx/s at the client) | per relayed message: all syscalls | readv (+recvfrom) | returning EAGAIN | "
              "sendto | writev + sendmsg + write | epoll_wait | with timeout 0 | epoll_ctl | bytes per send call | Envoy busy under the "
              "tracer (CPUs of 4) | cycles u+k per request under the tracer | leg valid | guards at start / end | MPTCP sockets on the box, "
              "TCP sockets on the listener port, to the origin |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for (sh, arm), m in sorted(legs.items(), key=lambda kv: ORDER.index(kv[0][1]) if kv[0][1] in ORDER else 99):
            pid = m.get("envoy_pid")
            st = s1.stat_csv(os.path.join(od, "sys-%s.stat.csv" % pid))
            resp = m.get("responses") or 0
            v = m.get("verdict") or {}
            rec = {"run": name, "arm": arm, "shape": sh, "pid": pid, "responses_20s": resp, "target_rps": m.get("target_rps"),
                   "client_rate_2xx": m.get("client_rate_2xx"), "valid": v.get("valid"), "reasons": v.get("reasons"),
                   "envoy_cpus_run": m.get("envoy_cpus_run"), "per_req": m.get("per_req"), "runtime_start": m.get("runtime_start"),
                   "runtime_end": m.get("runtime_end"), "binary_sha256": m.get("binary_sha256"), "sockets": socks.get(str(pid)),
                   "evidence_ok": (m.get("evidence") or {}).get("ok"), "evidence_failed": (m.get("evidence") or {}).get("failed"),
                   "client_overflow": m.get("client_overflow"), "client_pending_total": m.get("client_pending_total"),
                   "latency_us": m.get("latency_us")}
            if st and resp:
                n = 2.0 * resp
                g = lambda k: (st.get(k) or 0.0) / n  # noqa: E731
                sends = (st.get("sys_enter_sendto") or 0) + (st.get("sys_enter_writev") or 0) + (st.get("sys_enter_sendmsg") or 0) + (st.get("sys_enter_write") or 0)
                w = m.get("sut_stats_window") or {}
                tx = sum(w.get(k) or 0 for k in TX)
                raw = m.get("responses_raw") or 0
                rec["per_message"] = {
                    "all": g("sys_enter"), "readv": g("sys_enter_readv"), "recvfrom": g("sys_enter_recvfrom"), "read": g("sys_enter_read"),
                    "eagain": g("sys_exit_readv") + g("sys_exit_recvfrom") + g("sys_exit_read"), "sendto": g("sys_enter_sendto"),
                    "writev": g("sys_enter_writev"), "sendmsg": g("sys_enter_sendmsg"), "write": g("sys_enter_write"),
                    "epoll_wait": g("sys_exit_epoll_wait") + g("sys_exit_epoll_pwait"),
                    "epoll_wait_timeout0": g("sys_enter_epoll_wait") + g("sys_enter_epoll_pwait"), "epoll_ctl": g("sys_enter_epoll_ctl"),
                    "close": g("sys_enter_close"), "accept4": g("sys_enter_accept4")}
                rec["bytes_per_send_call"] = (tx / raw) / (sends / resp) if (raw and sends) else None
                rec["tracepoints_raw"] = st
                p = rec["per_message"]
                sk = rec["sockets"] or {}
                print("| %s / %s | %s (%.0f) | %.3f | %.3f (+%.3f) | %.3f | %.3f | %.3f | %.3f | %.3f | %.4f | %s | %s | %s | %s%s | %s / %s | %s, %s, %s |" % (
                    arm, sh, m.get("target_rps"), m.get("client_rate_2xx") or 0, p["all"], p["readv"], p["recvfrom"], p["eagain"], p["sendto"],
                    p["writev"] + p["sendmsg"] + p["write"], p["epoll_wait"], p["epoll_wait_timeout0"], p["epoll_ctl"],
                    "%.1f" % rec["bytes_per_send_call"] if rec["bytes_per_send_call"] else "-", m.get("envoy_cpus_run"),
                    "%.1fk" % (((m.get("per_req") or {}).get("cycles_total") or 0) / 1e3), v.get("valid"),
                    "" if v.get("valid") else " (%s)" % "; ".join(str(x) for x in (v.get("reasons") or [])[:3]),
                    json.dumps(m.get("runtime_start"), sort_keys=True), json.dumps(m.get("runtime_end"), sort_keys=True),
                    sk.get("mptcp_sockets", "-"), sk.get("tcp_established_on_10110", "-"), sk.get("tcp_established_to_origin", "-")))
            else:
                print("| %s / %s | %s | NO tracepoint counts (pid %s) |" % (arm, sh, m.get("target_rps"), pid))
            out.append(rec)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
