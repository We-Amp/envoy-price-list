#!/usr/bin/env python3
"""Run R1 (dose): the evidence legs (HITM loads and store-stat operations per request).

    python3 evidence.py [CONTENTION_DIR]   (default: data/stats/contention; reads dose-2/ and dose-evidence-2/)
"""
import json,math,os,sys
R=(sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','..','data','stats','contention')).rstrip('/')+'/'
e=json.load(open(R+'dose-evidence-2/results.json'))
H=("mem_load_uops_l3_hit_retired.xsnp_hitm","mem_load_uops_l3_miss_retired.remote_hitm"); L3="mem_load_uops_retired.l3_hit"
def g(ev,n): return ev.get(n) if ev.get(n) is not None else ev.get(n+':u')
by={}
for m in e['legs']:
    print(m['leg_id'],m['started_utc'][11:19],'valid',m['verdict']['valid'],'sup',m.get('superseded'),'att',m['attempt'],m['verdict']['reasons'])
    if m['verdict']['valid'] and not m.get('superseded'): by[(m['shape'],m['arm'])]=m
print(list(e['legs'][0]['per_req']['events'].keys()))
for s,K,own,sh,c in (('mt-14w-one',128,'own-128','shared-128','A'),('mt-14w-split',128,'own-128','shared-128','B'),('mt-28w',64,'own-64','shared-64','D')):
    row={}
    for a in ('base','stats-reject',own,sh):
        m=by[(s,a)]; ev=m['per_req']['events']
        row[a]=dict(loc=g(ev,H[0]),rem=g(ev,H[1]),l3=g(ev,L3),wc=m.get('workers_cycles_per_req'),ct=m['per_req'].get('cycles_total'),ins=m['per_req'].get('instructions_u'),busy=m.get('sut_busy'))
    hit={a:row[a]['loc']+row[a]['rem'] for a in row}
    cl={a:(row[a]['l3']-row[a]['loc']) for a in row}
    b=by[(s,'base')]; so=b['stat_ops']
    print('\n',c,'HITM/req',' '.join('%s %.2f (loc %.2f rem %.2f)'%(a,hit[a],row[a]['loc'],row[a]['rem']) for a in row))
    print('   h=%.3f  thr %.1f  base-reject %+.2f  d=(cleanL3 own-shared)/K %+.2f  [l3 own %.1f shared %.1f]  d with remote hitm also removed: n/a'%((hit[sh]-hit[own])/K,0.15*K,hit['base']-hit['stats-reject'],(cl[own]-cl[sh])/K,row[own]['l3'],row[sh]['l3']))
    print('   stat ops/req base: counters %.2f hist %.2f total %.2f ; responses %.0f'%(so['counter_incs']/b['responses'],so['histogram_samples']/b['responses'],(so['counter_incs']+so['histogram_samples'])/b['responses'],b['responses']))
    print('   wc: ',' '.join('%s %s'%(a,('%.1fk'%(row[a]['wc']/1e3)) if row[a]['wc'] else None) for a in row),'| cycles_total',' '.join('%.1fk'%(row[a]['ct']/1e3) for a in row),'| one-round shared-own: %+.2f%%, %+.1f cyc/update'%(100*math.log(row[sh]['wc']/row[own]['wc']),(row[sh]['wc']-row[own]['wc'])/K))
    print('   hitm (shared-own) vs cycles: ',hit[sh]-hit[own])
t=json.load(open(R+'dose-2.table.json'))
print(json.dumps(t['evidence'])[:1800])
print(json.dumps(t['model'])[:1500])
print(json.dumps(t['low'].get('lin')), t['low']['valid_rounds'], t['low']['rho_t'], sorted(t['low']['rho_rounds']))
print([(k,v.get('valid_rounds'),v['rho_t']['n'],v['aa']) for k,v in t['cells'].items()] if isinstance(t['cells'],dict) else json.dumps(t['cells'])[:1500])
