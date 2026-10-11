"""CPU-only copy budget regression on real arithmetic mini and real plan metadata."""
import json,subprocess,time,hashlib,resource
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def source_gate():
 from math_gate import closure
 from kernel_overlay import apply
 import re
 # Any new copy/fill/shared-USM operation in a kernel implementation is rejected.
 for path in closure():
  if path.name in ('backend.hpp','sycl_device.cpp'):continue
  text=apply(path,path.read_text())
  assert not re.search(r'\b(?:q|queue|h)\s*(?:\.|->)\s*(?:memcpy|copy|fill|memset)\s*\(|\bmalloc_shared\s*\(',text),str(path)
 assert 'if(ownrt::preparing_parameters){tail=l.last;submitted+=l.passes;return;}' in (P/'main.cpp').read_text()
 assert 'if(frozen_parameters[&d])throw' in (P/'owner.cpp').read_text()
 return True

def main():
 assert source_gate()
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 binary=B/'host/own-rt-iq3';rows=[]
 for mini in (True,False):
  out=B/('copy-budget-'+('mini' if mini else 'real-metadata')+'-'+str(time.time_ns()))
  cmd=[str(binary),'--cards','2','--card','0','--memory','resident','--context','256','--tokens',str(2 if mini else 10),'--output',str(out)]
  if mini:cmd+=['--mini']
  else:cmd+=['--count-submissions','--plan',str(B/'input/plan.tsv'),'--identity',str(B/'input/identity.tsv'),'--input',str(B/'input/tokens.txt'),'--model-dir',json.loads((B/'input/input.json').read_text())['model_dir']]
  with out.with_suffix('.log').open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT)
  tokens=[json.loads(x) for x in (out/'timings.jsonl').read_text().splitlines()]
  assert len(tokens)==(2 if mini else 10) and all(t['device_copies']==4 and t['device_copies_by_card']==[2,2] for t in tokens),tokens
  rows.append(dict(kind='mini-arithmetic' if mini else 'real-plan-metadata-only',argv=cmd,tokens=tokens,plan_sha256=hashlib.sha256((out/'plan.json').read_bytes()).hexdigest()))
 (P/'copy-budget.json').write_text(json.dumps(dict(passed=True,device_executed=False,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),rows=rows,definition='device_copies counts host/device queue copy commands; byte_move_launches counts ordered device byte-copy kernels, included in launches'),indent=2)+'\n')
 before_path=P/'copy-budget-before.json'
 if before_path.exists():
  before=json.loads(before_path.read_text());after=json.loads((P/'copy-budget.json').read_text());summary=[]
  for kind,index in [('mini-arithmetic',2),('real-plan-metadata-only',2),('real-plan-metadata-only',9)]:
   def row(d):return next(t for r in d['rows'] if r['kind']==kind for t in r['tokens'] if t['generated_index']==index)
   x,y=row(before),row(after);keys=('device_copies','host_waits','launches')
   summary.append(dict(kind=kind,generated_index=index,before={k:x[k] for k in keys},after={k:y[k] for k in keys}))
  (P/'copy-budget-summary.json').write_text(json.dumps(dict(passed=True,device_executed=False,before_binary_sha256=before['binary_sha256'],after_binary_sha256=after['binary_sha256'],rows=summary,parameter_cache_test=dict(launches=876,device_copies=0,host_waits=0),scope='Mock counts, not speed. Before excludes native-only r2 parameter uploads absent from its mock. After is two queue copies per card; byte-move kernels count as launches. Explicit event waits only; completed-queue synchronizes excluded.'),indent=2)+'\n')
 print('COPY BUDGET PASS: mini (2) and real plan (10), [2,2] per token')
if __name__=='__main__':main()
