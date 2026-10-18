"""Revalidate source device receipts; stored verdicts do not qualify bundle9."""
import json,sys,subprocess
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet139-record-bundle';N=P.with_name('packet137-token-input')
def read(output,lane,kind):
 assert (lane,kind) in (('A','smoke'),('B','bracket'))
 if lane=='A':
  sys.path.insert(0,str(P))
  from confirm136 import output as registered,view
  assert Path(output)==registered(-1),'unregistered smoke path'
  from smoke_validation import require_smoke
  result=require_smoke(lineage=view('candidate'),root=registered(-1),lane='A')
  from build_engine import sha
  root=registered(-1);window=json.loads((root/'window.json').read_text());summary=json.loads((root/'summary.json').read_text())
  for leaf in ('run/report-inputs.json','run/device-isolation.json'):
   assert window['files'].get(leaf)==sha(root/leaf),'unbound smoke artifact: '+leaf
  proof=json.loads((root/'run/report-inputs.json').read_text());isolation=json.loads((root/'run/device-isolation.json').read_text())
  assert proof['passed'] is True and isolation['passed'] is True and isolation==proof['device_isolation']==summary['device_isolation']
  assert len(proof['requests'])==len(summary['requests'])==12
  for a,b in zip(proof['requests'],summary['requests']):
   assert all(a[k]==b[k] for k in ('tokens','prompt_id','cached_tokens','repeat','passed','exact_oracle')),'smoke report differs'
  return dict(result=dict(passed=True,kind='smoke',request_count=12,max_new=64),selection_sha256=sha(P/'selection.json'),window_sha256=result['window_sha256'],evidence_path=result['path'])
 assert Path(output)==N/'v5/evidence/device-v5-B','unregistered bracket path'
 sys.path.insert(0,str(N/'v5'))
 from compare import load
 from common import read as read_json,sha,verify_map,ROOT as repo
 from cpu_seal import verify
 sealed=verify()
 result=load(output);output=Path(output)
 identity=read_json(output/'identity.json');window=read_json(output/'window.json')
 assert identity['lane']=='B' and identity['binary_sha256']==sha(P/'build/device/own-rt-iq3')==sealed['binary_sha256'],'bracket engine/lane differs'
 assert identity['dispatch_sha256']==sha(P/'dispatch-speed6.json'),'dispatch differs'
 assert read_json(P/'memory-plan.json')==read_json(N/'v5/lineage/memory-plan.json'),'memory layout differs'
 assert read_json(P/'selection.json')==read_json(N/'v5/lineage/candidate.json'),'composed selection differs'
 required=('identity.json','suite-manifest.snapshot.json','run/bracket-inputs.json','run/teardown.json','run/device-isolation.json','bracket-summary.json')
 for leaf in required:assert window['files'].get(leaf)==sha(output/leaf),'unbound bracket artifact '+leaf
 assert read_json(output/'run/device-isolation.json')['passed'] is True
 proof=read_json(output/'run/bracket-inputs.json')
 assert proof['passed'] is True and proof['kind']=='bracket' and len(proof['views'])==5
 descriptors=None
 for i,(raw,row,bound) in enumerate(zip(proof['views'],result['views'],identity['bracket']['views'])):
  expected=N/'v5/lineage'/('candidate.json' if i%2 else 'selection.json')
  assert bound['selection_sha256']==sha(expected)==raw['selection_sha256']
  assert raw['index']==row['index']==i and raw['choice']==row['choice']==('candidate' if i%2 else 'control')
  assert raw['passed'] is True and raw['started_utc_ns']<raw['finished_utc_ns']
  if i:assert proof['views'][i-1]['finished_utc_ns']<raw['started_utc_ns'],'overlapping views'
  dest=output/'run/views'/f'{i:02d}-{raw["choice"]}'
  assert raw['output']==str(dest)
  summary=read_json(dest/'summary.json')
  assert len(raw['requests'])==len(summary['requests'])==12
  for a,b in zip(raw['requests'],summary['requests']):
   assert all(a[k]==b[k] for k in ('tokens','token_timestamps','prompt_id','cached_tokens','hits','guesses','passed','exact_oracle')),'raw request proof differs'
  current_descriptors=[]
  for rank in (0,1):
   boundary=read_json(dest/'boundary'/f'boundary-rank{rank}.json')
   assert boundary==raw['boundary'][rank] and boundary['passed'] is True and boundary['total_reset'] is True
   assert boundary['cached_tokens']==0 and boundary['weight_uploads_after_load']==0 and boundary['selection_sha256']==sha(expected) and boundary['allocation_ids_preserved'] is True
   current_descriptors.append((boundary['arena_descriptors_sha256'],boundary['weight_descriptors_sha256']))
  if descriptors is None:descriptors=current_descriptors
  assert current_descriptors==descriptors,'arena/weight descriptors changed'
  for leaf in ('summary.json','incident64/receipt.json','boundary/boundary-rank0.json','boundary/boundary-rank1.json'):
   path=dest/leaf;assert window['files'].get(str(path.relative_to(output)))==sha(path),'missing view hash: '+leaf
 return dict(result=result,selection_sha256=sha(P/'selection.json'),window_sha256=sha(output/'window.json'),summary_sha256=sha(output/'bracket-summary.json'),evidence_path=str(output),wrapper_sha256=sha(N/'v5/placement-validation/wrapper-seal.json'))
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 try:print(json.dumps(read(Path(sys.argv[1]),sys.argv[2],sys.argv[3])))
 except (AssertionError,ValueError,OSError,KeyError,TypeError) as error:raise SystemExit('REFUSED: '+(str(error) or type(error).__name__))
