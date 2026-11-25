#!/usr/bin/env python3
"""Compare the spans two Envoy binaries exported, as the collector's debug exporter printed them (verbosity
detailed, one block per span).

    span_compare.py LOG_A LOG_B [EXPECT_A EXPECT_B]     exit 0 when the two logs hold the same spans

Each span block is reduced to a signature: its lines in order (name, kind, parent id, status, every attribute
key and value in the order printed, events), with what must differ between any two spans masked: the trace id
and span id (checked for their form: 32 and 16 lower-case hex digits), start and end time, event timestamps,
and the values of the attributes that are per-request (at least half of the spans of each log carry a value
of their own; reported by name: the request id). An attribute with a few values stays in the signature. The resource attributes and the instrumentation scope name
are part of the signature; the scope VERSION and the resource attribute telemetry.sdk.version are masked and
reported (both are the build's version string, which names the commit).

Same spans = both logs hold at least one span, the set of signatures is equal, every signature has the same
share of the spans within 2 points, every id is well-formed and unique, and (with EXPECT_*) each log holds
the expected number of spans within 1%."""
import collections
import re
import sys

SPAN = re.compile(r"^Span #\d+\s*$")
FIELD = re.compile(r"^\s+(Trace ID|Parent ID|ID|Name|Kind|Start time|End time|Status code|Status message|TraceState|Flags)\s*:\s?(.*)$")
ATTR = re.compile(r"^\s+-> ([^:]+(?::[^ ][^:]*)*?): (.*)$")
LOGLINE = re.compile(r"^\d{4}-\d\d-\d\dT")
HEX32, HEX16 = re.compile(r"^[0-9a-f]{32}$"), re.compile(r"^[0-9a-f]{16}$")


def parse(path):
    """[span]: {"fields": {name: value}, "lines": [(kind, key, value)], "resource": tuple, "scope": str}."""
    spans, cur, res, scope, mode = [], None, [], "", None
    with open(path, errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if LOGLINE.match(line) or line.startswith("\t{"):
                if "ResourceSpans #" not in line:
                    cur, mode = None, None
                    continue
                line = line[line.index("ResourceSpans #"):]
            if line.startswith("ResourceSpans #"):
                cur, res, scope, mode = None, [], "", "resource"
                continue
            if line.startswith("ScopeSpans #"):
                cur, mode = None, "scope"
                continue
            if line.startswith("InstrumentationScope"):
                scope = line
                continue
            if SPAN.match(line):
                cur = {"fields": {}, "lines": [], "resource": tuple(res), "scope": scope}
                spans.append(cur)
                mode = "span"
                continue
            if cur is None:
                m = ATTR.match(line)
                if m and mode == "resource":
                    res.append((m.group(1), m.group(2)))
                continue
            m = FIELD.match(line)
            if m:
                cur["fields"][m.group(1)] = m.group(2).strip()
                cur["lines"].append(("field", m.group(1), m.group(2).strip()))
                continue
            m = ATTR.match(line)
            if m:
                cur["lines"].append(("attr", m.group(1), m.group(2)))
            elif line.strip():
                cur["lines"].append(("text", line.strip(), ""))
    return spans


MASK_FIELDS = ("Trace ID", "ID", "Start time", "End time")


def volatile_keys(spans):
    vals = collections.defaultdict(set)
    for s in spans:
        for kind, k, v in s["lines"]:
            if kind == "attr":
                vals[k].add(v)
    return {k: len(v) for k, v in vals.items() if len(v) > 1}


def signature(s, vol):
    out = [("resource",) + tuple((k, "<version>" if k == "telemetry.sdk.version" else v) for k, v in s["resource"]),
           ("scope", re.sub(r"^(InstrumentationScope \S+).*$", r"\1 <version>", s["scope"]))]
    for kind, k, v in s["lines"]:
        if kind == "field" and k in MASK_FIELDS:
            v = "<masked>"
        elif kind == "attr" and k in vol:
            v = "<varies>"
        elif kind == "text":
            k = re.sub(r"(Timestamp\s*:\s*).*$", r"\1<masked>", k)
        out.append((kind, k, v))
    return tuple(out)


def ids_ok(spans):
    bad = [s for s in spans if not HEX32.match(s["fields"].get("Trace ID", "")) or not HEX16.match(s["fields"].get("ID", ""))]
    tids = {s["fields"].get("Trace ID") for s in spans}
    sids = {s["fields"].get("ID") for s in spans}
    return len(bad), len(tids), len(sids)


def compare(pa, pb, expect_a=None, expect_b=None):
    A, B = parse(pa), parse(pb)
    lines, ok = [], True
    # per-request values only: a key is masked when at least half of the spans of EACH log carry a value of
    # their own; a key with a few values stays in the signature (so a changed value is a different span)
    va, vb = volatile_keys(A), volatile_keys(B)
    vol = {k: max(va[k], vb[k]) for k in va if k in vb and 2 * va[k] >= len(A) and 2 * vb[k] >= len(B)}
    ca = collections.Counter(signature(s, vol) for s in A)
    cb = collections.Counter(signature(s, vol) for s in B)
    lines.append("spans: A %d, B %d (expected %s, %s); distinct signatures: A %d, B %d" % (
        len(A), len(B), expect_a, expect_b, len(ca), len(cb)))
    if not A or not B:
        return False, lines + ["FAIL: a log holds no span"], {}
    for name, spans, exp in (("A", A, expect_a), ("B", B, expect_b)):
        bad, nt, ns = ids_ok(spans)
        lines.append("%s: ill-formed ids %d; distinct trace ids %d, span ids %d of %d spans; parent ids set: %d; scope: %s; "
                     "telemetry.sdk.version: %s" % (
                         name, bad, nt, ns, len(spans), sum(1 for s in spans if s["fields"].get("Parent ID")), spans[0]["scope"],
                         dict(spans[0]["resource"]).get("telemetry.sdk.version")))
        if bad or nt != len(spans) or ns != len(spans):
            ok = False
            lines.append("FAIL: %s ids ill-formed or not unique" % name)
        if exp is not None and abs(len(spans) - exp) > max(1.0, 0.01 * exp):
            ok = False
            lines.append("FAIL: %s holds %d spans, expected %d within 1%%" % (name, len(spans), exp))
    lines.append("per-request attributes (masked; largest count of distinct values): %s" % (
        ", ".join("%s (%d)" % kv for kv in sorted(vol.items())) or "none"))
    if set(ca) != set(cb):
        ok = False
        lines.append("FAIL: signatures only in A: %d, only in B: %d" % (len(set(ca) - set(cb)), len(set(cb) - set(ca))))
        for name, only in (("A", set(ca) - set(cb)), ("B", set(cb) - set(ca))):
            for sig in list(only)[:2]:
                lines.append("  only in %s: %s" % (name, " | ".join("%s=%s" % (k, v) for _, k, v in sig[2:])[:1500]))
    for sig in sorted(set(ca) | set(cb), key=lambda x: -ca.get(x, 0)):
        sa, sb = 100.0 * ca.get(sig, 0) / len(A), 100.0 * cb.get(sig, 0) / len(B)
        if abs(sa - sb) > 2.0:
            ok = False
            lines.append("FAIL: a signature's share differs: A %.2f%%, B %.2f%%" % (sa, sb))
    top = ca.most_common(1)[0][0]
    lines.append("most common signature (A %.2f%%, B %.2f%% of the spans): %s" % (
        100.0 * ca[top] / len(A), 100.0 * cb.get(top, 0) / len(B),
        " | ".join(("%s=%s" % (k, v)) if kind != "text" else k for kind, k, v in top[2:])))
    lines.append("resource attributes: %s" % (top[0][1:],))
    lines.append("span_compare: %s" % ("SAME" if ok else "DIFFERENT"))
    return ok, lines, {"a": len(A), "b": len(B), "signatures_a": len(ca), "signatures_b": len(cb), "volatile": vol}


def main(argv):
    if len(argv) not in (2, 4):
        print(__doc__)
        return 2
    ea, eb = (float(argv[2]), float(argv[3])) if len(argv) == 4 else (None, None)
    ok, lines, _ = compare(argv[0], argv[1], ea, eb)
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
