"""Exact extra draft-head bytes; inherited limits are never weakened."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
EXTRA=91392*1600
def ledger(name):
 v=json.loads((P/'memory-plan.json').read_text())
 # Screens register only this topology/capacity. Other copied recipes are not arms.
 v['placements']={'1':v['placements']['1']}
 v['placements']['1']['capacities']={'4096':v['placements']['1']['capacities']['4096']}
 if name=='q4-g32':
  r=v['placements']['1']['capacities']['4096']['ranks'][1]
  r['draft_duplicate_head_bytes']+=EXTRA
  for k in ('arena_device_bytes','total_with_mtp_bytes'):r[k]+=EXTRA
  for k in ('arena_headroom_bytes','free_with_mtp_bytes'):r[k]-=EXTRA
  r['arena_margin_passed']=r['arena_headroom_bytes']>=0
  r['allocation_margin_passed']=r['free_with_mtp_bytes']>=v['minimum_free_bytes']
 v['packet83']=dict(view=name,extra_draft_only_head_bytes=EXTRA if name=='q4-g32' else 0,target_head_unchanged=True)
 return v
