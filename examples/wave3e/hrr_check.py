#!/usr/bin/env python3
"""Direct HelloRetryRequest check with the run's own TLS client: does the
listener's key-exchange setting make the client retry its handshake?

    python3 -I examples/wave3e/hrr_check.py --envoy BIN --nighthawk BIN --out DIR [--cpus-envoy 0-3]
        [--cpus-client 20-31,60-71] [--certs DIR]

On the bench box, idle, before any leg (about 30 s). The client is the Nighthawk binary of the runs, with the
runs' client TLS socket, one request per connection. It talks to a relay in this script, and the relay
forwards to an Envoy v1.40.2 listener built by the harness from the e-tls arms. The relay looks at the
first bytes from the server on every connection for the fixed HelloRetryRequest random (RFC 8446 4.1.3).

Cases (all must hold for rc 0):
  x25519-default   listener X25519,P-256 (ecdsa-x25519), client default groups     HRR on 0 connections
  hybrid-default   listener default (ecdsa-full), client default groups            HRR on 0 connections
  x25519-control   listener X25519,P-256, client offering P-256:X25519 (positive    HRR on every connection
                   control: its only key share is P-256, so the listener must ask)
Each case also records Envoy's negotiated groups. Only own processes are started and stopped (by PID).
Loopback only: Envoy on 127.0.0.1:10110, the relay on 127.0.0.1:20110, admin on 127.0.0.1:9921.

--client envoy (laptop test only): an Envoy client in place of Nighthawk, sent requests with urllib.
"""

import argparse
import copy
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
sys.path.insert(0, os.path.join(ROOT, "examples", "settings-matrix"))
from epl import envoy_config, experiment  # noqa: E402
import make as sm  # noqa: E402

HRR_RANDOM = bytes.fromhex("CF21AD74E59A6111BE1D8C021E65B891C2A211167ABB8C5E079E09E2C8A8339C")
CFG = os.path.join(HERE, "bench-x86_64", "e-tls.json")
LPORT, RPORT, ADMIN, CADMIN, CPORT = 20110, 10110, 9921, 9931, 10111


class Relay(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.hrr = self.conns = 0
        self.lock = threading.Lock()
        self.s = socket.socket()
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(("127.0.0.1", LPORT))
        self.s.listen(256)

    def run(self):
        while True:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            with self.lock:
                self.conns += 1
            try:
                u = socket.create_connection(("127.0.0.1", RPORT), timeout=5)
            except OSError:
                c.close()
                continue
            threading.Thread(target=self.pipe, args=(c, u, False), daemon=True).start()
            threading.Thread(target=self.pipe, args=(u, c, True), daemon=True).start()

    def pipe(self, a, b, from_server):
        head, seen = b"", False
        try:
            while True:
                d = a.recv(65536)
                if not d:
                    break
                if from_server and not seen and len(head) < 8192:
                    head += d
                    if HRR_RANDOM in head:
                        seen = True
                        with self.lock:
                            self.hrr += 1
                b.sendall(d)
        except OSError:
            pass
        finally:
            for x in (a, b):
                try:
                    x.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def close(self):
        try:
            self.s.shutdown(socket.SHUT_RDWR)  # wakes the accept() of the relay thread
        except OSError:
            pass
        self.s.close()
        self.join(timeout=5)


def admin(port, path):
    with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=5) as r:
        return r.read().decode()


def wait_ready(port, proc, t=30):
    end = time.time() + t
    while time.time() < end:
        if proc.poll() is not None:
            raise RuntimeError("envoy exited rc %s" % proc.returncode)
        try:
            if admin(port, "/ready").strip() == "LIVE":
                return
        except OSError:
            pass
        time.sleep(0.2)
    raise RuntimeError("envoy not ready on admin %d" % port)


def server_bootstrap(arm_name, cert_dir):
    exp = experiment.load(CFG)
    a = [x for x in exp["arms"] if x["name"] == arm_name][0]
    b = envoy_config.bootstrap(exp["shapes"], experiment.arm_envoy(exp, a, "/r"), exp["origin"]["port"], cert_dir)
    lst = b["static_resources"]["listeners"][0]
    lst.pop("additional_addresses", None)  # 127.0.0.1 is enough here
    vh = lst["filter_chains"][0]["filters"][0]["typed_config"]["route_config"]["virtual_hosts"][0]
    vh["routes"].insert(0, {"match": {"prefix": "/"}, "direct_response": {"status": 200, "body": {
        "inline_string": "ok"}}})
    return b


def client_socket(groups):
    ts = json.loads(sm.CLIENT_TLS_HS)
    if groups:
        ts["typed_config"]["common_tls_context"]["tls_params"]["ecdh_curves"] = list(groups)
    return ts


def run_nighthawk(nh, cpus, ts, n):
    args = ["taskset", "-c", cpus, nh, "--rps", "40", "--concurrency", "1", "--connections", "4",
            "--duration", str(max(1, n // 40)), "--max-requests-per-connection", "1",
            "--max-pending-requests", "100", "--transport-socket", json.dumps(ts, separators=(",", ":")),
            "--output-format", "json", "https://127.0.0.1:%d/s" % LPORT]
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        out = p.communicate(timeout=120)[0]
    finally:
        if p.poll() is None:
            p.terminate()
            p.wait(timeout=10)
    d = json.loads(out)
    g = [r for r in d["results"] if r["name"] == "global"][0]
    return {c["name"]: int(c["value"]) for c in g.get("counters", [])}.get("benchmark.http_2xx", 0)


def run_envoy_client(envoy, cpus, ts, n, work):
    sys.path.insert(0, HERE)
    import local_check as lc
    b = lc.client_bootstrap(LPORT, [("127.0.0.1", LPORT)], CADMIN)
    b["static_resources"]["listeners"][0]["address"]["socket_address"]["address"] = "127.0.0.1"
    b["admin"]["address"]["socket_address"]["address"] = "127.0.0.1"
    b["static_resources"]["clusters"][0]["transport_socket"] = ts
    p = os.path.join(work, "client.json")
    with open(p, "w") as f:
        json.dump(b, f)
    proc = subprocess.Popen(["taskset", "-c", cpus, envoy, "-c", p, "-l", "warn", "--base-id", "7",
                             "--concurrency", "1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_ready(CADMIN, proc)
        ok = 0
        for _ in range(n):
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/s" % CPORT, timeout=5) as r:
                    ok += r.status == 200
            except OSError:
                pass
        return ok
    finally:
        proc.terminate()
        proc.wait(timeout=15)


CASES = [("x25519-default", "ecdsa-x25519", None, "none"),
         ("hybrid-default", "ecdsa-full", None, "none"),
         ("x25519-control", "ecdsa-x25519", ["P-256", "X25519"], "all")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--envoy", required=True)
    ap.add_argument("--nighthawk")
    ap.add_argument("--client", choices=("nighthawk", "envoy"), default="nighthawk")
    ap.add_argument("--out", required=True)
    ap.add_argument("--certs", help="existing certificate directory (default: make them under --out)")
    ap.add_argument("--cpus-envoy", default="0-3")
    ap.add_argument("--cpus-client", default="20-31,60-71")
    ap.add_argument("-n", type=int, default=120, help="connections per case")
    a = ap.parse_args()
    out = os.path.abspath(os.path.expanduser(a.out))
    os.makedirs(out, exist_ok=True)
    cert_dir = os.path.abspath(a.certs) if a.certs else os.path.join(out, "certs")
    if not a.certs:
        from epl.origin import make_certs
        make_certs(cert_dir, ["ecdsa-p256"], lambda m: None)
    envoy, nh = os.path.expanduser(a.envoy), os.path.expanduser(a.nighthawk or "")
    res, bad = [], 0
    for case, arm, groups, want in CASES:
        bp = os.path.join(out, "srv-%s.json" % case)
        with open(bp, "w") as f:
            json.dump(server_bootstrap(arm, cert_dir), f)
        relay = Relay()
        relay.start()
        srv = subprocess.Popen(["taskset", "-c", a.cpus_envoy, envoy, "-c", bp, "-l", "warn", "--concurrency", "2"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        r = {"case": case, "listener_arm": arm, "client_groups": groups or "default"}
        try:
            wait_ready(ADMIN, srv)
            ts = client_socket(groups)
            ok = (run_nighthawk(nh, a.cpus_client, ts, a.n) if a.client == "nighthawk"
                  else run_envoy_client(envoy, a.cpus_client, ts, a.n, out))
            time.sleep(0.5)
            st = admin(ADMIN, "/stats?filter=listener.127.0.0.1_10110.ssl.(handshake|curves)")
            r.update(responses_2xx=ok, relay_connections=relay.conns, hrr=relay.hrr,
                     envoy_ssl={k: int(v) for k, v in (ln.split(": ") for ln in st.splitlines() if ": " in ln)
                                if v.strip().isdigit() and int(v)})
            n = relay.conns
            r["ok"] = n > 0 and ok > 0 and (relay.hrr == 0 if want == "none" else relay.hrr == n)
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as e:
            r.update(ok=False, error=str(e)[-300:])
        finally:
            srv.terminate()
            try:
                srv.wait(timeout=15)
            except subprocess.TimeoutExpired:
                srv.kill()
            relay.close()
            time.sleep(1)
        bad |= not r["ok"]
        res.append(r)
        print(json.dumps(r, sort_keys=True))
    with open(os.path.join(out, "hrr-check.json"), "w") as f:
        json.dump({"client": a.client, "nighthawk": nh, "envoy": envoy, "cases": res, "ok": not bad}, f, indent=1)
    print("hrr check %s" % ("PASS" if not bad else "FAIL"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
