#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU-only saved receipt overlap census. Never imports the runtime or uses sockets."""
import csv, hashlib, json
from pathlib import Path
from statistics import median
from datetime import datetime, timezone
HERE = Path(__file__).parent
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
SOURCES = {}
def read(path, lines=False):
    data = path.read_bytes()
    SOURCES[str(path)] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return [json.loads(x) for x in data.splitlines() if x.strip()] if lines else json.loads(data)
def overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0])) / 1e9
def interval(t, a, b):
    return (t[a], t[b])
def duration(a):
    return (a[1] - a[0]) / 1e9
def summary(rows):
    return {'n':len(rows), 'long_handoffs':sum(r['handoff_s'] > .15 for r in rows),
            'long_with_measured_maintenance':sum(r['handoff_s'] > .15 and r['handoff_maintenance_s'] > 0 for r in rows),
            'long_with_previous_preview':sum(r['handoff_s'] > .15 and r['handoff_previous_preview_s'] > 0 for r in rows),
            'long_with_previous_tail':sum(r['handoff_s'] > .15 and r['handoff_previous_tail_s'] > 0 for r in rows),
            'long_with_previous_display':sum(r['handoff_s'] > .15 and r['handoff_previous_display_s'] > 0 for r in rows),
            'medians':{k:median(r[k] for r in rows if r[k] is not None) for k in rows[0] if k.endswith('_s') and isinstance(rows[0][k], (float,int))}}
def main():
    runs={}
    for session in ['s121-live01','s121-live02','s123b-legacy-live01','s123b-live01','s123b-live02','s124-live01','s125-live01','s126-live01']:
        manifest=read(Path('/home/steve/ltx-stream')/session/'manifest.jsonl',True)
        first=manifest[0]; packet=first['run_name'].split('-')[0][6:]
        roots=[]
        for candidate in ROOT.glob('encoder-server-continuation-stream-'+packet+'*'):
            p=candidate/'receipts'/('receipt-'+first['run_name']+'.json')
            if p.is_file() and json.loads(p.read_bytes()).get('server_identity_sha256')==first['server_identity_sha256']:
                roots.append(candidate)
        assert len(roots)==1,(session,roots)
        root=roots[0]; receipts={}; decodes={}; previews={}; events={}
        for entry in manifest:
            seq=entry['stream_seq']; name=entry['run_name']
            for kind,table in [('receipt',receipts),('decode',decodes),('preview',previews)]:
                p=root/'receipts'/(kind+'-'+name+'.json')
                if p.is_file():
                    obj=read(p)
                    if kind=='receipt':
                        for event in obj.get('maintenance',{}).get('events',[]):events[event['sequence']]=event
                        table[seq]={k:obj[k] for k in ['timing_ns','snapshots','turnaround','prompt_changed','reuse_text','server_options']}
                    else:table[seq]={'timing_ns':obj['timing_ns']}
        rows=[]
        for seq,r in sorted(receipts.items()):
            if seq<10 or seq+1 not in receipts or seq-1 not in decodes or seq not in decodes or seq-1 not in previews or seq not in previews:continue
            n=receipts[seq+1]; t=r['timing_ns']; nt=n['timing_ns']; marks=n['turnaround']['marks_ns']; dt=decodes[seq]['timing_ns']; pt=decodes[seq-1]['timing_ns']; pv=previews[seq-1]['timing_ns']; v=previews[seq]['timing_ns']; origin=t['submit']
            handoff=interval(marks,'commit_written','first_served'); nextprep=interval(nt,'submit','sampler_a_start')
            intervals={'handoff':handoff, 'next_text_A_prep':nextprep,
                       'previous_display':interval(pt,'display_start','display_done'),
                       'previous_tail':interval(pt,'display_done','record_staged'),
                       'previous_preview':interval(pv,'write_start','preview_written'),
                       'own_A_precompute':interval(dt,'precompute_a_start','precompute_a_done'),
                       'own_display':interval(dt,'display_start','display_done'),
                       'own_tail':interval(dt,'display_done','record_staged'),
                       'own_preview':interval(v,'write_start','preview_written'),
                       'next_request_snapshot':interval(nt,'request_snapshot_start','request_snapshot_done')}
            maintenance=[e for e in events.values() if e['timing_ns'].get('cache_done') and overlap((e['timing_ns']['gc_start'],e['timing_ns']['cache_done']),handoff)>0]
            row={'session':session,'seq':seq,'modulo4':seq%4,'fresh_text':r['prompt_changed'],
                 'origin_ns':origin,'period_s':(nt['submit']-t['submit'])/1e9,'submit_to_A_s':(t['sampler_a_start']-t['submit'])/1e9,
                 'handoff_s':duration(handoff),'next_text_A_prep_s':duration(nextprep),
                 'intervals_relative_s':{k:[(x-origin)/1e9 for x in v] for k,v in intervals.items()},
                 'maintenance_events':maintenance,'maintenance_recorded':bool(events)}
            for win in ['handoff','next_text_A_prep']:
                for work in ['previous_display','previous_tail','previous_preview','own_A_precompute','own_display','own_tail','own_preview','next_request_snapshot']:
                    row[win+'_'+work+'_s']=overlap(intervals[win],intervals[work])
                for label,a,b in [('maintenance','gc_start','cache_done'),('gc','gc_start','gc_done'),('cache','gc_done','cache_done')]:
                    row[win+'_'+label+'_s']=sum(overlap(intervals[win],(e['timing_ns'][a],e['timing_ns'][b])) for e in events.values() if e['timing_ns'].get(b))
            row['preview_end_before_commit_s']=(handoff[0]-intervals['previous_preview'][1])/1e9
            row['maintenance_end_to_served_s']=None if not maintenance else (handoff[1]-max(e['timing_ns']['cache_done'] for e in maintenance))/1e9
            rows.append(row)
        runs[session]={'root':str(root),'identity':first['server_identity_sha256'],'frames':first['frames'],'options':r['server_options'],
            'summary':summary(rows),'parity':{str(k):summary([r for r in rows if r['seq']%2==k]) for k in range(2)},
            'modulo4':{str(k):summary([r for r in rows if r['seq']%4==k]) for k in range(4)},'rows':rows,
            'maintenance_events':list(events.values())}
        print(session,json.dumps(runs[session]['summary']))
    for rel in ['main.py','scripts/integration.py','scripts/maintenance125.py','scripts/stream_preview.py','scripts/stream_decode.py','scripts/run_storage.py','comfy_api/latest/_input_impl/video_types.py']:
        p=ROOT/'prepared-continuation-stream-127'/'source'/rel
        data=p.read_bytes(); SOURCES[str(p)]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    out={'schema':'ltx.continuation128.saved-overlap.v1','captured_utc':datetime.now(timezone.utc).isoformat(),
         'definition':'Source sequence parity. Handoff=commit_written to first_served. Closed positive overlap of raw absolute ns. Next prep=next submit to next sampler A. No synthetic timelines.',
         'runs':runs,'sources':SOURCES}
    checks={'all_requested_sessions':len(runs)==8,'all_frames145':all(r['frames']==145 for r in runs.values()),
            'all_periods_positive':all(x['period_s']>0 for r in runs.values() for x in r['rows']),
            'all_handoff_durations_close':all(abs(x['handoff_s']-(x['intervals_relative_s']['handoff'][1]-x['intervals_relative_s']['handoff'][0]))<1e-8 for r in runs.values() for x in r['rows']),
            'maintenance_subparts_close':all(abs(x['handoff_maintenance_s']-x['handoff_gc_s']-x['handoff_cache_s'])<1e-8 for r in runs.values() for x in r['rows']),
            'all_input_hashes_recorded':bool(SOURCES) and all(len(x['sha256'])==64 for x in SOURCES.values())}
    assert all(checks.values()),checks
    out['structural_checks']={'passed':len(checks),'failed':0,'checks':checks}
    (HERE/'continuation128-overlap-evidence.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    with (HERE/'continuation128-overlap-table.csv').open('w',newline='') as f:
        rows=[x for r in runs.values() for x in r['rows']]; fields=[k for k in rows[0] if k not in ['intervals_relative_s','maintenance_events']]
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    print('structural_checks',len(checks),'rows',sum(len(r['rows']) for r in runs.values()),'sources',len(SOURCES))
if __name__=='__main__':main()
