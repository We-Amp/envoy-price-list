#!/usr/bin/env python3
"""The tail add-on's count (W8-2's open flag: server-side QUIC retransmissions with the UDP stop guard), in the
design of the W8-2 result review. Unscored for CPU. Everything here is Exploratory unless the rule below says
"stands out"; nothing is said about CPU.

    python3 examples/wave8w1/tail_check.py TAIL_DIR [--json OUT]

Per leg (Envoy's own counters at the end of the leg, written when a connection closes; a leg is two client runs
of 16 connections, the 5 s warm-up and the measured run: 32 connection lifetimes):
  cx_tx_packets_retransmitted_total, cx_tx_packets_total, cx_rx_packets_total; the per-connection histogram of
  the retransmitted share (connections with a non-zero share, from the bucket counts); Envoy's dropped-datagram
  counter; the kernel's Udp counters over the leg's window (box-wide; the whole round's are in chain-tail.log);
  completed requests; client latency p99, p99.9 (where the client's table reaches it) and maximum; requests of
  20 ms or more (the client's percentile table: all requests minus the cumulative count of the last entry under
  20 ms).

THE RULE, FIXED BEFORE THE FIRST LEG (the reviewer's "stands out", made exact):
  Part A  statistic T = sum over rounds of [retransmitted(h3-stop-on) + retransmitted(h3-both-on)
          - retransmitted(h3-official) - retransmitted(h3-off)], packets per leg. Exact permutation test inside
          rounds: in each round the four legs' counts are relabelled in all 6 ways of choosing which two are the
          stop-guard pair; p = the share of the 6^rounds relabellings with T at least the observed T (one-sided).
          STANDS OUT when p < 0.05. Only rounds with all four legs count. The noise scale is printed beside it:
          h3-off minus h3-official per round.
  Part B  the same difference per round, split: short rounds (10 s of traffic) and long rounds (40 s). "Grows
          with duration" = the mean difference of the long rounds is positive and at least twice the mean of the
          short rounds (traffic time, warm-up included, is three times as long: 45 s against 15 s). An event per
          connection lifetime gives the same difference in both.
  Part C  (h3-off and h3-both-on at one request per second per connection, 60 s) STANDS OUT when h3-both-on has
          more requests of 20 ms or more than h3-off, summed over the legs that ran. Retransmitted packets per
          1,000 requests are printed per arm.
  A validity verdict of the harness does not remove a leg here (the gates are for CPU rows; the quiet shape fails
  the worker-share gate by design); a leg without counters or with a non-zero Envoy exit does.
By the reviewer's text: if it stands out and does not grow with duration, it must be explained from code before
"worth proposing"; if it grows with duration, or part C shows timer-length latencies, the stop guard is not
proposed as written. The counts per arm are stated with their number of legs either way."""
import itertools
import json
import os
import re
import sys

QS = "listener.127.0.0.1_10110.quic_stats."
DROPPED = "listener.127.0.0.1_10110.udp.downstream_rx_datagram_dropped"
ARMS_A = ["h3-official", "h3-off", "h3-stop-on", "h3-both-on"]
GUARD, OLD = ("h3-stop-on", "h3-both-on"), ("h3-official", "h3-off")


def legs_of(d):
    out = []
    p = os.path.join(d, "legs.jsonl")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            m = json.loads(line) if line else {}
            if m.get("arm"):
                out.append(m)
    return out


def secs(s):
    try:
        return float(str(s).rstrip("s"))
    except ValueError:
        return None


def over_20ms(d, leg_id):
    """(requests, requests of 20 ms or more, p99.9 in us or None) from the client's own output of the leg."""
    try:
        j = json.load(open(os.path.join(d, "nighthawk", leg_id + ".json")))
    except (OSError, ValueError):
        return None, None, None
    for res in j.get("results", []):
        if res.get("name") != "global":
            continue
        for st in res.get("statistics", []):
            if st.get("id") != "benchmark_http_client.request_to_response":
                continue
            n = int(st.get("count") or 0)
            under, p999 = 0, None
            for pc in st.get("percentiles", []):
                dur = secs(pc.get("duration"))
                if dur is None:
                    continue
                if dur < 0.020:
                    under = max(under, int(pc.get("count") or 0))
                if p999 is None and float(pc.get("percentile") or 0) >= 0.999:
                    p999 = dur * 1e6
            return n, n - under, p999
    return None, None, None


def hist_nonzero(lines, name="retransmitted"):
    """(connections recorded, connections in a bucket above zero) of the detailed histogram whose name holds
    `name`, or None. Admin text: a line `<stat name>:` followed by indented `totals=lower,width:count ...`
    (older form: both on one line)."""
    cur = ""
    for ln in lines or []:
        if not ln.startswith(" "):
            cur = ln
        if name in cur and "totals=" in ln:
            tot = ln.split("totals=", 1)[1].split("intervals=")[0]
            b = [(float(lo), float(c)) for lo, _, c in re.findall(r"([0-9.e+-]+),([0-9.e+-]+):([0-9.e+-]+)", tot)]
            n = sum(c for _, c in b)
            return (int(n), int(sum(c for lo, c in b if lo > 0)))
    return None


def hist_text(lines, name="retransmitted"):
    out, cur = [], ""
    for ln in lines or []:
        if not ln.startswith(" "):
            cur = ln
        if name in cur and "summary=" not in ln:
            out.append(ln.strip())
    return out


def leg_row(d, m):
    le = m.get("sut_stats_leg_end") or {}
    kn = (m.get("kernel_net") or {}).get("d") or {}
    lat = m.get("latency_us") or {}
    n, slow, p999 = over_20ms(d, m.get("leg_id"))
    return {"arm": m["arm"], "leg": m.get("leg_id"), "config": os.path.basename(d), "started": m.get("started_utc"),
            "retransmitted": le.get(QS + "cx_tx_packets_retransmitted_total"), "sent": le.get(QS + "cx_tx_packets_total"),
            "received": le.get(QS + "cx_rx_packets_total"), "hist": hist_nonzero(m.get("sut_histograms_leg_end")),
            "hist_lines": hist_text(m.get("sut_histograms_leg_end")),
            "dropped": le.get(DROPPED), "requests": le.get("http.ingress_http.downstream_rq_completed"),
            "client_requests": n, "requests_20ms_or_more": slow, "p99_us": lat.get("p99"), "p999_us": p999, "max_us": lat.get("max"),
            "udp_window": {k: kn.get(k) for k in ("UdpInDatagrams", "UdpOutDatagrams", "UdpInErrors", "UdpRcvbufErrors", "UdpSndbufErrors")},
            "envoy_exit": m.get("envoy_exit"), "valid": bool((m.get("verdict") or {}).get("valid")),
            "reasons": (m.get("verdict") or {}).get("reasons"), "duration_s": None}


def usable(x):
    return x["retransmitted"] is not None and x["sent"] and x["envoy_exit"] == 0


def perm_p(rounds):
    """Exact one-sided p of T over all within-round relabellings. rounds: list of the four counts in the order
    official, off, stop-on, both-on."""
    obs = sum(r[2] + r[3] - r[0] - r[1] for r in rounds)
    dist = {0: 1}
    for r in rounds:
        tot = sum(r)
        opts = [2 * (r[i] + r[j]) - tot for i, j in itertools.combinations(range(4), 2)]
        nd = {}
        for t, c in dist.items():
            for o in opts:
                nd[t + o] = nd.get(t + o, 0) + c
        dist = nd
    n = sum(dist.values())
    return obs, sum(c for t, c in dist.items() if t >= obs) / float(n), n


def main(argv):
    T = argv[0].rstrip("/")
    out = {"part_a": {}, "part_c": {}, "legs": []}
    print("# tail add-on: server-side QUIC retransmissions (Exploratory; unscored for CPU)\n")
    print("| config | traffic s | arm (in run order) | retransmitted | sent | per 100,000 sent | received | connections in the histogram / with a "
          "non-zero share | Envoy dropped | requests | 20 ms or more | p99 µs | p99.9 µs | max µs | kernel Udp in the window: in / out / "
          "InErrors / RcvbufErrors | usable | harness verdict |")
    print("|" + "---|" * 17)
    A, C = {}, []
    names = sorted((n for n in os.listdir(T) if n.startswith("tail-")), key=lambda s: (s[5], int(s.split("r")[-1]))) if os.path.isdir(T) else []
    for name in names:
        d = os.path.join(T, name)
        try:
            dur = json.load(open(os.path.join(d, "experiment.json")))["client"]["duration_s"]
        except (OSError, ValueError, KeyError):
            dur = None
        for m in legs_of(d):
            x = leg_row(d, m)
            x["duration_s"] = dur
            out["legs"].append(x)
            u = x["udp_window"]
            print("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s / %s / %s / %s | %s | %s |" % (
                name, dur, x["arm"], x["retransmitted"], x["sent"],
                "-" if not usable(x) else "%.2f" % (1e5 * x["retransmitted"] / x["sent"]), x["received"],
                "-" if x["hist"] is None else "%d / %d" % x["hist"], x["dropped"], x["requests"], x["requests_20ms_or_more"],
                x["p99_us"], None if x["p999_us"] is None else round(x["p999_us"]), x["max_us"], u["UdpInDatagrams"], u["UdpOutDatagrams"],
                u["UdpInErrors"], u["UdpRcvbufErrors"], "yes" if usable(x) else "NO", "valid" if x["valid"] else "not valid: %s" % "; ".join(str(r)[:60] for r in x["reasons"] or [])))
            if name.startswith("tail-a-"):
                A.setdefault(name, {})[x["arm"]] = x
            else:
                C.append(x)
    # part A and B
    full = [(n, r) for n, r in sorted(A.items(), key=lambda kv: int(kv[0].split("r")[-1])) if all(a in r and usable(r[a]) for a in ARMS_A)]
    print("\n## part A: per arm\n")
    print("| arm | legs | retransmitted, per leg | sum | sent, sum | per 100,000 sent: all legs pooled | per leg: min to max | 10 s legs: retransmitted "
          "(sum over legs) | 40 s legs | legs with a request of 20 ms or more | largest max µs |")
    print("|" + "---|" * 11)
    for a in ARMS_A:
        mine = [r[a] for _, r in full]
        if not mine:
            continue
        rt, sn = [x["retransmitted"] for x in mine], [x["sent"] for x in mine]
        per = [1e5 * x["retransmitted"] / x["sent"] for x in mine]
        s10 = [x["retransmitted"] for x in mine if x["duration_s"] == 10]
        s40 = [x["retransmitted"] for x in mine if x["duration_s"] == 40]
        out["part_a"][a] = {"legs": len(mine), "retransmitted": rt, "sent": sn, "per_100k_pooled": 1e5 * sum(rt) / sum(sn), "per_100k_per_leg": per,
                            "short": s10, "long": s40}
        print("| %s | %d | %s | %d | %d | %.2f | %.2f to %.2f | %s (%d legs) | %s (%d legs) | %d | %s |" % (
            a, len(mine), " ".join(str(v) for v in rt), sum(rt), sum(sn), 1e5 * sum(rt) / sum(sn), min(per), max(per), sum(s10), len(s10),
            sum(s40), len(s40), sum(1 for x in mine if x["requests_20ms_or_more"]), max(x["max_us"] or 0 for x in mine)))
    if full:
        rows = [[r[a]["retransmitted"] for a in ARMS_A] for _, r in full]
        obs, p, n = perm_p(rows)
        diff = [r[2] + r[3] - r[0] - r[1] for r in rows]
        noise = [r[1] - r[0] for r in rows]
        durs = [r[ARMS_A[0]]["duration_s"] for _, r in full]
        short = [d for d, t in zip(diff, durs) if t == 10]
        long_ = [d for d, t in zip(diff, durs) if t == 40]
        ms, ml = (sum(short) / len(short) if short else None), (sum(long_) / len(long_) if long_ else None)
        grows = bool(ml is not None and ms is not None and ml > 0 and ml >= 2.0 * ms)
        out["part_a"]["rule"] = {"rounds": len(full), "T": obs, "p_one_sided": p, "relabellings": n, "stands_out": p < 0.05,
                                 "per_round_difference": diff, "per_round_traffic_s": durs, "old_pair_difference_per_round": noise,
                                 "mean_difference_short": ms, "mean_difference_long": ml, "grows_with_duration": grows}
        print("\nPART A RULE: T = %d packets over %d rounds (stop-guard pair minus old-path pair, per round: %s; traffic s: %s). Exact "
              "one-sided p over %d within-round relabellings: %.4f. %s" % (
                  obs, len(full), " ".join("%+d" % v for v in diff), " ".join(str(t) for t in durs), n, p,
                  "STANDS OUT (p < 0.05)" if p < 0.05 else "does not stand out (p >= 0.05)"))
        print("noise scale: h3-off minus h3-official per round: %s" % " ".join("%+d" % v for v in noise))
        print("PART B (duration split): mean difference per round, 10 s rounds %s, 40 s rounds %s: %s" % (
            "-" if ms is None else "%+.2f" % ms, "-" if ml is None else "%+.2f" % ml,
            "GROWS with duration (long rounds positive and at least twice the short)" if grows else "does not grow with duration by the fixed rule"))
    else:
        print("\nPART A RULE: no complete round")
    # part C
    print("\n## part C: the quiet shape (one request per second per connection)\n")
    print("| arm | legs | requests | requests of 20 ms or more | retransmitted (per leg) | sum | per 1,000 requests | sent | max µs per leg |")
    print("|" + "---|" * 9)
    tot = {}
    for a in ("h3-off", "h3-both-on"):
        mine = [x for x in C if x["arm"] == a and usable(x) and x["requests_20ms_or_more"] is not None]
        if not mine:
            continue
        rq, slow, rt = sum(x["client_requests"] or 0 for x in mine), sum(x["requests_20ms_or_more"] for x in mine), [x["retransmitted"] for x in mine]
        tot[a] = slow
        out["part_c"][a] = {"legs": len(mine), "requests": rq, "requests_20ms_or_more": slow, "retransmitted": rt, "sent": sum(x["sent"] for x in mine),
                            "max_us": [x["max_us"] for x in mine]}
        print("| %s | %d | %d | %d | %s | %d | %.2f | %d | %s |" % (
            a, len(mine), rq, slow, " ".join(str(v) for v in rt), sum(rt), 1e3 * sum(rt) / rq if rq else float("nan"), sum(x["sent"] for x in mine),
            " ".join(str(round(x["max_us"] or 0)) for x in mine)))
    if len(tot) == 2:
        so = tot["h3-both-on"] > tot["h3-off"]
        out["part_c"]["rule"] = {"stands_out": so, "both_on": tot["h3-both-on"], "off": tot["h3-off"]}
        print("\nPART C RULE: requests of 20 ms or more: h3-both-on %d, h3-off %d: %s" % (
            tot["h3-both-on"], tot["h3-off"], "STANDS OUT (more with the guards)" if so else "does not stand out"))
    else:
        print("\nPART C RULE: not evaluated (an arm has no usable leg)")
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
