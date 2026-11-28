"""Per-leg validity verdict.

A leg that fails any gate is INVALID and contributes no number to any
comparison; its round pair is dropped for that shape and arm.
"""

N1_MARK = "n1"  # epl.nighthawk.N1_MARK (kept here so this module imports nothing)

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
    # Envoy's thread set (tids) must be the same before and after the window (checked where the
    # leg records it): perf -p does not follow a thread created after it attached.
    "require_envoy_threads_unchanged": True,
    # Main thread busy over the window, a fraction of one core (None: not gated). The xDS rows
    # set it, so updates never queue behind each other on the main thread.
    "max_main_busy": None,
    "min_eff_ghz": None,         # optional: effective clock under perf
    # Latency columns only: a leg whose client max request-to-response exceeds
    # this keeps its CPU numbers but drops out of the latency comparisons.
    "max_latency_ms": None,
    # Side services in their own containers (origin with the authorization service,
    # tracing collector): CPU time in the window, read from the container's cgroup,
    # at most this share of the container's CPU set; the container's cpuset and every
    # process in it must sit on the configured set. None turns the gate off.
    "max_side_service_busy": 0.5,
    # Cloud VMs: share of CPU time stolen by the hypervisor over the window (None: not gated)
    "max_steal_share": None,
    # the client sent at full rate over the whole window: alive at the window's last read, every
    # worker's own execution ending at least this many seconds after it and its ramp ending before the first
    # read (client_sending, from the client's output). Legs recorded before this check carry no record and keep
    # their verdict; a leg marked n1 (epl.nighthawk.N1_MARK) without the record is invalid (fail closed).
    "require_client_sending": True,
    "client_sending_margin_s": 1.0,
    # a client self-check that can fail. All None (off) by default, so earlier configs keep their
    # verdicts; a plan sets them before data. Sequencer statistics are per client worker over the whole client
    # run (open loop: a blocked start means the client could not issue a request when the rate limiter allowed
    # it). The floor gates need the session's zero-load calibration leg (client_calibration); without a good
    # floor they fail closed. client_perf: a leg measured with measure.client_perf must have its counters.
    "max_client_sequencer_blocking": None,   # blocked starts, summed over workers (suggested: 0)
    "max_client_callback_ms": None,          # largest per-worker sequencer.callback maximum
    "max_client_busy_above_floor": None,     # busiest client thread's busy share minus the floor's
    "max_client_perf_cpus_above_floor": None,  # client perf CPUs per client worker minus the floor's
}


def verdict(m, cfg=None):
    c = dict(DEFAULTS)
    c.update(cfg or {})
    if m.get("idle_leg"):
        return idle_verdict(m, c)
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
    # None: the rate is recorded only (run L gates the listener's request count itself, exactly)
    elif c["rate_tolerance"] is not None and abs(rate / tgt - 1.0) > c["rate_tolerance"]:
        reasons.append("achieved rate %.1f misses target %d by %.2f%%"
                       % (rate, tgt, (rate / tgt - 1.0) * 100))
    ovf_d = {k: v for k, v in (m.get("client_overflow") or {}).items() if k not in (c["overflow_ignore"] or [])}
    ovf = sum(ovf_d.values())
    # None: recorded, not gated (run L: a stalled worker makes the client queue, and that is an outcome)
    if c["max_overflow"] is not None and ovf > c["max_overflow"]:
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
    lim = c["max_side_service_busy"]
    for name, sv in sorted((m.get("side_services") or {}).items()):
        if lim is None:
            break
        if sv.get("error"):
            reasons.append("side service %s: %s" % (name, sv["error"]))
            continue
        if sv.get("busy_of_set") is None:
            reasons.append("side service %s: no CPU time measured" % name)
        elif sv["busy_of_set"] > lim:
            reasons.append("side service %s used %.0f%% of its CPU set in the window, limit %.0f%%"
                           % (name, sv["busy_of_set"] * 100, lim * 100))
        if not sv.get("cpuset_ok"):
            reasons.append("side service %s: container cpuset %s is not the configured set %s"
                           % (name, sv.get("cpuset"), sv.get("want")))
        if not sv.get("pids_ok"):
            reasons.append("side service %s: processes off the configured set: %s"
                           % (name, sv.get("bad_pids") or "no process found"))
    if c["max_steal_share"] is not None and (m.get("steal_share") is None or m["steal_share"] > c["max_steal_share"]):
        reasons.append("steal time %s of the CPU time in the window, limit %.1f%%" % (
            "unknown" if m.get("steal_share") is None else "%.2f%%" % (100 * m["steal_share"]),
            100 * c["max_steal_share"]))
    if m.get("rung_pin") is not None and not m["rung_pin"].get("ok"):
        reasons.append("rung threads not on their cores: %s" % m["rung_pin"])
    if m.get("rung_pin_after") is not None and not m["rung_pin_after"].get("ok"):
        reasons.append("rung threads left their cores during the leg: %s" % m["rung_pin_after"])
    if m.get("responses_from") == "origin":
        if not m.get("origin_reads_ok") or not m.get("responses"):
            reasons.append("no origin response count (stub_status read failed or zero)")
        adm = m.get("responses_admin_raw")
        if adm and m.get("responses_raw") and abs(m["responses_raw"] / float(adm) - 1.0) > 0.005:
            reasons.append("origin response count %d differs from Envoy's %d by more than 0.5%%"
                           % (m["responses_raw"], adm))
    if m.get("workers_expected") is not None and (m.get("workers_perf_threads") != m["workers_expected"]
                                                 or m.get("workers_cycles_per_req") is None):
        reasons.append("worker-only cycles cover %s of %d worker threads" % (
            m.get("workers_perf_threads"), m["workers_expected"]))
    xr = m.get("xds")
    if xr is not None and not xr.get("ok"):
        bad = sorted(k for k, v in (xr.get("checks") or {}).items() if not v) or [xr.get("error") or "no record"]
        reasons.append("xds: %s" % ", ".join(bad))
    th = m.get("envoy_thread_set")
    if th is not None and c.get("require_envoy_threads_unchanged", True) and not th.get("unchanged"):
        # perf -p counts the threads that exist when it attaches: a thread created inside the
        # window (a gRPC client pool growing) would run uncounted
        reasons.append("Envoy threads changed during the window (%s)" % th)
    mb = m.get("envoy_main_busy")
    if c.get("max_main_busy") is not None and mb is not None and mb > c["max_main_busy"]:
        reasons.append("main thread busy %.3f of a core (limit %.2f)" % (mb, c["max_main_busy"]))
    client_checks(m, c, reasons)
    ev = m.get("evidence")
    if ev is not None and ev.get("gate", True) and not ev.get("ok"):
        f = ev.get("failed") or ["no evidence evaluated"]
        reasons.append("evidence: %s%s" % ("; ".join(f[:4]), " (+%d more)" % (len(f) - 4) if len(f) > 4 else ""))
    return {"valid": not reasons, "reasons": reasons}


def client_checks(m, c, reasons):
    """Client-window gates (only on legs that carry the records, or are marked n1)."""
    marked = N1_MARK in (m.get("harness_marks") or [])
    cs = m.get("client_sending")
    if c.get("require_client_sending", True):
        if cs is not None and not cs.get("ok"):
            reasons.append("client not sending through the window: %s" % "; ".join(cs.get("reasons") or ["?"]))
        elif cs is None and marked:
            reasons.append("no client-sending record")
    sq = m.get("client_sequencer") or {}
    lim = c.get("max_client_sequencer_blocking")
    if lim is not None:
        v = sq.get("blocking_count_total")
        if v is None:
            reasons.append("no client sequencer.blocking statistic")
        elif v > lim:
            reasons.append("client sequencer blocked %d times (limit %d)" % (v, lim))
    lim = c.get("max_client_callback_ms")
    if lim is not None:
        v = sq.get("callback_max_us")
        if v is None:
            reasons.append("no client sequencer.callback statistic")
        elif v > lim * 1000.0:
            reasons.append("client sequencer.callback max %.1f ms over %.1f ms" % (v / 1000.0, lim))
    cp = m.get("client_perf")
    if cp is not None and not cp.get("ok"):
        reasons.append("client perf counters missing or multiplexed")
    cph = m.get("client_phases")
    if cph is not None and not cph.get("ok"):
        # the planned phases ran, and the window lies inside the measure phase with its lead-in
        reasons.append("client phases: %s" % "; ".join(cph.get("reasons") or ["?"]))
    elif cph is None and m.get("client_recipe") == "phases" and not m.get("error"):
        reasons.append("no client-phases record (recipe phases)")
    if m.get("client_md5_pin"):
        # the measured client process ran the pinned binary (md5 and sha256 of its own executed inode, read
        # after the client ended); fail closed
        if not m.get("client_exe_ok"):
            reasons.append("client binary not the pinned one: %s" % (
                m.get("client_exe_error") or "md5 %s sha256 %s, pinned %s %s" % (
                    m.get("client_md5"), m.get("client_sha256"), m.get("client_md5_pin"), m.get("client_sha256_pin"))))
    for key, field, what in (("max_client_busy_above_floor", "client_busy_above_floor", "busiest client thread"),
                             ("max_client_perf_cpus_above_floor", "client_perf_cpus_above_floor",
                              "client perf CPUs per worker")):
        lim = c.get(key)
        if lim is None:
            continue
        v = m.get(field)
        if v is None and m.get("client_floor_mismatch"):
            reasons.append("%s above the floor not measured: no matching floor (this leg's client flags differ "
                           "from every calibration leg's)" % what)
        elif v is None:
            reasons.append("%s above the floor not measured (no good calibration leg%s)" % (
                what, "" if m.get("client_floor_leg") else " in this run"))
        elif v > lim:
            reasons.append("%s %.3f above the zero-load floor (limit %.3f)" % (what, v, lim))
    if any(c.get(k) is not None for k in F1_KEYS):
        # client-bottleneck checks (epl.clientcheck): per-worker sequencer gates and the busiest client perf interval,
        # fail closed
        from .clientcheck import validity_reasons
        reasons += validity_reasons(m, c)


# the client-bottleneck validity keys (epl.clientcheck.VALIDITY_KEYS; named here so this module imports nothing at
# load): all off unless set, so no earlier leg's verdict changes
F1_KEYS = ("max_client_worker_sequencer_blocking", "max_client_worker_callback_ms",
           "max_client_perf_interval_cpus_per_worker", "client_overflow_gate")


def _common(m, c, reasons):
    """Gates every leg shares: box state, errors, pinning, SUT CPUs during the window, idle
    states, exit code, multiplexing, side services, evidence."""
    if not m.get("idle_ok"):
        reasons.append("box not idle before the leg")
    if not m.get("preflight_ok"):
        reasons.append("port preflight failed: %s" % m.get("preflight_detail"))
    if m.get("error"):
        reasons.append("error: %s" % m["error"])
    if not m.get("pinning_ok", True):
        reasons.append("process not on its configured CPUs")
    fc, sc = m.get("sut_foreign_cpus"), m.get("sut_sibling_cpus")
    if fc is None or sc is None:
        reasons.append("no scheduler run time for the SUT CPUs (%s)" % m.get("sched_probe", "no data"))
    else:
        if c["max_sut_foreign_cpus"] is not None and fc > c["max_sut_foreign_cpus"]:
            reasons.append("other tasks used %.3f CPUs on the SUT CPUs during the window" % fc)
        if c["max_sut_sibling_cpus"] is not None and sc > c["max_sut_sibling_cpus"]:
            reasons.append("SMT siblings of the SUT CPUs busy %.3f CPUs during the window" % sc)
    if c["require_cpuidle_unchanged"] and m.get("cpuidle_unchanged") is False:
        reasons.append("idle-state configuration of the SUT CPUs changed since the start of the run")
    if c["require_envoy_exit_zero"] and "envoy_exit" in m and m["envoy_exit"] not in (0, None):
        reasons.append("envoy exit code %s" % m["envoy_exit"])
    if c["require_perf_unmultiplexed"] and m.get("perf_min_running_pct") is not None \
            and m["perf_min_running_pct"] < 99.99:
        reasons.append("perf counters multiplexed (%.1f%% running)" % m["perf_min_running_pct"])


def idle_verdict(m, c):
    """An idle leg (stats row): no request gates; the main thread must be the right thread and
    sampled for the whole window, its counters complete; side services and evidence as usual."""
    reasons = []
    _common(m, c, reasons)
    if not m.get("perf_ok"):
        reasons.append("perf counters of the main thread missing")
    if not m.get("main_tid_ok"):
        reasons.append("main thread not sampled as the main thread for the whole window (comm %s, %s samples, "
                       "%s missing)" % (m.get("main_comm"), (m.get("main") or {}).get("samples"),
                                        (m.get("main") or {}).get("sampler_missing")))
    full = verdict(dict(m, idle_leg=False, idle_ok=True, preflight_ok=True, error=None, pinning_ok=True,
                        sut_rate_2xx=1, target_rps=1, client_headroom=1, perf_ok=True, responses=1,
                        sut_foreign_cpus=0, sut_sibling_cpus=0, envoy_exit=0, perf_min_running_pct=None,
                        envoy_worker_max_share=None, envoy_worker_min_share=None, envoy_workers=None),
                   dict(c, max_worker_share_factor=None, min_worker_share_factor=None,
                        max_pending_total=None))
    reasons += full["reasons"]  # the side-service and evidence gates
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
