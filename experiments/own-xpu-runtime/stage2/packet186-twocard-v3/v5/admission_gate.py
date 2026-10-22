"""Allocation admission for the three lineages from the measured production-shape census.

`production` (bundle 8, split head) keeps packet183/153's ledger byte for byte. `u` and `v3` share one
storage (the V3 dual layout): that ledger plus the census delta measured by p186_v5_full_shape.py with the
real allocation calls. The delta is attributed allocation by allocation from the retained census archives:
rank 0 = +130 allocations of layers 24-25 (weights and buffers) - the 9 split-head suffix/p105 allocations;
rank 1 = the 46,080 suffix head rows (packet185's measured un-split delta). Host admission: bundle 8 keeps
97 GiB + 1200 MiB = 105,411,248,128 B MemAvailable at START plus the queue's 1 GiB; the V3 lineages add the
host shadow of their extra device bytes (multi-card host shadow tracks device bytes).
"""
import json,resource,tarfile
from p186_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import HOST_BASE,HOST_V3_EXTRA,CENSUS_DELTA,host_required
def census_rows(shape,load,rank):
 art=next(r['artifact'] for r in shape['runs'] if r['load']==load and r['rank']==rank)
 assert sha(ROOT/art['path'])==art['sha256'],'retained census archive changed'
 with tarfile.open(ROOT/art['path']) as t:c=json.load(t.extractfile('census.json'))
 return {x['label']:x['bytes'] for x in c['allocations'] if x['memory']=='device' and x['live']}
def main():
 limits();rows=[]
 from common import P56,module
 gate=module('p186_memory_admission',P56/'memory_gate.py')
 plans={mode:P/'lineage'/mode/'memory-plan.json' for mode in ('production','u','v3')}
 shape=json.loads((P/'evidence/full-shape.json').read_text());assert shape['passed']
 assert shape['dual_memory_plan_sha256']==sha(plans['u'])==sha(plans['v3']),'dual plan is not the full-shape derivation'
 inherited=json.loads((LOCAL/'lineage-inputs/packet183-own/v5/evidence/admission.json').read_text())
 census={(r['layout'],r['rank']):r['device_allocation_bytes'] for r in shape['memory']}
 for mode,path in plans.items():
  layout='production' if mode=='production' else 'u-first'
  ledger=json.loads(path.read_text());config=gate.configuration(ledger,4096,1,0)
  for rank in config['ranks']:
   r=rank['rank'];live=census[(layout,r)]
   assert rank['free_with_mtp_bytes']>=ledger['minimum_free_bytes']
   assert rank['arena_device_bytes']<=ledger['arena_limit_bytes']
   assert live<=rank['total_with_mtp_bytes'],'census exceeds the plan'
   rows.append(dict(mode=mode,rank=r,planned_device_bytes=rank['arena_device_bytes'],planned_arena_headroom_bytes=ledger['arena_limit_bytes']-rank['arena_device_bytes'],
    planned_free_bytes=rank['free_with_mtp_bytes'],census_device_bytes=live,census_arena_headroom_bytes=ledger['arena_limit_bytes']-live,
    census_physical_free_bytes=ledger['capacity_bytes']-live,minimum_free_bytes=ledger['minimum_free_bytes'],host_required_available_bytes=host_required(mode)))
 delta=shape['census_delta_bytes_per_rank']
 assert delta==[census[('u-first',0)]-census[('production',0)],census[('u-first',1)]-census[('production',1)]]==list(CENSUS_DELTA)
 assert delta[1]==46080*3380-16,'rank 1 delta is the 46,080 suffix rows minus the 16-byte p105 best16 buffer (packet185 un-split)'
 A,B=census_rows(shape,'u-first',0),census_rows(shape,'production',0)
 added={k:v for k,v in A.items() if k not in B};removed={k:v for k,v in B.items() if k not in A}
 assert all(('blk.24.' in k or 'blk.25.' in k) for k in added) and all(A[k]==B[k] for k in A if k in B),'rank 0 delta must be exactly the moved layers and the suffix head'
 assert all(k=='card0:weight:output.weight' or k.startswith('card0:p105:') for k in removed)
 moved=sum(added.values());suffix=sum(removed.values())
 assert suffix==46080*3380+46080*2+46080*32+4*4+16+5120 and moved-suffix==delta[0]
 assert HOST_V3_EXTRA==sum(delta) and host_required('v3')==HOST_BASE+sum(delta)
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'admission_gate.py',P/'bracket_config.py',*plans.values(),P/'evidence/full-shape.json',LOCAL/'lineage-inputs/packet183-own/v5/evidence/admission.json')}
 save(P/'evidence/admission.json',dict(passed=True,device_executed=False,full_shape_read=False,driver_residency_unmeasured=True,rows=rows,
  census_delta_bytes_per_rank=delta,rank0_moved_layer_bytes=moved,rank0_moved_layer_allocations=len(added),rank0_suffix_head_bytes_removed=suffix,
  host_required_available_bytes=dict(production=HOST_BASE,u=host_required('u'),v3=host_required('v3')),host_queue_start_extra_bytes=1024**3,
  host_shadow_delta_bytes=sum(delta),production_ledger_inherited_rows=inherited.get('rows'),
  note='dual-layout rank-1 PLAN headroom is 1,373,494 B under the 30 GiB arena (the inherited plan keeps the unused 629,145,600 B class-layout reserve; identical to packet185 un-split, which ran on device); the measured census leaves 630,519,094 B arena headroom and 2.66 GB physical free on rank 1; rank 0 keeps 1,967,205,656 B arena headroom (census) / 1,338,041,752 B (plan)',
  sources=sources))
 print('admission PASS: production, u, v3; delta rank0',delta[0],'(moved +%d, suffix -%d) rank1'%(moved,suffix),delta[1])
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
