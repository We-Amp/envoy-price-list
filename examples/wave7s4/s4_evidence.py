#!/usr/bin/env python3
"""The on-box evidence the scored OpenTelemetry run waits for (the build record, evidence layer 3, and
the rule fixed before the run): read after the two non-scored configs ran.

    s4_evidence.py RUN_ROOT [--json OUT]      exit 0: both parts pass; 1: do not score the patched arms

Part A, the span path (mech/ev-span-path + mech/out-ev-span-path): the unstripped twin of the patched binary
at 0% sampling under the scored load, a user-space profile of the process over the window, per shape:
  guard on (default)   0 symbols of the OTLP span message (opentelemetry::proto::trace::v1::Span::) and 0 of
                       the tracer's recording span (Tracers::OpenTelemetry::Span::) among the sampled symbols,
                       and at least one of Tracers::OpenTelemetry::DeferredSpan::
  guard off            both classes above 0 (the positive control: the profile can see them)
  every leg            at least 5,000 samples, responses in the window, no non-2xx, the leg's own evidence
                       (tracer configured, nothing sampled, no span sent, guard state) passing
Part B, the export (mech/ev-export): official and patched at 100% sampling; every leg's own evidence passing
(every request sampled, spans sent and accepted 1.00 per request), and span_compare.py says the collector
printed the same spans for both (ids, times and per-request values masked)."""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_SAMPLES = 5000


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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


def span_check(out_dir):
    rows = {}
    p = os.path.join(out_dir, "span-check.txt")
    if not os.path.exists(p):
        return rows
    for line in open(p):
        parts = line.split()
        if len(parts) < 3:
            continue
        kv = dict(x.split("=", 1) for x in parts[2:] if "=" in x)
        m = re.match(r"span-(\d+)$", parts[1])
        if m:
            rows[int(m.group(1))] = dict(kv, status=parts[0])
    return rows


def leg_ok(m, lines, tag, bad):
    ev = m.get("evidence") or {}
    non2xx = (m.get("sut_non2xx") or 0) + sum((m.get("client_non2xx") or {}).values())
    ok = (m.get("responses_raw") or 0) > 0 and non2xx == 0 and ev.get("ok") is True
    lines.append("%s: responses in the window %s, non-2xx %s, leg evidence %s (%d items)%s, valid %s" % (
        tag, m.get("responses_raw"), non2xx, ev.get("ok"), len(ev.get("items") or []),
        "" if ev.get("ok") else " FAILED: " + "; ".join((ev.get("failed") or [])[:6]), (m.get("verdict") or {}).get("valid")))
    if not ok:
        bad.append("%s: no responses, a non-2xx, or the leg's evidence failed" % tag)
    return ok


def part_a(root, lines, bad):
    legs = latest(os.path.join(root, "mech", "ev-span-path"))
    rows = span_check(os.path.join(root, "mech", "out-ev-span-path"))
    out = {}
    if not legs:
        bad.append("A: no legs in mech/ev-span-path")
    for (sh, arm), m in sorted(legs.items()):
        tag = "A %s/%s" % (sh, arm)
        leg_ok(m, lines, tag, bad)
        r = rows.get(m.get("envoy_pid"))
        if not r:
            bad.append("%s: no profile of pid %s" % (tag, m.get("envoy_pid")))
            continue
        n, o, c, d = (int(r.get(k, 0)) for k in ("samples", "otlp_span_symbols", "recording_span_symbols", "deferred_span_symbols"))
        out["%s/%s" % (sh, arm)] = dict(r, pid=m.get("envoy_pid"))
        lines.append("%s: pid %s, %d samples, %s symbol lines; OTLP span message: %d symbols (%s%%); recording span: %d symbols "
                     "(%s%%); deferred span: %d symbols (%s%%)" % (
                         tag, m.get("envoy_pid"), n, r.get("symbol_lines"), o, r.get("otlp_span_pct"), c, r.get("recording_span_pct"),
                         d, r.get("deferred_span_pct")))
        if r["status"] != "OK" or n < MIN_SAMPLES:
            bad.append("%s: the profile holds %d samples (need %d) or its report is short" % (tag, n, MIN_SAMPLES))
        if arm.endswith("guard-off"):
            if not (o > 0 and c > 0):
                bad.append("%s: the positive control does not show both span classes (%d, %d)" % (tag, o, c))
        elif not (o == 0 and c == 0 and d > 0):
            bad.append("%s: guard on must show 0 / 0 symbols of the two span classes and the deferred span above 0 (%d, %d, %d)" % (tag, o, c, d))
    if len(legs) < 4:
        bad.append("A: %d legs, expected 4 (two arms on two shapes)" % len(legs))
    return out


def part_b(root, lines, bad):
    d = os.path.join(root, "mech", "ev-export")
    legs = latest(d)
    cmp_ = _load("span_compare", os.path.join(HERE, "span_compare.py"))
    got = {}
    for (sh, arm), m in sorted(legs.items()):
        tag = "B %s/%s" % (sh, arm)
        leg_ok(m, lines, tag, bad)
        cd = m.get("collector_delta") or {}
        p = os.path.join(d, "collector", m["leg_id"] + ".spans.log")
        lines.append("%s: spans accepted by the collector over the leg %s, refused %s; log %s (%s bytes)" % (
            tag, cd.get("accepted_spans"), cd.get("refused_spans"), os.path.basename(p),
            os.path.getsize(p) if os.path.exists(p) else "missing"))
        got[arm] = (p, cd.get("accepted_spans"))
    if set(got) != {"stock-100", "patched-100"}:
        bad.append("B: legs %s, expected stock-100 and patched-100" % sorted(got))
        return {}
    (pa, na), (pb, nb) = got["stock-100"], got["patched-100"]
    if not (os.path.exists(pa) and os.path.exists(pb)) or not na or not nb:
        bad.append("B: a span log or a span count is missing")
        return {}
    ok, out, detail = cmp_.compare(pa, pb, na, nb)
    lines.extend("B compare (A = stock-100, B = patched-100): " + x for x in out)
    if not ok:
        bad.append("B: the exported spans of the official and the patched binary differ")
    return detail


def main(argv):
    root = argv[0].rstrip("/")
    lines, bad = [], []
    a = part_a(root, lines, bad)
    b = part_b(root, lines, bad)
    print("\n".join(lines))
    for x in bad:
        print("EVIDENCE FAILED: " + x)
    print("s4_evidence: %s" % ("PASS" if not bad else "FAIL (%d)" % len(bad)))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump({"pass": not bad, "failed": bad, "span_path": a, "export": b, "lines": lines}, f, indent=1, sort_keys=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
