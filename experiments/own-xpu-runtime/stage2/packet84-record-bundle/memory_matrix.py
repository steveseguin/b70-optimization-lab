"""Admission from every real post-load allocation census; no GPU required."""
import json,gzip
from build_engine import P,ROOT,sha,save,limits
from bundle_selection import PLACEMENTS,configurations,DRAFT_HEAD
from memory_gate import check,ARENA_LIMIT_BYTES
def ledger(head):return json.loads((P/'evidence'/('memory-'+head+'.json')).read_text())
def main():
 limits();report=json.loads((P/'evidence/full-shape.json').read_text());assert report['passed']
 assert len(report['runs'])==len(configurations())*2
 sources={};admissions=[];caches={};ledgers={}
 for head in DRAFT_HEAD:
  value=dict(schema='packet84.full-shape-memory.v1',capacity_bytes=34242297856,minimum_free_bytes=1500000000,arena_limit_bytes=ARENA_LIMIT_BYTES,placements={},scope='Actual allocation calls with mock backend; physical driver residency unmeasured')
  for placement,(dr,split,boundary) in PLACEMENTS.items():
   samples=[r for r in report['runs'] if r['placement']==placement and r['draft_head']==head]
   if not samples:continue
   ranks=[]
   for rank in (0,1):
    totals=set()
    for r in samples:
     if r['rank']!=rank:continue
     path=ROOT/r['census'];assert sha(path)==r['census_sha256'];sources[r['census']]=sha(path)
     if r['census'] not in caches:caches[r['census']]=json.loads(gzip.decompress(path.read_bytes()))
     c=caches[r['census']];rows=[x for x in c['allocations'] if x['live'] and x['memory']=='device'];total=sum(x['bytes'] for x in rows)
     assert total==r['postload_device_bytes']==c['totals']['device']
     draft=sum(x['bytes'] for x in rows if ':draft:' in x['label'])
     heads=sum(x['bytes'] for x in rows if x['label'] in ('card0:draft:shared-head-host','card0:draft:q4-head'))
     assert heads==(91392*1600 if head=='q4-g32' and rank==dr else 91392*3380 if dr==rank==0 else 0)
     totals.add((total,draft,heads))
    assert len(totals)==1,'non-head choice changed allocation'
    total,draft,heads=totals.pop();reserve=(46500548,1228800)[rank];target=total-draft;free=value['capacity_bytes']-total-reserve
    ranks.append(dict(rank=rank,draft_rank=dr,target_layers=(boundary,48-boundary)[rank],target_modeled_allocations_bytes=target,allocation_reserve_bytes=reserve,draft_total_bytes=draft-heads,draft_duplicate_head_bytes=heads,target_total_bytes=target+reserve,total_with_mtp_bytes=total+reserve,free_with_mtp_bytes=free,allocation_margin_passed=free>=value['minimum_free_bytes'],arena_device_bytes=total,arena_headroom_bytes=ARENA_LIMIT_BYTES-total,arena_margin_passed=total<=ARENA_LIMIT_BYTES))
   value['placements']['0-split24' if placement=='0' else placement]=dict(draft_rank=dr,layer_boundary=boundary,capacities={'4096':dict(context_capacity=4096,ranks=ranks)})
  ledgers[head]=value;save(P/'evidence'/('memory-'+head+'.json'),value)
 for r in report['runs']:
  operation=ROOT/r['operations'];assert sha(operation)==r['operations_sha256'];sources[r['operations']]=sha(operation)
  v=check(caches[r['census']],ledgers[r['draft_head']],r['rank'],mtp=True,context=4096,draft_rank=r['draft_rank'],target_split=r['target_split'])
  admissions.append(dict(view=r['view'],placement=r['placement'],**v))
 for n in ('memory_matrix.py','memory_gate.py','evidence/full-shape.json',*('evidence/memory-'+h+'.json' for h in DRAFT_HEAD)):sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 save(P/'memory-plan.json',ledgers['production'])
 save(P/'evidence/memory-admission.json',dict(passed=True,device_executed=False,admissions=admissions,sources=sources))
 print('All',len(admissions),'per-card censuses admitted; Q4 rank1 headroom',ledgers['q4-g32']['placements']['1']['capacities']['4096']['ranks'][1]['arena_headroom_bytes'])
if __name__=='__main__':main()
