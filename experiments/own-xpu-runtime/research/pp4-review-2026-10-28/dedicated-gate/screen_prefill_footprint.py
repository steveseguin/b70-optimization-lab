#!/usr/bin/env python3
"""CPU source-derived prefill_allocate census from actual split launch plans."""
import hashlib,json
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime')
RUN=Path('/dev/shm/sc117-dedicated-2plus1-128k-gate-20261028-r1/output')

def screen(plan,rank,rows=256):
 bs={b['name']:b['bytes'] for b in plan['buffers']}
 role=lambda n:'blk.*'+n[n.find('.',4):] if n.startswith('blk.') else n
 persistent=lambda n:n in ('error','active','token_history','ple_metadata') or n.endswith(('.state','history','.keys','.values','.raw','.pooled'))
 sites=[l for l in plan['launches'] if not l['label'].startswith('final.') and l['label'] not in ('logits','argmax') and l['op'] not in ('handoff','handoff_result')]
 roles={};mapping={}
 for l in sites:
  for name in l['inputs']+l['outputs']:
   if name in ('position','token') or persistent(name):continue
   r=role(name);mapping[name]=r;roles[r]=max(roles.get(r,0),bs[name])
 slotbytes=[];members=[];assigned={}
 if rank==1:
  live={};opened={}
  for i,l in enumerate(sites):
   for name in l['inputs']:
    if name in mapping:
     r=mapping[name];opened[r]=(opened[r][0],i) if r in opened else (0,i)
   for name in l['outputs']:
    if name in mapping:
     r=mapping[name]
     if r in opened:live.setdefault(r,[]).append(opened[r])
     opened[r]=(0 if l['op']=='lookup' else i,i)
  for r,seg in opened.items():live.setdefault(r,[]).append(seg)
  for r in live:
   if not r.startswith('blk.*'):live[r]=[(0,len(sites))]
  assert roles.keys()<=live.keys()
  overlap=lambda a,b:any(x<=v and u<=y for x,y in live[a] for u,v in live[b])
  for r,size in sorted(roles.items(),key=lambda x:(-x[1],x[0])):
   candidates=[k for k,group in enumerate(members) if all(not overlap(r,q) for q in group)]
   best=min(candidates,key=lambda k:slotbytes[k]) if candidates else len(members)
   if best==len(members):members.append([]);slotbytes.append(0)
   members[best].append(r);slotbytes[best]=max(slotbytes[best],size);assigned[r]=best
 else:slotbytes=list(roles.values())
 shadow=sum(slotbytes)*rows;extras=8*rows*4+8*rows*5*4+64+2*rows*4
 return dict(rank=rank,rows=rows,sites=len(sites),roles=len(roles),role_buffers=len(mapping),packed_slots=len(slotbytes) if rank==1 else None,shadow_bytes=shadow,unpacked_bytes=sum(roles.values())*rows,xgroup_and_position_token_bytes=extras,added_device_bytes=shadow+extras,slots=[dict(bytes=slotbytes[i]*rows,roles=group) for i,group in enumerate(members)])
if __name__=='__main__':
 results=[]
 for rank,current in ((0,31548580340),(1,32028995744)):
  path=RUN/f'stage{rank}/native/launch-plan.json';d=screen(json.loads(path.read_text()),rank);d.update(source=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),current_actual_census_bytes=current,projected_with_prefill_bytes=current+d['added_device_bytes'],remaining_30GiB_bytes=30*1024**3-current-d['added_device_bytes']);results.append(d)
 validation=[]
 for rank in range(4):
  native=Path('/dev/shm/pp4-overlap-gate-20261028/output')/f'stage{rank}/native';allocation=native/'prefill-allocation.json';launch=native/'launch-plan.json';actual=json.loads(allocation.read_text());derived=screen(json.loads(launch.read_text()),0 if rank==0 else 1)
  for field in ('shadow_bytes','roles','sites'):assert actual[field]==derived[field]
  if rank:assert actual['packed_slots']==derived['packed_slots'] and actual['unpacked_bytes']==derived['unpacked_bytes']
  validation.append(dict(stage=rank,passed=True,actual=actual,allocation_source=str(allocation),allocation_sha256=hashlib.sha256(allocation.read_bytes()).hexdigest(),launch_sha256=hashlib.sha256(launch.read_bytes()).hexdigest()))
 report=dict(prior_actual_native_validation=validation,schema='ownrt.dedicated-128k-prefill-source-footprint.v1',device_work=False,rows=256,results=results,scope='Source-exact transcription of prefill_allocate live-role packing for neutral-V3 general pipeline plans, rank1 packing enabled, xgroup enabled/top8. Not actual native allocation execution; excludes dynamic driver/JIT or future extra device allocation. Provider owns only10MiB host rawcopy, no target shadows.',source_sha256=hashlib.sha256((ROOT/'engine/src/gsq-rco-iq3s/dense-packed-block/engine/build/source/prefill_engine.hpp').read_bytes()).hexdigest())
 out=Path(__file__).with_name('128k-prefill-footprint.json');out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps([{k:v for k,v in r.items() if k!='slots'} for r in results],indent=2))
