"""Derive admission from actual production-shape allocation calls, without a GPU."""
import json
from build_engine import P,ROOT,sha,save,limits
from bundle_selection import PLACEMENTS,views
from memory_gate import check,configuration,ARENA_LIMIT_BYTES

def main():
 limits();report=json.loads((P/'evidence/full-shape.json').read_text());assert report['passed']
 ledger=dict(schema='packet84.full-shape-memory.v1',capacity_bytes=34242297856,minimum_free_bytes=1500000000,
             arena_limit_bytes=ARENA_LIMIT_BYTES,placements={},source_sha256=sha(P/'evidence/full-shape.json'),
             scope='Exact mock allocation calls; driver overhead and physical residency unmeasured')
 admissions=[];censuses={}
 for placement,(dr,split,boundary) in PLACEMENTS.items():
  ranks=[]
  for rank in (0,1):
   samples=[r for r in report['runs'] if r['placement']==placement and r['rank']==rank]
   assert len(samples)==len(views())
   totals=[]
   for r in samples:
    path=ROOT/r['census'];assert sha(path)==r['census_sha256'];c=json.loads(path.read_text());censuses[r['census']]=sha(path)
    rows=[x for x in c['allocations'] if x['live'] and x['memory']=='device'];total=sum(x['bytes'] for x in rows)
    assert total==r['postload_device_bytes']==c['totals']['device']
    prefix=[x for x in rows if x['label']=='card0:draft:shared-head-host'];target_head=[x for x in rows if x['label']=='card0:weight:output.weight']
    assert not target_head if rank==0 else len(target_head)==1
    assert ([x['bytes'] for x in prefix]==[91392*3380]) if dr==rank==0 else not prefix
    draft=sum(x['bytes'] for x in rows if ':draft:' in x['label']);head=sum(x['bytes'] for x in prefix)
    totals.append((total,draft,head))
   assert len(set(totals))==1,'hc-wide changes allocation'
   total,draft,head=totals[0];reserve=(46500548,1228800)[rank];target=total-draft;free=ledger['capacity_bytes']-total-reserve
   ranks.append(dict(rank=rank,draft_rank=dr,target_layers=(boundary,48-boundary)[rank],target_modeled_allocations_bytes=target,
        allocation_reserve_bytes=reserve,draft_total_bytes=draft-head,draft_duplicate_head_bytes=head,target_total_bytes=target+reserve,
        total_with_mtp_bytes=total+reserve,free_with_mtp_bytes=free,allocation_margin_passed=free>=ledger['minimum_free_bytes'],
        arena_device_bytes=total,arena_headroom_bytes=ARENA_LIMIT_BYTES-total,arena_margin_passed=total<=ARENA_LIMIT_BYTES))
  key='0-split24' if placement=='0' else placement
  ledger['placements'][key]=dict(draft_rank=dr,layer_boundary=boundary,capacities={'4096':dict(context_capacity=4096,ranks=ranks)})
 save(P/'memory-plan.json',ledger)
 for r in report['runs']:
  value=check(json.loads((ROOT/r['census']).read_text()),ledger,r['rank'],mtp=True,context=4096,draft_rank=r['draft_rank'],target_split=r['target_split'])
  admissions.append(dict(view=r['view'],placement=r['placement'],**value))
 sources={**censuses,**{str((P/n).relative_to(ROOT)):sha(P/n) for n in ('memory_census.py','memory_gate.py','memory-plan.json','evidence/full-shape.json')}}
 save(P/'evidence/memory-admission.json',dict(passed=True,device_executed=False,admissions=admissions,sources=sources))
 print(json.dumps(ledger['placements'],indent=2))
if __name__=='__main__':main()
