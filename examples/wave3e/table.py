#!/usr/bin/env python3
"""Per-connection prices of wave 3 track E, offline, from a run's legs.

    python3 examples/wave3e/table.py RUN_DIR

Rows are paired by round: (arm - reference) in cycles per request for every round with a valid leg
of both, then the mean with a 95% t interval over the rounds. In a churn arm every request opens one
connection (evidence: listener downstream_cx_total 1.00 +/- 0.02 per request), so "churn arm minus
keep-alive arm" is the price of one new connection, in cycles; the column cx/req shows the measured
ratio. The A/A row in the same units is the floor: a price inside the A/A row's reach is not one.
Totals, user and kernel cycles are listed separately (the kernel share on loopback includes part of the
client's receive work and the conntrack work of this Docker host; it is not portable).
"""

import json
import math
import os
import sys

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
       11: 2.201, 12: 2.179}
LISTENER = "listener.127.0.0.1_10110."
ROWS = {
    "e-plain": [("c1", "ka", "plaintext connection (c1 - ka)"),
                ("ka-A2", "ka", "A/A (ka-A2 - ka)")],
    "e2-plain": [("c1", "ka", "plaintext connection again (c1 - ka; E: 238.7k +/- 7.0k)"),
                 ("c1-defer", "c1", "TCP_DEFER_ACCEPT 1 s (per connection)"),
                 ("c1-shared", "c1", "shared listen socket, no SO_REUSEPORT (per connection)"),
                 ("c1-xb", "c1", "exact_balance (per connection)"),
                 ("c1-A2", "c1", "A/A (c1-A2 - c1)")],
    "e2b-plain": [("c1", "ka", "plaintext connection again (c1 - ka; E: 238.7k +/- 7.0k)"),
                  ("c1-defer", "c1", "TCP_DEFER_ACCEPT 1 s (per connection)"),
                  ("c1-A2", "c1", "A/A (c1-A2 - c1)")],
    "e-tls": [("ecdsa-full", "tls-ka", "TLS connection, full handshake, ECDSA P-256"),
              ("rsa-full", "tls-ka", "TLS connection, full handshake, RSA-2048"),
              ("ecdsa-res", "tls-ka", "TLS connection, resumed, ECDSA P-256"),
              ("ecdsa-x25519", "tls-ka", "TLS connection, full handshake, ECDSA, X25519 only"),
              ("rsa-full", "ecdsa-full", "certificate: RSA-2048 - ECDSA P-256 (per full handshake)"),
              ("ecdsa-res", "ecdsa-full", "resumption: resumed - full (ECDSA)"),
              ("ecdsa-x25519", "ecdsa-full", "group: X25519 - X25519MLKEM768 (per full handshake)"),
              ("ecdsa-full-A2", "ecdsa-full", "A/A (ecdsa-full-A2 - ecdsa-full)")],
}
METRICS = ("cycles_total", "cycles_u", "cycles_k")


def legs(run_dir):
    out = {}
    with open(os.path.join(run_dir, "legs.jsonl")) as f:
        for ln in f:
            m = json.loads(ln)
            if m.get("warmup") or m.get("superseded") or not (m.get("verdict") or {}).get("valid"):
                continue
            out[(m["round"], m["arm"])] = m  # a re-run replaces the earlier attempt
    return out


def ci(xs):
    n = len(xs)
    if n < 2:
        return (xs[0] if xs else float("nan")), float("nan")
    mu = sum(xs) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
    return mu, T95.get(n - 1, 1.96) * sd / math.sqrt(n)


def cx_per_req(m):
    w = m.get("sut_stats_window") or {}
    r = m.get("responses_raw") or 0
    v = w.get(LISTENER + "downstream_cx_total")
    return v / r if r and v is not None else None


def table(run_dir):
    with open(os.path.join(run_dir, "experiment.json")) as f:
        name = json.load(f)["name"]
    rows = ROWS[name.replace("smoke-", "")]
    L = legs(run_dir)
    rounds = sorted({r for r, _ in L})
    print("# %s (%s): %d rounds with valid legs" % (name, run_dir, len(rounds)))
    print("| Row | n | cycles/conn (total) | user | kernel | cx/req of the arm | arm cycles/req |")
    print("|---|---|---|---|---|---|---|")
    for arm, ref, label in rows:
        d = {k: [] for k in METRICS}
        cx, lvl = [], []
        for r in rounds:
            a, b = L.get((r, arm)), L.get((r, ref))
            if not a or not b:
                continue
            for k in METRICS:
                if a["per_req"].get(k) is not None and b["per_req"].get(k) is not None:
                    d[k].append(a["per_req"][k] - b["per_req"][k])
            if cx_per_req(a) is not None:
                cx.append(cx_per_req(a))
            lvl.append(a["per_req"]["cycles_total"])
        cells = []
        for k in METRICS:
            mu, hw = ci(d[k])
            cells.append("%+.1fk +/- %.1fk" % (mu / 1e3, hw / 1e3) if d[k] else "-")
        print("| %s | %d | %s | %.3f | %.1fk |" % (label, len(d["cycles_total"]), " | ".join(cells),
                                                  sum(cx) / len(cx) if cx else float("nan"),
                                                  (sum(lvl) / len(lvl) / 1e3) if lvl else float("nan")))


if __name__ == "__main__":
    for rd in sys.argv[1:]:
        table(rd)
