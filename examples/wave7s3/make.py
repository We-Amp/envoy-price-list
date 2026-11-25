#!/usr/bin/env python3
"""Wave 7, session S3: one proxy, the typical config against the lean config (candidate 6), ten inert
filters (candidate 11) and the timer bounds (candidate 7). Config only, on the official v1.40.2 binary
(~/epl/bin/envoy-1.40.2, sha256 enforced) in every arm. The wave 7 plan, section 4.

    python3 examples/wave7s3/make.py

Configs (in configs/):

  s3a-stack.json  shape sx = s (4 KB proxied, 5,200 req/s) with the accept-encoding and authorization request
                  headers of the published compressor and JWT rows, in every arm. Arms: bare (base), bare-A2
                  (A/A at the baseline's load), typical (JSON file access log, OpenTelemetry tracer at 1%,
                  statsd sink over UDP, idle gzip compressor, JWT with the token cache, local rate limit,
                  retry policy), typical-A2 (A/A at the stack's load), typical-nosink (typical without the
                  sink), lean (typical with the text access log and the OpenTelemetry stats sink in place of
                  JSON and statsd). No arm carries generated clusters: every arm runs the plain config's own
                  stats, flushed at Envoy's default 5 s. 6 arms, 6 rounds, Williams order, seed 721.
  s3b-chain.json  shapes s (5,200 req/s) and fh (109 headers, direct response, 8,000 req/s). Arms: f0 (router
                  only; base), f0-A2 (A/A), f10 (the ten inert filters of envoy_config.INERT_FILTERS before
                  the router), f10-off (the same ten, each with `disabled: true`), idle-off (stream idle 0s,
                  downstream connection idle 0s, upstream connection idle 0s; route timeout at its default),
                  timers-off-all (idle-off plus route timeout 0s). 6 arms x 2 shapes, 6 rounds, seed 722.
  smoke-*.json    one round of every arm (order fixed), evidence recorded
  mech-*.json     the non-scored mechanism legs (one round, order fixed): measure.perf is a wrapper
                  (perf-sys.sh: syscall counts; perf-kcg.sh: a system-wide call-graph profile of the Envoy
                  CPUs). Their legs never enter a table of prices.
"""

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "configs")
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "examples", "settings-matrix"))
sys.path.insert(0, ROOT)
import make as sm  # noqa: E402
from epl import envoy_config  # noqa: E402

RUNS = "~/epl/runs/wave7s3"
HARNESS = "~/epl/harness-wave7s3"
CLIENT = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"  # Nighthawk 0.3.0, md5 310df412
SEEDS = {"s3a": 721, "s3b": 722}
ROUNDS = 6
COLLECTOR = {"image": sm.COLLECTOR, "port": 4317, "metrics_port": 8888, "metrics": True}
SINK = {"port": 8125, "rcvbuf": 268435456, "sample_every": 1}
RL_TOKENS_PER_S = 100000  # as the published row: about ten times the highest rate, nothing is rejected

with open(os.path.join(ROOT, "examples", "settings-matrix", "filters", "jwt.json")) as _f:
    JWT = json.load(_f)
JWT_SETTING = {"jwks": JWT["jwks"], "issuer": JWT["issuer"], "audience": JWT["audience"], "cache": True}
# the request headers of the published compressor row (14b) and JWT row (11), in every arm of s3a
SX_HEADERS = ["--request-header", "accept-encoding:gzip, br, zstd",
              "--request-header", "authorization:Bearer " + JWT["token"]]

Z = {"tol_abs": 0}
ONE = {"per_request": 1.0, "tol": 0.002}
RQ2XX = dict({"stat": "cluster.origin.upstream_rq_2xx"}, **ONE)
PER_RESP = "field:responses_raw"


def zero(stat, scope="window", **kw):
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


def warm(mx=0.001, **kw):
    return dict({"stat": "cluster.origin.upstream_cx_total", "scope": "window", "max": mx, "per": PER_RESP,
                 "label": "warm upstream pool: at most %g new connections per request in the window" % mx}, **kw)


def cfg(stat, label, **kw):
    """A config-scope item; `key` (when given) is the key looked up in /config_dump instead of `stat`."""
    key = kw.pop("key", None)
    return dict({"stat": key or stat, "scope": "config", "label": label}, **kw)


def base(name, run, extra_stats=None):
    b = json.loads(json.dumps(sm.BASE))
    b.pop("floor_from")
    b.pop("stop")
    b["client"]["binary"] = CLIENT
    b["origin"].update(stub_status=True)
    # idleness by load and CPU only: no process is matched by its command line
    b["idle"] = dict(b["idle"], procs=[])
    if extra_stats:
        b["measure"] = dict(b["measure"], stat_filter_extra=extra_stats)
    b.update(workdir=RUNS, name=name, order="williams", order_seed=SEEDS[run], rounds=ROUNDS,
             rounds_block=ROUNDS, rounds_max=ROUNDS, adaptive=False, comparisons="all_pairs",
             short_run_note="short run: %d fixed rounds in Williams order, run with --allow-short" % ROUNDS)
    return b


def arm(name, settings=None, ev=None):
    a = sm.arm(name, settings)
    if ev:
        a["evidence"] = copy.deepcopy(ev)
    return a


# ---------------------------------------------------------------- s3a: the stack

LOG_LINES = dict({"stat": "access_log_lines", "scope": "field", "per": "leg:http.ingress_http.downstream_rq_completed",
                  "label": "access-log lines per request completed over the leg"}, **ONE)
EV_LOG_TEXT = [LOG_LINES, zero("filesystem.write_failed", "leg"), zero("filesystem.reopen_failed", "leg"),
               {"stat": "access_log_bytes_per_line", "scope": "field", "min": 1, "label": "bytes per line recorded"},
               cfg("json_format", "access log in Envoy's default text format (no json_format)", absent=True)]
EV_LOG_JSON = EV_LOG_TEXT[:4] + [{"stat": "access_log_json_ok", "scope": "field", "equals": True,
                                  "label": "first and last 100 access-log lines parse as JSON"},
                                 cfg("json_format", "access log with a json_format", present=True)]
EV_LOG_OFF = [{"stat": "access_log_lines", "scope": "field", "absent": True, "label": "no access log file"}]

SPANS_SENT = "tracing.opentelemetry.spans_sent"
SAMPLED = "http.ingress_http.tracing.random_sampling"
EV_TRACE_OFF = [{"stat": SPANS_SENT, "scope": "leg", "absent": True, "label": "no tracer stats"}, zero(SAMPLED)]
EV_TRACE_1 = [
    {"stat": SAMPLED, "per_request": 0.01, "tol_binomial_sd": 4, "label": "sampled share within 4 binomial SD of 1%"},
    zero("cluster.otel_collector.upstream_rq_timeout"), zero("cluster.otel_collector.upstream_cx_connect_fail"),
    {"stat": SPANS_SENT, "scope": "leg", "per_request": 1.0, "tol": 0.05, "per": "leg:" + SAMPLED,
     "label": "spans sent per sampled request over the leg"},
    {"stat": "collector_delta.accepted_spans", "scope": "field", "per": "leg:" + SPANS_SENT, "min": 0.95,
     "label": "collector accepted >= 95% of spans sent"},
    {"stat": "collector_delta.accepted_spans", "scope": "field", "per": "leg:http.ingress_http.downstream_rq_completed",
     "min": 0.007, "max": 0.013, "label": "spans accepted by the collector about 1% of requests (0.7% to 1.3%)"},
    {"stat": "collector_delta.refused_spans", "scope": "field", "max": 0, "label": "collector refused no span"}]

COMP = "http.ingress_http.compressor.epl.gzip.response."
EV_COMP_IDLE = [dict({"stat": COMP + "not_compressed", "label": "compressor: not_compressed 1.000 per request"}, **ONE),
                zero(COMP + "compressed", label="compressor: nothing compressed"),
                zero(COMP[:-len("response.")] + "no_accept_header", label="compressor: every request carried accept-encoding"),
                # the response's content type is not in the filter's list, so the filter is left out of the
                # encoding decision and counts the accept-encoding header as not valid for it (v1.40.2
                # compressor_filter.cc chooseEncoding / shouldCompress): the path of the published row
                dict({"stat": COMP[:-len("response.")] + "header_not_valid",
                      "label": "compressor: the accept-encoding header was read on every response (content type "
                               "not compressible)"}, **ONE)]
EV_COMP_OFF = [{"stat": "http.ingress_http.compressor.*", "absent": True, "label": "no compressor stats"}]

JW = "http.ingress_http.jwt_authn."
EV_JWT = [dict({"stat": JW + "allowed", "label": "jwt_authn: allowed 1.000 per request"}, **ONE),
          dict({"stat": JW + "jwt_cache_hit", "label": "jwt_authn: token cache hit 1.000 per request"}, **ONE),
          zero(JW + "denied", label="jwt_authn: nothing denied"),
          zero(JW + "jwks_fetch_success", scope="leg", label="jwt_authn: no JWKS fetch"),
          zero(JW + "jwks_fetch_failed", scope="leg", label="jwt_authn: no failed JWKS fetch"),
          cfg("jwt_cache_config", "jwt_authn: the token cache is configured", present=True)]
EV_JWT_OFF = [{"stat": JW + "*", "absent": True, "label": "no jwt_authn stats"}]

RL = "http_local_rate_limiter.http_local_rate_limit."
EV_RL = [dict({"stat": RL + "enabled", "label": "local rate limit: enabled 1.000 per request"}, **ONE),
         dict({"stat": RL + "ok", "label": "local rate limit: ok 1.000 per request"}, **ONE),
         zero(RL + "rate_limited", label="local rate limit: nothing limited")]
EV_RL_OFF = [{"stat": RL + "*", "absent": True, "label": "no local rate-limit stats"}]

EV_RETRY = [cfg("retry_policy", "the route carries the retry policy", present=True),
            zero("cluster.origin.upstream_rq_retry", label="no retry in the window")]
EV_RETRY_OFF = [cfg("retry_policy", "no retry policy", absent=True)]

# statsd: the workers send one datagram per recorded histogram value (three per request on this config);
# the flush of the plain config's few hundred stats every 5 s adds under 0.02 per request
EV_STATSD = [{"stat": "udp.datagrams_per_request", "scope": "field", "min": 2.5, "max": 3.5,
              "label": "statsd datagrams per request over the window: 3.0 +/- 0.5 (kernel UDP counters of the "
                       "harness's sink)"},
             cfg("stats_sinks", "a stats sink is configured", present=True),
             cfg("statsd", "the sink is the plain statsd sink", present=True, key="@type",
                 where={"@type": envoy_config.STATSD})]
NO_UDP = {"stat": "kernel_net.d.UdpOutDatagrams", "scope": "field", "max": 0.01, "per": PER_RESP,
          "label": "no statsd traffic: box-wide UDP datagrams sent per request at most 0.01"}
EV_NOSINK = [cfg("stats_sinks", "no stats sink configured", absent=True), NO_UDP]
EV_OTLP = [cfg("stats_sinks", "a stats sink is configured", present=True),
           cfg("otlp", "the sink is the OpenTelemetry sink", present=True, key="@type",
               where={"@type": envoy_config.OTLP_SINK}),
           {"stat": "collector_delta.accepted_metric_points", "scope": "field", "min": 1,
            "label": "the collector accepted metric points over the leg (> 0)"},
           {"stat": "collector_delta.refused_metric_points", "scope": "field", "max": 0,
            "label": "the collector refused no metric point"},
           NO_UDP]
NO_GEN = cfg("epl-prime", "no generated clusters (no priming route)", absent=True, key="cluster_header")
COMMON = [RQ2XX, warm(), NO_GEN]

TYPICAL = {"access_log": {"format": "json"}, "tracing": {"sampling_pct": 1}, "stats_sink": {"kind": "statsd"},
           "compressor": {"library": "gzip"}, "jwt_authn": dict(JWT_SETTING),
           "local_ratelimit": {"tokens_per_s": RL_TOKENS_PER_S}, "retries": True}
NOSINK = {k: v for k, v in TYPICAL.items() if k != "stats_sink"}
LEAN = dict(NOSINK, access_log={"format": "text"}, stats_sink={"kind": "otlp"})
EV_FEATURES = EV_TRACE_1 + EV_COMP_IDLE + EV_JWT + EV_RL + EV_RETRY
EV_BARE = COMMON + EV_LOG_OFF + EV_TRACE_OFF + EV_COMP_OFF + EV_JWT_OFF + EV_RL_OFF + EV_RETRY_OFF + EV_NOSINK
EV_TYPICAL = COMMON + EV_LOG_JSON + EV_FEATURES + EV_STATSD
EV_TYPICAL_NOSINK = COMMON + EV_LOG_JSON + EV_FEATURES + EV_NOSINK
EV_LEAN = COMMON + EV_LOG_TEXT + EV_FEATURES + EV_OTLP


def sx_shape():
    return dict(sm.shapes({})["s"], name="sx", client_extra_args=list(SX_HEADERS))


def s3a_arms():
    return [arm("bare", None, EV_BARE), arm("bare-A2", None, EV_BARE),
            arm("typical", TYPICAL, EV_TYPICAL), arm("typical-A2", TYPICAL, EV_TYPICAL),
            arm("typical-nosink", NOSINK, EV_TYPICAL_NOSINK), arm("lean", LEAN, EV_LEAN)]


def s3a(name):
    c = base(name, "s3a")
    c["measure"] = dict(c["measure"], kernel_net=True)
    c.update(base_arm="bare", arms=s3a_arms(), shapes=[sx_shape()], collector=dict(COLLECTOR), stats_sink=dict(SINK),
             confirmatory=[["typical", "bare"], ["typical-nosink", "bare"], ["lean", "bare"], ["lean", "typical"]])
    return c


# ---------------------------------------------------------------- s3b: inert filters and timers

# (short name, type URL): /config_dump also lists every extension of the binary by name, so a filter in the
# chain is recognised by the type URL of its typed_config
INERT = [(n.rsplit(".", 1)[-1], c["@type"]) for n, c in envoy_config.INERT_FILTERS]
# every counter of the ten filters that would show an action (names read from the local functional check's
# /stats); the bandwidth filter's stats sit under its own prefix, outside the harness's fixed stats filter
S3B_STATS = r"^epl_inert\."
H = "http.ingress_http."
INERT_ACTION = [H + "fault.aborts_injected", H + "fault.delays_injected", H + "fault.response_rl_injected",
                H + "rbac.denied", H + "rbac.shadow_denied", H + "csrf.request_invalid", H + "csrf.missing_source_origin",
                H + "cors.origin_valid", H + "cors.origin_invalid",
                H + "health_check.request_total", H + "rbac.allowed", H + "csrf.request_valid",
                "epl_inert.http_bandwidth_limit.request_enforced", "epl_inert.http_bandwidth_limit.response_enforced"]
RQ2XX_S = dict(RQ2XX, shape="s")
DOWN_2XX = dict({"stat": H + "downstream_rq_2xx", "label": "downstream 2xx 1.000 per request"}, **ONE)
IDLE_OFF = {"idle_timers_off": True, "upstream_http": {"idle_timeout_s": 0}}
TIMERS_OFF_ALL = dict(IDLE_OFF, route_timeout_s=0)

CHAIN_NONE = [cfg("inert", "no inert filter in the chain (%s)" % n, absent=True, key="@type", where={"@type": t})
              for n, t in INERT] + \
             [cfg("disabled", "no filter entry is disabled", absent=True)]
CHAIN_TEN = [cfg("inert", "the chain lists %s" % n, present=True, key="@type", where={"@type": t}) for n, t in INERT]
ACTION_ZERO = [zero(s, scope="leg", label="no action: %s 0 over the leg" % s) for s in INERT_ACTION]
CHAIN_ON = CHAIN_TEN + [cfg("disabled", "no filter entry is disabled", absent=True)] + ACTION_ZERO
CHAIN_OFF = CHAIN_TEN + [cfg("disabled", "every one of the ten entries carries disabled: true", equals=True)] + \
            [cfg("disabled", "disabled: true on %s" % n, equals=True, where={"name": "envoy.filters.http." + n})
             for n, _ in INERT]
TIMERS_DEFAULT = [cfg("stream_idle_timeout", "stream idle timeout at its default", absent=True),
                  cfg("common_http_protocol_options", "connection idle timeouts at their defaults", absent=True),
                  cfg("timeout", "route timeout at its default (not set)", absent=True)]
TIMERS_IDLE_OFF = [cfg("stream_idle_timeout", "stream idle timeout 0s", equals="0s"),
                   cfg("common_http_protocol_options", "connection idle timeout 0s wherever it is set (listener and "
                       "origin cluster)", equals={"idle_timeout": "0s"}),
                   cfg("explicit_http_config", "the origin cluster carries its own protocol options (upstream idle "
                       "timeout)", present=True)]
ROUTE_DEFAULT = [cfg("timeout", "route timeout at its default (not set)", absent=True)]
ROUTE_OFF = [cfg("timeout", "route timeout 0s on the proxied route", equals="0s")]
S3B_COMMON = [RQ2XX_S, DOWN_2XX, warm(shape="s"),
              zero(H + "downstream_cx_idle_timeout", "leg"), zero(H + "downstream_rq_idle_timeout", "leg"),
              zero(H + "downstream_rq_timeout", "leg", label="no request timed out")]


def s3b_arms():
    return [arm("f0", None, S3B_COMMON + CHAIN_NONE + TIMERS_DEFAULT),
            arm("f0-A2", None, S3B_COMMON + CHAIN_NONE + TIMERS_DEFAULT),
            arm("f10", {"inert_filters": True}, S3B_COMMON + CHAIN_ON + TIMERS_DEFAULT),
            arm("f10-off", {"inert_filters": {"disabled": True}}, S3B_COMMON + CHAIN_OFF + TIMERS_DEFAULT),
            arm("idle-off", IDLE_OFF, S3B_COMMON + CHAIN_NONE + TIMERS_IDLE_OFF + ROUTE_DEFAULT),
            arm("timers-off-all", TIMERS_OFF_ALL, S3B_COMMON + CHAIN_NONE + TIMERS_IDLE_OFF + ROUTE_OFF)]


def s3b(name):
    c = base(name, "s3b", extra_stats=S3B_STATS)
    S = sm.shapes({})
    c.update(base_arm="f0", arms=s3b_arms(), shapes=[S["s"], S["fh"]],
             confirmatory=[[a, "f0"] for a in ("f10", "f10-off", "idle-off", "timers-off-all")])
    return c


# ---------------------------------------------------------------- mechanism legs (non-scored)

def as_mech(c, name, wrapper):
    c.update(name=name, smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1,
             comparisons="base")
    c.pop("short_run_note", None)
    c.pop("confirmatory", None)
    c["measure"] = dict(c["measure"], perf="bash %s/examples/wave7s3/%s" % (HARNESS, wrapper))
    # a profiler runs beside these legs: its CPU time is not Envoy's, and nothing here is scored
    c["validity"] = dict(c.get("validity") or {}, require_perf_unmultiplexed=False)
    return c


def mech(name, src, picks, wrapper, shapes=None):
    """One round, fixed order, of some arms (and shapes) of a scored config, under a perf wrapper."""
    c = copy.deepcopy(src)
    arms = {a["name"]: a for a in c["arms"]}
    c["arms"] = [copy.deepcopy(arms[n]) for n in picks]
    c["base_arm"] = picks[0]
    if shapes:
        c["shapes"] = [x for x in c["shapes"] if x["name"] in shapes]
        for a in c["arms"]:
            a["evidence"] = [it for it in a.get("evidence", []) if it.get("shape") is None or it["shape"] in shapes]
    return as_mech(c, name, wrapper)


def configs():
    out = {"s3a-stack": s3a("s3a-stack"), "smoke-s3a-stack": s3a("smoke-s3a-stack"),
           "s3b-chain": s3b("s3b-chain"), "smoke-s3b-chain": s3b("smoke-s3b-chain")}
    for k, c in out.items():
        if k.startswith("smoke-"):
            c.update(smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1)
            c.pop("short_run_note", None)
            c.pop("confirmatory", None)
    # the mechanism pipeline's own smoke (two legs of each kind on the plain shape, before any scored leg)
    out["smoke-mech-sys"] = mech("smoke-mech-sys", out["s3b-chain"], ["f0", "f10"], "perf-sys.sh", ["s"])
    out["smoke-mech-kcg"] = mech("smoke-mech-kcg", out["s3b-chain"], ["f0", "f10"], "perf-kcg.sh", ["s"])
    # Plan 4.4: syscall legs bare and typical on sx; profiles typical/sx, f0/s, f0/fh. The harness wants two
    # arms in every shape: bare runs beside typical in the profile, f10 beside f0.
    out["mech-sys-stack"] = mech("mech-sys-stack", out["s3a-stack"], ["bare", "typical"], "perf-sys.sh")
    out["mech-kcg-stack"] = mech("mech-kcg-stack", out["s3a-stack"], ["bare", "typical"], "perf-kcg.sh")
    out["mech-kcg-chain"] = mech("mech-kcg-chain", out["s3b-chain"], ["f0", "f10"], "perf-kcg.sh")
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn, c in sorted(configs().items()):
        with open(os.path.join(OUT, fn + ".json"), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
        print(fn + ".json")


if __name__ == "__main__":
    main()
