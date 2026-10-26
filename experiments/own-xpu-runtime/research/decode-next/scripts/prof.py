#!/usr/bin/env python3
import json,sys,collections
def load(run):
    L=[json.loads(l) for l in open(f'/dev/shm/ownrt-lab-dnext/runs/{run}/rank1/decode-device-profile.jsonl')]
    L=[l for l in L if not l['cancelled']][2:]
    acc=collections.defaultdict(list);span=[]
    for l in L:
        span.append(l['span_us'])
        for k,v in l['sites'].items():
            if '#' in k: continue
            acc[k].append((v['count'],v['busy_us']))
    return {k:(v[0][0],sum(x[1] for x in v)/len(v)) for k,v in acc.items()},sorted(span)[len(span)//2],len(L)
a,sa,na=load(sys.argv[1]);b,sb,nb=load(sys.argv[2])
flt=sys.argv[3] if len(sys.argv)>3 else None
rows=[(k,a[k][0],a[k][1],b.get(k,(0,0))[1]) for k in a]
rows.sort(key=lambda r:r[3]-r[2])
for k,n,x,y in rows:
    if flt and flt not in k: continue
    if abs(y-x)<3 and not flt: continue
    print('%-34s n=%3d %8.1f %8.1f %+7.1f'%(k,n,x,y,y-x))
print('span %.0f -> %.0f (%+.0f)  busy %.0f -> %.0f'%(sa,sb,sb-sa,sum(v[1] for v in a.values()),sum(v[1] for v in b.values())))
