#!/usr/bin/env python3
"""Run R1 (dose): the A/A offset pooled over the cells, the common-round rows and the user/kernel split.

    python3 aa_and_split.py [CONTENTION_DIR]   (default: data/stats/contention; reads dose-2/ and dose-evidence-2/)
"""
import json,math,os,sys
R=(sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','..','data','stats','contention')).rstrip('/')+'/'
d=json.load(open(R+'dose-2/results.json'))
L=d['legs']
TQ={1:12.7062,2:4.302653,3:3.182446,4:2.776445,5:2.570582,6:2.446912,16:2.12,15:2.131,17:2.11}
def mean(x): return sum(x)/len(x)
def sd(x):
    m=mean(x); return math.sqrt(sum((a-m)**2 for a in x)/(len(x)-1))
def ti(x):
    n=len(x); m=mean(x); se=sd(x)/math.sqrt(n); t=TQ.get(n-1,2.0); w=1.96*math.sqrt(se*se+0.34**2)
    return "n=%d mean %+.2f sd %.2f t[%+.2f,%+.2f] wid[%+.2f,%+.2f]"%(n,m,sd(x),m-t*se,m+t*se,m-w,m+w)
WC=lambda m:m['workers_cycles_per_req']
S={'A':'mt-14w-one','B':'mt-14w-split','D':'mt-28w'}
# run order
print('== run order (index time shape round.att: arms; * invalid)')
blocks=[]
for i,m in enumerate(L):
    k=(m['shape'],m['round'],m['attempt'])
    if not blocks or blocks[-1][0]!=k: blocks.append((k,[]))
    blocks[-1][1].append(m)
for k,ms in blocks:
    print(ms[0]['started_utc'][11:19],k[0][3:],'r%d.%d'%(k[1],k[2]),' '.join(m['arm']+('*' if not m['verdict']['valid'] else '') for m in ms))
cur={}
pos={}
for k,ms in blocks:
    for j,m in enumerate(ms):
        if m.get('superseded'): continue
        pos[(m['shape'],m['arm'],m['round'])]=j
        if m['verdict']['valid']: cur[(m['shape'],m['arm'],m['round'])]=m
def rho(c,a,b):
    s=S[c]; return {r:100*math.log(WC(cur[(s,a,r)])/WC(cur[(s,b,r)])) for r in range(1,7) if (s,a,r) in cur and (s,b,r) in cur}
print('\n== shared vs the A2 copy, and vs mean(own,A2)')
for c,sh,own,a2 in (('A','shared-128','own-128','own-128-A2'),('B','shared-128','own-128','own-128-A2'),('D','shared-64','own-64','own-64-A2'),('A','shared-64','own-64',None)):
    if not a2: continue
    r=rho(c,sh,a2); print(c,sh,'/',a2,' '.join('r%d %+.2f'%x for x in sorted(r.items())),ti(list(r.values())))
    s=S[c]; rr=[100*math.log(WC(cur[(s,sh,q)])/math.sqrt(WC(cur[(s,own,q)])*WC(cur[(s,a2,q)]))) for q in range(1,7) if all((s,x,q) in cur for x in (sh,own,a2))]
    print('   vs geo-mean of both own copies',' '.join('%+.2f'%x for x in rr),ti(rr))
aa=[]
for c,a,b in (('A','own-128-A2','own-128'),('B','own-128-A2','own-128'),('D','own-64-A2','own-64')):
    r=rho(c,a,b); aa+=list(r.values())
    print('A/A',c,[(q,pos[(S[c],a,q)],pos[(S[c],b,q)],'%+.2f'%v) for q,v in sorted(r.items())],'(round,posA2,posOwn,rho)')
print('pooled A/A',ti(aa),'neg %d of %d'%(sum(x<0 for x in aa),len(aa)))
# position effect within block: residual of leg vs arm mean, by position
print('\n== residual (100*ln(leg/arm mean in cell)) by position in block, current valid legs')
am={}
for (s,a,r),m in cur.items(): am.setdefault((s,a),[]).append(WC(m))
for c in 'ABD':
    bypos={}
    for (s,a,r),m in cur.items():
        if s!=S[c]: continue
        bypos.setdefault(pos[(s,a,r)],[]).append(100*math.log(WC(m)/mean(am[(s,a)])))
    print(c,' '.join('p%d %+.2f(n%d)'%(p,mean(v),len(v)) for p,v in sorted(bypos.items())))
# first-in-block vs rest for B and D pooled
f=[];o=[]
for (s,a,r),m in cur.items():
    x=100*math.log(WC(m)/mean(am[(s,a)])); (f if pos[(s,a,r)]==0 else o).append(x)
print('pooled first-in-block %+.2f (n%d) other %+.2f (n%d)'%(mean(f),len(f),mean(o),len(o)))
# drift by round
print('\n== drift: mean residual by round, per cell; and freq/busy')
for c in 'ABD':
    out=[]
    for r in range(1,7):
        v=[100*math.log(WC(m)/mean(am[(s,a)])) for (s,a,q),m in cur.items() if s==S[c] and q==r]
        out.append('r%d %+.2f'%(r,mean(v)) if v else 'r%d -'%r)
    print(c,' '.join(out))
for key in ('eff_ghz','freq_ratio','sut_foreign_cpus','sut_sibling_cpus','sut_busy','client_rate_2xx','idle_wait_s'):
    for c in 'ABD':
        v=[m[key] for m in L if m['shape']==S[c] and m.get(key) is not None]
        print(' ',key,c,'min %.4g mean %.4g max %.4g'%(min(v),mean(v),max(v)),end=';')
    print()
print('foreign cpus sorted cell A:',sorted(round(m['sut_foreign_cpus'],3) for m in L if m['shape']==S['A']))
print('foreign cpus sorted B,D:',sorted(round(m['sut_foreign_cpus'],3) for m in L if m['shape']!=S['A']))
# do invalid legs differ in wc?
for m in L:
    if not m['verdict']['valid']:
        s,a=m['shape'],m['arm']; print('  invalid',m['leg_id'],'%+.2f%% vs arm mean'%(100*math.log(WC(m)/mean(am[(s,a)]))),'foreign',m['sut_foreign_cpus'])
# correlation foreign cpus vs residual, cell A all legs
xs=[];ys=[]
for m in L:
    if m['shape']==S['A']:
        xs.append(m['sut_foreign_cpus']); ys.append(100*math.log(WC(m)/mean(am[(m['shape'],m['arm'])])))
mx,my=mean(xs),mean(ys)
print('cell A corr(foreign cpus, residual)=%.2f n=%d'%(sum((a-mx)*(b-my) for a,b in zip(xs,ys))/math.sqrt(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys)),len(xs)))
# stat_count check
print('\n== increments per request per arm (min,max)')
arms={}
for m in L:
    sc=m.get('stat_count') or {}
    if sc.get('sum_per_request') is not None: arms.setdefault((m['shape'][3:],m['arm']),[]).append((sc['sum_per_request'],sc.get('new_in_window'),sc.get('end_n')))
for k,v in sorted(arms.items()): print(' ',k,'%.3f-%.3f'%(min(x[0] for x in v),max(x[0] for x in v)),'new_in_window max',max(x[1] for x in v),'counters',sorted(set(x[2] for x in v)))
# table json compare
t=json.load(open(R+'dose-2.table.json'))
print('\nTABLE keys',list(t.keys()))
