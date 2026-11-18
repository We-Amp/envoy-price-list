"""Evidence that an arm's feature ran: per-leg checks on Envoy's counters, fail-closed.

An arm may carry `evidence`: a list of items. Each item reads one value and states
what it must be, always with a tolerance (a window-edge request or a byte is never an
exact equality, except a count that must stay at zero, whose tolerance is written as 0).

    {"stat": NAME, "scope": "window" | "leg" | "field" | "config",
     one of:
       "per_request": X   value / denominator within tolerance of X
       "equals": X        value within tolerance of X
       "min": X, "max": Y value inside [X, Y] (either may be left out)
       "absent": true     no such value (a reference arm: the feature is not there)
       "present": true    the value exists (config scope)
     tolerance (per_request and equals need at least one):
       "tol": F           relative, a fraction of the expected value
       "tol_abs": F       absolute
       "tol_binomial_sd": K   K binomial standard deviations of the expected share,
                              sqrt(X (1 - X) / n), n = the denominator
     "per": "SCOPE:NAME"  denominator of per_request, or of min/max when given (default
                          for per_request: window -> the 2xx
                          responses in the window; leg -> the end-of-leg
                          http.ingress_http.downstream_rq_completed)
     "ref": {"arm": A | "self", "offset": D}
                          per_request is the mean per-request value of arm A in the
                          smoke legs plus D, written in by `epl evidence-check --freeze`;
                          an item with a ref that has not been frozen fails
     "shape": NAME or [NAMES]   the item applies only to legs of these shapes
     "label": text}
  A `stat` ending in "*" with `absent` means no stat with that prefix in the snapshot.

Scopes:
  window  counter delta over the perf window (`sut_stats_window` of the leg; the
          admin snapshots that bracket the window, zero deltas included)
  leg     the end-of-leg admin snapshot, taken just before Envoy is stopped
          (`sut_stats_leg_end`; cumulative since Envoy started, warm-up included)
  field   a value of the leg record, by dotted path (`access_log_lines`,
          `collector_delta.accepted_spans`, `tcmalloc_percpu_slab_bytes`)
  config  the arm's /config_dump, saved at the arm's first start: every occurrence
          of the key NAME, anywhere in the dump; `equals` needs all of them equal
          to X (and at least one), `present` at least one, `absent` none
"""

import gzip
import json
import math
import os

SCOPES = ("window", "leg", "field", "config")
KINDS = ("per_request", "equals", "min", "max", "absent", "present")
DEFAULT_PER = {"window": "field:responses_raw", "leg": "leg:http.ingress_http.downstream_rq_completed"}


def validate_items(items, arm_names=()):
    """Config errors of one arm's evidence list."""
    errs = []
    if not isinstance(items, list):
        return ["evidence must be a list"]
    if not items:
        return ["evidence is empty (an arm with evidence would pass vacuously; leave the key out instead)"]
    for i, it in enumerate(items):
        w = "evidence[%d]" % i
        if not isinstance(it, dict) or not it.get("stat"):
            errs.append("%s needs a stat" % w)
            continue
        w = "evidence[%d] (%s)" % (i, it["stat"])
        sc = it.get("scope", "window")
        if sc not in SCOPES:
            errs.append("%s: scope must be one of %s" % (w, SCOPES))
        kinds = [k for k in KINDS if k in it] or (["per_request"] if "ref" in it else [])
        if not kinds:
            errs.append("%s: needs one of %s" % (w, KINDS))
        if "equals" in it and ({"min", "max"} & set(kinds)):
            errs.append("%s: equals cannot be combined with min or max" % w)
        if ("per_request" in it or "ref" in it) and set(kinds) - {"per_request"}:
            errs.append("%s: per_request (or ref) cannot be combined with %s" % (w, sorted(set(kinds) - {"per_request"})))
        numeric = sc != "config" and not isinstance(it.get("equals"), (str, bool))
        if numeric and ("equals" in it or "per_request" in it or "ref" in it) and not any(
                k in it for k in ("tol", "tol_abs", "tol_binomial_sd")):
            errs.append("%s: needs a tolerance (tol, tol_abs or tol_binomial_sd; 0 for a count that must stay 0)" % w)
        if sc == "config" and set(kinds) - {"equals", "present", "absent"}:
            errs.append("%s: config scope takes equals, present or absent" % w)
        if "per" in it and (not isinstance(it["per"], str) or it["per"].split(":", 1)[0] not in SCOPES[:3]):
            errs.append("%s: per must be SCOPE:NAME with scope window, leg or field" % w)
        ref = it.get("ref")
        if ref is not None:
            if not isinstance(ref, dict) or not ref.get("arm"):
                errs.append("%s: ref needs an arm" % w)
            elif arm_names and ref["arm"] != "self" and ref["arm"] not in arm_names:
                errs.append("%s: ref arm %s is not an arm of this experiment" % (w, ref["arm"]))
    return errs


def _path(m, dotted):
    v = m
    for p in dotted.split("."):
        if not isinstance(v, dict) or p not in v:
            return None
        v = v[p]
    return v


SNAPSHOT = {"window": "sut_stats_window", "leg": "sut_stats_leg_end"}


def snapshot_missing(m, scope):
    """True when the stats snapshot a window or leg item reads was never taken (or is empty):
    then no item of that scope can pass, `absent` included."""
    if scope not in SNAPSHOT:
        return False
    d = m.get(SNAPSHOT[scope])
    # an empty snapshot counts when the read itself succeeded (an arm that rejects every stat)
    return d is None or (not d and not m.get(SNAPSHOT[scope] + "_ok"))


def lookup(m, scope, name):
    """The value an item reads, or None when it does not exist."""
    if scope == "window":
        return (m.get("sut_stats_window") or {}).get(name)
    if scope == "leg":
        return (m.get("sut_stats_leg_end") or {}).get(name)
    if scope == "field":
        return _path(m, name)
    raise ValueError("scope %s has no plain lookup" % scope)


def config_values(dump, key):
    """Every value stored under `key` anywhere in a parsed /config_dump."""
    out = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == key:
                    out.append(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(dump)
    return out


def _denominator(m, it):
    sc = it.get("scope", "window")
    spec = it.get("per") or DEFAULT_PER.get(sc)
    if not spec and sc == "field":
        return 1.0, None  # a field value is compared as it is (per flush, per leg: the field says)
    if not spec:
        return None, "no denominator for scope %s" % sc
    s, n = spec.split(":", 1)
    d = lookup(m, s, n)
    if d is None:
        return None, "denominator %s missing" % spec
    if not d:
        return None, "denominator %s is 0" % spec
    return float(d), None


def _tolerance(it, expect, n=None):
    t = 0.0
    if "tol" in it:
        t = max(t, abs(float(it["tol"]) * expect))
    if "tol_abs" in it:
        t = max(t, float(it["tol_abs"]))
    if "tol_binomial_sd" in it and n:
        p = min(max(expect, 0.0), 1.0)
        t = max(t, float(it["tol_binomial_sd"]) * math.sqrt(p * (1.0 - p) / n))
    return t


def label(it):
    return it.get("label") or "%s:%s" % (it.get("scope", "window"), it["stat"])


def check_item(m, it, config_dump=None):
    """{label, ok, value, expect, why} for one item on one leg."""
    sc = it.get("scope", "window")
    r = {"label": label(it), "ok": False}
    if sc == "config":
        if config_dump is None:
            r["why"] = "no /config_dump for this arm"
            return r
        vals = config_values(config_dump, it["stat"])
        r["value"] = vals[:4]
        if it.get("absent"):
            r["ok"] = not vals
            r["why"] = "ok" if r["ok"] else "present in /config_dump"
        elif it.get("present"):
            r["ok"] = bool(vals)
            r["why"] = "ok" if r["ok"] else "not in /config_dump"
        else:
            r["expect"] = it["equals"]
            r["ok"] = bool(vals) and all(v == it["equals"] for v in vals)
            r["why"] = "ok" if r["ok"] else ("not in /config_dump" if not vals else "values %s" % vals[:4])
        return r
    if snapshot_missing(m, sc):
        r["why"] = "no %s snapshot in this leg (%s)" % (sc, m.get("leg_end_snapshot_error") or "not taken")
        return r
    if it.get("absent") and it["stat"].endswith("*") and sc in SNAPSHOT:
        # a prefix: no stat of that family at all
        pre = it["stat"][:-1]
        hit = sorted(k for k in m[SNAPSHOT[sc]] if k.startswith(pre))
        r["value"] = hit[:4]
        r["ok"] = not hit
        r["why"] = "ok" if r["ok"] else "present (%s)" % ", ".join(hit[:4])
        return r
    v = lookup(m, sc, it["stat"])
    r["value"] = v
    if it.get("absent"):
        r["ok"] = v is None
        r["why"] = "ok" if r["ok"] else "present (%s)" % (v,)
        return r
    if it.get("present"):
        r["ok"] = v is not None
        r["why"] = "ok" if r["ok"] else "missing"
        return r
    if v is None:
        r["why"] = "missing"
        return r
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        if "equals" in it and v == it["equals"]:
            r.update(ok=True, why="ok", expect=it["equals"])
        else:
            r["why"] = "not a number: %r" % (v,)
        return r
    if "per_request" in it or "ref" in it:
        if it.get("per_request") is None:
            r["why"] = "reference value not frozen (run evidence-check --freeze on the smoke)"
            return r
        d, why = _denominator(m, it)
        if d is None:
            r["why"] = why
            return r
        x = v / d
        e = float(it["per_request"])
        t = _tolerance(it, e, d)
        r.update(value=x, expect=e, tol=t, raw=v, denominator=d)
        r["ok"] = abs(x - e) <= t
        r["why"] = "ok" if r["ok"] else "%.6g per request, expected %.6g +/- %.3g" % (x, e, t)
        return r
    if "equals" in it:
        e = float(it["equals"])
        t = _tolerance(it, e)
        r.update(expect=e, tol=t)
        r["ok"] = abs(v - e) <= t
        r["why"] = "ok" if r["ok"] else "%s, expected %s +/- %.3g" % (v, it["equals"], t)
        return r
    lo, hi = it.get("min"), it.get("max")
    r.update(min=lo, max=hi)
    if "per" in it:
        # a bound on a ratio of two values (e.g. spans the collector accepted per span sent)
        d, why = _denominator(m, it)
        if d is None:
            r["why"] = why
            return r
        r.update(raw=v, denominator=d)
        v = v / d
        r["value"] = v
    r["ok"] = (lo is None or v >= lo) and (hi is None or v <= hi)
    r["why"] = "ok" if r["ok"] else "%s outside [%s, %s]" % (v, lo, hi)
    return r


def applies(it, shape):
    """An item with `shape` (a name or a list) applies only to legs of those shapes."""
    sh = it.get("shape")
    return sh is None or shape == sh or (isinstance(sh, list) and shape in sh)


def evaluate(m, items, config_dump=None, gate=True):
    """The evidence record of one leg: every item that applies to the leg's shape, `ok`
    only when all of them pass."""
    res = [check_item(m, it, config_dump) for it in items or [] if applies(it, m.get("shape"))]
    if items and not res:
        # an arm with evidence but nothing for this shape would pass vacuously
        res = [{"label": "evidence", "ok": False, "why": "no evidence item applies to shape %s" % m.get("shape")}]
    return {"ok": all(r["ok"] for r in res), "gate": bool(gate), "items": res,
            "failed": [r["label"] + ": " + r["why"] for r in res if not r["ok"]]}


# ---------------------------------------------------------------- offline check

def load_spec(path):
    """{arm: [items]} from an experiment config (arms[].evidence) or {"evidence": {arm: items}}."""
    with open(path) as f:
        raw = json.load(f)
    if isinstance(raw.get("evidence"), dict):
        return {k: list(v) for k, v in raw["evidence"].items()}
    return {a["name"]: list(a["evidence"]) for a in raw.get("arms", []) if a.get("evidence")}


def load_legs(run_dir):
    """Current legs of a run directory (superseded re-runs dropped), from legs.jsonl
    or, if that is missing, results.json."""
    p = os.path.join(run_dir, "legs.jsonl")
    legs = []
    if os.path.exists(p):
        sup = set()
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                x = json.loads(line)
                if "supersede" in x:
                    sup.update(x["supersede"])
                    continue
                legs.append(x)
        # a re-run reuses no leg id (attempt suffix), so the superseded ids are exact
        return [m for m in legs if m.get("leg_id") not in sup]
    with open(os.path.join(run_dir, "results.json")) as f:
        return [m for m in json.load(f)["legs"] if not m.get("superseded")]


def load_config_dump(run_dir, arm):
    p = os.path.join(run_dir, "config_dump", arm + ".json.gz")
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt") as f:
        return json.load(f)


def per_request_value(m, it):
    sc = it.get("scope", "window")
    v = lookup(m, sc, it["stat"])
    d, _ = _denominator(m, it)
    if v is None or d is None or isinstance(v, bool):
        return None
    return v / d


def freeze(spec, legs):
    """A copy of the spec with every `ref` item's per_request set from the legs:
    the mean per-request value of the ref arm (or the item's own arm) plus the offset.
    The value is taken per shape: an item without `shape` becomes one frozen item per shape
    the arm's legs ran (a per-request byte count differs between shapes), each with `shape`
    set. An item that is frozen already is kept as it is.
    Returns (spec, problems)."""
    out, problems = {}, []
    for arm, items in spec.items():
        new = []
        mine = sorted({m.get("shape") for m in legs if m.get("arm") == arm and m.get("shape")})
        for it in items:
            ref = it.get("ref")
            if not ref or it.get("per_request") is not None:
                new.append(dict(it))
                continue
            src = arm if ref["arm"] == "self" else ref["arm"]
            shapes = [s for s in mine if applies(it, s)]
            if not shapes:
                problems.append("%s %s: no leg of this arm in a shape the item covers" % (arm, label(it)))
                new.append(dict(it))
                continue
            for s in shapes:
                vals = [per_request_value(m, it) for m in legs if m.get("arm") == src and m.get("shape") == s
                        and (m.get("verdict") or {}).get("valid", True)]
                vals = [v for v in vals if v is not None]
                f = dict(it, shape=s)
                if not vals:
                    problems.append("%s %s on %s: no value of arm %s in the legs" % (arm, label(it), s, src))
                else:
                    f["per_request"] = sum(vals) / len(vals) + float(ref.get("offset", 0.0))
                    f["ref"] = dict(ref, frozen_from_legs=len(vals), frozen_min=min(vals), frozen_max=max(vals))
                new.append(f)
        out[arm] = new
    return out, problems


def check_run(spec, run_dir):
    """[(leg_id, arm, evidence record)] for every leg of an arm the spec names, plus a
    list of problems (arms of the spec with no leg)."""
    legs = load_legs(run_dir)
    dumps = {}
    rows, problems = [], []
    for arm, items in spec.items():
        mine = [m for m in legs if m.get("arm") == arm and "leg_id" in m]
        if not mine:
            problems.append("arm %s: no legs in %s" % (arm, run_dir))
            continue
        if arm not in dumps:
            dumps[arm] = load_config_dump(run_dir, arm)
        for m in mine:
            rows.append((m["leg_id"], arm, evaluate(m, items, dumps[arm])))
    return rows, problems
