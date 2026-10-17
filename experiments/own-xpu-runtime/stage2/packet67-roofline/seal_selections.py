#!/usr/bin/env python3
"""Bind both host compiler gates, actual submitters, selections and one binary."""
import importlib.util,json,os,shutil,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sys.path.insert(0,str(P/'screen'))
from common import read,require,sha,save,verify_map
from conditions import cpu_gate
from cpu_seal import verify as wrapper_verify
from prepare_views import CHOICES
def link(a,b):
 b.parent.mkdir(parents=True,exist_ok=True)
 if b.exists():require(sha(a)==sha(b),'existing artifact differs')
 else:os.link(a,b)
def main():
 cpu_gate();wrapper_verify();build=read(P/'build-device-receipt.json');verify_map(ROOT,build['sources']);verify_map(P,build['artifacts'])
 sg=read(P/'evidence/selection-tests.json')
 require(sg['passed'] and sg['build_receipt_sha256']==sha(P/'build-device-receipt.json') and sg['source_sha256']==sha(P/'submit_fixture.cpp') and sg['driver_sha256']==sha(P/'selection_tests.py'),'fresh actual submitters and parser gate required')
 fixture_sources={};retained=[]
 for mode,dirname in (('gnu','fixture-gnu-b'),('intel','fixture-intel')):
  root=P/'build'/dirname;receipt=read(root/'receipt.json');require(receipt['passed'] and not receipt['device_executed'],'CPU fixture failed')
  require(receipt['fixture_driver_sha256']==sha(P/'cpu_fixture.py'),'fixture driver changed');verify_map(ROOT,receipt['sources']);fixture_sources.update(receipt['sources'])
  require(len(receipt['runs'])==2,'two fresh CPU runs required')
  for n,row in enumerate(receipt['runs'],1):
   require(row['native']['cases']==60 and row['native']['passed'] and row['native']['nan_tolerance'] is False,'fixture coverage')
   require(sha(root/f'repeat-{n}'/'expected.bin')==sha(root/f'repeat-{n}'/'candidate.bin')==row['candidate_sha256']==row['expected_sha256'],'fixture bytes differ')
   require(sha(root/f'repeat-{n}'/'cases.jsonl')==row['cases_sha256'],'case manifest changed')
  require(receipt['runs'][0]['candidate_sha256']==receipt['runs'][1]['candidate_sha256'],'fresh repeat differs')
  dest=P/'evidence'/('cpu-'+mode);dest.mkdir(exist_ok=True)
  for name in ('receipt.json','compile.log','dependencies.d'):shutil.copyfile(root/name,dest/name);retained.append(dest/name)
  for n in (1,2):
   (dest/f'repeat-{n}').mkdir(exist_ok=True)
   for name in ('native.json','cases.jsonl','run.log'):shutil.copyfile(root/f'repeat-{n}'/name,dest/f'repeat-{n}'/name);retained.append(dest/f'repeat-{n}'/name)
 source=importlib.util.spec_from_file_location('generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(source);source.loader.exec_module(generic)
 extras=set(retained+[P/'seal_selections.py',P/'selection_tests.py',P/'prepare_views.py',P/'cpu_fixture.py',P/'submit_fixture.cpp',P/'verify_packet.py',P/'evidence/selection-tests.json',P/'evidence/host-compilers.json',P/'build-device-receipt.json',P/'screen/placement-validation/wrapper-seal.json',P.parent/'screen/seal.py'])
 extras.update((P/'screen').glob('*.py'));extras.update((P/'screen').glob('*.json'));extras.add(P/'screen/placement-jobs.txt')
 registers=read(P/'register-report.json');require(registers['passed'] and not registers['device_executed'],'offline build proof')
 extras.update((P/'register-report.json',P/'inspect_registers.py'))
 for kernel in registers['kernels']:
  path=ROOT/kernel['assembly'];require(sha(path)==kernel['sha256'],'offline assembly changed');extras.add(path)
 fixtures=P/'build/fixture-gnu-b/repeat-1'
 for choice in CHOICES:
  view=P/'selections'/choice;require(not (view/'screen-seal.json').exists(),'already sealed')
  for name in ('dispatch-speed6.json','memory-plan.json'):shutil.copyfile(P/name,view/name)
  for name in build['artifacts']:link(P/name,view/name)
  for name in ('expected.bin','candidate.bin'):link(fixtures/name,view/'fixture'/name)
  engine={str((P/name).relative_to(ROOT)):sha(P/name) for name in ('main.cpp','rank.hpp','mtp.hpp','p56_config.hpp','p56_prefix.hpp','p49d_submit.cpp','p60_submit.cpp','p67_hc.hpp','p67_recurrence.hpp','strict_snapshot.hpp')}
  save(view/'placement-audit.json',dict(schema='packet67.placement-audit.v1',placement='1',draft_rank=1,target_split=0,target_layers=[24,24],dispatch_sha256=sha(view/'dispatch-speed6.json'),binary_sha256=sha(view/'build/device/own-rt-iq3'),engine_sources=engine,rationale='same 24/24 packet64 production placement; 49920-byte head scratch fits existing QSA-dominated arena; no new allocation; device parity pending'))
  sources=dict(build['sources'],**fixture_sources);sources.update({str(p.relative_to(ROOT)):sha(p) for p in extras})
  for name in ('selection.json','placement-audit.json'):sources[str((view/name).relative_to(ROOT))]=sha(view/name)
  bp,fp=view/'build-receipt.json',view/'byte-fixture.json'
  save(bp,dict(schema='packet67.selection.build.v1',passed=True,device_executed=False,sources=sources,artifacts=build['artifacts'],selected=choice,parent_build_sha256=sha(P/'build-device-receipt.json')))
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='HC attention/FFN gate-mix and GDN head-once recurrence; every selectable candidate',command=['python3','-B',str(P/'cpu_fixture.py')],sources=fixture_sources,build_receipt_sha256=sha(bp),
       expected=dict(path='fixture/expected.bin',sha256=sha(view/'fixture/expected.bin')),actual=dict(path='fixture/candidate.bin',sha256=sha(view/'fixture/candidate.bin')),
       compilers=2,fresh_runs_per_compiler=2,cases_per_run=60,compiler_specific_nan_payloads=True,device_quality='pending packet49 screen; CPU model never run'))
  generic.create(view,'tp2',bp,fp,view/'build/device/own-rt-iq3',view/'dispatch-speed6.json',view/'screen-seal.json')
 print('five views sealed; one binary; 240 passing fixture cases; no device execution')
if __name__=='__main__':main()
