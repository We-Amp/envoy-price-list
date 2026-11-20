"""Independent analysis of run L (stats flush against request latency).

Reads legs.jsonl, probe/*.jsonl.gz and main/*.json.gz directly. Does not import the harness.
Statistics are re-implemented here (numpy, scipy for the t distribution).
"""
import gzip
import json
import math
import os

import numpy as np
from scipy import stats as sst

import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# every script: python3 <script>.py [RUN_DIR [OUT_DIR]]. RUN_DIR: the run's directory (legs.jsonl,
# probe/, main/, nighthawk/); OUT_DIR: where perleg.json, results.json and extra.json are written
# and read back (default: analysis/ beside the run directory)
RUN = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "RUN_L", os.path.join(HERE, "..", "..", "..", "data", "stats", "flush-latency", "lat"))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("OUT_L", os.path.join(RUN, "..", "analysis"))
os.makedirs(OUT, exist_ok=True)


def read_json(path):
    """A JSON file, stored as it was written or gzip-compressed (path + ".gz")."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    with gzip.open(path + ".gz", "rt") as f:
        return json.load(f)

GUARD = 0.020
ONSET = 0.050
POST = 0.250
EDGE = 0.5
BUSY = 0.2
JOIN = 0.1
MIN_FLUSH_RUN_S = 0.05  # a burst with less main-thread run time than this is listed as "minor", not a flush
INTERVAL = 10.0
CELLS = [("own", "nosink"), ("own", "statsd"), ("own", "otlp"), ("shared", "nosink"), ("shared", "statsd")]
FLOORS = {"p99": 120.0, "p50": 20.0, "share2": 0.2}


def cell_name(c):
    return "%s/%s" % c


# ---------------------------------------------------------------- loading

def load_legs():
    """Every line of legs.jsonl in file order: leg records and supersede markers."""
    out = []
    with open(os.path.join(RUN, "legs.jsonl")) as f:
        for n, line in enumerate(f):
            line = line.strip()
            if line:
                d = json.loads(line)
                d["_line"] = n
                out.append(d)
    return out


def load_main(leg_id):
    with gzip.open(os.path.join(RUN, "main", leg_id + ".json.gz"), "rt") as f:
        return json.load(f)


def load_probe(leg_id):
    """Returns dict with numpy arrays per stream, the meta line and the end line."""
    rows = {"d": [], "a": [], "c": []}
    meta = end = None
    with gzip.open(os.path.join(RUN, "probe", leg_id + ".jsonl.gz"), "rt") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            j = json.loads(line)
            if isinstance(j, list):
                rows[j[0]].append(j[1:])
            elif "meta" in j:
                meta = j
            elif "end" in j:
                end = j["end"]
    out = {"meta": meta, "end": end}
    for k, v in rows.items():
        # columns: connection, sequence, intended_ns, sent_ns, done_ns, status, bytes
        a = np.array([[(-1 if x is None else x) for x in r] for r in v], dtype=np.int64)
        out[k] = a
    return out


# ---------------------------------------------------------------- bursts

def find_bursts(series):
    """Own burst detector on one thread's [t, run_ns, wait_ns] series.

    An interval is busy when the thread ran more than BUSY of it; busy intervals closer than JOIN
    seconds are one burst. Returns list of dicts (start, end, run_s, partial)."""
    a = np.asarray(series, dtype=np.float64)
    t = a[:, 0]
    run = a[:, 1]
    dt = np.diff(t)
    dr = np.diff(run) / 1e9
    busy = dr / dt > BUSY
    idx = np.flatnonzero(busy)
    bursts = []
    if len(idx) == 0:
        return bursts
    s = idx[0]
    p = idx[0]
    groups = []
    for i in idx[1:]:
        if t[i] - t[p + 1] > JOIN:
            groups.append((s, p))
            s = i
        p = i
    groups.append((s, p))
    for s, p in groups:
        bursts.append({
            "start": float(t[s]), "end": float(t[p + 1]),
            "run_s": float((run[p + 1] - run[s]) / 1e9),
            "partial": bool(s == 0 or p + 1 == len(t) - 1),
        })
    return bursts


def flush_windows(main, t0, t1):
    """(whole flushes inside the used span, all flush-sized bursts, minor bursts)."""
    b = find_bursts(main["series"][str(main["main_tid"])])
    big = [x for x in b if x["run_s"] >= MIN_FLUSH_RUN_S or x["partial"]]
    minor = [x for x in b if not (x["run_s"] >= MIN_FLUSH_RUN_S or x["partial"])]
    whole = [x for x in big if not x["partial"] and x["start"] >= t0 + EDGE and x["end"] <= t1 - EDGE]
    return whole, big, minor


# ---------------------------------------------------------------- slices

def in_any(ts, ranges):
    m = np.zeros(len(ts), dtype=bool)
    for a, b in ranges:
        m |= (ts >= a) & (ts <= b)
    return m


def slice_masks(ts, whole, allb, t0, t1, gap_ranges=()):
    """Masks IN, ONSET, POST, OUT by intended time (plan section 4)."""
    span = (ts >= t0 + EDGE) & (ts <= t1 - EDGE)
    gapm = in_any(ts, gap_ranges) if len(gap_ranges) else np.zeros(len(ts), dtype=bool)
    ok = span & ~gapm
    m_in = in_any(ts, [(b["start"] + GUARD, b["end"] - GUARD) for b in whole]) & ok
    m_on = in_any(ts, [(b["start"] - GUARD, b["start"] + ONSET) for b in whole]) & ok
    m_post = np.zeros(len(ts), dtype=bool)
    for b in whole:
        m_post |= (ts > b["end"] - GUARD) & (ts <= b["end"] + POST)
    m_post &= ok
    zone = in_any(ts, [(b["start"] - GUARD, b["end"] + POST) for b in allb])
    m_out = ok & ~zone
    return {"in": m_in, "onset": m_on, "post": m_post, "out": m_out, "span": span, "gap": gapm & span}


def sstat(lat_us):
    n = len(lat_us)
    if n == 0:
        return {"n": 0, "p50": math.nan, "p90": math.nan, "p99": math.nan, "max": math.nan,
                "share2": math.nan, "over20": 0, "over100": 0}
    p50, p90, p99 = np.percentile(lat_us, [50, 90, 99])
    return {"n": int(n), "p50": float(p50), "p90": float(p90), "p99": float(p99), "max": float(lat_us.max()),
            "share2": float(100.0 * np.mean(lat_us > 2000.0)),  # percent
            "over20": int(np.sum(lat_us > 20000.0)), "over100": int(np.sum(lat_us > 100000.0))}


def contrasts(lat, masks, cpu0):
    """L1, L2, L3 at p99, p50 and share over 2 ms (points). lat in us; cpu0 boolean per probe."""
    out = {}
    groups = {"all": np.ones(len(lat), dtype=bool), "cpu0": cpu0, "others": ~cpu0}
    st = {g: {s: sstat(lat[masks[s] & gm]) for s in ("in", "onset", "out")} for g, gm in groups.items()}
    for m in ("p99", "p50", "share2"):
        out["L1_" + m] = st["all"]["in"][m] - st["all"]["out"][m]
        out["L2_" + m] = st["all"]["onset"][m] - st["all"]["out"][m]
        out["L3_" + m] = (st["cpu0"]["in"][m] - st["cpu0"]["out"][m]) - (st["others"]["in"][m] - st["others"]["out"][m])
        out["out_" + m] = st["all"]["out"][m]
        out["out0_" + m] = st["cpu0"]["out"][m]
    return out, st


def sham_shifts(whole, allb, t0, t1):
    """Admissible shifts on the 0.5 s grid: {shift: list of shifted (start, end)}.

    A shifted window may leave the used span for at most one window (that one is dropped); no shifted
    zone [start - g, end + POST] may touch a real zone."""
    zones = [(b["start"] - GUARD, b["end"] + POST) for b in allb]
    res = {}
    for k in range(1, 20):
        s = 0.5 * k
        keep = []
        dropped = 0
        bad = False
        for b in whole:
            a, e = b["start"] + s, b["end"] + s
            if a - GUARD < t0 + EDGE or e + POST > t1 - EDGE:
                dropped += 1
                continue
            for za, zb in zones:
                if a - GUARD <= zb and e + POST >= za:
                    bad = True
                    break
            if bad:
                break
            keep.append((a, e))
        if bad or dropped > 1 or not keep:
            continue
        res[s] = keep
    return res


def sham_contrast(ts, lat, cpu0, masks, wins):
    m_in = in_any(ts, [(a + GUARD, e - GUARD) for a, e in wins]) & masks["out"]
    m_on = in_any(ts, [(a - GUARD, a + ONSET) for a, e in wins]) & masks["out"]
    zone = in_any(ts, [(a - GUARD, e + POST) for a, e in wins])
    m = {"in": m_in, "onset": m_on, "out": masks["out"] & ~zone}
    c, _ = contrasts(lat, m, cpu0)
    return c


# ---------------------------------------------------------------- statistics

def tci(x, level=0.95):
    x = np.asarray([v for v in x if v is not None and not (isinstance(v, float) and math.isnan(v))], dtype=float)
    n = len(x)
    if n < 2:
        return {"n": n, "mean": float(x.mean()) if n else math.nan, "lo": math.nan, "hi": math.nan,
                "hw": math.nan, "sd": math.nan, "p": math.nan, "t": math.nan}
    m = x.mean()
    sd = x.std(ddof=1)
    se = sd / math.sqrt(n)
    tc = sst.t.ppf(0.5 + level / 2, n - 1)
    if se == 0:
        return {"n": n, "mean": float(m), "lo": float(m), "hi": float(m), "hw": 0.0, "sd": 0.0, "p": 0.0 if m else 1.0, "t": math.inf}
    t = m / se
    p = 2 * sst.t.sf(abs(t), n - 1)
    return {"n": n, "mean": float(m), "lo": float(m - tc * se), "hi": float(m + tc * se), "hw": float(tc * se),
            "sd": float(sd), "p": float(p), "t": float(t)}


def holm(ps):
    """Holm step-down adjusted p-values, same order as given."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj = [0.0] * len(ps)
    run = 0.0
    m = len(ps)
    for rank, i in enumerate(order):
        v = min(1.0, (m - rank) * ps[i])
        run = max(run, v)
        adj[i] = run
    return adj


def fmt(x, d=1):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return ("%+." + str(d) + "f") % x


def fnum(x, d=1):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return ("%." + str(d) + "f") % x
