#!/usr/bin/env python3
"""State rules of wave 7 S5 on the box, fixed before the run. A failure stops the chain before any scored leg.

    s5_check.py smoke SMOKE_DIR        one line per leg and per rule; exit 1 when a rule fails
    s5_check.py mech  MECH_DIR NAME    the syscall signature of every arm of mech/NAME (tracepoint counts in
                                       out-NAME); exit 1 when a blocking rule fails, 2 when the counts are missing

smoke (both smokes; every arm of make.ARMS on the run's shape):
  leg       the leg exists, is valid, and Envoy's exit code is 0
  binary    the file the leg's Envoy ran (sha256 of its /proc exe, read by the harness in that leg) equals the
            pin of the arm's build in bins.json; the two builds are two different files
  guards    both runtime guards, read from the admin /runtime of that leg's process at its start and at its
            end, are what the arm's row assumes (official arms: not set)
  errors    every evidence item of the arm that needs no frozen reference holds: no connection created or
            destroyed in the window, no reset, timeout, overflow or protocol error, client rate within 1% of
            the target, the right counters present. An arm of the patched binary failing here is reported
            as a possible patch defect.
  bytes     bytes per request in the window, on all four sides (client to Envoy, Envoy to origin, origin to
            Envoy, Envoy to client), within 0.5% of the official arm's; responses per second at the target

mech (NAME = mech-sys-relay is blocking; the other legs are printed and never block):
  per relayed message (one request = two messages; counts over the 20 s window divided by 2 x responses):
  official, patched-off, write-only   readv returning EAGAIN at least 0.90
  read-only, both-on                  readv returning EAGAIN at most 0.05
  official, patched-off, read-only    epoll_wait with timeout 0 at least 0.80
  write-only, both-on                 epoll_wait with timeout 0 at most 0.05
  every arm                           the counts exist (perf stat wrote them) and the leg is valid
A leg that misses these is not the arm it claims to be."""
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


mk = _load("w7s5_make_for_check", os.path.join(HERE, "make.py"))
BUILD = {n: b for n, b, _, _ in mk.ARMS}
GUARDS = {n: {"sr": -1 if sr is None else int(sr), "wr": -1 if wr is None else int(wr)} for n, _, sr, wr in mk.ARMS}
PATCHED = [n for n, b, _, _ in mk.ARMS if b != "official"]
BYTES = {"p64": [("client to Envoy", mk.RELAY + "downstream_cx_rx_bytes_total"), ("Envoy to origin", "cluster.origin.upstream_cx_tx_bytes_total"),
                 ("origin to Envoy", "cluster.origin.upstream_cx_rx_bytes_total"), ("Envoy to client", mk.RELAY + "downstream_cx_tx_bytes_total")],
         "s": [("client to Envoy", mk.H + "downstream_cx_rx_bytes_total"), ("Envoy to origin", "cluster.origin.upstream_cx_tx_bytes_total"),
               ("origin to Envoy", "cluster.origin.upstream_cx_rx_bytes_total"), ("Envoy to client", mk.H + "downstream_cx_tx_bytes_total")]}


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


def ref_labels(d):
    """Labels of the evidence items that need a frozen reference (unfrozen in a smoke: not judged here)."""
    try:
        exp = json.load(open(os.path.join(d, "experiment.json")))
    except (OSError, ValueError):
        return None
    return {e.get("label") for a in exp.get("arms", []) for e in a.get("evidence") or [] if "ref" in e}


def bytes_per_request(m, stat):
    w = (m.get("sut_stats_window") or {}).get(stat)
    n = m.get("responses_raw")
    return (w / n) if (w is not None and n) else None


def smoke(d, bins):
    legs = latest(d)
    rows, bad = [], []
    if not legs:
        return ["no legs in %s" % d], ["no legs in %s" % d]
    refs = ref_labels(d)
    if refs is None:
        bad.append("no experiment.json in %s" % d)
        refs = set()
    pins = {a: bins[b]["source_sha256"] for a, b in BUILD.items()}
    if len({bins[b]["source_sha256"] for b in bins}) != len(bins):
        bad.append("two builds pin the same file")
    shapes = sorted({k[0] for k in legs})
    for sh in shapes:
        for arm in BUILD:
            m = legs.get((sh, arm))
            if m is None:
                bad.append("%s/%s: no smoke leg" % (sh, arm))
                continue
            pr = m.get("per_req") or {}
            ev = m.get("evidence") or {}
            failed = [i for i in ev.get("items") or [] if not i.get("ok") and i.get("label") not in refs]
            v = (m.get("verdict") or {})
            rows.append("%s/%s: valid %s; Envoy exit %s; sha256 %s; guards at start %s, at end %s; responses in the window %s; "
                        "client 2xx/s %.1f (target %s); cycles u+k per request %s; Envoy busy %s CPUs; evidence items failing "
                        "(reference items left out) %d of %d" % (
                            sh, arm, v.get("valid"), m.get("envoy_exit"), (m.get("binary_sha256") or "-")[:16],
                            json.dumps(m.get("runtime_start"), sort_keys=True), json.dumps(m.get("runtime_end"), sort_keys=True),
                            m.get("responses_raw"), m.get("client_rate_2xx") or 0.0, m.get("target_rps"), pr.get("cycles_total"),
                            m.get("envoy_cpus_run"), len(failed), len(ev.get("items") or [])))
            if not v.get("valid"):
                bad.append("%s/%s: leg not valid: %s" % (sh, arm, v.get("reasons")))
            if m.get("envoy_exit") != 0:
                bad.append("%s/%s: Envoy exit code %s" % (sh, arm, m.get("envoy_exit")))
            if m.get("binary_sha256") != pins[arm]:
                bad.append("%s/%s: ran %s, pin %s" % (sh, arm, m.get("binary_sha256"), pins[arm]))
            for when in ("runtime_start", "runtime_end"):
                if m.get(when) != GUARDS[arm]:
                    bad.append("%s/%s: guards at %s read %s, the arm assumes %s" % (sh, arm, when, m.get(when), GUARDS[arm]))
            if not ev.get("items"):
                bad.append("%s/%s: no evidence items recorded" % (sh, arm))
            for i in failed:
                bad.append("%s/%s: evidence FAILED: %s (value %s; %s)%s" % (
                    sh, arm, i.get("label") or i.get("stat"), i.get("value"), i.get("why"),
                    " [patched binary: possible patch defect]" if arm in PATCHED else ""))
        off = legs.get((sh, "official"))
        for what, stat in BYTES.get(sh, []):
            base = bytes_per_request(off, stat) if off else None
            vals = {a: bytes_per_request(legs[(sh, a)], stat) for a in BUILD if (sh, a) in legs}
            rows.append("%s bytes per request, %s (%s): %s" % (sh, what, stat, ", ".join(
                "%s %s" % (a, "%.3f" % x if x is not None else "-") for a, x in vals.items())))
            for a, x in vals.items():
                if x is None or not base or abs(x / base - 1.0) > 0.005:
                    bad.append("%s/%s: %s bytes per request %s, official %s: over 0.5%% apart%s" % (
                        sh, a, what, x, base, " [patched binary: possible lost or extra bytes]" if a in PATCHED else ""))
    return rows, bad


def mech(mdir, name):
    s1 = _load("w7s1_mech_table_for_s5", os.path.join(HERE, "..", "wave7s1", "mech_table.py"))
    legs = latest(os.path.join(mdir, name))
    rows, bad, missing = [], [], False
    blocking = name == "mech-sys-relay"
    if not legs:
        return ["no legs in %s/%s" % (mdir, name)], ["no legs"], True
    for (sh, arm), m in sorted(legs.items(), key=lambda kv: mk.MECH_ARMS.index(kv[0][1]) if kv[0][1] in mk.MECH_ARMS else 99):
        st = s1.stat_csv(os.path.join(mdir, "out-" + name, "sys-%s.stat.csv" % m.get("envoy_pid")))
        resp = m.get("responses") or 0
        if not st or not resp or not st.get("sys_enter"):
            rows.append("%s/%s: NO tracepoint counts (pid %s, responses %s)" % (sh, arm, m.get("envoy_pid"), resp))
            bad.append("%s/%s: no tracepoint counts" % (sh, arm))
            missing = True
            continue
        n = 2.0 * resp
        g = lambda k: (st.get(k) or 0.0) / n  # noqa: E731
        eag = g("sys_exit_readv") + g("sys_exit_recvfrom") + g("sys_exit_read")
        ep0 = g("sys_enter_epoll_wait") + g("sys_enter_epoll_pwait")
        v = (m.get("verdict") or {})
        rows.append("%s/%s per relayed message (2 per request): all syscalls %.3f; readv %.3f (+recvfrom %.3f), returning EAGAIN "
                    "%.3f; sendto %.3f, writev %.3f; epoll_wait %.3f, with timeout 0 %.3f; epoll_ctl %.4f; guards %s; valid %s%s" % (
                        sh, arm, g("sys_enter"), g("sys_enter_readv"), g("sys_enter_recvfrom"), eag, g("sys_enter_sendto"),
                        g("sys_enter_writev"), g("sys_exit_epoll_wait") + g("sys_exit_epoll_pwait"), ep0, g("sys_enter_epoll_ctl"),
                        json.dumps(m.get("runtime_start"), sort_keys=True), v.get("valid"),
                        "" if v.get("valid") else " (%s)" % v.get("reasons")))
        if arm in GUARDS and (m.get("runtime_start") != GUARDS[arm] or m.get("runtime_end") != GUARDS[arm]):
            bad.append("%s/%s: guards read %s / %s, the arm assumes %s" % (sh, arm, m.get("runtime_start"), m.get("runtime_end"), GUARDS[arm]))
        if not blocking:
            continue
        if not v.get("valid"):
            bad.append("%s/%s: leg not valid: %s" % (sh, arm, v.get("reasons")))
        gd = GUARDS.get(arm) or {}
        if gd.get("sr") == 1:
            if eag > 0.05:
                bad.append("%s/%s: readv returning EAGAIN %.3f per message, the short-read guard is on (at most 0.05)" % (sh, arm, eag))
        elif eag < 0.90:
            bad.append("%s/%s: readv returning EAGAIN %.3f per message, the old read loop makes at least 0.90" % (sh, arm, eag))
        if gd.get("wr") == 1:
            if ep0 > 0.05:
                bad.append("%s/%s: epoll_wait with timeout 0 %.3f per message, the write guard is on (at most 0.05)" % (sh, arm, ep0))
        elif ep0 < 0.80:
            bad.append("%s/%s: epoll_wait with timeout 0 %.3f per message, the old write path makes at least 0.80" % (sh, arm, ep0))
    return rows, bad, missing


def main(argv):
    with open(os.path.join(HERE, "bins.json")) as f:
        bins = json.load(f)
    if argv and argv[0] == "smoke" and len(argv) == 2:
        rows, bad = smoke(argv[1].rstrip("/"), bins)
        tag = "smoke %s" % os.path.basename(argv[1].rstrip("/"))
        rc = 1 if bad else 0
    elif argv and argv[0] == "mech" and len(argv) == 3:
        rows, bad, missing = mech(argv[1].rstrip("/"), argv[2])
        tag = "mech %s" % argv[2]
        rc = 2 if missing else 1 if bad else 0
    else:
        print(__doc__)
        return 2
    print("\n".join(rows))
    for b in bad:
        print("STATE RULE FAILED: " + b)
    print("s5_check %s: %s" % (tag, "OK" if not bad else "FAILED (%d)" % len(bad)))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
