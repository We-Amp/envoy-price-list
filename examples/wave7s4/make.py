#!/usr/bin/env python3
"""Wave 7, session S4: built binaries. Candidate 4 (the OpenTelemetry tracer's deferred span for requests
that are not sampled) and candidate 2 (a PGO + ThinLTO build whose profile comes from Envoy's own tests).
The wave 7 plan, section 5; the build record.

    python3 examples/wave7s4/make.py

Binaries (bins.json; every arm pins its sha256 and the harness refuses a binary that differs):
  official   ~/epl/bin/envoy-1.40.2                       the official v1.40.2 release (the patch's unpatched
                                                          twin is byte-identical to it)
  dfs        ~/epl/bins/wave7s4/envoy-otel-dfs            v1.40.2 + the deferred-span patch, release options
  dfs-sym    ~/epl/bins/wave7s4/envoy-otel-dfs.unstripped the same link before stripping (evidence legs only)
  trainer    ~/epl/bins/wave7s4/envoy-pgolto              wave 2's PGO + ThinLTO build (trainer profile)
  tests      ~/epl/bins/wave7s4/envoy-pgolto-tests        the same options, profile from 12 integration tests
                                                          and 10 benchmark tests

Configs (in configs/); shapes s (4 KB proxied, 5,200 req/s) and fh (109 headers, direct response, 8,000
req/s); shape order rotates by round (shape_order latin):

  s4a-otel.json   8 arms, 8 rounds (one Williams square), seed 731:
                    notrace              official, no tracer (base)
                    stock-0              official, OpenTelemetry tracer, 0% sampling
                    stock-0-A2           the same (A/A)
                    patched-0            dfs, 0% sampling, runtime guard at its default (on)
                    patched-0-guard-off  dfs, 0% sampling, envoy.reloadable_features.otel_tracer_deferred_span
                                         false in the static runtime layer (the control: the build without
                                         the patch's path)
                    stock-1, patched-1   1% sampling on each binary (sampled cost unchanged)
                    patched-notrace      dfs, no tracer (the eighth arm: a Williams square needs an even
                                         arm count; it reads the build's layout shift without a tracer)
  s4b-pgo.json    4 arms, 8 rounds (two Williams squares), seed 732: official (base), official-A2,
                  pgolto-trainer, pgolto-tests
  smoke-*.json    one round of every arm (order fixed), evidence recorded
  ev-span-path.json  non-scored: the unstripped twin at 0% sampling, guard on and guard off, on both shapes,
                  under perf-span.sh (a user-space profile of the Envoy process over the window)
  ev-export.json     non-scored: official and dfs at 100% sampling at 96 req/s; the collector prints every
                  span it receives (collector.debug_spans), compared by span_compare.py
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

RUNS = "~/epl/runs/wave7s4"
HARNESS = "~/epl/harness-wave7s4"
CLIENT = "~/nighthawk-dogfood/bazel-bin/nighthawk_client"  # Nighthawk 0.3.0, md5 310df412
SEEDS = {"s4a": 731, "s4b": 732}
ROUNDS = 8
COLLECTOR = {"image": sm.COLLECTOR, "port": 4317, "metrics_port": 8888}
GUARD = "envoy.reloadable_features.otel_tracer_deferred_span"
# what the tracer adds to the upstream request: "traceparent: " + 55 + CRLF (70) and, with no incoming
# tracestate, an empty "tracestate: " + CRLF (14); read in the local functional check, the same in both binaries
TRACE_HEADER_BYTES = 84

with open(os.path.join(HERE, "bins.json")) as _f:
    BINS = json.load(_f)

Z = {"tol_abs": 0}
ONE = {"per_request": 1.0, "tol": 0.002}
H = "http.ingress_http."
RQ2XX = dict({"stat": "cluster.origin.upstream_rq_2xx", "shape": "s",
              "label": "upstream 2xx 1.000 per request"}, **ONE)
DOWN_2XX = dict({"stat": H + "downstream_rq_2xx", "label": "downstream 2xx 1.000 per request"}, **ONE)
PER_RESP = "field:responses_raw"
TX = "cluster.origin.upstream_cx_tx_bytes_total"
SPANS_SENT = "tracing.opentelemetry.spans_sent"
SAMPLED = H + "tracing.random_sampling"
NOT_TRACEABLE = H + "tracing.not_traceable"
DONE = "leg:" + H + "downstream_rq_completed"


def zero(stat, scope="window", **kw):
    return dict({"stat": stat, "scope": scope, "equals": 0}, **Z, **kw)


def cfg(stat, label, **kw):
    key = kw.pop("key", None)
    return dict({"stat": key or stat, "scope": "config", "label": label}, **kw)


WARM = {"stat": "cluster.origin.upstream_cx_total", "scope": "window", "max": 0.001, "per": PER_RESP, "shape": "s",
        "label": "warm upstream pool: at most 0.001 new connections per request in the window"}
COMMON = [RQ2XX, DOWN_2XX, WARM]
EV_GUARD_DEFAULT = [cfg("layered_runtime", "no runtime layer: the guard is at its default", absent=True),
                    cfg(GUARD, "the guard key is not set", absent=True)]
EV_GUARD_OFF = [cfg(GUARD, "the static runtime layer sets %s false" % GUARD, equals=False),
                {"stat": "runtime.num_keys", "scope": "leg", "equals": 1, "tol_abs": 0,
                 "label": "runtime.num_keys 1: the one key of the static layer is loaded"}]
TX_BASE = {"stat": TX, "shape": "s", "ref": {"arm": "notrace", "offset": 0}, "tol_abs": 0.5,
           "label": "upstream request bytes per request as the no-tracer arm (no traceparent header)"}
TX_TRACE = {"stat": TX, "shape": "s", "ref": {"arm": "notrace", "offset": TRACE_HEADER_BYTES}, "tol_abs": 0.5,
            "label": "upstream request bytes per request = the no-tracer arm + %d (the traceparent header and an "
                     "empty tracestate header reach the origin)" % TRACE_HEADER_BYTES}
EV_TRACE_OFF = [{"stat": SPANS_SENT, "scope": "leg", "absent": True, "label": "no tracer stats"}, zero(SAMPLED),
                zero(NOT_TRACEABLE, label="no tracing decision is made"),
                cfg("otel", "no OpenTelemetry tracer in the config", absent=True, key="@type",
                    where={"@type": envoy_config.OTEL}), TX_BASE]
EV_TRACER = [cfg("otel", "the OpenTelemetry tracer is configured", present=True, key="@type",
                 where={"@type": envoy_config.OTEL}),
             cfg("sampler", "no custom sampler (the path the patch covers)", absent=True),
             zero("cluster.otel_collector.upstream_rq_timeout"), zero("cluster.otel_collector.upstream_cx_connect_fail"),
             TX_TRACE]
REFUSED = {"stat": "collector_delta.refused_spans", "scope": "field", "max": 0, "label": "collector refused no span"}
EV_TRACE_0 = EV_TRACER + [
    zero(SAMPLED, label="no request sampled"),
    dict({"stat": NOT_TRACEABLE, "label": "the tracing decision ran on every request: not_traceable 1.000 per request"}, **ONE),
    zero(SPANS_SENT, "leg", label="spans sent 0 over the leg"),
    # (the collector creates its span counters with the first span, so a 0% leg is shown on Envoy's side)
    zero("cluster.otel_collector.upstream_rq_total", "leg", label="no export request to the collector over the leg")]
EV_TRACE_1 = EV_TRACER + [REFUSED,
    {"stat": SAMPLED, "per_request": 0.01, "tol_binomial_sd": 4, "label": "sampled share within 4 binomial SD of 1%"},
    {"stat": SPANS_SENT, "scope": "leg", "per_request": 1.0, "tol": 0.05, "per": "leg:" + SAMPLED,
     "label": "spans sent per sampled request over the leg"},
    {"stat": "collector_delta.accepted_spans", "scope": "field", "per": "leg:" + SPANS_SENT, "min": 0.95,
     "label": "collector accepted >= 95% of spans sent"},
    {"stat": "collector_delta.accepted_spans", "scope": "field", "per": DONE, "min": 0.007, "max": 0.013,
     "label": "spans accepted by the collector about 1% of requests (0.7% to 1.3%)"}]
EV_TRACE_100 = EV_TRACER[:-1] + [REFUSED,
    dict({"stat": SAMPLED, "label": "every request sampled"}, **ONE),
    # (a worker flushes at five spans or every 5 s, so the last few spans of a leg may still be unsent when the
    # end-of-leg snapshot is read: up to 16 of about 2,900)
    {"stat": SPANS_SENT, "scope": "leg", "per_request": 1.0, "tol": 0.03, "per": DONE,
     "label": "spans sent 1.00 per completed request over the leg (within 3%)"},
    {"stat": "collector_delta.accepted_spans", "scope": "field", "per": DONE, "min": 0.97, "max": 1.01,
     "label": "spans accepted by the collector 0.97 to 1.01 per completed request"}]


def base(name, run, extra_stats=r"^runtime\."):
    b = json.loads(json.dumps(sm.BASE))
    b.pop("floor_from")
    b.pop("stop")
    b["client"]["binary"] = CLIENT
    b["origin"].update(stub_status=True)
    # idleness by load and CPU only: no process is matched by its command line
    b["idle"] = dict(b["idle"], procs=[])
    b["measure"] = dict(b["measure"], stat_filter_extra=extra_stats)
    b.update(workdir=RUNS, name=name, order="williams", order_seed=SEEDS[run], rounds=ROUNDS,
             rounds_block=ROUNDS, rounds_max=ROUNDS, adaptive=False, comparisons="all_pairs", shape_order="latin",
             short_run_note="short run: %d fixed rounds in Williams order, run with --allow-short" % ROUNDS)
    return b


def arm(name, build, settings=None, ev=None):
    b = BINS[build]
    a = {"name": name, "binary": b["binary"], "source": b["source"], "source_sha256": b["source_sha256"], "build": build}
    if settings:
        a["settings"] = settings
    if ev:
        a["evidence"] = copy.deepcopy(ev)
    return a


def tr(pct, **more):
    return dict({"tracing": {"sampling_pct": pct}}, **more)


def s4a_arms():
    return [arm("notrace", "official", None, COMMON + EV_TRACE_OFF + EV_GUARD_DEFAULT),
            arm("stock-0", "official", tr(0), COMMON + EV_TRACE_0 + EV_GUARD_DEFAULT),
            arm("stock-0-A2", "official", tr(0), COMMON + EV_TRACE_0 + EV_GUARD_DEFAULT),
            arm("patched-0", "dfs", tr(0), COMMON + EV_TRACE_0 + EV_GUARD_DEFAULT),
            arm("patched-0-guard-off", "dfs", tr(0, runtime={GUARD: False}), COMMON + EV_TRACE_0 + EV_GUARD_OFF),
            arm("stock-1", "official", tr(1), COMMON + EV_TRACE_1 + EV_GUARD_DEFAULT),
            arm("patched-1", "dfs", tr(1), COMMON + EV_TRACE_1 + EV_GUARD_DEFAULT),
            arm("patched-notrace", "dfs", None, COMMON + EV_TRACE_OFF + EV_GUARD_DEFAULT)]


def s4a(name):
    c = base(name, "s4a")
    S = sm.shapes({})
    c.update(base_arm="notrace", arms=s4a_arms(), shapes=[S["s"], S["fh"]], collector=dict(COLLECTOR),
             confirmatory=[["patched-0", "notrace"], ["stock-0", "notrace"], ["patched-0", "stock-0"],
                           ["patched-0-guard-off", "stock-0"], ["patched-1", "stock-1"], ["patched-notrace", "notrace"]])
    return c


def s4b(name):
    c = base(name, "s4b")
    S = sm.shapes({})
    ev = COMMON + EV_GUARD_DEFAULT
    c.update(base_arm="official", shapes=[S["s"], S["fh"]],
             arms=[arm("official", "official", None, ev), arm("official-A2", "official", None, ev),
                   arm("pgolto-trainer", "trainer", None, ev), arm("pgolto-tests", "tests", None, ev)],
             confirmatory=[["pgolto-trainer", "official"], ["pgolto-tests", "official"], ["pgolto-tests", "pgolto-trainer"]])
    return c


def as_one_round(c):
    c.update(smoke=True, evidence_mode="record", order="fixed", rounds=1, rounds_block=1, rounds_max=1)
    c.pop("short_run_note", None)
    c.pop("confirmatory", None)
    c.pop("shape_order", None)
    return c


def ev_span_path():
    """The builder's on-box procedure (the build record, evidence layer 3): the unstripped twin at 0%
    sampling under load, guard on and guard off, with a user-space profile of the Envoy process."""
    c = as_one_round(base("ev-span-path", "s4a"))
    S = sm.shapes({})
    ev_on = [e for e in COMMON + EV_TRACE_0 + EV_GUARD_DEFAULT if "ref" not in e]
    ev_off = [e for e in COMMON + EV_TRACE_0 + EV_GUARD_OFF if "ref" not in e]
    c.update(base_arm="sym-0", shapes=[S["s"], S["fh"]], collector=dict(COLLECTOR), comparisons="base",
             arms=[arm("sym-0", "dfs-sym", tr(0), ev_on),
                   arm("sym-0-guard-off", "dfs-sym", tr(0, runtime={GUARD: False}), ev_off)])
    c["measure"] = dict(c["measure"], perf="bash %s/examples/wave7s4/perf-span.sh" % HARNESS)
    c["validity"] = dict(c.get("validity") or {}, require_perf_unmultiplexed=False)
    return c


def ev_export():
    """Official and patched at 100% sampling, 96 req/s: the collector prints every span (debug exporter)."""
    c = as_one_round(base("ev-export", "s4a"))
    s100 = dict(sm.shapes({})["s"], name="s96", rps=96)
    ev = [dict(e, shape="s96") if e.get("shape") == "s" else e for e in COMMON + EV_TRACE_100 + EV_GUARD_DEFAULT
          if e is not WARM]
    c.update(base_arm="stock-100", shapes=[s100], collector=dict(COLLECTOR, debug_spans=True), comparisons="base",
             arms=[arm("stock-100", "official", tr(100), ev), arm("patched-100", "dfs", tr(100), ev)])
    return c


def configs():
    return {"s4a-otel": s4a("s4a-otel"), "smoke-s4a-otel": as_one_round(s4a("smoke-s4a-otel")),
            "s4b-pgo": s4b("s4b-pgo"), "smoke-s4b-pgo": as_one_round(s4b("smoke-s4b-pgo")),
            "ev-span-path": ev_span_path(), "ev-export": ev_export()}


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn, c in sorted(configs().items()):
        with open(os.path.join(OUT, fn + ".json"), "w") as f:
            json.dump(c, f, indent=1, sort_keys=True)
            f.write("\n")
        print(fn + ".json")


if __name__ == "__main__":
    main()
