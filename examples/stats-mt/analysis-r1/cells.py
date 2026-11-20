#!/usr/bin/env python3
"""Run R1 (dose): the per-cell rows recomputed from the leg records (results.json), with the t and the widened interval.

    python3 cells.py [CONTENTION_DIR]   (default: data/stats/contention; reads dose-2/ and dose-evidence-2/)
"""
import json,math,os,sys
R=(sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','..','data','stats','contention')).rstrip('/')+'/'
d=json.load(open(R+'dose-2/results.json'))
L=d['legs']
TQ={1:12.7062,2:4.302653,3:3.182446,4:2.776445,5:2.570582,6:2.446912,7:2.364624,8:2.306,9:2.262,10:2.228,11:2.201}
def mean(x): return sum(x)/len(x)
def sd(x):
    m=mean(x); return math.sqrt(sum((a-m)**2 for a in x)/(len(x)-1))
def ti(x,terms=1):
    n=len(x); m=mean(x); se=sd(x)/math.sqrt(n); t=TQ[n-1]
    w=1.96*math.sqrt(se*se+terms*0.34**2)
    return dict(n=n,mean=m,sd=sd(x),se=se,lo=m-t*se,hi=m+t*se,wlo=m-w,whi=m+w,hw=t*se)
def f(t,u=''): return "n=%d mean %+.3f sd %.3f t[%+.2f,%+.2f] wid[%+.2f,%+.2f]%s"%(t['n'],t['mean'],t['sd'],t['lo'],t['hi'],t['wlo'],t['whi'],u)
WC=lambda m:m['workers_cycles_per_req']
INS=lambda m:m['per_req']['instructions_u']
# latest attempt per (shape,arm,round), valid only
cur={}
for m in L:
    if m.get('superseded') or not m['verdict']['valid']: continue
    k=(m['shape'],m['arm'],m['round']); assert k not in cur; cur[k]=m
# check superseded flag = not max attempt
mx={}
for m in L: mx[(m['shape'],m['round'])]=max(mx.get((m['shape'],m['round']),0),m['attempt'])
for m in L:
    assert bool(m.get('superseded'))==(m['attempt']<mx[(m['shape'],m['round'])]),m['leg_id']
print('superseded flags consistent with latest attempt; valid current legs',len(cur))
print('invalid:',[(m['leg_id'],m['verdict']['reasons'][0][:32]) for m in L if not m['verdict']['valid']])
def pr(shape,a,b,fn=WC,src=cur):
    return {r:(fn(src[(shape,a,r)]),fn(src[(shape,b,r)])) for r in range(1,7) if (shape,a,r) in src and (shape,b,r) in src}
def rho(shape,a,b,fn=WC):
    return {r:100*math.log(x/y) for r,(x,y) in pr(shape,a,b,fn).items()}
S={'A':'mt-14w-one','B':'mt-14w-split','D':'mt-28w'}
pairs=[('A128','A','shared-128','own-128',128),('A64','A','shared-64','own-64',64),('Ahot','A','hot-shared-128','hot-own-128',128),
       ('B128','B','shared-128','own-128',128),('D64','D','shared-64','own-64',64)]
RH={}
for name,c,a,b,K in pairs:
    r=rho(S[c],a,b); RH[name]=r
    p={k:(x-y)/K for k,(x,y) in pr(S[c],a,b).items()}
    ir=rho(S[c],a,b,INS)
    print('\n==',name,'rounds',sorted(r))
    print(' rho/round:',' '.join('r%d %+.2f'%(k,v) for k,v in sorted(r.items())))
    print(' P/round  :',' '.join('r%d %+.1f'%(k,v) for k,v in sorted(p.items())))
    print(' rho',f(ti(list(r.values()))))
    print(' P  ',f(ti(list(p.values()))), ' own mean %.1fk'%(mean([y for x,y in pr(S[c],a,b).values()])/1e3), 'own mean all valid %.1fk'%(mean([WC(m) for k,m in cur.items() if k[0]==S[c] and k[1]==b])/1e3))
    print(' instr sh/own %:',' '.join('%+.3f'%v for k,v in sorted(ir.items())),'mean %+.3f'%mean(list(ir.values())))
    # leave-one-out
    print(' LOO rho:',' '.join('-r%d:%+.2f[%+.2f,%+.2f]'%(k,ti([v for q,v in r.items() if q!=k])['mean'],ti([v for q,v in r.items() if q!=k])['lo'],ti([v for q,v in r.items() if q!=k])['hi']) for k in sorted(r)))
    print(' signs +:%d of %d; median %+.2f'%(sum(v>0 for v in r.values()),len(r),sorted(r.values())[len(r)//2]))
# A64 restricted to rounds common with A128
c5=[RH['A64'][r] for r in sorted(RH['A128']) if r in RH['A64']]
print('\nA64 on rounds common with A128',sorted(set(RH['A128'])&set(RH['A64'])),f(ti(c5)))
print('\n== A/A')
for c,a,b in (('A','own-128-A2','own-128'),('B','own-128-A2','own-128'),('D','own-64-A2','own-64')):
    r=rho(S[c],a,b); t=ti(list(r.values()))
    print(c,'rounds',sorted(r),' '.join('%+.2f'%v for k,v in sorted(r.items())),f(t),'hw %.2f reach %.2f tstat %.2f'%(t['hw'],max(abs(t['lo']),abs(t['hi'])),t['mean']/t['se']))
print('\n== contrasts')
for nm,x,y in (('S4 B128-A128','B128','A128'),('S5 D64-A64','D64','A64')):
    com=sorted(set(RH[x])&set(RH[y])); dd=[RH[x][r]-RH[y][r] for r in com]
    print(nm,'rounds',com,' '.join('%+.2f'%v for v in dd),f(ti(dd,2)))
# S5 unpaired view
# cross-arm pairs in cell A
print('\n== cell A cross-arm (same round, log%)')
for a,b in (('own-128','hot-own-128'),('shared-128','hot-own-128'),('shared-128','hot-shared-128'),('own-128-A2','hot-own-128'),('hot-shared-128','own-128')):
    r=rho(S['A'],a,b); ir=rho(S['A'],a,b,INS)
    print(' %s / %s'%(a,b),sorted(r),' '.join('%+.2f'%v for k,v in sorted(r.items())),f(ti(list(r.values()))),'instr %+.3f'%mean(list(ir.values())))
# cycles u / k split for hot pair
print('\n== hot pair split')
for key in ('cycles_u','cycles_k','instructions_u','instructions_k','cycles_total','context_switches'):
    fn=lambda m,key=key:m['per_req'][key]
    q=pr(S['A'],'hot-shared-128','hot-own-128',fn)
    print(' ',key,'own %.0f shared %.0f diff %+.0f (%+.2f%%)'%(mean([y for x,y in q.values()]),mean([x for x,y in q.values()]),mean([x-y for x,y in q.values()]),100*mean([math.log(x/y) for x,y in q.values()])))
for nm,c,a,b,K in pairs:
    for key in ('cycles_u','cycles_k','cycles_total'):
        fn=lambda m,key=key:m['per_req'][key]
        q=rho(S[c],a,b,fn); print('  ',nm,key,f(ti(list(q.values()))))
# sensitivity: all same-attempt valid pairs incl superseded
print('\n== sensitivity: every valid same-attempt pair (superseded attempts included)')
att={}
for m in L:
    if m['verdict']['valid']: att[(m['shape'],m['arm'],m['round'],m['attempt'])]=m
for name,c,a,b,K in pairs:
    v=[(r,t,100*math.log(WC(att[(S[c],a,r,t)])/WC(att[(S[c],b,r,t)]))) for r in range(1,7) for t in (0,1) if (S[c],a,r,t) in att and (S[c],b,r,t) in att]
    print(name,' '.join('r%d.%d %+.2f'%x for x in v),'| mean %+.2f n=%d'%(mean([x[2] for x in v]),len(v)))
