#!/usr/bin/env python3
"""CPU-only diagnostic replay of retained packet55 routes; never model payloads."""
import argparse
from bisect import bisect_left
import copy
import heapq
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'packet55-feasibility/analysis/locality.py'
spec=importlib.util.spec_from_file_location('packet55_locality_reference',SOURCE)
L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)

class GlobalArena:
    """Cache-table policy mirror: 256B extents, first fit, global recency eviction.

    This adapter commits after each observed route; it does not reproduce the
    future one-card runtime's between-position publication schedule.
    """
    def __init__(self,capacity=18_000_000_000):
        self.capacity=capacity;self.entries={};self.free=[(0,capacity)];self.clock=0;self.heap=[]
        self.evictions=0;self.fills=0;self.fill_bytes=0
    def release(self,offset,size):
        at=bisect_left(self.free,(offset,size));self.free.insert(at,(offset,size))
        if at and self.free[at-1][0]+self.free[at-1][1]==offset:
            old,n=self.free[at-1];self.free[at-1:at+1]=[(old,n+size)];at-=1
        if at+1<len(self.free) and self.free[at][0]+self.free[at][1]==self.free[at+1][0]:
            old,n=self.free[at];self.free[at:at+2]=[(old,n+self.free[at+1][1])]
    def fit(self,size):
        return next((i for i,(_,n) in enumerate(self.free) if n>=size),None)
    def route(self,layer,ids):
        keys=[layer*512+e for e in ids]
        misses=sum(k not in self.entries for k in keys)
        clocks={}
        for key in keys:
            self.clock+=1;clocks[key]=self.clock
            if key in self.entries:
                off,n,_=self.entries[key];self.entries[key]=(off,n,self.clock)
                heapq.heappush(self.heap,(self.clock,key))
        n=(L.packed(layer)+255)//256*256
        for key in keys:
            if key in self.entries or n>self.capacity:continue
            at=self.fit(n)
            while at is None:
                while True:
                    tick,victim=heapq.heappop(self.heap)
                    if victim in self.entries and self.entries[victim][2]==tick:break
                off,size,_=self.entries.pop(victim);self.release(off,size);self.evictions+=1
                at=self.fit(n)
            off,size=self.free[at]
            if size==n:self.free.pop(at)
            else:self.free[at]=(off+n,size-n)
            self.entries[key]=(off,n,clocks[key]);heapq.heappush(self.heap,(clocks[key],key))
            self.fills+=1;self.fill_bytes+=L.packed(layer)
        if len(self.heap)>max(32,len(self.entries)*4):
            self.heap=[(v[2],key) for key,v in self.entries.items()];heapq.heapify(self.heap)
        return misses

def stat():return dict(route_visits=0,requested_bytes=0,miss_bytes=0,missing_experts=0)
def update(row,layer,missing):
    row['route_visits']+=1;row['requested_bytes']+=10*L.packed(layer)
    row['miss_bytes']+=missing*L.packed(layer);row['missing_experts']+=missing

def finish(row):
    n=row['route_visits'];total=row['requested_bytes']
    return dict(row,byte_hit_fraction=1-row['miss_bytes']/total if total else None,
                missed_experts_per_layer_visit=row['missing_experts']/n if n else None,
                missed_bytes_per_layer_visit=row['miss_bytes']/n if n else None)

def replay(window,trace):
    manifest,summary,binding=L.inputs(window,trace)
    quotas=L.placement(18_000_000_000)['quotas']
    trained_layer=L.new_cache('lru',quotas);trained_global=GlobalArena()
    for row in L.records(trace,manifest,summary):
        if row['split']=='train' and row['role']=='target':
            trained_layer[row['layer']].route(row['ids']);trained_global.route(row['layer'],row['ids'])
    names=('per_layer_trained_reset','global_trained_reset','global_empty_persistent')
    totals={name:{phase:stat() for phase in ('prefill','decode')} for name in names}
    persistent=GlobalArena();prompt=None;prompts=[]
    for row in L.records(trace,manifest,summary):
        if row['split']!='test' or row['role']!='target':continue
        if row['prompt_id']!=prompt:
            prompt=row['prompt_id'];prompts.append(prompt)
            layered=copy.deepcopy(trained_layer);global_reset=copy.deepcopy(trained_global)
        layer=row['layer'];phase=row['phase'];ids=row['ids']
        misses=(layered[layer].route(ids),global_reset.route(layer,ids),persistent.route(layer,ids))
        for name,n in zip(names,misses):update(totals[name][phase],layer,n)
    return dict(schema='own-runtime.packet58.cache-policy-replay.v1',passed=True,device_executed=False,
        model_payload_read=False,measured_token_speed=False,source_bindings=binding,
        replay_source_sha256=L.sha(Path(__file__)),policy_source_sha256=L.sha(HERE/'cache_table.hpp'),
        upstream_analysis_sha256=L.sha(SOURCE),route_records=summary['records'],test_prompts=prompts,
        cache_arena_bytes=18_000_000_000,global_slot_alignment=256,
        comparisons={name:{phase:finish(row) for phase,row in phases.items()} for name,phases in totals.items()},
        global_empty_persistent_final=dict(resident_experts=len(persistent.entries),resident_bytes=sum(x[1] for x in persistent.entries.values()),
            free_extents=len(persistent.free),fill_bytes=persistent.fill_bytes,evictions=persistent.evictions),
        interpretation='Observed packet55 split-rank route demand only. Not one-card speed or native hit rate.',
        caveats=['Global order follows packet55 host monotonic ordering across two ranks; not one-card layer order.',
                 'Admissions complete after each observed layer route; packet58 zero-copy admits between positions.',
                 'All speculative/rejected route visits remain charged; packet58 plain decode has a different route stream.',
                 'Global cache budget is data arena; fixed per-layer budget includes its older alignment/metadata.',
                 'Trained-reset cases start every test prompt from the same train-only snapshot; empty-persistent starts empty and retains immutable weights across the 12 test prompts.',
                 'No benchmark prompts train cache placement; retained corpus is packet55 independent calibration.'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--window',type=Path,default=HERE.parent/'packet55-feasibility/route/evidence/cards23-a')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    L.require(not a.output.exists(),'new replay output required')
    row=replay(a.window,a.window/'routes.jsonl.gz')
    a.output.write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({name:phases['decode'] for name,phases in row['comparisons'].items()},indent=2))
if __name__=='__main__':main()
