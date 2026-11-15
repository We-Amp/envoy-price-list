"""Paired statistics for balanced rounds.

Headline: the mean of the per-round log ratios (arm / reference), in percent,
with a two-sided Student t interval. Support: pairs won, the exact sign test
and the exact Wilcoxon signed-rank test. Holm's step-down adjustment for a
family of primary comparisons.

Stdlib only. The t distribution comes from the regularized incomplete beta
function (continued fraction), inverted by bisection.
"""

import math
import statistics


def mean(xs):
    return statistics.fmean(xs) if hasattr(statistics, "fmean") else sum(xs) / len(xs)


def median(xs):
    return statistics.median(xs)


def sign_test_p(wins, losses):
    """Two-sided exact sign test. Ties must already be dropped."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def _ranks_abs(diffs):
    """Average ranks of |d| (1-based), ties share the mean rank."""
    order = sorted(range(len(diffs)), key=lambda i: abs(diffs[i]))
    ranks = [0.0] * len(diffs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(diffs[order[j + 1]]) == abs(diffs[order[i]]):
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def wilcoxon_p(diffs):
    """Two-sided exact Wilcoxon signed-rank p-value (zeros dropped).

    Uses the exact permutation distribution of W+ over all 2^n sign flips,
    computed by dynamic programming on doubled ranks (handles tied ranks).
    """
    d = [x for x in diffs if x != 0]
    n = len(d)
    if n == 0:
        return 1.0
    ranks = _ranks_abs(d)
    r2 = [int(round(2 * r)) for r in ranks]
    w_plus2 = sum(r for r, x in zip(r2, d) if x > 0)
    counts = {0: 1}
    for r in r2:
        nxt = dict(counts)
        for s, c in counts.items():
            nxt[s + r] = nxt.get(s + r, 0) + c
        counts = nxt
    allc = 2 ** n
    lo = sum(c for s, c in counts.items() if s <= w_plus2) / allc
    hi = sum(c for s, c in counts.items() if s >= w_plus2) / allc
    return min(1.0, 2.0 * min(lo, hi))


def stdev(xs):
    return statistics.stdev(xs) if len(xs) > 1 else None


# ---------------------------------------------------------------- Student t

def _betacf(a, b, x):
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-15:
            break
    return h


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def t_cdf(t, df):
    x = df / (df + t * t)
    tail = 0.5 * betainc(df / 2.0, 0.5, x)
    return 1.0 - tail if t >= 0 else tail


def t_ppf(q, df):
    """Quantile of Student t with df degrees of freedom (bisection, 1e-10)."""
    if not 0.0 < q < 1.0:
        raise ValueError("q must be in (0, 1)")
    if q < 0.5:
        return -t_ppf(1.0 - q, df)
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < q:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-10:
            break
    return (lo + hi) / 2.0


def paired_log_ratio(ref_vals, arm_vals, alpha=0.05, power=0.8):
    """Per-pair 100*ln(arm/ref); mean with a two-sided (1-alpha) t interval.

    effect_pct, lo_pct, hi_pct are the same numbers turned back into a ratio
    (100*(exp(x/100)-1)), so -5.0 means "5% lower than the reference".
    mde_pct is the true effect the paired t test detects with the given power
    at this n and this spread (two-sided alpha).
    """
    d = [100.0 * math.log(a / b) for a, b in zip(arm_vals, ref_vals) if a and b and a > 0 and b > 0]
    n = len(d)
    out = {"n": n, "log_pcts": d}
    if n == 0:
        return out
    m = mean(d)
    out["log_mean_pct"] = m
    out["effect_pct"] = 100.0 * (math.exp(m / 100.0) - 1.0)
    if n < 2:
        return out
    sd = stdev(d)
    se = sd / math.sqrt(n)
    tq = t_ppf(1.0 - alpha / 2.0, n - 1)
    hw = tq * se
    if se > 0:
        tp = 2.0 * (1.0 - t_cdf(abs(m) / se, n - 1))
    else:
        tp = 0.0 if m != 0 else 1.0
    out.update({
        "log_sd_pct": sd,
        "half_width_pct": hw,
        "log_lo_pct": m - hw,
        "log_hi_pct": m + hw,
        "lo_pct": 100.0 * (math.exp((m - hw) / 100.0) - 1.0),
        "hi_pct": 100.0 * (math.exp((m + hw) / 100.0) - 1.0),
        "t_p": min(1.0, max(0.0, tp)),
        "mde_pct": (tq + t_ppf(power, n - 1)) * se,
    })
    return out


def holm(pvals):
    """Holm step-down adjusted p-values, same order as the input."""
    k = len(pvals)
    order = sorted(range(k), key=lambda i: pvals[i])
    adj = [0.0] * k
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (k - rank) * pvals[i]))
        adj[i] = running
    return adj


def compare_paired(base_vals, arm_vals, lower_is_better=True, alpha=0.05):
    """Compare paired samples (same round, same shape).

    The headline is "paired": the mean per-pair log ratio with a t interval.
    Means, medians, the ratio of medians, pairs won and the exact sign and
    Wilcoxon p-values are kept as support.
    """
    assert len(base_vals) == len(arm_vals)
    n = len(base_vals)
    if n == 0:
        return {"n": 0}
    diffs = [a - b for a, b in zip(arm_vals, base_vals)]
    better = sum(1 for x in diffs if (x < 0 if lower_is_better else x > 0))
    worse = sum(1 for x in diffs if (x > 0 if lower_is_better else x < 0))
    ties = n - better - worse
    bm, am = mean(base_vals), mean(arm_vals)
    bmed, amed = median(base_vals), median(arm_vals)
    ratios = [a / b for a, b in zip(arm_vals, base_vals) if b]
    return {
        "n": n,
        "base_mean": bm,
        "arm_mean": am,
        "base_median": bmed,
        "arm_median": amed,
        "delta_mean_pct": (am / bm - 1.0) * 100.0 if bm else None,
        "delta_median_pct": (amed / bmed - 1.0) * 100.0 if bmed else None,
        "ratio_median": median(ratios) if ratios else None,
        "ratio_min": min(ratios) if ratios else None,
        "ratio_max": max(ratios) if ratios else None,
        "pairs_won": better,
        "pairs_lost": worse,
        "pairs_tied": ties,
        "sign_p": sign_test_p(better, worse),
        "wilcoxon_p": wilcoxon_p(diffs),
        "paired": paired_log_ratio(base_vals, arm_vals, alpha=alpha),
    }
