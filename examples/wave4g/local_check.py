#!/usr/bin/env python3
"""Local checks of the track G configs with the official Envoy v1.40.2 binary, in Docker, off the bench box
(no measurement; a laptop is enough).

    python3 examples/wave4g/local_check.py validate WORKDIR
    python3 examples/wave4g/local_check.py functional WORKDIR [N_RECONNECT_REQUESTS]

validate     every arm of every config (smokes included): `envoy --mode validate` OK; an arm whose validate
             crashes is retried with `--mode init_only` on its own (the HTTP/3 listener crash of earlier
             releases), and the result says which mode passed.
functional   one container network namespace with the origin (the harness's nginx.conf), the SUT Envoy (4
             workers, the arm's bootstrap) and a stand-in client: a second Envoy v1.40.2 whose origin cluster
             speaks to the SUT with the run's own client socket (the HTTP/3 socket of make.py, cert_dir
             filled in, or the TLS socket with HTTP/2) and, in reconnect arms, at most 10 requests per
             connection; curl sends requests to it. Per arm: every response 200 with 4,096 bytes; the
             protocol counters; the GSO writer's byte counter present (gso) or absent (nogso); and in the
             reconnect arms, the SUT's bytes sent per QUIC connection, the resumption reading fixed
             before the run (the stand-in client is not the run's Nighthawk; its session cache is QUICHE's,
             the same code Nighthawk links). Prints a JSON summary; exit 1 on a failed check.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import envoy_config, experiment, leg  # noqa: E402


def _load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


f = _load("wave3f_local_check", os.path.join(ROOT, "examples", "wave3f", "local_check.py"))  # Net, certs, stats
g = _load("wave4g_make", os.path.join(HERE, "make.py"))

CFG = os.path.join(HERE, "configs")
RUNS = ("g1-proto.json", "g2-resume.json", "smoke-g1-proto.json", "smoke-g2-resume.json", "g2s-resume.json",
        "smoke-g2s-resume.json")
FUNCTIONAL = tuple(x for x in os.environ.get("G_FUNCTIONAL", "smoke-g1-proto.json,smoke-g2-resume.json").split(","))
CLIENT_PORT, CLIENT_ADMIN = 18000, 19901


def load(fn):
    return experiment.load(os.path.join(CFG, fn))


def prepare(fn, work, sub):
    exp = load(fn)
    rd = os.path.join(work, sub, fn[:-5])
    os.makedirs(rd, exist_ok=True)
    paths, _, _ = experiment.prepare_bootstraps(exp, rd, make_certs=False)
    certs = f.make_certs(exp, rd)
    return exp, rd, paths, certs


def run_envoy(rd, p, mode):
    r = f.sh(["docker", "run", "--rm", "--platform", f.PLATFORM, "-v", "%s:%s:ro" % (rd, rd), f.IMAGE,
              "envoy", "--mode", mode, "-c", p, "-l", "warn", "--concurrency", "4"], timeout=300)
    txt = r.stdout + r.stderr
    return r.returncode, txt


def validate(work):
    out, bad = {}, 0
    for fn in RUNS:
        exp, rd, paths, _ = prepare(fn, work, "validate")
        if not out:
            f.image_sha256(exp["arms"][0]["source_sha256"])
        for key, p in sorted(paths.items()):
            rc, txt = run_envoy(rd, p, "validate")
            ok = rc == 0 and bool(txt.strip()) and "OK" in txt.splitlines()[-1]
            if ok:
                out["%s/%s" % (fn[:-5], key)] = "OK (validate)"
                continue
            rc2, txt2 = run_envoy(rd, p, "init_only")
            ok2 = rc2 == 0
            out["%s/%s" % (fn[:-5], key)] = ("validate rc=%d; init_only OK" % rc) if ok2 else (
                "validate rc=%d: %s | init_only rc=%d: %s" % (rc, txt[-300:], rc2, txt2[-300:]))
            bad += 0 if ok2 else 1
    print(json.dumps(out, indent=1))
    return 1 if bad else 0


# ---------------------------------------------------------------- functional

def client_bootstrap(rd, exp, a):
    """The stand-in client: HTTP/1 listener for curl, one cluster to the SUT with the arm's client socket
    and protocol (and the reconnect limit)."""
    xa = leg.sub_cert_dir(a["client"]["extra_args"], rd)
    sock = json.loads(xa[xa.index("--transport-socket") + 1])
    h3 = xa[xa.index("--protocol") + 1] == "http3"
    hpo = {"explicit_http_config": {("http3_protocol_options" if h3 else "http2_protocol_options"): {}},
           "@type": envoy_config.UPSTREAM_HTTP}
    if "--max-requests-per-connection" in xa:
        hpo["common_http_protocol_options"] = {
            "max_requests_per_connection": int(xa[xa.index("--max-requests-per-connection") + 1])}
    cl = {"name": "sut", "connect_timeout": "5s", "type": "STATIC",
          "load_assignment": {"cluster_name": "sut", "endpoints": [{"lb_endpoints": [{"endpoint": {"address": {
              "socket_address": {"address": "127.0.0.1", "port_value": exp["envoy"]["listener_port"],
                                 **({"protocol": "UDP"} if h3 else {})}}}}]}]},
          "typed_extension_protocol_options": {"envoy.extensions.upstreams.http.v3.HttpProtocolOptions": hpo},
          "transport_socket": sock}
    hcm = {"@type": envoy_config.HCM, "stat_prefix": "c", "codec_type": "HTTP1",
           "route_config": {"virtual_hosts": [{"name": "c", "domains": ["*"],
                                               "routes": [{"match": {"prefix": "/"}, "route": {"cluster": "sut"}}]}]},
           "http_filters": [{"name": "envoy.filters.http.router", "typed_config": {"@type": envoy_config.ROUTER}}]}
    b = {"admin": {"address": {"socket_address": {"address": "127.0.0.1", "port_value": CLIENT_ADMIN}}},
         "static_resources": {"listeners": [{"name": "c", "address": {"socket_address": {
             "address": "127.0.0.1", "port_value": CLIENT_PORT}}, "filter_chains": [{"filters": [{
                 "name": "envoy.filters.network.http_connection_manager", "typed_config": hcm}]}]}],
             "clusters": [cl]}}
    p = os.path.join(rd, "client-%s.json" % a["name"])
    with open(p, "w") as fh:
        json.dump(b, fh, indent=1)
    return p, h3


def curl_n(net, n):
    out, _ = net.curl("i=0; while [ $i -lt %d ]; do curl -s -o /tmp/b -w '%%{http_code}' "
                      "http://127.0.0.1:%d/s; echo \" $(wc -c < /tmp/b)\"; i=$((i+1)); done" % (n, CLIENT_PORT))
    return [tuple(x.split()) for x in out.splitlines() if len(x.split()) == 2]


SNIFF_IMAGE = f.CERT_IMAGE  # python:3.13-slim, already used for the certificates


def sniff_start(net, port, name):
    d = os.path.join(net.rd, "sniff-" + name)
    os.makedirs(d, exist_ok=True)
    for x in ("stop", "out.json", "out.json.ready"):
        if os.path.exists(os.path.join(d, x)):
            os.remove(os.path.join(d, x))
    r = f.sh(["docker", "run", "-d", "--rm", "--network", "container:" + net.origin, "--cap-add", "NET_RAW",
              "-v", "%s:/h:ro" % HERE, "-v", "%s:%s" % (d, d), SNIFF_IMAGE, "python3", "-I", "/h/udp_sniff.py",
              str(port), os.path.join(d, "stop"), os.path.join(d, "out.json")])
    if r.returncode:
        raise SystemExit("sniffer: " + r.stderr)
    net.ids.append(r.stdout.strip())
    end = time.time() + 30
    while time.time() < end and not os.path.exists(os.path.join(d, "out.json.ready")):
        time.sleep(0.2)
    return d, r.stdout.strip()


def sniff_stop(net, sn):
    d, cid = sn
    time.sleep(1.0)
    open(os.path.join(d, "stop"), "w").close()
    end = time.time() + 30
    while time.time() < end and not os.path.exists(os.path.join(d, "out.json")):
        time.sleep(0.2)
    net.stop(cid)
    with open(os.path.join(d, "out.json")) as fh:
        return json.load(fh)


def run_arm(net, exp, a, paths, n, res, fails):
    sut = net.envoy(paths[a["name"]], workers=4)
    cp, h3 = client_bootstrap(net.rd, exp, a)
    adm = exp["envoy"]["admin_port"]
    try:
        if not f.wait_ready(net, adm):
            fails.append("%s: SUT not ready: %s" % (a["name"], net.logs(sut)))
            return
        cli = net.envoy(cp, workers=1)
        if not f.wait_ready(net, CLIENT_ADMIN):
            fails.append("%s: client not ready: %s" % (a["name"], net.logs(cli)))
            return
        reconnect = ("--max-requests-per-connection" in a["client"]["extra_args"]
                     or bool((a.get("settings") or {}).get("downstream_keepalive")))
        k = n if reconnect else 40
        sn = sniff_start(net, exp["envoy"]["listener_port"], a["name"]) if h3 else None
        got = curl_n(net, k)
        sniff = sniff_stop(net, sn) if sn else None
        ok = len(got) == k and all(s == "200" and int(b) == 4096 for s, b in got)
        st = f.stats(net, adm, exp)
        cst = f.stats(net, CLIENT_ADMIN)
        L = g.LISTENER
        r = {"responses_ok": ok, "n": len(got),
             "h3_cx": st.get("http.ingress_http.downstream_cx_http3_total"),
             "h2_cx": st.get("http.ingress_http.downstream_cx_http2_total"),
             "cx_total": st.get(L + "downstream_cx_total"),
             "gso_bytes": st.get(g.GSO_BYTES, "absent"),
             "client_cx": cst.get("cluster.sut.upstream_cx_total"),
             "client_cx_fail": cst.get("cluster.sut.upstream_cx_connect_fail")}
        if sniff:
            r["sniff"] = {k_: v for k_, v in sniff.items() if k_ not in ("per_dst", "long_header_bytes_per_dst")}
            r["server_bytes_per_cx"] = round(sniff["bytes"] / max(1, len(sniff["per_dst"])), 1)
            r["client_sockets_seen"] = len(sniff["per_dst"])
            r["handshake_bytes_per_cx"] = sniff["long_header_bytes_per_dst"]
        res[a["name"]] = r
        if not ok:
            fails.append("%s: responses %s" % (a["name"], got[:3]))
        want_gso = (a["settings"].get("quic") or {}).get("gso", True)
        if (r["h3_cx"] or 0) < 1 if h3 else (r["h2_cx"] or 0) < 1:
            fails.append("%s: no %s connection on the SUT" % (a["name"], "HTTP/3" if h3 else "HTTP/2"))
        if not want_gso and r["gso_bytes"] != "absent":
            fails.append("%s: GSO writer counter present" % a["name"])
        if want_gso and r["gso_bytes"] == "absent":
            fails.append("%s: GSO writer counter absent" % a["name"])
        if h3 and sniff and (sniff["over_mtu"] > 0) != bool(want_gso):
            fails.append("%s: %d datagrams over the MTU (gso %s)" % (a["name"], sniff["over_mtu"], want_gso))
        if reconnect and r["cx_total"] != -(-k // g.REQS_PER_CONN):
            fails.append("%s: %s connections for %d requests" % (a["name"], r["cx_total"], k))
        net.stop(cli)
    finally:
        net.stop(sut)


def functional(work, n):
    res, fails = {}, []
    for fn in FUNCTIONAL:
        exp, rd, paths, _ = prepare(fn, work, "functional")
        net = f.Net(rd, exp)
        try:
            for a in exp["arms"]:
                run_arm(net, exp, a, paths, n, res, fails)
        finally:
            net.close()
    res["resumption_reading"] = resumption_reading(res, fails)
    print(json.dumps({"arms": res, "fails": fails}, indent=1))
    return 1 if fails else 0


def resumption_reading(res, fails, tol=8):
    """Classify each reconnect connection after the first by its handshake-flight size (the SUT's QUIC
    long-header bytes to that client socket): 'resumed-like' within tol bytes of a flight seen in h3r-tk
    (shared ticket key: every connection after the first can resume), 'full-like' within tol of one seen
    in h3r-nores (no resumption). A reading, not a proof: the sizes are a signature, not a decrypted
    handshake."""
    tk = (res.get("h3r-tk") or {}).get("handshake_bytes_per_cx") or []
    nr = (res.get("h3r-nores") or {}).get("handshake_bytes_per_cx") or []
    if not tk or not nr:
        return None
    # the first connection of an arm cannot resume: the largest flight (it carries the first response's
    # extra settings) is dropped from each reference
    tk_ref, nr_ref = sorted(tk)[:-1], sorted(nr)[:-1]
    near = lambda x, ref: any(abs(x - r) <= tol for r in ref)  # noqa: E731
    out = {}
    for name in ("h3r", "h3r-A2", "h3r-tk", "h3r-nores"):
        v = sorted((res.get(name) or {}).get("handshake_bytes_per_cx") or [])[:-1]
        rl = sum(1 for x in v if near(x, tk_ref) and not near(x, nr_ref))
        fl = sum(1 for x in v if near(x, nr_ref) and not near(x, tk_ref))
        out[name] = {"connections": len(v), "resumed_like": rl, "full_like": fl, "other": len(v) - rl - fl}
    if out["h3r-tk"]["resumed_like"] < 0.9 * out["h3r-tk"]["connections"]:
        fails.append("resumption reading: h3r-tk not distinguishable (%s)" % out["h3r-tk"])
    return out


def main(argv):
    if len(argv) < 3 or argv[1] not in ("validate", "functional"):
        print(__doc__)
        return 2
    work = os.path.abspath(argv[2])
    os.makedirs(work, exist_ok=True)
    if argv[1] == "validate":
        return validate(work)
    return functional(work, int(argv[3]) if len(argv) > 3 else 200)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
