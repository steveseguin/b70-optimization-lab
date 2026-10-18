#!/usr/bin/env python3
"""Bounded CPU proxy replay. Packet55 routes are NOT packet58g one-card routes."""
from bisect import bisect_left
from collections import Counter
import gzip
import hashlib
import heapq
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
SOURCE=HERE.parent/'packet55-feasibility/analysis/locality.py'
WINDOW=HERE.parent/'packet55-feasibility/route/evidence/cards23-a'


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def packed(layer):
    return 2329600 if layer==2 else 1971200


class Arena:
    """256-byte first fit; protect this selected route, publish after each route.

    This is deliberately a proxy, not a mirror of end-position 58g publication.
    LFU counts since admission, two-hit tracks prior observed demand (24,576 IDs).
    """
    def __init__(self, capacity, policy='lru'):
        self.capacity=capacity
        self.policy=policy
        self.entries={}
        self.free=[(0,capacity)]
        self.heap=[]
        self.clock=0
        self.seen=Counter()

    def release(self, off, n):
        at=bisect_left(self.free,(off,n))
        self.free.insert(at,(off,n))
        if at and self.free[at-1][0]+self.free[at-1][1]==off:
            old,size=self.free[at-1]
            self.free[at-1:at+1]=[(old,size+n)]
            at-=1
        if at+1<len(self.free) and sum(self.free[at])==self.free[at+1][0]:
            old,size=self.free[at]
            self.free[at:at+2]=[(old,size+self.free[at+1][1])]

    def score(self, e):
        return (e[3] if self.policy=='lfu' else 0,e[2])

    def touch(self, key):
        e=self.entries[key]
        self.entries[key]=(e[0],e[1],self.clock,e[3]+1)
        heapq.heappush(self.heap,(*self.score(self.entries[key]),key))

    def insert(self, key, protected, tick=None):
        n=packed(key//512)
        def fit():
            return next((i for i,(_,size) in enumerate(self.free) if size>=n),None)
        at=fit()
        while at is None:
            defer=[]
            while True:
                count,victim_tick,victim=heapq.heappop(self.heap)
                if victim not in self.entries or self.score(self.entries[victim])!=(count,victim_tick):
                    continue
                if victim in protected:
                    defer.append((count,victim_tick,victim))
                    continue
                break
            for item in defer:
                heapq.heappush(self.heap,item)
            off,size,_,_=self.entries.pop(victim)
            self.release(off,size)
            at=fit()
        off,size=self.free[at]
        if size==n:
            self.free.pop(at)
        else:
            self.free[at]=(off+n,size-n)
        self.entries[key]=(off,n,self.clock if tick is None else tick,1)
        heapq.heappush(self.heap,(*self.score(self.entries[key]),key))
        return n

    def route(self, layer, ids, prefetch=None):
        # Predictor sees only independent training frequencies and existing cache.
        # It must choose before receiving this route's IDs.
        speculative_bytes=0
        spec_key=None
        if prefetch:
            spec_key=next((layer*512+i for i in prefetch[layer] if layer*512+i not in self.entries),None)
            if spec_key is not None:
                self.clock+=1
                speculative_bytes=self.insert(spec_key,set())
        keys=[layer*512+i for i in ids]
        protected=set(keys)
        missing=[k for k in keys if k not in self.entries]
        stamps={}
        for k in keys:
            self.clock+=1
            stamps[k]=self.clock
            self.seen[k]+=1
            if k in self.entries:
                self.touch(k)
        fills=0
        for k in missing:
            if self.policy=='twohit' and self.seen[k]<2:
                continue
            fills+=self.insert(k,protected,stamps[k])
        if len(self.heap)>max(32,len(self.entries)*4):
            self.heap=[(*self.score(e),k) for k,e in self.entries.items()]
            heapq.heapify(self.heap)
        return dict(visits=1,requested_bytes=10*packed(layer),miss_bytes=len(missing)*packed(layer),
                    misses=len(missing),demand_fill_bytes=fills,speculative_fill_bytes=speculative_bytes,
                    useful_prefetches=int(spec_key in protected if spec_key is not None else False))


def prepare_inputs():
    """Validate original converter/native bindings once; keep compact replay inputs."""
    target=HERE/'route-inputs'
    binding_path=target/'binding.json'
    if binding_path.exists():
        binding=json.loads(binding_path.read_text())
        for p in binding['prompts']:
            assert digest(target/p['file'])==p['sha256']
        assert digest(target/'training-frequencies.json')==binding['training_frequencies_sha256']
        return binding
    target.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('p55_locality',SOURCE)
    L=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)
    trace=WINDOW/'routes.jsonl.gz'
    manifest,summary,source_binding=L.inputs(WINDOW,trace)
    freq=[Counter() for _ in range(48)]
    prompts={}
    for r in L.records(trace,manifest,summary):
        if r['role']!='target':
            continue
        if r['split']=='train':
            freq[r['layer']].update(r['ids'])
        else:
            prompts.setdefault(r['prompt_id'],[]).append([int(r['phase']=='decode'),r['layer'],r['ids']])
    prompt_rows=[]
    for name,rows in prompts.items():
        path=target/(name+'.jsonl.gz')
        data=('\n'.join(json.dumps(r,separators=(',',':')) for r in rows)+'\n').encode()
        path.write_bytes(gzip.compress(data,mtime=0))
        prompt_rows.append(dict(prompt_id=name,file=path.name,sha256=digest(path),route_visits=len(rows)))
    f=target/'training-frequencies.json'
    f.write_text(json.dumps([{str(k):v for k,v in sorted(c.items())} for c in freq],separators=(',',':'))+'\n')
    binding=dict(schema='packet58i.proxy-routes.v1',source_bindings=source_binding,
        source_trace=str(trace.relative_to(ROOT)), source_records=summary['records'],
        validator_source=str(SOURCE.relative_to(ROOT)),validator_sha256=digest(SOURCE),
        original_native_bindings_validated=True,benchmark_training=False,
        original_record_order_preserved=True,role='target',split='test',
        training_frequencies_sha256=digest(f),prompts=prompt_rows,
        caveats=['Two-rank speculative route visits, including rejected work; not one-card plain decode.',
                 'Publication after each route, not after the complete position.',
                 'Compact rows retain exact phase/layer/IDs for this byte-demand replay; they are not model-output evidence.'])
    binding_path.write_text(json.dumps(binding,indent=2)+'\n')
    return binding


def main():
    binding=prepare_inputs()
    raw=json.loads((HERE/'route-inputs/training-frequencies.json').read_text())
    freq=[sorted(range(512),key=lambda k:(-d.get(str(k),0),k)) for d in raw]
    configs={
        '18GB_LRU':(18000000000,'lru',False),
        '20.121GB_LRU_conditional_budget':(20121486620,'lru',False),
        '18GB_LFU':(18000000000,'lfu',False),
        '18GB_twohit_admission':(18000000000,'twohit',False),
        '18GB_frequency_one_prefetch_per_visit':(18000000000,'lru',True)}
    result={}
    for name,(cap,policy,speculative) in configs.items():
        arena=Arena(cap,policy)
        totals={'prefill':Counter(),'decode':Counter()}
        perlayer={phase:[Counter() for _ in range(48)] for phase in totals}
        prompts=[]
        for prompt in binding['prompts']:
            sums={'prefill':Counter(),'decode':Counter()}
            with gzip.open(HERE/'route-inputs'/prompt['file'],'rt') as f:
                for line in f:
                    decode,layer,ids=json.loads(line)
                    phase='decode' if decode else 'prefill'
                    row=arena.route(layer,ids,freq if speculative else None)
                    totals[phase].update(row)
                    sums[phase].update(row)
                    perlayer[phase][layer].update(row)
            prompts.append(dict(prompt_id=prompt['prompt_id'],totals=sums))
            extents=sorted([(e[0],e[1]) for e in arena.entries.values()]+arena.free)
            end=0
            for off,size in extents:
                assert off==end and size>0
                end=off+size
            assert end==cap
        result[name]=dict(capacity=cap,policy=policy,speculative=speculative,totals=totals,
                          per_layer=perlayer,prompts=prompts,
                          final_resident_bytes=sum(e[1] for e in arena.entries.values()))
        print(name,dict(totals['decode']),flush=True)
    report=dict(schema='packet58i.route-replay.v1',device_executed=False,benchmark_training=False,
                native_onecard_prediction=False,initial_cache='empty, persists across held-out prompts',
                caveats=binding['caveats'],binding_sha256=digest(HERE/'route-inputs/binding.json'),
                comparisons=result)
    (HERE/'route-replay.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
