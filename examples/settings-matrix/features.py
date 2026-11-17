#!/usr/bin/env python3
"""Feature rows, session 1: settings that already exist in the harness, each against the
settings-matrix baseline (make.py), with evidence that the feature ran on every leg.

    python3 examples/settings-matrix/features.py [write] [RATES_JSON]
    python3 examples/settings-matrix/features.py budget SMOKE_ROOT     seconds per leg, worst cases
    python3 examples/settings-matrix/features.py has-floor RUN_DIR      exit 0 if the run has a result

Configs (in features/):

  run-s.json        rows 19, 20, 21 and the A/A of the session in the same rounds: base,
                    retry-on (retry policy, never triggered), idle-off (stream and
                    connection idle timeout 0s), percpu-on (tcmalloc per-CPU caches via
                    GLIBC_TUNABLES=glibc.pthread.rseq=0), base-A2 (a second copy of the
                    baseline). Shapes s, fh; 20 rounds minimum, blocks of 10, cap 30, stop
                    when the confirmatory rows reach 0.8% on both shapes.
  18-access-log.json   file access log off, text, JSON. 18/6/30; 0.8% on s, 1.5% on fh.
  17-tracing.json      OpenTelemetry at 1%, 10%, 100% against no tracer; 16 fixed rounds.
                       Collector telemetry at level basic on a fixed port (a change against
                       the first tracing row, which ran it at none).
  13-ext-authz.json    external authorization, HTTP and gRPC, against off, plus a second
                       copy of off (the A/A of the 6,000 req/s header shape); s and fh6
                       (fh at 6,000 req/s); 16 fixed rounds.
  18w-access-log-w16.json   the access log at 16 workers on CPUs 0-15 (siblings idle), with
                       its own A/A arm; s-w16 at a calibrated rate, ramped client, 3 s
                       lead-in; 16/8/32, 1.0% on every row, the A/A included. Optional.
  smoke-*.json      two rounds of every arm, reference arms and A/A copies included (two
                    arms per smoke, so every order balances in two rounds); evidence is
                    recorded, not gated, and checked offline afterwards with
                    `epl evidence-check`, which fails when any arm has no smoke leg.

Every run uses order seed 21. Rows 17 and 18 take the A/A floor from run S's base-A2
arm (same session, an earlier run); rows 13 and 18w carry their own A/A arm (no floor_from). The named
confirmatory rows and the session-wide Holm step are in features_table.py, not here:
the per-run Holm values in results.json are not quoted.

Evidence counter names are the harness's best reading of v1.40.2's stats; the smoke's
saved /stats (stats/<arm>.txt.gz in each smoke run) is the source of truth, and any
name that differs is corrected here before the queue starts.
"""

import importlib.util
import json
import os
import sys
import time

import make

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "features")
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from epl import experiment  # noqa: E402

_spec = importlib.util.spec_from_file_location("rel_make", os.path.join(HERE, "..", "releases", "make.py"))
rel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rel)

RUNS = "~/epl/runs/wk5"
ORDER_SEED = 21
FLOOR = {"floor_from": RUNS + "/run-s/results.json", "floor_arm": "base-A2"}
COLLECTOR = {"image": make.COLLECTOR, "port": 4317, "metrics_port": 8888}
AUTHZ_PORTS = {"authz_port": 8093, "authz_grpc_port": 8094}
TCMALLOC_ENV = {"GLIBC_TUNABLES": "glibc.pthread.rseq=0"}
W16_CPUS = "0-15"
W16_LEAD_IN_S = 3
SESSION_STOP_S = 10 * 3600
MANDATORY = ["run-s", "18-access-log", "17-tracing", "13-ext-authz"]
OPTIONAL = ["18w-access-log-w16"]
ASK_LEAD_ABOVE_S = 9.5 * 3600

# ---------------------------------------------------------------- evidence

Z = {"tol_abs": 0}


def zero(stat, scope="window", **kw):
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


ONE = {"per_request": 1.0, "tol": 0.002}  # "1.000": within 0.2% of the 2xx responses in the window
TCMALLOC_OFF = zero("tcmalloc_percpu_slab_bytes", "field", label="tcmalloc per-CPU slab bytes 0")
TCMALLOC_ON = {"stat": "tcmalloc_percpu_slab_bytes", "scope": "field", "min": 1,
               "label": "tcmalloc per-CPU slab bytes > 0"}
IDLE_COUNTERS = [zero("http.ingress_http.downstream_cx_idle_timeout", "leg"),
                 zero("http.ingress_http.downstream_rq_idle_timeout", "leg")]
NO_RETRY_POLICY = {"stat": "retry_policy", "scope": "config", "absent": True}
NO_IDLE_SETTING = {"stat": "stream_idle_timeout", "scope": "config", "absent": True}

EV_BASE = [TCMALLOC_OFF, NO_RETRY_POLICY, NO_IDLE_SETTING, zero("cluster.origin.upstream_rq_retry")] + IDLE_COUNTERS
EV_RETRY = [TCMALLOC_OFF, {"stat": "retry_policy", "scope": "config", "present": True},
            zero("cluster.origin.upstream_rq_retry"), NO_IDLE_SETTING] + IDLE_COUNTERS
EV_IDLE = [TCMALLOC_OFF, NO_RETRY_POLICY, {"stat": "stream_idle_timeout", "scope": "config", "equals": "0s"},
           {"stat": "idle_timeout", "scope": "config", "equals": "0s",
            "label": "connection idle timeout 0s (every idle_timeout in the dump)"}] + IDLE_COUNTERS
EV_PERCPU = [TCMALLOC_ON, NO_RETRY_POLICY, NO_IDLE_SETTING] + IDLE_COUNTERS

LOG_LINES = dict({"stat": "access_log_lines", "scope": "field", "per": "leg:http.ingress_http.downstream_rq_completed",
                  "label": "log lines per request completed over the leg"}, **ONE)
EV_LOG_OFF = [{"stat": "access_log_lines", "scope": "field", "absent": True, "label": "no access log file"}]
EV_LOG_TEXT = [LOG_LINES, zero("filesystem.write_failed", "leg"), zero("filesystem.reopen_failed", "leg"),
               {"stat": "access_log_bytes_per_line", "scope": "field", "min": 1, "label": "bytes per line recorded"}]
EV_LOG_JSON = EV_LOG_TEXT + [{"stat": "access_log_json_ok", "scope": "field", "equals": True,
                              "label": "first and last 100 lines parse as JSON"}]

SPANS_SENT = "tracing.opentelemetry.spans_sent"
SAMPLED = "http.ingress_http.tracing.random_sampling"
EV_TRACE_OFF = [{"stat": SPANS_SENT, "scope": "leg", "absent": True, "label": "no tracer stats"},
                zero(SAMPLED)]


def ev_trace(pct):
    share = {"stat": SAMPLED, "per_request": pct / 100.0, "tol_binomial_sd": 4,
             "label": "sampled share within 4 binomial SD of %g%%" % pct}
    if pct >= 100:
        share["tol"] = 0.002
    return [share,
            zero("cluster.otel_collector.upstream_rq_timeout"),
            zero("cluster.otel_collector.upstream_cx_connect_fail"),
            {"stat": SPANS_SENT, "scope": "leg", "per_request": 1.0, "tol": 0.05, "per": "leg:" + SAMPLED,
             "label": "spans sent per sampled request over the leg"},
            {"stat": "collector_delta.accepted_spans", "scope": "field", "per": "leg:" + SPANS_SENT, "min": 0.95,
             "label": "collector accepted >= 95% of spans sent"},
            {"stat": "collector_delta.refused_spans", "scope": "field", "max": 0,
             "label": "collector refused no span"}]


EV_AUTHZ_OFF = [{"stat": "http.ingress_http.ext_authz.ok", "absent": True, "label": "no ext_authz counters"}]
EV_AUTHZ = [dict({"stat": "http.ingress_http.ext_authz.ok"}, **ONE),
            zero("http.ingress_http.ext_authz.denied"), zero("http.ingress_http.ext_authz.error"),
            zero("http.ingress_http.ext_authz.failure_mode_allowed"),
            zero("cluster.ext_authz.upstream_rq_timeout"),
            dict({"stat": "cluster.ext_authz.upstream_rq_total"}, **ONE),
            zero("cluster.ext_authz.upstream_cx_total", label="no new connection to the service in the window")]


# ---------------------------------------------------------------- configs

def arm(name, settings=None, env=None, ev=None):
    a = make.arm(name, settings, env)
    if ev is not None:
        a["evidence"] = json.loads(json.dumps(ev))
    return a


def shapes(rates):
    S = make.shapes(rates)
    r = lambda n, d: int(rates.get(n, d))  # noqa: E731
    return {
        "s": S["s"], "fh": S["fh"],
        "fh6": dict(S["fh"], name="fh6", rps=r("fh6", 6000)),
        # 16 workers at the per-worker rate of s (1,300 req/s); the rate is set by calibration
        "s-w16": dict(S["s"], name="s-w16", rps=r("s-w16", 20800), lead_in_s=W16_LEAD_IN_S,
                      client_extra_args=["--rate-limiter-plugin-config", rel.RAMP]),
    }


def target(shape, pct):
    return dict(shape, stop_target_half_width_pct=pct)


def base_cfg():
    b = json.loads(json.dumps(make.BASE))
    b.pop("floor_from")
    b.update(workdir=RUNS, order_seed=ORDER_SEED)
    return b


ARMS = {
    "base": lambda: arm("base", ev=EV_BASE),
    "retry-on": lambda: arm("retry-on", {"retries": True}, ev=EV_RETRY),
    "idle-off": lambda: arm("idle-off", {"idle_timers_off": True}, ev=EV_IDLE),
    "percpu-on": lambda: arm("percpu-on", env=dict(TCMALLOC_ENV), ev=EV_PERCPU),
    "base-A2": lambda: arm("base-A2", ev=EV_BASE),
    "log-off": lambda: arm("log-off", ev=EV_LOG_OFF),
    "log-text": lambda: arm("log-text", {"access_log": {"format": "text"}}, ev=EV_LOG_TEXT),
    "log-json": lambda: arm("log-json", {"access_log": {"format": "json"}}, ev=EV_LOG_JSON),
    "log-off-A2": lambda: arm("log-off-A2", ev=EV_LOG_OFF),
    "trace-off": lambda: arm("trace-off", ev=EV_TRACE_OFF),
    "trace-1": lambda: arm("trace-1", {"tracing": {"sampling_pct": 1}}, ev=ev_trace(1)),
    "trace-10": lambda: arm("trace-10", {"tracing": {"sampling_pct": 10}}, ev=ev_trace(10)),
    "trace-100": lambda: arm("trace-100", {"tracing": {"sampling_pct": 100}}, ev=ev_trace(100)),
    "authz-off": lambda: arm("authz-off", ev=EV_AUTHZ_OFF),
    "authz-http": lambda: arm("authz-http", {"ext_authz": "http"}, ev=EV_AUTHZ),
    "authz-grpc": lambda: arm("authz-grpc", {"ext_authz": "grpc"}, ev=EV_AUTHZ),
    "authz-off-A2": lambda: arm("authz-off-A2", ev=EV_AUTHZ_OFF),
}


def run_configs(rates):
    S = shapes(rates)
    out = {}

    def run(fname, name, arm_names, shp, **kw):
        c = base_cfg()
        c.update(name=name, base_arm=arm_names[0], arms=[ARMS[a]() for a in arm_names], shapes=shp)
        for k, v in kw.items():
            if isinstance(v, dict) and isinstance(c.get(k), dict):
                c[k] = dict(c[k], **v)
            else:
                c[k] = v
        out[fname] = c

    fixed16 = dict(rounds=16, rounds_block=16, rounds_max=16, adaptive=False)
    run("run-s.json", "wk5-run-s", ["base", "retry-on", "idle-off", "percpu-on", "base-A2"],
        [target(S["s"], 0.8), target(S["fh"], 0.8)],
        confirmatory=[["retry-on", "base", "s"], ["idle-off", "base", "s"], ["percpu-on", "base", ["s", "fh"]]],
        rounds=20, rounds_block=10, rounds_max=30, stop={"target_half_width_pct": 0.8, "rows": "confirmatory"})
    run("18-access-log.json", "wk5-access-log", ["log-off", "log-text", "log-json"],
        [target(S["s"], 0.8), target(S["fh"], 1.5)],
        confirmatory=[["log-text", "log-off"], ["log-json", "log-off"]],
        rounds=18, rounds_block=6, rounds_max=30, stop={"target_half_width_pct": 1.5, "rows": "confirmatory"},
        **FLOOR)
    run("17-tracing.json", "wk5-tracing", ["trace-off", "trace-1", "trace-10", "trace-100"], [S["s"], S["fh"]],
        confirmatory=[["trace-1", "trace-off"], ["trace-100", "trace-off"]], collector=dict(COLLECTOR),
        **dict(fixed16, **FLOOR))
    run("13-ext-authz.json", "wk5-ext-authz", ["authz-off", "authz-http", "authz-grpc", "authz-off-A2"],
        [S["s"], S["fh6"]], confirmatory=[["authz-http", "authz-off"], ["authz-grpc", "authz-off"]],
        origin=dict(make.BASE["origin"], **AUTHZ_PORTS), **fixed16)
    run("18w-access-log-w16.json", "wk5-access-log-w16", ["log-off", "log-text", "log-json", "log-off-A2"],
        [S["s-w16"]], confirmatory=[["log-text", "log-off"], ["log-json", "log-off"]],
        envoy=dict(make.BASE["envoy"], workers=16), cpus=dict(make.BASE["cpus"], sut=W16_CPUS),
        rounds=16, rounds_block=8, rounds_max=32, stop={"target_half_width_pct": 1.0})
    return out


SMOKES = [
    ("smoke-s1.json", "run-s.json", ["retry-on", "idle-off"], ["s", "fh"]),
    ("smoke-s2.json", "run-s.json", ["percpu-on", "base"], ["s", "fh"]),
    ("smoke-18.json", "18-access-log.json", ["log-text", "log-json"], ["s", "fh"]),
    ("smoke-17a.json", "17-tracing.json", ["trace-1", "trace-100"], ["s", "fh"]),
    ("smoke-17b.json", "17-tracing.json", ["trace-10", "trace-off"], ["s", "fh"]),
    ("smoke-13.json", "13-ext-authz.json", ["authz-http", "authz-grpc"], ["s", "fh6"]),
    ("smoke-18w.json", "18w-access-log-w16.json", ["log-text", "log-json"], ["s-w16"]),
    # the reference arms and A/A copies, so their (absent) evidence is exercised too
    ("smoke-ref1.json", "18-access-log.json", ["log-off", "base-A2"], ["s", "fh"]),
    ("smoke-ref2.json", "13-ext-authz.json", ["authz-off", "authz-off-A2"], ["s", "fh6"]),
    ("smoke-ref3.json", "18w-access-log-w16.json", ["log-off-A2", "log-off"], ["s-w16"]),
]


def configs(rates):
    out = run_configs(rates)
    for fn, src, arms, shp in SMOKES:
        c = json.loads(json.dumps(out[src]))
        c.update(name="wk5-" + fn[:-5], base_arm=arms[0],
                 arms=[([a for a in c["arms"] if a["name"] == n] or [ARMS[n]()])[0] for n in arms],
                 shapes=[s for n in shp for s in c["shapes"] if s["name"] == n],
                 rounds=2, rounds_block=2, rounds_max=2, adaptive=False, evidence_mode="record")
        for k in ("floor_from", "floor_arm", "confirmatory", "stop"):
            c.pop(k, None)
        out[fn] = c
    return out


# ---------------------------------------------------------------- session helpers

def legs_max(cfg_path):
    exp = experiment.load(cfg_path)
    last = exp["rounds_max"] if exp.get("adaptive", True) else exp["rounds"]
    return len(experiment.schedule(exp, 1, last))


def _utc(s):
    return time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def seconds_per_leg(smoke_root):
    """Mean seconds from one leg's start to the next over every smoke run under smoke_root."""
    gaps = []
    for d in sorted(os.listdir(smoke_root)):
        p = os.path.join(smoke_root, d, "legs.jsonl")
        if not os.path.exists(p):
            continue
        with open(p) as f:
            ts = [_utc(json.loads(x)["started_utc"]) for x in f if x.strip() and '"started_utc"' in x]
        ts.sort()
        gaps += [b - a for a, b in zip(ts, ts[1:])]
    if not gaps:
        raise SystemExit("no smoke legs with start times under %s" % smoke_root)
    return sum(gaps) / len(gaps), len(gaps)


def budget(smoke_root, out=sys.stdout):
    """Print seconds per leg and each run's worst case (cap rounds, no re-runs); return
    (mandatory worst-case seconds, {run: seconds})."""
    spl, n = seconds_per_leg(smoke_root)
    caps = {}
    out.write("seconds per leg (smoke, %d gaps): %.1f\n" % (n, spl))
    for r in MANDATORY + OPTIONAL:
        lm = legs_max(os.path.join(OUT, r + ".json"))
        caps[r] = lm * spl
        out.write("%-22s %4d legs at the cap  worst case %5.2f h%s\n" % (
            r, lm, caps[r] / 3600, "  (optional)" if r in OPTIONAL else ""))
    mand = sum(caps[r] for r in MANDATORY)
    out.write("mandatory worst case %.2f h (ask the lead above %.2f h); with %s %.2f h; stop at %.0f h\n" % (
        mand / 3600, ASK_LEAD_ABOVE_S / 3600, OPTIONAL[0], (mand + caps[OPTIONAL[0]]) / 3600,
        SESSION_STOP_S / 3600))
    return mand, caps


def has_floor(run_dir):
    """A run counts as a floor when it wrote results and is complete (not aborted early)."""
    p = os.path.join(run_dir, "results.json")
    if not os.path.exists(p):
        return False, "no results.json"
    with open(p) as f:
        md = json.load(f).get("metadata", {})
    if md.get("incomplete") or md.get("aborted"):
        return False, "incomplete (%s complete rounds%s)" % (
            md.get("rounds_complete"), "; %s" % md["aborted"] if md.get("aborted") else "")
    return True, "rounds %s, stop: %s" % (md.get("rounds_complete"), md.get("stop_reason"))


def main(argv):
    cmd = argv[0] if argv and argv[0] in ("write", "budget", "has-floor", "cap") else "write"
    args = argv[1:] if argv and argv[0] == cmd else argv
    if cmd == "budget":
        mand, _ = budget(args[0])
        return 3 if mand > ASK_LEAD_ABOVE_S else 0
    if cmd == "cap":
        # cap RUN SMOKE_ROOT: worst-case seconds of one run, an integer
        spl, _ = seconds_per_leg(args[1])
        print(int(legs_max(os.path.join(OUT, args[0] + ".json")) * spl))
        return 0
    if cmd == "has-floor":
        ok, why = has_floor(args[0])
        print(why)
        return 0 if ok else 1
    rates = {}
    if args:
        with open(args[0]) as f:
            rates = json.load(f)
    os.makedirs(OUT, exist_ok=True)
    for fn, c in configs(rates).items():
        with open(os.path.join(OUT, fn), "w") as f:
            json.dump(c, f, indent=1)
            f.write("\n")
        print(fn)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
