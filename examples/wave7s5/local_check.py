#!/usr/bin/env python3
"""Local checks of the wave 7 S5 configs, in Docker, off the bench box (no measurement).

    python3 examples/wave7s5/local_check.py validate WORKDIR BINDIR
    python3 examples/wave7s5/local_check.py functional WORKDIR BINDIR

BINDIR holds the patched binary under its bins.json file name (envoy-relay-sc); it is checked against its
pinned sha256 before use. The official arm runs the binary of the envoyproxy/envoy:v1.40.2 image (sha256 = pin).

validate    every arm's bootstrap of every config under `--mode validate` of that arm's own binary.
functional  one network namespace with the nginx origin (the harness's own nginx.conf, inline bodies and the
            HTTP/2 cleartext port included), Envoy and curl. Per config (smoke-relay, smoke-http,
            mech-load-h2-16k), arm and shape: N keep-alive requests return 200 with the right body size (the
            h2 shape: one HTTP/2 prior-knowledge connection through tcp_proxy); the admin /runtime is read
            before and after through the harness's own parser; the arm's evidence holds on the counters read
            through the leg's own stats filter and on /config_dump (items that need the box's client, a
            frozen reference or a still-open connection are skipped; every zero counter is also required to
            EXIST in the filtered snapshot); bytes per request on the four sides equal the official arm's.
            Negative: each patched arm's guard evidence fails on another patched arm's leg."""
import hashlib
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import envoy_config, evidence, experiment, leg  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


w3 = _load("w3f_local5", os.path.join(ROOT, "examples", "wave3f", "local_check.py"))
chk = _load("w7s5_check_local", os.path.join(HERE, "s5_check.py"))
CFG = os.path.join(HERE, "configs")
FUNCTIONAL = ("smoke-relay.json", "smoke-http.json", "mech-load-h2-16k.json")
N = 200


def local_bins(bindir):
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
    for fn in sorted(os.listdir(CFG)):
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


class Net(w3.Net):
    """As wave 3's (nginx owns the namespace), with the origin's inline bodies and an arm's own binary mounted."""

    def __init__(self, rd, exp):
        orig = envoy_config.nginx_conf
        inline = envoy_config.inline_bodies(exp["shapes"])
        envoy_config.nginx_conf = lambda *a, **kw: orig(*a, **dict(kw, inline=inline))
        try:
            super().__init__(rd, exp)
        finally:
            envoy_config.nginx_conf = orig

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


def keepalive(net, port, shape, n, h2):
    url = "http://127.0.0.1:%d%s" % (port, shape["path"])
    script = ("i=0; args=''; while [ $i -lt %d ]; do args=\"$args -o /dev/null %s\"; i=$((i+1)); done; "
              "curl -s %s -w '%%{http_code} %%{size_download} %%{http_version} %%{num_connects}\\n' $args" % (
                  n, url, "--http2-prior-knowledge" if h2 else ""))
    out, _ = net.curl(script)
    return [(p[0], int(p[1]), p[2], int(p[3])) for p in (line.split() for line in out.splitlines()) if len(p) == 4]


def box_only(it):
    """Items that need the box's client (rate, 512 connections), a frozen reference, or a connection that is
    still open when the counters are read (curl has closed its one connection by then)."""
    if "ref" in it:
        return True
    st, sc = it["stat"], it.get("scope", "window")
    if sc == "field" and not st.startswith("runtime_"):
        return True
    return sc == "window" and st.endswith(("upstream_cx_total", "downstream_cx_total", "cx_destroy", "cx_destroy_remote",
                                           "cx_destroy_local"))


def check_evidence(a, m, dump, st):
    out, seen = [], 0
    for it in a.get("evidence", []):
        if box_only(it):
            continue
        if it.get("min") is not None and it.get("scope") != "config":
            it = dict(it, min=1)
        r = evidence.check_item(m, it, dump)
        seen += 1
        if not r["ok"]:
            out.append("%s: %s" % (r["label"], r["why"]))
        if it.get("equals") == 0 and it.get("scope", "window") in ("window", "leg") and it["stat"] not in st:
            out.append("%s: the counter is not in the filtered snapshot (a zero read from nothing)" % it["stat"])
    return out, seen


def one_leg(net, exp, paths, a, shape, fails, res, bins, h2):
    adm, port = exp["envoy"]["admin_port"], exp["envoy"]["listener_port"]
    tag = "%s/%s/%s" % (exp["name"], a["name"], shape["name"])
    keys = exp["measure"]["runtime_keys"]
    eid = net.envoy_bin(paths[a["name"]], bins[a["build"]])
    try:
        if not w3.wait_ready(net, adm, 240):
            fails.append("%s: not ready: %s" % (tag, net.logs(eid)))
            return None
        rt0 = leg.runtime_values(net.text(adm, "/runtime"), keys)
        rs = keepalive(net, port, shape, N, h2)
        time.sleep(1.0)
        st = w3.stats(net, adm, exp)
        dump = json.loads(net.text(adm, "/config_dump"))
        rt_text = net.text(adm, "/runtime")
        rt1 = leg.runtime_values(rt_text, keys)
        m = {"sut_stats_leg_end": st, "sut_stats_leg_end_ok": True, "sut_stats_window": st, "sut_stats_window_ok": True,
             "responses_raw": N, "shape": shape["name"], "runtime_start": rt0, "runtime_end": rt1, "arm": a["name"]}
        bad, seen = check_evidence(a, m, dump, st)
        kind = "s" if shape["name"] == "s" else "p64"
        rec = {"n": len(rs), "statuses": sorted({r[0] for r in rs}), "bytes": sorted({r[1] for r in rs}),
               "http_versions": sorted({r[2] for r in rs}), "connections_opened": sum(r[3] for r in rs),
               "evidence_items_checked": seen, "runtime_start": rt0, "runtime_end": rt1, "runtime_dump": json.loads(rt_text),
               "bytes_per_request": {what: (st.get(stat) or 0) / float(N) for what, stat in chk.BYTES[kind]},
               "nonzero": {k: v for k, v in sorted(st.items()) if v and ("destroy" in k or "reset" in k or "fail" in k or "timeout" in k
                                                                         or "overflow" in k or "error" in k)},
               "runtime_stats": {k: v for k, v in st.items() if k.startswith("runtime.")},
               "upstream_protocol": {k: v for k, v in st.items() if k.endswith(("cx_http1_total", "cx_http2_total"))}}
        res[tag] = rec
        if len(rs) != N or any(r[0] != "200" or r[1] != int(shape["body_bytes"]) for r in rs):
            fails.append("%s: responses %s %s (n %d)" % (tag, rec["statuses"], rec["bytes"], len(rs)))
        if rec["connections_opened"] != 1:
            fails.append("%s: curl opened %d connections, 1 expected" % (tag, rec["connections_opened"]))
        if h2 and rec["http_versions"] != ["2"]:
            fails.append("%s: HTTP versions %s, 2 expected" % (tag, rec["http_versions"]))
        if rt0 != chk.GUARDS[a["name"]] or rt1 != chk.GUARDS[a["name"]]:
            fails.append("%s: guards %s / %s, the arm assumes %s" % (tag, rt0, rt1, chk.GUARDS[a["name"]]))
        fails.extend("%s: %s" % (tag, x) for x in bad)
        return m, dump, rec
    finally:
        net.stop(eid)


def functional(work, bindir):
    bins = local_bins(bindir)
    fails, res = [], {}
    for fn in FUNCTIONAL:
        exp, rd, paths = prepare(fn, work, "f")
        h2 = "--h2" in exp["client"].get("extra_args", [])
        net = Net(rd, exp)
        got = {}
        try:
            for a in exp["arms"]:
                if a["name"].endswith("-A2"):
                    continue
                for shape in exp["shapes"]:
                    got[a["name"]] = one_leg(net, exp, paths, a, shape, fails, res, bins, h2)
        finally:
            net.close()
        base = (got.get("official") or [None, None, {}])[2].get("bytes_per_request")
        for name, g in got.items():
            if g and g[2]["bytes_per_request"] != base:
                fails.append("%s/%s: bytes per request %s, official %s" % (fn[:-5], name, g[2]["bytes_per_request"], base))
        # negative: an arm's guard evidence must fail on the leg of another patched arm
        arms = {a["name"]: a for a in exp["arms"]}
        for mine, other in (("both-on", "patched-off"), ("patched-off", "both-on"), ("read-only", "write-only"),
                            ("write-only", "read-only"), ("official", "patched-off")):
            if not got.get(other):
                continue
            m, dump, _ = got[other]
            items = [it for it in arms[mine]["evidence"] if it.get("scope") in ("field", "config") and not box_only(it)]
            failed = [it for it in items if not evidence.check_item(m, it, dump)["ok"]]
            res["negative %s: %s's guard evidence on %s's leg" % (fn[:-5], mine, other)] = "%d of %d items fail" % (len(failed), len(items))
            if not failed:
                fails.append("negative %s: %s's guard evidence passes on %s's leg" % (fn[:-5], mine, other))
    print(json.dumps({"results": res, "failed": fails}, indent=1, sort_keys=True))
    return 1 if fails else 0


def main(argv):
    if len(argv) != 3 or argv[0] not in ("validate", "functional"):
        print(__doc__)
        return 2
    work = os.path.abspath(argv[1])
    os.makedirs(work, exist_ok=True)
    return validate(work, argv[2]) if argv[0] == "validate" else functional(work, argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
