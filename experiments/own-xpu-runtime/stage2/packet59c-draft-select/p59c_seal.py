#!/usr/bin/env python3
"""Seal default once; fast-reseal new immutable lineages using the same binary."""
import argparse,hashlib,json,os,shutil,sys,time
from pathlib import Path
import build
from p59c_cpu_gate import constraints,pair
from p59c_selection import P,sha,save,read
ROOT=P.parents[3];B=P/'build'
def checked():
 sources=build.compiled_sources();artifacts={}
 for mode in ('gnu-host','device'):
  receipt=P/('build-'+mode+'-receipt.json');row=json.loads(receipt.read_text())
  assert row['passed'] and row['device_executed'] is False
  assert row['compiled_sources_sha256']==build.compiled_sources(),'stale '+mode+' build'
  for name,digest in row['checked_mirror_sha256'].items():assert sha(B/name)==digest,'compiler mirror changed'
  assert sha(B/mode/'compile_commands.json')==row['compile_commands_sha256']
  for name,digest in row['link_files_sha256'].items():assert sha(B/name)==digest
  for name,digest in row['artifacts_sha256'].items():
   assert sha(B/name)==digest;artifacts['build/'+name]=digest
  sources[str(receipt.relative_to(ROOT))]=sha(receipt)
 gate=json.loads((P/'cpu-gates.json').read_text())
 assert gate['passed'] and not gate['device_executed'] and gate['sources']==build.compiled_sources()
 for name,digest in gate['gate_sources'].items():assert sha(P/name)==digest,'gate source changed'
 for name,digest in gate['choice_sets'].items():
  dest=P/'cpu-evidence'/name
  assert sha(dest/'receipt.json')==digest
  row=json.loads((dest/'receipt.json').read_text());assert row['passed'] and not row['device_executed']
  for key in ('expected','actual'):assert sha(P/row[key]['path'])==row[key]['sha256']
  assert row['expected']['sha256']==row['actual']['sha256']
  assert all(r['binary_sha256']==artifacts['build/gnu-host/own-rt-iq3'] for r in row['runs'])
  for f in dest.iterdir():
   if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 for suffix in ('a','b'):assert sha(P/'cpu-evidence'/('production-'+suffix+'.bin'))==gate['production_fixture_sha256']
 assert sha(B/'p59-fixture')==gate['fixture_binary_sha256'];artifacts['build/p59-fixture']=sha(B/'p59-fixture')
 assert sha(P/gate['parent_fixture']['path'])==gate['parent_fixture']['sha256']
 operators=json.loads((P/'operator-gates.json').read_text())
 assert operators['passed'] and not operators['device_executed'] and operators['compiled_sources']==build.compiled_sources()
 for name,digest in operators['sources'].items():assert sha(P/name)==digest
 for name,row in operators['rows'].items():
  binary=B/'p59c-route-fixture' if name=='route' else B/'gnu-host/p49-qsa-fixtures'
  assert sha(binary)==row['binary_sha256'];artifacts[str(binary.relative_to(P))]=sha(binary)
  for suffix in ('a','b'):assert sha(P/'cpu-evidence/operators'/(name+'-'+suffix)/'output.bin')==row['output_sha256']
 assert sha(B/'p59c-dense-fixture')==operators['dense_binary_sha256'];artifacts['build/p59c-dense-fixture']=sha(B/'p59c-dense-fixture')
 for suffix in ('a','b'):assert sha(P/'cpu-evidence/operators'/('dense-'+suffix+'.bin'))==operators['dense_output_sha256']
 tests=json.loads((P/'selection-tests.json').read_text());assert tests['passed'] and not tests['device_executed'] and tests['tests']>0
 assert tests['binary_sha256']==operators['rows']['route']['binary_sha256'],'stale parser tests'
 for name,digest in tests['sources'].items():assert sha(P/name)==digest
 for f in (P/'cpu-evidence/operators').rglob('*'):
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 for name in ('cpu-gates.json','operator-gates.json','selection-tests.json','selection-decision.json','parent-source-manifest.json','build.py','pipeline.py','storage.py','suite_metrics.py','p59c_seal.py','p59c_cpu_gate.py','p59c_operator_gate.py','p59c_selection.py','test_selection.py','p59c_route_fixture.cpp','p59_fixture.cpp','p59c_dense_fixture.cpp'):
  sources[str((P/name).relative_to(ROOT))]=sha(P/name)
 for name in ('parent.json','packet59.json','production-a.bin','production-b.bin'):
  f=P/'cpu-evidence'/name;sources[str(f.relative_to(ROOT))]=sha(f)
 return sources,artifacts,gate

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--fast-reseal',action='store_true');ap.add_argument('--selection',type=Path);ap.add_argument('--output',type=Path);ap.add_argument('--verify',action='store_true');a=ap.parse_args();constraints();start=time.monotonic()
 if a.verify:
  sys.path.insert(0,str(P.parent/'screen'));from common import sealed
  root=(a.output or P).resolve();sealed(argparse.Namespace(lineage=root,profile='tp2',seal=None,binary=None,dispatch=None))
  print(json.dumps({'passed':True,'device_executed':False,'elapsed_seconds':time.monotonic()-start}));return
 sources,artifacts,gate=checked()
 if a.fast_reseal:
  assert a.selection and a.output,'fast reseal requires --selection and a new --output'
  root=a.output.resolve();assert root.is_relative_to(P/'selected') and not root.exists(),'new packet-local selected/ lineage required'
  config=read(a.selection)
 else:
  assert a.output is None and a.selection is None,'initial seal uses production default'
  root=P;config=read(P/'selection.json');assert all(v=='production' for v in config['draft'].values())
 assert not (root/'build-receipt.json').exists(),'never overwrite a sealed lineage'
 matched=None
 for name in gate['choice_sets']:
  row=json.loads((P/'cpu-evidence'/name/'receipt.json').read_text())
  if row['selection']==config:matched=row;break
 if matched is None:
  # Arbitrary valid combinations also get two fresh tiny runs, without a rebuild.
  tag=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
  dest=P/'cpu-evidence'/('combination-'+tag)
  if dest.exists():
   matched=json.loads((dest/'receipt.json').read_text());assert matched['selection']==config and matched['passed']
   assert all(r['binary_sha256']==artifacts['build/gnu-host/own-rt-iq3'] for r in matched['runs'])
  else:matched=pair(config,dest,json.loads((P/gate['parent_fixture']['path']).read_text())['target'])
 for key in ('expected','actual'):assert sha(P/matched[key]['path'])==matched[key]['sha256']
 assert matched['expected']['sha256']==matched['actual']['sha256']
 if root!=P:
  root.mkdir(parents=True)
  for name in artifacts:
   target=root/name;target.parent.mkdir(parents=True,exist_ok=True);os.link(P/name,target)
  save(root/'selection.json',config)
  for name in ('dispatch-speed6.json','memory-plan.json','selection-decision.json'):shutil.copyfile(P/name,root/name)
 for name in ('dispatch-speed6.json','memory-plan.json','selection-decision.json','selection.json'):
  f=root/name;sources[str(f.relative_to(ROOT))]=sha(f)
 # Byte proof copied into the immutable lineage, no dependency on mutable scratch.
 for key in ('expected','actual'):shutil.copyfile(P/matched[key]['path'],root/('fixture-'+key+'.json'))
 save(root/'choice-gate.json',matched);sources[str((root/'choice-gate.json').relative_to(ROOT))]=sha(root/'choice-gate.json')
 save(root/'compile-receipt.json',{'schema':'packet59c.cpu-build.v1','passed':True,'device_executed':False,'sources':sources,'artifacts':artifacts})
 save(root/'byte-fixture.json',{'schema':'own-runtime.screen.byte-fixture.v1','passed':True,'device_executed':False,'build_receipt_sha256':sha(root/'compile-receipt.json'),'changed_class':'sealed draft choices; unchanged packet56 target fixtures; two fresh CPU draft runs','command':['nice','-n','19','taskset','-c','8-15,24-31','env','OMP_NUM_THREADS=2','python3','-B',str(P/'p59c_cpu_gate.py')],'sources':sources,'expected':{'path':'fixture-expected.json','sha256':sha(root/'fixture-expected.json')},'actual':{'path':'fixture-actual.json','sha256':sha(root/'fixture-actual.json')}})
 sys.path.insert(0,str(P.parent/'screen'));from seal import create
 create(root,'tp2',root/'compile-receipt.json',root/'byte-fixture.json',root/'build/device/own-rt-iq3',root/'dispatch-speed6.json',root/'build-receipt.json')
 elapsed=time.monotonic()-start
 save(root/'reseal-receipt.json',{'passed':True,'device_executed':False,'binary_sha256':sha(root/'build/device/own-rt-iq3'),'selection_sha256':sha(root/'selection.json'),'seal_sha256':sha(root/'build-receipt.json'),'seconds':elapsed,'under_two_minutes':elapsed<120,'compiled':False})
 assert elapsed<120,'fast reseal exceeded budget'
 print(json.dumps({'passed':True,'device_executed':False,'lineage':str(root.relative_to(ROOT)),'elapsed_seconds':elapsed}))
if __name__=='__main__':main()
