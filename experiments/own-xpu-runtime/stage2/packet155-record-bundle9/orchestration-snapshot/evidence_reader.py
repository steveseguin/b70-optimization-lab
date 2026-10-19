"""Replay original v4 receipts; stored verdicts never substitute for source evidence."""
import json,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3]
P=ROOT/'experiments/own-xpu-runtime/stage2/packet155-record-bundle9'
N=P.with_name('packet131b-snapshot-banks')
def same_memory_layout(local,native):
 a=dict(local);b=dict(native)
 if not isinstance(a.pop('view',None),str) or not isinstance(b.pop('view',None),str) or a!=b:
  raise ValueError('chain allocation/memory policy differs from bracket')
 return True
def read(output,lane,kind):
 assert lane in ('A','B') and kind in ('smoke','bracket')
 packet=P if lane=='A' else N
 assert Path(output)==packet,'unregistered evidence packet'
 sys.path.insert(0,str(packet))
 if lane=='A':
  from confirm136 import output as path,view,ORDER
  from compare136 import load
 else:
  from run131 import output as path,view,ORDER
  from compare131 import load
 from common import read as read_json,sha,require,D,summary
 sys.path.insert(0,str(P))
 import importlib.util
 spec=importlib.util.spec_from_file_location('p136_choices',P/'bundle_selection.py')
 choices=importlib.util.module_from_spec(spec);spec.loader.exec_module(choices)
 for values,label in zip(choices.views().values(),('control','candidate')):
  require(choices.selection(values)==read_json(view(label)/'selection.json'),'identical-selection rule failed')
  require(sha(P/'build/device/own-rt-iq3')==sha(view(label)/'build/device/own-rt-iq3'),'chain binary differs')
  require(sha(P/'dispatch-speed6.json')==sha(view(label)/'dispatch-speed6.json'),'chain dispatch differs')
  same_memory_layout(read_json(P/'memory-plan.json'),read_json(view(label)/'memory-plan.json'))
 selection_sha=sha(view('candidate')/'selection.json')
 if kind=='smoke':
  assert lane=='A','only composed local smoke qualifies'
  if not (path(-1)/'window.json').is_file():raise ValueError('pending A composed 12x64 smoke')
  from smoke_validation import require_smoke
  result=require_smoke(lineage=view('candidate'),root=path(-1),lane='A')
  return dict(result=dict(passed=True,kind='smoke',request_count=12,max_new=64),selection_sha256=selection_sha,window_sha256=result['window_sha256'],evidence_path=result['path'])
 rows=[];bindings={}
 for i,choice in enumerate(ORDER):
  root=path(i)
  if not (root/'window.json').is_file():raise ValueError('pending '+lane+' grid '+str(i)+': '+str(root))
  row=load(dict(lane=lane,index=i,choice=choice));window=read_json(root/'window.json')
  require(window.get('device_complete') is True,'device completion missing')
  required=('run/report-inputs.json','run/teardown.json','run/device-isolation.json','run/summary.json','identity.json','suite-manifest.snapshot.json','run/incident64/receipt.json')
  for leaf in required:
   require(window['files'].get(leaf)==sha(root/leaf),'artifact hash missing/changed: '+leaf)
   bindings[str((root/leaf).relative_to(ROOT))]=sha(root/leaf)
  proof=read_json(root/'run/report-inputs.json')
  require(proof['passed'] is True and proof['lane']==lane and proof['timing']=='token','raw proof differs')
  require(read_json(root/'run/teardown.json').get('drained') is True,'teardown did not drain')
  require(read_json(root/'run/device-isolation.json').get('passed') is True,'device isolation failed')
  from compare136 import checked_requests
  raw=checked_requests(summary(proof['requests'],proof['incident64'],'tp2'),lambda prompt:D.CHECK.token_record(D.ORACLE/'results'/prompt))
  require(raw['rate']==row['rate'] and raw['acceptance_counts']==row['acceptance_counts'],'raw proof/summary mismatch')
  rows.append(row)
 require(len({r['boot_id'] for r in rows})==1,'same-boot grid required')
 require(all(a['finished_utc_ns']<b['started_utc_ns'] for a,b in zip(rows,rows[1:])),'fresh windows overlap or order changed')
 return dict(result=dict(passed=True,kind='bracket',model_lifetimes=5,views=rows),selection_sha256=selection_sha,evidence_path=str(packet.relative_to(ROOT)),window_sha256=[r['window_sha256'] for r in rows],summary_sha256=bindings)
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 try:print(json.dumps(read(Path(sys.argv[1]),sys.argv[2],sys.argv[3])))
 except (AssertionError,ValueError,KeyError,OSError,TypeError) as error:
  raise SystemExit('REFUSED: '+(str(error) or type(error).__name__))
