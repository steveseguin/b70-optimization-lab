#!/usr/bin/env python3
# Usage: prof.py RUN [RUN2]  -- per-site mean busy us per half (non-speculative positions), routed sites first.
import json,sys,collections
def load(run):
    f=f'/dev/shm/ownrt-lab-dexp/runs/{run}/rank1/decode-device-profile.jsonl'
    L=[json.loads(l) for l in open(f)]
    L=[l for l in L if not l['cancelled']][2:]  # skip first two halves
    acc=collections.defaultdict(list);span=[]
    for l in L:
        span.append(l['span_us'])
        for k,v in l['sites'].items():
            if '#' in k: continue
            acc[k].append((v['count'],v['busy_us']))
    return {k:(v[0][0],sum(x[1] for x in v)/len(v)) for k,v in acc.items()},sorted(span)[len(span)//2],len(L)
a,sa,na=load(sys.argv[1]);b=None
if len(sys.argv)>2:b,sb,nb=load(sys.argv[2])
keys=sorted(a,key=lambda k:(not k.startswith(('routed','expert_gather','moe_combine','route')),-a[k][1]))
ta=tb=0
for k in keys:
    c,v=a[k];ta+=v
    line='%-34s n=%3d %8.1f'%(k,c,v)
    if b and k in b:tb+=b[k][1];line+='  %8.1f  %+7.1f'%(b[k][1],b[k][1]-v)
    print(line)
print('total busy %.1f span %.1f halves %d'%(ta,sa,na)+('  |  %.1f span %.1f halves %d'%(tb,sb,nb) if b else ''))
