#!/usr/bin/env python3
"""Host CopyEngine regression and synthetic forced-choice adoption sweep."""
import contextlib,copy,io,json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from storage import admit,digest,discard
from cpu_gates import host
from math_gate import closure
import k2_summary
from merge_dispatch import validate
P=Path(__file__).resolve().parent;E=P/'evidence/copy-extent-fix';B=P/'build/copy-extent-gate'
SOURCES=('copy_selection_gate.cpp','gemv_timing.cpp','p25_bridge.cpp','runtime_kernels.cpp',
 'adapter.cpp','performance.cpp','specialised_submit.cpp','round2_submit.cpp','p42_submit.cpp',
 'p30_submit.cpp','p33r2.cpp','p33_submit.cpp','p28/submit.cpp','expert_down.cpp',
 'small_gemv.cpp','small_gemv_fixture.cpp','adapter_fixture.cpp','p39_fixture.cpp','p39_submit.cpp',
 'route42_submit.cpp','owner.cpp','owner_retire.cpp')
def pins():
 files=set(closure())|{P/n for n in SOURCES}|{P/n for n in ('copy_extent_gate.cpp','copy_adoption_gate.py','k2_summary.py','k2-class-registry.json','kernel-registry.json','merge_dispatch.py','validation_mirror.py','test_copy_adoption.py')}
 return {str(f.relative_to(P.parents[3])):digest(f) for f in sorted(files)}
def expected():
 rows=[]
 for context in (256,4096,32768):
  for name,entry in k2_summary.registry_for_context(context).items():
   if not (name.startswith('gemv:') or name=='qsa.attention'):continue
   if context!=256 and name.startswith('gemv:'):continue # GEMV geometry is capacity-independent.
   for candidate in dict.fromkeys([entry.get('incumbent','packet18'),*entry['candidates']]):rows.append((name,context,candidate))
 return rows
def compile_gate(name,sources,validation=False):
 admit(200_000_000)
 cmd=['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-ffunction-sections','-fdata-sections','-Wl,--gc-sections']
 if validation:cmd+=['-I'+str(B/'validation')]
 cmd+=['-I'+str(B),'-I'+str(P),*[str(B/'validation'/n if validation and n in ('adapter.cpp','performance.cpp') else P/n) for n in sources],'-lcrypto','-o',str(B/name)]
 with (E/(name+'-compile.log')).open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 assert r.returncode==0,name
 host(B/name);return cmd
def run_gate(name,args):
 with (E/(name+'.log')).open('w') as log:r=subprocess.run([str(B/name),*map(str,args)],stdout=log,stderr=subprocess.STDOUT)
 assert r.returncode==0,(name,(E/(name+'.log')).read_text()[-2000:])
 return [json.loads(s) for s in (E/(name+'.log')).read_text().splitlines()]
def verify(gate=None):
 gate=gate or json.loads((P/'copy-adoption-gates.json').read_text())
 assert gate['passed'] and gate['device_executed'] is False and gate['synthetic_selection_only'] is True
 assert gate['compiled_sources_sha256']==pins(),'stale copy/adoption sources'
 assert [(r['class'],r['context'],r['candidate']) for r in gate['selection_rows']]==expected(),'selection coverage differs'
 assert gate['extent_result']['cases']==8 and gate['extent_result']['failures']==0
 assert gate['extent_result']['byte_cases']==4 and gate['extent_result']['guard_rejections']==5
 assert len(gate['extent_rows'])==8 and all(r['passed'] and 0<r['maximum_copy']<=4*1024*1024 for r in gate['extent_rows'])
 assert gate['extent_rows'][0]['bank_bytes']==268697600 and gate['extent_rows'][0]['rotations']==8
 for name,row in gate['programs'].items():
  assert digest(B/name)==row['binary_sha256'] and digest(E/(name+'.log'))==row['log_sha256']
  raw=[json.loads(s) for s in (E/(name+'.log')).read_text().splitlines()]
  if name=='after':assert raw==gate['extent_rows']+[gate['extent_result']]
  else:
   assert raw[-1]['rows']==len(expected()) and raw[-1]['passed'] and len(raw)==len(expected())+1
   assert all(r['passed'] and r['checks']>0 for r in raw[:-1])
   assert [(r['class'],r['context']) for r in raw[:-1]]==[(n,c) for n,c,v in expected()]
 for n,h in gate['generated_sha256'].items():assert digest(B/'validation'/n)==h
 assert digest(P/gate['archive']['path'])==gate['archive']['sha256']
 return gate
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 E.mkdir(exist_ok=True,parents=True);B.mkdir(exist_ok=True);source_pins=pins()
 (B/'owner.hpp').write_text('#include "'+str(P/'owner_api.hpp')+'"\n')
 (B/'device_validation.hpp').write_text('#pragma once\nnamespace fixture_validation {inline bool only=false,inject=false;}\n')
 validation=B/'validation';validation.mkdir(exist_ok=True)
 from validation_mirror import generate
 generate(B/'generated')
 for n in ('device_validation.hpp','adapter.cpp','performance.cpp'):
  (validation/n).write_text((B/'generated'/n).read_text().replace(str(P/'build/checked')+'/',str(P.parents[3])+'/'))
 commands={'after':compile_gate('after',('copy_extent_gate.cpp','owner.cpp','owner_retire.cpp')),
           'selection':compile_gate('selection',SOURCES,True)}
 extent=run_gate('after',[])
 root=Path(tempfile.mkdtemp(prefix='copy-adoption-',dir=P/'build'));rows=[];manifest=[]
 neutral=dict(schema='packet26.dispatch.v1',classes={},gemv={},fusions={})
 (root/'dispatch-default.json').write_text(json.dumps(neutral))
 for index,(name,context,winner) in enumerate(expected()):
  admit(20_000_000);entry=k2_summary.registry_for_context(context)[name];incumbent=entry.get('incumbent','packet18')
  arm=root/str(index);arm.mkdir();events=[]
  for candidate in entry['candidates']:
   for mode in entry.get('timing_modes',['reread']):
    for workload in entry.get('workloads',[name]):
     for rep in range(200):
      for variant in ('packet18','specialised'):
       cost=100 if variant=='packet18' else 50 if candidate==winner else 150
       events.append(dict(**{'class':name},candidate=candidate,implementation=entry.get('baseline_implementation',incumbent) if variant=='packet18' else candidate,
        variant=variant,workload=workload,repetition=rep,stage_count=1,start_ns=1,end_ns=1+cost,
        exact=True,bytes_equal=True,candidate_available=True,timing_mode=mode,rotation_copies=8,
        buffer_copy=(rep+(4 if variant=='specialised' else 0))%8,payload_bytes=1,full_payload_bytes=1,
        state_storage=entry.get('state_storage'),same_kernel=candidate==incumbent))
  (arm/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in events))
  # A neutral input dispatch isolates each choice; the real selector, serializer,
  # parser, registry, allocations, submissions and CopyEngine are unchanged.
  with patch.object(k2_summary,'HERE',root),contextlib.redirect_stdout(io.StringIO()):
   result=k2_summary.summarize(arm,classes={name:entry})
  assert result['passed'],result['failures']
  assert result['selection'][name]==winner,(name,winner,result['selection'])
  validate(result['final_dispatch']);dispatch=arm/'dispatch-measured.json'
  manifest.append(f'{name} {context} {dispatch}\n')
  rows.append(dict(**{'class':name},context=context,candidate=winner,dispatch_sha256=digest(dispatch),summary_sha256=digest(arm/'summary.json')))
 (root/'manifest.tsv').write_text(''.join(manifest))
 selected=run_gate('selection',[root/'manifest.tsv',root/'native'])
 assert selected[-1]['rows']==len(rows)
 archive=discard(root)
 assert pins()==source_pins,'source changed during gate'
 gate=dict(passed=True,device_executed=False,synthetic_selection_only=True,compiled_sources_sha256=source_pins,
  selection_rows=rows,selection_checks=selected[-1]['checks'],extent_rows=extent[:-1],extent_result=extent[-1],archive=archive,
  generated_sha256={n:digest(validation/n) for n in ('device_validation.hpp','adapter.cpp','performance.cpp')},
  programs={n:dict(command=c,binary_sha256=digest(B/n),log_sha256=digest(E/(n+'.log'))) for n,c in commands.items()})
 verify(gate);(P/'copy-adoption-gates.json').write_text(json.dumps(gate,indent=2)+'\n')
 print('PASS',len(rows),'adopted choices;',gate['selection_checks'],'native checks; 8 full-geometry P39 fixtures')
if __name__=='__main__':main()
