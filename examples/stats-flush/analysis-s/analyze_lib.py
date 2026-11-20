"""Statistics shared by analyze.py and extra.py (re-implemented, no harness import)."""
import math

from scipy import stats as sps

TAU = 0.34


def mean(xs):
    return sum(xs) / len(xs)


def sd(xs):
    mu = mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def t_int(xs):
    n = len(xs)
    mu, se = mean(xs), sd(xs) / math.sqrt(n)
    hw = sps.t.ppf(0.975, n - 1) * se
    return {"n": n, "mean": mu, "lo": mu - hw, "hi": mu + hw, "se": se, "sd": sd(xs)}


def pct(logpct):
    return 100.0 * (math.exp(logpct / 100.0) - 1.0)


def log_ratio(arm_vals, ref_vals):
    d = [100.0 * math.log(a / b) for a, b in zip(arm_vals, ref_vals)]
    t = t_int(d)
    se = t["se"]
    hw = t["hi"] - t["mean"]
    w = max(hw, 1.96 * math.sqrt(se * se + TAU * TAU))
    p = 2.0 * sps.t.sf(abs(t["mean"]) / se, t["n"] - 1) if se > 0 else 0.0
    return {"n": t["n"], "log": t["mean"], "log_lo": t["lo"], "log_hi": t["hi"], "hw": hw, "se": se, "w": w,
            "eff": pct(t["mean"]), "lo": pct(t["lo"]), "hi": pct(t["hi"]),
            "wlo": pct(t["mean"] - w), "whi": pct(t["mean"] + w), "p": p, "d": d}
