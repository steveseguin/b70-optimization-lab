#!/usr/bin/env python3
"""Capture the completed serial R308 lifecycle trace and verify its six transitions."""
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path('/mnt/fast-ai/bench-results/r308-lifecycle-diagnostic-20260913')
OUT=Path(__file__).resolve().parent
assert (ROOT/'DONE').exists()
STAGE=ROOT/'9b-acceptance-trace'
manifest=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for path in sorted(ROOT.glob('*'))+sorted(STAGE.glob('*')):
 if not path.is_file() or path.name.endswith('inspect.json'):continue
 dest=OUT/'evidence'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
 manifest.append({'source':str(path),'copy':str(dest.relative_to(OUT)),'sha256':sha(path),'bytes':path.stat().st_size})
data=json.loads((STAGE/'result.json').read_text());assert data['status']=='complete' and not data['passed'] and data['configuration']['concurrency']==[1]
cases={c['id']:c for c in data['cases']}
requests={}
for number,line in enumerate((STAGE/'server.log').read_text().splitlines(),1):
 match=re.search(r'R308_TRACE_(ACCEPTED_AFTER|REMOVE|READD|RUNNER) (\{.*\})',line)
 if not match:continue
 event=ast.literal_eval(match[2]);ids=event.get('req_ids',[event.get('req_id')])
 for req in ids:
  requests.setdefault(req,[]).append({'event':match[1],'line':number,'data':event})
chains=[]
for req,events in requests.items():
 for i,event in enumerate(events):
  if event['event']!='ACCEPTED_AFTER' or event['data']['accepted_gpu']!=[2]:continue
  chain=events[i:i+5]
  assert [x['event'] for x in chain]==['ACCEPTED_AFTER','REMOVE','READD','RUNNER','ACCEPTED_AFTER']
  a,b,c,d,e=[x['data'] for x in chain]
  assert a['computed']==[252] and b['accepted_cpu']==b['accepted_gpu']==2 and b['resumed'] is False
  assert c['accepted_cpu']==1 and c['computed']==254 and c['resumed'] is False
  assert d['accepted_gpu']==d['input_batch_accepted_cpu']==[1] and d['computed_cpu']==[254] and d['one_token_decode']==[True]
  assert e['computed']==[254]
  chains.append({'request_id':req,'events':chain,'final_sampled_token':e['sampled_ids'][0][0]})
assert len(chains)==len(data['rows'])==6
for chain,row in zip(chains,data['rows']):
 case=cases[row['case']];got=row['token_ids'];want=case['expected_ids']
 assert all(type(x)is int for x in got) and len(got)==len(want)==row['usage']['completion_tokens']==case['max_tokens']
 assert got[:-1]==want[:-1] and got[-1]!=want[-1] and got[-1]==chain['final_sampled_token']
 assert row['cached_tokens']==[0] and row['usage']['prompt_tokens']==len(case['prompt_ids'])
 chain.update(case=row['case'],repeat=row['repeat'],got_last=got[-1],expected_last=want[-1],first_diff=len(got)-1,absolute_position=255)
prefix='9b-acceptance-trace-postflight'
health=(ROOT/(prefix+'-compute-xccl.txt')).read_text();journal=(ROOT/(prefix+'-after-journal.txt')).read_text();discovery=(ROOT/(prefix+'-discovery.txt')).read_text()
faults=[x for x in journal.splitlines() if re.search(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup',x,re.I) and 'Xe device coredump has been deleted.' not in x]
summary={'schema':'r308-lifecycle-negative-v1','qualification_passed':False,'promotion_allowed':False,'functional_fix_tested':False,
 'requests':6,'exact_outputs':0,'verified_acceptance_reset_chains':6,
 'association':'Requests are serial (concurrency1); receipt rows paired with chronological trace chains and verified against traced final sampled IDs. Probe rows do not retain server request IDs.',
 'mechanism':'Accepted count2 is present at non-resumed removal, resets to1 at re-add, and reaches final one-token runner as1 in every failed request.',
 'chains':chains,'postflight':{'fault_lines':faults,'normal_devices':discovery.count('Device State: normal'),'compute_smokes':health.count('ok 2097152.0'),'rank0_allreduce_ok':'rank 0 allreduce ok 2.0' in health,'rank1_allreduce_ok':'rank 1 allreduce ok 2.0' in health},
 'limitations':['Instrumented execution; functional repair and unchanged-runtime qualification remain separate required evidence.','DONE denotes completed diagnostic, not quality pass.']}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
(OUT/'source-manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
(OUT/'.gitattributes').write_text('evidence/** -whitespace\n')
print(json.dumps({'copied_files':len(manifest),'bytes':sum(x['bytes'] for x in manifest),'verified_chains':len(chains)}))
