"""BASE reads the original bundle7 bracket; no duplicate device jobs or live queues."""
import json,hashlib,sys
from source_decision import O,ROOT,P,sha,save,parent_decision
sys.path.insert(0,str(P))
from bundle_selection import KEYS,name
from screen_jobs import WRAPPER

def current():
 ref=json.loads((O/'decision.json').read_text());path=ROOT/ref['path'];assert sha(path)==ref['sha256'];return path,json.loads(path.read_text())
def view(selection):
 from source_decision import selections,control_view
 control,candidate=selections()
 if selection==control:return control_view()
 assert selection==candidate,'unregistered packet124 selection'
 return P/'selections'/(name(*(selection[k] for k in KEYS))+'--placement-1')
def evidence_view(selection):
 from source_decision import selections,parent_candidate_view
 return parent_candidate_view() if selection==selections()[1] else view(selection)
def identity(config):return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]
def jobs(config,lane):
 assert lane in ('A','B')
 # Snapshot original decision, never read packet118's mutable decision pointer.
 source=parent_decision()
 assert config['control']==source['control'] and config['candidate']==source['candidate'],'BASE evidence may only authorize identical selections'
 return [dict(index=i,lane=lane,mode='grid',choice=label,selection=selection,out=f'p118-{identity(source)}-composite-{lane}-{i}-{label}') for i,(label,selection) in enumerate((('control',source['control']),('candidate',source['candidate']),('control',source['control'])))]
def validate(config):
 from source_decision import selections,read_sources,control_view,SOURCE_RULE,parent_candidate_view
 control,candidate=selections()
 assert config['control']==control and config['candidate']==candidate,'fixed composition differs'
 assert config['sources']==read_sources(),'source snapshot changed'
 assert config['composition_kind']=='bundle7-identical'
 assert config['evidence_rule']=='bundle7-identical-selection-v1' and config['threshold_ratio']==1.01
 assert config['source_rule']==SOURCE_RULE and config['schema']=='packet124.source-decision.v1'
 assert config['control_lineage']==str(control_view().relative_to(ROOT))
 assert config['control_seal_sha256']==sha(control_view()/'screen-seal.json')
 assert config['inherited_composite_decision_sha256']==sha(O/'inputs/bundle7-decision.json')
 from startup_receipt103 import verify
 verify()
 from bootstrap import install
 install()
 from common import sealed
 from types import SimpleNamespace
 for selection in (config['control'],config['candidate']):
  lineage=view(selection);sealed(SimpleNamespace(lineage=lineage,seal=lineage/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 local=view(candidate);parent=parent_candidate_view()
 for leaf in ('selection.json','memory-plan.json'):
  assert sha(local/leaf)==sha(O/'inputs'/('bundle7-'+leaf))==sha(parent/leaf),'bundle7 bytes differ: '+leaf
 for leaf in ('dispatch-speed6.json','build/device/own-rt-iq3','build/gnu-host/own-rt-iq3'):
  assert sha(local/leaf)==sha(parent/leaf),'bundle7 native identity differs: '+leaf

def generate():
 _,config=current();validate(config)
 save(O/'inherited-evidence-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,
     new_jobs=0,source_decision_sha256=sha(O/'inputs/bundle7-decision.json'),jobs={lane:jobs(config,lane) for lane in ('A','B')}))
if __name__=='__main__':generate()
