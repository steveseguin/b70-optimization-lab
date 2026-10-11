"""CPU summary of two native owners; timestamps are execution, not event spans."""
import argparse,json,math,statistics
from collections import defaultdict
from pathlib import Path

def percentile90(values):
    return sorted(values)[math.ceil(.9*len(values))-1]

def summarise(records):
    grouped=defaultdict(list);frequencies={};classes={}
    for row in records:
        assert row['passed'] is True
        key=(row['owner'],row['shape'],row['candidate'])
        events=row['events'];assert 1<=len(events)<=2
        intervals=[e['command_end_ns']-e['command_start_ns'] for e in events]
        assert all(x>0 for x in intervals)
        grouped[key].append((row['repetition'],sum(intervals)/1e6))
        frequencies[row['shape']]=row['frequency'];classes[row['shape']]=row['class']
    stats={}
    for key,samples in grouped.items():
        assert len(samples)==200 and {r for r,_ in samples}==set(range(200)), 'missing/duplicate samples'
        values=[v for _,v in samples]
        stats[key]=dict(median_ms=statistics.median(values),p90_ms=percentile90(values))
    rows=[]
    for (owner,shape,candidate),value in stats.items():
        baseline=stats[(owner,shape,'current')]['median_ms']
        rows.append(dict(owner=owner,shape=shape,**{'class':classes[shape]},candidate=candidate,**value,launch_groups_per_token=frequencies[shape],ms_per_token_saved=(baseline-value['median_ms'])*frequencies[shape]))
    assert {r['owner'] for r in rows}=={1,2}, 'two fresh owners required'
    a={(r['shape'],r['candidate']) for r in rows if r['owner']==1}
    b={(r['shape'],r['candidate']) for r in rows if r['owner']==2}
    assert a==b, 'fresh owners have different candidate coverage'
    combined=[]
    for shape,candidate in sorted(a):
        both=[r for r in rows if r['shape']==shape and r['candidate']==candidate]
        combined.append(dict(shape=shape,**{'class':both[0]['class']},candidate=candidate,median_ms=statistics.median(r['median_ms'] for r in both),p90_ms=statistics.median(r['p90_ms'] for r in both),ms_per_token_saved=statistics.median(r['ms_per_token_saved'] for r in both),owner_rows=both))
    return sorted(combined,key=lambda r:r['ms_per_token_saved'],reverse=True)

def sequence_summary(rows, full=False):
    groups=defaultdict(list)
    for row in rows:
        assert row['waits']==1
        if full:
            assert row['layers']==48 and row['launch_groups']==253
            key=row['tier'];assert 0<=key<7
        else:
            assert row['layer_positions']==48 and 0<row['launch_groups']<=48
            key=(row['shape'],row['candidate'])
        assert math.isfinite(row['wall_ms']) and row['wall_ms']>0
        groups[key].append(row)
    if full:assert set(groups)==set(range(7)), 'missing full sequence tier'
    out=[]
    for key,values in groups.items():
        assert len(values)==200 and {r['repetition'] for r in values}==set(range(200)), 'sequence coverage'
        ms=[r['wall_ms'] for r in values]
        out.append(dict(key=key,median_wall_ms=statistics.median(ms),p90_wall_ms=percentile90(ms)))
    return out

def write_summary(window):
    window=Path(window)
    w=json.loads((window/'window.json').read_text());assert w['passed'] and w['window']=='G1' and w['fresh_owners']==2
    records=[];sequences=[]
    for owner in (1,2):
        for line in (window/f'run/owner{owner}/timing.jsonl').read_text().splitlines():records.append(dict(json.loads(line),owner=owner))
        root=window/f'run/owner{owner}'
        readlines=lambda name:[json.loads(line) for line in (root/name).read_text().splitlines()]
        plan=readlines('full-sequence-plan.jsonl')
        assert len(plan)==7*13 and len({(r['tier'],r['shape']) for r in plan})==7*13
        sequences.append(dict(owner=owner,classes=sequence_summary(readlines('sequence-wall.jsonl')),full=sequence_summary(readlines('full-sequence-wall.jsonl'),True)))
    result=summarise(records)
    (window/'sequence-summary.json').write_text(json.dumps(sequences,indent=2)+'\n')
    (window/'ranked.json').write_text(json.dumps(dict(diagnostic=True,real_model_qualified=False,rows=result),indent=2)+'\n')
    lines=['| Shape | Candidate | Median ms | p90 ms | ms/token saved |','| --- | --- | ---: | ---: | ---: |']
    for r in result:lines.append(f"| {r['shape']} | {r['candidate']} | {r['median_ms']:.6f} | {r['p90_ms']:.6f} | {r['ms_per_token_saved']:.6f} |")
    text='\n'.join(lines)+'\n';(window/'ranked.md').write_text(text);print(text)
    return 0
def main():
    p=argparse.ArgumentParser();p.add_argument('window',type=Path);a=p.parse_args();return write_summary(a.window)
if __name__=='__main__':raise SystemExit(main())
