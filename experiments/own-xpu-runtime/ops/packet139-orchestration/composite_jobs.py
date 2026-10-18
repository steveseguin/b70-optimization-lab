"""One record selection; upstream lane B supplies the sole bracket."""
import json,sys
from source_decision import O,ROOT,P,sha,save,selections,read_sources,SOURCE_RULE
sys.path.insert(0,str(P))
from bundle_selection import KEYS,name
from screen_jobs import WRAPPER
def current():
 ref=json.loads((O/'decision.json').read_text());path=ROOT/ref['path'];assert sha(path)==ref['sha256'];return path,json.loads(path.read_text())
def view(selection):
 assert selection==selections()[1],'only bundle9 candidate may run locally'
 return P/'selections/bundle9-token-both--placement-1'
def evidence_view(selection):return view(selection)
def validate(config):
 assert (config['control'],config['candidate'])==selections()
 assert config['sources']==read_sources() and config['source_rule']==SOURCE_RULE
 assert config['threshold_ratio']==1.005 and config['max_control_drift_percent']==1.0 and config['evidence_rule']=='review26-B-v5-plus-A-smoke'
 from reuse_build import verify_native
 verify_native()
 from startup_receipt103 import verify
 verify()
 from bootstrap import install
 install()
 from common import sealed
 from types import SimpleNamespace
 lineage=view(config['candidate']);sealed(SimpleNamespace(lineage=lineage,seal=lineage/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
def jobs(config,lane):
 assert lane=='B';return dict(lane=lane,path=str(P.with_name('packet137-token-input')/'v5/evidence/device-v5-B'))
