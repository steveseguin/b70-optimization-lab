"""Inherited allocation ledger plus exact static metadata delta, no full-shape read."""
import csv,json,resource
from p184_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();csv_path=LOCAL/'lineage-inputs/capture-extents.csv'
 entries=list(csv.DictReader(csv_path.open()))
 active=[r for r in entries if int(r['candidate_copy_bytes'])]
 assert len(active)==984 and sum(int(r['candidate_copy_bytes']) for r in active)==19025640
 table_bytes=sum((int(r['candidate_copy_bytes'])+128*1024**2-1)//(128*1024**2) for r in active)*48
 assert table_bytes==47232 and table_bytes<65536
 rows=[]
 from common import P56,module
 gate=module('p153_memory_admission',P56/'memory_gate.py')
 for mode in ('production','static'):
  path=P/'lineage'/mode/'memory-plan.json';ledger=json.loads(path.read_text());config=gate.configuration(ledger,4096,1,0)
  for rank in config['ranks']:
   assert rank['free_with_mtp_bytes']>=ledger['minimum_free_bytes']
   assert rank['arena_device_bytes']<ledger['arena_limit_bytes']
   rows.append(dict(mode=mode,rank=rank['rank'],modeled_device_bytes=rank['arena_device_bytes'],arena_headroom_bytes=ledger['arena_limit_bytes']-rank['arena_device_bytes'],physical_free_bytes=rank['free_with_mtp_bytes'],minimum_free_bytes=ledger['minimum_free_bytes'],additional_table_bytes=table_bytes if rank['rank']==0 else 0,additional_reserve_bytes=65536 if rank['rank']==0 else 0))
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'admission_gate.py',csv_path,*(P/'lineage'/v/'memory-plan.json' for v in ('production','static')))}
 save(P/'evidence/admission.json',dict(passed=True,device_executed=False,full_shape_read=False,actual_new_full_shape_census=False,inherited_ledger=True,driver_residency_unmeasured=True,rows=rows,static_table_bytes=table_bytes,extent_count=984,copied_bytes=19025640,sources=sources))
 print('Static table 47232 bytes; both selections/ranks admitted from inherited ledger +64KiB reserve')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
