#!/usr/bin/env python3
"""Checks of the values questioned in the numbers review of run U-hi, from the raw leg records.
Usage: python3 verify_review.py [U_HI_DIR [U_DIR [OUT_DIR [STOPPED_1800_DIR]]]]  (as analyze.py; run it after analyze.py)
Reads results.json written by analyze.py plus the legs and calibration files. Writes review-checks.txt."""
import glob, json, math, os, sys
import numpy as np
from scipy import stats as st

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', '..', 'data', 'stats')
HI_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA, 'multi-worker-high-load')
U_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HI_DIR, '..', 'multi-worker')
OUT_DIR = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HI_DIR, 'analysis')
HI1800_DIR = sys.argv[4] if len(sys.argv) > 4 else os.path.join(HI_DIR, 'stopped-1800')
R = json.load(open(os.path.join(OUT_DIR, 'results.json')))
SHAPES = ['mt-14w-one', 'mt-14w-split', 'mt-28w']
ARMS = ['base', 'stats-reject', 'base-A2']
lines = []
def P(*a):
    s = ' '.join(str(x) for x in a); print(s); lines.append(s)
def pct(x): return 100 * (math.exp(x / 100) - 1)
def load(p):
    recs = [json.loads(l) for l in open(p)]
    legs = [r for r in recs if 'leg_id' in r]; sup = set()
    for r in recs:
        if 'leg_id' not in r and r.get('supersede'): sup |= set(r['supersede'])
    return legs, sup
def tstat(x):
    x = np.asarray(x, float); n = len(x); m = x.mean(); se = x.std(ddof=1) / math.sqrt(n); tc = st.t.ppf(0.975, n - 1)
    return dict(n=n, mean=m, se=se, hw=tc * se, lo=m - tc * se, hi=m + tc * se, p=2 * st.t.sf(abs(m / se), n - 1))
def holm(ps):
    idx = sorted(range(len(ps)), key=lambda i: ps[i]); out = [0] * len(ps); run = 0
    for rank, i in enumerate(idx):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i])); out[i] = run
    return out

legs, sup = load(os.path.join(HI_DIR, 'u-hi-1500', 'legs.jsonl'))
ulegs, usup = load(os.path.join(U_DIR, 'u', 'legs.jsonl'))
def cur(legs, sup): return {(r['shape'], r['round'], r['arm']): r for r in legs if r['leg_id'] not in sup and r['shape'] in SHAPES}
C, UC = cur(legs, sup), cur(ulegs, usup)
def val(r, m):
    p = r['per_req']
    return dict(wcyc=r['workers_cycles_per_req'], cyc_u=p['cycles_u'], cyc_k=p['cycles_k'], ins_u=p['instructions_u'],
                ins_tot=p['instructions_u'] + p['instructions_k'], cpi_u=p['cycles_u'] / p['instructions_u'])[m]
def lr(c, sh, arm, m='wcyc', skip=()):
    out = {}
    for rd in range(1, 16):
        if rd in skip: continue
        a, b = c.get((sh, rd, arm)), c.get((sh, rd, 'base'))
        if a and b and a['verdict']['valid'] and b['verdict']['valid']: out[rd] = 100 * math.log(val(a, m) / val(b, m))
    return out

P('== items 1, 18: v2 widened interval, 1.96*sqrt(SE^2 + 0.34^2), max with the t half-width')
for tag, key in [('U-hi', 'hi'), ('U', 'u')]:
    for sh in SHAPES:
        e = R[key][sh]['effect']; w = max(e['hw'], 1.96 * math.sqrt(e['se'] ** 2 + 0.34 ** 2))
        aa = R[key][sh]['aa']
        P(f"  {tag:5s} {sh:13s} effect {pct(e['mean']):+.2f}% widened [{pct(e['mean']-w):+.2f}, {pct(e['mean']+w):+.2f}] hw {w:.2f}; A/A hw {aa['hw']:.2f} gate {'pass' if aa['hw'] <= 1 else 'FAIL'}")
P('== note 4: Holm over the 3 effect rows only (U-hi)')
P('  ', [f'{x:.2g}' for x in holm([R['hi'][sh]['effect']['p'] for sh in SHAPES])])

P('== item 2: load difference with the plan cross-session form, SE = sqrt(SE1^2 + SE2^2 + 0.34^2 + 0.34^2), x1.96')
for sh in SHAPES:
    a, b = R['hi'][sh]['effect'], R['u'][sh]['effect']; d = a['mean'] - b['mean']
    se = math.sqrt(a['se'] ** 2 + b['se'] ** 2 + 2 * 0.34 ** 2)
    P(f"  {sh:13s} diff {d:+.2f} [{d-1.96*se:+.2f}, {d+1.96*se:+.2f}]; A/A gate U {R['u'][sh]['aa']['hw']:.2f} U-hi {R['hi'][sh]['aa']['hw']:.2f}")
    for m in ['cpi_tot', 'cpi_u']:
        a2, b2 = R['hi'][sh]['all'][f'stats-reject|{m}'], R['u'][sh]['all'][f'stats-reject|{m}']; d2 = a2['mean'] - b2['mean']
        se2 = math.sqrt(a2['se'] ** 2 + b2['se'] ** 2 + 2 * 0.34 ** 2)
        P(f"      {m} diff {d2:+.2f} [{d2-1.96*se2:+.2f}, {d2+1.96*se2:+.2f}] (0.34 was derived for cycles per request, applied here for scale only)")
P(f"  between-session spread alone: 1.96*sqrt(2)*0.34 = {1.96*math.sqrt(2)*0.34:.2f} points")

P('== item 5: marginal cycles per removed instruction (u+k), bootstrap over rounds (20000 resamples, seed 1)')
rng = np.random.default_rng(1)
def marg(c, sh):
    d = []
    for rd in range(1, 16):
        a, b = c.get((sh, rd, 'base')), c.get((sh, rd, 'stats-reject'))
        if a and b and a['verdict']['valid'] and b['verdict']['valid']:
            d.append((val(a, 'wcyc') - val(b, 'wcyc'), val(a, 'ins_tot') - val(b, 'ins_tot')))
    d = np.array(d); pt = d[:, 0].mean() / d[:, 1].mean()
    idx = rng.integers(0, len(d), (20000, len(d))); bs = d[idx, 0].mean(1) / d[idx, 1].mean(1)
    return pt, np.percentile(bs, [2.5, 97.5]), bs
for sh in SHAPES:
    ph, ch, bh = marg(C, sh); pu, cu, bu = marg(UC, sh); dd = np.percentile(bh - bu, [2.5, 97.5])
    P(f"  {sh:13s} U-hi {ph:.2f} [{ch[0]:.2f}, {ch[1]:.2f}]  U {pu:.2f} [{cu[0]:.2f}, {cu[1]:.2f}]  difference {ph-pu:+.2f} [{dd[0]:+.2f}, {dd[1]:+.2f}]")

P('== item 6: the two pre-declared contrasts (experiment.json growth / cross_socket), Holm over 2')
ex = json.load(open(os.path.join(HI_DIR, 'u-hi-1500', 'experiment.json')))
def find(o, k, path=''):
    if isinstance(o, dict):
        for kk, v in o.items():
            if kk == k: P(f"  experiment.json {path}/{kk} = {json.dumps(v)}")
            find(v, k, path + '/' + kk)
    elif isinstance(o, list):
        for i, v in enumerate(o): find(v, k, f'{path}[{i}]')
for k in ['growth', 'cross_socket', 'rerun_invalid', 'target_worker_busy', 'max_half_width_pct']: find(ex, k)
ps = []
for s1, s2 in [('mt-28w', 'mt-14w-one'), ('mt-14w-split', 'mt-14w-one')]:
    a, b = lr(C, s1, 'stats-reject'), lr(C, s2, 'stats-reject'); s = tstat([a[r] - b[r] for r in sorted(set(a) & set(b))]); ps.append(s['p'])
    P(f"  {s1} - {s2}: n {s['n']} {s['mean']:+.2f} [{s['lo']:+.2f}, {s['hi']:+.2f}] raw p {s['p']:.3f}")
P('   Holm(2):', [f'{x:.2f}' for x in holm(ps)])

P('== item 7: "other tasks" figure in calibration legs (rate per worker -> figure)')
for label, f in [(lb, g) for lb, d in (('stopped-1800', HI1800_DIR), ('multi-worker', U_DIR))
                 for g in sorted(glob.glob(os.path.join(d, 'cal-*', 'calibrate-legs.jsonl')))]:
    rows = [json.loads(l) for l in open(f)]
    P('  ', label + '/' + os.path.basename(os.path.dirname(f)) + '/calibrate-legs.jsonl', 'keys:', sorted(k for k in rows[0] if 'foreign' in k or k in ('rps', 'started_utc', 'valid', 'workers', 'rung_workers')))
    for r in rows:
        w = r.get('rung_workers') or r.get('envoy_workers') or r.get('workers')
        P(f"     {r.get('started_utc', '')} rps {r.get('rps', r.get('target_rps'))} workers {w} foreign {r.get('sut_foreign_cpus')} valid {r.get('valid', (r.get('verdict') or {}).get('valid'))} reasons {str(r.get('reasons', (r.get('verdict') or {}).get('reasons')))[:90]}")

P('== note 9: figure by position of the leg inside its block (consecutive legs of one shape)')
def bypos(legs, sh):
    blocks = {}
    for r in legs:
        if r['shape'] == sh: blocks.setdefault((r['round'], r['attempt']), []).append(r)
    pos = [[], [], []]; inv = [0, 0, 0]
    for b in blocks.values():
        b.sort(key=lambda r: r['started_utc'])
        if len(b) != 3: continue
        for i, r in enumerate(b): pos[i].append(r['sut_foreign_cpus']); inv[i] += (not r['verdict']['valid'])
    return pos, inv
for tag, L in [('U-hi', legs), ('U', ulegs)]:
    for sh in SHAPES:
        pos, inv = bypos(L, sh)
        d = np.array(pos[2]) - np.array(pos[0]); t = tstat(d); w = st.wilcoxon(d)
        P(f"  {tag:5s} {sh:13s} blocks {len(pos[0])} mean by position {np.mean(pos[0]):.3f} {np.mean(pos[1]):.3f} {np.mean(pos[2]):.3f} invalid by position {inv}; third-first paired t p {t['p']:.3f} wilcoxon p {w.pvalue:.3f}")
l18, _ = load(os.path.join(HI1800_DIR, 'u-hi', 'legs.jsonl')); s18, _ = load(os.path.join(HI1800_DIR, 'smoke-u-hi', 'legs.jsonl'))
v = [r['sut_foreign_cpus'] for r in l18 + s18 if r['shape'] == 'mt-14w-one']; P(f"  1,800 session 14w-one: n {len(v)} median {np.median(v):.3f} max {max(v):.3f}")

P('== note 13: per-arm medians of the figure')
for arm in ARMS:
    a = [r['sut_foreign_cpus'] for r in legs if r['arm'] == arm]; b = [r['sut_foreign_cpus'] for r in C.values() if r['arm'] == arm and r['verdict']['valid']]
    P(f"  {arm:12s} all {len(a)} legs {np.median(a):.4f}; current valid {len(b)} legs {np.median(b):.4f}")

P('== note 14: A/A half-width without the low legs; legs 3% or more from their shape/arm median')
for sh, skip in [('mt-14w-one', ()), ('mt-14w-one', (8,)), ('mt-14w-split', ()), ('mt-14w-split', (7,)), ('mt-14w-split', (1, 7))]:
    s = tstat(list(lr(C, sh, 'base-A2', skip=skip).values())); P(f"  {sh} A/A without rounds {skip}: n {s['n']} hw {s['hw']:.2f}")
for sh in SHAPES:
    for arm in ARMS:
        L = [r for k, r in C.items() if k[0] == sh and k[2] == arm and r['verdict']['valid']]; med = np.median([r['workers_cycles_per_req'] for r in L])
        for r in L:
            if abs(r['workers_cycles_per_req'] / med - 1) >= 0.0295: P(f"   {r['leg_id']} {r['workers_cycles_per_req']/med:.4f}")

P('== note 15: base arm, 14w-split against 14w-one, both runs (percent)')
for tag, c in [('U', UC), ('U-hi', C)]:
    for m in ['cyc_u', 'cpi_u', 'wcyc', 'cyc_k']:
        v = []
        for rd in range(1, 16):
            a, b = c.get(('mt-14w-split', rd, 'base')), c.get(('mt-14w-one', rd, 'base'))
            if a and b and a['verdict']['valid'] and b['verdict']['valid']: v.append(100 * math.log(val(a, m) / val(b, m)))
        s = tstat(v); P(f"  {tag:5s} {m:6s} n {s['n']} {pct(s['mean']):+.2f}% [{pct(s['lo']):+.2f}, {pct(s['hi']):+.2f}]")

P('== note 12: absolute delta 14w-split'); a = R['hi']['mt-14w-split']['abs_wcyc']; P(f"  {a['mean']:.3f}k [{a['lo']:.3f}, {a['hi']:.3f}]")
P('== note 11: base-arm SUT busy medians')
for tag, c in [('U-hi', C), ('U', UC)]:
    P('  ', tag, [round(100 * float(np.median([r['sut_busy'] for k, r in c.items() if k[0] == sh and k[2] == 'base' and r['verdict']['valid']])), 1) for sh in SHAPES])
open(os.path.join(OUT_DIR, 'review-checks.txt'), 'w').write('\n'.join(lines) + '\n')
