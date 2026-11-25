#!/usr/bin/env python3
"""Local checks of the wave 7 S4 configs, in Docker, off the bench box (no measurement).

    python3 examples/wave7s4/local_check.py validate WORKDIR BINDIR
    python3 examples/wave7s4/local_check.py functional WORKDIR BINDIR [s4a|s4b|span|export]

BINDIR holds the built binaries under the file names of bins.json (envoy-otel-dfs, envoy-otel-dfs.unstripped,
envoy-pgolto, envoy-pgolto-tests); each is checked against its pinned sha256 before use. The official arm runs
the binary of the envoyproxy/envoy:v1.40.2 image (sha256 = the pin).

validate    every arm's bootstrap of every config under `--mode validate` of that arm's own binary.
functional  one network namespace with the nginx origin, the pinned collector, Envoy and curl. Per arm and
            shape: N keep-alive requests return 200 with the right body size; the arm's evidence holds on the
            counters read through the leg's own stats filter and on /config_dump (items that need the box's
            load or a frozen reference are skipped; the reference item is checked here by hand: upstream
            request bytes per request against the no-tracer arm). The local origin echoes the traceparent
            header it received in a response header (local only: the box's origin is not changed), so the
            header's presence, its flag and its handling of an incoming header are read per arm. Negative
            checks: each arm's evidence fails on the leg of the arm it must be told apart from.
            export: both 100% arms; the collector's printed spans are compared by span_compare.py.
"""

import hashlib
import importlib.util
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import envoy_config, evidence, experiment, origin  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


w3 = _load("w3f_local4", os.path.join(ROOT, "examples", "wave3f", "local_check.py"))
s3 = _load("w7s3_local4", os.path.join(ROOT, "examples", "wave7s3", "local_check.py"))
cmp_ = _load("w7s4_span_compare", os.path.join(HERE, "span_compare.py"))
CFG = os.path.join(HERE, "configs")
ALL = ("smoke-s4a-otel.json", "smoke-s4b-pgo.json", "ev-span-path.json", "ev-export.json")
N = 400
TX = "cluster.origin.upstream_cx_tx_bytes_total"
SEEN = "x-seen-traceparent"


def local_bins(bindir):
    """{build: local path or None (the image's own binary)}; every file's sha256 equals its pin."""
    with open(os.path.join(HERE, "bins.json")) as f:
        bins = json.load(f)
    out = {}
    for k, b in bins.items():
        if k == "official":
            out[k] = None
            continue
        p = os.path.join(bindir, os.path.basename(b["binary"]))
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for blk in iter(lambda: f.read(1 << 20), b""):
                h.update(blk)
        if h.hexdigest() != b["source_sha256"]:
            raise SystemExit("%s: sha256 %s != pin %s" % (p, h.hexdigest(), b["source_sha256"]))
        out[k] = p
    return out


def prepare(fn, work, sub):
    exp = experiment.load(os.path.join(CFG, fn))
    rd = os.path.join(work, sub, fn[:-5])
    os.makedirs(os.path.join(rd, "certs"), exist_ok=True)
    paths, _, _ = experiment.prepare_bootstraps(exp, rd, make_certs=False)
    return exp, rd, paths


def validate(work, bindir):
    bins = local_bins(bindir)
    out, bad = {}, 0
    w3.image_sha256("1d64506e25c1844f146162ddb2ece7010fa4e784faddb40a079021491f1f03cc")
    for fn in ALL:
        exp, rd, paths = prepare(fn, work, "v")
        arms = {a["name"]: a for a in exp["arms"]}
        for key, p in sorted(paths.items()):
            b = bins[arms[key]["build"]]
            mount = ["-v", "%s:/epl-envoy:ro" % b] if b else []
            r = w3.sh(["docker", "run", "--rm", "--platform", w3.PLATFORM, "-e", "ENVOY_UID=0", "-v", "%s:%s" % (rd, rd)]
                      + mount + [w3.IMAGE, "/epl-envoy" if b else "envoy", "--mode", "validate", "-c", p, "-l", "warn"],
                      timeout=600)
            txt = r.stdout + r.stderr
            ok = r.returncode == 0 and bool(txt.strip()) and "OK" in txt.splitlines()[-1]
            out["%s/%s (%s)" % (fn[:-5], key, arms[key]["build"])] = "OK" if ok else txt[-900:]
            bad += 0 if ok else 1
    print(json.dumps(out, indent=1))
    return 1 if bad else 0


class Net(s3.Net):
    """As S3's (nginx origin, collector with the harness's own config), with an arm's own binary mounted, and
    the origin echoing the traceparent header it received (local check only)."""

    def __init__(self, rd, exp):
        c = exp.get("collector") or {}
        self._debug = bool(c.get("debug_spans"))
        orig = envoy_config.nginx_conf

        def conf(*a, **kw):
            return orig(*a, **kw).replace("http {", "http {\n    add_header %s $http_traceparent always;\n"
                                          "    add_header x-seen-tracestate $http_tracestate always;" % SEEN, 1)
        envoy_config.nginx_conf = conf
        oc = origin.collector_conf
        if self._debug:
            origin.collector_conf = lambda *a, **kw: oc(*a, debug_spans=True)
        try:
            super().__init__(rd, exp)
        finally:
            envoy_config.nginx_conf = orig
            origin.collector_conf = oc
        self.collector_id = self.ids[-1] if len(self.ids) > 1 else None

    def envoy_bin(self, bpath, binary, workers=2):
        mount = ["-v", "%s:/epl-envoy:ro" % binary] if binary else []
        r = w3.sh(["docker", "run", "-d", "--rm", "--platform", w3.PLATFORM, "--network", "container:" + self.origin,
                   "-e", "ENVOY_UID=0", "-v", "%s:%s" % (self.rd, self.rd)] + mount +
                  [w3.IMAGE, "/epl-envoy" if binary else "envoy", "-c", bpath, "--concurrency", str(workers),
                   "-l", "warn", "--use-dynamic-base-id"])
        if r.returncode:
            raise SystemExit("envoy: " + r.stderr)
        self.ids.append(r.stdout.strip())
        return self.ids[-1]

    def collector_log(self):
        r = w3.sh(["docker", "logs", self.collector_id])
        return r.stdout + r.stderr


def box_only(it):
    if "ref" in it:
        return True
    if it.get("scope") == "field" and it["stat"] == "collector_delta.accepted_spans" and "max" in it and it.get("max") != 0 \
            and it.get("min", 0) < 0.5:
        return True  # the 1% share: a few hundred local requests give a handful of spans
    if it.get("tol_binomial_sd"):
        return True
    return it.get("scope", "window") == "window" and it["stat"].endswith("upstream_cx_total")


def check_evidence(a, m, dump):
    out, seen = [], 0
    for it in a.get("evidence", []):
        if box_only(it) or not evidence.applies(it, m["shape"]):
            continue
        r = evidence.check_item(m, it, dump)
        seen += 1
        if not r["ok"]:
            out.append("%s: %s" % (r["label"], r["why"]))
    return out, seen


def seen_headers(net, port, path, extra=""):
    out, _ = net.curl("curl -s -D - -o /dev/null %s 'http://127.0.0.1:%d%s'" % (extra, port, path))
    return {k.lower(): v.strip() for k, _, v in (x.partition(":") for x in out.splitlines()) if k.lower().startswith("x-seen")}


def one_leg(net, exp, rd, paths, a, shape, n, fails, res, bins):
    adm, port = exp["envoy"]["admin_port"], exp["envoy"]["listener_port"]
    tag = "%s/%s" % (a["name"], shape["name"])
    eid = net.envoy_bin(paths[a["name"]], bins[a["build"]])
    try:
        if not w3.wait_ready(net, adm, 180):
            fails.append("%s: not ready: %s" % (tag, net.logs(eid)))
            return None
        c0 = net.scrape()
        rs = s3.keepalive_requests(net, port, shape, n)
        time.sleep(8.0)  # the tracer's flush
        st = w3.stats(net, adm, exp)
        allst = net.text(adm, "/stats")
        dump = json.loads(net.text(adm, "/config_dump"))
        rt = net.text(adm, "/runtime")
        c1 = net.scrape()
        m = {"sut_stats_leg_end": st, "sut_stats_leg_end_ok": True, "sut_stats_window": st, "sut_stats_window_ok": True,
             "responses_raw": n, "shape": shape["name"]}
        if c0 is not None and c1 is not None:
            m["collector_delta"] = {k: c1.get(k, 0) - c0.get(k, 0) for k in set(c0) | set(c1)}
        bad, seen = check_evidence(a, m, dump)
        rec = {"n": len(rs), "statuses": sorted({r[0] for r in rs}), "bytes": sorted({r[1] for r in rs}),
               "evidence_items_checked": seen, "collector_delta": m.get("collector_delta"),
               "tx_bytes_per_request": st.get(TX, 0) / float(n),
               "tracing_stats": {k: v for k, v in (x.split(": ", 1) for x in allst.splitlines() if ": " in x)
                                 if ("tracing" in k or k.startswith("cluster.otel_collector.upstream_rq_total"))
                                 and " P0(" not in v},
               "runtime_stats": {k: v for k, v in st.items() if k.startswith("runtime.")},
               "runtime_dump": json.loads(rt) if rt.strip().startswith("{") else rt[:200]}
        if shape["kind"] == "proxied":
            # after the counters were read: what the origin saw (fresh ids; an incoming sampled header)
            rec["origin_saw"] = seen_headers(net, port, shape["path"])
            rec["origin_saw_with_incoming"] = seen_headers(
                net, port, shape["path"], "-H 'traceparent: 00-0AF7651916CD43DD8448EB211C80319C-b7ad6b7169203331-01' "
                                          "-H 'tracestate: congo=t61rcWkgMzE'")
        res[tag] = rec
        if len(rs) != n or any(r[0] != "200" or r[1] != int(shape["body_bytes"]) for r in rs):
            fails.append("%s: responses %s %s (n %d)" % (tag, rec["statuses"], rec["bytes"], len(rs)))
        fails.extend("%s: %s" % (tag, x) for x in bad)
        return m, dump, rec
    finally:
        net.stop(eid)


NEGATIVE = [("notrace", "stock-0"), ("stock-0", "notrace"), ("stock-0", "stock-1"), ("stock-1", "stock-0"),
            ("patched-0", "patched-0-guard-off"), ("patched-0-guard-off", "patched-0"), ("patched-0", "patched-1"),
            ("patched-notrace", "patched-0"), ("patched-0", "patched-notrace")]
TP = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-(00|01)$")


def run_arms(fn, work, bins, fails, res, skip_a2=True, n=N):
    exp, rd, paths = prepare(fn, work, "f")
    res[fn] = {}
    net = Net(rd, exp)
    recs = {}
    try:
        for a in exp["arms"]:
            if skip_a2 and a["name"].endswith("-A2"):
                continue
            for shape in exp["shapes"]:
                r = one_leg(net, exp, rd, paths, a, shape, n, fails, res[fn], bins)
                if r:
                    recs[(a["name"], shape["name"])] = r
    finally:
        net.close()
    return exp, recs


def functional(work, bindir, only=None):
    bins = local_bins(bindir)
    fails, res = [], {}
    if only in (None, "s4a"):
        fn = "smoke-s4a-otel.json"
        exp, recs = run_arms(fn, work, bins, fails, res)
        arms = {x["name"]: x for x in exp["arms"]}
        for mine, other in NEGATIVE:
            if (other, "s") not in recs:
                fails.append("negative %s on %s: no leg" % (mine, other))
                continue
            m, dump, _ = recs[(other, "s")]
            bad, _ = check_evidence(arms[mine], m, dump)
            res[fn]["negative: %s evidence on a %s leg fails items" % (mine, other)] = len(bad)
            if not bad:
                fails.append("negative: the evidence of %s passes on a %s leg" % (mine, other))
        # the reference item by hand: upstream request bytes per request against the no-tracer arm, and
        # what the origin saw
        base = recs.get(("notrace", "s"))
        for (an, sh), (_, _, rec) in sorted(recs.items()):
            if sh != "s" or not base:
                continue
            tracer = bool((arms[an].get("settings") or {}).get("tracing"))
            d = rec["tx_bytes_per_request"] - base[2]["tx_bytes_per_request"]
            res[fn]["tx bytes per request, %s minus notrace" % an] = round(d, 3)
            want = 84 if tracer else 0
            if abs(d - want) > 0.5:
                fails.append("%s: upstream request bytes per request differ from notrace by %.3f, expected %d" % (an, d, want))
            saw = rec.get("origin_saw", {}).get(SEEN)
            inc = rec.get("origin_saw_with_incoming", {})
            if tracer:
                if not saw or not TP.match(saw):
                    fails.append("%s: the origin saw traceparent %r" % (an, saw))
                elif arms[an]["settings"]["tracing"]["sampling_pct"] == 0 and not saw.endswith("-00"):
                    fails.append("%s: traceparent flag %r at this sampling rate" % (an, saw))
                i = inc.get(SEEN, "")
                if not i.startswith("00-0af7651916cd43dd8448eb211c80319c-") or i.endswith("b7ad6b7169203331-01") \
                        or inc.get("x-seen-tracestate") != "congo=t61rcWkgMzE":
                    fails.append("%s: with an incoming header the origin saw %r %r" % (an, i, inc.get("x-seen-tracestate")))
            elif saw:
                fails.append("%s: the origin saw a traceparent without a tracer: %r" % (an, saw))
        # stock and patched read alike on every tracer counter and on what the origin saw with an incoming header
        for a, b in (("stock-0", "patched-0"), ("stock-0", "patched-0-guard-off"), ("stock-1", "patched-1")):
            ra, rb = recs.get((a, "s")), recs.get((b, "s"))
            if ra and rb:
                fa = ra[2]["origin_saw_with_incoming"].get(SEEN, "")[-3:]
                fb = rb[2]["origin_saw_with_incoming"].get(SEEN, "")[-3:]
                res[fn]["incoming sampled header, flag sent on: %s / %s" % (a, b)] = "%s / %s" % (fa, fb)
                if fa != fb:
                    fails.append("%s and %s send a different flag on for an incoming sampled header" % (a, b))
    if only in (None, "s4b"):
        run_arms("smoke-s4b-pgo.json", work, bins, fails, res, n=100)
    if only in (None, "span"):
        run_arms("ev-span-path.json", work, bins, fails, res, skip_a2=False, n=100)
    if only in (None, "export"):
        fn = "ev-export.json"
        exp, rd, paths = prepare(fn, work, "f")
        res[fn] = {}
        logs = {}
        for a in exp["arms"]:
            net = Net(rd, exp)  # a collector of its own per arm, so its log holds this arm's spans only
            try:
                one_leg(net, exp, rd, paths, a, exp["shapes"][0], 300, fails, res[fn], bins)
                time.sleep(8.0)  # the tracer flushes every 5 s: the two header-check requests are in both logs
                p = os.path.join(rd, "%s.spans.log" % a["name"])
                with open(p, "w") as f:
                    f.write(net.collector_log())
                logs[a["name"]] = p
            finally:
                net.close()
        if len(logs) == 2:
            ok, lines, _ = cmp_.compare(logs["stock-100"], logs["patched-100"], 302, 302)
            res[fn]["span_compare"] = lines
            if not ok:
                fails.append("export: the spans of stock-100 and patched-100 differ")
            # negative: a log against a copy with one attribute value changed must differ
            with open(logs["patched-100"]) as f:
                t = f.read()
            alt = os.path.join(rd, "altered.spans.log")
            with open(alt, "w") as f:
                f.write(t.replace("-> http.status_code: Str(200)", "-> http.status_code: Str(201)", 1))
            ok2, _, _ = cmp_.compare(logs["stock-100"], alt, 302, 302)
            res[fn]["negative: one altered attribute value is caught"] = not ok2
            if ok2:
                fails.append("export negative: an altered span was not caught")
    print(json.dumps({"results": res, "failed": fails}, indent=1, sort_keys=True))
    return 1 if fails else 0


def main(argv):
    if len(argv) not in (3, 4) or argv[0] not in ("validate", "functional"):
        print(__doc__)
        return 2
    work = os.path.abspath(argv[1])
    os.makedirs(work, exist_ok=True)
    if argv[0] == "validate":
        return validate(work, argv[2])
    return functional(work, argv[2], argv[3] if len(argv) == 4 else None)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
