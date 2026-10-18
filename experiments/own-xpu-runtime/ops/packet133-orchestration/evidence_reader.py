"""Read and replay frozen v5 evidence in an isolated import namespace; no writes."""
import json,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3]
P=ROOT/'experiments/own-xpu-runtime/stage2/packet133-record-bundle'
V=P.with_name('packet130-suffix-interleave')/'v5'
def same_memory_layout(local,native):
 # The human-readable view label gains the scheduling dimension; every
 # allocation, capacity, topology and safety field must otherwise be identical.
 a=dict(local);b=dict(native)
 if not isinstance(a.pop('view',None),str) or not isinstance(b.pop('view',None),str) or a!=b:
  raise ValueError('chain allocation/memory policy differs from bracket')
 return True

def read(output,lane,kind):
 sys.path.insert(0,str(V))
 from common import sha,read as load,require,D
 from cpu_seal import verify
 verify()
 from compare import load as replay
 output=Path(output);result=replay(output);window=load(output/'window.json');identity=load(output/'identity.json')
 require(result['kind']==kind and identity['lane']==lane,'wrong bracket lane/kind')
 from conditions import LANES
 require(identity['conditions']==LANES[lane] and window['lane']==lane and window['conditions']==LANES[lane],'lane conditions changed')
 require(load(output/'run/device-isolation.json').get('passed') is True,'device isolation failed')
 wrapper=P/'v5' if lane=='A' else V
 require(window['wrapper_sources']=={str(f.relative_to(ROOT)):sha(f) for f in wrapper.glob('*.py')},'execution wrapper source changed')
 from bracket_config import sealed_identity
 from types import SimpleNamespace
 expected=sealed_identity(SimpleNamespace(lineage=V/'lineage',seal=None,binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 require(all(identity.get(k)==v for k,v in expected.items()),'native selection/binary/dispatch/memory identity differs')
 from bracket import load_config
 require(identity['bracket']==load_config(V/'configs'/(kind+'.json')),'bracket choices changed')
 # Require hash bindings for all replay inputs, not merely whatever keys a receipt supplied.
 needed={'identity.json','bracket-summary.json','run/teardown.json','suite-manifest.snapshot.json','run/bracket-inputs.json','run/device-isolation.json'}
 if kind=='bracket':
  for i,choice in enumerate(('control','candidate','control','candidate','control')):
   stem=f'run/views/{i:02d}-{choice}/'
   needed.update(stem+n for n in ('summary.json','incident64/receipt.json','boundary/boundary-rank0.json','boundary/boundary-rank1.json'))
 require(needed<=set(window['files']),'incomplete v5 artifact hash bindings')
 # Verify local public dimension maps to exactly the native selections in this evidence.
 sys.path.insert(0,str(P))
 from bundle_selection import views,selection
 for v,leaf in zip(views().values(),('selection.json','candidate.json')):
  require(selection(v)==load(V/'lineage'/leaf),'identical-selection rule failed')
 require(sha(P/'build/device/own-rt-iq3')==identity['binary_sha256'],'chain binary differs from bracket')
 require(sha(P/'dispatch-speed6.json')==identity['dispatch_sha256'],'chain dispatch differs from bracket')
 same_memory_layout(load(P/'memory-plan.json'),load(V/'lineage/memory-plan.json'))
 # Recheck every boundary and raw proof binding, even if a stored summary says passed.
 proof=load(output/'run/bracket-inputs.json')
 require(proof['passed'] is True and proof['kind']==kind,'incomplete native bracket proof')
 require(len(proof['views'])==(1 if kind=='smoke' else 5),'missing native views')
 descriptors=None
 for i,v in enumerate(proof['views']):
  selected=identity['bracket']['views'][i]
  require(v['index']==i and v['choice']==selected['choice'] and v['selection_sha256']==selected['selection_sha256'] and v['passed'] is True,'raw selection mismatch')
  require(v['started_utc_ns']<v['finished_utc_ns'],'invalid view interval')
  if i:require(proof['views'][i-1]['finished_utc_ns']<v['started_utc_ns'],'overlapping views')
  require(Path(v['output'])==output/'run/views'/f'{i:02d}-{v["choice"]}', 'raw output escape')
  if kind=='bracket':
   from common import summary
   from compare import checked_requests
   raw=checked_requests(summary(v['requests'],v['incident64'],'tp2'),lambda prompt:D.CHECK.token_record(D.ORACLE/'results'/prompt))
   stored=result['views'][i]
   require(raw['rate']==stored['rate'] and raw['acceptance_counts']==stored['acceptance_counts'],'raw proof/summary mismatch')
  incident_path=Path(v['output'])/'incident64/receipt.json'
  incident=load(incident_path)
  require(v['incident64']['receipt_sha256']==sha(incident_path) and incident.get('passed') is True and incident.get('exact_oracle') is True and incident.get('cached_tokens')==0,'incident64 proof failed')
  desc=[]
  for rank in (0,1):
   b=load(Path(v['output'])/'boundary'/f'boundary-rank{rank}.json')
   require(b==v['boundary'][rank] and b['passed'] is True and b['total_reset'] is True and b['allocation_ids_preserved'] is True and b['cached_tokens']==0 and b['weight_uploads_after_load']==0 and b['selection_sha256']==selected['selection_sha256'],'boundary reset/load failed')
   desc.append((b['arena_descriptors_sha256'],b['weight_descriptors_sha256']))
  if descriptors is None:descriptors=desc
  require(desc==descriptors,'arena/weights changed across bracket')
 return dict(result=result,identity=identity,evidence_path=str(output.relative_to(ROOT)),window_sha256=sha(output/'window.json'),summary_sha256=sha(output/'bracket-summary.json'),selection_sha256=sha(V/'lineage/candidate.json'))
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 print(json.dumps(read(Path(sys.argv[1]),sys.argv[2],sys.argv[3])))
