#!/usr/bin/env python3
"""Local checks of the track C configs with the official Envoy v1.40.2 binary, in Docker, off the
bench box (no measurement; a laptop is enough).

    python3 examples/wave1c/local_check.py validate WORKDIR
    python3 examples/wave1c/local_check.py functional WORKDIR

The image envoyproxy/envoy:v1.40.2 (linux/amd64) carries the release binary: its sha256 is
checked against the one the configs pin before anything runs. WORKDIR must be a directory Docker
can bind-mount at the same path (the bootstraps name files by absolute path).

validate     every arm of every config in configs/: the harness writes the bootstrap (and the
             xDS files), `envoy --mode validate` must print OK.
functional   one container network namespace with the origin (nginx, the harness's own
             nginx.conf), the ext_proc service and Envoy: every ext_proc and ext_authz arm
             serves requests and its counters show what the arm says (messages per request,
             client, no failure); every xDS update kind at the small size applies (update
             counters, modified clusters, membership changes) and, for the cluster in use, the
             connections the origin accepted per update. Prints a JSON summary; exit 1 on a
             failed check.
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from epl import envoy_config, experiment, xds  # noqa: E402

IMAGE = "envoyproxy/envoy:v1.40.2"
PLATFORM = "linux/amd64"
NGINX = "nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11"
CFG = os.path.join(HERE, "configs")


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


def validate(work):
    out, bad = {}, 0
    for fn in sorted(os.listdir(CFG)):
        if fn.startswith("smoke-"):
            continue
        exp = load(fn)
        image_sha256(exp["arms"][0]["source_sha256"]) if not out else None
        rd = os.path.join(work, "validate", fn[:-5])
        os.makedirs(rd, exist_ok=True)
        paths, _, _ = experiment.prepare_bootstraps(exp, rd, make_certs=False)
        for a in exp["arms"]:
            p = paths[a["name"]]
            r = sh(["docker", "run", "--rm", "--platform", PLATFORM, "-v", "%s:%s:ro" % (rd, rd), IMAGE,
                    "envoy", "--mode", "validate", "-c", p, "-l", "warn"], timeout=300)
            txt = r.stdout + r.stderr
            ok = r.returncode == 0 and "OK" in txt.splitlines()[-1] if txt.strip() else False
            out["%s/%s" % (fn[:-5], a["name"])] = "OK" if ok else txt[-600:]
            bad += 0 if ok else 1
    print(json.dumps(out, indent=1))
    return 1 if bad else 0


# ---------------------------------------------------------------- functional

class Net:
    """The origin container (nginx) owns the network namespace; everything else joins it."""

    def __init__(self, work, origin_cfg, shapes):
        self.work, self.ids = work, []
        od = os.path.join(work, "origin")
        www = os.path.join(od, "www")
        os.makedirs(os.path.join(www, "_authz"), exist_ok=True)
        for rel, size in envoy_config.origin_files(shapes).items():
            with open(os.path.join(www, rel), "wb") as f:
                f.write(b"a" * size)
        with open(os.path.join(www, envoy_config.AUTHZ_GRPC_FILE), "wb") as f:
            f.write(envoy_config.AUTHZ_GRPC_BODY)
        with open(os.path.join(od, "nginx.conf"), "w") as f:
            f.write(envoy_config.nginx_conf(origin_cfg["port"], 2, None, origin_cfg.get("authz_grpc_port"),
                                            stub_status=True))
        r = sh(["docker", "run", "-d", "--rm", "-v", "%s/nginx.conf:/etc/nginx/nginx.conf:ro" % od,
                "-v", "%s:/www:ro" % www, NGINX])
        if r.returncode:
            raise SystemExit("origin: " + r.stderr)
        self.origin = r.stdout.strip()
        self.ids.append(self.origin)

    def run(self, args, mounts=(), entrypoint=None):
        cmd = ["docker", "run", "-d", "--rm", "--platform", PLATFORM, "--network", "container:" + self.origin]
        for m in mounts:
            cmd += ["-v", m]
        if entrypoint:
            cmd += ["--entrypoint", entrypoint]
        r = sh(cmd + [IMAGE] + list(args))
        if r.returncode:
            raise SystemExit("docker run: " + r.stderr)
        self.ids.append(r.stdout.strip())
        return self.ids[-1]

    def get(self, port, path, n=1):
        """n GETs from inside the namespace (busybox wget in the origin container); [status]."""
        script = ("i=0; while [ $i -lt %d ]; do wget -q -S -O /dev/null http://127.0.0.1:%d%s 2>&1 | "
                  "awk '/HTTP\\//{print $2}' | tail -1; i=$((i+1)); done") % (n, port, path)
        r = sh(["docker", "exec", self.origin, "sh", "-c", script], timeout=600)
        return r.stdout.split()

    def text(self, port, path):
        r = sh(["docker", "exec", self.origin, "wget", "-q", "-O-", "http://127.0.0.1:%d%s" % (port, path)],
               timeout=60)
        return r.stdout

    def stop(self, cid):
        sh(["docker", "stop", "-t", "2", cid])
        if cid in self.ids:
            self.ids.remove(cid)

    def close(self):
        for cid in reversed(self.ids):
            sh(["docker", "stop", "-t", "2", cid])


def stats(net, admin):
    out = {}
    for line in net.text(admin, "/stats").splitlines():
        k, _, v = line.partition(": ")
        try:
            out[k] = int(v)
        except ValueError:
            pass
    return out


def wait_ready(net, admin, t=60):
    end = time.time() + t
    while time.time() < end:
        if "LIVE" in net.text(admin, "/ready"):
            return True
        time.sleep(0.5)
    return False


def start_envoy(net, rd, bpath, workers=2):
    return net.run(["envoy", "-c", bpath, "--concurrency", str(workers), "-l", "warn"], mounts=["%s:%s" % (rd, rd)])


def functional(work):
    fails, res = [], {}
    xp = load("extproc.json")
    image_sha256(xp["arms"][0]["source_sha256"])
    rd = os.path.join(work, "functional", "extproc")
    os.makedirs(rd, exist_ok=True)
    paths, _, _ = experiment.prepare_bootstraps(xp, rd, make_certs=False)
    binary = os.path.join(ROOT, xp["origin"]["ext_proc_binary"])
    adm, lport = xp["envoy"]["admin_port"], xp["envoy"]["listener_port"]
    net = Net(os.path.join(work, "functional"), xp["origin"], xp["shapes"])
    try:
        svc = net.run(["-addr", "127.0.0.1:%d" % xp["origin"]["ext_proc_port"]],
                      mounts=["%s:/epl-extproc:ro" % binary], entrypoint="/epl-extproc")
        time.sleep(1)
        n = 50
        for a in xp["arms"]:
            if a["name"].endswith("-A2"):
                continue
            eid = start_envoy(net, rd, paths[a["name"]])
            if not wait_ready(net, adm):
                fails.append("%s: not ready" % a["name"])
                net.stop(eid)
                continue
            codes = net.get(lport, "/s", n)
            st = stats(net, adm)
            keep = {k: v for k, v in st.items() if (".ext_proc." in k or ".ext_authz." in k or k.startswith("grpc."))
                    and v and not k.endswith("_bucket")}
            res[a["name"]] = {"codes": sorted(set(codes)), "requests": len(codes), "stats": keep}
            if codes != ["200"] * n:
                fails.append("%s: status codes %s" % (a["name"], sorted(set(codes))))
            for ev in a.get("evidence", []):
                name, want = ev["stat"], ev.get("per_request", ev.get("equals"))
                if ev.get("absent"):
                    if name in st and st[name]:
                        fails.append("%s: %s present (%s)" % (a["name"], name, st[name]))
                    continue
                if name.endswith("upstream_cx_total"):
                    continue  # the window rule; here the connection is opened by these requests
                v = st.get(name, 0)
                exp_v = want * n if "per_request" in ev else want
                if v != exp_v:
                    fails.append("%s: %s = %s, expected %s" % (a["name"], name, v, exp_v))
            net.stop(eid)
        res["ext_proc_service"] = json.loads(net.text(xp["origin"]["ext_proc_port"], "/epl-stats") or "{}")
        net.stop(svc)
    finally:
        net.close()
    res["xds"] = functional_xds(work, fails)
    print(json.dumps({"results": res, "failed": fails}, indent=1, sort_keys=True))
    return 1 if fails else 0


PY = "python:3.12-alpine"


def functional_xds(work, fails, updates=5, hz=2.0):
    """The update kinds at the small size. The renames happen inside the Docker VM (a Python
    container runs epl/xds.py on a named volume that Envoy also mounts): a rename on the Mac side
    of a bind mount raises no inotify event in the VM, which is a property of the laptop setup,
    not of the bench box."""
    exp = load("xds-small.json")
    rd = os.path.join(work, "functional", "xds")
    os.makedirs(rd, exist_ok=True)
    paths, _, _ = experiment.prepare_bootstraps(exp, rd, make_certs=False)
    adm, lport = exp["envoy"]["admin_port"], exp["envoy"]["listener_port"]
    out = {}
    net = Net(os.path.join(work, "functional-xds"), exp["origin"], exp["shapes"])
    vol = "epl-w1c-xds-%d" % os.getpid()
    mounts = ["%s:%s:ro" % (rd, rd), "%s:%s" % (vol, os.path.join(rd, "xds"))]
    r = sh(["docker", "run", "-d", "--rm", "-v", "%s:/h:ro" % ROOT] + sum((["-v", m] for m in mounts), [])
           + [PY, "sleep", "3600"])
    if r.returncode:
        raise SystemExit("python container: " + r.stderr)
    py = r.stdout.strip()

    def drive(*args):
        q = sh(["docker", "exec", "-w", "/h", py, "python3", "examples/wave1c/local_check.py", "xds-driver"]
               + [str(x) for x in args], timeout=300)
        if q.returncode:
            raise SystemExit("xds-driver: " + q.stderr[-800:])
        return json.loads(q.stdout or "{}")
    try:
        for a in exp["arms"]:
            if a["name"].endswith("-A2"):
                continue
            drive("init", a["name"], rd)
            eid = net.run(["envoy", "-c", paths[a["name"]], "--concurrency", "2", "-l", "warn"], mounts=mounts)
            if not wait_ready(net, adm, 120):
                fails.append("xds %s: not ready" % a["name"])
                net.stop(eid)
                continue
            up = experiment.arm_settings(a).get("xds_update")
            stop = threading.Event()
            load_t = threading.Thread(target=lambda: [net.get(lport, "/s", 20) for _ in iter(stop.is_set, True)],
                                      daemon=True)
            load_t.start()
            time.sleep(1.0)
            q0 = stats(net, adm)
            acc0 = accepts(net, exp["origin"]["port"])
            dr = drive("update", a["name"], rd, updates, hz) if up else {"renames": 0, "error": None}
            time.sleep(1.0)
            q1 = stats(net, adm)
            acc1 = accepts(net, exp["origin"]["port"])
            stop.set()
            load_t.join(30)
            d = lambda k: q1.get(k, 0) - q0.get(k, 0)  # noqa: E731
            rec = {"renames": dr["renames"], "updater_error": dr["error"],
                   "rds_update_success": d("http.ingress_http.rds.local.update_success"),
                   "cds_update_success": d("cluster_manager.cds.update_success"),
                   "eds_update_success": d("cluster.epl-eds.update_success"),
                   "cluster_modified": d("cluster_manager.cluster_modified"),
                   "eds_membership_change": d("cluster.epl-eds.membership_change"),
                   "eds_membership_total": q1.get("cluster.epl-eds.membership_total"),
                   "origin_upstream_cx_total": d("cluster.origin.upstream_cx_total"),
                   "origin_accepts": (acc1 - acc0 - 1) if acc0 is not None and acc1 is not None else None,
                   "rejected": q1.get("cluster_manager.cds.update_rejected", 0)
                   + q1.get("http.ingress_http.rds.local.update_rejected", 0),
                   "active_clusters": q1.get("cluster_manager.active_clusters"),
                   "requests_2xx": d("http.ingress_http.downstream_rq_2xx"),
                   "requests_5xx": d("http.ingress_http.downstream_rq_5xx")}
            out[a["name"]] = rec
            kind = up["kind"] if up else None
            want = {"rds": updates if kind in ("rds", "rds_same") else 0,
                    "cds": updates if kind in ("cds", "cds_same", "cds_active") else 0,
                    "eds": updates if kind == "eds" else 0}
            for t in ("rds", "cds", "eds"):
                if rec["%s_update_success" % t] != want[t]:
                    fails.append("xds %s: %s updates %s, expected %s" % (a["name"], t, rec["%s_update_success" % t],
                                                                         want[t]))
            mod = updates if kind in ("cds", "cds_active") else 0
            if rec["cluster_modified"] != mod:
                fails.append("xds %s: cluster_modified %s, expected %s" % (a["name"], rec["cluster_modified"], mod))
            if rec["eds_membership_change"] != (updates if kind == "eds" else 0):
                fails.append("xds %s: membership changes %s" % (a["name"], rec["eds_membership_change"]))
            if rec["rejected"] or rec["requests_5xx"] or rec["updater_error"]:
                fails.append("xds %s: rejected %s, 5xx %s, updater %s" % (a["name"], rec["rejected"],
                                                                         rec["requests_5xx"], rec["updater_error"]))
            net.stop(eid)
    finally:
        net.close()
        sh(["docker", "stop", "-t", "1", py])
        sh(["docker", "volume", "rm", vol])
    return out


def xds_driver(argv):
    """Inside the Python container: init ARM RUN_DIR | update ARM RUN_DIR N HZ."""
    exp = load("xds-small.json")
    a = [x for x in exp["arms"] if x["name"] == argv[1]][0]
    st = experiment.xds_state(exp, a, argv[2])
    if argv[0] == "init":
        xds.write_initial(st)
        print("{}")
        return 0
    up = experiment.arm_settings(a)["xds_update"]
    u = xds.Updater(st, up["kind"], float(argv[4]), [1], count=int(argv[3]))
    u.start()
    u.join(int(argv[3]) / float(argv[4]) + 10)
    print(json.dumps({"renames": len(u.renames), "error": u.error}))
    return 0


def accepts(net, port):
    from epl.leg import parse_stub_accepts
    return parse_stub_accepts(net.text(port, envoy_config.ORIGIN_STATUS_PATH))


def main(argv):
    if argv and argv[0] == "xds-driver":
        return xds_driver(argv[1:])
    if len(argv) != 2 or argv[0] not in ("validate", "functional"):
        print(__doc__)
        return 2
    work = os.path.abspath(argv[1])
    os.makedirs(work, exist_ok=True)
    return validate(work) if argv[0] == "validate" else functional(work)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
