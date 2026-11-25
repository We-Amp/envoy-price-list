#!/usr/bin/env python3
"""Per-arm, per-leg evidence of the W8-2 scored run directories, recomputed from the legs (not from the harness's
own verdicts): what shows that each leg ran the binary and the guards its row assumes, that every response
arrived, and that nothing was reset, dropped or timed out (analysis only).

    python3 examples/wave8w2/evidence_summary.py RUN_DIR [RUN_DIR ...] [--json OUT]

Per run and arm over the current legs (min to max unless stated): legs valid and evidence passing; the sha256 of
the file each leg's Envoy ran against the pin; the three runtime guards as the admin /runtime of each leg's
process read them at its start and at its end (1 true, 0 false, -1 not set); responses in the window; the
client's 2xx per second against the open-loop target; bytes per request on three segments and UDP datagrams per
request (box-wide); every error counter (sum over the legs: the window's deltas and the end-of-leg values);
Envoy's exit codes; load figures; latency maximum per leg. Legs the harness replaced are listed with reasons."""
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


chk = _load("w8w2_check_for_evidence", os.path.join(HERE, "w2_check.py"))
mk = chk.mk
ERR = ("reset", "timeout", "protocol_error", "connect_fail", "overflow", "_5xx", "_4xx", "bug_failures", "assertion_failures",
       "connection_error", "datagram_dropped", "retry", "overload")


def rng(v, f="%.4f"):
    v = [x for x in v if x is not None]
    if not v:
        return "-"
    lo, hi = min(v), max(v)
    return (f % lo) if abs(hi - lo) < 1e-12 else (f + " to " + f) % (lo, hi)


def main(argv):
    out = {}
    dirs = [a for a in argv if not a.startswith("--") and (argv.index(a) == 0 or argv[argv.index(a) - 1] != "--json")]
    for d in dirs:
        d = d.rstrip("/")
        name = os.path.basename(d)
        p = os.path.join(d, "results.json")
        if not os.path.exists(p):
            print("\n## %s: no results.json" % name)
            continue
        res = json.load(open(p))
        cur = [m for m in res["legs"] if m.get("arm") and not m.get("superseded")]
        sup = [m for m in res["legs"] if m.get("arm") and m.get("superseded")]
        O = out[name] = {"arms": {}, "superseded": []}
        print("\n## %s: %d current legs, %d replaced\n" % (name, len(cur), len(sup)))
        for m in sup:
            v = m.get("verdict") or {}
            O["superseded"].append({"leg": m.get("leg_id"), "arm": m.get("arm"), "round": m.get("round"), "valid": v.get("valid"), "reasons": v.get("reasons")})
            print("- replaced: %s (round %s, arm %s): valid %s; %s" % (m.get("leg_id"), m.get("round"), m.get("arm"), v.get("valid"),
                                                                    "; ".join(str(x) for x in v.get("reasons") or []) or "its round was replaced because of another leg"))
        print("\n| arm | legs valid | evidence passing (items per leg) | sha256 equals the pin | guards at start / at end (ch, st, ru) | responses in the "
              "window | client 2xx/s over target | bytes/req Envoy to origin | origin to Envoy | Envoy to client | UDP datagrams/req | new or destroyed "
              "connections in the window (client side / origin side) | error counters above zero (window sum; end-of-leg sum) | Envoy exit codes | "
              "client headroom | busiest worker share | latency max µs |")
        print("|" + "---|" * 17)
        for a in mk.SCORED:
            mine = [m for m in cur if m["arm"] == a]
            if not mine:
                continue
            ev = [m.get("evidence") or {} for m in mine]
            w = lambda m, s: (m.get("sut_stats_window") or {}).get(s)  # noqa: E731
            pr = lambda s: [chk.per_request(m, s) for m in mine]  # noqa: E731
            gs = sorted({json.dumps([(m.get("runtime_start") or {}).get(k) for k in ("ch", "st", "ru")]) for m in mine})
            ge = sorted({json.dumps([(m.get("runtime_end") or {}).get(k) for k in ("ch", "st", "ru")]) for m in mine})
            errw, erre = {}, {}
            for m in mine:
                for k, x in (m.get("sut_stats_window") or {}).items():
                    if x and any(t in k for t in ERR):
                        errw[k] = errw.get(k, 0) + x
                for k, x in (m.get("sut_stats_leg_end") or {}).items():
                    if x and any(t in k for t in ERR):
                        erre[k] = erre.get(k, 0) + x
            cx = lambda keys: sum((w(m, k) or 0) for m in mine for k in keys)  # noqa: E731
            L, H, C = mk.L, mk.H, "cluster.origin."
            row = {"legs": len(mine), "valid": sum(1 for m in mine if (m.get("verdict") or {}).get("valid")),
                   "evidence_ok": sum(1 for e in ev if e.get("ok")), "items": sorted({len(e.get("items") or []) for e in ev}),
                   "pin_ok": sum(1 for m in mine if m.get("binary_sha256") == chk.PIN[a]), "guards_start": gs, "guards_end": ge,
                   "expected_guards": [mk.GUARDS[a][k] for k in ("ch", "st", "ru")],
                   "errors_window": errw, "errors_leg_end": erre, "exit": sorted({m.get("envoy_exit") for m in mine}),
                   "client_cx_window": cx([L + "downstream_cx_total", L + "downstream_cx_destroy"]),
                   "origin_cx_window": cx([C + "upstream_cx_total", C + "upstream_cx_destroy"]),
                   "latency_max_us": [(m.get("latency_us") or {}).get("max") for m in mine]}
            O["arms"][a] = row
            print("| %s | %d/%d | %d/%d (%s) | %d/%d | %s / %s (expected %s) | %s | %s | %s | %s | %s | %s | %d / %d | %s; %s | %s | %s | %s | %s |" % (
                a, row["valid"], row["legs"], row["evidence_ok"], row["legs"], ", ".join(str(x) for x in row["items"]), row["pin_ok"], row["legs"],
                " ".join(gs), " ".join(ge), json.dumps(row["expected_guards"]), rng([m.get("responses_raw") for m in mine], "%d"),
                rng([(m.get("client_rate_2xx") or 0) / (m.get("target_rps") or 1) for m in mine], "%.5f"),
                rng(pr("cluster.origin.upstream_cx_tx_bytes_total"), "%.3f"), rng(pr("cluster.origin.upstream_cx_rx_bytes_total"), "%.3f"),
                rng(pr(H + "downstream_cx_tx_bytes_total"), "%.3f"), rng([chk.datagrams(m) for m in mine]),
                row["client_cx_window"], row["origin_cx_window"], json.dumps(errw) if errw else "none", json.dumps(erre) if erre else "none",
                row["exit"], rng([m.get("client_headroom") for m in mine], "%.2f"), rng([m.get("envoy_worker_max_share") for m in mine], "%.3f"),
                rng(row["latency_max_us"], "%.0f")))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
