#!/usr/bin/env python3
"""Local checks of the W8-1 configs, in Docker, off the bench box (no measurement).

    python3 examples/wave8w1/local_check.py validate   WORKDIR BINDIR
    python3 examples/wave8w1/local_check.py functional WORKDIR BINDIR

BINDIR holds the staged binary (envoy-w8-A), checked against its pin. Official arms run the envoyproxy/envoy:v1.40.2
image's binary (checked against the pin).

validate    every arm's bootstrap of every config under `--mode validate` of the arm's own binary (init_only
            where the HTTP/3 listener's validate fails, as G's check).
functional  per config (smoke-a, smoke-b, smoke-d, smoke-c, and one arm of tail-a-r1) one network namespace with
            the nginx origin of the harness's own nginx.conf, the stream origin where the config has one, and the
            arm's Envoy. Per arm (the A2 twins left out) and shape: every response 200 with the body size and ONE
            body sha256 across all arms of the shape (the patch must not change a byte); the guards read from
            admin /runtime before and after equal the arm's; the evidence items that need no box load hold on the
            counters read through the leg's own stats filter and on /config_dump; the framing the client sees.
            smoke-b: direct from nginx, the chunked location answers `transfer-encoding: chunked` in two chunks
            of 0x8000 and its wire size is make.NGX_CH64_WIRE; the plain file answers with a content-length.
            Negative: frag-on's guard evidence fails on off's leg and the reverse; the chunked-origin item fails
            on a content-length leg. tail: the detailed histogram line of the QUIC statistics parses."""
import hashlib
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import evidence, experiment, leg, origin  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


w3 = _load("w3f_local_w8w1", os.path.join(ROOT, "examples", "wave3f", "local_check.py"))
g4 = _load("w4g_local_w8w1", os.path.join(ROOT, "examples", "wave4g", "local_check.py"))
s2lc = _load("w7s2_local_w8w1", os.path.join(ROOT, "examples", "wave7s2", "local_check.py"))
chk = _load("w8w1_check_local", os.path.join(HERE, "w1_check.py"))
tc = _load("w8w1_tail_local", os.path.join(HERE, "tail_check.py"))
mk = chk.mk
CFG = os.path.join(HERE, "configs")


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
    base = ["docker", "run", "--platform", w3.PLATFORM, "-e", "ENVOY_UID=0", "-v", "%s:%s" % (rd, rd)]
    if build == "official":
        return base, [w3.IMAGE, "envoy"]
    return base + ["-v", "%s:/epl-envoy:ro" % binary], [w3.IMAGE, "/epl-envoy"]


def validate(work, bindir):
    b = local_bin(bindir)
    w3.image_sha256(mk.BINS["official"]["source_sha256"])
    out, bad, seen = {}, 0, {}
    for fn in sorted(os.listdir(CFG)):
        exp, rd, paths = prepare(fn, work, "v")
        builds = {a["name"]: a["build"] for a in exp["arms"]}
        for key, p in sorted(paths.items()):
            # the same bootstrap under the same build is validated once (rate variants share their bootstraps)
            with open(p) as fh:
                sig = (builds[key], hashlib.sha256(fh.read().replace(rd, "RD").encode()).hexdigest())
            if sig in seen:
                continue
            seen[sig] = "%s/%s" % (fn[:-5], key)
            pre, img = envoy_cmd(rd, b, builds[key])
            r = w3.sh(pre + ["--rm"] + img + ["--mode", "validate", "-c", p, "-l", "warn", "--concurrency", "4"], timeout=900)
            txt = r.stdout + r.stderr
            ok = r.returncode == 0 and bool(txt.strip()) and "OK" in txt.splitlines()[-1]
            if not ok and "quic" in json.dumps(exp["arms"]):
                r2 = w3.sh(pre + ["--rm"] + img + ["--mode", "init_only", "-c", p, "-l", "warn", "--concurrency", "4"], timeout=900)
                ok = r2.returncode == 0
                txt = "validate rc=%d; init_only rc=%d %s" % (r.returncode, r2.returncode, (r2.stdout + r2.stderr)[-300:] if not ok else "OK")
            if not ok:
                out["%s/%s (%s)" % (fn[:-5], key, builds[key])] = txt[-400:]
                bad += 1
    print(json.dumps({"failed": out, "configs": len(os.listdir(CFG)), "distinct_bootstraps_validated": sorted(seen.values())}, indent=1))
    return 1 if bad else 0


class Net(s2lc.Net):
    def envoy_arm(self, bpath, binary, build, workers=4):
        pre, img = envoy_cmd(self.rd, binary, build)
        r = w3.sh(pre + ["-d", "--rm", "--network", "container:" + self.origin] + img +
                  ["-c", bpath, "--concurrency", str(workers), "-l", "warn", "--use-dynamic-base-id"])
        if r.returncode:
            raise SystemExit("envoy: " + r.stderr)
        self.ids.append(r.stdout.strip())
        return self.ids[-1]


def box_only(it):
    st, sc = it["stat"], it.get("scope", "window")
    if "ref" in it:
        return True
    if sc == "field" and not st.startswith(("runtime_", "stream_origin")):
        return True
    if sc == "window" and st.endswith(("cx_destroy", "cx_destroy_remote", "cx_destroy_local")):
        return True
    return s2lc.box_only(it)


def check_evidence(a, m, dump):
    out, seen = [], 0
    for it in a.get("evidence", []):
        if box_only(it) or not evidence.applies(it, m["shape"]):
            continue
        if it.get("min") is not None and it.get("max") is None and it["min"] > 1 and it.get("scope") == "leg":
            it = dict(it, min=1)
        r = evidence.check_item(m, it, dump)
        seen += 1
        if not r["ok"]:
            out.append("%s: %s" % (r["label"], r["why"]))
    return out, seen


def curl_n(net, port, path, n):
    one = ("curl -s -m 60 -o /tmp/b -D /tmp/h -w '%%{http_code}' 'http://127.0.0.1:%d%s'; "
           "echo \" $(wc -c < /tmp/b) $(sha256sum /tmp/b | cut -c1-16)\"" % (port, path))
    out, _ = net.curl("i=0; while [ $i -lt %d ]; do %s; i=$((i+1)); done; echo ---; tr -d '\\r' < /tmp/h" % (n, one))
    body, _, hdr = out.partition("---\n")
    return [tuple(x.split()) for x in body.splitlines() if len(x.split()) == 3], hdr.lower()


def run_config(fn, work, b, res, fails, got, only=None, n64=12, n1m=3):
    exp, rd, paths = prepare(fn, work, "f")
    adm, port = exp["envoy"]["admin_port"], exp["envoy"]["listener_port"]
    keys = exp["measure"]["runtime_keys"]
    run = chk.run_of(exp["name"])[0] if not fn.startswith("tail") else None
    net = Net(rd, exp)
    try:
        if fn == "smoke-b.json":
            hdr, sizes = s2lc.raw_chunks(net, exp["origin"]["port"], "/ngx-ch64")
            out, _ = net.curl("curl -s --raw -D /tmp/h -o /tmp/b 'http://127.0.0.1:%d/ngx-ch64'; cat /tmp/h /tmp/b | wc -c" % exp["origin"]["port"])
            res["direct ngx-ch64"] = {"chunk_sizes": sizes, "wire_bytes": out.strip(), "chunked": "transfer-encoding: chunked" in hdr}
            if sizes != [32768, 32768, 0] or "transfer-encoding: chunked" not in hdr or "content-length" in hdr or int(out.strip() or 0) != mk.NGX_CH64_WIRE:
                fails.append("direct ngx-ch64: %s (headers %r)" % (res["direct ngx-ch64"], hdr[:200]))
        for a in exp["arms"]:
            if a["name"].endswith("-A2") or (only and a["name"] not in only):
                continue
            for shape in exp["shapes"]:
                tag = "%s/%s/%s" % (fn[:-5], a["name"], shape["name"])
                sut = net.envoy_arm(paths[a["name"]], b, a["build"])
                cli = None
                try:
                    if not w3.wait_ready(net, adm, 300):
                        fails.append("%s: not ready: %s" % (tag, net.logs(sut)))
                        continue
                    rt0 = leg.runtime_values(net.text(adm, "/runtime"), keys)
                    path = ((a.get("client") or {}).get("paths") or {}).get(shape["name"]) or shape.get("client_path") or shape["path"]
                    n = n1m if int(shape["body_bytes"]) > 500000 else n64
                    so0 = net.so_stats() if net.stream_port else None
                    if (a.get("client") or {}).get("extra_args"):
                        cp, _ = g4.client_bootstrap(net.rd, exp, a)
                        cli = net.envoy(cp, workers=1)
                        if not w3.wait_ready(net, g4.CLIENT_ADMIN, 300):
                            fails.append("%s: client not ready: %s" % (tag, net.logs(cli)))
                            continue
                        rs, hdr = curl_n(net, g4.CLIENT_PORT, path, n)
                    else:
                        rs, hdr = curl_n(net, port, path, n)
                    time.sleep(1.0)
                    so1 = net.so_stats() if net.stream_port else None
                    st = w3.stats(net, adm, exp)
                    dump = json.loads(net.text(adm, "/config_dump"))
                    rt1 = leg.runtime_values(net.text(adm, "/runtime"), keys)
                    hist = None
                    if cli is not None:
                        net.stop(cli)
                        cli = None
                    if fn.startswith("tail"):
                        time.sleep(2.0)
                        st = w3.stats(net, adm, exp)
                        hist = net.text(adm, "/stats?histogram_buckets=detailed&filter=quic_stats").splitlines()
                    m = s2lc.leg_record(st, n, shape["name"], so0, so1) if net.stream_port else s2lc.leg_record(st, n, shape["name"])
                    m.update(runtime_start=rt0, runtime_end=rt1, arm=a["name"], envoy_exit=0)
                    bad, seen = check_evidence(a, m, dump)
                    rx, urq = st.get("cluster.origin.upstream_cx_rx_bytes_total"), st.get("cluster.origin.upstream_rq_completed")
                    rec = {"n": len(rs), "statuses": sorted({r[0] for r in rs}), "bytes": sorted({int(r[1]) for r in rs}),
                           "body_sha256_16": sorted({r[2] for r in rs}), "evidence_items_checked": seen, "evidence_items_total": len(a["evidence"]),
                           "runtime_start": rt0, "runtime_end": rt1, "upstream_rx_bytes_per_upstream_request": (rx / urq) if (rx and urq) else None,
                           "bytes_per_request": {what: (st.get(stat) or 0) / float(n) for what, stat in mk.BYTES},
                           "framing_seen_by_the_client": "chunked" if "transfer-encoding: chunked" in hdr else "content-length" if "content-length:" in hdr else "other (HTTP/2 or none)",
                           "memory": {k: v for k, v in st.items() if k.startswith("server.memory")},
                           "protocol_counters": {k: v for k, v in st.items() if k.endswith(("_http1_total", "_http2_total", "_http3_total")) and v},
                           "nonzero_error_counters": {k: v for k, v in sorted(st.items()) if v and (
                               "reset" in k or "fail" in k or "timeout" in k or "overflow" in k or "protocol_error" in k)}}
                    if hist is not None:
                        rec["quic_histogram_lines"] = [x[:300] for x in hist if "summary=" not in x]
                        rec["quic_counters"] = {k: v for k, v in st.items() if "quic_stats" in k}
                        rec["retransmitted_share_histogram (connections, non-zero)"] = tc.hist_nonzero(hist)
                        if tc.hist_nonzero(hist) is None:
                            fails.append("%s: the detailed histogram line of the retransmitted share does not parse" % tag)
                    res[tag] = rec
                    if len(rs) != n or any(r[0] != "200" or int(r[1]) != int(shape["body_bytes"]) for r in rs) or len(rec["body_sha256_16"]) != 1:
                        fails.append("%s: responses %s %s %s (n %d)" % (tag, rec["statuses"], rec["bytes"], rec["body_sha256_16"], len(rs)))
                    if run:
                        if rt0 != mk.GUARDS[run][a["name"]] or rt1 != mk.GUARDS[run][a["name"]]:
                            fails.append("%s: guards %s / %s, the arm assumes %s" % (tag, rt0, rt1, mk.GUARDS[run][a["name"]]))
                        fails.extend("%s: %s" % (tag, x) for x in bad)
                    got[tag] = (a, m, dump, rec)
                finally:
                    if cli is not None:
                        net.stop(cli)
                    net.stop(sut)
    finally:
        net.close()


def functional(work, bindir):
    b = local_bin(bindir)
    fails, res, got = [], {}, {}
    for fn in () if os.environ.get("W1_LOCAL_TAIL_ONLY") else ("smoke-a.json", "smoke-b.json", "smoke-d.json", "smoke-c.json"):
        run_config(fn, work, b, res, fails, got)
    run_config("tail-a-r1.json", work, b, res, fails, got, only=["h3-both-on"])
    # one body per shape across arms
    by = {}
    for tag, (_, _, _, rec) in got.items():
        cfg, arm, shape = tag.split("/")
        kind = "cl8k" if arm.endswith("cl8k") else "x"
        by.setdefault((cfg, shape), set()).update(rec["body_sha256_16"])
    for k, v in by.items():
        if len(v) != 1:
            fails.append("%s: the arms returned %d different bodies" % ("/".join(k), len(v)))
    res["bodies_per_shape"] = {"/".join(k): sorted(v) for k, v in by.items()}
    # negative: guard evidence across arms; the chunked-origin item on a content-length leg
    guard_items = lambda a: [it for it in a["evidence"] if (it.get("scope") == "field" and it["stat"].startswith("runtime_")) or (  # noqa: E731
        it.get("scope") == "config" and "reloadable_features" in it["stat"]) or it["stat"] in ("layered_runtime", "runtime.num_keys")]
    for mine, other in (("smoke-a/frag-on-ch8k/b64k", "smoke-a/off-ch8k/b64k"), ("smoke-a/off-ch8k/b64k", "smoke-a/frag-on-ch8k/b64k"),
                        ("smoke-a/off-ch8k/b64k", "smoke-a/official-ch8k/b64k"), ("smoke-b/frag-on/ngx-ch64", "smoke-b/off/ngx-ch64")):
        if mine in got and other in got:
            a, (_, m, dump, _) = got[mine][0], got[other]
            failed = [it for it in guard_items(a) if not evidence.check_item(m, it, dump)["ok"]]
            res.setdefault("negative", {})["%s on %s" % (mine, other)] = "%d of %d guard items fail" % (len(failed), len(guard_items(a)))
            if not failed:
                fails.append("negative: %s's guard evidence passes on %s's leg" % (mine, other))
    if "smoke-b/official/ngx-ch64" in got and "smoke-c/cl-ngx/l64" in got:
        a = got["smoke-b/official/ngx-ch64"][0]
        _, m, dump, _ = got["smoke-c/cl-ngx/l64"]
        it = [x for x in a["evidence"] if "answers chunked" in str(x.get("label"))][0]
        r = evidence.check_item(dict(m, shape="ngx-ch64"), it, dump)
        res.setdefault("negative", {})["chunked-origin item on a content-length leg"] = "fails" if not r["ok"] else "PASSES"
        if r["ok"]:
            fails.append("negative: the chunked-origin item passes on a content-length leg")
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
