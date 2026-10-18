"""Conservative transient relocation bound; no full-shape/model payload reads.
Originals remain until a whole class is copied and drained, then all are freed.
This is a proof from existing p136/p142 shape receipts, not a new shape run.
"""
import copy
from compositions import P,ROOT,read,save,sha,all_compositions,key
BUDGET=600*1024**2
TOKEN_DEVICE=0 # p137 embedding_staging uses Memory::pinned, not the device arena.
HOST_BYTES=97*1024**3+1271398400+64*1024**2+2*BUDGET
def plan(selection):
 row=copy.deepcopy(read(P/'lineage-inputs/bundle8-memory-plan.json'))
 extra=BUDGET if 'order600' in selection.values() else 0
 for rank in row['placements']['1']['capacities']['4096']['ranks']:
  # Overbound the peak as final baseline (including draft) plus one full bank;
  # the real relocation occurs earlier, before draft construction.
  rank['target_modeled_allocations_bytes']+=extra
  rank['target_total_bytes']+=extra
  rank['total_with_mtp_bytes']+=extra
  rank['free_with_mtp_bytes']-=extra
  rank['arena_device_bytes']+=extra
  rank['arena_headroom_bytes']-=extra
  rank['allocation_margin_passed']=rank['free_with_mtp_bytes']>=row['minimum_free_bytes']
  rank['arena_margin_passed']=rank['arena_headroom_bytes']>=0
  assert rank['allocation_margin_passed'] and rank['arena_margin_passed']
 row.update(view=key(selection),scope='Conservative inherited allocation ledger plus one temporary 600 MiB bank; class originals freed before next class; driver residency unmeasured',composition=selection)
 return row
def main():
 import memory_gate
 rows=[]
 for selection in all_compositions():
  ledger=plan(selection);config=memory_gate.configuration(ledger,4096,1,0)
  rows.append(dict(selection=selection,configuration=config,maximum_transient_copy_bytes_per_rank=BUDGET if 'order600' in selection.values() else 0))
 save(P/'evidence/memory143.json',dict(passed=True,device_executed=False,full_shape_read=False,full_shape_executed=False,rows=rows,host_required_available_bytes=HOST_BYTES,scope='Analytical peak bound from preserved baseline census; no new full-shape claim',sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'memory143.py',P/'class_layout.hpp',P/'memory_gate.py',P/'lineage-inputs/bundle8-memory-plan.json')}))
if __name__=='__main__':main()
