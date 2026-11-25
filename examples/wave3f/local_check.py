#!/usr/bin/env python3
"""Local checks of the track F configs with the official Envoy v1.40.2 binary, in Docker, off the bench box
(no measurement; a laptop is enough).

    python3 examples/wave3f/local_check.py validate WORKDIR
    python3 examples/wave3f/local_check.py functional WORKDIR

The image envoyproxy/envoy:v1.40.2 (linux/amd64) carries the release binary: its sha256 is checked against
the one the configs pin before anything runs. WORKDIR must be a directory Docker can bind-mount at the same
path (the bootstraps name the certificate files by absolute path). The test certificates are made the way
the harness makes them on the box (epl.origin.make_certs), inside a Debian container, so with OpenSSL 3
like the box and not the laptop's LibreSSL.

validate     every arm of every run config, and every second-hop bootstrap: `envoy --mode validate` OK.
functional   one container network namespace with the origin (nginx with the harness's own nginx.conf:
             plain, h2c and TLS servers, the gRPC responder), Envoy (and the second hop), and curl as the
             client. Every arm serves requests, the evidence items that do not depend on a warm pool hold
             on the counters, the gRPC responses carry 4,096 bytes and grpc-status 0, and two negative
             checks: hop B refuses a hop A without a client certificate, and hop A refuses a hop B whose
             SAN does not match. Prints a JSON summary; exit 1 on a failed check.
"""

import copy
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import envoy_config, evidence, experiment  # noqa: E402

IMAGE = "envoyproxy/envoy:v1.40.2"
PLATFORM = "linux/amd64"
NGINX = "nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11"
CURL = "curlimages/curl:8.10.1"
CERT_IMAGE = "python:3.13-slim"  # OpenSSL 3 CLI, for certificates made as on the box
CFG = os.path.join(HERE, "configs")
RUNS = ("f1-upstream.json", "f2-grpc.json", "f3-mtls.json")
N = 40


def sh(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def image_sha256(want):
    cid = sh(["docker", "create", "--platform", PLATFORM, IMAGE]).stdout.strip()
    try:
        r = subprocess.run("docker cp %s:/usr/local/bin/envoy - | tar -xO envoy | shasum -a 256" % cid, shell=True,
                           capture_output=True, text=True)
    finally:
        sh(["docker", "rm", cid])
    got = r.stdout.split()[0] if r.stdout else None
    if got != want:
        raise SystemExit("image binary sha256 %s != pinned %s" % (got, want))
    return got


def load(fn):
    return experiment.load(os.path.join(CFG, fn))


def make_certs(exp, rd):
    """The run's certificates in rd/certs, made by epl.origin.make_certs inside a Debian container."""
    kinds = experiment.cert_kinds(exp)
    if not kinds:
        return None
    code = ("import sys; sys.path.insert(0, '/h'); from epl.origin import make_certs; "
            "import json; print(json.dumps(make_certs(sys.argv[1], sys.argv[2].split(','), lambda m: None)))")
    r = sh(["docker", "run", "--rm", "-v", "%s:/h:ro" % ROOT, "-v", "%s:%s" % (rd, rd), CERT_IMAGE,
            "python3", "-c", code, os.path.join(rd, "certs"), ",".join(kinds)], timeout=300)
    if r.returncode:
        raise SystemExit("make_certs: " + r.stderr[-600:])
    return json.loads(r.stdout)


def prepare(fn, work, sub):
    exp = load(fn)
    rd = os.path.join(work, sub, fn[:-5])
    os.makedirs(rd, exist_ok=True)
    paths, _, _ = experiment.prepare_bootstraps(exp, rd, make_certs=False)
    certs = make_certs(exp, rd)
    return exp, rd, paths, certs


def validate(work):
    out, bad = {}, 0
    for fn in RUNS:
        exp, rd, paths, _ = prepare(fn, work, "validate")
        if not out:
            image_sha256(exp["arms"][0]["source_sha256"])
        for key, p in sorted(paths.items()):
            r = sh(["docker", "run", "--rm", "--platform", PLATFORM, "-v", "%s:%s:ro" % (rd, rd), IMAGE,
                    "envoy", "--mode", "validate", "-c", p, "-l", "warn"], timeout=300)
            txt = r.stdout + r.stderr
            ok = r.returncode == 0 and bool(txt.strip()) and "OK" in txt.splitlines()[-1]
            out["%s/%s" % (fn[:-5], key)] = "OK" if ok else txt[-600:]
            bad += 0 if ok else 1
    print(json.dumps(out, indent=1))
    return 1 if bad else 0


# ---------------------------------------------------------------- functional

class Net:
    """The origin container (nginx) owns the network namespace; Envoy and curl join it."""

    def __init__(self, rd, exp):
        self.ids = []
        o = exp["origin"]
        od = os.path.join(rd, "origin")
        www = os.path.join(od, "www")
        os.makedirs(www, exist_ok=True)
        for rel, size in envoy_config.origin_files(exp["shapes"]).items():
            os.makedirs(os.path.dirname(os.path.join(www, rel)), exist_ok=True)
            with open(os.path.join(www, rel), "wb") as f:
                f.write(b"a" * size)
        grpc = envoy_config.grpc_files(exp["shapes"])
        for rel, body in grpc.values():
            os.makedirs(os.path.dirname(os.path.join(www, rel)), exist_ok=True)
            with open(os.path.join(www, rel), "wb") as f:
                f.write(body)
        with open(os.path.join(od, "nginx.conf"), "w") as f:
            f.write(envoy_config.nginx_conf(o["port"], 2, stub_status=True, h2c_port=o.get("h2c_port"),
                                            tls_port=o.get("tls_port"), tls_cert=o.get("tls_cert"), grpc=grpc,
                                            chunked=envoy_config.chunked_paths(exp["shapes"])))
        r = sh(["docker", "run", "-d", "--rm", "-v", "%s/nginx.conf:/etc/nginx/nginx.conf:ro" % od,
                "-v", "%s:/www:ro" % www, "-v", "%s:/certs:ro" % os.path.join(rd, "certs"), NGINX])
        if r.returncode:
            raise SystemExit("origin: " + r.stderr)
        self.origin = r.stdout.strip()
        self.ids.append(self.origin)
        self.rd = rd
        time.sleep(1.0)

    def envoy(self, bpath, workers=2):
        r = sh(["docker", "run", "-d", "--rm", "--platform", PLATFORM, "--network", "container:" + self.origin,
                "-e", "ENVOY_UID=0", "-v", "%s:%s" % (self.rd, self.rd), IMAGE, "envoy", "-c", bpath, "--concurrency", str(workers),
                "-l", "warn", "--use-dynamic-base-id"])
        if r.returncode:
            raise SystemExit("envoy: " + r.stderr)
        self.ids.append(r.stdout.strip())
        return self.ids[-1]

    def curl(self, script, timeout=600):
        r = sh(["docker", "run", "--rm", "--network", "container:" + self.origin, "-v", "%s:%s" % (self.rd, self.rd),
                "--entrypoint", "sh", CURL, "-c", script], timeout=timeout)
        return r.stdout, r.stderr

    def text(self, port, path):
        out, _ = self.curl("curl -s 'http://127.0.0.1:%d%s'" % (port, path), timeout=60)
        return out

    def logs(self, cid):
        r = sh(["docker", "logs", cid])
        return (r.stdout + r.stderr)[-1500:]

    def stop(self, cid):
        sh(["docker", "stop", "-t", "2", cid])
        if cid in self.ids:
            self.ids.remove(cid)

    def close(self):
        for cid in reversed(self.ids):
            sh(["docker", "stop", "-t", "2", cid])


def stats(net, admin, exp=None):
    """Admin stats; with exp, through the leg's own filter (the fixed one plus the run's extra), so the
    evidence reads exactly what a box leg reads."""
    path = "/stats"
    if exp is not None:
        import urllib.parse
        from epl.leg import STAT_FILTER
        extra = exp["measure"].get("stat_filter_extra")
        path += "?filter=" + urllib.parse.quote(STAT_FILTER + ("|" + extra if extra else ""), safe="")
    out = {}
    for line in net.text(admin, path).splitlines():
        k, _, v = line.partition(": ")
        try:
            out[k] = int(v)
        except ValueError:
            pass
    return out


def wait_ready(net, admin, t=90):
    end = time.time() + t
    while time.time() < end:
        if "LIVE" in net.text(admin, "/ready"):
            return True
        time.sleep(1.0)
    return False


def requests(net, exp, shape, n=N):
    """n requests of the shape from curl; [(status, body bytes, grpc-status or None)]."""
    port = exp["envoy"]["listener_port"]
    url = "http://127.0.0.1:%d%s" % (port, shape["path"])
    if shape.get("grpc"):
        body = experiment.request_body_path(shape)
        # the request file is copied next to the run so the curl container sees it
        dst = os.path.join(net.rd, "grpc-request.bin")
        with open(body, "rb") as f, open(dst, "wb") as g:
            g.write(f.read())
        one = ("curl -s --http2-prior-knowledge -X POST --data-binary @%s -H 'content-type: application/grpc' "
               "-H 'te: trailers' -D /tmp/h -o /tmp/b %s; s=$(awk 'NR==1{print $2}' /tmp/h); "
               "g=$(tr -d '\\r' < /tmp/h | awk -F': ' 'tolower($1)==\"grpc-status\"{print $2}'); "
               "echo \"$s $(wc -c < /tmp/b) ${g:-none}\"" % (dst, url))
    else:
        one = "curl -s -o /tmp/b -w '%%{http_code}' %s; echo \" $(wc -c < /tmp/b) none\"" % url
    out, err = net.curl("i=0; while [ $i -lt %d ]; do %s; i=$((i+1)); done" % (n, one))
    res = []
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3:
            res.append((p[0], int(p[1]), None if p[2] == "none" else p[2]))
    return res


# window items that need a warm pool (here every connection is new): checked on the box only
def box_only(it):
    return it.get("scope") in ("window", "hop2_window") and (
        it["stat"].endswith("upstream_cx_total") or it["stat"].endswith("ssl.handshake"))


def check_evidence(a, st, st2, n):
    m = {"sut_stats_leg_end": st, "sut_stats_leg_end_ok": True, "sut_stats_window": st, "sut_stats_window_ok": True,
         "responses_raw": n, "shape": None}
    if st2 is not None:
        m.update(hop2_stats_leg_end=st2, hop2_stats_leg_end_ok=True, hop2_stats_window=st2, hop2_stats_window_ok=True)
    m["sut_stats_leg_end"] = dict(st, **{"http.ingress_http.downstream_rq_completed":
                                         st.get("http.ingress_http.downstream_rq_completed", n)})
    out = []
    for it in a.get("evidence", []):
        if box_only(it):
            continue
        if it.get("min") is not None and it["min"] > n:
            # a count the box reaches with 512 client connections; here curl opens one per request
            it = dict(it, min=n)
        r = evidence.check_item(m, it)
        if not r["ok"]:
            out.append("%s: %s" % (r["label"], r["why"]))
    return out


def run_arm(net, exp, a, paths, fails, res):
    shape = exp["shapes"][0]
    two = experiment.arm_settings(a).get("two_hop")
    adm, adm2 = exp["envoy"]["admin_port"], exp["hop2"]["admin_port"]
    hb = None
    if two:
        hb = net.envoy(paths[experiment.hop2_key(a)])
        if not wait_ready(net, adm2):
            fails.append("%s: hop B not ready: %s" % (a["name"], net.logs(hb)))
            net.stop(hb)
            return
    eid = net.envoy(paths[a["name"]])
    try:
        if not wait_ready(net, adm):
            fails.append("%s: not ready: %s" % (a["name"], net.logs(eid)))
            return
        rs = requests(net, exp, shape)
        st = stats(net, adm, exp)
        st2 = stats(net, adm2, exp) if hb else None
        keep = lambda s: {k: v for k, v in sorted((s or {}).items()) if v and not k.endswith("_bucket") and (  # noqa
            ".ssl." in k or "http2." in k or "upstream_cx_http" in k or ".grpc." in k or "rq_2xx" in k)}
        res[a["name"]] = {"responses": len(rs), "statuses": sorted({r[0] for r in rs}),
                          "body_bytes": sorted({r[1] for r in rs}), "grpc_status": sorted({str(r[2]) for r in rs}),
                          "stats": keep(st), "hop2_stats": keep(st2) if hb else None}
        want_body = int(shape["body_bytes"])
        if len(rs) != N or any(r[0] != "200" or r[1] != want_body for r in rs):
            fails.append("%s: responses %s" % (a["name"], res[a["name"]]))
        if shape.get("grpc") and any(r[2] != "0" for r in rs):
            fails.append("%s: grpc-status %s" % (a["name"], sorted({str(r[2]) for r in rs})))
        fails.extend("%s: %s" % (a["name"], x) for x in check_evidence(a, st, st2, len(rs)))
    finally:
        net.stop(eid)
        if hb:
            net.stop(hb)


def negative_mtls(net, exp, rd, paths, fails, res):
    """Hop A without its client certificate, and hop A expecting another SAN: no request gets through."""
    a = [x for x in exp["arms"] if x["name"] == "pair-mtls"][0]
    out = {}
    for case in ("no-client-cert", "wrong-san"):
        b = copy.deepcopy(a)
        ut = b["settings"]["upstream_tls"]
        if case == "no-client-cert":
            ut.pop("cert")
        else:
            ut["san"] = "other.bench.local"
        b["name"] = "pair-mtls-" + case
        exp2 = dict(exp, arms=[b])
        t = envoy_config.bootstrap_text(exp2["shapes"], experiment.arm_envoy(exp2, b, rd), exp["origin"]["port"],
                                        os.path.join(rd, "certs"))
        p = os.path.join(rd, "envoy-bootstrap-%s.json" % b["name"])
        with open(p, "w") as f:
            f.write(t)
        hb = net.envoy(paths[experiment.hop2_key(a)])
        wait_ready(net, exp["hop2"]["admin_port"])
        eid = net.envoy(p)
        try:
            wait_ready(net, exp["envoy"]["admin_port"])
            rs = requests(net, exp, exp["shapes"][0], n=5)
            st, st2 = stats(net, exp["envoy"]["admin_port"]), stats(net, exp["hop2"]["admin_port"])
            out[case] = {"statuses": sorted({r[0] for r in rs}),
                         "hop_a": {k: v for k, v in st.items() if "cluster.origin.ssl." in k and v},
                         "hop_b": {k: v for k, v in st2.items() if ".ssl." in k and v and "listener." in k}}
            if any(r[0] == "200" for r in rs):
                fails.append("negative %s: a request got through %s" % (case, out[case]))
        finally:
            net.stop(eid)
            net.stop(hb)
    res["negative_mtls"] = out


def functional(work):
    fails, res = [], {}
    first = True
    for fn in RUNS:
        exp, rd, paths, certs = prepare(fn, work, "functional")
        if first:
            image_sha256(exp["arms"][0]["source_sha256"])
            first = False
        res[fn] = {"certs": {k: v.get("san") for k, v in (certs or {}).get("certs", {}).items()},
                   "openssl": (certs or {}).get("openssl")}
        net = Net(rd, exp)
        try:
            for a in exp["arms"]:
                if a["name"].endswith("-A2"):
                    continue
                run_arm(net, exp, a, paths, fails, res[fn])
            if fn == "f3-mtls.json":
                negative_mtls(net, exp, rd, paths, fails, res[fn])
        finally:
            net.close()
    print(json.dumps({"results": res, "failed": fails}, indent=1, sort_keys=True))
    return 1 if fails else 0


def main(argv):
    if len(argv) != 2 or argv[0] not in ("validate", "functional"):
        print(__doc__)
        return 2
    work = os.path.abspath(argv[1])
    os.makedirs(work, exist_ok=True)
    return validate(work) if argv[0] == "validate" else functional(work)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
