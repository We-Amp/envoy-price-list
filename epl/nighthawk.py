"""Nighthawk client arguments and output parsing."""

import json

# Counters that mean the client did not send what it was asked to send.
OVERFLOW_COUNTERS = (
    "benchmark.pool_overflow",
    "benchmark.pool_connection_failure",
    "upstream_rq_pending_overflow",
    "upstream_cx_overflow",
    "upstream_cx_pool_overflow",
    "benchmark.stream_resets",
    # a connect that failed or timed out (churn shapes: an exhausted port range or a full
    # conntrack table shows here first); zero on every clean leg of any shape
    "upstream_cx_connect_fail",
    "upstream_cx_connect_timeout",
)
NON2XX_COUNTERS = ("benchmark.http_1xx", "benchmark.http_3xx", "benchmark.http_4xx",
                   "benchmark.http_5xx", "benchmark.http_xxx")


def per_worker_rps(total_rps, workers):
    """The per-worker --rps for a planned total rate. By design, Nighthawk gets no
    total-rate option, so a total the client's worker count does not divide is refused (ValueError), never
    rounded; the offered total is always --rps x --concurrency exactly."""
    try:
        w = int(workers)
        t = float(total_rps)
    except (TypeError, ValueError):
        raise ValueError("planned rate %r / client workers %r: not numbers" % (total_rps, workers))
    if w < 1 or t <= 0 or t != int(t):
        raise ValueError("planned rate %r with %r client workers: need a whole total rate > 0 and >= 1 worker"
                         % (total_rps, workers))
    if int(t) % w:
        lo, hi = int(t) // w * w, (int(t) // w + 1) * w
        raise ValueError("planned total rate %d is not divisible by the %d client workers (Nighthawk takes --rps "
                         "per worker and has no total-rate option): use %d or %d, or a worker count that divides "
                         "%d" % (int(t), w, lo, hi, int(t)))
    return int(t) // w


def multi_target_args(scheme, port, path, mt):
    """The target arguments that replace the URI when a leg spreads its connections over several
    loopback destination addresses: one --multi-target-endpoint per address (Nighthawk's one
    cluster per client worker, round robin over the hosts), the path, and HTTPS for TLS arms.
    mt = {"count": N, "base": "127.0.0.1"}: addresses base, base+1, ... (all inside 127/8)."""
    import ipaddress
    n = int(mt.get("count", 0))
    if n < 1:
        raise ValueError("multi_target.count must be at least 1")
    first = ipaddress.IPv4Address(mt.get("base", "127.0.0.1"))
    last = first + (n - 1)
    lo = ipaddress.IPv4Network("127.0.0.0/8")
    if first not in lo or last not in lo:
        raise ValueError("multi_target addresses must stay inside 127.0.0.0/8")
    args = []
    for i in range(n):
        args += ["--multi-target-endpoint", "%s:%d" % (first + i, int(port))]
    args += ["--multi-target-path", path]
    if scheme == "https":
        args.append("--multi-target-use-https")
    return args


PHASE_KEYS = ("warm_s", "measure_cap_s", "boundary_allow_s", "min_lead_in_s")
PHASE_DEFAULTS = {"boundary_allow_s": 1.0, "min_lead_in_s": 1.0}
WARM, MEASURE = "warm", "measure"


def phase_settings(client_cfg):
    """client.phases (recipe "phases") with its defaults: {warm_s, measure_cap_s, boundary_allow_s,
    min_lead_in_s}."""
    p = dict(PHASE_DEFAULTS)
    p.update(client_cfg.get("phases") or {})
    return p


def phase_vector(total_rps, workers, warm_s, measure_s):
    """The --phases vector of the phases recipe: one warm phase, then one measure phase, both at the
    shape's total rate over the same workers (the same concurrency keeps the warm phase's connections for the
    measure phase). `requests_per_second` is the phase's total; the divisibility rule (no total-rate
    option) holds per phase: phase_rate_errors refuses a total the phase's workers do not divide."""
    w = str(int(workers))
    return [{"name": WARM, "duration": "%ds" % int(warm_s), "requests_per_second": int(total_rps), "concurrency": w},
            {"name": MEASURE, "duration": "%ds" % int(measure_s), "requests_per_second": int(total_rps),
             "concurrency": w}]


def phase_rate_errors(phases, workers):
    """The per-phase divisibility rule: each phase's
    requests_per_second must be divisible by that phase's worker count (the phase's own `workers` or
    `concurrency`, else the run's), checked with per_worker_rps. epl.experiment.phase_rate_errors is this."""
    errs = []
    for i, ph in enumerate(phases or []):
        name = ph.get("id") or ph.get("name") or "#%d" % i
        try:
            per_worker_rps(ph.get("requests_per_second"), ph.get("workers") or ph.get("concurrency") or workers)
        except ValueError as ex:
            errs.append("phase %s: %s" % (name, ex))
    return errs


def client_args(client_cfg, total_rps, url, duration_s, json_out, shape_extra=None, base_extra=None, phases=None):
    """`url` is a URI string, or a list of target arguments (multi_target_args) that replaces it.
    `duration_s` None: `--no-duration` (client.lifetime "window": the harness ends the run with one SIGTERM
    after the window's last read; Nighthawk then cancels, still prints its output and exits 0).
    `phases`: a phase vector (phase_vector). Nighthawk refuses --rps, --concurrency, --duration and
    --no-duration beside --phases, so they are left out (the vector carries each phase's rate, workers and
    length); every phase's rate is checked against its workers first (ValueError)."""
    conc = int(client_cfg.get("concurrency", 4))
    if phases is not None:
        errs = phase_rate_errors(phases, conc)
        if errs:
            raise ValueError("; ".join(errs))
        args = ["--connections", str(int(client_cfg.get("connections_per_worker", 16))),
                "--phases", json.dumps(phases, separators=(",", ":"))]
    else:
        args = [
            "--rps", str(per_worker_rps(total_rps, conc)),
            "--connections", str(int(client_cfg.get("connections_per_worker", 16))),
            "--concurrency", str(conc),
        ]
        args += ["--no-duration"] if duration_s is None else ["--duration", str(int(duration_s))]
    args += [
        "--sequencer-idle-strategy", client_cfg.get("idle_strategy", "poll"),
    ]
    if client_cfg.get("open_loop", True):
        args.append("--open-loop")
    if json_out:
        args += ["--output-format", "json"]
    # a shape may replace the experiment's client arguments (base_extra), e.g. to drop
    # prefetch and LRU reuse so that connection churn is spread out in time
    args += list(client_cfg.get("extra_args", []) if base_extra is None else base_extra)
    args += list(shape_extra or [])  # per-shape client settings (TLS parameters, connection churn, h2)
    if isinstance(url, (list, tuple)):
        args += list(url)
    else:
        args.append(url)
    return args


def _dur_s(txt):
    return float(str(txt).rstrip("s"))


def is_phase_result(r):
    """A per-phase result of a --phases run (the fork's phase_<i>_<name> results carry phase_id)."""
    return bool(r.get("phase_id"))


def parse_output(path, measure_phase=None):
    """Extract counters, rate and latency from a Nighthawk JSON file.

    A --phases run: the per-phase results (phase_<i>_<name>, with phase_id) are never counted as workers;
    with `measure_phase` (its name), the client figures come from that phase only: latency and the sequencer
    statistics from its result (merged over the workers), and the response count and rate from its phase_metadata
    `completed` over its execution_duration. `completed` counts every completion whatever its status:
    `responses_2xx` then equals the measure phase's 2xx only while the run-wide non-2xx count
    is 0 (the non-2xx gate), so a phase parse also returns it as `measure_completed`, and `responses_basis` names
    the source. The run's global counters stay run-wide (overflow and non-2xx
    gates cover the whole run). Without phases the output is parsed exactly as before."""
    with open(path) as f:
        d = json.load(f)
    g = [r for r in d["results"] if r["name"] == "global"][0]
    counters = {c["name"]: int(c["value"]) for c in g.get("counters", [])}
    duration = _dur_s(g.get("execution_duration", "0s"))
    phase_results = [r for r in d["results"] if is_phase_result(r)]
    plain = [r for r in d["results"] if not is_phase_result(r)]
    src = g
    mres = None
    if measure_phase is not None:
        mres = next((r for r in phase_results if r.get("phase_id") == measure_phase), None)
        src = mres if mres is not None else {"statistics": []}
    lat = {}
    count = 0
    mean_us = max_us = None
    maxes = {}
    for st in src.get("statistics", []):
        if st["id"] in ("benchmark_http_client.queue_to_connect", "sequencer.callback") and "max" in st:
            maxes[st["id"]] = _dur_s(st["max"]) * 1e6
        if st["id"] != "benchmark_http_client.request_to_response":
            continue
        count = int(st.get("count", 0))
        if "mean" in st:
            mean_us = _dur_s(st["mean"]) * 1e6
        if "max" in st:
            max_us = _dur_s(st["max"]) * 1e6
        for pc in st.get("percentiles", []):
            p = float(pc["percentile"])
            for t in (0.5, 0.9, 0.99, 0.999):
                if t not in lat and p >= t:
                    lat[t] = _dur_s(pc["duration"]) * 1e6
    worker_max = []
    for r in plain:
        if r["name"] == "global":
            continue
        for st in r.get("statistics", []):
            if st["id"] == "benchmark_http_client.request_to_response" and "max" in st:
                worker_max.append(round(_dur_s(st["max"]) * 1e6, 1))
    v = d.get("version", {}).get("version", {})
    # each worker's own execution interval (wall clock start, rate limiter elapsed) and its sequencer
    # statistics; a single-worker run has only the global result, which then stands for its worker. In a phase
    # run every worker's result is its last phase's (its rate limiter and sequencer), so the measure phase.
    execs, seq = [], {}
    for r in plain:
        if r["name"] == "global" and len(plain) > 1:
            continue
        execs.append({"name": r["name"], "start_wall_s": parse_timestamp(r.get("execution_start")),
                      "duration_s": _dur_s(r.get("execution_duration", "0s"))})
        seq[r["name"]] = _seq_stats(r)
    if measure_phase is not None:
        # the measure phase's sequencer statistics (merged over its workers by the client)
        seq = {"phase:" + str(measure_phase): _seq_stats(mres)} if mres is not None else {}
    blk = [s.get("blocking_count") for s in seq.values() if s.get("blocking_count") is not None]
    cbm = [s.get("callback_max_us") for s in seq.values() if s.get("callback_max_us") is not None]
    bkm = [s.get("blocking_max_us") for s in seq.values() if s.get("blocking_max_us") is not None]
    resp_2xx = counters.get("benchmark.http_2xx", 0)
    rate = resp_2xx / duration if duration else 0.0
    phases = None
    if phase_results or d.get("phase_metadata") or measure_phase is not None:
        phases = {"metadata": [_phase_md(x) for x in d.get("phase_metadata") or []],
                  "results": [{"name": r["name"], "phase_id": r.get("phase_id"),
                               "duration_s": _dur_s(r.get("execution_duration", "0s"))} for r in phase_results],
                  "measure": measure_phase}
        if measure_phase is not None:
            mmd = next((x for x in phases["metadata"] if x["phase_id"] == measure_phase), None)
            mdur = _dur_s(mres.get("execution_duration", "0s")) if mres is not None else 0.0
            done = mmd["completed"] if mmd else None
            phases.update(measure_duration_s=mdur, measure_completed=done,
                          responses_basis="measure phase completed (every status; the 2xx count while the run-wide "
                                          "non-2xx count is 0)")
            # the measure phase's own figures (the global counters cover both phases)
            resp_2xx = done or 0
            duration = mdur
            rate = done / mdur if done is not None and mdur else 0.0
    out = {
        "worker_exec": execs,
        "execution_start_wall_s": parse_timestamp(g.get("execution_start")),
        "sequencer": {"per_worker": seq, "blocking_count_total": sum(blk) if blk else None,
                      "blocking_max_us": max(bkm) if bkm else None,
                      "callback_max_us": max(cbm) if cbm else None},
        "graceful_stop_requested": counters.get("graceful_stop_requested", 0),
        "failed_terminations": counters.get("sequencer.failed_terminations", 0),
        "pending_total": counters.get("upstream_rq_pending_total"),
        "cx_total": counters.get("upstream_cx_total"),
        "workers": len(worker_max) or None,
        "worker_r2r_max_us": worker_max,
        "queue_to_connect_max_us": maxes.get("benchmark_http_client.queue_to_connect"),
        "callback_max_us": maxes.get("sequencer.callback"),
        "counters": counters,
        "execution_duration_s": duration,
        "responses_2xx": resp_2xx,
        "rate_2xx": rate,
        "overflow": {k: counters[k] for k in OVERFLOW_COUNTERS if counters.get(k)},
        "non2xx": {k: counters[k] for k in NON2XX_COUNTERS if counters.get(k)},
        "latency_us": {"p50": lat.get(0.5), "p90": lat.get(0.9), "p99": lat.get(0.99),
                       "p999": lat.get(0.999), "mean": mean_us, "max": max_us, "count": count},
        "client_version": "%s.%s.%s" % (v.get("major_number"), v.get("minor_number"), v.get("patch")),
    }
    if phases is not None:
        out["phases"] = phases
        if measure_phase is not None:
            out["measure_completed"] = phases.get("measure_completed")
            out["responses_basis"] = phases.get("responses_basis")
    return out


def _seq_stats(r):
    s = {}
    for st in (r or {}).get("statistics", []):
        if st["id"] in ("sequencer.blocking", "sequencer.callback"):
            k = st["id"].split(".", 1)[1]
            s[k + "_count"] = int(st.get("count", 0))
            s[k + "_max_us"] = _dur_s(st["max"]) * 1e6 if "max" in st else None
    return s


def _phase_md(x):
    """One phase_metadata entry (proto JSON: uint64 as strings, default values left out)."""
    i = lambda k: int(x.get(k) or 0)  # noqa: E731
    return {"phase_id": x.get("phase_id"), "phase_index": i("phase_index"), "worker_count": i("worker_count"),
            "initiated": i("initiated"), "completed": i("completed"), "reset_or_timed_out": i("reset_or_timed_out"),
            "gate_exceeded": i("gate_exceeded"), "completion_ratio": x.get("completion_ratio"),
            "drain_s": _dur_s(x.get("drain_duration", "0s")), "idle_gap_s": _dur_s(x.get("idle_gap", "0s")),
            "workers_changed_vs_prior_phase": bool(x.get("workers_changed_vs_prior_phase")),
            "new_workers_cold_started": bool(x.get("new_workers_cold_started")),
            "drain_censored": bool(x.get("drain_censored")),
            "connections_created": sum(int(p.get("connections_created") or 0) for p in x.get("pool_health") or [])}


# ---------------------------------------------------------------- the client's lifetime and the window

# Marks a leg record written by a harness with the client-window checks (client-sending check, in-window
# per-request denominators, client self-check fields). Analysis code switches on it, so legs recorded
# before those checks keep the denominators they were published with. The value "n1" is a record format id.
N1_MARK = "n1"
LIFETIMES = ("duration", "window")


def parse_timestamp(txt):
    """Seconds since the epoch from a protobuf JSON Timestamp ("2026-11-25T14:04:37.984152Z", any number
    of fraction digits, or an explicit +hh:mm offset); None when missing or not a timestamp."""
    import calendar
    import re
    if not txt or not isinstance(txt, str):
        return None
    m = re.match(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)$", txt.strip())
    if not m:
        return None
    y, mo, d, h, mi, s, frac, tz = m.groups()
    t = calendar.timegm((int(y), int(mo), int(d), int(h), int(mi), int(s), 0, 0, 0))
    if frac:
        t += int(frac) / 10.0 ** len(frac)
    if tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        t -= sign * (int(tz[1:3]) * 3600 + int(tz[4:6]) * 60)
    return t


def arg_value(args, flag):
    """The value after `flag` in an argument list (the last one), or None."""
    v = None
    for i, a in enumerate(args or []):
        if a == flag and i + 1 < len(args):
            v = args[i + 1]
        elif isinstance(a, str) and a.startswith(flag + "="):
            v = a.split("=", 1)[1]
    return v


def ramp_s(args):
    """The linear ramp of a client argument list (the LinearRampingRateLimiter plugin's ramp_time), or 0."""
    import re
    for a in args or []:
        if isinstance(a, str) and "LinearRampingRateLimiterConfig" in a:
            m = re.search(r'"ramp_time"\s*:\s*"([0-9.]+)s"', a)
            if m:
                return float(m.group(1))
    return 0.0


def steady_rate(responses_2xx, execution_s, ramp):
    """The full-rate part's 2xx rate: 2xx / (execution - ramp / 2). A linear ramp from 0 sends half its
    length's worth of requests, so this equals Nighthawk's own rate when there is no ramp."""
    span = (execution_s or 0.0) - (ramp or 0.0) / 2.0
    return responses_2xx / span if span > 0 else None


def per_request_rate(m):
    """The request rate any per-request figure divides by: the SUT's own 2xx count inside the
    window over the window (sut_rate_2xx). Never the client's run-wide rate_2xx, whose execution covers the
    ramp and, under client.lifetime "window", the time after the window. None without a window count."""
    r = m.get("sut_rate_2xx")
    return r if r else None


def sending_check(lifetime, workers_exec, mono_minus_wall_s, t_window_start, t_last_read, ramp, margin_s,
                  alive_at_last_read, exit_code=None, graceful_stops=0, failed_terminations=0, workers=None):
    """Fail-closed evidence that the client sent at full rate over the whole window.

    workers_exec: [{"name", "start_wall_s", "duration_s"}] from the client's own output (each worker's rate
    limiter start and elapsed time). mono_minus_wall_s converts the wall clock to the harness's monotonic
    clock (from a clock pair read when the client started). The window runs from t_window_start (the first
    count read) to t_last_read (the end of the last count read), both monotonic.

    Every check must hold:
    - the client process was alive when the last count read ended;
    - every worker's own execution ends at least margin_s after the last read (min over workers);
    - every worker's ramp ended before the window's first read (max over workers of start + ramp);
    - with workers > 1: one result per configured worker in the output;
    - lifetime "window": exit code 0, the run ended by the harness's SIGTERM (graceful_stop_requested set,
      one per worker) and not by a failure predicate (sequencer.failed_terminations 0)."""
    why = []
    out = {"lifetime": lifetime, "margin_s": margin_s, "ramp_s": ramp}
    if not alive_at_last_read:
        why.append("client had exited before the window's last read ended")
    ws = [w for w in workers_exec or [] if w.get("start_wall_s") is not None and w.get("duration_s")]
    if workers and workers > 1 and len(workers_exec or []) != workers:
        # the worker count is the configured one, not the count that reported latency
        why.append("client output has %d worker results for %d workers" % (len(workers_exec or []), workers))
    if not ws or len(ws) < len(workers_exec or []) or mono_minus_wall_s is None:
        why.append("no execution start/duration for every client worker in the client output")
    else:
        starts = [w["start_wall_s"] + mono_minus_wall_s for w in ws]
        ends = [s + w["duration_s"] for s, w in zip(starts, ws)]
        out["first_end_after_last_read_s"] = round(min(ends) - t_last_read, 4)
        out["last_ramp_end_before_window_s"] = round(t_window_start - (max(starts) + (ramp or 0.0)), 4)
        if min(ends) < t_last_read + margin_s:
            why.append("a client worker stopped %.3f s after the window's last read (need >= %.3f s)"
                       % (min(ends) - t_last_read, margin_s))
        if max(starts) + (ramp or 0.0) > t_window_start:
            why.append("a client worker's ramp ended %.3f s after the window's first read"
                       % (max(starts) + (ramp or 0.0) - t_window_start))
    if lifetime == "window":
        out.update(exit_code=exit_code, graceful_stop_requested=graceful_stops,
                   failed_terminations=failed_terminations)
        if exit_code != 0:
            why.append("client exit code %s after SIGTERM (want 0)" % exit_code)
        if not graceful_stops or (workers and graceful_stops < workers):
            why.append("client output shows graceful_stop_requested %s for %s workers: the run did not end by "
                       "the harness's SIGTERM" % (graceful_stops, workers))
        if failed_terminations:
            why.append("client ended on a failure predicate (sequencer.failed_terminations %d)" % failed_terminations)
    out["ok"] = not why
    out["reasons"] = why
    return out


def phase_check(nhp, phases, workers, workers_exec, mono_minus_wall_s, t_window_start, min_lead_in_s,
                cx_expected=None):
    """Fail-closed evidence that a --phases leg ran the planned phases and that the window lies inside the
    measure phase with its lead-in. Every check must hold:
    - phase_metadata lists the planned phases in order, and a result exists for every phase;
    - every phase ran on the planned workers, with no worker set change, no cold start, no censored drain and no
      start refused by a per-phase gate;
    - the measure phase (every worker's result is its last phase's) began at least min_lead_in_s before the
      window's first read, on every worker (the lead-in counted from the warm-to-measure boundary);
    - with prefetch (cx_expected), the run opened exactly that many connections: the warm phase's connections
      served the measure phase.
    The rest of the window (the measure phase alive at the last read and after it, the ramp) is
    sending_check's, on the same worker results."""
    why = []
    ph = (nhp or {}).get("phases") or {}
    md = ph.get("metadata") or []
    want = [p["name"] for p in phases]
    out = {"planned": want, "workers": workers, "min_lead_in_s": min_lead_in_s, "cx_expected": cx_expected,
           "cx_total": (nhp or {}).get("cx_total"), "metadata": md,
           # recorded, not gated (a warm-phase reset is outside the window; a measure-phase
           # reset also shows in the run-wide counters, which the overflow gate covers)
           "reset_or_timed_out": {x.get("phase_id"): x.get("reset_or_timed_out") for x in md}}
    got = [x.get("phase_id") for x in md]
    if got != want:
        why.append("phase_metadata lists %s, planned %s" % (got, want))
    res = {r.get("phase_id") for r in ph.get("results") or []}
    miss = [n for n in want if n not in res]
    if miss:
        why.append("no per-phase result for %s" % miss)
    for x in md:
        n = x.get("phase_id")
        if workers and x.get("worker_count") != int(workers):
            why.append("phase %s ran on %s workers, planned %s" % (n, x.get("worker_count"), workers))
        for k, what in (("workers_changed_vs_prior_phase", "its worker set changed"),
                        ("new_workers_cold_started", "workers cold-started at its start"),
                        ("drain_censored", "its ending drain was censored")):
            if x.get(k):
                why.append("phase %s: %s" % (n, what))
        if x.get("gate_exceeded"):
            why.append("phase %s: %d starts refused by a per-phase gate" % (n, x["gate_exceeded"]))
    ws = [w for w in workers_exec or [] if w.get("start_wall_s") is not None]
    if not ws or mono_minus_wall_s is None:
        why.append("no measure-phase start for the client workers")
    else:
        start = max(w["start_wall_s"] for w in ws) + mono_minus_wall_s
        out["measure_lead_in_s"] = round(t_window_start - start, 4)
        if t_window_start - start < min_lead_in_s:
            why.append("the measure phase began %.3f s before the window's first read on its last worker "
                       "(need >= %.3f s)" % (t_window_start - start, min_lead_in_s))
    if cx_expected is not None and out["cx_total"] != cx_expected:
        why.append("the client opened %s connections, expected %d (warm connections carried into the measure "
                   "phase)" % (out["cx_total"], cx_expected))
    out["ok"] = not why
    out["reasons"] = why
    return out


def client_signature(args, url, md5=None):
    """A client argument list without what may differ between a calibration leg and the legs it calibrates: the
    --rps value and the target (the URI, or the multi-target arguments at the end). With the
    client binary's pinned md5, the signature starts with "md5:<md5>", so a floor taken with one client binary
    never applies to a leg of another (without a pin the signature is the unpinned one)."""
    a = list(args or [])
    tail = len(url) if isinstance(url, (list, tuple)) else 1
    a = a[:len(a) - tail] if tail <= len(a) else []
    out, skip, phases_next = [], False, False
    for x in a:
        if skip:
            skip = False
            continue
        if phases_next:
            # the phase vector without its rates (a zero-load floor runs the same phases at its own rate)
            phases_next = False
            out.append(_phases_without_rate(x))
            continue
        if x == "--rps":
            skip = True
            continue
        if isinstance(x, str) and x.startswith("--rps="):
            continue
        if x == "--phases":
            phases_next = True
        out.append(x)
    return (["md5:" + md5] if md5 else []) + out


def _phases_without_rate(text):
    try:
        v = json.loads(text)
    except (TypeError, ValueError):
        return text
    if not isinstance(v, list):
        return text
    return json.dumps([{k: p[k] for k in sorted(p) if k != "requests_per_second"} if isinstance(p, dict) else p
                       for p in v], separators=(",", ":"))
