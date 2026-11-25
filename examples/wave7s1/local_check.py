#!/usr/bin/env python3
"""Local checks of the wave 7 S1 configs with the official Envoy v1.40.2 binary, in Docker, off the bench box
(no measurement).

    python3 examples/wave7s1/local_check.py validate WORKDIR
    python3 examples/wave7s1/local_check.py functional WORKDIR

WORKDIR must be short (the Unix socket paths live under it; 107 bytes at most) and bind-mountable at the
same path. validate: every arm and second-hop bootstrap of every config under `envoy --mode validate`.
functional: per config one network namespace with the origin (the harness's own nginx.conf: inline-body
locations, the Unix-socket server), Envoy (and the second hop) and curl; every arm serves the shape with
status 200 and the right body size, and the evidence items that do not need the box's load hold on the
counters read through the leg's own stats filter. Negative check: hop A without a client certificate gets
nothing through pair-mtls-l4. The Unix sockets live on Docker volumes mounted at the paths the bootstraps
name (a laptop's bind mount cannot carry a socket)."""

import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import envoy_config, evidence, experiment  # noqa: E402

_s = importlib.util.spec_from_file_location("w3f_local", os.path.join(ROOT, "examples", "wave3f", "local_check.py"))
w3 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(w3)
CFG = os.path.join(HERE, "configs")
RUNS = ("smoke-s1a-hop.json", "smoke-s1b-relay.json")
N = 40


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
    for fn in sorted(os.listdir(CFG)):
        if fn.startswith("mech-") or "-half" in fn or "-no-" in fn or not fn.startswith("smoke-"):
            continue  # the smokes carry every arm of their runs
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
    def __init__(self, rd, exp):  # noqa: super().__init__ not called: another nginx.conf and the socket volumes
        self.ids, self.rd = [], rd
        o = exp["origin"]
        od = os.path.join(rd, "origin")
        www = os.path.join(od, "www")
        os.makedirs(www, exist_ok=True)
        for rel, size in envoy_config.origin_files(exp["shapes"]).items():
            with open(os.path.join(www, rel), "wb") as f:
                f.write(b"a" * size)
        with open(os.path.join(od, "nginx.conf"), "w") as f:
            f.write(envoy_config.nginx_conf(o["port"], 2, stub_status=True, inline=envoy_config.inline_bodies(exp["shapes"]),
                                            uds="/uds/origin.sock" if o.get("uds") else None))
        tag = "epl-w7lc-%d" % os.getpid()
        self.vols = {tag + "-o": experiment.origin_uds_dir(rd), tag + "-h": os.path.dirname(experiment.hop_uds_path(rd))}
        for v in self.vols:
            w3.sh(["docker", "volume", "create", v])
        vo = [k for k, p in self.vols.items() if p.endswith("origin-uds")][0]
        r = w3.sh(["docker", "run", "-d", "--rm", "-v", "%s/nginx.conf:/etc/nginx/nginx.conf:ro" % od,
                   "-v", "%s:/www:ro" % www, "-v", "%s:/uds" % vo, w3.NGINX])
        if r.returncode:
            raise SystemExit("origin: " + r.stderr)
        self.origin = r.stdout.strip()
        self.ids.append(self.origin)
        import time
        time.sleep(1.0)

    def _mounts(self):
        m = ["-v", "%s:%s" % (self.rd, self.rd)]
        for v, p in self.vols.items():
            m += ["-v", "%s:%s" % (v, p)]
        return m

    def envoy(self, bpath, workers=2):
        r = w3.sh(["docker", "run", "-d", "--rm", "--platform", w3.PLATFORM, "--network", "container:" + self.origin,
                   "-e", "ENVOY_UID=0"] + self._mounts() + [w3.IMAGE, "envoy", "-c", bpath, "--concurrency", str(workers),
                                                           "-l", "warn", "--use-dynamic-base-id"])
        if r.returncode:
            raise SystemExit("envoy: " + r.stderr)
        self.ids.append(r.stdout.strip())
        return self.ids[-1]

    def close(self):
        super().close()
        import time
        time.sleep(1.0)
        for v in self.vols:
            w3.sh(["docker", "volume", "rm", v])


def box_only(it):
    """Items that need the box's load or its leg record: window zeros of connection counters (here every
    connection is new), frozen references, and fields of the leg record."""
    if it.get("scope") == "field" or it.get("ref"):
        return True
    return it.get("scope") in ("window", "hop2_window") and (
        it["stat"].endswith(("upstream_cx_total", "ssl.handshake", "downstream_cx_total", "upstream_cx_destroy")))


def check_evidence(a, st, st2, n, dump):
    m = {"sut_stats_leg_end": st, "sut_stats_leg_end_ok": True, "sut_stats_window": st, "sut_stats_window_ok": True,
         "responses_raw": n, "shape": None}
    if st2 is not None:
        m.update(hop2_stats_leg_end=st2, hop2_stats_leg_end_ok=True, hop2_stats_window=st2, hop2_stats_window_ok=True)
    out, seen = [], 0
    for it in a.get("evidence", []):
        if box_only(it):
            continue
        if it.get("min") is not None and it["min"] > n and it.get("scope") != "config":
            it = dict(it, min=1)  # the box reaches 512 with its client; curl opens few connections
        r = evidence.check_item(m, it, dump)
        seen += 1
        if not r["ok"]:
            out.append("%s: %s" % (r["label"], r["why"]))
    return out, seen


def requests(net, exp, shape, n=N):
    url = "http://127.0.0.1:%d%s" % (exp["envoy"]["listener_port"], shape["path"])
    one = "curl -s -o /tmp/b -w '%%{http_code}' %s; echo \" $(wc -c < /tmp/b)\"" % url
    out, _ = net.curl("i=0; while [ $i -lt %d ]; do %s; i=$((i+1)); done" % (n, one))
    return [(p[0], int(p[1])) for p in (line.split() for line in out.splitlines()) if len(p) == 2]


def run_arm(net, exp, a, paths, fails, res):
    two = experiment.arm_settings(a).get("two_hop")
    adm, adm2 = exp["envoy"]["admin_port"], exp["hop2"]["admin_port"]
    hb = None
    if two:
        hb = net.envoy(paths[experiment.hop2_key(a)])
        if not w3.wait_ready(net, adm2):
            fails.append("%s: hop B not ready: %s" % (a["name"], net.logs(hb)))
            net.stop(hb)
            return
    eid = net.envoy(paths[a["name"]])
    try:
        if not w3.wait_ready(net, adm):
            fails.append("%s: not ready: %s" % (a["name"], net.logs(eid)))
            return
        tot, rec = 0, {}
        for shape in exp["shapes"]:
            rs = requests(net, exp, shape)
            tot += len(rs)
            rec[shape["name"]] = {"n": len(rs), "statuses": sorted({r[0] for r in rs}), "bytes": sorted({r[1] for r in rs})}
            if len(rs) != N or any(r[0] != "200" or r[1] != int(shape["body_bytes"]) for r in rs):
                fails.append("%s %s: responses %s" % (a["name"], shape["name"], rec[shape["name"]]))
        st = w3.stats(net, adm, exp)
        st2 = w3.stats(net, adm2, exp) if hb else None
        dump = json.loads(net.text(adm, "/config_dump"))
        bad, seen = check_evidence(a, st, st2, tot, dump)
        keep = lambda s: {k: v for k, v in sorted((s or {}).items()) if v and (  # noqa: E731
            k.startswith("tcp.") or "rq_2xx" in k or "cx_total" in k or ".ssl.handshake" in k)}
        res[a["name"]] = {"shapes": rec, "evidence_items_checked": seen, "stats": keep(st), "hop2_stats": keep(st2)}
        fails.extend("%s: %s" % (a["name"], x) for x in bad)
    finally:
        net.stop(eid)
        if hb:
            net.stop(hb)


def negative_mtls_l4(net, exp, rd, paths, fails, res):
    """Hop A without its client certificate: nothing gets through the relaying mTLS hop B."""
    a = [x for x in exp["arms"] if x["name"] == "pair-mtls-l4"][0]
    b = copy.deepcopy(a)
    b["settings"]["upstream_tls"].pop("cert")
    b["name"] = "pair-mtls-l4-no-client-cert"
    exp2 = dict(exp, arms=[b])
    t = envoy_config.bootstrap_text(exp2["shapes"], experiment.arm_envoy(exp2, b, rd), exp["origin"]["port"],
                                    os.path.join(rd, "certs"))
    p = os.path.join(rd, "envoy-bootstrap-%s.json" % b["name"])
    with open(p, "w") as f:
        f.write(t)
    hb = net.envoy(paths[experiment.hop2_key(a)])
    w3.wait_ready(net, exp["hop2"]["admin_port"])
    eid = net.envoy(p)
    try:
        w3.wait_ready(net, exp["envoy"]["admin_port"])
        rs = requests(net, exp, exp["shapes"][0], n=5)
        st2 = w3.stats(net, exp["hop2"]["admin_port"], exp)
        res["negative_no_client_cert"] = {"statuses": sorted({r[0] for r in rs}),
                                          "hop_b": {k: v for k, v in st2.items() if v and (".ssl." in k or k.startswith("tcp."))}}
        if any(r[0] == "200" for r in rs):
            fails.append("negative: a request got through without a client certificate")
    finally:
        net.stop(eid)
        net.stop(hb)


def functional(work):
    fails, res = [], {}
    for fn in RUNS:
        exp, rd, paths = prepare(fn, work, "f")
        res[fn] = {}
        net = Net(rd, exp)
        try:
            for a in exp["arms"]:
                if a["name"].endswith(("-A2", "-B2", "-B3")):
                    continue
                run_arm(net, exp, a, paths, fails, res[fn])
            if fn.startswith("smoke-s1a"):
                negative_mtls_l4(net, exp, rd, paths, fails, res[fn])
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
