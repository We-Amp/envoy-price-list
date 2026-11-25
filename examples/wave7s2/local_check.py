#!/usr/bin/env python3
"""Local checks of the wave 7 S2 configs with the official Envoy v1.40.2 binary, in Docker, off the bench box
(no measurement).

    python3 examples/wave7s2/local_check.py validate WORKDIR
    python3 examples/wave7s2/local_check.py functional WORKDIR

validate: every arm's bootstrap of every config under `envoy --mode validate` (binary sha256 = the pin).
functional: per config one network namespace with the nginx origin, the stream origin (the linux/amd64
binary the box runs, sha256 checked), Envoy and curl. Per arm and shape: the arm's own client path returns
200 with the right body size; the evidence items that do not need the box's load hold on the counters read
through the leg's own stats filter, on /config_dump and on the stream origin's own counters; the bytes Envoy
read from the origin equal the wire size make.py computes, exactly (HTTP/1.1 arms). The raw bytes are read
directly from the origin as well: `transfer-encoding: chunked`, the chunk sizes, and one origin write per
chunk (its write-call counter; the same count for cl8k). Negative check: the evidence of arm cl fails on a
ch8k leg and the reverse (the evidence tells the arms apart). The HTTP/3 arms use wave 4's stand-in client
(a second Envoy that speaks HTTP/3 or HTTP/2 over TLS to the SUT)."""

import importlib.util
import json
import os
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


w3 = _load("w3f_local", os.path.join(ROOT, "examples", "wave3f", "local_check.py"))
w4 = _load("w4g_local", os.path.join(ROOT, "examples", "wave4g", "local_check.py"))
mk = _load("w7s2_make", os.path.join(HERE, "make.py"))
CFG = os.path.join(HERE, "configs")
VALIDATE = ("smoke-s2a-chunked.json", "smoke-s2b-stream.json", "smoke-s2c-buf.json", "smoke-s2d-h3.json",
            "mech-sys-grpc.json", "mech-sys-buf.json")
STREAM_RUNS = ("smoke-s2a-chunked.json", "smoke-s2b-stream.json", "mech-sys-grpc.json")
N = 20


def prepare(fn, work, sub):
    exp = experiment.load(os.path.join(CFG, fn))
    rd = os.path.join(work, sub, fn[:-5].replace("smoke-", ""))
    os.makedirs(rd, exist_ok=True)
    paths, _, _ = experiment.prepare_bootstraps(exp, rd, make_certs=False)
    w3.make_certs(exp, rd)
    return exp, rd, paths


def validate(work):
    out, bad = {}, 0
    first = True
    for fn in VALIDATE:
        exp, rd, paths = prepare(fn, work, "v")
        if first:
            w3.image_sha256(exp["arms"][0]["source_sha256"])
            first = False
        for key, p in sorted(paths.items()):
            r = w3.sh(["docker", "run", "--rm", "--platform", w3.PLATFORM, "-v", "%s:%s:ro" % (rd, rd), w3.IMAGE,
                       "envoy", "--mode", "validate", "-c", p, "-l", "warn"], timeout=300)
            txt = r.stdout + r.stderr
            ok = r.returncode == 0 and bool(txt.strip()) and "OK" in txt.splitlines()[-1]
            out["%s/%s" % (fn[:-5], key)] = "OK" if ok else txt[-600:]
            bad += 0 if ok else 1
    print(json.dumps(out, indent=1))
    return 1 if bad else 0


class Net(w3.Net):
    """nginx owns the namespace; the stream origin (when the config has one), Envoy and curl join it."""

    def __init__(self, rd, exp):
        os.makedirs(os.path.join(rd, "certs"), exist_ok=True)
        super().__init__(rd, exp)
        o = exp["origin"]
        self.stream_port = o.get("stream_port")
        if self.stream_port:
            binary = origin.stream_binary(o)
            from epl import sysprobe
            got = sysprobe.file_hashes(binary)["sha256"]
            if got != o["stream_sha256"]:
                raise SystemExit("stream origin sha256 %s != %s" % (got, o["stream_sha256"]))
            r = w3.sh(["docker", "run", "-d", "--rm", "--platform", w3.PLATFORM, "--network", "container:" + self.origin,
                       "-v", "%s:/epl-streamorigin:ro" % binary, "--entrypoint", "/epl-streamorigin", w3.NGINX,
                       "-h1", "127.0.0.1:%d" % o["stream_port"], "-h2", "127.0.0.1:%d" % o["stream_h2_port"]])
            if r.returncode:
                raise SystemExit("stream origin: " + r.stderr)
            self.ids.append(r.stdout.strip())
            time.sleep(2.0)

    def so_stats(self):
        try:
            return json.loads(self.text(self.stream_port, "/epl-stats"))
        except ValueError:
            return None


def box_only(it):
    """Items that need the box's load or its leg record: new connections in the window (here every connection
    is new), late events (an emulated binary on a laptop), kernel counters."""
    s = it["stat"]
    if s.startswith("kernel_net.") or s.endswith("late_events"):
        return True
    if it.get("scope", "window") == "window" and s.endswith(("upstream_cx_total", "downstream_cx_total", "ssl.handshake")):
        return True
    return False


def check_evidence(a, m, n, dump):
    out, seen = [], 0
    for it in a.get("evidence", []):
        if box_only(it) or not evidence.applies(it, m["shape"]):
            continue
        if it.get("min") is not None and it["min"] > 1 and it.get("scope") == "leg":
            it = dict(it, min=1)  # the box reaches 16 with its client; curl opens few connections
        if it.get("per") == mk.PER_SO and it["stat"].endswith("responses") is False and "tol" in it and m.get("local_tol"):
            it = dict(it, tol=m["local_tol"])
        r = evidence.check_item(m, it, dump)
        seen += 1
        if not r["ok"]:
            out.append("%s: %s" % (r["label"], r["why"]))
    return out, seen


def curl_n(net, port, path, n, h2=False, per_timeout=30):
    flag = "--http2-prior-knowledge " if h2 else ""
    one = "curl -s %s-m %d -o /tmp/b -D /tmp/h -w '%%{http_code}' 'http://127.0.0.1:%d%s'; echo \" $(wc -c < /tmp/b)\"" % (
        flag, per_timeout, port, path)
    out, _ = net.curl("i=0; while [ $i -lt %d ]; do %s; i=$((i+1)); done; echo ---; tr -d '\\r' < /tmp/h" % (n, one))
    body, _, hdr = out.partition("---\n")
    rs = [(p[0], int(p[1])) for p in (line.split() for line in body.splitlines()) if len(p) == 2]
    return rs, hdr.lower()


def raw_chunks(net, port, path):
    """The origin's raw response to one request, direct: (header text, [chunk sizes]) for a chunked body."""
    out, _ = net.curl("curl -s --raw -D /tmp/h -o /tmp/b 'http://127.0.0.1:%d%s'; tr -d '\\r' < /tmp/h; echo ---; "
                      "tr -d '\\r' < /tmp/b | tr -s 'ax\\n' ' ' " % (port, path))
    hdr, _, body = out.partition("---\n")
    sizes = []
    for tok in body.split():
        try:
            sizes.append(int(tok, 16))
        except ValueError:
            pass
    return hdr.lower(), sizes


def leg_record(st, n, shape, so0=None, so1=None):
    m = {"sut_stats_leg_end": dict(st, **{"http.ingress_http.downstream_rq_completed":
                                          st.get("http.ingress_http.downstream_rq_completed", n)}),
         "sut_stats_leg_end_ok": True, "sut_stats_window": st, "sut_stats_window_ok": True, "responses_raw": n,
         "shape": shape}
    if so0 is not None or so1 is not None:
        m["stream_origin"] = origin.stream_window(so0, so1)
    return m


def stream_functional(fn, work, fails, res):
    exp, rd, paths = prepare(fn, work, "f")
    res[fn] = {}
    net = Net(rd, exp)
    adm, port = exp["envoy"]["admin_port"], exp["envoy"]["listener_port"]
    h2 = exp["envoy"].get("codec_type") == "HTTP2"
    recs = {}
    try:
        for a in exp["arms"]:
            if a["name"].endswith("-A2"):
                continue
            for shape in exp["shapes"]:
                eid = net.envoy(paths[a["name"]])
                tag = "%s/%s" % (a["name"], shape["name"])
                try:
                    if not w3.wait_ready(net, adm):
                        fails.append("%s: not ready: %s" % (tag, net.logs(eid)))
                        continue
                    path = ((a.get("client") or {}).get("paths") or {}).get(shape["name"]) or shape.get("client_path") or shape["path"]
                    n = 5 if shape.get("events", 0) >= 200 else N
                    so0 = net.so_stats()
                    rs, hdr = curl_n(net, port, path, n, h2=h2)
                    so1 = net.so_stats()
                    st = w3.stats(net, adm, exp)
                    dump = json.loads(net.text(adm, "/config_dump"))
                    m = leg_record(st, n, shape["name"], so0, so1)
                    recs[tag] = (m, dump)
                    bad, seen = check_evidence(a, m, n, dump)
                    d = (m["stream_origin"].get("d") or {})
                    rx = st.get("cluster.origin.upstream_cx_rx_bytes_total")
                    rec = {"n": len(rs), "statuses": sorted({r[0] for r in rs}), "bytes": sorted({r[1] for r in rs}),
                           "path": path, "evidence_items_checked": seen, "upstream_rx_bytes_per_request": rx / n if rx else None,
                           "origin": {k: d.get(k) for k in ("responses", "write_calls", "chunks", "events", "body_bytes",
                                                            "wire_bytes", "late_events", "h1_responses", "h2_responses")},
                           "response_framing": "chunked" if "transfer-encoding: chunked" in hdr else
                                               "content-length" if "content-length:" in hdr else "other"}
                    res[fn][tag] = rec
                    if len(rs) != n or any(r[0] != "200" or r[1] != int(shape["body_bytes"]) for r in rs):
                        fails.append("%s: responses %s" % (tag, rec))
                    fails.extend("%s: %s" % (tag, x) for x in bad)
                    upstream_h1 = (a.get("settings") or {}).get("origin_server") == "stream"
                    if upstream_h1 and fn.startswith("smoke-s2a"):
                        c = mk.CHUNK[a["name"]]
                        nb = int(shape["body_bytes"])
                        want = mk.wire_chunked(nb, c) if a["name"].startswith("ch") else mk.wire_cl(nb)
                        if rx != n * want or d.get("wire_bytes") != n * want:
                            fails.append("%s: upstream bytes %s (origin wrote %s), computed %d per request" % (
                                tag, rx, d.get("wire_bytes"), want))
                        # through Envoy the client sees the upstream's framing kind
                        if rec["response_framing"] != ("chunked" if a["name"].startswith("ch") else "content-length"):
                            fails.append("%s: response framing through Envoy: %s" % (tag, rec["response_framing"]))
                    if upstream_h1 and fn.startswith("smoke-s2b"):
                        want = mk.wire_sse(shape["events"])
                        if rx != n * want:
                            fails.append("%s: upstream bytes %s, computed %d per request" % (tag, rx, want))
                finally:
                    net.stop(eid)
        if fn.startswith("smoke-s2a"):
            # direct to the origin: framing, chunk sizes, one write per chunk
            direct = {}
            for an in ("cl", "cl8k", "ch8k", "ch4k"):
                a = [x for x in exp["arms"] if x["name"] == an][0]
                for shape in exp["shapes"]:
                    p = a["client"]["paths"][shape["name"]]
                    nb, c = int(shape["body_bytes"]), mk.CHUNK[an]
                    so0 = net.so_stats()
                    hdr, sizes = raw_chunks(net, exp["origin"]["stream_port"], p)
                    so1 = net.so_stats()
                    d = origin.stream_window(so0, so1)["d"]
                    tag = "direct %s/%s" % (an, shape["name"])
                    direct[tag] = {"write_calls": d["write_calls"], "chunks": d["chunks"], "wire_bytes": d["wire_bytes"],
                                   "chunk_sizes": sorted(set(sizes)), "n_sizes": len(sizes)}
                    if an.startswith("ch"):
                        ok = ("transfer-encoding: chunked" in hdr and "content-length" not in hdr
                              and sizes == [c] * (nb // c) + [0] and d["write_calls"] == nb // c and d["chunks"] == nb // c)
                    else:
                        ok = ("content-length: %d" % nb in hdr and "transfer-encoding" not in hdr
                              and d["write_calls"] == (nb // c if c else 1) and d["chunks"] == 0)
                    if not ok:
                        fails.append("%s: %s (headers %r)" % (tag, direct[tag], hdr[:200]))
            res[fn]["direct"] = direct
            # negative: each arm's evidence fails on the other's leg
            arms = {x["name"]: x for x in exp["arms"]}
            for mine, other in (("cl", "ch8k"), ("ch8k", "cl"), ("cl8k", "ch8k"), ("ch8k", "cl8k"), ("cl", "cl8k"), ("h2in", "cl")):
                m, dump = recs["%s/b64k" % other]
                bad, _ = check_evidence(arms[mine], m, m["responses_raw"], dump)
                res[fn]["negative %s evidence on a %s leg" % (mine, other)] = len(bad)
                if not bad:
                    fails.append("negative: the evidence of %s passes on a %s leg" % (mine, other))
    finally:
        net.close()


def nginx_functional(fn, work, fails, res):
    exp, rd, paths = prepare(fn, work, "f")
    res[fn] = {}
    net = Net(rd, exp)
    adm, port = exp["envoy"]["admin_port"], exp["envoy"]["listener_port"]
    try:
        for a in exp["arms"]:
            if a["name"].endswith("-A2"):
                continue
            for shape in exp["shapes"]:
                if a.get("shapes") and shape["name"] not in a["shapes"]:
                    continue
                eid = net.envoy(paths[a["name"]])
                tag = "%s/%s" % (a["name"], shape["name"])
                try:
                    if not w3.wait_ready(net, adm):
                        fails.append("%s: not ready: %s" % (tag, net.logs(eid)))
                        continue
                    rs, _ = curl_n(net, port, shape["path"], N)
                    st = w3.stats(net, adm, exp)
                    dump = json.loads(net.text(adm, "/config_dump"))
                    m = leg_record(st, N, shape["name"])
                    bad, seen = check_evidence(a, m, N, dump)
                    flow = {k: v for k, v in st.items() if "flow_control" in k}
                    res[fn][tag] = {"n": len(rs), "statuses": sorted({r[0] for r in rs}), "bytes": sorted({r[1] for r in rs}),
                                    "evidence_items_checked": seen, "flow_control_stats": len(flow),
                                    "flow_control_nonzero": {k: v for k, v in flow.items() if v}}
                    if len(rs) != N or any(r[0] != "200" or r[1] != int(shape["body_bytes"]) for r in rs):
                        fails.append("%s: responses %s" % (tag, res[fn][tag]))
                    if len(flow) < 6:
                        fails.append("%s: the flow-control counters are not in the filtered stats (%d)" % (tag, len(flow)))
                    fails.extend("%s: %s" % (tag, x) for x in bad)
                finally:
                    net.stop(eid)
    finally:
        net.close()


def h3_functional(fn, work, fails, res):
    exp, rd, paths = prepare(fn, work, "f")
    res[fn] = {}
    net = Net(rd, exp)
    adm = exp["envoy"]["admin_port"]
    try:
        for a in exp["arms"]:
            if a["name"].endswith("-A2"):
                continue
            sut = net.envoy(paths[a["name"]], workers=4)
            cp, h3 = w4.client_bootstrap(net.rd, exp, a)
            try:
                if not w3.wait_ready(net, adm):
                    fails.append("%s: SUT not ready: %s" % (a["name"], net.logs(sut)))
                    continue
                cli = net.envoy(cp, workers=1)
                if not w3.wait_ready(net, w4.CLIENT_ADMIN):
                    fails.append("%s: client not ready: %s" % (a["name"], net.logs(cli)))
                    continue
                tot = 0
                for shape in exp["shapes"]:
                    rs, _ = curl_n(net, w4.CLIENT_PORT, shape["path"], N)
                    tot += len(rs)
                    res[fn]["%s/%s" % (a["name"], shape["name"])] = {"n": len(rs), "statuses": sorted({r[0] for r in rs}),
                                                                   "bytes": sorted({r[1] for r in rs})}
                    if len(rs) != N or any(r[0] != "200" or r[1] != int(shape["body_bytes"]) for r in rs):
                        fails.append("%s/%s: responses %s" % (a["name"], shape["name"], rs[:3]))
                st = w3.stats(net, adm, exp)
                dump = json.loads(net.text(adm, "/config_dump"))
                for shape in exp["shapes"]:
                    m = leg_record(st, tot, shape["name"])
                    bad, seen = check_evidence(a, m, tot, dump)
                    fails.extend("%s/%s: %s" % (a["name"], shape["name"], x) for x in bad)
                res[fn][a["name"]] = {"h3_cx": st.get("http.ingress_http.downstream_cx_http3_total"),
                                      "h2_cx": st.get("http.ingress_http.downstream_cx_http2_total"), "evidence_items_checked": seen}
                net.stop(cli)
            finally:
                net.stop(sut)
    finally:
        net.close()


def functional(work, only=None):
    fails, res = [], {}
    for fn in STREAM_RUNS:
        if not only or only in fn:
            stream_functional(fn, work, fails, res)
    if not only or only in "mech-sys-buf.json":
        nginx_functional("mech-sys-buf.json", work, fails, res)
    if not only or only in "smoke-s2d-h3.json":
        h3_functional("smoke-s2d-h3.json", work, fails, res)
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
