#!/usr/bin/env python3
"""Wave 8 W8-1: per-arm evidence of the scored legs, from the copied run directory (analysis only).

    python3 examples/wave8w1/evidence_summary.py RUNS_DIR [--json OUT]

Per run, shape and arm over the current (not superseded) legs: valid legs; evidence passing; sha256 of the file the
leg's Envoy ran against the arm's pin; guards at start and end against the arm's row; 2xx per target; responses in
the window; bytes per request on the four segments (lowest to highest leg); the stream origin's writes and chunks per
response; client headroom; worker share; the superseded legs with their reasons."""
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


chk = _load("w8w1_check_for_evidence", os.path.join(HERE, "w1_check.py"))
mk = chk.mk


def rng(v, f="%.2f"):
    v = [x for x in v if x is not None]
    return "-" if not v else (f % min(v)) if max(v) - min(v) < 1e-9 else (f + " to " + f) % (min(v), max(v))


def main(argv):
    rd = argv[0].rstrip("/")
    out = {}
    for run in "abdc":
        try:
            var = open(os.path.join(rd, "pick-%s.txt" % run)).read().strip()
        except OSError:
            continue
        p = os.path.join(rd, var, "results.json")
        if not os.path.exists(p):
            print("\n## run %s (%s): not run" % (run, var))
            continue
        d = json.load(open(p))
        cur = [m for m in d["legs"] if m.get("arm") and not m.get("superseded")]
        sup = [m for m in d["legs"] if m.get("arm") and m.get("superseded")]
        print("\n## run %s (%s): %d current legs, %d superseded\n" % (run, var, len(cur), len(sup)))
        print("| shape | arm | valid | evidence ok | binary = pin | guards = the arm's (start and end) | client 2xx/s over target | responses in the "
              "window | bytes/req client to Envoy | Envoy to origin | origin to Envoy | Envoy to client | origin writes / chunks per response | "
              "client headroom (min) | busiest worker share (max) | Envoy exit codes |")
        print("|" + "---|" * 16)
        O = out[run] = {"variant": var, "arms": {}, "superseded": []}
        for sh in mk.SHAPES[run]:
            for arm in mk.ARMS[run]:
                mine = [m for m in cur if m["shape"] == sh and m["arm"] == arm]
                if not mine:
                    continue
                pin = sum(1 for m in mine if m.get("binary_sha256") == mk.PIN[run][arm])
                gd = sum(1 for m in mine if m.get("runtime_start") == mk.GUARDS[run][arm] and m.get("runtime_end") == mk.GUARDS[run][arm])
                evok = sum(1 for m in mine if (m.get("evidence") or {}).get("ok"))
                val = sum(1 for m in mine if (m.get("verdict") or {}).get("valid"))
                by = [[chk.per_request(m, s) for m in mine] for _, s in mk.BYTES]
                so = [((m.get("stream_origin") or {}).get("d") or {}) for m in mine]
                wr = [x["write_calls"] / x["responses"] for x in so if x.get("responses")]
                ck = [x["chunks"] / x["responses"] for x in so if x.get("responses")]
                rate = [(m.get("client_rate_2xx") or 0) / m["target_rps"] for m in mine if m.get("target_rps")]
                O["arms"]["%s/%s" % (sh, arm)] = {"legs": len(mine), "valid": val, "evidence_ok": evok, "pin_ok": pin, "guards_ok": gd,
                                                  "bytes": [[min(b), max(b)] if all(x is not None for x in b) else None for b in by]}
                print("| %s | %s | %d/%d | %d/%d | %d/%d | %d/%d | %s | %s | %s | %s | %s | %s | %s / %s | %.2f | %.3f | %s |" % (
                    sh, arm, val, len(mine), evok, len(mine), pin, len(mine), gd, len(mine), rng(rate, "%.5f"),
                    rng([m.get("responses_raw") for m in mine], "%d"), rng(by[0]), rng(by[1]), rng(by[2], "%.1f"), rng(by[3], "%.1f"),
                    rng(wr, "%.3f"), rng(ck, "%.3f"), min(m.get("client_headroom") or 0 for m in mine),
                    max(m.get("envoy_worker_max_share") or 0 for m in mine), sorted({m.get("envoy_exit") for m in mine})))
        for m in sup:
            O["superseded"].append({"leg": m.get("leg_id"), "arm": m["arm"], "shape": m["shape"], "reasons": (m.get("verdict") or {}).get("reasons")})
        if sup:
            print("\nsuperseded legs (a round with a leg that failed a validity gate is replaced once by the harness, all its arms):")
            for m in sup:
                r = (m.get("verdict") or {}).get("reasons") or []
                if r:
                    print("- %s %s/%s: %s" % (m.get("leg_id"), m["shape"], m["arm"], "; ".join(str(x)[:160] for x in r)))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
