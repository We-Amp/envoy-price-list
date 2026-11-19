"""Experiment config, balanced schedule, adaptive run loop, paired analysis."""

import copy
import json
import os
import platform
import random
import re
import shutil
import subprocess
import time

from . import __version__, envoy_config, stats, sysprobe, validity

ALPHA = 0.05
# the harness directory: body files and Wasm modules in a config are relative to it
HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    # Rounds: at least `rounds`, then blocks of `rounds_block` until every primary
    # comparison's 95% interval half-width is at or under the stop target, at most
    # `rounds_max`. `adaptive: false` runs exactly `rounds`.
    "rounds": 12,
    "rounds_block": 6,
    "rounds_max": 36,
    "adaptive": True,
    "stop": {"target_half_width_pct": 3.0},
    # auto: abba for 2 arms, rotate for 3 or more. Each round pair (r, r+1) runs
    # one order forward and the other reversed; a seeded coin picks which comes
    # first, so a disturbance with a period of two legs cannot line up with an arm.
    "order": "auto",
    "order_seed": 1,
    # Comparisons: "base" (every arm against base_arm) or "all_pairs".
    "comparisons": "base",
    # One primary metric per comparison row; Holm across the primary rows. All
    # other metrics are exploratory: interval only, no multiplicity control.
    "primary_metric": "cycles_total",
    "min_pairs": 6,
    "rerun_invalid": 1,          # re-run a round (one shape, all arms) with an invalid leg, at most this often
    "abort_after_invalid": 6,    # consecutive invalid legs before the run gives up
    # A/A limits: the 95% half-width the self-test must reach. Set them from the
    # smallest effect the runs that rely on this A/A intend to claim: release and
    # setting rows claim cycle effects of about 1%, so an A/A with a 3% interval
    # could not have excluded a harness bias of the size being published.
    "aa": {"metrics": ["instructions_u", "cycles_total"],
           "max_half_width_pct": {"instructions_u": 0.5, "cycles_total": 1.0}},
    "envoy": {"workers": 4, "listener_port": 10110, "admin_port": 9921, "exact_balance": True,
              "log_level": "warn", "codec_type": "HTTP1"},
    "client": {"concurrency": 4, "connections_per_worker": 16, "warmup_s": 5, "duration_s": 25,
               "idle_strategy": "poll", "open_loop": True, "extra_args": []},
    "measure": {"lead_in_s": 2, "window_s": 20, "perf": ["perf"], "conn_probe": True},
    "validity": {"rate_tolerance": 0.01, "min_client_headroom": 0.25, "max_overflow": 0, "max_non2xx": 0},
    "idle": {"max_load1": 4.0, "max_busy_pct": 2.0, "max_cpu_busy_pct": 5.0, "sample_s": 1.0, "poll_s": 5,
             "timeout_s": 600,
             "procs": [r"(^|/)envoy[^/ ]*( |$)", r"(^|/)nighthawk_client( |$)", r"(^|/)h2load( |$)",
                       r"(^|/)wrk2?( |$)", r"(^|/)fortio( |$)"]},
    "origin": {"mode": "docker", "image": "nginx:alpine", "port": 8092, "workers": 8, "authz_port": None,
               "authz_grpc_port": None},
    # second Envoy of a two-hop arm (its CPUs are cpus.hop2); baseline config
    "hop2": {"listener_port": 10120, "admin_port": 9931},
    # null OpenTelemetry collector for tracing arms (image pinned by digest in the config)
    # metrics_port: the collector's internal telemetry at level basic on this loopback port
    # (receiver span counters, scraped before and after every leg); None = level none
    "collector": {"image": None, "port": 4317, "metrics_port": None},
    # UDP discard sink for statsd arms (the stats row): port, receive buffer asked for, CPUs
    "stats_sink": {"port": 8125, "rcvbuf": 268435456, "sample_every": 1000},
    "record_hostname": False,
    "alpha": ALPHA,
}

METRICS = [
    ("instructions_u", "instructions:u / req", lambda m: m["per_req"]["instructions_u"]),
    ("cycles_u", "cycles:u / req", lambda m: m["per_req"]["cycles_u"]),
    ("cycles_k", "cycles:k / req", lambda m: m["per_req"]["cycles_k"]),
    ("cycles_total", "cycles (u+k) / req", lambda m: m["per_req"]["cycles_total"]),
    # two-hop experiments only (absent elsewhere, so no comparison is made):
    # every hop together, and that divided by the number of hops
    ("cycles_total_all", "cycles (u+k) / req, all hops", lambda m: m["per_req"]["cycles_total_all"]),
    ("cycles_total_per_hop", "cycles (u+k) / req / hop", lambda m: m["per_req"]["cycles_total_per_hop"]),
    ("instructions_u_all", "instructions:u / req, all hops", lambda m: m["per_req"]["instructions_u_all"]),
    ("cycles_total_hop2", "cycles (u+k) / req, second hop", lambda m: m["per_req"]["cycles_total_hop2"]),
    ("hop2_worker_max_share", "second hop: busiest worker's share", lambda m: m["hop2_workers"]["worker_max_share"]),
    ("hop2_worker_max_busy", "second hop: busiest worker busy (of a core)",
     lambda m: m["hop2_workers"]["worker_max_busy"]),
    ("hop2_conns_used", "first hop -> second hop: connections carrying traffic",
     lambda m: m["conn_hop2_downstream"]["conns_over_1pct_of_mean"]),
    # idle legs of the stats row (absent elsewhere, so no comparison is made): the main
    # thread's run time per second and per flush period, its cycles per second (perf -t)
    ("main_ms_per_s", "main thread ms / s", lambda m: m["main"]["run_ms_per_s"]),
    ("main_ms_per_period", "main thread ms / flush period", lambda m: m["main"]["run_ms_per_period"]),
    ("main_cycles_per_s", "main thread cycles / s", lambda m: m["main_perf"]["cycles_per_s"]),
    ("main_cycles_per_period", "main thread cycles / flush period", lambda m: m["main_perf"]["cycles_per_period"]),
    ("workers_cycles_per_req", "worker threads cycles / req", lambda m: m["workers_cycles_per_req"]),
    ("p50_us", "p50 latency (us)", lambda m: m["latency_us"]["p50"]),
    ("p99_us", "p99 latency (us)", lambda m: m["latency_us"]["p99"]),
]
METRIC_KEYS = [k for k, _, _ in METRICS]
LATENCY_KEYS = ("p50_us", "p99_us")


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _expand(p):
    """~ expansion; a bare program name (no slash) is looked up on PATH."""
    if not isinstance(p, str):
        return p
    p = os.path.expanduser(os.path.expandvars(p))
    if "/" not in p:
        found = shutil.which(p)
        if found:
            return found
    return p


def parse_sets(items):
    """["a.b=1", "c=x"] -> nested override dict; values are JSON when they parse."""
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError("--set wants key=value, got %r" % it)
        k, v = it.split("=", 1)
        try:
            val = json.loads(v)
        except ValueError:
            val = v
        cur = out
        parts = k.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = val
    return out


def load(path, overrides=None):
    with open(path) as f:
        raw = json.load(f)
    exp = _merge(DEFAULTS, raw)
    exp = _merge(exp, overrides or {})
    exp["_config_text"] = json.dumps(_merge(raw, overrides or {}), sort_keys=True)
    arch = box_arch(exp)
    for a in exp["arms"]:
        if a.get("binaries"):
            # per-architecture entries: the box's (or this machine's) architecture picks one
            pick = a["binaries"].get(arch)
            if pick is None:
                raise ValueError("arm %s has no binary for architecture %s" % (a.get("name"), arch))
            a.update(pick)
        a["binary"] = _expand(a["binary"])
    exp["client"]["binary"] = _expand(exp["client"]["binary"])
    if isinstance(exp["measure"]["perf"], str):
        exp["measure"]["perf"] = exp["measure"]["perf"].split()
    exp["measure"]["perf"] = [_expand(x) for x in exp["measure"]["perf"]]
    exp["workdir"] = _expand(exp.get("workdir", "~/epl/runs"))
    if exp.get("floor_from"):
        exp["floor_from"] = _expand(exp["floor_from"])
    return exp


def arm_settings(arm):
    return dict(arm.get("settings") or {})


def arm_envoy(exp, arm, run_dir=""):
    """The experiment's envoy section with the arm's settings merged in, plus the
    ports and paths the harness owns (access-log file, collector, authz service,
    second hop)."""
    e = _merge(exp["envoy"], arm_settings(arm))
    if e.get("access_log"):
        e["access_log"] = dict(e["access_log"], path=os.path.join(run_dir, "alog", arm["name"] + ".alog"))
    if e.get("tracing") or (e.get("stats_sink") or {}).get("kind") == "otlp":
        e["collector_port"] = exp["collector"]["port"]
    if (e.get("stats_sink") or {}).get("kind") in ("statsd", "dog_statsd"):
        e["stats_sink_port"] = exp["stats_sink"]["port"]
    if e.get("ext_authz") == "grpc":
        e["authz_grpc_port"] = exp["origin"]["authz_grpc_port"]
    elif e.get("ext_authz"):
        e["authz_port"] = exp["origin"]["authz_port"]
    if e.get("two_hop"):
        e["upstream_port"] = exp["hop2"]["listener_port"]
    if e.get("wasm") and e["wasm"].get("file"):
        e["wasm"] = dict(e["wasm"], file=os.path.join(HARNESS_ROOT, e["wasm"]["file"]))
    return e


def wasm_files(exp):
    """{arm: (absolute path, expected sha256)} of the arms that load a Wasm module."""
    out = {}
    for a in exp["arms"]:
        w = arm_envoy(exp, a).get("wasm")
        if w:
            out[a["name"]] = (w["file"], w.get("sha256"))
    return out


def check_wasm(exp):
    """[error] for every Wasm module whose file is missing or differs from its sha256."""
    errs = []
    for arm, (path, want) in wasm_files(exp).items():
        try:
            got = sysprobe.file_hashes(path)["sha256"]
        except OSError as e:
            errs.append("arm %s: wasm module %s unreadable (%s)" % (arm, path, e))
            continue
        if got != want:
            errs.append("arm %s: wasm module sha256 %s != %s" % (arm, got, want))
    return errs


def hop2_envoy(exp, arm=None):
    """The second hop: the experiment's baseline envoy section on the hop2 ports, plus
    the arm's `hop2_settings` (none by default)."""
    over = dict((arm_settings(arm).get("hop2_settings") or {}) if arm else {})
    for k in ("two_hop", "hop2_settings"):
        if k in over:
            raise ValueError("hop2_settings cannot contain %s" % k)
    # the second hop always listens on loopback (the first hop's upstream is 127.0.0.1)
    over.update(listener_port=exp["hop2"]["listener_port"], admin_port=exp["hop2"]["admin_port"],
                listener_address="127.0.0.1")
    return _merge(exp["envoy"], over)


def hop2_key(arm):
    return "_hop2:" + arm["name"]


def small_clusters(aenv, n=2):
    """The arm's envoy section with the generated cluster count capped at n: the same structure,
    for checks that do not need every cluster (validation, portability)."""
    sc = aenv.get("stats_clusters")
    if sc and int(sc.get("count", 0)) > n:
        aenv = dict(aenv, stats_clusters=dict(sc, count=n))
    return aenv


def needs_collector(exp):
    """Tracing arms and OTLP stats-sink arms send to the local null collector."""
    return uses(exp, "tracing") or any((arm_envoy(exp, a).get("stats_sink") or {}).get("kind") == "otlp"
                                       for a in exp["arms"])


def uses(exp, setting):
    return any(arm_settings(a).get(setting) for a in exp["arms"]) or bool(exp["envoy"].get(setting))


def prepare_bootstraps(exp, run_dir, log=lambda m: None, make_certs=True):
    """Write one bootstrap per arm (and one for the second hop when an arm uses
    it); make the test certificates when an arm uses TLS. Returns
    ({arm name: path, "_hop2:<arm>": path}, {arm name: bootstrap text}, cert metadata)."""
    certs = None
    cert_dir = os.path.join(run_dir, "certs")
    if uses(exp, "tls"):
        kinds = sorted({(arm_envoy(exp, a).get("tls") or {}).get("cert", "rsa2048")
                        for a in exp["arms"] if arm_envoy(exp, a).get("tls")})
        if make_certs:
            from .origin import make_certs as mk
            certs = mk(cert_dir, kinds, log)
        else:
            certs = {"certs": {k: {"crt_sha256": "dry-run"} for k in kinds}}
    if uses(exp, "access_log"):
        os.makedirs(os.path.join(run_dir, "alog"), exist_ok=True)
    paths, texts = {}, {}
    plain = not any(arm_settings(a) for a in exp["arms"])
    for a in exp["arms"]:
        t = envoy_config.bootstrap_text(exp["shapes"], arm_envoy(exp, a, run_dir), exp["origin"]["port"], cert_dir)
        p = os.path.join(run_dir, "envoy-bootstrap.json" if plain else "envoy-bootstrap-%s.json" % a["name"])
        with open(p, "w") as f:
            f.write(t)
        paths[a["name"]], texts[a["name"]] = p, t
    # one second-hop bootstrap per two-hop arm (they differ only when hop2_settings differ)
    for a in exp["arms"]:
        if not arm_settings(a).get("two_hop"):
            continue
        t = envoy_config.bootstrap_text(exp["shapes"], hop2_envoy(exp, a), exp["origin"]["port"], cert_dir)
        p = os.path.join(run_dir, "envoy-bootstrap-hop2-%s.json" % a["name"])
        with open(p, "w") as f:
            f.write(t)
        paths[hop2_key(a)], texts[hop2_key(a)] = p, t
    return paths, texts, certs


def effective_order(exp):
    if exp["order"] == "auto":
        return "abba" if len(exp["arms"]) <= 2 else "rotate"
    return exp["order"]


def cell_mode(exp):
    """An arm may list the shapes it runs on (`shapes: [...]`): the experiment is then a set of
    (shape, arm) cells, and the order rotates over the cells."""
    return any(a.get("shapes") is not None for a in exp.get("arms", []))


def cells(exp):
    """[(shape, arm)] that have legs, shapes first: every pair, or with `shapes` on an arm only
    the pairs it lists."""
    return [(sh, a) for sh in exp["shapes"] for a in exp["arms"]
            if a.get("shapes") is None or sh["name"] in a["shapes"]]


def order_period(exp):
    """Rounds after which every arm has been in every position equally often."""
    o = effective_order(exp)
    if cell_mode(exp):
        return len(cells(exp))
    return 2 if o == "abba" else len(exp["arms"]) if o == "latin" else 2 * len(exp["arms"])


def validate(exp, allow_short=False, check_rounds=True):
    errs = []
    if not exp.get("name") or not re.match(r"^[A-Za-z0-9._-]+$", exp["name"]):
        errs.append("name must be [A-Za-z0-9._-]+")
    arms = exp.get("arms", [])
    names = [a.get("name") for a in arms]
    if len(arms) < 2:
        errs.append("need at least 2 arms")
    if len(set(names)) != len(names):
        errs.append("arm names must be unique")
    for n in names:
        if not n or not re.match(r"^[A-Za-z0-9._-]+$", n):
            errs.append("arm name %r must be [A-Za-z0-9._-]+" % n)
    if exp.get("base_arm", names[0] if names else None) not in names:
        errs.append("base_arm not among arms")
    if exp["order"] not in ("auto", "abba", "rotate", "latin"):
        errs.append("order must be auto, abba, rotate or latin")
    elif exp["order"] == "abba" and len(arms) > 2:
        errs.append("abba with %d arms pins the middle arms to fixed positions; use rotate (or auto)" % len(arms))
    if exp["comparisons"] not in ("base", "all_pairs"):
        errs.append("comparisons must be base or all_pairs")
    if exp["primary_metric"] not in METRIC_KEYS:
        errs.append("primary_metric must be one of %s" % METRIC_KEYS)
    if exp.get("smoke"):
        check_rounds = False  # a smoke runs each arm once or twice; it carries no comparison
    snames_all = [s.get("name") for s in exp.get("shapes", [])]
    if cell_mode(exp):
        if exp["order"] != "latin":
            errs.append("arms with `shapes` (cells) need order latin (the rotation runs over the cells)")
        for a in arms:
            if a.get("shapes") is not None and (not isinstance(a["shapes"], list) or not a["shapes"]
                                                or any(x not in snames_all for x in a["shapes"])):
                errs.append("arm %s: shapes must be a non-empty list of shape names" % a.get("name"))
        for sh in exp.get("shapes", []):
            if not any(s2["name"] == sh["name"] for s2, _ in cells(exp)):
                errs.append("shape %s: no arm runs on it" % sh.get("name"))
    if check_rounds and len(arms) >= 2 and exp["order"] in ("auto", "abba", "rotate", "latin"):
        per = order_period(exp)
        rmin, rmax, blk = exp["rounds"], exp["rounds_max"], exp["rounds_block"]
        if rmin < 12 and not allow_short:
            errs.append("rounds must be >= 12 (method rule); use --allow-short only for smoke runs")
        for label, v in (("rounds", rmin), ("rounds_max", rmax), ("rounds_block", blk)):
            if effective_order(exp) != "latin" and (v < 2 or v % 2):
                # abba and rotate pair a forward with a reversed round; a Latin square does not
                errs.append("%s must be even (got %d)" % (label, v))
            elif v % per:
                errs.append("%s must be a multiple of %d (%s order, %d arms)" % (
                    label, per, effective_order(exp), len(arms)))
        if rmax < rmin:
            errs.append("rounds_max must be >= rounds")
        if rmax > 36 and not allow_short:
            errs.append("rounds_max is capped at 36")
    sets = {k: sysprobe.parse_cpuset(v) for k, v in exp["cpus"].items()}
    keys = sorted(sets)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ov = sets[keys[i]] & sets[keys[j]]
            if ov:
                errs.append("cpu sets %s and %s overlap on %s" % (keys[i], keys[j], sorted(ov)[:8]))
    for k in ("sut", "client"):
        if k not in sets:
            errs.append("cpus.%s missing" % k)
    if any(s["kind"] == "proxied" for s in exp.get("shapes", [])) and exp["origin"]["mode"] == "docker" \
            and "origin" not in sets:
        errs.append("cpus.origin missing for a docker origin")
    snames = [s.get("name") for s in exp.get("shapes", [])]
    if not snames or len(set(snames)) != len(snames):
        errs.append("shapes must be non-empty with unique names")
    for s in exp.get("shapes", []):
        if s.get("kind") not in ("proxied", "direct_headers", "routes", "idle"):
            errs.append("shape %s: kind must be proxied, direct_headers, routes or idle" % s.get("name"))
        if s.get("pre_window_settle_s") and s.get("kind") != "idle":
            li = s.get("lead_in_s", exp["measure"]["lead_in_s"])
            if li + float(s["pre_window_settle_s"]) + exp["measure"]["window_s"] + 1 > exp["client"]["duration_s"]:
                errs.append("shape %s: client duration must exceed lead_in + pre_window_settle + window + 1 s"
                            % s.get("name"))
        if s.get("kind") == "routes":
            rs = (s.get("route_table") or {}).get("routes")
            if not isinstance(rs, list) or not rs:
                errs.append("shape %s: route_table.routes must be a non-empty list" % s.get("name"))
            elif any("route" in r for r in rs if isinstance(r, dict)) and exp["origin"]["mode"] == "docker" \
                    and not any(x.get("kind") == "proxied" for x in exp.get("shapes", [])):
                errs.append("shape %s: a route table with upstream routes needs a proxied shape (the "
                            "origin starts only for those); use direct_response routes" % s.get("name"))
        if not str(s.get("path", "")).startswith("/"):
            errs.append("shape %s: path must start with /" % s.get("name"))
        if s.get("body_file"):
            if s.get("kind") != "proxied" or not s.get("body_sha256"):
                errs.append("shape %s: body_file needs a proxied shape and body_sha256" % s.get("name"))
            else:
                try:
                    envoy_config.origin_bodies([s], HARNESS_ROOT)
                except (OSError, ValueError) as e:
                    errs.append("shape %s: %s" % (s.get("name"), e))
        if s.get("warmup_s") is not None and not (isinstance(s["warmup_s"], (int, float)) and s["warmup_s"] >= 0):
            errs.append("shape %s: warmup_s must be a number >= 0" % s.get("name"))
        if int(s.get("rps", 0)) % int(exp["client"]["concurrency"]) != 0:
            errs.append("shape %s: rps must be divisible by client concurrency" % s.get("name"))
    for a in arms:
        st = arm_settings(a)
        bad = sorted(k for k in st if k not in envoy_config.SETTINGS and k not in ("codec_type",))
        if bad:
            errs.append("arm %s: unknown settings %s (known: %s)" % (a.get("name"), bad,
                                                                     sorted(envoy_config.SETTINGS)))
        tls = st.get("tls") or exp["envoy"].get("tls")
        if tls and tls.get("cert", "rsa2048") not in envoy_config.CERT_KINDS:
            errs.append("arm %s: tls.cert must be one of %s" % (a.get("name"), sorted(envoy_config.CERT_KINDS)))
        if bool(st.get("tls", exp["envoy"].get("tls"))) != bool(arms[0].get("settings", {}).get(
                "tls", exp["envoy"].get("tls"))):
            errs.append("arms must agree on TLS on or off (the client URL is per experiment)")
        if not isinstance(a.get("env", {}), dict):
            errs.append("arm %s: env must be an object" % a.get("name"))
        if not isinstance(a.get("hop2_env", {}), dict):
            errs.append("arm %s: hop2_env must be an object" % a.get("name"))
        if "hop2_env" in a and not arm_settings(a).get("two_hop"):
            errs.append("arm %s: hop2_env without two_hop" % a.get("name"))
    if uses(exp, "two_hop") and "hop2" not in sets:
        errs.append("a two_hop arm needs cpus.hop2")
    if needs_collector(exp) and not exp["collector"].get("image"):
        errs.append("a tracing arm needs collector.image")
    if needs_collector(exp) and "origin" not in sets:
        errs.append("a tracing arm needs cpus.origin (the collector runs there)")
    for a in arms:
        az = arm_settings(a).get("ext_authz")
        if az == "grpc" and not exp["origin"].get("authz_grpc_port"):
            errs.append("arm %s: a gRPC ext_authz arm needs origin.authz_grpc_port" % a.get("name"))
        elif az and az != "grpc" and not exp["origin"].get("authz_port"):
            errs.append("arm %s: an HTTP ext_authz arm needs origin.authz_port" % a.get("name"))
        try:
            envoy_config.bootstrap(exp.get("shapes", []), small_clusters(arm_envoy(exp, a, "/r")),
                                   exp["origin"]["port"], "/r/c")
        except (ValueError, KeyError, TypeError) as e:
            errs.append("arm %s: %s" % (a.get("name"), e))
        h2s = arm_settings(a).get("hop2_settings")
        if h2s is not None:
            if not arm_settings(a).get("two_hop"):
                errs.append("arm %s: hop2_settings without two_hop" % a.get("name"))
            bad = sorted(k for k in h2s if k not in envoy_config.SETTINGS or k in ("two_hop", "hop2_settings"))
            if bad:
                errs.append("arm %s: hop2_settings cannot contain %s" % (a.get("name"), bad))
        if not isinstance(a.get("validity", {}), dict):
            errs.append("arm %s: validity must be an object" % a.get("name"))
    if exp.get("primary_metric") in ("cycles_total_all", "cycles_total_per_hop") and not uses(exp, "two_hop"):
        errs.append("primary metric %s needs a two_hop arm" % exp["primary_metric"])
    m = exp["measure"]
    for li in [m["lead_in_s"]] + [sh["lead_in_s"] for sh in exp["shapes"] if sh.get("lead_in_s") is not None]:
        if li + m["window_s"] + 1 > exp["client"]["duration_s"]:
            errs.append("client duration must exceed lead_in + window + 1 s")
    names = [a.get("name") for a in arms]
    for p in exp.get("confirmatory") or []:
        ok = isinstance(p, (list, tuple)) and len(p) in (2, 3) and p[0] in names and p[1] in names and p[0] != p[1]
        if ok and len(p) == 3:
            sh = [p[2]] if isinstance(p[2], str) else p[2]
            ok = isinstance(sh, list) and bool(sh) and all(x in snames for x in sh)
        if not ok:
            errs.append("confirmatory rows are [arm, reference] or [arm, reference, shape(s)] with two different "
                        "arms and known shapes, got %r" % (p,))
    for s in exp.get("shapes", []):
        t = s.get("stop_target_half_width_pct")
        if t is not None and not (isinstance(t, (int, float)) and t > 0):
            errs.append("shape %s: stop_target_half_width_pct must be a positive number" % s.get("name"))
    if exp.get("audit") == "mt-s":
        for a in arms:
            try:
                b = envoy_config.bootstrap(exp.get("shapes", []), small_clusters(arm_envoy(exp, a, "/r")),
                                           exp["origin"]["port"], "/r/c")
                errs += ["arm %s: audit: %s" % (a.get("name"), p) for p in envoy_config.audit_mt_s(b)]
            except (ValueError, KeyError, TypeError) as e:
                errs.append("arm %s: audit: %s" % (a.get("name"), e))
    if exp["measure"].get("responses_from") == "origin" and not exp["origin"].get("stub_status"):
        errs.append("measure.responses_from origin needs origin.stub_status")
    for s in exp.get("shapes", []):
        if s.get("main_cpu") is not None:
            ws = sysprobe.parse_cpuset(s.get("worker_cpus", ""))
            # main_shares_worker: this shape alone puts the main thread on a worker's CPU
            inside = int(s["main_cpu"]) in ws and not s.get("main_shares_worker")
            if not ws or inside or len(ws) != int(s.get("workers", 0)):
                errs.append("shape %s: a rung needs workers = the size of worker_cpus and a main_cpu outside it"
                            % s.get("name"))
            if s.get("main_shares_worker") and int(s["main_cpu"]) not in ws:
                errs.append("shape %s: main_shares_worker needs a main_cpu inside worker_cpus" % s.get("name"))
            if s.get("worker_pin") not in (None, "one_to_one"):
                errs.append("shape %s: worker_pin must be one_to_one when set" % s.get("name"))
            if not (ws | {int(s["main_cpu"])}) <= sysprobe.parse_cpuset(exp["cpus"]["sut"]):
                errs.append("shape %s: rung CPUs must lie inside cpus.sut" % s.get("name"))
    if exp.get("shape_order", "fixed") not in ("fixed", "latin"):
        errs.append("shape_order must be fixed or latin")
    lt = exp["measure"].get("latency")
    if lt is not None:
        for k in ("sampler", "probe"):
            if len(sets.get(k, ())) != 1:
                errs.append("measure.latency needs cpus.%s, one CPU" % k)
        need = ("data_conns", "data_hz", "data_stagger_ms", "admin_period_ms", "control_conns", "control_hz",
                "per_worker", "map_requests", "map_margin", "map_max_opens", "gap_ms", "drain_s", "sample_s", "cpu0")
        miss = [k for k in need if k not in lt]
        if miss:
            errs.append("measure.latency lacks %s" % miss)
        if not exp["measure"].get("main_sampler"):
            errs.append("measure.latency needs measure.main_sampler")
        if any(s.get("kind") != "proxied" or s.get("main_cpu") is None or s.get("worker_pin") != "one_to_one"
               for s in exp.get("shapes", [])):
            errs.append("measure.latency needs proxied shapes that are rungs with worker_pin one_to_one")
        if not all(arm_settings(a).get("stats_clusters") for a in arms):
            errs.append("measure.latency needs stats_clusters on every arm (the reads around the client)")
    if exp.get("evidence_mode", "gate") not in ("gate", "record"):
        errs.append("evidence_mode must be gate or record")
    from . import evidence as _ev
    for a in arms:
        if "evidence" in a:
            # a smoke (evidence recorded) may leave out the arm a ref points at
            ref_names = names if exp.get("evidence_mode", "gate") == "gate" else ()
            errs += ["arm %s: %s" % (a.get("name"), x) for x in _ev.validate_items(a["evidence"], ref_names)]
    if exp.get("stop", {}).get("rows") == "confirmatory" and not exp.get("confirmatory"):
        errs.append("stop.rows = confirmatory needs confirmatory rows")
    groups = m.get("perf_event_groups")
    lists = ([m["perf_events"]] if m.get("perf_events") else []) + (groups or [])
    if groups is not None and (not isinstance(groups, list) or not groups):
        errs.append("measure.perf_event_groups must be a non-empty list of event lists")
    for ev in lists:
        names = set(ev.split(",")) if isinstance(ev, str) else set()
        if "instructions:u" not in names or not ({"cycles:u", "cycles:k"} <= names or "cycles" in names):
            errs.append("perf event list %r needs instructions:u and cycles (or cycles:u and cycles:k)" % (ev,))
    if lists and uses(exp, "two_hop"):
        errs.append("measure.perf_events / perf_event_groups are for one-hop experiments only")
    b = m.get("burst")
    if b:
        if not uses(exp, "two_hop"):
            errs.append("measure.burst needs a two_hop arm (it pauses the second hop)")
        if not 0 < float(b.get("at_s", -1)) < m["window_s"]:
            errs.append("measure.burst.at_s must lie inside the perf window")
        if "pause_hop2_ms" in b and not 0 < float(b["pause_hop2_ms"]) <= 1000:
            errs.append("measure.burst.pause_hop2_ms must be in (0, 1000]")
        if not 0.1 <= float(b.get("sample_s", 1.0)) <= 10:
            errs.append("measure.burst.sample_s must be in [0.1, 10]")
    return errs


def _coin(seed, pair):
    return random.Random("epl-order:%s:%d" % (seed, pair)).random() < 0.5


def round_order(exp, r):
    """Arm order of round r (1-based).

    abba:   A B / B A per round pair.
    rotate: round pair p starts at arm p mod k, so over 2k rounds every arm is
            in every position exactly twice (once in each direction).
    In every pair one round runs forward and the other reversed; a seeded coin
    per pair decides which one comes first.
    """
    arms = exp["arms"]
    k = len(arms)
    pair = (r - 1) // 2
    if effective_order(exp) == "latin":
        # one Latin square: round r starts at arm r-1 (mod k); k rounds put every arm in every
        # position once (a seeded rotation offset, no reversed rounds)
        off = random.Random("epl-latin:%s" % exp.get("order_seed", 1)).randrange(k)
        s = (r - 1 + off) % k
        return arms[s:] + arms[:s]
    if effective_order(exp) == "abba":
        fwd = list(arms)
    else:
        s = pair % k
        fwd = arms[s:] + arms[:s]
    first = (r % 2 == 1)
    flip = _coin(exp.get("order_seed", 1), pair) if exp.get("order_seed") is not None else False
    forward = first != flip
    return fwd if forward else list(reversed(fwd))


def shape_order(exp, r):
    """Shapes of round r: as configured, or (shape_order latin) rotated by round from a seeded
    offset, so a drift over the session is not aliased onto one shape (a rung)."""
    sh = exp["shapes"]
    if exp.get("shape_order") != "latin" or len(sh) < 2:
        return list(sh)
    off = random.Random("epl-shapes:%s" % exp.get("order_seed", 1)).randrange(len(sh))
    s = (r - 1 + off) % len(sh)
    return sh[s:] + sh[:s]


def cell_order(exp, r):
    """Cells of round r (1-based): one Latin square over the cells, round r starts at cell r-1
    (mod the number of cells) from a seeded offset, so every cell is in every position once
    per len(cells) rounds."""
    cs = cells(exp)
    off = random.Random("epl-latin:%s" % exp.get("order_seed", 1)).randrange(len(cs))
    s = (r - 1 + off) % len(cs)
    return cs[s:] + cs[:s]


def schedule(exp, first=1, last=None):
    """[(round, shape, arm)] for rounds first..last (default: the minimum rounds)."""
    last = exp["rounds"] if last is None else last
    out = []
    if cell_mode(exp):
        for r in range(first, last + 1):
            out += [(r, sh, a) for sh, a in cell_order(exp, r)]
        return out
    for r in range(first, last + 1):
        order = round_order(exp, r)
        for sh in shape_order(exp, r):
            for a in order:
                out.append((r, sh, a))
    return out


def leg_id(r, shape, arm, attempt=0):
    return "r%02d-%s-%s%s" % (r, shape["name"], arm["name"], (".rr%d" % attempt) if attempt else "")


# ---------------------------------------------------------------- metadata

def _cmd_out(args, timeout=60):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return "error: %s" % e


def harness_version():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vf = os.path.join(here, "VERSION")
    if os.path.exists(vf):
        with open(vf) as f:
            return f.read().strip()
    try:
        r = subprocess.run(["git", "-C", here, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        d = subprocess.run(["git", "-C", here, "status", "--porcelain"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return "%s (no git)" % __version__
    if r.returncode != 0:
        return "%s (uncommitted)" % __version__
    return "%s %s%s" % (__version__, r.stdout.strip()[:12], " dirty" if d.stdout.strip() else "")


def nighthawk_commit(version_text, configured=None):
    """(commit, source) for the client build. A commit given in the config wins;
    else a 40-hex revision printed by `--version` (Envoy-style builds print
    "<sha>/<version>/..."); else None, and the md5 identifies the build."""
    if configured and configured != "unknown":
        return configured, "config"
    m = re.search(r"\b([0-9a-f]{40})\b", version_text or "")
    if m:
        return m.group(1), "--version"
    return None, "not found in --version; the md5 identifies the build"


def collect_metadata(exp, bootstrap_text, texts=None):
    md = {"harness": harness_version(), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "machine_label": exp.get("machine_label"),
          "machine": sysprobe.machine_metadata(exp["cpus"], exp.get("record_hostname", False)),
          "cpus": exp["cpus"], "config_sha256": sysprobe.text_sha256(exp["_config_text"]),
          "bootstrap_sha256": sysprobe.text_sha256(bootstrap_text), "arms": {}}
    if texts:
        md["bootstrap_sha256_per_arm"] = {k: sysprobe.text_sha256(v) for k, v in texts.items()}
    for a in exp["arms"]:
        h = sysprobe.file_hashes(a["binary"])
        ver = _cmd_out([a["binary"], "--version"])
        vm = re.search(r"version:\s*(\S+)", ver)
        md["arms"][a["name"]] = dict(h, path=a["binary"], version=vm.group(1) if vm else ver[-200:],
                                     source=a.get("source"), source_sha256=a.get("source_sha256"),
                                     extra_args=a.get("extra_args", []), settings=arm_settings(a),
                                     env=a.get("env", {}))
    nh = exp["client"]["binary"]
    vtxt = _cmd_out([nh, "--version"])
    vline = ([x for x in vtxt.splitlines() if x.strip()] or [""])[-1]
    vm = re.search(r"version:\s*(\S+)", vline)
    commit, csrc = nighthawk_commit(vtxt, exp["client"].get("commit"))
    md["client"] = dict(sysprobe.file_hashes(nh), path=nh, version=vm.group(1) if vm else vline[-80:],
                        commit=commit, commit_source=csrc,
                        settings={k: v for k, v in exp["client"].items() if k != "binary"})
    md["perf_version"] = _cmd_out(exp["measure"]["perf"] + ["--version"])
    return md


ARCH_ALIASES = {"amd64": "x86_64", "arm64": "aarch64"}
ELF_MACHINE = {62: "x86_64", 183: "aarch64"}


def norm_arch(a):
    return ARCH_ALIASES.get(a, a)


def box_arch(exp):
    """The architecture a config is for: its `box.arch`, else this machine's."""
    return norm_arch((exp.get("box") or {}).get("arch") or platform.machine())


def elf_arch(path):
    """Architecture of an ELF executable from its header (e_machine), or None."""
    try:
        with open(path, "rb") as f:
            h = f.read(20)
    except OSError:
        return None
    if len(h) < 20 or h[:4] != b"\x7fELF":
        return None
    order = "little" if h[5] == 1 else "big"
    return ELF_MACHINE.get(int.from_bytes(h[18:20], order), "elf-machine-%d" % int.from_bytes(h[18:20], order))


def check_arch(exp):
    """[error]: the box description against this machine, and every arm's binary against both."""
    errs = []
    here = norm_arch(platform.machine())
    want = box_arch(exp)
    if want != here:
        errs.append("config is for %s, this machine is %s" % (want, here))
    for a in exp["arms"]:
        ea = elf_arch(a["binary"])
        if ea is not None and ea != want:
            errs.append("arm %s binary is %s, not %s" % (a["name"], ea, want))
    return errs


def check_binaries(exp, md):
    errs = []
    for a in exp["arms"]:
        want = a.get("md5")
        got = md["arms"][a["name"]]["md5"]
        if want and want != got:
            errs.append("arm %s md5 %s != expected %s" % (a["name"], got, want))
        want = a.get("source_sha256")
        got = md["arms"][a["name"]]["sha256"]
        if want and want != got:
            errs.append("arm %s sha256 %s != source sha256 %s" % (a["name"], got, want))
    return errs


def validate_bootstrap(exp, path):
    """path: one bootstrap for every arm, or {arm name: path, "_hop2:<arm>": path}."""
    res = {}
    todo = [(a["name"], a, path[a["name"]] if isinstance(path, dict) else path) for a in exp["arms"]]
    if isinstance(path, dict):
        todo += [(hop2_key(a), a, path[hop2_key(a)]) for a in exp["arms"] if hop2_key(a) in path]
    for name, a, path in todo:
        try:
            r = subprocess.run([a["binary"], "--mode", "validate", "-c", path, "-l", "warn"],
                               capture_output=True, text=True, timeout=120,
                               env=dict(os.environ, **a.get("env", {})))
            out, rc = r.stdout + r.stderr, r.returncode
        except (OSError, subprocess.TimeoutExpired) as e:
            out, rc = "error: %s" % e, -1
        ok = rc == 0 and re.search(r"^configuration '.*' OK$", out, re.M) is not None
        res[name] = {"ok": ok, "exit": rc, "deprecated_lines": len(re.findall(r"(?i)deprecat", out)),
                          "warnings": [ln[-300:] for ln in out.splitlines() if "[warning]" in ln][:10],
                          "tail": out[-400:]}
    return res


# ---------------------------------------------------------------- analysis

def comparison_pairs(exp):
    """[(arm, reference)] names, in a stable order."""
    names = [a["name"] for a in exp["arms"]]
    base = exp.get("base_arm", names[0])
    if exp.get("comparisons", "base") == "all_pairs":
        return [(names[j], names[i]) for i in range(len(names)) for j in range(i + 1, len(names))]
    return [(n, base) for n in names if n != base]


def floor_from_results(res, arm=None):
    """{shape: {metric: {"hw": A/A 95% half-width, "far": far end of the A/A 95%
    interval from zero}}} in log-%, from an A/A results dict. Over several A/A
    comparisons in one shape, the widest is kept. With `arm`, only that arm's
    comparisons count: an A/A arm inside another experiment (a second copy of the
    base binary in a release run, say), whose other comparisons are not A/A."""
    out = {}
    for s, sres in res["analysis"]["shapes"].items():
        for comp in sres.get("comparisons", []):
            if arm is not None and comp.get("arm") != arm:
                continue
            for k in METRIC_KEYS:
                p = (comp.get(k) or {}).get("paired") or {}
                if p.get("half_width_pct") is None:
                    continue
                far = max(abs(p["log_lo_pct"]), abs(p["log_hi_pct"]))
                cur = out.setdefault(s, {}).setdefault(k, {"hw": 0.0, "far": 0.0})
                cur["hw"] = max(cur["hw"], p["half_width_pct"])
                cur["far"] = max(cur["far"], far)
    return out


def aa_position(c):
    """Where an effect sits against the A/A run: "floor" when |effect| is within
    the A/A half-width, "interval" when within the far end of the A/A interval,
    None when outside both (or no A/A given). Log-% on both sides."""
    hw, far = c.get("aa_floor_half_width_pct"), c.get("aa_floor_far_pct")
    p = c.get("paired") or {}
    if hw is None or p.get("log_mean_pct") is None:
        return None
    e = abs(p["log_mean_pct"])
    if e <= hw:
        return "floor"
    if far is not None and e <= far:
        return "interval"
    return None


def load_floor(path, arm=None):
    if not path:
        return None
    with open(os.path.expanduser(path)) as f:
        fl = floor_from_results(json.load(f), arm)
    if arm is not None and not fl:
        raise ValueError("floor %s has no comparison of arm %s" % (path, arm))
    return fl


def _value(m, key, get, vcfg):
    if key in LATENCY_KEYS and not validity.latency_ok(m, vcfg):
        return None
    try:
        return get(m)
    except (KeyError, TypeError):
        return None


def current_legs(legs):
    """Valid, not superseded legs keyed by (shape, arm, round)."""
    by = {}
    for m in legs:
        if m.get("superseded") or not m.get("verdict", {}).get("valid"):
            continue
        by[(m["shape"], m["arm"], m["round"])] = m
    return by


def confirmatory_in_shape(p, shape):
    """Whether a confirmatory entry ([arm, ref] or [arm, ref, shape(s)]) covers this shape."""
    if len(p) < 3:
        return True
    return shape in ([p[2]] if isinstance(p[2], str) else p[2])


def complete_rounds(exp, legs):
    """The last round R, a multiple of the order period, such that every round up to R has a
    current (not superseded) leg for every shape and arm: only these rounds are balanced.
    An invalid leg counts only once its round has had all its re-runs (the method then drops
    that pair); an invalid leg still waiting for its re-run (a run stopped in the re-run
    phase) does not, so that block is not complete."""
    reruns = int(exp.get("rerun_invalid", 1))
    have = {(m["round"], m["shape"], m["arm"]) for m in legs
            if not m.get("superseded") and "round" in m
            and ((m.get("verdict") or {}).get("valid") or int(m.get("attempt", 0)) >= reruns)}
    per = order_period(exp)
    r = 0
    while True:
        nxt = range(r + 1, r + per + 1)
        if all((x, sh["name"], a["name"]) in have for x in nxt for sh, a in cells(exp)):
            r += per
        else:
            return r


INCOMPLETE = "incomplete, no verdict"


def mark_incomplete(analysis):
    """A run stopped before its minimum rounds: every row keeps its numbers, none a verdict."""
    analysis["incomplete"] = True
    for sres in analysis["shapes"].values():
        for comp in sres["comparisons"] + sres.get("confirmatory", []):
            for key in METRIC_KEYS:
                c = comp.get(key)
                if c:
                    c["status"] = INCOMPLETE
                    c["differs"] = None
    return analysis


def analyse(exp, legs, floor=None):
    base = exp.get("base_arm", exp["arms"][0]["name"])
    alpha = exp.get("alpha", ALPHA)
    primary = exp.get("primary_metric", "cycles_total")
    min_pairs = exp.get("min_pairs", 6)
    vcfg = exp.get("validity")
    by = current_legs(legs)
    getters = {k: g for k, _, g in METRICS}
    out = {"base_arm": base, "alpha": alpha, "primary_metric": primary, "min_pairs": min_pairs,
           "rounds_done": max([m["round"] for m in legs] or [0]), "shapes": {},
           "headline": "mean of per-round log ratios (arm/reference) with a two-sided 95% t interval"}
    for sh in exp["shapes"]:
        s = sh["name"]
        sres = {"arms": {}, "comparisons": [], "vs_base": {}}
        for a in exp["arms"]:
            an = a["name"]
            mine = [m for m in legs if m["shape"] == s and m["arm"] == an and not m.get("superseded")]
            valid = [m for m in mine if m.get("verdict", {}).get("valid")]
            summ = {"legs": len(mine), "valid": len(valid),
                    "superseded": len([m for m in legs if m["shape"] == s and m["arm"] == an
                                       and m.get("superseded")])}
            for key, _, get in METRICS:
                vals = [v for v in (_value(m, key, get, vcfg) for m in valid) if v is not None]
                if vals:
                    sd = stats.stdev(vals)
                    mu = stats.mean(vals)
                    summ[key] = {"mean": mu, "median": stats.median(vals), "min": min(vals), "max": max(vals),
                                 "cv_pct": (100.0 * sd / mu) if sd is not None and mu else None, "n": len(vals)}
            busy = [m["sut_busy"] for m in valid if m.get("sut_busy") is not None]
            if busy:
                summ["sut_busy_mean"] = stats.mean(busy)
            hr = [m["client_headroom"] for m in valid if m.get("client_headroom") is not None]
            if hr:
                summ["client_headroom_min"] = min(hr)
            sres["arms"][an] = summ
        sres["confirmatory"] = []
        conf = [(p[0], p[1]) for p in exp.get("confirmatory") or [] if confirmatory_in_shape(p, s)]
        for an, rn, kind in [(a, r, "row") for a, r in comparison_pairs(exp)] + [(a, r, "conf") for a, r in conf]:
            rounds = sorted(r for (ss, aa, r) in by if ss == s and aa == an and (s, rn, r) in by)
            comp = {"arm": an, "ref": rn, "rounds_paired": rounds}
            for key, _, get in METRICS:
                pr = [r for r in rounds if _value(by[(s, rn, r)], key, get, vcfg) is not None
                      and _value(by[(s, an, r)], key, get, vcfg) is not None]
                if not pr:
                    continue
                bv = [_value(by[(s, rn, r)], key, get, vcfg) for r in pr]
                av = [_value(by[(s, an, r)], key, get, vcfg) for r in pr]
                c = stats.compare_paired(bv, av, alpha=alpha)
                if key != primary:
                    c["role"] = "exploratory"
                else:
                    c["role"] = "confirmatory" if kind == "conf" else "primary"
                if floor and s in floor and key in floor[s]:
                    c["aa_floor_half_width_pct"] = floor[s][key]["hw"]
                    c["aa_floor_far_pct"] = floor[s][key]["far"]
                comp[key] = c
            if kind == "conf":
                # named before the run, its own family: Holm across these rows only
                sres["confirmatory"].append(comp)
                continue
            sres["comparisons"].append(comp)
            if rn == base:
                sres["vs_base"][an] = comp
        out["shapes"][s] = sres
    # Holm across the primary rows; everything else stays exploratory.
    prim = []
    for s, sres in out["shapes"].items():
        for comp in sres["comparisons"]:
            c = comp.get(primary)
            if c and c["paired"].get("t_p") is not None and c["n"] >= min_pairs:
                prim.append(c)
    adj = stats.holm([c["paired"]["t_p"] for c in prim])
    for c, a in zip(prim, adj):
        c["holm_p"] = a
    out["primary_family_size"] = len(prim)
    cfm = []
    for s, sres in out["shapes"].items():
        for comp in sres.get("confirmatory", []):
            c = comp.get(primary)
            if c and c["paired"].get("t_p") is not None and c["n"] >= min_pairs:
                cfm.append(c)
    for c, a in zip(cfm, stats.holm([c["paired"]["t_p"] for c in cfm])):
        c["holm_p"] = a
    if exp.get("confirmatory"):
        out["confirmatory_family_size"] = len(cfm)
    for s, sres in out["shapes"].items():
        for comp in sres["comparisons"] + sres.get("confirmatory", []):
            for key in METRIC_KEYS:
                c = comp.get(key)
                if not c:
                    continue
                p = c["paired"]
                if c["n"] < min_pairs or p.get("half_width_pct") is None:
                    c["status"] = "insufficient"
                    c["differs"] = None
                elif c["role"] in ("primary", "confirmatory"):
                    c["differs"] = c.get("holm_p", 1.0) <= alpha
                    c["status"] = "differs" if c["differs"] else "not resolved"
                else:
                    c["differs"] = not (p["log_lo_pct"] <= 0.0 <= p["log_hi_pct"])
                    c["status"] = "exploratory: interval excludes 0" if c["differs"] else "exploratory"
                # A difference no larger than what the A/A could not exclude is
                # not a finding on its own; say so instead of leaving it to the write-up.
                pos = aa_position(c) if c.get("differs") else None
                c["inside_aa"] = pos
                if pos == "floor":
                    c["status"] += ", inside the A/A floor"
                elif pos == "interval":
                    c["status"] += ", inside the A/A interval"
    return out


def stop_check(exp, analysis):
    """(stop, why): every primary comparison has n >= min_pairs and a 95% half-width
    at or under the target. Stopping on interval width, never on a p-value."""
    target = exp.get("stop", {}).get("target_half_width_pct", 3.0)
    metric = exp.get("stop", {}).get("metric", exp.get("primary_metric", "cycles_total"))
    if exp.get("expect") == "aa":
        # an A/A run keeps going until it can pass its own half-width limit
        lim = exp.get("aa", DEFAULTS["aa"])["max_half_width_pct"].get(metric)
        if lim is not None:
            target = min(target, lim)
    worst = []
    rows = "confirmatory" if exp.get("stop", {}).get("rows") == "confirmatory" else "comparisons"
    # a shape may set its own target (the same absolute cost is a larger percentage on a
    # cheaper shape); an A/A run's own limit still caps it
    starget = {sh["name"]: sh.get("stop_target_half_width_pct") for sh in exp["shapes"]}
    for s, sres in analysis["shapes"].items():
        t = target if starget.get(s) is None else float(starget[s])
        if exp.get("expect") == "aa" and starget.get(s) is not None:
            lim = exp.get("aa", DEFAULTS["aa"])["max_half_width_pct"].get(metric)
            t = t if lim is None else min(t, lim)
        for comp in sres.get(rows, []):
            c = comp.get(metric)
            hw = (c or {}).get("paired", {}).get("half_width_pct")
            if c is None or hw is None or c["n"] < exp.get("min_pairs", 6):
                return False, "%s %s vs %s: not enough pairs" % (s, comp["arm"], comp["ref"])
            worst.append((hw / t, hw, t, "%s %s vs %s" % (s, comp["arm"], comp["ref"])))
    if not worst:
        return False, "no comparisons"
    _, hw, t, where = max(worst)
    if all(w[0] <= 1.0 for w in worst):
        return True, "widest %s half-width against its target %.2f%% (%s) <= target %.2f%%" % (metric, hw, where, t)
    return False, "widest %s half-width against its target %.2f%% (%s) > target %.2f%%" % (metric, hw, where, t)


def aa_verdict(exp, analysis):
    """A/A self-test with power.

    Pass when, for every shape and every metric in aa.metrics:
      - there are at least min_pairs valid pairs;
      - the difference is not significant after Holm across all the A/A checks
        (paired t), so a perfect harness fails at most alpha of the time overall;
      - the 95% half-width is at or under aa.max_half_width_pct for that metric,
        so the run could have seen a bias of about that size (mde_pct is the bias
        it detects with 80% power, before the Holm step).
    """
    aa = exp.get("aa", DEFAULTS["aa"])
    alpha = analysis["alpha"]
    checks = []
    for s, sres in analysis["shapes"].items():
        for comp in sres["comparisons"]:
            for k in aa["metrics"]:
                c = comp.get(k)
                ch = {"shape": s, "arm": comp["arm"], "ref": comp["ref"], "metric": k,
                      "max_half_width_pct": aa["max_half_width_pct"].get(k)}
                if not c or c["n"] < analysis.get("min_pairs", 6) or c["paired"].get("t_p") is None:
                    ch.update(ok=False, why="insufficient pairs", pairs=(c or {}).get("n", 0))
                    checks.append(ch)
                    continue
                p = c["paired"]
                ch.update(pairs=c["n"], effect_pct=p["effect_pct"], lo_pct=p["lo_pct"], hi_pct=p["hi_pct"],
                          half_width_pct=p["half_width_pct"], sd_pct=p["log_sd_pct"], t_p=p["t_p"],
                          mde_pct=p["mde_pct"], sign_p=c["sign_p"], won=c["pairs_won"])
                checks.append(ch)
    live = [c for c in checks if "t_p" in c]
    for c, a in zip(live, stats.holm([c["t_p"] for c in live])):
        c["holm_p"] = a
        why = []
        if a <= alpha:
            why.append("differs (Holm p %.3f)" % a)
        lim = c["max_half_width_pct"]
        if lim is not None and c["half_width_pct"] > lim:
            why.append("half-width %.2f%% > %.2f%%" % (c["half_width_pct"], lim))
        c["ok"] = not why
        c["why"] = "; ".join(why) or "ok"
    return {"pass": bool(checks) and all(c["ok"] for c in checks), "checks": checks,
            "rule": "no Holm-significant difference and 95% half-width within the limit on every check"}


# ---------------------------------------------------------------- run loop

def harness_cpus(exp):
    """CPUs for the harness itself: everything online that no configured set or SUT sibling uses."""
    if exp["cpus"].get("harness"):
        return sysprobe.parse_cpuset(exp["cpus"]["harness"])
    used = set()
    for k, v in exp["cpus"].items():
        used |= sysprobe.parse_cpuset(v)
    used |= sysprobe.siblings_of(sysprobe.parse_cpuset(exp["cpus"]["sut"]) |
                                 sysprobe.parse_cpuset(exp["cpus"].get("hop2", "")))
    return sysprobe.online_cpus() - used


class Runner:
    def __init__(self, exp, run_dir, backend_factory, allow_short=False, log_stream=None):
        self.exp = exp
        self.run_dir = run_dir
        self.allow_short = allow_short
        for d in ("logs", "nighthawk", "perf"):
            os.makedirs(os.path.join(run_dir, d), exist_ok=True)
        self._logf = open(os.path.join(run_dir, "log.txt"), "a")
        self._stream = log_stream
        self.backend = backend_factory(exp, run_dir, self.log)

    def log(self, msg):
        line = sysprobe.scrub_text("%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg))
        self._logf.write(line + "\n")
        self._logf.flush()
        if self._stream:
            self._stream.write(line + "\n")
            self._stream.flush()

    def status(self, **kw):
        kw["updated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        kw["pid"] = os.getpid()
        tmp = os.path.join(self.run_dir, "status.json.tmp")
        with open(tmp, "w") as f:
            json.dump(sysprobe.scrub(kw), f, indent=1)
        os.replace(tmp, os.path.join(self.run_dir, "status.json"))

    def _record(self, m):
        with open(os.path.join(self.run_dir, "legs.jsonl"), "a") as f:
            f.write(json.dumps(sysprobe.scrub(m), sort_keys=True) + "\n")

    def _leg(self, legs, r, sh, a, bpath, attempt=0):
        lid = leg_id(r, sh, a, attempt)
        m = self.backend.run_leg(a, sh, r, bpath, lid)
        m["attempt"] = attempt
        legs.append(m)
        self._record(m)
        v = m["verdict"]
        pr = m.get("per_req") or {}
        self.log("%s %s ins_u=%.1fk cyc_tot=%.1fk busy=%s rate=%.1f/%d p99=%s %s" % (
            lid, "VALID" if v["valid"] else "INVALID",
            pr.get("instructions_u", 0) / 1e3, pr.get("cycles_total", 0) / 1e3,
            ("%.1f%%" % (m["sut_busy"] * 100)) if m.get("sut_busy") is not None else "-",
            m.get("sut_rate_2xx") or 0, m["target_rps"],
            ("%.0fus" % m["latency_us"]["p99"]) if (m.get("latency_us") or {}).get("p99") else "-",
            "" if v["valid"] else "; ".join(v["reasons"])))
        if v["valid"]:
            self._invalid_streak = 0
        else:
            self._invalid_streak += 1
            if self._invalid_streak >= self.exp.get("abort_after_invalid", 6):
                raise RuntimeError("%d consecutive invalid legs; giving up" % self._invalid_streak)
        return m

    def _rerun_invalid(self, legs, first, last, bpath):
        """Re-run, at the end of a block, every (round, shape) in it that has an invalid leg:
        all arms again, in the round's own order, so the round stays balanced."""
        if cell_mode(self.exp):
            return self._rerun_invalid_rounds(legs, first, last, bpath)
        for attempt in range(1, self.exp.get("rerun_invalid", 1) + 1):
            todo = []
            for r in range(first, last + 1):
                for sh in self.exp["shapes"]:
                    cur = [m for m in legs if m["round"] == r and m["shape"] == sh["name"]
                           and not m.get("superseded")]
                    if any(not m["verdict"]["valid"] for m in cur):
                        todo.append((r, sh, cur))
            if not todo:
                return
            for r, sh, cur in todo:
                self.log("re-running round %d shape %s (attempt %d): invalid %s" % (
                    r, sh["name"], attempt, [m["leg_id"] for m in cur if not m["verdict"]["valid"]]))
                for m in cur:
                    m["superseded"] = True
                self._record({"supersede": [m["leg_id"] for m in cur]})
                for a in round_order(self.exp, r):
                    self._leg(legs, r, sh, a, bpath, attempt)

    def _rerun_invalid_rounds(self, legs, first, last, bpath):
        """Cells: a round with an invalid leg is run again whole (every cell, in the round's own
        order) at the end of the block. `abort_after_invalid_rounds` (default 3) rounds with an
        invalid leg in a row, first runs and re-runs counted in the order they ran, abort."""
        for attempt in range(1, self.exp.get("rerun_invalid", 1) + 1):
            todo = []
            for r in range(first, last + 1):
                cur = [m for m in legs if m["round"] == r and not m.get("superseded")]
                if any(not m["verdict"]["valid"] for m in cur):
                    todo.append((r, cur))
            if not todo:
                return
            for r, cur in todo:
                self.log("re-running round %d, every cell (attempt %d): invalid %s" % (
                    r, attempt, [m["leg_id"] for m in cur if not m["verdict"]["valid"]]))
                for m in cur:
                    m["superseded"] = True
                self._record({"supersede": [m["leg_id"] for m in cur]})
                self._round_done([self._leg(legs, r, sh, a, bpath, attempt) for sh, a in cell_order(self.exp, r)])

    def _round_done(self, round_legs):
        """Cells: count rounds with an invalid leg in a row, as they ran; abort at the limit."""
        bad = any(not m["verdict"]["valid"] for m in round_legs)
        self._round_streak = self._round_streak + 1 if bad else 0
        lim = int(self.exp.get("abort_after_invalid_rounds", 3))
        if self._round_streak >= lim:
            raise RuntimeError("%d rounds in a row with an invalid leg; giving up" % self._round_streak)

    def run(self, simulate=False):
        exp = self.exp
        self._invalid_streak = 0
        self._round_streak = 0
        bpath, btexts, certs = prepare_bootstraps(exp, self.run_dir, self.log, make_certs=not simulate)
        btxt = btexts[exp["arms"][0]["name"]]
        with open(os.path.join(self.run_dir, "experiment.json"), "w") as f:
            json.dump(sysprobe.scrub({k: v for k, v in exp.items() if not k.startswith("_")}), f, indent=1,
                      sort_keys=True)
        floor = load_floor(exp.get("floor_from"), exp.get("floor_arm"))
        legs_min = len(schedule(exp))
        legs_max = len(schedule(exp, 1, exp["rounds_max"] if exp.get("adaptive", True) else exp["rounds"]))
        self.status(state="starting", legs_min=legs_min, legs_max=legs_max, legs_done=0)
        if simulate:
            md = self.backend.metadata(exp, btxt)
        else:
            hc = harness_cpus(exp)
            if hc:
                os.sched_setaffinity(0, hc)
            md = collect_metadata(exp, btxt, btexts)
            md["harness_cpus"] = sorted(os.sched_getaffinity(0))
            errs = check_binaries(exp, md) + check_wasm(exp) + (check_arch(exp) if exp.get("box") else [])
            md["box"] = exp.get("box")
            md["page_size"] = os.sysconf("SC_PAGE_SIZE")
            md["wasm_sha256"] = {a: w[1] for a, w in wasm_files(exp).items()}
            if errs:
                raise SystemExit("binary proof failed: " + "; ".join(errs))
            md["bootstrap_validate"] = validate_bootstrap(exp, bpath)
            bad = [k for k, v in md["bootstrap_validate"].items() if not v["ok"]]
            if bad:
                raise SystemExit("envoy --mode validate failed for %s: %s" % (
                    bad, md["bootstrap_validate"][bad[0]]["tail"]))
        if certs:
            md["tls"] = certs
        md["order"] = effective_order(exp)
        self.log("run %s: %s order, rounds %d..%d in blocks of %d (adaptive %s), arms %s, shapes %s" % (
            exp["name"], md["order"], exp["rounds"], exp["rounds_max"], exp["rounds_block"],
            exp.get("adaptive", True), [a["name"] for a in exp["arms"]], [s["name"] for s in exp["shapes"]]))
        origin = None
        collector = None
        legs = []
        done = 0
        target = exp["rounds"]
        stop_reason = None
        aborted = None
        try:
            if not simulate:
                from .origin import Origin
                origin = Origin(exp["origin"], exp["cpus"].get("origin", ""), exp["shapes"], self.run_dir, self.log)
                md["origin"] = origin.start()
                if needs_collector(exp):
                    from .origin import Collector
                    collector = Collector(exp["collector"], exp["cpus"]["origin"], self.run_dir, self.log)
                    md["collector"] = collector.start()
                if hasattr(self.backend, "attach"):
                    self.backend.attach(origin, collector)
                if uses(exp, "access_log"):
                    md["access_log_fs"] = sysprobe.fs_of(os.path.join(self.run_dir, "alog"))
            while True:
                plan = schedule(exp, done + 1, target)
                for i, (r, sh, a) in enumerate(plan):
                    self.status(state="running", rounds_done=done, rounds_target=target,
                                rounds_max=exp["rounds_max"], legs_done=len(legs),
                                current=leg_id(r, sh, a),
                                invalid_so_far=sum(1 for m in legs if not m["verdict"]["valid"]))
                    self._leg(legs, r, sh, a, bpath)
                    if cell_mode(exp) and (i + 1 == len(plan) or plan[i + 1][0] != r):
                        self._round_done([x for x in legs if x["round"] == r and not x.get("superseded")])
                self._rerun_invalid(legs, done + 1, target, bpath)
                done = target
                an = analyse(exp, legs, floor)
                stop, why = stop_check(exp, an)
                self.log("after %d rounds: %s" % (done, why))
                if not exp.get("adaptive", True):
                    stop_reason = "fixed rounds"
                    break
                if stop:
                    stop_reason = why
                    break
                if done >= exp["rounds_max"]:
                    stop_reason = "cap of %d rounds reached; %s" % (exp["rounds_max"], why)
                    break
                target = min(done + exp["rounds_block"], exp["rounds_max"])
        except BaseException as e:  # noqa: BLE001 - recorded (a stop signal too), partial results still written
            aborted = "%s: %s" % (type(e).__name__, e)
            self.log("ABORTED: %s" % aborted)
        finally:
            if collector:
                collector.stop()
            if origin:
                origin.stop()
            if hasattr(self.backend, "close"):
                self.backend.close()
        if not simulate:
            end = {a["name"]: sysprobe.file_hashes(a["binary"])["md5"] for a in exp["arms"]}
            md["arms_md5_at_end"] = end
            md["arms_md5_unchanged"] = all(end[n] == md["arms"][n]["md5"] for n in end)
            if wasm_files(exp):
                md["wasm_unchanged_at_end"] = not check_wasm(exp)
            cs = md["machine"].get("cpuidle_sut_summary") or {}
            if cs.get("cpus"):
                fp = sysprobe.cpuidle_fingerprint(sysprobe.parse_cpuset(cs["cpus"]))
                md["cpuidle_fingerprint_at_end"] = fp
                md["cpuidle_unchanged"] = fp == cs.get("fingerprint")
        md["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        md["platform"] = platform.platform()
        md["rounds_done"] = done
        md["stop_reason"] = stop_reason
        if aborted:
            md["aborted"] = aborted
        # Only complete rotation blocks enter the analysis. A run that ends before its
        # minimum rounds (a stop signal, an abort) is incomplete: numbers, no verdicts.
        md["rounds_complete"] = complete_rounds(exp, legs)
        # A run that was stopped or aborted never reached its stop rule: incomplete as well,
        # even with its minimum rounds done
        md["incomplete"] = md["rounds_complete"] < exp["rounds"] or aborted is not None
        if aborted is not None:
            md["stopped_early"] = "stopped before its stop rule (%s); %d complete rounds" % (
                aborted, md["rounds_complete"])
        used = [m for m in legs if m["round"] <= md["rounds_complete"]]
        if len(used) < len(legs):
            md["legs_after_last_complete_block"] = len(legs) - len(used)
        analysis = analyse(exp, used, floor)
        if md["incomplete"]:
            mark_incomplete(analysis)
            self.log("run incomplete: %d complete rounds of the minimum %d%s; no verdicts" % (
                md["rounds_complete"], exp["rounds"], ", stopped early" if aborted else ""))
        result = {"metadata": md, "experiment": {k: v for k, v in exp.items() if not k.startswith("_")},
                  "legs": legs, "analysis": analysis}
        if exp.get("expect") == "aa" and not md["incomplete"]:
            result["aa_selftest"] = aa_verdict(exp, analysis)
        result = sysprobe.scrub(result)
        with open(os.path.join(self.run_dir, "results.json"), "w") as f:
            json.dump(result, f, indent=1, sort_keys=True)
        from .report import markdown
        with open(os.path.join(self.run_dir, "summary.md"), "w") as f:
            f.write(markdown(result))
        self.status(state="aborted" if aborted else "done", rounds_done=done, legs_done=len(legs),
                    invalid=sum(1 for m in legs if not m["verdict"]["valid"]), error=aborted)
        self.log("done: %s" % os.path.join(self.run_dir, "summary.md"))
        if not simulate:
            sysprobe.scrub_tree(self.run_dir)
        if aborted:
            raise RuntimeError(aborted)
        return result
