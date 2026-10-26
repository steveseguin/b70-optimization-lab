import json,statistics,sys
for t in sys.argv[1:]:
    rows=[json.loads(l) for l in open('/dev/shm/ownrt-lab-sel/%s/rank1/decode-device-profile.jsonl'%t)]
    rows=[r for r in rows if not r['speculative']]
    out=[]
    for k in rows[0]['sites']:
        if 'qsa_select' in k or k in('qsa_prepare','qsa_append_pool','qsa_attention'):
            v=[r['sites'][k]['busy_us'] for r in rows if k in r['sites']];c=rows[0]['sites'][k]['count']
            out.append('%s %.1f'%(k,statistics.median(v)/c))
    print(t,'|',', '.join(out),'| span %.0f'%statistics.median([r['span_us'] for r in rows]))
