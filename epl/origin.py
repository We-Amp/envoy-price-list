"""Origin server for proxied shapes.

mode "docker":   the harness starts its own nginx container (host network,
                 pinned with --cpuset-cpus), records the container ID docker
                 returned, and stops only that ID.
mode "external": something else serves the origin port; the harness only
                 checks it accepts connections (and records that it did not
                 start it).
"""

import http.client
import os
import re
import subprocess
import time

from . import envoy_config, sysprobe


def container_pid(cid):
    """Main PID of a container this run started (read once, at start; never in a window)."""
    r = subprocess.run(["docker", "inspect", "--format", "{{.State.Pid}}", cid],
                       capture_output=True, text=True, timeout=30)
    try:
        pid = int(r.stdout.strip())
    except ValueError:
        return None
    return pid if pid > 1 else None


def side_service(name, cid, cpus, log):
    """A SideService for a container, or None (recorded) when its cgroup cannot be read."""
    from .sideservice import SideService
    pid = container_pid(cid)
    if not pid:
        log("%s: no main PID from docker inspect; side-service gate will fail closed" % name)
        return None
    try:
        return SideService(name, pid, cpus)
    except (RuntimeError, OSError) as e:
        log("%s: cgroup not readable (%s); side-service gate will fail closed" % (name, e))
        return None


class Origin:
    def __init__(self, cfg, cpus, shapes, run_dir, log):
        self.cfg = cfg
        self.cpus = cpus
        self.shapes = shapes
        self.run_dir = run_dir
        self.log = log
        self.container_id = None
        self.side = None  # SideService once the harness's own container runs
        self.meta = {"mode": cfg.get("mode", "external"), "port": cfg["port"]}

    def start(self):
        mode = self.meta["mode"]
        port = int(self.cfg["port"])
        needs = any(s["kind"] == "proxied" for s in self.shapes) or bool(self.cfg.get("authz_port")) \
            or bool(self.cfg.get("authz_grpc_port")) or bool(self.cfg.get("prime_file"))
        if mode == "external" or not needs:
            if needs and not sysprobe.port_open("127.0.0.1", port):
                raise RuntimeError("external origin port %d not accepting connections" % port)
            return self.meta
        if mode != "docker":
            raise ValueError("origin mode must be docker or external")
        if sysprobe.port_open("127.0.0.1", port):
            raise RuntimeError("origin port %d already in use; refusing to start a second origin" % port)
        od = os.path.join(self.run_dir, "origin")
        www = os.path.join(od, "www")
        os.makedirs(www, exist_ok=True)
        files = envoy_config.origin_files(self.shapes)
        from .experiment import HARNESS_ROOT
        bodies = envoy_config.origin_bodies(self.shapes, HARNESS_ROOT)
        if self.cfg.get("prime_file"):
            # the stats row's priming requests (one per generated cluster) fetch this file
            files[envoy_config.STATS_PRIME_PATH.lstrip("/")] = 2
        for rel, size in files.items():
            p = os.path.join(www, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(bodies.get(rel, b"a" * size))
        if self.cfg.get("authz_grpc_port"):
            p = os.path.join(www, envoy_config.AUTHZ_GRPC_FILE)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(envoy_config.AUTHZ_GRPC_BODY)
        conf = envoy_config.nginx_conf(port, self.cfg.get("workers", 8), self.cfg.get("authz_port"),
                                       self.cfg.get("authz_grpc_port"),
                                       self.cfg.get("keepalive_timeout_s", 600),
                                       self.cfg.get("keepalive_requests", 10000000),
                                       envoy_config.content_types(self.shapes),
                                       self.cfg.get("worker_connections", 8192), self.cfg.get("worker_rlimit_nofile"),
                                       bool(self.cfg.get("stub_status")))
        with open(os.path.join(od, "nginx.conf"), "w") as f:
            f.write(conf)
        image = self.cfg.get("image", "nginx:alpine")
        name = "%s-%d" % (self.cfg.get("name_prefix", "epl-origin"), os.getpid())
        args = ["docker", "run", "-d", "--rm", "--name", name, "--network", "host",
                "--cpuset-cpus", self.cpus] + (["--platform", self.cfg["platform"]] if self.cfg.get("platform") else []) + [
                "-v", "%s:/etc/nginx/nginx.conf:ro" % os.path.join(od, "nginx.conf"),
                "-v", "%s:/www:ro" % www, image]
        r = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError("docker run failed: %s" % r.stderr.strip()[:300])
        self.container_id = r.stdout.strip()
        self.log("origin container %s (%s) started" % (self.container_id[:12], name))
        for p in [port] + [int(self.cfg[k]) for k in ("authz_port", "authz_grpc_port") if self.cfg.get(k)]:
            if not sysprobe.wait_port("127.0.0.1", p, 30):
                self.stop()
                raise RuntimeError("origin did not open port %d" % p)
        img = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}} {{index .RepoDigests 0}}", image],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        self.side = side_service("origin", self.container_id, self.cpus, self.log)
        self.meta.update(image=image, image_id=img, container_name=name, workers=self.cfg.get("workers", 8),
                         authz_port=self.cfg.get("authz_port"), authz_grpc_port=self.cfg.get("authz_grpc_port"),
                         nginx_conf_sha256=sysprobe.text_sha256(conf),
                         files={k: v for k, v in files.items()})
        if bodies:
            import hashlib
            self.meta["body_sha256"] = {k: hashlib.sha256(v).hexdigest() for k, v in bodies.items()}
        time.sleep(0.5)
        return self.meta

    def stop(self):
        if self.container_id:
            subprocess.run(["docker", "stop", "-t", "5", self.container_id],
                           capture_output=True, text=True, timeout=60)
            self.log("origin container %s stopped" % self.container_id[:12])
            self.container_id = None


COLLECTOR_CONF = """receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 127.0.0.1:%d
%sexporters:
  nop:
service:
  telemetry:
    metrics:
%s  pipelines:
    traces:
      receivers: [otlp]
      exporters: [nop]
%s"""
METRICS_PIPELINE = """    metrics:
      receivers: [otlp]
      exporters: [nop]
"""


# Internal telemetry. "none" is what the first tracing row ran with. "basic" turns on the
# receiver's accepted/refused span counters, served for Prometheus on a fixed loopback
# port that the harness probes like every other port (a change against that row,
# recorded in the collector metadata).
TELEMETRY_NONE = "      level: none\n"
TELEMETRY_BASIC = ("      level: basic\n"
                   "      readers:\n"
                   "        - pull:\n"
                   "            exporter:\n"
                   "              prometheus:\n"
                   "                host: 127.0.0.1\n"
                   "                port: %d\n")


def collector_conf(port, metrics_port=None, metrics=False, max_recv_msg_size_mib=None):
    """metrics: also a metrics pipeline (OTLP receiver, nop exporter) for the stats sink.
    max_recv_msg_size_mib: the gRPC receiver's message limit (the collector's default is 4 MiB;
    an OTLP stats export of 10,000 histogram points is about 4.5 MB and is refused below the
    receiver, visible only as a stream reset on Envoy's side)."""
    tel = TELEMETRY_BASIC % int(metrics_port) if metrics_port else TELEMETRY_NONE
    lim = "        max_recv_msg_size_mib: %d\n" % int(max_recv_msg_size_mib) if max_recv_msg_size_mib else ""
    return COLLECTOR_CONF % (int(port), lim, tel, METRICS_PIPELINE if metrics else "")


SPANS_RE = re.compile(r"^otelcol_receiver_(accepted|refused)_(spans|metric_points)(?:_total)?(?:\{[^}]*\})?"
                      r"\s+([0-9.eE+-]+)\s*$", re.M)


def parse_collector_metrics(text):
    """{"accepted_spans": n, "refused_spans": n} summed over every receiver label set,
    from the collector's Prometheus text; a counter not exported yet is left out."""
    out = {}
    for kind, what, v in SPANS_RE.findall(text or ""):
        out[kind + "_" + what] = out.get(kind + "_" + what, 0.0) + float(v)
    return {k: int(round(v)) for k, v in out.items()}


LOG_ERROR_RE = re.compile(r"\t(error|ERROR|fatal|panic)\t|\b(level=error|\"level\":\"error\")")


def log_summary(text):
    """{lines, error_lines, first_error} of a collector log (console or JSON encoding)."""
    lines = [x for x in (text or "").splitlines() if x.strip()]
    errs = [x for x in lines if LOG_ERROR_RE.search(x)]
    return {"lines": len(lines), "error_lines": len(errs), "first_error": errs[0][:300] if errs else None}


class Collector:
    """Local null OpenTelemetry collector: OTLP/gRPC receiver, `nop` exporter (spans are
    received, decoded and dropped). Own container, host network, pinned; only the
    container ID `docker run` returned is ever stopped. With `metrics_port` set its
    internal telemetry runs at level basic on that loopback port, and `scrape()` reads
    the receiver's accepted and refused span counters (plain HTTP from Python)."""

    def __init__(self, cfg, cpus, run_dir, log):
        self.cfg = cfg
        self.cpus = cpus
        self.run_dir = run_dir
        self.log = log
        self.container_id = None
        self.side = None
        self.metrics_port = int(cfg["metrics_port"]) if cfg.get("metrics_port") else None
        self.meta = {"port": int(cfg["port"]), "image": cfg["image"],
                     "telemetry_level": "basic" if self.metrics_port else "none",
                     "metrics_port": self.metrics_port}

    def scrape(self):
        """Cumulative receiver span counters, or {"error": ...}."""
        if not self.metrics_port:
            return {"error": "collector telemetry off (no metrics_port)"}
        try:
            c = http.client.HTTPConnection("127.0.0.1", self.metrics_port, timeout=5.0)
            try:
                c.request("GET", "/metrics")
                r = c.getresponse()
                body = r.read().decode(errors="replace")
            finally:
                c.close()
        except (OSError, http.client.HTTPException, ValueError) as e:
            return {"error": "scrape failed: %s: %s" % (type(e).__name__, e)}
        if r.status != 200:
            return {"error": "scrape returned %d" % r.status}
        return parse_collector_metrics(body)

    def start(self):
        port = int(self.cfg["port"])
        for p in [port] + ([self.metrics_port] if self.metrics_port else []):
            if sysprobe.port_open("127.0.0.1", p):
                raise RuntimeError("collector port %d already in use" % p)
        d = os.path.join(self.run_dir, "collector")
        os.makedirs(d, exist_ok=True)
        conf = collector_conf(port, self.metrics_port, bool(self.cfg.get("metrics")),
                              self.cfg.get("max_recv_msg_size_mib"))
        with open(os.path.join(d, "config.yaml"), "w") as f:
            f.write(conf)
        name = "epl-collector-%d" % os.getpid()
        args = ["docker", "run", "-d", "--rm", "--name", name, "--network", "host", "--cpuset-cpus", self.cpus] + (
            ["--platform", self.cfg["platform"]] if self.cfg.get("platform") else []) + [
                "-v", "%s:/etc/epl-collector.yaml:ro" % os.path.join(d, "config.yaml"),
                self.cfg["image"], "--config", "/etc/epl-collector.yaml"]
        r = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError("docker run (collector) failed: %s" % r.stderr.strip()[:300])
        self.container_id = r.stdout.strip()
        self.log("collector container %s (%s) started" % (self.container_id[:12], name))
        for p in [port] + ([self.metrics_port] if self.metrics_port else []):
            if not sysprobe.wait_port("127.0.0.1", p, 30):
                self.stop()
                raise RuntimeError("collector did not open port %d" % p)
        img = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}} {{index .RepoDigests 0}}",
                              self.cfg["image"]], capture_output=True, text=True, timeout=30).stdout.strip()
        self.side = side_service("collector", self.container_id, self.cpus, self.log)
        self.meta.update(image_id=img, container_name=name, config_sha256=sysprobe.text_sha256(conf),
                         exporter="nop", max_recv_msg_size_mib=self.cfg.get("max_recv_msg_size_mib"))
        return self.meta

    def save_log_since(self, since_epoch_s, path):
        """The container's log since a wall time, written to path; {lines, error_lines, first_error}."""
        if not self.container_id:
            return {"error": "collector not running"}
        since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(since_epoch_s - 1)) + "Z"
        r = subprocess.run(["docker", "logs", "--since", since, self.container_id], capture_output=True, text=True,
                           timeout=60)
        text = (r.stdout or "") + (r.stderr or "")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        return log_summary(text) if r.returncode == 0 else {"error": "docker logs exited %d" % r.returncode}

    def stop(self):
        if self.container_id:
            subprocess.run(["docker", "stop", "-t", "5", self.container_id],
                           capture_output=True, text=True, timeout=60)
            self.log("collector container %s stopped" % self.container_id[:12])
            self.container_id = None


def make_certs(cert_dir, kinds, log):
    """Self-signed test certificates, one per kind, made with openssl in the run
    directory. Returns {kind: {crt_sha256, key_type}} for the metadata; key files
    stay in the run directory and are never printed."""
    os.makedirs(cert_dir, mode=0o700, exist_ok=True)
    out = {}
    for kind in kinds:
        crt, key = os.path.join(cert_dir, kind + ".crt"), os.path.join(cert_dir, kind + ".key")
        for args in (["openssl", "genpkey", "-out", key] + envoy_config.CERT_KINDS[kind],
                     ["openssl", "req", "-x509", "-new", "-key", key, "-days", "30", "-subj", "/CN=bench.local",
                      "-sha256", "-out", crt]):
            r = subprocess.run(args, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                raise RuntimeError("openssl failed for %s: %s" % (kind, r.stderr.strip()[-300:]))
        os.chmod(key, 0o600)
        out[kind] = {"crt_sha256": sysprobe.file_hashes(crt)["sha256"], "args": envoy_config.CERT_KINDS[kind]}
        log("certificate %s made" % kind)
    v = subprocess.run(["openssl", "version"], capture_output=True, text=True, timeout=30).stdout.strip()
    return {"openssl": v, "certs": out}
