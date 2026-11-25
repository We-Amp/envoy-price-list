#!/usr/bin/env python3
"""State rules of wave 8 W8-1, fixed before any leg ran on the box.

    w1_check.py smoke SMOKE_DIR        one line per leg and per rule. Exit 0: every rule holds; 3: only load
                                       failures; 1: another rule failed
    w1_check.py pick  SMOKE_DIR        prints the config to run next for this smoke's run: the same variant when
                                       every shape is healthy; the variant with a shape at half rate when the
                                       failures on that shape are all load failures (rule R3; one step, never from
                                       a variant that already halved that shape); `fail` otherwise
    w1_check.py mech  MECH_DIR NAME    tracepoint counts of mech/NAME per request and per MiB of body. Exit 0
                                       pass; 1 a blocking rule failed; 2 counts are missing
    w1_check.py sig   MECH_DIR NAME    THE SIGNATURE, from the call-graph legs mech/NAME (b1m): the share of
                                       worker-thread cycles whose leaf frame is in libc (the body copy). Exit 0
                                       pass; 1 a rule failed; 2 a profile is missing

smoke (every arm, every shape of the config):
  leg       the leg exists, is valid, Envoy's exit code is 0
  binary    sha256 of the file the leg's Envoy ran = the pin of the arm's build
  guards    the three runtime guards at the leg's start and end as the arm's row assumes (official: not set)
  errors    every evidence item that needs no frozen reference holds
  bytes     per shape, per wire format (the arm's reference arm in make.REF): bytes per request on all four
            segments within 0.5% of the reference arm's
  load      a leg whose verdict names a load gate (client rate, headroom, pending, overflow, worker shares, a
            side service over its CPU share) or whose only failing evidence is the client's rate or one of the
            origin's own counts is a LOAD failure, with whatever else failed in that leg.
mech (blocking): every leg present and valid, guards and pin as the arm's, tracepoint counts present, bytes per
  request on the four segments within 0.5% across the arms of a wire format. NOT blocking, printed as NOTE: how
  writev calls and iovecs of off-* compare with the official arm's, and of frag-on-* with off-*. The patch is
  expected to change the number and size of writes; in which direction on this box is what the leg records.
sig (blocking for the patch's scored runs; bands are ratios against what the OFFICIAL binary reads in this
  visit, nothing is taken from another host):
  official-ch8k  libc leaf share at least 1.0% of worker cycles (the copy exists on this rig; S2 read 5.5%)
  off-ch8k       0.5 to 2.0 times the official arm's share (the old path in the rebuilt binary)
  frag-on-ch8k   at most 0.5 times the official arm's share (the copy is gone)
A leg that misses these is not the arm it claims to be."""
import gzip
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOAD_REASONS = ("client headroom", "client pending", "Envoy load uneven", "misses target", "client overflow", "no achieved-rate",
                "side service stream_origin used", "side service origin used", "achieved rate", "rate ")
LOAD_EVIDENCE = ("client: 2xx responses per second", "origin:")
MIB = 1048576.0


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mk = _load("w8w1_make_for_check", os.path.join(HERE, "make.py"))


def run_of(name):
    """Config name -> (run letter, variant name): smoke-a-h64 -> (a, a-h64)."""
    for p in ("smoke-", "mech-sys-", "mech-kcg-"):
        if name.startswith(p):
            name = name[len(p):]
    name = name.split(".")[0]
    return name[0], name


def latest(d):
    out, sup, rows = {}, set(), []
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
        elif m.get("arm"):
            rows.append(m)
    for m in rows:
        if m.get("leg_id") not in sup and not m.get("superseded"):
            out[(m.get("shape"), m["arm"])] = m
    return out


def exp_of(d):
    try:
        return json.load(open(os.path.join(d, "experiment.json")))
    except (OSError, ValueError):
        return None


def per_request(m, stat):
    w = (m.get("sut_stats_window") or {}).get(stat)
    n = m.get("responses_raw")
    return (w / n) if (w is not None and n) else None


def problems(m, refs):
    """(hard, load) reasons a leg is not usable."""
    hard, load = [], []
    v, ev = m.get("verdict") or {}, m.get("evidence") or {}
    reasons = [str(r) for r in v.get("reasons") or []]
    failed = [i for i in ev.get("items") or [] if not i.get("ok") and i.get("label") not in refs]
    is_load = any(k in r for r in reasons for k in LOAD_REASONS)
    if not v.get("valid"):
        for r in reasons or ["?"]:
            (load if any(k in r for k in LOAD_REASONS) else hard).append("leg not valid: %s" % r)
    if m.get("envoy_exit") != 0:
        hard.append("Envoy exit code %s" % m.get("envoy_exit"))
    if not ev.get("items"):
        hard.append("no evidence items recorded")
    for i in failed:
        lab = str(i.get("label") or i.get("stat"))
        txt = "evidence FAILED: %s (value %s; %s)" % (lab, i.get("value"), i.get("why"))
        (load if (is_load or lab.startswith(LOAD_EVIDENCE)) else hard).append(txt)
    if is_load and hard:
        # an overloaded leg fails other items as a consequence
        load, hard = load + hard, []
    return hard, load


def bytes_rule(legs, run, shapes, arms):
    rows, bad = [], []
    for sh in shapes:
        for what, stat in mk.BYTES:
            vals = {a: per_request(legs[(sh, a)], stat) for a in arms if (sh, a) in legs}
            rows.append("bytes per request, %s, %s: %s" % (sh, what, ", ".join("%s %s" % (a, "%.2f" % x if x is not None else "-") for a, x in vals.items())))
            for a, x in vals.items():
                ref = mk.REF[mk.ARMS[run][a][2]]
                b0 = vals.get(ref)
                if ref not in vals:
                    continue
                if x is None or not b0 or abs(x / b0 - 1.0) > 0.005:
                    bad.append("%s/%s: %s bytes per request %s, %s %s: over 0.5%% apart" % (sh, a, what, x, ref, b0))
    return rows, bad


def smoke(d):
    """rows, {shape: (hard, load)}"""
    legs, exp = latest(d), exp_of(d)
    if not legs or not exp:
        return ["no legs in %s" % d], {"?": (["no legs in %s" % d], [])}
    run, _ = run_of(exp["name"])
    arms = [a["name"] for a in exp["arms"]]
    refs = {e.get("label") for a in exp["arms"] for e in a.get("evidence") or [] if "ref" in e}
    rows, res = [], {}
    for s in exp["shapes"]:
        sh = s["name"]
        hard, load = [], []
        for arm in arms:
            m = legs.get((sh, arm))
            if m is None:
                hard.append("%s: no smoke leg" % arm)
                continue
            pr, ev, v, lat = m.get("per_req") or {}, m.get("evidence") or {}, m.get("verdict") or {}, m.get("latency_us") or {}
            so = ((m.get("side_services") or {}).get("stream_origin") or (m.get("side_services") or {}).get("origin") or {})
            rows.append("%s/%s: valid %s; exit %s; sha256 %s; guards %s / %s; responses %s; 2xx/s %.1f (target %s); cycles u+k /req %s "
                        "(user %s, kernel %s); user instr /req %s; Envoy busy %s CPUs, busiest worker %s (share %s); client headroom %s, "
                        "pending %s; origin CPU %s of its set; p50 %s p99 %s max %s us; memory allocated at the window's end %s; evidence "
                        "failing (references left out) %d of %d" % (
                            sh, arm, v.get("valid"), m.get("envoy_exit"), (m.get("binary_sha256") or "-")[:12],
                            json.dumps(m.get("runtime_start"), sort_keys=True), json.dumps(m.get("runtime_end"), sort_keys=True),
                            m.get("responses_raw"), m.get("client_rate_2xx") or 0.0, m.get("target_rps"),
                            None if pr.get("cycles_total") is None else round(pr["cycles_total"]),
                            None if pr.get("cycles_u") is None else round(pr["cycles_u"]),
                            None if pr.get("cycles_k") is None else round(pr["cycles_k"]),
                            None if pr.get("instructions_u") is None else round(pr["instructions_u"]),
                            m.get("envoy_cpus_run"), m.get("envoy_worker_max_busy"), m.get("envoy_worker_max_share"),
                            None if m.get("client_headroom") is None else round(m["client_headroom"], 3), m.get("client_pending_total"),
                            so.get("busy_of_set"), lat.get("p50"), lat.get("p99"), lat.get("max"),
                            (m.get("sut_stats_end") or {}).get("server.memory_allocated"),
                            len([i for i in ev.get("items") or [] if not i.get("ok") and i.get("label") not in refs]), len(ev.get("items") or [])))
            h, l_ = problems(m, refs)
            hard += ["%s: %s" % (arm, x) for x in h]
            load += ["%s: %s" % (arm, x) for x in l_]
            if m.get("binary_sha256") != mk.PIN[run][arm]:
                hard.append("%s: ran %s, pin %s" % (arm, m.get("binary_sha256"), mk.PIN[run][arm]))
            for when in ("runtime_start", "runtime_end"):
                if m.get(when) != mk.GUARDS[run][arm]:
                    hard.append("%s: guards at %s read %s, the arm assumes %s" % (arm, when, m.get(when), mk.GUARDS[run][arm]))
        if not load:
            r2, b2 = bytes_rule(legs, run, [sh], arms)
            rows += r2
            hard += b2
        res[sh] = (hard, load)
    return rows, res


def pick(d):
    exp = exp_of(d)
    if not exp:
        return "fail"
    run, var = run_of(exp["name"])
    _, res = smoke(d)
    shapes = mk.SHAPES[run]
    if any(res.get(sh, (["?"], []))[0] for sh in shapes):
        return "fail"
    halve = [bool(res[sh][1]) for sh in shapes]
    if not any(halve):
        return var
    if var != run:
        return "fail"  # one step only
    if len(shapes) == 1:
        return run + "-half"
    return run + {(True, False): "-h64", (False, True): "-h1m", (True, True): "-hh"}[tuple(halve)]


def stat_csv(p):
    """[(event name, count)] in the order perf printed them."""
    out = []
    if not os.path.exists(p):
        return out
    for line in open(p):
        f = line.strip().split(",")
        if len(f) < 3 or not f[2] or line.startswith("#"):
            continue
        try:
            out.append((f[2].split(":")[-1], float(f[0])))
        except ValueError:
            continue
    return out


def counts(rows, resp):
    """Per-request figures of one traced leg, or None when the rows are not mech-inner.sh's 33."""
    wv = [v for k, v in rows if k == "sys_enter_writev"]
    rv = [v for k, v in rows if k == "sys_enter_readv"]
    if len(rows) != 33 or len(wv) != 20 or len(rv) != 2 or not resp:
        return None
    g = lambda name: next((v for k, v in rows if k == name), 0.0) / resp  # noqa: E731
    hist = wv[1:17]
    iov = sum((i + 1) * n for i, n in enumerate(hist))
    up, up1 = wv[18], wv[19]
    x = {"all": g("sys_enter"), "writev": wv[0] / resp, "iovecs": iov / resp, "writev_over_16": wv[17] / resp,
         "writev_origin_side": up / resp, "writev_origin_side_vlen1": up1 / resp,
         "writev_client_side": (wv[0] - up) / resp,
         # exact when every origin-side writev has one iovec (the request head); else a lower bound is printed too
         "iovecs_client_side": (iov - up1) / resp if up1 == up else None,
         "iovecs_client_side_min": (iov - up1 - 16 * (up - up1)) / resp,
         "readv": rv[0] / resp, "readv_origin_side": rv[1] / resp, "readv_eagain": g("sys_exit_readv"),
         "read": g("sys_enter_read"), "recvfrom": g("sys_enter_recvfrom"), "write": g("sys_enter_write"), "sendto": g("sys_enter_sendto"),
         "sendmsg": g("sys_enter_sendmsg"), "epoll_wait": g("sys_exit_epoll_wait"), "epoll_wait_t0": g("sys_enter_epoll_wait"),
         "epoll_ctl": g("sys_enter_epoll_ctl"), "vlen_hist": [n / resp for n in hist]}
    return x


def mech_rows(mdir, name):
    """{(shape, arm): {leg, counts}} of one traced config."""
    d = os.path.join(mdir, name)
    legs, exp = latest(d), exp_of(d)
    out = {}
    for (sh, arm), m in legs.items():
        st = stat_csv(os.path.join(mdir, "out-" + name, "sys-%s.stat.csv" % m.get("envoy_pid")))
        out[(sh, arm)] = {"leg": m, "counts": counts(st, m.get("responses") or 0), "rows": len(st)}
    return out, exp


def mech(mdir, name):
    got, exp = mech_rows(mdir, name)
    rows, bad, missing = [], [], False
    if not got or not exp:
        return ["no legs in %s/%s" % (mdir, name)], ["no legs"], True
    run, _ = run_of(exp["name"])
    arms = [a["name"] for a in exp["arms"]]
    body = {s["name"]: int(s["body_bytes"]) for s in exp["shapes"]}
    legs = {k: v["leg"] for k, v in got.items()}
    for s in exp["shapes"]:
        sh = s["name"]
        per_mib = MIB / body[sh]
        for arm in arms:
            e = got.get((sh, arm))
            if e is None:
                bad.append("%s/%s: no leg" % (sh, arm))
                missing = True
                continue
            m, x = e["leg"], e["counts"]
            v = m.get("verdict") or {}
            if m.get("runtime_start") != mk.GUARDS[run][arm] or m.get("runtime_end") != mk.GUARDS[run][arm]:
                bad.append("%s/%s: guards read %s / %s, the arm assumes %s" % (sh, arm, m.get("runtime_start"), m.get("runtime_end"), mk.GUARDS[run][arm]))
            if m.get("binary_sha256") != mk.PIN[run][arm]:
                bad.append("%s/%s: ran %s, pin %s" % (sh, arm, m.get("binary_sha256"), mk.PIN[run][arm]))
            if not v.get("valid"):
                bad.append("%s/%s: leg not valid: %s" % (sh, arm, v.get("reasons")))
            if x is None:
                rows.append("%s/%s: NO tracepoint counts (pid %s, %d rows, responses %s)" % (sh, arm, m.get("envoy_pid"), e["rows"], m.get("responses")))
                bad.append("%s/%s: no tracepoint counts" % (sh, arm))
                missing = True
                continue
            ic = x["iovecs_client_side"]
            rows.append("%s/%s per request [per MiB of body]: writev %.3f [%.2f], client side %.3f [%.2f], origin side %.3f (one iovec: %.3f); "
                        "iovecs in all %.2f [%.1f], client side %s [%s] (at least %.2f); iovecs per client-side writev %s; body bytes per "
                        "client-side writev %s; readv %.2f [%.1f] (origin side %.2f, returning EAGAIN %.2f); read %.2f, recvfrom %.2f, write "
                        "%.2f, sendto %.2f, sendmsg %.2f; epoll_wait %.2f (timeout 0: %.2f); epoll_ctl %.3f; all syscalls %.2f; valid %s%s" % (
                            sh, arm, x["writev"], x["writev"] * per_mib, x["writev_client_side"], x["writev_client_side"] * per_mib,
                            x["writev_origin_side"], x["writev_origin_side_vlen1"], x["iovecs"], x["iovecs"] * per_mib,
                            "-" if ic is None else "%.2f" % ic, "-" if ic is None else "%.1f" % (ic * per_mib), x["iovecs_client_side_min"],
                            "-" if not (ic and x["writev_client_side"]) else "%.2f" % (ic / x["writev_client_side"]),
                            "-" if not x["writev_client_side"] else "%.0f" % (body[sh] / x["writev_client_side"]),
                            x["readv"], x["readv"] * per_mib, x["readv_origin_side"], x["readv_eagain"], x["read"], x["recvfrom"], x["write"],
                            x["sendto"], x["sendmsg"], x["epoll_wait"], x["epoll_wait_t0"], x["epoll_ctl"], x["all"], v.get("valid"),
                            "" if v.get("valid") else " (%s)" % v.get("reasons")))
            rows.append("%s/%s writev per request by iovec count 1..16: %s; more than 16: %.4f" % (
                sh, arm, " ".join("%.3f" % n for n in x["vlen_hist"]), x["writev_over_16"]))
        r2, b2 = bytes_rule(legs, run, [sh], arms)
        rows += r2
        bad += b2
        # notes, not rules
        pairs = [(a, b) for a, b in (("off-ch8k", "official-ch8k"), ("frag-on-ch8k", "off-ch8k"), ("frag-on", "off"), ("h2in-ngx", "cl-ngx"))
                 if (sh, a) in got and (sh, b) in got and got[(sh, a)]["counts"] and got[(sh, b)]["counts"]]
        for a, b in pairs:
            xa, xb = got[(sh, a)]["counts"], got[(sh, b)]["counts"]
            rat = lambda k: (xa[k] / xb[k]) if (xa.get(k) and xb.get(k)) else float("nan")  # noqa: E731
            rows.append("NOTE (not a rule) %s: %s over %s: client-side writev x%.3f, client-side iovecs x%.3f, readv x%.3f, all syscalls x%.3f" % (
                sh, a, b, rat("writev_client_side"), rat("iovecs_client_side"), rat("readv"), rat("all")))
    return rows, bad, missing


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


def copy_share(path):
    """(share of worker-thread cycles whose leaf frame is in libc, top callers, worker period, user share)."""
    tot = libc = user = 0
    callers = {}
    for fr, per in stacks(path):
        tot += per
        if fr and not fr[-1].endswith("_[k]"):
            user += per
        if fr and fr[-1] == "[libc.so.6]":
            libc += per
            k = " <- ".join(x.split("(")[0][-56:] for x in fr[-2:-4:-1])
            callers[k] = callers.get(k, 0) + per
    if not tot:
        return None
    top = sorted(callers.items(), key=lambda kv: -kv[1])[:3]
    return {"libc_leaf_share": libc / float(tot), "user_share": user / float(tot), "worker_period": tot,
            "callers": [(k, v / float(tot)) for k, v in top]}


SIG_MIN_OFFICIAL, SIG_OFF_BAND, SIG_ON_MAX = 0.010, (0.5, 2.0), 0.5


def sig(mdir, name):
    d = os.path.join(mdir, name)
    legs = latest(d)
    rows, bad, missing, got = [], [], False, {}
    if not legs:
        return ["no legs in %s" % d], ["no legs"], True, {}
    for (sh, arm), m in sorted(legs.items()):
        p = os.path.join(mdir, "out-" + name, "kcg-%s.folded.gz" % m.get("envoy_pid"))
        c = copy_share(p) if os.path.exists(p) else None
        if c is None:
            rows.append("%s/%s: NO folded profile (pid %s)" % (sh, arm, m.get("envoy_pid")))
            bad.append("%s: no profile" % arm)
            missing = True
            continue
        got[arm] = c
        rows.append("%s/%s: libc leaf %.2f%% of worker cycles (user frames %.1f%%; worker period %d); top callers: %s; guards %s; sha256 %s" % (
            sh, arm, 100 * c["libc_leaf_share"], 100 * c["user_share"], c["worker_period"],
            "; ".join("%s %.2f%%" % (k, 100 * v) for k, v in c["callers"]) or "-",
            json.dumps(m.get("runtime_start"), sort_keys=True), (m.get("binary_sha256") or "-")[:12]))
        if m.get("runtime_start") != mk.GUARDS["a"].get(arm) or m.get("binary_sha256") != mk.PIN["a"].get(arm):
            bad.append("%s: guards or binary are not the arm's" % arm)
    o, f, n = (got.get(a, {}).get("libc_leaf_share") for a in ("official-ch8k", "off-ch8k", "frag-on-ch8k"))
    if o is None or f is None or n is None:
        return rows, bad or ["a profile is missing"], True, got
    rows.append("SIGNATURE: official %.2f%%, off %.2f%% (x%.2f of official), frag-on %.2f%% (x%.2f of official)" % (
        100 * o, 100 * f, f / o if o else float("nan"), 100 * n, n / o if o else float("nan")))
    if o < SIG_MIN_OFFICIAL:
        bad.append("official-ch8k: libc leaf %.2f%% of worker cycles, under 1.0%%: the copy does not show on this rig" % (100 * o))
    else:
        if not SIG_OFF_BAND[0] <= f / o <= SIG_OFF_BAND[1]:
            bad.append("off-ch8k: libc leaf x%.2f of the official arm's (0.5 to 2.0): not the old path" % (f / o))
        if n / o > SIG_ON_MAX:
            bad.append("frag-on-ch8k: libc leaf x%.2f of the official arm's (at most 0.5): the copy is still there" % (n / o))
    return rows, bad, missing, got


def main(argv):
    if len(argv) == 2 and argv[0] == "smoke":
        rows, res = smoke(argv[1].rstrip("/"))
        print("\n".join(rows))
        load = [b for h, l_ in res.values() for b in l_]
        other = [b for h, l_ in res.values() for b in h]
        for sh, (h, l_) in res.items():
            for b in l_:
                print("LOAD GATE FAILED (%s): %s" % (sh, b))
            for b in h:
                print("STATE RULE FAILED (%s): %s" % (sh, b))
        rc = 1 if other else 3 if load else 0
        print("w1_check smoke %s: %s" % (os.path.basename(argv[1].rstrip("/")), {0: "OK", 3: "LOAD (%d)" % len(load), 1: "FAILED (%d)" % len(other)}[rc]))
        return rc
    if len(argv) == 2 and argv[0] == "pick":
        print(pick(argv[1].rstrip("/")))
        return 0
    if len(argv) == 3 and argv[0] == "mech":
        rows, bad, missing = mech(argv[1].rstrip("/"), argv[2])
        print("\n".join(rows))
        for b in bad:
            print("STATE RULE FAILED: " + b)
        print("w1_check mech %s: %s" % (argv[2], "OK" if not bad else "FAILED (%d)" % len(bad)))
        return 2 if missing else 1 if bad else 0
    if len(argv) == 3 and argv[0] == "sig":
        rows, bad, missing, _ = sig(argv[1].rstrip("/"), argv[2])
        print("\n".join(rows))
        for b in bad:
            print("STATE RULE FAILED: " + b)
        print("w1_check sig %s: %s" % (argv[2], "OK" if not bad else "FAILED (%d)" % len(bad)))
        return 2 if missing else 1 if bad else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
