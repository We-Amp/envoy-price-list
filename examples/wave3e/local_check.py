#!/usr/bin/env python3
"""Laptop checks for wave 3 track E (Docker; never on the bench box).

    python3 examples/wave3e/local_check.py validate WORKDIR    every arm's bootstrap passes envoy --mode validate
    python3 examples/wave3e/local_check.py tls WORKDIR         per TLS arm: what the listener negotiates
    python3 examples/wave3e/local_check.py multi WORKDIR       the 16-address listener and the fan-out, per churn arm
    python3 examples/wave3e/local_check.py defer WORKDIR       e2-plain: TCP_DEFER_ACCEPT and the shared socket applied

`tls` starts the arm's Envoy (its harness bootstrap with a direct-response route added, so no origin
is needed) and a second Envoy v1.40.2 as the TLS client, with the client socket of the run (the same
UpstreamTlsContext as the Nighthawk legs, default groups, so the same ClientHello offer: an
X25519MLKEM768 and an X25519 key share). Between them runs a relay in this script that looks at the
server's bytes for a HelloRetryRequest (TLS 1.3 ServerHello with the fixed HRR random): an
X25519-only listener must pick the client's X25519 share without one, or the arm would price an
extra round trip (positive control: E_CLIENT_GROUPS=P-256:X25519 E_ARMS=ecdsa-x25519 must show
HRR 20). The client opens one connection per request (max_requests_per_connection 1).
Per arm it reports handshakes, resumed handshakes, the negotiated group and version, and HRR count.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, ROOT)
from epl import experiment, envoy_config  # noqa: E402
from epl.origin import make_certs  # noqa: E402

IMAGE = "envoyproxy/envoy:v1.40.2"
HRR_RANDOM = bytes.fromhex("CF21AD74E59A6111BE1D8C021E65B891C2A211167ABB8C5E079E09E2C8A8339C")
CFG = os.path.join(HERE, "bench-x86_64")
TLS_CLIENT = [True]  # the client cluster speaks TLS (False for the plaintext arms of `multi`)


def docker(*args, check=True, timeout=120):
    r = subprocess.run(["docker"] + list(args), capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError("docker %s: %s" % (args[0], r.stderr.strip()[-400:]))
    return r


def bootstraps(cfg_name, work):
    exp = experiment.load(os.path.join(CFG, cfg_name))
    cert_dir = os.path.join(work, "certs")
    kinds = sorted({(experiment.arm_envoy(exp, a).get("tls") or {}).get("cert", "rsa2048")
                    for a in exp["arms"] if experiment.arm_envoy(exp, a).get("tls")})
    if kinds:
        make_certs(cert_dir, kinds, lambda m: None)
    out = {}
    for a in exp["arms"]:
        b = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, a, "/w"), exp["origin"]["port"],
                                   "/w/certs")
        out[a["name"]] = (a, b)
    return exp, out


def validate(work):
    bad = 0
    for cfg in ("e-plain.json", "e-tls.json", "e2-plain.json", "e2b-plain.json"):
        _, bs = bootstraps(cfg, work)
        for name, (_, b) in sorted(bs.items()):
            p = os.path.join(work, "%s-%s.json" % (cfg[:-5], name))
            with open(p, "w") as f:
                json.dump(b, f)
            r = docker("run", "--rm", "-v", "%s:/w:ro" % work, IMAGE, "envoy", "--mode", "validate", "-c",
                       "/w/" + os.path.basename(p), check=False)
            ok = r.returncode == 0
            bad |= not ok
            print("%-8s %-14s %s" % (cfg[:-5], name, "OK" if ok else "FAIL " + (r.stderr or r.stdout)[-300:]))
    return bad


class Relay(threading.Thread):
    """127.0.0.1:lport -> 127.0.0.1:rport; counts HelloRetryRequests in the server's bytes."""

    def __init__(self, lport, rport):
        super().__init__(daemon=True)
        self.lport, self.rport, self.hrr, self.conns = lport, rport, 0, 0
        self.s = socket.socket()
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(("0.0.0.0", lport))
        self.s.listen(64)

    def run(self):
        while True:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            self.conns += 1
            u = socket.create_connection(("127.0.0.1", self.rport))
            threading.Thread(target=self.pipe, args=(c, u, False), daemon=True).start()
            threading.Thread(target=self.pipe, args=(u, c, True), daemon=True).start()

    def pipe(self, a, b, from_server):
        first = b""
        try:
            while True:
                d = a.recv(65536)
                if not d:
                    break
                if from_server and len(first) < 4096:
                    first += d
                    if HRR_RANDOM in first:
                        self.hrr += 1
                        first = b"x" * 4096
                b.sendall(d)
        except OSError:
            pass
        finally:
            for x in (a, b):
                try:
                    x.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass


def client_bootstrap(relay_port, endpoints=None, admin_port=9931):
    sys.path.insert(0, os.path.join(ROOT, "examples", "settings-matrix"))
    import make as sm
    ts = json.loads(sm.CLIENT_TLS_HS) if TLS_CLIENT[0] else None
    if os.environ.get("E_CLIENT_GROUPS"):
        # positive control of the HRR detector: a client offer the listener must answer with an HRR
        ts["typed_config"]["common_tls_context"]["tls_params"]["ecdh_curves"] = \
            os.environ["E_CLIENT_GROUPS"].split(":")
    return {
        "admin": {"address": {"socket_address": {"address": "0.0.0.0", "port_value": admin_port}}},
        "static_resources": {
            "listeners": [{"name": "c", "address": {"socket_address": {"address": "0.0.0.0", "port_value": 10111}},
                           "filter_chains": [{"filters": [{"name": "envoy.filters.network.http_connection_manager",
                                                           "typed_config": {
                               "@type": envoy_config.HCM, "stat_prefix": "c",
                               "route_config": {"virtual_hosts": [{"name": "v", "domains": ["*"], "routes": [
                                   {"match": {"prefix": "/"}, "route": {"cluster": "srv"}}]}]},
                               "http_filters": [{"name": "envoy.filters.http.router",
                                                 "typed_config": {"@type": envoy_config.ROUTER}}]}}]}]}],
            "clusters": [dict({"name": "srv", "type": "STRICT_DNS" if not endpoints else "STATIC",
                               "connect_timeout": "2s",
                          "load_assignment": {"cluster_name": "srv", "endpoints": [{"lb_endpoints": [{"endpoint": {
                              "address": {"socket_address": {"address": h, "port_value": p}}}}
                              for h, p in (endpoints or [("host.docker.internal", relay_port)])]}]},
                          "typed_extension_protocol_options": {
                              "envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
                                  "@type": envoy_config.UPSTREAM_HTTP,
                                  "common_http_protocol_options": {"max_requests_per_connection": 1},
                                  "explicit_http_config": {"http_protocol_options": {}}}}},
                              **({"transport_socket": ts} if ts else {}))]}}


def stats(port, flt):
    with urllib.request.urlopen("http://127.0.0.1:%d/stats?filter=%s" % (port, flt), timeout=5) as r:
        out = {}
        for ln in r.read().decode().splitlines():
            k, _, v = ln.partition(": ")
            if v.strip().isdigit():
                out[k] = int(v)
        return out


def tls(work):
    _, bs = bootstraps("e-tls.json", work)
    bad = 0
    only = os.environ.get("E_ARMS")
    for name, (a, b) in sorted(bs.items()):
        if only and name not in only.split(","):
            continue
        # a direct response in front of the proxied route: no origin needed for a handshake check
        vh = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"][
            "route_config"]["virtual_hosts"][0]
        vh["routes"].insert(0, {"match": {"prefix": "/"}, "direct_response": {"status": 200, "body": {
            "inline_string": "ok"}}})
        b["admin"]["address"]["socket_address"]["address"] = "0.0.0.0"
        # laptop only: Docker publishes a port to the container's own address, so this check (about the
        # ClientHello, not the addresses) runs the listener on the container's wildcard address
        lst = b["static_resources"]["listeners"][0]
        lst["address"]["socket_address"]["address"] = "0.0.0.0"
        lst.pop("additional_addresses", None)
        with open(os.path.join(work, "srv.json"), "w") as f:
            json.dump(b, f)
        with open(os.path.join(work, "cli.json"), "w") as f:
            json.dump(client_bootstrap(20110), f)
        relay = Relay(20110, 10110)
        relay.start()
        ids = []
        try:
            ids.append(docker("run", "-d", "--rm", "-p", "10110:10110", "-p", "9921:9921", "-v", "%s:/w:ro" % work,
                              IMAGE, "envoy", "-c", "/w/srv.json", "-l", "warn").stdout.strip())
            ids.append(docker("run", "-d", "--rm", "-p", "10111:10111", "-p", "9931:9931", "-v", "%s:/w:ro" % work,
                              IMAGE, "envoy", "-c", "/w/cli.json", "-l", "warn", "--base-id", "1").stdout.strip())
            time.sleep(4)
            n_ok = 0
            for _ in range(20):
                try:
                    with urllib.request.urlopen("http://127.0.0.1:10111/s", timeout=5) as r:
                        n_ok += r.status == 200
                except OSError:
                    pass
            st = stats(9921, "listener.0.0.0.0_10110.ssl")
            pre = "listener.0.0.0.0_10110.ssl."
            hs, reused = st.get(pre + "handshake", 0), st.get(pre + "session_reused", 0)
            curves = {k[len(pre) + 7:]: v for k, v in st.items() if k.startswith(pre + "curves.") and v}
            vers = {k[len(pre) + 9:]: v for k, v in st.items() if k.startswith(pre + "versions.") and v}
            print("%-14s 200s %2d/20  handshakes %2d  resumed %2d  curves %s  versions %s  relay conns %d  HRR %d"
                  % (name, n_ok, hs, reused, curves, vers, relay.conns, relay.hrr))
            want = "X25519" if name == "ecdsa-x25519" else "X25519MLKEM768"
            churn = name != "tls-ka"
            ok = (n_ok == 20 and relay.hrr == 0 and set(curves) == {want} and set(vers) == {"TLSv1.3"}
                  and (not churn or hs == 20)
                  and ((reused >= 18) if name == "ecdsa-res" else (reused == 0)))
            bad |= not ok
            print("    %s" % ("OK" if ok else "FAIL"))
        finally:
            for i in ids:
                docker("rm", "-f", i, check=False)
            relay.s.close()
            time.sleep(1)
    return bad


def text(port, path):
    with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=5) as r:
        return r.read().decode()


def multi(work, n_req=64):
    """The run's listener as configured (127.0.0.1 plus 15 additional addresses), with a client Envoy
    in the same network namespace that spreads one-request connections round robin over the 16
    addresses: every address accepts, every connection counts in one listener's stats, and resumption
    works across addresses (one TLS context, one ticket key)."""
    bad = 0
    for cfg in ("e-plain.json", "e-tls.json"):
        exp, bs = bootstraps(cfg, work)
        for name, (a, b) in sorted(bs.items()):
            if "multi_target" not in (a.get("client") or {}):
                continue
            mt = a["client"]["multi_target"]
            vh = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"][
                "route_config"]["virtual_hosts"][0]
            vh["routes"].insert(0, {"match": {"prefix": "/"}, "direct_response": {"status": 200, "body": {
                "inline_string": "ok"}}})
            b["admin"]["address"]["socket_address"]["address"] = "0.0.0.0"
            import ipaddress
            first = ipaddress.IPv4Address(mt.get("base", "127.0.0.1"))
            eps = [(str(first + i), 10110) for i in range(int(mt["count"]))]
            TLS_CLIENT[0] = bool(experiment.arm_envoy(exp, a).get("tls"))
            with open(os.path.join(work, "srv.json"), "w") as f:
                json.dump(b, f)
            with open(os.path.join(work, "cli.json"), "w") as f:
                json.dump(client_bootstrap(0, eps), f)
            ids = []
            try:
                srv = docker("run", "-d", "--rm", "-p", "9921:9921", "-p", "9931:9931", "-p", "10111:10111",
                             "-v", "%s:/w:ro" % work, IMAGE, "envoy", "-c", "/w/srv.json", "-l", "warn").stdout.strip()
                ids.append(srv)
                time.sleep(3)
                ids.append(docker("run", "-d", "--rm", "--network", "container:" + srv, "-v", "%s:/w:ro" % work,
                                  IMAGE, "envoy", "-c", "/w/cli.json", "-l", "warn", "--base-id", "1",
                                  "--concurrency", "1").stdout.strip())
                time.sleep(4)
                ok200 = 0
                for _ in range(n_req):
                    try:
                        with urllib.request.urlopen("http://127.0.0.1:10111/s", timeout=5) as r:
                            ok200 += r.status == 200
                    except OSError:
                        pass
                st = stats(9921, "listener\\.")
                scopes = sorted({k[len("listener."):k.index("_10110") + 6] for k in st
                                 if k.startswith("listener.") and "_10110" in k})
                pre = "listener.127.0.0.1_10110."
                cx, hs, ru = st.get(pre + "downstream_cx_total", 0), st.get(pre + "ssl.handshake", 0), \
                    st.get(pre + "ssl.session_reused", 0)
                hosts = {}
                for ln in text(9931, "/clusters").splitlines():
                    p = ln.split("::")
                    if len(p) == 4 and p[0] == "srv" and p[2] == "rq_success":
                        hosts[p[1]] = int(p[3])
                spread = sorted(hosts.values())
                tls_on = TLS_CLIENT[0]
                res = name == "ecdsa-res"
                ok = (ok200 == n_req and scopes == ["127.0.0.1_10110"] and cx == n_req and len(hosts) == len(eps)
                      and spread == [n_req // len(eps)] * len(eps)
                      and (not tls_on or hs == n_req) and (ru >= n_req - 2 if res else ru == 0))
                bad |= not ok
                print("%-8s %-14s 200s %d/%d  listener scopes %s  cx %d  handshakes %d  resumed %d  per-address "
                      "requests min %s max %s over %d  %s" % (cfg[:-5], name, ok200, n_req, scopes, cx, hs, ru,
                                                             spread[0] if spread else None,
                                                             spread[-1] if spread else None, len(hosts),
                                                             "OK" if ok else "FAIL"))
            finally:
                for i in ids[::-1]:
                    docker("rm", "-f", i, check=False)
                time.sleep(1)
    return bad


PROBE = r"""
import json, socket, sys, time, urllib.request
n = int(sys.argv[1])
def cx():
    t = urllib.request.urlopen("http://127.0.0.1:9921/stats?filter=listener.127.0.0.1_10110.downstream_cx_total").read()
    return int(t.decode().split(": ")[1])
c0 = cx()
socks = [socket.create_connection(("127.0.0.%d" % (i + 1), 10110)) for i in range(n)]
time.sleep(0.5)
silent = cx() - c0
ok = 0
for i, s in enumerate(socks):
    s.sendall(b"GET /s HTTP/1.1\r\nhost: x\r\n\r\n")
    ok += s.recv(4096).startswith(b"HTTP/1.1 200")
    s.close()
time.sleep(0.3)
print(json.dumps({"accepted_while_silent": silent, "served": ok, "accepted_total": cx() - c0}))
"""


def defer(work, n=16):
    """e2-plain arms: a connect that sends nothing is not handed to Envoy under TCP_DEFER_ACCEPT, on every
    one of the 16 addresses; every arm serves on all 16; the shared-socket arm's dump has
    enable_reuse_port false and one listen socket per address."""
    bad = 0
    exp, bs = bootstraps("e2-plain.json", work)
    with open(os.path.join(work, "probe.py"), "w") as f:
        f.write(PROBE)
    for name, (a, b) in sorted(bs.items()):
        if name in ("ka", "c1-A2"):
            continue
        vh = b["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"][
            "route_config"]["virtual_hosts"][0]
        vh["routes"].insert(0, {"match": {"prefix": "/"}, "direct_response": {"status": 200, "body": {
            "inline_string": "ok"}}})
        with open(os.path.join(work, "srv.json"), "w") as f:
            json.dump(b, f)
        ids = []
        try:
            srv = docker("run", "-d", "--rm", "-v", "%s:/w:ro" % work, IMAGE, "envoy", "-c", "/w/srv.json",
                         "-l", "warn", "--concurrency", "4").stdout.strip()
            ids.append(srv)
            time.sleep(3)
            r = docker("run", "--rm", "--network", "container:" + srv, "-v", "%s:/w:ro" % work,
                       "python:3.13-alpine", "python3", "-I", "/w/probe.py", str(n))
            res = json.loads(r.stdout.strip().splitlines()[-1])
            lis = docker("run", "--rm", "--network", "container:" + srv, "python:3.13-alpine", "python3", "-I", "-c",
                         "import urllib.request as u;print(u.urlopen('http://127.0.0.1:9921/config_dump').read()"
                         ".decode())").stdout
            reuse_off = '"enable_reuse_port": false' in lis
            defer_on = '"TCP_DEFER_ACCEPT"' in lis
            want_silent = 0 if name == "c1-defer" else n
            ok = (res["accepted_while_silent"] == want_silent and res["served"] == n and res["accepted_total"] == n
                  and reuse_off == (name == "c1-shared") and defer_on == (name == "c1-defer"))
            bad |= not ok
            print("%-10s %s  dump: reuse_port off %s, defer %s  %s" % (name, res, reuse_off, defer_on,
                                                                     "OK" if ok else "FAIL"))
        finally:
            for i in ids:
                docker("rm", "-f", i, check=False)
            time.sleep(1)
    return bad


def main():
    mode, work = sys.argv[1], os.path.abspath(sys.argv[2])
    os.makedirs(work, exist_ok=True)
    sys.exit({"validate": validate, "tls": tls, "multi": multi, "defer": defer}[mode](work))


if __name__ == "__main__":
    main()
