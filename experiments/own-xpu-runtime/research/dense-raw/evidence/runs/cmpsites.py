import json,statistics,sys
def load(t):
    rows=[json.loads(l) for l in open('/dev/shm/ownrt-lab-raw/runs/%s/rank1/decode-device-profile.jsonl'%t)];rows=[r for r in rows if not r['speculative']]
    return {k:(statistics.median([r['sites'][k]['busy_us'] for r in rows if k in r['sites']]),rows[0]['sites'][k]['count']) for k in rows[0]['sites']},statistics.median([r['span_us'] for r in rows])
a,sa=load(sys.argv[1]);b,sb=load(sys.argv[2])
print('span %.1f -> %.1f  (%.1f)'%(sa,sb,sb-sa))
tot=0
for k in sorted(a,key=lambda k:-a[k][0]):
    bb=b.get(k,(0,1))[0];d=a[k][0]-bb
    if k.startswith('gemv') and ('Q6_K' in k or 'Q8_0' in k) or abs(d)>8:
        tot+=d
        print('%-34s %4d  %8.1f -> %8.1f  per-call %7.2f -> %7.2f'%(k,a[k][1],a[k][0],bb,a[k][0]/a[k][1],bb/a[k][1]))
print('listed saving %.1f us'%tot)
