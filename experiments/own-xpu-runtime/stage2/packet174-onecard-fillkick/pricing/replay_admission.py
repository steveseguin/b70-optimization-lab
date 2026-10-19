"""Transferred replay: parent overlap cadence, LRU always-admit vs fixed second-touch admission.
Parameters fixed BEFORE running: W=256 positions; slots from 21,552,729,600 B / 1,978,667 B mean expert.
Trace: packet55 cards23-a target, non-speculative rows (two-card MTP lineage; NOT one-card evidence)."""
import gzip,json,sys,collections
TRACE=sys.argv[1]; W=256
EXP_BYTES=1978667
def load():
    pos=[];cur=None;key=None
    with gzip.open(TRACE,'rt') as f:
        for line in f:
            r=json.loads(line)
            if r.get('role')!='target' or r.get('speculative'):continue
            k=(r['prompt_id'],r['phase'],r['position'],r.get('fixture'))
            if k!=key:
                if cur:pos.append(cur)
                key=k;cur={'phase':r['phase'],'prompt':r['prompt_id'],'ids':[]}
            cur['ids'].extend(r['layer']*512+i for i in r['ids'])
    if cur:pos.append(cur)
    return pos
def run(pos,slots,policy):
    cache=collections.OrderedDict();published=set();last_seen={}
    state='idle';plan=None;prev=None;stats=collections.Counter()
    for k,p in enumerate(pos):
        # boundary at start of k
        if state=='filling':published=set(cache);state='idle'
        if state=='planned':
            published-=plan['evicted'];stats['fill_'+p['phase']]+=len(plan['fills']);state='filling'
            stats['fills']+=len(plan['fills'])
        ids=p['ids']
        h=sum(1 for i in ids if i in published);stats['routes_'+p['phase']]+=len(ids);stats['hits_'+p['phase']]+=h
        # plan during k from previous routes
        if state=='idle' and prev is not None:
            rk,routes=prev
            for i in routes:
                if i in cache:cache.move_to_end(i)
            fills=[];ev=set()
            for i in dict.fromkeys(routes):
                if i in cache:continue
                if policy=='second' and not (i in last_seen and last_seen[i][0] is not None and rk-W<=last_seen[i][0]<rk):continue
                while len(cache)>=slots:
                    v,_=cache.popitem(last=False);ev.add(v)
                cache[i]=True;fills.append(i)
            plan={'fills':fills,'evicted':ev};state='planned';prev=None
        # after k: observe
        for i in ids:
            if i in cache:cache.move_to_end(i)
            ls=last_seen.get(i)
            last_seen[i]=(ls[1] if ls and ls[1]!=k else (ls[0] if ls else None),k)
        prev=(k,ids)
    return stats
pos=load()
print('positions',len(pos),collections.Counter(p['phase'] for p in pos))
slots=21552729600//EXP_BYTES
out={}
for cap,s in (('21.55GB',slots),('18GB',18000000000//EXP_BYTES)):
    for pol in ('lru','second'):
        if cap=='18GB' and pol=='second':continue
        st=run(pos,s,pol);out[cap+'/'+pol]=st
        d=st['routes_decode'] or 1
        npos=sum(1 for p in pos if p['phase']=='decode')
        print(cap,pol,'decode hit %.4f misses/pos %.2f fills/pos %.2f fillMB/pos %.1f | prefill hit %.4f'%(st['hits_decode']/d,(d-st['hits_decode'])/npos,st['fill_decode']/npos,st['fill_decode']/npos*EXP_BYTES/1e6,st['hits_prefill']/max(1,st['routes_prefill'])))
json.dump({k:dict(v) for k,v in out.items()},open('replay-admission.json','w'),indent=1)
