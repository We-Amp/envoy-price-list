#!/usr/bin/env python3
"""Local checks of the wave 7 S3 configs with the official Envoy v1.40.2 binary, in Docker, off the bench box
(no measurement).

    python3 examples/wave7s3/local_check.py validate WORKDIR
    python3 examples/wave7s3/local_check.py functional WORKDIR [s3a|s3b]

validate: every arm's bootstrap of both run configs under `envoy --mode validate` (binary sha256 = the pin).
functional: per config one network namespace with the nginx origin, the pinned OpenTelemetry collector (s3a,
with the harness's own collector config), Envoy and curl. Per arm and shape: N keep-alive requests with the
shape's own request headers return 200 with the right body size, and the arm's evidence holds on the counters
read through the leg's own stats filter, on /config_dump, on the access-log file, on the collector's own
counters and on the namespace's UDP counters (statsd datagrams per request: no listener is needed, the
kernel counts a datagram sent to a closed loopback port). Items that need the box's load are skipped (new
upstream connections in the window: here every connection is new). Negative checks: each arm's evidence fails
on the leg of the arm it must be told apart from. The inert-filter arms also list every stat of the ten
filters with its value (the source of make.py's INERT_ACTION names)."""

import importlib.util
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import evidence, experiment, origin  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


w3 = _load("w3f_local", os.path.join(ROOT, "examples", "wave3f", "local_check.py"))
mk = _load("w7s3_make", os.path.join(HERE, "make.py"))
CFG = os.path.join(HERE, "configs")
RUNS = ("smoke-s3a-stack.json", "smoke-s3b-chain.json")
N = {"smoke-s3a-stack.json": 800, "smoke-s3b-chain.json": 40}
INERT_STAT = re.compile(r"cors|fault|rbac|csrf|health|header_mutation|grpc_web|grpc_http1|stateful|bandwidth|epl_inert")


def prepare(fn, work, sub):
    exp = experiment.load(os.path.join(CFG, fn))
    rd = os.path.join(work, sub, fn[:-5].replace("smoke-", ""))
    os.makedirs(os.path.join(rd, "certs"), exist_ok=True)
    os.makedirs(os.path.join(rd, "alog"), exist_ok=True)
    paths, _, _ = experiment.prepare_bootstraps(exp, rd, make_certs=False)
    return exp, rd, paths


def validate(work):
    out, bad = {}, 0
    first = True
    for fn in RUNS:
        exp, rd, paths = prepare(fn, work, "v")
        if first:
            w3.image_sha256(exp["arms"][0]["source_sha256"])
            first = False
        for key, p in sorted(paths.items()):
            r = w3.sh(["docker", "run", "--rm", "--platform", w3.PLATFORM, "-e", "ENVOY_UID=0", "-v", "%s:%s" % (rd, rd), w3.IMAGE,
                       "envoy", "--mode", "validate", "-c", p, "-l", "warn"], timeout=300)
            txt = r.stdout + r.stderr
            ok = r.returncode == 0 and bool(txt.strip()) and "OK" in txt.splitlines()[-1]
            out["%s/%s" % (fn[:-5], key)] = "OK" if ok else txt[-900:]
            bad += 0 if ok else 1
    print(json.dumps(out, indent=1))
    return 1 if bad else 0


class Net(w3.Net):
    """nginx owns the namespace; the collector (when the config has one), Envoy and curl join it."""

    def __init__(self, rd, exp):
        super().__init__(rd, exp)
        self.metrics_port = None
        c = exp.get("collector") or {}
        if c.get("image") and experiment.needs_collector(exp):
            d = os.path.join(rd, "collector")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "config.yaml"), "w") as f:
                f.write(origin.collector_conf(int(c["port"]), c.get("metrics_port"), bool(c.get("metrics")),
                                              c.get("max_recv_msg_size_mib")))
            r = w3.sh(["docker", "run", "-d", "--rm", "--network", "container:" + self.origin,
                       "-v", "%s:/etc/epl-collector.yaml:ro" % os.path.join(d, "config.yaml"),
                       c["image"], "--config", "/etc/epl-collector.yaml"])
            if r.returncode:
                raise SystemExit("collector: " + r.stderr)
            self.ids.append(r.stdout.strip())
            self.metrics_port = c.get("metrics_port")
            time.sleep(4.0)

    def scrape(self):
        if not self.metrics_port:
            return None
        return origin.parse_collector_metrics(self.text(self.metrics_port, "/metrics"))

    def udp_out(self):
        out, _ = self.curl("cat /proc/net/snmp")
        rows = [x.split() for x in out.splitlines() if x.startswith("Udp:")]
        if len(rows) < 2:
            return None
        return dict(zip(rows[0][1:], (int(v) for v in rows[1][1:])))["OutDatagrams"]


def header_args(shape):
    a = shape.get("client_extra_args") or []
    return " ".join("-H '%s'" % a[i + 1].replace(":", ": ", 1) for i in range(len(a) - 1) if a[i] == "--request-header")


def keepalive_requests(net, port, shape, n):
    """n requests on one keep-alive connection (one curl process, the URL repeated); [(status, bytes)]."""
    url = "http://127.0.0.1:%d%s" % (port, shape["path"])
    script = ("i=0; args=''; while [ $i -lt %d ]; do args=\"$args -o /dev/null %s\"; i=$((i+1)); done; "
              "curl -s %s -w '%%{http_code} %%{size_download}\\n' $args" % (n, url, header_args(shape)))
    out, _ = net.curl(script)
    return [(p[0], int(p[1])) for p in (line.split() for line in out.splitlines()) if len(p) == 2]


def box_only(it):
    """Items that need the box's load: new upstream connections in the window (here every connection is new),
    and the 1% span share (a few hundred local requests give a handful of spans)."""
    if it.get("scope") == "field" and it["stat"] == "collector_delta.accepted_spans" and "max" in it:
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


def one_leg(net, exp, rd, paths, a, shape, n, fails, res, fn):
    adm, port = exp["envoy"]["admin_port"], exp["envoy"]["listener_port"]
    tag = "%s/%s" % (a["name"], shape["name"])
    alog = os.path.join(rd, "alog", a["name"] + ".alog")
    if os.path.exists(alog):
        os.unlink(alog)
    eid = net.envoy(paths[a["name"]])
    try:
        if not w3.wait_ready(net, adm):
            fails.append("%s: not ready: %s" % (tag, net.logs(eid)))
            return None
        c0, u0 = net.scrape(), net.udp_out()
        rs = keepalive_requests(net, port, shape, n)
        time.sleep(8.0 if net.metrics_port else 1.5)  # the tracer's and the stats sink's flush, the log's flush
        st = w3.stats(net, adm, exp)
        allst = net.text(adm, "/stats")
        dump = json.loads(net.text(adm, "/config_dump"))
        c1, u1 = net.scrape(), net.udp_out()
        with open(os.path.join(rd, "stats-%s-%s.txt" % (a["name"], shape["name"])), "w") as f:
            f.write(allst)
        net.stop(eid)  # the access log's last lines are written when Envoy exits (as on the box)
        m = {"sut_stats_leg_end": st, "sut_stats_leg_end_ok": True, "sut_stats_window": st, "sut_stats_window_ok": True,
             "responses_raw": n, "shape": shape["name"]}
        if u0 is not None and u1 is not None:
            m["kernel_net"] = {"d": {"UdpOutDatagrams": u1 - u0}}
            if (a.get("settings") or {}).get("stats_sink", {}).get("kind") == "statsd":
                m["udp"] = {"datagrams_per_request": (u1 - u0) / float(n)}
        if c0 is not None and c1 is not None:
            m["collector_delta"] = {k: c1.get(k, 0) - c0.get(k, 0) for k in set(c0) | set(c1)}
        if os.path.exists(alog):
            with open(alog) as f:
                lines = f.read().splitlines()
            m["access_log_lines"] = len(lines)
            m["access_log_bytes_per_line"] = sum(len(x) + 1 for x in lines) / float(len(lines)) if lines else None
            js = 0
            for x in lines[:100] + lines[-100:]:
                try:
                    js += 1 if isinstance(json.loads(x), dict) else 0
                except ValueError:
                    pass
            m["access_log_json_ok"] = bool(lines) and js == len(lines[:100] + lines[-100:])
            m["access_log_first"] = lines[0][:200] if lines else None
        bad, seen = check_evidence(a, m, dump)
        names = [f["name"].rsplit(".", 1)[-1] for f in evidence.config_values(dump, "http_filters")[0]]
        rec = {"n": len(rs), "statuses": sorted({r[0] for r in rs}), "bytes": sorted({r[1] for r in rs}),
               "evidence_items_checked": seen, "http_filters": names, "stats_total": len(allst.splitlines()),
               "udp_out_per_request": (u1 - u0) / float(n) if u0 is not None and u1 is not None else None,
               "collector_delta": m.get("collector_delta"), "access_log_lines": m.get("access_log_lines"),
               "access_log_first": m.get("access_log_first"),
               "histogram_names": sorted({x.split(":")[0] for x in allst.splitlines() if " P0(" in x})[:40]}
        if "s3b" in fn:
            rec["inert_stats"] = {k: v for k, v in (x.split(": ", 1) for x in allst.splitlines() if ": " in x)
                                  if INERT_STAT.search(k) and " P0(" not in v}
        res[fn][tag] = rec
        if len(rs) != n or any(r[0] != "200" or r[1] != int(shape["body_bytes"]) for r in rs):
            fails.append("%s: responses %s %s (n %d)" % (tag, rec["statuses"], rec["bytes"], len(rs)))
        if rec["stats_total"] >= 2000:
            fails.append("%s: %d stats, expected under 2,000" % (tag, rec["stats_total"]))
        fails.extend("%s: %s" % (tag, x) for x in bad)
        return m, dump
    finally:
        net.stop(eid)


NEGATIVE = {"smoke-s3a-stack.json": [("typical", "typical-nosink"), ("typical-nosink", "typical"), ("bare", "typical"),
                                     ("typical", "bare"), ("lean", "typical"), ("typical", "lean"),
                                     ("lean", "typical-nosink"), ("typical-nosink", "lean"), ("bare", "lean")],
            "smoke-s3b-chain.json": [("f0", "f10"), ("f10", "f0"), ("f10-off", "f10"), ("f10", "f10-off"), ("f0", "f10-off"),
                                     ("idle-off", "f0"), ("f0", "idle-off"), ("idle-off", "timers-off-all"),
                                     ("timers-off-all", "idle-off"), ("f0", "timers-off-all")]}


def functional(work, only=None):
    fails, res = [], {}
    for fn in RUNS:
        if only and only not in fn:
            continue
        exp, rd, paths = prepare(fn, work, "f")
        res[fn] = {}
        net = Net(rd, exp)
        recs = {}
        try:
            for a in exp["arms"]:
                if a["name"].endswith("-A2"):
                    continue
                for shape in exp["shapes"]:
                    r = one_leg(net, exp, rd, paths, a, shape, N[fn], fails, res, fn)
                    if r:
                        recs[(a["name"], shape["name"])] = r
            arms = {x["name"]: x for x in exp["arms"]}
            sh0 = exp["shapes"][0]["name"]
            for mine, other in NEGATIVE[fn]:
                if (other, sh0) not in recs:
                    fails.append("negative %s on %s: no leg" % (mine, other))
                    continue
                m, dump = recs[(other, sh0)]
                bad, _ = check_evidence(arms[mine], m, dump)
                res[fn]["negative: %s evidence on a %s leg fails items" % (mine, other)] = len(bad)
                if not bad:
                    fails.append("negative: the evidence of %s passes on a %s leg" % (mine, other))
        finally:
            net.close()
    print(json.dumps({"results": res, "failed": fails}, indent=1, sort_keys=True))
    return 1 if fails else 0


def main(argv):
    if len(argv) not in (2, 3) or argv[0] not in ("validate", "functional"):
        print(__doc__)
        return 2
    work = os.path.abspath(argv[1])
    os.makedirs(work, exist_ok=True)
    return validate(work) if argv[0] == "validate" else functional(work, argv[2] if len(argv) == 3 else None)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
