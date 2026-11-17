"""epl: A/B harness beside Nighthawk for measuring Envoy CPU cost per request.

Commands (see README.md):
  plan CFG                       validate a config and print the schedule
  render CFG                     print the generated Envoy bootstrap and origin config
  run CFG [--dry-run] [--detach] run an experiment on this machine
  calibrate CFG --arm A --shape S --rps R1,R2,...   single legs, to pick rates
  status RUN_DIR                 progress of a (detached) run
  report RESULTS_JSON [--floor AA_RESULTS_JSON]   regenerate summary.md from results.json
  evidence-check SPEC RUN_DIR... [--freeze OUT]   run an evidence spec offline against recorded legs
  stats-calibrate CFG --arm A --shapes S1,S2      stats row: one idle leg per rung, N by kind, timeouts
  flush-profile CFG --arm A --shape S             stats row: perf record of the main thread over flushes
  portability-check DIR...                        stats row: configs per box are free of other boxes' literals
  request-probe CFG --arm A --shape S [--trace C] [--expect H=V]   one request through a throw-away Envoy
  scrub RUN_DIR                  replace home directory paths with ~ in a run directory
  selftest                       offline tests: statistics, validity gates, schedule, dry run
  remote HOST <run|calibrate|status|fetch|ship> ...  same, on a bench box over ssh
"""

import argparse
import io
import json
import os
import shlex
import signal
import subprocess
import sys
import tarfile
import time

from . import envoy_config, experiment, sysprobe

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _on_term(signum, frame):
    raise SystemExit("terminated by signal %d" % signum)


def _run_dir(exp, out):
    if out:
        return os.path.abspath(os.path.expanduser(out))
    return os.path.join(exp["workdir"], "%s-%s" % (exp["name"], time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))


def _load(args, overrides=None, check_rounds=True):
    ov = experiment.parse_sets(getattr(args, "set", None))
    ov = experiment._merge(ov, overrides or {})
    if getattr(args, "rounds", None):
        ov["rounds"] = args.rounds
    if getattr(args, "max_rounds", None):
        ov["rounds_max"] = args.max_rounds
    if getattr(args, "fixed", False):
        ov["adaptive"] = False
    exp = experiment.load(args.config, ov)
    if not exp.get("adaptive", True):
        exp["rounds_max"] = exp["rounds"]
    errs = experiment.validate(exp, allow_short=getattr(args, "allow_short", False), check_rounds=check_rounds)
    if errs:
        sys.exit("config errors:\n  " + "\n  ".join(errs))
    return exp


def cmd_plan(args):
    exp = _load(args)
    plan = experiment.schedule(exp)
    for r, s, a in plan:
        print(experiment.leg_id(r, s, a))
    leg_s = exp["client"]["warmup_s"] + exp["client"]["duration_s"] + 8
    mx = len(experiment.schedule(exp, 1, exp["rounds_max"])) if exp.get("adaptive", True) else len(plan)
    print("# %s order; %d legs for the minimum %d rounds (about %.0f min plus idle waits); up to %d legs "
          "(%d rounds) if the stop target is not met" % (
              experiment.effective_order(exp), len(plan), exp["rounds"], len(plan) * leg_s / 60.0, mx,
              exp["rounds_max"] if exp.get("adaptive", True) else exp["rounds"]))


def cmd_render(args):
    exp = _load(args)
    for a in exp["arms"]:
        print("# arm %s" % a["name"])
        print(envoy_config.bootstrap_text(exp["shapes"], experiment.arm_envoy(exp, a, "<run>"),
                                          exp["origin"]["port"], "<run>/certs"))
    if experiment.uses(exp, "two_hop"):
        print("# second hop")
        print(envoy_config.bootstrap_text(exp["shapes"], experiment.hop2_envoy(exp), exp["origin"]["port"]))
    print(envoy_config.nginx_conf(exp["origin"]["port"], exp["origin"].get("workers", 8),
                                  exp["origin"].get("authz_port"), exp["origin"].get("authz_grpc_port"),
                                  types=envoy_config.content_types(exp["shapes"])))


def _detach(log_path):
    if os.fork() > 0:
        return False
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    nul = os.open(os.devnull, os.O_RDONLY)
    os.dup2(nul, 0)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    return True


def cmd_run(args):
    exp = _load(args)
    run_dir = _run_dir(exp, args.out)
    if os.path.exists(os.path.join(run_dir, "legs.jsonl")):
        sys.exit("run dir %s already has legs; pick another --out" % run_dir)
    os.makedirs(run_dir, exist_ok=True)
    if args.detach:
        print(run_dir)
        sys.stdout.flush()
        if not _detach(os.path.join(run_dir, "console.log")):
            return
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGHUP, _on_term)
    if args.dry_run:
        from .sim import SimBackend
        factory = SimBackend
    else:
        from .leg import RealBackend
        factory = RealBackend
    r = experiment.Runner(exp, run_dir, factory, allow_short=args.allow_short,
                          log_stream=None if args.detach else sys.stdout)
    try:
        res = r.run(simulate=args.dry_run)
    except BaseException as e:
        r.log("ABORTED: %s: %s" % (type(e).__name__, e))
        r.status(state="aborted", error=str(e))
        if args.detach:
            # console.log lives in the run directory: no traceback with home paths in it.
            sys.stderr.write(sysprobe.scrub_text("aborted: %s: %s\n" % (type(e).__name__, e)))
            sys.exit(1)
        raise
    print(os.path.join(run_dir, "summary.md"))
    if "aa_selftest" in res:
        print("A/A self-test: %s" % ("PASS" if res["aa_selftest"]["pass"] else "FAIL"))


def cmd_calibrate(args):
    exp = _load(args, check_rounds=False)
    arm = [a for a in exp["arms"] if a["name"] == args.arm]
    shape = [s for s in exp["shapes"] if s["name"] == args.shape]
    if not arm or not shape:
        sys.exit("unknown arm or shape")
    run_dir = _run_dir(dict(exp, name=exp["name"] + "-calibrate"), args.out)
    from .leg import RealBackend
    from .origin import Origin
    signal.signal(signal.SIGTERM, _on_term)
    for d in ("logs", "nighthawk", "perf"):
        os.makedirs(os.path.join(run_dir, d), exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    bpath, _, _ = experiment.prepare_bootstraps(exp, run_dir, log)
    be = RealBackend(exp, run_dir, log)
    origin = Origin(exp["origin"], exp["cpus"].get("origin", ""), exp["shapes"], run_dir, log)
    collector = None
    rows = []
    try:
        origin.start()
        if experiment.needs_collector(exp):
            from .origin import Collector
            collector = Collector(exp["collector"], exp["cpus"]["origin"], run_dir, log)
            collector.start()
        be.attach(origin, collector)
        for rps in [int(x) for x in args.rps.split(",")]:
            sh = dict(shape[0], rps=rps)
            m = be.run_leg(arm[0], sh, 0, bpath, "cal-%s-%s-%d" % (args.arm, args.shape, rps))
            pr = m.get("per_req") or {}
            row = {"rps": rps, "valid": m["verdict"]["valid"], "reasons": m["verdict"]["reasons"],
                   "sut_busy": m.get("sut_busy"), "client_headroom": m.get("client_headroom"),
                   "rate": m.get("sut_rate_2xx"), "ins_u_k": pr.get("instructions_u", 0) / 1e3,
                   "cyc_total_k": pr.get("cycles_total", 0) / 1e3,
                   "p99_us": (m.get("latency_us") or {}).get("p99"),
                   "stats": m.get("sut_stats_delta"), "hop2_busy": m.get("hop2_busy"),
                   "pending_total": m.get("client_pending_total"), "access_log_lines": m.get("access_log_lines"),
                   "p50_us": (m.get("latency_us") or {}).get("p50"),
                   "worker_max_share": m.get("envoy_worker_max_share"),
                   "hop2_worker_max_share": (m.get("hop2_workers") or {}).get("worker_max_share"),
                   "hop2_worker_max_busy": (m.get("hop2_workers") or {}).get("worker_max_busy"),
                   "sut_foreign_cpus": m.get("sut_foreign_cpus"),
                   "side_services": m.get("side_services"),
                   "evidence_failed": (m.get("evidence") or {}).get("failed")}
            rows.append(row)
            # the full leg record too (shares, connections, counters), one line per rate
            with open(os.path.join(run_dir, "calibrate-legs.jsonl"), "a") as f:
                f.write(json.dumps(m, sort_keys=True) + "\n")
            print(json.dumps(row), flush=True)
    finally:
        if collector:
            collector.stop()
        origin.stop()
        be.close()
    with open(os.path.join(run_dir, "calibrate.json"), "w") as f:
        json.dump(rows, f, indent=1)


def cmd_probe(args):
    """Saturation probe: every arm at each rate of --rps (ascending), --reps times, the
    arms' order reversed on every other pass so no arm always runs first. Every leg is
    kept in full in probe.jsonl; probe.json has one summary row per leg."""
    exp = _load(args, check_rounds=False)
    shape = [s for s in exp["shapes"] if s["name"] == args.shape]
    if not shape:
        sys.exit("unknown shape")
    run_dir = _run_dir(dict(exp, name=exp["name"] + "-probe"), args.out)
    from .leg import RealBackend
    from .origin import Origin
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGHUP, _on_term)
    for d in ("logs", "nighthawk", "perf"):
        os.makedirs(os.path.join(run_dir, d), exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    bpath, _, _ = experiment.prepare_bootstraps(exp, run_dir, log)
    be = RealBackend(exp, run_dir, log)
    origin = Origin(exp["origin"], exp["cpus"].get("origin", ""), exp["shapes"], run_dir, log)
    rows = []
    n = 0
    try:
        origin.start()
        for rep in range(args.reps):
            for rps in [int(x) for x in args.rps.split(",")]:
                arms = list(exp["arms"]) if n % 2 == 0 else list(reversed(exp["arms"]))
                n += 1
                for a in arms:
                    sh = dict(shape[0], rps=rps)
                    m = be.run_leg(a, sh, rep, bpath, "probe-%s-%s-%d-r%d" % (a["name"], args.shape, rps, rep))
                    with open(os.path.join(run_dir, "probe.jsonl"), "a") as f:
                        f.write(json.dumps(m, default=str) + "\n")
                    pr = m.get("per_req") or {}
                    lat = m.get("latency_us") or {}
                    row = {"arm": a["name"], "rps": rps, "rep": rep, "valid": m["verdict"]["valid"],
                           "reasons": m["verdict"]["reasons"], "rate": m.get("sut_rate_2xx"),
                           "sut_busy": m.get("sut_busy"), "hop2_busy": m.get("hop2_busy"),
                           "client_headroom": m.get("client_headroom"),
                           "p50_us": lat.get("p50"), "p99_us": lat.get("p99"),
                           "cyc_total_k": pr.get("cycles_total", 0) / 1e3,
                           "cyc_all_k": pr.get("cycles_total_all", 0) / 1e3,
                           "hop2_workers": m.get("hop2_workers"),
                           "envoy_worker_max_busy": m.get("envoy_worker_max_busy"),
                           "client_overflow": m.get("client_overflow"),
                           "client_pending_total": m.get("client_pending_total"),
                           "hop2_conns": (m.get("conn_hop2_downstream") or {}).get("conns_over_1pct_of_mean")}
                    rows.append(row)
                    print(json.dumps(row), flush=True)
    finally:
        origin.stop()
        be.close()
        with open(os.path.join(run_dir, "probe.json"), "w") as f:
            json.dump(rows, f, indent=1)
        sysprobe.scrub_tree(run_dir)


def cmd_status(args):
    d = os.path.expanduser(args.run_dir)
    p = os.path.join(d, "status.json")
    if os.path.exists(p):
        with open(p) as f:
            st = json.load(f)
        st["process_alive"] = _is_epl_run(st.get("pid"))
        print(json.dumps(st, indent=1))
    lp = os.path.join(d, "log.txt")
    if os.path.exists(lp):
        with open(lp) as f:
            lines = f.readlines()
        sys.stdout.write("".join(lines[-args.lines:]))


def _is_epl_run(pid):
    """True when pid is alive and its command line is an epl run. Reads /proc only;
    never signals anything, and a reused PID running something else reads as dead."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 1:
        return False
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            argv = f.read().split(b"\0")
    except OSError:
        return False
    return any(a.endswith(b"epl") for a in argv) and b"run" in argv


def cmd_report(args):
    from .report import markdown
    with open(args.results) as f:
        res = json.load(f)
    floor = experiment.load_floor(args.floor, args.floor_arm) if args.floor else None
    if args.reanalyse or floor:
        exp = res["experiment"]
        res["analysis"] = experiment.analyse(exp, res["legs"], floor)
        if exp.get("expect") == "aa":
            res["aa_selftest"] = experiment.aa_verdict(exp, res["analysis"])
    sys.stdout.write(markdown(res, floor))


def cmd_evidence_check(args):
    """Evaluate the evidence spec (an experiment config's arms[].evidence, or
    {"evidence": {arm: [items]}}) against every recorded leg of the run directories.
    --freeze OUT first resolves every `ref` item from these legs (mean per-request value
    of the referenced arm plus the offset) and writes the spec, or the whole config with
    the frozen items, to OUT; the check then runs with the frozen spec. Exit 1 when any
    leg fails an item, a ref cannot be resolved, or an arm of the spec has no leg."""
    from . import evidence
    spec = evidence.load_spec(args.spec)
    if not spec:
        sys.exit("no evidence items in %s" % args.spec)
    bad = 0
    if args.freeze:
        legs = []
        for d in args.run_dir:
            legs += evidence.load_legs(os.path.expanduser(d))
        spec, problems = evidence.freeze(spec, legs)
        for p in problems:
            print("FREEZE PROBLEM %s" % p)
        bad += len(problems)
        with open(args.spec) as f:
            raw = json.load(f)
        if isinstance(raw.get("evidence"), dict):
            raw["evidence"] = spec
        else:
            for a in raw.get("arms", []):
                if a["name"] in spec:
                    a["evidence"] = spec[a["name"]]
        with open(args.freeze, "w") as f:
            json.dump(raw, f, indent=1)
            f.write("\n")
        print("frozen spec written to %s" % args.freeze)
    seen = set()
    for d in args.run_dir:
        rows, problems = evidence.check_run(spec, os.path.expanduser(d))
        for p in problems:
            print("note: %s" % p)
        for lid, arm, ev in rows:
            seen.add(arm)
            print("%s %-28s %s" % ("PASS" if ev["ok"] else "FAIL", lid, "" if ev["ok"] else "; ".join(ev["failed"])))
            if args.verbose:
                for it in ev["items"]:
                    print("      %-60s %s value=%s" % (it["label"], "ok" if it["ok"] else it["why"], it.get("value")))
            bad += 0 if ev["ok"] else 1
    # every arm of the spec must have been checked on at least one leg: an arm that never ran
    # has had none of its evidence exercised, reference arms (absent items) included
    missing = sorted(set(spec) - seen)
    if missing:
        print("FAIL arms of the spec with no leg in these runs: %s" % ", ".join(missing))
    ok = not bad and not missing and bool(seen)
    print("evidence-check: %s (%d failing legs, %d arms without a leg)" % ("PASS" if ok else "FAIL", bad, len(missing)))
    sys.exit(0 if ok else 1)


def request_headers(shape):
    """Request headers the client sends for a shape (its --request-header name:value arguments)."""
    out, xs = [], list(shape.get("client_extra_args") or [])
    for i, x in enumerate(xs):
        if x == "--request-header" and i + 1 < len(xs):
            k, _, v = xs[i + 1].partition(":")
            out.append((k.strip(), v.strip()))
    return out


def trace_problems(lines, comps):
    """A traced probe with no log line of the traced components means the filter was never
    entered (or logged nothing): that fails, closed."""
    return [] if lines else ["no %s log lines: the filter did not run on the request" % ",".join(comps)]


def check_expect(headers, expects):
    """[problem] for every NAME=VALUE that the response headers do not carry (NAME= : absent)."""
    got = {}
    for k, v in headers:
        got.setdefault(k.lower(), []).append(v)
    bad = []
    for e in expects or []:
        k, _, v = e.partition("=")
        have = got.get(k.lower().strip())
        if v == "":
            if have:
                bad.append("%s present (%s), expected absent" % (k, have))
        elif not have or v not in have:
            bad.append("%s is %s, expected %s" % (k, have, v))
    return bad


def cmd_request_probe(args):
    """Start the arm's Envoy (and the origin when the shape is proxied) on the SUT CPUs, send
    one request of the shape (with the shape's client headers) from Python, print the status,
    response headers and body size, check --expect NAME=VALUE (NAME= for absent), stop. With
    --trace COMPONENTS (e.g. lua:trace,wasm:trace) Envoy runs with that component log level;
    its log is kept in the output directory and the lines of those components are printed.
    For the smoke only: not a measurement."""
    import http.client as hc
    exp = _load(args, check_rounds=False)
    arm = [a for a in exp["arms"] if a["name"] == args.arm]
    shape = [s for s in exp["shapes"] if s["name"] == args.shape]
    if not arm or not shape:
        sys.exit("unknown arm or shape")
    arm, shape = arm[0], shape[0]
    run_dir = _run_dir(dict(exp, name="%s-probe-%s-%s" % (exp["name"], arm["name"], shape["name"])), args.out)
    os.makedirs(os.path.join(run_dir, "logs"), exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    errs = experiment.check_wasm(exp)
    if errs:
        sys.exit("; ".join(errs))
    bpath, _, _ = experiment.prepare_bootstraps(exp, run_dir, log)
    from .leg import RealBackend
    from .origin import Origin
    signal.signal(signal.SIGTERM, _on_term)
    be = RealBackend(exp, run_dir, log)
    origin = Origin(exp["origin"], exp["cpus"].get("origin", ""), [shape], run_dir, log)
    extra = list(arm.get("extra_args", []))
    if args.trace:
        extra += ["--component-log-level", args.trace]
    elog_path = os.path.join(run_dir, "logs", "probe.envoy.log")
    envoy = elog = None
    bad = []
    try:
        origin.start()
        envoy, elog = be._start_envoy(arm["binary"], bpath[arm["name"]], exp["cpus"]["sut"], exp["envoy"]["workers"],
                                      exp["envoy"]["admin_port"], dict(arm.get("env") or {}), extra, elog_path)
        c = hc.HTTPConnection("127.0.0.1", int(exp["envoy"]["listener_port"]), timeout=10)
        c.request("GET", shape["path"], headers=dict(request_headers(shape)))
        r = c.getresponse()
        body = r.read()
        hdrs = r.getheaders()
        c.close()
        print("status %d, body %d bytes" % (r.status, len(body)))
        for k, v in hdrs:
            print("  %s: %s" % (k, v))
        if r.status != 200:
            bad.append("status %d" % r.status)
        bad += check_expect(hdrs, args.expect)
    finally:
        if envoy is not None:
            be._stop_envoy(envoy, elog, elog_path)
        origin.stop()
        be.close()
    if args.trace:
        comps = [x.split(":")[0] for x in args.trace.split(",")]
        with open(elog_path) as f:
            lines = [ln.rstrip() for ln in f if any("[%s]" % c in ln for c in comps)]
        print("%d log lines of %s in %s" % (len(lines), ",".join(comps), elog_path))
        for ln in lines[:args.lines]:
            print("  " + ln[-240:])
        bad += trace_problems(lines, comps)
    for b in bad:
        print("PROBE FAIL %s" % b)
    print("request-probe: %s" % ("PASS" if not bad else "FAIL"))
    sys.exit(1 if bad else 0)


def _side_services(exp, run_dir, log, shapes):
    from .origin import Collector, Origin
    origin = Origin(exp["origin"], exp["cpus"].get("origin", ""), shapes, run_dir, log)
    collector = Collector(exp["collector"], exp["cpus"]["origin"], run_dir, log) \
        if experiment.needs_collector(exp) else None
    return origin, collector


def cmd_stats_calibrate(args):
    """One idle leg per rung (shape) of one arm, with N by kind (Counters, Gauges, Histograms,
    TextReadouts, all and used only), start time, admin read durations, flush duration (burst),
    memory and fd peak. Writes calibrate.json and rungs.json: per shape the timeouts and the
    settle the session should use (ready 3 x start, admin 3 x the slowest read, settle = the
    longest flush + 2 s, all with floors) and the calibrated counts."""
    exp = _load(args, check_rounds=False)
    arm = [a for a in exp["arms"] if a["name"] == args.arm]
    if not arm:
        sys.exit("unknown arm")
    shapes = []
    for n in args.shapes.split(","):
        sh = [s for s in exp["shapes"] if s["name"] == n]
        if not sh:
            sys.exit("unknown shape %s" % n)
        shapes.append(dict(sh[0], **({"ready_timeout_s": args.ready_timeout} if args.ready_timeout else {}),
                           **({"admin_timeout_s": args.admin_timeout} if args.admin_timeout else {})))
    run_dir = _run_dir(dict(exp, name=exp["name"] + "-stats-calibrate"), args.out)
    for d in ("logs", "nighthawk", "perf"):
        os.makedirs(os.path.join(run_dir, d), exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    from .leg import RealBackend
    signal.signal(signal.SIGTERM, _on_term)
    bpath, _, _ = experiment.prepare_bootstraps(exp, run_dir, log)
    be = RealBackend(exp, run_dir, log)
    be.calibrate = True
    origin, collector = _side_services(exp, run_dir, log, exp["shapes"])
    rows, rungs = [], {}
    try:
        origin.start()
        if collector:
            collector.start()
        be.attach(origin, collector)
        for sh in shapes:
            m = be.run_leg(arm[0], sh, 0, bpath, "cal-%s-%s" % (arm[0]["name"], sh["name"]))
            with open(os.path.join(run_dir, "calibrate-legs.jsonl"), "a") as f:
                f.write(json.dumps(m, sort_keys=True, default=str) + "\n")
            mn = m.get("main") or {}
            reads = [x for x in ((m.get("pre_read") or {}).get("seconds"), (m.get("post_read") or {}).get("seconds"))
                     if x is not None]
            row = {"shape": sh["name"], "valid": m["verdict"]["valid"], "reasons": m["verdict"]["reasons"],
                   "start_s": m.get("start_s"), "stats_total": m.get("stats_total"), "used_total": m.get("used_total"),
                   "used_cg_lines": m.get("used_cg_lines"), "by_kind": m.get("by_kind"),
                   "active_clusters": m.get("active_clusters"), "admin_read_s": reads, "bursts": mn.get("bursts"),
                   "flush_run_ms_max": mn.get("burst_run_ms_max"), "stall_ms_max": mn.get("stall_ms_max"),
                   "run_ms_per_period": mn.get("run_ms_per_period"), "memory": m.get("memory"),
                   "fd_count": m.get("fd_count"), "nofile_soft": m.get("nofile_soft"), "prime": m.get("prime"),
                   "udp": m.get("udp")}
            rows.append(row)
            print(json.dumps(row, default=str), flush=True)
            if m.get("start_s") is not None:
                rungs[sh["name"]] = {
                    "ready_timeout_s": max(60, int(3 * m["start_s"]) + 1),
                    "admin_timeout_s": max(10, int(3 * max(reads or [1])) + 1),
                    "settle_s": round((mn.get("stall_ms_max") or 0) / 1e3 + 2.0, 2),
                    "stats_total": m.get("stats_total"), "used_total": m.get("used_total"),
                    "used_cg_lines": m.get("used_cg_lines")}
    finally:
        if collector:
            collector.stop()
        origin.stop()
        be.close()
        with open(os.path.join(run_dir, "calibrate.json"), "w") as f:
            json.dump(rows, f, indent=1, default=str)
        with open(os.path.join(run_dir, "rungs.json"), "w") as f:
            json.dump(rungs, f, indent=1)
        sysprobe.scrub_tree(run_dir)
    print(os.path.join(run_dir, "rungs.json"))


PROFILE_CLASSES = (
    ("reference counting and latching", r"(?i)(refcount|incref|decref|RefcountPtr|latch|MetricSnapshot|"
                                         r"forEachSinked|SharedPtr|shared_ptr|atomic)"),
    ("histogram accumulate and quantiles", r"(?i)(hist_|merge|quantile|refresh|Histogram|circllhist)"),
)


def classify_profile(rows):
    """[(pct, symbol)] -> {class: pct} with the rest under "other"."""
    import re as _re
    out = {name: 0.0 for name, _ in PROFILE_CLASSES}
    out["other"] = 0.0
    for pct, sym in rows:
        for name, pat in PROFILE_CLASSES:
            if _re.search(pat, sym):
                out[name] += pct
                break
        else:
            out["other"] += pct
    return out


def parse_perf_report(text):
    """[(percent, symbol)] from `perf report --stdio --sort symbol` lines like
    `  12.34%  [.] Envoy::Stats::...`."""
    import re as _re
    rows = []
    for line in text.splitlines():
        mm = _re.match(r"^\s*([0-9.]+)%\s+\[[.k]\]\s+(.+?)\s*$", line)
        if mm:
            rows.append((float(mm.group(1)), mm.group(2)))
    return rows


def cmd_flush_profile(args):
    """Exploratory, outside any measured leg: a throw-away Envoy of the arm at the shape's rung,
    primed, then `perf record -t <main tid>` over several flushes; the main thread's samples by
    symbol, split into reference counting and latching, histogram merge and quantiles, and the
    rest. Without a symbol table the split is skipped and said so."""
    exp = _load(args, check_rounds=False)
    arm = [a for a in exp["arms"] if a["name"] == args.arm]
    shape = [s for s in exp["shapes"] if s["name"] == args.shape]
    if not arm or not shape:
        sys.exit("unknown arm or shape")
    arm, shape = arm[0], shape[0]
    run_dir = _run_dir(dict(exp, name="%s-profile-%s-%s" % (exp["name"], arm["name"], shape["name"])), args.out)
    os.makedirs(os.path.join(run_dir, "logs"), exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    from .leg import RealBackend, nofile_for
    signal.signal(signal.SIGTERM, _on_term)
    bpath, _, _ = experiment.prepare_bootstraps(exp, run_dir, log)
    be = RealBackend(exp, run_dir, log)
    origin, _ = _side_services(exp, run_dir, log, exp["shapes"])
    aenv = experiment.arm_envoy(exp, arm, run_dir)
    elog_path = os.path.join(run_dir, "logs", "profile.envoy.log")
    data = os.path.join(run_dir, "perf.data")
    envoy = elog = None
    try:
        origin.start()
        envoy, elog = be._start_envoy(arm["binary"], bpath[arm["name"]], exp["cpus"]["sut"], exp["envoy"]["workers"],
                                      exp["envoy"]["admin_port"], dict(arm.get("env") or {}), [], elog_path,
                                      ready_timeout_s=float(shape.get("ready_timeout_s", 60)),
                                      nofile=nofile_for(aenv, exp))
        m = {}
        be._prime(m, arm, shape, aenv)
        print("primed: %s" % m.get("prime"))
        r = subprocess.run(exp["measure"]["perf"] + ["record", "-F", str(args.freq), "-t", str(envoy.pid), "-o", data,
                                                     "--", "sleep", str(args.seconds)],
                           capture_output=True, text=True, timeout=args.seconds + 120)
        if r.returncode != 0:
            sys.exit("perf record failed: %s" % r.stderr[-400:])
    finally:
        if envoy is not None:
            be._stop_envoy(envoy, elog, elog_path)
        origin.stop()
        be.close()
    rep = subprocess.run(exp["measure"]["perf"] + ["report", "-i", data, "--stdio", "--sort", "symbol", "--no-children"],
                         capture_output=True, text=True, timeout=600)
    with open(os.path.join(run_dir, "perf-report.txt"), "w") as f:
        f.write(rep.stdout)
    rows = parse_perf_report(rep.stdout)
    named = sum(p for p, s in rows if not s.startswith("0x"))
    out = {"samples_by_symbol": rows[:40], "named_pct": named}
    if named < 50.0:
        out["split"] = None
        out["note"] = "the binary has no usable symbol table (%.0f%% of samples named): split skipped" % named
    else:
        out["split"] = classify_profile(rows)
    with open(os.path.join(run_dir, "profile.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "samples_by_symbol"}, indent=1))
    for p, s in rows[:15]:
        print("%6.2f%%  %s" % (p, s[:140]))


def cmd_portability_check(args):
    from . import portability
    problems = portability.check_dirs(args.dirs)
    for p in problems:
        print("PORTABILITY %s" % p)
    print("portability-check: %s (%d problems, %d boxes)" % ("PASS" if not problems else "FAIL", len(problems),
                                                             len(args.dirs)))
    sys.exit(1 if problems else 0)


def cmd_scrub(args):
    from .sysprobe import scrub_tree
    for p in scrub_tree(os.path.expanduser(args.run_dir)):
        print(p)


def cmd_selftest(args):
    import unittest
    suite = unittest.defaultTestLoader.discover(os.path.join(REPO, "tests"), top_level_dir=REPO)
    r = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    sys.exit(0 if r.wasSuccessful() else 1)


# ---------------------------------------------------------------- remote

def _ssh(host, cmd, inp=None, capture=True, timeout=600):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", host, cmd], input=inp,
                          capture_output=capture, timeout=timeout)


def _harness_tar():
    ver = experiment.harness_version().encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for top in ("epl", "bin", "tests", "examples"):
            p = os.path.join(REPO, top)
            if os.path.isdir(p):
                t.add(p, arcname=top, filter=lambda ti: None if "__pycache__" in ti.name else ti)
        ti = tarfile.TarInfo("VERSION")
        ti.size = len(ver)
        t.addfile(ti, io.BytesIO(ver))
    return buf.getvalue(), ver.decode()


def _check_root(root):
    if not root or root.startswith("/") or root.startswith("~") or ".." in root.split("/") \
            or not all(c.isalnum() or c in "._-/" for c in root):
        sys.exit("--root must be a non-empty relative path under the ssh home (got %r)" % root)


def remote_ship(host, root):
    _check_root(root)
    data, ver = _harness_tar()
    r = _ssh(host, "rm -rf %s/harness.new && mkdir -p %s/harness.new && tar -xz -C %s/harness.new && "
                   "rm -rf %s/harness && mv %s/harness.new %s/harness"
             % ((shlex.quote(root),) * 6), inp=data)
    if r.returncode != 0:
        sys.exit("ship failed: %s" % r.stderr.decode()[-500:])
    return "%s/harness/bin/epl" % root, ver


def _pull_root(args):
    """--root after the action ends up in the REMAINDER list; take it from there too,
    so `remote HOST ship --root X` cannot silently ship to the default root."""
    rest = list(args.rest)
    for i, x in enumerate(rest):
        if x == "--root" and i + 1 < len(rest):
            args.root = rest[i + 1]
            del rest[i:i + 2]
            break
        if x.startswith("--root="):
            args.root = x.split("=", 1)[1]
            del rest[i]
            break
    args.rest = rest


def cmd_remote(args):
    _pull_root(args)
    host, root = args.host, args.root
    _check_root(root)
    if args.action == "ship":
        tool, ver = remote_ship(host, root)
        print("shipped %s to %s:%s" % (ver, host, tool))
        return
    if args.action in ("run", "calibrate", "plan"):
        tool, ver = remote_ship(host, root)
        cfg_remote = "%s/configs/%s" % (root, os.path.basename(args.rest[0]))
        with open(args.rest[0], "rb") as f:
            r = _ssh(host, "mkdir -p %s/configs && cat > %s" % (shlex.quote(root), shlex.quote(cfg_remote)),
                     inp=f.read())
        if r.returncode != 0:
            sys.exit("config copy failed")
        extra = list(args.rest[1:])
        if args.action == "run" and "--detach" not in extra and not args.foreground:
            extra.append("--detach")
        cmd = "python3 %s %s %s %s" % (tool, args.action, shlex.quote(cfg_remote), " ".join(shlex.quote(x) for x in extra))
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", host, cmd], timeout=None)
        sys.exit(r.returncode)
    if args.action == "status":
        tool = "%s/harness/bin/epl" % root
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", host, "python3 %s status %s" % (tool, shlex.quote(args.rest[0]))])
        sys.exit(r.returncode)
    if args.action == "fetch":
        rd, local = args.rest[0], os.path.expanduser(args.rest[1])
        os.makedirs(local, exist_ok=True)
        p = subprocess.Popen(["ssh", "-o", "BatchMode=yes", host, "tar -C %s -cz %s" % (
            shlex.quote(os.path.dirname(rd.rstrip("/"))), shlex.quote(os.path.basename(rd.rstrip("/"))))],
            stdout=subprocess.PIPE)
        subprocess.run(["tar", "-xz", "-C", local], stdin=p.stdout, check=True)
        p.wait()
        print(os.path.join(local, os.path.basename(rd.rstrip("/"))))
        return
    sys.exit("unknown remote action")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="epl", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    def common(p):
        p.add_argument("--set", action="append", metavar="KEY=VALUE",
                       help="override a config value, dotted key, JSON value (repeatable)")

    p = sp.add_parser("plan")
    p.add_argument("config")
    p.add_argument("--rounds", type=int, help="minimum rounds")
    p.add_argument("--max-rounds", type=int)
    p.add_argument("--fixed", action="store_true", help="run exactly --rounds, no adaptive blocks")
    p.add_argument("--allow-short", action="store_true")
    common(p)
    p.set_defaults(fn=cmd_plan)
    p = sp.add_parser("render")
    p.add_argument("config")
    common(p)
    p.set_defaults(fn=cmd_render, allow_short=True)
    p = sp.add_parser("run")
    p.add_argument("config")
    p.add_argument("--out")
    p.add_argument("--rounds", type=int, help="minimum rounds")
    p.add_argument("--max-rounds", type=int)
    p.add_argument("--fixed", action="store_true", help="run exactly --rounds, no adaptive blocks")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--detach", action="store_true")
    p.add_argument("--allow-short", action="store_true")
    common(p)
    p.set_defaults(fn=cmd_run)
    p = sp.add_parser("calibrate")
    p.add_argument("config")
    p.add_argument("--arm", required=True)
    p.add_argument("--shape", required=True)
    p.add_argument("--rps", required=True)
    p.add_argument("--out")
    common(p)
    p.set_defaults(fn=cmd_calibrate, allow_short=True)
    p = sp.add_parser("probe")
    p.add_argument("config")
    p.add_argument("--shape", required=True)
    p.add_argument("--rps", required=True)
    p.add_argument("--reps", type=int, default=2)
    p.add_argument("--out")
    common(p)
    p.set_defaults(fn=cmd_probe, allow_short=True)
    p = sp.add_parser("status")
    p.add_argument("run_dir")
    p.add_argument("--lines", type=int, default=15)
    p.set_defaults(fn=cmd_status)
    p = sp.add_parser("report")
    p.add_argument("results")
    p.add_argument("--floor", help="A/A results.json whose half-widths are printed as the floor")
    p.add_argument("--floor-arm", help="use only this arm's comparisons of --floor (an A/A arm inside another run)")
    p.add_argument("--reanalyse", action="store_true", help="recompute the analysis from the legs")
    p.set_defaults(fn=cmd_report)
    p = sp.add_parser("evidence-check")
    p.add_argument("spec")
    p.add_argument("run_dir", nargs="+")
    p.add_argument("--freeze", metavar="OUT", help="resolve ref items from these legs and write the frozen spec")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_evidence_check)
    p = sp.add_parser("request-probe")
    p.add_argument("config")
    p.add_argument("--arm", required=True)
    p.add_argument("--shape", required=True)
    p.add_argument("--trace", help="component log levels, e.g. lua:trace,wasm:trace")
    p.add_argument("--expect", action="append", metavar="NAME=VALUE", help="response header (NAME= : absent)")
    p.add_argument("--lines", type=int, default=40)
    p.add_argument("--out")
    common(p)
    p.set_defaults(fn=cmd_request_probe, allow_short=True)
    p = sp.add_parser("stats-calibrate")
    p.add_argument("config")
    p.add_argument("--arm", required=True)
    p.add_argument("--shapes", required=True)
    p.add_argument("--ready-timeout", type=float)
    p.add_argument("--admin-timeout", type=float)
    p.add_argument("--out")
    common(p)
    p.set_defaults(fn=cmd_stats_calibrate, allow_short=True)
    p = sp.add_parser("flush-profile")
    p.add_argument("config")
    p.add_argument("--arm", required=True)
    p.add_argument("--shape", required=True)
    p.add_argument("--seconds", type=int, default=10)
    p.add_argument("--freq", type=int, default=999)
    p.add_argument("--out")
    common(p)
    p.set_defaults(fn=cmd_flush_profile, allow_short=True)
    p = sp.add_parser("portability-check")
    p.add_argument("dirs", nargs="+")
    p.set_defaults(fn=cmd_portability_check)
    p = sp.add_parser("scrub")
    p.add_argument("run_dir")
    p.set_defaults(fn=cmd_scrub)
    p = sp.add_parser("selftest")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_selftest)
    p = sp.add_parser("remote")
    p.add_argument("host")
    p.add_argument("action", choices=["ship", "run", "calibrate", "plan", "status", "fetch"])
    p.add_argument("--root", default="epl", help="directory on the bench box, relative to the ssh home")
    p.add_argument("--foreground", action="store_true")
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_remote)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
