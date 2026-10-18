"""Exactly two local sealed compositions; packet130 B is admitted by native identity."""
import json,hashlib,sys
from source_decision import O,ROOT,P,sha,save,selections,read_sources,SOURCE_RULE
sys.path.insert(0,str(P))
from bundle_selection import KEYS,name
from screen_jobs import WRAPPER

def current():
 ref=json.loads((O/'decision.json').read_text());path=ROOT/ref['path'];assert sha(path)==ref['sha256'];return path,json.loads(path.read_text())
def view(selection):
 assert selection in selections(),'unregistered packet133 selection'
 return P/'selections'/(name(*(selection[k] for k in KEYS))+'--placement-1')
def evidence_view(selection):return view(selection)
def jobs(config,lane):
 assert lane in ('A','B')
 return dict(lane=lane,path=str((P/'v5/evidence/device-v5-A') if lane=='A' else P.with_name('packet130-suffix-interleave')/'v5/evidence/device-v5-B'))
def validate(config):
 control,candidate=selections()
 assert config['control']==control and config['candidate']==candidate,'fixed composition differs'
 assert config['sources']==read_sources(),'source snapshot changed'
 assert config['source_rule']==SOURCE_RULE and config['threshold_ratio']==1.005
 assert config['composition_kind']=='bundle7+suffix-interleave'
 assert config['evidence_rule']=='identical-native-selection-both-v5-lanes-v1'
 from reuse_build import verify_native
 verify_native()
 from startup_receipt103 import verify
 verify()
 from bootstrap import install
 install()
 from common import sealed
 from types import SimpleNamespace
 for selection in (control,candidate):
  lineage=view(selection);sealed(SimpleNamespace(lineage=lineage,seal=lineage/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
def generate():
 _,config=current();validate(config)
 save(O/'inherited-evidence-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,jobs={lane:jobs(config,lane) for lane in ('A','B')},rule='Only exact same binary/selection/dispatch/memory may share p130 evidence; no inherited bundle7 speed pass'))
if __name__=='__main__':generate()
