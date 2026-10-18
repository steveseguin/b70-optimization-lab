"""Exact preflight ledger from retained full-shape allocation calls.
The independent post-build full_shape gate must reproduce each total exactly.
"""
import json,gzip
from build_engine import P,ROOT,sha
from memory_gate import configuration,ARENA_LIMIT_BYTES

def plan(v):
 assert v[14]=='80128' and v[13]=='split' and v[2]=='wide64+halfcache'
 report=json.loads((P/'evidence/census-first.json').read_text())
 ledger=dict(schema='packet120.full-shape-memory.v1',capacity_bytes=34242297856,minimum_free_bytes=1500000000,arena_limit_bytes=ARENA_LIMIT_BYTES,placements={},scope='CPU allocation census; external runtime pools and driver residency await device receipt')
 for placement,boundary in [('1',24),('25-23',25)]:
  ranks=[]
  for rank in (0,1):
   row=next(r for r in report['rows'] if r['placement']==placement and r['rank']==rank)
   path=ROOT/row['census'];assert sha(path)==row['sha256']
   census=json.loads(gzip.decompress(path.read_bytes()));live=[r for r in census['allocations'] if r['live'] and r['memory']=='device']
   total=sum(r['bytes'] for r in live);assert total==row['device_bytes']==census['totals']['device']
   draft=sum(r['bytes'] for r in live if ':draft:' in r['label']);target=total-draft;reserve=(46500548,1228800)[rank];free=ledger['capacity_bytes']-total-reserve
   ranks.append(dict(rank=rank,draft_rank=1,target_layers=(boundary,48-boundary)[rank],target_modeled_allocations_bytes=target,allocation_reserve_bytes=reserve,draft_total_bytes=draft,draft_duplicate_head_bytes=0,target_total_bytes=target+reserve,total_with_mtp_bytes=total+reserve,free_with_mtp_bytes=free,allocation_margin_passed=free>=ledger['minimum_free_bytes'],arena_device_bytes=total,arena_headroom_bytes=ARENA_LIMIT_BYTES-total,arena_margin_passed=total<=ARENA_LIMIT_BYTES))
  ledger['placements'][placement]=dict(draft_rank=1,layer_boundary=boundary,capacities={'4096':dict(context_capacity=4096,ranks=ranks)})
  configuration(ledger,4096,1,0 if placement=='1' else 25)
 return ledger
