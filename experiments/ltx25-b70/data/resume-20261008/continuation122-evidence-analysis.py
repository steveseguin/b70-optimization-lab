#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU/stdlib-only, bounded read-only receipt census. Never imports the runtime."""
import hashlib
import json
from pathlib import Path
from statistics import median, mean

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
OUT = Path(__file__).with_name('continuation122-evidence.json')
GIB = 2**30
SOURCES = {}
def read(path):
    raw = path.read_bytes()
    SOURCES[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)
def stats(xs):
    ys=sorted(xs)
    def pct(p):
        i=(len(ys)-1)*p; lo=int(i); return ys[lo]+(ys[min(lo+1,len(ys)-1)]-ys[lo])*(i-lo)
    return {'n':len(xs),'min':min(xs),'median':median(xs),'mean':mean(xs),'p10':pct(.1),'p90':pct(.9),'max':max(xs)}
def run(pattern, end):
    matches=list(ROOT.glob(pattern)); assert len(matches)==1,matches
    root=matches[0]
    receipts=[]; decodes=[]
    for p in sorted((root/'receipts').glob('receipt-*-s*.json')):
        seq=int(p.stem.rsplit('-s',1)[1])
        if seq>end: continue
        x=read(p); receipts.append(x)
        decodes.append(read(p.with_name(p.name.replace('receipt-','decode-',1))))
    byseq={x['stream_seq']:x for x in receipts}
    interior=[x for x in receipts if 10<=x['stream_seq']<end]
    rows=[]
    for x in interior:
        seq=x['stream_seq'];t=x['timing_s'];d=next(y for y in decodes if y['stream_seq']==seq)
        period=(byseq[seq+1]['timing_ns']['submit']-x['timing_ns']['submit'])/1e9
        a=t['sampler_a_split']['sampler_a']; b=t['sampler_b']; cone=t['anchor_decode_in_chain']
        rows.append({'seq':seq,'period':period,'sampler_a':a,'sampler_b':b,'cone':cone,
                     'a_bucket':t['sampler_a_bucket'],'upsample_b_prep':t['sampler_a_bucket']-a,
                     'upsample':t['sampler_a_split']['upsampler_to_condition_b'],
                     'text_a_prep':t['submit_to_sampler_start'],
                     'receipt':t['anchor_ready_to_receipt_staged'],
                     'display':d['timing_s']['display_decode'],
                     'residual':period-a-b-cone,
                     'dual_snapshots':sum(bool(s.get('dual')) for s in x.get('snapshots',[]))})
    phases={}
    for phase in ['before','A','B','after']:
        free=[]; refs=[]
        for x in receipts:
            values=[x['memory'][phase]['free']] if phase in ['before','after'] else [c[k] for c in x['memory']['conditioning'] if c['stage']==phase for k in ['free_before','free_after']]
            free+=values;refs += [x['stream_seq']]*len(values)
        phases[phase]={c:{'min_free_bytes':min(v[c] for v in free),'min_seq':refs[min(range(len(free)),key=lambda i:free[i][c])]} for c in free[0]}
    peaks={c:{k:max(x['memory'][p]['peaks'][c][k] for x in receipts for p in ['before','after']) for k in ['allocated','peak','reserved']} for c in ['xpu:0','xpu:1','xpu:2','xpu:3']}
    prep=read(root/'stream-preparation.json')['snapshot']
    result={'root':str(root),'receipt_count':len(receipts),'frames':receipts[0]['frames'], 'seq_inclusive':[min(byseq),max(byseq)],
            'phase_minima':phases,'allocator_high_water':peaks,'preparation':{'free':prep['physical_free_bytes'],'peaks':prep['peaks']},
            'timings':{k:stats([r[k] for r in rows]) for k in rows[0] if k!='seq'},'timing_rows':rows,
            'minimum_before_cone_free_bytes':min(d['xpu3_free_before_decode'] for d in decodes),
            'sample_minimum_free':{c:min(phases[p][c]['min_free_bytes'] for p in phases) for c in peaks},
            'snapshot_min_margin_bytes':min(s['min_margin_bytes'] for x in receipts for s in x.get('snapshots',[]) if s.get('min_margin_bytes') is not None) if receipts[0].get('snapshots') else None,
            'cone_equal_all':all(d['anchor_decode'].get('equal') is True for d in decodes)}
    if receipts[0]['frames']==145:
        result['freeze']=read(root/'stream-freeze.json');result['geometry']=read(root/'stream-geometry-measured.json')
    if 'stream-120-' in root.name:
        reps=[d['display_replica']['residency'] for d in decodes]
        result['replica']={'max_growth_bytes':max(d['last_decode']['observed_peak_or_reservation_growth_bytes'] for d in reps),
                          'min_before_free_bytes':min(d['last_decode']['before']['free_bytes'] for d in reps),
                          'min_after_free_bytes':min(d['last_decode']['after_free_bytes'] for d in reps),
                          'resident_bytes':reps[0]['resident_bytes'],
                          'pool_growth_bytes':max(d['decoder']['pool']['growth_bytes'] for d in decodes)}
    return result
runs={
 '117_97_dg1':run('*stream-117-frame-dg1*f97',110),
 '118b_121_dg0':run('*stream-118b-frame-dg0*f121.completed-20261010T033817Z',110),
 '120_121_dg1_replica':run('*stream-120-frame-dg1*f121*',110),
 '121_145_dg0':run('*stream-121-frame-dg0*f145',50),
}
for client in ['s120-live01','s121-live01']:
    for name in ['client.log','manifest.jsonl']:
        p=Path('/home/steve/ltx-stream')/client/name
        raw=p.read_bytes();SOURCES[str(p)]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'live_snapshot':True}
        if name=='manifest.jsonl' and client=='s120-live01':
            rows=[json.loads(s) for s in raw.splitlines() if s.strip()]
            runs['120_121_dg1_replica']['manifest_replica_max_growth_bytes']=max(x['display_replica']['residency']['last_decode']['observed_peak_or_reservation_growth_bytes'] for x in rows)
r=runs['121_145_dg0']; q=runs['120_121_dg1_replica']; floors={'xpu:0':8,'xpu:1':8,'xpu:2':2,'xpu:3':9}
census={}
for frames in [145,169]:
    scale=((frames-1)//8+1)/19; poolscale=((frames-1)//8+1)/16
    shared={}
    for c in ['xpu:0','xpu:1','xpu:3']:
        base=r['preparation']['free'][c]/GIB; loss=base-r['sample_minimum_free'][c]/GIB
        shared[c]=[base-loss*scale**2-floors[c],base-loss*scale-floors[c]]
    shared['xpu:2']=[r['sample_minimum_free']['xpu:2']/GIB-2]*2
    base=q['preparation']['free']['xpu:3']/GIB; pool=q['replica']['pool_growth_bytes']/GIB
    nonpool=base-q['sample_minimum_free']['xpu:3']/GIB-pool
    replica={**shared,'xpu:3':[base-pool*poolscale-nonpool*poolscale**2-9,base-pool*poolscale-nonpool*poolscale-9]}
    budget=5.640625 if frames==145 else 6.5
    replica['xpu:2']=[q['replica']['min_before_free_bytes']/GIB-budget-2]*2
    census[str(frames)]={'dg0_margin_gib':shared,'dg1_replica_margin_gib':replica,'pool_gib':pool*poolscale,
                        'replica_growth_gib':[q['replica']['max_growth_bytes']/GIB*poolscale,q['replica']['max_growth_bytes']/GIB*poolscale**2],
                        'replica_budget_gib':budget,'required_margin_gib':.75,'enabled_169':False}
def fit(xs,ys):
    mx=mean(xs);my=mean(ys);s=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)
    return {'intercept_seconds':my-s*mx,'slope_seconds_per_frame':s,'prediction_169':my+s*(169-mx)}
fitrows=[runs[k] for k in ['117_97_dg1','118b_121_dg0','121_145_dg0']]
fits={k:fit([97,121,145],[x['timings'][k]['median'] for x in fitrows]) for k in ['period','sampler_a','sampler_b','cone','residual']}
result={'schema':'ltx.continuation122.cpu-receipt-census.v1','units':'memory bytes unless named GiB; 1GiB=1073741824 bytes',
        'scope':'read-only regular-file CPU analysis; samples and cumulative allocator peaks are not isolated kernel peaks',
        'runs':runs,'census':census,'fits_descriptive_confounded_by_arm':fits,'sources':SOURCES}
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'timing':{k:{v:round(z['median'],6) for v,z in x['timings'].items()} for k,x in runs.items()},'census':census,'fits':fits},indent=2))
