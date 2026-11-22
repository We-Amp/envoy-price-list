"""File-based State-of-the-World xDS for the per-update price (no control plane process).

An arm with the `xds` setting gets its routes (RDS), its clusters (CDS) and, when asked, one
EDS cluster from files the harness writes. Envoy watches each file on its own path (inotify on
the file's directory, filtered by file name; no `watched_directory`), and every resource type
has its own directory, so a rename of the RDS file triggers RDS only. Envoy re-reads the whole
file on every rename: each update is a full SotW push of that type.

Sizes (all generic, no traffic goes to the filler resources):
  routes      filler prefix routes, after the shapes' own routes (so a request matches on its
              first route at every size: the request path costs the same, only the table grows);
              each adds one response header and points at a filler cluster
  clusters    filler STATIC clusters to the origin address, never used by a request
  eds_endpoints   one filler EDS cluster (`epl-eds`) with that many endpoints (0: none)
The origin cluster comes by CDS too (with a metadata value), so an update can change it.

Update kinds (`xds_update`: {kind, rate_hz}); update k of a leg:
  rds         one filler route's header value becomes "k": a changed RouteConfiguration
              (Envoy builds the whole table again)
  rds_same    the same RouteConfiguration with a new version_info (parse and compare only)
  cds         one filler cluster's metadata value becomes "k": one cluster modified
  cds_same    the same clusters with a new version_info (parse and compare only)
  cds_active  the origin cluster's metadata value becomes "k": the cluster carrying traffic is
              modified (Envoy replaces it; its connection pools drain)
  eds         endpoint k mod N leaves epl-eds and the one that left before comes back: one
              host removed and one added per update

Timing (one leg): a "pre" updater runs from Envoy's start through the warm-up at the leg's
rate, so the window sees steady churn, not the first update after a quiet minute. It stops
before the window's first stats read and the leg waits `guard_s`; the window updater then
renames at t0 + (j + 0.5) / rate for j < window_s * rate, so every update of the window
starts at least half a period after the window opens and is due to end half a period before
it closes. The leg checks both: the counters show every pre update applied before the window
and exactly the window's updates inside it, and the last update time Envoy reports is before
the window's end.
"""

import json
import os
import threading
import time

RDS_TYPE = "type.googleapis.com/envoy.config.route.v3.RouteConfiguration"
CDS_TYPE = "type.googleapis.com/envoy.config.cluster.v3.Cluster"
EDS_TYPE = "type.googleapis.com/envoy.config.endpoint.v3.ClusterLoadAssignment"
KINDS = ("rds", "rds_same", "cds", "cds_same", "cds_active", "eds")
ROUTE_NAME = "local"
EDS_CLUSTER = "epl-eds"
FILES = {"rds": ("rds", "rds.json"), "cds": ("cds", "cds.json"), "eds": ("eds", "eds.json")}
EDS_PORT_BASE = 30000
SIZE_KEYS = ("routes", "clusters", "eds_endpoints")

# counters (window deltas) and gauges per resource type in Envoy's stats; the stat filter of an
# xDS experiment must keep them (STAT_FILTER_EXTRA)
STATS = {
    "rds": "http.ingress_http.rds.%s." % ROUTE_NAME,
    "cds": "cluster_manager.cds.",
    "eds": "cluster.%s." % EDS_CLUSTER,
}
STAT_FILTER_EXTRA = (r"cluster_manager\.(cds\.|cluster_added|cluster_modified|cluster_removed|cluster_updated|"
                     r"cluster_updated_via_merge|update_merge_cancelled|update_out_of_merge_window|active_clusters|"
                     r"warming_clusters)|cluster\.%s\.(update_|membership_)" % EDS_CLUSTER)


def kind_type(kind):
    """The resource type an update kind writes: rds, cds or eds."""
    if kind not in KINDS:
        raise ValueError("xds_update.kind must be one of %s" % (KINDS,))
    return kind.split("_")[0]


def check_size(x):
    bad = sorted(set(x) - set(SIZE_KEYS) - {"dir"})
    if bad:
        raise ValueError("xds takes %s (got %s)" % (SIZE_KEYS, bad))
    for k in ("routes", "clusters"):
        if int(x.get(k, 0)) < 1:
            raise ValueError("xds.%s must be at least 1" % k)
    if int(x.get("eds_endpoints", 0)) < 0:
        raise ValueError("xds.eds_endpoints must be >= 0")


def paths(xdir):
    return {t: os.path.join(xdir, d, f) for t, (d, f) in FILES.items()}


def filler_cluster(i):
    return "epl-filler-%05d" % i


def _socket(addr, port):
    return {"socket_address": {"address": addr, "port_value": int(port)}}


def _meta(v):
    return {"filter_metadata": {"epl": {"v": str(v)}}}


def static_cluster(name, port, meta_v):
    return {"@type": CDS_TYPE, "name": name, "connect_timeout": "1s", "type": "STATIC", "lb_policy": "ROUND_ROBIN",
            "metadata": _meta(meta_v),
            "load_assignment": {"cluster_name": name, "endpoints": [{"lb_endpoints": [
                {"endpoint": {"address": _socket("127.0.0.1", port)}}]}]}}


def config_source(path):
    return {"path_config_source": {"path": path}, "resource_api_version": "V3"}


class State:
    """The resource contents of one arm at update number k (k = 0 is the initial state)."""

    def __init__(self, base_routes, size, origin_port, xdir):
        check_size(size)
        self.base_routes = base_routes
        self.n_routes = int(size["routes"])
        self.n_clusters = int(size["clusters"])
        self.n_eds = int(size.get("eds_endpoints", 0))
        self.origin_port = int(origin_port)
        self.paths = paths(xdir)
        # last value per mutable item
        self.route_v = {}
        self.cluster_v = {}
        self.origin_v = 0
        self.eds_out = None  # index of the endpoint currently left out

    def route_configuration(self):
        filler = []
        for i in range(self.n_routes):
            filler.append({"match": {"prefix": "/epl-f/%05d/" % i},
                           "route": {"cluster": filler_cluster(i % self.n_clusters)},
                           "response_headers_to_add": [{"header": {"key": "x-epl-v",
                                                                    "value": str(self.route_v.get(i, 0))}}]})
        return {"@type": RDS_TYPE, "name": ROUTE_NAME,
                "virtual_hosts": [{"name": "service", "domains": ["*"], "routes": list(self.base_routes) + filler}]}

    def clusters(self):
        out = [static_cluster("origin", self.origin_port, self.origin_v)]
        out += [static_cluster(filler_cluster(i), self.origin_port, self.cluster_v.get(i, 0))
                for i in range(self.n_clusters)]
        if self.n_eds:
            out.append({"@type": CDS_TYPE, "name": EDS_CLUSTER, "connect_timeout": "1s", "type": "EDS",
                        "lb_policy": "ROUND_ROBIN",
                        "eds_cluster_config": {"eds_config": config_source(self.paths["eds"])}})
        return out

    def load_assignment(self):
        eps = [{"endpoint": {"address": _socket("127.0.0.1", EDS_PORT_BASE + i)}}
               for i in range(self.n_eds) if i != self.eds_out]
        return {"@type": EDS_TYPE, "cluster_name": EDS_CLUSTER, "endpoints": [{"lb_endpoints": eps}]}

    def apply(self, kind, k):
        """Change the state for update k of this kind; returns the resource type to write."""
        t = kind_type(kind)
        if kind == "rds":
            self.route_v[k % self.n_routes] = k
        elif kind == "cds":
            self.cluster_v[k % self.n_clusters] = k
        elif kind == "cds_active":
            self.origin_v = k
        elif kind == "eds":
            if not self.n_eds:
                raise ValueError("an eds update needs xds.eds_endpoints")
            self.eds_out = k % self.n_eds
        return t

    def text(self, t, version):
        if t == "rds":
            res, tu = [self.route_configuration()], RDS_TYPE
        elif t == "cds":
            res, tu = self.clusters(), CDS_TYPE
        else:
            res, tu = [self.load_assignment()], EDS_TYPE
        return json.dumps({"version_info": str(version), "type_url": tu, "resources": res},
                          separators=(",", ":"), sort_keys=True)


def write_atomic(path, text):
    """Write next to the target under a dot name, then rename onto it: Envoy sees one
    IN_MOVED_TO for the target (the temporary file's events do not match the watched name)."""
    d, n = os.path.split(path)
    tmp = os.path.join(d, "." + n + ".tmp")
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def write_initial(state):
    """Version 0 of every file the arm reads (before Envoy starts, and before validation)."""
    for t, p in state.paths.items():
        if t == "eds" and not state.n_eds:
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        write_atomic(p, state.text(t, 0))


class Updater(threading.Thread):
    """Renames one update every 1 / rate_hz seconds at anchor + (j + 0.5) / rate_hz, j = 0, 1, ...
    (at most `count` when given). The content of update j is written to the temporary file
    before its time comes, so the rename is all that happens at the scheduled instant.
    `counter` is shared between the pre and the window updater of a leg (update numbers go on).
    Records (number, monotonic time, wall time) of every rename."""

    def __init__(self, state, kind, rate_hz, counter, anchor=None, count=None, clock=time.monotonic,
                 wall=time.time):
        super().__init__(daemon=True)
        self.state, self.kind, self.period = state, kind, 1.0 / float(rate_hz)
        self.counter = counter  # [next update number]
        self.anchor = anchor
        self.count = count
        self.clock, self.wall = clock, wall
        self.stop_evt = threading.Event()
        self.renames = []
        self.error = None

    def run(self):
        try:
            if self.anchor is None:
                self.anchor = self.clock()
            j = 0
            while not self.stop_evt.is_set() and (self.count is None or j < self.count):
                k = self.counter[0]
                t = self.state.apply(self.kind, k)
                path = self.state.paths[t]
                d, n = os.path.split(path)
                tmp = os.path.join(d, "." + n + ".tmp")
                with open(tmp, "w") as f:
                    f.write(self.state.text(t, k))
                due = self.anchor + (j + 0.5) * self.period
                while True:
                    left = due - self.clock()
                    if left <= 0 or self.stop_evt.wait(min(left, 0.05)):
                        break
                if self.stop_evt.is_set():
                    break
                os.replace(tmp, path)
                self.renames.append((k, self.clock(), self.wall()))
                self.counter[0] = k + 1
                j += 1
        except Exception as e:  # noqa: BLE001 - recorded, the leg fails closed on it
            self.error = "%s: %s" % (type(e).__name__, e)

    def stop(self, timeout=10.0):
        self.stop_evt.set()
        self.join(timeout)


def stat_names(kind_t):
    p = STATS[kind_t]
    return {"success": p + "update_success", "rejected": p + "update_rejected", "failure": p + "update_failure",
            "time": p + "update_time"}


def window_record(kind, q_start, q0, q1, pre, win, t0, t1, wall_t1, n_expected, eds=False):
    """The leg's xDS record and its checks (fail closed: any check false invalidates the leg).

    q_start: stats at the start of the pre phase; q0/q1: the snapshots that bracket the window;
    pre/win: the two updaters (win may be None for a reference arm, which then must show no
    update in the window); t0/t1: the perf window (monotonic); wall_t1: wall time at t1."""
    types = ["rds", "cds"] + (["eds"] if eds else [])
    rec = {"kind": kind, "expected_in_window": n_expected, "types": {}}
    checks = {}
    t_kind = kind_type(kind) if kind else None
    for t in types:
        sn = stat_names(t)
        d = {"success_window": q1.get(sn["success"], 0) - q0.get(sn["success"], 0),
             "success_pre": q0.get(sn["success"], 0) - q_start.get(sn["success"], 0),
             "rejected_total": q1.get(sn["rejected"], 0), "failure_total": q1.get(sn["failure"], 0),
             "update_time_ms": q1.get(sn["time"])}
        rec["types"][t] = d
        want = n_expected if t == t_kind else 0
        checks["%s_window_updates" % t] = d["success_window"] == want
        checks["%s_no_rejects" % t] = d["rejected_total"] == 0 and d["failure_total"] == 0
        if t == t_kind:
            checks["%s_pre_applied" % t] = d["success_pre"] == len(pre.renames if pre else [])
            checks["%s_last_update_in_window" % t] = (d["update_time_ms"] is not None
                                                     and d["update_time_ms"] <= wall_t1 * 1000.0 + 1)
    if win is not None:
        times = [x[1] for x in win.renames]
        rec["renames_in_window"] = sum(1 for x in times if t0 <= x <= t1)
        rec["first_rename_after_t0_s"] = round(times[0] - t0, 4) if times else None
        rec["last_rename_before_t1_s"] = round(t1 - times[-1], 4) if times else None
        checks["renames_in_window"] = rec["renames_in_window"] == n_expected == len(times)
        checks["updater_ok"] = win.error is None and (pre is None or pre.error is None)
    rec["pre_renames"] = len(pre.renames) if pre else 0
    rec["checks"] = checks
    rec["ok"] = all(checks.values())
    return rec
