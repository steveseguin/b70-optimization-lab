"""Static per-rank admission from pinned parent ledger plus conservative reserves.

No GGUF/full-shape/model reads. Actual device census remains a launch-time gate.
"""
import json,resource
from p151_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from common import module,P56

def main():
 limits();parent=LOCAL/'lineage-inputs/packet136-history/memory-plan.json'
 base=json.loads(parent.read_text());gate=module('p151_admission_memory',P56/'memory_gate.py')
 baseline=gate.configuration(base,4096,1,0)['ranks'];rows=[];paths=[parent,P/'admission_gate.py',P56/'memory_gate.py',P/'native/sibling.hpp']
 for variant in ('off','sibling'):
  path=P/'lineage'/variant/'memory-plan.json';paths.append(path)
  plan=json.loads(path.read_text());current=gate.configuration(plan,4096,1,0)['ranks']
  assert plan['packet151_sibling_reservation_bytes']==[256*1024**2,0]
  for rank,r in enumerate(current):
   # Both views retain the same allocation layout during the one-load bracket.
   additional=plan['class_layout_max_extra_per_rank']+plan['packet151_sibling_reservation_bytes'][rank]
   assert r['target_modeled_allocations_bytes']==baseline[rank]['target_modeled_allocations_bytes']+additional
   owned=gate.arena_bytes(r);assert owned<gate.ARENA_LIMIT_BYTES
   free=plan['capacity_bytes']-r['total_with_mtp_bytes'];assert free>=plan['minimum_free_bytes']
   rows.append(dict(variant=variant,rank=rank,parent_arena_bytes=gate.arena_bytes(baseline[rank]),added_bound_bytes=additional,planned_maximum_bytes=owned,arena_headroom_bytes=gate.ARENA_LIMIT_BYTES-owned,planned_physical_free_bytes=free,minimum_free_bytes=plan['minimum_free_bytes']))
 assert 'bytes<=256ull*1024*1024' in (P/'native/sibling.hpp').read_text()
 save(P/'evidence/admission.json',dict(passed=True,device_executed=False,static_upper_bound=True,actual_new_runtime_census_pending=True,rows=rows,sibling_bound_bytes=256*1024**2,sources={str(f.relative_to(ROOT)):sha(f) for f in paths}))
 print('Static rank admission PASS; sibling reserve 256 MiB; live census still required')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
