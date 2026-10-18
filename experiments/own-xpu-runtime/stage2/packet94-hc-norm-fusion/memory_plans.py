"""Bind real post-load censuses to unchanged 30 GiB/1.5 GB admission rules."""
import copy,gzip,json
from build_engine import P,ROOT,sha,save,limits
from bundle_selection import VIEWS
from memory_gate import check,configuration,ARENA_LIMIT_BYTES
DELTA={'production':(0,0),'hc-normfuse':(0,0),'hc-normfuse+weightcache':(442368000,442368000)}
def plan(name):
 base=json.loads((P.parent/'packet84-record-bundle/memory-plan.json').read_text())
 row=copy.deepcopy(base);row['schema']='packet94.exact-layout-memory.v1';row['placements']={'1':row['placements']['1']};row['view']=name;row['extra_weight_bytes_per_rank']=DELTA[name]
 for rank,r in enumerate(row['placements']['1']['capacities']['4096']['ranks']):
  for key in ('target_modeled_allocations_bytes','target_total_bytes','total_with_mtp_bytes','arena_device_bytes'):r[key]+=DELTA[name][rank]
  r['free_with_mtp_bytes']-=DELTA[name][rank];r['arena_headroom_bytes']-=DELTA[name][rank]
  r['allocation_margin_passed']=r['free_with_mtp_bytes']>=row['minimum_free_bytes'];r['arena_margin_passed']=r['arena_headroom_bytes']>=0
 configuration(row,4096,1,0)
 return row
def main():
 limits();shape=json.loads((P/'evidence/full-shape.json').read_text());records=[]
 for name in VIEWS:
  ledger=plan(name);save(P/'evidence'/('memory-plan-'+name+'.json'),ledger)
  for rank in (0,1):
   run=next(r for r in shape['runs'] if r['view']==name and r['rank']==rank)
   path=ROOT/run['census'];assert sha(path)==run['census_sha256'];c=json.loads(gzip.decompress(path.read_bytes()))
   prod=next(r for r in shape['runs'] if r['view']=='production' and r['rank']==rank)
   assert c['totals']['device']==prod['postload_device_bytes']+DELTA[name][rank],(name,rank,c['totals']['device'],prod['postload_device_bytes'])
   gate=check(c,ledger,rank,mtp=True,context=4096,draft_rank=1,target_split=0)
   assert c['totals']['device']==run['postload_device_bytes']
   records.append(dict(view=name,arena_headroom_bytes=ARENA_LIMIT_BYTES-c['totals']['device'],**gate))
 save(P/'evidence/full-shape-admission.json',dict(passed=True,device_executed=False,runs=records,sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('memory_plans.py','memory_gate.py','evidence/full-shape.json')}))
 print('six real post-load memory admissions PASS')
if __name__=='__main__':main()
