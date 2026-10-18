"""Bind the evidence-selected composition to a fresh record chain."""
from pathlib import Path
from compositions import P,ROOT,read,save,sha,path

def require(value,message):
 if not value:raise ValueError(message)
def check_map(root,entries):
 require(isinstance(entries,dict) and entries,'empty identity map')
 for n,h in entries.items():require(sha(Path(root)/n)==h,'sealed bytes changed: '+str(n))
def checked():
 from cpu_prepare143 import verify as cpu
 from bundle_selection import selected
 from shared_oracle import static_binding
 proof=cpu();choice=selected();view=path({k:choice[k] for k in __import__('compositions').DIMENSIONS})
 parent=read(P/'lineage-inputs/inherited-root/build-receipt.json')
 require(parent['shared_oracle']==static_binding(),'oracle differs')
 row=dict(parent);artifacts=dict(parent['artifacts_sha256'])
 for mode in ('device','gnu-host'):artifacts[mode+'/own-rt-iq3']=sha(P/'v5/build'/mode/'own-rt-iq3')
 check_map(P/'build',artifacts)
 row.update(schema='packet143.chain-cpu-seal.v1',runtime_revision=read(P/'runtime-revision.json')['runtime_revision'],sources=proof['sources'],artifacts_sha256=artifacts,original_artifacts_sha256=artifacts,bundle_selection=choice,memory_plan=read(P/'memory-plan.json'),screen_seal_sha256=sha(view/'screen-seal.json'),selection=dict(selection_sha256=sha(P/'selection.json'),choices=read(P/'selection.json')['choices']),device_admission_ready=True,scope=dict(qualification='CPU composed proof only; fresh record chain pending',memory='class originals released after drained complete-bank copy before captures; component bracket gains are estimates'))
 # Current selected config and oracle binding are explicit chain inputs.
 def canonical(value):
  if isinstance(value,list):return [canonical(x) for x in value]
  if not isinstance(value,dict):return value
  out={}
  for k,v in value.items():
   candidate=ROOT/k
   if isinstance(v,str) and len(v)==64 and candidate.is_symlink() and candidate.exists():
    resolved=candidate.resolve()
    if resolved.suffix in ('.o','.a') or resolved.read_bytes()[:4]==b'\x7fELF':k=str(resolved.relative_to(ROOT))
   out[k]=canonical(v)
  return out
 row=canonical(row)
 row['fixture_inputs_sha256']={str((P/'lineage-inputs/link-targets/build/fusion-fixtures'/n).relative_to(ROOT)):h for n,h in parent['fixture_inputs_sha256'].items()}
 row['oracle_inputs_sha256']={str((P.parent/'packet49-integrate/oracle'/n).relative_to(ROOT)):h for n,h in parent['oracle_inputs_sha256'].items()}
 row['sources']=dict(row['sources'],**{str((P/n).relative_to(ROOT)):sha(P/n) for n in ('selection.json','memory-plan.json','bundle-selection.json','runtime-revision.json','oracle-binding.json','active-composition.json','lineage-inputs/calibration/selection.json','p56_config.hpp','coverage.json','p83_head.hpp')})
 return row
def verify():
 row=read(P/'build-receipt.json');require(row==checked(),'chain selection/source binding changed');return row
def main():verify();print('chain seal PASS')
if __name__=='__main__':main()
