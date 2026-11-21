#!/usr/bin/env python3
"""Independent analysis of run U-hi (1,500 req/s per worker) against run U (1,000).
Reads only legs.jsonl files and queue.log; writes results.json and tables.txt to OUT_DIR.
Usage: python3 analyze.py [U_HI_DIR [U_DIR [OUT_DIR [STOPPED_1800_DIR]]]]
  U_HI_DIR  the high-load study's directory (u-hi-1500/, smoke-u-hi-1500/, queue.log)
  U_DIR     run U's directory (u/legs.jsonl), for the comparison at 1,000 req/s per worker
  OUT_DIR   default: U_HI_DIR/analysis
  STOPPED_1800_DIR  the leg records of the stopped first attempt at 1,800 req/s (u-hi/,
            smoke-u-hi/; default U_HI_DIR/stopped-1800), read for its "other tasks" figures only"""
import datetime as dt
import json, math, os, re, sys
import numpy as np
from scipy import stats as st

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', '..', 'data', 'stats')
HI_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA, 'multi-worker-high-load')
U_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HI_DIR, '..', 'multi-worker')
OUT_DIR = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HI_DIR, 'analysis')
HI1800_DIR = sys.argv[4] if len(sys.argv) > 4 else os.path.join(HI_DIR, 'stopped-1800')
os.makedirs(OUT_DIR, exist_ok=True)
HI = os.path.join(HI_DIR, 'u-hi-1500', 'legs.jsonl')
HI_SMOKE = os.path.join(HI_DIR, 'smoke-u-hi-1500', 'legs.jsonl')
U = os.path.join(U_DIR, 'u', 'legs.jsonl')
HI1800 = os.path.join(HI1800_DIR, 'u-hi', 'legs.jsonl')
HI1800_SMOKE = os.path.join(HI1800_DIR, 'smoke-u-hi', 'legs.jsonl')
QUEUE = os.path.join(HI_DIR, 'queue.log')
SHAPES = ['mt-14w-one', 'mt-14w-split', 'mt-28w']
ARMS = ['base', 'stats-reject', 'base-A2']
lines = []
def P(*a):
    s = ' '.join(str(x) for x in a); print(s); lines.append(s)

def load(path):
    recs = [json.loads(l) for l in open(path)]
    legs = [r for r in recs if 'leg_id' in r]
    sup = set()
    for r in recs:
        if 'leg_id' not in r and r.get('supersede'):
            sup |= set(r['supersede'])
    return recs, legs, sup

def metrics(r):
    p = r['per_req']
    m = dict(
        wcyc=r['workers_cycles_per_req'], cyc_tot=p['cycles_total'], cyc_u=p['cycles_u'], cyc_k=p['cycles_k'],
        ins_u=p['instructions_u'], ins_k=p['instructions_k'], ins_tot=p['instructions_u'] + p['instructions_k'],
        p50=r['latency_us']['p50'], p99=r['latency_us']['p99'], busy=r['sut_busy'],
        ctx=p['context_switches'])
    m['cpi_tot'] = m['cyc_tot'] / m['ins_tot']
    m['cpi_u'] = m['cyc_u'] / m['ins_u']
    m['cpi_k'] = m['cyc_k'] / m['ins_k']
    return m

def current(legs, sup, use_originals=False):
    """dict[(shape, round, arm)] -> leg. Superseding: a leg listed in a supersede record is dropped, so the
    .rr1 leg of the same round/shape/arm takes its place. use_originals: sensitivity, attempt 0 only."""
    d = {}
    for r in legs:
        if r['shape'] not in SHAPES: continue
        k = (r['shape'], r['round'], r['arm'])
        if use_originals:
            if r['attempt'] == 0: d[k] = r
        else:
            if r['leg_id'] in sup: continue
            assert k not in d, k
            d[k] = r
    return d

def pairs(cur, shape, arm, ref, metric, need_valid=True, rounds=None):
    out = {}
    rs = sorted({k[1] for k in cur if k[0] == shape})
    for rd in rs:
        if rounds is not None and rd not in rounds: continue
        a, b = cur.get((shape, rd, arm)), cur.get((shape, rd, ref))
        if a is None or b is None: continue
        if need_valid and not (a['verdict']['valid'] and b['verdict']['valid']): continue
        out[rd] = (metrics(a)[metric], metrics(b)[metric])
    return out

def tstat(x):
    x = np.asarray(x, float); n = len(x); m = x.mean(); sd = x.std(ddof=1); se = sd / math.sqrt(n)
    tc = st.t.ppf(0.975, n - 1); p = 2 * st.t.sf(abs(m / se), n - 1) if se > 0 else 0.0
    return dict(n=n, mean=m, sd=sd, se=se, hw=tc * se, lo=m - tc * se, hi=m + tc * se, p=p)

def logratio(pr):
    return tstat([100 * math.log(a / b) for a, b in pr.values()])   # log-percent
def diff(pr, scale=1.0):
    return tstat([(a - b) * scale for a, b in pr.values()])

def pct(x): return 100 * (math.exp(x / 100) - 1)
def holm(ps):
    idx = sorted(range(len(ps)), key=lambda i: ps[i]); out = [0] * len(ps); run = 0
    for rank, i in enumerate(idx):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i])); out[i] = run
    return out
def widen(s, h):
    return max(s['hw'], 1.96 * math.sqrt(s['se'] ** 2 + h ** 2))
def fmt(s, w=None, d=2):
    t = f"{pct(s['mean']):+.{d}f}% [{pct(s['lo']):+.{d}f}, {pct(s['hi']):+.{d}f}]"
    if w is not None: t += f" w[{pct(s['mean']-w):+.{d}f}, {pct(s['mean']+w):+.{d}f}]"
    return t
def welch(a, b):
    d = a['mean'] - b['mean']; va, vb = a['se'] ** 2, b['se'] ** 2; se = math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va ** 2 / (a['n'] - 1) + vb ** 2 / (b['n'] - 1)); tc = st.t.ppf(0.975, df)
    return dict(mean=d, se=se, df=df, lo=d - tc * se, hi=d + tc * se, hw=tc * se, p=2 * st.t.sf(abs(d / se), df))

res = {}
# ---------------------------------------------------------------- 1. data set
P('== 1. DATA SET (u-hi-1500)')
recs, legs, sup = load(HI)
P('records', len(recs), 'leg records', len(legs), 'supersede records', len(recs) - len(legs), 'superseded leg ids', len(sup))
P('valid', sum(r['verdict']['valid'] for r in legs), 'invalid', sum(not r['verdict']['valid'] for r in legs))
P('first leg start', min(r['started_utc'] for r in legs), 'last leg start', max(r['started_utc'] for r in legs))
for r in legs:
    if not r['verdict']['valid']:
        P('  INVALID', r['leg_id'], r['started_utc'], 'superseded' if r['leg_id'] in sup else 'CURRENT', r['verdict']['reasons'])
blocks = {}
for r in legs:
    if r['attempt']: blocks.setdefault((r['round'], r['shape']), []).append(r)
for (rd, sh), b in sorted(blocks.items()):
    orig = [r for r in legs if r['round'] == rd and r['shape'] == sh and r['attempt'] == 0]
    P(f"  re-run r{rd:02d} {sh}: original {min(r['started_utc'] for r in orig)[11:]} (invalid: {[r['arm'] for r in orig if not r['verdict']['valid']]}), "
      f"re-run {min(r['started_utc'] for r in b)[11:]} attempts {sorted(set(r['attempt'] for r in b))} valid {sum(r['verdict']['valid'] for r in b)}/3")
cur = current(legs, sup)
P('current legs', len(cur), 'current valid', sum(r['verdict']['valid'] for r in cur.values()))
for sh in SHAPES:
    P(' ', sh, {arm: sum(1 for k, r in cur.items() if k[0] == sh and k[2] == arm and r['verdict']['valid']) for arm in ARMS},
      'complete pairs reject/A2:', len(pairs(cur, sh, 'stats-reject', 'base', 'wcyc')), '/', len(pairs(cur, sh, 'base-A2', 'base', 'wcyc')))
P('gate fields over current valid legs:')
for sh in SHAPES:
    L = [r for k, r in cur.items() if k[0] == sh and r['verdict']['valid']]
    f = lambda key: (min(r[key] for r in L), max(r[key] for r in L))
    P(f"  {sh}: n {len(L)} target {L[0]['target_rps']} sut_rate/target {min(r['sut_rate_2xx']/r['target_rps'] for r in L):.4f}-{max(r['sut_rate_2xx']/r['target_rps'] for r in L):.4f} "
      f"client_rate/target {min(r['client_rate_2xx']/r['target_rps'] for r in L):.4f}-{max(r['client_rate_2xx']/r['target_rps'] for r in L):.4f} "
      f"headroom {f('client_headroom')[0]:.3f}-{f('client_headroom')[1]:.3f} freq_ratio {f('freq_ratio')[0]:.4f}-{f('freq_ratio')[1]:.4f} "
      f"sibling max {f('sut_sibling_cpus')[1]:.4f} non2xx {sum(r['sut_non2xx'] for r in L)} overflow {sum(len(r['client_overflow']) for r in L)} "
      f"pending max {f('client_pending_total')[1]} worker busy min/max {f('envoy_worker_min_busy')[0]:.3f}/{f('envoy_worker_max_busy')[1]:.3f} "
      f"pin {all(r['pinning_ok'] for r in L)} perf {all(r['perf_ok'] for r in L)} evid {all(r['evidence']['gate'] and not r['evidence']['failed'] for r in L)} idle_unchanged {all(r['cpuidle_unchanged'] for r in L)}")

urecs, ulegs, usup = load(U)
ucur = current(ulegs, usup)
P('\nrun U: legs', len(ulegs), 'superseded', len(usup), 'current(3 shapes)', len(ucur), 'valid', sum(r['verdict']['valid'] for r in ucur.values()))

METS = [('wcyc', 'worker cycles/req (PRIMARY)'), ('cyc_tot', 'process cycles u+k/req'), ('cyc_u', 'cycles:u/req'), ('cyc_k', 'cycles:k/req'),
        ('ins_u', 'instructions:u/req'), ('ins_k', 'instructions:k/req'), ('ins_tot', 'instructions u+k/req'),
        ('cpi_tot', 'cycles per instruction u+k'), ('cpi_u', 'CPI user'), ('cpi_k', 'CPI kernel'),
        ('p50', 'p50 latency'), ('p99', 'p99 latency'), ('busy', 'SUT busy (ratio)'), ('ctx', 'context switches/req')]

def per_shape(cur, rounds=None):
    out = {}; prim = []
    for sh in SHAPES:
        out[sh] = {}
        for arm in ['stats-reject', 'base-A2']:
            for m, _ in METS:
                out[sh][(arm, m)] = logratio(pairs(cur, sh, arm, 'base', m, rounds=rounds))
            prim.append((sh, arm))
    hp = holm([out[sh][(arm, 'wcyc')]['p'] for sh, arm in prim])
    for (sh, arm), h in zip(prim, hp): out[sh][(arm, 'wcyc')]['holm'] = h
    return out

def verdict(e, aa):
    h = aa['hw']; reach = max(abs(aa['lo']), abs(aa['hi'])); w = widen(e, h)
    excl = (e['mean'] - w > 0) or (e['mean'] + w < 0)
    size = abs(e['mean'])
    if e.get('holm', 0) >= 0.05 or not (e['lo'] > 0 or e['hi'] < 0): v = 'not resolved'
    elif not excl: v = 'not a finding: A/A-widened interval includes 0'
    elif size < 1.0: v = 'not a finding: under 1%'
    elif size <= reach: v = 'not a finding: inside the A/A reach'
    else: v = 'FINDING'
    return w, reach, v

def report(cur, tag, rounds=None):
    P(f'\n== 2. PER SHAPE, {tag}')
    o = per_shape(cur, rounds); R = {}
    for sh in SHAPES:
        base = [metrics(r) for k, r in cur.items() if k[0] == sh and k[2] == 'base' and r['verdict']['valid']]
        mm = lambda key: np.mean([b[key] for b in base])
        P(f"\n-- {sh}: base n {len(base)} median wcyc {np.median([b['wcyc'] for b in base])/1e3:.1f}k; means wcyc {mm('wcyc')/1e3:.1f}k ins_u {mm('ins_u')/1e3:.2f}k ins_tot {mm('ins_tot')/1e3:.2f}k "
          f"cyc_u {mm('cyc_u')/1e3:.1f}k cyc_k {mm('cyc_k')/1e3:.1f}k cpi_tot {mm('cpi_tot'):.3f} cpi_u {mm('cpi_u'):.3f} cpi_k {mm('cpi_k'):.3f} "
          f"p50 {np.median([b['p50'] for b in base]):.0f} p99 {np.median([b['p99'] for b in base]):.0f} busy {100*np.median([b['busy'] for b in base]):.1f}%")
        aa = o[sh][('base-A2', 'wcyc')]; e = o[sh][('stats-reject', 'wcyc')]
        w, reach, v = verdict(e, aa)
        aa_ok = aa['hw'] <= 1.0 and aa['holm'] >= 0.05
        P(f"  PRIMARY stats-reject vs base n={e['n']} {fmt(e, w)} hw {e['hw']:.2f} widened hw {w:.2f} (0.34-floor hw {widen(e,0.34):.2f}) sd {e['sd']:.2f} t-p {e['p']:.2g} Holm(6) {e['holm']:.2g}")
        P(f"  A/A     base-A2 vs base      n={aa['n']} {fmt(aa)} hw {aa['hw']:.2f} reach {reach:.2f} sd {aa['sd']:.2f} t-p {aa['p']:.2g} Holm(6) {aa['holm']:.2g}  plan A/A rule (hw<=1%, not Holm-sig): {'pass' if aa_ok else 'FAIL'}")
        P(f"  VERDICT (v2): {v}")
        R[sh] = dict(effect=e, aa=aa, widened_hw=w, reach=reach, verdict=v, aa_rule_pass=aa_ok, base_mean={k: mm(k) for k in base[0]})
        for arm in ['stats-reject', 'base-A2']:
            for m, name in METS[1:]:
                s = o[sh][(arm, m)]
                P(f"    {arm:12s} {name:28s} n={s['n']} {fmt(s)} hw {s['hw']:.2f}")
        for m in ['wcyc', 'cyc_u', 'cyc_k', 'ins_u', 'ins_tot']:
            s = diff(pairs(cur, sh, 'base', 'stats-reject', m, rounds=rounds), 1e-3)
            P(f"    abs base-reject {m:8s} {s['mean']:+.2f}k [{s['lo']:+.2f}, {s['hi']:+.2f}]")
            R[sh]['abs_' + m] = s
        R[sh]['marginal_cpi'] = R[sh]['abs_wcyc']['mean'] / R[sh]['abs_ins_tot']['mean']
        R[sh]['marginal_cpi_u'] = R[sh]['abs_cyc_u']['mean'] / R[sh]['abs_ins_u']['mean']
        P(f"    marginal cycles per instruction of removed work (u+k): {R[sh]['marginal_cpi']:.2f}; user only {R[sh]['marginal_cpi_u']:.2f}")
        s = diff(pairs(cur, sh, 'stats-reject', 'base', 'busy', rounds=rounds), 100); P(f"    busy points reject-base {s['mean']:+.2f} [{s['lo']:+.2f}, {s['hi']:+.2f}]")
        R[sh]['busy_points'] = s
        R[sh]['all'] = {f'{a}|{m}': v2 for (a, m), v2 in o[sh].items()}
    return R

res['hi'] = report(cur, 'run U-hi 1,500/worker (current valid legs)')
res['u'] = report(ucur, 'run U 1,000/worker (current valid legs), same method; Holm over these 6 rows only')

# ---------------------------------------------------------------- 3. load comparison
P('\n== 3. LOAD COMPARISON: effect(U-hi) - effect(U), Welch on mean paired log ratios (log-%)')
res['load'] = {}
for sh in SHAPES:
    P(f'-- {sh}')
    for m in ['wcyc', 'ins_tot', 'cpi_tot', 'cyc_u', 'ins_u', 'cpi_u', 'cyc_k', 'ins_k', 'cpi_k']:
        a = res['hi'][sh]['all'][f'stats-reject|{m}']; b = res['u'][sh]['all'][f'stats-reject|{m}']; w = welch(a, b)
        P(f"  {m:8s} U {b['mean']:+.2f} [{b['lo']:+.2f},{b['hi']:+.2f}]  U-hi {a['mean']:+.2f} [{a['lo']:+.2f},{a['hi']:+.2f}]  diff {w['mean']:+.2f} [{w['lo']:+.2f},{w['hi']:+.2f}] p {w['p']:.2g}")
        res['load'][f'{sh}|{m}'] = w
    a = res['hi'][sh]['abs_wcyc']; b = res['u'][sh]['abs_wcyc']; w = welch(a, b)
    P(f"  abs k cycles base-reject: U {b['mean']:.2f} [{b['lo']:.2f},{b['hi']:.2f}] U-hi {a['mean']:.2f} [{a['lo']:.2f},{a['hi']:.2f}] diff {w['mean']:+.2f} [{w['lo']:+.2f},{w['hi']:+.2f}] p {w['p']:.2g}")
    res['load'][f'{sh}|abs_wcyc'] = w
    a = res['hi'][sh]['abs_ins_tot']; b = res['u'][sh]['abs_ins_tot']; w = welch(a, b)
    P(f"  abs k instr u+k base-reject: U {b['mean']:.2f} U-hi {a['mean']:.2f} diff {w['mean']:+.2f} [{w['lo']:+.2f},{w['hi']:+.2f}]")
    res['load'][f'{sh}|abs_ins_tot'] = w
    aa_a = res['hi'][sh]['all']['base-A2|wcyc']; aa_b = res['u'][sh]['all']['base-A2|wcyc']
    hcomb = math.sqrt(aa_a['hw'] ** 2 + aa_b['hw'] ** 2)
    w = res['load'][f'{sh}|wcyc']; ww = max(w['hw'], 1.96 * math.sqrt(w['se'] ** 2 + hcomb ** 2))
    P(f"  primary diff widened by both A/A half-widths (h={hcomb:.2f}): [{w['mean']-ww:+.2f}, {w['mean']+ww:+.2f}]")
    res['load'][f'{sh}|wcyc_widened'] = [w['mean'] - ww, w['mean'] + ww]
hl = holm([res['load'][f'{sh}|wcyc']['p'] for sh in SHAPES]); P('  Holm(3) on the primary load differences:', [f'{x:.2g}' for x in hl])
hl = holm([res['load'][f'{sh}|cpi_tot']['p'] for sh in SHAPES]); P('  Holm(3) on the CPI (u+k) load differences:', [f'{x:.2g}' for x in hl])
hl = holm([res['load'][f'{sh}|cpi_u']['p'] for sh in SHAPES]); P('  Holm(3) on the CPI user load differences:', [f'{x:.2g}' for x in hl])
def pooled(cur, m, arm='stats-reject'):
    rs = None; per = {}
    for sh in SHAPES:
        per[sh] = {rd: 100 * math.log(a / b) for rd, (a, b) in pairs(cur, sh, arm, 'base', m).items()}
        rs = set(per[sh]) if rs is None else rs & set(per[sh])
    return tstat([np.mean([per[sh][rd] for sh in SHAPES]) for rd in sorted(rs)])
P('-- pooled over the three shapes (per-round mean of the shape log ratios); exploratory')
for arm in ['stats-reject', 'base-A2']:
    for m in ['wcyc', 'ins_tot', 'cpi_tot', 'cyc_u', 'cpi_u', 'cyc_k']:
        a, b = pooled(cur, m, arm), pooled(ucur, m, arm); w = welch(a, b)
        P(f"  {arm:12s} {m:8s} U {b['mean']:+.2f} [{b['lo']:+.2f},{b['hi']:+.2f}] n{b['n']}  U-hi {a['mean']:+.2f} [{a['lo']:+.2f},{a['hi']:+.2f}] n{a['n']}  diff {w['mean']:+.2f} [{w['lo']:+.2f},{w['hi']:+.2f}] p {w['p']:.2g}")
        res['load'][f'pooled|{arm}|{m}'] = dict(u=b, hi=a, diff=w)
P('-- base arm level, U-hi vs U (unpaired, different sessions)')
for sh in SHAPES:
    for m in ['wcyc', 'cyc_u', 'cyc_k', 'ins_u', 'ins_k', 'cpi_u', 'cpi_k', 'cpi_tot', 'ctx']:
        a = [metrics(r)[m] for k, r in cur.items() if k[0] == sh and k[2] == 'base' and r['verdict']['valid']]
        b = [metrics(r)[m] for k, r in ucur.items() if k[0] == sh and k[2] == 'base' and r['verdict']['valid']]
        P(f"  {sh} {m:8s} U {np.mean(b):.4g} U-hi {np.mean(a):.4g} change {100*(np.mean(a)/np.mean(b)-1):+.2f}%")

P('\n== 3b. WORKER-COUNT / SOCKET CONTRASTS within a run (paired by round, difference of log ratios, log-%)')
def contrast(cur, s1, s2, m, arm='stats-reject'):
    a = {rd: 100 * math.log(x / y) for rd, (x, y) in pairs(cur, s1, arm, 'base', m).items()}
    b = {rd: 100 * math.log(x / y) for rd, (x, y) in pairs(cur, s2, arm, 'base', m).items()}
    return tstat([a[r] - b[r] for r in sorted(set(a) & set(b))])
res['contrast'] = {}
for tag, c in [('U-hi', cur), ('U', ucur)]:
    for s1, s2 in [('mt-28w', 'mt-14w-one'), ('mt-14w-split', 'mt-14w-one'), ('mt-28w', 'mt-14w-split')]:
        for m in ['wcyc', 'ins_tot', 'cpi_tot', 'cpi_u']:
            s = contrast(c, s1, s2, m)
            P(f"  {tag:5s} effect({s1}) - effect({s2}) {m:8s} n={s['n']} {s['mean']:+.2f} [{s['lo']:+.2f}, {s['hi']:+.2f}] p {s['p']:.2g}")
            res['contrast'][f'{tag}|{s1}-{s2}|{m}'] = s
P('  difference of the worker-count contrast between loads (Welch):')
for s1, s2 in [('mt-28w', 'mt-14w-one'), ('mt-14w-split', 'mt-14w-one')]:
    for m in ['wcyc', 'cpi_tot']:
        w = welch(res['contrast'][f'U-hi|{s1}-{s2}|{m}'], res['contrast'][f'U|{s1}-{s2}|{m}'])
        P(f"    [{s1} - {s2}] {m}: {w['mean']:+.2f} [{w['lo']:+.2f}, {w['hi']:+.2f}] p {w['p']:.2g}")
        res['contrast'][f'load|{s1}-{s2}|{m}'] = w

# ---------------------------------------------------------------- 4. other tasks
P('\n== 4. "OTHER TASKS ON THE SUT CPUs" (sut_foreign_cpus, CPUs; gate 0.05), every leg record incl. invalid and superseded')
def dist(path, tag, shapes=SHAPES):
    _, L, _ = load(path); out = {}
    for sh in shapes + ['all']:
        v = np.array([r['sut_foreign_cpus'] for r in L if (sh == 'all' and r['shape'] in shapes) or r['shape'] == sh])
        if len(v) == 0: continue
        q = np.percentile(v, [0, 25, 50, 75, 90, 100])
        P(f"  {tag:22s} {sh:13s} n={len(v):3d} min {q[0]:.4f} p25 {q[1]:.4f} median {q[2]:.4f} p75 {q[3]:.4f} p90 {q[4]:.4f} max {q[5]:.4f} mean {v.mean():.4f} over0.05 {int((v>0.05).sum())} over0.025 {int((v>0.025).sum())}")
        out[sh] = dict(n=len(v), q=list(q), mean=float(v.mean()), over=int((v > 0.05).sum()), over025=int((v > 0.025).sum()))
    return out
res['foreign'] = {}
res['foreign']['U 1000 (11-18)'] = dist(U, 'U 1000 (11-18)')
res['foreign']['U 1000 1w/4w'] = dist(U, 'U 1000 1w/4w', ['mt-1w', 'mt-4w'])
res['foreign']['smoke 1800 (11-19)'] = dist(HI1800_SMOKE, 'smoke 1800 (11-19)')
res['foreign']['u-hi 1800 (11-19)'] = dist(HI1800, 'u-hi 1800 (11-19)')
res['foreign']['smoke 1500 clean'] = dist(HI_SMOKE, 'smoke 1500 clean')
res['foreign']['U-hi 1500'] = dist(HI, 'U-hi 1500')
P('  U-hi 1500 by period:')
for sh in SHAPES:
    for lab, f in [('00:44-01:30', lambda r: r['attempt'] == 0 and r['started_utc'][11:16] < '01:30'),
                   ('01:30-02:36', lambda r: r['attempt'] == 0 and '01:30' <= r['started_utc'][11:16]),
                   ('re-runs 02:36-02:56', lambda r: r['attempt'] > 0)]:
        v = np.array([r['sut_foreign_cpus'] for r in legs if r['shape'] == sh and f(r)])
        if len(v): P(f"    {sh:13s} {lab:20s} n={len(v):2d} median {np.median(v):.4f} max {v.max():.4f} over0.05 {int((v>0.05).sum())}")
P('  foreign per arm (U-hi 1500, all legs):')
for arm in ARMS:
    v = np.array([r['sut_foreign_cpus'] for r in legs if r['arm'] == arm]); P(f"    {arm:12s} n={len(v)} median {np.median(v):.4f} mean {v.mean():.4f} over0.05 {int((v>0.05).sum())}")
P('  foreign vs load1 at leg start and vs position after a 28w leg (U-hi 1500):')
ordered = sorted(legs, key=lambda r: r['started_utc'])
prev = {}
for i, r in enumerate(ordered):
    prev.setdefault((r['shape'], ordered[i - 1]['shape'] if i else 'none'), []).append(r['sut_foreign_cpus'])
for k in sorted(prev): P(f"    this {k[0]:13s} previous {k[1]:13s} n={len(prev[k]):2d} median {np.median(prev[k]):.4f} max {max(prev[k]):.4f} over0.05 {sum(x>0.05 for x in prev[k])}")
l1 = [r['idle_detail']['load1'] for r in legs]; fo = [r['sut_foreign_cpus'] for r in legs]
rr = st.spearmanr(l1, fo); P(f"    spearman(load1 at start, foreign) all legs: {rr[0]:+.3f} p {rr[1]:.2g}")
P('  queue.log INVALID lines (all sessions):')
for l in open(QUEUE):
    m = re.match(r'(\S+Z) (r\d\d-mt-\S+) INVALID .*?rate=\S+ p99=\S+ (.*)$', l.strip())
    if m: P('   ', m.group(1), m.group(2), '|', m.group(3)[:110])
P('  does the foreign figure move the metric? (current valid legs, residual of log wcyc from the shape/arm mean vs foreign)')
xs, ys = [], []
for sh in SHAPES:
    for arm in ARMS:
        L = [r for k, r in cur.items() if k[0] == sh and k[2] == arm and r['verdict']['valid']]
        mu = np.mean([math.log(r['workers_cycles_per_req']) for r in L])
        for r in L: xs.append(r['sut_foreign_cpus']); ys.append(100 * (math.log(r['workers_cycles_per_req']) - mu))
rr = st.pearsonr(xs, ys); sl = st.linregress(xs, ys)
P(f"    n={len(xs)} pearson r {rr[0]:+.3f} p {rr[1]:.2g}; slope {sl.slope:+.1f} log-% per CPU (se {sl.stderr:.1f}) => {sl.slope*0.05:+.2f}% at the 0.05 gate")
res['foreign_corr'] = dict(r=rr[0], p=rr[1], slope=sl.slope, se=sl.stderr)

# ---------------------------------------------------------------- 5. anomalies
P('\n== 5. SENSITIVITY AND DRIFT (U-hi)')
P('-- (a) originals instead of re-runs (attempt 0 legs, gate ignored)')
cur0 = current(legs, sup, use_originals=True); res['sens_originals'] = {}
for sh in SHAPES:
    for arm in ['stats-reject', 'base-A2']:
        s = logratio(pairs(cur0, sh, arm, 'base', 'wcyc', need_valid=False)); P(f"   {sh} {arm:12s} n={s['n']} {fmt(s)} hw {s['hw']:.2f}")
        res['sens_originals'][f'{sh}|{arm}'] = s
P('-- (b) dropping every round whose block was re-run'); res['sens_drop'] = {}
for sh in SHAPES:
    rr_rounds = {rd for (rd, s2) in blocks if s2 == sh}
    keep = set(range(1, 16)) - rr_rounds
    for arm in ['stats-reject', 'base-A2']:
        s = logratio(pairs(cur, sh, arm, 'base', 'wcyc', rounds=keep)); P(f"   {sh} {arm:12s} dropped {sorted(rr_rounds)} n={s['n']} {fmt(s)} hw {s['hw']:.2f}")
        res['sens_drop'][f'{sh}|{arm}'] = s
P('-- (b2) 14w-one round 3 kept with its invalid re-run base leg (0.052 CPUs)')
for arm in ['stats-reject', 'base-A2']:
    s = logratio(pairs(cur, 'mt-14w-one', arm, 'base', 'wcyc', need_valid=False)); P(f"   mt-14w-one {arm:12s} n={s['n']} {fmt(s)} hw {s['hw']:.2f}")
    res['sens_drop'][f'14w-one-keep-r3|{arm}'] = s
P('-- (c) per-round primary log ratios (log-%)')
for sh in SHAPES:
    a = pairs(cur, sh, 'stats-reject', 'base', 'wcyc'); b = pairs(cur, sh, 'base-A2', 'base', 'wcyc')
    P('  ', sh, 'rej', ' '.join(f"r{rd}:{100*math.log(x/y):+.1f}" for rd, (x, y) in a.items()))
    P('  ', sh, 'A/A', ' '.join(f"r{rd}:{100*math.log(x/y):+.1f}" for rd, (x, y) in b.items()))
    rds = np.array(sorted(a)); v = np.array([100 * math.log(a[r][0] / a[r][1]) for r in rds]); lr = st.linregress(rds, v)
    P(f"     trend of effect over rounds: {lr.slope:+.3f} log-%/round p {lr.pvalue:.2g}; won {int((v<0).sum())}/{len(v)}")
P('-- (d) level spread and drift over wall-clock time (reject legs shifted by the shape effect)')
for tag, c in [('U-hi', cur), ('U', ucur)]:
    for sh in SHAPES:
        L = sorted([r for k, r in c.items() if k[0] == sh and r['verdict']['valid']], key=lambda r: r['started_utc'])
        t = np.array([dt.datetime.strptime(r['started_utc'], '%Y-%m-%dT%H:%M:%SZ').timestamp() for r in L]); t = (t - t.min()) / 3600
        eff = res['hi' if tag == 'U-hi' else 'u'][sh]['effect']['mean']
        adj = [100 * math.log(r['workers_cycles_per_req']) - (eff if r['arm'] == 'stats-reject' else 0) for r in L]
        lr = st.linregress(t, adj); v = np.array([r['workers_cycles_per_req'] for r in L if r['arm'] != 'stats-reject']) / 1e3
        P(f"   {tag:5s} {sh:13s} base+A2 legs: min {v.min():.1f}k median {np.median(v):.1f}k max {v.max():.1f}k CV {100*v.std(ddof=1)/v.mean():.2f}%; drift {lr.slope:+.2f} log-%/h p {lr.pvalue:.2g}")
P('-- (e) shape against shape, base arm level in U-hi, paired by round')
for s1, s2 in [('mt-14w-split', 'mt-14w-one'), ('mt-28w', 'mt-14w-one')]:
    for m in ['wcyc', 'cyc_u', 'cyc_k', 'cpi_u', 'p50', 'p99']:
        v = []
        for rd in range(1, 16):
            a, b = cur.get((s1, rd, 'base')), cur.get((s2, rd, 'base'))
            if a and b and a['verdict']['valid'] and b['verdict']['valid']: v.append(100 * math.log(metrics(a)[m] / metrics(b)[m]))
        s = tstat(v); P(f"   base {s1} vs {s2} {m:6s} n={s['n']} {fmt(s)}")
P('-- (f) legs more than 3% from their shape/arm median (U-hi current valid)')
for sh in SHAPES:
    for arm in ARMS:
        L = [r for k, r in cur.items() if k[0] == sh and k[2] == arm and r['verdict']['valid']]
        med = np.median([r['workers_cycles_per_req'] for r in L])
        for r in L:
            if abs(r['workers_cycles_per_req'] / med - 1) > 0.03: P(f"   {r['leg_id']} {r['workers_cycles_per_req']/med:.3f} foreign {r['sut_foreign_cpus']} ins_u {r['per_req']['instructions_u']/1e3:.1f}k")
P('-- (g) busy, load reached (base arm)')
for tag, c in [('U-hi', cur), ('U', ucur)]:
    for sh in SHAPES:
        L = [r for k, r in c.items() if k[0] == sh and k[2] == 'base' and r['verdict']['valid']]
        P(f"   {tag:5s} {sh:13s} sut_busy median {100*np.median([r['sut_busy'] for r in L]):.1f}% range {100*min(r['sut_busy'] for r in L):.1f}-{100*max(r['sut_busy'] for r in L):.1f}; busiest worker max {100*max(r['envoy_worker_max_busy'] for r in L):.1f}%; client headroom min {min(r['client_headroom'] for r in L):.3f}; eff GHz {np.mean([r['eff_ghz'] for r in L]):.3f}")
P('-- (h) worker - process cycles (k/req), U-hi')
for sh in SHAPES:
    v = [(r['per_req']['cycles_total'] - r['workers_cycles_per_req']) / 1e3 for k, r in cur.items() if k[0] == sh and r['verdict']['valid']]
    P(f"   {sh} process minus workers: mean {np.mean(v):.3f}k max {max(v):.3f}k")

def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)): return float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    return o
json.dump(clean(res), open(os.path.join(OUT_DIR, 'results.json'), 'w'), indent=1)
open(os.path.join(OUT_DIR, 'tables.txt'), 'w').write('\n'.join(lines) + '\n')
