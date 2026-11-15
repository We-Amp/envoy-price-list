"""Origin server for proxied shapes.

mode "docker":   the harness starts its own nginx container (host network,
                 pinned with --cpuset-cpus), records the container ID docker
                 returned, and stops only that ID.
mode "external": something else serves the origin port; the harness only
                 checks it accepts connections (and records that it did not
                 start it).
"""

import os
import subprocess
import time

from . import envoy_config, sysprobe


class Origin:
    def __init__(self, cfg, cpus, shapes, run_dir, log):
        self.cfg = cfg
        self.cpus = cpus
        self.shapes = shapes
        self.run_dir = run_dir
        self.log = log
        self.container_id = None
        self.meta = {"mode": cfg.get("mode", "external"), "port": cfg["port"]}

    def start(self):
        mode = self.meta["mode"]
        port = int(self.cfg["port"])
        needs = any(s["kind"] == "proxied" for s in self.shapes) or bool(self.cfg.get("authz_port")) \
            or bool(self.cfg.get("authz_grpc_port"))
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
        for rel, size in files.items():
            p = os.path.join(www, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(b"a" * size)
        if self.cfg.get("authz_grpc_port"):
            p = os.path.join(www, envoy_config.AUTHZ_GRPC_FILE)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(envoy_config.AUTHZ_GRPC_BODY)
        conf = envoy_config.nginx_conf(port, self.cfg.get("workers", 8), self.cfg.get("authz_port"),
                                       self.cfg.get("authz_grpc_port"),
                                       self.cfg.get("keepalive_timeout_s", 600),
                                       self.cfg.get("keepalive_requests", 10000000))
        with open(os.path.join(od, "nginx.conf"), "w") as f:
            f.write(conf)
        image = self.cfg.get("image", "nginx:alpine")
        name = "%s-%d" % (self.cfg.get("name_prefix", "epl-origin"), os.getpid())
        args = ["docker", "run", "-d", "--rm", "--name", name, "--network", "host",
                "--cpuset-cpus", self.cpus,
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
        self.meta.update(image=image, image_id=img, container_name=name, workers=self.cfg.get("workers", 8),
                         authz_port=self.cfg.get("authz_port"), authz_grpc_port=self.cfg.get("authz_grpc_port"),
                         nginx_conf_sha256=sysprobe.text_sha256(conf),
                         files={k: v for k, v in files.items()})
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
exporters:
  nop:
service:
  telemetry:
    metrics:
      level: none
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [nop]
"""


class Collector:
    """Local null OpenTelemetry collector: OTLP/gRPC receiver, `nop` exporter (spans are
    received, decoded and dropped). Own container, host network, pinned; only the
    container ID `docker run` returned is ever stopped."""

    def __init__(self, cfg, cpus, run_dir, log):
        self.cfg = cfg
        self.cpus = cpus
        self.run_dir = run_dir
        self.log = log
        self.container_id = None
        self.meta = {"port": int(cfg["port"]), "image": cfg["image"]}

    def start(self):
        port = int(self.cfg["port"])
        if sysprobe.port_open("127.0.0.1", port):
            raise RuntimeError("collector port %d already in use" % port)
        d = os.path.join(self.run_dir, "collector")
        os.makedirs(d, exist_ok=True)
        conf = COLLECTOR_CONF % port
        with open(os.path.join(d, "config.yaml"), "w") as f:
            f.write(conf)
        name = "epl-collector-%d" % os.getpid()
        args = ["docker", "run", "-d", "--rm", "--name", name, "--network", "host", "--cpuset-cpus", self.cpus,
                "-v", "%s:/etc/epl-collector.yaml:ro" % os.path.join(d, "config.yaml"),
                self.cfg["image"], "--config", "/etc/epl-collector.yaml"]
        r = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError("docker run (collector) failed: %s" % r.stderr.strip()[:300])
        self.container_id = r.stdout.strip()
        self.log("collector container %s (%s) started" % (self.container_id[:12], name))
        if not sysprobe.wait_port("127.0.0.1", port, 30):
            self.stop()
            raise RuntimeError("collector did not open port %d" % port)
        img = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}} {{index .RepoDigests 0}}",
                              self.cfg["image"]], capture_output=True, text=True, timeout=30).stdout.strip()
        self.meta.update(image_id=img, container_name=name, config_sha256=sysprobe.text_sha256(conf),
                         exporter="nop")
        return self.meta

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
