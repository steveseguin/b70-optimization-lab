"""Inherited allocation ledger for both selections; S1 adds no allocation, no full-shape read.

S1 changes only which kernel reads the already-resident expanded rows: the
metadata it reads is part of every expanded Q6_K row the loader already uploads.
Both lineage memory plans are byte-identical (packet153's ledger, whose 64 KiB
rank-0 reserve S1 leaves unused), and the production-shape gate proves the
loaded arena descriptors identical across all five views of both ranks.
"""
import json,resource
from p183_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();rows=[]
 from common import P56,module
 gate=module('p183_memory_admission',P56/'memory_gate.py')
 plans={mode:P/'lineage'/mode/'memory-plan.json' for mode in ('production','metadata')}
 assert sha(plans['production'])==sha(plans['metadata']),'S1 must not change the memory plan'
 for mode,path in plans.items():
  ledger=json.loads(path.read_text());config=gate.configuration(ledger,4096,1,0)
  for rank in config['ranks']:
   assert rank['free_with_mtp_bytes']>=ledger['minimum_free_bytes']
   assert rank['arena_device_bytes']<ledger['arena_limit_bytes']
   rows.append(dict(mode=mode,rank=rank['rank'],modeled_device_bytes=rank['arena_device_bytes'],arena_headroom_bytes=ledger['arena_limit_bytes']-rank['arena_device_bytes'],physical_free_bytes=rank['free_with_mtp_bytes'],minimum_free_bytes=ledger['minimum_free_bytes'],s1_additional_bytes=0))
 shape=json.loads((P/'evidence/full-shape.json').read_text());assert shape['passed']
 assert all(r['result']['passed'] and r['result'].get('fresh_start_capture_identity') for r in shape['runs'])
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'admission_gate.py',*plans.values(),P/'evidence/full-shape.json')}
 save(P/'evidence/admission.json',dict(passed=True,device_executed=False,full_shape_read=False,inherited_ledger=True,driver_residency_unmeasured=True,
  rows=rows,s1_additional_bytes=0,memory_plans_identical=True,view_arena_identity='full-shape: bracket_arena_hash equal across 5 views, both ranks, both orientations',sources=sources))
 print('S1 admission: identical plans, no new bytes; both selections/ranks admitted from the inherited ledger')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
