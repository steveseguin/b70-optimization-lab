#!/usr/bin/env python3
"""Check provenance, joins, cache replay against an independent policy oracle."""
from collections import OrderedDict
import gzip
import hashlib
import json
from pathlib import Path
import random
import statistics as st
import sys

from replay import Arena, packed

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def main():
    original='--originals' in sys.argv
    inputs=json.loads((HERE/'inputs.json').read_text())
    for name,record in inputs.items():
        raw=gzip.decompress((HERE/record['archive']).read_bytes())
        assert len(raw)==record['bytes']
        assert hashlib.sha256(raw).hexdigest()==record['sha256']
        if original:
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==record['sha256'],name
    # Independent equal-sized LRU reference: touch all selected keys before eviction.
    rng=random.Random(58)
    cache=Arena(40*packed(0))
    reference=OrderedDict()
    for _ in range(1200):
        ids=rng.sample(range(80),10)
        missing=sum(k not in reference for k in ids)
        for key in ids:
            reference.pop(key,None)
            reference[key]=True
        while len(reference)>40:
            reference.popitem(last=False)
        row=cache.route(0,ids)
        assert row['misses']==missing
        assert set(reference)==set(cache.entries)
        assert cache.entries[ids[-1]][2]==cache.clock
    # Never select or admit based on current demand before a speculative prediction.
    cache=Arena(40*packed(0),'twohit')
    row=cache.route(0,list(range(10)))
    assert row['misses']==10 and row['demand_fill_bytes']==0
    row=cache.route(0,list(range(10)))
    assert row['misses']==10 and row['demand_fill_bytes']==10*packed(0)
    assert cache.route(0,list(range(10)))['misses']==0
    cache=Arena(40*packed(0),'lfu')
    reference={}
    tick=0
    for _ in range(1000):
        ids=rng.sample(range(80),10)
        missing=[key for key in ids if key not in reference]
        ticks={}
        for key in ids:
            tick+=1
            ticks[key]=tick
            if key in reference:
                reference[key]=(reference[key][0]+1,tick)
        for key in missing:
            if len(reference)==40:
                victim=min((k for k in reference if k not in ids),key=lambda k:(*reference[k],k))
                del reference[victim]
            reference[key]=(1,ticks[key])
        row=cache.route(0,ids)
        assert row['misses']==len(missing)
        assert set(reference)==set(cache.entries)
    # Unequal layer2 extents: first-fit and coalescing must cover the arena exactly.
    cache=Arena(40*packed(0))
    for i in range(300):
        layer=2 if i%3==0 else 0
        cache.route(layer,rng.sample(range(80),10))
        extents=sorted([(e[0],e[1]) for e in cache.entries.values()]+cache.free)
        end=0
        for off,n in extents:
            assert off==end and n>0
            end=off+n
        assert end==cache.capacity
    a=json.loads((HERE/'ATTRIBUTION.json').read_text())
    rows=[json.loads(x) for x in gzip.decompress((HERE/'position-attribution.jsonl.gz').read_bytes()).decode().splitlines()]
    selected=[r for r in rows if r['window']=='WS128' and r['phase']=='decode' and 2<=r['timing']['generated_index']<=100]
    assert len(selected)==1188
    for r in selected:
        assert r['timing']['copy_counts'][0]['host_to_device']==3*r['cache']['fills']+147
        assert r['timing']['copy_counts'][0]['device_to_host']==50
    assert st.mean(r['cache']['wall_ms'] for r in selected)==a['windows']['WS128']['metric_1_100']['cache']['wall_ms']['mean']
    s=a['windows']['WS128']['prompts']
    by_class={}
    for p in s.values():
        rate=99000/p['measured_interval_ms']
        assert abs(rate-p['recorded_rate'])<1e-10
        by_class.setdefault(p['prompt_class'],[]).append(rate)
    assert st.median(st.median(v) for v in by_class.values())==a['baseline']
    assert a['headroom']['declared_host_budget_bytes']==118308908048
    replay=json.loads((HERE/'route-replay.json').read_text())
    for name,result in replay['comparisons'].items():
        for phase,total in result['totals'].items():
            for key,value in total.items():
                assert sum(layer.get(key,0) for layer in result['per_layer'][phase])==value
                assert sum(p['totals'][phase].get(key,0) for p in result['prompts'])==value
        assert result['final_resident_bytes']<=result['capacity']
    assert a['decision']['status']=='closeout_no_build'
    for name in ('experts','HC','recurrence','attention','head'):
        assert a['windows']['WS128']['metric_1_100']['operator_ms'][name] is None
    report=dict(passed=True,original_evidence_hashes_checked=original,archived_inputs=len(inputs),
        lru_oracle_positions=1200,lfu_oracle_positions=1000,variable_extent_positions=300,metric_intervals=1188,
        device_executed=False,runtime_quality_claim=False)
    (HERE/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
