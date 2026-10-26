#!/usr/bin/env python3
import json,statistics as st,sys
def q(v,p):v=sorted(v);return v[min(len(v)-1,int(p*len(v)))]
for r in sys.argv[1:]:
    try:L=[json.loads(l) for l in open(f'/dev/shm/ownrt-lab-dnext/runs/{r}/rank1/timings.jsonl')]
    except Exception as e:print(r,'missing');continue
    L=[l for l in L if l.get('fixture')==1][2:]
    h=[l['half_completion_ms'] for l in L];e=[l['enqueue_loop_ms'] for l in L]
    s=json.load(open(f'/dev/shm/ownrt-lab-dnext/runs/{r}/summary.json'))['half_ms'][2:]
    print('%-14s n=%d drv_med=%.3f half p25=%.3f med=%.3f  enq med=%.2f load=%.1f'%(r,len(L),q(s,.5),q(h,.25),q(h,.5),q(e,.5),st.median([l['load_average_1m'] for l in L])))
