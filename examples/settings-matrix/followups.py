#!/usr/bin/env python3
"""Write the follow-up experiments of the settings matrix (after the first matrix runs):

    python3 examples/settings-matrix/followups.py

  f1-two-hop          two hops with the second hop loaded evenly: one upstream pool per
                      downstream connection on every Envoy, against the stock chain
  f2-buffer-limit     buffer limit with flow-control counters, plus a body that fits
  f2-ext-authz        ext_authz: HTTP and gRPC service
  f3-tls-cert         certificate type, reconnects spread out in time
  f3-tls-resumption   session resumption, reconnects spread out in time
  aa-tls, aa-h2       A/A on the TLS shapes and on the HTTP/2 shape

Same base, binary and CPUs as make.py.
"""

import json
import os

import make

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "followups")
F = dict(make.BASE, workdir="~/epl/runs/smf")
F.pop("floor_from")


def shapes():
    S = make.shapes({})
    S["s2k"] = {"name": "s2k", "path": "/s2k", "kind": "proxied", "body_bytes": 2048, "rps": 5200}
    # handshake-heavy TLS with reconnects spread out in time: no prefetch and the client's
    # default (MRU) connection reuse, so every client worker carries its load on about one
    # connection, which reconnects every N requests at its own moment. With prefetch and
    # LRU reuse (make.py's tls-hs) all 512 connections reach their N-th request together and
    # reconnect in waves. The request that triggers a reconnect waits for it, so the
    # pending gate allows one waiting request per connection opened; overflow is gated.
    S["tls-hs-st"] = dict(S["tls-hs"], name="tls-hs-st", path="/sh",
                          client_base_args=["--max-pending-requests", "1000"],
                          validity={"max_pending_total": "client_cx"})
    # keep-alive TLS: the 512 start-up handshakes overflow the client pool before the
    # window (RSA arms only); the pending gate is bounded at twice the connections
    S["tls-ka"] = dict(S["tls-ka"], validity={"max_pending_total": 1024,
                                               "overflow_ignore": ["upstream_cx_overflow"]})
    return S


def configs():
    S = shapes()
    out = {}

    def row(fname, name, arms, shp, **kw):
        c = json.loads(json.dumps(F))
        c.update(name=name, base_arm=arms[0]["name"], arms=arms, shapes=[S[x] for x in shp])
        for k, v in kw.items():
            if isinstance(v, dict) and isinstance(c.get(k), dict):
                c[k] = dict(c[k], **v)
            else:
                c[k] = v
        out[fname] = c

    ppd = {"upstream_pool_per_downstream": True}
    row("f1-two-hop.json", "smf-two-hop",
        [make.arm("one-hop"),
         make.arm("one-hop-ppd", dict(ppd)),
         # the stock chain: the first hop's pool reuses its most recently freed
         # connection, so the second hop's load concentrates; share gate off for hop 2
         dict(make.arm("two-hop-stock", {"two_hop": True}), validity={"hop2_worker_share_gate": False}),
         # every Envoy with one upstream pool per downstream connection: the second hop gets
         # as many busy connections as the first; share gate on for both hops
         make.arm("two-hop-ppd", dict(ppd, two_hop=True, hop2_settings=dict(ppd)))],
        ["s"], cpus=dict(F["cpus"], hop2="4-7"), primary_metric="cycles_total_per_hop",
        comparisons="all_pairs", rounds=16, rounds_block=8, rounds_max=32)
    row("f2-buffer-limit.json", "smf-buffer-limit",
        [make.arm("buffer-default"), make.arm("buffer-4k", {"buffer_limit_bytes": 4096})], ["m", "s2k"])
    row("f2-ext-authz.json", "smf-ext-authz",
        [make.arm("authz-off"), make.arm("authz-http", {"ext_authz": "http"}),
         make.arm("authz-grpc", {"ext_authz": "grpc"})], ["s"],
        origin=dict(F["origin"], authz_port=8093, authz_grpc_port=8094))
    full = {"resumption": False}
    row("f3-tls-cert.json", "smf-tls-cert",
        [make.arm("rsa2048", {"tls": dict(full, cert="rsa2048")}),
         make.arm("ecdsa-p256", {"tls": dict(full, cert="ecdsa-p256")})], ["tls-ka", "tls-hs-st"])
    row("f3-tls-resumption.json", "smf-tls-resumption",
        [make.arm("resumption-off", {"tls": {"cert": "rsa2048", "resumption": False}}),
         make.arm("resumption-on", {"tls": {"cert": "rsa2048"}})], ["tls-hs-st"])
    aa = dict(expect="aa", rounds_max=36)
    row("aa-tls.json", "smf-aa-tls",
        [make.arm("A", {"tls": dict(full, cert="rsa2048")}), make.arm("A2", {"tls": dict(full, cert="rsa2048")})],
        ["tls-ka", "tls-hs-st"], **aa)
    row("aa-h2.json", "smf-aa-h2", [make.arm("A"), make.arm("A2")], ["fh2"],
        envoy={"codec_type": "HTTP2"},
        client={"extra_args": ["--h2", "--prefetch-connections", "--max-pending-requests", "1000"]}, **aa)
    for k in ("aa-tls.json", "aa-h2.json"):
        for x in ("stop", "rounds_block", "primary_metric", "comparisons"):
            out[k].pop(x, None)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn, c in configs().items():
        with open(os.path.join(OUT, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)


if __name__ == "__main__":
    main()
