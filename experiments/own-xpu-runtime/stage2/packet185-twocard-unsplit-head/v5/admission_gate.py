"""Allocation admission for both selections from the measured production-shape census.

`production` (bundle 8, split head) keeps packet183/153's ledger byte for byte. `unsplit`
(full target head on rank 1) is that ledger plus the census delta measured by
p185_v5_full_shape.py with the real allocation calls (rank 0: no suffix rows, no p105
auxiliary buffers; rank 1: all 248,320 expanded Q6_K head rows). Host admission is
unchanged: 97 GiB + 1200 MiB = 105,411,248,128 B MemAvailable at START plus the queue's
1 GiB (the multi-card host shadow tracks device bytes; the two deltas net to -1.57 MB).
"""
import json,resource
from p185_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
HOST_REQUIRED=97*1024**3+1200*1024**2
def main():
 limits();rows=[]
 from common import P56,module
 gate=module('p185_memory_admission',P56/'memory_gate.py')
 plans={mode:P/'lineage'/mode/'memory-plan.json' for mode in ('production','unsplit')}
 shape=json.loads((P/'evidence/full-shape.json').read_text());assert shape['passed']
 assert shape['unsplit_memory_plan_sha256']==sha(plans['unsplit']),'unsplit plan is not the full-shape derivation'
 inherited=json.loads((LOCAL/'lineage-inputs/packet183-own/v5/evidence/admission.json').read_text())
 census={(r['selection'],r['rank']):r['device_allocation_bytes'] for r in shape['memory']}
 for mode,path in plans.items():
  ledger=json.loads(path.read_text());config=gate.configuration(ledger,4096,1,0)
  for rank in config['ranks']:
   r=rank['rank'];live=census[(mode,r)]
   assert rank['free_with_mtp_bytes']>=ledger['minimum_free_bytes']
   assert rank['arena_device_bytes']<=ledger['arena_limit_bytes']
   assert live<=rank['total_with_mtp_bytes'],'census exceeds the plan'
   rows.append(dict(mode=mode,rank=r,planned_device_bytes=rank['arena_device_bytes'],planned_arena_headroom_bytes=ledger['arena_limit_bytes']-rank['arena_device_bytes'],
    planned_free_bytes=rank['free_with_mtp_bytes'],census_device_bytes=live,census_arena_headroom_bytes=ledger['arena_limit_bytes']-live,
    census_physical_free_bytes=ledger['capacity_bytes']-live,minimum_free_bytes=ledger['minimum_free_bytes']))
 delta=shape['census_delta_bytes_per_rank']
 assert delta==[census[('unsplit',0)]-census[('production',0)],census[('unsplit',1)]-census[('production',1)]]
 assert delta[1]==46080*3380-16,'rank 1 delta is the 46,080 suffix rows minus the 16-byte p105 best16 buffer'
 assert delta[0]==-(46080*3380+46080*2+46080*32+4*4+16+5120),'rank 0 delta is the suffix rows plus the p105 auxiliary buffers'
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'admission_gate.py',*plans.values(),P/'evidence/full-shape.json',LOCAL/'lineage-inputs/packet183-own/v5/evidence/admission.json')}
 save(P/'evidence/admission.json',dict(passed=True,device_executed=False,full_shape_read=False,driver_residency_unmeasured=True,rows=rows,
  census_delta_bytes_per_rank=delta,host_required_available_bytes=HOST_REQUIRED,host_queue_start_extra_bytes=1024**3,
  host_shadow_delta_bytes=sum(delta),production_ledger_inherited_rows=inherited.get('rows'),
  note='unsplit rank-1 PLAN headroom is 1,373,494 B under the 30 GiB arena because the inherited plan keeps the unused 629,145,600 B class-layout reserve; the measured census leaves 630,519,094 B arena headroom and 2.66 GB physical free on rank 1',
  sources=sources))
 print('admission PASS: production and unsplit plans/census; delta rank0',delta[0],'rank1',delta[1])
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
