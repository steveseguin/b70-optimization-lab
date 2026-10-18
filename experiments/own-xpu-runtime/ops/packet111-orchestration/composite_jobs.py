"""Exact decision-bound control/candidate/control; temporary planning only."""
import json,hashlib,subprocess,sys,tempfile
from pathlib import Path
from source_decision import O,ROOT,P,sha,save
sys.path.insert(0,str(P))
from bundle_selection import KEYS,name
from screen_jobs import WRAPPER
QUEUE=O.parent/'lane-queue'
def current():
 ref=json.loads((O/'decision.json').read_text());path=ROOT/ref['path'];assert sha(path)==ref['sha256'];return path,json.loads(path.read_text())
def view(selection):return P/'selections'/(name(*(selection[k] for k in KEYS))+'--placement-1')
def identity(config):return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]
def jobs(config,lane):
 assert lane in ('A','B')
 return [dict(index=i,lane=lane,mode="grid",choice=label,selection=selection,out=f'p111r-{identity(config)}-composite-{lane}-{i}-{label}') for i,(label,selection) in enumerate((('control',config['control']),('candidate',config['candidate']),('control',config['control'])))]
def validate(config):
 from source_decision import decide,qualification,SOURCE_RULE
 fixed=json.loads((P/'fixed-base.json').read_text())
 assert config['control']==dict(fixed,other_fusion='production',target_head='production')
 assert config['candidate']==dict(fixed,**decide(config['sources']))
 assert config['extra_dimension_selected']==(config['candidate']!=config['control']),'identical-selection declaration differs'
 assert config['evidence_rule']=='identical-selection-v1' and config['threshold_ratio']==1.005
 assert config['source_rule']==SOURCE_RULE and config['schema']=='packet111.source-decision.v2','superseded source rule'
 for key,source in config['sources'].items():
  assert sha(ROOT/source['receipt'])==source['sha256'],'source snapshot changed'
  receipt=json.loads((ROOT/source['receipt']).read_text())
  eligible=False
  if source['status']=='complete':
   assert receipt['returncode']==0 and json.loads(receipt['stdout'])==source['result']
   eligible,ratio=qualification(source,key)
   assert source['ratio']==ratio
  for evidence in [source.get('lane_A',{}),*source.get('lane_A_brackets',[])]:
   if evidence.get('status')!='complete':continue
   assert sha(ROOT/evidence['receipt'])==evidence['sha256']
   receipt=json.loads((ROOT/evidence['receipt']).read_text());assert receipt['returncode']==0 and json.loads(receipt['stdout'])==evidence['result']
  assert source['eligible']==eligible,'source qualification differs from evidence'
 from startup_receipt103 import verify
 verify()
 from bootstrap import install
 install()
 from common import sealed
 from types import SimpleNamespace
 for selection in (config['control'],config['candidate']):
  lineage=view(selection);sealed(SimpleNamespace(lineage=lineage,seal=lineage/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
def generate():
 path,config=current();validate(config);rows=[]
 payloads={}
 for lane in ('A','B'):
  payloads[lane]=''.join(json.dumps(dict(name=j['out'],lane=lane,argv=['/usr/bin/python3','-B',str((O/'composite_screen.py').relative_to(ROOT)),'--decision',str(path),'--decision-sha256',sha(path),'--lane',lane,'--index',str(j['index']),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((WRAPPER/'fault_review.py').relative_to(ROOT))))+'\n' for j in jobs(config,lane))
 with tempfile.TemporaryDirectory(prefix='p111r-composites-') as tmp:
  for lane in ('A','B'):
   (Path(tmp)/('queue-'+lane+'.txt')).write_text(payloads[lane]);log=O/('p111r-composite-plan-'+lane+'.log')
   with log.open('w') as out:r=subprocess.run([sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane',lane,'--directory',tmp],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=240)
   assert r.returncode==0,str(log)
   rows.append(dict(lane=lane,passed=True,jobs=3,log_sha256=sha(log)))
 for lane in ('A','B'):(QUEUE/('proposed-p111r-composite-'+lane+'.txt')).write_text(payloads[lane])
 save(O/'p111r-composite-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,decision_sha256=sha(path),plans=rows))
if __name__=='__main__':generate()
