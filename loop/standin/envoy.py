#!/usr/bin/env python3
"""Stand-in Envoy for the loop's local tests: a real child process that serves the admin endpoints the loop uses.

    envoy.py --admin-port P --params JSON

GET /ready, GET /stats (the 2xx counter grows at `rate` per second; the filter is ignored), GET /runtime,
POST /runtime_modify (an admin layer), GET /standin (the per-request cycles and instructions the stand-in perf
multiplies, from the current runtime value: an instance offset drawn once per process, the candidate's effect
when the key holds `on`, and per-read noise), POST /standin_rate?rps=N (the stand-in nighthawk_mcp's steering).
Params: key, on (text), rate, base_cycles, effect_lp, instance_sd_lp, noise_lp, base_ins, marker, acts_stats, seed,
instance (the seed of the draws is seed * 100003 + instance: the same draws every run)."""
import argparse
import http.server
import json
import math
import os
import random
import signal
import socketserver
import sys
import threading
import time
from urllib.parse import parse_qsl, urlsplit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-port", type=int, required=True)
    ap.add_argument("--params", default="{}")
    a = ap.parse_args()
    p = json.loads(a.params)
    key = p.get("key", "envoy.reloadable_features.standin_guard")
    on_text = str(p.get("on", "true"))
    # deterministic per instance (the session seed and the instance number), never the PID
    rng = random.Random(int(p.get("seed", 1)) * 100003 + int(p.get("instance", 0)))
    st = {"values": {key: str(p.get("initial", "false"))}, "rate": float(p.get("rate", 1000)),
          "count": 0.0, "t": time.monotonic()}
    # an acts check (opt-in): {stat: [per request while the key is off, per request while it is on]}; each named
    # counter grows with the request count at its current state's rate (a check that a key's code path acts)
    acts = {k: (float(v[0]), float(v[1])) for k, v in (p.get("acts_stats") or {}).items()}
    st["acts"] = {k: 0.0 for k in acts}
    st["counted"] = 0  # the whole requests the acts counters have been grown by
    inst_lp = rng.gauss(0.0, float(p.get("instance_sd_lp", 0.0)))
    lock = threading.Lock()

    def count():
        with lock:
            now = time.monotonic()
            dn = st["rate"] * (now - st["t"])
            st["count"] += dn
            on_now = st["values"].get(key) == on_text
            # the acts counters grow by WHOLE requests (the integer count /stats reports), so a window's delta per
            # response is the state's exact rate: no truncation skew between the two counters
            whole = int(st["count"]) - st["counted"]
            st["counted"] += whole
            for k, (off_r, on_r) in acts.items():
                st["acts"][k] += whole * (on_r if on_now else off_r)
            st["t"] = now
            return int(st["count"])

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *x):
            pass

        def _send(self, code, body):
            b = body.encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/stats":
                n = count()
                self._send(200, "http.ingress_http.downstream_rq_2xx: %d\nhttp.ingress_http.downstream_rq_5xx: 0\n"
                                "http.ingress_http.downstream_rq_completed: %d\n"
                                "http.ingress_http.downstream_cx_active: 8\n" % (n, n)
                           + "".join("%s: %d\n" % (k, int(v)) for k, v in sorted(st["acts"].items())))
            elif path == "/runtime":
                self._send(200, json.dumps({"layers": ["epl-admin"], "entries": {
                    k: {"final_value": v, "layer_values": [v]} for k, v in st["values"].items()}}))
            elif path == "/ready":
                self._send(200, "LIVE\n")
            elif path == "/standin":
                on = st["values"].get(key) == on_text
                lp = inst_lp + (float(p.get("effect_lp", 0.0)) if on else 0.0) + rng.gauss(
                    0.0, float(p.get("noise_lp", 0.0)))
                self._send(200, json.dumps({
                    "cycles_per_req": float(p.get("base_cycles", 1000.0)) * math.exp(lp / 100.0),
                    "ins_per_req": float(p.get("base_ins", 2000.0)) - (float(p.get("marker", 0.0)) if on else 0.0),
                    "rate": st["rate"]}))
            else:
                self._send(404, "no")

        def do_POST(self):
            u = urlsplit(self.path)
            if u.path == "/runtime_modify":
                st["values"].update(dict(parse_qsl(u.query)))
                return self._send(200, "OK\n")
            if u.path == "/standin_rate":
                count()
                with lock:
                    st["rate"] = float(dict(parse_qsl(u.query)).get("rps", 0))
                return self._send(200, "OK\n")
            self._send(404, "no")

    class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True
    srv = S(("127.0.0.1", a.admin_port), H)
    signal.signal(signal.SIGTERM, lambda *x: threading.Thread(target=srv.shutdown, daemon=True).start())
    srv.serve_forever()
    srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
