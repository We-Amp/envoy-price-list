"""Event-study support: what one event (a runtime change, an origin fault) costs inside one Envoy process.

- **The scheduler** fires a declared event at declared times on CLOCK_MONOTONIC (offsets from the run's start)
  and, for an event with `hold_s`, its revert at fire + hold_s. Every action is logged with its planned and actual
  instant; an action later than `max_late_ms`, a failed action or an action that never fired makes the run invalid.
- **The null event** (`null: true`; or "alternate": real and null slots counterbalanced R N N R, K a multiple of 4)
  runs the same trigger, the same calls at the same instants, with no effect (NULL_EXECUTES says what a null still
  executes, per kind).
- **Expected errors** (`expected_errors`): the non-2xx codes an event run declares. Inside a real event's declared
  interval only the declared codes; outside every interval, and around every null event, 0 non-2xx; the counter
  gates (timeouts, connect failures, overflows, retries) 0 unless declared; the SUT's 5xx accounted for by the
  origin cluster's 5xx unless declared local codes allow it.
- **The estimands** per event, on a **bracketing baseline** (the median over pre_s before
  a guard bin, and over pre_s after the post window, interpolated linearly), on 1 s or finer perf bins:
  extra cycles and extra instructions, extra cycles per post-window request (counted requests),
  **t95** (the primary recovery figure), the settled time against a **frozen band** from a separate null
  calibration run, and the peak worker max/mean (read only as real peak minus null peak).
- **Across instances**: per instance (real - null), the t interval across instances, never across
  events in one process; a mix of null-subtracted and raw instances is refused.

Every figure is "in-process effect, Exploratory, steering only"; anything to be published goes through a
pre-registered between-process session (`between_instances`).
"""

import hashlib
import json
import math
import re
import threading
import time

from . import stats

KINDS = ("runtime", "origin_fault")
LABEL = "in-process effect, Exploratory, steering only"
# what a null event still executes, per kind (a null that is a no-op where the real event is not is no A/A)
NULL_EXECUTES = {
    "runtime": "the same POST /runtime_modify of the same key with the value in effect (the runtime snapshot is "
               "rebuilt and posted to every worker, as for a real write) and the same /runtime read-back",
    "origin_fault": "the same POST /runtime_modify of all four fault keys on the origin with the values in effect, the "
                    "same /runtime read-back and the same origin counter reads; the SUT sees no change",
}
EVENT_KEYS = {"kind", "at_s", "hold_s", "params", "null", "run_s", "pre_s", "post_s", "perf_interval_ms",
              "worker_sample_s", "max_late_ms", "warm_s", "lead_in_s", "expected_errors", "recovery",
              "fault_effect", "hang_factor", "calibration", "shape_client_check"}
ERROR_KEYS = {"codes", "window", "source", "local_codes", "counters", "max_share", "slack_s"}
CODE_RE = re.compile(r"^[1345][0-9][0-9]$")
UPSTREAM_CODE_RE = re.compile(r"^cluster\.origin\.upstream_rq_([1-5][0-9][0-9])$")
SUT_CLASSES = ("1xx", "3xx", "4xx", "5xx")
# the cluster counters that stand in for the response flags (UT, UF, UO, retries); 0 unless declared
COUNTER_GATES = ("cluster.origin.upstream_rq_timeout", "cluster.origin.upstream_cx_connect_fail",
                 "cluster.origin.upstream_rq_pending_overflow", "cluster.origin.upstream_cx_overflow",
                 "cluster.origin.upstream_rq_retry")
# the admin scrape's filter: the same in event and null runs, one scrape per perf bin edge
SCRAPE_FILTER = (r"^(http\.ingress_http\.downstream_rq_([1-5]xx|completed)|cluster\.origin\.upstream_rq_([1-5][0-9][0-9]|"
                 r"[1-5]xx|pending_overflow|timeout|retry|total)|cluster\.origin\.upstream_cx_(overflow|connect_fail))$")
CALIBRATION_KEYS = {"from", "band_pct", "quantile", "bin_ms", "sigma_cycles_per_bin", "n_instances", "n_bins",
                    "sha256"}
CENSOR_MAX = 0.25      # a median recovery across instances only if at most a quarter of events are censored
NULL_NOT_RECOVERED_MAX = 0.05  # the session's nulls under the frozen band


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---------------------------------------------------------------- validation

def event_errors(ev):
    """The event section's own checks (the driver adds the arm and origin checks)."""
    errs = []
    if not isinstance(ev, dict):
        return ["an event-block config needs an event section"]
    bad = sorted(set(ev) - EVENT_KEYS)
    if bad:
        errs.append("event: unknown keys %s" % bad)
    if ev.get("kind") not in KINDS:
        errs.append("event.kind must be one of %s" % (KINDS,))
    at = ev.get("at_s")
    if not (isinstance(at, list) and at and all(num(x) and x > 0 for x in at)
            and all(b > a for a, b in zip(at, at[1:]))):
        errs.append("event.at_s must be a non-empty, strictly increasing list of seconds > 0")
        at = []
    for k, lo in (("run_s", 1), ("pre_s", 1), ("post_s", 1)):
        if not (num(ev.get(k)) and ev[k] >= lo):
            errs.append("event.%s must be a number >= %s" % (k, lo))
    hold = ev.get("hold_s")
    if hold is not None and not (num(hold) and hold > 0):
        errs.append("event.hold_s must be a number > 0")
    if ev.get("kind") == "origin_fault" and hold is None:
        errs.append("an origin_fault event needs event.hold_s (the fault is reverted after it)")
    if ev.get("null", False) not in (False, True, "alternate"):
        errs.append("event.null must be false, true or \"alternate\"")
    if ev.get("null") == "alternate" and len(at) % 4:
        errs.append("event.null alternate needs a multiple of 4 events (the slots are counterbalanced R N N R)")
    iv = ev.get("perf_interval_ms", 1000)
    if not (isinstance(iv, int) and not isinstance(iv, bool) and iv >= 100):
        errs.append("event.perf_interval_ms must be whole ms >= 100")
        iv = 1000
    ws = ev.get("worker_sample_s", 0.25)
    if not (num(ws) and 0.01 <= ws <= iv / 4000.0):
        errs.append("event.worker_sample_s must be in [0.01, perf_interval_ms / 4000] (at least 4 samples per bin)")
    if ev.get("max_late_ms") is not None and not (num(ev["max_late_ms"]) and ev["max_late_ms"] > 0):
        errs.append("event.max_late_ms must be a number > 0")
    for k, lo in (("warm_s", 0), ("lead_in_s", 1)):
        if ev.get(k) is not None and not (num(ev[k]) and ev[k] >= lo):
            errs.append("event.%s must be a number >= %s" % (k, lo))
    if ev.get("hang_factor") is not None and not (num(ev["hang_factor"]) and ev["hang_factor"] >= 1):
        errs.append("event.hang_factor must be >= 1")
    if all(num(ev.get(k)) for k in ("run_s", "pre_s", "post_s")):
        pre, post, run = float(ev["pre_s"]), float(ev["post_s"]), float(ev["run_s"])
        guard = iv / 1000.0
        if pre < post:
            errs.append("event.pre_s must be >= post_s (the baseline's own error dominates otherwise)")
        if hold is not None and num(hold) and hold >= post:
            errs.append("event.post_s must exceed hold_s (the recovery is read after the revert)")
        if at:
            # the guard bin and pre_s before each event; post_s, then the bracketing post-post window (pre_s) after it
            if at[0] < pre + guard:
                errs.append("event.at_s[0] %.2f leaves less than pre_s + one guard bin (%.2f s) of baseline"
                            % (at[0], pre + guard))
            for a, b in zip(at, at[1:]):
                if b - a < post + pre + pre + guard:
                    errs.append("events at %.2f and %.2f s: the analysis windows overlap (spacing must be >= post_s + "
                                "pre_s (bracketing) + pre_s + one guard bin = %.2f s)" % (a, b, post + 2 * pre + guard))
            if at[-1] + post + pre > run:
                errs.append("the last event's bracketing window ends after run_s")
    errs += expected_errors_errors(ev.get("expected_errors"))
    rc = ev.get("recovery")
    if rc is not None:
        if not isinstance(rc, dict) or set(rc) - {"consecutive_bins", "basis"}:
            errs.append("event.recovery takes consecutive_bins and basis (the band comes frozen from event.calibration)")
        else:
            cb = rc.get("consecutive_bins", 3)
            if not (isinstance(cb, int) and not isinstance(cb, bool) and cb >= 1):
                errs.append("event.recovery.consecutive_bins must be a whole number >= 1")
            if rc.get("basis", "cycles_per_s") not in ("cycles_per_s", "cycles_per_req"):
                errs.append("event.recovery.basis must be cycles_per_s (open loop, constant rate) or cycles_per_req "
                            "(counted per-bin requests)")
    errs += calibration_errors(ev.get("calibration"), iv)
    fe = ev.get("fault_effect")
    if fe is not None:
        if ev.get("kind") != "origin_fault" or not isinstance(fe, dict) or set(fe) - {"z", "min_requests"}:
            errs.append("event.fault_effect (origin_fault only) takes z and min_requests")
        elif not (num(fe.get("z", 5.0)) and fe.get("z", 5.0) > 0 and isinstance(fe.get("min_requests", 200), int)
                  and fe.get("min_requests", 200) >= 1):
            errs.append("event.fault_effect: z > 0, min_requests a whole number >= 1")
    sc = ev.get("shape_client_check")
    if sc is not None and not (isinstance(sc, str) and sc.strip()):
        errs.append("event.shape_client_check names the client-check result of this shape's client")
    return errs


def calibration_errors(cal, interval_ms):
    if cal is None:
        return []
    errs = []
    if not isinstance(cal, dict) or set(cal) - CALIBRATION_KEYS:
        return ["event.calibration takes %s (a frozen calibrate() record)" % sorted(CALIBRATION_KEYS)]
    if not (num(cal.get("band_pct")) and cal["band_pct"] > 0):
        errs.append("event.calibration.band_pct must be a number > 0")
    if not (isinstance(cal.get("from"), str) and cal["from"].strip()):
        errs.append("event.calibration.from names the separate null calibration run(s)")
    if cal.get("bin_ms") != interval_ms:
        errs.append("event.calibration.bin_ms %s differs from event.perf_interval_ms %s: a band holds at its own bin "
                    "size only" % (cal.get("bin_ms"), interval_ms))
    if cal.get("sha256") is not None and cal["sha256"] != calibration_sha256(cal):
        errs.append("event.calibration.sha256 does not match its content (the band is frozen)")
    return errs


def expected_errors_errors(decl):
    if decl is None:
        return []
    errs = []
    if not isinstance(decl, dict) or set(decl) - ERROR_KEYS:
        return ["event.expected_errors takes %s" % sorted(ERROR_KEYS)]
    codes = decl.get("codes")
    if not (isinstance(codes, list) and codes and all(isinstance(c, str) and CODE_RE.match(c) for c in codes)
            and len(set(codes)) == len(codes)):
        errs.append("event.expected_errors.codes must be distinct non-2xx status codes as strings (\"503\")")
        codes = []
    if decl.get("window", "hold+post") not in ("hold", "hold+post"):
        errs.append("event.expected_errors.window must be hold or hold+post")
    src = decl.get("source", "upstream")
    if src not in ("upstream", "any"):
        errs.append("event.expected_errors.source must be upstream (accounted for by the origin cluster's codes) "
                    "or any (with local_codes)")
    lc = decl.get("local_codes")
    if src == "any" and not (isinstance(lc, list) and lc and all(c in codes for c in lc)):
        errs.append("event.expected_errors.source any must name its local_codes (a subset of codes)")
    if src != "any" and lc is not None:
        errs.append("event.expected_errors.local_codes is for source any")
    cn = decl.get("counters")
    if cn is not None and not (isinstance(cn, list) and all(c in COUNTER_GATES for c in cn)):
        errs.append("event.expected_errors.counters must be among %s" % (COUNTER_GATES,))
    if decl.get("max_share") is not None and not (num(decl["max_share"]) and 0 < decl["max_share"] <= 1):
        errs.append("event.expected_errors.max_share must be a share in (0, 1]")
    if decl.get("slack_s") is not None and not (num(decl["slack_s"]) and 0 <= decl["slack_s"] <= 5):
        errs.append("event.expected_errors.slack_s must be in [0, 5] s")
    return errs


def is_null(ev, k):
    """Whether event k (0-based) is a null event. "alternate": slots R N N R repeated (counterbalanced)."""
    n = ev.get("null", False)
    return n is True or (n == "alternate" and k % 4 in (1, 2))


def plan(ev):
    """[(offset s, event k, phase "on"|"off", null)] in time order."""
    out = []
    for k, t in enumerate(ev["at_s"]):
        out.append((float(t), k, "on", is_null(ev, k)))
        if ev.get("hold_s") is not None:
            out.append((float(t) + float(ev["hold_s"]), k, "off", is_null(ev, k)))
    return sorted(out)


# ---------------------------------------------------------------- the scheduler

class Scheduler(threading.Thread):
    """Fires plan(ev) at t0_ns + offset. `action(k, phase, null)` does the trigger and returns a dict with "ok"
    (a raised exception is a failed action, recorded). `log(event, detail)` is the event log."""

    def __init__(self, ev, t0_ns, action, log=None, clock_ns=time.monotonic_ns):
        super().__init__(daemon=True)
        self.ev = ev
        self.t0_ns = int(t0_ns)
        self.action = action
        self.log = log or (lambda e, d="": None)
        self.clock_ns = clock_ns
        self.stop_evt = threading.Event()
        self.planned = plan(ev)
        self.fired = []

    def run(self):
        for off, k, phase, null in self.planned:
            due = self.t0_ns + int(off * 1e9)
            while not self.stop_evt.is_set():
                wait = (due - self.clock_ns()) / 1e9
                if wait <= 0:
                    break
                self.stop_evt.wait(min(wait, 0.05) if wait < 0.2 else wait - 0.1)
            if self.stop_evt.is_set():
                return
            t = self.clock_ns()
            self.log("event_%s" % phase, "k=%d null=%s planned_s=%.3f" % (k, null, off))
            try:
                rec = dict(self.action(k, phase, null) or {})
            except Exception as ex:  # noqa: BLE001 - a failed trigger is recorded; the run is invalid
                rec = {"ok": False, "error": "%s: %s" % (type(ex).__name__, ex)}
            t2 = self.clock_ns()
            rec.update(k=k, phase=phase, null=null, planned_ns=due, fired_ns=t, done_ns=t2,
                       late_ms=round((t - due) / 1e6, 3), took_ms=round((t2 - t) / 1e6, 3))
            self.fired.append(rec)
            self.log("event_%s_done" % phase, "k=%d ok=%s late_ms=%.3f took_ms=%.3f" % (
                k, rec.get("ok"), rec["late_ms"], rec["took_ms"]))

    def record(self):
        """{ok, reasons, fired}: every planned action fired, ok, and within max_late_ms of its instant."""
        why = []
        lim = float(self.ev.get("max_late_ms", 50))
        if len(self.fired) != len(self.planned):
            why.append("%d of %d event actions fired" % (len(self.fired), len(self.planned)))
        for r in self.fired:
            if not r.get("ok"):
                why.append("event %d %s failed: %s" % (r["k"], r["phase"], r.get("error") or r.get("reasons")))
            if r["late_ms"] > lim:
                why.append("event %d %s fired %.1f ms late (limit %.1f)" % (r["k"], r["phase"], r["late_ms"], lim))
        return {"ok": not why, "reasons": why, "fired": self.fired}


# ---------------------------------------------------------------- the admin scrape at the bin edges

def admin_scrape(port, timeout=5.0):
    """{stat: value} of the SCRAPE_FILTER stats from the SUT's admin."""
    import http.client
    import urllib.parse
    c = http.client.HTTPConnection("127.0.0.1", int(port), timeout=timeout)
    try:
        c.request("GET", "/stats?filter=" + urllib.parse.quote(SCRAPE_FILTER))
        r = c.getresponse()
        body = r.read().decode(errors="replace")
    finally:
        c.close()
    if r.status != 200:
        raise RuntimeError("admin /stats returned %d" % r.status)
    out = {}
    for line in body.splitlines():
        k, sep, v = line.partition(": ")
        if sep:
            try:
                out[k.strip()] = int(v.strip())
            except ValueError:
                pass
    return out


class EdgeScraper(threading.Thread):
    """One admin scrape per perf bin edge: trigger(t) when perf's interval t is printed (and once at perf's
    start, t = 0); each sample is stamped on the tools side when its answer arrives. The per-bin request counts
    are then counts between two edges, never interpolations."""

    def __init__(self, read, cpus=None, clock_ns=time.monotonic_ns):
        super().__init__(daemon=True)
        import queue
        self.read = read
        self.cpus = cpus
        self.clock_ns = clock_ns
        self.q = queue.Queue()
        self.stop_evt = threading.Event()
        self.samples = []
        self.errors = []

    def trigger(self, t, ns=None):
        self.q.put(float(t))

    def _one(self, t):
        a = self.clock_ns()
        try:
            st = self.read()
        except Exception as ex:  # noqa: BLE001 - recorded
            self.errors.append({"t": t, "error": "%s: %s" % (type(ex).__name__, ex)})
            return
        b = self.clock_ns()
        self.samples.append({"t": t, "mono_ns": b, "read_ms": round((b - a) / 1e6, 3), "stats": st})

    def run(self):
        import os
        import queue
        if self.cpus and hasattr(os, "sched_setaffinity"):
            try:
                os.sched_setaffinity(0, self.cpus)
            except OSError as ex:
                self.errors.append({"error": "affinity: %s" % ex})
        while True:
            try:
                t = self.q.get(timeout=0.05)
            except queue.Empty:
                if self.stop_evt.is_set():
                    return
                continue
            self._one(t)

    def record(self, origin_ns, tol_ms):
        """{ok, reasons, n, offsets}: every edge scraped once, its answer within tol_ms of the edge."""
        why = []
        if self.errors:
            why.append("%d admin scrapes failed (first: %s)" % (len(self.errors), self.errors[0].get("error")))
        if len(self.samples) < 2:
            why.append("fewer than 2 admin scrapes")
        offs = [edge_offset_ms(s, origin_ns) for s in self.samples] if origin_ns is not None else []
        late = [o for o in offs if abs(o) > tol_ms]
        return {"ok": not why, "reasons": why, "n": len(self.samples),
                "max_abs_edge_offset_ms": round(max((abs(o) for o in offs), default=0.0), 3),
                "edges_outside_tolerance": len(late), "tolerance_ms": tol_ms,
                "max_read_ms": max((s["read_ms"] for s in self.samples), default=None)}


def edge_offset_ms(s, origin_ns):
    return (s["mono_ns"] - (origin_ns + int(round(s["t"] * 1e9)))) / 1e6


def scrape_deltas(scrapes):
    """Consecutive deltas of the scrapes (in arrival order): [{t0_ns, t1_ns, ok2xx, classes: {5xx: n}, upstream:
    {503: n}, upstream_5xx, counters: {name: n}}]."""
    scrapes = sorted(scrapes, key=lambda s: s["mono_ns"])
    out = []
    for a, b in zip(scrapes, scrapes[1:]):
        sa, sb = a["stats"], b["stats"]
        d = lambda k: (sb.get(k, 0) - sa.get(k, 0))  # noqa: E731
        up = {}
        for k in set(sa) | set(sb):
            m = UPSTREAM_CODE_RE.match(k)
            if m and not m.group(1).startswith("2") and d(k):
                up[m.group(1)] = d(k)
        out.append({"t0_ns": a["mono_ns"], "t1_ns": b["mono_ns"], "ok2xx": d("http.ingress_http.downstream_rq_2xx"),
                    "classes": {c: d("http.ingress_http.downstream_rq_%s" % c) for c in SUT_CLASSES
                                if d("http.ingress_http.downstream_rq_%s" % c)},
                    "upstream": up, "upstream_5xx": d("cluster.origin.upstream_rq_5xx"),
                    "counters": {k: d(k) for k in COUNTER_GATES if d(k)}})
    return out


def allowed_intervals(ev, fired):
    """[(lo_ns, hi_ns, k)] where a real event's declared codes may appear: its "on" instant to its "off" instant
    (window "hold") or to on + post_s (window "hold+post"), widened by slack_s at both ends. Null events have none."""
    decl = ev.get("expected_errors")
    if not decl:
        return []
    slack = int(float(decl.get("slack_s", 1.0)) * 1e9)
    on = {r["k"]: r["fired_ns"] for r in fired if r["phase"] == "on" and not r["null"]}
    off = {r["k"]: r["done_ns"] for r in fired if r["phase"] == "off" and not r["null"]}
    out = []
    for k, t in sorted(on.items()):
        if decl.get("window", "hold+post") == "hold":
            end = off.get(k, t + int(float(ev.get("hold_s") or ev["post_s"]) * 1e9))
        else:
            end = t + int(float(ev["post_s"]) * 1e9)
        out.append((t - slack, end + slack, k))
    return out


def expected_errors_check(ev, fired, deltas, client_non2xx=None):
    """Fail closed on any non-2xx or counter the declarations do not allow (module docstring). Returns {ok,
    reasons, per_event: {k: {codes, classes, errors, requests, share}}, outside_non2xx, counters}."""
    decl = ev.get("expected_errors") or {}
    codes = set(decl.get("codes") or [])
    classes = {c[0] + "xx" for c in codes}
    src = decl.get("source", "upstream")
    local_classes = {c[0] + "xx" for c in decl.get("local_codes") or []}
    allow_counters = set(decl.get("counters") or [])
    allowed = allowed_intervals(ev, fired)
    why = []
    per = {}
    outside = 0
    seen_counters = {}
    for d in deltas:
        hit = [k for lo, hi, k in allowed if d["t0_ns"] < hi and d["t1_ns"] > lo]
        for name, n in d["counters"].items():
            seen_counters[name] = seen_counters.get(name, 0) + n
            if name not in allow_counters or not hit:
                why.append("%s %d in the scrape interval ending %.3f s (%s)" % (
                    name, n, d["t1_ns"] / 1e9, "not declared" if name not in allow_counters else
                    "outside every declared interval"))
        bad = sum(d["classes"].values())
        if not bad and not d["upstream"]:
            continue
        if not hit:
            outside += bad
            why.append("non-2xx %s (origin %s) outside every declared interval (scrape interval ending %.3f s)"
                       % (d["classes"], d["upstream"], d["t1_ns"] / 1e9))
            continue
        k = hit[0]
        e = per.setdefault(k, {"codes": {}, "classes": {}, "errors": 0, "requests": 0, "upstream_5xx": 0})
        for c, n in d["classes"].items():
            e["classes"][c] = e["classes"].get(c, 0) + n
            if c not in classes:
                why.append("event %d: SUT %s %d not declared (declared %s)" % (k, c, n, sorted(codes)))
        for c, n in d["upstream"].items():
            e["codes"][c] = e["codes"].get(c, 0) + n
            if c not in codes:
                why.append("event %d: origin code %s %d not declared (declared %s)" % (k, c, n, sorted(codes)))
        e["errors"] += bad
    # the accounting over each event's whole allowed interval, not per scrape interval. The
    # router charges cluster.origin.upstream_rq_<code> when the upstream headers arrive and the HCM charges
    # downstream_rq_<class> when it encodes, and one /stats read renders cluster.* before http.*, so one response can
    # land in adjacent scrape intervals on the two sides; the slack puts the interval's ends in error-free scrapes.
    for d in deltas:
        for lo, hi, k in allowed:
            if d["t0_ns"] < hi and d["t1_ns"] > lo:
                e = per.setdefault(k, {"codes": {}, "classes": {}, "errors": 0, "requests": 0, "upstream_5xx": 0})
                e["requests"] += d["ok2xx"] + sum(d["classes"].values())
                e["upstream_5xx"] += d["upstream_5xx"]
                break
    for k, e in sorted(per.items()):
        for c, n in sorted(e["classes"].items()):
            up = sum(v for x, v in e["codes"].items() if x in codes and x[0] + "xx" == c)
            if n > up and not (src == "any" and c in local_classes):
                why.append("event %d: SUT %s %d not accounted for by the origin's declared codes (%d) over the "
                           "event's interval: a local reply? (declare source any with its local_codes if it is "
                           "expected)" % (k, c, n, up))
        if e["classes"].get("5xx", 0) > e["upstream_5xx"] and not (src == "any" and "5xx" in local_classes):
            why.append("event %d: SUT 5xx %d above the origin cluster's 5xx %d over the event's interval" % (
                k, e["classes"]["5xx"], e["upstream_5xx"]))
    per = {k: e for k, e in per.items() if e["errors"] or e["codes"]}
    for k, e in per.items():
        e["share"] = e["errors"] / float(e["requests"]) if e["requests"] else None
        if decl.get("max_share") is not None and (e["share"] is None or e["share"] > decl["max_share"]):
            why.append("event %d: non-2xx share %s above the declared %.3f" % (k, e["share"], decl["max_share"]))
    for name, n in sorted((client_non2xx or {}).items()):
        c = name.rsplit("_", 1)[-1]
        if n and c not in classes:
            why.append("client %s %d not a declared class" % (name, n))
    return {"ok": not why, "reasons": why, "per_event": per, "outside_non2xx": outside, "counters": seen_counters,
            "declared": sorted(codes), "label": "Observed (count)",
            "allowed_intervals": [(lo, hi, k) for lo, hi, k in allowed]}


# ---------------------------------------------------------------- per-bin series

def cycles_of(counts):
    if "cycles:u" in counts and "cycles:k" in counts:
        return counts["cycles:u"] + counts["cycles:k"]
    return counts.get("cycles")


def instructions_of(counts):
    """instructions u + k; None without both."""
    if "instructions:u" in counts and "instructions:k" in counts:
        return counts["instructions:u"] + counts["instructions:k"]
    return None


def requests_per_bin(bins, scrapes, origin_ns, tol_ms):
    """Completed requests (2xx + non-2xx at the SUT) per perf bin, COUNTED: the difference of the scrapes taken
    at the bin's two edges (EdgeScraper), each answer within tol_ms of its edge; None otherwise (never
    interpolated)."""
    by_t = {}
    for s in scrapes:
        by_t.setdefault(round(s["t"], 6), s)
    tot = lambda s: sum(s["stats"].get("http.ingress_http.downstream_rq_%s" % c, 0)  # noqa: E731
                        for c in ("1xx", "2xx", "3xx", "4xx", "5xx"))
    out = []
    for b in bins:
        a, c = by_t.get(round(b["t_rel0"], 6)), by_t.get(round(b["t_rel"], 6))
        if a is None or c is None or origin_ns is None or abs(edge_offset_ms(a, origin_ns)) > tol_ms \
                or abs(edge_offset_ms(c, origin_ns)) > tol_ms:
            out.append(None)
        else:
            out.append(tot(c) - tot(a))
    return out


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    pos = q * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _center(b):
    return (b["t0_ns"] + b["t1_ns"]) / 2.0


def bracket(bins, pre, pp, value):
    """The bracketing baseline of a per-second quantity: f(tau) linear between the median over the pre bins (at
    their mean centre) and the median over the post-post bins (at theirs)."""
    m0 = median([value(bins[i]) for i in pre])
    m1 = median([value(bins[i]) for i in pp])
    c0 = sum(_center(bins[i]) for i in pre) / len(pre)
    c1 = sum(_center(bins[i]) for i in pp) / len(pp)
    return (lambda tau: m0 + (m1 - m0) * (tau - c0) / (c1 - c0)), m0, m1


# ---------------------------------------------------------------- estimands

def event_estimands(ev, fired, bins, reqs, wcpu, errors=None):
    """Per event (by its "on" action), on the bracketing baseline (one guard bin before t_e excluded):
    extra cycles and instructions, extra cycles per post-window request (counted), t95 (the primary recovery
    figure), the settled time against the frozen band (secondary; censored when not reached), the per-bin deviations
    (for calibrate()), the peak worker max/mean and peak deviation (max-type: read only as real minus null), and
    the errors. An event whose windows lack data is incomplete, with its reasons."""
    pre_s, post_s = float(ev["pre_s"]), float(ev["post_s"])
    rc = ev.get("recovery") or {}
    kcons = int(rc.get("consecutive_bins", 3))
    basis = rc.get("basis", "cycles_per_s")
    cal = ev.get("calibration") or {}
    band = cal.get("band_pct")
    sigma = cal.get("sigma_cycles_per_bin")
    iv = bins[0]["dt_s"] if bins else 1.0
    out = []
    for r in [x for x in fired if x["phase"] == "on"]:
        t = r["fired_ns"]
        why = []
        before = [i for i, b in enumerate(bins) if b["t1_ns"] <= t]
        guard = before[-1] if before else None
        pre = [i for i in before[:-1] if bins[i]["t0_ns"] >= bins[guard]["t0_ns"] - int(pre_s * 1e9)] if before else []
        post = [i for i, b in enumerate(bins) if b["t1_ns"] > t and b["t0_ns"] < t + int(post_s * 1e9)]
        pend = bins[post[-1]]["t1_ns"] if post else t
        pp = [i for i, b in enumerate(bins) if b["t0_ns"] >= pend and b["t1_ns"] <= pend + int(pre_s * 1e9)]
        rec = {"k": r["k"], "null": r["null"], "fired_ns": t, "basis": LABEL, "baseline": "bracketing",
               "guard_bin": guard is not None, "pre_bins": len(pre), "post_bins": len(post), "postpost_bins": len(pp)}
        need = lambda s: max(1, int(0.8 * s / max(iv, 1e-9)))  # noqa: E731
        if len(pre) < need(pre_s):
            why.append("%d pre bins (want >= 80%% of pre_s)" % len(pre))
        if len(post) < need(post_s):
            why.append("%d post bins (want >= 80%% of post_s)" % len(post))
        if len(pp) < need(pre_s):
            why.append("%d post-post bins (want >= 80%% of pre_s: the bracketing baseline)" % len(pp))
        span = pre + post + pp
        if any(cycles_of(bins[i]["counts"]) is None for i in span):
            why.append("a bin without cycles")
        if any(instructions_of(bins[i]["counts"]) is None for i in span):
            why.append("a bin without instructions u + k")
        if any(wcpu[i] is None for i in span):
            why.append("a bin without per-worker CPU")
        if basis == "cycles_per_req" and any(reqs[i] is None for i in span):
            why.append("a bin without a counted request count (recovery.basis cycles_per_req)")
        if why:
            rec.update(complete=False, reasons=why)
            out.append(rec)
            continue
        cps = lambda b: cycles_of(b["counts"]) / b["dt_s"]  # noqa: E731
        ips = lambda b: instructions_of(b["counts"]) / b["dt_s"]  # noqa: E731
        fc, c0, c1 = bracket(bins, pre, pp, cps)
        fi, _, _ = bracket(bins, pre, pp, ips)
        xc = [cycles_of(bins[i]["counts"]) - fc(_center(bins[i])) * bins[i]["dt_s"] for i in post]
        xi = [instructions_of(bins[i]["counts"]) - fi(_center(bins[i])) * bins[i]["dt_s"] for i in post]
        excess, excess_i = sum(xc), sum(xi)
        counted = all(reqs[i] is not None for i in post)
        nreq = sum(reqs[i] for i in post) if counted else None
        # t95: when the cumulative excess cycles reach 95% of the post-window total
        t95 = None
        if excess > 0:
            cum, goal = 0.0, 0.95 * excess
            for i, x in zip(post, xc):
                if x > 0 and cum + x >= goal:
                    tau = bins[i]["t0_ns"] + (goal - cum) / x * (bins[i]["t1_ns"] - bins[i]["t0_ns"])
                    t95 = max(0.0, (tau - t) / 1e9)
                    break
                cum += x
        # the settled time (secondary): per-bin deviation from the bracketing baseline, on cycles per second
        # (nominal denominator) or on cycles per counted request
        if basis == "cycles_per_req":
            fq, _, _ = bracket(bins, pre, pp, lambda b: cycles_of(b["counts"]) / reqs[bins.index(b)])
            dev = [abs(cycles_of(bins[i]["counts"]) / reqs[i] / fq(_center(bins[i])) - 1.0) * 100 for i in post]
        else:
            dev = [abs(cps(bins[i]) / fc(_center(bins[i])) - 1.0) * 100 for i in post]
        rec.update(complete=True, baseline_cycles_per_s=[c0, c1], excess_cycles=excess, excess_instructions=excess_i,
                   post_requests=nreq,
                   excess_cycles_per_post_window_request=excess / nreq if nreq else None,
                   t95_s=t95, t95_note=None if excess > 0 else "no positive excess",
                   post_devs_pct=[round(d, 6) for d in dev], peak_dev_pct=max(dev),
                   post_residual_cycles=[round(x, 3) for x in xc],
                   context_pre_median_worker_max_over_mean=median(
                       [wcpu[i]["max_over_mean"] for i in pre if wcpu[i]["max_over_mean"] is not None]),
                   peak_worker_max_over_mean=max((wcpu[i]["max_over_mean"] for i in post
                                                  if wcpu[i]["max_over_mean"] is not None), default=None),
                   peak_main_cores=max((wcpu[i]["main_cores"] for i in post if wcpu[i]["main_cores"] is not None),
                                       default=None),
                   recovery_basis=basis,
                   series=[{"bin_t0_s": round((bins[i]["t0_ns"] - t) / 1e9, 3), "excess_cycles": round(x, 1),
                            "excess_instructions": round(y, 1), "dev_pct": round(d, 4),
                            "requests": reqs[i], "worker_max_over_mean": wcpu[i]["max_over_mean"],
                            "main_cores": wcpu[i]["main_cores"]} for i, x, y, d in zip(post, xc, xi, dev)])
        if sigma is not None:
            # var(excess) = P sigma^2 + P^2 var(baseline), the bracketing baseline averaging two medians
            P, nb = len(post), (len(pre) + len(pp)) / 2.0
            rec["excess_se_cycles"] = math.sqrt(P * sigma ** 2 + P ** 2 * (1.2533 * sigma) ** 2 / (2 * nb))
        if band is None:
            rec["settled"] = "Not resolved (no frozen band in event.calibration)"
        else:
            rec["settled_band_pct"] = band
            rec["settled_s"] = None
            rec["censored"] = True
            for j in range(len(dev) - kcons + 1):
                if all(d <= band for d in dev[j:j + kcons]):
                    rec["settled_s"] = max(0.0, (bins[post[j]]["t0_ns"] - t) / 1e9)
                    rec["censored"] = False
                    break
            if rec["censored"]:
                rec["settled"] = "not recovered within post_s"
        if errors is not None:
            rec["errors"] = (errors.get("per_event") or {}).get(r["k"], {"codes": {}, "errors": 0})
        out.append(rec)
    return out


def band_check(estimands):
    """The frozen band applied to the session's own null events: at most 5% "not recovered" and a median
    settled time of 0; otherwise the band is invalid for this session and every settled time is "Not resolved"."""
    nul = [e for e in estimands if e.get("null") and e.get("complete") and "censored" in e]
    if not nul:
        return {"ok": None, "reading": "no null events under a frozen band in this session", "n": 0}
    cens = sum(1 for e in nul if e["censored"]) / float(len(nul))
    med = median([e["settled_s"] for e in nul if not e["censored"]] or [float("inf")])
    ok = cens <= NULL_NOT_RECOVERED_MAX and med == 0.0
    return {"ok": ok, "n": len(nul), "null_not_recovered_share": round(cens, 4), "null_median_settled_s": med,
            "reading": "band holds for this session" if ok else "Not resolved: the frozen band fails on this "
                                                               "session's nulls"}


def calibration_sha256(rec):
    body = {k: v for k, v in rec.items() if k != "sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def calibrate(null_instances, source, bin_ms, q=0.99, min_instances=6):
    """The frozen band from a SEPARATE null calibration run: the q-quantile of every per-bin |deviation| over
    all complete null events of at least min_instances instances; sigma, the SD of the per-bin residual cycles
    (the bracketing baseline's noise model), and their lag-1 autocorrelation. Raises ValueError below min_instances or
    with a real event among them."""
    devs, res, lag = [], [], []
    n = 0
    for inst in null_instances:
        ests = [e for e in inst if e.get("complete")]
        if any(not e["null"] for e in inst):
            raise ValueError("a calibration run holds null events only")
        if not ests:
            continue
        n += 1
        for e in ests:
            devs += e["post_devs_pct"]
            r = e["post_residual_cycles"]
            res += r
            lag += list(zip(r, r[1:]))
    if n < min_instances:
        raise ValueError("a calibration needs >= %d null instances with complete events, got %d" % (min_instances, n))
    sd = stats.stdev(res) if len(res) >= 2 else None
    mx = sum(res) / len(res) if res else 0.0
    ac = None
    if lag and sd:
        ac = sum((a - mx) * (b - mx) for a, b in lag) / len(lag) / sd ** 2
    rec = {"from": source, "band_pct": round(quantile(devs, q), 6), "quantile": q, "bin_ms": int(bin_ms),
           "sigma_cycles_per_bin": sd, "n_instances": n, "n_bins": len(devs)}
    rec["lag1_autocorrelation"] = ac
    rec = {k: v for k, v in rec.items() if k in CALIBRATION_KEYS or k == "lag1_autocorrelation"}
    out = {k: v for k, v in rec.items() if k in CALIBRATION_KEYS}
    out["sha256"] = calibration_sha256(out)
    return out, {"lag1_autocorrelation": ac, "mean_residual_cycles": mx}


# ---------------------------------------------------------------- across instances

def _tint(xs, conf=0.95):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    sd = stats.stdev(xs)
    hw = stats.t_ppf(0.5 + conf / 2.0, n - 1) * sd / math.sqrt(n)
    return {"mean": m, "sd": sd, "df": n - 1, "interval": [m - hw, m + hw], "conf": conf}


def cost_reading(xs, margin=None):
    """The decision lines for a cost row: "detected" if the 95% t interval excludes 0; "cheap" only by
    equivalence (the 90% t interval inside +-margin, declared before data); otherwise "Not resolved"."""
    t95, t90 = _tint(xs, 0.95), _tint(xs, 0.90)
    if t95 is None:
        return {"reading": "Not resolved"}
    lo, hi = t95["interval"]
    if lo > 0 or hi < 0:
        r = "detected"
    elif margin is not None and -margin <= t90["interval"][0] and t90["interval"][1] <= margin:
        r = "cheap (equivalence within +-%s)" % margin
    else:
        r = "Not resolved"
    return dict(t95, interval90=t90["interval"], reading=r)


def across_instances(instances, mode="alternate", min_instances=6, margin=None, within_s=None):
    """Across process instances (the hybrid rule); the interval is the spread across instances, never across events
    in one process. instances: [{"name", "estimands"}] (or lists of estimands).

    mode "alternate": every instance holds its own nulls; per instance, the mean of its real events minus the mean of
    its nulls, for excess cycles, excess instructions, the peak worker max/mean and the peak deviation (max-type
    figures only as real peak minus null peak over windows of the same length). An instance without any null is a
    mix and is refused (ValueError); an instance with fewer than 2 complete real or 2 complete null events is
    dropped by name. mode "real": real-only instances (their nulls are separate instances: between_instances).

    Fewer than min_instances kept: every row "Not resolved". The recovery row is t95 over the real events (the
    censored count per instance; a median settled time only if at most a quarter are censored; "recovers within X s"
    only if none is censored and t95's upper end is under X). A cycles excess with no instructions excess is
    labelled "Measured [mechanism]: idle-state or frequency effect". Also: null after real against null after null."""
    norm = [i if isinstance(i, dict) else {"name": "instance-%d" % n, "estimands": i} for n, i in enumerate(instances)]
    if mode not in ("alternate", "real"):
        raise ValueError("mode must be alternate or real")
    has_null = [any(e.get("null") for e in i["estimands"]) for i in norm]
    if mode == "alternate" and not all(has_null):
        raise ValueError("a mix of null-subtracted and raw instances is refused: %s hold no null event" % [
            i["name"] for i, h in zip(norm, has_null) if not h])
    if mode == "real" and any(has_null):
        raise ValueError("mode real takes real-only instances (their nulls are separate instances)")
    kept, dropped = [], []
    rows = {"excess_cycles": [], "excess_instructions": [], "peak_worker_max_over_mean": [], "peak_dev_pct": [],
            "t95_s": [], "carry_over": []}
    censored = {}
    settled = []
    for inst in norm:
        ev = [e for e in inst["estimands"] if e.get("complete")]
        real = [e for e in ev if not e["null"]]
        nul = [e for e in ev if e["null"]]
        if len(real) < 2 or (mode == "alternate" and len(nul) < 2):
            dropped.append({"name": inst["name"], "why": "%d complete real and %d complete null events (want >= 2 "
                                                         "each)" % (len(real), len(nul))})
            continue
        kept.append(inst["name"])
        mean = lambda es, k: sum(e[k] for e in es) / len(es)  # noqa: E731
        sub = lambda k: mean(real, k) - (mean(nul, k) if mode == "alternate" else 0.0)  # noqa: E731
        for k in ("excess_cycles", "excess_instructions", "peak_dev_pct"):
            rows[k].append(sub(k))
        pk = [e for e in real if e.get("peak_worker_max_over_mean") is not None]
        pn = [e for e in nul if e.get("peak_worker_max_over_mean") is not None]
        if pk and (pn or mode == "real"):
            rows["peak_worker_max_over_mean"].append(
                mean(pk, "peak_worker_max_over_mean") - (mean(pn, "peak_worker_max_over_mean") if pn else 0.0))
        t95s = [e["t95_s"] for e in real if e.get("t95_s") is not None]
        if t95s:
            rows["t95_s"].append(sum(t95s) / len(t95s))
        censored[inst["name"]] = sum(1 for e in real if e.get("censored"))
        settled += [e for e in real if "censored" in e]
        if mode == "alternate":
            # a null right after a real slot against a null right after a null slot (R N N R: k%4 1 vs 2)
            order = sorted(ev, key=lambda e: e["k"])
            after_real = [e["excess_cycles"] for p, e in zip(order, order[1:]) if e["null"] and not p["null"]]
            after_null = [e["excess_cycles"] for p, e in zip(order, order[1:]) if e["null"] and p["null"]]
            if after_real and after_null:
                rows["carry_over"].append(sum(after_real) / len(after_real) - sum(after_null) / len(after_null))
    enough = len(kept) >= min_instances
    out = {"basis": LABEL, "mode": mode, "n_instances": len(kept), "kept": kept, "dropped": dropped,
           "null_subtracted": mode == "alternate", "min_instances": min_instances}
    for k in ("excess_cycles", "excess_instructions"):
        r = cost_reading(rows[k], margin.get(k) if isinstance(margin, dict) else None)
        r["per_instance"] = rows[k]
        if not enough:
            r["reading"] = "Not resolved (fewer than %d instances)" % min_instances
        out[k] = r
    c, i = out["excess_cycles"], out["excess_instructions"]
    if c.get("reading") == "detected" and i.get("reading") != "detected":
        c["label"] = "Measured [mechanism]: idle-state or frequency effect (cycles move, instructions do not)"
    for k in ("peak_worker_max_over_mean", "peak_dev_pct"):
        r = _tint(rows[k]) or {}
        r.update(per_instance=rows[k], definition="real peak minus null peak, same window length",
                 reading=("Not resolved (fewer than %d instances)" % min_instances) if not enough or not r
                 else "interval across instances")
        out[k] = r
    nc = sum(censored.values())
    ne = len(settled)
    r = _tint(rows["t95_s"]) or {}
    r.update(per_instance=rows["t95_s"], censored_per_instance=censored, primary="t95")
    if not enough or not rows["t95_s"]:
        r["reading"] = "Not resolved (fewer than %d instances)" % min_instances
    elif within_s is not None and nc == 0 and r.get("interval") and r["interval"][1] < within_s:
        r["reading"] = "recovers within %s s" % within_s
    else:
        r["reading"] = "t95 with its interval"
    if ne and nc / float(ne) <= CENSOR_MAX:
        r["median_settled_s"] = median([e["settled_s"] for e in settled if not e["censored"]])
    elif ne:
        r["settled_reading"] = "not recovered within post_s (%d of %d events censored)" % (nc, ne)
    out["recovery"] = r
    co = _tint(rows["carry_over"]) or {}
    co.update(per_instance=rows["carry_over"], basis="Exploratory",
              reading=("spacing too short: null after real differs from null after null"
                       if co.get("interval") and (co["interval"][0] > 0 or co["interval"][1] < 0)
                       else "no carry-over detected" if co.get("interval") else "not computed"))
    out["carry_over"] = co
    return out


def between_instances(real_instances, null_instances, min_each=8, margin=None):
    """The between-process confirmation a published row needs: real-only instances against null-only instances
    (at least min_each of each, randomized order by the plan); the difference of the per-instance means of excess
    cycles and instructions with a Welch interval. Below min_each of either: "Not resolved"."""
    def per(insts, null):
        out = {"excess_cycles": [], "excess_instructions": []}
        for inst in insts:
            es = inst["estimands"] if isinstance(inst, dict) else inst
            es = [e for e in es if e.get("complete") and bool(e["null"]) == null]
            if es:
                for k in out:
                    out[k].append(sum(e[k] for e in es) / len(es))
        return out
    r, n = per(real_instances, False), per(null_instances, True)
    res = {"basis": "between-process (pre-registered session only)", "n_real": len(r["excess_cycles"]),
           "n_null": len(n["excess_cycles"])}
    for k in ("excess_cycles", "excess_instructions"):
        a, b = r[k], n[k]
        if len(a) < min_each or len(b) < min_each:
            res[k] = {"reading": "Not resolved (fewer than %d instances of each)" % min_each}
            continue
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        va, vb = stats.stdev(a) ** 2 / len(a), stats.stdev(b) ** 2 / len(b)
        se = math.sqrt(va + vb)
        df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1)) if (va + vb) > 0 else len(a) + len(b) - 2
        hw = stats.t_ppf(0.975, max(1, int(df))) * se
        d = ma - mb
        reading = "detected" if d - hw > 0 or d + hw < 0 else "Not resolved"
        res[k] = {"difference": d, "interval": [d - hw, d + hw], "df": df, "reading": reading}
    return res
