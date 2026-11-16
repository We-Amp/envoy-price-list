#!/usr/bin/env python3
"""Turn a recorded Envoy YAML config into a route table for a `routes` shape.

    python3 from_yaml.py CONFIG.yaml OUT.json [ROUTE_PREFIX]

Takes the first virtual host of the first HTTP connection manager: its routes
(all of them, in order, or with ROUTE_PREFIX only the route whose match prefix
is ROUTE_PREFIX) and its virtual-host header fields. The md5 of the source file
is kept in the output, so the table can be traced to the run that used it.
Needs PyYAML (the harness itself does not).
"""

import hashlib
import json
import sys

import yaml

VHOST_FIELDS = ("request_headers_to_add", "response_headers_to_add", "request_headers_to_remove",
                "response_headers_to_remove")


def main():
    src, out = sys.argv[1], sys.argv[2]
    only = sys.argv[3] if len(sys.argv) > 3 else None
    raw = open(src, "rb").read()
    d = yaml.safe_load(raw)
    hcm = d["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]
    vh = hcm["route_config"]["virtual_hosts"][0]
    routes = vh["routes"]
    if only:
        routes = [r for r in routes if r["match"].get("prefix") == only]
        if len(routes) != 1:
            sys.exit("expected one route with prefix %s, found %d" % (only, len(routes)))
    for r in routes:
        if "direct_response" not in r:
            sys.exit("route %s is not a direct_response" % r["match"])
    t = {"source": src.rsplit("/", 1)[-1], "source_md5": hashlib.md5(raw).hexdigest(),
         "vhost": {k: vh[k] for k in VHOST_FIELDS if k in vh}, "routes": routes}
    if only:
        t["source_route"] = only
    with open(out, "w") as f:
        json.dump(t, f, indent=None, separators=(",", ":"), sort_keys=True)
        f.write("\n")
    print(out, len(routes), "routes", t["source_md5"])


if __name__ == "__main__":
    main()
