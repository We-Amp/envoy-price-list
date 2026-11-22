#!/usr/bin/env python3
"""Rows of wave 4 track G, offline, from a run's legs.

    python3 examples/wave4g/table.py RUN_DIR [RUN_DIR ...]

Per row, paired by round over the rounds with a valid leg of both arms:
  log-%       mean per-round log ratio of the primary metric (cycles u+k per request), 100 ln(arm/ref),
              with the 95% t half-width and the widened half-width 1.96*sqrt(SE^2 + 0.34^2), both in
              log-%; the quoted interval is the wider of the two (the price list's method)
  effect %    the same mean and interval turned back into a percent change, 100 (exp(log-%/100) - 1)
  delta       the same pairs as differences in cycles per request: total, user, kernel, user instructions
In g2 the reconnect arms open one connection per 10 requests, so (h3r - h3-ka) * 10 is the price of one
QUIC connection with the v1.40.2 defaults, in cycles; the cx/req column shows the measured ratio. The
UDP datagram column is box-wide (client and Envoy) per request: a reading, never a gate.
"""

import json
import math
import os
import sys

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
       11: 2.201, 12: 2.179}
FLOOR = 0.34
LISTENER = "listener.127.0.0.1_10110."
ROWS = {
    "g1-proto": [("h3-A2", "h3", "A/A (h3-A2 vs h3)", 1),
                 ("h3", "h2tls", "HTTP/3 vs HTTP/2 over TLS", 1),
                 ("h3-nogso", "h3", "HTTP/3 without the GSO writer vs with it", 1),
                 ("h3-nogso", "h2tls", "HTTP/3 without GSO vs HTTP/2 over TLS", 1)],
    "g2-resume": [("h3r-A2", "h3r", "A/A (h3r-A2 vs h3r)", 10),
                  ("h3r", "h3-ka", "QUIC connection, v1.40.2 defaults (per connection)", 10),
                  ("h3r-tk", "h3-ka", "QUIC connection, ticket guard on + shared key (per connection)", 10),
                  ("h3r-tk", "h3r", "guard on + shared key vs default (per connection)", 10)],
}
METRICS = ("cycles_total", "cycles_u", "cycles_k", "instructions_u")


def legs(run_dir):
    out = {}
    with open(os.path.join(run_dir, "legs.jsonl")) as f:
        for ln in f:
            m = json.loads(ln)
            if m.get("warmup") or m.get("superseded") or not (m.get("verdict") or {}).get("valid"):
                continue
            out[(m["round"], m["arm"])] = m
    return out


def ci(xs):
    n = len(xs)
    if n < 2:
        return (xs[0] if xs else float("nan")), float("nan"), float("nan")
    mu = sum(xs) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
    se = sd / math.sqrt(n)
    return mu, T95.get(n - 1, 1.96) * se, 1.96 * math.sqrt(se ** 2 + FLOOR ** 2)


def pct(log_pct):
    """A log ratio in log-% (100 ln(a/b)) as a percent change: 100 (a/b - 1)."""
    return math.expm1(log_pct / 100.0) * 100.0


def per_req(m, stat, scope="sut_stats_window"):
    r = m.get("responses_raw") or m.get("responses") or 0
    v = (m.get(scope) or {}).get(stat)
    return v / r if r and v is not None else None


def udp_out_per_req(m):
    r = m.get("responses_raw") or m.get("responses") or 0
    v = ((m.get("kernel_net") or {}).get("d") or {}).get("UdpOutDatagrams")
    return v / r if r and v is not None else None


def rows(run_dir):
    with open(os.path.join(run_dir, "experiment.json")) as f:
        exp = json.load(f)
    name = exp["name"].replace("smoke-", "").replace("g2s-", "g2-")
    metric = exp.get("primary_metric", "cycles_total")
    L = legs(run_dir)
    rounds = sorted({r for r, _ in L})
    out = []
    for arm, ref, label, scale in ROWS[name]:
        lr, d = [], {k: [] for k in METRICS}
        cx, udp, lvl, shr = [], [], [], []
        for r in rounds:
            a, b = L.get((r, arm)), L.get((r, ref))
            if not a or not b:
                continue
            pa, pb = a["per_req"], b["per_req"]
            if pa.get(metric) and pb.get(metric):
                lr.append(100.0 * math.log(pa[metric] / pb[metric]))
            for k in METRICS:
                if pa.get(k) is not None and pb.get(k) is not None:
                    d[k].append(scale * (pa[k] - pb[k]))
            c = per_req(a, LISTENER + "downstream_cx_total")
            if c is not None:
                cx.append(c)
            u = udp_out_per_req(a)
            if u is not None:
                udp.append(u)
            lvl.append(pa[metric])
            if a.get("envoy_worker_max_share") is not None:
                shr.append(a["envoy_worker_max_share"])
        mu, t, w = ci(lr)
        hw = max(t, w) if lr else float("nan")
        # the mean and the interval are on log ratios (log-%); the effect is that turned back into a ratio
        out.append({"row": label, "arm": arm, "ref": ref, "n": len(lr), "log_pct": mu, "effect_pct": pct(mu),
                    "t_hw": t, "widened_hw": w, "log_interval": (mu - hw, mu + hw),
                    "interval": (pct(mu - hw), pct(mu + hw)), "excludes_0": bool(lr) and (mu - hw > 0 or mu + hw < 0),
                    "pairs_up": sum(1 for x in lr if x > 0),
                    "delta": {k: ci(d[k])[:2] for k in METRICS if d[k]}, "scale": scale,
                    "cx_per_req": sum(cx) / len(cx) if cx else None,
                    "udp_out_per_req": sum(udp) / len(udp) if udp else None,
                    "arm_level": sum(lvl) / len(lvl) if lvl else None,
                    "max_share": (min(shr), max(shr)) if shr else None})
    return name, rounds, out


def table(run_dir):
    name, rounds, out = rows(run_dir)
    print("# %s (%s): %d rounds with valid legs" % (name, run_dir, len(rounds)))
    print("| Row | n | effect % [quoted interval] | log-% [quoted interval] | t hw (log-%) | widened hw (log-%) | up | "
          "delta total | user | kernel | ins:u | cx/req | UDP out/req | arm cyc/req | busiest worker share |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for o in out:
        unit = "/cx" if o["scale"] != 1 else "/req"
        cells = []
        for k in METRICS:
            mu, hw = o["delta"].get(k, (float("nan"), float("nan")))
            cells.append("%+.1fk +/- %.1fk%s" % (mu / 1e3, hw / 1e3, unit if k == "cycles_total" else ""))
        f = lambda x, p="%.3f": (p % x) if x is not None else "-"  # noqa: E731
        print("| %s | %d | %+.2f [%+.2f, %+.2f] | %+.2f [%+.2f, %+.2f] | %.2f | %.2f | %d/%d | %s | %s | %s | %.1fk | %s |" % (
            o["row"], o["n"], o["effect_pct"], o["interval"][0], o["interval"][1],
            o["log_pct"], o["log_interval"][0], o["log_interval"][1], o["t_hw"], o["widened_hw"],
            o["pairs_up"], o["n"], " | ".join(cells), f(o["cx_per_req"]), f(o["udp_out_per_req"], "%.2f"),
            (o["arm_level"] or float("nan")) / 1e3,
            "%.3f-%.3f" % o["max_share"] if o["max_share"] else "-"))


if __name__ == "__main__":
    for rd in sys.argv[1:]:
        table(rd)
