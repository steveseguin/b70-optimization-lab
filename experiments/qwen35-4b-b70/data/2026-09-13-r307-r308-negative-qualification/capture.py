#!/usr/bin/env python3
"""Capture completed negative R307 qualification and R308 trace evidence only."""
import hashlib
import json
from pathlib import Path
import re
import shutil

OUT=Path(__file__).resolve().parent
BASE=Path('/mnt/fast-ai/bench-results')
SINGLE=BASE/'r307-single-request-qualification-20260913'
TRACE=BASE/'r308-acceptance-diagnostic-20260913'
assert (SINGLE/'FAILED').exists() and (TRACE/'DONE').exists()
manifest=[]
summary={'schema':'r307-r308-negative-qualification-v1','qualification_passed':False,'promotion_allowed':False,'stages':{},'health':{},
 'limitations':['R3079B failed even at TP1/MTP3/max_num_seqs1; combined4B/9B qualification is rejected.',
 'R308 is an instrumented diagnostic. Trace observations do not establish an observation-neutral root cause or a fix.',
 '9B second fresh speculative server and strict qualification were never reached.']}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def copy(path):
 dest=OUT/'evidence'/path.relative_to(BASE);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
 manifest.append({'source':str(path),'copy':str(dest.relative_to(OUT)),'sha256':digest(path),'bytes':path.stat().st_size})
for root in (SINGLE,TRACE):
 for name in ('campaign-start.json','campaign.log','FAILED','DONE'):
  if (root/name).exists():copy(root/name)
 for path in root.glob('*flight-*.txt'):copy(path)
 for stage in [p for p in root.iterdir() if p.is_dir() and (p/'result.json').exists()]:
  for name in ('result.json','launch-env.json','server.log','probe.log'):copy(stage/name)
  data=load(stage/'result.json');cases={c['id']:c for c in data['cases']};checks=[]
  oracle=load(SINGLE/('4b-oracle' if stage.name.startswith('4b') else '9b-oracle')/'result.json')
  originals={c['id']:c for c in oracle['cases']}
  for key,case in cases.items():
   if '-tail' in key:
    length,offset=key[1:].split('-tail');prior=originals['L'+length];n=int(offset)
    assert case['prompt_ids']==prior['prompt_ids']+prior['expected_ids'][:n]
    assert case['expected_ids']==prior['expected_ids'][n:]
   else:
    assert case['prompt_ids']==originals[key]['prompt_ids'] and case['expected_ids']==originals[key]['expected_ids']
  if data['mode']=='compare':
   assert data['oracle_sha256']==digest(SINGLE/('4b-oracle' if stage.name.startswith('4b') else '9b-oracle')/'result.json')
  for row in data['rows']:
   case=cases[row['case']];got=row.get('token_ids');want=case['expected_ids']
   complete=isinstance(got,list) and all(type(x)is int and x>=0 for x in got) and len(got)==case['max_tokens']==row['usage']['completion_tokens']
   exact=complete and got==want
   assert row['passed']==exact and row['exact']==exact
   checks.append({'case':row['case'],'repeat':row['repeat'],'concurrency':row['concurrency'],'exact':exact,'complete_numeric_ids':complete,
     'cache_zero':row['cached_tokens']==[0],'prompt_usage_exact':row['usage']['prompt_tokens']==len(case['prompt_ids']),
     'first_diff':next((i for i,(x,y) in enumerate(zip(got,want)) if x!=y),None),
     **({'got':got,'want':want} if not exact else {})})
  env=load(stage/'launch-env.json')
  summary['stages'][f'{root.name}/{stage.name}']={'reported_status':data['status'],'reported_passed':data['passed'],
   'image':env['IMAGE'],'mtp_depth':env['MTP_DEPTH'],'max_num_seqs':env['MAX_NUM_SEQS'],'rows':len(checks),
   'exact_rows':sum(r['exact'] for r in checks),'complete_numeric_rows':sum(r['complete_numeric_ids'] for r in checks),
   'cache_zero_all':all(r['cache_zero'] for r in checks),'checks':checks,
   'contract_lines':[line for line in (stage/'server.log').read_text().splitlines() if 'IMAGE CONTRACT' in line]}
 for compute in root.glob('*postflight-compute-xccl.txt'):
  prefix=compute.name.removesuffix('-compute-xccl.txt');text=compute.read_text();journal=root/(prefix+'-after-journal.txt');discovery=root/(prefix+'-discovery.txt')
  faults=[x for x in journal.read_text().splitlines() if re.search(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup',x,re.I) and 'Xe device coredump has been deleted.' not in x]
  summary['health'][f'{root.name}/{prefix}']={'fault_lines':faults,'normal_devices':discovery.read_text().count('Device State: normal'),
   'compute_smokes':text.count('ok 2097152.0'),'rank0_allreduce_ok':'rank 0 allreduce ok 2.0' in text,'rank1_allreduce_ok':'rank 1 allreduce ok 2.0' in text}
trace_lines=[x for x in (TRACE/'9b-acceptance-trace/server.log').read_text().splitlines() if 'R308_TRACE_' in x]
(OUT/'trace-lines.txt').write_text('\n'.join(trace_lines)+'\n')
summary['trace_lines']=len(trace_lines)
(OUT/'.gitattributes').write_text('evidence/** -whitespace\n')
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
(OUT/'source-manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'files':len(manifest),'bytes':sum(p['bytes'] for p in manifest),'stages':{k:[v['exact_rows'],v['rows']] for k,v in summary['stages'].items()}}))
