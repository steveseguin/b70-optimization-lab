"""Execute real native full-shape startup/capture against a CPU-only backend."""
import hashlib,json,subprocess,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent.parent
ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def launch(identity):
 receipt=P/'evidence/fullshape.json';gate=json.loads(receipt.read_text())
 if not gate['passed'] or gate['device_executed']:raise ValueError('CPU startup gate missing')
 for name,digest in gate['sources'].items():
  if sha(ROOT/name)!=digest:raise ValueError('startup source changed: '+name)
 binary=P/'build/fullshape/test'
 if sha(binary)!=gate['binary_sha256']:raise ValueError('startup mock binary changed')
 view=Path(identity['lineage']);selection=view/'selection.json';dispatch=Path(identity['dispatch'])
 depth=json.loads(Path(identity['seal']).read_text()).get('depth2_kernels','serial') if view==P else 'off'
 from placement import admission_gate
 memory=admission_gate(view)[1];ledger=json.loads((view/'memory-plan.json').read_text())
 with tempfile.TemporaryDirectory(prefix='packet71c-startup-') as d:
  output=Path(d)/'run'
  cmd=[str(binary),str(P),str(output),str(selection),str(dispatch),depth]
  r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90)
  if r.returncode:raise ValueError('native startup refused: '+r.stdout+r.stderr)
  ranks=[]
  for rank in (0,1):
   result=json.loads((output/f'rank{rank}/result.json').read_text())
   census=json.loads((output/f'rank{rank}/census.json').read_text())
   admission=memory.check(census,ledger,rank,mtp=True,context=4096,draft_rank=1,target_split=0)
   ranks.append(dict(result=result,admission=admission))
 return dict(passed=True,device_executed=False,model_executed=False,depth2_kernels=depth,
             receipt_sha256=sha(receipt),binary_sha256=sha(binary),dispatch_sha256=sha(dispatch),
             selection_sha256=sha(selection),ranks=ranks)
