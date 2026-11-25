#!/usr/bin/env python3
"""State rules of wave 8 W8-2 on the box, fixed before the run.

    w2_check.py smoke SMOKE_DIR        one line per leg and per rule. Exit 0: every rule holds; 3: a load gate
                                       failed in at least one leg and no leg failed anything that is not
                                       explained by load; 1: another rule failed
    w2_check.py mech  MECH_DIR NAME    the syscall signature of every arm of mech/NAME (tracepoint counts in
                                       out-NAME). Exit 0 pass; 1 a blocking rule failed; 2 counts are missing

smoke (every arm of the config, on the run's one shape):
  leg       the leg exists, is valid, and Envoy's exit code is 0
  binary    the file the leg's Envoy ran (sha256 of its /proc exe, read by the harness in that leg) equals the
            pin of the arm's build in bins.json
  guards    the three runtime guards, read from the admin /runtime of that leg's process at its start and at
            its end, are what the arm's row assumes (official arms: not set)
  errors    every evidence item of the arm that needs no frozen reference holds (responses, protocol, no
            connection created or destroyed in the window, no reset, timeout, overflow or protocol error, no
            dropped datagram in Envoy or in the kernel, client rate within 1% of the target)
  bytes     HTTP/3 arms: bytes per request on Envoy-to-origin, origin-to-Envoy and Envoy-to-client within 0.5%
            of h3-official's; UDP datagrams per request (the kernel's box-wide count over the window, both
            directions) within 1% of h3-official's. The connection manager does not count the bytes read from a
            QUIC connection, so the datagram count stands for the client-to-Envoy segment.
  load      a leg whose verdict names a load gate (client rate, client headroom, pending requests, client
            overflow, the worker-share gate) is a LOAD failure, with whatever else failed in that leg: an
            overloaded leg fails other items as a consequence. Wave 7's rule R3 then halves the rate, once.
  printed, not judged: latency p99 and maximum, UDP datagrams per request to four decimals.

mech (blocking on shape s: NAME = mech-sys-s; on s-hi only the two EAGAIN rules block, and only the s-hi run):
  per request (counts over the 20 s tracer window divided by the leg's responses in the perf window):
  h3-official, h3-off, h3-reuse-on   of all recvmmsg, the share returning EAGAIN is 0.40 to 0.55 (the old loop:
                                     every read event ends with a call that finds nothing, so about half)
                                     AMENDED 2026-11-24 13:50Z. As first shipped this rule read "recvmmsg 3.6 to
                                     4.4, of which returning EAGAIN 1.8 to 2.2" (the plan's 4.0 with 2.0, S2's one
                                     leg). The first chain stopped on it: the OFFICIAL binary itself read 3.41 to
                                     3.48 with 1.69 (two datagrams of one worker's connections can share a read
                                     event, so calls per request depend on where the 16 connections land). The
                                     absolute band was a fault of the check, not a property of an arm; the share
                                     is what the arm table states. No scored leg had run.
  h3-stop-on, h3-both-on             recvmmsg at most 2.2, returning EAGAIN at most 0.1
  every HTTP/3 arm                   sendmsg + sendmmsg per request within 2% of h3-off's; UDP datagrams per
                                     request (box-wide) within 1% of h3-off's; the leg valid; guards as the arm's
  on s-hi: the same share rule for the old-path arms; the patched arms' EAGAIN at most 0.1 per request.
A leg that misses these is not the arm it claims to be."""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOAD_REASONS = ("client headroom", "client pending total", "Envoy load uneven", "misses target", "client overflow",
                "no achieved-rate")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mk = _load("w8w2_make_for_check", os.path.join(HERE, "make.py"))
PIN = {a: mk.BINS[mk.ARMS[a][0]]["source_sha256"] for a in mk.ARMS}
OLD = ("h3-official", "h3-official-A2", "h3-off", "h3-reuse-on")
NEW = ("h3-stop-on", "h3-both-on")


def latest(d):
    out, sup = {}, set()
    p = os.path.join(d, "legs.jsonl")
    if not os.path.exists(p):
        return out
    rows = []
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        m = json.loads(line)
        if "supersede" in m:
            sup.update(m["supersede"])
        elif m.get("arm"):
            rows.append(m)
    for m in rows:
        if m.get("leg_id") not in sup and not m.get("superseded"):
            out[m["arm"]] = m
    return out


def arms_of(d):
    try:
        return [a["name"] for a in json.load(open(os.path.join(d, "experiment.json")))["arms"]]
    except (OSError, ValueError, KeyError):
        return None


def ref_labels(d):
    try:
        exp = json.load(open(os.path.join(d, "experiment.json")))
    except (OSError, ValueError):
        return set()
    return {e.get("label") for a in exp.get("arms", []) for e in a.get("evidence") or [] if "ref" in e}


def per_request(m, stat):
    w = (m.get("sut_stats_window") or {}).get(stat)
    n = m.get("responses_raw")
    return (w / n) if (w is not None and n) else None


def datagrams(m):
    d = ((m.get("kernel_net") or {}).get("d") or {}).get("UdpInDatagrams")
    n = m.get("responses_raw")
    return (d / n) if (d is not None and n) else None


def stat_csv(p):
    """{event name: count}; a second row of the same event (a filtered one) is NAME#2."""
    out, seen = {}, {}
    if not os.path.exists(p):
        return out
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


def smoke(d):
    legs = latest(d)
    arms = arms_of(d)
    rows, load, other = [], [], []
    if not legs or not arms:
        return ["no legs in %s" % d], [], ["no legs in %s" % d]
    refs = ref_labels(d)
    for arm in arms:
        m = legs.get(arm)
        if m is None:
            other.append("%s: no smoke leg" % arm)
            continue
        pr, ev, v, lat = m.get("per_req") or {}, m.get("evidence") or {}, m.get("verdict") or {}, m.get("latency_us") or {}
        failed = [i for i in ev.get("items") or [] if not i.get("ok") and i.get("label") not in refs]
        dg = datagrams(m)
        rows.append("%s/%s: valid %s; Envoy exit %s; sha256 %s; guards at start %s, at end %s; responses in the window %s; client "
                    "2xx/s %.1f (target %s); cycles u+k per request %s; user instructions per request %s; Envoy busy %s CPUs, "
                    "busiest worker %s of a CPU (share %s); client headroom %s, pending %s; latency p99 %s us, max %s us; UDP "
                    "datagrams per request (box-wide) %s; evidence items failing (reference items left out) %d of %d" % (
                        m.get("shape"), arm, v.get("valid"), m.get("envoy_exit"), (m.get("binary_sha256") or "-")[:16],
                        json.dumps(m.get("runtime_start"), sort_keys=True), json.dumps(m.get("runtime_end"), sort_keys=True),
                        m.get("responses_raw"), m.get("client_rate_2xx") or 0.0, m.get("target_rps"),
                        None if pr.get("cycles_total") is None else round(pr["cycles_total"]),
                        None if pr.get("instructions_u") is None else round(pr["instructions_u"]),
                        m.get("envoy_cpus_run"), m.get("envoy_worker_max_busy"), m.get("envoy_worker_max_share"),
                        None if m.get("client_headroom") is None else round(m["client_headroom"], 3), m.get("client_pending_total"),
                        lat.get("p99"), lat.get("max"), None if dg is None else "%.4f" % dg, len(failed), len(ev.get("items") or [])))
        reasons = [str(r) for r in v.get("reasons") or []]
        is_load = any(k in r for r in reasons for k in LOAD_REASONS) or (
            bool(failed) and all(str(i.get("label") or "").startswith("client: 2xx responses per second") for i in failed))
        mine = []
        if not v.get("valid"):
            mine.append("leg not valid: %s" % reasons)
        if m.get("envoy_exit") != 0:
            mine.append("Envoy exit code %s" % m.get("envoy_exit"))
        if not ev.get("items"):
            mine.append("no evidence items recorded")
        for i in failed:
            mine.append("evidence FAILED: %s (value %s; %s)" % (i.get("label") or i.get("stat"), i.get("value"), i.get("why")))
        (load if is_load else other).extend("%s: %s" % (arm, x) for x in mine)
        # the pin and the guards are never a matter of load
        if m.get("binary_sha256") != PIN[arm]:
            other.append("%s: ran %s, pin %s" % (arm, m.get("binary_sha256"), PIN[arm]))
        for when in ("runtime_start", "runtime_end"):
            if m.get(when) != mk.GUARDS[arm]:
                other.append("%s: guards at %s read %s, the arm assumes %s" % (arm, when, m.get(when), mk.GUARDS[arm]))
    base = legs.get("h3-official")
    if base is not None and not load:
        for what, stat in mk.BYTES:
            b0 = per_request(base, stat)
            vals = {a: per_request(legs[a], stat) for a in arms if a in legs and mk.ARMS[a][1]}
            rows.append("bytes per request, %s (%s): %s" % (what, stat, ", ".join("%s %s" % (a, "%.3f" % x if x is not None else "-") for a, x in vals.items())))
            for a, x in vals.items():
                if x is None or not b0 or abs(x / b0 - 1.0) > 0.005:
                    other.append("%s: %s bytes per request %s, h3-official %s: over 0.5%% apart" % (a, what, x, b0))
        d0 = datagrams(base)
        vals = {a: datagrams(legs[a]) for a in arms if a in legs and mk.ARMS[a][1]}
        rows.append("UDP datagrams per request, box-wide, over the window: %s" % ", ".join("%s %s" % (a, "%.4f" % x if x is not None else "-") for a, x in vals.items()))
        for a, x in vals.items():
            if x is None or not d0 or abs(x / d0 - 1.0) > 0.01:
                other.append("%s: UDP datagrams per request %s, h3-official %s: over 1%% apart" % (a, x, d0))
    return rows, load, other


def mech(mdir, name):
    d = os.path.join(mdir, name)
    legs = latest(d)
    arms = arms_of(d) or sorted(legs)
    rows, bad, missing = [], [], False
    on_s = name == "mech-sys-s"
    if not legs:
        return ["no legs in %s" % d], ["no legs"], True
    got = {}
    for arm in arms:
        m = legs.get(arm)
        if m is None:
            bad.append("%s: no leg" % arm)
            missing = True
            continue
        st = stat_csv(os.path.join(mdir, "out-" + name, "sys-%s.stat.csv" % m.get("envoy_pid")))
        resp = m.get("responses") or 0
        if not st or not resp or not st.get("sys_enter") or "sys_exit_recvmmsg" not in st:
            rows.append("%s: NO tracepoint counts (pid %s, responses %s)" % (arm, m.get("envoy_pid"), resp))
            bad.append("%s: no tracepoint counts" % arm)
            missing = True
            continue
        g = lambda k: (st.get(k) or 0.0) / resp  # noqa: E731
        v = m.get("verdict") or {}
        x = {"recvmmsg": g("sys_enter_recvmmsg"), "eagain": g("sys_exit_recvmmsg"), "sends": g("sys_enter_sendmsg") + g("sys_enter_sendmmsg"),
             "datagrams": datagrams(m), "valid": bool(v.get("valid")), "all": g("sys_enter")}
        got[arm] = x
        pr, lat = m.get("per_req") or {}, m.get("latency_us") or {}
        rows.append("%s/%s per request: all syscalls %.3f; recvmmsg %.4f, returning EAGAIN %.4f (share %.3f); recvmsg %.4f; sendmsg "
                    "%.4f, sendmmsg %.4f; readv %.3f, writev %.3f, sendto %.3f; epoll_wait %.3f, with timeout 0 %.3f; UDP datagrams "
                    "(box-wide) %s; user instructions (under the tracer) %s; latency max %s us; guards %s; valid %s%s" % (
                        m.get("shape"), arm, x["all"], x["recvmmsg"], x["eagain"], (x["eagain"] / x["recvmmsg"]) if x["recvmmsg"] else 0.0,
                        g("sys_enter_recvmsg"), g("sys_enter_sendmsg"), g("sys_enter_sendmmsg"), g("sys_enter_readv"), g("sys_enter_writev"),
                        g("sys_enter_sendto"), g("sys_exit_epoll_wait") + g("sys_exit_epoll_pwait"),
                        g("sys_enter_epoll_wait") + g("sys_enter_epoll_pwait"), "-" if x["datagrams"] is None else "%.4f" % x["datagrams"],
                        None if pr.get("instructions_u") is None else round(pr["instructions_u"]), lat.get("max"),
                        json.dumps(m.get("runtime_start"), sort_keys=True), v.get("valid"), "" if v.get("valid") else " (%s)" % v.get("reasons")))
        if m.get("runtime_start") != mk.GUARDS[arm] or m.get("runtime_end") != mk.GUARDS[arm]:
            bad.append("%s: guards read %s / %s, the arm assumes %s" % (arm, m.get("runtime_start"), m.get("runtime_end"), mk.GUARDS[arm]))
        if m.get("binary_sha256") != PIN[arm]:
            bad.append("%s: ran %s, pin %s" % (arm, m.get("binary_sha256"), PIN[arm]))
        if not mk.ARMS[arm][1]:
            continue
        share = (x["eagain"] / x["recvmmsg"]) if x["recvmmsg"] else 0.0
        if arm in NEW:
            if x["eagain"] > 0.1:
                bad.append("%s: recvmmsg returning EAGAIN %.4f per request, the stop guard is on (at most 0.1)" % (arm, x["eagain"]))
            if on_s and x["recvmmsg"] > 2.2:
                bad.append("%s: recvmmsg %.4f per request, the stop guard is on (at most 2.2)" % (arm, x["recvmmsg"]))
        else:
            # AMENDED 2026-11-24 13:50Z, after the first chain stopped here and before any scored leg (see the docstring)
            if not 0.40 <= share <= 0.55:
                bad.append("%s: EAGAIN share of recvmmsg %.3f (%.4f of %.4f per request); the old loop makes about half (0.40 to 0.55)" % (
                    arm, share, x["eagain"], x["recvmmsg"]))
        if on_s and not x["valid"]:
            bad.append("%s: leg not valid: %s" % (arm, v.get("reasons")))
    ref = got.get("h3-off")
    for arm, x in got.items():
        if not mk.ARMS[arm][1] or ref is None:
            continue
        notes = []
        if not ref["sends"] or abs(x["sends"] / ref["sends"] - 1.0) > 0.02:
            notes.append("%s: sendmsg + sendmmsg %.4f per request, h3-off %.4f: over 2%% apart" % (arm, x["sends"], ref["sends"]))
        if x["datagrams"] is None or not ref["datagrams"] or abs(x["datagrams"] / ref["datagrams"] - 1.0) > 0.01:
            notes.append("%s: UDP datagrams %s per request, h3-off %s: over 1%% apart" % (arm, x["datagrams"], ref["datagrams"]))
        if on_s:
            bad += notes
        else:
            rows += ["NOTE (not blocking on s-hi): " + n for n in notes]
    return rows, bad, missing


def main(argv):
    if argv and argv[0] == "smoke" and len(argv) == 2:
        rows, load, other = smoke(argv[1].rstrip("/"))
        print("\n".join(rows))
        for b in load:
            print("LOAD GATE FAILED: " + b)
        for b in other:
            print("STATE RULE FAILED: " + b)
        rc = 1 if other else 3 if load else 0
        print("w2_check smoke %s: %s" % (os.path.basename(argv[1].rstrip("/")), {0: "OK", 3: "LOAD (%d)" % len(load), 1: "FAILED (%d)" % len(other)}[rc]))
        return rc
    if argv and argv[0] == "mech" and len(argv) == 3:
        rows, bad, missing = mech(argv[1].rstrip("/"), argv[2])
        print("\n".join(rows))
        for b in bad:
            print("STATE RULE FAILED: " + b)
        print("w2_check mech %s: %s" % (argv[2], "OK" if not bad else "FAILED (%d)" % len(bad)))
        return 2 if missing else 1 if bad else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
