#!/usr/bin/env python3
"""Local checks of the W8-2 configs, in Docker, off the bench box (no measurement).

    python3 examples/wave8w2/local_check.py validate   WORKDIR BINDIR
    python3 examples/wave8w2/local_check.py functional WORKDIR BINDIR

BINDIR holds the staged binary under its bins.json file name (envoy-w8-A); it is checked against its pinned
sha256 before use. Official arms run the envoyproxy/envoy:v1.40.2 image's binary (checked against the pin).

validate    every arm's bootstrap of every config under `--mode validate` of the arm's own binary.
functional  one network namespace with the nginx origin (the harness's own nginx.conf), the arm's Envoy and a
            stand-in client: a second Envoy (official) whose cluster speaks to the first with the run's own
            client socket (HTTP/3, or HTTP/2 over TLS for h2tls); curl sends N requests to it. Per arm of
            mech-sys-s (all seven guard and protocol combinations) and of loss-s: every response 200 with 4,096
            bytes; the admin /runtime read before and after through the harness's own parser equals the arm's
            guards; the arm's evidence holds on the counters read through the leg's own stats filter and on
            /config_dump (items that need the box's client, the kernel counters or a frozen reference are
            skipped; every zero counter is also required to EXIST in the filtered snapshot: the UDP listener's
            drop counter among them); loss-s: the QUIC statistics counters exist after the client closed.
            Negative: each arm's guard evidence fails on the leg of an arm with other guards."""
import hashlib
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import evidence, experiment, leg  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


w3 = _load("w3f_local_w8w2", os.path.join(ROOT, "examples", "wave3f", "local_check.py"))
g4 = _load("w4g_local_w8w2", os.path.join(ROOT, "examples", "wave4g", "local_check.py"))
chk = _load("w8w2_check_local", os.path.join(HERE, "w2_check.py"))
mk = chk.mk
CFG = os.path.join(HERE, "configs")
N = 60


def local_bin(bindir):
    b = mk.BINS["w8-A"]
    p = os.path.join(bindir, os.path.basename(b["binary"]))
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    if h.hexdigest() != b["source_sha256"]:
        raise SystemExit("%s: sha256 %s != pin %s" % (p, h.hexdigest(), b["source_sha256"]))
    return p


def prepare(fn, work, sub):
    exp = experiment.load(os.path.join(CFG, fn))
    rd = os.path.join(work, sub, fn[:-5])
    os.makedirs(os.path.join(rd, "certs"), exist_ok=True)
    paths, _, _ = experiment.prepare_bootstraps(exp, rd, make_certs=False)
    w3.make_certs(exp, rd)
    return exp, rd, paths


def envoy_cmd(rd, binary, build):
    """docker arguments that run the arm's binary: the staged file for w8-A, the image's own for official."""
    base = ["docker", "run", "--platform", w3.PLATFORM, "-e", "ENVOY_UID=0", "-v", "%s:%s" % (rd, rd)]
    if build == "official":
        return base, [w3.IMAGE, "envoy"]
    return base + ["-v", "%s:/epl-envoy:ro" % binary], [w3.IMAGE, "/epl-envoy"]


def validate(work, bindir):
    b = local_bin(bindir)
    w3.image_sha256(mk.BINS["official"]["source_sha256"])
    out, bad = {}, 0
    for fn in sorted(os.listdir(CFG)):
        exp, rd, paths = prepare(fn, work, "v")
        builds = {a["name"]: a["build"] for a in exp["arms"]}
        for key, p in sorted(paths.items()):
            pre, img = envoy_cmd(rd, b, builds[key])
            r = w3.sh(pre + ["--rm"] + img + ["--mode", "validate", "-c", p, "-l", "warn", "--concurrency", "4"], timeout=900)
            txt = r.stdout + r.stderr
            ok = r.returncode == 0 and bool(txt.strip()) and "OK" in txt.splitlines()[-1]
            if not ok:
                # the HTTP/3 listener's validate crash of some releases: init_only on its own (as G's check)
                r2 = w3.sh(pre + ["--rm"] + img + ["--mode", "init_only", "-c", p, "-l", "warn", "--concurrency", "4"], timeout=900)
                ok2 = r2.returncode == 0
                out["%s/%s (%s)" % (fn[:-5], key, builds[key])] = ("validate rc=%d; init_only OK" % r.returncode) if ok2 else (
                    "validate rc=%d: %s | init_only rc=%d: %s" % (r.returncode, txt[-400:], r2.returncode, (r2.stdout + r2.stderr)[-400:]))
                bad += 0 if ok2 else 1
            else:
                out["%s/%s (%s)" % (fn[:-5], key, builds[key])] = "OK"
    print(json.dumps(out, indent=1))
    return 1 if bad else 0


class Net(w3.Net):
    def envoy_arm(self, bpath, binary, build, workers=4):
        pre, img = envoy_cmd(self.rd, binary, build)
        r = w3.sh(pre + ["-d", "--rm", "--network", "container:" + self.origin] + img +
                  ["-c", bpath, "--concurrency", str(workers), "-l", "warn", "--use-dynamic-base-id"])
        if r.returncode:
            raise SystemExit("envoy: " + r.stderr)
        self.ids.append(r.stdout.strip())
        return self.ids[-1]


def box_only(it):
    """Items that need the box's client (rate, 16 connections, per-leg fields), the kernel counters, a frozen
    reference, or a connection that is still open when the counters are read."""
    st, sc = it["stat"], it.get("scope", "window")
    if "ref" in it:
        return True
    if sc == "field" and not st.startswith("runtime_"):
        return True
    return sc == "window" and st.endswith(("downstream_cx_total", "cx_destroy", "cx_destroy_remote", "cx_destroy_local",
                                           "ssl.handshake", "upstream_cx_total"))


def check_evidence(a, m, dump, st):
    out, seen = [], 0
    for it in a.get("evidence", []):
        if box_only(it):
            continue
        if it.get("min") is not None and it.get("scope") != "config":
            it = dict(it, min=min(1, it["min"]))
        r = evidence.check_item(m, it, dump)
        seen += 1
        if not r["ok"]:
            out.append("%s: %s" % (r["label"], r["why"]))
        if it.get("equals") == 0 and it.get("scope", "window") in ("window", "leg") and it["stat"] not in st:
            out.append("%s: the counter is not in the filtered snapshot (a zero read from nothing)" % it["stat"])
    for it in a.get("evidence", []):
        if box_only(it) and "ref" not in it and it.get("scope", "window") == "window" and it["stat"] not in st:
            out.append("%s: not in the filtered snapshot" % it["stat"])
    return out, seen


def run_config(fn, work, b, res, fails, got):
    exp, rd, paths = prepare(fn, work, "f")
    adm = exp["envoy"]["admin_port"]
    keys = exp["measure"]["runtime_keys"]
    shape = exp["shapes"][0]
    net = Net(rd, exp)
    try:
        for a in exp["arms"]:
            tag = "%s/%s" % (fn[:-5], a["name"])
            sut = net.envoy_arm(paths[a["name"]], b, a["build"])
            try:
                if not w3.wait_ready(net, adm, 300):
                    fails.append("%s: not ready: %s" % (tag, net.logs(sut)))
                    continue
                rt0 = leg.runtime_values(net.text(adm, "/runtime"), keys)
                cp, h3 = g4.client_bootstrap(net.rd, exp, a)
                cli = net.envoy(cp, workers=1)
                if not w3.wait_ready(net, g4.CLIENT_ADMIN, 300):
                    fails.append("%s: client not ready: %s" % (tag, net.logs(cli)))
                    continue
                rs = g4.curl_n(net, N)
                time.sleep(1.0)
                st = w3.stats(net, adm, exp)
                dump = json.loads(net.text(adm, "/config_dump"))
                rt1 = leg.runtime_values(net.text(adm, "/runtime"), keys)
                cst = w3.stats(net, g4.CLIENT_ADMIN)
                net.stop(cli)
                time.sleep(2.0)
                st_closed = w3.stats(net, adm, exp)
                m = {"sut_stats_leg_end": st, "sut_stats_leg_end_ok": True, "sut_stats_window": st, "sut_stats_window_ok": True,
                     "responses_raw": N, "shape": shape["name"], "runtime_start": rt0, "runtime_end": rt1, "arm": a["name"]}
                bad, seen = check_evidence(a, m, dump, st)
                rec = {"n": len(rs), "statuses": sorted({r[0] for r in rs}), "bytes": sorted({int(r[1]) for r in rs}),
                       "evidence_items_checked": seen, "evidence_items_total": len(a["evidence"]), "runtime_start": rt0, "runtime_end": rt1,
                       "bytes_per_request": {what: (st.get(stat) or 0) / float(N) for what, stat in mk.BYTES},
                       "protocol_counters": {k: v for k, v in st.items() if k.endswith(("_http1_total", "_http2_total", "_http3_total"))},
                       "udp_listener": {k: v for k, v in st.items() if ".udp." in k},
                       "quic_stats_after_the_client_closed": {k: v for k, v in st_closed.items() if ".quic_stats." in k},
                       "http3": {k: v for k, v in st.items() if k.startswith("http3.") and v},
                       "client": {k: v for k, v in cst.items() if k.startswith("cluster.sut.upstream_cx_") and v and "bytes" not in k and "length" not in k},
                       "nonzero_error_counters": {k: v for k, v in sorted(st.items()) if v and (
                           "reset" in k or "fail" in k or "timeout" in k or "overflow" in k or "error" in k or "dropped" in k)},
                       "runtime_stats": {k: v for k, v in st.items() if k.startswith("runtime.")}}
                res[tag] = rec
                if len(rs) != N or any(r[0] != "200" or int(r[1]) != int(shape["body_bytes"]) for r in rs):
                    fails.append("%s: responses %s %s (n %d)" % (tag, rec["statuses"], rec["bytes"], len(rs)))
                if rt0 != mk.GUARDS[a["name"]] or rt1 != mk.GUARDS[a["name"]]:
                    fails.append("%s: guards %s / %s, the arm assumes %s" % (tag, rt0, rt1, mk.GUARDS[a["name"]]))
                if mk.DROPPED not in st:
                    fails.append("%s: %s is not in the filtered snapshot" % (tag, mk.DROPPED))
                if (a.get("settings") or {}).get("quic", {}).get("stats") and not rec["quic_stats_after_the_client_closed"]:
                    fails.append("%s: no quic_stats counter after the client closed" % tag)
                fails.extend("%s: %s" % (tag, x) for x in bad)
                got[tag] = (a, m, dump)
            finally:
                net.stop(sut)
    finally:
        net.close()


def functional(work, bindir):
    b = local_bin(bindir)
    fails, res, got = [], {}, {}
    for fn in ("mech-sys-s.json", "loss-s.json"):
        run_config(fn, work, b, res, fails, got)
    # negative: an arm's guard evidence must fail on the leg of an arm with other guards
    names = [t for t in got if t.startswith("mech-sys-s/h3-")]
    for mine in names:
        for other in names:
            if mk.GUARDS[mine.split("/")[1]] == mk.GUARDS[other.split("/")[1]]:
                continue
            a = got[mine][0]
            _, m, dump = got[other]
            items = [it for it in a["evidence"] if (it.get("scope") == "field" and it["stat"].startswith("runtime_")) or (
                it.get("scope") == "config" and "reloadable_features" in it["stat"]) or it["stat"] in ("layered_runtime", "runtime.num_keys")]
            failed = [it for it in items if not evidence.check_item(m, it, dump)["ok"]]
            if not failed:
                fails.append("negative: %s's guard evidence passes on %s's leg" % (mine, other))
            res.setdefault("negative", {})["%s on %s" % (mine, other)] = "%d of %d guard items fail" % (len(failed), len(items))
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
