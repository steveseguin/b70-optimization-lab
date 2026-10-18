"""Exact composition deltas checked against real post-load Arena censuses."""
import copy,json
from build_engine import P
from bundle_selection import name
from memory_gate import configuration
TARGET_SAVING=248320*(3380-2100)
DRAFT_PREFIX=91392*3380
EXPERT_DELTA=(301465600,314572800)
def plan(v):
 row=copy.deepcopy(json.loads((P/'base-memory-plan.json').read_text()))
 row.update(schema='packet105.exact-layout-memory.v1',view=name(*v))
 row['placements']={'1':row['placements']['1']};row['placements']['1']['capacities']={'4096':row['placements']['1']['capacities']['4096']}
 half='halfcache' in v[2];head=v[8]=='head-transpose';split=v[8].startswith('head-split-');deltas=[]
 for rank,r in enumerate(row['placements']['1']['capacities']['4096']['ranks']):
  extra=EXPERT_DELTA[rank] if half else 0;extra+=(157322272 if rank==0 else -155750384) if split else 0;target=extra-(TARGET_SAVING if head and rank==1 else 0);prefix=DRAFT_PREFIX if head and rank==1 else 0;delta=target+prefix;deltas.append(delta)
  for k in ('target_modeled_allocations_bytes','target_total_bytes'):r[k]+=target
  r['draft_duplicate_head_bytes']+=prefix
  for k in ('total_with_mtp_bytes','arena_device_bytes'):r[k]+=delta
  r['free_with_mtp_bytes']-=delta;r['arena_headroom_bytes']-=delta
  r['allocation_margin_passed']=r['free_with_mtp_bytes']>=row['minimum_free_bytes'];r['arena_margin_passed']=r['arena_headroom_bytes']>=0
 row['extra_weight_bytes_per_rank']=deltas
 configuration(row,4096,1,0)
 return row
