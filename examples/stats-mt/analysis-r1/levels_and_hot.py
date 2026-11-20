#!/usr/bin/env python3
"""Run R1 (dose): per-arm level and spread, and the rows against the cache-resident counter arms.

    python3 levels_and_hot.py [CONTENTION_DIR]   (default: data/stats/contention; reads dose-2/ and dose-evidence-2/)
"""
import json,math,os,sys
R=(sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','..','data','stats','contention')).rstrip('/')+'/'
L=json.load(open(R+'dose-2/results.json'))['legs']
WC=lambda m:m['workers_cycles_per_req']
def mean(x): return sum(x)/len(x)
def sd(x):
    m=mean(x); return math.sqrt(sum((a-m)**2 for a in x)/(len(x)-1))
am={}
for m in L:
    if m['verdict']['valid'] and not m.get('superseded'): am.setdefault((m['shape'],m['arm']),[]).append(WC(m))
print('per-arm mean/sd% (current valid):')
for k,v in sorted(am.items()): print('  ',k[0][3:],k[1],'n%d mean %.1fk sd %.2f%% min %.1f max %.1f'%(len(v),mean(v)/1e3,100*sd(v)/mean(v),min(v)/1e3,max(v)/1e3))
kind=lambda a:'hot-own' if a.startswith('hot-own') else 'hot-shared' if a.startswith('hot-sh') else 'own' if a.startswith('own') else 'shared'
res={}
prev=None
for m in L:
    k=(m['shape'],m['round'],m['attempt'])
    p='START' if (prev is None or (prev['shape'],prev['round'],prev['attempt'])!=k) else kind(prev['arm'])
    if m['verdict']['valid'] and not m.get('superseded'):
        cell='A' if m['shape']=='mt-14w-one' else 'BD'
        res.setdefault((cell,kind(m['arm']),p),[]).append(100*math.log(WC(m)/mean(am[(m['shape'],m['arm'])])))
    prev=m
print('residual % by (cell group, arm kind, predecessor kind):')
for k,v in sorted(res.items()): print('  ',k,'n%d mean %+.2f'%(len(v),mean(v)),' '.join('%+.1f'%x for x in v))
# 5-round A64 price
cur={(m['shape'],m['arm'],m['round']):m for m in L if m['verdict']['valid'] and not m.get('superseded')}
p=[(WC(cur[('mt-14w-one','shared-64',r)])-WC(cur[('mt-14w-one','own-64',r)]))/64 for r in range(2,7)]
m_=mean(p); se=sd(p)/math.sqrt(5); print('A64 P on rounds 2-6: %+.1f [%+.1f,%+.1f]'%(m_,m_-2.776445*se,m_+2.776445*se))
# plain-config scaling
for nm,P,up,C in (('A128',14.8,158.0,542.5),('A64',51.3,105.5,542.5),('B128',2.3,75.5,533.8),('D64',29.4,124.4,528.6),('hot',156.3,254.5,542.5)):
    print(nm,'17 updates: point %.3f%%  t-upper %.3f%%'%(17*P/C/10,17*up/C/10))
for nm,P,C in (('A128 wid-up',123.0,542.5),('A64',128.5,542.5),('B',69.1,533.8),('D',127.2,528.6)): print(nm,'%.3f%%'%(17*P/C/10))
