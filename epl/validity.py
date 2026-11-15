"""Per-leg validity verdict.

A leg that fails any gate is INVALID and contributes no number to any
comparison; its round pair is dropped for that shape and arm.
"""

DEFAULTS = {
    "rate_tolerance": 0.01,      # achieved rate within 1% of target
    "min_client_headroom": 0.25,  # busiest client thread at most 75% busy
    "max_overflow": 0,           # client pool overflow / connection failures
    # Client counters not counted as overflow for this shape. Only for a counter that
    # cannot mean a dropped request: upstream_cx_overflow (the pool wanted more
    # connections than allowed and the request waited) during TLS start-up, where
    # every client connection does a full handshake at once, before the window.
    "overflow_ignore": [],
    "max_non2xx": 0,             # non-2xx at client and at the SUT
    # Client requests that ever waited in the client queue. Each client worker
    # queues its first request while its connections are set up, so the total
    # equals the client worker count on a clean leg; anything above it means
    # the queue absorbed a burst that the pool could not take.
    # "client_cx": at most one waiting request per client connection opened, plus
    # each client worker's first request (shapes
    # that open a new connection every N requests without prefetch: the request
    # that triggers a reconnect may wait for it, nothing else may).
    "max_pending_total": "client_workers",
    # During the perf window (scheduler run time from /proc/schedstat): time
    # other tasks ran on the SUT CPUs, and any task time on their SMT siblings
    # outside the SUT set, in CPUs (1.0 = one CPU fully busy).
    "max_sut_foreign_cpus": 0.05,
    "max_sut_sibling_cpus": 0.05,
    # Lower bound on both: run time cannot be negative beyond the snapshot
    # skew (about 1e-4 CPU), so a value under this means the probe is wrong.
    "min_sut_window_cpus": -0.01,
    # Busiest Envoy worker's share of worker CPU, as a multiple of the even
    # share (1/workers). Per-request cycles depend on how many workers carry the
    # load (fewer, busier workers batch more), so a leg that concentrates load
    # measures a different thing. Nighthawk's default MRU connection reuse does
    # exactly that, at random per leg; LRU reuse keeps every worker even (the
    # busiest worker stayed under 1.04x its even share in every LRU leg so far).
    # At 1.5x a leg with three of four workers busy still passed.
    "max_worker_share_factor": 1.2,
    # Least busy worker's share as a multiple of the even share: catches a
    # worker that carries nothing, which the busiest-worker bound misses when
    # the others share the load evenly.
    "min_worker_share_factor": 0.5,
    # Second hop of a two-hop arm: its load comes from the first hop's upstream
    # connection pool, not from the client, so how evenly it lands is part of what
    # the arm measures. False: the share gate covers the first hop only and the
    # second hop's shares are recorded.
    "hop2_worker_share_gate": True,
    "require_envoy_exit_zero": True,
    # The SUT CPUs' idle-state configuration (driver, governor, every state's
    # disable flag) must match the one recorded at the start of the run.
    "require_cpuidle_unchanged": True,
    "require_perf_unmultiplexed": True,
    "min_eff_ghz": None,         # optional: effective clock under perf
    # Latency columns only: a leg whose client max request-to-response exceeds
    # this keeps its CPU numbers but drops out of the latency comparisons.
    "max_latency_ms": None,
}


def verdict(m, cfg=None):
    c = dict(DEFAULTS)
    c.update(cfg or {})
    reasons = []
    if not m.get("idle_ok"):
        reasons.append("box not idle before the leg")
    if not m.get("preflight_ok"):
        reasons.append("port preflight failed: %s" % m.get("preflight_detail"))
    if m.get("error"):
        reasons.append("error: %s" % m["error"])
    if not m.get("pinning_ok", True):
        reasons.append("process not on its configured CPUs")
    tgt = m.get("target_rps") or 0
    rate = m.get("sut_rate_2xx")
    if rate is None or not tgt:
        reasons.append("no achieved-rate measurement")
    elif abs(rate / tgt - 1.0) > c["rate_tolerance"]:
        reasons.append("achieved rate %.1f misses target %d by %.2f%%"
                       % (rate, tgt, (rate / tgt - 1.0) * 100))
    ovf_d = {k: v for k, v in (m.get("client_overflow") or {}).items() if k not in (c["overflow_ignore"] or [])}
    ovf = sum(ovf_d.values())
    if ovf > c["max_overflow"]:
        reasons.append("client overflow/pool-exhausted counters %d (%s)"
                       % (ovf, ", ".join("%s=%d" % kv for kv in sorted(ovf_d.items()))))
    nc = sum((m.get("client_non2xx") or {}).values())
    ns = m.get("sut_non2xx", 0) or 0
    if nc > c["max_non2xx"] or ns > c["max_non2xx"]:
        reasons.append("non-2xx responses: client %d, SUT %d" % (nc, ns))
    hr = m.get("client_headroom")
    if hr is None:
        reasons.append("no client headroom measurement")
    elif hr < c["min_client_headroom"]:
        reasons.append("client headroom %.0f%% under %.0f%%" % (hr * 100, c["min_client_headroom"] * 100))
    if not m.get("perf_ok"):
        reasons.append("perf counters missing")
    if not m.get("responses"):
        reasons.append("zero successful responses in the window")
    lim = c["max_pending_total"]
    if lim == "client_workers":
        lim = m.get("client_workers")
    elif lim == "client_cx":
        # one waiting request per connection opened, plus each client worker's first
        cx, nw = m.get("client_cx_total"), m.get("client_workers")
        lim = None if cx is None else cx + (nw or 0)
    pend = m.get("client_pending_total")
    if lim is not None and pend is not None and pend > lim:
        reasons.append("client pending total %d above %d (queue absorbed a burst)" % (pend, lim))
    fc = m.get("sut_foreign_cpus")
    sc = m.get("sut_sibling_cpus")
    if c["max_sut_foreign_cpus"] is not None or c["max_sut_sibling_cpus"] is not None:
        if fc is None or sc is None:
            reasons.append("no scheduler run time for the SUT CPUs (%s)" % m.get("sched_probe", "no data"))
        else:
            lo = c["min_sut_window_cpus"]
            if c["max_sut_foreign_cpus"] is not None and fc > c["max_sut_foreign_cpus"]:
                reasons.append("other tasks used %.3f CPUs on the SUT CPUs during the window" % fc)
            if c["max_sut_sibling_cpus"] is not None and sc > c["max_sut_sibling_cpus"]:
                reasons.append("SMT siblings of the SUT CPUs busy %.3f CPUs during the window" % sc)
            if lo is not None and (fc < lo or sc < lo):
                reasons.append("scheduler run time probe inconsistent: foreign %.4f, siblings %.4f CPUs "
                               "(under %.2f)" % (fc, sc, lo))
    sh, lo, nw = m.get("envoy_worker_max_share"), m.get("envoy_worker_min_share"), m.get("envoy_workers")
    if c["max_worker_share_factor"] is not None or c["min_worker_share_factor"] is not None:
        if sh is None or not nw:
            # no wrk: thread found, or no worker CPU at all: the gate cannot be
            # checked, so the leg does not count
            reasons.append("no Envoy worker CPU measured (%s)" % m.get("envoy_worker_probe", "no data"))
        else:
            if c["max_worker_share_factor"] is not None and sh > c["max_worker_share_factor"] / nw:
                reasons.append("Envoy load uneven: busiest worker did %.1f%% of worker CPU, limit %.1f%% "
                               "(%d workers)" % (sh * 100, c["max_worker_share_factor"] * 100 / nw, nw))
            if c["min_worker_share_factor"] is not None and (lo is None or lo < c["min_worker_share_factor"] / nw):
                reasons.append("Envoy load uneven: least busy worker did %s of worker CPU, floor %.1f%% "
                               "(%d workers)" % ("?" if lo is None else "%.1f%%" % (lo * 100),
                                                 c["min_worker_share_factor"] * 100 / nw, nw))
    if c["require_cpuidle_unchanged"] and m.get("cpuidle_unchanged") is False:
        reasons.append("idle-state configuration of the SUT CPUs changed since the start of the run")
    if c["require_envoy_exit_zero"] and "envoy_exit" in m and m["envoy_exit"] not in (0, None):
        reasons.append("envoy exit code %s" % m["envoy_exit"])
    if c["require_perf_unmultiplexed"] and m.get("perf_min_running_pct") is not None \
            and m["perf_min_running_pct"] < 99.99:
        reasons.append("perf counters multiplexed (%.1f%% running)" % m["perf_min_running_pct"])
    if c["min_eff_ghz"] and m.get("eff_ghz") is not None and m["eff_ghz"] < c["min_eff_ghz"]:
        reasons.append("effective clock %.3f GHz under %.3f" % (m["eff_ghz"], c["min_eff_ghz"]))
    return {"valid": not reasons, "reasons": reasons}


def latency_ok(m, cfg=None):
    """Whether this leg's latency numbers may enter a latency comparison."""
    c = dict(DEFAULTS)
    c.update(cfg or {})
    lim = c["max_latency_ms"]
    mx = (m.get("latency_us") or {}).get("max")
    if lim is None:
        return True
    return mx is not None and mx <= lim * 1000.0
