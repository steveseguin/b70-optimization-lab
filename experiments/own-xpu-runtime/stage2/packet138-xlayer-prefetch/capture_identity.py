"""Packet-local diagnostic identity; reuse shared admission without parent reseals."""
import json,sys
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
WRAPPER=P.parent/'screen/v4-lanes'
sys.path.insert(0,str(WRAPPER))
from common import read,require,sha,verify_map
from shared_oracle import completed_binding
from cpu_seal import verify as verify_wrapper

def verify():
 verify_wrapper();completed_binding()
 row=read(P/'packet-seal.json')
 require(row.get('passed') is True and row.get('device_executed') is False,'CPU preparation seal required')
 verify_map(ROOT,row['sources'])
 verify_map(P,row['artifacts'])
 require(row['wrapper_seal_sha256']==sha(WRAPPER/'wrapper-seal.json'),'shared wrapper changed')
 require(read(P/'selection.json')['choices']['head']=='production','production target head required')
 return row

def memory():
 import importlib.util
 spec=importlib.util.spec_from_file_location('p138_memory_gate',P/'memory_gate.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 ledger=read(P/'memory-plan.json');config=module.configuration(ledger,4096,1,0)
 require(ledger['capture_bytes_per_rank']==30809088,'capture memory not admitted')
 require([r['target_layers'] for r in config['ranks']]==[24,24],'capture split must be 24/24')
 return module,config

def sealed(args):
 verify();_,config=memory()
 require(Path(args.lineage).resolve()==P and args.profile=='tp2' and args.placement=='1'
         and args.timing=='token','fixed capture identity required')
 binary=P/'build/device/own-rt-iq3';dispatch=P/'dispatch-speed6.json';seal=P/'packet-seal.json'
 for name,path in [('binary',binary),('dispatch',dispatch),('seal',seal)]:
  require(getattr(args,name,None) is None or Path(getattr(args,name)).resolve()==path,'foreign '+name)
 return dict(lineage=str(P),seal=str(seal),seal_sha256=sha(seal),binary=str(binary),
  binary_sha256=sha(binary),dispatch=str(dispatch),dispatch_sha256=sha(dispatch),
  selection_sha256=sha(P/'selection.json'),memory_plan_sha256=sha(P/'memory-plan.json'),
  suite_sha256=sha(P/'suite.snapshot.json'),timing='token',profile='tp2',
  placement=dict(name='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],
   supported=True,reason='bounded route diagnostic; full-state dumps disabled; model exactness required',
   memory_admitted=True,configuration=config),diagnostic_only=True)

def verify_identity(identity):
 from types import SimpleNamespace
 expected=sealed(SimpleNamespace(lineage=P,profile='tp2',placement='1',timing='token'))
 require(all(identity.get(k)==v for k,v in expected.items()),'capture identity changed')
 require(identity.get('lane')=='B','capture lane must be B')
 return expected['placement'],memory()[0]
