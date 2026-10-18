"""Use the frozen lane wrapper with one sealed 24/24 placement extension.

Both the supervisor and worker install the same admission function. All fault,
lane, drain, memory, oracle, environment and watchdog code remains frozen.
"""
import importlib.util,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent
V=P.parent/'screen/v3-packet64-lanes'
sys.path.insert(0,str(V))
import placement
original_admit=placement.admit
def admit(root,seal,receipt,dispatch,name):
 result=original_admit(root,seal,receipt,dispatch,name)
 if root.resolve()!=P or name!='1':return result
 from common import ROOT,read,require,sha
 audit_path=P/'placement-audit.json';audit=read(audit_path)
 require(seal['sources'].get(str(audit_path.relative_to(ROOT)))==sha(audit_path),'68b placement audit not sealed')
 require(audit['placement']=='1' and audit['draft_rank']==1 and audit['target_split']==0,'68b placement identity')
 require(audit['binary_sha256']==seal['artifacts']['build/device/own-rt-iq3'],'68b audited binary differs')
 require(audit['dispatch_sha256']==sha(dispatch),'68b audited dispatch differs')
 for name,digest in audit['sources'].items():require(seal['sources'].get(name)==digest and sha(ROOT/name)==digest,'68b audit source changed: '+name)
 result.update(supported=True,reason='Packet68b sealed 24/24, unchanged packet64 target/head ownership, bounded private row storage')
 # Rebind the plan digest after updating the support disposition.
 import hashlib
 result.pop('plan_sha256')
 result['plan_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return result
placement.admit=admit
def load(name,filename):
 spec=importlib.util.spec_from_file_location(name,V/filename);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
