#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Read frozen regular-file evidence only. No runtime imports or device operations."""
import hashlib
import json
from pathlib import Path
from statistics import median, mean

ROOT=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
HERE=Path(__file__).parent
GIB=2**30
FLOORS={'xpu:0':8,'xpu:1':8,'xpu:2':2,'xpu:3':9}
SOURCES={}
def read(path):
    raw=path.read_bytes()
    SOURCES[str(path)]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    return json.loads(raw)
def stats(values):
    values=sorted(values)
    return dict(n=len(values),min=min(values),median=median(values),mean=mean(values),max=max(values))
def collect(pattern,end,comparison_end):
    paths=list(ROOT.glob(pattern));assert len(paths)==1,paths
    root=paths[0]
    rs={i:read(root/'receipts'/('receipt-stream123b-s%08d.json'%i)) for i in range(end+1)}
    ds={i:read(root/'receipts'/('decode-stream123b-s%08d.json'%i)) for i in range(end+1)}
    rows=[]
    for i in range(10,end):
        r,d,n=rs[i],ds[i],ds[i+1];t=d['timing_ns'];nt=n['timing_ns'];base=rs[i+1]['timing_ns']['submit']
        def rel(v):return (v-base)/1e9
        rows.append(dict(seq=i,next_seq=i+1,origin='successor submit',origin_ns=base,
            period=(base-r['timing_ns']['submit'])/1e9,
            sampler_a=r['timing_s']['sampler_a_split']['sampler_a'],sampler_b=r['timing_s']['sampler_b'],
            cone_chain=r['timing_s']['anchor_decode_in_chain'],cone_actual=d['anchor_decode']['seconds'],
            queue_wait=d['timing_s']['queue_wait'],go_event_wait=d['schedule']['go_wait_s'],
            anchor_ready_to_go=d['timing_s']['anchor_ready_to_go'],display=d['timing_s']['display_decode'],
            display_start=rel(t['display_start']),display_end=rel(t['display_done']),
            decode_record=rel(t['record_staged']),next_decode_queued=rel(nt['decode_queued']),
            next_cone_start=rel(nt['decode_start']),next_cone_end=rel(nt['video_done']),
            next_fifo=n['timing_s']['queue_wait'],
            previous_display_remaining_at_enqueue=max(0,(t['display_done']-nt['decode_queued'])/1e9),
            previous_tail_after_display=(t['record_staged']-t['display_done'])/1e9,
            next_worker_after_record=(nt['decode_start']-t['record_staged'])/1e9,
            cone_display_overlap=max(0,(min(t['display_done'],nt['video_done'])-max(t['display_start'],nt['decode_start']))/1e9)))
    def summary(xs):return {k:stats([x[k] for x in xs]) for k in xs[0] if k not in ('seq','next_seq','origin','origin_ns')}
    phases={}
    for phase in ['before','A','B','after']:
        vals=[(i,v) for i,x in rs.items() for v in ([x['memory'][phase]['free']] if phase in ['before','after'] else [c[k] for c in x['memory']['conditioning'] if c['stage']==phase for k in ['free_before','free_after']])]
        phases[phase]={c:dict(min_free_bytes=min(v[c] for i,v in vals),min_free_gib=min(v[c] for i,v in vals)/GIB,min_seq=min(vals,key=lambda iv:iv[1][c])[0]) for c in FLOORS}
    peaks={c:{k:max(x['memory'][p]['peaks'][c][k] for x in rs.values() for p in ['before','after'])/GIB for k in ['allocated','peak','reserved']} for c in FLOORS}
    minimum={c:min(v[c]['min_free_gib'] for v in phases.values()) for c in FLOORS}
    prep=read(root/'stream-preparation.json')
    return dict(root=str(root),seq_inclusive=[0,end],receipt_count=len(rs),decode_count=len(ds),
        frames=rs[0]['frames'],options=rs[0]['server_options'],freeze=read(root/'stream-freeze.json'),
        phase_minima=phases,allocator_high_water_gib=peaks,minimum_free_gib=minimum,
        margins_gib={c:v-FLOORS[c] for c,v in minimum.items()},preparation_free_gib={c:v/GIB for c,v in prep['snapshot']['physical_free_bytes'].items()},
        before_cone_min_gib=min(d['xpu3_free_before_decode'] for d in ds.values())/GIB,
        all_cone_equal=all(d['anchor_decode']['equal'] for d in ds.values()),
        snapshot_min_margin_bytes=min(s['min_margin_bytes'] for r in rs.values() for s in r['snapshots']),
        dual_snapshot_count=sum(s['dual'] for r in rs.values() for s in r['snapshots']),
        snapshot_count=sum(len(r['snapshots']) for r in rs.values()),
        snapshot_timeline=[dict(seq=i, snapshots=[dict(label=z['label'],start_ns=z['start_ns'],end_ns=z['end_ns'],synchronized=z['synchronized'],dual=z['dual']) for z in rs[i]['snapshots']]) for i in range(end+1)],
        rows=rows,final_interior=summary(rows),fixed_comparison_window=[10,comparison_end],
        fixed_comparison_interior=summary([x for x in rows if x['seq']<=comparison_end]),
        go_reasons={v:sum(d['schedule']['go']==v for d in ds.values()) for v in set(d['schedule']['go'] for d in ds.values())})
runs={'169_aux':collect('*123b*f169-auxxpu2',48,36),'145_aux':collect('*123b*f145-auxxpu2.completed-*',40,32)}
old=read(HERE/'continuation122-evidence.json')
# Actual cone costs at old lengths supplement the preserved broad census.
scaling=[]
for key in ['117_97_dg1','118b_121_dg0','120_121_dg1_replica','121_145_dg0']:
    run=old['runs'][key];ds=[]
    oldroot=Path(run['root'])
    if not oldroot.is_dir():
        roots=list(ROOT.glob(oldroot.name+'*'))
        pins=[(Path(k).relative_to(oldroot),v['sha256']) for k,v in old['sources'].items() if k.startswith(str(oldroot)+'/receipts/decode-')][:1]
        roots=[p for p in roots if all((p/rel).is_file() and hashlib.sha256((p/rel).read_bytes()).hexdigest()==h for rel,h in pins)]
        assert len(roots)==1,roots
        oldroot=roots[0]
    for i in range(10,run['seq_inclusive'][1]):
        candidates=list((oldroot/'receipts').glob('decode-*-s%08d.json'%i));assert len(candidates)==1
        ds.append(read(candidates[0]))
    scaling.append(dict(arm=key,frames=run['frames'],n=len(ds),new_video_seconds=(run['frames']-1)/24,
        cone_actual=median(d['anchor_decode']['seconds'] for d in ds),cone_chain=run['timings']['cone']['median'],
        display=run['timings']['display']['median'],period=run['timings']['period']['median']))
for key,r in runs.items():
    t=r['fixed_comparison_interior'];scaling.append(dict(arm=key,frames=r['frames'],n=t['period']['n'],new_video_seconds=(r['frames']-1)/24,cone_actual=t['cone_actual']['median'],cone_chain=t['cone_chain']['median'],display=t['display']['median'],period=t['period']['median']))
up=995735808/GIB;audio=364666868/GIB
m=runs['169_aux']['margins_gib']
rep=old['runs']['120_121_dg1_replica']['replica']
census=dict(upsampler_gib=up,audio_gib=audio,
    legacy169_margins_gib={'xpu:0':m['xpu:0']-up,'xpu:1':m['xpu:1'],'xpu:2':rep['min_before_free_bytes']/GIB-6.5-2,'xpu:3':m['xpu:3']-audio},
    aux_to1_static_margin_gib=m['xpu:1']-up-audio,
    replica_budget_gib=6.5,replica169_growth_range_gib=[rep['max_growth_bytes']/GIB*22/16,rep['max_growth_bytes']/GIB*(22/16)**2],
    replica145_growth_range_gib=[rep['max_growth_bytes']/GIB*19/16,rep['max_growth_bytes']/GIB*(19/16)**2],
    required_screening_margin_gib=.75,
    limitations='Phase samples and cumulative allocator peaks, not isolated kernel peaks. Static credits are planning counterfactuals, not measured legacy169. Replica budget derives from 121 measured growth, and coexisting concurrent work must be checked natively.')
for client in ['s123b-f169-live01','s123b-live01']:
    for name in ['client.log','manifest.jsonl','qualification.jsonl']:
        path=Path('/home/steve/ltx-stream')/client/name;raw=path.read_bytes()
        SOURCES[str(path)]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
result=dict(schema='ltx.continuation124.cpu-evidence.v1',runs=runs,decoder_scaling=scaling,census=census,sources=SOURCES)
(HERE/'continuation124-evidence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(timings={k:v['fixed_comparison_interior'] for k,v in runs.items()},memory={k:v['margins_gib'] for k,v in runs.items()},scaling=scaling,census=census,source_count=len(SOURCES)),indent=2))
