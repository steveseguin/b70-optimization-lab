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
def view(selection):
 from source_decision import selections,control_view
 control,candidate=selections()
 if selection==control:return control_view()
 assert selection==candidate,'unregistered packet118 selection'
 return P/'selections'/(name(*(selection[k] for k in KEYS))+'--placement-1')
def identity(config):return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]
def jobs(config,lane):
 assert lane in ('A','B')
 return [dict(index=i,lane=lane,mode="grid",choice=label,selection=selection,out=f'p118-{identity(config)}-composite-{lane}-{i}-{label}') for i,(label,selection) in enumerate((('control',config['control']),('candidate',config['candidate']),('control',config['control'])))]
def validate(config):
 from source_decision import selections,read_sources,control_view,SOURCE_RULE
 control,candidate=selections()
 assert config['control']==control and config['candidate']==candidate,'fixed composition differs'
 assert config['sources']==read_sources(),'source snapshot changed'
 assert config['extra_dimension_selected']==(config['candidate']!=config['control']),'identical-selection declaration differs'
 assert config['evidence_rule']=='identical-selection-v1' and config['threshold_ratio']==1.01
 assert config['source_rule']==SOURCE_RULE and config['schema']=='packet118.source-decision.v1'
 assert config['control_lineage']==str(control_view().relative_to(ROOT))
 assert config['control_seal_sha256']==sha(control_view()/'screen-seal.json')
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
 with tempfile.TemporaryDirectory(prefix='p118-composites-') as tmp:
  for lane in ('A','B'):
   (Path(tmp)/('queue-'+lane+'.txt')).write_text(payloads[lane]);log=O/('p118-composite-plan-'+lane+'.log')
   with log.open('w') as out:r=subprocess.run([sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane',lane,'--directory',tmp],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=240)
   assert r.returncode==0,str(log)
   rows.append(dict(lane=lane,passed=True,jobs=3,log_sha256=sha(log)))
 for lane in ('A','B'):(QUEUE/('proposed-p118-composite-'+lane+'.txt')).write_text(payloads[lane])
 save(O/'p118-composite-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,decision_sha256=sha(path),plans=rows))
if __name__=='__main__':generate()
