#!/usr/bin/env python3
"""The hybrid screen: a screen of one candidate (a runtime guard or key)
runs N >= 6 short Envoy process instances. Each instance is one flip block (loop/flipblock.py): one warm
Envoy, one continuous client, runtime flips between windows, P counterbalanced control pairs (A = off, B = on), then
the in-instance A/A pair(s) (B, C: the on value written twice). The interval is taken ACROSS INSTANCES, the instance
being the unit (df N - 1); within-instance pairs only estimate each instance's effect.

Every number is labelled "in-process effect, Exploratory". There is no calibration factor and no 0.34 widening. A
screen never gives a published row: a survivor becomes a candidate record for a pre-registered between-process
confirmation session, and only that session gives a verdict.

This module holds the spec validation, the per-instance flip-block config and the analysis. It starts nothing."""
import copy
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from epl import nighthawk, stats  # noqa: E402

BASIS = "in-process effect, Exploratory"
NOT_PUBLISHED = ("not a published row: an in-process screen; publication needs a pre-registered between-process "
                 "confirmation session")
MIN_INSTANCES = 6
MAX_INSTANCES = 40
FLIP_EXTRA = ("cycle_connections", "window_items", "rate_tolerance")
SPEC_KEYS = {"arm", "key", "off", "on", "shape", "rate", "instances", "pairs", "aa_pairs", "window_s", "gap_s",
             "warm_s", "lead_in_s", "marker_min", "aa_marker_max", "note", "repeat_of"}
READ_POINTS = ("per_request", "per_connection", "per_config")
LABELS = {
    "instances": BASIS + ": per instance, the mean over its control pairs of d = 100 ln(c_on / c_off) (cycles u+k "
                         "per SUT 2xx), within one Envoy process",
    "across": BASIS + ": the t interval across instances (instance = unit, df N - 1); no 0.34 widening, no "
                      "calibration factor",
    "within": BASIS + ": the per-pair SD pooled within instances (each instance's mean removed); describes the "
                      "in-process resolution only",
    "instance_sd": BASIS + ": the between-instance SD component, sqrt(max(0, var(instance means) - s_w^2 / P))",
    "marker": BASIS + ": instructions:u per request, off - on, per instance; shows whether the flip reaches the "
                      "request path",
    "aa": BASIS + ": the in-instance A/A pair(s): the on value written twice; the across-instance interval must "
                  "contain 0",
    "validity": "every planned instance valid (flipblock's per-window and per-block items, plus ours off the SUT "
                "CPUs and siblings); at least %d instances; no replacement" % MIN_INSTANCES,
}


# ---------------------------------------------------------------- the spec

def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def spec_errors(spec, cfg):
    """Everything wrong with a screen spec against the daemon config (fail closed; nothing has started)."""
    errs = []
    if not isinstance(spec, dict):
        return ["the screen spec is an object"]
    bad = sorted(set(spec) - SPEC_KEYS)
    if bad:
        errs.append("unknown spec keys %s" % bad)
    arms = cfg.get("arms") or {}
    arm = arms.get(spec.get("arm"))
    if arm is None:
        errs.append("arm must be one of the staged arms %s" % sorted(arms))
        arm = {}
    keys = arm_keys(arm)
    if spec.get("key") not in keys:
        errs.append("key must be one of the arm's candidate keys %s" % sorted(keys))
    else:
        # a key's declared read point. A guard read when a config is built is never reached by a runtime flip
        # (a restart design, not built); one read when a connection is built needs a new client per window
        rp = read_point(arm, spec["key"])
        if rp == "per_config":
            errs.append("key %s is read when a config is built: a runtime flip never reaches it (no restart "
                        "design yet)" % spec["key"])
        elif rp == "per_connection" and not (arm.get("flip_extra") or {}).get("cycle_connections"):
            errs.append("key %s is read when a connection is built: the arm needs flip_extra.cycle_connections"
                        % spec["key"])
    for k in ("off", "on"):
        if not isinstance(spec.get(k), (bool, int, float, str)) or spec.get(k) is None:
            errs.append("%s: the runtime value written for the %s state (bool, number or string)" % (k, k))
    if "off" in spec and spec.get("off") == spec.get("on"):
        errs.append("off and on must differ (a screen flips the key)")
    shapes = cfg.get("shapes") or {}
    if spec.get("shape") not in shapes:
        errs.append("shape must be one of %s" % sorted(shapes))
    elif arm.get("shapes") is not None and spec["shape"] not in arm["shapes"]:
        errs.append("arm %s runs only the shapes %s" % (spec.get("arm"), sorted(arm["shapes"])))
    rate = spec.get("rate")
    if not (_int(rate) and rate > 0):
        errs.append("rate: a whole total req/s > 0")
    elif rate > int(cfg.get("max_rps", 20000)):
        errs.append("rate %d is above the daemon's ceiling %d" % (rate, int(cfg.get("max_rps", 20000))))
    n = spec.get("instances")
    if not (_int(n) and MIN_INSTANCES <= n <= MAX_INSTANCES):
        errs.append("instances: whole, %d..%d (the hybrid design's floor is %d short Envoy instances)" % (
            MIN_INSTANCES, MAX_INSTANCES, MIN_INSTANCES))
    p = spec.get("pairs")
    if not (_int(p) and 2 <= p <= 16):
        errs.append("pairs: control pairs per instance, whole, 2..16")
    elif _int(n) and p % 2 and n % 2:
        # with P odd the mirrored order balances first and second positions over PAIRS of instances only
        errs.append("pairs odd needs an even number of instances (the order balances over instance pairs)")
    a = spec.get("aa_pairs", 1)
    if not (_int(a) and 1 <= a <= 4):
        errs.append("aa_pairs: A/A pairs per instance, whole, 1..4 (every screen carries its A/A check)")
    lo = int(cfg.get("min_window_s", 5))
    w = spec.get("window_s", 10)
    if not (_int(w) and lo <= w <= 60):
        errs.append("window_s: whole seconds, %d..60" % lo)
    for k, dflt, low, high in (("gap_s", 2.0, 1.0, 10.0), ("warm_s", 5.0, 0.0, 30.0), ("lead_in_s", 2.0, 1.0, 10.0)):
        v = spec.get(k, dflt)
        if not (_num(v) and low <= v <= high):
            errs.append("%s: a number in %s..%s" % (k, low, high))
    for k in ("marker_min", "aa_marker_max"):
        if spec.get(k) is not None and not (_num(spec[k]) and spec[k] > 0):
            errs.append("%s: a positive number (instructions per request) or absent" % k)
    if spec.get("note") is not None and not (isinstance(spec["note"], str) and len(spec["note"]) <= 500):
        errs.append("note: a string of at most 500 characters")
    ro = spec.get("repeat_of")
    if ro is not None and not (isinstance(ro, str) and ro.startswith("scr") and ro[3:].isdigit()):
        errs.append("repeat_of: the id of an earlier screen of this session (scrNN)")
    return errs


def arm_keys(arm):
    """An arm's candidate keys: a list, or {key: {"read_point": ...}}."""
    k = (arm or {}).get("keys") or []
    return sorted(k) if isinstance(k, dict) else list(k)


def read_point(arm, key):
    k = (arm or {}).get("keys")
    if isinstance(k, dict):
        rp = (k.get(key) or {}).get("read_point")
        return rp if rp in READ_POINTS else None
    return None


def runtime_text(v):
    """The runtime value as Envoy's admin layer gets it (flipblock's runtime_text): false and "false" are one."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def screen_key(spec):
    """The register's key for the repeat rule: (arm, key, shape). A second screen of the same one in a
    session names repeat_of; a rate ladder of one key is a family, each rung naming the screen it repeats."""
    return [spec.get("arm"), spec.get("key"), spec.get("shape")]


def screen_values(spec):
    """The rest of the screen's identity, kept in the register entry: the normalised values and the rate."""
    return {"off": runtime_text(spec.get("off")), "on": runtime_text(spec.get("on")), "rate": spec.get("rate")}


def control_order(pairs, k):
    """Instance k's control-pair order: flipblock's counterbalanced order (AB BA BA AB ...), mirrored on odd
    instances so that A and B also balance across instances when P is not a multiple of 4."""
    from_fb = " ".join("AB" if i % 4 in (0, 3) else "BA" for i in range(int(pairs)))
    if k % 2:
        from_fb = from_fb.replace("AB", "xy").replace("BA", "AB").replace("xy", "BA")
    return from_fb


def aa_order(aa_pairs, k):
    """The A/A pairs (B and C: the on value written twice), alternating BC / CB by pair and instance."""
    return " ".join("BC" if (i + k) % 2 == 0 else "CB" for i in range(int(aa_pairs)))


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def instance_raw(cfg, spec, screen_id, k, workdir):
    """The raw flip-block config of instance k (0-based): the arm's base config, the daemon config's overrides,
    one shape at the screen's rate, and a flip section of kind "pairs" (labels A off, B on, C on)."""
    arm = cfg["arms"][spec["arm"]]
    with open(os.path.expanduser(arm["base"])) as f:
        raw = json.load(f)
    raw = deep_merge(raw, arm.get("overrides") or {})
    shape = dict(cfg["shapes"][spec["shape"]], rps=int(spec["rate"]))
    raw["name"] = "%s-i%02d" % (screen_id, k + 1)
    raw["shapes"] = [shape]
    raw["workdir"] = workdir
    raw["measure"] = dict(raw.get("measure") or {}, window_s=int(spec.get("window_s", 10)),
                          lead_in_s=float(spec.get("lead_in_s", 2.0)))
    # the A/A pair(s) first on even-numbered instances (k odd, 0-based) and last on odd-numbered ones, so both
    # ends of an instance are A/A-checked across the screen
    ctl, aa = control_order(spec["pairs"], k), aa_order(spec.get("aa_pairs", 1), k)
    order = (aa + " " + ctl) if k % 2 else (ctl + " " + aa)
    raw["flip"] = {"key": spec["key"], "values": {"A": spec["off"], "B": spec["on"], "C": spec["on"]},
                   "order": order, "kind": "pairs", "counterbalanced": False, "gating": False,
                   "window_s": int(spec.get("window_s", 10)), "gap_s": float(spec.get("gap_s", 2.0)),
                   "warm_s": float(spec.get("warm_s", 5.0)), "lead_in_s": float(spec.get("lead_in_s", 2.0)),
                   "cycle_connections": False, "hang_factor": 1.5, "rate_tolerance": float(
                       cfg.get("rate_tolerance", 0.005))}
    # an arm whose guard is read when a connection is built (the relay-write guard on a tcp_proxy arm) carries
    # flipblock's own settings for it: a new client per window and its bulk items
    raw["flip"].update({k: v for k, v in (arm.get("flip_extra") or {}).items() if k in FLIP_EXTRA})
    return raw


def control_variant(raw, spec):
    """The same instance as a flipblock "control" block (A/B only, the counterbalanced order), so flipblock's own
    validation (flip_errors) checks the arm, the admin layer, the perf events, the CPUs and the client recipe."""
    v = copy.deepcopy(raw)
    v["flip"] = dict(v["flip"], kind="control", values={"A": spec["off"], "B": spec["on"]},
                     order=" ".join("AB" if i % 4 in (0, 3) else "BA" for i in range(int(spec["pairs"]))),
                     counterbalanced=True)
    return v


def rate_error(cfg, spec):
    """The client's worker count must divide the total rate (by design: never rounded)."""
    arm = cfg["arms"][spec["arm"]]
    try:
        with open(os.path.expanduser(arm["base"])) as f:
            raw = deep_merge(json.load(f), arm.get("overrides") or {})
        nighthawk.per_worker_rps(spec["rate"], (raw.get("client") or {}).get("concurrency", 4))
    except (OSError, ValueError) as ex:
        return str(ex)
    return None


def planned_instance_s(spec, cfg=None):
    """flipblock.plan's arithmetic: start-up, the warm-up and lead-in, and per window the window plus the gap (plus,
    for an arm that cycles connections, a new client's warm-up, lead-in, exit and hash per window)."""
    w = int(spec.get("window_s", 10))
    warm, lead = float(spec.get("warm_s", 5.0)), float(spec.get("lead_in_s", 2.0))
    n_win = 2 * (int(spec["pairs"]) + int(spec.get("aa_pairs", 1)))
    per = w + float(spec.get("gap_s", 2.0))
    arm = ((cfg or {}).get("arms") or {}).get(spec.get("arm")) or {}
    if (arm.get("flip_extra") or {}).get("cycle_connections"):
        per += warm + lead + 2.0 + 1.0
    return 20.0 + warm + lead + n_win * per


# ---------------------------------------------------------------- the analysis

def _pairs_of(block):
    """[(first label, second label, window a, window b)] of a block's windows (pairs are windows 1-2, 3-4, ...)."""
    ws = (block or {}).get("windows") or []
    return [(ws[i]["label"], ws[i + 1]["label"], ws[i], ws[i + 1]) for i in range(0, len(ws) - 1, 2)]


def _cyc(w):
    return ((w or {}).get("per_req") or {}).get("cycles_total")


def _ins(w):
    return ((w or {}).get("per_req") or {}).get("instructions_u")


def instance_figures(block, n_pairs=None):
    """One instance's control d values, markers, and A/A d values and |markers|, from its windows. Pairs are told
    apart by their labels (A/B control, B/C A/A), wherever they sit in the instance."""
    ctl, mk, aa, aam = [], [], [], []
    for la, lb, wa, wb in _pairs_of(block):
        labs = {la: wa, lb: wb}
        if set(labs) == {"A", "B"}:
            off, on = labs["A"], labs["B"]
            if _cyc(off) and _cyc(on):
                ctl.append(100.0 * math.log(_cyc(on) / _cyc(off)))
                mk.append(_ins(off) - _ins(on))
        elif set(labs) == {"B", "C"}:
            b, c = labs["B"], labs["C"]
            if _cyc(b) and _cyc(c):
                aa.append(100.0 * math.log(_cyc(c) / _cyc(b)))
                aam.append(abs(_ins(b) - _ins(c)))
    return ctl, mk, aa, aam


def t_interval(xs):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    sd = stats.stdev(xs)
    hw = stats.t_ppf(0.975, n - 1) * sd / math.sqrt(n)
    return {"n": n, "df": n - 1, "mean": m, "sd": sd, "lo": m - hw, "hi": m + hw, "hw": hw}


def mde(sd, n):
    """Two-sided 5%, 80% power, at df n - 1."""
    return (stats.t_ppf(0.975, n - 1) + stats.t_ppf(0.80, n - 1)) * sd / math.sqrt(n)


def _r(x, k=4):
    return None if x is None else round(x, k)


def analyze(spec, blocks, screen_id=None, status=None):
    """The screen's result from its instance records (block.json dicts, in instance order; None for an instance
    not run). `status`: "complete" (every planned instance ran), "interim" or "aborted". Only a complete, valid
    screen can mark a candidate."""
    planned = int(spec["instances"])
    P = int(spec["pairs"])
    ran = [b for b in blocks if b is not None]
    status = status or ("complete" if len(ran) == planned else "interim")
    out = _analyze(spec, blocks, screen_id, status, planned, P, ran)
    return out if status == "complete" else blinded(out)


def _analyze(spec, blocks, screen_id, status, planned, P, ran):
    inst = []
    for k, b in enumerate(blocks):
        if b is None:
            continue
        ctl, mk, aa, aam = instance_figures(b, P)
        rec = {"instance": k + 1, "valid": bool(b.get("valid")), "reasons": list(b.get("reasons") or [])[:12],
               "n_pairs": len(ctl), "effect_lp": _r(sum(ctl) / len(ctl)) if ctl else None,
               "sd_lp": _r(stats.stdev(ctl)) if len(ctl) >= 2 else None, "d_lp": [_r(x) for x in ctl],
               "marker_ins_per_req": _r(sum(mk) / len(mk), 2) if mk else None,
               "aa_lp": _r(sum(aa) / len(aa)) if aa else None,
               "aa_marker_abs_ins_per_req": _r(sum(aam) / len(aam), 2) if aam else None,
               "envoy_pid": b.get("envoy_pid"), "ours": (b.get("loop") or {}).get("ours")}
        if rec["valid"] and (len(ctl) != P or len(aa) != int(spec.get("aa_pairs", 1))):
            rec["valid"] = False
            rec["reasons"].append("%d of %d control pairs and %d of %d A/A pairs have counts" % (
                len(ctl), P, len(aa), int(spec.get("aa_pairs", 1))))
        inst.append(rec)
    good = [r for r in inst if r["valid"]]
    out = {"basis": BASIS, "not_published": NOT_PUBLISHED, "labels": LABELS, "screen": screen_id,
           "status": status, "planned_instances": planned, "instances_run": len(ran),
           "instances_valid": len(good), "spec": spec, "instances": inst}
    # validity: every planned instance ran and is valid, and there are at least MIN_INSTANCES
    why = []
    if status != "complete":
        why.append("%s: %d of %d instances ran" % (status, len(ran), planned))
    bad = [r["instance"] for r in inst if not r["valid"]]
    if bad:
        why.append("invalid instances %s (no replacement)" % bad)
    if len(good) < MIN_INSTANCES:
        why.append("%d valid instances, fewer than %d" % (len(good), MIN_INSTANCES))
    out["validity"] = {"valid": not why, "reasons": why}
    # across instances (valid ones only); the interval is the screen's reading
    e = [r["effect_lp"] for r in good if r["effect_lp"] is not None]
    ti = t_interval(e)
    if ti:
        out["across"] = {"n": ti["n"], "df": ti["df"], "mean_lp": _r(ti["mean"]), "sd_between_lp": _r(ti["sd"]),
                         "t95_lp": [_r(ti["lo"]), _r(ti["hi"])],
                         "mean_simple_pct": _r(math.expm1(ti["mean"] / 100.0) * 100.0),
                         "mde_lp": _r(mde(ti["sd"], ti["n"]))}
    ss = df = 0
    for r in good:
        d = r["d_lp"]
        if len(d) >= 2:
            m = sum(d) / len(d)
            ss += sum((x - m) ** 2 for x in d)
            df += len(d) - 1
    if df:
        s_w = math.sqrt(ss / df)
        out["within"] = {"pooled_sd_lp": _r(s_w), "df": df}
        if ti:
            comp = ti["sd"] ** 2 - s_w ** 2 / P
            out["instance_sd_lp"] = _r(math.sqrt(comp) if comp > 0 else 0.0)
    # the marker: |off - on| per instance must reach marker_min with the same sign in every instance, so a key
    # whose on state ADDS instructions is screened without swapping off and on
    mks = [r["marker_ins_per_req"] for r in good if r["marker_ins_per_req"] is not None]
    mrec = {"per_instance": mks}
    tm = t_interval(mks)
    if tm:
        mrec.update(mean=_r(tm["mean"], 2), t95=[_r(tm["lo"], 2), _r(tm["hi"], 2)])
    signs = {(m > 0) - (m < 0) for m in mks}
    mrec["sign"] = {1: "on removes instructions", -1: "on adds instructions"}.get(signs.pop()) if len(
        signs) == 1 and 0 not in signs else "mixed"
    x = spec.get("marker_min")
    if x is not None:
        mrec["rule"] = "every valid instance's |marker| >= marker_min %s, one sign in every instance" % x
        mrec["reached"] = bool(mks) and mrec["sign"] != "mixed" and all(abs(m) >= x for m in mks)
    else:
        mrec["rule"] = "no marker_min given: the marker's across-instance interval excludes 0"
        mrec["reached"] = bool(tm) and (tm["lo"] > 0 or tm["hi"] < 0)
    out["marker"] = mrec
    # the A/A check
    aas = [r["aa_lp"] for r in good if r["aa_lp"] is not None]
    ta = t_interval(aas)
    arec = {"per_instance_lp": aas}
    if ta:
        arec.update(mean_lp=_r(ta["mean"]), t95_lp=[_r(ta["lo"]), _r(ta["hi"])],
                    contains_0=ta["lo"] <= 0.0 <= ta["hi"])
    else:
        arec["contains_0"] = False
    amax = spec.get("aa_marker_max")
    if amax is None and x is not None:
        amax = x / 4.0  # the marker's relation (X and X/4), never fail-open when a marker is set
        arec["marker_bound_rule"] = "aa_marker_max defaulted to marker_min / 4"
    am = [r["aa_marker_abs_ins_per_req"] for r in good if r["aa_marker_abs_ins_per_req"] is not None]
    arec["marker_abs_max"] = max(am) if am else None
    arec["marker_bound"] = amax
    if amax is None:
        arec["marker_ok"] = None
        arec["marker_bound_rule"] = "A/A marker unbounded (no marker_min and no aa_marker_max)"
    else:
        arec["marker_ok"] = bool(am) and max(am) < amax
    arec["ok"] = bool(arec["contains_0"]) and arec["marker_ok"] is not False
    out["aa"] = arec
    out["reading"], out["candidate"] = reading(out)
    return out


HIDDEN = ("across", "within", "instance_sd_lp", "marker", "aa")
HIDDEN_INSTANCE = ("effect_lp", "sd_lp", "d_lp", "marker_ins_per_req", "aa_lp", "aa_marker_abs_ins_per_req")


def blinded(out):
    """A screen that is not complete shows no effect figure. Interim: effects are hidden until it completes.
    Aborted: never shown. Per instance only valid, reasons and ours remain."""
    b = {k: v for k, v in out.items() if k not in HIDDEN}
    b["instances"] = [{k: v for k, v in r.items() if k not in HIDDEN_INSTANCE} for r in out["instances"]]
    if out["status"] == "aborted":
        b["reading"] = "ABORTED after %d of %d instances: Not resolved (%s); no effect figures are kept." % (
            out["instances_run"], out["planned_instances"], BASIS)
    else:
        b["reading"] = "INTERIM: effects are hidden until the screen is complete (%d of %d instances ran)." % (
            out["instances_run"], out["planned_instances"])
    b["candidate"] = False
    b["blinded"] = True
    return b


def reading(out):
    """(one sentence, candidate flag). The sentence always names the basis. Only complete screens get here
    unblinded (analyze blinds the rest)."""
    a = out.get("across")
    if not out["validity"]["valid"]:
        return "Not resolved (%s): %s." % (BASIS, "; ".join(out["validity"]["reasons"])), False
    if not a:
        return "Not resolved (%s): fewer than 2 valid instances." % BASIS, False
    if not out["aa"]["ok"]:
        return "Not resolved (%s): the in-screen A/A check failed (pairing, drift or the instruments)." % (
            BASIS), False
    if not out["marker"]["reached"]:
        return ("No marker (%s): the flip did not move the instructions on the request path; check where the "
                "guard is read. The cycles reading is not interpreted." % BASIS), False
    lo, hi = a["t95_lp"]
    if lo > 0 or hi < 0:
        txt = "%s: %+.3f lp [%+.3f, %+.3f] (%+.2f%%), %d instances; %s." % (
            BASIS, a["mean_lp"], lo, hi, a["mean_simple_pct"], a["n"], NOT_PUBLISHED)
        return txt[0].upper() + txt[1:], True
    return "No in-process effect resolved (%s): %+.3f lp [%+.3f, %+.3f], MDE %.3f lp at %d instances." % (
        BASIS, a["mean_lp"], lo, hi, a["mde_lp"], a["n"]), False


def candidate_record(result, screens_of_this_key=None, screens_in_session=None):
    """The session's record of a finished screen, which a later pre-registered plan imports (the two-tier
    rule). It is never a published row. It names every screen of the same key in the session (aborted and
    refused ones included) and the session's screen count (the family size), so the confirmation plan can choose
    its multiplicity rule. Only a candidate is called one; an aborted screen carries no effect figure."""
    s = result["spec"]
    a = result.get("across") or {}
    rec = {"basis": BASIS, "kind": ("candidate for a pre-registered between-process confirmation session"
                                    if result["candidate"] else "screen record, not a candidate"),
           "not_published": NOT_PUBLISHED, "screen": result["screen"], "status": result["status"],
           "validity_reasons": result["validity"]["reasons"], "arm": s["arm"], "key": s["key"],
           "off": s["off"], "on": s["on"], "shape": s["shape"], "rate": s["rate"], "repeat_of": s.get("repeat_of"),
           "instances_run": result["instances_run"], "instances_valid": result["instances_valid"],
           "pairs_per_instance": s["pairs"], "window_s": s.get("window_s", 10),
           "screens_of_this_key": screens_of_this_key or [], "screens_in_session": screens_in_session,
           "candidate": result["candidate"], "reading": result["reading"]}
    if result["status"] == "complete":
        rec.update(observed_in_process_lp=a.get("mean_lp"), t95_lp=a.get("t95_lp"),
                   instance_sd_lp=result.get("instance_sd_lp"), marker=(result.get("marker") or {}).get("mean"))
    return rec
